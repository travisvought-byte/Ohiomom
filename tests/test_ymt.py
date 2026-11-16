"""Safety and integrity tests for the national Yoga Mom Talk pages. Run: python3 -m unittest discover tests"""
import re
import sys
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import ymt_build  # noqa: E402
import ymt_lib as lib  # noqa: E402

# Only the pages this build writes. The Ohio pages under ohio/ are separate source.
PAGES = sorted(ROOT / rel for rel in ymt_build.build_all(lib.load()) if rel.endswith('.html'))
EXIT_URL = 'https://www.google.com/search?q=weather'


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.ids, self.links, self.h1 = [], [], [], 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self.tags.append((tag, a))
        if 'id' in a:
            self.ids.append(a['id'])
        if tag == 'h1':
            self.h1 += 1


def parse(path):
    p = Page()
    p.feed(path.read_text(encoding='utf-8'))
    return p


class SiteTests(unittest.TestCase):
    def test_expected_pages_exist(self):
        data = lib.load()
        names = {str(p.relative_to(ROOT)) for p in PAGES}
        for n in ('index.html', 'help.html', 'connect.html', 'states.html', 'yoga.html', 'about.html', 'report.html', '404.html'):
            self.assertIn(n, names)
        for s in data['states']:
            self.assertIn(f"states/{s['abbr'].lower()}.html", names)
        self.assertEqual(len([n for n in names if n.startswith('states/')]), 51)

    def test_every_page_has_exit_button_and_privacy_meta(self):
        for path in PAGES:
            p = parse(path)
            exits = [a for t, a in p.tags if t == 'a' and 'data-exit' in a]
            self.assertEqual(len(exits), 1, f'{path}: needs exactly one Leave this site button')
            self.assertEqual(exits[0]['href'], EXIT_URL, path)
            metas = [a for t, a in p.tags if t == 'meta' and a.get('name') == 'referrer']
            self.assertEqual([m['content'] for m in metas], ['no-referrer'], f'{path}: referrer policy')

    def test_page_basics(self):
        for path in PAGES:
            p = parse(path)
            self.assertEqual(p.h1, 1, f'{path}: exactly one h1')
            self.assertEqual(len(p.ids), len(set(p.ids)), f'{path}: duplicate ids')
            html_tag = [a for t, a in p.tags if t == 'html'][0]
            self.assertEqual(html_tag.get('lang'), 'en', path)
            self.assertTrue([1 for t, a in p.tags if t == 'title'], path)

    def test_no_third_party_loading_or_tracking(self):
        for path in PAGES:
            for tag, a in parse(path).tags:
                if tag == 'link' and a.get('rel') == 'canonical':
                    continue  # a canonical link names the page itself; it loads nothing
                if tag in ('script', 'link', 'img', 'iframe', 'source', 'video', 'audio', 'form', 'input'):
                    ref = a.get('src') or (a.get('href') if tag == 'link' else '') or ''
                    self.assertFalse(ref.startswith(('http://', 'https://', '//')), f'{path}: external <{tag}> {ref}')
                    self.assertNotIn(tag, ('iframe', 'form', 'input'), f'{path}: unexpected <{tag}>')
        js = (ROOT / 'assets' / 'ymt.js').read_text(encoding='utf-8')
        for banned in ('fetch(', 'XMLHttpRequest', 'sendBeacon', 'document.cookie', 'localStorage', 'sessionStorage', 'WebSocket'):
            self.assertNotIn(banned, js)

    def test_internal_links_resolve(self):
        ids = {}
        for path in PAGES:
            ids[path] = set(parse(path).ids)
        for path in PAGES:
            for tag, a in parse(path).tags:
                href = a.get('href') if tag in ('a', 'link') else a.get('src') if tag == 'script' else None
                if not href or href.startswith(('http://', 'https://', 'mailto:', 'tel:')):
                    continue
                target_part, _, frag = href.partition('#')
                if target_part.startswith('/'):
                    target = ROOT / target_part.lstrip('/')
                elif target_part == '':
                    target = path
                else:
                    target = (path.parent / target_part).resolve()
                self.assertTrue(target.exists(), f'{path}: broken link {href}')
                if frag and target.suffix == '.html':
                    self.assertIn(frag, ids.get(target, set()), f'{path}: missing anchor {href}')

    def test_phone_links_match_visible_numbers(self):
        for path in PAGES:
            text = path.read_text(encoding='utf-8')
            for href, shown in re.findall(r'href="tel:([^"]+)">Call ([^<]+)<', text):
                digits = re.sub(r'\D', '', shown)
                self.assertTrue(href.endswith(digits), f'{path}: {href} vs {shown}')

    def test_no_shelter_addresses_or_unfilled_placeholders(self):
        for path in PAGES:
            text = path.read_text(encoding='utf-8')
            self.assertNotRegex(text, r'\{(state|slug|snap_slug)\}', path)

    def test_no_page_sends_visitors_to_ohiomom_org(self):
        """ohiomom.org is not the address the site is served on. No page may redirect or link there,
        and no canonical may name it, so the site works whether or not that domain is connected."""
        for path in ROOT.rglob('*.html'):
            if 'node_modules' in path.parts or 'templates' in path.parts:
                continue
            text = path.read_text(encoding='utf-8')
            self.assertNotRegex(text, r'(href|url|content)="https?://(www\.)?ohiomom\.org', path)
            self.assertNotRegex(text, r"location\.(replace|assign|href)\s*[(=]\s*['\"]https?://(www\.)?ohiomom\.org", path)

    def test_family_guide_points_home_to_ohio(self):
        text = (ROOT / 'family-guide.html').read_text(encoding='utf-8')
        self.assertIn('<link rel="canonical" href="https://www.yogamomtalk.com/family-guide.html">', text)
        self.assertNotIn('href="./"', text)
        self.assertTrue('<a class="logo" href="ohio/index.html" id="back-guide">' in text, 'the logo goes home to OhioMom')
        self.assertTrue('<link rel="stylesheet" href="ohio/assets/site.css">' in text, 'the guide wears the OhioMom look')

    def test_no_link_to_a_bare_folder(self):
        """Wix serves a folder address only at the site root: /ohio/ is a 404, /ohio/index.html loads."""
        for path in ROOT.rglob('*.html'):
            if 'node_modules' in path.parts:
                continue
            text = path.read_text(encoding='utf-8')
            for href in re.findall(r'(?:href|url)="([^"#?]*/)"', text):
                if href.startswith(('http://', 'https://')) and 'yogamomtalk.com' not in href:
                    continue
                self.assertIn(href, ('https://www.yogamomtalk.com/',), f'{path}: {href}')
            self.assertNotRegex(text, r'location\.replace\(["\'][^"\']*/["\']', path)

    def test_pages_do_not_claim_to_be_cookie_free(self):
        for path in ROOT.rglob('*.html'):
            if 'node_modules' in path.parts or 'templates' in path.parts:
                continue
            self.assertNotRegex(path.read_text(encoding='utf-8'), r'(?i)no (tracking, )?cookies|no third-party scripts', path)

    def test_front_pages_show_no_listings(self):
        """The front page asks what she needs. Listings appear only after she chooses."""
        for rel in ('index.html', 'ohio/index.html'):
            text = (ROOT / rel).read_text(encoding='utf-8')
            self.assertNotIn('class="card', text, f'{rel}: a front page shows no listing cards')
            self.assertEqual(text.count('class="tile '), 6, f'{rel}: six needs to choose from')
        home = (ROOT / 'index.html').read_text(encoding='utf-8')
        self.assertEqual(home.count('class="phonecard"'), 3)

    def test_needs_are_closed_and_cards_are_short(self):
        for path in PAGES:
            text = path.read_text(encoding='utf-8')
            self.assertNotRegex(text, r'<details[^>]*\sopen', f'{path}: nothing is open until it is asked for')
            for card in re.findall(r'<article class="card[^"]*" id="[^"]+">(.*?)</article>', text, re.S):
                visible = card.split('<details class="more">')[0]
                self.assertIn('<details class="more">', card, path)
                self.assertNotIn('Sources:', visible, f'{path}: sources belong in the details')
                self.assertNotIn('Next step:', visible, f'{path}: the next step belongs in the details')
                self.assertLessEqual(len(re.sub(r'<[^>]+>', '', visible)), 330, f'{path}: the short part of a card got long')

    def test_exit_link_is_inside_the_page_header(self):
        # Everything a screen reader meets is inside a landmark, the quick exit included.
        for path in PAGES:
            text = path.read_text(encoding='utf-8')
            self.assertIn('<header class="top"><a class="exit" data-exit ', text, path)
            self.assertEqual(text.count('<header'), 1, f'{path}: one banner')
            self.assertEqual(text.count('<main'), 1, path)

    def test_row_headings_sit_directly_in_the_summary(self):
        # A heading inside a <span> is not valid HTML. The row heading is a child of <summary>.
        for path in list(PAGES) + sorted((ROOT / 'ohio').rglob('*.html')):
            text = path.read_text(encoding='utf-8')
            self.assertNotIn('class="ntext"', text, path)
            self.assertIsNone(re.search(r'<span[^>]*>\s*<h[1-6]', text), f'{path}: heading inside a span')
        for script in ('ohio/assets/site.js', 'assets/ymt.js'):
            self.assertNotIn('ntext', (ROOT / script).read_text(encoding='utf-8'), script)

    def test_button_text_has_enough_contrast(self):
        def lum(h):
            r, g, b = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
            f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
            return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)
        for sheet in ('ohio/assets/site.css', 'assets/ymt.css'):
            css = (ROOT / sheet).read_text(encoding='utf-8')
            for name in ('brand', 'teal'):
                m = re.search(r'--%s:(#[0-9a-fA-F]{6})' % name, css)
                self.assertIsNotNone(m, f'{sheet}: --{name}')
                ratio = 1.05 / (lum(m.group(1)) + 0.05)
                self.assertGreaterEqual(ratio, 4.5, f'{sheet}: white text on --{name} {m.group(1)} is {ratio:.2f}:1')

    def test_front_page_says_what_the_site_is(self):
        text = (ROOT / 'index.html').read_text(encoding='utf-8')
        title = re.search(r'<title>(.*?)</title>', text).group(1)
        self.assertIn('Yoga Mom Talk', title)
        self.assertGreater(len(title), 30, 'the title says more than the name')
        import json
        about = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', text).group(1))
        self.assertEqual(about['@type'], 'WebSite')
        self.assertEqual(about['url'], 'https://www.yogamomtalk.com/')
        for path in PAGES:
            desc = re.search(r'<meta name="description" content="([^"]*)"', path.read_text(encoding='utf-8'))
            self.assertIsNotNone(desc, path)
            self.assertLessEqual(len(desc.group(1)), 165, f'{path}: description is cut off in search results past about 160 characters')

    def test_sitemap_lists_every_page_but_404_and_stubs(self):
        sm = (ROOT / 'sitemap.xml').read_text(encoding='utf-8')
        locs = re.findall(r'<loc>([^<]+)</loc>', sm)
        self.assertEqual(len(locs), len(set(locs)))
        ohio = [p for p in (ROOT / 'ohio').rglob('*.html')
                if 'name="robots" content="noindex"' not in p.read_text(encoding='utf-8')]
        # minus 404, plus the ohio pages that are not pass-through pages, plus the family guide
        self.assertEqual(len(locs), len(PAGES) - 1 + len(ohio) + 1)
        self.assertNotIn('https://www.yogamomtalk.com/ohio/help/disability.html', locs)
        self.assertIn('https://www.yogamomtalk.com/ohio/index.html', locs)
        self.assertIn('https://www.yogamomtalk.com/family-guide.html', locs)
        for loc in locs:
            self.assertNotIn('?', loc)

    def test_state_pages_use_their_own_state(self):
        data = lib.load()
        for s in data['states']:
            html = (ROOT / 'states' / f"{s['abbr'].lower()}.html").read_text(encoding='utf-8')
            self.assertIn(f"snap-directory-entry/{s['snap_slug']}", html)
            self.assertIn(f"childcare.gov/state-resources/{s['slug']}", html)
            self.assertIn(f"{s['name']}: help for moms", html)
        oh = (ROOT / 'states' / 'oh.html').read_text(encoding='utf-8')
        self.assertIn('href="../ohio/index.html"', oh)

    def test_old_ohio_urls_still_land_on_ohio_pages(self):
        stubs = ['events', 'near-you', 'counties', 'listen', 'wellbeing']
        moved = [f'{n}.html' for n in stubs]
        moved += [f'counties/{c}.html' for c in ('delaware', 'franklin', 'knox', 'morrow')]
        moved += [f'help/{h}.html' for h in ('bills', 'disability', 'pregnancy-baby', 'single-parent')]
        for old in moved:
            text = (ROOT / old).read_text(encoding='utf-8')
            m = re.search(r'http-equiv="refresh" content="0; url=([^"]+)"', text)
            self.assertTrue(m, f'{old}: stub must redirect')
            self.assertTrue(((ROOT / old).parent / m.group(1)).resolve().is_file(), f'{old}: target {m.group(1)} missing')
            self.assertIn('noindex', text)

    def test_ohio_pages_and_family_guide_kept(self):
        for rel in ('ohio/index.html', 'ohio/events.html', 'ohio/near-you.html', 'ohio/counties/knox.html',
                    'ohio/help/bills.html', 'ohio/assets/site.js', 'ohio/assets/data.json', 'family-guide.html',
                    'js/wix/form-store.js'):
            self.assertTrue((ROOT / rel).is_file(), rel)

    def test_ohiomom_domain_home_goes_to_ohio_landing(self):
        html = (ROOT / 'index.html').read_text(encoding='utf-8')
        self.assertRegex(html, r'ohiomom.*location\.replace\("ohio/index\.html"')
        for path in PAGES:
            if path.name != 'index.html' or path.parent != ROOT:
                self.assertNotIn('ohiomom\\.org', path.read_text(encoding='utf-8'), f'{path}: only the home page redirects')


if __name__ == '__main__':
    unittest.main()
