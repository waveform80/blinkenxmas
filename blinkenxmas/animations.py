from colorzero import Color, Lightness

from .httpd import animation, Param


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
    ] + [[Color('#000') for led in range(led_count)]]
