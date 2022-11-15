import time
import json
import struct
import uasyncio as asyncio
from machine import Pin

from plasma import plasma_stick, WS2812, COLOR_ORDER_RGB
from mqtt_as import MQTTClient
from config import config


async def animate(frames):
    def set_frame(frame):
        for led in frame:
            leds.set_rgb(*led)

    if not frames:
        leds.clear()
    else:
        try:
            if len(frames) > 1:
                frame_time = 1000 // config.get('fps', 60)
            else:
                # If the animation is static, use an absurdly long frame time
                # so we're not doing too much work...
                frame_time = 5000
            while True:
                for frame in frames:
                    start = time.ticks_ms()
                    set_frame(frame)
                    await asyncio.sleep_ms(frame_time - (time.ticks_ms() - start))
        except asyncio.CancelledError:
            pass
        finally:
            leds.clear()


async def receive(client):
    anim_task = None
    async for topic, msg, retained in client.queue:
        topic = topic.decode('utf-8')
        print(f'Received new animation for {topic}')
        try:
            frames = json.loads(msg.decode('utf-8'))
        except ValueError:
            print('Failed to decode animation; ignoring')
            continue
        else:
            print(f'New animation contains {len(frames)} frames')
        if anim_task is not None:
            anim_task.cancel()
        anim_task = asyncio.create_task(animate(frames))
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
