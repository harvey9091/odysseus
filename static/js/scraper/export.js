/**
 * Scraper Export — CSV export functionality.
 */

const API_BASE = window.location.origin;

export function showExportDialog(filters) {
  // Simple export — directly trigger download
  exportCSV(filters);
}

export async function exportCSV(filters = {}) {
  try {
    const params = new URLSearchParams();
    if (filters.min_score) params.set('min_score', filters.min_score);
    if (filters.provider) params.set('provider', filters.provider);

    const res = await fetch(`${API_BASE}/api/scraper/export?${params}`, {
      credentials: 'same-origin',
    });

    if (res.ok) {
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `scraper_leads_${new Date().toISOString().split('T')[0]}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } else {
      throw new Error('Export failed');
    }
  } catch (e) {
    console.error('Export failed:', e);
    alert('Export failed. Please try again.');
  }
}
