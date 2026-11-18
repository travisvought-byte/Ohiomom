#!/usr/bin/env python3
"""Suicide and homelessness help on every page (owner direction, November 17, 2026).

One short "Need help now?" block sits directly above the footer of every page a visitor reads, on
Yoga Mom Talk and on OhioMom. Pages that only pass the visitor on do not carry it.

Each line was read on its source page on November 17, 2026:
- 988lifeline.org: call or text 988, 24 hours a day, free and confidential.
- veteranscrisisline.net: dial 988, then press 1.
- hud.gov/contactus: dial 2-1-1 and press 6 for homeless services; the Find Shelter tool.
- usa.gov/emergency-housing: National Call Center for Homeless Veterans, 1-877-424-3838,
  24 hours a day.
No number here has been dialed, like every other number on the site.

The block follows the site's own rules: phone links only (the site has no text-message links, so
"text 988" is words, not a link), nothing loaded from anywhere else, and its styles are written on
the block itself, so it reads the same under either stylesheet.

`scripts/ymt_build.py` adds the block to the national pages and `scripts/build_family_guide.py` to
the family guide. The OhioMom pages are static source, so they get it from this script:

    python3 scripts/help_now.py          add or refresh the block on the static pages
    python3 scripts/help_now.py --check  fail if any page is missing it or out of date

To publish: the block is one line, placed directly above the footer line of each page, so the live
copy of a page is changed the same way (insert that line above the footer) and then compared with
the repository, as for any other change (README, "Publishing to Wix").
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Each link is underlined and bold so it stands out under either stylesheet. Short links never break
# across lines; the longer Find Shelter link may wrap, so the block fits a narrow screen.
_WRAP = ' style="color:#0b4f6c;font-weight:700;text-decoration:underline"'
_LINK = ' style="color:#0b4f6c;font-weight:700;text-decoration:underline;white-space:nowrap"'
BLOCK = ('<aside class="help-now" aria-label="Need help now?" style="box-sizing:border-box;width:calc(100% - 32px);max-width:960px;'
         'margin:24px auto;padding:12px 16px;border:1px solid #b9c2bd;border-left:6px solid #7a1f1f;border-radius:6px;'
         'background:#fff;color:#1b1b1b;font:400 16px/1.5 system-ui,sans-serif;text-align:left">'
         '<strong>Need help now?</strong> Thinking about suicide, or in any crisis: '
         '<a href="tel:988"' + _LINK + '>call 988</a> or text 988, any time. '
         'Veterans: dial 988, then press 1. No safe place to sleep tonight: '
         '<a href="tel:211"' + _LINK + '>dial 211</a> and press 6 for homeless services, or use '
         '<a href="https://www.hud.gov/findshelter" rel="noopener"' + _WRAP + '>HUD’s Find Shelter tool</a>. Veterans: '
         '<a href="tel:+18774243838"' + _LINK + '>call 1-877-424-3838</a>, 24 hours a day.</aside>')
# One line of its own, directly above the footer line.
LINE = '<!--help-now-->' + BLOCK + '<!--/help-now-->\n'
FOOTER = '<footer'


def is_forward(text: str) -> bool:
    """A page that only passes the visitor on."""
    return 'http-equiv="refresh"' in text


def wants_help(name: str, text) -> bool:
    """True for a page a visitor reads: not a template and not a forwarding page."""
    if not name.endswith('.html') or not isinstance(text, str):
        return False
    if name.startswith(('templates/', 'tests/', 'node_modules/')):
        return False
    return not is_forward(text)


def strip_help(text: str) -> str:
    return re.sub(r'<!--help-now-->.*?<!--/help-now-->\n?', '', text, flags=re.S)


def add_help(text: str, name: str = 'page') -> str:
    """Put the block on its own line directly above the page's footer. Safe to repeat."""
    text = strip_help(text)
    if 'class="help-now"' in text:
        raise ValueError(f'{name}: carries a help block this script did not add')
    at = text.rfind(FOOTER)
    if at < 0:
        raise ValueError(f'{name}: no footer to put the help block above')
    return text[:at] + LINE + text[at:]


def tracked_pages(root: Path = ROOT):
    listed = subprocess.run(['git', '-C', str(root), 'ls-files', '*.html'], capture_output=True, text=True, check=True).stdout.split()
    return sorted(listed)


def built_names():
    """Pages written by the two builders, which add the block themselves."""
    sys.path.insert(0, str(ROOT / 'scripts'))
    import build_family_guide
    import ymt_build
    import ymt_lib
    return {n for n in ymt_build.build_all(ymt_lib.load()) if n.endswith('.html')} | set(build_family_guide.outputs())


def static_pages(root: Path = ROOT):
    """The static source pages a visitor reads: everything tracked that the builders do not write."""
    built = built_names()
    return [n for n in tracked_pages(root) if n not in built and wants_help(n, (root / n).read_text(encoding='utf-8'))]


def check_pages(root: Path = ROOT) -> int:
    """Every page a visitor reads carries the block once, on its own line directly above the footer. No other page carries it."""
    count = 0
    for name in tracked_pages(root):
        text = (root / name).read_text(encoding='utf-8')
        if not wants_help(name, text):
            assert 'class="help-now"' not in text, f'{name}: a template or forwarding page should not carry the help block'
            continue
        assert text.count(LINE) == 1 and text.count('class="help-now"') == 1, f'{name}: needs the help block exactly once'
        after = text[text.index(LINE) + len(LINE):]
        assert after.startswith(FOOTER) and FOOTER not in after[1:], f'{name}: the help block sits directly above the footer'
        assert add_help(text, name) == text, f'{name}: help block is out of date'
        count += 1
    return count


def main(argv):
    check = '--check' in argv
    stale = []
    for name in static_pages():
        path = ROOT / name
        text = path.read_text(encoding='utf-8')
        new = add_help(text, name)
        if new != text:
            stale.append(name)
            if not check:
                path.write_text(new, encoding='utf-8')
    if check:
        if stale:
            sys.exit('Help block missing or out of date (run python3 scripts/help_now.py):\n' + '\n'.join(stale))
        print(f'OK: {check_pages()} pages carry the help block once, directly above the footer')
    else:
        print('Updated: ' + (', '.join(stale) or 'nothing; the static pages were current'))


if __name__ == '__main__':
    main(sys.argv[1:])
