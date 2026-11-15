#!/usr/bin/env python3
"""Check the data before anything is published. Exit 1 on any problem."""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, __import__('os').path.dirname(__file__))
import ymt_lib as lib  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]


def check_url(rid, u, errors):
    if not isinstance(u, str) or not u.startswith('https://'):
        errors.append(f'{rid}: link must be https: {u}')


def main():
    data = lib.load()
    errors, seen = [], set()
    sections = {s['id'] for s in data['sections']}
    site = data['site']
    for key in ('name', 'domain', 'founder', 'corrections_email', 'reviewed_on', 'ohio_path', 'ohio_yoga_path'):
        if not site.get(key):
            errors.append(f'site: missing {key}')
    for key in ('ohio_path', 'ohio_yoga_path'):
        if site.get(key) and not (ROOT / site[key]).is_file():
            errors.append(f'site: {key} {site[key]} does not exist')

    states = data['states']
    if len(states) != 51:
        errors.append(f'expected 50 states plus DC, found {len(states)}')
    abbrs = [s['abbr'] for s in states]
    slugs = [s['slug'] for s in states]
    if len(set(abbrs)) != len(abbrs) or len(set(slugs)) != len(slugs):
        errors.append('states: duplicate abbr or slug')
    for s in states:
        for k in ('early_intervention', 'parent_center', 'protection_advocacy'):
            e = s.get(k)
            if e:
                check_url(f"{s['abbr']}.{k}", e.get('url'), errors)
                if e.get('phone') and not lib.PHONE.match(e['phone']):
                    errors.append(f"{s['abbr']}.{k}: bad phone {e['phone']}")
        if s.get('local_site'):
            path = s['local_site'].get('path', '')
            if not (ROOT / path).is_file():
                errors.append(f"{s['abbr']}.local_site: {path} does not exist")

    records = lib.all_records(data)
    for r in records:
        rid = r.get('id', '?')
        for key in lib.REQUIRED:
            if not r.get(key):
                errors.append(f'{rid}: missing {key}')
        if rid in seen:
            errors.append(f'{rid}: duplicate id')
        seen.add(rid)
        if r.get('section') not in sections:
            errors.append(f'{rid}: unknown section {r.get("section")}')
        for a in r.get('also', []):
            if a not in sections:
                errors.append(f'{rid}: unknown also-section {a}')
        if r.get('phone') and not lib.PHONE.match(r['phone']):
            errors.append(f'{rid}: phone must be NNN or NNN-NNN-NNNN')
        if r.get('urgent') and not r.get('phone'):
            errors.append(f'{rid}: urgent listings need a phone number')
        if not r.get('url'):
            errors.append(f'{rid}: missing url')
        check_url(rid, r.get('url'), errors)
        for u in r.get('sources', []):
            check_url(rid, u, errors)
        for link in r.get('links', []):
            check_url(rid, link.get('url'), errors)
            if not link.get('label'):
                errors.append(f'{rid}: link missing label')
        for field in ('name', 'org', 'what', 'how'):
            v = r.get(field, '')
            if '{' in v or '}' in v:
                errors.append(f'{rid}: unfilled placeholder in {field}')
        try:
            d = date.fromisoformat(r.get('reviewed_on', ''))
            if d > date.today():
                errors.append(f'{rid}: reviewed_on is in the future')
        except ValueError:
            errors.append(f'{rid}: bad reviewed_on')

    if errors:
        print('\n'.join(errors))
        sys.exit(1)
    print(f'OK: {len(records)} listings ({len(data["resources"])} national, '
          f'{len(records) - len(data["resources"])} state) in {len(sections)} sections, {len(states)} states')


if __name__ == '__main__':
    main()
