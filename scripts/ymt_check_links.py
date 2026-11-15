#!/usr/bin/env python3
"""Request every link on the national pages and print a markdown report.

Exit 1 when a person needs to look: a link is broken, now goes to a different website, or sits on
a site that turns robots away and has not been opened in a browser recently. See linkcheck.py.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import linkcheck  # noqa: E402
import ymt_lib as lib  # noqa: E402


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


def main():
    used = collect()
    results = linkcheck.Checker().check_all(sorted(used))
    text, needs_a_person = linkcheck.report(
        results, used, linkcheck.load_ledger(),
        fix_hint='Fix `data/ymt/` and run `python3 scripts/ymt_build.py`.')
    print(text)
    sys.exit(1 if needs_a_person else 0)


if __name__ == '__main__':
    main()
