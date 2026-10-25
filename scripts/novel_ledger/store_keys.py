"""Declared kv keys shared by application services and adapters.

The key space is part of the application's data contract, not of a concrete
store: a bare ``'claim:' + task_id`` inside an adapter would make the layout
below the port. Keys are therefore built only here, and a guard test rejects
new literals elsewhere.
"""
from __future__ import annotations

# Fixed keys: one row per key, with the writer and the readers named so a new
# consumer is an explicit decision rather than an accidental discovery.
KEYS = {
    'controller': {'owner': 'application', 'readers': ('application',)},
    'official_branch': {'owner': 'application', 'readers': ('application', 'delivery')},
    'amendment_base': {'owner': 'application', 'readers': ('contract_activation',)},
    'completion_delivery': {'owner': 'application', 'readers': ('application',)},
    'writing_batch': {'owner': 'writing_service', 'readers': ('writing_service',)},
    'schema': {'owner': 'sqlite_store', 'readers': ('sqlite_store',)},
    'assurance_policy': {'owner': 'governance', 'readers': ('governance',)},
    'governance_checkpoint': {'owner': 'governance', 'readers': ('governance',)},
}
CONTROLLER = 'controller'
OFFICIAL_BRANCH = 'official_branch'
AMENDMENT_BASE = 'amendment_base'
COMPLETION_DELIVERY = 'completion_delivery'
WRITING_BATCH = 'writing_batch'
SCHEMA_KEY = 'schema'
ASSURANCE_POLICY = 'assurance_policy'
GOVERNANCE_CHECKPOINT = 'governance_checkpoint'
# The four-partition root is storage-owned: the concrete store owns the layout
# of the ledger it writes, so this one is declared but built by the adapter.
BOOK_ROOT = 'book'

PREFIXES = ('claim:', 'branch-book:', 'history_head:', 'technical_failure:', 'execution_reads:', 'task_outcome:',
            'authorization:', 'continuity_review:', 'pending_review:', 'review_candidates:', 'content_rounds:',
            'world_rejection:')

# The journal row an actual read leaves behind. It is written by the application and summed by the
# storage adapter's `usage`, so the shape is declared here instead of being an implicit agreement
# between two layers: renaming `chars` would otherwise make reported usage silently wrong.
READ_RECORD = ('task', 'records', 'chars')
READ_RECORD_OPTIONAL = ('execution_id', 'record_hashes')


def read_record(task_id, names, chars, *, execution_id=None, record_hashes=None):
    value = {'task': task_id, 'records': list(names), 'chars': chars}
    if execution_id is not None:
        value['execution_id'] = execution_id
    if record_hashes is not None:
        value['record_hashes'] = dict(record_hashes)
    return value


def read_chars(value):
    """The character count of one recorded read, from the declared shape."""
    return value['chars']


def claim(task_id):
    return 'claim:' + task_id


def technical_failure(task_id):
    return 'technical_failure:' + task_id


def execution_reads(execution_id):
    return 'execution_reads:' + execution_id


def content_rounds(task_id):
    return 'content_rounds:' + task_id


def world_rejection(task_id):
    """The world candidate this task refused, staged with its findings for a narrow repair.

    Owner and reader are both the application: it writes the refusal after the refused submit
    rolled back, serves it as the task's `previous_proposal` record on read, compares the next
    submission against it, and clears it the moment a candidate is accepted. No key means no
    refusal to build on — the first dispatch and every fresh task start from a clean slate.
    """
    return 'world_rejection:' + task_id


def task_outcome(task_id):
    return 'task_outcome:' + task_id


def authorization(nonce):
    return 'authorization:' + nonce


def continuity_review(ident):
    return 'continuity_review:' + ident


def pending_review(task_id):
    return 'pending_review:' + task_id


def review_candidates(task_id):
    return 'review_candidates:' + task_id


def branch_book(branch):
    return 'branch-book:' + branch


def history_head(ident):
    return 'history_head:' + ident
