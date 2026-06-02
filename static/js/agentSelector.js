/**
 * agentSelector.js — Agent backend selector UI.
 *
 * Displays the currently active agent (OpenCode, Hermes, etc.) near the
 * chat input area and provides a dropdown to switch between backends.
 * Integrates with the /api/agents backend API.
 */

let _agents = [];
let _currentAgent = null;
let _menuOpen = false;

/** Fetch available agent backends from the server */
async function fetchAgents() {
  try {
    const res = await fetch('/api/agents');
    if (!res.ok) return;
    _agents = await res.json();
    _currentAgent = _agents.find(a => a.active) || _agents[0];
    updateDisplay();
  } catch (e) {
    console.warn('[agentSelector] fetchAgents error:', e);
  }
}

/** Switch the active agent backend */
async function switchAgent(name) {
  try {
    const res = await fetch('/api/agents/switch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ backend: name }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      console.warn('[agentSelector] switch failed:', data.detail || res.statusText);
      return;
    }
    // Refresh list to get updated active state
    await fetchAgents();
  } catch (e) {
    console.warn('[agentSelector] switchAgent error:', e);
  }
}

/** Update the UI display */
function updateDisplay() {
  const label = document.getElementById('agent-selector-label');
  if (!label) return;

  if (_currentAgent) {
    label.textContent = _currentAgent.display_name || _currentAgent.name;
    label.title = _currentAgent.description || '';
  } else {
    label.textContent = 'Agent';
  }

  // Also update the dropdown menu items
  const menu = document.getElementById('agent-selector-menu');
  if (menu) {
    menu.innerHTML = '';
    _agents.forEach(agent => {
      const item = document.createElement('div');
      item.className = 'agent-selector-item' + (agent.active ? ' active' : '');
      item.innerHTML = `
        <span class="agent-item-name">${agent.display_name || agent.name}</span>
        ${agent.active ? '<span class="agent-item-check">✓</span>' : ''}
      `;
      item.title = agent.description || '';
      item.addEventListener('click', () => {
        switchAgent(agent.name);
        toggleMenu(false);
      });
      menu.appendChild(item);
    });
  }
}

/** Toggle the dropdown menu */
function toggleMenu(force) {
  const menu = document.getElementById('agent-selector-menu');
  if (!menu) return;

  _menuOpen = typeof force === 'boolean' ? force : !_menuOpen;
  menu.classList.toggle('hidden', !_menuOpen);

  if (_menuOpen) {
    // Close menu when clicking outside
    setTimeout(() => {
      document.addEventListener('click', _handleOutsideClick, { once: true });
    }, 0);
  }
}

function _handleOutsideClick(e) {
  const wrap = document.getElementById('agent-selector-wrap');
  if (wrap && !wrap.contains(e.target)) {
    toggleMenu(false);
  }
}

/** Initialize the agent selector UI */
export function initAgentSelector() {
  const btn = document.getElementById('agent-selector-btn');
  if (btn) {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      toggleMenu();
    });
  }

  // Close menu on escape
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && _menuOpen) {
      toggleMenu(false);
    }
  });

  // Initial fetch
  fetchAgents();
}

/** Refresh the agent list (called when settings change) */
export function refreshAgents() {
  fetchAgents();
}

/** Get the currently active agent name */
export function getActiveAgent() {
  return _currentAgent ? _currentAgent.name : null;
}

/** Get the currently active agent display name */
export function getActiveAgentName() {
  return _currentAgent ? (_currentAgent.display_name || _currentAgent.name) : 'Agent';
}
