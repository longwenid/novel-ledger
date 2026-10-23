// Keep only the current settings surface and current chapter in the DOM.
var previewMode = mode, previewRequest = null, previewQuery = '', previewTimer = null;
function previewMessage(target, text) {
  target.replaceChildren();
  var p = document.createElement('p'); p.className = 'note'; p.textContent = text;
  target.appendChild(p);
}
async function loadFragment(path, target, after) {
  if (location.protocol === 'file:') return;
  if (previewRequest) previewRequest.abort();
  var request = new AbortController(); previewRequest = request;
  previewMessage(target, '正在读取…');
  try {
    var response = await fetch('api/' + path, {cache: 'no-store', signal: request.signal});
    var data = await response.json();
    if (!response.ok) throw new Error(data.message || '读取失败');
    if (request.signal.aborted) return;
    target.innerHTML = data.html;
    document.querySelector('.brand b').textContent = data.title;
    document.querySelector('.brand span').textContent = '分支 ' + data.branch + ' · ' + data.chapters + ' 章 · ' + data.written.toLocaleString() + ' 汉字';
    document.title = data.title + ' · 作品预览';
    if (after) after();
  } catch (error) {
    if (error.name !== 'AbortError') previewMessage(target, '读取失败：' + error.message + '。确认预览命令仍在运行后点击刷新重试。');
  }
}
function settingsKey(hash) {
  var key = hash.split('-')[0];
  if (key === 'entity' || key === 'place') return 'ledger';
  return ['overview','contract','world','outline','plans','understanding','ledger','drift','audit'].includes(key) ? key : 'overview';
}
function showSettings(hash) {
  previewMode('settings', true);
  return loadFragment('section/' + settingsKey(hash), document.getElementById('live-settings'), revealTarget);
}
mode = function(m) {
  if (location.protocol === 'file:') { previewMode('settings', true); return; }
  if (m === 'read') openIndex();
  else { history.replaceState(null, '', '#overview'); showSettings('overview'); }
};
openChapter = function(n, keep) {
  if (location.protocol === 'file:') return;
  clearTimeout(previewTimer);
  previewMode('read', true);
  document.getElementById('ch-index').hidden = true;
  var slot = document.getElementById('chapter-slot'); slot.hidden = false;
  if (!keep) history.replaceState(null, '', '#read-' + n);
  return loadFragment('chapter/' + n, slot, applyReader);
};
function loadIndex(offset) {
  if (location.protocol === 'file:') return;
  clearTimeout(previewTimer);
  previewMode('read', true);
  document.getElementById('chapter-slot').replaceChildren();
  var index = document.getElementById('ch-index'); index.hidden = false;
  return loadFragment('index?offset=' + offset + '&q=' + encodeURIComponent(previewQuery), index, applyReader);
}
openIndex = function() { history.replaceState(null, '', '#read'); return loadIndex(0); };
filterIndex = function(q) {
  previewQuery = q.trim(); clearTimeout(previewTimer);
  previewTimer = setTimeout(openIndex, 200);
};
function refreshPreview() {
  clearTimeout(previewTimer);
  var hash = location.hash.slice(1);
  if (/^read-\d+$/.test(hash)) openChapter(Number(hash.slice(5)), true);
  else if (hash === 'read') loadIndex(0);
  else showSettings(hash);
}
window.addEventListener('hashchange', refreshPreview);
if (location.protocol !== 'file:') {
  document.getElementById('preview-help').hidden = true;
  var refresh = document.createElement('button'); refresh.textContent = '刷新';
  refresh.onclick = refreshPreview; document.querySelector('.tabs').appendChild(refresh);
  refreshPreview();
} else previewMode('settings', true);
applyReader();
