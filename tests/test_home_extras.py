"""The picture and the daily affirmation on the two front pages. Run: python3 -m unittest discover tests"""
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
import affirmation_preview as preview  # noqa: E402

FRONT = {'index.html': False, 'ohio/index.html': True}  # page: is it the OhioMom one
TEMPLATE = (ROOT / 'templates' / 'home-extras.css').read_text(encoding='utf-8')


def read(rel):
    return (ROOT / rel).read_text(encoding='utf-8')


def batch(n=3, approved=True):
    return {'affirmations': [{'text': f'Kind word number {i + 1}.', 'approved': approved} for i in range(n)]}


def card(ohio, sayings):
    """The picture card as each front page asks for it."""
    if ohio:
        return extras.scene_block(True, sayings, extras.OHIO_LIST, extras.OHIO_HELP)
    return extras.scene_block(False, sayings, 'affirmations.html', 'help.html#take-care')


def shown(svg, attribute):
    """The names in `attribute` (data-pose, data-kid, ...) whose groups are not switched off in the drawing as written."""
    return [name for name, off in re.findall(r'<g %s="([a-z0-9]+)"[^>]*?( display="none")?>' % attribute, svg) if not off]


def every(svg, attribute):
    return re.findall(r'<g %s="([a-z0-9]+)"' % attribute, svg)


class PictureTests(unittest.TestCase):
    def test_each_front_page_has_the_picture_beside_its_headline(self):
        sayings = extras.approved_affirmations()
        for rel, ohio in FRONT.items():
            text = read(rel)
            self.assertEqual(text.count('<svg class="scene"'), 1, rel)
            built = card(ohio, sayings)
            self.assertIn(built, text, f'{rel}: the picture card on the page is the one the script makes')
            hero = text[text.index('<section class="hero home">'):text.index('<div class="tiles">')]
            self.assertRegex(hero, r'<div class="herotop"><div class="herotext"><h1>[^<]+</h1><p class="lede">[^<]+</p></div>', rel)
            self.assertIn(built, hero, f'{rel}: the picture card sits in the hero, after the question')
            self.assertLess(text.index('<h1>'), text.index('<svg class="scene"'), f'{rel}: the question is read first')

    def test_the_picture_is_decoration(self):
        """It says nothing a visitor needs, so screen readers skip it and the keyboard never lands in it."""
        for ohio in (False, True):
            svg = extras.scene_svg(ohio)
            self.assertTrue(svg.startswith('<svg class="scene" viewBox="0 10 520 216" aria-hidden="true" focusable="false">'),
                            'the floor is deep enough for the buttons that flip and the line between them')
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
        """Deborah and her four children. Each child is drawn once and stands in a place of his or her own."""
        svg = extras.scene_svg()
        self.assertEqual(svg.count('data-mom'), 1)
        self.assertEqual(svg.count('data-top'), 1, 'her top half is drawn once and every pose moves it')
        self.assertEqual(sorted(every(svg, 'data-kid')), sorted(extras.KIDS))
        self.assertEqual(set(extras.KID_X), set(extras.KIDS))
        self.assertEqual(set(extras.KID_NAMES), set(extras.KIDS))
        places = sorted(extras.KID_X.values())
        self.assertTrue(all(b - a >= 40 for a, b in zip(places, places[1:])), 'the children stand apart from each other')
        self.assertTrue(all(x < 174 - 20 or x > 358 + 20 for x in places), 'and off her mat')
        # Before the script runs, the page shows Deborah with the first child.
        self.assertEqual(shown(svg, 'data-kid'), ['delilah'])
        both = extras.scene_svg(cast=('atlas', 'ephraim'))
        self.assertEqual(sorted(shown(both, 'data-kid')), ['atlas', 'ephraim'])
        self.assertEqual(shown(extras.scene_svg(cast=()), 'data-kid'), [], 'Deborah can have the mat to herself')

    def test_the_children_are_around_not_on_stage(self):
        """They do their own things while she says her kind word (the owner's call, November 17, 2026). Only the
        smallest speaks, and only to her mother: she wants a hug."""
        svg = extras.scene_svg()
        kids = {}
        ends = sorted(svg.index(f'<g data-kid="{name}"') for name in extras.KIDS) + [svg.index('<g class="sc-leaf">')]
        for name in extras.KIDS:
            start = svg.index(f'<g data-kid="{name}"')
            kids[name] = svg[start:min(e for e in ends if e > start)]
        self.assertEqual(re.findall(r'<text[^>]*>([^<]*)</text>', svg), ['Mama!', 'Hug?', 'LOVE YOU!', 'Big hug!'])
        self.assertEqual(kids['delilah'].count('class="sc-b '), 4)
        for name in ('ephraim', 'genevieve', 'atlas'):
            self.assertNotIn('<text', kids[name], f'{name} says nothing')
            self.assertNotIn('sc-b', kids[name])
        self.assertNotIn('data-say', svg, 'nobody is picked to speak')
        self.assertNotIn('data-say', extras.DRESS)
        # What each one is doing is in the drawing, and it moves.
        self.assertIn('class="sc-look"', kids['ephraim'], 'he looks up from his book')
        self.assertIn('class="sc-grin"', kids['genevieve'], 'she almost laughs')
        self.assertIn('class="sc-peek"', kids['atlas'], 'he leans out from behind the plant')
        self.assertIn('class="sc-hi"', kids['atlas'])
        self.assertIn('class="sc-kid"', kids['delilah'])
        self.assertLess(svg.index('<g data-kid="atlas"'), svg.index('<g class="sc-leaf">'), 'the plant is drawn in front of him')
        # Who is around takes turns: every child comes round, alone and in company, and never the same lot twice running.
        for group in extras.CASTS:
            self.assertTrue(group and set(group) <= set(extras.KIDS) and len(set(group)) == len(group), group)
        self.assertEqual(len(set(extras.CASTS)), len(extras.CASTS))
        for name in extras.KIDS:
            self.assertIn((name,), extras.CASTS, f'{name} has turns alone with her')
            self.assertGreaterEqual(sum(name in group for group in extras.CASTS), 4, name)
        self.assertIn(tuple(extras.KIDS), extras.CASTS, 'and sometimes everybody is there')

    def test_the_picture_names_nobody(self):
        """The drawing is hidden from screen readers, so no name is in it. The caption names Deborah and nobody else."""
        svg = extras.scene_svg(True)
        for name in list(extras.KID_NAMES.values()) + ['Deborah', 'Vought']:
            self.assertNotIn(name, svg, name)
        for name in extras.KID_NAMES.values():
            self.assertRegex(name, r'^[A-Z][a-z]+$', 'a first name')
        for pose in extras.POSES:
            words = extras.caption(pose)
            self.assertIn('Deborah', words)
            for name in extras.KID_NAMES.values():
                self.assertNotIn(name, words)

    def test_every_pose_is_drawn_and_only_one_shows(self):
        svg = extras.scene_svg()
        self.assertEqual(set(every(svg, 'data-pose')), set(extras.POSES), 'each pose has its arms and legs in the drawing')
        self.assertEqual(set(shown(svg, 'data-pose')), {extras.FIRST_POSE}, 'only the first pose shows before the script runs')
        self.assertEqual(extras.top_move(extras.FIRST_POSE), '', 'the first pose leaves her top half where it is drawn')
        self.assertGreaterEqual(len(extras.POSES), 7, 'enough that the same pose does not keep coming round')
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
            self.assertTrue(all(26 <= y <= 170 for _, y in points), f'{pose}: she stays under the bubble and on her mat')
            self.assertTrue(set(spec['front']) <= set('Lab'), pose)
            self.assertTrue(174 <= spec['foot'][0] <= 358, f'{pose}: she wobbles about a point on her mat')
            self.assertRegex(extras.bubble_tail(pose), r'^[3-6]\d%$', f'{pose}: the tail of the bubble points at her')

    def test_every_sweater_can_be_worn(self):
        svg = extras.scene_svg()
        patterns = set(every(svg, 'data-pat'))
        self.assertGreaterEqual(len(extras.SWEATERS), 7, 'enough that the same sweater does not keep coming round')
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
        # A stylesheet from before, whose block began with other words, gets today's block in its place, not a second one.
        old = 'body{margin:0}\n' + extras.CSS_OPEN + '. What the first line used to say. */\n.gone{color:red}\n' + extras.CSS_END + '\n'
        new = extras.render_sheet(old)
        self.assertEqual(new, 'body{margin:0}\n' + extras.CSS_START + '\n' + TEMPLATE + extras.CSS_END + '\n')
        self.assertEqual(extras.render_sheet(new), new)
        with self.assertRaises(SystemExit, msg='two blocks, or one that is not at the end, is refused'):
            extras.render_sheet(new + 'p{margin:0}\n')

    def test_every_moving_part_has_its_rule(self):
        used = set(re.findall(r'\bsc-[a-z0-9]+', extras.scene_svg(True))) - {'sc-wall', 'sc-sky', 'sc-pane', 'sc-knit', 'sc-lamp'}
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


class AffirmationTests(unittest.TestCase):
    def test_the_affirmations_on_file_are_well_formed(self):
        data = extras.read_affirmations()
        self.assertEqual(extras.check_affirmations(data), [])
        self.assertGreaterEqual(len(data['affirmations']), 1)

    def test_the_affirmations_are_kind_plain_and_never_preach(self):
        """The owner's call, November 20, 2026: something warm and positive for a mom going through a tough time,
        mom to mom. No guilt, no "should", no religion, and no medical or mental-health claims."""
        texts = [j['text'] for j in extras.read_affirmations()['affirmations']]
        self.assertGreaterEqual(len(texts), 90, 'plenty, so a mom can come back for weeks')
        banned = (r'\bshould\b', r'\bmust\b', r'\bought\b', r'\bfailure\b', r'\bguilt', r'\bgod\b', r'\bpray', r'\bbless', r'\bfaith\b',
                  r'\bchurch\b', r'\bjesus\b', r'\bheaven', r'\bdepress', r'\banxiety\b', r'\bdisorder\b', r'\bdiagnos', r'\btherap',
                  r'\bmedic', r'\bcure', r'\bheal', r'\bsymptom', r'\bhormone', r'\bjoke', r'\bkill', r'\bdie\b', r'\bsuicid')
        for text in texts:
            for word in banned:
                self.assertNotRegex(text.lower(), word, text)
            for name in extras.KID_NAMES.values():
                self.assertNotIn(name, text, 'the affirmations name no child')
            self.assertRegex(text, r'^[A-Z“"]', text)
            self.assertRegex(text, r'[.!?”]$', text)
            self.assertNotRegex(text, r'\d{3}', 'no phone numbers: the help line under the bubble points to the site\'s own page')

    def test_the_check_catches_what_can_go_wrong(self):
        def problems(change):
            data = batch()
            change(data['affirmations'])
            return ' '.join(extras.check_affirmations(data))
        self.assertEqual(extras.check_affirmations(batch()), [])
        self.assertIn('empty', problems(lambda j: j[0].update(text=' ')))
        self.assertIn('characters', problems(lambda j: j[0].update(text='kind ' * 50 + 'word')))
        self.assertIn('no markup', problems(lambda j: j[0].update(text='A <b>bold</b> word.')))
        self.assertIn('no markup', problems(lambda j: j[0].update(text='One | two.')), 'the page splits a picture on this mark')
        self.assertIn('true or false', problems(lambda j: j[0].update(approved='yes')))
        self.assertIn('listed twice', problems(lambda j: j[1].update(text=j[0]['text'])))
        # The day an affirmation shows comes from its place in the list, so it has no date of its own.
        self.assertIn('date is not something an affirmation has', problems(lambda j: j[0].update(date='2030-01-01')))
        # Who is in the picture, her pose and her sweater are optional, and checked when given.
        self.assertEqual(problems(lambda j: j[0].update(cast=['atlas', 'delilah'], pose='tree', sweater='plum')), '')
        self.assertEqual(problems(lambda j: j[0].update(cast=[])), '', 'Deborah alone')
        self.assertIn('cast is a list', problems(lambda j: j[0].update(cast=['the dog'])))
        self.assertIn('cast is a list', problems(lambda j: j[0].update(cast=['atlas', 'atlas'])))
        self.assertIn('cast is a list', problems(lambda j: j[0].update(cast='atlas')))
        self.assertIn('pose is one of', problems(lambda j: j[0].update(pose='handstand')))
        self.assertIn('sweater is one of', problems(lambda j: j[0].update(sweater='tuxedo')))

    def test_only_approved_affirmations_are_ever_published(self):
        data = batch()
        data['affirmations'][1]['approved'] = False
        self.assertEqual(extras.approved_affirmations(data), ['Kind word number 1.', 'Kind word number 3.'])
        self.assertEqual(extras.approved_affirmations(batch(approved=False)), [])
        real = extras.read_affirmations()
        pages = [read(rel) for rel in FRONT] + ([read('affirmations.html')] if (ROOT / 'affirmations.html').exists() else [])
        for j in real['affirmations']:
            if j['approved'] is True:
                continue
            for page in pages:
                self.assertNotIn(j['text'], page, 'an affirmation the owner has not approved is in a page')
                self.assertNotIn(json.dumps(j['text'], ensure_ascii=False), page)
        # The same holds for the picture: an affirmation's pose, sweater, children and caption wait for its approval.
        data = batch()
        data['affirmations'][1].update(approved=False, pose='goddess', sweater='plum', cast=['atlas'])
        self.assertEqual(len(extras.approved_looks(data)), 2)
        self.assertNotIn('goddess|plum|atlas', ' '.join(extras.scene_data(extras.approved_looks(data))['d']))
        self.assertEqual(extras.approved_looks(batch(approved=False)), [])

    def test_the_pages_match_the_affirmations_on_file(self):
        sayings, saying_looks = extras.approved_affirmations(), extras.approved_looks()
        home, ohio = read('index.html'), read('ohio/index.html')
        self.assertEqual(extras.render_ohio(ohio, sayings, saying_looks), ohio, 'run python3 scripts/home_extras.py')
        if not sayings:
            for rel, page in (('index.html', home), ('ohio/index.html', ohio)):
                for part in ('id="affirm"', 'affirmations-data', 'id="scene-data"', 'scene-cap', 'scene-foot', 'affirmations.html'):
                    self.assertNotIn(part, page, f'{rel}: nothing about affirmations until some are approved')
            self.assertFalse((ROOT / 'affirmations.html').exists(), 'no affirmations page until some are approved')
            return
        self.assertIn(extras.affirmation_bubble(sayings, 'affirmations.html', 'help.html#take-care'), home)
        self.assertIn(extras.affirmation_bubble(sayings, '../affirmations.html', 'wellbeing.html'), ohio)
        # The list page is plain words: every affirmation once, in the order on file, and no script.
        listing = read('affirmations.html')
        self.assertEqual(listing.count(extras.affirmation_list(sayings)), 1)
        self.assertEqual(listing.count('<li>'), len(sayings))
        self.assertIn('<a href="help.html#take-care">Find someone to talk to</a>', listing, 'the list points to people to talk to')
        for part in ('id="affirmations-data"', 'id="scene-data"', extras.AFFIRMATION_SCRIPT, '<svg class="scene"', 'ad-slot'):
            self.assertNotIn(part, listing, 'the list has no picture to dress, nothing to turn and no ad')
        # The old address of the jokes passes visitors on to the affirmations, and stays out of search.
        moved = read('jokes.html')
        self.assertIn('<meta http-equiv="refresh" content="0; url=affirmations.html">', moved)
        self.assertIn('<script>location.replace("affirmations.html"+location.search+location.hash)</script>', moved)
        self.assertIn('<meta name="robots" content="noindex">', moved)
        self.assertIn('<link rel="canonical" href="https://www.yogamomtalk.com/affirmations.html">', moved)
        for rel, page in (('index.html', home), ('ohio/index.html', ohio)):
            self.assertEqual(page.count('id="affirmations-data"'), 1, rel)
            self.assertEqual(page.count(extras.AFFIRMATION_SCRIPT), 1, f'{rel}: one script on the page')
            # The affirmation is in the picture, at the top: Deborah's speech bubble, straight above the drawing, before the choices.
            self.assertEqual(page.count('id="affirm"'), 1, rel)
            self.assertIn('<div class="scenebox" id="scene" style="position:relative"><div class="saying" id="affirm" hidden>', page, rel)
            self.assertIn('</div><svg class="scene"', page, f'{rel}: the bubble sits straight above the drawing')
            self.assertLess(page.index('id="affirm"'), page.index('<div class="tiles">'), f'{rel}: the affirmation is met before the choices')
            # Every affirmation brings its picture, and the same script shows both.
            self.assertEqual(page.count(extras.affirmation_scripts(sayings, saying_looks)), 1, rel)
            self.assertIn('</svg>' + extras.flip_bar(sayings) + '</div>', page, f'{rel}: the buttons that flip lie along the floor of the drawing')
            block = page[page.index('id="affirmations-data">') + len('id="affirmations-data">'):]
            self.assertEqual(json.loads(block[:block.index('</script>')]), sayings, f'{rel}: the approved affirmations, in the order on file')
            block = page[page.index('id="scene-data">') + len('id="scene-data">'):]
            scene = json.loads(block[:block.index('</script>')])
            self.assertEqual(len(scene['d']), len(sayings), f'{rel}: a picture for each affirmation')
        sitemap = read('sitemap.xml')
        self.assertIn('<url><loc>https://www.yogamomtalk.com/affirmations.html</loc></url>', sitemap)
        self.assertNotIn('jokes.html', sitemap, 'the old address only passes visitors on')

    def test_no_affirmation_block_without_an_approved_affirmation(self):
        self.assertEqual(extras.affirmation_bubble([], 'affirmations.html', 'help.html#take-care'), '')
        self.assertEqual(extras.flip_bar([]), '')
        self.assertEqual(extras.affirmation_scripts([], []), '')
        self.assertEqual(extras.scene_block(True), f'<div class="scenebox" id="scene" style="position:relative">{extras.scene_svg(True)}</div>',
                         'the picture alone: no bubble, no buttons, no caption')
        with self.assertRaises(SystemExit, msg='an affirmation with no picture, or a picture with no affirmation, is refused'):
            extras.affirmation_scripts(['One.', 'Two.'], extras.approved_looks(batch(1)))

    def test_the_card_starts_hidden_and_has_its_buttons(self):
        sayings = extras.approved_affirmations(batch())
        bubble = extras.affirmation_bubble(sayings, '../affirmations.html', 'wellbeing.html')
        self.assertTrue(bubble.startswith('<div class="saying" id="affirm" hidden>'), 'no empty bubble when the script does not run')
        self.assertIn('<h2>A kind word for today</h2>', bubble)
        self.assertIn('<p class="affirmtext" id="affirm-text"></p>', bubble)
        self.assertIn('<a href="../affirmations.html">More kind words</a>', bubble)
        # One gentle line under the affirmation points to the site's own page of people to talk to. It carries no number of its own.
        self.assertIn('<p class="sayhelp">Having a really hard time? <a href="wellbeing.html">Find someone to talk to</a></p>', bubble)
        self.assertLess(bubble.index('id="affirm-text"'), bubble.index('class="sayhelp"'))
        self.assertNotIn('tel:', bubble)
        self.assertNotIn('Kind word number', bubble, 'the affirmation itself is put in by the script')
        self.assertNotIn('aria-live', bubble, 'the day\'s affirmation is not read out over whatever a screen reader is saying')
        self.assertNotIn('<button', bubble, 'nothing turns by itself, so there is nothing to stop')
        bar = extras.flip_bar(sayings)
        self.assertTrue(bar.startswith('<div class="flipbar" id="scene-foot" style="position:absolute;'), 'where it lies is on the bar itself')
        self.assertIn(' hidden>', bar[:bar.index('>') + 1], 'the buttons do nothing without the script, so they wait for it')
        self.assertRegex(bar, r'<button type="button" id="affirm-prev" aria-label="Previous affirmation"><svg [^>]*aria-hidden="true"')
        self.assertRegex(bar, r'<button type="button" id="affirm-next" aria-label="Next affirmation"><svg [^>]*aria-hidden="true"')
        self.assertLess(bar.index('id="affirm-prev"'), bar.index('id="scene-cap"'))
        self.assertLess(bar.index('id="scene-cap"'), bar.index('id="affirm-next"'), 'Back, what she is working on, Next')
        for part in (bubble, bar):
            self.assertNotIn('aria-hidden="true"', re.sub(r'<svg [^>]*>.*?</svg>', '', part), 'only the little pictures in the buttons are hidden from screen readers')
            self.assertEqual(len(re.findall(r'<svg ', part)), len(re.findall(r'<svg width="14" height="14" ', part)), 'each carries its own size')
        built = card(False, sayings)
        self.assertEqual(built.count('<button '), 2)
        self.assertEqual(built.count('type="button"'), 2, 'neither can send a form')
        self.assertEqual(extras.affirmation_list(sayings),
                         '<ol class="affirmlist"><li>Kind word number 1.</li><li>Kind word number 2.</li><li>Kind word number 3.</li></ol>')

    def test_an_affirmation_cannot_break_out_of_the_page(self):
        nasty = ['Ha</script><script>alert(1)</script> & "quotes"']
        block = extras.affirmations_data(nasty)
        self.assertEqual(block.count('</script>'), 1)
        self.assertEqual(json.loads(block[block.index('>') + 1:block.rindex('<')]), nasty)
        self.assertNotIn('<script>', extras.affirmation_list(nasty))
        self.assertIn('&lt;/script&gt;', extras.affirmation_list(nasty))

    def test_the_script_sends_and_stores_nothing(self):
        for banned in ('fetch(', 'XMLHttpRequest', 'sendBeacon', 'document.cookie', 'cookie', 'localStorage', 'sessionStorage',
                       'WebSocket', 'http', 'innerHTML', 'outerHTML', 'insertAdjacent', 'document.write', 'eval(', 'Function(',
                       'createElement', 'location', 'navigator', 'setTimeout', 'Date.parse', 'toLocale', 'getTimezone'):
            self.assertNotIn(banned, extras.AFFIRMATION_SCRIPT, banned)
        self.assertIn('textContent', extras.AFFIRMATION_SCRIPT)
        self.assertIn(extras.DRESS, extras.AFFIRMATION_SCRIPT, 'the same few lines dress the picture')
        self.assertEqual(extras.AFFIRMATION_SCRIPT.count('<script>'), 1)
        # It reads the visitor's clock (for the day's affirmation, and the seasonal and late-night ones) and nothing else about them.
        self.assertEqual(extras.AFFIRMATION_SCRIPT.count('new Date()'), 1)

    def test_one_a_day_by_the_date(self):
        """The owner's call, November 20, 2026: a daily affirmation. The day picks it; nothing turns by itself."""
        for gone in ('setInterval', 'Math.random', 'clearInterval', 'TURN_SECONDS'):
            self.assertNotIn(gone, extras.AFFIRMATION_SCRIPT, gone)
        self.assertFalse(hasattr(extras, 'TURN_SECONDS'))
        self.assertIn('Date.UTC(now.getFullYear(),now.getMonth(),now.getDate())/864e5', extras.AFFIRMATION_SCRIPT,
                      'the day is counted on the visitor\'s own calendar, so it changes at her midnight')
        # The bubble keeps room for the longest affirmation, so nothing under the card moves when the reader flips.
        self.assertRegex(TEMPLATE, r'\.affirmtext\{[^}]*min-height:calc\(5\.2\*clamp\(')
        self.assertRegex(TEMPLATE, r'\.sayhelp\{')
        self.assertNotIn('.pp', TEMPLATE, 'no stop button, so no rule for one')

    def approving(self, data):
        """The affirmation file after `approve`, run on a copy."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'affirmations.json'
            path.write_text(json.dumps(data), encoding='utf-8')
            real, extras.AFFIRMATIONS = extras.AFFIRMATIONS, path
            try:
                extras.approve()
                return extras.read_affirmations()
            finally:
                extras.AFFIRMATIONS = real

    def test_approving_marks_every_waiting_affirmation(self):
        data = batch(4)
        data['affirmations'][1]['approved'] = data['affirmations'][3]['approved'] = False
        data['affirmations'][3]['cast'] = ['atlas']
        after = self.approving(data)
        self.assertEqual([j['text'] for j in after['affirmations']], [j['text'] for j in data['affirmations']], 'nothing moves')
        self.assertTrue(all(j['approved'] is True for j in after['affirmations']))
        self.assertEqual(after['affirmations'][3]['cast'], ['atlas'], 'an affirmation keeps its picture')
        self.assertEqual(extras.check_affirmations(after), [])
        with self.assertRaises(SystemExit, msg='nothing is waiting'):
            self.approving(batch())


class TranslationTests(unittest.TestCase):
    """A country page shows the day's affirmation in the language most of its people speak, over the English. Each
    language's lines are in data/affirmations-i18n/, one for each affirmation, in the same order."""

    def test_every_language_on_file_is_complete_and_follows_the_english(self):
        data = extras.read_affirmations()
        self.assertEqual(extras.check_translations(data), [])
        english = extras.approved_affirmations(data)
        for lang in extras.translation_langs():
            lines = extras.local_affirmations(lang, data)
            self.assertEqual(len(lines), len(english), lang)
            self.assertEqual(len(set(lines)), len(lines), f'{lang}: no line twice')
            self.assertFalse(set(lines) & set(english), f'{lang}: no line left in English')
            found = extras.read_translation(lang)
            self.assertEqual([j['en'] for j in found['affirmations']][:len(data['affirmations'])],
                             [j['text'] for j in data['affirmations']], f'{lang}: line for line with the English')

    def test_every_country_language_is_known(self):
        world = json.loads((ROOT / 'data/ymt/world.json').read_text(encoding='utf-8'))['countries']
        langs = set(extras.translation_langs())
        for c in world:
            self.assertRegex(c.get('lang', ''), extras.LANG_TAG, c['slug'])
        for slug, lang in {'india': 'hi', 'switzerland': 'de-CH', 'belgium': 'nl', 'kenya': 'sw', 'tanzania': 'sw',
                           'canada': 'en', 'nigeria': 'en', 'south-africa': 'en', 'philippines': 'en'}.items():
            self.assertEqual(next(c['lang'] for c in world if c['slug'] == slug), lang, slug)
        # A country whose language has no file yet stays in English: no half-made card.
        missing = sorted(c['slug'] for c in world if c['lang'] != 'en' and c['lang'] not in langs)
        for slug in missing:
            self.assertIsNone(extras.local_language(next(c['lang'] for c in world if c['slug'] == slug)), slug)

    def test_the_swiss_spell_without_eszett(self):
        swiss = extras.local_affirmations('de-CH')
        self.assertFalse(any('\u00df' in line for line in swiss))
        self.assertTrue(any('\u00df' in line for line in extras.local_affirmations('de')), 'the German has some to swap')

    def test_the_check_catches_what_can_go_wrong(self):
        data = {'affirmations': [{'text': 'One.', 'approved': True}, {'text': 'Two.', 'approved': True}, {'text': 'Three.', 'approved': False}]}

        def problems(change, name='fr'):
            found = {'lang': name, 'name': 'French', 'dir': 'rtl' if name in extras.RTL else 'ltr',
                     'affirmations': [{'en': 'One.', 'text': 'Un.'}, {'en': 'Two.', 'text': 'Deux.'}]}
            change(found)
            return ' '.join(extras.check_translation(found, data, name))
        self.assertEqual(problems(lambda f: None), '', 'a line may wait for an unapproved affirmation')
        self.assertIn('lang must be', problems(lambda f: f.update(lang='de')))
        self.assertIn('dir must be "rtl"', problems(lambda f: f.update(dir='ltr'), 'ar'))
        self.assertIn('dir must be "ltr"', problems(lambda f: f.update(dir='rtl')))
        self.assertIn('has no fr line yet', problems(lambda f: f['affirmations'].pop()))
        self.assertIn('translate it again', problems(lambda f: f['affirmations'][0].update(en='Once.')))
        self.assertIn('still in English', problems(lambda f: f['affirmations'][0].update(text='One.')))
        self.assertIn('no markup', problems(lambda f: f['affirmations'][0].update(text='<b>Un</b>.')))
        self.assertIn('stray spaces', problems(lambda f: f['affirmations'][0].update(text=' Un.')))
        self.assertIn('twice', problems(lambda f: f['affirmations'][1].update(text='Un.')))
        self.assertIn('4 lines', problems(lambda f: f['affirmations'].extend([{'en': 'x', 'text': 'y'}] * 2)))

    def test_english_and_unknown_languages_stay_english(self):
        for lang in (None, '', 'en', 'en-GB', 'xx'):
            self.assertIsNone(extras.local_language(lang), lang)
        self.assertEqual(extras.local_language('ar'), ('ar', 'rtl'))
        self.assertEqual(extras.local_language('ja'), ('ja', 'ltr'))
        plain = extras.affirmation_card(['One.'], 'a.html', 'b.html')
        self.assertNotIn('affirm-local', plain)
        local = extras.affirmation_card(['One.'], 'a.html', 'b.html', ('he', 'rtl'))
        self.assertIn('<p class="affirmlocal" id="affirm-local" lang="he" dir="rtl" hidden></p>', local)
        self.assertIn('<p class="affirmtext" id="affirm-text" lang="en"></p>', local)

    def test_each_language_file_is_written_and_safe_in_a_page(self):
        for lang in extras.translation_langs():
            path = ROOT / extras.LOCAL_JS.format(lang=lang)
            self.assertTrue(path.exists(), path)
            code = path.read_text(encoding='utf-8')
            self.assertEqual(code, extras.affirmation_local_script(lang), f'{path} is up to date')
            self.assertNotIn('</script', code.lower())
            self.assertNotIn('http', code.split('\n', 1)[1], 'it loads nothing')


class StoryTests(unittest.TestCase):
    """An affirmation and its picture are one little story: her pose, her sweater, which children are around, and the caption."""

    def test_every_affirmation_on_file_has_its_picture(self):
        data = extras.read_affirmations()
        saying_looks = extras.looks(data)
        self.assertEqual(len(saying_looks), len(data['affirmations']))
        for j, (pose, sweater, cast, words, acts, when) in zip(data['affirmations'], saying_looks):
            self.assertEqual([a.split('.')[0] for a in acts], list(extras.KIDS), 'something to do for every child')
            for a in acts:
                kid, what = a.split('.')
                self.assertIn(what, extras.ACTS[kid])
                if kid in (j.get('do') or {}):
                    self.assertEqual(what, j['do'][kid], 'what a story says a child is doing, it gets')
            self.assertEqual(when, j.get('when') or '')
            if when:
                self.assertIn(sweater, extras.SEASON_SWEATERS[when], 'a seasonal story wears a sweater of its season')
            else:
                self.assertIn(sweater, extras.EVERYDAY_SWEATERS, 'and an everyday one never does')
            if 'delilah.copy' in acts and 'delilah' in cast:
                self.assertIn(pose, extras.COPY_POSES, 'she copies her mother only when there are arms up to copy')
            if when == 'night':
                self.assertEqual((cast, pose), ((), 'easy'), 'after bedtime the children are asleep')
            self.assertIn(pose, extras.POSES)
            self.assertIn(sweater, extras.SWEATERS)
            self.assertTrue(set(cast) <= set(extras.KIDS))
            self.assertEqual((j.get('pose') or pose, j.get('sweater') or sweater), (pose, sweater), 'what an affirmation names, it gets')
            if 'cast' in j:
                self.assertEqual(list(cast), j['cast'])
            self.assertEqual(words, f'Deborah is working on {extras.POSES[pose]["name"]}.')
            self.assertNotIn('|', words + ''.join(cast), 'the page keeps a picture as one line split on this mark')

    def test_there_are_plenty_of_stories_and_everyone_is_in_some(self):
        """The owner asked for about thirty little stories to flip through (November 17, 2026)."""
        data = extras.read_affirmations()
        told = [(j, look) for j, look in zip(data['affirmations'], extras.looks(data)) if j['approved'] is True]
        self.assertGreaterEqual(len(told), 30)
        for kid in extras.KIDS:
            self.assertGreaterEqual(sum(kid in look[2] for _, look in told), 8, f'{kid} is around in plenty of them')
        self.assertGreaterEqual(sum(not look[2] for _, look in told) + sum(len(look[2]) == 1 for _, look in told), 10, 'some are quiet')
        self.assertEqual({look[0] for _, look in told}, set(extras.POSES), 'every pose is in a story')
        self.assertEqual({look[1] for _, look in told}, set(extras.SWEATERS), 'and every sweater')
        # The site does not print the children's names.
        for j in data['affirmations']:
            for name in extras.KID_NAMES.values():
                self.assertNotIn(name, j['text'], 'the affirmations name no child')

    def test_poses_and_sweaters_take_turns(self):
        saying_looks = extras.looks(batch(40))
        for part, names in ((0, extras.POSES), (1, extras.EVERYDAY_SWEATERS)):
            worn = [look[part] for look in saying_looks]
            self.assertEqual(set(worn), set(names), 'all of them come round')
            for gap in (1, 2):
                self.assertTrue(all(a != b for a, b in zip(worn, worn[gap:])), 'never the same twice in three')
        around = [look[2] for look in saying_looks]
        self.assertEqual(around[:len(extras.CASTS)], list(extras.CASTS), 'with no cast named, who is around takes turns')
        self.assertTrue(all(a != b for a, b in zip(around, around[1:])), 'never the same children twice running')
        # An affirmation that names who is around gets them, and the ones on either side step aside.
        named = batch(5)
        named['affirmations'][1]['cast'] = list(extras.CASTS[0])
        named['affirmations'][3]['cast'] = list(extras.CASTS[2])
        around = [look[2] for look in extras.looks(named)]
        self.assertEqual((around[1], around[3]), (extras.CASTS[0], extras.CASTS[2]))
        self.assertTrue(all(a != b for a, b in zip(around, around[1:])), around)
        # An affirmation that names its pose gets it, and the ones around it step aside.
        data = batch(6)
        data['affirmations'][2]['pose'] = 'tree'
        data['affirmations'][3]['sweater'] = extras.FIRST_SWEATER
        worn = extras.looks(data)
        self.assertEqual(worn[2][0], 'tree')
        self.assertEqual(worn[3][1], extras.FIRST_SWEATER)
        for part in (0, 1):
            names = [look[part] for look in worn]
            for gap in (1, 2):
                self.assertTrue(all(a != b for a, b in zip(names, names[gap:])), names)

    def test_the_caption_is_about_deborah(self):
        """One short line: what she is working on. The children are in the picture, and that is enough."""
        self.assertEqual(extras.caption('tree'), 'Deborah is working on tree pose.')
        self.assertEqual(extras.caption('warrior2'), 'Deborah is working on warrior two.')
        for pose in extras.POSES:
            self.assertLessEqual(len(extras.caption(pose)), 36, 'one line between the two buttons, on a phone')
            self.assertNotIn('oday', extras.caption(pose), 'the caption is about the picture; the bubble already says today')
        self.assertRegex(TEMPLATE, r'\.scenecap\{[^}]*font-size:clamp\([^)]*vw[^)]*\)', 'and on a narrow phone the line is set smaller, not broken in two')
        data = batch(3)
        data['affirmations'][0]['cast'] = ['genevieve', 'atlas']
        for pose, _, _, words, _, _ in extras.looks(data):
            self.assertEqual(words, extras.caption(pose), 'whoever is around')

    def test_the_page_gets_what_the_script_needs(self):
        data = batch(3)
        data['affirmations'][1].update(cast=['atlas', 'genevieve'], pose='triangle', sweater='plum')
        scene = extras.scene_data(extras.approved_looks(data))
        self.assertEqual(set(scene), {'p', 'w', 'd', 's'})
        self.assertEqual(scene['s'], {k: list(v) for k, v in extras.WHENS.items()})
        self.assertEqual(set(scene['p']), set(extras.POSES))
        self.assertEqual(set(scene['w']), set(extras.SWEATERS))
        self.assertEqual(len(scene['d']), 3)
        self.assertTrue(scene['d'][1].startswith('triangle|plum|atlas genevieve|Deborah is working on triangle pose.|delilah.'))
        self.assertEqual(scene['d'][1].count('|'), 5, 'pose, sweater, children, caption, what each child is doing, and when')
        self.assertEqual(scene['p']['tree'], ['', '256.5px 168px', '50%'])
        self.assertEqual(scene['p']['triangle'][0], 'translate(8 4)rotate(-58 262 113)')
        self.assertEqual(scene['w']['plum'], list(extras.SWEATERS['plum']))
        for move, foot, tail in scene['p'].values():
            self.assertRegex(move, r'^(translate\(-?[\d.]+ -?[\d.]+\))?(rotate\(-?[\d.]+ 262 113\))?$')
            self.assertRegex(foot, r'^[\d.]+px [\d.]+px$')
        block = extras.affirmation_scripts(extras.approved_affirmations(data), extras.approved_looks(data))
        self.assertEqual(block.count('<script'), 3, 'the affirmations, the picture, and one script')
        self.assertEqual(block.count('<script>'), 1)
        self.assertLess(block.index('id="affirmations-data"'), block.index('id="scene-data"'))


class SeasonTests(unittest.TestCase):
    """The owner's call, November 18, 2026: the children do different things, holiday stories come out in their season,
    and there are late-night stories for after the children are in bed."""

    def test_the_check_holds_the_season_rules(self):
        def problems(**change):
            data = batch(1)
            data['affirmations'][0].update(change)
            return ' '.join(extras.check_affirmations(data))
        self.assertEqual(problems(when='winter', sweater='snowy', cast=['atlas'], do={'atlas': 'box'}), '')
        self.assertEqual(problems(when='night', cast=[], pose='easy'), '')
        self.assertIn('when is one of', problems(when='easter'))
        self.assertIn('does not go with', problems(sweater='pumpkin'), 'a pumpkin sweater stays in its season')
        self.assertIn('does not go with', problems(when='thanksgiving', sweater='heart'))
        self.assertIn('asleep', problems(when='night', cast=['delilah']), 'nobody is up after bedtime but her')
        self.assertIn('asleep', problems(when='night'), 'a late-night story says so: an empty cast')
        self.assertIn('asleep', problems(when='night', cast=[], pose='tree'))
        self.assertIn('do says', problems(cast=['atlas'], do={'atlas': 'skydiving'}))
        self.assertIn('not in the cast', problems(cast=['atlas'], do={'delilah': 'juice'}))
        self.assertIn('arms up', problems(cast=['delilah'], do={'delilah': 'copy'}, pose='goddess'))
        self.assertEqual(problems(cast=['delilah'], do={'delilah': 'copy'}, pose='tree'), '')

    def test_every_activity_and_season_is_in_a_story(self):
        told = extras.approved_looks()
        acts = {a for look in told for a in look[4] if a.split('.')[0] in look[2]}
        self.assertEqual(acts, {f'{k}.{a}' for k, v in extras.ACTS.items() for a in v}, 'every child does each of his or her things in some story')
        self.assertEqual({look[5] for look in told}, {''} | set(extras.WHENS))
        self.assertEqual({look[1] for look in told}, set(extras.SWEATERS))
        for when in extras.WHENS:
            self.assertGreaterEqual(sum(look[5] == when for look in told), 5, f'enough {when} stories to flip through')

    def test_the_picture_has_every_activity_and_season(self):
        svg = extras.scene_svg(True)
        for k, v in extras.ACTS.items():
            for a in v:
                tag = re.search(r'<g data-act="%s\.%s"( display="none")?>' % (k, a), svg)
                self.assertTrue(tag, f'{k} {a}')
                self.assertEqual(bool(tag.group(1)), a != v[0], 'the first is drawn showing, the others wait')
        for when in extras.WHENS:
            self.assertIn(f'data-when="{when}" display="none"', svg, f'{when} is drawn, and hidden until its story')
        self.assertNotRegex(svg, r'data-when="[a-z]+"(?! display="none")', 'nothing seasonal shows before the script picks')

    def test_the_seasons_are_the_right_days(self):
        self.assertEqual(extras.WHENS['thanksgiving'], ('d', 1115, 1130))
        self.assertEqual(extras.WHENS['winter'], ('d', 1201, 1231))
        self.assertEqual(extras.WHENS['night'], ('h', 21, 4), 'nine at night to five in the morning')


class PreviewTests(unittest.TestCase):
    """The page the owner looks at (scripts/affirmation_preview.py). It shows the picture card as the site draws it, for
    every affirmation on file, and it can hold affirmations nobody has approved, so it stays out of the site."""

    def test_it_shows_every_affirmation_with_the_site_s_own_picture(self):
        data = batch(4)
        for j in data['affirmations'][2:]:
            j['approved'] = False
        data['affirmations'][3]['cast'] = ['atlas', 'genevieve']
        html = preview.page(data)
        self.assertTrue(html.startswith('<!DOCTYPE html>'))
        order = ['Kind word number 3.', 'Kind word number 4.', 'Kind word number 1.', 'Kind word number 2.']  # the waiting ones come first
        for i, text in enumerate(order):
            self.assertEqual(html.count(f'data-item="{i}"'), 1)
            self.assertIn(f'data-item="{i}" aria-current="false">{text}<span class="who">', html)
        self.assertIn(extras.scene_block(False, order, '#', '#'), html, 'the card the front pages show')
        self.assertIn(extras.DRESS, html, 'dressed by the front pages\' own lines of script')
        self.assertIn(TEMPLATE, html, 'and moved by the same rules')
        self.assertIn('Waiting for your OK (2)', html)
        self.assertIn('In the turn on the site (2)', html)
        self.assertRegex(html, r'Atlas \([a-z]+\), Genevieve \([a-z]+\) · ', 'each affirmation says who is in its picture and what they are doing')
        self.assertEqual(html.count('data-try="pose"'), len(extras.POSES), 'and any pose, sweater or child can be tried')
        self.assertEqual(html.count('data-try="sweater"'), len(extras.SWEATERS))
        self.assertEqual(html.count('data-try="kid"'), len(extras.KIDS))
        self.assertIn('Preview. Not the site.', html)
        self.assertIn('<meta name="robots" content="noindex">', html)
        self.assertNotIn('setInterval', html, 'the preview does not turn by itself')

    def test_it_is_one_file_that_loads_nothing(self):
        html = preview.page(batch(3, approved=False))
        for banned in (' src=', '<link', '@import', 'http', 'fetch(', 'XMLHttpRequest', 'localStorage', 'document.cookie', '<iframe', '<img'):
            self.assertNotIn(banned, html, banned)
        self.assertTrue(all(ref.startswith('#sc-') for ref in re.findall(r'url\(([^)]*)\)', html)), 'only the drawing\'s own gradients and clips')
        self.assertEqual(html.count('<script>'), 1)
        self.assertNotIn('Waiting for your OK', preview.page(batch(2)), 'no heading for a list with nothing in it')
        self.assertNotIn('In the turn on the site', html)

    def test_it_is_never_written_into_the_repository(self):
        for inside in (ROOT / 'preview.html', ROOT / 'ohio' / 'preview.html', ROOT):
            real, sys.argv = sys.argv, ['affirmation_preview.py', str(inside)]
            try:
                with self.assertRaises(SystemExit):
                    preview.main()
            finally:
                sys.argv = real
        self.assertFalse((ROOT / 'preview.html').exists())
        self.assertFalse((ROOT / 'ohio' / 'preview.html').exists())
        with tempfile.TemporaryDirectory() as tmp:
            real, sys.argv = sys.argv, ['affirmation_preview.py', str(Path(tmp) / 'preview.html')]
            try:
                preview.main()
            finally:
                sys.argv = real
            written = (Path(tmp) / 'preview.html').read_text(encoding='utf-8')
        self.assertEqual(written, preview.page())
        for j in extras.read_affirmations()['affirmations']:
            self.assertIn(j['text'].replace('&', '&amp;'), written)


if __name__ == '__main__':
    unittest.main()
