#!/usr/bin/env python3
"""Check the data before anything is published. Exit 1 on any problem."""
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, __import__('os').path.dirname(__file__))
import ads  # noqa: E402
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
                if e.get('url'):
                    check_url(f"{s['abbr']}.{k}", e.get('url'), errors)
                elif not e.get('phone'):
                    errors.append(f"{s['abbr']}.{k}: needs a website or a phone number")
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
        if r.get('url'):
            check_url(rid, r.get('url'), errors)
        elif not r.get('phone'):
            errors.append(f'{rid}: needs a website or a phone number')
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

    # Outside the U.S. (data/ymt/world.json): each listing needs a source, a date, and digits that a phone can dial.
    world = data.get('world', {})
    dial = re.compile(r'^\+?\d{3,15}$')
    emergency_dial = re.compile(r'^\d{2,15}$')  # some countries' police number is two digits (Morocco: 19)
    codes = set()
    for c in world.get('countries', []):
        for key in ('code', 'slug', 'name', 'flag'):
            if not c.get(key):
                errors.append(f'world {c.get("code", "?")}: missing {key}')
        if c.get('code') in codes:
            errors.append(f'world {c["code"]}: duplicate country')
        codes.add(c.get('code'))
        # The language the country page shows the day's affirmation in (en for English only). A language the affirmations
        # are not in yet (data/affirmations-i18n/) keeps the page in English until they are.
        if 'lang' in c and not (isinstance(c['lang'], str) and re.match(r'^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$', c['lang'])):
            errors.append(f'world {c.get("code")}: lang is a language tag such as en, es or zh-Hant')
        # A country that shares its name with a U.S. state (Georgia) names the state, and its pages link to each other.
        bare = re.sub(r'\s*\(.*\)$', '', c.get('name', ''))
        if bare in {s['name'] for s in states} and ('us_state' not in c or bare == c.get('name')):
            errors.append(f'world {c.get("code")}: {bare} is also a U.S. state: name it "{bare} (the country)" and set us_state')
        if 'us_state' in c and c['us_state'] not in {s['abbr'] for s in states}:
            errors.append(f'world {c.get("code")}: us_state is the two letters of a U.S. state')
        if 'us_state' in c and c.get('slug') in {s['slug'] for s in states}:
            errors.append(f'world {c.get("code")}: slug {c["slug"]} is also a state\'s slug')
        e = c.get('emergency') or {}
        if not emergency_dial.match(e.get('number', '')) or not e.get('label'):
            errors.append(f'world {c.get("code")}: emergency needs a number and a label')
        check_url(f'world {c.get("code")} emergency', e.get('source'), errors)
    listings = list(world.get('worldwide', [])) + [dict(r, scope=c['code']) for c in world.get('countries', []) for r in c['resources']]
    for r in listings:
        rid = r.get('id', '?')
        for key in lib.REQUIRED:
            if not r.get(key):
                errors.append(f'{rid}: missing {key}')
        if rid in seen:
            errors.append(f'{rid}: duplicate id')
        seen.add(rid)
        if r.get('section') not in sections or any(a not in sections for a in r.get('also', [])):
            errors.append(f'{rid}: unknown section')
        if r.get('phone') and not dial.match(r.get('dial', '')):
            errors.append(f'{rid}: a phone number needs "dial", the digits to call')
        if r.get('urgent') and not r.get('phone'):
            errors.append(f'{rid}: urgent listings need a phone number')
        if not r.get('url') and not r.get('phone'):
            errors.append(f'{rid}: needs a website or a phone number')
        for u in [r.get('url')] * bool(r.get('url')) + r.get('sources', []):
            check_url(rid, u, errors)
        try:
            if date.fromisoformat(r.get('reviewed_on', '')) > date.today():
                errors.append(f'{rid}: reviewed_on is in the future')
        except ValueError:
            errors.append(f'{rid}: bad reviewed_on')
    errors += [f'data/ads.json: {e}' for e in ads.check(data['ads'])]
    errors += ads.check_client(data.get('adsense_client', ''))
    on = ads.today()
    for ad in data['ads']:
        if isinstance(ad, dict) and ad.get('end') and str(ad['end']) < on:
            print(f"note: the ad for {ad.get('sponsor')} ended on {ad['end']}; take it out of data/ads.json")

    # Help for moms and babies: the mined table, its county index and its source registry (scripts/local_help.py).
    import local_help  # noqa: E402
    errors += [f'local help: {e}' for e in local_help.check()]

    if errors:
        print('\n'.join(errors))
        sys.exit(1)
    print(f'OK: {len(records)} listings ({len(data["resources"])} national, '
          f'{len(records) - len(data["resources"])} state) in {len(sections)} sections, {len(states)} states')


if __name__ == '__main__':
    main()
