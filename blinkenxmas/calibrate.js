function initCalibrateForm(form) {
    let buttons = form.querySelector('.buttons');
    let calibrateBtn = form.elements['calibrate'];
    let previewBtn = document.createElement('input');

    previewBtn.id = 'preview';
    previewBtn.type = 'button';
    previewBtn.value = 'Preview';
    previewBtn.addEventListener('click', startPreview);
    buttons.insertBefore(previewBtn, calibrate);
}

function startPreview(evt) {
    let form = document.forms[0];
    let previewBtn = form.querySelector('#preview');

    form.querySelector('#preview-image').src =
        '/calibrate/preview.mjpg?width=640&height=480&angle=0';
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
