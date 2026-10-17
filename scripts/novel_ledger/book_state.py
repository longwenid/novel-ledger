"""Persistent ownership boundaries; domains receive an assembled transaction-local view."""
from __future__ import annotations

import copy
from .contracts import require

BOOK_SCHEMA = 'novel-ledger.book/1'
PART_FIELDS = {
    'settings': ('contract', 'contract_source', 'lexical_policy', 'contract_review'),
    'canon': ('state', 'written_han'),
    'intent': ('creation', 'world', 'world_review', 'designs', 'plans', 'profiles',
               'profile_history', 'style_anchor', 'scope_ends', 'understanding'),
    'execution': ('branch', 'revision', 'status', 'target', 'finish', 'pilot', 'draft',
                  'proposal', 'scope_parts', 'reviews', 'rework', 'revision_run', 'feedback',
                  'decisions', 'last_task', 'pause_reason', 'pending_contract',
                  'pending_contract_reviewer', 'contract_draft', 'controller_owner',
                  'opening_world_only', 'run_authorized', 'alignment_hold',
                  'alignment_proposal', 'alignment_history', 'author_block',
                  'author_decision_history', 'carry_findings', 'accepted_findings', 'prior_candidate',
                  'repair_cases', 'remedy_exhausted', 'revision_directive',
                  'scope_findings', 'scope_closures', 'completed_at', 'completion_snapshot')}


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


def check_state(book):
    """Invariants every state transition must leave behind.

    Separate fields that have to move together are how a project ends up `running` while still
    carrying the previous pause reason, or holding findings nobody can see. This is checked on every
    read of the status, so the command that broke it is the command that reports it.
    """
    status = book.get('status')
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
    return book
