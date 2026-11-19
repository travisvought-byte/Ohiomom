// OhioMom's housing page and its "All resources" page. Run: node tests/ohio-directory.cjs
const assert = require('node:assert/strict'), fs = require('node:fs'), { JSDOM } = require('jsdom');
const all = (d, sel) => [...d.querySelectorAll(sel)];
const tick = () => new Promise((r) => setTimeout(r, 0));
const siteScript = fs.readFileSync('ohio/assets/site.js', 'utf8');
const dirScript = fs.readFileSync('ohio/assets/all.js', 'utf8');
const ohioData = JSON.parse(fs.readFileSync('ohio/assets/data.json', 'utf8'));
const places = JSON.parse(fs.readFileSync('ohio/assets/places.json', 'utf8'));
const staticDoc = (file) => new JSDOM(fs.readFileSync(file, 'utf8')).window.document;
const names = (d, sel = 'article.card') => all(d, sel).map((c) => c.querySelector('h3').textContent.trim());

// 1. Housing and shelter is a door of its own, on the front page and on the help page.
{
  for (const f of ['ohio/index.html', 'ohio/help.html']) {
    const d = staticDoc(f);
    assert(d.querySelector('.tile[href="help/housing.html"]'), `${f}: housing and shelter is a choice of its own`);
    assert(d.querySelector('.tile[href="all.html"]'), `${f}: there is a way to see everything`);
    assert.match(d.querySelector('.tile[href="help/bills.html"] strong').textContent, /food or bills/, `${f}: the bills tile no longer hides housing`);
  }
  const d = staticDoc('ohio/help/housing.html');
  const rows = all(d, 'details.need');
  assert.deepEqual(rows.map((r) => r.id), ['tonight', 'safe', 'rent']);
  for (const r of rows) assert(r.querySelectorAll('article.card').length >= 5, `#${r.id}: a choice opens more than two or three listings`);
  const listed = names(d);
  for (const must of ['Find shelter and homeless services in your county', 'Ohio 211', 'Find your local domestic violence program',
    "Women's shelters and advocates in Ohio", 'YWCA: shelter, housing and support for women', 'Got an eviction notice? Start here',
    'Emergency help for families from your county (PRC)', 'Find an affordable rental (Ohio Housing Locator)']) assert(listed.includes(must), must);
  // The numbers that must never be more than one tap away are in the open, and each is a full listing below.
  const phones = all(d, '.phonecard');
  assert.equal(phones.length, 2);
  const calls = all(d, 'article.card a.call').map((a) => a.getAttribute('href'));
  for (const a of phones) {
    assert(calls.includes(a.getAttribute('href')), `${a.textContent} is also a listing on the page`);
    assert(a.textContent.includes(a.getAttribute('href').slice(4).slice(-3)), 'the number shown is the number dialed');
  }
  // A domestic violence line is in the open, so the quick way to leave the page is too. The safety row has its own.
  assert(d.querySelector('.rightnow [data-exit]') && d.querySelector('details.need.urgent#safe [data-exit]'));
  // Shelter addresses are never printed: no card on this page carries an address line.
  assert.equal(all(d, '.addr').length, 0);
  assert(d.body.textContent.includes('Shelter addresses are never listed on OhioMom'));
  // Every phone number a button dials is the number it shows.
  for (const a of all(d, 'a.btn.call')) {
    const dialed = a.getAttribute('href').replace('tel:', '');
    assert(a.textContent.replace(/\D/g, '').endsWith(dialed.slice(-4)), `${a.textContent} dials ${dialed}`);
  }
  assert(d.querySelector('a[href="../all.html#need=housing"]'), 'the housing page leads to every housing listing');
}
// The old one-card pointer is gone: the Ohio pages name the county guide and Ohio 211 by their own addresses.
for (const f of ['ohio/help/bills.html', 'ohio/help/housing.html', 'ohio/counties/franklin.html']) {
  const text = fs.readFileSync(f, 'utf8');
  assert(!text.includes('housingresourceguide'), `${f}: 211 and the shelter guide no longer share one borrowed link`);
}
console.log('PASS Ohio housing page: three rows, phone cards, quick exit, no addresses');

// 2. Every Ohio page offers the full list.
{
  const pages = fs.readdirSync('ohio').filter((f) => f.endsWith('.html')).map((f) => 'ohio/' + f)
    .concat(fs.readdirSync('ohio/help').filter((f) => f.endsWith('.html')).map((f) => 'ohio/help/' + f))
    .concat(fs.readdirSync('ohio/counties').filter((f) => f.endsWith('.html')).map((f) => 'ohio/counties/' + f))
    .concat(['family-guide.html'])
    .filter((f) => !/http-equiv="refresh"/i.test(fs.readFileSync(f, 'utf8')));
  assert(pages.length >= 20);
  for (const f of pages) {
    const link = staticDoc(f).querySelector('.footnav a[href$="all.html"]');
    assert(link && link.textContent === 'All resources', `${f}: the footer links to All resources`);
    const target = new URL(link.getAttribute('href'), 'https://example.org/' + f).pathname;
    assert.equal(target, '/ohio/all.html', f);
    const about = staticDoc(f).querySelector('.footnav a[href$="about.html"]');
    assert(about && about.textContent === 'About us', `${f}: the footer links to the About page`);
    assert.equal(new URL(about.getAttribute('href'), 'https://example.org/' + f).pathname, '/ohio/about.html', f);
  }
  for (const f of fs.readdirSync('ohio/counties').filter((x) => x.endsWith('.html'))) {
    const d = staticDoc('ohio/counties/' + f);
    const county = d.querySelector('h1').textContent.replace(' County', '');
    assert(d.querySelector(`a[href="../all.html#county=${county}"]`), `${f}: a link to everything for ${county} County`);
  }
}

// 3. The place list: all 88 counties, every ZIP code once, and only counties that exist.
{
  const counties = Object.keys(ohioData.counties);
  assert.deepEqual(Object.keys(places.counties).sort(), counties.slice().sort());
  const seen = new Set();
  for (const [county, line] of Object.entries(places.counties)) {
    for (const entry of line.split('|')) {
      const codes = entry.match(/\b\d{5}\b/g);
      assert(codes && codes.length >= 1, `${county}: "${entry}" has no ZIP code`);
      assert(/^[A-Za-z .'-]+$/.test(entry.replace(/\b\d{5}\b/g, '').trim()), `${county}: "${entry}"`);
      for (const z of codes) {
        assert(/^4[345]\d{3}$/.test(z), `${z} is not an Ohio ZIP code`);
        assert(!seen.has(z), `${z} is listed twice`);
        seen.add(z);
      }
    }
  }
  assert(seen.size > 1300);
  for (const [z, others] of Object.entries(places.reaches)) {
    assert(seen.has(z), `${z} reaches another county but is not listed`);
    const home = counties.find((c) => new RegExp('\\b' + z + '\\b').test(places.counties[c]));
    for (const c of others.split('|')) assert(counties.includes(c) && c !== home, `${z}: ${c}`);
  }
  assert(/\bMarengo 43334\b/.test(places.counties.Morrow));
  assert(/GeoNames/.test(places.about) && /CC BY 4\.0/.test(places.about) && /Census/.test(places.about));
  assert(/GeoNames/.test(fs.readFileSync('ohio/all.html', 'utf8')), 'the page that uses the list credits it');
}
console.log('PASS every Ohio page links to All resources; the place list covers 88 counties');

// 4. The page itself. Without its script it is an index of links, and the tools stay hidden so no box does nothing.
{
  const d = staticDoc('ohio/all.html');
  assert(d.querySelector('[data-directory-tools]').hidden);
  assert(all(d, '[data-directory-index] a').length >= 8);
  for (const a of all(d, '[data-directory-index] a')) {
    const file = new URL(a.getAttribute('href'), 'https://example.org/ohio/all.html').pathname.slice(1);
    assert(fs.existsSync(file), `${file} is linked from the index`);
  }
  // The site script binds #q, #place and #need on other pages. This page keeps its own names.
  for (const id of ['q', 'place', 'places', 'need', 'count']) assert(!d.getElementById(id), `#${id} belongs to the site script`);
  for (const id of ['find', 'county', 'town']) assert(d.querySelector(`label[for="${id}"]`), `#${id} has a label`);
}
// The script reads this site's own pages and nothing else, and keeps what is typed on the device.
for (const banned of ['XMLHttpRequest', 'sendBeacon', 'document.cookie', 'sessionStorage', 'innerHTML', 'http://', 'https://']) {
  assert(!dirScript.includes(banned), `all.js: ${banned}`);
}
assert.deepEqual([...new Set(dirScript.match(/localStorage\.\w+\('[^']+'/g))].sort(), ["localStorage.getItem('om.area'", "localStorage.setItem('om.area'"]);

async function loadDirectory(hash = '', { missing = [], area = null } = {}) {
  const here = 'https://example.org/ohio/all.html';
  const dom = new JSDOM(fs.readFileSync('ohio/all.html', 'utf8'), { url: here + hash, runScripts: 'outside-only' });
  const w = dom.window;
  w.matchMedia = () => ({ matches: false });
  const asked = [];
  w.fetch = (url) => {
    const u = new URL(String(url), here);
    asked.push(u.href);
    const file = decodeURIComponent(u.pathname.slice(1));
    const gone = u.origin !== 'https://example.org' || u.search || missing.includes(file) || !fs.existsSync(file);
    const body = gone ? '' : fs.readFileSync(file, 'utf8');
    return Promise.resolve({ ok: !gone, status: gone ? 404 : 200, text: () => Promise.resolve(body), json: () => (gone ? Promise.reject(new Error('404')) : Promise.resolve(JSON.parse(body))) });
  };
  if (area) w.localStorage.setItem('om.area', JSON.stringify(area));
  w.eval(siteScript);
  w.eval(dirScript);
  for (let i = 0; i < 80 && w.document.querySelector('[data-directory-tools]').hidden; i++) await tick();
  for (let i = 0; i < 8; i++) await tick();
  const d = w.document;
  const type = (id, value, event = 'input') => { const e = d.getElementById(id); e.value = value; e.dispatchEvent(new w.Event(event, { bubbles: true })); };
  const click = (e) => e.dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
  return { w, d, asked, type, click, shown: () => names(d, '[data-directory-list] article.card'), found: () => d.getElementById('found').textContent };
}

(async () => {
  // 5. Everything is there, once.
  const sources = ['ohio/help/bills.html', 'ohio/help/pregnancy-baby.html', 'ohio/help/single-parent.html', 'ohio/wellbeing.html', 'ohio/help/housing.html', 'ohio/holidays.html']
    .concat(fs.readdirSync('ohio/counties').filter((f) => f.endsWith('.html')).map((f) => 'ohio/counties/' + f));
  {
    const { d, asked, shown, found } = await loadDirectory();
    assert(!d.querySelector('[data-directory-tools]').hidden, 'the tools appear once the list is built');
    assert(d.querySelector('[data-directory-index]').hidden, 'the index of links gives way to the list');
    assert(d.querySelector('[data-directory-status]').hidden, 'nothing failed to load');
    const listed = shown();
    assert(listed.length > 140, `the whole list: ${listed.length}`);
    assert.equal(new Set(listed).size, listed.length, 'no listing appears twice');
    assert.equal(found(), `${listed.length} listings.`);
    for (const f of sources) for (const n of names(staticDoc(f))) assert(listed.includes(n), `${f}: "${n}" is missing from All resources`);
    for (const g of ohioData.groups) assert(listed.includes(g.name), `group "${g.name}" is missing`);
    const guide = staticDoc('family-guide.html');
    for (const c of all(guide, 'article.card')) {
      if (/(^|\s)OH:/.test(c.getAttribute('data-replaced') || '')) continue;
      assert(listed.includes(c.querySelector('h3').textContent.trim()), `family guide: "${c.querySelector('h3').textContent}" is missing`);
    }
    for (const must of ['Disability Rights Ohio', 'Head Start near you in Ohio', 'Veterans Crisis Line', 'Find a food bank near you']) assert(listed.includes(must), must);
    // Ohio's own listing stands in for the general one the national page carries.
    for (const general of ['SNAP in Ohio', 'Dial 211 in Ohio', 'Free legal help in Ohio', 'Domestic violence help in Ohio']) assert(!listed.includes(general), general);
    // Groups by need, each with a heading and a count, in a fixed order.
    const heads = all(d, '.dirgroup h2').map((h) => h.firstChild.textContent);
    assert.deepEqual(heads, ['Housing and shelter', 'Safety and crisis lines', 'Food and bills', 'Pregnancy and new baby',
      'My child learns or grows differently', 'Parenting on my own', 'Take care of me', 'Military and veteran families', 'Holiday help', 'Meet other moms']);
    for (const g of all(d, '.dirgroup')) assert.equal(g.querySelector('.ncount').textContent, `${g.querySelectorAll('article.card').length} listings`);
    // Every card is a short card: a name, one line, a way to act, the rest folded away. Nothing carries a duplicate id.
    for (const c of all(d, '[data-directory-list] article.card')) {
      const name = c.querySelector('h3').textContent;
      assert(c.querySelector(':scope > p.short').textContent.trim().length > 15, name);
      assert(c.querySelectorAll(':scope > p.actions a, .locations a').length >= 1, `${name}: a way to act`);
      assert(!/new tab/.test(c.textContent), `${name}: links open in the same tab here, so nothing says otherwise`);
      assert(c.querySelector(':scope > details.more') && !c.querySelector('details[open]'), `${name}: details start closed`);
      assert(!c.id && !c.querySelector('[id]'), `${name}: no ids are copied in`);
      assert(!c.querySelector('a[target]') && !c.querySelector('a.report'), `${name}: every card behaves alike`);
      for (const a of all(c, 'a[href]')) assert(/^(https:|tel:|mailto:)/.test(a.getAttribute('href')), `${name}: ${a.getAttribute('href')}`);
    }
    // Links that were relative on their own page still work from here.
    const prc = all(d, '[data-directory-list] article.card').find((c) => c.querySelector('h3').textContent.startsWith('Emergency help for families'));
    assert.equal(prc.querySelector('details.more a').getAttribute('href'), 'https://example.org/ohio/counties.html');
    // A local office carries its county. One that serves two counties carries both and is listed once.
    const tags = (name) => all(all(d, '[data-directory-list] article.card').find((c) => c.querySelector('h3').textContent === name), '.tag').map((t) => t.textContent);
    assert.deepEqual(tags('Morrow County Job and Family Services'), ['Morrow County']);
    assert.deepEqual(tags('Turning Point').sort(), ['Delaware County', 'Morrow County']);
    assert.deepEqual(tags('Ohio 211'), [], 'a statewide listing shown on a county page is not local');
    assert.deepEqual(tags('Help with heating and electric bills (HEAP)'), []);
    // It asks only for this site's own pages and data, and never puts anything in the address it asks for.
    assert(asked.length >= sources.length + 4);
    for (const u of asked) assert(u.startsWith('https://example.org/') && !u.includes('?') && /\.(html|json)$/.test(u), u);
    assert.equal(d.querySelectorAll('#county option').length, 89);
  }
  console.log('PASS All resources: every listing once, grouped by need, local offices tagged');

  // 6. Narrowing by need, by county, by town and by ZIP code.
  {
    const { w, d, type, click, shown, found } = await loadDirectory();
    const total = shown().length;
    click(d.querySelector('[data-need-chips] button[data-need="housing"]'));
    assert.deepEqual(all(d, '.dirgroup h2').map((h) => h.firstChild.textContent), ['Housing and shelter']);
    assert.equal(shown()[0], 'Find shelter and homeless services in your county');
    for (const n of names(staticDoc('ohio/help/housing.html'))) assert(shown().includes(n), n);
    assert(shown().includes('Free legal help: custody, divorce, eviction, benefits'), 'a listing can answer to a second need');
    assert(!shown().includes('WIC: food for pregnancy, babies and children under 5'));
    assert.equal(w.location.hash, '#need=housing', 'the need can be shared as a link');
    assert.equal(d.querySelector('[data-need-chips] button[aria-pressed="true"]').textContent, 'Housing and shelter');
    click(d.querySelector('[data-need-chips] button[data-need=""]'));
    assert.equal(shown().length, total);
    assert.equal(w.location.hash, '');

    // A town sets the county, says so, and is remembered the way the rest of the site remembers an area.
    type('town', 'Marengo');
    assert.equal(d.getElementById('county').value, 'Morrow');
    assert.equal(d.getElementById('townnote').textContent, 'Marengo is in Morrow County.');
    assert.deepEqual(JSON.parse(w.localStorage.getItem('om.area')), { r: 'central', c: 'Morrow' });
    assert.equal(d.querySelector('[data-area-chip]').textContent, '📍 Morrow County');
    assert.match(found(), /^Showing \d+ of \d+ listings for Morrow County and all of Ohio\.$/);
    assert(shown().includes('Morrow County Job and Family Services') && !shown().includes('Franklin County Job and Family Services'));
    assert(shown().includes('Ohio 211'), 'statewide help stays');
    const food = all(d, '.dirgroup').find((g) => g.querySelector('h2').firstChild.textContent === 'Food and bills');
    assert.deepEqual(all(food.querySelector('article.card'), '.tag').map((t) => t.textContent), ['Morrow County'], "the county's own offices come first");
    assert(!shown().some((n) => /Northeast Ohio|Cincinnati/.test(n)), 'groups from other parts of Ohio step aside');
    // A ZIP code that crosses a county line says so and offers the other county.
    type('town', '43334');
    assert.match(d.getElementById('townnote').textContent, /^43334 \(Marengo\) is in Morrow County\. This ZIP code also reaches into Delaware County\./);
    const other = d.querySelector('#townnote button[data-county="Delaware"]');
    assert(other);
    click(other);
    assert.equal(d.getElementById('county').value, 'Delaware');
    // Leaving the box afterwards does not undo the choice she just made.
    type('town', '43334', 'change');
    assert.equal(d.getElementById('county').value, 'Delaware');
    assert(shown().includes('Delaware County Job and Family Services') && !shown().includes('Morrow County Job and Family Services'));
    // Short forms, capitals and post office spellings are all the same place.
    for (const [typed, county, says] of [['mt. gilead', 'Morrow', 'Mount Gilead is in Morrow County.'], ['McArthur', 'Vinton', 'McArthur is in Vinton County.'],
      ['St. Clairsville', 'Belmont', 'Saint Clairsville is in Belmont County.'], ['KETTERING, OH', 'Montgomery', 'Kettering is in Montgomery County.'],
      ['Hamilton County', 'Hamilton', 'Showing Hamilton County.'], ['43215-1234', 'Franklin', '43215 (Columbus) is in Franklin County.']]) {
      type('town', typed);
      assert.equal(d.getElementById('county').value, county, typed);
      assert(d.getElementById('townnote').textContent.startsWith(says), `${typed}: ${d.getElementById('townnote').textContent}`);
    }
    // A town that shares its name with a county somewhere else: the town wins, and the county is offered.
    type('town', 'Warren');
    assert.equal(d.getElementById('county').value, 'Trumbull');
    assert(d.querySelector('#townnote button[data-county="Warren"]'));
    // A place we do not know is not guessed at. Nothing is said until she has finished typing.
    type('town', 'Nowheresvil');
    assert.equal(d.getElementById('townnote').textContent, '');
    type('town', 'Nowheresville', 'change');
    assert.match(d.getElementById('townnote').textContent, /We do not have .Nowheresville. on our list of Ohio towns/);
    assert.equal(d.getElementById('county').value, 'Trumbull', 'an unknown place changes nothing');
    type('town', '99999', 'change');
    assert.match(d.getElementById('townnote').textContent, /We do not have ZIP code 99999/);
    // A county with no page yet says so, and shows what works statewide.
    const pick = d.getElementById('county');
    pick.value = 'Wood';
    pick.dispatchEvent(new w.Event('change', { bubbles: true }));
    assert.equal(d.getElementById('town').value, '', 'choosing from the list clears the town box');
    assert.match(d.querySelector('[data-directory-note]').textContent, /We have not added local offices for Wood County yet/);
    assert(shown().length > 60 && !shown().some((n) => /County Job and Family Services$/.test(n)));
    pick.value = '';
    pick.dispatchEvent(new w.Event('change', { bubbles: true }));
    assert.equal(shown().length, total);
    assert.deepEqual(JSON.parse(w.localStorage.getItem('om.area')), { r: 'northwest', c: 'Wood' }, '"All of Ohio" is a look around, not a new home');

    // Search: whole words from the start, everyday words, and nothing found is said plainly.
    type('find', 'rent');
    assert(shown().includes('Questions about your rights as a renter') && shown().includes('The Salvation Army: shelter and help with rent'));
    assert(!shown().includes('National Parent & Youth Helpline'), '"rent" does not match "parent"');
    type('find', 'daycare');
    assert(shown().includes('Help paying for child care'), 'an everyday word finds the listing');
    type('find', 'cardington');
    assert.deepEqual(shown(), ['Cardington Community Food Pantry']);
    type('find', 'zzzz');
    assert.equal(shown().length, 0);
    assert.match(d.querySelector('[data-directory-note]').textContent, /^Nothing matches\./);
    type('find', '');
    assert.equal(shown().length, total);
  }
  // A link can open the list on a need and a county. The saved area is where it starts otherwise.
  {
    const { d, shown, w } = await loadDirectory('#need=housing&county=Franklin');
    assert.equal(d.getElementById('county').value, 'Franklin');
    assert.equal(shown()[0], 'Homeless Hotline for Columbus and Franklin County');
    assert.equal(w.localStorage.getItem('om.area'), null, 'following a link does not change the saved area');
    const saved = await loadDirectory('', { area: { r: 'central', c: 'Knox' } });
    assert.equal(saved.d.getElementById('county').value, 'Knox');
    assert(saved.shown().includes('Knox County Job and Family Services'));
  }
  // If one page fails to load, the rest still shows, and the page says so.
  {
    const { d, shown } = await loadDirectory('', { missing: ['ohio/help/bills.html'] });
    assert(shown().length > 100);
    assert(!d.querySelector('[data-directory-status]').hidden);
    assert.match(d.querySelector('[data-directory-status]').textContent, /Some listings did not load/);
    const none = await loadDirectory('', { missing: ['ohio/assets/data.json'] });
    assert(none.d.querySelector('[data-directory-tools]').hidden && !none.d.querySelector('[data-directory-index]').hidden, 'with no data the index of links stays');
    const noPlaces = await loadDirectory('', { missing: ['ohio/assets/places.json'] });
    assert(noPlaces.d.getElementById('town').disabled, 'without the place list the town box steps aside and the county list still works');
  }
  // The built page keeps one banner, one main and headings in order.
  {
    const { d } = await loadDirectory();
    let last = 0;
    for (const h of all(d, 'h1, h2, h3, h4, h5, h6')) {
      const level = +h.tagName[1];
      assert(level <= last + 1, `"${h.textContent.trim().slice(0, 40)}" jumps from h${last} to h${level}`);
      last = level;
    }
    assert.equal(all(d, 'main').length, 1);
  }
  console.log('PASS All resources: need, county, town, ZIP code, search, links and failures');
})().catch((e) => { console.error(e); process.exit(1); });
