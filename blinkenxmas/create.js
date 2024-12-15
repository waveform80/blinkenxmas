function initCreateForm(form) {
  form.addEventListener('change', (evt) => {
    if (evt.target.nodeName != 'BUTTON')
      delete form.dataset.anim;
  });
  form.addEventListener('submit', (evt) => {
    evt.preventDefault();
    evt.stopPropagation();
    doCreate(form);
  });
  form.elements['name'].addEventListener('input', (evt) => createOrUpdate(form));
  form.elements['animation'].addEventListener('change', (evt) => setupCreateForm(form));
  createPreviewBtn(form);
}

function createPreviewBtn(form) {
  let buttons = form.querySelector('.buttons');
  let btn = document.createElement('input');
  btn.type = 'button';
  btn.id = 'preview';
  btn.value = 'Preview';
  btn.addEventListener('click', (evt) => doPreview(form));
  buttons.insertBefore(btn, buttons.firstChild);
}

function createOrUpdate(form) {
  getPresets().then((data) => {
    let presets = data;
    if (presets.includes(form.elements['name'].value))
      form.elements['create'].value = 'Update';
    else
      form.elements['create'].value = 'Create';
  });
}

function setupCreateForm(form) {
  let animation = form.elements['animation'].value;
  let nameInput = form.elements['name'];
  let descElem = form.querySelector('.description');

  // Remove existing animation controls
  for (let elem of Array.from(form.elements)) {
    switch (elem.nodeName) {
      case 'LABEL':
        continue;
      case 'INPUT':
        if (elem.type == 'button')
          continue;
        if (elem.name == 'name')
          continue;
        break;
      case 'SELECT':
        if (elem.name == 'animation')
          continue;
        break;
    }
    for (let label of elem.labels)
      label.remove();
    elem.remove();
  }

  descElem.hidden = true;
  if (animation) {
    getAnimations().then((data) => {
      let animations = data;
      let params = animations[animation][3];

      nameInput.defaultValue = animations[animation][0];
      createOrUpdate(form);
      if (animations[animation][1]) {
        descElem.innerHTML = animations[animation][1];
        descElem.hidden = false;
      }

      // Create new elements for the selected animation before the buttons at
      // the bottom of the form
      let buttons = form.querySelector('.buttons');
      for (let param in params) {
        let label = document.createElement('label');
        let input = null;
        if (params[param][1] == 'select') {
          input = document.createElement('select');
          let choices = params[param][5];
          input.name = param;
          input.id = escapeIdent(param);
          for (let choice in choices) {
            let option = document.createElement('option');
            option.value = choice;
            option.textContent = choices[choice];
            input.append(option);
          }
        }
        else {
          input = document.createElement('input');
          input.name = param;
          input.id = escapeIdent(param);
          input.type = params[param][1];
          if (params[param][1] == 'checkbox') {
            if (params[param][2] !== null)
                input.checked = params[param][2];
          }
          else {
            if (params[param][2] !== null)
              input.defaultValue = params[param][2];
            if (params[param][3] !== null)
              input.min = params[param][3];
            if (params[param][4] !== null)
              input.max = params[param][4];
          }
        }
        label.htmlFor = input.id;
        label.textContent = params[param][0];
        form.insertBefore(label, buttons);
        form.insertBefore(input, buttons);
      }
    });
  }
}

function generateAnim(form) {
  let animation = form.elements['animation'].value;

  if (animation && !form.dataset.anim) {
    let params = new FormData(form);
    params.delete('name');
    params.delete('data');
    params.delete('animation');

    let req = new Request(`/animation/${encodeURIComponent(animation)}`, {
      method: 'POST',
      body: params,
      cache: 'no-store',
    });
    let tid = setTimeout(
        () => showMessage('Please waiting, building animation'),
        500);
    return fetch(req)
      .then((resp) => {
        clearTimeout(tid);
        if (resp.ok)
          return resp.text();
        else
          throw new Error(resp.statusText);
      })
      .then((data) => {
        form.dataset.anim = data;
        return data;
      });
  }
  return new Promise((resolve, reject) => resolve(form.dataset.anim));
}

function doPreview(form) {
  generateAnim(form)
    .then((data) => {
      let req = new Request('/preview', {
        method: 'POST',
        headers: new Headers({'Content-Type': 'application/json'}),
        body: data,
        cache: 'no-store',
      });
      fetch(req)
        .catch((e) => showMessage(e));
    })
    .catch((e) => showMessage(e));
}

function doCreate(form) {
  generateAnim(form)
    .then((data) => {
      let name = form.elements['name'].value;
      let req = new Request(`/preset/${encodeURIComponent(name)}.json`, {
        method: 'PUT',
        headers: new Headers({'Content-Type': 'application/json'}),
        body: data,
        cache: 'no-store',
      });
      fetch(req)
        .then(() => { window.location = '/'; })
        .catch((e) => showMessage(e));
    })
    .catch((e) => showMessage(e));
}
