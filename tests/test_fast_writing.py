"""Fast writing reuses one real execution identity in a bounded five-chapter group."""
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'tests')]
from novel_ledger import store_keys, unattended
from novel_ledger.bootstrap import open_local_runtime
from novel_ledger.contracts import Error, digest
from support import contract, drive, response


class FastWritingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name) / 'book'
        self.runtime = open_local_runtime(self.project, initialize=True, contract=contract(12))
        self.addCleanup(self.runtime.close)
        self.app, self.repo = self.runtime.app, self.runtime.repo
        self.owner = self.app.run(finish=True, source='工程授权快速完本。', mode='fast')['owner']
        drive(self.app, self.owner, until='write')

    def start_group(self, session='fast-worker'):
        pilot = self.repo.pending()
        self.assertNotIn('worker_batch', pilot['input']['payload'])
        self.app.submit(response(self.app))
        step = self.app.advance(owner=self.owner)
        self.assertEqual(step['action'], 'await_author')
        self.app.approve(step['prose_hash'], '作者认可这一版首章。', self.owner)
        task = self.app.advance(owner=self.owner)['task']
        self.assertEqual(task['worker_batch']['first'], 2)
        lease = self.app.claim(task['task_id'], session)
        return task, lease

    def submit(self, session, lease):
        receipt = response(self.app)
        receipt.update(session=session, execution_claim=lease['token'])
        return receipt, self.app.submit(receipt)

    def next(self, task, lease, session='fast-worker'):
        step = self.app.continue_writing(task['task_id'], session, lease['token'])
        return step['task'], {'token': step['execution_claim']}

    def test_same_worker_commits_five_chapters_then_a_new_group_requires_a_fresh_worker(self):
        task, lease = self.start_group()
        group_id = task['worker_batch']['id']
        plans = copy.deepcopy(self.repo.load()['plans'])
        for chapter in range(2, 7):
            self.assertEqual(self.repo.pending()['input']['chapter'], chapter)
            receipt, result = self.submit('fast-worker', lease)
            self.assertEqual(result['committed_chapter'], chapter)
            self.assertEqual(result['book_view']['chapters'], chapter)
            page = Path(result['book_view']['path']).read_text(encoding='utf-8')
            self.assertEqual(page.count('<section class="chapter"'), chapter)
            self.assertIn('id="read-' + str(chapter) + '"', page)
            self.assertEqual(result['worker_boundary'], 'finished' if chapter == 6 else 'continue')
            if chapter < 6:
                self.assertEqual(self.app.advance(owner=self.owner)['action'], 'wait_for_batch')
                task, lease = self.next(task, lease)
                self.assertEqual(task['worker_batch']['id'], group_id)
                self.assertFalse(task['requires_new_worker'])
        self.assertEqual(len(self.repo.headers('main')), 6)
        self.assertEqual(self.repo.load()['plans'], plans)
        new = self.app.advance(owner=self.owner)['task']
        self.assertEqual((new['worker_batch']['first'], new['worker_batch']['last']), (7, 11))
        with self.assertRaises(Error) as caught:
            self.app.claim(new['task_id'], 'fast-worker')
        self.assertEqual(caught.exception.code, 'session_reuse')
        self.app.claim(new['task_id'], 'next-worker')

    def test_failed_prose_repairs_the_same_chapter_without_spending_the_next_chapter_budget(self):
        task, lease = self.start_group()
        before = copy.deepcopy(self.repo.load())
        receipt = response(self.app)
        receipt.update(session='fast-worker', execution_claim=lease['token'])
        receipt['data']['drift_check']['items'].pop()
        self.assertIsNone(self.app.submit(receipt)['committed_chapter'])
        task, lease = self.next(task, lease)
        self.assertEqual((task['stage'], task['chapter']), ('repair', 2))
        self.assertEqual(self.repo.load()['plans'], before['plans'])
        self.assertNotIn('3', self.repo.load()['rework'])
        _, result = self.submit('fast-worker', lease)
        self.assertEqual(result['committed_chapter'], 2)
        self.assertEqual(self.repo.load()['rework']['2']['repairs'], 1)
        task, lease = self.next(task, lease)
        self.assertEqual((task['stage'], task['chapter']), ('write', 3))

    def test_continuation_is_idempotent_but_old_or_foreign_callbacks_cannot_skip_work(self):
        first, lease = self.start_group()
        self.submit('fast-worker', lease)
        second, second_lease = self.next(first, lease)
        result_file = Path(second['task_path']).parent / 'result.json'
        result_file.write_text(json.dumps({'session': 'fast-worker', 'data': {'prose': '已写好的一部分。'}}), encoding='utf-8')
        partial = result_file.read_text(encoding='utf-8')
        repeated, repeated_lease = self.next(first, lease)
        self.assertEqual(repeated['task_id'], second['task_id'])
        self.assertEqual(repeated_lease, second_lease)
        self.assertEqual(result_file.read_text(encoding='utf-8'), partial)
        before = tuple(self.repo.db.iterdump())
        with self.assertRaises(Error):
            self.app.continue_writing(first['task_id'], 'other-worker', lease['token'])
        self.assertEqual(tuple(self.repo.db.iterdump()), before)
        self.submit('fast-worker', second_lease)
        third, _ = self.next(second, second_lease)
        before = tuple(self.repo.db.iterdump())
        with self.assertRaises(Error):
            self.app.continue_writing(first['task_id'], 'fast-worker', lease['token'])
        self.assertEqual(tuple(self.repo.db.iterdump()), before)
        self.assertEqual(self.repo.pending()['id'], third['task_id'])

    def test_unchanged_material_is_reused_only_inside_the_same_group(self):
        task, lease = self.start_group()
        first = self.app.read(task['task_id'])
        self.assertIn('contract', first['records'])
        self.submit('fast-worker', lease)
        task, lease = self.next(task, lease)
        second = self.app.read(task['task_id'])
        self.assertIn('contract', second['already_read'])
        self.assertIn('chapter_outline', second['records'])
        self.assertIn('state', second['records'])
        complete = self.app.read(task['task_id'], everything=True)
        self.assertIn('contract', complete['records'])

    def test_cancelled_group_keeps_committed_prefix_and_cannot_be_resumed_by_its_worker(self):
        task, lease = self.start_group()
        self.submit('fast-worker', lease)
        self.app.pause('作者要求中断本组。', cancel=True, owner=self.owner)
        self.app.resume(self.owner)
        stop = self.app.continue_writing(task['task_id'], 'fast-worker', lease['token'])
        self.assertEqual(stop['action'], 'batch_finished')
        fresh = self.app.advance(owner=self.owner)['task']
        self.assertEqual(fresh['chapter'], 3)
        self.assertEqual(len(self.repo.headers('main')), 2)
        self.assertTrue(fresh['requires_new_worker'])
        with self.assertRaises(Error):
            self.app.claim(fresh['task_id'], 'fast-worker')

    def test_short_target_stops_inside_a_group_and_standard_mode_keeps_one_worker_per_task(self):
        self.app.run(through=3, owner=self.owner, mode='fast')
        task, lease = self.start_group()
        self.assertEqual(task['worker_batch']['last'], 3)
        self.submit('fast-worker', lease)
        task, lease = self.next(task, lease)
        _, result = self.submit('fast-worker', lease)
        self.assertEqual(result['worker_boundary'], 'finished')
        self.assertEqual(self.app.advance(owner=self.owner)['action'], 'target_reached')
        self.app.run(through=5, owner=self.owner, mode='standard')
        task = self.app.advance(owner=self.owner)['task']
        self.assertNotIn('worker_batch', task)
        lease = self.app.claim(task['task_id'], 'ordinary-worker')
        self.submit('ordinary-worker', lease)
        task = self.app.advance(owner=self.owner)['task']
        with self.assertRaises(Error):
            self.app.claim(task['task_id'], 'ordinary-worker')

    def test_cli_worker_can_continue_but_cannot_advance_or_approve(self):
        task, lease = self.start_group()
        self.submit('fast-worker', lease)
        base = [sys.executable, str(ROOT / 'scripts/novel.py'), '--project', str(self.project)]
        environment = {**os.environ, 'NOVEL_TASK_ID': task['task_id'], 'NOVEL_SESSION': 'fast-worker',
                       'NOVEL_EXECUTION_CLAIM': lease['token']}
        continued = subprocess.run(base + ['worker-next', '--task', task['task_id']], env=environment,
                                   capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(continued.stdout)['task']['chapter'], 3)
        for command in (['advance'], ['approve', '--prose-hash', 'x', '--source', '伪造认可。']):
            denied = subprocess.run(base + command, env=environment, capture_output=True, text=True)
            self.assertNotEqual(denied.returncode, 0)
            self.assertEqual(json.loads(denied.stdout)['error'], 'worker_boundary')

    def test_preflight_rolls_back_group_cursor_session_and_chapter_changes(self):
        task, lease = self.start_group()
        receipt = response(self.app)
        receipt.update(session='fast-worker', execution_claim=lease['token'])
        before = tuple(self.repo.db.iterdump())
        checked = self.app.check(receipt)
        self.assertIsNotNone(checked['committed_chapter'])
        self.assertTrue(checked['checked'])
        self.assertEqual(tuple(self.repo.db.iterdump()), before)
        self.assertEqual(self.repo.pending()['id'], task['task_id'])

    def test_stalled_repairs_end_the_group_and_keep_the_per_chapter_budget(self):
        task, lease = self.start_group()
        for round_number in range(3):
            receipt = response(self.app)
            receipt.update(session='fast-worker', execution_claim=lease['token'])
            receipt['data']['drift_check']['items'].pop()
            result = self.app.submit(receipt)
            if round_number < 2:
                task, lease = self.next(task, lease)
        self.assertEqual(result['worker_boundary'], 'finished')
        book = self.repo.load()
        self.assertEqual(book['status'], 'paused')
        self.assertEqual(book['rework']['2']['repairs'], 2)
        self.assertNotIn('3', book['rework'])
        self.assertEqual(self.app.continue_writing(task['task_id'], 'fast-worker', lease['token'])['action'],
                         'batch_finished')

    def test_fast_book_finishes_and_delivers_with_one_session_per_group(self):
        task, lease = self.start_group()
        groups = []
        session_number = 1
        session = 'fast-worker'
        while True:
            group_id = task['worker_batch']['id']
            if not groups or groups[-1] != group_id:
                groups.append(group_id)
            _, result = self.submit(session, lease)
            if result['worker_boundary'] == 'continue':
                task, lease = self.next(task, lease, session)
                continue
            step = self.app.advance(owner=self.owner)
            if step['action'] == 'ready_to_complete':
                break
            self.assertEqual(step['action'], 'task_ready')
            task = step['task']
            session_number += 1
            session = 'fast-worker-' + str(session_number)
            lease = self.app.claim(task['task_id'], session)
        self.assertEqual(len(groups), 3)
        self.assertEqual(len(self.repo.headers('main')), 12)
        self.assertTrue(self.app.complete(self.owner)['completed'])
        self.assertTrue(self.runtime.deliver()['delivered'])

    def test_watch_waits_for_the_entire_group_and_returns_the_next_new_worker(self):
        task, lease = self.start_group()
        state = {'task': task, 'lease': lease}
        def work(_seconds):
            current = state['task']
            _, result = self.submit('fast-worker', state['lease'])
            if result['worker_boundary'] == 'continue':
                state['task'], state['lease'] = self.next(current, state['lease'])
        result = unattended.watch(self.app, self.owner, poll=0.01, idle_limit=100, sleep=work)
        self.assertEqual(result['action'], 'task_ready')
        self.assertEqual(result['task']['chapter'], 7)
        self.assertTrue(result['task']['requires_new_worker'])
        self.assertEqual(len(self.repo.headers('main')), 6)

    def test_changed_future_outline_cannot_be_silently_adopted_by_continuation(self):
        task, lease = self.start_group()
        self.submit('fast-worker', lease)
        book = self.repo.load()
        book['plans']['3']['synopsis'] += '在本组之外擅自改变章纲。'
        self.repo.save(book)
        before = tuple(self.repo.db.iterdump())
        with self.assertRaises(Error) as caught:
            self.app.continue_writing(task['task_id'], 'fast-worker', lease['token'])
        self.assertEqual(caught.exception.code, 'writing_batch')
        self.assertEqual(tuple(self.repo.db.iterdump()), before)

    def test_changed_current_outline_rolls_back_the_entire_submission(self):
        task, lease = self.start_group()
        book = self.repo.load()
        book['plans']['2']['synopsis'] += '擅自修改正在执行的章纲。'
        self.repo.save(book)
        receipt = response(self.app)
        receipt.update(session='fast-worker', execution_claim=lease['token'])
        before = tuple(self.repo.db.iterdump())
        with self.assertRaises(Error) as caught:
            self.app.submit(receipt)
        self.assertEqual(caught.exception.code, 'writing_batch')
        self.assertEqual(tuple(self.repo.db.iterdump()), before)
        self.assertEqual(self.repo.pending()['id'], task['task_id'])

    def test_reopening_keeps_mode_range_and_same_worker_continuation(self):
        task, lease = self.start_group()
        self.submit('fast-worker', lease)
        reopened = open_local_runtime(self.project)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.app.status()['writing_mode'], 'fast')
        step = reopened.app.continue_writing(task['task_id'], 'fast-worker', lease['token'])
        self.assertEqual(step['task']['chapter'], 3)
        self.assertEqual(step['task']['worker_batch']['last'], 6)

    def test_group_stops_at_volume_boundary(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        runtime = open_local_runtime(Path(temporary.name) / 'volumes', initialize=True, contract=contract(6, 2))
        self.addCleanup(runtime.close)
        owner = runtime.app.run(finish=True, mode='fast')['owner']
        drive(runtime.app, owner, until='write')
        runtime.app.submit(response(runtime.app))
        step = runtime.app.advance(owner=owner)
        runtime.app.approve(step['prose_hash'], '作者认可首章。', owner)
        task = runtime.app.advance(owner=owner)['task']
        self.assertEqual((task['worker_batch']['first'], task['worker_batch']['last']), (2, 3))

    def test_one_real_subprocess_completes_the_entire_group_through_cli_guards(self):
        self.app.submit(response(self.app))
        step = self.app.advance(owner=self.owner)
        self.app.approve(step['prose_hash'], '作者认可首章。', self.owner)
        result = self.runtime.host_step([sys.executable, str(ROOT / 'tests/process_worker.py'), 'fast'],
                                        self.owner, timeout=30)
        self.assertEqual(result['action'], 'worker_finished')
        self.assertFalse(result['batch_active'])
        log = json.loads(Path(result['log']).read_text(encoding='utf-8'))
        self.assertEqual(log['chapters'], [2, 3, 4, 5, 6])
        self.assertTrue(log['synthetic'])
        self.assertEqual(len(self.repo.headers('main')), 6)


if __name__ == '__main__':
    unittest.main()
