from colorzero import Color, Lightness

from .httpd import animation, Param


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
                    ((index + 10) / (led_count + 20)) -
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
           duration=Param('Duration', 'range', default=1, min=1, max=10))
def flash(led_count, fps, color1, color2, duration):
    frame_count = int(fps * duration / 2)
    return (
        [[color1 for index in range(led_count)]] * frame_count +
        [[color2 for index in range(led_count)]] * frame_count
    )
