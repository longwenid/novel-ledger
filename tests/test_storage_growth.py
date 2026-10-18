"""Storage retention: superseded snapshots must not accumulate without bound.

Documents are content addressed and rewritten on every commit, so an ever growing
partition leaves one unreachable copy behind per save. This measures that garbage
and the reclamation that removes it, using source records only.

The chapter rows and the contract come from `support`, the shared fixture module: they were
previously imported from two other test modules, so rewriting either one broke this file's
collection before a single assertion ran.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'tests')]
from novel_ledger.sqlite_store import SQLiteRepository
from novel_ledger.workflow import new_book
from support import append_history, tracked_contract


def db_bytes(repo):
    return os.path.getsize(repo.project / 'novel.sqlite3')


class StorageGrowthTests(unittest.TestCase):
    def test_prune_reclaims_superseded_snapshots_and_keeps_live_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = SQLiteRepository.initialize(Path(temporary) / 'book', new_book(tracked_contract(40)))
            try:
                book = repo.load()
                for n in range(1, 31):
                    append_history(repo, n, n, prose_han=200)
                    # Each save rewrites the whole intent partition; only the last is live.
                    book.setdefault('plans', {})['1'] = {'chapter': 1, 'note': 'snapshot-%d' % n}
                    repo.save(book)
                before = db_bytes(repo)
                stored = repo.db.execute('SELECT count(*) FROM documents').fetchone()[0]
                result = repo.prune()
                after = db_bytes(repo)
                self.assertGreater(result['documents_removed'], 20,
                                   'Superseded snapshots must be reclaimable.')
                self.assertLess(after, before)
                self.assertGreater(stored, result['documents_kept'])
                self.assertEqual(repo.db.execute('SELECT count(*) FROM documents').fetchone()[0],
                                 result['documents_kept'])
                # Live state survives the reclamation and stays readable.
                self.assertEqual(repo.load()['plans']['1']['note'], 'snapshot-30')
                row = repo.chapter('main', 30)
                self.assertEqual(row['n'], 30)
                self.assertTrue(repo.read_document(row['prose']).startswith('工程第30章'))
                self.assertEqual(repo.read_document(row['plan']), {})
                # A second pass has nothing left to reclaim.
                self.assertEqual(repo.prune()['documents_removed'], 0)
            finally:
                repo.close()

    def test_prune_keeps_a_document_a_live_pointer_still_names(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = SQLiteRepository.initialize(Path(temporary) / 'book', new_book(tracked_contract(6)))
            try:
                token = repo.document({'frozen': 'material'})
                self.assertEqual(repo.read_document(token)['frozen'], 'material')
                repo.put('probe:reference', {'records': {'story': token}})
                repo.prune()
                self.assertEqual(repo.read_document(token)['frozen'], 'material')
            finally:
                repo.close()


if __name__ == '__main__':
    unittest.main()
