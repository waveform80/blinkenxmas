import os
import math
import errno
import struct
import deflate
from micropython import const


anim_path = 'animations'

chunk_size = const(4096)
packet_fmt = const('!LLL')
anim_fmt   = const('!BH')
frame_fmt  = const('!B')
led_fmt    = const('!BH')
wbits      = const(10)  # Use a 1024 bytes window for zlib

packet_size = struct.calcsize(packet_fmt)
anim_size   = struct.calcsize(anim_fmt)
frame_size  = struct.calcsize(frame_fmt)
led_size    = struct.calcsize(led_fmt)


class Animation:
    def __init__(self, buf):
        initial_msg = memoryview(buf)
        self.ident, offset, size = struct.unpack_from(packet_fmt, initial_msg)
        print(f'Receiving new animation {self.ident} (size {size//1024}KB)')
        self._fps = None
        self._len = None
        # Pre-allocate the file in which we store the animation
        self._file = open(f'{anim_path}/{self.ident}.z', 'wb')
        self._file.seek(size - 1)
        self._file.write(b'\x00')
        # Chunks is a bit-field where each bit indicates a chunk yet to be
        # received. The animation is complete when chunks == 0
        self._chunks = 2 ** math.ceil(size / chunk_size) - 1
        self.write(initial_msg)

    def close(self):
        self._file.close()
        try:
            os.remove(f'{anim_path}/{self.ident}.z')
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise
        try:
            os.remove(f'{anim_path}/{self.ident}.dat')
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise

    @classmethod
    def setup(cls):
        try:
            os.mkdir(anim_path)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise
        print(f'Removing {len(os.listdir(anim_path))} cached files')
        for filename in os.listdir(anim_path):
            os.remove(f'{anim_path}/{filename}')

    def write(self, buf):
        msg = memoryview(buf)
        ident, offset, size = struct.unpack_from(packet_fmt, msg)
        if ident != self.ident:
            raise ValueError('new ident')
        chunk = 2 ** (offset // chunk_size)
        if self._chunks & chunk:
            self._file.seek(offset)
            self._file.write(msg[packet_size:])
            self._chunks &= ~chunk
        if not self._chunks:
            self._file.close()
            self.unpack()

    def unpack(self):
        arc_name = f'{anim_path}/{self.ident}.z'
        anim_name = f'{anim_path}/{self.ident}.dat'
        arc = deflate.DeflateIO(open(arc_name, 'rb'), deflate.AUTO, 0, True)
        self._file = open(anim_name, 'wb')
        buf = bytearray(1024)
        mem = memoryview(buf)
        while True:
            if not arc.readinto(mem):
                break
            self._file.write(mem)
        arc.close()
        os.remove(arc_name)
        self._file.close()
        self._file = open(anim_name, 'rb')
        self._fps, self._len = struct.unpack(anim_fmt, self._file.read(anim_size))

    @property
    def complete(self):
        return not self._chunks

    @property
    def fps(self):
        return self._fps

    def __len__(self):
        return self._len

    def __iter__(self):
        self._file.seek(anim_size)
        frame_buf = bytearray(frame_size)
        led_buf = bytearray(led_size)
        for frame in range(len(self)):
            assert self._file.readinto(frame_buf) == len(frame_buf)
            count, = struct.unpack(frame_fmt, frame_buf)
            leds = [None] * count
            for led in range(count):
                assert self._file.readinto(led_buf) == len(led_buf)
                leds[led] = struct.unpack(led_fmt, led_buf)
            yield leds
