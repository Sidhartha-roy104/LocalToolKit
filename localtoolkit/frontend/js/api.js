/**
 * api.js — Fetch wrappers + job polling + Session token injection.
 * All requests go to the same origin (127.0.0.1); no external calls.
 */

const BASE = '';  // same origin

// Automatically attach per-launch session token to all outgoing fetch requests
if (typeof window !== 'undefined' && window.fetch) {
  const _origFetch = window.fetch;
  window.fetch = function (url, options = {}) {
    const token = window.__LTK_TOKEN__;
    if (token && typeof url === 'string' && url.startsWith('/api/')) {
      options = options || {};
      options.headers = options.headers || {};
      if (options.headers instanceof Headers) {
        if (!options.headers.has('X-Session-Token')) options.headers.set('X-Session-Token', token);
      } else if (Array.isArray(options.headers)) {
        options.headers.push(['X-Session-Token', token]);
      } else {
        if (!options.headers['X-Session-Token']) options.headers['X-Session-Token'] = token;
      }
    }
    return _origFetch(url, options);
  };
}

/**
 * Submit a tool form and download the result.
 * @param {string} endpoint - e.g. '/api/pdf/merge'
 * @param {FormData} formData
 * @param {function} onProgress - called with 0-100 while uploading
 * @returns {Promise<{blob: Blob, filename: string, originalSize: number, resultSize: number}>}
 */
export async function submitTool(endpoint, formData, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', BASE + endpoint);
    xhr.responseType = 'blob';

    if (window.__LTK_TOKEN__) {
      xhr.setRequestHeader('X-Session-Token', window.__LTK_TOKEN__);
    }

    // Upload progress
    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable) {
        onProgress && onProgress(Math.round((e.loaded / e.total) * 60));
      }
    });

    xhr.addEventListener('load', () => {
      onProgress && onProgress(100);
      if (xhr.status >= 200 && xhr.status < 300) {
        const disp = xhr.getResponseHeader('Content-Disposition') || '';
        const match = disp.match(/filename="?([^";\n]+)"?/);
        const filename = match ? match[1] : 'download';
        resolve({
          blob: xhr.response,
          filename,
          resultSize: xhr.response.size,
        });
      } else {
        // Try to parse JSON error
        const reader = new FileReader();
        reader.onload = () => {
          try {
            const err = JSON.parse(reader.result);
            reject(new Error(err.detail || `Server error ${xhr.status}`));
          } catch {
            reject(new Error(`Server error ${xhr.status}`));
          }
        };
        reader.readAsText(xhr.response);
      }
    });

    xhr.addEventListener('error', () => reject(new Error('Network error — is the server running?')));
    xhr.addEventListener('abort', () => reject(new Error('Upload cancelled.')));
    xhr.send(formData);
  });
}

/**
 * Trigger a file download from a Blob.
 */
export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}

/**
 * Fetch server health / dependency info.
 */
export async function fetchHealth() {
  try {
    const res = await fetch(BASE + '/api/health');
    if (!res.ok) throw new Error('Health check failed');
    return await res.json();
  } catch {
    return null;
  }
}

/**
 * Poll a job until done or error.
 */
export async function pollJob(jobId, onProgress, intervalMs = 800) {
  return new Promise((resolve, reject) => {
    const timer = setInterval(async () => {
      try {
        const res = await fetch(`${BASE}/api/jobs/${jobId}`);
        const data = await res.json();
        onProgress && onProgress(data.progress || 0, data.message || '');
        if (data.status === 'done') {
          clearInterval(timer);
          resolve(data);
        } else if (data.status === 'error') {
          clearInterval(timer);
          reject(new Error(data.error || 'Job failed'));
        }
      } catch (e) {
        clearInterval(timer);
        reject(e);
      }
    }, intervalMs);
  });
}

/**
 * Preview API calls
 */
export async function getPDFThumbnails(file, maxPages = 50) {
  const fd = new FormData();
  fd.append('file', file);
  fd.append('max_pages', String(maxPages));
  const res = await fetch(BASE + '/api/preview/pdf-thumbnails', { method: 'POST', body: fd });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to generate PDF thumbnails');
  }
  return await res.json();
}

export async function getWatermarkPreview(file, text, opacity, fontSize, angle = 45, color = 'gray') {
  const fd = new FormData();
  fd.append('file', file);
  fd.append('text', text);
  fd.append('opacity', String(opacity));
  fd.append('font_size', String(fontSize));
  fd.append('angle', String(angle));
  fd.append('color', color);
  const res = await fetch(BASE + '/api/preview/watermark', { method: 'POST', body: fd });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to preview watermark');
  }
  return await res.json();
}

export async function getPageNumbersPreview(file, position, start, fontSize, formatStyle = 'Page {n}') {
  const fd = new FormData();
  fd.append('file', file);
  fd.append('position', position);
  fd.append('start', String(start));
  fd.append('font_size', String(fontSize));
  fd.append('format_style', formatStyle);
  const res = await fetch(BASE + '/api/preview/page-numbers', { method: 'POST', body: fd });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to preview page numbers');
  }
  return await res.json();
}

export async function getDocPreview(file) {
  const fd = new FormData();
  fd.append('file', file);
  const res = await fetch(BASE + '/api/preview/doc-page', { method: 'POST', body: fd });
  if (!res.ok) return { available: false };
  return await res.json();
}

/**
 * User Settings & History API
 */
export async function getUserSettings() {
  try {
    const res = await fetch('/api/user/settings');
    if (res.ok) return await res.json();
  } catch {}
  return {
    favorites: [],
    recent_tools: [],
    history_paused: false,
    recent_files_enabled: false,
    recent_files: [],
  };
}

export async function updateUserSettings(data) {
  const fd = new FormData();
  for (const [k, v] of Object.entries(data)) {
    if (v !== undefined && v !== null) fd.append(k, String(v));
  }
  const res = await fetch('/api/user/settings', { method: 'POST', body: fd });
  if (!res.ok) throw new Error('Failed to update settings');
  return await res.json();
}

export async function recordToolUsage(toolId) {
  try {
    const fd = new FormData();
    fd.append('tool_id', toolId);
    await fetch('/api/user/record-tool', { method: 'POST', body: fd });
  } catch {}
}

export async function recordRecentFile(name, size) {
  try {
    const fd = new FormData();
    fd.append('name', name);
    fd.append('size', String(size || 0));
    await fetch('/api/user/record-file', { method: 'POST', body: fd });
  } catch {}
}

export async function toggleFavorite(toolId) {
  const fd = new FormData();
  fd.append('tool_id', toolId);
  const res = await fetch('/api/user/toggle-favorite', { method: 'POST', body: fd });
  if (!res.ok) throw new Error('Failed to update favorite');
  return await res.json();
}

export async function clearHistory() {
  const res = await fetch('/api/user/clear-history', { method: 'POST' });
  if (!res.ok) throw new Error('Failed to clear history');
  return await res.json();
}

export async function clearRecentFiles() {
  const res = await fetch('/api/user/clear-recent-files', { method: 'POST' });
  if (!res.ok) throw new Error('Failed to clear recent files');
  return await res.json();
}

export async function openAppDataFolder() {
  const res = await fetch('/api/user/open-appdata', { method: 'POST' });
  if (!res.ok) throw new Error('Failed to open app data folder');
  return await res.json();
}
