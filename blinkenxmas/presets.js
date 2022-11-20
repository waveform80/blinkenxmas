function showMessage(s) {
  document.querySelector("#message p").innerHTML = s;
  document.querySelector("#message").style.display = "block";
}

function hideMessage() {
  document.querySelector("#message").style.display = "none";
}

function doCreate(form) {
  if (form.reportValidity()) {
    let req = new Request(`/preset/${form.name.value}`, {
      method: "PUT",
      body: form.data.value,
      cache: "no-store",
    });
    fetch(req)
      .then(() => { window.location = "/"; })
      .catch((e) => showMessage(e));
  }
}

doUpdate = doCreate;

function doDelete(form) {
  let req = new Request(`/preset/${name}`, {
    method: "DELETE",
    cache: "no-store",
  });
  fetch(req)
    .then(() => { window.location = "/"; })
    .catch((e) => showMessage(e));
}
