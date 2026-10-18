"""Local presentation works with an opaque, read-only, non-SQLite ledger."""
import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from novel_ledger import bookpage, delivery
from novel_ledger.contracts import Error, digest, han_count
from novel_ledger.presentation import LocalPresentation
from novel_ledger.publication import publication
from novel_ledger.workspace import LocalWorkspace
from support import link_or_skip


class MemoryReader:
    """No project path, connection, lifecycle operations, or storage-specific names."""
    def __init__(self):
        self.book = {'branch': 'main', 'status': 'running', 'contract': None,
                     'state': {}, 'written_han': 0, 'plans': {},
                     'volumes_outline': {}, 'chapter_outlines': {}, 'design_drift': []}
        self.documents = {'prose': '夜班的灯亮着，沈桐再次核对箱子上的签字。',
                          'state': {'clock': 0, 'resources': {}, 'placements': {}, 'knowledge': {}, 'hooks': {}}}
        self.rows = []

    def load(self):
        return copy.deepcopy(self.book)

    def read_document(self, key):
        return copy.deepcopy(self.documents[key])

    def headers(self, branch):
        return copy.deepcopy(self.rows)

    def get(self, key, default=None):
        return default


class PresentationBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.workspace = LocalWorkspace(self.root / 'workspace')
        self.repo = MemoryReader()
        self.presentation = LocalPresentation(self.repo, self.workspace, ROOT / 'scripts' / 'novel.py')

    def tearDown(self):
        self.temp.cleanup()

    def task(self):
        return {'id': 'opaque-task', 'input_hash': 'frozen-input', 'reviewer': None,
                'input': {'schema': 1, 'stage': 'write', 'chapter': 1, 'scope': 'chapter',
                          'prose': [{'chapter': 1, 'hash': 'prose'}],
                          'records': {'state': 'state'}, 'required': [], 'payload': {}, 'obligations': []}}

    def test_view_and_task_files_need_only_reader_and_workspace(self):
        rendered = bookpage.render(self.repo)
        self.assertIn('未定名书稿', rendered)
        self.assertNotIn('novel.sqlite3', rendered)
        page = bookpage.write(self.repo, workspace=self.workspace)
        self.assertEqual(Path(page['path']).read_text(encoding='utf-8'), rendered)
        view = self.presentation.task(self.task(), baseline={'clock': 0})
        self.assertEqual(view['project_path'], str(self.workspace.project))
        self.assertEqual(view['host_log_path'], str(self.workspace.project / 'work/opaque-task/host.log'))
        self.assertEqual(Path(view['prose_files'][0]['path']).read_text(encoding='utf-8'), self.repo.documents['prose'])
        self.assertIn(str(self.workspace.project), view['commands']['submit'])
        form = Path(view['template_path'])
        receipt = json.loads(form.read_text(encoding='utf-8'))
        receipt['data']['title'] = 'Worker 已填写'
        form.write_text(json.dumps(receipt, ensure_ascii=False), encoding='utf-8')
        self.presentation.task(self.task())
        self.assertEqual(json.loads(form.read_text(encoding='utf-8'))['data']['title'], 'Worker 已填写')

    def test_every_dispatch_is_formal_and_shows_the_baseline_it_reconciles_against(self):
        """v2 has no blind first read: the drift_check is compared with the projected before-state.

        The retired protocol materialized a separate first-read file and hid the baseline until the
        reviewer had filed one. With the reviewer gone, the baseline is what the writer's
        `actual.from` is checked against, so it must be in the same envelope the writer reads.
        """
        formal = self.presentation.task(self.task())
        self.assertEqual(formal['delivery_phase'], 'formal')
        self.assertEqual(formal['baseline']['clock'], 0)
        self.assertIn('source', formal['baseline'])
        self.assertIn('input_path', formal)
        self.assertTrue(formal['requires_new_worker'])
        self.assertNotIn('first_read_path', formal)
        self.assertNotIn('blind', formal)
        identity = json.loads(Path(formal['identity_path']).read_text(encoding='utf-8'))
        self.assertEqual(identity['delivery_phase'], 'formal')
        self.assertNotIn('first_read', json.dumps(identity, ensure_ascii=False))
        # The worker's half-filled form is never blanked by a later render of the same task.
        Path(formal['result_path']).write_text('Worker 已填写', encoding='utf-8')
        self.presentation.task(self.task())
        self.assertEqual(Path(formal['result_path']).read_text(encoding='utf-8'), 'Worker 已填写')

    def test_revision_file_contains_the_complete_frozen_plan(self):
        plan = {'plan_hash': 'abc123', 'blocked': True, 'changes': [{'kind': 'canon', 'key': 'rule'}],
                'affected': {'chapters': [1, 4], 'reason': '世界规则变化'}}
        path = self.presentation.revision(plan)
        self.assertEqual(path, self.presentation.revision_path('abc123'))
        self.assertEqual(json.loads(Path(path).read_text(encoding='utf-8')), plan)

    def test_revision_replaces_final_link_and_rejects_work_parent_escape(self):
        external = self.root / 'external.txt'
        external.write_text('external content', encoding='utf-8')
        work = self.workspace.project / 'work'
        work.mkdir(parents=True)
        revision = work / 'revision-abc123.json'
        link_or_skip(self, revision, external)
        plan = {'plan_hash': 'abc123', 'blocked': True}
        self.presentation.revision(plan)
        self.assertFalse(revision.is_symlink())
        self.assertEqual(json.loads(revision.read_text(encoding='utf-8')), plan)
        self.assertEqual(external.read_text(encoding='utf-8'), 'external content')
        revision.unlink()
        work.rmdir()
        outside = self.root / 'outside-work'
        outside.mkdir()
        link_or_skip(self, work, outside, target_is_directory=True)
        with self.assertRaises(Error) as caught:
            self.presentation.revision(plan)
        self.assertEqual(caught.exception.code, 'output')
        self.assertEqual(list(outside.iterdir()), [])

    def test_world_files_need_only_reader_and_workspace(self):
        model = {'selection_hash': 'frozen-selection', 'premise': '夜班仓库的退件纠纷。',
                 'story_capacity': '调查责任怎样沿经手关系传递。'}
        self.repo.book.update(world=model, creation={'selections': [{'gate': 'genre'}]})
        self.workspace.project.mkdir()
        external = self.root / 'external-world.txt'
        external.write_text('external world content', encoding='utf-8')
        for name in ('world.json', 'book.html'):
            link_or_skip(self, self.workspace.project / name, external)
        result = self.presentation.world()
        self.assertEqual(external.read_text(encoding='utf-8'), 'external world content')
        self.assertFalse((self.workspace.project / 'world.json').is_symlink())
        self.assertFalse((self.workspace.project / 'book.html').is_symlink())
        self.assertIn(model['premise'], Path(result['html_path']).read_text(encoding='utf-8'))
        data = json.loads(Path(result['json_path']).read_text(encoding='utf-8'))
        self.assertEqual(data['world'], model)
        self.assertEqual(data['choices'], [{'gate': 'genre'}])
        self.assertEqual(data['model_hash'], result['model_hash'])

    def test_publication_keeps_completed_content_frozen_without_storage_adapter(self):
        frozen = copy.deepcopy(self.repo.book)
        frozen['contract'] = {'title': '冻结书名'}
        self.repo.documents['snapshot'] = {'book': frozen, 'chapters': []}
        self.repo.book.update(status='completed', completed_at=123, completion_snapshot='snapshot',
                              contract={'title': '后改书名'})
        book, rows = publication(self.repo)
        self.assertEqual(book['contract']['title'], '冻结书名')
        self.assertEqual(book['status'], 'completed')
        self.assertEqual(book['completed_at'], 123)
        self.assertEqual(rows, [])
        self.assertEqual(self.repo.documents['snapshot']['book'], frozen)
        exported = delivery.export_book(self.repo, format='md', workspace=self.workspace)
        self.assertEqual(Path(exported['path']).read_text(encoding='utf-8').strip(), '# 冻结书名')

    def test_complete_delivery_uses_only_reader_and_preserves_frozen_content(self):
        prose = self.repo.documents['prose']
        frozen = copy.deepcopy(self.repo.book)
        frozen.update(status='completed', completed_at=123, written_han=han_count(prose),
                      contract={'title': '冻结书名', 'word_range': [1, 100], 'chapter_min': 1,
                                'chapter_max': 100, 'chapter_aim': 50,
                                'volumes': [{'id': 'v1', 'first': 1, 'end': 1, 'purpose': '查明来源。'}]})
        row = {'n': 1, 'title': '冻结章节', 'prose': 'prose', 'review': 'review',
               'han': han_count(prose), 'summary': '查明签字来源。'}
        self.repo.documents.update(review={'facts': {}, 'reader': {}},
                                   snapshot={'book': frozen, 'chapters': [row]})
        self.repo.book.update(status='completed', completed_at=123, completion_snapshot='snapshot',
                              contract={'title': '后来修改的书名'})
        self.repo.rows = [{**row, 'title': '后来修改的章节'}]
        before = copy.deepcopy(vars(self.repo))
        for name in ('transaction', 'put', 'record', 'project'):
            self.assertFalse(hasattr(self.repo, name), name)

        self.workspace.project.mkdir()
        external = self.root / 'external-completion.txt'
        external.write_text('external completion content', encoding='utf-8')
        for name in ('book.md', 'book.html', 'delivery.json'):
            link_or_skip(self, self.workspace.project / name, external)

        result = delivery.deliver_completion(self.repo, bookpage.render, workspace=self.workspace)

        self.assertEqual(external.read_text(encoding='utf-8'), 'external completion content')
        self.assertFalse(any((self.workspace.project / name).is_symlink()
                             for name in ('book.md', 'book.html', 'delivery.json')))
        self.assertTrue(result['delivered'])
        self.assertEqual(result['snapshot_hash'], 'snapshot')
        self.assertEqual(result['chapters'], [{'chapter': 1, 'prose_hash': 'prose'}])
        self.assertEqual({Path(row['path']).name for row in result['files']}, {'book.md', 'book.html'})
        for file in result['files']:
            content = Path(file['path']).read_text(encoding='utf-8')
            self.assertIn('冻结书名', content)
            self.assertIn('冻结章节', content)
            self.assertIn(prose, content)
            self.assertNotIn('后来修改', content)
            self.assertEqual(file['content_hash'], digest(content))
        manifest = json.loads(Path(result['manifest_path']).read_text(encoding='utf-8'))
        self.assertEqual(manifest, {key: result[key] for key in ('snapshot_hash', 'chapters', 'files')})
        self.assertEqual(vars(self.repo), before)

    def test_arbitrary_protected_names_reject_direct_symbolic_and_hard_link_aliases(self):
        protected = self.root / 'opaque-ledger.data'
        protected.write_text('storage must survive', encoding='utf-8')
        transaction = self.root / 'opaque-transaction.chunk'
        workspace = LocalWorkspace(self.workspace.project, (protected, transaction))
        symbolic = self.root / 'symbolic-output.html'
        link_or_skip(self, symbolic, protected)
        dangling = self.root / 'transaction-alias.html'
        link_or_skip(self, dangling, transaction)
        hard_link = self.root / 'hard-linked-output.html'
        os.link(protected, hard_link)
        for target in (protected, transaction, symbolic, dangling, hard_link):
            for writer in (bookpage.write, delivery.export_book):
                with self.subTest(target=target, writer=writer.__name__):
                    # A contract is enough for an empty prose export.
                    self.repo.book['contract'] = {'title': '测试书名'}
                    with self.assertRaises(Error) as caught:
                        writer(self.repo, target, workspace=workspace)
                    self.assertEqual(caught.exception.code, 'output')
        self.assertEqual(protected.read_text(encoding='utf-8'), 'storage must survive')
        self.assertFalse(transaction.exists())

    def test_task_artifact_alias_cannot_overwrite_or_retire_protected_storage(self):
        protected = self.root / 'opaque-ledger.data'
        protected.write_text('storage must survive', encoding='utf-8')
        workspace = LocalWorkspace(self.workspace.project, (protected,))
        base = workspace.project / 'work/opaque-task'
        base.mkdir(parents=True)
        link_or_skip(self, base / 'input.json', protected)
        presentation = LocalPresentation(self.repo, workspace, ROOT / 'scripts/novel.py')
        for operation in (lambda: presentation.task(self.task()), lambda: presentation.retire('opaque-task')):
            with self.assertRaises(Error) as caught:
                operation()
            self.assertEqual(caught.exception.code, 'output')
        self.assertEqual(protected.read_text(encoding='utf-8'), 'storage must survive')

    def test_retiring_work_symlink_removes_the_link_and_preserves_external_target(self):
        outside = self.root / 'outside-draft.txt'
        outside.write_text('作者的其他文档', encoding='utf-8')
        base = self.workspace.project / 'work/opaque-task'
        base.mkdir(parents=True)
        alias = base / 'input.json'
        link_or_skip(self, alias, outside)

        self.presentation.retire('opaque-task')

        self.assertEqual(outside.read_text(encoding='utf-8'), '作者的其他文档')
        self.assertFalse(alias.is_symlink())

    def test_materializing_work_symlink_replaces_the_link_and_preserves_external_target(self):
        outside = self.root / 'outside-draft.txt'
        outside.write_text('作者的其他文档', encoding='utf-8')
        base = self.workspace.project / 'work/opaque-task'
        base.mkdir(parents=True)
        aliases = [base / name for name in ('input.json', 'chapter-1.txt', 'task.json')]
        for alias in aliases:
            link_or_skip(self, alias, outside)

        view = self.presentation.task(self.task())

        self.assertEqual(outside.read_text(encoding='utf-8'), '作者的其他文档')
        self.assertTrue(all(path.is_file() and not path.is_symlink() for path in aliases))
        self.assertEqual(json.loads(Path(view['input_path']).read_text(encoding='utf-8'))['task_id'], 'opaque-task')
        self.assertEqual(Path(view['prose_files'][0]['path']).read_text(encoding='utf-8'), self.repo.documents['prose'])

    def test_task_and_work_parent_symlinks_cannot_escape_the_project(self):
        for parent in ('work', 'work/opaque-task'):
            with self.subTest(parent=parent):
                project = self.root / parent.replace('/', '-')
                outside = self.root / ('outside-' + parent.replace('/', '-'))
                outside.mkdir()
                original = outside / 'input.json'
                original.write_text('项目外原稿', encoding='utf-8')
                link = project / parent
                link.parent.mkdir(parents=True)
                link_or_skip(self, link, outside, target_is_directory=True)
                workspace = LocalWorkspace(project)
                presentation = LocalPresentation(self.repo, workspace, ROOT / 'scripts/novel.py')
                for operation in (lambda: presentation.task(self.task()), lambda: presentation.retire('opaque-task')):
                    with self.assertRaises(Error) as caught:
                        operation()
                    self.assertEqual(caught.exception.code, 'output')
                self.assertEqual(original.read_text(encoding='utf-8'), '项目外原稿')
                self.assertEqual(list(outside.iterdir()), [original])


if __name__ == '__main__':
    unittest.main()
