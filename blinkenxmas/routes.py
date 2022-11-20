import io
import json
from http import HTTPStatus

from colorzero import Color

from .httpd import route
from .http import HTTPResponse


def compress(frames):
    """
    Given a list of lists of :class:`~colorzero.Color` instances representing
    the color of each LED in each frame, return a list of lists of ``(index, r,
    g, b)`` tuples containing only those color positions that actually change
    each frame.
    """
    def convert(frames):
        for frame in frames:
            yield [color.rgb_bytes for color in frame]

    def diff(frames):
        last = None
        for frame in frames:
            if last is None:
                yield [
                    (index,) + color
                    for index, color in enumerate(frame)
                    if any(color)
                ]
            else:
                yield [
                    (index,) + color
                    for index, color in enumerate(frame)
                    if last[index] != color
                ]
            last = frame

    return list(diff(convert(frames)))


@route('/')
def home(request):
    return HTTPResponse(
        request, status_code=HTTPStatus.MOVED_PERMANENTLY,
        headers={'Location': '/index.html'})


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
        data = request.json()
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
def preview(request, name=None):
    try:
        data = request.json()
        # TODO Assert that the structure is correct (voluptuous?)
    except ValueError:
        return HTTPResponse(request, status_code=HTTPStatus.BAD_REQUEST)
    else:
        request.server.queue.put(data)
        return HTTPResponse(request, status_code=HTTPStatus.NO_CONTENT)


@route('/preview/:name', 'POST')
def preview_preset(request, name):
    try:
        data = request.server.store[name]
    except KeyError:
        return HTTPResponse(request, status_code=HTTPStatus.NOT_FOUND)
    else:
        request.server.queue.put(data)
        return HTTPResponse(request, status_code=HTTPStatus.NO_CONTENT)


@route('/animation/:name', 'POST')
def generate_animation(request, name):
    try:
        anim = request.animations[name]
        params = {
            name:
                int(value) if anim.params[name].input_type == 'range' else
                float(value) if anim.params[name].input_type == 'number' else
                Color(value) if anim.params[name].input_type == 'color' else
                str(value)
            for name, value in request.json().items()
        }
        data = anim.function(
            request.server.config.led_count,
            request.server.config.fps,
            **params)
    except (ValueError, TypeError) as e:
        raise
        return HTTPResponse(
            request, body=str(e), status_code=HTTPStatus.BAD_REQUEST)
    else:
        return HTTPResponse(request, body=json.dumps(compress(data)))
