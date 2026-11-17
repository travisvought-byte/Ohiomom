"""The picture and the joke of the day on the two front pages. Run: python3 -m unittest discover tests"""
import datetime
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import home_extras as extras  # noqa: E402

FRONT = {'index.html': False, 'ohio/index.html': True}  # page: is it the OhioMom one
TEMPLATE = (ROOT / 'templates' / 'home-extras.css').read_text(encoding='utf-8')


def read(rel):
    return (ROOT / rel).read_text(encoding='utf-8')


def batch(n=3, start='2030-01-01', approved=True):
    day = datetime.date.fromisoformat(start)
    return {'jokes': [{'date': (day + datetime.timedelta(days=i)).isoformat(), 'text': f'Joke number {i + 1}.', 'approved': approved}
                      for i in range(n)]}


class PictureTests(unittest.TestCase):
    def test_each_front_page_has_the_picture_beside_its_headline(self):
        jokes = extras.approved_jokes()
        for rel, ohio in FRONT.items():
            text = read(rel)
            self.assertEqual(text.count('<svg class="scene"'), 1, rel)
            card = extras.scene_block(ohio, jokes, '../jokes.html' if ohio else 'jokes.html')
            self.assertIn(card, text, f'{rel}: the picture card on the page is the one the script makes')
            hero = text[text.index('<section class="hero home">'):text.index('<div class="tiles">')]
            self.assertRegex(hero, r'<div class="herotop"><div class="herotext"><h1>[^<]+</h1><p class="lede">[^<]+</p></div>', rel)
            self.assertIn(card, hero, f'{rel}: the picture card sits in the hero, after the question')
            self.assertLess(text.index('<h1>'), text.index('<svg class="scene"'), f'{rel}: the question is read first')

    def test_the_picture_is_decoration(self):
        """It says nothing a visitor needs, so screen readers skip it and the keyboard never lands in it."""
        for ohio in (False, True):
            svg = extras.scene_svg(ohio)
            self.assertTrue(svg.startswith('<svg class="scene" viewBox="0 10 520 196" aria-hidden="true" focusable="false">'))
            for banned in ('<a ', 'href', 'tabindex', '<title', 'onclick', '<script', '<image', 'http'):
                self.assertNotIn(banned, svg, banned)
            ids = re.findall(r'\bid="([^"]+)"', svg)
            self.assertEqual(len(ids), len(set(ids)))
            for i in ids:
                self.assertTrue(i.startswith('sc-'), f'{i}: ids in the picture carry its prefix so they cannot clash with the page')

    def test_ohio_has_its_cardinal_and_its_outline(self):
        national, ohio = extras.scene_svg(), extras.scene_svg(True)
        self.assertNotIn('sc-bird', national)
        self.assertNotIn(extras.OHIO, national)
        self.assertIn('class="sc-bird"', ohio)
        self.assertIn(extras.OHIO, ohio)
        self.assertEqual(national.count('class="sc-b '), 4, 'four things the child says')
        for words in ('>Ha ha!<', '>Again!<', '>AGAIN!<', '>Please?<'):
            self.assertIn(words, national)

    def test_both_stylesheets_carry_the_rules_from_the_template(self):
        for rel in extras.SHEETS:
            css = read(rel)
            self.assertEqual(extras.render_sheet(css), css, f'{rel}: run python3 scripts/home_extras.py')
            block = css[css.index(extras.CSS_START) + len(extras.CSS_START) + 1:css.index(extras.CSS_END)]
            self.assertEqual(block, TEMPLATE, rel)
            self.assertTrue(css.endswith(extras.CSS_END + '\n'), rel)

    def test_every_moving_part_has_its_rule(self):
        used = set(re.findall(r'\bsc-[a-z0-9]+', extras.scene_svg(True))) - {'sc-wall', 'sc-sky', 'sc-pane'}
        for cls in sorted(used):
            self.assertRegex(TEMPLATE, r'\.%s[{,]' % re.escape(cls), f'{cls} is in the picture but has no rule')
        named = set(re.findall(r'animation:(sc-[a-z0-9]+) ', TEMPLATE))
        defined = set(re.findall(r'@keyframes (sc-[a-z0-9]+)\{', TEMPLATE))
        self.assertEqual(named, defined, 'every animation has its keyframes, and no keyframes are left over')
        self.assertTrue(named)

    def test_the_picture_holds_still_when_the_visitor_asks(self):
        self.assertIn('@media (prefers-reduced-motion:reduce){.scene *{animation:none!important}.sc-b1{opacity:1}}', TEMPLATE)
        self.assertIn('@media print{.scenebox{display:none}}', TEMPLATE)
        self.assertNotIn('url(', TEMPLATE, 'the rules load nothing')
        self.assertNotIn('@import', TEMPLATE)


class JokeTests(unittest.TestCase):
    def test_the_jokes_on_file_are_well_formed(self):
        data = extras.read_jokes()
        self.assertEqual(extras.check_jokes(data), [])
        self.assertGreaterEqual(len(data['jokes']), 1)

    def test_the_check_catches_what_can_go_wrong(self):
        def problems(change):
            data = batch()
            change(data['jokes'])
            return ' '.join(extras.check_jokes(data))
        self.assertEqual(extras.check_jokes(batch()), [])
        self.assertIn('bad date', problems(lambda j: j[1].update(date='soon')))
        self.assertIn('used twice', problems(lambda j: j[1].update(date=j[0]['date'])))
        self.assertIn('does not follow', problems(lambda j: j[2].update(date='2030-01-09')))
        self.assertIn('empty', problems(lambda j: j[0].update(text=' ')))
        self.assertIn('characters', problems(lambda j: j[0].update(text='ha ' * 100 + 'ha')))
        self.assertIn('no markup', problems(lambda j: j[0].update(text='A <b>bold</b> joke.')))
        self.assertIn('true or false', problems(lambda j: j[0].update(approved='yes')))
        self.assertIn('listed twice', problems(lambda j: j[1].update(text=j[0]['text'])))

    def test_only_approved_jokes_are_ever_published(self):
        data = batch()
        data['jokes'][1]['approved'] = False
        self.assertEqual(sorted(extras.approved_jokes(data)), ['2030-01-01', '2030-01-03'])
        self.assertEqual(extras.approved_jokes(batch(approved=False)), {})
        real = extras.read_jokes()
        pages = [read(rel) for rel in FRONT] + ([read('jokes.html')] if (ROOT / 'jokes.html').exists() else [])
        for j in real['jokes']:
            for page in pages:
                if j['approved'] is True:
                    continue
                self.assertNotIn(j['text'], page, 'a joke the owner has not approved is in a page')
                self.assertNotIn(json.dumps(j['text'], ensure_ascii=False), page)

    def test_the_pages_match_the_jokes_on_file(self):
        jokes = extras.approved_jokes()
        home, ohio = read('index.html'), read('ohio/index.html')
        self.assertEqual(extras.render_ohio(ohio, jokes), ohio, 'run python3 scripts/home_extras.py')
        if not jokes:
            for rel, page in (('index.html', home), ('ohio/index.html', ohio)):
                for part in ('id="joke"', 'jokes-data', 'jokes.html'):
                    self.assertNotIn(part, page, f'{rel}: nothing about jokes until a batch is approved')
            self.assertFalse((ROOT / 'jokes.html').exists(), 'no jokes page until a batch is approved')
            return
        self.assertIn(extras.joke_bubble(jokes, 'jokes.html'), home)
        self.assertIn(extras.joke_bubble(jokes, '../jokes.html'), ohio)
        listing = read('jokes.html')
        for page in (home, ohio, listing):
            self.assertEqual(page.count(extras.joke_scripts(jokes)), 1)
            self.assertEqual(page.count('id="jokes-data"'), 1)
        self.assertEqual(listing.count('<li data-date="'), len(jokes))
        for rel, page in (('index.html', home), ('ohio/index.html', ohio)):
            # The joke is in the picture, at the top: the mom's speech bubble, straight above the drawing, before the choices.
            self.assertEqual(page.count('id="joke"'), 1, rel)
            self.assertIn('<div class="scenebox"><div class="saying" id="joke" hidden>', page, rel)
            self.assertIn('</div><svg class="scene"', page, f'{rel}: the bubble sits straight above the drawing')
            self.assertLess(page.index('id="joke"'), page.index('<div class="tiles">'), f'{rel}: the joke is met before the choices')
        self.assertIn('<url><loc>https://www.yogamomtalk.com/jokes.html</loc></url>', read('sitemap.xml'))

    def test_no_joke_block_without_an_approved_batch(self):
        self.assertEqual(extras.joke_bubble({}, 'jokes.html'), '')
        self.assertEqual(extras.joke_scripts({}), '')
        self.assertEqual(extras.scene_block(True), f'<div class="scenebox">{extras.scene_svg(True)}</div>', 'the picture alone')

    def test_the_joke_block_starts_hidden_and_points_to_the_list(self):
        jokes = extras.approved_jokes(batch())
        section = extras.joke_bubble(jokes, '../jokes.html')
        self.assertTrue(section.startswith('<div class="saying" id="joke" hidden>'), 'no empty bubble when the script does not run')
        self.assertIn('<h2>Mom joke of the day</h2>', section)
        self.assertIn('<p class="joketext" id="joke-text"></p>', section)
        self.assertIn('<a href="../jokes.html">Earlier jokes</a>', section)
        self.assertNotIn('Joke number', section, 'the joke itself is filled in by the script, for the visitor\'s own date')
        self.assertNotIn('aria-hidden', section, 'the joke is for everyone, so screen readers read it; only the drawing is hidden from them')
        rows = extras.joke_list(jokes)
        self.assertEqual(re.findall(r'<li data-date="([^"]+)" hidden>', rows), ['2030-01-03', '2030-01-02', '2030-01-01'])
        self.assertIn('<small>January 3, 2030</small>Joke number 3.', rows)
        self.assertIn('id="joke-none" hidden', rows)

    def test_a_joke_cannot_break_out_of_the_page(self):
        nasty = {'2030-01-01': 'Ha</script><script>alert(1)</script> & "quotes"'}
        block = extras.jokes_data(nasty)
        self.assertEqual(block.count('</script>'), 1)
        self.assertEqual(json.loads(block[block.index('>') + 1:block.rindex('<')]), nasty)
        self.assertNotIn('<script>', extras.joke_list(nasty))

    def test_the_joke_script_sends_and_stores_nothing(self):
        for banned in ('fetch(', 'XMLHttpRequest', 'sendBeacon', 'document.cookie', 'localStorage', 'sessionStorage',
                       'WebSocket', 'http', 'innerHTML', 'eval('):
            self.assertNotIn(banned, extras.JOKE_SCRIPT, banned)
        self.assertIn('textContent', extras.JOKE_SCRIPT)

    def test_approving_marks_every_joke_and_can_move_the_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'jokes.json'
            path.write_text(json.dumps(batch(approved=False)), encoding='utf-8')
            real, extras.JOKES = extras.JOKES, path
            try:
                extras.approve('2031-03-30')
                data = extras.read_jokes()
            finally:
                extras.JOKES = real
        self.assertEqual([j['date'] for j in data['jokes']], ['2031-03-30', '2031-03-31', '2031-04-01'])
        self.assertTrue(all(j['approved'] is True for j in data['jokes']))
        self.assertEqual(extras.check_jokes(data), [])


if __name__ == '__main__':
    unittest.main()
