#!/usr/bin/env python3
"""Build every page from data/*.json.

    python3 scripts/build.py          write the site
    python3 scripts/build.py --check  fail if the files on disk differ from the data

Edit data or this script, never the built pages. The Ohio pages under ohio/ are separate source, not built here.
"""
import sys
import urllib.parse
from html import escape as esc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ymt_lib as lib  # noqa: E402

ROOT = lib.ROOT
EXIT_URL = 'https://www.google.com/search?q=weather'
NAV = [('help.html', 'Find help'), ('connect.html', 'Meet moms'), ('states.html', 'By state'), ('yoga.html', 'Yoga')]
FOOT = [('help.html', 'Find help'), ('connect.html', 'Meet moms'), ('states.html', 'By state'),
        ('yoga.html', 'Yoga with Deborah'), ('about.html', 'About'), ('report.html', 'Report a problem')]
TILES = [
    ('t1', '🤝', 'Meet other moms', 'Groups and communities near you and online.', 'connect.html'),
    ('t2', '🧺', 'A hand with food, bills or housing', 'SNAP, WIC, energy bills and food banks.', 'help.html#food-bills'),
    ('t3', '🍼', "I'm pregnant or have a new baby", 'Health coverage, nursing help, diapers, safe sleep.', 'help.html#pregnancy-baby'),
    ('t4', '🧩', 'My child learns or grows differently', 'Autism, ADHD, delays, school help and other parents.', 'help.html#kids-differently'),
    ('t5', '💛', 'Parenting on my own', 'Child care, Head Start, child support and legal help.', 'help.html#single-parent'),
    ('t6', '☕', 'Take care of me', 'Someone to talk to on the hard days.', 'help.html#take-care'),
]
# ohiomom.org is one way into this site: its home page goes straight to the Ohio landing page.
OHIO_REDIRECT = ('\n<script>if(/(^|\\.)ohiomom\\.org$/i.test(location.hostname)){'
                 'location.replace("ohio/"+location.search+location.hash)}</script>')
STATE_SECTIONS = ['help-now', 'food-bills', 'pregnancy-baby', 'kids-differently', 'single-parent', 'take-care']


def tel(p):
    return lib.tel_href(p)


def logo_html(name):
    words = name.split()
    return esc(' '.join(words[:-1])) + ' <span>' + esc(words[-1]) + '</span>'


def page(data, path, title, desc, body, body_class='', head_extra=''):
    site = data['site']
    root = '../' * path.count('/')
    url = f"https://{site['domain']}/" + ('' if path == 'index.html' else path)
    full_title = title if title == site['name'] else f"{title} | {site['name']}"
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
<link rel="stylesheet" href="{root}assets/ymt.css">{head_extra}
</head>
<body class="{esc(body_class)}">
<a class="skip" href="#main">Skip to content</a>
<a class="exit" data-exit href="{EXIT_URL}" rel="noreferrer">Leave this site</a>
<header class="top"><a class="logo" href="{root}index.html">{logo_html(site['name'])}</a><nav class="mainnav" aria-label="Main">{nav}</nav></header>
<main id="main">
{body}
</main>
<footer class="foot">
<p class="footnav">{foot}</p>
<p>Founded by {esc(site['founder'])}. See something out of date, or know a group we should list? <a href="{root}report.html">Report a problem</a>.</p>
<p class="small">In danger right now? Call 911. {esc(site['name'])} is an information directory, not an emergency service or a provider of legal, medical or financial advice. Contacts come from published official and organization sources and are not telephone-confirmed. No tracking, cookies or sign-up.</p>
<p class="small">Ohio mom? Visit <a href="{root}{esc(site['ohio_path'])}">OhioMom</a>. Mobility and disability resources: <a href="{esc(site['mobilitytalk_url'])}">Mobility Talk</a>.</p>
</footer>
<script src="{root}assets/ymt.js"></script>
</body>
</html>
'''


def card(r, root='', compact_href=None):
    rid = esc(r['id'])
    if compact_href:
        return (f'<article class="card also" id="also-{rid}"><h3>{esc(r["name"])}</h3>'
                f'<p class="note">Also useful here. <a href="{compact_href}">See the full listing</a>.</p></article>')
    cls = 'card urgent' if r.get('urgent') else 'card'
    out = [f'<article class="{cls}" id="{rid}"><h3>{esc(r["name"])}</h3><p class="org">{esc(r["org"])}</p>',
           f'<p>{esc(r["what"])}</p><p>{esc(r["how"])}</p>']
    if r.get('text'):
        out.append(f'<p class="textline">{esc(r["text"])}</p>')
    if r.get('phone') and r.get('phone_label'):
        out.append(f'<p class="note">{esc(r["phone_label"])}</p>')
    acts = []
    if r.get('phone'):
        acts.append(f'<a class="btn call" href="{tel(r["phone"])}">Call {esc(r["phone"])}</a>')
    acts.append(f'<a class="btn" href="{esc(r["url"])}" rel="noopener">Website</a>')
    for link in r.get('links', []):
        acts.append(f'<a class="btn plain" href="{esc(link["url"])}" rel="noopener">{esc(link["label"])}</a>')
    out.append('<p class="actions">' + ''.join(acts) + '</p>')
    srcs = ' '.join(f'<a href="{esc(u)}" rel="noopener">{i}</a>' for i, u in enumerate(r['sources'], 1))
    out.append(f'<p class="src">Checked {esc(lib.pretty_date(r["reviewed_on"]))}. Sources: {srcs}</p></article>')
    return ''.join(out)


def cards(records, root='', compact=None):
    return '<div class="cards">' + ''.join(card(r, root, (compact or {}).get(r['id'])) for r in records) + '</div>'


def sec_map(data):
    return {s['id']: s for s in data['sections']}


def hero(title, lede, extra='', cls='slim'):
    return f'<section class="hero {cls}"><div class="wrap"><h1>{title}</h1><p class="lede">{lede}</p>{extra}</div></section>'


# ---------------------------------------------------------------- pages
def build_index(data):
    site = data['site']
    tiles = ''.join(f'<a class="tile {c}" href="{h}"><span class="ico" aria-hidden="true">{i}</span><strong>{esc(t)}</strong><span>{esc(d)}</span></a>'
                    for c, i, t, d, h in TILES)
    urgent = [r for r in data['resources'] if r['id'] in ('us-ndvh', 'us-988', 'us-childhelp')]
    calls = ''.join(
        f'<div class="callbox"><h3>{esc(r["name"])}</h3><p>{esc(r["how"])}</p><p class="actions"><a class="btn call" href="{tel(r["phone"])}">Call {esc(r["phone"])}</a>'
        + (f' <span class="textline">{esc(r["text"])}</span>' if r.get('text') else '') + '</p></div>' for r in urgent)
    options = '<option value="">Choose your state</option>' + ''.join(
        f'<option value="states/{s["abbr"].lower()}.html">{esc(s["name"])}</option>' for s in data['states'])
    body = f'''{hero('Hi, mom. What do you need today?', 'A place for moms to connect, and a short list of real help for when things get hard. Free, private, no sign-up.', f'<div class="tiles">{tiles}</div>', 'home')}
<section class="wrap" id="now"><h2>Need help right now?</h2><p>These lines are free and answer any hour. If you or your child are in danger, call 911.</p><div class="callrow">{calls}</div></section>
<section class="wrap" id="state"><h2>Help in your state</h2><p>Food, child care, health coverage and disability help work differently in every state. Pick yours for the right offices and phone numbers.</p><div class="statepick"><div><label for="statepick">Your state</label><select id="statepick" data-state-pick>{options}</select></div><a class="btn" href="states.html">See all states</a></div>
<div class="localbox"><strong>Ohio mom?</strong> <a href="{esc(site['ohio_path'])}">OhioMom</a> has county offices, local events and a full Ohio family guide.</div></section>
<section class="wrap"><div class="steps"><h2>How this site works</h2><ul><li><strong>Free and private.</strong> No sign-up, no ads, no tracking, no cookies. A Leave this site button is on every page.</li><li><strong>Real sources.</strong> Every listing links to the official pages it came from and shows the date it was checked.</li><li><strong>Nobody pays to be listed.</strong> We list public programs, nonprofits and official locators, not private businesses.</li></ul><p><a href="about.html">More about how we choose and check listings</a></p></div></section>
<section class="wrap cta"><h2>Yoga with Deborah</h2><p>{esc(site['name'])} was started by {esc(site['founder'])}, a yoga instructor and personal trainer. She takes private and small-group sessions.</p><p><a class="btn big" href="yoga.html">Learn more</a></p></section>'''
    return page(data, 'index.html', site['name'],
                f"{site['tagline']} Free, private help for moms in all 50 states and DC: food, child care, health coverage, disability and crisis lines.",
                body, 'home', head_extra=OHIO_REDIRECT)


def build_help(data):
    secs = [s for s in data['sections'] if not s.get('page')]
    chips = '<ul class="chips">' + ''.join(f'<li><a href="#{s["id"]}">{s["icon"]} {esc(s["label"])}</a></li>' for s in secs) + '</ul>'
    parts = []
    for s in secs:
        primary = [r for r in data['resources'] if r['section'] == s['id']]
        also = [r for r in data['resources'] if s['id'] in r.get('also', [])]
        compact = {r['id']: f"#{r['id']}" for r in also}
        parts.append(f'<section class="group wrap" id="{s["id"]}"><h2>{s["icon"]} {esc(s["label"])}</h2><p class="quiet">{esc(s["summary"])}</p>{cards(primary + also, "", compact)}</section>')
    banner = '<div class="banner"><strong>In danger right now? Call 911.</strong> The lines below are free. Domestic violence shelter addresses are never listed here for safety.</div>'
    body = hero('Find help', 'Clear next steps and who to call. Pick what you need. These are national programs that work in every state. For your state\'s offices, <a href="states.html">choose your state</a>.', chips + banner) + ''.join(parts)
    return page(data, 'help.html', 'Find help for moms',
                'Free national help for moms: crisis lines, food and bills, pregnancy and baby, kids who learn differently, single parents and military families.', body)


def build_connect(data):
    prim = [r for r in data['resources'] if r['section'] == 'connect']
    also = [r for r in data['resources'] if 'connect' in r.get('also', [])]
    site = data['site']
    body = hero('Meet other moms', 'Moms groups, feeding groups and people who get it. Find one near you or online.') + f'''
<section class="group wrap"><h2>Groups for moms</h2><p class="quiet">Local chapters and meetups run by volunteers. Groups differ, so ask how one runs before you go.</p>{cards(prim)}</section>
<section class="group wrap"><h2>Support for the hard days</h2><p class="quiet">Feeding help and support lines from people who have been there.</p>{cards(also)}</section>
<section class="wrap"><div class="localbox"><strong>Ohio mom?</strong> <a href="{esc(site['ohio_path'])}">OhioMom</a> lists Ohio groups, meetups and events by region and county.</div></section>
<section class="wrap cta"><h2>Run a group, or know a good one?</h2><p>If it is free or low cost and good for moms, we want to list it. Nobody pays to be listed here.</p><p><a class="btn big" href="report.html">Tell us about it</a></p></section>'''
    return page(data, 'connect.html', 'Meet other moms',
                'Moms groups, breastfeeding groups and support for the hard days, in person and online, across the U.S.', body)


def build_states_index(data):
    items = ''.join(f'<li><a href="states/{s["abbr"].lower()}.html">{esc(s["name"])}<small>{s["abbr"]}</small></a></li>' for s in data['states'])
    body = hero('Help by state', 'All 50 states and the District of Columbia. Pick yours.') + f'<section class="wrap"><ul class="statelist">{items}</ul><p class="note">Looking for something national? See <a href="help.html">Find help</a>.</p></section>'
    return page(data, 'states.html', 'Help by state',
                'Pick your state for SNAP, WIC, child care, health coverage, disability help and domestic violence resources.', body)


def build_state(data, s):
    secs = sec_map(data)
    recs = lib.state_records(s, data)
    by = {}
    for r in recs:
        by.setdefault(r['section'], []).append(r)
    nat = {r['id']: r for r in data['resources']}
    by['help-now'] = [nat['us-ndvh'], nat['us-988'], nat['us-childhelp']] + by.get('help-now', [])
    by['take-care'] = [nat['us-tlc-mama'], nat['us-psi'], nat['us-parent-helpline']]
    order = {'food-bills': ['snap', 'wic', 'energy', '211'], 'pregnancy-baby': ['coverage', 'health-centers', 'diapers']}
    parts = []
    for sid in STATE_SECTIONS:
        s_ = secs[sid]
        items = by.get(sid, [])
        parts.append(f'<section class="group wrap" id="{sid}"><h2>{s_["icon"]} {esc(s_["label"])}</h2>{cards(items, "../")}</section>')
    local = ''
    if s.get('local_site'):
        ls = s['local_site']
        local = f'<div class="localbox"><strong>Ohio mom?</strong> <a href="../{esc(ls["path"])}">{esc(ls["name"])}</a> is {esc(ls["what"][0].lower() + ls["what"][1:])}</div>'
    chips = '<ul class="chips">' + ''.join(f'<li><a href="#{i}">{secs[i]["icon"]} {esc(secs[i]["label"])}</a></li>' for i in STATE_SECTIONS) + '</ul>'
    note = ''
    if not s.get('parent_center'):
        note = f'<p class="note">{esc(data["states_meta"].get("parent_centers_note", ""))}</p>'
    intro = (f'National hotlines work in every state. Below are the {esc(s["name"])} offices and locators to start with. '
             f'<a href="../states.html">Choose another state</a>.')
    body = hero(f'{esc(s["name"])}: help for moms', intro, chips + local, 'slim') + ''.join(parts) + \
        f'<section class="wrap cta"><h2>Meet other moms</h2><p>Find a group near you or online.</p><p><a class="btn big" href="../connect.html">Meet moms</a></p></section>'
    return page(data, f'states/{s["abbr"].lower()}.html', f'{s["name"]}: help for moms',
                f'Free help for moms in {s["name"]}: SNAP, WIC, child care, health coverage, disability services and domestic violence resources.',
                body)


def build_yoga(data):
    site = data['site']
    body = hero('Yoga and training with Deborah', f'{esc(site["founder"])} started {esc(site["name"])}. She is also a yoga instructor and a personal trainer, and she takes private and small-group sessions.') + f'''
<section class="wrap"><div class="steps"><h2>What she offers</h2><h3>Yoga sessions</h3><p>Private or small-group yoga. Come on your own or bring a couple of friends.</p><h3>Personal training</h3><p>One-on-one training built around where you are right now.</p><p>This is Deborah's own paid work. Ask for current rates when you write. Everything else on {esc(site["name"])} stays free, and no listing on this site is paid for.</p><p><a class="btn big" href="{esc(site["ohio_yoga_path"])}">Ask about a session</a></p><p class="note">The booking form is on the OhioMom pages, where Deborah's sessions are taken.</p></div></section>'''
    return page(data, 'yoga.html', 'Yoga with Deborah',
                f'Private and small-group yoga and personal training with {site["founder"]}, founder of {site["name"]}.', body)


def build_about(data):
    site = data['site']
    body = hero(f'About {esc(site["name"])}', f'A place where moms can connect, with real help for the moms who need it.') + f'''
<section class="wrap"><div class="steps"><h2>Who runs it</h2><p>{esc(site["name"])} was founded by {esc(site["founder"])}. It grows out of <a href="{esc(site["ohio_path"])}">OhioMom</a>, her Ohio hub for mothers, which is now the Ohio part of this site. The same approach now reaches every state.</p>
<p>It is an independent project. It is not affiliated with any podcast, show or organization named "Mom Talk".</p>
<h2>How we choose listings</h2><ul><li>We list free or low-cost public programs, nonprofits and official locators. We do not list private businesses, and nobody pays to be listed.</li><li>Each listing links to the published sources it came from and shows the date it was checked.</li><li>Contacts come from official sources and are not confirmed by telephone. Phone numbers and websites change. If one is wrong, <a href="report.html">tell us</a>.</li><li>Every link is checked automatically each month, and a person reviews any that fail.</li><li>Domestic violence shelter addresses are never listed. We point to the hotline or state coalition that places people safely.</li></ul>
<h2>What this site is not</h2><p>It is not an emergency service. If you or someone else is in danger, call 911. It does not give legal, medical or financial advice, and it cannot sign you up for anything.</p>
<h2>Your privacy and safety</h2><ul><li>No tracking, no cookies, no ads, no sign-up, no forms, and no third-party scripts.</li><li>A <strong>Leave this site</strong> button is on every page. It takes you to a weather search and removes this page from your back button.</li><li>It cannot erase your browser history. If someone else may check your device, use a private or incognito window, or a device they cannot reach.</li><li>Sites we link to have their own privacy practices.</li></ul>
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
        'report.html': build_report(data), '404.html': build_404(data),
    }
    for s in data['states']:
        files[f'states/{s["abbr"].lower()}.html'] = build_state(data, s)
    domain = data['site']['domain']
    pages = sorted(p for p in files if p != '404.html')
    # Pages that only pass the visitor on (marked noindex) stay out of the sitemap.
    ohio = sorted(str(p.relative_to(ROOT)) for p in (ROOT / 'ohio').rglob('*.html')
                  if 'name="robots" content="noindex"' not in p.read_text(encoding='utf-8'))
    pages += ohio + ['family-guide.html']

    def loc(p):
        return '' if p == 'index.html' else 'ohio/' if p == 'ohio/index.html' else p
    urls = ''.join(f'  <url><loc>https://{domain}/{loc(p)}</loc></url>\n' for p in sorted(set(pages)))
    files['sitemap.xml'] = f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}</urlset>\n'
    files['robots.txt'] = f'User-agent: *\nAllow: /\n\nSitemap: https://{domain}/sitemap.xml\n'
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
