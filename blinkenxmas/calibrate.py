import io
from time import sleep
from pathlib import Path
from operator import itemgetter
from threading import Thread, Event, Lock

import numpy as np
from colorzero import Color
from PIL import Image, ImageChops, ImageDraw, ImageFilter

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


class Calibration:
    def __init__(self, angle, camera, queue, led_count):
        self._lock = Lock()
        self._stop = Event()
        self._thread = None
        self._base = None
        self._base_image = None
        # XXX Make this configurable? Is it necessary to do different colors?
        self._colors = [
            Color('red'),
            Color('green'),
            Color('blue'),
            Color('white'),
        ]
        self._angle = angle
        self._mask = []
        self._positions = {}
        self._count = led_count
        self._camera = camera
        self._queue = queue
        self.capture_base()

    def capture_base(self):
        self._queue.put([])
        self._queue.join()
        # XXX Wait? May not be necessary given camera warm-up time
        self._base = io.BytesIO(self._camera.capture(self._angle).read())
        self._base_image = Image.open(self._base)
        if self._base_image.mode != 'RGB':
            self._base_image = self._base_image.convert('RGB')
        self._base.seek(0)
        w, h = self._base_image.size
        self._mask = [
            (0, 0),
            (w - 1, 0),
            (w - 1, h - 1),
            (0, h - 1),
        ]

    def start(self, mask):
        with self._lock:
            if not self._thread:
                self._thread = Thread(target=self.calibrate, daemon=True)
                self._mask = mask
                self._stop.clear()
                self._thread.start()

    def stop(self):
        with self._lock:
            if self._thread:
                self._stop.set()
                self._thread.join(timeout=10)
                if self._thread.is_alive():
                    raise RuntimeError('failed to stop calibration thread')
                self._thread = None

    def calibrate(self):
        black = Color('black')
        w, h = self._base_image.size
        clear = Image.new('RGB', (w, h))
        mask = Image.new('1', (w, h))
        draw = ImageDraw.Draw(mask)
        draw.polygon([(int(x * w), int(y * h)) for x, y in self._mask], fill=1)
        base = clear.copy()
        base.paste(self._base_image, mask=mask)

        # The position is calculated by taking the difference between the
        # captured image for a given color on the LED and the base image
        # captured for the currently configured angle, applying a Gaussian blur
        # to remove high-frequency noise (as a result of camera motion,
        # changing daylight, etc.), and selecting the brightest pixels in the
        # resulting image.
        #
        # The positions of the brightest pixels are then subject to a weighted
        # median to determine "the" position of the LED in the X/Y plane for
        # the given angle (X will be adjusted to Z later based on the
        # configured angle).
        for led in range(self._count):
            positions = []
            for color in self._colors:
                if self._stop.wait(0):
                    return
                self._queue.put([[
                    color if led == i else black
                    for i in range(self._count)
                ]])
                self._queue.join()
                with self._camera.capture(self._angle, led, color) as f:
                    image = clear.copy()
                    image.paste(Image.open(f), mask=mask)
                diff = ImageChops.subtract(image, base).filter(
                    ImageFilter.GaussianBlur(radius=7)).convert('L')
                arr = np.frombuffer(diff.tobytes(), dtype=np.uint8).reshape(
                    diff.height, diff.width)
                score = arr.max()
                if score:
                    coords = (arr == score).nonzero()
                    for y, x in zip(*coords):
                        # The int() calls below are necessary to convert from
                        # numpy's size-specific integers (which can't be
                        # serialized to JSON)
                        positions.append(((x / w, y / h), int(score)))

            position, score = weighted_median(positions)
            # TODO Threshold the score
            self._positions[led] = position

    @property
    def angle(self):
        return self._angle

    @property
    def base(self):
        return self._base.getvalue()

    @property
    def mask(self):
        return self._mask

    @property
    def progress(self):
        return len(self._positions) / self._count

    @property
    def positions(self):
        return {
            led: coord
            # Copy needed as thread may be simultaneously inserting into dict
            # (could lock, but the dict is guaranteed tiny)
            for led, coord in self._positions.copy().items()
            if coord is not None
        }
