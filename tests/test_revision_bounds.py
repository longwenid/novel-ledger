"""A revision that reaches beyond the automatic window becomes an author decision, not a fork.

v2 has no reviewer to notice that a repair plan outgrew its scope, so the bound is checked where the
revision is requested: `revise` analyzes the impact, measures it against the contract's window and
the volumes already written to their end, and — when it reaches too far — saves the complete plan
(its hash, range, impact and design context) and pauses instead of touching the original prose. Only
the author's own words bound to that exact plan hash start the branch.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from novel_ledger.bootstrap import local_application as Application
from novel_ledger.contracts import Error
from novel_ledger.sqlite_store import SQLiteRepository
from support import contract, drive, response, seeded_book


class RevisionBoundsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / 'book'
        self.repo = None

    def tearDown(self):
        if self.repo:
            self.repo.close()
        self.temp.cleanup()

    def assertCode(self, code, fn, *args, **kwargs):
        with self.assertRaises(Error) as caught:
            fn(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)
        return caught.exception

    def written(self, chapters=5):
        """A two-volume book written through chapter five: volume one is closed, volume two is not."""
        self.repo = SQLiteRepository.initialize(self.project, seeded_book(contract(6, 2)))
        self.app = Application(self.repo)
        self.owner = self.app.run(through=chapters, source='工程夹具：写到第五章。')['owner']
        self.assertEqual(drive(self.app, self.owner)['action'], 'target_reached')
        return self.repo.load()

    def blocked(self, first, changes, through):
        """Ask for a revision that reaches outside the window; return the saved plan."""
        self.written()
        self.app.revise(first, '工程夹具：修改这一段。', self.owner, through=through, changes=changes)
        book = self.repo.load()
        self.assertEqual(book['status'], 'paused')
        plan = book['revision_directive']
        self.assertTrue(plan['blocked'])
        self.assertIsNone(book['revision_run'])
        return plan

    def authorize(self, plan, first=2):
        self.app.revise(first, '采纳。', self.owner, proposal_hash=plan['plan_hash'],
                        source='工程作者明确授权该准确方案。')
        return self.repo.load()

    def test_a_revision_inside_the_window_opens_its_exact_range(self):
        self.written()
        self.app.revise(5, '只改最后一章的表达。', self.owner, through=5, changes={'mode': 'expression'})
        book = self.repo.load()
        self.assertIsNone(book.get('revision_directive'))
        self.assertEqual((book['revision_run']['first'], book['revision_run']['last']), (5, 5))
        self.assertNotEqual(book['branch'], 'main')
        self.assertEqual(len(self.repo.headers('main')), 5)
        self.assertEqual(self.app.status()['revision_run']['first'], 5)

    def test_unfinished_revision_cannot_replace_the_formal_branch(self):
        self.written()
        parent_rows = self.repo.headers('main')
        self.assertCode('revision', self.app.promote, self.owner)
        self.app.revise(5, '修改第五章表达。', self.owner, through=5, changes={'mode': 'expression'})
        before = self.repo.load()
        self.assertEqual(self.app.status()['formal_chapters'], 5)
        self.assertCode('revision', self.app.promote, self.owner)
        self.assertEqual(self.repo.load(), before)
        self.assertEqual(self.repo.headers('main'), parent_rows)
        self.assertEqual(self.app.status()['formal_branch'], 'main')
        self.assertEqual(self.app.status()['formal_chapters'], 5)
        # A frozen repair is not completion either.
        self.app.advance(owner=self.owner)
        self.assertCode('revision', self.app.promote, self.owner)
        self.assertEqual(self.app.status()['formal_branch'], 'main')

    def test_ready_revision_is_adopted_before_resuming_the_original_finish_goal(self):
        self.written()
        self.app.run(finish=True, owner=self.owner, source='作者授权续写并完本。')
        self.app.revise(5, '先修第五章表达。', self.owner, through=5, changes={'mode': 'expression'})
        handoff = drive(self.app, self.owner)
        self.assertEqual(handoff['action'], 'revision_ready')
        self.assertEqual(self.app.status()['formal_branch'], 'main')
        self.assertCode('completion', self.app.complete, self.owner)
        adopted = self.app.promote(self.owner)
        self.assertIsNone(adopted['revision_run'])
        self.assertEqual(adopted['target'], 6)
        self.assertTrue(adopted['finish'])
        self.assertEqual(drive(self.app, self.owner)['action'], 'ready_to_complete')
        self.assertTrue(self.app.complete(self.owner)['completed'])

    def test_a_revision_older_than_the_window_is_saved_for_the_author(self):
        plan = self.blocked(2, {'mode': 'expression'}, 2)
        self.assertIn('outside_recent_window', plan['violations'])
        self.assertEqual(plan['first'], 2)
        self.assertEqual(plan['impact']['last'], 2)
        handoff = self.app.advance(owner=self.owner)
        self.assertEqual(handoff['action'], 'revision_blocked')
        self.assertEqual(handoff['proposal']['plan_hash'], plan['plan_hash'])
        self.assertTrue(Path(handoff['proposal']['plan_path']).is_file())
        # resume may not widen the authorization on its own.
        self.assertCode('revision_bounds', self.app.resume, self.owner)

    def test_a_semantic_change_larger_than_the_window_is_saved(self):
        plan = self.blocked(2, {'mode': 'semantic', 'changes': [{'kind': 'facts', 'key': 'shen:secret'}]}, 5)
        self.assertIn('rewrite_limit', plan['violations'])
        self.assertEqual(plan['impact']['last'], 5)
        self.assertEqual(self.repo.load()['branch'], 'main')

    def test_a_closed_volume_blocks_even_a_recent_single_chapter_fix(self):
        plan = self.blocked(3, {'mode': 'expression'}, 3)
        self.assertIn('closed_volume', plan['violations'])
        self.assertEqual(plan['impact']['last'], 3)
        self.assertEqual(self.repo.load()['branch'], 'main')

    def test_authorization_is_bound_to_the_exact_hash_range_and_source(self):
        plan = self.blocked(2, {'mode': 'expression'}, 2)
        key = plan['plan_hash']
        self.assertCode('author_source', self.app.revise, 2, '采纳。', self.owner, proposal_hash=key)
        self.assertCode('revision_proposal', self.app.revise, 2, '采纳。', self.owner,
                        proposal_hash='old-hash', source='工程作者授权。')
        self.assertCode('revision_proposal', self.app.revise, 1, '采纳。', self.owner,
                        proposal_hash=key, source='工程作者授权。')
        self.assertCode('revision_proposal', self.app.revise, 3, '采纳。', self.owner,
                        proposal_hash=key, source='工程作者授权。')
        book = self.authorize(plan)
        self.assertEqual(book['revision_run']['first'], 2)
        self.assertEqual(book['decisions'][-1]['plan_hash'], key)
        self.assertIsNone(self.app.status()['revision_proposal'])
        self.assertEqual(book['status'], 'running')

    def test_a_changed_design_context_invalidates_an_old_authorization(self):
        plan = self.blocked(2, {'mode': 'expression'}, 2)
        book = self.repo.load()
        book['plans']['5']['synopsis'] = '上下文已变化，旧授权不得套用。'
        self.repo.save(book)
        self.assertCode('revision_proposal', self.app.revise, 2, '采纳旧方案。', self.owner,
                        proposal_hash=plan['plan_hash'], source='工程作者对旧上下文方案的授权。')
        self.assertEqual(self.repo.load()['branch'], 'main')

    def test_lexical_change_invalidates_authorization_until_the_plan_is_refreshed(self):
        plan = self.blocked(2, {'mode': 'expression'}, 2)
        self.app.set_lexical({'forbidden_terms': ['临时禁词']}, '工程作者改变字面规则。', self.owner)
        self.assertCode('revision_proposal', self.app.revise, 2, '采纳旧方案。', self.owner,
                        proposal_hash=plan['plan_hash'], source='工程作者对旧上下文方案的授权。')
        self.app.revise(2, '重新分析原缺陷。', self.owner, through=2, changes={'mode': 'expression'})
        refreshed = self.repo.load()['revision_directive']
        self.assertNotEqual(refreshed['plan_hash'], plan['plan_hash'])
        self.authorize(refreshed)
        self.assertEqual(self.repo.load()['revision_run']['first'], 2)

    def test_a_blocked_plan_leaves_the_ledger_and_the_budget_untouched(self):
        self.written()
        before = self.repo.load()
        rows = self.repo.headers('main')
        self.app.revise(2, '工程夹具：修改这一段。', self.owner, through=2, changes={'mode': 'expression'})
        plan = self.repo.load()['revision_directive']
        self.assertEqual(self.repo.headers('main'), rows)
        self.assertEqual(self.repo.load()['rework'], before['rework'])
        self.assertEqual(plan['impact']['first'], 2)
        self.assertEqual(plan['impact']['last'], 2)
        self.assertIsNone(before['revision_run'])

    def test_a_carried_suffix_keeps_its_exact_prose_and_facts(self):
        plan = self.blocked(2, {'mode': 'expression'}, 2)
        parent = {n: self.repo.chapter('main', n)['prose'] for n in (3, 4, 5)}
        before = self.repo.chapter('main', 2)['prose']
        self.authorize(plan)
        task = self.app.advance(owner=self.owner)['task']
        self.assertEqual((task['stage'], task['chapter']), ('repair', 2))
        changed = response(self.app)
        changed['data']['prose'] = changed['data']['prose'].replace('夜班登记册', '夜班台账')
        self.app.submit(changed)
        branch = self.repo.load()['branch']
        self.assertEqual([r['n'] for r in self.repo.headers(branch)], [1, 2, 3, 4, 5])
        for n in (3, 4, 5):
            self.assertEqual(self.repo.chapter(branch, n)['prose'], parent[n])
        self.assertNotEqual(self.repo.chapter(branch, 2)['prose'], before)
        self.assertTrue(self.app.audit()['ok'])
        self.assertEqual(drive(self.app, self.owner)['action'], 'revision_ready')
        self.assertEqual(self.app.status()['formal_branch'], 'main')
        adopted = self.app.promote(self.owner)
        self.assertEqual(adopted['formal_branch'], branch)
        self.assertIsNone(adopted['revision_run'])
        self.assertEqual(self.app.advance(owner=self.owner)['action'], 'target_reached')

    def test_an_expression_revision_that_moves_a_fact_cannot_carry_its_suffix(self):
        plan = self.blocked(2, {'mode': 'expression'}, 2)
        self.authorize(plan)
        task = self.app.advance(owner=self.owner)['task']
        self.assertEqual((task['stage'], task['chapter']), ('repair', 2))
        candidate = response(self.app)
        spend = next(item for item in candidate['data']['drift_check']['items'] if item['kind'] == 'resources')
        spend.update(status='deviated', reason='本章多花了一趟车费，实际账面与章纲不同。')
        spend['actual'] = {**spend['actual'], 'to': spend['planned']['to'] - 1}
        candidate['data']['drift_check']['verdict'] = 'deviated'
        with self.assertRaises(Error) as caught:
            self.app.submit(candidate)
        self.assertEqual(caught.exception.code, 'revision_carry')
        # The refused carry rolls the submission back: the parent keeps five chapters, and the
        # revision branch still holds only the prefix it forked from.
        self.assertEqual([r['n'] for r in self.repo.headers('main')], [1, 2, 3, 4, 5])
        branch = self.repo.load()['branch']
        self.assertNotEqual(branch, 'main')
        self.assertEqual([r['n'] for r in self.repo.headers(branch)], [1])

    def test_an_invalid_endpoint_is_refused_without_changing_the_plan(self):
        self.written()
        before = self.repo.get('book')
        for through in ('5', False, 0, [], {}):
            with self.subTest(through=through):
                self.assertCode('revision', self.app.revise, 5, '按作者要求修订。', self.owner, through=through)
                self.assertEqual(self.repo.get('book'), before)

    def test_cli_can_deliver_a_blocked_plan_and_authorize_only_that_plan(self):
        plan = self.blocked(2, {'mode': 'expression'}, 2)
        base = [sys.executable, str(ROOT / 'scripts' / 'novel.py'), '--project', str(self.project),
                '--owner', self.owner]
        result = subprocess.run(base + ['advance', '--compact'], capture_output=True, text=True,
                                encoding='utf-8', check=True)
        proposal = json.loads(result.stdout)['proposal']
        self.assertEqual(proposal['plan_hash'], plan['plan_hash'])
        self.assertTrue(Path(proposal['plan_path']).is_file())
        accepted = subprocess.run(base + ['revise', '--from-chapter', '2', '--reason', '工程作者采纳修复方案。',
                                          '--proposal-hash', proposal['plan_hash'],
                                          '--source', '工程作者明确授权该准确方案。'],
                                  capture_output=True, text=True, encoding='utf-8', check=True)
        self.assertEqual(json.loads(accepted.stdout)['revision_run']['first'], 2)


if __name__ == '__main__':
    unittest.main()
