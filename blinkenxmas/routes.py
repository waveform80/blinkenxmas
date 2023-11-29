import io
import json
from http import HTTPStatus

from colorzero import Color

from .httpd import route
from .http import HTTPResponse, DummyResponse
from .calibrate import Angle, Positions


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
    else:
        return HTTPResponse(request, mime_type='application/json',
                            body=json.dumps(data))


@route('/preset/<name>', 'DELETE')
def del_preset(request, name):
    try:
        del request.store.presets[name]
    except KeyError:
        return HTTPResponse(request, status_code=HTTPStatus.NOT_FOUND)
    else:
        return HTTPResponse(request, status_code=HTTPStatus.NO_CONTENT)


@route('/preset/<name>', 'PUT')
def set_preset(request, name):
    try:
        data = request.json()
        # TODO Assert that the structure is correct (voluptuous?)
    except ValueError:
        return HTTPResponse(request, status_code=HTTPStatus.BAD_REQUEST)
    if name in request.store.presets:
        code = HTTPStatus.NO_CONTENT
        headers = {}
    else:
        code = HTTPStatus.CREATED
        headers= {'Location': '/preset/' + name}
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
    #request.close_connection = False
    request.send_response(200)
    # Don't cache the response... no, really don't
    request.send_header('Age', 0)
    request.send_header('Cache-Control', 'no-cache, private')
    # Dreadful hack which tells the browser this resource contains several
    # MIME "things" which should replace the original as each is received
    request.send_header(
        'Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
    request.end_headers()

    request.server.camera.add_client(request)
    try:
        while True:
            with request.server.camera.frame_ready:
                request.server.camera.frame_ready.wait()
                frame = request.server.camera.frame
            request.wfile.write(b'--FRAME\r\n')
            request.send_header('Content-Type', 'image/jpeg')
            request.send_header('Content-Length', len(frame))
            request.end_headers()
            request.wfile.write(frame)
            request.wfile.write(b'\r\n')
    except (BrokenPipeError, ConnectionResetError):
        pass
    finally:
        request.server.camera.remove_client(request)
    return DummyResponse(request)


@route('/angle<angle>_base.jpg', 'GET')
def calibration_base(request, angle):
    try:
        angle = int(angle, base=10)
    except ValueError:
        return HTTPResponse(request, status_code=HTTPStatus.NOT_FOUND)

    try:
        calibration = request.server.angles[angle]
    except KeyError:
        calibration = request.server.angles[angle] = Angle(
            angle, request.server.camera, request.server.queue,
            request.server.config.led_strips)
    return HTTPResponse(request, body=calibration.base, mime_type='image/jpeg')


@route('/angle<angle>_mask.json', 'GET')
def calibration_mask(request, angle):
    try:
        angle = int(angle, base=10)
        calibration = request.server.angles[angle]
    except (KeyError, ValueError):
        return HTTPResponse(request, status_code=HTTPStatus.NOT_FOUND)

    return HTTPResponse(request, body=json.dumps(calibration.mask),
                        mime_type='application/json')


@route('/angle<angle>_state.json', 'GET')
def calibration_state(request, angle):
    try:
        angle = int(angle, base=10)
        calibration = request.server.angles[angle]
    except (KeyError, ValueError):
        return HTTPResponse(request, status_code=HTTPStatus.NOT_FOUND)

    return HTTPResponse(request, body=json.dumps({
        'progress':  calibration.progress,
        'mask':      calibration.mask,
        'positions': calibration.positions,
        'scores':    calibration.scores,
    }), mime_type='application/json')


@route('/calibrate.html', 'GET')
def calibration_run(request):
    try:
        angle = int(request.query['angle'])
        mask = [
            (float(x), float(y))
            for x, y in json.loads(request.query['mask'])
            if 0 <= float(x) <= 1 and 0 <= float(y) <= 1
        ]
        calibration = request.server.angles[angle]
    except (KeyError, ValueError):
        return HTTPResponse(request, status_code=HTTPStatus.NOT_FOUND)

    calibration.start(mask)

    # Fall-through to render the calibrate.html.pt template as the response
    return None


@route('/cancel.html', 'GET')
def calibration_cancel(request):
    try:
        angle = int(request.query['angle'])
        calibration = request.server.angles.pop(angle)
    except (KeyError, ValueError):
        return HTTPResponse(request, status_code=HTTPStatus.NOT_FOUND)

    calibration.stop()
    return HTTPResponse(
        request, status_code=HTTPStatus.SEE_OTHER,
        headers={'Location': '/index.html'})
