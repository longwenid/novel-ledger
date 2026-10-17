"""The storage adapter owns transactions and rows, never delivery artifacts."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from novel_ledger.sqlite_store import SQLiteRepository
from support import link_or_skip


class StorageBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / 'book'
        self.repo = SQLiteRepository.initialize(self.project, {})

    def tearDown(self):
        self.repo.close()
        self.temp.cleanup()

    def test_cancellation_only_changes_rows_and_returns_the_task_id(self):
        task = self.repo.add_task({'stage': 'storage-probe'})
        artifact = self.project / 'work' / task['id'] / 'result.template.json'
        artifact.parent.mkdir(parents=True)
        artifact.write_text('worker draft', encoding='utf-8')

        with self.repo.transaction():
            self.assertEqual(self.repo.cancel_pending('cancel probe'), task['id'])

        self.assertEqual(self.repo.task(task['id'])['status'], 'cancelled')
        self.assertEqual(artifact.read_text(encoding='utf-8'), 'worker draft')
        logged = self.repo.db.execute("SELECT value FROM journal WHERE action='cancel'").fetchone()
        self.assertEqual(json.loads(logged['value']), {'reason': 'cancel probe', 'task': task['id']})
        self.assertIsNone(self.repo.cancel_pending('nothing left'))

    def test_cancellation_rollback_keeps_task_and_worker_files(self):
        task = self.repo.add_task({'stage': 'storage-probe'})
        artifact = self.project / 'work' / task['id'] / 'result.json'
        artifact.parent.mkdir(parents=True)
        artifact.write_text('submitted receipt', encoding='utf-8')

        with self.assertRaisesRegex(RuntimeError, 'abort'):
            with self.repo.transaction():
                self.repo.cancel_pending('rolled back')
                raise RuntimeError('abort')

        self.assertEqual(self.repo.pending()['id'], task['id'])
        self.assertEqual(artifact.read_text(encoding='utf-8'), 'submitted receipt')
        self.assertEqual(self.repo.db.execute("SELECT count(*) FROM journal WHERE action='cancel'").fetchone()[0], 0)

    def test_after_commit_runs_in_order_after_data_is_visible_to_another_connection(self):
        calls = []

        def read_committed():
            observer = SQLiteRepository(self.project)
            try:
                calls.append(observer.get('committed'))
            finally:
                observer.close()
            self.assertFalse(self.repo.db.in_transaction)

        with self.repo.transaction():
            self.repo.put('committed', 'visible')
            self.repo.after_commit(read_committed)
            self.repo.after_commit(lambda: calls.append('second'))
            self.assertEqual(calls, [])
        self.assertEqual(calls, ['visible', 'second'])

    def test_after_commit_runs_immediately_outside_a_transaction(self):
        calls = []
        self.repo.after_commit(lambda: calls.append('now'))
        self.assertEqual(calls, ['now'])

    def test_preview_discards_callbacks_and_database_changes(self):
        calls = []
        with self.repo.transaction(preview=True):
            self.repo.put('preview', True)
            self.repo.after_commit(lambda: calls.append('preview'))
        self.assertIsNone(self.repo.get('preview'))
        with self.repo.transaction():
            self.repo.put('real', True)
        self.assertEqual(calls, [])

    def test_failure_discards_callbacks_and_database_changes(self):
        calls = []
        with self.assertRaisesRegex(RuntimeError, 'abort'):
            with self.repo.transaction():
                self.repo.put('failed', True)
                self.repo.after_commit(lambda: calls.append('failed'))
                raise RuntimeError('abort')
        self.assertIsNone(self.repo.get('failed'))
        with self.repo.transaction():
            self.repo.put('real', True)
        self.assertEqual(calls, [])

    def test_callback_failure_reports_failure_without_rolling_back_committed_data(self):
        def fail():
            raise RuntimeError('delivery failed')

        with self.assertRaisesRegex(RuntimeError, 'delivery failed'):
            with self.repo.transaction():
                self.repo.put('committed', True)
                self.repo.after_commit(fail)

        observer = SQLiteRepository(self.project)
        try:
            self.assertIs(observer.get('committed'), True)
        finally:
            observer.close()
        calls = []
        self.repo.after_commit(lambda: calls.append('still outside'))
        self.assertEqual(calls, ['still outside'])

    def test_storage_paths_include_all_database_sidecars(self):
        expected = {(self.project / ('novel.sqlite3' + suffix)).resolve()
                    for suffix in ('', '-wal', '-shm', '-journal')}
        self.assertEqual(self.repo.storage_paths, expected)

    def test_storage_paths_resolve_project_and_database_aliases(self):
        self.repo.close()
        database = self.project / 'novel.sqlite3'
        external = Path(self.temp.name) / 'actual.sqlite3'
        database.rename(external)
        link_or_skip(self, database, external)
        alias = Path(self.temp.name) / 'project-alias'
        link_or_skip(self, alias, self.project, target_is_directory=True)
        self.repo = SQLiteRepository(alias)

        expected = {(self.project / ('novel.sqlite3' + suffix)).resolve()
                    for suffix in ('', '-wal', '-shm', '-journal')}
        expected.update(Path(str(external) + suffix).resolve()
                        for suffix in ('', '-wal', '-shm', '-journal'))
        self.assertEqual(self.repo.storage_paths, expected)
        self.assertTrue(all(path.is_absolute() for path in self.repo.storage_paths))


if __name__ == '__main__':
    unittest.main()
