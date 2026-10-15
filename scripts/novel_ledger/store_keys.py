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
}
CONTROLLER = 'controller'
OFFICIAL_BRANCH = 'official_branch'
AMENDMENT_BASE = 'amendment_base'
COMPLETION_DELIVERY = 'completion_delivery'
# The four-partition root is storage-owned: the concrete store owns the layout
# of the ledger it writes, so this one is declared but built by the adapter.
BOOK_ROOT = 'book'

PREFIXES = ('claim:', 'branch-book:', 'history_head:')


def claim(task_id):
    return 'claim:' + task_id


def branch_book(branch):
    return 'branch-book:' + branch


def history_head(ident):
    return 'history_head:' + ident
