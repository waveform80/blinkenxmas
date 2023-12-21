import io
import tempfile
import mimetypes
import datetime as dt
import email.parser
import email.policy
import email.utils as eut
from pathlib import Path
from http import HTTPStatus
from contextlib import suppress, closing
from collections.abc import Mapping, MutableMapping


class HTTPHeaders(MutableMapping):
    canonical = {
        s.lower(): s
        # The few HTTP headers with "canonical" capitalization that doesn't
        # follow the dash-separated title-case convention. There's a few more
        # of these that can be found in the IANA HTTP Field Name Registry at
        # https://www.iana.org/assignments/http-fields/http-fields.xhtml but
        # these are the only ones we're likely to care about
        for s in ['ETag', 'TE', 'WWW-Authenticate']
    }

    def __init__(self, iterable=None, **kwargs):
        self._data = {}
        if iterable is not None:
            if isinstance(iterable, Mapping):
                for key, value in iterable.items():
                    self[key] = value
            else:
                for key, value in iterable:
                    self[key] = value
        for key, value in kwargs.items():
            self[key.replace('_', '-')] = value

    def __repr__(self):
        return f'{self.__class__.__name__}({self._data!r})'

    @staticmethod
    def _http_name(s):
        try:
            return HTTPHeaders.canonical[s.lower()]
        except KeyError:
            return '-'.join(p.title() for p in s.split('-'))

    def __getitem__(self, key):
        return self._data[self._http_name(key)]

    def __delitem__(self, key):
        del self._data[self._http_name(key)]

    def __setitem__(self, key, value):
        self._data[self._http_name(key)] = value

    def __iter__(self):
        for key in self._data:
            yield key

    def __len__(self):
        return len(self._data)

    def __contains__(self, key):
        return self._http_name(key) in self._data


def merge(ranges):
    """
    Given a list of *ranges* in ascending order, this generator function
    returns the list with any overlapping ranges consolidated into individual
    ranges. For example::

        >>> list(merge([range(0, 5), range(4, 10)]))
        [range(0, 10)]
        >>> list(merge([range(0, 5), range(5, 10)]))
        [range(0, 10)]
        >>> list(merge([range(0, 5), range(6, 10)]))
        [range(0, 5), range(6, 10)]
    """
    start = stop = None
    for r in ranges:
        if start is None:
            start = r.start
        elif r.start > stop:
            yield range(start, stop)
            start = r.start
        stop = r.stop
    if start is not None:
        yield range(start, stop)


COPY_BUFSIZE = 64 * 1024
def transfer(source, target, *, byterange=None):
    """
    Transfer *byterange* bytes (a :class:`range` object), or all bytes (if
    *byterange* is :data:`None`, the default) from *source* to *target*.

    The *target* must implement a ``write`` method, and the *source* must at
    the very least implement a ``read`` method, but preferably a ``readinto``
    method (which will permit a single static buffer to be used during the
    transfer). If *byterange* is not :data:`None`, the *source* must
    additionally implemented ``seek``. No attempt is made to seek the *target*;
    bytes are simply written to it at its current position.
    """
    if byterange is not None:
        if byterange.step != 1:
            raise ValueError('step in byterange must be 1')
        source.seek(byterange.start)
        length = len(byterange)
    else:
        length = None
    if length is not None and length < COPY_BUFSIZE:
        # Fast path for trivially short copies
        target.write(source.read(length))
        return
    # Cache methods to avoid repeated lookup, and to discover if we can
    # pre-allocate the transfer buffer
    write = target.write
    try:
        readinto = source.readinto
    except AttributeError:
        read = source.read
        if length is None:
            while True:
                buf = read(COPY_BUFSIZE)
                if not buf:
                    break
                write(buf)
        else:
            while length > 0:
                buf = read(min(COPY_BUFSIZE, length))
                length -= len(buf)
                write(buf)
    else:
        with memoryview(bytearray(COPY_BUFSIZE)) as buf:
            if length is None:
                while True:
                    n = readinto(buf)
                    if not n:
                        break
                    with buf[:n] as read_buf:
                        write(read_buf)
            else:
                while length > 0:
                    with buf[:min(COPY_BUFSIZE, length)] as read_buf:
                        n = readinto(read_buf)
                    with buf[:n] as read_buf:
                        write(read_buf)
                    length -= n


def parse_content_value(s):
    """
    Parse the content of an HTTP Content-* header's value, *s*. The result is a
    tuple of (value, attrs) where *value* is the principal value (the part
    before the first semi-colon, if any), and *attrs* is a dictionary of
    attributes that follow the principal value.
    """
    value, *attrs = (part.strip() for part in s.split(';'))
    return value, {
        key.strip().lower(): value.strip('"')
        for attr in attrs
        for key, value in (attr.split('='),)
    }


# This must be greater than 72 bytes to ensure the splitting algorithm can
# operate with all valid boundary markers
SPLIT_MULTIPART_BUFSIZE = 64 * 1024
def split_multipart(request):
    """
    Given *request*, a :class:`~blinkenxmas.httpd.HTTPRequestHandler`, which
    must have a Content-Type of multipart/*, yield each part of the multipart
    body as a separate (headers, content) tuple. The *headers* are returned as
    a :class:`HTTPHeaders` instance, and the *content* as a file-like object.
    """

    def get_boundary():
        s = request.headers.get('Content-Type', '')
        value, attrs = parse_content_value(s)
        mime_type, mime_subtype = value.split('/', 1)
        if mime_type != 'multipart':
            raise ValueError(
                f'MIME-type {s!r} is not a multipart/*')
        try:
            if not 1 <= len(attrs['boundary']) <= 70:
                raise ValueError(
                    f'Boundary definition in {s!r} has a silly length')
            encoding = attrs.get('charset', 'utf-8')
            return attrs['boundary'].encode(encoding)
        except KeyError:
            raise ValueError(f'Missing boundary definition in {s!r}')

    def discard_and_fill(buf, size, discard):
        # Discard bytes from the start of *buf*, moving later bytes back to the
        # start. Then fill later bytes from request.rfile. Returns the new
        # number of valid bytes present in buf
        assert discard >= 0
        if discard > 0:
            if discard < size:
                buf[:size - discard] = buf[discard:size]
                size -= discard
            else:
                size = 0
        assert size < len(buf)
        return size + request.rfile.readinto(buf[size:])

    boundary = b'--' + get_boundary()
    parser = email.parser.BytesHeaderParser(policy=email.policy.HTTP)
    buffer = bytearray(SPLIT_MULTIPART_BUFSIZE)
    mem = memoryview(buffer)
    size = 0
    headers = content = None

    size = discard_and_fill(mem, size, 0)
    while size > 0:
        try:
            # Try and find the next multipart boundary
            index = buffer.index(boundary, 0, size)
        except ValueError:
            # No multipart boundary found in the buffer. If content is None,
            # we've yet to find a multipart boundary so everything so far is
            # preamble and can be ignored. Otherwise...
            if content is not None:
                if size < len(boundary):
                    # This is the degenerate case where we've reached the end
                    # of the stream but there's no final marker; assume all
                    # remaining content is part of the final part
                    content.write(mem[:size])
                    break
                else:
                    # Otherwise, dump the buffer to the content, and keep
                    # len(boundary)-1 bytes within the buffer in case we had a
                    # boundary prefix at the end
                    keep = len(boundary) - 1
                    content.write(mem[:size - keep])
                    size = discard_and_fill(mem, size, size - keep)
        else:
            if content is not None:
                content.write(mem[:index])
                content.seek(0)
                yield headers, content
            content = None
            index += len(boundary)
            size = discard_and_fill(mem, size, index)
            # Optional linear white-space is permitted after the boundary
            index = 0
            while index < size and mem[index] in (ord(b' '), ord(b'\t')):
                index += 1
            size = discard_and_fill(mem, size, index)
            if size < 2 or mem[:2] == b'--':
                break
            content = tempfile.SpooledTemporaryFile(
                max_size=SPLIT_MULTIPART_BUFSIZE)
            if mem[:2] != b'\r\n':
                raise ValueError('Invalid boundary found')
            try:
                index = buffer.index(b'\r\n\r\n', 0, size)
            except IndexError:
                # Headers are larger than len(buffer); this is potentially
                # abusive (assuming len(buffer) is sane), so reject it
                raise ValueError('Headers exceed buffer size')
            else:
                if index > 0:
                    headers = HTTPHeaders(
                        parser.parsebytes(mem[2:index + 4].tobytes()).items())
                    size = discard_and_fill(mem, size, index + 4)
                else:
                    headers = HTTPHeaders()
                    size = discard_and_fill(mem, size, 4)
            # Only the first boundary found is permitted to have no CR-LF
            # prefix (because the HTTP header parser has already eaten the
            # preceding ones); subsequent boundaries *must* begin with it
            if boundary[:2] == b'--':
                boundary = b'\r\n' + boundary
    if content is not None:
        content.seek(0)
        yield headers, content


def parse_formdata(request):
    """
    Given *request*, a :class:`~blinkenxmas.httpd.HTTPRequestHandler`, which
    must have a Content-Type of "multipart/form-data", split the multipart body
    into its constituent parts, and return a :class:`dict` mapping form names
    to their corresponding content.

    Short text or binary values are returned as :class:`str` or :class:`bytes`
    values respectively. Anything with a "filename" attribute, or which exceeds
    a relatively large string size (currently 64KB) will be returned as a
    file-like object.
    """
    value, attrs = parse_content_value(request.headers['Content-Type'])
    if value != 'multipart/form-data':
        raise ValueError(f'Invalid Content-Type: {value!r}')
    query = {}
    for headers, content in split_multipart(request):
        try:
            disposition = headers['Content-Disposition']
        except KeyError:
            continue
        else:
            disposition, attrs = parse_content_value(disposition)
            if disposition != 'form-data':
                continue
            try:
                name = attrs['name']
            except KeyError:
                continue
            mime_type, attrs = parse_content_value(
                headers.get('Content-Type', 'text/plain'))
            is_short = content.seek(0, io.SEEK_END) <= SPLIT_MULTIPART_BUFSIZE
            content.seek(0)
            if mime_type.startswith('text/'):
                content = io.TextIOWrapper(
                    content, encoding=attrs.get('charset', 'utf-8'),
                    errors='ignore')
            if is_short and 'filename' not in attrs:
                query[name] = content.read()
            else:
                query[name] = content
    return query


class DummyResponse:
    """
    An HTTP response that does nothing; useful for things that need to keep a
    client connection for whatever reason.
    """
    def __init__(self, request, **kwargs):
        self.headers = HTTPHeaders()

    def check_cached(self):
        pass

    def check_ranges(self):
        pass

    def send_headers(self):
        pass

    def send_body(self):
        pass


class HTTPResponse:
    """
    An HTTP response.

    The *request* is the :class:`http.server.BaseHTTPRequestHandler` instance
    representing the original request. The *body* (which forms the body of the
    response) may contain a :class:`str`, :class:`bytes`, or a file-like
    object.

    Other parameters represent typical HTTP headers and, if not given, will be
    derived from the body where possible.

    :param http.server.BaseHTTPRequestHandler request:
        The request instance representing the client's request.

    :param body:
        The object containing the body of the response. Ultimately this will
        be converted to a file-like object (:class:`~io.IOBase` descendent)
        in the :attr:`stream` attribute. This can be:

        * A file-like object in which case it will be used directly as the
          value of :attr:`stream`.

        * A :class:`str`. This will be converted to a :class:`io.BytesIO`
          stream with UTF-8 encoding.

        * A :class:`bytes` string. This will be used verbatim as the content of
          a :class:`io.BytesIO` stream.

        * A :class:`pathlib.Path`. This will be opened as a binary file.

    :param http.HTTPStatus status_code:
        The HTTP status code of the response. Expected to be a
        :class:`http.HTTPStatus` attribute. Defaults to
        :attr:`http.HTTPStatus.OK`.

    :param int content_length:
        The number of bytes in the response body. If not specified, and the
        body stream is seekable, this will be filled out automatically.

    :param bool accept_ranges:
        If :data:`True` (the default), handle "bytes" ranges automatically.

        Specifically, if this is set, the response will automatically handle
        sending only those ranges requested. It will re-write the
        "Content-Length", "Content-Type", "Content-Range", and "Accept-Ranges"
        headers accordingly as necessary.

    :param str filename:
        The original filename of the body (if any). If not specified, will be
        filled out automatically from the ``name`` property of the
        :attr:`stream` if it exists.

    :param str mime_type:
        The MIME type of the response body. If not specified, will be
        determined automatically from the *filename* (if that was specified or
        determined).

    :param str encoding:
        The encoding of the response body. If not specified, will be determined
        automatically from the *filename* (if that was specified or
        determined).

    :param datetime.datetime last_modified:
        The last modification date of the response body. If this is specified
        it must be a time-zone aware datetime instance. If not specified, will
        be determined automatically (if possible) from the last modification
        date of the file containing the body content.

    :param dict headers:
        Additional headers to include in the response.
    """
    def __init__(self, request, body=None, *, status_code=HTTPStatus.OK,
                 content_length=None, accept_ranges=True, filename=None,
                 mime_type=None, encoding=None, last_modified=None,
                 headers=None):
        self.request = request
        self.accept_ranges = accept_ranges
        self.status_code = HTTPStatus(status_code)
        self._headers = HTTPHeaders(headers)

        if isinstance(body, str):
            self.stream = io.BytesIO(body.encode('utf-8'))
        elif isinstance(body, bytes):
            self.stream = io.BytesIO(body)
        elif isinstance(body, Path):
            self.stream = body.open('rb')
            if filename is None:
                filename = str(body)
        else:
            self.stream = body
            if filename is None:
                with suppress(AttributeError):
                    filename = self.stream.name

        if (
            content_length is None and self.stream is not None and
            self.stream.seekable()
        ):
            content_length = self.stream.seek(0, io.SEEK_END)
            self.stream.seek(0)
        if mime_type is None and filename is not None:
            mime_type, encoding = mimetypes.guess_type(filename)
        if last_modified is None and filename is not None:
            with suppress(FileNotFoundError, PermissionError):
                last_modified = dt.datetime.fromtimestamp(
                    Path(filename).stat().st_mtime_ns / 1_000_000_000,
                    tz=dt.timezone.utc)

        if content_length is not None:
            self.headers['Content-Length'] = content_length
        if mime_type is not None:
            self.headers['Content-Type'] = mime_type
        if encoding is not None:
            self.headers['Content-Encoding'] = encoding
        if last_modified is not None:
            self.headers['Last-Modified'] = eut.format_datetime(
                last_modified, usegmt=True)

    def __repr__(self):
        headers = '\n'.join(
            f'{key}: {value}'
            for key, value in self.headers.items()
        )
        return (
            f'{self.request.protocol_version} {self.status_code.value} '
            f'{self.status_code.phrase}\n{headers}'
        )

    @property
    def headers(self):
        return self._headers

    def _no_content(self):
        with suppress(AttributeError):
            self.stream.close()
        self.stream = None
        self.headers.pop('Content-Length', None)

    def _check_last_modified(self):
        try:
            last_modified = eut.parsedate_to_datetime(
                self.headers['Last-Modified'])
            if_modified_since = eut.parsedate_to_datetime(
                self.request.headers['If-Modified-Since'])
        except (KeyError, ValueError, OverflowError, TypeError, IndexError):
            return False
        else:
            if if_modified_since.tzinfo is None:
                if_modified_since = if_modified_since.replace(
                    tzinfo=dt.timezone.utc)
            return last_modified <= if_modified_since

    def _check_etag(self):
        try:
            etag = self.headers['ETag']
            if_none_match = {
                tag.strip()
                for tag in self.request.headers['If-None-Match'].split(',')
            }
        except KeyError:
            return False
        else:
            return etag in if_none_match

    def check_cached(self):
        """
        Check if the response is fresh in the client's cache.

        If the request is GET or HEAD with appropriate caching tests
        (``If-Modified-Since`` and/or ``If-None-Match``), and the response has
        appropriate caching responses then this method will (if the response is
        still "fresh" in the client's cache), modify the :attr:`status_code` to
        :attr:`http.HTTPStatus.NOT_MODIFIED` and set :attr:`stream` to
        :data:`None`.
        """
        cached = (
            self.request.command in ('GET', 'HEAD') and
            self.status_code.value == 200 and
            # NOTE: Technically, this is wrong. ETag takes strict precedence
            # over Last-Modified; if both are present, Last-Modified should be
            # ignored. But currently we don't use ETag so it's irrelevant
            (self._check_etag() or self._check_last_modified())
        )
        if cached:
            self.status_code = HTTPStatus.NOT_MODIFIED
            self._no_content()

    def _parse_ranges(self):
        length = self.headers['Content-Length']
        ranges = []
        parts = (
            s.strip() for s in
            self.request.headers['Range'][len('bytes='):].split(',')
            if s.strip())
        for part in parts:
            if part.startswith('-'):
                # Last n bytes
                n = int(part)
                ranges.append(range(length + n, length))
            elif part.endswith('-'):
                # From byte n
                n = int(part.rstrip('-'))
                ranges.append(range(n, length))
            else:
                # Normal range
                start, finish = (int(n) for n in part.split('-', 1))
                if finish < start:
                    raise ValueError(f'Backwards range, {finish} < {start}')
                ranges.append(range(start, finish + 1))
        return ranges

    def _merge_ranges(self, ranges):
        length = self.headers['Content-Length']
        for r in ranges:
            if not (0 <= r.start < length and 0 <= r.stop - 1 < length):
                self.headers['Content-Range'] = (
                    f'bytes {r.start}-{r.stop - 1}/{length}')
                raise ValueError('Requested bytes outside content length')
        sorted_ranges = sorted(ranges, key=lambda r: r.start)
        merged_ranges = list(merge(sorted_ranges))
        if sorted_ranges == merged_ranges:
            # If we consolidated nothing, return ranges in their defined
            # order (which we SHOULD according to the HTTP RFC)
            return ranges
        else:
            # Otherwise all bets are off
            return merged_ranges

    def check_ranges(self):
        """
        Check if the request wanted a partial response (if the "Range:" header
        was included).

        If the *accept_ranges* parameter was :data:`True` at construction (the
        default), and a range or ranges were requested, this handles re-writing
        the response accordingly (this may include re-writing the status code,
        "Content-Length", "Content-Type", "Content-Range", and "Accept-Ranges"
        headers).
        """
        if self.accept_ranges and self.status_code.value == 200:
            self.headers.setdefault('Accept-Ranges', 'bytes')
        ranged = (
            self.headers.get('Accept-Ranges', '') == 'bytes' and
            self.status_code.value == 200 and
            self.request.headers.get('Range', '').startswith('bytes=') and
            'Content-Length' in self.headers
        )
        if ranged:
            try:
                self.headers['Content-Length'] = int(
                    self.headers['Content-Length'])
                ranges = self._parse_ranges()
            except ValueError:
                self.status_code = HTTPStatus.BAD_REQUEST
                self._no_content()
                return
            try:
                ranges = self._merge_ranges(ranges)
            except ValueError:
                self.status_code = HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE
                self._no_content()
                return
            if ranges:
                self.status_code = HTTPStatus.PARTIAL_CONTENT
                self.headers['Content-Range'] = ranges

    def send_headers(self):
        """
        Transmit the response's headers to the client.
        """
        self.request.send_response(self.status_code.value)
        num_ranges = (
            len(self.headers['Content-Range'])
            if self.status_code == HTTPStatus.PARTIAL_CONTENT
            and isinstance(self.headers['Content-Range'], list) else 0)
        for key, value in self.headers.items():
            # NOTE: Below we alter the headers we're going to send
            # on-the-fly, we don't alter any headers that are stored as we
            # need the original values of each header later
            if key == 'Content-Range':
                if num_ranges == 1:
                    r = value[0]
                    length = int(self.headers['Content-Length'])
                    value = f'bytes {r.start}-{r.stop - 1}/{length}'
                elif num_ranges > 1:
                    # Skip if multipart; will be sent in multipart header
                    continue
            elif key == 'Content-Length':
                if num_ranges == 1:
                    r = self.headers['Content-Range'][0]
                    value = len(r)
                elif num_ranges > 1:
                    # Skip if multipart; unknown in this case
                    continue
            elif key == 'Content-Type':
                if num_ranges > 1:
                    # Skip; we'll force this later (in case Content-Type
                    # is missing from the headers)
                    continue
            self.request.send_header(key, value)
        if num_ranges > 1:
            self.request.send_header(
                'Content-Type', 'multipart/byteranges; boundary=BOUNDARY')
        self.request.end_headers()

    def send_body(self):
        """
        Transmit the response body to the client.
        """
        if self.stream is None:
            return
        with closing(self.stream):
            num_ranges = (
                len(self.headers['Content-Range'])
                if self.status_code == HTTPStatus.PARTIAL_CONTENT
                and isinstance(self.headers['Content-Range'], list) else 0)
            if num_ranges == 0:
                transfer(self.stream, self.request.wfile)
            elif num_ranges == 1:
                transfer(self.stream, self.request.wfile,
                         byterange=self.headers['Content-Range'][0])
            else:
                length = self.headers['Content-Length']
                for r in self.headers['Content-Range']:
                    self.request.wfile.write(b'--BOUNDARY\r\n')
                    if 'Content-Type' in self.headers:
                        self.request.send_header(
                            'Content-Type', self.headers['Content-Type'])
                    self.request.send_header(
                        'Content-Range', f'bytes {r.start}-{r.stop - 1}/{length}')
                    self.request.end_headers()
                    transfer(self.stream, self.request.wfile, byterange=r)
                    self.request.wfile.write(b'\r\n')
                self.request.wfile.write(b'--BOUNDARY--\r\n')
