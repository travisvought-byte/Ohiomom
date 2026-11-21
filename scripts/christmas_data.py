"""Toys for Tots campaigns for the Christmas help pages.

Marine Toys for Tots runs one local campaign per area, each with its own website where families apply for toys.
The national site publishes every place it serves (about 1,800 towns and counties) as WordPress "tft-location"
records, each naming the campaign website that serves it and a ZIP code with a map point.

    python3 scripts/christmas_data.py --fetch      download the list into data/ymt/toysfortots.json
    python3 scripts/christmas_data.py              write assets/us/christmas.json from that file
    python3 scripts/christmas_data.py --check      confirm assets/us/christmas.json matches

The download needs the open internet (GitHub Actions has it; .github/workflows/christmas-refresh.yml runs it).
assets/us/christmas.json is read by the county page: for each county, the campaigns that list a place in it,
found by the place's ZIP code through the same ZIP files the county page uses (assets/us/z*.json).
The state pages take their lists from campaigns_by_state() when scripts/ymt_build.py runs.
"""
import json
import re
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / 'data' / 'ymt' / 'toysfortots.json'
OUT = ROOT / 'assets' / 'us' / 'christmas.json'
API = 'https://www.toysfortots.org/wp-json/wp/v2/tft-location'
SOURCE = 'https://www.toysfortots.org/find-your-local-chapter/'
STATES = set('AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH '
              'OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY'.split())


def php_field(blob, key):
    """One value out of the PHP-serialized address WordPress stores, e.g. s:4:"city";s:6:"Durant"; or s:3:"lat";d:33.1;"""
    m = re.search(r's:\d+:"' + re.escape(key) + r'";(?:s:\d+:"([^"]*)"|d:(-?[\d.]+)|i:(-?\d+))', blob or '')
    if not m:
        return None
    return m.group(1) if m.group(1) is not None else (m.group(2) or m.group(3))


def clean_site(url):
    url = (url or '').strip()
    if not url:
        return ''
    if not url.lower().startswith('http'):
        url = 'https://' + url
    url = re.sub(r'^http://', 'https://', url, flags=re.I)
    m = re.match(r'https://([^/?#]+)', url, re.I)
    if not m or not m.group(1).lower().endswith('toysfortots.org'):
        return ''  # only campaign sites on toysfortots.org are listed
    return 'https://' + m.group(1).lower() + '/'


def fetch():
    out, page, total = [], 1, None
    while True:
        url = f'{API}?per_page=100&page={page}&_fields=id,title,cp_meta_data'
        req = urllib.request.Request(url, headers={'User-Agent': 'YogaMomTalk-directory/1.0 (+https://www.yogamomtalk.com/)'})
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    total = int(r.headers.get('X-WP-TotalPages') or 1)
                    rows = json.load(r)
                break
            except Exception as e:  # noqa: BLE001
                if attempt == 3:
                    raise
                print(f'page {page}: {e}; retrying', file=sys.stderr)
                time.sleep(5 * (attempt + 1))
        for o in rows:
            m = o.get('cp_meta_data') or {}

            def one(k):
                v = m.get(k)
                return (v[0] if isinstance(v, list) and v else v or '') if v is not None else ''
            addr = one('location_address')
            title = re.sub(r'\s+', ' ', (o.get('title') or {}).get('rendered', '')).strip()
            state = (php_field(addr, 'state_short') or '').upper()
            tail = re.search(r'\b([A-Z]{2})$', title)
            if state not in STATES and tail:
                state = tail.group(1)
            lat, lng = php_field(addr, 'lat'), php_field(addr, 'lng')
            out.append({
                'id': o['id'], 'name': title, 'state': state,
                'zip': (php_field(addr, 'post_code') or '')[:5],
                'lat': round(float(lat), 4) if lat else None, 'lng': round(float(lng), 4) if lng else None,
                'site': clean_site(one('location_website')),
                'email': one('location_email').strip().lower(),
                'phone': one('location_phone').strip(),
            })
        print(f'page {page}/{total}: {len(out)} places', file=sys.stderr)
        if page >= (total or 1):
            break
        page += 1
        time.sleep(1)
    out.sort(key=lambda r: (r['state'], r['name'].lower(), r['id']))
    RAW.write_text(json.dumps({'checked_on': date.today().isoformat(), 'source': SOURCE, 'api': API,
                               'places': out}, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'Wrote {len(out)} places to {RAW.relative_to(ROOT)}')


def load():
    return json.loads(RAW.read_text(encoding='utf-8')) if RAW.exists() else None


def campaigns(raw=None):
    """One entry per campaign website: [site, name, state, [place names]]. The name is the place whose title matches
    the website's address best (greenville-il.toysfortots.org is "Greenville IL"), otherwise the first place."""
    raw = raw or load()
    if not raw:
        return []
    by = {}
    for p in raw['places']:
        if p['site'] and p['state'] in STATES:
            by.setdefault(p['site'], []).append(p)
    out = []
    for site, places in by.items():
        host = site.split('//')[1].split('.')[0].replace('-', '').lower()

        def score(p):
            key = re.sub(r'[^a-z]', '', p['name'].lower())
            return 0 if key == host else (1 if key[:6] == host[:6] else 2)
        best = sorted(places, key=lambda p: (score(p), p['name']))[0]
        states = sorted({p['state'] for p in places}, key=lambda s: -sum(q['state'] == s for q in places))
        names = sorted({p['name'] for p in places})
        out.append({'site': site, 'name': best['name'], 'state': states[0], 'states': states, 'places': names,
                    'email': next((p['email'] for p in places if p['email']), ''),
                    'zips': sorted({p['zip'] for p in places if p['zip']})})
    out.sort(key=lambda c: (c['state'], c['name'].lower()))
    return out


def campaigns_by_state(raw=None):
    """{state: [campaign, ...]} with a campaign listed in every state where it serves a place."""
    out = {}
    for c in campaigns(raw):
        for s in c['states']:
            out.setdefault(s, []).append(c)
    for s in out:
        out[s].sort(key=lambda c: c['name'].lower())
    return out


def zip_county():
    z = {}
    for f in sorted((ROOT / 'assets' / 'us').glob('z*.json')):
        z.update(json.loads(f.read_text(encoding='utf-8')))
    return z


def build():
    raw = load()
    if not raw:
        return None
    camps = campaigns(raw)
    zc = zip_county()
    county = {}
    for i, c in enumerate(camps):
        for z in c['zips']:
            f = zc.get(z)
            if f and i not in county.setdefault(f, []):
                county[f].append(i)
    data = {'v': 1, 'asof': raw['checked_on'],
            # [website, campaign name, state, email, places served]
            'tft': [[c['site'], c['name'], c['state'], c['email'], c['places']] for c in camps],
            'c': {f: sorted(v) for f, v in sorted(county.items())}}
    return json.dumps(data, separators=(',', ':'), ensure_ascii=False) + '\n'


def main():
    if '--fetch' in sys.argv:
        fetch()
        return
    text = build()
    if text is None:
        print('No data/ymt/toysfortots.json yet: run with --fetch where the internet is open.')
        sys.exit(1)
    if '--check' in sys.argv:
        if not OUT.exists() or OUT.read_text(encoding='utf-8') != text:
            print('assets/us/christmas.json is out of date: run python3 scripts/christmas_data.py')
            sys.exit(1)
        print('OK: assets/us/christmas.json matches')
        return
    OUT.write_text(text, encoding='utf-8')
    d = json.loads(text)
    print(f"Wrote {OUT.relative_to(ROOT)}: {len(d['tft'])} campaigns, {len(d['c'])} counties with a campaign place")


if __name__ == '__main__':
    main()
