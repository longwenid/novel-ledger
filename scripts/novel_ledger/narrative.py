"""Evidence-backed story progress. Design intentions never change these projections."""
from __future__ import annotations

import copy
from decimal import Decimal, InvalidOperation
from .contracts import require, text

STATUSES = ('seeded', 'advanced', 'resolved')
REVEALS = ('hinted', 'suspected', 'misled', 'confirmed', 'retracted')


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
        if isinstance(expect, bool) or isinstance(got, bool):
            return False
        try:
            left, right = Decimal(str(expect).strip()), Decimal(str(got).strip())
            return left.is_finite() and right.is_finite() and left == right
        except (InvalidOperation, TypeError, ValueError):
            return False
    return expect == got


def unmet(state, plan):
    return [p for p in plan.get('preconditions', []) if not same(p['kind'], p['expected'], value(state, p))]


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
            {'nodes': missing, 'threads': open_lines, 'recover': '在正文中兑现并通过提交核账；改变终局要求须走作者改约。'})


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
