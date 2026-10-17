"""A chapter review reads its judgement basis; background material stays on demand.

Measured on a real project, one 3,375-character chapter was reviewed against 56,031 characters
of required material — 16.6 times the text under review — while `scene_context` and `profiles`
(the largest shares) only supply background the reviewer rarely cites. The declared split is
enforced in both directions: the required set is exactly the judgement basis, and everything
demoted is still delivered by `read --record` because it stays in the envelope's records.
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from novel_ledger import context, workflow
from novel_ledger.bootstrap import local_application as Application
from novel_ledger.sqlite_store import SQLiteRepository
from support import contract, drive


class ReviewMaterialTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / 'book'

    def tearDown(self):
        self.temp.cleanup()

    def review_input(self):
        repo = SQLiteRepository.initialize(self.project, workflow.new_book(contract()))
        app = Application(repo)
        try:
            drive(app, until='write')
            app.submit(__import__('support').response(app))
            handoff = drive(app, until='chapter_review')
            work = app.repo.pending()['input']
            repo.close()
            return work, handoff
        except BaseException:
            repo.close()
            raise

    def test_the_review_reads_its_judgement_basis_and_nothing_else(self):
        work, _ = self.review_input()
        self.assertEqual(work['stage'], 'chapter_review')
        # The judgement basis is declared; conditional records (feedback, revision terms) join
        # when they exist. Everything demoted is out of the required set...
        self.assertLessEqual(set(work['required']), set(context.STAGE_MATERIAL['chapter_review']))
        for name in context.CHAPTER_REVIEW_ON_DEMAND:
            self.assertNotIn(name, work['required'])
        # ...but demoted is not deleted: the record stays in the envelope for read --record.
        self.assertIn('story', work['records'])
        self.assertNotIn('story', work['required'])

    def test_the_required_half_and_the_demoted_half_do_not_overlap(self):
        self.assertEqual(set(context.STAGE_MATERIAL['chapter_review'])
                         & set(context.CHAPTER_REVIEW_ON_DEMAND), set())


if __name__ == '__main__':
    unittest.main()
