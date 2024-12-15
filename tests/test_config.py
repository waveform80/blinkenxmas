import sys
from pathlib import Path
from configparser import ConfigParser
from contextlib import suppress
from textwrap import dedent
from unittest import mock

import pytest

from blinkenxmas.config import *


def test_configargparser_set_defaults_from():
    parser = ConfigArgumentParser()
    group_section = parser.add_argument_group('group', section='group')
    group_section.add_argument(
        '--number', key='number', type=int, help="A number")
    config = ConfigParser()
    config.read_string("""
[group]
number=-1
""")
    parser.set_defaults_from(config)
    assert parser.get_default('number') == '-1'
    assert parser.parse_args([]).number == -1


def test_configargparser_update_config():
    parser = ConfigArgumentParser()
    group_section = parser.add_argument_group('group', section='group')
    group_section.add_argument(
        '--number', key='number', type=int, help="A number")
    config = ConfigParser()
    config.read_string("""
[group]
number=-1
""")
    parser.set_defaults_from(config)
    assert parser.get_default('number') == '-1'
    namespace = parser.parse_args(['--number', '10'])
    assert namespace.number == 10
    parser.update_config(config, namespace)
    assert config['group']['number'] == '10'


def test_configargparser_of_type():
    parser = ConfigArgumentParser()
    paths_section = parser.add_argument_group('paths', section='paths')
    paths_section.add_argument(
        '--input', key='input', type=Path, help="An input path")
    paths_section.add_argument(
        '--output', key='output', type=Path, help="An output path")
    paths_section.add_argument(
        '--overwrite', action='store_true', key='overwrite',
        help="If true, overwrite output without prompting")
    assert parser.of_type(Path) == {
        ('paths', 'input'),
        ('paths', 'output'),
    }


def test_configargparser_bad_arg():
    parser = ConfigArgumentParser()
    with pytest.raises(ValueError):
        parser.add_argument('--number', key='number', type=int)


def test_configargparser_handles_bools():
    parser = ConfigArgumentParser()
    parser.add_argument('--verbose', action='store_true', section='log',
                        key='verbose')
    config = ConfigParser()
    config.read_string("""
[log]
verbose=no
""")
    parser.set_defaults_from(config)
    assert not parser.get_default('verbose')
    assert not parser.parse_args([]).verbose
    assert parser.parse_args(['--verbose']).verbose


def test_configargparser_bad_grouped_opts():
    parser = ConfigArgumentParser()
    parser.add_argument('--sensor', action='store_true', section='devices',
                        key='sensor')
    with pytest.raises(ValueError):
        parser.add_argument('--no-sensor', dest='sensor', action='store_false',
                            section='devices', key='no_sensor')


def test_port():
    with mock.patch('blinkenxmas.config.socket') as socket:
        def myget(s):
            try:
                return {
                    'http': 80,
                    'https': 443,
                    'ftp': 21,
                }[s]
            except KeyError:
                raise OSError(f'unknown service {s}')
        socket.getservbyname = myget
        assert port('8000') == 8000
        assert port('http') == 80
        with pytest.raises(ValueError):
            port('ssh')


def test_boolean():
    assert boolean('no') is False
    assert boolean(' FALSE ') is False
    assert boolean('  Yes') is True
    assert boolean(1) is True
    assert boolean('0') is False
    with pytest.raises(ValueError):
        boolean('foo')


def test_get_parser(capsys):
    config = get_config()
    parser = get_parser(config, description="Foo!")
    with suppress(SystemExit):
        parser.parse_args(['--help'])
    help_text = capsys.readouterr()
    assert 'Foo!' in help_text.out
    assert '--help' in help_text.out
    assert '--version' in help_text.out


def test_get_config():
    ignore = {p.expanduser().resolve() for p in CONFIG_LOCATIONS}
    def no_system_config(filename, mode='r', **kwargs):
        if filename.resolve() in ignore:
            raise FileNotFoundError(filename)
        return open(filename, mode, **kwargs)
    with mock.patch('configparser.open', no_system_config):
        config = get_config()
        assert set(config.sections()) == {
            'mqtt',
            'web',
            'wifi',
            'pico',
            'camera',
        }


def test_get_config_path_resolution(tmp_path):
    mock_conf = tmp_path / 'blinkenxmas.conf'
    (tmp_path / 'videos').mkdir()
    with mock.patch('blinkenxmas.config.CONFIG_LOCATIONS', [mock_conf]):
        mock_conf.write_text(dedent("""
            [web]
            port = 8000
            database = presets.db
            """))
        config = get_config()
        assert config['web']['database'] == str(tmp_path / 'presets.db')


def test_get_bad_config(tmp_path):
    mock_conf = tmp_path / 'blinkenxmas.conf'
    with mock.patch('blinkenxmas.config.CONFIG_LOCATIONS', [mock_conf]):
        mock_conf.write_text(dedent("""
            [bad_section]
            path = ~/videos
            """))
        with pytest.raises(ValueError):
            get_config()
        mock_conf.write_text(dedent("""
            [web]
            bad_key = http://foo.bar
            """))
        with pytest.raises(ValueError):
            get_config()
