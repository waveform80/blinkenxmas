import os
import sys
from queue import Queue
from pathlib import Path

# NOTE: The routes and animations imports are performed solely to "register"
# their definitions with the httpd module
from . import mqtt, httpd, routes, animations
from .config import (
    get_config, get_parser,
    resolution, port, rotation, SUPPRESS
)


def get_web_parser():
    """
    Return an :class:`~blinkenxmas.config.ConfigArgumentParser` instance for
    handling the options of :program:`bxweb`.
    """
    config = get_config()
    parser = get_parser(config, description=__doc__)

    web_section = parser.add_argument_group('web', section='web')
    web_section.add_argument(
        '--httpd-bind', key='bind', metavar='ADDR',
        help="the address on which to listen for HTTP requests. Default: "
        "%(default)s")
    web_section.add_argument(
        '--httpd-port', key='port', type=port, metavar='PORT',
        help="the port to listen for HTTP requests. Default: %(default)s")
    web_section.add_argument(
        '--no-production', dest='production', section='web', key='production',
        action='store_false')
    web_section.add_argument(
        '--production', section='web', key='production', action='store_true',
        help="If specified, run in production mode where an internal server "
        "error will not terminate the server and will not output a stack "
        "trace (default: no)")
    web_section.add_argument(
        '--db', metavar='FILE', key='database',
        help="the SQLite database to store presets in. Default: %(default)s")

    camera_section = parser.add_argument_group(section='camera')
    camera_section.add_argument(
        '--camera-type', key='type', default='none',
        choices={'none', 'files', 'picamera', 'gstreamer'},
        help=SUPPRESS)
    camera_section.add_argument(
        '--camera-path', key='path', type=Path,
        help=SUPPRESS)
    camera_section.add_argument(
        '--camera-device', key='device', default='/dev/video0', type=Path,
        help=SUPPRESS)
    camera_section.add_argument(
        '--camera-capture', key='capture', default='960x720', type=resolution,
        help=SUPPRESS)
    camera_section.add_argument(
        '--camera-preview', key='preview', default='640x480', type=resolution,
        help=SUPPRESS)
    camera_section.add_argument(
        '--camera-rotation', key='rotate', default='0', type=rotation,
        help=SUPPRESS)

    parser.set_defaults_from(config)
    return parser


def main(args=None):
    "Entry point for :program:`bxweb`"
    try:
        config = get_web_parser().parse_args(args)
        if config.led_count == 0:
            raise RuntimeError(
                'No LED strips defined; please edit the configuration file')
        queue = Queue()
        messages = httpd.Messages()
        with mqtt.MessageThread(config, queue) as message_task, \
                httpd.HTTPThread(config, messages, queue) as httpd_task:
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
