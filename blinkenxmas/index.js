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
    method: 'POST',
    headers: new Headers({'Content-Type': 'application/x-www-form-urlencoded'}),
    cache: 'no-store',
  });
  fetch(req)
    .catch((e) => showMessage(e));
}
