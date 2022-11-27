import gc
import os
import time
import math
import struct
import machine
import uasyncio as asyncio
from micropython import const

from plasma import plasma_stick, WS2812, COLOR_ORDER_RGB
from mqtt_as import MQTTClient
from config import config


def rgb565_to_rgb(c):
    r = (c & 0xf800) >> 8
    g = (c & 0x07e0) >> 3
    b = (c & 0x001f) << 3
    r |= r >> 5
    g |= g >> 6
    b |= b >> 5
    return r, g, b


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


async def animate(anim):
    print(f'New animation contains {len(anim)} frames at {anim.fps}fps')
    if not len(anim):
        leds.clear()
    else:
        try:
            if len(anim) > 1:
                frame_time = 1000 // anim.fps
            else:
                # If the animation is static, use an absurdly long frame time
                # so we're not doing too much work...
                frame_time = 5000
            while True:
                for frame in anim:
                    start = time.ticks_ms()
                    for index, color in frame:
                        leds.set_rgb(index, *rgb565_to_rgb(color))
                    await asyncio.sleep_ms(
                        max(0, frame_time - (time.ticks_ms() - start)))
        finally:
            leds.clear()
            anim.close()


async def receive(client):
    anim_task = None
    anim = None
    async for topic, msg, retained in client.queue:
        topic = topic.decode('utf-8')
        if anim is None:
            anim = Animation(msg)
        else:
            try:
                anim.write(msg)
            except ValueError:
                print(f'Discarding incomplete animation {anim.ident}')
                anim.close()
                anim = Animation(msg)
        if anim.complete:
            if anim_task is not None:
                anim_task.cancel()
            print(gc.mem_free(), 'bytes free RAM')
            anim_task = asyncio.create_task(animate(anim))
            anim = None
    if anim_task is not None:
        anim_task.cancel()
    if anim is not None:
        anim.close()


async def blinkie(count):
    led = machine.Pin('LED', machine.Pin.OUT)
    try:
        while True:
            for i in range(count):
                led.value(1)
                await asyncio.sleep_ms(200)
                led.value(0)
                await asyncio.sleep_ms(200)
            await asyncio.sleep_ms(1000)
    except asyncio.CancelledError:
        led.value(1)


async def connection(client):
    print(f'Awaiting connection to SSID {config["ssid"]}')
    task = asyncio.create_task(blinkie(2))
    await client.connect()
    while True:
        print(f'Awaiting connection to broker {config["server"]}')
        task.cancel()
        task = asyncio.create_task(blinkie(3))
        await client.up.wait()
        client.up.clear()
        print(f'Connection established; subscribing to {config["topic"]}')
        await client.subscribe(config['topic'], 1)
        task.cancel()
        await client.down.wait()
        client.down.clear()
        print('Connection failed')


async def main(client):
    tasks = []
    def error(loop, context):
        print(repr(context))
        for task in tasks:
            task.cancel()

    asyncio.get_event_loop().set_exception_handler(error)
    tasks.append(asyncio.create_task(connection(client)))
    tasks.append(asyncio.create_task(receive(client)))
    await tasks[-1]


# We use queue_len 1 to discard duplicate messages which can be sent at QoS 1
config['queue_len'] = 1
config['clean'] = True
config['keepalive'] = 120

# The LEDs must be initialized once at the top-level
leds = WS2812(
    config.get('led_count', 50), 0, 0, plasma_stick.DAT,
    color_order=COLOR_ORDER_RGB)
leds.start()

client = MQTTClient(config)
try:
    asyncio.run(main(client))
finally:
    client.close()
    if config.get('error', 'reset') == 'reset':
        machine.soft_reset()
    else:
        asyncio.new_event_loop()
        asyncio.run(blinkie(5))
