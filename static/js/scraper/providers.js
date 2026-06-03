/**
 * Scraper Providers — Provider info and selection UI.
 */

// Re-export from filters.js for now — providers module mainly provides data
export function render(container, providers, state, onChange) {
  // Delegate to filters module for the filter bar
  // This module is reserved for future provider config UI
  const filters = import('./filters.js').then(f => f.render(container, providers, state, onChange));
}
