"""Run the real application through replaceable ports without a filesystem or database."""
import copy
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, __file__.rsplit('/', 2)[0] + '/scripts')
from novel_ledger.application import Application
from novel_ledger import context, workflow, world
from novel_ledger.contracts import Error, RESULT, SCALE_TIERS, digest
from novel_ledger.ports import Repository
from memory_repository import MemoryRepository
from support import contract, drive, response


class MemoryPresentation:
    """A replaceable delivery channel that records effects instead of writing files."""

    def __init__(self):
        self.effects = []

    def task(self, task, baseline=None, compact=False):
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
            self.assertEqual(app.advance()['task']['stage'], 'contract_review')
            app.submit(response(app, session='opening-reviewer'))
            self.assertEqual(app.advance()['task']['stage'], 'book_plan')
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
            self.assertEqual(len(repo.memory_rows(next(repo.history_pages(frozen))[1])), 1)

            original = repo.headers('main')
            app.revise(2, '作者要求调整中章措辞。', owner, through=2)
            candidate = repo.load()['branch']
            self.assertNotEqual(candidate, 'main')
            self.assertEqual(repo.headers('main'), original)
            self.assertEqual(drive(app, owner)['action'], 'revision_ready')
            app.promote(owner)
            self.assertEqual(app.status()['formal_branch'], candidate)
            self.assertEqual(len(repo.headers(candidate)), 3)
            self.assertEqual(repo.headers('main'), original)
            self.assertEqual([p['n'] for _, p in repo.history_pages(frozen)], [3, 2, 1])
            app.run(finish=True, owner=owner, source='作者授权修订后完本。')
            self.assertEqual(drive(app, owner)['action'], 'ready_to_complete')
            app.complete(owner)
            self.assertTrue(app.audit()['ok'])

            app.revise(3, '尝试末章表达，保留可撤销候选。', owner)
            pending = app.advance(owner=owner)['task']['task_id']
            app.discard(owner)
            self.assertEqual(repo.task(pending)['status'], 'cancelled')
            self.assertEqual(app.status()['branch'], candidate)
            self.assertEqual(app.status()['status'], 'completed')
            self.assertIn(('retire', pending), presentation.effects)
            self.assertGreater(app.usage()['tasks'], 10)
        self.assertTrue({'contract_review', 'book_plan', 'volume_plan', 'plan', 'profiles',
                         'write', 'chapter_review', 'scope_review', 'scope_synthesis', 'repair'} <= set(compiled))
        self.assertTrue(any(effect[0] == 'task' for effect in presentation.effects))

    def test_guided_world_opening_delivers_through_the_injected_channel(self):
        app, repo, presentation, _, _ = self.make_app(preparing=True)
        repo.save(workflow.preparing_book('作者按当前开书协议提供完整方向。', guided=True, opening_version=2))
        tier = SCALE_TIERS[0]
        raw = contract(tier['chapter_window'][0], tier['volume_count'])
        raw.update({key: copy.deepcopy(tier[key]) for key in ('word_range', 'chapter_min', 'chapter_max', 'chapter_aim')})
        raw.update(tone='冷静而具体。', pov='第三人称限知，只写沈桐的所见所知。', theme='责任如何在人之间传递。', red_lines=[])
        values = {gate: {key: copy.deepcopy(raw[key]) for key in keys} for gate, keys in {
            'genre': ('genre', 'reader_promise', 'tone'), 'pov': ('pov',),
            'relationships': ('relationships',), 'engine': ('story_engine', 'opposition'),
            'ending': ('ending', 'theme'), 'voice': ('voice', 'style_traits'), 'title': ('title',)}.items()}
        values['protagonist'] = copy.deepcopy(raw['protagonist_setup'])
        values['scale'] = {'tier': tier['id']}
        values['world'] = {'world_premise': raw['world_premise'], 'red_lines': [], 'allow_special_mechanism': False,
                           'mechanism': {'mode': 'none', 'principle': '只有普通仓库规章。', 'cost': '违规须负责。', 'limits': []}}
        with patch('builtins.open', side_effect=AssertionError('Opening attempted filesystem I/O.')):
            app.intake(values, '作者确认这些具体开书方向。')
            app.advance()
            pending = repo.pending()
            opening = repo.load()['creation']
            model = {'selection_hash': opening['selection_hash'], 'premise': raw['world_premise'], 'story_capacity': '退件与责任持续引发冲突。'}
            for section, fields in world.SECTIONS.items():
                ident = 'shen' if section == 'characters' else {'rules': 'r1', 'geography': 'g1'}.get(section, section + '1')
                model[section] = [{'id': ident, **{field: '仓库中具体的' + field for field in fields}, 'links': []}]
            model['characters'][0].update(name='沈桐', desire=raw['protagonist_setup']['desire'], limit=raw['protagonist_setup']['limit'])
            model['rules'][0]['principle'] = raw['world_rules'][0]
            model['mechanisms'] = []
            app.submit({'schema': RESULT, 'task_id': pending['id'], 'input_hash': pending['input_hash'],
                        'session': 'world-creator', 'data': {**model, 'contract': raw}})
            self.assertEqual(app.advance()['task']['stage'], 'world_review')
            app.submit(response(app, session='world-reviewer'))
            self.assertEqual(app.advance()['task']['stage'], 'contract_review')
            app.submit(response(app, session='guided-contract-reviewer'))
            handoff = app.advance()
            self.assertEqual(handoff['action'], 'world_ready')
            self.assertEqual(handoff['world_view'], {'delivery_id': 'memory:world'})
            self.assertEqual(presentation.effects[-1], ('world',))
            self.assertEqual(repo.load()['creation']['phase'], 'ready')

    def test_blocked_revision_is_delivered_without_paths_or_file_access(self):
        app, repo, presentation, _, _ = self.make_app(chapters=6)
        owner = app.run(finish=True, source='作者授权六章工程样本。')['owner']
        with patch('builtins.open', side_effect=AssertionError('Revision attempted filesystem I/O.')):
            drive(app, owner, until='scope_synthesis')
            candidate = response(app, session='scope-defect-reviewer')
            data = candidate['data']
            criterion = data['checks'][0]['id']
            data['verdict'] = data['checks'][0]['result'] = 'fix'
            data['findings'] = [{'criterion': criterion, 'severity': 'quality', 'reason': '第二章表达需要调整。',
                                 'target_chapter': 2, 'repair_scope': 'local', 'evidence': {'chapter': 2, 'quote': '次日'}}]
            app.submit(candidate)
            original = repo.headers('main')
            app.revise(2, '按独立审稿调整第二章。', owner, through=2, changes={'mode': 'expression'})
            handoff = app.advance(owner=owner)
            self.assertEqual(handoff['action'], 'revision_blocked')
            plan = repo.load()['revision_directive']
            self.assertEqual(handoff['proposal']['plan_path'], 'memory:revision/' + plan['plan_hash'])
            self.assertEqual(presentation.effects[-1], ('revision', plan))
            self.assertEqual(repo.headers('main'), original)
            self.assertIsNone(repo.load()['revision_run'])

    def test_preview_of_a_real_chapter_commit_restores_every_store_and_emits_no_effect(self):
        app, repo, presentation, _, _ = self.make_app(chapters=2)
        owner = app.run(finish=True, source='工程验证写审事务。')['owner']
        drive(app, owner, until='chapter_review')
        receipt = response(app, session='review-preview')
        before, effects = repo.snapshot(), copy.deepcopy(presentation.effects)
        result = app.check(receipt, session='review-preview')
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

    def test_cancellation_effect_runs_only_after_commit_and_survives_callback_failure(self):
        app, repo, presentation, _, _ = self.make_app()
        pending = app.advance()['task']['task_id']
        before, effects = repo.snapshot(), copy.deepcopy(presentation.effects)
        original_save = repo.save

        def fail_save(book):
            raise RuntimeError('Injected persistence failure after cancellation.')

        repo.save = fail_save
        try:
            with self.assertRaisesRegex(RuntimeError, 'persistence failure'):
                app.set_lexical({'forbidden_terms': ['测试禁词']}, '作者修改规则。')
        finally:
            repo.save = original_save
        self.assertEqual(repo.snapshot(), before)
        self.assertEqual(presentation.effects, effects)
        self.assertEqual(repo.task(pending)['status'], 'pending')

        with repo.transaction(preview=True):
            app._cancel_pending('预览取消不能撤走交付。')
        self.assertEqual(repo.snapshot(), before)
        self.assertEqual(presentation.effects, effects)

        app.set_lexical({'forbidden_terms': ['测试禁词']}, '作者修改规则。')
        self.assertEqual(repo.task(pending)['status'], 'cancelled')
        self.assertEqual(presentation.effects[-1], ('retire', pending))
        self.assertEqual(presentation.effects.count(('retire', pending)), 1)

        pending = app.advance()['task']['task_id']
        with patch.object(presentation, 'retire', side_effect=OSError('Delivery channel unavailable.')):
            with self.assertRaisesRegex(OSError, 'Delivery channel'):
                app.pause('作者暂停并取消派工。', cancel=True)
        self.assertEqual(repo.task(pending)['status'], 'cancelled')
        self.assertEqual(app.status()['status'], 'paused')
        app.resume()
        self.assertEqual(app.advance()['task']['stage'], 'book_plan')

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
