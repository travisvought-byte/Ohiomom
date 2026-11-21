"""Marine Toys for Tots local campaigns for the Christmas help pages.

Toys for Tots runs one local campaign per area, each with its own website on toysfortots.org where families
apply for toys. The national site publishes every place it serves as WordPress "tft-location" records, each naming
the campaign website and a ZIP code. data/ymt/toysfortots.txt keeps them, one line per campaign website:

    subdomain | campaign place | state | ZIP codes of its places | other place names

    python3 scripts/christmas_data.py --fetch      read the list again from toysfortots.org into that file
    python3 scripts/christmas_data.py              write assets/us/christmas.json from it
    python3 scripts/christmas_data.py --check      confirm assets/us/christmas.json matches

toysfortots.org refuses GitHub's servers (HTTP 403, November 20, 2026), so --fetch has to run from an ordinary
internet connection. The November 20, 2026 list was read in a browser on the owner's computer and checked
character for character against what the site returned.

assets/us/christmas.json is read by the county page: for each county, the campaigns with a place in it, found by
ZIP code through the same ZIP files the county page uses (assets/us/z*.json), and every campaign in the state.
The state pages and christmas.html take their lists from by_state() when scripts/ymt_build.py runs.
"""
import json
import re
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / 'data' / 'ymt' / 'toysfortots.txt'
OUT = ROOT / 'assets' / 'us' / 'christmas.json'
API = 'https://www.toysfortots.org/wp-json/wp/v2/tft-location'
SOURCE = 'https://www.toysfortots.org/find-your-local-chapter/'
STATES = set('AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH '
              'OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY PR GU VI'.split())
SKIP = {'mtftf'}  # the Foundation's own headquarters record, not a local campaign
# Spelling slips in the source names, fixed for display only.
NAME_FIXES = {'Delware OH': 'Delaware OH', 'Townshed VT': 'Townshend VT', 'PaHrump NV': 'Pahrump NV',
              'Steuben county NY': 'Steuben County NY', 'Kellog': 'Kellogg'}


def site(slug):
    return f'https://{slug}.toysfortots.org/'


def php_field(blob, key):
    """One value out of the PHP-serialized address WordPress stores, e.g. s:4:"city";s:6:"Durant";"""
    m = re.search(r's:\d+:"' + re.escape(key) + r'";(?:s:\d+:"([^"]*)"|d:(-?[\d.]+))', blob or '')
    return (m.group(1) if m.group(1) is not None else m.group(2)) if m else ''


def fetch():
    """Read every place from the WordPress list and group the places by campaign website."""
    places, page, total = [], 1, 1
    while page <= total:
        req = urllib.request.Request(f'{API}?per_page=100&page={page}&_fields=id,title,cp_meta_data',
                                     headers={'User-Agent': 'Mozilla/5.0 (YogaMomTalk directory; +https://www.yogamomtalk.com/)'})
        with urllib.request.urlopen(req, timeout=60) as r:
            total = int(r.headers.get('X-WP-TotalPages') or 1)
            rows = json.load(r)
        for o in rows:
            m = o.get('cp_meta_data') or {}

            def one(k):
                v = m.get(k)
                return (v[0] if isinstance(v, list) and v else v) or ''
            name = re.sub(r'\s+', ' ', (o.get('title') or {}).get('rendered', '')).replace('&#8217;', "'").replace('&amp;', '&').strip()
            host = re.sub(r'^https?://', '', one('location_website').strip().lower()).split('/')[0]
            if not host.endswith('.toysfortots.org'):
                continue
            addr = one('location_address')
            tail = re.search(r'\b([A-Z]{2})$', name)
            st = tail.group(1) if tail and tail.group(1) in STATES else (php_field(addr, 'state_short').split() or [''])[-1].upper()
            places.append({'slug': host[:-len('.toysfortots.org')], 'name': name, 'st': st if st in STATES else '',
                           'zip': php_field(addr, 'post_code')[:5].zfill(5) if php_field(addr, 'post_code') else ''})
        page += 1
        time.sleep(1)
    by = {}
    for p in places:
        by.setdefault(p['slug'], []).append(p)

    def key(s):
        return re.sub(r'[^a-z]', '', s.lower())
    lines = []
    for slug, ps in by.items():
        if slug in SKIP:
            continue
        h = key(slug)
        best = sorted(ps, key=lambda p: (0 if key(p['name']) == h else 1 if key(p['name'])[:6] == h[:6] else 2, p['name']))[0]
        sts = list(dict.fromkeys(p['st'] for p in ps if p['st']))
        zips = sorted({p['zip'] for p in ps if p['zip']})
        others = sorted({p['name'] for p in ps} - {best['name']})
        lines.append('|'.join([slug, best['name'], ' '.join(sts), ','.join(zips), ';'.join(others)]).rstrip('|'))
    lines.sort(key=lambda l: (l.split('|')[2] or 'ZZ', l.split('|')[1], l.split('|')[0]))
    head = RAW.read_text(encoding='utf-8').splitlines()[:1] if RAW.exists() else ['# Marine Toys for Tots local campaigns']
    head.append(f'# Read {date.today().isoformat()} from {API} (the list behind {SOURCE}). Rebuilt by scripts/christmas_data.py --fetch.')
    RAW.write_text('\n'.join(head + lines) + '\n', encoding='utf-8')
    print(f'Wrote {len(lines)} campaigns from {len(places)} places to {RAW.relative_to(ROOT)}')


def checked_on():
    m = re.search(r'# Read (\d{4}-\d{2}-\d{2})', RAW.read_text(encoding='utf-8'))
    return m.group(1) if m else ''


def campaigns():
    """Every campaign: {'slug', 'url', 'name', 'place', 'state', 'zips', 'others'}. name is the place without its
    state code ("Greenville IL" is "Greenville")."""
    out = []
    for line in RAW.read_text(encoding='utf-8').splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        parts = (line.split('|') + ['', '', '', ''])[:5]
        slug, place, st, zips, others = parts
        if slug in SKIP:
            continue
        place = NAME_FIXES.get(place, place)
        state = st.split()[0] if st else ''
        name = re.sub(r'\s+' + re.escape(state) + r'\b', '', place).strip() if state else place
        out.append({'slug': slug, 'url': site(slug), 'name': name or place, 'place': place, 'state': state,
                    'zips': [z for z in zips.split(',') if z], 'others': [o for o in others.split(';') if o]})
    return out


def by_state():
    out = {}
    for c in campaigns():
        out.setdefault(c['state'], []).append(c)
    for s in out:
        out[s].sort(key=lambda c: c['name'].lower())
    return out


def zip_county():
    z = {}
    for f in sorted((ROOT / 'assets' / 'us').glob('z*.json')):
        z.update(json.loads(f.read_text(encoding='utf-8')))
    return z


def build():
    camps = sorted(campaigns(), key=lambda c: (c['state'], c['name'].lower()))
    zc = zip_county()
    county, state = {}, {}
    for i, c in enumerate(camps):
        state.setdefault(c['state'], []).append(i)
    # A county's campaigns: first those named for it (knox-county-oh, "Delaware OH"), then those whose listed
    # address is in it. The address is often the coordinator's office, so the page says each campaign's own
    # website names the towns it serves.
    names = json.loads((ROOT / 'data' / 'ymt' / 'counties.json').read_text(encoding='utf-8'))
    for cty in names:
        base = re.sub(r'\s+(County|Parish|Borough|Census Area|City and Borough|Municipality|Planning Region|city)$', '', cty['name'])
        words = re.sub(r'[^a-z ]', '', base.lower()).split()
        if not words:
            continue
        pat = re.compile(r'(^|[^a-z])' + r'[^a-z]*'.join(words) + r'([^a-z]|$)')
        for i, c in enumerate(camps):
            if c['state'] != cty['state']:
                continue
            text = (c['slug'] + ' ' + c['place'] + ' ' + ' '.join(c['others'])).lower()
            county_word = re.search(r'(^|[^a-z])' + r'[^a-z]*'.join(words) + r'[^a-z]*(county|parish|co)([^a-z]|$)', text)
            # A bare town name counts only when the county has the same name (Delaware, Marion, Lancaster).
            if county_word or pat.search(re.sub(r'\b' + cty['state'].lower() + r'\b', '', c['place'].lower())):
                county.setdefault(cty['fips'], [])
                if i not in county[cty['fips']]:
                    county[cty['fips']].append(i)
    for i, c in enumerate(camps):
        for z in c['zips']:
            f = zc.get(z)
            if f and i not in county.setdefault(f, []):
                county[f].append(i)
    data = {'v': 1, 'asof': checked_on(), 'source': SOURCE, 'site': 'https://{}.toysfortots.org/',
            # [website subdomain, campaign name, state]
            't': [[c['slug'], c['name'], c['state']] for c in camps],
            'st': state, 'c': {f: v for f, v in sorted(county.items())}}
    return json.dumps(data, separators=(',', ':'), ensure_ascii=False) + '\n'


def main():
    if '--fetch' in sys.argv:
        fetch()
        return
    text = build()
    if '--check' in sys.argv:
        if not OUT.exists() or OUT.read_text(encoding='utf-8') != text:
            print('assets/us/christmas.json is out of date: run python3 scripts/christmas_data.py')
            sys.exit(1)
        print('OK: assets/us/christmas.json matches')
        return
    OUT.write_text(text, encoding='utf-8')
    d = json.loads(text)
    print(f"Wrote {OUT.relative_to(ROOT)}: {len(d['t'])} campaigns, {len(d['c'])} counties with a campaign place")


if __name__ == '__main__':
    main()
