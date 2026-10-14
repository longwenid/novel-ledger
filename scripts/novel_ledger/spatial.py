"""Optional fixed anchors, topology and custody. Evidence is checked by facts."""
from __future__ import annotations

import copy
from .contracts import require, text

OPS = ('anchor', 'anchor_assert', 'anchor_change', 'link', 'link_change', 'placement', 'travel', 'perceive')


def seed(state, contract):
    state.update(anchors={}, links={}, custody={}, arrivals={})
    for row in contract.get('anchors', []):
        settle(state, {'op': 'anchor', **row})
    for row in contract.get('links', []):
        settle(state, {'op': 'link', **row})
    return state


def location(state, entity):
    seen = set()
    while entity in state.get('custody', {}):
        require(entity not in seen, 'custody', '持有链有环。')
        seen.add(entity)
        entity = state['custody'][entity]
    return state['placements'].get(entity)


def settle(state, event):
    op = event['op']
    require('anchors' in state, 'spatial_protocol', '该约定未启用空间能力；明确改约后使用。')
    ident = event.get('entity')
    if op.startswith('anchor'):
        require(isinstance(ident, str) and ident in state['entities'] | state['places'] and text(event.get('key')), 'anchor', '锚点需要已登记实体或地点及 key。')
        key = ident + ':' + event['key']
        old = state['anchors'].get(key)
        if op == 'anchor':
            require('value' in event and event.get('policy', 'fixed') in ('fixed', 'eventful'), 'anchor', '锚点需 value/policy。')
            item = {'value': event['value'], 'policy': event.get('policy', 'fixed')}
            require(old is None or old == item, 'anchor_fixed', '不能覆盖已成立锚点。')
            state['anchors'][key] = copy.deepcopy(item)
        elif op == 'anchor_assert':
            require(old is not None and 'value' in event and old['value'] == event['value'], 'anchor_fixed', '再次出现的稳定事实与原值冲突。')
        else:
            require(old is not None and old['policy'] == 'eventful' and event.get('before') == old['value']
                    and 'after' in event and text(event.get('reason')), 'anchor_fixed', '仅 eventful 锚点可凭原因及前值变更。')
            old['value'] = copy.deepcopy(event['after'])
    elif op == 'link':
        key = event.get('id')
        require(text(key) and key not in state['links'] and text(event.get('a')) and text(event.get('b')) and text(event.get('kind'))
                and event.get('a') in state['places'] and event.get('b') in state['places']
                and event['a'] != event['b'] and event.get('kind') in ('path', 'sight', 'sound'), 'link', '连接需唯一 id、两个地点和 path/sight/sound。')
        require(type(event.get('open', True)) is bool and type(event.get('directed', False)) is bool,
                'link', 'open/directed 须为布尔值。')
        ticks = event.get('min_days')
        require(ticks is None or event['kind'] == 'path' and type(ticks) is int and ticks >= 0, 'link', 'min_days 为非负整数，未知时省略。')
        require(isinstance(event.get('requires', {}), dict), 'link', 'requires 为事实坐标到前值的映射。')
        state['links'][key] = {k: copy.deepcopy(v) for k, v in event.items() if k not in ('op', 'evidence')}
    elif op == 'link_change':
        require(text(event.get('id')), 'link', '连接 ID 须非空字符串。')
        item = state['links'].get(event.get('id'))
        require(item is not None and event.get('before') == item.get('open', True) and type(event.get('after')) is bool
                and text(event.get('reason')), 'link', '连接变更需准确 before、布尔 after 和 reason。')
        item['open'] = event['after']
    elif op == 'placement':
        require(isinstance(ident, str) and ident in state['entities'], 'custody', '物件实体须存在。')
        old = {'holder': state['custody'][ident]} if ident in state['custody'] else ({'place': state['placements'][ident]} if ident in state['placements'] else None)
        after = event.get('after')
        require('before' in event and event['before'] == old and isinstance(after, dict) and len(after) == 1
                and (set(after) == {'holder'} or set(after) == {'place'}), 'custody', 'placement 需准确 before 和 {holder} 或 {place}。')
        if 'holder' in after:
            holder = after['holder']
            require(text(holder) and holder in state['entities'] and holder != ident and location(state, holder) is not None
                    and location(state, ident) == location(state, holder), 'custody', '交接双方须在同一已知地点；新物件先建立地点。')
            state['custody'][ident] = holder
            state['placements'].pop(ident, None)
            location(state, ident)
            state['arrivals'][ident] = max(state['arrivals'].get(ident, 0), state['arrivals'].get(holder, 0))
        else:
            require(text(after['place']) and after['place'] in state['places'] and (old is None or location(state, ident) == after['place']), 'custody', '已定位实体不能用 placement 跳过移动。')
            state['custody'].pop(ident, None)
            state['placements'][ident] = after['place']
    elif op in ('travel', 'perceive'):
        source, target = event.get('from'), event.get('to')
        require(text(source) and text(target) and source in state['places'] and target in state['places'], 'path', '起终点须存在。')
        if op == 'perceive':
            observer, observed = event.get('observer'), event.get('target')
            require(text(observer) and text(observed) and observer in state['entities'] and observed in state['entities'] and location(state, observer) == source
                    and location(state, observed) == target and event.get('channel') in ('sight', 'sound'), 'perceive', '感知需准确站位与 sight/sound；不自动更新知情。')
            route = [] if source == target else [event.get('link')]
            kind = event['channel']
        else:
            require(text(ident) and ident in state['entities'] and ident not in state['custody'] and location(state, ident) == source, 'path', '移动实体起点不匹配或由持有者携带。')
            route, kind = event.get('links'), 'path'
            require(isinstance(route, list) and route and all(text(k) for k in route), 'path', 'travel.links 明示逐段 path ID。')
        at, minimum = source, 0
        for key in route:
            require(text(key), 'path', '连接 ID 须非空字符串。')
            link = state['links'].get(key)
            require(link is not None and link['kind'] == kind and link.get('open', True)
                    and all(state['facts'].get(k) == v for k, v in link.get('requires', {}).items()), 'path', '连接类型、开放状态或条件不满足。')
            if link['a'] == at:
                at = link['b']
            else:
                require(not link.get('directed', False) and link['b'] == at, 'path', '路径不连续或方向错误。')
                at = link['a']
            minimum += link.get('min_days') or 0
        require(at == target, 'path', '路径没有到达终点。')
        if op == 'travel':
            require(('depart' in event) == ('arrive' in event), 'path_time', 'depart/arrive 同时给出或省略。')
            if 'depart' in event:
                carried = [i for i in state['custody'] if _root(state, i) == ident]
                lower = max([state['clock'], state['arrivals'].get(ident, 0)] + [state['arrivals'].get(i, 0) for i in carried])
                require(type(event['depart']) is int and type(event['arrive']) is int and event['depart'] >= lower
                        and event['arrive'] - event['depart'] >= minimum, 'path_time', '移动时间不能早于当前时钟或小于已知最短耗时。')
                for item in [ident, *carried]:
                    state['arrivals'][item] = event['arrive']
            state['placements'][ident] = target


def _root(state, entity):
    seen = set()
    while entity in state['custody']:
        require(entity not in seen, 'custody', '持有链有环。')
        seen.add(entity)
        entity = state['custody'][entity]
    return entity
