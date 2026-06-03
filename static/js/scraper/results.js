/**
 * Scraper Results — Lead cards and grid rendering.
 */

export function render(container, leads, onLeadClick) {
  if (!container) return;

  if (!leads || leads.length === 0) {
    container.innerHTML = `
      <div class="scraper-empty">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.3">
          <circle cx="11" cy="11" r="8"/>
          <path d="M21 21l-4.35-4.35"/>
        </svg>
        <p>No leads found yet.</p>
        <p class="scraper-empty-hint">Start a scrape run to discover startup leads.</p>
      </div>
    `;
    return;
  }

  const cards = leads.map(lead => _renderCard(lead)).join('');
  container.innerHTML = `<div class="scraper-cards-grid">${cards}</div>`;

  // Wire click events
  container.querySelectorAll('.scraper-card').forEach(card => {
    card.addEventListener('click', () => {
      const leadId = card.dataset.leadId;
      if (onLeadClick) onLeadClick(leadId);
    });
  });
}

function _renderCard(lead) {
  const score = lead.affordability_score || 0;
  const scoreClass = score >= 70 ? 'high' : score >= 40 ? 'medium' : 'low';
  const provider = lead.source_provider || 'unknown';
  const website = lead.website ? new URL(lead.website).hostname.replace('www.', '') : '';
  const description = lead.description ? _truncate(lead.description, 100) : 'No description available';
  const emailCount = (lead.emails || []).length;
  const founderCount = (lead.founders || []).length;

  return `
    <div class="scraper-card" data-lead-id="${lead.id}">
      <div class="scraper-card-header">
        <div class="scraper-card-name">${_escapeHtml(lead.name)}</div>
        <div class="scraper-score ${scoreClass}" title="Affordability Score">${score || '—'}</div>
      </div>
      <div class="scraper-card-website">${_escapeHtml(website)}</div>
      <div class="scraper-card-desc">${_escapeHtml(description)}</div>
      <div class="scraper-card-meta">
        <span class="scraper-badge scraper-badge-provider">${_escapeHtml(provider)}</span>
        ${lead.category ? `<span class="scraper-badge scraper-badge-category">${_escapeHtml(lead.category)}</span>` : ''}
        ${emailCount ? `<span class="scraper-meta-icon"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/></svg>${emailCount}</span>` : ''}
        ${founderCount ? `<span class="scraper-meta-icon"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>${founderCount}</span>` : ''}
      </div>
      ${lead.ai_summary ? `<div class="scraper-card-ai">${_escapeHtml(_truncate(lead.ai_summary, 80))}</div>` : ''}
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
