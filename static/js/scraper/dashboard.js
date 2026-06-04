/**
 * Scraper Dashboard — Stats widgets and system metrics bar.
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

export function renderMetrics(container, metrics) {
  if (!container) return;
  if (!metrics) {
    container.innerHTML = '';
    return;
  }

  const cpuColor = metrics.cpu_percent > 70 ? 'var(--red, #e06c75)' : 'var(--fg-muted, #888)';
  const ramColor = metrics.ram_percent > 70 ? 'var(--red, #e06c75)' : 'var(--fg-muted, #888)';

  container.innerHTML = `
    <div class="scraper-metrics-bar">
      <div class="scraper-metric">
        <span class="scraper-metric-icon">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="4" width="16" height="16" rx="2"/><path d="M9 9h6v6H9z"/></svg>
        </span>
        <span class="scraper-metric-label">CPU</span>
        <span class="scraper-metric-value" style="color:${cpuColor}">${metrics.cpu_percent.toFixed(0)}%</span>
      </div>
      <div class="scraper-metric">
        <span class="scraper-metric-icon">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 19a4 4 0 0 1-4-4 4 4 0 0 1 4-4h.5a4 4 0 0 1 4 4 4 4 0 0 1-4 4H6z"/><path d="M12 19V5"/></svg>
        </span>
        <span class="scraper-metric-label">RAM</span>
        <span class="scraper-metric-value" style="color:${ramColor}">${metrics.ram_percent.toFixed(0)}%</span>
      </div>
      <div class="scraper-metric">
        <span class="scraper-metric-icon">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
        </span>
        <span class="scraper-metric-label">Threads</span>
        <span class="scraper-metric-value">${metrics.active_workers}/${metrics.max_workers}</span>
      </div>
      <div class="scraper-metric">
        <span class="scraper-metric-icon">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
        </span>
        <span class="scraper-metric-label">Leads</span>
        <span class="scraper-metric-value">${metrics.total_leads || 0} saved</span>
      </div>
      <div class="scraper-metric scraper-metric-status">
        <span class="scraper-status-dot ${metrics.status === 'running' ? 'active' : ''}"></span>
        <span class="scraper-metric-value">${metrics.status}</span>
      </div>
    </div>
  `;
}
