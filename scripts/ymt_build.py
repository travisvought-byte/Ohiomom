#!/usr/bin/env python3
"""Build every page from data/*.json.

    python3 scripts/build.py          write the site
    python3 scripts/build.py --check  fail if the files on disk differ from the data

Edit data or this script, never the built pages. The Ohio pages under ohio/ are separate source, not built here.
"""
import json
import re
import sys
import urllib.parse
from html import escape as esc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import help_now  # noqa: E402
import home_extras as extras  # noqa: E402
import ymt_lib as lib  # noqa: E402
from us_geo import STATE_FIPS  # noqa: E402

ROOT = lib.ROOT
EXIT_URL = 'https://www.google.com/search?q=weather'
NAV = [('help.html', 'Find help'), ('connect.html', 'Meet moms'), ('states.html', 'By state'), ('county.html', 'Near you')]
FOOT = [('help.html', 'Find help'), ('connect.html', 'Meet moms'), ('states.html', 'By state'),
        ('about.html', 'About'), ('report.html', 'Report a problem')]
TILES = [
    ('t1', '🤝', 'Meet other moms', 'Groups and communities near you and online.', 'connect.html'),
    ('t7', '🏠', 'Housing and shelter', "A place to stay tonight, women's shelters, help with rent.", 'help.html#housing'),
    ('t2', '🧺', 'A hand with food or bills', 'SNAP, WIC, energy bills and food banks.', 'help.html#food-bills'),
    ('t3', '🍼', "I'm pregnant or have a new baby", 'Health coverage, nursing help, diapers, safe sleep.', 'help.html#pregnancy-baby'),
    ('t4', '🧩', 'My child learns or grows differently', 'Autism, ADHD, delays, school help and other parents.', 'help.html#kids-differently'),
    ('t5', '💛', 'Parenting on my own', 'Child care, Head Start, child support and legal help.', 'help.html#single-parent'),
    ('t6', '☕', 'Take care of me', 'Someone to talk to on the hard days.', 'help.html#take-care'),
    ('t8', '🔎', 'See everything', 'Every listing in one place, with a search box.', 'help.html#everything'),
]
# ohiomom.org is one way into this site: its home page goes straight to the Ohio landing page.
OHIO_REDIRECT = ('\n<script>if(/(^|\\.)ohiomom\\.org$/i.test(location.hostname)){'
                 'location.replace("ohio/index.html"+location.search+location.hash)}</script>')
STATE_SECTIONS = ['help-now', 'housing', 'food-bills', 'pregnancy-baby', 'kids-differently', 'single-parent', 'take-care', 'military']
URGENT_LINES = ['us-ndvh', 'us-988', 'us-childhelp']
# A state page shows every national listing too, except the ones the state has its own version of.
# National id: the state template (or state record) that takes its place.
REPLACED_BY_STATE = {
    'us-dv-coalition': 'dv', 'us-211-help': '211', 'us-snap': 'snap', 'us-wic': 'wic', 'us-liheap': 'energy',
    'us-health-centers': 'health-centers', 'us-insure-kids': 'coverage', 'us-diaper-banks': 'diapers',
    'us-childcare': 'childcare', 'us-head-start': 'head-start', 'us-legal-aid': 'legal',
    'us-cdc-find-ei': 'ei', 'us-parent-center': 'pti',
}
# Within a need these come first, in this order: the most urgent door, then the local ones.
# National listings are named by id, state listings by their template. The rest keep the order of the data files.
FIRST = {
    'help-now': ['us-ndvh', 'us-988', 'us-childhelp'],
    'housing': ['us-find-shelter', 'shelters', 'us-ndvh', 'dv', 'us-dv-coalition', '211', 'us-211-help',
                'housing-hud', 'us-housing-counselor'],
}


def tel(p):
    return lib.tel_href(p)


def logo_html(name):
    words = name.split()
    return esc(' '.join(words[:-1])) + ' <span>' + esc(words[-1]) + '</span>'


def share_tags(image, alt, root=''):
    """What a phone, Facebook or a search engine shows for a shared link, and the icon in a browser tab.
    `image` is a full address because the apps that read it do not follow relative ones."""
    return f'''<meta property="og:image" content="{esc(image)}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{esc(alt)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#fff9f3">
<link rel="icon" href="{root}assets/icon-48.png" sizes="48x48" type="image/png">
<link rel="icon" href="{root}assets/icon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="{root}assets/icon-180.png">'''


def page(data, path, title, desc, body, body_class='', head_extra='', canonical=None, scripts=''):
    site = data['site']
    root = '../' * path.count('/')
    url = f"https://{site['domain']}/" + ('' if (canonical or path) == 'index.html' else (canonical or path))
    full_title = title if title.startswith(site['name']) else f"{title} | {site['name']}"
    nav = ''.join(
        f'<a href="{root}{h}"' + (' aria-current="page"' if h == path else '') + f'>{esc(t)}</a>' for h, t in NAV)
    foot = ''.join(f'<a href="{root}{h}">{esc(t)}</a>' for h, t in FOOT)
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(full_title)}</title>
<meta name="description" content="{esc(desc)}">
<meta name="referrer" content="no-referrer">
<link rel="canonical" href="{esc(url)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{esc(site['name'])}">
<meta property="og:url" content="{esc(url)}">
<meta property="og:title" content="{esc(full_title)}">
<meta property="og:description" content="{esc(desc)}">
{share_tags(f"https://{site['domain']}/assets/share.jpg", f"{site['name']}: help for moms in all 50 states. Free, with no sign-up and no ads.", root)}
<link rel="stylesheet" href="{root}assets/ymt.css">{head_extra}
</head>
<body class="{esc(body_class)}">
<a class="skip" href="#main">Skip to content</a>
<header class="top"><a class="exit" data-exit href="{EXIT_URL}" rel="noreferrer">Leave this site</a><a class="logo" href="{root}index.html">{logo_html(site['name'])}</a><nav class="mainnav" aria-label="Main">{nav}</nav></header>
<main id="main">
{body}
</main>
<footer class="foot">
<p class="footnav">{foot}</p>
<p>Founded by {esc(site['founder'])}. See something out of date, or know a group we should list? <a href="{root}report.html">Report a problem</a>.</p>
<p class="small">In danger right now? Call 911. {esc(site['name'])} is an information directory, not an emergency service or a provider of legal, medical or financial advice. Contacts come from published official and organization sources and are not telephone-confirmed. No sign-up or ads, and we add no tracking. Our web host, Wix, sets its own cookies.</p>
<p class="small">Ohio mom? Visit <a href="{root}{esc(site['ohio_path'])}">OhioMom</a>. Mobility and disability resources: <a href="{esc(site['mobilitytalk_url'])}">Mobility Talk</a>.</p>
</footer>
<script src="{root}assets/ymt.js"></script>{scripts}
</body>
</html>
'''


ABBREVIATIONS = ('U.S.', 'a.m.', 'p.m.', 'e.g.', 'i.e.', 'St.', 'Dr.', 'Mr.', 'Mrs.', 'Ms.', 'vs.', 'No.', 'Inc.')


def split_first(text):
    """(first sentence, the rest). The first sentence is the one line a card shows before it is opened."""
    for m in re.finditer(r'[.!?]["”)]?\s+', text):
        head = text[:m.end()].rstrip()
        if head.endswith(ABBREVIATIONS):
            continue
        nxt = text[m.end():m.end() + 1]
        if nxt and (nxt.isupper() or nxt.isdigit() or nxt in '"“('):
            return head, text[m.end():].strip()
    return text.strip(), ''


def card(r, root='', cid=None):
    """A short card: the name, one line, and the buttons. Everything else waits behind "More about this"."""
    rid = esc(cid or r['id'])
    short, rest = split_first(r['what'])
    cls = 'card urgent' if r.get('urgent') else 'card'
    out = [f'<article class="{cls}" id="{rid}"><h3>{esc(r["name"])}</h3><p class="short">{esc(short)}</p>']
    if r.get('text'):
        out.append(f'<p class="textline">{esc(r["text"])}</p>')
    acts = []
    if r.get('phone'):
        acts.append(f'<a class="btn call" href="{tel(r["phone"])}">Call {esc(r["phone"])}</a>')
    if r.get('url'):
        acts.append(f'<a class="btn" href="{esc(r["url"])}" rel="noopener">Website</a>')
    out.append('<p class="actions">' + ''.join(acts) + '</p>')
    more = [f'<p class="org">{esc(r["org"])}</p>']
    if rest:
        more.append(f'<p>{esc(rest)}</p>')
    more.append(f'<p><strong>Next step:</strong> {esc(r["how"])}</p>')
    if r.get('phone') and r.get('phone_label'):
        more.append(f'<p class="note">Phone: {esc(r["phone_label"])}</p>')
    if r.get('links'):
        more.append('<p class="actions">' + ''.join(
            f'<a class="btn plain" href="{esc(link["url"])}" rel="noopener">{esc(link["label"])}</a>' for link in r['links']) + '</p>')
    srcs = ' '.join(f'<a href="{esc(u)}" rel="noopener">{i}</a>' for i, u in enumerate(r['sources'], 1))
    more.append(f'<p class="src">Checked {esc(lib.pretty_date(r["reviewed_on"]))}. Sources: {srcs}</p>')
    out.append(f'<details class="more"><summary>More about this<span class="sr">: {esc(r["name"])}</span></summary>{"".join(more)}</details></article>')
    return ''.join(out)


def cards(records, root='', prefix=None):
    """prefix: {record id: card id} for a listing shown a second time on the same page."""
    return '<div class="cards">' + ''.join(card(r, root, (prefix or {}).get(r['id'])) for r in records) + '</div>'


def need(sec, records, root='', prefix=None):
    """One need, closed until she asks for it: a row that opens to its short cards."""
    n = len(records)
    count = f'{n} option{"s" if n != 1 else ""}'
    cls = 'need urgent' if sec['id'] == 'help-now' else 'need'
    return (f'<details class="{cls}" id="{sec["id"]}"><summary><span class="ico" aria-hidden="true">{sec["icon"]}</span>'
            f'<h2>{esc(sec["label"])}</h2><span class="nsum">{esc(sec["summary"])}</span>'
            f'<span class="ncount">{count}</span></summary>{cards(records, root, prefix)}</details>')


def needs(body):
    return f'<section class="wrap needs" aria-label="What do you need?">{body}</section>'


def kind(r):
    """What a listing is, whichever state it is for: the national id, or the state template's id."""
    return r['id'] if r['scope'] == 'US' else r['id'].split('-', 1)[1]


def in_order(sid, records):
    first = FIRST.get(sid, [])
    return sorted(records, key=lambda r: first.index(kind(r)) if kind(r) in first else len(first))


def row(sec, records, root=''):
    """One need with everything that belongs under it. A listing filed under another need first is shown here as well."""
    sid = sec['id']
    primary = [r for r in records if r['section'] == sid]
    also = [r for r in records if sid in r.get('also', [])]
    prefix = {r['id']: f"{sid}--{r['id']}" for r in also}
    return need(sec, in_order(sid, primary + also), root, prefix)


def finder(what, hint):
    """Search and "Show everything" for a page of needs. It only hides and shows what is already on the page."""
    return (f'<section class="wrap finder" id="everything" data-finder hidden><label for="q">{esc(what)}</label>'
            f'<div class="finderrow"><input id="q" type="search" placeholder="{esc(hint)}" autocomplete="off" enterkeyhint="search">'
            f'<button type="button" class="btn" data-show-all aria-pressed="false">Show everything</button></div>'
            f'<p class="quiet" data-count role="status"></p>'
            f'<p class="quiet">Nothing you type here is sent or saved.</p></section>')


def urgent_strip(data, root=''):
    """The three lines that must never be more than one tap away, as small phone cards."""
    nat = {r['id']: r for r in data['resources']}
    lines = [nat[i] for i in URGENT_LINES]
    items = ''.join(
        f'<li><a class="phonecard" href="{tel(r["phone"])}">Call {esc(r["phone"])}<small>{esc(r["chip"])}</small></a></li>' for r in lines)
    texts = esc(nat['us-ndvh']['text'])
    return (f'<section class="wrap now" id="now"><h2>Need help right now?</h2>'
            f'<p class="quiet">Free, and answered any hour. If you or your child are in danger, call 911.</p>'
            f'<ul class="phonecards">{items}</ul>'
            f'<p class="quiet">Cannot talk out loud? {texts} for the domestic violence hotline, or text 988. '
            f'<a href="{root}help.html#help-now">More ways to get help now</a></p></section>')


def sec_map(data):
    return {s['id']: s for s in data['sections']}


def hero(title, lede, extra='', cls='slim'):
    return f'<section class="hero {cls}"><div class="wrap"><h1>{title}</h1><p class="lede">{lede}</p>{extra}</div></section>'


# ---------------------------------------------------------------- pages
def build_index(data):
    """The front page asks one question and shows no listings. Every listing is one choice away.
    Beside the question is the picture, with the joke of the day in a speech bubble in it (scripts/home_extras.py)."""
    site = data['site']
    jokes = extras.approved_jokes()
    tiles = ''.join(f'<a class="tile {c}" href="{h}"><span class="ico" aria-hidden="true">{i}</span><span class="ttext"><strong>{esc(t)}</strong><span>{esc(d)}</span></span></a>'
                    for c, i, t, d, h in TILES)
    options = '<option value="">Choose your state</option>' + ''.join(
        f'<option value="states/{s["abbr"].lower()}.html">{esc(s["name"])}</option>' for s in data['states'])
    pick = (f'<div class="statepick"><label for="statepick">Or start with your state</label>'
            f'<select id="statepick" data-state-pick>{options}</select><a href="states.html">See all states</a>'
            f'<a href="county.html">Find your county</a></div>')
    lede = 'Pick one. You will get a short list of who to call. Free, private, no sign-up.'
    top = (f'<div class="herotop"><div class="herotext"><h1>Hi, mom. What do you need today?</h1>'
           f'<p class="lede">{lede}</p></div>{extras.scene_block(False, jokes, "jokes.html")}</div>')
    body = (f'<section class="hero home"><div class="wrap">{top}<div class="tiles">{tiles}</div>{pick}</div></section>'
            + '\n' + urgent_strip(data))
    desc = f"{site['tagline']} Food, child care, health coverage, disability help and crisis lines in all 50 states."
    about = {'@context': 'https://schema.org', '@type': 'WebSite', '@id': f"https://{site['domain']}/#website", 'name': site['name'],
             'url': f"https://{site['domain']}/", 'description': desc, 'inLanguage': 'en',
             'publisher': {'@type': 'Organization', 'name': site['name'],
                           'founder': {'@type': 'Person', 'name': site['founder']}}}
    structured = '\n<script type="application/ld+json">' + json.dumps(about, ensure_ascii=False).replace('<', '\\u003c') + '</script>'
    return page(data, 'index.html', f"{site['name']}: help for moms in all 50 states", desc,
                body, 'home', head_extra=OHIO_REDIRECT + structured,
                scripts='\n' + extras.joke_scripts(jokes) if jokes else '')


def build_jokes(data, jokes):
    """The running list of the jokes of the day: the ones that have already run, newest first."""
    lede = ('One mom joke a day, for the days that need one. Today\'s is on the <a href="index.html">home page</a>. '
            'The ones that already ran are below, newest first.')
    body = hero('Mom joke of the day', lede) + f'\n<section class="wrap">{extras.joke_list(jokes)}</section>'
    return page(data, 'jokes.html', 'Mom joke of the day', 'A mom joke every day, and the ones that already ran.', body,
                head_extra=structured_data(breadcrumbs(data, [('Mom joke of the day', 'jokes.html')])),
                scripts='\n' + extras.joke_scripts(jokes))


def structured_data(*items):
    """A JSON-LD block for the page head. '<' is escaped so no listing text can close the script tag."""
    graph = {'@context': 'https://schema.org', '@graph': list(items)} if len(items) > 1 else {'@context': 'https://schema.org', **items[0]}
    return '\n<script type="application/ld+json">' + json.dumps(graph, ensure_ascii=False).replace('<', '\\u003c') + '</script>'


def breadcrumbs(data, trail):
    """Home, then each (name, path) step. Search engines can show this path under the page's result."""
    base = f"https://{data['site']['domain']}/"
    steps = [(data['site']['name'], '')] + trail
    return {'@type': 'BreadcrumbList', 'itemListElement': [
        {'@type': 'ListItem', 'position': i, 'name': name, 'item': base + path} for i, (name, path) in enumerate(steps, 1)]}


def build_help(data):
    secs = [s for s in data['sections'] if not s.get('page')]
    # A listing that belongs under two needs is shown under both, so nobody has to hunt for it.
    rows = [row(s, data['resources']) for s in secs]
    lede = ('Pick what you need, or search every listing. These work in every state. '
            'For your state\'s own offices, <a href="states.html">choose your state</a>.')
    body = (hero('Find help', lede) + finder('Search every listing', 'shelter, rent, WIC, child care…') + needs(''.join(rows))
            + '<section class="wrap slim"><p>In danger right now? Call 911. Domestic violence shelter addresses are never listed here, for safety.</p></section>')
    return page(data, 'help.html', 'Find help for moms',
                'Free national help for moms: crisis lines, housing and shelter, food and bills, pregnancy and baby, kids who learn differently and single parents.', body,
                head_extra=structured_data(breadcrumbs(data, [('Find help', 'help.html')])))


def build_connect(data):
    prim = [r for r in data['resources'] if r['section'] == 'connect']
    also = [r for r in data['resources'] if 'connect' in r.get('also', [])]
    site = data['site']
    body = hero('Meet other moms', 'Moms groups, feeding groups and people who get it. Find one near you or online.') + f'''
<section class="group wrap"><h2>Groups for moms</h2><p class="quiet">Local chapters and meetups run by volunteers. Groups differ, so ask how one runs before you go.</p>{cards(prim)}</section>
<section class="group wrap"><h2>Support for the hard days</h2><p class="quiet">Feeding help and support lines from people who have been there.</p>{cards(also, '', {r['id']: 'connect--' + r['id'] for r in also})}</section>
<section class="wrap"><div class="localbox"><strong>Ohio mom?</strong> <a href="{esc(site['ohio_path'])}">OhioMom</a> lists Ohio groups, meetups and events by region and county.</div></section>
<section class="wrap cta"><h2>Run a group, or know a good one?</h2><p>If it is free or low cost and good for moms, we want to list it. Nobody pays to be listed here.</p><p><a class="btn big" href="report.html">Tell us about it</a></p></section>'''
    return page(data, 'connect.html', 'Meet other moms',
                'Moms groups, breastfeeding groups and support for the hard days, in person and online, across the U.S.', body,
                head_extra=structured_data(breadcrumbs(data, [('Meet other moms', 'connect.html')])))


def build_states_index(data):
    items = ''.join(f'<li><a href="states/{s["abbr"].lower()}.html">{esc(s["name"])}<small>{s["abbr"]}</small></a></li>' for s in data['states'])
    body = hero('Help by state', 'All 50 states and the District of Columbia. Pick yours.') + f'<section class="wrap"><ul class="statelist">{items}</ul><p class="note">Looking for help close to home? <a href="county.html">Find your county</a>. Looking for something national? See <a href="help.html">Find help</a>.</p></section>'
    return page(data, 'states.html', 'Help by state',
                'Pick your state for SNAP, WIC, child care, health coverage, disability help and domestic violence resources.', body,
                head_extra=structured_data(breadcrumbs(data, [('Help by state', 'states.html')])))


def build_state(data, s):
    secs = sec_map(data)
    recs = lib.state_records(s, data)
    have = {kind(r) for r in recs}
    # The state's own offices first, then every national listing the state does not already have its own version of.
    everything = recs + [r for r in data['resources'] if REPLACED_BY_STATE.get(r['id']) not in have]
    rows = ''.join(row(secs[sid], everything, '../') for sid in STATE_SECTIONS)
    local = ''
    if s.get('local_site'):
        ls = s['local_site']
        local = f'<div class="localbox"><strong>Ohio mom?</strong> <a href="../{esc(ls["path"])}">{esc(ls["name"])}</a> is {esc(ls["what"][0].lower() + ls["what"][1:])}</div>'
    intro = (f'Pick what you need, or search every listing. Each choice opens {esc(s["name"])}\'s own offices first, then national lines. '
             f'<a href="../states.html">Choose another state</a>.')
    body = (hero(f'{esc(s["name"])}: help for moms', intro, county_pick(data, s) + local, 'slim')
            + finder(f'Search every {s["name"]} listing', 'shelter, rent, WIC, child care…') + needs(rows)
            + '<section class="wrap slim"><p><strong>Meet other moms.</strong> Find a group near you or online. <a href="../connect.html">Meet moms</a></p></section>')
    path = f'states/{s["abbr"].lower()}.html'
    desc = f'Free help for moms in {s["name"]}: housing and shelter, SNAP, WIC, child care, health coverage, disability services and domestic violence resources.'
    base = f"https://{data['site']['domain']}/"
    about = {'@type': 'CollectionPage', '@id': base + path, 'url': base + path, 'name': f'{s["name"]}: help for moms',
             'description': desc, 'inLanguage': 'en', 'isPartOf': {'@id': base + '#website'},
             'about': {'@type': 'State', 'name': s['name']}}
    trail = breadcrumbs(data, [('Help by state', 'states.html'), (s['name'], path)])
    return page(data, path, f'{s["name"]}: help for moms', desc, body, head_extra=structured_data(about, trail))


def county_pick(data, s):
    """Local listings for each county of the state, one choice away. The same picker the front page uses for states."""
    counties = sorted((c for c in data['counties'] if c['state'] == s['abbr']), key=lambda c: c['name'])
    if not counties:
        return ''
    if len(counties) == 1:
        return f'<p class="countylink"><a href="../county.html#{counties[0]["fips"]}">Local listings for {esc(s["name"])}</a>: public housing, legal aid, health centers, school districts and Head Start.</p>'
    noun = {'LA': 'parish', 'AK': 'borough or area'}.get(s['abbr'], 'county')
    options = f'<option value="">Choose your {noun}</option>' + ''.join(
        f'<option value="../county.html#{c["fips"]}">{esc(c["name"])}</option>' for c in counties)
    return (f'<div class="statepick"><label for="countypick">Local help in your {noun}</label>'
            f'<select id="countypick" data-state-pick>{options}</select></div>')


COUNTY_SOURCES = [  # in the order the rows appear on the page
    ('pha', 'Public housing and Section 8', "HUD's list of public housing agencies, from its {0}. How vouchers work is on HUD's {1}",
     [('https://hudgis-hud.opendata.arcgis.com/datasets/HUD::public-housing-authorities-1', 'open data site'),
      ('https://www.hud.gov/helping-americans/housing-choice-vouchers-tenants', 'Housing Choice Voucher page')],
     "A county lists the agencies with their office there or named for it, then the nearest others in the state, then "
     "the state's own voucher program where it has one. Programs a service provider runs for one group of people are left out."),
    ('hud', 'Housing counselors', "HUD's list of approved housing counseling agencies, also on its {0} and {1}",
     [('https://www.hud.gov/i_want_to/talk_to_a_housing_counselor', 'housing counselor page'), ('https://data.hud.gov/housing_counseling.html', 'counselor search')],
     'Counselors are matched to a county by the ZIP code of their office, and nearby ones are shown by distance.'),
    ('lg', 'Free legal help', "the Legal Services Corporation's list of the legal aid programs it funds and its map of the areas "
     "they serve, also searchable in its {0}. What legal aid helps with is on its {1}",
     [('https://www.lsc.gov/about-lsc/what-legal-aid/i-need-legal-help', 'legal aid finder'),
      ('https://www.lsc.gov/about-lsc/what-legal-aid', 'page on what legal aid does')],
     'A county is matched to the program whose service area holds it.'),
    ('hrsa', 'Health centers', "the Health Resources and Services Administration's list of health center sites, also searchable in its {0} and {1}",
     [('https://findahealthcenter.hrsa.gov/', 'Find a Health Center tool'), ('https://data.hrsa.gov/data/download', 'data downloads')],
     'School, mobile-van and residential sites are left out.'),
    ('sd', 'School districts', "the National Center for Education Statistics' list of public school districts, also searchable in "
     "its {0}. What the row says about evaluations comes from the {1} and {2}",
     [('https://nces.ed.gov/ccd/districtsearch/', 'district search'),
      ('https://www.parentcenterhub.org/preschoolers/', 'Center for Parent Information and Resources page on preschool special education'),
      ('https://www.law.cornell.edu/cfr/text/34/300.503', 'the federal rule on written notice')],
     'A district is listed in each county its boundary covers. Charter schools and high-school-only districts are left out.'),
    ('hs', 'Head Start', "the Office of Head Start's list of open program locations, also searchable in its {0} and {1}",
     [('https://headstart.gov/center-locator', 'center locator'), ('https://headstart.gov/how-apply', 'how to apply')],
     'Locations with no phone number in the list are left out.'),
]


def build_county(data):
    """One page for every county. The listings are in assets/us/<state>.json and assets/county.js draws them."""
    secs = sec_map(data)
    options = '<option value="">Choose your state</option>' + ''.join(
        f'<option value="{s["abbr"].lower()}" data-fips="{STATE_FIPS[s["abbr"]]}">{esc(s["name"])}</option>' for s in data['states'])
    find = ('<div class="countyfind" data-county-find hidden>'
            f'<div><label for="cstate">State</label><select id="cstate">{options}</select></div>'
            '<div><label for="ccounty">County</label><select id="ccounty" disabled><option value="">Choose a state first</option></select></div>'
            '<div><label for="zip">Or your ZIP code</label><input id="zip" type="search" inputmode="numeric" maxlength="5" '
            'autocomplete="off" enterkeyhint="go" placeholder="5 digits"></div></div>'
            '<p class="quiet" id="cmsg" role="status"></p>')
    lede = ('Pick your county to see where to apply for housing help, free legal help, low-cost health care, free evaluations '
            'for your child and Head Start close to you. Free, private, no sign-up.')
    hero_html = (f'<section class="hero slim"><div class="wrap"><h1 id="ctitle">Help near you</h1>'
                 f'<p class="lede" id="clede">{esc(lede)}</p>{find}</div></section>')
    fallback = ('<section class="wrap"><p>The local listings on this page need JavaScript, which seems to be off or still loading. '
                'You can still <a href="states.html">choose your state</a> for its offices and help lines.</p></section>')
    statehelp = ('<div hidden data-statehelp><ul>' + ''.join(
        f'<li><a data-sec="{sid}" href="states.html">{esc(secs[sid]["label"])}</a></li>' for sid in STATE_SECTIONS) + '</ul></div>')
    def sentence(key, template, links):
        # {0}, {1}... in the template are the links, in order; their numbers on each card follow the same order.
        parts = re.split(r'\{(\d)\}', template)
        out = []
        for i, part in enumerate(parts):
            if i % 2:
                u, t = links[int(part)]
                out.append(f'<a data-src="{key}" href="{esc(u)}" rel="noopener">{esc(t)}</a>')
            else:
                out.append(esc(part))
        return ''.join(out)
    items = ''.join(f'<li><strong>{esc(label)}:</strong> {sentence(key, what, links)}. {esc(note)}</li>'
                    for key, label, what, links, note in COUNTY_SOURCES)
    sources = (f'<section class="wrap slim" id="sources"><h2>Where these listings come from</h2><ul>{items}</ul>'
               '<p class="note">Listings are copied from these federal lists by a program, not checked by phone, and the date of '
               'the copy is on each one. A Website button appears only when that website loaded in our automatic check. '
               'If something is wrong, <a href="report.html">tell us</a>.</p>'
               '<p class="note">Nothing you type on this page is saved. A ZIP code is matched inside your browser, using a list '
               'your browser downloads for the first digit of the code.</p></section>')
    body = hero_html + f'\n<div id="county-app">{fallback}</div>' + statehelp + '\n' + urgent_strip(data) + '\n' + sources
    return page(data, 'county.html', 'Help near you, by county',
                'Public housing, housing counselors, legal aid, health centers, school districts and Head Start in every U.S. county, '
                'from federal directories. Free, with no sign-up.',
                body, head_extra=structured_data(breadcrumbs(data, [('Help near you, by county', 'county.html')])),
                scripts='\n<script src="assets/county.js"></script>')


def build_yoga(data):
    """Deborah's sessions are in person in Ohio, so they are offered on the OhioMom pages only.
    This address stays so old links still work, and passes visitors straight on."""
    site = data['site']
    dest = site['ohio_yoga_path']
    head = (f'\n<meta name="robots" content="noindex">\n<meta http-equiv="refresh" content="0; url={esc(dest)}">'
            f'\n<script>location.replace({json.dumps(dest)}+location.search+location.hash)</script>')
    body = hero('Yoga with Deborah', 'Deborah\'s yoga and training sessions are in Ohio, so they are on the OhioMom pages.',
                f'<p class="actions"><a class="btn big" href="{esc(dest)}">Go to yoga with Deborah</a></p>')
    return page(data, 'yoga.html', 'Yoga with Deborah', f"{site['founder']}'s yoga and training sessions are in Ohio, on the OhioMom pages.",
                body, head_extra=head, canonical=dest)


def build_about(data):
    site = data['site']
    body = hero(f'About {esc(site["name"])}', f'A place where moms can connect, with real help for the moms who need it.') + f'''
<section class="wrap"><div class="steps"><div class="aboutwho"><figure class="aboutphoto"><img src="assets/about-us.jpg" width="380" height="379" alt="Travis and Deborah smiling together outdoors on a sunny day"><figcaption>Travis and Deborah</figcaption></figure><div><h2>Who runs it</h2><p>We are Travis and Deborah Vought, and it is just the two of us. Deborah founded {esc(site["name"])}. It grows out of <a href="{esc(site["ohio_path"])}">OhioMom</a>, her Ohio hub for mothers, which is now the Ohio part of this site. The same approach now reaches every state. Travis looks after the website.</p>
<p>We have four kids. One has type 1 diabetes and two have autism, so ours is a neurodivergent family. We live in rural Ohio, and we are involved in community building.</p>
<p>It is an independent project. It is not affiliated with any podcast, show or organization named "Mom Talk".</p></div></div>
<h2>How we choose listings</h2><ul><li>We list free or low-cost public programs, nonprofits and official locators. We do not list private businesses, and nobody pays to be listed.</li><li>Each listing links to the published sources it came from and shows the date it was checked.</li><li>Contacts come from official sources and are not confirmed by telephone. Phone numbers and websites change. If one is wrong, <a href="report.html">tell us</a>.</li><li>Every link is checked automatically each month, and a person reviews any that fail.</li><li>Domestic violence shelter addresses are never listed. We point to the hotline or state coalition that places people safely.</li></ul>
<h2>What this site is not</h2><p>It is not an emergency service. If you or someone else is in danger, call 911. It does not give legal, medical or financial advice, and it cannot sign you up for anything.</p>
<h2>Your privacy and safety</h2><ul><li>No ads, no sign-up and no forms, and we add no tracking or cookies of our own.</li><li>This site is hosted on Wix. Wix loads its own script and sets a few cookies on every page it hosts. We do not control those.</li><li>A <strong>Leave this site</strong> button is on every page. It takes you to a weather search and removes this page from your back button.</li><li>It cannot erase your browser history. If someone else may check your device, use a private or incognito window, or a device they cannot reach.</li><li>Sites we link to have their own privacy practices.</li></ul>
<h2>Credit and license</h2><p>{esc(data["attribution"])} The data on this site is licensed CC BY 4.0 and the code is MIT. Listings describe third-party organizations from their published sources. The license covers the compilation and gives no rights in those organizations' names or marks.</p></div></section>'''
    return page(data, 'about.html', 'About', f'Who runs {site["name"]}, how listings are chosen and checked, and how your privacy and safety are protected.', body)


def build_report(data):
    site = data['site']
    subject = urllib.parse.quote(f'{site["name"]}: report a problem')
    mbody = urllib.parse.quote('Page or listing:\nWhat is wrong, or what should we add:\nA link or phone number for the right information:\n')
    href = f'mailto:{site["corrections_email"]}?subject={subject}&body={mbody}'
    body = hero('Report a problem', 'Found a phone number or link that is wrong? Know a group we should list? A person will review it.') + f'''
<section class="wrap"><div class="steps"><p><a class="btn big" href="{esc(href)}">Email us</a></p><p>That opens your email app with a short note to start from. Or write to <strong>{esc(site["corrections_email"])}</strong>.</p><ul><li>Tell us which page or listing, and what is wrong.</li><li>Send a link to the right information if you have one.</li><li>Please leave out private details about your own situation.</li></ul><p class="note">This is not monitored for emergencies. If you need help now, call 911, or see <a href="help.html#help-now">Get help now</a>. We do not store anything on this site; your email goes only to the address above.</p></div></section>'''
    return page(data, 'report.html', 'Report a problem', 'Tell us about a wrong phone number or link, or suggest a moms group to list.', body)


def build_404(data):
    body = hero('We could not find that page', 'It may have moved. Try one of these.') + '''
<section class="wrap"><p class="actions"><a class="btn big" href="/index.html">Go to the home page</a> <a class="btn" href="/help.html">Find help</a> <a class="btn" href="/states.html">Help by state</a></p></section>'''
    # 404 is served from any path, so it uses root-absolute links and assets.
    html = page(data, '404.html', 'Page not found', 'This page could not be found.', body)
    return (html.replace('href="assets/', 'href="/assets/').replace('src="assets/', 'src="/assets/')
                .replace('href="index.html"', 'href="/index.html"').replace('href="help.html', 'href="/help.html')
                .replace('href="connect.html', 'href="/connect.html').replace('href="states.html', 'href="/states.html')
                .replace('href="yoga.html', 'href="/yoga.html').replace('href="about.html', 'href="/about.html')
                .replace('href="report.html', 'href="/report.html'))


def build_all(data):
    files = {
        'index.html': build_index(data), 'help.html': build_help(data), 'connect.html': build_connect(data),
        'states.html': build_states_index(data), 'yoga.html': build_yoga(data), 'about.html': build_about(data),
        'report.html': build_report(data), '404.html': build_404(data), 'county.html': build_county(data),
    }
    for s in data['states']:
        files[f'states/{s["abbr"].lower()}.html'] = build_state(data, s)
    jokes = extras.approved_jokes()
    if jokes:  # no page until the owner has approved a batch
        files['jokes.html'] = build_jokes(data, jokes)
    domain = data['site']['domain']
    pages = sorted(p for p in files if p != '404.html' and 'name="robots" content="noindex"' not in files[p])
    # Pages that only pass the visitor on (marked noindex) stay out of the sitemap.
    ohio = sorted(str(p.relative_to(ROOT)) for p in (ROOT / 'ohio').rglob('*.html')
                  if 'name="robots" content="noindex"' not in p.read_text(encoding='utf-8'))
    pages += ohio + ['family-guide.html']

    def loc(p):
        # Wix serves a folder address only at the site root, so every other page is named in full.
        return '' if p == 'index.html' else p
    urls = ''.join(f'  <url><loc>https://{domain}/{loc(p)}</loc></url>\n' for p in sorted(set(pages)))
    files['sitemap.xml'] = f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}</urlset>\n'
    files['robots.txt'] = f'User-agent: *\nAllow: /\n\nSitemap: https://{domain}/sitemap.xml\n'
    # Suicide and homelessness help on its own line directly above the footer of every page a visitor reads
    # (scripts/help_now.py). Pages that only pass the visitor on stay as they are.
    for rel, content in files.items():
        if help_now.wants_help(rel, content):
            files[rel] = help_now.add_help(content, rel)
    return files


def main():
    check = '--check' in sys.argv
    data = lib.load()
    files = build_all(data)
    stale = []
    for rel, content in files.items():
        p = ROOT / rel
        if check:
            if not p.exists() or p.read_text(encoding='utf-8') != content:
                stale.append(rel)
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding='utf-8')
    if check:
        if stale:
            print('Out of date (run python3 scripts/build.py):\n' + '\n'.join(stale))
            sys.exit(1)
        print(f'OK: {len(files)} files match the data')
    else:
        print(f'Built {len(files)} files')


if __name__ == '__main__':
    main()
