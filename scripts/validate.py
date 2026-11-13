#!/usr/bin/env python3
"""Check data/resources.json before it is published."""
import json, re, sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ('id', 'section', 'scope', 'name', 'org', 'what', 'how', 'sources', 'reviewed_on')
PHONE = re.compile(r'^(\d{3}|\d{3}-\d{3}-\d{4})$')


def main():
    data = json.loads((ROOT / 'data' / 'resources.json').read_text(encoding='utf-8'))
    sections = {s['id'] for s in data['sections']}
    errors, seen = [], set()
    for r in data['resources']:
        rid = r.get('id', '?')
        for key in REQUIRED:
            if not r.get(key):
                errors.append(f'{rid}: missing {key}')
        if rid in seen:
            errors.append(f'{rid}: duplicate id')
        seen.add(rid)
        if r.get('section') not in sections:
            errors.append(f'{rid}: unknown section')
        if r.get('phone') and not PHONE.match(r['phone']):
            errors.append(f'{rid}: phone must be NNN or NNN-NNN-NNNN')
        for u in [r.get('url')] + list(r.get('sources', [])):
            if u and not u.startswith('https://'):
                errors.append(f'{rid}: link must be https: {u}')
        try:
            if date.fromisoformat(r.get('reviewed_on', '')) > date.today():
                errors.append(f'{rid}: reviewed_on is in the future')
        except ValueError:
            errors.append(f'{rid}: bad reviewed_on')
    if errors:
        print('\n'.join(errors))
        sys.exit(1)
    print(f'OK: {len(data["resources"])} resources in {len(sections)} sections')


if __name__ == '__main__':
    main()
