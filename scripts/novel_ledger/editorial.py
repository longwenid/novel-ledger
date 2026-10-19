"""Effective contract, revision bounds and frozen design identity."""
from __future__ import annotations

import copy
from .contracts import digest

REVISION_BOUNDS = 'revision-bounds/1'
# A revision that reaches further back than the caller's contract allows is an author decision, not
# an engine one; the default matches the contract's own legacy window when a project declares none.
REVISION_LIMIT_DEFAULT = 3


def enabled(book):
    return bool((book.get('contract') or {}).get('editorial_features'))


def effective_contract(book):
    value = copy.deepcopy(book['contract'])
    first = 1
    for volume in value['volumes']:
        volume['first'] = first
        volume['end'] = book.get('scope_ends', {}).get(volume['id'], volume['end'])
        first = volume['end'] + 1
    return value


def revision_policy(book, head):
    """Recent revision window and volumes whose chapters are all written."""
    contract = effective_contract(book)
    limit = book['contract'].get('planning_window') or REVISION_LIMIT_DEFAULT
    return {'schema': REVISION_BOUNDS, 'head': head, 'limit': limit,
            'earliest': max(1, head - limit + 1),
            'closed_volumes': [{'id': v['id'], 'first': v['first'], 'last': v['end']}
                               for v in contract['volumes'] if v['end'] <= head]}


def revision_violations(policy, impact):
    first, last = impact['first'], impact['last']
    result = []
    if first < policy['earliest']:
        result.append('outside_recent_window')
    if last - first + 1 > policy['limit']:
        result.append('rewrite_limit')
    if any(first <= v['last'] and last >= v['first'] for v in policy['closed_volumes']):
        result.append('closed_volume')
    return result


def context_hash(book):
    """Bind revision directives to the contract, outlines and style anchor."""
    return digest({k: book.get(k) for k in ('contract', 'volumes_outline', 'chapter_outlines',
                                           'style_anchor', 'scope_ends')})
