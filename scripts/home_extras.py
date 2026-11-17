#!/usr/bin/env python3
"""The picture and the joke of the day on the two front pages.

Both front pages carry the same two extras, drawn here so they cannot drift apart:

- **The picture.** A mom holds tree pose on her mat while her child says "Mom? Mom? MOM!" until she opens one
  eye, and then says "Hi." It is inline SVG, moved by CSS. The rules are in templates/home-extras.css, and this
  script copies them to the end of assets/ymt.css and ohio/assets/site.css, between marker comments, so the two
  sites cannot drift apart: edit the template, never the copies. The picture is decoration, so it is hidden
  from screen readers, and it holds still for visitors whose device asks for reduced motion. The OhioMom
  picture is the same room with a cardinal at the window and Ohio on the wall.
- **The joke of the day.** data/jokes.json holds one joke for each date. Only jokes marked `approved` are ever
  written into a page; the owner approves each batch before it runs. The page carries the approved jokes and a
  few lines of script that show the one for the visitor's own date, so the joke changes at midnight on her
  clock and nothing is sent anywhere. When a batch runs out the list starts over, one a day, until new jokes
  are approved. jokes.html is the running list of the ones that have already run.

The national front page (index.html) and jokes.html are built by scripts/ymt_build.py, which calls the
functions here. The OhioMom front page (ohio/index.html) is static source, so this script writes the same
blocks into it between marker comments, the way scripts/prerender_ohio.py does for the events.

    python3 scripts/home_extras.py                    write the blocks into ohio/index.html and the rules into both stylesheets
    python3 scripts/home_extras.py --check            check data/jokes.json, and fail if a page or stylesheet is out of step
    python3 scripts/home_extras.py --approve          mark every joke approved (after the owner has approved the batch)
    python3 scripts/home_extras.py --approve --start 2026-12-18
                                                      the same, and re-date the batch to start on that day
"""
import datetime
import json
import re
import sys
from html import escape as esc
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JOKES = ROOT / 'data' / 'jokes.json'
OHIO_HOME = ROOT / 'ohio' / 'index.html'
STYLE = ROOT / 'templates' / 'home-extras.css'
SHEETS = ('assets/ymt.css', 'ohio/assets/site.css')
MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July',
          'August', 'September', 'October', 'November', 'December']
JOKE_MAX = 220  # characters: a joke is a line or two, never a story

INK, LEGS, SKIN, HAIR = '#2b2140', '#3b2e5a', '#e4b08a', '#4a2f27'
BRAND, TEAL, SUN = '#cf2f5b', '#12766f', '#ffcb52'
HEART = 'M0-1.5C-1.5-4.5-6-3.5-5 .5C-4.2 3 0 6 0 6S4.2 3 5 .5C6-3.5 1.5-4.5 0-1.5Z'
# Ohio's outline, 27.7 wide by 30 tall, from the state's corner and river coordinates.
OHIO = ('M.1 2.4L8.8 2.1L10.8 3L12 3.9L13.5 4.4L15.9 4.6L18.5 4L20.1 4L22.7 2.2L24.9 1.1L27.7 0L27.7 11.3L26.8 13.1'
        'L27.1 14.1L26.3 16.1L25.4 19.6L24 21.1L21.7 21.7L20.7 23L19.7 25.5L18 24.9L16.9 26.8L15.3 30L14.4 30L13.8 29'
        'L11.7 27.4L9.8 28.5L7.8 27.7L5.9 27.1L3.5 25.5L2 24.3L0 24.2Z')


# ---------------------------------------------------------------- the picture
def heart(x, y, size, fill, cls=''):
    """A small heart, about 10 units wide at size 1, with its middle near (x, y)."""
    c = f' class="{cls}"' if cls else ''
    return f'<g transform="translate({x} {y}) scale({size})"><path{c} d="{HEART}" fill="{fill}"/></g>'


def bubble(n, text, width, height, size, fill=INK):
    """One thing the child says: a white bubble above her, with a tail that points down to her. Each has its moment in the loop."""
    x, bottom, r = 372, 100, 12
    y = bottom - height
    return (f'<g class="sc-b sc-b{n}"><path d="M{x} {y + r}a{r} {r} 0 0 1 {r}-{r}h{width - 2 * r}a{r} {r} 0 0 1 {r} {r}v{height - 2 * r}'
            f'a{r} {r} 0 0 1-{r} {r}h{-(width - 2 * r - 22)}l-10 11-2-11h-10a{r} {r} 0 0 1-{r}-{r}z" fill="#fff"/>'
            f'<text x="{x + width / 2:g}" y="{y + height / 2 + size * .36:.1f}" font-size="{size}" fill="{fill}">{esc(text)}</text></g>')


def scene_svg(ohio=False):
    """The front-page picture. `ohio` adds the cardinal at the window and Ohio on the wall."""
    blush = '#ee8fa0'
    p = ['<svg class="scene" viewBox="0 10 520 196" aria-hidden="true" focusable="false">'
         '<defs><linearGradient id="sc-wall" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#e6f5f0"/>'
         '<stop offset="1" stop-color="#d2ebe5"/></linearGradient>'
         '<linearGradient id="sc-sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#b9e0fa"/>'
         '<stop offset="1" stop-color="#eef8ff"/></linearGradient>'
         '<clipPath id="sc-pane"><rect x="30" y="24" width="84" height="74" rx="5"/></clipPath></defs>',
         # the room
         '<rect width="520" height="220" fill="url(#sc-wall)"/><rect y="172" width="520" height="48" fill="#f6dcc0"/>'
         '<rect y="169" width="520" height="4" fill="#fff"/>']
    # the window: morning sky, a hill, a cloud that drifts (and in Ohio, a cardinal)
    bird = ''
    if ohio:
        bird = ('<g class="sc-bird"><path d="M40 93l-10 5 2-7z" fill="#b3261e"/><ellipse cx="46" cy="90" rx="8" ry="6.5" fill="#d0342c"/>'
                '<circle cx="53" cy="84" r="5.2" fill="#d0342c"/><path d="M50 81l1.5-8.5 4.5 6.5z" fill="#d0342c"/>'
                f'<path d="M54.5 83.5q4-1.5 3.5 2-2 2-4 .5z" fill="{INK}"/><path d="M57.5 84.3l5.5 1.5-5.5 1.7z" fill="#f08a3c"/>'
                f'<circle cx="53.6" cy="82.8" r=".9" fill="{INK}"/></g>')
    p.append('<rect x="24" y="18" width="96" height="86" rx="9" fill="#fff"/><g clip-path="url(#sc-pane)">'
             '<rect x="30" y="24" width="84" height="74" fill="url(#sc-sky)"/>'
             f'<circle cx="94" cy="44" r="19" fill="{SUN}" opacity=".28"/><circle cx="94" cy="44" r="12" fill="{SUN}"/>'
             '<g class="sc-cloud" fill="#fff"><circle cx="46" cy="47" r="6.5"/><circle cx="55" cy="43" r="8.5"/>'
             '<circle cx="65" cy="47" r="6"/><rect x="42" y="46" width="27" height="7.5" rx="3.7"/></g>'
             f'<path d="M30 98V86Q50 72 72 83T114 78V98Z" fill="#9fd6a4"/>{bird}</g>'
             '<path d="M72 24V98M30 61H114" stroke="#fff" stroke-width="4"/>'
             '<rect x="18" y="101" width="108" height="8" rx="4" fill="#fff"/>'
             '<rect x="22" y="109" width="100" height="2.5" rx="1.2" fill="#b7d9d1"/>')
    # on the wall: a lotus, or Ohio with a heart
    p.append('<rect x="303" y="24" width="50" height="58" rx="6" fill="#fff"/>'
             '<rect x="308" y="29" width="40" height="48" rx="3" fill="#fff1e6"/>')
    if ohio:
        p.append(f'<path transform="translate(314.5 38)" d="{OHIO}" fill="{BRAND}"/>' + heart(327.5, 52, .8, '#fff'))
    else:
        petal = 'M0-13C5.5-7 5.5 1 0 6C-5.5 1-5.5-7 0-13Z'
        p.append('<g transform="translate(328 58)">'
                 + ''.join(f'<path d="{petal}" transform="rotate({a} 0 6)" fill="{c}"/>'
                           for a, c in ((-64, '#f6b5c6'), (64, '#f6b5c6'), (-32, '#e9799a'), (32, '#e9799a'), (0, BRAND)))
                 + '</g>')
    # a stool with her coffee, going cold
    steam = ''.join(f'<circle class="sc-steam" cx="{x}" cy="118" r="{r}" style="animation-delay:{d}s"/>'
                    for x, r, d in ((150, 3.2, 0), (154, 2.6, -1.2), (151.5, 3, -2.4)))
    p.append('<path d="M140 172L144 147M166 172L162 147" stroke="#b97c4d" stroke-width="4" stroke-linecap="round"/>'
             '<rect x="134" y="141" width="38" height="7" rx="3.5" fill="#d39a67"/>'
             '<path d="M161 128q8 0 8 5.5t-8 5.5" fill="none" stroke="#fff" stroke-width="3.2"/>'
             '<rect x="143" y="123" width="19" height="18" rx="4" fill="#fff"/>' + heart(152.5, 131.5, .62, BRAND)
             + f'<g fill="#fff">{steam}</g>')
    # a plant in the corner
    p.append('<g class="sc-leaf"><path d="M489 150C486 128 474 117 461 113C464 131 473 144 489 150Z" fill="#3f9b6e"/>'
             '<path d="M489 150C492 127 503 116 516 112C512 131 504 144 489 150Z" fill="#2f8a5f"/>'
             '<path d="M489 150C481 133 483 112 489 97C496 112 497 133 489 150Z" fill="#58b386"/></g>'
             '<path d="M474 152h30l-4 26h-22z" fill="#d9825b"/><rect x="471" y="147" width="36" height="8" rx="3.5" fill="#e79a72"/>')
    # the mat, her blocks and the bunny
    p.append('<ellipse cx="266" cy="183" rx="104" ry="5" fill="#8a5a3a" opacity=".13"/>'
             '<rect x="174" y="170" width="184" height="11" rx="5.5" fill="#2a9d8f"/>'
             '<rect x="176" y="171.5" width="180" height="3" rx="1.5" fill="#5cc3b5"/>'
             '<rect x="428" y="164" width="15" height="15" rx="3" fill="#b9a6ef"/>'
             '<rect x="443.5" y="164" width="15" height="15" rx="3" fill="#f6b5c6"/>'
             f'<rect x="435.5" y="149" width="15" height="15" rx="3" fill="{SUN}"/>'
             '<g fill="#fff"><ellipse cx="409" cy="174" rx="7.5" ry="6.5"/><circle cx="409" cy="164" r="5.5"/>'
             '<ellipse cx="406" cy="155" rx="2.4" ry="6.5" transform="rotate(-10 406 155)"/>'
             '<ellipse cx="412" cy="155" rx="2.4" ry="6.5" transform="rotate(10 412 155)"/></g>'
             '<ellipse cx="406" cy="155.5" rx="1" ry="4" transform="rotate(-10 406 155)" fill="#f6b5c6"/>'
             '<ellipse cx="412" cy="155.5" rx="1" ry="4" transform="rotate(10 412 155)" fill="#f6b5c6"/>'
             f'<circle cx="407" cy="163.5" r=".9" fill="{INK}"/><circle cx="411" cy="163.5" r=".9" fill="{INK}"/>')
    # mom, in tree pose, eyes closed
    p.append(f'<g class="sc-mom"><path d="M257 124V165" stroke="{LEGS}" stroke-width="11" stroke-linecap="round"/>'
             f'<path d="M254 168h10" stroke="{SKIN}" stroke-width="5.5" stroke-linecap="round"/>'
             f'<path d="M267 124L295 137L264 148" fill="none" stroke="{LEGS}" stroke-width="11" stroke-linecap="round" stroke-linejoin="round"/>'
             f'<path d="M264 148l-3 4" stroke="{SKIN}" stroke-width="5.5" stroke-linecap="round"/>'
             f'<path d="M250.5 117h23v9a11.5 11.5 0 0 1-23 0z" fill="{LEGS}"/>'
             f'<path d="M254 92L245 65L262 43M270 92L279 65L262 43" fill="none" stroke="{SKIN}" stroke-width="6.5" stroke-linecap="round" stroke-linejoin="round"/>'
             f'<path d="M251 122Q249 103 252 90Q262 84 272 90Q275 103 273 122Z" fill="{BRAND}"/>'
             f'<rect x="258.5" y="79" width="7" height="10" rx="3" fill="{SKIN}"/>'
             f'<circle cx="262" cy="57.5" r="6.5" fill="{HAIR}"/><circle cx="262" cy="71" r="12.5" fill="{SKIN}"/>'
             f'<path d="M249.5 71a12.5 12.5 0 0 1 25 0c-2-6-6-8.5-12.5-8.5s-10.5 2.5-12.5 8.5z" fill="{HAIR}"/>'
             f'<g fill="none" stroke="{LEGS}" stroke-width="1.7" stroke-linecap="round"><path d="M254.8 72.5q2.6 2.4 5.2 0"/>'
             '<path class="sc-lid" d="M264 72.5q2.6 2.4 5.2 0"/><path d="M257.5 78q4.5 3.2 9 0"/></g>'
             f'<circle class="sc-eye" cx="266.6" cy="72.3" r="2" fill="{LEGS}"/>'
             f'<circle cx="253" cy="76.5" r="2.5" fill="{blush}" opacity=".7"/><circle cx="271" cy="76.5" r="2.5" fill="{blush}" opacity=".7"/></g>')
    # her child, looking up at her
    p.append(f'<g class="sc-kid"><path d="M379 160V176M389 160V176" stroke="{TEAL}" stroke-width="6.5" stroke-linecap="round"/>'
             f'<ellipse cx="377.5" cy="178" rx="5" ry="2.8" fill="{BRAND}"/><ellipse cx="390.5" cy="178" rx="5" ry="2.8" fill="{BRAND}"/>'
             f'<path d="M394 144L401 156" stroke="{SKIN}" stroke-width="5" stroke-linecap="round"/>'
             f'<path class="sc-wave" d="M374 143L363 132" stroke="{SKIN}" stroke-width="5" stroke-linecap="round"/>'
             f'<rect x="373" y="137" width="22" height="27" rx="8" fill="{SUN}"/>'
             f'<circle cx="384" cy="125" r="12" fill="{SKIN}"/>'
             f'<path d="M372 125a12 12 0 0 1 24 0c-3-5.5-8-7.5-12-7.5s-9 2-12 7.5z" fill="{HAIR}"/>'
             f'<path d="M385 113.5q.5-6 6-6.5" fill="none" stroke="{HAIR}" stroke-width="2.6" stroke-linecap="round"/>'
             f'<circle cx="378.5" cy="126.5" r="1.6" fill="{LEGS}"/><circle cx="385.5" cy="126.5" r="1.6" fill="{LEGS}"/>'
             f'<path d="M379 131.5q3 2.6 6 0" fill="none" stroke="{LEGS}" stroke-width="1.6" stroke-linecap="round"/>'
             f'<circle cx="375.5" cy="130" r="2.2" fill="{blush}" opacity=".7"/><circle cx="389" cy="130" r="2.2" fill="{blush}" opacity=".7"/></g>')
    # what she says, and how it ends
    p.append(heart(326, 126, 1.5, BRAND, 'sc-heart'))
    p.append(bubble(1, 'Mom?', 66, 32, 16) + bubble(2, 'Mom?', 76, 36, 19) + bubble(3, 'MOM!', 92, 42, 24, BRAND)
             + bubble(4, 'Hi.', 56, 34, 18))
    p.append('</svg>')
    return ''.join(p)


def scene_block(ohio=False):
    return f'<div class="scenebox">{scene_svg(ohio)}</div>'


# ---------------------------------------------------------------- the joke of the day
def read_jokes():
    return json.loads(JOKES.read_text(encoding='utf-8'))


def approved_jokes(data=None):
    """{ISO date: joke} for the jokes the owner has approved. An unapproved joke is never written into a page."""
    data = read_jokes() if data is None else data
    return {j['date']: j['text'] for j in data['jokes'] if j.get('approved') is True}


def long_date(iso):
    y, m, d = (int(x) for x in iso.split('-'))
    return f'{MONTHS[m - 1]} {d}, {y}'


def check_jokes(data):
    """Problems with data/jokes.json, as a list of sentences."""
    errors, seen, last = [], set(), None
    for i, j in enumerate(data.get('jokes', []), 1):
        where = f'joke {i}'
        try:
            day = datetime.date.fromisoformat(j.get('date', ''))
        except ValueError:
            errors.append(f'{where}: bad date')
            continue
        if j['date'] in seen:
            errors.append(f'{where}: {j["date"]} is used twice')
        seen.add(j['date'])
        if last and day != last + datetime.timedelta(days=1):
            errors.append(f'{where}: {j["date"]} does not follow {last.isoformat()}; a batch runs one day after another')
        last = day
        text = j.get('text')
        if not isinstance(text, str) or not text.strip() or text != text.strip():
            errors.append(f'{where}: the joke is empty or has stray spaces')
        elif len(text) > JOKE_MAX:
            errors.append(f'{where}: {len(text)} characters; keep a joke under {JOKE_MAX}')
        elif '<' in text or '>' in text:
            errors.append(f'{where}: plain words only, no markup')
        if not isinstance(j.get('approved'), bool):
            errors.append(f'{where}: approved must be true or false')
    texts = [j.get('text') for j in data.get('jokes', [])]
    if len(set(texts)) != len(texts):
        errors.append('the same joke is listed twice')
    return errors


# Shows the joke for the visitor's own date; on jokes.html, shows the ones that have already run.
# If today has no joke of its own, the latest earlier one stays up; once the batch has run out the list starts over.
JOKE_SCRIPT = ('<script>(function(){var j=JSON.parse(document.getElementById("jokes-data").textContent),k=Object.keys(j).sort(),'
               'd=new Date(),t=d.getFullYear()+"-"+("0"+(d.getMonth()+1)).slice(-2)+"-"+("0"+d.getDate()).slice(-2),p=null,i;'
               'function n(s){var a=s.split("-");return Math.round(Date.UTC(+a[0],a[1]-1,+a[2])/864e5)}'
               'if(k.length&&t>k[k.length-1]){p=k[(n(t)-n(k[k.length-1])-1)%k.length]}'
               'else{for(i=0;i<k.length;i++)if(k[i]<=t)p=k[i]}'
               'var b=document.getElementById("joke");if(b&&p){document.getElementById("joke-text").textContent=j[p];b.hidden=false}'
               'var r=document.querySelectorAll("#joke-list li"),s=0;for(i=0;i<r.length;i++)if(r[i].getAttribute("data-date")<=t){r[i].hidden=false;s++}'
               'var e=document.getElementById("joke-none");if(e&&!s)e.hidden=false})();</script>')


def jokes_data(jokes):
    """The approved jokes as a data block in the page. '<' is escaped so no joke can close the script tag."""
    return '<script type="application/json" id="jokes-data">' + json.dumps(jokes, ensure_ascii=False, sort_keys=True).replace('<', '\\u003c') + '</script>'


def joke_section(jokes, list_href):
    """The joke of the day for a front page: hidden until the script has a joke for today. Nothing at all with no approved jokes."""
    if not jokes:
        return ''
    return ('<section class="wrap smile" id="joke" hidden><div class="jokecard"><h2>Mom joke of the day</h2>'
            f'<p class="joketext" id="joke-text"></p><p class="quiet"><a href="{esc(list_href)}">Earlier jokes</a></p></div></section>')


def joke_scripts(jokes):
    return (jokes_data(jokes) + JOKE_SCRIPT) if jokes else ''


def joke_list(jokes):
    """The running list for jokes.html, newest first. A joke stays hidden until its day."""
    rows = ''.join(f'<li data-date="{d}" hidden><small>{long_date(d)}</small>{esc(jokes[d])}</li>' for d in sorted(jokes, reverse=True))
    return (f'<ul class="jokelist" id="joke-list">{rows}</ul>'
            '<p class="quiet" id="joke-none" hidden>No jokes have run yet. Come back tomorrow.</p>')


# ---------------------------------------------------------------- the rules that move the picture
CSS_START = '/* home-extras:start. Front-page picture and joke of the day. Copied from templates/home-extras.css by scripts/home_extras.py; edit the template. */'
CSS_END = '/* home-extras:end */'


def render_sheet(text):
    """The stylesheet with the current rules at its end, between the two marker comments."""
    block = CSS_START + '\n' + STYLE.read_text(encoding='utf-8').rstrip('\n') + '\n' + CSS_END + '\n'
    if CSS_START in text:
        if text.count(CSS_START) != 1 or text.count(CSS_END) != 1 or not text.endswith(CSS_END + '\n'):
            raise SystemExit('a stylesheet needs exactly one home-extras block, at its end')
        text = text[:text.index(CSS_START)]
    return text + block


# ---------------------------------------------------------------- the OhioMom front page
MARK = re.compile(r'<!--home-extras:(?P<name>[a-z]+)-->(?P<body>.*?)<!--/home-extras-->', re.S)


def ohio_blocks(jokes):
    return {'scene': scene_block(ohio=True), 'joke': joke_section(jokes, '../jokes.html'), 'jokescript': joke_scripts(jokes)}


def render_ohio(text, jokes):
    blocks = ohio_blocks(jokes)
    found = [m.group('name') for m in MARK.finditer(text)]
    if sorted(found) != sorted(blocks):
        raise SystemExit(f'ohio/index.html: expected one marker each for {sorted(blocks)}, found {found}')
    return MARK.sub(lambda m: f'<!--home-extras:{m.group("name")}-->{blocks[m.group("name")]}<!--/home-extras-->', text)


def approve(start=None):
    data = read_jokes()
    day = datetime.date.fromisoformat(start) if start else None
    for j in data['jokes']:
        j['approved'] = True
        if day:
            j['date'] = day.isoformat()
            day += datetime.timedelta(days=1)
    JOKES.write_text(json.dumps(data, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'Approved {len(data["jokes"])} jokes, {data["jokes"][0]["date"]} to {data["jokes"][-1]["date"]}. '
          'Now run scripts/ymt_build.py and scripts/home_extras.py.')


def main():
    if '--approve' in sys.argv:
        approve(sys.argv[sys.argv.index('--start') + 1] if '--start' in sys.argv else None)
        return
    data = read_jokes()
    errors = check_jokes(data)
    if errors:
        raise SystemExit('data/jokes.json:\n' + '\n'.join(errors))
    jokes = approved_jokes(data)
    targets = {OHIO_HOME: lambda text: render_ohio(text, jokes)}
    targets.update({ROOT / rel: render_sheet for rel in SHEETS})
    stale = []
    for path, render in targets.items():
        text = path.read_text(encoding='utf-8')
        new = render(text)
        if new != text:
            stale.append(str(path.relative_to(ROOT)))
            if '--check' not in sys.argv:
                path.write_text(new, encoding='utf-8')
    if '--check' in sys.argv:
        if stale:
            raise SystemExit('Out of step with the picture, its rules or the jokes (run python3 scripts/home_extras.py):\n' + '\n'.join(stale))
        print(f'OK: {len(data["jokes"])} jokes, {len(jokes)} approved; the OhioMom front page and both stylesheets match')
    else:
        print(f'{len(jokes)} approved jokes. ' + ('Wrote ' + ', '.join(stale) if stale else 'Nothing to write'))


if __name__ == '__main__':
    main()
