from itertools import tee

from colorzero import Color, Lightness

from .httpd import animation, Param


def pairwise(it):
    a, b = tee(it)
    next(b, None)
    return zip(a, b)


def compress(frames):
    """
    Given a list of lists of :class:`~colorzero.Color`, return a list of
    lists of (index, r, g, b) tuples containing only those color positions
    that actually changed since the last frame.
    """
    first = True
    for last, this in pairwise(frames):
        if first:
            first = False
            yield [
                (index,) + color.rgb_bytes
                for index, color in enumerate(last)
                if any(color)
            ]
        yield [
            (index,) + color.rgb_bytes
            for index, color in enumerate(this)
            if last[index] != color
        ]


@animation('Solid Color',
           color=Param('Color', 'color', default='#000000'))
def solid_color(led_count, fps, color):
    return [[(led,) + color.rgb_bytes for led in range(led_count)]]


@animation('Solid Gradient',
           color1=Param('From', 'color', default='#000000'),
           color2=Param('To', 'color', default='#ffffff'))
def solid_gradient(led_count, fps, color1, color2):
    gradient = color1.gradient(color2, steps=led_count)
    return [[
        (led,) + c.rgb_bytes for led, c in zip(range(led_count), gradient)
    ]]


@animation('Sweep',
           color=Param('Color', 'color', default='#ffffff'),
           duration=Param('Duration', 'range', default=1, min=1, max=10))
def sweep(led_count, fps, color, duration):
    frame_count = int(fps * duration)
    return list(compress(
        [
            color * Lightness(1 - ((index / led_count) - (frame / frame_count)) ** 2)
            for index in range(led_count)
        ]
        for frame in range(frame_count)
    ))
