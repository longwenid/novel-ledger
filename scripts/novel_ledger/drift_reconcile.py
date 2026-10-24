"""Submission-time reconciliation of the writer's drift_check against the projected state,
and state_mismatch for comparing a submitted chapter row with the engine projection."""
from __future__ import annotations

import copy

from .contracts import require, text

from .drift import HOOK_ACTIONS, ITEM_KINDS, ITEM_STATUSES, NODE_STATES, REVEALS, THREAD_STATES, VERDICTS, _declared, _deltas, _finding, _item, _kind_of, _number, _place_registry, _project, _reduce, _resource_coordinate, _safe, _same, _split_dump
from .drift_simulation import _event_for, _registrations
from . import evidence, world


# ---------------------------------------------------------- reconciliation
def _planned(row):
    """The chapter's planned increments as coverage coordinates, in the order the form lists them."""
    planned = []
    plot = row.get('plot') if isinstance(row.get('plot'), dict) else {}
    for node in plot.get('nodes') or []:
        if isinstance(node, dict) and text(node.get('node')):
            definition = (row.get('node_contracts') or {}).get(node['node']) or node
            planned.append({'kind': 'node', 'key': node['node'],
                            'planned': {'after': node.get('after')},
                            'detail': {'outcome': node.get('outcome')},
                            'definition': definition})
    for thread in plot.get('threads') or []:
        if isinstance(thread, dict) and text(thread.get('thread')):
            planned.append({'kind': 'thread', 'key': thread['thread'],
                            'planned': {'after': thread.get('after')},
                            'detail': {'reason': thread.get('reason'), 'return_by': thread.get('return_by')}})
    # The promise actions sit beside the node/thread actions: one comparison row per declared step,
    # in the order the chapter declares them (a same-chapter plant then payoff stays in that order,
    # which is also the order the events must settle in).
    for entry in row.get('hooks') or []:
        if isinstance(entry, dict) and text(entry.get('hook')):
            planned.append({'kind': 'hook', 'key': entry['hook'],
                            'planned': {'action': entry.get('action')},
                            'detail': {'note': entry.get('note')},
                            'definition': (row.get('hook_contracts') or {}).get(entry['hook']) or {}})
    for entry in row.get('resources') or []:
        if isinstance(entry, dict) and text(entry.get('key')):
            planned.append({'kind': 'resources', 'key': entry['key'],
                            'planned': {'from': entry.get('from'), 'to': entry.get('to')},
                            'detail': {'holder': entry.get('holder'), 'asset': entry.get('asset'),
                                       'unit': entry.get('unit'), 'reason': entry.get('reason')}})
    for entry in row.get('places') or []:
        if isinstance(entry, dict) and text(entry.get('entity')):
            planned.append({'kind': 'places', 'key': entry['entity'],
                            'planned': {'from': entry.get('from'), 'to': entry.get('to')},
                            'detail': {'route': entry.get('route'), 'links': entry.get('links'),
                                       'depart': entry.get('depart'), 'arrive': entry.get('arrive'),
                                       'reason': entry.get('reason')}})
    for entry in row.get('knowledge') or []:
        if isinstance(entry, dict) and text(entry.get('who')) and text(entry.get('topic')):
            planned.append({'kind': 'knowledge', 'key': entry['who'] + ':' + entry['topic'],
                            'planned': {'from': entry.get('from'), 'to': entry.get('to')},
                            'detail': {'who': entry['who'], 'topic': entry['topic'],
                                       'reason': entry.get('reason')}})
    for entry in row.get('characters') or []:
        if isinstance(entry, dict) and text(entry.get('entity')):
            planned.append({'kind': 'characters', 'key': entry['entity'],
                            'planned': {'from': entry.get('from'), 'to': entry.get('to')},
                            'detail': {'choice': entry.get('choice'), 'cost': entry.get('cost'),
                                       'change': entry.get('change'), 'reason': entry.get('reason')}})
    clock = row.get('clock') if isinstance(row.get('clock'), dict) else {}
    planned.append({'kind': 'clock', 'key': 'clock',
                    'planned': {'advance_days': clock.get('advance_days') or 0}, 'detail': {}})
    for entry in row.get('disclosures') or []:
        if isinstance(entry, dict) and text(entry.get('topic')):
            planned.append({'kind': 'disclosure', 'key': entry['topic'],
                            'planned': {'after': entry.get('after')},
                            'detail': {'claim': entry.get('claim')}})
    return planned


def _evidence_of(item, chapter, findings):
    ref = item.get('evidence')
    if not isinstance(ref, dict) or type(ref.get('chapter')) is not int or ref['chapter'] != chapter \
            or not text(ref.get('quote')):
        findings.append(_finding(chapter, _kind_of(item.get('kind')), item.get('key'),
                                 '{chapter:%d,quote:正文原文片段}' % chapter, _safe(ref),
                                 '每条自比都要附正文原文引文；引文由引擎按冻结正文校验。',
                                 'drift_evidence', 'blocker'))
        return None
    return {'chapter': ref['chapter'], 'quote': ref['quote'],
            **({'start': ref['start']} if type(ref.get('start')) is int else {})}


def _actual_of(kind, item, projected):
    """(from, to) the writer filed, with `from` optional because the engine projects it."""
    actual = item.get('actual')
    if kind == 'hook':
        return None, actual.get('action') if isinstance(actual, dict) else actual
    if kind in ('node', 'thread', 'disclosure'):
        states = NODE_STATES if kind == 'node' else THREAD_STATES if kind == 'thread' else REVEALS
        if isinstance(actual, dict) and actual.get('after') in states:
            return None, actual.get('after')
        if actual in states:
            return None, actual
        return None, None
    if kind == 'clock':
        if isinstance(actual, dict) and type(actual.get('advance_days')) is int:
            return None, actual['advance_days']
        if isinstance(actual, dict) and _number(actual.get('from')) is not None and _number(actual.get('to')) is not None:
            return _number(actual['from']), _number(actual['to'])
        if _number(actual) is not None:
            return None, _number(actual)
        return None, None
    if not isinstance(actual, dict):
        return None, None
    return (actual.get('from') if 'from' in actual else None), actual.get('to')


def _coverage_key(kind, key, planned):
    """The identity of one comparison row.

    A promise's plant and its payoff are two steps of the same coordinate — a one-chapter volume
    legally opens and closes the same promise — so a hook row is identified by its action as well.
    The clock keeps its single `clock/main` coordinate under whichever spelling came in.
    """
    if kind == 'clock':
        return ('clock', 'clock')
    action = planned.get('action') if isinstance(planned, dict) else None
    return (kind, key, action) if kind == 'hook' else (kind, key)


def reconcile(drift_check, row, state, world):
    """Reconcile a writer's `drift_check` against the chapter outline and the projected state.

    Returns `{'events', 'findings', 'deviations'}`. `events` is exactly what `facts.settle` has
    always accepted — one item per planned increment, in a fixed order, with every `before` field
    projectively rebuilt here so the writer never self-reports a before-value. `findings` blocks the
    submission (coverage, an actual `from` that is not the projection, a `kept` row whose result
    moved, missing evidence). Declared departures remain diagnostic candidates and always produce
    findings: a frozen outline cannot be changed by accepting a different prose outcome.
    """
    findings, deviations, events = [], [], []
    require(isinstance(row, dict) and type(row.get('chapter')) is int, 'drift_check',
            '漂移核算需要本章已登记的章纲行。')
    chapter = row['chapter']
    require(isinstance(drift_check, dict), 'drift_check', '执笔须提交 drift_check.items/unplanned/verdict。')
    items = drift_check.get('items')
    require(isinstance(items, list), 'drift_check', 'drift_check.items 须为数组。')
    unplanned = drift_check.get('unplanned') or []
    require(isinstance(unplanned, list) and all(isinstance(entry, dict) for entry in unplanned),
            'drift_check', 'drift_check.unplanned 须为对象数组。')
    planned = _planned(row)
    # 1. Coverage: one item per planned increment, no more and no fewer. A promise's plant and its
    # payoff are two separate steps of the same coordinate, so a hook row's identity is
    # (kind, key, action) — a one-chapter volume legally plants and pays off the same promise.
    expected, seen_items = {}, {}
    for entry in planned:
        expected[_coverage_key(entry['kind'], entry['key'], entry.get('planned'))] = entry
    for item in items:
        if not isinstance(item, dict):
            findings.append(_finding(chapter, 'item', None, 'object', _safe(item),
                                     'drift_check.items 的每一项都须为对象。', 'drift_coverage', 'blocker'))
            continue
        kind = _kind_of(item.get('kind'))
        key = item.get('key')
        if kind not in ('node', 'thread', 'hook', 'resources', 'places', 'knowledge', 'characters', 'clock', 'disclosure'):
            findings.append(_finding(chapter, 'item', key, '|'.join(ITEM_KINDS), kind,
                                     '未知的自比种类。', 'drift_coverage', 'blocker'))
            continue
        filed = item.get('planned') if isinstance(item.get('planned'), dict) else {}
        if kind == 'hook' and filed.get('action') not in HOOK_ACTIONS:
            findings.append(_finding(chapter, kind, key, 'planned.action∈plant|payoff', _safe(filed),
                                     'hook 自比行的 planned.action 必须写明是埋设还是兑现，'
                                     '同一承诺的两步是两行。', 'drift_coverage', 'blocker'))
            continue
        coordinate = _coverage_key(kind, key, filed)
        if coordinate in seen_items:
            findings.append(_finding(chapter, kind, key, '每步一行', 'duplicate',
                                     '同一步骤出现了两行自比。', 'drift_coverage', 'blocker'))
            continue
        seen_items[coordinate] = item
    for coordinate, entry in expected.items():
        if coordinate not in seen_items:
            findings.append(_finding(chapter, entry['kind'], entry['key'], '自比一行',
                                     'missing', '漏项：章纲声明的计划增量没有对应的自比行。',
                                     'drift_coverage', 'blocker'))
    for coordinate in seen_items:
        if coordinate not in expected:
            findings.append(_finding(chapter, coordinate[0], coordinate[1], '章纲未声明', 'extra',
                                     '多项：自比行没有对应的章纲增量，须返修本章正文。',
                                     'drift_coverage', 'blocker'))
    # 2. Per-item reconciliation against the projected state.
    shadow = copy.deepcopy(state) if isinstance(state, dict) else {}
    registrations = _registrations(row, shadow, chapter, findings)
    ordered = [entry for entry in planned
               if _coverage_key(entry['kind'], entry['key'], entry.get('planned')) in seen_items]
    for entry in ordered:
        item = seen_items[_coverage_key(entry['kind'], entry['key'], entry.get('planned'))]
        kind, key = entry['kind'], entry['key']
        evidence = _evidence_of(item, chapter, findings)
        status = item.get('status')
        if status not in ITEM_STATUSES:
            findings.append(_finding(chapter, kind, key, '|'.join(ITEM_STATUSES), status,
                                     '每行自比须声明 kept/deviated/skipped。', 'drift_status', 'blocker'))
            continue
        if evidence is None:
            continue
        item = {**item, 'evidence': evidence}
        projected = _project(shadow, kind, key)
        coordinate = _resource_coordinate(shadow, key, entry['detail'].get('asset')) if kind == 'resources' else None
        actual_from, actual_to = _actual_of(kind, item, projected)
        if kind == 'resources' and actual_from is None and isinstance(item.get('actual'), dict) \
                and 'from' not in item['actual']:
            actual_from = _number(entry['planned'].get('from'))
        if kind == 'clock':
            actual_from, actual_to = projected, actual_to
        if actual_from is not None and not _same(kind, _declared(kind, key, actual_from, shadow, world), projected):
            findings.append(_finding(chapter, kind, key,
                                     _declared(kind, key, actual_from, shadow, world), projected,
                                     '自报前态与引擎投影的真实值不符：前态由引擎给出，不由执笔申报。',
                                     'drift_before', 'blocker'))
            continue
        if actual_to is None and status != 'skipped':
            findings.append(_finding(chapter, kind, key, '实际结果', _safe(item.get('actual')),
                                     '自比行缺少实际结果（跳过的行请标 skipped）。', 'drift_actual', 'blocker'))
            continue
        # A kept row's result must be the one the outline declared; the planned side speaks a
        # different key per kind (a node/thread declares `after`, the clock `advance_days`).
        expected_kept = (entry['planned'].get('advance_days') if kind == 'clock'
                         else entry['planned'].get('action') if kind == 'hook'
                         else entry['planned'].get('after') if kind in ('node', 'thread', 'disclosure')
                         else entry['planned'].get('to'))
        # Normalize place names to registered IDs so the kept comparison and the move
        # event speak the same key the outline's entity registry uses (the unplanned
        # path already does this at line 298).
        if kind == 'places' and actual_to is not None:
            actual_to = _declared(kind, key, actual_to, shadow, world) or actual_to
        if status == 'kept' and not _same(kind, actual_to, expected_kept):
            findings.append(_finding(chapter, kind, key, expected_kept, actual_to,
                                     '实际结果必须与已固定章纲一致；须返修正文，改为 deviated 不能豁免。',
                                     'drift_kept', 'blocker'))
            continue
        if status == 'skipped' and not _same(kind, actual_to if actual_to is not None else projected, projected):
            findings.append(_finding(chapter, kind, key, projected, actual_to,
                                     'status=skipped 表示本章没有发生该变化，实际结果必须等于前态。',
                                     'drift_skipped', 'blocker'))
            continue
        if status in ('deviated', 'skipped'):
            if not text(item.get('reason')):
                findings.append(_finding(chapter, kind, key, 'reason', None,
                                         '标为 deviated/skipped 的行必须写明理由。', 'drift_reason', 'blocker'))
                continue
            deviations.append({'chapter': chapter, 'kind': kind, 'key': key,
                               'planned': _safe(entry['planned']), 'actual': _safe(item.get('actual')),
                               'reason': item['reason']})
        if status == 'skipped':
            continue
        event = _event_for(kind, key, item, entry, actual_to, projected if kind != 'resources' else actual_from,
                           shadow, chapter, findings,
                           coordinate=coordinate)
        if event is not None:
            events.append(event)
            _reduce(shadow, event, chapter, kind, key, findings)
    # 3. Unplanned factual deltas use the same event builders and reducers as planned deltas.
    # A prose note alone cannot establish a state; refusing it is safer than accepting a receipt
    # whose body and canonical state silently disagree. Narrative actions remain plan-bound.
    for entry in unplanned:
        kind = _kind_of(entry.get('kind'))
        key = entry.get('key')
        if kind not in ('resources', 'places', 'knowledge', 'characters') or not text(key):
            findings.append(_finding(chapter, kind, key,
                                     'resources|places|knowledge|characters 与非空 key', _safe(entry),
                                     '该计划外状态种类未开放结算；情节、伏笔、披露与时钟须先按章纲契约处理。',
                                     'drift_unplanned', 'blocker'))
            continue
        if not text(entry.get('reason')):
            findings.append(_finding(chapter, kind, key, 'reason', None,
                                     '计划外变化须写明原因，否则无法入账。', 'drift_unplanned', 'blocker'))
            continue
        actual = entry.get('actual')
        if not isinstance(actual, dict) or not {'from', 'to'} <= set(actual) or actual['to'] is None:
            findings.append(_finding(chapter, kind, key, 'actual={from,to}', _safe(actual),
                                     '计划外变化须给出可结算的 actual.from/to，不能只填 change 说明。',
                                     'drift_unplanned', 'blocker'))
            continue
        if kind == 'knowledge' and (not isinstance(actual['to'], str) or actual['to'] not in REVEALS
                                     or actual['from'] is not None and
                                     (not isinstance(actual['from'], str) or actual['from'] not in REVEALS)):
            findings.append(_finding(chapter, kind, key, 'from:null|知情档位,to:知情档位', _safe(actual),
                                     '计划外知情值必须使用已声明的披露档位。', 'drift_unplanned', 'blocker'))
            continue
        if kind == 'places' and (not text(actual['to']) or actual['from'] is not None and not text(actual['from'])):
            findings.append(_finding(chapter, kind, key, 'from:null|地点文本,to:地点文本', _safe(actual),
                                     '计划外位置值必须是可解析的地点文本。', 'drift_unplanned', 'blocker'))
            continue
        evidence = _evidence_of(entry, chapter, findings)
        if evidence is None:
            continue
        coordinate = _resource_coordinate(shadow, key) if kind == 'resources' else None
        projected = _project(shadow, kind, key)
        if kind == 'resources' and projected is None and _split_dump(key) is not None:
            coordinate, projected = key, 0
        declared_from = _declared(kind, key, actual['from'], shadow, world)
        if not _same(kind, declared_from, projected):
            findings.append(_finding(chapter, kind, key, projected, declared_from,
                                     '计划外变化的自报前态与引擎投影不符。', 'drift_before', 'blocker'))
            continue
        after = _declared(kind, key, actual['to'], shadow, world)
        if kind == 'resources' and (after is None or after < 0):
            findings.append(_finding(chapter, kind, key, '非负有限资源数值', _safe(actual['to']),
                                     '计划外资源终值必须是非负有限数值。', 'drift_resource', 'blocker'))
            continue
        if kind == 'places' and after not in _place_registry(shadow, world):
            findings.append(_finding(chapter, kind, key, '已登记地点', _safe(after),
                                     '计划外位置变化指向未登记地点。', 'drift_place', 'blocker'))
            continue
        item = {**entry, 'evidence': evidence, 'status': 'deviated'}
        before_findings = len(findings)
        event = _event_for(kind, key, item, {'detail': {}}, after, projected,
                           shadow, chapter, findings, coordinate=coordinate)
        if len(findings) != before_findings:
            continue
        if event is not None:
            events.append(event)
            _reduce(shadow, event, chapter, kind, key, findings)
        deviations.append({'chapter': chapter, 'kind': kind, 'key': key,
                           'planned': _safe(entry.get('planned')), 'actual': _safe(actual),
                           'reason': entry['reason']})
    # 4. The verdict is a claim the engine can contradict.
    verdict = drift_check.get('verdict')
    if verdict not in VERDICTS:
        findings.append(_finding(chapter, 'verdict', 'verdict', '|'.join(VERDICTS), verdict,
                                 'drift_check.verdict 须为 clean 或 deviated。', 'drift_verdict', 'quality'))
    elif verdict == 'clean' and deviations:
        findings.append(_finding(chapter, 'verdict', 'verdict', 'clean', 'deviated',
                                 '有偏差却声明 clean：须返修正文使其符合章纲，并按最终稿重新自比。',
                                 'drift_verdict', 'quality'))
    elif verdict == 'deviated' and not deviations:
        findings.append(_finding(chapter, 'verdict', 'verdict', 'deviated', 'clean',
                                 '声明 deviated 却没有一条偏差：逐条标出 deviated/skipped 并写理由。',
                                 'drift_verdict', 'quality'))
    # 5. A declared departure diagnoses a failed draft; it never authorizes a new contract.
    # Keep its proposed events as a scratch preview for diagnostics only. Workflow must repair the
    # current prose, and audit uses this same reconciliation before accepting committed history.
    for deviation in deviations:
        findings.append(_finding(chapter, deviation['kind'], deviation['key'],
                                 deviation['planned'], deviation['actual'],
                                 '正文偏离已固定章纲，须返修本章正文；说明理由不能豁免，也不能自动重排章纲。',
                                 'outline_alignment', 'blocker'))
    return {'events': registrations + events, 'findings': findings, 'deviations': deviations}


def state_mismatch(state, row):
    """Whether a chapter's declared entry conditions still describe the state the book is in.

    Empty means the chapter can be written against this row. A row cannot be fixed by rewriting
    prose, so the caller re-plans the remaining chapter outlines from the state that moved.
    """
    findings = []
    if not isinstance(row, dict):
        return findings
    chapter = row.get('chapter')
    model = None
    for item in row.get('enter') or []:
        if not isinstance(item, dict) or 'expected' not in item:
            continue
        kind, key = _kind_of(item.get('kind')), item.get('key')
        got = _project(state, kind, key)
        expect = _declared(kind, key, item.get('expected'), state, model)
        if not _same(kind, expect, got):
            findings.append(_finding(chapter, kind, key, expect, got,
                                     '本章纲声明的进入条件与引擎投影的真实状态不符。',
                                     'drift_chain', 'blocker', 'volume'))
    for coord in _deltas(row, []):
        if coord['kind'] == 'hook':
            continue                      # promised steps are judged below, in declaration order
        if coord['kind'] == 'clock' or coord['from'] is None:
            continue
        kind, key = coord['kind'], coord['key']
        got = _project(state, kind, key)
        expect = _declared(kind, key, coord['from'], state, model)
        if not _same(kind, expect, got):
            findings.append(_finding(chapter, kind, key, expect, got,
                                     '本章增量声明的前态与引擎投影的真实状态不符。',
                                     'drift_chain', 'blocker', 'volume'))
    # The promise account, walked in the order the chapter declares it: a same-chapter plant then
    # payoff is legal, so each step is judged against the status the previous step left behind —
    # never against the pre-chapter state, which would make every short-hook chapter look like drift.
    statuses = {ident: _item((state or {}).get('hooks'), ident).get('status')
                for ident in ((state or {}).get('hooks') or {})}
    for coord in _deltas(row, []):
        if coord['kind'] != 'hook':
            continue
        hook_id, action = coord['key'], coord['to']
        current = statuses.get(hook_id)
        expect = None if action == 'plant' else 'open'
        if current != expect:
            findings.append(_finding(chapter, 'hook', hook_id, expect, current,
                                     '本章纲的伏笔动作与引擎投影的真实承诺状态不符。',
                                     'drift_chain', 'blocker', 'volume'))
        statuses[hook_id] = 'open' if action == 'plant' else 'paid'
    return findings


def presence_notes(plan, model, prose):
    """Mechanical presence proxy for semantic fulfillment: a character the chapter plan
    declares on stage should surface in the prose under its own world-model name.

    A miss is an observation (severity 'note'), never a repair charge or a refusal: pronouns,
    aliases and deliberate withholding are legitimate prose, so this records what a reader
    could check in one pass and judges nothing. Ids the world model does not carry as a named
    record are skipped silently — the observation exists only where plan and model agree.
    """
    plan = plan if isinstance(plan, dict) else {}
    names = {}
    if isinstance(model, dict):
        for section in world.SECTIONS:
            for row in model.get(section) or []:
                if isinstance(row, dict) and text(row.get('id')) and text(row.get('name')):
                    names[row['id']] = row['name']
    notes = []
    for entry in plan.get('characters') or []:
        if not isinstance(entry, dict) or not text(entry.get('entity')):
            continue
        entity = entry['entity']
        name = names.get(entity)
        if name and name not in prose:
            notes.append({'criterion': 'presence', 'severity': 'note', 'kind': 'characters',
                          'entity': entity, 'name': name,
                          'reason': '章纲声明出场，正文未见其世界模型名称；代词或别名属正常，仅供观察。'})
    return notes
