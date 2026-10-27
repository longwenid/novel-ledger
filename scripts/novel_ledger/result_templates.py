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
    prose actually did. A skipped or deviated row diagnoses a draft that needs prose repair; it
    cannot pass settlement. The engine projects the true before-value itself.
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
    # The promise account: one row per declared plant/payoff. The engine turns each `kept` row into
    # the existing hook event, so the writer's comparison is what settles `state.hooks`. The order
    # follows the engine's own coverage list (plot, then promises, then the state deltas).
    for entry in row.get('hooks') or []:
        if isinstance(entry, dict) and text(entry.get('hook')):
            items.append(_drift_item('hook', entry['hook'], {'action': entry.get('action')}, chapter))
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
    for entry in row.get('relations') or []:
        if isinstance(entry, dict) and text(entry.get('source')) and text(entry.get('target')) \
                and text(entry.get('key')):
            items.append(_drift_item('relations',
                                     entry['source'] + '>' + entry['target'] + ':' + entry['key'],
                                     {'from': entry.get('from'), 'to': entry.get('to')}, chapter))
    clock = row.get('clock') if isinstance(row.get('clock'), dict) else {}
    items.append(_drift_item('clock', 'clock', {'advance_days': clock.get('advance_days') or 0}, chapter))
    for entry in row.get('disclosures') or []:
        if isinstance(entry, dict) and text(entry.get('topic')):
            items.append(_drift_item('disclosure', entry['topic'], {'after': entry.get('after')}, chapter))
    return items


def volume_row(ident):
    """One volume of a blank volume outline: every declared field present, all values empty.

    `hooks` can declare that this volume opens no promise. Style trend and the absolute clock
    terminal must be filled before submission. `stage` is the chosen rung of the opening's ladder; an opening
    that declared no ladder leaves it empty, which is the pre-opening/5 shape. `relations` and
    `reader_knowledge` are the optional terminals: leave them empty to declare no closure check.
    """
    return {'id': ident, 'purpose': '', 'stage': '', 'arc': '', 'turns': [{'at': '', 'turn': ''}], 'climax': '',
            'nodes': [], 'threads': [], 'hooks': [],
            'resources': [], 'places': [], 'characters': [],
            'relations': [], 'reader_knowledge': [],
            'knowledge': [], 'clock': {'advance_days': 0, 'to': None}, 'exit_state': '',
            'style': {'trend': '', 'window': {}}}


def chapter_row(number, volume=None):
    """One blank chapter outline row: the required fields plus the declared delta arrays.

    The template lists every array so a writer checks each kind of change. The validator interprets
    absent or null factual delta arrays just like empty arrays — `relations` included, so a chapter
    with no relation change simply leaves the empty array. Hooks remain an explicit required
    declaration: an empty hooks array says this chapter plants and pays off nothing.
    """
    row = {'chapter': number, 'synopsis': '', 'story_events': [], 'reader_effect': None, 'timeline': None,
           # Optional structural expression. `beats: []` stays an empty-but-present declaration
           # (an empty list is not None, so the conditional landing keeps the key — a row that
           # never fills it digests the same as any other row that submitted the empty array),
           # while `role: None` is dropped by that same conditional and reads exactly like "no
           # claim". Both remain legal to submit untouched.
           'beats': [], 'role': None,
           'plot': {'beat': '', 'nodes': [], 'threads': []},
           'resources': [], 'places': [], 'knowledge': [], 'characters': [],
           'relations': [],
           'clock': {'advance_days': 0},
           'enter': [], 'exit': [],
           'disclosures': [], 'world_refs': [], 'new_entities': [],
           'hooks': [],
           'hook_refs': [], 'reader_refs': [], 'history_refs': [],
           'scenes': [], 'pacing': {},
           'style': {'pov': '', 'rhythm': '', 'notes': ''},
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
                **({'through_chapter': last} if payload.get('allow_retained_suffix') else {}),
                'chapters': [chapter_row(number) for number in range(first, (last if isinstance(last, int) else -1) + 1)]}
    if stage in ('write', 'repair', 'redesign'):
        # The planned deltas of this chapter, one blank row each. `actual` starts empty because the
        # engine already knows the true before-state: a writer that reported its own `from` would be
        # checked against the projection anyway, so guessing it is pure waste.
        row = payload.get('chapter_outline') or {}
        return {'title': '', 'prose': '', 'summary': '',
                'drift_check': {'items': drift_items(row), 'introductions': [], 'unplanned': [], 'verdict': ''},
                'self_check': ''}
    require(False, 'stage_template', '阶段已登记但没有结果骨架，属引擎缺陷。',
            {'stage': stage, 'known': sorted(stages.STAGES)})
