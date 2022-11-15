import io
import re
import random
import socket
import mimetypes
import datetime as dt
from http import HTTPStatus
from threading import Thread
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from shutil import copyfileobj

# The fallback comes first here as Python 3.7 incorporates importlib.resources
# but at a version incompatible with our requirements. Ultimately the try
# clause should be removed in favour of the except clause once compatibility
# moves beyond Python 3.9
try:
    import importlib_resources as resources
except ImportError:
    from importlib import resources

from pkg_resources import resource_stream
from chameleon import PageTemplate

from .store import Storage


def get_best_family(host, port):
    infos = socket.getaddrinfo(
        host, port,
        type=socket.SOCK_STREAM,
        flags=socket.AI_PASSIVE)
    for family, type, proto, canonname, sockaddr in infos:
        return family, sockaddr


def get_port(service):
    try:
        return int(service)
    except ValueError:
        try:
            return socket.getservbyname(service)
        except OSError:
            raise ValueError('invalid service name or port number')


class HTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


class HTTPRequestHandler(BaseHTTPRequestHandler):
    server_version = 'BlinkenXmas/1.0'
    static_path = resources.files('blinkenxmas')
    static_modified = dt.datetime.now()
    template_cache = {}

    def get_response(self):
        path = self.path.lstrip('/')
        template_key = path + '.pt'
        if not path:
            return HTTPResponse(
                self, status_code=301, headers={'Location': '/index.html'})
        elif (self.static_path / path).exists():
            return HTTPResponse(
                self, body=(self.static_path / path).open('rb'),
                last_modified=self.static_modified, filename=path)
        elif (self.static_path / template_key).exists():
            try:
                template = self.template_cache[template_key]
            except KeyError:
                template = PageTemplate(
                    (self.static_path / template_key).read_text())
                self.template_cache[template_key] = template
            now = dt.datetime.now()
            return HTTPResponse(
                self, body=template.render(
                    queue=self.server.queue, store=self.server.store,
                    now=now),
                last_modified=now, filename=path)
        else:
            return HTTPResponse(self, status_code=404)

    def do_HEAD(self):
        self.get_response().send(head=True)

    def do_GET(self):
        self.get_response().send(head=False)


class HTTPResponse:
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

    def send(self, *, head=False):
        self.request.send_response(self.status_code.value)
        for key, value in self.headers.items():
            self.request.send_header(key, value)
        self.request.end_headers()
        if self.stream is not None:
            if not head:
                copyfileobj(self.stream, self.request.wfile)
            self.stream.close()


class HTTPThread(Thread):
    def __init__(self, queue, bind, port, db):
        super().__init__(target=self.serve, daemon=True)
        mimetypes.init()
        HTTPServer.address_family, addr = get_best_family(bind, port)
        HTTPServer.queue = queue
        HTTPServer.store = Storage(db)
        self.httpd = HTTPServer(addr[:2], HTTPRequestHandler)
        self.exception = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *exc_info):
        if self.exception:
            raise self.exception
        self.stop()

    def stop(self):
        self.httpd.shutdown()

    def serve(self):
        try:
            host, port = self.httpd.socket.getsockname()[:2]
            hostname = socket.gethostname()
            print(f'Serving on {host} port {port}')
            print(f'http://{hostname}:{port}/ ...')
            self.httpd.serve_forever()
        except Exception as e:
            self.exception = e
