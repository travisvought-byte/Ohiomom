// The OhioMom map page (ohio/map.html, ohio/assets/ohio-map.js). It must read as a plain list with no script,
// load nothing from another site, and, with the script, put every place on the map in its own county, list
// them, filter them and find a county from a town or a ZIP code. Leaflet runs for real here; jsdom has no
// layout, so the map box is given a size.
const assert = require('assert');
const fs = require('fs');
const { JSDOM } = require('jsdom');

const page = fs.readFileSync('ohio/map.html', 'utf8');
const places = JSON.parse(fs.readFileSync('ohio/assets/map-places.json', 'utf8'));
const files = {};
for (const f of ['data.json', 'map.json', 'map-places.json', 'places.json']) files['assets/' + f] = fs.readFileSync('ohio/assets/' + f, 'utf8');
const tick = () => new Promise((r) => setTimeout(r, 0));

// ---- with no script at all
{
  const doc = new JSDOM(page).window.document;
  assert(doc.querySelector('[data-mapapp]').hidden, 'the map and its controls stay hidden until the script runs');
  assert(doc.querySelector('noscript'), 'a note says the list below is the same places');
  const counties = doc.querySelectorAll('#every-place details.mapcounty');
  assert.equal(counties.length, 88, 'every county has its part of the plain list');
  assert.equal(doc.querySelectorAll('#every-place .plainplaces li').length, places.places.length, 'every place is in the plain list');
  for (const d of counties) assert(d.querySelector('summary > h3'), 'each county row has a heading directly in its summary');
  for (const a of doc.querySelectorAll('#every-place .mapcounty a[href]')) {
    assert(!/^https?:/.test(a.getAttribute('href')), 'the plain list carries no web links, so the monthly link check stays small: ' + a.getAttribute('href'));
  }
  for (const a of doc.querySelectorAll('#every-place a[href^="tel:"]')) assert(/^tel:\d{10}$/.test(a.getAttribute('href')), a.getAttribute('href'));
  for (const s of doc.querySelectorAll('script[src], link[rel=stylesheet]')) {
    const src = s.getAttribute('src') || s.getAttribute('href');
    if (s.id === 'wix-site-script') continue; // the Wix script every OhioMom page carries for its forms
    assert(!/^(https?:)?\/\//.test(src), 'served from this site, not a CDN: ' + src);
  }
  assert(!/tile\.|openstreetmap|\{z\}/.test(fs.readFileSync('ohio/assets/ohio-map.js', 'utf8')), 'the map loads no tiles from anywhere');
  assert(!doc.getElementById('map') && !doc.getElementById('place'), 'nothing for the old area picker in site.js to take over');
  console.log('PASS The map page reads as a plain list without its script');
}

// ---- with the script
(async () => {
  const dom = new JSDOM(page, { url: 'https://example.org/ohio/map.html', runScripts: 'outside-only', pretendToBeVisual: true });
  const w = dom.window;
  const doc = w.document;
  w.matchMedia = () => ({ matches: false });
  Object.defineProperty(w.HTMLElement.prototype, 'clientWidth', { get() { return this.id === 'omap' || this.closest && this.closest('#omap') ? 600 : 0; } });
  Object.defineProperty(w.HTMLElement.prototype, 'clientHeight', { get() { return this.id === 'omap' || this.closest && this.closest('#omap') ? 560 : 0; } });
  const asked = [];
  w.fetch = (path) => { asked.push(path); return Promise.resolve({ ok: true, json: () => Promise.resolve(JSON.parse(files[path])) }); };
  w.eval(fs.readFileSync('assets/vendor/leaflet.js', 'utf8'));
  w.eval(fs.readFileSync('assets/vendor/leaflet.markercluster.js', 'utf8'));
  w.eval(fs.readFileSync('ohio/assets/ohio-map.js', 'utf8'));
  for (let i = 0; i < 20; i++) await tick();
  assert.deepEqual(asked.sort(), Object.keys(files).sort(), 'reads only this site\'s own files');
  assert(!doc.querySelector('[data-mapapp]').hidden, 'the map shows once its files load');

  const $ = (s) => doc.querySelector(s);
  const status = () => $('#mstatus').textContent;
  const upcoming = JSON.parse(files['assets/data.json']).events.filter((e) => (e.end || e.start) >= new Date().toISOString().slice(0, 10)).length;
  const total = places.places.length;
  assert.equal(doc.querySelectorAll('path.ocounty').length, 88, 'every county is drawn');
  assert.equal(doc.querySelectorAll('[data-map-kinds] button[aria-pressed="true"]').length, 5, 'five kinds, all on');
  assert.equal($('#mcounty').options.length, 89, 'a county box with every county');
  assert.equal($('#mhead').textContent, 'All of Ohio');
  assert(new RegExp('^' + (total + upcoming).toLocaleString('en-US').replace(',', ',?') + ' places in Ohio').test(status()) ||
    status().startsWith((total + upcoming).toLocaleString('en-US') + ' places'), 'counts everything: ' + status());
  assert.equal(doc.querySelectorAll('#mlist > li').length, 20, 'a short list at first');
  const icons = doc.querySelectorAll('.ocount, .ocluster');
  assert(icons.length > 0, 'count circles are on the map');
  for (const i of icons) {
    assert.equal(i.getAttribute('tabindex'), '0', 'a count circle can be reached with the keyboard');
    assert.equal(i.getAttribute('role'), 'button');
    assert(/places? in|County: /.test(i.querySelector('.sr').textContent), 'a count circle says what it counts');
  }

  // Show more adds the next 20 and moves focus to the first new one.
  $('#mmore').click();
  assert.equal(doc.querySelectorAll('#mlist > li').length, 40);
  assert.equal(doc.activeElement, doc.querySelectorAll('#mlist > li h3')[20], 'focus lands on the first new place');

  // The county box.
  const sel = $('#mcounty');
  sel.value = 'Knox';
  sel.dispatchEvent(new w.Event('change'));
  const knox = places.places.filter((p) => p[1] === 'Knox').length;
  assert.equal($('#mhead').textContent, 'Knox County');
  assert(status().includes(' in Knox County'), status());
  for (const li of doc.querySelectorAll('#mlist > li')) assert(li.querySelector('.osub').textContent.endsWith('Knox County'), 'only Knox County places');
  assert(doc.querySelectorAll('#mlist > li').length >= Math.min(20, knox));
  assert($('#mcountyinfo a[href="../county.html#39083"]'), 'links to the full county page');
  assert($('#mcountyinfo a[href="all.html#county=Knox"]'), 'links to the statewide help for the county');
  assert($('#mcountyinfo a[href="counties/knox.html"]'), 'links to the OhioMom county page where there is one');
  assert.equal(w.location.hash, '#county=Knox', 'the address keeps the county, so it can be shared');
  assert.equal(JSON.parse(w.localStorage.getItem('om.area')).c, 'Knox', 'remembered like the Near you page');
  assert(!$('#mreset').hidden, 'a way back to all of Ohio');

  // A kind chip turns a kind off.
  const health = $('[data-map-kinds] button[data-k="health"]');
  health.click();
  assert.equal(health.getAttribute('aria-pressed'), 'false');
  assert(![...doc.querySelectorAll('#mlist .okind')].some((k) => k.textContent === 'Health care'), 'no health care listed once it is off');
  health.click();

  // A town, a ZIP code and plain words in the search box.
  const q = $('#mq');
  const search = async (v) => { q.value = v; q.dispatchEvent(new w.Event('change')); await tick(); };
  await search('Sunbury');
  assert.equal($('#mhead').textContent, 'Delaware County', 'a town finds its county');
  assert(status().startsWith('Sunbury is in Delaware County.'), status());
  await search('45693');
  assert.equal($('#mhead').textContent, 'Adams County', 'a ZIP code finds its county');
  assert(status().startsWith('ZIP code 45693 is in Adams County'), status());
  await search('head start');
  assert.equal($('#mhead').textContent, 'All of Ohio', 'words search all of Ohio when the county came from a search');
  for (const li of doc.querySelectorAll('#mlist > li')) assert(/head start/i.test(li.textContent));
  await search('zzzz nothing like this');
  assert.equal(doc.querySelectorAll('#mlist > li').length, 0);
  assert(/^Nothing in Ohio matches/.test(status()), status());
  await search('');

  // A county chosen on the map with the keyboard.
  const circle = [...doc.querySelectorAll('.ocount, .ocluster')][0];
  circle.dispatchEvent(new w.KeyboardEvent('keypress', { key: 'Enter', keyCode: 13, bubbles: true }));
  await tick();
  assert($('#mhead').textContent !== 'All of Ohio' || doc.querySelectorAll('.ocluster').length, 'Enter on a circle opens its county or zooms in');

  // Nothing from the data is written as markup.
  const evil = JSON.parse(files['assets/map-places.json']);
  evil.places[0][2] = '<img src=x onerror=alert(1)>';
  evil.places[0][7] = 'javascript:alert(1)';
  const dom2 = new JSDOM(page, { url: 'https://example.org/ohio/map.html', runScripts: 'outside-only', pretendToBeVisual: true });
  const w2 = dom2.window;
  w2.matchMedia = w.matchMedia;
  Object.defineProperty(w2.HTMLElement.prototype, 'clientWidth', { get() { return 600; } });
  Object.defineProperty(w2.HTMLElement.prototype, 'clientHeight', { get() { return 560; } });
  w2.fetch = (path) => Promise.resolve({ ok: true, json: () => Promise.resolve(path.endsWith('map-places.json') ? evil : JSON.parse(files[path])) });
  w2.eval(fs.readFileSync('assets/vendor/leaflet.js', 'utf8'));
  w2.eval(fs.readFileSync('assets/vendor/leaflet.markercluster.js', 'utf8'));
  w2.eval(fs.readFileSync('ohio/assets/ohio-map.js', 'utf8'));
  for (let i = 0; i < 20; i++) await tick();
  const sel2 = w2.document.querySelector('#mcounty');
  sel2.value = evil.places[0][1];
  sel2.dispatchEvent(new w2.Event('change'));
  assert(!w2.document.querySelector('#mlist img'), 'a name is shown as text');
  assert(!w2.document.querySelector('#mlist a[href^="javascript"]'), 'only https websites are linked');
  assert(w2.document.querySelector('#mlist').textContent.includes('<img src=x'), 'the odd name still shows, as text');

  // If a file does not load, the plain list is all there is.
  const dom3 = new JSDOM(page, { url: 'https://example.org/ohio/map.html', runScripts: 'outside-only' });
  const w3 = dom3.window;
  w3.fetch = () => Promise.resolve({ ok: false, json: () => Promise.resolve({}) });
  w3.eval(fs.readFileSync('assets/vendor/leaflet.js', 'utf8'));
  w3.eval(fs.readFileSync('assets/vendor/leaflet.markercluster.js', 'utf8'));
  w3.eval(fs.readFileSync('ohio/assets/ohio-map.js', 'utf8'));
  for (let i = 0; i < 10; i++) await tick();
  assert(w3.document.querySelector('[data-mapapp]').hidden, 'no half-drawn map');
  assert(/did not load/.test(w3.document.querySelector('.hero').textContent), 'says the map did not load');
  console.log('PASS The map page draws every county, lists, filters and finds places, and fails safe');
})().catch((e) => { console.error(e); process.exit(1); });
