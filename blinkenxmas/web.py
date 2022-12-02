"""
The HTTP server for the BlinkenXmas project. Provides a simple web-interface
for building tree animations and serving them over MQTT to the Pico W connected
to the blinkenlights on the tree.
"""

import os
import sys
from queue import Queue

# NOTE: The routes and animations imports are performed solely to "register"
# their definitions with the httpd module
from . import mqtt, httpd, routes, animations
from .config import get_parser


def main(args=None):
    try:
        parser = get_parser(description=__doc__)
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
