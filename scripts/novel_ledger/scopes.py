"""Bounded review trees; every parent covers frozen, contiguous child reports."""
from __future__ import annotations

from .contracts import CHECKS_VERSION, Job, digest, require, text

HANDOFF_FIELDS = ('causal_bridge', 'thread_changes', 'character_changes', 'disclosures', 'rhythm', 'open_questions')


def tree(headers, first, last, chunk, fanout, version=CHECKS_VERSION, context=None):
    leaves = []
    for start in range(first, last + 1, chunk):
        end = min(last, start + chunk - 1)
        part = {'first': start, 'last': end, 'level': 0, 'children': []}
        part['part_id'] = digest({'checks_version': version, 'span': [start, end], 'chain': [h['chain'] for h in headers if start <= h['n'] <= end],
                                 **({'context': context} if context else {})})
        leaves.append(part)
    result, level = list(leaves), leaves
    while len(level) > 1 or level[0]['level'] == 0:
        parents = []
        for offset in range(0, len(level), fanout):
            children = level[offset:offset + fanout]
            part = {'first': children[0]['first'], 'last': children[-1]['last'], 'level': children[0]['level'] + 1,
                    'children': [c['part_id'] for c in children]}
            part['part_id'] = digest({'level': part['level'], 'children': part['children']})
            parents.append(part)
        result.extend(parents)
        level = parents
    return result


def reports(book):
    result = {p['part_id']: p for parts in book['scope_parts'].values() for p in parts if 'part_id' in p}
    result.update({p['part_id']: p for p in book['reviews'].values() if 'part_id' in p})
    return result


def next_review(book, headers, scope, first, last, key, chunk=None):
    contract = book['contract']
    parts = tree(headers, first, last, contract['review_chunk'] if chunk is None else chunk,
                 contract['review_fanout'], context=key if contract.get('editorial_features') else None)
    existing = reports(book)
    for part in parts:
        # A root always needs its own scope acceptance even when its complete tree is reusable.
        root = part is parts[-1]
        if part['part_id'] in existing and not root:
            continue
        return Job('scope_synthesis' if part['level'] else 'scope_review', last, scope, part['first'], part['last'],
                   {'review_key': key, 'scope_first': first, 'scope_last': last, 'review_tree': True, 'root': root, **part})


def validate_handoff(data, sources, evidence):
    handoff = data.get('handoff')
    require(isinstance(handoff, dict) and all(text(handoff.get(k)) and len(handoff[k]) <= 800 for k in HANDOFF_FIELDS),
            'scope_handoff', 'handoff 六项须具体且每项不超过 800 字；无变化/疑点时说明依据。')
    refs = handoff.get('evidence')
    require(isinstance(refs, list) and 1 <= len(refs) <= 8 and all(isinstance(r, dict) and text(r.get('quote')) and len(r['quote']) <= 240 for r in refs),
            'scope_handoff', 'handoff.evidence 为 1～8 条原文证据，每条引文最多 240 字，完整原文保留补读。')
    return {**handoff, 'evidence': [evidence(r, sources) for r in refs]}


def digest_report(report):
    return {k: report[k] for k in ('part_id', 'first', 'last', 'level', 'children', 'handoff')}
