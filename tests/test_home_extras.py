"""The picture and the joke of the day on the two front pages. Run: python3 -m unittest discover tests"""
import datetime
import json
import math
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import home_extras as extras  # noqa: E402
import joke_preview as preview  # noqa: E402

FRONT = {'index.html': False, 'ohio/index.html': True}  # page: is it the OhioMom one
TEMPLATE = (ROOT / 'templates' / 'home-extras.css').read_text(encoding='utf-8')


def read(rel):
    return (ROOT / rel).read_text(encoding='utf-8')


def batch(n=3, start='2030-01-01', approved=True):
    day = datetime.date.fromisoformat(start)
    return {'jokes': [{'date': (day + datetime.timedelta(days=i)).isoformat(), 'text': f'Joke number {i + 1}.', 'approved': approved}
                      for i in range(n)]}


def shown(svg, attribute):
    """The names in `attribute` (data-pose, data-kid, ...) whose groups are not switched off in the drawing as written."""
    return [name for name, off in re.findall(r'<g %s="([a-z0-9]+)"[^>]*?( display="none")?>' % attribute, svg) if not off]


def every(svg, attribute):
    return re.findall(r'<g %s="([a-z0-9]+)"' % attribute, svg)


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
        rest = lambda svg: svg[svg.index('<ellipse cx="266" cy="183"'):]  # from her mat on: the family, the plant, the toys
        self.assertEqual(rest(national), rest(ohio), 'the same family in both rooms')

    def test_the_family_is_in_the_picture(self):
        """Deborah and her four children. Each child is drawn once, stands in a place of his or her own, and
        has four things to say; only the child the joke belongs to says them."""
        svg = extras.scene_svg()
        self.assertEqual(svg.count('data-mom'), 1)
        self.assertEqual(svg.count('data-top'), 1, 'her top half is drawn once and every pose moves it')
        self.assertEqual(sorted(every(svg, 'data-kid')), sorted(extras.KIDS))
        self.assertEqual(sorted(every(svg, 'data-say')), sorted(extras.KIDS))
        self.assertEqual(set(extras.KID_X), set(extras.KIDS))
        self.assertEqual(set(extras.KID_NAMES), set(extras.KIDS))
        self.assertEqual(set(extras.KID_LINES), set(extras.KIDS))
        places = sorted(extras.KID_X.values())
        self.assertTrue(all(b - a >= 40 for a, b in zip(places, places[1:])), 'the children stand apart from each other')
        self.assertTrue(all(x < 174 - 20 or x > 358 + 20 for x in places), 'and off her mat')
        self.assertEqual(svg.count('class="sc-b '), 4 * len(extras.KIDS), 'four bubbles for each child')
        for words in ('>Ha ha!<', '>Again!<', '>AGAIN. NOW.<', '>Please?<', '>6 out of 10.<', '>Fine. 10.<', '>MOM.<', '>…heh.<'):
            self.assertEqual(svg.count(words), 1, words)
        self.assertEqual(svg.count('class="sc-heart"'), len(extras.KIDS), 'each child ends on a heart')
        # Before the script runs, the page shows Deborah with the first child, who has the bubbles.
        self.assertEqual(shown(svg, 'data-kid'), ['delilah'])
        self.assertEqual(shown(svg, 'data-say'), ['delilah'])
        both = extras.scene_svg(cast=('atlas', 'ephraim'))
        self.assertEqual(sorted(shown(both, 'data-kid')), ['atlas', 'ephraim'])
        self.assertEqual(shown(both, 'data-say'), ['atlas'], 'the first one named answers the joke')
        alone = extras.scene_svg(cast=())
        self.assertEqual(shown(alone, 'data-kid') + shown(alone, 'data-say'), [], 'Deborah can have the mat to herself')

    def test_the_picture_names_nobody(self):
        """The drawing is hidden from screen readers, so no name is in it; names are in the caption and the jokes.
        The children go by first name only, everywhere."""
        svg = extras.scene_svg(True)
        for name in list(extras.KID_NAMES.values()) + ['Deborah', 'Vought']:
            self.assertNotIn(name, svg, name)
        for name in extras.KID_NAMES.values():
            self.assertRegex(name, r'^[A-Z][a-z]+$', 'a first name')
        said = [line for lines in extras.KID_LINES.values() for line in lines]
        for kid, lines in extras.KID_LINES.items():
            self.assertGreaterEqual(len(lines), 3)
            for line in lines:
                self.assertTrue(line.startswith(extras.KID_NAMES[kid] + ' ') and line.endswith('.'), line)
        self.assertEqual(len(set(said)), len(said))

    def test_every_pose_is_drawn_and_only_one_shows(self):
        svg = extras.scene_svg()
        self.assertEqual(set(every(svg, 'data-pose')), set(extras.POSES), 'each pose has its arms and legs in the drawing')
        self.assertEqual(set(shown(svg, 'data-pose')), {extras.FIRST_POSE}, 'only the first pose shows before the script runs')
        self.assertEqual(extras.top_move(extras.FIRST_POSE), '', 'the first pose leaves her top half where it is drawn')
        self.assertGreaterEqual(len(extras.POSES), 7, 'enough for a different pose every day of the week')
        names = [spec['name'] for spec in extras.POSES.values()]
        self.assertEqual(len(set(names)), len(names))
        for pose, spec in extras.POSES.items():
            right, down, _ = spec['top']
            for i in (0, 1):
                elbow, hand = spec['arms'][i]
                arm = math.dist(extras.placed(extras.SHOULDERS[i], spec['top']), elbow) + math.dist(elbow, hand)
                self.assertTrue(30 <= arm <= 62, f'{pose}: an arm {arm:.0f} long is not her arm')
                knee, ankle = spec['legs'][i]
                leg = math.dist((extras.HIPS[i][0] + right, extras.HIPS[i][1] + down), knee) + math.dist(knee, ankle)
                self.assertTrue(45 <= leg <= 65, f'{pose}: a leg {leg:.0f} long is not her leg')
            points = [pt for limb in spec['arms'] + spec['legs'] + spec['feet'] for pt in limb] + [extras.placed(extras.HEAD, spec['top'])]
            self.assertTrue(all(200 <= x <= 330 for x, _ in points), f'{pose}: she stays between the children')
            self.assertTrue(all(26 <= y <= 170 for _, y in points), f'{pose}: she stays under the joke and on her mat')
            self.assertTrue(set(spec['front']) <= set('Lab'), pose)
            self.assertTrue(174 <= spec['foot'][0] <= 358, f'{pose}: she wobbles about a point on her mat')
            self.assertRegex(extras.bubble_tail(pose), r'^[3-6]\d%$', f'{pose}: the tail of the joke points at her')

    def test_every_sweater_can_be_worn(self):
        svg = extras.scene_svg()
        patterns = set(every(svg, 'data-pat'))
        self.assertGreaterEqual(len(extras.SWEATERS), 7, 'a different sweater every day of the week')
        self.assertEqual(len(set(extras.SWEATERS.values())), len(extras.SWEATERS), 'no two alike')
        for name, (wool, accent, trim, pattern) in extras.SWEATERS.items():
            for color in (wool, accent, trim):
                self.assertRegex(color, r'^#[0-9a-f]{6}$', name)
            self.assertNotEqual(wool, accent, name)
            self.assertNotEqual(wool, extras.SKIN, f'{name}: a sweater the color of her skin looks like no sweater')
            self.assertTrue(pattern == 'plain' or pattern in patterns, f'{name}: {pattern} is not drawn')
        first = extras.SWEATERS[extras.FIRST_SWEATER]
        self.assertEqual(shown(svg, 'data-pat'), [first[3]], 'only the first sweater\'s pattern shows before the script runs')
        # The script recolors by these marks: 0 the wool, 1 the pattern, 2 the collar and hem.
        for mark, color in re.findall(r'(?:fill|stroke)="(#[0-9a-f]{6})" data-(?:fill|stroke)="([012])"', svg):
            self.assertEqual(mark, first[int(color)])
        self.assertEqual(set(re.findall(r'data-(?:fill|stroke)="(\d)"', svg)), {'0', '1', '2'})
        self.assertIn(f'stroke="{extras.LEGGINGS}"', svg, 'pink leggings whatever the sweater')

    def test_both_stylesheets_carry_the_rules_from_the_template(self):
        for rel in extras.SHEETS:
            css = read(rel)
            self.assertEqual(extras.render_sheet(css), css, f'{rel}: run python3 scripts/home_extras.py')
            block = css[css.index(extras.CSS_START) + len(extras.CSS_START) + 1:css.index(extras.CSS_END)]
            self.assertEqual(block, TEMPLATE, rel)
            self.assertTrue(css.endswith(extras.CSS_END + '\n'), rel)

    def test_every_moving_part_has_its_rule(self):
        used = set(re.findall(r'\bsc-[a-z0-9]+', extras.scene_svg(True))) - {'sc-wall', 'sc-sky', 'sc-pane', 'sc-knit'}
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
        # Who is in the picture, her pose and her sweater are optional, and checked when given.
        self.assertEqual(problems(lambda j: j[0].update(cast=['atlas', 'delilah'], pose='tree', sweater='plum')), '')
        self.assertEqual(problems(lambda j: j[0].update(cast=[])), '', 'Deborah alone')
        self.assertIn('cast is a list', problems(lambda j: j[0].update(cast=['the dog'])))
        self.assertIn('cast is a list', problems(lambda j: j[0].update(cast=['atlas', 'atlas'])))
        self.assertIn('cast is a list', problems(lambda j: j[0].update(cast='atlas')))
        self.assertIn('pose is one of', problems(lambda j: j[0].update(pose='handstand')))
        self.assertIn('sweater is one of', problems(lambda j: j[0].update(sweater='tuxedo')))

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
                self.assertNotIn(f'"{j["date"]}"', page, 'nothing about an unapproved day is in a page, its picture included')
        # The same holds for the picture: a day's pose, sweater, children and caption wait for its joke's approval.
        data = batch()
        data['jokes'][1]['approved'] = False
        self.assertEqual(sorted(extras.approved_looks(data)), ['2030-01-01', '2030-01-03'])
        self.assertEqual(extras.approved_looks(batch(approved=False)), {})

    def test_the_pages_match_the_jokes_on_file(self):
        jokes, day_looks = extras.approved_jokes(), extras.approved_looks()
        home, ohio = read('index.html'), read('ohio/index.html')
        self.assertEqual(extras.render_ohio(ohio, jokes, day_looks), ohio, 'run python3 scripts/home_extras.py')
        if not jokes:
            for rel, page in (('index.html', home), ('ohio/index.html', ohio)):
                for part in ('id="joke"', 'jokes-data', 'id="scene-data"', 'scene-cap', 'jokes.html'):
                    self.assertNotIn(part, page, f'{rel}: nothing about jokes until a batch is approved')
            self.assertFalse((ROOT / 'jokes.html').exists(), 'no jokes page until a batch is approved')
            return
        self.assertIn(extras.joke_bubble(jokes, 'jokes.html'), home)
        self.assertIn(extras.joke_bubble(jokes, '../jokes.html'), ohio)
        listing = read('jokes.html')
        self.assertEqual(listing.count(extras.joke_scripts(jokes)), 1)
        self.assertNotIn('id="scene-data"', listing, 'the list has no picture to dress')
        self.assertEqual(listing.count('<li data-date="'), len(jokes))
        for page in (home, ohio, listing):
            self.assertEqual(page.count('id="jokes-data"'), 1)
            self.assertEqual(page.count(extras.JOKE_SCRIPT), 1, 'one script on the page')
        for rel, page in (('index.html', home), ('ohio/index.html', ohio)):
            # The joke is in the picture, at the top: Deborah's speech bubble, straight above the drawing, before the choices.
            self.assertEqual(page.count('id="joke"'), 1, rel)
            self.assertIn('<div class="scenebox" id="scene"><div class="saying" id="joke" hidden>', page, rel)
            self.assertIn('</div><svg class="scene"', page, f'{rel}: the bubble sits straight above the drawing')
            self.assertLess(page.index('id="joke"'), page.index('<div class="tiles">'), f'{rel}: the joke is met before the choices')
            # The picture is dressed for the same days the jokes are for, by the same script.
            self.assertEqual(page.count(extras.joke_scripts(jokes, day_looks)), 1, rel)
            self.assertIn('</svg>' + extras.caption_line(jokes) + '</div>', page, f'{rel}: the caption sits straight under the drawing')
            self.assertRegex(extras.caption_line(jokes), r'^<p class="scenecap" id="scene-cap" style="[^"<>]+" hidden></p>$')
            self.assertNotIn('.scenecap', TEMPLATE, 'its look is on the line itself, so an old stylesheet cannot leave it bare')
            block = page[page.index('id="scene-data">') + len('id="scene-data">'):]
            scene = json.loads(block[:block.index('</script>')])
            self.assertEqual(sorted(scene['d']), sorted(jokes), f'{rel}: a picture for each day that has a joke')
        self.assertIn('<url><loc>https://www.yogamomtalk.com/jokes.html</loc></url>', read('sitemap.xml'))

    def test_no_joke_block_without_an_approved_batch(self):
        self.assertEqual(extras.joke_bubble({}, 'jokes.html'), '')
        self.assertEqual(extras.joke_scripts({}), '')
        self.assertEqual(extras.joke_scripts({}, {}), '')
        self.assertEqual(extras.scene_block(True), f'<div class="scenebox" id="scene">{extras.scene_svg(True)}</div>',
                         'the picture alone: no bubble, no caption')

    def test_the_joke_block_starts_hidden_and_points_to_the_list(self):
        jokes = extras.approved_jokes(batch())
        section = extras.joke_bubble(jokes, '../jokes.html')
        self.assertTrue(section.startswith('<div class="saying" id="joke" hidden>'), 'no empty bubble when the script does not run')
        self.assertIn('<h2>Deborah’s joke of the day</h2>', section, 'the jokes are hers, and the heading says so')
        self.assertIn('<p class="joketext" id="joke-text"></p>', section)
        self.assertIn('<a href="../jokes.html">Earlier<span> jokes</span></a>', section,
                      'a narrow phone hides the second word from the eye, never from a screen reader')
        self.assertIn('@media (max-width:400px){.sayinghead a span{position:absolute;width:1px;height:1px;overflow:hidden;', TEMPLATE)
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
        for banned in ('fetch(', 'XMLHttpRequest', 'sendBeacon', 'document.cookie', 'cookie', 'localStorage', 'sessionStorage',
                       'WebSocket', 'http', 'innerHTML', 'outerHTML', 'insertAdjacent', 'document.write', 'eval(', 'Function(',
                       'createElement', 'location', 'navigator'):
            self.assertNotIn(banned, extras.JOKE_SCRIPT, banned)
        self.assertIn('textContent', extras.JOKE_SCRIPT)
        self.assertIn(extras.DRESS, extras.JOKE_SCRIPT, 'the same few lines dress the picture')
        self.assertEqual(extras.JOKE_SCRIPT.count('<script>'), 1)

    def approving(self, data, start=None):
        """The joke file after `approve`, run on a copy."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'jokes.json'
            path.write_text(json.dumps(data), encoding='utf-8')
            real, extras.JOKES = extras.JOKES, path
            try:
                extras.approve(start)
                return extras.read_jokes()
            finally:
                extras.JOKES = real

    def test_approving_marks_every_joke_and_can_move_the_batch(self):
        data = self.approving(batch(approved=False), '2031-03-30')
        self.assertEqual([j['date'] for j in data['jokes']], ['2031-03-30', '2031-03-31', '2031-04-01'])
        self.assertTrue(all(j['approved'] is True for j in data['jokes']))
        self.assertEqual(extras.check_jokes(data), [])
        kept = self.approving(batch(approved=False))
        self.assertEqual([j['date'] for j in kept['jokes']], ['2030-01-01', '2030-01-02', '2030-01-03'], 'with no start the days stay')
        with self.assertRaises(SystemExit, msg='nothing is waiting'):
            self.approving(batch())

    def test_a_new_batch_can_go_ahead_of_the_jokes_still_waiting_their_turn(self):
        """A batch approved today can start today: the jokes that already ran keep their days, the new ones
        take over, and the approved ones that had not run yet follow after them. Nothing is lost or repeated."""
        old, new = batch(5, '2030-01-01')['jokes'], batch(2, '2030-01-06', approved=False)['jokes']
        for i, j in enumerate(old):
            j['text'] = f'Old joke {i + 1}.'
        new[0].update(text='New joke 1.', cast=['atlas'])
        new[1].update(text='New joke 2.')
        data = self.approving({'jokes': old + new}, '2030-01-03')
        self.assertEqual([(j['date'], j['text']) for j in data['jokes']], [
            ('2030-01-01', 'Old joke 1.'), ('2030-01-02', 'Old joke 2.'),
            ('2030-01-03', 'New joke 1.'), ('2030-01-04', 'New joke 2.'),
            ('2030-01-05', 'Old joke 3.'), ('2030-01-06', 'Old joke 4.'), ('2030-01-07', 'Old joke 5.')])
        self.assertTrue(all(j['approved'] is True for j in data['jokes']))
        self.assertEqual(data['jokes'][2]['cast'], ['atlas'], 'a joke keeps its picture when it moves')
        self.assertEqual(extras.check_jokes(data), [])
        waiting = lambda: {'jokes': batch(5)['jokes'] + [dict(j, text='Later ' + j['text'])
                                                         for j in batch(2, '2030-01-06', approved=False)['jokes']]}
        after = self.approving(waiting(), '2030-01-06')
        self.assertEqual([j['date'] for j in after['jokes']], [f'2030-01-0{n}' for n in range(1, 8)], 'or simply follow them')
        with self.assertRaises(SystemExit, msg='a start that leaves a day with no joke is refused'):
            self.approving(waiting(), '2030-01-09')


class DayTests(unittest.TestCase):
    """What the picture shows on each day: her pose, her sweater, which children are in it, and the caption."""

    def test_every_joke_on_file_has_its_picture(self):
        data = extras.read_jokes()
        day_looks = extras.looks(data)
        self.assertEqual(list(day_looks), [j['date'] for j in data['jokes']])
        for j in data['jokes']:
            pose, sweater, cast, words = day_looks[j['date']]
            self.assertIn(pose, extras.POSES)
            self.assertIn(sweater, extras.SWEATERS)
            self.assertTrue(set(cast) <= set(extras.KIDS))
            self.assertEqual((j.get('pose') or pose, j.get('sweater') or sweater), (pose, sweater), 'what a joke names, it gets')
            if 'cast' in j:
                self.assertEqual(list(cast), j['cast'])
            self.assertRegex(words, '^Today Deborah is working on ' + re.escape(extras.POSES[pose]['name']) + '[.,]')
            self.assertNotIn('|', words + ''.join(cast), 'the page keeps a day as one line split on this mark')
            for kid in extras.KIDS:  # a child the caption names is in the picture
                if extras.KID_NAMES[kid] in words:
                    self.assertIn(kid, cast, words)
        # Every child the words of a joke name is in that day's picture.
        for j in data['jokes']:
            for kid in extras.KIDS:
                if extras.KID_NAMES[kid] in j['text']:
                    self.assertIn(kid, day_looks[j['date']][2], j['text'])

    def test_poses_and_sweaters_take_turns(self):
        day_looks = list(extras.looks(batch(40)).values())
        for part, names in ((0, extras.POSES), (1, extras.SWEATERS)):
            worn = [look[part] for look in day_looks]
            self.assertEqual(set(worn), set(names), 'all of them come round')
            for gap in (1, 2):
                self.assertTrue(all(a != b for a, b in zip(worn, worn[gap:])), 'never the same twice in three days')
        self.assertEqual([look[2] for look in day_looks[:5]], [('delilah',), ('ephraim',), ('genevieve',), ('atlas',), ('delilah',)],
                         'with no cast named, the children take turns')
        # A joke that names its pose gets it, and the days around it step aside.
        data = batch(6)
        data['jokes'][2]['pose'] = 'tree'
        data['jokes'][3]['sweater'] = extras.FIRST_SWEATER
        worn = list(extras.looks(data).values())
        self.assertEqual(worn[2][0], 'tree')
        self.assertEqual(worn[3][1], extras.FIRST_SWEATER)
        for part in (0, 1):
            names = [look[part] for look in worn]
            for gap in (1, 2):
                self.assertTrue(all(a != b for a, b in zip(names, names[gap:])), names)

    def test_the_caption_says_who_is_there(self):
        self.assertEqual(extras.caption('tree', []), 'Today Deborah is working on tree pose.')
        self.assertEqual(extras.caption('tree', ['delilah']), 'Today Deborah is working on tree pose. Delilah is supervising.')
        self.assertEqual(extras.caption('tree', ['delilah'], 1), 'Today Deborah is working on tree pose. Delilah has notes.')
        self.assertEqual(extras.caption('warrior2', ['atlas', 'ephraim']), 'Today Deborah is working on warrior two, with Atlas and Ephraim.')
        self.assertEqual(extras.caption('easy', ['atlas', 'ephraim', 'delilah']),
                         'Today Deborah is working on easy pose, with Atlas, Ephraim and Delilah.')
        self.assertEqual(extras.caption('star', list(extras.KIDS)), 'Today Deborah is working on star pose, with all four kids.')
        # On a phone the caption is two lines at most, so the choices below it stay where they are: about 80 letters.
        casts = [[k] for k in extras.KIDS] + [['genevieve', 'ephraim'], ['genevieve', 'ephraim', 'delilah'], list(extras.KIDS), []]
        for pose in extras.POSES:
            for cast in casts:
                for turn in range(4):
                    self.assertLessEqual(len(extras.caption(pose, cast, turn)), 80, extras.caption(pose, cast, turn))
        data = batch(9)
        for j in data['jokes']:
            j['cast'] = ['genevieve']
        lines = [look[3].split('. ', 1)[1] for look in extras.looks(data).values()]
        self.assertEqual(lines[:len(extras.KID_LINES['genevieve'])], list(extras.KID_LINES['genevieve']), 'a child goes through her own lines in order')
        self.assertEqual(lines[len(extras.KID_LINES['genevieve'])], lines[0], 'and then starts over')

    def test_the_page_gets_what_the_script_needs(self):
        data = batch(3)
        data['jokes'][1].update(cast=['atlas', 'genevieve'], pose='triangle', sweater='plum')
        scene = extras.scene_data(extras.approved_looks(data))
        self.assertEqual(set(scene), {'p', 'w', 'd'})
        self.assertEqual(set(scene['p']), set(extras.POSES))
        self.assertEqual(set(scene['w']), set(extras.SWEATERS))
        self.assertEqual(scene['d']['2030-01-02'], 'triangle|plum|atlas genevieve|Today Deborah is working on triangle pose, with Atlas and Genevieve.')
        self.assertEqual(scene['p']['tree'], ['', '256.5px 168px', '50%'])
        self.assertEqual(scene['p']['triangle'][0], 'translate(8 4)rotate(-58 262 113)')
        self.assertEqual(scene['w']['plum'], list(extras.SWEATERS['plum']))
        for move, foot, tail in scene['p'].values():
            self.assertRegex(move, r'^(translate\(-?[\d.]+ -?[\d.]+\))?(rotate\(-?[\d.]+ 262 113\))?$')
            self.assertRegex(foot, r'^[\d.]+px [\d.]+px$')
        block = extras.joke_scripts(extras.approved_jokes(data), extras.approved_looks(data))
        self.assertEqual(block.count('<script'), 3, 'the jokes, the picture, and one script')
        self.assertEqual(block.count('<script>'), 1)
        self.assertLess(block.index('id="jokes-data"'), block.index('id="scene-data"'))
        self.assertNotIn('id="scene-data"', extras.joke_scripts(extras.approved_jokes(data)), 'no picture data where there is no picture')


class PreviewTests(unittest.TestCase):
    """The page the owner looks at before approving a batch (scripts/joke_preview.py). It shows the picture card as
    the site draws it, for every joke on file, and it holds jokes nobody has approved, so it stays out of the site."""

    def test_it_shows_every_joke_with_the_site_s_own_picture(self):
        data = batch(4)
        for j in data['jokes'][2:]:
            j['approved'] = False
        data['jokes'][3]['cast'] = ['atlas', 'genevieve']
        html = preview.page(data)
        self.assertTrue(html.startswith('<!DOCTYPE html>'))
        for j in data['jokes']:
            self.assertEqual(html.count(f'data-day="{j["date"]}"'), 1)
            self.assertIn(f'>{j["text"]}<span class="who">', html)
        self.assertIn(extras.scene_block(False, {j['date']: j['text'] for j in data['jokes']}, '#'), html, 'the card the front pages show')
        self.assertIn(extras.DRESS, html, 'dressed by the front pages\' own lines of script')
        self.assertIn(TEMPLATE, html, 'and moved by the same rules')
        self.assertLess(html.index('data-day="2030-01-03"'), html.index('data-day="2030-01-01"'), 'the waiting jokes come first')
        self.assertIn('Waiting for your OK (2)', html)
        self.assertIn('Already approved (2)', html)
        self.assertIn('Atlas, Genevieve · ', html, 'each joke says who is in its picture')
        self.assertEqual(html.count('data-try="pose"'), len(extras.POSES), 'and any pose, sweater or child can be tried')
        self.assertEqual(html.count('data-try="sweater"'), len(extras.SWEATERS))
        self.assertEqual(html.count('data-try="kid"'), len(extras.KIDS))
        self.assertIn('Preview. Not on the site.', html)
        self.assertIn('<meta name="robots" content="noindex">', html)

    def test_it_is_one_file_that_loads_nothing(self):
        html = preview.page(batch(3, approved=False))
        for banned in (' src=', '<link', '@import', 'http', 'fetch(', 'XMLHttpRequest', 'localStorage', 'document.cookie', '<iframe', '<img'):
            self.assertNotIn(banned, html, banned)
        self.assertTrue(all(ref.startswith('#sc-') for ref in re.findall(r'url\(([^)]*)\)', html)), 'only the drawing\'s own gradients and clips')
        self.assertEqual(html.count('<script>'), 1)
        self.assertIn('Nothing is waiting', preview.page(batch(2)))

    def test_it_is_never_written_into_the_repository(self):
        for inside in (ROOT / 'preview.html', ROOT / 'ohio' / 'preview.html', ROOT):
            real, sys.argv = sys.argv, ['joke_preview.py', str(inside)]
            try:
                with self.assertRaises(SystemExit):
                    preview.main()
            finally:
                sys.argv = real
        self.assertFalse((ROOT / 'preview.html').exists())
        self.assertFalse((ROOT / 'ohio' / 'preview.html').exists())
        with tempfile.TemporaryDirectory() as tmp:
            real, sys.argv = sys.argv, ['joke_preview.py', str(Path(tmp) / 'preview.html')]
            try:
                preview.main()
            finally:
                sys.argv = real
            written = (Path(tmp) / 'preview.html').read_text(encoding='utf-8')
        self.assertEqual(written, preview.page())
        for j in extras.read_jokes()['jokes']:
            self.assertIn(j['text'].replace('&', '&amp;'), written)


if __name__ == '__main__':
    unittest.main()
