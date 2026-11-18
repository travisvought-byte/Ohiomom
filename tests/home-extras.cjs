// The joke of the day changes on the visitor's own clock, the picture changes with it (Deborah's pose and sweater,
// and which of her children are in it), and the picture stays out of the way.
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
// The names in an attribute (data-pose, data-kid, ...) whose parts of the drawing are showing.
const seen = (d, attr) => all(d, `svg.scene [${attr}]`).filter((el) => el.getAttribute('display') !== 'none').map((el) => el.getAttribute(attr));

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
  assert.equal(box.querySelector('h2').textContent, 'Deborah’s joke of the day');
  assert.equal(box.querySelector('a').getAttribute('href'), 'jokes.html');
  assert.equal(box.querySelector('a').textContent, 'Earlier jokes', 'the link says where it goes, whatever a narrow phone shows of it');
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
      assert.equal(box.querySelector('h2').textContent, 'Deborah’s joke of the day');
      assert(fs.existsSync(require('node:path').join(require('node:path').dirname(file), box.querySelector('a').getAttribute('href'))), `${file}: the list of earlier jokes is where the link says`);
      assert.equal(Object.keys(JSON.parse(d.getElementById('jokes-data').textContent)).length, approved.length);
      // The caption is words, so it is outside the drawing, straight under it, and waits for the script like the joke.
      const cap = d.getElementById('scene-cap');
      assert(cap && cap.hidden && cap.matches('p.scenecap'), `${file}: the caption is there and waits for the script`);
      assert.equal(cap.previousElementSibling, art[0], `${file}: the caption sits straight under the drawing`);
      assert(!cap.closest('[aria-hidden]'), `${file}: screen readers read the caption`);
      assert.equal(art[0].parentElement.id, 'scene', `${file}: the script finds the picture card by its id`);
      const scene = JSON.parse(d.getElementById('scene-data').textContent);
      assert.deepEqual(Object.keys(scene.d).sort(), approved.map((j) => j.date).sort(), `${file}: a picture for every day that has a joke`);
      // Every approved day, as the page itself would show it: the right children, one pose, and the joke's own cast.
      const own = all(d, 'script').filter((x) => x.textContent.includes('"jokes-data"'));
      assert.equal(own.length, 1, `${file}: one script shows the joke and dresses the picture`);
      const parts = art[0].parentElement.outerHTML + d.getElementById('jokes-data').outerHTML + d.getElementById('scene-data').outerHTML + own[0].outerHTML;
      for (const j of approved) {
        const day = on(j.date, parts);
        assert.equal(day.getElementById('joke-text').textContent, j.text);
        assert.deepEqual(seen(day, 'data-kid').sort(), [...(j.cast || seen(day, 'data-kid'))].sort(), `${file} ${j.date}: the children the joke names`);
        assert.equal(seen(day, 'data-pose').length > 0 && new Set(seen(day, 'data-pose')).size, 1, `${file} ${j.date}: one pose`);
        if (j.pose) assert.equal(seen(day, 'data-pose')[0], j.pose, `${file} ${j.date}: the pose the joke names`);
        assert(day.getElementById('scene-cap').textContent.startsWith('Today Deborah is working on '), `${file} ${j.date}: a caption`);
      }
    } else {
      assert(!box && !d.getElementById('jokes-data') && !d.getElementById('scene-data') && !d.getElementById('scene-cap'),
        `${file}: no joke bubble, caption or picture data until a batch is approved`);
    }
  }
}

// 4. The picture is dressed for the day: Deborah's pose and sweater, which children are in it, who speaks, the caption.
{
  const days = [
    { date: '2030-03-30', cast: ['atlas', 'ephraim'], pose: 'triangle', sweater: 'plum' },
    { date: '2030-03-31', cast: [], pose: 'easy', sweater: 'bubblegum' },
    { date: '2030-04-01', cast: ['genevieve'], pose: 'warrior2', sweater: 'candy' },
  ];
  const tables = JSON.parse(py('import json\nprint(json.dumps({"poses": {k: e.top_move(k) for k in e.POSES}, "sweaters": e.SWEATERS, "first": [e.FIRST_POSE, e.FIRST_SWEATER]}))'));
  const body = py(`import json
data = {"jokes": [dict(j, text="Joke for " + j["date"] + ".", approved=True) for j in json.loads(${JSON.stringify(JSON.stringify(days))})]}
jokes, looks = e.approved_jokes(data), e.approved_looks(data)
print(e.scene_block(False, jokes, "jokes.html") + e.joke_scripts(jokes, looks))`);
  const fills = (d, mark) => [...new Set(all(d, `svg.scene [data-fill="${mark}"]`).map((el) => el.getAttribute('fill')))];
  const strokes = (d, mark) => [...new Set(all(d, `svg.scene [data-stroke="${mark}"]`).map((el) => el.getAttribute('stroke')))];
  const check = (d, day, label) => {
    const [wool, accent, trim, pattern] = tables.sweaters[day.sweater];
    assert.deepEqual(seen(d, 'data-kid').sort(), [...day.cast].sort(), `${label}: the children in the picture`);
    assert.deepEqual(seen(d, 'data-say'), day.cast.slice(0, 1), `${label}: only the first child named has the bubbles`);
    assert.deepEqual([...new Set(seen(d, 'data-pose'))], [day.pose], `${label}: her arms and legs for this pose and no other`);
    assert.equal(d.querySelector('svg.scene [data-top]').getAttribute('transform') || '', tables.poses[day.pose], `${label}: her top half is moved for the pose`);
    assert.deepEqual(seen(d, 'data-pat'), pattern === 'plain' ? [] : [pattern], `${label}: the sweater's pattern`);
    assert.deepEqual(fills(d, 0), [wool], `${label}: the wool`);
    assert.deepEqual(strokes(d, 0), [wool], `${label}: the sleeves match`);
    assert.deepEqual(strokes(d, 2), [trim], `${label}: the collar`);
    for (const el of all(d, `svg.scene [data-fill="1"]`)) assert.equal(el.getAttribute('fill'), accent, `${label}: the pattern's color`);
  };
  // Before the first day the picture is the one written into the page, and there is no caption.
  let d = on('2030-03-29', body);
  check(d, { cast: ['delilah'], pose: tables.first[0], sweater: tables.first[1] }, 'before the batch');
  assert(d.getElementById('scene-cap').hidden, 'no caption without a day');
  // Then each day has its own.
  d = on('2030-03-30', body);
  check(d, days[0], 'day one');
  assert.equal(d.getElementById('scene-cap').textContent, 'Today Deborah is working on triangle pose, with Atlas and Ephraim.');
  assert(!d.getElementById('scene-cap').hidden);
  assert.match(d.getElementById('scene').style.getPropertyValue('--tail'), /^\d\d%$/, 'the tail of the joke bubble follows her head');
  d = on('2030-03-31', body);
  check(d, days[1], 'day two');
  assert.equal(d.getElementById('scene-cap').textContent, 'Today Deborah is working on easy pose.', 'Deborah alone');
  d = on('2030-04-01', body);
  check(d, days[2], 'day three');
  assert.equal(d.getElementById('scene-cap').textContent, 'Today Deborah is working on warrior two. Genevieve is not impressed.');
  // When the batch has run out the pictures come round again with their jokes.
  d = on('2030-04-02', body);
  check(d, days[0], 'the day after the batch');
  assert.equal(shown(d), 'Joke for 2030-03-30.');
  d = on('2030-04-04', body);
  check(d, days[2], 'three days after the batch');
  assert.equal(shown(d), 'Joke for 2030-04-01.');
  // The script only dresses the drawing: it adds nothing to the page that a keyboard or a screen reader could land on.
  assert.equal(all(d, 'svg.scene a, svg.scene [tabindex], svg.scene [href], svg.scene title').length, 0);
  assert.equal(d.querySelector('svg.scene').getAttribute('aria-hidden'), 'true');
  // A page with jokes and no picture (the list of earlier jokes) runs the same script without complaint.
  assert.doesNotThrow(() => on('2030-03-31', listing(BATCH)));
  // And a front page whose picture data is missing a day still shows that day's joke.
  const holed = on('2030-03-31', body.replace(/"2030-03-31": "easy\|[^"]*", /, ''));
  assert.equal(shown(holed), 'Joke for 2030-03-31.');
  check(holed, { cast: ['delilah'], pose: tables.first[0], sweater: tables.first[1] }, 'a day with no picture of its own keeps the one in the page');
}
// 5. The owner's preview of a waiting batch (scripts/joke_preview.py) runs the same picture through every day on file.
{
  const html = py(`import json, joke_preview as jp
days = [("2030-03-30", True, ["delilah"]), ("2030-03-31", True, ["ephraim"]), ("2030-04-01", False, ["atlas", "genevieve"]), ("2030-04-02", False, [])]
print(jp.page({"jokes": [{"date": d, "text": "Joke for " + d + ".", "approved": ok, "cast": cast} for d, ok, cast in days]}))`);
  const dom = new JSDOM(html, { runScripts: 'outside-only' });
  const d = dom.window.document;
  const run = all(d, 'script').filter((x) => x.type !== 'application/json');
  assert.equal(run.length, 1, 'the preview has one script');
  dom.window.eval(run[0].textContent);
  const tap = (sel) => d.querySelector(sel).dispatchEvent(new dom.window.Event('click', { bubbles: true }));
  const pressed = () => all(d, '[aria-pressed="true"]').map((b) => b.getAttribute('data-name'));
  const where = () => d.getElementById('where').textContent;
  // It opens on the whole family, so every likeness can be checked at once.
  assert.deepEqual(seen(d, 'data-kid').sort(), ['atlas', 'delilah', 'ephraim', 'genevieve']);
  assert.equal(where(), 'The whole family');
  assert(!d.getElementById('joke').hidden && !d.getElementById('scene-cap').hidden);
  // Next goes to the first joke that is waiting, then on through the approved ones, and round again.
  tap('#next');
  assert.equal(shown(d), 'Joke for 2030-04-01.');
  assert.equal(where(), 'Waiting: 1 of 2');
  assert.deepEqual(seen(d, 'data-kid').sort(), ['atlas', 'genevieve']);
  assert.deepEqual(seen(d, 'data-say'), ['atlas']);
  assert.equal(d.querySelector('.list button[aria-current="true"]').getAttribute('data-day'), '2030-04-01');
  tap('#next');
  assert.equal(shown(d), 'Joke for 2030-04-02.');
  assert.deepEqual(seen(d, 'data-kid'), [], 'a day with Deborah alone');
  tap('#next');
  assert.equal(shown(d), 'Joke for 2030-03-30.');
  assert.equal(where(), 'Approved: 1 of 2');
  tap('#next'); tap('#next');
  assert.equal(where(), 'Waiting: 1 of 2', 'round again');
  tap('#prev');
  assert.equal(where(), 'The whole family', 'Back from the first day is the family');
  // Tapping a joke shows its picture.
  tap('.list button[data-day="2030-03-31"]');
  assert.equal(shown(d), 'Joke for 2030-03-31.');
  assert.deepEqual(seen(d, 'data-kid'), ['ephraim']);
  // Any pose, any sweater, any child: the buttons start from the day on show and show what is on.
  assert(pressed().includes('ephraim') && pressed().length === 3, 'one child, one pose and one sweater are marked');
  tap('[data-try="pose"][data-name="triangle"]');
  tap('[data-try="sweater"][data-name="plum"]');
  tap('[data-try="kid"][data-name="delilah"]');
  assert.deepEqual([...new Set(seen(d, 'data-pose'))], ['triangle']);
  assert.deepEqual(seen(d, 'data-pat'), ['band']);
  assert.deepEqual(seen(d, 'data-kid').sort(), ['delilah', 'ephraim']);
  assert.deepEqual(pressed().sort(), ['delilah', 'ephraim', 'plum', 'triangle']);
  assert.equal(where(), 'Trying it out');
  assert.equal(d.getElementById('scene-cap').textContent, 'Trying it out: triangle pose, the plum sweater.');
  tap('[data-try="kid"][data-name="ephraim"]');
  assert.deepEqual(seen(d, 'data-kid'), ['delilah'], 'tapping a child again takes him out');
  // Going back to a day drops what was tried.
  tap('.list button[data-day="2030-03-30"]');
  assert.deepEqual(seen(d, 'data-kid'), ['delilah']);
  assert.equal(d.getElementById('scene-cap').textContent.slice(0, 28), 'Today Deborah is working on ');
  tap('#all');
  assert.equal(where(), 'The whole family');
  assert.equal(all(d, 'a[href^="http"], [src], link').length, 0, 'the preview loads nothing and links nowhere');
}
console.log('PASS front-page picture is decoration beside the question; the joke is Deborah\'s speech bubble in it, follows the visitor\'s date, repeats when a batch runs out, and waits for approval; her pose, her sweater, the children and the caption follow the same day; the owner\'s preview steps through every day with the same picture');
