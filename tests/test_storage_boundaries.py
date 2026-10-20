"""The storage adapter owns transactions and rows, never delivery artifacts."""
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from novel_ledger.sqlite_store import SQLiteRepository
from novel_ledger.contracts import Error, SCHEMA, dump
from support import link_or_skip


class StorageBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / 'book'
        self.repo = SQLiteRepository.initialize(self.project, {})

    def tearDown(self):
        self.repo.close()
        self.temp.cleanup()

    def test_cancellation_commits_rows_and_rollback_keeps_task_and_worker_files(self):
        task = self.repo.add_task({'stage': 'storage-probe'})
        artifact = self.project / 'work' / task['id'] / 'result.json'
        artifact.parent.mkdir(parents=True)
        artifact.write_text('submitted receipt', encoding='utf-8')

        with self.repo.transaction():
            self.assertEqual(self.repo.cancel_pending('cancel probe'), task['id'])
        self.assertEqual(self.repo.task(task['id'])['status'], 'cancelled')
        self.assertEqual(artifact.read_text(encoding='utf-8'), 'submitted receipt')
        logged = self.repo.db.execute("SELECT value FROM journal WHERE action='cancel'").fetchone()
        self.assertEqual(json.loads(logged['value']), {'reason': 'cancel probe', 'task': task['id']})
        self.assertIsNone(self.repo.cancel_pending('nothing left'))

        task = self.repo.add_task({'stage': 'storage-probe-2'})
        journal_before = self.repo.db.execute("SELECT count(*) FROM journal WHERE action='cancel'").fetchone()[0]
        with self.assertRaisesRegex(RuntimeError, 'abort'):
            with self.repo.transaction():
                self.repo.cancel_pending('rolled back')
                raise RuntimeError('abort')
        self.assertEqual(self.repo.pending()['id'], task['id'])
        self.assertEqual(artifact.read_text(encoding='utf-8'), 'submitted receipt')
        self.assertEqual(self.repo.db.execute("SELECT count(*) FROM journal WHERE action='cancel'").fetchone()[0],
                         journal_before)

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

    def test_discarded_transactions_discard_callbacks_and_database_changes(self):
        """Both a preview and a failure discard the staged rows and the callbacks they registered."""
        calls = []
        with self.repo.transaction(preview=True):
            self.repo.put('preview', True)
            self.repo.after_commit(lambda: calls.append('preview'))
        self.assertIsNone(self.repo.get('preview'))
        with self.repo.transaction():
            self.repo.put('real', True)
        self.assertEqual(calls, [])
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
        # Outside a transaction a callback runs immediately.
        calls = []
        self.repo.after_commit(lambda: calls.append('still outside'))
        self.assertEqual(calls, ['still outside'])

    def test_only_current_storage_is_opened_without_mutating_unsupported_databases(self):
        columns = {row['name'] for row in self.repo.db.execute('PRAGMA table_info(tasks)')}
        self.assertFalse({'first_read', 'first_read_hash'} & columns)
        path = self.project / 'novel.sqlite3'
        for schema in ('novel-ledger/1', 'novel-ledger/2', 'novel-ledger/3', 'novel-ledger/4', 'unknown'):
            with self.subTest(schema=schema):
                self.repo.db.execute("UPDATE kv SET value=? WHERE key='schema'", (dump(schema),))
                before = path.read_bytes()
                with self.assertRaises(Error) as caught:
                    SQLiteRepository(self.project)
                self.assertEqual(caught.exception.code, 'schema')
                self.assertEqual(path.read_bytes(), before)
        self.repo.db.execute("UPDATE kv SET value=? WHERE key='schema'", (dump(SCHEMA),))

    def test_storage_paths_include_all_database_sidecars(self):
        expected = {(self.project / ('novel.sqlite3' + suffix)).resolve()
                    for suffix in ('', '-wal', '-shm', '-journal')}
        self.assertEqual(self.repo.storage_paths, expected)

    def test_readonly_connection_reconstructs_shared_sources_and_cannot_write(self):
        value = {'versions': [{'chapter': n, 'text': '完整冻结来源' * 80} for n in range(100)]}
        key = self.repo.document(value)
        before = (self.project / 'novel.sqlite3').read_bytes()
        reader = SQLiteRepository(self.project, readonly=True)
        try:
            self.assertEqual(reader.read_document(key), value)
            self.assertEqual(reader.load(), self.repo.load())
            with self.assertRaises(sqlite3.OperationalError):
                reader.put('read-only-probe', True)
            self.assertIsNone(self.repo.get('read-only-probe'))
            self.assertEqual((self.project / 'novel.sqlite3').read_bytes(), before)
        finally:
            reader.close()

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
