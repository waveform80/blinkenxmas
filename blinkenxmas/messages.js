function showMessage(s) {
  const messageDiv = document.createElement('div');
  const messageClose = document.createElement('a');
  const messageP = document.createElement('p');
  messageP.textContent = s;
  messageClose.textContent = 'x';
  messageClose.href = document.location.pathname;
  messageClose.addEventListener('click', hideMessage);
  messageDiv.append(messageClose, messageP);
  document.querySelector('#messages').append(messageDiv);
}

function hideMessage(evt) {
  evt.target.parentElement.remove();
  evt.preventDefault();
  evt.stopPropagation();
}

function showMessages() {
  let req = new Request('/messages.json', { cache: 'no-store' });
  return fetch(req)
    .then((resp) => resp.json())
    .then((data) => data.map(showMessage))
    .catch((e) => showMessage(e));
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
      return ':' + c.codePointAt(0).toString(16).padStart(8, '0');
  }).join('');
}

function unescapeIdent(s) {
  let charRe = /:[0-9A-Fa-f]{8}|./g;
  return Array.from(s.matchAll(charRe)).map((match) => {
    let c = match[0];
    if (c == '_')
      return ' ';
    else if (c[0] == ':')
      return String.fromCodePoint(Number.parseInt(c.substring(1), 16));
    else
      return c;
  }).join('');
}
