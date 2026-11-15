#!/usr/bin/env python3
"""Request every link on the site and print a markdown report.

Exit 1 only if a link looks truly broken (404, 410, 5xx, unknown host). Sites that
refuse automated requests (401, 403, 429, timeouts) are listed separately for a person
to open by hand, because a refusal does not mean the page is gone.
"""
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ymt_lib as lib  # noqa: E402

UA = 'Mozilla/5.0 (compatible; YogaMomTalk link check; +https://yogamomtalk.com/about.html)'
SOFT = {401, 403, 405, 406, 429, 999}


def collect():
    data = lib.load()
    used = {}
    for r in lib.all_records(data):
        urls = [r.get('url')] + list(r.get('sources', [])) + [l['url'] for l in r.get('links', [])]
        for u in urls:
            if u:
                used.setdefault(u, set()).add(r['id'])
    for u in (data['site']['mobilitytalk_url'], data['site']['vhg_guide_url']):
        used.setdefault(u, set()).add('site')
    return used


def fetch(url):
    last = ''
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'text/html,*/*'})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return 'ok', resp.status
        except urllib.error.HTTPError as exc:
            if exc.code in SOFT:
                return 'soft', exc.code
            last = f'HTTP {exc.code}'
            if exc.code < 500:
                return 'bad', last
        except urllib.error.URLError as exc:
            last = str(exc.reason)[:100]
            if 'timed out' in last:
                return 'soft', last
        except Exception as exc:  # report it; a person decides what it means
            last = str(exc)[:100]
        time.sleep(2)
    return 'bad', last


def main():
    used = collect()
    urls = sorted(used)

    def work(u):
        time.sleep(0.2)
        return u, fetch(u)

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(work, urls))
    bad = [(u, why) for u, (kind, why) in results if kind == 'bad']
    soft = [(u, why) for u, (kind, why) in results if kind == 'soft']

    def listing(u):
        ids = sorted(used[u])
        return ', '.join(f'`{i}`' for i in ids[:6]) + (f' and {len(ids) - 6} more' if len(ids) > 6 else '')

    print(f'Checked {len(urls)} links.\n')
    if bad:
        print('## Links that did not load\n')
        print('Open each one before changing it. Then fix `data/` and run `python3 scripts/build.py`.\n')
        for u, why in bad:
            print(f'- {u} ({why}), used by {listing(u)}')
        print()
    if soft:
        print('## Sites that refused an automated check\n')
        print('These often work in a browser. Open them to confirm.\n')
        for u, why in soft:
            print(f'- {u} ({why}), used by {listing(u)}')
        print()
    if not bad and not soft:
        print('All links loaded.')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
