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

from novel_ledger import ledger, workflow
from novel_ledger.bootstrap import local_application as Application
from novel_ledger.contracts import Error
from novel_ledger.sqlite_store import SQLiteRepository
from support import contract, drive, response


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
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / 'book'
        self.repo = SQLiteRepository.initialize(self.project, workflow.new_book(contract()))
        self.app = Application(self.repo)

    def tearDown(self):
        self.repo.close()
        self.temp.cleanup()

    def design_with_ledger(self):
        drive(self.app, until='book_plan')
        result = response(self.app)
        result['data']['ledger'] = [{'key': '垫付总数', 'value': 6, 'sum_of': [2, 4]}]
        self.app.submit(result)
        return [{'key': '垫付总数', 'value': 6, 'sum_of': [2, 4]}]

    def test_a_design_declares_arithmetic_and_a_plan_must_agree(self):
        self.design_with_ledger()
        # The design review, the volume plan and its review all pass on the way to the plans.
        drive(self.app, until='plan')
        result = response(self.app)
        result['data']['plans'][0]['ledger'] = [{'key': '垫付总数', 'value': 6, 'equals': [6, 6]}]
        self.app.submit(result)                      # same key, same value: accepted
        drive(self.app, until='write')               # profiles accepted on the way

    def test_a_disagreeing_plan_is_rejected_with_both_values(self):
        self.design_with_ledger()
        drive(self.app, until='plan')
        result = response(self.app)
        result['data']['plans'][0]['ledger'] = [{'key': '垫付总数', 'value': 5, 'sum_of': [2, 3]}]
        with self.assertRaises(Error) as caught:
            self.app.submit(result)
        self.assertEqual(caught.exception.code, 'ledger')
        self.assertEqual(caught.exception.details['already_on_record'], 6)

    def test_bad_arithmetic_in_a_design_is_rejected_at_submit(self):
        drive(self.app, until='book_plan')
        result = response(self.app)
        result['data']['ledger'] = [{'key': '垫付总数', 'value': 7, 'sum_of': [2, 4]}]
        with self.assertRaises(Error) as caught:
            self.app.submit(result)
        self.assertEqual(caught.exception.details, {'declared': 7, 'computed': 6,
                                                   'relation': 'sum_of', 'operands': [2, 4],
                                                   'recover': '按算得的结果改 value，或修正操作数；观感描述不要写进账目行。'})


if __name__ == '__main__':
    unittest.main()
