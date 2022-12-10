"""
BlinkenXmas calibration tool. Alpha quality :)
"""

import os
import io
import re
import sys
import json
import argparse
from time import sleep
from queue import Queue
from pathlib import Path
from argparse import SUPPRESS
from collections import namedtuple
from operator import itemgetter
from threading import Condition

import numpy as np
from colorzero import Color
from PIL import Image, ImageChops, ImageFilter

from . import mqtt, httpd
from .config import get_config_and_parser


Capture = namedtuple('Capture', (
    'angle',
    'led',
    'color',
    'base',
    'image'))


class Source:
    def __init__(self, queue, config):
        self._queue = queue
        self._frame_ready = Condition()

    def start_preview(self):
        raise NotImplementedError

    def stop_preview(self):
        pass

    @property
    def frame_ready(self):
        return self._frame_ready

    @property
    def frame(self):
        pass

    @property
    def progress(self):

    def _capture_base(self):
        raise NotImplementedError

    def _capture_led(self):

    def stream(self):
        try:
            queue.put([[]])
            queue.join()
            sleep(1) # TODO Do we still need this?
            buf = io.BytesIO()
            camera.capture(buf, format='jpeg')
            buf.seek(0)
            base_image = Image.open(buf)
            # TODO Draw tree contour if interactive
            print(f'Captured base image for angle {angle:03d}')
            black = Color(0, 0, 0)
            for led in range(config.led_count):
                for color in config.colors:
                    queue.put([[
                        color if led == i else black
                        for i in range(config.led_count)
                    ]])
                    queue.join()
                    sleep(1) # TODO Do we still need this?
                    buf.seek(0)
                    camera.capture(buf, format='jpeg')
                    buf.truncate()
                    buf.seek(0)
                    lit_image = Image.open(buf)
                    yield Capture(
                        config.angle, led, color, base_image, lit_image)
        finally:
            queue.put([[]])


def files_capture(config):
    if not config.files_path:
        raise RuntimeError(
            '--files-path must be specified for the "files" camera')
    base_path = Path(config.files_path) / f'angle{config.angle:03d}_base.jpg'
    base_image = Image.open(base_path)
    if config.interactive:
        # TODO Draw tree contour if interactive
        pass
    for led in range(config.led_count):
        for color in config.colors:
            lit_path = (
                Path(config.files_path) /
                f'angle{config.angle:03d}_'
                f'led{led:03d}_'
                f'color{color.html}.jpg')
            yield Capture(
                config.angle, led, color, base_image, Image.open(lit_path))


def picamera_capture(config):
    from picamera import PiCamera

    queue = Queue()
    with (
            PiCamera(resolution=PiCamera.MAX_RESOLUTION) as camera,
            mqtt.MessageThread(queue, config) as message_task):
        try:
            if config.interactive:
                camera.start_preview(resolution='720p')
                input("Press Enter to proceed with capture")
                camera.stop_preview()
            else:
                # Provide time for exposure and white-balance to settle
                sleep(3)
            # TODO Lock exposure and white-balance off baseline
            queue.put([[]])
            queue.join()
            sleep(1) # TODO Do we still need this?
            buf = io.BytesIO()
            camera.capture(buf, format='jpeg')
            buf.seek(0)
            base_image = Image.open(buf)
            # TODO Draw tree contour if interactive
            print(f'Captured base image for angle {angle:03d}')
            black = Color(0, 0, 0)
            for led in range(config.led_count):
                for color in config.colors:
                    queue.put([[
                        color if led == i else black
                        for i in range(config.led_count)
                    ]])
                    queue.join()
                    sleep(1) # TODO Do we still need this?
                    buf.seek(0)
                    camera.capture(buf, format='jpeg')
                    buf.truncate()
                    buf.seek(0)
                    lit_image = Image.open(buf)
                    yield Capture(
                        config.angle, led, color, base_image, lit_image)
        finally:
            queue.put([[]])
            camera.stop_preview()


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


def main(args=None):
    try:
        _, parser = get_config_and_parser(description=__doc__)
        parser.add_argument(
            'camera', choices=['picamera', 'files'],
            help="The camera type to use")
        parser.add_argument(
            '--files-path', type=Path,
            help="The path to use with the selected camera type")
        parser.add_argument(
            '-a', '--angle', type=int, default=0,
            help="The angle (about the axis of the tree's trunk) from which "
            "captures will be taken")
        parser.add_argument(
            '--interactive', action='store_true')
        parser.add_argument(
            '--no-interactive', dest='interactive', action='store_true',
            help="Proceed without prompting; useful when dealing with a Pi "
            "with no console")

        # Internal arguments
        parser.add_argument(
            '--colors', default='white,red,green,blue',
            help=SUPPRESS)

        config = parser.parse_args(args)
        config.colors = [
            Color(s.strip())
            for s in config.colors.split(',')
        ]

        stream = {
            'picamera': picamera_capture,
            'files':    files_capture,
        }[config.camera](config)
        positions = calibrate(config, stream)
        print(json.dumps(positions))

    except KeyboardInterrupt:
        print('Interrupted', file=sys.stderr)
        return 2
    except Exception as e:
        debug = int(os.environ.get('DEBUG', '0'))
        if not debug:
            print(str(e), file=sys.stderr)
            return 1
        elif debug == 1:
            raise
        else:
            import pdb
            pdb.post_mortem()
    else:
        return 0
