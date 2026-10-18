import copy
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from novel_ledger.bootstrap import local_application as Application, local_workspace
from novel_ledger.contracts import CHECKS_VERSION, ENFORCEMENT, Error, RESULT, dump
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
        output = delivery.export_book(self.repo, output=Path(self.temp.name) / 'book-plain.html', workspace=local_workspace(self.repo))
        self.assertIn('第4章', Path(output['path']).read_text(encoding='utf-8'))
        self.assertTrue(self.app.complete(owner)['idempotent'])

    def test_scene_openings_allow_same_day_chapters_and_interior_time_evidence(self):
        self.repo.save(workflow.new_book(contract(3)))
        owner = self.app.run(finish=True, source='工程夹具授权验证三章时间衔接。')['owner']
        prose = [
            '沈桐把箱子推到主管面前，指着封条上的签字，要求核对退件来源，主管却按住了箱盖。',
            '“先把责任栏填上。”主管把登记册塞给沈桐。他没有接，反而抽出封条，指给主管看另一处笔迹。',
            '封条被主管扣进抽屉，沈桐攥紧了空白的责任单。次日，他带着退件人的签字回来，把两份笔迹并排放下。',
        ]
        for n, chapter_prose in enumerate(prose, 1):
            self.assertEqual(drive(self.app, owner, until='write')['task']['chapter'], n)
            draft = response(self.app)
            draft['data']['prose'] = chapter_prose
            self.app.submit(draft)
            drive(self.app, owner, until='chapter_review')
            review = response(self.app)
            review['data']['facts'].update(elapsed_days=0 if n < 3 else 1, events=[])
            if n == 3:
                review['data']['facts']['events'] = [
                    {'op': 'clock', 'before': 0, 'after': 1,
                     'evidence': {'chapter': n, 'quote': '次日'}},
                ]
            self.app.submit(review)
            self.assertEqual(self.repo.load()['state']['clock'], 0 if n < 3 else 1)
        self.assertEqual(drive(self.app, owner)['action'], 'ready_to_complete')
        self.app.complete(owner)
        self.assertTrue(self.app.audit()['ok'])
        output = delivery.export_book(self.repo, output=Path(self.temp.name) / 'scene-openings.md', format='md', workspace=local_workspace(self.repo))
        exported = Path(output['path']).read_text(encoding='utf-8')
        for chapter_prose in prose:
            self.assertIn(chapter_prose, exported)

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
        self.assertTrue(checked['valid'])
        self.assertFalse(checked['committed'])
        self.assertEqual(dump(self.repo.load()), before)
        self.assertEqual(self.repo.pending()['id'], result['task_id'])
        committed = self.app.submit(result)
        self.assertTrue(committed['valid'])
        self.assertTrue(committed['committed'])
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
        # The spent chapter budget is an author decision, not a wall: resume hands up the question.
        status = self.app.resume()
        self.assertEqual(status['status'], 'paused')
        self.assertEqual(status['author_decision']['id'], 'repair-exhausted:chapter_repair')
        self.assertIn('第 1 章', status['author_decision']['question'])
        # Accepting keeps the formal chapter and records the reviewer's findings as open items.
        accepted = self.app.answer('repair-exhausted:chapter_repair', workflow.ACCEPT_OPEN, '这一处我承担。')
        self.assertEqual(accepted['status'], 'running')
        book = self.repo.load()
        self.assertIsNone(book['draft'])
        self.assertTrue(book['carry_findings'])
        self.assertEqual(book['accepted_findings'][0]['scope'], 'chapter:1')

    def test_a_spent_repair_budget_hands_the_decision_to_the_author(self):
        """A converging candidate used to dead-end: resume refused and there was no channel at all.

        The world candidate of a real book went 14 -> 7 -> 4 -> 3 findings and then hit the budget.
        Neither escape (recontract, opening back) is proportionate to three local fixes, so the stop
        becomes an author decision instead of a wall.
        """
        findings = [{'criterion': 'economic_consequences', 'severity': 'quality', 'reason': '指标算不平。',
                     'evidence': [{'chapter': 0, 'quote': '一年三到五个'}], 'target_chapter': 0,
                     'repair_scope': 'local'}]
        book = self.repo.load()
        book['proposal'] = {'scope': 'world', 'chapter': 1, 'data': {'premise': '工程候选。'},
                            'producer': 'controller-1', 'attempts': 3, 'findings': findings,
                            'needs_repair': True}
        book.update(status='paused', pause_reason='世界模型核验修复耗尽，候选保留。')
        self.repo.save(book)
        status = self.app.resume()
        self.assertEqual(status['status'], 'paused')
        decision = status['author_decision']
        self.assertEqual(decision['id'], 'repair-exhausted:world_review')
        self.assertEqual([row['label'] for row in decision['options']],
                         [workflow.REPAIR_AGAIN, workflow.ACCEPT_OPEN, decision['options'][2]['label']])
        # One more round restores exactly one repair, and the candidate is re-dispatched.
        granted = self.app.answer(decision['id'], workflow.REPAIR_AGAIN, '这几条都得改透。', 'controller-1')
        self.assertEqual(granted['status'], 'running')
        reloaded = self.repo.load()
        self.assertEqual(reloaded['proposal']['attempts'], 2)
        self.assertTrue(reloaded['proposal']['needs_repair'])
        # Accepting instead keeps the findings on the record rather than turning them into a pass.
        book = self.repo.load()
        book['proposal']['attempts'] = 3
        book.update(status='paused', pause_reason='世界模型核验修复耗尽，候选保留。')
        self.repo.save(book)
        status = self.app.resume()
        accepted = self.app.answer(status['author_decision']['id'], workflow.ACCEPT_OPEN,
                                   '这一处我承担，先往下走。', 'controller-1')
        self.assertEqual(accepted['status'], 'running')
        book = self.repo.load()
        self.assertIsNone(book['proposal'])
        self.assertEqual(book['world']['premise'], '工程候选。')
        self.assertEqual(book['accepted_findings'][0]['stage'], 'world_review')
        self.assertEqual(book['carry_findings'][-1]['criterion'], 'economic_consequences')

    def test_answering_a_pending_author_decision_releases_the_halt(self):
        block = {'id': 'death-detail', 'question': '录音能不能带出铁门内的内容？',
                 'options': [{'label': '不能', 'impact': '录音须改写。'}, {'label': '能', 'impact': '禁令改写为另一条。'}]}
        book = self.repo.load()
        book['author_block'] = copy.deepcopy(block)
        book.update(status='paused', pause_reason=block['question'])
        self.repo.save(book)
        status = self.app.status()
        self.assertEqual(status['author_decision']['id'], 'death-detail')
        self.assertEqual(len(status['author_decision']['options']), 2)
        # The whole point of a handed-up decision: resume cannot bypass it.
        self.assertCode('author_decision', self.app.resume)
        self.assertCode('author_decision', self.app.answer, 'death-detail', '第三条路', '作者原话', 'controller-1')
        self.assertCode('author_decision', self.app.answer, 'voice-range', '不能', '作者原话', 'controller-1')
        answered = self.app.answer('death-detail', '不能', '铁门内不留记录，录音也不能例外。', 'controller-1')
        self.assertIsNone(answered['author_decision'])
        self.assertEqual((answered['status'], answered['pause_reason']), ('running', None))
        record = self.repo.load()['author_decision_history'][-1]
        self.assertEqual(record['question']['id'], 'death-detail')
        self.assertEqual(record['resolution'], {'result': 'answered', 'option': '不能',
                                                'reason': '铁门内不留记录，录音也不能例外。'})
        self.assertEqual(record['reviewer'], 'controller-1')
        # The question is closed: it cannot be answered twice.
        self.assertCode('author_decision', self.app.answer, 'death-detail', '不能', '再答一次', 'controller-1')
        # The command is wired end to end: no pending decision means an explicit refusal, not a crash.
        blocked = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'novel.py'), '--project', str(self.project),
                                  '--owner', 'controller-1', 'answer', '--decision-id', 'death-detail',
                                  '--option', '不能', '--source', '作者原话'],
                                 text=True, capture_output=True, encoding='utf-8', errors='replace')
        self.assertEqual(blocked.returncode, 2)
        self.assertEqual(json.loads(blocked.stdout)['error'], 'author_decision')

    def test_a_second_full_read_only_hands_over_what_is_still_new(self):
        """A real run spent more characters re-sending records than on every envelope together.

        The journal already knows what a task was handed, so a plain read returns the remainder and
        names the records it skipped; `--all` and `--record` stay available for a deliberate re-read.
        """
        task = self.app.advance()['task']
        first = self.app.read(task['task_id'])
        self.assertTrue(first['records'], 'first read hands over the required records')
        second = self.app.read(task['task_id'])
        self.assertEqual(second['records'], {})
        self.assertEqual(sorted(second['already_read']), sorted(first['records']))
        self.assertIn('--all', second['already_read_note'])
        again = self.app.read(task['task_id'], everything=True)
        self.assertEqual(sorted(again['records']), sorted(first['records']))
        self.assertNotIn('already_read', again)

    def test_a_revision_with_out_of_range_scope_findings_asks_the_author(self):
        """The third shape of one dead end: the run cannot grow and cannot be finished.

        A revision run's own closure review can flag a chapter outside its range. `revise` refuses
        while a run is open and `promote` refuses while the finding stands, so the author decides.
        """
        book = self.repo.load()
        book['revision_run'] = {'parent': 'main', 'first': 3, 'last': 3, 'carry': []}
        book['scope_findings'] = [{'criterion': 'causality', 'severity': 'quality',
                                   'reason': '第二章与第一章逐字重复。', 'evidence': [],
                                   'target_chapter': 2, 'repair_scope': 'local'}]
        book.update(status='paused', pause_reason='跨章核验发现缺陷，按明确 target_chapter 开修订分支。')
        self.repo.save(book)
        status = self.app.resume()
        self.assertEqual(status['author_decision']['id'], 'scope-findings:open-revision')
        self.assertIn('第 2 章', status['author_decision']['question'])
        accepted = self.app.answer('scope-findings:open-revision', workflow.SCOPE_OPTIONS[0]['label'],
                                   '这一处我承担，先把本次修订做完。', 'controller-1')
        self.assertEqual(accepted['status'], 'running')
        book = self.repo.load()
        self.assertIsNone(book.get('scope_findings'))
        self.assertEqual(book['accepted_findings'][0]['scope'], 'open-revision')
        self.assertTrue(book['carry_findings'])
        # The author's second exit names the command instead of silently discarding the run.
        book['scope_findings'] = [{'criterion': 'causality', 'severity': 'quality', 'reason': '再记一条。',
                                   'evidence': [], 'target_chapter': 2, 'repair_scope': 'local'}]
        book.update(status='paused', pause_reason='跨章核验发现缺陷。')
        self.repo.save(book)
        status = self.app.resume()
        held = self.app.answer('scope-findings:open-revision', workflow.SCOPE_OPTIONS[1]['label'],
                               '我先把这次修订撤掉。', 'controller-1')
        self.assertEqual(held['status'], 'paused')
        self.assertIn('discard', held['pause_reason'])

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
        self.assertEqual(self.app.advance(after=task['task_id'], compact=True)['action'], 'wait_for_submit')
        self.app.submit(response(self.app))
        following = self.app.advance(after=task['task_id'], compact=True)['task']
        self.app.submit(response(self.app))
        self.assertEqual(self.app.advance(after=task['task_id'], compact=True)['action'], 'resync')
        self.assertEqual(self.app.advance(after=following['task_id'])['action'], 'task_ready')

    def test_compact_dispatch_keeps_complete_worker_material_and_preserves_its_form(self):
        full = self.app.advance()['task']
        template = Path(full['template_path'])
        form = json.loads(template.read_text(encoding='utf-8'))
        form['data']['intent'] = 'Worker 尚未完成的方案。'
        template.write_text(json.dumps(form, ensure_ascii=False), encoding='utf-8')
        frozen = copy.deepcopy(self.repo.pending()['input'])

        compact = self.app.advance(compact=True)['task']
        stored = json.loads(Path(compact['task_path']).read_text(encoding='utf-8'))
        self.assertLess(len(dump(compact)), len(dump(full)))
        self.assertNotIn('baseline', compact)
        self.assertNotIn('records', compact)
        self.assertNotIn('commands', compact)
        # The render counter and the material size are meant to move between renders; everything
        # else about the preserved material and the untouched form must not.
        for key in ('redispatch_count', 'material_bytes'):
            stored.pop(key, None)
            full.pop(key, None)
        self.assertEqual(stored, full)
        self.assertTrue(Path(stored['input_path']).is_file())
        self.assertEqual(self.repo.pending()['input'], frozen)
        self.assertEqual(json.loads(template.read_text(encoding='utf-8')), form)
        self.assertEqual(self.app.submit(response(self.app))['worker_boundary'], 'finished')

    def test_compact_dispatch_exposes_claim_and_same_reviewer_after_first_read(self):
        handle = self.review_task()
        compact = self.app.advance(compact=True)['task']
        self.assertTrue(compact['requires_new_worker'])
        self.assertIsNone(compact['review_session'])
        locked = json.loads(Path(compact['task_path']).read_text(encoding='utf-8'))
        self.assertNotIn('input_path', locked)
        self.assertNotIn('records', locked)
        self.assertTrue(all(Path(p['path']).is_file() for p in locked['prose_files']))

        claim = self.app.claim(handle['task_id'], 'reviewer-for-current-task')
        compact = self.app.advance(compact=True)['task']
        self.assertEqual(compact['claim'], {'session': claim['session'], 'expired': False})
        self.assertNotIn('token', compact['claim'])
        result = response(self.app, session=claim['session'], claim=claim['token'])
        resumed = self.app.advance(compact=True)['task']
        self.assertEqual(resumed['task_id'], handle['task_id'])
        self.assertEqual(resumed['delivery_phase'], 'formal')
        self.assertFalse(resumed['requires_new_worker'])
        self.assertEqual(resumed['review_session'], claim['session'])
        self.assertCode('first_read', self.app.claim, handle['task_id'], 'another-reviewer')
        self.assertTrue(self.app.submit(result)['accepted'])

    def test_compact_cli_dispatches_a_complete_task_file(self):
        command = [sys.executable, str(ROOT / 'scripts' / 'novel.py'), '--project', str(self.project),
                   'advance', '--compact']
        executed = subprocess.run(command, text=True, capture_output=True, encoding='utf-8', check=True)
        handoff = json.loads(executed.stdout)
        self.assertEqual(handoff['action'], 'task_ready')
        handle = handoff['task']
        stored = json.loads(Path(handle['task_path']).read_text(encoding='utf-8'))
        self.assertEqual(stored['task_id'], handle['task_id'])
        self.assertIn('read', stored['commands'])
        self.assertNotIn('commands', handle)

    def test_compact_loop_preserves_author_boundary_and_reaches_revision_completion_and_delivery(self):
        owner = self.app.run(finish=True, source='工程夹具：授权写完并验收交付。')['owner']

        def until_boundary():
            after = None
            for _ in range(100):
                handoff = self.app.advance(after=after, owner=owner, compact=True)
                if handoff['action'] != 'task_ready':
                    return handoff
                after = handoff['task']['task_id']
                submitted = self.app.submit(response(self.app, task_id=after))
                self.assertTrue(submitted['accepted'])
                self.assertEqual(submitted['worker_boundary'], 'finished')
            self.fail('工程循环未到达业务边界。')

        author = until_boundary()
        self.assertEqual(author['action'], 'await_author')
        self.assertEqual(self.app.status()['accepted_chapters'], 1)
        self.app.approve(author['prose_hash'], '工程夹具作者认可当前首章。', owner)
        self.assertEqual(until_boundary()['action'], 'ready_to_complete')
        self.app.revise(2, '工程夹具：修改末章表达。', owner)
        self.assertEqual(until_boundary()['action'], 'revision_ready')
        self.app.promote(owner)
        self.assertEqual(until_boundary()['action'], 'ready_to_complete')
        completed = self.app.complete(owner)
        self.assertEqual(until_boundary()['action'], 'completed')
        manifest = delivery.deliver_completion(self.repo, workspace=local_workspace(self.repo))
        self.assertEqual(manifest['snapshot_hash'], completed['snapshot_hash'])
        self.assertTrue((self.project / 'book.md').is_file())
        self.assertTrue((self.project / 'delivery.json').is_file())

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

    def test_narrow_revision_carries_unchanged_suffix(self):
        self.repo.save(workflow.new_book(contract(3)))
        owner = self.finish()
        formal3 = self.repo.chapter('main', 3)
        self.app.revise(2, '一词之修。', owner, through=2)
        self.assertEqual(self.app.status()['accepted_chapters'], 1)
        self.assertEqual(drive(self.app, owner)['action'], 'revision_ready')
        carried = self.repo.chapter(self.repo.load()['branch'], 3)
        self.assertEqual(carried['prose'], formal3['prose'])
        self.assertEqual(self.app.status()['accepted_chapters'], 3)
        self.assertTrue(self.app.audit()['ok'])
        self.app.promote(owner)
        self.assertTrue(self.app.audit()['ok'])

    def test_narrow_revision_refuses_carry_when_facts_drift(self):
        self.repo.save(workflow.new_book(contract(3)))
        owner = self.finish()
        self.app.revise(2, '改时钟。', owner, through=2)
        self.assertEqual(self.app.advance(owner=owner)['task']['stage'], 'repair')
        self.app.submit(response(self.app))  # 重写第 2 章并进入章审
        self.assertEqual(self.app.advance(owner=owner)['task']['stage'], 'chapter_review')
        review = response(self.app)
        clock = review['data']['facts']['events'][0]['before']
        review['data']['facts']['events'][0]['after'] = clock + 2
        review['data']['facts']['elapsed_days'] = 2  # 第 3 章冻结事件的时钟前值随之失效
        self.assertCode('revision_carry', self.app.submit, review)
        self.assertEqual(self.app.advance(owner=owner)['task']['stage'], 'chapter_review')

    def test_advance_carries_ledger_baseline(self):
        handoff = drive(self.app, until='write')
        baseline = handoff['task']['baseline']
        self.assertEqual(baseline['clock'], 0)
        self.assertIn('["shen","车费","元"]', baseline['resources'])
        self.assertIsNone(baseline['candidate'])
        on_disk = json.loads(Path(handoff['task']['task_path']).read_text(encoding='utf-8'))
        self.assertEqual(on_disk['baseline']['clock'], 0)

    def test_receipts_record_check_list_version(self):
        self.review_task()
        result = response(self.app)
        self.assertEqual(result['data']['facts']['checks_version'], CHECKS_VERSION)
        self.app.submit(result)
        review = self.repo.read_document(self.repo.chapter('main', 1)['review'])
        self.assertEqual(review['facts']['checks_version'], CHECKS_VERSION)
        self.assertTrue(self.app.audit()['ok'])

    def test_fast_verification_skips_interval_and_merges_blocks(self):
        book = workflow.new_book(contract(4, 1))
        book['contract']['review_interval'] = 2
        book['contract']['verification'] = 'fast'
        self.repo.save(book)
        run = self.app.run(finish=True, source='工程夹具授权写完。')
        owner, blocks = run['owner'], []
        for _ in range(100):
            handoff = self.app.advance(owner=owner)
            if handoff['action'] == 'await_author':
                self.app.approve(handoff['prose_hash'], '工程夹具作者明确认可当前版本。', owner)
                continue
            if handoff['action'] != 'task_ready':
                break
            task = handoff['task']
            if task['stage'] == 'scope_review':
                work = self.repo.task(task['task_id'])['input']
                blocks.append((work['scope'], work['first'], work['last']))
            self.app.submit(response(self.app))
        self.assertEqual(handoff['action'], 'ready_to_complete')
        self.assertFalse(any(scope == 'interval' for scope, _, _ in blocks))
        self.assertIn(('volume:v1', 1, 4), blocks)

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

    def test_a_second_activation_keeps_the_verified_world(self):
        """A re-contract after the first activation used to lose the verified world.

        The world was copied only while the opening phase was still 'contract'; the first
        activation moves that phase to 'ready', so every later amendment continued with
        `world=None` — and the design stages after it bound a null world hash with empty refs.
        """
        from novel_ledger.contract_activation import ContractActivation

        class Repo:
            def __init__(self):
                self.book = None
            def put(self, key, value):
                return None
            def get(self, key, default=None):
                return default
            def headers(self, branch):
                return []
            def save(self, book):
                self.book = book
            def record(self, action, value):
                return None

        proposal = {'data': contract(2), 'producer': 'controller', 'source': '作者改约原话。'}
        old = {'pending_contract': proposal, 'lexical_policy': [], 'creation': {'phase': 'ready'},
               'world': {'premise': '已核验的世界。'}, 'world_review': {'receipt': {}},
               'feedback': [], 'rework': {}, 'revision': 0, 'branch': 'main', 'target': 2,
               'finish': False, 'draft': None}
        book = ContractActivation(Repo()).activate(old)
        self.assertEqual(book['world'], {'premise': '已核验的世界。'})
        self.assertEqual(book['world_review'], {'receipt': {}})
        self.assertTrue(book['opening_world_only'])
        self.assertEqual(book['creation']['phase'], 'ready')

    def test_contract_activation_preserves_project_lexical_versions(self):
        self.app.set_lexical({'forbidden_terms': ['临时禁词'], 'forbidden_name_chars': ['禁']}, '工程作者指定项目字面规则。')
        versions = self.repo.load()['lexical_policy']
        changed = contract()
        changed['reader_promise'] = '工程作者改变阅读承诺。'
        self.app.recontract(changed, '工程作者明确改约。')
        self.app.advance()
        self.app.submit(response(self.app))
        self.app.advance()
        self.assertEqual(self.repo.load()['lexical_policy'], versions)
        task = self.repo.pending()['input']
        self.assertEqual(task['policy']['forbidden_terms'], ['临时禁词'])
        self.assertEqual(task['policy']['source'], '工程作者指定项目字面规则。')

    def test_null_contract_controls_are_rejected_before_staging_an_amendment(self):
        before = self.repo.get('book')
        for field in ('scope_append_limit', 'allow_special_mechanism'):
            with self.subTest(field=field):
                changed = contract()
                changed[field] = None
                self.assertCode('contract', self.app.recontract, changed, '工程作者提供的候选约定。')
                self.assertEqual(self.repo.get('book'), before)

    def test_discard_restores_prose_without_undoing_project_lexical_decisions(self):
        owner = self.finish()
        original = self.repo.headers('main')
        self.app.revise(2, '工程作者要求调整表达。', owner, through=2)
        self.app.set_lexical({'forbidden_terms': ['临时禁词']}, '工程作者在修订期间调整项目字面规则。', owner)
        versions = self.repo.load()['lexical_policy']
        self.app.discard(owner)
        self.assertEqual(self.repo.headers('main'), original)
        self.assertEqual(self.repo.load()['lexical_policy'], versions)

    def test_malformed_worker_receipt_is_a_json_error_without_a_traceback(self):
        task = self.app.advance()['task']
        path = self.project / 'malformed.json'
        path.write_text('[]', encoding='utf-8')
        environment = dict(os.environ, NOVEL_TASK_ID=task['task_id'], NOVEL_SESSION='engineering-malformed')
        for command in ('submit', 'preflight', 'first-read'):
            with self.subTest(command=command):
                result = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'novel.py'),
                    '--project', str(self.project), command, '--file', str(path)], env=environment,
                    capture_output=True, text=True, encoding='utf-8')
                self.assertEqual(result.returncode, 2)
                self.assertEqual(json.loads(result.stdout)['error'], 'schema')
                self.assertNotIn('Traceback', result.stderr)
        self.assertEqual(self.repo.pending()['id'], task['task_id'])

    def test_malformed_plan_rows_are_rejected_without_mutating_the_task(self):
        drive(self.app, until='plan')
        result = response(self.app)
        before = self.repo.get('book')
        valid = copy.deepcopy(result['data']['plans'])
        for rows in (valid + [None], [None] + valid, [dict(valid[0], chapter=True)]):
            with self.subTest(rows=rows):
                result['data']['plans'] = rows
                self.assertCode('plan', self.app.submit, result)
                self.assertEqual(self.repo.get('book'), before)
        self.assertEqual(self.repo.pending()['id'], result['task_id'])

    def test_malformed_plan_dependencies_entities_and_schedule_leave_the_task_intact(self):
        drive(self.app, until='plan')
        valid = response(self.app)
        before = self.repo.get('book')
        for field, value in (('node_ids', [[]]), ('new_entities', [None]),
                             ('new_entities', [{'id': 'new', 'name': '新人物', 'kind': 'person', 'aliases': None}]),
                             ('schedule', None), ('schedule', {})):
            with self.subTest(field=field, value=value):
                result = copy.deepcopy(valid)
                result['data']['plans'][0][field] = value
                with self.assertRaises(Error):
                    self.app.submit(result)
                self.assertEqual(self.repo.get('book'), before)
        self.assertEqual(self.repo.pending()['id'], valid['task_id'])

    def test_audit_detects_modified_document_and_projection(self):
        self.finish()
        row = self.repo.chapter('main', 1)
        self.repo.db.execute('UPDATE documents SET value=? WHERE hash=?', (dump('被篡改的正文。'), row['prose']))
        self.assertCode('source_integrity', self.app.audit)

    def test_completion_reads_the_derived_band_not_a_hand_entered_total(self):
        """The author decides chapters and the per-chapter range; the total cannot gate completion."""
        raw = contract(2, 1)
        raw['word_range'] = [200, 300]
        raw['chapter_min'], raw['chapter_max'], raw['chapter_aim'] = 71, 150, 90
        self.repo.save(workflow.new_book(raw))
        # the hand-entered band is replaced by the projection of the two real decisions
        self.assertEqual(self.repo.load()['contract']['word_range'], [2 * 71, 2 * 150])
        owner = self.finish()
        self.assertTrue(self.app.complete(owner)['completed'])
        self.assertEqual(self.repo.load()['status'], 'completed')

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
                 'value': {'genre': '都市生活', 'reader_promise': '查清责任。', 'tone': '冷硬的夜班底色。'}},
                {'id': 'B', 'title': '另一条路', 'premise': '换一种推进。', 'driver': '从对手的账目往回查。',
                 'pitch': '他先查对手，再查自己。',
                 'scene': ['白天的主管办公室里，他盯着对方的签字栏。', '雨夜的码头，他等一个送货人开口。'],
                 'tradeoff': '相比另两案，选它要放弃更稳的开局。', 'fit_reason': '承接夜班题材，把压力放在对手线上。',
                 'value': {'genre': '都市生活', 'reader_promise': '换一个承诺。', 'tone': '更亮的日常底色。'}},
            ]})
        self.assertEqual(board['board']['options'][0]['title'], '夜班退件')      # offer() alone stores what it got
        with self.assertRaises(Error) as caught:
            planning.enforce(planning.resolve_policy({}), 'opening_options',
                             {'gate': 'genre', 'options': board['board']['options']})
        self.assertEqual(caught.exception.code, 'literal_policy')
        fields = {row['field'] for row in caught.exception.details['violations']['forbidden_terms']}
        self.assertIn('options.premise', fields)

    def test_export_cannot_overwrite_database(self):
        self.assertCode('output', delivery.export_book, self.repo, self.project / 'novel.sqlite3', workspace=local_workspace(self.repo))

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
        # The spent budget is no longer a wall: resume hands the decision to the author, and the
        # engine keeps the budget unless the author explicitly grants one more round.
        status = self.app.resume()
        self.assertEqual(status['status'], 'paused')
        self.assertEqual(status['author_decision']['id'], 'repair-exhausted:design_review')
        self.assertEqual(self.repo.load()['proposal']['attempts'], 3)

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

    def test_host_releases_claim_when_log_cannot_be_opened(self):
        def open_log(path, *args, **kwargs):
            if path.name == 'host.log':
                raise OSError('工程夹具：日志目录不可写。')
            return original(path, *args, **kwargs)
        original = Path.open
        with patch.object(Path, 'open', open_log):
            result = host.step(self.app, [sys.executable, '-c', 'pass'])
        self.assertEqual(result['action'], 'host_launch_failed')
        self.assertIsNone(self.repo.get('claim:' + result['task_id']))

    def test_host_releases_claim_when_owner_renewal_fails(self):
        owner = self.app.run(through=1, source='工程夹具授权。')['owner']
        with patch.object(self.app, 'renew', side_effect=Error('lease', '工程夹具续租失败。')):
            self.assertCode('lease', host.step, self.app, [sys.executable, '-c', 'pass'], owner)
        self.assertIsNone(self.repo.get('claim:' + self.repo.pending()['id']))

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

    def test_dispatch_identity_travels_with_the_task_and_explains_the_credential(self):
        """Identity is data the dispatch can be checked against, while the credential stays ambient."""
        task = self.app.advance()['task']
        identity_path = Path(task['identity_path'])
        self.assertTrue(identity_path.is_file())
        identity = json.loads(identity_path.read_text(encoding='utf-8'))
        self.assertEqual((identity['task_id'], identity['input_hash'], identity['stage']),
                         (task['task_id'], task['input_hash'], task['stage']))
        self.assertTrue(identity['requires_new_worker'])
        self.assertEqual(identity['worker_env'], {'NOVEL_TASK_ID': task['task_id'], 'NOVEL_SESSION': None})
        self.assertEqual(Path(identity['task_path']), Path(task['task_path']))
        # The compact view a controller forwards names the same file, so it can be handed on.
        self.assertEqual(Path(self.app.advance(compact=True)['task']['identity_path']), identity_path)
        # The refusal teaches what to inject instead of leaving the asker to guess.
        import argparse
        import importlib
        cli = importlib.import_module('novel')
        args = argparse.Namespace(command='read', task=task['task_id'], project=str(self.project))
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('NOVEL_TASK_ID', None)
            os.environ.pop('NOVEL_SESSION', None)
            with self.assertRaises(Error) as caught:
                cli.role_guard(args)
        self.assertEqual(caught.exception.code, 'role_boundary')
        self.assertIn('NOVEL_TASK_ID', caught.exception.details['recover'])
        self.assertEqual(caught.exception.details['identity']['task_id'], task['task_id'])

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
            delivery.export_book(self.repo, workspace=local_workspace(self.repo))
        self.assertEqual(caught.exception.code, 'output')
        allowed = delivery.export_book(self.repo, output=Path(self.temp.name) / 'plain.html', workspace=local_workspace(self.repo))
        self.assertEqual(Path(allowed['path']).name, 'plain.html')

    def test_contract_derives_its_total_band_from_chapters_and_the_per_chapter_range(self):
        """The author decides the chapter count and the per-chapter range; the total follows."""
        raw = contract(2, 1)
        raw['volumes'] = [{'id': 'v1', 'purpose': '查明来源并面对后果。', 'end': 47}]
        raw['chapter_min'], raw['chapter_max'], raw['chapter_aim'] = 2000, 2600, 2300
        # An incoming band is ignored rather than argued with: the projection is the authority.
        raw['word_range'] = [90000, 110000]
        self.assertEqual(planning.validate_contract(raw)['word_range'], [47 * 2000, 47 * 2600])
        raw['chapter_max'] = 2500
        self.assertEqual(planning.validate_contract(raw)['word_range'], [47 * 2000, 47 * 2500])
        # A contract that names no band at all is still complete: it is derived, not required.
        raw.pop('word_range')
        self.assertEqual(planning.validate_contract(raw)['word_range'], [94000, 117500])

    def test_dispatch_material_carries_its_own_path_self_check(self):
        self.repo.save(workflow.preparing_book(guided=True))
        handle = self.app.advance()['task']
        self.assertEqual(handle['stage'], 'opening_options')          # the stage that carries a brief
        envelope = json.loads(Path(handle['task_path']).read_text(encoding='utf-8'))
        self.assertIn('当前安装的真实路径', envelope['note'])
        self.assertIn('advance', envelope['note'])
        material = json.loads(Path(handle['input_path']).read_text(encoding='utf-8'))
        self.assertIn('路径自检', material['brief'])
        entry = envelope['commands']['submit'][1]
        self.assertTrue(Path(entry).is_file(), entry)

    def test_check_command_reports_the_offending_field_without_committing(self):
        """A worker must be able to learn the format from `check`, not from reading the engine source."""
        command = [sys.executable, str(ROOT / 'scripts' / 'novel.py'), '--project', str(self.project)]
        task = self.app.advance()['task']
        pending = self.repo.pending()['id']
        blank = json.loads(Path(task['template_path']).read_text(encoding='utf-8'))
        malformed = subprocess.run(command + ['check'], input=json.dumps(blank), text=True, capture_output=True,
                                   encoding='utf-8', errors='replace')
        self.assertEqual(malformed.returncode, 2)
        body = json.loads(malformed.stdout)
        self.assertEqual(body['error'], 'design')
        self.assertIn('intent', body['message'])
        self.assertEqual(self.repo.pending()['id'], pending)          # nothing was committed
        self.assertEqual(self.repo.task(pending)['status'], 'pending')
        # a missing input_hash is reported as such, with the expected value
        blank.pop('input_hash', None)
        wrong = subprocess.run(command + ['check'], input=json.dumps(blank), text=True, capture_output=True,
                               encoding='utf-8', errors='replace')
        self.assertEqual(json.loads(wrong.stdout)['error'], 'input_version')
        self.assertTrue(json.loads(wrong.stdout)['details']['expected'])

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

    def test_the_declared_repository_protocol_covers_the_adapter(self):
        """A hand-written interface nobody checks drifts: this keeps the declaration honest."""
        from novel_ledger.ports import Repository
        from novel_ledger.sqlite_store import SQLiteRepository

        declared = {name for cls in Repository.__mro__ for name, value in vars(cls).items()
                    if not name.startswith('_') and callable(value)}
        actual = {name for name, value in vars(SQLiteRepository).items()
                  if not name.startswith('_') and not isinstance(value, (classmethod, staticmethod)) and callable(value)}
        self.assertEqual(actual - declared, set())          # every adapter method is declared
        self.assertEqual(declared - actual, set())          # nothing is declared that does not exist
        self.assertIn('initialize', SQLiteRepository.__dict__)   # the constructor side of the contract



if __name__ == '__main__':
    unittest.main()
