#!/usr/bin/env python3
"""How much of the country has county-level help on the site. Reads only files that are in the repo.

    python3 scripts/coverage.py          print the report
    python3 scripts/coverage.py --json   the same numbers as JSON

Three levels, from broadest to deepest:
    state page        a page for the state, with its own offices (51 of 51)
    county page       a page for the county with listings from three federal directories (every county)
    local guide       a hand-checked page written for that county (ohio/counties/)
"Local listings" means at least one listing from a federal directory is inside the county itself, not just nearby.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load():
    counties = json.loads((ROOT / 'data' / 'ymt' / 'counties.json').read_text(encoding='utf-8'))
    shards = {}
    for c in counties:
        st = c['state']
        if st not in shards:
            shards[st] = json.loads((ROOT / 'assets' / 'us' / f'{st.lower()}.json').read_text(encoding='utf-8'))
    return counties, shards


def report():
    counties, shards = load()
    total_pop = sum(c['pop'] for c in counties)
    rows = []
    for c in counties:
        e = shards[c['state']]['c'][c['fips']]
        inside = {'health': bool(e.get('health')), 'head_start': bool(e.get('headStart')),
                  'hud': any(h[1] == 0 for h in e.get('hud', []))}
        near = {'health': inside['health'] or bool(e.get('healthNear')),
                'head_start': inside['head_start'] or bool(e.get('headStartNear')), 'hud': bool(e.get('hud'))}
        rows.append((c, inside, near, 'pg' in e))

    def share(pred):
        sel = [c for c, i, n, g in rows if pred(i, n, g)]
        return {'counties': len(sel), 'county_pct': round(100 * len(sel) / len(counties), 1),
                'people_pct': round(100 * sum(c['pop'] for c in sel) / total_pop, 1)}
    out = {
        'counties': len(counties), 'people': total_pop, 'states': len({c['state'] for c in counties}),
        'with_a_county_page': share(lambda i, n, g: True),
        'local_guide': share(lambda i, n, g: g),
        'health_center_in_county': share(lambda i, n, g: i['health']),
        'head_start_in_county': share(lambda i, n, g: i['head_start']),
        'housing_counselor_in_county': share(lambda i, n, g: i['hud']),
        'all_three_in_county': share(lambda i, n, g: i['health'] and i['head_start'] and i['hud']),
        'something_in_county': share(lambda i, n, g: i['health'] or i['head_start'] or i['hud']),
        'health_center_in_or_near': share(lambda i, n, g: n['health']),
        'head_start_in_or_near': share(lambda i, n, g: n['head_start']),
        'all_three_in_or_near': share(lambda i, n, g: n['health'] and n['head_start'] and n['hud']),
        'nothing_in_or_near': share(lambda i, n, g: not (n['health'] or n['head_start'] or n['hud'])),
    }
    return out


def main():
    r = report()
    if '--json' in sys.argv:
        print(json.dumps(r, indent=1))
        return
    print(f"{r['states']} places, {r['counties']:,} counties, {r['people']:,} people\n")
    names = [('with_a_county_page', 'County page (federal listings)'),
             ('local_guide', 'Hand-checked local guide'),
             ('health_center_in_county', 'Health center in the county'),
             ('head_start_in_county', 'Head Start in the county'),
             ('housing_counselor_in_county', 'Housing counselor in the county'),
             ('something_in_county', 'At least one of the three in the county'),
             ('all_three_in_county', 'All three in the county'),
             ('health_center_in_or_near', 'Health center in or within 60 miles'),
             ('head_start_in_or_near', 'Head Start in or within 60 miles'),
             ('all_three_in_or_near', 'All three in or near'),
             ('nothing_in_or_near', 'None of the three in or near')]
    print(f"{'':44}{'counties':>9}{'of counties':>13}{'of people':>11}")
    for key, label in names:
        s = r[key]
        print(f"{label:44}{s['counties']:>9,}{s['county_pct']:>12}%{s['people_pct']:>10}%")


if __name__ == '__main__':
    main()
