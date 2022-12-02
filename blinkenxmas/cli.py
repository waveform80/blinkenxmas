"""
The command line interface for the BlinkenXmas project. Provides a simple
command line which can load or delete an existing preset, set all LEDs to a
specific color, or set an individual LED to a specified color.
"""

import os
import sys
from queue import Queue

from colorzero import Color

from . import mqtt
from .store import Storage
from .config import get_parser


def get_commands_parser(*, description):
    parser = get_parser(description=description)
    parser.set_defaults(func=do_help)

    commands = parser.add_subparsers(title='commands')

    help_cmd = commands.add_parser(
        'help',
        description="With no arguments, display the list of sub-commands. "
        "If a command name is given, display the description and options for "
        "that command",
        help="Display command help")
    help_cmd.add_argument(
        'cmd', nargs='?',
        help="The name of the command to display help for")
    help_cmd.set_defaults(func=do_help)

    off_cmd = commands.add_parser(
        'off', aliases=['clear'],
        description="Switch all LEDs off",
        help="Switch all LEDs off")
    off_cmd.set_defaults(func=do_off)

    on_cmd = commands.add_parser(
        'on', aliases=['all'],
        description="Switch all LEDs on with the specified color",
        help="Switch all LEDs to the specified color")
    on_cmd.add_argument(
        'color', type=Color,
        help="The color to set all LEDs to; may be given as a common CSS3 "
        "color name, or an HTML color code, i.e. #RRGGBB")
    on_cmd.set_defaults(func=do_on)

    set_cmd = commands.add_parser(
        'set',
        description="Switch on a single LED to the specified color",
        help="Switch one LED on to the specified color")
    set_cmd.add_argument(
        'number', type=int,
        help="The number of the LED (from 1 to the number of LEDs) to light")
    set_cmd.add_argument(
        'color', type=Color,
        help="The color to set the LEDs to; may be given as a common CSS3 "
        "color name, or an HTML color code, i.e. #RRGGBB")

    list_cmd = commands.add_parser(
        'list', aliases=['ls'],
        description="List the names of all available presets",
        help="List all presets")
    list_cmd.set_defaults(func=do_list)

    show_cmd = commands.add_parser(
        'show', aliases=['load'],
        description="Load and display the specified preset",
        help="Show a preset")
    show_cmd.add_argument(
        'preset',
        help="The name of the preset to load; if the preset contains spaces "
        "it will need quoting on the command line")
    show_cmd.set_defaults(func=do_show)

    return parser


def do_help(config, queue):
    parser = get_commands_parser(description=__doc__)
    if 'cmd' in config and config.cmd is not None:
        parser.parse_args([config.cmd, '-h'])
    else:
        parser.parse_args(['-h'])


def do_off(config, queue):
    queue.put([[]])


def do_on(config, queue):
    queue.put([[config.color.html] * config.led_count])


def do_set(config, queue):
    black = Color('black')
    queue.put([[
        config.color.html if number == config.number else black
        for number in range(1, config.led_count + 1)
    ]])


def do_list(config, queue):
    store = Storage(config.db)
    for preset in store:
        print(preset)


def do_show(config, queue):
    store = Storage(config.db)
    queue.put(store[config.preset])


def main(args=None):
    parser = get_commands_parser(description=__doc__)
    try:
        config = parser.parse_args(args)
        queue = Queue()
        with mqtt.MessageThread(queue, config) as message_task:
            config.func(config, queue)
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
