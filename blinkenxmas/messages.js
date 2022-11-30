function showMessage(s) {
  document.querySelector("#message p").innerHTML = s;
  document.querySelector("#message").style.display = "block";
}

function hideMessage() {
  document.querySelector("#message").style.display = "none";
}

function doShow(name) {
  let req = new Request(`/preview/${name}`, {
    method: "POST",
    cache: "no-store",
  });
  fetch(req)
    .catch((e) => showMessage(e));
}
