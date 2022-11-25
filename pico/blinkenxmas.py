import gc
import time
import struct
import uasyncio as asyncio
from machine import Pin
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


_anim_fmt  = const('!BH')
_frame_fmt = const('!B')
_led_fmt   = const('!BH')

_anim_size  = struct.calcsize(_anim_fmt)
_frame_size = struct.calcsize(_frame_fmt)
_led_size   = struct.calcsize(_led_fmt)

async def animate(data):
    fps, frames = struct.unpack(_anim_fmt, data[:_anim_size])
    print(f'New animation contains {frames} frames at {fps}fps')
    if not frames:
        leds.clear()
    else:
        try:
            if frames > 1:
                frame_time = 1000 // fps
            else:
                # If the animation is static, use an absurdly long frame time
                # so we're not doing too much work...
                frame_time = 5000
            while True:
                off = _anim_size
                for frame in range(frames):
                    start = time.ticks_ms()
                    count, = struct.unpack(
                        _frame_fmt, data[off:off + _frame_size])
                    off += _frame_size
                    for led in range(count):
                        index, color = struct.unpack(
                            _led_fmt, data[off:off + _led_size])
                        leds.set_rgb(index, *rgb565_to_rgb(color))
                        off += _led_size
                    await asyncio.sleep_ms(
                        max(0, frame_time - (time.ticks_ms() - start)))
        finally:
            leds.clear()


async def receive(client):
    anim_task = None
    async for topic, msg, retained in client.queue:
        gc.collect()
        print(gc.mem_free(), 'bytes free RAM')
        topic = topic.decode('utf-8')
        print(f'Received new animation for {topic}')
        if anim_task is not None:
            anim_task.cancel()
        anim_task = asyncio.create_task(animate(msg))
    if anim_task is not None:
        anim_task.cancel()


async def blinkie(delay):
    led = Pin('LED', Pin.OUT)
    try:
        while True:
            led.value(1)
            await asyncio.sleep_ms(delay)
            led.value(0)
            await asyncio.sleep_ms(delay)
    except asyncio.CancelledError:
        led.value(1)


async def connection(client):
    print(f'Awaiting connection to SSID {config["ssid"]}')
    task = asyncio.create_task(blinkie(250))
    await client.connect()
    while True:
        print(f'Awaiting connection to broker {config["server"]}')
        task.cancel()
        task = asyncio.create_task(blinkie(500))
        await client.up.wait()
        client.up.clear()
        print(f'Connection established; subscribing to {config["topic"]}')
        await client.subscribe(config['topic'], 1)
        task.cancel()
        await client.down.wait()
        client.down.clear()
        print('Connection failed')


async def main(client):
    asyncio.create_task(connection(client))
    asyncio.create_task(receive(client))
    while True:
        await asyncio.sleep(5)


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
    asyncio.new_event_loop()
