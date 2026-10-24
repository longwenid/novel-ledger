"""Selected remote improvements preserve execution, evidence and preview boundaries."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'tests')]
from novel_ledger import delivery, drift, store_keys
from novel_ledger.bootstrap import open_local_runtime
from novel_ledger.contracts import Error, policy_default
from support import contract, drive, response


class RemoteIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.runtime = open_local_runtime(Path(self.temp.name) / 'book', initialize=True, contract=contract(2))
        self.addCleanup(self.runtime.close)
        self.app, self.repo = self.runtime.app, self.runtime.repo
        self.environment = {k: v for k, v in os.environ.items() if not k.startswith('NOVEL_')}

    def writer(self, seconds=300):
        view = drive(self.app, until='write')['task']
        prepared = self.app.prepare_worker(view['task_id'], 'integration-writer', seconds=seconds)
        return view, prepared, json.loads(Path(view['task_path']).read_text())

    def cli(self, command, prepared, code=0):
        process = subprocess.run(command, env={**self.environment, **prepared['worker_env']},
                                 capture_output=True, text=True, timeout=20)
        self.assertEqual(process.returncode, code, process.stdout + process.stderr)
        return json.loads(process.stdout)

    def test_heartbeat_preserves_grant_and_never_revives_expired_or_wrong_claim(self):
        view, prepared, _ = self.writer(seconds=7200)
        task, token = view['task_id'], prepared['worker_env']['NOVEL_EXECUTION_CLAIM']
        now, original_book = self.app.clock(), self.repo.load()
        self.app.clock = lambda: now + 100
        self.app.worker_heartbeat(task, 'integration-writer', token)
        lease = self.repo.get(store_keys.claim(task))
        self.assertEqual(lease['until'], now + 100 + 7200)
        for session, value in [('other-context', token), ('integration-writer', 'wrong-token')]:
            with self.assertRaises(Error):
                self.app.worker_heartbeat(task, session, value)
            self.assertEqual(self.repo.get(store_keys.claim(task)), lease)
        self.app.clock = lambda: lease['until'] + 1
        with self.assertRaises(Error):
            self.app.worker_heartbeat(task, 'integration-writer', token)
        self.assertEqual(self.repo.load(), original_book)

    def test_default_lease_follows_silent_design_or_prose_stage(self):
        task = self.app.advance()['task']['task_id']
        lease = self.app.claim(task, 'design-worker')
        self.assertEqual(lease['seconds'], policy_default('single_delivery_lease_seconds'))
        self.app.release_claim(task, lease['token'])
        prose = drive(self.app, until='write')['task']['task_id']
        self.assertEqual(self.app.claim(prose, 'prose-worker')['seconds'], policy_default('worker_lease_seconds'))

    def test_read_save_delivers_all_records_and_full_previous_prose(self):
        view, prepared, disk = self.writer()
        result = self.cli(disk['commands']['read'] + ['--save'], prepared)
        payload = json.loads(Path(result['saved']).read_text())
        self.assertEqual(set(payload['records']), set(self.repo.task(view['task_id'])['input']['required']))
        self.assertTrue(all(Path(path).is_file() for path in result['packs']))
        previous = '开端标识' + '不可截断的前文证据。' * 700 + '末尾标识'
        packs = delivery.pack_markdowns({'task_id': 'complete-prose', 'records': {
            'previous_chapters': {'value': [{'chapter': 1, 'prose': previous}]},
            'contract': {'value': {'voice': '完整参考设定。'}}}})
        self.assertIn(previous, packs['read_pack.md'])
        self.assertIn('完整参考设定。', packs['read_ref.md'])

    def test_failed_material_save_preserves_undelivered_cache(self):
        view, prepared, disk = self.writer()
        cache_key = store_keys.execution_reads(self.repo.get(store_keys.claim(view['task_id']))['execution_id'])
        before = self.repo.get(cache_key)
        failed = self.cli(disk['commands']['read'] + ['--save', str(self.repo.project / 'novel.sqlite3')], prepared, code=2)
        self.assertEqual(failed['error'], 'output')
        self.assertEqual(self.repo.get(cache_key), before)
        delivered = self.cli(disk['commands']['read'], prepared)
        self.assertEqual(set(delivered['records']), set(self.repo.task(view['task_id'])['input']['required']))

    def test_material_output_cannot_alias_a_pack(self):
        _, prepared, disk = self.writer()
        failed = self.cli(disk['commands']['read'] + ['--save', str(self.repo.project / 'read_pack.md')], prepared, code=2)
        self.assertEqual(failed['error'], 'output')
        self.assertFalse((self.repo.project / 'read_pack.md').exists())

    def test_content_preview_does_not_count_or_clear_an_unresolved_file_failure(self):
        view, prepared, disk = self.writer()
        receipt = response(self.app, session='integration-writer')
        receipt['data']['drift_check'] = 'invalid'
        Path(disk['result_path']).write_text(json.dumps(receipt), encoding='utf-8')
        recovery = self.app.worker_failure(view['task_id'], 'integration-writer', 'preflight', 'file')
        self.assertTrue(recovery['syntax_error'])
        before = self.repo.load()
        for _ in range(3):
            result = self.cli(disk['commands']['preflight'], prepared)
            self.assertFalse(result['valid'])
            self.assertEqual(result['outcome'], 'repair_required')
            self.assertTrue(result['findings'])
            # Syntax errors don't consume the technical budget; the unresolved content
            # failure is tracked by content_rounds/stalled, not by the failure counter.
            self.assertIsNone(self.repo.get(store_keys.technical_failure(view['task_id'])))
        self.assertEqual(self.repo.load(), before)
        self.assertEqual(self.repo.headers('main'), [])
        self.assertEqual(result['content_rounds'], 3)
        self.assertTrue(result['stalled'])
        self.assertEqual(result['next_action']['actor'], 'controller')

    def test_core_preview_stays_read_only_and_diagnostic_lists_are_complete(self):
        self.writer()
        receipt = response(self.app, session='integration-writer')
        receipt['execution_claim'] = self.repo.get(store_keys.claim(receipt['task_id']))['token']
        before = tuple(self.repo.db.iterdump())
        self.app.check(receipt)
        self.assertEqual(tuple(self.repo.db.iterdump()), before)
        findings = [{'criterion': 'test', 'reason': str(index)} for index in range(20)]
        with self.assertRaises(Error) as caught:
            drift._reject(findings, 'design_drift', 'all findings')
        self.assertEqual(caught.exception.details['findings'], findings)
        self.assertEqual(caught.exception.details['findings_count'], 20)


if __name__ == '__main__':
    unittest.main()
