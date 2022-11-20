import struct
from queue import Empty
from threading import Thread, Event

import paho.mqtt.client as mqtt


def render(animation, fps):
    """
    Given an *animation* (which is a list of lists of (index, r, g, b) tuples),
    and an *fps* speed, returns a byte-string representation of the animation.

    The byte-string returned leads with a single unsigned byte containing the
    *fps* value. This is followed by an unsigned short (2-bytes) containing the
    number of frames. Then follows, for each frame, a single unsigned byte
    containing the number of following LED changes, then for each LED change
    four unsigned bytes comprising the LED index, red, green, and blue values.
    """
    def chunks():
        yield struct.pack('!BH', fps, len(animation))
        for frame in animation:
            yield struct.pack('!B', len(frame))
            for index, r, g, b in frame:
                yield struct.pack('!BBBB', index, r, g, b)
    return b''.join(chunks())


class MessageThread(Thread):
    def __init__(self, queue, config):
        super().__init__(target=self.listen, daemon=True)
        self.queue = queue
        self.host = config.broker_address
        self.port = config.broker_port
        self.topic = config.topic
        self.fps = config.fps
        self.exception = None
        self._stopping = Event()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *exc_info):
        if self.exception:
            raise self.exception
        self.stop()

    def stop(self):
        self._stopping.set()

    def listen(self):
        try:
            client = mqtt.Client(clean_session=True)
            client.connect(self.host, self.port, keepalive=120)
            while not self._stopping.wait(0):
                client.loop(timeout=0.1)
                try:
                    frames = self.queue.get(timeout=1)
                except Empty:
                    pass
                else:
                    client.publish(self.topic, render(frames, self.fps), qos=1)
        except Exception as e:
            self.exception = e
