function initIndexForm(form) {
  form.querySelectorAll("ul#presets li a").forEach(
    (link) => {
      link.href = '#';
      link.addEventListener('click',
        (evt) => doShow(link.dataset.preset));
    });
}

function initCreateForm(form) {
  form.addEventListener('change', (evt) => {
    dataArea = form.elements['data'];
    if ((evt.target.nodeName != 'BUTTON') && (evt.target !== dataArea))
      form.dataset.changed = 1;
  });
  form.elements['animation'].addEventListener('change', (evt) => setupCreateForm(form));
  form.elements['preview'].addEventListener('click', (evt) => doPreview(form));
  form.elements['create'].addEventListener('click', (evt) => doCreate(form));
}

function setupCreateForm(form) {
  let animation = form.elements['animation'].value;
  let dataArea = form.elements['data'];

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
      case 'TEXTAREA':
        if (elem.name == 'data')
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

  if (animation) {
    let params = animations[animation][2];

    // Create new elements for the selected animation before the buttons at
    // the bottom of the form
    let buttons = form.querySelector('.buttons');
    for (let param in params) {
      let labelElem = document.createElement('label');
      labelElem.htmlFor = param;
      labelElem.textContent = params[param][0];
      form.insertBefore(labelElem, buttons);
      let inputElem = document.createElement('input');
      inputElem.name = param;
      inputElem.id = param;
      inputElem.type = params[param][1];
      if (param[2] !== null)
        inputElem.defaultValue = params[param][2];
      if (param[3] !== null)
        inputElem.min = params[param][3];
      if (param[4] !== null)
        inputElem.max = params[param][4];
      form.insertBefore(inputElem, buttons);
    }

    for (let label of dataArea.labels)
      label.style.display = 'none';
    dataArea.style.display = 'none';
  }
  else {
    for (let label of dataArea.labels)
      label.style.display = 'block';
    dataArea.style.display = 'block';
  }
}

function generateAnim(form) {
  let animation = form.elements['animation'].value;
  let dataArea = form.elements['data'];

  if (animation && !!form.dataset.changed) {
    // Build the parameters object
    let params = {};
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
        case 'TEXTAREA':
          if (elem.name == 'data')
            continue;
          break;
        case 'SELECT':
          if (elem.name == 'animation')
            continue;
          break;
      }
      params[elem.name] = elem.value;
    }

    let req = new Request(`/animation/${animation}`, {
      method: 'POST',
      body: JSON.stringify(params),
      cache: 'no-store',
    });
    return fetch(req)
      .then((resp) => resp.text())
      .then((data) => {
        dataArea.value = data;
        delete form.dataset.changed;
        return data;
      });
  }
  return new Promise((resolve, reject) => resolve(dataArea.value));
}

function doPreview(form) {
  generateAnim(form)
    .then((data) => {
      let req = new Request('/preview', {
        method: 'POST',
        body: data,
        cache: 'no-store',
      });
      fetch(req)
        .catch((e) => showMessage(e));
    })
    .catch((e) => showMessage(e));
}

function doCreate(form) {
  if (!form.reportValidity()) return;

  generateAnim(form)
    .then((data) => {
      let name = form.elements['name'].value;
      let req = new Request(`/preset/${name}`, {
        method: 'PUT',
        body: data,
        cache: 'no-store',
      });
      fetch(req)
        .then(() => { window.location = '/'; })
        .catch((e) => showMessage(e));
    })
    .catch((e) => showMessage(e));
}

function doDelete(form) {
  let name = form.elements['name'].value;
  let req = new Request(`/preset/${name}`, {
    method: 'DELETE',
    cache: 'no-store',
  });
  fetch(req)
    .then(() => { window.location = '/'; })
    .catch((e) => showMessage(e));
}

function doShow(name) {
  let req = new Request(`/show/${name}`, {
    method: "POST",
    cache: "no-store",
  });
  fetch(req)
    .catch((e) => showMessage(e));
}
