function mode(m,keep){var r=document.getElementById('view-read'),s=document.getElementById('view-settings');
r.hidden=m!=='read';s.hidden=m!=='settings';document.body.classList.toggle('reading',m==='read');
var ns=document.getElementById('nav-settings'),jr=document.getElementById('jump-read');
if(ns)ns.style.display=m==='settings'?'':'none';if(jr)jr.style.display=m==='read'?'':'none';
document.querySelectorAll('.tabs button').forEach(function(b){b.classList.toggle('active',b.dataset.m===m)});
if(!keep)history.replaceState(null,'',m==='read'?'#read':'#settings');window.scrollTo(0,0)}
function openChapter(n,keep){mode('read',true);
document.querySelectorAll('.chapter').forEach(function(s){s.hidden=true});
var ix=document.getElementById('ch-index');if(ix)ix.hidden=true;
var el=document.getElementById('read-'+n);if(el)el.hidden=false;
if(!keep)history.replaceState(null,'','#read-'+n);window.scrollTo(0,0)}
function openIndex(){mode('read',true);
document.querySelectorAll('.chapter').forEach(function(s){s.hidden=true});
var ix=document.getElementById('ch-index');if(ix)ix.hidden=false;window.scrollTo(0,0)}
function filterIndex(q){var t=q.trim().toLowerCase();
document.querySelectorAll('#ch-index .item').forEach(function(d){
d.style.display=(!t||d.textContent.toLowerCase().indexOf(t)>=0)?'':'none'})}
function jump(sel){var o=sel.selectedOptions[0];if(o&&o.dataset.n)openChapter(+o.dataset.n,true)}
function toggleSide(){document.body.classList.toggle('side-off')}
function graphFocus(svg,keys){var near=new Set(keys);
svg.querySelectorAll('.graph-edge').forEach(function(e){if(keys.indexOf(e.dataset.a)>=0||keys.indexOf(e.dataset.b)>=0){near.add(e.dataset.a);near.add(e.dataset.b)}});
svg.querySelectorAll('.graph-node').forEach(function(n){n.classList.toggle('faded',keys.length>0&&!near.has(n.dataset.key))});
svg.querySelectorAll('.graph-edge').forEach(function(e){e.classList.toggle('faded',keys.length>0&&keys.indexOf(e.dataset.a)<0&&keys.indexOf(e.dataset.b)<0)})}
function focusGraph(node){graphFocus(node.closest('svg'),[node.dataset.key])}
function filterGraph(input){var svg=input.closest('.chart').querySelector('svg'),q=input.value.trim().toLowerCase(),keys=[];
svg.querySelectorAll('.graph-node').forEach(function(n){if(q&&n.textContent.toLowerCase().indexOf(q)>=0)keys.push(n.dataset.key)});
graphFocus(svg,keys);if(q&&!keys.length)svg.querySelectorAll('.graph-node,.graph-edge').forEach(function(n){n.classList.add('faded')})}
function resetGraph(button){var chart=button.closest('.chart');chart.querySelector('input').value='';graphFocus(chart.querySelector('svg'),[])}
function revealTarget(){var id=location.hash.slice(1),el=document.getElementById(id);if(!el)return;
if(el.tagName==='DETAILS')el.open=true;var p=el.parentElement;while(p){if(p.tagName==='DETAILS')p.open=true;p=p.parentElement}el.scrollIntoView()}
window.addEventListener('hashchange',function(){if(location.hash.indexOf('#read-')===0)openChapter(parseInt(location.hash.slice(6),10),true);else revealTarget()});
var RS={size:parseInt(localStorage.getItem('nl_rsize')||'19',10),
serif:localStorage.getItem('nl_rserif')!=='0',wide:localStorage.getItem('nl_rwide')==='1',
theme:localStorage.getItem('nl_rtheme')||'paper'};
function applyReader(){document.documentElement.style.setProperty('--reader-size',RS.size+'px');
document.documentElement.classList.toggle('sans-reading',!RS.serif);
document.documentElement.classList.toggle('sepia',RS.theme==='sepia');
document.documentElement.classList.toggle('night',RS.theme==='dark');
var w=document.getElementById('rd-wrap');if(w)w.classList.toggle('wide',RS.wide);
var a=document.getElementById('rb-serif'),b=document.getElementById('rb-sans'),
c=document.getElementById('rw-std'),d=document.getElementById('rw-wide');
if(a)a.classList.toggle('on',RS.serif);if(b)b.classList.toggle('on',!RS.serif);
if(c)c.classList.toggle('on',!RS.wide);if(d)d.classList.toggle('on',RS.wide);
document.querySelectorAll('.rd-tools .themes i').forEach(function(t){
t.classList.toggle('on',t.classList.contains('th-'+RS.theme))})}
function readerSize(v){RS.size=Math.min(30,Math.max(15,RS.size+v));localStorage.setItem('nl_rsize',RS.size);applyReader()}
function readerFamily(s){RS.serif=s;localStorage.setItem('nl_rserif',s?'1':'0');applyReader()}
function readerWide(w){RS.wide=w;localStorage.setItem('nl_rwide',w?'1':'0');applyReader()}
function readerTheme(t){RS.theme=t;localStorage.setItem('nl_rtheme',t);applyReader()}
applyReader();
(function(){var h=location.hash;if(h.indexOf('#read-')===0){var n=parseInt(h.slice(6),10);if(n)openChapter(n,true)}
else if(h==='#read'){mode('read',true)}else{mode('settings',true);revealTarget()}})();