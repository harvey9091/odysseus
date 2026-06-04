/**
 * Scraper Results — Lead cards and grid rendering.
 */

export function render(container, leads, onLeadClick) {
  if (!container) return;

  if (!leads || leads.length === 0) {
    container.innerHTML = `
      <div class="scraper-results-empty">
        <svg class="scraper-results-empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <circle cx="11" cy="11" r="8"/>
          <path d="M21 21l-4.35-4.35"/>
        </svg>
        <p class="scraper-results-empty-text">No leads found yet.</p>
        <p class="scraper-results-empty-hint">Enter a directory URL and click Discover to find startup leads.</p>
      </div>
    `;
    return;
  }

  const cards = leads.map(lead => _renderCard(lead)).join('');
  container.innerHTML = `<div class="scraper-results-grid">${cards}</div>`;

  container.querySelectorAll('.scraper-card').forEach(card => {
    card.addEventListener('click', () => {
      const leadId = card.dataset.leadId;
      if (onLeadClick) onLeadClick(leadId);
    });
  });
}

function _renderCard(lead) {
  const website = lead.website ? _extractDomain(lead.website) : '';
  const description = lead.description || 'No description available';
  const emailCount = (lead.emails || []).length;
  const founderCount = (lead.founders || []).length;

  let founderName = 'Team';
  if (lead.founders && lead.founders.length > 0) {
    founderName = lead.founders[0].name || lead.founders[0] || 'Unknown';
    if (lead.founders.length > 1) {
      founderName += `+${lead.founders.length - 1}`;
    }
  }

  const industry = lead.industry || lead.category || '';
  const source = lead.source_provider || 'discovery_agent';

  return `
    <div class="scraper-card" data-lead-id="${lead.id}">
      <div class="scraper-card-header">
        <div class="scraper-card-name">${_escapeHtml(lead.name)}</div>
      </div>
      <div class="scraper-card-website">${_escapeHtml(website)}</div>
      <div class="scraper-card-desc">${_escapeHtml(_truncate(description, 80))}</div>
      <div class="scraper-card-meta">
        <span class="scraper-badge scraper-badge-industry">${_escapeHtml(industry)}</span>
        ${emailCount ? `<span class="scraper-meta-emails" title="${(lead.emails || []).join(', ')}">✉ ${emailCount}</span>` : ''}
        ${founderCount ? `<span class="scraper-meta-founders">👤 ${founderCount}</span>` : ''}
      </div>
    </div>
  `;
}

function _truncate(str, len) {
  if (!str) return '';
  return str.length > len ? str.substring(0, len) + '...' : str;
}

function _escapeHtml(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function _extractDomain(url) {
  try {
    return new URL(url).hostname.replace('www.', '');
  } catch {
    return url;
  }
}