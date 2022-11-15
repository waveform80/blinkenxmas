import io
import re
import socket
import mimetypes
import datetime as dt
from http import HTTPStatus
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from shutil import copyfileobj

from pkg_resources import resource_stream


class TreeServer(ThreadingHTTPServer):
    allow_reuse_address = True


class TreeRequestHandler(BaseHTTPRequestHandler):
    server_version = 'BlinkenXmas/1.0'
    static_paths = {
        '/index.html': 'text/html',
        '/style.css': 'text/css',
        '/favicon.opt.svg': 'image/svg+xml',
    }
    static_modified = dt.datetime.now()

    def do_GET(self):
        if self.path == '/':
            resp = TreeResponse(
                self, status_code=301, headers={'Location': '/index.html'})
        elif self.path.startswith('/preset/'):
            resp = TreeResponse(self, body='Preset!')
        elif self.path in self.static_paths:
            resp = TreeResponse(
                self, body=resource_stream(__name__, self.path.lstrip()),
                last_modified=self.static_modified,
                mime_type=self.static_paths[self.path])
        else:
            resp = TreeResponse(self, status_code=404)
        resp.send()


class TreeResponse:
    def __init__(self, request, body=None, *, status_code=200,
                 content_length=None, filename=None, mime_type=None,
                 encoding=None, last_modified=None, headers=None):
        self.request = request
        self.status_code = HTTPStatus(status_code)
        if headers is None:
            self.headers = {}
        else:
            self.headers = headers.copy()
        if isinstance(body, str):
            self.stream = io.BytesIO(body.encode('utf-8'))
        elif isinstance(body, bytes):
            self.stream = io.BytesIO(body)
        else:
            self.stream = body
        if (
            content_length is None and self.stream is not None and
            self.stream.seekable()
        ):
            content_length = self.stream.seek(0, io.SEEK_END)
            self.stream.seek(0)
        if content_length is not None:
            self.headers['Content-Length'] = content_length
        if mime_type is None and filename is not None:
            mime_type, encoding = mimetypes.guess_type(filename)
        if mime_type is not None:
            self.headers['Content-Type'] = mime_type
        if encoding is not None:
            self.headers['Content-Encoding'] = encoding
        if last_modified is not None:
            self.headers['Last-Modified'] = request.date_time_string(
                last_modified.timestamp())

    def __repr__(self):
        headers = '\n'.join(f'{key}: {value}' for key, value in self.headers)
        return (
            f'{self.request.protocol_version} {self.status_code.value} '
            f'{self.status_code.phrase}\n{headers}\n\n'
        )

    def send(self, head=False):
        self.request.send_response(self.status_code.value)
        for key, value in self.headers.items():
            self.request.send_header(key, value)
        self.request.end_headers()
        if not head and self.stream is not None:
            copyfileobj(self.stream, self.request.wfile)


def get_best_family(host, port):
    infos = socket.getaddrinfo(
        host, port,
        type=socket.SOCK_STREAM,
        flags=socket.AI_PASSIVE)
    family, type, proto, canonname, sockaddr = next(iter(infos))
    return family, sockaddr


def get_port(service):
    try:
        return int(service)
    except ValueError:
        try:
            return socket.getservbyname(service)
        except OSError:
            raise ValueError('invalid service name or port number')


def server(bind, port):
    mimetypes.init()
    TreeServer.address_family, addr = get_best_family(bind, port)
    with TreeServer(addr[:2], TreeRequestHandler) as httpd:
        host, port = httpd.socket.getsockname()[:2]
        hostname = socket.gethostname()
        print(f'Serving on {host} port {port}')
        print(f'http://{hostname}:{port}/ ...')
        httpd.serve_forever()
