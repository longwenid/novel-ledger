"""Persistent ownership boundaries; domains receive an assembled transaction-local view."""
from __future__ import annotations

import copy
from .contracts import require

BOOK_SCHEMA = 'novel-ledger.book/1'
# v2 removed the design-review and plan stages, so their containers are gone with them: the volume
# outlines, the chapter outlines and the rows materialized from them are the whole design record,
# and `design_drift` is the ledger of departures the writer declared and the engine registered.
PART_FIELDS = {
    'settings': ('contract', 'contract_source', 'lexical_policy'),
    'canon': ('state', 'written_han'),
    'intent': ('creation', 'world', 'volumes_outline', 'chapter_outlines', 'plans',
               'style_anchor', 'scope_ends', 'understanding'),
    'execution': ('branch', 'revision', 'status', 'target', 'finish', 'pilot', 'draft',
                  'rework', 'revision_run', 'feedback', 'decisions', 'last_task', 'pause_reason',
                  'pending_contract', 'controller_owner', 'opening_world_only', 'run_authorized',
                  'author_block', 'author_decision_history', 'carry_findings', 'accepted_findings',
                  'prior_candidate', 'repair_cases', 'remedy_exhausted', 'revision_directive',
                  'design_drift', 'completed_at', 'completion_snapshot', 'writing_mode')}


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
    return book
