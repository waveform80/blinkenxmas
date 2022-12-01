function showMessage(s) {
  document.querySelector("#message p").innerHTML = s;
  document.querySelector("#message").style.display = "block";
}

function hideMessage() {
  document.querySelector("#message").style.display = "none";
}
