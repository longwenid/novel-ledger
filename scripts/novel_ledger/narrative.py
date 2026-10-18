"""Evidence-backed story progress. Design intentions never change these projections."""
from __future__ import annotations

import copy
from .contracts import require, text

STATUSES = ('seeded', 'advanced', 'resolved')
REVEALS = ('hinted', 'suspected', 'misled', 'confirmed', 'retracted')
PACE_FIELDS = ('role', 'pressure_in', 'pressure_out', 'emotional_aftereffect', 'recovery_purpose')
PACE_ROLES = ('setup', 'pressure', 'turn', 'climax', 'aftermath', 'recovery', 'relationship', 'discovery')


# The coordinate names a chapter outline's `enter`/`exit` rows use, mapped to the projection field
# they read. A chapter speaks of `character` and `thread`; the state stores `character_current` and
# `thread_progress`. Both spellings resolve to the same value.
FIELDS = {'node': 'story_nodes', 'thread': 'thread_progress', 'character': 'character_current',
          'characters': 'character_current'}
STANCES = {'hinted': 'suspects', 'suspected': 'suspects', 'misled': 'believes',
           'confirmed': 'knows', 'retracted': 'disproved'}
# Reading a settled projection back needs the reverse direction: facts.settle stores the stance,
# and a chapter outline speaks the reveal stage the reader is at.
STANCE_REVEALS = {stance: reveal for reveal, stance in STANCES.items()}


def registry(book):
    """The book's node and thread registry.

    v2 registers them per volume: `book['volumes_outline'][vid]` carries `nodes` and `threads`, and
    a cross-volume line says `continues: true` — the first registration is the definition. A node
    always leaves here with a `line`, because a story_node event activates the line it belongs to
    and the closure guard reads `node['line']`; a volume row may name it explicitly, and a node that
    does not defaults to its own kind (main/side/hidden).
    """
    nodes, threads = {}, {}
    for design in (book.get('designs') or {}).values():
        nodes.update({n['id']: n for n in design.get('nodes', [])})
        threads.update({t['id']: t for t in design.get('threads', [])})
    for outline in (book.get('volumes_outline') or {}).values():
        if not isinstance(outline, dict):
            continue
        for node in outline.get('nodes') or []:
            if isinstance(node, dict) and text(node.get('id')):
                nodes[node['id']] = {**copy.deepcopy(node),
                                     'line': node.get('line') or node.get('thread') or node.get('kind') or 'main',
                                     'depends_on': list(node.get('depends_on') or [])}
        for thread in outline.get('threads') or []:
            if isinstance(thread, dict) and text(thread.get('id')):
                threads.setdefault(thread['id'], copy.deepcopy(thread))
    return nodes, threads


def validate_threads(data, nodes, known_threads=()):
    threads = data.get('threads')
    require(isinstance(threads, list), 'story_threads', '跟踪设计须声明 threads；卷沿用既有线路时可为空。')
    ids = []
    for item in threads:
        require(isinstance(item, dict) and all(text(item.get(k)) for k in ('id', 'purpose', 'ending_condition'))
                and item.get('kind') in ('main', 'side', 'hidden') and type(item.get('required')) is bool,
                'story_threads', '线路需要 id/kind:main|side|hidden/purpose/ending_condition/required。')
        ids.append(item['id'])
    require(len(ids) == len(set(ids)) and not set(ids).intersection(known_threads), 'story_threads', '线路 ID 不能重复或覆盖。')
    available = set(ids) | set(known_threads)
    require(all(n['line'] in available for n in nodes), 'story_line', '节点须归属已登记线路。')
    for node in nodes:
        require(type(node.get('required')) is bool, 'story_node', '节点须声明 required，明确完本是否必须兑现。')
        window = node.get('window')
        require(isinstance(window, list) and len(window) == 2 and all(type(n) is int for n in window)
                and 1 <= window[0] <= window[1], 'story_window', '节点须声明 window=[最早章,最晚章]，远期保留粗范围。')
    return copy.deepcopy(threads)


def progress(state, ident):
    return state.get('story_nodes', {}).get(ident, {}).get('status')


def value(state, item):
    kind, key = item['kind'], item['key']
    if kind == 'clock':
        return state['clock']
    if kind in FIELDS:
        field = FIELDS[kind]
        entry = state.get(field, {}).get(key)
        if kind == 'node':
            return (entry or {}).get('status')
        if kind == 'thread':
            return (entry or {}).get('status')
        return (entry or {}).get('value')
    if kind == 'knowledge':
        entry = state.get('knowledge', {}).get(key)
        if not isinstance(entry, dict):
            return None
        return entry.get('status') if entry.get('status') in REVEALS else STANCE_REVEALS.get(entry.get('stance'))
    return state.get(kind, {}).get(key)


def same(kind, expect, got):
    """Whether a declared coordinate value equals the projection, reading quantities as numbers.

    `state['resources']` stores decimal strings while an outline declares `from: 0`; comparing those
    as strings would report every resource precondition as unmet.
    """
    if kind in ('resources', 'clock'):
        try:
            return float(str(expect).strip()) == float(str(got).strip())
        except (TypeError, ValueError):
            return False
    return expect == got


def unmet(state, plan):
    return [p for p in plan.get('preconditions', []) if not same(p['kind'], p['expected'], value(state, p))]


def validate_plan(plan, nodes, state):
    actions = plan.get('node_actions')
    require(isinstance(actions, list) and actions and all(isinstance(a, dict) and a.get('node') in plan['node_ids']
            and a.get('after') in STATUSES for a in actions), 'story_actions', 'node_actions 需要 {node,after:seeded|advanced|resolved}。')
    require(len(actions) == len({a['node'] for a in actions}) and {a['node'] for a in actions} == set(plan['node_ids']),
            'story_actions', 'node_actions 须恰好覆盖本章节点，不得重复。')
    require(isinstance(plan.get('preconditions'), list), 'plan_preconditions', '声明 preconditions=[{kind,key,expected}]，无额外前提用空数组。')
    for item in plan['preconditions']:
        require(isinstance(item, dict) and item.get('kind') in ('facts', 'knowledge', 'resources', 'relations', 'placements', 'character_current', 'node', 'clock')
                and text(item.get('key')) and 'expected' in item, 'plan_preconditions', '计划前提坐标或 expected 缺失。')
    require(not unmet(state, plan), 'plan_preconditions', '章计划的前提与当前/窗口模拟状态不符。',
            {'unmet': unmet(state, plan), 'recover': '依据真实状态重排近期计划，不要改历史事实。'})
    pace = plan.get('pacing')
    require(isinstance(pace, dict) and all(text(pace.get(k)) for k in PACE_FIELDS) and pace['role'] in PACE_ROLES,
            'pacing', 'pacing 需要 role/pressure_in/pressure_out/emotional_aftereffect/recovery_purpose，均用具体文字；不需恢复时说明原因。')
    require(isinstance(plan.get('disclosures'), list) and all(isinstance(d, dict) and text(d.get('topic'))
            and d.get('after') in REVEALS for d in plan['disclosures']), 'disclosure', 'disclosures=[{topic,after}] 声明本章允许的读者认知变化，无变化用空数组。')
    require(len(plan['disclosures']) == len({d['topic'] for d in plan['disclosures']}), 'disclosure', '披露 topic 重复。')
    for action in actions:
        node = nodes[action['node']]
        require(node['window'][0] <= plan['chapter'] <= node['window'][1], 'story_window', '节点安排超出了已核验的章节范围。')
        require(progress(state, node['id']) != 'resolved', 'story_resolved', '已兑现节点不能反复安排推进。')
        if action['after'] != 'seeded':
            missing = [n for n in node['depends_on'] if progress(state, n) != 'resolved']
            require(not missing, 'story_dependency', '前置因果尚未兑现，不能提前推进/兑现。', {'node': node['id'], 'unresolved': missing})
        state.setdefault('story_nodes', {})[node['id']] = {'status': action['after']}
    plan['node_contracts'] = {a['node']: copy.deepcopy(nodes[a['node']]) for a in actions}


def prepare_events(events, plan):
    """Normalize design coordinates only; the independent reviewer supplies outcomes and evidence."""
    result = copy.deepcopy(events)
    require(isinstance(result, list) and all(isinstance(e, dict) for e in result), 'story_coverage', 'events 须为事件对象数组。')
    actions = {a['node']: a['after'] for a in plan['node_actions']}
    seen, revealed = {}, {}
    for event in result:
        if event.get('op') == 'story_node':
            ident = event.get('node')
            require(text(ident) and ident in actions and ident not in seen and event.get('after') == actions[ident],
                    'story_coverage', '正文节点事件须逐项匹配本章计划，不得漏报、重复或替换结果。')
            definition = plan['node_contracts'][ident]
            event['line'], event['depends_on'] = definition['line'], list(definition['depends_on'])
            seen[ident] = event['after']
        if event.get('op') == 'reader_knowledge':
            topic = event.get('topic')
            require(text(topic) and topic not in revealed, 'disclosure', '读者认知 topic 须为非空字符串，同章不重复。')
            revealed[topic] = event.get('after')
    require(seen == actions, 'story_coverage', '事实审稿遗漏了计划节点的正文实现。', {'expected': actions, 'actual': seen})
    require(revealed == {d['topic']: d['after'] for d in plan['disclosures']}, 'disclosure', '读者披露与本章许可范围不一致。')
    return result


def settle_event(state, event, chapter):
    op = event['op']
    require('story_nodes' in state, 'story_protocol', '当前约定未启用叙事跟踪；通过明确改约启用后使用。')
    if op == 'story_node':
        ident, after = event.get('node'), event.get('after')
        require(text(ident) and text(event.get('line')) and isinstance(event.get('depends_on'), list)
                and all(text(d) for d in event['depends_on']) and after in STATUSES and text(event.get('outcome')),
                'story_node', '节点事件需要 node/before/after/outcome，线路和依赖由引擎冻结。')
        old = progress(state, ident)
        require('before' in event and event['before'] == old and old != 'resolved'
                and not (old == 'advanced' and after == 'seeded'), 'story_precondition', '节点前态不符或发生倒退/重复兑现。')
        require(after == 'seeded' or all(progress(state, d) == 'resolved' for d in event['depends_on']),
                'story_dependency', '节点事件不能跳过尚未兑现的前置因果。')
        prior_criteria = state['story_nodes'].get(ident, {}).get('criteria', {})
        state['story_nodes'][ident] = {'status': after, 'outcome': event['outcome'], 'chapter': chapter, 'evidence': event['evidence'],
                                     **({'criteria': {**prior_criteria, **{c['id']: c for c in event['criteria']}}} if 'criteria' in event or prior_criteria else {})}
        previous = state['thread_progress'].get(event['line'], {})
        require(previous.get('status') != 'resolved', 'story_thread', '已关闭线路不能继续推进。')
        state['thread_progress'][event['line']] = {**previous, 'status': 'active', 'last_chapter': chapter, 'evidence': event['evidence']}
    elif op == 'story_thread':
        ident, after = event.get('thread'), event.get('after')
        require(text(ident), 'story_thread', 'thread 须为非空线路 ID。')
        old = state['thread_progress'].get(ident, {})
        require('before' in event and after in ('active', 'dormant', 'resolved') and event.get('before') == old.get('status')
                and old.get('status') != 'resolved' and text(event.get('reason')), 'story_thread', '线路变更需要 thread/before/after/reason。',
                {'current': old.get('status'), 'recover': '事件按数组顺序结算；story_node 会先激活所属线路，紧跟的线路事件 before 须按 current 填写。'})
        due = event.get('return_by')
        require(after != 'dormant' or type(due) is int and due > chapter, 'story_thread', '暂缓线路须声明未来章节 return_by。')
        state['thread_progress'][ident] = {'status': after, 'last_chapter': chapter, 'return_by': due,
                                          'reason': event['reason'], 'evidence': event['evidence']}
    elif op == 'reader_knowledge':
        topic, after = event.get('topic'), event.get('after')
        require(text(topic), 'reader_knowledge', 'topic 须为非空 ID。')
        old = state['reader_knowledge'].get(topic, {})
        require(text(topic) and after in REVEALS and 'before' in event and event['before'] == old.get('status')
                and text(event.get('claim')), 'reader_knowledge', '读者认知需要 topic/before/after/claim。')
        require(old.get('status') != 'confirmed' or after in ('confirmed', 'retracted'), 'reader_knowledge', '已确认信息不能无解释退回暗示。')
        require(after != 'retracted' or text(event.get('reason')), 'reader_knowledge', '推翻已知信息须说明正文中的原因。')
        state['reader_knowledge'][topic] = {'status': after, 'claim': event['claim'], 'chapter': chapter, 'evidence': event['evidence']}
    elif op == 'character_current':
        ident, after = event.get('entity'), event.get('after')
        require(text(ident), 'character_current', 'entity 须为非空人物 ID。')
        old = state['character_current'].get(ident, {}).get('value')
        require(ident in state['entities'] and 'before' in event and event['before'] == old and isinstance(after, dict)
                and all(text(after.get(k)) for k in ('desire', 'stance', 'relationship_focus'))
                and all(text(event.get(k)) for k in ('choice', 'cost', 'change')), 'character_current', '当前人物状态须有 before、after={desire,stance,relationship_focus} 及选择、代价、变化。')
        state['character_current'][ident] = {'value': after, 'chapter': chapter, 'evidence': event['evidence']}


def closure(book):
    nodes, threads = registry(book)
    missing = [ident for ident, node in nodes.items() if node.get('required') and progress(book['state'], ident) != 'resolved']
    open_lines = [ident for ident, thread in threads.items() if thread['required'] and book['state']['thread_progress'].get(ident, {}).get('status') != 'resolved']
    require(not missing and not open_lines, 'story_closure', '必要节点或线路尚未完成，不能宣告完本。',
            {'nodes': missing, 'threads': open_lines, 'recover': '在正文中兑现并独立核验；改变终局要求须走作者改约。'})


def budget_for(book, chapter, through=None):
    # A pending carry row is fixed only beyond the chapter/window being rewritten.
    # Future alignment can clear plans while their original prose remains queued.
    boundary = chapter if through is None else through
    carried = [r for r in (book.get('revision_run') or {}).get('carry', []) if r['n'] > boundary]
    contract = copy.deepcopy(book['contract'])
    for volume in contract['volumes']:
        volume['end'] = book.get('scope_ends', {}).get(volume['id'], volume['end'])
    return word_budget(contract, book['written_han'], chapter, sum(r['han'] for r in carried), len(carried))


def word_budget(contract, written, chapter, reserved_han=0, reserved_chapters=0):
    last = contract['volumes'][-1]['end']
    remaining = last - chapter + 1 - reserved_chapters
    effective = written + reserved_han
    # The total is a projection of the chapter count and the per-chapter range, so it is derived
    # here from the count in force: an authorized append or revision moves the count and the band
    # together, and a budget read off a stale frozen band would refuse a legal extension.
    lo, hi = last * contract['chapter_min'], last * contract['chapter_max']
    minimum = max(contract['chapter_min'], lo - effective - max(0, remaining - 1) * contract['chapter_max'])
    maximum = min(contract['chapter_max'], hi - effective - max(0, remaining - 1) * contract['chapter_min'])
    require(remaining > 0 and minimum <= maximum, 'word_budget', '剩余章数已无法达到总篇幅约定。',
            {'written_han': written, 'remaining_chapters': remaining,
            'reachable_total': [effective + remaining * contract['chapter_min'], effective + remaining * contract['chapter_max']],
             'required_total': [lo, hi], 'recover': '修订前文展开或由作者改约；不要继续写无法完成的章节。'})
    return {'chapter': chapter, 'minimum': minimum, 'maximum': maximum,
            'aim': min(maximum, max(minimum, contract['chapter_aim'])), 'remaining_chapters': remaining,
            'fixed_suffix_han': reserved_han, 'fixed_suffix_chapters': reserved_chapters}
