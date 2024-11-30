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
    with mock.patch('hamstercam.config.socket') as socket:
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


def test_duration():
    assert duration('1d, 6h') == relativedelta(days=1, hours=6)
    assert duration('1 month') == relativedelta(months=1)
    assert duration('1hr 30mins 5secs') == relativedelta(hours=1, minutes=30, seconds=5)
    assert duration('1yr, 1m, 1wk, 1d, 1hr, 1mi, 1s, 1ms, 1us') == relativedelta(years=1, months=1, days=8, hours=1, minutes=1, seconds=1, microseconds=1001)
    with pytest.raises(ValueError):
        duration('foo')


def test_disk_space():
    assert disk_space('25%') == 0.25
    assert disk_space('1MB') == 1000000
    assert disk_space('12345678') == 12345678
    assert disk_space('123B') == 123
    with pytest.raises(ValueError):
        disk_space('foo')
    with pytest.raises(ValueError):
        disk_space('250%')
    with pytest.raises(ValueError):
        disk_space('-1MB')


def test_schedule():
    assert schedule('') == {
        (weekday, hour): Recorder.on_motion
        for weekday in range(1, 8)
        for hour in range(24)
    }
    assert schedule('* * on-motion') == {
        (weekday, hour): Recorder.on_motion
        for weekday in range(1, 8)
        for hour in range(24)
    }
    assert schedule('* * on-motion, * 09-10 always, Sat-Sun * never') == {
        (weekday, hour):
            Recorder.never if 6 <= weekday <= 7 else
            Recorder.always if 9 <= hour <= 10 else
            Recorder.on_motion
        for weekday in range(1, 8)
        for hour in range(24)
    }
    assert schedule(['* * on-motion', '* 9 always', 'Sat * never']) == {
        (weekday, hour):
            Recorder.never if weekday == 6 else
            Recorder.always if hour == 9 else
            Recorder.on_motion
        for weekday in range(1, 8)
        for hour in range(24)
    }
    assert schedule("""
        * * on-motion
        Mon-Fri 9-17 never
        """) == {
        (weekday, hour):
            Recorder.never if 1 <= weekday <= 5 and 9 <= hour <= 17 else
            Recorder.on_motion
        for weekday in range(1, 8)
        for hour in range(24)
    }


def test_get_parser(capsys):
    parser = get_parser(description="Foo!")
    with suppress(SystemExit):
        parser.parse_args(['--help'])
    help_text = capsys.readouterr()
    assert 'Foo!' in help_text.out
    assert '--help' in help_text.out
    assert '--version' in help_text.out


def test_get_config():
    config = get_config()
    assert set(config.sections()) == {
        'camera',
        'gpio',
        'motion',
        'recordings',
        'storage',
        'web',
    }


def test_get_config_path_resolution(tmp_path):
    mock_conf = tmp_path / 'hamstercam.conf'
    (tmp_path / 'videos').mkdir()
    with mock.patch('hamstercam.config.CONFIG_LOCATIONS', [mock_conf]):
        mock_conf.write_text(dedent("""
            [storage]
            min_free = 10%
            path = videos
            """))
        config = get_config()
        assert config['storage']['path'] == str(tmp_path / 'videos')


def test_get_bad_config(tmp_path):
    mock_conf = tmp_path / 'hamstercam.conf'
    with mock.patch('hamstercam.config.CONFIG_LOCATIONS', [mock_conf]):
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
