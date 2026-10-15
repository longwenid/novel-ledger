"""Review-triggered history repair has a bounded, source-bound execution plan."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from novel_ledger import editorial, workflow
from novel_ledger.bootstrap import local_application as Application
from novel_ledger.contracts import Error
from novel_ledger.sqlite_store import SQLiteRepository
from support import contract
from test_narrative import tracked_contract
from test_editorial import drive, enhanced_response


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

    def root(self, scope='volume:v1', volumes=1):
        raw = tracked_contract(6)
        raw['editorial_features'] = True
        raw['volumes'] = contract(6, volumes)['volumes']
        self.repo = SQLiteRepository.initialize(self.project, workflow.new_book(raw))
        self.app = Application(self.repo)
        self.owner = self.app.run(finish=True, source='工程夹具：授权完成全书。')['owner']
        for _ in range(300):
            handoff = self.app.advance(owner=self.owner)
            if handoff['action'] == 'await_author':
                self.app.approve(handoff['prose_hash'], '工程作者认可准确首章。', self.owner)
                continue
            self.assertEqual(handoff['action'], 'task_ready')
            work = self.repo.pending()['input']
            if work['stage'] == 'scope_synthesis' and work['scope'] == scope and 'closure' in work['payload']:
                return
            self.app.submit(enhanced_response(self.app))
        self.fail('未到达指定范围审。')

    def finding(self, first, last=None, changes=None):
        result = enhanced_response(self.app)
        data = result['data']
        ref = {'chapter': first, 'quote': '次日'}
        data['verdict'] = 'fix'
        next(r for r in data['checks'] if r['id'] == 'payoffs')['result'] = 'fix'
        data['findings'] = [{'criterion': 'payoffs', 'severity': 'quality', 'reason': '本章余波需修改。',
                             'evidence': ref, 'target_chapter': first, 'repair_scope': 'local'}]
        data['closure'].update(decision='revise_range', range=[first, first if last is None else last],
            changes={'mode': 'expression'} if changes is None else changes,
            repair_case={'root_ref': 'aftermath', 'goal': '修好余波的阅读作用。',
                         'verification_condition': '修改后关系作用清楚。', 'evidence': ref},
            remedy={'mechanism': '局部调整余波。', 'substantive_change': '保留事实，只调整具体表达。'})
        data['closure']['checks'][4]['result'] = 'defect'
        return result

    def test_local_root_fix_does_not_rewrite_to_the_scope_end(self):
        self.root()
        formal = self.repo.headers('main')
        result = self.finding(5)
        self.app.submit(result, preview=True)
        self.assertEqual(self.repo.headers('main'), formal)
        self.assertIsNone(self.repo.load()['revision_run'])
        self.app.submit(result)
        book = self.repo.load()
        self.assertEqual(book['revision_run']['first'], 5)
        self.assertEqual(book['revision_run']['last'], 5)
        self.assertEqual(book['revision_run']['impact']['chapter_actions'][-1]['action'], 'keep')
        self.assertEqual(drive(self.app, self.owner)['action'], 'revision_ready')
        candidate = self.repo.chapter(self.repo.load()['branch'], 6)
        self.assertEqual(candidate['prose'], formal[-1]['prose'])
        self.assertEqual(self.repo.headers('main'), formal)
        self.assertTrue(self.app.audit()['ok'])

    def test_reading_fix_preserves_suffix_prose_after_independent_review(self):
        self.root()
        before = self.repo.headers('main')[-1]['prose']
        self.app.submit(self.finding(5, changes={'mode': 'reading',
            'reading_changes': [{'kind': 'character', 'key': 'shen'}]}))
        book = self.repo.load()
        self.assertEqual(book['revision_run']['last'], 5)
        self.assertEqual(book['revision_run']['impact']['chapter_actions'][-1]['action'], 'review')
        self.assertEqual(drive(self.app, self.owner, until='revision_review')['task']['stage'], 'revision_review')
        self.assertEqual(drive(self.app, self.owner)['action'], 'revision_ready')
        self.assertEqual(self.repo.headers(self.repo.load()['branch'])[-1]['prose'], before)

    def test_old_local_fix_is_saved_without_changing_branch_or_spending_chapter_budget(self):
        self.root()
        headers, rework = self.repo.headers('main'), copy.deepcopy(self.repo.load()['rework'])
        task_id = self.repo.pending()['id']
        self.app.submit(self.finding(2))
        book = self.repo.load()
        self.assertEqual(book['branch'], 'main')
        self.assertIsNone(book['revision_run'])
        self.assertEqual(book['rework'], rework)
        self.assertEqual(self.repo.headers('main'), headers)
        self.assertEqual(self.repo.task(task_id)['status'], 'done')
        handoff = self.app.advance(after=task_id, owner=self.owner, compact=True)
        self.assertEqual(handoff['action'], 'revision_blocked')
        self.assertEqual(handoff['proposal']['violations'], ['outside_recent_window'])
        plan = json.loads(Path(handoff['proposal']['plan_path']).read_text(encoding='utf-8'))
        self.assertEqual(plan['impact']['first'], 2)
        self.assertEqual(plan['impact']['last'], 2)
        self.assertEqual(plan['impact']['chapter_actions'][-1]['action'], 'keep')
        self.assertCode('revision_bounds', self.app.resume, self.owner)

    def test_semantic_expansion_is_reported_before_any_rewrite(self):
        self.root()
        self.app.submit(self.finding(2, changes={'mode': 'semantic', 'changes': []}))
        plan = self.repo.load()['revision_directive']
        self.assertEqual(plan['through'], 2)
        self.assertEqual(plan['impact']['last'], 6)
        self.assertIn('rewrite_limit', plan['violations'])
        self.assertEqual(self.repo.load()['branch'], 'main')
        self.assertIsNone(self.repo.load()['draft'])

    def test_closed_volume_blocks_even_a_recent_single_chapter_fix(self):
        self.root(scope='book', volumes=2)
        self.app.submit(self.finding(6))
        plan = self.repo.load()['revision_directive']
        self.assertEqual(plan['violations'], ['closed_volume'])
        self.assertEqual(plan['impact']['last'], 6)
        self.assertEqual(self.repo.load()['branch'], 'main')

    def test_previous_closed_volume_does_not_block_the_current_unclosed_volume(self):
        self.root(scope='volume:v2', volumes=2)
        self.app.submit(self.finding(5))
        book = self.repo.load()
        self.assertIsNotNone(book['revision_run'])
        self.assertEqual(book['revision_run']['first'], 5)
        self.assertEqual(book['revision_run']['last'], 5)

    def test_scope_revise_command_cannot_bypass_the_automatic_limit(self):
        self.root()
        self.app.submit(self.finding(2))
        self.app.revise(2, '按审稿修订。', self.owner, through=2, changes={'mode': 'expression'})
        self.assertEqual(self.app.advance(owner=self.owner)['action'], 'revision_blocked')
        self.assertIsNone(self.repo.load()['revision_run'])
        self.assertEqual(len(next(iter(self.repo.load()['repair_cases'].values()))['rounds']), 1)

    def test_review_driven_revision_rejects_invalid_ends_without_changing_the_plan(self):
        self.root()
        self.app.submit(self.finding(2))
        original = self.repo.get('book')
        for through in ('2', False, 1, [], {}):
            with self.subTest(through=through):
                self.assertCode('revision', self.app.revise, 2, '按审稿修订。', self.owner, through=through)
                self.assertEqual(self.repo.get('book'), original)

    def test_explicit_plan_authorization_is_bound_to_hash_range_and_source(self):
        self.root()
        self.app.submit(self.finding(2))
        plan = self.repo.load()['revision_directive']
        key = plan['plan_hash']
        self.assertCode('author_source', self.app.revise, 2, '采纳。', self.owner, proposal_hash=key)
        self.assertCode('revision_proposal', self.app.revise, 2, '采纳。', self.owner,
                        proposal_hash='old-hash', source='工程作者授权。')
        self.assertCode('revision_proposal', self.app.revise, 1, '采纳。', self.owner,
                        proposal_hash=key, source='工程作者授权。')
        self.assertCode('revision_proposal', self.app.revise, 2, '采纳。', self.owner, through=6,
                        proposal_hash=key, source='工程作者授权。')
        self.app.revise(2, '采纳。', self.owner, proposal_hash=key, source='工程作者明确授权本方案修改第二章。')
        book = self.repo.load()
        self.assertEqual(book['revision_run']['last'], 2)
        self.assertEqual(book['decisions'][-1]['plan_hash'], key)
        self.assertIsNone(self.app.status()['revision_proposal'])
        self.assertEqual(len(next(iter(book['repair_cases'].values()))['rounds']), 1)
        self.assertEqual(drive(self.app, self.owner)['action'], 'revision_ready')
        self.assertTrue(self.app.audit()['ok'])

    def test_closed_range_protects_the_accepted_chapters_without_freezing_later_appendices(self):
        book = workflow.new_book(tracked_contract(6))
        book['scope_closures'] = {'volume:v1': {'first': 1, 'last': 4}}
        policy = editorial.revision_policy(book, 6)
        self.assertIn('closed_volume', editorial.revision_violations(policy, {'first': 4, 'last': 4}))
        self.assertEqual(editorial.revision_violations(policy, {'first': 5, 'last': 6}), [])
        # Legacy closures without explicit bounds retain conservative protection.
        book['scope_closures']['volume:v1'] = {}
        self.assertIn('closed_volume', editorial.revision_violations(
            editorial.revision_policy(book, 6), {'first': 5, 'last': 6}))

    def test_changed_context_invalidates_an_old_plan_authorization(self):
        self.root()
        self.app.submit(self.finding(2))
        book = self.repo.load()
        key = book['revision_directive']['plan_hash']
        book['plans']['6']['ending'] = '上下文已变化，旧授权不得套用。'
        self.repo.save(book)
        self.assertCode('revision_proposal', self.app.revise, 2, '采纳。', self.owner,
                        proposal_hash=key, source='工程作者授权旧方案。')
        self.assertEqual(self.repo.load()['branch'], 'main')

    def test_lexical_change_invalidates_authorization_until_the_plan_is_refreshed(self):
        self.root()
        self.app.submit(self.finding(2))
        old = self.repo.load()['revision_directive']
        self.app.set_lexical({'forbidden_terms': ['临时禁词']}, '工程作者改变字面规则。', self.owner)
        self.assertCode('revision_proposal', self.app.revise, 2, '采纳旧方案。', self.owner,
                        proposal_hash=old['plan_hash'], source='工程作者对旧上下文方案的授权。')
        self.app.revise(2, '重新分析原缺陷。', self.owner, through=old['through'], changes=old['changes'])
        refreshed = self.repo.load()['revision_directive']
        self.assertNotEqual(refreshed['plan_hash'], old['plan_hash'])
        self.app.revise(2, '采纳当前方案。', self.owner,
                        proposal_hash=refreshed['plan_hash'], source='工程作者明确授权当前方案。')
        self.assertEqual(self.repo.load()['revision_run']['last'], 2)

    def test_author_recontract_can_finish_review_without_reexecuting_a_blocked_plan(self):
        self.root()
        self.app.submit(self.finding(2))
        original = self.repo.load()
        changed = copy.deepcopy(original['contract'])
        changed['reader_promise'] = '工程作者明确改变作品的阅读承诺。'
        self.app.recontract(changed, '工程作者明确要求按新承诺改约。', self.owner)
        self.assertEqual(self.app.advance(owner=self.owner)['task']['stage'], 'contract_review')
        self.assertEqual(self.app.submit(enhanced_response(self.app))['status'], 'running')
        self.assertEqual(self.app.advance(owner=self.owner)['task']['stage'], 'book_plan')
        activated = self.repo.load()
        self.assertEqual(activated['contract']['reader_promise'], changed['reader_promise'])
        self.assertEqual(activated['repair_cases'], original['repair_cases'])
        self.assertEqual(activated['rework'], original['rework'])
        self.assertIsNone(self.app.status()['revision_proposal'])
        self.app.discard(self.owner)
        self.assertEqual(self.repo.load()['revision_directive'], original['revision_directive'])
        self.assertEqual(self.app.advance(owner=self.owner)['action'], 'revision_blocked')

    def test_new_protocol_rejects_unrelated_rewind_and_invalid_change_spec_atomically(self):
        self.root()
        result = self.finding(5)
        result['data']['closure']['range'] = [4, 5]
        self.assertCode('revision_range', self.app.submit, result)
        result['data']['closure']['range'] = [5, 5]
        result['data']['closure']['changes'] = {}
        self.assertCode('revision_impact', self.app.submit, result)
        self.assertIsNone(self.repo.load().get('repair_cases'))
        self.assertEqual(self.repo.pending()['id'], result['task_id'])

    def test_blocked_plan_preflight_rolls_back_cases_and_artifacts(self):
        self.root()
        before = self.repo.get('book')
        result = self.finding(2)
        self.app.submit(result, preview=True)
        self.assertEqual(self.repo.get('book'), before)
        self.assertIsNone(self.app.status()['revision_proposal'])
        self.assertFalse(list((self.project / 'work').glob('revision-*.json')))

    def test_legacy_root_keeps_its_frozen_range_semantics_and_still_obeys_execution_bounds(self):
        self.root()
        work = copy.deepcopy(self.repo.pending()['input'])
        work['payload']['closure'].pop('revision_policy')
        self.repo.cancel_pending('工程夹具：模拟旧冻结根审。')
        self.repo.add_task(work)
        result = self.finding(2)
        # A newer same-named changes field must not grant an old protocol a narrow repair.
        self.app.submit(result)
        plan = self.repo.load()['revision_directive']
        self.assertEqual(plan['changes']['mode'], 'semantic')
        self.assertEqual(plan['through'], 6)
        self.assertEqual(plan['impact']['last'], 6)
        self.assertIn('rewrite_limit', plan['violations'])
        self.assertEqual(self.repo.load()['branch'], 'main')

    def test_cli_can_deliver_a_blocked_plan_and_authorize_only_that_plan(self):
        self.root()
        self.app.submit(self.finding(2))
        base = [sys.executable, str(ROOT / 'scripts' / 'novel.py'), '--project', str(self.project), '--owner', self.owner]
        result = subprocess.run(base + ['advance', '--compact'], capture_output=True, text=True,
                                encoding='utf-8', check=True)
        proposal = json.loads(result.stdout)['proposal']
        self.assertTrue(Path(proposal['plan_path']).is_file())
        accepted = subprocess.run(base + ['revise', '--from-chapter', '2', '--reason', '工程作者采纳修复方案。',
            '--proposal-hash', proposal['plan_hash'], '--source', '工程作者明确授权该准确方案。'],
            capture_output=True, text=True, encoding='utf-8', check=True)
        self.assertEqual(json.loads(accepted.stdout)['revision_run']['last'], 2)


if __name__ == '__main__':
    unittest.main()
