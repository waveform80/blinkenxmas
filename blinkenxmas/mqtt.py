import io
import time
import struct
from queue import Empty
from threading import Thread, Event

import paho.mqtt.client as mqtt
from colorzero import Color

from .pico.animation import (
    packet_fmt,
    anim_fmt,
    frame_fmt,
    led_fmt,
)


def render(animation, fps, chunk_size=1024):
    """
    Given an *animation* (which is a list of lists of strings of HTML color
    specifications), and an *fps* speed, returns a byte-string representation
    of the animation.

    The byte-string returned consists of:

    * An unsigned byte containing the *fps* value

    * An unsigned short (2 bytes in network order) containing the number of
      frames following

    * For each frame:

      * An unsigned byte containing the number of LED changes following

      * For each LED change:

        * An unsigned byte with the zero-based index of the LED

        * An unsigned short (2 bytes in network order) containing the color
          of the LED in RGB565 format

    For example, an animation that switches the first and second LEDs between
    red and blue at 1fps would be rendered as::

        b"\x01\x02\x02\x00\xF8\x00\x01\x00\x00\x02\x00\x00\x00\x01\x00\x1F"
    """
    def convert(frames):
        # Convert HTML color codes into RGB565 representation
        for frame in frames:
            yield [Color(html).rgb565 for html in frame]

    def diff(frames):
        # Determine which LEDs actually changed from each frame to the next
        last = None
        for frame in frames:
            if last is None:
                yield [
                    (index, color)
                    for index, color in enumerate(frame)
                ]
            else:
                yield [
                    (index, color)
                    for index, color in enumerate(frame)
                    if last[index] != color
                ]
            last = frame

    def serialize(frames):
        # Convert list of lists into a simple byte-string representation
        yield struct.pack(anim_fmt, fps, len(animation))
        for frame in frames:
            yield struct.pack(frame_fmt, len(frame))
            for index, color in frame:
                yield struct.pack(led_fmt, index, color)

    def chunkify(stream, chunk_size):
        # Split into 1KB chunks with headers
        s = b''.join(stream)
        ident = time.monotonic_ns() % (2 ** 32)
        for i in range(0, len(s), chunk_size):
            yield struct.pack(packet_fmt, ident, i, len(s)) + s[i:i + chunk_size]

    return chunkify(serialize(diff(convert(animation))), chunk_size)


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
                try:
                    frames = self.queue.get(timeout=0.9)
                except Empty:
                    client.loop(timeout=0.1)
                else:
                    try:
                        messages = [
                            client.publish(self.topic, chunk, qos=1)
                            for chunk in render(frames, self.fps)
                        ]
                        # XXX Raise exception on timeout?
                        while not all(m.is_published for m in messages):
                            client.loop(timeout=1)
                    finally:
                        self.queue.task_done()
        except Exception as e:
            self.exception = e
