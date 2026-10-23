"""Real CLI handoff: host identity, portable argv, bounded failures and frozen prose safety."""
import copy
import json
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'tests')]
from novel_ledger.bootstrap import open_local_runtime
from novel_ledger.contracts import Error, execution_recovery, policy_default
from novel_ledger import delivery, store_keys, unattended
from support import contract, drive, response


def shell_roundtrip(argv):
    """Parse the rendered command back into argv on the current platform."""
    quoted = delivery._quoted_argv(argv)
    if sys.platform != 'win32':
        return shlex.split(quoted)
    parts, i, n = [], 2, len(quoted)  # skip the leading '& '
    while i < n:
        if quoted[i] != "'":
            i += 1
            continue
        i += 1
        part = []
        while i < n:
            if quoted.startswith("''", i):
                part.append("'")
                i += 2
            elif quoted[i] == "'":
                i += 1
                break
            else:
                part.append(quoted[i])
                i += 1
        parts.append(''.join(part))
    return parts


class ExecutionHandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="writer's workspace ")
        self.addCleanup(self.temp.cleanup)
        self.runtime = open_local_runtime(Path(self.temp.name) / 'book', initialize=True, contract=contract(2))
        self.addCleanup(self.runtime.close)
        self.app, self.repo = self.runtime.app, self.runtime.repo
        self.view = drive(self.app, until='write')['task']
        self.task_id = self.view['task_id']
        self.environment = {k: v for k, v in os.environ.items() if not k.startswith('NOVEL_')}

    def cli(self, argv, env=None, code=0):
        result = subprocess.run(argv, env={**self.environment, **(env or {})},
                                capture_output=True, text=True, encoding='utf-8', timeout=20)
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def prepare(self, reset=False):
        return self.app.prepare_worker(self.task_id, 'host-real-worker', reset_failures=reset)

    def full_view(self):
        return json.loads(Path(self.view['task_path']).read_text(encoding='utf-8'))

    def test_missing_identity_stops_before_read_and_controller_recovers_same_draft(self):
        view = self.full_view()
        self.assertEqual(view['execution']['state'], 'await_worker_identity')
        draft = Path(view['result_path'])
        draft.write_text('作者候选草稿保留', encoding='utf-8')
        book = copy.deepcopy(self.repo.load())
        denied = self.cli(view['commands']['ready'], code=2)
        self.assertEqual(denied['details']['recovery']['actor'], 'controller')
        self.assertFalse(denied['details']['recovery']['retry_allowed'])
        self.assertEqual(self.repo.load(), book)
        prepared = self.prepare(reset=True)
        self.assertEqual(draft.read_text(encoding='utf-8'), '作者候选草稿保留')
        self.assertFalse(draft.with_name('result.stale.json').exists())
        view = self.full_view()
        self.assertEqual(view['execution']['state'], 'ready')
        ready = self.cli(view['commands']['ready'], prepared['worker_env'])
        self.assertTrue(ready['ready'])
        read = self.cli(view['commands']['read'], prepared['worker_env'])
        self.assertEqual(read['task_id'], self.task_id)
        token = prepared['worker_env']['NOVEL_EXECUTION_CLAIM']
        for name in ('task.json', 'identity.json', 'dispatch.md', 'result.template.json'):
            self.assertNotIn(token, draft.with_name(name).read_text(encoding='utf-8'))

    def test_explicit_python_arguments_work_without_shell_environment(self):
        prepared = self.prepare()
        env = prepared['worker_env']
        argv = self.full_view()['commands']['ready']
        index = argv.index('--')
        argv[index:index] = ['--session', env['NOVEL_SESSION'], '--execution-claim', env['NOVEL_EXECUTION_CLAIM']]
        self.assertTrue(self.cli(argv)['ready'])
        # A POSIX command must remain executable with spaces and apostrophes in paths.
        self.assertEqual(self.cli(shell_roundtrip(argv))['session'], env['NOVEL_SESSION'])

    def test_receipt_identity_is_injected_in_memory_and_preflight_keeps_story_unchanged(self):
        prepared = self.prepare()
        view = self.full_view()
        receipt = response(self.app, session='host-real-worker')
        receipt['session'] = ''
        receipt.pop('execution_claim', None)
        path = Path(view['result_path'])
        path.write_text(json.dumps(receipt, ensure_ascii=False), encoding='utf-8')
        frozen = path.read_bytes()
        book = self.repo.load()
        checked = self.cli(view['commands']['preflight'], prepared['worker_env'])
        self.assertTrue(checked['checked'])
        self.assertEqual(self.repo.load(), book)
        self.assertEqual(path.read_bytes(), frozen)
        accepted = self.cli(view['commands']['submit'], prepared['worker_env'])
        self.assertEqual(accepted['committed_chapter'], 1)
        self.assertEqual(path.read_bytes(), frozen)
        self.assertEqual(self.repo.task(self.task_id)['result']['session'], 'host-real-worker')

    def test_two_file_errors_block_execution_without_spending_literary_repairs(self):
        prepared = self.prepare()
        view = self.full_view()
        before = self.repo.load()
        for count in range(1, policy_default('technical_retries') + 1):
            failed = self.cli(view['commands']['preflight'], prepared['worker_env'], code=2)
            self.assertEqual(failed['details']['recovery']['failures'], count)
        self.assertFalse(failed['details']['recovery']['retry_allowed'])
        denied = self.cli(view['commands']['read'], prepared['worker_env'], code=2)
        self.assertEqual(denied['error'], 'technical_blocked')
        self.assertEqual(self.app.advance()['action'], 'worker_blocked')
        self.assertEqual(self.app.status()['execution_failure']['failures'], policy_default('technical_retries'))
        self.assertEqual(self.repo.load(), before)
        self.assertEqual(self.repo.pending()['id'], self.task_id)
        with self.assertRaises(Error) as caught:
            self.prepare()
        self.assertEqual(caught.exception.code, 'technical_blocked')
        restored = self.prepare(reset=True)
        self.assertTrue(self.cli(view['commands']['ready'], restored['worker_env'])['ready'])
        self.assertEqual(self.repo.load(), before)

    def test_unrelated_read_does_not_clear_file_failure(self):
        prepared = self.prepare()
        view = self.full_view()
        self.cli(view['commands']['preflight'], prepared['worker_env'], code=2)
        self.cli(view['commands']['read'], prepared['worker_env'])
        self.assertEqual(self.repo.get(store_keys.technical_failure(self.task_id))['failures'], 1)
        second = self.cli(view['commands']['preflight'], prepared['worker_env'], code=2)
        self.assertEqual(second['details']['recovery']['failures'], 2)
        self.assertFalse(second['details']['recovery']['retry_allowed'])

    def test_matching_operation_success_resolves_failure(self):
        prepared = self.prepare()
        view = self.full_view()
        self.cli(view['commands']['preflight'], prepared['worker_env'], code=2)
        receipt = response(self.app, session='host-real-worker')
        receipt['session'] = ''
        Path(view['result_path']).write_text(json.dumps(receipt), encoding='utf-8')
        self.cli(view['commands']['preflight'], prepared['worker_env'])
        self.assertIsNone(self.repo.get(store_keys.technical_failure(self.task_id)))

    def test_portable_submit_replays_exact_success_and_rejects_conflict(self):
        prepared = self.prepare()
        view = self.full_view()
        receipt = response(self.app, session='host-real-worker')
        receipt['session'] = ''
        path = Path(view['result_path'])
        path.write_text(json.dumps(receipt), encoding='utf-8')
        first = self.cli(view['commands']['submit'], prepared['worker_env'])
        again = self.cli(view['commands']['submit'], prepared['worker_env'])
        self.assertTrue(again['idempotent'])
        self.assertEqual(again['committed_chapter'], first['committed_chapter'])
        self.assertEqual(again['outcome'], 'chapter_committed')
        self.assertEqual(len(self.repo.headers('main')), 1)
        receipt['data']['summary'] += '不同提交'
        path.write_text(json.dumps(receipt), encoding='utf-8')
        self.assertEqual(self.cli(view['commands']['submit'], prepared['worker_env'], code=2)['error'], 'replay_conflict')

    def test_replacement_worker_and_empty_context_get_all_required(self):
        prepared = self.prepare()
        view = self.full_view()
        original = self.cli(view['commands']['read'], prepared['worker_env'])
        self.assertTrue(original['records'])
        self.assertFalse(self.cli(view['commands']['read'], prepared['worker_env'])['records'])
        # Expiry is clock injection, not a direct mutation of story or task data.
        with patch.object(self.app, 'clock', return_value=self.app.clock() + 301):
            replacement = self.app.prepare_worker(self.task_id, 'host-real-replacement')
        fresh = self.cli(view['commands']['read'], replacement['worker_env'])
        self.assertEqual(set(fresh['records']), set(original['records']))
        self.assertNotEqual(fresh['execution_id'], original['execution_id'])
        reopened = self.app.prepare_worker(self.task_id, 'host-real-replacement', fresh_context=True)
        all_again = self.cli(view['commands']['read'], reopened['worker_env'])
        self.assertEqual(set(all_again['records']), set(original['records']))

    def test_business_failure_returns_all_findings_in_preview_and_submit(self):
        receipt = response(self.app)
        receipt['data']['prose'] += '他等了许久，窗外的雨沿着破损的玻璃往下流。值班室另一头有人收起了钥匙，走廊的灯熄了一盏，门后的脚步声渐渐远去。'
        before = self.repo.load()
        preview = self.app.submit(receipt, preview=True)
        self.assertEqual(self.repo.load(), before)
        self.assertEqual(preview['outcome'], 'repair_required')
        failure = next(f for f in preview['findings'] if f['criterion'] == 'substance')
        self.assertGreater(failure['actual_han'], failure['allowed'][1])
        submitted = self.app.submit(receipt)
        self.assertEqual(preview['findings'], submitted['findings'])
        self.assertIsNone(submitted['committed_chapter'])
        self.assertTrue(submitted['transaction']['persisted'])

    def test_unchanged_or_whitespace_repair_does_not_consume_budget(self):
        receipt = response(self.app)
        receipt['data']['prose'] += '他等了许久，窗外的雨沿着破损的玻璃往下流。值班室另一头有人收起了钥匙，走廊的灯熄了一盏，门后的脚步声渐渐远去。'
        self.app.submit(receipt)
        self.app.advance()
        before = self.repo.load()
        repair = response(self.app)
        repair['data'] = copy.deepcopy(receipt['data'])
        repair['data']['prose'] = '\n ' + repair['data']['prose'] + '  '
        with self.assertRaises(Error) as caught:
            self.app.submit(repair)
        self.assertEqual(caught.exception.code, 'no_progress')
        self.assertEqual(self.repo.load(), before)

    def test_frozen_build_rejects_changed_engine_before_materials_or_budget(self):
        self.assertIn('build', self.repo.task(self.task_id)['input'])
        self.app.build_info = {**self.app.build_info, 'engine_hash': 'different-build'}
        before = tuple(self.repo.db.iterdump())
        with self.assertRaises(Error) as caught:
            self.app.read(self.task_id)
        self.assertEqual(caught.exception.code, 'engine_changed')
        self.assertEqual(tuple(self.repo.db.iterdump()), before)

    def test_watch_returns_when_worker_reports_external_tool_failures(self):
        prepared = self.prepare()
        view = self.full_view()
        owner = self.app.run(through=1)['owner']
        for _ in range(policy_default('technical_retries')):
            argv = view['commands']['report_error'] + ['--code', 'host_tool', '--operation', 'host-read']
            self.cli(argv, prepared['worker_env'])
        outcome = unattended.watch(self.app, owner, poll=0.01, idle_limit=1,
                                   sleep=lambda _: self.fail('blocked task must not keep waiting'))
        self.assertEqual(outcome['action'], 'worker_blocked')
        self.assertEqual(outcome['task_id'], self.task_id)

    def test_old_session_and_controller_commands_cannot_be_used_as_worker(self):
        prepared = self.prepare()
        view = self.full_view()
        wrong = {**prepared['worker_env'], 'NOVEL_SESSION': 'previous-outline-worker'}
        failed = self.cli(view['commands']['ready'], wrong, code=2)
        self.assertEqual(failed['details']['recovery']['actor'], 'controller')
        argv = [sys.executable, str(ROOT / 'scripts/novel.py'), '--project', str(self.repo.project),
                'worker', '--task', self.task_id, '--', 'prepare-worker', '--task', self.task_id,
                '--session', 'invented']
        denied = self.cli(argv, code=2)
        self.assertEqual(denied['error'], 'worker_boundary')

    def test_controller_preparation_cli_and_owner_guard(self):
        owner = self.app.run(through=1)['owner']
        base = [sys.executable, str(ROOT / 'scripts/novel.py'), '--project', str(self.repo.project),
                'prepare-worker', '--task', self.task_id, '--session', 'host-created-cli-worker']
        denied = self.cli(base, code=2)
        self.assertEqual(denied['details']['recovery']['action'], 'renew_controller')
        self.assertIsNone(self.repo.get(store_keys.claim(self.task_id)))
        prepared = self.cli(base + ['--owner', owner])
        view = self.full_view()
        self.assertTrue(self.cli(view['commands']['ready'], prepared['worker_env'])['ready'])

    def test_single_chapter_summary_and_both_shell_quoting_rules(self):
        line = delivery.task_line({'stage': 'write', 'scope': 'chapter', 'chapter': 61,
                                   'first': 0, 'last': 0, 'required': []})
        self.assertIn('chapter=61', line)
        self.assertNotIn('0-0', line)
        with patch.object(delivery.sys, 'platform', 'win32'):
            command = delivery._quoted_argv(["C:/writer's folder/python.exe", '读正文'])
            self.assertTrue(command.startswith("& 'C:/writer''s folder/python.exe'"))

    def test_role_recovery_is_the_same_for_lease_and_boundary_errors(self):
        for code in ('worker_lease', 'controller_lease', 'role_boundary', 'session_reuse'):
            recovery = Error(code, '失败').as_dict()['details']['recovery']
            self.assertEqual(recovery, execution_recovery(code))
            self.assertEqual(recovery['actor'], 'controller')
            self.assertFalse(recovery['retry_allowed'])


if __name__ == '__main__':
    unittest.main()
