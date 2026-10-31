/**
 * crop.js — Interactive Canvas Crop Tool with live dimensions (px, cm, mm, in at DPI).
 * Fully self-contained with mount() and destroy() lifecycle methods.
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
    this.origCrop = { x: 0, y: 0, w: 100, h: 100 }; // in image natural coordinates
    this.isDragging = false;
    this.activeHandle = null;
    this.startPos = { x: 0, y: 0 };
    this.scale = 1.0;
    this._objectUrl = null;
    this._listeners = null;
  }

  mount(containerEl) {
    if (containerEl) this.container = containerEl;
  }

  destroy() {
    if (this._listeners) {
      window.removeEventListener('mousemove', this._listeners.onMove);
      window.removeEventListener('mouseup', this._listeners.onEnd);
      window.removeEventListener('touchmove', this._listeners.onMove);
      window.removeEventListener('touchend', this._listeners.onEnd);
      if (this.canvas) {
        this.canvas.removeEventListener('mousedown', this._listeners.onStart);
        this.canvas.removeEventListener('touchstart', this._listeners.onStart);
      }
      this._listeners = null;
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
    this.dpi = dpi;
    this._updateReadout();
  }

  setUnit(unit) {
    this.unit = unit;
    this._updateReadout();
  }

  setAspectRatio(ratio) {
    this.aspectRatio = ratio;
    if (ratio && this.img && this.canvas) {
      const cw = this.canvas.width;
      const ch = this.canvas.height;
      let w = cw * 0.7;
      let h = w / ratio;
      if (h > ch * 0.8) {
        h = ch * 0.8;
        w = h * ratio;
      }
      this.cropRect = {
        x: (cw - w) / 2,
        y: (ch - h) / 2,
        w: w,
        h: h,
      };
      this._redraw();
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
          <canvas id="crop-canvas"></canvas>
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

    const padX = this.canvas.width * 0.1;
    const padY = this.canvas.height * 0.1;
    this.cropRect = {
      x: padX,
      y: padY,
      w: this.canvas.width - (2 * padX),
      h: this.canvas.height - (2 * padY),
    };

    this._wireEvents();
    this._redraw();

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

  _wireEvents() {
    const c = this.canvas;
    const getPos = (e) => {
      const rect = c.getBoundingClientRect();
      const clientX = e.touches ? e.touches[0].clientX : e.clientX;
      const clientY = e.touches ? e.touches[0].clientY : e.clientY;
      return {
        x: (clientX - rect.left) * (c.width / rect.width),
        y: (clientY - rect.top) * (c.height / rect.height),
      };
    };

    const handleRadius = 12;

    const onStart = (e) => {
      e.preventDefault();
      const pos = getPos(e);
      const r = this.cropRect;

      if (Math.hypot(pos.x - r.x, pos.y - r.y) < handleRadius) this.activeHandle = 'tl';
      else if (Math.hypot(pos.x - (r.x + r.w), pos.y - r.y) < handleRadius) this.activeHandle = 'tr';
      else if (Math.hypot(pos.x - (r.x + r.w), pos.y - (r.y + r.h)) < handleRadius) this.activeHandle = 'br';
      else if (Math.hypot(pos.x - r.x, pos.y - (r.y + r.h)) < handleRadius) this.activeHandle = 'bl';
      else if (pos.x >= r.x && pos.x <= r.x + r.w && pos.y >= r.y && pos.y <= r.y + r.h) this.activeHandle = 'move';
      else return;

      this.isDragging = true;
      this.startPos = pos;
    };

    const onMove = (e) => {
      if (!this.isDragging) return;
      e.preventDefault();
      const pos = getPos(e);
      const dx = pos.x - this.startPos.x;
      const dy = pos.y - this.startPos.y;
      const r = this.cropRect;
      const minSize = 25;

      if (this.activeHandle === 'move') {
        r.x = Math.max(0, min(this.canvas.width - r.w, r.x + dx));
        r.y = Math.max(0, min(this.canvas.height - r.h, r.y + dy));
      } else if (this.activeHandle === 'br') {
        r.w = Math.max(minSize, min(this.canvas.width - r.x, r.w + dx));
        r.h = this.aspectRatio ? r.w / this.aspectRatio : Math.max(minSize, min(this.canvas.height - r.y, r.h + dy));
      } else if (this.activeHandle === 'tl') {
        const newX = Math.max(0, min(r.x + r.w - minSize, r.x + dx));
        const newY = Math.max(0, min(r.y + r.h - minSize, r.y + dy));
        r.w += r.x - newX;
        r.h += r.y - newY;
        r.x = newX;
        r.y = newY;
      } else if (this.activeHandle === 'tr') {
        const newY = Math.max(0, min(r.y + r.h - minSize, r.y + dy));
        r.w = Math.max(minSize, min(this.canvas.width - r.x, r.w + dx));
        r.h += r.y - newY;
        r.y = newY;
      } else if (this.activeHandle === 'bl') {
        const newX = Math.max(0, min(r.x + r.w - minSize, r.x + dx));
        r.w += r.x - newX;
        r.x = newX;
        r.h = Math.max(minSize, min(this.canvas.height - r.y, r.h + dy));
      }

      this.startPos = pos;
      this._redraw();
    };

    const onEnd = () => {
      if (this.isDragging) {
        this.isDragging = false;
        this.activeHandle = null;
      }
    };

    this._listeners = { onStart, onMove, onEnd };

    c.addEventListener('mousedown', onStart);
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onEnd);
    c.addEventListener('touchstart', onStart, { passive: false });
    window.addEventListener('touchmove', onMove, { passive: false });
    window.addEventListener('touchend', onEnd);
  }

  _redraw() {
    if (!this.ctx || !this.img || !this.canvas) return;
    const ctx = this.ctx;
    const c = this.canvas;
    const r = this.cropRect;

    ctx.clearRect(0, 0, c.width, c.height);

    ctx.drawImage(this.img, 0, 0, c.width, c.height);

    ctx.fillStyle = 'rgba(0, 0, 0, 0.50)';
    ctx.fillRect(0, 0, c.width, r.y);
    ctx.fillRect(0, r.y + r.h, c.width, c.height - (r.y + r.h));
    ctx.fillRect(0, r.y, r.x, r.h);
    ctx.fillRect(r.x + r.w, r.y, c.width - (r.x + r.w), r.h);

    ctx.strokeStyle = '#2563EB';
    ctx.lineWidth = 2;
    ctx.strokeRect(r.x, r.y, r.w, r.h);

    ctx.strokeStyle = 'rgba(255, 255, 255, 0.35)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(r.x + r.w / 3, r.y); ctx.lineTo(r.x + r.w / 3, r.y + r.h);
    ctx.moveTo(r.x + 2 * r.w / 3, r.y); ctx.lineTo(r.x + 2 * r.w / 3, r.y + r.h);
    ctx.moveTo(r.x, r.y + r.h / 3); ctx.lineTo(r.x + r.w, r.y + r.h / 3);
    ctx.moveTo(r.x, r.y + 2 * r.h / 3); ctx.lineTo(r.x + r.w, r.y + 2 * r.h / 3);
    ctx.stroke();

    const handleSize = 6;
    ctx.fillStyle = '#2563EB';
    ctx.strokeStyle = '#FFFFFF';
    ctx.lineWidth = 2;
    const corners = [
      [r.x, r.y],
      [r.x + r.w, r.y],
      [r.x + r.w, r.y + r.h],
      [r.x, r.y + r.h],
    ];
    corners.forEach(([cx, cy]) => {
      ctx.beginPath();
      ctx.arc(cx, cy, handleSize, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
    });

    this.origCrop = {
      x: Math.round(r.x * this.scale),
      y: Math.round(r.y * this.scale),
      w: Math.round(r.w * this.scale),
      h: Math.round(r.h * this.scale),
    };

    this._updateReadout();
    this.onCropChange(this.origCrop);
  }

  _updateReadout() {
    const el = document.getElementById('crop-readout');
    if (!el || !this.origCrop) return;

    const pxW = this.origCrop.w;
    const pxH = this.origCrop.h;

    const cmW = (pxW / this.dpi * 2.54).toFixed(1);
    const cmH = (pxH / this.dpi * 2.54).toFixed(1);

    const mmW = (pxW / this.dpi * 25.4).toFixed(0);
    const mmH = (pxH / this.dpi * 25.4).toFixed(0);

    const inW = (pxW / this.dpi).toFixed(2);
    const inH = (pxH / this.dpi).toFixed(2);

    el.innerHTML = `<strong>${pxW} × ${pxH} px</strong> · ${cmW} × ${cmH} cm (${mmW} × ${mmH} mm) · ${inW} × ${inH} in @ ${this.dpi} DPI`;
  }

  getCropParams() {
    return this.origCrop;
  }
}
