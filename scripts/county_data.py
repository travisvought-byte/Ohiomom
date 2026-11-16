#!/usr/bin/env python3
"""Build the county layer from federal downloads.

Every county and county-equivalent in the 50 states and D.C. (3,144 of them) gets local listings from three
public federal directories, with no hand editing:

    HRSA Health Center Program sites       low-cost care, whether or not you have insurance
    Head Start / Early Head Start          free early learning for families who qualify
    HUD-approved housing counseling        rent, homelessness, mortgage trouble and budgeting

    python3 scripts/county_data.py --fetch SRC    download the raw files into SRC (about 25 MB)
    python3 scripts/county_data.py SRC            build data/ymt/counties.json and assets/us/*.json from SRC
    python3 scripts/county_data.py SRC --urls     print every website address the build would link, one per line

The raw files are not kept in the repo. SRC holds exactly the files named in SOURCES, plus hud/XX.json per state.
Website buttons appear only for addresses data/county-links.json says loaded (scripts/county_links.py makes it).
Connecticut is listed by its nine planning regions, the county-equivalents the Census Bureau has used since 2022.

Shape of assets/us/<st>.json (short names keep 3,144 counties under 5 MB):
    c[fips] = {n: name, p: population, pg: hand-built page, health: [...], healthNear: [...],
               headStart: [...], headStartNear: [...], hud: [[agency id, miles (0 = in the county)], ...]}
    health row     [org, name, street, city, zip, phone, website, hours a week, seasonal 0/1, miles, state]
    headStart row  [name, org, street, city, zip, phone, kinds (1 Head Start, 2 Early, 4 migrant, 8 tribal), miles, state]
    hu[agency id]  [name, street, city, zip, phone, website, services RHDBP, methods FPVI, languages, state]
    "Near" lists appear only when the county itself has none. assets/us/z<digit>.json maps a ZIP to its county.
"""
import argparse
import csv
import io
import json
import re
import sys
import urllib.request
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

try:
    import numpy as np
except ImportError:   # the tests read this module's rules without building anything, so they run without numpy
    np = None

sys.path.insert(0, str(Path(__file__).resolve().parent))
from us_geo import FIPS_STATE, STATE_FIPS  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
COUNTIES_JSON = ROOT / 'data' / 'ymt' / 'counties.json'
LINKS_JSON = ROOT / 'data' / 'county-links.json'
OUT_US = ROOT / 'assets' / 'us'

GAZ = 'https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2023_Gazetteer/'
# file name in SRC: (address, member to take out of a zip, or None)
SOURCES = {
    'co-est2024-alldata.csv': ('https://www2.census.gov/programs-surveys/popest/datasets/2020-2024/counties/totals/co-est2024-alldata.csv', None),
    '2023_Gaz_counties_national.txt': (GAZ + '2023_Gaz_counties_national.zip', '2023_Gaz_counties_national.txt'),
    '2023_Gaz_cousubs_national.txt': (GAZ + '2023_Gaz_cousubs_national.zip', '2023_Gaz_cousubs_national.txt'),
    '2023_Gaz_zcta_national.txt': (GAZ + '2023_Gaz_zcta_national.zip', '2023_Gaz_zcta_national.txt'),
    'tab20_zcta520_county20_natl.txt': ('https://www2.census.gov/geo/docs/maps-data/data/rel2020/zcta520/tab20_zcta520_county20_natl.txt', None),
    'hrsa-sites.csv': ('https://data.hrsa.gov/DataDownload/DD_Files/Health_Center_Service_Delivery_and_LookAlike_Sites.csv', None),
    'HS_Service_Locations.csv': ('https://s3foa.s3.us-east-1.amazonaws.com/HS_Service_Locations.csv', None),
}
HUD_URL = 'https://data.hud.gov/Housing_Counselor/search?AgencyName=&City=&State={st}&RowLimit=&Services=&Languages='

# How far a county's own listings are topped up from neighbours, in miles from the middle of the county.
NEAR_MILES = {'health': 60, 'head_start': 60, 'hud': 75}
NEAR_MAX = {'health': 3, 'head_start': 3, 'hud': 4}
HUD_FAR_MILES = 150          # a lone fallback when nothing is within NEAR_MILES['hud']
HRSA_OK_SETTINGS = {'All Other Clinic Types', 'Hospital', 'Unknown'}
HRSA_OK_KINDS = {'Service Delivery Site', 'Administrative/Service Delivery Site'}
HUD_OK_STATUS = {'A', 'P'}   # HUD does not publish what the codes mean; 'C' rows are left out
# A site inside a shelter, crisis unit or residence serves the people staying there, and a domestic violence
# location must never be published. Any site, program or agency whose name or street says so is left out.
SENSITIVE = re.compile(
    r"\bshelters?\b|respite|transitional|domestic|violence|abuse|battered|survivor|safe ?(house|haven|place)|\brefuge\b|"
    r"sanctuary|crisis|rescue mission|soup kitchen|anonymous|confidential|undisclosed|withheld|"
    r"\bjail\b|prison|correction|detention|juvenile hall", re.I)
# Places people live while they are treated. Applied to clinics and Head Start sites, not to housing agencies,
# whose names use "residential" in the ordinary sense.
CARE_HOME = re.compile(r"residential|group home|recovery (house|home|residence)|sobering|detox", re.I)


def sensitive(*texts, homes=True):
    return any(SENSITIVE.search(t or '') or (homes and CARE_HOME.search(t or '')) for t in texts)


SOCIAL = ('facebook.com', 'instagram.com', 'twitter.com', 'x.com', 'linkedin.com', 'youtube.com', 'tiktok.com')
BAD_HOSTS = ('notavailable.org', 'example.com', 'example.org') + SOCIAL

# ------------------------------------------------------------------ small cleaners
ACRONYMS = {'FQHC', 'HIV', 'AIDS', 'II', 'III', 'IV', 'VI', 'VII', 'VIII', 'IX', 'XI', 'XII', 'NE', 'NW', 'SE', 'SW', 'PO',
            'USA', 'LLC', 'CHC', 'FHC', 'HCA', 'WIC', 'OB', 'GYN', 'ER', 'MD', 'PC', 'LP', 'LLP', 'HQ', 'YMCA',
            'YWCA', 'SBHC', 'ENT', 'DBA', 'US', 'UT', 'UC', 'USC', 'UCLA', 'NYC', 'DC', 'FQHCS', 'CAP', 'CAA', 'HUD', 'VA'}
STATE_ABBRS = set(STATE_FIPS)
SMALL = {'of', 'the', 'and', 'for', 'de', 'del', 'la', 'las', 'los', 'el', 'y', 'at', 'in', 'on', 'to', 'a', 'an', 'or', 'by'}
STREET_ABBR = {'DR', 'ST', 'RD', 'BLVD', 'HWY', 'PKWY', 'LN', 'TRL', 'CIR', 'PL', 'TER', 'SQ', 'AVE', 'STE', 'FL', 'RM',
               'BLDG', 'APT', 'MT', 'FT', 'CT', 'CTR', 'PLZ', 'EXPY', 'XING'}


def smart_title(text, address=False):
    """ALL CAPS becomes Normal Case. Mixed-case text is somebody's own spelling and is left alone."""
    text = (text or '').strip()
    text = re.sub(r'\s+', ' ', text)
    if not text or not text.isupper():
        return text
    first = [True]

    def word(m):
        tok = m.group(0)
        was_first = first[0]
        first[0] = False
        after = text[:m.start()].rstrip()
        # A state's two letters after a comma, or at the very end, stay capitals: "Dayton, OH".
        if tok in STATE_ABBRS and (after.endswith(',') or m.end() == len(text)):
            return tok
        if address and tok in STREET_ABBR:
            return tok.capitalize()
        if tok in ACRONYMS:
            return tok
        if re.fullmatch(r'\d+(ST|ND|RD|TH)', tok):
            return tok.lower()
        if re.search(r'\d', tok) or len(tok) == 1:
            return tok
        if not re.search(r'[AEIOUY]', tok) and len(tok) <= 5 and tok not in STREET_ABBR:
            return tok
        if tok.lower() in SMALL and not was_first:
            return tok.lower()
        if tok.startswith('MC') and len(tok) > 3:
            return 'Mc' + tok[2:].capitalize()
        if tok.startswith("O'") and len(tok) > 3:
            return "O'" + tok[2:].capitalize()
        return tok.capitalize()
    return re.sub(r"[A-Za-z0-9']+", word, text)


def phone10(raw):
    """555-123-4567, or '' when the number is missing, short, or an obvious placeholder."""
    d = re.sub(r'\D', '', raw or '')
    if len(d) == 11 and d[0] == '1':
        d = d[1:]
    d = d[:10]                     # anything past ten digits is an extension, which a phone link cannot carry
    if len(d) != 10 or d[0] in '01' or len(set(d)) < 4:
        return ''
    return f'{d[:3]}-{d[3:6]}-{d[6:]}'


def zip5(raw):
    m = re.match(r'\d{5}', (raw or '').strip())
    return m.group(0) if m else ''


def clean_url(raw):
    """A web address the build could link, or '' when the field holds words, a placeholder or a social page."""
    u = (raw or '').strip()
    if not u or re.search(r'\s', u) or len(u) > 150:
        return ''
    scheme = 'https'
    m = re.match(r'(?i)(https?)://', u)
    if m:
        scheme, u = m.group(1).lower(), u[m.end():]
    parts = re.match(r'([^/?#]*)(.*)', u)
    host, rest = parts.group(1).lower(), parts.group(2)
    if not re.fullmatch(r'[a-z0-9.-]+\.[a-z]{2,}', host) or any(host == b or host.endswith('.' + b) for b in BAD_HOSTS):
        return ''
    if rest in ('', '/'):
        rest = ''
    return f'{scheme}://{host}{rest}'


def county_title(name):
    """Census writes Virginia's independent cities in lower case: 'Richmond city'."""
    return re.sub(r' city$', ' City', name)


def norm(name):
    s = name.lower().replace('&', 'and')
    s = re.sub(r'\bsaint\b|\bst\.', 'st', s)
    s = re.sub(r'\bsainte\b|\bste\.', 'ste', s)
    return re.sub(r'[^a-z0-9]+', '', s)


SUFFIX = re.compile(r'(cityandborough|censusarea|municipality|county|parish|borough|city)$')


def miles_from(lat, lon, lats, lons):
    p1, p2 = np.radians(lat), np.radians(lats)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lons - lon) / 2) ** 2
    return 3958.8 * 2 * np.arcsin(np.sqrt(a))


def in_us(lat, lon):
    """A point somewhere in the 50 states (including Alaska and Hawaii). Zero and swapped values fail."""
    return lat is not None and lon is not None and 18 < lat < 72 and -180 < lon < -66


def tsv(path):
    with open(path, encoding='utf-8-sig', newline='') as f:
        rows = csv.reader(f, delimiter='\t', quoting=csv.QUOTE_NONE)
        head = [h.strip() for h in next(rows)]
        for r in rows:
            yield dict(zip(head, [c.strip() for c in r]))


# ------------------------------------------------------------------ geography
class Geo:
    """The county list, a ZIP-to-county table, and a way to place a point in a Connecticut planning region."""

    def __init__(self, src):
        if np is None:
            sys.exit('Building the county data needs numpy: pip install numpy')
        gaz = {r['GEOID']: r for r in tsv(src / '2023_Gaz_counties_national.txt')}
        self.counties = []
        with open(src / 'co-est2024-alldata.csv', encoding='latin-1', newline='') as f:
            for r in csv.DictReader(f):
                if r['SUMLEV'] != '050' or r['STATE'].zfill(2) not in FIPS_STATE:
                    continue
                fips = r['STATE'].zfill(2) + r['COUNTY'].zfill(3)
                g = gaz[fips]
                self.counties.append({
                    'fips': fips, 'name': county_title(r['CTYNAME']), 'state': FIPS_STATE[fips[:2]],
                    'pop': int(r['POPESTIMATE2024']), 'lat': float(g['INTPTLAT']), 'lon': float(g['INTPTLONG'])})
        self.counties.sort(key=lambda c: c['fips'])
        self.by_fips = {c['fips']: c for c in self.counties}
        self.name_index = defaultdict(dict)
        self.loose_index = defaultdict(lambda: defaultdict(set))
        for c in self.counties:
            self.name_index[c['state']][norm(c['name'])] = c['fips']
            self.loose_index[c['state']][SUFFIX.sub('', norm(c['name']))].add(c['fips'])
        towns = [(r['GEOID'][:5], float(r['INTPTLAT']), float(r['INTPTLONG']))
                 for r in tsv(src / '2023_Gaz_cousubs_national.txt')
                 if r['USPS'] == 'CT' and r['GEOID'][:5] in self.by_fips and r['FUNCSTAT'] == 'A']
        self.ct_fips = [t[0] for t in towns]
        self.ct_lat = np.array([t[1] for t in towns])
        self.ct_lon = np.array([t[2] for t in towns])
        self.zip_map = self._zips(src)

    def ct_region(self, lat, lon):
        return self.ct_fips[int(np.argmin(miles_from(lat, lon, self.ct_lat, self.ct_lon)))]

    def _zips(self, src):
        """Each ZIP Code Tabulation Area goes to the county holding most of its land."""
        best = {}
        for line in open(src / 'tab20_zcta520_county20_natl.txt', encoding='utf-8-sig'):
            p = line.rstrip('\n').split('|')
            if len(p) < 17 or not p[1].isdigit():
                continue
            z, county, area = p[1], p[9], int(p[16] or 0)
            if z not in best or area > best[z][1]:
                best[z] = (county, area)
        points = {r['GEOID']: (float(r['INTPTLAT']), float(r['INTPTLONG'])) for r in tsv(src / '2023_Gaz_zcta_national.txt')}
        out = {}
        for z, (county, _) in best.items():
            if county[:2] == '09':                      # the old Connecticut counties no longer exist
                if z not in points:
                    continue
                county = self.ct_region(*points[z])
            if county in self.by_fips:
                out[z] = county
        return out

    def from_name(self, state, county_name):
        """'Stevens County' in WA to its code, or '' when the name does not match one county."""
        n = norm(county_name or '')
        hit = self.name_index[state].get(n)
        if hit:
            return hit
        loose = self.loose_index[state].get(SUFFIX.sub('', n), set())
        return next(iter(loose)) if len(loose) == 1 else ''


# ------------------------------------------------------------------ the three directories
def load_hrsa(src, geo):
    sites, seen, dropped = [], set(), Counter()
    with open(src / 'hrsa-sites.csv', encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            if (r['Site Status Description'] != 'Active' or r['Health Center Type Description'] not in HRSA_OK_KINDS
                    or r['Health Center Service Delivery Site Location Setting Description'] not in HRSA_OK_SETTINGS
                    or r['Health Center Location Type Description'] not in ('Permanent', 'Seasonal')):
                dropped['not a place to walk in'] += 1
                continue
            z = zip5(r['Site Postal Code'])
            fips = r['State and County Federal Information Processing Standard Code'].strip()
            if fips not in geo.by_fips:
                fips = geo.zip_map.get(z, '')
            if not fips or r['Site State Abbreviation'] not in STATE_FIPS:
                dropped['no county'] += 1
                continue
            name = smart_title(r['Site Name'])
            street = smart_title(r['Site Address'], True)
            if sensitive(name, street):
                dropped['shelter, crisis or confidential site'] += 1
                continue
            key = (name.lower(), street.lower(), z)
            if key in seen:
                dropped['duplicate'] += 1
                continue
            seen.add(key)
            phone = phone10(r['Site Telephone Number'])
            if not phone:
                dropped['no phone'] += 1
                continue
            try:
                hours = int(float(r['Operating Hours per Week'] or 0))
            except ValueError:
                hours = 0
            try:
                lat = float(r['Geocoding Artifact Address Primary Y Coordinate'])
                lon = float(r['Geocoding Artifact Address Primary X Coordinate'])
            except ValueError:
                lat = lon = None
            if not in_us(lat, lon):
                lat = lon = None
            sites.append({
                'fips': fips, 'st': r['Site State Abbreviation'], 'org': smart_title(r['Health Center Name']), 'name': name, 'street': street,
                'city': smart_title(r['Site City']), 'zip': z, 'phone': phone, 'web': clean_url(r['Site Web Address']),
                'hours': hours, 'seasonal': int(r['Health Center Location Type Description'] == 'Seasonal'),
                'lat': lat, 'lon': lon})
    return sites, dropped


HS_TYPES = {'1': 1, '2': 2, '3': 1 | 4, '4': 2 | 4, '5': 1 | 8, '6': 2 | 8}   # 1 Head Start, 2 Early, 4 migrant/seasonal, 8 tribal


def load_head_start(src, geo):
    places, dropped = {}, Counter()
    with open(src / 'HS_Service_Locations.csv', encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            if r['status'] != 'Open' or r['state'] not in STATE_FIPS:
                continue
            z = zip5(r['zip'])
            try:
                lat, lon = float(r['latitude']), float(r['longitude'])
            except ValueError:
                lat = lon = None
            if not in_us(lat, lon):
                lat = lon = None
            if r['state'] == 'CT':
                fips = geo.ct_region(lat, lon) if lat is not None else geo.zip_map.get(z, '')
            else:
                fips = geo.from_name(r['state'], r['county']) or geo.zip_map.get(z, '')
            if fips not in geo.by_fips or fips[:2] != STATE_FIPS[r['state']]:
                dropped['no county'] += 1
                continue
            phone = phone10(r['registration_phone_number']) or phone10(r['service_location_phone_number'])
            if not phone:
                dropped['no phone'] += 1
                continue
            street = smart_title(' '.join(x for x in (r['address_line_one'], r['address_line_two']) if x.strip()), True)
            city = smart_title(r['city'])
            key = (fips, street.lower(), city.lower(), z)
            name = smart_title(r['service_location_name']) or smart_title(r['program_admin_name'])
            org = smart_title(r['program_admin_name'])
            if sensitive(name, street):
                dropped['shelter, crisis or confidential site'] += 1
                continue
            p = places.setdefault(key, {'fips': fips, 'st': r['state'], 'name': name, 'org': org, 'street': street, 'city': city, 'zip': z,
                                        'phone': phone, 'types': 0, 'lat': lat, 'lon': lon})
            p['types'] |= HS_TYPES.get(r['program_type'], 0)
    return list(places.values()), dropped


SERVICE_FLAGS = {'RHC': 'R', 'HMC': 'H', 'DFC': 'D', 'FBC': 'B', 'PPC': 'P'}   # rent, homeless, mortgage trouble, budget, buying
METHOD_FLAGS = {'Face to Face Counseling': 'F', 'Phone Counseling': 'P', 'Phone Counseling Only': 'P',
                'Video Conference': 'V', 'Internet Counseling': 'I'}
LANGUAGES = {'ASL': 'American Sign Language', 'ARA': 'Arabic', 'CAM': 'Cambodian', 'CAN': 'Cantonese', 'CHI': 'Mandarin',
             'CRE': 'Creole', 'CZE': 'Czech', 'FAR': 'Farsi', 'FRE': 'French', 'GER': 'German', 'HIN': 'Hindi',
             'HMO': 'Hmong', 'IND': 'Indonesian', 'ITA': 'Italian', 'KOR': 'Korean', 'POL': 'Polish', 'POR': 'Portuguese',
             'RUS': 'Russian', 'SPA': 'Spanish', 'SWA': 'Swahili', 'TUR': 'Turkish', 'UKR': 'Ukrainian', 'VIE': 'Vietnamese'}


def load_hud(src, geo):
    agencies, dropped = [], Counter()
    for st in sorted(STATE_FIPS):
        p = src / 'hud' / f'{st}.json'
        if not p.exists():
            continue
        for a in json.loads(p.read_text(encoding='utf-8')):
            if a.get('agc_STATUS') not in HUD_OK_STATUS:
                dropped['status'] += 1
                continue
            phone = phone10(a.get('phone1'))
            try:
                lat, lon = float(a['agc_ADDR_LATITUDE']), float(a['agc_ADDR_LONGITUDE'])
            except (TypeError, ValueError, KeyError):
                lat = lon = None
            if not in_us(lat, lon):
                dropped['no point'] += 1
                continue
            if not phone:
                dropped['no phone'] += 1
                continue
            if sensitive(a.get('nme'), a.get('adr1'), homes=False):
                dropped['shelter, crisis or confidential site'] += 1
                continue
            z = zip5(a.get('zipcd'))
            svc = sorted({SERVICE_FLAGS[s] for s in (a.get('services') or '').split(',') if s.strip() in SERVICE_FLAGS})
            methods = sorted({METHOD_FLAGS[m.strip()] for m in (a.get('counslg_METHOD') or '').split(',') if m.strip() in METHOD_FLAGS})
            langs = [LANGUAGES[x.strip()] for x in (a.get('languages') or '').split(',') if x.strip() in LANGUAGES]
            fips = geo.ct_region(lat, lon) if a.get('statecd') == 'CT' else geo.zip_map.get(z, '')
            agencies.append({
                'id': str(a['agcid']), 'fips': fips, 'st': a.get('statecd') or '', 'name': smart_title(a['nme']), 'street': smart_title(a.get('adr1') or '', True),
                'city': smart_title(a.get('city') or ''), 'zip': z, 'phone': phone, 'web': clean_url(a.get('weburl')),
                'services': ''.join(svc), 'methods': ''.join(methods), 'languages': langs, 'lat': lat, 'lon': lon})
    return agencies, dropped


# ------------------------------------------------------------------ assembling the shards
def verified(url, ledger):
    """The address to link, if the link check saw it load: as written, or as plain http when only that worked."""
    if url and ledger.get(url) in ('ok', 'refused'):
        return url
    plain = 'http://' + url[len('https://'):] if url.startswith('https://') else ''
    return plain if plain and ledger.get(plain) in ('ok', 'refused') else ''


def nearest(county, items, kind, exclude=()):
    """Up to NEAR_MAX items from the county's neighbourhood, nearest first, each with its distance in whole miles."""
    pts = [i for i in items if i['lat'] is not None and i not in exclude]
    if not pts:
        return []
    d = miles_from(county['lat'], county['lon'], np.array([i['lat'] for i in pts]), np.array([i['lon'] for i in pts]))
    order = np.argsort(d)[:NEAR_MAX[kind]]
    return [(pts[int(i)], max(1, int(round(float(d[int(i)]))))) for i in order if d[int(i)] <= NEAR_MILES[kind]]


def build(src, ledger, asof):
    geo = Geo(src)
    hrsa, hrsa_drop = load_hrsa(src, geo)
    hs, hs_drop = load_head_start(src, geo)
    hud, hud_drop = load_hud(src, geo)
    by = {'health': defaultdict(list), 'head_start': defaultdict(list), 'hud': defaultdict(list)}
    for s in hrsa:
        by['health'][s['fips']].append(s)
    for s in hs:
        by['head_start'][s['fips']].append(s)
    for a in hud:
        if a['fips']:
            by['hud'][a['fips']].append(a)
    # Latitudes and longitudes, grouped once so each county's neighbourhood search is a single array operation.
    pools = {'health': [s for s in hrsa if s['lat'] is not None], 'head_start': [s for s in hs if s['lat'] is not None], 'hud': hud}
    ohio_pages = {p.stem: f'ohio/counties/{p.name}' for p in (ROOT / 'ohio' / 'counties').glob('*.html')}

    def health_row(s, miles):
        return [s['org'], s['name'], s['street'], s['city'], s['zip'], s['phone'], verified(s['web'], ledger),
                s['hours'], s['seasonal'], miles, s['st']]

    def hs_row(s, miles):
        return [s['name'], s['org'], s['street'], s['city'], s['zip'], s['phone'], s['types'], miles, s['st']]

    shards = {st: {'v': 1, 'asof': asof, 'st': st, 'c': {}, 'hu': {}} for st in STATE_FIPS}
    used_hud = defaultdict(set)
    for c in geo.counties:
        entry = {'n': c['name'], 'p': c['pop']}
        slug = c['name'].removesuffix(' County').lower().replace(' ', '-')
        if c['state'] == 'OH' and slug in ohio_pages:
            entry['pg'] = ohio_pages[slug]
        local = sorted(by['health'][c['fips']], key=lambda s: (s['city'].lower(), s['org'].lower(), s['name'].lower()))
        if local:
            entry['health'] = [health_row(s, 0) for s in local]
        else:
            near = nearest(c, pools['health'], 'health')
            if near:
                entry['healthNear'] = [health_row(s, m) for s, m in near]
        local = sorted(by['head_start'][c['fips']], key=lambda s: (s['city'].lower(), s['name'].lower()))
        if local:
            entry['headStart'] = [hs_row(s, 0) for s in local]
        else:
            near = nearest(c, pools['head_start'], 'head_start')
            if near:
                entry['headStartNear'] = [hs_row(s, m) for s, m in near]
        # Housing counselors: those in the county first, then the nearest others, a handful in all.
        inside = by['hud'][c['fips']]
        d_in = {a['id']: miles_from(c['lat'], c['lon'], np.array([a['lat']]), np.array([a['lon']]))[0] for a in inside}
        chosen = [(a, 0) for a in sorted(inside, key=lambda a: d_in[a['id']])][:NEAR_MAX['hud']]
        if len(chosen) < NEAR_MAX['hud']:
            more = nearest(c, [a for a in hud if a not in inside], 'hud')
            chosen += [(a, m) for a, m in more][:NEAR_MAX['hud'] - len(chosen)]
        if not chosen and hud:
            d = miles_from(c['lat'], c['lon'], np.array([a['lat'] for a in hud]), np.array([a['lon'] for a in hud]))
            i = int(np.argmin(d))
            if d[i] <= HUD_FAR_MILES:
                chosen = [(hud[i], int(round(float(d[i]))))]
        if chosen:
            entry['hud'] = [[a['id'], m] for a, m in chosen]
            for a, _ in chosen:
                used_hud[c['state']].add(a['id'])
        shards[c['state']]['c'][c['fips']] = entry
    hud_by_id = {a['id']: a for a in hud}
    for st, ids in used_hud.items():
        for i in sorted(ids):
            a = hud_by_id[i]
            shards[st]['hu'][i] = [a['name'], a['street'], a['city'], a['zip'], a['phone'], verified(a['web'], ledger),
                                   a['services'], a['methods'], a['languages'], a['st']]
    stats = {'hrsa': (len(hrsa), dict(hrsa_drop)), 'head_start': (len(hs), dict(hs_drop)), 'hud': (len(hud), dict(hud_drop))}
    return geo, shards, stats


def write_all(geo, shards):
    OUT_US.mkdir(parents=True, exist_ok=True)
    for old in OUT_US.glob('*.json'):
        old.unlink()
    dump = lambda o: json.dumps(o, separators=(',', ':'), sort_keys=True)  # noqa: E731
    for st, shard in shards.items():
        (OUT_US / f'{st.lower()}.json').write_text(dump(shard) + '\n', encoding='utf-8')
    by_digit = defaultdict(dict)
    for z, fips in sorted(geo.zip_map.items()):
        by_digit[z[0]][z] = fips
    for d, table in sorted(by_digit.items()):
        (OUT_US / f'z{d}.json').write_text(dump(table) + '\n', encoding='utf-8')
    COUNTIES_JSON.write_text(json.dumps(
        [{'fips': c['fips'], 'name': c['name'], 'state': c['state'], 'pop': c['pop']} for c in geo.counties],
        separators=(',', ':'), ensure_ascii=True) + '\n', encoding='utf-8')


def candidate_urls(src):
    """Every website address a build from SRC could link: what scripts/county_links.py has to check."""
    geo = Geo(src)
    urls = {s['web'] for s in load_hrsa(src, geo)[0]} | {a['web'] for a in load_hud(src, geo)[0]}
    return sorted(u for u in urls if u)


# ------------------------------------------------------------------ fetching
def fetch(src):
    src.mkdir(parents=True, exist_ok=True)
    (src / 'hud').mkdir(exist_ok=True)
    jobs = [(name, url, member) for name, (url, member) in SOURCES.items()]
    jobs += [(f'hud/{st}.json', HUD_URL.format(st=st), None) for st in sorted(STATE_FIPS)]
    for name, url, member in jobs:
        dest = src / name
        if dest.exists() and dest.stat().st_size > 0:
            continue
        print('fetching', name, flush=True)
        req = urllib.request.Request(url, headers={'User-Agent': 'YogaMomTalk county data build (+https://www.yogamomtalk.com/about.html)'})
        with urllib.request.urlopen(req, timeout=180) as resp:
            blob = resp.read()
        if member:
            blob = zipfile.ZipFile(io.BytesIO(blob)).read(member)
        dest.write_bytes(blob)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('src', type=Path)
    ap.add_argument('--fetch', action='store_true', help='download the raw files into SRC first')
    ap.add_argument('--urls', action='store_true', help='print the website addresses the build would link')
    ap.add_argument('--asof', default=None, help='date the federal files were downloaded, YYYY-MM-DD (default: today)')
    args = ap.parse_args()
    if args.fetch:
        fetch(args.src)
    if args.urls:
        print('\n'.join(candidate_urls(args.src)))
        return
    from datetime import date
    asof = args.asof or date.today().isoformat()
    ledger = json.loads(LINKS_JSON.read_text(encoding='utf-8')).get('urls', {}) if LINKS_JSON.exists() else {}
    geo, shards, stats = build(args.src, ledger, asof)
    write_all(geo, shards)
    for k, (n, drop) in stats.items():
        print(f'{k}: kept {n}, left out {drop}')
    print(f'{len(geo.counties)} counties, {len(geo.zip_map)} ZIP codes, {sum(1 for v in ledger.values() if v in ("ok", "refused"))} checked websites')


if __name__ == '__main__':
    main()
