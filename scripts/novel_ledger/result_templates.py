"""Blank worker results. Presentation shapes do not participate in domain decisions.

Every skeleton starts from empty values with the complete field set of its stage, so a worker never
has to read engine source to learn a shape. The one place a blank form carries data is the writer's
`drift_check`: the chapter outline already declared which deltas this chapter must produce, and
pre-filling one empty item per planned delta is what turns "self-check" from a free paragraph into a
line-by-line comparison the engine can reconcile.
"""
from __future__ import annotations

from .contracts import contract_skeleton, require, text
from .world import SECTIONS
from . import stages


def _drift_item(kind, key, planned, chapter=''):
    """One planned delta as a blank self-comparison row: only the plan side is pre-filled.

    `actual` starts as null rather than an empty object: the writer either fills it with what the
    prose actually did, or leaves it null and marks the row skipped. The engine projects the true
    before-value itself, so the writer never has to guess it.
    """
    return {'kind': kind, 'key': key, 'planned': planned, 'actual': None,
            'status': '', 'reason': '', 'evidence': {'chapter': chapter, 'quote': ''}}


def _knowledge_key(entry):
    """A knowledge delta's identity is who learns what, so both halves name the item."""
    parts = [entry.get('who'), entry.get('topic')]
    return ':'.join(part for part in parts if text(part))


def drift_items(row):
    """The chapter outline's planned deltas, one blank comparison row each.

    The list mirrors the coverage coordinates the reconciliation derives from the same row — same
    kinds, same keys, same order, same skip rules (a malformed entry that names no coordinate is not
    a coordinate) and the clock row is always present because the engine always expects it. A form
    that listed one row fewer than the engine expects would make a diligent writer fail coverage for
    a row nobody handed them.
    """
    row = row or {}
    plot = row.get('plot') if isinstance(row.get('plot'), dict) else {}
    chapter = row.get('chapter', '')
    items = []
    for node in plot.get('nodes') or []:
        if isinstance(node, dict) and text(node.get('node')):
            items.append(_drift_item('node', node['node'], {'after': node.get('after')}, chapter))
    for thread in plot.get('threads') or []:
        if isinstance(thread, dict) and text(thread.get('thread')):
            items.append(_drift_item('thread', thread['thread'], {'after': thread.get('after')}, chapter))
    for entry in row.get('resources') or []:
        if isinstance(entry, dict) and text(entry.get('key')):
            items.append(_drift_item('resources', entry['key'],
                                     {'from': entry.get('from'), 'to': entry.get('to')}, chapter))
    for entry in row.get('places') or []:
        if isinstance(entry, dict) and text(entry.get('entity')):
            items.append(_drift_item('places', entry['entity'],
                                     {'from': entry.get('from'), 'to': entry.get('to')}, chapter))
    for entry in row.get('knowledge') or []:
        if isinstance(entry, dict) and text(entry.get('who')) and text(entry.get('topic')):
            items.append(_drift_item('knowledge', _knowledge_key(entry),
                                     {'from': entry.get('from'), 'to': entry.get('to')}, chapter))
    for entry in row.get('characters') or []:
        if isinstance(entry, dict) and text(entry.get('entity')):
            items.append(_drift_item('characters', entry['entity'],
                                     {'from': entry.get('from'), 'to': entry.get('to')}, chapter))
    clock = row.get('clock') if isinstance(row.get('clock'), dict) else {}
    items.append(_drift_item('clock', 'clock', {'advance_days': clock.get('advance_days') or 0}, chapter))
    return items


def volume_row(ident):
    """One volume of a blank volume outline: every §3 field present, all values empty."""
    return {'id': ident, 'purpose': '', 'arc': '', 'turns': [{'at': '', 'turn': ''}], 'climax': '',
            'nodes': [], 'threads': [], 'resources': [], 'places': [], 'characters': [],
            'knowledge': [], 'clock': {'advance_days': 0}, 'exit_state': ''}


def chapter_row(number, volume=None):
    """One blank chapter outline row: the required fields plus the four declared delta arrays.

    The arrays are empty rather than absent on purpose: an empty array is the declaration "nothing
    of this kind changes in this chapter", which is a claim the state chain can check, while a
    missing field is nothing to check at all.
    """
    row = {'chapter': number, 'synopsis': '',
           'plot': {'beat': '', 'nodes': [], 'threads': []},
           'resources': [], 'places': [], 'knowledge': [], 'characters': [],
           'clock': {'advance_days': 0},
           'enter': [], 'exit': [],
           'disclosures': [], 'world_refs': [], 'new_entities': [],
           'hook_refs': [], 'reader_refs': [], 'history_refs': [],
           'scenes': [], 'pacing': {},
           # Optional workbench protocol: the template states the keys so a writer who declares a
           # full reading dependency knows the names, and 'partial' keeps the conservative default
           # for everyone who does not. Empty here means "nothing declared", not "nothing depends".
           'dependency_coverage': 'partial', 'reading_coverage': 'partial',
           'reading_refs': [], 'understanding_refs': []}
    return row


def _policy(payload, key):
    """The batch policy of an outline dispatch, from either place the engine carries it.

    `payload[key]` is the policy map the compiler writes; the top-level keys are accepted too so a
    hand-built dispatch (or a test) mints the same form instead of an empty one.
    """
    policy = payload.get(key)
    return policy if isinstance(policy, dict) else {}


def _volume_span(payload, ident):
    """One volume's first/last chapter, read off the merged dispatch's chapter policy."""
    row = next((v for v in _policy(payload, 'chapter_outline').get('volumes') or []
                if v.get('id') == ident), None)
    return (row or {}).get('first', 1) or 1, (row or {}).get('last', 0) or 0


def template(stage, chapter, extra=(), payload=None, tracking=False):
    """The blank result for a stage. `extra` carries stages a combined dispatch also answers."""
    stages.require_stage(stage)
    payload = payload or {}
    if stage == 'opening_options':
        return {'gate': '', 'options': []}
    if stage == 'world_model':
        skeleton = {'selection_hash': '', 'premise': '', 'story_capacity': '',
                    **{k: [{'id': '', **{field: '' for field in fields}, 'links': []}] for k, fields in SECTIONS.items()}}
        if extra and 'opening_contract' in extra:
            # One dispatch drafts the world and the contract it implies: the contract is a reading
            # of selections plus that world, so it belongs in the same cold session.
            return {**skeleton, 'contract': contract_skeleton()}
        return skeleton
    if stage == 'opening_contract':
        return contract_skeleton()
    if stage == 'volume_outline':
        # The missing volumes the batch answers are named by the dispatch; the skeleton is one
        # complete row per volume so a receipt cannot answer half a volume and leave the rest to
        # be inferred. On the tiers that merge, the same receipt also carries each volume's chapter
        # outlines, keyed by volume id.
        policy = _policy(payload, 'volume_outline')
        ids = payload.get('volume_ids') or policy.get('volume_ids') or []
        skeleton = {'volumes': [volume_row(ident) for ident in ids]}
        if 'chapter_outline' in (payload.get('also') or ()):
            skeleton['chapters'] = {}
            for ident in ids:
                first, last = _volume_span(payload, ident)
                skeleton['chapters'][ident] = [chapter_row(number) for number in range(first, last + 1)]
        return skeleton
    if stage == 'chapter_outline':
        policy = _policy(payload, 'chapter_outline')
        first = policy.get('first', payload.get('first', 0)) or 0
        last = policy.get('last', payload.get('last', -1))
        volume = policy.get('volume') or payload.get('volume') or ''
        return {'volume': volume,
                'chapters': [chapter_row(number) for number in range(first, (last if isinstance(last, int) else -1) + 1)]}
    if stage in ('write', 'repair', 'redesign'):
        # The planned deltas of this chapter, one blank row each. `actual` starts empty because the
        # engine already knows the true before-state: a writer that reported its own `from` would be
        # checked against the projection anyway, so guessing it is pure waste.
        row = payload.get('chapter_outline') or {}
        return {'title': '', 'prose': '', 'summary': '',
                'drift_check': {'items': drift_items(row), 'unplanned': [], 'verdict': ''},
                'self_check': ''}
    require(False, 'stage_template', '阶段已登记但没有结果骨架，属引擎缺陷。',
            {'stage': stage, 'known': sorted(stages.STAGES)})
