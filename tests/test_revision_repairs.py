"""Applied revision actions and future-design changes remain authoritative."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from novel_ledger import narrative, revision_impact, story_memory, workflow
from novel_ledger.bootstrap import local_application as Application
from novel_ledger.contracts import Error
from novel_ledger.sqlite_store import SQLiteRepository
from support import contract, drive, response
from test_narrative import tracked_contract
from test_editorial import drive as drive_enhanced, enhanced_response


class RevisionRepairTests(unittest.TestCase):
    def test_replanning_window_does_not_reserve_its_queued_original_chapters(self):
        book = workflow.new_book(tracked_contract(5))
        book['written_han'] = 120
        book['revision_run'] = {'carry': [{'n': n, 'han': 60} for n in (3, 4, 5)]}
        write_budget = narrative.budget_for(book, 3)
        plan_budget = narrative.budget_for(book, 3, through=4)
        self.assertEqual((write_budget['fixed_suffix_chapters'], write_budget['remaining_chapters']), (2, 1))
        self.assertEqual((plan_budget['fixed_suffix_chapters'], plan_budget['remaining_chapters']), (1, 2))
        self.assertEqual(plan_budget['fixed_suffix_han'], 60)

    def test_expanded_reading_interval_propagates_new_scene_bridges(self):
        rows = []
        for n in range(1, 5):
            plan = {'chapter': n, 'participants': [], 'dependency_coverage': 'complete',
                    'reading_schema': story_memory.READING_SCHEMA, 'reading_coverage': 'complete',
                    'scenes': [{'id': 's' + str(n), 'reads': [], 'reading_refs': [], 'depends_on': []}]}
            rows.append(dict(n=n, chain=str(n), plan=plan, events=[], plan_hash=str(n), events_hash=str(n)))
        rows[3]['plan']['scenes'][0]['depends_on'] = ['s3']
        changes = {'mode': 'reading', 'reading_changes': [{'kind': 'theme', 'key': 'responsibility'}]}
        initial = revision_impact.analyze(rows, 2, changes)
        self.assertEqual(initial['chapter_actions'][-1]['action'], 'keep')
        expanded = revision_impact.analyze(rows, 2, changes, through=3)
        self.assertEqual([a['action'] for a in expanded['chapter_actions']], ['local', 'rewrite', 'review'])
        self.assertIn('s3', expanded['affected_scenes'])

    def test_expanded_semantic_interval_propagates_new_fact_outputs(self):
        rows = []
        for n in range(1, 5):
            plan = {'chapter': n, 'participants': [], 'dependency_coverage': 'complete',
                    'scenes': [{'id': 's' + str(n), 'reads': [], 'depends_on': []}]}
            rows.append(dict(n=n, chain=str(n), plan=plan, events=[], plan_hash=str(n), events_hash=str(n)))
        rows[2]['events'] = [{'op': 'knowledge', 'entity': 'other', 'topic': 'source'}]
        rows[3]['plan']['scenes'][0]['reads'] = [{'kind': 'knowledge', 'key': 'other:source'}]
        changes = {'mode': 'semantic', 'changes': [{'kind': 'facts', 'key': 'shen:secret'}]}
        self.assertEqual(revision_impact.analyze(rows, 2, changes)['last'], 2)
        self.assertEqual(revision_impact.analyze(rows, 2, changes, through=3)['last'], 4)

    def test_explicit_endpoint_rejects_new_dependencies_before_forking(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = SQLiteRepository.initialize(Path(temp) / 'book', workflow.new_book(contract(4)))
            try:
                app = Application(repo)
                owner = app.run(through=4, source='工程回归：四章。')['owner']
                for _ in range(100):
                    handoff = app.advance(owner=owner)
                    if handoff['action'] == 'await_author':
                        app.approve(handoff['prose_hash'], '工程夹具认可。', owner)
                        continue
                    if handoff['action'] != 'task_ready':
                        break
                    receipt = response(app)
                    work = repo.pending()['input']
                    if work['stage'] == 'plan':
                        for plan in receipt['data']['plans']:
                            reads = [{'kind': 'knowledge', 'key': 'shen:source'}] if plan['chapter'] == 4 else []
                            plan.update(dependency_coverage='complete',
                                        scenes=[{'label': '核对退件。', 'reads': reads, 'depends_on': []}])
                    elif work['stage'] == 'chapter_review' and work['chapter'] == 3:
                        receipt['data']['facts']['events'].append({'op': 'knowledge', 'entity': 'shen',
                            'topic': 'source', 'before': None, 'claim': '看到了封条签字。',
                            'source': '亲眼核对。', 'stance': 'knows', 'evidence': {'chapter': 3, 'quote': '封条上的签字'}})
                    app.submit(receipt)
                self.assertEqual(handoff['action'], 'target_reached')
                changes = {'mode': 'semantic', 'changes': [{'kind': 'facts', 'key': 'shen:secret'}]}
                self.assertEqual(app.revision_impact(2, changes)['last'], 2)
                before = repo.load()
                with self.assertRaises(Error) as caught:
                    app.revise(2, '明确修改到第三章。', owner, through=3, changes=changes)
                self.assertEqual(caught.exception.code, 'revision_impact')
                self.assertEqual(caught.exception.details['required_through'], 4)
                self.assertEqual(repo.load(), before)
                self.assertTrue(app.audit()['ok'])
            finally:
                repo.close()

    def test_explicit_endpoint_updates_applied_actions_and_preserves_analysis_endpoint(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = SQLiteRepository.initialize(Path(temp) / 'book', workflow.new_book(contract(4)))
            try:
                app = Application(repo)
                owner = app.run(through=4, source='工程回归：四章。')['owner']
                drive(app, owner)
                changes = {'mode': 'reading', 'reading_changes': [{'kind': 'character', 'key': 'shen'}]}
                app.revise(2, '明确修改到第三章。', owner, through=3, changes=changes)
                impact = repo.load()['revision_run']['impact']
                self.assertEqual((impact['analyzed_last'], impact['last']), (2, 3))
                self.assertEqual(impact['rewrite_chapters'], [2, 3])
                self.assertEqual([a['action'] for a in impact['chapter_actions']], ['local', 'rewrite', 'review'])
                app.advance(owner=owner)
                app.submit(response(app))
                app.advance(owner=owner)
                app.submit(response(app))
                task = app.advance(owner=owner)['task']
                self.assertEqual((task['chapter'], task['stage']), (3, 'repair'))
                self.assertEqual(drive(app, owner)['action'], 'revision_ready')
                self.assertTrue(app.audit()['ok'])
            finally:
                repo.close()

    def future_alignment(self, temp, changes):
        raw = tracked_contract(4)
        raw['editorial_features'] = True
        repo = SQLiteRepository.initialize(Path(temp) / 'book', workflow.new_book(raw))
        app = Application(repo)
        owner = app.run(through=4, source='工程回归：四章。')['owner']
        drive_enhanced(app, owner)
        app.revise(2, '调整阅读作用并保留后续改案。', owner, through=2, changes=changes)
        app.advance(owner=owner)
        app.submit(enhanced_response(app))
        app.advance(owner=owner)
        review = enhanced_response(app)
        review['data']['alignment']['action'] = 'adapt_future'
        app.submit(review)
        # Carry must stop even before the new plan is proposed.
        self.assertEqual([r['n'] for r in repo.headers(repo.load()['branch'])], [1, 2])
        self.assertEqual(app.advance(owner=owner)['task']['stage'], 'alignment_plan')
        proposal = enhanced_response(app)
        proposal['data']['plan']['goal'] = '已核验的新后续目标。'
        app.submit(proposal)
        app.advance(owner=owner)
        app.submit(enhanced_response(app))
        return repo, app, owner

    def test_approved_future_plan_is_kept_and_changed_chapter_gets_full_review(self):
        with tempfile.TemporaryDirectory() as temp:
            changes = {'mode': 'reading', 'reading_changes': [{'kind': 'character', 'key': 'shen'}]}
            repo, app, owner = self.future_alignment(temp, changes)
            try:
                task = app.advance(owner=owner)['task']
                self.assertEqual((task['chapter'], task['stage']), (3, 'repair'))
                work = repo.pending()['input']
                plan = repo.read_document(work['records']['scene_context'])['plan']
                self.assertEqual(plan['goal'], '已核验的新后续目标。')
                self.assertEqual(repo.load()['plans']['3']['goal'], plan['goal'])
                app.submit(enhanced_response(app))
                self.assertEqual(app.advance(owner=owner)['task']['stage'], 'chapter_review')
                app.submit(enhanced_response(app))
                # Alignment cleared the rest of the future window: it must be planned again.
                self.assertEqual(app.advance(owner=owner)['task']['stage'], 'plan')
                old_review = repo.chapter(repo.load()['revision_run']['parent'], 4)['review']
                app.submit(enhanced_response(app))
                # Recreating the original plan cannot revive its old passed review.
                self.assertEqual(app.advance(owner=owner)['task']['stage'], 'repair')
                self.assertEqual(drive_enhanced(app, owner)['action'], 'revision_ready')
                accepted = repo.read_document(repo.chapter(repo.load()['branch'], 3)['plan'])
                self.assertEqual(accepted['goal'], '已核验的新后续目标。')
                self.assertEqual(repo.load()['plans']['3']['goal'], accepted['goal'])
                self.assertNotEqual(repo.chapter(repo.load()['branch'], 4)['review'], old_review)
                self.assertTrue(app.audit()['ok'])
                app.promote(owner)
                self.assertTrue(app.audit()['ok'])
            finally:
                repo.close()

    def test_manual_narrow_revision_also_waits_for_future_alignment(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, app, owner = self.future_alignment(temp, None)
            try:
                self.assertEqual(app.advance(owner=owner)['task']['stage'], 'repair')
                self.assertEqual(drive_enhanced(app, owner)['action'], 'revision_ready')
                accepted = repo.read_document(repo.chapter(repo.load()['branch'], 3)['plan'])
                self.assertEqual(accepted['goal'], '已核验的新后续目标。')
                self.assertTrue(app.audit()['ok'])
            finally:
                repo.close()


if __name__ == '__main__':
    unittest.main()
