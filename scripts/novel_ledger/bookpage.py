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
from decimal import Decimal
from pathlib import Path
from .contracts import CONTRACT_FIELDS, LENSES, VOLUME_TURNS, han_count
from .delivery import atomic_write, publication
from .planning import volume_for
from .world import LABELS as WORLD_LABELS, SECTIONS as WORLD_SECTIONS
from .briefs import gate_title

FIELD_LABELS = {'title': '书名', 'reader_promise': '读者承诺', 'ending': '终局', 'genre': '题材',
                'story_engine': '推进引擎', 'opposition': '主要对抗', 'world_premise': '世界前提',
                'voice': '文风', 'allow_special_mechanism': '允许特殊机制', 'red_lines': '禁区',
                'style_traits': '文风要点', 'relationships': '核心关系', 'world_rules': '世界规则',
                'protagonist_setup': '主角设定', 'entities': '初始人物', 'initial_resources': '初始资源',
                'volumes': '分卷', 'word_range': '总字数区间', 'chapter_min': '章幅下限', 'chapter_max': '章幅上限',
                'chapter_aim': '章幅目标', 'planning_window': '规划窗口', 'review_interval': '复审间隔',
                'review_chunk': '复审块大小', 'initial_facts': '初始事实', 'places': '初始地点',
                'placements': '初始站位', 'arcs': '人物弧', 'editorial_features': '编辑能力',
                'scope_append_limit': '单轮补写章数上限', 'volume_outline': '逐章卷纲要求', 'anchors': '稳定设定', 'links': '空间连接'}
SUB_LABELS = {'id': '标识', 'name': '名称', 'kind': '类型', 'aliases': '别名', 'identity': '身份',
              'desire': '欲望', 'limit': '底线', 'purpose': '卷职责', 'end': '卷末章', 'holder': '持有者',
              'asset': '资产', 'unit': '单位', 'quantity': '数量', 'entity': '实体', 'key': '键', 'value': '值'}
SUB_LABELS.update(tier='人物层次', biography='小传与矛盾', speech='表达方式', public_role='公开身份', contradiction='内在矛盾',
                  values='价值优先顺序', register='语域', tactics='交涉策略', rhythm='句式节奏', stress_shift='压力下的变化',
                  relationship_modes='关系中的表达', mode='表达方式', change_reason='重核原因', fear='顾虑', voice='声线',
                  knowledge_boundary='知情边界', intent='场景意图', conflict='冲突', turn='转折', label='场所', present='在场者',
                  speakers='发言者', dialogue_intents='对白意图', seeks='索求', withholds='隐瞒', pressure='压力', tactic='策略',
                  knowledge_topics='知情话题', focus='展开重点', development='演出方式', expected_change='产生的变化', scene='场景')
SUB_LABELS.update(environment='环境', resources='资源', access='通行条件', story_pressure='情节压力',
                  period='时期', event='历史事件', consequence='后果', present_effect='当下影响', principle='规则原理',
                  scope='适用范围', limits='限制', consequences='违反后果', goal='诉求', power='力量来源',
                  dependencies='依赖', conflicts='冲突', resource='核心资源', production='生产', distribution='分配',
                  scarcity='稀缺', institution='制度', norm='习惯', enforcement='执行方式', practice='日常行为',
                  constraint='约束', story_use='故事作用', role='身份与作用', truth='隐秘内容', disclosure='披露安排',
                  causal_role='因果作用', cost='代价', failure_condition='失效条件')
NODE_LABELS = {'id': '节点', 'line': '线索', 'cause': '起因', 'choice': '选择', 'cost': '代价',
               'outcome': '结果', 'disclosure': '披露安排', 'depends_on': '依赖'}
PLAN_LABELS = {'goal': '目标', 'obstacle': '阻碍', 'choice': '选择', 'cost': '代价', 'change': '变化',
               'ending': '章末', 'node_ids': '设计节点', 'participants': '参与人', 'world_refs': '世界引用',
               'obligations': '承接义务', 'schedule': '硬日程', 'new_entities': '新人物', 'scenes': '场景安排', 'expansion_units': '展开依据'}
HOOK_LABELS = {'open': '待兑现', 'paid': '已兑现', 'closed': '已关闭'}
STANCE_LABELS = {'knows': '确知', 'believes': '相信', 'suspects': '怀疑', 'disproved': '已推翻'}
CHECK_LABELS = {'coverage': '覆盖', 'continuity': '连续性', 'resources': '资源', 'knowledge': '知情',
                'time': '时间', 'world_rules': '世界规则', 'space': '空间', 'read_on': '追读',
                'character': '人物', 'change': '变化', 'emotion_cost': '情绪代价', 'language': '语言',
                'repetition': '重复', 'substance': '有效展开', 'causality': '因果', 'character_arcs': '人物弧线',
                'payoffs': '兑现', 'pacing': '节奏'}
CHECK_LABELS.update(character_consistency='人物依据', stable_facts='稳定事实', dialogue_identity='对白辨识度',
                    voice_match='文风连续性', voice_evolution='声线成长', revision_intent='修订目标', narrative='叙事实现',
                    disclosure='披露边界', bridges='跨段承接', threads='线路职责')
CHECK_LABELS.update(choice_alignment='选择一致性', rule_consistency='规则一致性', spatial_connections='空间连接',
                    historical_causes='历史因果', faction_interests='势力利益', economic_consequences='经济后果',
                    social_pressure='社会压力', character_boundaries='人物边界', story_capacity='长篇承载')
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
.chart{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin:12px 0}
.chart figcaption{font-weight:600;margin-bottom:5px}.chart .sub{margin-bottom:12px}
.chart-tools{display:flex;gap:8px;margin:10px 0}.chart-tools input{min-width:0;flex:1;padding:7px 10px;
border:1px solid var(--line);border-radius:7px;background:var(--paper);color:var(--ink);font:inherit}
.chart-tools button{border:1px solid var(--line);border-radius:7px;background:var(--paper);color:var(--ink);cursor:pointer}
.graph-scroll,.chart-scroll{overflow:auto;max-height:620px}.graph{display:block;width:100%;min-width:660px}
.graph rect{fill:var(--accent-soft);stroke:var(--accent);stroke-width:1}.graph text{fill:var(--ink);font-family:var(--sans);font-size:12px}
.graph .group-label{fill:var(--muted);font-size:10px}.graph path{stroke:var(--muted);fill:none;stroke-width:1.4}
.graph marker path{fill:var(--muted);stroke:none}.graph-node:focus rect,.graph-node:hover rect{stroke-width:3}
.graph .faded{opacity:.12}.graph-node,.graph-edge{transition:opacity .15s}
.bar-row{display:grid;grid-template-columns:minmax(100px,1fr) minmax(120px,3fr) minmax(70px,1fr);gap:12px;
align-items:center;margin:10px 0;font-size:13px}.bar-track{height:12px;border-radius:20px;background:var(--bg);overflow:hidden}
.bar-fill{height:100%;background:var(--accent);border-radius:20px}.bar-value{text-align:right;color:var(--muted)}
.timeline{list-style:none;margin:12px 0;padding:0 0 0 20px;border-left:2px solid var(--line)}
.timeline li{position:relative;padding:0 0 18px 10px}.timeline li:before{content:"";position:absolute;left:-27px;top:7px;
width:12px;height:12px;border-radius:50%;background:var(--accent);border:3px solid var(--card)}
.timeline p{margin:4px 0}.timeline .note{display:block}.node-detail:target{outline:2px solid var(--accent);outline-offset:3px}
.chapter-bars{display:flex;gap:5px;align-items:flex-end;min-height:160px;padding-top:24px;overflow-x:auto}
.chapter-bar{min-width:38px;flex:1;text-align:center;font-size:11px;color:var(--muted);text-decoration:none}
.chapter-bar i{display:block;background:var(--accent);border-radius:5px 5px 0 0;margin:4px auto;max-width:50px}
.chapter-bar:hover i{background:var(--ok)}
@media (max-width:880px){.wrap{grid-template-columns:minmax(0,1fr);padding:14px}aside{position:static;max-height:none}
.rd-tools{top:auto;position:static}}
@media (max-width:520px){.chart{padding:12px}.bar-row{grid-template-columns:90px minmax(80px,1fr) 66px;gap:6px}}
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
else if(h==='#read'){mode('read',true)}else{mode('settings',true);revealTarget()}})();'''


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


def _anchor(prefix, ident):
    return prefix + '-' + str(ident).encode('utf-8').hex()


def _graph(title, nodes, edges, caption='点击节点查看完整详情，搜索可突出节点及其直接关联。'):
    """Inline SVG, with links derived only from explicit references; no inferred relationships."""
    if not nodes:
        return ''
    columns = min(3, len(nodes))
    width, height = columns * 250 + 20, ((len(nodes) + columns - 1) // columns) * 92 + 30
    positions = {node['id']: (135 + (i % columns) * 250, 48 + (i // columns) * 92)
                 for i, node in enumerate(nodes)}
    arrow = _anchor('arrow', title)
    parts = ['<figure class="chart"><figcaption>' + _esc(title) + '</figcaption><div class="sub">' + _esc(caption)
             + '</div><div class="chart-tools"><input aria-label="搜索' + _esc(title)
             + '节点" placeholder="搜索节点…" oninput="filterGraph(this)"><button onclick="resetGraph(this)">显示全部</button></div>'
             '<div class="graph-scroll"><svg class="graph" role="img" aria-label="' + _esc(title)
             + '" viewBox="0 0 %d %d"><title>' % (width, height) + _esc(title) + '</title><defs><marker id="'
             + arrow + '" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
             '<path d="M0 0 L10 5 L0 10 Z"/></marker></defs>']
    for a, b, label, directed in edges:
        if a not in positions or b not in positions:
            continue
        x1, y1 = positions[a]
        x2, y2 = positions[b]
        dx, dy = x2 - x1, y2 - y1
        if a == b:
            path = 'M%d %d C%d %d %d %d %d %d' % (x1-40, y1-28, x1-90, y1-60, x1+90, y1-60, x1+40, y1-28)
        else:
            ratio = min(104 / abs(dx) if dx else float('inf'), 28 / abs(dy) if dy else float('inf'))
            x1, y1, x2, y2 = x1 + dx * ratio, y1 + dy * ratio, x2 - dx * ratio, y2 - dy * ratio
            path = 'M%.1f %.1f L%.1f %.1f' % (x1, y1, x2, y2)
        parts.append('<path class="graph-edge" data-a="' + _anchor('key', a) + '" data-b="' + _anchor('key', b)
                     + '" d="' + path + '"' + (' marker-end="url(#' + arrow + ')"' if directed else '')
                     + '><title>' + _esc(label) + '</title></path>')
    for node in nodes:
        x, y = positions[node['id']]
        parts.append('<a class="graph-node" data-key="' + _anchor('key', node['id']) + '" href="#'
                     + node['target'] + '" tabindex="0" onclick="focusGraph(this)" onfocus="focusGraph(this)">'
                     '<title>' + _esc(node.get('detail', node['label'])) + '</title>'
                     '<rect x="%d" y="%d" width="208" height="56" rx="9"/>' % (x-104, y-28)
                     + '<text x="%d" y="%d" text-anchor="middle">' % (x, y-2) + _esc(_short(node['label'], 15))
                     + '</text><text class="group-label" x="%d" y="%d" text-anchor="middle">' % (x, y+17)
                     + _esc(_short(node.get('group', ''), 24)) + '</text></a>')
    parts.append('</svg></div><details><summary>查看关联明细 · ' + str(len(edges)) + ' 条</summary><ul class="tight">')
    labels = {node['id']: node['label'] for node in nodes}
    parts.extend('<li>' + _esc(labels.get(a, a)) + (' → ' if directed else ' ↔ ') + _esc(labels.get(b, b))
                 + ' · ' + _esc(label) + '</li>' for a, b, label, directed in edges)
    parts.append('</ul></details></figure>')
    return ''.join(parts)


def _bars(title, items, caption=''):
    """Each item supplies its own denominator and readable exact value."""
    if not items:
        return ''
    parts = ['<figure class="chart"><figcaption>' + _esc(title) + '</figcaption><div class="sub">' + _esc(caption) + '</div>']
    for label, value, maximum, display in items:
        percent = min(100, max(0, float(Decimal(str(value)) / Decimal(str(maximum)) * 100))) if maximum else 0
        parts.append('<div class="bar-row"><span>' + _esc(label) + '</span><div class="bar-track" role="img" aria-label="'
                     + _esc(label + '：' + display) + '"><div class="bar-fill" style="width:%.2f%%"></div></div>' % percent
                     + '<span class="bar-value">' + _esc(display) + '</span></div>')
    return ''.join(parts) + '</figure>'


def _timeline(title, items, caption=''):
    if not items:
        return ''
    return '<figure class="chart"><figcaption>' + _esc(title) + '</figcaption><div class="sub">' + _esc(caption) + '</div><ol class="timeline">' + ''.join(
        '<li><span class="pill">' + _esc(label) + '</span><b>' + _esc(head) + '</b><p>' + _esc(body)
        + '</p><span class="note">' + _esc(note) + '</span></li>' for label, head, body, note in items) + '</ol></figure>'


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
        pieces.append(_bars('写作进度', [('目标下限', written, band[0], format(written, ',') + ' / ' + format(band[0], ','))],
                            '字数达到下限后，仍需完成终局与独立核验。'))
        pieces.append(_bars('分卷进度', [(v['id'], sum(v['first'] <= row['n'] <= v['end'] for row in rows), v['end']-v['first']+1,
                                         str(sum(v['first'] <= row['n'] <= v['end'] for row in rows)) + ' / ' + str(v['end']-v['first']+1) + ' 章')
                                        for v in contract['volumes']]))
        if contract.get('volume_outline'):
            pieces.append(_bars('卷纲设计进度', [(v['id'], len(book.get('designs', {}).get('volume:' + v['id'], {}).get('chapters', [])),
                                                v['end']-v['first']+1,
                                                str(len(book.get('designs', {}).get('volume:' + v['id'], {}).get('chapters', []))) + ' / ' + str(v['end']-v['first']+1) + ' 章')
                                               for v in contract['volumes']], '只统计已通过独立核验的逐章卷纲。'))
        if rows:
            maximum = max(row['han'] for row in rows) or 1
            pieces.append('<figure class="chart"><figcaption>章节篇幅</figcaption><div class="sub">柱高表示实际汉字数，点击阅读对应章节。</div><div class="chapter-bars">'
                          + ''.join('<a class="chapter-bar" href="#read-' + str(row['n']) + '" onclick="openChapter(' + str(row['n'])
                                    + ');return false" title="第' + str(row['n']) + '章 · ' + str(row['han']) + ' 汉字">'
                                    + str(row['han']) + '<i style="height:%.1fpx"></i>' % (120 * row['han'] / maximum)
                                    + str(row['n']) + '</a>' for row in rows) + '</div></figure>')
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
        pieces.append('<p class="note">故事累计经过 ' + str(state['clock']) + ' 天</p>')
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
            pieces.append('<div class="card"><b>' + _esc(gate_title(row['gate'])) + ' · ' + _esc(option.get('title', '')) + '</b>'
                          + '<p>' + _esc(option.get('premise', '')) + '</p><p class="note">推进：'
                          + _esc(option.get('driver', '')) + '　代价：' + _esc(option.get('tradeoff', '')) + '</p>'
                          + '<table class="t">' + ''.join('<tr><th>' + _esc(FIELD_LABELS.get(k, SUB_LABELS.get(k, k))) + '</th><td>' + _display(v) + '</td></tr>'
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
    nodes, edges, seen = [], [], set()
    for section in WORLD_SECTIONS:
        for record in model.get(section, []):
            ident = section + ':' + record['id']
            label = record.get('name') or record.get('period') or record.get('resource') or record.get('institution') or record.get('practice') or record.get('principle') or record.get('truth') or record['id']
            nodes.append(dict(id=ident, label=label, group=WORLD_LABELS[section], target=_anchor('world', ident), detail=label + ' · ' + WORLD_LABELS[section]))
            for ref in record.get('links', []):
                pair = tuple(sorted((ident, ref)))
                if pair not in seen:
                    edges.append((ident, ref, '设定关联', False))
                    seen.add(pair)
    pieces.append(_graph('世界关联图', nodes, edges, '连线来自世界设定的显式引用，表示关联，不推断敌友或因果。点击节点查看设定。'))
    pieces.append(_timeline('历史时间线', [(r['period'], r['event'], r['consequence'], '当下影响：' + r['present_effect'])
                                          for r in model.get('history', [])], '按世界模型中的记录顺序展示，时期保留原文。'))
    for section in WORLD_SECTIONS:
        records = model.get(section, [])
        pieces.append('<h3>' + _esc(WORLD_LABELS.get(section, section)) + ' <span class="pill dim">'
                      + str(len(records)) + ' 条</span></h3>')
        if not records:
            pieces.append('<p class="note">按已选方向，不设置特殊机制。</p>' if section == 'mechanisms' else _empty('记录'))
        for record in records:
            links = record.get('links') or []
            pieces.append('<div class="card node-detail" id="' + _anchor('world', section + ':' + record['id']) + '"><b>'
                          + _esc(record.get('name') or record.get('period') or record.get('resource') or record.get('institution') or WORLD_LABELS[section]) + '</b><table class="t">' + ''.join(
                '<tr><th>' + _esc(SUB_LABELS.get(k, k)) + '</th><td>' + _display(v) + '</td></tr>'
                for k, v in record.items() if k not in ('id', 'links')) + '</table>'
                + ('<p class="note">关联：' + ''.join('<a class="pill" href="#' + _anchor('world', ref) + '">' + _esc(ref) + '</a>' for ref in links) + '</p>' if links else '') + '</div>')
    review = book.get('world_review')
    if review:
        receipt = review.get('receipt', review)
        pieces.append('<details><summary>世界独立核验 · ' + _esc(VERDICT_LABELS.get(receipt.get('verdict'), receipt.get('verdict', ''))) + '</summary>')
        for check in receipt.get('checks', []):
            pieces.append('<p><span class="pill ' + ('ok' if check['result'] == 'pass' else 'bad') + '">' + _esc(VERDICT_LABELS.get(check['result'], check['result']))
                          + '</span>' + _esc(CHECK_LABELS.get(check['id'], check['id'])) + ' · ' + _esc(check['reason']) + '</p>')
        pieces.append(_raw(review) + '</details>')
    return ''.join(pieces)


def _designs(book):
    pieces = ['<h2 id="design">设计与因果节点</h2>']
    designs = book.get('designs') or {}
    if not designs:
        return ''.join(pieces) + _empty('设计')
    nodes = [dict(id=n['id'], label=n.get('outcome') or n.get('cause') or n['id'], group=n['id'] + ' · ' + n.get('line', ''),
                  target=_anchor('design', n['id']), detail=n['id'] + ' · ' + n.get('cause', '') + ' → ' + n.get('outcome', ''))
             for d in designs.values() for n in d.get('nodes', [])]
    edges = [(dep, n['id'], '因果前置', True) for d in designs.values() for n in d.get('nodes', []) for dep in n.get('depends_on', [])]
    pieces.append(_graph('因果节点图', nodes, edges, '箭头从因果前置指向后续节点。设计安排与正文实际实现分别展示。'))
    for scope, design in designs.items():
        pieces.append('<h3>' + _esc('全书' if scope == 'book' else scope) + '</h3><div class="card"><table class="t">'
                      '<tr><th>意图</th><td>' + _esc(design.get('intent', '')) + '</td></tr>'
                      '<tr><th>终局条件</th><td>' + _esc(design.get('ending_conditions', '')) + '</td></tr></table></div>')
        if design.get('brainstorm'):
            pieces.append('<details><summary>卷纲脑暴与选案</summary><table class="t">')
            for option in design['brainstorm']:
                pieces.append('<tr><th>' + _esc(option['id']) + (' · 已选' if option['id'] == design['selected'] else '')
                              + '</th><td>' + _esc(option['premise']) + '<p class="note">取舍：' + _esc(option['tradeoff'])
                              + '</p></td></tr>')
            pieces.append('</table><p>选案理由：' + _esc(design['selection_reason']) + '</p></details>')
        if design.get('chapters'):
            pieces.append('<h3>逐章卷纲 · ' + _esc(scope) + '</h3><ol class="timeline">')
            for entry in design['chapters']:
                pieces.append('<li><details id="' + _anchor('outline', entry['chapter']) + '"><summary>第' + str(entry['chapter'])
                              + '章 · ' + str(han_count(entry['synopsis'])) + ' 字 · ' + _esc(_short(entry['synopsis'], 32))
                              + '</summary><p style="white-space:pre-wrap">' + _esc(entry['synopsis']) + '</p><p class="note">世界依据：'
                              + ''.join('<a class="pill" href="#' + _anchor('world', ref) + '">' + _esc(ref) + '</a>' for ref in entry['world_refs'])
                              + '</p><p class="note">因果节点：' + _pills(entry['node_ids']) + '</p></details></li>')
            pieces.append('</ol>')
        for node in design.get('nodes', []):
            pieces.append('<details class="node-detail" id="' + _anchor('design', node['id']) + '"><summary><span class="pill">' + _esc(node.get('id', '')) + '</span>'
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
    pieces.append(_timeline('章节推进', [('第' + str(n) + '章', plans[str(n)].get('goal', ''),
                                        plans[str(n)].get('change', ''), '章末：' + plans[str(n)].get('ending', '')) for n in numbers]))
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
            for k, v in profile.items() if k not in ('entity', 'growth_basis')) + '</table></div>')
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
            pieces.append('<div class="stat node-detail" id="' + _anchor('entity', item['id']) + '"><b>' + _esc(item.get('name', '')) + '</b><span>' + _esc(item.get('kind', ''))
                          + (' · ' + _esc('、'.join(aliases)) if aliases else '') + '</span></div>')
        pieces.append('</div>')
    name_of = lambda ident: entities.get(ident, {}).get('name', ident)
    relations = state.get('relations') or {}
    if relations:
        edges = []
        for key, value in relations.items():
            pair, label = key.split(':', 1)
            a, b = pair.split('>', 1)
            edges.append((a, b, label + '：' + str(value), True))
        involved = {ident for a, b, _label, _directed in edges for ident in (a, b)}
        pieces.append(_graph('人物关系图', [dict(id=ident, label=name_of(ident), group=entities.get(ident, {}).get('kind', ''),
                                               target=_anchor('entity', ident)) for ident in entities if ident in involved], edges,
                             '连线只展示正文已成立的关系；悬停连线或展开明细查看关系内容。'))
    for key, label in (('facts', '状态事实'), ('relations', '关系'), ('historical_assertions', '历史断言'),
                       ('developments', '人物成长'), ('story_nodes', '节点实际推进'), ('thread_progress', '线路实际推进'),
                       ('reader_knowledge', '读者已见信息'), ('character_current', '人物当前动机与关系')):
        records = state.get(key) or {}
        if records:
            pieces.append('<h3>' + label + ' <span class="pill dim">' + str(len(records)) + '</span></h3><div class="card"><table class="t">'
                          + ''.join('<tr><th>' + _esc(k) + '</th><td>' + _display(v) + '</td></tr>'
                                    for k, v in sorted(records.items())) + '</table></div>')
    resources = state.get('resources') or {}
    if resources:
        groups = {}
        for key, value in sorted(resources.items()):
            holder, asset, unit = json.loads(key)
            groups.setdefault((asset, unit), []).append((holder, Decimal(value), value))
        for (asset, unit), items in groups.items():
            maximum = max(amount for _holder, amount, _value in items)
            pieces.append(_bars('资源分布 · ' + asset, [(name_of(holder), amount, maximum, value + ' ' + unit)
                                                       for holder, amount, value in items], '同一资产、同一单位内比较，数值保留原始精度。'))
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
        pieces.append(_timeline('承诺期限', [('最迟第' + str(h['due']) + '章', ident, h.get('text', ''), HOOK_LABELS.get(h.get('status'), ''))
                                           for ident, h in sorted(hooks.items(), key=lambda pair: pair[1].get('due', 0)) if 'due' in h]))
        pieces.append('<h3>承诺 <span class="pill dim">' + str(len(hooks)) + '</span></h3>')
        for ident, hook in sorted(hooks.items()):
            status = hook.get('status')
            cls = ' ok' if status == 'paid' else (' bad' if status == 'open' else ' dim')
            pieces.append('<div class="card"><b>' + _esc(ident) + '</b><span class="pill' + cls + '">'
                          + _esc(HOOK_LABELS.get(status, status or '')) + '</span><p>' + _esc(hook.get('text', '')) + '</p>'
                          + '<p class="note">最迟第 ' + _esc(hook.get('due', '—')) + ' 章 · 埋设于第 '
                          + _esc(hook.get('seed', {}).get('chapter', hook.get('seed_chapter', '—'))) + ' 章 · 延期 ' + _esc(hook.get('extensions', 0)) + '/2</p></div>')
    places = state.get('places') or {}
    if state.get('pace_history'):
        pieces.append('<h3>近期节奏与情绪承接</h3>' + _display(state['pace_history']))
    if places:
        nodes = [dict(id='p:' + ident, label=place.get('name', ident), group='地点', target=_anchor('place', ident)) for ident, place in places.items()]
        edges = [('p:' + ident, 'p:' + place['parent'], '属于', True) for ident, place in places.items() if place.get('parent')]
        located = set(state.get('placements', {})) | set(state.get('custody', {})) | set(state.get('custody', {}).values())
        nodes.extend(dict(id='e:' + ident, label=name_of(ident), group='人物 / 物品', target=_anchor('entity', ident)) for ident in entities if ident in located)
        edges.extend(('e:' + ident, 'p:' + place, '位于', True) for ident, place in state.get('placements', {}).items())
        edges.extend(('e:' + ident, 'e:' + holder, '由其持有', True) for ident, holder in state.get('custody', {}).items())
        kinds = {'path': '路径', 'sight': '视线', 'sound': '声音'}
        edges.extend(('p:' + link['a'], 'p:' + link['b'], kinds.get(link['kind'], link['kind']) + (' · 已关闭' if not link.get('open', True) else ''),
                      link.get('directed', False)) for link in state.get('links', {}).values())
        pieces.append(_graph('地点与站位图', nodes, edges, '包含关系、当前位置和已登记的路径 / 视听连接；不推断未登记的距离或人物知情。'))
        pieces.append('<h3>地点与站位</h3><div class="card"><table class="t">')
        for item in places.values():
            parent = places.get(item['parent'], {}).get('name') if item.get('parent') else None
            pieces.append('<tr class="node-detail" id="' + _anchor('place', item['id']) + '"><th>' + _esc(item.get('name', '')) + '</th><td>'
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
    book, rows = publication(repo)
    branch = book['branch']
    contract = book.get('contract')
    state = book.get('state') or {}
    written = book.get('written_han') or 0
    report = _audit_report(book, rows)
    open_hooks = {k: v for k, v in (state.get('hooks') or {}).items() if v.get('status') == 'open'}
    title = contract['title'] if contract else '未定名书稿'
    generated = time.strftime('%Y-%m-%d %H:%M', time.localtime(book['completed_at'])) if book.get('completed_at') else time.strftime('%Y-%m-%d %H:%M')

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
    _, rows = publication(repo)
    return {'path': str(target), 'chars': len(view), 'chapters': len(rows),
            'inside_project': target.is_relative_to(repo.project)}
