/**
 * my_files.js — My Files local storage view & operations.
 */
import { Icons } from './icons.js';
import { toast, fmtSize } from './ui.js';
import { downloadBlob } from './api.js';

export async function fetchMyFilesInfo() {
  const res = await fetch('/api/files/info');
  return res.ok ? await res.json() : null;
}

export async function fetchMyFilesList(folder = '', query = '', fileType = '') {
  const params = new URLSearchParams();
  if (folder) params.append('folder', folder);
  if (query) params.append('query', query);
  if (fileType) params.append('file_type', fileType);
  const res = await fetch(`/api/files/list?${params}`);
  return res.ok ? await res.json() : [];
}

export async function saveToMyFiles(blob, filename, folder = '') {
  const fd = new FormData();
  fd.append('file', blob, filename);
  if (folder) fd.append('folder', folder);
  fd.append('filename', filename);
  const res = await fetch('/api/files/save', { method: 'POST', body: fd });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to save to My Files');
  }
  return await res.json();
}

export async function openFolderInOS(folder = '') {
  const fd = new FormData();
  if (folder) fd.append('folder', folder);
  const res = await fetch('/api/files/open-folder', { method: 'POST', body: fd });
  return res.ok;
}

export async function deleteMyFile(folder, filename) {
  const res = await fetch(`/api/files/delete?folder=${encodeURIComponent(folder)}&filename=${encodeURIComponent(filename)}`, {
    method: 'DELETE',
  });
  return res.ok;
}

export async function deleteAllMyFiles() {
  const res = await fetch('/api/files/delete-all', { method: 'DELETE' });
  return res.ok ? await res.json() : null;
}

export async function renameMyFile(folder, oldName, newName) {
  const fd = new FormData();
  fd.append('folder', folder);
  fd.append('old_name', oldName);
  fd.append('new_name', newName);
  const res = await fetch('/api/files/rename', { method: 'POST', body: fd });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Rename failed');
  }
  return await res.json();
}

export function renderMyFilesView(containerEl, currentLang = 'en') {
  containerEl.innerHTML = `
    <div class="my-files-page">
      <div class="my-files-header">
        <div>
          <h1 class="my-files-title">My Files (Local Folders)</h1>
          <p class="my-files-path" id="mf-root-path">Loading storage path…</p>
        </div>
        <div class="my-files-header-actions">
          <button type="button" class="btn btn--secondary btn--sm" id="mf-open-explorer">
            📁 Open in File Explorer
          </button>
          <button type="button" class="btn btn--secondary btn--sm" id="mf-copy-path">
            📋 Copy Path
          </button>
          <button type="button" class="btn btn--danger btn--sm" id="mf-delete-all">
            🗑️ Delete All
          </button>
        </div>
      </div>

      <div class="my-files-notice">
        <span>🛡️ <strong>100% On-Device:</strong> Files saved here reside permanently in your local <code>Documents/LocalToolkit/</code> folder until you delete them. They are never uploaded or synced to any server.</span>
      </div>

      <div class="my-files-toolbar">
        <div class="my-files-search-wrap">
          <input type="text" id="mf-search" class="input" placeholder="Search saved files by name…">
        </div>
        <div class="my-files-filters">
          <select id="mf-folder-filter" class="select select--sm">
            <option value="">All Folders</option>
          </select>
          <select id="mf-type-filter" class="select select--sm">
            <option value="">All Types</option>
            <option value="pdf">PDF Documents</option>
            <option value="image">Images</option>
          </select>
        </div>
      </div>

      <div class="my-files-grid" id="mf-file-list">
        <div class="preview-loading">Loading your saved files…</div>
      </div>
    </div>
  `;

  _wireMyFiles(containerEl);
}

async function _wireMyFiles(containerEl) {
  const rootPathEl = document.getElementById('mf-root-path');
  const folderFilter = document.getElementById('mf-folder-filter');
  const typeFilter = document.getElementById('mf-type-filter');
  const searchInput = document.getElementById('mf-search');
  const listEl = document.getElementById('mf-file-list');
  const openBtn = document.getElementById('mf-open-explorer');
  const copyBtn = document.getElementById('mf-copy-path');
  const delAllBtn = document.getElementById('mf-delete-all');

  let currentRoot = '';

  const info = await fetchMyFilesInfo();
  if (info) {
    currentRoot = info.root_path;
    if (rootPathEl) rootPathEl.textContent = `📁 ${info.root_path} (${info.total_files} files, ${fmtSize(info.total_bytes)})`;
    if (folderFilter) {
      info.folders.forEach(f => {
        const opt = document.createElement('option');
        opt.value = f;
        opt.textContent = f;
        folderFilter.appendChild(opt);
      });
    }
  }

  async function _reload() {
    listEl.innerHTML = '<div class="preview-loading">Loading…</div>';
    const folder = folderFilter ? folderFilter.value : '';
    const type = typeFilter ? typeFilter.value : '';
    const query = searchInput ? searchInput.value : '';
    const files = await fetchMyFilesList(folder, query, type);

    if (files.length === 0) {
      listEl.innerHTML = `
        <div class="empty-state">
          <div class="empty-state__title">No files saved yet</div>
          <div class="empty-state__msg">When you process any file, click <strong>"Save to My Files"</strong> to organize it into auto-size folders.</div>
        </div>
      `;
      return;
    }

    listEl.innerHTML = files.map((f, i) => `
      <div class="mf-card" data-folder="${f.folder}" data-name="${f.name}">
        <div class="mf-card__icon">${f.ext === '.pdf' ? '📄' : '🖼️'}</div>
        <div class="mf-card__body">
          <div class="mf-card__name" title="${f.name}">${f.name}</div>
          <div class="mf-card__meta">
            <span class="mf-card__folder">${f.folder}</span> &middot;
            <span>${fmtSize(f.size)}</span>
          </div>
        </div>
        <div class="mf-card__actions">
          <a href="/api/files/download/${encodeURIComponent(f.folder)}/${encodeURIComponent(f.name)}?token=${encodeURIComponent(window.__LTK_TOKEN__ || '')}" download="${f.name}" class="btn btn--sm btn--secondary mf-download-btn" title="Download">⬇️</a>
          <button type="button" class="btn btn--sm btn--secondary mf-rename-btn" title="Rename" data-idx="${i}">✏️</button>
          <button type="button" class="btn btn--sm btn--danger mf-del-btn" title="Delete" data-idx="${i}">🗑️</button>
        </div>
      </div>
    `).join('');

    listEl.querySelectorAll('.mf-download-btn').forEach(link => {
      link.addEventListener('click', async (e) => {
        e.preventDefault();
        const card = link.closest('.mf-card');
        const folder = card.dataset.folder;
        const name = card.dataset.name;
        try {
          const res = await fetch(`/api/files/download/${encodeURIComponent(folder)}/${encodeURIComponent(name)}`);
          if (res.ok) {
            const blob = await res.blob();
            downloadBlob(blob, name);
          } else {
            const err = await res.json().catch(() => ({}));
            toast('error', 'Download Failed', err.detail || 'Could not download file.');
          }
        } catch (err) {
          toast('error', 'Download Failed', err.message);
        }
      });
    });

    listEl.querySelectorAll('.mf-del-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const card = btn.closest('.mf-card');
        const folder = card.dataset.folder;
        const name = card.dataset.name;
        if (confirm(`Delete "${name}" from your local storage?`)) {
          await deleteMyFile(folder, name);
          toast('info', 'Deleted', `Deleted ${name}`);
          _reload();
        }
      });
    });

    listEl.querySelectorAll('.mf-rename-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const card = btn.closest('.mf-card');
        const folder = card.dataset.folder;
        const name = card.dataset.name;
        const newName = prompt(`Enter new filename:`, name);
        if (newName && newName.trim() && newName.trim() !== name) {
          try {
            await renameMyFile(folder, name, newName.trim());
            toast('success', 'Renamed', 'File renamed successfully');
            _reload();
          } catch (err) {
            toast('error', 'Rename failed', err.message);
          }
        }
      });
    });
  }

  folderFilter?.addEventListener('change', _reload);
  typeFilter?.addEventListener('change', _reload);
  searchInput?.addEventListener('input', () => {
    clearTimeout(searchInput._t);
    searchInput._t = setTimeout(_reload, 300);
  });

  openBtn?.addEventListener('click', () => {
    const folder = folderFilter ? folderFilter.value : '';
    openFolderInOS(folder);
  });

  copyBtn?.addEventListener('click', () => {
    if (currentRoot) {
      navigator.clipboard.writeText(currentRoot);
      toast('success', 'Copied!', 'Path copied to clipboard');
    }
  });

  delAllBtn?.addEventListener('click', async () => {
    if (confirm('Are you sure you want to delete ALL files in My Files? This action cannot be undone.')) {
      await deleteAllMyFiles();
      toast('info', 'Cleaned', 'All files deleted from My Files');
      _reload();
    }
  });

  _reload();
}

