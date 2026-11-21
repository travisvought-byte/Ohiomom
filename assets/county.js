// Yoga Mom Talk: county pages. Reads one state's list from this site and builds the page in your browser.
// Only files from this site are fetched. No third parties, no storage, no tracking. Nothing typed here is saved.
(function () {
  'use strict';
  var app = document.getElementById('county-app');
  var picker = document.querySelector('[data-county-find]');
  var stateSel = document.getElementById('cstate');
  var countySel = document.getElementById('ccounty');
  var zipBox = document.getElementById('zip');
  var msg = document.getElementById('cmsg');
  var title = document.getElementById('ctitle');
  var lede = document.getElementById('clede');
  if (!app || !picker || !stateSel || !countySel || !zipBox || !window.fetch || !window.Promise) { return; }

  var DATA = 'assets/us/';
  var MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  var STAGE = 6;        // cards shown before "Show more"
  var SHOW_ALL = 8;     // a list this short is shown whole
  var CAP = 60;         // most cards drawn at once, so a very large county stays quick on a phone
  var HOME_TITLE = title.textContent;
  var HOME_LEDE = lede.textContent;
  var HOME_DOC = document.title;
  var STATES = {};      // 'oh': {name: 'Ohio', fips: '39'}
  var BY_FIPS = {};     // '39': 'oh'
  Array.prototype.forEach.call(stateSel.options, function (o) {
    if (o.value) { STATES[o.value] = { name: o.textContent, fips: o.getAttribute('data-fips') }; BY_FIPS[o.getAttribute('data-fips')] = o.value; }
  });
  var shards = {};
  var zips = {};
  var turn = 0;         // a later choice cancels the page an earlier one was still loading

  // ---- small helpers. Text is always put in with textContent, never as markup.
  function h(tag, props, kids) {
    var node = document.createElement(tag);
    Object.keys(props || {}).forEach(function (k) {
      if (k === 'text') { node.textContent = props[k]; } else { node.setAttribute(k, props[k]); }
    });
    (kids || []).forEach(function (kid) {
      if (kid) { node.appendChild(typeof kid === 'string' ? document.createTextNode(kid) : kid); }
    });
    return node;
  }
  function pretty(iso) {
    var p = String(iso).split('-');
    return MONTHS[Number(p[1]) - 1] + ' ' + Number(p[2]) + ', ' + p[0];
  }
  function count(n, one, many) { return n + ' ' + (n === 1 ? one : many); }
  function safeUrl(u) { return /^https?:\/\/[^\s"'<>]+$/.test(u || '') ? u : ''; }
  function telHref(p) { return 'tel:+1' + String(p).replace(/\D/g, ''); }
  function fetchJson(url) {
    return fetch(url, { credentials: 'omit', referrerPolicy: 'no-referrer' }).then(function (r) {
      if (!r.ok) { throw new Error('HTTP ' + r.status); }
      return r.json();
    });
  }
  function loadShard(st) {
    if (!shards[st]) { shards[st] = fetchJson(DATA + st + '.json'); }
    return shards[st].catch(function (e) { delete shards[st]; throw e; });
  }
  var xmas = null;
  function loadXmas() {
    if (!xmas) { xmas = fetchJson(DATA + 'christmas.json'); }
    return xmas.catch(function (e) { xmas = null; throw e; });
  }
  function loadZips(d) {
    if (!zips[d]) { zips[d] = fetchJson(DATA + 'z' + d + '.json'); }
    return zips[d].catch(function (e) { delete zips[d]; throw e; });
  }
  function say(text) { msg.textContent = text; }
  function sourceLinks(key) {
    var out = [];
    Array.prototype.forEach.call(document.querySelectorAll('a[data-src="' + key + '"]'), function (a, i) {
      out.push(h('a', { href: a.getAttribute('href'), rel: 'noopener', text: String(i + 1) }));
    });
    return out;
  }
  function sourceLine(key, asof) {
    var p = h('p', { 'class': 'src' }, ['Federal data as of ' + pretty(asof) + ', not confirmed by phone. Sources: ']);
    sourceLinks(key).forEach(function (a, i) { if (i) { p.appendChild(document.createTextNode(' ')); } p.appendChild(a); });
    return p;
  }

  // ---- cards. These have the same parts as every other card on the site.
  function card(id, name, short, phone, web, more) {
    var acts = h('p', { 'class': 'actions' }, [h('a', { 'class': 'btn call', href: telHref(phone), text: 'Call ' + phone })]);
    if (safeUrl(web)) { acts.appendChild(h('a', { 'class': 'btn', href: web, rel: 'noopener', text: 'Website' })); }
    var details = h('details', { 'class': 'more' }, [h('summary', { text: 'More about this' }, [h('span', { 'class': 'sr', text: ': ' + name })])].concat(more));
    return h('article', { 'class': 'card', id: id }, [h('h3', { text: name }), h('p', { 'class': 'short', text: short }), acts, details]);
  }
  // Toys for Tots campaign: [website subdomain, name, state]
  function tftCard(i, t, here, ctx) {
    var web = safeUrl(String(ctx.site || '').replace('{}', t[0]));
    var short = (here ? 'Named for ' + ctx.county + ', or with its address there. ' : 'Toys for Tots campaign in ' + t[1] + ', ' + t[2] + '. ')
      + 'New toys for children whose families cannot afford Christmas gifts.';
    var more = [h('p', { 'class': 'org', text: 'Marine Toys for Tots' }),
      h('p', { text: 'The campaign\'s website says which towns it serves, its dates, and whether it takes requests from families or only through local charities and agencies.' }),
      h('p', {}, [h('strong', { text: 'Next step:' }), ' Open the website and its Request a Toy page. If requests have closed, use its Contact page and ask which local groups are giving out its toys.']),
      h('p', { 'class': 'src' }, ['From Toys for Tots\' list of local campaigns, checked ' + pretty(ctx.xasof) + '. Sources: ',
        h('a', { href: safeUrl(ctx.source) || 'christmas.html', rel: 'noopener', text: '1' })])];
    var acts = h('p', { 'class': 'actions' }, web ? [h('a', { 'class': 'btn', href: web, rel: 'noopener', text: 'Campaign website' })] : []);
    var details = h('details', { 'class': 'more' }, [h('summary', { text: 'More about this' }, [h('span', { 'class': 'sr', text: ': Toys for Tots: ' + t[1] })])].concat(more));
    return h('article', { 'class': 'card', id: 'tft-' + i }, [h('h3', { text: 'Toys for Tots: ' + t[1] }), h('p', { 'class': 'short', text: short }), acts, details]);
  }
  function christmasRow(x, fips, code, c, stName) {
    var ctx = { county: c.n, xasof: x.asof, site: x.site, source: x.source };
    var here = (x.c[fips] || []).filter(function (i) { return x.t[i]; });
    var rest = (x.st[code.toUpperCase()] || []).filter(function (i) { return here.indexOf(i) === -1; });
    var items = here.map(function (i) { return [i, true]; }).concat(rest.map(function (i) { return [i, false]; }));
    var intro = h('p', { 'class': 'quiet' }, [here.length ? 'Toys for Tots campaigns for ' + c.n + ' come first, then every campaign in ' + stName + '. '
      : 'No Toys for Tots campaign is named for ' + c.n + ' or has its address there, so here is every campaign in ' + stName + '. Each one\'s website says which towns it serves. ',
      'Sign-ups close early. If one has closed, dial ', h('a', { href: 'tel:211', text: '211' }), ' and ask what Christmas help is still open. ',
      h('a', { href: 'states/' + code + '.html#christmas', text: 'More Christmas help in ' + stName }), ' · ', h('a', { href: 'christmas.html', text: 'Christmas help everywhere' })]);
    return row('county-christmas', '🎄', 'Christmas help',
      here.length ? 'Toys for Tots for ' + c.n + ', and Christmas help across ' + stName : 'Toys for Tots campaigns in ' + stName + ', and more Christmas help',
      items.length, ['campaign', 'campaigns'],
      h('div', {}, [intro, items.length ? cardList(items, function (it) { return tftCard(it[0], x.t[it[0]], it[1], ctx); }, function (it) { return x.t[it[0]][1].toLowerCase() + ' '; })
        : h('p', { 'class': 'quiet', text: 'No Toys for Tots campaign is listed in ' + stName + '. Dial 211 and ask what Christmas help is open near you.' })]));
  }
  function place(street, city, st, zip) { return [street, city + ', ' + st + (zip ? ' ' + zip : '')].filter(Boolean).join(', '); }
  function away(miles, county) {
    return miles ? 'About ' + count(miles, 'mile', 'miles') + ' from the middle of ' + county + '. ' : '';
  }

  // health row: [org, name, street, city, zip, phone, website, hours, seasonal, miles, state]
  function healthCard(r, i, ctx) {
    var short = away(r[9], ctx.county) + 'Low-cost health care in ' + r[3] + ', ' + r[10] + ', whether or not you have insurance. Fees are based on your income.';
    var more = [h('p', { 'class': 'org', text: 'Part of ' + r[0] }), h('p', { text: place(r[2], r[3], r[10], r[4]) })];
    if (r[7] > 0) { more.push(h('p', { text: 'Open about ' + count(r[7], 'hour', 'hours') + ' a week.' })); }
    if (r[8]) { more.push(h('p', { text: 'This site is open only part of the year, so call before you go.' })); }
    more.push(h('p', {}, [h('strong', { text: 'Next step:' }), ' Call, say you want to become a new patient, and ask about the sliding fee discount and what to bring. Ask whether they offer what you need, such as prenatal care, checkups for children or dental care.']));
    more.push(sourceLine('hrsa', ctx.asof));
    return card('hc-' + i, r[1], short, r[5], r[6], more);
  }
  // head start row: [name, org, street, city, zip, phone, kinds, miles, state]
  function headStartCard(r, i, ctx) {
    var kinds = r[6];
    var what;
    if ((kinds & 1) && (kinds & 2)) {
      what = 'Free early learning in ' + r[3] + ', ' + r[8] + ': Head Start for ages 3 to 5, and Early Head Start for babies, toddlers and pregnant moms. For families who qualify.';
    } else if (kinds & 2) {
      what = 'Free early learning for babies and toddlers, and support for pregnant moms, in ' + r[3] + ', ' + r[8] + '. For families who qualify.';
    } else {
      what = 'Free preschool in ' + r[3] + ', ' + r[8] + ' for children ages 3 to 5 in families who qualify.';
    }
    var more = [h('p', { 'class': 'org', text: r[1] }), h('p', { text: place(r[2], r[3], r[8], r[4]) })];
    var notes = [];
    if (kinds & 4) { notes.push('This program serves migrant and seasonal farmworker families.'); }
    if (kinds & 8) { notes.push('This is a tribal program (American Indian and Alaska Native Head Start). Ask who can enroll.'); }
    notes.push('Free for families who qualify. Families with a low income qualify, and so do children in foster care and families who are homeless or who get TANF or SSI.');
    more.push(h('p', { text: notes.join(' ') }));
    more.push(h('p', {}, [h('strong', { text: 'Next step:' }), ' Call and ask how to apply and what papers to bring. Programs can have waiting lists, so ask to be added even if there is no opening now.']));
    more.push(sourceLine('hs', ctx.asof));
    return card('hs-' + i, r[0], away(r[7], ctx.county) + what, r[5], '', more);
  }
  var SERVICE_WORDS = { R: 'renting', H: 'homelessness', D: 'mortgage trouble', B: 'budgeting', P: 'buying a home' };
  var METHOD_WORDS = { F: 'in person', P: 'by phone', V: 'by video', I: 'online' };
  function listWords(items) {
    if (items.length < 2) { return items.join(''); }
    return items.slice(0, -1).join(', ') + ' and ' + items[items.length - 1];
  }
  // agency: [name, street, city, zip, phone, website, services, methods, languages, state]; ref: [id, miles]
  function hudCard(ref, a, ctx) {
    var topics = 'RHDBP'.split('').filter(function (k) { return a[6].indexOf(k) !== -1; }).map(function (k) { return SERVICE_WORDS[k]; });
    var where = ref[1] ? 'About ' + count(ref[1], 'mile', 'miles') + ' away, in ' + a[2] + ', ' + a[9] + '. ' : 'In ' + ctx.county + '. ';
    var short = where + 'Free or low-cost help from a HUD-approved counselor' + (topics.length ? ' with ' + listWords(topics) : '') + '.';
    var more = [h('p', { 'class': 'org', text: 'HUD-approved housing counseling agency' }), h('p', { text: place(a[1], a[2], a[9], a[3]) })];
    var how = a[7].split('').map(function (k) { return METHOD_WORDS[k]; }).filter(Boolean);
    if (how.length) { more.push(h('p', { text: 'Counseling is offered ' + listWords(how) + '.' })); }
    if (a[8].length) { more.push(h('p', { text: 'Also helps in ' + listWords(a[8]) + '.' })); }
    more.push(h('p', {}, [h('strong', { text: 'Next step:' }), ' Call and say what is happening: rent you cannot pay, an eviction notice, a shutoff, or a mortgage you are behind on. Ask whether there is a fee.']));
    more.push(sourceLine('hud', ctx.asof));
    return card('hud-' + ref[0], a[0], short, a[4], a[5], more);
  }

  // agency: [name, street, city, zip, phone, programs, public housing homes, vouchers, state]; ref: [code, miles, how]
  var PROGRAM = {
    C: 'Public housing and Housing Choice Vouchers (Section 8).',
    S: 'Housing Choice Vouchers (Section 8), which help pay rent to a private landlord.',
    P: 'Public housing: apartments with rent based on your income.'
  };
  function thousands(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ','); }
  function phaCard(ref, a, ctx) {
    var how = ref[2];
    var short;
    if (how === 's') {
      short = 'Statewide agency, run from ' + a[2] + ', ' + a[8] + '. ' + PROGRAM[a[5]] + ' Ask whether it serves ' + ctx.county + '.';
    } else if (how === 'r') {
      short = 'About ' + count(ref[1], 'mile', 'miles') + ' away, in ' + a[2] + ', ' + a[8] + '. ' + PROGRAM[a[5]] + ' Ask whether it serves where you live.';
    } else if (how === 'n') {
      short = 'Named for ' + ctx.county + ', with its office in ' + a[2] + ', ' + a[8] + '. ' + PROGRAM[a[5]];
    } else {
      short = 'Office in ' + a[2] + ', ' + a[8] + '. ' + PROGRAM[a[5]];
    }
    var more = [h('p', { 'class': 'org', text: how === 's' ? 'State housing agency, funded by HUD' : 'Public housing agency, funded by HUD' }),
      h('p', { text: place(a[1], a[2], a[8], a[3]) })];
    var size = [];
    if (a[6] > 0) { size.push('about ' + thousands(a[6]) + ' public housing ' + (a[6] === 1 ? 'home' : 'homes')); }
    if (a[7] > 0) { size.push('about ' + thousands(a[7]) + (a[7] === 1 ? ' voucher' : ' vouchers')); }
    if (size.length) { more.push(h('p', { text: 'By HUD\'s count, ' + size.join(' and ') + '.' })); }
    more.push(h('p', {}, [h('strong', { text: 'Next step:' }), ' Call and ask whether the waiting list is open, how to apply, and whether they serve where you live. You can be on more than one agency\'s list. If you are homeless or escaping violence, ask whether that moves you up the list.']));
    more.push(sourceLine('pha', ctx.asof));
    return card('ph-' + ref[0], a[0], short, a[4], '', more);
  }
  // district: [name, street, city, zip, phone, website, state]
  function districtCard(id, miles, d, ctx) {
    var short = miles ? 'About ' + count(miles, 'mile', 'miles') + ' away, in ' + d[2] + ', ' + d[6] + '. Ask whether it serves where you live.'
      : 'Public school district with its office in ' + d[2] + ', ' + d[6] + '. Ask for the special education office.';
    var more = [h('p', { 'class': 'org', text: 'Public school district' }), h('p', { text: place(d[1], d[2], d[6], d[3]) }),
      h('p', {}, [h('strong', { text: 'Next step:' }), ' Call and ask for the special education office, or preschool special education for a child under 5. Say you would like your child evaluated, then make the same request in writing, with the date, and keep a copy.']),
      sourceLine('sd', ctx.asof)];
    return card('sd-' + id, d[0], short, d[4], d[5], more);
  }

  // legal aid: [program name, phone, website, state]
  function legalCard(sa, a, ctx) {
    var short = 'Free legal help for people with low incomes, with problems such as custody, child support, protection from abuse and eviction.';
    var more = [h('p', { 'class': 'org', text: 'Legal aid program funded by the Legal Services Corporation' }),
      h('p', { text: 'It serves ' + ctx.county + ' and the rest of its area, and can tell you if another program is the one for you.' }),
      h('p', {}, [h('strong', { text: 'Next step:' }), ' Call and say what is happening and any date you have to meet, such as a court date or the deadline on an eviction notice. If they cannot take your case, ask who can.']),
      sourceLine('lg', ctx.asof)];
    return card('lg-' + sa, a[0], short, a[1], a[2], more);
  }

  // ---- a row: closed until asked for, like every need on the site
  function row(id, icon, label, sum, n, noun, body) {
    return h('details', { 'class': 'need', id: id }, [
      h('summary', {}, [h('span', { 'class': 'ico', 'aria-hidden': 'true', text: icon }), h('h2', { text: label }),
        h('span', { 'class': 'nsum', text: sum }), h('span', { 'class': 'ncount', text: n === null ? '' : count(n, noun[0], noun[1]) })]),
      h('div', { 'class': 'rowbody' }, [body])
    ]);
  }
  // A list of cards: the first few, "Show more", and a box to narrow a long list by town or name.
  function cardList(items, make, haystack) {
    var box = h('div', { 'class': 'cards' });
    var wrap = h('div', {}, [box]);
    var shown = items.length <= SHOW_ALL ? items.length : STAGE;
    var filter = null;
    var more = null;
    var note = h('p', { 'class': 'quiet', role: 'status' });
    function draw() {
      var term = filter ? filter.value.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim() : '';
      var hits = items.map(function (it, i) { return i; });
      if (term) {
        hits = hits.filter(function (i) { return term.split(' ').every(function (t) { return haystack(items[i]).indexOf(t) !== -1; }); });
      }
      var limit = term ? CAP : Math.min(shown, CAP);
      box.textContent = '';
      hits.slice(0, limit).forEach(function (i) { box.appendChild(make(items[i], i)); });
      if (more) { more.hidden = !!term || shown >= items.length || shown >= CAP; }
      if (more && !more.hidden) { more.textContent = 'Show ' + Math.min(STAGE * 2, items.length - shown, CAP - shown) + ' more'; }
      if (term && !hits.length) { note.textContent = 'Nothing matches. Try a town name or part of a name.'; }
      else if (term) { note.textContent = hits.length > CAP ? 'Showing the first ' + CAP + ' of ' + hits.length + '. Type more to narrow the list.' : count(hits.length, 'match', 'matches') + '.'; }
      else { note.textContent = items.length > Math.min(shown, CAP) ? 'Showing ' + Math.min(shown, CAP) + ' of ' + items.length + '.' : ''; }
    }
    if (items.length > SHOW_ALL) {
      filter = h('input', { type: 'search', 'class': 'rowfilter', placeholder: 'Narrow by town or name', autocomplete: 'off', 'aria-label': 'Narrow this list by town or name' });
      filter.addEventListener('input', draw);
      more = h('button', { type: 'button', 'class': 'btn plain' });
      more.addEventListener('click', function () { shown += STAGE * 2; draw(); });
      wrap.insertBefore(filter, box);
      wrap.appendChild(more);
    }
    wrap.appendChild(note);
    draw();
    return wrap;
  }
  function haystackOf(cols) {
    return function (it) { return cols.map(function (c) { return String(it[c]); }).join(' ').toLowerCase().replace(/[^a-z0-9]+/g, ' ') + ' '; };
  }

  function stateHelp(code) {
    var src = document.querySelector('[data-statehelp]');
    var list = h('ul', { 'class': 'statelinks' });
    if (src) {
      Array.prototype.forEach.call(src.querySelectorAll('a[data-sec]'), function (a) {
        list.appendChild(h('li', {}, [h('a', { href: 'states/' + code + '.html#' + a.getAttribute('data-sec'), text: a.textContent })]));
      });
    }
    return h('div', {}, [h('p', { 'class': 'quiet', text: 'Your state has its own offices for SNAP, WIC, child care, health coverage and more.' }), list]);
  }

  // ---- showing a county
  function showCounty(shard, fips, code, x) {
    var c = shard.c[fips];
    var stName = STATES[code].name;
    var nice = c.n === stName ? c.n : c.n + ', ' + stName;
    var ctx = { county: c.n, asof: shard.asof };
    var health = c.health || c.healthNear || [];
    var start = c.headStart || c.headStartNear || [];
    var hud = c.hud || [];
    var rows = [];
    if (x && x.t) { rows.push(christmasRow(x, fips, code, c, stName)); }
    function words(list) { return list.join(' ').toLowerCase().replace(/[^a-z0-9]+/g, ' ') + ' '; }
    // Where to apply for public housing and rent vouchers.
    var pha = (c.pha || []).filter(function (ref) { return shard.ph && shard.ph[ref[0]]; });
    var phaHere = pha.some(function (ref) { return ref[2] === 'c' || ref[2] === 'n'; });
    var phaNear = pha.some(function (ref) { return ref[2] === 'r'; });
    rows.push(row('county-pha', '🔑', 'Public housing and Section 8',
      phaHere ? 'Where to apply in ' + c.n + ' for public housing and rent vouchers'
        : (phaNear ? 'Nearest agencies, outside ' + c.n : 'Your state\'s agency for public housing and rent vouchers'), pha.length, ['agency', 'agencies'],
      pha.length ? cardList(pha, function (ref) { return phaCard(ref, shard.ph[ref[0]], ctx); }, function (ref) { var a = shard.ph[ref[0]]; return words([a[0], a[2], a[3]]); })
        : h('p', { 'class': 'quiet', text: 'No public housing agency is listed near ' + c.n + '. Call HUD at 800-955-2232 to find the one that serves you.' })));
    var agencies = hud.filter(function (ref) { return shard.hu[ref[0]]; });
    rows.push(row('county-hud', '🏠', 'Housing counselors',
      'Free or low-cost help with rent, eviction and mortgages', agencies.length, ['counselor', 'counselors'],
      agencies.length ? cardList(agencies, function (ref) { return hudCard(ref, shard.hu[ref[0]], ctx); }, function (ref) { var a = shard.hu[ref[0]]; return words([a[0], a[2]]); })
        : h('p', { 'class': 'quiet', text: 'No HUD-approved counselor is listed near ' + c.n + '. Call HUD at 800-569-4287 to be matched with one by phone.' })));
    var legal = (c.lg || []).filter(function (sa) { return shard.lg && shard.lg[sa]; });
    rows.push(row('county-legal', '⚖️', 'Free legal help',
      'Legal aid that serves ' + c.n, legal.length, ['program', 'programs'],
      legal.length ? cardList(legal, function (sa) { return legalCard(sa, shard.lg[sa], ctx); }, function (sa) { return words([shard.lg[sa][0]]); })
        : h('p', { 'class': 'quiet', text: 'No legal aid program is listed for ' + c.n + '. Your state\'s legal help is in the last row.' })));
    rows.push(row('county-health', '🩺', 'Low-cost health care',
      c.health ? 'Health centers in ' + c.n : 'Nearest health centers, outside ' + c.n, health.length, ['place', 'places'],
      health.length ? cardList(health, function (r, i) { return healthCard(r, i, ctx); }, haystackOf([0, 1, 2, 3, 4]))
        : h('p', { 'class': 'quiet', text: 'No health center is listed within 60 miles. Dial 211 and ask for a free or low-cost clinic.' })));
    // Where to ask for a free evaluation for a child from age 3.
    var sd = (c.sd || []).map(function (id) { return [id, 0]; }).concat(c.sdNear || []).filter(function (ref) { return shard.sd && shard.sd[ref[0]]; });
    var intro = h('p', { 'class': 'quiet' }, ['From age 3, children can get special education free through the public schools, even before kindergarten. ',
      'If you think your child has a delay or disability, call your school district and ask for an evaluation. If the district decides not to evaluate, it has to tell you why in writing. ',
      'For a child under 3, ask ', h('a', { href: 'states/' + code + '.html#' + code + '-ei', text: 'early intervention in ' + stName }), ' instead.']);
    rows.push(row('county-schools', '🧩', 'Free evaluation for your child',
      c.sd ? 'School districts in ' + c.n + ', for children 3 and up' : 'Nearest school districts, outside ' + c.n, sd.length, ['district', 'districts'],
      h('div', {}, [intro, sd.length ? cardList(sd, function (ref) { return districtCard(ref[0], ref[1], shard.sd[ref[0]], ctx); }, function (ref) { var d = shard.sd[ref[0]]; return words([d[0], d[2], d[3]]); })
        : h('p', { 'class': 'quiet', text: 'No school district is listed for ' + c.n + '. Call your state\'s department of education and ask which district serves you.' })])));
    rows.push(row('county-start', '🧸', 'Head Start and Early Head Start',
      c.headStart ? 'Free early learning in ' + c.n : 'Nearest programs, outside ' + c.n, start.length, ['place', 'places'],
      start.length ? cardList(start, function (r, i) { return headStartCard(r, i, ctx); }, haystackOf([0, 1, 2, 3, 4]))
        : h('p', { 'class': 'quiet', text: 'No open Head Start location is listed within 60 miles. Dial 211 and ask about free child care and preschool.' })));
    rows.push(row('county-state', '📍', 'Help across ' + stName, 'SNAP, WIC, child care, health coverage and more', null, null, stateHelp(code)));
    var out = h('section', { 'class': 'wrap needs', 'aria-label': 'Help in ' + nice }, rows);
    if (c.pg) {
      out.insertBefore(h('div', { 'class': 'localbox' }, [h('strong', { text: 'We have a local guide for ' + c.n + '.' }), ' ', h('a', { href: c.pg, text: 'Open the ' + c.n + ' guide' }), ' for hand-checked listings, then come back here for the rest.']), out.firstChild);
    }
    app.textContent = '';
    app.appendChild(out);
    app.appendChild(h('p', { 'class': 'wrap quiet' }, ['Listings come from federal directories and are not confirmed by phone. A phone number or address may be out of date. ', h('a', { href: 'report.html', text: 'Report a problem' }), '.']));
    title.textContent = nice;
    lede.textContent = 'Local listings for ' + c.n + ', and where to find your state\'s offices. Pick what you need.';
    document.title = nice + ': help for moms | ' + HOME_DOC.split('|').pop().trim();
    say('');
    syncPicker(shard, code, fips);
  }

  function showState(shard, code) {
    var stName = STATES[code].name;
    var list = h('ul', { 'class': 'statelist' });
    Object.keys(shard.c).sort(function (a, b) { return shard.c[a].n < shard.c[b].n ? -1 : 1; }).forEach(function (fips) {
      list.appendChild(h('li', {}, [h('a', { href: '#' + fips, text: shard.c[fips].n })]));
    });
    app.textContent = '';
    app.appendChild(h('section', { 'class': 'wrap' }, [h('h2', { text: count(Object.keys(shard.c).length, 'county', 'counties') + ' in ' + stName }), list,
      h('p', { 'class': 'note' }, [h('a', { href: 'states/' + code + '.html', text: 'See all of ' + stName + '\'s help' })])]));
    title.textContent = stName + ' counties';
    lede.textContent = 'Pick your county.';
    document.title = stName + ' counties: help for moms | ' + HOME_DOC.split('|').pop().trim();
    syncPicker(shard, code, '');
  }

  function showHome() {
    app.textContent = '';
    title.textContent = HOME_TITLE;
    lede.textContent = HOME_LEDE;
    document.title = HOME_DOC;
    say('');
  }

  function problem(code) {
    app.textContent = '';
    var p = h('p', {}, ['We could not load that list just now. Please try again in a moment.']);
    if (code && STATES[code]) {
      p.appendChild(document.createTextNode(' You can also '));
      p.appendChild(h('a', { href: 'states/' + code + '.html', text: 'open the ' + STATES[code].name + ' page' }));
      p.appendChild(document.createTextNode('.'));
    }
    app.appendChild(h('section', { 'class': 'wrap' }, [p]));
  }

  // ---- the three ways to choose
  function fillCounties(shard, selected) {
    countySel.textContent = '';
    countySel.appendChild(h('option', { value: '', text: 'Choose your county' }));
    Object.keys(shard.c).sort(function (a, b) { return shard.c[a].n < shard.c[b].n ? -1 : 1; }).forEach(function (fips) {
      var o = h('option', { value: fips, text: shard.c[fips].n });
      if (fips === selected) { o.selected = true; }
      countySel.appendChild(o);
    });
    countySel.disabled = false;
  }
  function syncPicker(shard, code, fips) {
    stateSel.value = code;
    if (countySel.getAttribute('data-state') !== code) { fillCounties(shard, fips); countySel.setAttribute('data-state', code); }
    countySel.value = fips;
  }

  function route() {
    var hash = '';
    try { hash = decodeURIComponent(window.location.hash.slice(1)); } catch (e) { hash = ''; }
    var mine = ++turn;
    var code = '';
    if (/^\d{5}$/.test(hash)) { code = BY_FIPS[hash.slice(0, 2)] || ''; }
    else if (/^[a-z]{2}$/.test(hash) && STATES[hash]) { code = hash; }
    if (!code) { showHome(); return; }
    loadShard(code).then(function (shard) {
      if (mine !== turn) { return; }
      if (hash.length === 5 && shard.c[hash]) {
        // The Christmas row is extra: if its list cannot load, the county page shows without it.
        loadXmas().then(function (x) { if (mine === turn) { showCounty(shard, hash, code, x); } },
          function () { if (mine === turn) { showCounty(shard, hash, code, null); } });
      }
      else if (hash.length === 2) { showState(shard, code); }
      else { showHome(); say('We do not have a county with that code.'); }
    }).catch(function () { if (mine === turn) { problem(code); } });
  }

  stateSel.addEventListener('change', function () {
    var code = stateSel.value;
    countySel.disabled = true;
    countySel.removeAttribute('data-state');
    if (!code) { countySel.textContent = ''; countySel.appendChild(h('option', { value: '', text: 'Choose a state first' })); return; }
    window.location.hash = code;
  });
  countySel.addEventListener('change', function () {
    if (countySel.value) { window.location.hash = countySel.value; }
  });
  function lookup() {
    var z = zipBox.value.replace(/\D/g, '');
    if (z.length !== 5) { say(z.length ? 'A ZIP code has five digits.' : ''); return; }
    say('Looking up ' + z + '…');
    loadZips(z.charAt(0)).then(function (table) {
      if (table[z]) { say(''); window.location.hash = table[z]; }
      else { say('We could not match that ZIP code to a county. Choose your state and county instead.'); }
    }).catch(function () { say('We could not look that up just now. Choose your state and county instead.'); });
  }
  zipBox.addEventListener('input', function () { if (zipBox.value.replace(/\D/g, '').length === 5) { lookup(); } });
  zipBox.addEventListener('keydown', function (e) { if (e.key === 'Enter') { lookup(); } });
  zipBox.addEventListener('search', lookup);

  picker.hidden = false;
  window.addEventListener('hashchange', route);
  route();
})();
