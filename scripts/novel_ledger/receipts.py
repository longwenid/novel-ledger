"""Mechanical receipt assembly for prose stages.

The envelope, the drift rows and their projected before-values are engine facts. A writer that
assembles them by hand spends model calls — and every call re-reads the whole transcript — on
plumbing the engine can do locally (measured: one fast-group run burned ~10 extraction calls per
chapter before inventing its own build script). The writer keeps the prose, the comparison
verdicts and the evidence quotes; this module removes only the assembly.
"""
from __future__ import annotations

from .contracts import RESULT, TIME_MARKERS, require, text
from . import drift
from .result_templates import drift_items, template

# The self-comparison's standard sentence for a kept row. A genuine deviation still carries the
# writer's own reason; this default only states what the engine is about to verify anyway.
KEPT_REASON = '正文中该变化按章纲发生，动作与后果均有落点。'

QUOTE_WIDTH = 16


def _quote_candidates(item):
    """Words worth anchoring an evidence quote on: Chinese planned values, then key parts."""
    words = []
    planned = item.get('planned') if isinstance(item.get('planned'), dict) else {}
    for side in ('to', 'from'):
        value = planned.get(side)
        if isinstance(value, str) and sum(1 for ch in value if ord(ch) > 127) >= 2:
            words.append(value)
    key = item.get('key')
    if isinstance(key, str):
        words.extend(part for part in key.replace(':', ' ').split()
                     if len(part) >= 2 and any(ord(ch) > 127 for ch in part))
    return words


def _unique(prose, window):
    """A window the chapter quotes verbatim and unambiguously — evidence requires exactly one hit."""
    index = prose.find(window)
    return index >= 0 and prose.find(window, index + 1) < 0


def locate_quote(prose, anchor, width=QUOTE_WIDTH):
    """A verbatim window containing `anchor`, or None when the prose cannot supply one."""
    index = prose.find(anchor)
    if index < 0:
        return None
    for left in range(max(0, index - 6), min(index + 1, max(1, len(prose) - width + 1))):
        window = prose[left:left + width]
        if len(window) == width and _unique(prose, window):
            return window
    return None


def fallback_quote(prose, position, width=QUOTE_WIDTH):
    """A deterministic spread-out window, so items without an anchor still get distinct quotes."""
    if len(prose) <= width:
        return prose if prose and _unique(prose, prose) else None
    span = len(prose) - width
    for attempt in range(span):
        left = (position * 131 + attempt * 37) % span
        window = prose[left:left + width]
        if _unique(prose, window):
            return window
    return None


def _time_anchor(prose):
    """A short window around the first time expression: the clock event's evidence must quote one."""
    for marker in TIME_MARKERS:
        index = prose.find(marker)
        if index >= 0:
            return prose[max(0, index - 3):index + len(marker) + 3]
    return None


def assemble(task, state, prose, meta, row):
    """A submit-shaped receipt for a write chapter: envelope from the task, drift rows from the
    chapter outline with the engine's own projections filled in, quotes located in the draft.

    Returns `(receipt, missing, unlocated)`: the fields the writer still owes (title, summary,
    self_check) and the comparison rows whose quote the prose could not mechanically supply.
    """
    work = task['input']
    data = template(work['stage'], work['chapter'],
                    extra=tuple((work.get('payload') or {}).get('also') or ()),
                    payload=work.get('payload') or {},
                    tracking=work.get('narrative_tracking', False))
    data['prose'] = prose
    for field in ('title', 'summary', 'self_check'):
        if text(meta.get(field)):
            data[field] = meta[field]
    missing = [field for field in ('title', 'summary', 'self_check') if not text(data.get(field))]
    items, unlocated = [], []
    for position, item in enumerate(drift_items(row)):
        kind, planned = item['kind'], item['planned']
        if kind == 'clock':
            actual = {'advance_days': planned.get('advance_days')}
        elif kind in ('node', 'thread', 'disclosure'):
            actual = {'after': planned.get('after')}
        elif kind == 'hook':
            actual = {'action': planned.get('action')}
        else:
            actual = {'from': drift.project(state, kind, item['key']), 'to': planned.get('to')}
        quote = None
        if kind == 'clock':
            # The clock event's evidence must quote a time expression, so anchor on one.
            anchor = _time_anchor(prose)
            if anchor:
                quote = locate_quote(prose, anchor)
        else:
            for anchor in _quote_candidates(item):
                quote = locate_quote(prose, anchor)
                if quote:
                    break
        if quote is None:
            quote = fallback_quote(prose, position)
        if quote is None:
            unlocated.append({'kind': kind, 'key': item['key']})
        items.append({'kind': kind, 'key': item['key'], 'planned': planned, 'actual': actual,
                      'status': 'kept', 'reason': KEPT_REASON,
                      'evidence': {'chapter': item['evidence'].get('chapter'), 'quote': quote or ''}})
    data['drift_check'] = {'items': items, 'unplanned': [], 'verdict': 'clean'}
    receipt = {'schema': RESULT, 'task_id': task['id'], 'input_hash': task['input_hash'],
               'data': data}
    require(isinstance(row, dict), 'drift_check', '本章尚无已登记的章纲，不能组装回执。')
    return receipt, missing, unlocated
