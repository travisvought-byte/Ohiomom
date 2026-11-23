#!/usr/bin/env python3
"""Check the website addresses on the county pages, and keep the answers in data/county-links.json.

A county page shows a Website button only for an address this check has seen load. The health center,
housing counselor and school district directories hold thousands of addresses, and some have lapsed or been
taken over, so nothing is linked on trust.

    python3 scripts/county_links.py SRC             check every address county_data.py would link (SRC as there)
    python3 scripts/county_links.py SRC --recheck   check them all again, not only the new ones
    python3 scripts/county_links.py --shards        check the addresses the built shards link now (the monthly check)
    python3 scripts/county_links.py --local-help    check the new websites in the local help for moms listings
                                                    (data/ymt/local-help/listings.csv; scripts/local_help.py)

Answers: ok (loaded), refused (the site turns robots away, so it is there but cannot be confirmed),
and everything else, which is left off the page: broken, moved, unverified. 'moved' needs a person
to open it. After a run, rebuild with scripts/county_data.py so the pages follow the answers.
"""
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import linkcheck  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / 'data' / 'county-links.json'
SHOWN = ('ok', 'refused')


def load():
    return json.loads(LEDGER.read_text(encoding='utf-8')) if LEDGER.exists() else {'checked_on': '', 'urls': {}}


def save(ledger):
    LEDGER.write_text(json.dumps(ledger, separators=(',', ':'), sort_keys=True) + '\n', encoding='utf-8')


def answer(checker, url):
    pile, why, _ = checker.check(url)
    if pile == 'ok':
        return 'ok'
    if pile == 'unchecked' and 'refused the robot' in why:
        return 'refused'
    return {'unchecked': 'unverified'}.get(pile, pile)


def check_one(checker, url):
    """An address as written, and, if a https address will not connect, the plain http one."""
    result = {url: answer(checker, url)}
    if url.startswith('https://') and result[url] not in SHOWN:
        plain = 'http://' + url[len('https://'):]
        result[plain] = answer(checker, plain)
    return result


def shard_urls():
    urls = set()
    for p in sorted((ROOT / 'assets' / 'us').glob('??.json')):
        shard = json.loads(p.read_text(encoding='utf-8'))
        for entry in shard['c'].values():
            for row in entry.get('health', []) + entry.get('healthNear', []):
                urls.add(row[6])
        urls.update(a[5] for a in shard['hu'].values())
        urls.update(d[5] for d in shard.get('sd', {}).values())
    urls.discard('')
    return sorted(urls)


def local_help_urls():
    import csv
    path = ROOT / 'data' / 'ymt' / 'local-help' / 'listings.csv'
    if not path.exists():
        return []
    with path.open(encoding='utf-8', newline='') as fh:
        return sorted({r['website'] for r in csv.DictReader(fh) if r['website']})


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    ledger = load()
    if '--shards' in sys.argv:
        urls = shard_urls()
    elif '--local-help' in sys.argv:
        urls = local_help_urls()
    elif args:
        import county_data
        urls = county_data.candidate_urls(Path(args[0]))
    else:
        sys.exit(__doc__)
    again = '--recheck' in sys.argv or '--shards' in sys.argv
    todo = [u for u in urls if again or u not in ledger['urls']]
    print(f'{len(urls)} addresses, {len(todo)} to check', flush=True)
    checker = linkcheck.Checker()
    done, started = 0, time.time()
    with ThreadPoolExecutor(max_workers=16) as pool:
        futures = [pool.submit(check_one, checker, u) for u in todo]
        for f in as_completed(futures):
            ledger['urls'].update(f.result())
            done += 1
            if done % 250 == 0:
                ledger['checked_on'] = date.today().isoformat()
                save(ledger)
                print(f'{done}/{len(todo)} in {int(time.time() - started)}s', flush=True)
    ledger['checked_on'] = date.today().isoformat()
    save(ledger)
    counts = {}
    for u in urls:
        status = ledger['urls'].get(u, 'not checked')
        counts[status] = counts.get(status, 0) + 1
    print(counts)


if __name__ == '__main__':
    main()
