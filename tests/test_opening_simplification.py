"""The opening pipeline's shape scales with the book: measured from the 2026-10-18 run.

That live micro book (t0, 17 chapters, opened to validate the flow) paid 14 cold dispatches
between the gates and the first outline batch, five more batches were still pending, and the
run halted for an author decision over one quality finding whose fix was a single wording
change. These tests pin the shape decisions that pay that back: single-volume tiers outline in
one batch — or none, when the outline rides the skeleton dispatch and one review covers both —
an exhausted budget routes by what remains instead of by round count, and the finding-field
rules are told in the rejection instead of probed with scratch candidates.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'tests'))

from novel_ledger import quality, workflow, world
from novel_ledger.bootstrap import local_application as Application
from novel_ledger.contracts import CHECKS_VERSION, Error, REPAIRS
from novel_ledger.sqlite_store import SQLiteRepository
from support import contract, response
from test_opening_v2 import combined, model, options, receipt, review_data


class FindingRuleTests(unittest.TestCase):
    """R5: the target_chapter rule is stated with its valid values, not discovered by probing."""

    def review(self, **finding):
        ref = {'chapter': 0, 'quote': '冻结材料原文。'}
        return {'verdict': 'fix', 'checks_version': CHECKS_VERSION,
                'checks': [{'id': 'causality', 'result': 'fix', 'reason': '工程反例。', 'evidence': [dict(ref)]}],
                'findings': [{'criterion': 'causality', 'severity': 'quality', 'reason': '工程反例。',
                              'evidence': dict(ref), **finding}]}

    def test_a_chapter_the_task_does_not_hold_is_named_in_the_rejection(self):
        with self.assertRaises(Error) as caught:
            quality.checks(self.review(target_chapter=7, repair_scope='local'), ('causality',), {0: '冻结材料原文。'})
        self.assertEqual(caught.exception.code, 'repair_scope')
        details = caught.exception.details
        self.assertEqual(details['valid_chapters'], [0])
        self.assertEqual(details['got'], 7)
        self.assertIn('chapter 0', details['rule'])

    def test_an_unknown_repair_scope_lists_the_valid_scopes(self):
        with self.assertRaises(Error) as caught:
            quality.checks(self.review(target_chapter=0, repair_scope='volume'), ('causality',), {0: '冻结材料原文。'})
        self.assertEqual(caught.exception.code, 'repair_scope')
        self.assertEqual(caught.exception.details['valid_scopes'], ['local', 'chapter'])


class OutlineBatchTests(unittest.TestCase):
    """R2: the outline batch knife follows the tier, not the writing-time rolling window."""

    def batch_for(self, band, words, chapters):
        contract_rows = {'chapter_min': band[0], 'chapter_max': band[1], 'chapter_aim': (band[0] + band[1]) // 2,
                         'word_range': words, 'planning_window': 3,
                         'volume_outline': {'scope': 'rolling', 'words': 500, 'tolerance': 50},
                         'volumes': [{'id': 'v1', 'purpose': '查明来源。', 'first': 1, 'end': chapters}]}
        book = {'contract': contract_rows, 'designs': {'volume:v1': {'chapters': [], 'world_hash': 'x'}}}
        return workflow.next_outline(book, contract_rows['volumes'][0])

    def test_a_single_volume_tier_outlines_the_whole_volume_in_one_batch(self):
        job = self.batch_for((2000, 3500), [4000, 7000], 2)
        self.assertEqual((job.stage, job.first, job.last), ('volume_outline', 1, 2))

    def test_short_and_compact_tiers_also_outline_whole_volumes(self):
        # t1/t2 carry the same declaration: a 25-chapter volume is minutes of work, and the
        # lead-time argument for small rolling batches does not exist at this size.
        job = self.batch_for((1800, 3500), [90000, 175000], 25)
        self.assertEqual((job.first, job.last), (1, 25))
        job = self.batch_for((2200, 4000), [220000, 400000], 25)
        self.assertEqual((job.first, job.last), (1, 25))

    def test_a_long_tier_keeps_the_rolling_window_knife(self):
        job = self.batch_for((2500, 4500), [450000, 810000], 143)
        self.assertEqual((job.first, job.last), (1, 3))       # planning_window stays the bound


class SimplifiedOpeningTests(unittest.TestCase):
    """The t0 opening: one merged skeleton+outline dispatch, one review, no batch parade."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / 'book'
        self.repo = SQLiteRepository.initialize(self.project,
                                                workflow.preparing_book(guided=True, opening_version=2))
        self.app = Application(self.repo)

    def tearDown(self):
        self.repo.close()
        self.temp.cleanup()

    def choose_current_gate(self, tier='t0'):
        handoff = self.app.advance()
        if handoff['action'] == 'await_choice':
            board = handoff['board']
            if board['gate']['id'] == 'scale':
                self.app.opening_tier(tier, '作者指定该档。')
                return
        else:
            self.app.submit(receipt(self.app, options(self.app)))
            board = self.app.advance()['board']
        self.app.opening_choice(board['options'][0]['id'], board['hash'], '作者选它。')

    def to_design_review(self, tier='t0'):
        for _gate in range(10):
            self.choose_current_gate(tier)
        self.assertEqual(self.app.advance()['task']['stage'], 'world_model')
        data = combined(self.app)
        data['contract']['volume_outline'] = {'scope': 'rolling', 'words': 500, 'tolerance': 50}
        self.app.submit(receipt(self.app, data))
        self.assertEqual(self.app.advance()['task']['stage'], 'world_review')
        self.app.submit(receipt(self.app, review_data(self.app)))
        handoff = self.app.advance()                      # contract_ready: activation, then the dispatch
        if handoff.get('action') == 'contract_ready':
            handoff = self.app.advance()
        return handoff

    def fix_review(self, severity='quality', scope='local'):
        data = review_data(self.app)
        ref = data['checks'][0]['evidence'][0]
        data['verdict'] = 'fix'
        data['checks'][0].update(result='fix', reason='工程反例。')
        data['findings'] = [{'criterion': data['checks'][0]['id'], 'severity': severity,
                             'reason': '工程反例：找到退件来源。这一处的骨架与窗口不一致。',
                             'evidence': ref, 'target_chapter': 0, 'repair_scope': scope}]
        return data

    def test_a_pre_contract_world_brief_keeps_the_tier_scoped_domains(self):
        """The world dispatch runs before the contract exists, so the tier comes from the choice.

        Without that fallback a t0 project's brief asked for all ten domains while the check
        accepted six: the worker wrote records nobody reads and the reviewer charged them as
        off-tier padding — the drift the world domain table was supposed to have closed.
        """
        for _gate in range(10):
            self.choose_current_gate()
        self.assertEqual(self.app.advance()['task']['stage'], 'world_model')
        brief = self.repo.pending()['input']['brief']
        domains = brief.split('## 本档位要填的领域')[1].split('\n\n')[0]
        # The tier's six domains are the ones asked for; the other four may only appear as
        # "keep them empty", never as an extra writing request.
        asked = domains.split('其余领域')[0]
        for name in world.TIER_SECTIONS['t0']:
            self.assertIn(name, asked)
        for name in ('geography', 'history', 'factions', 'economy'):
            self.assertNotIn(name, asked)
        self.assertIn('保留为空数组', domains)
        # The size section is not dropped on the one dispatch that has no contract to read it from.
        size = brief.split('## 规模要与已选体量相称')[1].split('\n\n')[0]
        self.assertIn('微型档', size)
        self.assertIn('1 卷', size)

    def test_the_skeleton_dispatch_carries_the_volume_outline_and_one_review_covers_both(self):
        handoff = self.to_design_review()
        self.assertEqual(handoff['task']['stage'], 'book_plan')
        self.assertEqual(handoff['task']['stages'], ['book_plan', 'volume_outline'])
        work = self.repo.pending()['input']
        policy = work['payload']['volume_outline']
        self.assertEqual((policy['first'], policy['last']), (1, 2))
        self.assertIn('逐章卷纲', work['brief'])
        # A first design review still reads the full set; the contract that skipped its own
        # review is judged here, and the audit says so honestly.
        self.assertIn('state', work['required'])
        self.assertIn('world_model', work['required'])
        self.assertEqual(self.repo.load()['contract_review']['reviewer'], 'design_review(merged)')
        self.app.submit(response(self.app))                     # skeleton + outlines in one receipt
        review = self.app.advance()
        self.assertEqual(review['task']['stage'], 'design_review')
        brief = self.repo.pending()['input']['brief']
        self.assertIn('合并档', brief)
        self.assertIn('约定随设计核验', brief)
        self.app.submit(receipt(self.app, review_data(self.app)))
        book = self.repo.load()
        volume_design = book['designs']['volume:v1']
        self.assertEqual([c['chapter'] for c in volume_design['chapters']], [1, 2])
        self.assertEqual(volume_design['outline_reviews'][0]['reviewer'], review['task']['review_session']
                         or volume_design['outline_reviews'][0]['reviewer'])
        # The outline is complete: nothing dispatches another outline batch.
        self.assertIsNone(workflow.next_outline(book, book['contract']['volumes'][0]))

    def test_a_longer_tier_still_gets_its_own_contract_review(self):
        handoff = self.to_design_review(tier='t2')
        self.assertEqual(handoff['task']['stage'], 'contract_review')

    def test_a_repaired_world_moves_under_the_contract_back_to_its_own_review(self):
        for _gate in range(10):
            self.choose_current_gate()
        self.assertEqual(self.app.advance()['task']['stage'], 'world_model')
        data = combined(self.app)
        data['contract']['volume_outline'] = {'scope': 'rolling', 'words': 500, 'tolerance': 50}
        self.app.submit(receipt(self.app, data))
        self.assertEqual(self.app.advance()['task']['stage'], 'world_review')
        review = review_data(self.app)
        ref = review['checks'][0]['evidence'][0]
        review['verdict'] = 'fix'
        review['checks'][0].update(result='fix', reason='工程反例。')
        review['findings'] = [{'criterion': review['checks'][0]['id'], 'severity': 'quality',
                               'reason': '这条规则不成句：夜班退件必须登记负责人。',
                               'evidence': ref, 'target_chapter': 0, 'repair_scope': 'local'}]
        self.app.submit(receipt(self.app, review))
        self.assertEqual(self.app.advance()['task']['stage'], 'world_model')   # repair
        repaired = model(self.app)
        repaired['rules'][0]['principle'] = '夜班退件必须由当班负责人当场登记并签字。'
        self.app.submit(receipt(self.app, repaired))
        self.assertEqual(self.app.advance()['task']['stage'], 'world_review')  # re-check
        self.app.submit(receipt(self.app, review_data(self.app)))
        # The contract was drafted against the old rule; the engine's alignment check refuses to
        # activate it blind, and the separate contract review is dispatched instead.
        self.assertEqual(self.app.advance()['task']['stage'], 'contract_review')

    def test_a_merged_candidate_repairs_as_one_artifact_and_the_recheck_reads_the_diff(self):
        self.to_design_review()
        self.app.submit(response(self.app))
        self.assertEqual(self.app.advance()['task']['stage'], 'design_review')
        self.app.submit(receipt(self.app, self.fix_review()))
        repair = self.app.advance()['task']
        self.assertEqual(repair['stage'], 'book_plan')
        self.assertEqual(repair['stages'], ['book_plan', 'volume_outline'])   # the combined shape survives repair
        self.app.submit(response(self.app))
        diff = self.repo.load()['proposal']['repair_diff']
        self.assertTrue(diff['named_by_findings'] or diff['changed'])
        self.assertTrue(diff['findings'])                       # the re-review checks each was answered
        recheck = self.app.advance()
        self.assertEqual(recheck['task']['stage'], 'design_review')
        work = self.repo.pending()['input']
        self.assertIn('repair_diff', work['records'])
        self.assertEqual(sorted(work['required']), ['contract', 'proposal', 'repair_diff'])
        self.assertNotIn('state', work['required'])             # proven-unchanged context moves to on-demand
        self.assertIn('返修后重核', work['brief'])
        self.app.submit(receipt(self.app, review_data(self.app)))
        self.assertEqual([c['chapter'] for c in self.repo.load()['designs']['volume:v1']['chapters']], [1, 2])

    def test_exhausted_minor_findings_are_recorded_and_the_book_moves_on(self):
        self.to_design_review()
        self.app.submit(response(self.app))
        for _round in range(REPAIRS):
            self.assertEqual(self.app.advance()['task']['stage'], 'design_review')
            self.app.submit(receipt(self.app, self.fix_review(severity='quality', scope='local')))
            self.assertEqual(self.app.advance()['task']['stage'], 'book_plan')
            self.app.submit(response(self.app))
        self.assertEqual(self.app.advance()['task']['stage'], 'design_review')
        self.app.submit(receipt(self.app, self.fix_review(severity='quality', scope='local')))
        book = self.repo.load()
        self.assertEqual(book['status'], 'running')             # no halt over a wording-level finding
        self.assertIsNone(book.get('author_block'))
        self.assertIsNone(book['proposal'])
        self.assertEqual(book['accepted_findings'][-1]['stage'], 'design_review')
        self.assertEqual([c['chapter'] for c in book['designs']['volume:v1']['chapters']], [1, 2])

    def test_exhausted_blockers_still_reach_the_author(self):
        self.to_design_review()
        self.app.submit(response(self.app))
        for _round in range(REPAIRS):
            self.assertEqual(self.app.advance()['task']['stage'], 'design_review')
            self.app.submit(receipt(self.app, self.fix_review(severity='blocker', scope='local')))
            self.assertEqual(self.app.advance()['task']['stage'], 'book_plan')
            self.app.submit(response(self.app))
        self.assertEqual(self.app.advance()['task']['stage'], 'design_review')
        self.app.submit(receipt(self.app, self.fix_review(severity='blocker', scope='local')))
        book = self.repo.load()
        self.assertEqual(book['status'], 'paused')
        self.assertEqual(book['author_block']['id'], 'repair-exhausted:design_review')


class PlanSeedTests(unittest.TestCase):
    """E: a plan whose window sits inside the reviewed outline starts from a seeded template."""

    def test_the_template_is_seeded_from_the_reviewed_outline(self):
        from novel_ledger import result_templates
        seed = [{'chapter': 1, 'synopsis': '沈桐核对封条并发现笔迹矛盾。',
                 'node_ids': ['book'], 'world_refs': ['rules:r1']}]
        data = result_templates.template('plan', 1, {}, payload={'outline_seed': seed})
        row = data['plans'][0]
        self.assertEqual(row['chapter'], 1)
        self.assertEqual(row['node_ids'], ['book'])
        self.assertEqual(row['world_refs'], ['rules:r1'])
        for field in ('goal', 'obstacle', 'choice', 'cost', 'change', 'ending'):
            self.assertEqual(row[field], '沈桐核对封条并发现笔迹矛盾。')

    def test_six_copies_of_one_sentence_are_rejected_but_refinements_pass(self):
        from novel_ledger import planning
        def row(**fields):
            base = {'chapter': 1, 'goal': '查清来源。', 'obstacle': '开箱违规。', 'choice': '核对封条。',
                    'cost': '承担责任。', 'change': '发现矛盾。', 'ending': '追问签字人。',
                    'node_ids': ['book'], 'participants': ['shen']}
            base.update(fields)
            return base
        with self.assertRaises(Error) as caught:
            planning.validate_plans({'plans': [row(obstacle='查清来源。', choice='查清来源。',
                                                   cost='查清来源。', change='查清来源。', ending='查清来源。')]},
                                     1, 1, {'book'}, {'entities': {'shen': {}}}, contract())
        self.assertEqual(caught.exception.code, 'plan')
        self.assertIn('各自回答不同问题', caught.exception.message)
        planning.validate_plans({'plans': [row()]}, 1, 1, {'book'}, {'entities': {'shen': {}}}, contract())

    def test_a_plan_dispatch_inside_the_outline_carries_the_seed(self):
        from test_pipeline_shapes import long_prose, micro_contract
        from support import response as drive_response
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        project = Path(temp.name) / 'book'
        base = micro_contract(chapters=2, volumes=1)
        base['volume_outline'] = {'scope': 'rolling', 'words': 500, 'tolerance': 50}
        repo = SQLiteRepository.initialize(project, workflow.new_book(base))
        self.addCleanup(repo.close)
        app = Application(repo)
        owner = app.run(through=2, source='工程夹具授权写两章。')['owner']
        for _ in range(80):
            handoff = app.advance(owner=owner)
            if handoff.get('action') != 'task_ready':
                break
            work = repo.pending()['input']
            if work['stage'] == 'plan':
                seed = work['payload'].get('outline_seed')
                self.assertTrue(seed)
                self.assertEqual([row['chapter'] for row in seed],
                                 list(range(work['first'], work['last'] + 1)))
                self.assertIn('模板已按已核验卷纲预填', work['brief'])
                blank = json.loads(Path(handoff['task']['template_path']).read_text(encoding='utf-8'))['data']['plans']
                self.assertEqual([row['chapter'] for row in blank], [row['chapter'] for row in seed])
                self.assertEqual(blank[0]['node_ids'], seed[0]['node_ids'])
                return
            result = drive_response(app)
            if result['data'].get('prose') is not None:
                result['data']['prose'] = long_prose(work['chapter'])
            app.submit(result)
        self.fail('did not reach a seeded plan dispatch')


if __name__ == '__main__':
    unittest.main()
