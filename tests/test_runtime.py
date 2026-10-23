import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from novel_ledger.bootstrap import local_application as Application, local_workspace
from novel_ledger.contracts import ENFORCEMENT, Error, dump
from novel_ledger import delivery, facts, host, planning, workflow
from novel_ledger.sqlite_store import SQLiteRepository
from support import contract, drive, long_prose, prose_stub, response, seeded_book


def app_stage(repo):
    """The stage of the frozen dispatch waiting to be answered, or None at a boundary."""
    task = repo.pending()
    return task['input']['stage'] if task else None


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / 'book'
        self.repo = SQLiteRepository.initialize(self.project, seeded_book())
        self.app = Application(self.repo)

    def tearDown(self):
        self.repo.close()
        self.temp.cleanup()

    def assertCode(self, code, fn, *args, **kwargs):
        with self.assertRaises(Error) as caught:
            fn(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)

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
        # Three chapters: the first two happen on the same day (clock advance 0), the third moves the
        # main clock by one day and must cite the interior time expression it declares.
        from support import chapter_rows
        self.repo.save(seeded_book(contract(3)))
        owner = self.app.run(finish=True, source='工程夹具授权验证三章时间衔接。')['owner']
        word = self.app.advance(owner=owner)          # volume outline first
        self.assertEqual(word['task']['stage'], 'volume_outline')
        volume_receipt = response(self.app)
        volume_receipt['data']['volumes'][0]['clock'] = {'advance_days': 1, 'to': 1}
        self.app.submit(volume_receipt)
        handoff = self.app.advance(owner=owner)
        self.assertEqual(handoff['task']['stage'], 'chapter_outline')
        prose = [
            '沈桐把箱子推到主管面前，指着封条上的签字，要求核对退件来源，主管却按住了箱盖。',
            '“先把责任栏填上。”主管把登记册塞给沈桐。他没有接，反而抽出封条，指给主管看另一处笔迹。',
            '封条被主管扣进抽屉，沈桐攥紧了空白的责任单。次日，他带着退件人的签字回来，把两份笔迹并排放下。',
        ]
        book = self.repo.load()
        volume = book['contract']['volumes'][0]
        rows = chapter_rows(book, volume, book['state'])
        for row in rows[:2]:                     # chapters 1-2 are the same story day
            row['clock'] = {'advance_days': 0}
            for item in row['enter'] + row['exit']:
                if item['kind'] == 'clock':
                    item['expected'] = 0
        for item in rows[2]['enter']:
            if item['kind'] == 'clock':
                item['expected'] = 0
        for item in rows[2]['exit']:
            if item['kind'] == 'clock':
                item['expected'] = 1
        self.app.submit({'schema': 'novel-ledger.result/1',
                         'task_id': self.repo.pending()['id'],
                         'input_hash': self.repo.pending()['input_hash'],
                         'session': 'scene-openings-setup',
                         'data': {'volume': 'v1', 'chapters': rows}})
        for n, chapter_prose in enumerate(prose, 1):
            self.assertEqual(drive(self.app, owner, until='write')['task']['chapter'], n)
            draft = response(self.app)
            draft['data']['prose'] = chapter_prose
            for item in draft['data']['drift_check']['items']:
                quote = chapter_prose[:12]
                if item['kind'] == 'clock' and '次日' in chapter_prose:
                    quote = '次日，他带着退件人的签字回来'
                item['evidence'] = {'chapter': n, 'quote': quote}
            self.app.submit(draft)
            self.assertEqual(self.repo.load()['state']['clock'], 0 if n < 3 else 1)
        self.assertEqual(drive(self.app, owner)['action'], 'ready_to_complete')
        self.app.complete(owner)
        self.assertTrue(self.app.audit()['ok'])
        output = delivery.export_book(self.repo, output=Path(self.temp.name) / 'scene-openings.md', format='md', workspace=local_workspace(self.repo))
        exported = Path(output['path']).read_text(encoding='utf-8')
        for chapter_prose in prose:
            self.assertIn(chapter_prose, exported)




    def test_rejection_does_not_commit_fact_or_spend_budget(self):
        drive(self.app, until='write')
        result = response(self.app)
        target = next(item for item in result['data']['drift_check']['items']
                      if item['kind'] == 'resources')
        target['actual']['from'] = 99
        state_before = copy.deepcopy(self.repo.load()['state'])
        self.app.submit(result)
        self.assertEqual(self.repo.headers('main'), [])
        book = self.repo.load()
        self.assertEqual(book['state'], state_before)
        self.assertEqual(book['written_han'], 0)
        self.assertIn('drift_before', {finding.get('criterion')
                                       for finding in (book['draft'] or {}).get('findings') or []})


    def test_short_prose_preserved_and_rework_is_bounded(self):
        drive(self.app, until='write')
        stages = []
        for _ in range(5):
            handoff = self.app.advance()
            if handoff['action'] != 'task_ready':
                break
            stages.append(app_stage(self.repo))
            result = response(self.app)
            result['data']['prose'] = ('他走了。', '他哭了。', '他睡了。')[len(stages) - 1]
            self.app.submit(result)
        # Two repair rounds raise the same finding again: v2 stops the non-converging loop at the
        # stall point (before the budget is spent), and hands the decision to the author.
        self.assertEqual(stages, ['write', 'repair', 'repair'])
        status = self.app.status()
        self.assertEqual(status['status'], 'paused')
        decision_id = status['author_decision']['id']
        self.assertTrue(decision_id.startswith('repair-stalled:chapter_repair:'))
        self.assertIn('第 1 章', status['author_decision']['question'])
        book = self.repo.load()
        self.assertEqual(book['draft']['prose'], '他睡了。')
        self.assertEqual(book['rework']['1']['repairs'], 2)
        # Mechanical failures cannot be accepted into the chapter. Every offered path preserves
        # the candidate; the granted round can produce a chapter that actually commits.
        options = [row['label'] for row in status['author_decision']['options']]
        self.assertNotIn(workflow.ACCEPT_OPEN, options)
        self.assertCode('author_decision', self.app.answer,
                        decision_id, workflow.ACCEPT_OPEN, '这一处我承担。')
        self.assertEqual(self.repo.load()['draft']['prose'], '他睡了。')
        granted = self.app.answer(decision_id, workflow.REPAIR_AGAIN, '再返修一轮。')
        self.assertEqual(granted['status'], 'running')
        self.assertEqual(self.app.advance()['task']['stage'], 'repair')
        self.app.submit(response(self.app))
        self.assertEqual(self.app.advance()['action'], 'await_author')
        self.assertEqual(self.app.status()['formal_chapters'], 1)


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



    def test_first_chapter_approval_binds_exact_version(self):
        drive(self.app, until='write')
        self.app.submit(response(self.app))
        handoff = self.app.advance()
        self.assertEqual(handoff['action'], 'await_author')
        self.assertCode('pilot_version', self.app.approve, 'wrong', '作者认可。')
        self.app.approve(handoff['prose_hash'], '作者认可这版。')
        self.assertEqual(self.app.advance()['action'], 'target_reached')

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

    def test_compact_dispatch_exposes_claim_and_never_reuses_a_session(self):
        handle = self.app.advance()['task']
        compact = self.app.advance(compact=True)['task']
        self.assertTrue(compact['requires_new_worker'])
        self.assertIsNone(compact['review_session'])
        self.assertNotIn('input_path', compact)
        self.assertNotIn('records', compact)
        self.assertNotIn('commands', compact)

        claim = self.app.claim(handle['task_id'], 'worker-for-current-task')
        compact = self.app.advance(compact=True)['task']
        self.assertEqual(compact['claim'], {'session': claim['session'], 'expired': False})
        self.assertNotIn('token', compact['claim'])
        # v2 has no blind first read: one worker owns the dispatch, and a second session cannot
        # take it over while the lease is held.
        self.assertCode('worker_busy', self.app.claim, handle['task_id'], 'another-worker')
        self.assertTrue(self.app.submit(response(self.app, session=claim['session'],
                                                 claim=claim['token']))['accepted'])

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






    def test_advance_carries_ledger_baseline(self):
        handoff = drive(self.app, until='write')
        baseline = handoff['task']['baseline']
        self.assertEqual(baseline['clock'], 0)
        self.assertIn('["shen","车费","元"]', baseline['resources'])
        self.assertIsNone(baseline['candidate'])
        on_disk = json.loads(Path(handoff['task']['task_path']).read_text(encoding='utf-8'))
        self.assertEqual(on_disk['baseline']['clock'], 0)



    def test_lexical_override_is_versioned_and_applies_from_the_opening_stage(self):
        self.assertEqual(self.app.advance()['task']['stage'], 'volume_outline')
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







    def test_malformed_worker_receipt_is_a_json_error_without_a_traceback(self):
        task = self.app.advance()['task']
        path = self.project / 'malformed.json'
        path.write_text('[]', encoding='utf-8')
        environment = dict(os.environ, NOVEL_TASK_ID=task['task_id'], NOVEL_SESSION='engineering-malformed')
        for command in ('submit', 'preflight'):
            with self.subTest(command=command):
                result = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'novel.py'),
                    '--project', str(self.project), command, '--file', str(path)], env=environment,
                    capture_output=True, text=True, encoding='utf-8')
                self.assertEqual(result.returncode, 2)
                self.assertEqual(json.loads(result.stdout)['error'], 'schema')
                self.assertNotIn('Traceback', result.stderr)
        self.assertEqual(self.repo.pending()['id'], task['task_id'])



    def test_audit_detects_modified_document_and_projection(self):
        self.finish()
        row = self.repo.chapter('main', 1)
        self.repo.db.execute('UPDATE documents SET value=? WHERE hash=?', (dump('被篡改的正文。'), row['prose']))
        self.assertCode('source_integrity', self.app.audit)

    def test_the_total_band_is_derived_and_cannot_gate_completion(self):
        """The author decides chapters and the per-chapter range; the total is a projection of those
        two decisions — an incoming hand-entered band is ignored, and completion reads the projection."""
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
        # Completion is judged against the derived band, never a hand-entered total.
        raw = contract(2, 1)
        raw['word_range'] = [200, 300]
        raw['chapter_min'], raw['chapter_max'], raw['chapter_aim'] = 71, 150, 90
        self.repo.save(workflow.new_book(raw))
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

    def test_export_cannot_overwrite_the_database_or_the_book_view(self):
        self.assertCode('output', delivery.export_book, self.repo, self.project / 'novel.sqlite3',
                        workspace=local_workspace(self.repo))
        with self.assertRaises(Error) as caught:
            delivery.export_book(self.repo, workspace=local_workspace(self.repo))
        self.assertEqual(caught.exception.code, 'output')
        allowed = delivery.export_book(self.repo, output=Path(self.temp.name) / 'plain.html', workspace=local_workspace(self.repo))
        self.assertEqual(Path(allowed['path']).name, 'plain.html')


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






    def test_host_runs_real_process_and_verifies_cli_submission(self):
        drive(self.app, until='write')
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

    def test_host_failures_always_release_the_claim(self):
        """A bad binary, an unopenable log and a failing owner renewal each end the step with the
        lease released, so a broken host never strands the worker's task."""
        result = host.step(self.app, ['/nonexistent-host'])
        self.assertEqual(result['action'], 'host_launch_failed')
        self.assertIsNone(self.repo.get('claim:' + result['task_id']))

        def open_log(path, *args, **kwargs):
            if path.name == 'host.log':
                raise OSError('工程夹具：日志目录不可写。')
            return original(path, *args, **kwargs)
        original = Path.open
        with patch.object(Path, 'open', open_log):
            result = host.step(self.app, [sys.executable, '-c', 'pass'])
        self.assertEqual(result['action'], 'host_launch_failed')
        self.assertIsNone(self.repo.get('claim:' + result['task_id']))

        owner = self.app.run(through=1, source='工程夹具授权。')['owner']
        with patch.object(self.app, 'renew', side_effect=Error('lease', '工程夹具续租失败。')):
            self.assertCode('lease', host.step, self.app, [sys.executable, '-c', 'pass'], owner)
        self.assertIsNone(self.repo.get('claim:' + self.repo.pending()['id']))

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

    def test_dispatch_material_carries_its_own_path_self_check(self):
        self.repo.save(workflow.preparing_book(guided=True))
        handle = self.app.advance()['task']
        self.assertEqual(handle['stage'], 'opening_options')          # the stage that carries a brief
        envelope = json.loads(Path(handle['task_path']).read_text(encoding='utf-8'))
        self.assertIn('当前安装的真实路径', envelope['note'])
        self.assertIn('advance', envelope['note'])
        material = json.loads(Path(handle['input_path']).read_text(encoding='utf-8'))
        # The slim opening card keeps install paths in the envelope note and points reads
        # through task.json commands; the brief itself must not inline real paths.
        self.assertIn('task.json.commands.read', material['brief'])
        self.assertNotIn(str(ROOT), material['brief'])
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
        # A content defect is preview data now, not a raised error: exit 0, valid=false, findings.
        self.assertEqual(malformed.returncode, 0)
        body = json.loads(malformed.stdout)
        self.assertFalse(body['valid'])
        self.assertEqual(body['error'], 'design_drift')
        self.assertTrue(body['message'])
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
        for field in ('unknown_field', 'planning_window', 'review_interval', 'review_chunk',
                      'review_fanout', 'verification'):
            with self.subTest(field=field):
                raw = contract()
                raw[field] = 3
                with self.assertRaises(Error) as caught:
                    workflow.new_book(raw)
                self.assertEqual(caught.exception.code, 'contract')
                self.assertIn('未知约定字段', caught.exception.message)

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



class GuidedOpeningTests(unittest.TestCase):
    """A new project opens on the thirteen-gate setting protocol and writes through it.

    The gates themselves are covered in test_opening; what this class pins is the hand-off: thirteen
    decisions, one world receipt plus the contract it implies, every volume's outline, one volume's
    chapter outlines, and only then a word of prose — with no reviewer anywhere in between.
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / 'book'
        self.repo = SQLiteRepository.initialize(self.project, workflow.preparing_book(guided=True))
        self.app = Application(self.repo)

    def tearDown(self):
        self.repo.close()
        self.temp.cleanup()

    def chapter_receipt(self):
        """A write receipt whose prose lands inside the tier's band without echoing itself.

        The tier the default window opens on writes 2500~4500 汉字 per chapter, so the fixture stub
        is padded with varied text; the stub's own opening is kept verbatim because the writer's
        drift_check cites it as evidence.
        """
        candidate = response(self.app)
        number = self.repo.pending()['input']['chapter']
        candidate['data']['prose'] = prose_stub(number)[:14] + long_prose(number, count=110)
        return candidate

    def test_the_thirteen_gates_end_at_the_design_boundary_without_prose(self):
        from novel_ledger import creation
        self.assertEqual(creation.gate_ids(creation.OPENING_VERSION),
                         tuple(gate for gate, _title in creation.GATES))
        self.assertEqual(len(creation.GATES), 13)
        handoff = drive(self.app)
        self.assertEqual(handoff['action'], 'outline_ready')
        book = self.repo.load()
        self.assertEqual(creation.opening_version(book['creation']), creation.OPENING_VERSION)
        self.assertEqual(len(book['creation']['selections']), 13)
        self.assertEqual(book['creation']['phase'], 'ready')
        self.assertEqual(self.repo.headers('main'), [])
        # The six opening/5 contract fields are decisions, so the contract carries all of them.
        for key in ('core_premise', 'world_scale', 'world_ladder', 'world_tiers', 'world_resource',
                    'promise_anchor'):
            self.assertIn(key, book['contract'], key)
        self.assertEqual(sorted(book['volumes_outline']), [row['id'] for row in book['contract']['volumes']])
        # With `chapter_outline.scope == 'volume'` and no prose authorization, the design boundary
        # hands over the volume outlines and keeps the chapter outlines for the writing step.
        self.assertEqual(book['contract']['chapter_outline']['scope'], 'volume')
        self.assertEqual(book['chapter_outlines'], {})
        self.assertTrue(self.app.audit()['ok'])

    def test_an_authorized_chapter_is_written_through_the_current_opening(self):
        drive(self.app)
        run = self.app.run(through=1, source='作者授权试写一章。')
        handoff = drive(self.app, run['owner'], until='write')
        self.assertEqual(handoff['task']['chapter'], 1)
        outcome = self.app.submit(self.chapter_receipt())
        self.assertEqual(outcome['committed_chapter'], 1)
        self.assertEqual([row['n'] for row in self.repo.headers('main')], [1])
        self.assertGreaterEqual(self.repo.load()['state']['clock'], 1)
        self.assertTrue(self.app.audit()['ok'])


if __name__ == '__main__':
    unittest.main()
