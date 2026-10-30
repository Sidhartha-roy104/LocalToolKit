/**
 * ui.js — DOM helpers, toast, drag-reorder, skeleton, progress.
 */

// ── Toast ─────────────────────────────────────────────────────────
const toastContainer = () => document.getElementById('toast-container');

/**
 * Show a toast notification.
 * @param {'success'|'error'|'info'} type
 * @param {string} title
 * @param {string} [msg]
 * @param {number} [duration] ms
 */
export function toast(type, title, msg = '', duration = 4500) {
  const icons = {
    success: `<svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="#16A34A" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><path stroke-linecap="round" d="M8 12l3 3 5-5"/></svg>`,
    error:   `<svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="#DC2626" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><path stroke-linecap="round" d="M15 9l-6 6M9 9l6 6"/></svg>`,
    info:    `<svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="#2563EB" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><path stroke-linecap="round" d="M12 16v-4M12 8h.01"/></svg>`,
  };
  const el = document.createElement('div');
  el.className = `toast toast--${type}`;
  el.setAttribute('role', 'alert');
  el.setAttribute('aria-live', 'polite');
  el.innerHTML = `
    <span class="toast__icon">${icons[type]}</span>
    <div class="toast__body">
      <div class="toast__title">${title}</div>
      ${msg ? `<div class="toast__msg">${msg}</div>` : ''}
    </div>
    <button class="toast__close" aria-label="Dismiss">&times;</button>
  `;
  el.querySelector('.toast__close').onclick = () => dismiss(el);
  toastContainer().appendChild(el);
  const timer = setTimeout(() => dismiss(el), duration);
  el._timer = timer;
  return el;
}

function dismiss(el) {
  clearTimeout(el._timer);
  el.classList.add('toast--out');
  el.addEventListener('animationend', () => el.remove(), { once: true });
}

// ── Progress bar ───────────────────────────────────────────────────
export function setProgress(barEl, fillEl, pct, label = '') {
  if (!barEl || !fillEl) return;
  barEl.setAttribute('aria-valuenow', pct);
  fillEl.style.width = `${pct}%`;
  if (label) barEl.setAttribute('aria-label', label);
}

// ── Format file size ───────────────────────────────────────────────
export function fmtSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}

// ── Drag-to-reorder file list ──────────────────────────────────────
/**
 * Make a container's children reorderable by drag-and-drop.
 * Items need a [data-drag-handle] child or are themselves draggable.
 * @param {HTMLElement} listEl
 * @param {function} onReorder - called with new order array after each drop
 */
export function makeDraggable(listEl, onReorder) {
  let dragged = null;

  listEl.addEventListener('dragstart', (e) => {
    dragged = e.target.closest('[draggable]');
    if (!dragged) return;
    dragged.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
  });
  listEl.addEventListener('dragend', () => {
    if (dragged) dragged.classList.remove('dragging');
    dragged = null;
    onReorder && onReorder([...listEl.children].map(el => el.dataset.fileIndex));
  });
  listEl.addEventListener('dragover', (e) => {
    e.preventDefault();
    const target = e.target.closest('[draggable]');
    if (!target || target === dragged) return;
    const rect = target.getBoundingClientRect();
    const after = e.clientY > rect.top + rect.height / 2;
    if (after) target.after(dragged);
    else target.before(dragged);
  });
}

// ── Render file item ───────────────────────────────────────────────
/**
 * Create a draggable file list item.
 * @param {File} file
 * @param {number} index
 * @param {function} onRemove - called with index when × clicked
 * @param {boolean} showDrag
 */
export function createFileItem(file, index, onRemove, showDrag = true) {
  const ext = file.name.split('.').pop().toUpperCase();
  const li = document.createElement('div');
  li.className = 'file-item';
  li.setAttribute('draggable', showDrag ? 'true' : 'false');
  li.dataset.fileIndex = index;
  li.innerHTML = `
    ${showDrag ? `<span class="file-item__drag" aria-hidden="true">
      <svg width="16" height="16" fill="currentColor" viewBox="0 0 24 24">
        <circle cx="9" cy="6" r="1.5"/><circle cx="9" cy="12" r="1.5"/>
        <circle cx="9" cy="18" r="1.5"/><circle cx="15" cy="6" r="1.5"/>
        <circle cx="15" cy="12" r="1.5"/><circle cx="15" cy="18" r="1.5"/>
      </svg>
    </span>` : ''}
    <span class="file-item__icon">
      <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414A1 1 0 0120 9.414V19a2 2 0 01-2 2z"/>
      </svg>
    </span>
    <div class="file-item__info">
      <div class="file-item__name" title="${file.name}">${file.name}</div>
      <div class="file-item__size">${fmtSize(file.size)}</div>
    </div>
    <button class="file-item__remove" aria-label="Remove ${file.name}" title="Remove">
      <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
        <path stroke-linecap="round" d="M18 6L6 18M6 6l12 12"/>
      </svg>
    </button>
  `;
  li.querySelector('.file-item__remove').addEventListener('click', (e) => {
    e.stopPropagation();
    onRemove(index);
  });
  return li;
}

// ── Show/hide sections ────────────────────────────────────────────
export function show(el) { if (el) el.style.display = ''; }
export function hide(el) { if (el) el.style.display = 'none'; }
export function showFlex(el) { if (el) el.style.display = 'flex'; }

// ── ARIA live announce ────────────────────────────────────────────
const _announcer = (() => {
  const el = document.createElement('div');
  el.setAttribute('aria-live', 'assertive');
  el.setAttribute('aria-atomic', 'true');
  el.className = 'sr-only';
  document.body.appendChild(el);
  return el;
})();

export function announce(msg) {
  _announcer.textContent = '';
  requestAnimationFrame(() => { _announcer.textContent = msg; });
}

