"""
The capture calibration tool for the BlinkenXmas project. Must be run on a
Raspberry Pi equipped with a camera module. The utility will illuminate each
LED a variety of colors, capturing an image of each. A baseline image of the
tree (or frame) will also be captured. This can (and should) be run multiple
times from a variety of different angles of the tree, but from the same
distance each time. At least two captures from different angles are required to
calculate a 3-dimensional coordinate for a given LED.
"""

import os
import sys
from time import sleep
from queue import Queue
from pathlib import Path
from argparse import SUPPRESS

from picamera import PiCamera
from colorzero import Color

from . import mqtt
from .config import get_parser


def main(args=None):
    try:
        parser = get_parser(description=__doc__)
        parser.add_argument(
            '-o', '--output', type=Path, metavar='DIR', default='.',
            help="The path under which to store all the captured images")
        parser.add_argument(
            '-a', '--angle', type=int, default=0,
            help="The angle (about the axis of the tree's trunk) from which "
            "captures will be taken")
        parser.add_argument(
            '-y', '--yes', dest='prompt', action='store_false',
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
        queue = Queue()
        with (
                PiCamera(resolution=PiCamera.MAX_RESOLUTION) as camera,
                mqtt.MessageThread(queue, config) as message_task):
            try:
                if config.prompt:
                    camera.start_preview(resolution='720p')
                    input("Press Enter to proceed with capture")
                    camera.stop_preview()
                else:
                    # Provide time for exposure and white-balance to settle
                    sleep(3)
                # TODO lock exposure and white-balance off baseline
                queue.put([[]])
                sleep(1)
                filename = config.output / f'angle{config.angle:03d}_base.jpg'
                camera.capture(filename)
                print(f'Captured {filename}')
                black = Color(0, 0, 0)
                for led in range(config.led_count):
                    for color in config.colors:
                        queue.put([[
                            color if led == i else black
                            for i in range(config.led_count)
                        ]])
                        sleep(1)
                        filename = (
                            config.output /
                            f'angle{config.angle:03d}_'
                            f'led{led:03d}_'
                            f'color{color.html}.jpg')
                        camera.capture(str(filename))
                        print(f'Captured {filename}')
            finally:
                queue.put([[]])
                camera.stop_preview()

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
