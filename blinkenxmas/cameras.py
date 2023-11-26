import io
import sys
from pathlib import Path
from threading import Lock, Thread, Event, Condition

from PIL import Image


class AbstractSource:
    """
    An abstract camera source.

    The *config* is the application configuration object.
    """
    def __init__(self, config):
        self._lock = Lock()
        self._clients = []
        self.frame = b''
        self.frame_ready = Condition()

    def start_preview(self, angle):
        """
        Start a live preview from the camera, passing JPEG image frames to
        the internal :meth:`_preview_frame` method. The *angle* is the current
        angle of the tree.
        """
        raise NotImplementedError

    def stop_preview(self):
        """
        Terminate the live preview from the camera.
        """
        raise NotImplementedError

    def capture(self, angle, led=None):
        """
        Capture a high-quality (highest possible resolution) image of the tree
        at *angle* with *led* lit full white. Expected to return a file-like
        object containing the JPEG image data.
        """
        raise NotImplementedError

    def _preview_frame(self, frame):
        with self.frame_ready:
            self.frame = frame
            if self.frame:
                self.frame_ready.notify_all()

    def add_client(self, client):
        with self._lock:
            if not self._clients:
                angle = int(client.query.get('angle', '0'))
                self.start_preview(angle)
            self._clients.append(client)

    def remove_client(self, client):
        with self._lock:
            try:
                self._clients.remove(client)
            except ValueError:
                pass # already removed
            if not self._clients:
                self.stop_preview()


class FilesSource(AbstractSource):
    thread = None
    lock = Lock()
    stop = Event()

    def __init__(self, config):
        assert config.camera_type == 'files'
        if not config.camera_path:
            raise RuntimeError('path must be specified for the "files" camera')

        super().__init__(config)
        self._path = config.camera_path
        self._preview_res = config.camera_preview

    def start_preview(self, angle):
        with FilesSource.lock:
            if FilesSource.thread is None:
                FilesSource.thread = Thread(
                    target=self._preview_thread, args=(angle,), daemon=True)
                FilesSource.stop.clear()
                FilesSource.thread.start()

    def stop_preview(self):
        with FilesSource.lock:
            if FilesSource.thread is not None:
                FilesSource.stop.set()
                FilesSource.thread = None

    def _preview_thread(self, angle):
        base_path = self._path / f'angle{angle:03d}_base.jpg'
        image = Image.open(base_path).resize(self._preview_res)
        preview = io.BytesIO()
        image.save(preview, 'jpeg')
        while not FilesSource.stop.wait(timeout=0.1):
            self._preview_frame(preview.getvalue())

    def capture(self, angle, led=None):
        if FilesSource.thread is not None:
            raise RuntimeError('Cannot capture while previewing')
        if led is None:
            return (self._path / f'angle{angle:03d}_base.jpg').open('rb')
        else:
            return (
                self._path /
                f'angle{angle:03d}_led{led:03d}.jpg').open('rb')


class PiCameraOutput:
    def __init__(self, source):
        self.source = source
        self.frame = io.BytesIO()

    def write(self, buf):
        if buf.startswith(b'\xff\xd8'):
            size = self.frame.tell()
            self.frame.seek(0)
            self.source._preview_frame(self.frame.read(size))
            self.frame.seek(0)
        self.frame.write(buf)

    def flush(self):
        pass


class PiCameraSource(AbstractSource):
    lock = Lock()
    output = None

    def __init__(self, config):
        from picamera import PiCamera
        assert config.camera_type == 'picamera'

        super().__init__(config)
        self._camera = PiCamera()
        self._capture_res = config.camera_capture
        self._preview_res = config.camera_preview

    def start_preview(self, angle):
        with PiCameraSource.lock:
            if PiCameraSource.output is None:
                PiCameraSource.output = PiCameraOutput(self)
                self._camera.resolution = self._preview_res
                self._camera.start_recording(
                    PiCameraSource.output, format='mjpeg')

    def stop_preview(self):
        with PiCameraSource.lock:
            if PiCameraSource.output is not None:
                self._camera.stop_recording()
                PiCameraSource.output = None

    def capture(self, angle, led=None):
        self.stop_preview()
        self._camera.resolution = self._capture_res
        frame = io.BytesIO()
        self._camera.capture(frame, format='jpeg')
        frame.seek(0)
        return frame


class GStreamerSource(AbstractSource):
    Gst = None
    GstVideo = None

    thread = None
    lock = Lock()
    stop = Event()

    def __init__(self, config):
        if GStreamerSource.Gst is None:
            import gi
            gi.require_version('GLib', '2.0')
            gi.require_version('GObject', '2.0')
            gi.require_version('Gst', '1.0')
            gi.require_version('GstVideo', '1.0')
            from gi.repository import Gst, GstVideo
            Gst.init(sys.argv)
            GStreamerSource.Gst = Gst
            GStreamerSource.GstVideo = GstVideo
        assert config.camera_type == 'gstreamer'
        if not config.camera_device:
            raise RuntimeError(
                'device must be specified for the "gstreamer" camera')

        super().__init__(config)
        self._device = config.camera_device
        self._capture_res = config.camera_capture
        self._preview_res = config.camera_preview
        self._captured = Event()
        self._discard = 0

    def start_preview(self, angle):
        with GStreamerSource.lock:
            if GStreamerSource.thread is None:
                GStreamerSource.thread = Thread(
                    target=self._gst_thread, daemon=True)
                GStreamerSource.stop.clear()
                GStreamerSource.thread.start()

    def stop_preview(self):
        with GStreamerSource.lock:
            if GStreamerSource.thread is not None:
                GStreamerSource.stop.set()
                # NOTE: You cannot attempt to join the thread because it's
                # actually the current thread (but Python doesn't realize that
                # presumably due to the roundabout way the thread's entered
                # via a GStreamer callback)
                GStreamerSource.thread = None

    def capture(self, angle, led=None):
        self.stop_preview()
        width, height = self._capture_res
        pipeline = self.Gst.parse_launch(
            f"""
            v4l2src device={self._device} !
            capsfilter caps=image/jpeg,width={width},height={height} !
            appsink drop=true emit-signals=true name=sink
            """)
        if pipeline.set_state(self.Gst.State.PLAYING) == self.Gst.StateChangeReturn.FAILURE:
            raise RuntimeError('failed to start GStreamer pipeline')
        data = io.BytesIO()
        try:
            sink = pipeline.get_by_name('sink')
            # Number of frames to initially discard; some cameras require
            # several "warm-up" frames to measure white-balance, exposure,
            # and so on so discard a few before capturing
            self._discard = 10
            self._captured.clear()
            sink.connect('new-sample', self._capture_sample, data)
            if not self._captured.wait(timeout=30):
                raise RuntimeError('failed to capture image')
            data.seek(0)
            return data
        finally:
            pipeline.set_state(self.Gst.State.NULL)

    def _capture_sample(self, sink, data):
        sample = sink.emit('pull-sample')
        if not isinstance(sample, self.Gst.Sample):
            return self.Gst.FlowReturn.ERROR
        buf = sample.get_buffer()
        self._discard -= 1
        if not self._discard:
            data.write(buf.extract_dup(0, buf.get_size()))
            self._captured.set()
        return self.Gst.FlowReturn.OK

    def _gst_thread(self):
        width, height = self._preview_res
        pipeline = self.Gst.parse_launch(
            f"""
            v4l2src device={self._device} !
            capsfilter caps=image/jpeg,width={width},height={height} !
            appsink drop=true emit-signals=true name=sink
            """)
        if pipeline.set_state(self.Gst.State.PLAYING) == self.Gst.StateChangeReturn.FAILURE:
            raise RuntimeError('failed to start GStreamer pipeline')
        try:
            sink = pipeline.get_by_name('sink')
            sink.connect('new-sample', self._preview_sample, None)
            self.stop.wait()
        finally:
            pipeline.set_state(self.Gst.State.NULL)

    def _preview_sample(self, sink, user_data):
        sample = sink.emit('pull-sample')
        if not isinstance(sample, self.Gst.Sample):
            return self.Gst.FlowReturn.ERROR
        buf = sample.get_buffer()
        self._preview_frame(buf.extract_dup(0, buf.get_size()))
        return self.Gst.FlowReturn.OK
