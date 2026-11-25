"""Checks for the pictures on the built pages: the line icons, the at-a-glance counts, the step diagrams, the
Toys for Tots map and the family guide's age chart. Run: python3 -m unittest discover tests"""
import json
import re
import sys
import unittest
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import ymt_build  # noqa: E402
import ymt_lib as lib  # noqa: E402

SPRITE = ROOT / 'assets' / 'icons.svg'
PAGES = sorted(ROOT / rel for rel in ymt_build.build_all(lib.load()) if rel.endswith('.html')) + [ROOT / 'family-guide.html']
SVG_NS = '{http://www.w3.org/2000/svg}'


def read(path):
    return path.read_text(encoding='utf-8')


class SpriteTests(unittest.TestCase):
    def test_sprite_is_plain_line_icons(self):
        text = read(SPRITE)
        tree = ElementTree.fromstring(text)
        symbols = tree.findall(f'{SVG_NS}symbol')
        self.assertTrue(symbols)
        for sym in symbols:
            with self.subTest(icon=sym.get('id')):
                self.assertEqual(sym.get('viewBox'), '0 0 24 24')
                self.assertEqual(sym.get('stroke'), 'currentColor')
                self.assertEqual(sym.get('stroke-width'), '1.8')
                self.assertEqual(sym.get('fill'), 'none')
        # No styles, scripts, pictures or outside addresses: the file is drawn here and needs nothing else.
        for bad in ('<style', '<script', '<image', 'http:', 'https:', 'xlink:href', 'url('):
            self.assertNotIn(bad, text.replace('http://www.w3.org/2000/svg', ''))
        self.assertLess(len(text.encode()), 8000, 'keep the icon sprite small')

    def test_every_icon_used_exists_and_resolves(self):
        names = set(re.findall(r'<symbol id="([a-z-]+)"', read(SPRITE)))
        used = set()
        for page in PAGES:
            for href in re.findall(r'<use href="([^"]+)"', read(page)):
                path, _, name = href.partition('#')
                with self.subTest(page=page.relative_to(ROOT).as_posix(), href=href):
                    self.assertIn(name, names)
                    self.assertEqual((page.parent / path).resolve(), SPRITE.resolve())
                used.add(name)
        self.assertFalse(names - used, f'icons nobody uses: {sorted(names - used)}')


class InlineSvgTests(unittest.TestCase):
    def test_svgs_are_hidden_or_named(self):
        """Decoration is hidden from screen readers and keyboards; anything else carries a name."""
        for page in PAGES:
            for tag in re.findall(r'<svg\b[^>]*>', read(page)):
                with self.subTest(page=page.relative_to(ROOT).as_posix(), tag=tag[:80]):
                    hidden = 'aria-hidden="true"' in tag and 'focusable="false"' in tag
                    named = re.search(r'role="(img|group)"', tag) and 'aria-label="' in tag
                    self.assertTrue(hidden or named)

    def test_inline_art_is_small(self):
        for page in PAGES:
            for svg in re.findall(r'<svg class="art".*?</svg>', read(page), re.S):
                self.assertLess(len(svg.encode()), 6000, page)


class GlanceTests(unittest.TestCase):
    def test_county_glance_counts_match_rows(self):
        """Each at-a-glance number is the count its own row shows, and its link reaches that row."""
        checked = 0
        for page in PAGES:
            text = read(page)
            nav = re.search(r'<nav class="glance"[^>]*>(.*?)</nav>', text, re.S)
            if not nav:
                continue
            ids = set(re.findall(r'\bid="([^"]+)"', text))
            for rid, n in re.findall(r'<a href="#([a-z-]+)">.*?<b>([\d,]+)</b>', nav.group(1)):
                with self.subTest(page=page.relative_to(ROOT).as_posix(), row=rid):
                    self.assertIn(rid, ids)
                    row = re.search(rf'<details[^>]*\bid="{rid}".*?</summary>', text, re.S)
                    self.assertIsNotNone(row)
                    count = re.search(r'class="ncount"[^>]*>\s*([\d,]+)', row.group(0))
                    self.assertIsNotNone(count)
                    self.assertEqual(count.group(1), n)
                    self.assertNotEqual(n, '0')
            checked += 1
        self.assertGreater(checked, 3000)

    def test_state_glance_on_state_pages(self):
        text = read(ROOT / 'states' / 'oh.html')
        fig = re.search(r'<figure class="glance"><figcaption>(.*?)</figcaption>(.*?)</figure>', text, re.S)
        self.assertIsNotNone(fig)
        self.assertIn("Ohio's 88 counties", fig.group(1))
        self.assertEqual(len(re.findall(r'<li>', fig.group(2))), 6)


class DiagramTests(unittest.TestCase):
    def test_steps_are_real_ordered_lists(self):
        for name, cls in (('inside.html', 'flow across'), ('kinship.html', 'flow path')):
            text = read(ROOT / name)
            with self.subTest(page=name):
                self.assertIn(f'<ol class="{cls}" role="list">', text)
                self.assertNotIn(f'<ul class="{cls}"', text)
        when = re.search(r'<figure class="when">.*?</figure>', read(ROOT / 'christmas.html'), re.S).group(0)
        self.assertIn('<ol role="list">', when)
        self.assertEqual(when.count('<li>'), 4)

    def test_christmas_dates_come_from_the_listing(self):
        data = lib.load()
        santa = next(r for r in data['resources'] if r['id'] == 'us-operation-santa')
        date = re.search(r'postmarked by ([A-Z][a-z]+ \d{1,2}),', santa['how']).group(1)
        self.assertIn(f'<strong>{date}</strong>', read(ROOT / 'christmas.html'))

    def test_toys_for_tots_tiles_match_cards(self):
        text = read(ROOT / 'christmas.html')
        ids = set(re.findall(r'\bid="([^"]+)"', text))
        tiles = re.findall(r'<a class="t(\d)" href="#(tft-[a-z]{2})">[A-Z]{2} <small>(\d+)</small><span class="sr"> campaigns? in [^<]+</span></a>', text)
        self.assertGreater(len(tiles), 40)
        for shade, anchor, n in tiles:
            with self.subTest(tile=anchor):
                self.assertIn(anchor, ids)
                n = int(n)
                want = next(cls for top, cls in ymt_build.T4T_SHADES if n <= top)
                self.assertEqual(f't{shade}', want)


class FamilyGuideAgeBarTests(unittest.TestCase):
    def test_age_bar_is_text_with_spanish(self):
        text = read(ROOT / 'family-guide.html')
        fig = re.search(r'<figure class="agebar">.*?</figure>', text, re.S)
        self.assertIsNotNone(fig)
        fig = fig.group(0)
        self.assertIn('<ol role="list">', fig)
        for bar in re.findall(r'<span class="agerange[^"]*"[^>]*>', fig):
            self.assertIn('aria-hidden="true"', bar)
        es = json.loads(read(ROOT / 'data' / 'family-guide-es.json'))
        self.assertIn('agebar-title', es['static'])
        for key in re.findall(r'data-i18n-stage="([a-z-]+):', fig):
            self.assertIn(key, es['stages'])


if __name__ == '__main__':
    unittest.main()
