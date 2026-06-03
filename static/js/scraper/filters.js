/**
 * Scraper Filters — Provider selection and filter controls.
 */

export function render(container, providerList, currentState, onChange) {
  if (!container) return;

  const selectedProviders = currentState.providers || ['hackernews', 'producthunt'];

  const providerChips = (providerList || []).map(p => {
    const isSelected = selectedProviders.includes(p.name);
    return `
      <label class="scraper-provider-chip ${isSelected ? 'selected' : ''}" data-provider="${p.name}">
        <input type="checkbox" ${isSelected ? 'checked' : ''} style="display:none">
        <span class="scraper-chip-name">${_formatProviderName(p.name)}</span>
      </label>
    `;
  }).join('');

  container.innerHTML = `
    <div class="scraper-filters">
      <div class="scraper-filter-row">
        <label class="scraper-filter-label">Providers</label>
        <div class="scraper-provider-list">${providerChips}</div>
      </div>
      <div class="scraper-filter-row">
        <label class="scraper-filter-label">Days Back</label>
        <select class="scraper-select" id="scraper-days-filter">
          <option value="3">Last 3 days</option>
          <option value="7" selected>Last 7 days</option>
          <option value="14">Last 14 days</option>
          <option value="30">Last 30 days</option>
        </select>
        <label class="scraper-filter-label">Min Score</label>
        <input type="number" class="scraper-input" id="scraper-min-score" placeholder="0" min="0" max="100" value="${currentState.min_score || ''}">
      </div>
    </div>
  `;

  // Wire events
  container.querySelectorAll('.scraper-provider-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      chip.classList.toggle('selected');
      _emitChange(container, onChange);
    });
  });

  container.querySelector('#scraper-days-filter')?.addEventListener('change', () => _emitChange(container, onChange));
  container.querySelector('#scraper-min-score')?.addEventListener('change', () => _emitChange(container, onChange));
}

function _emitChange(container, onChange) {
  if (!onChange) return;

  const selectedProviders = Array.from(
    container.querySelectorAll('.scraper-provider-chip.selected')
  ).map(c => c.dataset.provider);

  const daysBack = parseInt(container.querySelector('#scraper-days-filter')?.value || '7');
  const minScore = parseInt(container.querySelector('#scraper-min-score')?.value || '0') || null;

  onChange({
    providers: selectedProviders,
    days_back: daysBack,
    min_score: minScore,
  });
}

function _formatProviderName(name) {
  const names = {
    producthunt: 'Product Hunt',
    hackernews: 'Hacker News',
    peerlist: 'Peerlist',
    devhunt: 'DevHunt',
    indiehackers: 'Indie Hackers',
    betalist: 'BetaList',
    uneed: 'Uneed',
    alternativeto: 'AlternativeTo',
  };
  return names[name] || name.charAt(0).toUpperCase() + name.slice(1);
}
