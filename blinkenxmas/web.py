"""
The HTTP server for the BlinkenXmas project. Provides a simple web-interface
for building tree animations and serving them over MQTT to the Pico W connected
to the blinkenlights on the tree.
"""

import os
import sys
from queue import Queue

from . import mqtt, httpd
from .config import get_parser


def main(args=None):
    try:
        queue = Queue()
        config = get_parser(description=__doc__).parse_args(args)
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
