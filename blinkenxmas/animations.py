import random
from itertools import tee
from collections import deque

import numpy as np
from colorzero import Color, Lightness, Saturation

from .httpd import animation, Param, ParamLEDCount, ParamLEDPositions, ParamFPS


def scale(value, in_range, out_range):
    """
    Scales *value* from *in_range* to *out_range*. The ranges are expected to
    be (min, max) tuples. Provided *value* is within *in_range*, the result
    will be within *out_range*, scaled linearly.
    """
    ratio = (out_range[1] - out_range[0]) / (in_range[1] - in_range[0])
    return ((value - in_range[0]) * ratio) + out_range[0]


def range_of(it):
    """
    Returns a (minimum, maximum) tuple for the range of values in *it*,
    utilizing a single pass. This can be slightly more efficient that calling
    :func:`min` and :func:`max` separately on *it* depending on its size.
    However, it may also be more efficient to :func:`sort` *it* and simply
    access the first and last element, depending on circumstance.
    """
    min_ = max_ = None
    for value in it:
        if min_ is None:
            min_ = max_ = value
        elif value < min_:
            min_ = value
        elif value > max_:
            max_ = value
    return (min_, max_)


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
        print(''.join(
            f'{c:16m}#{c:0}' if isinstance(c, Color) else
            '{cs:16m}#{cs:0}'.format(cs=Color(c))
            for c in frame
        ))


@animation('Solid Color',
           led_count=ParamLEDCount(),
           color=Param('Color', 'color', default='#000000'))
def solid_color(led_count, color):
    """
    This "animation" simply shows the selected color on all LEDs of the tree.
    Use black to create a setting that turns all LEDs off.
    """
    return [[color for led in range(led_count)]]


@animation('Simple Gradient',
           led_count=ParamLEDCount(),
           color1=Param('From', 'color', default='#000000'),
           color2=Param('To', 'color', default='#ffffff'))
def simple_gradient(led_count, color1, color2):
    """
    This displays a gradient that fades from one color to another along all
    LEDs of the tree. Please note this does *not* use the scanned coordinates
    of the LEDs (see "Gradient" instead), so the effect will only appear to be
    a gradient over the height of the tree if the LEDs are laid out in numeric
    order.
    """
    gradient = color1.gradient(color2, steps=led_count)
    return [[color for color in gradient]]


@animation('Gradient',
           led_count=ParamLEDCount(),
           positions=ParamLEDPositions(),
           bottom=Param('Bottom', 'color', default='#000000'),
           top=Param('Top', 'color', default='#ffffff'))
def gradient(led_count, positions, bottom, top):
    """
    This displays a gradient that fades from one color at the bottom of the
    tree, to another color at the top. Please note this requires that you have
    run the calibration step to determine LED positions accurately.
    """
    black = Color('black')
    y_range = range_of(pos.y for pos in positions.values())
    gradient = list(top.gradient(bottom, steps=20))
    return [[
        gradient[int(positions[led].y * 19)]
        if led in positions else black
        for led in range(led_count)
    ]]


@animation('Sweep',
           led_count=ParamLEDCount(),
           fps=ParamFPS(),
           color=Param('Color', 'color', default='#ffffff'),
           duration=Param('Duration', 'range', default=1, min=1, max=10))
def sweep(led_count, fps, color, duration):
    """
    This animation sweeps the specified color along the LEDs in numeric order.
    The Duration determines how many seconds it takes for the color to sweep
    from one end to the other.

    Please note this does *not* use the scanned coordinates of the LEDs, so the
    sweep will only appear to move up the tree if the LEDs are laid out in
    numeric order.
    """
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
           led_count=ParamLEDCount(),
           fps=ParamFPS(),
           color=Param('Color', 'color', default='#ffffff'),
           duration=Param('Duration', 'range', default=1, min=1, max=10))
def bounce(led_count, fps, color, duration):
    """
    This animation is similar to "Sweep", moving the specified color along the
    LEDs in numeric order, but then moves the color back making the animation
    symmetric. The Duration determines how many seconds it takes for the color
    to sweep from one end to the other.

    Please note this does *not* use the scanned coordinates of the LEDs, so the
    sweep will only appear to move up the tree if the LEDs are laid out in
    numeric order.
    """
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
           led_count=ParamLEDCount(),
           fps=ParamFPS(),
           color1=Param('Color 1', 'color', default='#000000'),
           color2=Param('Color 2', 'color', default='#ffffff'),
           speed=Param('Speed', 'range', default=5, min=1, max=10))
def flash(led_count, fps, color1, color2, speed):
    """
    This animation trivially flashes all LEDs on the tree alternately between
    color 1 and 2 at the specified speed.
    """
    duration = 11 - speed
    frame_count = fps * duration // 2
    return (
        [[color1 for index in range(led_count)]] * frame_count +
        [[color2 for index in range(led_count)]] * frame_count
    )


@animation('Twinkle',
           led_count=ParamLEDCount(),
           fps=ParamFPS(),
           color=Param('Color', 'color', default='#ffffff'),
           lit=Param('Lit %', 'range', default=1, min=1, max=10),
           speed=Param('Speed', 'range', default=1, min=1, max=10))
def twinkle(led_count, fps, color, lit, speed, duration=10):
    """
    Generates a cyclic animation that randomly fades LEDs on the tree from
    black up to the specified color and back to black. The "Lit %" determines
    the number of LEDs that should be fully lit during any given frame. The
    "Speed" indicates how quickly the fade should occur.
    """
    frame_count = int(fps * duration)
    lit = led_count * lit // 50
    fade_frames = fps * (11 - speed) // 20
    fade_frames = (fade_frames * 2) + 1

    frames = np.zeros((frame_count + fade_frames, led_count), dtype=float)
    fade = np.linspace(0, 1, (fade_frames // 2) + 2, dtype=float)[1:-1]
    fade = np.concatenate((fade, [1], fade[::-1]))
    for led in range(led_count):
        for frame in random.sample(range(frame_count), k=lit):
            frames[frame:frame + fade_frames, led] += fade / (1 + random.random())
    frames[:fade_frames, :] += frames[frame_count:frame_count + fade_frames, :]
    frames = frames[:frame_count, :].clip(0, 1)

    return [[color * Lightness(led) for led in frame] for frame in frames]


@animation('Simple Rainbow',
           led_count=ParamLEDCount(),
           count=Param('# Rainbows', 'range', default=1, min=1, max=5),
           saturation=Param('Saturation', 'range', default=10, min=1, max=10),
           value=Param('Brightness', 'range', default=10, min=1, max=10))
def simple_rainbow(led_count, count, saturation, value):
    """
    This displays a rainbow along all LEDs of the tree. If you have multiple
    equal length strips of LEDs on your tree, it is worth setting "# Rainbows"
    to the number of strips to obtain a continuous rainbow up the height of the
    tree.

    Please note this does *not* use the scanned coordinates of the LEDs (see
    "Rainbow" instead), so the effect will only appear to be a rainbow over the
    height of the tree if the LEDs are laid out in numeric order, and/or the
    "# Rainbows" parameter equals the number of (equal length) strips running
    up the tree.
    """
    return [[
        Color(h=led * count / led_count, s=(saturation / 10), v=(value / 10))
        for led in range(led_count)
    ]]


@animation('Rainbow',
           led_count=ParamLEDCount(),
           positions=ParamLEDPositions(),
           count=Param('# Rainbows', 'range', default=1, min=1, max=5),
           saturation=Param('Saturation', 'range', default=10, min=1, max=10),
           value=Param('Brightness', 'range', default=10, min=1, max=10))
def rainbow(led_count, positions, count, saturation, value):
    """
    This displays the specified number of rainbows from the top of the tree, to
    the bottom. The saturation and brightness sliders determine the strength
    of colors in the rainbow.

    Please note this requires that you have run the calibration step to
    determine LED positions accurately.
    """
    black = Color('black')
    y_range = range_of(pos.y for pos in positions.values())
    return [[
        Color(h=scale(positions[led].y, y_range, (0, count)) % 1,
              s=(saturation / 10),
              v=(value / 10))
        if led in positions else black
        for led in range(led_count)
    ]]


@animation('Rolling Simple Rainbow',
           led_count=ParamLEDCount(),
           fps=ParamFPS(),
           count=Param('# Rainbows', 'range', default=1, min=1, max=5),
           saturation=Param('Saturation', 'range', default=10, min=1, max=10),
           value=Param('Brightness', 'range', default=10, min=1, max=10),
           duration=Param('Duration', 'range', default=1, min=1, max=10))
def rolling_simple_rainbow(led_count, fps, count, saturation, value, duration):
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


@animation('Spinning Rainbow',
           led_count=ParamLEDCount(),
           fps=ParamFPS(),
           positions=ParamLEDPositions(),
           saturation=Param('Saturation', 'range', default=10, min=1, max=10),
           value=Param('Brightness', 'range', default=10, min=1, max=10),
           duration=Param('Duration', 'range', default=1, min=1, max=10))
def spinning_rainbow(led_count, fps, positions, saturation, value, duration):
    """
    Displays a rainbow around the trunk of the tree which spins for the
    specified duration. The saturation and brightness sliders determine the
    strength of colors in the rainbow.

    Please note this requires that you have run the calibration step to
    determine LED positions accurately.
    """
    frame_count = int(fps * duration)
    black = Color('black')
    return [
        [
            Color(h=((positions[led].a / 360.0) + (frame / frame_count)) % 1,
                  s=(saturation / 10),
                  v=(value / 10))
            if led in positions else black
            for led in range(led_count)
        ]
        for frame in range(frame_count)
    ]


@animation('Pride',
           led_count=ParamLEDCount(),
           positions=ParamLEDPositions(),
           flag=Param('Flag', 'select', default='gay', choices={
               'gay':     'Gay',
               'bi':      'Bisexual',
               'lesbian': 'Lesbian',
               'trans':   'Transgender',
               'pan':     'Pansexual',
               'ace':     'Asexual',
               'nonbin':  'Non-binary',
               'fluid':   'Gender-fluid',
               'queer':   'Gender-queer',
               'inter':   'Intersex',
           }),
           saturation=Param('Saturation', 'range', default=10, min=1, max=10),
           lightness=Param('Brightness', 'range', default=10, min=1, max=10))
def pride(led_count, positions, flag, saturation, lightness):
    """
    Display one of the Pride flags on the tree from top to bottom. The
    saturation and brightness sliders determine the strength of colors in the
    rainbow.

    Please note this requires that you have run the calibration step to
    determine LED positions accurately.
    """
    black = Color('black')
    if flag == 'inter':
        mid_y = scale(0.5, (0, 1), range_of(pos.y for pos in positions.values()))
        mid_z = scale(0.5, (0, 1), range_of(pos.z for pos in positions.values()))
        def circle(pos, min_r=0.1, max_r=0.2):
            return min_r**2 <= (pos.z - mid_z)**2 + (pos.y - mid_y)**2 <= max_r**2
        colors = (Color('#ffd800'), Color('#8d02b1'))
        return [[
            colors[circle(positions[led])]
                * Saturation(saturation / 10) * Lightness(lightness / 10)
            if led in positions else black
            for led in range(led_count)
        ]]
    else:
        colors = {
            'gay': [
                Color('#e50203'),
                Color('#ff8a01'),
                Color('#feed00'),
                Color('#008026'),
                Color('#014bfe'),
                Color('#750685'),
            ],
            'bi': [
                Color('#d60270'),
                Color('#d60270'),
                Color('#9b4f97'),
                Color('#0038a7'),
                Color('#0038a7'),
            ],
            'lesbian': [
                Color('#d62c00'),
                Color('#ff9956'),
                Color('#ffe'),
                Color('#d362a4'),
                Color('#a40162'),
            ],
            'trans': [
                Color('#5bcff9'),
                Color('#f5a8b8'),
                Color('white'),
                Color('#f5a8b8'),
                Color('#5bcff9'),
            ],
            'pan': [
                Color('#ff218c'),
                Color('#ffd800'),
                Color('#21b1fe'),
            ],
           'ace': [
               Color('black'),
               Color('#a0a0a0'),
               Color('white'),
               Color('#9a0778'),
           ],
           'nonbin': [
               Color('#fff430'),
               Color('white'),
               Color('#9d59d2'),
               Color('black'),
           ],
           'fluid': [
               Color('#fe75a1'),
               Color('white'),
               Color('#bf17d5'),
               Color('black'),
               Color('#323ebc'),
           ],
           'queer': [
               Color('#b57edc'),
               Color('white'),
               Color('#4a8123'),
           ],
        }[flag]
        y_range = range_of(pos.y for pos in positions.values())
        out_range = (0, len(colors) - 0.00001)
        return [[
            colors[int(scale(positions[led].y, y_range, out_range))]
                * Saturation(saturation / 10) * Lightness(lightness / 10)
            if led in positions else black
            for led in range(led_count)
        ]]
