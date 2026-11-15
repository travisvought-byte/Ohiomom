// Yoga Mom Talk: small helpers. No network requests, no storage, no tracking.
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
  // Needs stay closed until one is asked for. A link that names a need (help.html#food-bills)
  // or a listing inside one opens that need and brings it into view.
  function openNamed() {
    var id = decodeURIComponent(window.location.hash.slice(1));
    var el = id && document.getElementById(id);
    if (!el) { return; }
    for (var node = el; node; node = node.parentElement) {
      if (node.tagName === 'DETAILS') { node.open = true; }
    }
    if (el.scrollIntoView) { el.scrollIntoView(); }
  }
  window.addEventListener('hashchange', openNamed);
  openNamed();
  // A printed page shows everything.
  window.addEventListener('beforeprint', function () {
    document.querySelectorAll('details:not([open])').forEach(function (d) {
      d.setAttribute('data-print-opened', '');
      d.open = true;
    });
  });
  window.addEventListener('afterprint', function () {
    document.querySelectorAll('details[data-print-opened]').forEach(function (d) {
      d.removeAttribute('data-print-opened');
      d.open = false;
    });
  });
})();
