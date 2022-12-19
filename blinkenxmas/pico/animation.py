import os
import math
import errno
import struct
from micropython import const


anim_path = 'animations'

chunk_size = const(1024)
packet_fmt = const('!LLL')
anim_fmt   = const('!BH')
frame_fmt  = const('!B')
led_fmt    = const('!BH')

packet_size = struct.calcsize(packet_fmt)
anim_size   = struct.calcsize(anim_fmt)
frame_size  = struct.calcsize(frame_fmt)
led_size    = struct.calcsize(led_fmt)


class Animation:
    def __init__(self, initial_msg):
        self.ident, offset, size = struct.unpack(packet_fmt, initial_msg)
        print(f'Receiving new animation {self.ident} (size {size//1024}KB)')
        self._fps = None
        self._len = None
        self._buf = open(f'{anim_path}/{self.ident}.dat', 'wb')
        self._buf.seek(size - 1)
        self._buf.write(b'\x00')
        self._chunks = 2 ** math.ceil(size / chunk_size) - 1
        self.write(initial_msg)

    def close(self):
        self._buf.close()
        os.remove(f'{anim_path}/{self.ident}.dat')

    @classmethod
    def setup(cls):
        try:
            os.mkdir(anim_path)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise
        print(f'Removing {len(os.listdir(anim_path))} cached animations')
        for filename in os.listdir(anim_path):
            os.remove(f'{anim_path}/{filename}')

    def write(self, buf):
        msg = memoryview(buf)
        ident, offset, size = struct.unpack(packet_fmt, msg)
        if ident != self.ident:
            raise ValueError('new ident')
        chunk = 2 ** (offset // chunk_size)
        if self._chunks & chunk:
            self._buf.seek(offset)
            self._buf.write(msg[packet_size:])
            self._chunks &= ~chunk
            if chunk == 1:
                self._fps, self._len = struct.unpack(
                    anim_fmt, msg[packet_size:packet_size + anim_size])
        self._buf.close()
        self._buf = open(f'{anim_path}/{self.ident}.dat', 'rb')

    @property
    def complete(self):
        return not self._chunks

    @property
    def fps(self):
        return self._fps

    def __len__(self):
        return self._len

    def __iter__(self):
        self._buf.seek(anim_size)
        frame_buf = bytearray(frame_size)
        led_buf = bytearray(led_size)
        for frame in range(len(self)):
            assert self._buf.readinto(frame_buf) == len(frame_buf)
            count, = struct.unpack(frame_fmt, frame_buf)
            frame = [None] * count
            for led in range(count):
                assert self._buf.readinto(led_buf) == len(led_buf)
                frame[led] = struct.unpack(led_fmt, led_buf)
            yield frame
