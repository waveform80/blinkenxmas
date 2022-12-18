import os
from pathlib import Path
from string import Template
from fnmatch import fnmatchcase
from argparse import ArgumentParser, SUPPRESS
from configparser import RawConfigParser, ConfigParser

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
    Path('/etc/blinkenxmas.conf'),
    Path(XDG_CONFIG_HOME / 'blinkenxmas.conf'),
    Path('~/.blinkenxmas.conf'),
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


def get_port(service):
    try:
        return int(service)
    except ValueError:
        try:
            return socket.getservbyname(service)
        except OSError:
            raise ValueError('invalid service name or port number')


def get_parser(config, **kwargs):
    parser = ConfigArgumentParser(**kwargs)
    parser.add_argument(
        '--version', action='version', version=version('blinkenxmas'))
    parser.add_argument(
        '--db', metavar='FILE',
        section='web', key='database',
        help="the SQLite database to store presets in. Default: %(default)s")
    parser.add_argument(
        '--broker-address', section='mqtt', key='host', metavar='ADDR',
        help="the address on which to find the MQTT broker. Default: "
        "%(default)s")
    parser.add_argument(
        '--broker-port', section='mqtt', key='port',
        type=get_port, metavar='ADDR',
        help="the address on which to find the MQTT broker. Default: "
        "%(default)s")
    parser.add_argument(
        '--topic', section='mqtt', key='topic',
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

    return parser


def get_config():
    config = ConfigParser(
        delimiters=('=',), empty_lines_in_values=False, interpolation=None,
        converters={'list': lambda s: s.strip().splitlines()})
    with resources.path('blinkenxmas', 'default.conf') as default_conf:
        config.read(default_conf)
    valid = {config.default_section: set()}
    for section, keys in config.items():
        for key in keys:
            valid.setdefault(
                'leds:*' if section.startswith('leds:') else section,
                set()
            ).add(key)
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
        for section, key in CONFIG_PATHS:
            if key in config[section]:
                value = Path(config[section][key])
                if not value.is_absolute():
                    value = (path.parent / value).expanduser().resolve()
                    config[section][key] = str(value)
    return config


def get_pico_config(config):
    pass
