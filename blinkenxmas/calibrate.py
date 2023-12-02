import io
import logging
import math as m
from time import sleep
from pathlib import Path
from collections import Counter
from contextlib import suppress
from operator import itemgetter
from statistics import median, mean
from threading import Thread, Event, Lock
from itertools import accumulate, combinations

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


def weighted_median(seq):
    items = sorted(seq, key=itemgetter(0))
    cum_weights = list(accumulate(weight for item, weight in items))
    try:
        median = cum_weights[-1] / 2.0
    except IndexError:
        raise ValueError('seq must contain at least one item')
    for (item, weight), cum_weight in zip(items, cum_weights):
        if cum_weight >= median:
            return item, weight


class AngleScanner:
    score_fuzz = 10
    score_min = 10
    area_max = 0.01
    logger = logging.getLogger('scanner')

    def __init__(self, angle, camera, queue, strips, messages):
        self._messages = messages
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
        self._queue.put([[]])
        self._queue.join()
        # Be sure the camera's had some time to warm up and deal with AWB et al
        sleep(1)
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

    def scan(self, mask):
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
        try:
            self._calibrate_scan()
        finally:
            self._queue.put([[]])
            self._queue.join()
            self._messages.show(f'Scan finished for angle {self._angle}°')

    def _calibrate_scan(self):
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
        scene = [black] * count
        for strip in self._strips:
            for led in strip:
                positions = []
                if self._stop.wait(0):
                    return
                scene[led] = white
                self._queue.put([scene])
                self._queue.join()
                scene[led] = black
                with self._camera.capture(self._angle, led) as f:
                    image = clear.copy()
                    image.paste(Image.open(f), mask=mask)
                    image = image.filter(blur)
                try:
                    position, score = self._calibrate_diff(base, image)
                except PointNotFound as e:
                    self._scores[led] = 0
                    self.logger.warning('LED #%d: %s', led, str(e))
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


class PositionsCalculator:
    score_min = 40
    logger = logging.getLogger('calculator')

    def __init__(self, strips, messages):
        self._messages = messages
        self._strips = strips
        self._angles = {}
        self._scores = {}
        self._positions = {}
        self._confidence = {}

    def clear(self):
        self._angles.clear()
        self._scores.clear()
        self._positions.clear()
        self._confidence.clear()
        self._messages.show('Cleared calculated positions')

    def add_angle(self, scanner):
        with suppress(KeyError):
            del self._angles[scanner.angle]
        # The coordinates passed by the scanner are relative to the picture as
        # a whole, but we need the X coordinates to be relative to the trunk
        # of the tree (or the centre of rotation, more precisely). Find the
        # trunk's X coordinate by the average of the minimum and maximum X
        # coordinates of "good" positions
        good_x = [
            x
            for ((x, y), score) in [
                (scanner.positions[key], scanner.scores[key])
                for key in scanner.positions
            ]
            if score >= self.score_min
        ]
        trunk_x = mean([min(good_x), max(good_x)])
        self._angles[scanner.angle] = {
            led: (x - trunk_x, y)
            for led, (x, y) in scanner.positions.items()
        }
        self._scores[scanner.angle] = {
            led: score
            for led, score in scanner.scores.items()
        }
        self.estimate()

    def estimate(self):
        self.logger.info(
            f'Beginning estimation with {len(self._angles)} scanned angles')
        led_angles = {}
        new_positions = {}
        for angle in self._angles:
            for led in self._angles[angle]:
                led_angles.setdefault(led, set()).add(angle)
        for led, angles in led_angles.items():
            if len(angles) == 1:
                continue
            self.logger.info(
                f'Estimating position of LED {led} from {len(angles)} angles')
            for a1, a2 in combinations(sorted(angles), 2):
                if abs(a2 - a1) == 180:
                    self.logger.warning(
                        'Skipping because angle difference is 180°')
                    continue

                x1, y1 = self._angles[a1][led]
                x2, y2 = self._angles[a2][led]
                if abs(y1 - y2) > 0.1:
                    self.logger.warning(
                        f'LED {led} went from ({x1}, {y1}) at {a1}° to '
                        f'({x2}, {y2}) at {a2}°')
                # This little bit of trigonometric magic is thanks to user KDP
                # on the math(s) stack-exchange [1]. The question for that
                # answer is written specifically with this application in mind
                # and may shed more light on how this is being solved, too.
                #
                # [1]: https://math.stackexchange.com/a/4816273/555505
                #
                # NOTE: This probably *ought* to use atan2, but every time I've
                # tried in practice I get plenty of weird readings that are
                # exactly 180° out. Oh well, this seems to work for now...
                alpha = m.radians(a2) - m.radians(a1)
                try:
                    beta = m.atan(
                        m.sin(alpha) /
                        ((x2 / x1) - m.cos(alpha)))
                    r = abs(x1 / m.sin(beta))
                except ZeroDivisionError:
                    self.logger.warning(
                        f'Bad r-calculation for LED {led} with alpha={alpha}, '
                        f'x1={x1}, x2={x2}')
                    continue

                # Because atan only operates from -90° to 90° (-π/2 to π/2 for
                # those working in radians), we need to determine where on the
                # circle it is. The offset and modulo step gets us into the
                # "left half" of the tree (angles 0° to 180°). We then
                # calculate a "check x1" value. If this has the same sign as
                # the original then our result is actually in the "right half"
                # of the tree (as you look at it) so we need to offset by 180°.
                a = (m.degrees(beta) - a1) % 180
                tx1 = r * m.sin(m.radians(a1 + a))
                if (tx1 > 0) == (x1 > 0):
                    a += 180
                else:
                    tx1 = -tx1
                if not m.isclose(x1, tx1, rel_tol=0.00001):
                    self.logger.warning(
                        f'Test x-calculation for LED {led} is not within '
                        f'expected tolerance, x1={x1}, tx1={tx1}')

                # Calculate a confidence score to use as a weighted median on
                # determining the "real" position. This is heavily biased by
                # the two scores of the input points. The sin of the angle
                # between the two measured angles favours those that aren't
                # near 0 and 180° (at which point the problem is degenerate and
                # nothing can be determined) and favours those closer to 90°.
                # Finally, major differences in the two Y-coordinates are
                # heavily penalised.
                confidence = abs(
                    self._scores[a1][led] *
                    self._scores[a2][led] *
                    m.sin(alpha) *
                    max(0, 1 - (y2 - y1) * 10))

                if r <= 1:
                    new_positions.setdefault(led, set()).add((
                        (y1, a, r), # height from base, angle, radius from trunk
                        confidence,
                    ))
                else:
                    self.logger.warning(
                        f'Ignoring z={z} for LED {led} with alpha={alpha}, '
                        f'beta={beta}, x1={x1}, x2={x2}')
        if new_positions:
            self._positions = {
                led: weighted_median(positions)
                for led, positions in new_positions.items()
            }
            self._messages.show(
                f'Calculated {len(self._positions)} from '
                f'{len(self._angles)} angles')

    @property
    def angles(self):
        return self._angles

    @property
    def positions(self):
        return self._positions


class Calibration:
    def __init__(self, config, messages):
        self.config = config
        self.scanner = None
        self.calculator = PositionsCalculator(config.led_strips, messages)
