"""A repair loop that is not converging becomes an author decision, not a bonfire.

A real chapter spent four repair rounds on the same two findings — the narrow-repair guard had
stopped rewrites, but nothing noticed that the fixes were not landing. The engine now counts how
many times the very same finding comes back after a repair that was told to fix it; at two, the
loop stops with the spent-budget options while budget still remains, and a granted round resets
the counter.
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

    def review_with_recurring_finding(self):
        """A chapter review that fails the same reader check for the same stated reason."""
        result = response(self.app)
        n = self.repo.pending()['input']['chapter']
        prose = next(iter(self.app._sources(self.repo.pending()['input']).values()))
        reader = result['data']['reader']
        reader['verdict'] = 'fix'
        for row in reader['checks']:
            if row['id'] == 'repetition':
                row['result'] = 'fix'
                row['reason'] = '同一段动作组在本章重复出现，未按上轮意见改写。'
        reader['findings'] = [{'criterion': 'repetition', 'severity': 'quality',
                               'reason': '同一段动作组在本章重复出现，未按上轮意见改写。',
                               'target_chapter': n, 'repair_scope': 'local',
                               'evidence': {'chapter': n, 'quote': prose[:20]}}]
        return result

    def rounds(self, count):
        for _ in range(count):
            drive(self.app, until='chapter_review')
            self.app.submit(self.review_with_recurring_finding())
            handoff = self.app.advance()
            self.assertEqual(handoff['action'], 'task_ready')
            self.app.submit(response(self.app))

    def test_the_same_finding_twice_unresolved_stalls_into_an_author_decision(self):
        drive(self.app, until='write')
        self.app.submit(response(self.app))
        self.rounds(2)
        # Two repair rounds in, the same finding is back: still budgeted, but the loop is not
        # converging, so the third identical round is not dispatched.
        book = self.repo.load()
        self.assertEqual((book['status'], book['draft']['stage']), ('running', 'chapter_review'))
        self.assertEqual(book['rework']['1']['repairs'], 2)
        drive(self.app, until='chapter_review')
        self.app.submit(self.review_with_recurring_finding())
        book = self.repo.load()
        self.assertEqual(book['status'], 'paused')
        self.assertEqual(book['author_block']['id'], 'repair-stalled:chapter_repair')
        self.assertIn('连续 2 轮', book['author_block']['question'])
        self.assertEqual(book['draft']['stage'], 'stalled')
        # The stall hands its decision up directly, so resume refuses to bypass it; the pending
        # question is already visible in status.
        self.assertEqual(self.app.status()['author_decision']['id'], 'repair-stalled:chapter_repair')
        with self.assertRaises(Error):
            self.app.resume()

    def test_a_granted_round_resets_the_counter_and_the_chapter_can_still_finish(self):
        drive(self.app, until='write')
        self.app.submit(response(self.app))
        self.rounds(2)
        drive(self.app, until='chapter_review')
        self.app.submit(self.review_with_recurring_finding())
        granted = self.app.answer('repair-stalled:chapter_repair', workflow.REPAIR_AGAIN,
                                  '这一轮真的改，改完再验。')
        self.assertEqual(granted['status'], 'running')
        book = self.repo.load()
        self.assertEqual(book['draft']['stage'], 'repair')
        self.assertNotIn('recurrence', book['draft'])
        # The author saw movement: the repaired chapter now passes its review and commits.
        handoff = self.app.advance()
        self.assertEqual(handoff['task']['stage'], 'repair')
        self.app.submit(response(self.app))
        drive(self.app, until='chapter_review')
        self.app.submit(response(self.app))
        self.assertEqual(self.repo.headers('main')[-1]['n'], 1)


if __name__ == '__main__':
    unittest.main()
