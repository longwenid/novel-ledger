"""Applied revision actions stay bounded: the author's endpoint decides how far the fork reaches.

v2 removed the alignment stages that used to arbitrate what a revision was allowed to change, so the
bound is enforced where the branch is created: `revise` analyzes the requested range, records the
impact on the revision run, and the carried suffix re-settles against the new state or refuses. A
range the window does not cover is not started at all — it becomes the author's authorization
decision (covered in test_revision_bounds.py).
"""
import copy
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from novel_ledger import context, narrative, revision_impact, story_memory, workflow
from novel_ledger.bootstrap import local_application as Application
from novel_ledger.contracts import Error, Job
from novel_ledger.sqlite_store import SQLiteRepository
from support import contract, drive, response, seeded_book, tracked_contract


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

    def test_expanded_intervals_propagate_new_reading_and_fact_dependencies(self):
        def plain_rows(reading):
            rows = []
            for n in range(1, 5):
                plan = {'chapter': n, 'participants': [], 'dependency_coverage': 'complete',
                        'scenes': [{'id': 's' + str(n), 'reads': [], 'depends_on': []}]}
                if reading:
                    plan.update(reading_schema=story_memory.READING_SCHEMA, reading_coverage='complete')
                    plan['scenes'][0]['reading_refs'] = []
                story_memory.bind(plan, {})
                rows.append(dict(n=n, chain=str(n), plan=plan, events=[], plan_hash=str(n),
                                 events_hash=str(n)))
            return rows

        reading_rows = plain_rows(reading=True)
        reading_rows[3]['plan']['scenes'][0]['depends_on'] = ['s3']
        reading_changes = {'mode': 'reading', 'reading_changes': [{'kind': 'theme', 'key': 'responsibility'}]}
        initial = revision_impact.analyze(reading_rows, 2, reading_changes)
        self.assertEqual(initial['chapter_actions'][-1]['action'], 'keep')
        expanded = revision_impact.analyze(reading_rows, 2, reading_changes, through=3)
        self.assertEqual([a['action'] for a in expanded['chapter_actions']], ['local', 'rewrite', 'rewrite'])
        self.assertIn('s3', expanded['affected_scenes'])
        self.assertEqual(expanded['last'], 4)
        self.assertEqual(expanded['rewrite_chapters'], [2, 3, 4])

        semantic_rows = plain_rows(reading=False)
        semantic_rows[2]['events'] = [{'op': 'knowledge', 'entity': 'other', 'topic': 'source'}]
        semantic_rows[3]['plan']['scenes'][0]['reads'] = [{'kind': 'knowledge', 'key': 'other:source'}]
        semantic_changes = {'mode': 'semantic', 'changes': [{'kind': 'facts', 'key': 'shen:secret'}]}
        self.assertEqual(revision_impact.analyze(semantic_rows, 2, semantic_changes)['last'], 2)
        self.assertEqual(revision_impact.analyze(semantic_rows, 2, semantic_changes, through=3)['last'], 4)

    def book(self, chapters=5):
        """Five chapters of a two-volume book: volume one closed, volume two still open."""
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        repo = SQLiteRepository.initialize(Path(temp.name) / 'book', seeded_book(contract(6, 2)))
        self.addCleanup(repo.close)
        app = Application(repo)
        owner = app.run(through=chapters, source='工程回归：写到第五章。')['owner']
        self.assertEqual(drive(app, owner)['action'], 'target_reached')
        return repo, app, owner

    def test_a_narrow_endpoint_beyond_the_analysis_waits_for_the_author(self):
        """An endpoint smaller than the analyzed impact is a policy violation, not a silent widening.

        The engine saves the complete plan (hash, range, impact, context) and pauses; the branch is
        only created when the author authorizes that exact plan with their own words.
        """
        for changes in ({'mode': 'semantic', 'changes': [{'kind': 'knowledge', 'key': 'shen:source'}]},
                        {'mode': 'reading', 'reading_changes': [{'kind': 'character', 'key': 'shen'}]}):
            with self.subTest(mode=changes['mode']):
                repo, app, owner = self.book()
                before = [r['n'] for r in repo.headers('main')]
                app.revise(4, '只改到第四章。', owner, through=4, changes=changes)
                book = repo.load()
                plan = book['revision_directive']
                self.assertTrue(plan['blocked'])
                self.assertIn('impact_beyond_request', plan['violations'])
                self.assertEqual(plan['impact']['last'], 5)
                self.assertIsNone(book['revision_run'])
                self.assertEqual([r['n'] for r in repo.headers('main')], before)
                app.revise(4, '采纳。', owner, proposal_hash=plan['plan_hash'],
                           source='工程作者明确授权把这一改动做到第五章。')
                self.assertEqual(repo.load()['revision_run']['first'], 4)
                self.assertEqual(repo.load()['revision_run']['last'], 5)

    def test_a_wider_endpoint_widens_the_applied_actions_and_the_rewrite_leaves_the_parent_intact(self):
        repo, app, owner = self.book()
        parent = {n: repo.chapter('main', n)['prose'] for n in (1, 2, 3, 4, 5)}
        changes = {'mode': 'reading', 'reading_changes': [{'kind': 'character', 'key': 'shen'}]}
        self.assertEqual(app.revision_impact(4, changes)['last'], 5)
        app.revise(4, '明确修改到第五章。', owner, through=5, changes=changes)
        impact = repo.load()['revision_run']['impact']
        self.assertEqual((impact['analyzed_last'], impact['last']), (5, 5))
        self.assertEqual(impact['rewrite_chapters'], [4, 5])
        self.assertEqual(impact['chapter_actions'][0]['action'], 'local')
        original_outlines = copy.deepcopy(repo.load()['chapter_outlines'])
        before_replan = repo.load()
        premature = context.build(repo, before_replan, Job('repair', 4))
        with self.assertRaises(Error) as caught:
            workflow.apply(before_replan, premature, {'title': '工程标题', 'summary': '工程摘要',
                           'self_check': '核对当前修订任务。'}, 'premature-worker', {})
        self.assertEqual(caught.exception.code, 'revision_outline')
        self.assertEqual(repo.load(), before_replan)
        outline_task = app.advance(owner=owner)['task']
        self.assertEqual(outline_task['stage'], 'chapter_outline')
        work = repo.pending()['input']
        self.assertEqual((work['first'], work['last']), (4, 5))
        result = response(app)
        root = repo.get('book')
        budget = copy.deepcopy(repo.load()['rework'])
        oversized = copy.deepcopy(result)
        oversized['data']['through_chapter'] = 6
        # A content defect answers the preview as data: nothing commits, nothing is counted.
        checked = app.check(oversized)
        self.assertFalse(checked['valid'])
        self.assertEqual(checked['error'], 'chapter_outline')
        self.assertEqual(repo.get('book'), root)
        result['data']['chapters'][0]['synopsis'] += '人物重新权衡自己的责任。'
        app.check(result)
        self.assertEqual(repo.get('book'), root)
        self.assertEqual(repo.load()['rework'], budget)
        app.submit(result)
        updated = repo.load()
        self.assertNotEqual(updated['chapter_outlines']['v2'][0], original_outlines['v2'][0])
        self.assertEqual(updated['chapter_outlines']['v2'][-1], original_outlines['v2'][-1])
        for _chapter in (4, 5):
            task = app.advance(owner=owner)['task']
            self.assertEqual(task['stage'], 'repair')
            app.submit(response(app))
        branch = repo.load()['branch']
        self.assertEqual([r['n'] for r in repo.headers(branch)], [1, 2, 3, 4, 5])
        self.assertEqual([r['n'] for r in repo.headers('main')], [1, 2, 3, 4, 5])
        for n in (1, 2, 3):
            self.assertEqual(repo.chapter(branch, n)['prose'], parent[n])
        self.assertTrue(app.audit()['ok'])
        self.assertEqual(drive(app, owner)['action'], 'revision_ready')
        self.assertEqual(app.status()['formal_branch'], 'main')
        app.promote(owner)
        self.assertEqual(app.status()['formal_branch'], branch)
        self.assertEqual(app.status()['formal_chapters'], 5)
        self.assertIsNone(repo.load()['revision_run'])

    def test_reading_revision_replans_each_affected_volume_before_its_prose(self):
        repo, app, owner = self.book()
        changes = {'mode': 'reading', 'reading_changes': [{'kind': 'character', 'key': 'shen'}]}
        app.revise(2, '跨卷调整人物理解。', owner, through=5, changes=changes)
        proposal = repo.load()['revision_directive']
        app.revise(2, '采用准确方案。', owner, proposal_hash=proposal['plan_hash'],
                   source='工程作者授权从第二章重写至第五章。')
        stages = []
        for stage, number in (('chapter_outline', 2), ('repair', 2), ('repair', 3),
                              ('chapter_outline', 4), ('repair', 4), ('repair', 5)):
            task = app.advance(owner=owner)['task']
            self.assertEqual((task['stage'], task['chapter']), (stage, number))
            result = response(app)
            if stage == 'chapter_outline':
                self.assertEqual(result['data']['through_chapter'], 3 if number == 2 else 5)
                result['data']['chapters'][0]['synopsis'] += '按修订后的阅读关联展开人物选择。'
            stages.append(stage)
            app.submit(result)
        self.assertEqual(stages.count('chapter_outline'), 2)
        self.assertEqual(app.advance(owner=owner)['action'], 'revision_ready')
        self.assertTrue(app.audit()['ok'])


if __name__ == '__main__':
    unittest.main()
