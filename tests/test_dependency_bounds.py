"""A dispatch reads a bounded causal neighbourhood however deep the chain is.

The previous closure walked the whole ancestry recursively: a long chain grew the
required material with book length, and a thousand-node chain aborted dispatch with
RecursionError. These are the end-to-end regressions for that bound.
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
from novel_ledger.workflow import new_book
from support import contract, drive, node


def chain(size):
    return [{**node('chain-' + str(i), () if i == 0 else ['chain-' + str(i - 1)]),
             'required': False, 'window': [1, 2]} for i in range(size)]


class DependencyBoundTests(unittest.TestCase):
    def build(self, size, tracking):
        temporary = tempfile.TemporaryDirectory()
        repo = SQLiteRepository.initialize(Path(temporary.name) / 'book', new_book(contract()))
        app = Application(repo)
        drive(app, until='write')
        repo.cancel_pending('工程依赖边界夹具。')
        book = repo.load()
        book['contract']['narrative_tracking'] = tracking
        nodes = chain(size)
        book['designs']['book']['nodes'] = nodes
        tail = 'chain-' + str(size - 1)
        plan = book['plans']['1']
        plan.update(node_ids=[tail], node_actions=[{'node': tail, 'after': 'seeded'}],
                    node_contracts={tail: nodes[-1]}, disclosures=[], preconditions=[])
        repo.save(book)
        return temporary, repo, app

    def test_basic_project_with_a_long_chain_still_dispatches(self):
        temporary, repo, app = self.build(1200, tracking=False)
        try:
            work = repo.task(app.advance()['task']['task_id'])['input']
            values = {n: repo.read_document(work['records'][n]) for n in work['required']}
            self.assertLessEqual(len(values['story']), 25)
            self.assertLess(len(dump(values).encode('utf-8')), 20000)
        finally:
            repo.close()
            temporary.cleanup()

    def test_tracked_project_still_reads_target_and_direct_prerequisites(self):
        temporary, repo, app = self.build(1200, tracking=True)
        try:
            work = repo.task(app.advance()['task']['task_id'])['input']
            self.assertEqual(len(repo.read_document(work['records']['story'])), 2)
        finally:
            repo.close()
            temporary.cleanup()


if __name__ == '__main__':
    unittest.main()
