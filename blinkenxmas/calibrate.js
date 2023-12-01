function initCaptureForm(form) {
    let buttons = form.querySelector('.buttons');
    let captureBtn = form.elements['capture'];
    let previewBtn = document.createElement('input');

    previewBtn.id = 'preview';
    previewBtn.type = 'button';
    previewBtn.value = 'Preview';
    previewBtn.addEventListener('click', startPreview);
    buttons.insertBefore(previewBtn, captureBtn);
    captureBtn.addEventListener('click', stopPreview);
}

function initMaskForm(form) {
    let buttons = form.querySelector('.buttons');
    let scanBtn = form.elements['scan'];
    let undoBtn = document.createElement('input');
    let preview = form.querySelector('#preview-image');
    let canvas = document.createElement('canvas');
    let mask = new Array();

    undoBtn.id = 'undo';
    undoBtn.type = 'button';
    undoBtn.value = 'Undo';
    buttons.insertBefore(undoBtn, scanBtn);

    // Replace the preview image with a canvas that the user can click on to
    // draw the calibration mask
    canvas.id = 'preview-image';
    preview.onload = () => {
        canvas.width = preview.width;
        canvas.height = preview.height;
        drawMask(form, canvas, preview, mask);
        preview.replaceWith(canvas);
    };

    canvas.addEventListener('mousedown', (evt) => {
        let coords = [evt.offsetX / canvas.width, evt.offsetY / canvas.height];
        mask.push(coords);
        drawMask(form, canvas, preview, mask);
    });

    undoBtn.addEventListener('click', (evt) => {
        mask.pop();
        drawMask(form, canvas, preview, mask);
    });
}

function initCalibrateForm(form, angle) {
    angle = new String(angle).padStart(3, '0');
    let refreshBtn = form.querySelector('#refresh');
    let progressBar = form.querySelector('#progress');
    let preview = form.querySelector('#preview-image');
    let canvas = document.createElement('canvas');

    refreshBtn.remove();
    canvas.id = 'preview-image';
    preview.onload = () => {
        canvas.width = preview.width;
        canvas.height = preview.height;
        drawState(canvas, preview);
        preview.replaceWith(canvas);
    };

    function refresh() {
        let req = new Request(`/angle${angle}_state.json`, {
            method: 'GET',
            cache: 'no-store',
        });
        fetch(req)
            .then((resp) => resp.json())
            .then((data) => {
                console.log(data.progress);
                progressBar.value = data.progress;
                if (preview.complete)
                    drawState(canvas, preview, data);
                if (data.progress < 1)
                    setTimeout(refresh, 1000);
                else
                    window.location = '/capture.html';
            })
            .catch((e) => showMessage(e));
    }
    refresh();
}

function drawMask(form, canvas, image, maskPath) {
    let context = canvas.getContext('2d');

    form.elements['mask'].value = JSON.stringify(maskPath);
    context.drawImage(image, 0, 0, canvas.width, canvas.height);
    if (maskPath.length) {
        // Draw the path
        context.lineWidth = 3;
        context.strokeStyle = '#a0f';
        let [x, y] = maskPath[0];
        context.beginPath();
        context.moveTo(x * canvas.width, y * canvas.height);
        for (let [x, y] of maskPath)
            context.lineTo(x * canvas.width, y * canvas.height);
        context.closePath();
        context.stroke();

        // Draw the vertexes
        context.strokeStyle = '#000';
        context.fillStyle = '#fff';
        for (let [x, y] of maskPath) {
            context.beginPath();
            context.ellipse(
                x * canvas.width, y * canvas.height, 5, 5, 0, 0, 2 * Math.PI);
            context.fill();
            context.stroke();
        }
    }
}

function drawState(canvas, image, data) {
    let context = canvas.getContext('2d');

    context.drawImage(image, 0, 0, canvas.width, canvas.height);
    if (!data) return;
    context.strokeStyle = '#000';
    for (led in data.positions) {
        let [x, y] = data.positions[led];
        let score = data.scores[led];
        context.fillStyle = `rgb(
            ${Math.min(255, 128 + Math.floor(score * 2.0))},
            ${Math.min(255,   0 + Math.floor(score * 1.5))},
            ${Math.min(255,   0 + Math.floor(score * 0.5))}
        )`;
        x *= canvas.width;
        y *= canvas.height;

        context.beginPath();
        context.ellipse(x, y, 5, 5, 0, 0, 2 * Math.PI);
        context.fill();
        context.stroke();
        context.fillText(`${led}`, x + 7, y - 7);
    }
}

function startPreview(evt) {
    let form = document.forms[0];
    let angle = parseInt(form.elements['angle'].value);
    let previewBtn = form.querySelector('#preview');

    // XXX: Set angle correctly
    form.querySelector('#preview-image').src =
        `/live-preview.mjpg?angle=${angle}`;
    previewBtn.removeEventListener('click', startPreview);
    previewBtn.addEventListener('click', stopPreview);
    previewBtn.value = 'Stop';
}

function stopPreview(evt) {
    let form = document.forms[0];
    let previewBtn = form.querySelector('#preview');

    form.querySelector('#preview-image').src = '/no-preview.png';
    previewBtn.removeEventListener('click', stopPreview);
    previewBtn.addEventListener('click', startPreview);
    previewBtn.value = 'Preview';
}
