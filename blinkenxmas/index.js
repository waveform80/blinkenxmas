function initIndexForm(form) {
  form.querySelectorAll("ul#presets li a").forEach(
    (link) => {
      link.href = '#';
      link.addEventListener('click',
        (evt) => doShow(link.dataset.preset));
    });
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
