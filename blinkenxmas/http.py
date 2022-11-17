import io
import mimetypes
import email.utils as eut
from http import HTTPStatus
from shutil import copyfileobj


class HTTPResponse:
    def __init__(self, request, body=None, *, status_code=HTTPStatus.OK,
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
            self.headers['Last-Modified'] = eut.format_datetime(
                last_modified, usegmt=True)

    def __repr__(self):
        headers = '\n'.join(f'{key}: {value}' for key, value in self.headers)
        return (
            f'{self.request.protocol_version} {self.status_code.value} '
            f'{self.status_code.phrase}\n{headers}\n\n'
        )

    def send_headers(self):
        self.request.send_response(self.status_code.value)
        for key, value in self.headers.items():
            self.request.send_header(key, value)
        self.request.end_headers()

    def send_body(self):
        if self.stream is not None:
            copyfileobj(self.stream, self.request.wfile)
            self.stream.close()
