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
  assert.equal(all(d, '.hero .tile').length, 6, 'six needs to choose from');
  assert.equal(all(d, 'main > section').length, 2, 'front page is the question and the help-now strip, nothing else');
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
checkNeeds('help.html', 7);
for (const f of fs.readdirSync('states').filter((f) => f.endsWith('.html'))) checkNeeds('states/' + f, 6);
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

// 5. The OhioMom front page: the question, the six needs and the area picker. Events and the poll live on their own pages.
{
  const d = new JSDOM(fs.readFileSync('ohio/index.html', 'utf8')).window.document;
  assert.equal(all(d, '.hero .tile').length, 6);
  assert.equal(all(d, '[data-events], [data-poll], .card, .event').length, 0, 'no events, polls or listings on the OhioMom front page');
  assert(d.querySelector('#place') && d.querySelector('[data-region-buttons]'), 'area picker stays');
  const fold = d.querySelector('details.mapfold');
  assert(fold && !fold.open && fold.querySelector('#map'), 'the map opens on request');
  assert.equal(all(d, 'main > section').length, 2);
}
console.log('PASS front pages show no listings, needs open only when chosen, cards fold their details');
