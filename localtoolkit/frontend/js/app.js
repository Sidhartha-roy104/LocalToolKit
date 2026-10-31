/**
 * app.js — Main application entry point for LocalToolkit.
 * Integrates:
 * - 100% offline SPA router
 * - Govt Form helper & Presets selector (approximate, unbundled custom presets)
 * - Tool preview component with explicit mount()/destroy() lifecycle
 * - History, Favorites & User Settings saved to OS app data
 * - Live size estimation & sanitized output filenames
 * - "Save to My Files" local folder organizer with cloud detection
 * - Simple Mode & Multilingual (English, Hindi, Telugu)
 */
import { Icons } from './icons.js';
import { TOOLS, TOOL_MAP, CATEGORIES } from './tools.js';
import { navigate, route, init as routerInit } from './router.js';
import {
  submitTool,
  downloadBlob,
  fetchHealth,
  getUserSettings,
  updateUserSettings,
  recordToolUsage,
  recordRecentFile,
  toggleFavorite,
  clearHistory,
  clearRecentFiles,
  openAppDataFolder,
} from './api.js';
import { toast, fmtSize, createFileItem, makeDraggable, announce, setProgress } from './ui.js';
import { ToolPreview } from './preview.js';
import { renderMyFilesView, saveToMyFiles } from './my_files.js';

// ── App state ─────────────────────────────────────────────────────
let _health = null;
let _activeCategory = 'all';
let _searchQuery = '';
let _files = [];
let _currentTool = null;
let _translations = {};
let _lang = localStorage.getItem('localtoolkit_lang') || 'en';
let _simpleMode = localStorage.getItem('localtoolkit_simple') === 'true';
let _presets = [];
let _activeToolPreview = null;
let _userSettings = {
  favorites: [],
  recent_tools: [],
  history_paused: false,
  recent_files_enabled: false,
  recent_files: [],
  my_files_path: '',
};

// ── Lifecycle helper ──────────────────────────────────────────────
function _destroyActivePreview() {
  if (_activeToolPreview) {
    try {
      _activeToolPreview.destroy();
    } catch (err) {
      console.warn('Error destroying preview:', err);
    }
    _activeToolPreview = null;
  }
}

// ── Boot ──────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  await _loadTranslations();
  await _loadPresets();
  _userSettings = await getUserSettings();

  _applySimpleMode(_simpleMode);
  _renderNavbar();
  _renderHome();
  _applyTheme(_loadTheme());

  // Setup Routes
  route('/', showHome);
  route('/my-files', showMyFiles);
  route('/settings', showSettings);
  route('*', showTool);
  routerInit();

  // Async health check
  fetchHealth().then(h => {
    _health = h;
    _updateDepWarnings();
  });
});

async function _loadTranslations() {
  try {
    const res = await fetch('/data/translations.json');
    if (res.ok) _translations = await res.json();
  } catch {
    _translations = {};
  }
}

async function _loadPresets() {
  try {
    const res = await fetch('/api/presets');
    if (res.ok) _presets = await res.json();
  } catch {
    _presets = [];
  }
}

function t(key, fallback = '') {
  return _translations[_lang]?.[key] || _translations['en']?.[key] || fallback || key;
}

// ── Theme & Modes ─────────────────────────────────────────────────
function _loadTheme() {
  return localStorage.getItem('localtoolkit_theme') || 'light';
}

function _applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('localtoolkit_theme', theme);
}

function _toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme');
  _applyTheme(current === 'dark' ? 'light' : 'dark');
}

function _applySimpleMode(enable) {
  _simpleMode = enable;
  document.body.classList.toggle('simple-mode', enable);
  localStorage.setItem('localtoolkit_simple', enable ? 'true' : 'false');
}

// ── Navbar ────────────────────────────────────────────────────────
function _renderNavbar() {
  const nav = document.getElementById('navbar');
  nav.innerHTML = `
    <div class="container navbar__inner">
      <a href="#" class="navbar__brand" aria-label="LocalToolkit Home">
        <span class="navbar__logo">${Icons.get('logo')}</span>
        <span class="navbar__title">Local<span class="blue">Toolkit</span></span>
      </a>
      <nav class="navbar__nav" aria-label="Main navigation">
        <a href="#" class="navbar__link" id="nav-tools">${t('all_tools', 'All Tools')}</a>
        <a href="#/my-files" class="navbar__link" id="nav-myfiles">📁 ${t('my_files', 'My Files')}</a>
        <a href="#/settings" class="navbar__link" id="nav-settings">⚙️ Settings</a>
        <a href="#/privacy" class="navbar__link">${t('privacy', 'Privacy')}</a>
        <a href="#/about" class="navbar__link">${t('about', 'About')}</a>
      </nav>
      <div class="navbar__actions">
        <!-- Language selector -->
        <select id="lang-select" class="select select--sm" aria-label="Select Language" style="width: auto; padding: 2px 6px; font-size: .76rem;">
          <option value="en" ${_lang === 'en' ? 'selected' : ''}>English</option>
          <option value="hi" ${_lang === 'hi' ? 'selected' : ''}>हिंदी</option>
          <option value="te" ${_lang === 'te' ? 'selected' : ''}>తెలుగు</option>
        </select>

        <!-- Simple mode toggle button -->
        <button type="button" class="btn btn--sm ${_simpleMode ? 'btn--primary' : 'btn--secondary'}" id="simple-toggle" title="Toggle simplified layout for easy form filling">
          ${_simpleMode ? '✓ Simple' : 'Simple Mode'}
        </button>

        <!-- Theme toggle -->
        <button class="theme-toggle" id="theme-toggle" aria-label="Toggle dark mode" title="Toggle dark mode">
          <span class="icon-moon">${Icons.get('moon')}</span>
          <span class="icon-sun">${Icons.get('sun')}</span>
        </button>
      </div>
    </div>
  `;

  document.getElementById('theme-toggle').addEventListener('click', _toggleTheme);
  document.getElementById('lang-select').addEventListener('change', (e) => {
    _lang = e.target.value;
    localStorage.setItem('localtoolkit_lang', _lang);
    _renderNavbar();
    if (_currentTool) _renderToolPage(_currentTool);
    else _renderHome();
  });
  document.getElementById('simple-toggle').addEventListener('click', () => {
    _applySimpleMode(!_simpleMode);
    _renderNavbar();
  });
}

// ── Home page ─────────────────────────────────────────────────────
function _renderHome() {
  _destroyActivePreview();

  const recentTools = (!_userSettings.history_paused && _userSettings.recent_tools && _userSettings.recent_tools.length > 0)
    ? _userSettings.recent_tools
        .map(item => (typeof item === 'string' ? item : item.id))
        .map(id => TOOL_MAP[id])
        .filter(Boolean)
    : [];

  const recentRowHtml = recentTools.length > 0 ? `
    <div class="recent-tools-row" aria-label="Recently used tools">
      <span class="recent-tools-label">🕒 Recent:</span>
      ${recentTools.map(t => `
        <a href="#/${t.id}" class="recent-tool-chip" title="${t.desc}">
          <span>${t.name}</span>
        </a>
      `).join('')}
    </div>
  ` : '';

  const home = document.getElementById('home-view');
  home.innerHTML = `
    <!-- Compact Hero -->
    <section class="hero" aria-labelledby="hero-title">
      <div class="hero__eyebrow">
        ${Icons.get('lock')}
        100% Offline · Your files never leave this device
      </div>
      <h1 class="hero__title" id="hero-title">
        All File Tools in <span class="blue">One Place</span>
      </h1>
      <p class="hero__subtitle">
        ${t('hero_sub', 'Fast, private and works offline. No uploads. No account required.')}
      </p>

      <!-- Indian Govt Form Upload Helper Section -->
      <div class="govt-helper">
        <div class="govt-helper__title">
          <span>🎯</span> ${t('what_uploading', 'What are you uploading for your application?')}
        </div>
        <p class="govt-helper__subtitle">
          One-click shortcuts tuned for UPSC, SSC, IBPS, GATE, Passport & State Govt portals (approximate guides):
        </p>
        <div class="govt-helper__grid">
          <a href="#/resize-image?preset=ssc-photo" class="govt-card">
            <span class="govt-card__badge">📷 ${t('cat_photo', 'Photograph')}</span>
            <span class="govt-card__name">Passport Photo</span>
            <span class="govt-card__spec">3.5 × 4.5 cm / 20–50 KB</span>
          </a>
          <a href="#/resize-image?preset=ssc-signature" class="govt-card">
            <span class="govt-card__badge">✍️ ${t('cat_signature', 'Signature')}</span>
            <span class="govt-card__name">Signature Scan</span>
            <span class="govt-card__spec">Clean ink on white / 10–20 KB</span>
          </a>
          <a href="#/compress-pdf?preset=cert-100kb" class="govt-card">
            <span class="govt-card__badge">📜 ${t('cat_certificate', 'Certificate')}</span>
            <span class="govt-card__name">Marksheet / Caste</span>
            <span class="govt-card__spec">PDF under 100 KB or 300 KB</span>
          </a>
          <a href="#/redact" class="govt-card">
            <span class="govt-card__badge">🛡️ ${t('cat_idproof', 'ID Proof')}</span>
            <span class="govt-card__name">Mask Aadhaar / ID</span>
            <span class="govt-card__spec">Blackout Aadhaar / Address</span>
          </a>
        </div>
      </div>

      <!-- Compact Search Bar -->
      <div class="search-wrap" role="search">
        <span class="search-icon">${Icons.get('search')}</span>
        <input
          type="search"
          id="search-input"
          class="search-input"
          placeholder="${t('search_placeholder', 'Search tools (e.g. compress pdf, photo resize, docx)...')}"
          value="${_searchQuery}"
          aria-label="Search tools"
          autocomplete="off"
          spellcheck="false"
        >
        <button class="search-btn" id="search-btn" aria-label="Search">
          ${Icons.get('search')}
        </button>
      </div>

      <!-- Category Filter Pills -->
      <div class="category-pills" id="category-pills" role="tablist" aria-label="Tool categories">
        ${CATEGORIES.map(cat => `
          <button
            class="pill ${cat.id === _activeCategory ? 'pill--active' : ''}"
            data-cat="${cat.id}"
            role="tab"
            aria-selected="${cat.id === _activeCategory}"
          >${cat.label}</button>
        `).join('')}
      </div>
    </section>

    <!-- Tools Section -->
    <section class="tools-section container" aria-label="Tools list">
      ${recentRowHtml}
      <div class="tools-section__header">
        <span class="tools-section__count" id="tools-count"></span>
      </div>
      <div class="tool-grid" id="tool-grid" role="list"></div>
    </section>
  `;

  _renderGrid();

  document.getElementById('search-input').addEventListener('input', (e) => {
    _searchQuery = e.target.value.toLowerCase().trim();
    _renderGrid();
  });
  document.getElementById('search-btn').addEventListener('click', () => {
    _searchQuery = document.getElementById('search-input').value.toLowerCase().trim();
    _renderGrid();
  });

  document.getElementById('category-pills').addEventListener('click', (e) => {
    const pill = e.target.closest('[data-cat]');
    if (!pill) return;
    _activeCategory = pill.dataset.cat;
    document.querySelectorAll('.pill').forEach(p => {
      const active = p.dataset.cat === _activeCategory;
      p.classList.toggle('pill--active', active);
      p.setAttribute('aria-selected', active);
    });
    _renderGrid();
  });
}

function _renderGrid() {
  const grid = document.getElementById('tool-grid');
  const countEl = document.getElementById('tools-count');
  if (!grid) return;

  const filtered = TOOLS.filter(t => {
    const isFav = _userSettings.favorites && _userSettings.favorites.includes(t.id);
    const catOk = _activeCategory === 'all'
      || (_activeCategory === 'favorites' && isFav)
      || t.category === _activeCategory;
    const searchOk = !_searchQuery ||
      t.name.toLowerCase().includes(_searchQuery) ||
      t.desc.toLowerCase().includes(_searchQuery) ||
      t.category.includes(_searchQuery);
    return catOk && searchOk;
  });

  if (countEl) countEl.textContent = `${filtered.length} tool${filtered.length !== 1 ? 's' : ''}`;

  if (filtered.length === 0) {
    grid.innerHTML = `
      <div class="empty-state">
        <div class="empty-state__title">No tools found</div>
        <div class="empty-state__msg">Try a different search term or category.</div>
      </div>
    `;
    return;
  }

  grid.innerHTML = filtered.map(tool => {
    const unavailable = tool.requiresDep && _health && !_health.dependencies?.[tool.requiresDep];
    const isFav = _userSettings.favorites && _userSettings.favorites.includes(tool.id);
    return `
      <div
        class="tool-card ${unavailable ? 'tool-card--unavailable' : ''}"
        style="--card-pastel: ${tool.cardBg}"
        role="listitem"
        aria-label="${tool.name}"
        title="${tool.desc}"
      >
        <button type="button" class="tool-card__star ${isFav ? 'tool-card__star--active' : ''}"
                data-tool="${tool.id}" title="${isFav ? 'Starred in Favorites' : 'Add to Favorites'}">
          ${isFav ? '★' : '☆'}
        </button>
        <a href="#/${tool.id}" style="text-decoration:none; display:flex; flex-direction:column; align-items:center; width:100%; height:100%; justify-content:center;">
          <div class="tool-card__icon-wrap">
            <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28"
                 fill="none" viewBox="0 0 24 24"
                 stroke="${tool.iconColor}" stroke-width="1.8">
              ${_getIconPaths(tool.icon)}
            </svg>
          </div>
          <span class="tool-card__name">${tool.name}</span>
        </a>
      </div>
    `;
  }).join('');

  grid.querySelectorAll('.tool-card__star').forEach(starBtn => {
    starBtn.addEventListener('click', async (e) => {
      e.preventDefault();
      e.stopPropagation();
      const tid = starBtn.dataset.tool;
      try {
        const res = await toggleFavorite(tid);
        _userSettings.favorites = res.favorites || [];
        _renderGrid();
      } catch (err) {
        toast('error', 'Error', err.message);
      }
    });
  });
}

function _getIconPaths(iconKey) {
  const svg = Icons.get(iconKey);
  return svg.replace(/<svg[^>]*>/, '').replace('</svg>', '');
}

function _updateDepWarnings() {
  if (!_health) return;
  _renderGrid();
}

// ── Show/hide views ───────────────────────────────────────────────
function showHome() {
  _destroyActivePreview();
  document.getElementById('home-view').style.display = '';
  document.getElementById('my-files-view').style.display = 'none';
  document.getElementById('settings-view').style.display = 'none';
  document.getElementById('tool-view').style.display = 'none';
  _currentTool = null;
  _files = [];
  _renderHome();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function showMyFiles() {
  _destroyActivePreview();
  document.getElementById('home-view').style.display = 'none';
  document.getElementById('settings-view').style.display = 'none';
  document.getElementById('tool-view').style.display = 'none';
  const mfView = document.getElementById('my-files-view');
  mfView.style.display = 'block';
  _currentTool = null;
  _files = [];
  renderMyFilesView(mfView, _lang);
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

async function showSettings() {
  _destroyActivePreview();
  document.getElementById('home-view').style.display = 'none';
  document.getElementById('my-files-view').style.display = 'none';
  document.getElementById('tool-view').style.display = 'none';
  const stView = document.getElementById('settings-view');
  stView.style.display = 'block';
  _currentTool = null;
  _files = [];
  await _renderSettingsPage();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function showTool(path) {
  _destroyActivePreview();
  const [cleanPath, queryString] = path.replace(/^\//, '').split('?');
  const toolId = cleanPath;

  if (toolId === 'my-files') { showMyFiles(); return; }
  if (toolId === 'settings') { showSettings(); return; }
  if (toolId === 'privacy')  { _showInfoPage('privacy'); return; }
  if (toolId === 'about')    { _showInfoPage('about');   return; }

  const tool = TOOL_MAP[toolId];
  if (!tool) { navigate('/'); return; }

  _currentTool = tool;
  _files = [];

  // Record tool usage
  recordToolUsage(tool.id).then(async () => {
    _userSettings = await getUserSettings();
  });

  document.getElementById('home-view').style.display = 'none';
  document.getElementById('my-files-view').style.display = 'none';
  document.getElementById('settings-view').style.display = 'none';
  const view = document.getElementById('tool-view');
  view.style.display = 'block';

  let initialPreset = null;
  if (queryString) {
    const params = new URLSearchParams(queryString);
    const pId = params.get('preset');
    if (pId) initialPreset = _presets.find(p => p.id === pId);
  }

  _renderToolPage(tool, initialPreset);
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ── Settings Page ─────────────────────────────────────────────────
async function _renderSettingsPage() {
  const stView = document.getElementById('settings-view');
  const settings = await getUserSettings();
  _userSettings = settings;

  stView.innerHTML = `
    <div class="settings-wrap">
      <div class="tool-topbar" style="margin-bottom:0">
        <a href="#" class="btn-back" id="settings-back-btn">
          <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" d="M19 12H5M12 5l-7 7 7 7"/></svg>
          Back to Tools
        </a>
      </div>

      <h1 style="font-size:1.5rem; font-weight:800; margin-bottom:var(--sp-2)">Settings & Local Privacy</h1>
      <p style="color:var(--muted); font-size:0.88rem; margin-bottom:var(--sp-4)">
        Manage local history, storage directories, and device preferences. Everything stays 100% on this machine.
      </p>

      <!-- History & Privacy Card -->
      <div class="settings-card">
        <div class="settings-card__header">
          <span class="settings-card__title">🕒 Tool Usage History</span>
        </div>
        <div class="settings-card__desc">
          Shows your recently used tools on the Home screen for quick access (max 12 tools).
        </div>
        <div style="display:flex; align-items:center; gap:var(--sp-3); margin-bottom:var(--sp-3)">
          <label style="display:flex; align-items:center; gap:8px; cursor:pointer; font-size:0.88rem; font-weight:600">
            <input type="checkbox" id="setting-pause-history" ${settings.history_paused ? 'checked' : ''}>
            Pause tool history
          </label>
          <button type="button" class="btn btn--sm btn--secondary" id="btn-clear-history">Clear Tool History</button>
        </div>
      </div>

      <!-- Recent Files Card -->
      <div class="settings-card">
        <div class="settings-card__header">
          <span class="settings-card__title">📄 Recent Files List</span>
        </div>
        <div class="settings-card__desc">
          Off by default. Stores only processed file names and sizes (never file contents).
        </div>
        <div style="display:flex; align-items:center; gap:var(--sp-3); margin-bottom:var(--sp-3)">
          <label style="display:flex; align-items:center; gap:8px; cursor:pointer; font-size:0.88rem; font-weight:600">
            <input type="checkbox" id="setting-recent-files" ${settings.recent_files_enabled ? 'checked' : ''}>
            Enable recent files list
          </label>
          <button type="button" class="btn btn--sm btn--secondary" id="btn-clear-recent-files">Clear Recent Files</button>
        </div>
      </div>

      <!-- My Files Path Card -->
      <div class="settings-card">
        <div class="settings-card__header">
          <span class="settings-card__title">📁 "My Files" Storage Folder</span>
        </div>
        <div class="settings-card__desc">
          Default folder on your computer where files saved with "Save to My Files" are organized.
        </div>
        <div style="display:flex; gap:var(--sp-2); align-items:center">
          <input type="text" id="setting-my-files-path" class="input" style="flex:1" value="${settings.my_files_path || ''}">
          <button type="button" class="btn btn--primary btn--sm" id="btn-save-my-files-path">Update Path</button>
        </div>
        ${settings.cloud_warning ? `
          <div class="cloud-warning-box">
            <strong>⚠️ Cloud Sync Detected:</strong> This folder appears to be inside <strong>${settings.cloud_warning}</strong>. Files placed here may be automatically uploaded by your cloud client. To maintain 100% offline privacy, choose a local folder outside cloud sync.
          </div>
        ` : ''}
      </div>

      <!-- What's Stored On This Device Card -->
      <div class="settings-card">
        <div class="settings-card__header">
          <span class="settings-card__title">🔒 What's Stored on this Device</span>
          <button type="button" class="btn btn--secondary btn--sm" id="btn-open-appdata">Open AppData Folder</button>
        </div>
        <div class="settings-card__desc">
          LocalToolkit stores only application settings in your user app data directory:
        </div>
        <div style="background:var(--bg-2); padding:var(--sp-3); border-radius:var(--r-md); font-family:monospace; font-size:0.8rem; word-break:break-all; margin-bottom:var(--sp-2)">
          ${settings.app_data_path || 'AppData/LocalToolkit'}
        </div>
        <ul style="font-size:0.82rem; color:var(--text-2); padding-left:20px; line-height:1.6">
          <li><strong>settings_history.json:</strong> Starred favorites, recent tool IDs (max 12), and UI settings.</li>
          <li><strong>custom_presets.json:</strong> Any custom upload presets you created or edited.</li>
          <li><strong>Zero file contents:</strong> Your converted, compressed, and edited documents are never permanently stored in app data.</li>
        </ul>
      </div>
    </div>
  `;

  document.getElementById('settings-back-btn')?.addEventListener('click', (e) => {
    e.preventDefault();
    navigate('/');
  });

  document.getElementById('setting-pause-history')?.addEventListener('change', async (e) => {
    const paused = e.target.checked;
    await updateUserSettings({ history_paused: paused });
    _userSettings.history_paused = paused;
    toast('info', paused ? 'History Paused' : 'History Resumed', 'Recently used tools will not be recorded while paused.');
  });

  document.getElementById('btn-clear-history')?.addEventListener('click', async () => {
    await clearHistory();
    _userSettings.recent_tools = [];
    toast('success', 'Cleared', 'Tool history has been emptied.');
  });

  document.getElementById('setting-recent-files')?.addEventListener('change', async (e) => {
    const enabled = e.target.checked;
    await updateUserSettings({ recent_files_enabled: enabled });
    _userSettings.recent_files_enabled = enabled;
    toast('info', enabled ? 'Recent Files Enabled' : 'Recent Files Disabled', 'Stores only file names and sizes on disk.');
  });

  document.getElementById('btn-clear-recent-files')?.addEventListener('click', async () => {
    await clearRecentFiles();
    _userSettings.recent_files = [];
    toast('success', 'Cleared', 'Recent files list has been cleared.');
  });

  document.getElementById('btn-save-my-files-path')?.addEventListener('click', async () => {
    const val = document.getElementById('setting-my-files-path')?.value.trim();
    if (!val) return;
    const res = await updateUserSettings({ my_files_path: val });
    _userSettings.my_files_path = res.settings.my_files_path;
    toast('success', 'Folder Updated', `My Files root is now set to ${res.settings.my_files_path}`);
    await _renderSettingsPage();
  });

  document.getElementById('btn-open-appdata')?.addEventListener('click', async () => {
    try {
      await openAppDataFolder();
      toast('info', 'Opened', 'Opened app data folder in file manager.');
    } catch (err) {
      toast('error', 'Could not open', err.message);
    }
  });
}

// ── Tool page ─────────────────────────────────────────────────────
function _renderToolPage(tool, activePreset = null) {
  _destroyActivePreview();

  const unavailable = tool.requiresDep && _health && !_health.dependencies?.[tool.requiresDep];
  const view = document.getElementById('tool-view');

  const relevantPresets = _presets.filter(p => {
    if (tool.id === 'resize-image') return p.category === 'photo' || p.category === 'signature';
    if (tool.id === 'compress-pdf') return p.category === 'certificate' || p.format === 'pdf';
    if (tool.id === 'compress-image') return p.category === 'photo' || p.category === 'signature';
    return false;
  });

  const hasDualSlots = Boolean(tool && tool.dualSlots && typeof tool.dualSlots === 'object' && tool.dualSlots.slot1 && tool.dualSlots.slot2);

  view.innerHTML = `
    <!-- Top breadcrumb bar -->
    <div class="tool-topbar">
      <a href="#" class="btn-back" id="back-btn" aria-label="Back to all tools">
        <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" d="M19 12H5M12 5l-7 7 7 7"/></svg>
        ${t('all_tools', 'All Tools')}
      </a>
      <span class="tool-topbar__sep">/</span>
      <span class="tool-topbar__name">${tool.name}</span>
    </div>

    <!-- Two-column workspace -->
    <div class="tool-workspace">
      <!-- Left Column: Source & Visual Preview -->
      <div class="tool-workspace__source">
        <!-- Dependency warning if missing -->
        ${unavailable ? `
          <div class="dep-card dep-card--warning" role="alert">
            <span class="dep-card__icon">⚠️</span>
            <div class="dep-card__body">
              <strong>${tool.depName || 'External tool'} required</strong>
              <p>This conversion requires ${tool.depName}, which is not currently installed or in PATH.</p>
              ${tool.depInstallUrl ? `<a href="${tool.depInstallUrl}" target="_blank" rel="noopener" class="btn btn--sm btn--primary">Install ${tool.depName}</a>` : ''}
            </div>
          </div>
        ` : ''}

        ${hasDualSlots ? `
        <!-- Dual Upload Slots -->
        <div class="dual-slots-container" style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px;">
          <div class="dropzone dropzone--slot" id="dropzone-slot1" role="region" aria-label="${tool.dualSlots.slot1.label}" tabindex="0" style="padding:16px 12px;border:2px dashed var(--border-2);border-radius:var(--r-md);text-align:center;cursor:pointer;background:var(--card-bg);transition:all var(--dur-fast);">
            <input type="file" id="file-input-slot1" class="file-input" style="display:none;" accept="${tool.dualSlots.slot1.accept}" aria-label="Upload ${tool.dualSlots.slot1.label}">
            <div style="font-size:11px;font-weight:700;color:var(--primary);text-transform:uppercase;margin-bottom:4px;letter-spacing:0.5px;">Slot 1: ${tool.dualSlots.slot1.label}</div>
            <div class="dropzone__title" id="slot1-name" style="font-size:13px;font-weight:600;margin-bottom:2px;">Click or drop file</div>
            <div class="dropzone__hint" style="font-size:11px;color:var(--text-muted);">${tool.dualSlots.slot1.hint}</div>
          </div>
          <div class="dropzone dropzone--slot" id="dropzone-slot2" role="region" aria-label="${tool.dualSlots.slot2.label}" tabindex="0" style="padding:16px 12px;border:2px dashed var(--border-2);border-radius:var(--r-md);text-align:center;cursor:pointer;background:var(--card-bg);transition:all var(--dur-fast);">
            <input type="file" id="file-input-slot2" class="file-input" style="display:none;" accept="${tool.dualSlots.slot2.accept}" aria-label="Upload ${tool.dualSlots.slot2.label}">
            <div style="font-size:11px;font-weight:700;color:var(--primary);text-transform:uppercase;margin-bottom:4px;letter-spacing:0.5px;">Slot 2: ${tool.dualSlots.slot2.label}</div>
            <div class="dropzone__title" id="slot2-name" style="font-size:13px;font-weight:600;margin-bottom:2px;">Click or drop file</div>
            <div class="dropzone__hint" style="font-size:11px;color:var(--text-muted);">${tool.dualSlots.slot2.hint}</div>
          </div>
        </div>
        ` : `
        <!-- Dropzone -->
        <div class="dropzone dropzone--compact" id="dropzone" role="region" aria-label="File drop area" tabindex="0">
          <input type="file" id="file-input" class="file-input" style="display:none;"
            ${tool.multi ? 'multiple' : ''}
            accept="${tool.accept || '*/*'}"
            aria-label="Choose file"
          >
          <div class="dropzone__icon">${Icons.get(tool.icon || 'upload')}</div>
          <div class="dropzone__title">${tool.multi ? 'Drop files here or click to browse' : 'Drop a file here or click to browse'}</div>
          <div class="dropzone__hint">${tool.accept ? tool.accept.split(',').join(' · ') : 'Any supported file'} (up to 200 MB)</div>
        </div>
        ` }

        <!-- File queue list -->
        <div class="file-list" id="file-list" role="list"></div>

        <!-- Universal Interactive Preview Mount Point -->
        <div id="tool-preview-container" class="tool-preview-container"></div>
      </div>

      <!-- Right Column: Settings & Actions -->
      <div class="tool-workspace__controls">
        <!-- Preset Picker for Govt Forms -->
        ${relevantPresets.length > 0 ? `
          <div class="govt-preset-box">
            <label class="govt-preset-label">
              <span>🏛️ Exam / Portal Preset</span>
              <span class="govt-preset-badge">Approximate Guide</span>
            </label>
            <select class="select select--sm" id="preset-picker">
              <option value="">-- Choose portal preset (e.g. UPSC, SSC, IBPS) --</option>
              ${relevantPresets.map(p => `
                <option value="${p.id}" ${activePreset?.id === p.id ? 'selected' : ''}>
                  ${p.portal} — ${p.name} (${p.max_kb ? p.max_kb + ' KB' : 'standard'})
                </option>
              `).join('')}
            </select>
            <div class="preset-note-box" id="preset-note-box" style="margin-top:6px;"></div>
          </div>
        ` : ''}

        <!-- Options Panel -->
        <div class="options-panel" id="options-panel">
          ${_renderToolOptions(tool)}
        </div>

        <!-- Live Size Estimation Box -->
        <div class="estimate-box" id="estimate-box" style="display:none;">
          <div class="estimate-box__title">
            <span>⚡ Size Estimate</span>
            <span class="estimate-badge" id="estimate-badge">Calculating…</span>
          </div>
          <div class="estimate-box__text" id="estimate-text">
            Original: <strong>--</strong> → Expected: <strong>--</strong>
          </div>
        </div>

        <!-- Primary Action Section -->
        <div class="action-section" id="action-section">
          <button type="button" class="btn btn--primary btn--block" id="process-btn">
            ${tool.actionLabel || 'Process File'}
          </button>
        </div>

        <!-- Progress Indicator -->
        <div class="progress-wrap" id="progress-wrap" style="display:none;" role="status">
          <div class="progress-bar" role="progressbar" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100" id="progress-bar">
            <div class="progress-fill" id="progress-fill"></div>
          </div>
          <span class="progress-label" id="progress-label">Processing locally…</span>
        </div>

        <!-- Result Card -->
        <div class="result-panel" id="result-panel" role="region" aria-label="Result">
          <div class="result-panel__header">
            <div class="result-panel__icon">✓</div>
            <div>
              <div class="result-panel__title">Ready for download!</div>
              <div class="result-panel__stats" id="result-stats"></div>
            </div>
          </div>

          <!-- Phase 6: Editable Sanitized Filename Field -->
          <div class="filename-edit-wrap">
            <label for="result-filename-input" class="filename-edit-label">Output Filename:</label>
            <input type="text" id="result-filename-input" class="input input--sm filename-input" value="download" spellcheck="false">
          </div>

          <!-- Download and Local Storage Buttons -->
          <div class="result-actions-grid">
            <button type="button" class="btn btn--primary" id="download-btn">
              ${Icons.get('download')} Download
            </button>
            <button type="button" class="btn btn--secondary" id="save-myfiles-btn" title="Save directly to Documents/LocalToolkit/">
              📁 Save to My Files
            </button>
          </div>

          <div style="margin-top: 10px; text-align: center;">
            <button type="button" class="btn-text" id="again-btn">Convert another file</button>
          </div>
        </div>

        <!-- Error Card -->
        <div class="error-panel" id="error-panel" role="alert">
          <div class="error-panel__icon">✕</div>
          <div class="error-panel__body">
            <div class="error-panel__title">Processing Failed</div>
            <div class="error-panel__msg" id="error-msg"></div>
          </div>
        </div>
      </div>
    </div>
  `;

  // Wire back button
  document.getElementById('back-btn').addEventListener('click', (e) => {
    e.preventDefault();
    navigate('/');
  });

  const dropzone      = document.getElementById('dropzone');
  const fileInput     = document.getElementById('file-input');
  const fileList      = document.getElementById('file-list');
  const optionsView   = document.getElementById('options-panel');
  const actionSection = document.getElementById('action-section');
  const processBtn    = document.getElementById('process-btn');
  const progressWrap  = document.getElementById('progress-wrap');
  const progressBar   = document.getElementById('progress-bar');
  const progressFill  = document.getElementById('progress-fill');
  const progressLabel = document.getElementById('progress-label');
  const resultPanel   = document.getElementById('result-panel');
  const resultStats   = document.getElementById('result-stats');
  const downloadBtn   = document.getElementById('download-btn');
  const saveMyFilesBtn= document.getElementById('save-myfiles-btn');
  const filenameInput = document.getElementById('result-filename-input');
  const againBtn      = document.getElementById('again-btn');
  const errorPanel    = document.getElementById('error-panel');
  const errorMsg      = document.getElementById('error-msg');
  const presetPicker  = document.getElementById('preset-picker');
  const presetNoteBox = document.getElementById('preset-note-box');
  const estimateBox   = document.getElementById('estimate-box');
  const estimateText  = document.getElementById('estimate-text');
  const estimateBadge = document.getElementById('estimate-badge');

  let _resultBlob = null;
  let _resultFilename = 'download';

  // Instantiate Preview Component with lifecycle
  const previewContainer = document.getElementById('tool-preview-container');
  _activeToolPreview = previewContainer ? new ToolPreview(previewContainer, {
    onStateChange: () => {},
  }) : null;
  if (_activeToolPreview) {
    _activeToolPreview.mount(previewContainer);
  }
  const toolPreview = _activeToolPreview;

  function _getFormOptions() {
    const opts = {};
    if (optionsView) {
      optionsView.querySelectorAll('input, select').forEach(el => {
        if (!el.name) return;
        const val = el.value !== undefined ? String(el.value).trim() : '';
        if (el.type === 'number') {
          // Never send "" for numeric fields: only send if valid number
          if (val !== '' && !isNaN(Number(val))) {
            opts[el.name] = val;
          }
        } else if (val !== '') {
          opts[el.name] = val;
        }
      });
    }
    return opts;
  }

  // Handle Preset Selection (Always marked approximate)
  function _applyPreset(p) {
    if (!p) return;
    if (presetNoteBox) {
      const verifiedStr = p.verified_on ? ` · Verified ${p.verified_on}` : '';
      const sourceStr = p.source_note ? `<br><small style="opacity:0.85">Source: ${p.source_note}</small>` : '';
      presetNoteBox.innerHTML = `
        <div style="font-size:0.82rem; line-height:1.4;">
          <span class="badge badge--yellow" style="font-size:0.7rem; font-weight:700; margin-bottom:4px; display:inline-block;">Approximate — check portal's latest notice</span>
          <div><strong>${p.portal} (${p.name}):</strong> ${p.note || ''} (Target: ${p.max_kb ? p.max_kb + ' KB' : 'standard'}${verifiedStr})</div>
          ${sourceStr}
        </div>
      `;
    }
    if (tool.id === 'resize-image') {
      const wEl = document.getElementById('opt-width');
      const hEl = document.getElementById('opt-height');
      const uEl = document.getElementById('opt-unit');
      const dEl = document.getElementById('opt-dpi');
      if (wEl) wEl.value = p.width;
      if (hEl) hEl.value = p.height;
      if (uEl) uEl.value = p.unit;
      if (dEl) dEl.value = p.dpi;
    } else if (tool.id === 'compress-image' || tool.id === 'compress-pdf') {
      const tkbEl = document.getElementById('opt-target_kb');
      if (tkbEl) tkbEl.value = p.max_kb;
    }
    toolPreview && toolPreview.update(tool, _files, _getFormOptions());
    _triggerEstimate();
  }

  if (activePreset) {
    _applyPreset(activePreset);
  }

  presetPicker?.addEventListener('change', () => {
    const selId = presetPicker.value;
    const p = _presets.find(x => x.id === selId);
    _applyPreset(p);
  });

  // Debounced Size Estimation
  let _estimateTimer = null;
  function _triggerEstimate() {
    if (_files.length === 0) {
      if (estimateBox) estimateBox.style.display = 'none';
      return;
    }
    if (tool.id !== 'compress-image' && tool.id !== 'compress-pdf') return;

    if (_estimateTimer) clearTimeout(_estimateTimer);
    _estimateTimer = setTimeout(async () => {
      try {
        const targetKbEl = document.getElementById('opt-target_kb');
        const targetKb = targetKbEl ? targetKbEl.value : '50';
        const fd = new FormData();
        fd.append('file', _files[0]);
        fd.append('target_kb', targetKb);

        const endpoint = tool.id === 'compress-image' ? '/api/image/estimate-size' : '/api/pdf/estimate-size';
        const res = await fetch(endpoint, { method: 'POST', body: fd });
        if (res.ok) {
          const data = await res.json();
          estimateBox.style.display = 'block';
          const origKb = Math.round(data.original_bytes / 1024);
          const estKb = Math.round(data.estimated_bytes / 1024);
          estimateText.innerHTML = `Original: <strong>${origKb} KB</strong> → Estimated: <strong>${estKb} KB</strong> (Target: ${targetKb} KB)`;
          if (data.reachable) {
            estimateBadge.textContent = '✓ Reachable';
            estimateBadge.className = 'estimate-badge estimate-badge--ok';
          } else {
            estimateBadge.textContent = '⚠️ Tight limit';
            estimateBadge.className = 'estimate-badge estimate-badge--warn';
          }
        }
      } catch {}
    }, 350);
  }

  optionsView?.addEventListener('input', (e) => {
    if (e.target && (e.target.name === 'pages' || e.target.name === 'ranges')) {
      toolPreview && toolPreview.syncFromInput && toolPreview.syncFromInput(tool.id, e.target.value);
    } else {
      toolPreview && toolPreview.update(tool, _files, _getFormOptions());
    }
    _triggerEstimate();
  });

  let _slot1File = null;
  let _slot2File = null;

  if (hasDualSlots) {
    const dz1 = document.getElementById('dropzone-slot1');
    const in1 = document.getElementById('file-input-slot1');
    const name1 = document.getElementById('slot1-name');
    const dz2 = document.getElementById('dropzone-slot2');
    const in2 = document.getElementById('file-input-slot2');
    const name2 = document.getElementById('slot2-name');

    const bindSlot = (dz, input, nameEl, isSlot1) => {
      if (!dz || !input) return;
      dz.addEventListener('click', (e) => {
        if (e.target !== input) input.click();
      });
      input.addEventListener('click', (e) => e.stopPropagation());
      dz.addEventListener('dragover', (e) => {
        e.preventDefault();
        dz.classList.add('dropzone--over');
      });
      dz.addEventListener('dragleave', () => dz.classList.remove('dropzone--over'));
      dz.addEventListener('drop', (e) => {
        e.preventDefault();
        dz.classList.remove('dropzone--over');
        if (e.dataTransfer.files?.length) setFile(e.dataTransfer.files[0]);
      });
      input.addEventListener('change', () => {
        if (input.files?.length) {
          setFile(input.files[0]);
          input.value = '';
        }
      });
      const setFile = (f) => {
        if (isSlot1) {
          _slot1File = f;
        } else {
          _slot2File = f;
        }
        if (nameEl) nameEl.textContent = '✓ ' + f.name;
        dz.style.borderColor = 'var(--accent, #10B981)';
        dz.style.background = 'rgba(16, 185, 129, 0.08)';
        _files = [_slot1File, _slot2File].filter(Boolean);
        toolPreview && toolPreview.update(tool, _files, _getFormOptions());
        _triggerEstimate();
      };
    };

    bindSlot(dz1, in1, name1, true);
    bindSlot(dz2, in2, name2, false);
  }

  // Drag & drop handlers
  if (dropzone && fileInput) {
    dropzone.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropzone.classList.add('dropzone--over');
    });
    dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dropzone--over'));
    dropzone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropzone.classList.remove('dropzone--over');
      if (e.dataTransfer.files?.length) {
        _addFiles(Array.from(e.dataTransfer.files));
      }
    });

    dropzone.addEventListener('click', (e) => {
      if (e.target !== fileInput) {
        fileInput.click();
      }
    });
    fileInput.addEventListener('click', (e) => {
      e.stopPropagation();
    });
    dropzone.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        fileInput.click();
      }
    });

    fileInput.addEventListener('change', () => {
      if (fileInput.files?.length) {
        _addFiles(Array.from(fileInput.files));
        fileInput.value = '';
      }
    });
  }

  function _addFiles(incoming) {
    if (tool.multi) {
      _files.push(...incoming);
    } else {
      _files = [incoming[0]];
    }
    _renderFileList();
    _updateDropzoneState();
    toolPreview && toolPreview.update(tool, _files, _getFormOptions());
    _triggerEstimate();
  }

  function _renderFileList() {
    fileList.innerHTML = '';
    _files.forEach((file, index) => {
      const item = createFileItem(file, index, _removeFile, _files.length > 1);
      fileList.appendChild(item);
    });

    if (tool.multi && _files.length > 1) {
      makeDraggable(fileList, _onReorder);
    }
  }

  function _updateDropzoneState() {
    if (!dropzone) return;
    if (_files.length > 0 && !tool.multi) {
      dropzone.classList.add('dropzone--has-file');
    } else {
      dropzone.classList.remove('dropzone--has-file');
    }
  }

  function _removeFile(index) {
    _files.splice(index, 1);
    _renderFileList();
    _updateDropzoneState();
    toolPreview && toolPreview.update(tool, _files, _getFormOptions());
    _triggerEstimate();
  }

  function _onReorder(newOrder) {
    _files = newOrder.map(i => _files[i]);
    if (toolPreview) toolPreview.update(tool, _files, _getFormOptions());
  }

  function _sanitizeName(val) {
    return val.replace(/\s+/g, '_').replace(/[^\w.-]/g, '');
  }

  filenameInput?.addEventListener('input', () => {
    const raw = filenameInput.value;
    const sanitized = _sanitizeName(raw);
    if (raw !== sanitized) filenameInput.value = sanitized;
    _resultFilename = sanitized || 'download';
  });

  // Action Button / Processing
  processBtn.addEventListener('click', _process);

  async function _process() {
    if (_files.length === 0) {
      toast('info', 'No files selected', 'Please add a file first.');
      return;
    }

    const formData = new FormData();
    if (hasDualSlots) {
      if (!_slot1File || !_slot2File) {
        toast('info', 'Both files required', `Please upload both ${tool.dualSlots.slot1.label} and ${tool.dualSlots.slot2.label}.`);
        return;
      }
      formData.append(tool.dualSlots.slot1.key, _slot1File);
      formData.append(tool.dualSlots.slot2.key, _slot2File);
      formData.append('files', _slot1File);
      formData.append('files', _slot2File);
    } else if (tool.multi) {
      _files.forEach(f => formData.append('files', f));
    } else {
      formData.append('file', _files[0]);
    }

    // Include cropper coords if live crop was used
    if (toolPreview && toolPreview.getCropParams) {
      const crop = toolPreview.getCropParams();
      if (crop && crop.w > 0 && crop.h > 0) {
        formData.append('crop_x', crop.x);
        formData.append('crop_y', crop.y);
        formData.append('crop_w', crop.w);
        formData.append('crop_h', crop.h);
      }
    }

    // Append options
    const opts = _getFormOptions();
    for (const [k, v] of Object.entries(opts)) {
      formData.append(k, v);
    }

    // For rotate-pdf, include visualizer per-page rotations
    if (tool.id === 'rotate-pdf' && toolPreview && toolPreview.getPageRotations) {
      const pageRots = toolPreview.getPageRotations();
      if (pageRots && Object.keys(pageRots).length > 0) {
        formData.set('page_rotations', JSON.stringify(pageRots));
      }
    }

    // For remove-pages and extract-pages, ensure exact input value is sent
    if (tool.id === 'remove-pages' || tool.id === 'extract-pages') {
      const pInput = document.querySelector('input[name="pages"]');
      if (pInput) {
        formData.set('pages', pInput.value.trim());
      }
    }

    processBtn.setAttribute('disabled', 'true');
    progressWrap.style.display = '';
    errorPanel.classList.remove('active');
    const originalSize = _files.reduce((s, f) => s + f.size, 0);

    try {
      const result = await submitTool(tool.endpoint, formData, (pct) => {
        if (progressFill) progressFill.style.width = pct + '%';
        if (progressBar) progressBar.setAttribute('aria-valuenow', pct);
        if (progressLabel) progressLabel.textContent = pct < 60 ? 'Uploading…' : 'Processing locally…';
      });

      _resultBlob = result.blob;

      // Clean auto-generated default filename (e.g. photo_45KB.jpg)
      const baseStem = _files[0]?.name?.split('.')[0] || 'file';
      const sizeTag = Math.round(result.resultSize / 1024) + 'KB';
      const ext = result.filename ? result.filename.split('.').pop() : (tool.outputName ? tool.outputName.split('.').pop() : 'pdf');
      const defaultName = _sanitizeName(`${baseStem}_${sizeTag}.${ext}`);

      _resultFilename = defaultName;
      if (filenameInput) filenameInput.value = defaultName;

      // If recent files is enabled, record file name and size
      if (_userSettings.recent_files_enabled) {
        recordRecentFile(defaultName, result.resultSize);
      }

      // Switch right panel to result view
      progressWrap.style.display = 'none';
      optionsView.style.display = 'none';
      actionSection.style.display = 'none';
      resultPanel.classList.add('active');

      if (result.compressionReport) {
        const cr = result.compressionReport;
        const reachedBadge = cr.reached
          ? `<span style="background:var(--success-bg,#D1FAE5);color:var(--success-text,#065F46);font-size:11px;font-weight:700;padding:2px 8px;border-radius:12px;margin-left:8px;">Target Met</span>`
          : (cr.target_size > 0 ? `<span style="background:var(--warn-bg,#FEF3C7);color:var(--warn-text,#92400E);font-size:11px;font-weight:700;padding:2px 8px;border-radius:12px;margin-left:8px;">Closest: ${fmtSize(cr.closest_reached)}</span>` : '');

        let stepsHtml = '';
        if (cr.steps_saved) {
          const s1 = cr.steps_saved.lossless_cleanup || 0;
          const s2 = cr.steps_saved.image_compression || 0;
          const s3 = cr.steps_saved.rasterization || 0;
          stepsHtml = `
            <div style="font-size:12px;color:var(--text-muted);margin-top:6px;line-height:1.5;">
              <div>• Lossless cleanup saved: <strong>${fmtSize(s1)}</strong></div>
              <div>• Image downsampling saved: <strong>${fmtSize(s2)}</strong></div>
              ${s3 > 0 ? `<div>• Rasterization saved: <strong>${fmtSize(s3)}</strong></div>` : ''}
            </div>
          `;
        }

        let breakdownHtml = '';
        if (cr.breakdown) {
          breakdownHtml = `
            <div style="font-size:11px;color:var(--text-muted);margin-top:4px;">
              Document breakdown: Images ${fmtSize(cr.breakdown.images || 0)} · Fonts ${fmtSize(cr.breakdown.fonts || 0)} · Other ${fmtSize(cr.breakdown.other || 0)}
            </div>
          `;
        }

        let retryRasterizeBtn = '';
        if (!cr.reached && cr.rasterize_needed) {
          retryRasterizeBtn = `
            <div style="margin-top:10px;padding:8px 12px;background:var(--card-bg);border:1px solid var(--border-1);border-radius:var(--r-sm);">
              <div style="font-size:12px;font-weight:600;margin-bottom:4px;color:var(--text);">Target size not reached via image downsampling.</div>
              <button type="button" class="btn btn--sm btn--secondary" id="retry-rasterize-btn" style="width:100%;">
                Retry with Page Rasterization
              </button>
            </div>
          `;
        }

        const saved = Math.max(0, originalSize - result.resultSize);
        const pct = Math.round((saved / originalSize) * 100);

        resultStats.innerHTML = `
          <div style="margin-bottom:4px;">
            <strong>${fmtSize(originalSize)} → ${fmtSize(result.resultSize)}</strong> (Saved ${pct}%)
            ${reachedBadge}
          </div>
          ${breakdownHtml}
          ${stepsHtml}
          ${retryRasterizeBtn}
        `;

        const retryBtn = document.getElementById('retry-rasterize-btn');
        if (retryBtn) {
          retryBtn.addEventListener('click', () => {
            const cb = document.querySelector('input[name="allow_rasterize"]');
            if (cb) cb.checked = true;
            _process();
          });
        }
      } else if (tool.showSizeDiff && originalSize > 0) {
        const saved = Math.max(0, originalSize - result.resultSize);
        const pct = Math.round((saved / originalSize) * 100);
        resultStats.innerHTML = pct > 0
          ? `<strong>Saved ${pct}%</strong> (${fmtSize(originalSize)} → ${fmtSize(result.resultSize)})`
          : `Output size: ${fmtSize(result.resultSize)}`;
      } else {
        resultStats.textContent = `Output size: ${fmtSize(result.resultSize)}`;
      }

      if (toolPreview) {
        toolPreview.update(tool, _files, _getFormOptions(), result.blob);
      }

      announce(`Done! ${tool.name} complete. Ready to download.`);
      toast('success', 'Done!', `${tool.name} completed successfully.`);
    } catch (err) {
      progressWrap.style.display = 'none';
      processBtn.removeAttribute('disabled');
      errorPanel.classList.add('active');
      errorMsg.textContent = err.message || 'An error occurred. Please try again.';
      announce(`Error: ${err.message}`);
      toast('error', 'Request Failed', err.message || 'An error occurred. Please try again.');
    }
  }

  downloadBtn.addEventListener('click', () => {
    if (_resultBlob) downloadBlob(_resultBlob, _resultFilename);
  });

  saveMyFilesBtn.addEventListener('click', async () => {
    if (!_resultBlob) return;
    try {
      saveMyFilesBtn.setAttribute('disabled', 'true');
      const res = await saveToMyFiles(_resultBlob, _resultFilename);
      saveMyFilesBtn.removeAttribute('disabled');
      toast('success', 'Saved!', `Stored in My Files → "${res.folder}" folder.`);
    } catch (err) {
      saveMyFilesBtn.removeAttribute('disabled');
      toast('error', 'Save failed', err.message);
    }
  });

  againBtn.addEventListener('click', () => {
    if (toolPreview) toolPreview.reset();
    _files = [];
    _resultBlob = null;
    if (hasDualSlots) {
      _slot1File = null;
      _slot2File = null;
      const n1 = document.getElementById('slot1-name');
      const dz1 = document.getElementById('dropzone-slot1');
      const n2 = document.getElementById('slot2-name');
      const dz2 = document.getElementById('dropzone-slot2');
      if (n1) n1.textContent = 'Click or drop file';
      if (dz1) { dz1.style.borderColor = ''; dz1.style.background = ''; }
      if (n2) n2.textContent = 'Click or drop file';
      if (dz2) { dz2.style.borderColor = ''; dz2.style.background = ''; }
    }
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

// ── Render tool specific options ──────────────────────────────────
function _renderToolOptions(tool) {
  if (!tool.options || tool.options.length === 0) return '';
  return tool.options.map(opt => {
    if (opt.type === 'number') {
      return `
        <div class="option-group">
          <label for="opt-${opt.key}">${opt.label}</label>
          <input type="number" id="opt-${opt.key}" name="${opt.key}" class="input input--sm"
                 value="${opt.default ?? ''}" min="${opt.min ?? ''}" max="${opt.max ?? ''}" step="${opt.step ?? '1'}">
          ${opt.hint ? `<span class="option-hint">${opt.hint}</span>` : ''}
        </div>
      `;
    }
    if (opt.type === 'select') {
      return `
        <div class="option-group">
          <label for="opt-${opt.key}">${opt.label}</label>
          <select id="opt-${opt.key}" name="${opt.key}" class="select select--sm">
            ${opt.choices.map(c => `
              <option value="${c.value}" ${c.value === opt.default ? 'selected' : ''}>${c.label}</option>
            `).join('')}
          </select>
          ${opt.hint ? `<span class="option-hint">${opt.hint}</span>` : ''}
        </div>
      `;
    }
    if (opt.type === 'range') {
      return `
        <div class="option-group">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <label for="opt-${opt.key}">${opt.label}</label>
            <span class="range-val" id="val-${opt.key}">${opt.format ? opt.format(opt.default) : opt.default}</span>
          </div>
          <input type="range" id="opt-${opt.key}" name="${opt.key}" class="range-slider"
                 value="${opt.default}" min="${opt.min}" max="${opt.max}" step="${opt.step || 1}"
                 oninput="document.getElementById('val-${opt.key}').textContent = ${opt.format ? `(${opt.format.toString()})(this.value)` : 'this.value'}">
        </div>
      `;
    }
    if (opt.type === 'text') {
      return `
        <div class="option-group">
          <label for="opt-${opt.key}">${opt.label}</label>
          <input type="text" id="opt-${opt.key}" name="${opt.key}" class="input input--sm"
                 placeholder="${opt.placeholder || ''}" value="${opt.default || ''}">
          ${opt.hint ? `<span class="option-hint">${opt.hint}</span>` : ''}
        </div>
      `;
    }
    return '';
  }).join('');
}

// ── Info pages ────────────────────────────────────────────────────
function _showInfoPage(page) {
  _destroyActivePreview();
  document.getElementById('home-view').style.display = 'none';
  document.getElementById('my-files-view').style.display = 'none';
  document.getElementById('settings-view').style.display = 'none';
  const view = document.getElementById('tool-view');
  view.style.display = 'block';

  const content = {
    privacy: `
      <div class="info-page">
        <h1>Privacy Policy</h1>
        <div class="badge badge--green" style="margin-bottom:24px">${Icons.get('lock')} 100% Local — No data leaves your device</div>
        
        <h2>LocalToolkit Privacy Guarantee</h2>
        <p>LocalToolkit never uploads your files. Everything runs on your computer. A few tools need free helper programs (LibreOffice, Ghostscript, Tesseract). History stays on your device; pause or clear it anytime.</p>
        
        <h2>How to Verify (Zero Outbound Requests)</h2>
        <ol style="padding-left: 20px; line-height: 1.6; margin-bottom: 24px;">
          <li><strong>Turn off Wi-Fi or unplug your network cable:</strong> Open LocalToolkit and test any conversion, crop, or compression tool. Everything works with zero internet connection.</li>
          <li><strong>Check browser Network tab:</strong> Press <code>F12</code> or right-click → <em>Inspect</em>, click the <em>Network</em> tab, and process any file. You will see every call goes strictly to <code>http://127.0.0.1</code> with zero third-party requests.</li>
          <li><strong>Zero Tracking:</strong> No telemetry, analytics, cookies, or remote scripts exist in LocalToolkit.</li>
        </ol>

        <h2>My Files Local Storage</h2>
        <p>When you click "Save to My Files", the file is saved exclusively in your computer's local directory (default: <code>LocalToolkit/</code> in your user home folder). You can change this path in Settings anytime.</p>
      </div>
    `,
    about: `
      <div class="info-page">
        <h1>About LocalToolkit</h1>
        <p>LocalToolkit is an offline, privacy-first Swiss Army knife for files, tuned for government exam uploads and everyday conversions.</p>
      </div>
    `,
  };

  view.innerHTML = `
    <div class="tool-topbar">
      <a href="#" class="btn-back">
        <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" d="M19 12H5M12 5l-7 7 7 7"/></svg>
        All Tools
      </a>
    </div>
    ${content[page] || ''}
  `;

  view.querySelector('.btn-back').onclick = (e) => {
    e.preventDefault();
    navigate('/');
  };
}
