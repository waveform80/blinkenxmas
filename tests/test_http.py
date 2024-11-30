import io
import http
import datetime as dt
import email.utils as eut

import pytest

from blinkenxmas.http import *


class DummyRequest:
    def __init__(self, command='GET', path='/', protocol_version='HTTP/1.0',
                 if_modified_since=None, if_none_match=None, ranges=None,
                 headers=None, body=b""):
        self.command = command
        self.path = path
        self.protocol_version = protocol_version
        self.headers = HTTPHeaders(headers)
        if if_modified_since is not None:
            self.headers['If-Modified-Since'] = eut.format_datetime(
                if_modified_since, usegmt=if_modified_since.tzinfo is not None)
        if if_none_match is not None:
            self.headers['If-None-Match'] = if_none_match
        if ranges is not None:
            self.headers['Range'] = f'bytes={",".join(ranges)}'
        self.rfile = io.BytesIO(body)
        self.wfile = io.BytesIO()
        self.log = []
        self._header_buffer = []

    def send_response(self, status_code):
        self._header_buffer.append(
            f'{self.protocol_version} {status_code} '
            f'{http.HTTPStatus(status_code).phrase}')

    def send_header(self, key, value):
        self._header_buffer.append(
            f'{HTTPHeaders._http_name(key)}: {value}')

    def end_headers(self):
        for line in self._header_buffer:
            self.wfile.write(line.encode('utf-8'))
            self.wfile.write(b'\r\n')
        self.wfile.write(b'\r\n')
        self._header_buffer.clear()

    def log_error(self, s):
        self.log.append(s)


@pytest.fixture()
def headers():
    return HTTPHeaders(
        connection='keep-alive',
        content_type='text/html',
        content_length=1024)


def test_httpheaders_init():
    headers = HTTPHeaders({
        'Content-Type': 'text/html',
        'Content-Length': 1024,
    })
    assert len(headers) == 2
    assert headers.keys() == {'Content-Type', 'Content-Length'}
    headers = HTTPHeaders([
        ('Content-Type', 'text/html'),
        ('Content-Length', 1024),
    ])
    assert len(headers) == 2
    assert headers.keys() == {'Content-Type', 'Content-Length'}
    headers = HTTPHeaders(
        connection='keep-alive',
        content_type='text/html',
        content_length=1024)
    assert len(headers) == 3
    assert headers.keys() == {'Connection', 'Content-Type', 'Content-Length'}
    headers = HTTPHeaders()
    assert len(headers) == 0
    assert headers.keys() == set()


def test_httpheaders_get(headers):
    assert headers['Connection'] == 'keep-alive'
    assert headers['connection'] == 'keep-alive'
    assert headers['coNneCTion'] == 'keep-alive'
    assert headers['Content-Length'] == 1024


def test_httpheaders_del(headers):
    assert 'Content-Length' in headers
    del headers['Content-Length']
    assert 'Content-Length' not in headers
    with pytest.raises(KeyError):
        del headers['Content-Length']


def test_httpheaders_set(headers):
    assert headers['Content-Length'] == 1024
    headers['content-length'] = 100
    assert headers['Content-Length'] == 100


def test_httpheaders_iter(headers):
    assert {key for key in headers} == {
        'Content-Type', 'Content-Length', 'Connection'}


def test_httpheaders_len(headers):
    assert len(headers) == 3


def test_httpheaders_contains(headers):
    assert 'Content-Type' in headers
    assert 'foo' not in headers


def test_merge():
    assert list(merge([range(5), range(4, 10)])) == [range(10)]
    assert list(merge([range(5), range(5, 10)])) == [range(10)]
    assert list(merge([range(5), range(6, 10)])) == [range(5), range(6, 10)]


def test_transfer():
    source = io.BytesIO(b"ABCDEFG\x00" * 100000)
    target = io.BytesIO()
    transfer(source, target)
    assert source.getvalue() == target.getvalue()


def test_transfer_short_range():
    source = io.BytesIO(b"ABCDEFG\x00" * 100000)
    target = io.BytesIO()
    transfer(source, target, byterange=range(100, 10001))
    assert source.getvalue()[100:10001] == target.getvalue()


def test_transfer_range():
    source = io.BytesIO(b"ABCDEFG\x00" * 100000)
    target = io.BytesIO()
    transfer(source, target, byterange=range(100, 90001))
    print(len(target.getvalue()))
    assert source.getvalue()[100:90001] == target.getvalue()


def test_transfer_badrange():
    source = io.BytesIO(b"ABCDEFG\x00" * 100000)
    target = io.BytesIO()
    with pytest.raises(ValueError):
        transfer(source, target, byterange=range(100, 10001, 3))


def test_transfer_no_readinto():
    class MySource:
        def __init__(self, data):
            self._pos = 0
            self._data = data

        def read(self, n=-1):
            if n == -1:
                n = len(self._data) - self._pos
            result = self._data[self._pos:self._pos + n]
            self._pos += len(result)
            return result

        def seek(self, pos):
            self._pos = pos

    source = MySource(b"ABCDEFG\x00" * 100000)
    target = io.BytesIO()
    transfer(source, target)
    assert source._data == target.getvalue()

    source.seek(0)
    target = io.BytesIO()
    transfer(source, target, byterange=range(100, 90001))
    assert source._data[100:90001] == target.getvalue()


def test_dummy_response():
    req = DummyRequest()
    resp = DummyResponse(req)
    resp.check_cached()
    resp.check_ranges()
    resp.send_headers()
    resp.send_body()
    assert req.wfile.getvalue() == b''


def test_http_response_str():
    req = DummyRequest()
    resp = HTTPResponse(req, body="FOO")
    resp.send_headers()
    resp.send_body()
    assert req.wfile.getvalue() == b"""\
HTTP/1.0 200 OK\r
Content-Length: 3\r
\r
FOO"""


def test_http_response_str_encoding():
    req = DummyRequest()
    resp = HTTPResponse(req, body="FOO", encoding='ascii')
    resp.send_headers()
    resp.send_body()
    assert req.wfile.getvalue() == b"""\
HTTP/1.0 200 OK\r
Content-Length: 3\r
Content-Encoding: ascii\r
\r
FOO"""


def test_http_response_bytes():
    req = DummyRequest()
    resp = HTTPResponse(req, body=b"bar")
    resp.send_headers()
    resp.send_body()
    assert req.wfile.getvalue() == b"""\
HTTP/1.0 200 OK\r
Content-Length: 3\r
\r
bar"""


def test_http_response_path(tmp_path):
    body = tmp_path / 'body.dat'
    body.write_text('Foo Bar Baz')
    last_modified = dt.datetime.fromtimestamp(
        body.stat().st_mtime_ns / 1_000_000_000,
        tz=dt.timezone.utc)
    req = DummyRequest()
    resp = HTTPResponse(req, body=body)
    resp.send_headers()
    resp.send_body()
    # Last-Modified derived implicitly from the path
    assert req.wfile.getvalue() == f"""\
HTTP/1.0 200 OK\r
Content-Length: 11\r
Last-Modified: {eut.format_datetime(last_modified, usegmt=True)}\r
\r
Foo Bar Baz""".encode('utf-8')


def test_http_response_path_with_filename(tmp_path):
    body = tmp_path / 'body.dat'
    body.write_text('Foo Bar Baz')
    req = DummyRequest()
    resp = HTTPResponse(req, body=body, filename='body.txt')
    resp.send_headers()
    resp.send_body()
    # Content-Type appears because the .txt extension matches MIME-type
    # text/plain, while Last-Modified disappears because the specified filename
    # doesn't actually exist
    assert req.wfile.getvalue() == f"""\
HTTP/1.0 200 OK\r
Content-Length: 11\r
Content-Type: text/plain\r
\r
Foo Bar Baz""".encode('utf-8')


def test_http_response_stream():
    body = io.BytesIO(b"QUUX")
    req = DummyRequest()
    resp = HTTPResponse(req, body=body)
    resp.send_headers()
    resp.send_body()
    assert req.wfile.getvalue() == b"""\
HTTP/1.0 200 OK\r
Content-Length: 4\r
\r
QUUX"""


def test_http_response_stream_with_filename():
    body = io.BytesIO(b"QUUX")
    req = DummyRequest()
    resp = HTTPResponse(req, body=body, filename='body.txt')
    resp.send_headers()
    resp.send_body()
    assert req.wfile.getvalue() == b"""\
HTTP/1.0 200 OK\r
Content-Length: 4\r
Content-Type: text/plain\r
\r
QUUX"""


def test_http_response_stream_no_seek():
    class MySource(io.IOBase):
        def __init__(self, data):
            self._pos = 0
            self._data = data

        def read(self, n=-1):
            if n == -1:
                n = len(self._data) - self._pos
            result = self._data[self._pos:self._pos + n]
            self._pos += len(result)
            return result

    body = MySource(b"XYZZY")
    req = DummyRequest()
    resp = HTTPResponse(req, body=body, filename='body.txt')
    resp.send_headers()
    resp.send_body()
    assert req.wfile.getvalue() == b"""\
HTTP/1.0 200 OK\r
Content-Type: text/plain\r
\r
XYZZY"""


def test_http_response_repr():
    req = DummyRequest()
    resp = HTTPResponse(req, body="FOO")
    assert repr(resp) == """\
HTTP/1.0 200 OK
Content-Length: 3"""


def test_http_response_cached_datetime(tmp_path):
    body = tmp_path / 'body.dat'
    body.write_text('Foo Bar Baz')
    last_modified = dt.datetime.fromtimestamp(
        body.stat().st_mtime_ns / 1_000_000_000,
        tz=dt.timezone.utc)
    req = DummyRequest(if_modified_since=last_modified)
    resp = HTTPResponse(req, body=body)
    resp.check_cached()
    resp.send_headers()
    resp.send_body()
    # Last-Modified derived implicitly from the path
    assert req.wfile.getvalue() == f"""\
HTTP/1.0 304 Not Modified\r
Last-Modified: {eut.format_datetime(last_modified, usegmt=True)}\r
\r
""".encode('utf-8')


def test_http_response_cached_naive_datetime(tmp_path):
    body = tmp_path / 'body.dat'
    body.write_text('Foo Bar Baz')
    last_modified = dt.datetime.utcfromtimestamp(
        body.stat().st_mtime_ns / 1_000_000_000)
    req = DummyRequest(if_modified_since=last_modified)
    resp = HTTPResponse(req, body=body)
    resp.check_cached()
    resp.send_headers()
    resp.send_body()
    # Last-Modified derived implicitly from the path
    last_modified = last_modified.replace(tzinfo=dt.timezone.utc)
    assert req.wfile.getvalue() == f"""\
HTTP/1.0 304 Not Modified\r
Last-Modified: {eut.format_datetime(last_modified, usegmt=True)}\r
\r
""".encode('utf-8')


def test_http_response_not_cached_datetime(tmp_path):
    body = tmp_path / 'body.dat'
    body.write_text('Foo Bar Baz')
    last_modified = dt.datetime.fromtimestamp(
        body.stat().st_mtime_ns / 1_000_000_000,
        tz=dt.timezone.utc)
    req = DummyRequest()
    resp = HTTPResponse(req, body=body)
    resp.check_cached()
    resp.send_headers()
    resp.send_body()
    # Last-Modified derived implicitly from the path
    assert req.wfile.getvalue() == f"""\
HTTP/1.0 200 OK\r
Content-Length: 11\r
Last-Modified: {eut.format_datetime(last_modified, usegmt=True)}\r
\r
Foo Bar Baz""".encode('utf-8')


def test_http_response_cached_etag():
    body = io.BytesIO(b'Foo Bar Baz')
    req = DummyRequest(if_none_match='QUUX')
    resp = HTTPResponse(req, body=body, headers={'ETag': 'QUUX'})
    resp.check_cached()
    resp.send_headers()
    resp.send_body()
    # Last-Modified derived implicitly from the path
    assert req.wfile.getvalue() == f"""\
HTTP/1.0 304 Not Modified\r
ETag: QUUX\r
\r
""".encode('utf-8')


def test_http_response_ranges_normal():
    body = io.BytesIO(b'FOOBARBAZQUUX')
    req = DummyRequest(ranges=['3-5'])
    resp = HTTPResponse(req, body=body)
    resp.check_cached()
    resp.check_ranges()
    resp.send_headers()
    resp.send_body()
    assert req.wfile.getvalue() == f"""\
HTTP/1.0 206 Partial Content\r
Content-Length: 3\r
Accept-Ranges: bytes\r
Content-Range: bytes 3-5/13\r
\r
BAR""".encode('utf-8')


def test_http_response_ranges_from_byte():
    body = io.BytesIO(b'FOOBARBAZQUUX')
    req = DummyRequest(ranges=['9-'])
    resp = HTTPResponse(req, body=body)
    resp.check_cached()
    resp.check_ranges()
    resp.send_headers()
    resp.send_body()
    assert req.wfile.getvalue() == f"""\
HTTP/1.0 206 Partial Content\r
Content-Length: 4\r
Accept-Ranges: bytes\r
Content-Range: bytes 9-12/13\r
\r
QUUX""".encode('utf-8')


def test_http_response_ranges_last_bytes():
    body = io.BytesIO(b'FOOBARBAZQUUX')
    req = DummyRequest(ranges=['-7'])
    resp = HTTPResponse(req, body=body)
    resp.check_cached()
    resp.check_ranges()
    resp.send_headers()
    resp.send_body()
    assert req.wfile.getvalue() == f"""\
HTTP/1.0 206 Partial Content\r
Content-Length: 7\r
Accept-Ranges: bytes\r
Content-Range: bytes 6-12/13\r
\r
BAZQUUX""".encode('utf-8')


def test_http_response_backwards_range():
    body = io.BytesIO(b'FOOBARBAZQUUX')
    req = DummyRequest(ranges=['9-6'])
    resp = HTTPResponse(req, body=body)
    resp.check_cached()
    resp.check_ranges()
    resp.send_headers()
    resp.send_body()
    assert req.wfile.getvalue() == f"""\
HTTP/1.0 400 Bad Request\r
Accept-Ranges: bytes\r
\r
""".encode('utf-8')


def test_http_response_bad_range():
    body = io.BytesIO(b'FOOBARBAZQUUX')
    req = DummyRequest(ranges=['6-20'])
    resp = HTTPResponse(req, body=body)
    resp.check_cached()
    resp.check_ranges()
    resp.send_headers()
    resp.send_body()
    assert req.wfile.getvalue() == f"""\
HTTP/1.0 416 Requested Range Not Satisfiable\r
Accept-Ranges: bytes\r
Content-Range: bytes 6-20/13\r
\r
""".encode('utf-8')


def test_http_response_ranges_merged():
    body = io.BytesIO(b'FOOBARBAZQUUX')
    req = DummyRequest(ranges=['3-5', '0-2'])
    resp = HTTPResponse(req, body=body)
    resp.check_cached()
    resp.check_ranges()
    resp.send_headers()
    resp.send_body()
    assert req.wfile.getvalue() == f"""\
HTTP/1.0 206 Partial Content\r
Content-Length: 6\r
Accept-Ranges: bytes\r
Content-Range: bytes 0-5/13\r
\r
FOOBAR""".encode('utf-8')


def test_http_response_ranges_multiple():
    body = io.BytesIO(b'FOOBARBAZQUUX')
    req = DummyRequest(ranges=['0-2', '6-8'])
    resp = HTTPResponse(req, body=body)
    resp.check_cached()
    resp.check_ranges()
    resp.send_headers()
    resp.send_body()
    assert req.wfile.getvalue() == f"""\
HTTP/1.0 206 Partial Content\r
Accept-Ranges: bytes\r
Content-Type: multipart/byteranges; boundary=BOUNDARY\r
\r
--BOUNDARY\r
Content-Range: bytes 0-2/13\r
\r
FOO\r
--BOUNDARY\r
Content-Range: bytes 6-8/13\r
\r
BAZ\r
""".encode('utf-8')


def test_http_response_ranges_multiple_with_content_type():
    body = io.BytesIO(b'FOOBARBAZQUUX')
    req = DummyRequest(ranges=['0-2', '6-8'])
    resp = HTTPResponse(req, body=body, headers={'Content-Type': 'text/plain'})
    resp.check_cached()
    resp.check_ranges()
    resp.send_headers()
    resp.send_body()
    assert req.wfile.getvalue() == f"""\
HTTP/1.0 206 Partial Content\r
Accept-Ranges: bytes\r
Content-Type: multipart/byteranges; boundary=BOUNDARY\r
\r
--BOUNDARY\r
Content-Type: text/plain\r
Content-Range: bytes 0-2/13\r
\r
FOO\r
--BOUNDARY\r
Content-Type: text/plain\r
Content-Range: bytes 6-8/13\r
\r
BAZ\r
""".encode('utf-8')


def test_http_response_no_ranges():
    body = io.BytesIO(b'FOOBARBAZQUUX')
    req = DummyRequest(ranges=['0-2', '6-8'])
    resp = HTTPResponse(req, body=body, accept_ranges=False)
    resp.check_cached()
    resp.check_ranges()
    resp.send_headers()
    resp.send_body()
    assert req.wfile.getvalue() == f"""\
HTTP/1.0 200 OK\r
Content-Length: 13\r
\r
FOOBARBAZQUUX""".encode('utf-8')


def test_http_response_empty_ranges():
    body = io.BytesIO(b'FOOBARBAZQUUX')
    req = DummyRequest(ranges=[])
    resp = HTTPResponse(req, body=body)
    resp.check_cached()
    resp.check_ranges()
    resp.send_headers()
    resp.send_body()
    assert req.wfile.getvalue() == f"""\
HTTP/1.0 200 OK\r
Content-Length: 13\r
Accept-Ranges: bytes\r
\r
FOOBARBAZQUUX""".encode('utf-8')
