#!/usr/bin/env python3
"""Request each listing's website; print a report and exit 1 if any fail."""
import json, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
data = json.loads((ROOT / 'data' / 'resources.json').read_text(encoding='utf-8'))
bad = []
for r in data['resources']:
    url = r.get('url')
    if not url:
        continue
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (OhioMom link check)'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status >= 400:
                bad.append((r, f'HTTP {resp.status}'))
    except Exception as exc:  # report every failure; a person decides what it means
        bad.append((r, str(exc)[:120]))
if bad:
    print('These listings did not load. Some sites block automated checks, so open each one before changing it.\n')
    for r, why in bad:
        print(f'- **{r["name"]}** (`{r["id"]}`): {r["url"]} — {why}')
    sys.exit(1)
print('All listing websites loaded.')
