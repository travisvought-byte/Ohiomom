"""The OhioMom map (ohio/map.html). Run: python3 -m unittest discover tests

The map shows only places the site already has, from assets/us/oh.json, each in its own county. There is no
street-level position for any of them, so nothing here may claim one. The page must read as a plain list with
no script, load its map code from this site, and load no map tiles from anyone.
"""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import ohio_map  # noqa: E402


class OhioMapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = ohio_map.build()
        cls.page = (ROOT / 'ohio' / 'map.html').read_text(encoding='utf-8')
        cls.state = json.loads((ROOT / 'assets' / 'us' / 'oh.json').read_text(encoding='utf-8'))

    def test_files_match_the_data(self):
        self.assertEqual((ROOT / 'ohio' / 'assets' / 'map-places.json').read_text(encoding='utf-8'), ohio_map.dumps(self.data),
                         'run python3 scripts/ohio_map.py')
        self.assertEqual(self.page, ohio_map.page_text(self.data, self.page), 'run python3 scripts/ohio_map.py')

    def test_every_place_is_one_the_county_data_has_in_that_county(self):
        shapes = json.loads((ROOT / 'ohio' / 'assets' / 'map.json').read_text(encoding='utf-8'))['c']
        self.assertEqual(set(self.data['counties']), set(shapes), 'all 88 counties')
        names = {c['n'].removesuffix(' County'): c for c in self.state['c'].values()}
        for kind, county, name, street, city, zip_, phone, web, _more in self.data['places']:
            self.assertIn(kind, ohio_map.KINDS)
            c = names[county]
            if kind == 'health':
                rows = [r for r in c['health'] if r[1] == name and r[9] == 0]
            elif kind == 'start':
                rows = [r for r in c['headStart'] if r[0] == name and r[7] == 0]
            elif kind == 'housing':
                rows = [code for code, _m, how in c['pha'] if how == 'c' and self.state['ph'][code][0] == name]
            else:
                rows = [hid for hid, m in c['hud'] if m == 0 and self.state['hu'][hid][0] == name]
            self.assertTrue(rows, f'{name} is listed in {county} County in oh.json')
            self.assertRegex(zip_, r'^4[3-5]\d{3}$', f'{name}: an Ohio ZIP code')
            self.assertTrue(web == '' or web.startswith('https://'), f'{name}: {web}')
        self.assertGreater(len(self.data['places']), 900)

    def test_no_place_claims_a_position_the_site_does_not_have(self):
        text = (ROOT / 'ohio' / 'assets' / 'map-places.json').read_text(encoding='utf-8')
        self.assertNotRegex(text, r'"(lat|lon|lng|latitude|longitude)"')
        self.assertIn('Places are shown at the middle of their county, not at their street address.', self.page)

    def test_plain_list_works_without_the_script(self):
        block = re.search(r'<!--maplist-->(.*?)<!--/maplist-->', self.page, re.S).group(1)
        self.assertEqual(block.count('<details class="mapcounty"'), 88)
        self.assertEqual(block.count('<li>'), len(self.data['places']))
        self.assertNotRegex(block, r'href="https?:', 'no web links, so the monthly Ohio link check stays small')
        self.assertIn('<section class="wrap omapapp" data-mapapp hidden', self.page, 'the map shows only once its script runs')
        self.assertIn('<noscript>', self.page)

    def test_map_code_is_served_from_this_site_and_loads_no_tiles(self):
        for ref in re.findall(r'<(?:script|link)[^>]+(?:src|href)="([^"]+)"', self.page):
            if 'wix.com' in ref or ref.startswith('https://www.yogamomtalk.com/'):
                continue  # the Wix script every OhioMom page carries, and the page's own address
            self.assertFalse(re.match(r'(https?:)?//', ref), f'no CDN: {ref}')
            self.assertTrue((ROOT / 'ohio' / ref).resolve().exists(), ref)
        for rel in ('assets/vendor/leaflet.js', 'assets/vendor/leaflet.markercluster.js', 'assets/vendor/LICENSES.txt'):
            self.assertTrue((ROOT / rel).exists(), rel)
        self.assertIn('Leaflet 1.9.4', (ROOT / 'assets' / 'vendor' / 'leaflet.js').read_text(encoding='utf-8')[:200])
        script = (ROOT / 'ohio' / 'assets' / 'ohio-map.js').read_text(encoding='utf-8')
        self.assertNotRegex(script, r'tileLayer|openstreetmap|\{z\}/\{x\}')
        self.assertNotRegex(script, r'Math\.random|innerHTML\s*=\s*[^;]*\+\s*(it|p|e)\.(name|title|web|url)\b', 'every value goes through esc()')

    def test_the_map_is_linked_from_the_ohio_pages(self):
        for rel in ('ohio/index.html', 'ohio/near-you.html', 'ohio/counties.html'):
            self.assertIn('href="map.html"', (ROOT / rel).read_text(encoding='utf-8'), rel)
        self.assertIn('<a href="../map.html">Map</a>', (ROOT / 'ohio' / 'counties' / 'knox.html').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
