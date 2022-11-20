function setupForm(form) {
  // Remove existing animation controls
  for (let elem of Array.from(form.elements)) {
    switch (elem.nodeName) {
      case "LABEL":
        continue;
      case "INPUT":
        if (elem.type == "button")
          continue;
        if (elem.name == "name")
          continue;
        break;
      case "TEXTAREA":
        if (elem.name == "data")
          continue;
        break;
      case "SELECT":
        if (elem.name == "animation")
          continue;
        break;
    }
    for (let label of elem.labels)
      label.remove();
    elem.remove();
  }

  if (form.animation.value) {
    let params = animations[form.animation.value][2];

    // Create new elements for the selected animation below the "animation"
    // select control
    let after = form.querySelector('select[name="animation"]');
    for (let param in params) {
      let inputElem = document.createElement("input");
      inputElem.name = param;
      inputElem.id = param;
      inputElem.type = params[param][1];
      if (param[2] !== null)
        inputElem.defaultValue = params[param][2];
      if (param[3] !== null)
        inputElem.min = params[param][3];
      if (param[4] !== null)
        inputElem.max = params[param][4];
      after.insertAdjacentElement('afterend', inputElem);
      let labelElem = document.createElement("label");
      labelElem.htmlFor = param;
      labelElem.appendChild(document.createTextNode(params[param][0]));
      inputElem.insertAdjacentElement('beforebegin', labelElem);
      after = inputElem;
    }

    // Hide the "data" text-area
    for (let label of form.data.labels)
      label.style.display = 'none';
    form.data.style.display = 'none';
  }
  else {
    // Show the "data" text-area (can't use form.data.labels here as once it's
    // hidden the label no longer counts as a control label of the text-area)
    form.data.style.display = 'block';
    form.data.previousElementSibling.style.display = 'block';
  }
}

function generateAnim(form) {
  if (form.animation.value) {
    // Build the parameters object
    let params = {};
    for (let elem of Array.from(form.elements)) {
      switch (elem.nodeName) {
        case "LABEL":
          continue;
        case "INPUT":
          if (elem.type == "button")
            continue;
          if (elem.name == "name")
            continue;
          break;
        case "TEXTAREA":
          if (elem.name == "data")
            continue;
          break;
        case "SELECT":
          if (elem.name == "animation")
            continue;
          break;
      }
      params[elem.name] = elem.value;
    }

    let req = new Request(`/animation/${form.animation.value}`, {
      method: "POST",
      body: JSON.stringify(params),
      cache: "no-store",
    });
    return fetch(req)
      .then((resp) => resp.text())
      .then((data) => {
        form.data.value = data;
        return data;
      });
  }
  return new Promise((resolve, reject) => resolve(form.data.value));
}

function doPreview(form) {
  generateAnim(form)
    .then((data) => {
      let req = new Request("/preview", {
        method: "POST",
        body: data,
        cache: "no-store",
      });
      fetch(req)
        .catch((e) => showMessage(e));
    })
    .catch((e) => showMessage(e));
}
