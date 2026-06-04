/**
 * Scraper Logs — Live activity console.
 */

let _messageCount = 0;
const MAX_MESSAGES = 200;

export function addMessage(containerId, event) {
  const container = document.getElementById(containerId);
  if (!container) return;

  const line = document.createElement('div');
  line.className = `scraper-log-line scraper-log-${event.type || 'info'}`;

  const timestamp = new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });

  let icon = '';
  let message = '';

  switch (event.type) {
    case 'log':
      icon = '<span class="scraper-log-icon">›</span>';
      message = event.message || '';
      break;
    case 'lead_found':
      icon = '<span class="scraper-log-icon scraper-log-success">+</span>';
      message = `Lead found: ${event.lead?.name || event.name || 'Unknown'}`;
      break;
    case 'lead_scored':
      icon = '<span class="scraper-log-icon scraper-log-info">★</span>';
      message = `Scored: ${event.name || 'Unknown'} (${event.affordability_score || '?'}/100)`;
      break;
    case 'progress':
      icon = '<span class="scraper-log-icon">⟳</span>';
      message = `${event.provider || ''}: ${event.current || 0}/${event.total || '?'}`;
      break;
    case 'provider_update':
      icon = `<span class="scraper-log-icon">${event.status === 'scraping' ? '⟳' : '✓'}</span>`;
      message = `${event.provider}: ${event.status}`;
      break;
    case 'error':
      icon = '<span class="scraper-log-icon scraper-log-error">✗</span>';
      message = event.message || 'Error occurred';
      break;
    case 'warning':
      icon = '<span class="scraper-log-icon scraper-log-warn">!</span>';
      message = event.message || 'Warning';
      break;
    case 'completed':
      icon = '<span class="scraper-log-icon scraper-log-success">✓</span>';
      if (event.stats) {
        message = `Completed: ${event.stats.raw_candidates || 0} raw → ${event.stats.qualified_startups || 0} qualified → ${event.stats.stored_leads || 0} stored`;
      } else {
        message = `Completed: ${event.leads_found || 0} leads found`;
      }
      break;
    default:
      icon = '<span class="scraper-log-icon">•</span>';
      message = event.message || JSON.stringify(event);
  }

  line.innerHTML = `<span class="scraper-log-time">[${timestamp}]</span> ${icon} <span class="scraper-log-msg">${_escapeHtml(message)}</span>`;

  container.appendChild(line);
  _messageCount++;

  // Trim old messages
  while (container.children.length > MAX_MESSAGES) {
    container.removeChild(container.firstChild);
  }

  // Auto-scroll
  container.scrollTop = container.scrollHeight;
}

export function clear(containerId) {
  const container = document.getElementById(containerId);
  if (container) {
    container.innerHTML = '';
    _messageCount = 0;
  }
}

function _escapeHtml(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
