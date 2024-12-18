import re
import json
import socket
import logging
import mimetypes
import datetime as dt
import urllib.parse
from http import HTTPStatus
from textwrap import dedent
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from collections import namedtuple, deque
from threading import Thread, Lock
from contextlib import suppress
from inspect import signature

# NOTE: The fallback comes first here as Python 3.7 incorporates
# importlib.resources but at a version incompatible with our requirements.
# Ultimately the try clause should be removed in favour of the except clause
# once compatibility moves beyond Python 3.9
try:
    import importlib_resources as resources
except ImportError:
    from importlib import resources

# NOTE: Remove except when compatibility moves beyond Python 3.8
try:
    from importlib.metadata import version
except ImportError:
    from importlib_metadata import version

import docutils
import docutils.core
from chameleon import PageTemplate
from colorzero import Color

from . import cameras, store, calibrate
from .http import HTTPResponse, parse_formdata, parse_content_value


def get_best_family(host, port):
    """
    Given a *host* name and a *port* specification (either a number or a
    service name), returns the network family (e.g. ``socket.AF_INET``) and
    socket address to listen on as a tuple.
    """
    try:
        infos = socket.getaddrinfo(
            host, port,
            type=socket.SOCK_STREAM,
            flags=socket.AI_PASSIVE)
    except socket.gaierror as exc:
        raise ValueError('invalid host and port combination') from exc
    for family, _, _, _, sockaddr in infos:
        return family, sockaddr
    raise ValueError('invalid host and port combination')


def route(pattern, command='GET'):
    """
    Decorator that associates a route with a function

    The *pattern* specifies the route that is to be matched. Within the
    *pattern*, angle-bracket words designate variable sections of the route
    that will be passed to like-named parameters in the associated function.
    The *command* (which defaults to 'GET') specifies which HTTP command the
    route will match.

    The associated function must accept the mandatory "request" parameter
    first, which will contain the associated :class:`HTTPRequestHandler`, plus
    any parameters implied by ``<sections>`` in the *pattern*. It must return a
    :class:`HTTPResponse` object, or :data:`None` if (for some reason) the
    route doesn't match.

    For example, the following declaration will match the single route
    "/index.html"::

        @route('/index.html')
        def homepage(request):
            return HTTPResponse(request, body='Hello, world!')

    The following declaration will match any HTML file directly under
    ``/people``::

        @route('/people/<name>.html', 'GET')
        def get_person(request, name):
            person = db.lookup_person(name)
            return HTTPResponse(request, body=f'Hello, {person.name}!')
    """
    def decorator(f):
        s = re.escape(pattern)
        s = re.sub(r'<([A-Za-z_][A-Za-z0-9_]*)>', r'(?P<\1>[^/]+)', s)
        pattern_re = re.compile(f'^{s}$')
        assert pattern_re not in HTTPRequestHandler.routes
        HTTPRequestHandler.routes[(pattern_re, command)] = f
        if command == 'GET':
            # Anything registered for GET gets automatically associated with
            # HEAD as well
            HTTPRequestHandler.routes[(pattern_re, 'HEAD')] = f
        return f
    return decorator


class Function(namedtuple('Function', (
        'name', 'description', 'function', 'params'))):
    """
    Defines an animation function.

    .. attribute:: name

        The short title of the animation.

    .. attribute:: description

        An extended description of the animation detailing all the parameters
        and the intended result. Typically derived from the function's
        doc-string.

    .. attribute:: function

        The implementing callable function.

    .. attribute:: params

        A dict mapping each parameter name of :attr:`function` to
        :class:`Param` instances (or the special classes like
        :class:`ParamFPS`) indicating how to render the controls for each
        parameter.
    """


class Param(namedtuple('Param', (
        'label', 'input_type', 'default', 'min', 'max', 'choices', 'suffix'))):
    """
    Defines the associated parameter as being a user-configured value.

    The *input_type* is used in the generated ``<input>`` element's "type"
    parameter (if this is "select" then a ``<select>`` drop-down element is
    generated instead). The *default*, *min*, and *max* parameters correspond
    to the "default", "min", and "max" attributes of the ``<input>`` element.
    Finally, the *choices* parameter is a mapping of valid identifiers to
    labels used when *input_type* is "select".

    .. attribute:: label

        The content of the ``<label>`` to render with the parameter's
        ``<input>`` element.

    .. attribute:: input_type

        The value of the ``<input>`` element's ``type`` parameter.

    .. attribute:: default

        The default value of the input.

    .. attribute:: min

        The minimum value for ``range`` type inputs.

    .. attribute:: max

        The maximum value for ``range`` type inputs.

    .. attribute:: choices

        A :class:`dict` defining the valid selections for ``select`` type
        inputs. The values of the dictionary represent the labels for each
        option value.

    .. attribute:: suffix

        A text suffix to render after the input box.
    """
    __slots__ = () # workaround python issue #24931

    def __new__(cls, label, input_type, *, default=None, min=None, max=None,
                choices=None, suffix=None):
        return super(Param, cls).__new__(
            cls, label, input_type, default, min, max, choices, suffix)

    def value(self, value):
        return (
            int(value) if self.input_type == 'range' else
            float(value) if self.input_type == 'number' else
            Color(value) if self.input_type == 'color' else
            bool(value) if self.input_type == 'checkbox' else
            str(value))


class ParamLEDCount:
    """
    Defines the associated parameter as taking the total number of LEDs on the
    tree (an :class:`int`).
    """
    __slots__ = ()

    def value(self, request):
        return request.server.config.led_count


class ParamLEDPositions:
    """
    Defines the associated parameter as taking the mapping of LED indexes to
    :class:`~blinkenxmas.store.Position` instances.

    .. warning::

        Please be aware that not all LEDs may be included in the mapping. If an
        LED was not detected during calibration (either because it is
        persistently hidden or defective) then it will not be included in the
        mapping.
    """
    __slots__ = ()

    def value(self, request):
        return request.store.positions


class ParamFPS:
    """
    Defines the associated parameter as taking the frames-per-second that
    animations are expected to be rendered for.
    """
    __slots__ = ()

    def value(self, request):
        return request.server.config.fps


def animation(name, **params):
    """
    Decorates a function as an animation generator to be presented in the
    Create interface. The doc-string of the function is used as the description
    and is expected to be in reStructuredText format (which will be rendered
    into HTML).

    Each of the parameters to the function must be defined as a keyword
    argument to the decorator which is associated with one of the parameter
    classes defined:

    * :class:`ParamLEDCount`

    * :class:`ParamLEDPositions`

    * :class:`ParamFPS`

    * :class:`Param`
    """
    def decorator(f):
        required_params = {
            key: param
            for key, param in signature(f).parameters.items()
            if param.default is param.empty
        }
        if required_params.keys() != params.keys():
            extra = required_params.keys() - params.keys()
            if extra:
                raise ValueError(
                    f'animation function {f!r} has extra parameter(s) '
                    f'{", ".join(extra)}')
            missing = params.keys() - required_params.keys()
            if missing:
                raise ValueError(
                    f'animation function {f!r} is missing parameter(s) '
                    f'{", ".join(missing)}')
        invalid_params = {'name', 'data', 'animation'} & params.keys()
        if invalid_params:
            raise ValueError(
                f'invalid parameter name(s) in animation function {f!r}: '
                f'{", ".join(invalid_params)}')
        if f.__doc__:
            overrides = {
                'input_encoding':       'unicode',
                'doctitle_xform':       False,
                'initial_header_level': 2,
                }
            html = docutils.core.publish_parts(
                source=dedent(f.__doc__), writer_name='html',
                settings_overrides=overrides)['fragment']
        else:
            html = ''
        func = Function(name, html, f, params)
        HTTPRequestHandler.animations[f.__name__] = func
        return f
    return decorator


def for_commands(*commands):
    """
    Decorator that associates methods in the request handler with HTTP commands
    like GET, HEAD, etc. This is only intended for internal use in
    :class:`HTTPRequestHandler`.
    """
    def decorator(f):
        f.commands = commands
        if 'GET' in commands:
            f.commands += ('HEAD',)
        return f
    return decorator


class HTTPServer(ThreadingHTTPServer):
    """
    The blinkenxmas HTTP server class, which descends from
    :class:`http.server.ThreadingHTTPServer` and is thus multi-threaded. This
    does precious little other than override :meth:`handle_error`.
    """
    allow_reuse_address = True
    daemon_threads = True
    logger = logging.getLogger('httpd')

    def handle_error(self, request, client_address):
        """
        Overridden to shut down the server in the event of an error when the
        configuration doesn't specify production mode.
        """
        if self.config.production:
            super().handle_error(request, client_address)
        else:
            # We don't print the error with the parent handle_error here as
            # we're actually going to re-raise it in the main thread
            self.shutdown()


class HTTPRequestHandler(BaseHTTPRequestHandler):
    """
    The blinkenxmas request handler. The :meth:`get_response` method is the
    primary piece of machinery that decides what handler deals with a given
    request. There are roughly three types of handler:

    * Simple static data (included in the package data) is handled by
      :meth:`try_static`

    * Chameleon templates (also included in the package data) are rendered by
      :meth:`try_template`

    * Finally, custom functions (decorated by :func:`route`) are called by
      :meth:`try_route`
    """
    server_version = f'BlinkenXmas/{version("blinkenxmas")}'
    static_path = resources.files('blinkenxmas')
    static_modified = dt.datetime.now(dt.timezone.utc)
    template_cache = {
        'layout.pt': PageTemplate((static_path / 'layout.html.pt').read_text())
    }
    routes = {}
    animations = {}

    def get_template(self, name):
        """
        Returns the Chameleon template with the specified *name*. Templates are
        loaded from module resources and cached in the
        :attr:`HTTPRequestHandler.template_cache` class attribute.
        """
        try:
            template = self.template_cache[name]
        except KeyError:
            template = PageTemplate((self.static_path / name).read_text())
            type(self).template_cache[name] = template
        return template

    def get_template_ns(self, **kwargs):
        """
        Returns the namespace used when rendering Chameleon templates.
        """
        ns = {
            'layout':         self.template_cache['layout.pt']['layout'],
            'url':            urllib.parse.quote,
            'json':           json.dumps,
            'request':        self,
            'messages':       self.server.messages,
            'config':         self.server.config,
            'now':            dt.datetime.now(tz=dt.timezone.utc),
            'datetime':       dt.datetime,
            'timedelta':      dt.timedelta,
            'led_count':      self.server.config.led_count,
            'calibration':    self.server.calibration,
            'store':          self.store,
            'animations':     self.animations,
        }
        ns.update(kwargs)
        return ns

    @for_commands('GET', 'POST', 'PUT', 'DELETE')
    def try_route(self):
        """
        Searches for a match of the requested :attr:`path` in the defined
        :mod:`routes`.

        If a match is found, the function associated with the route is called
        and, if it returns a :class:`HTTPResponse`, that is returned. If no
        match is found, returns :data:`None`.
        """
        for (pattern, command), handler in self.routes.items():
            m = pattern.match(self.path)
            if m and command == self.command:
                resp = handler(self, **{
                    param: urllib.parse.unquote(value)
                    for param, value in m.groupdict().items()
                })
                if resp is not None:
                    resp.headers.setdefault('Cache-Control', 'no-cache')
                    return resp
        return None

    @for_commands('GET')
    def try_static(self):
        """
        Attempts to find a match for the requested :attr:`path` in the static
        data of the module.

        If a match is found, a :class:`HTTPResponse` is constructed and
        returned. Otherwise, returns :data:`None`.
        """
        path = self.path.lstrip('/')
        try:
            body = (self.static_path / path).open('rb')
        except FileNotFoundError:
            return None
        else:
            return HTTPResponse(
                self, body=body, filename=path,
                headers={'Cache-Control': 'max-age=86400'})

    @for_commands('GET', 'POST')
    def try_template(self):
        """
        Attempts to find a Chameleon template within the static data of the
        module that matches the requested :attr:`path` plus a ``.pt`` suffix.

        If a template is found, it is rendered with the result of
        :meth:`get_template_ns` as the namespace, and a :class:`HTTPResponse`
        is constructed from the result. Otherwise, returns :data:`None`.
        """
        path = self.path.lstrip('/')
        template_key = path + '.pt'
        try:
            template = self.get_template(template_key)
        except FileNotFoundError:
            return None
        namespace = self.get_template_ns()
        body = template.render(**namespace)
        return HTTPResponse(
            self, body=body, last_modified=namespace['now'], etag=False,
            filename=path, headers={'Cache-Control': 'no-cache'})

    def get_response(self):
        """
        Tries various methods (:meth:`try_route`, :meth:`try_static`,
        :meth:`try_template` in that order) to obtain a :class:`HTTPResponse`
        for the current request.

        Handles returning appropriate errors in the case of failure (500
        internal server error in the case that rendering of a route or template
        fails, 404 not found in the case that no route, static file, or
        template can be found that matches the requested :attr:`path`).
        """
        try:
            # Parse the path into its components
            self.uri = self.path
            parts = urllib.parse.urlsplit(self.uri)
            self.path = parts.path
            self.fragment = parts.fragment
            if self.command == 'GET' and parts.query:
                self.query = urllib.parse.parse_qs(parts.query)
            elif self.command == 'POST':
                try:
                    content_type, attrs = parse_content_value(
                        self.headers.get('Content-Type', ''))
                    if content_type == 'application/x-www-form-urlencoded':
                        body = self.rfile.read(
                            int(self.headers['Content-Length'])
                            if 'Content-Length' in self.headers else
                            None).decode('utf-8', errors='ignore')
                        self.query = urllib.parse.parse_qs(body)
                    elif content_type == 'multipart/form-data':
                        self.query = parse_formdata(self)
                    elif content_type == 'application/json':
                        self.query = self.json()
                    else:
                        raise ValueError(
                            f'unexpected content type: {content_type}')
                except (TypeError, ValueError):
                    return HTTPResponse(self, status_code=HTTPStatus.BAD_REQUEST)
            else:
                self.query = {}
            if isinstance(self.query, dict):
                self.query = {
                    key: value[0]
                         if isinstance(value, list) and len(value) == 1 else
                         value
                    for key, value in self.query.items()
                }

            # Try various methods to render the path, using the first one that
            # successfully returns a response
            self.store = store.Storage(self.server.config.db)
            for method in (self.try_route, self.try_static, self.try_template):
                if self.command in method.commands:
                    resp = method()
                    if resp is not None:
                        return resp
        except Exception as exc:
            if self.server.config.production:
                self.server.handle_error(self, self.client_address)
            else:
                self.server.exception = exc
                raise
            return HTTPResponse(self, status_code=HTTPStatus.INTERNAL_SERVER_ERROR)
        return HTTPResponse(self, status_code=HTTPStatus.NOT_FOUND)

    def json(self):
        """
        Decode the body of the request as a JSON object. Note this handler can
        be called once, and only once, as it reads the request body on-demand.

        .. warning::

            This method does not check the Content-Type header, and simply
            trusts that the request body is a valid JSON object. Wrap in
            exception handlers as appropriate!
        """
        try:
            body_len = int(self.headers['Content-Length'])
        except (KeyError, ValueError, TypeError):
            body_len = 0
        if body_len > 0:
            body = self.rfile.read(body_len)
            self.headers['Content-Length'] = '0'
        else:
            raise ValueError('invalid Content-Length for JSON')
        return json.loads(body)

    def do_HEAD(self):
        """
        Handle HTTP HEAD requests. See :meth:`get_response` for more
        information.
        """
        resp = self.get_response()
        resp.check_cached()
        resp.check_ranges()
        with suppress(BrokenPipeError, ConnectionResetError):
            resp.send_headers()

    def do_GET(self):
        """
        Handle HTTP GET requests. See :meth:`get_response` for more
        information.
        """
        resp = self.get_response()
        resp.check_cached()
        resp.check_ranges()
        with suppress(BrokenPipeError, ConnectionResetError):
            resp.send_headers()
            resp.send_body()

    def do_DELETE(self):
        """
        Handle HTTP DELETE requests. See :meth:`get_response` for more
        information.
        """
        resp = self.get_response()
        with suppress(BrokenPipeError, ConnectionResetError):
            resp.send_headers()
            resp.send_body()

    def do_PUT(self):
        """
        Handle HTTP PUT requests. See :meth:`get_response` for more
        information.
        """
        resp = self.get_response()
        with suppress(BrokenPipeError, ConnectionResetError):
            resp.send_headers()
            resp.send_body()

    def do_POST(self):
        """
        Handle HTTP POST requests. See :meth:`get_response` for more
        information.
        """
        resp = self.get_response()
        with suppress(BrokenPipeError, ConnectionResetError):
            resp.send_headers()
            resp.send_body()


class Messages:
    """
    This is a trivial class which is used to buffer up to *maxlen* messages,
    which are simple strings, for display to the user at some future point.

    The :meth:`show` method is used to add a message to the buffer, and
    :meth:`drain` to retrieve all messages from the buffer as a list of
    strings. Instances of the class are thread-safe and may be used from
    multiple threads without additional locking.
    """
    def __init__(self, maxlen=20):
        self._lock = Lock()
        self._items = deque(maxlen=maxlen)

    def show(self, msg):
        """
        Add *msg* to the buffer. If the buffer is already full (has *maxlen*
        items in it), the oldest message is discarded and the new message is
        appended.
        """
        with self._lock:
            self._items.append(msg)

    def drain(self):
        """
        Empties the buffer, returning all messages currently stored within it
        as a :class:`list`.
        """
        with self._lock:
            result = list(self._items)
            self._items.clear()
        return result


class HTTPThread(Thread):
    """
    The blinkenxmas HTTP thread class wraps an instance of :class:`HTTPServer`
    in a :class:`~threading.Thread` for background execution. Instances of this
    class may be used as a context manager that will start the thread upon
    entry, and stop it (re-raising any exception that occurred during
    execution) on exit. This is the recommended method of running this thread.

    :param argparse.Namespace config:
        The application configuration

    :param Messages messages:
        A buffer for messages to be relayed to the user

    :param queue.Queue queue:
        The queue to submit animations to for transmission to the broker
    """
    def __init__(self, config, messages, queue):
        super().__init__(target=self.serve, daemon=True)
        mimetypes.init()
        HTTPServer.address_family, addr = get_best_family(
            config.httpd_bind, config.httpd_port)
        self.httpd = HTTPServer(addr[:2], HTTPRequestHandler)
        self.httpd.queue = queue
        self.httpd.config = config
        self.httpd.messages = messages
        self.httpd.camera = {
            'none':      lambda config: None,
            'files':     cameras.FilesSource,
            'picamera':  cameras.PiCameraSource,
            'gstreamer': cameras.GStreamerSource,
        }[config.camera_type.strip().lower()](config)
        self.httpd.calibration = calibrate.Calibration(
            config, self.httpd.messages)
        self.httpd.exception = None
        self._shutdown_needed = False

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *exc_info):
        self.stop()
        if self.httpd.exception:
            raise self.httpd.exception

    def stop(self):
        """
        Stop the HTTP background thread.
        """
        if self._shutdown_needed:
            self.httpd.shutdown()

    def serve(self):
        """
        The "main" routine of the background thread. Mostly this just calls
        :meth:`http.server.HTTPserver.serve_forever`.
        """
        try:
            host, port = self.httpd.socket.getsockname()[:2]
            hostname = socket.gethostname()
            self.httpd.logger.warning(f'Serving on {host} port {port}')
            self.httpd.logger.warning(f'http://{hostname}:{port}/ ...')
            self._shutdown_needed = True
            self.httpd.serve_forever()
        except Exception as exc:
            self.httpd.exception = exc
