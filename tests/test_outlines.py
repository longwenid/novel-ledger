"""Synthetic protocol tests for world-grounded, full-volume chapter outlines."""
import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from novel_ledger import context, planning, workflow
from novel_ledger.bootstrap import local_application as Application
from novel_ledger.contracts import Error, Job, han_count
from novel_ledger.sqlite_store import SQLiteRepository
from support import contract, response
from test_narrative import tracked_contract, tracked_response


class OutlineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        raw = tracked_contract(12)
        raw['volume_outline'] = {'scope': 'current', 'words': 500, 'tolerance': 50}
        self.repo = SQLiteRepository.initialize(Path(self.temp.name) / 'book', workflow.new_book(raw))
        self.app = Application(self.repo)

    def tearDown(self):
        self.repo.close()
        self.temp.cleanup()

    def drive_to(self, stage, owner=None):
        for _ in range(150):
            handoff = self.app.advance(owner=owner)
            if handoff['action'] == 'await_author':
                self.app.approve(handoff['prose_hash'], '工程夹具认可版本。', owner)
            elif handoff['action'] != 'task_ready':
                return handoff
            elif handoff['task']['stage'] == stage:
                return handoff
            else:
                self.app.submit(tracked_response(self.app) if self.repo.pending()['input']['narrative_tracking'] else response(self.app))
        self.fail('流程未在有限步骤内结束。')

    def test_current_volume_covers_all_chapters_while_plan_only_reads_its_window(self):
        self.drive_to('plan')
        book = self.repo.load()
        self.assertEqual([c['chapter'] for c in book['designs']['volume:v1']['chapters']], list(range(1, 13)))
        work = self.repo.pending()['input']
        self.assertEqual([c['chapter'] for c in self.repo.read_document(work['records']['volume_outline_window'])], [1])
        for name in work['required']:
            if name.startswith('frontier:'):
                self.assertNotIn('chapters', self.repo.read_document(work['records'][name]))
        self.assertEqual(book['state']['story_nodes'], {})
        self.assertEqual(self.repo.headers('main'), [])

    def test_all_scope_designs_each_volume_before_writing(self):
        raw = tracked_contract(4)
        raw['volumes'] = contract(4, 2)['volumes']
        raw['volume_outline'] = {'scope': 'all', 'words': 500, 'tolerance': 50}
        self.repo.save(workflow.new_book(raw))
        self.drive_to('write')
        book = self.repo.load()
        self.assertEqual([c['chapter'] for c in book['designs']['volume:v1']['chapters']], [1, 2])
        self.assertEqual([c['chapter'] for c in book['designs']['volume:v2']['chapters']], [3, 4])
        self.assertEqual(self.repo.headers('main'), [])
        work = self.repo.pending()['input']
        self.assertEqual(self.repo.read_document(work['records']['chapter_outline'])['chapter'], 1)

    def test_outline_batches_are_bounded_atomic_and_resume_from_reviewed_prefix(self):
        self.drive_to('volume_outline')
        task = self.repo.pending()['input']
        self.assertEqual((task['first'], task['last']), (1, 3))
        self.app.submit(tracked_response(self.app))
        self.app.advance()
        review = tracked_response(self.app)
        self.app.submit(review, preview=True)
        self.assertEqual(self.repo.load()['designs']['volume:v1'].get('chapters', []), [])
        self.app.submit(review)
        first = copy.deepcopy(self.repo.load()['designs']['volume:v1']['chapters'])
        self.assertEqual([c['chapter'] for c in first], [1, 2, 3])
        self.repo.close()
        self.repo = SQLiteRepository(Path(self.temp.name) / 'book')
        self.app = Application(self.repo)
        self.app.advance()
        task = self.repo.pending()['input']
        self.assertEqual((task['first'], task['last']), (4, 6))
        self.assertEqual(self.repo.load()['designs']['volume:v1']['chapters'], first)
        self.assertEqual(self.repo.read_document(task['records']['outline_bridge']), first[-1:])
        self.assertNotIn('chapters', self.repo.read_document(task['records']['volume_design']))
        self.assertTrue(all(not name.startswith('design:') for name in task['required']))

    def test_large_planning_window_cannot_make_an_unbounded_outline_batch(self):
        raw = tracked_contract(100)
        raw['planning_window'] = 100
        raw.pop('volume_outline')
        self.repo.save(workflow.new_book(raw))
        self.drive_to('volume_outline')
        work = self.repo.pending()['input']
        self.assertEqual((work['first'], work['last']), (1, 6))

    def test_outline_fix_retries_current_batch_without_clearing_reviewed_prefix(self):
        self.drive_to('volume_outline')
        self.app.submit(tracked_response(self.app))
        self.app.advance()
        self.app.submit(tracked_response(self.app))
        prefix = copy.deepcopy(self.repo.load()['designs']['volume:v1']['chapters'])
        self.app.advance()
        self.app.submit(tracked_response(self.app))
        self.app.advance()
        review = tracked_response(self.app)
        row = next(c for c in review['data']['checks'] if c['id'] == 'causality')
        row['result'] = 'fix'
        review['data']['verdict'] = 'fix'
        review['data']['findings'] = [dict(criterion='causality', severity='quality', reason='工程缺陷样本：批次衔接缺少选择依据。',
                                         evidence=row['evidence'][0], target_chapter=0, repair_scope='chapter')]
        self.app.submit(review)
        self.app.advance()
        task = self.repo.pending()['input']
        self.assertEqual(task['stage'], 'volume_outline')
        self.assertEqual((task['first'], task['last']), (4, 6))
        self.assertEqual(self.repo.load()['proposal']['attempts'], 1)
        self.assertEqual(self.repo.load()['designs']['volume:v1']['chapters'], prefix)
        self.assertIn('previous_proposal', task['required'])

    def test_defaults_strict_length_and_original_task_compatibility(self):
        raw = contract()
        raw.pop('volume_outline')
        self.assertEqual(planning.validate_contract(raw)['volume_outline'], {'scope': 'rolling', 'words': 500, 'tolerance': 50})
        self.assertEqual(planning.skeleton()['volume_outline']['words'], 500)
        raw['volume_outline'] = {'scope': 'current', 'words': 500, 'tolerance': 0}
        self.repo.save(workflow.new_book(raw))
        self.drive_to('volume_outline')
        valid = response(self.app)
        self.assertEqual(han_count(valid['data']['chapters'][0]['synopsis']), 500)
        invalid = copy.deepcopy(valid)
        invalid['data']['chapters'][0]['synopsis'] = '甲' * 499
        with self.assertRaises(Error) as caught:
            self.app.submit(invalid)
        self.assertEqual(caught.exception.code, 'outline_length')
        self.app.submit(valid)
        # A legacy frozen task is not retrofitted with the new schema or chapter placeholders.
        old = workflow.new_book(contract())
        old['contract'].pop('volume_outline')
        work = context.build(self.repo, old, Job('volume_plan', 1, 'volume:v1'))
        self.assertNotIn('volume_outline', work['payload'])
        self.assertNotIn('volume_outline', work['capabilities'])


if __name__ == '__main__':
    unittest.main()
