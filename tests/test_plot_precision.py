"""Synthetic temporary-project probes for exact planned and actual continuity."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from novel_ledger import drift, facts, narrative
from novel_ledger.sqlite_store import SQLiteRepository
from support import chapter_rows, contract, seeded_book, volume_rows


RESOURCE = '["shen","车费","元"]'
QUOTE = '沈桐核对了账上的车费，记录下这次变动。'


class ExactContinuityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = SQLiteRepository.initialize(Path(self.temp.name) / 'book', seeded_book(contract(4)))
        self.addCleanup(self.repo.close)
        self.book = self.repo.load()
        self.state = self.book['state']

    def row(self, before='4', after='4.0000000001'):
        return {'chapter': 1, 'plot': {'nodes': [], 'threads': []}, 'hooks': [],
                'resources': [{'key': RESOURCE, 'from': before, 'to': after, 'reason': '账目变动。'}],
                'places': [], 'knowledge': [], 'characters': [], 'clock': {'advance_days': 0},
                'enter': [{'kind': 'resources', 'key': RESOURCE, 'expected': before}],
                'exit': [{'kind': 'resources', 'key': RESOURCE, 'expected': after}]}

    def check(self, row, before=None, after=None):
        step = row['resources'][0]
        return {'items': [
            {'kind': 'resources', 'key': RESOURCE, 'planned': {'from': step['from'], 'to': step['to']},
             'actual': {'from': step['from'] if before is None else before,
                        'to': step['to'] if after is None else after}, 'status': 'kept',
             'evidence': {'chapter': 1, 'quote': QUOTE}},
            {'kind': 'clock', 'key': 'clock', 'planned': {'advance_days': 0},
             'actual': {'advance_days': 0}, 'status': 'kept',
             'evidence': {'chapter': 1, 'quote': QUOTE}}], 'unplanned': [], 'verdict': 'clean'}

    def test_subnanounit_changes_are_settled_in_both_design_and_prose(self):
        row = self.row()
        state, findings = drift.simulate([row], self.state, self.book['world'])
        self.assertEqual(findings, [])
        self.assertEqual(state['resources'][RESOURCE], '4.0000000001')
        result = drift.reconcile(self.check(row), row, self.state, self.book['world'])
        self.assertEqual(result['findings'], [])
        state, events = facts.settle(self.state, result['events'], QUOTE, 1)
        self.assertEqual(len(events), 1)
        self.assertEqual(state['resources'][RESOURCE], '4.0000000001')

    def test_large_integer_spending_preserves_the_last_unit(self):
        self.state['resources'][RESOURCE] = '9007199254740993'
        row = self.row('9007199254740993', '9007199254740992')
        result = drift.reconcile(self.check(row), row, self.state, self.book['world'])
        self.assertEqual(result['findings'], [])
        state, events = facts.settle(self.state, result['events'], QUOTE, 1)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['quantity'], '1')
        self.assertEqual(state['resources'][RESOURCE], '9007199254740992')

    def test_spending_preserves_all_supported_decimal_digits(self):
        balance = '123456789012345678901234567890.123456789'
        self.state['resources'][RESOURCE] = balance
        row = self.row(balance, '0')
        result = drift.reconcile(self.check(row), row, self.state, self.book['world'])
        self.assertEqual(result['findings'], [])
        state, events = facts.settle(self.state, result['events'], QUOTE, 1)
        self.assertEqual(events[0]['quantity'], balance)
        self.assertEqual(state['resources'][RESOURCE], '0')

    def test_kept_claim_and_actual_before_have_no_float_tolerance(self):
        row = self.row('4', '4')
        for before, after, criterion in [('4', '4.0000000001', 'drift_kept'),
                                         ('4.0000000001', '4', 'drift_before')]:
            with self.subTest(criterion=criterion):
                result = drift.reconcile(self.check(row, before, after), row, self.state, self.book['world'])
                self.assertIn(criterion, {f['criterion'] for f in result['findings']})

    def test_volume_terminal_and_replan_entry_are_exact(self):
        row = self.row('4', '4')
        terminal = {'resources': [{'key': RESOURCE, 'to': '4.0000000001'}]}
        _, findings = drift.simulate([row], self.state, self.book['world'], volume_outline=terminal)
        self.assertIn('drift_closure', {f['criterion'] for f in findings})
        row['enter'][0]['expected'] = '4.0000000001'
        self.assertTrue(drift.state_mismatch(self.state, row))

    def test_projection_values_remain_json_safe_without_precision_loss(self):
        for value in ('4.0000000001', '9007199254740993'):
            with self.subTest(value=value):
                self.state['resources'][RESOURCE] = value
                projected = drift.project(self.state, 'resources', RESOURCE)
                decoded = json.loads(json.dumps(projected))
                self.assertEqual(str(decoded), value)

    def test_fractional_entry_and_exit_values_freeze_as_json_safe_exact_values(self):
        volume = self.book['contract']['volumes'][0]
        outline = volume_rows(self.book, ['v1'])[0]
        rows = chapter_rows(self.book, volume, self.state)
        for row in rows:
            before = '4' if row['chapter'] == 1 else '4.0000000001'
            row['resources'] = self.row(before)['resources']
            for condition in row['enter']:
                if condition['kind'] == 'resources':
                    condition['expected'] = before
            for condition in row['exit']:
                if condition['kind'] == 'resources':
                    condition['expected'] = '4.0000000001'
        outline['resources'] = [{'key': RESOURCE, 'from': '4', 'to': '4.0000000001',
                                 'reason': '保留精确余额。'}]
        normalized = drift.validate_chapter_outline(
            {'volume': 'v1', 'chapters': rows}, self.book['contract']['chapter_outline'],
            volume, outline, self.book['world'], self.state)
        decoded = json.loads(json.dumps(drift.plan_rows(normalized)))
        self.assertEqual(next(p['expected'] for p in decoded[0]['exit'] if p['kind'] == 'resources'),
                         '4.0000000001')

    def test_legacy_preconditions_use_exact_finite_numbers(self):
        plan = {'preconditions': [{'kind': 'resources', 'key': RESOURCE, 'expected': '4.0000000001'}]}
        self.assertEqual(len(narrative.unmet(self.state, plan)), 1)
        self.state['clock'] = 9007199254740993
        plan = {'preconditions': [{'kind': 'clock', 'key': 'main', 'expected': 9007199254740992}]}
        self.assertEqual(len(narrative.unmet(self.state, plan)), 1)
        for bad in (True, 'Infinity', 'NaN'):
            with self.subTest(value=bad):
                self.assertFalse(narrative.same('resources', bad, bad))


if __name__ == '__main__':
    unittest.main()
