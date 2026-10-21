"""The engine's own wait loop: no host inference while an externally executed worker runs.

A real unattended run kept its controller loop in the host session: dispatch, sleep, poll
`status`, repeat — 121 polls and 11.5 hours of full-context model calls that only ever waited
for a worker that needed no supervision. watch owns that waiting, and returns to the caller
exactly when the caller has something to do.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from novel_ledger import unattended, workflow
from novel_ledger.bootstrap import local_application as Application, open_local_runtime
from novel_ledger.contracts import Error
from novel_ledger.sqlite_store import SQLiteRepository
from support import contract, drive, response


class FakeWatchApp:
    """A scripted application: a queue of handoffs plus when each task stops being pending."""

    def __init__(self, handoffs, pending_reads=2):
        self.handoffs = list(handoffs)
        self.pending_reads = pending_reads
        self.advance_owners = []
        self.renews = 0
        self.reads = {}
        self.slept = []

    def advance(self, after=None, owner=None, compact=False, wait_pending=False):
        self.advance_owners.append(owner)
        return self.handoffs.pop(0)

    def renew(self, owner, seconds=300):
        self.renews += 1

    def task_status(self, task_id):
        seen = self.reads.get(task_id, 0) + 1
        self.reads[task_id] = seen
        return {'id': task_id, 'status': 'pending' if seen <= self.pending_reads else 'done',
                'reviewer': None}

    def clock(self):
        # Fine enough that the lease renewal (every 30s) fires before the idle limit (100s).
        self.now = getattr(self, 'now', 0) + 10
        return self.now

    def sleeper(self, seconds):
        self.slept.append(seconds)


def ready(task_id, stage='write', chapter=1):
    return {'action': 'task_ready', 'task': {'task_id': task_id, 'stage': stage,
                                             'chapter': chapter, 'scope': 'chapter'}}


class WatchUnitTests(unittest.TestCase):
    def test_one_step_waits_for_the_task_then_hands_back_the_next_dispatch(self):
        app = FakeWatchApp([ready('a'), ready('b', 'write')])
        result = unattended.watch(app, 'owner-1', steps=1, poll=1, idle_limit=1000,
                                  sleep=app.sleeper, now=app.clock)
        self.assertEqual(result['action'], 'task_ready')
        self.assertEqual(result['task']['task_id'], 'b')
        self.assertEqual(result['dispatched'], [{'task_id': 'a', 'stage': 'write',
                                                 'chapter': 1, 'scope': 'chapter'}])
        self.assertEqual(app.advance_owners, ['owner-1', 'owner-1'])
        self.assertIn('watch_note', result)

    def test_a_stop_point_is_returned_untouched_with_what_was_overseen(self):
        app = FakeWatchApp([ready('a'), {'action': 'await_author', 'prose_hash': 'h'}])
        result = unattended.watch(app, 'owner-1', steps=1, poll=1, idle_limit=1000,
                                  sleep=app.sleeper, now=app.clock)
        self.assertEqual(result['action'], 'await_author')
        self.assertEqual(result['prose_hash'], 'h')
        self.assertEqual([row['task_id'] for row in result['dispatched']], ['a'])

    def test_a_silent_worker_returns_idle_instead_of_waiting_forever(self):
        app = FakeWatchApp([ready('a')], pending_reads=10 ** 9)
        result = unattended.watch(app, 'owner-1', steps=1, poll=1, idle_limit=100,
                                  sleep=app.sleeper, now=app.clock)
        self.assertEqual(result['action'], 'idle')
        self.assertEqual(result['task_id'], 'a')
        self.assertTrue(app.renews >= 1)

    def test_the_dispatch_journal_sees_every_overseen_task(self):
        app = FakeWatchApp([ready('a'), ready('b')])
        seen = []
        unattended.watch(app, 'owner-1', steps=1, poll=1, idle_limit=1000,
                         sleep=app.sleeper, now=app.clock, on_dispatch=seen.append)
        self.assertEqual([row['task_id'] for row in seen], ['a'])

    def test_watch_requires_the_controller_identity(self):
        self.assertRaises(Error, unattended.watch, FakeWatchApp([]), '  ')


class WatchIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / 'book'

    def tearDown(self):
        self.temp.cleanup()

    def test_waiting_preserves_an_active_receipt_with_or_without_a_claim(self):
        for claimed in (False, True):
            with self.subTest(claimed=claimed):
                project = self.project / str(claimed)
                repo = SQLiteRepository.initialize(project, workflow.new_book(contract()))
                try:
                    app = Application(repo)
                    owner = app.run(through=1, source='作者授权试章。')['owner']
                    task = drive(app, owner, until='write')['task']
                    session = 'active-writer'
                    claim = app.claim(task['task_id'], session)['token'] if claimed else None
                    receipt = response(app, session=session, claim=claim)
                    result_path = Path(task['result_path'])
                    result_path.write_text(json.dumps(receipt, ensure_ascii=False), encoding='utf-8')
                    before = result_path.read_bytes()
                    submitted = []

                    def finish_worker(_seconds):
                        # This is the same frozen file commands.submit will open, after watch has
                        # entered its wait. A re-dispatch here used to move the file away.
                        self.assertEqual(result_path.read_bytes(), before)
                        self.assertFalse(result_path.with_name('result.stale.json').exists())
                        submitted.append(app.submit(json.loads(result_path.read_text(encoding='utf-8'))))

                    result = unattended.watch(app, owner, steps=1, poll=0.01, idle_limit=1,
                                              sleep=finish_worker)
                    self.assertEqual(result['action'], 'await_author')
                    self.assertEqual(len(submitted), 1)
                    self.assertEqual(submitted[0]['committed_chapter'], 1)
                    self.assertEqual(app.status()['formal_chapters'], 1)
                finally:
                    repo.close()

    def test_the_local_runtime_journals_dispatches_and_reports_idle(self):
        repo = SQLiteRepository.initialize(self.project, workflow.new_book(contract()))
        app = Application(repo)
        run = app.run(through=1, source='工程夹具授权。')
        owner = run['owner']
        app.advance(owner=owner)
        app.submit(response(app))          # the chapter outline is done before watch starts
        repo.close()
        runtime = open_local_runtime(str(self.project))
        try:
            result = runtime.watch(owner, steps=1, poll=0.01, idle_limit=0.05)
        finally:
            runtime.close()
        self.assertEqual(result['action'], 'idle')
        journal = (self.project / 'work' / 'watch.jsonl').read_text(encoding='utf-8').strip()
        self.assertIn(result['task_id'], journal)
        self.assertIn('"stage"', journal)


if __name__ == '__main__':
    unittest.main()
