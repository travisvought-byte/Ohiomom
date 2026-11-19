#!/usr/bin/env python3
"""Write the OhioMom events and groups into the pages themselves.

The Ohio pages fill their lists in the browser from ohio/assets/data.json. A
search engine that does not run the page's script, a link preview, or a
visitor with scripts turned off would see empty lists. This writes the same
lists into the HTML, between marker comments, so the page reads complete
without the script. When the script runs it replaces them as before, filtered
to the visitor's area and to today's date.

The markup below mirrors the card and event templates in ohio/assets/site.js
(functions k, E and F1 there). Change both together.

    python3 scripts/prerender_ohio.py           write the lists, as of today
    python3 scripts/prerender_ohio.py --check   fail if a page is out of step
                                                with data.json (uses the date
                                                already written in the page)
"""
import datetime
import html
import json
import re
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'ohio' / 'assets' / 'data.json'
MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
ABBREV = re.compile(r'(U\.S\.|a\.m\.|p\.m\.|e\.g\.|i\.e\.|St\.|Dr\.|Mr\.|Mrs\.|Ms\.|vs\.|No\.|Inc\.)$')

# page -> list of (container opening tag, block name)
TARGETS = {
    'ohio/events.html': [
        ('<div class="events" data-events="all">', 'events-all'),
        ('<div class="groups" data-groups="calendar">', 'groups-calendar'),
    ],
    'ohio/connect.html': [
        ('<div class="groups" data-groups="sections">', 'groups-sections'),
    ],
    'ohio/holidays.html': [
        ('<div class="events" data-events="holiday">', 'events-holiday'),
    ],
}


def esc(value):
    """Same as the a() helper in site.js: &, <, > and double quotes; single quotes stay."""
    s = '' if value is None else str(value)
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def short_date(iso):
    y, m, d = iso.split('-')
    return f'{MONTHS[int(m) - 1]} {int(d)}'


def first_sentence(text):
    """Split off the first sentence, as F1 in site.js does."""
    for m in re.finditer(r'[.!?]["”)]?\s+', text):
        end = m.end()
        head = text[:end].rstrip()
        if ABBREV.search(head):
            continue
        nxt = text[end:end + 1]
        if nxt and ((nxt != nxt.lower() and nxt == nxt.upper()) or nxt.isdigit() or nxt in '"“('):
            return head, text[end:].strip()
    return text.strip(), ''


class Site:
    def __init__(self, data):
        self.d = data
        self.regions = {r['id']: r for r in data['regions']}

    def region_of(self, county):
        return self.regions[self.d['counties'][county][0]]

    def event(self, e, today):
        started = e['start'] <= today
        last = e.get('end') or e['start']
        if started and last != e['start']:
            date = f'<span class="date now"><b>Now</b><i>to {short_date(last)}</i></span>'
        elif started:
            date = '<span class="date now"><b>Today</b></span>'
        else:
            mon, day = short_date(e['start']).split(' ')
            date = f'<span class="date"><b>{day}</b><i>{mon}</i></span>'
        span = f"{short_date(e['start'])} to {short_date(last)}. " if last != e['start'] else ''
        r = self.region_of(e['county'])
        cost = '<br>' + esc(e['cost']) if e.get('cost') else ''
        return (
            f'<article class="event">{date}<div><p class="tags">'
            f'<span class="tag k-{esc(e["kind"])}">{esc(self.d["eventKinds"][e["kind"]])}</span>'
            f'<span class="tag" style="background:{r["color"]}">{esc(r["label"])}</span></p>'
            f'<h3>{esc(e["title"])}</h3><p class="where">{esc(e["city"])} · {esc(e["county"])} County</p>'
            f'<details class="more"><summary>When, where and cost<span class="sr">: {esc(e["title"])}</span></summary>'
            f'<p>{esc(e["blurb"])}</p><p class="when">{esc(span + e["when"])}<br>{esc(e["place"])}{cost}</p>'
            f'<p class="actions"><a class="btn" href="{esc(e["url"])}" rel="noopener noreferrer">Details</a>'
            f'<a class="src" href="{esc(e["source"])}" rel="noopener noreferrer">Source, checked {short_date(e["checked"])}</a></p>'
            f'</details></div></article>'
        )

    def upcoming(self, today, holiday=False):
        live = [e for e in self.d['events'] if (e.get('end') or e['start']) >= today and (e.get('holiday') or not holiday)]
        return sorted(live, key=lambda e: (max(e['start'], today), 1 if e.get('end') else 0))

    def group(self, g):
        r = None if g['region'] == 'all' else self.regions[g['region']]
        short, rest = first_sentence(str(g.get('what') or ''))
        style = f' style="background:{r["color"]}"' if r else ''
        call = ''
        if g.get('phone'):
            call = f'<a class="btn call" href="tel:{re.sub(r"[^0-9]", "", g["phone"])}">Call {esc(g["phone"])}</a>'
            if g.get('phone_label'):
                call += f'<span class="note">{esc(g["phone_label"])}</span>'
        more = f'<p>{esc(rest)}</p>' if rest else ''
        return (
            f'<article class="card group"><p class="tags"><span class="tag"{style}>{esc(r["label"] if r else "All of Ohio")}</span></p>'
            f'<h3>{esc(g["name"])}</h3><p class="short">{esc(short)}</p>'
            f'<p class="actions">{call}<a class="btn" href="{esc(g["url"])}" rel="noopener noreferrer">Website</a></p>'
            f'<details class="more"><summary>More about this<span class="sr">: {esc(g["name"])}</span></summary>{more}'
            f'<p><strong>Next step:</strong> {esc(g["how"])}</p><p class="meta">Checked {short_date(g["checked"])}</p></details></article>'
        )

    def groups_of(self, kind):
        # Statewide listings last, as in L() with no area chosen.
        return sorted((g for g in self.d['groups'] if g['kind'] == kind), key=lambda g: g['region'] == 'all')

    def block(self, name, today):
        if name == 'events-all':
            events = self.upcoming(today)
            if not events:
                return '<p class="pending">Nothing listed for Ohio right now. <a href="report.html">Tell us about an event</a>.</p>'
            return ''.join(self.event(e, today) for e in events)
        if name == 'events-holiday':
            events = self.upcoming(today, holiday=True)
            if not events:
                return ('<p class="pending">Nothing listed for Ohio right now. <a href="report.html">Tell us about an event</a>, '
                        'or <a href="events.html">see all of Ohio</a>.</p>')
            return ''.join(self.event(e, today) for e in events)
        if name == 'groups-calendar':
            cal = [g for g in self.groups_of('calendar') if g['region'] != 'all']
            return '<div class="cards">' + ''.join(self.group(g) for g in cal) + '</div>'
        if name == 'groups-sections':
            out = ''
            for kind, label in self.d['groupKinds'].items():
                rows = self.groups_of(kind)
                count = f'{len(rows)} option' + ('' if len(rows) == 1 else 's')
                out += (f'<details class="need"><summary><h2>{esc(label)}</h2><span class="ncount">{count}</span></summary>'
                        f'<div class="cards">' + ''.join(self.group(g) for g in rows) + '</div></details>')
            return out
        raise KeyError(name)


MARK = re.compile(r'<!--prerender:(?P<name>[a-z-]+) as of (?P<date>\d{4}-\d{2}-\d{2})-->.*?<!--/prerender-->', re.S)


def render_page(text, blocks, site, today):
    for opening, name in blocks:
        i = text.find(opening)
        if i < 0 or text.count(opening) != 1:
            raise SystemExit(f'{name}: expected one {opening!r}')
        start = i + len(opening)
        m = MARK.match(text, start)
        end = m.end() if m else start
        if not m and not text.startswith('</div>', start):
            raise SystemExit(f'{name}: the container is not empty and has no prerender marker')
        filled = f'<!--prerender:{name} as of {today}-->{site.block(name, today)}<!--/prerender-->'
        text = text[:start] + filled + text[end:]
    return text


def written_date(text):
    m = MARK.search(text)
    return m.group('date') if m else None


def main():
    check = '--check' in sys.argv
    site = Site(json.loads(DATA.read_text()))
    today = datetime.datetime.now(ZoneInfo('America/New_York')).date().isoformat()
    stale = []
    for rel, blocks in TARGETS.items():
        path = ROOT / rel
        text = path.read_text()
        if check:
            as_of = written_date(text)
            if not as_of:
                stale.append(f'{rel}: lists not written into the page')
                continue
            if render_page(text, blocks, site, as_of) != text:
                stale.append(f'{rel}: lists differ from ohio/assets/data.json')
        else:
            path.write_text(render_page(text, blocks, site, today))
    if stale:
        raise SystemExit('Run python3 scripts/prerender_ohio.py\n' + '\n'.join(stale))
    print('OhioMom lists are written into the pages' if not check else 'OhioMom lists in the pages match the data')


if __name__ == '__main__':
    main()
