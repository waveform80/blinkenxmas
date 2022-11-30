import re
import json
import socket
import mimetypes
import datetime as dt
import email.utils as eut
import urllib.parse
from http import HTTPStatus
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from collections import namedtuple
from threading import Thread

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
from .http import HTTPResponse


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


def route(pattern, command='GET'):
    def decorator(f):
        s = re.escape(pattern)
        s = re.sub(r'\*\*:([A-Za-z_][A-Za-z0-9_]*)', r'(?P<\1>.+)', s)
        s = re.sub(r'\*?:([A-Za-z_][A-Za-z0-9_]*)', r'(?P<\1>[^/]+)', s)
        pattern_re = re.compile(f'^{s}$')
        assert pattern_re not in HTTPRequestHandler.routes
        HTTPRequestHandler.routes[(pattern_re, command)] = f
        if command == 'GET':
            # Anything registered for GET gets automatically assocaited with
            # HEAD as well
            HTTPRequestHandler.routes[(pattern_re, 'HEAD')] = f
        return f
    return decorator


Function = namedtuple('Function', ('name', 'function', 'params'))
class Param(namedtuple('Param', ('label', 'input_type', 'default', 'min', 'max'))):
    __slots__ = () # workaround python issue #24931
    def __new__(cls, label, input_type, *, default=None, min=None, max=None):
        return super(Param, cls).__new__(
            cls, label, input_type, default, min, max)


def animation(name, **params):
    def decorator(f):
        HTTPRequestHandler.animations[f.__name__] = Function(name, f, params)
        return f
    return decorator


class HTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


class HTTPRequestHandler(BaseHTTPRequestHandler):
    server_version = 'BlinkenXmas/1.0'
    static_path = resources.files('blinkenxmas')
    static_modified = dt.datetime.now(dt.timezone.utc)
    template_cache = {
        'layout.pt': PageTemplate((static_path / 'layout.html.pt').read_text())
    }
    routes = {}
    animations = {}

    def get_template(self, name):
        try:
            template = self.template_cache[name]
        except KeyError:
            template = PageTemplate((self.static_path / name).read_text())
            type(self).template_cache[name] = template
        return template

    def get_response(self):
        # Parse the path into its components
        self.uri = self.path
        parts = urllib.parse.urlsplit(self.uri)
        self.path = parts.path
        self.query = urllib.parse.parse_qs(parts.query)
        self.fragment = parts.fragment
        self.store = Storage(self.server.config.db)
        # Search for a match in the routes table and call the appropriate
        # method if any is found; if the method returns None, keep searching
        for (pattern, command), handler in self.routes.items():
            m = pattern.match(self.path)
            if m and command == self.command:
                resp = handler(self, **{
                    param: urllib.parse.unquote(value)
                    for param, value in m.groupdict().items()
                })
                if resp is not None:
                    return resp
        # Nothing found in the routes table; attempt to either find a literal
        # match in the static path (and check if-modified-since) or find a
        # template in the static path, load and render it
        path = self.path.lstrip('/')
        template_key = path + '.pt'
        if (self.static_path / path).exists():
            if self.headers.get('If-Modified-Since'):
                limit = eut.parsedate_to_datetime(
                    self.headers['If-Modified-Since'])
                if self.static_modified <= limit:
                    return HTTPResponse(
                        self, status_code=HTTPStatus.NOT_MODIFIED)
            return HTTPResponse(
                self, body=(self.static_path / path).open('rb'),
                last_modified=self.static_modified, filename=path)
        elif (self.static_path / template_key).exists():
            template = self.get_template(template_key)
            now = dt.datetime.now(dt.timezone.utc)
            # TODO Handle errors in rendering
            return HTTPResponse(
                self, body=template.render(
                    layout=self.template_cache['layout.pt']['layout'],
                    led_count=self.server.config.led_count,
                    # "Sanitize" animations to make it JSON serializable
                    animations={
                        name: Function(anim.name, None, anim.params)
                        for name, anim in self.animations.items()
                    },
                    json=json.dumps,
                    request=self,
                    store=self.store,
                    now=now),
                last_modified=now, filename=path)
        return HTTPResponse(self, status_code=HTTPStatus.NOT_FOUND)

    def json(self):
        try:
            body_len = int(self.headers['Content-Length'])
        except KeyError:
            body = self.rfile.read()
        else:
            body = self.rfile.read(body_len)
        return json.loads(body)

    def do_HEAD(self):
        resp = self.get_response()
        resp.send_headers()

    def do_GET(self):
        resp = self.get_response()
        resp.send_headers()
        resp.send_body()

    def do_DELETE(self):
        resp = self.get_response()
        resp.send_headers()
        resp.send_body()

    def do_PUT(self):
        resp = self.get_response()
        resp.send_headers()
        resp.send_body()

    def do_POST(self):
        resp = self.get_response()
        resp.send_headers()
        resp.send_body()


class HTTPThread(Thread):
    def __init__(self, queue, config):
        super().__init__(target=self.serve, daemon=True)
        mimetypes.init()
        HTTPServer.address_family, addr = get_best_family(
            config.httpd_bind, config.httpd_port)
        HTTPServer.queue = queue
        HTTPServer.config = config
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
