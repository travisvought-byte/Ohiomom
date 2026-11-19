"""Ad slots: ready on the pages, and invisible until an ad is filled in.

The ads live in data/ads.json, a list under "ads". With the list empty (as it ships) no page carries any ad
markup at all. Each ad names the one slot it fills:

    {"slot": "state-oh", "sponsor": "Name", "text": "One or two plain sentences.",
     "url": "https://example.org/", "image": "assets/ads/name.png", "alt": "What the picture shows",
     "start": "2026-12-01", "end": "2026-12-31"}

image, alt, start and end are optional. An image is a file kept on this site under assets/ads/, never an address
on another site, so a page loads nothing from anyone else. Dates are first and last days, inclusive, by the
calendar in Ohio: an ad is written into the pages only on the days between them, so an ad with dates needs a
rebuild and a publish on its first day and the day after its last (until then `ymt_build.py --check` says the
pages are out of date).

Where a slot sits, and the rules it keeps (see build/place below):
- At most one ad on a page, and only on the home pages and the state, county and topic pages.
- After the page's own content, as the last thing in <main>: never inside a list of listings or a need.
- Never on a crisis or help-now page (ohio/help/housing.html, ohio/wellbeing.html and the family guide carry none).
- Labeled "Advertisement", with rel="sponsored noopener" on its link, and styled apart from a listing card.

Slot names. A page takes the first slot in its list that an ad names, so a named state or county can have its own
ad and the rest share one:
    home                      the Yoga Mom Talk front page
    topic-help, topic         help.html
    topic-connect, topic      connect.html
    state-oh, state           states/oh.html (any state's two letters)
    country-gb, country       countries/united-kingdom.html (any country's two letters; world.html takes topic-help, topic)
    county                    county.html (one page for every U.S. county)
    ohio-home                 ohio/index.html
    ohio-county-morrow, ohio-county      ohio/counties/morrow.html (any Ohio county page)
    ohio-topic-bills, ohio-topic         ohio/help/bills.html, pregnancy-baby.html, single-parent.html
    ohio-topic-connect, ohio-topic       ohio/connect.html
"""
import datetime
import json
import re
from html import escape as esc
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
ADS = ROOT / 'data' / 'ads.json'
FIELDS = {'slot', 'sponsor', 'text', 'url', 'image', 'alt', 'start', 'end', 'note'}
SLOT = re.compile(r'^(home|topic|topic-help|topic-connect|state|state-[a-z]{2}|country|country-[a-z]{2}|county|ohio-home|ohio-county|ohio-county-[a-z-]+'
                  r'|ohio-topic|ohio-topic-(bills|pregnancy-baby|single-parent|connect))$')
# OhioMom pages that may carry an ad, with the slots each takes in order. Pages not named here never do.
OHIO_TOPICS = ('help/bills', 'help/pregnancy-baby', 'help/single-parent', 'connect')
# Pages that must never carry one: crisis and help-now pages.
NEVER = ('ohio/help/housing.html', 'ohio/wellbeing.html', 'family-guide.html', 'report.html', 'ohio/report.html')
ASIDE = re.compile(r'\n?<aside class="ad-slot"[^>]*>.*?</aside>', re.S)


def today():
    return datetime.datetime.now(ZoneInfo('America/New_York')).date().isoformat()


def load(path=ADS):
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding='utf-8')).get('ads', [])


def check(ads):
    """Problems with the ad list, as plain sentences. An empty list is fine."""
    errors, seen = [], set()
    if not isinstance(ads, list):
        return ['data/ads.json: "ads" must be a list']
    for n, ad in enumerate(ads, 1):
        who = f'ad {n} ({ad.get("sponsor", "?")})' if isinstance(ad, dict) else f'ad {n}'
        if not isinstance(ad, dict):
            errors.append(f'{who}: must be an object')
            continue
        for key in sorted(set(ad) - FIELDS):
            errors.append(f'{who}: unknown field {key}')
        for key in ('slot', 'sponsor', 'text', 'url'):
            if not isinstance(ad.get(key), str) or not ad.get(key).strip():
                errors.append(f'{who}: missing {key}')
        slot = ad.get('slot', '')
        if slot and not SLOT.match(slot):
            errors.append(f'{who}: unknown slot {slot}')
        if slot.startswith('ohio-county-') and not (ROOT / 'ohio' / 'counties' / f'{slot[12:]}.html').is_file():
            errors.append(f'{who}: no Ohio county page for {slot}')
        if slot in seen:
            errors.append(f'{who}: slot {slot} already has an ad; a page shows at most one')
        seen.add(slot)
        if ad.get('url') and not str(ad['url']).startswith('https://'):
            errors.append(f'{who}: url must start with https://')
        for key in ('sponsor', 'text', 'alt'):
            if re.search(r'[<>]', str(ad.get(key, ''))):
                errors.append(f'{who}: {key} must be plain words, no markup')
        if len(str(ad.get('text', ''))) > 220:
            errors.append(f'{who}: text is longer than 220 characters')
        if ad.get('image'):
            img = str(ad['image'])
            if not img.startswith('assets/ads/') or '..' in img or not (ROOT / img).is_file():
                errors.append(f'{who}: image must be a file on this site under assets/ads/ ({img})')
            if not str(ad.get('alt', '')).strip():
                errors.append(f'{who}: an image needs alt words')
        dates = {}
        for key in ('start', 'end'):
            if ad.get(key):
                try:
                    dates[key] = datetime.date.fromisoformat(ad[key])
                except (TypeError, ValueError):
                    errors.append(f'{who}: {key} must be a date like 2026-12-01')
        if len(dates) == 2 and dates['end'] < dates['start']:
            errors.append(f'{who}: end is before start')
    return errors


def active(ads, on):
    """The ads running on the day `on` (an ISO date)."""
    return [a for a in ads if (not a.get('start') or a['start'] <= on) and (not a.get('end') or on <= a['end'])]


def pick(ads, slots):
    """The ad for a page that takes `slots`, the most specific first. None when no ad names any of them."""
    by_slot = {a['slot']: a for a in ads}
    for s in slots:
        if s in by_slot:
            return by_slot[s]
    return None


def aside(ad, root=''):
    """The ad itself. It is not a listing card: it has its own label, its own look, and rel="sponsored"."""
    if not ad:
        return ''
    pic = ''
    if ad.get('image'):
        pic = f'<img src="{esc(root + ad["image"])}" alt="{esc(ad.get("alt", ""))}" loading="lazy">'
    sponsor = esc(ad['sponsor'])
    return (f'<aside class="ad-slot" aria-label="Advertisement"><p class="ad-label">Advertisement</p>'
            f'<div class="ad-body">{pic}<div><p class="ad-sponsor">{sponsor}</p><p>{esc(ad["text"])}</p>'
            f'<p><a href="{esc(ad["url"])}" rel="sponsored noopener">Visit {sponsor}</a></p></div></div></aside>')


def ohio_pages():
    """{OhioMom page path: its slots}, for the OhioMom pages that may carry an ad."""
    pages = {'ohio/index.html': ['ohio-home']}
    for p in sorted((ROOT / 'ohio' / 'counties').glob('*.html')):
        pages[f'ohio/counties/{p.name}'] = [f'ohio-county-{p.stem}', 'ohio-county']
    for t in OHIO_TOPICS:
        pages[f'ohio/{t}.html'] = [f'ohio-topic-{t.split("/")[-1]}', 'ohio-topic']
    return pages


def place(text, ad, root=''):
    """The page with any old ad taken out and this one (if any) put last in <main>."""
    text = ASIDE.sub('', text)
    if text.count('</main>') != 1:
        raise SystemExit('a page with an ad slot needs exactly one </main>')
    if not ad:
        return text
    return text.replace('</main>', aside(ad, root) + '\n</main>')
