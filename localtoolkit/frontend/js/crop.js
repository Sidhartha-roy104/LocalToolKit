/**
 * crop.js — Interactive Canvas Crop Tool with live dimensions (px, cm, mm, in at DPI).
 * Uses Pointer Events with setPointerCapture, 4 edges, 4 corners, box movement, and aspect lock.
 */
export class InteractiveCropper {
  constructor(containerEl, options = {}) {
    this.container = containerEl;
    this.dpi = options.dpi || 150;
    this.unit = options.unit || 'cm';
    this.aspectRatio = options.aspectRatio || null; // null = free, or number w/h
    this.onCropChange = options.onCropChange || (() => {});
    this.img = null;
    this.canvas = null;
    this.ctx = null;
    this.cropRect = { x: 0, y: 0, w: 100, h: 100 }; // in canvas display coordinates
    this.isDragging = false;
    this.activeHandle = null; // 'tl', 'tr', 'br', 'bl', 't', 'b', 'l', 'r', 'move'
    this.startPos = { x: 0, y: 0 };
    this.startRect = { x: 0, y: 0, w: 0, h: 0 };
    this.scale = 1.0;
    this._objectUrl = null;
    this._boundPointerDown = null;
    this._boundPointerMove = null;
    this._boundPointerUp = null;
    this._boundPointerCancel = null;
  }

  mount(containerEl) {
    if (containerEl) this.container = containerEl;
  }

  destroy() {
    if (this.canvas) {
      if (this._boundPointerDown) this.canvas.removeEventListener('pointerdown', this._boundPointerDown);
      if (this._boundPointerMove) this.canvas.removeEventListener('pointermove', this._boundPointerMove);
      if (this._boundPointerUp) this.canvas.removeEventListener('pointerup', this._boundPointerUp);
      if (this._boundPointerCancel) this.canvas.removeEventListener('pointercancel', this._boundPointerCancel);
    }
    if (this._objectUrl) {
      URL.revokeObjectURL(this._objectUrl);
      this._objectUrl = null;
    }
    this.img = null;
    this.canvas = null;
    this.ctx = null;
    if (this.container) {
      this.container.innerHTML = '';
    }
  }

  loadImage(fileOrBlob) {
    if (this._objectUrl) {
      URL.revokeObjectURL(this._objectUrl);
    }
    this._objectUrl = URL.createObjectURL(fileOrBlob);
    const img = new Image();
    img.onload = () => {
      this.img = img;
      this._setupCanvas();
    };
    img.src = this._objectUrl;
  }

  setDpi(dpi) {
    this.dpi = Math.max(72, parseInt(dpi || 150, 10));
    this._updateReadout();
  }

  setUnit(unit) {
    this.unit = unit || 'cm';
    this._updateReadout();
  }

  setAspectRatio(ratio) {
    this.aspectRatio = ratio ? parseFloat(ratio) : null;
    if (this.aspectRatio && this.canvas) {
      const cw = this.canvas.width;
      const ch = this.canvas.height;
      let w = cw * 0.7;
      let h = w / this.aspectRatio;
      if (h > ch * 0.8) {
        h = ch * 0.8;
        w = h * this.aspectRatio;
      }
      this.cropRect = {
        x: Math.round((cw - w) / 2),
        y: Math.round((ch - h) / 2),
        w: Math.round(w),
        h: Math.round(h),
      };
      this._redraw();
      this._notifyChange();
    }
  }

  _setupCanvas() {
    if (!this.container) return;
    this.container.innerHTML = `
      <div class="cropper-wrap">
        <div class="cropper-toolbar">
          <span class="cropper-title">Live Canvas Crop</span>
          <div class="cropper-aspects" id="aspect-btns">
            <button type="button" class="btn btn--xs ${!this.aspectRatio ? 'btn--primary' : 'btn--secondary'}" data-ratio="free">Free</button>
            <button type="button" class="btn btn--xs" data-ratio="1">1:1 Square</button>
            <button type="button" class="btn btn--xs" data-ratio="0.7778">3.5:4.5 Photo</button>
            <button type="button" class="btn btn--xs" data-ratio="2.0">4:2 Signature</button>
          </div>
        </div>
        <div class="cropper-canvas-stage">
          <canvas id="crop-canvas" style="touch-action:none;"></canvas>
        </div>
        <div class="cropper-readout" id="crop-readout">
          Drag handles or move box to crop
        </div>
      </div>
    `;

    this.canvas = document.getElementById('crop-canvas');
    this.ctx = this.canvas.getContext('2d');

    const maxW = Math.min(560, this.container.clientWidth || 500);
    const maxH = 340;
    const aspect = this.img.width / this.img.height;

    let dispW = maxW;
    let dispH = dispW / aspect;
    if (dispH > maxH) {
      dispH = maxH;
      dispW = dispH * aspect;
    }

    this.canvas.width = Math.round(dispW);
    this.canvas.height = Math.round(dispH);
    this.scale = this.img.width / this.canvas.width;

    const padX = Math.round(this.canvas.width * 0.1);
    const padY = Math.round(this.canvas.height * 0.1);
    this.cropRect = {
      x: padX,
      y: padY,
      w: this.canvas.width - (2 * padX),
      h: this.canvas.height - (2 * padY),
    };

    this._wirePointerEvents();
    this._redraw();
    this._notifyChange();

    const aspectBtns = document.getElementById('aspect-btns');
    aspectBtns?.querySelectorAll('button').forEach(btn => {
      btn.addEventListener('click', () => {
        aspectBtns.querySelectorAll('button').forEach(b => {
          b.classList.remove('btn--primary');
          b.classList.add('btn--secondary');
        });
        btn.classList.remove('btn--secondary');
        btn.classList.add('btn--primary');
        const r = btn.dataset.ratio;
        this.setAspectRatio(r === 'free' ? null : parseFloat(r));
      });
    });
  }

  _getCanvasPos(e) {
    const rect = this.canvas.getBoundingClientRect();
    const scaleX = this.canvas.width / rect.width;
    const scaleY = this.canvas.height / rect.height;
    return {
      x: Math.max(0, Math.min(this.canvas.width, (e.clientX - rect.left) * scaleX)),
      y: Math.max(0, Math.min(this.canvas.height, (e.clientY - rect.top) * scaleY)),
    };
  }

  _detectHandle(pos) {
    const r = this.cropRect;
    const cornerRadius = 14;
    const edgeThreshold = 10;

    // Corners (checked first)
    if (Math.hypot(pos.x - r.x, pos.y - r.y) <= cornerRadius) return 'tl';
    if (Math.hypot(pos.x - (r.x + r.w), pos.y - r.y) <= cornerRadius) return 'tr';
    if (Math.hypot(pos.x - (r.x + r.w), pos.y - (r.y + r.h)) <= cornerRadius) return 'br';
    if (Math.hypot(pos.x - r.x, pos.y - (r.y + r.h)) <= cornerRadius) return 'bl';

    // Edges
    if (Math.abs(pos.y - r.y) <= edgeThreshold && pos.x >= r.x && pos.x <= r.x + r.w) return 't';
    if (Math.abs(pos.y - (r.y + r.h)) <= edgeThreshold && pos.x >= r.x && pos.x <= r.x + r.w) return 'b';
    if (Math.abs(pos.x - r.x) <= edgeThreshold && pos.y >= r.y && pos.y <= r.y + r.h) return 'l';
    if (Math.abs(pos.x - (r.x + r.w)) <= edgeThreshold && pos.y >= r.y && pos.y <= r.y + r.h) return 'r';

    // Interior (move)
    if (pos.x >= r.x && pos.x <= r.x + r.w && pos.y >= r.y && pos.y <= r.y + r.h) return 'move';

    return null;
  }

  _updateCursor(handle) {
    if (!this.canvas) return;
    const cursors = {
      tl: 'nwse-resize',
      br: 'nwse-resize',
      tr: 'nesw-resize',
      bl: 'nesw-resize',
      t: 'ns-resize',
      b: 'ns-resize',
      l: 'ew-resize',
      r: 'ew-resize',
      move: 'move',
    };
    this.canvas.style.cursor = cursors[handle] || 'default';
  }

  _wirePointerEvents() {
    const c = this.canvas;

    this._boundPointerDown = (e) => {
      e.preventDefault();
      const pos = this._getCanvasPos(e);
      const handle = this._detectHandle(pos);
      if (!handle) return;

      this.isDragging = true;
      this.activeHandle = handle;
      this.startPos = pos;
      this.startRect = { ...this.cropRect };
      c.setPointerCapture(e.pointerId);
      this._updateCursor(handle);
    };

    this._boundPointerMove = (e) => {
      const pos = this._getCanvasPos(e);

      if (!this.isDragging) {
        const hoverHandle = this._detectHandle(pos);
        this._updateCursor(hoverHandle);
        return;
      }

      e.preventDefault();
      const dx = pos.x - this.startPos.x;
      const dy = pos.y - this.startPos.y;
      const s = this.startRect;
      const minSize = 20;
      const cw = this.canvas.width;
      const ch = this.canvas.height;
      let { x, y, w, h } = s;

      if (this.activeHandle === 'move') {
        x = Math.max(0, Math.min(cw - w, s.x + dx));
        y = Math.max(0, Math.min(ch - h, s.y + dy));
      } else {
        // Handle edges and corners
        if (this.activeHandle.includes('r')) {
          w = Math.max(minSize, Math.min(cw - s.x, s.w + dx));
        }
        if (this.activeHandle.includes('b')) {
          h = Math.max(minSize, Math.min(ch - s.y, s.h + dy));
        }
        if (this.activeHandle.includes('l')) {
          const newX = Math.max(0, Math.min(s.x + s.w - minSize, s.x + dx));
          w = s.w + (s.x - newX);
          x = newX;
        }
        if (this.activeHandle.includes('t')) {
          const newY = Math.max(0, Math.min(s.y + s.h - minSize, s.y + dy));
          h = s.h + (s.y - newY);
          y = newY;
        }

        // Apply aspect ratio lock if active
        if (this.aspectRatio) {
          if (this.activeHandle === 'r' || this.activeHandle === 'l') {
            h = Math.max(minSize, Math.min(ch - y, w / this.aspectRatio));
            w = h * this.aspectRatio;
          } else {
            w = Math.max(minSize, Math.min(cw - x, h * this.aspectRatio));
            h = w / this.aspectRatio;
          }
        }
      }

      this.cropRect = { x: Math.round(x), y: Math.round(y), w: Math.round(w), h: Math.round(h) };
      this._redraw();
      this._updateReadout();
    };

    const onPointerEnd = (e) => {
      if (this.isDragging) {
        this.isDragging = false;
        try { c.releasePointerCapture(e.pointerId); } catch {}
        this._updateCursor(null);
        this._notifyChange();
      }
    };

    this._boundPointerUp = onPointerEnd;
    this._boundPointerCancel = onPointerEnd;

    c.addEventListener('pointerdown', this._boundPointerDown);
    c.addEventListener('pointermove', this._boundPointerMove);
    c.addEventListener('pointerup', this._boundPointerUp);
    c.addEventListener('pointercancel', this._boundPointerCancel);
  }

  _notifyChange() {
    const coords = this.getCropParams();
    if (coords) {
      this.onCropChange(coords);
    }
  }

  getCropParams() {
    if (!this.img || !this.scale) return null;
    const r = this.cropRect;
    return {
      x: Math.max(0, Math.round(r.x * this.scale)),
      y: Math.max(0, Math.round(r.y * this.scale)),
      w: Math.max(1, Math.round(r.w * this.scale)),
      h: Math.max(1, Math.round(r.h * this.scale)),
    };
  }

  _updateReadout() {
    const el = document.getElementById('crop-readout');
    if (!el || !this.scale) return;

    const r = this.cropRect;
    const pxW = Math.round(r.w * this.scale);
    const pxH = Math.round(r.h * this.scale);

    const dpi = this.dpi || 150;
    const cmW = (pxW / (dpi / 2.54)).toFixed(2);
    const cmH = (pxH / (dpi / 2.54)).toFixed(2);
    const mmW = (pxW / (dpi / 25.4)).toFixed(1);
    const mmH = (pxH / (dpi / 25.4)).toFixed(1);
    const inW = (pxW / dpi).toFixed(2);
    const inH = (pxH / dpi).toFixed(2);

    let unitText = '';
    if (this.unit === 'mm') unitText = `${mmW} × ${mmH} mm`;
    else if (this.unit === 'in') unitText = `${inW} × ${inH} in`;
    else unitText = `${cmW} × ${cmH} cm`;

    el.innerHTML = `<strong>${pxW} × ${pxH} px</strong> · ${unitText} @ ${dpi} DPI`;
  }

  _redraw() {
    if (!this.ctx || !this.canvas || !this.img) return;
    const ctx = this.ctx;
    const cw = this.canvas.width;
    const ch = this.canvas.height;
    const r = this.cropRect;

    ctx.clearRect(0, 0, cw, ch);
    ctx.drawImage(this.img, 0, 0, cw, ch);

    // Dark overlay outside crop box
    ctx.fillStyle = 'rgba(0, 0, 0, 0.55)';
    ctx.fillRect(0, 0, cw, r.y);
    ctx.fillRect(0, r.y + r.h, cw, ch - (r.y + r.h));
    ctx.fillRect(0, r.y, r.x, r.h);
    ctx.fillRect(r.x + r.w, r.y, cw - (r.x + r.w), r.h);

    // Grid rule of thirds inside crop box
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.35)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(r.x + r.w / 3, r.y);
    ctx.lineTo(r.x + r.w / 3, r.y + r.h);
    ctx.moveTo(r.x + (2 * r.w) / 3, r.y);
    ctx.lineTo(r.x + (2 * r.w) / 3, r.y + r.h);
    ctx.moveTo(r.x, r.y + r.h / 3);
    ctx.lineTo(r.x + r.w, r.y + r.h / 3);
    ctx.moveTo(r.x, r.y + (2 * r.h) / 3);
    ctx.lineTo(r.x + r.w, r.y + (2 * r.h) / 3);
    ctx.stroke();

    // Crop box outline
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 2;
    ctx.strokeRect(r.x, r.y, r.w, r.h);

    // Draw 4 corner handles
    const handleSize = 10;
    ctx.fillStyle = '#2563EB';
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 2;

    const corners = [
      [r.x, r.y],
      [r.x + r.w, r.y],
      [r.x + r.w, r.y + r.h],
      [r.x, r.y + r.h],
    ];
    corners.forEach(([cx, cy]) => {
      ctx.fillRect(cx - handleSize / 2, cy - handleSize / 2, handleSize, handleSize);
      ctx.strokeRect(cx - handleSize / 2, cy - handleSize / 2, handleSize, handleSize);
    });

    // Draw 4 edge handles (pill bars)
    const edgeLen = 16;
    const edgeThick = 6;
    const edges = [
      [r.x + r.w / 2 - edgeLen / 2, r.y - edgeThick / 2, edgeLen, edgeThick], // Top
      [r.x + r.w / 2 - edgeLen / 2, r.y + r.h - edgeThick / 2, edgeLen, edgeThick], // Bottom
      [r.x - edgeThick / 2, r.y + r.h / 2 - edgeLen / 2, edgeThick, edgeLen], // Left
      [r.x + r.w - edgeThick / 2, r.y + r.h / 2 - edgeLen / 2, edgeThick, edgeLen], // Right
    ];
    edges.forEach(([ex, ey, ew, eh]) => {
      ctx.fillRect(ex, ey, ew, eh);
      ctx.strokeRect(ex, ey, ew, eh);
    });

    this._updateReadout();
  }
}
