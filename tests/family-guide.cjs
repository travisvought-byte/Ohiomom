const assert=require('node:assert/strict'),fs=require('node:fs'),{JSDOM}=require('jsdom');
const html=fs.readFileSync('family-guide.html','utf8'),script=fs.readFileSync('assets/family-guide.js','utf8');
function load(q=''){
 const dom=new JSDOM(html,{url:'https://example.org/family-guide.html'+q,runScripts:'outside-only'});
 const w=dom.window;w.print=()=>{};w.eval(script);const d=w.document,$=id=>d.getElementById(id);
 const set=(id,value)=>{$(id).value=value;$(id).dispatchEvent(new w.Event('change'));};
 return {w,d,$,set};
}

const {$,d,set}=load('?state=OH&county=Knox&stage=early');
const data=JSON.parse($('family-data').textContent);
assert.deepEqual(Object.keys(data.states),['OH']);
assert.equal($('state').options.length,1);
assert.equal($('county').options.length,89);
assert($('county-result').textContent.includes('740-397-4656'));
assert.equal(d.querySelectorAll('#pa-list li').length,1);
assert(!$('r-oh-help-me-grow').hidden);
for(const c of data.ohio_counties){set('county',c.county);assert($('county-result').textContent.includes(c.county));assert(/\d{3}-\d{3}-\d{4}/.test($('county-result').textContent));}
for(const stage of data.stages){d.querySelector('[data-stage="'+stage.id+'"]').click();assert(!/undefined|NaN/.test($('result-status').textContent));}
assert.equal(load('?state=NY').$('state').value,'OH');
assert(load('?lang=es').d.querySelector('h1').textContent.includes('familias'));
assert(d.querySelector('a[href="https://guide.vethomeguard.org/family-guide.html?state=US"]'));
assert.equal($('back-guide').getAttribute('href'),'./');
assert($('cvso-link').href.startsWith('https://guide.vethomeguard.org/'));
assert(!html.includes('assets/analytics.js'));
console.log('PASS Ohio-only scope, 88 county contacts, stages, Spanish and cross-site links');
