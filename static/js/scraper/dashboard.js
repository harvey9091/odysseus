/**
 * Scraper Dashboard — Stats widgets.
 */

export function render(container, stats) {
  if (!container) return;
  if (!stats) {
    container.innerHTML = '';
    return;
  }

  const widgets = [
    {
      label: 'Total Leads',
      value: stats.total_leads || 0,
      icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>',
    },
    {
      label: 'Qualified',
      value: stats.qualified_leads || 0,
      icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>',
      accent: 'green',
    },
    {
      label: 'Avg Score',
      value: stats.avg_affordability_score || 0,
      icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="20" x2="12" y2="10"/><line x1="18" y1="20" x2="18" y2="4"/><line x1="6" y1="20" x2="6" y2="16"/></svg>',
    },
    {
      label: 'Runs',
      value: stats.total_runs || 0,
      icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>',
    },
  ];

  container.innerHTML = widgets.map(w => `
    <div class="scraper-stat-card">
      <div class="scraper-stat-icon" ${w.accent ? `style="color: var(--green, #98c379)"` : ''}>${w.icon}</div>
      <div class="scraper-stat-value">${typeof w.value === 'number' ? w.value.toFixed(w.value % 1 ? 1 : 0) : w.value}</div>
      <div class="scraper-stat-label">${w.label}</div>
    </div>
  `).join('');
}
