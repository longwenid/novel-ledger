"""Pure editorial decisions: revision bounds, root remedies and the contract's book view.

v2 removed every editorial path that existed to arbitrate a review receipt — alignment holds,
scope closure and remedy review all consumed an independent reader's findings, and there is no
independent reader any more. What is left is mechanical: the contract as the book sees it, the
bound a revision must stay inside, the hash that freezes a design context, and the root-case
bookkeeping an author-granted remedy round is recorded in.
"""
from __future__ import annotations

import copy
from .contracts import digest, require, text

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
    """The window a revision may reach back over, and the volumes it is already past.

    A volume counts as closed once every chapter of it is written: the old closure receipt that
    used to say so is gone with the review stage, and the fact it recorded is the chapter count.
    """
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
    """The design context a frozen revision directive is bound to.

    v2's design record is the volume outlines, the chapter outlines derived from them, and the rows
    materialized for settlement; a directive that names a hash of anything else would not notice the
    design moving under it.
    """
    return digest({k: book.get(k) for k in ('contract', 'volumes_outline', 'chapter_outlines',
                                           'style_anchor', 'scope_ends')})


def root_case(book, data, scope, evidence, chapter):
    """Record one author-scoped remedy round against a stable root, and return its case id."""
    value = data.get('repair_case')
    require(isinstance(value, dict) and all(text(value.get(k)) for k in ('root_ref', 'goal', 'verification_condition')),
            'repair_case', '修复需 repair_case={root_ref,goal,verification_condition,evidence}，root_ref 使用稳定问题来源。')
    ref = evidence(value.get('evidence'))
    cases = book.setdefault('repair_cases', {})
    # An unresolved scope has one stable root. A new label cannot reset the existing allowance.
    active = [(k, c) for k, c in cases.items() if c['scope'] == scope and c['status'] != 'resolved']
    key = digest({'scope': scope, 'root_ref': value['root_ref']})
    require(not active or any(k == key for k, c in active), 'repair_case', '本范围尚有未解决根问题，不能换来源文字重开额度。',
            {'active': [k for k, c in active], 'recover': '沿原 repair_case.root_ref 和目标提出下一轮实质方案。'})
    case = cases.setdefault(key, {'root_ref': value['root_ref'], 'scope': scope, 'goal': value['goal'],
                                 'verification_condition': value['verification_condition'], 'rounds': [], 'status': 'open'})
    require(case['goal'] == value['goal'] and case['verification_condition'] == value['verification_condition'],
            'repair_case', '未解决的原目标与验收条件不能被新措辞替换。')
    mechanism = data.get('remedy')
    require(isinstance(mechanism, dict) and all(text(mechanism.get(k)) for k in ('mechanism', 'substantive_change')),
            'remedy', 'remedy 需 mechanism/substantive_change，说明本轮如何修好。')
    require(len(case['rounds']) < 2, 'remedy_exhausted', '根问题两轮方案已耗尽，保留最后验收和原目标。', {'case_id': key, 'recover': '请求作者针对原问题作具体裁决，不 resume 重发。'})
    fingerprint = digest(mechanism)
    require(not case['rounds'] or case['rounds'][-1]['mechanism_hash'] != fingerprint, 'remedy', '原样方案不能作为新一轮修复。')
    round_id = digest({'case': key, 'round': len(case['rounds']) + 1, 'mechanism': mechanism})
    case['rounds'].append({'id': round_id, 'mechanism_hash': fingerprint, 'proposal': copy.deepcopy(mechanism),
                           'evidence': ref, 'chapter': chapter, 'status': 'pending'})
    case['status'] = 'open'
    return key
