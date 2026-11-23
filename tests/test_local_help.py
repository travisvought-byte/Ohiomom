"""The local-help pipeline (scripts/local_help.py): parsers, normalizing, placing in counties, removing duplicates,
the safety screen, and the county page row it feeds. Runs offline on small made-up rows shaped like each source.
Run: python3 -m unittest discover tests"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import local_help as lh  # noqa: E402

REG = {s['id']: s for s in lh.load_registry()['sources']}


class Geo(lh.Geo):
    """The real ZIP -> county files, with a couple of town and ZIP centres instead of the Census gazetteer."""

    def __init__(self):
        super().__init__(Path(tempfile.mkdtemp()))
        self.places = {('OH', 'columbus'): (39.9612, -82.9988)}
        self.zc = {'43215': (39.96, -83.0), '43016': (40.1, -83.15)}
        self.cents = {'39049': (39.97, -83.01), '39041': (40.28, -83.0)}


GEO = Geo()


class Registry(unittest.TestCase):
    def test_registry_and_table_pass_the_check(self):
        self.assertEqual(lh.check(), [])

    def test_every_blocked_or_queued_source_says_why(self):
        for s in REG.values():
            if s['status'] != 'active':
                self.assertTrue(s.get('why'), s['id'])

    def test_active_sources_say_what_and_next(self):
        for s in REG.values():
            if s['status'] == 'active':
                self.assertTrue(s.get('what') and s.get('next'), s['id'])
                self.assertTrue(s['homepage'].startswith('https://'), s['id'])


class Parsers(unittest.TestCase):
    def test_parents_as_teachers_serves_its_zip_codes(self):
        raw = json.dumps([
            {'id': 682, 'title': '18 Degrees', 'street': '480 West Street', 'city': 'Pittsfield', 'state': 'MA',
             'postal_code': '01201-5865', 'country_code': 'US', 'lat': '42.4515', 'lng': '-73.2694',
             'phone': '(413) 448-8281', 'email': 'someone@example.org', 'website': '',
             'description_2': '01201| 01238| O6450| 01262', 'categories': '19'},
            {'id': 9, 'title': 'Pending one', 'state': 'MA', 'postal_code': '01201', 'phone': '413-448-8282', 'categories': '20'},
        ]).encode()
        rows = lh.parse(REG['pat-affiliates'], raw)
        self.assertEqual(len(rows), 1)
        r = lh.normalize(REG['pat-affiliates'], rows[0], GEO, '2026-11-23')
        self.assertEqual(r['county_fips'], '25003')   # Berkshire County
        self.assertEqual(r['phone'], '413-448-8281')
        self.assertNotIn('example.org', json.dumps(r))  # staff emails are never copied
        self.assertEqual(r['recheck_on'], '2026-12-23')

    def test_diaper_bank_page(self):
        body = ('<h4>Ohio</h4><ul><li>Columbus &#8211; <a href="https://columbusdiaperbank.org">Columbus Diaper Bank</a></li></ul>'
                '<h4>Alabama</h4><ul><li>Birmingham – <a href="http://bundlesdiaperbank.org/">Bundles of Hope Diaper Bank</a></li></ul>')
        rows = lh.parse(REG['ndbn-members'], json.dumps({'content': {'rendered': body}}).encode())
        self.assertEqual([(r['state'], r['city'], r['name']) for r in rows],
                         [('OH', 'Columbus', 'Columbus Diaper Bank'), ('AL', 'Birmingham', 'Bundles of Hope Diaper Bank')])
        r = lh.normalize(REG['ndbn-members'], rows[0], GEO, '2026-11-23')
        self.assertEqual(r['county_fips'], '39049')   # placed by its town: Franklin County
        self.assertEqual(r['website'], 'https://columbusdiaperbank.org')

    def test_la_leche_league_keeps_no_leader_contacts(self):
        raw = json.dumps([
            {'id': '113', 'map_id': '3', 'title': 'Bakersfield', 'address': 'Bakersfield, CA 93301', 'lat': '35.38',
             'lng': '-119.01', 'link': 'https://lllusa.org/groups/bakersfield', 'description': 'Call Jane at 661-555-0100'},
            {'id': '7', 'map_id': '1', 'title': 'Live Love Latch', 'address': 'Somewhere'},
        ]).encode()
        rows = lh.parse(REG['lllusa-groups'], raw)
        self.assertEqual(len(rows), 1)
        r = lh.normalize(REG['lllusa-groups'], rows[0], GEO, '2026-11-23')
        self.assertEqual(r['county_fips'], '06029')   # Kern County, from the ZIP code
        self.assertNotIn('Jane', json.dumps(r))
        self.assertEqual(r['name'], 'La Leche League: Bakersfield')

    def test_npi_registry_keeps_primary_public_health_only(self):
        raw = json.dumps([
            {'number': 1316506900, 'basic': {'organization_name': 'ASHLAND COUNTY GENERAL HEALTH DISTRICT'},
             'taxonomies': [{'code': '261QP0905X', 'primary': True}],
             'addresses': [{'address_purpose': 'MAILING', 'city': 'X'},
                           {'address_purpose': 'LOCATION', 'address_1': '1763 STATE ROUTE 60', 'city': 'ASHLAND',
                            'state': 'OH', 'postal_code': '448059239', 'telephone_number': '419-282-4357', 'country_code': 'US'}]},
            {'number': 2, 'basic': {'organization_name': 'SOME HOSPITAL'}, 'taxonomies': [{'code': '282N00000X', 'primary': True}],
             'addresses': [{'address_purpose': 'LOCATION', 'state': 'OH', 'postal_code': '44805', 'telephone_number': '419-282-0000'}]},
        ]).encode()
        rows = lh.parse(REG['nppes-public-health'], raw)
        self.assertEqual(len(rows), 1)
        r = lh.normalize(REG['nppes-public-health'], rows[0], GEO, '2026-11-23')
        self.assertEqual((r['name'], r['city'], r['county_fips']), ('Ashland County General Health District', 'Ashland', '39005'))

    def test_arcgis_layer_with_column_map(self):
        raw = json.dumps([{'FACILITY': 'Andrew County Health Department', 'ADDRESS': '106 North 5th Street', 'CITY': 'Savannah',
                           'ZIP': '64485', 'COUNTY': 'Andrew', 'PHONE': '(816) 324-3139', '_lat': 39.94, '_lon': -94.83}]).encode()
        rows = lh.parse(REG['mo-dhss-wic'], raw)
        r = lh.normalize(REG['mo-dhss-wic'], rows[0], GEO, '2026-11-23')
        self.assertEqual((r['state'], r['county_fips'], r['phone']), ('MO', '29003', '816-324-3139'))


class Normalize(unittest.TestCase):
    def src(self):
        return REG['wa-doh-wic']

    def test_shelters_and_confidential_sites_are_never_listed(self):
        for name in ('Hope Domestic Violence Shelter', 'Confidential Location'):
            self.assertIsNone(lh.normalize(self.src(), {'name': name, 'state': 'WA', 'zip': '98101', 'phone': '206-296-4600'},
                                           GEO, '2026-11-23'))

    def test_a_row_with_no_phone_or_website_is_dropped(self):
        self.assertIsNone(lh.normalize(self.src(), {'name': 'WIC', 'state': 'WA', 'zip': '98101'}, GEO, '2026-11-23'))

    def test_placeholder_phones_are_dropped(self):
        for raw in ('000-000-0000', '206-555-1234', '1234567'):
            self.assertEqual(lh.phone10(raw), '')
        self.assertEqual(lh.phone10('1 (206) 296-4600 ext 3'), '206-296-4600')

    def test_websites_are_https_and_not_social(self):
        self.assertEqual(lh.clean_url('www.kingcounty.gov/wic'), 'https://www.kingcounty.gov/wic')
        self.assertEqual(lh.clean_url('https://facebook.com/somegroup'), '')

    def test_a_zip_in_another_state_does_not_place_a_listing(self):
        r = lh.normalize(self.src(), {'name': 'Clinic', 'state': 'WA', 'zip': '43215', 'phone': '206-296-4600'}, GEO, '2026-11-23')
        self.assertIsNone(r)

    def test_duplicates_keep_the_government_row(self):
        a = lh.normalize(REG['oh-odh-lhd'], {'name': 'Delaware Public Health District', 'state': 'OH', 'zip': '43015',
                                             'phone': '740-368-1700'}, GEO, '2026-11-23')
        b = lh.normalize(REG['nppes-public-health'], {'name': 'DELAWARE PUBLIC HEALTH DISTRICT', 'state': 'OH', 'zip': '43015',
                                                     'phone': '(740) 368-1700', 'record': '1'}, GEO, '2026-11-23')
        kept = lh.dedupe([b, a])
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]['source_id'], 'oh-odh-lhd')
        self.assertIn('nppes-public-health', kept[0]['note'])

    def test_ids_are_stable(self):
        d = {'name': 'Clinic', 'state': 'OH', 'zip': '43215', 'phone': '614-555-0199', 'record': 'A1'}
        d2 = dict(d, phone='614-645-7417')
        self.assertEqual(lh.normalize(REG['oh-odh-lhd'], d2, GEO, '2026-11-23')['id'],
                         lh.normalize(REG['oh-odh-lhd'], d2, GEO, '2026-12-23')['id'])

    def test_index_tops_up_from_neighbours(self):
        r = lh.normalize(REG['ndbn-members'], {'name': 'Columbus Diaper Bank', 'state': 'OH', 'city': 'Columbus',
                                               'website': 'https://columbusdiaperbank.org'}, GEO, '2026-11-23')
        idx = lh.build_index([r], GEO)
        self.assertEqual(idx['39049'], [[r['id'], 0]])     # in Franklin County
        self.assertEqual(idx['39041'][0][0], r['id'])      # Delaware County: the nearest one, outside it
        self.assertGreater(idx['39041'][0][1], 0)


class CountyRow(unittest.TestCase):
    """The row on a county page, fed a single made-up listing."""

    def setUp(self):
        import ymt_build
        self.yb = ymt_build
        self.saved = getattr(ymt_build.local_help, 'cache', 'unset')
        r = lh.normalize(REG['ndbn-members'], {'name': 'Columbus Diaper Bank', 'state': 'OH', 'city': 'Columbus',
                                               'website': 'https://columbusdiaperbank.org'}, GEO, '2026-11-23')
        r = {k: str(v) for k, v in r.items()}
        self.row = r
        ymt_build.local_help.cache = {'rows': {r['id']: r}, 'index': {'39049': [[r['id'], 0]], '39041': [[r['id'], 22]]},
                                      'sources': REG, 'links': {'https://columbusdiaperbank.org': 'ok'}}

    def tearDown(self):
        if self.saved == 'unset':
            del self.yb.local_help.cache
        else:
            self.yb.local_help.cache = self.saved

    def test_the_row_shows_the_listing_with_its_source(self):
        html = self.yb.mh_row('OH', '39049', {'n': 'Franklin County'}, 'Ohio', 'oh', '../../')
        self.assertIn('id="county-moms"', html)
        self.assertIn('Columbus Diaper Bank', html)
        self.assertIn('https://columbusdiaperbank.org', html)
        self.assertIn('National Diaper Bank Network', html)
        self.assertIn('not confirmed by phone', html)
        self.assertIn('Diapers in or near Franklin County', html)

    def test_a_neighbouring_county_says_how_far(self):
        html = self.yb.mh_row('OH', '39041', {'n': 'Delaware County'}, 'Ohio', 'oh', '../../')
        self.assertIn('About 22 miles away', html)
        self.assertIn('Diapers near Delaware County', html)

    def test_a_listing_whose_only_website_did_not_load_waits(self):
        self.yb.local_help.cache['links'] = {'https://columbusdiaperbank.org': 'broken'}
        html = self.yb.mh_row('OH', '39049', {'n': 'Franklin County'}, 'Ohio', 'oh', '../../')
        self.assertNotIn('Columbus Diaper Bank', html)   # nothing left to do with it, so not shown until it loads
        self.assertIn('not found a local listing', html)

    def test_no_listings_yet_means_no_row(self):
        self.yb.local_help.cache = None
        self.assertIsNone(self.yb.mh_row('OH', '39049', {'n': 'Franklin County'}, 'Ohio', 'oh', '../../'))


if __name__ == '__main__':
    unittest.main()
