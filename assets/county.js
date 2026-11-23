// Yoga Mom Talk: find your county. Every county has its own page (states/<state>/<county>.html, written by
// scripts/ymt_build.py). This script only finds it: by state and county, by ZIP code, or by an old county.html#<code>
// address, and then opens that page.
// Only files from this site are fetched. No third parties, no storage, no tracking. Nothing typed here is saved.
(function () {
  'use strict';
  var app = document.getElementById('county-app');
  var picker = document.querySelector('[data-county-find]');
  var stateSel = document.getElementById('cstate');
  var countySel = document.getElementById('ccounty');
  var zipBox = document.getElementById('zip');
  var msg = document.getElementById('cmsg');
  var title = document.getElementById('ctitle');
  var lede = document.getElementById('clede');
  if (!app || !picker || !stateSel || !countySel || !zipBox || !window.fetch || !window.Promise) { return; }

  var DATA = 'assets/us/';
  var HOME_TITLE = title.textContent;
  var HOME_LEDE = lede.textContent;
  var HOME_DOC = document.title;
  var STATES = {};      // 'oh': {name: 'Ohio', fips: '39'}
  var BY_FIPS = {};     // '39': 'oh'
  Array.prototype.forEach.call(stateSel.options, function (o) {
    if (o.value) { STATES[o.value] = { name: o.textContent, fips: o.getAttribute('data-fips') }; BY_FIPS[o.getAttribute('data-fips')] = o.value; }
  });
  var shards = {};
  var zips = {};
  var turn = 0;         // a later choice cancels the page an earlier one was still loading

  // ---- small helpers. Text is always put in with textContent, never as markup.
  function h(tag, props, kids) {
    var node = document.createElement(tag);
    Object.keys(props || {}).forEach(function (k) {
      if (k === 'text') { node.textContent = props[k]; } else { node.setAttribute(k, props[k]); }
    });
    (kids || []).forEach(function (kid) {
      if (kid) { node.appendChild(typeof kid === 'string' ? document.createTextNode(kid) : kid); }
    });
    return node;
  }
  function count(n, one, many) { return n + ' ' + (n === 1 ? one : many); }
  function fetchJson(url) {
    return fetch(url, { credentials: 'omit', referrerPolicy: 'no-referrer' }).then(function (r) {
      if (!r.ok) { throw new Error('HTTP ' + r.status); }
      return r.json();
    });
  }
  function loadShard(st) {
    if (!shards[st]) { shards[st] = fetchJson(DATA + st + '.json'); }
    return shards[st].catch(function (e) { delete shards[st]; throw e; });
  }
  function loadZips(d) {
    if (!zips[d]) { zips[d] = fetchJson(DATA + 'z' + d + '.json'); }
    return zips[d].catch(function (e) { delete zips[d]; throw e; });
  }
  function say(text) { msg.textContent = text; }
  // The same rule as county_slug in scripts/ymt_build.py.
  function slug(name) {
    return String(name).normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
  }
  function countyPage(code, name) { return 'states/' + code + '/' + slug(name) + '.html'; }
  function byName(shard) {
    return Object.keys(shard.c).sort(function (a, b) { return shard.c[a].n < shard.c[b].n ? -1 : 1; });
  }

  // ---- a state's counties, each a link to its page
  function showState(shard, code) {
    var stName = STATES[code].name;
    var list = h('ul', { 'class': 'statelist' });
    byName(shard).forEach(function (fips) {
      list.appendChild(h('li', {}, [h('a', { href: countyPage(code, shard.c[fips].n), text: shard.c[fips].n })]));
    });
    app.textContent = '';
    app.appendChild(h('section', { 'class': 'wrap' }, [h('h2', { text: count(Object.keys(shard.c).length, 'county', 'counties') + ' in ' + stName }), list,
      h('p', { 'class': 'note' }, [h('a', { href: 'states/' + code + '.html', text: 'See all of ' + stName + '\'s help' })])]));
    title.textContent = stName + ' counties';
    lede.textContent = 'Pick your county.';
    document.title = stName + ' counties: help for moms | ' + HOME_DOC.split('|').pop().trim();
    syncPicker(shard, code, '');
  }

  function showHome() {
    app.textContent = '';
    title.textContent = HOME_TITLE;
    lede.textContent = HOME_LEDE;
    document.title = HOME_DOC;
  }

  function problem(code) {
    app.textContent = '';
    var p = h('p', {}, ['We could not load that list just now. Please try again in a moment.']);
    if (code && STATES[code]) {
      p.appendChild(document.createTextNode(' You can also '));
      p.appendChild(h('a', { href: 'states/' + code + '.html', text: 'open the ' + STATES[code].name + ' page' }));
      p.appendChild(document.createTextNode('.'));
    }
    app.appendChild(h('section', { 'class': 'wrap' }, [p]));
  }

  // ---- the three ways to choose
  function fillCounties(shard, selected) {
    countySel.textContent = '';
    countySel.appendChild(h('option', { value: '', text: 'Choose your county' }));
    byName(shard).forEach(function (fips) {
      var o = h('option', { value: fips, text: shard.c[fips].n });
      if (fips === selected) { o.selected = true; }
      countySel.appendChild(o);
    });
    countySel.disabled = false;
  }
  function syncPicker(shard, code, fips) {
    stateSel.value = code;
    if (countySel.getAttribute('data-state') !== code) { fillCounties(shard, fips); countySel.setAttribute('data-state', code); }
    countySel.value = fips;
  }

  // county.html#39117 (a county's code) opens that county's page; county.html#oh lists Ohio's counties.
  function route() {
    var hash = '';
    try { hash = decodeURIComponent(window.location.hash.slice(1)); } catch (e) { hash = ''; }
    var mine = ++turn;
    var code = '';
    if (/^\d{5}$/.test(hash)) { code = BY_FIPS[hash.slice(0, 2)] || ''; }
    else if (/^[a-z]{2}$/.test(hash) && STATES[hash]) { code = hash; }
    if (!code) { showHome(); return; }
    loadShard(code).then(function (shard) {
      if (mine !== turn) { return; }
      if (hash.length === 5 && shard.c[hash]) {
        say('Opening ' + shard.c[hash].n + '…');
        window.location.replace(countyPage(code, shard.c[hash].n));
      }
      else if (hash.length === 2) { showState(shard, code); }
      else { showHome(); say('We do not have a county with that code.'); }
    }).catch(function () { if (mine === turn) { problem(code); } });
  }

  stateSel.addEventListener('change', function () {
    var code = stateSel.value;
    countySel.disabled = true;
    countySel.removeAttribute('data-state');
    if (!code) { countySel.textContent = ''; countySel.appendChild(h('option', { value: '', text: 'Choose a state first' })); return; }
    window.location.hash = code;
  });
  countySel.addEventListener('change', function () {
    if (countySel.value) { window.location.hash = countySel.value; }
  });
  function lookup() {
    var z = zipBox.value.replace(/\D/g, '');
    if (z.length !== 5) { say(z.length ? 'A ZIP code has five digits.' : ''); return; }
    say('Looking up ' + z + '…');
    loadZips(z.charAt(0)).then(function (table) {
      if (table[z]) { say(''); window.location.hash = table[z]; }
      else { say('We could not match that ZIP code to a county. Choose your state and county instead.'); }
    }).catch(function () { say('We could not look that up just now. Choose your state and county instead.'); });
  }
  zipBox.addEventListener('input', function () { if (zipBox.value.replace(/\D/g, '').length === 5) { lookup(); } });
  zipBox.addEventListener('keydown', function (e) { if (e.key === 'Enter') { lookup(); } });
  zipBox.addEventListener('search', lookup);

  picker.hidden = false;
  window.addEventListener('hashchange', route);
  route();
})();
