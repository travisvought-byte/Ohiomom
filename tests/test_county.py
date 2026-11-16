"""The county layer: its data files, the county page, and the pickers that lead to it.
Run: python3 -m unittest discover tests"""
import json
import re
import sys
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import county_data as cd  # noqa: E402
from us_geo import FIPS_STATE, STATE_FIPS  # noqa: E402

US = ROOT / 'assets' / 'us'
COUNTIES = json.loads((ROOT / 'data' / 'ymt' / 'counties.json').read_text(encoding='utf-8'))
SHARDS = {st: json.loads((US / f'{st.lower()}.json').read_text(encoding='utf-8')) for st in STATE_FIPS}
LEDGER = json.loads((ROOT / 'data' / 'county-links.json').read_text(encoding='utf-8'))['urls']
PHONE = re.compile(r'^\d{3}-\d{3}-\d{4}$')
SHOWN = ('ok', 'refused')


def rows(kind):
    """Every listing of one kind, with the state file it is in and whether it is a nearby one."""
    for st, shard in SHARDS.items():
        for fips, entry in shard['c'].items():
            for key, near in ((kind, False), (kind + 'Near', True)):
                for r in entry.get(key, []):
                    yield st, fips, near, r


class Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def tags(rel):
    p = Tags()
    p.feed((ROOT / rel).read_text(encoding='utf-8'))
    return p.tags


class CountyData(unittest.TestCase):
    def test_every_county_is_listed_once(self):
        self.assertEqual(len(COUNTIES), 3144, 'the 50 states and D.C. have 3,144 counties and county-equivalents')
        codes = [c['fips'] for c in COUNTIES]
        self.assertEqual(len(set(codes)), len(codes))
        for c in COUNTIES:
            self.assertEqual(FIPS_STATE[c['fips'][:2]], c['state'], c)
            self.assertEqual(SHARDS[c['state']]['c'][c['fips']]['n'], c['name'])
        self.assertEqual(sum(len(s['c']) for s in SHARDS.values()), 3144)
        self.assertEqual(sorted(c['name'] for c in COUNTIES if c['state'] == 'CT')[0], 'Capitol Planning Region')
        self.assertEqual(len([c for c in COUNTIES if c['state'] == 'OH']), 88)
        self.assertGreater(sum(c['pop'] for c in COUNTIES), 330_000_000)

    def test_health_centers_have_the_documented_shape(self):
        n = 0
        for st, fips, near, r in rows('health'):
            n += 1
            self.assertEqual(len(r), 11, r)
            org, name, street, city, z, phone, web, hours, seasonal, miles, where = r
            self.assertTrue(org and name and city, r)
            self.assertRegex(phone, PHONE)
            self.assertRegex(z, r'^(\d{5})?$')   # one Alaska village clinic has no ZIP in the list
            self.assertIn(where, STATE_FIPS)
            self.assertIn(seasonal, (0, 1))
            self.assertTrue(isinstance(hours, int) and hours >= 0)
            self.assertEqual(miles > 0, near, r)
            if near:
                self.assertLessEqual(miles, cd.NEAR_MILES['health'])
            else:
                self.assertEqual(where, st, r)
        self.assertGreater(n, 10000)

    def test_head_start_sites_have_the_documented_shape(self):
        n = 0
        for st, fips, near, r in rows('headStart'):
            n += 1
            self.assertEqual(len(r), 9, r)
            name, org, street, city, z, phone, kinds, miles, where = r
            self.assertTrue(name and city, r)
            self.assertRegex(phone, PHONE)
            self.assertTrue(1 <= kinds <= 15 and kinds & 3, r)
            self.assertEqual(miles > 0, near, r)
            if not near:
                self.assertEqual(where, st, r)
        self.assertGreater(n, 12000)

    def test_housing_counselors_are_in_the_state_file_that_names_them(self):
        for st, shard in SHARDS.items():
            used = set()
            for entry in shard['c'].values():
                for agency, miles in entry.get('hud', []):
                    self.assertIn(agency, shard['hu'])
                    self.assertTrue(0 <= miles <= cd.HUD_FAR_MILES)
                    used.add(agency)
            self.assertEqual(used, set(shard['hu']), f'{st}: every counselor in the file is shown somewhere')
            for a in shard['hu'].values():
                self.assertEqual(len(a), 10, a)
                self.assertRegex(a[4], PHONE)
                self.assertTrue(set(a[6]) <= set('RHDBP') and set(a[7]) <= set('FPVI'), a)

    def test_a_near_list_only_when_the_county_has_none(self):
        for shard in SHARDS.values():
            for e in shard['c'].values():
                self.assertFalse(e.get('health') and e.get('healthNear'))
                self.assertFalse(e.get('headStart') and e.get('headStartNear'))

    def test_every_website_button_passed_the_link_check(self):
        webs = [r[6] for _, _, _, r in rows('health') if r[6]] + [a[5] for s in SHARDS.values() for a in s['hu'].values() if a[5]]
        self.assertGreater(len(webs), 2000)
        for u in webs:
            self.assertIn(LEDGER.get(u), SHOWN, u)
            self.assertRegex(u, r'^https?://[a-z0-9.-]+\.[a-z]{2,}(/|$|\?)')

    def test_no_shelter_crisis_or_confidential_location(self):
        """A domestic violence location is never published, and a clinic inside a shelter is for the people staying there."""
        for _, _, _, r in rows('health'):
            self.assertFalse(cd.sensitive(r[1], r[2]), r)
        for _, _, _, r in rows('headStart'):
            self.assertFalse(cd.sensitive(r[0], r[2]), r)
        for s in SHARDS.values():
            for a in s['hu'].values():
                self.assertFalse(cd.sensitive(a[0], a[1], homes=False), a)
        self.assertTrue(cd.sensitive("Franklin Avenue Women's Shelter"))
        self.assertTrue(cd.sensitive('Domestic Violence Solutions', 'Anonymous'))
        self.assertFalse(cd.sensitive('PrimaryOne Health 3480 Refugee Road'))

    def test_zip_codes_find_their_county(self):
        known = {code for code in (c['fips'] for c in COUNTIES)}
        total = 0
        for d in '0123456789':
            table = json.loads((US / f'z{d}.json').read_text(encoding='utf-8'))
            total += len(table)
            for z, fips in table.items():
                self.assertTrue(z.startswith(d) and len(z) == 5 and z.isdigit(), z)
                self.assertIn(fips, known, z)
        self.assertGreater(total, 33000)
        z = lambda code: json.loads((US / f'z{code[0]}.json').read_text(encoding='utf-8')).get(code)  # noqa: E731
        self.assertEqual(z('43338'), '39117')   # Mount Gilead, Morrow County, Ohio
        self.assertEqual(z('10001'), '36061')   # Manhattan
        self.assertEqual(z('90210'), '06037')   # Los Angeles County
        self.assertEqual(z('06103'), '09110')   # Hartford, in the Capitol Planning Region

    def test_files_stay_light_enough_for_phones_and_for_wix(self):
        files = sorted(US.glob('*.json'))
        self.assertEqual(len(files), 61, '51 state files and 10 ZIP files')
        for p in files:
            self.assertLess(p.stat().st_size, 700_000, p.name)
        self.assertLess(sum(p.stat().st_size for p in files), 8_000_000, 'the whole site has to stay under 20 MB on Wix')

    def test_hand_built_county_pages_are_linked_from_their_county(self):
        guides = {e['pg'] for s in SHARDS.values() for e in s['c'].values() if 'pg' in e}
        self.assertEqual(guides, {f'ohio/counties/{p.name}' for p in (ROOT / 'ohio' / 'counties').glob('*.html')})
        self.assertEqual(SHARDS['OH']['c']['39117']['pg'], 'ohio/counties/morrow.html')


class CountyPages(unittest.TestCase):
    def test_county_page_offers_every_state_and_its_code(self):
        t = tags('county.html')
        opts = [a for tag, a in t if tag == 'option' and a.get('data-fips')]
        self.assertEqual({a['value'].upper(): a['data-fips'] for a in opts}, STATE_FIPS)
        ids = {a.get('id') for _, a in t}
        for need in ('cstate', 'ccounty', 'zip', 'cmsg', 'ctitle', 'clede', 'county-app', 'sources'):
            self.assertIn(need, ids)
        scripts = [a['src'] for tag, a in t if tag == 'script' and a.get('src')]
        self.assertEqual(scripts, ['assets/ymt.js', 'assets/county.js'])
        zipbox = [a for tag, a in t if tag == 'input']
        self.assertEqual(len(zipbox), 1)
        self.assertEqual((zipbox[0]['type'], zipbox[0]['id']), ('search', 'zip'))
        self.assertNotIn('name', zipbox[0], 'nothing typed can be sent')
        srcs = [a['data-src'] for tag, a in t if tag == 'a' and a.get('data-src')]
        self.assertEqual(sorted(srcs), ['hrsa', 'hrsa', 'hs', 'hs', 'hud', 'hud'])

    def test_every_state_page_leads_to_its_counties(self):
        for st in STATE_FIPS:
            t = tags(f'states/{st.lower()}.html')
            mine = sorted(c['fips'] for c in COUNTIES if c['state'] == st)
            values = [a['value'] for tag, a in t if tag == 'option' and a.get('value', '').startswith('../county.html#')]
            links = [a['href'] for tag, a in t if tag == 'a' and a.get('href', '').startswith('../county.html#')]
            shown = sorted(v.split('#')[1] for v in values + links)
            self.assertEqual(shown, mine, st)

    def test_county_script_only_reads_this_site(self):
        js = (ROOT / 'assets' / 'county.js').read_text(encoding='utf-8')
        for banned in ('XMLHttpRequest', 'sendBeacon', 'document.cookie', 'localStorage', 'sessionStorage', 'WebSocket',
                       'innerHTML', 'outerHTML', 'insertAdjacentHTML', 'eval(', 'new Function', 'document.write'):
            self.assertNotIn(banned, js)
        self.assertEqual(js.count('fetch('), 1, 'one place fetches, and only files under assets/us/')
        self.assertIn("var DATA = 'assets/us/';", js)
        self.assertNotRegex(js, r'''["']https?://''', 'no outside address is written into the script')
        self.assertIn("credentials: 'omit'", js)


if __name__ == '__main__':
    unittest.main()
