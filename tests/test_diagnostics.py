"""Operational handoffs stay small, read-only, and separate from story verification."""
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
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'tests')]

from novel_ledger import store_keys
from novel_ledger.bootstrap import open_local_runtime
from novel_ledger.contracts import Error, execution_recovery
from support import contract, drive, response


class DiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="writer's diagnosis ")
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name).resolve() / '小说 project'
        self.runtime = open_local_runtime(self.project, initialize=True, contract=contract(2))
        self.addCleanup(self.runtime.close)
        self.app, self.repo = self.runtime.app, self.runtime.repo
        self.owner = self.app.run(finish=True, source='测试作者授权写完当前两章。')['owner']
        self.view = drive(self.app, self.owner, until='write')['task']
        self.task_id = self.view['task_id']
        self.entry = ROOT / 'scripts' / 'novel.py'
        self.base = [sys.executable, str(self.entry), '--project', str(self.project)]
        self.environment = {key: value for key, value in os.environ.items()
                            if not key.startswith('NOVEL_')}

    def cli(self, argv=None, *, env=None, code=0):
        process = subprocess.run(argv or self.base + ['diagnose'],
                                 env={**self.environment, **(env or {})},
                                 capture_output=True, text=True, encoding='utf-8', timeout=20)
        self.assertEqual(process.returncode, code, process.stdout + process.stderr)
        return json.loads(process.stdout)

    def snapshot(self, project=None):
        project = project or self.project
        return {str(path.relative_to(project)): path.read_bytes()
                for path in project.rglob('*') if path.is_file()}

    def prepare(self):
        return self.app.prepare_worker(self.task_id, 'real-host-worker', owner=self.owner)

    def test_real_cli_does_not_change_database_artifacts_leases_or_failures(self):
        prepared = self.prepare()
        self.app.worker_failure(self.task_id, 'real-host-worker', 'preflight', 'file')
        draft = self.project / 'work' / self.task_id / 'result.json'
        draft.write_text('{"data":{"prose":"未提交候选必须原样保留"}}', encoding='utf-8')
        before = self.snapshot()
        lease = copy.deepcopy(self.repo.get(store_keys.claim(self.task_id)))
        failure = copy.deepcopy(self.repo.get(store_keys.technical_failure(self.task_id)))

        first = self.cli()
        second = self.cli(first['handoff']['resume'])

        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.repo.get(store_keys.claim(self.task_id)), lease)
        self.assertEqual(self.repo.get(store_keys.technical_failure(self.task_id)), failure)
        self.assertEqual(second['task']['task_id'], self.task_id)
        self.assertEqual(first['controller']['owner'], self.owner)
        self.assertEqual(first['project']['target'], 2)
        self.assertFalse(first['handoff']['resets_model_history'])
        self.assertNotIn(prepared['worker_env']['NOVEL_EXECUTION_CLAIM'], json.dumps(first))

    def test_candidate_and_committed_prose_are_neither_loaded_nor_returned(self):
        receipt = response(self.app, session='first-chapter-worker')
        self.app.submit(receipt)
        view = drive(self.app, self.owner, until='write')['task']
        task_id = view['task_id']
        candidate_marker = 'PRIVATE_UNCOMMITTED_PROSE_SENTINEL'
        candidate = self.project / 'work' / task_id / 'result.json'
        candidate.write_text(json.dumps({'data': {'prose': candidate_marker * 1000}}), encoding='utf-8')
        prose_hash = self.repo.headers('main')[0]['prose']
        read_document = self.repo.read_document

        def without_prose(key):
            self.assertNotEqual(key, prose_hash, 'diagnostics must not read committed prose')
            return read_document(key)

        with patch.object(self.repo, 'read_document', side_effect=without_prose), \
                patch.object(self.repo, 'load', side_effect=AssertionError('no whole-book load')), \
                patch.object(self.app.presentation, 'task', side_effect=AssertionError('no redispatch')):
            result = self.runtime.diagnose()
        serialized = json.dumps(result, ensure_ascii=False)
        self.assertNotIn(candidate_marker, serialized)
        self.assertNotIn(receipt['data']['prose'], serialized)
        self.assertEqual(result['project']['accepted_chapters'], 1)
        self.assertEqual(result['task']['task_id'], task_id)

    def test_damaged_projection_returns_metadata_without_claiming_validation(self):
        book = self.repo.load()
        book['state']['placements']['shen'] = 'yard'
        self.repo.save(book)
        with self.assertRaises(Error) as caught:
            self.app.status()
        self.assertEqual(caught.exception.code, 'projection')
        before = self.snapshot()

        result = self.cli()

        self.assertEqual(result['task']['task_id'], self.task_id)
        self.assertEqual(result['project']['target'], 2)
        self.assertFalse(result['validation']['integrity_checked'])
        self.assertFalse(result['validation']['dispatch_authorized'])
        self.assertEqual(self.snapshot(), before)

    def test_engine_mismatch_reports_exact_task_and_missing_upgrade_authority(self):
        self.prepare()
        task = self.repo.pending()
        current = {**self.app.build_info, 'engine_hash': 'different-running-release'}
        before = self.snapshot()
        with patch.object(self.app, 'build_info', current):
            result = self.runtime.diagnose()

        self.assertFalse(result['engine']['matches'])
        self.assertEqual(result['engine']['current'], current)
        self.assertEqual(result['engine']['frozen'], task['input']['build'])
        self.assertEqual(result['recovery'], execution_recovery('engine_changed'))
        recovery = result['engine_recovery']
        self.assertEqual(recovery['task_id'], task['id'])
        self.assertEqual(recovery['input_hash'], task['input_hash'])
        self.assertEqual(recovery['preserved_result_path'],
                         str(self.project / 'work' / task['id'] / 'result.json'))
        upgrade = recovery['upgrade_release']
        arguments = upgrade['from_pinned_entry_arguments']
        for flag, expected in (('--project', str(self.project)), ('--owner', self.owner),
                               ('--task', task['id']), ('--input-hash', task['input_hash'])):
            self.assertEqual(arguments[arguments.index(flag) + 1], expected)
        self.assertIn('recover-engine', arguments)
        self.assertNotIn('--source', arguments)
        self.assertNotIn('--worker-stopped', arguments)
        self.assertTrue({'pinned_entry', 'author_upgrade_source', 'worker_stopped_confirmation'}
                        <= set(upgrade['required_inputs']))
        self.assertEqual(self.snapshot(), before)

    def test_expired_and_active_worker_leases_never_claim_process_liveness(self):
        self.prepare()
        lease = self.repo.get(store_keys.claim(self.task_id))
        for observed, expired in ((False, False), (True, False), (True, True)):
            with self.subTest(observed=observed, expired=expired):
                changed = {**lease, 'until': self.app.clock() + (-30 if expired else 300)}
                if observed:
                    changed['activity_at'] = self.app.clock() - 60
                self.repo.put(store_keys.claim(self.task_id), changed)
                before = copy.deepcopy(changed)
                result = self.runtime.diagnose()
                self.assertEqual(result['worker']['session'], 'real-host-worker')
                self.assertTrue(result['worker']['identity_registered'])
                self.assertEqual(result['worker']['lease_valid'], not expired)
                self.assertEqual(result['worker']['activity_observed'], observed)
                self.assertIsNone(result['worker']['worker_running'])
                self.assertEqual(self.repo.get(store_keys.claim(self.task_id)), before)

    def test_technical_block_retains_recovery_and_does_not_reset_counters(self):
        self.prepare()
        recovery = self.app.worker_failure(self.task_id, 'real-host-worker', 'preflight', 'worker_lease')
        before = self.snapshot()

        result = self.cli()

        self.assertEqual(result['execution_failure'],
                         {'code': 'worker_lease', 'operation': 'preflight', 'failures': 1, 'blocked': True})
        self.assertEqual(result['recovery'], {key: recovery[key] for key in
                                             ('actor', 'action', 'retry_allowed', 'failures', 'limit')})
        self.assertFalse(result['recovery']['retry_allowed'])
        self.assertEqual(self.snapshot(), before)

    def test_worker_calls_are_rejected_without_heartbeat_or_failure_accounting(self):
        prepared = self.prepare()
        environment = prepared['worker_env']
        self.app.worker_failure(self.task_id, 'real-host-worker', 'preflight', 'file')
        before = self.snapshot()

        direct = self.cli(env=environment, code=2)
        portable = self.cli(self.base + ['worker', '--task', self.task_id, '--', 'diagnose'],
                            env=environment, code=2)

        self.assertEqual(direct['error'], 'worker_boundary')
        self.assertEqual(portable['error'], 'worker_boundary')
        self.assertEqual(self.snapshot(), before)

    def test_commands_and_handoff_use_real_paths_without_shell_quoting_assumptions(self):
        result = self.cli()
        self.assertEqual(result['runtime']['entry'], str(self.entry.resolve()))
        self.assertEqual(result['runtime']['root'], str(ROOT.resolve()))
        self.assertEqual(result['project_path'], str(self.project))
        self.assertEqual(result['commands']['diagnose'], self.base + ['diagnose'])
        self.assertEqual(result['commands']['status'], self.base + ['status'])
        self.assertEqual(result['handoff']['resume'], result['commands']['diagnose'])
        for name, filename in (('task', 'task.json'), ('dispatch', 'dispatch.md'), ('result', 'result.json')):
            self.assertEqual(result['task']['paths'][name], str(self.project / 'work' / self.task_id / filename))
        second = self.cli(result['commands']['diagnose'])
        self.assertEqual(second['task']['input_hash'], result['task']['input_hash'])

    def test_handoff_does_not_grow_with_author_history_and_candidate_text(self):
        with patch.object(self.app, 'clock', return_value=self.app.clock()):
            before = self.runtime.diagnose()
            book = self.repo.load()
            marker = 'PRIVATE_AUTHOR_HISTORY_AND_DRAFT'
            book['author_decision_history'] = [
                {'id': 'past-' + str(index), 'source': marker * 40} for index in range(400)]
            book['decisions'].extend({'kind': 'historical', 'source': marker * 40} for _ in range(400))
            book['prior_candidate'] = {'data': {'prose': marker * 10000}}
            self.repo.save(book)
            candidate = self.project / 'work' / self.task_id / 'result.json'
            candidate.write_text(json.dumps({'data': {'prose': marker * 10000}}), encoding='utf-8')
            after = self.runtime.diagnose()

        self.assertEqual(after, before)
        self.assertNotIn(marker, json.dumps(after))

    def test_no_pending_task_and_paused_boundary_remain_readonly(self):
        self.app.pause('测试作者暂停并保留当前范围。', cancel=True, owner=self.owner)
        before = self.snapshot()

        result = self.cli()

        self.assertIsNone(result['task'])
        self.assertIsNone(result['worker'])
        self.assertEqual(result['project']['status'], 'paused')
        self.assertEqual(result['project']['target'], 2)
        self.assertFalse(result['validation']['dispatch_authorized'])
        self.assertNotIn('advance', result['commands'])
        self.assertEqual(self.snapshot(), before)

    def test_submitted_active_batch_keeps_original_worker_visible_between_chapters(self):
        project = self.project.parent / 'fast writing project'
        runtime = open_local_runtime(project, initialize=True, contract=contract(4))
        self.addCleanup(runtime.close)
        app, repo = runtime.app, runtime.repo
        owner = app.run(finish=True, mode='fast', source='测试作者授权快速写完四章。')['owner']
        drive(app, owner, until='write')
        app.submit(response(app))
        first = drive(app, owner, until='write')['task']
        self.assertEqual(first['chapter'], 2)
        prepared = app.prepare_worker(first['task_id'], 'existing-fast-worker', owner=owner)
        submitted = app.submit(response(app, session='existing-fast-worker',
                                        claim=prepared['worker_env']['NOVEL_EXECUTION_CLAIM']))
        self.assertEqual(submitted['worker_boundary'], 'continue')
        self.assertIsNone(repo.pending())
        self.assertTrue(repo.get(store_keys.WRITING_BATCH)['active'])
        before = self.snapshot(project)

        result = self.cli([sys.executable, str(self.entry), '--project', str(project), 'diagnose'])

        self.assertEqual(result['task']['task_id'], first['task_id'])
        self.assertEqual(result['task']['input_hash'], first['input_hash'])
        self.assertEqual(result['task']['status'], 'done')
        self.assertEqual(result['task']['origin'], 'active_batch')
        self.assertEqual(result['worker']['session'], 'existing-fast-worker')
        self.assertIsNone(result['worker']['worker_running'])
        self.assertEqual(result['next_action'], 'verify_existing_worker')
        self.assertEqual(result['commands']['watch'],
                         [sys.executable, str(self.entry), '--project', str(project),
                          '--owner', owner, 'watch'])
        self.assertNotIn('advance', result['commands'])
        self.assertFalse(result['validation']['dispatch_authorized'])
        self.assertEqual(self.snapshot(project), before)
        changed_build = {**app.build_info, 'engine_hash': 'changed-between-chapters'}
        with patch.object(app, 'build_info', changed_build):
            changed = runtime.diagnose()
        self.assertFalse(changed['engine']['matches'])
        self.assertEqual(changed['task']['status'], 'done')
        self.assertNotIn('upgrade_release', changed['engine_recovery'])
        self.assertEqual(self.snapshot(project), before)

    def test_paused_boundary_precedes_engine_mismatch(self):
        self.prepare()
        self.app.pause('作者暂停期间不应直接恢复引擎。', owner=self.owner)
        current = {**self.app.build_info, 'engine_hash': 'different-running-release'}
        before = self.snapshot()

        with patch.object(self.app, 'build_info', current):
            result = self.runtime.diagnose()

        self.assertEqual(result['project']['status'], 'paused')
        self.assertFalse(result['engine']['matches'])
        self.assertEqual(result['recovery'], execution_recovery('engine_changed'))
        self.assertEqual(result['next_action'], 'handle_boundary')
        self.assertNotIn('advance', result['commands'])
        self.assertNotIn('watch', result['commands'])
        self.assertEqual(self.snapshot(), before)

    def test_paused_boundary_precedes_technical_block(self):
        self.prepare()
        self.app.worker_failure(self.task_id, 'real-host-worker', 'preflight', 'worker_lease')
        self.app.pause('作者暂停期间不应自动恢复技术执行。', owner=self.owner)
        before = self.snapshot()

        result = self.cli()

        self.assertEqual(result['project']['status'], 'paused')
        self.assertTrue(result['execution_failure']['blocked'])
        self.assertEqual(result['next_action'], 'handle_boundary')
        self.assertNotIn('advance', result['commands'])
        self.assertNotIn('watch', result['commands'])
        self.assertEqual(self.snapshot(), before)


if __name__ == '__main__':
    unittest.main()
