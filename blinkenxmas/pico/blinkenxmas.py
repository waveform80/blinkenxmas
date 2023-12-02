import gc
import time
import machine
import asyncio

from animation import Animation
from leds import LEDStrips
from mqtt_as import MQTTClient
from config import config


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
                        leds[index] = color
                    await asyncio.sleep_ms(
                        max(0, frame_time - (time.ticks_ms() - start)))
        finally:
            anim.close()
            leds.clear()


async def receive():
    anim_task = None
    anim = None
    try:
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
    finally:
        if anim_task is not None:
            anim_task.cancel()
        if anim is not None:
            anim.close()


async def blinkie(count):
    led = machine.Pin(config.get('status-led', 'LED'), machine.Pin.OUT)
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


async def connection():
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


async def manager():
    tasks = []
    def error(loop, context):
        print(repr(context))
        for task in tasks:
            task.cancel()

    asyncio.get_event_loop().set_exception_handler(error)
    tasks.append(asyncio.create_task(connection()))
    tasks.append(asyncio.create_task(receive()))
    await tasks[-1]


# We use queue_len 1 to discard duplicate messages which can be sent at QoS 1
config['queue_len'] = 1
config['clean'] = True
config['keepalive'] = 120

# The LEDs must be initialized once at the top-level
leds = LEDStrips(config['leds'])
client = MQTTClient(config)

def main():
    Animation.setup()
    try:
        asyncio.run(manager())
    finally:
        client.close()
        if config.get('error', 'reset') == 'reset':
            machine.soft_reset()
        else:
            asyncio.new_event_loop()
            asyncio.run(blinkie(5))
