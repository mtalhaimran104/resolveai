/*!
 * ResolveAI — Phase 1 front-end initialization.
 * Minimal static UI behaviour only. No API calls.
 */
(() => {
  'use strict';

  document.addEventListener('DOMContentLoaded', () => {
    console.log('ResolveAI dashboard ready.');
    initTooltips();
  });

  function initTooltips() {
    if (!window.bootstrap) return;
    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach((el) => {
      new window.bootstrap.Tooltip(el);
    });
  }
})();
