// The OhioMom map (ohio/map.html), in the style of Nina's Map: a map you can zoom, a list beside it, kind
// chips and a search box.
//
// What it shows: ohio/assets/map-places.json (built by scripts/ohio_map.py from the federal county data) and the
// upcoming events in ohio/assets/data.json. There is no street-level position for any place, so each one is
// counted at its county's label point in ohio/assets/map.json, and the map draws the county shapes from the same
// file. No map tiles are loaded from anywhere: nothing about the visitor leaves the page. A county the visitor
// picks is remembered in this browser only, the same way the Near you page does it.
//
// Without this script, or if a file does not load, the page shows the plain list, county by county.
(function () {
  'use strict';
  var box = document.getElementById('omap');
  var app = document.querySelector('[data-mapapp]');
  if (!box || !app || !window.L || !window.fetch || !L.markerClusterGroup) { return; }

  var $ = function (id) { return document.getElementById(id); };
  var search = $('mq'), townList = $('mplaces'), select = $('mcounty'), chips = document.querySelector('[data-map-kinds]');
  var status = $('mstatus'), head = $('mhead'), info = $('mcountyinfo'), list = $('mlist'), more = $('mmore'), reset = $('mreset');
  var KINDS = [
    ['health', 'Health care', '#cf2f5b'],
    ['start', 'Head Start', '#b45309'],
    ['housing', 'Public housing', '#12766f'],
    ['counsel', 'Housing counselors', '#5b4b8a'],
    ['event', 'Events', '#2b2140']
  ];
  var KIND_ONE = { health: 'Health care', start: 'Head Start', housing: 'Public housing', counsel: 'Housing counselor', event: 'Event' };
  var PROGRAM = {
    C: 'Public housing and Section 8 vouchers.',
    S: 'Section 8 vouchers, which help pay rent to a private landlord.',
    P: 'Public housing: apartments with rent based on your income.'
  };
  var SERVICES = { R: 'renting', H: 'homelessness', D: 'mortgage trouble', B: 'budgeting', P: 'buying a home' };
  var MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  var PAGE = 20;
  var S = 0.25; // map.json units to map units, so that the zoom levels stay at zero and above

  var site, shapes, data;
  var items = [], byCounty = {}, counties = [], shapesOf = {}, markers = {};
  var on = {}, picked = '', pickedBy = '', text = '', town = '', shown = PAGE, lastNote = '';
  var map, cluster, ohio;

  KINDS.forEach(function (k) { on[k[0]] = true; });

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function words(list) {
    list = list.filter(Boolean);
    return list.length < 2 ? list.join('') : list.slice(0, -1).join(', ') + ' and ' + list[list.length - 1];
  }
  function plural(n, one, many) { return n.toLocaleString('en-US') + ' ' + (n === 1 ? one : many); }
  function today() {
    var d = new Date();
    return d.getFullYear() + '-' + ('0' + (d.getMonth() + 1)).slice(-2) + '-' + ('0' + d.getDate()).slice(-2);
  }
  function short(iso) { var p = iso.split('-'); return MONTHS[+p[1] - 1] + ' ' + (+p[2]); }
  function tel(phone) { var d = String(phone || '').replace(/\D/g, ''); return d.length === 10 ? d : ''; }
  function safeUrl(u) { return /^https:\/\/[A-Za-z0-9.-]+(\/[^\s"<>]*)?$/.test(u || '') ? u : ''; }
  function ll(x, y) { return [-y * S, x * S]; }
  function region(county) {
    var id = site.counties[county] && site.counties[county][0];
    return site.regions.filter(function (r) { return r.id === id; })[0] || { label: 'Ohio', color: '#ddd' };
  }
  function norm(s) { return String(s || '').toLowerCase().replace(/\s+/g, ' ').trim(); }

  // ---- what each place says, from the codes in map-places.json (see scripts/ohio_map.py)
  function what(kind, m) {
    if (kind === 'health') {
      return 'Low-cost health care, with or without insurance. Fees are based on your income.' +
        (m[0] ? ' Part of ' + m[0] + '.' : '') + (m[1] ? ' Open only part of the year, so call before you go.' : '');
    }
    if (kind === 'start') {
      var k = m[0], s;
      if ((k & 1) && (k & 2)) { s = 'Free preschool for ages 3 to 5, and Early Head Start for babies, toddlers and pregnant moms.'; }
      else if (k & 2) { s = 'Early Head Start: free early learning for babies and toddlers, and support for pregnant moms.'; }
      else { s = 'Free preschool for children ages 3 to 5.'; }
      if (k & 4) { s += ' Serves migrant and seasonal farmworker families.'; }
      if (k & 8) { s += ' A tribal program; ask who can enroll.'; }
      return s + ' For families who qualify.' + (m[1] ? ' Run by ' + m[1] + '.' : '');
    }
    if (kind === 'housing') { return (PROGRAM[m] || 'Public housing agency.') + ' Ask whether the waiting list is open.'; }
    var topics = words('RHDBP'.split('').filter(function (c) { return String(m).indexOf(c) !== -1; }).map(function (c) { return SERVICES[c]; }));
    return 'Free or low-cost help from a HUD-approved housing counselor' + (topics ? ' with ' + topics : '') + '.';
  }

  function load() {
    // places: [kind, county, name, street, city, zip, phone, web, more]
    data.places.forEach(function (p) {
      items.push({ k: p[0], county: p[1], name: p[2], city: p[4], addr: [p[3], (p[4] + ', OH ' + p[5]).trim()].filter(Boolean).join(', '),
        phone: p[6], web: safeUrl(p[7]), what: what(p[0], p[8]) });
    });
    var now = today();
    (site.events || []).forEach(function (e) {
      var end = e.end || e.start;
      if (end < now || !shapes.c[e.county]) { return; }
      var from = e.start < now ? now : e.start;
      items.push({ k: 'event', county: e.county, name: e.title, city: e.city, addr: e.place,
        when: (e.start < now ? 'Now' : short(e.start)) + (end !== from ? ' to ' + short(end) : ''), sortWhen: from,
        what: e.blurb || '', web: safeUrl(e.url), more: e.when || '' });
    });
    items.forEach(function (it, i) {
      it.i = i;
      it.hay = norm([it.name, it.city, it.addr, it.what, KIND_ONE[it.k]].join(' '));
      (byCounty[it.county] = byCounty[it.county] || []).push(it);
    });
    counties = Object.keys(shapes.c).sort();
  }

  // ---- where a search points: a county, a town or a ZIP code (from ohio/assets/places.json)
  var placeIndex = { towns: {}, zips: {}, reach: {} };
  function indexPlaces(p) {
    Object.keys(p.counties || {}).forEach(function (county) {
      String(p.counties[county]).split('|').forEach(function (entry) {
        var parts = entry.split(' '), name = [];
        parts.forEach(function (w) {
          if (/^\d{5}$/.test(w)) { placeIndex.zips[w] = placeIndex.zips[w] || county; } else { name.push(w); }
        });
        var key = norm(name.join(' '));
        if (key) { (placeIndex.towns[key] = placeIndex.towns[key] || []).indexOf(county) === -1 && placeIndex.towns[key].push(county); }
      });
    });
    placeIndex.reach = p.reaches || {};
    Object.keys(site.cities || {}).forEach(function (c) {
      var key = norm(c);
      if (!placeIndex.towns[key]) { placeIndex.towns[key] = [site.cities[c]]; }
    });
    var opts = counties.map(function (c) { return '<option value="' + esc(c) + ' County">'; });
    Object.keys(placeIndex.towns).sort().forEach(function (t) {
      var name = t.replace(/\b[a-z]/g, function (c) { return c.toUpperCase(); });
      opts.push('<option value="' + esc(name) + '">');
    });
    townList.innerHTML = opts.join('');
  }
  function lookup(q) {
    var key = norm(q).replace(/,? (oh|ohio)$/, '');
    if (!key) { return null; }
    var bare = key.replace(/ county$/, '');
    for (var i = 0; i < counties.length; i++) {
      if (norm(counties[i]) === bare) { return { county: counties[i], note: '' }; }
    }
    if (/^\d{5}$/.test(key)) {
      var home = placeIndex.zips[key];
      if (!home) { return { none: 'ZIP code ' + key + ' is not one we have for Ohio.' }; }
      var reach = String(placeIndex.reach[key] || '').split('|').filter(function (c) { return c && c !== home; });
      return { county: home, note: 'ZIP code ' + key + ' is in ' + home + ' County' +
        (reach.length ? ', and part of it reaches ' + words(reach) + (reach.length === 1 ? ' County' : ' counties') : '') + '.' };
    }
    var towns = placeIndex.towns[key];
    if (towns) {
      var name = q.trim().replace(/,? (oh|ohio)$/i, '');
      return { county: towns[0], town: key, note: name + ' is in ' + towns[0] + ' County.' +
        (towns.length > 1 ? ' There is also a ' + name + ' in ' + words(towns.slice(1)) + (towns.length > 2 ? ' counties.' : ' County.') : '') };
    }
    return null;
  }

  // ---- the map
  function drawMap() {
    map = L.map(box, { crs: L.CRS.Simple, zoomSnap: 0.25, zoomDelta: 0.5, minZoom: 0, maxZoom: 5, scrollWheelZoom: false,
      attributionControl: true });
    map.attributionControl.setPrefix('<a href="https://leafletjs.com" rel="noopener noreferrer">Leaflet</a>');
    ohio = L.latLngBounds([ll(0, shapes.h), ll(shapes.w, 0)]);
    counties.forEach(function (c) {
      var rings = shapes.c[c].d.split('M').filter(Boolean).map(function (part) {
        return [part.replace(/Z/g, '').split('L').map(function (pt) { var xy = pt.split(','); return ll(+xy[0], +xy[1]); })];
      });
      var poly = L.polygon(rings, { color: '#fff', weight: 1, fillColor: region(c).color, fillOpacity: 0.62, className: 'ocounty' });
      poly.bindTooltip(c + ' County', { sticky: true, direction: 'top', className: 'otip' });
      poly.on('click', function () { pick(c, 'map'); });
      poly.on('mouseover', function () { if (c !== picked) { poly.setStyle({ fillOpacity: 0.85 }); } });
      poly.on('mouseout', function () { styleCounty(c); });
      poly.addTo(map);
      shapesOf[c] = poly;
    });
    cluster = L.markerClusterGroup({
      showCoverageOnHover: false, spiderfyOnMaxZoom: false, zoomToBoundsOnClick: true,
      // Counties sit about 45 map.json units apart. Zoomed out (a phone) neighbors join up; zoomed in, each county has its own circle.
      maxClusterRadius: function (z) { return z <= 1 ? 30 : z === 2 ? 16 : 10; },
      iconCreateFunction: function (cl) {
        var kids = cl.getAllChildMarkers(), n = 0, names = [];
        kids.forEach(function (m) { n += m.options.n; names.push(m.options.county); });
        names.sort();
        var named = names.length > 3 ? names.slice(0, 2).join(', ') + ' and ' + (names.length - 2) + ' more counties' : words(names) + ' counties';
        return bubble(n, 'ocluster', plural(n, 'place', 'places') + ' in ' + named + '. Zoom in to split them up.');
      }
    });
    cluster.on('clusterclick', function (e) {
      // At the closest zoom a group cannot split any further: open the first of its counties instead.
      if (map.getZoom() >= map.getMaxZoom()) { pick(e.layer.getAllChildMarkers()[0].options.county, 'map'); }
    });
    cluster.on('clusterkeypress', function (e) {
      if (!pressed(e)) { return; }
      if (map.getZoom() >= map.getMaxZoom()) { pick(e.layer.getAllChildMarkers()[0].options.county, 'map'); } else { e.layer.zoomToBounds({ padding: [20, 20] }); }
    });
    map.addLayer(cluster);
    fit();
    map.on('resize', function () { var z = map.getBoundsZoom(ohio, false, L.point(8, 8)); map.setMinZoom(Math.max(0, z - 0.5)); if (!picked) { fit(); } });
    map.on('moveend', function () { if (!picked) { shown = PAGE; renderList(); } });
  }
  // A count circle is a button: Enter or Space opens it, as a click does.
  function pressed(e) {
    var k = e.originalEvent && (e.originalEvent.key || e.originalEvent.keyCode);
    if (k === 'Enter' || k === ' ' || k === 13 || k === 32) { e.originalEvent.preventDefault(); return true; }
    return false;
  }
  function fit() {
    var z = map.getBoundsZoom(ohio, false, L.point(16, 16));
    map.setMinZoom(Math.max(0, z - 0.5));
    map.setMaxBounds(ohio.pad(0.2));
    map.fitBounds(ohio, { padding: [8, 8] });
  }
  function bubble(n, cls, label) {
    var size = n > 99 ? 36 : n > 9 ? 30 : 26;
    return L.divIcon({ className: cls, iconSize: [size, size],
      html: '<span aria-hidden="true">' + n + '</span><span class="sr">' + esc(label) + '</span>' });
  }
  function styleCounty(c) {
    var poly = shapesOf[c];
    if (!poly) { return; }
    var sel = c === picked;
    poly.setStyle({ color: sel ? '#2b2140' : '#fff', weight: sel ? 3 : 1, fillOpacity: picked && !sel ? 0.4 : 0.62 });
    if (sel) { poly.bringToFront(); }
  }

  // ---- what is showing
  function matches(it) { return on[it.k] && (!text || it.hay.indexOf(text) !== -1); }
  function countFor(c) { return (byCounty[c] || []).filter(matches).length; }
  function drawMarkers() {
    cluster.clearLayers();
    markers = {};
    var layers = [];
    counties.forEach(function (c) {
      var n = countFor(c);
      if (!n) { return; }
      var pt = shapes.c[c];
      var m = L.marker(ll(pt.x, pt.y), { icon: bubble(n, 'ocount' + (c === picked ? ' sel' : ''), c + ' County: ' + plural(n, 'place', 'places') + '. Show the list.'),
        keyboard: true, n: n, county: c, riseOnHover: true });
      m.on('click', function () { pick(c, 'map'); });
      m.on('keypress', function (e) { if (pressed(e)) { pick(c, 'map'); } });
      markers[c] = m;
      layers.push(m);
    });
    cluster.addLayers(layers);
  }
  function pool() {
    var out;
    if (picked) {
      out = (byCounty[picked] || []).filter(matches);
    } else {
      var view = map.getBounds(), whole = view.contains(ohio);
      out = items.filter(function (it) { return matches(it) && (whole || view.contains(ll(shapes.c[it.county].x, shapes.c[it.county].y))); });
    }
    var order = { health: 0, start: 1, housing: 2, counsel: 3, event: 4 };
    return out.sort(function (a, b) {
      if (town) { var ta = norm(a.city) === town ? 0 : 1, tb = norm(b.city) === town ? 0 : 1; if (ta !== tb) { return ta - tb; } }
      if (!picked && a.county !== b.county) { return a.county < b.county ? -1 : 1; }
      if (a.k !== b.k) { return order[a.k] - order[b.k]; }
      if (a.k === 'event' && a.sortWhen !== b.sortWhen) { return a.sortWhen < b.sortWhen ? -1 : 1; }
      return a.name.toLowerCase() < b.name.toLowerCase() ? -1 : 1;
    });
  }
  function card(it) {
    var acts = '';
    if (tel(it.phone)) { acts += '<a class="btn call" href="tel:' + tel(it.phone) + '">Call ' + esc(it.phone) + '</a>'; }
    if (it.web) { acts += '<a class="btn" href="' + esc(it.web) + '" rel="noopener noreferrer">' + (it.k === 'event' ? 'Details' : 'Website') + '</a>'; }
    var sub = '<span class="okind k-' + it.k + '">' + esc(KIND_ONE[it.k]) + '</span>' + (it.when ? ' · ' + esc(it.when) : '') +
      ' · ' + esc(it.city ? it.city + ', ' : '') + esc(it.county) + ' County';
    return '<li class="oplace k-' + it.k + '"><h3 tabindex="-1">' + esc(it.name) + '</h3><p class="osub">' + sub + '</p>' +
      (it.what ? '<p>' + esc(it.what) + '</p>' : '') + (it.more ? '<p class="owhen">' + esc(it.more) + '</p>' : '') +
      (it.addr ? '<p class="oaddr">' + esc(it.addr) + '</p>' : '') + (acts ? '<p class="actions">' + acts + '</p>' : '') + '</li>';
  }
  function anyKind() { return KINDS.some(function (k) { return on[k[0]]; }); }
  function renderList(focusFrom) {
    var all = pool(), total = all.length;
    var whole = !picked && map.getBounds().contains(ohio);
    head.textContent = picked ? picked + ' County' : whole ? 'All of Ohio' : 'In view on the map';
    reset.hidden = !picked && whole;
    list.innerHTML = all.slice(0, shown).map(card).join('');
    more.hidden = total <= shown;
    more.textContent = 'Show ' + Math.min(PAGE, total - shown) + ' more of ' + total.toLocaleString('en-US');
    var where = picked ? picked + ' County' : whole ? 'Ohio' : 'this part of the map';
    var say;
    if (!anyKind()) { say = 'Pick at least one kind of place to show.'; }
    else if (!total) { say = text ? 'Nothing in ' + where + ' matches “' + search.value.trim() + '”. Try part of a name, or clear the search.' : 'Nothing of these kinds is listed in ' + where + '. The county page lists the nearest ones.'; }
    else { say = plural(total, 'place', 'places') + ' in ' + where + (text ? ' match “' + search.value.trim() + '”' : '') + '.'; }
    status.textContent = (lastNote ? lastNote + ' ' : '') + say;
    if (focusFrom != null) { var h = list.querySelectorAll('h3')[focusFrom]; if (h) { h.focus(); } }
  }
  function renderInfo() {
    if (!picked) { info.innerHTML = ''; return; }
    var row = site.counties[picked] || [], r = region(picked), links = [];
    if (row[2]) { links.push('<a class="btn" href="' + esc(row[2]) + '">OhioMom page for ' + esc(picked) + ' County</a>'); }
    links.push('<a class="btn" href="../county.html#' + esc(data.counties[picked]) + '">Everything for ' + esc(picked) + ' County</a>');
    links.push('<a class="btn" href="all.html#county=' + encodeURIComponent(picked) + '">Statewide help that serves it</a>');
    info.innerHTML = '<p class="small">' + esc(r.label) + (row[1] ? ', county seat ' + esc(row[1]) : '') + '. For benefits, WIC and child support, dial <a href="tel:211">211</a> and give your county.</p>' +
      '<p class="actions">' + links.join('') + '</p>';
  }
  function render(focusFrom) {
    drawMarkers();
    renderInfo();
    renderList(focusFrom);
    counties.forEach(styleCounty);
  }

  // ---- choosing
  function remember(c) {
    try { localStorage.setItem('om.area', JSON.stringify({ r: site.counties[c][0], c: c })); } catch (e) { /* private window */ }
    var chip = document.querySelector('[data-area-chip]');
    if (chip) { chip.textContent = '📍 ' + c + ' County'; }
  }
  function setHash(c) {
    if (!window.history || !history.replaceState) { return; }
    try { history.replaceState(null, '', c ? '#county=' + encodeURIComponent(c) : location.pathname + location.search); } catch (e) { /* file: pages */ }
  }
  function pick(c, how) {
    if (!shapes.c[c]) { return; }
    picked = c;
    pickedBy = how;
    if (how !== 'search') { town = ''; lastNote = ''; }
    shown = PAGE;
    select.value = c;
    setHash(c);
    if (how !== 'start') { remember(c); }
    map.fitBounds(shapesOf[c].getBounds(), { padding: [30, 30], maxZoom: 4 });
    render();
    if (how === 'map' && window.matchMedia && window.matchMedia('(max-width: 760px)').matches && head.scrollIntoView) {
      head.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }
  function unpick() {
    picked = '';
    pickedBy = '';
    town = '';
    lastNote = '';
    shown = PAGE;
    select.value = '';
    setHash('');
    map.fitBounds(ohio, { padding: [8, 8] });
    render();
  }

  function controls() {
    select.innerHTML = '<option value="">All of Ohio</option>' + counties.map(function (c) {
      return '<option value="' + esc(c) + '">' + esc(c) + ' County</option>';
    }).join('');
    select.addEventListener('change', function () { if (select.value) { pick(select.value, 'select'); } else { unpick(); } });
    chips.innerHTML = KINDS.map(function (k) {
      return '<button type="button" data-k="' + k[0] + '" aria-pressed="true" style="--c:' + k[2] + '">' + esc(k[1]) + '</button>';
    }).join('');
    chips.addEventListener('click', function (e) {
      var b = e.target.closest && e.target.closest('button');
      if (!b) { return; }
      var k = b.getAttribute('data-k');
      on[k] = !on[k];
      b.setAttribute('aria-pressed', String(on[k]));
      shown = PAGE;
      render();
    });
    var timer = null;
    function run() {
      var q = search.value;
      var hit = lookup(q);
      if (hit && hit.county) {
        text = '';
        town = hit.town || '';
        lastNote = hit.note;
        pick(hit.county, 'search');
        return;
      }
      text = norm(q);
      town = '';
      lastNote = hit && hit.none ? hit.none : '';
      if (pickedBy === 'search') { unpick(); return; }
      shown = PAGE;
      render();
    }
    search.addEventListener('input', function () { clearTimeout(timer); timer = setTimeout(run, 300); });
    search.addEventListener('change', function () { clearTimeout(timer); run(); });
    search.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); clearTimeout(timer); run(); } });
    more.addEventListener('click', function () { var from = shown; shown += PAGE; renderList(from); });
    reset.addEventListener('click', function () { search.value = ''; text = ''; unpick(); head.focus(); });
  }

  function start() {
    var c = '';
    var m = /(?:^#|&)county=([^&]+)/.exec(location.hash || '');
    if (m) { try { c = decodeURIComponent(m[1].replace(/\+/g, ' ')); } catch (e) { c = ''; } }
    if (!shapes.c[c]) {
      c = '';
      try { var saved = JSON.parse(localStorage.getItem('om.area') || 'null'); if (saved && shapes.c[saved.c]) { c = saved.c; } } catch (e) { c = ''; }
    }
    if (c) { pick(c, 'start'); } else { render(); }
  }

  function json(path) { return fetch(path).then(function (r) { if (!r.ok) { throw new Error(path); } return r.json(); }); }
  Promise.all([json('assets/data.json'), json('assets/map.json'), json('assets/map-places.json'), json('assets/places.json')])
    .then(function (got) {
      site = got[0]; shapes = got[1]; data = got[2];
      app.hidden = false;
      load();
      indexPlaces(got[3]);
      drawMap();
      controls();
      start();
    })
    .catch(function () {
      app.hidden = true;
      var note = document.createElement('p');
      note.className = 'pending';
      note.textContent = 'The map did not load. Every place is in the list below, county by county.';
      var hero = document.querySelector('.hero .wrap');
      if (hero) { hero.appendChild(note); }
    });
}());
