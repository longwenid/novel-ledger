"""Evidence-backed reducers. Accept values, return a new state; no side effects."""
from __future__ import annotations

import copy
from decimal import Decimal, InvalidOperation, localcontext
from .contracts import Error, TIME_MARKERS, digest, dump, require, text
from . import narrative, spatial
from .evidence import evidence
from .entities import register as register_entity


def amount(value):
    require(isinstance(value, str), 'amount', '资源数量使用十进制字符串。')
    try:
        number = Decimal(value)
    except InvalidOperation:
        raise Error('amount', '数量不是有效十进制数。')
    require(number.is_finite() and number >= 0 and len(number.as_tuple().digits) <= 120
            and abs(number.as_tuple().exponent) <= 120, 'amount', '数量须非负、有限且在精度范围内。')
    return number


def spell(number):
    """The canonical spelling of a quantity: an integral balance carries no decimal point.

    Every comparison still goes through `amount`, so nothing about conservation, the negative check
    or the precision bound relaxes here. What this fixes is the shape the author reads back: an
    author who seeded four units and spent one must see `3`, and a caller that built its flow event
    from float arithmetic must not be able to write `3.0` into the ledger.
    """
    return str(int(number)) if number == number.to_integral_value() else str(number)


def resource_key(holder, asset, unit):
    return dump([holder, asset, unit])


def entity(state, item):
    """Register an entity in the factual state using the shared identity rules."""
    register_entity(state['entities'], item)


def seed(contract):
    state = {k: {} for k in ('entities', 'facts', 'knowledge', 'resources', 'relations', 'hooks', 'clock_threads', 'places', 'placements', 'historical_assertions', 'developments')}
    state['clock'] = 0
    if contract.get('narrative_tracking'):
        state.update({k: {} for k in ('story_nodes', 'thread_progress', 'reader_knowledge', 'character_current')})
    for item in contract.get('entities', []):
        entity(state, item)
    for item in contract.get('initial_facts', []):
        require(item.get('entity') in state['entities'] and text(item.get('key')) and 'value' in item, 'initial_fact', '初始事实缺少实体、键或值。')
        key = item['entity'] + ':' + item['key']
        require(key not in state['facts'], 'initial_fact', '初始事实重复。')
        state['facts'][key] = item['value']
    for item in contract.get('initial_resources', []):
        require(item.get('holder') in state['entities'] and text(item.get('asset')) and text(item.get('unit')), 'resource', '资源归属、资产或单位缺失。')
        key = resource_key(item['holder'], item['asset'], item['unit'])
        require(key not in state['resources'], 'resource', '初始资源重复。')
        state['resources'][key] = spell(amount(item.get('quantity')))
    for item in contract.get('places', []):
        require(isinstance(item, dict) and text(item.get('id')) and text(item.get('name')), 'place', '地点需要 id/name。')
        require(item['id'] not in state['places'], 'place', '地点 ID 重复。')
        state['places'][item['id']] = copy.deepcopy(item)
    for item in state['places'].values():
        require(item.get('parent') is None or item['parent'] in state['places'], 'place', '父地点不存在。')
        seen, at = set(), item['id']
        while at is not None:
            require(at not in seen, 'place_cycle', '地点包含关系有环。')
            seen.add(at)
            at = state['places'][at].get('parent')
    for ident, place in contract.get('placements', {}).items():
        require(ident in state['entities'] and place in state['places'], 'placement', '初始站位实体或地点不存在。')
        state['placements'][ident] = place
    if contract.get('editorial_features'):
        spatial.seed(state, contract)
    return state


def _before(container, key, event):
    require('before' in event and 'after' in event and container.get(key) == event['before'],
            'precondition', '事实前值不匹配。', {'key': key, 'current': container.get(key), 'recover': '照抄 current 为 before；新值放 after。'})


def prepare_hook_links(events):
    """Stamp the hook-link protocol onto events that carry linked fields."""
    require(isinstance(events, list), 'events', '事实结算须提供 events 数组。')
    result = copy.deepcopy(events)
    for event in result:
        if isinstance(event, dict) and event.get('op') == 'hook':
            require('hook_links_version' not in event, 'hook_reference', '承诺关联版本由引擎填写。')
            if any(k in event for k in ('subjects', 'topics')):
                event['hook_links_version'] = 1
    return result


def apply_event(state, event, chapter):
    """Apply one event to an owned projection, without checking prose evidence.

    Used by design simulation, reconciliation and final settlement. Callers own the scratch state;
    only settle validates evidence and returns a canonical state eligible for persistence.
    """
    op = event.get('op')
    if op in spatial.OPS:
        spatial.settle(state, event)
    elif op in ('story_node', 'story_thread', 'reader_knowledge', 'character_current'):
        narrative.settle_event(state, event, chapter)
    elif op == 'entity':
        entity(state, event.get('entity'))
    elif op == 'alias':
        ident, alias = event.get('entity'), event.get('alias')
        require(ident in state['entities'] and text(alias), 'alias', '别名实体或称呼无效。')
        used = {s for e in state['entities'].values() for s in [e['name']] + e.get('aliases', [])}
        require(alias not in used, 'alias_conflict', '别名已使用。')
        state['entities'][ident].setdefault('aliases', []).append(alias)
    elif op == 'state':
        ident, key = event.get('entity'), event.get('key')
        require(ident in state['entities'] and text(key), 'state', '状态实体或键无效。')
        require(key not in ('location', 'location_id', 'holder') or ident not in state['placements'], 'placement', '已登记站位用 move 事件修改。')
        full = ident + ':' + key
        _before(state['facts'], full, event)
        require(key != 'alive' or event['before'] is not False or event['after'] is not True or text(event.get('exception_reason')), 'resurrection', '复活须说明世界规则与因果。')
        state['facts'][full] = event['after']
    elif op == 'relation':
        src, dst, key = event.get('from'), event.get('to'), event.get('key')
        require(src in state['entities'] and dst in state['entities'] and src != dst and text(key)
                and not any(c in key for c in ':>'), 'relation', '关系坐标无效。')
        full = src + '>' + dst + ':' + key
        _before(state['relations'], full, event)
        state['relations'][full] = event['after']
    elif op == 'knowledge':
        ident, topic = event.get('entity'), event.get('topic')
        require(ident in state['entities'] and text(topic) and text(event.get('claim')) and text(event.get('source'))
                and event.get('stance') in ('knows', 'believes', 'suspects', 'disproved'), 'knowledge', '认知需要对象、命题、来源和立场。')
        key = ident + ':' + topic
        old = state['knowledge'].get(key)
        require('before' in event and event['before'] == (old['claim'] if old else None), 'precondition', '认知前值不匹配。',
                {'current': old['claim'] if old else None,
                 'recover': '新 topic 的 before 为 null；已有 topic 的 before 照抄 current（旧 claim 原文）。'})
        state['knowledge'][key] = {k: event[k] for k in ('claim', 'source', 'stance', 'evidence')}
    elif op == 'resource':
        src, dst, asset, unit = event.get('from'), event.get('to'), event.get('asset'), event.get('unit')
        require(src != dst and (src is not None or dst is not None) and all(h is None or h in state['entities'] for h in (src, dst))
                and text(asset) and text(unit) and text(event.get('reason')), 'resource', '资源坐标与流动原因无效。')
        quantity = amount(event.get('quantity'))
        require(quantity > 0, 'resource', '资源流动须大于零。')
        for holder, sign, field in ((src, -1, 'from_before'), (dst, 1, 'to_before')):
            if holder is None:
                continue
            key = resource_key(holder, asset, unit)
            old = amount(state['resources'].get(key, '0'))
            require(field in event and amount(event[field]) == old, 'precondition', '资源前值不匹配。', {'current': str(old), 'field': field, 'recover': '将对应 before 字段设为 current。'})
            with localcontext() as ctx:
                ctx.prec = 512
                new = old + sign * quantity
            require(new >= 0, 'insufficient_resource', '资源不足。')
            state['resources'][key] = spell(amount(str(new)))
    elif op == 'clock':
        thread = event.get('thread')
        require(thread is None or text(thread), 'clock', '支线时间 ID 须非空。')
        current = state['clock_threads'].get(thread, state['clock']) if thread else state['clock']
        require(type(event.get('before')) is int and type(event.get('after')) is int
                and event['before'] == current and event['after'] >= current, 'time_conflict', '时间前值不匹配或发生倒退。',
                {'current': current, 'recover': 'before 照抄 current；after 不得小于 current。'})
        if thread:
            state['clock_threads'][thread] = event['after']
        else:
            state['clock'] = event['after']
    elif op == 'hook':
        ident, status = event.get('id'), event.get('status')
        require(text(ident) and status in ('open', 'paid', 'closed'), 'hook', '承诺 ID 或状态无效。')
        old = state['hooks'].get(ident)
        require('before' in event and event['before'] == (old['status'] if old else None), 'precondition', '承诺前态不匹配。',
                {'current': old['status'] if old else None,
                 'recover': '新承诺的 before 为 null；已有承诺照抄 current（当前 status 原文）。'})
        require((old is None and status == 'open') or (old is not None and old['status'] == 'open'), 'hook', '承诺未埋设或已关闭。')
        due = event.get('due', old.get('due') if old else None)
        require(type(due) is int and due >= chapter, 'hook_due', '承诺期限须为当前或后续章节。')
        item = copy.deepcopy(old) if old else {'text': event.get('text'), 'seed': event['evidence'], 'extensions': 0}
        require(text(item.get('text')), 'hook', '新承诺需要内容。')
        require('hook_links_version' not in event or event['hook_links_version'] == 1,
                'hook_reference', '未知承诺关联事件版本。')
        for field in (('subjects', 'topics') if event.get('hook_links_version') == 1 else ()):
            if field in event:
                refs = event[field]
                require(isinstance(refs, list) and all(text(r) for r in refs) and len(refs) == len(set(refs)),
                        'hook_reference', '承诺 subjects/topics 须为不重复的非空 ID 数组，可用空数组表示无关联。')
                require(field != 'subjects' or all(r in state['entities'] for r in refs),
                        'hook_reference', '承诺 subjects 只能引用已成立的人物或物品实体。')
                require(not old or field not in old or old[field] == refs or text(event.get('reason')),
                        'hook_reference', '改变已登记的承诺关联须给出正文依据及 reason。')
                item[field] = list(refs)
        if old and due > old['due']:
            item['extensions'] += 1
            require(item['extensions'] <= 2 and text(event.get('reason')), 'hook_extension', '延期须有因果，最多两次。')
        require(status != 'closed' or text(event.get('reason')), 'hook', '取消承诺须解释正文交代。')
        item.update(status=status, due=due, last=event['evidence'])
        state['hooks'][ident] = item
    elif op == 'place':
        item = event.get('place')
        require(isinstance(item, dict) and text(item.get('id')) and text(item.get('name')) and item['id'] not in state['places'], 'place', '新地点需要未使用的 id/name。')
        require(item.get('parent') is None or item['parent'] in state['places'], 'place', '父地点尚未建立。')
        state['places'][item['id']] = item
    elif op == 'move':
        ident, dst = event.get('entity'), event.get('after')
        require(ident in state['entities'] and dst in state['places'], 'move', '站位实体或地点无效。')
        require(ident not in state.get('custody', {}) and not any(l['kind'] == 'path' and ((l['a'] == state['placements'].get(ident) and l['b'] == dst) or (not l.get('directed', False) and l['b'] == state['placements'].get(ident) and l['a'] == dst)) for l in state.get('links', {}).values()),
                'move', '持有物由携带者移动；已建路径拓扑时用 travel 显式核验。')
        _before(state['placements'], ident, event)
        require(text(event.get('route')) and text(event.get('reason')), 'move', '移动须有路径和因果说明。')
        state['placements'][ident] = dst
    elif op == 'historical_assertion':
        ident, subjects, occurred = event.get('id'), event.get('subjects'), event.get('occurred_at')
        require(text(ident) and ident not in state['historical_assertions'] and isinstance(subjects, list) and subjects
                and all(s in state['entities'] for s in subjects) and text(event.get('claim')) and text(event.get('source')), 'historical', '历史断言需要新 ID、对象、命题和来源。')
        require(isinstance(occurred, dict) and occurred.get('basis') == 'main_clock'
                and type(occurred.get('start')) is int and type(occurred.get('end')) is int
                and occurred['start'] <= occurred['end'] <= state['clock'], 'historical', '历史区间不能晚于当前主线时钟。')
        require(set(event) <= {'op', 'id', 'subjects', 'claim', 'source', 'occurred_at', 'evidence'}, 'historical', '历史断言不能混入当前状态变更。')
        state['historical_assertions'][ident] = event
    elif op == 'character_development':
        ident = event.get('entity')
        require(ident in state['entities'] and text(event.get('choice')) and text(event.get('cost')) and text(event.get('change')), 'development', '人物发展需要选择、代价和变化。')
        state['developments'].setdefault(ident, []).append(event)
    else:
        raise Error('event_op', '未知事件类型：' + str(op),
                    {'valid_ops': ['entity', 'alias', 'state', 'relation', 'knowledge', 'resource', 'clock',
                                   'hook', 'place', 'move', 'historical_assertion', 'character_development',
                                   'story_node', 'story_thread', 'reader_knowledge', 'character_current', *spatial.OPS]})


def check_deadlines(state, chapter):
    """Chapter-boundary rules shared by planned and actual state chains."""
    overdue = [k for k, h in state['hooks'].items() if h['status'] == 'open' and h['due'] <= chapter]
    require(not overdue, 'hook_due', '承诺已到期，须在正文兑现或有据延期。', {'hooks': overdue, 'recover': '补齐承诺处理的正文与事件；不得直接删承诺。'})
    sleeping = [k for k, t in state.get('thread_progress', {}).items() if t['status'] == 'dormant' and t['return_by'] <= chapter]
    require(not sleeping, 'thread_due', '暂缓线路已到返回章节，须推进或在正文有据调整返回条件。', {'threads': sleeping})


def settle(before, events, prose, chapter):
    require(isinstance(events, list), 'events', '事实结算须提供 events 数组。')
    state = copy.deepcopy(before)
    normalized = []
    for raw in events:
        require(isinstance(raw, dict), 'event', '事件须为对象。')
        event = copy.deepcopy(raw)
        if event.get('op') in ('entity', 'alias', 'place'):
            # Registration events are generated from the frozen chapter outline, not claimed by
            # the prose; anchor them to the chapter itself when the writer filed no evidence.
            ref = event.get('evidence')
            valid = isinstance(ref, dict) and type(ref.get('chapter')) is int and text(ref.get('quote'))
            if not valid:
                source = event.get('entity') or event.get('place') or event.get('alias') or {}
                name = source.get('name') if isinstance(source, dict) else None
                anchor = prose.find(name) if text(name) else -1
                if anchor >= 0:
                    event['evidence'] = {'chapter': chapter, 'quote': name, 'start': anchor}
                else:
                    event['evidence'] = {'chapter': chapter, 'quote': prose[:1], 'start': 0}
        event['evidence'] = evidence(event.get('evidence'), {chapter: prose})
        if event.get('op') == 'clock':
            require(any(t in event['evidence']['quote'] for t in TIME_MARKERS),
                    'time_evidence', '时间事件须引用正文中的时间表达。')
        if event.get('op') == 'story_node' and 'criteria' in event:
            rows = event['criteria']
            require(isinstance(rows, list) and all(isinstance(c, dict) and text(c.get('id')) and text(c.get('actual_effect')) for c in rows)
                    and len({c['id'] for c in rows}) == len(rows), 'story_criteria', '节点判据需唯一 id/actual_effect/evidence。')
            for criterion in rows:
                criterion['evidence'] = evidence(criterion.get('evidence'), {chapter: prose})
        apply_event(state, event, chapter)
        normalized.append(event)
    check_deadlines(state, chapter)
    return state, normalized


def chain(previous, row, contract_hash):
    return digest({'previous': previous, 'contract': contract_hash,
                   **{k: row[k] for k in ('n', 'prose', 'events', 'plan', 'review', 'state_hash')}})
