"""A dispatch reads a bounded material set however long the book gets.

The v1 long-form regression was a closure that walked the whole ancestry recursively: a 1,200-node
chain grew the required material with book length and aborted dispatch with a RecursionError. v2's
material is bounded by construction: a chapter outline carries its own deltas and its enter/exit
chain, and a writer reads one chapter row plus one volume row, so neither the node registry nor the
history prefix can put the whole book into one envelope. These tests pin that bound.
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts')]

from novel_ledger.bootstrap import local_application as Application
from novel_ledger.contracts import dump
from novel_ledger.sqlite_store import SQLiteRepository
from support import contract, drive, response, seeded_book


class DependencyBoundTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / 'book'
        self.repo = None

    def tearDown(self):
        if self.repo is not None:
            self.repo.close()
        self.temp.cleanup()

    def build(self, chapters=40):
        self.repo = SQLiteRepository.initialize(self.project, seeded_book(contract(chapters=chapters)))
        return self.repo, Application(self.repo)

    def test_a_long_volume_still_dispatches_a_bounded_chapter_outline(self):
        repo, app = self.build(chapters=40)
        handoff = app.advance()
        self.assertEqual(handoff['task']['stage'], 'volume_outline')
        work = repo.pending()['input']
        self.assertLess(len(dump(work['payload']).encode('utf-8')), 20000)
        app.submit(response(app))
        handoff = app.advance()
        self.assertEqual(handoff['task']['stage'], 'chapter_outline')
        work = repo.pending()['input']
        # One dispatch answers the whole volume: the material is the volume row and the contract,
        # not the forty rows it is about to write.
        self.assertIn('volume_outline', work['required'])
        self.assertLess(len(dump(work['payload']).encode('utf-8')), 20000)
        self.assertLessEqual(len(work['required']), 12)

    def test_a_writer_reads_one_chapter_row_and_one_volume_row(self):
        repo, app = self.build(chapters=40)
        drive(app, until='write')
        work = repo.pending()['input']
        self.assertIn('chapter_outline', work['required'])
        self.assertIn('volume_outline', work['required'])
        chapter = repo.read_document(work['records']['chapter_outline'])
        volume = repo.read_document(work['records']['volume_outline'])
        self.assertEqual(chapter['chapter'], 1)
        self.assertEqual(volume['id'], 'v1')
        # The chapter row's material is its own deltas; the remaining chapters never travel with it.
        self.assertNotIn('chapters', volume)
        self.assertLessEqual(len(work['required']), 20)

    def test_the_book_can_still_be_completed_after_a_long_volume_is_outlined(self):
        repo, app = self.build(chapters=6)
        owner = app.run(finish=True, source='工程夹具授权写完六章。')['owner']
        handoff = drive(app, owner)
        self.assertEqual(handoff['action'], 'ready_to_complete')
        self.assertEqual(len(repo.headers('main')), 6)


if __name__ == '__main__':
    unittest.main()
