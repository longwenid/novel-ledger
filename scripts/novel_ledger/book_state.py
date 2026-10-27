"""Persistent ownership boundaries; domains receive an assembled transaction-local view."""
from __future__ import annotations

import copy
from .contracts import BLUEPRINT_CATALOG, require

BOOK_SCHEMA = 'novel-ledger.book/1'
# v2 removed the design-review and plan stages, so their containers are gone with them: the volume
# outlines, the chapter outlines and the rows materialized from them are the whole design record,
# and `design_drift` is the ledger of departures the writer declared and the engine registered.
# The volume-outline confirmation gate adds three book-level fields: `pending_design` (the staged,
# validated-but-not-installed batch, merged chapter half included), `volume_gate` (its round,
# reasoned refusals and confirmations) and `structure_blueprint` (the author's optional book-level
# structural choice). All three are absent-by-default legal, so an in-flight project predating the
# gate needs no migration.
PART_FIELDS = {
    'settings': ('contract', 'contract_source', 'lexical_policy'),
    'canon': ('state', 'written_han'),
    'intent': ('creation', 'world', 'volumes_outline', 'chapter_outlines', 'plans',
               'style_anchor', 'scope_ends', 'understanding',
               'pending_design', 'volume_gate', 'structure_blueprint'),
    'execution': ('branch', 'revision', 'status', 'target', 'finish', 'pilot', 'draft',
                  'rework', 'revision_run', 'feedback', 'decisions', 'last_task', 'pause_reason',
                  'pending_contract', 'controller_owner', 'opening_world_only', 'run_authorized',
                  'author_block', 'author_decision_history', 'carry_findings', 'accepted_findings',
                  'prior_candidate', 'repair_cases', 'remedy_exhausted', 'revision_directive',
                  'design_drift', 'completed_at', 'completion_snapshot', 'writing_mode',
                  'writing_batch_chapters')}


def split(book):
    allowed = {key for fields in PART_FIELDS.values() for key in fields}
    require(isinstance(book, dict) and not set(book) - allowed, 'book_ownership',
            '项目字段必须声明持久化归属。', {'unknown_fields': sorted(set(book) - allowed) if isinstance(book, dict) else []})
    return {name: {key: copy.deepcopy(book[key]) for key in fields if key in book}
            for name, fields in PART_FIELDS.items()}


def assemble(parts):
    require(set(parts) == set(PART_FIELDS), 'book_integrity', '项目分区不完整。')
    result = {}
    for name, value in parts.items():
        require(isinstance(value, dict) and set(value) <= set(PART_FIELDS[name]),
                'book_integrity', '项目分区包含越界字段。', {'part': name})
        result.update(copy.deepcopy(value))
    return result


STATUSES = ('preparing', 'running', 'paused', 'completed')
FINDING_BATCH_FIELDS = ('stage', 'scope', 'findings')
# A design-drift row is what the engine registered when the prose did not follow the outline: it
# carries the coordinate, what was planned, what actually happened, and the writer's reason.
DRIFT_FIELDS = ('chapter', 'kind', 'key', 'reason')


def check_state(book):
    """Invariants every state transition must leave behind.

    Separate fields that have to move together are how a project ends up `running` while still
    carrying the previous pause reason, or holding findings nobody can see. This is checked on every
    read of the status, so the command that broke it is the command that reports it.
    """
    status = book.get('status')
    require(book.get('writing_mode', 'standard') in ('standard', 'fast'), 'book_state', '未知写作模式。')
    batch = book.get('writing_batch_chapters')
    require(batch is None or type(batch) is int and batch > 0, 'book_state',
            '连写组章数须为正整数（run --batch N）。')
    require(isinstance(book.get('rework'), dict), 'book_state',
            '返修额度记录缺失或损坏，禁止把缺失解释为未消耗。')
    require(status in STATUSES, 'book_state', '未知的项目状态。', {'status': status, 'known': list(STATUSES)})
    reason = book.get('pause_reason')
    require(status != 'running' or not reason, 'book_state',
            '项目在运行却带着暂停原因：暂停原因必须与状态一起改。', {'pause_reason': reason})
    require(status != 'paused' or (isinstance(reason, str) and reason.strip()), 'book_state',
            '项目已暂停却没有暂停原因。')
    for batch in book.get('accepted_findings') or []:
        require(isinstance(batch, dict) and all(key in batch for key in FINDING_BATCH_FIELDS)
                and isinstance(batch['findings'], list), 'book_state',
                '作者接受过的条目必须说明阶段、范围与具体意见。', {'batch': sorted(batch) if isinstance(batch, dict) else None})
    draft = book.get('draft')
    require(draft is None or (isinstance(draft, dict) and type(draft.get('chapter')) is int and draft['chapter'] >= 1),
            'book_state', '候选稿必须指向一个章号。')
    # A registered departure without a reason would be a silent rewrite of the outline: the writer
    # declares it in `drift_check`, and the reason is what makes it reviewable later.
    for row in book.get('design_drift') or []:
        require(isinstance(row, dict) and all(key in row for key in DRIFT_FIELDS)
                and isinstance(row['reason'], str) and row['reason'].strip(), 'book_state',
                '与章纲不符的登记项必须说明章号、坐标与理由。',
                {'row': sorted(row) if isinstance(row, dict) else None})
    for volume_id, outline in (book.get('volumes_outline') or {}).items():
        require(isinstance(outline, dict) and outline.get('id') == volume_id
                and isinstance(outline.get('nodes'), list) and isinstance(outline.get('threads'), list),
                'book_state', '卷纲登记须按卷 ID 保存完整行。', {'volume': volume_id})
    for volume_id, rows in (book.get('chapter_outlines') or {}).items():
        require(isinstance(rows, list)
                and all(isinstance(row, dict) and type(row.get('chapter')) is int for row in rows),
                'book_state', '章纲登记须按卷保存章行数组。', {'volume': volume_id})
    # The staged half of the confirmation gate. Its shape invariant is what makes "not installed
    # yet" a structural fact rather than a flag: the volumes are whole validated rows, the merged
    # chapter half is either absent or whole per-volume rows, and the id list names exactly the
    # volumes the author is being asked about.
    pending = book.get('pending_design')
    if pending is not None:
        require(isinstance(pending, dict) and isinstance(pending.get('volumes'), dict)
                and pending['volumes'] and isinstance(pending.get('volume_ids'), list)
                and pending['volume_ids'] and isinstance(pending.get('plans'), dict)
                and (pending.get('chapters') is None or isinstance(pending.get('chapters'), dict))
                and isinstance(pending.get('scope'), str) and pending['scope']
                and isinstance(pending.get('volumes_hash'), str) and pending['volumes_hash']
                and type(pending.get('round')) is int and pending['round'] >= 0,
                'book_state', '暂存卷纲须携带完整形状：卷行、卷清单、策略、哈希、轮次与合并半体。',
                {'pending': sorted(pending) if isinstance(pending, dict) else None})
        require(set(pending['volumes']) == set(pending['volume_ids']),
                'book_state', '暂存卷纲的卷清单须与卷行一致。')
    gate = book.get('volume_gate')
    require(gate is None or (isinstance(gate, dict) and type(gate.get('round')) is int
                             and isinstance(gate.get('rejections'), list)
                             and isinstance(gate.get('confirmed'), dict)),
            'book_state', '卷纲门记录须为 {round, rejections, confirmed} 形状。')
    blueprint = book.get('structure_blueprint')
    require(blueprint is None or (isinstance(blueprint, dict) and set(blueprint) <= {'name', 'source'}
                                  and isinstance(blueprint.get('name'), str)
                                  and blueprint['name'] in BLUEPRINT_CATALOG
                                  and isinstance(blueprint.get('source'), str) and blueprint['source']),
            'book_state', '结构蓝图须为 {name, source}，name 取自内置蓝图目录。')
    return book
