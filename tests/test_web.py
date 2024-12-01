from unittest import mock

import pytest

from blinkenxmas.httpd import Messages
from blinkenxmas.web import *


@pytest.fixture()
def dummy_args(request):
    return ['--camera-type', 'none',
            '--camera-capture', '640x480',
            '--led-strips', '50,100',
            '--led-count', '150',
            '--fps', '60']


def test_messages():
    messages = Messages(maxlen=5)
    messages.show('foo')
    messages.show('bar')
    assert messages.drain() == ['foo', 'bar']
    for i in range(10):
        messages.show(str(i))
    assert messages.drain() == [str(i) for i in range(5, 10)]


def test_main_help(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(['-h'])
    assert exc_info.value.args[0] == 0  # return code 0
    captured = capsys.readouterr()
    assert captured.out.lstrip().startswith('usage: ')


def test_main_sigint(dummy_args):
    with mock.patch('blinkenxmas.httpd.HTTPThread') as HTTPThread:
        HTTPThread().__enter__().join.side_effect = KeyboardInterrupt()
        assert main(dummy_args) == 2


def test_main_bad_config(dummy_args):
    with pytest.raises(SystemExit):
        assert main(dummy_args + ['--when', 'on-sensor']) == 1
    with pytest.raises(SystemExit):
        assert main(dummy_args + ['--gpio-record-on-sensor', 'GPIO2']) == 1
    with pytest.raises(SystemExit):
        assert main(dummy_args + ['--lead-duration', '10s',
                                  '--min-duration', '10s',
                                  '--max-duration', '10s']) == 1
