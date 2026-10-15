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
from string import Template
from .contracts import CONTRACT_FIELDS, LENSES, VOLUME_TURNS, han_count
from .ports import PublicationReader
from .publication import publication
from .workspace import LocalWorkspace
from .planning import volume_for
from .world import LABELS as WORLD_LABELS, SECTIONS as WORLD_SECTIONS
from . import creation, understanding
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
                'planning_window': '规划窗口', 'review_interval': '复审间隔',
                'review_chunk': '复审块大小', 'initial_facts': '初始事实', 'places': '初始地点',
                'placements': '初始站位', 'arcs': '人物弧', 'editorial_features': '编辑能力',
                'scope_append_limit': '单轮补写章数上限', 'volume_outline': '逐章卷纲要求', 'anchors': '稳定设定', 'links': '空间连接'}
# Option values that are engine bookkeeping rather than an author-facing decision: the structural gate's
# tier id and its arithmetic window are already stated in the option's own sentence.
OPENING_VALUE_HIDDEN = ('tier', 'chapter_window')
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
            ('plans', '章计划'), ('profiles', '人物档案'), ('understanding', '作品理解'), ('ledger', '事实账本'), ('reviews', '章审记录'),
            ('audit', '账本核验'))




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
        for index, reading in enumerate(review.get('revision_readings', []), 1):
            pieces.append(_revision_reading(reading, index))
        pieces.append('</details>')
    return ''.join(pieces)


def _review_evidence(refs):
    return ''.join('<p class="note">原文依据 · 第' + _esc(ref.get('chapter', ''))
                   + '章</p><blockquote>' + _esc(ref.get('quote', '')) + '</blockquote>' for ref in refs)


def _revision_reading(reading, index):
    receipt = reading['receipt']
    pieces = ['<details><summary>修订独立重读 · 第' + str(index) + '次 · '
              + _esc(VERDICT_LABELS.get(receipt.get('verdict'), receipt.get('verdict', ''))) + '</summary>',
              '<p class="note" style="overflow-wrap:anywhere">正文版本：' + _esc(reading['prose_hash'])
              + '<br>审稿会话：' + _esc(reading['reviewer']) + '<br>核验清单版本：'
              + _esc(receipt.get('checks_version', 1)) + '</p>', '<h3>冻结首读</h3>']
    labels = {'desire': '期待', 'obstacle': '阻碍', 'change': '变化', 'read_on_reason': '追读理由'}
    for first in reading['first_read']['reads']:
        pieces.append('<div class="card"><b>第' + _esc(first['chapter']) + '章</b><table class="t">'
                      + ''.join('<tr><th>' + label + '</th><td>' + _esc(first[key]) + '</td></tr>'
                                for key, label in labels.items()) + '</table></div>')
    for check in receipt.get('checks', []):
        pieces.append('<p><b>' + _esc(CHECK_LABELS.get(check['id'], check['id'])) + '</b> · '
                      + _esc(VERDICT_LABELS.get(check['result'], check['result'])) + ' · '
                      + _esc(check['reason']) + '</p>' + _review_evidence(check.get('evidence', [])))
    for finding in receipt.get('findings', []):
        evidence = finding.get('evidence', [])
        pieces.append('<p>发现（' + _esc(finding.get('severity', '')) + '）：'
                      + _esc(finding['reason']) + '</p>'
                      + _review_evidence(evidence if isinstance(evidence, list) else [evidence]))
    pieces.append(_raw(reading) + '</details>')
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


def render(repo: PublicationReader):
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
    settings = ''.join((
        _overview(book, contract, rows, state, open_hooks, report, written),
        _contract(contract) if contract else '<h2 id="contract">创作约定</h2>' + _empty('生效约定'),
        _world(book), _designs(book), _plans(book, contract), _profiles(book), _understanding(book),
        _ledger(state), _reviews(rows, repo), _audit(book, report)))
    templates = Path(__file__).with_name('templates')
    shell = Template((templates / 'book.html').read_text(encoding='utf-8'))
    return shell.substitute(
        title=_esc(title), branch=_esc(branch), chapter_count=len(rows),
        written=format(written, ','), generated=_esc(generated), nav=nav, jump=jump,
        settings=settings, reader=_reader(rows, repo, contract, book),
        styles=(templates / 'book.css').read_text(encoding='utf-8'),
        script=(templates / 'book.js').read_text(encoding='utf-8'))



def write(repo: PublicationReader, output=None, *, workspace: LocalWorkspace):
    """Write the view (default <project>/book.html) and report where it went."""
    target = (workspace.output_path(output, 'book.html') if output
              else workspace.artifact_path(workspace.project / 'book.html'))
    view = render(repo)
    workspace.write_text(target, view)
    _, rows = publication(repo)
    return {'path': str(target), 'chars': len(view), 'chapters': len(rows),
            'inside_project': target.is_relative_to(workspace.project)}
