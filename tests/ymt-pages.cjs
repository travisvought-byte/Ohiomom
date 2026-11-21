// The pages show a little first and the rest when asked. Run: node tests/ymt-pages.cjs
const assert = require('node:assert/strict'), fs = require('node:fs'), { JSDOM } = require('jsdom');
const script = fs.readFileSync('assets/ymt.js', 'utf8');
function load(file, hash = '') {
  const dom = new JSDOM(fs.readFileSync(file, 'utf8'), { url: 'https://example.org/' + file + hash, runScripts: 'outside-only' });
  dom.window.eval(script);
  return { w: dom.window, d: dom.window.document };
}
const all = (d, sel) => [...d.querySelectorAll(sel)];

// 1. The front page asks one question and shows no listings.
{
  const { d } = load('index.html');
  assert.equal(all(d, '.card').length, 0, 'front page shows no listing cards');
  assert.equal(all(d, '.hero .tile').length, 9, 'Christmas help, seven needs and "See everything"');
  assert.equal(all(d, 'main > section').length, 2, 'front page is the question and the help-now strip, nothing else (the picture and its affirmation are inside the question)');
  assert(all(d, 'main > section')[1].matches('#now'), 'the help-now strip comes straight after the question');
  assert(d.querySelector('.hero .tile[href="help.html#housing"]'), 'housing and shelter is a choice of its own');
  const phones = all(d, '.phonecard');
  assert.equal(phones.length, 3);
  for (const a of phones) assert.match(a.getAttribute('href'), /^tel:/);
  assert.equal(d.querySelector('[data-state-pick]').options.length, 52);
  for (const t of all(d, '.hero .tile')) {
    const [page, frag] = t.getAttribute('href').split('#');
    assert(fs.existsSync(page), page);
    if (frag) assert(load(page).d.getElementById(frag), `${page}#${frag}`);
  }
}

// 2. A card is a name, one line and the buttons. Everything else is folded behind "More about this".
function checkCards(d, file) {
  for (const c of all(d, 'article.card')) {
    const kids = [...c.children].map((e) => e.tagName + (e.className ? '.' + e.className.split(' ')[0] : ''));
    const allowed = ['H3', 'P.short', 'P.textline', 'P.actions', 'DETAILS.more'];
    for (const k of kids) assert(allowed.includes(k), `${file} #${c.id}: unexpected ${k} outside "More about this"`);
    assert(c.querySelector(':scope > h3').textContent.trim(), `${file} #${c.id}: name`);
    assert(c.querySelector(':scope > p.short').textContent.trim().length > 20, `${file} #${c.id}: one line`);
    assert(c.querySelectorAll(':scope > p.actions a').length >= 1, `${file} #${c.id}: a way to act`);
    const more = c.querySelector(':scope > details.more');
    assert(more && !more.open, `${file} #${c.id}: details start closed`);
    assert(more.querySelector('p.src a'), `${file} #${c.id}: sources are in the details`);
    assert(more.textContent.includes('Next step:'), `${file} #${c.id}: next step is in the details`);
    assert(more.querySelector('summary').textContent.includes(c.querySelector('h3').textContent.trim()), `${file} #${c.id}: summary names the listing for screen readers`);
  }
}

// 3. Needs are closed rows until one is chosen.
function checkNeeds(file, count) {
  const { d } = load(file);
  const needs = all(d, 'details.need');
  assert.equal(needs.length, count, `${file}: ${count} needs`);
  for (const n of needs) {
    assert(!n.open, `${file} #${n.id}: closed until chosen`);
    assert(n.querySelector('summary h2').textContent.trim(), `${file} #${n.id}: named`);
    assert(n.querySelectorAll('article.card').length >= 1, `${file} #${n.id}: has listings`);
  }
  assert.equal(all(d, 'article.card').filter((c) => !c.closest('details.need')).length, 0, `${file}: no listing outside a need`);
  checkCards(d, file);
}
checkNeeds('help.html', 9);
for (const f of fs.readdirSync('states').filter((f) => f.endsWith('.html'))) checkNeeds('states/' + f, 9);
// Christmas help: four needs and the Toys for Tots campaigns of every state.
checkNeeds('christmas.html', 5);
checkCards(load('connect.html').d, 'connect.html');

// 4. Choosing a need on the front page opens that need, and only that one.
{
  const { d } = load('help.html', '#food-bills');
  assert.deepEqual(all(d, 'details.need').filter((n) => n.open).map((n) => n.id), ['food-bills']);
  assert.equal(all(d, '#food-bills details.more').filter((m) => m.open).length, 0, 'cards inside stay short');
}
// A link to one listing opens the need that holds it.
{
  const { d } = load('help.html', '#us-wic');
  assert.deepEqual(all(d, 'details.need').filter((n) => n.open).map((n) => n.id), ['food-bills']);
}
// Changing the address opens the next one; nothing she opened is closed behind her.
{
  const { w, d } = load('help.html', '#food-bills');
  w.location.hash = '#take-care';
  w.dispatchEvent(new w.HashChangeEvent('hashchange'));
  assert.deepEqual(all(d, 'details.need').filter((n) => n.open).map((n) => n.id).sort(), ['food-bills', 'take-care']);
}
// With no need named, everything stays closed.
assert.equal(all(load('help.html').d, 'details[open]').length, 0);
// A printed page shows everything, then goes back to how it was.
{
  const { w, d } = load('help.html', '#food-bills');
  w.dispatchEvent(new w.Event('beforeprint'));
  assert.equal(all(d, 'details:not([open])').length, 0);
  w.dispatchEvent(new w.Event('afterprint'));
  assert.deepEqual(all(d, 'details[open]').map((n) => n.id), ['food-bills']);
}

// 4b. Search and "Show everything": every listing can be reached from one box, and nothing leaves the page.
{
  const type = (w, d, text) => { const q = d.getElementById('q'); q.value = text; q.dispatchEvent(new w.Event('input')); };
  const shown = (d) => all(d, 'article.card').filter((c) => !c.hidden && !c.closest('details.need').hidden);
  const { w, d } = load('states/oh.html');
  const finder = d.querySelector('[data-finder]');
  assert(!finder.hidden, 'the script shows the search bar');
  const total = new Set(all(d, 'article.card').map((c) => c.id.split('--').pop())).size;
  assert.equal(d.querySelector('[data-count]').textContent, `${total} listings in 9 groups.`);
  assert(total >= 44, 'a state page holds every listing for that state');
  // A word opens the needs that hold a match and hides the rest.
  type(w, d, 'shelter');
  assert(shown(d).length >= 5, 'shelter finds several listings');
  assert(shown(d).some((c) => c.id === 'us-find-shelter') && shown(d).some((c) => c.id === 'oh-shelters'));
  for (const n of all(d, 'details.need')) assert.equal(n.open, !n.hidden, `${n.id}: open exactly when it holds a match`);
  assert.match(d.querySelector('[data-count]').textContent, /^\d+ of \d+ listings match\.$/);
  assert(d.querySelector('[data-show-all]').hidden, 'no "Show everything" while searching');
  // Words match where a word starts: "rent" is not found inside "parent".
  type(w, d, 'rent');
  assert(!shown(d).some((c) => c.id === 'us-p2p-usa'), 'Parent to Parent is not a match for rent');
  assert(shown(d).some((c) => c.id === 'oh-housing-hud'));
  // Everyday words reach the listing that uses another word.
  type(w, d, 'homeless');
  assert(shown(d).some((c) => c.id === 'us-find-shelter'));
  type(w, d, 'food stamps');
  assert(shown(d).some((c) => c.id === 'oh-snap'));
  type(w, d, 'daycare');
  assert(shown(d).some((c) => c.id === 'oh-childcare'));
  // Nothing found says so and points to a person.
  type(w, d, 'qqqqzz');
  assert.equal(shown(d).length, 0);
  assert.match(d.querySelector('[data-count]').textContent, /Nothing matches.*211/);
  // Clearing the box puts the page back: every listing there, every need closed.
  type(w, d, '');
  assert.equal(all(d, 'article.card').filter((c) => c.hidden).length, 0);
  assert.equal(all(d, 'details.need').filter((n) => n.open || n.hidden).length, 0);
  // "Show everything" opens every need, and closes them again.
  const button = d.querySelector('[data-show-all]');
  button.click();
  assert.equal(all(d, 'details.need').filter((n) => !n.open).length, 0);
  assert.equal(button.getAttribute('aria-pressed'), 'true');
  assert.equal(button.textContent, 'Close all');
  button.click();
  assert.equal(all(d, 'details.need').filter((n) => n.open).length, 0);
  // Two addresses do the same from a link: #everything and #q=word.
  assert.equal(all(load('help.html', '#everything').d, 'details.need').filter((n) => !n.open).length, 0);
  const linked = load('help.html', '#q=diapers');
  assert.equal(linked.d.getElementById('q').value, 'diapers');
  assert(shown(linked.d).some((c) => c.id === 'us-diaper-banks'));
  // The script never talks to a server and never stores anything.
  for (const banned of ['fetch(', 'XMLHttpRequest', 'sendBeacon', 'document.cookie', 'localStorage', 'sessionStorage']) assert(!script.includes(banned), banned);
  // Without the script the search bar stays hidden, so there is never a box that does nothing.
  assert(new JSDOM(fs.readFileSync('help.html', 'utf8')).window.document.querySelector('[data-finder]').hidden);
}

// 5. The OhioMom front page: the question, eight things to choose from, "See everything" and the area picker.
// Events and the poll live on their own pages.
{
  const d = new JSDOM(fs.readFileSync('ohio/index.html', 'utf8')).window.document;
  assert.equal(all(d, '.hero .tile').length, 10, 'eight needs, the holiday page and "See everything"');
  assert.equal(all(d, '[data-events], [data-poll], .card, .event').length, 0, 'no events, polls or listings on the OhioMom front page');
  assert(d.querySelector('#place') && d.querySelector('[data-region-buttons]'), 'area picker stays');
  const fold = d.querySelector('details.mapfold');
  assert(fold && !fold.open && fold.querySelector('#map'), 'the map opens on request');
  assert.equal(all(d, 'main > section').length, 2);
}
console.log('PASS front pages show no listings, needs open only when chosen, cards fold their details');

// 6. The inner OhioMom pages follow the same rule: an index of closed rows, short cards, the rest when asked.
const ohioScript = fs.readFileSync('ohio/assets/site.js', 'utf8');
const ohioData = JSON.parse(fs.readFileSync('ohio/assets/data.json', 'utf8'));
// The feedback script is a module; without its one export keyword it runs as a plain script here.
const listenScript = fs.readFileSync('ohio/assets/listen.js', 'utf8').replace('export async function send', 'async function send');
assert(!/^\s*(import|export)\s/m.test(listenScript));
const tick = () => new Promise((r) => setTimeout(r, 0));
// Every event is moved to today or later, so this test does not start failing as the real dates pass.
function futureData() {
  const data = JSON.parse(JSON.stringify(ohioData));
  const day = (n) => { const t = new Date(Date.now() + n * 864e5); return t.getFullYear() + '-' + ('0' + (t.getMonth() + 1)).slice(-2) + '-' + ('0' + t.getDate()).slice(-2); };
  data.events.forEach((e, i) => { e.start = day(i); delete e.end; });
  return data;
}
async function loadOhio(file, hash = '') {
  const dom = new JSDOM(fs.readFileSync(file, 'utf8'), { url: 'https://example.org/' + file + hash, runScripts: 'outside-only' });
  const w = dom.window;
  w.matchMedia = () => ({ matches: false });
  w.fetch = (url) => Promise.resolve({ json: () => Promise.resolve(/map\.json$/.test(url) ? JSON.parse(fs.readFileSync('ohio/assets/map.json', 'utf8')) : futureData()) });
  w.eval(ohioScript);
  w.eval(listenScript);
  for (let i = 0; i < 6; i++) await tick();
  return { w, d: w.document };
}
function checkOhioCards(d, file) {
  for (const c of all(d, 'article.card')) {
    const name = c.querySelector(':scope > h3').textContent.trim();
    const kids = [...c.children].map((e) => e.tagName + (e.className ? '.' + e.className.split(' ')[0] : ''));
    for (const k of kids) assert(['P.tags', 'H3', 'P.short', 'P.actions', 'DETAILS.more'].includes(k), `${file} "${name}": unexpected ${k} outside "More about this"`);
    assert(c.querySelector(':scope > p.short').textContent.trim().length > 15, `${file} "${name}": one line`);
    assert(c.querySelector(':scope > p.short').textContent.length <= 220, `${file} "${name}": the one line is short`);
    assert(c.querySelectorAll(':scope > p.actions a').length >= 1, `${file} "${name}": a way to act`);
    const more = c.querySelector(':scope > details.more');
    assert(more && !more.open, `${file} "${name}": details start closed`);
    assert(more.textContent.includes('Next step:'), `${file} "${name}": next step is in the details`);
    assert(more.querySelector('p.meta').textContent.includes('Checked'), `${file} "${name}": the checked date is in the details`);
    assert(more.querySelector('summary').textContent.includes(name), `${file} "${name}": summary names the listing for screen readers`);
  }
}
function checkOhioRows(d, file, min) {
  const rows = all(d, 'details.need');
  assert(rows.length >= min, `${file}: at least ${min} rows, found ${rows.length}`);
  for (const r of rows) {
    assert(!r.open, `${file} #${r.id}: closed until chosen`);
    assert(r.id && d.querySelectorAll('#' + r.id).length === 1, `${file}: every row can be linked to`);
    assert(r.querySelector('summary h2').textContent.trim(), `${file} #${r.id}: named`);
    assert(r.querySelectorAll('article.card').length >= 1, `${file} #${r.id}: has listings`);
  }
  assert.equal(all(d, 'article.card').filter((c) => !c.closest('details.need')).length, 0, `${file}: no listing outside a row`);
}
const staticDoc = (file) => new JSDOM(fs.readFileSync(file, 'utf8')).window.document;
const counties = fs.readdirSync('ohio/counties').filter((f) => f.endsWith('.html')).map((f) => 'ohio/counties/' + f);
assert(counties.length >= 4);
for (const f of counties) {
  const d = staticDoc(f);
  checkOhioRows(d, f, 8);
  checkOhioCards(d, f);
  assert(d.getElementById('q'), `${f}: search stays`);
  assert(!d.querySelector('nav[aria-label="Sections"]'), `${f}: the rows are the index, so there is no second one`);
}
for (const [f, rows] of [['ohio/help/pregnancy-baby.html', 3], ['ohio/wellbeing.html', 2], ['ohio/help/housing.html', 3]]) {
  const d = staticDoc(f);
  checkOhioRows(d, f, rows);
  checkOhioCards(d, f);
}
for (const f of ['ohio/help/bills.html', 'ohio/help/single-parent.html']) {
  const d = staticDoc(f);
  assert(all(d, 'article.card').length >= 3 && all(d, 'article.card').length <= 6, `${f}: a handful of short cards`);
  checkOhioCards(d, f);
}
// The lines that must never be more than one tap away are in the open, and each one is a listing on the same page.
{
  const d = staticDoc('ohio/wellbeing.html');
  const phones = all(d, '.phonecard');
  assert.equal(phones.length, 3);
  const listed = all(d, 'article.card a.call').map((a) => a.getAttribute('href'));
  for (const a of phones) {
    assert.match(a.getAttribute('href'), /^tel:\d+$/);
    assert(listed.includes(a.getAttribute('href')), `wellbeing: ${a.textContent} is also a full listing below`);
    assert(a.textContent.includes(a.getAttribute('href').slice(4).slice(-4)), 'the number shown is the number dialed');
  }
  assert(d.querySelector('details.need.urgent#safe'), 'the crisis row keeps its address and its red edge');
  // A domestic violence line is in the open here, so the way to leave the page quickly is in the open with it.
  const exit = d.querySelector('[data-exit]');
  assert(exit && !exit.closest('details'), 'wellbeing: the quick exit is not behind a tap');
  assert(exit.closest('section').querySelector('.phonecard'), 'wellbeing: the quick exit sits with the phone cards');
}
// On a county page nothing about safety at home shows until that row is opened, and the row carries its own quick exit.
for (const f of counties) {
  const safety = staticDoc(f).querySelector('details.need.urgent');
  assert(safety && safety.querySelector('[data-exit]'), `${f}: the safety row has a quick exit inside it`);
}

// 7. What a screen reader relies on: one banner, one main, nothing outside a landmark, headings that never skip a level,
// and row headings that are direct children of their <summary> (a heading inside a <span> is not valid HTML).
function checkStructure(d, file) {
  assert.equal(all(d, 'body > header').length, 1, `${file}: one banner`);
  assert.equal(all(d, 'header').length, 1, `${file}: no second header`);
  assert.equal(all(d, 'main').length, 1, `${file}: one main`);
  for (const el of d.body.children) {
    const ok = ['HEADER', 'MAIN', 'FOOTER', 'SCRIPT'].includes(el.tagName) || el.matches('a.skip');
    assert(ok, `${file}: <${el.tagName.toLowerCase()} class="${el.className}"> sits outside the page landmarks`);
  }
  let last = 0;
  for (const h of all(d, 'h1, h2, h3, h4, h5, h6')) {
    const level = +h.tagName[1];
    assert(level <= last + 1, `${file}: "${h.textContent.trim().slice(0, 40)}" jumps from h${last} to h${level}`);
    last = level;
  }
  for (const h of all(d, 'summary h2, summary h3')) assert.equal(h.parentElement.tagName, 'SUMMARY', `${file}: a row heading is a direct child of its summary`);
  for (const sm of all(d, 'summary')) for (const c of sm.children) assert(!['DIV', 'P', 'UL', 'SECTION'].includes(c.tagName), `${file}: a block element inside a summary`);
}
const staticPages = ['index.html', 'help.html', 'connect.html', 'states.html', 'county.html', 'about.html', 'privacy.html', 'yoga.html', 'report.html', '404.html', 'family-guide.html']
  .concat(fs.readdirSync('states').filter((f) => f.endsWith('.html')).map((f) => 'states/' + f))
  .concat(fs.readdirSync('ohio').filter((f) => f.endsWith('.html')).map((f) => 'ohio/' + f))
  .concat(fs.readdirSync('ohio/help').filter((f) => f.endsWith('.html')).map((f) => 'ohio/help/' + f))
  .concat(counties)
  .filter((f) => !/http-equiv="refresh"/i.test(fs.readFileSync(f, 'utf8')));
assert(staticPages.length > 70);
for (const f of staticPages) checkStructure(staticDoc(f), f);
console.log(`PASS structure: one banner, one main, landmarks and heading order on ${staticPages.length} pages`);

(async () => {
  // The pages that fill themselves in keep the same structure once they have.
  for (const [f, hash] of [['ohio/events.html', ''], ['ohio/connect.html', ''], ['ohio/near-you.html', '#central']]) {
    const { d } = await loadOhio(f, hash);
    checkStructure(d, f + hash);
    assert(d.querySelector('main > .helpful'), `${f}: the "did you find it" question is inside <main>`);
  }
  // A county page: a link to a section opens that row; search opens the rows that match and puts the rest away.
  {
    const { w, d } = await loadOhio('ohio/counties/morrow.html', '#legal');
    assert.deepEqual(all(d, 'details.need').filter((n) => n.open).map((n) => n.id), ['legal']);
    const q = d.getElementById('q');
    q.value = 'wic';
    q.dispatchEvent(new w.Event('input', { bubbles: true }));
    const open = all(d, 'details.need').filter((n) => n.open);
    assert(open.length >= 1 && open.every((n) => /wic/i.test(n.textContent)), 'search opens only rows with a match');
    assert.equal(all(d, 'details.need').filter((n) => !n.open && !n.hidden).length, 0, 'rows without a match are put away');
    q.value = '';
    q.dispatchEvent(new w.Event('input', { bubbles: true }));
    assert.equal(all(d, 'details.need').filter((n) => n.open || n.hidden).length, 0, 'clearing the search closes everything again');
    w.dispatchEvent(new w.Event('beforeprint'));
    assert.equal(all(d, 'details:not([open])').length, 0, 'a printed page shows everything');
    w.dispatchEvent(new w.Event('afterprint'));
    assert.equal(all(d, 'details[open]').length, 0);
  }
  // Events: the next six, the rest when asked, and short again after choosing a region.
  {
    const { w, d } = await loadOhio('ohio/events.html');
    const shown = () => all(d, '[data-events] .event').length;
    const total = ohioData.events.length;
    assert(total > 8);
    assert.equal(shown(), 6);
    assert.equal(all(d, '.event details.more').filter((m) => m.open).length, 0, 'times, places and prices wait behind "When, where and cost"');
    const button = d.querySelector('[data-show-all]');
    assert.equal(button.textContent, `Show all ${total} events`);
    button.dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
    assert.equal(shown(), total);
    assert(!d.querySelector('[data-show-all]'));
    d.querySelector('[data-region-chips] button[data-r="central"]').dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
    const central = ohioData.events.filter((e) => ohioData.counties[e.county][0] === 'central').length;
    assert.equal(shown(), central > 8 ? 6 : central, 'a new choice starts short again');
    const cal = d.getElementById('calendars');
    assert(cal && !cal.open && cal.querySelectorAll('article.card').length >= 1, 'local calendars open on request');
    checkOhioCards(d, 'ohio/events.html');
  }
  // Meet moms: four closed rows of short cards.
  {
    const { d } = await loadOhio('ohio/connect.html');
    const rows = all(d, 'details.need');
    assert.equal(rows.length, Object.keys(ohioData.groupKinds).length);
    assert.equal(rows.filter((n) => n.open).length, 0);
    assert.equal(all(d, 'article.card').length, ohioData.groups.length);
    assert.equal(all(d, 'article.card').filter((c) => !c.closest('details.need')).length, 0);
    checkOhioCards(d, 'ohio/connect.html');
  }
  // Near you: nothing until an area is picked, then an index for that area and nothing open.
  {
    const { w, d } = await loadOhio('ohio/near-you.html');
    const panel = d.querySelector('[data-area-panel]');
    assert(panel.hidden, 'no area picked yet');
    d.querySelector('[data-region-buttons] button[data-r="central"]').dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
    assert(!panel.hidden);
    assert.equal(d.querySelector('[data-area-name]').textContent, 'Central Ohio');
    assert.equal(d.querySelector('#coming-up h2').textContent, 'Coming up in Central Ohio');
    assert.equal(all(panel, 'details.need').length, 1 + Object.keys(ohioData.groupKinds).length);
    assert.equal(all(panel, 'details[open]').length, 0, 'nothing is open until she asks');
    assert.equal(all(panel, '.event, article.card').filter((c) => !c.closest('details.need')).length, 0, 'no event or listing outside a row');
    assert(all(panel, '#coming-up .event').length <= 6);
  }
  console.log('PASS OhioMom inner pages: closed rows, short cards, six events first, search and links open the right row');
})().catch((e) => { console.error(e); process.exit(1); });
