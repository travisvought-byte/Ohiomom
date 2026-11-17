// The joke of the day changes on the visitor's own clock, and the picture stays out of the way.
// Run: node tests/home-extras.cjs
const assert = require('node:assert/strict'), fs = require('node:fs'), { execFileSync } = require('node:child_process'), { JSDOM } = require('jsdom');
const all = (d, sel) => [...d.querySelectorAll(sel)];
const py = (code) => execFileSync('python3', ['-c', 'import sys; sys.path.insert(0, "scripts"); import home_extras as e\n' + code], { encoding: 'utf8' });

// A batch of three jokes, built by the same code that builds the pages.
const front = (dates) => py(`jokes = {d: "Joke for " + d + "." for d in ${JSON.stringify(dates)}}\nprint(e.joke_bubble(jokes, "jokes.html") + e.joke_scripts(jokes))`);
const listing = (dates) => py(`jokes = {d: "Joke for " + d + "." for d in ${JSON.stringify(dates)}}\nprint(e.joke_list(jokes) + e.joke_scripts(jokes))`);
const BATCH = ['2030-03-30', '2030-03-31', '2030-04-01'];

// Load a page body as it stands on the given day, and run the page's own script.
function on(day, body) {
  const dom = new JSDOM(`<!doctype html><html lang="en"><body><main>${body}</main></body></html>`, { runScripts: 'outside-only' });
  const w = dom.window, [y, m, d] = day.split('-').map(Number);
  const Real = w.Date;
  w.Date = class extends Real { constructor(...a) { if (a.length) super(...a); else super(y, m - 1, d, 12, 0, 0); } };
  const scripts = all(w.document, 'script').filter((s) => s.type !== 'application/json');
  assert.equal(scripts.length, 1, 'one script runs the joke');
  w.eval(scripts[0].textContent);
  return w.document;
}
const shown = (d) => (d.getElementById('joke').hidden ? null : d.getElementById('joke-text').textContent);

// 1. On a front page: nothing before the batch starts, then each day's own joke.
{
  const body = front(BATCH);
  assert.equal(shown(on('2030-03-29', body)), null, 'no joke before the first day, and no empty box');
  assert.equal(shown(on('2030-03-30', body)), 'Joke for 2030-03-30.');
  assert.equal(shown(on('2030-03-31', body)), 'Joke for 2030-03-31.', 'the joke changes with the date, across a month end too');
  assert.equal(shown(on('2030-04-01', body)), 'Joke for 2030-04-01.');
  // When the batch has run out the list starts over, one a day, so the page never goes blank.
  assert.equal(shown(on('2030-04-02', body)), 'Joke for 2030-03-30.');
  assert.equal(shown(on('2030-04-03', body)), 'Joke for 2030-03-31.');
  assert.equal(shown(on('2030-04-04', body)), 'Joke for 2030-04-01.');
  assert.equal(shown(on('2030-04-05', body)), 'Joke for 2030-03-30.');
  assert.equal(shown(on('2031-01-01', body)), shown(on('2031-01-04', body)), 'a year on, it still turns over every three days');
  assert.notEqual(shown(on('2031-01-01', body)), shown(on('2031-01-02', body)));
  // A day with no joke of its own keeps the one before it.
  const gap = front(['2030-03-30', '2030-04-01']);
  assert.equal(shown(on('2030-03-31', gap)), 'Joke for 2030-03-30.');
  // The bubble is a heading, the joke and a link to the list, and it starts hidden.
  const d = new JSDOM(body).window.document;
  const box = d.getElementById('joke');
  assert(box.hidden && box.matches('div.saying'), 'hidden until the script has a joke for today');
  assert.equal(box.querySelector('h2').textContent, 'Mom joke of the day');
  assert.equal(box.querySelector('a').getAttribute('href'), 'jokes.html');
  assert.equal(all(box, '.card, .tile, form, input, button, img').length, 0, 'the joke is words and one link');
}

// 2. On the list page: only the jokes that have run, newest first.
{
  const body = listing(BATCH);
  const visible = (d) => all(d, '#joke-list li').filter((li) => !li.hidden).map((li) => li.getAttribute('data-date'));
  let d = on('2030-03-29', body);
  assert.deepEqual(visible(d), []);
  assert(!d.getElementById('joke-none').hidden, 'says so when none have run yet');
  d = on('2030-03-31', body);
  assert.deepEqual(visible(d), ['2030-03-31', '2030-03-30'], 'tomorrow\'s joke is not given away');
  assert(d.getElementById('joke-none').hidden);
  assert.deepEqual(visible(on('2030-06-01', body)), ['2030-04-01', '2030-03-31', '2030-03-30']);
  assert.equal(all(new JSDOM(body).window.document, '#joke-list li').filter((li) => !li.hidden).length, 0, 'every row waits for the script');
}

// 3. The pages as built: the picture is beside the question and hidden from screen readers; the joke is in the picture
// card, as the mom's speech bubble straight above the drawing, once a batch is approved.
{
  const approved = JSON.parse(fs.readFileSync('data/jokes.json', 'utf8')).jokes.filter((j) => j.approved === true);
  for (const file of ['index.html', 'ohio/index.html']) {
    const d = new JSDOM(fs.readFileSync(file, 'utf8')).window.document;
    const art = all(d, 'svg.scene');
    assert.equal(art.length, 1, `${file}: one picture`);
    assert.equal(art[0].getAttribute('aria-hidden'), 'true', `${file}: the picture is decoration`);
    assert(art[0].closest('.hero.home .herotop > .scenebox'), `${file}: the picture sits beside the question`);
    assert.equal(all(art[0], 'a, [tabindex], [href]').length, 0, `${file}: nothing in the picture takes the keyboard`);
    const top = d.querySelector('.herotop');
    assert.equal(top.firstElementChild.className, 'herotext', `${file}: the question is first in reading order`);
    assert(top.querySelector('.herotext > h1') && top.querySelector('.herotext > .lede'), `${file}: the question and its line`);
    assert(top.nextElementSibling.matches('.tiles'), `${file}: the choices follow at once`);
    assert.equal(all(d, 'main > section').length, 2, `${file}: the joke adds no section of its own`);
    const box = d.getElementById('joke');
    if (approved.length) {
      assert(box && box.hidden, `${file}: the joke bubble is there and waits for the script`);
      assert.equal(box.parentElement, art[0].parentElement, `${file}: the joke is in the picture card`);
      assert.equal(box.nextElementSibling, art[0], `${file}: the bubble sits straight above the drawing`);
      assert(!box.closest('[aria-hidden]'), `${file}: screen readers read the joke; only the drawing is hidden from them`);
      assert.equal(box.querySelector('h2').textContent, 'Mom joke of the day');
      assert(fs.existsSync(require('node:path').join(require('node:path').dirname(file), box.querySelector('a').getAttribute('href'))), `${file}: the list of earlier jokes is where the link says`);
      assert.equal(Object.keys(JSON.parse(d.getElementById('jokes-data').textContent)).length, approved.length);
    } else {
      assert(!box && !d.getElementById('jokes-data'), `${file}: no joke bubble until a batch is approved`);
    }
  }
}
console.log('PASS front-page picture is decoration beside the question; the joke is the mom\'s speech bubble in it, follows the visitor\'s date, repeats when a batch runs out, and waits for approval');
