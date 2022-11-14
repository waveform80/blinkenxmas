import time
import struct
import uasyncio as asyncio

from plasma import plasma_stick, COLOR_ORDER_RGB
from mqtt_as import MQTTClient
from config import config


async def animate(frames):
    leds = plasma.WS2812(
        config.get('led_count', 50), 0, 0, plasma_stick.DAT,
        color_order=COLOR_ORDER_RGB)
    leds.start()
    try:
        frame_time = 1000 // config.get('fps', 60)
        while True:
            for frame in frames:
                frame_start = time.ticks_ms()
                for led in frame:
                    leds.set_rgb(*led)
                frame_end = time.ticks_ms()
                await asyncio.sleep_ms(frame_time - (frame_end - frame_start))
    except asyncio.CancelledError:
        pass
    finally:
        leds.clear()


async def receive(client):
    anim_task = None
    async for topic, msg, retained in client.queue:
        if anim_task is not None:
            anim_task.cancel()
        # XXX Decode?
        anim_task = asyncio.create_task(animate(msg))
    if anim_task is not None:
        anim_task.cancel()


async def blinkie():
    led = Pin('LED', Pin.OUT)
    try:
        while True:
            led.value(1)
            await asyncio.sleep_ms(500)
            led.value(0)
            await asyncio.sleep_ms(500)
    except asyncio.CancelledError:
        led.value(1)


async def connection(client):
    while True:
        print(f'Awaiting connection to {config["ssid"]}')
        task = asyncio.create_task(blinkie())
        await client.up.wait()
        client.up.clear()
        print(f'Connection established; subscribing to config["topic"]')
        client.subscribe(config['topic'], 1)
        task.cancel()
        await client.down.wait()
        client.down.clear()
        print(f'Connection failed')


async def main(client):
    asyncio.create_task(connection(client))
    asyncio.create_task(receive(client))
    while True:
        print(f'Main loop')
        await asyncio.sleep(5)


# We use queue_len 1 to discard duplicate messages which can be sent at QoS 1
config['queue_len'] = 1
config['clean'] = True
config['keepalive'] = 120

client = MQTTClient(config)
try:
    asyncio.run(main(client))
finally:
    client.close()
    asyncio.new_event_loop()
