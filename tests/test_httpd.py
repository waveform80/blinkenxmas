import json
import socket
import email.utils as eut
from http import HTTPStatus
from http.client import RemoteDisconnected
from unittest import mock

import pytest

from blinkenxmas.httpd import *
from colorzero import Color
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


def test_httpd_exception(web_config, server_factory, no_routes):
    server = server_factory(web_config)
    server.httpd.socket = mock.Mock(server.httpd.socket, autospec=True)
    server.httpd.socket.getsockname.side_effect = socket.gaierror()
    with pytest.raises(socket.gaierror):
        with server:
            pass


def test_static_HEAD(web_config, server_factory, no_routes, client_factory):
    style_css = resources.files('blinkenxmas') / 'style.css'
    with server_factory(web_config) as server:
        client = client_factory(server)
        client.request('HEAD', '/style.css')
        resp = client.getresponse()
        assert resp.status == 200
        assert resp.read() == b''
        assert 'max-age' in resp.headers['Cache-Control']
        assert resp.headers['Content-Type'] == 'text/css'
        assert int(resp.headers['Content-Length']) == style_css.stat().st_size


def test_static_GET(web_config, server_factory, no_routes, client_factory):
    style_css = resources.files('blinkenxmas') / 'style.css'
    expected = style_css.read_bytes()
    with server_factory(web_config) as server:
        client = client_factory(server)
        client.request('GET', '/style.css')
        resp = client.getresponse()
        assert resp.status == 200
        assert resp.read() == expected
        assert 'max-age' in resp.headers['Cache-Control']
        assert resp.headers['Content-Type'] == 'text/css'
        assert int(resp.headers['Content-Length']) == len(expected)


def test_static_GET_cached(web_config, server_factory, no_routes, client_factory):
    style_css = resources.files('blinkenxmas') / 'style.css'
    expected = style_css.read_bytes()
    with server_factory(web_config) as server:
        client = client_factory(server)
        client.request('GET', '/style.css', headers={
            'If-Modified-Since': eut.format_datetime(
                HTTPRequestHandler.static_modified)})
        resp = client.getresponse()
        assert resp.status == 304
        assert resp.read() == b''
        assert resp.headers['Content-Type'] == 'text/css'


def test_static_ignores_POST(web_config, server_factory, no_routes, client_factory):
    style_css = resources.files('blinkenxmas') / 'style.css'
    expected = style_css.read_bytes()
    with server_factory(web_config) as server:
        client = client_factory(server)
        client.request('POST', '/style.css', headers={
            'Content-Type': 'application/x-www-form-urlencoded'})
        resp = client.getresponse()
        assert not resp.read()
        assert resp.status == 404


def test_static_bad_POST(web_config, server_factory, no_routes, client_factory):
    style_css = resources.files('blinkenxmas') / 'style.css'
    expected = style_css.read_bytes()
    with server_factory(web_config) as server:
        client = client_factory(server)
        client.request('POST', '/style.css', headers={
            'Content-Type': 'application/binary'})
        resp = client.getresponse()
        assert not resp.read()
        assert resp.status == 400


def test_static_not_found(web_config, server_factory, no_routes, client_factory):
    with server_factory(web_config) as server:
        client = client_factory(server)
        client.request('GET', '/i-dont-exist.css')
        resp = client.getresponse()
        assert not resp.read()
        assert resp.status == 404


def test_template_HEAD(web_config, server_factory, no_routes, client_factory):
    with server_factory(web_config) as server:
        client = client_factory(server)
        client.request('HEAD', '/index.html')
        resp = client.getresponse()
        assert resp.status == 200
        assert resp.read() == b''
        assert 'max-age' not in resp.headers['Cache-Control']
        assert resp.headers['Content-Type'] == 'text/html'


def test_template_GET_empty_index(web_config, server_factory, no_routes,
                                  client_factory):
    with server_factory(web_config) as server:
        client = client_factory(server)
        client.request('GET', '/index.html')
        resp = client.getresponse()
        body = list(split(resp))
        assert resp.status == 200
        assert 'max-age' not in resp.headers['Cache-Control']
        assert resp.headers['Content-Type'] == 'text/html'
        assert find(('<p>', 'No presets defined yet!', '</p>'), body)
        assert not find(('<p>', 'Select from one of the following presets:', '</p>'), body)


def test_route_HEAD(web_config, server_factory, no_routes, client_factory):
    with server_factory(web_config) as server:
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


def test_route_GET_no_params(web_config, server_factory, no_routes,
                             client_factory):
    with server_factory(web_config) as server:
        data = None

        @route('/')
        def home_redir(request):
            nonlocal data
            data = request.query
            return HTTPResponse(
                request, status_code=HTTPStatus.MOVED_PERMANENTLY,
                headers={'Location': '/index.html'})

        client = client_factory(server)
        client.request('GET', '/')
        resp = client.getresponse()
        assert resp.status == 301
        assert data == {}


def test_route_GET_params(web_config, server_factory, no_routes,
                          client_factory):
    with server_factory(web_config) as server:
        data = None

        @route('/')
        def home_redir(request):
            nonlocal data
            data = request.query
            return HTTPResponse(
                request, status_code=HTTPStatus.MOVED_PERMANENTLY,
                headers={'Location': '/index.html'})

        client = client_factory(server)
        client.request('GET', '/?foo=bar')
        resp = client.getresponse()
        assert resp.status == 301
        assert data == {'foo': 'bar'}


def test_route_PUT_json(web_config, server_factory, no_routes, client_factory):
    with server_factory(web_config) as server:
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


def test_route_POST_json(web_config, server_factory, no_routes,
                         client_factory):
    with server_factory(web_config) as server:
        data = None

        @route('/config', command='POST')
        def configure(request):
            nonlocal data
            data = request.query
            return HTTPResponse(request, status_code=HTTPStatus.NO_CONTENT)

        expected = {'foo': 1, 'bar': 2}
        client = client_factory(server)
        client.request('POST', '/config',
                       body=json.dumps(expected),
                       headers={'Content-Type': 'application/json'})
        resp = client.getresponse()
        body = resp.read()
        assert resp.status == 204
        assert body == b''
        assert data == expected


def test_route_POST_formdata(web_config, server_factory, no_routes,
                             client_factory):
    with server_factory(web_config) as server:
        data = None

        @route('/config', command='POST')
        def configure(request):
            nonlocal data
            data = request.query.copy()
            return HTTPResponse(request, status_code=HTTPStatus.NO_CONTENT)

        body = """\
--FOO\r
Content-Disposition: form-data; name="foo"\r
\r
1\r
--FOO\r
Content-Disposition: form-data; name="bar"\r
\r
2\r
--FOO--\r
"""
        client = client_factory(server)
        client.request('POST', '/config',
                       body=body,
                       headers={'Content-Type': 'multipart/form-data; boundary=FOO'})
        resp = client.getresponse()
        body = resp.read()
        assert resp.status == 204
        assert body == b''
        assert data == {'foo': '1', 'bar': '2'}


def test_route_DELETE(web_config, server_factory, no_routes, client_factory):
    with server_factory(web_config) as server:
        @route('/to-delete', 'DELETE')
        def configure(request):
            return HTTPResponse(request, status_code=HTTPStatus.NO_CONTENT)

        client = client_factory(server)
        client.request('DELETE', '/to-delete')
        resp = client.getresponse()
        body = resp.read()
        assert resp.status == 204
        assert body == b''


def test_route_PUT_json_bad_len(web_config, server_factory, no_routes,
                                client_factory):
    with server_factory(web_config) as server:
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


def test_route_broken_in_production(web_config, server_factory, no_routes,
                                    client_factory):
    web_config.production = True
    with server_factory(web_config) as server:
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


def test_route_broken_in_development(web_config, server_factory, no_routes,
                                     client_factory):
    web_config.production = False

    class BrokenRoute(Exception):
        pass

    with pytest.raises(BrokenRoute):
        with server_factory(web_config) as server:
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


def test_route_fallthru(web_config, server_factory, client_factory, no_routes):
    web_config.production = True
    with server_factory(web_config) as server:
        @route('/broken.html')
        def broken_route(request):
            return None

        client = client_factory(server)
        client.request('GET', '/broken.html')
        resp = client.getresponse()
        assert not resp.read()
        assert resp.status == 404


def test_for_commands():
    @for_commands('GET')
    def get_handler():
        pass

    @for_commands('GET', 'POST')
    def get_post_handler():
        pass

    @for_commands('DELETE')
    def delete_handler():
        pass

    assert set(get_handler.commands) == {'GET', 'HEAD'}
    assert set(get_post_handler.commands) == {'GET', 'POST', 'HEAD'}
    assert set(delete_handler.commands) == {'DELETE'}


def test_param_values():
    assert Param('Name', 'text').value('foo') == 'foo'
    assert Param('Count', 'range', min=0, max=100).value('50') == 50
    assert Param('Temperature', 'number', min=0, max=40).value('37.7') == 37.7
    assert Param('Foreground', 'color').value('#fff') == Color('#fff')
    assert Param('Locked', 'checkbox').value('') is False
    assert Param('Locked', 'checkbox').value('locked') is True


def test_special_param_values():
    request = mock.Mock()
    request.server.config.led_count = 50
    request.store.positions = [(0, 0, 0) for i in range(50)]
    request.server.config.fps = 60
    assert ParamLEDCount().value(request) == 50
    assert ParamFPS().value(request) == 60
    assert all(pos == (0, 0, 0) for pos in ParamLEDPositions().value(request))
