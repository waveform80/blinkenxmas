import io
import json
from http import HTTPStatus
from urllib.parse import quote

from .httpd import route, Function, Param, HTTPRequestHandler
from .http import HTTPResponse, DummyResponse
from .calibrate import AngleScanner


@route('/')
def home(request):
    """
    This is the handler for the root URL; it simply returns a redirect to
    :file:`/index.html`.
    """
    return HTTPResponse(
        request, status_code=HTTPStatus.MOVED_PERMANENTLY,
        headers={'Location': '/index.html'})


@route('/messages.json', 'GET')
def get_messages(request):
    """
    Drains the :class:`~blinkenxmas.httpd.Messages` instance of all messages
    and returns them in the body of the response as a JSON-encoded list of
    strings.
    """
    return HTTPResponse(
        request, mime_type='application/json',
        body=json.dumps(request.server.messages.drain()))


@route('/animations.json', 'GET')
def get_animations(request):
    "Returns the list of defined animations as a JSON map."
    return HTTPResponse(
        request, mime_type='application/json',
        body=json.dumps({
            # Can't JSON serialize the actual functions ...
            fkey: func._replace(function=None, params={
                pkey: param
                for pkey, param in func.params.items()
                # ... or parameters which aren't tuples (e.g. ParamFPS)
                if isinstance(param, Param)
            })
            for fkey, func in request.animations.items()
        }))


@route('/presets.json', 'GET')
def get_presets(request):
    "Returns the list of defined presets as a JSON array."
    return HTTPResponse(request, mime_type='application/json',
                        body=json.dumps(list(request.store.presets)))


@route('/preset/<name>.json', 'GET')
def get_preset(request, name):
    "Returns the animation frames for the named preset as a JSON array."
    try:
        data = request.store.presets[name]
    except KeyError:
        return HTTPResponse(request, status_code=HTTPStatus.NOT_FOUND)
    else:
        return HTTPResponse(request, mime_type='application/json',
                            body=json.dumps(data))


@route('/preset/<name>.json', 'DELETE')
def del_preset(request, name):
    "Removes the named preset from the store."
    try:
        del request.store.presets[name]
    except KeyError:
        return HTTPResponse(request, status_code=HTTPStatus.NOT_FOUND)
    else:
        request.server.messages.show(f'Removed preset {name}')
        return HTTPResponse(request, status_code=HTTPStatus.NO_CONTENT)


@route('/preset/<name>.json', 'PUT')
def set_preset(request, name):
    "Replaces the named preset with the JSON data from the body of the request."
    try:
        data = request.json()
        # TODO Assert that the structure is correct (voluptuous?)
    except ValueError:
        return HTTPResponse(request, status_code=HTTPStatus.BAD_REQUEST)
    if name in request.store.presets:
        code = HTTPStatus.NO_CONTENT
        headers = {}
        request.server.messages.show(f'Updated preset {name}')
    else:
        code = HTTPStatus.CREATED
        headers= {'Location': f'/preset/{quote(name)}'}
        request.server.messages.show(f'Created preset {name}')
    request.store.presets[name] = data
    return HTTPResponse(request, status_code=code, headers=headers)


@route('/remove', 'POST')
def remove(request):
    "Removes the presets listed in the 'name' of the query."
    try:
        presets = request.query['name']
    except KeyError:
        return HTTPResponse(self, status_code=HTTPStatus.BAD_REQUEST)
    if not isinstance(presets, list):
        presets = [presets]
    for name in presets:
        try:
            del request.store.presets[name]
        except KeyError:
            pass
        else:
            request.server.messages.show(f'Removed preset {name}')
    return HTTPResponse(
        request, status_code=HTTPStatus.SEE_OTHER,
        headers={'Location': '/index.html'})


@route('/preview', 'POST')
def preview(request):
    """
    Previews the animation frames provided by the JSON array in the body of the
    request on the tree.
    """
    data = request.query
    # TODO Assert that the structure is correct (voluptuous?)
    request.server.queue.put(data)
    return HTTPResponse(request, status_code=HTTPStatus.NO_CONTENT)


@route('/show/<name>', 'GET')
@route('/show/<name>', 'POST')
def preview_preset(request, name):
    """
    Retrieves the named preset from the store and sends its animation frames to
    the tree.
    """
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


def generate_animation(request, anim_name, params):
    anim = HTTPRequestHandler.animations[anim_name]
    kwargs = {
        key: anim.params[key].value(value)
        for key, value in params.items()
        if key in anim.params
        and isinstance(anim.params[key], Param)
    }
    # Convert None for values missing from the submitted form; this is
    # principally to support controls like "checkbox" which are absent from
    # the submitted dataset when unchecked
    kwargs.update({
        key: param.value(None)
        for key, param in anim.params.items()
        if isinstance(param, Param)
        and key not in params
    })
    # Fill out non-form parameters
    kwargs.update({
        key: param.value(request)
        for key, param in anim.params.items()
        if not isinstance(param, Param)
    })
    return anim.function(**kwargs)


@route('/create', 'POST')
def create_animation(request):
    """
    Given a preset name, an animation function name, and a set of parameters,
    calls the specified animation function with the specified parameter values,
    and creates a named preset with the resulting data.
    """
    try:
        params = request.query.copy()
        name = params.pop('name')
        anim = params.pop('animation')
        data = generate_animation(request, anim, params)
    except (KeyError) as e:
        return HTTPResponse(
            request, body=str(e), status_code=HTTPStatus.BAD_REQUEST)
    else:
        # TODO Assert that the structure is correct (voluptuous?)
        data = [[led.html for led in frame] for frame in data]
        if name in request.store.presets:
            request.server.messages.show(f'Updated preset {name}')
        else:
            request.server.messages.show(f'Created preset {name}')
        request.store.presets[name] = data
        return HTTPResponse(
            request, status_code=HTTPStatus.SEE_OTHER,
            headers={'Location': '/index.html'})


@route('/animation/<name>', 'POST')
def get_animation(request, name):
    """
    Calls the named animation function with parameters derived from the JSON
    object in the request body, returning the generated animation frames as a
    JSON array in the body of the response.
    """
    try:
        data = generate_animation(request, name, request.query)
    except (KeyError, ValueError, TypeError) as e:
        return HTTPResponse(
            request, body=str(e), status_code=HTTPStatus.BAD_REQUEST)
    else:
        # TODO Assert that the structure is correct (voluptuous?)
        data = [[led.html for led in frame] for frame in data]
        return HTTPResponse(request, body=json.dumps(data))


@route('/capture.html', 'GET')
def calibration_positions(request):
    """
    Runs at the start of calibration, and immediately after each angle has been
    scanned. Ultimately it just falls through to the :file:`capture.html.pt`
    template but before that, if LED positions from the scan of an angle are
    present,  it will feed them to the calibration algorithm to determine 3D
    positions of those LEDs.
    """
    scanner = request.server.calibration.scanner
    if scanner is not None and scanner.progress == 1:
        calc = request.server.calibration.calculator
        request.server.calibration.scanner = None
        calc.add_angle(scanner)

    # Fall-through to render the capture.html.pt template as the response
    return None


@route('/live-preview.mjpg', 'GET')
def calibration_preview(request):
    """
    Continually sends JPEG frames from the camera to the client to provide the
    preview of the tree before the capture step.
    """
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


def scanner_for(request, angle):
    """
    Returns the :class:`~blinkenxmas.calibrate.AngleScanner` instance for
    the specified *angle*, or raises :exc:`ValueError` if the current scanner
    does not match the requested angle.
    """
    scanner = request.server.calibration.scanner
    if scanner is None or scanner.angle != angle:
        raise ValueError(f'Scanner is not for {angle}')
    return scanner


@route('/angle<angle>_base.jpg', 'GET')
def calibration_base(request, angle):
    """
    Obtains the :class:`~blinkenxmas.calibrate.AngleScanner` instance for the
    specified angle. If none exists, one will be constructed, which will
    implicitly capture the first image of the (unlit) tree at this angle.

    The "base" image of the unlit tree is returned as the response.
    """
    try:
        angle = int(angle, base=10) % 360
    except ValueError:
        return HTTPResponse(request, status_code=HTTPStatus.NOT_FOUND)
    try:
        if int(request.query.get('force', '0')):
            # This is used in mask.html.pt to guarantee we capture a fresh
            # image in case the user has re-started this angle for some reason
            raise ValueError('Forcing scanner reset')
        scanner = scanner_for(request, angle)
    except ValueError:
        scanner = request.server.calibration.scanner = AngleScanner(
            angle, request.server.camera, request.server.queue,
            request.server.config.led_strips, request.server.messages)

    return HTTPResponse(request, body=scanner.base, mime_type='image/jpeg')


@route('/angle<angle>_mask.json', 'GET')
def calibration_mask(request, angle):
    """
    Returns a JSON array containing the coordinates drawn by the user around
    the outline of the tree at the specified angle. The coordinates are (x, y)
    pairs of floating-point values where (0, 0) is the top left of the base
    image, and (1, 1) is the bottom right of the image.
    """
    try:
        angle = int(angle, base=10) % 360
        scanner = scanner_for(request, angle)
    except ValueError:
        return HTTPResponse(request, status_code=HTTPStatus.NOT_FOUND)

    return HTTPResponse(request, body=json.dumps(scanner.mask),
                        mime_type='application/json')


@route('/angle<angle>_state.json', 'GET')
def calibration_state(request, angle):
    """
    Returns a JSON object containing information about the progress and state
    of the (presumably ongoing) scan of the specified angle of the tree. This
    is typically polled during the scan to display the currently detected LEDs,
    and how confident the algorithm is in its determination of their position.
    It also includes the mask coordinates in case this is useful for display
    purposes.

    Again, coordinates are specified as (x, y) pairs of floating-point values
    between (0, 0) for the top left of the image, and (1, 1) for the bottom
    right.
    """
    try:
        angle = int(angle, base=10) % 360
        scanner = scanner_for(request, angle)
    except ValueError:
        return HTTPResponse(request, status_code=HTTPStatus.NOT_FOUND)

    return HTTPResponse(request, body=json.dumps({
        'progress':  scanner.progress,
        'mask':      scanner.mask,
        'positions': scanner.positions,
        'scores':    scanner.scores,
    }), mime_type='application/json')


@route('/calibrate.html', 'GET')
def calibration_run(request):
    """
    Falls through to the :file:`calibrate.html.pt` template. Before doing so,
    however, it retrieves the :class:`~blinkenxmas.calibrate.AngleScanner`
    instance for the specified angle and starts the calibration scan. If mask
    data is passed (as a JSON array) in the "mask" value of the query-string,
    it will be passed to the scan method.
    """
    try:
        angle = int(request.query['angle'])
        mask = [
            (float(x), float(y))
            for x, y in json.loads(request.query['mask'])
            if 0 <= float(x) <= 1 and 0 <= float(y) <= 1
        ]
        scanner = scanner_for(request, angle)
    except (KeyError, ValueError):
        return HTTPResponse(request, status_code=HTTPStatus.NOT_FOUND)

    scanner.scan(mask)

    # Fall-through to render the calibrate.html.pt template as the response
    return None


@route('/cancel.html', 'GET')
def calibration_cancel(request):
    """
    Cancels any on-going scan of the tree angle specified in the "angle" value
    of the query-string.
    """
    try:
        angle = int(request.query['angle'])
        scanner = scanner_for(request, angle)
    except ValueError:
        return HTTPResponse(request, status_code=HTTPStatus.NOT_FOUND)

    request.server.calibration.scanner = None
    scanner.stop()
    request.server.messages.show(f'Cancelled current scan for angle {angle}°')
    return HTTPResponse(
        request, status_code=HTTPStatus.SEE_OTHER,
        headers={'Location': '/index.html'})


@route('/estimated.json', 'GET')
def calibration_result(request):
    """
    TODO
    """
    calculator = request.server.calibration.calculator
    return HTTPResponse(request, body=json.dumps({
        'positions': {
            led: list(coords)
            for led, coords in calculator.positions.items()
        },
    }), mime_type='application/json')


@route('/commit.html', 'GET')
def calibration_commit(request):
    """
    TODO
    """
    calculator = request.server.calibration.calculator
    with request.store:
        request.store.positions.clear()
        for led, position in calculator.positions.items():
            request.store.positions[led] = position
        calculator.clear()
    request.server.messages.show(
        f'Committed {len(request.store.positions)} LED positions to the database')
    return HTTPResponse(
        request, status_code=HTTPStatus.SEE_OTHER,
        headers={'Location': '/index.html'})
