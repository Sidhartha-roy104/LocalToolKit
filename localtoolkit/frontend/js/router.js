/**
 * router.js — Hash-based SPA router.
 * Routes: #/ → home, #/<tool-id> → tool page
 */

const _routes = new Map();
let _currentRoute = null;

export function route(path, handler) {
  _routes.set(path, handler);
}

export function navigate(path, pushState = true) {
  if (pushState) {
    window.location.hash = path === '/' ? '' : path;
  }
  _dispatch(path);
}

function _dispatch(path) {
  // Exact match first
  if (_routes.has(path)) {
    _currentRoute = path;
    _routes.get(path)(path);
    return;
  }
  // Wildcard / dynamic
  if (_routes.has('*')) {
    _currentRoute = path;
    _routes.get('*')(path);
  }
}

function _getPath() {
  const hash = window.location.hash.replace(/^#\/?/, '') || '/';
  return hash.startsWith('/') ? hash : '/' + hash;
}

export function init() {
  window.addEventListener('hashchange', () => _dispatch(_getPath()));
  _dispatch(_getPath());
}

export function currentRoute() { return _currentRoute; }

