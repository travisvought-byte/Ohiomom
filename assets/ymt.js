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

  // Search and "Show everything". This only hides and shows listings that are already on the page.
  // Nothing typed here is sent anywhere or kept.
  var finder = document.querySelector('[data-finder]');
  var rows = Array.prototype.slice.call(document.querySelectorAll('details.need'));
  var box = finder && finder.querySelector('input');
  var allButton = finder && finder.querySelector('[data-show-all]');
  var countLine = finder && finder.querySelector('[data-count]');
  var showAll = false;
  var searching = false;
  // Everyday words for the words the listings use.
  var ALSO = {
    homeless: ['shelter'], homelessness: ['shelter'], shelters: ['shelter'], apartment: ['rent', 'housing'],
    evicted: ['eviction'], evict: ['eviction'], landlord: ['eviction', 'rent'], section: ['voucher'],
    daycare: ['child care'], childcare: ['child care'], babysitter: ['child care'], preschool: ['head start'],
    stamps: ['snap'], ebt: ['snap'], groceries: ['snap', 'food'], formula: ['wic', 'breastfeeding'],
    abuse: ['domestic violence'], abused: ['domestic violence'], violence: ['domestic violence'], dv: ['domestic violence'],
    lawyer: ['legal'], attorney: ['legal'], divorce: ['legal'], custody: ['legal'],
    depressed: ['mental health'], depression: ['mental health', 'postpartum'], anxiety: ['mental health'],
    therapy: ['mental health'], counseling: ['mental health'], suicide: ['988'],
    electric: ['energy'], gas: ['energy'], heat: ['energy'], utilities: ['energy'], utility: ['energy'],
    insurance: ['coverage'], medicaid: ['coverage'], doctor: ['health center'], pregnant: ['pregnan', 'prenatal'],
    nursing: ['breastfeeding'], iep: ['school'], veteran: ['veterans'], military: ['veterans', 'military']
  };
  var cards = [];
  rows.forEach(function (row) {
    var head = row.querySelector('summary').textContent;
    Array.prototype.forEach.call(row.querySelectorAll('article.card'), function (card) {
      var text = ' ' + (card.textContent + ' ' + head).toLowerCase().replace(/[^a-z0-9]+/g, ' ');
      cards.push({ el: card, row: row, text: text, key: card.id.split('--').pop() });
    });
  });
  function countKeys(list) {
    var seen = {};
    list.forEach(function (c) { seen[c.key] = true; });
    return Object.keys(seen).length;
  }
  // A word matches where a word starts, so "rent" finds "rental" but not "parent".
  function matches(text, term) {
    var tries = [term].concat(ALSO[term] || []);
    if (term.length > 3 && term.slice(-1) === 's') { tries.push(term.slice(0, -1)); }
    return tries.some(function (word) { return text.indexOf(' ' + word) !== -1; });
  }
  function apply() {
    if (!finder) { return; }
    var terms = box.value.toLowerCase().split(/[^a-z0-9]+/).filter(function (t) { return t.length > 1 || /\d/.test(t); });
    var was = searching;
    searching = terms.length > 0;
    var hits = [];
    cards.forEach(function (c) {
      var ok = !searching || terms.every(function (t) { return matches(c.text, t); });
      c.el.hidden = !ok;
      if (ok) { hits.push(c); }
    });
    rows.forEach(function (row) {
      var any = hits.some(function (c) { return c.row === row; });
      row.hidden = searching && !any;
      if (searching) { row.open = any; } else if (was || showAll) { row.open = showAll; }
    });
    allButton.textContent = showAll ? 'Close all' : 'Show everything';
    allButton.setAttribute('aria-pressed', showAll ? 'true' : 'false');
    allButton.hidden = searching;
    var total = countKeys(cards);
    if (!searching) {
      countLine.textContent = total + ' listings in ' + rows.length + ' groups.';
    } else if (hits.length) {
      var n = countKeys(hits);
      countLine.textContent = n + ' of ' + total + ' listings match.';
    } else {
      countLine.textContent = 'Nothing matches. Try another word, or dial 211 and say what you need.';
    }
  }
  if (finder) {
    finder.hidden = false;
    box.addEventListener('input', apply);
    box.addEventListener('search', apply);
    allButton.addEventListener('click', function () {
      showAll = !showAll;
      rows.forEach(function (row) { row.open = showAll; });
      apply();
    });
    apply();
  }

  // Needs stay closed until one is asked for. A link that names a need (help.html#food-bills)
  // or a listing inside one opens that need and brings it into view. Two special addresses:
  // #everything opens every need, and #q=rent searches for a word.
  function openNamed() {
    var id = decodeURIComponent(window.location.hash.slice(1));
    if (finder && id === 'everything') {
      showAll = true;
      rows.forEach(function (row) { row.open = true; });
      apply();
      return;
    }
    if (finder && id.slice(0, 2) === 'q=') {
      box.value = id.slice(2).replace(/\+/g, ' ');
      apply();
      return;
    }
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

// Visit counter (GoatCounter, added November 19, 2026 at the owner's request). It sets no cookie and does not record
// who the visitor is. It sends only the page's path, never a search, ZIP code or anything typed (those stay in the
// page or after the #, which is not sent). The path carries the site name so these pages stay apart from the owner's
// other sites on the same counter. The referring address is cut to its site and path, as on the owner's other sites.
// The same lines are in assets/ymt.js, ohio/assets/site.js and assets/family-guide.js.
(function(){if(window.ymtCountLoaded)return;window.ymtCountLoaded=true;var h=location.hostname.replace(/^www\./,'');window.goatcounter={path:function(p){return '/'+h+p.replace(/\?.*$/,'');},referrer:function(){try{var u=new URL(document.referrer);return u.origin+u.pathname;}catch(e){return '';}}};var s=document.createElement('script');s.async=true;s.src='https://gc.zgo.at/count.js';s.setAttribute('data-goatcounter','https://travisvought.goatcounter.com/count');document.head.appendChild(s);})();
