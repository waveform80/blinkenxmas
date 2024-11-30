import json
import socket
import email.utils as eut
from http import HTTPStatus
from http.client import RemoteDisconnected
from unittest import mock

import pytest

from blinkenxmas.httpd import *
from conftest import split, find


def test_get_best_family():
    assert get_best_family('127.0.0.1', 8000) == (
        socket.AF_INET, ('127.0.0.1', 8000))
    with mock.patch('blinkenxmas.httpd.socket.getaddrinfo') as getaddrinfo:
        getaddrinfo.side_effect = socket.gaierror('Name or service not known')
        with pytest.raises(ValueError):
            get_best_family('foo', 8000)
        getaddrinfo.side_effect = None
        getaddrinfo.return_value = []
        with pytest.raises(ValueError):
            get_best_family('foo', 8000)


def test_httpd_exception(config, server_factory, no_routes):
    server = server_factory(config)
    server.httpd.socket = mock.Mock(server.httpd.socket, autospec=True)
    server.httpd.socket.getsockname.side_effect = socket.gaierror()
    with pytest.raises(socket.gaierror):
        with server:
            pass


def test_static_HEAD(config, server_factory, no_routes, client_factory):
    style_css = resources.files('blinkenxmas') / 'style.css'
    with server_factory(config) as server:
        client = client_factory(server)
        client.request('HEAD', '/style.css')
        resp = client.getresponse()
        assert resp.status == 200
        assert resp.read() == b''
        assert 'immutable' in resp.headers['Cache-Control']
        assert resp.headers['Content-Type'] == 'text/css'
        assert int(resp.headers['Content-Length']) == style_css.stat().st_size


def test_static_GET(config, server_factory, no_routes, client_factory):
    style_css = resources.files('blinkenxmas') / 'style.css'
    expected = style_css.read_bytes()
    with server_factory(config) as server:
        client = client_factory(server)
        client.request('GET', '/style.css')
        resp = client.getresponse()
        assert resp.status == 200
        assert resp.read() == expected
        assert 'immutable' in resp.headers['Cache-Control']
        assert resp.headers['Content-Type'] == 'text/css'
        assert int(resp.headers['Content-Length']) == len(expected)


def test_static_GET_cached(config, server_factory, no_routes, client_factory):
    style_css = resources.files('blinkenxmas') / 'style.css'
    expected = style_css.read_bytes()
    with server_factory(config) as server:
        client = client_factory(server)
        client.request('GET', '/style.css', headers={
            'If-Modified-Since': eut.format_datetime(
                HTTPRequestHandler.static_modified)})
        resp = client.getresponse()
        assert resp.status == 304
        assert resp.read() == b''
        assert resp.headers['Content-Type'] == 'text/css'


def test_static_ignores_POST(config, server_factory, no_routes, client_factory):
    style_css = resources.files('blinkenxmas') / 'style.css'
    expected = style_css.read_bytes()
    with server_factory(config) as server:
        client = client_factory(server)
        client.request('POST', '/style.css', headers={
            'Content-Type': 'application/x-www-form-urlencoded'})
        resp = client.getresponse()
        assert not resp.read()
        assert resp.status == 404


def test_static_bad_POST(config, server_factory, no_routes, client_factory):
    style_css = resources.files('blinkenxmas') / 'style.css'
    expected = style_css.read_bytes()
    with server_factory(config) as server:
        client = client_factory(server)
        client.request('POST', '/style.css', headers={
            'Content-Type': 'application/json'})
        resp = client.getresponse()
        assert not resp.read()
        assert resp.status == 400


def test_static_not_found(config, server_factory, no_routes, client_factory):
    with server_factory(config) as server:
        client = client_factory(server)
        client.request('GET', '/i-dont-exist.css')
        resp = client.getresponse()
        assert not resp.read()
        assert resp.status == 404


def test_template_HEAD(config, server_factory, no_routes, client_factory):
    with server_factory(config) as server:
        client = client_factory(server)
        client.request('HEAD', '/index.html')
        resp = client.getresponse()
        assert resp.status == 200
        assert resp.read() == b''
        assert 'immutable' not in resp.headers['Cache-Control']
        assert resp.headers['Content-Type'] == 'text/html'


def test_template_GET_empty_index(config, server_factory, no_routes,
                                  client_factory):
    with server_factory(config) as server:
        client = client_factory(server)
        client.request('GET', '/index.html')
        resp = client.getresponse()
        body = list(split(resp))
        assert resp.status == 200
        assert 'immutable' not in resp.headers['Cache-Control']
        assert resp.headers['Content-Type'] == 'text/html'
        assert find(('<p>', 'No recordings yet!', '</p>'), body)
        assert not find(('<h2>', 'Recordings', '</h2>'), body)


def test_template_GET_page_2(config, server_factory, no_routes, client_factory,
                             recordings_factory):
    recordings = recordings_factory(30)
    with server_factory(config, recordings=recordings) as server:
        client = client_factory(server)
        client.request('GET', '/index.html?page=2')
        resp = client.getresponse()
        body = list(split(resp))
        assert resp.status == 200
        assert 'immutable' not in resp.headers['Cache-Control']
        assert resp.headers['Content-Type'] == 'text/html'
        assert not find(('<p>', 'No recordings yet!', '</p>'), body)
        assert find(('<h2>', 'Recordings', '</h2>'), body)
        assert find((
            '<ul id="pages">',
            '<li>', 'Pages', '</li>',
            '<li>', '<a href="?page=1">', '1', '</a>', '</li>',
            '<li>', '<a class="selected" href="?page=2">', '2', '</a>', '</li>'
        ), body)


def test_route_HEAD(config, server_factory, no_routes, client_factory):
    with server_factory(config) as server:
        @route('/')
        def home_redir(request):
            return HTTPResponse(
                request, status_code=HTTPStatus.MOVED_PERMANENTLY,
                headers={'Location': '/index.html'})

        client = client_factory(server)
        client.request('GET', '/')
        resp = client.getresponse()
        body = resp.read()
        assert resp.status == 301
        assert resp.headers['Location'] == '/index.html'
        assert body == b''


def test_route_PUT_json(config, server_factory, no_routes, client_factory):
    with server_factory(config) as server:
        data = None

        @route('/config.json', 'PUT')
        def configure(request):
            nonlocal data
            data = request.json()
            return HTTPResponse(request, status_code=HTTPStatus.NO_CONTENT)

        expected = {'foo': 1, 'bar': 2}
        client = client_factory(server)
        client.request('PUT', '/config.json',
                       body=json.dumps(expected),
                       headers={'Content-Type': 'application/json'})
        resp = client.getresponse()
        body = resp.read()
        assert resp.status == 204
        assert body == b''
        assert data == expected


def test_route_DELETE(config, server_factory, no_routes, client_factory):
    with server_factory(config) as server:
        @route('/to-delete', 'DELETE')
        def configure(request):
            return HTTPResponse(request, status_code=HTTPStatus.NO_CONTENT)

        client = client_factory(server)
        client.request('DELETE', '/to-delete')
        resp = client.getresponse()
        body = resp.read()
        assert resp.status == 204
        assert body == b''


def test_route_PUT_json_bad_len(config, server_factory, no_routes,
                                client_factory):
    with server_factory(config) as server:
        data = None

        @route('/config.json', 'PUT')
        def configure(request):
            nonlocal data
            try:
                data = request.json()
                return HTTPResponse(request, status_code=HTTPStatus.NO_CONTENT)
            except ValueError:
                return HTTPResponse(request, status_code=HTTPStatus.BAD_REQUEST)

        expected = {'foo': 1, 'bar': 2}
        client = client_factory(server)
        # NOTE: not sending Content-Length
        client.putrequest('PUT', '/config.json')
        client.putheader('Content-Type', 'application/json')
        client.endheaders()
        client.send(json.dumps(expected).encode('utf-8'))
        resp = client.getresponse()
        body = resp.read()
        assert resp.status == 400
        assert body == b''
        assert data is None


def test_route_broken_in_production(config, server_factory, no_routes,
                                    client_factory):
    config.production = True
    with server_factory(config) as server:
        @route('/')
        def home_redir(request):
            return HTTPResponse(
                request, status_code=HTTPStatus.MOVED_PERMANENTLY,
                headers={'Location': '/index.html'})

        @route('/broken.html')
        def broken_route(request):
            raise TypeError('This route is broken!')

        client = client_factory(server)
        client.request('GET', '/broken.html')
        resp = client.getresponse()
        body = resp.read()
        assert resp.status == 500
        assert 'Location' not in resp.headers
        assert body == b''
        assert not server.join(0)


def test_route_broken_in_development(config, server_factory, no_routes,
                                     client_factory):
    config.production = False

    class BrokenRoute(Exception):
        pass

    with pytest.raises(BrokenRoute):
        with server_factory(config) as server:
            @route('/')
            def home_redir(request):
                return HTTPResponse(
                    request, status_code=HTTPStatus.MOVED_PERMANENTLY,
                    headers={'Location': '/index.html'})

            @route('/broken.html')
            def broken_route(request):
                raise BrokenRoute('This route is broken!')

            client = client_factory(server)
            client.request('GET', '/broken.html')
            with pytest.raises(RemoteDisconnected):
                client.getresponse()
            server.join(1)
            assert not server.is_alive()


def test_route_fallthru(config, server_factory, client_factory, no_routes):
    config.production = True
    with server_factory(config) as server:
        @route('/broken.html')
        def broken_route(request):
            return None

        client = client_factory(server)
        client.request('GET', '/broken.html')
        resp = client.getresponse()
        assert not resp.read()
        assert resp.status == 404
