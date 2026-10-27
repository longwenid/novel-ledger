"""Frozen installs and exact task recovery, with real CLI processes and SQLite transactions."""
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'tests')]
from novel_ledger import context, runtime_install, store_keys
from novel_ledger.bootstrap import local_application, local_workspace, open_local_runtime
from novel_ledger.contracts import Error, digest
from support import contract, drive, response


class RuntimeInstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.source = self.base / 'source'
        self.source.mkdir()
        for name in runtime_install.PARTS:
            path = ROOT / name
            if path.is_dir():
                shutil.copytree(path, self.source / name, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.DS_Store'))
            elif path.is_file():
                shutil.copy2(path, self.source / name)
        self.target = self.base / 'fixed'
        self.environment = {key: value for key, value in os.environ.items() if not key.startswith('NOVEL_')}

    def cli(self, entry, *args, code=0):
        process = subprocess.run([sys.executable, str(entry), *map(str, args)], capture_output=True,
                                 text=True, encoding='utf-8', env=self.environment, timeout=30)
        self.assertEqual(process.returncode, code, process.stdout + process.stderr)
        return json.loads(process.stdout)

    def test_fixed_cli_survives_source_changes_and_emits_fixed_worker_commands(self):
        pinned = self.cli(self.source / 'scripts/novel.py', 'pin-engine', '--output', self.target)
        before = runtime_install.verify(self.target)['build']
        (self.source / 'references/runtime.md').write_text('开发中的另一版运行规则。', encoding='utf-8')
        project = self.base / 'book'
        self.cli(pinned['entry'], '--project', project, 'init')
        step = self.cli(pinned['entry'], '--project', project, 'advance', '--compact')
        self.assertTrue(step['controller']['must_continue'])
        task = json.loads(Path(step['task']['task_path']).read_text())
        self.assertEqual(Path(task['commands']['submit'][1]), self.target / 'scripts/novel.py')
        self.assertEqual(runtime_install.verify(self.target)['build'], before)
        self.assertTrue(self.cli(pinned['entry'], '--project', project, 'host-check')['watch_creates_workers'] is False)
        reused = runtime_install.pin(self.source, self.target)
        self.assertTrue(reused['reused'])
        self.assertFalse(reused['source_matches_runtime'])
        self.assertEqual(reused['source_build'], runtime_install.build_at(self.source))
        self.assertEqual(reused['build'], before)

    def test_no_overwrite_source_or_unrelated_directory_and_no_partial_mismatch(self):
        for target in (self.source, self.source / 'runtime', self.base):
            with self.assertRaises(Error):
                runtime_install.pin(self.source, target)
        expected = {**runtime_install.build_at(self.source), 'engine_hash': 'not-the-release'}
        with self.assertRaises(Error):
            runtime_install.pin(self.source, self.target, expected=expected)
        self.assertFalse(self.target.exists())
        self.assertFalse(any(self.base.glob('.novel-runtime-*')))

    def test_installer_detects_tampered_template_and_refuses_reuse(self):
        runtime_install.pin(self.source, self.target)
        template = self.target / 'scripts/novel_ledger/templates/book.js'
        template.chmod(0o644)
        template.write_text('tampered', encoding='utf-8')
        with self.assertRaises(Error):
            runtime_install.pin(self.source, self.target)
        result = self.cli(self.target / 'scripts/novel.py', '--project', self.base / 'book', 'init', code=2)
        self.assertEqual(result['error'], 'engine_changed')
        self.assertFalse((self.base / 'book/novel.sqlite3').exists())

    def test_frozen_target_remains_usable_when_development_source_is_incomplete(self):
        runtime_install.pin(self.source, self.target)
        (self.source / 'scripts/novel_ledger/contracts.py').write_text('unfinished = (', encoding='utf-8')
        reused = runtime_install.pin(self.source, self.target)
        self.assertTrue(reused['reused'])
        self.assertIsNone(reused['source_build'])
        self.assertIsNone(reused['source_matches_runtime'])
        self.assertEqual(reused['build'], runtime_install.verify(self.target)['build'])

    def test_mismatch_reports_distinct_frozen_and_authorized_upgrade_paths(self):
        expected = {**runtime_install.build_at(self.source), 'engine_hash': 'old-release'}
        task = {'task_id': 'exact-pending-task', 'input_hash': 'frozen-input-hash'}
        for existing in (False, True):
            if existing:
                runtime_install.pin(self.source, self.target)
            with self.assertRaises(Error) as caught:
                runtime_install.pin(self.source, self.target, expected=expected,
                                    project=self.base / 'book', task=task)
            details = caught.exception.details
            self.assertEqual(details['expected'], expected)
            self.assertEqual(details['selected'], runtime_install.build_at(self.source))
            self.assertEqual({key: details[key] for key in task}, task)
            paths = details['recovery_options']
            self.assertFalse(paths['match_frozen_build']['changes_task'])
            self.assertIn('--ref', paths['match_frozen_build']['command_template'])
            upgrade = paths['upgrade_frozen_task']
            self.assertTrue(upgrade['requires_author_upgrade'])
            self.assertNotIn('--project', upgrade['prepare_command_template'])
            recovery = upgrade['recover_command_template']
            self.assertEqual(recovery[1], '<new-runtime-directory>/scripts/novel.py')
            self.assertEqual(recovery[recovery.index('--task') + 1], task['task_id'])
            self.assertEqual(recovery[recovery.index('--input-hash') + 1], task['input_hash'])
            self.assertNotIn('--worker-stopped', recovery)
            self.assertEqual(self.target.exists(), existing)
            self.assertFalse(any(self.base.glob('.novel-runtime-*')))

    def test_new_fixed_release_recovers_exact_pending_task_without_development_tree_edits(self):
        source_entry = self.source / 'scripts/novel.py'
        project = self.base / 'book'
        self.cli(source_entry, '--project', project, 'init')
        step = self.cli(source_entry, '--project', project, 'advance', '--compact')
        task_id = step['task']['task_id']
        frozen = json.loads((project / 'work' / task_id / 'task.json').read_text())
        before = (project / 'novel.sqlite3').read_bytes()
        rules = self.source / 'references/runtime.md'
        changed_rules = rules.read_text() + '\n选定的新发布规则。\n'
        rules.write_text(changed_rules, encoding='utf-8')
        mismatch = self.cli(source_entry, '--project', project, 'pin-engine', '--output', self.target, code=2)
        self.assertEqual(mismatch['error'], 'engine_changed')
        details = mismatch['details']
        self.assertEqual(details['task_id'], task_id)
        self.assertEqual(details['input_hash'], frozen['input_hash'])
        self.assertEqual((project / 'novel.sqlite3').read_bytes(), before)
        self.assertFalse(self.target.exists())
        pinned = self.cli(source_entry, 'pin-engine', '--output', self.target)
        self.assertEqual((project / 'novel.sqlite3').read_bytes(), before)
        self.assertEqual(rules.read_text(), changed_rules)
        result = self.cli(pinned['entry'], '--project', project, 'recover-engine', '--task', task_id,
                          '--input-hash', frozen['input_hash'], '--source', '作者授权将准确待办切换到选定新发布。')
        self.assertEqual(result['retired_task'], task_id)
        self.assertNotEqual(result['task']['task_id'], task_id)
        self.assertEqual(rules.read_text(), changed_rules)
        new_task = json.loads(Path(result['task']['task_path']).read_text())
        self.assertEqual(Path(new_task['commands']['submit'][1]), self.target / 'scripts/novel.py')

    def test_release_pin_matches_pending_build_without_checkout_or_project_mutation(self):
        # Releases may omit optional directories; passing absent pathspecs to git
        # archive would reject an otherwise complete, matching installation.
        shutil.rmtree(self.source / 'docs', ignore_errors=True)
        self.assertEqual(subprocess.run(['git', 'init', '-q', str(self.source)]).returncode, 0)
        for args in (['add', '.'], ['-c', 'user.name=Runtime Test', '-c', 'user.email=runtime@example.invalid',
                                  'commit', '-qm', 'release']):
            subprocess.run(['git', '-C', str(self.source), *args], check=True, capture_output=True)
        source_entry = self.source / 'scripts/novel.py'
        project = self.base / 'book'
        self.cli(source_entry, '--project', project, 'init')
        step = self.cli(source_entry, '--project', project, 'advance', '--compact')
        before = (project / 'novel.sqlite3').read_bytes()
        rule = self.source / 'references/runtime.md'
        original = rule.read_text()
        rule.write_text(original + '\n开发改动\n')
        result = self.cli(source_entry, '--project', project, 'pin-engine', '--ref', 'HEAD', '--output', self.target)
        self.assertEqual((project / 'novel.sqlite3').read_bytes(), before)
        self.assertIn('开发改动', rule.read_text())
        frozen = json.loads((project / 'work' / step['task']['task_id'] / 'input.json').read_text())
        self.assertEqual(result['build'], frozen['build'])
        self.assertEqual(result['build'], runtime_install.build_at(self.target))
        self.cli(result['entry'], '--project', project, 'advance', '--compact')
        reused = runtime_install.pin(self.source, self.target, ref='HEAD')
        self.assertTrue(reused['reused'])
        self.assertTrue(reused['source_matches_runtime'])
        self.assertEqual(reused['source_build'], result['build'])
        with self.assertRaises(Error):
            runtime_install.pin(self.source, self.target, ref='missing-release')



class EngineRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.runtime = open_local_runtime(Path(self.temp.name) / 'book', initialize=True, contract=contract(12))
        self.addCleanup(self.runtime.close)
        self.repo, self.app = self.runtime.repo, self.runtime.app
        # A real old compiler freezes old build metadata. The replacement factory uses the
        # current compiler, exactly as two separately installed releases would.
        self.old_build = {**self.app.build_info, 'engine_hash': 'old-release'}
        self.app.build_info = self.old_build
        self.app._writing.compile_task = lambda book, job: {**context.build(self.repo, book, job), 'build': self.old_build}
        self.owner = self.app.run(finish=True, source='测试作者授权完本。', mode='fast')['owner']
        self.first = drive(self.app, self.owner, until='write')['task']
        self.new = local_application(self.repo)

    def recover(self, task=None, **options):
        task = task or self.repo.pending()
        return self.new.recover_engine(task['id'], task['input_hash'], '作者明确授权切换当前待办至新发布构建。',
                                       self.owner, **options)

    def test_exact_recovery_keeps_plan_candidate_target_and_budget_without_replanning(self):
        task = self.repo.pending()
        receipt = response(self.app)
        candidate = self.repo.project / 'work' / task['id'] / 'result.json'
        candidate.write_text(json.dumps(receipt, ensure_ascii=False), encoding='utf-8')
        before = copy.deepcopy(self.repo.load())
        result = self.recover()
        after = self.repo.load()
        self.assertTrue(result['controller']['must_continue'])
        self.assertNotEqual(result['task']['task_id'], task['id'])
        self.assertEqual(self.repo.task(task['id'])['status'], 'cancelled')
        self.assertEqual(self.repo.task(task['id'])['input']['build'], self.old_build)
        self.assertEqual(self.repo.pending()['input']['build'], self.new.build_info)
        for field in ('plans', 'chapter_outlines', 'volumes_outline', 'contract', 'state', 'draft', 'rework', 'target', 'finish'):
            self.assertEqual(after[field], before[field], field)
        self.assertEqual(json.loads(candidate.read_text())['data'], receipt['data'])
        self.assertEqual(self.repo.headers('main'), [])
        with self.assertRaises(Error):
            self.app.submit(receipt)

    def test_recovery_requires_exact_task_stopped_worker_and_author_upgrade_proof(self):
        task = self.repo.pending()
        self.app.prepare_worker(task['id'], 'real-old-worker', self.owner)
        before = tuple(self.repo.db.iterdump())
        for operation in (
            lambda: self.new.recover_engine(task['id'], 'wrong-hash', '允许切换。', self.owner, True),
            lambda: self.new.recover_engine(task['id'], task['input_hash'], '', self.owner, True),
            lambda: self.recover(),
        ):
            with self.assertRaises(Error):
                operation()
            self.assertEqual(tuple(self.repo.db.iterdump()), before)
        result = self.recover(worker_stopped=True)
        self.assertTrue(result['task']['requires_new_worker'])
        self.assertFalse(self.new.worker_presence(result['task']['task_id'])['identity_registered'])

    def test_compile_failure_rolls_back_cancel_group_and_story_revision(self):
        task = self.repo.pending()
        before = tuple(self.repo.db.iterdump())
        with patch.object(self.new._writing, 'compile_task', side_effect=RuntimeError('compiler failed')):
            with self.assertRaisesRegex(RuntimeError, 'compiler failed'):
                self.recover()
        self.assertEqual(tuple(self.repo.db.iterdump()), before)
        self.assertTrue((self.repo.project / 'work' / task['id'] / 'input.json').exists())

    def test_repair_candidate_and_spent_budget_survive_recovery(self):
        receipt = response(self.app)
        receipt['data']['drift_check']['items'].pop()
        self.app.submit(receipt)
        self.app.advance(owner=self.owner)
        before = copy.deepcopy(self.repo.load())
        self.assertIsNotNone(before['draft'])
        result = self.recover()
        self.assertEqual(result['task']['stage'], self.repo.pending()['input']['stage'])
        for field in ('draft', 'rework', 'plans', 'chapter_outlines', 'prior_candidate'):
            self.assertEqual(self.repo.load().get(field), before.get(field), field)

    def test_local_cli_cannot_authorize_upgrade_in_required_trust_mode(self):
        runtime = open_local_runtime(Path(self.temp.name) / 'required', initialize=True, contract=contract(2))
        try:
            runtime.app.configure_assurance('required', 'off', '作者明确要求可验证宿主。')
            runtime.app.build_info = self.old_build
            runtime.app._writing.compile_task = lambda book, job: {**context.build(runtime.repo, book, job), 'build': self.old_build}
            runtime.app.advance()
            pending = runtime.repo.pending()
            before = tuple(runtime.repo.db.iterdump())
            current = local_application(runtime.repo)
            with self.assertRaises(Error) as caught:
                current.recover_engine(pending['id'], pending['input_hash'], '自行声称作者授权升级。')
            self.assertEqual(caught.exception.code, 'host_authority')
            self.assertEqual(tuple(runtime.repo.db.iterdump()), before)
        finally:
            runtime.close()

    def test_recovery_cli_returns_new_task_and_old_candidate_location(self):
        task = self.repo.pending()
        environment = {key: value for key, value in os.environ.items() if not key.startswith('NOVEL_')}
        process = subprocess.run([sys.executable, str(ROOT / 'scripts/novel.py'), '--project', str(self.repo.project),
                                  '--owner', self.owner, 'recover-engine', '--task', task['id'],
                                  '--input-hash', task['input_hash'], '--source', '作者明确授权升级当前待办。'],
                                 env=environment, capture_output=True, text=True, encoding='utf-8', timeout=30)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        result = json.loads(process.stdout)
        self.assertEqual(result['retired_task'], task['id'])
        self.assertNotEqual(result['task']['task_id'], task['id'])
        self.assertEqual(result['preserved_result_path'], str(self.repo.project / 'work' / task['id'] / 'result.json'))

    def test_presence_never_equates_registration_or_activity_with_running_process(self):
        task = self.repo.pending()
        self.assertEqual(self.app.worker_presence(task['id'])['phase'], 'await_worker_identity')
        prepared = self.app.prepare_worker(task['id'], 'actual-worker', self.owner)
        self.assertTrue(prepared['identity_registered'])
        self.assertFalse(prepared['worker_presence']['activity_observed'])
        self.assertEqual(prepared['worker_presence']['phase'], 'await_worker_start')
        self.app.worker_ready(task['id'], 'actual-worker', prepared['worker_env']['NOVEL_EXECUTION_CLAIM'])
        self.app.read(task['id'])
        seen = self.app.worker_presence(task['id'])
        self.assertTrue(seen['activity_observed'])
        self.assertIsNone(seen['worker_running'])
        self.app.clock = lambda: seen['lease_until'] + 1
        self.assertEqual(self.app.worker_presence(task['id'])['phase'], 'lease_expired')
        self.assertFalse(self.app.status()['worker_presence']['lease_valid'])
