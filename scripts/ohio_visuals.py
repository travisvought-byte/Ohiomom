#!/usr/bin/env python3
"""Pictures on the hand-kept OhioMom pages (added November 25, 2026 at the owner's request: "add some reasonable
visuals everywhere, at least for the US side").

The pages under ohio/ are hand-kept source, so this script writes each picture into its page between
<!-- visuals --> and <!-- /visuals --> markers, and --check fails when a page is out of step. What it draws:

- At a glance (housing, pregnancy and baby, kinship, Taking care of you, a loved one inside, Christmas): one tile per
  row or part of the page, with the line icon of the national site (assets/icons.svg), the row's own name and the count
  its own row shows, and a link that opens it. Read from the page itself, so the two can never disagree.
- Who to call (food and bills, parenting on my own): the page's own listings by name, each beside an icon.
- Ohio's counties (help.html and counties.html): the 88 counties from ohio/assets/map.json with the six that have their
  own page shaded. On counties.html it is a named picture with the six labeled; on help.html, whose words are
  translated, it is decoration beside the county tiles that say the same.
- A small drawing beside the heading of the pages that have no listings to count (Meet moms, Things to do, Talk to us,
  Tell us, Yoga, All resources): decoration only, drawn for this site.

Icons and decoration are hidden from screen readers; every word a picture carries is page text. The translated pages
(scripts/ohio_i18n.py) copy these blocks from the English page, so every word here is one the page already has, or
one with a translation in data/i18n/ (only "At a glance").

    python3 scripts/ohio_visuals.py           write the pictures into the pages
    python3 scripts/ohio_visuals.py --check   fail if a page is out of step
Then run python3 scripts/ohio_i18n.py, which copies them into the translated pages.
"""
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OHIO = ROOT / 'ohio'
SPRITE = ROOT / 'assets' / 'icons.svg'
BLOCK = re.compile(r'<!-- visuals -->.*?<!-- /visuals -->', re.S)
# The six counties with their own page under ohio/counties/, as the county tiles name them.
COUNTY_PAGES = ['Cuyahoga', 'Delaware', 'Franklin', 'Hamilton', 'Knox', 'Morrow']

# Icons for the rows and parts of each page, by the id of the row or part.
ROW_ICONS = {
    'help/housing.html': {'tonight': 'house', 'safe': 'lock', 'rent': 'key'},
    'help/pregnancy-baby.html': {'coverage-and-prenatal-care': 'clinic', 'support-at-home': 'house-heart',
                                 'food-diapers-and-a-safe-place-to-sleep': 'bottle'},
    'help/kinship.html': {'start-here': 'phone', 'money': 'coins', 'health': 'clinic', 'papers': 'court', 'support': 'people'},
    'wellbeing.html': {'someone-to-talk-to': 'cup', 'safe': 'phone'},
}
PART_ICONS = {
    'help/family-inside.html': {'touch': 'pin', 'kids': 'blocks', 'home': 'house', 'you': 'cup'},
    'holidays.html': {'help': 'gift', 'fun': 'star', 'you': 'cup'},
}
# Who to call: an icon for each listing, by its name on the page.
CARD_ICONS = {
    'help/bills.html': {'Ohio 211': 'phone', 'Help with heating and electric bills (HEAP)': 'house',
                        'Food, cash and Medicaid: one application': 'doc',
                        'WIC: food for pregnancy, babies and children under 5': 'bottle', 'Find a food bank near you': 'basket'},
    'help/single-parent.html': {'Help paying for child care': 'blocks', 'Child support: open or change a case': 'coins',
                                'Free legal help: custody, divorce, eviction, benefits': 'scales',
                                'Head Start near you in Ohio': 'book', 'National Parent &amp; Youth Helpline': 'phone'},
}

PALE = '#a8ddd3'
DEEP = '#12766f'
GROUND = (f'<path d="M0 94c26-12 52-14 80-5s54 7 80-5v28H0z" fill="{PALE}"/>'
          f'<path d="M0 102c34-9 62-7 92 0s46 5 68-2v14H0z" fill="{DEEP}" opacity=".85"/>')
HEART = '<path d="M{x} {y}s-5-3-5-6.4a2.8 2.8 0 0 1 5-1.7 2.8 2.8 0 0 1 5 1.7C{x2} {y2} {x} {y} {x} {y}z" fill="#cf2f5b"/>'


def heart(x, y):
    return HEART.format(x=x, y=y, x2=x + 5, y2=y - 3)


def art(inner):
    return (f'<svg class="art" viewBox="0 0 160 112" width="160" height="112" aria-hidden="true" focusable="false">'
            f'{inner}</svg>')


# Small drawings beside a heading. Decoration only.
MUGS = art('<circle cx="128" cy="26" r="13" fill="#ffe3a3"/><circle cx="128" cy="26" r="8.5" fill="#ffcb52"/>' + GROUND
           + '<path d="M38 56h30v24a9 9 0 0 1-9 9H47a9 9 0 0 1-9-9z" fill="#fff" stroke="#cf2f5b" stroke-width="2.4"/>'
           '<path d="M68 62h4a6 6 0 0 1 0 12h-4" fill="none" stroke="#cf2f5b" stroke-width="2.4"/>'
           '<path d="M88 56h30v24a9 9 0 0 1-9 9H97a9 9 0 0 1-9-9z" fill="#fff" stroke="#12766f" stroke-width="2.4"/>'
           '<path d="M88 62h-4a6 6 0 0 0 0 12h4" fill="none" stroke="#12766f" stroke-width="2.4"/>'
           '<path d="M49 47c-2-3 2-5 0-8M57 47c-2-3 2-5 0-8M99 47c-2-3 2-5 0-8M107 47c-2-3 2-5 0-8" fill="none" '
           'stroke="#655c78" stroke-width="2" stroke-linecap="round"/>' + heart(78, 36))
BUNTING = art('<circle cx="132" cy="62" r="13" fill="#ffe3a3"/><circle cx="132" cy="62" r="8.5" fill="#ffcb52"/>' + GROUND
              + '<path d="M4 14q76 26 152 0" fill="none" stroke="#655c78" stroke-width="1.6"/>'
              '<path d="M14 18l6 13 6-10zM40 24l5 13 7-11zM68 27l4 13 7-12zM96 26l3 13 8-12zM124 22l2 13 8-11z" '
              'fill="#cf2f5b"/><path d="M27 21l5 13 7-11zM54 26l4 13 7-12zM82 27l4 13 7-12zM110 24l3 13 8-11z" fill="#ffcb52"/>'
              '<path d="M44 86V68M44 68c-7-1-10-7-9-13 6 1 10 6 9 13zM44 72c6-1 9-6 8-11-6 1-9 6-8 11z" fill="#3f9b88" '
              'stroke="#3f9b88" stroke-width="1.6" stroke-linejoin="round"/>')
BUBBLES = art('<circle cx="132" cy="24" r="12" fill="#ffe3a3"/><circle cx="132" cy="24" r="7.5" fill="#ffcb52"/>' + GROUND
              + '<path d="M22 30h56a8 8 0 0 1 8 8v20a8 8 0 0 1-8 8H44l-12 10v-10h-10a8 8 0 0 1-8-8V38a8 8 0 0 1 8-8z" '
              'fill="#fff" stroke="#cf2f5b" stroke-width="2.4" stroke-linejoin="round"/>'
              '<path d="M84 52h48a8 8 0 0 1 8 8v16a8 8 0 0 1-8 8h-6v9l-11-9H84a8 8 0 0 1-8-8V60a8 8 0 0 1 8-8z" '
              'fill="#fff" stroke="#12766f" stroke-width="2.4" stroke-linejoin="round"/>'
              '<circle cx="95" cy="68" r="3" fill="#12766f"/><circle cx="108" cy="68" r="3" fill="#12766f"/>'
              '<circle cx="121" cy="68" r="3" fill="#12766f"/>' + heart(50, 53))
MAT = art('<circle cx="80" cy="56" r="26" fill="#ffe3a3"/><circle cx="80" cy="56" r="17" fill="#ffcb52"/>' + GROUND
          + '<rect x="30" y="80" width="62" height="9" rx="4.5" fill="#f2a2b6" stroke="#cf2f5b" stroke-width="2"/>'
          '<circle cx="92" cy="84.5" r="7.5" fill="#f2a2b6" stroke="#cf2f5b" stroke-width="2"/>'
          '<circle cx="92" cy="84.5" r="3" fill="none" stroke="#cf2f5b" stroke-width="1.6"/>'
          '<path d="M122 90c-1-8 1-14 5-18l1.4 1.2c-3.6 4-5 9-4.4 16.8z" fill="#3f9b88"/>'
          '<path d="M127.6 72.3c1.2-5 5.2-7.6 10.4-7.3-.6 5.2-4.6 8.3-10.4 7.3z" fill="#3f9b88"/>'
          '<path d="M124.8 80.6c-4.3-3.7-9.4-3.9-12.8-1.2 3.2 3.6 8.4 4 12.8 1.2z" fill="#3f9b88"/>' + heart(80, 25))
LENS = art('<circle cx="134" cy="22" r="11" fill="#ffe3a3"/><circle cx="134" cy="22" r="7" fill="#ffcb52"/>' + GROUND
           + '<rect x="24" y="40" width="58" height="42" rx="6" fill="#fff" stroke="#655c78" stroke-width="2"/>'
           '<rect x="34" y="30" width="58" height="42" rx="6" fill="#fff" stroke="#12766f" stroke-width="2.4"/>'
           '<path d="M43 42h34M43 51h40M43 60h26" stroke="#a8ddd3" stroke-width="3" stroke-linecap="round"/>'
           '<circle cx="100" cy="60" r="15" fill="#fff" fill-opacity=".6" stroke="#cf2f5b" stroke-width="4"/>'
           '<path d="M111 71l14 14" stroke="#cf2f5b" stroke-width="6" stroke-linecap="round"/>')
ART = {'connect.html': MUGS, 'events.html': BUNTING, 'listen.html': BUBBLES, 'report.html': BUBBLES,
       'yoga.html': MAT, 'all.html': LENS}


def icon(name, page):
    """A line icon from the national site's sprite, hidden from screen readers: the words beside it say the same."""
    if f'<symbol id="{name}"' not in SPRITE.read_text(encoding='utf-8'):
        sys.exit(f'scripts/ohio_visuals.py: no icon "{name}" in assets/icons.svg')
    up = '../' * (page.count('/') + 1)
    return f'<svg class="gi" aria-hidden="true" focusable="false" width="24" height="24"><use href="{up}assets/icons.svg#{name}"/></svg>'


def mark(inner):
    return f'<!-- visuals -->{inner}<!-- /visuals -->'


def glance_rows(page, text):
    """One tile per row: its icon, its name and the count the row shows ("7 options"), a link that opens it."""
    icons = ROW_ICONS[page]
    items = []
    for rid, summary in re.findall(r'<details class="need(?: urgent)?" id="([a-z-]+)"><summary>(.*?)</summary>', text, re.S):
        if rid not in icons:
            sys.exit(f'scripts/ohio_visuals.py: {page}: no icon for the row "{rid}"')
        name = re.search(r'<h2>(.*?)</h2>', summary).group(1)
        count = re.search(r'<span class="ncount">([^<]+)</span>', summary)
        small = f' <small>{count.group(1)}</small>' if count else ''
        items.append(f'<li><a href="#{rid}">{icon(icons[rid], page)}<span>{name}{small}</span></a></li>')
    return f'<nav class="glance" aria-label="At a glance"><ul>{"".join(items)}</ul></nav>'


def glance_parts(page, text):
    """One tile per part of the page (a heading with an id), with the number of listings under it."""
    icons = PART_ICONS[page]
    items = []
    parts = re.split(r'(?=<h2 id=")', text)
    for part in parts[1:]:
        pid, name = re.match(r'<h2 id="([a-z-]+)">(.*?)</h2>', part).groups()
        if pid not in icons:
            continue
        # Only the listings written into the page count; events the page's script draws are left out.
        n = part.split('</section>', 1)[0].count('<article class="card')
        small = f' <small>{n} listing{"s" if n != 1 else ""}</small>' if n else ''
        items.append(f'<li><a href="#{pid}">{icon(icons[pid], page)}<span>{name}{small}</span></a></li>')
    missing = set(icons) - {re.match(r'<h2 id="([a-z-]+)"', p).group(1) for p in parts[1:]}
    if missing:
        sys.exit(f'scripts/ohio_visuals.py: {page}: no heading with the id {", ".join(sorted(missing))}')
    return f'<nav class="glance" aria-label="At a glance"><ul>{"".join(items)}</ul></nav>'


def who_to_call(page, text):
    """The page's listings by name, each beside an icon, under the page's own "Who to call"."""
    icons = CARD_ICONS[page]
    names = re.findall(r'<article class="card[^"]*"[^>]*><h3>(.*?)</h3>', text)
    if sorted(names) != sorted(icons):
        sys.exit(f'scripts/ohio_visuals.py: {page}: the listings changed; give each one an icon in CARD_ICONS')
    items = ''.join(f'<li><span class="gtile">{icon(icons[n], page)}<span>{n}</span></span></li>' for n in names)
    return f'<figure class="glance"><figcaption>Who to call</figcaption><ul>{items}</ul></figure>'


def ohio_map(page, named):
    """Ohio's 88 counties, the six with their own page shaded. named: a picture with a name and labels (counties.html);
    otherwise decoration beside the county tiles (help.html, whose words are translated)."""
    m = json.loads((OHIO / 'assets' / 'map.json').read_text(encoding='utf-8'))
    shapes = m['c']
    if set(COUNTY_PAGES) - set(shapes) or len(shapes) != 88:
        sys.exit('scripts/ohio_visuals.py: ohio/assets/map.json does not hold the 88 counties')

    def short(d):  # one decimal is more than a picture this size needs
        return re.sub(r'(\d+\.\d)\d+', r'\1', d)
    rest = ''.join(short(c['d']) for name, c in sorted(shapes.items()) if name not in COUNTY_PAGES)
    own = ''.join(short(shapes[name]['d']) for name in COUNTY_PAGES)
    body = (f'<path d="{rest}" fill="#fff" stroke="#9a8775" stroke-width="1.2" stroke-linejoin="round"/>'
            f'<path class="own" d="{own}" fill="#12766f" stroke="#0b4f4a" stroke-width="1.6" stroke-linejoin="round"/>')
    view = f'0 0 {m["w"]} {m["h"]}'
    if not named:
        return (f'<div class="ohmap"><svg viewBox="{view}" width="{m["w"]}" height="{m["h"]}" aria-hidden="true" focusable="false">'
                f'{body}</svg></div>')
    def label(n):  # a name near the state line starts at the edge instead of running off it
        x, y = shapes[n]['x'], shapes[n]['y'] + 5
        return (f'<text x="4" y="{y}">{n}</text>' if x < 60 else f'<text x="{x}" y="{y}" text-anchor="middle">{n}</text>')
    labels = ''.join(label(n) for n in COUNTY_PAGES)
    listed = ', '.join(COUNTY_PAGES[:-1]) + ' and ' + COUNTY_PAGES[-1]
    return (f'<figure class="ohmap named"><svg viewBox="{view}" width="{m["w"]}" height="{m["h"]}" role="img" '
            f'aria-labelledby="ohmap-t ohmap-d"><title id="ohmap-t">Map of Ohio\'s 88 counties</title>'
            f'<desc id="ohmap-d">The six counties with their own page are shaded: {listed}.</desc>{body}'
            f'<g class="lbl" font-size="19" font-weight="700" fill="#2b2140" stroke="#fff" stroke-width="5" '
            f'stroke-linejoin="round" paint-order="stroke">{labels}</g></svg>'
            f'<figcaption>The six shaded counties have their own page: {listed}.</figcaption></figure>')


def hero_end(text):
    """Where the end of the page's hero is: just before the first </div></section> after <section class="hero."""
    start = text.index('<section class="hero')
    return text.index('</div></section>', start)


def after(anchor):
    def where(text):
        return text.index(anchor) + len(anchor)
    return where


def hero_start(text):
    start = text.index('<section class="hero')
    anchor = '<div class="wrap">'
    return text.index(anchor, start) + len(anchor)


COUNTY_P = '<h2>Your county</h2><p>Most help in Ohio is run by your county. Each county page lists the local offices and phone numbers.</p>'
COUNTIES_HERO = '<section class="hero slim"><div class="wrap"><h1>Find your county</h1>'

# page: [(where it goes, what it draws)]. Each block is written fresh from the page as it stands without its blocks.
PLAN = {
    'help.html': [(after(COUNTY_P), lambda p, t: ohio_map(p, False))],
    'counties.html': [(hero_end, lambda p, t: ohio_map(p, True))],
    'help/housing.html': [(hero_end, glance_rows)],
    'help/pregnancy-baby.html': [(hero_end, glance_rows)],
    'help/kinship.html': [(hero_end, glance_rows)],
    'wellbeing.html': [(hero_end, glance_rows)],
    'help/family-inside.html': [(hero_end, glance_parts)],
    'holidays.html': [(hero_end, glance_parts)],
    'help/bills.html': [(hero_end, who_to_call)],
    'help/single-parent.html': [(hero_end, who_to_call)],
    **{p: [(hero_start, (lambda a: lambda p, t: a)(a))] for p, a in ART.items()},
}


def render(page):
    text = BLOCK.sub('', (OHIO / page).read_text(encoding='utf-8'))
    blocks = [(where(text), make(page, text)) for where, make in PLAN[page]]
    for at, block in sorted(blocks, reverse=True):
        text = text[:at] + mark(block) + text[at:]
    return text


def main():
    check = '--check' in sys.argv[1:]
    stale = []
    for page in PLAN:
        path = OHIO / page
        new = render(page)
        if path.read_text(encoding='utf-8') != new:
            if check:
                stale.append(page)
            else:
                path.write_text(new, encoding='utf-8')
    if stale:
        sys.exit('Out of date (run python3 scripts/ohio_visuals.py, then scripts/ohio_i18n.py): ' + ', '.join(stale))
    print(f'OK: {len(PLAN)} OhioMom pages carry their pictures' if check else f'Wrote the pictures into {len(PLAN)} OhioMom pages')


if __name__ == '__main__':
    main()
