function initCalibrateForm(form) {
    let buttons = form.querySelector('.buttons');
    let calibrateBtn = form.elements['calibrate'];
    let previewBtn = document.createElement('input');

    previewBtn.id = 'preview';
    previewBtn.type = 'button';
    previewBtn.value = 'Preview';
    previewBtn.addEventListener('click', startPreview);
    buttons.insertBefore(previewBtn, calibrateBtn);
    calibrateBtn.addEventListener('click', stopPreview);
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

function initMaskForm(form) {
    let buttons = form.querySelector('.buttons');
    let calibrateBtn = form.elements['calibrate'];
    let angle = (new URL(document.location)).searchParams.get('angle');
    let preview = form.querySelector('#preview-image');
    let canvas = document.createElement('canvas');
    let context = canvas.getContext('2d');

    canvas.id = 'preview-image';
    preview.onload = () => {
        canvas.width = preview.width;
        canvas.height = preview.height;
        context.drawImage(preview, 0, 0, preview.width, preview.height);
        preview.replaceWith(canvas);
    };
}
