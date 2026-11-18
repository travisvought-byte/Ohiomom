// Deborah's jokes take turns in the picture card on the two front pages: a random one first, another about once a
// minute, and the visitor can flip back and on and stop the turning. Each joke brings its picture (her pose and
// sweater, and which of her children are around), and the picture stays out of the way.
// Run: node tests/home-extras.cjs
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), { execFileSync } = require('node:child_process'), { JSDOM } = require('jsdom');
const all = (d, sel) => [...d.querySelectorAll(sel)];
const py = (code) => execFileSync('python3', ['-c', 'import sys; sys.path.insert(0, "scripts"); import home_extras as e\n' + code], { encoding: 'utf8', maxBuffer: 1 << 26 });

// Four little stories, built by the same code that builds the pages.
const STORIES = [
  { text: 'Joke one.', cast: ['atlas', 'ephraim'], pose: 'triangle', sweater: 'plum' },
  { text: 'Joke two.', cast: [], pose: 'easy', sweater: 'bubblegum' },
  { text: 'Joke three.', cast: ['genevieve'], pose: 'warrior2', sweater: 'candy' },
  { text: 'Joke four.', cast: ['delilah'], pose: 'tree', sweater: 'heart' },
];
const card = (stories) => py(`import json
data = {"jokes": [dict(j, approved=True) for j in json.loads(${JSON.stringify(JSON.stringify(stories))})]}
jokes, looks = e.approved_jokes(data), e.approved_looks(data)
print(e.scene_block(False, jokes, "jokes.html") + e.joke_scripts(jokes, looks))`);
const TURN = Number(py('print(e.TURN_SECONDS * 1000)'));

// Open a page body and run the page's own script, with the dice, the clock and the visitor's settings in the test's hands.
// `random` near 1 leaves the jokes in the order on file, so a test can say which comes next.
// `now` is the visitor's clock: by default a weekday noon in March, when no seasonal or late-night story is in the turn.
function open(body, { random = () => 0.999999, reduce = false, now = '2027-03-10T12:00:00' } = {}) {
  const dom = new JSDOM(`<!doctype html><html lang="en"><body><main>${body}</main></body></html>`, { runScripts: 'outside-only', pretendToBeVisual: true });
  const w = dom.window, d = w.document, timers = new Map();
  let next = 1, hidden = false;
  w.Math.random = random;
  const RealDate = w.Date;
  w.Date = class extends RealDate { constructor(...a) { if (a.length) super(...a); else super(now); } };
  w.setInterval = (f, ms) => { timers.set(next, { f, ms }); return next++; };
  w.clearInterval = (id) => { timers.delete(id); };
  w.matchMedia = (q) => ({ matches: reduce && q === '(prefers-reduced-motion: reduce)' });
  Object.defineProperty(d, 'hidden', { get: () => hidden, configurable: true });
  const scripts = all(d, 'script').filter((s) => s.type !== 'application/json');
  assert.equal(scripts.length, 1, 'one script runs the card');
  w.eval(scripts[0].textContent);
  return {
    d, timers,
    minute: () => { for (const t of [...timers.values()]) t.f(); },   // one turn of the clock
    hide: (yes) => { hidden = yes; },
    tap: (sel) => d.querySelector(sel).dispatchEvent(new w.Event('click', { bubbles: true })),
  };
}
const shown = (d) => (d.getElementById('joke').hidden ? null : d.getElementById('joke-text').textContent);
// The names in an attribute (data-pose, data-kid, ...) whose parts of the drawing are showing.
const seen = (d, attr) => all(d, `svg.scene [${attr}]`).filter((el) => el.getAttribute('display') !== 'none').map((el) => el.getAttribute(attr));
const turning = (page) => page.timers.size === 1;
const button = (d) => { const b = d.getElementById('joke-pause'); return [b.getAttribute('aria-label'), all(b, '[data-icon]').filter((i) => i.getAttribute('display') !== 'none').map((i) => i.getAttribute('data-icon')).join()]; };

// 1. A visit opens on a joke picked by the dice, and every joke comes round once before any comes round again.
{
  const body = card(STORIES);
  assert.equal(shown(open(body).d), 'Joke one.');
  assert.equal(shown(open(body, { random: () => 0 }).d), 'Joke two.', 'other dice, another joke first');
  let k = 0;
  const dice = [0.3, 0.9, 0.1], page = open(body, { random: () => dice[k++ % dice.length] });
  const round = [shown(page.d)];
  for (let i = 1; i < STORIES.length; i++) { page.minute(); round.push(shown(page.d)); }
  assert.deepEqual([...round].sort(), STORIES.map((s) => s.text).sort(), 'all four, once each');
  page.minute();
  assert.equal(shown(page.d), round[0], 'then round again in the same order');
  // Before the script runs there is no empty bubble and no dead button.
  const still = new JSDOM(body).window.document;
  assert(still.getElementById('joke').hidden && still.getElementById('scene-foot').hidden, 'the bubble and the buttons wait for the script');
  assert.equal(still.getElementById('joke-text').textContent, '');
}

// 2. It turns by itself about once a minute, and only while someone can see it.
{
  const page = open(card(STORIES)), d = page.d;
  assert(turning(page), 'one timer');
  assert.equal([...page.timers.values()][0].ms, TURN);
  assert(TURN >= 45000 && TURN <= 75000, 'about a minute');
  assert.deepEqual(button(d), ['Pause the jokes', 'pause']);
  assert(!d.getElementById('scene-foot').hidden, 'the buttons show once the script is running');
  page.minute();
  assert.equal(shown(d), 'Joke two.');
  assert(!d.getElementById('joke-text').hasAttribute('aria-live'), 'a joke that turns by itself is not read out over what a screen reader is saying');
  page.hide(true); page.minute(); page.minute();
  assert.equal(shown(d), 'Joke two.', 'a tab nobody is looking at does not turn');
  page.hide(false); page.minute();
  assert.equal(shown(d), 'Joke three.');
}

// 3. The button in the bubble stops it and starts it.
{
  const page = open(card(STORIES)), d = page.d;
  page.tap('#joke-pause');
  assert(!turning(page), 'stopped');
  assert.deepEqual(button(d), ['Play the jokes', 'play'], 'the button says what it will do now');
  assert.equal(shown(d), 'Joke one.', 'stopping leaves the joke where it is');
  page.tap('#joke-pause');
  assert(turning(page) && page.timers.size === 1, 'started again, with one timer and no more');
  assert.deepEqual(button(d), ['Pause the jokes', 'pause']);
  page.minute();
  assert.equal(shown(d), 'Joke two.');
}

// 4. Back and Next flip. The reader has taken over, so the turning stops, and a screen reader hears the new joke.
{
  const page = open(card(STORIES)), d = page.d;
  page.tap('#joke-next');
  assert.equal(shown(d), 'Joke two.');
  assert(!turning(page), 'a flip stops the turning');
  assert.deepEqual(button(d), ['Play the jokes', 'play']);
  assert.equal(d.getElementById('joke-text').getAttribute('aria-live'), 'polite');
  page.tap('#joke-next'); page.tap('#joke-next');
  assert.equal(shown(d), 'Joke four.');
  page.tap('#joke-next');
  assert.equal(shown(d), 'Joke one.', 'after the last comes the first');
  page.tap('#joke-prev');
  assert.equal(shown(d), 'Joke four.', 'and before the first, the last');
  page.tap('#joke-prev');
  assert.equal(shown(d), 'Joke three.');
  // Starting it again carries on from the joke on show, and goes quiet for screen readers again.
  page.tap('#joke-pause'); page.minute();
  assert.equal(shown(d), 'Joke four.');
  assert(!d.getElementById('joke-text').hasAttribute('aria-live'));
  assert.equal(d.getElementById('joke-prev').getAttribute('aria-label'), 'Previous joke');
  assert.equal(d.getElementById('joke-next').getAttribute('aria-label'), 'Next joke');
  assert.equal(all(d, '#scene button').length, 3, 'three buttons: back, next, and stop or start');
  for (const b of all(d, '#scene button')) assert(b.getAttribute('aria-label') && b.type === 'button' && !b.closest('[aria-hidden]'), 'each is a real button with a name');
}

// 5. A device that asks for less motion is not given a card that changes by itself. The reader can still flip, and can start it.
{
  const page = open(card(STORIES), { reduce: true }), d = page.d;
  assert.equal(shown(d), 'Joke one.', 'there is still a joke');
  assert(!turning(page), 'nothing turns');
  assert.deepEqual(button(d), ['Play the jokes', 'play']);
  page.tap('#joke-next');
  assert.equal(shown(d), 'Joke two.');
  page.tap('#joke-pause');
  assert(turning(page), 'the reader can start it');
}

// 6. Each joke brings its picture: Deborah's pose and sweater, which children are around, and the caption.
{
  const tables = JSON.parse(py('import json\nprint(json.dumps({"poses": {k: e.top_move(k) for k in e.POSES}, "sweaters": e.SWEATERS, "first": [e.FIRST_POSE, e.FIRST_SWEATER]}))'));
  const body = card(STORIES);
  const fills = (d, mark) => [...new Set(all(d, `svg.scene [data-fill="${mark}"]`).map((el) => el.getAttribute('fill')))];
  const strokes = (d, mark) => [...new Set(all(d, `svg.scene [data-stroke="${mark}"]`).map((el) => el.getAttribute('stroke')))];
  const check = (d, story, label) => {
    const [wool, accent, trim, pattern] = tables.sweaters[story.sweater];
    assert.deepEqual(seen(d, 'data-kid').sort(), [...story.cast].sort(), `${label}: the children who are around`);
    assert.deepEqual([...new Set(seen(d, 'data-pose'))], [story.pose], `${label}: her arms and legs for this pose and no other`);
    assert.equal(d.querySelector('svg.scene [data-top]').getAttribute('transform') || '', tables.poses[story.pose], `${label}: her top half is moved for the pose`);
    assert.deepEqual(seen(d, 'data-pat'), pattern === 'plain' ? [] : [pattern], `${label}: the sweater's pattern`);
    assert.deepEqual(fills(d, 0), [wool], `${label}: the wool`);
    assert.deepEqual(strokes(d, 0), [wool], `${label}: the sleeves match`);
    assert.deepEqual(strokes(d, 2), [trim], `${label}: the collar`);
    for (const el of all(d, 'svg.scene [data-fill="1"]')) assert.equal(el.getAttribute('fill'), accent, `${label}: the pattern's color`);
  };
  // As written, before any script: the first pose, the first sweater, one child.
  check(new JSDOM(body).window.document, { cast: ['delilah'], pose: tables.first[0], sweater: tables.first[1] }, 'with scripts off');
  const page = open(body), d = page.d;
  check(d, STORIES[0], 'story one');
  assert.equal(d.getElementById('scene-cap').textContent, 'Deborah is working on triangle pose.', 'the caption is about Deborah, whoever is around');
  assert.match(d.getElementById('scene').style.getPropertyValue('--tail'), /^\d\d%$/, 'the tail of the joke bubble follows her head');
  page.minute();
  check(d, STORIES[1], 'story two, when the clock turns');
  assert.equal(d.getElementById('scene-cap').textContent, 'Deborah is working on easy pose.', 'Deborah alone');
  page.tap('#joke-next');
  check(d, STORIES[2], 'story three, by the button');
  assert.equal(d.getElementById('scene-cap').textContent, 'Deborah is working on warrior two.');
  page.tap('#joke-prev'); page.tap('#joke-prev');
  check(d, STORIES[0], 'back to story one: the picture goes back with the joke');
  page.tap('#joke-prev');
  check(d, STORIES[3], 'and round to the last');
  // However the dice fall, a joke and its picture stay together, whether the clock turns it or the reader does.
  const caps = { triangle: 'Deborah is working on triangle pose.', easy: 'Deborah is working on easy pose.', warrior2: 'Deborah is working on warrior two.', tree: 'Deborah is working on tree pose.' };
  const dice = [() => () => 0, () => () => 0.5, () => { let k = 0; return () => [0.7, 0.2, 0.4][k++ % 3]; }];
  for (const make of dice) {
    for (const step of [(pg) => pg.minute(), (pg) => pg.tap('#joke-next'), (pg) => pg.tap('#joke-prev')]) {
      const mixed = open(body, { random: make() }), order = [];
      for (let i = 0; i < STORIES.length; i++) {
        const story = STORIES.find((s) => s.text === shown(mixed.d));
        order.push(story.text);
        check(mixed.d, story, `shuffled, ${story.text}`);
        assert.equal(mixed.d.getElementById('scene-cap').textContent, caps[story.pose]);
        step(mixed);
      }
      assert.equal(new Set(order).size, STORIES.length, 'every story once');
      assert.notDeepEqual(order, STORIES.map((s) => s.text), 'these dice do mix the order');
    }
  }
  // The script only dresses the drawing: it adds nothing to it that a keyboard or a screen reader could land on.
  assert.equal(all(d, 'svg.scene a, svg.scene [tabindex], svg.scene [href], svg.scene title, svg.scene button').length, 0);
  assert.equal(d.querySelector('svg.scene').getAttribute('aria-hidden'), 'true');
  assert(!d.getElementById('scene-cap').closest('[aria-hidden]') && !d.getElementById('joke-text').closest('[aria-hidden]'), 'the words are for everyone');
  // A page whose picture data has lost a story still tells that story's joke, in the picture it had on.
  const holed = open(body.replace(/"easy\|bubblegum\|\|[^"]*"/, '""'));
  holed.minute();
  assert.equal(shown(holed.d), 'Joke two.');
  check(holed.d, STORIES[0], 'a joke with no picture of its own keeps the one before it');
}

// 7. The pages as built: the picture is beside the question and hidden from screen readers; the joke is in the picture
// card, as Deborah's speech bubble straight above the drawing; and every approved joke comes round with its own picture.
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
      assert.equal(box.querySelector('h2').textContent, 'Deborah’s jokes');
      const link = box.querySelector('a');
      assert.equal(link.textContent, 'All jokes');
      assert(fs.existsSync(path.join(path.dirname(file), link.getAttribute('href'))), `${file}: the list of jokes is where the link says`);
      assert.deepEqual(JSON.parse(d.getElementById('jokes-data').textContent), approved.map((j) => j.text), `${file}: the approved jokes, in the order on file`);
      // The buttons that flip lie along the floor of the drawing, with the caption between them, and wait for the script.
      const bar = d.getElementById('scene-foot');
      assert(bar && bar.hidden && bar.previousElementSibling === art[0], `${file}: the bar comes straight after the drawing and waits for the script`);
      assert.equal(bar.style.position, 'absolute', `${file}: it lies over the floor whatever stylesheet the browser kept`);
      assert.deepEqual([...bar.children].map((el) => el.id), ['joke-prev', 'scene-cap', 'joke-next'], `${file}: Back, what she is working on, Next`);
      assert(!bar.closest('[aria-hidden]'), `${file}: screen readers reach the buttons and the caption`);
      assert.equal(art[0].parentElement.id, 'scene', `${file}: the script finds the picture card by its id`);
      const scene = JSON.parse(d.getElementById('scene-data').textContent);
      assert.equal(scene.d.length, approved.length, `${file}: a picture for every joke`);
      // Every approved joke, as the page itself shows it: its own children, one pose, and what the joke asks for.
      const own = all(d, 'script').filter((x) => x.textContent.includes('"jokes-data"'));
      assert.equal(own.length, 1, `${file}: one script tells the joke and dresses the picture`);
      const page = open(art[0].parentElement.outerHTML + d.getElementById('jokes-data').outerHTML + d.getElementById('scene-data').outerHTML + own[0].outerHTML);
      // At three times of year and day: which stories are in the turn, the one in season first, each with its picture.
      const inTurn = (j, now) => {
        if (!j.when) return true;
        const t = new Date(now), [kind, from, to] = scene.s[j.when], y = kind === 'h' ? t.getHours() : (t.getMonth() + 1) * 100 + t.getDate();
        return from <= to ? y >= from && y <= to : y >= from || y <= to;
      };
      for (const now of ['2027-03-10T12:00:00', '2026-11-20T12:00:00', '2026-12-24T22:30:00', '2027-07-04T02:00:00']) {
        const page = open(art[0].parentElement.outerHTML + d.getElementById('jokes-data').outerHTML + d.getElementById('scene-data').outerHTML + own[0].outerHTML, { now });
        const order = approved.filter((j) => inTurn(j, now));
        const first = order.findIndex((j) => j.when);
        if (first > 0) [order[0], order[first]] = [order[first], order[0]];
        if (now.startsWith('2027-03')) assert(order.every((j) => !j.when), 'a March noon has only everyday stories');
        else assert(order[0].when, `${now}: the card opens on a story of the season, or of the hour`);
        order.forEach((j, i) => {
          const label = `${file} ${now} story ${i + 1}`;
          if (i) page.tap('#joke-next');
          assert.equal(shown(page.d), j.text, label);
          assert.deepEqual(seen(page.d, 'data-kid').sort(), [...(j.cast || seen(page.d, 'data-kid'))].sort(), `${label}: the children the story names`);
          assert.equal(seen(page.d, 'data-pose').length > 0 && new Set(seen(page.d, 'data-pose')).size, 1, `${label}: one pose`);
          if (j.pose) assert.equal(seen(page.d, 'data-pose')[0], j.pose, `${label}: the pose the story names`);
          const acts = seen(page.d, 'data-act');
          for (const k of seen(page.d, 'data-kid')) assert.equal(new Set(acts.filter((a) => a.startsWith(k + '.'))).size, 1, `${label}: ${k} does one thing`);
          for (const [k, a] of Object.entries(j.do || {})) assert(acts.includes(`${k}.${a}`), `${label}: ${k} is doing what the story says`);
          assert.deepEqual([...new Set(seen(page.d, 'data-when'))], j.when ? [j.when] : [], `${label}: the season's things, and only them`);
          assert.match(page.d.getElementById('scene-cap').textContent, /^Deborah is working on [a-z -]+\.$/, `${label}: a caption`);
        });
        page.tap('#joke-next');
        assert.equal(shown(page.d), order[0].text, `${now}: round again, and only the stories in the turn`);
      }
    } else {
      assert(!box && !d.getElementById('jokes-data') && !d.getElementById('scene-data') && !d.getElementById('scene-foot'),
        `${file}: no joke bubble, buttons or picture data until a joke is approved`);
    }
  }
  // The list of all the jokes is plain words: no script, no picture, nothing hidden.
  if (approved.length) {
    const d = new JSDOM(fs.readFileSync('jokes.html', 'utf8')).window.document;
    assert.deepEqual(all(d, 'ol.jokelist > li').map((li) => li.textContent), approved.map((j) => j.text));
    assert.equal(all(d, 'ol.jokelist [hidden], svg.scene, #jokes-data, #scene-data').length, 0);
  }
}

// 8. The owner's preview (scripts/joke_preview.py) runs the same picture through every joke on file.
{
  const html = py(`import json, joke_preview as jp
jokes = [("Joke A.", True, ["delilah"]), ("Joke B.", True, ["ephraim"]), ("Joke C.", False, ["atlas", "genevieve"]), ("Joke D.", False, [])]
print(jp.page({"jokes": [{"text": t, "approved": ok, "cast": cast} for t, ok, cast in jokes]}))`);
  const dom = new JSDOM(html, { runScripts: 'outside-only' });
  const d = dom.window.document;
  const run = all(d, 'script').filter((x) => x.type !== 'application/json');
  assert.equal(run.length, 1, 'the preview has one script');
  dom.window.eval(run[0].textContent);
  const tap = (sel) => d.querySelector(sel).dispatchEvent(new dom.window.Event('click', { bubbles: true }));
  const pressed = (kind) => all(d, `[aria-pressed="true"]${kind ? `[data-try="${kind}"]` : ':not([data-try="act"]):not([data-try="when"])'}`).map((b) => b.getAttribute('data-name'));
  const where = () => d.getElementById('where').textContent;
  const current = () => d.querySelector('.list button[aria-current="true"]');
  // It opens on the whole family, so every likeness can be checked at once.
  assert.deepEqual(seen(d, 'data-kid').sort(), ['atlas', 'delilah', 'ephraim', 'genevieve']);
  assert.equal(where(), 'The whole family');
  assert(!d.getElementById('joke').hidden && !d.getElementById('scene-foot').hidden);
  assert.equal(current(), null);
  // The card's own Next goes to the first joke that is waiting, then on through the approved ones, and round again.
  tap('#joke-next');
  assert.equal(shown(d), 'Joke C.');
  assert.equal(where(), 'Waiting: 1 of 2');
  assert.deepEqual(seen(d, 'data-kid').sort(), ['atlas', 'genevieve']);
  assert.equal(current().textContent.slice(0, 7), 'Joke C.');
  tap('#joke-next');
  assert.equal(shown(d), 'Joke D.');
  assert.deepEqual(seen(d, 'data-kid'), [], 'Deborah alone');
  tap('#joke-next');
  assert.equal(shown(d), 'Joke A.');
  assert.equal(where(), 'In the turn: 1 of 2');
  tap('#joke-next'); tap('#joke-next');
  assert.equal(where(), 'Waiting: 1 of 2', 'round again');
  tap('#joke-prev');
  assert.equal(where(), 'The whole family', 'Back from the first joke is the family');
  // Tapping a joke shows its picture.
  tap('.list button[data-joke="3"]');
  assert.equal(shown(d), 'Joke B.');
  assert.deepEqual(seen(d, 'data-kid'), ['ephraim']);
  // Any pose, any sweater, any child: the buttons start from the joke on show and show what is on.
  assert(pressed().includes('ephraim') && pressed().length === 3, 'one child, one pose and one sweater are marked');
  assert.equal(pressed('act').length, 4, 'and what each child is doing');
  assert.deepEqual(pressed('when'), [''], 'and that the story is for any time');
  tap('[data-try="pose"][data-name="triangle"]');
  tap('[data-try="sweater"][data-name="plum"]');
  tap('[data-try="kid"][data-name="delilah"]');
  assert.deepEqual([...new Set(seen(d, 'data-pose'))], ['triangle']);
  assert.deepEqual(seen(d, 'data-pat'), ['band']);
  assert.deepEqual(seen(d, 'data-kid').sort(), ['delilah', 'ephraim']);
  assert.deepEqual(pressed().sort(), ['delilah', 'ephraim', 'plum', 'triangle']);
  assert.equal(where(), 'Trying it out');
  assert.equal(d.getElementById('scene-cap').textContent, 'Trying triangle pose in plum.');
  // What a child is doing, and when the story is for.
  tap('[data-try="act"][data-name="delilah.juice"]');
  assert(seen(d, 'data-act').includes('delilah.juice') && !seen(d, 'data-act').includes('delilah.again'));
  assert(pressed('act').includes('delilah.juice'));
  tap('[data-try="when"][data-name="night"]');
  assert.deepEqual([...new Set(seen(d, 'data-when'))], ['night'], 'the room after bedtime');
  tap('[data-try="when"][data-name=""]');
  assert.deepEqual(seen(d, 'data-when'), []);
  tap('[data-try="kid"][data-name="ephraim"]');
  assert.deepEqual(seen(d, 'data-kid'), ['delilah'], 'tapping a child again takes him out');
  // Going back to a joke drops what was tried.
  tap('.list button[data-joke="2"]');
  assert.equal(shown(d), 'Joke A.');
  assert.deepEqual(seen(d, 'data-kid'), ['delilah']);
  assert.match(d.getElementById('scene-cap').textContent, /^Deborah is working on /);
  tap('#all');
  assert.equal(where(), 'The whole family');
  assert.equal(all(d, 'a[href^="http"], [src], link').length, 0, 'the preview loads nothing and links nowhere');
}
console.log('PASS front-page picture is decoration beside the question; Deborah\'s jokes are her speech bubble in it: a random one first, another about once a minute while the page is in view, back and next to flip, a button to stop and start, and no turning on a device that asks for less motion; every joke brings its own pose, sweater, children, what they are doing and caption; seasonal and late-night stories come out only in their time, and open the card when they do; the owner\'s preview steps through every joke with the same picture');
