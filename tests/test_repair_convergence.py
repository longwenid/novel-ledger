"""A repair loop that is not converging becomes an author decision, not a bonfire.

A real chapter spent four repair rounds on the same two findings — the narrow-repair guard had
stopped rewrites, but nothing noticed that the fixes were not landing. The engine now counts how
many times the very same finding comes back after a repair that was told to fix it; at two, the
loop stops with the spent-budget options while budget still remains, and a granted round resets
the counter.

The findings in v2 are raised by the engine itself at submission (drift reconciliation, lint, word
budget) instead of arriving in a reviewer's receipt, so the recurring finding here is a mechanical
one: the same stray Latin word filed again by the same producer.
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from novel_ledger import workflow
from novel_ledger.bootstrap import local_application as Application
from novel_ledger.contracts import Error
from novel_ledger.sqlite_store import SQLiteRepository
from support import contract, drive, response


class RepairConvergenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / 'book'
        self.repo = SQLiteRepository.initialize(self.project, workflow.new_book(contract()))
        self.app = Application(self.repo)

    def tearDown(self):
        self.repo.close()
        self.temp.cleanup()

    def draft_with_a_stray_word(self):
        """The same mechanical defect, filed by the same producer: a Latin run in Chinese prose."""
        result = response(self.app)
        result['data']['prose'] = result['data']['prose'].replace('要求先核对', '要求 check 核对')
        return result

    def test_the_same_finding_twice_unresolved_stalls_into_an_author_decision(self):
        drive(self.app, until='write')
        self.app.submit(self.draft_with_a_stray_word())
        book = self.repo.load()
        self.assertEqual(book['draft']['stage'], 'repair')
        self.assertIn('language', [row['criterion'] for row in book['draft']['findings']])
        for _round in range(2):
            handoff = self.app.advance()
            self.assertEqual(handoff['task']['stage'], 'repair')
            self.app.submit(self.draft_with_a_stray_word())
        # Two repair rounds in, the same finding is back verbatim: still budgeted (the redesign
        # round remains), but the loop is not converging, so a third identical round is not
        # dispatched — the question goes to the author instead.
        book = self.repo.load()
        self.assertEqual((book['status'], book['draft']['stage']), ('paused', 'stalled'))
        self.assertEqual(book['rework']['1']['repairs'], 2)
        self.assertEqual(book['author_block']['id'], 'repair-stalled:chapter_repair')
        self.assertIn('连续 2 轮', book['author_block']['question'])
        # The stall hands its decision up directly, so resume refuses to bypass it; the pending
        # question is already visible in status.
        self.assertEqual(self.app.status()['author_decision']['id'], 'repair-stalled:chapter_repair')
        with self.assertRaises(Error):
            self.app.resume()

    def test_a_granted_round_resets_the_counter_and_the_chapter_can_still_finish(self):
        drive(self.app, until='write')
        self.app.submit(self.draft_with_a_stray_word())
        for _round in range(2):
            self.app.advance()
            self.app.submit(self.draft_with_a_stray_word())
        granted = self.app.answer('repair-stalled:chapter_repair', workflow.REPAIR_AGAIN,
                                  '这一轮真的改，改完再验。')
        self.assertEqual(granted['status'], 'running')
        book = self.repo.load()
        self.assertEqual(book['draft']['stage'], 'repair')
        self.assertNotIn('recurrence', book['draft'])
        # The author saw movement: the repaired chapter is clean this time and commits.
        handoff = self.app.advance()
        self.assertEqual(handoff['task']['stage'], 'repair')
        self.app.submit(response(self.app))
        self.assertEqual(self.repo.headers('main')[-1]['n'], 1)
        self.assertIsNone(self.repo.load()['draft'])
        self.assertTrue(self.app.audit()['ok'])


if __name__ == '__main__':
    unittest.main()
