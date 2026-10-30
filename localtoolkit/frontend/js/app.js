/**
 * app.js — Main application entry point.
 * Bootstraps the SPA, wires up the router, handles home and tool pages.
 */
import { Icons } from './icons.js';
import { TOOLS, TOOL_MAP, CATEGORIES } from './tools.js';
import { navigate, route, init as routerInit } from './router.js';
import { submitTool, downloadBlob, fetchHealth } from './api.js';
import { toast, fmtSize, createFileItem, makeDraggable, announce, setProgress } from './ui.js';

// ── App state ─────────────────────────────────────────────────────
let _health = null;
let _activeCategory = 'all';
let _searchQuery = '';
let _files = [];        // File[] for current tool
let _currentTool = null;

// ── Boot ──────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  _renderNavbar();
  _renderHome();
  _applyTheme(_loadTheme());

  // Router
  route('/', showHome);
  route('*', showTool);
  routerInit();

  // Health check (non-blocking)
  _health = await fetchHealth();
  _updateDepWarnings();
});

// ── Theme ─────────────────────────────────────────────────────────
function _loadTheme() {
  const saved = localStorage.getItem('theme');
  if (saved) return saved;
  return 'light';
}

function _applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('theme', theme);
}

function _toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme');
  _applyTheme(current === 'dark' ? 'light' : 'dark');
}

// ── Navbar ────────────────────────────────────────────────────────
function _renderNavbar() {
  const nav = document.getElementById('navbar');
  nav.innerHTML = `
    <div class="container">
      <a href="#" class="navbar__brand" aria-label="LocalToolkit home">
        ${Icons.get('logo')}
        <span class="navbar__wordmark">Local<span>Toolkit</span></span>
      </a>
      <nav class="navbar__nav" aria-label="Main navigation">
        <a href="#" class="navbar__link">All Tools</a>
        <a href="#/privacy" class="navbar__link">Privacy</a>
        <a href="#/about" class="navbar__link">About</a>
      </nav>
      <div class="navbar__actions">
        <button class="theme-toggle" id="theme-toggle" aria-label="Toggle dark mode" title="Toggle dark mode">
          <span class="icon-moon">${Icons.get('moon')}</span>
          <span class="icon-sun">${Icons.get('sun')}</span>
        </button>
        <button class="navbar__hamburger" id="hamburger" aria-label="Open menu" aria-expanded="false">
          ${Icons.get('menu')}
        </button>
      </div>
    </div>
  `;
  document.getElementById('theme-toggle').addEventListener('click', _toggleTheme);
  document.getElementById('hamburger').addEventListener('click', _openMobileNav);
}

function _openMobileNav() {
  let drawer = document.getElementById('mobile-nav');
  if (!drawer) {
    drawer = document.createElement('div');
    drawer.id = 'mobile-nav';
    drawer.className = 'mobile-nav';
    drawer.setAttribute('role', 'dialog');
    drawer.setAttribute('aria-modal', 'true');
    drawer.setAttribute('aria-label', 'Navigation menu');
    drawer.innerHTML = `
      <div class="mobile-nav__overlay"></div>
      <nav class="mobile-nav__drawer">
        <a href="#" class="mobile-nav__link">All Tools</a>
        <a href="#/privacy" class="mobile-nav__link">Privacy</a>
        <a href="#/about" class="mobile-nav__link">About</a>
      </nav>
    `;
    drawer.querySelector('.mobile-nav__overlay').onclick = () => {
      drawer.classList.remove('open');
    };
    document.body.appendChild(drawer);
  }
  drawer.classList.add('open');
  document.getElementById('hamburger').setAttribute('aria-expanded', 'true');
}

// ── Home page ─────────────────────────────────────────────────────
function _renderHome() {
  const home = document.getElementById('home-view');
  home.innerHTML = `
    <!-- Hero -->
    <section class="hero" aria-labelledby="hero-title">
      <div class="hero__eyebrow">
        ${Icons.get('lock')}
        100% Offline · Your files never leave this device
      </div>
      <h1 class="hero__title" id="hero-title">
        All File Tools in <span class="blue">One Place</span>
      </h1>
      <p class="hero__subtitle">
        Fast, private and works offline. No uploads to servers. No account required.
      </p>
      <div class="hero__search">
        <div class="search-bar" role="search">
          <span class="search-bar__icon" aria-hidden="true">${Icons.get('search')}</span>
          <input
            type="search"
            class="search-bar__input"
            id="search-input"
            placeholder="Search tools — compress, merge, convert…"
            aria-label="Search file tools"
            autocomplete="off"
          />
          <button class="search-bar__btn" id="search-btn" aria-label="Search">
            ${Icons.get('search')} Search
          </button>
        </div>
      </div>
    </section>

    <!-- Tools section -->
    <section class="tools-section container" aria-labelledby="tools-heading">
      <div class="tools-section__header">
        <div>
          <h2 id="tools-heading" class="sr-only">File Tools</h2>
          <div class="pills" role="group" aria-label="Filter by category" id="category-pills">
            ${CATEGORIES.map(c => `
              <button
                class="pill ${c.id === 'all' ? 'pill--active' : ''}"
                data-cat="${c.id}"
                aria-pressed="${c.id === 'all'}"
                type="button"
              >${c.label}</button>
            `).join('')}
          </div>
        </div>
        <span class="tools-count" id="tools-count" aria-live="polite"></span>
      </div>
      <div class="tool-grid" id="tool-grid" role="list" aria-label="Available tools">
      </div>
    </section>
  `;

  _renderGrid();

  // Explicit card click handler for immediate routing
  document.getElementById('tool-grid').addEventListener('click', (e) => {
    const card = e.target.closest('.tool-card');
    if (!card) return;
    const href = card.getAttribute('href');
    if (href && href.startsWith('#/')) {
      e.preventDefault();
      window.location.hash = href;
      showTool(href.replace('#/', '/'));
    }
  });

  // Explicit card click handler for immediate routing

  document.getElementById('tool-grid').addEventListener('click', (e) => {

    const card = e.target.closest('.tool-card');

    if (!card) return;

    const href = card.getAttribute('href');

    if (href && href.startsWith('#/')) {

      e.preventDefault();

      window.location.hash = href;

      showTool(href.replace('#/', '/'));

    }

  });



  // Search
  document.getElementById('search-input').addEventListener('input', (e) => {
    _searchQuery = e.target.value.toLowerCase().trim();
    _renderGrid();
  });
  document.getElementById('search-btn').addEventListener('click', () => {
    _searchQuery = document.getElementById('search-input').value.toLowerCase().trim();
    _renderGrid();
  });

  // Category pills
  document.getElementById('category-pills').addEventListener('click', (e) => {
    const pill = e.target.closest('[data-cat]');
    if (!pill) return;
    _activeCategory = pill.dataset.cat;
    document.querySelectorAll('.pill').forEach(p => {
      const active = p.dataset.cat === _activeCategory;
      p.classList.toggle('pill--active', active);
      p.setAttribute('aria-pressed', active);
    });
    _renderGrid();
  });
}

function _renderGrid() {
  const grid = document.getElementById('tool-grid');
  const countEl = document.getElementById('tools-count');
  if (!grid) return;

  const filtered = TOOLS.filter(t => {
    const catOk = _activeCategory === 'all' || t.category === _activeCategory;
    const searchOk = !_searchQuery ||
      t.name.toLowerCase().includes(_searchQuery) ||
      t.desc.toLowerCase().includes(_searchQuery) ||
      t.category.includes(_searchQuery);
    return catOk && searchOk;
  });

  if (countEl) countEl.textContent = `${filtered.length} tool${filtered.length !== 1 ? 's' : ''}`;

  if (filtered.length === 0) {
    grid.innerHTML = `
      <div class="empty-state" role="status">
        <span class="empty-state__icon">
          <svg width="48" height="48" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
            <circle cx="11" cy="11" r="8"/><path stroke-linecap="round" d="M21 21l-4.35-4.35"/>
          </svg>
        </span>
        <div class="empty-state__title">No tools found</div>
        <div class="empty-state__msg">Try a different search term or category.</div>
      </div>
    `;
    return;
  }

  grid.innerHTML = filtered.map(tool => {
    const unavailable = tool.requiresDep && _health &&
      !_health.dependencies?.[tool.requiresDep];
    return `
      <a
        href="#/${tool.id}"
        class="tool-card ${unavailable ? 'tool-card--unavailable' : ''}"
        style="--card-pastel: ${tool.cardBg}"
        role="listitem"
        aria-label="${tool.name}${unavailable ? ' (requires ' + tool.depName + ')' : ''}"
        title="${tool.desc}"
      >
        <div class="tool-card__icon-wrap">
          <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28"
               fill="none" viewBox="0 0 24 24"
               stroke="${tool.iconColor}" stroke-width="1.8">
            ${_getIconPaths(tool.icon)}
          </svg>
        </div>
        <span class="tool-card__name">${tool.name}</span>
      </a>
    `;
  }).join('');
}

// Extract inner SVG paths from Icons (strip outer svg tag)
function _getIconPaths(iconKey) {
  const svg = Icons.get(iconKey);
  return svg.replace(/<svg[^>]*>/, '').replace('</svg>', '');
}

// ── Dependency warnings ───────────────────────────────────────────
function _updateDepWarnings() {
  if (!_health) return;
  // Re-render grid with dep info
  _renderGrid();
}

// ── Show/hide views ───────────────────────────────────────────────
function showHome() {
  document.getElementById('home-view').style.display = '';
  document.getElementById('tool-view').style.display = 'none';
  _currentTool = null;
  _files = [];
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function showTool(path) {
  const toolId = path.replace(/^\//, '');

  // Info pages
  if (toolId === 'privacy') { _showInfoPage('privacy'); return; }
  if (toolId === 'about')   { _showInfoPage('about');   return; }

  const tool = TOOL_MAP[toolId];
  if (!tool) { navigate('/'); return; }

  _currentTool = tool;
  _files = [];

  document.getElementById('home-view').style.display = 'none';
  const view = document.getElementById('tool-view');
  view.style.display = 'block';

  _renderToolPage(tool);
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ── Tool Page (Two-Column Minimal Scrolling Layout) ───────────────
function _renderToolPage(tool) {
  const view = document.getElementById('tool-view');
  const depMissing = tool.requiresDep && _health && !_health.dependencies?.[tool.requiresDep];

  view.innerHTML = `
    <!-- Slim single-row topbar -->
    <div class="tool-topbar">
      <a href="#" class="btn-back" id="back-btn">
        <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" d="M19 12H5M12 5l-7 7 7 7"/></svg>
        All Tools
      </a>
      <div class="tool-topbar__icon" style="background:${tool.cardBg}">
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18"
             fill="none" viewBox="0 0 24 24"
             stroke="${tool.iconColor}" stroke-width="1.8">
          ${_getIconPaths(tool.icon)}
        </svg>
      </div>
      <div class="tool-topbar__info">
        <h1 class="tool-topbar__title">${tool.name}</h1>
        <span class="tool-topbar__desc">${tool.desc}</span>
      </div>
    </div>

    <!-- Two-column workspace -->
    <div class="tool-workspace">
      <!-- LEFT: Dropzone + uploaded file list -->
      <div class="tool-left">
        <div id="dropzone" class="dropzone" role="button" tabindex="0"
             aria-label="Drop ${tool.multi ? 'files' : 'a file'} here or click to browse">
          <input type="file" class="dropzone__input" id="file-input"
                 ${tool.multi ? 'multiple' : ''}
                 accept="${tool.accept}"
                 aria-label="Choose file${tool.multi ? 's' : ''}">
          <div class="dropzone__icon">${Icons.get('upload')}</div>
          <div class="dropzone__title" id="dropzone-title">Drop ${tool.multi ? 'files' : 'your file'} here</div>
          <p class="dropzone__subtitle" id="dropzone-sub">
            or <span class="dropzone__browse">browse</span> &middot; ${tool.accept.toUpperCase().replace(/\./g, '').replace(/,/g, ', ')}
          </p>
        </div>

        <div class="file-list-wrap">
          <div class="file-list" id="file-list" aria-live="polite" aria-label="Selected files"></div>
        </div>
      </div>

      <!-- RIGHT: Options + Action or Result view -->
      <div class="tool-right">
        <!-- Inline error banner -->
        <div class="error-panel" id="error-panel" role="alert">
          <span class="error-panel__icon">
            <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><path stroke-linecap="round" d="M12 8v4M12 16h.01"/></svg>
          </span>
          <span class="error-panel__msg" id="error-msg">Something went wrong.</span>
        </div>

        <!-- Options View -->
        <div class="tool-right__body" id="options-view">
          <div class="tool-right__header">
            <span>Configuration</span>
            <span class="badge badge--blue" id="file-badge">0 files</span>
          </div>

          ${depMissing ? `
            <div class="process-area__warning" role="alert">
              ${Icons.get('warn')}
              <div>
                <strong>${tool.depName} not found.</strong>
                <a href="${tool.depInstallUrl}" target="_blank" rel="noopener">Install ${tool.depName}</a> then restart.
              </div>
            </div>
          ` : ''}

          ${tool.note ? `
            <div class="process-area__warning" role="note">
              ${Icons.get('info')} <div>${tool.note}</div>
            </div>
          ` : ''}

          <div id="options-panel">
            ${_renderOptionsGroup(tool.options, tool.actionLabel)}
          </div>
        </div>

        <!-- Sticky Action section at bottom of right column -->
        <div class="tool-right__action" id="action-section">
          <div id="progress-wrap" style="display:none">
            <div class="progress-bar" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0">
              <div class="progress-bar__fill" id="progress-fill" style="width:0%"></div>
            </div>
            <p id="progress-label" style="font-size:.74rem;color:var(--muted);margin-top:3px;text-align:center">Processing…</p>
          </div>
          <button id="process-btn" class="btn btn--primary btn--full" ${depMissing ? 'disabled' : ''}>
            ${tool.actionLabel}
          </button>
        </div>

        <!-- Result View (replaces options view in right column when complete) -->
        <div class="result-panel" id="result-panel" role="status" aria-live="polite">
          <div class="result-panel__check">${Icons.get('check')}</div>
          <h3 class="result-panel__title">Processing Complete!</h3>
          <p class="result-panel__stats" id="result-stats"></p>
          <div class="result-panel__actions">
            <button id="download-btn" class="btn btn--primary btn--lg">
              ${Icons.get('download')} Download
            </button>
            <button id="again-btn" class="btn btn--secondary">
              ${Icons.get('refresh')} Process another file
            </button>
          </div>
        </div>
      </div>
    </div>
  `;

  _wireToolPage(tool);
}

function _renderOptionsGroup(options, actionLabel) {
  if (!options || options.length === 0) {
    return `
      <p style="font-size: .82rem; color: var(--muted); line-height: 1.5; margin: 4px 0 12px;">
        Add your files on the left and click <strong>${actionLabel}</strong> to begin. Everything processes 100% locally.
      </p>
    `;
  }

  const primary = options.filter(o => !o.advanced);
  const advanced = options.filter(o => o.advanced);

  let html = primary.map(opt => _renderOption(opt)).join('');

  if (advanced.length > 0) {
    html += `
      <details class="more-options">
        <summary>More options</summary>
        <div style="margin-top: 8px;">
          ${advanced.map(opt => _renderOption(opt)).join('')}
        </div>
      </details>
    `;
  }
  return html;
}

function _renderOption(opt) {
  const id = `opt-${opt.key}`;
  switch (opt.type) {
    case 'range': return `
      <div class="option-group">
        <div class="option-label">
          <label for="${id}">${opt.label}</label>
          <span class="option-label__val" id="${id}-val">
            ${opt.format ? opt.format(parseFloat(opt.default)) : opt.default}
          </span>
        </div>
        <input type="range" id="${id}" name="${opt.key}"
               min="${opt.min}" max="${opt.max}" step="${opt.step}"
               value="${opt.default}">
      </div>
    `;
    case 'select': return `
      <div class="option-group">
        <label for="${id}">${opt.label}</label>
        <select id="${id}" name="${opt.key}">
          ${opt.choices.map(c => `<option value="${c.value}" ${c.value === opt.default ? 'selected' : ''}>${c.label}</option>`).join('')}
        </select>
      </div>
    `;
    case 'number': return `
      <div class="option-group">
        <label for="${id}">${opt.label}</label>
        <input type="number" id="${id}" name="${opt.key}"
               value="${opt.default || ''}"
               ${opt.min != null ? `min="${opt.min}"` : ''}
               ${opt.max != null ? `max="${opt.max}"` : ''}>
      </div>
    `;
    case 'password': return `
      <div class="option-group">
        <label for="${id}">${opt.label}</label>
        <input type="password" id="${id}" name="${opt.key}"
               placeholder="${opt.placeholder || ''}"
               ${opt.required ? 'required' : ''} autocomplete="new-password">
      </div>
    `;
    default: return `
      <div class="option-group">
        <label for="${id}">${opt.label}</label>
        <input type="text" id="${id}" name="${opt.key}"
               placeholder="${opt.placeholder || ''}"
               value="${opt.default || ''}"
               ${opt.required ? 'required' : ''}>
        ${opt.hint ? `<p class="option-hint">${opt.hint}</p>` : ''}
      </div>
    `;
  }
}

// ── Wire tool page interactions ───────────────────────────────────
function _wireToolPage(tool) {
  const dropzone      = document.getElementById('dropzone');
  const dropzoneTitle = document.getElementById('dropzone-title');
  const dropzoneSub   = document.getElementById('dropzone-sub');
  const fileInput     = document.getElementById('file-input');
  const fileList      = document.getElementById('file-list');
  const fileBadge     = document.getElementById('file-badge');
  const processBtn    = document.getElementById('process-btn');
  const progressWrap  = document.getElementById('progress-wrap');
  const progressFill  = document.getElementById('progress-fill');
  const progressBar   = progressWrap?.querySelector('.progress-bar');
  const progressLabel = document.getElementById('progress-label');
  const optionsView   = document.getElementById('options-view');
  const actionSection = document.getElementById('action-section');
  const resultPanel   = document.getElementById('result-panel');
  const resultStats   = document.getElementById('result-stats');
  const downloadBtn   = document.getElementById('download-btn');
  const againBtn      = document.getElementById('again-btn');
  const errorPanel    = document.getElementById('error-panel');
  const errorMsg      = document.getElementById('error-msg');
  const backBtn       = document.getElementById('back-btn');
  const optionsPanel  = document.getElementById('options-panel');

  let _resultBlob = null;
  let _resultFilename = 'download';

  // Back button
  if (backBtn) {
    backBtn.addEventListener('click', (e) => {
      e.preventDefault();
      navigate('/');
    });
  }

  // Range option live labels
  tool.options.filter(o => o.type === 'range').forEach(opt => {
    const input = document.getElementById(`opt-${opt.key}`);
    const valEl = document.getElementById(`opt-${opt.key}-val`);
    if (input && valEl) {
      input.addEventListener('input', () => {
        valEl.textContent = opt.format ? opt.format(parseFloat(input.value)) : input.value;
      });
    }
  });

  // Dropzone interactions
  dropzone.addEventListener('dragover', (e) => { e.preventDefault(); dropzone.classList.add('drag-over'); });
  dropzone.addEventListener('dragleave', () => dropzone.classList.remove('drag-over'));
  dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.classList.remove('drag-over');
    _addFiles([...e.dataTransfer.files]);
  });
  dropzone.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fileInput.click(); }
  });
  dropzone.addEventListener('click', (e) => {
    if (e.target !== fileInput) {
      fileInput.click();
    }
  });
  fileInput.addEventListener('change', () => {
    if (fileInput.files && fileInput.files.length > 0) {
      _addFiles([...fileInput.files]);
      fileInput.value = '';
    }
  });

  function _addFiles(newFiles) {
    if (!tool.multi) _files = [];
    const accepted = newFiles.filter(f => {
      const ext = '.' + f.name.split('.').pop().toLowerCase();
      return tool.accept.split(',').some(a => a.trim() === ext || a.trim() === '.*');
    });
    if (accepted.length !== newFiles.length) {
      toast('error', 'Unsupported file type', `Accepted: ${tool.accept}`);
    }
    _files.push(...accepted);
    _renderFileList();
    _updateDropzoneState();
    if (_files.length > 0) {
      errorPanel.classList.remove('active');
    }
  }

  function _updateDropzoneState() {
    const hasFiles = _files.length > 0;
    dropzone.classList.toggle('dropzone--compact', hasFiles);
    if (hasFiles) {
      if (dropzoneTitle) dropzoneTitle.textContent = tool.multi ? 'Add more files' : 'Replace file';
      if (dropzoneSub) dropzoneSub.style.display = 'none';
    } else {
      if (dropzoneTitle) dropzoneTitle.textContent = `Drop ${tool.multi ? 'files' : 'your file'} here`;
      if (dropzoneSub) dropzoneSub.style.display = '';
    }
    if (fileBadge) {
      fileBadge.textContent = `${_files.length} file${_files.length !== 1 ? 's' : ''}`;
    }
  }

  function _renderFileList() {
    fileList.innerHTML = '';
    _files.forEach((file, i) => {
      const item = createFileItem(file, i, _removeFile, tool.multi);
      fileList.appendChild(item);
    });
    if (tool.multi) makeDraggable(fileList, _onReorder);
  }

  function _removeFile(idx) {
    _files.splice(idx, 1);
    _renderFileList();
    _updateDropzoneState();
  }

  function _onReorder(newOrder) {
    _files = newOrder.map(i => _files[parseInt(i)]);
  }

  // Process
  processBtn.addEventListener('click', _process);

  async function _process() {
    if (_files.length === 0) {
      toast('error', 'No files selected', 'Please add at least one file on the left.');
      return;
    }
    if (tool.id === 'merge-pdf' && _files.length < 2) {
      toast('error', 'Need 2+ files', 'Please upload at least 2 PDF files to merge.');
      return;
    }

    const formData = new FormData();

    // Single-file vs multi-file payload
    if (tool.multi) {
      _files.forEach(f => formData.append('files', f));
    } else {
      formData.append('file', _files[0]);
    }

    // Options validation & collection
    if (optionsPanel) {
      const inputs = optionsPanel.querySelectorAll('input, select');
      for (const el of inputs) {
        if (el.required && !el.value.trim()) {
          toast('error', 'Missing required option', `Please enter a value for "${el.previousElementSibling?.textContent || el.name}".`);
          return;
        }
        if (el.name) formData.set(el.name, el.value);
      }
    }

    // UI: show progress
    processBtn.setAttribute('disabled', 'true');
    progressWrap.style.display = '';
    errorPanel.classList.remove('active');
    const originalSize = _files.reduce((s, f) => s + f.size, 0);

    try {
      const result = await submitTool(tool.endpoint, formData, (pct) => {
        if (progressFill) progressFill.style.width = pct + '%';
        if (progressBar) progressBar.setAttribute('aria-valuenow', pct);
        if (progressLabel) progressLabel.textContent = pct < 60 ? 'Uploading…' : 'Processing…';
      });

      _resultBlob = result.blob;
      _resultFilename = result.filename || tool.outputName || 'download';

      // Switch right panel to result view
      progressWrap.style.display = 'none';
      optionsView.style.display = 'none';
      actionSection.style.display = 'none';
      resultPanel.classList.add('active');

      if (tool.showSizeDiff && originalSize > 0) {
        const saved = Math.max(0, originalSize - result.resultSize);
        const pct = Math.round((saved / originalSize) * 100);
        resultStats.innerHTML = pct > 0
          ? `<strong>Saved ${pct}%</strong> (${fmtSize(originalSize)} → ${fmtSize(result.resultSize)})`
          : `Output size: ${fmtSize(result.resultSize)}`;
      } else {
        resultStats.textContent = `Output size: ${fmtSize(result.resultSize)}`;
      }

      announce(`Done! ${tool.name} complete. Ready to download.`);
      toast('success', 'Done!', `${tool.name} completed successfully.`);
    } catch (err) {
      progressWrap.style.display = 'none';
      processBtn.removeAttribute('disabled');
      errorPanel.classList.add('active');
      errorMsg.textContent = err.message || 'An error occurred. Please try again.';
      announce(`Error: ${err.message}`);
    }
  }

  downloadBtn.addEventListener('click', () => {
    if (_resultBlob) downloadBlob(_resultBlob, _resultFilename);
  });

  againBtn.addEventListener('click', () => {
    _files = [];
    _resultBlob = null;
    fileList.innerHTML = '';
    _updateDropzoneState();
    optionsView.style.display = '';
    actionSection.style.display = '';
    resultPanel.classList.remove('active');
    errorPanel.classList.remove('active');
    processBtn.removeAttribute('disabled');
    if (progressFill) progressFill.style.width = '0%';
  });
}

// ── Info pages ────────────────────────────────────────────────────
function _showInfoPage(page) {
  document.getElementById('home-view').style.display = 'none';
  const view = document.getElementById('tool-view');
  view.style.display = 'block';

  const content = {
    privacy: `
      <div class="info-page">
        <h1>Privacy Policy</h1>
        <div class="badge badge--green" style="margin-bottom:24px">${Icons.get('lock')} 100% Local — No data leaves your device</div>
        <h2>What we collect</h2>
        <p>Nothing. LocalToolkit processes all files locally on your machine. No file contents, metadata, or personal information is ever transmitted anywhere.</p>
        <h2>Network access</h2>
        <p>LocalToolkit binds only to <code>127.0.0.1</code> (localhost) and never makes outgoing network requests. You can verify this by running it with Wi-Fi disabled.</p>
        <h2>Temporary files</h2>
        <p>Files are processed in isolated temporary directories that are automatically deleted immediately after each operation. Any leftover temp files are swept on startup.</p>
        <h2>Fonts & assets</h2>
        <p>All fonts, icons, and assets are bundled locally. No CDN, no Google Fonts, no external scripts.</p>
        <h2>Analytics</h2>
        <p>None. Zero. LocalToolkit contains no analytics, crash reporting, or telemetry of any kind.</p>
      </div>
    `,
    about: `
      <div class="info-page">
        <h1>About LocalToolkit</h1>
        <p>LocalToolkit is a free, open-source, 100% offline file tools application. It runs on your laptop and processes all files locally — nothing ever leaves your machine.</p>
        <h2>Tech stack</h2>
        <ul>
          <li><strong>Backend:</strong> Python 3.12, FastAPI, Uvicorn</li>
          <li><strong>PDF:</strong> pypdf, PyMuPDF</li>
          <li><strong>Images:</strong> Pillow, pillow-heif, img2pdf</li>
          <li><strong>Documents:</strong> pdf2docx, LibreOffice (optional)</li>
          <li><strong>Frontend:</strong> Plain HTML, CSS, vanilla JS — no framework, no CDN</li>
        </ul>
        <h2>To run</h2>
        <p><code>python run.py</code> — opens automatically in your browser.</p>
        <h2>Adding a new tool</h2>
        <p>Add a backend router in <code>backend/tools/</code> and a registry entry in <code>frontend/js/tools.js</code>. That's it.</p>
      </div>
    `,
  };

  view.innerHTML = `
    <nav aria-label="Breadcrumb" class="breadcrumb">
      <a href="#" class="breadcrumb__link">${Icons.get('arrowLeft')} All Tools</a>
      <span class="breadcrumb__sep">›</span>
      <span class="breadcrumb__current">${page.charAt(0).toUpperCase() + page.slice(1)}</span>
    </nav>
    ${content[page] || '<p>Page not found.</p>'}
  `;
}

