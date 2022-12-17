import io
import sys
from pathlib import Path
from threading import Lock

from PIL import Image


class AbstractSource:
    """
    An abstract camera source.

    The *config* is the application configuration object.
    """
    def __init__(self, config):
        self._lock = Lock()
        self._clients = []

    def start_preview(self, angle, resolution):
        """
        Start a live preview from the camera, passing JPEG image frames to
        the internal :meth:`_preview_frame` method. The *angle* is the current
        angle of the tree, and *resolution* is the expected preview resolution.
        """
        raise NotImplementedError

    def stop_preview(self):
        """
        Terminate the live preview from the camera.
        """
        raise NotImplementedError

    def capture(self, angle, led, color):
        """
        Capture a high-quality (highest possible resolution) image of the tree
        at *angle* with *led* lit with specified *color*. Expected to return a
        file-like object containing the JPEG image data.
        """
        raise NotImplementedError

    def _preview_frame(self, frame):
        died = []
        size = len(frame)
        with self._lock:
            for client in self._clients:
                try:
                    client.wfile.write(b'--FRAME\r\n')
                    client.send_header('Content-Type', 'image/jpeg')
                    client.send_header('Content-Length', size)
                    client.end_headers()
                    client.wfile.write(frame)
                    client.wfile.write(b'\r\n')
                except Exception as e:
                    died.append(client)
        if died:
            self.remove_clients(died)

    def add_client(self, client):
        with self._lock:
            if not self._clients:
                angle = int(client.query.get('angle', ['0'])[0])
                resolution = (
                    int(client.query.get('width', ['640'])[0]),
                    int(client.query.get('height', ['480'])[0]),
                )
                self.start_preview(angle, resolution)
            self._clients.append(client)

    def remove_clients(self, clients):
        with self._lock:
            for client in clients:
                try:
                    self._clients.remove(client)
                except ValueError:
                    pass # already removed
            if not self._clients:
                self.stop_preview()


class FilesSource(AbstractSource):
    def __init__(self, config):
        assert config.camera_type == 'files'
        if not config.camera_path:
            raise RuntimeError('path must be specified for the "files" camera')

        super().__init__(config)
        self._path = config.camera_path
        self._preview = None

    def start_preview(self, angle, resolution):
        base_path = self._path / f'angle{angle:03d}_base.jpg'
        image = Image.open(base_path).resize(resolution)
        preview = io.BytesIO()
        image.save(preview, format='jpeg')
        preview.seek(0)
        self._preview = preview

    def stop_preview(self):
        self._preview = None

    def capture(self, angle, led, color):
        if self._preview is not None:
            raise RuntimeError('Cannot capture while previewing')
        return (
            self._path /
            f'angle{angle:03d}_led{led:03d}_color{color.html}.jpg').open('rb')

    def add_client(self, client):
        super().add_client(client)
        self._preview_frame(self._preview.getvalue())


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
    def __init__(self, config):
        from picamera import PiCamera
        assert config.camera_type == 'picamera'

        super().__init__(config)
        self._camera = PiCamera()
        self._preview = None

    def start_preview(self, angle, resolution):
        self._preview = PiCameraOutput(self)
        self._camera.resolution = resolution
        self._camera.start_recording(self._preview, format='mjpeg')

    def stop_preview(self):
        self._camera.stop_recording()
        self._preview = None

    def capture(self, angle, led, color):
        if self._preview is not None:
            raise RuntimeError('Cannot capture while previewing')
        self._camera.resolution = self._camera.MAX_RESOLUTION
        frame = io.BytesIO()
        self._camera.capture(frame, format='jpeg')
        frame.seek(0)
        return frame


class GStreamerSource(AbstractSource):
    Gst = None
    GstVideo = None

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
        self._pipeline = None

    def start_preview(self, angle, resolution):
        self._pipeline = self.Gst.parse_launch(
            f"""
            v4l2src device={self._device} !
            capsfilter caps=image/jpeg,width={resolution[0]},height={resolution[1]} !
            queue leaky=upstream silent=true !
            appsink emit-signals=true name=sink
            """)
        self._pipeline.set_state(self.Gst.State.PLAYING)
        sink = self._pipeline.get_by_name('sink')
        sink.connect('new-sample', self._new_sample, None)

    def stop_preview(self):
        self._pipeline.send_event(self.Gst.Event.new_eos())
        self._pipeline.set_state(self.Gst.State.NULL)
        self._pipeline = None

    def capture(self, angle, led, color):
        pass

    def _new_sample(self, sink, user_data):
        sample = sink.emit('pull-sample')
        if not isinstance(sample, self.Gst.Sample):
            return self.Gst.FlowReturn.ERROR
        buf = sample.get_buffer()
        self._preview_frame(buf.extract_dup(0, buf.get_size()))
        return self.Gst.FlowReturn.OK
