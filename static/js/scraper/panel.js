/**
 * Scraper Intelligence System — Main Panel Module
 * Autonomous startup lead discovery and qualification dashboard.
 *
 * Renders as a native Odysseus floating window (same infrastructure as
 * Tasks, Compare, Research).  Supports drag, snap, dock, minimize, and
 * z-index stacking via modalManager + windowDrag.
 */

import * as results from './results.js';
import * as filters from './filters.js';
import * as logs from './logs.js';
import * as dashboard from './dashboard.js';
import * as providers from './providers.js';
import * as leadModal from './leadModal.js';
import * as exportModule from './export.js';
import { makeWindowDraggable } from '../windowDrag.js';
import themeModule from '../theme.js';

const API_BASE = window.location.origin;
let _open = false;
let _currentRun = null;
let _eventSource = null;
let _stats = null;
let _leads = [];
let _filtersState = {};
let _escHandler = null;

// ─────────────────────────────────────────────────────────────────────
// Panel Lifecycle
// ─────────────────────────────────────────────────────────────────────

export function toggle() {
  _open ? closePanel() : openPanel();
}

export async function openPanel() {
  if (_open) return;
  _open = true;

  // Build modal shell — same structure as Tasks / Compare / Research.
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
            <path d="M11 8v6M8 11h6"/>
          </svg>
          Scraper Intelligence
          <span class="scraper-status" id="scraper-status" style="margin-left:12px;">
            <span class="scraper-status-dot" id="scraper-status-dot"></span>
            <span id="scraper-status-text">Idle</span>
          </span>
        </h4>
        <span style="flex:1"></span>
        <button class="close-btn" id="scraper-close-btn" title="Close">✖</button>
      </div>
      <div class="scraper-toolbar-row" id="scraper-toolbar">
        <div class="scraper-filters-row" id="scraper-filters" style="display:flex;flex:1;gap:8px;align-items:center;"></div>
        <div style="display:flex;gap:8px;align-items:center;">
          <button class="scraper-btn scraper-btn-secondary" id="scraper-export-btn">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            Export
          </button>
          <button class="scraper-btn scraper-btn-primary" id="scraper-run-btn">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
            Start Scrape
          </button>
        </div>
      </div>
      <div class="scraper-main-row">
        <div class="scraper-console-panel">
          <div class="scraper-section-title">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>
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
        <div class="scraper-stats-row" id="scraper-stats" style="display:grid;grid-template-columns:repeat(auto-fit, minmax(140px, 1fr));gap:10px;"></div>
      </div>
    </div>
  `;
  document.body.appendChild(modal);

  // Make draggable — shared helper handles drag + L/R dock + snap.
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

  // Register with modal manager for minimize/restore/dock.
  try {
    const Modals = await import('../modalManager.js');
    Modals.register('scraper-pane', {
      railBtnId: 'rail-scraper',
      sidebarBtnId: 'tool-scraper-btn',
      closeFn: closePanel,
      restoreFn: () => {},
      label: 'Scraper',
      icon: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/><path d="M11 8v6M8 11h6"/></svg>',
    });
  } catch {}

  // Wire up UI
  _wireEvents(modal);

  // Close on backdrop click (click outside .modal-content)
  modal.addEventListener('click', (e) => {
    if (e.target === modal) closePanel();
  });

  // ESC to close
  _escHandler = (e) => {
    if (e.key === 'Escape' && _open) closePanel();
  };
  document.addEventListener('keydown', _escHandler);

  // Load initial data
  await _loadStats();
  await _loadLeads();
  await _loadProviders();

  // Update active state
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
  // Close button
  modal.querySelector('#scraper-close-btn')?.addEventListener('click', closePanel);

  // Run button
  modal.querySelector('#scraper-run-btn')?.addEventListener('click', _startScrape);

  // Export button
  modal.querySelector('#scraper-export-btn')?.addEventListener('click', () => {
    exportModule.showExportDialog(_filtersState);
  });
}

// ─────────────────────────────────────────────────────────────────────
// Data Loading
// ─────────────────────────────────────────────────────────────────────

async function _loadStats() {
  try {
    const res = await fetch(`${API_BASE}/api/scraper/stats`, { credentials: 'same-origin' });
    if (res.ok) {
      _stats = await res.json();
      dashboard.render(document.getElementById('scraper-stats'), _stats);
    }
  } catch (e) {
    console.warn('Failed to load scraper stats:', e);
  }
}

async function _loadLeads(page = 1) {
  try {
    const params = new URLSearchParams({ page: page.toString(), limit: '50' });
    if (_filtersState.min_score) params.set('min_score', _filtersState.min_score);
    if (_filtersState.provider) params.set('provider', _filtersState.provider);

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

async function _loadProviders() {
  try {
    const res = await fetch(`${API_BASE}/api/scraper/providers`, { credentials: 'same-origin' });
    if (res.ok) {
      const data = await res.json();
      providers.render(document.getElementById('scraper-filters'), data.providers, _filtersState, (newFilters) => {
        _filtersState = newFilters;
        _loadLeads();
      });
    }
  } catch (e) {
    console.warn('Failed to load scraper providers:', e);
  }
}

// ─────────────────────────────────────────────────────────────────────
// Scrape Control
// ─────────────────────────────────────────────────────────────────────

async function _startScrape() {
  const btn = document.getElementById('scraper-run-btn');
  const statusDot = document.getElementById('scraper-status-dot');
  const statusText = document.getElementById('scraper-status-text');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="scraper-spinner"></span> Running...';
  }
  if (statusDot) statusDot.classList.add('active');
  if (statusText) statusText.textContent = 'Running';

  try {
    const body = {
      providers: _filtersState.providers || ['hackernews', 'producthunt'],
      filters: _filtersState,
    };

    const res = await fetch(`${API_BASE}/api/scraper/start`, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    if (res.ok) {
      const data = await res.json();
      _currentRun = data.run_id;
      _connectStream(data.run_id);
      logs.addMessage('scraper-console', { type: 'info', message: 'Scrape started...' });
    } else {
      throw new Error('Failed to start scrape');
    }
  } catch (e) {
    console.error('Start scrape failed:', e);
    logs.addMessage('scraper-console', { type: 'error', message: `Failed: ${e.message}` });
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg> Start Scrape';
    }
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
  const consoleEl = document.getElementById('scraper-console');
  if (!consoleEl) return;

  // Add to console
  logs.addMessage('scraper-console', event);

  // Handle specific events
  if (event.type === 'lead_found') {
    _loadLeads();  // Refresh leads list
    _loadStats();  // Refresh stats
  }

  if (event.type === 'lead_scored') {
    _loadLeads();
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
    btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg> Start Scrape';
  }

  const statusDot = document.getElementById('scraper-status-dot');
  const statusText = document.getElementById('scraper-status-text');
  if (statusDot) statusDot.classList.remove('active');
  if (statusText) statusText.textContent = 'Idle';

  _loadStats();
  _loadLeads();
}

// ─────────────────────────────────────────────────────────────────────
// Lead Detail
// ─────────────────────────────────────────────────────────────────────

function _openLeadDetail(leadId) {
  const lead = _leads.find(l => l.id === leadId);
  if (lead) {
    leadModal.show(lead);
  }
}
