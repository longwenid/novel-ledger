"""Derived single-file book view: one static HTML page over the whole project.

Two modes share one file: 看设定 renders every canon-level surface as cards (contract,
opening choices, world model, designs, rolling plans, profiles, ledger state, review
records, audit), 读正文 is a reader for the committed prose. Structured cards come first
and raw JSON is kept only as a collapsed fallback. No server, no external assets, no
writes to the project: the database stays the single source of truth.
"""
from __future__ import annotations

import html
import json
import time
from pathlib import Path
from .contracts import CONTRACT_FIELDS, LENSES, VOLUME_TURNS
from .delivery import atomic_write
from .planning import volume_for
from .world import LABELS as WORLD_LABELS

FIELD_LABELS = {'title': '书名', 'reader_promise': '读者承诺', 'ending': '终局', 'genre': '题材',
                'story_engine': '推进引擎', 'opposition': '主要对抗', 'world_premise': '世界前提',
                'voice': '文风', 'allow_special_mechanism': '允许特殊机制', 'red_lines': '禁区',
                'style_traits': '文风要点', 'relationships': '核心关系', 'world_rules': '世界规则',
                'protagonist_setup': '主角设定', 'entities': '初始人物', 'initial_resources': '初始资源',
                'volumes': '分卷', 'word_range': '总字数区间', 'chapter_min': '章幅下限', 'chapter_max': '章幅上限',
                'chapter_aim': '章幅目标', 'planning_window': '规划窗口', 'review_interval': '复审间隔',
                'review_chunk': '复审块大小', 'initial_facts': '初始事实', 'places': '初始地点',
                'placements': '初始站位', 'arcs': '人物弧'}
SUB_LABELS = {'id': '标识', 'name': '名称', 'kind': '类型', 'aliases': '别名', 'identity': '身份',
              'desire': '欲望', 'limit': '底线', 'purpose': '卷职责', 'end': '卷末章', 'holder': '持有者',
              'asset': '资产', 'unit': '单位', 'quantity': '数量', 'entity': '实体', 'key': '键', 'value': '值'}
NODE_LABELS = {'id': '节点', 'line': '线索', 'cause': '起因', 'choice': '选择', 'cost': '代价',
               'outcome': '结果', 'disclosure': '披露安排', 'depends_on': '依赖'}
PLAN_LABELS = {'goal': '目标', 'obstacle': '阻碍', 'choice': '选择', 'cost': '代价', 'change': '变化',
               'ending': '章末', 'node_ids': '设计节点', 'participants': '参与人', 'world_refs': '世界引用',
               'obligations': '承接义务', 'schedule': '硬日程', 'new_entities': '新人物'}
HOOK_LABELS = {'open': '待兑现', 'paid': '已兑现', 'closed': '已关闭'}
STANCE_LABELS = {'knows': '确知', 'believes': '相信', 'suspects': '怀疑', 'disproved': '已推翻'}
CHECK_LABELS = {'coverage': '覆盖', 'continuity': '连续性', 'resources': '资源', 'knowledge': '知情',
                'time': '时间', 'world_rules': '世界规则', 'space': '空间', 'read_on': '追读',
                'character': '人物', 'change': '变化', 'emotion_cost': '情绪代价', 'language': '语言',
                'repetition': '重复', 'substance': '有效展开', 'causality': '因果', 'character_arcs': '人物弧线',
                'payoffs': '兑现', 'pacing': '节奏'}
VERDICT_LABELS = {'pass': '通过', 'fix': '待修'}
STATUS_LABELS = {'preparing': '开书准备', 'running': '进行中', 'paused': '已暂停', 'completed': '已完本'}
SECTIONS = (('overview', '概览'), ('contract', '创作约定'), ('world', '世界与选择'), ('design', '设计与节点'),
            ('plans', '章计划'), ('profiles', '人物档案'), ('ledger', '事实账本'), ('reviews', '章审记录'),
            ('audit', '账本核验'))

CSS = ''':root{--paper:#fbf8f1;--bg:#f2eee6;--card:#fffdf8;--ink:#2b261e;--muted:#8a8070;--line:#e3dbca;
--accent:#8a6a35;--accent-soft:#f2ead9;--ok:#3c6e3a;--ok-soft:#e4efdf;--bad:#8a3226;--bad-soft:#f3ded8;
--reader-size:19px;--reader-width:38em;
--serif:Georgia,"Times New Roman","Noto Serif SC","Source Han Serif SC",SimSun,serif;
--sans:"Microsoft YaHei","PingFang SC","Hiragino Sans GB",system-ui,sans-serif}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);font-size:15px;line-height:1.75}
a{color:var(--accent)}
.bar{position:sticky;top:0;z-index:30;display:flex;align-items:center;gap:12px;padding:8px 18px;background:var(--bg);
border-bottom:1px solid var(--line);flex-wrap:wrap}
.bar .menu{border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:8px;padding:4px 11px;
font-size:15px;cursor:pointer;font-family:inherit}
.bar .brand{display:flex;flex-direction:column;line-height:1.25;min-width:0}
.bar .brand b{font-family:var(--serif);font-size:16.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bar .brand span{color:var(--muted);font-size:11.5px;white-space:nowrap}
.bar .grow{flex:1}
.tabs{display:flex;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}
.tabs button{border:none;background:transparent;color:var(--ink);cursor:pointer;font-size:13.5px;padding:6px 15px;font-family:inherit}
.tabs button.active{background:var(--accent);color:var(--paper);font-weight:700}
.wrap{display:grid;grid-template-columns:196px minmax(0,1fr);gap:22px;padding:18px 22px 0}
body.side-off .wrap{grid-template-columns:minmax(0,1fr)}
body.side-off aside{display:none}
aside{position:sticky;top:52px;align-self:start;max-height:calc(100vh - 60px);overflow-y:auto;padding-bottom:30px}
aside a{display:block;padding:4px 11px;margin:1px 0;border-radius:7px;color:var(--ink);text-decoration:none;font-size:13.5px}
aside a:hover{background:var(--accent-soft)}
.toc-select{width:100%;padding:6px;border:1px solid var(--line);border-radius:8px;background:var(--card);
color:var(--ink);margin-top:10px;font-family:inherit}
main{min-width:0;padding-bottom:40px}
h2{font-family:var(--serif);font-size:21px;margin:30px 0 4px;padding-top:6px;border-top:1px solid var(--line)}
h2:first-child{border-top:none;margin-top:6px}
h3{font-family:var(--serif);font-size:16.5px;margin:18px 0 6px}
.sub{color:var(--muted);font-size:12.5px;margin-bottom:10px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 15px;margin:9px 0}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(132px,1fr));gap:9px;margin:10px 0}
.stat{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 13px}
.stat b{display:block;font-family:var(--serif);font-size:21px}
.stat span{color:var(--muted);font-size:12px}
table.t{width:100%;border-collapse:collapse;font-size:14px}
table.t th{text-align:left;vertical-align:top;white-space:nowrap;color:var(--muted);font-weight:600;padding:4px 12px 4px 0;width:7.5em}
table.t td{padding:4px 0;vertical-align:top}
.pill{display:inline-block;padding:1px 8px;border-radius:9px;background:var(--accent-soft);color:var(--accent);
font-size:12px;margin:0 5px 3px 0;white-space:nowrap}
.pill.ok{background:var(--ok-soft);color:var(--ok)}
.pill.bad{background:var(--bad-soft);color:var(--bad)}
.pill.dim{background:transparent;border:1px solid var(--line);color:var(--muted)}
.note{color:var(--muted);font-size:12.5px}
ul.tight{margin:6px 0;padding-left:19px}
ul.tight li{margin:2px 0}
details{margin:7px 0;border:1px solid var(--line);border-radius:10px;background:var(--card);padding:8px 13px}
details>summary{cursor:pointer;font-size:14px}
details[open]>summary{margin-bottom:7px;border-bottom:1px solid var(--line);padding-bottom:6px}
pre{white-space:pre-wrap;word-break:break-word;font-size:12px;background:var(--bg);border:1px solid var(--line);
border-radius:8px;padding:9px;max-height:26em;overflow:auto}
footer{color:var(--muted);font-size:12px;padding:16px 22px 30px;border-top:1px solid var(--line);margin-top:20px}
#view-read{background:var(--paper);border-radius:12px;padding:14px 20px 30px}
.rd-tools{display:flex;align-items:center;gap:7px;flex-wrap:wrap;position:sticky;top:52px;z-index:20;
background:var(--paper);padding:8px 0;border-bottom:1px solid var(--line);margin-bottom:14px}
.rd-tools .lab{color:var(--muted);font-size:12px}
.rd-tools button{border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:7px;
padding:3px 10px;font-size:12.5px;cursor:pointer;font-family:inherit}
.rd-tools button.on{background:var(--accent);color:var(--paper);border-color:var(--accent)}
.rd-tools .grow{flex:1;min-width:8px}
.rd-tools input{border:1px solid var(--line);border-radius:7px;padding:4px 9px;font-size:12.5px;
background:var(--card);color:var(--ink);font-family:inherit;min-width:9em}
.rd-tools .themes i{display:inline-block;width:15px;height:15px;border-radius:50%;border:1px solid var(--muted);
margin-right:5px;cursor:pointer;vertical-align:-3px}
.rd-tools .themes i.on{outline:2px solid var(--accent);outline-offset:1px}
.rd-wrap{max-width:var(--reader-width);margin:0 auto}
.rd-wrap.wide{max-width:52em}
.book{font-family:var(--serif);text-align:center;font-size:23px;margin:26px 0 4px}
.book-sub{text-align:center;color:var(--muted);font-size:12.5px;margin-bottom:22px}
.vol{font-family:var(--serif);font-size:14px;color:var(--accent);margin:16px 0 5px;border-bottom:1px solid var(--line);padding-bottom:4px}
.item{display:grid;grid-template-columns:4.2em 1fr;gap:2px 10px;padding:7px 9px;border-radius:8px;cursor:pointer}
.item:hover{background:var(--accent-soft)}
.item .no{color:var(--muted);font-size:12.5px}
.item .ttl{font-family:var(--serif);font-size:15px}
.item .sum{grid-column:2;color:var(--muted);font-size:12.5px}
.chapter{max-width:var(--reader-width);margin:0 auto}
.ch-head{text-align:center;margin:22px 0 18px}
.ch-head .orn{color:var(--accent);letter-spacing:.5em;font-size:12px}
.ch-head h3{font-size:22px;margin:8px 0 4px}
.ch-head .meta{color:var(--muted);font-size:12.5px}
.prose{font-family:var(--serif);font-size:var(--reader-size);line-height:2}
.prose p{margin:0 0 1.05em;text-indent:2em}
html.sans-reading .prose{font-family:var(--sans)}
html.sepia #view-read{background:#f4ead6}
html.night{--paper:#211e18;--card:#211e18;--bg:#191713;--ink:#e9e2d2;--muted:#9c9280;--line:#3b352a;
--accent:#d6b478;--accent-soft:#332c1e;--ok:#a5c99a;--ok-soft:#26331f;--bad:#dfa294;--bad-soft:#3c241d}
.ch-nav{display:flex;align-items:center;gap:10px;justify-content:center;margin:30px 0 6px;flex-wrap:wrap}
.ch-nav button{border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:8px;
padding:5px 14px;font-size:13px;cursor:pointer;font-family:inherit}
.ch-nav button:disabled{opacity:.45;cursor:default}
.ch-nav .pos{color:var(--muted);font-size:12.5px}
@media (max-width:880px){.wrap{grid-template-columns:minmax(0,1fr);padding:14px}aside{position:static;max-height:none}
.rd-tools{top:auto;position:static}}
@media print{.bar,aside,.rd-tools,.ch-nav{display:none!important}body{background:#fff}#view-settings{display:none}
#view-read{display:block!important;background:#fff}.chapter{display:block!important;page-break-after:always;max-width:none}
.item{display:none}}'''

JS = '''function mode(m,keep){var r=document.getElementById('view-read'),s=document.getElementById('view-settings');
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
else if(h==='#read'){mode('read',true)}else{mode('settings',true)}})();'''


def _esc(value):
    return html.escape(str(value), quote=True)


def _pretty(value):
    return _esc(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))


def _pills(items, cls=''):
    return ''.join('<span class="pill %s">%s</span>' % (cls, _esc(item)) for item in items)


def _raw(value):
    return '<details><summary class="note">原始数据</summary><pre>' + _pretty(value) + '</pre></details>'


def _empty(label):
    return '<p class="note">（尚无' + _esc(label) + '）</p>'


def _short(value, limit=64):
    text = str(value)
    return text if len(text) <= limit else text[:limit] + '…'


def _display(value):
    if isinstance(value, list):
        if not value:
            return '<span class="note">（空）</span>'
        if all(not isinstance(v, (dict, list)) for v in value):
            return _pills(value)
        return '<ul class="tight">' + ''.join(
            '<li>' + (', '.join('%s：%s' % (_esc(SUB_LABELS.get(k, k)), _esc(item[k])) for k in item)
                      if isinstance(item, dict) else _esc(item)) + '</li>' for item in value) + '</ul>'
    if isinstance(value, dict):
        if not value:
            return '<span class="note">（空）</span>'
        # inline, not nested tables: these objects sit inside a table cell of their own
        return _pills('%s：%s' % (SUB_LABELS.get(k, k), v) for k, v in value.items())
    if isinstance(value, bool):
        return '是' if value else '否'
    if value in (None, ''):
        return '<span class="note">（未填）</span>'
    return _esc(value)


def _records(items, label_key):
    """Cards for a list of dict records, one table row per field."""
    return ''.join('<div class="card"><b>' + _esc(item.get(label_key, '')) + '</b><table class="t">' + ''.join(
        '<tr><th>' + _esc(SUB_LABELS.get(k, k)) + '</th><td>' + _display(v) + '</td></tr>'
        for k, v in item.items() if k != label_key) + '</table></div>' for item in items)


def _overview(book, contract, rows, state, open_hooks, report, written):
    pieces = ['<h2 id="overview">概览</h2><div class="sub">数据库派生只读视图 · 真源 novel.sqlite3 · 可随时重新生成</div><div class="cards">',
              '<div class="stat"><b>' + str(len(rows)) + '</b><span>已提交章节</span></div>',
              '<div class="stat"><b>' + format(written, ',') + '</b><span>累计汉字</span></div>',
              '<div class="stat"><b>' + str(len(open_hooks)) + '</b><span>待兑现承诺</span></div>',
              '<div class="stat"><b>' + _esc(STATUS_LABELS.get(book.get('status'), book.get('status') or '')) + '</b><span>运行状态</span></div>',
              '<div class="stat"><b>' + _esc(book.get('target') if book.get('target') is not None else '—') + '</b><span>授权目标章</span></div>',
              '<div class="stat"><b>' + ('是' if report['ok'] else '否') + '</b><span>账本核验</span></div></div>']
    if contract:
        band = contract['word_range']
        pieces.append('<div class="card"><table class="t">'
                      '<tr><th>目标区间</th><td>' + format(band[0], ',') + ' ~ ' + format(band[1], ',') + ' 汉字</td></tr>'
                      '<tr><th>完成度</th><td>' + format(written, ',') + ' 汉字（占目标下限 '
                      + (str(min(100, round(100 * written / band[0]))) + '%' if band[0] else '—') + '）</td></tr>'
                      '<tr><th>章幅</th><td>' + str(contract['chapter_min']) + ' ~ ' + str(contract['chapter_max'])
                      + ' 汉字，目标 ' + str(contract['chapter_aim']) + '</td></tr>'
                      '<tr><th>分卷</th><td>' + str(len(contract['volumes'])) + ' 卷，全书末章 '
                      + str(contract['volumes'][-1]['end']) + '</td></tr></table></div>')
    else:
        pieces.append('<p class="note">约定尚未激活：项目仍在开书阶段。</p>')
    if state.get('clock'):
        pieces.append('<p class="note">主线时钟：第 ' + str(state['clock']) + ' 天</p>')
    if book.get('pause_reason'):
        pieces.append('<p class="note">暂停原因：' + _esc(book['pause_reason']) + '</p>')
    if report['problems']:
        pieces.append('<div class="card" style="border-color:var(--bad)"><b>核验发现的问题</b><ul class="tight">'
                      + ''.join('<li>' + _esc(p) + '</li>' for p in report['problems']) + '</ul></div>')
    return ''.join(pieces)


def _contract(contract):
    pieces = ['<h2 id="contract">创作约定</h2><div class="sub">作者认可的全书边界；系统不为过关而改约</div><div class="card"><table class="t">']
    for row in CONTRACT_FIELDS:
        pieces.append('<tr><th>' + _esc(FIELD_LABELS.get(row['key'], row['key'])) + '</th><td>'
                      + _display(contract.get(row['key'])) + '</td></tr>')
    pieces.append('</table></div>')
    return ''.join(pieces) + _raw(contract)


def _world(book):
    pieces = ['<h2 id="world">世界与选择</h2>']
    opening = book.get('creation')
    if opening and opening.get('selections'):
        pieces.append('<h3>逐门选择</h3>')
        for row in opening['selections']:
            option = row['option']
            pieces.append('<div class="card"><b>' + _esc(row['gate']) + ' · ' + _esc(option.get('title', '')) + '</b>'
                          + '<p>' + _esc(option.get('premise', '')) + '</p><p class="note">推进：'
                          + _esc(option.get('driver', '')) + '　代价：' + _esc(option.get('tradeoff', '')) + '</p>'
                          + '<table class="t">' + ''.join('<tr><th>' + _esc(k) + '</th><td>' + _display(v) + '</td></tr>'
                                                          for k, v in option.get('value', {}).items()) + '</table>'
                          + (('<p class="note">作者原话：' + _esc(row.get('source', '')) + '</p>') if row.get('source') else '')
                          + '</div>')
    model = book.get('world')
    if not model:
        pieces.append('<p class="note">世界模型尚未经独立核验通过。</p>')
        return ''.join(pieces)
    pieces.append('<h3>世界模型</h3><div class="card"><table class="t">'
                  '<tr><th>前提</th><td>' + _esc(model['premise']) + '</td></tr>'
                  '<tr><th>长篇承载</th><td>' + _esc(model['story_capacity']) + '</td></tr></table></div>')
    for section, records in model.items():
        if section in ('selection_hash', 'premise', 'story_capacity') or not records:
            continue
        pieces.append('<h3>' + _esc(WORLD_LABELS.get(section, section)) + ' <span class="pill dim">'
                      + str(len(records)) + ' 条</span></h3>')
        for record in records:
            links = record.get('links') or []
            pieces.append('<div class="card"><b>' + _esc(record.get('id', '')) + '</b><table class="t">' + ''.join(
                '<tr><th>' + _esc(SUB_LABELS.get(k, k)) + '</th><td>' + _display(v) + '</td></tr>'
                for k, v in record.items() if k not in ('id', 'links')) + '</table>'
                + ('<p class="note">关联：' + _pills(links) + '</p>' if links else '') + '</div>')
    return ''.join(pieces)


def _designs(book):
    pieces = ['<h2 id="design">设计与因果节点</h2>']
    designs = book.get('designs') or {}
    if not designs:
        return ''.join(pieces) + _empty('设计')
    for scope, design in designs.items():
        pieces.append('<h3>' + _esc('全书' if scope == 'book' else scope) + '</h3><div class="card"><table class="t">'
                      '<tr><th>意图</th><td>' + _esc(design.get('intent', '')) + '</td></tr>'
                      '<tr><th>终局条件</th><td>' + _esc(design.get('ending_conditions', '')) + '</td></tr></table></div>')
        for node in design.get('nodes', []):
            pieces.append('<details><summary><span class="pill">' + _esc(node.get('id', '')) + '</span>'
                          + _esc(node.get('line', '')) + ' · ' + _esc(_short(node.get('cause', ''))) + '</summary><table class="t">'
                          + ''.join('<tr><th>' + _esc(NODE_LABELS.get(k, k)) + '</th><td>' + _display(v) + '</td></tr>'
                                    for k, v in node.items() if k not in ('id', 'line')) + '</table></details>')
    return ''.join(pieces)


def _plans(book, contract):
    pieces = ['<h2 id="plans">章计划</h2>']
    plans = book.get('plans') or {}
    if not plans:
        return ''.join(pieces) + _empty('章计划')
    numbers = sorted(int(n) for n in plans)
    pieces.append('<p class="note">已冻结 ' + str(len(numbers)) + ' 章计划：第 ' + str(numbers[0]) + ' ~ '
                  + str(numbers[-1]) + ' 章（滚动窗口，未写部分可重规划）</p>')
    for number in numbers:
        plan = plans[str(number)]
        volume = volume_for(contract, number) if contract else None
        head = '<span class="pill">第' + str(number) + '章</span>'
        if volume:
            head += '<span class="pill dim">' + _esc(volume['id']) + '</span>'
        pieces.append('<details><summary>' + head + _esc(_short(plan.get('goal', ''))) + '</summary><table class="t">'
                      + ''.join('<tr><th>' + _esc(PLAN_LABELS.get(k, k)) + '</th><td>' + _display(v) + '</td></tr>'
                                for k, v in plan.items() if k != 'chapter') + '</table></details>')
    return ''.join(pieces)


def _profiles(book):
    pieces = ['<h2 id="profiles">人物档案</h2>']
    profiles = book.get('profiles') or {}
    if not profiles:
        return ''.join(pieces) + _empty('人物档案')
    for profile in profiles.values():
        pieces.append('<div class="card"><b>' + _esc(profile.get('entity', '')) + '</b><table class="t">' + ''.join(
            '<tr><th>' + _esc(SUB_LABELS.get(k, k)) + '</th><td>' + _display(v) + '</td></tr>'
            for k, v in profile.items() if k != 'entity') + '</table></div>')
    return ''.join(pieces)


def _ledger(state):
    pieces = ['<h2 id="ledger">事实账本</h2><div class="sub">由已提交章节的事件结算而来；每条事实都能追溯到正文引文</div>']
    if not state:
        return ''.join(pieces) + _empty('事实')
    entities = state.get('entities') or {}
    if entities:
        pieces.append('<h3>人物</h3><div class="cards">')
        for item in entities.values():
            aliases = item.get('aliases') or []
            pieces.append('<div class="stat"><b>' + _esc(item.get('name', '')) + '</b><span>' + _esc(item.get('kind', ''))
                          + (' · ' + _esc('、'.join(aliases)) if aliases else '') + '</span></div>')
        pieces.append('</div>')
    name_of = lambda ident: entities.get(ident, {}).get('name', ident)
    for key, label in (('facts', '状态事实'), ('relations', '关系'), ('historical_assertions', '历史断言'),
                       ('developments', '人物成长')):
        records = state.get(key) or {}
        if records:
            pieces.append('<h3>' + label + ' <span class="pill dim">' + str(len(records)) + '</span></h3><div class="card"><table class="t">'
                          + ''.join('<tr><th>' + _esc(k) + '</th><td>' + _display(v) + '</td></tr>'
                                    for k, v in sorted(records.items())) + '</table></div>')
    resources = state.get('resources') or {}
    if resources:
        pieces.append('<h3>资源</h3><div class="card"><table class="t">')
        for key, value in sorted(resources.items()):
            holder, asset, unit = json.loads(key)
            pieces.append('<tr><th>' + _esc(name_of(holder)) + '</th><td>' + _esc(asset) + ' '
                          + _esc(value) + ' ' + _esc(unit) + '</td></tr>')
        pieces.append('</table></div>')
    knowledge = state.get('knowledge') or {}
    if knowledge:
        pieces.append('<h3>知情边界 <span class="pill dim">' + str(len(knowledge)) + '</span></h3>')
        for key, item in sorted(knowledge.items()):
            entity, topic = key.split(':', 1)
            pieces.append('<div class="card"><b>' + _esc(name_of(entity)) + '</b><span class="pill">'
                          + _esc(STANCE_LABELS.get(item.get('stance'), item.get('stance', ''))) + '</span>'
                          + '<span class="note">' + _esc(topic) + '</span><p>' + _esc(item.get('claim', '')) + '</p>'
                          + '<p class="note">来源：' + _esc(item.get('source', '')) + '</p></div>')
    hooks = state.get('hooks') or {}
    if hooks:
        pieces.append('<h3>承诺 <span class="pill dim">' + str(len(hooks)) + '</span></h3>')
        for ident, hook in sorted(hooks.items()):
            status = hook.get('status')
            cls = ' ok' if status == 'paid' else (' bad' if status == 'open' else ' dim')
            pieces.append('<div class="card"><b>' + _esc(ident) + '</b><span class="pill' + cls + '">'
                          + _esc(HOOK_LABELS.get(status, status or '')) + '</span><p>' + _esc(hook.get('text', '')) + '</p>'
                          + '<p class="note">最迟第 ' + _esc(hook.get('due', '—')) + ' 章 · 埋设于第 '
                          + _esc(hook.get('seed_chapter', '—')) + ' 章 · 延期 ' + _esc(hook.get('extensions', 0)) + '/2</p></div>')
    places = state.get('places') or {}
    if places:
        pieces.append('<h3>地点与站位</h3><div class="card"><table class="t">')
        for item in places.values():
            parent = places.get(item['parent'], {}).get('name') if item.get('parent') else None
            pieces.append('<tr><th>' + _esc(item.get('name', '')) + '</th><td>'
                          + (_esc('上级：' + parent) if parent else '—') + '</td></tr>')
        for entity, place in (state.get('placements') or {}).items():
            pieces.append('<tr><th>' + _esc(name_of(entity)) + '</th><td>位于 '
                          + _esc(places.get(place, {}).get('name', place)) + '</td></tr>')
        pieces.append('</table></div>')
    return ''.join(pieces) + _raw({'clock': state.get('clock'), 'clock_threads': state.get('clock_threads')})


def _reviews(rows, repo):
    pieces = ['<h2 id="reviews">章审记录</h2><div class="sub">事实与阅读两类独立核验；审稿者与执笔者不同人</div>']
    if not rows:
        return ''.join(pieces) + _empty('章审记录')
    for row in rows:
        review = repo.read_document(row['review'])
        facts = review.get('facts') or {}
        reader = review.get('reader') or {}
        pieces.append('<details><summary><span class="pill">第' + str(row['n']) + '章</span>'
                      + '<span class="pill ' + ('ok' if facts.get('verdict') == 'pass' else 'bad') + '">事实 '
                      + _esc(VERDICT_LABELS.get(facts.get('verdict'), facts.get('verdict') or '')) + '</span>'
                      + '<span class="pill ' + ('ok' if reader.get('verdict') == 'pass' else 'bad') + '">阅读 '
                      + _esc(VERDICT_LABELS.get(reader.get('verdict'), reader.get('verdict') or '')) + '</span></summary>'
                      '<table class="t"><tr><th>事实摘要</th><td>' + _esc(facts.get('summary', '')) + '</td></tr>'
                      '<tr><th>时间推进</th><td>' + _esc(facts.get('elapsed_days', '')) + ' 天</td></tr>'
                      '<tr><th>结算事件</th><td>' + str(len(facts.get('events') or [])) + ' 条</td></tr></table>')
        for label, receipt in (('事实', facts), ('阅读', reader)):
            for check in receipt.get('checks') or []:
                pieces.append('<p class="note">' + label + ' · ' + _esc(CHECK_LABELS.get(check.get('id'), check.get('id', '')))
                              + '：<span class="pill ' + ('ok' if check.get('result') == 'pass' else 'bad') + '">'
                              + _esc(VERDICT_LABELS.get(check.get('result'), check.get('result') or '')) + '</span>'
                              + _esc(check.get('reason', '')) + '</p>')
            for finding in receipt.get('findings') or []:
                pieces.append('<p class="note">发现（' + _esc(finding.get('severity', '')) + '）：'
                              + _esc(finding.get('reason', '')) + '</p>')
        pieces.append('</details>')
    return ''.join(pieces)


def _audit(book, report):
    pieces = ['<h2 id="audit">账本核验</h2><div class="sub">promote 与 complete 会复查同一组条件</div>'
              '<div class="card"><table class="t">'
              '<tr><th>结论</th><td>' + ('通过' if report['ok'] else '发现问题') + '</td></tr>'
              '<tr><th>已入库章节</th><td>' + str(report['chapters']) + '</td></tr>'
              '<tr><th>投影一致</th><td>' + ('是' if report['projection'] else '否') + '</td></tr>'
              '<tr><th>设计世代</th><td>' + str(book.get('revision')) + '</td></tr></table></div>']
    if report['problems']:
        pieces.append('<ul class="tight">' + ''.join('<li>' + _esc(p) + '</li>' for p in report['problems']) + '</ul>')
    pieces.append('<p class="note">开书透镜：' + _esc('、'.join(label for label, _p, _s in LENSES)) + '</p>')
    pieces.append('<p class="note">卷级转折方法：' + _esc('、'.join(label for label, _t in VOLUME_TURNS)) + '</p>')
    return ''.join(pieces)


def _reader(rows, repo, contract, book):
    """Reader mode body: index plus one hidden section per chapter."""
    pieces = ['<div id="view-read" hidden>']
    if not rows:
        return ''.join(pieces) + '<div class="rd-wrap"><p class="note" style="padding:24px">尚无已提交章节。</p></div></div>'
    pieces.append('<div class="rd-tools"><span class="lab">字号</span>'
                  '<button onclick="readerSize(-1)">A−</button><button onclick="readerSize(1)">A＋</button>'
                  '<span class="grow"></span><span class="lab">版心</span>'
                  '<button id="rw-std" onclick="readerWide(false)">适中</button>'
                  '<button id="rw-wide" onclick="readerWide(true)">加宽</button>'
                  '<span class="grow"></span><span class="lab">纸色</span><span class="themes">'
                  '<i class="th-paper on" onclick="readerTheme(\'paper\')" style="background:#fbf8f1" title="纸白"></i>'
                  '<i class="th-sepia" onclick="readerTheme(\'sepia\')" style="background:#f4ead6" title="羊皮"></i>'
                  '<i class="th-dark" onclick="readerTheme(\'dark\')" style="background:#211e18" title="夜间"></i></span>'                  '<span class="grow"></span><button id="rb-serif" onclick="readerFamily(true)">衬线</button>'
                  '<button id="rb-sans" onclick="readerFamily(false)">黑体</button>'
                  '<span class="grow"></span><input placeholder="筛选章节…" oninput="filterIndex(this.value)">'
                  '<button onclick="openChapter(' + str(rows[0]['n']) + ')">从第一章读起</button></div>')
    pieces.append('<div class="rd-wrap" id="rd-wrap"><div id="ch-index"><div class="book">❦ '
                  + _esc(contract['title'] if contract else '书稿') + ' ❦</div><div class="book-sub">'
                  + str(len(rows)) + ' 章 · ' + format(book.get('written_han') or 0, ',') + ' 汉字 · 目录</div>')
    seen = None
    for row in rows:
        volume = volume_for(contract, row['n']) if contract else None
        if volume and volume['id'] != seen:
            seen = volume['id']
            pieces.append('<div class="vol">卷 ' + _esc(volume['id']) + ' · ' + _esc(volume.get('purpose', '')) + '</div>')
        pieces.append('<div class="item" onclick="openChapter(' + str(row['n']) + ')"><span class="no">第'
                      + str(row['n']) + '章</span><span class="ttl">' + _esc(row.get('title') or '') + '</span>'
                      '<span class="sum">' + _esc(row.get('summary') or '') + '</span></div>')
    pieces.append('</div>')
    for index, row in enumerate(rows):
        paragraphs = [line.strip() for line in repo.read_document(row['prose']).split('\n') if line.strip()]
        previous = rows[index - 1]['n'] if index else 0
        following = rows[index + 1]['n'] if index + 1 < len(rows) else 0
        pieces.append('<section class="chapter" id="read-' + str(row['n']) + '" hidden><div class="ch-head">'
                      '<div class="orn">❖ ❖ ❖</div><h3>第' + str(row['n']) + ' 章 ' + _esc(row.get('title') or '')
                      + '</h3><div class="meta">' + format(row.get('han') or 0, ',') + ' 汉字 · '
                      + _esc(row.get('summary') or '') + '</div></div><div class="prose">'
                      + ''.join('<p>' + _esc(p) + '</p>' for p in paragraphs) + '</div><div class="ch-nav">'
                      '<button ' + ('disabled' if not previous else 'onclick="openChapter(' + str(previous) + ')"')
                      + '>← 上一章</button><button onclick="openIndex()">目录</button><span class="pos">'
                      + str(index + 1) + ' / ' + str(len(rows)) + '</span><button '
                      + ('disabled' if not following else 'onclick="openChapter(' + str(following) + ')"')
                      + '>下一章 →</button></div></section>')
    return ''.join(pieces) + '</div></div>'


def _audit_report(book, rows):
    """Read-only consistency report. Never raises; findings only."""
    problems = []
    contract = book.get('contract')
    if contract:
        if sum(row.get('han') or 0 for row in rows) != (book.get('written_han') or 0):
            problems.append('汉字计数投影与各章之和不一致。')
        for row in rows:
            if not (contract['chapter_min'] <= (row.get('han') or 0) <= contract['chapter_max']):
                problems.append('第 ' + str(row['n']) + ' 章篇幅超出约定区间。')
        if [row['n'] for row in rows] != list(range(1, len(rows) + 1)):
            problems.append('正式章节号不连续。')
    head = rows[-1]['n'] if rows else 0
    for ident, hook in (book.get('state') or {}).get('hooks', {}).items():
        if hook.get('status') == 'open' and hook.get('due') and head and hook['due'] <= head:
            problems.append('承诺 ' + str(ident) + ' 已过期未兑现。')
    return {'ok': not problems, 'chapters': len(rows),
            'projection': sum(row.get('han') or 0 for row in rows) == (book.get('written_han') or 0),
            'problems': problems}


def render(repo):
    """Build the whole page as one HTML string."""
    book = repo.load()
    branch = book['branch']
    rows = repo.headers(branch)
    contract = book.get('contract')
    state = book.get('state') or {}
    written = book.get('written_han') or 0
    report = _audit_report(book, rows)
    open_hooks = {k: v for k, v in (state.get('hooks') or {}).items() if v.get('status') == 'open'}
    title = contract['title'] if contract else '未定名书稿'
    generated = time.strftime('%Y-%m-%d %H:%M')

    nav = ''.join('<a href="#%s">%s</a>' % (key, label) for key, label in SECTIONS)
    jump = ('<select id="jump-read" class="toc-select" style="display:none" onchange="jump(this)">'
            '<option>跳转章节…</option>'
            + ''.join('<option data-n="%d">第%d章</option>' % (row['n'], row['n']) for row in rows) + '</select>')
    pieces = ['<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">',
              '<meta name="viewport" content="width=device-width,initial-scale=1">',
              '<title>' + _esc(title) + ' · 全书视图</title><style>' + CSS + '</style></head><body>',
              '<header class="bar"><button class="menu" onclick="toggleSide()">☰</button>',
              '<div class="brand"><b>' + _esc(title) + '</b><span>分支 ' + _esc(branch) + ' · ' + str(len(rows))
              + ' 章 · ' + format(written, ',') + ' 汉字 · 生成于 ' + _esc(generated) + '</span></div>',
              '<div class="grow"></div><div class="tabs">',
              '<button data-m="settings" onclick="mode(\'settings\')">看设定</button>',
              '<button data-m="read" onclick="mode(\'read\')">读正文</button></div></header>',
              '<div class="wrap"><aside><nav id="nav-settings">' + nav + '</nav>' + jump + '</aside>',
              '<main><div id="view-settings">',
              _overview(book, contract, rows, state, open_hooks, report, written),
              _contract(contract) if contract else '<h2 id="contract">创作约定</h2>' + _empty('生效约定'),
              _world(book), _designs(book), _plans(book, contract), _profiles(book), _ledger(state),
              _reviews(rows, repo), _audit(book, report),
              '</div>',                                                # closes #view-settings
              _reader(rows, repo, contract, book),
              '</main></div>',
              '<footer><div class="rd-wrap">本页为派生只读视图，真源是 novel.sqlite3；重新生成：'
              'novel.py html --project &lt;PROJECT&gt; · 生成于 ' + _esc(generated)
              + ' · Ctrl+P 可打印或导出 PDF</div></footer>',
              '<script>' + JS + '</script></body></html>']
    return ''.join(pieces)


def write(repo, output=None):
    """Write the view (default <project>/book.html) and report where it went."""
    view = render(repo)
    target = Path(output).expanduser().resolve() if output else repo.project / 'book.html'
    atomic_write(target, view)
    rows = repo.headers(repo.load()['branch'])
    return {'path': str(target), 'chars': len(view), 'chapters': len(rows),
            'inside_project': target.is_relative_to(repo.project)}
