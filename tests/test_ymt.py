"""Safety and integrity tests for the national Yoga Mom Talk pages. Run: python3 -m unittest discover tests"""
import json
import re
import struct
import sys
import unittest
from html import escape as esc
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import home_extras  # noqa: E402
import ymt_build  # noqa: E402
import ymt_lib as lib  # noqa: E402

# Only the pages this build writes. The Ohio pages under ohio/ are separate source.
PAGES = sorted(ROOT / rel for rel in ymt_build.build_all(lib.load()) if rel.endswith('.html'))
COUNTY_CODES = {c['fips'] for c in lib.load()['counties']}
STATE_CODES = {s['abbr'] for s in lib.load()['states']}
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


def picture_size(path):
    """(width, height) of a JPEG or PNG file, read from its own header."""
    data = path.read_bytes()
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        return struct.unpack('>II', data[16:24])
    assert data[:2] == b'\xff\xd8', f'{path} is not a JPEG or PNG'
    i = 2
    while i < len(data):
        assert data[i] == 0xFF, path
        if data[i + 1] in (0xC0, 0xC1, 0xC2):
            height, width = struct.unpack('>HH', data[i + 5:i + 9])
            return width, height
        i += 2 + struct.unpack('>H', data[i + 2:i + 4])[0]
    raise AssertionError(f'{path}: no size found')


class SiteTests(unittest.TestCase):
    def test_expected_pages_exist(self):
        data = lib.load()
        names = {str(p.relative_to(ROOT)) for p in PAGES}
        for n in ('index.html', 'help.html', 'connect.html', 'states.html', 'yoga.html', 'about.html', 'privacy.html', 'report.html', '404.html'):
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
                    self.assertNotIn(tag, ('iframe', 'form'), f'{path}: unexpected <{tag}>')
                    if tag == 'input':
                        # The one field on these pages filters what is already on the page (or, on the county page,
                        # matches a ZIP code in the browser). With no form around it and no name, a browser has
                        # nowhere to send what is typed.
                        allowed = {('search', 'zip')} if path.name == 'county.html' else {('search', 'q')}
                        self.assertIn((a.get('type'), a.get('id')), allowed, f'{path}: unexpected <input>')
                        self.assertNotIn('name', a, f'{path}: the search field must not have a name')
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
                if frag and target_part and target.name == 'county.html' and target.parent == ROOT:
                    # The county page reads a county's code, or a state's two letters, from the address.
                    self.assertTrue(frag in COUNTY_CODES or frag.upper() in STATE_CODES, f'{path}: no county {href}')
                elif frag and target.suffix == '.html':
                    self.assertIn(frag, ids.get(target, set()), f'{path}: missing anchor {href}')

    def test_phone_links_match_visible_numbers(self):
        for path in PAGES:
            text = path.read_text(encoding='utf-8')
            for href, shown in re.findall(r'href="tel:([^"]+)">Call ([^<]+)<', text):
                digits = re.sub(r'\D', '', shown)
                self.assertTrue(href.endswith(digits), f'{path}: {href} vs {shown}')

    def test_country_pages_never_send_moms_to_911(self):
        """A mom in Ghana who reads "Call 911" calls nothing. Country pages give their own number, the world page none."""
        data = lib.load()
        for c in data['world']['countries']:
            text = (ROOT / f"countries/{c['slug']}.html").read_text(encoding='utf-8')
            self.assertIn(f"In danger right now? Call {c['emergency']['number']}.", text, c['slug'])
            if c['emergency']['number'] != '911':
                self.assertNotIn('Call 911.', text, f"{c['slug']} tells moms to call 911")
        world = (ROOT / 'world.html').read_text(encoding='utf-8')
        self.assertIn('Call your local emergency number.', world)
        self.assertNotIn('In danger right now? Call 911.', world)

    def test_location_pages_of_a_level_read_the_same(self):
        """Every state page has the same blocks in the same order, and so does every country page, however few listings
        a country has: the crisis phone cards first, then search, every need, the day's affirmation and the same closing
        lines. A thin country shows a plain line under a need it has nothing for, never an empty heading or list."""
        def blocks(text):
            return re.findall(r'<(?:section|details) class="([^"]+)"(?: id="([^"]+)")?', text)
        for level, sections in (('states', ymt_build.STATE_SECTIONS), ('countries', ymt_build.WORLD_SECTIONS)):
            pages = sorted((ROOT / level).glob('*.html'))
            self.assertTrue(pages, level)
            first = None
            for path in pages:
                text = path.read_text(encoding='utf-8')
                found = [i for c, i in blocks(text) if c.startswith('need')]
                self.assertEqual(found, sections, f'{path.name}: every need, in order')
                shape = [(c, i) for c, i in blocks(text) if not c.startswith(('need', 'more'))]
                first = first or shape
                self.assertEqual(shape, first, f'{path.name}: the same blocks as {pages[0].name}')
                self.assertEqual(text.count('class="wrap now" id="now"'), 1, f'{path.name}: one crisis block')
                self.assertEqual(text.count('id="affirm"'), 1, f'{path.name}: the day\'s affirmation')
                self.assertIn('Shelter addresses are never listed here, for safety.', text, path.name)
                self.assertNotRegex(text, r'<h[1-3][^>]*>\s*</h|<ul[^>]*>\s*</ul>|<div class="cards">\s*</div>|\bundefined\b', path.name)
                for need in re.findall(r'<details class="need[^"]*" id="[^"]+">.*?</details>(?=<details class="need|</section>)', text, re.S):
                    self.assertTrue('class="card' in need or 'class="pending"' in need, f'{path.name}: a need with nothing under it')
                if level == 'countries':
                    self.assertNotIn('dial 211', text, f'{path.name}: 211 is a U.S. number')
        self.assertIn('id="affirm"', (ROOT / 'county.html').read_text(encoding='utf-8'))

    def test_crisis_cards_come_right_after_the_heading(self):
        """On every state page, country page and the county page, the "Need help right now?" phone cards are the first
        thing after the heading, before search, the county picker's results or any need."""
        pages = sorted((ROOT / 'states').glob('*.html')) + sorted((ROOT / 'countries').glob('*.html')) + [ROOT / 'county.html']
        for path in pages:
            text = path.read_text(encoding='utf-8')
            main = text[text.index('<main id="main">'):]
            first_after_hero = re.search(r'<section class="hero[^"]*">.*?</div></section>\s*(<[^>]+>)', main, re.S).group(1)
            self.assertEqual(first_after_hero, '<section class="wrap now" id="now">', f'{path.name}: crisis cards first')
            self.assertEqual(main.count('class="wrap now" id="now"'), 1, path.name)
            self.assertIn('Need help right now?', main, path.name)

    def test_world_page_leads_with_the_emergency_line(self):
        """Above the map, one short line goes straight to the emergency numbers."""
        text = (ROOT / 'world.html').read_text(encoding='utf-8')
        line = text.find('<p class="dangerline"><a href="#now">')
        self.assertGreater(line, 0, 'the line is there')
        self.assertLess(line, text.find('<h1'), 'it comes first')
        self.assertLess(line, text.find('<svg class="worldmap"'), 'it comes before the map')
        self.assertIn('id="now"', text, 'it leads somewhere')

    def test_country_pages_load_only_their_own_language(self):
        """A country page in another language loads that language's affirmations and no other; an English-speaking
        country loads none, and nothing on a page loads from anywhere but the site."""
        langs = set(home_extras.translation_langs())
        for c in lib.load()['world']['countries']:
            text = (ROOT / 'countries' / f"{c['slug']}.html").read_text(encoding='utf-8')
            files = re.findall(r'<script src="\.\./assets/kindword/([^"]+)\.js"></script>', text)
            if c['lang'] in langs:
                self.assertEqual(files, [c['lang']], c['slug'])
                self.assertIn(f'lang="{c["lang"]}"', text, c['slug'])
                rtl = c['lang'].split('-')[0] in home_extras.RTL
                self.assertEqual('dir="rtl"' in text, rtl, c['slug'])
            else:
                self.assertEqual(files, [], c['slug'])
                self.assertNotIn('affirm-local', text, c['slug'])

    def test_world_map_shades_and_links_every_country(self):
        """Every country in world.json is pink and a link to its page on the world map, with its name for screen
        readers and a hover title; countries without a page are grey and not links. The same countries are in the
        list under the map, so nothing is lost without the map."""
        data = lib.load()
        text = (ROOT / 'world.html').read_text(encoding='utf-8')
        svg = re.search(r'<svg class="worldmap"[^>]*>(.*?)</svg>', text, re.S)
        self.assertIsNotNone(svg, 'world.html has the map')
        grey = re.search(r'<g class="land" aria-hidden="true">(.*?)</g>', svg.group(1), re.S).group(1)
        self.assertNotIn('<a', grey, 'grey countries are not links')
        # The rest of the world is drawn: every outline without a page of its own (fewer as countries are added).
        outlines = json.loads((ROOT / 'data/ymt/world-map.json').read_text(encoding='utf-8'))['countries']
        linked = {c['code'] for c in data['world']['countries']} | {'US'}
        self.assertEqual(grey.count('<path'), sum(1 for c in outlines if c.get('code') not in linked), 'the rest of the world is drawn')
        self.assertGreater(grey.count('<path'), 20, 'the rest of the world is drawn')
        covered = re.search(r'<g class="covered">(.*)</g>', svg.group(1), re.S).group(1)
        links = re.findall(r'<a href="([^"]+)" aria-label="([^"]+)" data-country="([A-Z]{2})">(.*?)</a>', covered, re.S)
        self.assertEqual(len(links), covered.count('<a '), 'every link on the map has a name')
        by_code = {code: (href, label, inner) for href, label, code, inner in links}
        listed = re.search(r'<details class="maplist">(.*?)</details>', text, re.S).group(1)
        for c in data['world']['countries']:
            self.assertIn(c['code'], by_code, f"{c['name']} is not on the map")
            href, label, inner = by_code[c['code']]
            self.assertEqual(href, f"countries/{c['slug']}.html", c['name'])
            self.assertEqual(label, esc(c['name']), c['name'])
            self.assertIn(f'<title>{esc(c["name"])}</title>', inner, c['name'])
            self.assertRegex(inner, r'<(path d="M|circle )', f"{c['name']} has a shape or a dot")
            self.assertTrue((ROOT / href).exists(), href)
            self.assertIn(f'href="{href}"', listed, f"{c['name']} is in the list under the map")
        self.assertEqual(by_code.get('US', ('',))[0], 'states.html', 'the United States leads to the states')
        self.assertEqual(len(by_code), len(data['world']['countries']) + 1, 'no link for a country without a page')
        self.assertNotIn('tabindex="-1"', svg.group(0), 'every country link can be reached from the keyboard')
        for small in ('SG', 'BB', 'BS', 'TT', 'BH', 'MU', 'FJ', 'ME', 'AL', 'AM', 'MK'):
            if small in by_code:
                self.assertIn('<circle ', by_code[small][2], f'{small} is big enough to tap')
        # The map stays small: the outlines file and the page.
        self.assertLess((ROOT / 'data/ymt/world-map.json').stat().st_size, 60_000)
        # The page grows by about 460 bytes a country (its emergency card, its list row and its map link).
        self.assertLess(len(text.encode('utf-8')), 125_000)

    def test_georgia_the_country_is_never_mixed_up_with_the_state(self):
        """Georgia is a country and a U.S. state. The country's page has its own address, says it is the country in its
        title, heading and map label, and links to the state's page, which links back."""
        data = lib.load()
        twins = [c for c in data['world']['countries'] if c.get('us_state')]
        self.assertIn('GE', [c['code'] for c in twins])
        state_slugs = {s['slug'] for s in data['states']}
        for c in twins:
            st = next(s for s in data['states'] if s['abbr'] == c['us_state'])
            self.assertNotIn(c['slug'], state_slugs, c['name'])
            self.assertIn('(the country)', c['name'])
            page = (ROOT / 'countries' / f"{c['slug']}.html").read_text(encoding='utf-8')
            self.assertIn(f'<title>{esc(c["name"])}: help for moms', page)
            self.assertIn(f'href="../states/{st["abbr"].lower()}.html"', page)
            state = (ROOT / 'states' / f"{st['abbr'].lower()}.html").read_text(encoding='utf-8')
            self.assertIn(f'href="../countries/{c["slug"]}.html"', state)
            self.assertIn(f'<title>{esc(st["name"])}: help for moms', state)
        world = (ROOT / 'world.html').read_text(encoding='utf-8')
        self.assertIn('aria-label="Georgia (the country)" data-country="GE"', world)

    def test_country_names_take_the_in_a_sentence(self):
        """Inside a sentence a the-country reads "in the Philippines", "in the Bahamas", "in the United Kingdom", never
        "in Philippines" or "in The Bahamas"; its heading and title keep the plain name. Every page the build writes is
        read, so a new country or a new sentence is checked too."""
        known = ('Bahamas', 'Central African Republic', 'Comoros', 'Czech Republic', 'Democratic Republic of the Congo',
                 'Dominican Republic', 'Gambia', 'Maldives', 'Marshall Islands', 'Netherlands', 'Philippines',
                 'Solomon Islands', 'United Arab Emirates', 'United Kingdom')
        countries = lib.load()['world']['countries']
        for c in countries:
            bare = c['name'][4:] if c['name'].startswith('The ') else c['name']
            if bare in known or c['name'].startswith('The '):
                self.assertEqual(ymt_build.in_name(c), 'the ' + bare, c['slug'])
                page = (ROOT / 'countries' / f"{c['slug']}.html").read_text(encoding='utf-8')
                self.assertIn(f'Free help for moms in the {esc(bare)}:', page, c['slug'])
                self.assertIn(f'<title>{esc(c["name"])}: help for moms', page, c['slug'])
            else:
                self.assertFalse(ymt_build.in_name(c).startswith('the '), c['slug'])
        names = '|'.join(re.escape(n) for n in known)
        bad = re.compile(rf'\b(?:in|In|for|of|from|to|across|than) (?:The )?(?:{names})\b|\b(?:in|for|of|from|to) The [A-Z]')
        for path in PAGES:
            text = path.read_text(encoding='utf-8')
            found = bad.search(text)
            self.assertIsNone(found, f'{path.relative_to(ROOT)}: "{found.group(0) if found else ""}" needs a lower-case "the"')
        self.assertEqual(ymt_build.possessive({'code': 'PH', 'name': 'Philippines'}), "the Philippines'")
        self.assertEqual(ymt_build.possessive({'code': 'GB', 'name': 'United Kingdom'}), "the United Kingdom's")
        self.assertEqual(ymt_build.possessive({'code': 'CA', 'name': 'Canada'}), "Canada's")

    def test_state_grid_has_every_state_once(self):
        data = lib.load()
        text = (ROOT / 'states.html').read_text(encoding='utf-8')
        grid = re.search(r'<ul class="usgrid"[^>]*>(.*?)</ul>', text, re.S)
        self.assertIsNotNone(grid, 'states.html has the state grid')
        tiles = re.findall(r'<li style="grid-area:(\d+)/(\d+)"><a href="states/([a-z]{2})\.html" title="([^"]+)">([A-Z]{2})'
                           r'<span class="sr"> ([^<]+)</span></a></li>', grid.group(1))
        self.assertEqual(len(tiles), grid.group(1).count('<li'), 'every tile is a plain link')
        self.assertEqual(len({(r, c) for r, c, *_ in tiles}), len(tiles), 'no two tiles in one place')
        self.assertEqual(sorted(a for _, _, a, *_ in tiles), sorted(s['abbr'].lower() for s in data['states']))
        names = {s['abbr']: s['name'] for s in data['states']}
        for _, _, a, title, shown, sr in tiles:
            self.assertEqual(shown, a.upper())
            self.assertEqual(title, esc(names[shown]))
            self.assertEqual(sr, esc(names[shown]))
        self.assertEqual(len(tiles), 51)
        listed = re.search(r'<details class="maplist">(.*?)</details>', text, re.S).group(1)
        for s in data['states']:
            self.assertIn(f'href="states/{s["abbr"].lower()}.html"', listed, f"{s['name']} is in the list under the grid")

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
        for rel, choices in (('index.html', 9), ('ohio/index.html', 10)):
            text = (ROOT / rel).read_text(encoding='utf-8')
            self.assertNotIn('class="card', text, f'{rel}: a front page shows no listing cards')
            self.assertEqual(text.count('class="tile '), choices, f'{rel}: the needs to choose from')
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

    def test_housing_and_shelter_is_its_own_need(self):
        """A mom who needs a place to stay finds it by name on the front page, the help page and every state page."""
        data = lib.load()
        home = (ROOT / 'index.html').read_text(encoding='utf-8')
        self.assertIn('href="help.html#housing"', home)
        self.assertIn('Housing and shelter', home)
        help_page = (ROOT / 'help.html').read_text(encoding='utf-8')
        row = re.search(r'<details class="need" id="housing">(.*?)</details>(?=<details class="need|</section>)', help_page, re.S).group(1)
        for rid in ('us-find-shelter', 'us-ywca', 'us-family-promise', 'us-salvation-army', 'us-housing-counselor'):
            self.assertIn(f'id="{rid}"', row, rid)
        self.assertIn('800-799-7233', row, 'the domestic violence hotline is shown under housing too')
        for s in data['states']:
            text = (ROOT / 'states' / f"{s['abbr'].lower()}.html").read_text(encoding='utf-8')
            row = re.search(r'<details class="need" id="housing">(.*?)</details>(?=<details class="need|</section>)', text, re.S).group(1)
            self.assertGreaterEqual(row.count('<article'), 10, s['name'])
            self.assertIn(f"https://www.hud.gov/states/{s['slug']}", row, s['name'])
            self.assertIn(f"https://www.womenslaw.org/find-help/{s['abbr'].lower()}/advocates-and-shelters/local-programs", row, s['name'])
            self.assertIn(f"Women&#x27;s shelters and advocates in {s['name']}", row)
        # Shelter addresses are never printed: housing listings carry phone numbers and websites only.
        for r in lib.all_records(data):
            if r['section'] == 'housing':
                self.assertNotIn('address', r, r['id'])

    def test_a_state_page_shows_every_listing_once_per_need(self):
        """A state page is everything for that state: its own offices, then every national listing it has no version of."""
        data = lib.load()
        national = {r['id'] for r in data['resources'] if r['section'] != 'connect'}
        for s in data['states']:
            text = (ROOT / 'states' / f"{s['abbr'].lower()}.html").read_text(encoding='utf-8')
            ids = re.findall(r'<article class="card[^"]*" id="([^"]+)">', text)
            self.assertEqual(len(ids), len(set(ids)), s['name'])
            shown = {i.split('--')[-1] for i in ids}
            have = {i.split('-', 1)[1] for i in shown if not i.startswith('us-')}
            missing = {n for n in national if n not in shown and ymt_build.REPLACED_BY_STATE.get(n) not in have}
            self.assertFalse(missing, f"{s['name']}: national listings left off the state page")
            doubled = {n for n in national if n in shown and ymt_build.REPLACED_BY_STATE.get(n) in have}
            self.assertFalse(doubled, f"{s['name']}: shown twice, once national and once for the state")
            self.assertGreaterEqual(len(shown), 44, s['name'])

    def test_search_only_filters_the_page(self):
        """The search box and "Show everything" are on the help page and every state page, and start hidden without the script."""
        pages = [ROOT / 'help.html'] + sorted((ROOT / 'states').glob('*.html'))
        for path in pages:
            text = path.read_text(encoding='utf-8')
            self.assertEqual(text.count('data-finder'), 1, path)
            self.assertRegex(text, r'<section class="wrap finder" id="everything" data-finder data-none="[^"]+" hidden>', path)
            self.assertIn('Nothing you type here is sent or saved.', text, path)
        self.assertNotIn('data-finder', (ROOT / 'index.html').read_text(encoding='utf-8'))

    def test_every_page_has_a_share_picture_and_an_icon(self):
        """A shared link shows our own picture, served from our own site, and a browser tab shows our icon."""
        home = f"https://{lib.load()['site']['domain']}/"
        ohio = [p for p in sorted((ROOT / 'ohio').rglob('*.html'))
                if 'name="robots" content="noindex"' not in p.read_text(encoding='utf-8')]
        expected = {path: 'assets/share.jpg' for path in PAGES}
        expected.update({path: 'ohio/assets/share.jpg' for path in ohio})
        expected[ROOT / 'family-guide.html'] = 'assets/share-family-guide.jpg'
        # 62 national pages (christmas.html among them), the world page and one page per country (data/ymt/world.json), the list of daily affirmations
        # and the old address of the jokes that passes visitors on to it, once an affirmation is approved; 24 Ohio pages;
        # the family guide
        world = 1 + len(lib.load()['world']['countries'])
        self.assertEqual(len(expected), 62 + world + (2 if home_extras.approved_affirmations() else 0) + 24 + 1)
        for path, picture in expected.items():
            p = parse(path)
            meta = {a.get('property') or a.get('name'): a.get('content') for t, a in p.tags if t == 'meta'}
            self.assertEqual(meta.get('og:image'), home + picture, f'{path}: the picture must be a full address on our own site')
            self.assertEqual((meta.get('og:image:width'), meta.get('og:image:height')), ('1200', '630'), path)
            self.assertGreater(len(meta.get('og:image:alt') or ''), 20, f'{path}: the picture needs words for people who cannot see it')
            self.assertEqual(meta.get('twitter:card'), 'summary_large_image', path)
            links = [a for t, a in p.tags if t == 'link' and a.get('rel') in ('icon', 'apple-touch-icon')]
            self.assertEqual(sorted(a['rel'] for a in links), ['apple-touch-icon', 'icon', 'icon'], path)
            for a in links:
                href = a['href']
                target = ROOT / href.lstrip('/') if href.startswith('/') else (path.parent / href).resolve()
                self.assertTrue(target.is_file(), f'{path}: {href} does not exist')
                self.assertEqual(target.parent, ROOT / 'assets', path)
        for picture in set(expected.values()):
            self.assertEqual(picture_size(ROOT / picture), (1200, 630), picture)
            self.assertLess((ROOT / picture).stat().st_size, 200_000, f'{picture}: keep it light for phones')
        self.assertEqual(picture_size(ROOT / 'assets/icon-180.png'), (180, 180))
        self.assertEqual(picture_size(ROOT / 'assets/icon-48.png'), (48, 48))
        self.assertIn('viewBox="0 0 64 64"', (ROOT / 'assets/icon.svg').read_text(encoding='utf-8'))

    def test_share_cards_only_say_what_the_site_says(self):
        """The cards are pictures, so their words are checked here against the promise printed on the pages."""
        cards = (ROOT / 'scripts/share_cards.py').read_text(encoding='utf-8')
        # The site may carry ads (the owners' decision, November 19, 2026), so no card promises there are none.
        self.assertEqual(cards.count("'second': 'Free. No sign-up.'"), 3)
        self.assertNotRegex(cards, r'(?i)no ads')
        self.assertIn('Free, with no sign-up.', (ROOT / 'index.html').read_text(encoding='utf-8'))
        self.assertNotIn('yogamomtalk.com/ohio', cards, 'that address is a folder, and Wix does not serve folders')

    def test_sitemap_lists_every_page_but_404_and_stubs(self):
        sm = (ROOT / 'sitemap.xml').read_text(encoding='utf-8')
        locs = re.findall(r'<loc>([^<]+)</loc>', sm)
        self.assertEqual(len(locs), len(set(locs)))
        ohio = [p for p in (ROOT / 'ohio').rglob('*.html')
                if 'name="robots" content="noindex"' not in p.read_text(encoding='utf-8')]
        stubs = [p for p in PAGES if 'name="robots" content="noindex"' in p.read_text(encoding='utf-8')]
        # minus 404 and the pages that only pass visitors on, plus the ohio pages that are not, plus the family guide
        self.assertEqual(len(locs), len(PAGES) - 1 - len(stubs) + len(ohio) + 1)
        self.assertNotIn('https://www.yogamomtalk.com/yoga.html', locs)
        self.assertNotIn('https://www.yogamomtalk.com/ohio/help/disability.html', locs)
        self.assertIn('https://www.yogamomtalk.com/ohio/index.html', locs)
        self.assertIn('https://www.yogamomtalk.com/family-guide.html', locs)
        for loc in locs:
            self.assertNotIn('?', loc)

    def test_yoga_sessions_are_offered_on_ohio_pages_only(self):
        """Deborah's sessions are in person in Ohio. National pages do not offer them; yoga.html passes visitors to OhioMom."""
        dest = lib.load()['site']['ohio_yoga_path']
        for path in PAGES:
            text = path.read_text(encoding='utf-8')
            if path.name == 'yoga.html':
                self.assertIn('name="robots" content="noindex"', text)
                self.assertIn(f'content="0; url={dest}"', text)
                continue
            self.assertNotIn('href="yoga.html"', text, path)
            self.assertNotIn('href="../yoga.html"', text, path)
            self.assertNotIn('Ask about a session', text, path)
        self.assertIn('yoga sessions with Deborah', (ROOT / 'states' / 'oh.html').read_text(encoding='utf-8'))
        self.assertTrue((ROOT / dest).exists())

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

    def test_about_pages_say_who_runs_the_site_and_the_photo_is_clean(self):
        """Both About pages show the same small photo, with words for it. The file is light and has no camera
        data in it (no place, no device), because it is a family photo on a public page."""
        photo = ROOT / 'assets' / 'about-us.jpg'
        data = photo.read_bytes()
        self.assertEqual(data[:2], b'\xff\xd8', 'the photo is a JPEG')
        self.assertLess(len(data), 40000, 'a phone should not have to wait for a family photo')
        i, markers = 2, []
        while i < len(data) and data[i + 1] != 0xDA:  # up to the start of the picture data
            markers.append(data[i + 1])
            i += 2 + struct.unpack('>H', data[i + 2:i + 4])[0]
        banned = [m for m in markers if 0xE1 <= m <= 0xEF or m == 0xFE]  # Exif, XMP, IPTC, other tags, comments
        self.assertEqual(banned, [], 'the photo carries camera or location data')
        width, height = picture_size(photo)
        for rel, src in (('about.html', 'assets/about-us.jpg'), ('ohio/about.html', '../assets/about-us.jpg')):
            path = ROOT / rel
            imgs = [a for t, a in parse(path).tags if t == 'img']
            self.assertEqual(len(imgs), 1, rel)
            self.assertEqual(imgs[0]['src'], src, rel)
            self.assertEqual((imgs[0]['width'], imgs[0]['height']), (str(width), str(height)), f'{rel}: the size is named, so the page does not jump')
            self.assertGreater(len(imgs[0].get('alt', '')), 20, f'{rel}: the photo needs words for people who cannot see it')
            text = path.read_text(encoding='utf-8')
            self.assertIn('it is just the two of us', text, rel)
            self.assertIn('<figcaption>Travis and Deborah</figcaption>', text, rel)

    def test_ohiomom_domain_home_goes_to_ohio_landing(self):
        html = (ROOT / 'index.html').read_text(encoding='utf-8')
        self.assertRegex(html, r'ohiomom.*location\.replace\("ohio/index\.html"')
        for path in PAGES:
            if path.name != 'index.html' or path.parent != ROOT:
                self.assertNotIn('ohiomom\\.org', path.read_text(encoding='utf-8'), f'{path}: only the home page redirects')


if __name__ == '__main__':
    unittest.main()
