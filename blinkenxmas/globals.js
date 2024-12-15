var _animations;
function getAnimations() {
  if (_animations !== undefined)
    return new Promise((resolve, reject) => resolve(_animations));
  else
    return getJSON('/animations.json').then((data) => {
      _animations = data;
      return data;
    });
}

var _presets;
function getPresets() {
  if (_presets !== undefined)
    return new Promise((resolve, reject) => resolve(_presets));
  else
    return getJSON('/presets.json').then((data) => {
      _presets = data;
      return data;
    });
}

function getJSON(url) {
  let req = new Request(url);
  return fetch(req).then((resp) => {
    if (resp.ok)
      return resp.json();
    else
      throw new Error(resp.statusText);
  });
}
