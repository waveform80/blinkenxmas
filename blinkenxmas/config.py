import os
from pathlib import Path
from string import Template
from configparser import ConfigParser
from argparse import ArgumentParser, SUPPRESS

# NOTE: The fallback comes first here as Python 3.7 incorporates
# importlib.resources but at a version incompatible with our requirements.
# Ultimately the try clause should be removed in favour of the except clause
# once compatibility moves beyond Python 3.9
try:
    import importlib_resources as resources
except ImportError:
    from importlib import resources

# NOTE: Remove except when compatibility moves beyond Python 3.8
try:
    from importlib.metadata import version
except ImportError:
    from importlib_metadata import version


XDG_CONFIG_HOME = Path(os.environ.get('XDG_CONFIG_HOME', '~/.config'))
CONFIG_LOCATIONS = (
    Path('/etc/blinkenxmas.conf'),
    Path(XDG_CONFIG_HOME / 'blinkenxmas.conf'),
    Path('~/.blinkenxmas.conf'),
)


def get_port(service):
    try:
        return int(service)
    except ValueError:
        try:
            return socket.getservbyname(service)
        except OSError:
            raise ValueError('invalid service name or port number')


def get_config_and_parser(*, description):
    config = read_config()

    parser = ArgumentParser(description=description)
    parser.add_argument(
        '--version', action='version', version=version('blinkenxmas'))
    parser.add_argument(
        '--db', metavar='FILE', default=config['web']['database'],
        help="the SQLite database to store presets in. Default: %(default)s")
    parser.add_argument(
        '--broker-address', metavar='ADDR',
        default=config['mqtt']['host'],
        help="the address on which to find the MQTT broker. Default: "
        "%(default)s")
    parser.add_argument(
        '--broker-port', metavar='ADDR', type=get_port,
        default=config['mqtt']['port'],
        help="the address on which to find the MQTT broker. Default: "
        "%(default)s")
    parser.add_argument(
        '--topic', default=config['mqtt']['topic'],
        help="the topic on which the Pico W is listening for messages. "
        "Default: %(default)s")

    # Internal use arguments
    parser.add_argument(
        '--led-count', metavar='NUM', type=int, default=sum(
            int(config[section]['count'])
            for section in config
            if section.startswith('leds:')
        ),
        help=SUPPRESS)
    parser.add_argument(
        '--fps', metavar='NUM', type=int, default=min(
            int(config[section].get('fps', 60))
            for section in config
            if section.startswith('leds:')
        ),
        help=SUPPRESS)

    return config, parser


def read_config():
    config = ConfigParser(
        delimiters=('=',), empty_lines_in_values=False, interpolation=None,
        converters={'list': lambda s: s.strip().splitlines()})
    with resources.path('blinkenxmas', 'default.conf') as default_conf:
        config.read(default_conf)
    for path in CONFIG_LOCATIONS:
        path = path.expanduser()
        config.read(path)
        if not Path(config['web']['database']).is_absolute():
            db_path = (path.parent / Path(config['web']['database']))
            db_path = db_path.expanduser().resolve()
            config['web']['database'] = str(db_path)

    return config


def generate_pico_config(config):
    pass
