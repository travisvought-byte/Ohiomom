#!/usr/bin/env python3
"""Request each Ohio listing's website and print a markdown report.

Exit 1 when a person needs to look: a link is broken, now goes to a different website, or sits on
a site that turns robots away and has not been opened in a browser recently. See linkcheck.py.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import linkcheck  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def collect():
    data = json.loads((ROOT / 'data' / 'resources.json').read_text(encoding='utf-8'))
    used = {}
    for r in data['resources']:
        if r.get('url'):
            used.setdefault(r['url'], set()).add(r['id'])
    return used


def main():
    used = collect()
    results = linkcheck.Checker().check_all(sorted(used))
    text, needs_a_person = linkcheck.report(
        results, used, linkcheck.load_ledger(),
        fix_hint='Fix `data/resources.json` and the matching card on the Ohio pages.')
    print(text)
    sys.exit(1 if needs_a_person else 0)


if __name__ == '__main__':
    main()
