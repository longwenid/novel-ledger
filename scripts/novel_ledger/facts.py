"""Evidence-backed reducers. Accept values, return a new state; no side effects."""
from __future__ import annotations

import copy
from decimal import Decimal, InvalidOperation, localcontext
from .contracts import Error, TIME_MARKERS, digest, dump, require, text


def amount(value):
    require(isinstance(value, str), 'amount', '资源数量使用十进制字符串。')
    try:
        number = Decimal(value)
    except InvalidOperation:
        raise Error('amount', '数量不是有效十进制数。')
    require(number.is_finite() and number >= 0 and len(number.as_tuple().digits) <= 120
            and abs(number.as_tuple().exponent) <= 120, 'amount', '数量须非负、有限且在精度范围内。')
    return number


def resource_key(holder, asset, unit):
    return dump([holder, asset, unit])


def entity(state, item):
    require(isinstance(item, dict) and all(text(item.get(k)) for k in ('id', 'name', 'kind')), 'entity', '实体需要 id/name/kind。')
    ident = item['id']
    require(not any(c in ident for c in ':>') and ident not in state['entities'], 'entity', '实体 ID 重复或含分隔符。')
    aliases = item.get('aliases', [])
    require(isinstance(aliases, list) and all(text(a) for a in aliases), 'alias', '别名须为非空字符串数组。')
    names = [item['name']] + aliases
    used = {s for e in state['entities'].values() for s in [e['name']] + e.get('aliases', [])}
    require(len(set(names)) == len(names) and not used.intersection(names), 'alias_conflict', '称呼重复或属于另一实体。')
    state['entities'][ident] = copy.deepcopy(item)


def seed(contract):
    state = {k: {} for k in ('entities', 'facts', 'knowledge', 'resources', 'relations', 'hooks', 'clock_threads', 'places', 'placements', 'historical_assertions', 'developments')}
    state['clock'] = 0
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
        state['resources'][key] = str(amount(item.get('quantity')))
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
    return state


def evidence(ref, sources):
    require(isinstance(ref, dict) and type(ref.get('chapter')) is int and text(ref.get('quote')), 'evidence', '证据需要 chapter/quote。')
    chapter = ref['chapter']
    require(chapter in sources, 'evidence_scope', '引文不在冻结正文范围内。')
    prose, quote = sources[chapter], ref['quote']
    start = ref.get('start')
    if start is None:
        start = prose.find(quote)
        require(start >= 0 and prose.find(quote, start + 1) < 0, 'evidence', '引文缺失或多次出现，请提供准确 start。')
    require(type(start) is int and start >= 0 and prose[start:start + len(quote)] == quote,
            'evidence', '引文与冻结正文不一致。')
    return {'chapter': chapter, 'start': start, 'quote': quote}


def _before(container, key, event):
    require('before' in event and 'after' in event and container.get(key) == event['before'],
            'precondition', '事实前值不匹配。', {'key': key, 'current': container.get(key), 'recover': '照抄 current 为 before；新值放 after。'})


def settle(before, events, prose, chapter):
    require(isinstance(events, list), 'events', '独立事实审稿须提供 events 数组。')
    state = copy.deepcopy(before)
    normalized = []
    for raw in events:
        require(isinstance(raw, dict), 'event', '事件须为对象。')
        event = copy.deepcopy(raw)
        event['evidence'] = evidence(event.get('evidence'), {chapter: prose})
        op = event.get('op')
        if op == 'entity':
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
            require('before' in event and event['before'] == (old['claim'] if old else None), 'precondition', '认知前值不匹配。')
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
                state['resources'][key] = str(amount(str(new)))
        elif op == 'clock':
            thread = event.get('thread')
            require(thread is None or text(thread), 'clock', '支线时间 ID 须非空。')
            current = state['clock_threads'].get(thread, state['clock']) if thread else state['clock']
            require(type(event.get('before')) is int and type(event.get('after')) is int
                    and event['before'] == current and event['after'] >= current, 'time_conflict', '时间前值不匹配或发生倒退。')
            require(any(t in event['evidence']['quote'] for t in TIME_MARKERS), 'time_evidence', '时间事件须引用正文中的时间表达。')
            if thread:
                state['clock_threads'][thread] = event['after']
            else:
                state['clock'] = event['after']
        elif op == 'hook':
            ident, status = event.get('id'), event.get('status')
            require(text(ident) and status in ('open', 'paid', 'closed'), 'hook', '承诺 ID 或状态无效。')
            old = state['hooks'].get(ident)
            require('before' in event and event['before'] == (old['status'] if old else None), 'precondition', '承诺前态不匹配。')
            require((old is None and status == 'open') or (old is not None and old['status'] == 'open'), 'hook', '承诺未埋设或已关闭。')
            due = event.get('due', old.get('due') if old else None)
            require(type(due) is int and due >= chapter, 'hook_due', '承诺期限须为当前或后续章节。')
            item = copy.deepcopy(old) if old else {'text': event.get('text'), 'seed': event['evidence'], 'extensions': 0}
            require(text(item.get('text')), 'hook', '新承诺需要内容。')
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
            raise Error('event_op', '未知事件类型：' + str(op))
        normalized.append(event)
    overdue = [k for k, h in state['hooks'].items() if h['status'] == 'open' and h['due'] <= chapter]
    require(not overdue, 'hook_due', '承诺已到期，须在正文兑现或有据延期。', {'hooks': overdue, 'recover': '补齐承诺处理的正文与事件；不得直接删承诺。'})
    return state, normalized


def chain(previous, row, contract_hash):
    return digest({'previous': previous, 'contract': contract_hash,
                   **{k: row[k] for k in ('n', 'prose', 'events', 'plan', 'review', 'state_hash')}})
