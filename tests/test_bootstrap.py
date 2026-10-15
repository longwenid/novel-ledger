"""Real composition bridges: SQLite, use cases, local files and the CLI together."""
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

from novel_ledger.bootstrap import open_local_runtime
from novel_ledger.contracts import digest
from support import contract, drive


class BootstrapIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = (Path(self.temp.name) / 'book').resolve()
        self.runtime = open_local_runtime(self.project, initialize=True, contract=contract(2),
                                          source='工程夹具作者约定。')

    def tearDown(self):
        if self.runtime is not None:
            self.runtime.close()
        self.temp.cleanup()

    def close_runtime(self):
        self.runtime.close()
        self.runtime = None

    def cli_deliver(self):
        environment = {key: value for key, value in os.environ.items()
                       if not key.startswith('NOVEL_')}
        process = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'novel.py'),
                                  '--project', str(self.project), 'deliver'],
                                 env=environment, capture_output=True, text=True,
                                 encoding='utf-8', timeout=20)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        result = json.loads(process.stdout)
        self.assertTrue(result['delivered'])
        return result

    def assert_recorded_delivery(self, result, snapshot_hash, chapters, count):
        manifest_path = self.project / 'delivery.json'
        self.assertEqual(result['manifest_path'], str(manifest_path))
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        self.assertEqual(manifest['snapshot_hash'], snapshot_hash)
        self.assertEqual(manifest['chapters'], chapters)
        self.assertEqual({row['path'] for row in manifest['files']},
                         {str(self.project / name) for name in ('book.md', 'book.html')})
        for row in manifest['files']:
            self.assertEqual(row['content_hash'], digest(Path(row['path']).read_text(encoding='utf-8')))
        self.assertEqual(self.runtime.repo.get('completion_delivery'), manifest)
        journal = self.runtime.repo.db.execute(
            "SELECT value FROM journal WHERE action='deliver' ORDER BY id").fetchall()
        self.assertEqual([json.loads(row['value']) for row in journal],
                         [{'snapshot_hash': snapshot_hash}] * count)
        return manifest

    def test_real_cli_delivery_records_and_reuses_the_completed_snapshot_after_reopen(self):
        app, repo = self.runtime.app, self.runtime.repo
        owner = app.run(finish=True, source='工程夹具作者授权写完。')['owner']
        self.assertEqual(drive(app, owner)['action'], 'ready_to_complete')
        completed = app.complete(owner)
        snapshot_hash = completed['snapshot_hash']
        snapshot = repo.read_document(snapshot_hash)
        chapters = [{'chapter': row['n'], 'prose_hash': row['prose']}
                    for row in snapshot['chapters']]
        self.assertEqual(len(chapters), 2)
        self.close_runtime()

        first_result = self.cli_deliver()
        self.runtime = open_local_runtime(self.project)
        first = self.assert_recorded_delivery(first_result, snapshot_hash, chapters, 1)
        frozen_files = {name: (self.project / name).read_bytes()
                        for name in ('book.md', 'book.html')}
        self.assertIn(contract(2)['title'], frozen_files['book.md'].decode('utf-8'))

        # The completed snapshot remains authoritative if the mutable live view
        # differs. Reopening and retrying must not export that mutable content.
        with self.runtime.repo.transaction():
            live = self.runtime.repo.load()
            live['contract']['title'] = '完本后可变投影中的书名'
            self.runtime.repo.save(live)
        self.close_runtime()
        second_result = self.cli_deliver()
        self.runtime = open_local_runtime(self.project)
        second = self.assert_recorded_delivery(second_result, snapshot_hash, chapters, 2)
        self.assertEqual(second, first)
        for name, content in frozen_files.items():
            self.assertEqual((self.project / name).read_bytes(), content)

        # The facade's direct path uses the same application recording bridge.
        third_result = self.runtime.deliver()
        self.assertEqual(self.assert_recorded_delivery(third_result, snapshot_hash, chapters, 3), first)

    def worker_files(self):
        task = self.runtime.app.advance()['task']
        paths = [Path(task['input_path']), Path(task['template_path'])]
        receipt = Path(task['result_path'])
        receipt.write_text('Worker 独立写入的回执', encoding='utf-8')
        return task['task_id'], {path: path.read_bytes() for path in paths}, receipt

    def test_real_form_retirement_waits_for_database_commit(self):
        task_id, files, receipt = self.worker_files()
        repo = self.runtime.repo
        original_save = repo.save
        observed = []

        def inspect_before_commit(book):
            self.assertTrue(repo.db.in_transaction)
            self.assertIsNone(repo.pending())
            self.assertEqual(repo.task(task_id)['status'], 'cancelled')
            for path, content in files.items():
                self.assertEqual(path.read_bytes(), content)
            observer = open_local_runtime(self.project)
            try:
                self.assertEqual(observer.repo.pending()['id'], task_id)
            finally:
                observer.close()
            observed.append('uncommitted cancellation keeps forms')
            original_save(book)

        with patch.object(repo, 'save', side_effect=inspect_before_commit):
            self.runtime.app.set_lexical({'forbidden_name_chars': ['砚']}, '作者调整字面规则。')

        self.assertEqual(observed, ['uncommitted cancellation keeps forms'])
        self.assertFalse(repo.db.in_transaction)
        self.assertIsNone(repo.pending())
        self.assertEqual(repo.task(task_id)['status'], 'cancelled')
        self.assertTrue(all(not path.exists() for path in files))
        self.assertEqual(receipt.read_text(encoding='utf-8'), 'Worker 独立写入的回执')

    def test_failed_save_rolls_back_cancellation_without_retiring_real_forms(self):
        task_id, files, receipt = self.worker_files()
        repo = self.runtime.repo
        before = repo.load()
        cancel_count = repo.db.execute("SELECT count(*) FROM journal WHERE action='cancel'").fetchone()[0]

        def fail_after_cancellation(book):
            self.assertTrue(repo.db.in_transaction)
            self.assertIsNone(repo.pending())
            for path, content in files.items():
                self.assertEqual(path.read_bytes(), content)
            raise OSError('simulated persistence failure')

        with patch.object(repo, 'save', side_effect=fail_after_cancellation):
            with self.assertRaisesRegex(OSError, 'simulated persistence failure'):
                self.runtime.app.set_lexical({'forbidden_name_chars': ['砚']}, '作者调整字面规则。')

        self.assertEqual(repo.pending()['id'], task_id)
        self.assertEqual(repo.task(task_id)['status'], 'pending')
        self.assertEqual(repo.load(), before)
        self.assertEqual(repo.db.execute("SELECT count(*) FROM journal WHERE action='cancel'").fetchone()[0], cancel_count)
        # An unrelated later commit must not revive a rolled-back delivery effect.
        with repo.transaction():
            repo.put('later_commit', True)
        for path, content in files.items():
            self.assertEqual(path.read_bytes(), content)
        self.assertEqual(receipt.read_text(encoding='utf-8'), 'Worker 独立写入的回执')


if __name__ == '__main__':
    unittest.main()
