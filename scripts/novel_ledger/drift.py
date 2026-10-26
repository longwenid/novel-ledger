"""Shared drift vocabulary: outline field tables, world/projection helpers, chapter deltas
and the state reducer design simulation and prose reconciliation both walk. plan_rows freezes
a chapter outline into the item list a write receipt must answer."""
from __future__ import annotations

import copy
from decimal import Decimal, InvalidOperation

from .contracts import Error
from .contracts import require
from .contracts import text

from . import facts, narrative, spatial, world


# --------------------------------------------------------------- declarations
# `relations`/`reader_knowledge` are the optional pair: a volume that declares no relation
# terminal or no reader-knowledge terminal is checked for neither (declared-then-checked), and a
# chapter that omits `relations` declares "no relation change this chapter" — the same reading an
# absent increment array already has.
VOLUME_FIELDS = ('id', 'purpose', 'stage', 'arc', 'turns', 'climax', 'nodes', 'threads', 'hooks',
                 'resources', 'places', 'knowledge', 'characters', 'relations', 'reader_knowledge',
                 'clock', 'exit_state', 'style')


CHAPTER_FIELDS = ('chapter', 'synopsis', 'plot', 'resources', 'places', 'knowledge', 'characters',
                  'relations', 'clock', 'enter', 'exit', 'disclosures', 'world_refs', 'new_entities',
                  'hook_refs', 'hooks', 'reader_refs', 'history_refs', 'scenes', 'pacing', 'style',
                  'story_events', 'reader_effect', 'timeline')


# The five increment arrays plus the clock: what a chapter declares it changes. `relations` is the
# fifth array — its coordinate is `source>target:key`, the exact key `facts.apply_event` stores in
# `state.relations`, so design simulation, reconciliation and settlement share one identity.
DELTA_KINDS = ('resources', 'places', 'knowledge', 'characters', 'relations', 'clock')


# The promise account: a volume declares the promises it opens and closes, a chapter acts on them.
# There are exactly two actions — mid-course reminders are the existing `hook_refs` hand-off.
HOOK_ACTIONS = ('plant', 'payoff')


# The status an action leaves in the projection; the outline speaks in actions, the state in statuses.
HOOK_STATUS = {'plant': 'open', 'payoff': 'paid'}


HOOK_FIELDS = ('id', 'text', 'plant', 'payoff', 'required', 'continues')


# Optional workbench protocols a chapter outline may carry: the scene identity and reading
# dependency declarations the writer makes, and the schemas `story_memory.bind` freezes back onto
# the row. They are not part of the drift contract, but dropping them would silently disable the
# scene chain and turn every reading revision conservative.
PROTOCOL_FIELDS = ('scene_schema', 'reading_schema', 'reading_coverage', 'dependency_coverage',
                   'reading_refs', 'understanding_refs')


# What an `enter`/`exit` row may name. A delta array is plural (`characters`), a coordinate is the
# projection field it reads (`character`), so both spellings are accepted and normalized.
ENTER_KINDS = ('resources', 'places', 'knowledge', 'character', 'characters', 'relations',
               'clock', 'node', 'thread')


ITEM_KINDS = ('node', 'thread', 'hook', 'resources', 'places', 'knowledge', 'characters',
              'relations', 'clock', 'disclosure', 'reader_knowledge', 'reader')


ITEM_STATUSES = ('kept', 'deviated', 'skipped')


VERDICTS = ('clean', 'deviated')


NODE_STATES = narrative.STATUSES


THREAD_STATES = ('active', 'dormant', 'resolved')


REVEALS = narrative.REVEALS


STANCES = narrative.STANCES


STANCE_REVEALS = narrative.STANCE_REVEALS


# The two vocabularies are not one-to-one: `hinted` and `suspected` are the same stance, and
# `misled`/`confirmed`/`retracted` each have exactly one. Comparing a declared stage with a settled
# projection therefore compares canonical forms — otherwise a chapter that declared `hinted` would
# read back `suspected` and look like drift the moment it was settled.
REVEAL_CANON = {reveal: STANCE_REVEALS[stance] for reveal, stance in STANCES.items()}


REVEAL_RANK = {'hinted': 1, 'suspected': 2, 'misled': 2, 'confirmed': 3, 'retracted': 0}


KIND_ALIASES = {'resource': 'resources', 'place': 'places', 'places': 'places',
                'characters': 'characters', 'character': 'characters', 'knowledge': 'knowledge',
                'relations': 'relations', 'relation': 'relations', 'clock': 'clock',
                'node': 'node', 'thread': 'thread',
                'disclosure': 'disclosure', 'reader_knowledge': 'disclosure', 'reader': 'disclosure'}


# The projection field a coordinate kind reads.
FIELDS = {'resources': 'resources', 'places': 'placements', 'knowledge': 'knowledge',
          'characters': 'character_current', 'relations': 'relations', 'clock': 'clock',
          'node': 'story_nodes', 'thread': 'thread_progress', 'disclosure': 'reader_knowledge'}


WORLD_GEOGRAPHY = 'geography'


# ------------------------------------------------------------------- values
def _safe(value):
    """A JSON-safe deep copy: findings and deviations are digested and stored."""
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(v) for v in value]
    if isinstance(value, bool) or value is None or isinstance(value, (str, int)):
        return value
    if isinstance(value, float):
        return value if value == value and value not in (float('inf'), float('-inf')) else str(value)
    if isinstance(value, Decimal):
        return int(value) if value.is_finite() and value == value.to_integral_value() else str(value)
    return str(value)


def _number(value):
    """A precise comparable quantity, never a binary-float approximation of the ledger."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if not isinstance(value, (str, float, Decimal)):
        return None
    try:
        number = Decimal(str(value).strip())
    except InvalidOperation:
        return None
    if not number.is_finite() or len(number.as_tuple().digits) > 120 \
            or abs(number.as_tuple().exponent) > 120:
        return None
    return int(number) if number == number.to_integral_value() else number


def _item(container, key):
    """A projection entry as a dict, whatever the stored shape was."""
    value = (container or {}).get(key)
    return value if isinstance(value, dict) else {}


def _window(value):
    """A declared `[earliest, latest]` chapter window."""
    return isinstance(value, list) and len(value) == 2 and all(type(n) is int for n in value) \
        and value[0] <= value[1]


def _kind_of(kind):
    return KIND_ALIASES.get(kind, kind) if isinstance(kind, str) else ''


def _finding(chapter, kind, key, expect, got, why, criterion='drift', severity='blocker',
             scope='chapter'):
    return {'chapter': chapter, 'kind': kind, 'key': key, 'expect': _safe(expect), 'got': _safe(got),
            'why': why, 'criterion': criterion, 'severity': severity,
            'target_chapter': chapter, 'repair_scope': scope, 'reason': why}


def _reject(findings, code, message, details=None):
    # The full list, not a sample: a preview answers every defect in one call, and a truncated
    # answer used to resurface the cut findings one repair round at a time.
    rows = [f for f in findings if isinstance(f, dict)]
    require(not rows, code, message, {**(details or {}), 'findings': _safe(rows),
                                      'findings_count': len(rows),
                                      'recover': '按 findings 逐条修正章纲/卷纲后重提；'
                                                 '不要改库或历史事实。'})


# ------------------------------------------------------------------- world
def _world_index(model):
    return world.index(model) if isinstance(model, dict) else {}


def _world_ids(model):
    return {key.split(':', 1)[-1] for key in _world_index(model)}


def _entity_ids(model, selected=None):
    ids = set()
    for row in ((model or {}).get('characters') or []) if isinstance(model, dict) else []:
        if isinstance(row, dict) and text(row.get('id')):
            ids.add(row['id'])
    if isinstance(selected, dict):
        protagonist = selected.get('protagonist')
        if isinstance(protagonist, dict) and text(protagonist.get('id')):
            ids.add(protagonist['id'])
    return ids


def _place_registry(state, model):
    rows = {}
    for ident, row in ((state or {}).get('places') or {}).items():
        rows[ident] = row if isinstance(row, dict) else {'id': ident}
    for row in (((model or {}).get(WORLD_GEOGRAPHY) or []) if isinstance(model, dict) else []):
        if isinstance(row, dict) and text(row.get('id')):
            rows.setdefault(row['id'], row)
    return rows


def _place_id(state, model, value):
    """The projection id a declared place names; an unknown value is returned unchanged."""
    if not text(value):
        return value
    rows = _place_registry(state, model)
    if value in rows:
        return value
    for ident, row in rows.items():
        if isinstance(row, dict) and row.get('name') == value:
            return ident
    return value


def _split_dump(value):
    """Parse this engine's own JSON-array projection key without importing a parser.

    `facts.resource_key` is `dump([holder, asset, unit])`, a three-string JSON array. Reading it
    back is how a chapter outline that names a resource the way a reader would ("spirit-stone")
    still produces a conservation-checked flow event.
    """
    if not isinstance(value, str) or len(value) < 2 or value[0] != '[' or value[-1] != ']':
        return None
    body, index, parts = value[1:-1], 0, []
    escapes = {'"': '"', '\\': '\\', '/': '/', 'b': '\b', 'f': '\f', 'n': '\n', 'r': '\r', 't': '\t'}
    while index < len(body):
        if body[index] != '"':
            return None
        index += 1
        chars = []
        while True:
            if index >= len(body):
                return None
            char = body[index]
            if char == '"':
                index += 1
                break
            if char == '\\':
                if index + 1 >= len(body):
                    return None
                marker = body[index + 1]
                if marker == 'u':
                    code = body[index + 2:index + 6]
                    if len(code) != 4:
                        return None
                    try:
                        chars.append(chr(int(code, 16)))
                    except ValueError:
                        return None
                    index += 6
                    continue
                if marker not in escapes:
                    return None
                chars.append(escapes[marker])
                index += 2
                continue
            chars.append(char)
            index += 1
        parts.append(''.join(chars))
        if index < len(body):
            if body[index] != ',':
                return None
            index += 1
    return parts if len(parts) == 3 else None


def _resource_coordinate(state, key, asset=None):
    """The projection key a declared resource coordinate names.

    Exact coordinate first, then a coordinate whose asset element is the declared key. Ambiguity is
    not guessed: two coordinates for the same asset need the holder named explicitly.
    """
    resources = (state or {}).get('resources') or {}
    if key in resources:
        return key
    asset = key if asset is None else asset
    if not text(asset):
        return None
    matches = []
    for existing in resources:
        parts = _split_dump(existing)
        if parts and (key in parts[1:2] or asset == parts[1] or key in parts):
            matches.append(existing)
    return matches[0] if len(matches) == 1 else None


def _resource_known(state, model, key):
    if _resource_coordinate(state, key) is not None:
        return True
    if text(key) and key in _world_ids(model):
        return True
    return not (state or {}).get('resources')


def _resource_parts(coordinate, item, planned):
    """(holder, asset, unit) for a resource flow event, from the item, the plan or the key."""
    holder = item.get('holder') or planned.get('holder')
    asset = item.get('asset') or planned.get('asset')
    unit = item.get('unit') or planned.get('unit')
    if text(holder) and text(asset) and text(unit):
        return holder, asset, unit
    parts = _split_dump(coordinate)
    if parts is None:
        return None, None, None
    return (holder or parts[0], asset or parts[1], unit or parts[2])


# -------------------------------------------------------------- projection
def _reveal_of(entry):
    if not isinstance(entry, dict):
        return None
    if entry.get('status') in REVEALS:
        return entry['status']
    return STANCE_REVEALS.get(entry.get('stance'))


def _project(state, kind, key):
    """The canonical projection a coordinate reads, shaped the way a chapter outline declares it."""
    kind = _kind_of(kind)
    if kind == 'resources':
        coordinate = _resource_coordinate(state, key)
        return None if coordinate is None else _number(((state or {}).get('resources') or {}).get(coordinate))
    if kind == 'places':
        if 'custody' in (state or {}):
            return spatial.location(state, key)
        return ((state or {}).get('placements') or {}).get(key)
    if kind == 'knowledge':
        return _reveal_of(((state or {}).get('knowledge') or {}).get(key))
    if kind == 'characters':
        return _item((state or {}).get('character_current'), key).get('value')
    if kind == 'relations':
        # `facts.apply_event` stores the relation's `after` directly, not an entry dict, so the
        # projection is the stored value itself (None = the coordinate was never established).
        return ((state or {}).get('relations') or {}).get(key)
    if kind == 'clock':
        return (state or {}).get('clock')
    if kind == 'node':
        return _item((state or {}).get('story_nodes'), key).get('status')
    if kind == 'thread':
        return _item((state or {}).get('thread_progress'), key).get('status')
    if kind == 'disclosure':
        return _item((state or {}).get('reader_knowledge'), key).get('status')
    return None


def project(state, kind, key):
    """Public projection query: the current true value of one coordinate.

    Exported so a caller (a fixture, a brief, a repair dispatch) can fill `actual.from` with the
    value the engine already holds instead of guessing it — the reconciliation compares the two, and
    the writer is never asked to self-report a before-value.
    """
    return _safe(_project(state, kind, key))


def _declared(kind, key, value, state, model):
    """A declared coordinate value normalized to the projection's own vocabulary."""
    kind = _kind_of(kind)
    if kind == 'places':
        return _place_id(state, model, value)
    if kind in ('resources', 'clock'):
        return _number(value)
    return value


def _canonical_reveal(value):
    """The representative stage two spellings of the same stance agree on."""
    return REVEAL_CANON.get(value, value)


def _same(kind, expect, got):
    kind = _kind_of(kind)
    if kind in ('resources', 'clock'):
        left, right = _number(expect), _number(got)
        return left is not None and right is not None and left == right
    if kind in ('knowledge', 'disclosure'):
        return _canonical_reveal(expect) == _canonical_reveal(got)
    return _safe(expect) == _safe(got)


# ---------------------------------------------------------------- deltas
def _rows_of(chapter, field, findings):
    """A declared delta array: a list of objects, or a finding. Absent means empty (never invented)."""
    value = chapter.get(field)
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
        findings.append(_finding(chapter.get('chapter'), field, field, 'array', type(value).__name__,
                                 '章纲的增量须为对象数组；空数组、缺省或 null 均表示本章该类无变化。',
                                 'drift_shape', 'blocker', 'outline'))
        return []
    return value


def _deltas(chapter, findings):
    """The normalized increments one chapter row declares, in settlement order.

    Keys are the projection coordinates (`who:topic` for knowledge, the resource coordinate for
    resources, the entity for places/characters), so the same list feeds the state chain, the
    coverage check and the event builder.
    """
    chapter_no = chapter.get('chapter')
    coords = []
    for row in _rows_of(chapter, 'resources', findings):
        key = row.get('key')
        if not text(key) or _number(row.get('from')) is None or _number(row.get('to')) is None:
            findings.append(_finding(chapter_no, 'resources', key, '{key,from,to,reason}',
                                     _safe(row), '资源增量需要 key 与 from/to 数值。', 'drift_shape', 'blocker', 'outline'))
            continue
        if not text(row.get('reason')):
            findings.append(_finding(chapter_no, 'resources', key, 'reason', None,
                                     '资源增量须写明原因。', 'drift_shape', 'blocker', 'outline'))
        coords.append({'kind': 'resources', 'key': key, 'from': _number(row.get('from')),
                       'to': _number(row.get('to')), 'reason': row.get('reason') or '',
                       'detail': {'holder': row.get('holder'), 'asset': row.get('asset'),
                                  'unit': row.get('unit')}})
    for row in _rows_of(chapter, 'places', findings):
        key = row.get('entity')
        if not text(key) or not text(row.get('to')):
            findings.append(_finding(chapter_no, 'places', key, '{entity,from,to,reason}', _safe(row),
                                     '位置增量需要 entity 与 to 地点（from 可为 null）。', 'drift_shape', 'blocker', 'outline'))
            continue
        if not text(row.get('reason')):
            findings.append(_finding(chapter_no, 'places', key, 'reason', None,
                                     '位置变化须写明原因。', 'drift_shape', 'blocker', 'outline'))
        coords.append({'kind': 'places', 'key': key, 'from': row.get('from'), 'to': row.get('to'),
                       'reason': row.get('reason') or '',
                       'detail': {'route': row.get('route'), 'links': row.get('links'),
                                  'depart': row.get('depart'), 'arrive': row.get('arrive')}})
    for row in _rows_of(chapter, 'knowledge', findings):
        who, topic = row.get('who'), row.get('topic')
        if not text(who) or not text(topic) or row.get('to') not in REVEALS:
            findings.append(_finding(chapter_no, 'knowledge', who, 'to∈' + '|'.join(REVEALS), _safe(row),
                                     '知情增量需要 who/topic 与 to∈' + '|'.join(REVEALS) + '。',
                                     'drift_shape', 'blocker', 'outline'))
            continue
        if row.get('from') is not None and row.get('from') not in REVEALS:
            findings.append(_finding(chapter_no, 'knowledge', who + ':' + topic, 'from∈' + '|'.join(REVEALS),
                                     row.get('from'), '知情的 from 只能是 null 或已知披露档位。',
                                     'drift_shape', 'blocker', 'outline'))
        if not text(row.get('reason')):
            findings.append(_finding(chapter_no, 'knowledge', who + ':' + topic, 'reason', None,
                                     '知情变化须写明原因。', 'drift_shape', 'blocker', 'outline'))
        coords.append({'kind': 'knowledge', 'key': who + ':' + topic, 'from': row.get('from'),
                       'to': row.get('to'), 'reason': row.get('reason') or '',
                       'detail': {'who': who, 'topic': topic}})
    for row in _rows_of(chapter, 'characters', findings):
        key, after = row.get('entity'), row.get('to')
        if not text(key) or not isinstance(after, dict) or not all(text(after.get(k)) for k in ('desire', 'stance', 'relationship_focus')):
            findings.append(_finding(chapter_no, 'characters', key,
                                     'to={desire,stance,relationship_focus}', _safe(row),
                                     '人物增量需要 entity 与 to 的三项当前状态。', 'drift_shape', 'blocker', 'outline'))
            continue
        if not text(row.get('choice')) or not text(row.get('cost')):
            findings.append(_finding(chapter_no, 'characters', key, 'choice/cost', _safe(row),
                                     '人物变化须写明选择与代价。', 'drift_shape', 'blocker', 'outline'))
        coords.append({'kind': 'characters', 'key': key, 'from': row.get('from'), 'to': after,
                       'reason': row.get('reason') or '',
                       'detail': {'choice': row.get('choice'), 'cost': row.get('cost'),
                                  'change': row.get('change')}})
    # The fifth increment: one relation coordinate per row, keyed exactly the way the factual
    # reducer keys it (`source>target:key`), so the chain, the coverage check and the event builder
    # all speak one identity. The literal continuity the design leans on — chapter N's `to` is
    # chapter N+1's `from` — is the same `drift_chain` check every other increment runs.
    for row in _rows_of(chapter, 'relations', findings):
        source, target, relation = row.get('source'), row.get('target'), row.get('key')
        if not text(source) or not text(target) or source == target or not text(relation) \
                or any(c in relation for c in ':>') or not text(row.get('to')):
            findings.append(_finding(chapter_no, 'relations', relation,
                                     '{source,target,key,from,to,reason}；source≠target，key 不含 : 与 >',
                                     _safe(row),
                                     '关系增量需要 source/target 两端实体、关系名 key 与 to 稳定短词。',
                                     'drift_shape', 'blocker', 'outline'))
            continue
        if row.get('from') is not None and not text(row.get('from')):
            findings.append(_finding(chapter_no, 'relations', source + '>' + target + ':' + relation,
                                     'from:null|既有关系值', _safe(row.get('from')),
                                     '关系的 from 只能是 null（首次确立）或前章留下的关系值。',
                                     'drift_shape', 'blocker', 'outline'))
        if not text(row.get('reason')):
            findings.append(_finding(chapter_no, 'relations', source + '>' + target + ':' + relation,
                                     'reason', None, '关系变化须写明原因。', 'drift_shape', 'blocker', 'outline'))
        coords.append({'kind': 'relations', 'key': source + '>' + target + ':' + relation,
                       'from': row.get('from'), 'to': row.get('to'),
                       'reason': row.get('reason') or '',
                       'detail': {'source': source, 'target': target, 'key': relation}})
    # The settlement side applies the same test when the chapter's prose arrives (reconcile step
    # five); a row that cannot pass it here would deadlock the write stage against a frozen
    # outline it is not allowed to fix.
    for row in _rows_of(chapter, 'disclosures', findings):
        topic, after = row.get('topic'), row.get('after')
        if not text(topic) or after not in REVEALS:
            findings.append(_finding(chapter_no, 'disclosures', topic, 'topic 与 ' + '|'.join(REVEALS), _safe(row),
                                     '章纲的披露需要 topic 与档位。', 'drift_shape', 'blocker', 'outline'))
    clock = chapter.get('clock')
    if clock is None or not isinstance(clock, dict) or type(clock.get('advance_days')) is not int \
            or clock['advance_days'] < 0:
        findings.append(_finding(chapter_no, 'clock', 'main', '{advance_days:非负整数}', _safe(clock),
                                 '章纲须声明 clock.advance_days（非负整数）。', 'drift_shape', 'blocker', 'outline'))
    else:
        coords.append({'kind': 'clock', 'key': 'main', 'advance': clock['advance_days'],
                       'reason': '', 'detail': {}})
    plot = chapter.get('plot')
    if not isinstance(plot, dict):
        findings.append(_finding(chapter_no, 'plot', 'plot', '{beat,nodes,threads}', _safe(plot),
                                 '章纲需要 plot.beat 与 nodes/threads。', 'drift_shape', 'blocker', 'outline'))
        plot = {}
    for row in plot.get('nodes') or []:
        if not isinstance(row, dict) or not text(row.get('node')) or row.get('after') not in NODE_STATES:
            findings.append(_finding(chapter_no, 'node', None, 'after∈' + '|'.join(NODE_STATES), _safe(row),
                                     'plot.nodes 需要 {node,after,outcome}。', 'drift_shape', 'blocker', 'outline'))
            continue
        coords.append({'kind': 'node', 'key': row['node'], 'from': None, 'to': row['after'],
                       'reason': row.get('outcome') or '',
                       'detail': {'outcome': row.get('outcome'), 'criteria': row.get('criteria')}})
    for row in plot.get('threads') or []:
        if not isinstance(row, dict) or not text(row.get('thread')) or row.get('after') not in THREAD_STATES:
            findings.append(_finding(chapter_no, 'thread', None, 'after∈' + '|'.join(THREAD_STATES), _safe(row),
                                     'plot.threads 需要 {thread,after,reason}。', 'drift_shape', 'blocker', 'outline'))
            continue
        if not text(row.get('reason')):
            findings.append(_finding(chapter_no, 'thread', row['thread'], 'reason', None,
                                     '线路变化须写明原因。', 'drift_shape', 'blocker', 'outline'))
        if row.get('after') == 'dormant' and not (type(row.get('return_by')) is int
                                                  and row['return_by'] > (chapter_no or 0)):
            findings.append(_finding(chapter_no, 'thread', row['thread'], 'return_by>本章', row.get('return_by'),
                                     '暂缓线路须声明未来章节 return_by，否则线路会静默消失。',
                                     'drift_shape', 'blocker', 'outline'))
        coords.append({'kind': 'thread', 'key': row['thread'], 'from': None, 'to': row['after'],
                       'reason': row.get('reason') or '',
                       'detail': {'return_by': row.get('return_by')}})
    # The promise account: a chapter plants and pays off the promises its volume declared. The
    # field is mandatory because "this chapter opens no promise" is itself a declaration the chain
    # has to see; the two actions are the whole vocabulary (a mid-course reminder is `hook_refs`).
    if not isinstance(chapter.get('hooks'), list):
        findings.append(_finding(chapter_no, 'hook', 'hooks', 'array', _safe(chapter.get('hooks')),
                                 '章纲须声明 hooks 数组（本章不动伏笔就给空数组），缺字段不是"没有伏笔"。',
                                 'chapter_hook', 'blocker', 'outline'))
    for row in _rows_of(chapter, 'hooks', findings):
        hook_id, action = row.get('hook'), row.get('action')
        if not text(hook_id) or action not in HOOK_ACTIONS:
            findings.append(_finding(chapter_no, 'hook', hook_id, 'action∈plant|payoff', _safe(row),
                                     '章纲 hooks 需要 {hook,action:plant|payoff,note?}。',
                                     'chapter_hook', 'blocker', 'outline'))
            continue
        coords.append({'kind': 'hook', 'key': hook_id, 'from': None, 'to': action,
                       'reason': row.get('note') or '',
                       'detail': {'note': row.get('note')}})
    return coords


def _enter_rows(chapter, findings):
    """The declared enter/exit coordinates, normalized as `{kind,key,expected}` rows."""
    result = []
    for field in ('enter', 'exit'):
        value = chapter.get(field)
        if not isinstance(value, list):
            findings.append(_finding(chapter.get('chapter'), field, field, 'array',
                                     type(value).__name__ if value is not None else None,
                                     '章纲必须声明 ' + field + '（无坐标用空数组）。',
                                     'drift_shape', 'blocker', 'outline'))
            continue
        for row in value:
            if not isinstance(row, dict) or row.get('kind') not in ENTER_KINDS or not text(row.get('key')):
                findings.append(_finding(chapter.get('chapter'), field, None,
                                         'kind∈' + '|'.join(ENTER_KINDS), _safe(row),
                                         field + ' 坐标须为 {kind,key,expected}。',
                                         'drift_shape', 'blocker', 'outline'))
                continue
            if 'expected' not in row:
                findings.append(_finding(chapter.get('chapter'), _kind_of(row.get('kind')), row.get('key'),
                                         'expected', None, field + ' 坐标缺少 expected。',
                                         'drift_shape', 'blocker', 'outline'))
                continue
            result.append({'field': field, 'kind': row['kind'], 'key': _coord_key(row['kind'], row['key']),
                           'expected': row['expected'], 'row': row})
    return result


def _coord_key(kind, key):
    """The projection key a coordinate names: the main clock is one thread, whatever it is called."""
    return 'main' if _kind_of(kind) == 'clock' else key


def _reduce(state, event, chapter, kind, key, findings, scope='chapter'):
    """Apply the canonical reducer to scratch state; a refused event leaves no partial changes."""
    candidate = copy.deepcopy(state)
    try:
        facts.apply_event(candidate, event, chapter)
    except Error as exc:
        criterion = {'resources': 'drift_resource', 'places': 'drift_place',
                     'knowledge': 'drift_knowledge', 'characters': 'drift_character',
                     'relations': 'drift_relation',
                     'clock': 'drift_clock', 'node': 'drift_node', 'thread': 'drift_thread',
                     'hook': 'chapter_hook', 'disclosure': 'drift_disclosure'}.get(kind, 'design_drift')
        findings.append(_finding(chapter, kind, key, '可按正式规则结算', exc.code,
                                 str(exc), criterion, 'blocker', scope))
        return False
    state.clear()
    state.update(candidate)
    return True


# ------------------------------------------------------------- plan rows
def _preconditions(chapter):
    """`enter` as the precondition rows the older consumers (narrative.unmet) already read.

    The kind is translated into the projection field the value actually lives in: a chapter speaks
    of `places` and `character`, the state stores `placements` and `character_current`. The main
    clock is the one coordinate with a fixed key, so it is normalized to `clock/main` here.
    """
    fields = {'places': 'placements', 'place': 'placements',
              'characters': 'character_current', 'character': 'character_current'}
    rows = []
    for item in chapter.get('enter') or []:
        if not isinstance(item, dict) or 'expected' not in item:
            continue
        kind = item.get('kind')
        rows.append({'kind': fields.get(kind, kind), 'key': _coord_key(kind, item.get('key')),
                     'expected': copy.deepcopy(item.get('expected'))})
    return rows


def plan_rows(chapters):
    """The materialized settlement row for each chapter outline row.

    This is the row the engine reconciles a `drift_check` against and the one the writer's material
    is built from, so it carries both vocabularies: the outline's own declarations (`enter`/`exit`,
    the five increment arrays, `clock.advance_days`) and the plan-shaped keys the surrounding code
    already reads (`node_ids`/`node_actions`/`node_contracts`/`preconditions`/`participants`/
    `scenes`/`pacing`/`world_refs`).
    """
    rows = []
    for chapter in chapters or []:
        if not isinstance(chapter, dict) or type(chapter.get('chapter')) is not int:
            continue
        plot = chapter.get('plot') if isinstance(chapter.get('plot'), dict) else {}
        nodes = [row for row in plot.get('nodes') or [] if isinstance(row, dict) and text(row.get('node'))]
        threads = [row for row in plot.get('threads') or [] if isinstance(row, dict) and text(row.get('thread'))]
        characters = [row for row in chapter.get('characters') or [] if isinstance(row, dict)]
        participants = []
        for entry in [row.get('entity') for row in characters] + \
                [row.get('id') for row in chapter.get('new_entities') or [] if isinstance(row, dict)] + \
                [row.get('who') for row in chapter.get('knowledge') or [] if isinstance(row, dict)] + \
                [row.get('entity') for row in chapter.get('places') or [] if isinstance(row, dict)] + \
                [end for row in chapter.get('relations') or [] if isinstance(row, dict)
                 for end in (row.get('source'), row.get('target'))]:
            if text(entry) and entry not in participants:
                participants.append(entry)
        for scene in chapter.get('scenes') or []:
            if isinstance(scene, dict):
                for present in scene.get('present') or []:
                    if text(present) and present not in participants:
                        participants.append(present)
        row = {
            'chapter': chapter['chapter'],
            'synopsis': chapter.get('synopsis', ''),
            'goal': chapter.get('synopsis', ''),
            'obstacle': plot.get('beat', ''),
            'choice': (characters[0].get('choice') if characters else '') or plot.get('beat', ''),
            'cost': (characters[0].get('cost') if characters else '') or (nodes[0].get('outcome') if nodes else '') or '',
            'change': plot.get('beat', ''),
            'ending': (nodes[-1].get('outcome') if nodes else '') or (threads[-1].get('reason') if threads else '') or '',
            'plot': copy.deepcopy(plot),
            'node_ids': [row['node'] for row in nodes],
            'node_actions': [{'node': row['node'], 'after': row['after']} for row in nodes],
            'node_contracts': {row['node']: copy.deepcopy(row) for row in nodes},
            'preconditions': _preconditions(chapter),
            'disclosures': copy.deepcopy(chapter.get('disclosures') or []),
            'participants': participants,
            'scenes': copy.deepcopy(chapter.get('scenes') or []),
            'pacing': copy.deepcopy(chapter.get('pacing') or {}),
            'world_refs': copy.deepcopy(chapter.get('world_refs') or []),
            'new_entities': copy.deepcopy(chapter.get('new_entities') or []),
            'hook_refs': copy.deepcopy(chapter.get('hook_refs') or []),
            'hooks': copy.deepcopy(chapter.get('hooks') or []),
            'hook_contracts': copy.deepcopy(chapter.get('hook_contracts') or {}),
            'reader_refs': copy.deepcopy(chapter.get('reader_refs') or []),
            'history_refs': copy.deepcopy(chapter.get('history_refs') or []),
            'enter': copy.deepcopy(chapter.get('enter') or []),
            'exit': copy.deepcopy(chapter.get('exit') or []),
            'clock': copy.deepcopy(chapter.get('clock') or {'advance_days': 0}),
            'schedule': [],
        }
        # The optional protocols a row may carry travel with it: the scene/reading identity
        # `story_memory.bind` froze on the chapter outline, and the reading coverage a reading-mode
        # revision reads. Dropping them here would silently disable the workbench's scene chain and
        # turn every reading revision conservative, because this row is what both are read from.
        for field in PROTOCOL_FIELDS:
            if chapter.get(field) is not None:
                row[field] = copy.deepcopy(chapter[field])
        row['dependency_coverage'] = chapter.get('dependency_coverage') or 'partial'
        if chapter.get('style') is not None:
            row['style'] = copy.deepcopy(chapter['style'])
        for field in DELTA_KINDS:
            row[field] = copy.deepcopy(chapter.get(field) or ({} if field == 'clock' else []))
        rows.append(row)
    return rows
