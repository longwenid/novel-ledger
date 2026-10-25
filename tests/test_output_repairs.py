"""Behavior regressions for protected outputs, frozen publication and blind evaluations."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'tests'))

import quality_eval
from novel_ledger import bookpage, delivery, store_keys, workflow
from novel_ledger.bootstrap import local_application as Application, local_workspace
from novel_ledger.contracts import Error, digest, dump
from novel_ledger.sqlite_store import SQLiteRepository
from support import contract, drive, link_or_skip, opening_gate_values, response


class OutputRepairTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name).resolve()
        self.project = self.base / 'book'
        self.repo = SQLiteRepository.initialize(self.project, workflow.new_book(contract(4)))
        self.app = Application(self.repo)

    def tearDown(self):
        self.repo.close()
        self.temp.cleanup()

    def rejected_output(self, target):
        for writer in (bookpage.write, delivery.export_book):
            with self.subTest(writer=writer.__name__, target=target), self.assertRaises(Error) as caught:
                writer(self.repo, target, workspace=local_workspace(self.repo))
            self.assertEqual(caught.exception.code, 'output')

    def test_html_and_export_preserve_database_and_transaction_paths(self):
        original = (self.project / 'novel.sqlite3').read_bytes()
        for suffix in ('', '-wal', '-shm', '-journal'):
            self.rejected_output(self.project / ('novel.sqlite3' + suffix))
        self.assertEqual((self.project / 'novel.sqlite3').read_bytes(), original)
        self.assertEqual(self.repo.load()['contract']['title'], '夜班退件')
        self.assertFalse((self.project / 'novel.sqlite3-wal').exists())
        self.assertTrue(Path(bookpage.write(self.repo, workspace=local_workspace(self.repo))['path']).is_file())
        target = self.base / 'prose.html'
        delivery.export_book(self.repo, target, workspace=local_workspace(self.repo))
        self.assertIn('夜班退件', target.read_text(encoding='utf-8'))

    def test_output_symlinks_cannot_bypass_database_or_reserved_view_protection(self):
        original = (self.project / 'novel.sqlite3').read_bytes()
        for index, suffix in enumerate(('', '-wal', '-shm', '-journal')):
            alias = self.base / ('alias-' + str(index) + '.html')
            link_or_skip(self, alias, self.project / ('novel.sqlite3' + suffix))
            self.rejected_output(alias)
            self.assertTrue(alias.is_symlink())
        bookpage.write(self.repo, workspace=local_workspace(self.repo))
        view = (self.project / 'book.html').read_bytes()
        alias = self.base / 'view-alias.html'
        alias.symlink_to(self.project / 'book.html')
        with self.assertRaises(Error) as caught:
            delivery.export_book(self.repo, alias, workspace=local_workspace(self.repo))
        self.assertEqual(caught.exception.code, 'output')
        self.assertEqual((self.project / 'book.html').read_bytes(), view)
        self.assertEqual((self.project / 'novel.sqlite3').read_bytes(), original)


class EvaluationRepairTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name).resolve()
        (self.base / 'one.txt').write_text('他开门，决定承担责任。', encoding='utf-8')
        (self.base / 'two.txt').write_text('他交出三文钱。', encoding='utf-8')

    def tearDown(self):
        self.temp.cleanup()

    def prepare(self, cases):
        manifest = {'chapters': [{'chapter': 1, 'path': 'one.txt'}, {'chapter': 2, 'path': 'two.txt'}],
                    'cases': cases}
        path = self.base / 'manifest.json'
        path.write_text(dump(manifest), encoding='utf-8')
        return quality_eval.prepare(path, self.base / 'evaluation')

    def reviewed_case(self):
        result = self.prepare([{'chapters': [1], 'targets': [1]}])
        case = result['cases'][0]
        work = json.loads(Path(case['input']).read_text(encoding='utf-8'))
        first = {'case_id': work['case_id'], 'input_hash': digest(work), 'data': {'reads': [{
            'chapter': 1, 'desire': '开门。', 'obstacle': '责任压力。', 'change': '选择行动。',
            'read_on_reason': '后果如何。'}]}}
        receipt = self.base / 'first.json'
        receipt.write_text(dump(first), encoding='utf-8')
        quality_eval.seal(case['input'], receipt)
        review = {'case_id': work['case_id'], 'input_hash': digest(work), 'first_read': first['data'],
                  'checks': [{'id': criterion, 'result': 'pass', 'reason': '工程评测判断。',
                              'evidence': [{'chapter': 1, 'start': 0, 'quote': work['chapters'][0]['prose']}]}
                             for criterion in quality_eval.CRITERIA], 'findings': []}
        Path(case['output']).write_text(dump(review), encoding='utf-8')
        return self.base / 'evaluation', work

    def test_invalid_later_case_rejects_batch_before_writing_any_artifacts(self):
        cases = [{'chapters': [1]}, {'chapters': [1], 'edits': [
            {'chapter': 2, 'start': 3, 'old': '三', 'new': '九', 'criterion': 'cost'}]}]
        with self.assertRaises(Error) as caught:
            self.prepare(cases)
        self.assertEqual(caught.exception.code, 'coverage')
        self.assertFalse((self.base / 'evaluation').exists())

    def test_malformed_manifests_fail_without_creating_an_evaluation_batch(self):
        source = [{'chapter': 1, 'path': 'one.txt'}]
        values = [[], {}, {'chapters': None, 'cases': [{}]}, {'chapters': [], 'cases': [{}]},
                  {'chapters': source, 'cases': []}, {'chapters': [None], 'cases': [{}]},
                  {'chapters': [{'chapter': 1, 'path': None}], 'cases': [{}]},
                  {'chapters': source, 'cases': [None]}]
        path = self.base / 'malformed.json'
        out = self.base / 'evaluation'
        for value in values:
            with self.subTest(value=value):
                path.write_text(dump(value), encoding='utf-8')
                with self.assertRaises(Error):
                    quality_eval.prepare(path, out)
                self.assertFalse(out.exists())

    def test_scoring_refuses_old_invisible_or_malformed_seeded_locations(self):
        directory, work = self.reviewed_case()
        private_path = directory / 'private.json'
        original = json.loads(private_path.read_text(encoding='utf-8'))
        length = len(work['chapters'][0]['prose'])
        valid = {'chapter': 1, 'start': 0, 'end': 1, 'criterion': 'cost'}
        locations = [None, {}, {**valid, 'chapter': 2}, {**valid, 'chapter': True},
                     {**valid, 'start': -1}, {**valid, 'start': '0'}, {**valid, 'end': length + 1},
                     {**valid, 'start': 2, 'end': 1}, {**valid, 'criterion': 'unknown'}]
        for location in locations:
            private = copy.deepcopy(original)
            private['cases'][0]['locations'] = [location]
            private_path.write_text(dump(private), encoding='utf-8')
            with self.subTest(location=location), self.assertRaises(Error):
                quality_eval.score(directory)
            self.assertFalse((directory / 'score.json').exists())
        private = copy.deepcopy(original)
        private['cases'][0]['locations'] = None
        private_path.write_text(dump(private), encoding='utf-8')
        with self.assertRaises(Error):
            quality_eval.score(directory)
        private_path.write_text(dump(original), encoding='utf-8')
        self.assertIsNone(quality_eval.score(directory)['seeded']['recall'])

    def test_visible_multiple_edits_keep_positions_in_the_delivered_variant(self):
        result = self.prepare([{'chapters': [2], 'edits': [
            {'chapter': 2, 'start': 3, 'old': '三', 'new': '九十九', 'criterion': 'cost'},
            {'chapter': 2, 'start': 6, 'old': '。', 'new': '', 'criterion': 'language'}]}])
        case = result['cases'][0]
        work = json.loads(Path(case['input']).read_text(encoding='utf-8'))
        self.assertEqual(work['chapters'][0]['prose'], '他交出九十九文钱')
        private = json.loads((self.base / 'evaluation' / 'private.json').read_text(encoding='utf-8'))
        self.assertEqual([(row['start'], row['end']) for row in private['cases'][0]['locations']], [(3, 6), (8, 8)])


class WorldRefusalChainTests(unittest.TestCase):
    """A refused world candidate is staged, supplied as previous_proposal, and repaired narrowly.

    The v2 pipeline tore out the v1 candidate loop's refusal staging without replacing it: a
    worker repaired a refused world by re-drafting all of it, and records the refusal had already
    settled came back changed (the results.md #6/#7 lesson, replayed on the world path). This
    pins the restored loop end to end — staging, supply, the narrow guard, its safe downgrade,
    and the cleanup an accepted candidate owes.
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name).resolve()
        self.project = self.base / 'book'
        self.repo = SQLiteRepository.initialize(self.project, workflow.preparing_book(guided=True))
        self.app = Application(self.repo)
        # The structural gate first, so the fixture values the remaining gates generate are
        # already sized to the tier those gates validate against.
        self.app.intake({'scale': {'tier': 't3'}}, '工程夹具：作者先定体量。')
        values = opening_gate_values(self.repo.load())
        self.app.intake(values, '工程夹具：作者一次给全部门的选择。')
        self.task = self.app.advance()['task']
        self.task_id = self.task['task_id']
        self.assertEqual(self.task['stage'], 'world_model')

    def tearDown(self):
        self.repo.close()
        self.temp.cleanup()

    def refused(self, defect):
        """Submit the fixture world receipt with one deterministic defect the engine refuses."""
        broken = copy.deepcopy(response(self.app))
        defect(broken['data'])
        with self.assertRaises(Error) as caught:
            self.app.submit(broken)
        # The refusal kept the frozen task: the worker resubmits against the same input.
        self.assertEqual(self.repo.pending()['id'], self.task_id)
        return broken, caught.exception

    def test_a_duplicate_place_name_refusal_stages_and_narrows_the_repair(self):
        def defect(data):
            row = copy.deepcopy(data['geography'][0])
            row['id'] = 'colliding-yard'
            data['geography'].append(row)

        rejected, error = self.refused(defect)
        self.assertEqual(error.code, 'world_identity')
        self.assertIn('recover', error.details, '拒绝响应要带返修指引')
        # The staged refusal keeps the whole candidate plus findings that name the colliding records.
        staged = self.repo.get(store_keys.world_rejection(self.task_id))
        self.assertEqual(staged['proposal']['geography'][-1]['id'], 'colliding-yard')
        self.assertTrue(staged['findings'])
        # read serves the previous proposal from the staging; the frozen input predates the refusal.
        read = self.app.read(self.task_id)
        self.assertIn('previous_proposal', read['records'])
        self.assertEqual(read['records']['previous_proposal']['value']['proposal'],
                         staged['proposal'])
        # A resubmission whose world half is valid, but which also rewrote an unnamed record,
        # is refused before anything moves.
        def renamed(receipt):
            fixed = copy.deepcopy(receipt)
            for row in fixed['data']['geography']:
                if row['id'] == 'colliding-yard':
                    row['name'] = '不再撞名的后院'
            return fixed

        drifted = renamed(rejected)
        drifted['data']['everyday'][0]['story_use'] = '顺手改掉的日常。'
        with self.assertRaises(Error) as caught:
            self.app.submit(drifted)
        self.assertEqual(caught.exception.code, 'repair_scope')
        self.assertTrue(caught.exception.details['changed_but_not_named'])
        # Only the named fix passes, and acceptance clears the staging.
        outcome = self.app.submit(renamed(rejected))
        self.assertTrue(outcome['accepted'])
        self.assertIsNone(self.repo.get(store_keys.world_rejection(self.task_id)))

    def test_an_unidentifiable_refusal_does_not_fence_the_next_candidate(self):
        society = copy.deepcopy(response(self.app)['data']['society'])

        def defect(data):
            data['society'] = []

        rejected, error = self.refused(defect)
        self.assertEqual(error.code, 'world_section')
        staged = self.repo.get(store_keys.world_rejection(self.task_id))
        # The findings here name no record of the candidate, so the guard does not guess a scope:
        # the next submission may touch records the refusal never mentioned.
        self.assertEqual(workflow.named_items(staged['proposal'], staged['findings']), set())
        healed = copy.deepcopy(rejected)
        healed['data']['society'] = society
        healed['data']['everyday'][0]['story_use'] = '不在点名范围里的修改。'
        outcome = self.app.submit(healed)
        self.assertTrue(outcome['accepted'])
        self.assertIsNone(self.repo.get(store_keys.world_rejection(self.task_id)))

    def test_a_first_dispatch_has_no_staged_previous(self):
        self.assertIsNone(self.repo.get(store_keys.world_rejection(self.task_id)))
        read = self.app.read(self.task_id)
        self.assertNotIn('previous_proposal', read['records'])
        # The declared material table still owns the name; the frozen dispatch just never
        # required it, because there was no refusal to build on.
        self.assertNotIn('previous_proposal', self.repo.pending()['input']['required'])
        from novel_ledger import context
        self.assertIn('previous_proposal', context.STAGE_MATERIAL['world_model'])


if __name__ == '__main__':
    unittest.main()
