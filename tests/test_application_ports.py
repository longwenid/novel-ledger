"""Run the real application through replaceable ports without a filesystem or database."""
import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from novel_ledger.application import Application
from novel_ledger import context, workflow, store_keys
from novel_ledger.contracts import Error, digest, policy_default
from novel_ledger.ports import Repository
from memory_repository import MemoryRepository
from support import contract, drive, prose_stub, response


class MemoryPresentation:
    """A replaceable delivery channel that records effects instead of writing files."""

    def __init__(self):
        self.effects = []

    def task(self, task, baseline=None, compact=False, preserve_result=False):
        self.effects.append(('task', task['id']))
        return {'task_id': task['id'], 'input_hash': task['input_hash'],
                'stage': task['input']['stage'], 'chapter': task['input']['chapter'],
                'baseline': copy.deepcopy(baseline), 'compact': compact,
                'delivery_id': 'memory:task/' + task['id']}

    def revision_path(self, plan_hash):
        return 'memory:revision/' + plan_hash

    def revision(self, plan):
        self.effects.append(('revision', copy.deepcopy(plan)))
        return {'delivery_id': self.revision_path(plan['plan_hash'])}

    def world(self):
        self.effects.append(('world',))
        return {'delivery_id': 'memory:world'}

    def book(self):
        self.effects.append(('book',))
        return {'delivery_id': 'memory:book'}

    def board(self, board):
        self.effects.append(('board', board.get('hash')))
        return {'delivery_id': 'memory:board/' + str(board.get('hash'))}

    def retire(self, task_id):
        self.effects.append(('retire', task_id))


class ControlledRuntime:
    def __init__(self):
        self.now = 1000.0
        self.sequence = 0

    def clock(self):
        return self.now

    def new_id(self):
        self.sequence += 1
        return 'runtime-' + str(self.sequence)


class ApplicationPortsTests(unittest.TestCase):
    def test_fast_continuation_works_with_memory_ports_without_file_or_database_access(self):
        app, repo, _, _, _ = self.make_app(chapters=6)
        with patch('builtins.open', side_effect=AssertionError('Application attempted filesystem I/O.')):
            owner = app.run(finish=True, mode='fast')['owner']
            drive(app, owner, until='write')
            app.submit(response(app))
            step = app.advance(owner=owner)
            app.approve(step['prose_hash'], '作者认可首章。', owner)
            task = app.advance(owner=owner)['task']
            lease = app.claim(task['task_id'], 'memory-worker')
            for chapter in range(2, 7):
                receipt = response(app)
                receipt.update(session='memory-worker', execution_claim=lease['token'])
                result = app.submit(receipt)
                self.assertEqual(result['committed_chapter'], chapter)
                if result['worker_boundary'] == 'continue':
                    step = app.continue_writing(task['task_id'], 'memory-worker', lease['token'])
                    task, lease = step['task'], {'token': step['execution_claim']}
            self.assertEqual(app.advance(owner=owner)['action'], 'ready_to_complete')
            self.assertTrue(app.complete(owner)['completed'])

    def make_app(self, preparing=False, chapters=3):
        book = workflow.preparing_book('作者准备导入完整约定。') if preparing else workflow.new_book(contract(chapters))
        repo = MemoryRepository(book)
        presentation = MemoryPresentation()
        runtime = ControlledRuntime()
        compiled = []

        def compile_task(current, job):
            compiled.append(job.stage)
            return context.build(repo, current, job)

        app = Application(repo, compile_task=compile_task, presentation=presentation,
                          clock=runtime.clock, new_id=runtime.new_id)
        return app, repo, presentation, runtime, compiled

    def assertCode(self, code, fn, *args, **kwargs):
        with self.assertRaises(Error) as caught:
            fn(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)

    def test_full_lifecycle_can_replace_every_environment_adapter(self):
        app, repo, presentation, runtime, compiled = self.make_app(preparing=True)
        self.assertIs(type(app), Application)
        self.assertFalse(hasattr(repo, 'project'))
        self.assertFalse(hasattr(repo, 'db'))
        with patch('builtins.open', side_effect=AssertionError('Application attempted filesystem I/O.')):
            app.recontract(contract(3), '作者导入完整开书约定。', opening=True)
            self.assertEqual(app.advance()['task']['stage'], 'volume_outline')
            app.submit(response(app))
            self.assertEqual(app.advance()['task']['stage'], 'chapter_outline')
            app.submit(response(app))
            owner = app.run(finish=True, source='作者明确授权写完。')['owner']
            self.assertEqual(owner, 'runtime-1')
            self.assertEqual(drive(app, owner)['action'], 'ready_to_complete')
            completed = app.complete(owner)
            self.assertEqual(completed['chapters'], 3)
            self.assertTrue(app.audit()['ok'])
            self.assertEqual(repo.load()['completed_at'], runtime.now)
            self.assertTrue(app.complete(owner)['idempotent'])
            manifest = {'snapshot_hash': completed['snapshot_hash'],
                        'chapters': [{'chapter': r['n'], 'prose_hash': r['prose']} for r in repo.headers('main')],
                        'files': [{'path': 'memory:completed-book', 'content_hash': digest('exported book')}]}
            self.assertTrue(app.record_delivery(manifest)['recorded'])
            recorded = repo.get('completion_delivery')
            self.assertEqual(recorded, manifest)
            self.assertCode('completion', app.record_delivery, {**manifest, 'snapshot_hash': 'obsolete'})
            self.assertEqual(repo.get('completion_delivery'), recorded)
            self.assertCode('delivery', app.record_delivery, {**manifest, 'chapters': manifest['chapters'][:-1]})
            self.assertEqual(repo.get('completion_delivery'), recorded)
            self.assertCode('delivery', app.record_delivery, {**manifest, 'files': []})
            self.assertEqual(repo.get('completion_delivery'), recorded)
            frozen = repo.history_snapshot('main')
            self.assertEqual([p['n'] for _, p in repo.history_pages(frozen, before=3)], [2, 1])
            # Each committed chapter's settlement events are searchable: v2 writes one event per
            # declared delta (clock, resource, place, knowledge) instead of a reviewer's receipt.
            memory = repo.memory_rows(next(repo.history_pages(frozen))[1])
            self.assertGreaterEqual(len(memory), 1)
            self.assertIn('clock', {row['op'] for row in memory})
            self.assertGreaterEqual(app.usage()['tasks'], 5)
        self.assertTrue({'volume_outline', 'chapter_outline', 'write'} <= set(compiled))
        self.assertFalse({'chapter_review', 'book_plan', 'volume_plan', 'plan'} & set(compiled))
        self.assertTrue(any(effect[0] == 'task' for effect in presentation.effects))

    def test_preview_of_a_real_chapter_commit_restores_every_store_and_emits_no_effect(self):
        app, repo, presentation, _, _ = self.make_app(chapters=2)
        owner = app.run(finish=True, source='工程验证执笔提交事务。')['owner']
        drive(app, owner, until='write')
        receipt = response(app, session='preview-worker')
        before, effects = repo.snapshot(), copy.deepcopy(presentation.effects)
        result = app.check(receipt, session='preview-worker')
        self.assertTrue(result['checked'])
        self.assertFalse(result['accepted'])
        # A preview answers two different questions, and says so: the receipt itself is valid,
        # while nothing was committed. A worker must not have to infer validity from a missing error.
        self.assertTrue(result['valid'])
        self.assertFalse(result['committed'])
        self.assertEqual(result['committed_chapter'], 1)
        self.assertEqual(repo.snapshot(), before)
        self.assertEqual(presentation.effects, effects)
        app.submit(receipt)
        self.assertEqual(len(repo.headers('main')), 1)
        self.assertEqual(repo.task(receipt['task_id'])['status'], 'done')


    def test_check_uses_explicit_session_and_controlled_identity_and_clock(self):
        app, repo, _, runtime, _ = self.make_app()
        pending = app.advance()['task']['task_id']
        candidate = response(app, session='declared-worker')
        before = repo.snapshot()
        self.assertCode('session', app.check, candidate, session='different-worker')
        self.assertEqual(repo.snapshot(), before)
        candidate.pop('session')
        checked = app.check(candidate, session='explicit-worker')
        self.assertEqual(checked['session_used'], 'explicit-worker')
        self.assertEqual(repo.snapshot(), before)
        self.assertIsNone(repo.session_task('explicit-worker'))

        lease = app.claim(pending, 'claimed-worker', seconds=30)
        self.assertEqual(lease['token'], 'runtime-1')
        self.assertEqual(lease['until'], 1030.0)
        runtime.now = 1031.0
        expired = response(app, session='claimed-worker', claim=lease['token'])
        self.assertCode('worker_lease', app.submit, expired)
        self.assertEqual(repo.task(pending)['status'], 'pending')
        renewed = app.claim(pending, 'claimed-worker', seconds=30)
        self.assertEqual(renewed['until'], 1061.0)
        app.submit(expired)
        self.assertEqual(repo.task(pending)['status'], 'done')

    def test_worker_activity_renews_the_lease_while_silence_still_expires_it(self):
        app, repo, _, runtime, _ = self.make_app()
        pending = app.advance()['task']['task_id']
        lease = app.claim(pending, 'claimed-worker', seconds=30)
        candidate = response(app, session='claimed-worker', claim=lease['token'])
        # 25s in, the lease is still valid: a successful check is a heartbeat and extends it by
        # the lease's own granted span (30s here — never the global default), so a slow repair
        # loop that keeps calling the engine never runs out of lease.
        runtime.now = 1025.0
        app.check(candidate, session='claimed-worker')
        self.assertEqual(repo.get(store_keys.claim(pending))['until'], 1055.0)
        # Past the original 1030 expiry, the renewed lease still admits the same receipt.
        runtime.now = 1031.0
        app.submit(candidate)
        self.assertEqual(repo.task(pending)['status'], 'done')

    def test_receipt_assembly_passes_preflight_without_model_plumbing(self):
        app, repo, _, runtime, _ = self.make_app()
        drive(app, until='write')
        pending = repo.pending()
        outcome = app.draft_receipt(pending['id'], prose_stub(pending['input']['chapter']),
                                    {'title': '封条' + str(pending['input']['chapter']),
                                     'summary': '沈桐要求核对退件来源。',
                                     'self_check': '逐项按章纲比对，动作与证据均在正文中，无计划外变化。'})
        self.assertEqual(outcome['missing'], [])
        self.assertEqual(outcome['quotes_unlocated'], [])
        receipt = outcome['receipt']
        items = receipt['data']['drift_check']['items']
        self.assertGreaterEqual(len(items), 4)
        for item in items:
            self.assertEqual(item['status'], 'kept')
            self.assertTrue(item['evidence']['quote'], item['kind'])
            if item['kind'] in ('resources', 'places', 'knowledge', 'characters'):
                self.assertIn('from', item['actual'])
        preview = app.check(receipt, session='assembler')
        self.assertTrue(preview['valid'], preview.get('findings'))
        receipt['session'] = 'assembler'
        app.submit(receipt)
        self.assertEqual(repo.task(pending['id'])['status'], 'done')

    def test_every_worker_entry_renews_and_a_widened_grant_is_never_narrowed(self):
        app, repo, _, runtime, _ = self.make_app()
        drive(app, until='write')
        pending = repo.pending()['id']
        lease = app.claim(pending, 'widened-worker', seconds=7200)
        receipt = response(app, session='widened-worker', claim=lease['token'])
        runtime.now = 1500.0                       # deep inside the widened grant
        app.check(receipt, session='widened-worker')
        self.assertEqual(repo.get(store_keys.claim(pending))['until'], 1500.0 + 7200)
        # Preflight enters submit directly, without check() around it: it renews on its own.
        runtime.now = 1501.0
        app.submit(receipt, preview=True)
        self.assertEqual(repo.get(store_keys.claim(pending))['until'], 1501.0 + 7200)
        # A material read carrying the token is the drafting worker's heartbeat.
        runtime.now = 1502.0
        app.read(pending, claim=lease['token'])
        self.assertEqual(repo.get(store_keys.claim(pending))['until'], 1502.0 + 7200)

    def test_single_delivery_stages_default_to_the_long_lease(self):
        design, _, _, _, _ = self.make_app()
        outline = design.advance()['task']['task_id']   # volume_outline: one long silent receipt
        lease = design.claim(outline, 'design-worker')
        self.assertEqual(lease['seconds'], policy_default('single_delivery_lease_seconds'))
        self.assertEqual(lease['until'], 1000.0 + policy_default('single_delivery_lease_seconds'))
        app, _, _, _, _ = self.make_app()
        drive(app, until='write')
        short = app.claim(app.repo.pending()['id'], 'prose-worker')
        self.assertEqual(short['seconds'], policy_default('worker_lease_seconds'))
        self.assertEqual(short['until'], 1000.0 + policy_default('worker_lease_seconds'))

    def test_memory_adapter_implements_the_entire_application_repository_port(self):
        _, repo, _, _, _ = self.make_app()
        methods = {name for base in Repository.__mro__ for name, value in vars(base).items()
                   if not name.startswith('_') and callable(value)}
        self.assertTrue(methods)
        self.assertTrue(all(callable(getattr(repo, name, None)) for name in methods))
        detached = repo.load_part('settings')
        detached['contract']['title'] = '修改读取副本'
        self.assertEqual(repo.load()['contract']['title'], '夜班退件')


if __name__ == '__main__':
    unittest.main()
