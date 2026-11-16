"""The script that builds ohio/assets/places.json, run against a few made-up rows."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import ohio_places  # noqa: E402


def row(zip_code, town, county, lat, lng, state='OH'):
    return '\t'.join(['US', zip_code, town, 'Ohio', state, county, '000', '', '', str(lat), str(lng), '4'])


class Places(unittest.TestCase):
    def build(self, rows, census, known):
        with tempfile.TemporaryDirectory() as tmp:
            geo, cen = Path(tmp) / 'US.txt', Path(tmp) / 'census.json'
            geo.write_text('\n'.join(rows) + '\n', encoding='utf-8')
            cen.write_text(json.dumps({'OH': {'counties': {c + ' County': {'zip_codes': z} for c, z in census.items()}}}), encoding='utf-8')
            return ohio_places.build(geo, cen, '2024-04-12', known)

    ROWS = [
        row('43334', 'Marengo', 'Morrow', 40.39, -82.81),
        row('43338', 'Mount Gilead', 'Morrow', 40.54, -82.81),
        row('43240', 'Columbus', 'Franklin', 40.14, -82.98),      # GeoNames slip: the Census table says Delaware only
        row('43215', 'Columbus', 'Franklin', 39.97, -83.00),
        row('43216', 'Columbus', 'Franklin', 39.96, -83.00),      # a post office box ZIP code: no Census area, right county
        row('45202', 'Cincinnati', 'Hamilton', 39.11, -84.50),
        row('45275', 'Cincinnati', 'Brown', 39.16, -84.46),       # no Census area, wrong county: settled in FIXES
        row('40004', 'Bardstown', 'Nelson', 37.8, -85.4, state='KY'),
    ]
    CENSUS = {'Morrow': ['43334', '43338'], 'Delaware': ['43334', '43240'], 'Franklin': ['43215'], 'Hamilton': ['45202']}
    KNOWN = {'Morrow', 'Delaware', 'Franklin', 'Hamilton'}

    def test_counties_towns_and_the_counties_a_zip_code_reaches(self):
        data, corrected = self.build(self.ROWS, self.CENSUS, self.KNOWN)
        self.assertEqual(data['counties']['Morrow'], 'Marengo 43334|Mount Gilead 43338')
        self.assertEqual(data['counties']['Franklin'], 'Columbus 43215 43216')
        self.assertEqual(data['reaches'], {'43334': 'Delaware'}, 'only the other counties are listed, never the one the ZIP code is filed under')
        self.assertNotIn('Bardstown', json.dumps(data), 'other states are left out')
        self.assertIn('GeoNames', data['about'])
        self.assertIn('2024-04-12', data['about'])
        # Where the two sources disagree outright, the Census county wins, and the change is reported.
        self.assertEqual(data['counties']['Delaware'], 'Columbus 43240')
        self.assertIn(('43240', 'Columbus', 'Franklin', 'Delaware'), corrected)
        # A ZIP code with no Census area takes the county a person settled.
        self.assertEqual(data['counties']['Hamilton'], 'Cincinnati 45202 45275')
        self.assertIn(('45275', 'Cincinnati', 'Brown', 'Hamilton'), corrected)

    def test_a_zip_code_out_of_place_stops_the_build_until_someone_settles_it(self):
        # Its four nearest neighbors with a Census area are all in Hamilton County, and it says Morrow.
        near = [row('4520' + n, 'Cincinnati', 'Hamilton', 39.10 + int(n) / 100, -84.50) for n in '345']
        census = dict(self.CENSUS, Hamilton=['45202', '45203', '45204', '45205'])
        self.build(self.ROWS + near, census, self.KNOWN)
        with self.assertRaisesRegex(AssertionError, 'Settle these in FIXES'):
            self.build(self.ROWS + near + [row('45299', 'Cincinnati', 'Morrow', 39.12, -84.51)], census, self.KNOWN)

    def test_every_county_must_have_a_place(self):
        with self.assertRaises(AssertionError):
            self.build(self.ROWS, self.CENSUS, self.KNOWN | {'Vinton'})

    def test_the_file_is_written_one_county_to_a_line_and_reads_back_the_same(self):
        data, _ = self.build(self.ROWS, self.CENSUS, self.KNOWN)
        text = ohio_places.dump(data)
        self.assertEqual(json.loads(text), data)
        self.assertEqual(sum(1 for line in text.split('\n') if line.startswith('  "')), len(data['counties']))
        committed = (ROOT / 'ohio' / 'assets' / 'places.json').read_text(encoding='utf-8')
        self.assertEqual(ohio_places.dump(json.loads(committed)), committed, 'the committed file is in the form the script writes')


if __name__ == '__main__':
    unittest.main()
