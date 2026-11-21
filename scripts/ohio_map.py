#!/usr/bin/env python3
"""Build the places on the OhioMom map (ohio/map.html) from data the site already has.

Every place comes from assets/us/oh.json, the federal county data that scripts/county_data.py refreshes each
month, and only from the rows that are in the county itself (zero miles away, or a housing office marked as in
the county):

    health      health centers (HRSA)
    start       Head Start and Early Head Start programs (Office of Head Start)
    housing     public housing agencies (HUD)
    counsel     HUD-approved housing counseling agencies

Nothing here has a street-level position. The repository has no latitude or longitude for any place, so the map
places each one at its county's label point in ohio/assets/map.json (the same shapes the old county map draws),
and says so on the page. Nothing is geocoded or guessed.

It writes two things:

    ohio/assets/map-places.json   what the map script (ohio/assets/ohio-map.js) shows, websites included
    ohio/map.html                 the same places as a plain list, county by county, between the
                                  <!--maplist--> markers, so the page works with no script at all. The list
                                  carries phone links but no web links, so the monthly Ohio link check
                                  (scripts/check_links.py) does not grow by a thousand addresses.

Events are not built here: the map script reads them from ohio/assets/data.json in the browser, upcoming only.

    python3 scripts/ohio_map.py           write both
    python3 scripts/ohio_map.py --check   fail if either is out of step with the data
"""
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / 'assets' / 'us' / 'oh.json'
SHAPES = ROOT / 'ohio' / 'assets' / 'map.json'
DATA = ROOT / 'ohio' / 'assets' / 'data.json'
OUT = ROOT / 'ohio' / 'assets' / 'map-places.json'
PAGE = ROOT / 'ohio' / 'map.html'
MARK = re.compile(r'<!--maplist-->.*?<!--/maplist-->', re.S)

KINDS = {
    'health': 'Health care',
    'start': 'Head Start',
    'housing': 'Public housing',
    'counsel': 'Housing counselor',
}
ORDER = list(KINDS)


def esc(value):
    return html.escape('' if value is None else str(value), quote=True)


def web(url):
    """Keep a website only when it is a plain https address."""
    url = (url or '').strip()
    return url if re.match(r'^https://[A-Za-z0-9.-]+(/[^\s"<>]*)?$', url) else ''


def build():
    """{'asof', 'kinds', 'counties': {name: fips}, 'places': [[kind, county, name, street, city, zip, phone, web, more]]}

    more is what the map script turns into a sentence: for health, [organization, 1 if open part of the year];
    for start, [program bits (1 Head Start, 2 Early Head Start, 4 migrant, 8 tribal), organization]; for housing,
    the programs (C both, S vouchers, P public housing); for counsel, the services (R renting, H homelessness,
    D mortgage trouble, B budgeting, P buying a home).
    """
    state = json.loads(STATE.read_text(encoding='utf-8'))
    shapes = json.loads(SHAPES.read_text(encoding='utf-8'))['c']
    counties, places, seen = {}, [], set()
    for fips, c in sorted(state['c'].items()):
        county = c['n'].removesuffix(' County')
        if county not in shapes:
            raise SystemExit(f'{county}: in oh.json but not in ohio/assets/map.json')
        counties[county] = fips

        def add(kind, key, name, street, city, zip_, phone, site, more):
            if (kind, key) in seen:
                return
            seen.add((kind, key))
            places.append([kind, county, name, street, city, zip_, phone, web(site), more])

        # [org, name, street, city, zip, phone, website, hours, seasonal, miles, state]
        for r in c.get('health', []):
            if r[9] == 0 and r[10] == 'OH':
                org = r[0] if r[0] and r[0].lower() != r[1].lower() else ''
                add('health', (r[1], r[2], r[3]), r[1], r[2], r[3], r[4], r[5], r[6], [org, 1 if r[8] else 0])
        # [name, org, street, city, zip, phone, kinds, miles, state]
        for r in c.get('headStart', []):
            if r[7] == 0 and r[8] == 'OH':
                add('start', (r[0], r[2], r[3]), r[0], r[2], r[3], r[4], r[5], '', [r[6], r[1] or ''])
        # pha: [code, miles, how]; ph[code]: [name, street, city, zip, phone, programs, homes, vouchers, state]
        for code, _miles, how in c.get('pha', []):
            a = state['ph'][code]
            if how == 'c' and a[8] == 'OH':
                add('housing', code, a[0], a[1], a[2], a[3], a[4], '', a[5])
        # hud: [id, miles]; hu[id]: [name, street, city, zip, phone, website, services, methods, langs, state]
        for hid, miles in c.get('hud', []):
            a = state['hu'][hid]
            if miles == 0 and a[9] == 'OH':
                add('counsel', hid, a[0], a[1], a[2], a[3], a[4], a[5], a[6])
    places.sort(key=lambda p: (p[1], ORDER.index(p[0]), p[2].lower(), p[4]))
    return {
        'about': 'Places on the OhioMom map, built by scripts/ohio_map.py from assets/us/oh.json. Each place sits at '
                 'its county\'s label point in map.json: there is no street-level position for any of them.',
        'asof': state['asof'],
        'kinds': KINDS,
        'counties': counties,
        'places': places,
    }


def pretty(iso):
    y, m, d = iso.split('-')
    months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October',
              'November', 'December']
    return f'{months[int(m) - 1]} {int(d)}, {y}'


def slug(county):
    return re.sub(r'[^a-z]+', '-', county.lower()).strip('-')


def tel(phone):
    digits = re.sub(r'\D', '', phone or '')
    return digits if len(digits) == 10 else ''


def plain_list(data, pages):
    """The no-script list: every county, its places, and where to read more."""
    by = {}
    for p in data['places']:
        by.setdefault(p[1], []).append(p)
    out = [f'<p class="small">{len(data["places"]):,} places in {len(data["counties"])} counties, from federal lists '
           f'as of <time datetime="{data["asof"]}">{pretty(data["asof"])}</time>. Not confirmed by phone, so call first.</p>']
    for county in sorted(data['counties']):
        rows = by.get(county, [])
        n = len(rows)
        out.append(f'<details class="mapcounty" id="list-{slug(county)}"><summary><h3>{esc(county)} County</h3>'
                   f'<span class="ncount">{n} {"place" if n == 1 else "places"}</span></summary>')
        if rows:
            out.append('<ul class="plainplaces">')
            for kind, _c, name, street, city, zip_, phone, _web, _more in rows:
                call = f'<a href="tel:{tel(phone)}">{esc(phone)}</a>' if tel(phone) else esc(phone)
                addr = ', '.join(x for x in (street, f'{city}, OH {zip_}'.strip()) if x)
                out.append(f'<li><strong>{esc(name)}</strong> <span class="kindtag">{esc(KINDS[kind])}</span><br>'
                           f'{esc(addr)}' + (f'<br>{call}' if call else '') + '</li>')
            out.append('</ul>')
        else:
            out.append('<p>None of these federal lists has an office inside this county. The county pages list the nearest ones.</p>')
        more = [f'<a href="../county.html#{data["counties"][county]}">Everything for {esc(county)} County</a>']
        if pages.get(county):
            more.insert(0, f'<a href="{esc(pages[county])}">OhioMom page for {esc(county)} County</a>')
        out.append('<p class="small">' + ' · '.join(more) + '</p></details>')
    return '<!--maplist-->' + ''.join(out) + '<!--/maplist-->'


def page_text(data, text):
    pages = {k: v[2] for k, v in json.loads(DATA.read_text(encoding='utf-8'))['counties'].items() if len(v) > 2}
    if len(MARK.findall(text)) != 1:
        raise SystemExit('ohio/map.html: expected one <!--maplist--> block')
    block = plain_list(data, pages)
    return MARK.sub(lambda _m: block, text)


def dumps(data):
    return json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n'


def main():
    check = '--check' in sys.argv
    data = build()
    page = PAGE.read_text(encoding='utf-8')
    want = {OUT: dumps(data), PAGE: page_text(data, page)}
    stale = [str(p.relative_to(ROOT)) for p, text in want.items() if not p.exists() or p.read_text(encoding='utf-8') != text]
    if check:
        if stale:
            raise SystemExit('Run python3 scripts/ohio_map.py\nOut of step: ' + ', '.join(stale))
        print(f'OhioMom map matches the data: {len(data["places"])} places')
        return
    for p, text in want.items():
        p.write_text(text, encoding='utf-8')
    print(f'Wrote the OhioMom map: {len(data["places"])} places in {len(data["counties"])} counties')


if __name__ == '__main__':
    main()
