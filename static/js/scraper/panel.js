/**
 * Generic Discovery Agent Panel — Clean interface for lead discovery.
 * Accepts any directory URL and autonomously discovers startup leads.
 */

import * as results from './results.js';
import * as logs from './logs.js';
import * as dashboard from './dashboard.js';
import { makeWindowDraggable } from '../windowDrag.js';

const API_BASE = window.location.origin;
let _open = false;
let _currentRun = null;
let _eventSource = null;

// ─────────────────────────────────────────────────────────────────────
// Panel Lifecycle
// ─────────────────────────────────────────────────────────────────────

export function toggle() {
  _open ? closePanel() : openPanel();
}

export async function openPanel() {
  if (_open) return;
  _open = true;

  const modal = document.createElement('div');
  modal.className = 'modal';
  modal.id = 'scraper-pane';
  modal.innerHTML = `
    <div class="modal-content scraper-modal-content">
      <div class="modal-header scraper-modal-header">
        <h4 style="display:flex;align-items:center;">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px;margin-right:6px">
            <circle cx="11" cy="11" r="8"/>
            <path d="M21 21l-4.35-4.35"/>
          </svg>
          Lead Discovery Agent
          <span class="scraper-status" id="scraper-status" style="margin-left:12px;">
            <span class="scraper-status-dot" id="scraper-status-dot"></span>
            <span id="scraper-status-text">Idle</span>
          </span>
        </h4>
        <span style="flex:1"></span>
        <button class="close-btn" id="scraper-close-btn" title="Close">✖</button>
      </div>
      <div class="scraper-toolbar-row" id="scraper-toolbar">
        <div style="display:flex;flex:1;gap:8px;align-items:center;">
          <input type="url" id="scraper-source-url" placeholder="Enter directory URL (Product Hunt, startup list, company directory...)" 
                 style="flex:1;padding:6px 10px;border:1px solid var(--border);border-radius:4px;background:var(--input-bg);color:var(--text);"
                 list="scraper-examples-list" />
          <datalist id="scraper-examples-list">
            <option value="https://www.producthunt.com/leaderboard/daily">Product Hunt Daily</option>
            <option value="https://www.producthunt.com/topics">Product Hunt Topics</option>
            <option value="https://indiehackers.org">Indie Hackers</option>
            <option value="https://betalist.com">BetaList</option>
          </datalist>
        </div>
        <div style="display:flex;gap:8px;align-items:center;">
          <button class="scraper-btn scraper-btn-secondary" id="scraper-export-btn">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x1="12" y2="3"/></svg>
            Export
          </button>
          <button class="scraper-btn scraper-btn-primary" id="scraper-run-btn">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
            Discover
          </button>
        </div>
      </div>
      <div class="scraper-main-row">
        <div class="scraper-console-panel">
          <div class="scraper-section-title">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x1="20" y2="19"/></svg>
            Activity Console
          </div>
          <div class="scraper-console" id="scraper-console"></div>
        </div>
        <div class="scraper-results-panel">
          <div class="scraper-section-title">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
            Leads
            <span class="scraper-lead-count" id="scraper-lead-count"></span>
          </div>
          <div class="scraper-results" id="scraper-results"></div>
          <div class="scraper-pagination" id="scraper-pagination"></div>
        </div>
      </div>
      <div class="scraper-footer-row" id="scraper-footer">
        <div class="scraper-stats-row" id="scraper-stats" style="display:grid;grid-template-columns:repeat(auto-fit, minmax(100px, 1fr));gap:10px;"></div>
      </div>
    </div>
  `;
  document.body.appendChild(modal);

  const content = modal.querySelector('.modal-content');
  const header = modal.querySelector('.modal-header');
  if (content && header) {
    makeWindowDraggable(modal, {
      content,
      header,
      enableFullscreen: false,
      resizeStorageKey: 'winsize-scraper-pane',
      minWidth: 480,
      minHeight: 360,
    });
  }

  try {
    const Modals = await import('../modalManager.js');
    Modals.register('scraper-pane', {
      railBtnId: 'rail-scraper',
      sidebarBtnId: 'tool-scraper-btn',
      closeFn: closePanel,
      restoreFn: () => {},
      label: 'Discovery Agent',
      icon: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>',
    });
  } catch {}

  _wireEvents(modal);

  modal.addEventListener('click', (e) => {
    if (e.target === modal) closePanel();
  });

  _escHandler = (e) => {
    if (e.key === 'Escape' && _open) closePanel();
  };
  document.addEventListener('keydown', _escHandler);

  await _loadStats();
  await _loadLeads();

  let _escHandler;
  window.addEventListener('lead-deleted', () => {
    _loadLeads();
    _loadStats();
  });

  document.getElementById('tool-scraper-btn')?.classList.add('active');
  document.getElementById('rail-scraper')?.classList.add('active');
}

export function closePanel() {
  if (!_open) return;
  _open = false;
  _disconnectStream();

  const modal = document.getElementById('scraper-pane');
  if (modal) {
    const content = modal.querySelector('.modal-content');
    if (content) {
      content.classList.add('modal-closing');
      content.addEventListener('animationend', () => modal.remove(), { once: true });
      setTimeout(() => { if (modal.parentElement) modal.remove(); }, 250);
    } else {
      modal.remove();
    }
  }

  if (_escHandler) {
    document.removeEventListener('keydown', _escHandler);
    _escHandler = null;
  }

  document.getElementById('tool-scraper-btn')?.classList.remove('active');
  document.getElementById('rail-scraper')?.classList.remove('active');

  try {
    import('../modalManager.js').then(m => m.unregister('scraper-pane'));
  } catch {}
}

export function isOpen() {
  return _open;
}

// ─────────────────────────────────────────────────────────────────────
// Event Wiring
// ─────────────────────────────────────────────────────────────────────

function _wireEvents(modal) {
  modal.querySelector('#scraper-close-btn')?.addEventListener('click', closePanel);
  modal.querySelector('#scraper-run-btn')?.addEventListener('click', _startScrape);
  modal.querySelector('#scraper-export-btn')?.addEventListener('click', _exportCsv);
}

// ─────────────────────────────────────────────────────────────────────
// Data Loading
// ─────────────────────────────────────────────────────────────────────

async function _loadStats() {
  try {
    const res = await fetch(`${API_BASE}/api/scraper/stats`, { credentials: 'same-origin' });
    if (res.ok) {
      const stats = await res.json();
      dashboard.render(document.getElementById('scraper-stats'), stats);
    }
  } catch (e) {
    console.warn('Failed to load scraper stats:', e);
  }
}

async function _loadLeads(page = 1) {
  try {
    const params = new URLSearchParams({ page: page.toString(), limit: '50' });
    const res = await fetch(`${API_BASE}/api/scraper/leads?${params}`, { credentials: 'same-origin' });
    if (res.ok) {
      const data = await res.json();
      _leads = data.leads || [];
      results.render(document.getElementById('scraper-results'), _leads, _openLeadDetail);
      document.getElementById('scraper-lead-count').textContent = `(${data.total || 0})`;
    }
  } catch (e) {
    console.warn('Failed to load scraper leads:', e);
  }
}

let _leads = [];

// ─────────────────────────────────────────────────────────────────────
// Scrape Control
// ─────────────────────────────────────────────────────────────────────

async function _startScrape() {
  const sourceUrl = document.getElementById('scraper-source-url').value.trim();
  const btn = document.getElementById('scraper-run-btn');
  const statusDot = document.getElementById('scraper-status-dot');
  const statusText = document.getElementById('scraper-status-text');

  if (!sourceUrl) {
    logs.addMessage('scraper-console', { type: 'error', message: 'Please enter a source URL' });
    return;
  }

  // Proper URL validation using URL constructor
  try {
    const url = new URL(sourceUrl);
    // Must be http or https
    if (url.protocol !== 'http:' && url.protocol !== 'https:') {
      throw new Error('Protocol must be http or https');
    }
  } catch (e) {
    logs.addMessage('scraper-console', { type: 'error', message: `Invalid URL: ${e.message}` });
    return;
  }

  btn.disabled = true;
  btn.innerHTML = '<span class="scraper-spinner"></span> Discovering...';
  statusDot?.classList.add('active');
  statusText.textContent = 'Running';

  try {
    const res = await fetch(`${API_BASE}/api/scraper/start`, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source_url: sourceUrl }),
    });

    if (res.ok) {
      const data = await res.json();
      if (data.error) {
        throw new Error(data.error);
      }
      _currentRun = data.run_id;
      _connectStream(data.run_id);
      logs.addMessage('scraper-console', { type: 'info', message: `Discovery started from: ${sourceUrl}` });
    } else {
      throw new Error('Failed to start discovery');
    }
  } catch (e) {
    console.error('Start discovery failed:', e);
    logs.addMessage('scraper-console', { type: 'error', message: `Failed: ${e.message}` });
    btn.disabled = false;
    btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg> Discover';
  }
}

async function _exportCsv() {
  try {
    const res = await fetch(`${API_BASE}/api/scraper/export`, { credentials: 'same-origin' });
    if (res.ok) {
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'scraper_leads.csv';
      a.click();
      window.URL.revokeObjectURL(url);
    }
  } catch (e) {
    console.error('Export failed:', e);
    logs.addMessage('scraper-console', { type: 'error', message: 'Export failed' });
  }
}

function _connectStream(runId) {
  _disconnectStream();

  const evtSource = new EventSource(`${API_BASE}/api/scraper/stream/${runId}`);
  _eventSource = evtSource;

  evtSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      _handleStreamEvent(data);
    } catch {}
  };

  evtSource.onerror = () => {
    _disconnectStream();
    _onRunComplete();
  };
}

function _disconnectStream() {
  if (_eventSource) {
    _eventSource.close();
    _eventSource = null;
  }
}

function _handleStreamEvent(event) {
  logs.addMessage('scraper-console', event);

  if (event.type === 'lead_found') {
    _loadLeads();
    _loadStats();
  }

  if (event.type === 'done' || event.type === 'completed') {
    _onRunComplete();
  }
}

function _onRunComplete() {
  _disconnectStream();
  _currentRun = null;

  const btn = document.getElementById('scraper-run-btn');
  if (btn) {
    btn.disabled = false;
    btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg> Discover';
  }

  const statusDot = document.getElementById('scraper-status-dot');
  const statusText = document.getElementById('scraper-status-text');
  statusDot?.classList.remove('active');
  statusText.textContent = 'Idle';

  _loadStats();
  _loadLeads();
}

// ─────────────────────────────────────────────────────────────────────
// Lead Detail
// ─────────────────────────────────────────────────────────────────────

function _openLeadDetail(leadId) {
  // Simple inline detail view
  const lead = _leads.find(l => l.id === leadId);
  if (!lead) return;

  const modal = document.createElement('div');
  modal.className = 'modal';
  modal.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.5);z-index:10000;display:flex;align-items:center;justify-content:center;';
  modal.innerHTML = `
    <div style="background:var(--bg);border-radius:8px;padding:20px;max-width:500px;width:90%;max-height:80vh;overflow:auto;">
      <h3 style="margin-top:0;">${lead.name || 'Unknown'}</h3>
      <p><strong>Website:</strong> <a href="${lead.website}" target="_blank" style="color:var(--accent);">${lead.website || 'N/A'}</a></p>
      <p><strong>Description:</strong> ${lead.description || 'N/A'}</p>
      <p><strong>Industry:</strong> ${lead.industry || lead.category || 'N/A'}</p>
      <p><strong>Emails:</strong> ${(lead.emails || []).join(', ') || 'None found'}</p>
      <p><strong>Founders:</strong> ${(lead.founders || []).map(f => f.name || f).join(', ') || 'N/A'}</p>
      <div style="margin-top:16px;display:flex;gap:8px;justify-content:flex-end;">
        <button class="scraper-btn scraper-btn-secondary" id="delete-lead-btn" data-lead-id="${lead.id}">Delete</button>
        <button class="scraper-btn scraper-btn-primary" id="close-detail-btn">Close</button>
      </div>
    </div>
  `;
  document.body.appendChild(modal);

  modal.querySelector('#close-detail-btn')?.addEventListener('click', () => modal.remove());
  modal.querySelector('#delete-lead-btn')?.addEventListener('click', async (e) => {
    const leadId = e.target.dataset.leadId;
    await fetch(`${API_BASE}/api/scraper/lead/${leadId}`, { method: 'DELETE', credentials: 'same-origin' });
    modal.remove();
    _loadLeads();
    _loadStats();
  });
}