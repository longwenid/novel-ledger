"""Behavior regressions for protected outputs, frozen publication and blind evaluations."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

import quality_eval
from novel_ledger import bookpage, delivery, workflow
from novel_ledger.bootstrap import local_application as Application, local_workspace
from novel_ledger.contracts import Error, digest, dump
from novel_ledger.sqlite_store import SQLiteRepository
from support import contract, drive, link_or_skip, response


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

    def test_legacy_completion_metadata_keeps_frozen_content_and_understanding(self):
        owner = self.app.run(finish=True, source='工程夹具：完成四章。')['owner']
        drive(self.app, owner, until='chapter_review')
        candidate = response(self.app)
        candidate['data']['understanding'] = [{
            'id': 'responsibility', 'kind': 'theme', 'claim': '承担责任仍是一种待检验的理解。',
            'subjects': [], 'topics': [], 'status': 'tentative', 'reason': '正文行动支持这个解释。',
            'evidence': [{'chapter': 1, 'quote': '要求先核对退件人的名字再开箱。'}], 'counterevidence': []}]
        self.app.submit(candidate)
        self.assertEqual(drive(self.app, owner)['action'], 'ready_to_complete')
        completed = self.app.complete(owner)
        snapshot = self.repo.read_document(completed['snapshot_hash'])
        self.assertEqual(snapshot['book']['status'], 'completed')
        snapshot['book']['status'] = 'running'
        snapshot['book'].pop('completed_at')
        live = self.repo.load()
        completion_time = live['completed_at']
        live['completion_snapshot'] = self.repo.document(snapshot)
        live['contract']['title'] = '后来修改的标题不进入完本快照'
        live['understanding']['versions'] = []
        self.repo.save(live)
        frozen, rows = delivery.publication(self.repo)
        self.assertEqual(frozen['status'], 'completed')
        self.assertEqual(frozen['completed_at'], completion_time)
        self.assertEqual(frozen['contract']['title'], '夜班退件')
        self.assertEqual(rows, snapshot['chapters'])
        self.assertEqual(frozen['understanding'], snapshot['book']['understanding'])
        page = bookpage.render(self.repo)
        self.assertIn('<b>已完本</b><span>运行状态</span>', page)
        self.assertIn('承担责任仍是一种待检验的理解。', page)
        self.assertNotIn(live['contract']['title'], page)
        self.assertEqual(self.repo.read_document(live['completion_snapshot']), snapshot)

    def test_reading_revision_renders_independent_review_and_frozen_sources(self):
        owner = self.app.run(through=4, source='工程夹具：四章。')['owner']
        drive(self.app, owner)
        self.app.revise(2, '调整人物动机的表达。', owner,
                        changes={'mode': 'reading', 'reading_changes': [{'kind': 'character', 'key': 'shen'}]})
        drive(self.app, owner, until='revision_review')
        candidate = response(self.app)
        reason = '新增独立重读判断 <script>不能执行</script>'
        candidate['data']['reader']['checks'][0]['reason'] = reason
        candidate['data']['reader']['findings'] = [{
            'criterion': candidate['data']['reader']['checks'][0]['id'], 'severity': 'note',
            'reason': '新阅读语境下的建议，不构成返修。', 'evidence': {'chapter': 3, 'quote': '次日'}}]
        self.app.submit(candidate)
        row = self.repo.chapter(self.repo.load()['branch'], 3)
        reading = self.repo.read_document(row['review'])['revision_readings'][0]
        page = bookpage.render(self.repo)
        self.assertIn('修订独立重读 · 第1次 · 通过', page)
        self.assertIn('新增独立重读判断 &lt;script&gt;不能执行&lt;/script&gt;', page)
        self.assertNotIn(reason, page)
        self.assertIn('新阅读语境下的建议，不构成返修。', page)
        self.assertIn('正文版本：' + reading['prose_hash'], page)
        self.assertIn('审稿会话：' + reading['reviewer'], page)
        self.assertIn('冻结首读', page)
        self.assertIn(reading['first_read']['reads'][0]['read_on_reason'], page)
        self.assertIn('原文依据 · 第3章', page)
        self.assertTrue(self.app.audit()['ok'])


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


if __name__ == '__main__':
    unittest.main()
