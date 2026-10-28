"""Author instructions must survive a fresh controller and remain scoped to active choices."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'tests'))

from novel_ledger import workflow
from novel_ledger.bootstrap import local_application as Application
from novel_ledger.sqlite_store import SQLiteRepository
from test_opening_inline import gate_result


class OpeningSourceTests(unittest.TestCase):
    def test_original_request_and_active_choice_survive_reopen_and_back(self):
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder) / 'book'
            request = '番茄都市异能，主角不要系统，节奏明快。'
            repo = SQLiteRepository.initialize(project, workflow.preparing_book(request, guided=True))
            app = Application(repo)
            app.advance()
            first = repo.pending()['input']
            self.assertIn('opening_basis', first['required'])
            self.assertEqual(repo.read_document(first['records']['opening_basis'])['source'], request)
            result = gate_result(app, 'controller-test')
            app.submit(result)
            board = repo.load()['creation']['board']
            app.opening_choice(result['data']['options'][0]['id'], board['hash'], '选第一项，主角不杀无辜。')
            repo.close()

            repo = SQLiteRepository(project)
            try:
                app = Application(repo)
                app.advance()
                second = repo.pending()['input']
                self.assertIn('opening_basis', second['required'])
                basis = repo.read_document(second['records']['opening_basis'])
                self.assertEqual(basis['source'], request)
                self.assertEqual(basis['selection_sources'], [
                    {'gate': 'genre', 'source': '选第一项，主角不杀无辜。'}])
                app.opening_back('genre', '重新选择题材。')
                app.advance()
                replacement = repo.pending()['input']
                basis = repo.read_document(replacement['records']['opening_basis'])
                self.assertEqual(basis['source'], request)
                self.assertEqual(basis['selection_sources'], [])
            finally:
                repo.close()


if __name__ == '__main__':
    unittest.main()
