import io
import logging
from time import sleep
from pathlib import Path
from statistics import median
from operator import itemgetter
from itertools import accumulate
from threading import Thread, Event, Lock

import numpy as np
from colorzero import Color
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from . import mqtt, httpd

try:
    from math import dist
except ImportError:
    from math import sqrt
    dist = lambda a, b: sqrt(sum((px - qx) ** 2 for px, qx in zip(p, q)))


class PointNotFound(ValueError):
    """
    Exception raised by the calibration engine when it cannot find an LED by
    comparison to a base unlit image.
    """


class Angle:
    score_fuzz = 10
    score_min = 10
    area_max = 0.01

    def __init__(self, angle, camera, queue, strips):
        self._lock = Lock()
        self._stop = Event()
        self._thread = None
        self._base = None
        self._base_image = None
        self._angle = angle
        self._mask = []
        self._positions = {}
        self._scores = {}
        self._strips = strips
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
                if mask:
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
        white = Color('white')
        w, h = self._base_image.size
        blur = ImageFilter.GaussianBlur(radius=5)
        clear = Image.new('RGB', (w, h))
        mask = Image.new('1', (w, h))
        draw = ImageDraw.Draw(mask)
        draw.polygon([(int(x * w), int(y * h)) for x, y in self._mask], fill=1)
        base = clear.copy()
        base.paste(self._base_image, mask=mask)
        base = base.filter(blur)

        count = sum(len(strip) for strip in self._strips)
        for strip in self._strips:
            for led in strip:
                positions = []
                if self._stop.wait(0):
                    return
                scene = [black] * count
                scene[led] = white
                self._queue.put([scene])
                self._queue.join()
                with self._camera.capture(self._angle, led) as f:
                    image = clear.copy()
                    image.paste(Image.open(f), mask=mask)
                    image = image.filter(blur)
                try:
                    position, score = self._calibrate_diff(base, image)
                except PointNotFound as e:
                    self._scores[led] = 0
                    logging.warning('LED #%d: %s', led, str(e))
                    continue
                else:
                    self._positions[led] = position
                    self._scores[led] = score

    def _calibrate_diff(self, unlit, lit):
        # The position is calculated by taking the difference between the
        # captured image for a given color on the LED and the base image
        # captured for the currently configured angle, applying a Gaussian blur
        # to remove high-frequency noise (as a result of camera motion,
        # changing daylight, etc.), and selecting the brightest pixels in the
        # resulting image.
        #
        # If the brightest pixels aren't sufficiently bright (indicating very
        # little difference), the point is rejected. The area covered by the
        # brightest pixels is then sanity checked (a less than marginal match
        # usually covers several patches of an image). If this passes, the a
        # median of all matched coordinates is taken to determine the canonical
        # "position" of the LED. Note this only covers the position in the X/Y
        # plane. Later we'll calculate the Z based on matching positions
        # between angles.
        diff = ImageChops.difference(lit, unlit).convert('L')
        w, h = diff.size
        arr = np.frombuffer(diff.tobytes(), dtype=np.uint8).reshape(h, w)
        score = arr.max()
        if score < self.score_min:
            raise PointNotFound(f'diff score too low: {score}')
        coords = (arr >= score - self.score_fuzz).nonzero()
        area = (
            (coords[1].max() - coords[1].min()) *
            (coords[0].max() - coords[0].min())) / (w * h)
        if area > self.area_max:
            raise PointNotFound(
                f'potential coords cover large area: {area*100:0.2f}%')
        coords = [(x / w, y / h) for y, x in zip(*coords)]
        position = (
            median(x for x, y in coords),
            median(y for x, y in coords))
        # The int() calls below are necessary to convert from numpy's
        # size-specific integers (which can't be serialized to JSON)
        return position, int(score)

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
        return len(self._scores) / sum(len(strip) for strip in self._strips)

    @property
    def positions(self):
        return {
            led: coord
            # Copy needed as thread may be simultaneously inserting into dict
            # (could lock, but the dict is guaranteed tiny)
            for led, coord in self._positions.copy().items()
            if coord is not None
        }

    @property
    def scores(self):
        return {
            led: score
            for led, score in self._scores.copy().items()
            if score is not None
        }


class Positions:
    def __init__(self):
        self._positions = {}

    @property
    def positions(self):
        return self._positions
