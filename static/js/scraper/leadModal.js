/**
 * Scraper Lead Modal — Lead detail view.
 */

let _modalEl = null;

export function show(lead) {
  if (!lead) return;
  close();

  const modal = document.createElement('div');
  modal.id = 'scraper-lead-modal';
  modal.className = 'scraper-modal';
  modal.innerHTML = _renderContent(lead);
  document.body.appendChild(modal);
  _modalEl = modal;

  // Backdrop
  const backdrop = document.createElement('div');
  backdrop.id = 'scraper-modal-backdrop';
  backdrop.addEventListener('click', close);
  document.body.appendChild(backdrop);

  // Close on escape
  document.addEventListener('keydown', _handleKeydown);
}

export function close() {
  if (_modalEl) {
    _modalEl.remove();
    _modalEl = null;
  }
  document.getElementById('scraper-modal-backdrop')?.remove();
  document.removeEventListener('keydown', _handleKeydown);
}

function _handleKeydown(e) {
  if (e.key === 'Escape') close();
}

function _renderContent(lead) {
  const score = lead.affordability_score || 0;
  const scoreClass = score >= 70 ? 'high' : score >= 40 ? 'medium' : 'low';

  return `
    <div class="scraper-modal-content">
      <div class="scraper-modal-header">
        <div class="scraper-modal-title">
          <h3>${_escapeHtml(lead.name)}</h3>
          ${lead.website ? `<a href="${lead.website}" target="_blank" class="scraper-modal-link">${_escapeHtml(lead.website)}</a>` : ''}
        </div>
        <button class="scraper-modal-close" onclick="document.getElementById('scraper-lead-modal')?.remove(); document.getElementById('scraper-modal-backdrop')?.remove();">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
      </div>

      <div class="scraper-modal-body">
        <!-- Scores Row -->
        <div class="scraper-modal-scores">
          <div class="scraper-score-widget ${scoreClass}">
            <div class="scraper-score-value">${score || '—'}</div>
            <div class="scraper-score-label">Affordability</div>
          </div>
          <div class="scraper-score-widget">
            <div class="scraper-score-value">${lead.promo_video_fit_score || '—'}</div>
            <div class="scraper-score-label">Video Fit</div>
          </div>
          <div class="scraper-score-widget">
            <div class="scraper-score-value">${lead.urgency_score || '—'}</div>
            <div class="scraper-score-label">Urgency</div>
          </div>
          <div class="scraper-score-widget">
            <div class="scraper-score-value">${lead.funding_probability || '—'}</div>
            <div class="scraper-score-label">Funding</div>
          </div>
        </div>

        <!-- AI Summary -->
        ${lead.ai_summary ? `
          <div class="scraper-modal-section">
            <h4>AI Analysis</h4>
            <p class="scraper-ai-summary">${_escapeHtml(lead.ai_summary)}</p>
          </div>
        ` : ''}

        <!-- Description -->
        ${lead.description ? `
          <div class="scraper-modal-section">
            <h4>Description</h4>
            <p>${_escapeHtml(lead.description)}</p>
          </div>
        ` : ''}

        <!-- Contact Info -->
        <div class="scraper-modal-section">
          <h4>Contact Information</h4>
          ${lead.emails && lead.emails.length > 0 ? `
            <div class="scraper-contact-list">
              ${lead.emails.map(e => `<a href="mailto:${_escapeHtml(e)}" class="scraper-email">${_escapeHtml(e)}</a>`).join('')}
            </div>
          ` : '<p class="scraper-muted">No emails found</p>'}

          ${lead.founders && lead.founders.length > 0 ? `
            <div class="scraper-founders-list">
              <h5>Founders</h5>
              ${lead.founders.map(f => `
                <div class="scraper-founder">
                  <span class="scraper-founder-name">${_escapeHtml(f.name || 'Unknown')}</span>
                  ${f.linkedin ? `<a href="${_escapeHtml(f.linkedin)}" target="_blank" class="scraper-founder-link">LinkedIn</a>` : ''}
                  ${f.twitter ? `<a href="${_escapeHtml(f.twitter)}" target="_blank" class="scraper-founder-link">Twitter</a>` : ''}
                </div>
              `).join('')}
            </div>
          ` : ''}
        </div>

        <!-- Social Profiles -->
        ${lead.social && Object.keys(lead.social).length > 0 ? `
          <div class="scraper-modal-section">
            <h4>Social Profiles</h4>
            <div class="scraper-social-list">
              ${Object.entries(lead.social).map(([platform, url]) => `
                <a href="${_escapeHtml(url)}" target="_blank" class="scraper-social-link">${_escapeHtml(platform)}</a>
              `).join('')}
            </div>
          </div>
        ` : ''}

        <!-- Tech Stack -->
        ${lead.tech_stack && lead.tech_stack.length > 0 ? `
          <div class="scraper-modal-section">
            <h4>Tech Stack</h4>
            <div class="scraper-tech-tags">
              ${lead.tech_stack.map(t => `<span class="scraper-tag">${_escapeHtml(t)}</span>`).join('')}
            </div>
          </div>
        ` : ''}

        <!-- Outreach Recommendations -->
        ${lead.outreach_recommendations ? `
          <div class="scraper-modal-section">
            <h4>Outreach Recommendations</h4>
            <p class="scraper-outreach">${_escapeHtml(lead.outreach_recommendations)}</p>
          </div>
        ` : ''}

        <!-- Meta -->
        <div class="scraper-modal-section scraper-modal-meta">
          <span>Source: ${_escapeHtml(lead.source_provider || 'Unknown')}</span>
          ${lead.category ? `<span>Category: ${_escapeHtml(lead.category)}</span>` : ''}
          ${lead.launch_date ? `<span>Launched: ${_escapeHtml(lead.launch_date.split('T')[0])}</span>` : ''}
          ${lead.pricing_model ? `<span>Pricing: ${_escapeHtml(lead.pricing_model)}</span>` : ''}
        </div>
      </div>
    </div>
  `;
}

function _escapeHtml(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
