#!/usr/bin/env python3
"""OhioMom's busiest help pages in the languages of Ohio's largest non-English-speaking communities.

Spanish (es), Somali (so), Haitian Creole (ht) and Nepali (ne). The English page is the source: this script reads
each English page under ohio/, swaps every visible text and the words in a few attributes (title, description,
placeholder, aria-label, alt) for the line in data/i18n/ohio-<lang>.json, and writes the copy to
ohio/<lang>/<same path>. Links are rewritten so the translated pages link to each other, and everything else
still reaches the English page it pointed to.

- Names of agencies and programs stay in English. A translation may add its own words in brackets after a name.
- A line with no translation yet stays in English and is marked lang="en", so nothing is ever half-made or empty.
  `--missing` lists them, language by language.
- Every page in the set, English included, gets hreflang links (head) and a language switch (top of <main>), written
  between <!-- i18n --> markers. Each translated page ends with a short line, in its own language, inviting
  corrections through the site's own report page.
- Ads are never copied into a translated page.

Run after changing any of the English pages or a translation file:
    python3 scripts/ohio_i18n.py            write the pages
    python3 scripts/ohio_i18n.py --check    fail if any page is out of date (run by the Validate workflow)
    python3 scripts/ohio_i18n.py --missing  list lines that still show in English
    python3 scripts/ohio_i18n.py --strings  print every line to translate, in page order, as JSON
"""
import html
import json
import posixpath
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OHIO = ROOT / 'ohio'
I18N = ROOT / 'data' / 'i18n'
SITE = 'https://www.yogamomtalk.com/'
# The pages, as paths under ohio/. Order is the order of the language switch's page list.
PAGES = ['help.html', 'help/housing.html', 'help/bills.html', 'help/pregnancy-baby.html', 'help/single-parent.html']
# Language code, its own name, and the name in English (for the switch's accessible label).
LANGS = [('es', 'Español', 'Spanish'), ('so', 'Soomaali', 'Somali'), ('ht', 'Kreyòl ayisyen', 'Haitian Creole'), ('ne', 'नेपाली', 'Nepali')]
TEXT_ATTRS = ('title', 'placeholder', 'aria-label', 'alt')
META_TEXT = ('description', 'og:title', 'og:description', 'og:image:alt')
URL_ATTRS = ('href', 'src', 'data-root')
TOKEN = re.compile(r'(<!--.*?-->|<[^>]+>)', re.S)
ATTR = re.compile(r'''([a-zA-Z:-]+)="([^"]*)"''')
MARK = re.compile(r'\n?<!-- i18n -->.*?<!-- /i18n -->', re.S)
AD_ASIDE = re.compile(r'\n?<aside class="ad-slot"[^>]*>.*?</aside>', re.S)
AD_NET = re.compile(r'\n?<!-- ad network -->.*?<!-- /ad network -->', re.S)
LETTER = re.compile(r'[^\W\d_]{2}', re.U)


def norm(text):
    return ' '.join(html.unescape(text).split())


def load(lang):
    p = I18N / f'ohio-{lang}.json'
    data = json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
    return data


def strip_generated(text):
    return AD_NET.sub('', AD_ASIDE.sub('', MARK.sub('', text)))


def strings(text):
    """Every line a translator needs, in page order, without repeats."""
    out, skip = [], 0
    for tok in TOKEN.split(strip_generated(text)):
        if not tok:
            continue
        if tok.startswith('<!--'):
            continue
        if tok.startswith('<'):
            name = re.match(r'</?\s*([a-zA-Z0-9]+)', tok)
            name = name.group(1).lower() if name else ''
            if name in ('script', 'style'):
                skip += -1 if tok.startswith('</') else (0 if tok.endswith('/>') else 1)
            if tok.startswith('</'):
                continue
            attrs = dict(ATTR.findall(tok))
            for a in TEXT_ATTRS:
                if a in attrs and LETTER.search(attrs[a]):
                    out.append(norm(attrs[a]))
            if name == 'meta' and (attrs.get('name') in META_TEXT or attrs.get('property') in META_TEXT):
                out.append(norm(attrs.get('content', '')))
            continue
        if skip:
            continue
        line = norm(tok)
        if line and LETTER.search(line):
            out.append(line)
    seen, ordered = set(), []
    for s in out:
        if s not in seen:
            seen.add(s)
            ordered.append(s)
    return ordered


def target(lang, page):
    return f'{lang}/{page}'


def rel(from_page, to_path):
    """Relative address from ohio/<from_page> to ohio/<to_path> (both under ohio/, either may climb out with ../)."""
    start = posixpath.dirname(from_page) or '.'
    r = posixpath.relpath(to_path, start)
    return r


def rewrite_url(url, src_page, out_page, lang):
    if not url or url.startswith(('http:', 'https:', 'tel:', 'mailto:', '#', 'data:', '//')):
        return url
    if url.startswith('/'):
        return url
    path, sep, frag = url.partition('#')
    path, qsep, query = path.partition('?')
    trailing = path.endswith('/') or path in ('.', '..', '../', './')
    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(src_page) or '.', path or posixpath.basename(src_page)))
    if lang and resolved in PAGES:
        resolved = target(lang, resolved)
    new = rel(out_page, resolved) if path else ''
    if trailing and not new.endswith('/'):
        new += '/'
    if path == '' and not frag:
        return url
    return new + (qsep + query if qsep else '') + (sep + frag if sep else '')


def translate_attr_value(value, table, lang):
    key = norm(value)
    if key in table:
        return html.escape(table[key], quote=True)
    return value


def page_url(page):
    return f'{SITE}ohio/{page}'


def alternates(page):
    links = [f'<link rel="alternate" hreflang="en" href="{page_url(page)}">']
    links += [f'<link rel="alternate" hreflang="{code}" href="{page_url(target(code, page))}">' for code, _, _ in LANGS]
    links.append(f'<link rel="alternate" hreflang="x-default" href="{page_url(page)}">')
    return '<!-- i18n -->' + ''.join(links) + '<!-- /i18n -->'


def switch(page, here_page, current):
    """The language switch at the top of <main>: every language, each in its own words."""
    items = [('en', 'English', 'English', page)] + [(c, n, e, target(c, page)) for c, n, e in LANGS]
    links = []
    for code, name, eng, dest in items:
        attrs = f'lang="{code}" hreflang="{code}"'
        if code == current:
            links.append(f'<a {attrs} href="{rel(here_page, dest)}" aria-current="page">{html.escape(name)}</a>')
        else:
            label = '' if code == 'en' else f' aria-label="{html.escape(name)} ({eng})"'
            links.append(f'<a {attrs} href="{rel(here_page, dest)}"{label}>{html.escape(name)}</a>')
    return ('<!-- i18n --><nav class="langs" aria-label="Language"><div class="wrap">' + ''.join(links)
            + '</div></nav><!-- /i18n -->')


def fix_line(lang, table, out_page):
    words = table.get('__fix__') or {}
    if not words:
        return ''
    return (f'<!-- i18n --><section class="wrap i18n-fix"><p>{html.escape(words["line"])} '
            f'<a href="{rel(out_page, "report.html")}">{html.escape(words["link"])}</a></p></section><!-- /i18n -->')


def english_page(page):
    """The English page with its hreflang links and language switch brought up to date."""
    text = MARK.sub('', (OHIO / page).read_text(encoding='utf-8'))
    text = text.replace('<link rel="canonical"', alternates(page) + '\n<link rel="canonical"', 1)
    text = text.replace('<main id="main">\n', '<main id="main">\n' + switch(page, page, 'en') + '\n', 1)
    return text


def translated_page(page, lang, table):
    src = strip_generated((OHIO / page).read_text(encoding='utf-8'))
    out_page = target(lang, page)
    parts, skip = [], 0
    for tok in TOKEN.split(src):
        if not tok:
            continue
        if tok.startswith('<!--'):
            parts.append(tok)
            continue
        if tok.startswith('<'):
            m = re.match(r'</?\s*([a-zA-Z0-9]+)', tok)
            name = m.group(1).lower() if m else ''
            if name in ('script', 'style'):
                skip += -1 if tok.startswith('</') else (0 if tok.endswith('/>') else 1)
            if tok.startswith('</'):
                parts.append(tok)
                continue
            attrs = dict(ATTR.findall(tok))
            is_meta_text = name == 'meta' and (attrs.get('name') in META_TEXT or attrs.get('property') in META_TEXT)

            def sub(mm):
                k, v = mm.group(1), mm.group(2)
                if k in TEXT_ATTRS or (is_meta_text and k == 'content'):
                    return f'{k}="{translate_attr_value(v, table, lang)}"'
                if k in URL_ATTRS:
                    return f'{k}="{html.escape(rewrite_url(html.unescape(v), page, out_page, lang), quote=True)}"'
                if name == 'meta' and attrs.get('property') == 'og:url' and k == 'content':
                    return f'content="{page_url(out_page)}"'
                if name == 'link' and attrs.get('rel') == 'canonical' and k == 'href':
                    return f'href="{page_url(out_page)}"'
                return mm.group(0)
            if name == 'link' and attrs.get('rel') == 'canonical':
                tok = f'<link rel="canonical" href="{page_url(out_page)}">'
            elif name == 'html':
                tok = f'<html lang="{lang}">'
            else:
                tok = ATTR.sub(sub, tok)
            parts.append(tok)
            continue
        if skip:
            parts.append(tok)
            continue
        line = norm(tok)
        if not line or not LETTER.search(line):
            parts.append(tok)
            continue
        lead = tok[:len(tok) - len(tok.lstrip())]
        tail = tok[len(tok.rstrip()):]
        if line in table:
            parts.append(lead + html.escape(table[line], quote=False) + tail)
        else:
            parts.append(lead + f'<span lang="en">{html.escape(line, quote=False)}</span>' + tail)
    text = ''.join(parts)
    text = text.replace('<link rel="canonical"', alternates(page) + '\n<link rel="canonical"', 1)
    text = text.replace('<main id="main">\n', '<main id="main">\n' + switch(page, out_page, lang) + '\n', 1)
    text = text.replace('\n</main>', '\n' + fix_line(lang, table, out_page) + '\n</main>', 1)
    return text


def build():
    files = {}
    for page in PAGES:
        files[f'ohio/{page}'] = english_page(page)
    for code, _, _ in LANGS:
        table = load(code)
        strings_table = {k: v for k, v in table.items() if not k.startswith('__')}
        strings_table['__fix__'] = table.get('__fix__')
        for page in PAGES:
            files[f'ohio/{target(code, page)}'] = translated_page(page, code, strings_table)
    return files


def missing():
    out = {}
    for code, _, _ in LANGS:
        table = load(code)
        need = []
        for page in PAGES:
            for s in strings((OHIO / page).read_text(encoding='utf-8')):
                if s not in table and s not in need:
                    need.append(s)
        out[code] = need
    return out


def main():
    if '--strings' in sys.argv:
        allx = []
        for page in PAGES:
            for s in strings((OHIO / page).read_text(encoding='utf-8')):
                if s not in allx:
                    allx.append(s)
        print(json.dumps(allx, ensure_ascii=False, indent=1))
        return
    if '--missing' in sys.argv:
        for code, need in missing().items():
            print(f'{code}: {len(need)} lines still in English')
            for s in need:
                print('   ', s)
        return
    files = build()
    if '--check' in sys.argv:
        stale = [p for p, t in files.items() if not (ROOT / p).exists() or (ROOT / p).read_text(encoding='utf-8') != t]
        if stale:
            print('Out of date (run python3 scripts/ohio_i18n.py):\n' + '\n'.join(stale))
            sys.exit(1)
        print(f'OK: {len(files)} pages match their English source and translations')
        return
    for p, t in files.items():
        (ROOT / p).parent.mkdir(parents=True, exist_ok=True)
        (ROOT / p).write_text(t, encoding='utf-8')
    print(f'Wrote {len(files)} pages')


if __name__ == '__main__':
    main()
