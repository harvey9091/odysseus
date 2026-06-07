/**
 * LeadHunter workspace panel — exact Deep Research architecture clone.
 *
 * Window structure (identical to Deep Research):
 *   #leadhunter-overlay  (className: "modal leadhunter-overlay")
 *   └── #leadhunter-pane  (className: "modal-content doclib-modal-content leadhunter-pane")
 *       ├── .modal-header.leadhunter-pane-header
 *       │   ├── h4 "[icon] LeadHunter"
 *       │   └── .leadhunter-pane-header-actions
 *       │       ├── #leadhunter-panel-minimize (.modal-minimize-btn)
 *       │       └── #leadhunter-panel-close (.close-btn)
 *       └── .modal-body.leadhunter-pane-body
 *           └── [tabbed content]
 */

import themeModule from './theme.js';
import spinnerModule from './spinner.js';

let _open = false;
let _onDocKeydown = null;
let _apiBase = '';
const API_BASE = window.location.origin;

// ── Settings persistence ──────────────────────────────────────────
const _SETTINGS_KEY = 'leadhunter-settings';
const _COLLAPSE_KEY = 'leadhunter-settings-collapsed';
let _settingsCollapsed = false;
try { _settingsCollapsed = localStorage.getItem(_COLLAPSE_KEY) === '1'; } catch {}

function _saveSettingsToStorage() {
  try {
    const activeTab = document.querySelector('.leadhunter-tab.active');
    localStorage.setItem(_SETTINGS_KEY, JSON.stringify({
      tab: activeTab?.dataset.tab || 'dashboard',
    }));
  } catch {}
}

function _loadSettingsFromStorage() {
  try {
    const raw = localStorage.getItem(_SETTINGS_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
}

// ── Icons ─────────────────────────────────────────────────────────
const _closeIcon = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>';
const _minimizeIcon = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="5" y1="18" x2="19" y2="18"/></svg>';
const _refreshIcon = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 11-2.12-9.36L23 10"/></svg>';
const _chevronIcon = '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>';

// ── State ─────────────────────────────────────────────────────────
let _activeTab = 'dashboard';
let _leads = [];
let _campaigns = [];
let _listmonkStatus = null;
let _stats = { total_leads: 0, qualified_leads: 0, synced_leads: 0, campaign_count: 0, last_sync: '' };

// ── Lifecycle ─────────────────────────────────────────────────────

export function toggle() {
  if (_open) {
    const overlay = document.getElementById('leadhunter-overlay');
    if (overlay && overlay.style.display === 'none') {
      overlay.style.display = '';
      const btn = document.getElementById('tool-leadhunter-btn');
      if (btn) btn.classList.remove('minimized');
      return;
    }
    closePanel();
  } else {
    openPanel();
  }
}

export function openPanel() {
  if (_open) {
    const overlay = document.getElementById('leadhunter-overlay');
    if (overlay && overlay.style.display === 'none') {
      overlay.style.display = '';
      const btn = document.getElementById('tool-leadhunter-btn');
      if (btn) btn.classList.remove('minimized');
    }
    return;
  }

  _open = true;
  const btn = document.getElementById('tool-leadhunter-btn');
  if (btn) btn.classList.add('active');

  // Exact Deep Research pattern:
  // 1. Create overlay (className: "modal leadhunter-overlay")
  console.error('LEADHUNTER RENDERER ACTIVE', new Date().toISOString());
  const overlay = document.createElement('div');
  overlay.id = 'leadhunter-overlay';
  overlay.className = 'modal leadhunter-overlay';

  // 2. Create pane (className: "modal-content doclib-modal-content leadhunter-pane")
  const pane = document.createElement('div');
  pane.id = 'leadhunter-pane';
  pane.className = 'modal-content doclib-modal-content leadhunter-pane';
  // Match Deep Research sizing exactly
  pane.style.cssText = (window.innerWidth <= 768)
    ? 'width:100vw;max-width:100vw;height:90dvh;max-height:90dvh;border-radius:14px 14px 0 0;background:var(--bg);'
    : 'width:min(640px, 92vw);max-height:85vh;background:var(--bg);';
  pane.innerHTML = _buildPanelHTML();

  // 3. Append pane to overlay, overlay to body
  overlay.appendChild(pane);
  document.body.appendChild(overlay);

  // 4. Backdrop click → close (identical to Deep Research)
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) closePanel();
  });

  // 5. Document-level ESC handler (identical to Deep Research)
  _onDocKeydown = (e) => {
    if (e.key === 'Escape' && _open) {
      e.preventDefault();
      closePanel();
    }
  };
  document.addEventListener('keydown', _onDocKeydown);

  // 6. Make draggable by header — exact Deep Research pattern
  const paneHeader = pane.querySelector('.leadhunter-pane-header');
  if (themeModule && themeModule.makeDraggable && paneHeader) {
    themeModule.makeDraggable(pane, paneHeader);
  }

  // 7. Wire events
  _wireEvents(pane);

  // 8. Load live data
  _loadAllData();

  // 9. Restore last tab
  _restoreTab();
}

export function closePanel() {
  if (!_open) return;
  _open = false;

  if (_onDocKeydown) {
    document.removeEventListener('keydown', _onDocKeydown);
    _onDocKeydown = null;
  }

  const btn = document.getElementById('tool-leadhunter-btn');
  if (btn) btn.classList.remove('active');

  const overlay = document.getElementById('leadhunter-overlay');
  if (overlay) overlay.remove();
}

// ── Panel HTML ────────────────────────────────────────────────────

function _buildPanelHTML() {
  const settingsHidden = _settingsCollapsed ? ' style="display:none"' : '';
  const chevronCls = _settingsCollapsed ? ' collapsed' : '';

  return `
    <div class="modal-header leadhunter-pane-header">
      <h4>
        <span style="position:relative;top:-1px;left:6px;display:inline-flex;vertical-align:middle;">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
            <circle cx="9" cy="7" r="4"/>
            <line x1="22" y1="21" x2="22" y2="21"/>
            <line x1="19" y1="18" x2="25" y2="18"/>
            <line x1="19" y1="24" x2="25" y2="24"/>
          </svg>
        </span>
        <span style="margin-left:6px;">LeadHunter</span>
      </h4>
      <div class="leadhunter-pane-header-actions">
        <button id="leadhunter-panel-refresh" class="modal-minimize-btn" type="button" title="Refresh" style="margin-right:4px;">${_refreshIcon}</button>
        <button id="leadhunter-panel-minimize" class="modal-minimize-btn" type="button" title="Minimize">${_minimizeIcon}</button>
        <button id="leadhunter-panel-close" class="close-btn" title="Close">&#x2716;</button>
      </div>
    </div>
    <div class="modal-body leadhunter-pane-body" data-no-swipe-dismiss>
      <div class="leadhunter-tabs" role="tablist">
        <button class="leadhunter-tab active" data-tab="dashboard" role="tab" aria-selected="true">Dashboard</button>
        <button class="leadhunter-tab" data-tab="leads" role="tab" aria-selected="false">Leads</button>
        <button class="leadhunter-tab" data-tab="campaigns" role="tab" aria-selected="false">Campaigns</button>
        <button class="leadhunter-tab" data-tab="listmonk" role="tab" aria-selected="false">Listmonk</button>
        <button class="leadhunter-tab" data-tab="settings" role="tab" aria-selected="false">Settings</button>
      </div>
      <div class="leadhunter-tab-panel active" data-panel="dashboard">
        <div id="leadhunter-dashboard-content">
          <div class="modal-spinner">Loading...</div>
        </div>
      </div>
      <div class="leadhunter-tab-panel hidden" data-panel="leads">
        <div id="leadhunter-leads-content">
          <div class="modal-spinner">Loading...</div>
        </div>
      </div>
      <div class="leadhunter-tab-panel hidden" data-panel="campaigns">
        <div id="leadhunter-campaigns-content">
          <div class="modal-spinner">Loading...</div>
        </div>
      </div>
      <div class="leadhunter-tab-panel hidden" data-panel="listmonk">
        <div id="leadhunter-listmonk-content">
          <div class="modal-spinner">Loading...</div>
        </div>
      </div>
      <div class="leadhunter-tab-panel hidden" data-panel="settings">
        <div id="leadhunter-settings-content"></div>
      </div>
    </div>
  `;
}

// ── Event wiring ──────────────────────────────────────────────────

function _wireEvents(pane) {
  // Close
  pane.querySelector('#leadhunter-panel-close').addEventListener('click', closePanel);

  // Minimize
  pane.querySelector('#leadhunter-panel-minimize').addEventListener('click', () => {
    const overlay = document.getElementById('leadhunter-overlay');
    if (overlay) overlay.style.display = 'none';
    const btn = document.getElementById('tool-leadhunter-btn');
    if (btn) btn.classList.add('minimized');
  });

  // Refresh
  pane.querySelector('#leadhunter-panel-refresh')?.addEventListener('click', () => {
    _loadAllData();
  });

  // Tabs
  pane.querySelectorAll('.leadhunter-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      _switchTab(tab.dataset.tab);
      _saveSettingsToStorage();
    });
  });

  // Settings toggle
  pane.querySelector('#leadhunter-settings-toggle')?.addEventListener('click', () => {
    const body = document.getElementById('leadhunter-settings-body');
    const btn = pane.querySelector('#leadhunter-settings-toggle');
    if (!body || !btn) return;
    _settingsCollapsed = !_settingsCollapsed;
    body.style.display = _settingsCollapsed ? 'none' : '';
    btn.classList.toggle('collapsed', _settingsCollapsed);
    try { localStorage.setItem(_COLLAPSE_KEY, _settingsCollapsed ? '1' : '0'); } catch {}
  });
}

function _switchTab(tabName) {
  _activeTab = tabName;
  const pane = document.getElementById('leadhunter-pane');
  if (!pane) return;

  // Update tab buttons
  pane.querySelectorAll('.leadhunter-tab').forEach(t => {
    const isActive = t.dataset.tab === tabName;
    t.classList.toggle('active', isActive);
    t.setAttribute('aria-selected', isActive ? 'true' : 'false');
  });

  // Update tab panels
  pane.querySelectorAll('.leadhunter-tab-panel').forEach(p => {
    p.classList.toggle('hidden', p.dataset.panel !== tabName);
    p.classList.toggle('active', p.dataset.panel === tabName);
  });

  // Load data for the tab
  _loadTabData(tabName);
}

function _restoreTab() {
  const saved = _loadSettingsFromStorage();
  const tab = saved?.tab || 'dashboard';
  _switchTab(tab);
}

// ── Data loading ──────────────────────────────────────────────────

async function _loadAllData() {
  await Promise.all([
    _loadStats(),
    _loadLeads(),
    _loadCampaigns(),
    _loadListmonkStatus(),
  ]);
}

async function _loadStats() {
  try {
    const [statsRes, metricsRes] = await Promise.all([
      fetch(`${API_BASE}/api/leadhunter/stats`, { credentials: 'same-origin' }),
      fetch(`${API_BASE}/api/leadhunter/metrics`, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      })
    ]);
    const stats = statsRes.ok ? await statsRes.json() : {};
    const metrics = metricsRes.ok ? await metricsRes.json() : {};
    _stats = {
      total_leads: stats.total_leads || 0,
      qualified_leads: stats.qualified_leads || 0,
      synced_leads: stats.synced_leads || 0,
      campaign_count: stats.campaigns || 0,
      last_sync: stats.last_sync || 'Never',
    };
    _renderDashboard();
  } catch (e) {
    console.error('LeadHunter: failed to fetch stats', e);
  }
}

async function _loadLeads() {
  try {
    const res = await fetch(`${API_BASE}/api/leadhunter/leads?limit=50`, { credentials: 'same-origin' });
    const data = await res.json();
    _leads = data.leads || [];
    _renderLeads();
  } catch (e) {
    console.error('LeadHunter: failed to fetch leads', e);
  }
}

async function _loadCampaigns() {
  try {
    const res = await fetch(`${API_BASE}/api/leadhunter/campaigns`, { credentials: 'same-origin' });
    const data = await res.json();
    _campaigns = data.campaigns || [];
    _renderCampaigns();
  } catch (e) {
    console.error('LeadHunter: failed to fetch campaigns', e);
  }
}

async function _loadListmonkStatus() {
  try {
    const res = await fetch(`${API_BASE}/api/leadhunter/health`, { credentials: 'same-origin' });
    const data = await res.json();
    _listmonkStatus = data;
    _renderListmonk();
  } catch (e) {
    console.error('LeadHunter: failed to fetch listmonk status', e);
  }
}

function _loadTabData(tab) {
  switch (tab) {
    case 'dashboard': _loadStats(); break;
    case 'leads': _loadLeads(); break;
    case 'campaigns': _loadCampaigns(); break;
    case 'listmonk': _loadListmonkStatus(); break;
    case 'settings': _renderSettings(); break;
  }
}

// ── Rendering ─────────────────────────────────────────────────────

function _renderDashboard() {
  const el = document.getElementById('leadhunter-dashboard-content');
  if (!el) return;

  const statusColor = _listmonkStatus?.listmonk === 'ok' ? '#4caf50'
    : _listmonkStatus?.listmonk === 'unreachable' ? '#f44336' : '#ff9800';
  const statusText = _listmonkStatus?.listmonk || 'unknown';

  el.innerHTML = `
    <div class="leadhunter-dashboard-grid">
      <div class="leadhunter-stat-card">
        <div class="leadhunter-stat-value">${_stats.total_leads}</div>
        <div class="leadhunter-stat-label">Total Leads</div>
      </div>
      <div class="leadhunter-stat-card">
        <div class="leadhunter-stat-value">${_stats.qualified_leads}</div>
        <div class="leadhunter-stat-label">Qualified Leads</div>
      </div>
      <div class="leadhunter-stat-card">
        <div class="leadhunter-stat-value">${_stats.synced_leads}</div>
        <div class="leadhunter-stat-label">Synced Leads</div>
      </div>
      <div class="leadhunter-stat-card">
        <div class="leadhunter-stat-value">${_stats.campaign_count}</div>
        <div class="leadhunter-stat-label">Campaigns</div>
      </div>
      <div class="leadhunter-stat-card">
        <div class="leadhunter-stat-value" style="font-size:13px;">${_stats.last_sync}</div>
        <div class="leadhunter-stat-label">Last Sync</div>
      </div>
      <div class="leadhunter-stat-card">
        <div class="leadhunter-stat-value" style="display:flex;align-items:center;gap:6px;">
          <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${statusColor};"></span>
          ${statusText}
        </div>
        <div class="leadhunter-stat-label">Listmonk Status</div>
      </div>
    </div>
  `;
}

function _renderLeads() {
  const el = document.getElementById('leadhunter-leads-content');
  if (!el) return;

  if (!_leads.length) {
    el.innerHTML = '<div class="leadhunter-empty">No leads yet. Discover leads from the Dashboard.</div>';
    return;
  }

  const rows = _leads.map(l => `
    <tr class="leadhunter-row">
      <td>${_esc(l.name || '')}</td>
      <td>${_esc(l.email || '')}</td>
      <td>${_esc(l.company || '')}</td>
      <td>${_esc(l.source || '')}</td>
      <td><span class="leadhunter-score ${l.score >= 70 ? 'qualified' : ''}">${l.score || 0}</span></td>
      <td><span class="leadhunter-status-badge ${l.status || 'new'}">${l.status || 'new'}</span></td>
      <td>${l.synced ? '<span style="color:#4caf50;">&#10003;</span>' : '<span style="opacity:0.3;">&#10007;</span>'}</td>
      <td>${l.created_at ? new Date(l.created_at).toLocaleDateString() : ''}</td>
    </tr>
  `).join('');

  el.innerHTML = `
    <div class="leadhunter-table-wrap">
      <table class="leadhunter-table">
        <thead>
          <tr>
            <th>Name</th><th>Email</th><th>Company</th><th>Source</th><th>Score</th><th>Status</th><th>Synced</th><th>Created</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
}

function _renderCampaigns() {
  const el = document.getElementById('leadhunter-campaigns-content');
  if (!el) return;

  if (!_campaigns.length) {
    el.innerHTML = '<div class="leadhunter-empty">No campaigns yet.</div>';
    return;
  }

  el.innerHTML = _campaigns.map(c => `
    <div class="leadhunter-campaign-card">
      <div class="leadhunter-campaign-name">${_esc(c.name || 'Unnamed')}</div>
      <div class="leadhunter-campaign-meta">
        <span class="leadhunter-status-badge ${c.status || 'draft'}">${c.status || 'draft'}</span>
        <span>${c.subscriber_count || 0} subscribers</span>
      </div>
      ${c.open_rate !== undefined ? `<div class="leadhunter-campaign-metrics">Open: ${c.open_rate}% · Click: ${c.click_rate || 0}%</div>` : ''}
    </div>
  `).join('');
}

function _renderListmonk() {
  const el = document.getElementById('leadhunter-listmonk-content');
  if (!el) return;

  if (!_listmonkStatus) {
    el.innerHTML = '<div class="leadhunter-empty">Loading Listmonk status...</div>';
    return;
  }

  const statusColor = _listmonkStatus.listmonk === 'ok' ? '#4caf50' : '#f44336';
  el.innerHTML = `
    <div class="leadhunter-listmonk-grid">
      <div class="leadhunter-stat-card">
        <div class="leadhunter-stat-value" style="display:flex;align-items:center;gap:6px;">
          <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${statusColor};"></span>
          ${_listmonkStatus.listmonk || 'unknown'}
        </div>
        <div class="leadhunter-stat-label">Connection</div>
      </div>
      <div class="leadhunter-stat-card">
        <div class="leadhunter-stat-value">${_listmonkStatus.database === 'ok' ? '&#10003;' : '&#10007;'}</div>
        <div class="leadhunter-stat-label">Database</div>
      </div>
      <div class="leadhunter-stat-card">
        <div class="leadhunter-stat-value">${_listmonkStatus.service === 'ok' ? '&#10003;' : '&#10007;'}</div>
        <div class="leadhunter-stat-label">Service</div>
      </div>
    </div>
  `;
}

function _renderSettings() {
  const el = document.getElementById('leadhunter-settings-content');
  if (!el) return;

  el.innerHTML = `
    <div class="leadhunter-settings-grid">
      <div class="leadhunter-setting-row">
        <span class="leadhunter-setting-label">API Status</span>
        <span class="leadhunter-setting-value">${_listmonkStatus?.service === 'ok' ? 'Connected' : 'Disconnected'}</span>
      </div>
      <div class="leadhunter-setting-row">
        <span class="leadhunter-setting-label">Database</span>
        <span class="leadhunter-setting-value">${_listmonkStatus?.database === 'ok' ? 'Connected' : 'Disconnected'}</span>
      </div>
      <div class="leadhunter-setting-row">
        <span class="leadhunter-setting-label">Listmonk URL</span>
        <span class="leadhunter-setting-value">${_listmonkStatus?.listmonk || 'Not configured'}</span>
      </div>
      <div class="leadhunter-setting-row">
        <span class="leadhunter-setting-label">Scheduler</span>
        <span class="leadhunter-setting-value">Running</span>
      </div>
    </div>
  `;
}

// ── Utilities ─────────────────────────────────────────────────────

function _esc(s) {
  const d = document.createElement('div');
  d.textContent = s || '';
  return d.innerHTML;
}

export function isOpen() { return _open; }
