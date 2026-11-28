// The family guide: a question first, a short list when asked, the rest in closed rows. Run: node tests/family-guide.cjs
const assert = require('node:assert/strict'), fs = require('node:fs'), { JSDOM } = require('jsdom');
const html = fs.readFileSync('family-guide.html', 'utf8'), script = fs.readFileSync('assets/family-guide.js', 'utf8');
function load(q = '') {
  const dom = new JSDOM(html, { url: 'https://example.org/family-guide.html' + q, runScripts: 'outside-only' });
  const w = dom.window; w.print = () => {}; w.eval(script);
  const d = w.document, $ = (id) => d.getElementById(id);
  const set = (id, value) => { $(id).value = value; $(id).dispatchEvent(new w.Event('change')); };
  const click = (el) => el.dispatchEvent(new w.MouseEvent('click', { bubbles: true, cancelable: true }));
  const all = (sel) => [...d.querySelectorAll(sel)];
  // "In view" here means: the list is showing, the listing passes the filters, and it is not held back by the six-first cut.
  const inView = () => $('results').classList.contains('chosen') ? all('#cards .resource').filter((c) => !c.hidden && !c.classList.contains('capped')) : [];
  return { w, d, $, set, click, all, inView };
}

// --- Scope and data: Ohio only, all 88 counties, every stage.
{
  const { $, d, set, click } = load('?state=OH&county=Knox&stage=early');
  const data = JSON.parse($('family-data').textContent);
  assert.deepEqual(Object.keys(data.states), ['OH']);
  assert.equal($('state').options.length, 1);
  assert.equal($('county').options.length, 89);
  assert($('county-result').textContent.includes('740-397-4656'));
  assert.equal(d.querySelectorAll('#pa-list li').length, 1);
  assert(!$('r-oh-help-me-grow').hidden);
  for (const c of data.ohio_counties) { set('county', c.county); assert($('county-result').textContent.includes(c.county)); assert(/\d{3}-\d{3}-\d{4}/.test($('county-result').textContent)); }
  for (const stage of data.stages) { click(d.querySelector('[data-stage="' + stage.id + '"]')); assert(!/undefined|NaN/.test($('result-status').textContent)); }
  assert.equal(load('?state=NY').$('state').value, 'OH');
  assert(d.querySelector('a[href="https://guide.vethomeguard.org/family-guide.html?state=US"]'));
  assert.equal($('back-guide').getAttribute('href'), 'ohio/index.html');
  assert($('cvso-link').href.startsWith('https://guide.vethomeguard.org/'));
  assert(!html.includes('assets/analytics.js'));
}
console.log('PASS Ohio-only scope, 88 county contacts, stages and cross-site links');

// --- A little first. On arrival the page asks; it lists nothing.
{
  const { $, d, all, inView, click } = load();
  assert(!$('results').classList.contains('chosen'), 'no list until a choice is made');
  assert.equal(inView().length, 0);
  assert.equal(all('details[open]').length, 0, 'every row and every listing starts closed');
  assert.equal(all('.quick-btn').length, 2, 'the first question is the child\'s age');
  assert.equal(all('.stage').length, 7, 'six stages and "Show everything"');
  assert.equal(all('.stage')[6].dataset.stage, 'all', '"Show everything" comes last');
  assert.equal(all('.stage[aria-pressed="true"], .quick-btn[aria-pressed="true"]').length, 0, 'nothing is pre-selected');
  assert(html.includes("document.documentElement.className='js'"), 'the list is hidden only when the script that reveals it can run');
  assert(fs.readFileSync('assets/family-guide.css', 'utf8').includes('.js #results:not(.chosen){display:none}'));
  const total = all('#military-cards .resource').length;
  assert(total >= 1 && $('military-count').textContent === String(total), 'the military row counts its programs before any choice');

  // One tap: the first calls and a short list.
  click(d.querySelector('[data-quick="school"]'));
  assert($('results').classList.contains('chosen'));
  assert.equal(d.querySelector('[data-stage="school"]').getAttribute('aria-pressed'), 'true');
  assert(all('#anchor-list li').length >= 2, 'first calls for this stage');
  assert(!$('letter').hidden && !$('letter').open, 'the letter is offered, folded');
  const passing = all('#cards .resource').filter((c) => !c.hidden).length;
  assert(passing > 8, 'this stage has a long list');
  assert.equal(inView().length, 6, 'six listings first');
  assert.equal($('show-all').textContent, `Show all ${passing} programs`);
  assert(!$('show-all-wrap').hidden);
  assert($('result-status').textContent.startsWith(passing + ' programs for school years'));
  click($('show-all'));
  assert.equal(inView().length, passing, 'the rest when asked');
  assert($('show-all-wrap').hidden);
  // A new choice starts short again.
  click(d.querySelector('[data-stage="all"]'));
  assert.equal(inView().length, 6);
  assert.match($('show-all').textContent, /^Show all \d+ programs$/);
}

// --- Other ways of choosing: a county, a need, a link.
{
  const a = load();
  a.set('county', 'Morrow');
  assert(a.$('results').classList.contains('chosen'), 'picking a county is a choice');
  assert(a.$('county-result').textContent.includes('Morrow County'));
  assert(a.w.location.search.includes('county=Morrow') && a.w.location.search.includes('stage=all'));

  const b = load();
  const box = b.d.querySelector('input[name=need][value=autism]');
  box.checked = true; box.dispatchEvent(new b.w.Event('change'));
  assert(b.$('results').classList.contains('chosen'), 'checking a need is a choice');
  assert(b.inView().length >= 1 && b.inView()[0].classList.contains('match'), 'programs made for that need come first');

  const c = load('?state=OH&county=Knox');
  assert(c.$('results').classList.contains('chosen'), 'an old link that names a county still shows the list');
  assert(!load('?state=OH').$('results').classList.contains('chosen'));

  const e = load('#r-oh-help-me-grow');
  const card = e.$('r-oh-help-me-grow');
  assert(e.$('results').classList.contains('chosen') && !card.hidden && !card.classList.contains('capped'), 'a link to one listing shows it');
  assert(card.querySelector('details.more').open, 'and opens it');

  const f = load('#words');
  assert(f.$('words').open && !f.$('results').classList.contains('chosen'), 'a link to a row opens that row only');
  assert.equal(f.all('details.need[open]').length, 1);
}

// --- Every listing is a short card; the rest is behind "More about this".
{
  const { all } = load('?stage=all');
  const cards = all('.resource');
  assert(cards.length >= 40);
  for (const c of cards) {
    const name = c.querySelector(':scope > h3').textContent.trim();
    const kids = [...c.children].map((el) => el.tagName + (el.className ? '.' + el.className.split(' ')[0] : ''));
    for (const k of kids) assert(['H3', 'P.for-need', 'P.short', 'P.actions', 'DETAILS.more'].includes(k), `"${name}": unexpected ${k} outside "More about this"`);
    const short = c.querySelector(':scope > p.short').textContent;
    assert(short.trim().length > 15 && short.length <= 220, `"${name}": one short line`);
    const more = c.querySelector(':scope > details.more');
    assert(more && !more.open, `"${name}": details start closed`);
    assert(more.textContent.includes('Next step:'), `"${name}": next step is in the details`);
    assert(more.querySelectorAll('ul.src li a').length >= 1, `"${name}": sources are in the details`);
    assert(more.querySelector('a.report'), `"${name}": a way to report a problem`);
    assert(more.querySelector('summary').textContent.includes(name), `"${name}": the summary names the listing for screen readers`);
    const acts = c.querySelectorAll(':scope > p.actions a');
    assert(acts.length >= 1 || more.querySelector('ul.locations a[href^="tel:"]'), `"${name}": a way to act`);
    for (const a of c.querySelectorAll('a[href^="tel:"]')) assert(a.textContent.replace(/\D/g, '').endsWith(a.getAttribute('href').replace(/\D/g, '').slice(-7)), `"${name}": the number shown is the number dialed`);
  }
}

// --- Rows at the bottom, structure, language, printing, leaving.
{
  const { w, d, $, all, click, inView } = load('?stage=early');
  const rows = all('details.need');
  assert.deepEqual(rows.map((r) => r.id), ['military', 'words', 'changes', 'rights-list', 'crisis-help', 'good-to-know', 'share-guide']);
  for (const r of rows) {
    assert(!r.open, `#${r.id}: closed until asked`);
    assert.equal(r.querySelector('summary h2').parentElement.tagName, 'SUMMARY');
    assert(r.querySelector('summary .nsum').textContent.trim().length > 20, `#${r.id}: says what is inside`);
  }
  assert(all('#share-guide img').every((i) => i.getAttribute('loading') === 'lazy'), 'the flyer and QR images load only when the row is opened');
  assert.equal(all('body > header').length, 1);
  assert.equal(all('header, main').length, 2);
  for (const el of d.body.children) assert(['HEADER', 'MAIN', 'FOOTER', 'SCRIPT'].includes(el.tagName) || el.matches('a.skip'), `<${el.tagName}> outside the landmarks`);
  let last = 0;
  for (const h of all('h1, h2, h3, h4, h5, h6')) { const n = +h.tagName[1]; assert(n <= last + 1, `"${h.textContent.trim().slice(0, 40)}" jumps from h${last} to h${n}`); last = n; }
  for (const b of all('.stage, .quick-btn')) assert(!b.hasAttribute('aria-labelledby') && !b.hasAttribute('aria-describedby'), 'a button is named by its own text');
  assert(!d.querySelector('[data-exit], .urgentline'), 'a disability guide: no quick exit and no crisis box at the top');
  assert($('crisis-help').querySelector('a[href="tel:988"]'), 'the crisis lines are in their own row, further down');
  assert(!html.includes('www.ohiomom.org'), 'the printed address is the one the site lives at');

  // Printing shows each listing in view in full, then puts the page back.
  const before = inView().length;
  w.dispatchEvent(new w.Event('beforeprint'));
  assert(inView().every((c) => c.querySelector('details.more').open));
  assert($('good-to-know').open);
  assert($('crisis-help').open, 'a printed list carries the crisis lines');
  w.dispatchEvent(new w.Event('afterprint'));
  assert.equal(all('details[open]').length, 0);
  assert.equal(inView().length, before);

  // Spanish: the top of the page, with nothing left undefined.
  const es = load('?lang=es&stage=school');
  assert(es.d.querySelector('h1').textContent.includes('familias'));
  for (const el of es.all('[data-i18n], [data-i18n-stage], [data-i18n-need]')) assert(el.textContent.trim() && !/undefined/.test(el.textContent), 'every marked string has Spanish');
  assert(!/undefined|NaN/.test(es.$('result-status').textContent + es.$('show-all').textContent + es.$('anchors-title').textContent));
  assert.match(es.$('show-all').textContent, /^Mostrar los \d+ programas$/);
  click(es.$('lang-toggle'));
  assert(es.d.querySelector('h1').textContent.startsWith('Help for families'));
}
console.log('PASS family guide: nothing listed until asked, six first, short cards, closed rows, links, print and Spanish');
