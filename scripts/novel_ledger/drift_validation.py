"""Mechanical validation of volume and chapter outlines: field shape, ladder stages, length
policy, declared deltas/enter rows and the normalized chapter shape simulated before prose."""
from __future__ import annotations

from .continuity import timeline_findings

import copy

from .contracts import han_count, require, text
from .entities import register as register_entity

from .drift import CHAPTER_FIELDS, EXPRESSION_FIELDS, HOOK_ACTIONS, PROTOCOL_FIELDS, REVEALS, VOLUME_FIELDS, _coord_key, _declared, _deltas, _enter_rows, _entity_ids, _finding, _kind_of, _number, _place_id, _project, _reject, _resource_known, _safe, _same, _window, _world_ids, _world_index
from .drift_simulation import _hook_registry, _node_registry, _thread_registry, simulate
from . import drift, entities, world


# ------------------------------------------------------- outline validation
def _deep_han(value):
    # One implementation, in drift beside the field tables it counts over: the confirmation board
    # quotes volume lengths through the same walk, so the author's number is the validator's number.
    return drift.deep_han(value)


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
                            state=None):
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
        if not isinstance(volume_style, dict) or not text(volume_style.get('trend')):
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
                or type(clock.get('to')) is not int or clock['to'] < 0:
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
                findings.append(_finding(chapter_no, 'resources', key,
                                         '{key,from,to,reason}；from/to 数值', _safe(row),
                                         '卷纲资源需要 key、from/to 数值与原因。资源坐标须先在约定 initial_resources '
                                         '或既有状态里登记，卷纲/章纲不能凭空确立新资源。', 'volume_reference', 'blocker', 'volume'))
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
                                         '卷纲站位引用了世界模型与既有状态都没有的实体。'
                                         '要写位置变化的实体，先在约定 entities 登记；其实体初始站位在约定 placements 声明'
                                         '——没有初始站位的实体不能建立位置坐标，只能不写它的位置变化。',
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
            if not isinstance(row, dict) or not text(entity) or not structured \
                    or not text(row.get('reason')):
                findings.append(_finding(chapter_no, 'characters', entity,
                                         '{entity,to:{desire,stance,relationship_focus},reason}', _safe(row),
                                         '新卷纲人物终值须用三项当前状态对象声明，并给出原因。',
                                         'volume_reference', 'blocker', 'volume'))
                continue
            if entity not in entities:
                findings.append(_finding(chapter_no, 'characters', entity, '已登记实体', None,
                                         '卷纲人物引用了未登记的实体。', 'volume_reference', 'blocker', 'volume'))
        # The optional terminals: both arrays are legal when absent or empty (declared-then-checked),
        # and a declared row is held to the same registered-entity discipline as the four above.
        for row in volume.get('relations') or []:
            source = row.get('source') if isinstance(row, dict) else None
            target = row.get('target') if isinstance(row, dict) else None
            relation = row.get('key') if isinstance(row, dict) else None
            if not isinstance(row, dict) or not text(source) or not text(target) or source == target \
                    or not text(relation) or any(c in relation for c in ':>') \
                    or not text(row.get('to')) or not text(row.get('reason')):
                findings.append(_finding(chapter_no, 'relations', relation,
                                         '{source,target,key,to,reason}；source≠target，key 不含 : 与 >',
                                         _safe(row),
                                         '卷纲关系终值需要 source/target 两端实体、关系名、to 稳定短词与原因。',
                                         'volume_reference', 'blocker', 'volume'))
                continue
            if source not in entities or target not in entities:
                findings.append(_finding(chapter_no, 'relations', source, '已登记实体', None,
                                         '卷纲关系引用了世界模型与既有状态都没有的实体。',
                                         'volume_reference', 'blocker', 'volume'))
        for row in volume.get('reader_knowledge') or []:
            topic = row.get('topic') if isinstance(row, dict) else None
            if not isinstance(row, dict) or not text(topic) or row.get('to') not in REVEALS \
                    or not text(row.get('reason')):
                findings.append(_finding(chapter_no, 'reader_knowledge', topic,
                                         '{topic,to:' + '|'.join(REVEALS) + ',reason}', _safe(row),
                                         '卷纲读者认知终值需要 topic、to 披露档位与原因；不声明则闭合免检。',
                                         'volume_reference', 'blocker', 'volume'))
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


def validate_chapter_outline(data, policy, volume_row, volume_row_outline, world, state0):
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
    for row in chapters:
        # Retained current rows include derived hook contracts; they are rebuilt from the
        # volume registry below, never trusted as author input.
        unknown = sorted(set(row) - set(CHAPTER_FIELDS) - set(PROTOCOL_FIELDS)
                         - set(EXPRESSION_FIELDS) - {'hook_contracts'})
        require(not unknown, 'chapter_outline', '章纲含当前协议之外的字段，请按当前模板重交。',
                {'chapter': row['chapter'], 'unknown_fields': unknown})
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
    previous_timeline = None
    for position, row in enumerate(chapters):
        chapter_no = row['chapter']
        if row.get('story_events') is not None:
            require(isinstance(row['story_events'], list) and all(text(item) for item in row['story_events']),
                    'chapter_outline', 'story_events只列故事内发生的事件。')
        require(row.get('reader_effect') is None or text(row['reader_effect']), 'chapter_outline',
                'reader_effect只作读者效果注释，不参与事实结算。')
        # The two structural-expression fields are shape-only and optional: a row that gives no
        # beats/role is making no structural claim, exactly like an absent story_events.
        if row.get('beats') is not None:
            require(isinstance(row['beats'], list) and all(text(item) for item in row['beats']),
                    'chapter_outline', 'beats只列本章推进顺序的非空短句，缺省与空数组合法。')
        require(row.get('role') is None or text(row['role']), 'chapter_outline',
                'role只写本章在卷内的结构职责一句话。')
        findings.extend(timeline_findings(row, previous_timeline))
        if (row.get('timeline') or {}).get('relation') not in ('parallel', 'flashback'):
            previous_timeline = row
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
        unknown = [ref for ref in (refs if isinstance(refs, list) else [])
                   if not text(ref) or ref not in world_ids]
        duplicated = len(refs) != len(set(refs)) if isinstance(refs, list) and all(text(r) for r in refs) else False
        if not isinstance(refs, list) or unknown or duplicated:
            sample = '、'.join(sorted(world_ids)[:8]) + ('…' if len(world_ids) > 8 else '')
            findings.append(_finding(chapter_no, 'world_refs', unknown[0] if unknown else 'world_refs',
                                     '世界模型已有记录 ID（例：%s）' % sample, _safe(unknown or refs),
                                     'world_refs 引用了不存在的记录 ID：%s。合法 ID 形如 领域:id，且不重复。'
                                     % ('、'.join(map(str, unknown)) if unknown else '存在重复项'),
                                     'chapter_world', 'blocker', 'outline'))
        plot = row.get('plot')
        chapter_style = row.get('style')
        if chapter_no >= anchor and (not isinstance(chapter_style, dict)
                                     or not all(text(chapter_style.get(k)) for k in ('pov', 'rhythm'))):
            findings.append(_finding(chapter_no, 'style', 'style', '{pov,rhythm:非空文本}',
                                     _safe(chapter_style), '新章纲须声明非空的 style.pov 与 style.rhythm。',
                                     'chapter_style', 'blocker', 'outline'))
        if chapter_no >= anchor and isinstance(chapter_style, dict) and 'dialogue_ratio' in chapter_style:
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
    for field in ('resources', 'knowledge', 'characters', 'relations'):
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
                row['expected'] = _safe(_number(row.get('expected')))
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
    # The optional workbench protocols and the structural-expression fields land only when the
    # author (or the workbench) actually submitted them: a key that lands unconditionally here
    # would change every stored row's digest and break the retained-suffix repair's byte-for-byte
    # comparison in `workflow.py`.
    for field in PROTOCOL_FIELDS + EXPRESSION_FIELDS:
        if chapter.get(field) is not None:
            normalized[field] = copy.deepcopy(chapter[field])
    return normalized
