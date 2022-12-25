function initCalibrateForm(form) {
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
    let calibrateBtn = form.elements['calibrate'];
    let undoBtn = document.createElement('input');
    let preview = form.querySelector('#preview-image');
    let canvas = document.createElement('canvas');
    let mask = new Array();

    undoBtn.id = 'undo';
    undoBtn.type = 'button';
    undoBtn.value = 'Undo';
    buttons.insertBefore(undoBtn, calibrateBtn);

    canvas.id = 'preview-image';
    preview.onload = () => {
        console.log("Natural resolution", preview.naturalWidth, ",", preview.naturalHeight);
        console.log("Preview resolution", preview.width, ",", preview.height);
        canvas.width = preview.width;
        canvas.height = preview.height;
        drawMask(canvas, preview, mask);
        preview.replaceWith(canvas);
    };

    canvas.addEventListener('mousedown', (evt) => {
        let coords = [evt.offsetX / canvas.width, evt.offsetY / canvas.height];
        console.log("Click event", coords);
        mask.push(coords);

        drawMask(canvas, preview, mask);
    });

    undoBtn.addEventListener('click', (evt) => {
        mask.pop();
        drawMask(canvas, preview, mask);
    });
}

function drawMask(canvas, image, maskPath) {
    let context = canvas.getContext('2d');

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

function startPreview(evt) {
    let form = document.forms[0];
    let previewBtn = form.querySelector('#preview');

    // XXX: Set angle correctly
    form.querySelector('#preview-image').src = '/live-preview.mjpg?angle=0';
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
