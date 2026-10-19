"""Validate outline state chains and reconcile prose deltas against projected facts.

Design and prose share event builders and reducers. Only facts.settle verifies prose
evidence; scratch design projections never become canonical facts. Findings carry
JSON-safe coordinates and repair scope for workflow.route_repair."""
from __future__ import annotations

import copy

from .contracts import Error, han_count, require, text
from .entities import register as register_entity
from . import facts, narrative, spatial, world

# --------------------------------------------------------------- declarations
VOLUME_FIELDS = ('id', 'purpose', 'stage', 'arc', 'turns', 'climax', 'nodes', 'threads', 'hooks',
                 'resources', 'places', 'knowledge', 'characters', 'clock', 'exit_state', 'style')
CHAPTER_FIELDS = ('chapter', 'synopsis', 'plot', 'resources', 'places', 'knowledge', 'characters',
                  'clock', 'enter', 'exit', 'disclosures', 'world_refs', 'new_entities',
                  'hook_refs', 'hooks', 'reader_refs', 'history_refs', 'scenes', 'pacing', 'style')
# The four increment arrays plus the clock: what a chapter declares it changes.
DELTA_KINDS = ('resources', 'places', 'knowledge', 'characters', 'clock')
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
ENTER_KINDS = ('resources', 'places', 'knowledge', 'character', 'characters', 'clock', 'node', 'thread')
ITEM_KINDS = ('node', 'thread', 'hook', 'resources', 'places', 'knowledge', 'characters', 'clock',
              'disclosure', 'reader_knowledge', 'reader')
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
                'clock': 'clock', 'node': 'node', 'thread': 'thread',
                'disclosure': 'disclosure', 'reader_knowledge': 'disclosure', 'reader': 'disclosure'}
# The projection field a coordinate kind reads.
FIELDS = {'resources': 'resources', 'places': 'placements', 'knowledge': 'knowledge',
          'characters': 'character_current', 'clock': 'clock', 'node': 'story_nodes',
          'thread': 'thread_progress', 'disclosure': 'reader_knowledge'}
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
    return str(value)


def _number(value):
    """A comparable number for a declared quantity, or None when it is not numeric."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value if value == value and value not in (float('inf'), float('-inf')) else None
    if isinstance(value, str):
        body = value.strip()
        if not body:
            return None
        try:
            number = float(body)
        except ValueError:
            return None
        if number != number or number in (float('inf'), float('-inf')):
            return None
        return number
    return None


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
    rows = [f for f in findings if isinstance(f, dict)]
    require(not rows, code, message, {**(details or {}), 'findings': _safe(rows[:12]),
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
    return _project(state, kind, key)


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
        return left is not None and right is not None and abs(left - right) < 1e-9
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


def _reduce(state, event, chapter, kind, key, findings, scope='chapter'):
    """Apply the canonical reducer to scratch state; a refused event leaves no partial changes."""
    candidate = copy.deepcopy(state)
    try:
        facts.apply_event(candidate, event, chapter)
    except Error as exc:
        criterion = {'resources': 'drift_resource', 'places': 'drift_place',
                     'knowledge': 'drift_knowledge', 'characters': 'drift_character',
                     'clock': 'drift_clock', 'node': 'drift_node', 'thread': 'drift_thread',
                     'hook': 'chapter_hook', 'disclosure': 'drift_disclosure'}.get(kind, 'design_drift')
        findings.append(_finding(chapter, kind, key, '可按正式规则结算', exc.code,
                                 str(exc), criterion, 'blocker', scope))
        return False
    state.clear()
    state.update(candidate)
    return True


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


# ------------------------------------------------------- outline validation
def _deep_han(value):
    if isinstance(value, str):
        return han_count(value)
    if isinstance(value, dict):
        return sum(_deep_han(item) for item in value.values())
    if isinstance(value, list):
        return sum(_deep_han(item) for item in value)
    return 0


def _length_policy(policy):
    if not isinstance(policy, dict) or not policy:
        return None
    words, tolerance = policy.get('words'), policy.get('tolerance')
    if type(words) is not int or type(tolerance) is not int:
        return None
    return words, tolerance


def _ladder_stages(selected):
    """The 格局 rungs a v5 opening chose, in order; empty for an opening that never chose one.

    A volume names the rung it plays on, and the rungs only climb: the contract's volume order is the
    story's order, so the same index sequence has to be non-decreasing across the whole book.
    A selection that is not the declared shape yields no rungs rather than raising: the gate already
    owns that shape, and a half-written project must still be able to read its own outline.
    """
    choice = selected.get('ladder') if isinstance(selected, dict) else None
    rows = choice.get('ladder') if isinstance(choice, dict) else None
    return [row for row in (rows or []) if isinstance(row, dict) and text(row.get('stage'))]


def validate_volume_outline(data, contract, world, selected=None, existing=None, missing_ids=None,
                            state=None, strict=True):
    """Check and normalize the volume outline batch; returns `{volume_id: row}`.

    One volume per contract row, in contract order, each within the policy's length band, with node
    and thread ids unique across the whole book (a cross-volume line says `continues: true`), every
    referenced key/entity present in the world model or the existing state, node windows inside the
    volume's own chapter range, and a non-empty `exit_state`.
    """
    require(isinstance(data, dict) and isinstance(contract, dict), 'volume_outline',
            '卷纲回执须为 {volumes:[...]} 对象。')
    volumes = data.get('volumes')
    require(isinstance(volumes, list) and volumes, 'volume_outline', '卷纲须交出至少一卷。')
    rows = contract.get('volumes') or []
    known = {row['id']: row for row in rows}
    existing = existing if isinstance(existing, dict) else {}
    allowed = [ident for ident in (missing_ids if missing_ids is not None else known)
               if ident in known and ident not in existing]
    require(allowed, 'volume_outline', '本次派工没有需要交付的卷。')
    submitted = [row.get('id') if isinstance(row, dict) else None for row in volumes]
    require(submitted == list(allowed), 'volume_outline', '卷纲须按合同顺序恰好覆盖本次派发的卷，不多不少。',
            {'expected': list(allowed), 'got': submitted})
    findings = []
    seen_nodes, seen_threads, seen_hooks = {}, {}, {}
    for old_id, old in existing.items():
        for row in (old or {}).get('nodes') or []:
            if isinstance(row, dict) and text(row.get('id')):
                seen_nodes[row['id']] = old_id
        for row in (old or {}).get('threads') or []:
            if isinstance(row, dict) and text(row.get('id')):
                seen_threads[row['id']] = old_id
        for row in (old or {}).get('hooks') or []:
            if isinstance(row, dict) and text(row.get('id')):
                seen_hooks[row['id']] = old_id
    world_ids = _world_ids(world)
    entities = _entity_ids(world, selected) | set(((state or {}).get('entities') or {}))
    ladder = _ladder_stages(selected)
    rungs = [row['stage'] for row in ladder]
    report = {}
    for volume in volumes:
        ident = volume['id']
        contract_row = known[ident]
        first, end = contract_row.get('first'), contract_row.get('end')
        chapter_no = first
        purpose = volume.get('purpose')
        if not text(purpose) or not text(volume.get('arc')) or not text(volume.get('climax')) \
                or not text(volume.get('exit_state')):
            findings.append(_finding(chapter_no, 'volume', ident, 'purpose/arc/climax/exit_state', _safe(
                {k: volume.get(k) for k in ('purpose', 'arc', 'climax', 'exit_state')}),
                '卷纲需要职责、卷内弧线、卷末高潮与卷末状态各一句。', 'volume_shape', 'blocker', 'volume'))
        volume_style = volume.get('style')
        if strict and (not isinstance(volume_style, dict) or not text(volume_style.get('trend'))):
            findings.append(_finding(chapter_no, 'style', ident, '{trend:非空文本}',
                                     _safe(volume_style), '新卷纲须声明具体的 style.trend。',
                                     'volume_style', 'blocker', 'volume'))
        # A v5 opening that chose a 格局 ladder names one rung per volume, verbatim; an opening that
        # never chose one leaves `stage` empty and nothing here changes for it.
        if ladder and volume.get('stage') not in rungs:
            findings.append(_finding(chapter_no, 'stage', ident, rungs, _safe(volume.get('stage')),
                                     '本卷的格局层级必须逐字取自已选阶梯里的一级。',
                                     'volume_stage', 'blocker', 'volume'))
        policy = _length_policy(contract.get('volume_outline'))
        if policy:
            words, tolerance = policy
            length = _deep_han({key: volume.get(key) for key in VOLUME_FIELDS})
            if not words - tolerance <= length <= words + tolerance:
                findings.append(_finding(chapter_no, 'volume', ident, [words - tolerance, words + tolerance],
                                         length, '卷纲篇幅不在每卷目标汉字数区间内。', 'volume_length', 'blocker', 'volume'))
        turns = volume.get('turns') or []
        if not isinstance(turns, list):
            findings.append(_finding(chapter_no, 'volume', ident, 'array', _safe(turns),
                                     'turns 须为 {at,turn} 数组。', 'volume_shape', 'blocker', 'volume'))
            turns = []
        for turn in turns:
            if not isinstance(turn, dict) or (not text(turn.get('at')) and not text(turn.get('turn'))):
                continue                      # the blank template row is "no turn declared"
            if not text(turn.get('at')) or not text(turn.get('turn')):
                findings.append(_finding(chapter_no, 'volume', ident, '{at,turn}', _safe(turn),
                                         '每个转折需要位置与内容。', 'volume_shape', 'blocker', 'volume'))
        clock = volume.get('clock')
        if not isinstance(clock, dict) or type(clock.get('advance_days')) is not int \
                or clock['advance_days'] < 0 \
                or (strict and (type(clock.get('to')) is not int or clock['to'] < 0)):
            findings.append(_finding(chapter_no, 'volume', ident,
                                     '{advance_days:非负整数,to:卷末绝对天数}', _safe(clock),
                                     '新卷纲须声明本卷推进天数与可计算的卷末绝对时钟 clock.to。',
                                     'volume_shape', 'blocker', 'volume'))
        for row in volume.get('nodes') or []:
            node_id = row.get('id') if isinstance(row, dict) else None
            if not isinstance(row, dict) or not text(node_id) or not text(row.get('purpose')) \
                    or not text(row.get('ending_condition')) or row.get('kind') not in ('main', 'side', 'hidden') \
                    or type(row.get('required')) is not bool:
                findings.append(_finding(chapter_no, 'node', node_id, 'id/kind/purpose/ending_condition/required',
                                         _safe(row), '节点需要 id、kind:main|side|hidden、purpose、ending_condition、required。',
                                         'volume_node', 'blocker', 'volume'))
                continue
            if node_id in seen_nodes and seen_nodes[node_id] != ident:
                findings.append(_finding(chapter_no, 'node', node_id, '全书唯一', seen_nodes[node_id],
                                         '节点 ID 已被其它卷登记。', 'volume_node', 'blocker', 'volume'))
            seen_nodes[node_id] = ident
            window = row.get('window')
            if not isinstance(window, list) or len(window) != 2 or not all(type(n) is int for n in window) \
                    or not (first <= window[0] <= window[1] <= end):
                findings.append(_finding(chapter_no, 'node', node_id, [first, end], _safe(window),
                                         '节点窗口须落在本卷章号区间内。', 'volume_node', 'blocker', 'volume'))
        for row in volume.get('threads') or []:
            thread_id = row.get('id') if isinstance(row, dict) else None
            if not isinstance(row, dict) or not text(thread_id) or not text(row.get('purpose')) \
                    or not text(row.get('ending_condition')) or row.get('kind') not in ('main', 'side', 'hidden') \
                    or type(row.get('required')) is not bool:
                findings.append(_finding(chapter_no, 'thread', thread_id,
                                         'id/kind/purpose/ending_condition/required', _safe(row),
                                         '线路需要 id、kind、purpose、ending_condition、required。',
                                         'volume_thread', 'blocker', 'volume'))
                continue
            carries = row.get('continues') is True
            if thread_id in seen_threads and seen_threads[thread_id] != ident:
                if not carries:
                    findings.append(_finding(chapter_no, 'thread', thread_id, 'continues:true', seen_threads[thread_id],
                                             '跨卷线路须以 continues:true 明示沿用，否则不得覆盖既有线路 ID。',
                                             'volume_thread', 'blocker', 'volume'))
            elif not carries and thread_id in seen_threads:
                findings.append(_finding(chapter_no, 'thread', thread_id, '唯一', seen_threads[thread_id],
                                         '线路 ID 在本次交付中重复。', 'volume_thread', 'blocker', 'volume'))
            seen_threads[thread_id] = ident
        hooks = volume.get('hooks')
        if not isinstance(hooks, list):
            findings.append(_finding(chapter_no, 'hook', ident, 'array',
                                     _safe(hooks) if hooks is not None else 'missing',
                                     '卷纲须声明 hooks 数组：本卷没有伏笔就给空数组，缺字段不是"没有伏笔"。',
                                     'volume_hook', 'blocker', 'volume'))
            hooks = []
        for row in hooks:
            hook_id = row.get('id') if isinstance(row, dict) else None
            if not isinstance(row, dict) or not text(hook_id) or not text(row.get('text')) \
                    or type(row.get('required')) is not bool or type(row.get('continues', False)) is not bool:
                findings.append(_finding(chapter_no, 'hook', hook_id,
                                         'id/text/plant/payoff/required/continues', _safe(row),
                                         '卷纲伏笔需要 id、对读者的具体承诺 text、plant/payoff 窗口、'
                                         'required:true|false，以及可选的 continues:true。',
                                         'volume_hook', 'blocker', 'volume'))
                continue
            # One namespace for node, thread and hook ids: a promise that shadows a node is a
            # bookkeeping collision, not two records.
            carries = row.get('continues') is True
            shadow = seen_nodes.get(hook_id) or seen_threads.get(hook_id)
            if shadow:
                holder = '节点' if hook_id in seen_nodes else '线路'
                findings.append(_finding(chapter_no, 'hook', hook_id, '全书唯一', shadow,
                                         '伏笔 ID 与已登记的%s ID 重复：节点/线路/伏笔共用同一命名空间。' % holder,
                                         'volume_hook', 'blocker', 'volume'))
            elif hook_id in seen_hooks:
                # A new volume may continue a promise an earlier volume opened, but only by saying so.
                if seen_hooks[hook_id] == ident or row.get('continues') is not True:
                    findings.append(_finding(chapter_no, 'hook', hook_id, '全书唯一', seen_hooks[hook_id],
                                             '伏笔 ID 重复：本卷内重复声明，或沿用既有卷的伏笔却没有 continues:true。',
                                             'volume_hook', 'blocker', 'volume'))
            seen_hooks[hook_id] = ident
            plant, payoff = row.get('plant'), row.get('payoff')
            if not _window(plant) or not first <= plant[0] <= plant[1] <= end:
                findings.append(_finding(chapter_no, 'hook', hook_id, [first, end], _safe(plant),
                                         '伏笔 plant 窗口须落在本卷章号区间内。',
                                         'volume_hook', 'blocker', 'volume'))
                continue
            if not _window(payoff) or payoff[0] < plant[1]:
                findings.append(_finding(chapter_no, 'hook', hook_id, {'payoff[0]>=': plant[1]}, _safe(payoff),
                                         '伏笔 payoff 窗口须为两章区间，且不早于 plant 的最迟章。',
                                         'volume_hook', 'blocker', 'volume'))
                continue
            if payoff[1] > end and (not carries or row.get('required')):
                findings.append(_finding(chapter_no, 'hook', hook_id,
                                         'continues:true 且 required:false', _safe(row),
                                         '兑现窗口越过本卷末的伏笔必须由 continues:true 带入下一卷，因此本卷不能 required。',
                                         'volume_hook', 'blocker', 'volume'))
        for row in volume.get('resources') or []:
            key = row.get('key') if isinstance(row, dict) else None
            if not isinstance(row, dict) or not text(key) or _number(row.get('from')) is None \
                    or _number(row.get('to')) is None or not text(row.get('reason')):
                findings.append(_finding(chapter_no, 'resources', key, '{key,from,to,reason}', _safe(row),
                                         '卷纲资源需要 key、from/to 数值与原因。', 'volume_reference', 'blocker', 'volume'))
                continue
            if not _resource_known(state, world, key) and key not in world_ids:
                findings.append(_finding(chapter_no, 'resources', key, '世界模型或既有状态', None,
                                         '卷纲资源 key 必须存在于世界模型或既有状态。',
                                         'volume_reference', 'blocker', 'volume'))
        for row in volume.get('places') or []:
            entity = row.get('entity') if isinstance(row, dict) else None
            if not isinstance(row, dict) or not text(entity) or not text(row.get('to')) or not text(row.get('reason')):
                findings.append(_finding(chapter_no, 'places', entity, '{entity,from,to,reason}', _safe(row),
                                         '卷纲站位需要 entity、to 与原因。', 'volume_reference', 'blocker', 'volume'))
                continue
            if entity not in entities:
                findings.append(_finding(chapter_no, 'places', entity, '已登记实体', None,
                                         '卷纲站位引用了世界模型与既有状态都没有的实体。',
                                         'volume_reference', 'blocker', 'volume'))
        for row in volume.get('knowledge') or []:
            who = row.get('who') if isinstance(row, dict) else None
            if not isinstance(row, dict) or not text(who) or not text(row.get('topic')) \
                    or row.get('to') not in REVEALS or not text(row.get('reason')):
                findings.append(_finding(chapter_no, 'knowledge', who, 'who/topic/to∈' + '|'.join(REVEALS), _safe(row),
                                         '卷纲知情需要 who、topic、to 档位与原因。', 'volume_reference', 'blocker', 'volume'))
                continue
            if who not in entities:
                findings.append(_finding(chapter_no, 'knowledge', who, '已登记实体', None,
                                         '卷纲知情引用了未登记的人物。', 'volume_reference', 'blocker', 'volume'))
        for row in volume.get('characters') or []:
            entity = row.get('entity') if isinstance(row, dict) else None
            after = row.get('to') if isinstance(row, dict) else None
            structured = isinstance(after, dict) and all(text(after.get(k))
                                                       for k in ('desire', 'stance', 'relationship_focus'))
            if not isinstance(row, dict) or not text(entity) or not (structured or not strict and text(after)) \
                    or not text(row.get('reason')):
                findings.append(_finding(chapter_no, 'characters', entity,
                                         '{entity,to:{desire,stance,relationship_focus},reason}', _safe(row),
                                         '新卷纲人物终值须用三项当前状态对象声明，并给出原因。',
                                         'volume_reference', 'blocker', 'volume'))
                continue
            if entity not in entities:
                findings.append(_finding(chapter_no, 'characters', entity, '已登记实体', None,
                                         '卷纲人物引用了未登记的实体。', 'volume_reference', 'blocker', 'volume'))
        normalized = {key: copy.deepcopy(volume.get(key, [])) for key in VOLUME_FIELDS}
        normalized['id'] = ident
        normalized['purpose'] = purpose
        normalized['stage'] = volume.get('stage') or ''
        normalized['arc'] = volume.get('arc') or ''
        normalized['climax'] = volume.get('climax') or ''
        normalized['exit_state'] = volume.get('exit_state') or ''
        normalized['turns'] = [copy.deepcopy(turn) for turn in turns
                               if isinstance(turn, dict) and text(turn.get('at')) and text(turn.get('turn'))]
        normalized['clock'] = {'advance_days': (clock or {}).get('advance_days') or 0}
        if isinstance(clock, dict) and type(clock.get('to')) is int:
            normalized['clock']['to'] = clock['to']
        normalized['nodes'] = copy.deepcopy(volume.get('nodes') or [])
        normalized['threads'] = copy.deepcopy(volume.get('threads') or [])
        normalized['hooks'] = [dict(copy.deepcopy(row),
                                    required=bool(row.get('required')),
                                    continues=bool(row.get('continues', False)))
                               for row in hooks if isinstance(row, dict)]
        normalized['style'] = copy.deepcopy(volume.get('style') or {})
        report[ident] = normalized
    if ladder:
        # The rungs climb across the whole book, not just this batch: a rolling dispatch is checked
        # against the volumes already on record, and the contract's volume order is the story order.
        rank = {stage: index for index, stage in enumerate(rungs)}
        walked = []
        for contract_volume in rows:
            source = next((row for row in volumes if row.get('id') == contract_volume['id']),
                          existing.get(contract_volume['id'])) or {}
            stage = source.get('stage') if isinstance(source, dict) else None
            if text(stage):
                walked.append((contract_volume['id'], contract_volume['first'], rank.get(stage)))
        for position in range(1, len(walked)):
            if walked[position][2] is None or walked[position - 1][2] is None:
                continue
            if walked[position][2] < walked[position - 1][2]:
                findings.append(_finding(walked[position][1], 'stage', walked[position][0],
                                         '按合同卷序只升不降', [row['stage'] for row in ladder[:walked[position][2] + 1]],
                                         '格局阶梯按合同卷序单调不减：后面的卷不能退回更小的层级。',
                                         'volume_stage', 'blocker', 'volume'))
                break
    _reject(findings, 'design_drift', '卷纲未通过机械核账。', {'volume_ids': list(allowed)})
    return report


def validate_chapter_outline(data, policy, volume_row, volume_row_outline, world, state0, strict=True):
    """Check and normalize one volume's chapter outlines; returns the chapter rows.

    Every rule of §4: continuous coverage of the volume's chapter range, synopsis length inside the
    policy band, legal increment shapes with references that exist, `exit == enter + deltas`, the
    volume-wide state chain (`simulate`), and the volume's declared terminals at the last chapter.

    A repair batch may start after the volume's first chapter: the state passed in is the state the
    book is actually in, so the rows before it are a stale prefix — the engine anchors the chain on
    the first submitted chapter whose declared entry condition matches that state. A prefix the
    engine cannot anchor on stays checked: the mismatch is reported, not skipped.
    """
    require(isinstance(data, dict), 'chapter_outline', '章纲回执须为 {volume,chapters} 对象。')
    require(isinstance(volume_row, dict) and type(volume_row.get('first')) is int
            and type(volume_row.get('end')) is int, 'chapter_outline', '章纲校验需要本卷合同范围。')
    chapters = data.get('chapters')
    require(isinstance(chapters, list) and chapters
            and all(isinstance(row, dict) and type(row.get('chapter')) is int for row in chapters),
            'chapter_outline', '章纲须按章号顺序交出 chapters 数组。')
    first, end = volume_row['first'], volume_row['end']
    numbers = [row['chapter'] for row in chapters]
    require(numbers == list(range(numbers[0], end + 1)), 'chapter_outline',
            '章纲须从起始章连续覆盖到本卷末章。',
            {'first': first, 'end': end, 'got': numbers[:3] + ['…'] + numbers[-2:]})
    require(first <= numbers[0] <= end, 'chapter_outline', '章纲起始章超出本卷范围。',
            {'first': first, 'start': numbers[0]})
    policy = policy if isinstance(policy, dict) else {}
    words = policy.get('words') if type(policy.get('words')) is int else None
    tolerance = policy.get('tolerance') if type(policy.get('tolerance')) is int else 0
    findings = []
    known_nodes = _node_registry(volume_row_outline)
    known_threads = _thread_registry(volume_row_outline)
    world_ids = _world_index(world)
    scratch = copy.deepcopy((state0 or {}).get('entities') or {})
    anchor = _anchor(data, chapters, numbers, first, end, state0, world)
    for row in chapters:
        chapter_no = row['chapter']
        synopsis = row.get('synopsis')
        if not text(synopsis):
            findings.append(_finding(chapter_no, 'synopsis', 'synopsis', '章节推进说明', None,
                                     '每章须给出 synopsis。', 'chapter_shape', 'blocker', 'outline'))
        elif words is not None:
            length = han_count(synopsis)
            if not words - tolerance <= length <= words + tolerance:
                findings.append(_finding(chapter_no, 'synopsis', 'synopsis', [words - tolerance, words + tolerance],
                                         length, '章纲篇幅不在每章目标汉字数区间内。',
                                         'chapter_length', 'blocker', 'outline'))
        refs = row.get('world_refs')
        if not isinstance(refs, list) or not all(text(ref) and ref in world_ids for ref in refs) \
                or len(refs) != len(set(refs)):
            findings.append(_finding(chapter_no, 'world_refs', 'world_refs', '世界模型已有记录 ID', _safe(refs),
                                     'world_refs 须引用存在的 领域:id，且不重复。',
                                     'chapter_world', 'blocker', 'outline'))
        plot = row.get('plot')
        chapter_style = row.get('style')
        if strict and chapter_no >= anchor and (not isinstance(chapter_style, dict)
                                     or not all(text(chapter_style.get(k)) for k in ('pov', 'rhythm'))):
            findings.append(_finding(chapter_no, 'style', 'style', '{pov,rhythm:非空文本}',
                                     _safe(chapter_style), '新章纲须声明非空的 style.pov 与 style.rhythm。',
                                     'chapter_style', 'blocker', 'outline'))
        if strict and chapter_no >= anchor and isinstance(chapter_style, dict) and 'dialogue_ratio' in chapter_style:
            ratio = chapter_style['dialogue_ratio']
            if isinstance(ratio, bool) or not isinstance(ratio, (int, float)) or not 0 <= ratio <= 1:
                findings.append(_finding(chapter_no, 'style', 'dialogue_ratio', '0~1 数值', _safe(ratio),
                                         'style.dialogue_ratio 要么省略，要么声明 0~1 的有限目标。',
                                         'chapter_style', 'blocker', 'outline'))
        if isinstance(plot, dict) and not text(plot.get('beat')):
            findings.append(_finding(chapter_no, 'plot', 'beat', '一句话情节变化', None,
                                     '章纲须写清 plot.beat。', 'chapter_shape', 'blocker', 'outline'))
        for node in (plot or {}).get('nodes') or [] if isinstance(plot, dict) else []:
            node_id = node.get('node') if isinstance(node, dict) else None
            if node_id not in known_nodes:
                findings.append(_finding(chapter_no, 'node', node_id, '本卷卷纲已登记节点', None,
                                         '章纲引用的节点不在本卷卷纲登记集合内。',
                                         'chapter_node', 'blocker', 'outline'))
        for thread in (plot or {}).get('threads') or [] if isinstance(plot, dict) else []:
            thread_id = thread.get('thread') if isinstance(thread, dict) else None
            if thread_id not in known_threads:
                findings.append(_finding(chapter_no, 'thread', thread_id, '本卷卷纲已登记线路', None,
                                         '章纲引用的线路不在本卷卷纲登记集合内。',
                                         'chapter_thread', 'blocker', 'outline'))
        for entity in row.get('new_entities') or []:
            try:
                register_entity(scratch, entity)
            except Exception as error:                       # structured Error from entities
                findings.append(_finding(chapter_no, 'entity',
                                         entity.get('id') if isinstance(entity, dict) else None,
                                         'id/name/kind 唯一', _safe(entity),
                                         '内联新实体不合法：' + str(error),
                                         'chapter_entity', 'blocker', 'outline'))
        shape = []
        _deltas(row, shape)
        findings.extend(shape)
        entry = []
        _enter_rows(row, entry)
        findings.extend(entry)
    # The promise account, in two layers: the volume declared which promises exist and when they may
    # be opened and closed; the chapters may only act on those, exactly once each, in order. Only the
    # volume's own declarations can be planted, and a promise planted here can be paid off here or
    # carried to the next volume when the volume declared `continues`.
    #
    # The anchor is computed first: a repair batch re-emits the volume's stale prefix, and judging
    # that prefix against the state the book is actually in would call every promise action it has
    # already settled a duplicate. Rows before the anchor are history; only the tail is new work.
    known_hooks = _hook_registry(volume_row_outline)
    carried = {ident: entry for ident, entry in ((state0 or {}).get('hooks') or {}).items()
               if isinstance(entry, dict)}
    planted, paid = set(), set()
    for row in chapters:
        chapter_no = row['chapter']
        if chapter_no < anchor:
            continue
        for item in row.get('hooks') or []:
            if not isinstance(item, dict):
                continue
            hook_id, action = item.get('hook'), item.get('action')
            if not text(hook_id) or action not in HOOK_ACTIONS:
                continue                      # shape already reported by `_deltas`
            declaration = known_hooks.get(hook_id)
            if declaration is None and hook_id not in carried:
                findings.append(_finding(chapter_no, 'hook', hook_id, '本卷声明或前卷未兑现的 id', None,
                                         '章纲执行了既不在本卷卷纲声明、也不是前卷遗留未兑现的伏笔。',
                                         'chapter_hook', 'blocker', 'outline'))
                continue
            if action == 'plant':
                if hook_id in carried or hook_id in planted:
                    findings.append(_finding(chapter_no, 'hook', hook_id, '未埋设', 'planted',
                                             '同一伏笔只能 plant 一次；已埋设的承诺用 hook_refs 承接。',
                                             'chapter_hook', 'blocker', 'outline'))
                    continue
                window = (declaration or {}).get('plant')
                if _window(window) and not window[0] <= chapter_no <= window[1]:
                    findings.append(_finding(chapter_no, 'hook', hook_id, window, chapter_no,
                                             'plant 不在卷纲声明的埋设窗口内。',
                                             'chapter_hook', 'blocker', 'outline'))
                planted.add(hook_id)
                continue
            if hook_id in paid or (hook_id in carried and carried[hook_id].get('status') != 'open'):
                findings.append(_finding(chapter_no, 'hook', hook_id, 'open',
                                         (carried.get(hook_id) or {}).get('status') or 'paid',
                                         '该伏笔已兑现，不能重复 payoff。',
                                         'chapter_hook', 'blocker', 'outline'))
                continue
            if hook_id not in planted and (carried.get(hook_id) or {}).get('status') != 'open':
                findings.append(_finding(chapter_no, 'hook', hook_id, 'plant 之后才 payoff', 'payoff',
                                         'payoff 早于 plant：本卷还没有埋下这个承诺。',
                                         'chapter_hook', 'blocker', 'outline'))
                continue
            window = (declaration or {}).get('payoff')
            if _window(window) and not window[0] <= chapter_no <= window[1]:
                findings.append(_finding(chapter_no, 'hook', hook_id, window, chapter_no,
                                         'payoff 不在卷纲声明的兑现窗口内。',
                                         'chapter_hook', 'blocker', 'outline'))
            paid.add(hook_id)
        for ref in row.get('hook_refs') or []:
            if text(ref) and ref not in planted and ref not in carried:
                findings.append(_finding(chapter_no, 'hook', ref, '已埋设', None,
                                         'hook_refs 承接了尚未埋设的承诺：未埋就承接是漂移。',
                                         'chapter_hook', 'blocker', 'outline'))
    _reject(findings, 'design_drift', '章纲形状/引用核账未通过。',
            {'volume': volume_row.get('id'), 'first': numbers[0]})
    tail = [row for row in chapters if row['chapter'] >= anchor]
    simulated, chain = simulate(tail, state0, world, volume_row, volume_row_outline)
    _reject(chain, 'design_drift', '章纲状态链核账未通过。',
            {'volume': volume_row.get('id'), 'anchor': anchor})
    _reject([f for f in chain if f.get('criterion') == 'drift_closure'], 'design_drift',
            '章纲卷末闭合核账未通过。', {'volume': volume_row.get('id')})
    return [_normalize_chapter(row, simulated if row['chapter'] > anchor else state0, world,
                               known_nodes, known_hooks)
            for row in tail]


def _anchor(data, chapters, numbers, first, end, state0, world):
    """Where a repair batch stops re-emitting history and starts describing the book's real state.

    A repair re-derives the rest of the volume from the state the book is in, so the prefix it
    re-emits is stale by construction: the engine anchors on the first row whose declared entry
    condition is the truth. Rows without a declared entry condition cannot anchor (they would match
    anything), which keeps a wrong first chapter from being skipped. An explicit `from_chapter` is
    taken as given.
    """
    hint = data.get('from_chapter') if isinstance(data, dict) else None
    if hint is not None:
        require(type(hint) is int and first <= hint <= end and hint in numbers,
                'chapter_outline', 'from_chapter 须在当前回执的章号范围内。')
        return hint
    if numbers[0] == first and _enter_mismatch(chapters[0], state0, world):
        for row in chapters[1:]:
            if any(item['field'] == 'enter' for item in _enter_rows(row, [])) \
                    and not _enter_mismatch(row, state0, world):
                return row['chapter']
    return numbers[0]


def _enter_mismatch(chapter, state, world):
    """Whether a chapter's declared entry conditions differ from the projection (cheap probe)."""
    mismatch = []
    for item in _enter_rows(chapter, []) if isinstance(chapter, dict) else []:
        if item['field'] != 'enter':
            continue
        expect = _declared(item['kind'], item['key'], item['expected'], state, world)
        if not _same(item['kind'], expect, _project(state, item['kind'], item['key'])):
            mismatch.append(item)
    return bool(mismatch)


def _normalize_chapter(chapter, state, world, registry=None, hooks=None):
    """A normalized copy of one chapter row: every declared field present, places resolved to ids.

    A node action also carries the definition the volume outline registered for it (its line and
    its dependencies), and a promise action carries the volume's declaration (its text and its
    payoff window), because the settlement event has to freeze both: the writer declares which node
    moved or which promise it touched, the volume outline owns what that promise is and when it may
    be closed.
    """
    normalized = {key: copy.deepcopy(chapter.get(key)) for key in CHAPTER_FIELDS}
    normalized['chapter'] = chapter['chapter']
    normalized['synopsis'] = chapter.get('synopsis')
    plot = chapter.get('plot') if isinstance(chapter.get('plot'), dict) else {}
    nodes = []
    for row in plot.get('nodes') or []:
        if not isinstance(row, dict):
            continue
        definition = (registry or {}).get(row.get('node')) or {}
        row = copy.deepcopy(row)
        row['line'] = (definition.get('line') or definition.get('thread') or definition.get('kind')
                       or row.get('line') or 'main')
        row['depends_on'] = list(definition.get('depends_on') or [])
        nodes.append(row)
    normalized['plot'] = {'beat': plot.get('beat'), 'nodes': nodes,
                          'threads': copy.deepcopy(plot.get('threads') or [])}
    for field in ('resources', 'knowledge', 'characters'):
        normalized[field] = copy.deepcopy(chapter.get(field) or [])
    normalized['places'] = []
    for row in chapter.get('places') or []:
        row = copy.deepcopy(row)
        row['from'] = _place_id(state, world, row.get('from')) if row.get('from') is not None else None
        row['to'] = _place_id(state, world, row.get('to'))
        normalized['places'].append(row)
    clock = chapter.get('clock')
    normalized['clock'] = {'advance_days': clock.get('advance_days') if isinstance(clock, dict) else 0}
    for field in ('enter', 'exit'):
        rows = []
        for row in chapter.get(field) or []:
            row = copy.deepcopy(row)
            kind = _kind_of(row.get('kind'))
            row['kind'] = kind
            row['key'] = _coord_key(kind, row.get('key'))
            if kind == 'places':
                row['expected'] = _place_id(state, world, row.get('expected')) if row.get('expected') is not None else None
            elif kind in ('resources', 'clock'):
                row['expected'] = _number(row.get('expected'))
            rows.append(row)
        normalized[field] = rows
    for field in ('disclosures', 'world_refs', 'new_entities', 'hook_refs', 'reader_refs',
                  'history_refs', 'scenes', 'hooks'):
        normalized[field] = copy.deepcopy(chapter.get(field) or [])
    normalized['pacing'] = copy.deepcopy(chapter.get('pacing') or {})
    normalized['style'] = copy.deepcopy(chapter.get('style') or {})
    normalized['hook_contracts'] = {
        item['hook']: copy.deepcopy((hooks or {}).get(item['hook']) or {})
        for item in normalized['hooks']
        if isinstance(item, dict) and text(item.get('hook'))}
    for field in PROTOCOL_FIELDS:
        if chapter.get(field) is not None:
            normalized[field] = copy.deepcopy(chapter[field])
    return normalized


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
    the four increment arrays, `clock.advance_days`) and the plan-shaped keys the surrounding code
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
                [row.get('entity') for row in chapter.get('places') or [] if isinstance(row, dict)]:
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
            'obligations': [],
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
    if kind in ('node', 'thread'):
        if isinstance(actual, dict) and actual.get('after') in (NODE_STATES if kind == 'node' else THREAD_STATES):
            return None, actual.get('after')
        if actual in (NODE_STATES if kind == 'node' else THREAD_STATES):
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
    if isinstance(number, float):
        if number.is_integer() and abs(number) < 1e15:
            return str(int(number))
        return repr(number)
    return str(number)


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
    delta = (after or 0) - (before or 0)
    if abs(delta) < 1e-9:
        return None
    if delta > 0:
        event = {'op': 'resource', 'from': None, 'to': holder, 'asset': asset, 'unit': unit,
                 'quantity': _amount_string(delta),
                 'to_before': _amount_string(before if before is not None else 0),
                 'reason': reason, 'evidence': evidence}
    else:
        event = {'op': 'resource', 'from': holder, 'to': None, 'asset': asset, 'unit': unit,
                 'quantity': _amount_string(-delta),
                 'from_before': _amount_string(before if before is not None else 0),
                 'reason': reason, 'evidence': evidence}
    return event


def _event_for(kind, key, item, planned, actual_to, actual_from, state, chapter, findings,
               coordinate=None):
    evidence = item.get('evidence')
    detail = planned.get('detail') or {}
    inner = planned.get('planned') if isinstance(planned.get('planned'), dict) else {}
    reason = (item.get('reason') or detail.get('reason') or detail.get('change') or '')
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
    moved, missing evidence); `deviations` are the declared, reasoned departures that are recorded.
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
        if kind == 'disclosure':
            continue
        if kind not in ('node', 'thread', 'hook', 'resources', 'places', 'knowledge', 'characters', 'clock'):
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
                                     '多项：自比行没有对应的章纲增量（计划外变化走 unplanned）。',
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
                         else entry['planned'].get('after') if kind in ('node', 'thread')
                         else entry['planned'].get('to'))
        if status == 'kept' and not _same(kind, actual_to, expected_kept):
            findings.append(_finding(chapter, kind, key, expected_kept, actual_to,
                                     'status=kept 时实际结果必须与章纲声明一致；不符请标 deviated 并说明理由。',
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
                                 '有偏差却声明 clean：要么改回与章纲一致，要么把 verdict 改为 deviated。',
                                 'drift_verdict', 'quality'))
    elif verdict == 'deviated' and not deviations:
        findings.append(_finding(chapter, 'verdict', 'verdict', 'deviated', 'clean',
                                 '声明 deviated 却没有一条偏差：逐条标出 deviated/skipped 并写理由。',
                                 'drift_verdict', 'quality'))
    # 5. Planned disclosures: settled from the outline when the writer filed no explicit row for
    # them, and registered as a deviation so the ledger of what was not self-reported stays visible.
    reported = {}
    for item in items:
        if isinstance(item, dict) and _kind_of(item.get('kind')) == 'disclosure':
            reported[item.get('key')] = item
    declared_disclosures = [row for row in row.get('disclosures') or [] if isinstance(row, dict)]
    if declared_disclosures and not findings:
        quote = None
        for item in items:
            if isinstance(item, dict) and isinstance(item.get('evidence'), dict) \
                    and text(item['evidence'].get('quote')):
                quote = {'chapter': chapter, 'quote': item['evidence']['quote']}
                break
        for disclosure in declared_disclosures:
            topic, after = disclosure.get('topic'), disclosure.get('after')
            if not text(topic) or after not in REVEALS:
                findings.append(_finding(chapter, 'disclosure', topic, 'topic 与 ' + '|'.join(REVEALS), _safe(disclosure),
                                         '章纲的披露需要 topic 与档位。', 'drift_disclosure', 'blocker'))
                continue
            if quote is None:
                findings.append(_finding(chapter, 'disclosure', topic, '正文引文', None,
                                         '披露入账需要正文引文：至少一条自比行要给出原文片段。',
                                         'drift_evidence', 'blocker'))
                continue
            item = reported.get(topic) or {}
            evidence = item.get('evidence') if isinstance(item.get('evidence'), dict) else quote
            if not text((evidence or {}).get('quote')):
                evidence = quote
            before = _project(shadow, 'disclosure', topic)
            if after != 'retracted' and before is not None \
                    and REVEAL_RANK.get(_canonical_reveal(after), 0) < REVEAL_RANK.get(_canonical_reveal(before), 0):
                findings.append(_finding(chapter, 'disclosure', topic, before, after,
                                         '读者认知倒退：除 retracted 外不得退回暗示。',
                                         'drift_disclosure', 'blocker'))
                continue
            events.append({'op': 'reader_knowledge', 'topic': topic, 'before': before, 'after': after,
                           'claim': item.get('claim') or disclosure.get('claim') or (evidence or {}).get('quote'),
                           'evidence': evidence})
            _reduce(shadow, events[-1], chapter, 'disclosure', topic, findings)
            if topic not in reported:
                deviations.append({'chapter': chapter, 'kind': 'disclosure', 'key': topic,
                                   'planned': {'after': after}, 'actual': {'after': after},
                                   'reason': '执笔未逐条自报本章披露，引擎按章纲登记。'})
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
