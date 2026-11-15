'use strict';
// Family guide filters. Choices live in the URL only: nothing is stored or sent.
(() => {
 const data = JSON.parse(document.getElementById('family-data').textContent);
 const $ = id => document.getElementById(id);
 const states = data.states, pa = data.protection_advocacy;
 const stageIds = new Set(data.stages.map(s => s.id));
 const stageLabel = new Map(data.stages.map(s => [s.id, s.label]));
 const needName = new Map(data.needs.map(n => [n.id, n.label.split(' (')[0]]));
 const counties = new Map(data.ohio_counties.map(c => [c.county, c]));
 const reduceMotion = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
 const el = (tag, attrs = {}, text = '') => { const e = document.createElement(tag); Object.entries(attrs).forEach(([k, v]) => e.setAttribute(k, v)); if (text) e.textContent = text; return e; };
 const tel = p => 'tel:' + p.replace(/\D/g, '');
 const link = (href, text) => el('a', /^https?:/.test(href) ? {href, target: '_blank', rel: 'noopener'} : {href}, text);
 // Remember authored order so sorting can always return to it.
 const original = new Map();
 document.querySelectorAll('.resource').forEach((c, i) => original.set(c, i));
 // '' until the visitor makes a choice. Nothing is listed before that; 'all' is the choice "Show everything".
 let stage = '';
 // Six listings first, the rest when asked. A new stage or need starts short again.
 const CAP = 6;
 let showAll = false;
 // Language: English by default; ?lang=es switches the top of the page to Spanish. Listings stay in English.
 const es = data.es;
 let lang = 'en';
 const fill = (tpl, vals) => tpl.replace(/\{(\w+)\}/g, (_, k) => vals[k]);
 const english = new Map();
 const marked = () => document.querySelectorAll('[data-i18n],[data-i18n-stage],[data-i18n-need]');
 marked().forEach(e => english.set(e, e.innerHTML));
 const esText = e => {
  if (e.dataset.i18n) return es.static[e.dataset.i18n];
  if (e.dataset.i18nNeed) return es.needs[e.dataset.i18nNeed].label;
  const [id, field] = e.dataset.i18nStage.split(':');
  return es.stages[id][field];
 };
 const stageName = id => lang === 'es' ? es.stages[id].label : stageLabel.get(id);
 const needShort = id => lang === 'es' ? es.needs[id].short : needName.get(id).toLowerCase();

 const LETTER_EN = "Dear Director of Special Education,\n\nI am the parent of [child's name], who is in [grade] at [school name]. I am writing to request an evaluation for special education services because I am concerned about [briefly describe what you're seeing].\n\nPlease send me the consent form and let me know what happens next.\n\nThank you,\n[Your name]\n[Phone or email]";
 const letterTemplate = () => lang === 'es' ? es.dynamic.letter : LETTER_EN;
 let letterEdited = false;

 function applyLang() {
  const spanish = lang === 'es';
  if (!letterEdited) $('letter-text').value = letterTemplate();
  $('letter-status').textContent = '';
  marked().forEach(e => {
   e.innerHTML = spanish ? esText(e) : english.get(e);
   if (spanish) e.setAttribute('lang', 'es'); else e.removeAttribute('lang');
  });
  const toggle = $('lang-toggle');
  toggle.textContent = spanish ? es.static['lang-toggle'] : 'Español';
  toggle.setAttribute('lang', spanish ? 'en' : 'es');
  toggle.setAttribute('hreflang', spanish ? 'en' : 'es');
  $('es-note').textContent = es.static['es-note'];
  $('es-note').hidden = !spanish;
 }

 function readParams() {
  const p = new URLSearchParams(location.search);
  lang = p.get('lang') === 'es' ? 'es' : 'en';
  const s = (p.get('state') || 'OH').toUpperCase();
  $('state').value = states[s] ? s : 'OH';
  const c = p.get('county') || '';
  $('county').value = counties.has(c) ? c : '';
  const st = p.get('stage') || '';
  stage = st === 'all' || stageIds.has(st) ? st : '';
  const needs = new Set((p.get('need') || '').split(',').filter(n => needName.has(n)));
  document.querySelectorAll('input[name=need]').forEach(i => { i.checked = needs.has(i.value); });
  if (needs.size) $('needs-box').open = true;
  // A link that already names a county, a need or one listing is a choice.
  if (!stage && ($('county').value || needs.size || /^#r-/.test(location.hash))) stage = 'all';
 }

 const selectedNeeds = () => [...document.querySelectorAll('input[name=need]:checked')].map(i => i.value);

 function writeParams(state, county, needs) {
  const p = new URLSearchParams();
  p.set('state', state);
  if (state === 'OH' && county) p.set('county', county);
  if (stage) p.set('stage', stage);
  if (needs.length) p.set('need', needs.join(','));
  if (lang === 'es') p.set('lang', 'es');
  history.replaceState(null, '', location.pathname + '?' + p.toString() + location.hash);
 }

 function matches(card, state, needs) {
  if (card.dataset.scope === 'OH' && state !== 'OH') return false;
  if ((card.dataset.replaced || '').split(' ').some(r => r.split(':')[0] === state)) return false;
  if (stage && stage !== 'all' && !card.dataset.stages.split(' ').includes(stage)) return false;
  if (needs.length) {
   const cardNeeds = card.dataset.needs.split(' ');
   if (!cardNeeds.includes('any') && !needs.some(n => cardNeeds.includes(n))) return false;
  }
  return true;
 }

 // Show a container's cards: programs made for a checked need first, then the state's own programs, then authored order.
 function showCards(container, state, needs) {
  const cards = [...container.querySelectorAll('.resource')];
  let shown = 0, specific = 0;
  const rank = c => {
   const isMatch = needs.length > 0 && needs.some(n => c.dataset.needs.split(' ').includes(n));
   c.classList.toggle('match', isMatch);
   return (isMatch ? 0 : 2) + (c.dataset.scope === state ? 0 : 1);
  };
  const sorted = cards.sort((a, b) => rank(a) - rank(b) || original.get(a) - original.get(b));
  const ok = new Map(sorted.map(c => [c, matches(c, state, needs)]));
  const total = sorted.filter(c => ok.get(c)).length;
  // Only the main list is cut short, and only when that hides more than a couple of listings.
  const cap = container.id === 'cards' && !showAll && total > CAP + 2 ? CAP : Infinity;
  sorted.forEach(c => {
   const yes = ok.get(c);
   c.hidden = !yes;
   if (yes) { shown++; if (c.classList.contains('match')) specific++; }
   c.classList.toggle('capped', yes && shown > cap);
   container.append(c);
  });
  return {shown, specific, held: total > cap ? total - cap : 0};
 }

 function renderAnchors(state, county) {
  const name = states[state];
  const spanish = lang === 'es';
  const say = text => spanish && es.anchor_text[text] ? es.anchor_text[text] : text;
  $('anchors-title').textContent = spanish ? fill(es.dynamic.anchors_title, {state: name}) : 'Your first calls in ' + name;
  const list = $('anchor-list');
  list.replaceChildren();
  for (const a of data.anchors[state === 'OH' ? 'OH' : 'default']) {
   if (stage && stage !== 'all' && !a.stages.includes(stage)) continue;
   const li = el('li'), parts = [];
   li.append(el('strong', {}, (spanish ? es.anchor_labels[a.label] : a.label) + ': '));
   for (const item of a.items) {
    if (item.pa) parts.push(link(pa[state].url, pa[state].name), link(tel(pa[state].phone), pa[state].phone));
    else if (item.ei) { const e = data.early_intervention[state]; parts.push(link(e.url, e.name), link(tel(e.phone), e.phone)); }
    else if (item.pti) { const c = data.parent_centers[state]; if (c) parts.push(link(c.url, c.name), link(tel(c.phone), c.phone)); else parts.push(link('https://www.parentcenterhub.org/find-your-center/', spanish ? fill(es.anchor_text.parent_centers, {state: name}) : 'find ' + name + "'s parent centers (more than one serves the state)")); }
    else if (item.tel) parts.push(link(tel(item.tel), item.tel));
    else if (item.href) parts.push(link(item.href, say(item.text).replace('{state}', name)));
    else parts.push(document.createTextNode(say(item.text)));
   }
   parts.forEach((n, i) => { if (i) li.append(' · '); li.append(n); });
   list.append(li);
  }
  const box = $('county-result');
  box.replaceChildren();
  if (state !== 'OH' || !county) return;
  const c = counties.get(county), wrap = el('div', {class: 'county-box'}), ul = el('ul');
  const d = es.dynamic;
  wrap.append(el('h3', {}, spanish ? fill(d.county_heading, {county}) : county + ' County'));
  const row = (label, nodes) => { const li = el('li'); li.append(el('strong', {}, label + ': ')); nodes.forEach((n, i) => { if (i) li.append(' · '); li.append(n); }); ul.append(li); };
  const ddLabel = spanish ? d.county_dd : 'County board of DD';
  if (c.dd) {
   const boardName = spanish ? fill(d.county_dd_link, {county}) : county + ' County Board of DD';
   const nodes = [c.dd.url ? link(c.dd.url, boardName) : document.createTextNode(boardName + (c.dd.city ? ' (' + c.dd.city + ')' : '')), link(tel(c.dd.phone), c.dd.phone)];
   if (c.dd.ask) nodes.push(document.createTextNode(spanish ? d.county_dd_ask : 'ask how to apply for services'));
   row(ddLabel, nodes);
  }
  else row(ddLabel, [link('https://www.oacbdd.org/familyresources', spanish ? fill(d.county_dd_map, {county}) : 'pick ' + county + ' County on the map'), link('tel:8006176733', '800-617-6733')]);
  row(spanish ? d.veteran_families : 'Veteran families', [link('https://guide.vethomeguard.org/?state=OH&county=' + encodeURIComponent(county), spanish ? fill(d.cvso, {county}) : county + ' County veterans service office')]);
  wrap.append(ul);
  box.append(wrap);
 }

 function updateReports(state) {
  document.querySelectorAll('a.report').forEach(a => {
   const subject = 'Family guide correction: ' + a.dataset.report + ' (' + state + ')';
   const body = 'Listing: ' + a.dataset.report + '\nState: ' + states[state] + '\nWhat should be corrected?\n\n\nPlease do not include a child\'s name, medical details or other personal information.';
   a.href = 'mailto:travis@vethomeguard.org?subject=' + encodeURIComponent(subject) + '&body=' + encodeURIComponent(body);
  });
 }

 function apply(write = true) {
  const state = $('state').value, ohio = state === 'OH';
  $('county-wrap').hidden = !ohio;
  $('ohio-crisis').hidden = !ohio;
  if (!ohio) $('county').value = '';
  const county = $('county').value, needs = selectedNeeds();
  // The list and the first calls appear once a choice has been made.
  $('results').classList.toggle('chosen', stage !== '');
  const staged = stage && stage !== 'all';
  document.querySelectorAll('.stage').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.stage === stage)));
  document.querySelectorAll('.quick-btn').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.quick === stage)));
  // The written-request letter appears when school-age evaluation is the next step.
  $('letter').hidden = !(stage === 'school' || stage === 'concern');
  const main = showCards($('cards'), state, needs), mil = showCards($('military-cards'), state, needs);
  $('empty').hidden = main.shown > 0;
  $('military-count').textContent = mil.shown;
  const spanish = lang === 'es', d = es.dynamic;
  const where = ohio ? (county ? (spanish ? fill(d.county_where, {county}) : county + ' County, Ohio') : 'Ohio') : states[state];
  let text;
  if (spanish) {
   const topic = staged ? fill(d.topic, {stage: stageName(stage)}) : '';
   text = fill(main.shown === 1 ? d.showing_one : d.showing_many, {n: main.shown, topic, where});
   if (needs.length) {
    const names = needs.map(needShort).join(d.or);
    text += main.specific ? fill(d.need_match, {k: main.specific, names}) : fill(d.need_none, {names});
   }
  } else {
   const topic = staged ? ' for ' + stageLabel.get(stage).toLowerCase() : '';
   text = main.shown + (main.shown === 1 ? ' program' : ' programs') + topic + ' in ' + where + '.';
   if (needs.length) {
    const names = needs.map(needShort).join(' or ');
    text += main.specific ? ' ' + main.specific + ' made for ' + names + ' are at the top; the rest help with any disability.' : ' None are only for ' + names + ', so these help with any disability.';
   }
  }
  $('result-status').textContent = text;
  $('show-all-wrap').hidden = !main.held;
  $('show-all').textContent = spanish ? fill(d.show_all, {n: main.shown}) : 'Show all ' + main.shown + ' programs';
  $('print-context').textContent = where + (staged ? ' · ' + stageLabel.get(stage) : '') + (needs.length ? ' · ' + needs.map(n => needName.get(n)).join(', ') : '');
  renderAnchors(state, county);
  $('cvso-link').href = 'https://guide.vethomeguard.org/?state=' + state + (ohio && county ? '&county=' + encodeURIComponent(county) : '');
  $('back-guide').href = 'ohio/index.html';
  updateReports(state);
  if (write) writeParams(state, county, needs);
 }

 function renderAgencies() {
  const list = $('pa-list');
  Object.entries(states).forEach(([code, name]) => {
   const a = pa[code], li = el('li');
   li.append(el('strong', {}, name + ': '), link(a.url, a.name), ' · ', link(tel(a.phone), a.phone));
   list.append(li);
  });
 }

 // After a choice, bring the first calls and the list into view and move focus there, so the change is seen and heard.
 function reveal() {
  const r = $('results');
  if (r.scrollIntoView) r.scrollIntoView({behavior: reduceMotion ? 'auto' : 'smooth', block: 'start'});
  if (r.focus) r.focus({preventScroll: true});
 }
 // A link that names a row, or something inside one, opens it. A link to one listing shows the list and opens that listing.
 function openNamed() {
  let id = '';
  try { id = decodeURIComponent(location.hash.slice(1)); } catch { return; }
  const target = id && $(id);
  if (!target) return;
  const listing = target.classList.contains('resource');
  if (listing) { if (!stage) stage = 'all'; showAll = true; apply(false); }
  for (let n = target; n; n = n.parentElement) if (n.tagName === 'DETAILS') n.open = true;
  if (listing) { const more = target.querySelector('details.more'); if (more) more.open = true; }
  if (target.scrollIntoView) target.scrollIntoView();
 }
 // The first choice can also be a county or a need: that shows the list too.
 function firstChoice() { if (stage) return false; stage = 'all'; return true; }

 document.querySelectorAll('.stage').forEach(b => b.addEventListener('click', () => { stage = b.dataset.stage; showAll = false; apply(); reveal(); }));
 document.querySelectorAll('.quick-btn').forEach(b => b.addEventListener('click', () => { stage = b.dataset.quick; showAll = false; apply(); reveal(); }));
 $('show-all').addEventListener('click', () => {
  showAll = true; apply();
  // Focus goes to the first listing that was just added, so a keyboard or screen reader user carries on from there.
  const next = [...document.querySelectorAll('#cards .resource:not([hidden])')][CAP];
  const stop = next && next.querySelector('a, summary');
  if (stop) stop.focus();
 });
 $('letter-text').addEventListener('input', () => { letterEdited = true; });
 $('letter-copy').addEventListener('click', async () => {
  const spanish = lang === 'es', box = $('letter-text');
  try { await navigator.clipboard.writeText(box.value); $('letter-status').textContent = spanish ? es.dynamic.letter_copied : 'Letter copied. Fill in the brackets before you send it.'; }
  catch { box.focus(); box.select(); $('letter-status').textContent = spanish ? es.dynamic.letter_select : 'Select the letter text and copy it.'; }
 });
 $('state').addEventListener('change', () => apply());
 $('county').addEventListener('change', () => { const first = $('county').value && firstChoice(); apply(); if (first) reveal(); });
 document.querySelectorAll('input[name=need]').forEach(i => i.addEventListener('change', () => { const first = i.checked && firstChoice(); showAll = false; apply(); if (first) reveal(); }));
 window.addEventListener('hashchange', openNamed);
 // "Leave this site" replaces this page in the browser's history, so Back does not return here.
 document.querySelectorAll('[data-exit]').forEach(a => a.addEventListener('click', e => { e.preventDefault(); location.replace(a.href); }));
 $('print').addEventListener('click', () => window.print());
 // A printed list shows each listing in full, then the page goes back to how it was.
 window.addEventListener('beforeprint', () => {
  document.querySelectorAll('#results .resource:not([hidden]) details.more:not([open]), #good-to-know:not([open])').forEach(d => { d.setAttribute('data-print-opened', ''); d.open = true; });
 });
 window.addEventListener('afterprint', () => {
  document.querySelectorAll('details[data-print-opened]').forEach(d => { d.removeAttribute('data-print-opened'); d.open = false; });
 });
 $('share').addEventListener('click', async () => {
  const url = location.href.split('#')[0];
  const spanish = lang === 'es';
  try { await navigator.clipboard.writeText(url); $('share-status').textContent = spanish ? es.dynamic.copied : 'Link copied. It includes only your state, county, stage and need choices.'; }
  catch { $('share-status').textContent = (spanish ? es.dynamic.copy_this : 'Copy this link: ') + url; }
 });
 $('lang-toggle').addEventListener('click', e => { e.preventDefault(); lang = lang === 'es' ? 'en' : 'es'; $('share-status').textContent = ''; applyLang(); apply(); });
 readParams();
 applyLang();
 renderAgencies();
 apply(false);
 openNamed();
})();
