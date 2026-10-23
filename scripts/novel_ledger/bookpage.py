"""Read-only book views: a fixed preview shell and explicit offline exports.

Live fragments and standalone exports share escaped presentation helpers.
Only the local preview adapter opens databases; this module accepts a reader.
"""
from __future__ import annotations

import html
import json
import os
import shlex
import subprocess
import sys
import time
from decimal import Decimal
from pathlib import Path
from string import Template
from .catalog import LENSES, VOLUME_TURNS
from .contracts import CONTRACT_FIELDS, han_count, require
from .ports import PublicationReader
from .publication import publication
from .workspace import LocalWorkspace
from .planning import volume_for
from .world import LABELS as WORLD_LABELS, SECTIONS as WORLD_SECTIONS
from . import catalog, creation, understanding
from .briefs import gate_title

FIELD_LABELS = {'title': '书名', 'reader_promise': '读者承诺', 'ending': '终局', 'genre': '题材',
                'story_engine': '推进引擎', 'opposition': '主要对抗', 'world_premise': '世界前提',
                'voice': '文风', 'allow_special_mechanism': '允许特殊机制', 'red_lines': '禁区',
                'tone': '基调', 'theme': '母题', 'pov': '叙述视角',
                'style_traits': '文风要点', 'relationships': '核心关系', 'world_rules': '世界规则',
                'protagonist_setup': '主角设定', 'entities': '初始人物', 'initial_resources': '初始资源',
                'volumes': '分卷', 'word_range': '总字数区间', 'chapter_min': '章幅下限', 'chapter_max': '章幅上限',
                'chapter_aim': '章幅目标', 'volume_count': '卷数', 'chapters': '总章数',
                'chapter_window': '可写完章数区间', 'tier': '体量档位',
                'revision_limit': '修订窗口', 'initial_facts': '初始事实', 'places': '初始地点',
                'placements': '初始站位', 'arcs': '人物弧', 'editorial_features': '编辑能力',
                'scope_append_limit': '单轮补写章数上限', 'volume_outline': '卷纲要求',
                'chapter_outline': '章纲要求', 'style_window': '文风容差',
                # opening/5: the brainstorm gate's four questions, the ladder's scale, the tier
                # ladder, the hard currency, and the promise anchor.
                'world_architecture': '世界架构', 'architecture': '世界架构', 'core_premise': '核心设想', 'world_scale': '格局尺度', 'world_ladder': '升格阶梯',
                'world_tiers': '位阶阶梯', 'world_resource': '硬通货', 'promise_anchor': '主题锚点',
                'anchors': '稳定设定', 'links': '空间连接'}
# Option values that are engine bookkeeping rather than an author-facing decision: the structural gate's
# tier id and its arithmetic window are already stated in the option's own sentence.
OPENING_VALUE_HIDDEN = ('tier', 'chapter_window')
SUB_LABELS = {'space': '世界全貌', 'history': '历史断层', 'civilizations': '文明与秩序', 'mystery': '终极谜题', 'id': '标识', 'name': '名称', 'kind': '类型', 'aliases': '别名', 'identity': '身份',
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
# v2 design surfaces: the volume outline's own fields, the chapter outline's drift fields, and the
# sentence-shaped fields that carry the state chain.
SUB_LABELS.update(arc='卷内弧线', turns='卷内转折', climax='卷末高潮', exit_state='卷末必须达到的状态',
                  synopsis='本章推进', beat='情节变化', outcome='结果', after='之后', node='节点', thread='线路',
                  enter='入场状态', exit='出场状态', expected='期望值', from_='起点', to='终点', reason='理由',
                  continues='跨卷延续', window='窗口区间', ending_condition='兑现条件', required='必需',
                  who='知情者', topic='话题', entity='实体', choice='选择', stance='立场',
                  desire='欲望', relationship_focus='关系焦点', kind='类型', key='键', planned='计划',
                  actual='实际', status='比对结果', evidence='正文依据', quote='原文片段',
                  disclosures='读者认知推进', world_refs='世界引用', new_entities='新登场',
                  hook_refs='承接承诺', reader_refs='读者关联', history_refs='历史关联', events='事件')
# v2.1: the promise ledger and the style specification, on both the volume and the chapter row.
SUB_LABELS.update(hooks='伏笔账', hook='伏笔', text='对读者的承诺', plant='埋设窗口', payoff='兑现窗口',
                  action='动作', note='说明', style='文风', trend='本卷文风走向', pov='叙述人称与视角',
                  rhythm='句法与节奏', dialogue_ratio='对白占比目标', notes='本章例外',
                  anchor='首章实测指标', voice='文风', tone='基调', style_traits='文风要点',
                  sentence='句长', paragraph='段长', dialogue='对白', repetition='重复度', person='人称')
# opening/5: the brainstorm gate's four answers, the ladder and tier tables, the hard currency, the
# promise anchor, the world's optional deep fields, and the two grand domains' own fields.
SUB_LABELS.update(novelty='核心设想', first_cause='第一推动力', dark_side='世界暗面来源',
                  opening='开局可见边界', terminal='终局等级', unchanged='跨卷不变的上层结构',
                  stage='升格层级', scope='适用范围/尺度', growth='变大的是什么', new_rule='这一级新增的规则',
                  condition='晋升条件', gain='得到什么', allocator='分配者',
                  deliverable='必须兑现的东西', deadline_chapter='最迟兑现章',
                  epoch='纪元/分期', carryover='上一纪元的延续', counter_space='对立空间',
                  survives_scale_up='跨卷仍在场的原因', reveal_window='披露排期', survival='真相揭开后的生存问题',
                  layer='层名', inhabitant='谁在', law='法则', entry='怎么进')
SUB_LABELS['from'] = '起点'
DRIFT_LABELS = {'kind': '类型', 'key': '坐标', 'planned': '章纲计划', 'actual': '正文实际',
                'status': '比对结果', 'reason': '说明', 'evidence': '正文依据'}
DRIFT_STATUS_LABELS = {'kept': '已兑现', 'deviated': '有偏差', 'skipped': '未发生',
                       'clean': '无偏差', 'open': '未处理'}
HOOK_LABELS = {'open': '待兑现', 'paid': '已兑现', 'closed': '已关闭'}
HOOK_ACTION_LABELS = {'plant': '埋设', 'payoff': '兑现'}
STANCE_LABELS = {'knows': '确知', 'believes': '相信', 'suspects': '怀疑', 'disproved': '已推翻'}
STATUS_LABELS = {'preparing': '开书准备', 'running': '进行中', 'paused': '已暂停', 'completed': '已完本'}
SECTIONS = (('overview', '概览'), ('contract', '创作约定'), ('world', '世界与选择'),
            ('outline', '卷纲与章纲'), ('plans', '章纲结算行'), ('understanding', '作品理解'),
            ('ledger', '事实账本'), ('drift', '漂移挂账'), ('audit', '账本核验'))




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
    pieces = ['<h2 id="overview">概览</h2><div class="sub">账本派生只读视图 · 真源是作品账本 · 可随时重新生成</div><div class="cards">',
              '<div class="stat"><b>' + str(len(rows)) + '</b><span>已提交章节</span></div>',
              '<div class="stat"><b>' + format(written, ',') + '</b><span>累计汉字</span></div>',
              '<div class="stat"><b>' + str(len(open_hooks)) + '</b><span>待兑现承诺</span></div>',
              '<div class="stat"><b>' + _esc(STATUS_LABELS.get(book.get('status'), book.get('status') or '')) + '</b><span>运行状态</span></div>',
              '<div class="stat"><b>' + _esc(book.get('target') if book.get('target') is not None else '—') + '</b><span>授权目标章</span></div>',
              '<div class="stat"><b>' + ('是' if report['ok'] else '否') + '</b><span>账本核验</span></div></div>']
    if contract:
        band = contract['word_range']
        pieces.append(_bars('写作进度', [('目标下限', written, band[0], format(written, ',') + ' / ' + format(band[0], ','))],
                            '字数达到下限后，仍需完成卷末闭合与全书终局。'))
        pieces.append(_bars('分卷进度', [(v['id'], sum(v['first'] <= row['n'] <= v['end'] for row in rows), v['end']-v['first']+1,
                                         str(sum(v['first'] <= row['n'] <= v['end'] for row in rows)) + ' / ' + str(v['end']-v['first']+1) + ' 章')
                                        for v in contract['volumes']]))
        if contract.get('volume_outline') or contract.get('chapter_outline'):
            # The design progress bar counts chapter outline rows, not reviews: v2 has no review
            # gate, so what can be missing is the row itself.
            outlines = book.get('chapter_outlines') or {}
            pieces.append(_bars('章纲进度', [(v['id'], len([r for r in outlines.get(v['id'], [])
                                                           if v['first'] <= r.get('chapter', 0) <= v['end']]),
                                            v['end']-v['first']+1,
                                            str(len([r for r in outlines.get(v['id'], [])
                                                     if v['first'] <= r.get('chapter', 0) <= v['end']]))
                                            + ' / ' + str(v['end']-v['first']+1) + ' 章')
                                           for v in contract['volumes']],
                              '统计已交付的章纲行；卷纲本身见「卷纲与章纲」区。'))
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
    block = book.get('author_block')
    if block:
        pieces.append('<div class="card" style="border-color:var(--bad)"><b>待作者裁决</b><p class="note">'
                      + _esc(block.get('question', '')) + '</p><ul class="tight">'
                      + ''.join('<li>' + _esc(o.get('label', '')) + '：' + _esc(o.get('impact', '')) + '</li>'
                                for o in block.get('options') or []) + '</ul></div>')
    if report['problems']:
        pieces.append('<div class="card" style="border-color:var(--bad)"><b>核验发现的问题</b><ul class="tight">'
                      + ''.join('<li>' + _esc(p) + '</li>' for p in report['problems']) + '</ul></div>')
    return ''.join(pieces)


def _contract(contract):
    pieces = ['<h2 id="contract">创作约定</h2><div class="sub">作者认可的全书边界；系统不为过关而改约</div><div class="card"><table class="t">']
    for row in CONTRACT_FIELDS:
        # A contract written before a field existed simply does not carry it; an empty row would read
        # as a decision the author left blank.
        if row['key'] not in contract:
            continue
        pieces.append('<tr><th>' + _esc(FIELD_LABELS.get(row['key'], row['key'])) + '</th><td>'
                      + _display(contract.get(row['key'])) + '</td></tr>')
    pieces.append('</table></div>')
    return ''.join(pieces) + _raw(contract)


def _world(book):
    pieces = ['<h2 id="world">世界与选择</h2>']
    opening = book.get('creation')
    if opening and opening.get('selections'):
        pieces.append('<h3>逐门选择</h3>')
        version = creation.opening_version(opening)
        for row in opening['selections']:
            option = row['option']
            notes = [label + _esc(option[key]) for label, key in (('推进：', 'driver'), ('代价：', 'tradeoff'))
                     if option.get(key)]
            pieces.append('<div class="card"><b>' + _esc(gate_title(row['gate'], version)) + ' · ' + _esc(option.get('title', '')) + '</b>'
                          + (('<p>' + _esc(option['premise']) + '</p>') if option.get('premise') else '')
                          + (('<p class="note">' + '　'.join(notes) + '</p>') if notes else '')
                          + '<table class="t">' + ''.join('<tr><th>' + _esc(FIELD_LABELS.get(k, SUB_LABELS.get(k, k))) + '</th><td>' + _display(v) + '</td></tr>'
                                                          for k, v in option.get('value', {}).items() if k not in OPENING_VALUE_HIDDEN)
                          + '</table>'
                          + (('<p class="note">作者原话：' + _esc(row.get('source', '')) + '</p>') if row.get('source') else '')
                          + '</div>')
    model = book.get('world')
    if not model:
        pieces.append('<p class="note">世界模型尚未生成。')
        return ''.join(pieces)
    pieces.append('<h3>世界模型</h3><div class="card"><table class="t">'
                  '<tr><th>前提</th><td>' + _esc(model['premise']) + '</td></tr>'
                  '<tr><th>长篇承载</th><td>' + _esc(model['story_capacity']) + '</td></tr></table></div>')
    # The record total, so a reader can see at a glance whether the world is the size the tier asked
    # for: the per-domain counts below answer "what is in this one", not "how much world is there".
    filled = [section for section in WORLD_SECTIONS if model.get(section)]
    total = sum(len(model.get(section) or []) for section in WORLD_SECTIONS)
    pieces.append('<p class="note">世界记录共 <b>' + str(total) + ' 条</b>，覆盖 ' + str(len(filled))
                  + ' 个领域；其余领域按本档位留空，下面按领域列出。</p>')
    nodes, edges, seen = [], [], set()
    for section in WORLD_SECTIONS:
        for record in model.get(section, []):
            ident = section + ':' + record['id']
            label = record.get('name') or record.get('layer') or record.get('period') or record.get('resource') or record.get('institution') or record.get('practice') or record.get('principle') or record.get('truth') or record['id']
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
                          + _esc(record.get('name') or record.get('layer') or record.get('period') or record.get('resource') or record.get('institution') or WORLD_LABELS.get(section, section)) + '</b><table class="t">' + ''.join(
                '<tr><th>' + _esc(SUB_LABELS.get(k, k)) + '</th><td>' + _display(v) + '</td></tr>'
                for k, v in record.items() if k not in ('id', 'links')) + '</table>'
                + ('<p class="note">关联：' + ''.join('<a class="pill" href="#' + _anchor('world', ref) + '">' + _esc(ref) + '</a>' for ref in links) + '</p>' if links else '') + '</div>')
    return ''.join(pieces)


def _delta_block(title, rows, empty_note):
    """One drift group of a chapter row. An empty array is a declaration, so it is shown as one."""
    if not rows:
        return '<p class="note">' + _esc(title) + '：' + _esc(empty_note) + '</p>'
    return ('<p class="note">' + _esc(title) + '</p><ul class="tight">'
            + ''.join('<li>' + _display(row) + '</li>' for row in rows) + '</ul>')


def _chain(rows):
    """The enter/exit state chain, one pill per coordinate."""
    if not rows:
        return '<span class="note">（空）</span>'
    return ''.join('<span class="pill">' + _esc('%s:%s=%s' % (row.get('kind', ''), row.get('key', ''),
                                                      _short(row.get('expected'), 24)))
                   + '</span>' for row in rows)


def _hook_rows(rows, declared=None):
    """The promise ledger: what a volume declares, or what a chapter acts on.

    A volume row carries the declaration (windows, required, continues); a chapter row carries the
    action. Both are rendered against the same ledger so a reader can see whether a promise's window
    still contains a plant/payoff that has not been written yet.
    """
    if not rows:
        return '<span class="note">（无）</span>'
    by_id = {entry.get('id'): entry for entry in (declared or []) if isinstance(entry, dict)}
    pieces = ['<ul class="tight">']
    for entry in rows:
        if not isinstance(entry, dict):
            pieces.append('<li>' + _display(entry) + '</li>')
            continue
        ident = entry.get('id') or entry.get('hook') or ''
        bits = []
        if entry.get('text'):
            bits.append(_esc(entry['text']))
        elif ident in by_id and by_id[ident].get('text'):
            bits.append(_esc(by_id[ident]['text']))
        if entry.get('action'):
            bits.append('<span class="pill">' + _esc(HOOK_ACTION_LABELS.get(entry['action'], entry['action'])) + '</span>')
        if entry.get('plant'):
            bits.append('埋设窗口 ' + _esc(entry['plant']))
        if entry.get('payoff'):
            bits.append('兑现窗口 ' + _esc(entry['payoff']))
        if entry.get('required') is not None:
            bits.append('卷末必须兑现' if entry['required'] else '可选')
        if entry.get('continues'):
            bits.append('跨卷延续')
        if entry.get('note'):
            bits.append(_esc(entry['note']))
        pieces.append('<li><b>' + _esc(ident) + '</b>（' + '　'.join(bits) + '）</li>')
    pieces.append('</ul>')
    return ''.join(pieces)


def _style_block(style):
    """A rendered style specification: trend/window on a volume, execution points on a chapter."""
    if not style:
        return '<span class="note">（未声明）</span>'
    fields = [(key, value) for key, value in style.items() if value not in (None, '', {}, [])]
    if not fields:
        return '<span class="note">（未声明）</span>'
    return '<table class="t">' + ''.join(
        '<tr><th>' + _esc(SUB_LABELS.get(key, key)) + '</th><td>' + _display(value) + '</td></tr>'
        for key, value in fields) + '</table>'


def _chapter_card(row):
    number = row.get('chapter', '?')
    plot = row.get('plot') or {}
    pieces = ['<li><details id="' + _anchor('outline', number) + '"><summary>第' + str(number)
              + '章 · ' + str(han_count(row.get('synopsis', ''))) + ' 字 · '
              + _esc(_short(row.get('synopsis', ''), 32)) + '</summary>',
              '<p class="note">情节变化：' + _esc(plot.get('beat', '')) + '</p>',
              '<p style="white-space:pre-wrap">' + _esc(row.get('synopsis', '')) + '</p>',
              _delta_block('节点推进（plot.nodes）', plot.get('nodes'), '本章不推进已登记节点。'),
              _delta_block('线路状态（plot.threads）', plot.get('threads'), '本章线路状态不变。')]
    for field, title, note in (('resources', '资源增量', '本章无资源变化。'),
                               ('places', '位置增量', '本章无位置变化。'),
                               ('knowledge', '知情增量', '本章无知情变化。'),
                               ('characters', '人物增量', '本章无人物变化。')):
        pieces.append(_delta_block(title, row.get(field), note))
    pieces.append('<p class="note">伏笔执行（hooks）</p>' + _hook_rows(row.get('hooks')))
    pieces.append('<p class="note">本章文风执行点（style）</p>' + _style_block(row.get('style')))
    clock = row.get('clock') or {}
    pieces.append('<p class="note">时钟：本章推进 ' + _esc(clock.get('advance_days', '—')) + ' 天</p>')
    pieces.append('<table class="t"><tr><th>入场状态 enter</th><td>' + _chain(row.get('enter')) + '</td></tr>'
                  '<tr><th>出场状态 exit</th><td>' + _chain(row.get('exit')) + '</td></tr>'
                  '<tr><th>读者认知推进</th><td>' + _display(row.get('disclosures') or []) + '</td></tr>'
                  '<tr><th>世界引用</th><td>' + ''.join('<a class="pill" href="#' + _anchor('world', ref)
                                                        + '">' + _esc(ref) + '</a>' for ref in row.get('world_refs') or [])
                  + '</td></tr>'
                  '<tr><th>新登场</th><td>' + _display(row.get('new_entities') or []) + '</td></tr>'
                  '<tr><th>承接资料</th><td>' + _display({'hook_refs': row.get('hook_refs') or [],
                                                          'reader_refs': row.get('reader_refs') or [],
                                                          'history_refs': row.get('history_refs') or []}) + '</td></tr>'
                  '</table>')
    pieces.append(_raw(row) + '</details></li>')
    return ''.join(pieces)


def _outlines(book):
    """The design surface v2 actually has: volume outlines plus their chapter outlines.

    No review records and no brainstorm/selection: what a volume owes is its arc, its node and
    thread register, its resource/place/knowledge trends and the state its end must reach; what a
    chapter owes is its synopsis, its four delta groups, and the enter/exit chain the state
    simulation replays.
    """
    pieces = ['<h2 id="outline">卷纲与章纲</h2><div class="sub">设计期声明：卷纲每卷约千字，'
              '章纲逐章声明增量与 enter/exit 链；这两份声明就是执笔自比与引擎核算的依据</div>']
    volumes = book.get('volumes_outline') or {}
    outlines = book.get('chapter_outlines') or {}
    if not volumes and not outlines:
        return ''.join(pieces) + _empty('卷纲与章纲')
    for vid, row in volumes.items():
        pieces.append('<h3>卷纲 · ' + _esc(vid) + '</h3><div class="card"><table class="t">'
                      '<tr><th>卷职责</th><td>' + _esc(row.get('purpose', '')) + '</td></tr>'
                      '<tr><th>卷内弧线</th><td style="white-space:pre-wrap">' + _esc(row.get('arc', '')) + '</td></tr>'
                      '<tr><th>卷末高潮</th><td>' + _esc(row.get('climax', '')) + '</td></tr>'
                      '<tr><th>卷末必须达到的状态</th><td style="white-space:pre-wrap">' + _esc(row.get('exit_state', '')) + '</td></tr>'
                      '<tr><th>时钟</th><td>本卷推进 ' + _esc((row.get('clock') or {}).get('advance_days', '—')) + ' 天</td></tr>'
                      '</table></div>')
        if row.get('turns'):
            pieces.append(_timeline('卷内转折', [(str(turn.get('at', '')), turn.get('turn', ''), '', '')
                                                for turn in row['turns']]))
        pieces.append('<h4>本卷伏笔账 <span class="pill dim">' + str(len(row.get('hooks') or [])) + ' 条</span></h4>')
        pieces.append('<p class="note">卷纲声明 promises：plant/payoff 窗口、卷末是否必须兑现、跨卷是否延续；'
                      '章纲只做 plant/payoff 两个动作，中途再提用 hook_refs 承接。</p>')
        pieces.append(_hook_rows(row.get('hooks')))
        pieces.append('<h4>本卷文风走向</h4>' + _style_block(row.get('style')))
        for field, title in (('nodes', '本卷节点'), ('threads', '本卷线路')):
            rows = row.get(field) or []
            pieces.append('<h4>' + _esc(title) + ' <span class="pill dim">' + str(len(rows)) + ' 条</span></h4>')
            if rows:
                pieces.append('<ul class="tight">' + ''.join(
                    '<li>' + _display({k: v for k, v in item.items() if k != 'id'})
                    + '　<span class="pill">' + _esc(item.get('id', '')) + '</span></li>' for item in rows) + '</ul>')
            else:
                pieces.append('<p class="note">本卷不新建。</p>')
        for field, title in (('resources', '资源大势'), ('places', '人物位置走向'),
                             ('knowledge', '知情走向'), ('characters', '人物弧走向')):
            pieces.append(_delta_block(title, row.get(field), '本卷无此类变化。'))
    for vid, rows in outlines.items():
        ordered = sorted(rows, key=lambda item: item.get('chapter', 0))
        pieces.append('<h3>章纲 · ' + _esc(vid) + ' <span class="pill dim">' + str(len(ordered)) + ' 章</span></h3>')
        pieces.append(_timeline('章纲推进', [('第' + str(r.get('chapter', '?')) + '章',
                                             _short(r.get('synopsis', ''), 40),
                                             (r.get('plot') or {}).get('beat', ''),
                                             '推进天数：' + str((r.get('clock') or {}).get('advance_days', '—')))
                                            for r in ordered]))
        pieces.append('<ol class="timeline">' + ''.join(_chapter_card(r) for r in ordered) + '</ol>')
    return ''.join(pieces)


def _plans(book, contract):
    """The materialized settlement rows the engine reconciles a draft against."""
    pieces = ['<h2 id="plans">章纲结算行</h2><div class="sub">由章纲物化、写入时作为结算契约的行；'
              '执笔的 drift_check 就是逐条与它对账</div>']
    plans = book.get('plans') or {}
    if not plans:
        return ''.join(pieces) + _empty('章纲结算行')
    numbers = sorted(int(n) for n in plans)
    pieces.append('<p class="note">已物化 ' + str(len(numbers)) + ' 章：第 ' + str(numbers[0]) + ' ~ '
                  + str(numbers[-1]) + ' 章</p>')
    for number in numbers:
        plan = plans[str(number)]
        volume = volume_for(contract, number) if contract else None
        head = '<span class="pill">第' + str(number) + '章</span>'
        if volume:
            head += '<span class="pill dim">' + _esc(volume['id']) + '</span>'
        pieces.append('<details><summary>' + head + _esc(_short(plan.get('synopsis', ''), 32)) + '</summary><table class="t">'
                      + ''.join('<tr><th>' + _esc(SUB_LABELS.get(k, k)) + '</th><td>' + _display(v) + '</td></tr>'
                                for k, v in plan.items() if k != 'chapter') + '</table></details>')
    return ''.join(pieces)


def _design_drift(book):
    """Deviations the engine booked while reconciling a writer's drift_check."""
    pieces = ['<h2 id="drift">漂移挂账</h2><div class="sub">执笔自比与引擎核算记下的偏差：'
              '本章照常入库，但后章章纲重排必须吸收它们</div>']
    rows = book.get('design_drift') or []
    if not rows:
        return ''.join(pieces) + _empty('漂移记录')
    for row in rows:
        status = row.get('status') if isinstance(row, dict) else None
        pieces.append('<div class="card"><b>' + _esc(str(row.get('kind', '')) + ' · ' + str(row.get('key', '')))
                      + '</b><span class="pill ' + ('ok' if status == 'kept' else 'bad') + '">'
                      + _esc(DRIFT_STATUS_LABELS.get(status, status or '')) + '</span><table class="t">'
                      + ''.join('<tr><th>' + _esc(DRIFT_LABELS.get(k, SUB_LABELS.get(k, k))) + '</th><td>' + _display(v) + '</td></tr>'
                                for k, v in row.items() if k not in ('kind', 'key', 'status')) + '</table></div>')
    return ''.join(pieces) + _raw(rows)


def _understanding(book):
    pieces = ['<h2 id="understanding">作品理解</h2><p class="note">独立读者的解释与表达样本，可修订并保留反证；不属于既成事实或强制写作要求。</p>']
    kinds = {'character': '人物', 'relationship': '关系', 'theme': '母题', 'voice': '表达'}
    statuses = {'tentative': '待验证', 'supported': '有依据', 'contested': '存在争议', 'retired': '已停用'}
    rows = understanding.latest(book.get('understanding'))
    for row in rows.values():
        pieces.append('<div class="card"><b>' + _esc(row['claim']) + '</b>'
                      + _pills([kinds[row['kind']], statuses[row['status']]])
                      + '<p>' + _esc(row['reason']) + '</p>')
        for field, label in (('evidence', '原文依据'), ('counterevidence', '反证')):
            for ref in row[field]:
                pieces.append('<p class="note">' + label + ' · 第' + str(ref['chapter']) + '章</p><blockquote>'
                              + _esc(ref['quote']) + '</blockquote>')
        pieces.append('<details><summary>版本与适用范围</summary>' + _raw(row) + '</details></div>')
    return ''.join(pieces) + ('' if rows else _empty('作品理解'))


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


def _audit(book, report):
    pieces = ['<h2 id="audit">账本核验</h2><div class="sub">promote 与 complete 会复查同一组条件</div>'
              '<div class="card"><table class="t">'
              '<tr><th>结论</th><td>' + ('通过' if report['ok'] else '发现问题') + '</td></tr>'
              '<tr><th>已入库章节</th><td>' + str(report['chapters']) + '</td></tr>'
              '<tr><th>投影一致</th><td>' + ('是' if report['projection'] else '否') + '</td></tr>'
              '<tr><th>设计世代</th><td>' + str(book.get('revision')) + '</td></tr></table></div>']
    if report['problems']:
        pieces.append('<ul class="tight">' + ''.join('<li>' + _esc(p) + '</li>' for p in report['problems']) + '</ul>')
    pieces.append('<p class="note">开书透镜：' + _esc('、'.join(LENSES)) + '</p>')
    pieces.append('<p class="note">卷级转折方法：' + _esc('、'.join(VOLUME_TURNS)) + '</p>')
    return ''.join(pieces)


def _reader_controls(first):
    return ('<div class="rd-tools"><span class="lab">字号</span>'
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
                  '<button onclick="openChapter(' + str(first) + ')">从第一章读起</button></div>')


def _reader_index(rows, contract, book, page=None):
    pieces = ['<div class="book">❦ '
                  + _esc(contract['title'] if contract else '书稿') + ' ❦</div><div class="book-sub">'
                  + str(len(rows)) + ' 章 · ' + format(book.get('written_han') or 0, ',') + ' 汉字 · 目录</div>']
    seen = None
    for row in (rows if page is None else page):
        volume = volume_for(contract, row['n']) if contract else None
        if volume and volume['id'] != seen:
            seen = volume['id']
            pieces.append('<div class="vol">卷 ' + _esc(volume['id']) + ' · ' + _esc(volume.get('purpose', '')) + '</div>')
        pieces.append('<div class="item" onclick="openChapter(' + str(row['n']) + ')"><span class="no">第'
                      + str(row['n']) + '章</span><span class="ttl">' + _esc(row.get('title') or '') + '</span>'
                      '<span class="sum">' + _esc(row.get('summary') or '') + '</span></div>')
    return ''.join(pieces)


def _reader_chapter(rows, index, repo):
    row = rows[index]
    paragraphs = [line.strip() for line in repo.read_document(row['prose']).split('\n') if line.strip()]
    previous = rows[index - 1]['n'] if index else 0
    following = rows[index + 1]['n'] if index + 1 < len(rows) else 0
    return ('<section class="chapter" id="read-' + str(row['n']) + '" hidden><div class="ch-head">'
                  '<div class="orn">❖ ❖ ❖</div><h3>第' + str(row['n']) + ' 章 ' + _esc(row.get('title') or '')
                  + '</h3><div class="meta">' + format(row.get('han') or 0, ',') + ' 汉字 · '
                  + _esc(row.get('summary') or '') + '</div></div><div class="prose">'
                  + ''.join('<p>' + _esc(p) + '</p>' for p in paragraphs) + '</div><div class="ch-nav">'
                  '<button ' + ('disabled' if not previous else 'onclick="openChapter(' + str(previous) + ')"')
                  + '>← 上一章</button><button onclick="openIndex()">目录</button><span class="pos">'
                  + str(index + 1) + ' / ' + str(len(rows)) + '</span><button '
                  + ('disabled' if not following else 'onclick="openChapter(' + str(following) + ')"')
                  + '>下一章 →</button></div></section>')


def _reader(rows, repo, contract, book):
    if not rows:
        return ('<div id="view-read" hidden><div class="rd-wrap">'
                '<p class="note" style="padding:24px">尚无已提交章节。</p></div></div>')
    return ('<div id="view-read" hidden>' + _reader_controls(rows[0]['n'])
            + '<div class="rd-wrap" id="rd-wrap"><div id="ch-index">'
            + _reader_index(rows, contract, book) + '</div>'
            + ''.join(_reader_chapter(rows, index, repo) for index in range(len(rows)))
            + '</div></div>')


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


def render(repo: PublicationReader):
    """Build the whole page as one HTML string."""
    book, rows = publication(repo)
    branch = book['branch']
    contract = book.get('contract')
    written = book.get('written_han') or 0
    title = contract['title'] if contract else '未定名书稿'
    generated = time.strftime('%Y-%m-%d %H:%M', time.localtime(book['completed_at'])) if book.get('completed_at') else time.strftime('%Y-%m-%d %H:%M')

    nav = ''.join('<a href="#%s">%s</a>' % (key, label) for key, label in SECTIONS)
    jump = ('<select id="jump-read" class="toc-select" style="display:none" onchange="jump(this)">'
            '<option>跳转章节…</option>'
            + ''.join('<option data-n="%d">第%d章</option>' % (row['n'], row['n']) for row in rows) + '</select>')
    settings = ''.join(section(book, rows, key) for key, _ in SECTIONS)
    templates = Path(__file__).with_name('templates')
    shell = Template((templates / 'book.html').read_text(encoding='utf-8'))
    return shell.substitute(
        title=_esc(title), branch=_esc(branch), chapter_count=len(rows),
        written=format(written, ','), generated=_esc(generated), nav=nav, jump=jump,
        settings=settings, reader=_reader(rows, repo, contract, book),
        styles=(templates / 'book.css').read_text(encoding='utf-8'),
        script=(templates / 'book.js').read_text(encoding='utf-8'))



def write(repo: PublicationReader, output=None, *, workspace: LocalWorkspace, standalone=False, entry=None):
    """Maintain a small preview entry; full offline content is an explicit export."""
    target = (workspace.output_path(output, 'book.html') if output
              else workspace.artifact_path(workspace.project / 'book.html'))
    require(not standalone or (output and not workspace.same_path(target, workspace.project / 'book.html')),
            'output', '离线全书请用 --output 指定其他文件，例如 book-export.html。')
    _, rows = publication(repo)
    view = render(repo) if standalone else live_shell(workspace.project, entry)
    if target.is_symlink() or not target.is_file() or target.read_bytes() != view.encode('utf-8'):
        workspace.write_text(target, view)
    return {'path': str(target), 'chars': len(view), 'chapters': len(rows),
            'mode': 'standalone' if standalone else 'live',
            'preview_command': preview_command(workspace.project, entry),
            'inside_project': target.is_relative_to(workspace.project)}


def section(book, rows, key):
    """Render one settings surface, without loading any chapter prose."""
    contract = book.get('contract')
    state = book.get('state') or {}
    renderers = {
        'overview': lambda: _overview(book, contract, rows, state,
                                     {k: v for k, v in (state.get('hooks') or {}).items()
                                      if v.get('status') == 'open'},
                                     _audit_report(book, rows), book.get('written_han') or 0),
        'contract': lambda: _contract(contract) if contract else
                           '<h2 id="contract">创作约定</h2>' + _empty('生效约定'),
        'world': lambda: _world(book),
        'outline': lambda: _outlines(book),
        'plans': lambda: _plans(book, contract),
        'understanding': lambda: _understanding(book),
        'ledger': lambda: _ledger(state),
        'drift': lambda: _design_drift(book),
        'audit': lambda: _audit(book, _audit_report(book, rows)),
    }
    require(key in renderers, 'section', '未知预览栏目。')
    return renderers[key]()


def preview_fragment(repo: PublicationReader, kind, value=None, *, offset=0, query=''):
    """Live responses contain one section, one index page, or one chapter."""
    book, rows = publication(repo)
    contract = book.get('contract')
    if kind == 'section':
        content = section(book, rows, value)
    elif kind == 'index':
        matching = [row for row in rows if not query or query.casefold() in
                    ('第%d章 %s %s' % (row['n'], row.get('title', ''), row.get('summary', ''))).casefold()]
        limit = 100
        content = _reader_index(rows, contract, book, matching[offset:offset + limit])
        if not matching:
            content += '<p class="note">' + ('没有匹配章节。' if rows else '尚无已提交章节。') + '</p>'
        content += ('<div class="ch-nav"><button ' +
                    ('disabled' if offset == 0 else 'onclick="loadIndex(%d)"' % max(0, offset - limit)) +
                    '>← 上一页</button><span>共 %d 章</span><button ' % len(matching) +
                    ('disabled' if offset + limit >= len(matching) else 'onclick="loadIndex(%d)"' % (offset + limit)) +
                    '>下一页 →</button></div>')
    else:
        require(kind == 'chapter', 'chapter', '未知预览内容。')
        index = next((i for i, row in enumerate(rows) if row['n'] == value), None)
        require(index is not None, 'chapter', '正式章节不存在。')
        content = _reader_chapter(rows, index, repo).replace(' hidden>', '>', 1)
    return {'html': content, 'title': contract['title'] if contract else '未定名书稿',
            'branch': book['branch'], 'chapters': len(rows), 'written': book.get('written_han') or 0}


def preview_command(project, entry=None):
    entry = entry or Path(__file__).resolve().parents[1] / 'novel.py'
    return [sys.executable, str(entry), '--project', str(project), 'preview', '--open']


def live_shell(project, entry=None):
    """The entry is independent of book length and contains no embedded story data."""
    templates = Path(__file__).with_name('templates')
    command = preview_command(project, entry)
    command_text = subprocess.list2cmdline(command) if os.name == 'nt' else shlex.join(command)
    instructions = ('<div id="preview-help" class="card"><h2>打开作品预览</h2>'
                    '<p>在终端运行以下命令，浏览器会打开预览。保持命令运行，结束时按 Ctrl+C。</p>'
                    '<pre>' + _esc(command_text) + '</pre>'
                    '<p>设定按栏目读取，正文按章读取；页面不保存整本书。</p></div>')
    return Template((templates / 'book.html').read_text(encoding='utf-8')).substitute(
        title='作品预览', branch='—', chapter_count='—', written='—', generated='读取时更新',
        nav=''.join('<a href="#%s">%s</a>' % item for item in SECTIONS), jump='',
        settings=instructions + '<div id="live-settings"></div>',
        reader='<div id="view-read" hidden>' + _reader_controls(1)
               + '<div class="rd-wrap" id="rd-wrap"><div id="ch-index"></div>'
                 '<div id="chapter-slot"></div></div></div>',
        styles=(templates / 'book.css').read_text(encoding='utf-8'),
        script='window.NOVEL_LIVE=true;\n' + (templates / 'book.js').read_text(encoding='utf-8')
               + '\n' + (templates / 'preview.js').read_text(encoding='utf-8'))
