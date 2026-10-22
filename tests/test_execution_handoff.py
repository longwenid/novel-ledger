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
from support import contract, drive, prose_stub, response


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
        # The rendered shell command must survive spaces and apostrophes in paths on both
        # platforms: shlex round-trips the POSIX form, the win32 card is PowerShell-quoted.
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

    def test_successful_operation_clears_only_nonblocked_failure_streak(self):
        prepared = self.prepare()
        view = self.full_view()
        self.cli(view['commands']['preflight'], prepared['worker_env'], code=2)
        self.cli(view['commands']['read'], prepared['worker_env'])
        self.assertIsNone(self.repo.get(store_keys.technical_failure(self.task_id)))
        first = self.cli(view['commands']['preflight'], prepared['worker_env'], code=2)
        self.assertEqual(first['details']['recovery']['failures'], 1)

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

    def test_first_identity_fault_hands_back_without_reset_ceremony(self):
        view = self.full_view()
        denied = self.cli(view['commands']['ready'], code=2)   # credentials not injected yet
        self.assertEqual(denied['details']['recovery']['actor'], 'controller')
        self.assertFalse(denied['details']['recovery']['retry_allowed'])
        # Blocking is uniform at the retry limit: one identity fault routes to the controller
        # but does not block, so a plain prepare-worker re-claim recovers — no --reset-failures.
        self.assertFalse(denied['details']['recovery']['blocked'])
        prepared = self.prepare()
        self.assertEqual(self.repo.get(store_keys.technical_failure(self.task_id))['failures'], 1)
        self.assertTrue(self.cli(view['commands']['ready'], prepared['worker_env'])['ready'])
        # ready is a probe, not an operation: the streak stays until the first real read clears it.
        self.assertFalse(self.repo.get(store_keys.technical_failure(self.task_id))['blocked'])
        self.cli(view['commands']['read'], prepared['worker_env'])
        self.assertIsNone(self.repo.get(store_keys.technical_failure(self.task_id)))

    def test_role_recovery_is_the_same_for_lease_and_boundary_errors(self):
        for code in ('worker_lease', 'controller_lease', 'role_boundary', 'session_reuse'):
            recovery = Error(code, '失败').as_dict()['details']['recovery']
            self.assertEqual(recovery, execution_recovery(code))
            self.assertEqual(recovery['actor'], 'controller')
            self.assertFalse(recovery['retry_allowed'])


class ContentPreviewHandoffTests(unittest.TestCase):
    """Design-stage content defects answer previews as data: the full findings list, the stalled
    signal, and no technical accounting — the fix loop is the worker's own budget, not the
    controller's (measured: one unattended run burned 18 counted drift failures and ~14 blocking
    recoveries on exactly this path)."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="design worker's workspace ")
        self.addCleanup(self.temp.cleanup)
        self.runtime = open_local_runtime(Path(self.temp.name) / 'book', initialize=True,
                                          contract=contract(6))
        self.addCleanup(self.runtime.close)
        self.app, self.repo = self.runtime.app, self.runtime.repo
        self.view = drive(self.app, until='chapter_outline')['task']
        self.task_id = self.view['task_id']
        self.prepared = self.app.prepare_worker(self.task_id, 'design-worker')
        self.environment = {k: v for k, v in os.environ.items() if not k.startswith('NOVEL_')}

    def cli(self, argv, env=None, code=0):
        result = subprocess.run(argv, env={**self.environment, **(env or {})},
                                capture_output=True, text=True, encoding='utf-8', timeout=20)
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def broken_receipt(self):
        """A chapter-outline receipt whose every row fails the length, beat and style shape checks."""
        receipt = response(self.app, session='design-worker')
        for row in receipt['data']['chapters']:
            row['synopsis'] = '太短'
            row['plot'] = {'beat': '', 'nodes': [], 'threads': []}
            row['style'] = {'pov': '', 'rhythm': ''}
        return receipt

    def test_preflight_answers_all_findings_as_data_without_counting_failures(self):
        path = Path(self.view['result_path'])
        path.write_text(json.dumps(self.broken_receipt(), ensure_ascii=False), encoding='utf-8')
        checked = self.cli(self.view['commands']['preflight'], self.prepared['worker_env'])
        self.assertFalse(checked['valid'])
        self.assertTrue(checked['checked'])
        self.assertFalse(checked['committed'])
        self.assertEqual(checked['error'], 'design_drift')
        self.assertGreater(checked['findings_count'], 12)   # untruncated: the old sample cap was 12
        self.assertEqual(len(checked['findings']), checked['findings_count'])
        self.assertEqual(checked['content_rounds'], 1)
        self.assertFalse(checked['stalled'])
        self.assertIsNone(self.repo.get(store_keys.technical_failure(self.task_id)))
        self.assertFalse(self.app.task_status(self.task_id)['execution_blocked'])

    def test_repeated_blind_retries_signal_stalled_and_progress_resets_it(self):
        path = Path(self.view['result_path'])
        path.write_text(json.dumps(self.broken_receipt(), ensure_ascii=False), encoding='utf-8')
        rounds = [self.cli(self.view['commands']['preflight'], self.prepared['worker_env'])
                  for _ in range(policy_default('design_stall_rounds'))]
        self.assertEqual([row['content_rounds'] for row in rounds],
                         list(range(1, policy_default('design_stall_rounds') + 1)))
        self.assertTrue(rounds[-1]['stalled'])
        self.assertIn('stalled', rounds[-1]['note'])
        self.assertFalse(self.app.task_status(self.task_id)['execution_blocked'])
        # A changed finding set is progress: the count restarts and the stall clears.
        receipt = self.broken_receipt()
        receipt['data']['chapters'][0]['synopsis'] = '改掉一章的字数问题，其余保持。'
        path.write_text(json.dumps(receipt, ensure_ascii=False), encoding='utf-8')
        moved = self.cli(self.view['commands']['preflight'], self.prepared['worker_env'])
        self.assertEqual(moved['content_rounds'], 1)
        self.assertFalse(moved['stalled'])
        self.assertIsNone(self.repo.get(store_keys.technical_failure(self.task_id)))

    def test_submit_content_refusal_still_raises_and_never_counts(self):
        path = Path(self.view['result_path'])
        path.write_text(json.dumps(self.broken_receipt(), ensure_ascii=False), encoding='utf-8')
        for _ in range(2):
            refused = self.cli(self.view['commands']['submit'], self.prepared['worker_env'], code=2)
            self.assertEqual(refused['error'], 'design_drift')
        self.assertIsNone(self.repo.get(store_keys.technical_failure(self.task_id)))
        # Not blocked: the worker keeps reading material and converging on its own budget.
        read = self.cli(self.view['commands']['read'], self.prepared['worker_env'])
        self.assertEqual(read['task_id'], self.task_id)


class WriteReceiptHandoffTests(unittest.TestCase):
    """The write chapter's mechanical assembly is an engine command: draft file in, receipt file
    out, preflight green — the model spends its calls on prose and verdicts, not on plumbing
    (measured: a fast-group worker burned ~10 extraction calls per chapter on exactly this)."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="prose worker's workspace ")
        self.addCleanup(self.temp.cleanup)
        self.runtime = open_local_runtime(Path(self.temp.name) / 'book', initialize=True, contract=contract(6))
        self.addCleanup(self.runtime.close)
        self.app, self.repo = self.runtime.app, self.runtime.repo
        self.view = drive(self.app, until='write')['task']
        self.task_id = self.view['task_id']
        self.prepared = self.app.prepare_worker(self.task_id, 'prose-worker')
        self.environment = {k: v for k, v in os.environ.items() if not k.startswith('NOVEL_')}

    def cli(self, argv, env=None, code=0):
        result = subprocess.run(argv, env={**self.environment, **(env or {})},
                                capture_output=True, text=True, encoding='utf-8', timeout=20)
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def task_view(self):
        return json.loads(Path(self.view['task_path']).read_text(encoding='utf-8'))

    def test_read_save_lands_the_pack_and_keeps_the_answer_compact(self):
        view = self.task_view()
        pack = Path(view['task_path']).with_name('read_pack.json')
        saved = self.cli(view['commands']['read'] + ['--save', str(pack)], self.prepared['worker_env'])
        self.assertEqual(saved['saved'], str(pack))
        self.assertEqual(len(saved['packs']), 3)              # json + writing pack + reference pack
        self.assertIn('records', saved)                       # the record names …
        self.assertLess(len(json.dumps(saved, ensure_ascii=False)), 1500)  # … not the bodies
        writing = pack.with_name('read_pack.md')
        reference = pack.with_name('read_ref.md')
        landed_pack = writing.read_text(encoding='utf-8')
        self.assertIn('## chapter_outline', landed_pack)      # the per-chapter material, in one file
        self.assertIn('## previous_chapters', landed_pack)
        self.assertIn('contract', reference.read_text(encoding='utf-8'))
        landed = json.loads(pack.read_text(encoding='utf-8'))
        self.assertTrue(landed['records'])
        self.assertEqual(sorted(landed['records']), saved['records'])

    def test_receipt_assembles_from_the_draft_and_preflight_goes_green(self):
        view = self.task_view()
        commands = view['commands']
        self.assertIn('receipt', commands)
        draft = Path(view['task_path']).with_name('draft.md')
        draft.write_text(prose_stub(1), encoding='utf-8')
        assembled = self.cli(commands['receipt'] +
                             ['--title', '封条一', '--summary', '沈桐要求核对退件来源。',
                              '--self-check', '逐项按章纲比对，动作与证据均在正文中，无计划外变化。'],
                             self.prepared['worker_env'])
        self.assertEqual(assembled['missing'], [])
        self.assertEqual(assembled['quotes_unlocated'], [])
        self.assertGreaterEqual(assembled['items'], 4)
        receipt_path = Path(view['result_path'])
        self.assertTrue(receipt_path.exists())
        # The receipt the engine wrote is the receipt the engine accepts, unchanged.
        checked = self.cli(commands['preflight'], self.prepared['worker_env'])
        self.assertTrue(checked['valid'], checked.get('findings'))
        accepted = self.cli(commands['submit'], self.prepared['worker_env'])
        self.assertEqual(accepted['committed_chapter'], 1)


if __name__ == '__main__':
    unittest.main()
