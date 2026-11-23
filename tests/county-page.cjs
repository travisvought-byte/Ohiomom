// The county pages. Every U.S. county has its own written page (states/<state>/<county>.html, scripts/ymt_build.py):
// its rows closed, its cards with the same parts as every other card on the site, readable with no script at all.
// county.html finds a county by state, by county or by ZIP code and opens that page. Run: node tests/county-page.cjs
const assert = require('node:assert/strict'), fs = require('node:fs'), { JSDOM, VirtualConsole } = require('jsdom');
const ymt = fs.readFileSync('assets/ymt.js', 'utf8');
const countyJs = fs.readFileSync('assets/county.js', 'utf8');
const all = (root, sel) => [...root.querySelectorAll(sel)];
const slug = (name) => name.normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
const SHARDS = {};
for (const f of fs.readdirSync('assets/us').filter((f) => /^[a-z]{2}\.json$/.test(f))) SHARDS[f.slice(0, 2)] = JSON.parse(fs.readFileSync('assets/us/' + f, 'utf8'));
const pageOf = (fips) => {
  const code = Object.keys(SHARDS).find((c) => SHARDS[c].c[fips]);
  return `states/${code}/${slug(SHARDS[code].c[fips].n)}.html`;
};

// A county's written page, with the site's own script (search, rows opened by address) running on it.
function county(fips, hash = '') {
  const file = pageOf(fips);
  const dom = new JSDOM(fs.readFileSync(file, 'utf8'), { url: 'https://example.org/' + file + hash, runScripts: 'outside-only' });
  dom.window.eval(ymt);
  return { w: dom.window, d: dom.window.document, file };
}
// county.html, the finder.
function finder(hash = '', { fail = false, noFetch = false } = {}) {
  // jsdom cannot open another page; the script asking it to is what case 4 checks, so that one notice is dropped.
  const quiet = new VirtualConsole();
  quiet.on('jsdomError', (e) => { if (!/navigation to another Document/.test(e.message)) console.error(e); });
  const dom = new JSDOM(fs.readFileSync('county.html', 'utf8'), { url: 'https://example.org/county.html' + hash, runScripts: 'outside-only', virtualConsole: quiet });
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
  const cards = all(d, 'main article.card');
  assert(cards.length > 0, `${label}: some cards`);
  for (const c of cards) {
    const kids = [...c.children].map((e) => e.tagName + (e.className ? '.' + e.className.split(' ')[0] : ''));
    for (const k of kids) assert(['H3', 'P.short', 'P.textline', 'P.actions', 'DETAILS.more'].includes(k), `${label} #${c.id}: unexpected ${k}`);
    const name = c.querySelector(':scope > h3').textContent.trim();
    assert(name, `${label} #${c.id}: a name`);
    assert(c.querySelector(':scope > p.short').textContent.trim().length > 20, `${label} #${c.id}: one line`);
    const call = c.querySelector(':scope > p.actions a.call');
    if (c.id.startsWith('tft-')) {
      // A Toys for Tots campaign has its website instead: each campaign keeps its phone on its own Contact page.
      assert(!call && c.querySelector(':scope > p.actions a[href$=".toysfortots.org/"]'), `${label} #${c.id}: the campaign's website`);
    } else {
      assert(call && /^tel:\+1\d{10}$/.test(call.getAttribute('href')), `${label} #${c.id}: a phone to call`);
      assert(call.getAttribute('href').endsWith(call.textContent.replace(/\D/g, '')), `${label} #${c.id}: the link dials the number shown`);
    }
    for (const a of all(c, ':scope > p.actions a:not(.call)')) {
      assert.match(a.getAttribute('href'), /^https?:\/\/[^\s"'<>]+$/);
      assert.equal(a.getAttribute('rel'), 'noopener');
    }
    const more = c.querySelector(':scope > details.more');
    assert(more && !more.open, `${label} #${c.id}: details start closed`);
    assert(more.querySelector('p.org'), `${label} #${c.id}: who runs it is in the details`);
    assert(more.querySelector('summary').textContent.includes(name), `${label} #${c.id}: "More about this" names the listing`);
    const visible = [...c.children].filter((e) => e.tagName !== 'DETAILS').map((e) => e.textContent).join(' ');
    assert(visible.length <= 330, `${label} #${c.id}: the short part of a card got long`);
    // The next step and the sources are said once for the whole row, around its cards.
    const row = c.closest('details.need');
    if (!c.id.startsWith('tft-')) {
      assert(row.querySelector('.rowbody > p.nextstep').textContent.startsWith('Next step:'), `${label} #${c.id}: the row says the next step`);
      assert(row.querySelector('.rowbody > p.src a[rel="noopener"]'), `${label} #${c.id}: the row names its sources`);
    } else {
      assert(more.querySelector('p.src a'), `${label} #${c.id}: sources are in the details`);
    }
  }
  const ids = all(d, '[id]').map((e) => e.id);
  assert.equal(new Set(ids).size, ids.length, `${label}: no id is used twice`);
}

(async () => {
  // 1. A county's own page: its name in the title, the way back up, closed rows, a local guide where there is one.
  {
    const { d, file } = county('39117');
    assert.equal(file, 'states/oh/morrow-county.html');
    assert.equal(d.querySelector('h1').textContent, 'Morrow County, Ohio');
    assert.equal(d.title, 'Morrow County, Ohio: help for moms | Yoga Mom Talk');
    assert.equal(d.querySelector('link[rel="canonical"]').href, 'https://www.yogamomtalk.com/states/oh/morrow-county.html');
    const desc = d.querySelector('meta[name="description"]').content;
    assert(desc.includes('Morrow County, Ohio') && desc.length <= 160, desc);
    assert.deepEqual(all(d, '.crumbs a').map((a) => a.getAttribute('href')), ['../../index.html', '../../states.html', '../oh.html']);
    const ld = JSON.parse(d.querySelector('script[type="application/ld+json"]').textContent);
    const trail = ld['@graph'].find((g) => g['@type'] === 'BreadcrumbList').itemListElement.map((i) => i.name);
    assert.deepEqual(trail, ['Yoga Mom Talk', 'Help by state', 'Ohio', 'Morrow County']);
    assert.equal(d.querySelector('.hero').nextElementSibling.id, 'now', 'the crisis cards come right after the heading');
    const rows = all(d, 'details.need');
    assert.deepEqual(rows.map((r) => r.id), ['county-christmas', 'county-pha', 'county-hud', 'county-legal', 'county-health', 'county-schools', 'county-start', 'county-state']);
    const legal = all(d, '#county-legal article.card');
    assert.equal(legal.length, 1);
    assert.equal(legal[0].querySelector('h3').textContent, 'Legal Aid of Southeast and Central Ohio');
    assert.match(legal[0].querySelector('.short').textContent, /custody, child support, protection from abuse and eviction/);
    assert(rows.every((r) => !r.open), 'rows stay closed until asked for');
    for (const r of rows) assert.equal(r.querySelector('summary h2').parentElement.tagName, 'SUMMARY');
    checkCards(d, 'Morrow');
    // Public housing: Morrow's own agency first, said plainly to have its office in Mount Vernon, then the nearest others.
    const pha = all(d, '#county-pha article.card');
    assert.equal(pha[0].querySelector('h3').textContent, 'Morrow Metropolitan Housing Authority');
    assert.match(pha[0].querySelector('.short').textContent, /^Named for Morrow County, with its office in Mount Vernon, OH\. Housing Choice Vouchers/);
    for (const c of pha.slice(1)) assert.match(c.querySelector('.short').textContent, /^About \d+ miles away, in .*Ask whether it serves where you live\.$/);
    assert.match(d.querySelector('#county-pha .nsum').textContent, /^Where to apply in Morrow County/);
    // School districts: every district that reaches into Morrow County, the ones covering the most of it first,
    // after a few lines on asking for an evaluation.
    const schools = d.getElementById('county-schools');
    assert.deepEqual(all(schools, 'article.card h3').map((h) => h.textContent).slice(0, 4),
      ['Highland Local', 'Northmor Local', 'Mount Gilead Exempted Village', 'Cardington-Lincoln Local']);
    assert.match(schools.querySelector('.rowbody p.quiet').textContent, /From age 3.*evaluation.*in writing/);
    assert.equal(schools.querySelector('.rowbody p.quiet a').getAttribute('href'), '../../states/oh.html#oh-ei');
    assert(new JSDOM(fs.readFileSync('states/oh.html', 'utf8')).window.document.getElementById('oh-ei'), 'the early intervention card is there');
    assert.equal(d.querySelector('.localbox a').getAttribute('href'), '../../ohio/counties/morrow.html');
    const ohio = new JSDOM(fs.readFileSync('states/oh.html', 'utf8')).window.document;
    const links = all(d, '#county-state .statelinks a');
    assert.equal(links.length, 9);
    for (const a of links) {
      const [page, frag] = a.getAttribute('href').split('#');
      assert.equal(page, '../../states/oh.html');
      assert(ohio.getElementById(frag), `states/oh.html#${frag}`);
    }
    // The way to another county: the state's list, which links every county's page.
    const back = d.querySelector('.countylink a').getAttribute('href');
    assert.equal(back, '../oh.html#counties');
    const list = all(ohio, '#counties a');
    assert.equal(list.length, 88, 'Ohio has 88 counties');
    for (const a of list) assert(fs.existsSync('states/' + a.getAttribute('href')), a.getAttribute('href'));
    assert(list.some((a) => a.getAttribute('href') === 'oh/morrow-county.html'));
    assert.equal(all(d, 'form').length, 0);
    assert.equal(all(d, 'input[name]').length, 0, 'no field has a name, so nothing can be sent');
  }

  // 1b. Every county of every state has its page, and no card breaks the card rules (the largest county of each state).
  {
    let n = 0;
    for (const [code, shard] of Object.entries(SHARDS)) {
      for (const fips of Object.keys(shard.c)) { assert(fs.existsSync(pageOf(fips)), pageOf(fips)); n++; }
      const fips = Object.keys(shard.c).sort((a, b) => shard.c[b].p - shard.c[a].p)[0];
      const { d } = county(fips);
      assert.equal(all(d, 'details.need').length, 8, fips + ': Christmas help and seven needs');
      assert(all(d, '#county-legal article.card').length >= 1, fips + ': every county has legal aid');
      checkCards(d, `${code} ${fips}`);
    }
    assert.equal(Object.keys(SHARDS).length, 51);
    assert.equal(n, 3144);
  }

  // 2. A county with hundreds of listings lists them all, closed in their row, and the search box narrows them by town.
  {
    const { w, d } = county('06037');
    const health = d.getElementById('county-health');
    const n = SHARDS.ca.c['06037'].health.length;
    assert(n > 500);
    assert.equal(all(health, 'article.card').length, n);
    assert.equal(health.querySelector('.ncount').textContent, n + ' places');
    const q = d.getElementById('q');
    q.value = 'pasadena';
    q.dispatchEvent(new w.Event('input', { bubbles: true }));
    const shown = all(health, 'article.card').filter((c) => !c.hidden);
    assert(shown.length > 0 && shown.every((c) => /pasadena/i.test(c.textContent)), 'narrowing keeps only matching places');
    assert(health.open, 'the row with a match opens');
    checkCards(d, 'Los Angeles');
  }

  // 3. A county with no health center of its own shows the nearest ones and says how far they are.
  {
    const { d } = county('48301');
    const health = d.getElementById('county-health');
    assert.match(health.querySelector('.nsum').textContent, /^Nearest health centers, outside Loving County$/);
    for (const c of all(health, 'article.card')) assert.match(c.querySelector('.short').textContent, /^About \d+ miles? from the middle of Loving County\./);
    const schools = d.getElementById('county-schools');
    assert.match(schools.querySelector('.nsum').textContent, /^School districts in Loving County/);
    assert.deepEqual(all(schools, 'article.card h3').map((h) => h.textContent), ['Wink-Loving ISD'], 'by boundary, not by where the office is');
    const state = all(d, '#county-pha article.card').filter((c) => /^Statewide agency/.test(c.querySelector('.short').textContent));
    assert.equal(state.length, 1, "Texas's statewide voucher program is offered too");
    checkCards(d, 'Loving');
  }

  // 3b. A Virginia city with no school district of its own shows the nearest, with the distance. Names with accents get plain addresses.
  {
    const { d } = county('51600');
    const schools = d.getElementById('county-schools');
    assert.match(schools.querySelector('.nsum').textContent, /^Nearest school districts, outside Fairfax City$/);
    const first = schools.querySelector('article.card');
    assert.equal(first.querySelector('h3').textContent, 'Fairfax County Public Schools');
    assert.match(first.querySelector('.short').textContent, /^About \d+ miles? away, in .*Ask whether it serves where you live\.$/);
    checkCards(d, 'Fairfax City');
    assert.equal(pageOf('35013'), 'states/nm/dona-ana-county.html');
  }

  // 3c. A link to a row opens it.
  {
    const { d } = county('39117', '#county-legal');
    assert.deepEqual(all(d, 'details.need').filter((r) => r.open).map((r) => r.id), ['county-legal']);
  }

  // 4. On county.html a ZIP code is matched in the browser and opens its county's page. Nothing is sent but the request for a list.
  {
    const { w, d, asked } = finder('');
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
    assert.equal(d.getElementById('cmsg').textContent, 'Opening Morrow County…');
    assert.deepEqual(asked.map((a) => a[0]), ['assets/us/z4.json', 'assets/us/oh.json']);
    for (const [url, opts] of asked) {
      assert.match(url, /^assets\/us\/[a-z0-9]+\.json$/, 'only this site\'s own files are read');
      assert.equal(opts.credentials, 'omit');
      assert.equal(opts.referrerPolicy, 'no-referrer');
    }
    zip.value = '00001';
    zip.dispatchEvent(new w.Event('input'));
    await settle(w);
    assert.match(d.getElementById('cmsg').textContent, /could not match that ZIP code/);
    assert(!d.querySelector('[data-county-find]').hidden, 'the choosers show once the script runs');
  }

  // 5. A state's two letters list its counties, each a link to its page; choosing a state does the same.
  {
    const { w, d } = finder('#oh');
    await settle(w);
    assert.equal(d.getElementById('ctitle').textContent, 'Ohio counties');
    const links = all(d, '#county-app .statelist a');
    assert.equal(links.length, 88);
    for (const a of links) assert(fs.existsSync(a.getAttribute('href')), a.getAttribute('href'));
    assert.equal(d.getElementById('ccounty').options.length, 89);
    const pick = d.getElementById('cstate');
    pick.value = 'ct';
    pick.dispatchEvent(new w.Event('change'));
    await settle(w);
    assert.equal(w.location.hash, '#ct');
    assert.equal(all(d, '#county-app .statelist a').length, 9, 'Connecticut has nine planning regions');
  }

  // 6. When a list cannot be loaded, the page says so and points to the state page. An unknown code goes home.
  {
    const { w, d } = finder('#39117', { fail: true });
    await settle(w);
    assert.match(d.getElementById('county-app').textContent, /could not load that list/);
    assert.equal(d.querySelector('#county-app a').getAttribute('href'), 'states/oh.html');
    const other = finder('#99999');
    await settle(other.w);
    assert.equal(other.d.getElementById('ctitle').textContent, 'Help near you');
  }

  // 7. A browser that cannot fetch keeps the plain message and a way to the state pages.
  {
    const { w, d } = finder('#39117', { noFetch: true });
    await settle(w);
    assert(d.querySelector('[data-county-find]').hidden);
    assert.match(d.getElementById('county-app').textContent, /needs JavaScript/);
    assert(d.querySelector('#county-app a[href="states.html"]'));
  }
  console.log('PASS county pages: 3,144 written pages with closed rows and the same card parts; county.html finds a county by code, state or ZIP code');
})().catch((e) => { console.error(e); process.exit(1); });
