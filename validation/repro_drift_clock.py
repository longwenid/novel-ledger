"""Minimal repro: a `kept` clock row is rejected by drift.reconcile.

    python validation/repro_drift_clock.py

Root cause (evidence below): `drift._planned(row)` files the clock's declared days as
`entry['planned']['advance_days']`, and the `status=kept` check reads exactly that
(`drift.py:1439`, `entry['planned'].get('advance_days')`). But `_event_for` reads one level too
high — `planned.get('advance_days')` where `planned` is the whole entry (`drift.py:1312`) — so it
compares the filed result against `None` and raises `drift_clock` for every chapter whose outline
declares a non-zero clock advance. The chapter is then routed to `repair`, spends the budget, and
the book pauses: no chapter with a clock advance can ever commit.

Expected: `findings == []` and one `clock` event.
Actual:   one blocker finding, `expect=None`, `got=1`.
"""
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'scripts')]
from novel_ledger import drift                      # noqa: E402


def row(chapter=1, advance_days=1):
    """A chapter outline row reduced to what the reconciliation actually reads."""
    return {'chapter': chapter, 'synopsis': '工程样本。', 'clock': {'advance_days': advance_days},
            'plot': {'beat': '核对来源。', 'nodes': [], 'threads': []},
            'resources': [], 'places': [], 'knowledge': [], 'characters': [],
            'enter': [], 'exit': [], 'world_refs': [], 'new_entities': [],
            'disclosures': [], 'hook_refs': [], 'reader_refs': [], 'history_refs': [],
            'scenes': [], 'pacing': {}}


def check(advance_days=1):
    """The writer's self-comparison: one kept row per planned coordinate, clock included."""
    return {'items': [{
                'kind': 'clock', 'key': 'clock',
                'planned': {'advance_days': advance_days},
                'actual': {'advance_days': advance_days},
                'status': 'kept', 'reason': '',
                'evidence': {'chapter': 1, 'quote': '次日'}}],
            'unplanned': [], 'verdict': 'clean'}


def main():
    entries = drift._planned(row())
    clock_entry = next(entry for entry in entries if entry['kind'] == 'clock')
    print('1. drift._planned files the clock as:', clock_entry)
    print('2. entry.get(advance_days)     ->', clock_entry.get('advance_days'), ' (what drift.py:1312 reads)')
    print('3. entry["planned"][...]       ->', clock_entry['planned'].get('advance_days'),
          ' (what drift.py:1439 reads)')
    outcome = drift.reconcile(check(), row(), {'clock': 0}, {})
    print('4. drift.reconcile findings    ->', outcome['findings'])
    print('5. events                      ->', outcome['events'])
    return 0 if not outcome['findings'] else 1


if __name__ == '__main__':
    sys.exit(main())
