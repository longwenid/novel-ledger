import ast
import copy
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from novel_ledger.application import Application
from novel_ledger.contracts import ENFORCEMENT, Error, FACT_CHECKS, RESULT, digest, dump
from novel_ledger import delivery, facts, host, planning, workflow
from novel_ledger.sqlite_store import SQLiteRepository
from support import contract, drive, response


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / 'book'
        self.repo = SQLiteRepository.initialize(self.project, workflow.new_book(contract()))
        self.app = Application(self.repo)

    def tearDown(self):
        self.repo.close()
        self.temp.cleanup()

    def assertCode(self, code, fn, *args, **kwargs):
        with self.assertRaises(Error) as caught:
            fn(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)

    def review_task(self):
        return drive(self.app, until='chapter_review')['task']

    def finish(self):
        run = self.app.run(finish=True, source='工程夹具授权写完。')
        final = drive(self.app, run['owner'])
        self.assertEqual(final['action'], 'ready_to_complete')
        return run['owner']

    def test_complete_two_volumes_and_immutable_snapshot(self):
        self.repo.save(workflow.new_book(contract(4, 2)))
        owner = self.finish()
        result = self.app.complete(owner)
        self.assertEqual(result['chapters'], 4)
        self.assertTrue(self.app.audit()['ok'])
        snapshot = self.repo.read_document(result['snapshot_hash'])
        self.assertEqual(len(snapshot['chapters']), 4)
        output = delivery.export_book(self.repo, output=Path(self.temp.name) / 'book-plain.html')
        self.assertIn('第4章', Path(output['path']).read_text(encoding='utf-8'))
        self.assertTrue(self.app.complete(owner)['idempotent'])

    def test_repeated_advance_keeps_a_worker_form_and_replaces_a_stale_template(self):
        drive(self.app, until='write')
        self.repo.cancel_pending('rebuild probe')
        task = self.app.advance()['task']
        base = Path(task['task_path']).parent
        template_path = base / 'result.template.json'
        payload = json.loads(template_path.read_text(encoding='utf-8'))
        payload['data']['title'] = 'WORKER-EDIT'
        template_path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
        self.assertEqual(self.app.advance()['task']['task_id'], task['task_id'])
        kept = json.loads(template_path.read_text(encoding='utf-8'))
        self.assertEqual(kept['data']['title'], 'WORKER-EDIT')
        self.assertIn('self_check', kept['data'])
        stale = {'schema': RESULT, 'task_id': 'stale-task', 'input_hash': 'stale-hash', 'session': '', 'data': {}}
        template_path.write_text(json.dumps(stale, ensure_ascii=False), encoding='utf-8')
        self.app.advance()
        replaced = json.loads(template_path.read_text(encoding='utf-8'))
        self.assertEqual(replaced['task_id'], task['task_id'])
        self.assertEqual(replaced['input_hash'], task['input_hash'])

    def test_blind_gate_hides_formal_files_and_writer_evaluation(self):
        task = self.review_task()
        base = Path(task['task_path']).parent
        self.assertEqual(task['delivery_phase'], 'first_read')
        self.assertFalse((base / 'input.json').exists())
        self.assertCode('first_read_sealed', self.app.read, task['task_id'])
        self.assertCode('first_read_sealed', self.app.audit)
        result = response(self.app)
        material = self.app.read(task['task_id'])
        self.assertNotIn('self_check', dump(material))
        self.assertNotIn('writer_summary', dump(material))
        self.assertTrue((base / 'input.json').exists())
        self.app.submit(result)

    def test_first_read_is_frozen_and_same_reviewer_must_finish(self):
        self.review_task()
        result = response(self.app)
        task = self.repo.pending()
        changed = copy.deepcopy(task['first_read'])
        changed['reads'][0]['change'] = '修改了首读。'
        self.assertCode('first_read_frozen', self.app.seal, {'task_id': task['id'], 'input_hash': task['input_hash'], 'session': task['reviewer'], 'data': changed})
        result['session'] = 'different-reviewer'
        self.assertCode('first_read', self.app.submit, result)

    def test_preflight_rolls_back_and_retries_are_idempotent(self):
        self.app.advance()
        result = response(self.app)
        before = dump(self.repo.load())
        checked = self.app.submit(result, preview=True)
        self.assertTrue(checked['checked'])
        self.assertEqual(dump(self.repo.load()), before)
        self.assertEqual(self.repo.pending()['id'], result['task_id'])
        self.app.submit(result)
        self.assertTrue(self.app.submit(result)['idempotent'])
        result['data']['intent'] = '不同内容。'
        self.assertCode('replay_conflict', self.app.submit, result)

    def test_rejection_does_not_commit_fact_or_spend_budget(self):
        self.review_task()
        result = response(self.app)
        result['data']['facts']['events'][0]['before'] = 99
        before = dump(self.repo.load())
        self.assertCode('time_conflict', self.app.submit, result)
        self.assertEqual(dump(self.repo.load()), before)
        self.assertEqual(self.repo.headers('main'), [])

    def test_missing_check_and_bad_quote_are_rejected(self):
        self.review_task()
        result = response(self.app)
        result['data']['reader']['checks'].pop()
        self.assertCode('review_coverage', self.app.submit, result)
        result = response(self.app)
        result['data']['facts']['checks'][0]['evidence'][0] = {'chapter': 1, 'quote': '正文中不存在的句子。'}
        self.assertCode('evidence', self.app.submit, result)

    def test_short_prose_preserved_and_rework_is_bounded(self):
        drive(self.app, until='write')
        stages = []
        for _ in range(4):
            task = self.repo.pending() or self.app.advance()['task']
            result = response(self.app)
            stages.append(self.repo.pending()['input']['stage'])
            result['data']['prose'] = '他走了。'
            self.app.submit(result)
        self.assertEqual(stages, ['write', 'repair', 'repair', 'redesign'])
        self.assertEqual(self.repo.load()['draft']['prose'], '他走了。')
        self.assertEqual(self.repo.load()['rework']['1'], {'repairs': 2, 'redesigns': 1, 'initial_used': True})
        self.assertEqual(self.app.status()['status'], 'paused')
        self.assertCode('repair_budget', self.app.resume)

    def test_first_chapter_approval_binds_exact_version(self):
        final = drive(self.app, until='chapter_review')
        self.app.submit(response(self.app))
        handoff = self.app.advance()
        self.assertEqual(handoff['action'], 'await_author')
        self.assertCode('pilot_version', self.app.approve, 'wrong', '作者认可。')
        self.app.approve(handoff['prose_hash'], '作者认可这版。')
        self.assertEqual(self.app.advance()['action'], 'target_reached')

    def test_new_workers_cannot_reuse_session_or_self_review(self):
        self.app.advance()
        result = response(self.app, session='same-session')
        self.app.submit(result)
        self.app.advance()
        other = response(self.app, session='same-session')
        self.assertCode('session_reuse', self.app.submit, other)

    def test_restart_rebuilds_same_pending_material(self):
        task = self.app.advance()['task']
        Path(task['task_path']).unlink()
        self.repo.close()
        self.repo = SQLiteRepository(self.project)
        self.app = Application(self.repo)
        restored = self.app.advance()['task']
        self.assertEqual(restored['task_id'], task['task_id'])
        self.assertEqual(restored['input_hash'], task['input_hash'])
        self.assertTrue(Path(restored['task_path']).is_file())

    def test_advance_requires_real_submission_and_rejects_old_callback(self):
        task = self.app.advance()['task']
        self.assertEqual(self.app.advance(after=task['task_id'])['action'], 'wait_for_submit')
        self.app.submit(response(self.app))
        following = self.app.advance(after=task['task_id'])['task']
        self.app.submit(response(self.app))
        self.assertEqual(self.app.advance(after=task['task_id'])['action'], 'resync')
        self.assertEqual(self.app.advance(after=following['task_id'])['action'], 'task_ready')

    def test_cancelled_receipt_never_commits(self):
        self.app.advance()
        result = response(self.app)
        self.app.pause('作者暂停。', cancel=True)
        self.app.resume()
        self.assertCode('stale_task', self.app.submit, result)
        self.assertNotEqual(self.app.advance()['task']['task_id'], result['task_id'])

    def test_controller_lease_fences_second_controller(self):
        run = self.app.run(through=2)
        self.assertCode('controller_lease', self.app.advance)
        self.assertEqual(self.app.advance(owner=run['owner'])['action'], 'task_ready')

    def test_worker_claim_and_expiry_fence_stale_result(self):
        task = self.app.advance()['task']
        claim = self.app.claim(task['task_id'], 'claimed')
        self.assertEqual(self.app.claim(task['task_id'], 'claimed')['token'], claim['token'])
        self.assertCode('worker_busy', self.app.claim, task['task_id'], 'another')
        result = response(self.app, session='claimed', claim=claim['token'])
        lease = self.repo.get('claim:' + task['task_id'])
        lease['until'] = 0
        self.repo.put('claim:' + task['task_id'], lease)
        replacement = self.app.claim(task['task_id'], 'replacement')
        self.assertCode('worker_lease', self.app.submit, result)
        self.app.submit(response(self.app, session='replacement', claim=replacement['token']))

    def test_revision_preserves_formal_branch_until_review_and_promotion(self):
        owner = self.finish()
        self.app.revise(2, '作者要求改结尾表达。', owner)
        status = self.app.status()
        self.assertEqual(status['formal_chapters'], 2)
        self.assertEqual(status['accepted_chapters'], 1)
        self.assertCode('revision', self.app.promote, owner)
        self.assertEqual(drive(self.app, owner)['action'], 'revision_ready')
        result = self.app.promote(owner)
        self.assertEqual(result['formal_branch'], result['branch'])
        self.assertTrue(self.app.audit()['ok'])

    def test_discard_restores_old_goal_and_prose(self):
        owner = self.finish()
        old = self.repo.chapter('main', 2)
        self.app.revise(2, '试改后再决定。', owner)
        self.app.advance(owner=owner)
        self.app.discard(owner)
        self.assertEqual(self.repo.chapter('main', 2), old)
        self.assertTrue(self.repo.load()['finish'])

    def test_discard_preserves_already_spent_repair_budget(self):
        owner = self.finish()
        self.app.revise(2, '修订表达。', owner)
        self.app.advance(owner=owner)
        self.app.submit(response(self.app))
        self.app.discard(owner)
        self.assertEqual(self.repo.load()['rework']['2']['repairs'], 1)

    def test_lexical_override_is_versioned_and_applies_from_the_opening_stage(self):
        self.assertEqual(self.app.advance()['task']['stage'], 'book_plan')
        with self.assertRaises(Error) as caught:
            self.app.set_lexical({'forbidden_name_chars': ['砚']}, '')
        self.assertEqual(caught.exception.code, 'author_source')
        with self.assertRaises(Error) as caught:
            self.app.set_lexical({'unknown_rule': []}, '作者改规则。')
        self.assertEqual(caught.exception.code, 'lexical_policy')
        # a project rule the author adds, then lifts: both versions stay on record
        self.app.set_lexical({'forbidden_name_chars': ['砚']}, '作者要求人物名不得用砚字。')
        self.assertEqual(planning.policy_of(self.repo.load())['forbidden_name_chars'], ['砚'])
        self.app.set_lexical({'forbidden_name_chars': []}, '作者允许主角名用砚字。')
        versions = self.repo.load()['lexical_policy']
        self.assertEqual([v['version'] for v in versions], [1, 2, 3])
        self.assertEqual(planning.policy_of(self.repo.load())['forbidden_name_chars'], [])
        self.assertEqual(planning.policy_of(self.repo.load())['forbidden_terms'], ['账本', '入账', '回执'])
        raw = contract()
        raw['entities'][0]['name'] = '沈砚'
        raw['protagonist_setup']['name'] = '沈砚'
        self.assertEqual(planning.validate_contract(raw)['entities'][0]['name'], '沈砚')
        self.assertIsNone(self.repo.pending())
        with self.assertRaises(Error) as caught:
            self.app.set_lexical({'forbidden_name_chars': []}, '同一规则再写一次。')
        self.assertEqual(caught.exception.code, 'lexical_policy')

    def test_recontract_cannot_reopen_free_initial_draft(self):
        drive(self.app, until='write')
        result = response(self.app)
        result['data']['prose'] = '他走了。'
        self.app.submit(result)
        self.app.recontract(contract(), '作者改约，文学修复额度继续有效。')
        self.app.advance()
        self.app.submit(response(self.app))
        self.assertEqual(drive(self.app, until='repair')['task']['stage'], 'repair')
        self.app.submit(response(self.app))
        self.assertEqual(self.repo.load()['rework']['1']['repairs'], 1)
        self.app.advance()
        obligations = self.repo.pending()['input']['obligations']
        self.assertTrue(any('汉字篇幅' in o['text'] for o in obligations))

    def test_recontract_is_reviewed_and_old_branch_can_be_restored(self):
        owner = self.finish()
        changed = contract()
        changed['reader_promise'] = '工人在退件纠纷中保住同事的工作。'
        self.app.recontract(changed, '作者明确修改读者承诺。', owner)
        self.assertNotEqual(self.repo.load()['contract']['reader_promise'], changed['reader_promise'])
        self.assertEqual(self.app.advance(owner=owner)['task']['stage'], 'contract_review')
        self.app.submit(response(self.app))
        self.assertEqual(self.app.advance(owner=owner)['task']['stage'], 'book_plan')
        self.assertEqual(self.repo.load()['contract']['reader_promise'], changed['reader_promise'])
        self.app.discard(owner)
        self.assertIsNone(self.repo.load().get('pending_contract'))
        self.assertEqual(self.app.advance(owner=owner)['action'], 'ready_to_complete')

    def test_audit_detects_modified_document_and_projection(self):
        self.finish()
        row = self.repo.chapter('main', 1)
        self.repo.db.execute('UPDATE documents SET value=? WHERE hash=?', (dump('被篡改的正文。'), row['prose']))
        self.assertCode('source_integrity', self.app.audit)

    def test_complete_never_relaxes_word_target(self):
        raw = contract()
        raw['word_range'] = [390, 400]
        self.repo.save(workflow.new_book(raw))
        owner = self.finish()
        self.assertCode('word_target', self.app.complete, owner)
        self.assertEqual(self.repo.load()['contract']['word_range'], [390, 400])

    def test_lexical_enforcement_scope_is_declared_and_exercised(self):
        """The declared coverage and the enforced coverage come from one table, at every stage."""
        handle = self.app.advance()['task']
        material = self.repo.task(handle['task_id'])['input']
        policy = material['policy']
        self.assertEqual(policy['version'], 1)
        self.assertEqual(policy['source'], '内置默认')
        self.assertEqual(policy['forbidden_terms'], ['账本', '入账', '回执'])
        self.assertEqual(policy['forbidden_name_chars'], [])
        self.assertEqual(policy['scope']['terms'], list(ENFORCEMENT[material['stage']]['terms']))
        self.assertIn('prose', ENFORCEMENT['write']['terms'])
        self.assertIn('lexical', policy['editable'])
        # every stage that declares coverage really runs it
        for stage, scope in ENFORCEMENT.items():
            self.assertTrue(scope.get('terms') or scope.get('names'), stage)
        self.assertIn('opening_options', ENFORCEMENT)

    def test_plan_stage_honours_an_author_name_override(self):
        """A plan's new entity is a name: it must be judged by the active project policy."""
        self.app.set_lexical({'forbidden_name_chars': ['砚']}, '作者要求人物名不得用砚字。')
        drive(self.app, until='plan')
        work = self.repo.pending()['input']
        self.assertEqual(work['policy']['forbidden_name_chars'], ['砚'])
        self.assertEqual(work['policy']['scope']['names'], ['new_entities'])
        blocked = {'plans': [dict(chapter=work['first'], goal='核对封条。', obstacle='主管阻拦。', choice='查记录。',
                                  cost='得罪同事。', change='拿到签字。', ending='追问来源。',
                                  node_ids=['volume:v1'], participants=['shen'],
                                  new_entities=[{'id': 'yan', 'name': '沈砚', 'kind': 'person'}])]}
        with self.assertRaises(Error) as caught:
            self.app.submit({**response(self.app), 'data': blocked})
        self.assertEqual(caught.exception.code, 'literal_policy')
        self.assertIn('砚', json.dumps(caught.exception.details, ensure_ascii=False))
        # the author lifts the rule; the next plan is judged by the new version, not the old one
        self.app.set_lexical({'forbidden_name_chars': []}, '作者允许人物名用砚字。')
        self.app.advance()
        work = self.repo.pending()['input']
        self.assertEqual(work['policy']['version'], 3)
        self.assertEqual(work['policy']['forbidden_name_chars'], [])
        allowed = {'plans': [dict(chapter=work['first'], goal='核对封条。', obstacle='主管阻拦。', choice='查记录。',
                                  cost='得罪同事。', change='拿到签字。', ending='追问来源。',
                                  node_ids=['volume:v1'], participants=['shen'],
                                  new_entities=[{'id': 'yan', 'name': '沈砚', 'kind': 'person'}])]}
        self.app.submit({**response(self.app), 'data': allowed})
        stored = self.repo.load()['plans'][str(work['first'])]
        self.assertEqual(stored['new_entities'][0]['name'], '沈砚')

    def test_opening_option_text_is_checked_not_only_the_name(self):
        """The dispatch declares the whole option; the machine must inspect the whole option."""
        from novel_ledger import creation

        state = creation.begin()
        board = creation.offer(state, {
            'gate': 'genre',
            'options': [
                {'id': 'A', 'title': '夜班退件', 'premise': '他把入账记录摊在桌上。', 'driver': '核对封条与签字。',
                 'pitch': '一箱退件，一张签错的封条。',
                 'scene': ['夜班仓库里，他把退件箱推到灯下核对封条。', '凌晨的登记台前，他逐页翻自己经手的那栏。'],
                 'tradeoff': '相比另两案，选它要放弃更快的升级节奏。', 'fit_reason': '承接夜班题材，落在具体物件上。',
                 'value': {'genre': '都市生活', 'reader_promise': '查清责任。', 'red_lines': [], 'allow_special_mechanism': False}},
                {'id': 'B', 'title': '另一条路', 'premise': '换一种推进。', 'driver': '从对手的账目往回查。',
                 'pitch': '他先查对手，再查自己。',
                 'scene': ['白天的主管办公室里，他盯着对方的签字栏。', '雨夜的码头，他等一个送货人开口。'],
                 'tradeoff': '相比另两案，选它要放弃更稳的开局。', 'fit_reason': '承接夜班题材，把压力放在对手线上。',
                 'value': {'genre': '都市生活', 'reader_promise': '换一个承诺。', 'red_lines': [], 'allow_special_mechanism': False}},
            ]})
        self.assertEqual(board['board']['options'][0]['title'], '夜班退件')      # offer() alone stores what it got
        with self.assertRaises(Error) as caught:
            planning.enforce(planning.resolve_policy({}), 'opening_options',
                             {'gate': 'genre', 'options': board['board']['options']})
        self.assertEqual(caught.exception.code, 'literal_policy')
        fields = {row['field'] for row in caught.exception.details['violations']['forbidden_terms']}
        self.assertIn('options.premise', fields)

    def test_export_cannot_overwrite_database(self):
        self.assertCode('output', delivery.export_book, self.repo, self.project / 'novel.sqlite3')

    def test_preparing_project_activates_only_reviewed_contract(self):
        self.repo.save(workflow.preparing_book('作者先给了一个想法。'))
        self.assertEqual(self.app.advance()['action'], 'preparing')
        self.assertCode('creation', self.app.run, through=2)
        self.app.recontract(contract(), '作者补全了方向和体量。')
        self.assertIsNone(self.repo.load()['contract'])
        self.assertEqual(self.app.advance()['task']['stage'], 'contract_review')
        self.app.submit(response(self.app))
        self.assertEqual(self.app.advance()['task']['stage'], 'book_plan')
        self.assertIsNotNone(self.repo.load()['contract'])

    def test_atomic_initialize_never_overwrites_existing_book(self):
        self.app.advance()
        original = self.repo.pending()['id']
        self.assertCode('exists', SQLiteRepository.initialize, self.project, workflow.new_book(contract()))
        self.assertEqual(self.repo.pending()['id'], original)

    def test_two_connections_get_one_identical_pending_task(self):
        first = self.app.advance()['task']
        other = SQLiteRepository(self.project)
        try:
            second = Application(other).advance()['task']
            self.assertEqual(first['task_id'], second['task_id'])
        finally:
            other.close()

    def test_projection_corruption_is_detected(self):
        self.finish()
        book = self.repo.load()
        book['state']['clock'] = 99
        self.repo.save(book)
        self.assertCode('projection', self.app.audit)

    def test_sealed_first_read_hash_is_verified_on_recovery(self):
        task = self.review_task()
        response(self.app)
        changed = self.repo.task(task['task_id'])['first_read']
        changed['reads'][0]['obstacle'] = '数据库中被修改。'
        self.repo.db.execute('UPDATE tasks SET first_read=? WHERE id=?', (dump(changed), task['task_id']))
        self.assertCode('first_read_integrity', self.app.advance)

    def test_scope_review_is_chunked_and_then_independently_synthesized(self):
        raw = contract(5)
        raw['review_chunk'] = 2
        self.repo.save(workflow.new_book(raw))
        run = self.app.run(finish=True)
        head = drive(self.app, run['owner'], until='scope_review')
        spans = []
        for _ in range(3):
            work = self.repo.pending()['input']
            spans.append((work['first'], work['last']))
            self.app.submit(response(self.app))
            self.app.advance(owner=run['owner'])
        self.assertEqual(spans, [(1, 2), (3, 4), (5, 5)])
        work = self.repo.pending()['input']
        self.assertEqual(work['stage'], 'scope_synthesis')
        records = self.app.read(self.repo.pending()['id'])['records']
        self.assertEqual(len(records['scope_parts']['value']), 3)
        self.assertFalse(work['blind'])

    def test_scope_review_rejects_incomplete_actual_chapter_coverage(self):
        run = self.app.run(finish=True)
        drive(self.app, run['owner'], until='scope_review')
        result = response(self.app)
        result['data']['coverage'].pop()
        self.assertCode('scope_coverage', self.app.submit, result)
        self.assertEqual(self.repo.load()['scope_parts'], {})

    def test_design_repairs_do_not_reset_attempts(self):
        self.app.advance()
        self.app.submit(response(self.app))
        for attempt in range(3):
            self.app.advance()
            result = response(self.app)
            result['data']['verdict'] = 'fix'
            result['data']['checks'][0]['result'] = 'fix'
            ref = result['data']['checks'][0]['evidence'][0]
            result['data']['findings'] = [dict(criterion='author_constraints', severity='quality', reason='工程设计缺陷。', evidence=ref, target_chapter=0, repair_scope='chapter')]
            self.app.submit(result)
            self.assertEqual(self.repo.load()['proposal']['attempts'], attempt + 1)
            if attempt < 2:
                self.assertEqual(self.app.advance()['task']['stage'], 'book_plan')
                self.app.submit(response(self.app))
        self.assertEqual(self.app.status()['status'], 'paused')
        self.assertCode('repair_budget', self.app.resume)

    def test_fact_fix_and_short_repair_share_one_budget(self):
        self.review_task()
        result = response(self.app)
        result['data']['reader']['verdict'] = 'fix'
        row = result['data']['reader']['checks'][0]
        row['result'] = 'fix'
        result['data']['reader']['findings'] = [dict(criterion='read_on', severity='quality', reason='追读理由不足。', evidence=row['evidence'][0], target_chapter=1, repair_scope='chapter')]
        self.app.submit(result)
        self.app.advance()
        repair = response(self.app)
        repair['data']['prose'] = '他走了。'
        self.app.submit(repair)
        draft = self.repo.load()['draft']
        self.assertTrue(any(f['criterion'] == 'read_on' for f in draft['findings']))
        self.assertTrue(any(f['criterion'] == 'substance' for f in draft['findings']))
        self.assertEqual(self.repo.load()['rework']['1']['repairs'], 1)

    def test_host_runs_real_process_and_verifies_cli_submission(self):
        task = drive(self.app, until='chapter_review')['task']
        result = host.step(self.app, [sys.executable, str(ROOT / 'tests' / 'process_worker.py')])
        self.assertEqual(result['action'], 'worker_finished')
        self.assertTrue(result['submitted'])
        self.assertEqual(result['exit_code'], 0)
        self.assertEqual(self.app.status()['accepted_chapters'], 1)

    def test_host_cannot_mistake_zero_exit_for_submission(self):
        result = host.step(self.app, [sys.executable, '-c', 'pass'])
        self.assertEqual(result['action'], 'needs_attention')
        self.assertFalse(result['submitted'])
        self.assertIsNotNone(self.repo.pending())

    def test_host_reports_launch_failure_and_releases_claim(self):
        result = host.step(self.app, ['/nonexistent-host'])
        self.assertEqual(result['action'], 'host_launch_failed')
        self.assertIsNone(self.repo.get('claim:' + result['task_id']))

    def test_worker_process_cannot_take_controller_actions(self):
        result = host.step(self.app, [sys.executable, str(ROOT / 'tests' / 'process_worker.py'), 'controller'])
        self.assertEqual(result['action'], 'needs_attention')
        self.assertEqual(result['exit_code'], 2)
        self.assertIn('worker_boundary', Path(result['log']).read_text(encoding='utf-8', errors='replace'))

    def test_host_does_not_fabricate_resume_of_frozen_model_session(self):
        task = self.review_task()
        response(self.app)
        result = host.step(self.app, [sys.executable, '-c', 'pass'])
        self.assertEqual(result['action'], 'resume_session_required')
        self.assertEqual(result['task_id'], task['task_id'])

    def test_role_boundary_keeps_the_controller_out_of_prose(self):
        command = [sys.executable, str(ROOT / 'scripts' / 'novel.py'), '--project', str(self.project)]
        task = self.app.advance()['task']
        controller = subprocess.run(command + ['read', '--task', task['task_id']], text=True, capture_output=True,
                                    encoding='utf-8', errors='replace')
        self.assertEqual(controller.returncode, 2)
        self.assertEqual(json.loads(controller.stdout)['error'], 'role_boundary')
        environment = {**os.environ, 'NOVEL_TASK_ID': task['task_id'], 'NOVEL_SESSION': 'qc-worker-' + task['task_id'][:8]}
        dispatcher = subprocess.run(command + ['read', '--task', task['task_id']], text=True, capture_output=True,
                                    encoding='utf-8', errors='replace', env=environment)
        self.assertEqual(json.loads(dispatcher.stdout)['task_id'], task['task_id'])
        foreign = {**os.environ, 'NOVEL_TASK_ID': 'some-other-task', 'NOVEL_SESSION': 'qc-worker-foreign'}
        outsider = subprocess.run(command + ['read', '--task', task['task_id']], text=True, capture_output=True,
                                  encoding='utf-8', errors='replace', env=foreign)
        self.assertEqual(json.loads(outsider.stdout)['error'], 'worker_boundary')

    def test_legacy_database_is_refused_after_the_schema_change(self):
        older = Path(self.temp.name) / 'v1'
        older.mkdir()
        (older / 'novel.sqlite3').write_text('schema 声明为旧版的库', encoding='utf-8')
        with self.assertRaises(Error) as caught:
            SQLiteRepository(older)
        self.assertEqual(caught.exception.code, 'schema')

    def test_cancelling_a_task_retires_its_form(self):
        task = self.app.advance()['task']
        base = Path(task['task_path']).parent
        self.assertTrue((base / 'input.json').is_file())
        self.assertTrue((base / 'result.template.json').is_file())
        self.app.pause('作者暂停', cancel=True)
        self.assertFalse((base / 'input.json').exists())
        self.assertFalse((base / 'result.template.json').exists())

    def test_export_refuses_to_clobber_the_book_view(self):
        with self.assertRaises(Error) as caught:
            delivery.export_book(self.repo)
        self.assertEqual(caught.exception.code, 'output')
        allowed = delivery.export_book(self.repo, output=Path(self.temp.name) / 'plain.html')
        self.assertEqual(Path(allowed['path']).name, 'plain.html')

    def test_export_and_audit_refuse_a_project_without_a_contract(self):
        unstarted = Path(self.temp.name) / 'unstarted'
        subprocess.run([sys.executable, str(ROOT / 'scripts' / 'novel.py'), '--project', str(unstarted), 'init'],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
        for command in ('export', 'audit'):
            proc = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'novel.py'),
                                   '--project', str(unstarted), command],
                                  capture_output=True, text=True, encoding='utf-8', errors='replace')
            self.assertEqual(proc.returncode, 2, proc.stderr)
            self.assertEqual(json.loads(proc.stdout)['error'], 'contract')

    def test_cli_rejects_unknown_database_and_supports_project_after_command(self):
        command = [sys.executable, str(ROOT / 'scripts' / 'novel.py'), 'status', '--project', str(self.project)]
        result = subprocess.run(command, text=True, capture_output=True, encoding='utf-8', errors='replace')
        self.assertEqual(result.returncode, 0, result.stderr)
        other = Path(self.temp.name) / 'legacy'
        other.mkdir()
        (other / 'novel.sqlite3').write_text('未知旧库内容。', encoding='utf-8')
        command[-1] = str(other)
        result = subprocess.run(command, text=True, capture_output=True, encoding='utf-8', errors='replace')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)['error'], 'schema')


class DomainTests(unittest.TestCase):
    def test_resource_precondition_and_conservation(self):
        before = facts.seed(contract())
        event = {'op': 'resource', 'from': 'shen', 'to': None, 'asset': '车费', 'unit': '元', 'quantity': '2', 'from_before': '4', 'reason': '乘车。', 'evidence': {'chapter': 1, 'quote': '他付了两元车费。'}}
        state, _ = facts.settle(before, [event], '他付了两元车费。', 1)
        self.assertEqual(state['resources'][facts.resource_key('shen', '车费', '元')], '2')
        self.assertEqual(before['resources'][facts.resource_key('shen', '车费', '元')], '4')
        event['quantity'] = '5'
        with self.assertRaises(Error):
            facts.settle(before, [event], '他付了两元车费。', 1)

    def test_parallel_time_does_not_advance_main_clock(self):
        state, _ = facts.settle(facts.seed(contract()), [{'op': 'clock', 'thread': 'side', 'before': 0, 'after': 3, 'evidence': {'chapter': 1, 'quote': '三天后'}}], '三天后，他回来。', 1)
        self.assertEqual(state['clock'], 0)
        self.assertEqual(state['clock_threads']['side'], 3)

    def test_historical_assertion_has_no_resource_or_clock_effect(self):
        before = facts.seed(contract())
        event = {'op': 'historical_assertion', 'id': 'past', 'subjects': ['shen'], 'claim': '曾在这里值夜班。', 'source': '直接回忆。', 'occurred_at': {'basis': 'main_clock', 'start': -3, 'end': -1}, 'evidence': {'chapter': 1, 'quote': '他想起以前的夜班。'}}
        after, _ = facts.settle(before, [event], '他想起以前的夜班。', 1)
        self.assertEqual(after['resources'], before['resources'])
        self.assertEqual(after['clock'], 0)

    def test_ambiguous_evidence_requires_exact_position(self):
        with self.assertRaises(Error):
            facts.evidence({'chapter': 1, 'quote': '他走了'}, {1: '他走了，又回来了。他走了。'})
        self.assertEqual(facts.evidence({'chapter': 1, 'start': 9, 'quote': '他走了'}, {1: '他走了，又回来了。他走了。'})['start'], 9)

    def test_spatial_seed_and_move(self):
        raw = contract()
        raw.update(places=[{'id': 'a', 'name': '门口'}, {'id': 'b', 'name': '房间', 'parent': 'a'}], placements={'shen': 'a'})
        state, _ = facts.settle(facts.seed(raw), [{'op': 'move', 'entity': 'shen', 'before': 'a', 'after': 'b', 'route': '走进门内。', 'reason': '核对退件。', 'evidence': {'chapter': 1, 'quote': '他走进房间。'}}], '他走进房间。', 1)
        self.assertEqual(state['placements']['shen'], 'b')

    def test_contract_and_names_are_checked_before_initialization(self):
        raw = contract()
        raw['entities'][0]['name'] = '沈砚'
        raw['protagonist_setup']['name'] = '沈砚'
        # the built-in default bans no character, so a name is only rejected when the author says so
        self.assertEqual(workflow.new_book(raw)['contract']['entities'][0]['name'], '沈砚')
        with self.assertRaises(Error) as caught:
            planning.check_contract_names(raw, planning.resolve_policy({'forbidden_name_chars': ['砚']}))
        self.assertEqual(caught.exception.code, 'literal_policy')
        self.assertIn('砚', json.dumps(caught.exception.details, ensure_ascii=False))
        raw['unknown_field'] = '旧版本残留字段'
        with self.assertRaises(Error) as caught:
            workflow.new_book(raw)
        self.assertEqual(caught.exception.code, 'contract')
        self.assertIn('未知约定字段', caught.exception.message)

    def test_architecture_diagram_products_match_their_source(self):
        def block(text):
            match = re.search(r'```mermaid\n(.*?)```', text, re.S)
            return (match.group(1) if match else text).strip()

        source = block((ROOT / 'references' / 'architecture.md').read_text(encoding='utf-8'))
        self.assertEqual(block((ROOT / 'docs' / 'architecture.mmd').read_text(encoding='utf-8')), source)
        self.assertIn(source, (ROOT / 'README.md').read_text(encoding='utf-8'))

    def test_all_imports_including_deferred_are_acyclic_and_domains_have_no_io(self):
        graph = {}
        pure = {'contracts', 'facts', 'planning', 'quality', 'workflow', 'creation', 'world'}
        for path in (ROOT / 'scripts' / 'novel_ledger').glob('*.py'):
            deps = set()
            tree = ast.parse(path.read_text(encoding='utf-8'), feature_version=(3, 9))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.level == 1:
                    deps.update([node.module] if node.module else [a.name for a in node.names])
                if path.stem in pure and isinstance(node, ast.Import):
                    self.assertFalse({a.name.split('.')[0] for a in node.names} & {'sqlite3', 'pathlib', 'subprocess', 'os'})
            graph[path.stem] = deps
            if path.stem in pure:
                self.assertFalse(deps - pure)
        def visit(name, trail):
            self.assertNotIn(name, trail, str(trail))
            for dependency in graph.get(name, set()):
                visit(dependency, trail + [name])
        for name in graph:
            visit(name, [])


if __name__ == '__main__':
    unittest.main()
