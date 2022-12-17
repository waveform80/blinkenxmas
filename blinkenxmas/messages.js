function showMessage(s) {
  document.querySelector("#message p").innerHTML = s;
  document.querySelector("#message").style.display = "block";
}

function hideMessage() {
  document.querySelector("#message").style.display = "none";
}

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

