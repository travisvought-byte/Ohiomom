#!/usr/bin/env python3
"""Request every outside link on the Ohio pages and print a markdown report.

The links come from three places: the statewide listings in data/resources.json, every link written
into the pages under ohio/ (the county pages keep their listings there), and the moms groups in
ohio/assets/data.json. Events are left out, because an event's page is expected to go away.

Exit 1 when a person needs to look: a link is broken, now goes to a different website, or sits on
a site that turns robots away and has not been opened in a browser recently. See linkcheck.py.
"""
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import linkcheck  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
HREF = re.compile(r'<a\b[^>]*\bhref="(https://[^"]+)"')
OWN_SITE = 'yogamomtalk.com'


def collect():
    """{address: the listings and pages that use it}"""
    used = {}
    data = json.loads((ROOT / 'data' / 'resources.json').read_text(encoding='utf-8'))
    for r in data['resources']:
        if r.get('url'):
            used.setdefault(r['url'], set()).add(r['id'])
    for page in sorted((ROOT / 'ohio').rglob('*.html')):
        for url in HREF.findall(page.read_text(encoding='utf-8')):
            url = html.unescape(url)
            if linkcheck.site_of(url) != OWN_SITE:
                used.setdefault(url, set()).add(page.relative_to(ROOT).as_posix())
    groups = json.loads((ROOT / 'ohio' / 'assets' / 'data.json').read_text(encoding='utf-8'))['groups']
    for g in groups:
        used.setdefault(g['url'], set()).add('group ' + g['id'])
    return used


def main():
    used = collect()
    results = linkcheck.Checker().check_all(sorted(used))
    text, needs_a_person = linkcheck.report(
        results, used, linkcheck.load_ledger(),
        fix_hint='Fix the card on the Ohio page named, and `data/resources.json` or `ohio/assets/data.json` if the listing is kept there.')
    print(text)
    sys.exit(1 if needs_a_person else 0)


if __name__ == '__main__':
    main()
