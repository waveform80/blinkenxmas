import io
import json
from http import HTTPStatus

from colorzero import Color

from .httpd import route
from .http import HTTPResponse, DummyResponse


@route('/')
def home(request):
    return HTTPResponse(
        request, status_code=HTTPStatus.MOVED_PERMANENTLY,
        headers={'Location': '/index.html'})


@route('/preset/<name>', 'GET')
def get_preset(request, name):
    try:
        data = request.store.presets[name]
    except KeyError:
        return HTTPResponse(request, status_code=HTTPStatus.NOT_FOUND)
    return HTTPResponse(request, body=json.dumps(data))


@route('/preset/<name>', 'DELETE')
def del_preset(request, name):
    try:
        del request.store.presets[name]
    except KeyError:
        return HTTPResponse(request, status_code=HTTPStatus.NOT_FOUND)
    return HTTPResponse(request, status_code=HTTPStatus.NO_CONTENT)


@route('/preset/<name>', 'PUT')
def set_preset(request, name):
    try:
        data = request.json()
        # TODO Assert that the structure is correct (voluptuous?)
    except ValueError:
        return HTTPResponse(request, status_code=HTTPStatus.BAD_REQUEST)
    if name in request.store.presets:
        code = HTTPStatus.CREATED
        headers= {'Location': '/preset/' + name}
    else:
        code = HTTPStatus.NO_CONTENT
        headers = {}
    request.store.presets[name] = data
    return HTTPResponse(request, status_code=code, headers=headers)


@route('/preview', 'POST')
def preview(request):
    try:
        data = request.json()
    except ValueError:
        return HTTPResponse(request, status_code=HTTPStatus.BAD_REQUEST)
    else:
        # TODO Assert that the structure is correct (voluptuous?)
        request.server.queue.put(data)
        return HTTPResponse(request, status_code=HTTPStatus.NO_CONTENT)


@route('/show/<name>', 'GET')
@route('/show/<name>', 'POST')
def preview_preset(request, name):
    try:
        data = request.store.presets[name]
    except KeyError:
        return HTTPResponse(request, status_code=HTTPStatus.NOT_FOUND)
    else:
        # TODO Assert that the structure is correct (voluptuous?)
        request.server.queue.put(data)
        if request.command == 'POST':
            return HTTPResponse(request, status_code=HTTPStatus.NO_CONTENT)
        else:
            return HTTPResponse(
                request, status_code=HTTPStatus.SEE_OTHER,
                headers={'Location': '/index.html'})


@route('/animation/<name>', 'POST')
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
        return HTTPResponse(
            request, body=str(e), status_code=HTTPStatus.BAD_REQUEST)
    else:
        # TODO Assert that the structure is correct (voluptuous?)
        data = [[led.html for led in frame] for frame in data]
        return HTTPResponse(request, body=json.dumps(data))


@route('/live-preview.mjpg', 'GET')
def calibration_preview(request):
    request.close_connection = False
    request.send_response(200)
    # Don't cache the response... no, really don't
    request.send_header('Age', 0)
    request.send_header('Cache-Control', 'no-cache, private')
    request.send_header('Pragma', 'no-cache')
    # Dreadful hack which tells the browser this resource contains several
    # MIME "things" which should replace the original as each is received
    request.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=--FRAME')
    request.end_headers()
    request.server.camera.add_client(request)
    return DummyResponse()


@route('/angle<angle>_base.jpg', 'GET')
def calibration_base(request, angle):
    try:
        angle = int(angle, base=10)
    except ValueError:
        return HTTPResponse(request, status_code=HTTPStatus.NOT_FOUND)
    try:
        base = request.server.angles[angle][None]
    except KeyError:
        # No base image exists for this angle; switch off the LEDs and capture
        # one
        request.server.queue.put([])
        # XXX Wait? May not be necessary given camera warm-up time
        base = request.server.camera.capture(angle)
        request.server.angles[angle] = {None: base}
    return HTTPResponse(request, body=base, mime_type='image/jpeg')
