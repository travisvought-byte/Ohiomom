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

    def test_sitemap_lists_every_page_but_404_and_stubs(self):
        sm = (ROOT / 'sitemap.xml').read_text(encoding='utf-8')
        locs = re.findall(r'<loc>([^<]+)</loc>', sm)
        self.assertEqual(len(locs), len(set(locs)))
        ohio = [p for p in (ROOT / 'ohio').rglob('*.html')]
        self.assertEqual(len(locs), len(PAGES) - 1 + len(ohio) + 1)  # minus 404, plus ohio pages and the family guide
        self.assertIn('https://yogamomtalk.com/ohio/', locs)
        self.assertIn('https://yogamomtalk.com/family-guide.html', locs)
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
        self.assertRegex(html, r'ohiomom.*location\.replace\("ohio/"')
        for path in PAGES:
            if path.name != 'index.html' or path.parent != ROOT:
                self.assertNotIn('ohiomom\\.org', path.read_text(encoding='utf-8'), f'{path}: only the home page redirects')


if __name__ == '__main__':
    unittest.main()
