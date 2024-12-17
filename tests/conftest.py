import io
import json
import random
import select
import argparse
import datetime as dt
from pathlib import Path
from unittest import mock
from functools import wraps
from queue import Queue, Empty
from collections import namedtuple, deque
from html.parser import HTMLParser
from http.client import HTTPConnection

import pytest

from blinkenxmas.httpd import HTTPThread, HTTPRequestHandler
# This import is required to register the default routes
from blinkenxmas import routes


@pytest.fixture()
def config(request):
    result = argparse.Namespace()

    result.broker_adddress = 'broker'
    result.broker_port = 1883
    result.topic = 'blinkenxmas'

    result.led_strips = [range(0, 50), range(50, 100), range(100, 150)]
    result.led_count = 150
    result.fps = 60

    return result


@pytest.fixture()
def web_config(request, config, tmp_path):
    result = config

    result.httpd_bind = '127.0.0.1'
    result.httpd_port = 0
    result.production = False
    result.db = str(tmp_path / 'presets.db')
    result.docs = 'https://blinkenxmas.readthedocs.io/'
    result.source = 'https://github.com/waveform80/blinkenxmas/'

    result.camera_type = 'none'
    result.camera_path = str(tmp_path)
    result.camera_device = '/dev/video0'
    result.camera_capture = (960, 720)
    result.camera_preview = (640, 480)
    result.camera_rotation = 0

    return result


@pytest.fixture()
def default_routes(request):
    # Restore a saved copy of the default routes in case a prior
    # test messed with them
    HTTPRequestHandler.routes = _default_routes.copy()
    return HTTPRequestHandler.routes
_default_routes = HTTPRequestHandler.routes.copy()


@pytest.fixture()
def no_routes(request):
    # Clear the routes table; if default_routes is False then routes
    # must be registered *after* server construction
    HTTPRequestHandler.routes.clear()
    return HTTPRequestHandler.routes


@pytest.fixture()
def server_factory(request):
    def factory(config, messages=None, queue=None):
        if messages is None:
            messages = mock.Mock()
            messages.drain.return_value = []
        if queue is None:
            queue = mock.Mock()
        return HTTPThread(config, messages, queue)
    return factory


@pytest.fixture()
def client_factory(request):
    def factory(server, timeout=10):
        host, port = server.httpd.socket.getsockname()[:2]
        return HTTPConnection(host, port, timeout=timeout)
    return factory


class HTMLSplitter(HTMLParser):
    def __init__(self):
        super().__init__()
        self.queue = Queue()

    def handle_starttag(self, tag, attrs):
        attrs_str = ''.join(
            f' {key}="{value}"'
            for key, value in sorted(attrs)
        )
        self.queue.put(f'<{tag}{attrs_str}>')

    def handle_endtag(self, tag):
        self.queue.put(f'</{tag}>')

    def handle_startendtag(self, tag, attrs):
        attrs_str = ''.join(
            f' {key}="{value}"'
            for key, value in sorted(attrs)
        )
        self.queue.put(f'<{tag}{attrs_str}/>')

    def handle_data(self, data):
        data = data.strip()
        if data:
            self.queue.put(data)

def split(stream):
    if isinstance(stream, str):
        stream = io.BytesIO(stream)
    if not isinstance(stream, io.TextIOBase):
        stream = io.TextIOWrapper(stream, encoding='utf-8')
    parser = HTMLSplitter()
    while True:
        buf = stream.read(select.PIPE_BUF)
        if not buf:
            break
        parser.feed(buf)
        while True:
            try:
                yield parser.queue.get(block=False)
            except Empty:
                break

def window(it, n):
    d = deque(maxlen=n)
    for item in it:
        d.append(item)
        if len(d) == n:
            yield tuple(d)

def find(pattern, content):
    for seq in window(content, len(pattern)):
        if seq == pattern:
            return True
    return False
