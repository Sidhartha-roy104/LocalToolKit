/**
 * api.js — Fetch wrappers + job polling.
 * All requests go to the same origin (127.0.0.1); no external calls.
 */

const BASE = '';  // same origin

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

