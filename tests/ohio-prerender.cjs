// The events and groups written into the Ohio pages (scripts/prerender_ohio.py) must be exactly
// what the page script draws for the same day, so a visitor never sees the list change shape
// and a search engine reads what people read.
const assert = require('assert');
const fs = require('fs');
const { JSDOM } = require('jsdom');

const site = fs.readFileSync('ohio/assets/site.js', 'utf8');
const data = fs.readFileSync('ohio/assets/data.json', 'utf8');
const strip = (s) => s.replace(/<!--prerender:[^>]*-->|<!--\/prerender-->/g, '');
const tick = () => new Promise((r) => setTimeout(r, 0));

(async () => {
  const blocks = { 'ohio/events.html': ['[data-events="all"]', '[data-groups="calendar"]'], 'ohio/connect.html': ['[data-groups="sections"]'] };
  for (const [file, selectors] of Object.entries(blocks)) {
    const src = fs.readFileSync(file, 'utf8');
    const asOf = (src.match(/<!--prerender:[a-z-]+ as of (\d{4}-\d{2}-\d{2})-->/) || [])[1];
    assert(asOf, `${file}: the lists are written into the page`);
    const written = new JSDOM(src).window.document;
    const dom = new JSDOM(src, { url: 'https://example.org/' + file, runScripts: 'outside-only' });
    const w = dom.window;
    const [y, m, d] = asOf.split('-').map(Number);
    // The page script reads the date from Date(); fix it to the day the lists were written.
    w.eval(`(() => { const R = Date; const t = new R(${y}, ${m - 1}, ${d}, 12).getTime();
      Date = class extends R { constructor(...a) { super(...(a.length ? a : [t])); } static now() { return t; } }; })()`);
    w.matchMedia = () => ({ matches: false });
    w.fetch = () => Promise.resolve({ json: () => Promise.resolve(JSON.parse(data)) });
    w.eval(site);
    for (let i = 0; i < 8; i++) await tick();
    const more = w.document.querySelector('[data-show-all]');
    if (more) more.dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
    for (const sel of selectors) {
      const a = strip(written.querySelector(sel).innerHTML);
      const b = w.document.querySelector(sel).innerHTML;
      assert(a.length > 500, `${file} ${sel}: the list is written into the page`);
      assert.equal(a, b, `${file} ${sel}: the written list matches what the page script draws`);
    }
  }
  console.log('PASS OhioMom events and groups are in the page and match what the script draws');
})().catch((e) => { console.error(e); process.exit(1); });
