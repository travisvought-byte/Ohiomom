"""Shared loading and record-building for the national Yoga Mom Talk pages.

All site content comes from data/*.json. Nothing here fetches anything.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data' / 'ymt'

PHONE = re.compile(r'^(\d{3}|\d{3}-\d{3}-\d{4})$')
REQUIRED = ('id', 'section', 'scope', 'name', 'org', 'what', 'how', 'sources', 'reviewed_on')
MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July',
          'August', 'September', 'October', 'November', 'December']


def read_json(name):
    return json.loads((DATA / name).read_text(encoding='utf-8'))


def load():
    res = read_json('resources.json')
    states = read_json('states.json')
    tmpl = read_json('state-templates.json')
    return {
        'site': res['site'],
        'sections': res['sections'],
        'attribution': res.get('attribution', ''),
        'resources': res['resources'],
        'states': states['states'],
        'states_meta': states,
        'templates': tmpl['templates'],
    }


def pretty_date(iso):
    y, m, d = (int(x) for x in iso.split('-'))
    return f'{MONTHS[m - 1]} {d}, {y}'


def _fill(text, state):
    return (text.replace('{state}', state['name'])
                .replace('{slug}', state['slug'])
                .replace('{snap_slug}', state['snap_slug']))


def state_records(state, data):
    """Every card shown on one state's page, in display order within a section."""
    meta = data['states_meta']
    rev = data['site']['reviewed_on']
    out = []
    for t in data['templates']:
        r = {k: (_fill(v, state) if isinstance(v, str) else v) for k, v in t.items()}
        r['id'] = f"{state['abbr'].lower()}-{t['id']}"
        r['scope'] = state['abbr']
        r['reviewed_on'] = rev
        out.append(r)
    src = meta['special_needs_sources']
    srev = meta['reviewed_on']

    def special(kind, entry, org, what, how):
        r = {'id': f"{state['abbr'].lower()}-{kind}", 'section': 'kids-differently',
             'scope': state['abbr'], 'name': entry['name'], 'org': org, 'what': what,
             'how': how, 'sources': src, 'reviewed_on': srev}
        # A program's own website can go away while its phone line still works.
        # Such an entry is listed by phone alone, with no Website button.
        if entry.get('url'):
            r['url'] = entry['url']
        if entry.get('phone'):
            r['phone'] = entry['phone']
        return r

    ei = state.get('early_intervention')
    if ei:
        out.append(special('ei', ei, f"{state['name']} early intervention program (birth to age 3)",
                           "Free early intervention for children under 3 who are behind or have a disability. You can call yourself. You do not need a doctor's note.",
                           "Call and ask for a free evaluation. If your child is 3 or older, call your public school district instead."))
    pc = state.get('parent_center')
    if pc:
        out.append(special('pti', pc, 'Parent Training and Information Center',
                           "A free parent center for families of children with any disability, from birth to age 26. Staff help with school plans, meetings and your rights.",
                           "Call before your next school meeting."))
    else:
        out.append({'id': f"{state['abbr'].lower()}-pti", 'section': 'kids-differently',
                    'scope': state['abbr'], 'name': f"Parent centers in {state['name']}",
                    'org': 'Center for Parent Information and Resources',
                    'what': f"{state['name']} has several regional parent centers that help families of children with any disability with school plans, meetings and your rights.",
                    'how': f"Open the national map and choose {state['name']} to find the center that serves your area.",
                    'url': 'https://www.parentcenterhub.org/find-your-center/', 'sources': src,
                    'reviewed_on': srev})
    pa = state.get('protection_advocacy')
    if pa:
        out.append(special('pa', pa, 'Protection and Advocacy agency (disability rights)',
                           "The federally funded disability rights agency for your state. Call if your child with a disability is being denied services, education or fair treatment.",
                           "Call or open the website and ask for help for your child."))
    return out


def all_records(data):
    recs = list(data['resources'])
    for s in data['states']:
        recs.extend(state_records(s, data))
    return recs


def tel_href(phone):
    return 'tel:' + (phone if len(phone) == 3 else '+1' + phone.replace('-', ''))
