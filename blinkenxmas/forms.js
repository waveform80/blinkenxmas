function escapeIdent(s) {
  let firstChar = /[A-Za-z]/;
  let otherChar = /[A-Za-z0-9-.]/;
  return Array.from(s).map((c, index) => {
    if (c == ' ')
      return '_';
    else if (c.match(index == 0 ? firstChar : otherChar))
      return c;
    else
      return ':' + c.charCodeAt(0).toString(16).padStart(4, '0');
  }).join('');
}

function unescapeIdent(s) {
  let charRe = /:[0-9A-Fa-f]{4}|./g;
  return Array.from(s.matchAll(charRe)).map((match) => {
    let c = match[0];
    if (c == '_')
      return ' ';
    else if (c[0] == ':')
      return String.fromCharCode(Number.parseInt(c.substring(1), 16));
    else
      return c;
  }).join('');
}

function initIndexForm(form) {
  form.querySelectorAll("ul#presets li a").forEach(
    (link) => {
      link.href = '#';
      link.addEventListener('click',
        (evt) => doShow(link.dataset.preset));
    });
  let manageBtn = document.createElement('input');
  manageBtn.type = 'button';
  manageBtn.value = 'Manage';
  manageBtn.addEventListener('click', (evt) => doManage(form));
  document.querySelector('#manage').replaceWith(manageBtn);
  manageBtn.id = 'manage';
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
      let input = document.createElement('input');
      input.name = param;
      input.id = escapeIdent(param);
      input.type = params[param][1];
      if (param[2] !== null)
        input.defaultValue = params[param][2];
      if (param[3] !== null)
        input.min = params[param][3];
      if (param[4] !== null)
        input.max = params[param][4];
      let label = document.createElement('label');
      label.htmlFor = input.id;
      label.textContent = params[param][0];
      form.insertBefore(label, buttons);
      form.insertBefore(input, buttons);
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

    let req = new Request(`/animation/${encodeURIComponent(animation)}`, {
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
      let req = new Request(`/preset/${encodeURIComponent(name)}`, {
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

function doManage(form) {
  form.querySelectorAll("ul#presets li a").forEach(
    (link) => {
      let check = document.createElement('input');
      check.type = 'checkbox';
      check.name = 'name';
      check.dataset.preset = link.dataset.preset;
      check.id = escapeIdent(check.dataset.preset);
      let label = document.createElement('label');
      label.textContent = check.dataset.preset;
      label.htmlFor = check.id;
      link.replaceWith(check, label);
    });
  let remove = document.createElement('input');
  remove.type = 'button';
  remove.id = 'remove';
  remove.value = 'Remove';
  remove.addEventListener('click', (evt) => doRemove(form));
  let cancel = document.createElement('input');
  cancel.type = 'button';
  cancel.id = 'cancel';
  cancel.value = 'Cancel';
  cancel.addEventListener('click', (evt) => cancelManage(form));
  form.querySelector('.buttons').replaceChildren(remove, cancel);
}

function cancelManage(form) {
  form.querySelectorAll("ul#presets li").forEach(
    (item) => {
      let link = document.createElement('a');
      link.href = '#';
      link.dataset.preset = unescapeIdent(item.querySelector('input').id);
      link.textContent = link.dataset.preset;
      link.addEventListener('click',
        (evt) => doShow(link.dataset.preset))
      item.replaceChildren(link);
    });
  let create = document.createElement('a');
  create.href = 'create.html';
  create.classList.add('button');
  create.textContent = 'Create';
  let manage = document.createElement('input')
  manage.type = 'input';
  manage.id = 'manage';
  manage.value = 'Manage';
  manage.addEventListener('click', (evt) => doManage(form));
  form.querySelector('.buttons').replaceChildren(create, manage);
}

function doRemove(form) {
  let formList = form.querySelector('#presets');
  let toRemove = Array
    .from(form.elements['name'])
    .filter((item) => item.checked);
  let toRemoveNames = toRemove.map((item) => item.dataset.preset);

  function _remove(item) {
    if (item == undefined) {
      cancelManage(form);
      showMessage(`Removed ${toRemoveNames.join(', ')}`);
    }
    else {
      let name = item.dataset.preset;
      let req = new Request(`/preset/${encodeURIComponent(name)}`, {
        method: 'DELETE',
        cache: 'no-store',
      });
      return fetch(req)
        .then(() => {
          formList.removeChild(item.parentElement);
          return _remove(toRemove.pop());
        })
        .catch((e) => showMessage(e));
    }
  }
  return _remove(toRemove.pop());
}

function doShow(name) {
  let req = new Request(`/show/${encodeURIComponent(name)}`, {
    method: "POST",
    cache: "no-store",
  });
  fetch(req)
    .catch((e) => showMessage(e));
}
