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
from collections import namedtuple
from html.parser import HTMLParser
from http.client import HTTPConnection

import pytest

from blinkenxmas.httpd import HTTPThread, HTTPRequestHandler
# This import is required to register the default routes
from blinkenxmas import routes


@pytest.fixture()
def config(request, tmp_path):
    result = argparse.Namespace()

    result.db = str(tmp_path / '/presets.db')
    result.production = False
    result.broker_adddress = 'broker'
    result.broker_port = 1883
    result.topic = 'blinkenxmas'

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
    def factory(config, messages=None, preview=None, recordings=None,
                recorder=None):
        if messages is None:
            messages = mock.Mock()
        return HTTPThread(
            config, messages=messages, preview=preview,
            recordings=recordings, recorder=recorder)
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

def find(pattern, content):
    for seq in window(content, len(pattern)):
        if seq == pattern:
            return True
    return False
