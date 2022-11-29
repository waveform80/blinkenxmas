import os
import math
import struct
from micropython import const


_chunk_size = const(1024)
_packet_fmt = const('!LLL')
_anim_fmt   = const('!BH')
_frame_fmt  = const('!B')
_led_fmt    = const('!BH')

_packet_size = struct.calcsize(_packet_fmt)
_anim_size   = struct.calcsize(_anim_fmt)
_frame_size  = struct.calcsize(_frame_fmt)
_led_size    = struct.calcsize(_led_fmt)


class Animation:
    def __init__(self, initial_msg):
        self.ident, offset, size = struct.unpack(_packet_fmt, initial_msg)
        print(f'Receiving new animation {self.ident} (size {size//1024}KB)')
        self._fps = None
        self._len = None
        self._buf = open(f'{self.ident}.dat', 'w+b')
        self._buf.seek(size - 1)
        self._buf.write(b'\x00')
        self._chunks = 2 ** math.ceil(size / _chunk_size) - 1
        self.write(initial_msg)

    def close(self):
        self._buf.close()
        os.remove(f'{self.ident}.dat')

    @classmethod
    def cleanup(cls):
        # TODO Make a specific directory for animation caching (so we can just
        # burn everything in there)
        to_remove = [
            filename
            for filename in os.listdir()
            if filename.endswith('.dat')
            and filename[:-len('.dat')].isdigit()
        ]
        print(f'Removing {len(to_remove)} left over animation files')
        for filename in to_remove:
            os.remove(filename)

    def write(self, msg):
        ident, offset, size = struct.unpack(_packet_fmt, msg)
        if ident != self.ident:
            raise ValueError('new ident')
        chunk = 2 ** (offset // _chunk_size)
        if self._chunks & chunk:
            self._buf.seek(offset)
            self._buf.write(msg[_packet_size:])
            self._chunks &= ~chunk
            if chunk == 1:
                self._fps, self._len = struct.unpack(
                    _anim_fmt, msg[_packet_size:_packet_size + _anim_size])
        # TODO If we're complete, re-open in read-only mode?

    @property
    def complete(self):
        return not self._chunks

    @property
    def fps(self):
        return self._fps

    def __len__(self):
        return self._len

    def __iter__(self):
        self._buf.seek(_anim_size)
        frame_buf = bytearray(_frame_size)
        led_buf = bytearray(_led_size)
        for frame in range(len(self)):
            assert self._buf.readinto(frame_buf) == len(frame_buf)
            count, = struct.unpack(_frame_fmt, frame_buf)
            frame = [None] * count
            for led in range(count):
                assert self._buf.readinto(led_buf) == len(led_buf)
                frame[led] = struct.unpack(_led_fmt, led_buf)
            yield frame
