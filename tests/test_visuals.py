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


class NeedGlanceTests(unittest.TestCase):
    """help.html and connect.html: one tile per need or part, with the count its own row or part shows."""
    def test_help_glance_counts_match_rows(self):
        text = read(ROOT / 'help.html')
        nav = re.search(r'<nav class="glance needglance"[^>]*>(.*?)</nav>', text, re.S)
        self.assertIsNotNone(nav)
        tiles = re.findall(r'<a href="#([a-z-]+)">.*?<span>([^<]+) <small><b>(\d+)</b> options?</small>', nav.group(1))
        rows = re.findall(r'<details class="need(?: urgent)?" id="([a-z-]+)"><summary>.*?<h2>([^<]+)</h2>.*?<span class="ncount">(\d+) ', text)
        self.assertEqual(tiles, [r for r in rows if r[2] != '0'])
        self.assertGreater(len(tiles), 8)

    def test_connect_glance_counts_match_sections(self):
        text = read(ROOT / 'connect.html')
        for sid, n in re.findall(r'<a href="#([a-z-]+)">.*?<b>(\d+)</b>', re.search(r'<nav class="glance needglance".*?</nav>', text, re.S).group(0)):
            with self.subTest(part=sid):
                part = re.search(rf'<section class="group wrap" id="{sid}">.*?</section>', text, re.S)
                self.assertIsNotNone(part)
                self.assertEqual(part.group(0).count('<article class="card'), int(n))


class SmallPagePictureTests(unittest.TestCase):
    def test_every_us_hub_and_topic_page_has_a_picture(self):
        """Every national page (not a country page or a page that only passes visitors on) shows a picture."""
        for page in PAGES:
            rel = page.relative_to(ROOT).as_posix()
            text = read(page)
            if rel.startswith('countries/') or 'http-equiv="refresh"' in text:
                continue
            main = re.search(r'<main.*?</main>', text, re.S).group(0)
            with self.subTest(page=rel):
                self.assertRegex(main, r'class="(glance|flow|art|summary|when|paths|worldmap|usgrid|agebar|scene|aboutphoto|steps-fig|iconlist)[ "]')

    def test_report_steps_and_summaries_are_page_text(self):
        report = read(ROOT / 'report.html')
        self.assertIn('<ol class="flow across" role="list">', report)
        for name in ('privacy.html', 'terms.html'):
            fig = re.search(r'<figure class="summary"><figcaption>At a glance</figcaption><ul class="iconlist" role="list">(.*?)</ul></figure>',
                            read(ROOT / name), re.S)
            with self.subTest(page=name):
                self.assertIsNotNone(fig)
                self.assertGreaterEqual(fig.group(1).count('<li>'), 3)


class OhioPictureTests(unittest.TestCase):
    """The OhioMom pictures (scripts/ohio_visuals.py) are page text or hidden decoration, and current."""
    def test_ohio_pictures_are_current_and_accessible(self):
        import ohio_visuals
        for page in ohio_visuals.PLAN:
            text = read(ROOT / 'ohio' / page)
            with self.subTest(page=page):
                self.assertEqual(text, ohio_visuals.render(page))
                block = re.findall(r'<!-- visuals -->(.*?)<!-- /visuals -->', text, re.S)
                self.assertTrue(block)
                for tag in re.findall(r'<svg\b[^>]*>', ''.join(block)):
                    hidden = 'aria-hidden="true"' in tag and 'focusable="false"' in tag
                    named = 'role="img"' in tag and 'aria-labelledby="' in tag
                    self.assertTrue(hidden or named, tag[:80])
                ids = set(re.findall(r'\bid="([^"]+)"', text))
                for href in re.findall(r'<a href="#([^"]+)"', ''.join(block)):
                    self.assertIn(href, ids)
                for href in re.findall(r'<use href="([^"#]+)#', ''.join(block)):
                    self.assertEqual(((ROOT / 'ohio' / page).parent / href).resolve(), SPRITE.resolve())

    def test_ohio_row_counts_are_the_rows_own(self):
        text = read(ROOT / 'ohio' / 'help' / 'housing.html')
        nav = re.search(r'<!-- visuals --><nav class="glance" aria-label="At a glance">(.*?)</nav>', text, re.S).group(1)
        for rid, count in re.findall(r'<a href="#([a-z-]+)">.*?<small>([^<]+)</small>', nav):
            row = re.search(rf'<details class="need[^"]*" id="{rid}"><summary>.*?<span class="ncount">([^<]+)</span>', text, re.S)
            self.assertEqual(row.group(1), count)

    def test_county_map_names_the_county_pages(self):
        text = read(ROOT / 'ohio' / 'counties.html')
        tiles = re.findall(r'href="counties/([a-z]+)\.html"', text)
        desc = re.search(r'<desc id="ohmap-d">([^<]+)</desc>', text).group(1)
        for county in tiles:
            self.assertIn(county.capitalize(), desc)


if __name__ == '__main__':
    unittest.main()
