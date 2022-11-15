#!/usr/bin/python3

# SPDX-License-Identifier: GPL-3.0-or-later

"""
The HTTP server for the BlinkenXmas project. Provides a simple web-interface
for building tree animations and serving them over MQTT to the Pico W connected
to the blinkenlights on the tree.
"""

import os
import sys
import sqlite3
from pathlib import Path
from string import Template
from functools import partial
from argparse import ArgumentParser
from configparser import ConfigParser
from http.server import ThreadingHTTPServer

from pkg_resources import require


XDG_CONFIG_HOME = os.environ.get('XDG_CONFIG_HOME', '~/.config')


class TreeServer(ThreadingHTTPServer):
    allow_reuse_address = True


class TreeRequestHandler(BaseHTTPRequestHandler):
    server_version = 'BlinkenXmas/1.0'

    def do_GET(self):
        pass


def get_best_family(host, port):
    infos = socket.getaddrinfo(
        host, port,
        type=socket.SOCK_STREAM,
        flags=socket.AI_PASSIVE)
    family, type, proto, canonname, sockaddr = next(iter(infos))
    return family, sockaddr


def server(config):
    TreeServer.address_family, addr = get_best_family(config.bind, config.port)
    with DevServer(addr[:2], TreeRequestHandler) as httpd:
        host, port = httpd.socket.getsockname()[:2]
        hostname = socket.gethostname()
        print(f'Serving {config.html} HTTP on {host} port {port}')
        print(f'http://{hostname}:{port}/ ...')
        httpd.serve_forever()


def get_config(args, section='blinkenxmas'):
    config = ConfigParser(
        defaults={
            'db': 'blinkenxmas.db',
            'bind': '0.0.0.0',
            'port': '8000',
        },
        delimiters=('=',), default_section=SETUP_SECTION,
        empty_lines_in_values=False, interpolation=None,
        converters={'list': lambda s: s.strip().splitlines()})
    #config.read(PROJECT_ROOT / 'setup.cfg')
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
        '--bind', metavar='ADDR', default=config[section]['bind'],
        help="The address to listen on. Default: %(default)s")
    parser.add_argument(
        '--port', metavar='PORT', default=config[section]['port'],
        help="The port to listen on. Default: %(default)s")
    return parser.parse_args(args)


def main(args=None):
    try:
        config = get_config(args)
        server(parser.parse_args(args))
    except KeyboardInterrupt as e:
        print("Interrupted", file=sys.stderr)
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
