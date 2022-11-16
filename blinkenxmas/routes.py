import io
import json
from http import HTTPStatus

from .httpd import route
from .http import HTTPResponse


@route('/')
def home(request):
    return HTTPResponse(
        status_code=HTTPStatus.MOVED_PERMANENTLY,
        headers={'Location': 'index.html'})


@route('/preset/:name', 'GET')
def get_preset(request, name):
    try:
        data = request.server.store[name]
    except KeyError:
        return HTTPResponse(request, status_code=HTTPStatus.NOT_FOUND)
    return HTTPResponse(request, body=json.dumps(data))


@route('/preset/:name', 'DELETE')
def del_preset(request, name):
    try:
        del request.server.store[name]
    except KeyError:
        return HTTPResponse(request, status_code=HTTPStatus.NOT_FOUND)
    return HTTPResponse(request, status_code=HTTPStatus.NO_CONTENT)


@route('/preset/:name', 'PUT')
def set_preset(request, name):
    try:
        with io.TextIOWrapper(request.rfile) as f:
            data = json.load(f)
        # TODO Assert that the structure is correct (voluptuous?)
    except ValueError:
        return HTTPResponse(request, status_code=HTTPStatus.BAD_REQUEST)
    if name in request.server.store:
        code = HTTPStatus.CREATED
        headers= {'Location': '/preset/' + name}
    else:
        code = HTTPStatus.NO_CONTENT
        headers = {}
    request.server.store[name] = data
    return HTTPResponse(request, status_code=code, headers=headers)


@route('/preview', 'POST')
@route('/preview/:name', 'POST')
def preview(request, name=None):
    if name is not None:
        try:
            data = request.server.store[name]
        except KeyError:
            return HTTPResponse(request, status_code=HTTPStatus.NOT_FOUND)
    else:
        try:
            with io.TextIOWrapper(request.rfile) as f:
                data = json.load(f)
            # TODO Assert that the structure is correct (voluptuous?)
        except ValueError:
            return HTTPResponse(self, status_code=HTTPStatus.BAD_REQUEST)
    request.server.queue.put(data)
    return HTTPResponse(request, status_code=HTTPStatus.NO_CONTENT)