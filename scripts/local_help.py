#!/usr/bin/env python3
"""Local help for moms and babies, mined from public sources into one table, county by county.

This is the data-mining pipeline behind the "Help for moms and babies" row of every county page. It works like the
federal layer in scripts/county_data.py, but for help that is about pregnancy, babies and new moms: WIC offices,
Healthy Start projects, local health departments, diaper banks, breastfeeding groups, postpartum support and home
visiting. Every row it writes names the source it came from and the date it was copied. Nothing is typed in by hand.

    python3 scripts/local_help.py --fetch SRC     download every active source in the registry into SRC (needs the internet)
    python3 scripts/local_help.py SRC             parse SRC, normalize, place in counties, dedupe; write the table and index
    python3 scripts/local_help.py --check         check the table (also run by scripts/ymt_validate.py)
    python3 scripts/local_help.py --coverage      write the coverage report: which counties and countries are thinnest

Files (all in data/ymt/local-help/):
    registry.json      every source: what it is, who publishes it, where to download it, how strong its evidence is,
                       how often to recheck it, and whether it is active, queued or blocked (and why)
    listings.csv       the normalized table, one row per place (schema in FIELDS below). Generated: do not hand-edit.
    county-index.json  {fips: [[listing id, miles], ...]}: miles 0 means in the county (or a county the listing says it
                       serves); otherwise the nearest listings of that kind within NEAR_MILES. Generated.
    coverage.md        the coverage report. Generated.

Evidence levels (the same idea as the cannabis directory's evidence standard):
    government     copied from a government agency's own published list (HRSA, a state health department)
    organization   copied from the network's own directory of its members or groups (a diaper bank network)
Every listing is "source-listed": it is in the source on the date shown and has not been confirmed by phone.

Running it cold: see the "Local help for moms" section of README.md. The monthly workflow
.github/workflows/local-help-refresh.yml runs --fetch, the build and every check, and opens a pull request.
"""
import argparse
import csv
import hashlib
import io
import json
import math
import re
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / 'data' / 'ymt' / 'local-help'
REGISTRY = DIR / 'registry.json'
LISTINGS = DIR / 'listings.csv'
INDEX = DIR / 'county-index.json'
COVERAGE = DIR / 'coverage.md'
US = ROOT / 'assets' / 'us'

FIELDS = ['id', 'need', 'name', 'org', 'street', 'city', 'state', 'zip', 'county_fips', 'serves_fips', 'latitude',
          'longitude', 'phone', 'website', 'source_id', 'source_url', 'source_record', 'evidence', 'status',
          'first_seen', 'checked_on', 'recheck_on', 'note']

# The needs, in the order the county row shows them. Labels are what a mom reads.
NEEDS = {
    'wic': ('WIC office', 'WIC offices'),
    'healthy-start': ('Healthy Start program', 'Healthy Start programs'),
    'home-visiting': ('home visiting program', 'home visiting programs'),
    'health-dept': ('health department', 'health departments'),
    'diapers': ('diaper bank', 'diaper banks'),
    'breastfeeding': ('breastfeeding group', 'breastfeeding groups'),
    'postpartum': ('postpartum support', 'postpartum support'),
}
EVIDENCE = {'government', 'organization'}
# How far a county's own listings are topped up from neighbours, in miles from the middle of the county.
NEAR_MILES = {'wic': 40, 'healthy-start': 0, 'home-visiting': 0, 'health-dept': 0, 'diapers': 60, 'breastfeeding': 40,
              'postpartum': 0}
NEAR_MAX = 3
GAZ_COUNTIES = ('https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2023_Gazetteer/2023_Gaz_counties_national.zip',
                '2023_Gaz_counties_national.txt')
GAZ_ZCTA = ('https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2023_Gazetteer/2023_Gaz_zcta_national.zip',
            '2023_Gaz_zcta_national.txt')
GAZ_PLACES = ('https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2023_Gazetteer/2023_Gaz_place_national.zip',
              '2023_Gaz_place_national.txt')
UA = 'YogaMomTalk-directory/1.0 (+https://www.yogamomtalk.com/about.html)'

# The same safety screen as the federal layer: never publish a shelter, crisis unit or confidential address.
SENSITIVE = re.compile(r"shelter|safe ?house|domestic violence|confidential|crisis (center|unit|nursery)|respite|"
                       r"residential|group home|recovery (house|home|residence)|detox", re.I)


# ---------------------------------------------------------------- small helpers

def today():
    return date.today().isoformat()


def stable_id(*parts):
    return 'mh-' + hashlib.sha256('|'.join(p.strip().casefold() for p in parts).encode()).hexdigest()[:12]


def clean(text):
    return ' '.join(str(text or '').replace(' ', ' ').split())


def phone10(raw):
    """'(614) 555-0100 ext 2' -> '614-555-0100'. Placeholders and 555 numbers become ''."""
    digits = re.sub(r'\D', '', str(raw or '').split('x')[0].split('ext')[0])
    if len(digits) == 11 and digits.startswith('1'):
        digits = digits[1:]
    if len(digits) != 10 or digits[0] in '01' or digits[3] in '01' or digits[3:6] == '555' or len(set(digits)) == 1:
        return ''
    return f'{digits[:3]}-{digits[3:6]}-{digits[6:]}'


def zip5(raw):
    m = re.match(r'\s*(\d{5})', str(raw or ''))
    return m.group(1) if m else ''


def clean_url(raw):
    u = clean(raw)
    if not u:
        return ''
    if not re.match(r'https?://', u, re.I):
        u = 'https://' + u.lstrip('/')
    u = re.sub(r'^http://', 'https://', u, flags=re.I)
    try:
        p = urllib.parse.urlsplit(u)
    except ValueError:
        return ''
    if not p.hostname or '.' not in p.hostname or re.search(r'[\s"\'<>]', u):
        return ''
    if any(h in p.hostname for h in ('facebook.com', 'instagram.com', 'example.com', 'bit.ly')):
        return ''
    return u


def title_case(text):
    """Only for names a source gives in capitals."""
    t = clean(text)
    if t and t.upper() == t and any(c.isalpha() for c in t):
        small = {'of', 'the', 'and', 'for', 'in', 'at', 'on', 'a', 'de', 'la'}
        keep = {'WIC', 'LLC', 'INC', 'USA', 'PO', 'NE', 'NW', 'SE', 'SW', 'II', 'III'}
        words = []
        for i, w in enumerate(t.split(' ')):
            if w in keep:
                words.append(w)
            elif i and w.lower() in small:
                words.append(w.lower())
            else:
                words.append(w[:1] + w[1:].lower())
        t = ' '.join(words)
    return t


def miles(a_lat, a_lon, b_lat, b_lon):
    r = 3958.8
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp, dl = p2 - p1, math.radians(b_lon - a_lon)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def zip_county():
    """ZIP code -> county FIPS, from the site's own assets/us/z<digit>.json (made from the Census relationship file)."""
    out = {}
    for p in sorted(US.glob('z[0-9].json')):
        out.update(json.loads(p.read_text(encoding='utf-8')))
    return out


def counties():
    return {c['fips']: c for c in json.loads((ROOT / 'data' / 'ymt' / 'counties.json').read_text(encoding='utf-8'))}


def county_names():
    """(state, normalized county name) -> fips, for sources that name the county."""
    out = {}
    for f, c in counties().items():
        out[(c['state'], norm_county(c['name']))] = f
    return out


def norm_county(name):
    n = re.sub(r"[^a-z]", '', clean(name).lower().replace('saint', 'st'))
    return re.sub(r'(cityandborough|censusarea|municipality|municipio|county|parish|borough|planningregion)$', '', n) or n


def load_registry():
    return json.loads(REGISTRY.read_text(encoding='utf-8'))


# ---------------------------------------------------------------- fetching (runs in GitHub Actions)

def http_get(url, data=None, headers=None, tries=3):
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers={'User-Agent': UA, **(headers or {})})
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001 - recorded, then retried
            last = e
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f'{url}: {last}')


def fetch_arcgis(url, params):
    """Every feature of an ArcGIS FeatureServer/MapServer layer, page by page. A layer that does not page is read in
    one request."""
    rows, offset = [], 0
    size = int(params.get('page', 1000))
    paging = True
    while True:
        q = {'where': params.get('where', '1=1'), 'outFields': params.get('outFields', '*'), 'f': 'json',
             'returnGeometry': 'true', 'outSR': '4326'}
        if paging:
            q.update(resultOffset=offset, resultRecordCount=size)
        doc = json.loads(http_get(url.rstrip('/') + '/query?' + urllib.parse.urlencode(q)))
        if doc.get('error'):
            if paging and offset == 0:
                paging = False
                continue
            raise RuntimeError(f'{url}: {doc["error"]}')
        feats = doc.get('features', [])
        for f in feats:
            a = dict(f.get('attributes') or {})
            g = f.get('geometry') or {}
            if 'x' in g and 'y' in g:
                a['_lon'], a['_lat'] = g['x'], g['y']
            rows.append(a)
        if not paging or not feats or (not doc.get('exceededTransferLimit') and len(feats) < size):
            break
        offset += len(feats)
    return json.dumps(rows).encode()


def fetch_nppes(params):
    """CMS's NPI Registry, one state at a time, 200 rows a page (the API allows skip up to 1,000)."""
    from us_geo import STATE_FIPS  # noqa: E402
    out = []
    for st in sorted(STATE_FIPS):
        for skip in range(0, 1001, 200):
            q = dict(params, version='2.1', state=st, limit=200, skip=skip)
            doc = json.loads(http_get('https://npiregistry.cms.hhs.gov/api/?' + urllib.parse.urlencode(q)))
            res = doc.get('results') or []
            out += res
            if len(res) < 200:
                break
            time.sleep(0.3)
    return json.dumps(out).encode()


def fetch_source(src, out):
    f = src['fetch']
    kind = f.get('kind', 'get')
    if kind == 'arcgis':
        body = fetch_arcgis(f['url'], f.get('params', {}))
    elif kind == 'nppes':
        body = fetch_nppes(f.get('params', {}))
    else:
        body = http_get(f['url'])
    if f.get('member'):
        with zipfile.ZipFile(io.BytesIO(body)) as z:
            body = z.read(f['member'])
    out.write_bytes(body)
    return len(body)


def fetch_all(src_dir, only=None):
    src_dir.mkdir(parents=True, exist_ok=True)
    reg = load_registry()
    log = {'fetched_on': today(), 'sources': {}}
    for url, member in (GAZ_COUNTIES, GAZ_ZCTA, GAZ_PLACES):
        p = src_dir / member
        if not p.exists():
            with zipfile.ZipFile(io.BytesIO(http_get(url))) as z:
                p.write_bytes(z.read(member))
    for s in reg['sources']:
        if s['status'] != 'active' or (only and s['id'] not in only):
            continue
        p = src_dir / f"{s['id']}.raw"
        try:
            n = fetch_source(s, p)
            log['sources'][s['id']] = {'ok': True, 'bytes': n}
            print(f"fetched {s['id']}: {n:,} bytes", file=sys.stderr)
        except Exception as e:  # noqa: BLE001 - one failed source must not stop the others
            log['sources'][s['id']] = {'ok': False, 'error': str(e)[:300]}
            print(f"FAILED {s['id']}: {e}", file=sys.stderr)
    (src_dir / 'fetch-log.json').write_text(json.dumps(log, indent=1))
    return log


# ---------------------------------------------------------------- parsers: raw source -> plain dicts
# A parser returns dicts with any of: name, org, street, city, state, zip, county, county_fips, serves_zips (list),
# serves_fips (list), lat, lon, phone, website, record (the source's own id for the row), note.

def parse(src, raw):
    return PARSERS[src['parser']](src, raw)


def _rows_json(text):
    doc = json.loads(text)
    rows = doc if isinstance(doc, list) else doc.get('features') or doc.get('data') or doc.get('rows') or doc.get('results') or []
    out = []
    for r in rows:
        if isinstance(r, dict) and ('attributes' in r or 'properties' in r):
            a = dict(r.get('attributes') or r.get('properties') or {})
            g = r.get('geometry') or {}
            if g.get('type') == 'Point':
                a['_lon'], a['_lat'] = g['coordinates'][:2]
            elif 'x' in g:
                a['_lon'], a['_lat'] = g['x'], g['y']
            out.append(a)
        else:
            out.append(r)
    return out


def _pick(row, *keys):
    for k in keys:
        if k in row and row[k] not in (None, ''):
            return row[k]
        for rk in row:
            if rk.lower() == k.lower() and row[rk] not in (None, ''):
                return row[rk]
    return ''


RAW_KEYS = {}   # the first raw row's column names per source, for the run report


def parse_generic(src, raw):
    """Any CSV, JSON list, ArcGIS or GeoJSON whose column names the registry maps in parser_options.columns. Constant
    values (a state for a one-state layer) go in parser_options.constants."""
    opts = src.get('parser_options', {})
    cols = opts.get('columns', {})
    text = raw.decode('utf-8-sig', 'replace')
    rows = _rows_json(text) if text.lstrip().startswith(('[', '{')) else list(csv.DictReader(io.StringIO(text)))
    flt = opts.get('filter')   # {"column": ..., "match": regex}
    if rows and isinstance(rows[0], dict):
        RAW_KEYS[src['id']] = sorted(rows[0])[:60]
    out = []
    for r in rows:
        if flt and not re.search(flt['match'], str(_pick(r, flt['column'])), re.I):
            continue
        d = {k: _pick(r, *(v if isinstance(v, list) else [v])) for k, v in cols.items()}
        d.setdefault('lat', r.get('_lat', ''))
        d.setdefault('lon', r.get('_lon', ''))
        if not d.get('lat'):
            d['lat'], d['lon'] = r.get('_lat', ''), r.get('_lon', '')
        d.update(opts.get('constants', {}))
        out.append(d)
    return out


def parse_pat(src, raw):
    """Parents as Teachers' affiliate list (its store locator's own data). Each affiliate names the ZIP codes it serves.
    Staff emails are left out; affiliates still waiting to be approved (category 20) are left out."""
    out = []
    for r in json.loads(raw):
        if str(r.get('country_code') or 'US').upper() not in ('US', 'USA', ''):
            continue
        cats = {c.strip() for c in str(r.get('categories') or '').split(',')}
        if cats and cats <= {'20'}:
            continue
        zips = re.findall(r'\b\d{5}\b', str(r.get('description_2') or ''))
        out.append({'name': r.get('title'), 'street': r.get('street'), 'city': r.get('city'), 'state': r.get('state'),
                    'zip': r.get('postal_code'), 'lat': r.get('lat'), 'lon': r.get('lng'), 'phone': r.get('phone'),
                    'website': r.get('website'), 'record': r.get('id'), 'serves_zips': zips,
                    'org': 'Parents as Teachers affiliate'})
    return out


STATE_NAMES = None


def _state_abbr(name):
    global STATE_NAMES
    if STATE_NAMES is None:
        states = json.loads((ROOT / 'data' / 'ymt' / 'states.json').read_text(encoding='utf-8'))['states']
        STATE_NAMES = {s['name'].lower(): s['abbr'] for s in states}
        STATE_NAMES.update({s['abbr'].lower(): s['abbr'] for s in states})
        STATE_NAMES['washington dc'] = STATE_NAMES['washington, d.c.'] = STATE_NAMES['d.c.'] = 'DC'
    return STATE_NAMES.get(clean(re.sub(r'<[^>]+>', '', name)).lower().rstrip(':'), '')


def parse_ndbn(src, raw):
    """The National Diaper Bank Network's member page (WordPress JSON). The page is a list per state:
    <h4>State</h4> then <li>City – <a href="...">Name</a></li>. It gives no street or phone, so each member is placed
    by its city and shown with its website."""
    import html as htmllib
    doc = json.loads(raw)
    body = doc.get('content', {}).get('rendered', '') if isinstance(doc, dict) else ''
    out, st = [], ''
    for m in re.finditer(r'<h[2-6][^>]*>(.*?)</h[2-6]>|<li[^>]*>(.*?)</li>', body, re.S | re.I):
        if m.group(1) is not None:
            st = _state_abbr(htmllib.unescape(m.group(1))) or st
            continue
        li = htmllib.unescape(m.group(2))
        a = re.search(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', li, re.S | re.I)
        text = clean(re.sub(r'<[^>]+>', ' ', li))
        city = clean(re.split(r'\s[–—-]\s', text, maxsplit=1)[0]) if re.search(r'\s[–—-]\s', text) else ''
        name = clean(re.sub(r'<[^>]+>', '', a.group(2))) if a else clean(re.split(r'\s[–—-]\s', text, maxsplit=1)[-1])
        if st and name:
            out.append({'name': name, 'city': city, 'state': st, 'website': a.group(1) if a else '',
                        'record': f'{st}|{city}|{name}', 'org': 'Member of the National Diaper Bank Network'})
    return out


def parse_lll(src, raw):
    """La Leche League USA's group map. Only the group name, where it meets and its page are used: the descriptions
    hold volunteer leaders' own phone numbers and emails, which are not published here."""
    out = []
    for r in json.loads(raw):
        if str(r.get('map_id')) != str(src.get('parser_options', {}).get('map_id', '3')):
            continue
        addr = clean(r.get('address'))
        m = re.search(r'(?:^|,)\s*([^,]+?),\s*([A-Z]{2})\s*(\d{5})?(?:,\s*(USA|United States))?\s*$', addr)
        out.append({'name': 'La Leche League: ' + clean(r.get('title')), 'street': '', 'city': m.group(1) if m else '',
                    'state': m.group(2) if m else '', 'zip': (m.group(3) or '') if m else '', 'lat': r.get('lat'),
                    'lon': r.get('lng'), 'website': r.get('link') or src.get('default_website', ''), 'record': r.get('id'),
                    'org': 'La Leche League USA', 'note': addr})
    return out


def parse_nppes(src, raw):
    """CMS's NPI Registry: organizations whose primary type is a state or local public health clinic or center."""
    out = []
    for r in json.loads(raw):
        tax = [t for t in r.get('taxonomies', []) if t.get('primary')]
        if not tax or tax[0].get('code') != src.get('parser_options', {}).get('taxonomy', '261QP0905X'):
            continue
        basic = r.get('basic', {})
        name = basic.get('organization_name') or ''
        keep = src.get('parser_options', {}).get('name_pattern')
        if keep and not re.search(keep, name, re.I):
            continue   # the type is self-chosen: state agencies, prison health contractors and tribal offices pick it too
        loc = next((a for a in r.get('addresses', []) if a.get('address_purpose') == 'LOCATION'), None)
        if not loc or loc.get('country_code', 'US') != 'US':
            continue
        out.append({'name': name, 'street': loc.get('address_1'), 'city': loc.get('city'), 'state': loc.get('state'),
                    'zip': loc.get('postal_code'), 'phone': loc.get('telephone_number'), 'record': r.get('number'),
                    'org': 'Public health department or clinic'})
    return out


PARSERS = {'generic': parse_generic, 'pat': parse_pat, 'ndbn': parse_ndbn, 'lll': parse_lll, 'nppes': parse_nppes}


# ---------------------------------------------------------------- placing listings in counties

class Geo:
    """Everything needed to put a listing in a county: ZIP -> county (the site's own files), county and ZIP and town
    centroids (Census gazetteer files fetched with the sources)."""

    def __init__(self, src_dir):
        self.zips = zip_county()
        self.names = county_names()
        self.cents, self.zc, self.places = {}, {}, {}
        for fname, store, key in ((GAZ_COUNTIES[1], self.cents, 'GEOID'), (GAZ_ZCTA[1], self.zc, 'GEOID')):
            p = src_dir / fname
            if p.exists():
                for r in csv.DictReader(io.StringIO(p.read_text(encoding='utf-8', errors='replace')), delimiter='\t'):
                    r = {k.strip(): v for k, v in r.items()}
                    store[r[key].zfill(5)] = (float(r['INTPTLAT']), float(r['INTPTLONG']))
        p = src_dir / GAZ_PLACES[1]
        if p.exists():
            for r in csv.DictReader(io.StringIO(p.read_text(encoding='utf-8', errors='replace')), delimiter='\t'):
                r = {k.strip(): v for k, v in r.items()}
                nm = re.sub(r'\s+(city|town|village|borough|CDP|municipality|city and borough|urban county)$', '', r['NAME'], flags=re.I)
                k = (r['USPS'], nm.lower())
                if k not in self.places:   # a city before a CDP of the same name: the file lists both
                    self.places[k] = (float(r['INTPTLAT']), float(r['INTPTLONG']))
        self._zc_by_state = None

    def county_at(self, lat, lon, st):
        """The county of the nearest ZIP code centre in the same state (good to a mile or two in towns)."""
        from us_geo import STATE_FIPS  # noqa: E402
        if self._zc_by_state is None:
            self._zc_by_state = defaultdict(list)
            for z, (a, b) in self.zc.items():
                f = self.zips.get(z)
                if f:
                    self._zc_by_state[f[:2]].append((a, b, f))
        best = min(((miles(lat, lon, a, b), f) for a, b, f in self._zc_by_state.get(STATE_FIPS.get(st, ''), [])), default=None)
        return best[1] if best and best[0] < 25 else ''

    def town(self, city, st):
        c = clean(city).lower().replace('saint ', 'st. ').replace('st ', 'st. ')
        return self.places.get((st, clean(city).lower())) or self.places.get((st, c))


def normalize(src, d, geo, checked):
    need = src['need']
    st = clean(d.get('state')).upper()[:2]
    if len(clean(d.get('state'))) > 2:
        st = _state_abbr(d.get('state')) or st
    z = zip5(d.get('zip'))
    lat, lon = d.get('lat'), d.get('lon')
    try:
        lat, lon = (float(lat), float(lon)) if lat not in (None, '') and lon not in (None, '') else (None, None)
        if lat is not None and not (17 < lat < 72 and -180 < lon < -64):
            lat, lon = None, None
    except (TypeError, ValueError):
        lat, lon = None, None
    if lat is None and d.get('city') and st:
        t = geo.town(d['city'], st)
        if t:
            lat, lon = t
    fips = clean(d.get('county_fips')).zfill(5) if d.get('county_fips') else ''
    if not fips and z and z in geo.zips and (not st or _same_state(geo.zips[z], st)):
        fips = geo.zips[z]
    if not fips and st and d.get('county'):
        fips = geo.names.get((st, norm_county(d['county'])), '')
    if not fips and lat is not None and st:
        fips = geo.county_at(lat, lon, st)
    if fips and not st:
        from us_geo import FIPS_STATE  # noqa: E402
        st = FIPS_STATE.get(fips[:2], '')
    name = title_case(d.get('name'))
    if not name or not st:
        return None
    if SENSITIVE.search(name + ' ' + clean(d.get('street'))):
        return None
    serves = {clean(x).zfill(5) for x in (d.get('serves_fips') or []) if clean(x)}
    serves |= {geo.zips[x] for x in (d.get('serves_zips') or []) if x in geo.zips and _same_state(geo.zips[x], st)}
    serves.discard(fips)
    row = {
        'need': need, 'name': name, 'org': clean(d.get('org')), 'street': title_case(d.get('street')),
        'city': title_case(d.get('city')), 'state': st, 'zip': z, 'county_fips': fips, 'serves_fips': ';'.join(sorted(serves)),
        'latitude': round(lat, 5) if lat is not None else '', 'longitude': round(lon, 5) if lon is not None else '',
        'phone': phone10(d.get('phone')), 'website': clean_url(d.get('website')),
        'source_id': src['id'], 'source_url': src.get('cite_url') or src['homepage'],
        'source_record': clean(d.get('record')), 'evidence': src['evidence'], 'status': 'source-listed',
        'checked_on': checked, 'recheck_on': (date.fromisoformat(checked) + timedelta(days=src['recheck_days'])).isoformat(),
        'note': clean(d.get('note')) if src.get('keep_note') else '',
    }
    if not (row['phone'] or row['website']):
        return None   # nothing a mom can do with it
    if not (row['county_fips'] or row['serves_fips']):
        return None   # cannot be placed on a county page
    row['id'] = stable_id(need, src['id'], row['source_record'] or f"{name}|{z}|{row['street']}|{row['city']}")
    return row


def _same_state(fips, st):
    from us_geo import STATE_FIPS  # noqa: E402
    return fips[:2] == STATE_FIPS.get(st)


def dedupe(rows, priority=None):
    """One row per place. Two rows of the same need are the same place when their names match after tidying and they
    share a ZIP code or town, or they share a phone number. The row from the stronger source is kept (government before
    organization, then the lower registry "priority": a state's own list before a national catch-all), and the other
    source is noted on it."""
    rank = {'government': 0, 'organization': 1}
    if priority is None:
        priority = {s['id']: s.get('priority', 1) for s in load_registry()['sources']}

    def key_name(n):
        return re.sub(r'[^a-z0-9]', '', re.sub(r'\b(inc|the|of|program|office|clinic|county|department|dept)\b', '', n.lower()))
    rows = sorted(rows, key=lambda r: (rank[r['evidence']], priority.get(r['source_id'], 1), r['source_id'], r['id']))
    kept, seen = [], {}
    for r in rows:
        keys = {(r['need'], key_name(r['name']), r['zip'] or r['city'].lower())}
        if r['phone']:
            keys.add((r['need'], 'tel', r['phone']))
        hit = next((seen[k] for k in keys if k in seen), None)
        if hit is not None:
            if r['source_id'] != hit['source_id'] and f"Also listed by {r['source_id']}" not in hit['note']:
                hit['note'] = clean(f"{hit['note']} Also listed by {r['source_id']}.")
            continue
        kept.append(r)
        for k in keys:
            seen[k] = r
    return kept


def build_index(rows, geo):
    """{fips: [[id, miles], ...]}. The county's own listings and those that say they serve it (miles 0), then, for a
    need with none of those, the nearest few within NEAR_MILES of the middle of the county."""
    index = defaultdict(list)
    where, need_of = {}, {}
    for r in rows:
        need_of[r['id']] = r['need']
        if r['latitude'] != '' and r['longitude'] != '':
            where[r['id']] = (float(r['latitude']), float(r['longitude']))
        elif r['zip'] in geo.zc:
            where[r['id']] = geo.zc[r['zip']]
        for f in {r['county_fips'], *r['serves_fips'].split(';')} - {''}:
            index[f].append([r['id'], 0])
    by_need = defaultdict(list)
    for r in rows:
        if r['id'] in where:
            by_need[r['need']].append((r['id'], where[r['id']]))
    for f, (clat, clon) in geo.cents.items():
        have = {i for i, _m in index.get(f, [])}
        needs_here = {need_of[i] for i in have}
        for need, limit in NEAR_MILES.items():
            if not limit or need in needs_here:
                continue
            cand = sorted((round(miles(clat, clon, lat, lon)), i) for i, (lat, lon) in by_need.get(need, []))
            for m, i in cand[:NEAR_MAX]:
                if m <= limit:
                    index[f].append([i, max(m, 1)])
    cs = counties()
    return {f: v for f, v in sorted(index.items()) if f in cs}


def read_listings():
    if not LISTINGS.exists():
        return []
    with LISTINGS.open(encoding='utf-8', newline='') as fh:
        return list(csv.DictReader(fh))


def write_listings(rows):
    DIR.mkdir(parents=True, exist_ok=True)
    with LISTINGS.open('w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator='\n')
        w.writeheader()
        for r in sorted(rows, key=lambda r: (r['state'], r['county_fips'], r['need'], r['name'], r['id'])):
            w.writerow({k: r.get(k, '') for k in FIELDS})


def build(src_dir):
    reg = load_registry()
    log = json.loads((src_dir / 'fetch-log.json').read_text()) if (src_dir / 'fetch-log.json').exists() else {}
    checked = log.get('fetched_on', today())
    old = {r['id']: r for r in read_listings()}
    geo = Geo(src_dir)
    rows, report = [], {}
    for s in reg['sources']:
        if s['status'] != 'active':
            continue
        p = src_dir / f"{s['id']}.raw"
        if not p.exists() or not log.get('sources', {}).get(s['id'], {}).get('ok', True):
            # A source that failed today keeps its rows from the last run, with their old dates, so one outage does
            # not empty the pages. Their recheck date shows they are due.
            kept = [r for r in old.values() if r['source_id'] == s['id']]
            rows += kept
            report[s['id']] = f'not fetched; kept {len(kept)} rows from the last run'
            continue
        try:
            parsed = parse(s, p.read_bytes())
        except Exception as e:  # noqa: BLE001 - a changed source format is reported, and its old rows kept
            kept = [r for r in old.values() if r['source_id'] == s['id']]
            rows += kept
            report[s['id']] = f'could not be read ({e}); kept {len(kept)} rows from the last run'
            continue
        made = [normalize(s, d, geo, checked) for d in parsed]
        good = [r for r in made if r]
        report[s['id']] = f'{len(made)} in source, {len(good)} usable'
        if s['id'] in RAW_KEYS:
            report[s['id'] + ' columns'] = ', '.join(map(str, RAW_KEYS[s['id']]))
        rows += good
    rows = dedupe(rows)
    for r in rows:
        r['first_seen'] = old.get(r['id'], {}).get('first_seen') or r['checked_on']
    write_listings(rows)
    INDEX.write_text(json.dumps(build_index(rows, geo), separators=(',', ':'), sort_keys=True) + '\n', encoding='utf-8')
    (DIR / 'last-run.json').write_text(json.dumps({'checked_on': checked, 'sources': report,
                                                   'fetch': log.get('sources', {})}, indent=1, sort_keys=True) + '\n')
    for k, v in report.items():
        print(f'{k}: {v}', file=sys.stderr)
    print(f'{len(rows)} listings after removing duplicates', file=sys.stderr)
    return rows


# ---------------------------------------------------------------- checks and coverage

def check():
    errors = []
    reg = load_registry()
    ids = [s['id'] for s in reg['sources']]
    if len(set(ids)) != len(ids):
        errors.append('registry: duplicate source id')
    for s in reg['sources']:
        for k in ('id', 'need', 'name', 'publisher', 'homepage', 'evidence', 'status', 'recheck_days', 'fetch'):
            if s.get(k) in (None, ''):
                errors.append(f"registry {s.get('id')}: missing {k}")
        if s.get('need') not in NEEDS and s.get('scope') != 'country':
            errors.append(f"registry {s['id']}: unknown need {s.get('need')}")
        if s.get('evidence') not in EVIDENCE:
            errors.append(f"registry {s['id']}: evidence must be one of {sorted(EVIDENCE)}")
        if s.get('status') not in ('active', 'queued', 'blocked'):
            errors.append(f"registry {s['id']}: status must be active, queued or blocked")
        if s.get('status') != 'active' and not s.get('why'):
            errors.append(f"registry {s['id']}: a {s.get('status')} source needs a why")
        if s.get('status') == 'active' and s.get('parser') not in PARSERS:
            errors.append(f"registry {s['id']}: unknown parser {s.get('parser')}")
    known = {s['id']: s for s in reg['sources']}
    cs = counties()
    seen = set()
    rows = read_listings()
    for r in rows:
        rid = r.get('id', '?')
        if rid in seen:
            errors.append(f'{rid}: duplicate id')
        seen.add(rid)
        if r['need'] not in NEEDS:
            errors.append(f'{rid}: unknown need {r["need"]}')
        if r['source_id'] not in known:
            errors.append(f'{rid}: source {r["source_id"]} is not in the registry')
        if not r['source_url'].startswith('https://'):
            errors.append(f'{rid}: source_url must be https')
        if r['website'] and not r['website'].startswith('https://'):
            errors.append(f'{rid}: website must be https')
        if r['phone'] and not re.fullmatch(r'\d{3}-\d{3}-\d{4}', r['phone']):
            errors.append(f'{rid}: bad phone {r["phone"]}')
        if not (r['phone'] or r['website']):
            errors.append(f'{rid}: needs a phone or a website')
        if r['county_fips'] and r['county_fips'] not in cs:
            errors.append(f'{rid}: unknown county {r["county_fips"]}')
        for d in ('checked_on', 'recheck_on', 'first_seen'):
            try:
                date.fromisoformat(r[d])
            except ValueError:
                errors.append(f'{rid}: bad {d} {r[d]!r}')
        if r['evidence'] not in EVIDENCE or r['status'] != 'source-listed':
            errors.append(f'{rid}: bad evidence or status')
        if SENSITIVE.search(r['name'] + ' ' + r['street']):
            errors.append(f'{rid}: name or street looks like a shelter or confidential site')
    if INDEX.exists():
        idx = json.loads(INDEX.read_text(encoding='utf-8'))
        for f, refs in idx.items():
            if f not in cs:
                errors.append(f'county-index: unknown county {f}')
            for i, _m in refs:
                if i not in seen:
                    errors.append(f'county-index {f}: unknown listing {i}')
    return errors


def coverage():
    """Which counties have no mom-specific help yet, biggest first, and which countries are thinnest."""
    cs = counties()
    idx = json.loads(INDEX.read_text(encoding='utf-8')) if INDEX.exists() else {}
    rows = {r['id']: r for r in read_listings()}
    reg = load_registry()
    pop = sum(c['pop'] for c in cs.values())
    lines = ['# Local help for moms: coverage', '',
             f'Generated by `python3 scripts/local_help.py --coverage` from `listings.csv` ({len(rows):,} listings).', '']
    by_need = Counter(r['need'] for r in rows.values())
    lines += ['## Listings by need', '', '| Need | Listings | Counties with one in the county | People in those counties |',
              '| --- | ---: | ---: | ---: |']
    for need, (one, many) in NEEDS.items():
        inside = {f for f, refs in idx.items() if any(m == 0 and rows.get(i, {}).get('need') == need for i, m in refs)}
        ppl = sum(cs[f]['pop'] for f in inside if f in cs)
        lines.append(f'| {many[0].upper() + many[1:]} | {by_need[need]:,} | {len(inside):,} of {len(cs):,} | '
                     f'{100 * ppl / pop:.1f}% |')
    some = {f for f, refs in idx.items() if any(m == 0 for _i, m in refs)}
    lines += ['', f'{len(some):,} of {len(cs):,} counties ({100 * sum(cs[f]["pop"] for f in some if f in cs) / pop:.1f}% of people) '
              'have at least one mom-specific listing in the county.', '']
    thin = sorted((c for f, c in cs.items() if f not in some), key=lambda c: -c['pop'])
    lines += ['## Thinnest counties, most people first (the next batch)', '',
              'Counties with no mom-specific listing in the county yet. Work down this list.', '',
              '| County | State | People |', '| --- | --- | ---: |']
    lines += [f"| {c['name']} | {c['state']} | {c['pop']:,} |" for c in thin[:60]]
    lines += ['', f'{len(thin):,} counties in all are still waiting.', '']
    world = json.loads((ROOT / 'data' / 'ymt' / 'world.json').read_text(encoding='utf-8'))
    secs = [s['id'] for s in json.loads((ROOT / 'data' / 'ymt' / 'resources.json').read_text(encoding='utf-8'))['sections']]
    rowsc = []
    for c in world['countries']:
        n = Counter(x['section'] for x in c.get('resources', []))
        empty = [s for s in secs if s not in ('christmas',) and not n.get(s)]
        rowsc.append((len(c.get('resources', [])), len(empty), c['name'], empty))
    rowsc.sort(key=lambda x: (x[0], -x[1], x[2]))
    lines += ['## Thinnest countries (the next batch outside the U.S.)', '',
              '| Country | Listings | Needs with nothing yet |', '| --- | ---: | --- |']
    lines += [f'| {name} | {n} | {", ".join(e)} |' for n, _k, name, e in rowsc[:40]]
    lines += ['', '## Sources', '', '| Source | Need | Status | Why |', '| --- | --- | --- | --- |']
    lines += [f"| [{s['name']}]({s['homepage']}) | {s['need']} | {s['status']} | {s.get('why', '')} |" for s in reg['sources']]
    COVERAGE.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return '\n'.join(lines)


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('src', nargs='?')
    ap.add_argument('--fetch', action='store_true')
    ap.add_argument('--only', nargs='*')
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--coverage', action='store_true')
    ap.add_argument('--sample', action='store_true', help='print a few rows of each source, for the run log')
    a = ap.parse_args()
    if a.check:
        errs = check()
        for e in errs:
            print(e)
        sys.exit(1 if errs else 0)
    if a.sample:
        by = defaultdict(list)
        for r in read_listings():
            by[r['source_id']].append(r)
        for sid, rs in sorted(by.items()):
            print(f'== {sid}: {len(rs)} rows')
            for r in rs[:4]:
                print('   ', {k: r[k] for k in ('name', 'city', 'state', 'zip', 'county_fips', 'serves_fips', 'phone', 'website') if r[k]})
        return
    if a.coverage:
        print(coverage())
        return
    if not a.src:
        ap.error('SRC is required')
    src = Path(a.src)
    if a.fetch:
        fetch_all(src, a.only)
        return
    build(src)
    coverage()


if __name__ == '__main__':
    main()
