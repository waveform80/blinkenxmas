import os
import sys
from queue import Queue

from colorzero import Color

from . import mqtt
from .store import Storage
from .config import get_config, get_parser


def get_cli_parser():
    """
    Return an :class:`~blinkenxmas.config.ConfigArgumentParser` instance for
    handling the options of :program:`bxcli`.
    """
    config = get_config()
    parser = get_parser(config, description=__doc__)
    parser.set_defaults(func=do_help)

    commands = parser.add_subparsers(title='commands')

    help_cmd = commands.add_parser(
        'help',
        description=do_help.__doc__,
        help="Display command help")
    help_cmd.add_argument(
        'cmd', nargs='?',
        help="The name of the command to display help for")
    help_cmd.set_defaults(func=do_help)

    off_cmd = commands.add_parser(
        'off', aliases=['clear'], description=do_off.__doc__,
        help=do_off.__doc__)
    off_cmd.set_defaults(func=do_off)

    on_cmd = commands.add_parser(
        'on', aliases=['all'], description=do_on.__doc__,
        help=do_on.__doc__)
    on_cmd.add_argument(
        'color', type=Color,
        help="The color to set all LEDs to; may be given as a common CSS3 "
        "color name, or an HTML color code, i.e. #RRGGBB")
    on_cmd.set_defaults(func=do_on)

    set_cmd = commands.add_parser(
        'set', description=do_set.__doc__,
        help=do_set.__doc__)
    set_cmd.add_argument(
        'number', type=int,
        help="The number of the LED (from 1 to the number of LEDs) to light")
    set_cmd.add_argument(
        'color', type=Color,
        help="The color to set the LEDs to; may be given as a common CSS3 "
        "color name, or an HTML color code, i.e. #RRGGBB")
    set_cmd.set_defaults(func=do_set)

    list_cmd = commands.add_parser(
        'list', aliases=['ls'], description=do_list.__doc__,
        help="List all presets")
    list_cmd.set_defaults(func=do_list)

    show_cmd = commands.add_parser(
        'show', aliases=['load'], description=do_show.__doc__,
        help="Show a preset")
    show_cmd.add_argument(
        'preset',
        help="The name of the preset to load; if the preset contains spaces "
        "it will need quoting on the command line")
    show_cmd.set_defaults(func=do_show)

    parser.set_defaults_from(config)
    return parser


def do_help(config, queue):
    """
    With no arguments, display the list of sub-commands. If a command name is
    given, display the description and options for that command
    """
    parser = get_cli_parser()
    if 'cmd' in config and config.cmd is not None:
        parser.parse_args([config.cmd, '-h'])
    else:
        parser.parse_args(['-h'])


def do_off(config, queue):
    "Switch all LEDs off"
    queue.put([[]])


def do_on(config, queue):
    "Switch all LEDs on with the specified color"
    queue.put([[config.color.html] * config.led_count])


def do_set(config, queue):
    "Switch on a single LED to the specified color"
    black = Color('black')
    queue.put([[
        config.color.html if number == config.number else black
        for number in range(1, config.led_count + 1)
    ]])


def do_list(config, queue):
    "List the names of all available presets"
    store = Storage(config.db)
    for preset in store.presets:
        print(preset)


def do_show(config, queue):
    "Load and display the specified preset"
    store = Storage(config.db)
    queue.put(store.presets[config.preset])


def main(args=None):
    "Entry point for :program:`bxcli`"
    try:
        config = get_cli_parser().parse_args(args)
        if config.led_count == 0:
            raise RuntimeError(
                'No LED strips defined; please edit the configuration file')
        queue = Queue()
        with mqtt.MessageThread(queue, config) as message_task:
            config.func(config, queue)
            queue.join()
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
