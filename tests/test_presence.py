"""The mechanical half of semantic fulfillment: declared on-stage characters must surface.

The engine refuses to judge prose quality, but "the plan says this character appears and the
prose never names them" is checkable arithmetic. These tests pin the three behaviors that
matter: a named miss is recorded as a note, a present name is silent, and an id the world
model does not name is skipped rather than guessed at. Budget neutrality (no repair charge,
no refusal) is what separates the observation from a judgment.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from novel_ledger import drift_reconcile

PLAN = {'chapter': 1, 'characters': [
    {'entity': 'shen', 'from': {}, 'to': {}},
    {'entity': 'unknown-id', 'from': {}, 'to': {}},
    'not-a-dict',
]}
WORLD = {'characters': [
    {'id': 'shen', 'name': '沈青梧', 'role': '主角'},
    {'id': 'no-name-record'},
]}


class PresenceNoteTests(unittest.TestCase):
    def test_a_declared_character_missing_from_prose_is_one_note(self):
        notes = drift_reconcile.presence_notes(PLAN, WORLD, '黑市门口站着一个女人。')
        self.assertEqual(len(notes), 1)
        note = notes[0]
        self.assertEqual(note['criterion'], 'presence')
        self.assertEqual(note['severity'], 'note')
        self.assertEqual(note['name'], '沈青梧')
        self.assertEqual(note['kind'], 'characters')

    def test_a_present_name_is_silent_and_unresolvable_ids_are_skipped(self):
        notes = drift_reconcile.presence_notes(PLAN, WORLD, '沈青梧走进黑市，没人抬头。')
        self.assertEqual(notes, [])

    def test_malformed_inputs_observe_nothing_rather_than_raise(self):
        self.assertEqual(drift_reconcile.presence_notes(None, None, ''), [])
        self.assertEqual(drift_reconcile.presence_notes(PLAN, 'not-a-dict', '正文'), [])


if __name__ == '__main__':
    unittest.main()
