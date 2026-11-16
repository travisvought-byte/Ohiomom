#!/usr/bin/env python3
"""Build ohio/assets/places.json: Ohio ZIP codes and post office towns, by county.

The "All resources" page uses it so a mother can type her town or ZIP code and be shown her county.
Run it by hand when the list needs refreshing. The two source files are not kept in this repository:

    python3 scripts/ohio_places.py US.txt state_county_zip.json 2024-04-12

US.txt                 GeoNames postal codes for the United States (Creative Commons Attribution 4.0),
                       https://download.geonames.org/export/zip/US.zip
state_county_zip.json  the U.S. Census Bureau's 2010 ZCTA to County Relationship File (public domain), as
                       packaged in the npm module us-zcta-counties
the date               the date of the GeoNames file, written into the "about" line

GeoNames gives each ZIP code one town name and one county. The Census table lists every county a ZIP
code area reaches into, which is how the page can say "this ZIP code also reaches into Delaware County".
Where GeoNames names a county the Census table does not list for that ZIP code at all, the Census
county is used. About one ZIP code in six (post office boxes, mostly) has no Census area to compare
with. Those are compared with their nearest neighbors instead, and the build stops if one sits in a
county none of its neighbors is in, until a person settles it in FIXES below.
With --check the file in the repository is compared and nothing is written.
"""
import csv
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'ohio' / 'assets' / 'places.json'
ABOUT = ('Ohio ZIP codes and post office towns by county, for the place box on the All resources page. '
         'Each county holds "Town ZIP ZIP" entries split by "|". "reaches" lists the other counties a ZIP code '
         'area reaches into. ZIP codes, town names and counties: GeoNames postal codes, CC BY 4.0, '
         'https://www.geonames.org/ (file dated {dated}). Other counties a ZIP code reaches: U.S. Census Bureau, '
         '2010 ZCTA to County Relationship File. Built by scripts/ohio_places.py. Do not edit by hand.')


# ZIP codes with no Census area where GeoNames names the wrong county, settled by a person.
FIXES = {
    '45275': 'Hamilton',  # a Cincinnati business ZIP code. GeoNames says Brown; its own coordinates are downtown.
}


def read_geonames(path):
    """{zip: (town, county, latitude, longitude)} for Ohio."""
    rows = {}
    with open(path, encoding='utf-8', newline='') as f:
        for r in csv.reader(f, delimiter='\t', quoting=csv.QUOTE_NONE):
            if len(r) >= 11 and r[0] == 'US' and r[4] == 'OH':
                assert r[1].isdigit() and len(r[1]) == 5 and r[1] not in rows, r[1]
                assert r[2] and '|' not in r[2] and not any(ch.isdigit() for ch in r[2]), r[2]
                rows[r[1]] = (r[2], r[5], float(r[9]), float(r[10]))
    return rows


def out_of_place(rows, reach):
    """ZIP codes with no Census area whose county is not the county of any of their four nearest neighbors."""
    backed = [z for z in rows if z in reach]

    def miles(a, b):
        return math.hypot((rows[a][2] - rows[b][2]) * 69, (rows[a][3] - rows[b][3]) * 53)
    odd = []
    for z in sorted(set(rows) - set(backed) - set(FIXES)):
        near = sorted(backed, key=lambda b: miles(z, b))[:4]
        if rows[z][1] not in set().union(*(reach[b] for b in near)):
            odd.append(f'{z} {rows[z][0]}: GeoNames says {rows[z][1]}; its neighbors are in {sorted(set().union(*(reach[b] for b in near)))}')
    return odd


def read_census(path):
    """{zip: {county, ...}} for Ohio: every county the ZIP code area reaches."""
    counties = json.loads(Path(path).read_text(encoding='utf-8'))['OH']['counties']
    reach = defaultdict(set)
    for county, entry in counties.items():
        for z in entry['zip_codes']:
            reach[z].add(county.removesuffix(' County'))
    return reach


def build(geonames, census, dated, known):
    rows, reach = read_geonames(geonames), read_census(census)
    odd = out_of_place(rows, reach)
    assert not odd, 'Settle these in FIXES:\n' + '\n'.join(odd)
    by_county = defaultdict(lambda: defaultdict(list))
    reaches, corrected = {}, []
    for z in sorted(rows):
        town, county = rows[z][:2]
        touched = reach.get(z, set())
        if z in FIXES:
            assert not touched and county != FIXES[z], f'{z}: this fix is no longer needed'
            corrected.append((z, town, county, FIXES[z]))
            county = FIXES[z]
        elif touched and county not in touched:
            assert len(touched) == 1, f'{z}: GeoNames says {county}, the Census table says {sorted(touched)}'
            corrected.append((z, town, county, next(iter(touched))))
            county = next(iter(touched))
        assert county in known, f'{z}: {county} is not one of the 88 counties'
        by_county[county][town].append(z)
        others = sorted(touched - {county})
        assert all(c in known for c in others), (z, others)
        if others:
            reaches[z] = '|'.join(others)
    assert set(by_county) == set(known), sorted(set(known) - set(by_county))
    counties = {c: '|'.join(f'{town} {" ".join(zips)}' for town, zips in sorted(by_county[c].items()))
                for c in sorted(by_county)}
    return {'about': ABOUT.format(dated=dated), 'counties': counties, 'reaches': reaches}, corrected


def dump(data):
    """One county to a line, so a change shows up as a small diff."""
    lines = ['{', ' "about": ' + json.dumps(data['about'], ensure_ascii=False) + ',', ' "counties": {']
    names = list(data['counties'])
    for c in names:
        lines.append(f'  {json.dumps(c)}: {json.dumps(data["counties"][c], ensure_ascii=False)}' + (',' if c != names[-1] else ''))
    lines += [' },', ' "reaches": ' + json.dumps(data['reaches'], separators=(',', ':')), '}']
    return '\n'.join(lines) + '\n'


def main():
    args = [a for a in sys.argv[1:] if a != '--check']
    if len(args) != 3:
        sys.exit(__doc__)
    known = json.loads((ROOT / 'ohio' / 'assets' / 'data.json').read_text(encoding='utf-8'))['counties']
    data, corrected = build(args[0], args[1], args[2], known)
    text = dump(data)
    assert json.loads(text) == data
    for z, town, was, now in corrected:
        print(f'{z} {town}: GeoNames says {was} County. Using {now} County.')
    zips = sum(len(re.findall(r'\b\d{5}\b', entry)) for entry in data['counties'].values())
    if '--check' in sys.argv:
        assert TARGET.read_text(encoding='utf-8') == text, 'ohio/assets/places.json is stale'
    else:
        TARGET.write_text(text, encoding='utf-8')
    print(f'{len(data["counties"])} counties, {zips} ZIP codes, {len(data["reaches"])} that reach a second county, {len(text)} bytes')


if __name__ == '__main__':
    main()
