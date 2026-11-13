#!/usr/bin/env python3
"""Build index.html from data/resources.json. Run: python3 scripts/build.py [--check]"""
import html, json, sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def esc(v):
    return html.escape(str(v), quote=True)


def tel(p):
    return 'tel:' + ''.join(c for c in p if c.isdigit())


def card(r, needs):
    bits = [f'<article class="card" data-section="{esc(r["section"])}" data-needs="{esc(" ".join(r.get("needs", [])))}">']
    bits.append(f'<h3>{esc(r["name"])}</h3><p class="org">{esc(r["org"])}'
                + (' · National' if r['scope'] == 'US' else '') + '</p>')
    bits.append(f'<p>{esc(r["what"])}</p><p><strong>Next step:</strong> {esc(r["how"])}</p><p class="actions">')
    if r.get('phone'):
        bits.append(f'<a class="btn call" href="{tel(r["phone"])}">Call {esc(r["phone"])}</a>')
        if r.get('phone_label'):
            bits.append(f'<span class="note">{esc(r["phone_label"])}</span>')
    if r.get('text'):
        bits.append(f'<span class="btn plain">{esc(r["text"])}</span>')
    if r.get('url'):
        bits.append(f'<a class="btn" href="{esc(r["url"])}" rel="noopener noreferrer">Website</a>')
    d = date.fromisoformat(r['reviewed_on'])
    bits.append(f'</p><p class="meta">Checked against published sources {d.strftime("%B")} {d.day}, {d.year}</p></article>')
    return ''.join(bits)


def build():
    data = json.loads((ROOT / 'data' / 'resources.json').read_text(encoding='utf-8'))
    site = data['site']
    nav = ''.join(f'<a href="#{esc(s["id"])}">{esc(s["label"])}</a>' for s in data['sections'])
    tiles = ''.join(
        f'<a class="tile{" urgent" if s["id"] == "help-now" else ""}" href="#{esc(s["id"])}">'
        f'<strong>{esc(s["label"])}</strong><span>{esc(s["summary"])}</span></a>' for s in data['sections'])
    body = []
    for s in data['sections']:
        items = [r for r in data['resources'] if r['section'] == s['id']]
        extra = ''
        if s['id'] == 'help-now':
            extra = ('<div class="safety"><p><strong>In danger right now? Call 911.</strong></p>'
                     '<p>If someone checks your phone or computer, use a device they cannot reach, such as one at a '
                     'library or a friend\'s home. The "Leave this site" button at the top of every page takes you '
                     'to a weather search right away. It does not erase your browser history.</p></div>')
        if s['id'] == 'disability':
            opts = ''.join(f'<option value="{esc(n["id"])}">{esc(n["label"])}</option>' for n in data['needs'])
            extra = (f'<p><label for="need">Show resources for </label><select id="need">'
                     f'<option value="">any need</option>{opts}</select></p>')
        body.append(f'<section id="{esc(s["id"])}"><h2>{esc(s["label"])}</h2><p class="lede">{esc(s["summary"])}</p>'
                    f'{extra}<div class="cards">{"".join(card(r, data["needs"]) for r in items)}</div></section>')
    founder = f'<p>Founded by {esc(site["founder"])}.</p>' if site.get('founder') else ''
    report = (f'<p>See something out of date? <a href="mailto:{esc(site["corrections_email"])}?subject=OhioMom%20correction">'
              f'Report a problem</a>.</p>') if site.get('corrections_email') else ''
    tpl = (ROOT / 'templates' / 'index.html').read_text(encoding='utf-8')
    out = (tpl.replace('{{NAV}}', nav).replace('{{TILES}}', tiles).replace('{{SECTIONS}}', ''.join(body))
           .replace('{{FOUNDER}}', founder).replace('{{REPORT}}', report)
           .replace('{{ATTRIBUTION}}', esc(data['attribution'])))
    return out


if __name__ == '__main__':
    out = build()
    target = ROOT / 'index.html'
    if '--check' in sys.argv:
        if not target.exists() or target.read_text(encoding='utf-8') != out:
            sys.exit('index.html is out of date. Run: python3 scripts/build.py')
        print('index.html is current')
    else:
        target.write_text(out, encoding='utf-8')
        print('wrote index.html')
