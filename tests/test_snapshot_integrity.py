"""Immutable JSON snapshots share storage without changing their logical values.

These are isolated storage fixtures, not model calls or literary acceptance. Most
checks use the repository surface. The corruption checks deliberately inspect the
private SQLite representation so a damaged leaf or intermediate block cannot be
mistaken for a valid frozen source.
"""
import copy
import json
import re
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'tests')]
from novel_ledger.contracts import Error, digest, dump
from novel_ledger import store_keys
from novel_ledger.sqlite_store import SQLiteRepository
from novel_ledger.workflow import new_book
from support import append_history, tracked_contract


class SnapshotIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='novel-snapshot-test-')
        self.project = Path(self.temporary.name) / 'book'
        self.repo = SQLiteRepository.initialize(self.project, new_book(tracked_contract(8)))

    def tearDown(self):
        self.repo.close()
        self.temporary.cleanup()

    def reopen(self):
        self.repo.close()
        self.repo = SQLiteRepository(self.project)

    def physical_rows(self):
        return {table: tuple(tuple(row) for row in self.repo.db.execute(
            'SELECT hash,value FROM ' + table + ' ORDER BY hash'))
                for table in ('documents', 'document_blocks')}

    def physical_bytes(self):
        return sum(len(value.encode('utf-8')) for rows in self.physical_rows().values()
                   for _, value in rows)

    def database_rows(self):
        """Compare every persisted row, including the exact stored text bytes."""
        return tuple(self.repo.db.iterdump())

    def block_tree(self, document):
        """Find actual private edges, without depending on block kind field names."""
        raw = self.repo.db.execute('SELECT value FROM documents WHERE hash=?',
                                   (document,)).fetchone()[0]
        self.assertTrue(raw.startswith('NL5\n'), 'the fixture must exercise shared blocks')
        root = json.loads(raw[4:])
        rows = dict(self.physical_rows()['document_blocks'])
        self.assertIn(root, rows)
        graph = {key: set(re.findall(r'[0-9a-f]{64}', value)) & rows.keys()
                 for key, value in rows.items()}
        reachable, pending = set(), [root]
        while pending:
            key = pending.pop()
            if key not in reachable:
                reachable.add(key)
                pending.extend(graph[key])
        return root, {key: graph[key] for key in reachable}, rows

    def assert_source_damaged(self, key):
        with self.assertRaises(Error) as caught:
            self.repo.read_document(key)
        self.assertEqual(caught.exception.code, 'source_integrity')

    def assert_prune_rejects_without_mutation(self):
        before = self.database_rows()
        with self.assertRaises(Error) as caught:
            self.repo.prune()
        self.assertEqual(caught.exception.code, 'source_integrity')
        self.assertEqual(self.database_rows(), before,
                         'damage validation must finish before any garbage is deleted')

    @staticmethod
    def cumulative_value(number):
        rows = [{'chapter': n, 'choice': '核实来源，承担后果。' + str(n) + '测' * 150}
                for n in range(number)]
        return {'state': {'characters': {'shen': {'development': rows}}},
                'understanding': {'versions': {str(n): row for n, row in enumerate(rows)}}}

    def test_json_values_and_storage_lookalikes_round_trip_without_collision(self):
        structured = self.cumulative_value(50)
        key = self.repo.document(structured)
        root, _, rows = self.block_tree(key)
        root_encoding = self.repo.db.execute('SELECT value FROM documents WHERE hash=?',
                                            (key,)).fetchone()[0]
        values = [None, True, False, 0, -17, 2 ** 80, 0.25, -0.0, '', '汉字\n🙂', [], {},
                  'NL5\n', 'NL5\n' + json.dumps(root), root_encoding,
                  json.loads(rows[root]), ['ref', root], ['inline', {'reference': root}],
                  ['list-index', [root]], ['value', {'reference': root}],
                  {'$ref': root}, {'hash': root, 'value': root_encoding},
                  {'NL5': root, 'nested': [json.loads(rows[root]), {'$ref': root}]},
                  {'': None, '0': False, '汉字': [1, '1', {}, [], {'quote': '"\\'}]}]
        keys = []
        with self.repo.transaction():
            for value in values:
                token = self.repo.document(value)
                keys.append(token)
                self.assertEqual(token, digest(value))
                self.assertEqual(dump(self.repo.read_document(token)), dump(value))
            self.repo.put('probe:json-values', keys)
        self.repo.prune()
        self.reopen()
        for token, value in zip(keys, values):
            with self.subTest(value=value):
                self.assertEqual(dump(self.repo.read_document(token)), dump(value))

    def test_old_versions_and_returned_mutable_values_are_independent(self):
        value = self.cumulative_value(65)
        original = copy.deepcopy(value)
        first = self.repo.document(value)
        value['state']['characters']['shen']['development'][0]['choice'] = '发生变化'
        value['state']['characters']['shen']['development'].append({'chapter': 66})
        del value['understanding']['versions']['0']
        second = self.repo.document(value)
        self.assertNotEqual(first, second)
        self.assertEqual(self.repo.read_document(first), original)
        self.assertEqual(self.repo.read_document(second), value)
        before = self.physical_rows()
        self.assertEqual(self.repo.document(copy.deepcopy(original)), first)
        self.assertEqual(self.physical_rows(), before, 'writing the same JSON must reuse every block')

        shared = {'rows': [{'id': n, 'text': '不可变来源' * 30} for n in range(80)]}
        repeated = self.repo.document({'a': shared, 'b': shared})
        restored = self.repo.read_document(repeated)
        restored['a']['rows'][0]['text'] = '调用方修改'
        restored['a']['rows'].append({'id': 81})
        self.assertEqual(restored['b'], shared, 'equal JSON subtrees must not acquire mutable aliases')
        self.assertEqual(self.repo.read_document(repeated), {'a': shared, 'b': shared})
        self.assertEqual(self.repo.read_document(first), original)

    def test_nested_cumulative_lists_and_dicts_share_retained_snapshots(self):
        before = self.physical_bytes()
        expected, naive_bytes = [], 0
        with self.repo.transaction():
            for number in range(1, 97):
                value = self.cumulative_value(number)
                expected.append((self.repo.document(value), copy.deepcopy(value)))
                naive_bytes += len(dump(value).encode('utf-8'))
            self.repo.put('probe:retained-snapshots', [key for key, _ in expected])
        actual_bytes = self.physical_bytes() - before
        self.assertLess(actual_bytes, naive_bytes * 0.55,
                        'nested appends must share old data even while every frozen version remains live')
        self.repo.prune()
        self.reopen()
        for key, value in expected:
            self.assertEqual(self.repo.read_document(key), value)

    def test_prune_and_reopen_preserve_branch_history_and_frozen_task_sources(self):
        with self.repo.transaction():
            append_history(self.repo, 1, 3, prose_han=1800)
            branch = self.repo.fork('main', 3)
            frozen = self.cumulative_value(65)
            frozen_key = self.repo.document(frozen)
            task = self.repo.add_task({'stage': 'storage-probe', 'records': {'complete_state': frozen_key}})
            self.repo.finish_task(task['id'], {'accepted': True})
            latest = self.cumulative_value(80)
            latest_key = self.repo.document(latest)
            self.repo.put('probe:latest', latest_key)
            orphan = self.repo.document({'orphan': ['弃用' * 100, '不应保留' * 100] * 80})
        main_history = self.repo.history_snapshot('main')
        branch_history = self.repo.history_snapshot(branch)
        result = self.repo.prune()
        self.assertGreater(result['documents_removed'], 0)
        self.reopen()
        self.assertEqual(self.repo.read_document(frozen_key), frozen)
        self.assertEqual(self.repo.read_document(latest_key), latest)
        self.assertEqual(self.repo.task(task['id'])['input']['records']['complete_state'], frozen_key)
        self.assertEqual([page['n'] for _, page in self.repo.history_pages(main_history)], [3, 2, 1])
        self.assertEqual([page['n'] for _, page in self.repo.history_pages(branch_history)], [2, 1])
        self.assertEqual(self.repo.chapter(branch, 2)['prose'], self.repo.chapter('main', 2)['prose'])
        self.assertTrue(self.repo.read_document(self.repo.chapter(branch, 2)['prose']).startswith('工程第2章'))
        with self.assertRaises(Error) as caught:
            self.repo.read_document(orphan)
        self.assertEqual(caught.exception.code, 'source')
        self.assertEqual(self.repo.prune()['documents_removed'], 0)

    def test_prune_follows_logical_document_hashes_inside_shared_blocks(self):
        with self.repo.transaction():
            frozen = self.cumulative_value(65)
            frozen_key = self.repo.document(frozen)
            keyed = {'meaning': 'a logical document hash can also be an object key'}
            keyed_key = self.repo.document(keyed)
            wrapper = {'nested': {'records': [
                {'source': frozen_key, 'padding': '共享材料' * 120} for _ in range(40)]},
                keyed_key: {'long_scalar': '长标量' * 400 + frozen_key}}
            wrapper_key = self.repo.document(wrapper)
            task = self.repo.add_task({'stage': 'storage-probe', 'records': {'wrapper': wrapper_key}})
            self.repo.finish_task(task['id'], {})
        self.repo.prune()
        self.reopen()
        self.assertEqual(self.repo.read_document(wrapper_key), wrapper)
        self.assertEqual(self.repo.read_document(frozen_key), frozen)
        self.assertEqual(self.repo.read_document(keyed_key), keyed)

    def corruption_fixture(self):
        value = [{'chapter': n, 'evidence': '工程引文' + str(n) + '测' * 60} for n in range(2304)]
        key = self.repo.document(value)
        root, graph, rows = self.block_tree(key)
        intermediate = next((token for token, children in graph.items()
                             if token != root and children), None)
        leaf = next((token for token, children in graph.items() if not children), None)
        self.assertIsNotNone(intermediate, 'the fixture must contain a real intermediate manifest')
        self.assertIsNotNone(leaf)
        return key, value, {'root': root, 'intermediate': intermediate, 'leaf': leaf}, rows

    def test_changed_leaf_intermediate_and_root_blocks_fail_integrity_checks(self):
        key, value, targets, rows = self.corruption_fixture()
        for role, token in targets.items():
            with self.subTest(block=role):
                self.repo.db.execute('UPDATE document_blocks SET value=? WHERE hash=?',
                                     (dump({'damaged': role}), token))
                self.assert_source_damaged(key)
                self.repo.db.execute('UPDATE document_blocks SET value=? WHERE hash=?', (rows[token], token))
                self.assertEqual(self.repo.read_document(key), value)

    def test_missing_leaf_intermediate_and_root_blocks_fail_closed_after_reopen(self):
        key, value, targets, rows = self.corruption_fixture()
        for role, token in targets.items():
            with self.subTest(block=role):
                self.repo.db.execute('DELETE FROM document_blocks WHERE hash=?', (token,))
                self.reopen()
                self.assert_source_damaged(key)
                self.repo.db.execute('INSERT INTO document_blocks VALUES (?,?)', (token, rows[token]))
                self.assertEqual(self.repo.read_document(key), value)

    def test_invalid_root_encoding_cannot_be_read_as_a_logical_json_value(self):
        key = self.repo.document(self.cumulative_value(50))
        original = self.repo.db.execute('SELECT value FROM documents WHERE hash=?', (key,)).fetchone()[0]
        for replacement in ('NL5\nnot json', 'NL5\nnull', 'NL5\n{}', 'NL5\n' + dump('f' * 64),
                            dump({'modified': True}), 'NaN', '[Infinity]', '[-Infinity]',
                            sqlite3.Binary(b'not a text source')):
            with self.subTest(replacement=replacement):
                self.repo.db.execute('UPDATE documents SET value=? WHERE hash=?', (replacement, key))
                self.assert_source_damaged(key)
        self.repo.db.execute('UPDATE documents SET value=? WHERE hash=?', (original, key))
        self.assertEqual(self.repo.read_document(key), self.cumulative_value(50))

    def test_a_valid_tree_substituted_under_another_logical_hash_is_rejected(self):
        first = self.repo.document(self.cumulative_value(50))
        second = self.repo.document(self.cumulative_value(51))
        replacement = self.repo.db.execute('SELECT value FROM documents WHERE hash=?',
                                           (second,)).fetchone()[0]
        self.repo.db.execute('UPDATE documents SET value=? WHERE hash=?', (replacement, first))
        self.reopen()
        self.assert_source_damaged(first)
        self.assertEqual(self.repo.read_document(second), self.cumulative_value(51))

    def test_prune_rejects_a_substituted_valid_tree_before_deleting_any_rows(self):
        first = self.repo.document(self.cumulative_value(50))
        second = self.repo.document(self.cumulative_value(51))
        self.repo.document({'orphan': '待回收材料' * 800})
        self.repo.put('probe:damaged-root', first)
        replacement = self.repo.db.execute('SELECT value FROM documents WHERE hash=?',
                                           (second,)).fetchone()[0]
        # Every block and edge in this tree is self-consistent. Its logical JSON
        # is still not the immutable source named by `first`.
        self.repo.db.execute('UPDATE documents SET value=? WHERE hash=?', (replacement, first))
        self.assert_prune_rejects_without_mutation()

    def test_prune_rejects_a_substituted_raw_json_source_before_deleting_any_rows(self):
        first = self.repo.document({'frozen': 'original'})
        self.repo.document({'orphan': '待回收材料' * 800})
        self.repo.put('probe:damaged-raw-source', first)
        self.repo.db.execute('UPDATE documents SET value=? WHERE hash=?',
                             (dump({'frozen': 'different but valid JSON'}), first))
        self.assert_prune_rejects_without_mutation()

    def test_prune_preserves_every_row_when_shared_leaf_or_manifest_is_damaged_or_missing(self):
        value = self.cumulative_value(96)
        first = self.repo.document(value)
        second_value = self.cumulative_value(97)
        second = self.repo.document(second_value)
        _, first_graph, rows = self.block_tree(first)
        _, second_graph, _ = self.block_tree(second)
        shared = set(first_graph) & set(second_graph)
        leaf = next((key for key in shared if not first_graph[key]), None)
        intermediate = next((key for key in first_graph if first_graph[key]), None)
        self.assertIsNotNone(leaf, 'the fixture must exercise a leaf shared by two live sources')
        self.assertIsNotNone(intermediate)
        self.repo.put('probe:shared-live-roots', [first, second])
        self.repo.document({'orphan': '待回收材料' * 800})
        for role, token in (('shared leaf', leaf), ('manifest', intermediate)):
            for mutation in ('corrupt', 'delete'):
                with self.subTest(block=role, mutation=mutation):
                    if mutation == 'corrupt':
                        self.repo.db.execute('UPDATE document_blocks SET value=? WHERE hash=?',
                                             (dump({'damage': role}), token))
                    else:
                        self.repo.db.execute('DELETE FROM document_blocks WHERE hash=?', (token,))
                    self.assert_prune_rejects_without_mutation()
                    self.repo.db.execute('INSERT OR REPLACE INTO document_blocks VALUES (?,?)',
                                         (token, rows[token]))
        self.assertEqual(self.repo.read_document(first), value)
        self.assertEqual(self.repo.read_document(second), second_value)

    def test_prune_holds_a_writer_lock_from_marking_until_collection_finishes(self):
        retained = self.repo.document(self.cumulative_value(50))
        self.repo.put('probe:retained', retained)
        self.repo.document(self.cumulative_value(70))
        observer = SQLiteRepository(self.project)
        observer.db.execute('PRAGMA busy_timeout=0')
        original_read = self.repo.read_document
        checks = []

        def read_with_another_writer(key):
            if not checks:
                with self.assertRaisesRegex(sqlite3.OperationalError, 'locked'):
                    observer.db.execute('BEGIN IMMEDIATE')
                self.assertFalse(observer.db.in_transaction)
                checks.append(key)
            return original_read(key)

        self.repo.read_document = read_with_another_writer
        try:
            self.repo.prune()
            self.assertTrue(checks, 'the lock check must happen during reachable-source verification')
            observer.db.execute('BEGIN IMMEDIATE')
            observer.put('probe:after-collection', 'writer can proceed')
            observer.db.commit()
            self.assertEqual(self.repo.get('probe:after-collection'), 'writer can proceed')
            self.assertEqual(original_read(retained), self.cumulative_value(50))
        finally:
            self.repo.read_document = original_read
            observer.close()

    def test_a_failure_while_deleting_blocks_rolls_back_deleted_document_roots(self):
        retained = self.repo.document(self.cumulative_value(50))
        self.repo.put('probe:retained', retained)
        orphan = self.repo.document(self.cumulative_value(90))
        deletions = []

        def abort_after_one_block_was_deleted():
            deletions.append(True)
            return len(deletions) > 1

        self.repo.db.create_function('snapshot_probe_abort', 0, abort_after_one_block_was_deleted)
        self.repo.db.execute('''CREATE TRIGGER abort_block_collection BEFORE DELETE ON document_blocks
            WHEN snapshot_probe_abort()=1
            BEGIN SELECT RAISE(ABORT, 'storage-probe collection abort'); END''')
        before = self.database_rows()
        with self.assertRaisesRegex(sqlite3.DatabaseError, 'storage-probe collection abort'):
            self.repo.prune()
        self.assertEqual(len(deletions), 2, 'the first block deletion must precede the injected failure')
        self.assertFalse(self.repo.db.in_transaction)
        self.assertEqual(self.database_rows(), before,
                         'root deletion and block deletion must roll back together')
        self.reopen()
        self.assertEqual(self.repo.read_document(orphan), self.cumulative_value(90))
        self.assertEqual(self.repo.read_document(retained), self.cumulative_value(50))

    def test_prune_refuses_a_callers_transaction_without_committing_or_rolling_it_back(self):
        before = self.database_rows()
        observer = SQLiteRepository(self.project)
        try:
            with self.repo.transaction(preview=True):
                self.repo.put('probe:caller-uncommitted', 'staged')
                staged = self.database_rows()
                with self.assertRaises(Error) as caught:
                    self.repo.prune()
                self.assertEqual(caught.exception.code, 'transaction')
                self.assertTrue(self.repo.db.in_transaction)
                self.assertEqual(self.database_rows(), staged)
                self.assertEqual(self.repo.get('probe:caller-uncommitted'), 'staged')
                self.assertIsNone(observer.get('probe:caller-uncommitted'))
            self.assertEqual(self.database_rows(), before)
            self.assertIsNone(self.repo.get('probe:caller-uncommitted'))
        finally:
            observer.close()

    def test_a_standalone_document_failure_rolls_back_blocks_created_before_root_publication(self):
        value = self.cumulative_value(90)
        self.repo.db.execute('''CREATE TRIGGER abort_document_publish BEFORE INSERT ON documents
            BEGIN SELECT RAISE(ABORT, 'storage-probe publication abort'); END''')
        before = self.database_rows()
        with self.assertRaisesRegex(sqlite3.DatabaseError, 'storage-probe publication abort'):
            self.repo.document(value)
        self.assertFalse(self.repo.db.in_transaction)
        self.assertEqual(self.database_rows(), before,
                         'a failed document root must not leave any newly written blocks')
        self.repo.db.execute('DROP TRIGGER abort_document_publish')
        accepted = self.repo.document(value)
        self.reopen()
        self.assertEqual(self.repo.read_document(accepted), value)

    def test_a_standalone_document_holds_one_transaction_until_its_root_is_published(self):
        value = self.cumulative_value(90)
        key = digest(value)
        observer = SQLiteRepository(self.project)
        observer.db.execute('PRAGMA busy_timeout=0')
        original_store = SQLiteRepository._store_block
        before_blocks = observer.db.execute('SELECT count(*) FROM document_blocks').fetchone()[0]
        checks = []

        def store_with_another_writer(db, block):
            result = original_store(db, block)
            if not checks:
                with self.assertRaisesRegex(sqlite3.OperationalError, 'locked'):
                    observer.db.execute('BEGIN IMMEDIATE')
                self.assertIsNone(observer.db.execute('SELECT hash FROM documents WHERE hash=?',
                                                      (key,)).fetchone())
                self.assertEqual(observer.db.execute('SELECT count(*) FROM document_blocks').fetchone()[0],
                                 before_blocks, 'unpublished blocks must remain uncommitted')
                checks.append(result)
            return result

        try:
            with patch.object(SQLiteRepository, '_store_block', side_effect=store_with_another_writer):
                self.assertEqual(self.repo.document(value), key)
            self.assertTrue(checks)
            self.assertEqual(observer.read_document(key), value)
            observer.put('probe:after-document', 'writer can proceed')
            self.assertEqual(self.repo.get('probe:after-document'), 'writer can proceed')
        finally:
            observer.close()

    def test_standalone_save_keeps_partition_writes_and_root_publication_atomic(self):
        original_book = self.repo.load()
        modified_book = copy.deepcopy(original_book)
        modified_book['plans'] = {'1': self.cumulative_value(90)}
        observer = SQLiteRepository(self.project)
        observer.db.execute('PRAGMA busy_timeout=0')
        root_key = store_keys.BOOK_ROOT.replace("'", "''")
        self.repo.db.execute("CREATE TRIGGER abort_book_publication BEFORE INSERT ON kv WHEN NEW.key='"
                             + root_key + "' BEGIN SELECT RAISE(ABORT, 'storage-probe save abort'); END")
        before = self.database_rows()
        original_put, checks = self.repo.put, []

        def put_with_another_writer(key, value):
            if key == store_keys.BOOK_ROOT:
                with self.assertRaisesRegex(sqlite3.OperationalError, 'locked'):
                    observer.db.execute('BEGIN IMMEDIATE')
                self.assertEqual(observer.load(), original_book)
                checks.append(key)
            return original_put(key, value)

        try:
            with patch.object(self.repo, 'put', side_effect=put_with_another_writer):
                with self.assertRaisesRegex(sqlite3.DatabaseError, 'storage-probe save abort'):
                    self.repo.save(modified_book)
            self.assertTrue(checks, 'lock inspection must happen after partitions and before the book root')
            self.assertEqual(self.database_rows(), before)
            self.repo.db.execute('DROP TRIGGER abort_book_publication')
            before_preview = self.database_rows()
            with self.repo.transaction(preview=True):
                self.repo.save(modified_book)
                self.assertEqual(self.repo.load(), modified_book)
                self.assertEqual(observer.load(), original_book)
            self.assertEqual(self.database_rows(), before_preview)
            self.repo.save(modified_book)
            self.assertEqual(observer.load(), modified_book)
            observer.put('probe:after-save', True)
        finally:
            observer.close()

    def test_standalone_history_snapshot_keeps_page_writes_and_head_publication_atomic(self):
        append_history(self.repo, 1, 4, prose_han=100)
        observer = SQLiteRepository(self.project)
        observer.db.execute('PRAGMA busy_timeout=0')
        cache_key = store_keys.history_head('main')
        sql_key = cache_key.replace("'", "''")
        self.repo.db.execute("CREATE TRIGGER abort_history_publication BEFORE INSERT ON kv WHEN NEW.key='"
                             + sql_key + "' BEGIN SELECT RAISE(ABORT, 'storage-probe history abort'); END")
        before = self.database_rows()
        original_put, checks = self.repo.put, []

        def put_with_another_writer(key, value):
            if key == cache_key:
                with self.assertRaisesRegex(sqlite3.OperationalError, 'locked'):
                    observer.db.execute('BEGIN IMMEDIATE')
                self.assertIsNone(observer.get(cache_key))
                checks.append(key)
            return original_put(key, value)

        try:
            with patch.object(self.repo, 'put', side_effect=put_with_another_writer):
                with self.assertRaisesRegex(sqlite3.DatabaseError, 'storage-probe history abort'):
                    self.repo.history_snapshot('main')
            self.assertTrue(checks, 'lock inspection must happen after pages and before the history head')
            self.assertEqual(self.database_rows(), before)
            self.repo.db.execute('DROP TRIGGER abort_history_publication')
            accepted = self.repo.history_snapshot('main')
            self.assertEqual([page['n'] for _, page in observer.history_pages(accepted)], [4, 3, 2, 1])
            before_preview = self.database_rows()
            with self.repo.transaction(preview=True):
                append_history(self.repo, 5, 5, prose_han=100)
                preview = self.repo.history_snapshot('main')
                self.assertEqual(preview['through'], 5)
                self.assertEqual(observer.get(cache_key), accepted)
            self.assertEqual(self.database_rows(), before_preview)
            observer.put('probe:after-history-snapshot', True)
        finally:
            observer.close()

    def test_preview_failure_and_invalid_json_leave_no_blocks_or_document_roots(self):
        stable = self.repo.document(self.cumulative_value(50))
        before = self.physical_rows()
        for preview in (True, False):
            candidate = self.cumulative_value(80 if preview else 90)
            candidate_key = digest(candidate)
            try:
                with self.repo.transaction(preview=preview):
                    self.repo.document(candidate)
                    self.repo.put('probe:discarded', candidate_key)
                    self.assertGreater(self.physical_bytes(), sum(len(v.encode('utf-8'))
                                       for rows in before.values() for _, v in rows))
                    if not preview:
                        raise RuntimeError('storage-probe abort')
            except RuntimeError as failure:
                self.assertEqual(str(failure), 'storage-probe abort')
            self.assertEqual(self.physical_rows(), before)
            self.assertIsNone(self.repo.get('probe:discarded'))
            with self.assertRaises(Error) as caught:
                self.repo.read_document(candidate_key)
            self.assertEqual(caught.exception.code, 'source')
        with self.assertRaises(ValueError):
            self.repo.document({'large': self.cumulative_value(80), 'invalid': float('nan')})
        self.assertEqual(self.physical_rows(), before)
        with self.repo.transaction():
            accepted = self.repo.document(self.cumulative_value(90))
            self.repo.put('probe:accepted', accepted)
        self.reopen()
        self.assertEqual(self.repo.read_document(accepted), self.cumulative_value(90))
        self.assertEqual(self.repo.read_document(stable), self.cumulative_value(50))

    def test_many_list_appends_form_a_shallow_tree_and_reopen_without_history_recursion(self):
        rows, versions = [], []
        with self.repo.transaction():
            for number in range(1600):
                rows.append({'chapter': number, 'choice': '承担选择的后果。'})
                versions.append(self.repo.document({'nested': {'history': rows}}))
            self.repo.put('probe:many-appends', versions)
        root, graph, _ = self.block_tree(versions[-1])
        pending, depth = [(root, 1, frozenset())], 0
        while pending:
            token, level, ancestors = pending.pop()
            self.assertNotIn(token, ancestors, 'a block graph must not contain a cycle')
            depth = max(depth, level)
            pending.extend((child, level + 1, ancestors | {token}) for child in graph[token])
        self.assertLessEqual(depth, 16, 'snapshot appends must not build a linear dependency chain')
        self.repo.prune()
        self.reopen()
        self.assertEqual(self.repo.read_document(versions[-1]), {'nested': {'history': rows}})
        self.assertEqual(self.repo.read_document(versions[0]), {'nested': {'history': rows[:1]}})
        self.assertEqual(self.repo.read_document(versions[799]), {'nested': {'history': rows[:800]}})


if __name__ == '__main__':
    unittest.main()
