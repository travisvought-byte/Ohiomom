// The county page: it finds a county by state, by county or by ZIP code, draws that county's rows closed,
// and its cards have the same parts as every other card on the site. Run: node tests/county-page.cjs
const assert = require('node:assert/strict'), fs = require('node:fs'), { JSDOM } = require('jsdom');
const ymt = fs.readFileSync('assets/ymt.js', 'utf8');
const countyJs = fs.readFileSync('assets/county.js', 'utf8');
const all = (root, sel) => [...root.querySelectorAll(sel)];

function load(hash = '', { fail = false, noFetch = false } = {}) {
  const dom = new JSDOM(fs.readFileSync('county.html', 'utf8'), { url: 'https://example.org/county.html' + hash, runScripts: 'outside-only' });
  const w = dom.window;
  const asked = [];
  w.fetch = noFetch ? undefined : (url, opts) => {
    asked.push([url, opts]);
    if (fail) return Promise.reject(new Error('offline'));
    if (!fs.existsSync(url)) return Promise.resolve({ ok: false, status: 404, json: () => Promise.reject(new Error('404')) });
    const body = fs.readFileSync(url, 'utf8');
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(JSON.parse(body)) });
  };
  w.eval(ymt);
  w.eval(countyJs);
  return { w, d: w.document, asked };
}
async function settle(w) {
  for (let i = 0; i < 30; i++) await new Promise((r) => w.setTimeout(r, 0));
}

function checkCards(d, label) {
  const cards = all(d, '#county-app article.card');
  assert(cards.length > 0, `${label}: some cards`);
  for (const c of cards) {
    const kids = [...c.children].map((e) => e.tagName + (e.className ? '.' + e.className.split(' ')[0] : ''));
    for (const k of kids) assert(['H3', 'P.short', 'P.textline', 'P.actions', 'DETAILS.more'].includes(k), `${label} #${c.id}: unexpected ${k}`);
    const name = c.querySelector(':scope > h3').textContent.trim();
    assert(name, `${label} #${c.id}: a name`);
    assert(c.querySelector(':scope > p.short').textContent.trim().length > 20, `${label} #${c.id}: one line`);
    const call = c.querySelector(':scope > p.actions a.call');
    assert(call && /^tel:\+1\d{10}$/.test(call.getAttribute('href')), `${label} #${c.id}: a phone to call`);
    assert(call.getAttribute('href').endsWith(call.textContent.replace(/\D/g, '')), `${label} #${c.id}: the link dials the number shown`);
    for (const a of all(c, ':scope > p.actions a:not(.call)')) {
      assert.match(a.getAttribute('href'), /^https?:\/\/[^\s"'<>]+$/);
      assert.equal(a.getAttribute('rel'), 'noopener');
    }
    const more = c.querySelector(':scope > details.more');
    assert(more && !more.open, `${label} #${c.id}: details start closed`);
    assert(more.querySelector('p.src a'), `${label} #${c.id}: sources are in the details`);
    assert(more.textContent.includes('Next step:'), `${label} #${c.id}: a next step`);
    assert(more.querySelector('summary').textContent.includes(name), `${label} #${c.id}: "More about this" names the listing`);
    const visible = [...c.children].filter((e) => e.tagName !== 'DETAILS').map((e) => e.textContent).join(' ');
    assert(visible.length <= 330, `${label} #${c.id}: the short part of a card got long`);
  }
  const ids = all(d, '[id]').map((e) => e.id);
  assert.equal(new Set(ids).size, ids.length, `${label}: no id is used twice`);
}

(async () => {
  // 1. A county by its code: four closed rows, a local guide where there is one, and the pickers follow along.
  {
    const { w, d, asked } = load('#39117');
    await settle(w);
    assert.equal(d.getElementById('ctitle').textContent, 'Morrow County, Ohio');
    assert.equal(d.title, 'Morrow County, Ohio: help for moms | Yoga Mom Talk');
    const rows = all(d, '#county-app details.need');
    assert.deepEqual(rows.map((r) => r.id), ['county-health', 'county-start', 'county-hud', 'county-state']);
    assert(rows.every((r) => !r.open), 'rows stay closed until asked for');
    for (const r of rows) assert.equal(r.querySelector('summary h2').parentElement.tagName, 'SUMMARY');
    checkCards(d, 'Morrow');
    const guide = d.querySelector('#county-app .localbox a');
    assert.equal(guide.getAttribute('href'), 'ohio/counties/morrow.html');
    assert(fs.existsSync('ohio/counties/morrow.html'));
    const ohio = new JSDOM(fs.readFileSync('states/oh.html', 'utf8')).window.document;
    const links = all(d, '#county-app .statelinks a');
    assert.equal(links.length, 8);
    for (const a of links) {
      const [page, frag] = a.getAttribute('href').split('#');
      assert.equal(page, 'states/oh.html');
      assert(ohio.getElementById(frag), `states/oh.html#${frag}`);
    }
    assert.equal(d.getElementById('cstate').value, 'oh');
    assert.equal(d.getElementById('ccounty').value, '39117');
    assert.equal(d.getElementById('ccounty').options.length, 89, 'Ohio has 88 counties');
    assert(!d.querySelector('[data-county-find]').hidden, 'the choosers show once the script runs');
    assert(asked.length >= 1);
    for (const [url, opts] of asked) {
      assert.match(url, /^assets\/us\/[a-z0-9]+\.json$/, 'only this site\'s own files are read');
      assert.equal(opts.credentials, 'omit');
      assert.equal(opts.referrerPolicy, 'no-referrer');
    }
    assert.equal(all(d, 'form').length, 0);
    assert.equal(all(d, 'input[name]').length, 0, 'no field has a name, so nothing can be sent');
  }

  // 2. A county with hundreds of listings shows a few, then more on request, and can be narrowed by town.
  {
    const { w, d } = load('#06037');
    await settle(w);
    const health = d.getElementById('county-health');
    assert.equal(all(health, 'article.card').length, 6);
    const more = health.querySelector('.rowbody button');
    assert.equal(more.textContent, 'Show 12 more');
    more.click();
    assert.equal(all(health, 'article.card').length, 18);
    const box = health.querySelector('input.rowfilter');
    assert.equal(box.type, 'search');
    box.value = 'pasadena';
    box.dispatchEvent(new w.Event('input'));
    const shown = all(health, 'article.card');
    assert(shown.length > 0 && shown.every((c) => /pasadena/i.test(c.textContent)), 'narrowing keeps only matching places');
    assert(more.hidden, '"Show more" steps aside while narrowing');
    box.value = 'zzzzqx';
    box.dispatchEvent(new w.Event('input'));
    assert.equal(all(health, 'article.card').length, 0);
    assert.match(health.textContent, /Nothing matches/);
    box.value = '';
    box.dispatchEvent(new w.Event('input'));
    checkCards(d, 'Los Angeles');
  }

  // 3. A county with no health center of its own shows the nearest ones and says how far they are.
  {
    const { w, d } = load('#48301');
    await settle(w);
    const health = d.getElementById('county-health');
    assert.match(health.querySelector('.nsum').textContent, /^Nearest health centers, outside Loving County$/);
    for (const c of all(health, 'article.card')) assert.match(c.querySelector('.short').textContent, /^About \d+ miles? from the middle of Loving County\./);
    checkCards(d, 'Loving');
  }

  // 4. A ZIP code is matched in the browser and opens its county. Nothing is sent but the request for a list.
  {
    const { w, d, asked } = load('');
    await settle(w);
    const zip = d.getElementById('zip');
    zip.value = '4333';
    zip.dispatchEvent(new w.Event('input'));
    await settle(w);
    assert.equal(asked.length, 0, 'four digits are not looked up');
    zip.value = '43338';
    zip.dispatchEvent(new w.Event('input'));
    await settle(w);
    assert.equal(w.location.hash, '#39117');
    await settle(w);
    assert.equal(d.getElementById('ctitle').textContent, 'Morrow County, Ohio');
    assert.deepEqual(asked.map((a) => a[0]), ['assets/us/z4.json', 'assets/us/oh.json']);
    zip.value = '00001';
    zip.dispatchEvent(new w.Event('input'));
    await settle(w);
    assert.match(d.getElementById('cmsg').textContent, /could not match that ZIP code/);
  }

  // 5. A state's two letters list its counties; choosing a state does the same.
  {
    const { w, d } = load('#oh');
    await settle(w);
    assert.equal(d.getElementById('ctitle').textContent, 'Ohio counties');
    const links = all(d, '#county-app .statelist a');
    assert.equal(links.length, 88);
    for (const a of links) assert.match(a.getAttribute('href'), /^#39\d{3}$/);
    const pick = d.getElementById('cstate');
    pick.value = 'ct';
    pick.dispatchEvent(new w.Event('change'));
    await settle(w);
    assert.equal(w.location.hash, '#ct');
    assert.equal(all(d, '#county-app .statelist a').length, 9, 'Connecticut has nine planning regions');
  }

  // 6. When a list cannot be loaded, the page says so and points to the state page. An unknown code goes home.
  {
    const { w, d } = load('#39117', { fail: true });
    await settle(w);
    assert.match(d.getElementById('county-app').textContent, /could not load that list/);
    assert.equal(d.querySelector('#county-app a').getAttribute('href'), 'states/oh.html');
    const other = load('#99999');
    await settle(other.w);
    assert.equal(other.d.getElementById('ctitle').textContent, 'Help near you');
  }

  // 7. A browser that cannot fetch keeps the plain message and a way to the state pages.
  {
    const { w, d } = load('#39117', { noFetch: true });
    await settle(w);
    assert(d.querySelector('[data-county-find]').hidden);
    assert.match(d.getElementById('county-app').textContent, /need JavaScript/);
    assert(d.querySelector('#county-app a[href="states.html"]'));
  }
  console.log('PASS county page: codes, ZIP codes and states find a county; closed rows; same card parts; long lists narrow; failures explained');
})().catch((e) => { console.error(e); process.exit(1); });
