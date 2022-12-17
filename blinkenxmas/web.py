"""
The HTTP server for the BlinkenXmas project. Provides a simple web-interface
for building tree animations and serving them over MQTT to the Pico W connected
to the blinkenlights on the tree.
"""

import os
import sys
from queue import Queue
from pathlib import Path

# NOTE: The routes and animations imports are performed solely to "register"
# their definitions with the httpd module
from . import mqtt, httpd, routes, animations
from .config import get_config, get_parser, get_port, SUPPRESS


def get_web_parser():
    config = get_config()
    parser = get_parser(config, description=__doc__)

    parser.add_argument(
        '--httpd-bind', section='web', key='bind', metavar='ADDR',
        help="the address on which to listen for HTTP requests. Default: "
        "%(default)s")
    parser.add_argument(
        '--httpd-port', section='web', key='port',
        type=get_port, metavar='PORT',
        help="the port to listen for HTTP requests. Default: %(default)s")

    parser.add_argument(
        '--camera-type', section='camera', key='type', default='none',
        choices={'none', 'files', 'picamera', 'gstreamer'}, help=SUPPRESS)
    parser.add_argument(
        '--camera-path', section='camera', key='path', type=Path,
        help=SUPPRESS)
    parser.add_argument(
        '--camera-device', section='camera', key='device',
        default='/dev/video0', type=Path,
        help=SUPPRESS)

    parser.set_defaults_from(config)
    return parser


def main(args=None):
    parser = get_web_parser()
    try:
        config = parser.parse_args(args)
        queue = Queue()
        with (
            mqtt.MessageThread(queue, config) as message_task,
            httpd.HTTPThread(queue, config) as httpd_task,
        ):
            while True:
                httpd_task.join(1)
                if not httpd_task.is_alive():
                    break
                message_task.join(1)
                if not message_task.is_alive():
                    break
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
