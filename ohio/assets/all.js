// OhioMom "All resources": every listing in one place, with a search box, a county and a need.
// The list is put together in the visitor's browser from the other pages of this site, so it cannot
// fall out of step with them. Nothing typed here is sent anywhere.
(function () {
  'use strict';
  var root = document.querySelector('[data-directory]');
  if (!root || !window.fetch || !window.DOMParser || !window.Promise) { return; }
  var tools = root.querySelector('[data-directory-tools]');
  var list = root.querySelector('[data-directory-list]');
  var status = root.querySelector('[data-directory-status]');
  var search = document.getElementById('find');
  var pick = document.getElementById('county');
  var town = document.getElementById('town');
  var townNote = document.getElementById('townnote');
  var chips = root.querySelector('[data-need-chips]');
  var countLine = document.getElementById('found');
  var note = root.querySelector('[data-directory-note]');

  // The pages that hold listings, in the order they are read. When two pages carry the same listing, the
  // first one read is the one shown. The second part is the need a listing gets when its row does not say.
  var SOURCES = [
    ['help/bills.html', 'food'], ['help/pregnancy-baby.html', 'baby'], ['help/single-parent.html', 'parent'], ['help/kinship.html', 'parent'],
    ['wellbeing.html', 'care'], ['help/housing.html', 'housing'], ['holidays.html', 'holiday'], ['help/family-inside.html', 'inside'], ['../family-guide.html', 'kids'], ['../states/oh.html', '']
  ];
  var NEEDS = [
    ['housing', 'Housing and shelter'], ['safety', 'Safety and crisis lines'], ['food', 'Food and bills'],
    ['baby', 'Pregnancy and new baby'], ['kids', 'My child learns or grows differently'], ['parent', 'Parenting on my own'],
    ['care', 'Take care of me'], ['military', 'Military and veteran families'], ['inside', 'A loved one in jail or prison'], ['holiday', 'Holiday help'], ['groups', 'Meet other moms']
  ];
  // The need for each row and section name used on the pages above and on the county pages.
  var NEED_OF = {
    'help-now': 'safety', safe: 'safety', safety: 'safety housing', 'children-services': 'safety',
    housing: 'housing', 'housing-bills': 'food', 'food-bills': 'food', benefits: 'food', bills: 'food', 'local-help': 'care food',
    'pregnancy-baby': 'baby', health: 'baby', early: 'baby kids',
    'kids-differently': 'kids', disability: 'kids', dd: 'kids', fcfc: 'kids',
    'single-parent': 'parent', 'child-support': 'parent', legal: 'parent housing',
    'take-care': 'care', wellbeing: 'care', military: 'military', holiday: 'holiday', inside: 'inside'
  };
  // The Ohio page of the national site repeats these in a general form. OhioMom has its own, fuller listing for each.
  var OHIO_HAS_ITS_OWN = ['oh-snap', 'oh-wic', 'oh-energy', 'oh-211', 'oh-coverage', 'oh-health-centers', 'oh-diapers',
    'oh-childcare', 'oh-legal', 'oh-dv'];
  var HOUSING = /(^|[^a-z])(shelter|homeless|housing|rent|evict)/i;
  // Everyday words for the words the listings use.
  var ALSO = {
    homeless: ['shelter'], homelessness: ['shelter'], apartment: ['rent', 'rental', 'housing'], apartments: ['rent', 'rental', 'housing'],
    evicted: ['eviction'], evict: ['eviction'], landlord: ['eviction', 'renter', 'tenant'], voucher: ['vouchers'],
    daycare: ['child care'], childcare: ['child care'], babysitter: ['child care'], preschool: ['head start'],
    stamps: ['snap', 'food assistance'], ebt: ['snap', 'food assistance'], groceries: ['snap', 'food'], pantry: ['pantry', 'food bank'],
    formula: ['wic', 'breastfeeding'], abuse: ['domestic violence'], abused: ['domestic violence'], violence: ['domestic violence'],
    dv: ['domestic violence'], lawyer: ['legal'], attorney: ['legal'], divorce: ['legal'], custody: ['legal'],
    depressed: ['depression', 'mental health'], anxious: ['anxiety', 'mental health'], therapy: ['mental health', 'counseling'],
    suicide: ['988'], electric: ['energy', 'heating', 'utility'], gas: ['energy', 'heating'], heat: ['heating', 'energy'],
    utilities: ['utility', 'energy', 'heating'], insurance: ['coverage', 'medicaid'], doctor: ['health center', 'prenatal'],
    pregnant: ['pregnancy', 'prenatal'], nursing: ['breastfeeding'], iep: ['school'], veteran: ['veterans'], vet: ['veterans'],
    jail: ['jail', 'prison'], prison: ['prison', 'jail'], inmate: ['prison', 'jail'], incarcerated: ['prison', 'jail'], visitation: ['visit'], reentry: ['re-entry', 'release']
  };

  var items = [];      // { el, name, text, needs, counties, region, at }
  var byName = {};     // every listing taken so far, by name
  var data = null;     // assets/data.json: counties, regions, groups
  var places = null;   // assets/places.json, once it has loaded
  var need = '';
  var county = '';
  var missed = 0;

  function each(listLike, fn) { Array.prototype.forEach.call(listLike, fn); }
  function clean(text) { return text.replace(/\s+/g, ' ').trim(); }
  function words(text) { return ' ' + text.toLowerCase().replace(/[^a-z0-9]+/g, ' '); }
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) { e.className = cls; }
    if (text) { e.textContent = text; }
    return e;
  }
  function labelOf(id) {
    for (var i = 0; i < NEEDS.length; i++) { if (NEEDS[i][0] === id) { return NEEDS[i][1]; } }
    return '';
  }

  // ---- gathering -------------------------------------------------------------------------------------------

  function add(card, needs, place, region) {
    var name = clean(card.querySelector('h3').textContent);
    var twin = byName[name.toLowerCase()];
    if (twin) {
      // The same listing on a second page: keep the first, and let it answer to every need and county.
      needs.forEach(function (n) { if (twin.needs.indexOf(n) < 0) { twin.needs.push(n); } });
      if (place && twin.counties.length && twin.counties.indexOf(place) < 0) { twin.counties.push(place); }
      return;
    }
    var node = document.importNode(card, true);
    node.className = 'card';
    node.removeAttribute('id');
    node.hidden = false;
    each(node.querySelectorAll('[id]'), function (n) { n.removeAttribute('id'); });
    each(node.querySelectorAll('details'), function (d) { d.open = false; });
    // The family guide opens links in a new tab and adds a "report a problem" line. Here every card behaves alike.
    each(node.querySelectorAll('a[target]'), function (a) { a.removeAttribute('target'); });
    each(node.querySelectorAll('a .sr'), function (s) { if (/new tab/.test(s.textContent)) { s.parentNode.removeChild(s); } });
    each(node.querySelectorAll('a.report'), function (a) { a.parentNode.parentNode.removeChild(a.parentNode); });
    var short = node.querySelector('.short');
    if (needs.indexOf('housing') < 0) {
      // A local office named for shelter or housing is a housing listing first. One that only mentions it is one too, second.
      if (place && HOUSING.test(name)) { needs.unshift('housing'); } else if (HOUSING.test(name + ' ' + (short ? short.textContent : ''))) { needs.push('housing'); }
    }
    var item = { el: node, name: name, needs: needs, counties: place ? [place] : [], region: region || '', at: items.length };
    byName[name.toLowerCase()] = item;
    items.push(item);
  }

  function take(doc, base, fallback, always, place) {
    var cards = Array.prototype.slice.call(doc.querySelectorAll('article.card'));
    // The family guide lists national programs before Ohio's. Here Ohio's own come first.
    var ohioFirst = cards.filter(function (c) { return c.getAttribute('data-scope') === 'OH'; })
      .concat(cards.filter(function (c) { return c.getAttribute('data-scope') !== 'OH'; }));
    ohioFirst.forEach(function (card) {
      if (!card.querySelector('h3')) { return; }
      var id = (card.id || '').split('--').pop();
      if (OHIO_HAS_ITS_OWN.indexOf(id) >= 0) { return; }
      // The family guide marks the national listings that Ohio has its own version of.
      if (/(^|\s)OH:/.test(card.getAttribute('data-replaced') || '')) { return; }
      var row = card.closest('details.need');
      var named = ((NEED_OF[card.getAttribute('data-section') || ''] || '') + ' ' + ((row && NEED_OF[row.id]) || '')).split(' ');
      var needs = [];
      named.concat(always ? [always] : []).forEach(function (n) { if (n && needs.indexOf(n) < 0) { needs.push(n); } });
      if (!needs.length) { needs.push(fallback || 'food'); }
      // A county page that has no local office for a row shows the statewide one. That one is not local.
      var local = place && !(row && row.querySelector('.pending')) ? place : '';
      each(card.querySelectorAll('a[href]'), function (a) { a.setAttribute('href', new URL(a.getAttribute('href'), base).href); });
      add(card, needs, local, '');
    });
  }

  function page(path) {
    var url = new URL(path, document.baseURI).href;
    return fetch(url).then(function (r) {
      if (!r.ok) { throw new Error(path); }
      return r.text();
    }).then(function (html) {
      return { doc: new DOMParser().parseFromString(html, 'text/html'), base: url };
    }).catch(function () { missed += 1; return null; });
  }

  // The first sentence of a description is the one line a card shows.
  function firstSentence(text) {
    var re = /[.!?]["\u201d)]?\s+/g;
    var m;
    while ((m = re.exec(text))) {
      var end = m.index + m[0].length;
      var head = text.slice(0, end).replace(/\s+$/, '');
      if (/(U\.S\.|a\.m\.|p\.m\.|e\.g\.|i\.e\.|St\.|Dr\.|Mr\.|Mrs\.|Ms\.|vs\.|No\.|Inc\.)$/.test(head)) { continue; }
      var next = text.slice(end, end + 1);
      if (next && ((next !== next.toLowerCase() && next === next.toUpperCase()) || /[0-9"\u201c(]/.test(next))) {
        return [head, text.slice(end).trim()];
      }
    }
    return [text.trim(), ''];
  }

  function longDate(iso) {
    var months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
    var d = String(iso || '').split('-');
    return d.length === 3 ? months[+d[1] - 1] + ' ' + (+d[2]) + ', ' + d[0] : String(iso || '');
  }

  // A moms group from assets/data.json, in the same shape as every other card.
  function groupCard(g) {
    var card = el('article', 'card');
    var parts = firstSentence(String(g.what || ''));
    card.appendChild(el('h3', '', g.name));
    card.appendChild(el('p', 'short', parts[0]));
    var acts = el('p', 'actions');
    if (g.phone) {
      var call = el('a', 'btn call', 'Call ' + g.phone);
      call.href = 'tel:' + g.phone.replace(/\D/g, '');
      acts.appendChild(call);
      if (g.phone_label) { acts.appendChild(el('span', 'note', g.phone_label)); }
    }
    var site = el('a', 'btn', 'Website');
    site.href = g.url;
    site.rel = 'noopener noreferrer';
    acts.appendChild(site);
    card.appendChild(acts);
    var more = el('details', 'more');
    var sum = el('summary', '', 'More about this');
    sum.appendChild(el('span', 'sr', ': ' + g.name));
    more.appendChild(sum);
    if (parts[1]) { more.appendChild(el('p', '', parts[1])); }
    var how = el('p');
    how.appendChild(el('strong', '', 'Next step:'));
    how.appendChild(document.createTextNode(' ' + g.how));
    more.appendChild(how);
    more.appendChild(el('p', 'meta', 'Checked against published sources ' + longDate(g.checked)));
    card.appendChild(more);
    return card;
  }

  // ---- places ----------------------------------------------------------------------------------------------

  // "Mt. Gilead", "mount gilead" and "MOUNT GILEAD" are one place. So are "Mc Arthur" and "McArthur".
  function placeKey(text) {
    return (' ' + text.toLowerCase() + ' ').replace(/,?\s+(oh|ohio)\s*$/, ' ')
      .replace(/ mt\.? /g, ' mount ').replace(/ st\.? /g, ' saint ').replace(/ ft\.? /g, ' fort ')
      .replace(/[^a-z0-9]+/g, '');
  }
  function shown(name) { return name.replace(/\bMc (\w)/g, 'Mc$1'); }

  function readPlaces(raw) {
    var zips = {};
    var towns = {};
    function town(name, c, n) {
      var k = placeKey(name);
      towns[k] = towns[k] || { name: shown(name), counties: {} };
      towns[k].counties[c] = (towns[k].counties[c] || 0) + n;
    }
    Object.keys(raw.counties).forEach(function (c) {
      raw.counties[c].split('|').forEach(function (entry) {
        var codes = entry.match(/\b\d{5}\b/g) || [];
        var name = clean(entry.replace(/\b\d{5}\b/g, ''));
        codes.forEach(function (z) { zips[z] = { town: shown(name), county: c, also: (raw.reaches[z] || '').split('|').filter(Boolean) }; });
        town(name, c, codes.length);
      });
    });
    // County seats and the larger cities that share a post office name with a neighbor.
    Object.keys(data.counties).forEach(function (c) { if (!towns[placeKey(data.counties[c][1])]) { town(data.counties[c][1], c, 1); } });
    Object.keys(data.cities || {}).forEach(function (name) { if (!towns[placeKey(name)]) { town(name, data.cities[name], 1); } });
    return { zips: zips, towns: towns };
  }

  function countyNamed(text) {
    var k = placeKey(text.replace(/\s+(county|co\.?)\s*$/i, ''));
    var found = '';
    Object.keys(data.counties).forEach(function (c) { if (placeKey(c) === k) { found = c; } });
    return found;
  }

  // What the town box holds. null while there is nothing to say yet; otherwise
  // { ok, lead, zip, counties: [the county shown, then others it reaches], meant: a county of the same name }.
  function locate(typed) {
    var text = clean(typed);
    if (!text) { return null; }
    if (/\s(county|co\.?)$/i.test(text)) {
      return countyNamed(text) ? { ok: true, lead: '', counties: [countyNamed(text)], meant: '' }
        : { ok: false, lead: 'Ohio has no county by that name. Pick your county from the list.' };
    }
    var digits = text.replace(/[\s-]/g, '');
    if (/^\d+$/.test(digits)) {
      if (!/^\d{5}(\d{4})?$/.test(digits) || !places) { return null; }
      var code = digits.slice(0, 5);
      var z = places.zips[code];
      if (!z) { return { ok: false, lead: 'We do not have ZIP code ' + code + ' on our Ohio list. Pick your county instead.' }; }
      return { ok: true, zip: true, lead: code + ' (' + z.town + ')', counties: [z.county].concat(z.also), meant: '' };
    }
    if (!places || text.length < 3) { return null; }
    var t = places.towns[placeKey(text)];
    var asCounty = countyNamed(text);
    if (!t) {
      if (asCounty) { return { ok: true, lead: '', counties: [asCounty], meant: '' }; }
      return { ok: false, lead: 'We do not have \u201c' + text + '\u201d on our list of Ohio towns. Try your ZIP code, or pick your county.' };
    }
    var ranked = Object.keys(t.counties).sort(function (a, b) { return t.counties[b] - t.counties[a] || (a < b ? -1 : 1); });
    return { ok: true, lead: t.name, counties: ranked, meant: asCounty && ranked.indexOf(asCounty) < 0 ? asCounty : '' };
  }

  // Says where the place is, and offers the other counties it could be as buttons.
  function sayPlace(found, final) {
    while (townNote.firstChild) { townNote.removeChild(townNote.firstChild); }
    if (!found || (!found.ok && !final)) { return; }
    function say(text) { townNote.appendChild(document.createTextNode(text)); }
    function offer(c) {
      var b = el('button', 'linkbtn', c + ' County');
      b.type = 'button';
      b.setAttribute('data-county', c);
      townNote.appendChild(b);
    }
    if (!found.ok) { say(found.lead); return; }
    var others = found.counties.slice(1);
    say(found.lead ? found.lead + ' is in ' + found.counties[0] + ' County.' : 'Showing ' + found.counties[0] + ' County.');
    if (others.length > 3) {
      say(' It reaches into other counties too. If this is not yours, pick your county from the list.');
    } else if (others.length) {
      say(found.zip ? ' This ZIP code also reaches into ' : ' Part of it is in ');
      others.forEach(function (c, i) {
        if (i) { say(i === others.length - 1 ? ' and ' : ', '); }
        offer(c);
      });
      say(others.length === 1 ? '. Choose it if that is yours.' : '. Choose yours if it is one of these.');
    }
    if (found.meant) {
      say(' If you meant ');
      offer(found.meant);
      say(', choose it here.');
    }
  }

  function setCounty(name, remember) {
    county = data.counties[name] ? name : '';
    pick.value = county;
    if (county && remember) {
      // The same "your area" the rest of OhioMom uses. It stays in this browser.
      try { window.localStorage.setItem('om.area', JSON.stringify({ r: data.counties[county][0], c: county })); } catch (e) { /* private mode */ }
      var chip = document.querySelector('[data-area-chip]');
      if (chip) { chip.textContent = '\ud83d\udccd ' + county + ' County'; }
    }
  }

  // Runs as she types and again when she leaves the box. Leaving the box must not undo a county she has
  // just chosen from the note under it, so a place that has already been answered is left alone.
  var answered = null;
  function placeTyped(final) {
    var text = clean(town.value);
    if (text === answered) { return; }
    var found = locate(text);
    if (found && found.ok) { setCounty(found.counties[0], true); }
    if (found && (found.ok || final)) { answered = text; } else { answered = null; }
    sayPlace(found, final);
    show();
  }

  // ---- showing ---------------------------------------------------------------------------------------------

  function matches(text, term) {
    var tries = [term].concat(ALSO[term] || []);
    if (term.length > 3 && term.slice(-1) === 's') { tries.push(term.slice(0, -1)); }
    return tries.some(function (word) { return text.indexOf(' ' + word) !== -1; });
  }

  function show() {
    var terms = search.value.toLowerCase().split(/[^a-z0-9]+/).filter(function (t) { return t.length > 1 || /\d/.test(t); });
    var region = county ? data.counties[county][0] : '';
    var groups = {};
    var total = 0;
    items.forEach(function (it) {
      var ok = (!need || it.needs.indexOf(need) >= 0)
        && (!county || !it.counties.length || it.counties.indexOf(county) >= 0)
        && (!county || !it.region || it.region === 'all' || it.region === region)
        && terms.every(function (t) { return matches(it.text, t); });
      if (!ok) { return; }
      total += 1;
      var mine = county && (it.counties.indexOf(county) >= 0 || it.region === region);
      // With a county chosen its own offices come first; otherwise statewide help comes before local offices.
      it.rank = mine ? 0 : (it.counties.length || (it.region && it.region !== 'all') ? 2 : 1);
      var g = need || it.needs[0];
      (groups[g] = groups[g] || []).push(it);
    });
    while (list.firstChild) { list.removeChild(list.firstChild); }
    NEEDS.forEach(function (n) {
      var found = groups[n[0]];
      if (!found) { return; }
      // Local offices for the chosen county, then the listings this need is the main purpose of, then the rest.
      found.sort(function (a, b) {
        return a.rank - b.rank || (a.needs[0] === n[0] ? 0 : 1) - (b.needs[0] === n[0] ? 0 : 1)
          || (a.counties[0] || '').localeCompare(b.counties[0] || '') || a.at - b.at;
      });
      var section = el('section', 'dirgroup');
      var h = el('h2', '', n[1]);
      h.appendChild(el('span', 'ncount', found.length + (found.length === 1 ? ' listing' : ' listings')));
      section.appendChild(h);
      var cards = el('div', 'cards');
      found.forEach(function (it) { cards.appendChild(it.el); });
      section.appendChild(cards);
      list.appendChild(section);
    });
    var narrowed = need || county || terms.length;
    countLine.textContent = (narrowed ? 'Showing ' + total + ' of ' + items.length : items.length) + ' listings'
      + (county ? ' for ' + county + ' County and all of Ohio.' : '.');
    while (note.firstChild) { note.removeChild(note.firstChild); }
    if (!total) {
      note.textContent = 'Nothing matches. Try another word or a different need, or dial 211 and say what you need.';
    } else if (county && !items.some(function (it) { return it.counties.indexOf(county) >= 0; })) {
      note.textContent = 'We have not added local offices for ' + county + ' County yet. Everything shown here works statewide. For local help, dial 211 and give your county.';
    } else if (county && data.counties[county][2] && !need && !terms.length) {
      note.appendChild(document.createTextNode(county + ' County also has its own page: '));
      var link = el('a', '', 'open the ' + county + ' County page');
      link.href = data.counties[county][2];
      note.appendChild(link);
      note.appendChild(document.createTextNode('.'));
    }
    note.hidden = !note.firstChild;
    each(chips.querySelectorAll('button'), function (b) { b.setAttribute('aria-pressed', String(b.getAttribute('data-need') === need)); });
  }

  function fromAddress() {
    var hash = window.location.hash.slice(1);
    try { hash = decodeURIComponent(hash); } catch (e) { /* leave it as typed */ }
    hash.split('&').forEach(function (part) {
      var cut = part.indexOf('=');
      if (cut < 0) { return; }
      var k = part.slice(0, cut);
      var v = part.slice(cut + 1).replace(/\+/g, ' ');
      if (k === 'need') { need = labelOf(v) ? v : ''; }
      if (k === 'q') { search.value = v; }
      if (k === 'county' && countyNamed(v)) { setCounty(countyNamed(v), false); }
    });
  }

  function build() {
    // What a search can find: the card's own words, its needs and its counties.
    items.forEach(function (it) {
      if (it.counties.length || it.region) {
        var tags = el('p', 'tags');
        it.counties.forEach(function (c) { tags.appendChild(el('span', 'tag', c + ' County')); });
        if (it.region) {
          var r = data.regions.filter(function (x) { return x.id === it.region; })[0];
          tags.appendChild(el('span', 'tag', r ? r.label : 'All of Ohio'));
        }
        it.el.insertBefore(tags, it.el.firstChild);
      }
      it.text = words(it.el.textContent + ' ' + it.needs.map(labelOf).join(' '));
    });
    [['', 'Everything']].concat(NEEDS).forEach(function (n) {
      if (n[0] && !items.some(function (it) { return it.needs.indexOf(n[0]) >= 0; })) { return; }
      var b = el('button', '', n[1]);
      b.type = 'button';
      b.setAttribute('data-need', n[0]);
      chips.appendChild(b);
    });
    Object.keys(data.counties).sort().forEach(function (c) {
      var o = el('option', '', c + ' County');
      o.value = c;
      pick.appendChild(o);
    });
    // The area already chosen elsewhere on OhioMom is where the list starts.
    try {
      var saved = JSON.parse(window.localStorage.getItem('om.area') || 'null');
      if (saved && saved.c && data.counties[saved.c]) { setCounty(saved.c, false); }
    } catch (e) { /* nothing saved */ }
    fromAddress();
    chips.addEventListener('click', function (e) {
      var b = e.target.closest && e.target.closest('button');
      if (!b) { return; }
      need = b.getAttribute('data-need');
      // The need goes in the address so the view can be shared. What is typed never does.
      if (window.history && window.history.replaceState) {
        window.history.replaceState(null, '', need ? '#need=' + need : window.location.pathname + window.location.search);
      }
      show();
    });
    search.addEventListener('input', show);
    pick.addEventListener('change', function () {
      if (pick.value) { setCounty(pick.value, true); } else { county = ''; }
      town.value = '';
      answered = null;
      sayPlace(null);
      show();
    });
    town.addEventListener('input', function () { placeTyped(false); });
    town.addEventListener('change', function () { placeTyped(true); });
    townNote.addEventListener('click', function (e) {
      var b = e.target.closest && e.target.closest('button[data-county]');
      if (!b) { return; }
      setCounty(b.getAttribute('data-county'), true);
      sayPlace({ ok: true, lead: '', counties: [county], meant: '' }, true);
      show();
      pick.focus();
    });
    window.addEventListener('hashchange', function () { fromAddress(); show(); });
    var index = root.querySelector('[data-directory-index]');
    if (index) { index.hidden = true; }
    status.textContent = missed ? 'Some listings did not load. Refresh the page to try again.' : '';
    status.hidden = !missed;
    tools.hidden = false;
    show();
    fetch(new URL('assets/places.json', document.baseURI).href).then(function (r) { return r.json(); }).then(function (raw) {
      places = readPlaces(raw);
      if (town.value) { placeTyped(false); }
    }).catch(function () {
      town.disabled = true;
      town.placeholder = 'Pick your county from the list';
    });
  }

  status.hidden = false;
  status.textContent = 'Loading every listing\u2026';
  var jobs = SOURCES.map(function (s) { return page(s[0]); });
  var json = fetch(new URL('assets/data.json', document.baseURI).href).then(function (r) { return r.json(); }).catch(function () { return null; });
  Promise.all([json].concat(jobs)).then(function (got) {
    data = got[0];
    if (!data) { throw new Error('data'); }
    var pages = got.slice(1);
    // County pages are named in the data file. A county page that fails to load leaves its county without local offices.
    var named = Object.keys(data.counties).filter(function (c) { return data.counties[c][2]; });
    return Promise.all(named.map(function (c) { return page(data.counties[c][2]); })).then(function (countyPages) {
      pages.forEach(function (p, i) {
        if (p) { take(p.doc, p.base, SOURCES[i][1], SOURCES[i][0] === '../family-guide.html' ? 'kids' : '', ''); }
      });
      countyPages.forEach(function (p, i) { if (p) { take(p.doc, p.base, 'food', '', named[i]); } });
      (data.groups || []).forEach(function (g) { add(groupCard(g), ['groups'], '', g.region || 'all'); });
      if (!items.length) { throw new Error('empty'); }
      build();
    });
  }).catch(function () {
    status.hidden = false;
    status.textContent = 'The full list did not load. Refresh the page, or use the links below.';
  });
})();
