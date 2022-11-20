from colorzero import Color

from .httpd import animation, Param

@animation('Solid Color',
           color=Param('Color', 'color', default='#000000'))
def solid_color(led_count, fps, color):
    c = Color.from_string(color)
    return [[(led,) + c.rgb_bytes for led in range(led_count)]]


@animation('Solid Gradient',
           color1=Param('From', 'color', default='#000000'),
           color2=Param('To', 'color', default='#ffffff'))
def solid_gradient(led_count, fps, color1, color2):
    gradient = Color.from_string(color1).gradient(
        Color.from_string(color2), steps=led_count)
    return [[
        (led,) + c.rgb_bytes for led, c in zip(range(led_count), gradient)
    ]]
