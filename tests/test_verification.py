"""Verification must reject the successful-looking states observed in the live run."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'tests')]
from novel_ledger.bootstrap import open_local_runtime
from novel_ledger.contracts import Error, digest
from novel_ledger.verification import VerificationService
from novel_ledger import workflow
from support import drive, response, tracked_contract


class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.project = Path(self.temporary.name) / 'book'
        self.runtime = open_local_runtime(self.project, initialize=True, contract=tracked_contract(2))
        self.addCleanup(self.runtime.close)
        self.app, self.repo = self.runtime.app, self.runtime.repo
        self.owner = self.app.run(finish=True, source='工程夹具授权完成两章。')['owner']

    def assertCode(self, code, fn, *args, **kwargs):
        with self.assertRaises(Error) as caught:
            fn(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)

    def finish(self):
        self.assertEqual(drive(self.app, self.owner)['action'], 'ready_to_complete')
        return self.app.complete(self.owner)

    def poison_snapshot(self, change):
        book = self.repo.load()
        snapshot = self.repo.read_document(book['completion_snapshot'])
        change(snapshot)
        snapshot['audit'] = {'ok': True, 'chapters': 2}
        book['completion_snapshot'] = self.repo.document(snapshot)
        self.repo.save(book)
        return book['completion_snapshot']

    def test_out_of_band_initial_and_committed_state_changes_stop_before_more_work(self):
        for phase in ('initial', 'committed'):
            with self.subTest(phase=phase):
                if phase == 'committed':
                    live = self.repo.load()
                    live['state']['resources'].pop('injected', None)
                    self.repo.save(live)
                    drive(self.app, self.owner, until='write')
                    self.app.submit(response(self.app))
                book = self.repo.load()
                book['state']['resources']['injected'] = '0'
                self.repo.save(book)
                before = tuple(self.repo.db.iterdump())
                self.assertCode('projection', self.app.advance, owner=self.owner)
                self.assertEqual(tuple(self.repo.db.iterdump()), before)

    def test_pending_submission_does_not_absorb_an_unrecorded_state_change(self):
        drive(self.app, self.owner, until='write')
        receipt = response(self.app)
        book = self.repo.load()
        book['state']['resources']['injected'] = '0'
        self.repo.save(book)
        before = tuple(self.repo.db.iterdump())
        for submit in (self.app.check, self.app.submit):
            with self.subTest(operation=submit.__name__):
                self.assertCode('projection', submit, receipt)
                self.assertEqual(tuple(self.repo.db.iterdump()), before)
        self.assertEqual(self.repo.task(receipt['task_id'])['status'], 'pending')
        material = self.app.read(receipt['task_id'], everything=True)
        self.assertTrue(material['complete_records'])
        self.assertEqual(material['task_id'], receipt['task_id'])

    def test_invalid_transition_rolls_back_chapters_documents_tasks_and_sessions(self):
        drive(self.app, self.owner, until='write')
        receipt = response(self.app)
        apply = workflow.apply
        def corrupt_transition(*args, **kwargs):
            outcome = apply(*args, **kwargs)
            outcome.book['state']['resources']['unrecorded'] = '0'
            return outcome
        before = tuple(self.repo.db.iterdump())
        with patch.object(workflow, 'apply', side_effect=corrupt_transition):
            self.assertCode('projection', self.app.submit, receipt)
        self.assertEqual(tuple(self.repo.db.iterdump()), before)

    def test_old_author_answer_cannot_grant_budget_to_a_new_candidate(self):
        book = self.repo.load()
        book['draft'] = {'chapter': 1, 'prose': '第一版候选。', 'stage': 'exhausted', 'findings': []}
        book['rework']['1'] = {'repairs': 2, 'redesigns': 1, 'initial_used': True}
        first = workflow.hold_for_draft_exhaustion(book)['id']
        with self.repo.transaction():
            self.app._save(book)  # Trusted fixture setup; direct tampering is separately rejected.
        self.app.answer(first, workflow.REPAIR_AGAIN, '作者为这个版本追加一轮。', self.owner)
        book = self.repo.load()
        book['draft']['prose'] = '第二版候选。'
        book['rework']['1']['repairs'] = 2
        second = workflow.hold_for_draft_exhaustion(book)['id']
        with self.repo.transaction():
            self.app._save(book)
        self.assertNotEqual(first, second)
        before = tuple(self.repo.db.iterdump())
        self.assertCode('author_decision', self.app.answer, first, workflow.REPAIR_AGAIN,
                        '这是对前一个问题的回复。', self.owner)
        self.assertEqual(tuple(self.repo.db.iterdump()), before)
        book = self.repo.load()
        book['author_block']['subject']['prose_hash'] = '0' * 64
        self.repo.save(book)
        before = tuple(self.repo.db.iterdump())
        self.assertCode('governance_integrity', self.app.answer, second, workflow.REPAIR_AGAIN,
                        '对象已被另行修改的答复。', self.owner)
        self.assertEqual(tuple(self.repo.db.iterdump()), before)

    def test_completed_flag_and_saved_success_report_cannot_bypass_required_lines(self):
        self.finish()

        def add_unfinished_line(snapshot):
            snapshot['book']['volumes_outline']['v1']['threads'].append(
                {'id': 'unclosed', 'required': True, 'kind': 'side', 'continues': True})

        reference = self.poison_snapshot(add_unfinished_line)
        md = self.project / 'book.md'
        html = self.project / 'book.html'
        md.write_text('保留已有正文文件。', encoding='utf-8')
        html.write_text('保留已有阅读页面。', encoding='utf-8')
        before = tuple(self.repo.db.iterdump())
        for operation in (self.app.audit, lambda: self.app.complete(self.owner),
                          self.runtime.deliver, self.runtime.html,
                          lambda: self.runtime.export(format='md')):
            with self.subTest(operation=operation):
                self.assertCode('story_closure', operation)
                self.assertEqual(tuple(self.repo.db.iterdump()), before)
                self.assertEqual(md.read_text(encoding='utf-8'), '保留已有正文文件。')
                self.assertEqual(html.read_text(encoding='utf-8'), '保留已有阅读页面。')
                self.assertFalse((self.project / 'delivery.json').exists())
        manifest = {'snapshot_hash': reference, 'chapters': [],
                    'files': [{'path': str(md), 'content_hash': digest(md.read_text(encoding='utf-8'))}]}
        self.assertCode('story_closure', self.app.record_delivery, manifest)
        self.assertIsNone(self.repo.get('completion_delivery'))

    def test_completed_flag_without_sources_is_not_idempotent_success(self):
        book = self.repo.load()
        book['status'] = 'completed'
        self.repo.save(book)
        self.assertCode('completion', self.app.complete, self.owner)
        self.assertCode('completion', self.runtime.deliver)

    def test_completed_queries_use_the_same_verified_frozen_book_as_publication(self):
        completed = self.finish()
        live = self.repo.load()
        live['written_han'] = -1
        live['pilot'] = None
        live['state']['resources']['injected'] = '999'
        self.repo.save(live)
        status = self.app.status()
        self.assertEqual(status['written_han'], completed['written_han'])
        self.assertTrue(self.app.complete(self.owner)['idempotent'])

    def test_completed_review_coverage_uses_frozen_chapter_rows(self):
        self.finish()
        before = self.app.audit()['continuity_review']
        self.repo.db.execute("UPDATE chapters SET review=? WHERE branch='main' AND n=1", ('0' * 64,))
        self.assertEqual(self.app.audit()['continuity_review'], before)

    def test_snapshot_replay_does_not_depend_on_revision_mutation_service(self):
        self.finish()
        self.app._revisions.replay = lambda *args: (_ for _ in ()).throw(AssertionError('mutation service used'))
        # A verifier is runnable with only two read capabilities, no mutable repository API.
        class Sources:
            read_document = self.repo.read_document
            headers = self.repo.headers
        sources = Sources()
        self.assertFalse(hasattr(sources, 'save'))
        for capability in ('save', 'put', 'record', 'transaction', 'prune'):
            self.assertFalse(hasattr(self.app._verification.sources, capability))
        snapshot = VerificationService(sources).snapshot(self.repo.load()['completion_snapshot'])
        self.assertEqual(len(snapshot['chapters']), 2)
        repeated = self.app.complete(self.owner)
        self.assertTrue(repeated['idempotent'])
        self.assertEqual(repeated['verification_scope'], 'mechanical')
        self.assertIn('model_context_isolation', repeated['unverified'])

    def test_changing_frozen_chapter_rows_cannot_be_hidden_by_a_saved_audit(self):
        self.finish()
        def replace_state_hash(snapshot):
            snapshot['chapters'][0]['state_hash'] = '0' * 64
        self.poison_snapshot(replace_state_hash)
        self.assertCode('state_integrity', self.runtime.deliver)
        self.assertFalse((self.project / 'delivery.json').exists())


if __name__ == '__main__':
    unittest.main()
