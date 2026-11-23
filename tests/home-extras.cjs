// The daily affirmation is Deborah's speech bubble in the picture card on the two front pages: one a day, picked by the
// visitor's own date, and the visitor can flip back and on to read others. Nothing turns by itself. Each affirmation
// brings its picture (her pose and sweater, and which of her children are around), and the picture stays out of the way.
// Run: node tests/home-extras.cjs
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), { execFileSync } = require('node:child_process'), { JSDOM } = require('jsdom');
const all = (d, sel) => [...d.querySelectorAll(sel)];
const py = (code) => execFileSync('python3', ['-c', 'import sys; sys.path.insert(0, "scripts"); import home_extras as e\n' + code], { encoding: 'utf8', maxBuffer: 1 << 26 });

// Four little stories, built by the same code that builds the pages.
const STORIES = [
  { text: 'Kind word one.', cast: ['atlas', 'ephraim'], pose: 'triangle', sweater: 'plum' },
  { text: 'Kind word two.', cast: [], pose: 'easy', sweater: 'bubblegum' },
  { text: 'Kind word three.', cast: ['genevieve'], pose: 'warrior2', sweater: 'candy' },
  { text: 'Kind word four.', cast: ['delilah'], pose: 'tree', sweater: 'heart' },
];
const card = (stories) => py(`import json
data = {"affirmations": [dict(j, approved=True) for j in json.loads(${JSON.stringify(JSON.stringify(stories))})]}
sayings, looks = e.approved_affirmations(data), e.approved_looks(data)
print(e.scene_block(False, sayings, "affirmations.html", "help.html#take-care") + e.affirmation_scripts(sayings, looks))`);

// Open a page body and run the page's own script, with the clock and the visitor's settings in the test's hands.
// `now` is the visitor's clock: by default a weekday noon in March, when no seasonal or late-night story is in the turn.
// Any timer the script asks for is counted, so a test can say there are none.
function open(body, { reduce = false, now = '2027-03-10T12:00:00' } = {}) {
  const dom = new JSDOM(`<!doctype html><html lang="en"><body><main>${body}</main></body></html>`, { runScripts: 'outside-only', pretendToBeVisual: true });
  const w = dom.window, d = w.document, timers = [];
  const RealDate = w.Date;
  w.Date = class extends RealDate { constructor(...a) { if (a.length) super(...a); else super(now); } };
  w.setInterval = (f, ms) => { timers.push(ms); return timers.length; };
  w.setTimeout = (f, ms) => { timers.push(ms); return timers.length; };
  w.matchMedia = (q) => ({ matches: reduce && q === '(prefers-reduced-motion: reduce)' });
  const scripts = all(d, 'script').filter((s) => s.type !== 'application/json');
  assert.equal(scripts.length, 1, 'one script runs the card');
  w.eval(scripts[0].textContent);
  return { d, timers, tap: (sel) => d.querySelector(sel).dispatchEvent(new w.Event('click', { bubbles: true })) };
}
const shown = (d) => (d.getElementById('affirm').hidden ? null : d.getElementById('affirm-text').textContent);
// The names in an attribute (data-pose, data-kid, ...) whose parts of the drawing are showing.
const seen = (d, attr) => all(d, `svg.scene [${attr}]`).filter((el) => el.getAttribute('display') !== 'none').map((el) => el.getAttribute(attr));
// The day number the page counts from: days since 1 January 1970 on the visitor's own calendar.
const dayOf = (now) => { const t = new Date(now); return Math.floor(Date.UTC(t.getFullYear(), t.getMonth(), t.getDate()) / 864e5); };

// 1. One a day, by the visitor's date: everyone sees the same one on the same day, and the next day brings the next.
{
  const body = card(STORIES);
  const days = ['2027-03-10', '2027-03-11', '2027-03-12', '2027-03-13', '2027-03-14'];
  const seenDays = days.map((day) => shown(open(body, { now: day + 'T12:00:00' }).d));
  const first = dayOf('2027-03-10T12:00:00') % STORIES.length;
  assert.deepEqual(seenDays, days.map((_, i) => STORIES[(first + i) % STORIES.length].text), 'the next day, the next one, and round again');
  assert.equal(shown(open(body, { now: '2027-03-10T00:05:00' }).d), seenDays[0], 'just after midnight');
  assert.equal(shown(open(body, { now: '2027-03-10T20:55:00' }).d), seenDays[0], 'and late in the evening: one all day');
  // Before the script runs there is no empty bubble and no dead button.
  const still = new JSDOM(body).window.document;
  assert(still.getElementById('affirm').hidden && still.getElementById('scene-foot').hidden, 'the bubble and the buttons wait for the script');
  assert.equal(still.getElementById('affirm-text').textContent, '');
}

// 2. Nothing turns by itself, so nothing needs a stop button.
{
  const page = open(card(STORIES)), d = page.d;
  assert.deepEqual(page.timers, [], 'no timer of any kind');
  assert(!d.getElementById('scene-foot').hidden, 'the buttons show once the script is running');
  assert(!d.getElementById('affirm-text').hasAttribute('aria-live'), 'the day\'s affirmation is read in its place, not announced');
  assert.equal(d.getElementById('affirm-pause'), null);
  // One gentle line under it points to the site's own page of people to talk to.
  const help = d.querySelector('#affirm .sayhelp a');
  assert.equal(help.textContent, 'Find someone to talk to');
  assert.equal(help.getAttribute('href'), 'help.html#take-care');
}

// 3. Back and Next flip, and a screen reader hears the new one.
{
  const page = open(card(STORIES), { now: '2027-03-10T12:00:00' }), d = page.d, start = dayOf('2027-03-10T12:00:00') % STORIES.length;
  const at = (k) => STORIES[((start + k) % STORIES.length + STORIES.length) % STORIES.length].text;
  page.tap('#affirm-next');
  assert.equal(shown(d), at(1));
  assert.equal(d.getElementById('affirm-text').getAttribute('aria-live'), 'polite');
  page.tap('#affirm-next'); page.tap('#affirm-next'); page.tap('#affirm-next');
  assert.equal(shown(d), at(0), 'after the last comes the first');
  page.tap('#affirm-prev');
  assert.equal(shown(d), at(-1), 'and before the first, the last');
  assert.deepEqual(page.timers, []);
  assert.equal(d.getElementById('affirm-prev').getAttribute('aria-label'), 'Previous affirmation');
  assert.equal(d.getElementById('affirm-next').getAttribute('aria-label'), 'Next affirmation');
  assert.equal(all(d, '#scene button').length, 2, 'two buttons: back and next');
  for (const b of all(d, '#scene button')) assert(b.getAttribute('aria-label') && b.type === 'button' && !b.closest('[aria-hidden]'), 'each is a real button with a name');
}

// 4. A device that asks for less motion gets the same day's affirmation, and can still flip.
{
  const page = open(card(STORIES), { reduce: true }), d = page.d, start = dayOf('2027-03-10T12:00:00') % STORIES.length;
  assert.equal(shown(d), STORIES[start].text, 'the same one');
  page.tap('#affirm-next');
  assert.equal(shown(d), STORIES[(start + 1) % STORIES.length].text);
}

// 6. Each affirmation brings its picture: Deborah's pose and sweater, which children are around, and the caption.
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
  // On a day that opens on story one, the stories come round in order as the reader flips, each with its picture.
  const one = ['2027-03-10', '2027-03-11', '2027-03-12', '2027-03-13'].map((x) => x + 'T12:00:00').find((x) => dayOf(x) % STORIES.length === 0);
  const page = open(body, { now: one }), d = page.d;
  check(d, STORIES[0], 'story one');
  assert.equal(d.getElementById('scene-cap').textContent, 'Deborah is working on triangle pose.', 'the caption is about Deborah, whoever is around');
  assert.match(d.getElementById('scene').style.getPropertyValue('--tail'), /^\d\d%$/, 'the tail of the bubble follows her head');
  page.tap('#affirm-next');
  check(d, STORIES[1], 'story two');
  assert.equal(d.getElementById('scene-cap').textContent, 'Deborah is working on easy pose.', 'Deborah alone');
  page.tap('#affirm-next');
  check(d, STORIES[2], 'story three');
  assert.equal(d.getElementById('scene-cap').textContent, 'Deborah is working on warrior two.');
  page.tap('#affirm-prev'); page.tap('#affirm-prev');
  check(d, STORIES[0], 'back to story one: the picture goes back with the words');
  page.tap('#affirm-prev');
  check(d, STORIES[3], 'and round to the last');
  // Whatever the day, an affirmation and its picture stay together, whichever way the reader flips.
  const caps = { triangle: 'Deborah is working on triangle pose.', easy: 'Deborah is working on easy pose.', warrior2: 'Deborah is working on warrior two.', tree: 'Deborah is working on tree pose.' };
  for (const day of ['2027-03-10', '2027-03-11', '2027-03-12', '2027-03-13']) {
    for (const step of ['#affirm-next', '#affirm-prev']) {
      const other = open(body, { now: day + 'T12:00:00' }), order = [];
      for (let i = 0; i < STORIES.length; i++) {
        const story = STORIES.find((s) => s.text === shown(other.d));
        order.push(story.text);
        check(other.d, story, `${day}, ${story.text}`);
        assert.equal(other.d.getElementById('scene-cap').textContent, caps[story.pose]);
        other.tap(step);
      }
      assert.equal(new Set(order).size, STORIES.length, 'every story once');
    }
  }
  // The script only dresses the drawing: it adds nothing to it that a keyboard or a screen reader could land on.
  assert.equal(all(d, 'svg.scene a, svg.scene [tabindex], svg.scene [href], svg.scene title, svg.scene button').length, 0);
  assert.equal(d.querySelector('svg.scene').getAttribute('aria-hidden'), 'true');
  assert(!d.getElementById('scene-cap').closest('[aria-hidden]') && !d.getElementById('affirm-text').closest('[aria-hidden]'), 'the words are for everyone');
  // A page whose picture data has lost a story still gives that story's words, in the picture it had on.
  const holed = open(body.replace(/"easy\|bubblegum\|\|[^"]*"/, '""'), { now: one });
  holed.tap('#affirm-next');
  assert.equal(shown(holed.d), 'Kind word two.');
  check(holed.d, STORIES[0], 'an affirmation with no picture of its own keeps the one before it');
}

// 7. The pages as built: the picture is beside the question and hidden from screen readers; the affirmation is in the
// picture card, as Deborah's speech bubble straight above the drawing; and every approved one comes round with its own picture.
{
  const approved = JSON.parse(fs.readFileSync('data/affirmations.json', 'utf8')).affirmations.filter((j) => j.approved === true);
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
    // The choices follow at once: "I'm..." (who she is), then the tiles (what she needs).
    assert(top.nextElementSibling.matches('nav.iam'), `${file}: the "I'm..." chooser follows the question`);
    assert(top.nextElementSibling.nextElementSibling.matches('.tiles'), `${file}: the choices follow at once`);
    assert(all(top.nextElementSibling, 'a').length >= 6, `${file}: the chooser offers several ways in`);
    assert.equal(all(d, 'main > section').length, 2, `${file}: the affirmation adds no section of its own`);
    const box = d.getElementById('affirm');
    if (approved.length) {
      assert(box && box.hidden, `${file}: the bubble is there and waits for the script`);
      assert.equal(box.parentElement, art[0].parentElement, `${file}: the affirmation is in the picture card`);
      assert.equal(box.nextElementSibling, art[0], `${file}: the bubble sits straight above the drawing`);
      assert(!box.closest('[aria-hidden]'), `${file}: screen readers read the affirmation; only the drawing is hidden from them`);
      assert.equal(box.querySelector('h2').textContent, 'A kind word for today');
      const link = box.querySelector('.sayinghead a');
      assert.equal(link.textContent, 'More kind words');
      assert(fs.existsSync(path.join(path.dirname(file), link.getAttribute('href'))), `${file}: the list is where the link says`);
      // One gentle line under the affirmation points to the page of people to talk to that the site already has.
      const help = box.querySelector('.sayhelp a');
      const [target, hash] = help.getAttribute('href').split('#');
      assert.equal(target, file === 'index.html' ? 'help.html' : 'wellbeing.html', `${file}: the site's own page of people to talk to`);
      const there = new JSDOM(fs.readFileSync(path.join(path.dirname(file), target), 'utf8')).window.document;
      if (hash) assert(there.getElementById(hash), `${file}: #${hash} is on ${target}`);
      assert(there.querySelector('a[href="tel:988"]'), `${file}: that page has the crisis line`);
      assert.deepEqual(JSON.parse(d.getElementById('affirmations-data').textContent), approved.map((j) => j.text), `${file}: the approved affirmations, in the order on file`);
      // The buttons that flip lie along the floor of the drawing, with the caption between them, and wait for the script.
      const bar = d.getElementById('scene-foot');
      assert(bar && bar.hidden && bar.previousElementSibling === art[0], `${file}: the bar comes straight after the drawing and waits for the script`);
      assert.equal(bar.style.position, 'absolute', `${file}: it lies over the floor whatever stylesheet the browser kept`);
      assert.deepEqual([...bar.children].map((el) => el.id), ['affirm-prev', 'scene-cap', 'affirm-next'], `${file}: Back, what she is working on, Next`);
      assert(!bar.closest('[aria-hidden]'), `${file}: screen readers reach the buttons and the caption`);
      assert.equal(art[0].parentElement.id, 'scene', `${file}: the script finds the picture card by its id`);
      const scene = JSON.parse(d.getElementById('scene-data').textContent);
      assert.equal(scene.d.length, approved.length, `${file}: a picture for every affirmation`);
      // Every approved affirmation, as the page itself shows it: its own children, one pose, and what the story asks for.
      const own = all(d, 'script').filter((x) => x.textContent.includes('"affirmations-data"'));
      assert.equal(own.length, 1, `${file}: one script shows the affirmation and dresses the picture`);
      const page = open(art[0].parentElement.outerHTML + d.getElementById('affirmations-data').outerHTML + d.getElementById('scene-data').outerHTML + own[0].outerHTML);
      // At three times of year and day: which stories are in the turn, the day's one first (one of the season or the
      // hour when there are any), then the rest in the order on file, each with its picture.
      const inTurn = (j, now) => {
        if (!j.when) return true;
        const t = new Date(now), [kind, from, to] = scene.s[j.when], y = kind === 'h' ? t.getHours() : (t.getMonth() + 1) * 100 + t.getDate();
        return from <= to ? y >= from && y <= to : y >= from || y <= to;
      };
      for (const now of ['2027-03-10T12:00:00', '2026-11-20T12:00:00', '2026-12-24T22:30:00', '2027-07-04T02:00:00']) {
        const page = open(art[0].parentElement.outerHTML + d.getElementById('affirmations-data').outerHTML + d.getElementById('scene-data').outerHTML + own[0].outerHTML, { now });
        const inOrder = approved.filter((j) => inTurn(j, now)), special = inOrder.filter((j) => j.when), everyday = inOrder.filter((j) => !j.when);
        const today = special.length ? special[dayOf(now) % special.length] : everyday[dayOf(now) % everyday.length];
        const k = inOrder.indexOf(today), order = inOrder.slice(k).concat(inOrder.slice(0, k));
        if (now.startsWith('2027-03')) assert(order.every((j) => !j.when), 'a March noon has only everyday stories');
        else assert(order[0].when, `${now}: the card opens on a story of the season, or of the hour`);
        order.forEach((j, i) => {
          const label = `${file} ${now} story ${i + 1}`;
          if (i) page.tap('#affirm-next');
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
        page.tap('#affirm-next');
        assert.equal(shown(page.d), order[0].text, `${now}: round again, and only the stories in the turn`);
      }
    } else {
      assert(!box && !d.getElementById('affirmations-data') && !d.getElementById('scene-data') && !d.getElementById('scene-foot'),
        `${file}: no bubble, buttons or picture data until an affirmation is approved`);
    }
  }
  // The list of all the affirmations is plain words: no script, no picture, nothing hidden.
  if (approved.length) {
    const d = new JSDOM(fs.readFileSync('affirmations.html', 'utf8')).window.document;
    assert.deepEqual(all(d, 'ol.affirmlist > li').map((li) => li.textContent), approved.map((j) => j.text));
    assert.equal(all(d, 'ol.affirmlist [hidden], svg.scene, #affirmations-data, #scene-data').length, 0);
  }
}

// 8. The owner's preview (scripts/affirmation_preview.py) runs the same picture through every affirmation on file.
{
  const html = py(`import json, affirmation_preview as jp
sayings = [("Word A.", True, ["delilah"]), ("Word B.", True, ["ephraim"]), ("Word C.", False, ["atlas", "genevieve"]), ("Word D.", False, [])]
print(jp.page({"affirmations": [{"text": t, "approved": ok, "cast": cast} for t, ok, cast in sayings]}))`);
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
  assert(!d.getElementById('affirm').hidden && !d.getElementById('scene-foot').hidden);
  assert.equal(current(), null);
  // The card's own Next goes to the first affirmation that is waiting, then on through the approved ones, and round again.
  tap('#affirm-next');
  assert.equal(shown(d), 'Word C.');
  assert.equal(where(), 'Waiting: 1 of 2');
  assert.deepEqual(seen(d, 'data-kid').sort(), ['atlas', 'genevieve']);
  assert.equal(current().textContent.slice(0, 7), 'Word C.');
  tap('#affirm-next');
  assert.equal(shown(d), 'Word D.');
  assert.deepEqual(seen(d, 'data-kid'), [], 'Deborah alone');
  tap('#affirm-next');
  assert.equal(shown(d), 'Word A.');
  assert.equal(where(), 'In the turn: 1 of 2');
  tap('#affirm-next'); tap('#affirm-next');
  assert.equal(where(), 'Waiting: 1 of 2', 'round again');
  tap('#affirm-prev');
  assert.equal(where(), 'The whole family', 'Back from the first one is the family');
  // Tapping one shows its picture.
  tap('.list button[data-item="3"]');
  assert.equal(shown(d), 'Word B.');
  assert.deepEqual(seen(d, 'data-kid'), ['ephraim']);
  // Any pose, any sweater, any child: the buttons start from the affirmation on show and show what is on.
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
  assert(seen(d, 'data-act').includes('delilah.juice') && !seen(d, 'data-act').includes('delilah.hug'));
  assert(pressed('act').includes('delilah.juice'));
  tap('[data-try="when"][data-name="night"]');
  assert.deepEqual([...new Set(seen(d, 'data-when'))], ['night'], 'the room after bedtime');
  tap('[data-try="when"][data-name=""]');
  assert.deepEqual(seen(d, 'data-when'), []);
  tap('[data-try="kid"][data-name="ephraim"]');
  assert.deepEqual(seen(d, 'data-kid'), ['delilah'], 'tapping a child again takes him out');
  // Going back to one drops what was tried.
  tap('.list button[data-item="2"]');
  assert.equal(shown(d), 'Word A.');
  assert.deepEqual(seen(d, 'data-kid'), ['delilah']);
  assert.match(d.getElementById('scene-cap').textContent, /^Deborah is working on /);
  tap('#all');
  assert.equal(where(), 'The whole family');
  assert.equal(all(d, 'a[href^="http"], [src], link').length, 0, 'the preview loads nothing and links nowhere');
}
// 9. Every location page (each state, country and county page, the hand-kept Ohio county pages included) carries the
// same day's affirmation as the front page, with the same Back and Next, even a country with few listings. Seasonal and
// late-night ones keep to their time there too.
{
  const ROOT = path.join(__dirname, '..');
  const built = (rel) => {
    const d = new JSDOM(fs.readFileSync(path.join(ROOT, rel), 'utf8')).window.document;
    const box = d.getElementById('scene') || d.getElementById('affirm');
    assert(box, `${rel}: the affirmation card is on the page`);
    // A location page loads the card's script from one file of the site's own, and a country page in another language
    // first loads that one language's affirmations from a file of its own.
    const srcs = all(d, 'script[src]').map((el) => el.getAttribute('src'));
    const file = srcs.filter((src) => src.endsWith('/kindword.js') || src === 'kindword.js');
    const local = srcs.filter((src) => /kindword\/[^/]+\.js$/.test(src));
    if (!d.getElementById('scene')) {
      assert.equal(file.length, 1, `${rel}: the card's script`);
      assert(local.length <= 1, `${rel}: at most one language's file`);
      if (local.length) assert(srcs.indexOf(local[0]) < srcs.indexOf(file[0]), `${rel}: the language's file loads before the card's script`);
      const code = local.concat(file).map((src) => fs.readFileSync(path.join(ROOT, path.dirname(rel), src), 'utf8')).join('\n');
      assert(!code.includes('</script'), 'the script file can sit in a page');
      return box.outerHTML + `<script>${code}</script>`;
    }
    const run = ['affirmations-data', 'scene-data'].map((id) => d.getElementById(id));
    assert(run.every(Boolean), `${rel}: the affirmations are in the page`);
    const script = all(d, 'script:not([src]):not([type])').filter((el) => el.textContent.includes('affirmations-data'));
    assert.equal(script.length, 1, `${rel}: one script shows the affirmation`);
    return box.outerHTML + run.map((el) => el.outerHTML).join('') + script[0].outerHTML;
  };
  const places = ['index.html', 'county.html']
    .concat(fs.readdirSync(path.join(ROOT, 'ohio/counties')).filter((f) => f.endsWith('.html')).map((f) => 'ohio/counties/' + f))
    .concat(fs.readdirSync(path.join(ROOT, 'states')).filter((f) => f.endsWith('.html')).map((f) => 'states/' + f))
    .concat(fs.readdirSync(path.join(ROOT, 'countries')).filter((f) => f.endsWith('.html')).map((f) => 'countries/' + f));
  const bodies = Object.fromEntries(places.map((rel) => [rel, built(rel)]));
  for (const now of ['2027-03-10T12:00:00', '2026-11-20T12:00:00', '2026-12-10T12:00:00', '2027-03-10T23:30:00']) {
    const front = shown(open(bodies['index.html'], { now }).d);
    assert(front, 'the front page shows one');
    for (const rel of places) assert.equal(shown(open(bodies[rel], { now }).d), front, `${rel} at ${now}: the same affirmation as the front page`);
  }
  for (const rel of ['states/wy.html', 'countries/ethiopia.html', 'county.html', 'ohio/counties/morrow.html']) {
    const page = open(bodies[rel]), d = page.d, first = shown(d);
    assert(!d.getElementById('scene-foot').hidden, `${rel}: Back and Next show once the script runs`);
    page.tap('#affirm-next');
    assert.notEqual(shown(d), first, `${rel}: Next flips`);
    page.tap('#affirm-prev');
    assert.equal(shown(d), first, `${rel}: Back flips back`);
    assert(d.querySelector('#affirm .sayhelp a'), `${rel}: one line points to people to talk to`);
    const still = new JSDOM(bodies[rel]).window.document;
    assert(still.getElementById('affirm').hidden, `${rel}: no empty card before the script runs`);
  }
  console.log(`PASS the day's affirmation is on all ${places.length - 1} location pages, the same one as the front page, with Back and Next`);
}

// 10. A country page whose people mostly speak another language shows the day's affirmation in that language, with the
// English under it, both the same one as the front page and in step through Back and Next. An English-speaking country,
// or one whose language has no translation yet, shows the English alone and loads no language file.
{
  const ROOT = path.join(__dirname, '..');
  const world = JSON.parse(fs.readFileSync(path.join(ROOT, 'data/ymt/world.json'), 'utf8')).countries;
  const english = JSON.parse(py('import json; print(json.dumps(e.approved_affirmations()))'));
  const langs = JSON.parse(py('import json; print(json.dumps({l: e.local_affirmations(l) for l in e.translation_langs()}))'));
  const RTL = ['ar', 'he', 'ur', 'fa'];
  const pageOf = (c) => {
    const rel = `countries/${c.slug}.html`, d = new JSDOM(fs.readFileSync(path.join(ROOT, rel), 'utf8')).window.document;
    const srcs = all(d, 'script[src]').map((el) => el.getAttribute('src'));
    const local = srcs.filter((src) => /kindword\/[^/]+\.js$/.test(src));
    const code = local.concat(srcs.filter((src) => src.endsWith('/kindword.js'))).map((src) => fs.readFileSync(path.join(ROOT, 'countries', src), 'utf8')).join('\n');
    return { rel, d, local, body: d.getElementById('affirm').outerHTML + `<script>${code}</script>` };
  };
  let localized = 0, plain = 0;
  for (const c of world) {
    const p = pageOf(c), words = langs[c.lang], line = p.d.getElementById('affirm-local');
    if (!words) {
      plain++;
      assert(!line, `${p.rel}: English only, no second line`);
      assert.equal(p.local.length, 0, `${p.rel}: English only, no language file`);
      const page = open(p.body);
      assert.equal(page.d.getElementById('affirm-local'), null);
      continue;
    }
    localized++;
    assert.equal(words.length, english.length, `${c.lang}: one line for each affirmation`);
    assert.deepEqual(p.local, [`../assets/kindword/${c.lang}.js`], `${p.rel}: loads its own language and no other`);
    assert(line, `${p.rel}: the line in ${c.lang}`);
    assert.equal(line.getAttribute('lang'), c.lang, `${p.rel}: lang`);
    assert.equal(line.getAttribute('dir'), RTL.includes(c.lang.split('-')[0]) ? 'rtl' : null, `${p.rel}: dir`);
    assert.equal(p.d.getElementById('affirm-text').getAttribute('lang'), 'en', `${p.rel}: the English is marked English`);
    assert(line.hidden, `${p.rel}: nothing shows before the script runs`);
    for (const now of ['2027-03-10T12:00:00', '2026-11-20T12:00:00', '2026-12-10T12:00:00', '2027-03-10T23:30:00']) {
      const page = open(p.body, { now }), d = page.d;
      const check = (what) => {
        const en = shown(d), i = english.indexOf(en), here = d.getElementById('affirm-local');
        assert(i >= 0, `${p.rel}: an approved affirmation`);
        assert(!here.hidden, `${p.rel} ${what}: the line in ${c.lang} shows`);
        assert.equal(here.textContent, words[i], `${p.rel} at ${now} ${what}: the same affirmation in ${c.lang}`);
      };
      check('today');
      page.tap('#affirm-next'); check('after Next');
      page.tap('#affirm-next'); check('after Next again');
      page.tap('#affirm-prev'); check('after Back');
      assert.equal(d.getElementById('affirm-local').getAttribute('aria-live'), 'polite', `${p.rel}: a flipped line is read out`);
    }
  }
  assert(localized > 40 && plain > 10, `${localized} countries in their language, ${plain} in English`);
  for (const slug of ['united-kingdom', 'canada', 'nigeria', 'south-africa', 'philippines']) assert.equal(world.find((c) => c.slug === slug).lang, 'en', `${slug} reads in English`);
  console.log(`PASS ${localized} country pages show the day's affirmation in their language over the English, in step through Back and Next, with lang and dir set; ${plain} show the English alone`);
}

console.log('PASS front-page picture is decoration beside the question; the daily affirmation is Deborah\'s speech bubble in it: one a day by the visitor\'s own date, the next one tomorrow, back and next to flip, no timers, and one gentle line to the site\'s own page of people to talk to; every affirmation brings its own pose, sweater, children, what they are doing and caption; seasonal and late-night ones come out only in their time, and open the card when they do; the owner\'s preview steps through every affirmation with the same picture');
