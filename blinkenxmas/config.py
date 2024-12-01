import os
import socket
from pathlib import Path
from fnmatch import fnmatchcase
from itertools import accumulate, chain
from argparse import ArgumentParser, SUPPRESS
from configparser import ConfigParser

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


# The locations to attempt to read the configuration from
XDG_CONFIG_HOME = Path(os.environ.get('XDG_CONFIG_HOME', '~/.config'))
CONFIG_LOCATIONS = (
    Path('/usr/local/etc/blinkenxmas.conf'),
    Path('/etc/blinkenxmas.conf'),
    Path(XDG_CONFIG_HOME / 'blinkenxmas.conf'),
)

# The set of keys within the configuration that represent paths and thus need
# to be resolved relative to the configuration file they were read from
CONFIG_PATHS = {
    # section,  key
    ('web',    'database'),
    ('camera', 'path'),
    ('camera', 'device'),
}


class ConfigArgumentParser(ArgumentParser):
    """
    A variant of :class:`~argparse.ArgumentParser` that links arguments to
    specified keys in a :class:`~configparser.ConfigParser` instance.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._config_map = {}

    def add_argument(self, *args, section=None, key=None, **kwargs):
        """
        Adds *section* and *key* parameters. These link the new argument to the
        specified configuration entry.

        The default for the argument can be specified directly as usual, or
        can be read from the configuration (see :meth:`set_defaults`). When
        arguments are parsed, the value assigned to this argument will be
        copied to the associated configuration entry.
        """
        if (section is None) != (key is None):
            raise ValueError('section and key must be specified together')
        action = super().add_argument(*args, **kwargs)
        if key is not None:
            self._config_map[action.dest] = (section, key)
        return action

    def set_defaults_from(self, config):
        """
        Sets defaults for all arguments from their associated configuration
        entries in *config*.
        """
        kwargs = {
            dest: config[section][key]
            for dest, (section, key) in self._config_map.items()
            if section in config
            and key in config[section]
        }
        return super().set_defaults(**kwargs)

    def update_config(self, config, namespace):
        """
        Copy values from *namespace* (presumably the result of calling
        something like :meth:`~argparse.ArgumentParser.parse_args`) to
        *config*. Note that namespace values will be converted to :class:`str`
        implicitly.
        """
        for dest, (section, key) in self._config_map.items():
            self._config[section][key] = str(getattr(namespace, dest))


def resolution(s):
    """
    Convert the string *s* into a tuple of (width, height).
    """
    width, height = (int(i) for i in s.lower().split('x', 1))
    return width, height


def rotation(s):
    """
    Convert the string *s* into a rotation in degrees. Values which are not
    multiples of 90 are rejected with :exc:`ValueError`.
    """
    r = int(s) % 360
    if r not in (0, 90, 180, 270):
        raise ValueError(f'invalid rotation {s}; must be multiple of 90')
    return r


def strips(s):
    """
    Convert the :class:`str` *s*, which must contain a comma-separated list of
    integers, into an iterable of :class:`range` objects, each containing a
    number of elements specified by the input string. For example:

        >>> list(strips('1,2,3'))
        [range(0, 2), range(1, 3), range(3, 6)]
        >>> list(strips('50,100'))
        [range(0, 50), range(50, 150)]
    """
    start = 0
    for count in map(int, s.split(',')):
        yield range(start, start + count)
        start += count


def port(s):
    """
    Convert the :class:`str` *s* into a port number. *s* may contain an integer
    representation (in which case the conversion is trivial), or a :class:`str`
    containing a registered port name, in which case ``getservbyname`` will be
    used to convert it to a port number (usually via NSS).
    """
    try:
        return int(s)
    except ValueError:
        try:
            return socket.getservbyname(s)
        except OSError:
            raise ValueError(f'invalid service name or port number: {s}')


def get_parser(config, **kwargs):
    parser = ConfigArgumentParser(**kwargs)
    parser.add_argument(
        '--version', action='version', version=version('blinkenxmas'))
    parser.add_argument(
        '--db', metavar='FILE',
        section='web', key='database',
        help="the SQLite database to store presets in. Default: %(default)s")
    parser.add_argument(
        '--no-production', dest='production', section='web', key='production',
        action='store_false')
    parser.add_argument(
        '--production', section='web', key='production', action='store_true',
        help="If specified, run in production mode where an internal server "
        "error will not terminate the server and will not output a stack "
        "trace (default: no)")
    parser.add_argument(
        '--broker-address', section='mqtt', key='host', metavar='ADDR',
        help="the address on which to find the MQTT broker. Default: "
        "%(default)s")
    parser.add_argument(
        '--broker-port', section='mqtt', key='port',
        type=port, metavar='ADDR',
        help="the address on which to find the MQTT broker. Default: "
        "%(default)s")
    parser.add_argument(
        '--topic', section='mqtt', key='topic',
        help="the topic on which the Pico W is listening for messages. "
        "Default: %(default)s")

    # Internal use arguments
    led_sections = [s for s in config if s.startswith('leds:')]
    strip_counts = [int(config[s]['count']) for s in led_sections]
    parser.add_argument(
        '--led-strips', metavar='NUM,NUM,...', type=strips, default=[
            range(start, start + count)
            for start, count
            in zip(accumulate(chain([0], strip_counts)), strip_counts)
        ],
        help=SUPPRESS)
    parser.add_argument(
        '--led-count', metavar='NUM', type=int,
        default=sum(strip_counts, start=0),
        help=SUPPRESS)
    parser.add_argument(
        '--fps', metavar='NUM', type=int, default=min((
            int(config[section].get('fps', 60))
            for section in config
            if section.startswith('leds:')
        ), default=60),
        help=SUPPRESS)

    return parser


def get_config():
    # Load the default configuration from the project resources, defining the
    # valid sections and keys from the default (amalgamating the example leds
    # sections into a template "leds:*" section)
    config = ConfigParser(
        delimiters=('=',), empty_lines_in_values=False, interpolation=None,
        converters={'list': lambda s: s.strip().splitlines()}, strict=False)
    with resources.path('blinkenxmas', 'default.conf') as default_conf:
        config.read(default_conf)
    valid = {config.default_section: set()}
    for section, keys in config.items():
        for key in keys:
            valid.setdefault(
                'leds:*' if section.startswith('leds:') else section,
                set()
            ).add(key)
    for section in {s for s in config if s.startswith('leds:')}:
        del config[section]

    # Attempt to load each of the pre-defined locations for the "main"
    # configuration, validating sections and keys against the default template
    # loaded above
    for path in CONFIG_LOCATIONS:
        path = path.expanduser()
        config.read(path)
        for section, keys in config.items():
            try:
                section = {s for s in valid if fnmatchcase(section, s)}.pop()
            except KeyError:
                raise ValueError(
                    f'{path}: invalid section [{section}]')
            for key in set(keys) - valid[section]:
                raise ValueError(
                    f'{path}: invalid key {key} in [{section}]')
        # Resolve paths relative to the configuration file just loaded
        for section, key in CONFIG_PATHS:
            if key in config[section]:
                value = Path(config[section][key]).expanduser()
                if not value.is_absolute():
                    value = (path.parent / value).resolve()
                config[section][key] = str(value)
    return config


def get_pico_config(config):
    leds = [
        (
            config[section]['driver'],
            int(config[section]['count']),
            int(config[section].get('reversed', 'no') == 'yes'),
            config[section]['order'],
        ) + (
            (int(config[section]['pin']),)
            if config[section]['driver'] == 'WS2812' else
            (int(config[section]['clk']), int(config[section]['dat']))
        )
        for section in config
        if section.startswith('leds:')
    ]
    return f"""\
from mqtt_as import config

# WiFi configuration
config['ssid'] = {config['wifi']['ssid']!r}
config['wifi_pw'] = {config['wifi']['password']!r}

# MQTT broker configuration
config['server'] = {config['mqtt']['host']!r}
config['topic'] = {config['mqtt']['topic']!r}

# Configuration of the LEDs
config['fps'] = {
    min(int(config[section].get('fps', 60))
    for section in config
    if section.startswith('leds:'))
}
config['leds'] = {leds!r}

# Error handling and status reporting
config['status'] = {
    int(config['pico']['status'])
    if config['pico'].get('status', 'LED').isdigit() else
    config['pico']['status']
!r}
config['error'] = {config['pico']['error']!r}
"""
