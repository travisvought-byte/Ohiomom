// Yoga Mom Talk: two small helpers. No network requests, no storage, no tracking.
(function () {
  'use strict';
  // "Leave this site": replace this page in history so Back does not return to it.
  document.querySelectorAll('[data-exit]').forEach(function (el) {
    el.addEventListener('click', function (e) {
      e.preventDefault();
      window.location.replace(el.getAttribute('href'));
    });
  });
  // State picker: jump straight to the chosen state's page.
  document.querySelectorAll('[data-state-pick]').forEach(function (sel) {
    sel.addEventListener('change', function () {
      if (sel.value) { window.location.href = sel.value; }
    });
  });
})();
