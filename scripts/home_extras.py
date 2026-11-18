#!/usr/bin/env python3
"""The picture and the joke of the day on the two front pages.

Both front pages carry the same two extras, drawn here so they cannot drift apart:

- **The picture.** It is the family whose site this is (the owner's call, November 17, 2026). Deborah is on her
  mat, tall and blond, in pink leggings, trying to get through the joke of the day. Her children are around,
  each doing his or her own thing; nobody is there to answer the joke. Who they are is shown by what they do
  and never said. It changes every day: she works on a different pose (POSES) in a different sweater (SWEATERS),
  and different children are around (KIDS, CASTS). The site does not name the children, and nothing else about
  them is written here: no ages, schools or places, and nothing about their health. It is inline SVG, moved by CSS. The rules are in templates/home-extras.css, and this script copies them to
  the end of assets/ymt.css and ohio/assets/site.css, between marker comments, so the two sites cannot drift
  apart: edit the template, never the copies. The picture is decoration, so it is hidden from screen readers,
  and it holds still for visitors whose device asks for reduced motion. The OhioMom picture is the same room
  with a cardinal at the window and Ohio on the wall.
- **The joke of the day.** It is in the picture: Deborah's speech bubble, at the top of the page, so it is the
  first thing a visitor meets (the owner's call, November 17, 2026: it should disarm people as they arrive).
  data/jokes.json holds one joke for each date. Only jokes marked `approved` are ever written into a page; the
  owner approves each batch before it runs. The page carries the approved jokes and a few lines of script that
  show the one for the visitor's own date, so the joke changes at midnight on her clock and nothing is sent
  anywhere. The bubble is HTML, not part of the drawing, so the words wrap, can be read aloud by a screen
  reader, and can be selected. When a batch runs out the list starts over, one a day, until new jokes are
  approved. jokes.html is the running list of the ones that have already run.
- **The caption.** Under the drawing, one line says what Deborah is working on today. It is HTML too, for the
  same reasons.

How a day gets its picture: every pose's arms and legs, every sweater pattern and all four children are in the
drawing, and all but one set are switched off. The same script that shows the day's joke switches on the day's
set, by setting attributes on the drawing. What it needs (the poses, the sweaters, and each day's choice) is in
the page beside the jokes, not in the stylesheet, so a stylesheet a browser kept from last month cannot dress
her wrong. With scripts off the page shows the first pose, the first sweater and the first child.

The national front page (index.html) and jokes.html are built by scripts/ymt_build.py, which calls the
functions here. The OhioMom front page (ohio/index.html) is static source, so this script writes the same
blocks into it between marker comments, the way scripts/prerender_ohio.py does for the events.

    python3 scripts/home_extras.py                    write the blocks into ohio/index.html and the rules into both stylesheets
    python3 scripts/home_extras.py --check            check data/jokes.json, and fail if a page or stylesheet is out of step
    python3 scripts/home_extras.py --approve          mark the waiting jokes approved (after the owner has approved the batch)
    python3 scripts/home_extras.py --approve --start 2026-12-18
                                                      the same, and run them from that day; approved jokes that had
                                                      that day or a later one follow after them
"""
import datetime
import json
import math
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
JOKE_HEADING = 'Deborah’s joke of the day'  # the heading of the speech bubble: the jokes are hers

INK, SKIN, BLUSH = '#2b2140', '#f3c7a6', '#ee8fa0'
BRAND, TEAL, SUN = '#cf2f5b', '#12766f', '#ffcb52'
LEGGINGS = '#e2557f'  # Deborah likes pink
# Hair: Deborah, then Ephraim, Genevieve, Atlas and Delilah.
BLONDE, BROWN, DARK_BLONDE, LIGHT_BLONDE, GOLD_BROWN = '#f2cb5c', '#6b4428', '#b89a5e', '#f7dc7c', '#d9a65a'
NIGHT, VIOLET = '#1d1826', '#9b6fe0'  # Genevieve's black, and the stripes on her sleeves and tights
HEART = 'M0-1.5C-1.5-4.5-6-3.5-5 .5C-4.2 3 0 6 0 6S4.2 3 5 .5C6-3.5 1.5-4.5 0-1.5Z'
# Ohio's outline, 27.7 wide by 30 tall, from the state's corner and river coordinates.
OHIO = ('M.1 2.4L8.8 2.1L10.8 3L12 3.9L13.5 4.4L15.9 4.6L18.5 4L20.1 4L22.7 2.2L24.9 1.1L27.7 0L27.7 11.3L26.8 13.1'
        'L27.1 14.1L26.3 16.1L25.4 19.6L24 21.1L21.7 21.7L20.7 23L19.7 25.5L18 24.9L16.9 26.8L15.3 30L14.4 30L13.8 29'
        'L11.7 27.4L9.8 28.5L7.8 27.7L5.9 27.1L3.5 25.5L2 24.3L0 24.2Z')

# ---------------------------------------------------------------- who is in the picture
# The picture is the family whose site this is (the owner's call, November 17, 2026): Deborah on her mat and
# her four children. The children are simply around, each doing his or her own thing while she tries to get
# through her joke: nobody is there to answer it. Who they are is shown by what they do, never said (the owner's
# call the same day). Each child stands in the same place every time, so nothing ever overlaps.
# The site does not name them: the names below only say who is in a day's picture. Nothing else about the
# children is written anywhere in this repository: no ages, schools or places, and nothing about their health.
KIDS = ('delilah', 'ephraim', 'genevieve', 'atlas')
KID_NAMES = {'delilah': 'Delilah', 'ephraim': 'Ephraim', 'genevieve': 'Genevieve', 'atlas': 'Atlas'}
KID_X = {'genevieve': 106, 'ephraim': 150, 'delilah': 380, 'atlas': 452}  # where each one stands
# Who is around on a day whose joke does not say: these take turns, so the room is never the same two days running.
CASTS = (('delilah',), ('ephraim', 'atlas'), ('genevieve',), ('atlas', 'delilah'), ('ephraim',), ('genevieve', 'delilah'),
         ('atlas',), ('ephraim', 'genevieve'), ('delilah', 'ephraim', 'genevieve', 'atlas'), ('genevieve', 'atlas'),
         ('ephraim', 'delilah'))

# ---------------------------------------------------------------- her sweaters
# Deborah wears a different sweater every day. name: (wool, pattern color, collar and hem, pattern).
SWEATERS = {
    'heart': ('#ffd9e4', '#cf2f5b', '#f7b3c8', 'heart'),
    'candy': ('#f47aa5', '#ffffff', '#d95486', 'stripes'),
    'lilac': ('#b9a6ef', '#ffffff', '#9a84de', 'dots'),
    'teal': ('#2a9d8f', '#fff1e6', '#1f7f73', 'zigzag'),
    'sunny': ('#ffcb52', '#ffffff', '#e9ac2b', 'star'),
    'rainbow': ('#9fd0f2', '#ffffff', '#78b6e0', 'rainbow'),
    'bubblegum': ('#ff9ebd', '#ffffff', '#f47aa5', 'plain'),
    'plum': ('#3b2e5a', '#f47aa5', '#2b2140', 'band'),
    'mint': ('#bfe8d9', '#ffffff', '#93d1bd', 'stripes'),
    'berry': ('#cf2f5b', '#fff1e6', '#a9244a', 'dots'),
}
FIRST_SWEATER = 'heart'  # the one drawn in the page, before the script has picked the day's

# ---------------------------------------------------------------- her poses
# Deborah works on a different pose every day. She is drawn once from the hips up (her "top half"), and each
# pose moves that into place and draws its own arms and legs. All of them face the visitor, so one face works
# for every pose. Points are in the picture's own units; her left is the visitor's right.
HIP = (262, 113)                          # the middle of her hips when she stands straight
SHOULDERS = ((251.5, 80), (272.5, 80))    # where her sleeves start, on the visitor's left and right
HIPS = ((256.5, 112), (267.5, 112))       # where her legs start
HEAD = (262, 54)
# name: what the caption calls it; top: how her top half moves (right, down, degrees clockwise about her hips);
# foot: the point she wobbles about; legs and arms: knee then ankle, elbow then hand, visitor's left first;
# feet: one short line each; front: what is drawn in front of her top half (L legs, a left arm, b right arm).
POSES = {
    'tree': dict(name='tree pose', top=(0, 0, 0), foot=(256.5, 168),
                 legs=(((256.5, 140), (256.5, 163)), ((293, 126), (264, 141))),
                 feet=(((252, 167.5), (262, 167.5)), ((264.5, 141.5), (261, 146.5))),
                 arms=(((244, 58), (262, 36)), ((280, 58), (262, 36))), front=''),
    'mountain': dict(name='mountain pose', top=(0, 0, 0), foot=(262, 168),
                     legs=(((256, 140), (255.5, 163)), ((268, 140), (268.5, 163))),
                     feet=(((251, 167.5), (259, 167.5)), ((265, 167.5), (273, 167.5))),
                     arms=(((247, 57), (246, 35)), ((277, 57), (278, 35))), front=''),
    'warrior2': dict(name='warrior two', top=(5, 12, 0), foot=(263, 168),
                     legs=(((244, 144), (227, 163)), ((298, 133), (300, 163))),
                     feet=(((229, 167.5), (219, 167.5)), ((297, 167.5), (308, 167.5))),
                     arms=(((234, 92), (213, 92)), ((300, 92), (321, 92))), front=''),
    'goddess': dict(name='goddess pose', top=(0, 15, 0), foot=(262, 168),
                    legs=(((234, 136), (232, 163)), ((290, 136), (292, 163))),
                    feet=(((236, 167.5), (225, 167.5)), ((288, 167.5), (299, 167.5))),
                    arms=(((231, 95), (231, 74)), ((293, 95), (293, 74))), front=''),
    'star': dict(name='star pose', top=(0, 3, 0), foot=(262, 168),
                 legs=(((244, 139), (232, 163)), ((280, 139), (292, 163))),
                 feet=(((235, 167.5), (225, 167.5)), ((289, 167.5), (299, 167.5))),
                 arms=(((230, 77), (209, 71)), ((294, 77), (315, 71))), front=''),
    'triangle': dict(name='triangle pose', top=(8, 4, -58), foot=(270, 168),
                     legs=(((250, 140), (236, 163)), ((290, 140), (304, 163))),
                     feet=(((239, 167.5), (228, 167.5)), ((301, 167.5), (311, 167.5))),
                     arms=(((236, 130), (239, 150)), ((247.6, 68), (247.6, 46))), front='a'),
    'crescent': dict(name='crescent moon', top=(-6, 0, 18), foot=(256, 168),
                     legs=(((250, 140), (249.5, 163)), ((262, 140), (262.5, 163))),
                     feet=(((245, 167.5), (253, 167.5)), ((259, 167.5), (267, 167.5))),
                     arms=(((262, 54), (291, 37)), ((291, 64), (293, 38))), front=''),
    'easy': dict(name='easy pose', top=(0, 44, 0), foot=(262, 168),
                 legs=(((234, 160), (270, 166)), ((290, 160), (254, 166))),
                 feet=(((270, 166), (273, 166)), ((254, 166), (251, 166))),
                 arms=(((243, 141), (236, 155)), ((281, 141), (288, 155))), front='Lab'),
    'bigtoe': dict(name='big-toe pose', top=(0, 0, 0), foot=(268, 168),
                   legs=(((233, 101), (212, 90)), ((268, 140), (268, 163))),
                   feet=(((211, 89.5), (209, 82.5)), ((263.5, 167.5), (273.5, 167.5))),
                   arms=(((231, 80), (213, 84)), ((286, 97), (275, 109))), front='b'),
}
FIRST_POSE = 'tree'  # the one drawn in the page, before the script has picked the day's


def num(v):
    """A number, written as short as it goes."""
    s = f'{v:.1f}'
    s = s[:-2] if s.endswith('.0') else s
    return '0' if s == '-0' else s


def line(*points):
    return 'M' + 'L'.join(f'{num(x)} {num(y)}' for x, y in points)


def placed(point, top):
    """Where a point of her top half is once the pose has moved it."""
    right, down, degrees = top
    x, y, a = point[0] - HIP[0], point[1] - HIP[1], math.radians(degrees)
    return (HIP[0] + right + x * math.cos(a) - y * math.sin(a), HIP[1] + down + x * math.sin(a) + y * math.cos(a))


def top_move(pose):
    """The pose's move of her top half, as an SVG transform. Empty when she stands straight."""
    right, down, degrees = POSES[pose]['top']
    move = f'translate({num(right)} {num(down)})' if right or down else ''
    turn = f'rotate({num(degrees)} {num(HIP[0])} {num(HIP[1])})' if degrees else ''
    return move + turn


def bubble_tail(pose):
    """How far across the picture her head is, so the tail of the joke bubble can point at her."""
    return f'{round(placed(HEAD, POSES[pose]["top"])[0] / 5.2)}%'


def short_of(a, b, by):
    """The point `by` units before b on the way from a."""
    length = math.hypot(b[0] - a[0], b[1] - a[1])
    return (b[0] - (b[0] - a[0]) * by / length, b[1] - (b[1] - a[1]) * by / length)


def limbs(pose, front):
    """Her arms and legs for one pose: the ones that go in front of her top half, or the ones behind it."""
    spec, wool = POSES[pose], SWEATERS[FIRST_SWEATER][0]
    right, down, _ = spec['top']
    out = []
    if ('L' in spec['front']) == front:
        legs = ''.join(line((HIPS[i][0] + right, HIPS[i][1] + down), *spec['legs'][i]) for i in (0, 1))
        out.append(f'<path d="{legs}" stroke="{LEGGINGS}" stroke-width="10"/>'
                   f'<path d="{"".join(line(*f) for f in spec["feet"])}" stroke="{SKIN}" stroke-width="5.5"/>')
    arms = [i for i, letter in enumerate('ab') if (letter in spec['front']) == front]
    if arms:
        sleeves, hands = '', ''
        for i in arms:
            elbow, hand = spec['arms'][i]
            sleeves += line(placed(SHOULDERS[i], spec['top']), elbow, short_of(elbow, hand, 3.5))
            hands += f'M{num(hand[0])} {num(hand[1])}h.01'
        out.append(f'<path d="{sleeves}" stroke="{wool}" data-stroke="0" stroke-width="7.4"/>'
                   f'<path d="{hands}" stroke="{SKIN}" stroke-width="7.6"/>')
    if not out:
        return ''
    hidden = '' if pose == FIRST_POSE else ' display="none"'
    return f'<g data-pose="{pose}"{hidden}>{"".join(out)}</g>'


# ---------------------------------------------------------------- the picture
def heart(x, y, size, fill, cls=''):
    """A small heart, about 10 units wide at size 1, with its middle near (x, y)."""
    c = f' class="{cls}"' if cls else ''
    return f'<g transform="translate({x} {y}) scale({size})"><path{c} d="{HEART}" fill="{fill}"/></g>'


def bubble(n, x, y, width, height, tail, inside):
    """One thing a child says: a white bubble with a tail that points down at `tail`. Each has its moment in the loop.
    It grows out of its tail, so the tail's place along the bubble is also where it grows from."""
    r, bottom = 12, y + height
    grow = round(100 * (tail - x) / width)
    return (f'<g class="sc-b sc-b{n}" style="transform-origin:{grow}% 100%"><path d="M{num(x + r)} {num(y)}h{num(width - 2 * r)}'
            f'a{r} {r} 0 0 1 {r} {r}v{num(height - 2 * r)}a{r} {r} 0 0 1-{r} {r}H{num(tail + 7)}L{num(tail)} {num(bottom + 9)}'
            f'L{num(tail - 5)} {num(bottom)}H{num(x + r)}a{r} {r} 0 0 1-{r}-{r}v-{num(height - 2 * r)}a{r} {r} 0 0 1 {r}-{r}z" fill="#fff"/>'
            f'{inside}</g>')


def says(n, x, y, width, height, tail, text, size=16, fill=INK):
    words = (f'<text x="{num(x + width / 2)}" y="{num(y + height / 2 + size * .36)}" style="font-size:{size}px" '
             f'fill="{fill}">{esc(text)}</text>')
    return bubble(n, x, y, width, height, tail, words)


def kid(name, drawn, cast):
    """One child, drawn about x = 0 and moved to where he or she stands. Switched off unless in the day's cast."""
    hidden = '' if name in cast else ' display="none"'
    return f'<g data-kid="{name}" transform="translate({KID_X[name]} 0)"{hidden}>{drawn}</g>'


def face(y, gap, mouth, r=1.6):
    """Two eyes and a mouth."""
    return (f'<circle cx="{num(-gap)}" cy="{num(y)}" r="{r}" fill="{INK}"/><circle cx="{num(gap)}" cy="{num(y)}" r="{r}" fill="{INK}"/>'
            f'<path d="{mouth}" fill="none" stroke="{INK}" stroke-width="1.5" stroke-linecap="round"/>')


def cheeks(y, gap, r=2.4):
    return (f'<circle cx="{num(-gap)}" cy="{num(y)}" r="{r}" fill="{BLUSH}" opacity=".7"/>'
            f'<circle cx="{num(gap)}" cy="{num(y)}" r="{r}" fill="{BLUSH}" opacity=".7"/>')


def delilah(cast):
    """Delilah, the smallest: hands on her hips, one eyebrow up. She is the one who wants the joke again,
    as the child in the first picture did, until her mother opens one eye."""
    boots, top = '#e0453a', '#8a63d2'
    body = (f'<g class="sc-kid"><path d="M-7 163v10M7 163v10" stroke="{boots}" stroke-width="8.5" stroke-linecap="round"/>'
            f'<ellipse cx="-8.5" cy="176.2" rx="6.3" ry="3.2" fill="{boots}"/><ellipse cx="8.5" cy="176.2" rx="6.3" ry="3.2" fill="{boots}"/>'
            '<ellipse cx="0" cy="160" rx="19.5" ry="6.5" fill="#f9c5d5"/><ellipse cx="0" cy="157.5" rx="16.5" ry="5" fill="#f497b6"/>'
            f'<path d="M-12 142L-23.5 149.5L-13.5 156M12 142L23.5 149.5L13.5 156" fill="none" stroke="{SKIN}" stroke-width="5.4" '
            'stroke-linecap="round" stroke-linejoin="round"/>'
            f'<rect x="-13.5" y="135" width="27" height="24" rx="10.5" fill="{top}"/>'
            f'<circle cx="-12.5" cy="141" r="4.6" fill="{top}"/><circle cx="12.5" cy="141" r="4.6" fill="{top}"/>'
            + heart(0, 147, .75, '#fff')
            + f'<path d="M0 113q-5.5-7.5-9.5-6M0 113q.2-8.5 1-10M0 113q5.5-7.5 9.5-6" fill="none" stroke="{GOLD_BROWN}" '
            'stroke-width="2.8" stroke-linecap="round"/>'
            f'<ellipse cx="0" cy="123.5" rx="12.8" ry="11.8" fill="{SKIN}"/>'
            f'<path d="M-12.8 123.5a12.8 11.8 0 0 1 25.6 0c-3-5-8-7-12.8-7s-9.8 2-12.8 7z" fill="{GOLD_BROWN}"/>'
            f'<circle cx="0" cy="112.8" r="2.8" fill="{BRAND}"/>'
            + cheeks(129.3, 8.6, 2.8) + face(125.2, 5, 'M-3.6 130.6q4.2 2.4 7.6-1.1')
            + f'<path d="M-8.3 120.4l5 .5M3.2 119.9l5.2-2" fill="none" stroke="{INK}" stroke-width="1.3" stroke-linecap="round"/></g>')
    said = (says(1, -12, 64, 74, 30, 3, 'Ha ha!') + says(2, -12, 60, 86, 34, 3, 'Again!', 19)
            + says(3, -12, 58, 104, 38, 3, 'AGAIN!', 22, BRAND) + says(4, -12, 62, 92, 32, 3, 'Please?', 18)
            + heart(-46, 128, 1.5, BRAND, 'sc-heart'))
    return kid('delilah', body + said, cast)


def atlas(cast):
    """Atlas: blond hair down over his ears, a big smile. He hides behind the plant, which does not cover
    him, and leans out now and then to wave."""
    shirt, shorts = '#f2743a', '#3b4a7a'
    body = ('<g class="sc-peek">'
            f'<path d="M-5 158V174M5 158V174" stroke="{SKIN}" stroke-width="5.2" stroke-linecap="round"/>'
            f'<ellipse cx="-6" cy="177" rx="5.4" ry="2.9" fill="{TEAL}"/><ellipse cx="6" cy="177" rx="5.4" ry="2.9" fill="{TEAL}"/>'
            f'<path d="M-5 150V159M5 150V159" stroke="{shorts}" stroke-width="7.6" stroke-linecap="round"/>'
            f'<path class="sc-hi" d="M-9 127L-19 114" stroke="{SKIN}" stroke-width="4.8" stroke-linecap="round"/>'
            f'<path d="M9 127L16 140" stroke="{SKIN}" stroke-width="4.8" stroke-linecap="round"/>'
            f'<rect x="-10.5" y="121" width="21" height="31" rx="7.5" fill="{shirt}"/><rect x="-10.5" y="133" width="21" height="4.5" fill="#ffd9a0"/>'
            f'<circle cx="0" cy="109.5" r="11.5" fill="{SKIN}"/>'
            f'<path d="M-12.5 110a12.5 12.5 0 0 1 25 0v7.5q-1.8 2.2-3.8.3l-.4-6.6q-3.2-6.2-8.3-6.2t-8.3 6.2l-.4 6.6q-2 1.9-3.8-.3z" fill="{LIGHT_BLONDE}"/>'
            + cheeks(115, 7.8)
            + f'<circle cx="-4.6" cy="110.8" r="1.6" fill="{INK}"/><circle cx="4.6" cy="110.8" r="1.6" fill="{INK}"/>'
            f'<path d="M-5.2 114.6q5.2 6.8 10.4 0z" fill="{INK}"/></g>')
    return kid('atlas', body + heart(-26, 104, 1.2, BRAND, 'sc-heart'), cast)


def genevieve(cast):
    """Genevieve, dressed like the heroine of a gothic anime: black dress, striped sleeves and tights, big
    boots, cat ears, hair over one eye. She stands with her arms crossed and does not laugh. Once, near the
    end, she almost does."""
    stripes = f'stroke="{VIOLET}" stroke-width="5" stroke-dasharray="2.6 3.4"'
    body = (f'<path d="M-5 144V168M5 144V168" stroke="{INK}" stroke-width="5"/><path d="M-5 146V168M5 146V168" {stripes}/>'
            f'<path d="M-5 167v6M5 167v6" stroke="{NIGHT}" stroke-width="8" stroke-linecap="round"/>'
            f'<rect x="-11.5" y="172.5" width="11" height="6" rx="2.2" fill="{NIGHT}"/><rect x=".5" y="172.5" width="11" height="6" rx="2.2" fill="{NIGHT}"/>'
            f'<path d="M-12.5 94a12.5 12.5 0 0 1 25 0L14.5 110q-14.5 4-29 0z" fill="{DARK_BLONDE}"/>'
            f'<rect x="-2.8" y="101" width="5.6" height="7" fill="{SKIN}"/><path d="M-2.8 104.3h5.6" stroke="{NIGHT}" stroke-width="1.7"/>'
            f'<path d="M-8.5 107.5Q0 104 8.5 107.5L14.5 145Q0 150-14.5 145Z" fill="{NIGHT}"/>'
            '<path d="M-6.5 106.3q3.4 3.6 6.5 0q3.1 3.6 6.5 0q-6.5-2.8-13 0z" fill="#fff"/>'
            f'<path d="M-13.8 141.5Q0 146.3 13.8 141.5" fill="none" stroke="{VIOLET}" stroke-width="1.6" stroke-dasharray="1.5 2.3"/>'
            f'<g fill="none" stroke-linejoin="round"><path d="M-8 110L-12 121L6 119.5M8 110L12 121L-6 122.5" stroke="{INK}" stroke-width="5" stroke-linecap="round"/>'
            f'<path d="M-8 110L-12 121L3 119.8M8 110L12 121L-3 122.3" {stripes}/></g>'
            f'<circle cx="6.5" cy="119.5" r="2.5" fill="{SKIN}"/><circle cx="-6.5" cy="122.5" r="2.5" fill="{SKIN}"/>'
            f'<circle cx="0" cy="93.5" r="11.5" fill="{SKIN}"/>'
            f'<path d="M-11.4 96.5a11.8 11.8 0 0 1 23.2-3q-2.8-5.2-7.3-7.2q-3.5 8.5-15.9 10.2z" fill="{DARK_BLONDE}"/>'
            f'<path d="M-10 86l1.5-9.5 6.5 5.7zM10 86l-1.5-9.5-6.5 5.7z" fill="{NIGHT}"/>'
            f'<circle cx="5" cy="95.8" r="1.7" fill="{INK}"/><path d="M6.3 94.5l2.3-1.4" stroke="{INK}" stroke-width="1.1" stroke-linecap="round"/>'
            f'<g fill="none" stroke="{INK}" stroke-width="1.5" stroke-linecap="round"><path class="sc-flat" d="M-1.5 100.8h5.5"/>'
            '<path class="sc-grin" opacity="0" d="M-1.5 100.3q2.8 2.1 5.5 0"/></g>')
    return kid('genevieve', body, cast)


def ephraim(cast):
    """Ephraim, the tallest of the four: brown hair, a hoodie, and his nose in a book. He looks up once."""
    hoodie, shade, jeans, cover = '#8f9bb3', '#76839d', '#3f5f8a', '#1f7f73'
    body = (f'<path d="M-4.5 124L-5.5 173.5M4.5 124L5.5 173.5" stroke="{jeans}" stroke-width="6.2" stroke-linecap="round"/>'
            '<ellipse cx="-7" cy="177" rx="6.6" ry="3" fill="#fff"/><ellipse cx="7" cy="177" rx="6.6" ry="3" fill="#fff"/>'
            f'<rect x="-3" y="79" width="6" height="8" fill="{SKIN}"/>'
            f'<rect x="-10.5" y="83.5" width="21" height="44" rx="7.5" fill="{hoodie}"/>'
            f'<path d="M-8.5 88q8.5-7 17 0" fill="none" stroke="{shade}" stroke-width="3.4" stroke-linecap="round"/>'
            f'<rect x="-7.5" y="113" width="15" height="9" rx="3.5" fill="{shade}"/>'
            f'<path d="M-10 89L-15.5 102L-9.5 108.5M10 89L15.5 102L9.5 108.5" fill="none" stroke="{shade}" stroke-width="5.2" '
            'stroke-linecap="round" stroke-linejoin="round"/>'
            f'<path d="M-11 96.5L0 98.5L11 96.5V109L0 111L-11 109Z" fill="{cover}"/>'
            '<path d="M-9.8 95.5L-.6 97.3V109L-9.8 107.2ZM9.8 95.5L.6 97.3V109L9.8 107.2Z" fill="#fff"/>'
            f'<circle cx="-10.3" cy="108.3" r="2.5" fill="{SKIN}"/><circle cx="10.3" cy="108.3" r="2.5" fill="{SKIN}"/>'
            f'<g class="sc-look"><circle cx="0" cy="71.5" r="11" fill="{SKIN}"/>'
            f'<path d="M-12.3 72.3a12.3 12.3 0 0 1 24.6 0v4.1q-1.7 1.6-3.4.2q.2-4.8-1.6-7.4q-7.3 3.3-14.6 0q-1.8 2.6-1.6 7.4q-1.7 1.4-3.4-.2z" fill="{BROWN}"/>'
            + face(75.2, 4.3, 'M-2.6 79.3q2.8 1.5 5.2 0', 1.5) + '</g>')
    return kid('ephraim', body, cast)


def star(x, y, outer, inner):
    """A five-pointed star as a path."""
    points = []
    for i in range(10):
        r, a = (outer, inner)[i % 2], math.radians(36 * i - 90)
        points.append((x + r * math.cos(a), y + r * math.sin(a)))
    return line(*points) + 'Z'


KNIT = 'M249 82.5Q249.5 76 256.5 75H267.5Q274.5 76 275 82.5L277 112Q262 117 247 112Z'  # the body of her sweater


def top_half():
    """Deborah from the hips up, standing straight: today's sweater, her blond ponytail, her eyes closed."""
    wool, accent, trim, first = SWEATERS[FIRST_SWEATER]
    patterns = {
        'heart': f'<path transform="translate(262 94) scale(1.5)" d="{HEART}" fill="{accent}" data-fill="1"/>',
        'stripes': f'<path d="M240 86h44M240 95h44M240 104h44" stroke="{accent}" data-stroke="1" stroke-width="4"/>',
        'dots': (f'<path d="M254 85h.01M262 83h.01M270 85h.01M258 93h.01M266 93h.01M252 101h.01M262 102h.01M272 101h.01" '
                 f'stroke="{accent}" data-stroke="1" stroke-width="4.4" stroke-linecap="round"/>'),
        'zigzag': (f'<path d="M245 97l4.3-7 4.3 7 4.2-7 4.2 7 4.2-7 4.2 7 4.3-7 4.3 7" fill="none" stroke="{accent}" data-stroke="1" '
                   'stroke-width="2.6" stroke-linejoin="round"/>'),
        'band': f'<path d="M240 93.5h44" stroke="{accent}" data-stroke="1" stroke-width="11"/>',
        'rainbow': (f'<g fill="none" stroke-width="3"><path d="M251.5 101.5a10.5 10.5 0 0 1 21 0" stroke="{BRAND}"/>'
                    f'<path d="M254.5 101.5a7.5 7.5 0 0 1 15 0" stroke="{SUN}"/><path d="M257.5 101.5a4.5 4.5 0 0 1 9 0" stroke="#2a9d8f"/></g>'),
        'star': f'<path d="{star(262, 94, 8.5, 3.6)}" fill="{accent}" data-fill="1"/>',
    }
    worn = ''.join(f'<g data-pat="{name}"{"" if name == first else " display=\"none\""}>{drawn}</g>' for name, drawn in patterns.items())
    return (f'<g data-top><path class="sc-pony" d="M266 43C278 37.5 286.5 45.5 284.5 58C283.3 66 280 71.5 276.5 74.5C278 66 277 58 271 51.5Z" fill="{BLONDE}"/>'
            f'<rect x="258.5" y="63" width="7" height="14" fill="{SKIN}"/>'
            f'<path d="{KNIT}" fill="{wool}" data-fill="0"/><g clip-path="url(#sc-knit)">{worn}'
            f'<path d="M247 107.5Q262 112.5 277 107.5V118H247Z" fill="{trim}" data-fill="2"/></g>'
            f'<path d="M256.5 75.5Q262 80.5 267.5 75.5" fill="none" stroke="{trim}" data-stroke="2" stroke-width="3" stroke-linecap="round"/>'
            f'<circle cx="262" cy="54" r="12" fill="{SKIN}"/>'
            f'<path d="M249.7 54.5a12.3 12.3 0 0 1 24.6 0c-2-6.6-6.6-9-12.3-9s-10.3 2.4-12.3 9z" fill="{BLONDE}"/>'
            f'<circle cx="268" cy="43.3" r="3.3" fill="{BRAND}"/>'
            f'<g fill="none" stroke="{INK}" stroke-width="1.7" stroke-linecap="round"><path d="M254.8 55.5q2.6 2.4 5.2 0"/>'
            '<path class="sc-lid" d="M264 55.5q2.6 2.4 5.2 0"/><path d="M257.5 61q4.5 3.2 9 0"/></g>'
            f'<circle class="sc-eye" cx="266.6" cy="55.3" r="2" fill="{INK}"/>'
            f'<circle cx="253" cy="59.5" r="2.5" fill="{BLUSH}" opacity=".7"/><circle cx="271" cy="59.5" r="2.5" fill="{BLUSH}" opacity=".7"/></g>')


def deborah():
    """Deborah on her mat: tall, blond, in pink leggings, with every pose's arms and legs (one set shows)."""
    behind = ''.join(limbs(pose, False) for pose in POSES)
    before = ''.join(limbs(pose, True) for pose in POSES)
    wrap = '<g fill="none" stroke-linecap="round" stroke-linejoin="round">'
    return f'<g class="sc-mom" data-mom>{wrap}{behind}</g>{top_half()}{wrap}{before}</g></g>'


def scene_svg(ohio=False, cast=('delilah',)):
    """The front-page picture. `ohio` adds the cardinal at the window and Ohio on the wall. `cast` is who is
    drawn showing before the script has picked the day's children."""
    p = ['<svg class="scene" viewBox="0 10 520 196" aria-hidden="true" focusable="false">'
         '<defs><linearGradient id="sc-wall" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#e6f5f0"/>'
         '<stop offset="1" stop-color="#d2ebe5"/></linearGradient>'
         '<linearGradient id="sc-sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#b9e0fa"/>'
         '<stop offset="1" stop-color="#eef8ff"/></linearGradient>'
         '<clipPath id="sc-pane"><rect x="30" y="24" width="84" height="74" rx="5"/></clipPath>'
         f'<clipPath id="sc-knit"><path d="{KNIT}"/></clipPath></defs>',
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
    p.append('<rect x="303" y="18" width="50" height="50" rx="6" fill="#fff"/>'
             '<rect x="308" y="23" width="40" height="40" rx="3" fill="#fff1e6"/>')
    if ohio:
        p.append(f'<path transform="translate(314.5 28)" d="{OHIO}" fill="{BRAND}"/>' + heart(327.5, 42, .8, '#fff'))
    else:
        petal = 'M0-13C5.5-7 5.5 1 0 6C-5.5 1-5.5-7 0-13Z'
        p.append('<g transform="translate(328 47)">'
                 + ''.join(f'<path d="{petal}" transform="rotate({a} 0 6)" fill="{c}"/>'
                           for a, c in ((-64, '#f6b5c6'), (64, '#f6b5c6'), (-32, '#e9799a'), (32, '#e9799a'), (0, BRAND)))
                 + '</g>')
    # under the window: a stool with her coffee, going cold
    steam = ''.join(f'<circle class="sc-steam" cx="{x}" cy="118" r="{r}" style="animation-delay:{d}s"/>'
                    for x, r, d in ((46, 3.2, 0), (50, 2.6, -1.2), (47.5, 3, -2.4)))
    p.append('<path d="M36 172L40 147M62 172L58 147" stroke="#b97c4d" stroke-width="4" stroke-linecap="round"/>'
             '<rect x="30" y="141" width="38" height="7" rx="3.5" fill="#d39a67"/>'
             '<path d="M57 128q8 0 8 5.5t-8 5.5" fill="none" stroke="#fff" stroke-width="3.2"/>'
             '<rect x="39" y="123" width="19" height="18" rx="4" fill="#fff"/>' + heart(48.5, 131.5, .62, BRAND)
             + f'<g fill="#fff">{steam}</g>')
    # her mat
    p.append('<ellipse cx="266" cy="183" rx="104" ry="5" fill="#8a5a3a" opacity=".13"/>'
             '<rect x="174" y="170" width="184" height="11" rx="5.5" fill="#2a9d8f"/>'
             '<rect x="176" y="171.5" width="180" height="3" rx="1.5" fill="#5cc3b5"/>')
    # the family: the two big kids by the window, Deborah on her mat, the two little ones by the plant
    p.append(genevieve(cast) + ephraim(cast) + deborah() + delilah(cast) + atlas(cast))
    # the plant in the corner, in front of Atlas
    p.append('<g class="sc-leaf"><path d="M489 150C486 128 474 117 461 113C464 131 473 144 489 150Z" fill="#3f9b6e"/>'
             '<path d="M489 150C492 127 503 116 516 112C512 131 504 144 489 150Z" fill="#2f8a5f"/>'
             '<path d="M489 150C481 133 483 112 489 97C496 112 497 133 489 150Z" fill="#58b386"/></g>'
             '<path d="M474 152h30l-4 26h-22z" fill="#d9825b"/><rect x="471" y="147" width="36" height="8" rx="3.5" fill="#e79a72"/>')
    # on the floor in front: blocks and the bunny
    p.append('<rect x="414" y="186" width="14" height="14" rx="3" fill="#b9a6ef"/>'
             '<rect x="428.5" y="186" width="14" height="14" rx="3" fill="#f6b5c6"/>'
             f'<rect x="421" y="172" width="14" height="14" rx="3" fill="{SUN}"/>'
             '<g fill="#fff"><ellipse cx="399" cy="193" rx="7.5" ry="6.5"/><circle cx="399" cy="183" r="5.5"/>'
             '<ellipse cx="396" cy="174" rx="2.4" ry="6.5" transform="rotate(-10 396 174)"/>'
             '<ellipse cx="402" cy="174" rx="2.4" ry="6.5" transform="rotate(10 402 174)"/></g>'
             '<ellipse cx="396" cy="174.5" rx="1" ry="4" transform="rotate(-10 396 174)" fill="#f6b5c6"/>'
             '<ellipse cx="402" cy="174.5" rx="1" ry="4" transform="rotate(10 402 174)" fill="#f6b5c6"/>'
             f'<circle cx="397" cy="182.5" r=".9" fill="{INK}"/><circle cx="401" cy="182.5" r=".9" fill="{INK}"/>')
    p.append('</svg>')
    return ''.join(p)


CAPTION_STYLE = 'margin:0;padding:.4rem .9rem .5rem;background:#fff;color:#655c78;font-size:.82rem;line-height:1.35'


def caption_line(jokes):
    """Under the drawing: what Deborah is working on today. The script fills it in, so it
    starts hidden, and with no approved jokes there is no script and no line. Its look is written on the line
    itself, not in the stylesheet, so it looks right even beside a stylesheet a browser kept from before it existed."""
    return f'<p class="scenecap" id="scene-cap" style="{CAPTION_STYLE}" hidden></p>' if jokes else ''


def scene_block(ohio=False, jokes=None, list_href='jokes.html'):
    """The picture card for a front page: the joke of the day in a speech bubble, the drawing under it, and
    under that a line that says what Deborah is working on today."""
    jokes = jokes or {}
    return f'<div class="scenebox" id="scene">{joke_bubble(jokes, list_href)}{scene_svg(ohio)}{caption_line(jokes)}</div>'


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
        # The picture for the day: who is around, her pose, her sweater. All optional: what a joke leaves out takes its turn.
        cast = j.get('cast')
        if cast is not None and (not isinstance(cast, list) or len(set(cast)) != len(cast) or any(k not in KIDS for k in cast)):
            errors.append(f'{where}: cast is a list of {", ".join(KIDS)}, each once (an empty list is Deborah alone)')
        if j.get('pose') is not None and j['pose'] not in POSES:
            errors.append(f'{where}: pose is one of {", ".join(POSES)}')
        if j.get('sweater') is not None and j['sweater'] not in SWEATERS:
            errors.append(f'{where}: sweater is one of {", ".join(SWEATERS)}')
    texts = [j.get('text') for j in data.get('jokes', [])]
    if len(set(texts)) != len(texts):
        errors.append('the same joke is listed twice')
    return errors


# ---------------------------------------------------------------- the picture for each day
def take_turns(jokes, key, names):
    """Each joke's `key` (its pose or its sweater): its own if it names one, otherwise the next in turn.
    A turn is skipped if the two days before or the two days after already have it, so she is never in the
    same pose, or the same sweater, twice in three days unless the jokes themselves ask for it."""
    out, turn = [], 0
    for i, j in enumerate(jokes):
        mine = j.get(key)
        if not mine:
            near = out[-2:] + [later.get(key) for later in jokes[i + 1:i + 3]]
            while names[turn % len(names)] in near:
                turn += 1
            mine = names[turn % len(names)]
            turn += 1
        out.append(mine)
    return out


def caption(pose):
    """The line under the drawing: what Deborah is working on today. It says nothing about the children:
    they are in the picture, and that is enough."""
    return f'Today Deborah is working on {POSES[pose]["name"]}.'


def looks(data=None):
    """{ISO date: (pose, sweater, cast, caption)} for every joke on file: what the picture shows that day.
    A joke can name its pose, its sweater and its cast (which children are around). Whatever it leaves out
    takes its turn. A joke about "my youngest" names Delilah as its cast, so she is the one in the room; the
    joke itself never says so."""
    jokes = (read_jokes() if data is None else data)['jokes']
    poses, sweaters = take_turns(jokes, 'pose', list(POSES)), take_turns(jokes, 'sweater', list(SWEATERS))
    out, turn, before = {}, 0, None
    for i, j in enumerate(jokes):
        cast = j.get('cast')
        if cast is None:
            after = jokes[i + 1].get('cast') if i + 1 < len(jokes) else None
            near = (before, tuple(after) if after is not None else None)
            while CASTS[turn % len(CASTS)] in near:  # not the same children two days running
                turn += 1
            cast, turn = CASTS[turn % len(CASTS)], turn + 1
        before = tuple(cast)
        out[j['date']] = (poses[i], sweaters[i], before, caption(poses[i]))
    return out


def approved_looks(data=None):
    """The picture for each approved joke's day. Like the jokes, nothing about an unapproved day reaches a page."""
    data = read_jokes() if data is None else data
    approved, every = approved_jokes(data), looks(data)
    return {date: every[date] for date in approved}


def scene_data(day_looks):
    """What the page's script needs to dress the picture for a day: every pose (how her top half moves, the point
    she wobbles about, where the joke bubble's tail points), every sweater, and each day's pose, sweater, children
    and caption. It is all in the page, so a stylesheet a browser kept from last month cannot put it out of step."""
    return {
        'p': {name: [top_move(name), f'{num(spec["foot"][0])}px {num(spec["foot"][1])}px', bubble_tail(name)] for name, spec in POSES.items()},
        'w': {name: list(sweater) for name, sweater in SWEATERS.items()},
        'd': {date: '|'.join((pose, sweater, ' '.join(cast), words)) for date, (pose, sweater, cast, words) in day_looks.items()},
    }


# Dresses the picture for the day whose key is `p`: the pose, the sweater, which children are around, and the
# caption. It only sets attributes on the drawing, so it can run again for another day.
# It does nothing on a page with no picture, or for a day the page has no picture for.
DRESS = ('function(D,p){var S=D.getElementById("scene-data"),B=D.getElementById("scene");if(!S||!B||!p)return;'
         'S=JSON.parse(S.textContent);var v=(S.d[p]||"").split("|"),P=S.p[v[0]],W=S.w[v[1]];if(!P||!W)return;'
         'var c=" "+v[2]+" ",'
         'q=function(s,g){var a=B.querySelectorAll(s),i;for(i=0;i<a.length;i++)g(a[i],a[i].getAttribute(s.slice(1,-1)))},'
         'o=function(e,y){e.setAttribute("display",y?"inline":"none")};'
         'q("[data-pose]",function(e,a){o(e,a==v[0])});'
         'q("[data-top]",function(e){e.setAttribute("transform",P[0])});'
         'q("[data-mom]",function(e){e.style.transformOrigin=P[1]});'
         'q("[data-kid]",function(e,a){o(e,c.indexOf(" "+a+" ")>=0)});'
         'q("[data-pat]",function(e,a){o(e,a==W[3])});'
         'q("[data-fill]",function(e,a){e.setAttribute("fill",W[a])});'
         'q("[data-stroke]",function(e,a){e.setAttribute("stroke",W[a])});'
         'B.style.setProperty("--tail",P[2]);'
         'var C=D.getElementById("scene-cap");if(C&&v[3]){C.textContent=v[3];C.hidden=false}}')

# Shows the joke for the visitor's own date; on jokes.html, shows the ones that have already run.
# If today has no joke of its own, the latest earlier one stays up; once the batch has run out the list starts over.
# On a front page it then dresses the picture for that same day. Nothing is sent or stored.
JOKE_SCRIPT = ('<script>(function(){var D=document,j=JSON.parse(D.getElementById("jokes-data").textContent),k=Object.keys(j).sort(),'
               'd=new Date(),t=d.getFullYear()+"-"+("0"+(d.getMonth()+1)).slice(-2)+"-"+("0"+d.getDate()).slice(-2),p=null,i;'
               'function n(s){var a=s.split("-");return Math.round(Date.UTC(+a[0],a[1]-1,+a[2])/864e5)}'
               'if(k.length&&t>k[k.length-1]){p=k[(n(t)-n(k[k.length-1])-1)%k.length]}'
               'else{for(i=0;i<k.length;i++)if(k[i]<=t)p=k[i]}'
               'var b=D.getElementById("joke");if(b&&p){D.getElementById("joke-text").textContent=j[p];b.hidden=false}'
               'var r=D.querySelectorAll("#joke-list li"),s=0;for(i=0;i<r.length;i++)if(r[i].getAttribute("data-date")<=t){r[i].hidden=false;s++}'
               'var e=D.getElementById("joke-none");if(e&&!s)e.hidden=false;'
               '(' + DRESS + ')(D,p)})();</script>')


def as_data(name, value):
    """A value as a data block in the page. '<' is escaped so nothing in it can close the script tag."""
    return f'<script type="application/json" id="{name}">' + json.dumps(value, ensure_ascii=False, sort_keys=True).replace('<', '\\u003c') + '</script>'


def jokes_data(jokes):
    """The approved jokes as a data block in the page."""
    return as_data('jokes-data', jokes)


def joke_bubble(jokes, list_href):
    """The joke of the day as Deborah's speech bubble, for the top of the picture card. It is hidden until the script
    has a joke for today, so there is never an empty bubble. Nothing at all with no approved jokes."""
    if not jokes:
        return ''
    return (f'<div class="saying" id="joke" hidden><div class="sayinghead"><h2>{JOKE_HEADING}</h2>'
            f'<a href="{esc(list_href)}">Earlier<span> jokes</span></a></div><p class="joketext" id="joke-text"></p></div>')


def joke_scripts(jokes, day_looks=None):
    """The data and the one script for a page with jokes. A front page passes `day_looks` too, and the same
    script then dresses its picture; the list of earlier jokes has no picture and leaves it out."""
    if not jokes:
        return ''
    scene = as_data('scene-data', scene_data({d: day_looks[d] for d in jokes})) if day_looks else ''
    return jokes_data(jokes) + scene + JOKE_SCRIPT


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


def ohio_blocks(jokes, day_looks=None):
    return {'scene': scene_block(True, jokes, '../jokes.html'), 'jokescript': joke_scripts(jokes, day_looks)}


def render_ohio(text, jokes, day_looks=None):
    blocks = ohio_blocks(jokes, day_looks)
    found = [m.group('name') for m in MARK.finditer(text)]
    if sorted(found) != sorted(blocks):
        raise SystemExit(f'ohio/index.html: expected one marker each for {sorted(blocks)}, found {found}')
    return MARK.sub(lambda m: f'<!--home-extras:{m.group("name")}-->{blocks[m.group("name")]}<!--/home-extras-->', text)


def approve(start=None):
    """Mark the waiting jokes approved. With `start`, they run from that day: jokes dated before it keep their
    days, and approved jokes that had that day or a later one move back to follow the new ones, in order."""
    data = read_jokes()
    jokes = data['jokes']
    new = [j for j in jokes if j.get('approved') is not True]
    if not new:
        raise SystemExit('Every joke on file is already approved.')
    if start:
        day = datetime.date.fromisoformat(start)
        old = [j for j in jokes if j.get('approved') is True]
        kept, moved = [j for j in old if j['date'] < start], [j for j in old if j['date'] >= start]
        if kept and datetime.date.fromisoformat(kept[-1]['date']) + datetime.timedelta(days=1) != day:
            raise SystemExit(f'{start} would leave a gap after {kept[-1]["date"]}; a batch runs one day after another.')
        for j in new + moved:
            j['date'] = day.isoformat()
            day += datetime.timedelta(days=1)
        data['jokes'] = jokes = kept + new + moved
    for j in new:
        j['approved'] = True
    JOKES.write_text(json.dumps(data, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'Approved {len(new)} jokes, {new[0]["date"]} to {new[-1]["date"]}; the list now runs to {jokes[-1]["date"]}. '
          'Now run scripts/ymt_build.py and scripts/home_extras.py.')


def main():
    if '--approve' in sys.argv:
        approve(sys.argv[sys.argv.index('--start') + 1] if '--start' in sys.argv else None)
        return
    data = read_jokes()
    errors = check_jokes(data)
    if errors:
        raise SystemExit('data/jokes.json:\n' + '\n'.join(errors))
    jokes, day_looks = approved_jokes(data), approved_looks(data)
    targets = {OHIO_HOME: lambda text: render_ohio(text, jokes, day_looks)}
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
