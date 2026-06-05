/**
 * LeadHunter Module — Lead discovery dashboard and campaign analytics.
 */

import uiModule from './ui.js';
import spinnerModule from './spinner.js';
import * as Modals from './modalManager.js';
import { makeWindowDraggable } from './windowDrag.js';

const API_BASE = window.location.origin;
let _open = false;
let _stats = { total_leads: 0, qualified_leads: 0, synced_leads: 0, emails_sent: 0, opens: 0, clicks: 0 };
let _leads = [];
let _modal = null;
let _backdrop = null;
let _escHandler = null;

function _escKeyDown(e) {
    if (e.key === 'Escape') {
        closePanel();
    }
}

function _render() {
    const pane = document.getElementById('leadhunter-pane');
    if (!pane) return;

    pane.innerHTML = `
        <div class="leadhunter-header">
            <h3>LeadHunter Dashboard</h3>
            <div class="leadhunter-stats">
                <div class="stat-item"><span class="stat-value">${_stats.total_leads}</span><span class="stat-label">Total Leads</span></div>
                <div class="stat-item"><span class="stat-value">${_stats.qualified_leads}</span><span class="stat-label">Qualified</span></div>
                <div class="stat-item"><span class="stat-value">${_stats.synced_leads}</span><span class="stat-label">Synced</span></div>
                <div class="stat-item"><span class="stat-value">${_stats.emails_sent}</span><span class="stat-label">Sent</span></div>
                <div class="stat-item"><span class="stat-value">${_stats.opens}</span><span class="stat-label">Opens</span></div>
                <div class="stat-item"><span class="stat-value">${_stats.clicks}</span><span class="stat-label">Clicks</span></div>
            </div>
        </div>
    `;
}

async function _fetchStats() {
    try {
        const res = await fetch(`${API_BASE}/api/leadhunter/stats`, { credentials: 'same-origin' });
        if (res.ok) {
            const data = await res.json();
            _stats = data;
            _render();
        }
    } catch (e) {
        console.error('LeadHunter: failed to fetch stats', e);
    }
}

function _buildPanel() {
    document.getElementById('leadhunter-pane')?.remove();
    document.getElementById('leadhunter-pane-backdrop')?.remove();

    const backdrop = document.createElement('div');
    backdrop.id = 'leadhunter-pane-backdrop';
    backdrop.className = 'modal-backdrop';

    const pane = document.createElement('div');
    pane.id = 'leadhunter-pane';
    pane.className = 'modal';
    pane.style.cssText = 'max-width: 600px; padding: 20px;';
    pane.innerHTML = '<div class="modal-spinner">Loading...</div>';

    Modals.register('leadhunter-pane', pane);
    document.body.appendChild(backdrop);
    document.body.appendChild(pane);

    makeWindowDraggable(pane, pane.querySelector('.modal-header') || pane);
    _modal = pane;
    _backdrop = backdrop;

    return pane;
}

function openPanel() {
    if (_open) {
        closePanel();
        return;
    }
    _open = true;
    document.getElementById('tool-leadhunter-btn')?.classList.add('active');
    const pane = _buildPanel();

    _escHandler = _escKeyDown;
    document.addEventListener('keydown', _escHandler);

    if (_backdrop) {
        _backdrop.addEventListener('click', closePanel);
    }
    if (pane) {
        pane.addEventListener('click', (e) => {
            if (e.target === _backdrop) closePanel();
        });
    }

    _fetchStats();
}

function closePanel() {
    _open = false;
    document.getElementById('tool-leadhunter-btn')?.classList.remove('active');
    if (_escHandler) {
        document.removeEventListener('keydown', _escHandler);
        _escHandler = null;
    }
    Modals.unregister('leadhunter-pane');
    document.getElementById('leadhunter-pane')?.remove();
    document.getElementById('leadhunter-pane-backdrop')?.remove();
}

function isPanelOpen() { return _open; }

export { openPanel, closePanel, isPanelOpen };
export default { openPanel, closePanel, isPanelOpen };