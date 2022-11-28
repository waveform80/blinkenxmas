import plasma


def rgb_to_rgb565(r, g, b):
    return (
        ((r & 0xF8) << 8) |
        ((g & 0xFC) << 3) |
        ((b & 0xF8) >> 3)
    )


def rgb565_to_rgb(c):
    r = (c & 0xF800) >> 8
    g = (c & 0x07E0) >> 3
    b = (c & 0x001F) << 3
    # Fill out the bottom bits from the top bits
    r |= r >> 5
    g |= g >> 6
    b |= b >> 5
    return r, g, b


class LEDStrips:
    def __init__(self, led_config):
        order_map = {
            'RGB': plasma.COLOR_ORDER_RGB,
            'RBG': plasma.COLOR_ORDER_RBG,
            'GRB': plasma.COLOR_ORDER_GRB,
            'GBR': plasma.COLOR_ORDER_GBR,
            'BGR': plasma.COLOR_ORDER_BGR,
            'BRG': plasma.COLOR_ORDER_BRG,
        }
        pios = [(pio, sm) for pio in range(2) for sm in range(4)]
        self._strips = [
            (
                plasma.WS2812(
                    led_count, pio, sm, *pins,
                    color_order=order_map[color_order.upper()])
                if led_type == 'WS2812' else
                plasma.APA102(
                    led_count, pio, sm, *pins,
                    color_order=order_map[color_order.upper()])
                if led_type == 'APA102' else
                None,
                led_count,
                rev_index,
            )
            for (led_type, led_count, rev_index, color_order, *pins), (pio, sm)
            in zip(led_config, pios)
        ]
        for (strip, _, _), (led_type, *_) in zip(self._strips, led_config):
            if strip is None:
                raise ValueError(f'invalid LED strip type: {led_type}')
            strip.start()

    def __len__(self):
        return sum(count for _, count, _ in self._strips)

    def _find_strip(self, index):
        for strip, count, rev in self._strips:
            if count > index:
                if rev:
                    index = count - index
                return strip, index
            else:
                index -= count

    def __getitem__(self, index):
        strip, index = self._find_strip(index)
        return rgb_to_rgb565(*strip.get(index))

    def __setitem__(self, index, color):
        strip, index = self._find_strip(index)
        strip.set_rgb(index, *rgb565_to_rgb(color))

    def clear(self):
        for strip, _, _ in self._strips:
            strip.clear()
