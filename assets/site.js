(function () {
  // Quick exit: replace this page so the Back button does not return here.
  document.getElementById('exit').addEventListener('click', function () {
    window.location.replace('https://www.google.com/search?q=weather');
  });
  var q = document.getElementById('q'), need = document.getElementById('need'), count = document.getElementById('count');
  var cards = Array.prototype.slice.call(document.querySelectorAll('.card'));
  function apply() {
    var term = q.value.trim().toLowerCase(), n = need ? need.value : '', shown = 0;
    cards.forEach(function (c) {
      var ok = !term || c.textContent.toLowerCase().indexOf(term) !== -1;
      if (ok && n && c.dataset.section === 'disability') {
        var needs = c.dataset.needs.split(' ');
        ok = needs.indexOf(n) !== -1 || needs.indexOf('any') !== -1;
      }
      c.hidden = !ok;
      if (ok) shown++;
    });
    count.textContent = term || n ? shown + ' of ' + cards.length + ' listings shown' : '';
  }
  q.addEventListener('input', apply);
  if (need) need.addEventListener('change', apply);
})();
