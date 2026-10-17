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
    'schema': {'owner': 'sqlite_store', 'readers': ('sqlite_store',)},
}
CONTROLLER = 'controller'
OFFICIAL_BRANCH = 'official_branch'
AMENDMENT_BASE = 'amendment_base'
COMPLETION_DELIVERY = 'completion_delivery'
SCHEMA_KEY = 'schema'
# The four-partition root is storage-owned: the concrete store owns the layout
# of the ledger it writes, so this one is declared but built by the adapter.
BOOK_ROOT = 'book'

PREFIXES = ('claim:', 'branch-book:', 'history_head:')

# The journal row an actual read leaves behind. It is written by the application and summed by the
# storage adapter's `usage`, so the shape is declared here instead of being an implicit agreement
# between two layers: renaming `chars` would otherwise make reported usage silently wrong.
READ_RECORD = ('task', 'records', 'chars')


def read_record(task_id, names, chars):
    return {'task': task_id, 'records': list(names), 'chars': chars}


def read_chars(value):
    """The character count of one recorded read, from the declared shape."""
    return value['chars']


def claim(task_id):
    return 'claim:' + task_id


def branch_book(branch):
    return 'branch-book:' + branch


def history_head(ident):
    return 'history_head:' + ident
