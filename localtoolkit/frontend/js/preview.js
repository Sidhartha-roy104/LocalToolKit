/**
 * preview.js — Universal Reusable Preview Component for LocalToolkit.
 * Supports:
 * 1. Interactive canvas crop with handles and live unit readouts.
 * 2. Page thumbnail grid (interactive rotate, reorder, remove, select) for PDF tools
 *    with lazy IntersectionObserver rendering for 100+ page documents.
 * 3. Zoomable image before/after preview.
 * 4. Live stamping preview for Watermark and Page Numbers.
 * 5. Document / First-page PDF preview.
 * 
 * Exposes explicit mount() and destroy() lifecycle methods.
 */
import { getPDFThumbnails, getWatermarkPreview, getPageNumbersPreview, getDocPreview } from './api.js';
import { InteractiveCropper } from './crop.js';
import { Icons } from './icons.js';

export class ToolPreview {
  constructor(containerEl, options = {}) {
    this.container = containerEl;
    this.onStateChange = options.onStateChange || (() => {});
    this.tool = null;
    this.files = [];
    this.currentPageState = [];
    this.zoomLevel = 1.0;
    this.activeTab = 'before';
    this.resultBlobUrl = null;
    this.cropper = null;
    this._observer = null;
    this._createdUrls = new Set();
  }

  mount(containerEl) {
    if (containerEl) this.container = containerEl;
  }

  destroy() {
    // 1. Disconnect any active intersection observers
    if (this._observer) {
      this._observer.disconnect();
      this._observer = null;
    }

    // 2. Destroy cropper if active
    if (this.cropper) {
      this.cropper.destroy();
      this.cropper = null;
    }

    // 3. Revoke all tracked object URLs
    for (const url of this._createdUrls) {
      try { URL.revokeObjectURL(url); } catch {}
    }
    this._createdUrls.clear();

    if (this.resultBlobUrl) {
      try { URL.revokeObjectURL(this.resultBlobUrl); } catch {}
      this.resultBlobUrl = null;
    }

    // 4. Clear container DOM and state
    if (this.container) {
      this.container.innerHTML = '';
    }
    this.currentPageState = [];
    this.files = [];
    this.tool = null;
  }

  reset() {
    this.destroy();
  }

  _trackUrl(url) {
    if (url && typeof url === 'string' && url.startsWith('blob:')) {
      this._createdUrls.add(url);
    }
    return url;
  }

  async update(tool, files, currentOptions = {}, resultBlob = null) {
    this.tool = tool;
    this.files = files;

    if (resultBlob) {
      if (this.resultBlobUrl) {
        URL.revokeObjectURL(this.resultBlobUrl);
        this._createdUrls.delete(this.resultBlobUrl);
      }
      this.resultBlobUrl = this._trackUrl(URL.createObjectURL(resultBlob));
    }

    if (!files || files.length === 0) {
      this.reset();
      return;
    }

    const toolId = tool.id;

    // 1. Live Crop for Resize tool
    if (toolId === 'resize-image') {
      this._renderCropper(currentOptions);
    }
    // 2. Page thumbnail grid for page-manipulation tools
    else if (['merge-pdf', 'split-pdf', 'rotate-pdf', 'organize-pdf', 'remove-pages', 'extract-pages'].includes(toolId)) {
      await this._renderThumbnailGrid(toolId);
    }
    // 3. Live stamping preview for Watermark
    else if (toolId === 'watermark-pdf') {
      await this._renderWatermarkPreview(currentOptions);
    }
    // 4. Live stamping preview for Page Numbers
    else if (toolId === 'pagenumbers-pdf') {
      await this._renderPageNumbersPreview(currentOptions);
    }
    // 5. Word to PDF / PDF to Word doc preview
    else if (['word-to-pdf', 'pdf-to-word', 'scan-cleanup'].includes(toolId)) {
      await this._renderDocPreview(toolId);
    }
    // 6. Image tools (zoomable before/after)
    else if (['compress-image', 'convert-image', 'image-to-pdf', 'combine-photo-signature', 'redact'].includes(toolId) || files[0].type.startsWith('image/')) {
      this._renderImagePreview();
    }
    // 7. PDF single page / first-page before & after
    else if (toolId === 'compress-pdf' || toolId === 'protect-pdf' || toolId === 'unlock-pdf' || toolId === 'pdf-sign' || toolId === 'remove-metadata') {
      await this._renderPDFBeforeAfter();
    }
  }

  // ── Interactive Crop Stage ────────────────────────────────────────
  _renderCropper(options) {
    if (!this.container.querySelector('.cropper-wrap')) {
      this.cropper = new InteractiveCropper(this.container, {
        dpi: parseInt(options.dpi || 150, 10),
        unit: options.unit || 'cm',
        onCropChange: (cropCoords) => {
          this.cropCoords = cropCoords;
          this.onStateChange({ crop: cropCoords });
        },
      });
      this.cropper.loadImage(this.files[0]);
    } else if (this.cropper) {
      if (options.dpi) this.cropper.setDpi(parseInt(options.dpi, 10));
      if (options.unit) this.cropper.setUnit(options.unit);
    }
  }

  getCropParams() {
    return this.cropper ? this.cropper.getCropParams() : null;
  }

  // ── Thumbnail Grid with Lazy IntersectionObserver ─────────────────
  async _renderThumbnailGrid(toolId) {
    this.container.innerHTML = `
      <div class="preview-panel">
        <div class="preview-panel__header">
          <div class="preview-panel__title">
            <span>Page Visualizer</span>
            <span class="preview-panel__badge" id="preview-page-count">Loading pages…</span>
          </div>
          <div class="preview-panel__hint">
            ${toolId === 'rotate-pdf' ? 'Click ↻ to rotate page' :
              toolId === 'remove-pages' ? 'Click ✕ to exclude page' :
              toolId === 'split-pdf' || toolId === 'extract-pages' ? 'Click page to toggle selection' :
              'Drag or use arrows to reorder pages'}
          </div>
        </div>
        <div class="preview-grid" id="preview-thumbnail-grid">
          <div class="preview-loading">Rendering page thumbnails…</div>
        </div>
      </div>
    `;

    try {
      const file = this.files[0];
      const data = await getPDFThumbnails(file, 100);

      this.currentPageState = data.thumbnails.map(t => ({
        page: t.page,
        rotation: 0,
        removed: false,
        selected: true,
        data: t.data,
      }));

      const gridEl = document.getElementById('preview-thumbnail-grid');
      const badgeEl = document.getElementById('preview-page-count');
      if (badgeEl) badgeEl.textContent = `${data.total_pages} page${data.total_pages !== 1 ? 's' : ''}`;

      this._drawThumbnails(gridEl, toolId);
    } catch (err) {
      const gridEl = document.getElementById('preview-thumbnail-grid');
      if (gridEl) {
        gridEl.innerHTML = `<div class="preview-error">Thumbnail preview unavailable (${err.message}).</div>`;
      }
    }
  }

  _drawThumbnails(gridEl, toolId) {
    if (!gridEl) return;

    // Disconnect old observer before re-drawing
    if (this._observer) {
      this._observer.disconnect();
      this._observer = null;
    }

    gridEl.innerHTML = this.currentPageState.map((p, idx) => `
      <div class="thumb-card ${p.removed ? 'thumb-card--removed' : ''} ${p.selected ? 'thumb-card--selected' : ''}"
           data-index="${idx}" data-page="${p.page}" draggable="true">
        <div class="thumb-card__header">
          <span class="thumb-card__num">Page ${p.page}</span>
          <div class="thumb-card__actions">
            <button type="button" class="thumb-btn thumb-btn--rotate" title="Rotate 90° clockwise" data-action="rotate" data-index="${idx}">
              ↻
            </button>
            ${toolId === 'remove-pages' || toolId === 'split-pdf' || toolId === 'extract-pages' ? `
              <button type="button" class="thumb-btn thumb-btn--toggle" title="Toggle page" data-action="toggle" data-index="${idx}">
                ${p.removed ? '＋' : '✕'}
              </button>
            ` : ''}
          </div>
        </div>
        <div class="thumb-card__img-wrap" data-action="card-click" data-index="${idx}">
          <img data-src="${p.data}" alt="Page ${p.page}" class="thumb-lazy-img"
               style="transform: rotate(${p.rotation}deg); transition: transform 0.2s ease;">
        </div>
        <div class="thumb-card__footer">
          <button type="button" class="thumb-arrow-btn" data-action="move-left" data-index="${idx}" ${idx === 0 ? 'disabled' : ''}>◀</button>
          <span class="thumb-card__order">#${idx + 1}</span>
          <button type="button" class="thumb-arrow-btn" data-action="move-right" data-index="${idx}" ${idx === this.currentPageState.length - 1 ? 'disabled' : ''}>▶</button>
        </div>
      </div>
    `).join('');

    // Lazy load thumbnails via IntersectionObserver
    if ('IntersectionObserver' in window) {
      this._observer = new IntersectionObserver((entries, obs) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            const img = entry.target.querySelector('img[data-src]');
            if (img && img.dataset.src) {
              img.src = img.dataset.src;
              img.removeAttribute('data-src');
            }
            obs.unobserve(entry.target);
          }
        });
      }, { root: gridEl, rootMargin: '120px' });

      gridEl.querySelectorAll('.thumb-card').forEach(card => this._observer.observe(card));
    } else {
      // Fallback: immediate load
      gridEl.querySelectorAll('img[data-src]').forEach(img => {
        img.src = img.dataset.src;
        img.removeAttribute('data-src');
      });
    }

    gridEl.querySelectorAll('button').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const action = btn.dataset.action;
        const index = parseInt(btn.dataset.index, 10);
        this._handleThumbAction(action, index, toolId, gridEl);
      });
    });

    gridEl.querySelectorAll('.thumb-card__img-wrap').forEach(wrap => {
      wrap.addEventListener('click', () => {
        const index = parseInt(wrap.dataset.index, 10);
        this._handleThumbAction('toggle', index, toolId, gridEl);
      });
    });

    this._wireDragDrop(gridEl, toolId);
    this._syncStateWithTool(toolId);
  }

  _handleThumbAction(action, index, toolId, gridEl) {
    if (action === 'rotate') {
      this.currentPageState[index].rotation = (this.currentPageState[index].rotation + 90) % 360;
    } else if (action === 'toggle') {
      if (toolId === 'remove-pages') {
        this.currentPageState[index].removed = !this.currentPageState[index].removed;
      } else {
        this.currentPageState[index].selected = !this.currentPageState[index].selected;
      }
    } else if (action === 'move-left' && index > 0) {
      const item = this.currentPageState.splice(index, 1)[0];
      this.currentPageState.splice(index - 1, 0, item);
    } else if (action === 'move-right' && index < this.currentPageState.length - 1) {
      const item = this.currentPageState.splice(index, 1)[0];
      this.currentPageState.splice(index + 1, 0, item);
    }
    this._drawThumbnails(gridEl, toolId);
  }

  _wireDragDrop(gridEl, toolId) {
    let draggedIndex = null;
    gridEl.querySelectorAll('.thumb-card').forEach(card => {
      card.addEventListener('dragstart', (e) => {
        draggedIndex = parseInt(card.dataset.index, 10);
        card.classList.add('thumb-card--dragging');
        e.dataTransfer.effectAllowed = 'move';
      });
      card.addEventListener('dragend', () => {
        card.classList.remove('thumb-card--dragging');
      });
      card.addEventListener('dragover', (e) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
      });
      card.addEventListener('drop', (e) => {
        e.preventDefault();
        const targetIndex = parseInt(card.dataset.index, 10);
        if (draggedIndex !== null && targetIndex !== draggedIndex) {
          const item = this.currentPageState.splice(draggedIndex, 1)[0];
          this.currentPageState.splice(targetIndex, 0, item);
          this._drawThumbnails(gridEl, toolId);
        }
      });
    });
  }

  _syncStateWithTool(toolId) {
    if (toolId === 'organize-pdf') {
      const orderStr = this.currentPageState.map(p => p.page).join(',');
      const input = document.querySelector('input[name="order"]');
      if (input) {
        input.value = orderStr;
        input.dispatchEvent(new Event('input', { bubbles: true }));
      }
    } else if (toolId === 'remove-pages') {
      const removedPages = this.currentPageState.filter(p => p.removed).map(p => p.page).join(',');
      const input = document.querySelector('input[name="pages"]');
      if (input) {
        input.value = removedPages || 'none';
        input.dispatchEvent(new Event('input', { bubbles: true }));
      }
    } else if (toolId === 'extract-pages' || toolId === 'split-pdf') {
      const selected = this.currentPageState.filter(p => p.selected).map(p => p.page).join(',');
      const input = document.querySelector('input[name="pages"]') || document.querySelector('input[name="ranges"]');
      if (input && selected) {
        input.value = selected;
        input.dispatchEvent(new Event('input', { bubbles: true }));
      }
    }
    this.onStateChange(this.currentPageState);
  }

  // ── Live Watermark Preview ────────────────────────────────────────
  async _renderWatermarkPreview(options) {
    const text = options.text || 'CONFIDENTIAL';
    const opacity = parseFloat(options.opacity || 0.2);
    const fontSize = parseInt(options.font_size || 36, 10);
    const color = options.color || 'gray';

    this._renderLiveCanvasStage('Watermark Live Preview', 'Page 1 stamping preview updates in real time');

    try {
      const file = this.files[0];
      const res = await getWatermarkPreview(file, text, opacity, fontSize, 45, color);
      this._updatePreviewImage(res.data, 'Page 1 Preview');
    } catch {
      // Fallback
    }
  }

  // ── Live Page Numbers Preview ─────────────────────────────────────
  async _renderPageNumbersPreview(options) {
    const position = options.position || 'bottom-center';
    const start = parseInt(options.start || 1, 10);
    const fontSize = parseInt(options.font_size || 12, 10);

    this._renderLiveCanvasStage('Page Numbers Live Preview', `Position: ${position} · Starts at: ${start}`);

    try {
      const file = this.files[0];
      const res = await getPageNumbersPreview(file, position, start, fontSize);
      this._updatePreviewImage(res.data, 'Page 1 Preview');
    } catch {
      // Fallback
    }
  }

  _renderLiveCanvasStage(title, subtitle) {
    if (!this.container.querySelector('.preview-stage')) {
      this.container.innerHTML = `
        <div class="preview-panel">
          <div class="preview-panel__header">
            <div class="preview-panel__title">
              <span>${title}</span>
            </div>
            <div class="preview-panel__hint" id="preview-stage-hint">${subtitle}</div>
          </div>
          <div class="preview-stage" id="preview-stage">
            <div class="preview-loading">Generating live preview…</div>
          </div>
        </div>
      `;
    } else {
      const hint = document.getElementById('preview-stage-hint');
      if (hint) hint.textContent = subtitle;
    }
  }

  _updatePreviewImage(src, alt) {
    const stage = document.getElementById('preview-stage');
    if (!stage) return;
    stage.innerHTML = `
      <div class="preview-zoom-wrap" style="transform: scale(${this.zoomLevel})">
        <img src="${src}" alt="${alt}" class="preview-zoom-img">
      </div>
      <div class="preview-zoom-controls">
        <button type="button" class="zoom-btn" id="zoom-out" title="Zoom out">−</button>
        <span class="zoom-level">${Math.round(this.zoomLevel * 100)}%</span>
        <button type="button" class="zoom-btn" id="zoom-in" title="Zoom in">＋</button>
        <button type="button" class="zoom-btn" id="zoom-reset" title="Fit">Fit</button>
      </div>
    `;

    document.getElementById('zoom-in')?.addEventListener('click', () => {
      this.zoomLevel = Math.min(2.5, this.zoomLevel + 0.2);
      this._updatePreviewImage(src, alt);
    });
    document.getElementById('zoom-out')?.addEventListener('click', () => {
      this.zoomLevel = Math.max(0.5, this.zoomLevel - 0.2);
      this._updatePreviewImage(src, alt);
    });
    document.getElementById('zoom-reset')?.addEventListener('click', () => {
      this.zoomLevel = 1.0;
      this._updatePreviewImage(src, alt);
    });
  }

  // ── Document Preview (Word/PDF) ───────────────────────────────────
  async _renderDocPreview(toolId) {
    this._renderLiveCanvasStage('Document First Page Preview', 'Rendering document layout…');
    try {
      const file = this.files[0];
      if (file.name.toLowerCase().endsWith('.pdf')) {
        const data = await getPDFThumbnails(file, 1);
        if (data.thumbnails?.[0]) {
          this._updatePreviewImage(data.thumbnails[0].data, 'Document Preview');
        }
      } else {
        const res = await getDocPreview(file);
        if (res.available && res.data) {
          this._updatePreviewImage(res.data, 'Word Document Preview');
        } else {
          const stage = document.getElementById('preview-stage');
          if (stage) {
            stage.innerHTML = `
              <div class="preview-notice">
                <svg width="32" height="32" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8">
                  <path stroke-linecap="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                </svg>
                <span>First page preview unavailable for this file format. You can still process it safely.</span>
              </div>
            `;
          }
        }
      }
    } catch {
      // Fallback
    }
  }

  // ── Image Zoomable Before / After ─────────────────────────────────
  _renderImagePreview() {
    const file = this.files[0];
    const originalUrl = this._trackUrl(URL.createObjectURL(file));

    this.container.innerHTML = `
      <div class="preview-panel">
        <div class="preview-panel__header">
          <div class="preview-panel__title">
            <span>Image Preview</span>
            <span class="preview-panel__badge">${(file.size / 1024).toFixed(1)} KB</span>
          </div>
          ${this.resultBlobUrl ? `
            <div class="preview-tabs">
              <button type="button" class="preview-tab ${this.activeTab === 'before' ? 'preview-tab--active' : ''}" id="tab-before">Original</button>
              <button type="button" class="preview-tab ${this.activeTab === 'after' ? 'preview-tab--active' : ''}" id="tab-after">Result</button>
            </div>
          ` : ''}
        </div>
        <div class="preview-stage" id="preview-stage">
          <div class="preview-zoom-wrap" id="zoom-stage" style="transform: scale(${this.zoomLevel})">
            <img src="${this.activeTab === 'after' && this.resultBlobUrl ? this.resultBlobUrl : originalUrl}"
                 alt="${file.name}" class="preview-zoom-img">
          </div>
          <div class="preview-zoom-controls">
            <button type="button" class="zoom-btn" id="zoom-out">−</button>
            <span class="zoom-level">${Math.round(this.zoomLevel * 100)}%</span>
            <button type="button" class="zoom-btn" id="zoom-in">＋</button>
            <button type="button" class="zoom-btn" id="zoom-reset">Fit</button>
          </div>
        </div>
      </div>
    `;

    document.getElementById('zoom-in')?.addEventListener('click', () => {
      this.zoomLevel = Math.min(3.0, this.zoomLevel + 0.25);
      this._renderImagePreview();
    });
    document.getElementById('zoom-out')?.addEventListener('click', () => {
      this.zoomLevel = Math.max(0.4, this.zoomLevel - 0.25);
      this._renderImagePreview();
    });
    document.getElementById('zoom-reset')?.addEventListener('click', () => {
      this.zoomLevel = 1.0;
      this._renderImagePreview();
    });

    document.getElementById('tab-before')?.addEventListener('click', () => {
      this.activeTab = 'before';
      this._renderImagePreview();
    });
    document.getElementById('tab-after')?.addEventListener('click', () => {
      this.activeTab = 'after';
      this._renderImagePreview();
    });
  }

  // ── PDF First-Page Before / After ─────────────────────────────────
  async _renderPDFBeforeAfter() {
    this._renderLiveCanvasStage('PDF Document Preview', 'Rendering first-page preview…');
    try {
      const file = this.files[0];
      const data = await getPDFThumbnails(file, 1);
      if (data.thumbnails?.[0]) {
        this._updatePreviewImage(data.thumbnails[0].data, 'PDF First Page Preview');
      }
    } catch (err) {
      const stage = document.getElementById('preview-stage');
      if (stage) stage.innerHTML = `<div class="preview-error">${err.message}</div>`;
    }
  }
}
