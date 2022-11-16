import re
import socket
import mimetypes
import datetime as dt
from threading import Thread
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

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


def route(pattern, method='GET'):
    def decorator(f):
        pattern_re = re.compile(
            '^' +
            re.sub(r':([A-Za-z_][A-Za-z0-9_]*)', r'(?P<\1>[^/]+)' +
            '$', re.escape(route))
        )
        assert pattern_re not in HTTPRequestHandler.routes
        HTTPRequestHandler.routes[(pattern_re, method)] = f
        if method == 'GET':
            # Anything registered for GET gets automatically assocaited with
            # HEAD as well
            HTTPRequestHandler.routes[(pattern_re, 'HEAD')] = f
        return f
    return decorator


class HTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


class HTTPRequestHandler(BaseHTTPRequestHandler):
    server_version = 'BlinkenXmas/1.0'
    static_path = resources.files('blinkenxmas')
    static_modified = dt.datetime.now()
    template_cache = {}
    routes = {}

    def get_response(self):
        # Search for a match in the routes table and call the appropriate
        # method if any is found; if the method returns None, keep searching
        for (pattern, method), handler in self.routes.items():
            m = pattern.match(self.path)
            if m and method == self.method:
                resp = handler(self, **m.groupdict())
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
            try:
                template = self.template_cache[template_key]
            except KeyError:
                template = PageTemplate(
                    (self.static_path / template_key).read_text())
                type(self).template_cache[template_key] = template
            now = dt.datetime.now()
            return HTTPResponse(
                self, body=template.render(
                    queue=self.server.queue,
                    store=self.server.store,
                    now=now),
                last_modified=now, filename=path)
        return HTTPResponse(self, status_code=HTTPStatus.NOT_FOUND)

    def do_HEAD(self):
        self.method = 'HEAD'
        resp = self.get_response()
        resp.send_headers()

    def do_GET(self):
        self.method = 'GET'
        resp = self.get_response()
        resp.send_headers()
        resp.send_body()

    def do_DELETE(self):
        self.method = 'DELETE'
        resp = self.get_response()
        resp.send_headers()
        resp.send_body()

    def do_PUT(self):
        self.method = 'PUT'
        resp = self.get_response()
        resp.send_headers()
        resp.send_body()

    def do_POST(self):
        self.method = 'POST'
        resp = self.get_response()
        resp.send_headers()
        resp.send_body()


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
