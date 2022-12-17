from time import sleep
from pathlib import Path
from operator import itemgetter

import numpy as np
from colorzero import Color
from PIL import Image, ImageChops, ImageFilter

from . import mqtt, httpd


def cum_sum(it, start=0):
    for item in it:
        start += item
        yield start


def weighted_median(seq):
    items = sorted(seq, key=itemgetter(0))
    cum_weights = list(cum_sum(weight for item, weight in items))
    try:
        median = cum_weights[-1] / 2.0
    except IndexError:
        raise ValueError('seq must contain at least one item')
    for (item, weight), cum_weight in zip(items, cum_weights):
        if cum_weight >= median:
            return item, weight


def calibrate(config, stream):
    # pos is the mapping {led: {angle: (x, y)}}, that is the mapping of LED
    # index to angle to position.
    #
    # The position is calculated by taking the difference between the captured
    # image for a given color on the LED and the base image captured for the
    # currently configured angle, applying a Gaussian blur to remove
    # high-frequency noise (as a result of camera motion, changing daylight,
    # etc.), and selecting the brightest pixels in the resulting image.
    #
    # The positions of the brightest pixels are then subject to a weighted
    # median to determine "the" position of the LED in the X/Y plane for the
    # given angle (X will be adjusted to Z later based on the configured
    # angle).
    bases = {}
    pos = {}
    for capture in stream:
        bases[capture.angle] = capture.base
        diff = ImageChops.subtract(capture.image, capture.base).filter(
            ImageFilter.GaussianBlur(radius=7)).convert('L')
        arr = np.frombuffer(diff.tobytes(), dtype=np.uint8).reshape(
            diff.height, diff.width)
        score = arr.max()
        coords = (arr == score).nonzero()
        for y, x in zip(*coords):
            pos.setdefault(
                capture.led, {}).setdefault(
                    capture.angle, []).append(((int(x), int(y)), int(score)))

    pos = {
        led: {
            angle: weighted_median(coords)
            for angle, coords in angles.items()
        }
        for led, angles in pos.items()
    }

    from PIL import ImageDraw
    result = bases[config.angle].copy()
    draw = ImageDraw.Draw(result)
    for led in pos:
        coord, score = pos[led][config.angle]
        x, y = coord
        top_left = (x - 10, y - 10)
        bottom_right = (x + 10, y + 10)
        draw.ellipse((top_left, bottom_right), outline=(255, 0, 0), width=5)
    result.show()

    return pos
