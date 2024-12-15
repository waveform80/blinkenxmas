import random
import math as m
from itertools import tee
from collections import deque

import numpy as np
from colorzero import Color, Lightness, Saturation

from .httpd import animation, Param, ParamLEDCount, ParamLEDPositions, ParamFPS
from .store import Position


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
    However, it may also be more efficient to :meth:`~list.sort` *it* and
    simply access the first and last element, depending on circumstance.
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


def preview(anim):
    """
    On a true-color capable terminal, print a line per frame of the specified
    *anim*. This is primarily intended as a debugging function.
    """
    for frame in anim:
        print(''.join(
            f'{c:16m}#{c:0}' if isinstance(c, Color) else
            '{cs:16m}#{cs:0}'.format(cs=Color(c))
            for c in frame
        ))


@animation('One Color',
           led_count=ParamLEDCount(),
           color=Param('Color', 'color', default='#000000'))
def one_color(led_count, color):
    """
    This "animation" simply shows the selected color on all LEDs of the tree.
    Use black to create a setting that turns all LEDs off.
    """
    return [[color for led in range(led_count)]]


@animation('Calibration',
           led_count=ParamLEDCount(),
           positions=ParamLEDPositions(),
           found_color=Param('Found', 'color', default='#00ff00'),
           missing_color=Param('Missing', 'color', default='#ff0000'))
def calibration(led_count, positions, found_color, missing_color):
    """
    This "animation" shows which LEDs were found during calibration and which
    were not by assigning them different colors. This is primarily useful for
    debugging your setup. Your are advised to use two non-black colors so that
    you can check for unlit LEDs, which may be a result of bad connections,
    broken LEDs, or bad configuration of the strand lengths.

    Please note this animation requires that you have run the calibration step
    or all LEDs (exception bad ones) will simply appear in the "missing" color.
    """
    return [[
        found_color if led in positions else missing_color
        for led in range(led_count)
    ]]


@animation('Gradient (by index)',
           led_count=ParamLEDCount(),
           color1=Param('From', 'color', default='#000000'),
           color2=Param('To', 'color', default='#ffffff'))
def gradient_by_index(led_count, color1, color2):
    """
    This displays a gradient that fades from one color to another along all
    LEDs of the tree. Please note this does *not* use the scanned coordinates
    of the LEDs (see "Gradient" instead), so the effect will only appear to be
    a gradient over the height of the tree if the LEDs are laid out in numeric
    order.
    """
    gradient = color1.gradient(color2, steps=led_count)
    return [[color for color in gradient]]


@animation('Gradient (by position)',
           led_count=ParamLEDCount(),
           positions=ParamLEDPositions(),
           top=Param('Top', 'color', default='#ffffff'),
           bottom=Param('Bottom', 'color', default='#000000'))
def gradient_by_pos(led_count, positions, bottom, top):
    """
    This displays a gradient that fades from one color at the bottom of the
    tree, to another color at the top. Please note this requires that you have
    run the calibration step to determine LED positions accurately.
    """
    black = Color('black')
    indexes = np.linspace(*range_of(pos.y for pos in positions.values()), 50)
    gradient = list(top.gradient(bottom, steps=50))
    return [[
        gradient[indexes.searchsorted(positions[led].y)]
        if led in positions else black
        for led in range(led_count)
    ]]


@animation('Sweep (by index)',
           led_count=ParamLEDCount(),
           fps=ParamFPS(),
           color=Param('Color', 'color', default='#ffffff'),
           bounce=Param('Bounce', 'checkbox', default=False),
           speed=Param('Speed', 'range', default=5, min=1, max=10))
def sweep_by_index(led_count, fps, color, bounce, speed):
    """
    This animation sweeps the specified color along the LEDs in numeric order.
    If Bounce is checked, the color will sweep back along the LEDs to the
    start, in effect bouncing between the extremes of the strand(s). Speed
    indicates how quickly the sweep (or bounce) should occur.

    Please note this does *not* use the scanned coordinates of the LEDs, so the
    sweep will only appear to move up the tree if the LEDs are laid out in
    numeric order.
    """
    duration = 11 - speed
    if bounce:
        frame_count = int(fps * duration / 2)
    else:
        frame_count = int(fps * duration)
    anim = [
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
    if bounce:
        return anim + anim[::-1]
    else:
        return anim


@animation('Sweep (planar by position)',
           led_count=ParamLEDCount(),
           fps=ParamFPS(),
           positions=ParamLEDPositions(),
           angle=Param('Angle', 'range', default=0, min=0, max=359),
           slant=Param('Slant', 'range', default=0, min=0, max=180),
           planes=Param('Planes', 'range', default=1, min=1, max=5),
           color=Param('Color', 'color', default='#ffffff'),
           speed=Param('Speed', 'range', default=5, min=1, max=10))
def sweep_by_pos(led_count, fps, positions, angle, slant, planes, color, speed):
    """
    This animation sweeps a plane of the specified color through the tree at
    the Angle and Slant specified.

    Slant represents the angle from the vertical that the plane moves along.
    The default of 0° means vertically downwards through the tree, 90° means
    horizontally through the tree, and 180° is vertically upwards. Angle
    dictates the rotation about the trunk (and thus is only really meaningful
    when Slant is not near 0° or 180°).

    Planes determines how many planes simultaneously sweep through the tree.
    Speed determines how quickly the color sweeps from one extreme to the
    other.

    Please note this animation requires that you have run the calibration step
    to determine LED positions accurately.
    """
    duration = 11 - speed
    frame_count = int(fps * duration)
    frames = np.zeros((frame_count, led_count), dtype=float)
    one_sweep = frames.copy()
    null_pos = Position.from_cartesian(0, 2, 0) # off the top of the tree
    pos = np.asarray([
        (pos.x, pos.y, pos.z)
        for led in range(led_count)
        for pos in (positions[led] if led in positions else null_pos,)
    ], dtype=float)
    y_range = (
        pos[:, 1].min(),
        pos[:, 1].max(where=pos[:, 1] < 2, initial=0)
    )
    slant = m.radians(slant)
    angle = m.radians(angle)

    # Equation of the plane is ax + by + cz + d = 0. abc is a numpy array
    # defining coefficients a, b, and c which are static throughout the
    # animation. Coefficient d varies as the plane sweeps along the defined
    # line, hence D is the array holding the value of d for each frame. We then
    # use distance of a point to the plane, abs(ax+by+cz-d)/sqrt(a^2+b^2+c^2),
    # to determine the distance of each LED to the plane, scale it by 10 and
    # invert it to determine the brightness of that LED in the frame
    abc = np.asarray([
        m.sin(slant) * m.cos(angle),  # a
        m.cos(slant),                 # b
        m.sin(slant) * m.sin(angle),  # c
    ], dtype=float)
    sqrsum = (abc**2).sum()
    # We sweep from y_min-0.1 to y_max+0.1 so that LEDs will actually fade to
    # black; the plane sweeps "off the end" far enough that even LEDs at the
    # extremes are no longer "close enough to the plane" to be lit
    D = np.fromiter((
        t * sqrsum
        for t in np.linspace(y_range[0] - 0.1, y_range[1] + 0.1,
                             frame_count, endpoint=False)
    ), dtype=float)
    for frame, d in enumerate(D):
        one_sweep[frame, :] = (
            1 - 10 * (np.abs((abc * pos).sum(axis=1) - d) / m.sqrt(sqrsum))
        ).clip(0, 1)

    offsets = np.linspace(0, frame_count, planes, endpoint=False, dtype=int)
    for offset in offsets:
        frames[...] += np.roll(one_sweep, offset, axis=0)
    frames = frames.clip(0, 1)

    return [[color * Lightness(led) for led in frame] for frame in frames]


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
def twinkle(led_count, fps, color, lit, speed, duration=5):
    """
    Generates a cyclic animation that randomly fades LEDs on the tree from
    black up to the specified color and back to black. The Lit % indicates the
    proportion of LEDs that should be fully lit during any given frame. At high
    proportions the animation appears more as if LEDs are periodically fading
    off, rather than fading on. Speed indicates how quickly the fade should
    occur.
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


@animation('Rainbow (by index)',
           led_count=ParamLEDCount(),
           count=Param('# Rainbows', 'range', default=1, min=1, max=5),
           saturation=Param('Saturation', 'range', default=10, min=1, max=10),
           value=Param('Brightness', 'range', default=10, min=1, max=10))
def rainbow_by_index(led_count, count, saturation, value):
    """
    This displays a rainbow along all LEDs of the tree. If you have multiple
    equal length strips of LEDs on your tree, it is worth setting "# Rainbows"
    to the number of strips to obtain a continuous rainbow up the height of the
    tree.

    Please note this does *not* use the scanned coordinates of the LEDs (see
    "Rainbow (by position)" instead), so the effect will only appear to be a
    rainbow over the height of the tree if the LEDs are laid out in numeric
    order, and/or the "# Rainbows" parameter equals the number of (equal
    length) strips running up the tree.
    """
    return [[
        Color(h=led * count / led_count, s=(saturation / 10), v=(value / 10))
        for led in range(led_count)
    ]]


@animation('Rainbow (by position)',
           led_count=ParamLEDCount(),
           positions=ParamLEDPositions(),
           count=Param('# Rainbows', 'range', default=1, min=1, max=5),
           saturation=Param('Saturation', 'range', default=10, min=1, max=10),
           value=Param('Brightness', 'range', default=10, min=1, max=10))
def rainbow_by_pos(led_count, positions, count, saturation, value):
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


@animation('Scrolling Rainbow (by index)',
           led_count=ParamLEDCount(),
           fps=ParamFPS(),
           count=Param('# Rainbows', 'range', default=1, min=1, max=5),
           saturation=Param('Saturation', 'range', default=10, min=1, max=10),
           value=Param('Brightness', 'range', default=10, min=1, max=10),
           duration=Param('Duration', 'range', default=1, min=1, max=10))
def scrolling_rainbow_by_index(led_count, fps, count, saturation, value, duration):
    """
    This displays a rainbow along all LEDs of the tree that rotates through all
    hues. If you have multiple equal length strips of LEDs on your tree, it is
    worth setting "# Rainbows" to the number of strips to obtain a continuous
    rainbow up the height of the tree.

    Please note this does *not* use the scanned coordinates of the LEDs (see
    "Scrolling Rainbow (by position)" or "Spinning Rainbow" instead), so the
    effect will only appear to be a rainbow over the height of the tree if the
    LEDs are laid out in numeric order, and/or the "# Rainbows" parameter
    equals the number of (equal length) strips running up the tree.
    """
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


@animation('Pride Flags',
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
def pride_flags(led_count, positions, flag, saturation, lightness):
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
