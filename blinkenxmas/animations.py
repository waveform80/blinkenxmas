import random
from itertools import tee
from collections import deque

import numpy as np
from colorzero import Color, Lightness

from .httpd import animation, Param


def pairwise(it):
    """
    Given an iterable *it*, yields successive overlapping pairs. For example:
    pairwise('ABCDEF') --> AB BC CD DE EF
    """
    a, b = tee(it)
    next(b, None)
    return zip(a, b)


def wrap_window(it, n):
    """
    Given an iterable *it*, yields a sliding window of size *n* over that
    sequence. The final yields will wrap around to the start of the sequence.
    For example: wrap_window('ABCDEF', 3) --> ABC BCD CDE DEF EFA FAB
    """
    d = deque(maxlen=n)
    buf = []
    for i in it:
        d.append(i)
        if len(d) == n:
            yield tuple(d)
        else:
            buf.append(i)
    while buf:
        d.append(buf.pop(0))
        yield tuple(d)


def preview(anim):
    """
    On a true-color capable terminal, print a line per frame of the specified
    *anim*.
    """
    for frame in anim:
        print(''.join(f'{c:16m}#{c:0}' for c in frame))


@animation('Solid Color',
           color=Param('Color', 'color', default='#000000'))
def solid_color(led_count, fps, color):
    return [[color for led in range(led_count)]]


@animation('Solid Gradient',
           color1=Param('From', 'color', default='#000000'),
           color2=Param('To', 'color', default='#ffffff'))
def solid_gradient(led_count, fps, color1, color2):
    gradient = color1.gradient(color2, steps=led_count)
    return [[color for color in gradient]]


@animation('Sweep',
           color=Param('Color', 'color', default='#ffffff'),
           duration=Param('Duration', 'range', default=1, min=1, max=10))
def sweep(led_count, fps, color, duration):
    frame_count = int(fps * duration)
    return [
        [
            color * Lightness(
                (1 - abs(
                    ((index + 10) / (led_count + 20)) -
                    (frame / frame_count)
                )) ** 20)
            for index in range(led_count)
        ]
        for frame in range(frame_count)
    ]


@animation('Bounce',
           color=Param('Color', 'color', default='#ffffff'),
           duration=Param('Duration', 'range', default=1, min=1, max=10))
def bounce(led_count, fps, color, duration):
    frame_count = int(fps * duration / 2)
    anim = [
        [
            color * Lightness(
                (1 - abs(
                    (index / led_count) -
                    (frame / frame_count)
                )) ** 20)
            for index in range(led_count)
        ]
        for frame in range(frame_count)
    ]
    return anim + anim[::-1]


@animation('Flash',
           color1=Param('Color 1', 'color', default='#000000'),
           color2=Param('Color 2', 'color', default='#ffffff'),
           speed=Param('Speed', 'range', default=5, min=1, max=10))
def flash(led_count, fps, color1, color2, speed):
    duration = 11 - speed
    frame_count = fps * duration // 2
    return (
        [[color1 for index in range(led_count)]] * frame_count +
        [[color2 for index in range(led_count)]] * frame_count
    )


@animation('Twinkle',
           color=Param('Color', 'color', default='#ffffff'),
           lit=Param('Lit %', 'range', default=1, min=1, max=10),
           speed=Param('Speed', 'range', default=1, min=1, max=10))
def twinkle(led_count, fps, color, lit, speed, duration=10):
    frame_count = int(fps * duration)
    lit = led_count * lit // 50
    black = Color('black')

    # We start transposed with a list of lists where the outer list is the
    # LEDs, and the inner the list of colors for that LED (the frame)
    leds = [
        [
            black
            for frame in range(frame_count)
        ]
        for led in range(led_count)
    ]

    # Set the frames that should be "on" to the appropriate lit proportion
    for led in leds:
        for frame in random.sample(range(frame_count), k=lit):
            led[frame] = color * Lightness(0.5 + random.random() / 2)

    # Calculate a weighted average color for each led in turn
    window = fps * (11 - speed) // 10
    weights = tuple(i / (window // 2) for i in range(1, (window // 2)))
    weights = weights + (1,) + weights[::-1]
    leds = [
        [
            # Summation of the weighted neighbours
            sum((
                # Weighting each component of the neighbouring LEDs
                Color(*(component * weight for component in c))
                # The sequence of neighbouring LEDs zipped with their
                # respective weights
                for c, weight in zip(neighbours, weights)
            ), black)
            for neighbours in wrap_window(led, len(weights))
        ]
        for led in leds
    ]

    # Transpose to list of lists where outer list is the frames, and the inner
    # list is the frame of LEDs
    return zip(*leds)


@animation('Rainbow',
           count=Param('# Rainbows', 'range', default=1, min=1, max=5),
           saturation=Param('Saturation', 'range', default=10, min=1, max=10),
           value=Param('Brightness', 'range', default=10, min=1, max=10))
def rainbow(led_count, fps, count, saturation, value):
    return [[
        Color(h=led * count / led_count, s=(saturation / 10), v=(value / 10))
        for led in range(led_count)
    ]]


@animation('Rolling Rainbow',
           count=Param('# Rainbows', 'range', default=1, min=1, max=5),
           saturation=Param('Saturation', 'range', default=10, min=1, max=10),
           value=Param('Brightness', 'range', default=10, min=1, max=10),
           duration=Param('Duration', 'range', default=1, min=1, max=10))
def rolling_rainbow(led_count, fps, count, saturation, value, duration):
    frame_count = int(fps * duration)
    return [
        [
            Color(
                h=((led * count / led_count) + (frame / frame_count)) % 1.0,
                s=(saturation / 10), v=(value / 10))
            for led in range(led_count)
        ]
        for frame in range(frame_count)
    ]
