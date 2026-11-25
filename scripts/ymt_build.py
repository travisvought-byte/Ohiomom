#!/usr/bin/env python3
"""Build every page from data/*.json.

    python3 scripts/build.py          write the site
    python3 scripts/build.py --check  fail if the files on disk differ from the data

Edit data or this script, never the built pages. The Ohio pages under ohio/ are separate source, not built here.
"""
import json
import re
import sys
import unicodedata
import urllib.parse
from html import escape as esc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ads  # noqa: E402
import christmas_data as xmas  # noqa: E402
import home_extras as extras  # noqa: E402
import ymt_lib as lib  # noqa: E402
from us_geo import STATE_FIPS  # noqa: E402

ROOT = lib.ROOT
EXIT_URL = 'https://www.google.com/search?q=weather'
NAV = [('christmas.html', 'Christmas help'), ('help.html', 'Find help'), ('connect.html', 'Meet moms'), ('states.html', 'By state'), ('county.html', 'Near you'),
       ('world.html', 'Worldwide')]
FOOT = [('christmas.html', 'Christmas help'), ('help.html', 'Find help'), ('connect.html', 'Meet moms'), ('states.html', 'By state'),
        ('about.html', 'About'), ('about.html#advertise', 'Advertise'), ('privacy.html', 'Privacy'), ('report.html', 'Report a problem')]
TILES = [
    ('t9', '🎄', 'Christmas help', 'Toys for your kids, a holiday meal, the heat bill. Many sign-ups close early.', 'christmas.html'),
    ('t1', '🤝', 'Meet other moms', 'Groups and communities near you and online.', 'connect.html'),
    ('t7', '🏠', 'Housing and shelter', "A place to stay tonight, women's shelters, help with rent.", 'help.html#housing'),
    ('t2', '🧺', 'A hand with food or bills', 'SNAP, WIC, energy bills and food banks.', 'help.html#food-bills'),
    ('t3', '🍼', "I'm pregnant or have a new baby", 'Health coverage, nursing help, diapers, safe sleep.', 'help.html#pregnancy-baby'),
    ('t4', '🧩', 'My child learns or grows differently', 'Autism, ADHD, delays, school help and other parents.', 'help.html#kids-differently'),
    ('t5', '💛', 'Parenting on my own', 'Child care, Head Start, child support and legal help.', 'help.html#single-parent'),
    ('t10', '👵', 'Raising a grandchild', 'For grandparents and relatives raising kids: money, custody, school and support.', 'kinship.html'),
    ('t6', '☕', 'Take care of me', 'Someone to talk to on the hard days.', 'help.html#take-care'),
    ('t8', '🔎', 'See everything', 'Every listing in one place, with a search box.', 'help.html#everything'),
]
# "I'm…": the front page's second way in, by who she is rather than what she needs. Each points at a need or listing
# that is already on the site; nothing here is a page of its own. (label, href)
IAM = [
    ('a single mom', 'help.html#single-parent'),
    ('expecting, or just had a baby', 'help.html#pregnancy-baby'),
    ('raising a child with a disability', 'help.html#kids-differently'),
    ('behind on bills', 'help.html#food-bills'),
    ('about to lose my home', 'help.html#housing'),
    ('leaving an unsafe situation', 'help.html#us-ndvh'),
    ('a military or veteran family', 'help.html#military'),
    ('raising my grandkids', 'kinship.html'),
    ('missing someone in jail or prison', 'inside.html'),
    ('having a really hard time', 'help.html#take-care'),
    ('new here and want to meet moms', 'connect.html'),
    ('raising kids outside the U.S.', 'world.html'),
]


def iam_block(items, root=''):
    """The "I'm…" chooser: short links that each say who she is and go straight to the help for that."""
    links = ''.join(f'<li><a href="{root}{h}">{esc(t)}</a></li>' for t, h in items)
    return f'<nav class="iam" aria-labelledby="iam-h"><h2 id="iam-h">I’m…</h2><ul>{links}</ul></nav>'


# ohiomom.org is one way into this site: its home page goes straight to the Ohio landing page.
OHIO_REDIRECT = ('\n<script>if(/(^|\\.)ohiomom\\.org$/i.test(location.hostname)){'
                 'location.replace("ohio/index.html"+location.search+location.hash)}</script>')
STATE_SECTIONS = ['help-now', 'christmas', 'housing', 'food-bills', 'pregnancy-baby', 'kids-differently', 'single-parent', 'take-care', 'military']
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
    'christmas': ['us-toys-for-tots', 'us-angel-tree', '211', 'us-211-help', 'us-operation-santa', 'us-food-bank',
                  'energy', 'us-liheap', 'us-pf-angel-tree', 'us-homefront-holidays'],
}
# Names for the places outside the 50 states and D.C. that have a Toys for Tots campaign.
TERRITORIES = {'PR': 'Puerto Rico', 'GU': 'Guam', 'VI': 'U.S. Virgin Islands'}


def tel(p):
    return lib.tel_href(p)


def dial_href(r):
    """A listing outside the U.S. carries the digits to dial ('dial'); a U.S. listing is dialed from its phone."""
    return 'tel:' + r['dial'] if r.get('dial') else tel(r['phone'])


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


def running_ads(data):
    """The ads that run on the day of the build (data['today'] stands in for it in the tests)."""
    return ads.active(data.get('ads', []), data.get('today') or ads.today())


def page(data, path, title, desc, body, body_class='', head_extra='', canonical=None, scripts='', slots=(),
         danger='In danger right now? Call 911.'):
    """slots: the ad slots this page takes, the most specific first (scripts/ads.py). A page with none never shows an ad,
    and a page whose slots no running ad names has no ad markup at all. The ad comes last in <main>, after the page's own content."""
    site = data['site']
    root = '../' * path.count('/')
    ad = ads.aside(ads.pick(running_ads(data), slots), root) if slots else ''
    if ads.network_ok(slots):
        head_extra = head_extra + ads.network_head(data.get('adsense_client', ''))
    if ad:
        body = body + '\n' + ad
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
{share_tags(f"https://{site['domain']}/assets/share.jpg", f"{site['name']}: help for moms in all 50 states. Free, with no sign-up.", root)}
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
<p class="small">{esc(danger)} {esc(site['name'])} is an information directory, not an emergency service or a provider of legal, medical or financial advice. Contacts come from published official and organization sources and are not telephone-confirmed. No sign-up. We count visits without cookies, and nothing you type is sent. Any ad is labeled Advertisement. See <a href="{root}privacy.html">Privacy</a>.</p>
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
        acts.append(f'<a class="btn call" href="{dial_href(r)}">Call {esc(r["phone"])}</a>')
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


def need(sec, records, root='', prefix=None, extra=''):
    """One need, closed until she asks for it: a row that opens to its short cards. extra: more cards, already
    written, that go after the listings (the Toys for Tots campaigns of a state)."""
    n = len(records) + extra.count('<article class="card')
    count = f'{n} option{"s" if n != 1 else ""}'
    cls = 'need urgent' if sec['id'] == 'help-now' else 'need'
    return (f'<details class="{cls}" id="{sec["id"]}"><summary><span class="ico" aria-hidden="true">{sec["icon"]}</span>'
            f'<h2>{esc(sec["label"])}</h2><span class="nsum">{esc(sec["summary"])}</span>'
            f'<span class="ncount">{count}</span></summary>{cards(records, root, prefix)[:-6]}{extra}</div></details>')


def needs(body):
    return f'<section class="wrap needs" aria-label="What do you need?">{body}</section>'


def kind(r):
    """What a listing is, whichever state it is for: the national id, or the state template's id."""
    return r['id'] if r['scope'] == 'US' else r['id'].split('-', 1)[1]


def in_order(sid, records):
    first = FIRST.get(sid, [])
    return sorted(records, key=lambda r: first.index(kind(r)) if kind(r) in first else len(first))


def row(sec, records, root='', extra=''):
    """One need with everything that belongs under it. A listing filed under another need first is shown here as well."""
    sid = sec['id']
    primary = [r for r in records if r['section'] == sid]
    also = [r for r in records if sid in r.get('also', [])]
    prefix = {r['id']: f"{sid}--{r['id']}" for r in also}
    return need(sec, in_order(sid, primary + also), root, prefix, extra)


def campaigns_card(data, st, camps, cid=None):
    """Every Toys for Tots campaign in one state, as one card: a list of links to the campaigns' own websites."""
    name = next((s['name'] for s in data['states'] if s['abbr'] == st), TERRITORIES.get(st, st))
    items = ''.join(f'<li><a href="{esc(c["url"])}" rel="noopener">{esc(c["name"])}</a></li>' for c in camps)
    n = len(camps)
    checked = lib.pretty_date(xmas.checked_on())
    return (f'<article class="card" id="{esc(cid or "tft-" + st.lower())}"><h3>Toys for Tots campaigns in {esc(name)}</h3>'
            f'<p class="short">{n} local campaign{"s" if n != 1 else ""}, each with its own website and dates. Open the one for your area, then its Request a Toy page.</p>'
            f'<p class="actions"><a class="btn plain" href="https://www.toysfortots.org/find-your-local-chapter/" rel="noopener">Toys for Tots map</a></p>'
            f'<details class="more"><summary>{"Show the campaign" if n == 1 else f"Show all {n} campaigns"}<span class="sr">: Toys for Tots campaigns in {esc(name)}</span></summary>'
            f'<ul class="camps">{items}</ul><p class="org">Marine Toys for Tots</p><p>Each campaign\'s website says which towns and counties it serves, its dates, '
            f'and whether it takes requests from families or only through local charities and agencies.</p>'
            f'<p><strong>Next step:</strong> Open the campaign nearest you. If your town is not on its site, use the Toys for Tots map to find the campaign that covers you.</p>'
            f'<p class="src">Checked {esc(checked)}, from Toys for Tots\' list of local campaigns. Sources: '
            f'<a href="{esc(xmas.SOURCE)}" rel="noopener">1</a></p></details></article>')


# What the search box says when nothing matches. 211 is a U.S. number, so a page outside the U.S. says something else.
NO_MATCH_US = 'Nothing matches. Try another word, or dial 211 and say what you need.'
NO_MATCH_WORLD = 'Nothing matches. Try another word, or open Get help now.'


def finder(what, hint, none=NO_MATCH_US):
    """Search and "Show everything" for a page of needs. It only hides and shows what is already on the page.
    none: the line shown when nothing matches (assets/ymt.js reads it from the page)."""
    return (f'<section class="wrap finder" id="everything" data-finder data-none="{esc(none)}" hidden><label for="q">{esc(what)}</label>'
            f'<div class="finderrow"><input id="q" type="search" placeholder="{esc(hint)}" autocomplete="off" enterkeyhint="search">'
            f'<button type="button" class="btn" data-show-all aria-pressed="false">Show everything</button></div>'
            f'<p class="quiet" data-count role="status"></p>'
            f'<p class="quiet">Nothing you type here is sent or saved.</p></section>')


def urgent_strip(data, root='', more=None):
    """The three lines that must never be more than one tap away, as small phone cards. The same block, in the same
    words, is on the front page, every state page and the county page. more: where "More ways to get help now" goes
    (a state page has its own Get help now row)."""
    more = more or f'{root}help.html#help-now'
    nat = {r['id']: r for r in data['resources']}
    lines = [nat[i] for i in URGENT_LINES]
    items = ''.join(
        f'<li><a class="phonecard" href="{tel(r["phone"])}">Call {esc(r["phone"])}<small>{esc(r["chip"])}</small></a></li>' for r in lines)
    texts = esc(nat['us-ndvh']['text'])
    return (f'<section class="wrap now" id="now"><h2>Need help right now?</h2>'
            f'<p class="quiet">Free, and answered any hour. If you or your child are in danger, call 911.</p>'
            f'<ul class="phonecards">{items}</ul>'
            f'<p class="quiet">Cannot talk out loud? {texts} for the domestic violence hotline, or text 988. '
            f'<a href="{esc(more)}">More ways to get help now</a></p></section>')


def kind_word(help_href, root='', lang=None):
    """The day's affirmation, as on the front page but without the picture. Every state, country and county page
    carries it, in the same place: after the needs, before the closing note (scripts/home_extras.py).
    lang: a country's language (its "lang" in data/ymt/world.json). Where the affirmations are in that language, the
    card shows the day's one in it, with the English under it; otherwise it stays English only."""
    sayings = extras.approved_affirmations()
    return extras.affirmation_card(sayings, f'{root}affirmations.html', help_href, extras.local_language(lang))


def kind_word_scripts(root='', lang=None):
    """The card's script: one file, assets/kindword.js, written by scripts/home_extras.py, and on a country page in
    another language, that one language's file (assets/kindword/<lang>.js) before it."""
    sayings = extras.approved_affirmations()
    local = extras.local_language(lang)
    return ('\n' + extras.affirmation_card_scripts(sayings, root, local[0] if local else None)) if sayings else ''


def closing(root, free=''):
    """The last lines of every state and country page, in the same words: shelter addresses are never listed, and
    where to say something is out of date. free: a line about what calls cost, where the page can say it."""
    return (f'<section class="wrap slim closing"><p>{free}Shelter addresses are never listed here, for safety. '
            f'See something out of date? <a href="{root}report.html">Tell us</a>.</p></section>')


def sec_map(data):
    return {s['id']: s for s in data['sections']}


def hero(title, lede, extra='', cls='slim'):
    return f'<section class="hero {cls}"><div class="wrap"><h1>{title}</h1><p class="lede">{lede}</p>{extra}</div></section>'


# ---------------------------------------------------------------- visuals
# Added November 24, 2026 at the owner's request ("I'd like our websites to have visuals on them as well, wherever
# feasible"). Every picture here is drawn for this site: line icons in assets/icons.svg and small diagrams made of
# plain HTML. An icon never stands alone (the words beside it say what it means), so each one is hidden from screen
# readers. A diagram's words are page text, never words inside a picture. Every count comes from data the page shows.
ICON_SPRITE = ROOT / 'assets' / 'icons.svg'


def icon_names():
    if not hasattr(icon_names, 'cache'):
        icon_names.cache = set(re.findall(r'<symbol id="([a-z-]+)"', ICON_SPRITE.read_text(encoding='utf-8')))
    return icon_names.cache


def icon(name, root=''):
    """One line icon from assets/icons.svg. It is decoration beside words that say the same, so screen readers skip it."""
    if name not in icon_names():
        sys.exit(f'scripts/ymt_build.py: no icon "{name}" in assets/icons.svg')
    return (f'<svg class="gi" aria-hidden="true" focusable="false" width="24" height="24">'
            f'<use href="{root}assets/icons.svg#{name}"/></svg>')


def glance_item(ico, n, label, href=None, root=''):
    """One tile of an at-a-glance row: an icon, a number and what it counts. A link when href is given."""
    inner = f'{icon(ico, root)}<span><b>{n:,}</b> {esc(label)}</span>'
    return f'<li><a href="{esc(href)}">{inner}</a></li>' if href else f'<li><span class="gtile">{inner}</span></li>'


def flow(steps, cls='flow', root=''):
    """A short how-to as numbered steps with an icon each: a real ordered list, so the steps read in order without
    the picture. steps: [(icon, html)]."""
    items = ''.join(f'<li>{icon(ico, root)}<span>{text}</span></li>' for ico, text in steps)
    return f'<ol class="{cls}" role="list">{items}</ol>'


# One icon per need (data/ymt/resources.json sections), for the at-a-glance row of a page of needs. Added
# November 25, 2026 at the owner's request ("add some reasonable visuals everywhere, at least for the US side").
NEED_ICONS = {'help-now': 'phone', 'christmas': 'gift', 'housing': 'house', 'food-bills': 'basket',
              'pregnancy-baby': 'bottle', 'kids-differently': 'blocks', 'single-parent': 'heart', 'kinship': 'people',
              'take-care': 'cup', 'military': 'star', 'connect': 'people', 'inside': 'house-heart'}


def needs_glance(rows, label, root=''):
    """At a glance for a page of needs: one tile per row, with its icon, its name and the count its own row shows,
    a link that opens that row. Read from the rows themselves, so the two can never disagree."""
    items = []
    for rid, summary in re.findall(r'<details class="need(?: urgent)?" id="([a-z-]+)"><summary>(.*?)</summary>', rows):
        name = re.search(r'<h2>(.*?)</h2>', summary).group(1)
        n = int(re.search(r'<span class="ncount">(\d+) ', summary).group(1))
        if n and rid in NEED_ICONS:
            items.append(f'<li><a href="#{rid}">{icon(NEED_ICONS[rid], root)}<span>{name} '
                         f'<small><b>{n:,}</b> option{"s" if n != 1 else ""}</small></span></a></li>')
    return f'<nav class="glance needglance" aria-label="{esc(label)}"><ul>{"".join(items)}</ul></nav>' if items else ''


def icon_summary(caption, points, root=''):
    """A short "at a glance" list of a page's own sentences, each beside an icon. points: [(icon, html)]."""
    items = ''.join(f'<li>{icon(ico, root)}{text}</li>' for ico, text in points)
    return f'<figure class="summary"><figcaption>{esc(caption)}</figcaption><ul class="iconlist" role="list">{items}</ul></figure>'


# ---------------------------------------------------------------- pages
def build_index(data):
    """The front page asks one question and shows no listings. Every listing is one choice away.
    Beside the question is the picture, with the day's affirmation in Deborah's speech bubble (scripts/home_extras.py)."""
    site = data['site']
    sayings = extras.approved_affirmations()
    tiles = ''.join(f'<a class="tile {c}" href="{h}"><span class="ico" aria-hidden="true">{i}</span><span class="ttext"><strong>{esc(t)}</strong><span>{esc(d)}</span></span></a>'
                    for c, i, t, d, h in TILES)
    options = '<option value="">Choose your state</option>' + ''.join(
        f'<option value="states/{s["abbr"].lower()}.html">{esc(s["name"])}</option>' for s in data['states'])
    pick = (f'<div class="statepick"><label for="statepick">Or start with your state</label>'
            f'<select id="statepick" data-state-pick>{options}</select><a href="states.html">See all states</a>'
            f'<a href="county.html">Find your county</a><a href="world.html">Outside the U.S.? Help in {len(data.get('world', {}).get('countries', []))} countries</a></div>')
    lede = ('Single mom, new baby, behind on the rent, or just worn thin? Tell us who you are or pick what you need, '
            'and you will get a short list of who to call. Free, private, no sign-up.')
    top = (f'<div class="herotop"><div class="herotext"><h1>Hi, mom. What do you need today?</h1>'
           f'<p class="lede">{lede}</p></div>{extras.scene_block(False, sayings, "affirmations.html", "help.html#take-care")}</div>')
    body = (f'<section class="hero home"><div class="wrap">{top}{iam_block(IAM)}<div class="tiles">{tiles}</div>{pick}</div></section>'
            + '\n' + urgent_strip(data))
    desc = ('Free help for single moms, new moms and moms behind on bills: food, rent, child care, disability help and '
            'crisis lines in every U.S. state, and beyond.')
    about = {'@context': 'https://schema.org', '@type': 'WebSite', '@id': f"https://{site['domain']}/#website", 'name': site['name'],
             'url': f"https://{site['domain']}/", 'description': desc, 'inLanguage': 'en',
             'publisher': {'@type': 'Organization', 'name': site['name'],
                           'founder': {'@type': 'Person', 'name': site['founder']}}}
    structured = '\n<script type="application/ld+json">' + json.dumps(about, ensure_ascii=False).replace('<', '\\u003c') + '</script>'
    return page(data, 'index.html', f"{site['name']}: help for moms in all 50 states", desc,
                body, 'home', head_extra=OHIO_REDIRECT + structured, slots=('home',),
                scripts='\n' + extras.affirmation_scripts(sayings, extras.approved_looks()) if sayings else '')


# A small sunrise beside the heading of the affirmations page: decoration only, drawn for this site.
SUNRISE = ('<svg class="art" viewBox="0 0 160 112" width="160" height="112" aria-hidden="true" focusable="false"><circle cx="80" cy="76" r="33" fill="#ffe3a3"/><circle cx="80" cy="76" r="23" fill="#ffcb52"/><path d="M52 44l-5-5M108 44l5-5M38 68h-7M122 68h7" fill="none" stroke="#f0b43c" stroke-width="2.4" stroke-linecap="round"/><path d="M80 33s-8.5-5-8.5-10.8a4.7 4.7 0 0 1 8.5-2.8 4.7 4.7 0 0 1 8.5 2.8C88.5 28 80 33 80 33z" fill="#cf2f5b"/><path d="M0 92c26-14 52-16 80-6s54 8 80-6v32H0z" fill="#a8ddd3"/><path d="M0 100c34-10 62-8 92 0s46 6 68-2v16H0z" fill="#12766f" opacity=".85"/><g fill="#3f9b88"><path d="M133 96c-.6-7 1-12.5 5-16.5l1.2 1.1c-3.6 3.7-5 8.6-4.4 15.2z"/><path d="M138.6 80.3c1.2-5 5.2-7.6 10.4-7.3-.6 5.2-4.6 8.3-10.4 7.3z"/><path d="M135.8 87.6c-4.3-3.7-9.4-3.9-12.8-1.2 3.2 3.6 8.4 4 12.8 1.2z"/></g></svg>')


def build_affirmations(data, sayings):
    """Every daily affirmation on one page, in plain words. The front page shows one a day, in Deborah's speech bubble.
    The page carries no ad: it is for a mom having a hard day."""
    lede = ('A kind word for the hard days, from one mom to another. A new one comes up each day at the top of the '
            '<a href="index.html">home page</a>. Here they all are, for whenever you need one.')
    help_line = ('<p class="sayhelp">If today is more than a hard day, you do not have to get through it alone. '
                 '<a href="help.html#take-care">Find someone to talk to</a>, or see <a href="help.html#help-now">help right now</a>.</p>')
    body = (hero('Kind words for hard days', lede, help_line).replace('<div class="wrap">', '<div class="wrap withart">' + SUNRISE, 1)
            + f'\n<section class="wrap">{extras.affirmation_list(sayings)}</section>')
    return page(data, 'affirmations.html', 'Daily affirmations for moms',
                'Daily affirmations for moms going through a hard time: tired days, new babies, toddlers, teens, money worries and grief.',
                body, head_extra=structured_data(breadcrumbs(data, [('Daily affirmations for moms', 'affirmations.html')])))


def build_jokes_moved(data):
    """Deborah's jokes gave way to the daily affirmations on November 20, 2026. This address stays so old links still
    work, and passes visitors straight on."""
    dest = 'affirmations.html'
    head = (f'\n<meta name="robots" content="noindex">\n<meta http-equiv="refresh" content="0; url={dest}">'
            f'\n<script>location.replace({json.dumps(dest)}+location.search+location.hash)</script>')
    body = hero('Kind words for hard days', 'The jokes made way for a kind word each day.',
                f'<p class="actions"><a class="btn big" href="{dest}">Go to the daily affirmations</a></p>')
    return page(data, 'jokes.html', 'Daily affirmations for moms', 'The jokes made way for a daily affirmation for moms.',
                body, head_extra=head, canonical=dest)


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
    lede = ('Not sure where to start? Pick the one thing weighing on you most today, or search every listing. These work in '
            'every state. For your state\'s own offices, <a href="states.html">choose your state</a>. '
            'Someone you love in jail or prison? <a href="inside.html">Start here</a>.')
    glance = needs_glance(''.join(rows), 'At a glance: every need on this page')
    body = (hero('Find help', lede, glance) + finder('Search every listing', 'shelter, rent, WIC, child care…') + needs(''.join(rows))
            + '<section class="wrap slim"><p>In danger right now? Call 911. Domestic violence shelter addresses are never listed here, for safety.</p></section>')
    return page(data, 'help.html', 'Find help for moms',
                'Free national help for moms: crisis lines, housing and shelter, food and bills, pregnancy and baby, kids who learn differently and single parents.', body,
                head_extra=structured_data(breadcrumbs(data, [('Find help', 'help.html')])), slots=('topic-help', 'topic'))


CHRISTMAS_ROWS = [
    ('xmas-gifts', '🎁', 'Toys and gifts for your kids', 'Toys for Tots, Angel Tree, a letter to Santa, and help for military families.',
     ['us-toys-for-tots', 'us-angel-tree', 'us-operation-santa', 'us-pf-angel-tree', 'us-homefront-holidays', 'us-211-help']),
    ('xmas-meal', '🍽️', 'A holiday meal', 'Food banks and pantries, holiday food boxes, and SNAP.',
     ['us-food-bank', 'us-211-help', 'us-snap', 'us-homefront-holidays']),
    ('xmas-heat', '🔥', 'The heat bill', 'Help paying for heat, and what to do about a shutoff notice.',
     ['us-liheap', 'us-211-help']),
    ('xmas-you', '☕', 'Take care of you', 'The holidays can be hard. Someone to talk to, any hour.',
     ['us-parent-helpline', 'us-tlc-mama', 'us-988']),
]


T4T_SHADES = [(5, 't1'), (12, 't2'), (24, 't3'), (44, 't4'), (10 ** 6, 't5')]  # campaigns up to n: shade


def campaigns_map(data, by):
    """The states as tiles, each with its two letters and its number of Toys for Tots campaigns, a link to that state's
    card below it. The number is written on the tile; the shade only repeats it."""
    names = {s['abbr']: s['name'] for s in data['states']}
    tiles = ''
    # In the order of the cards below (by name); each tile's place on the map comes from US_TILES. On a phone the
    # tiles become a row of chips in this order.
    for a, r, c in sorted(US_TILES, key=lambda t: names.get(t[0], t[0])):
        n = len(by.get(a, []))
        if a not in names or not n:
            continue
        shade = next(cls for top, cls in T4T_SHADES if n <= top)
        tiles += (f'<li style="grid-area:{r + 1}/{c + 1}"><a class="{shade}" href="#tft-{a.lower()}">{a} <small>{n}</small>'
                  f'<span class="sr"> {"campaign" if n == 1 else "campaigns"} in {esc(names[a])}</span></a></li>')
    more = ' · '.join(f'<a href="#tft-{t.lower()}">{esc(TERRITORIES[t])} ({len(by[t])})</a>' for t in sorted(TERRITORIES) if t in by)
    return (f'<nav class="tftnav" aria-label="Toys for Tots campaigns by state"><p class="quiet">Tap your state to jump to its campaigns. '
            f'The number is how many local campaigns it has.</p><ul class="usgrid tftmap">{tiles}</ul>'
            + (f'<p class="quiet">Also: {more}</p>' if more else '') + '</nav>')


def christmas_when(nat):
    """When Christmas help closes, from the listings on the page: Angel Tree sign-ups in the fall, Toys for Tots
    campaigns from the end of November into December, Operation Santa's postmark date, and 211 any day."""
    santa = re.search(r'postmarked by ([A-Z][a-z]+ \d{1,2}), \d{4}', nat['us-operation-santa']['how'])
    if not santa:
        sys.exit('scripts/ymt_build.py: the Operation Santa listing no longer gives a postmark date; update christmas_when')
    steps = [('gift', 'In the fall', 'Many Salvation Army <a href="#xmas-gifts--us-angel-tree">Angel Tree</a> sign-ups close.'),
             ('gift', 'Late November and December', '<a href="#toys-for-tots">Toys for Tots campaigns</a> close, each on its own date.'),
             ('letter', santa.group(1), 'Last postmark for a letter to <a href="#xmas-gifts--us-operation-santa">Operation Santa</a>.'),
             ('phone', 'Any day', 'If something has closed, dial <a href="tel:211">211</a> and ask what is still open.')]
    items = ''.join(f'<li>{icon(ico)}<span><strong>{esc(when)}</strong> {text}</span></li>' for ico, when, text in steps)
    return (f'<section class="wrap"><figure class="when"><figcaption>When Christmas help closes</figcaption>'
            f'<ol role="list">{items}</ol></figure></section>')


def build_christmas(data):
    """Christmas help in one place: the national programs by need, then every Toys for Tots campaign by state."""
    nat = {r['id']: r for r in data['resources']}
    rows = []
    for rid, icon, label, summary, ids in CHRISTMAS_ROWS:
        sec = {'id': rid, 'label': label, 'icon': icon, 'summary': summary}
        rows.append(need(sec, [nat[i] for i in ids], '', {i: f'{rid}--{i}' for i in ids}))
    by = xmas.by_state()
    order = [s['abbr'] for s in data['states']] + sorted(k for k in by if k in TERRITORIES)
    tft = campaigns_map(data, by) + ''.join(campaigns_card(data, st, by[st], f'tft-{st.lower()}') for st in order if st in by)
    total = sum(len(v) for v in by.values())
    sec = {'id': 'toys-for-tots', 'label': 'Toys for Tots near you, state by state', 'icon': '🧸',
           'summary': f'All {total} local campaigns, each with its own website and sign-up dates.'}
    rows.append(need(sec, [], '', None, tft))
    options = '<option value="">Choose your state</option>' + ''.join(
        f'<option value="states/{s["abbr"].lower()}.html#christmas">{esc(s["name"])}</option>' for s in data['states'])
    pick = (f'<div class="statepick"><label for="statepick">Christmas help in your state</label>'
            f'<select id="statepick" data-state-pick>{options}</select>'
            f'<a href="county.html">Find your county</a><a href="#toys-for-tots">Toys for Tots campaigns</a></div>')
    late = ('<div class="localbox xmasnote"><strong>Late in the season?</strong> Many Angel Tree sign-ups closed in the fall, '
            'and each Toys for Tots campaign closes on its own date, some at the end of November and some in December. '
            'Start with your area\'s Toys for Tots campaign today. If something has closed, dial <a href="tel:211">211</a> and ask: '
            '\u201cWhat Christmas help is still open for my kids?\u201d Never pay to sign up for free Christmas help.</div>')
    lede = ('Worried about Christmas for your kids this year? Here is where to ask for toys, a holiday meal and help with the '
            'heat bill. Free, and no sign-up here. Pick what you need, or search for your town.')
    site = data['site']
    ohio = (f'<section class="wrap"><div class="localbox"><strong>Ohio mom?</strong> '
            f'<a href="ohio/holidays.html">Christmas and holiday help in Ohio</a> lists Ohio\'s own programs, holiday meals, '
            f'and lights and Santa close to home.</div></section>')
    body = (hero('🎄 Christmas help for moms', lede, pick + late) + christmas_when(nat)
            + finder('Search Christmas help', 'toys, Columbus, heat bill…') + needs(''.join(rows)) + ohio
            + '<section class="wrap slim"><p>In danger right now? Call 911. The holidays can be hard: you can call or text 988 any hour.</p></section>')
    desc = ('Free Christmas help for moms in every state: local Toys for Tots campaigns, Angel Tree, '
            'Operation Santa, holiday meals and help with the heat bill.')
    base = f"https://{site['domain']}/"
    about = {'@type': 'CollectionPage', '@id': base + 'christmas.html', 'url': base + 'christmas.html',
             'name': 'Christmas help for moms', 'description': desc, 'inLanguage': 'en', 'isPartOf': {'@id': base + '#website'}}
    return page(data, 'christmas.html', 'Christmas help for moms: toys, gifts and holiday meals', desc, body,
                head_extra=structured_data(about, breadcrumbs(data, [('Christmas help', 'christmas.html')])),
                slots=('topic-help', 'topic'))


INSIDE_ROWS = [
    ('inside-touch', '📞', 'Find them, and stay in touch', 'Where they are held, visits, phone calls, mail and putting money on their account.',
     ['us-bop-locator', 'us-bop-contact']),
    ('inside-kids', '🧸', 'Helping your children', 'Talking with young children about it, getting ready for a visit, and a Christmas gift from their parent.',
     ['us-sesame-incarceration', 'us-pf-angel-tree']),
    ('inside-home', '🏡', 'Coming home', 'Local help after release, free legal help, clearing a record, and help for veterans and their families.',
     ['us-211-help', 'us-legal-aid', 'us-record-relief', 'us-vet-justice']),
    ('inside-you', '☕', 'Take care of you', 'When someone you love is inside, you are carrying a lot too. Someone to talk to, any hour.',
     ['us-parent-helpline', 'us-988']),
]


def build_inside(data):
    """For moms and caregivers with a loved one in jail or prison or coming home: national help by need, then Ohio."""
    nat = {r['id']: r for r in data['resources']}
    rows = []
    for rid, icon, label, summary, ids in INSIDE_ROWS:
        sec = {'id': rid, 'label': label, 'icon': icon, 'summary': summary}
        rows.append(need(sec, [nat[i] for i in ids], '', {i: f'{rid}--{i}' for i in ids}))
    first = ('<div class="localbox"><strong>Where to start.</strong> Find out where your loved one is held and how that '
             'jail or prison handles visits, calls and money: each one sets its own rules. Read them before you pay or travel. '
             'Your state\'s prison system has its own search; for a county jail, call the county sheriff\'s office.</div>')
    first += ('<figure class="steps-fig"><figcaption class="sr">Where to start, step by step</figcaption>'
              + flow([('pin', 'Find out where they are held: your state\'s prison search, or the county sheriff\'s office for a county jail.'),
                      ('doc', 'Read how that jail or prison handles visits, calls and money. Each one sets its own rules.'),
                      ('calendar', 'Then pay or travel, once you know the rules. <a href="#inside-touch">Visits, calls and money</a>')],
                     'flow across') + '</figure>')
    lede = ('When your partner, your child\'s parent or someone else you love is in jail or prison, or coming home: '
            'staying in touch, helping your kids, and help for you. Free, and no sign-up.')
    ohio = ('<section class="wrap"><div class="localbox"><strong>In Ohio?</strong> '
            '<a href="ohio/help/family-inside.html">A loved one in jail or prison, in Ohio</a> covers prison visits and video visits, '
            'calls and money through the state\'s provider, what every Ohio jail must offer, help for relatives raising the children, '
            'and coming home.</div></section>')
    body = (hero('🕊️ Someone I love is in jail or prison', lede, first) + finder('Search this page', 'visit, money, kids, release…')
            + needs(''.join(rows)) + ohio
            + '<section class="wrap slim"><p>In danger right now? Call 911. Having a really hard time? You can call or text 988 any hour.</p></section>')
    desc = ('For moms and caregivers when someone you love is in jail or prison: visits, calls and money, '
            'helping your children, coming home, and support for you.')
    site = data['site']
    base = f"https://{site['domain']}/"
    about = {'@type': 'CollectionPage', '@id': base + 'inside.html', 'url': base + 'inside.html',
             'name': 'Someone I love is in jail or prison', 'description': desc, 'inLanguage': 'en', 'isPartOf': {'@id': base + '#website'}}
    return page(data, 'inside.html', 'When someone you love is in jail or prison: help for moms', desc, body,
                head_extra=structured_data(about, breadcrumbs(data, [('Someone I love is in jail or prison', 'inside.html')])))


KINSHIP_ROWS = [
    ('kin-start', '\U0001f9ed', 'Where to start', 'A navigator who knows the programs, and the fact sheet for your state.',
     ['us-kin-navigator', 'us-grandfacts', 'us-211-help']),
    ('kin-money', '\U0001f9fa', 'Money and health coverage for the child', 'Cash help for the child, Medicaid or CHIP, and food.',
     ['us-tanf-child-only', 'us-insure-kids', 'us-snap', 'us-wic']),
    ('kin-legal', '\u2696\ufe0f', 'Custody, guardianship, foster care and school', 'Free legal help to choose the right papers, and what a foster license means.',
     ['us-legal-aid', 'us-kin-foster-license', 'us-gu-grandfamilies']),
    ('kin-you', '\u2615', 'Support for you', 'Other grandparents who understand, a break, and someone to talk to.',
     ['us-kin-caregiver-support', 'us-parent-helpline', 'us-samhsa']),
]


def kinship_paths():
    """The legal custody and foster license note above it, drawn as two short paths, one for each way the children may
    have come to you, that meet at free legal aid. Every step says only what the note says."""
    custody = flow([('people', 'Caring for the children on your own, with no court order'),
                    ('court', 'A court can give you legal custody or guardianship'),
                    ('book', 'That lets you enroll them in school and take them to the doctor')], 'flow path')
    foster = flow([('house-heart', 'Children services placed the children with you'),
                   ('doc', 'You can also ask about becoming a licensed foster parent'),
                   ('coins', 'A foster license comes with foster care payments')], 'flow path')
    return ('<figure class="paths"><figcaption>Two paths, depending on how the children came to you</figcaption>'
            f'<div class="pathcols">{custody}<p class="pathor">or</p>{foster}</div>'
            f'<p class="pathjoin">{icon("scales")}<span>Each choice affects money, your rights and the parents\' rights differently, '
            'so talk with <a href="#kin-legal--us-legal-aid">free legal aid</a> before you sign anything.</span></p></figure>')


def build_kinship(data):
    """Grandparents and other relatives raising children (kinship care, "grandfamilies"): the national listings by need,
    a plain-words note on legal custody and a foster license, and the way to Ohio's own page."""
    nat = {r['id']: r for r in data['resources']}
    rows = []
    for rid, icon, label, summary, ids in KINSHIP_ROWS:
        sec = {'id': rid, 'label': label, 'icon': icon, 'summary': summary}
        rows.append(need(sec, [nat[i] for i in ids], '', {i: f'{rid}--{i}' for i in ids}))
    lede = ('You stepped in when the children needed you. Whether you are their grandmother, aunt, uncle, big sister or a family friend, '
            'there is help for them and for you. Pick what you need first.')
    choose = ('<section class="wrap"><div class="localbox"><strong>Legal custody or a foster license?</strong> '
              'If you are caring for the children on your own, with no court order, you may need papers to enroll them in school or to take them to the doctor. '
              'A court can give you legal custody or guardianship, which lets you make those decisions. '
              'If children services placed the children with you, you can also ask about becoming a licensed foster parent, which comes with foster care payments. '
              'Each choice affects money, your rights and the parents\' rights differently, so talk with free legal aid before you sign anything. '
              'Your <a href="https://grandfamilies.org/state-fact-sheets" rel="noopener">state\'s GrandFacts sheet</a> lists the options where you live.</div>'
              + kinship_paths() + '</section>')
    parent = ('<section class="wrap"><div class="localbox"><strong>If a parent is struggling with addiction.</strong> Many grandparents are raising grandchildren because of opioids or other drugs. '
              'The <a href="#kin-you--us-samhsa">SAMHSA National Helpline</a> is free and private, any hour, for the parent or for you. '
              'Taking care of yourself is part of taking care of them.</div></section>')
    ohio = ('<section class="wrap"><div class="localbox"><strong>In Ohio?</strong> '
            '<a href="ohio/help/kinship.html">Raising a grandchild in Ohio</a> covers OhioKAN, Ohio\'s kinship programs, '
            'the grandparent power of attorney and caretaker affidavit, cash help, Medicaid and school enrollment.</div></section>')
    body = (hero('Raising a grandchild or a relative\'s child', lede)
            + finder('Search this page', 'custody, cash help, Medicaid…') + needs(''.join(rows)) + choose + parent + ohio
            + '<section class="wrap slim"><p>In danger right now? Call 911. To report a child in danger, call the Childhelp hotline at <a href="tel:8004224453">800-422-4453</a>.</p></section>')
    desc = ('Raising your grandkids? Find a kinship navigator, cash help and Medicaid for the child, '
            'custody or foster license options, and support for you.')
    base = f"https://{data['site']['domain']}/"
    about = {'@type': 'CollectionPage', '@id': base + 'kinship.html', 'url': base + 'kinship.html',
             'name': 'Raising a grandchild or a relative\'s child', 'description': desc, 'inLanguage': 'en', 'isPartOf': {'@id': base + '#website'}}
    return page(data, 'kinship.html', 'Raising a grandchild or a relative\'s child: help for grandparents and kinship caregivers', desc, body,
                head_extra=structured_data(about, breadcrumbs(data, [('Find help', 'help.html'), ('Raising a grandchild', 'kinship.html')])),
                slots=('topic-help', 'topic'))

def build_connect(data):
    prim = [r for r in data['resources'] if r['section'] == 'connect']
    also = [r for r in data['resources'] if 'connect' in r.get('also', [])]
    site = data['site']
    tiles = [('people', 'groups', 'Groups for moms', len(prim)), ('cup', 'hard-days', 'Support for the hard days', len(also))]
    glance = ('<nav class="glance needglance" aria-label="At a glance: this page"><ul>' + ''.join(
        f'<li><a href="#{sid}">{icon(ico)}<span>{label} <small><b>{n}</b> listing{"s" if n != 1 else ""}</small></span></a></li>'
        for ico, sid, label, n in tiles if n) + '</ul></nav>')
    body = hero('Meet other moms', 'New in town, home all day with a baby, or just want someone who gets it? Moms groups, feeding '
                'groups and people who have been there, near you or online.', glance) + f'''
<section class="group wrap" id="groups"><h2>Groups for moms</h2><p class="quiet">Local chapters and meetups run by volunteers. Groups differ, so ask how one runs before you go.</p>{cards(prim)}</section>
<section class="group wrap" id="hard-days"><h2>Support for the hard days</h2><p class="quiet">Feeding help and support lines from people who have been there.</p>{cards(also, '', {r['id']: 'connect--' + r['id'] for r in also})}</section>
<section class="wrap"><div class="localbox"><strong>Ohio mom?</strong> <a href="{esc(site['ohio_path'])}">OhioMom</a> lists Ohio groups, meetups and events by region and county.</div></section>
<section class="wrap cta"><h2>Run a group, or know a good one?</h2><p>If it is free or low cost and good for moms, we want to list it. Nobody pays to be listed here.</p><p><a class="btn big" href="report.html">Tell us about it</a></p></section>'''
    return page(data, 'connect.html', 'Meet other moms',
                'Moms groups, breastfeeding groups and support for the hard days, in person and online, across the U.S.', body,
                head_extra=structured_data(breadcrumbs(data, [('Meet other moms', 'connect.html')])), slots=('topic-connect', 'topic'))


# The U.S. as a grid of equal tiles, roughly where each state sits on the map: (abbreviation, row, column), row by row.
US_TILES = [
    ('AK', 0, 0), ('ME', 0, 10),
    ('WI', 1, 5), ('VT', 1, 9), ('NH', 1, 10),
    ('WA', 2, 0), ('ID', 2, 1), ('MT', 2, 2), ('ND', 2, 3), ('MN', 2, 4), ('IL', 2, 5), ('MI', 2, 6), ('NY', 2, 8), ('MA', 2, 9),
    ('OR', 3, 0), ('NV', 3, 1), ('WY', 3, 2), ('SD', 3, 3), ('IA', 3, 4), ('IN', 3, 5), ('OH', 3, 6), ('PA', 3, 7), ('NJ', 3, 8),
    ('CT', 3, 9), ('RI', 3, 10),
    ('CA', 4, 0), ('UT', 4, 1), ('CO', 4, 2), ('NE', 4, 3), ('MO', 4, 4), ('KY', 4, 5), ('WV', 4, 6), ('VA', 4, 7), ('MD', 4, 8),
    ('DE', 4, 9),
    ('AZ', 5, 1), ('NM', 5, 2), ('KS', 5, 3), ('AR', 5, 4), ('TN', 5, 5), ('NC', 5, 6), ('SC', 5, 7), ('DC', 5, 8),
    ('OK', 6, 3), ('LA', 6, 4), ('MS', 6, 5), ('AL', 6, 6), ('GA', 6, 7),
    ('HI', 7, 0), ('TX', 7, 3), ('FL', 7, 8),
]


def state_grid(data):
    """Every state and D.C. as one tile with its two letters, each a link to its page. Plain links in a list, in reading
    order (row by row), so it works with no script, from the keyboard and with a screen reader, which reads each
    tile's full name after its letters."""
    names = {s['abbr']: s['name'] for s in data['states']}
    missing = sorted(set(names) - {a for a, _, _ in US_TILES})
    if missing:
        sys.exit(f'scripts/ymt_build.py: no tile in US_TILES for {", ".join(missing)}')
    tiles = ''.join(f'<li style="grid-area:{r + 1}/{c + 1}"><a href="states/{a.lower()}.html" title="{esc(names[a])}">'
                    f'{a}<span class="sr"> {esc(names[a])}</span></a></li>' for a, r, c in US_TILES if a in names)
    return f'<ul class="usgrid" aria-label="Map of the states">{tiles}</ul>'


def build_states_index(data):
    items = ''.join(f'<li><a href="states/{s["abbr"].lower()}.html">{esc(s["name"])}<small>{s["abbr"]}</small></a></li>' for s in data['states'])
    n_dc = sum(1 for s in data['states'] if s['abbr'] == 'DC')
    tiles = [glance_item('pin', len(data['states']), f'state pages, D.C. included' if n_dc else 'state pages'),
             glance_item('house', len(data['counties']), 'county pages', 'county.html'),
             glance_item('heart', sum(1 for r in data['resources'] if r['scope'] == 'US'), 'national listings', 'help.html')]
    glance = f'<figure class="glance"><figcaption>On this site</figcaption><ul>{"".join(tiles)}</ul></figure>'
    body = (hero('Help by state', 'SNAP, WIC, health coverage and child care help are run state by state, so your state\'s page has '
                   'the right office and phone number. Tap yours on the map, or open the list.', glance)
            + f'<section class="wrap mapwrap">{state_grid(data)}'
            f'<details class="maplist"><summary>All {len(data["states"])} as a list</summary><ul class="statelist">{items}</ul></details>'
            '<p class="note">Looking for help close to home? Open your state for the list of its counties, or <a href="county.html">find your county by ZIP code</a>. Looking for something national? See <a href="help.html">Find help</a>. Outside the U.S.? <a href="world.html">Choose your country</a>.</p></section>')
    return page(data, 'states.html', 'Help by state',
                'Pick your state for SNAP, WIC, child care, health coverage, disability help and domestic violence resources.', body,
                head_extra=structured_data(breadcrumbs(data, [('Help by state', 'states.html')])))


def biggest_counties(data, st, n=2):
    """The state's most populous counties (Census 2024 estimates), most people first."""
    return sorted((c for c in data['counties'] if c['state'] == st), key=lambda c: -c.get('pop', 0))[:n]


def fits(desc):
    """A description short enough that search results show it whole, counted as it is written in the page."""
    return len(esc(desc)) <= 158


def state_intro(data, s):
    """The opening lines of a state page, written to a mom in that state: the state's own name for the program she is
    most likely to need and not know the name of (early intervention), and the counties most of its moms live in."""
    name, code = esc(s['name']), s['abbr'].lower()
    whose = 'the District\'s' if s['abbr'] == 'DC' else f'{name}\'s'
    out = (f'Raising kids in {name} and need a hand? Pick what you need below: {whose} own offices come first, then '
           'national lines that work anywhere.')
    ei = s.get('early_intervention', {}).get('name')
    if ei:
        out += (f' If your baby or toddler seems behind, {whose} early intervention program is '
                f'<a href="#{code}-ei">{esc(ei)}</a>, and you can call it yourself.')
    big = biggest_counties(data, s['abbr'])
    if len(big) == 2 and big[0]['name'] != s['name']:
        links = ' or '.join(f'<a href="{code}/{county_slug(c["name"])}.html">{esc(c["name"])}</a>' for c in big)
        out += (f' For housing, legal aid and clinics close to home, open your {esc(county_noun(s["abbr"]))}, such as {links}, '
                'from the list below.')
    return out + ' <a href="../states.html">Choose another state</a>.'


def state_desc(s):
    """Search-result line for a state page: the state's own early intervention program by name, then the rest."""
    ei = s.get('early_intervention', {}).get('name')
    tries = []
    if ei:
        tries.append(f'Free help for moms in {s["name"]}: SNAP, WIC, energy bills, housing and shelter, child care, and {ei} '
                     'for babies and toddlers.')
        tries.append(f'Free help for moms in {s["name"]}: SNAP, WIC, housing, child care and {ei}.')
    tries.append(f'Free help for moms in {s["name"]}: housing and shelter, SNAP, WIC, child care, health coverage and disability services.')
    return next((t for t in tries if fits(t)), tries[-1])


def build_state(data, s):
    secs = sec_map(data)
    recs = lib.state_records(s, data)
    have = {kind(r) for r in recs}
    # The state's own offices first, then every national listing the state does not already have its own version of.
    everything = recs + [r for r in data['resources'] if REPLACED_BY_STATE.get(r['id']) not in have]
    camps = xmas.by_state().get(s['abbr'], [])
    rows = ''.join(row(secs[sid], everything, '../', campaigns_card(data, s['abbr'], camps) if sid == 'christmas' and camps else '')
                   for sid in STATE_SECTIONS)
    local = ''
    if s.get('local_site'):
        ls = s['local_site']
        local = f'<div class="localbox"><strong>Ohio mom?</strong> <a href="../{esc(ls["path"])}">{esc(ls["name"])}</a> is {esc(ls["what"][0].lower() + ls["what"][1:])}</div>'
    intro = state_intro(data, s)
    # A country with the same name (Georgia): say which is which, and link to the other.
    for c in data['world']['countries']:
        if c.get('us_state') == s['abbr']:
            intro += (f' This page is the U.S. state. Looking for the country? '
                      f'<a href="../countries/{c["slug"]}.html">{esc(c["name"])}</a>.')
    body = (hero(f'{esc(s["name"])}: help for moms', intro, county_pick(data, s) + local, 'slim')
            + urgent_strip(data, '../', '#help-now')
            + finder(f'Search every {s["name"]} listing', 'shelter, rent, WIC, child care…') + needs(rows)
            + county_list(data, s)
            + '<section class="wrap slim"><p><strong>Meet other moms.</strong> Find a group near you or online. <a href="../connect.html">Meet moms</a></p></section>'
            + kind_word('#take-care', '../') + closing('../'))
    path = f'states/{s["abbr"].lower()}.html'
    desc = state_desc(s)
    base = f"https://{data['site']['domain']}/"
    about = {'@type': 'CollectionPage', '@id': base + path, 'url': base + path, 'name': f'{s["name"]}: help for moms',
             'description': desc, 'inLanguage': 'en', 'isPartOf': {'@id': base + '#website'},
             'about': {'@type': 'State', 'name': s['name']}}
    trail = breadcrumbs(data, [('Help by state', 'states.html'), (s['name'], path)])
    return page(data, path, f'{s["name"]}: help for moms', desc, body, head_extra=structured_data(about, trail),
                slots=(f'state-{s["abbr"].lower()}', 'state'), scripts=kind_word_scripts('../'))


# ---------------------------------------------------------------- outside the U.S.
WORLD_SECTIONS = ['help-now', 'housing', 'food-bills', 'pregnancy-baby', 'kids-differently', 'single-parent', 'take-care', 'connect']


def country_pick(world, root=''):
    options = '<option value="">Choose your country</option>' + ''.join(
        f'<option value="{root}countries/{c["slug"]}.html">{esc(c["name"])}</option>' for c in world['countries'])
    return (f'<div class="statepick"><label for="countrypick">Start with your country</label>'
            f'<select id="countrypick" data-state-pick>{options}</select><a href="{root}world.html">All countries</a></div>')


# A country whose English name takes "the" in a sentence: "in the Philippines", "in the United Kingdom". Headings, titles,
# lists and the map keep the plain name ("The Bahamas", "Philippines"); only words inside a sentence use in_name. A name
# written with a capital The ("The Bahamas") is lowered by itself; any other the-country is listed here by its code.
THE_COUNTRIES = {
    'AE',  # the United Arab Emirates
    'BS',  # the Bahamas
    'CD',  # the Democratic Republic of the Congo
    'CF',  # the Central African Republic
    'CG',  # the Republic of the Congo
    'CZ',  # the Czech Republic
    'DO',  # the Dominican Republic
    'GB',  # the United Kingdom
    'GM',  # the Gambia
    'KM',  # the Comoros
    'MH',  # the Marshall Islands
    'MV',  # the Maldives
    'NL',  # the Netherlands
    'PH',  # the Philippines
    'SB',  # the Solomon Islands
    'US',  # the United States
    'VA',  # the Vatican
}


def in_name(c):
    """The country's name as it reads inside a sentence: "in the Philippines", "in the Bahamas", "in Canada"."""
    name = c['name']
    if name.startswith('The '):
        return 'the ' + name[4:]
    return ('the ' + name) if c.get('code') in THE_COUNTRIES else name


def possessive(c):
    """"the Philippines' own services", "Canada's own services": a plural the-name takes the apostrophe alone."""
    name = in_name(c)
    return name + ("'" if name.startswith('the ') and name.endswith('s') else "'s")


# The U.S. summaries name U.S. programs (WIC, Head Start), so the pages outside the U.S. say it their own way.
WORLD_SUMMARIES = {
    'help-now': 'Safety, crisis support and urgent needs. Free, and most lines are open any hour.',
    'housing': 'A safe place to stay, and help leaving an unsafe home.',
    'food-bills': 'Family payments, child benefits and one number that finds local help.',
    'pregnancy-baby': 'Breastfeeding help, maternity benefits and support with a new baby.',
    'kids-differently': 'Help lines for children, and for parents worried about a child.',
    'single-parent': 'Parenting alone, separating, and families split across borders.',
    'take-care': 'Someone to talk to on the hard days, in pregnancy and after.',
    'connect': 'Groups where moms meet other moms, near you or online.',
}


def world_rows(data, records, root='', country=None):
    """The needs, each closed until she opens it. On world.html only the needs that have something in them. On a
    country page every need, in the same order on every country: a need with nothing listed for the country yet says
    so, gives the emergency number and asks for a service to add, so a thin page reads the same as a full one."""
    secs = {sid: dict(sec, summary=WORLD_SUMMARIES.get(sid, sec['summary'])) for sid, sec in sec_map(data).items()}
    out = ''
    for sid in WORLD_SECTIONS:
        if any(r['section'] == sid or sid in r.get('also', []) for r in records):
            out += row(secs[sid], records, root)
        elif country:
            out += empty_need(secs[sid], country, root)
    return out


def empty_need(sec, c, root=''):
    """A need with no listing for this country yet: the same row as any other, with a plain line where the cards go."""
    return (f'<details class="need" id="{sec["id"]}"><summary><span class="ico" aria-hidden="true">{sec["icon"]}</span>'
            f'<h2>{esc(sec["label"])}</h2><span class="nsum">{esc(sec["summary"])}</span>'
            f'<span class="ncount">Not listed yet</span></summary><p class="pending">We have not listed a service in '
            f'{esc(in_name(c))} for this yet. If you or your child are in danger, call {esc(c["emergency"]["number"])}, or open '
            f'<a href="#help-now">Get help now</a>. Know a free service for moms here? <a href="{root}report.html">Tell us</a> '
            f'and we will add it.</p></details>')


def emergency_card(c):
    e = c['emergency']
    return (f'<li><a class="phonecard" href="tel:{esc(e["number"])}">Call {esc(e["number"])}'
            f'<small>Emergency in {esc(in_name(c))}: {esc(e["label"])}</small></a></li>')


WORLD_MAP = lib.DATA / 'world-map.json'  # Natural Earth outlines, made by scripts/world_map_data.py
DOT_AREA = 24  # a country drawn smaller than this (in square map units) also gets a dot, so it can be found and tapped (Albania, Armenia and North Macedonia, at 22, among them)


def world_map(world):
    """The map on world.html: every country, grey; every country with a page, pink and a link to it (the United States
    links to the state pages). A country too
    small to draw at this scale (Singapore, Barbados) is a dot at its label point, and a very small one gets a dot too.
    A new country in world.json is shaded the next time this runs; one that is not on the map stops the build."""
    m = json.loads(WORLD_MAP.read_text(encoding='utf-8'))
    covered = {c['code'] for c in world['countries']}
    shapes = {c['code']: c for c in m['countries'] if c.get('code')}
    points = {p['code']: p for p in m['points']}
    missing = sorted(covered - set(shapes) - set(points))
    if missing:
        sys.exit(f'scripts/ymt_build.py: {", ".join(missing)} not in {WORLD_MAP.relative_to(ROOT)}')
    # The United States has no country page: it links to the states instead.
    targets = [(c['slug'], c['code'], c['name'], f'countries/{c["slug"]}.html') for c in world['countries']]
    if 'US' in shapes and 'US' not in covered:
        targets.append(('united-states', 'US', 'United States: help by state', 'states.html'))
    linked = {code for _, code, _, _ in targets}
    grey = ''.join(f'<path d="{c["d"]}"/>' for c in m['countries'] if c.get('code') not in linked)
    links = ''
    for _, code, name, href in sorted(targets):
        shape = shapes.get(code)
        x, y = (shape or points[code])['label']
        inner = f'<title>{esc(name)}</title>' + (f'<path d="{shape["d"]}"/>' if shape else '')
        if not shape or shape['area'] < DOT_AREA:
            inner += f'<circle cx="{x}" cy="{y}" r="5"/>'
        links += f'<a href="{href}" aria-label="{esc(name)}" data-country="{code}">{inner}</a>'
    return (f'<svg class="worldmap" viewBox="0 0 {m["width"]} {m["height"]}" role="group" '
            f'aria-label="World map. The {len(covered)} countries with their own page are shaded and link to it.">'
            f'<g class="land" aria-hidden="true">{grey}</g><g class="covered">{links}</g></svg>')


def build_world(data):
    world = data['world']
    items = ''.join(f'<li><a href="countries/{c["slug"]}.html"><span aria-hidden="true">{c["flag"]}</span> {esc(c["name"])}'
                    f'<small>Emergency {esc(c["emergency"]["number"])}</small></a></li>' for c in world['countries'])
    lede = ('Raising children outside the U.S.? Pick your country for its own emergency number, crisis lines, family payments '
            'and support, or use the help below, which works in any country. Free, private, no sign-up.')
    n = len(world['countries'])
    # The map comes first to the eye, so one line above it keeps the way to an emergency number first of all.
    danger = '<p class="dangerline"><a href="#now">In danger right now? Find your country\'s emergency number</a></p>'
    top = hero('Help for moms, anywhere in the world', lede, country_pick(world)).replace('<div class="wrap">', '<div class="wrap">' + danger, 1)
    body = (top
            + f'<section class="wrap mapwrap" id="countries"><h2>Find your country</h2>'
            f'<p class="quiet">The {n} countries in pink have their own page, and the United States leads to its states. '
            f'Tap yours, or open the list.</p>{world_map(world)}'
            f'<details class="maplist"><summary>All {n} countries as a list</summary><ul class="statelist">{items}</ul></details>'
            '<p class="note">More countries are on the way. Living in the U.S.? <a href="states.html">Choose your state</a>. '
            'Know a free service for moms in your country? <a href="report.html">Tell us</a>.</p></section>'
            + '<section class="wrap now" id="now"><h2>In danger right now?</h2>'
            '<p class="quiet">Call your country\'s emergency number. Here are the numbers for the countries we cover so far.</p>'
            f'<ul class="phonecards">{"".join(emergency_card(c) for c in world["countries"])}</ul></section>'
            + finder('Search help that works in any country', 'helpline, breastfeeding, custody…', NO_MATCH_WORLD)
            + needs(world_rows(data, world['worldwide'])))
    desc = ('Free help for moms outside the U.S.: crisis and domestic violence lines, family payments, breastfeeding and '
            'postpartum support, country by country.')
    base = f"https://{data['site']['domain']}/"
    about = {'@type': 'CollectionPage', '@id': base + 'world.html', 'url': base + 'world.html', 'name': 'Help for moms, anywhere in the world',
             'description': desc, 'inLanguage': 'en', 'isPartOf': {'@id': base + '#website'}}
    return page(data, 'world.html', 'Help for moms around the world', desc, body,
                head_extra=structured_data(about, breadcrumbs(data, [('Worldwide', 'world.html')])), slots=('topic-help', 'topic'),
                danger='In danger right now? Call your local emergency number.')


# What each need is for, said to a mother, for the opening lines of a country page.
FOR_WHAT = {
    'help-now': 'for urgent help', 'housing': 'if home is not safe', 'food-bills': 'for money, food and family payments',
    'pregnancy-baby': 'for pregnancy and a new baby', 'kids-differently': 'if you are worried about a child',
    'single-parent': 'if you are raising children on your own', 'take-care': 'when you need someone to talk to',
    'connect': 'to meet other mothers',
}


def lower_first(text):
    """'Someone to talk to' -> 'someone to talk to', but 'NHS 111' and 'WhatsApp line' stay as they are."""
    return text[0].lower() + text[1:] if len(text) > 1 and text[1].islower() else text


def own_lines(c, n=3):
    """The country's own listings, the urgent ones first, as they lead its page."""
    return sorted(c['resources'], key=lambda r: (not r.get('urgent'), c['resources'].index(r)))[:n]


def country_intro(c):
    """The opening lines of a country page, written to a mother there: the emergency number, the country's own lines by
    name and what each is for, and the language the day's kind word is in."""
    where = esc(re.sub(r' \(.*\)$', '', in_name(c)))  # "Georgia (the country)" reads as Georgia here; the page says which
    out = f'Raising children in {where}? If you or your child are in danger, call {esc(c["emergency"]["number"])}.'
    mine = own_lines(c)
    if mine:
        named = [f'<a href="#{esc(r["id"])}">{esc(r["name"])}</a>' + ('' if r['name'].endswith(')') else
                 f' ({esc(lower_first(r["chip"]) if r.get("chip") else FOR_WHAT.get(r["section"], "for help"))})') for r in mine]
        lst = named[0] if len(named) == 1 else ', '.join(named[:-1]) + ' and ' + named[-1]
        whose = re.sub(r' \(.*\)', '', possessive(c))
        out += f' {esc(whose[0].upper() + whose[1:])} own services come first, such as {lst}.'
        out += ' Then come lines that work in any country.'
    else:
        out += f' We have not listed {esc(re.sub(r" [(].*[)]", "", possessive(c)))} own services yet, so the help below is the kind that works in any country.'
    out += ' Pick what you need, or search.'
    local = extras.local_language(c.get('lang'))
    if local:
        lname = extras.read_translation(local[0]).get('name', '')
        lname = re.sub(r' \(.*\)$', '', lname)
        if lname:
            out += f' Today\'s kind word, near the end of the page, is in {esc(lname)}, with the English under it.'
    out += ' <a href="../world.html">Choose another country</a>.'
    return out


def country_desc(c):
    """Search-result line for a country page: the emergency number and the country's own lines by name."""
    head = f'Free help for moms in {in_name(c)}: emergency {c["emergency"]["number"]}'
    names = [r['name'] for r in own_lines(c)]
    tail = ', crisis lines, family payments, breastfeeding and postpartum support.'
    for k in range(len(names), 0, -1):
        d = head + ', ' + ', '.join(names[:k]) + ' and more help for mothers.'
        if fits(d):
            return d
    d = head + tail
    return d if fits(d) else f'Free help for moms in {in_name(c)}: emergency {c["emergency"]["number"]}, crisis lines and family support.'


def build_country(data, c):
    world = data['world']
    mine = [dict(r, scope=c['code']) for r in c['resources']]
    everything = mine + world['worldwide']
    urgent = [r for r in mine if r.get('urgent') and r.get('phone')]
    cards_now = emergency_card(c) + ''.join(
        f'<li><a class="phonecard" href="{dial_href(r)}">Call {esc(r["phone"])}<small>{esc(r.get("chip") or r["name"])}</small></a></li>'
        for r in urgent)
    intro = country_intro(c)
    if c.get('us_state'):  # a country with the name of a U.S. state (Georgia): link to the state, so the two are never mixed up
        st = next(s for s in data['states'] if s['abbr'] == c['us_state'])
        intro += (f' This page is the country. Looking for the U.S. state? '
                  f'<a href="../states/{st["abbr"].lower()}.html">{esc(st["name"])}, U.S. state</a>.')
    body = (hero(f'<span aria-hidden="true">{c["flag"]}</span> {esc(c["name"])}: help for moms', intro, '', 'slim')
            + f'<section class="wrap now" id="now"><h2>Need help right now?</h2>'
            f'<p class="quiet">If you or your child are in danger, call {esc(c["emergency"]["number"])}.</p>'
            f'<ul class="phonecards">{cards_now}</ul></section>'
            + finder(f'Search every listing for {in_name(c)}', 'helpline, benefit, breastfeeding…', NO_MATCH_WORLD)
            + needs(world_rows(data, everything, '../', c))
            + kind_word('#take-care', '../', c.get('lang'))
            + closing('../', 'Numbers are free to call unless the listing says otherwise. '))
    path = f'countries/{c["slug"]}.html'
    desc = country_desc(c)
    base = f"https://{data['site']['domain']}/"
    about = {'@type': 'CollectionPage', '@id': base + path, 'url': base + path, 'name': f'{c["name"]}: help for moms',
             'description': desc, 'inLanguage': 'en', 'isPartOf': {'@id': base + '#website'},
             'about': {'@type': 'Country', 'name': c['name']}}
    trail = breadcrumbs(data, [('Worldwide', 'world.html'), (c['name'], path)])
    return page(data, path, f'{c["name"]}: help for moms', desc, body, head_extra=structured_data(about, trail),
                slots=(f'country-{c["code"].lower()}', 'country'),
                danger=f'In danger right now? Call {c["emergency"]["number"]}.', scripts=kind_word_scripts('../', c.get('lang')))


def county_pick(data, s):
    """Local listings for each county of the state, one choice away: a picker beside the heading, and the same counties
    as plain links lower on the page (county_list), which search engines follow."""
    counties = sorted((c for c in data['counties'] if c['state'] == s['abbr']), key=lambda c: c['name'])
    if not counties:
        return ''
    code = s['abbr'].lower()
    if len(counties) == 1:
        return (f'<p class="countylink"><a href="{code}/{county_slug(counties[0]["name"])}.html">Local listings for {esc(s["name"])}</a>: '
                'public housing, legal aid, health centers, school districts and Head Start.</p>')
    noun = county_noun(s['abbr'])
    options = f'<option value="">Choose your {noun}</option>' + ''.join(
        f'<option value="{code}/{county_slug(c["name"])}.html">{esc(c["name"])}</option>' for c in counties)
    return (f'<div class="statepick"><label for="countypick">Local help in your {noun}</label>'
            f'<select id="countypick" data-state-pick>{options}</select><a href="#counties">See the list</a></div>')


def county_list(data, s):
    """Every county of the state as a link to its own page."""
    counties = sorted((c for c in data['counties'] if c['state'] == s['abbr']), key=lambda c: c['name'])
    if not counties:
        return ''
    code = s['abbr'].lower()
    items = ''.join(f'<li><a href="{code}/{county_slug(c["name"])}.html">{esc(c["name"])}</a></li>' for c in counties)
    many = county_noun(s['abbr'], plural=True)
    whose = (f'for each of {esc(s["name"])}\'s {len(counties)} {esc(many)}' if len(counties) > 1
             else f'for {"the " if s["name"].startswith("District") else ""}{esc(s["name"])}')
    return (f'<section class="wrap" id="counties"><h2>Local help by {esc(county_noun(s["abbr"]))}</h2>'
            f'<p class="quiet">Public housing, housing counselors, legal aid, health centers, school districts and Head Start, '
            f'{whose}.</p>{state_glance(s, len(counties), many)}<ul class="statelist countylist">{items}</ul></section>')


def state_glance(s, n_counties, many):
    """How many places the county pages of a state list, by kind, counted from the same files the county pages are
    written from (assets/us/<state>.json): the health center and Head Start sites in each county, and the agencies,
    counselors, districts and legal aid programs based in the state."""
    shard = county_shards().get(s['abbr'])
    if not shard:
        return ''
    cs = list(shard['c'].values())
    based = lambda table: sum(1 for v in shard.get(table, {}).values() if v[-1] == s['abbr'])
    counts = [('clinic', sum(len(c.get('health', [])) for c in cs), 'health center site', 'health center sites'),
              ('blocks', sum(len(c.get('headStart', [])) for c in cs), 'Head Start site', 'Head Start sites'),
              ('key', based('ph'), 'public housing agency', 'public housing agencies'),
              ('house', based('hu'), 'housing counselor', 'housing counselors'),
              ('book', based('sd'), 'school district', 'school districts'),
              ('scales', based('lg'), 'legal aid program', 'legal aid programs')]
    items = ''.join(glance_item(ico, n, one if n == 1 else many, root='../') for ico, n, one, many in counts if n)
    where = (f'Across {esc(s["name"])}\'s {n_counties} {esc(many)}, our pages list' if n_counties > 1
             else f'For {"the " if s["name"].startswith("District") else ""}{esc(s["name"])}, our page lists')
    return f'<figure class="glance"><figcaption>{where}</figcaption><ul>{items}</ul></figure>' if items else ''


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


# Where the "Help for moms and babies" row comes from, for county.html's list of sources (only once there is data).
MH_SOURCE = ('mh', 'Help for moms and babies',
             "each program's own published list: state health departments' WIC and health department lists, the federal "
             "NPI Registry, and the member and group lists of Parents as Teachers, the National Diaper Bank Network and La "
             "Leche League USA. Every source, and the ones we cannot use yet and why, is in our {0}",
             [('https://github.com/travisvought-byte/Ohiomom/blob/main/data/ymt/local-help/registry.json', 'list of sources')],
             'Each card names its source and the date it was copied. A listing is placed in the county where it is, or in each '
             'county it says it serves; nearby ones are shown by distance when the county has none.')

def county_shows(n):
    """What every county page holds, as icon tiles, in the words of this page's own lede."""
    kinds = [('key', 'Where to apply for housing help'), ('scales', 'Free legal help'), ('clinic', 'Low-cost health care'),
             ('book', 'Free evaluations for your child'), ('blocks', 'Head Start')]
    items = ''.join(f'<li><span class="gtile">{icon(ico)}<span>{esc(label)}</span></span></li>' for ico, label in kinds)
    return f'<figure class="glance shows"><figcaption>What each of our {n:,} county pages shows</figcaption><ul>{items}</ul></figure>'


def build_county(data):
    """Find your county: by state and county, or by ZIP code. assets/county.js finds it and opens its own page
    (build_county_pages). The sources of every county listing are explained here."""
    options = '<option value="">Choose your state</option>' + ''.join(
        f'<option value="{s["abbr"].lower()}" data-fips="{STATE_FIPS[s["abbr"]]}">{esc(s["name"])}</option>' for s in data['states'])
    find = ('<div class="countyfind" data-county-find hidden>'
            f'<div><label for="cstate">State</label><select id="cstate">{options}</select></div>'
            '<div><label for="ccounty">County</label><select id="ccounty" disabled><option value="">Choose a state first</option></select></div>'
            '<div><label for="zip">Or your ZIP code</label><input id="zip" type="search" inputmode="numeric" maxlength="5" '
            'autocomplete="off" enterkeyhint="go" placeholder="5 digits"></div></div>'
            '<p class="quiet" id="cmsg" role="status"></p>')
    lede = ('Want help close to home? Pick your county, or type your ZIP code, to see where to apply for housing help, free '
            'legal help, low-cost health care, free evaluations for your child and Head Start near you. Free, private, no sign-up.')
    hero_html = (f'<section class="hero slim"><div class="wrap"><h1 id="ctitle">Help near you</h1>'
                 f'<p class="lede" id="clede">{esc(lede)}</p>{find}{county_shows(len(data["counties"]))}</div></section>')
    fallback = ('<section class="wrap"><p>Finding a county by ZIP code needs JavaScript, which seems to be off or still loading. '
                'You can still <a href="states.html">choose your state</a>: each state page lists its counties, and each county '
                'has its own page.</p></section>')
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
    srcs = list(COUNTY_SOURCES)
    if local_help():
        srcs.insert(2, MH_SOURCE)
    items = ''.join(f'<li><strong>{esc(label)}:</strong> {sentence(key, what, links)}. {esc(note)}</li>'
                    for key, label, what, links, note in srcs)
    sources = (f'<section class="wrap slim" id="sources"><h2>Where these listings come from</h2><ul>{items}</ul>'
               '<p class="note">Listings are copied from these federal lists by a program, not checked by phone, and the date of '
               'the copy is on each one. A Website button appears only when that website loaded in our automatic check. '
               'If something is wrong, <a href="report.html">tell us</a>.</p>'
               '<p class="note">Nothing you type on this page is saved. A ZIP code is matched inside your browser, using a list '
               'your browser downloads for the first digit of the code.</p></section>')
    # The crisis phone cards come right after the heading, as on every state and country page.
    body = (hero_html + '\n' + urgent_strip(data) + f'\n<div id="county-app">{fallback}</div>\n'
            + kind_word('help.html#take-care') + '\n' + sources)
    return page(data, 'county.html', 'Help near you, by county',
                'Public housing, housing counselors, legal aid, health centers, school districts and Head Start in every U.S. county, '
                'from federal directories, free.',
                body, head_extra=structured_data(breadcrumbs(data, [('Help near you, by county', 'county.html')])),
                scripts='\n<script src="assets/county.js"></script>' + kind_word_scripts(), slots=('county',))


# ---------------------------------------------------------------- one page for every U.S. county
# assets/county.js once drew a county in the browser from assets/us/<state>.json. Search engines and slow phones read
# a written page better, so every county now has its own: states/<state>/<county-slug>.html, written here from the
# same files, with the same rows and cards. county.html stays as the way to find a county by state or ZIP code.
MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']


def county_slug(name):
    """'Prince George's County' -> 'prince-george-s-county', 'Doña Ana County' -> 'dona-ana-county'. The same rule is in
    assets/county.js."""
    plain = ''.join(ch for ch in unicodedata.normalize('NFKD', name) if not unicodedata.combining(ch))
    return re.sub(r'[^a-z0-9]+', '-', plain.lower()).strip('-')


def county_path(st, name):
    return f'states/{st.lower()}/{county_slug(name)}.html'


def county_shards():
    """{'OH': the parsed assets/us/oh.json, ...}, read once."""
    if not hasattr(county_shards, 'cache'):
        county_shards.cache = {p.stem.upper(): json.loads(p.read_text(encoding='utf-8'))
                               for p in sorted((ROOT / 'assets' / 'us').glob('*.json')) if re.fullmatch(r'[a-z]{2}', p.stem)}
    return county_shards.cache


def christmas_shard():
    p = ROOT / 'assets' / 'us' / 'christmas.json'
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else None


def _pretty(iso):
    y, m, d = str(iso).split('-')
    return f'{MONTHS[int(m) - 1]} {int(d)}, {y}'


def _count(n, one, many):
    return f'{n} {one if n == 1 else many}'


def _words(items):
    return items[0] if len(items) < 2 else ', '.join(items[:-1]) + ' and ' + items[-1]


def _safe_url(u):
    return u if re.fullmatch(r'https?://[^\s"\'<>]+', u or '') else ''


def _tel1(p):
    return 'tel:+1' + re.sub(r'\D', '', str(p))


def _source_line(key, asof):
    links = next(s[3] for s in COUNTY_SOURCES if s[0] == key)
    nums = ' '.join(f'<a href="{esc(u)}" rel="noopener">{i}</a>' for i, (u, _t) in enumerate(links, 1))
    return f'<p class="src">Federal data as of {esc(_pretty(asof))}, not confirmed by phone. Sources: {nums}</p>'


def _next(text):
    return f'<p><strong>Next step:</strong> {esc(text)}</p>'


def _ccard(cid, name, short, phone, web, more):
    acts = f'<a class="btn call" href="{_tel1(phone)}">Call {esc(phone)}</a>'
    if _safe_url(web):
        acts += f'<a class="btn" href="{esc(web)}" rel="noopener">Website</a>'
    return (f'<article class="card" id="{esc(cid)}"><h3>{esc(name)}</h3><p class="short">{esc(short)}</p>'
            f'<p class="actions">{acts}</p><details class="more"><summary>More about this<span class="sr">: {esc(name)}</span></summary>'
            f'{"".join(more)}</details></article>')


def _place(street, city, st, zip_):
    return ', '.join(x for x in (street, f'{city}, {st}' + (f' {zip_}' if zip_ else '')) if x)


def _away(miles, county):
    return f'About {_count(miles, "mile", "miles")} from the middle of {county}. ' if miles else ''


def _p(text, cls=''):
    return f'<p class="{cls}">{esc(text)}</p>' if cls else f'<p>{esc(text)}</p>'


def _health_card(r, i, ctx):
    short = _away(r[9], ctx['county']) + f'Low-cost health care in {r[3]}, {r[10]}, whether or not you have insurance. Fees are based on your income.'
    more = [_p('Part of ' + re.sub(r'^The ', 'the ', r[0]), 'org'), _p(_place(r[2], r[3], r[10], r[4]))]
    if r[7] > 0:
        more.append(_p(f'Open about {_count(r[7], "hour", "hours")} a week.'))
    if r[8]:
        more.append(_p('This site is open only part of the year, so call before you go.'))
    return _ccard(f'hc-{i}', r[1], short, r[5], r[6], more)


def _head_start_card(r, i, ctx):
    kinds = r[6]
    if kinds & 1 and kinds & 2:
        what = (f'Free early learning in {r[3]}, {r[8]}: Head Start for ages 3 to 5, and Early Head Start for babies, toddlers '
                'and pregnant moms. For families who qualify.')
    elif kinds & 2:
        what = f'Free early learning for babies and toddlers, and support for pregnant moms, in {r[3]}, {r[8]}. For families who qualify.'
    else:
        what = f'Free preschool in {r[3]}, {r[8]} for children ages 3 to 5 in families who qualify.'
    notes = []
    if kinds & 4:
        notes.append('This program serves migrant and seasonal farmworker families.')
    if kinds & 8:
        notes.append('This is a tribal program (American Indian and Alaska Native Head Start). Ask who can enroll.')
    notes.append('Free for families who qualify. Families with a low income qualify, and so do children in foster care and '
                 'families who are homeless or who get TANF or SSI.')
    more = [_p(r[1], 'org'), _p(_place(r[2], r[3], r[8], r[4])), _p(' '.join(notes))]
    return _ccard(f'hs-{i}', r[0], _away(r[7], ctx['county']) + what, r[5], '', more)


SERVICE_WORDS = {'R': 'renting', 'H': 'homelessness', 'D': 'mortgage trouble', 'B': 'budgeting', 'P': 'buying a home'}
METHOD_WORDS = {'F': 'in person', 'P': 'by phone', 'V': 'by video', 'I': 'online'}


def _hud_card(ref, a, ctx):
    topics = [SERVICE_WORDS[k] for k in 'RHDBP' if k in a[6]]
    where = f'About {_count(ref[1], "mile", "miles")} away, in {a[2]}, {a[9]}. ' if ref[1] else f'In {ctx["county"]}. '
    short = where + 'Free or low-cost help from a HUD-approved counselor' + (f' with {_words(topics)}' if topics else '') + '.'
    more = [_p('HUD-approved housing counseling agency', 'org'), _p(_place(a[1], a[2], a[9], a[3]))]
    how = [METHOD_WORDS[k] for k in a[7] if k in METHOD_WORDS]
    if how:
        more.append(_p(f'Counseling is offered {_words(how)}.'))
    if a[8]:
        more.append(_p(f'Also helps in {_words(a[8])}.'))
    return _ccard(f'hud-{ref[0]}', a[0], short, a[4], a[5], more)


PROGRAM = {
    'C': 'Public housing and Housing Choice Vouchers (Section 8).',
    'S': 'Housing Choice Vouchers (Section 8), which help pay rent to a private landlord.',
    'P': 'Public housing: apartments with rent based on your income.',
}


def _pha_card(ref, a, ctx):
    how = ref[2]
    if how == 's':
        short = f'Statewide agency, run from {a[2]}, {a[8]}. {PROGRAM[a[5]]} Ask whether it serves {ctx["county"]}.'
    elif how == 'r':
        short = f'About {_count(ref[1], "mile", "miles")} away, in {a[2]}, {a[8]}. {PROGRAM[a[5]]} Ask whether it serves where you live.'
    elif how == 'n':
        short = f'Named for {ctx["county"]}, with its office in {a[2]}, {a[8]}. {PROGRAM[a[5]]}'
    else:
        short = f'Office in {a[2]}, {a[8]}. {PROGRAM[a[5]]}'
    more = [_p('State housing agency, funded by HUD' if how == 's' else 'Public housing agency, funded by HUD', 'org'),
            _p(_place(a[1], a[2], a[8], a[3]))]
    size = []
    if a[6] > 0:
        size.append(f'about {a[6]:,} public housing {"home" if a[6] == 1 else "homes"}')
    if a[7] > 0:
        size.append(f'about {a[7]:,} {"voucher" if a[7] == 1 else "vouchers"}')
    if size:
        more.append(_p("By HUD's count, " + ' and '.join(size) + '.'))
    return _ccard(f'ph-{ref[0]}', a[0], short, a[4], '', more)


def _district_card(did, miles, d, ctx):
    short = (f'About {_count(miles, "mile", "miles")} away, in {d[2]}, {d[6]}. Ask whether it serves where you live.' if miles
             else f'Public school district with its office in {d[2]}, {d[6]}. Ask for the special education office.')
    more = [_p('Public school district', 'org'), _p(_place(d[1], d[2], d[6], d[3]))]
    return _ccard(f'sd-{did}', d[0], short, d[4], d[5], more)


def _legal_card(sa, a, ctx):
    short = 'Free legal help for people with low incomes, with problems such as custody, child support, protection from abuse and eviction.'
    more = [_p('Legal aid program funded by the Legal Services Corporation', 'org'),
            _p(f'It serves {ctx["county"]} and the rest of its area, and can tell you if another program is the one for you.')]
    return _ccard(f'lg-{sa}', a[0], short, a[1], a[2], more)


def _tft_card(i, t, here, ctx):
    web = _safe_url(str(ctx['site'] or '').replace('{}', t[0]))
    short = ((f'Named for {ctx["county"]}, or with its address there. ' if here else f'Toys for Tots campaign in {t[1]}, {t[2]}. ')
             + 'New toys for children whose families cannot afford Christmas gifts.')
    src = _safe_url(ctx['source']) or ctx['root'] + 'christmas.html'
    more = [_p('Marine Toys for Tots', 'org'),
            _p("The campaign's website says which towns it serves, its dates, and whether it takes requests from families or only "
               'through local charities and agencies.'),
            _next('Open the website and its Request a Toy page. If requests have closed, use its Contact page and ask which local '
                  'groups are giving out its toys.'),
            f'<p class="src">From Toys for Tots\' list of local campaigns, checked {esc(_pretty(ctx["xasof"]))}. Sources: '
            f'<a href="{esc(src)}" rel="noopener">1</a></p>']
    acts = f'<a class="btn" href="{esc(web)}" rel="noopener">Campaign website</a>' if web else ''
    name = 'Toys for Tots: ' + t[1]
    return (f'<article class="card" id="tft-{i}"><h3>{esc(name)}</h3><p class="short">{esc(short)}</p><p class="actions">{acts}</p>'
            f'<details class="more"><summary>More about this<span class="sr">: {esc(name)}</span></summary>{"".join(more)}</details></article>')


def _crow(rid, icon, label, summary, n, noun, body):
    count = '' if n is None else _count(n, *noun)
    return (f'<details class="need" id="{rid}"><summary><span class="ico" aria-hidden="true">{icon}</span><h2>{esc(label)}</h2>'
            f'<span class="nsum">{esc(summary)}</span><span class="ncount">{count}</span></summary>'
            f'<div class="rowbody">{body}</div></details>')


# The next step for every card of a row, said once at the top of the row (a state page says it on each card; a county
# row can hold dozens of cards of one kind, so it is said once, and the sources once at the end).
COUNTY_NEXT = {
    'pha': 'Call and ask whether the waiting list is open, how to apply, and whether they serve where you live. You can be on '
           "more than one agency's list. If you are homeless or escaping violence, ask whether that moves you up the list.",
    'hud': 'Call and say what is happening: rent you cannot pay, an eviction notice, a shutoff, or a mortgage you are behind on. '
           'Ask whether there is a fee.',
    'lg': 'Call and say what is happening and any date you have to meet, such as a court date or the deadline on an eviction '
          'notice. If they cannot take your case, ask who can.',
    'hrsa': 'Call, say you want to become a new patient, and ask about the sliding fee discount and what to bring. Ask whether '
            'they offer what you need, such as prenatal care, checkups for children or dental care.',
    'sd': 'Call and ask for the special education office, or preschool special education for a child under 5. Say you would like '
          'your child evaluated, then make the same request in writing, with the date, and keep a copy.',
    'hs': 'Call and ask how to apply and what papers to bring. Programs can have waiting lists, so ask to be added even if there '
          'is no opening now.',
}


def _clist(items, make, key=None, county='', asof=None):
    """Every card of a row, after the row's next step and before its sources. A large county lists hundreds; the
    search box at the top of the page narrows them by town or name."""
    out = (f'<p class="nextstep"><strong>Next step:</strong> {esc(COUNTY_NEXT[key])}</p>' if key in COUNTY_NEXT else '')
    out += '<div class="cards">' + ''.join(make(it, i) for i, it in enumerate(items)) + '</div>'
    if asof and key:
        out += _source_line(key, asof)
    return out


# ---- Help for moms and babies: the mined layer (scripts/local_help.py, data/ymt/local-help/) ----

def local_help():
    """{'rows': {id: row}, 'index': {fips: [[id, miles]]}, 'sources': {id: registry entry}}, or None before the first
    run of scripts/local_help.py has written any listings."""
    if not hasattr(local_help, 'cache'):
        d = ROOT / 'data' / 'ymt' / 'local-help'
        local_help.cache = None
        if (d / 'listings.csv').exists() and (d / 'county-index.json').exists():
            import csv
            with (d / 'listings.csv').open(encoding='utf-8', newline='') as fh:
                rows = {r['id']: r for r in csv.DictReader(fh)}
            if rows:
                reg = json.loads((d / 'registry.json').read_text(encoding='utf-8'))
                links = ROOT / 'data' / 'county-links.json'
                ledger = json.loads(links.read_text(encoding='utf-8')).get('urls', {}) if links.exists() else {}
                local_help.cache = {'rows': rows, 'index': json.loads((d / 'county-index.json').read_text(encoding='utf-8')),
                                    'sources': {s['id']: s for s in reg['sources']}, 'links': ledger}
    return local_help.cache


MH_NEEDS = [  # in the order the row shows them: (need, heading)
    ('wic', 'WIC'),
    ('health-dept', 'Health department'),
    ('home-visiting', 'Home visits for new parents'),
    ('healthy-start', 'Healthy Start'),
    ('breastfeeding', 'Breastfeeding support'),
    ('diapers', 'Diapers'),
    ('postpartum', 'Support after the baby comes'),
]


def _mh_card(r, m, src, ctx):
    name = r['name']
    town = f"{r['city']}, {r['state']}" if r['city'] else r['state']
    if m:
        where = f'About {_count(m, "mile", "miles")} away, in {town}. Ask whether it serves where you live. '
    elif r['county_fips'] and r['county_fips'] != ctx['fips']:
        where = f'Based in {town}, and lists {ctx["county"]} among the places it serves. '
    else:
        where = f'In {town}. ' if r['city'] else ''
    acts = f'<a class="btn call" href="{_tel1(r["phone"])}">Call {esc(r["phone"])}</a>' if r['phone'] else ''
    if _safe_url(r['website']) and ctx.get('links', {}).get(r['website']) in ('ok', 'refused'):
        # only a website scripts/county_links.py --local-help has seen load, as on the rest of the county page
        acts += f'<a class="btn" href="{esc(r["website"])}" rel="noopener">Website</a>'
    what = src.get('what', '')
    room = 320 - len(name) - len(re.sub(r'<[^>]+>', '', acts))   # the short part of a card stays short
    short = where + what
    if len(short) > room:
        short = where + what.split(': ')[0].split('. ')[0].rstrip('.') + '.'
    if len(short) > room:
        short = where.strip()
    more = [_p(r['org'] or f'Listed by {src["publisher"]}', 'org')]
    place = _place(r['street'], r['city'], r['state'], r['zip']) if r['street'] else ''
    if place:
        more.append(_p(place))
    url = _safe_url(r['source_url'])
    link = f' Source: <a href="{esc(url)}" rel="noopener">1</a>' if url else ''
    more.append(f'<p class="src">From {esc(src["publisher"])}: {esc(src["name"])}, copied {esc(_pretty(r["checked_on"]))}, '
                f'not confirmed by phone.{link}</p>')
    cid = 'mh-' + r['id'][3:]
    return (f'<article class="card" id="{esc(cid)}"><h3>{esc(name)}</h3><p class="short">{esc(short)}</p>'
            f'<p class="actions">{acts}</p><details class="more"><summary>More about this<span class="sr">: {esc(name)}</span></summary>'
            f'{"".join(more)}</details></article>')


def mh_row(st, fips, c, sname, code, root):
    """The 'Help for moms and babies' row of a county page: WIC, the health department, home visiting, breastfeeding
    groups and diaper banks, each from its own published list. None before the pipeline has run."""
    lh = local_help()
    if lh is None:
        return None
    ctx = {'county': c['n'], 'fips': fips, 'links': lh.get('links', {})}
    # a listing with no phone and no website that loaded gives a mom nothing to do, so it waits for the next check
    refs = [(lh['rows'][i], m) for i, m in lh['index'].get(fips, [])
            if i in lh['rows'] and (lh['rows'][i]['phone'] or ctx['links'].get(lh['rows'][i]['website']) in ('ok', 'refused'))]
    groups, present = [], []
    for need, heading in MH_NEEDS:
        items = sorted((x for x in refs if x[0]['need'] == need), key=lambda x: (x[1], x[0]['name']))
        if items:
            cards = ''.join(_mh_card(r, m, lh['sources'][r['source_id']], ctx) for r, m in items)
            used = []   # the group's sources, most listings first: the next step is the main one's, the source line names all
            for r, _m in items:
                if r['source_id'] not in used:
                    used.append(r['source_id'])
            used.sort(key=lambda sid: -sum(1 for r, _m in items if r['source_id'] == sid))
            srcs = [lh['sources'][sid] for sid in used]
            nxt = next((x['next'] for x in srcs if x.get('next')), '')
            links = ' '.join(f'<a href="{esc(_safe_url(x.get("cite_url") or x["homepage"]))}" rel="noopener">{i}</a>'
                             for i, x in enumerate(srcs, 1) if _safe_url(x.get('cite_url') or x['homepage']))
            copied = max(r['checked_on'] for r, _m in items)
            groups.append(f'<h3 class="subneed">{esc(heading)}</h3>'
                          + (f'<p class="nextstep"><strong>Next step:</strong> {esc(nxt)}</p>' if nxt else '')
                          + f'<div class="cards">{cards}</div>'
                          + f'<p class="src">From {esc("; ".join(x["publisher"] for x in srcs))}, copied {esc(_pretty(copied))}, '
                          f'not confirmed by phone. Sources: {links}</p>')
            present.append(heading if need in ('wic', 'healthy-start') else heading.lower())
    inside = sum(1 for _r, m in refs if m == 0)
    tail = (f'<p class="quiet">WIC, help paying for child care, health coverage for you and your baby and more are on '
            f'<a href="{root}states/{code}.html#pregnancy-baby">the {esc(sname)} page</a>. '
            'Or dial <a href="tel:211">211</a> and ask what help there is for moms and babies near you.</p>')
    if not groups:
        body = (f'<p class="quiet">We have not found a local listing for moms and babies in or near {esc(c["n"])} yet. '
                'We add more every month.</p>' + tail)
        summary = f'WIC, health department and more for {sname}'
    else:
        body = ''.join(groups) + tail
        named = present[0] if len(present) == 1 else ', '.join(present[:-1]) + ' and ' + present[-1]
        summary = f'{named[0].upper()}{named[1:]} {"in or near" if inside else "near"} {c["n"]}'
    return _crow('county-moms', '🍼', 'Help for moms and babies', summary, len(refs) or None, ('place', 'places'), body)


def county_rows(data, st, fips, shard, x, root):
    """The rows of one county's page, in the order county.html has always shown them."""
    c = shard['c'][fips]
    sname = next(s['name'] for s in data['states'] if s['abbr'] == st)
    code = st.lower()
    ctx = {'county': c['n'], 'asof': shard['asof'], 'root': root}
    rows = []
    if x and x.get('t'):
        xc = dict(ctx, xasof=x['asof'], site=x.get('site'), source=x.get('source'))
        here = [i for i in x['c'].get(fips, []) if i < len(x['t']) and x['t'][i]]
        rest = [i for i in x['st'].get(st, []) if i not in here and i < len(x['t']) and x['t'][i]]
        intro = (f'Toys for Tots campaigns named for {esc(c["n"])}, or with their address there. ' if here else
                 f'No Toys for Tots campaign is named for {esc(c["n"])} or has its address there. Each campaign\'s website says '
                 'which towns it serves, so open the list for your state below. ')
        intro = (f'<p class="quiet">{intro}Sign-ups close early. If one has closed, dial <a href="tel:211">211</a> and ask what '
                 f'Christmas help is still open. <a href="{root}states/{code}.html#christmas">More Christmas help in {esc(sname)}</a> · '
                 f'<a href="{root}christmas.html">Christmas help everywhere</a></p>')
        # Only the county's own campaigns are cards here. The state page lists every other campaign in one card.
        every = (f'<p class="quiet"><a href="{root}states/{code}.html#tft-{code}">Every Toys for Tots campaign in {esc(sname)}</a> '
                 f'({len(here) + len(rest)}), with a link to each one\'s website.</p>') if rest else ''
        body = intro + (_clist(here, lambda i, _n: _tft_card(i, x['t'][i], True, xc)) if here else '') + every
        if not here and not rest:
            body = intro + f'<p class="quiet">No Toys for Tots campaign is listed in {esc(sname)}. Dial 211 and ask what Christmas help is open near you.</p>'
        rows.append(_crow('county-christmas', '🎄', 'Christmas help',
                          f'Toys for Tots for {c["n"]}, and Christmas help across {sname}' if here else
                          f'Toys for Tots campaigns in {sname}, and more Christmas help', len(here) if here else None,
                          ('campaign', 'campaigns'), body))
    pha = [ref for ref in c.get('pha', []) if ref[0] in shard.get('ph', {})]
    here = any(ref[2] in 'cn' for ref in pha)
    near = any(ref[2] == 'r' for ref in pha)
    rows.append(_crow('county-pha', '🔑', 'Public housing and Section 8',
                      f'Where to apply in {c["n"]} for public housing and rent vouchers' if here else
                      (f'Nearest agencies, outside {c["n"]}' if near else "Your state's agency for public housing and rent vouchers"),
                      len(pha), ('agency', 'agencies'),
                      _clist(pha, lambda ref, _i: _pha_card(ref, shard['ph'][ref[0]], ctx), 'pha', c['n'], shard['asof']) if pha else
                      f'<p class="quiet">No public housing agency is listed near {esc(c["n"])}. Call HUD at 800-955-2232 to find the one that serves you.</p>'))
    agencies = [ref for ref in c.get('hud', []) if ref[0] in shard.get('hu', {})]
    rows.append(_crow('county-hud', '🏠', 'Housing counselors', 'Free or low-cost help with rent, eviction and mortgages',
                      len(agencies), ('counselor', 'counselors'),
                      _clist(agencies, lambda ref, _i: _hud_card(ref, shard['hu'][ref[0]], ctx), 'hud', c['n'], shard['asof']) if agencies else
                      f'<p class="quiet">No HUD-approved counselor is listed near {esc(c["n"])}. Call HUD at 800-569-4287 to be matched with one by phone.</p>'))
    moms = mh_row(st, fips, c, sname, code, root)
    if moms:
        rows.append(moms)
    legal = [sa for sa in c.get('lg', []) if sa in shard.get('lg', {})]
    rows.append(_crow('county-legal', '⚖️', 'Free legal help', f'Legal aid that serves {c["n"]}', len(legal), ('program', 'programs'),
                      _clist(legal, lambda sa, _i: _legal_card(sa, shard['lg'][sa], ctx), 'lg', c['n'], shard['asof']) if legal else
                      f'<p class="quiet">No legal aid program is listed for {esc(c["n"])}. Your state\'s legal help is in the last row.</p>'))
    health = c.get('health') or c.get('healthNear') or []
    rows.append(_crow('county-health', '🩺', 'Low-cost health care',
                      f'Health centers in {c["n"]}' if c.get('health') else f'Nearest health centers, outside {c["n"]}',
                      len(health), ('place', 'places'),
                      _clist(health, lambda r, i: _health_card(r, i, ctx), 'hrsa', c['n'], shard['asof']) if health else
                      '<p class="quiet">No health center is listed within 60 miles. Dial 211 and ask for a free or low-cost clinic.</p>'))
    sd = [[i, 0] for i in c.get('sd', [])] + list(c.get('sdNear', []))
    sd = [ref for ref in sd if ref[0] in shard.get('sd', {})]
    intro = ('<p class="quiet">From age 3, children can get special education free through the public schools, even before kindergarten. '
             'If you think your child has a delay or disability, call your school district and ask for an evaluation. If the district '
             'decides not to evaluate, it has to tell you why in writing. For a child under 3, ask '
             f'<a href="{root}states/{code}.html#{code}-ei">early intervention in {esc(sname)}</a> instead.</p>')
    rows.append(_crow('county-schools', '🧩', 'Free evaluation for your child',
                      f'School districts in {c["n"]}, for children 3 and up' if c.get('sd') else f'Nearest school districts, outside {c["n"]}',
                      len(sd), ('district', 'districts'),
                      intro + (_clist(sd, lambda ref, _i: _district_card(ref[0], ref[1], shard['sd'][ref[0]], ctx), 'sd', c['n'], shard['asof']) if sd else
                               f'<p class="quiet">No school district is listed for {esc(c["n"])}. Call your state\'s department of education and ask which district serves you.</p>')))
    start = c.get('headStart') or c.get('headStartNear') or []
    rows.append(_crow('county-start', '🧸', 'Head Start and Early Head Start',
                      f'Free early learning in {c["n"]}' if c.get('headStart') else f'Nearest programs, outside {c["n"]}',
                      len(start), ('place', 'places'),
                      _clist(start, lambda r, i: _head_start_card(r, i, ctx), 'hs', c['n'], shard['asof']) if start else
                      '<p class="quiet">No open Head Start location is listed within 60 miles. Dial 211 and ask about free child care and preschool.</p>'))
    secs = sec_map(data)
    links = ''.join(f'<li><a href="{root}states/{code}.html#{sid}">{esc(secs[sid]["label"])}</a></li>' for sid in STATE_SECTIONS)
    rows.append(_crow('county-state', '📍', f'Help across {sname}', 'SNAP, WIC, child care, health coverage and more', None, None,
                      '<p class="quiet">Your state has its own offices for SNAP, WIC, child care, health coverage and more.</p>'
                      f'<ul class="statelinks">{links}</ul>'))
    return ''.join(rows)


# The at-a-glance row of a county page: (row, icon, what one is called, what several are called). Christmas help is
# seasonal and the last row is links, so neither is here.
GLANCE = [
    ('county-pha', 'key', 'housing agency', 'housing agencies'),
    ('county-hud', 'house', 'housing counselor', 'housing counselors'),
    ('county-moms', 'bottle', 'place for moms and babies', 'places for moms and babies'),
    ('county-legal', 'scales', 'legal aid program', 'legal aid programs'),
    ('county-health', 'clinic', 'health center', 'health centers'),
    ('county-schools', 'book', 'school district', 'school districts'),
    ('county-start', 'blocks', 'Head Start site', 'Head Start sites'),
]


def county_glance(rows, place, root):
    """What a county page holds, one tile per row: the count its row shows, and a link that opens that row. Read from
    the rows themselves, so the two can never disagree. A row that lists places outside the county says "nearby"."""
    found = {}
    for rid, summary in re.findall(r'<details class="need" id="(county-[a-z]+)"><summary>(.*?)</summary>', rows):
        n = re.search(r'<span class="ncount">(\d+) ', summary)
        nsum = re.search(r'<span class="nsum">([^<]*)</span>', summary).group(1)
        if n and int(n.group(1)):
            found[rid] = (int(n.group(1)), nsum.startswith(('Nearest', 'Your state')))
    items = ''.join(glance_item(ico, found[rid][0], (one if found[rid][0] == 1 else many) + (' nearby' if found[rid][1] else ''),
                                f'#{rid}', root)
                    for rid, ico, one, many in GLANCE if rid in found)
    return f'<nav class="glance" aria-label="At a glance: help in {esc(place)}"><ul>{items}</ul></nav>' if items else ''


def county_towns(c, n=2):
    """The towns a county's own listings are in (health center sites, Head Start locations and the housing agencies with
    their office there), the most listed first: the places a mom from this county is likely to know it by. A county
    named for its town (Carson City) or a city that is its own county (Baltimore city) gives none."""
    from collections import Counter
    seen = Counter()
    for r in c.get('health') or []:
        seen[r[3]] += 1
    for r in c.get('headStart') or []:
        seen[r[3]] += 1
    towns = [t for t, k in sorted(seen.items(), key=lambda kv: -kv[1]) if t and t.lower() != c['n'].lower()
             and t.upper() != t]
    if re.search(r'\bcity$', c['n'], re.I):
        return []
    return towns[:n]


def county_pha(c, shard):
    """(name, how) of the first housing agency a county page lists, or None. how is the agency's tie to the county:
    'c' office there, 'n' named for it, 'r' nearby, 's' the state's own voucher program."""
    for ref in c.get('pha', []):
        if ref[0] in shard.get('ph', {}):
            return shard['ph'][ref[0]][0], ref[2]
    return None


def county_legal(c, shard):
    return next((shard['lg'][sa][0] for sa in c.get('lg', []) if sa in shard.get('lg', {})), None)


def the_place(name):
    """'Capitol Planning Region' -> 'the Capitol Planning Region', as it reads in a sentence; counties keep their name."""
    return ('the ' + name) if re.search(r'(Planning Region|Census Area|Borough|Municipality)$', name) else name


def mh_needs(fips):
    """The kinds of help for moms and babies a county page lists (as its row names them), in the row's order."""
    lh = local_help()
    if lh is None:
        return []
    links = lh.get('links', {})
    have = {lh['rows'][i]['need'] for i, _m in lh['index'].get(fips, [])
            if i in lh['rows'] and (lh['rows'][i]['phone'] or links.get(lh['rows'][i]['website']) in ('ok', 'refused'))}
    say = {'wic': 'WIC', 'health-dept': 'the health department', 'home-visiting': 'home visits for new parents',
           'healthy-start': 'Healthy Start', 'breastfeeding': 'breastfeeding support', 'diapers': 'free diapers',
           'postpartum': 'support after the baby comes'}
    return [say.get(need, h.lower()) for need, h in MH_NEEDS if need in have]


def county_intro(c, shard, fips=None):
    """The opening lines of a county page, written to a mom who lives there: the towns she knows it by, and by name the
    housing agency to apply to and the legal aid program that serves her, each a link that opens its row."""
    n = esc(the_place(c['n']))
    towns = county_towns(c)
    if len(towns) == 2:
        out = f'Raising kids in {esc(towns[0])}, {esc(towns[1])} or anywhere else in {n}? Here is who to call close to home.'
    elif towns:
        out = f'Raising kids in {esc(towns[0])} or anywhere else in {n}? Here is who to call close to home.'
    else:
        out = f'Raising kids in {n}? Here is who to call close to home.'
    pha = county_pha(c, shard)
    if pha:
        name, how = pha
        if how in 'cn':
            out += f' To apply for public housing or a Section 8 voucher, start with <a href="#county-pha">{esc(name)}</a>.'
        elif how == 'r':
            out += f' For public housing or a Section 8 voucher, the nearest agency we list is <a href="#county-pha">{esc(name)}</a>.'
        else:
            out += f' For a Section 8 voucher, start with <a href="#county-pha">{esc(name)}</a>.'
    legal = county_legal(c, shard)
    if legal:
        out += (f' Free legal help with custody, child support, protection from abuse or an eviction comes from '
                f'<a href="#county-legal">{esc(legal)}</a>.')
    moms = mh_needs(fips) if fips else []
    if moms:
        named = moms[0] if len(moms) == 1 else ', '.join(moms[:-1]) + ' and ' + moms[-1]
        out += f' Expecting, or have a little one? You will find {esc(named)} <a href="#county-moms">near you</a>.'
    near = ' nearby' if not c.get('health') or not c.get('headStart') else ''
    out += (f' Low-cost clinics, free evaluations for your child and Head Start{near} are below too. Pick what you need. '
            'Free, private, no sign-up.')
    return re.sub(r'\.(</a>)\.', r'.\1', out)  # a name that ends in "Inc." ends its sentence too


def county_desc(nice, c=None, shard=None):
    """Search-result line for a county page: the place (with its main towns), then by name the housing agency and the
    legal aid program, shortened until it fits."""
    tries = []
    if c is not None:
        towns = county_towns(c)
        pha = county_pha(c, shard)
        pha = pha if pha and pha[1] in 'cn' else None  # an agency only nearby may not serve the county
        legal = county_legal(c, shard)
        where = f'{nice} ({", ".join(towns)})' if towns else nice
        if pha and legal:
            tries.append(f'Help for moms in {where}: Section 8 with {pha[0]}, free legal aid from {legal}, clinics and Head Start.')
            tries.append(f'Help for moms in {nice}: Section 8 with {pha[0]}, free legal aid from {legal}, clinics and Head Start.')
        if pha:
            tries.append(f'Help for moms in {where}: Section 8 with {pha[0]}, legal aid, clinics and Head Start.')
            tries.append(f'Help for moms in {nice}: Section 8 with {pha[0]}, legal aid, clinics and Head Start.')
        if legal:
            tries.append(f'Help for moms in {where}: housing, free legal aid from {legal}, clinics and Head Start.')
    for d in tries:
        if fits(d):
            return d
    for d in (f'Help for moms in {nice}: public housing and Section 8, housing counselors, free legal aid, low-cost health care, '
              'school evaluations and Head Start, with phone numbers.',
              f'Help for moms in {nice}: public housing, legal aid, low-cost health care, school evaluations and Head Start.',
              f'Help for moms in {nice}: housing, legal aid, health care and Head Start.'):
        if len(d) <= 158:
            return d
    return d


def the_district(html_text):
    """The District of Columbia takes "the" inside a sentence: "help in the District of Columbia".
    Titles, headings that name the place alone and the breadcrumb keep the bare name."""
    return re.sub(r'\b(in|In|for|to|serves|opens|across|and|Find) District of Columbia',
                  lambda m: f'{m.group(1)} the District of Columbia', html_text)


def county_title(c, s):
    """A search title that fits: Google cuts titles near 60 characters, so a long county name
    takes the state's two letters, and a Connecticut planning region or Alaska census area
    drops that word last of all. The county page for D.C. gets its own title, apart from the state page's."""
    if c['n'] == s['name']:
        return 'Washington, DC: local help for moms'
    for t in (f'{c["n"]}, {s["name"]}: help for moms', f'{c["n"]}, {s["abbr"]}: help for moms',
              f'{re.sub(r" (Planning Region|Census Area)$", "", c["n"])}, {s["abbr"]}: help for moms'):
        if len(t) <= 54:
            return t
    return t


def county_noun(st, plural=False):
    one, many = {'LA': ('parish', 'parishes'), 'AK': ('borough or area', 'boroughs and areas'),
                 'CT': ('planning region', 'planning regions')}.get(st, ('county', 'counties'))
    return many if plural else one


def build_county_page(data, st, fips, shard, x):
    c = shard['c'][fips]
    s = next(s for s in data['states'] if s['abbr'] == st)
    nice = c['n'] if c['n'] == s['name'] else f'{c["n"]}, {s["name"]}'
    path = county_path(st, c['n'])
    root = '../../'
    code = st.lower()
    crumbs = (f'<nav class="crumbs" aria-label="You are here"><a href="{root}index.html">Home</a> › '
              f'<a href="{root}states.html">States</a> › <a href="../{code}.html">{esc(s["name"])}</a> › '
              f'<span aria-current="page">{esc(c["n"])}</span></nav>')
    lede = county_intro(c, shard, fips)
    first = (f'<a href="../{code}.html">All help in {esc(s["name"])}</a>' if c['n'] == s['name']  # D.C. is one county
             else f'<a href="../{code}.html#counties">Another {esc(county_noun(st))} in {esc(s["name"])}</a>')
    other = (f'<p class="countylink">{first} · '
             f'<a href="{root}county.html">Find yours by ZIP code</a></p>')
    top = hero(esc(nice), lede, other).replace('<div class="wrap">', '<div class="wrap">' + crumbs, 1)
    local = ''
    if c.get('pg'):
        local = (f'<div class="localbox"><strong>We have a local guide for {esc(c["n"])}.</strong> <a href="{root}{esc(c["pg"])}">'
                 f'Open the {esc(c["n"])} guide</a> for hand-checked listings, then come back here for the rest.</div>')
    rows = county_rows(data, st, fips, shard, x, root)
    body = (top + urgent_strip(data, root)
            + finder(f'Search every listing for {c["n"]}', 'town, name, Section 8, dental…')
            + f'<section class="wrap needs" aria-label="Help in {esc(nice)}">{county_glance(rows, c["n"], root)}{local}{rows}</section>'
            + kind_word(f'{root}help.html#take-care', root)
            + f'<section class="wrap slim closing"><p>Listings come from federal directories and are not confirmed by phone. '
              f'A phone number or address may be out of date. <a href="{root}county.html#sources">Where these listings come from</a> · '
              f'<a href="{root}report.html">Report a problem</a>.</p></section>')
    desc = county_desc(nice, c, shard)
    base = f"https://{data['site']['domain']}/"
    title = county_title(c, s)
    about = {'@type': 'CollectionPage', '@id': base + path, 'url': base + path, 'name': title,
             'description': desc, 'inLanguage': 'en', 'isPartOf': {'@id': base + '#website'},
             'about': {'@type': 'AdministrativeArea', 'name': nice}}
    trail = breadcrumbs(data, [('Help by state', 'states.html'), (s['name'], f'states/{code}.html'), (c['n'], path)])
    return path, page(data, path, title, desc, body, head_extra=structured_data(about, trail),
                      slots=('county',), scripts=kind_word_scripts(root))


def build_county_pages(data):
    x = christmas_shard()
    out = {}
    for st, shard in county_shards().items():
        for fips in sorted(shard['c']):
            path, html_ = build_county_page(data, st, fips, shard, x)
            out[path] = html_
    return out


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
<h2>How we choose listings</h2><ul class="iconlist" role="list"><li>{icon('heart')}We list free or low-cost public programs, nonprofits and official locators. We do not list private businesses, and nobody pays to be listed.</li><li>{icon('doc')}Each listing links to the published sources it came from and shows the date it was checked.</li><li>{icon('phone')}Contacts come from official sources and are not confirmed by telephone. Phone numbers and websites change. If one is wrong, <a href="report.html">tell us</a>.</li><li>{icon('refresh')}Every link is checked automatically each month, and a person reviews any that fail.</li><li>{icon('lock')}Domestic violence shelter addresses are never listed. We point to the hotline or state coalition that places people safely.</li></ul>
<h2>What this site is not</h2><p>It is not an emergency service. If you or someone else is in danger, call 911. It does not give legal, medical or financial advice, and it cannot sign you up for anything.</p>
{advertise(site)}
<h2 id="contact">Contact us</h2><p>Email <a href="{esc(mail_href(site, f'{site["name"]}: a question'))}">{esc(site["corrections_email"])}</a> with a question, a correction, an idea for a listing or an advertising request. To fix one listing, <a href="report.html">Report a problem</a> is quickest. We read every message, but this is not an emergency line.</p>
<h2>Your privacy and safety</h2><ul><li>There is no sign-up, and the Yoga Mom Talk pages have no forms. The OhioMom pages have a few short forms for reports and questions; our <a href="privacy.html">Privacy page</a> says what they send.</li><li>We count visits with GoatCounter, which does not use cookies and does not record who you are. Nothing you type in a search or ZIP code box is sent.</li><li>The site may show ads. Each one is labeled Advertisement and kept apart from the listings. If we use Google AdSense, we ask it for non-personalized ads only, and its code stays off our help pages. Google may still set its own cookies; the <a href="privacy.html#ads">Privacy page</a> says more.</li><li>This site is hosted on GitHub Pages, which logs visitors' internet addresses for security. The OhioMom pages also load a script from Wix, which runs their forms and may set a few cookies. We do not control those.</li><li>A <strong>Leave this site</strong> button is on every page. It takes you to a weather search and removes this page from your back button.</li><li>It cannot erase your browser history. If someone else may check your device, use a private or incognito window, or a device they cannot reach.</li><li>Sites we link to have their own privacy practices.</li></ul>
<p>The <a href="terms.html">Terms of use</a> cover using this site.</p>
<h2>Credit and license</h2><p>{esc(data["attribution"])} The data on this site is licensed CC BY 4.0 and the code is MIT. Listings describe third-party organizations from their published sources. The license covers the compilation and gives no rights in those organizations' names or marks.</p></div></section>'''
    return page(data, 'about.html', 'About', f'Who runs {site["name"]}, how listings are chosen and checked, and how your privacy and safety are protected.', body)


def mail_href(site, subject, body=''):
    href = f'mailto:{site["corrections_email"]}?subject={urllib.parse.quote(subject)}'
    return href + (f'&body={urllib.parse.quote(body)}' if body else '')


def advertise(site):
    """Who may advertise and on what terms. Ads pay for the site; they never touch the listings."""
    href = mail_href(site, f'Advertising on {site["name"]}', 'Who we are:\nWhat we would like to show:\nOur website:\n')
    return (f'<h2 id="advertise">Advertise with us</h2><p>{esc(site["name"])} and OhioMom may carry a few ads to help keep the site free. '
            'We welcome businesses and groups that serve families: family and parenting services, maternal and baby health, '
            'yoga and wellness, child care, and the like.</p><ul>'
            '<li>Every ad is labeled Advertisement and kept apart from the resource listings and the help lines.</li>'
            '<li>An ad never changes what is listed, what a listing says or the order listings are in. Nobody can pay to be listed.</li>'
            '<li>Ads are never placed inside a crisis or help-now section, and never on our pages for a place to stay tonight or for taking care of yourself.</li>'
            '<li>We review every ad before it runs. We turn down ads that are misleading, and anything aimed at people in crisis.</li></ul>'
            f'<p>To ask about advertising, <a href="{esc(href)}">email us</a> '
            f'at <strong>{esc(site["corrections_email"])}</strong>. Tell us who you are and what you would like to show.</p>')


PRIVACY_UPDATED = '2026-11-23'


def build_privacy(data):
    """What the site collects, plainly. Keep it true: change it in the same commit as anything it describes."""
    site = data['site']
    name = esc(site['name'])
    email = esc(site['corrections_email'])
    updated = lib.pretty_date(PRIVACY_UPDATED)
    lede = (f'What this site collects, what it does not, and the choices you have. '
            f'Last updated <time datetime="{PRIVACY_UPDATED}">{updated}</time>.')
    body = hero('Privacy', lede) + f'''
<section class="wrap"><div class="steps">
{icon_summary('At a glance', [('lock', 'There is no sign-up and no account.'),
                              ('doc', 'Nothing you type in a search box or ZIP code box is sent or saved.'),
                              ('people', 'We count visits with GoatCounter, which does not use cookies and does not record who you are.'),
                              ('heart', 'We do not sell personal information.')])}
<p>This page covers {name} at {esc(site["domain"])}, including the OhioMom pages and the Ohio family guide. It is run by Travis and Deborah Vought.</p>
<h2 id="hosting">Who hosts the site</h2><p>The site is hosted on GitHub Pages. GitHub logs the internet address of each visitor for security purposes. The OhioMom pages also load a script from Wix, which runs their forms and may set a few cookies of its own. We do not control those. GitHub's and Wix's own privacy policies say what they collect.</p>
<h2 id="counting">Visit counting</h2><p>We count visits with GoatCounter, a visit counter that does not use cookies and does not record who you are. For each page view it receives the address of the page (never a search or ZIP code you typed), the site that linked you here, your browser type and screen size, and a rough location (the country) worked out from your internet address. Your internet address itself is not stored. We use the totals to see which pages help people.</p>
<h2 id="device">What stays on your device</h2><ul><li>The {name} pages store nothing of their own on your device. Pages that show Google ads load Google's ad code, which can set its own cookies (see Advertising below). Nothing you type in a search box or ZIP code box is sent or saved.</li><li>The OhioMom pages remember the area you pick, and which quick polls you have answered, in this browser only. Wix may set a few cookies of its own on the OhioMom pages.</li><li>The <strong>Leave this site</strong> button takes you to a weather search. It cannot erase your browser history.</li></ul>
<h2 id="forms">Sign-up and forms</h2><ul><li>There is no sign-up and no account.</li><li>The {name} pages have no forms. The Report a problem page opens your own email app, and nothing is sent until you send it from there.</li><li>The OhioMom pages have a few short forms: Report a problem, the message box and quick polls on Talk to us, and a question at the bottom of some pages, "Did you find what you came for?" What you send goes to our account on Wix, and we read it there. With a poll answer, a message or that question we also receive the page you were on and, if you picked one, your Ohio area. We ask for an email address only if you want a reply. Sending one saves an anonymous visitor ID in your browser so Wix can deliver it.</li><li>Please leave out private details about your situation. These forms are not watched for emergencies.</li></ul>
<h2 id="ads">Advertising</h2><p>This site shows ads. Every ad is labeled "Advertisement" and kept apart from the resource listings. We use Google AdSense and ask Google to show only non-personalized ads, which are not chosen from your browsing on this or other sites. Google and its partners may still use cookies or similar technology to limit how often an ad is shown, to count ads and to stop fraud. Google's ad code never loads on the Find help, Christmas help or Worldwide pages, the OhioMom help pages, the family guide, or the About, Privacy, Terms and Report pages. You can turn off personalized ads at <a href="https://adssettings.google.com" rel="noopener">https://adssettings.google.com</a> and learn more at <a href="https://policies.google.com/technologies/ads" rel="noopener">https://policies.google.com/technologies/ads</a>, or opt out of many networks at <a href="https://optout.aboutads.info" rel="noopener">https://optout.aboutads.info</a>.</p><p>An ad never changes what is listed or the order of the listings. How we take ads is on the <a href="about.html#advertise">About page</a>.</p>
<h2 id="selling">We do not sell your information</h2><p>We do not sell personal information.</p>
<h2 id="children">Children</h2><p>This site is for parents and caregivers. It is not directed to children under 13, and we do not knowingly collect information from them.</p>
<h2 id="links">Other sites</h2><p>Listings and ads link to other websites. Those sites have their own privacy practices.</p>
<h2 id="contact">Questions</h2><p>Write to <a href="{esc(mail_href(site, f"{site['name']}: privacy question"))}">{email}</a>, or use <a href="report.html">Report a problem</a>. If this page changes, the date at the top changes with it. The <a href="terms.html">Terms of use</a> cover using the site.</p>
</div></section>'''
    return page(data, 'privacy.html', 'Privacy',
                f'What {site["name"]} collects and what it does not: hosting on GitHub Pages, no sign-up, the OhioMom forms, and how ads and ad cookies work.', body,
                head_extra=structured_data(breadcrumbs(data, [('Privacy', 'privacy.html')])))


TERMS_UPDATED = '2026-11-22'


def build_terms(data):
    """The plain terms for using the site (November 22, 2026), the page ad networks' reviewers look for."""
    site = data['site']
    name = esc(site['name'])
    email = esc(site['corrections_email'])
    updated = lib.pretty_date(TERMS_UPDATED)
    lede = f'The plain terms for using {name}. Last updated <time datetime="{TERMS_UPDATED}">{updated}</time>.'
    body = hero('Terms of use', lede) + f'''
<section class="wrap"><div class="steps">
{icon_summary('At a glance', [('heart', f'{name} is a free directory of public programs, nonprofits and official locators for mothers and caregivers.'),
                              ('phone', 'It is information, not an emergency service. If you or someone else is in danger, call 911.'),
                              ('doc', 'Confirm with the program before you rely on a listing.'),
                              ('coins', 'Ads are labeled Advertisement and kept apart from the listings.')])}
<p>These terms cover {name} at {esc(site["domain"])}, including the OhioMom pages and the Ohio family guide. It is run by Travis and Deborah Vought. Using the site means you accept these terms.</p>
<h2 id="what">What this site is</h2><p>{name} is a free directory of public programs, nonprofits and official locators for mothers and caregivers. It is information, not an emergency service, and it does not give legal, medical or financial advice. If you or someone else is in danger, call 911 or your local emergency number.</p>
<h2 id="check">Check before you rely on a listing</h2><p>Listings come from published official and organization sources and show the date they were checked. They are not confirmed by telephone, and programs change. Confirm with the program before you rely on it. If a listing is wrong, <a href="report.html">tell us</a> and we fix it.</p>
<h2 id="ads">Ads</h2><p>Ads are labeled Advertisement and kept apart from the listings. They are paid for by the advertiser, and we do not vouch for what an advertiser offers. An ad never changes what is listed or the order of the listings. <a href="about.html#advertise">How we take ads</a></p>
<h2 id="links">Other sites</h2><p>Listings and ads link to sites we do not run. They have their own terms and privacy rules.</p>
<h2 id="warranty">No warranty</h2><p>The site is provided as it is, without any warranty. We are not responsible for decisions made on the strength of a listing, or for what another organization does or does not provide.</p>
<h2 id="use">Using what is here</h2><p>{esc(data["attribution"])} The data on this site is licensed CC BY 4.0 and the code is MIT. Those licenses give no rights in the names or marks of the organizations listed.</p>
<h2 id="privacy">Your information</h2><p>The <a href="privacy.html">Privacy page</a> says what this site collects and what it does not.</p>
<h2 id="contact">Changes and questions</h2><p>We may update these terms and will change the date at the top when we do. Questions: <a href="{esc(mail_href(site, f"{site['name']}: terms question"))}">{email}</a>.</p>
</div></section>'''
    return page(data, 'terms.html', 'Terms of use',
                f'The terms for using {site["name"]}: a free information directory, listings to confirm with the program, labeled ads and no warranty.', body,
                head_extra=structured_data(breadcrumbs(data, [('Terms of use', 'terms.html')])))


REPORT_STEPS = ('<figure class="steps-fig"><figcaption class="sr">How to report a problem, step by step</figcaption>'
                + flow([('letter', 'Email us. That opens your email app with a short note to start from.'),
                        ('doc', 'Tell us which page or listing, and what is wrong.'),
                        ('people', 'A person will review it.')], 'flow across') + '</figure>')


def build_report(data):
    site = data['site']
    subject = urllib.parse.quote(f'{site["name"]}: report a problem')
    mbody = urllib.parse.quote('Page or listing:\nWhat is wrong, or what should we add:\nA link or phone number for the right information:\n')
    href = f'mailto:{site["corrections_email"]}?subject={subject}&body={mbody}'
    body = hero('Report a problem', 'Found a phone number or link that is wrong? Know a group we should list? A person will review it.') + f'''
<section class="wrap"><div class="steps">{REPORT_STEPS}<p><a class="btn big" href="{esc(href)}">Email us</a></p><p>That opens your email app with a short note to start from. Or write to <strong>{esc(site["corrections_email"])}</strong>.</p><ul><li>Tell us which page or listing, and what is wrong.</li><li>Send a link to the right information if you have one.</li><li>Please leave out private details about your own situation.</li></ul><p class="note">This is not monitored for emergencies. If you need help now, call 911, or see <a href="help.html#help-now">Get help now</a>. We do not store anything on this site; your email goes only to the address above.</p></div></section>'''
    return page(data, 'report.html', 'Report a problem', 'Tell us about a wrong phone number or link, or suggest a moms group to list.', body)


# A small signpost beside the heading of the page-not-found page: decoration only, drawn for this site.
SIGNPOST = ('<svg class="art" viewBox="0 0 160 112" width="160" height="112" aria-hidden="true" focusable="false">'
            '<circle cx="122" cy="30" r="14" fill="#ffe3a3"/><circle cx="122" cy="30" r="9" fill="#ffcb52"/>'
            '<path d="M0 94c26-12 52-14 80-5s54 7 80-5v28H0z" fill="#a8ddd3"/><path d="M0 102c34-9 62-7 92 0s46 5 68-2v14H0z" fill="#12766f" opacity=".85"/>'
            '<rect x="66" y="22" width="6" height="74" rx="2" fill="#8a5a3c"/>'
            '<path d="M40 30h48l9 8-9 8H40z" fill="#fff" stroke="#cf2f5b" stroke-width="2.4" stroke-linejoin="round"/>'
            '<path d="M98 52H50l-9 8 9 8h48z" fill="#fff" stroke="#12766f" stroke-width="2.4" stroke-linejoin="round"/>'
            '<path d="M51 38h28M60 60h28" stroke="#655c78" stroke-width="2.4" stroke-linecap="round"/>'
            '<path d="M69 17s-5-3-5-6.4a2.8 2.8 0 0 1 5-1.7 2.8 2.8 0 0 1 5 1.7C74 14 69 17 69 17z" fill="#cf2f5b"/></svg>')


def build_404(data):
    body = hero('We could not find that page', 'It may have moved. Try one of these.').replace('<div class="wrap">', '<div class="wrap withart">' + SIGNPOST, 1) + '''
<section class="wrap"><p class="actions"><a class="btn big" href="/index.html">Go to the home page</a> <a class="btn" href="/help.html">Find help</a> <a class="btn" href="/states.html">Help by state</a></p></section>'''
    # 404 is served from any path, so it uses root-absolute links and assets.
    html = page(data, '404.html', 'Page not found', 'This page could not be found.', body)
    return (html.replace('href="assets/', 'href="/assets/').replace('src="assets/', 'src="/assets/')
                .replace('href="index.html"', 'href="/index.html"').replace('href="help.html', 'href="/help.html')
                .replace('href="connect.html', 'href="/connect.html').replace('href="states.html', 'href="/states.html')
                .replace('href="yoga.html', 'href="/yoga.html').replace('href="about.html', 'href="/about.html')
                .replace('href="report.html', 'href="/report.html').replace('href="privacy.html', 'href="/privacy.html'))


def build_all(data):
    files = {
        'index.html': build_index(data), 'help.html': build_help(data), 'connect.html': build_connect(data),
        'states.html': build_states_index(data), 'christmas.html': build_christmas(data), 'inside.html': build_inside(data), 'kinship.html': build_kinship(data), 'yoga.html': build_yoga(data), 'about.html': build_about(data),
        'report.html': build_report(data), '404.html': build_404(data), 'county.html': build_county(data),
        'privacy.html': build_privacy(data), 'terms.html': build_terms(data),
    }
    for s in data['states']:
        files[f'states/{s["abbr"].lower()}.html'] = build_state(data, s)
    files.update(build_county_pages(data))
    for p in files:  # "in the District of Columbia", as it reads in a sentence
        if p == 'states/dc.html' or p.startswith('states/dc/'):
            files[p] = the_district(files[p])
    if data.get('world', {}).get('countries'):
        files['world.html'] = build_world(data)
        for c in data['world']['countries']:
            files[f'countries/{c["slug"]}.html'] = build_country(data, c)
    sayings = extras.approved_affirmations()
    if sayings:  # no page until the owner has approved a batch
        files['affirmations.html'] = build_affirmations(data, sayings)
        files['jokes.html'] = build_jokes_moved(data)
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
    if ads.ads_txt(data.get('adsense_client', '')):
        files['ads.txt'] = ads.ads_txt(data['adsense_client'])
    return files


def ohio_ad_files(data):
    """The OhioMom pages that may carry an ad, with this build's ad (or none) last in <main>. The rest of each page is
    hand-kept source and is left as it is (scripts/ads.py)."""
    running = running_ads(data)
    out = {}
    for rel, slots in ads.ohio_pages().items():
        text = (ROOT / rel).read_text(encoding='utf-8')
        text = ads.place(text, ads.pick(running, slots), '../' * rel.count('/'))
        out[rel] = ads.place_network(text, data.get('adsense_client', ''), slots)
    return out


def main():
    check = '--check' in sys.argv
    data = lib.load()
    problems = ads.check(data['ads']) + ads.check_client(data.get('adsense_client', ''))
    if problems:
        print('data/ads.json:\n' + '\n'.join(problems))
        sys.exit(1)
    files = build_all(data)
    files.update(ohio_ad_files(data))
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
