"""Structured account blocks: arithmetic the engine checks, prose no longer has to carry.

The design is rework.md 机制 3: an optional `ledger` on a design, an outline or a chapter plan;
once present, every row is proved at submit (and at preflight, which runs the same validation),
and a later artifact reusing a key must agree with the value already on record. The defects this
replaces each cost a repair round plus a full independent re-review when only the reviewer could
re-derive "six payments of three years is eighteen".
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from novel_ledger import ledger
from novel_ledger.bootstrap import local_application as Application
from novel_ledger.contracts import Error
from novel_ledger.sqlite_store import SQLiteRepository
from support import drive, response, seeded_book


class LedgerUnitTests(unittest.TestCase):
    def assert_row_rejected(self, row, fragment):
        with self.assertRaises(Error) as caught:
            ledger.check([row])
        self.assertEqual(caught.exception.code, 'ledger')
        self.assertIn(fragment, caught.exception.message)

    def test_each_relation_computes_and_bad_arithmetic_is_named(self):
        ledger.check([{'key': '总数', 'value': 17, 'sum_of': [6, 11]},
                      {'key': '年数', 'value': 18, 'product_of': [6, 3]},
                      {'key': '份数', 'value': 6, 'equals': [6, 6, 6]},
                      {'key': '均值', 'value': 3, 'ratio_of': [18, 6]}])
        self.assert_row_rejected({'key': '总数', 'value': 16, 'sum_of': [6, 11]}, '总数')
        self.assert_row_rejected({'key': '年数', 'value': 18, 'product_of': [5, 3]}, '年数')
        self.assert_row_rejected({'key': '均值', 'value': 4, 'ratio_of': [18, 6]}, '均值')

    def test_shape_complaints_cover_duplicates_and_missing_relations(self):
        self.assert_row_rejected({'key': 'x', 'value': 1}, '恰好声明一种关系')
        self.assert_row_rejected({'key': 'x', 'value': 1, 'sum_of': [1, 0], 'equals': [1, 1]}, '恰好声明一种关系')
        with self.assertRaises(Error):
            ledger.check([{'key': 'x', 'value': 1, 'sum_of': [1, 0]},
                          {'key': 'x', 'value': 2, 'sum_of': [1, 1]}])

    def test_a_reused_key_must_keep_its_recorded_value(self):
        prior = [{'key': '总数', 'value': 17, 'sum_of': [6, 11]}]
        ledger.cross_check([{'key': '总数', 'value': 17, 'equals': [17, 17]}], prior)
        with self.assertRaises(Error) as caught:
            ledger.cross_check([{'key': '总数', 'value': 16, 'sum_of': [6, 10]}], prior)
        self.assertEqual(caught.exception.details['already_on_record'], 17)


class LedgerFlowTests(unittest.TestCase):
    """An outline may carry account blocks; the engine proves the arithmetic at submit.

    v2 kept `ledger.check` on the two outline dispatches and dropped the design→plan cross-check with
    the design stages that owned the earlier declaration: the chapter outline *is* the declaration
    now, so there is no later artifact to disagree with it.
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / 'book'
        self.repo = SQLiteRepository.initialize(self.project, seeded_book())
        self.app = Application(self.repo)

    def tearDown(self):
        self.repo.close()
        self.temp.cleanup()

    def test_bad_arithmetic_in_a_volume_outline_is_rejected_at_submit(self):
        handoff = self.app.advance()
        self.assertEqual(handoff['task']['stage'], 'volume_outline')
        result = response(self.app)
        result['data']['ledger'] = [{'key': '垫付总数', 'value': 7, 'sum_of': [2, 4]}]
        with self.assertRaises(Error) as caught:
            self.app.submit(result)
        self.assertEqual(caught.exception.code, 'ledger')
        self.assertEqual(caught.exception.details['computed'], 6)
        self.assertIsNone(self.repo.load()['volumes_outline'].get('v1'))

    def test_chapter_outline_arithmetic_is_proved_at_submit(self):
        drive(self.app, until='chapter_outline')
        bad = response(self.app)
        bad['data']['ledger'] = [{'key': '垫付总数', 'value': 6, 'product_of': [2, 4]}]
        with self.assertRaises(Error) as caught:
            self.app.submit(bad)
        self.assertEqual(caught.exception.code, 'ledger')
        self.assertEqual(self.repo.load()['chapter_outlines'], {})
        good = response(self.app)
        good['data']['ledger'] = [{'key': '垫付总数', 'value': 6, 'sum_of': [2, 4]}]
        self.app.submit(good)
        self.assertEqual(sorted(self.repo.load()['chapter_outlines']), ['v1'])


if __name__ == '__main__':
    unittest.main()
