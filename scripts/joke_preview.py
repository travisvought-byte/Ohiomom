#!/usr/bin/env python3
"""A page for the owner to look at before a batch of jokes is approved.

    python3 scripts/joke_preview.py ../preview.html

It shows the picture card exactly as the front pages draw it (the same drawing, the same rules, the same few
lines of script), for every day on file: the jokes that are waiting for approval first, then the ones already
approved. The owner can step through the days, tap any joke to see its picture, and try any pose, any sweater
and any of the children. It is one file with nothing to load, so it can be opened on a phone or sent to someone.

It is not part of the site. It holds jokes nobody has approved yet, so it is never written into this repository
(the script refuses), never committed and never published.
"""
import json
import sys
from html import escape as esc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import home_extras as extras  # noqa: E402

TITLE = 'Yoga Mom Talk: the family picture and the jokes waiting for approval'
EVERYONE = 'everyone'  # the key of the first view: the whole family at once, so each likeness can be checked
STYLE = '''
:root{--ink:#2b2140;--muted:#655c78;--bg:#fff9f3;--line:#f1e4d8;--brand:#cf2f5b;--teal:#12766f}
*{box-sizing:border-box}
body{margin:0;font:1.0625rem/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;color:var(--ink);background:var(--bg)}
main{max-width:34rem;margin:0 auto;padding:1.1rem 1rem 3rem}
h1,h2{font-family:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;line-height:1.15;margin:0}
h1{font-size:1.7rem;margin-bottom:.4rem}
h2{font-size:1.25rem;margin:1.8rem 0 .2rem}
p{margin:.4rem 0}
a{color:var(--teal)}
.note{display:inline-block;margin:0 0 .6rem;padding:.15rem .6rem;border-radius:2rem;background:#ffe9c2;font-size:.8rem;font-weight:700}
.quiet{color:var(--muted);font-size:.92rem}
.stage{position:sticky;top:0;z-index:5;margin:0 -1rem;padding:.6rem 1rem .5rem;background:var(--bg)}
.stage .scenebox{width:100%;max-width:26rem;margin:0 auto}
.stage .sayinghead a{pointer-events:none}
.step{display:flex;align-items:center;justify-content:space-between;gap:.5rem;max-width:26rem;margin:.5rem auto 0}
.step span{flex:1;text-align:center;font-size:.9rem;color:var(--muted)}
button{font:inherit;color:inherit;cursor:pointer}
.step button,.chips button{border:1.5px solid var(--line);background:#fff;border-radius:2rem;padding:.4rem .9rem;font-weight:600;font-size:.92rem}
.step button{min-width:5.2rem}
.chips{display:flex;flex-wrap:wrap;gap:.4rem;margin:.35rem 0 .2rem}
.chips button[aria-pressed=true]{background:var(--brand);border-color:var(--brand);color:#fff}
.list{list-style:none;counter-reset:n;padding:0;margin:.5rem 0 0}
.list li{counter-increment:n;border-top:1.5px solid var(--line)}
.list button{display:block;width:100%;text-align:left;border:0;background:none;padding:.7rem 0 .7rem 2.1rem;position:relative}
.list button::before{content:counter(n);position:absolute;left:0;top:.75rem;width:1.5rem;height:1.5rem;border-radius:50%;background:#fff1e6;
  font-size:.78rem;font-weight:700;line-height:1.5rem;text-align:center}
.list button[aria-current=true]::before{background:var(--brand);color:#fff}
.list .who{display:block;color:var(--muted);font-size:.82rem;margin-top:.15rem}
button:focus-visible{outline:3px solid var(--teal);outline-offset:2px}
@media (min-width:52rem){main{max-width:60rem;display:grid;grid-template-columns:26rem 1fr;gap:0 2.5rem;align-items:start}
  .top,.stage{grid-column:1}.stage{top:.5rem;margin:0;padding:0}.rest{grid-column:2;grid-row:1/span 3}.rest h2:first-child{margin-top:0}}
'''
# The page's own script. `dress` is the front pages' own function (home_extras.DRESS), so what shows here is what
# the site will show. A view is a key of the picture data: a day, the whole family, or "mine" for the try-it-yourself row.
SCRIPT = '''(function(){var D=document,dress=%(dress)s,jokes=JSON.parse(D.getElementById("jokes-data").textContent),
store=D.getElementById("scene-data"),scene=JSON.parse(store.textContent),days=%(days)s,at=-1,
$=function(id){return D.getElementById(id)},all=function(s){return Array.prototype.slice.call(D.querySelectorAll(s))};
function press(){var v=(scene.d[at<0?"%(everyone)s":days[at]]||"").split("|"),mine=scene.d.mine?scene.d.mine.split("|"):v;
  all("[data-try]").forEach(function(b){var k=b.getAttribute("data-try"),n=b.getAttribute("data-name");
    b.setAttribute("aria-pressed",k=="kid"?(" "+mine[2]+" ").indexOf(" "+n+" ")>=0:mine[k=="pose"?0:1]==n)})}
function show(key,words,label){$("joke-text").textContent=words;$("joke").hidden=false;dress(D,key);$("where").textContent=label;
  all(".list button").forEach(function(b){b.setAttribute("aria-current",b.getAttribute("data-day")==key)})}
function day(i){at=i;delete scene.d.mine;var k=days[i],n=%(waiting)d;
  show(k,jokes[k],i<n?"Waiting: "+(i+1)+" of "+n:"Approved: "+(i-n+1)+" of "+(days.length-n));press()}
function everyone(){at=-1;delete scene.d.mine;show("%(everyone)s",%(hello)s,"The whole family");press()}
function mine(change){var v=(scene.d.mine||scene.d[at<0?"%(everyone)s":days[at]]).split("|");change(v);
  v[3]="Trying it out: "+scene.names[v[0]]+", the "+v[1]+" sweater.";scene.d.mine=v.join("|");store.textContent=JSON.stringify(scene);
  $("joke-text").textContent=%(trying)s;dress(D,"mine");$("where").textContent="Trying it out";press()}
$("prev").onclick=function(){at<=0?everyone():day(at-1)};
$("next").onclick=function(){day(at<days.length-1?at+1:0)};
$("all").onclick=everyone;
all(".list button").forEach(function(b){b.onclick=function(){day(days.indexOf(b.getAttribute("data-day")))}});
all("[data-try]").forEach(function(b){b.onclick=function(){var k=b.getAttribute("data-try"),n=b.getAttribute("data-name");
  mine(function(v){if(k=="pose")v[0]=n;else if(k=="sweater")v[1]=n;else{var c=v[2]?v[2].split(" "):[],i=c.indexOf(n);i<0?c.push(n):c.splice(i,1);v[2]=c.join(" ")}})}});
everyone()})();'''


def who(look):
    """One line under a joke in the list: who is in its picture, her pose and her sweater."""
    pose, sweater, cast, _ = look
    kids = ', '.join(extras.KID_NAMES[k] for k in cast) or 'Deborah alone'
    return f'{kids} · {extras.POSES[pose]["name"]} · {sweater} sweater'


def chips(kind, names, labels):
    return '<div class="chips">' + ''.join(
        f'<button type="button" data-try="{kind}" data-name="{n}" aria-pressed="false">{esc(labels[n])}</button>' for n in names) + '</div>'


def page(data=None):
    """The preview as one HTML document."""
    data = extras.read_jokes() if data is None else data
    errors = extras.check_jokes(data)
    if errors:
        raise SystemExit('data/jokes.json:\n' + '\n'.join(errors))
    looks = extras.looks(data)
    waiting = [j for j in data['jokes'] if j.get('approved') is not True]
    approved = [j for j in data['jokes'] if j.get('approved') is True]
    order = waiting + approved
    jokes = {j['date']: j['text'] for j in order}
    scene = extras.scene_data(looks)
    scene['d'][EVERYONE] = '|'.join(('mountain', extras.FIRST_SWEATER, ' '.join(extras.KIDS),
                                     'Deborah on her mat. Left to right: Genevieve, Ephraim, Delilah and Atlas.'))
    scene['names'] = {name: spec['name'] for name, spec in extras.POSES.items()}

    def rows(batch):
        return '<ol class="list">' + ''.join(
            f'<li><button type="button" data-day="{j["date"]}" aria-current="false">{esc(j["text"])}'
            f'<span class="who">{esc(who(looks[j["date"]]))}</span></button></li>' for j in batch) + '</ol>'

    hello = 'This is all of us at once, so you can check each of us. Step through the days, or tap any joke below to see its picture.'
    script = SCRIPT % {'dress': extras.DRESS, 'days': json.dumps([j['date'] for j in order]), 'waiting': len(waiting),
                       'everyone': EVERYONE, 'hello': json.dumps(hello, ensure_ascii=False),
                       'trying': json.dumps('Any pose, any sweater, any of the kids: tap the buttons below.', ensure_ascii=False)}
    rules = extras.STYLE.read_text(encoding='utf-8')
    wait_head = (f'<h2>Waiting for your OK ({len(waiting)})</h2><p class="quiet">None of these is on the site. Tap one to see its picture.</p>{rows(waiting)}'
                 if waiting else '<h2>Nothing is waiting</h2><p class="quiet">Every joke on file is approved.</p>')
    done_head = (f'<h2>Already approved ({len(approved)})</h2><p class="quiet">The words are as approved. This is who is in the picture with each.</p>{rows(approved)}'
                 if approved else '')
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>{esc(TITLE)}</title>
<style>{STYLE}{rules}</style>
</head>
<body>
<main>
<div class="top"><p class="note">Preview. Not on the site.</p>
<h1>The family picture and the jokes</h1>
<p class="quiet">This is the card at the top of the Yoga Mom Talk and OhioMom home pages, drawn by the same code. It moves; give it a few seconds.</p></div>
<div class="stage" id="stage">{extras.scene_block(False, jokes, '#')}
<div class="step"><button type="button" id="prev">Back</button><span id="where" aria-live="polite"></span><button type="button" id="next">Next</button></div></div>
<div class="rest">
<h2>Try it yourself</h2>
<p class="quiet">Who is in the picture</p>{chips('kid', extras.KIDS, extras.KID_NAMES)}
<p class="quiet">Her pose</p>{chips('pose', extras.POSES, {n: s['name'] for n, s in extras.POSES.items()})}
<p class="quiet">Her sweater</p>{chips('sweater', extras.SWEATERS, {n: n for n in extras.SWEATERS})}
<div class="chips"><button type="button" id="all">Show the whole family again</button></div>
{wait_head}
{done_head}
</div>
</main>
{extras.as_data('jokes-data', jokes)}{extras.as_data('scene-data', scene)}
<script>{script}</script>
</body>
</html>
'''


def main():
    if len(sys.argv) != 2 or sys.argv[1].startswith('-'):
        raise SystemExit(__doc__)
    out = Path(sys.argv[1]).resolve()
    if out == extras.ROOT or extras.ROOT in out.parents:
        raise SystemExit('The preview holds jokes that are not approved, so it is not written inside the repository. Give a path outside it.')
    out.write_text(page(), encoding='utf-8')
    print(f'Wrote {out}')


if __name__ == '__main__':
    main()
