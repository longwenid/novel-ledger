"""The intra-volume state chain: node/thread/hook registries, the reducer walk over chapter
deltas, volume closure, and the event builders both design simulation and submission-time
reconciliation emit (facts.settle remains the only prose-evidence check)."""
from __future__ import annotations

import copy
from decimal import Decimal, localcontext

from .contracts import Error, text

from .drift import HOOK_ACTIONS, NODE_STATES, REVEALS, REVEAL_RANK, STANCES, THREAD_STATES, _canonical_reveal, _declared, _deltas, _enter_rows, _finding, _item, _kind_of, _number, _place_id, _project, _reduce, _resource_coordinate, _resource_parts, _safe, _same, _split_dump, _window
from . import evidence, facts, world


# ------------------------------------------------------------- simulation
def _node_registry(volume_outline):
    rows = {}
    for row in ((volume_outline or {}).get('nodes') or []):
        if isinstance(row, dict) and text(row.get('id')):
            rows[row['id']] = row
    return rows


def _thread_registry(volume_outline):
    rows = {}
    for row in ((volume_outline or {}).get('threads') or []):
        if isinstance(row, dict) and text(row.get('id')):
            rows[row['id']] = row
    return rows


def _hook_registry(volume_outline):
    """The promises one volume declares: id → {text, plant, payoff, required, continues}."""
    rows = {}
    for row in ((volume_outline or {}).get('hooks') or []):
        if isinstance(row, dict) and text(row.get('id')):
            rows[row['id']] = row
    return rows


def _apply(state, coord, chapter_no, model, nodes, hooks, findings):
    """Design-only checks surround the same event builder and reducer used by prose."""
    kind, key = coord['kind'], coord['key']
    current = _project(state, kind, key)
    declared_from = coord.get('from')
    if declared_from is not None and not _same(kind, _declared(kind, key, declared_from, state, model), current):
        findings.append(_finding(chapter_no, kind, key, declared_from, current,
                                 '增量的 from 与前序章节留下的状态不符。', 'drift_chain', 'blocker', 'volume'))
        return findings
    detail = coord.get('detail') or {}
    after = coord.get('advance') if kind == 'clock' else _declared(kind, key, coord.get('to'), state, model)
    coordinate = _resource_coordinate(state, key, detail.get('asset')) if kind == 'resources' else None
    if kind == 'resources' and (coordinate is None or after is None or after < 0):
        findings.append(_finding(chapter_no, kind, key, '已登记资源坐标与非负终值', after,
                                 '资源坐标无法解析或消耗超过账面。', 'drift_resource', 'blocker', 'volume'))
        return findings
    definition = (nodes.get(key) or {}) if kind == 'node' else (hooks.get(key) or {}) if kind == 'hook' else {}
    window = definition.get('window') if kind == 'node' else definition.get(coord.get('to')) if kind == 'hook' else None
    if _window(window) and not window[0] <= chapter_no <= window[1]:
        findings.append(_finding(chapter_no, kind, key, window, chapter_no,
                                 '安排超出卷纲声明的章节窗口。',
                                 'chapter_hook' if kind == 'hook' else 'drift_node', 'blocker', 'volume'))
        return findings
    if kind == 'node' and after == current and after != 'seeded':
        findings.append(_finding(chapter_no, kind, key, '推进', after,
                                 '同一节点重复推进。', 'drift_node', 'blocker', 'volume'))
        return findings
    planned = {'detail': detail, 'definition': definition,
               'planned': {'advance_days': after} if kind == 'clock' else {}}
    # There is no prose evidence in a design. Scratch projections never become canonical facts.
    item = {'reason': coord.get('reason') or detail.get('change') or detail.get('choice'),
            'evidence': None}
    before_findings = len(findings)
    event = _event_for(kind, key, item, planned, after, current, state, chapter_no, findings,
                       coordinate=coordinate)
    if event is not None and len(findings) == before_findings:
        _reduce(state, event, chapter_no, kind, key, findings, 'volume')
    return findings


def _closure(state, volume_outline, chapter_no, model, findings, clock_start=None):
    """The volume's declared terminals, at tolerance zero, against the simulated last chapter."""
    for row in (volume_outline or {}).get('hooks') or []:
        if not isinstance(row, dict) or not text(row.get('id')) or not row.get('required'):
            continue
        entry = _item(state.get('hooks'), row['id'])
        if entry.get('status') != 'paid':
            findings.append(_finding(chapter_no, 'hook', row['id'], 'paid', entry.get('status'),
                                     '本卷 required 的伏笔必须在卷末兑现；跨卷伏笔用 continues:true 且 required:false。',
                                     'drift_closure', 'blocker', 'volume'))
    for row in (volume_outline or {}).get('resources') or []:
        if not isinstance(row, dict) or not text(row.get('key')):
            continue
        got = _project(state, 'resources', row['key'])
        if not _same('resources', row.get('to'), got):
            findings.append(_finding(chapter_no, 'resources', row['key'], row.get('to'), got,
                                     '卷末资源终值与卷纲声明不符。', 'drift_closure', 'blocker', 'volume'))
    for row in (volume_outline or {}).get('places') or []:
        if not isinstance(row, dict) or not text(row.get('entity')):
            continue
        got = _project(state, 'places', row['entity'])
        expect = _place_id(state, model, row.get('to'))
        if not _same('places', expect, got):
            findings.append(_finding(chapter_no, 'places', row['entity'], expect, got,
                                     '卷末站位与卷纲声明不符。', 'drift_closure', 'blocker', 'volume'))
    for row in (volume_outline or {}).get('knowledge') or []:
        if not isinstance(row, dict) or not text(row.get('who')) or not text(row.get('topic')):
            continue
        key = row['who'] + ':' + row['topic']
        got = _project(state, 'knowledge', key)
        if not _same('knowledge', row.get('to'), got):
            findings.append(_finding(chapter_no, 'knowledge', key, row.get('to'), got,
                                     '卷末知情档位与卷纲声明不符。', 'drift_closure', 'blocker', 'volume'))
    for row in (volume_outline or {}).get('characters') or []:
        if not isinstance(row, dict) or not text(row.get('entity')):
            continue
        got = _project(state, 'characters', row['entity'])
        expect = row.get('to')
        # Old accepted outlines used prose here. Keep their presence check; only a structured
        # terminal is an equality the engine can honestly compute.
        if (isinstance(expect, dict) and not _same('characters', expect, got)) or got is None:
            findings.append(_finding(chapter_no, 'characters', row['entity'],
                                     expect if isinstance(expect, dict) else '卷末当前状态', got,
                                     '卷末人物当前状态与卷纲的可计算终值不符。',
                                     'drift_closure', 'blocker', 'volume'))
    clock = (volume_outline or {}).get('clock') or {}
    # `to` is an absolute terminal so a remaining-tail replan can check it too. Its absence is
    # the old persisted outline shape and must not retroactively invent a terminal for it.
    if isinstance(clock, dict) and type(clock.get('to')) is int:
        if state.get('clock') != clock['to']:
            findings.append(_finding(chapter_no, 'clock', 'main', clock['to'], state.get('clock'),
                                     '卷末主线时钟与卷纲 clock.to 不符。',
                                     'drift_closure', 'blocker', 'volume'))
        if clock_start is not None and state.get('clock', 0) - clock_start != clock.get('advance_days'):
            findings.append(_finding(chapter_no, 'clock', 'main', clock.get('advance_days'),
                                     state.get('clock', 0) - clock_start,
                                     '整卷章纲推进天数与卷纲 clock.advance_days 不符。',
                                     'drift_closure', 'blocker', 'volume'))
    return findings


def _registrations(row, state, chapter, findings):
    events = []
    for entity in row.get('new_entities') or []:
        if not isinstance(entity, dict) or not text(entity.get('id')) or entity['id'] in state.get('entities', {}):
            continue
        event = {'op': 'entity', 'entity': copy.deepcopy(entity)}
        if _reduce(state, event, chapter, 'entity', entity['id'], findings):
            events.append(event)
        if entity.get('kind') == 'place' and text(entity.get('name')):
            event = {'op': 'place', 'place': {'id': entity['id'], 'name': entity['name'],
                                              'parent': entity.get('parent')}}
            if _reduce(state, event, chapter, 'places', entity['id'], findings):
                events.append(event)
    return events


def simulate(chapters, state0, world, volume_row=None, volume_outline=None):
    """Walk the declared increments from `state0`; return `(simulated_state, findings)`.

    Every rule the design-time chain owns lives here: the enter handshake with the previous
    chapter's exit, `exit == enter + deltas`, and the guards a chapter cannot argue with (negative
    resources, a backwards clock, an unregistered place, a regressing reveal, a node advanced
    twice, a resolved thread reused). Closure against the volume's terminals runs when the walked
    range ends on the volume's last chapter.
    """
    state = copy.deepcopy(state0) if isinstance(state0, dict) else {}
    findings = []
    rows = [row for row in (chapters or []) if isinstance(row, dict)]
    nodes = _node_registry(volume_outline)
    hooks = _hook_registry(volume_outline)
    for chapter in rows:
        chapter_no = chapter.get('chapter')
        _registrations(chapter, state, chapter_no, findings)
        coords = _deltas(chapter, findings)
        declared = _enter_rows(chapter, findings)
        # The declared entry condition must be the projection the previous chapter left behind.
        for item in declared:
            if item['field'] != 'enter':
                continue
            expect = _declared(item['kind'], item['key'], item['expected'], state, world)
            got = _project(state, item['kind'], item['key'])
            if not _same(item['kind'], expect, got):
                findings.append(_finding(chapter_no, _kind_of(item['kind']), item['key'], expect, got,
                                         '本章的进入条件与模拟到本章开始的状态不符。',
                                         'drift_chain', 'blocker', 'volume'))
        # Applying the increments is what makes the next chapter's handshake checkable. The promise
        # account is tracked by its own state machine, not as an enter/exit coordinate: a chapter
        # declares which promise it opens or closes, never a before/after pair for it.
        projected = {}
        for item in declared:
            projected[(_kind_of(item['kind']), item['key'])] = item
        for coord in coords:
            if coord['kind'] in ('clock', 'hook'):
                continue
            projected.setdefault((coord['kind'], coord['key']), None)
        for coord in coords:
            _apply(state, coord, chapter_no, world, nodes, hooks, findings)
        # Rule 4.4: the declared exit is the engine's own arithmetic, compared value by value.
        declared_exit = {}
        for item in declared:
            if item['field'] != 'exit':
                continue
            kind, key = _kind_of(item['kind']), item['key']
            if (kind, key) in declared_exit:
                findings.append(_finding(chapter_no, kind, key, '唯一', 'duplicate',
                                         'exit 坐标重复。', 'drift_chain', 'blocker', 'volume'))
            declared_exit[(kind, key)] = _declared(kind, key, item['expected'], state, world)
        for kind, key in sorted(projected):
            computed = _project(state, kind, key)
            if (kind, key) not in declared_exit:
                findings.append(_finding(chapter_no, kind, key, computed, 'missing',
                                         'exit 缺少本章增量/进入条件涉及的坐标：缺项即漂移。',
                                         'drift_chain', 'blocker', 'volume'))
            elif not _same(kind, declared_exit[(kind, key)], computed):
                findings.append(_finding(chapter_no, kind, key, declared_exit[(kind, key)], computed,
                                         'exit 声明与 enter⊕本章增量算出的结果不符。',
                                         'drift_chain', 'blocker', 'volume'))
        for kind, key in sorted(declared_exit):
            if (kind, key) not in projected:
                findings.append(_finding(chapter_no, kind, key, 'enter 的坐标', declared_exit[(kind, key)],
                                         'exit 出现了 enter 与本章增量都没有的坐标。',
                                         'drift_chain', 'blocker', 'volume'))
        try:
            facts.check_deadlines(state, chapter_no)
        except Error as exc:
            findings.append(_finding(chapter_no, 'deadline', 'chapter', '到期事项已处理', exc.code,
                                     str(exc), 'drift_deadline', 'blocker', 'volume'))
    last = rows[-1].get('chapter') if rows else None
    reach = volume_row.get('end') if isinstance(volume_row, dict) else None
    if volume_outline is not None and (reach is None or last == reach):
        clock_start = ((state0 or {}).get('clock') if rows and isinstance(volume_row, dict)
                       and rows[0].get('chapter') == volume_row.get('first') else None)
        _closure(state, volume_outline, last, world, findings, clock_start)
    return state, findings


def _amount_string(value):
    """A quantity in the ledger's own spelling: an integral amount carries no decimal point.

    The comparison side is numeric either way; this is about the shape the author reads back. A
    balance seeded from `"4"` must settle to `"3"`, not `"3.0"` — the writer's self-comparison feeds
    these quantities straight into `facts.settle`, and a float-shaped ledger is a visible artefact of
    the engine's own arithmetic.
    """
    number = _number(value)
    if number is None:
        return None
    return facts.spell(Decimal(number))


def _resource_event(coordinate, before, after, reason, evidence, findings):
    """A conservation-checked flow event for one resource coordinate change."""
    holder, asset, unit = _resource_parts(coordinate, {}, {'holder': None, 'asset': None, 'unit': None})
    parts = _split_dump(coordinate)
    if parts is not None:
        holder, asset, unit = parts
    if not text(holder) or not text(asset) or not text(unit):
        findings.append(_finding(None, 'resources', coordinate, '可解析的资源坐标', None,
                                 '资源增量无法还原成 holder/asset/unit：请在增量行或自比行里显式声明。',
                                 'drift_resource', 'blocker'))
        return None
    before, after = _number(before), _number(after)
    if before is None or after is None:
        findings.append(_finding(None, 'resources', coordinate, '有限资源前值与终值', None,
                                 '资源变化需要可计算的数值。', 'drift_resource', 'blocker'))
        return None
    # Match facts.apply_event's exact arithmetic; even the smallest supported unit must settle.
    with localcontext() as ctx:
        ctx.prec = 512
        delta = after - before
    if delta == 0:
        return None
    if delta > 0:
        event = {'op': 'resource', 'from': None, 'to': holder, 'asset': asset, 'unit': unit,
                 'quantity': _amount_string(delta),
                 'to_before': _amount_string(before if before is not None else 0),
                 'reason': reason, 'evidence': evidence}
    else:
        event = {'op': 'resource', 'from': holder, 'to': None, 'asset': asset, 'unit': unit,
                 'quantity': _amount_string(delta.copy_abs() if isinstance(delta, Decimal) else -delta),
                 'from_before': _amount_string(before if before is not None else 0),
                 'reason': reason, 'evidence': evidence}
    return event


def _event_for(kind, key, item, planned, actual_to, actual_from, state, chapter, findings,
               coordinate=None):
    evidence = item.get('evidence')
    detail = planned.get('detail') or {}
    inner = planned.get('planned') if isinstance(planned.get('planned'), dict) else {}
    reason = (item.get('reason') or detail.get('reason') or detail.get('change') or '')
    if kind == 'disclosure':
        before = _project(state, kind, key)
        if actual_to not in REVEALS or (actual_to != 'retracted' and before is not None
                and REVEAL_RANK.get(_canonical_reveal(actual_to), 0) < REVEAL_RANK.get(_canonical_reveal(before), 0)):
            findings.append(_finding(chapter, kind, key, before, actual_to,
                                     '读者认知须使用披露档位，除 retracted 外不得退回较早档位。',
                                     'drift_disclosure', 'blocker'))
            return None
        return {'op': 'reader_knowledge', 'topic': key, 'before': before, 'after': actual_to,
                'claim': item.get('claim') or detail.get('claim') or (evidence or {}).get('quote'),
                'evidence': evidence}
    if kind == 'resources':
        if not text(reason):
            findings.append(_finding(chapter, kind, key, 'reason', None,
                                     '资源变化须写明原因（章纲或自比行）。', 'drift_resource', 'blocker'))
            return None
        return _resource_event(coordinate or key, actual_from, actual_to, reason, evidence, findings)
    if kind == 'places':
        route = item.get('route') or detail.get('route') or reason
        if not text(route) or not text(reason):
            findings.append(_finding(chapter, kind, key, 'route/reason', None,
                                     '站位变化须给出路径与原因。', 'drift_place', 'blocker'))
            return None
        links = item.get('links') or detail.get('links')
        if isinstance(links, list) and links:
            event = {'op': 'travel', 'entity': key, 'from': actual_from, 'to': actual_to,
                     'links': list(links), 'evidence': evidence}
            depart, arrive = item.get('depart', detail.get('depart')), item.get('arrive', detail.get('arrive'))
            if depart is not None:
                event['depart'] = depart
            if arrive is not None:
                event['arrive'] = arrive
            return event
        return {'op': 'move', 'entity': key, 'before': actual_from, 'after': actual_to,
                'route': route, 'reason': reason, 'evidence': evidence}
    if kind == 'knowledge':
        who, topic = detail.get('who'), detail.get('topic')
        if not text(who) or not text(topic):
            parts = key.split(':', 1)
            who, topic = (parts + [''])[0], (parts + [''])[1] if len(parts) > 1 else ''
        stance = STANCES.get(actual_to)
        if not text(who) or not text(topic) or stance is None:
            findings.append(_finding(chapter, kind, key, 'who:topic 与 to 档位', _safe(item.get('actual')),
                                     '知情事件需要可还原的人物与披露档位。', 'drift_knowledge', 'blocker'))
            return None
        previous = _canonical_reveal(_project(state, kind, key))
        if previous is not None and actual_to != 'retracted' \
                and REVEAL_RANK.get(_canonical_reveal(actual_to), 0) < REVEAL_RANK.get(previous, 0):
            findings.append(_finding(chapter, kind, key, previous, actual_to,
                                     '知情倒退：除 retracted 外不得从已知退回暗示。',
                                     'drift_knowledge', 'blocker'))
            return None
        claim = item.get('claim') or reason or (evidence or {}).get('quote')
        old = _item((state or {}).get('knowledge'), key)
        return {'op': 'knowledge', 'entity': who, 'topic': topic, 'claim': claim,
                'source': item.get('source') or '正文自比', 'stance': stance,
                'before': old.get('claim'), 'evidence': evidence}
    if kind == 'characters':
        after = actual_to
        if not isinstance(after, dict) or not all(text(after.get(k)) for k in ('desire', 'stance', 'relationship_focus')):
            findings.append(_finding(chapter, kind, key, 'to={desire,stance,relationship_focus}', _safe(after),
                                     '人物事件需要三项当前状态。', 'drift_character', 'blocker'))
            return None
        choice = item.get('choice') or detail.get('choice')
        cost = item.get('cost') or detail.get('cost')
        change = item.get('change') or reason or (evidence or {}).get('quote')
        if not text(choice) or not text(cost) or not text(change):
            findings.append(_finding(chapter, kind, key, 'choice/cost/change', None,
                                     '人物变化须有选择、代价与变化说明。', 'drift_character', 'blocker'))
            return None
        return {'op': 'character_current', 'entity': key, 'before': actual_from, 'after': after,
                'choice': choice, 'cost': cost, 'change': change, 'evidence': evidence}
    if kind == 'clock':
        if type(actual_to) is not int or actual_to < 0:
            findings.append(_finding(chapter, kind, key, '非负整数天数', _safe(item.get('actual')),
                                     '时钟自比须给出推进天数。', 'drift_clock', 'blocker'))
            return None
        planned_days = inner.get('advance_days')
        if actual_to != planned_days:
            findings.append(_finding(chapter, kind, key, planned_days, actual_to,
                                     '本章时间推进与章纲声明不一致：正文的时间跨度是章纲契约的一部分。',
                                     'drift_clock', 'blocker'))
            return None
        after = (state or {}).get('clock', 0) + actual_to
        if actual_to == 0:
            return None
        return {'op': 'clock', 'before': (state or {}).get('clock', 0), 'after': after, 'evidence': evidence}
    if kind == 'node':
        definition = (planned.get('definition') or {})
        outcome = item.get('outcome') or detail.get('outcome') or reason or (evidence or {}).get('quote')
        if actual_to not in NODE_STATES or not text(outcome):
            findings.append(_finding(chapter, kind, key, 'after/outcome', _safe(item.get('actual')),
                                     '节点自比须给出 after 与实现说明。', 'drift_node', 'blocker'))
            return None
        event = {'op': 'story_node', 'node': key, 'before': _project(state, 'node', key),
                 'after': actual_to, 'outcome': outcome,
                 'line': definition.get('line') or key.split(':')[0], 'depends_on': list(definition.get('depends_on') or []),
                 'evidence': evidence}
        if item.get('criteria'):
            event['criteria'] = copy.deepcopy(item['criteria'])
        return event
    if kind == 'thread':
        reason_text = reason or detail.get('reason')
        if actual_to not in THREAD_STATES or not text(reason_text):
            findings.append(_finding(chapter, kind, key, 'after/reason', _safe(item.get('actual')),
                                     '线路自比须给出 after 与原因。', 'drift_thread', 'blocker'))
            return None
        event = {'op': 'story_thread', 'thread': key, 'before': _project(state, 'thread', key),
                 'after': actual_to, 'reason': reason_text, 'evidence': evidence}
        due = item.get('return_by', detail.get('return_by'))
        if type(due) is int:
            event['return_by'] = due
        return event
    if kind == 'hook':
        # The writer files the action it took; the engine owns everything else about the promise:
        # the text the volume declared and the deadline its payoff window sets.
        declaration = planned.get('definition') or {}
        entry = _item((state or {}).get('hooks'), key)
        note = detail.get('note') or reason
        if actual_to == 'plant':
            text_value = declaration.get('text') or item.get('text')
            window = declaration.get('payoff')
            due = window[1] if _window(window) else (item.get('due') if type(item.get('due')) is int else None)
            if not text(text_value) or type(due) is not int:
                findings.append(_finding(chapter, kind, key, 'text 与 due（由卷纲声明）', _safe(declaration),
                                         '埋设承诺需要卷纲声明的 text 与 payoff 窗口：引擎据此写入 due。',
                                         'drift_hook', 'blocker'))
                return None
            return {'op': 'hook', 'id': key, 'status': 'open', 'due': due, 'text': text_value,
                    'before': entry.get('status'), 'reason': note, 'evidence': evidence}
        if actual_to == 'payoff':
            if entry.get('status') != 'open':
                findings.append(_finding(chapter, kind, key, 'open', entry.get('status'),
                                         '只有已埋设且未兑现的承诺才能 payoff；引擎按投影的真实状态判定。',
                                         'drift_hook', 'blocker'))
                return None
            return {'op': 'hook', 'id': key, 'status': 'paid', 'before': entry.get('status'),
                    'reason': note or '正文兑现该承诺。', 'evidence': evidence}
        findings.append(_finding(chapter, kind, key, '|'.join(HOOK_ACTIONS), _safe(actual_to),
                                 '伏笔自比的动作只有 plant 与 payoff。', 'drift_hook', 'blocker'))
        return None
    return None
