#!/usr/bin/python3

# SPDX-License-Identifier: GPL-3.0-or-later

"""
The HTTP server for the BlinkenXmas project. Provides a simple web-interface
for building tree animations and serving them over MQTT to the Pico W connected
to the blinkenlights on the tree.
"""

import os
import sys
from queue import Queue
from pathlib import Path
from string import Template
from argparse import ArgumentParser
from configparser import ConfigParser

from pkg_resources import require

from . import httpd, mqtt, routes, animations


XDG_CONFIG_HOME = os.environ.get('XDG_CONFIG_HOME', '~/.config')


def get_config(args, section='blinkenxmas'):
    config = ConfigParser(
        defaults={
            'db': '/var/blinkenxmas/blinkenxmas.db',
            'broker-address': 'localhost',
            'broker-port': '1883',
            'topic': 'blinkenxmas',
            'httpd-bind': '0.0.0.0',
            'httpd-port': '80',
        },
        delimiters=('=',), default_section=section,
        empty_lines_in_values=False, interpolation=None,
        converters={'list': lambda s: s.strip().splitlines()})
    for filename in (
        '/etc/blinkenxmas.conf',
        '$XDG_CONFIG_HOME/blinkenxmas.conf',
        '~/.blinkenxmas.conf'
    ):
        path = Path(Template(filename).substitute({
            'XDG_CONFIG_HOME': XDG_CONFIG_HOME,
            'HOME': str(Path.home()),
        }))
        config.read(path.expanduser())
        if not Path(config[section]['db']).is_absolute():
            config[section]['db'] = str(path / Path(config[section]['db']))

    parser = ArgumentParser(description=__doc__.format(**globals()))
    parser.add_argument(
        '--version', action='version', version=require('blinkenxmas')[0].version)
    parser.add_argument(
        '--db', metavar='FILE', default=config[section]['db'],
        help="The SQLite database to store presets in. Default: %(default)s")
    parser.add_argument(
        '--broker-address', metavar='ADDR',
        default=config[section]['broker-address'],
        help="The address on which to find the MQTT broker. Default: "
        "%(default)s")
    parser.add_argument(
        '--broker-port', metavar='ADDR', type=httpd.get_port,
        default=config[section]['broker-port'],
        help="The address on which to find the MQTT broker. Default: "
        "%(default)s")
    parser.add_argument(
        '--topic', default=config[section]['topic'],
        help="The topic on which the Pico W is listening for messages. "
        "Default: %(default)s")
    parser.add_argument(
        '--httpd-bind', metavar='ADDR', default=config[section]['httpd-bind'],
        help="The address on which to listen for HTTP requests. Default: "
        "%(default)s")
    parser.add_argument(
        '--httpd-port', metavar='PORT', type=httpd.get_port,
        default=config[section]['httpd-port'],
        help="The port to listen for HTTP requests. Default: %(default)s")
    parser.add_argument(
        '--led-count', metavar='NUM', type=int, default=50,
        help="The number of LEDs controlled by the Pico")
    parser.add_argument(
        '--fps', metavar='NUM', type=int, default=60,
        help="The number of frames per second that the Pico will show")
    return parser.parse_args(args)


def main(args=None):
    try:
        queue = Queue()
        config = get_config(args)
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


if __name__ == '__main__':
    sys.exit(main())
