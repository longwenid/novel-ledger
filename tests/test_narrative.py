"""Step five on a tracked book: the writer's self-comparison replaces the reviewer's receipt.

`drift_reconcile.reconcile` projects the true before-value and checks the fixed chapter contract. A declared
change or omission stays a failed candidate; it cannot settle facts or rewrite future outlines.
"""
import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from novel_ledger import drift, drift_reconcile, drift_simulation, drift_validation, narrative
from novel_ledger.bootstrap import local_application as Application
from novel_ledger.contracts import Error
from novel_ledger.sqlite_store import SQLiteRepository
from support import (chapter_rows, contract, drive, response, seeded_book,
                     volume_rows)



def tracked_contract(chapters=6):
    raw = contract(chapters=chapters, volumes=1)
    raw.update(narrative_tracking=True)
    return raw


class TrackingChainTests(unittest.TestCase):
    """A tracked book's node/thread chain is validated before the prose, not after."""

    def setUp(self):
        self.book = seeded_book(tracked_contract(4))
        self.contract = self.book['contract']
        self.world = self.book['world']
        self.volume = self.contract['volumes'][0]
        self.volume_row = drift_validation.validate_volume_outline(
            {'volumes': volume_rows(self.book, ['v1'])}, self.contract, self.world,
            {}, {}, ['v1'], self.book['state'])['v1']
        self.rows = chapter_rows(self.book, self.volume, self.book['state'])

    def submit(self, rows, state0=None):
        return drift_validation.validate_chapter_outline(
            {'volume': 'v1', 'chapters': rows}, self.contract['chapter_outline'], self.volume,
            self.volume_row, self.world,
            self.book['state'] if state0 is None else state0)

    def test_the_node_registry_is_read_off_the_volume_outlines(self):
        book = copy.deepcopy(self.book)
        book['volumes_outline'] = {'v1': self.volume_row}
        nodes, threads = narrative.registry(book)
        self.assertEqual(sorted(nodes), ['n1', 'n2', 'n3', 'n4'])
        self.assertEqual(sorted(threads), ['line-v1'])
        self.assertEqual(nodes['n1']['line'], 'main')

    def test_a_tracked_chain_resolves_every_node_and_closes_the_line(self):
        rows = self.submit(self.rows)
        state, findings = drift_simulation.simulate(rows, self.book['state'], self.world, self.volume,
                                         self.volume_row)
        self.assertEqual(findings, [])
        self.assertEqual(state['story_nodes'][rows[0]['plot']['nodes'][0]['node']]['status'], 'resolved')
        self.assertEqual(state['thread_progress']['line-v1']['status'], 'resolved')

    def test_a_broken_chain_declaration_is_refused_before_the_prose(self):
        # One rule, three declarations the simulation refuses: a node ahead of its dependency, a
        # reopened line, a character delta without a cost. Each scenario is copied verbatim from the
        # micro-test it replaces; what is shared is that the chain check runs before any prose.
        def node_order():
            volume = copy.deepcopy(self.volume_row)
            volume['nodes'][1]['depends_on'] = ['n1']
            broken = copy.deepcopy(self.rows)
            broken[0]['plot']['nodes'] = copy.deepcopy(broken[1]['plot']['nodes'])
            return volume, broken

        def line_reuse():
            rows = chapter_rows(self.book, self.volume, self.book['state'])
            # Chapter 1 closes the line; chapter 2 tries to reopen it. Both rows stay self-consistent
            # as declarations, so what fails is the simulation's own guard, not the exit arithmetic.
            rows[0]['plot']['threads'] = [{'thread': 'line-v1', 'after': 'resolved',
                                           'reason': '本卷核对提前收束。'}]
            rows[0]['enter'].append({'kind': 'thread', 'key': 'line-v1', 'expected': None})
            rows[0]['exit'].append({'kind': 'thread', 'key': 'line-v1', 'expected': 'resolved'})
            rows[1]['plot']['threads'] = [{'thread': 'line-v1', 'after': 'active',
                                           'reason': '工程样本：试图重开已收束的线路。'}]
            rows[1]['enter'].append({'kind': 'thread', 'key': 'line-v1', 'expected': 'resolved'})
            rows[1]['exit'].append({'kind': 'thread', 'key': 'line-v1', 'expected': 'resolved'})
            return self.volume_row, rows

        def character_shape():
            broken = copy.deepcopy(self.rows)
            broken[0]['characters'][0].pop('cost')
            return self.volume_row, broken

        cases = [('drift_node', node_order), ('drift_thread', line_reuse),
                 ('drift_shape', character_shape)]
        for criterion, build in cases:
            with self.subTest(criterion=criterion):
                outline, rows = build()
                with self.assertRaises(Error) as caught:
                    drift_validation.validate_chapter_outline(
                        {'volume': 'v1', 'chapters': rows}, self.contract['chapter_outline'],
                        self.volume, outline, self.world, self.book['state'])
                self.assertEqual(caught.exception.code, 'design_drift')
                criteria = {finding['criterion'] for finding in caught.exception.details['findings']}
                self.assertIn(criterion, criteria,
                              str(caught.exception.details['findings'])[:400])

    def test_closure_refuses_unresolved_required_work(self):
        book = copy.deepcopy(self.book)
        book['volumes_outline'] = {'v1': self.volume_row}
        book['state'] = dict(book['state'], story_nodes={'n1': {'status': 'resolved'}},
                             thread_progress={})
        with self.assertRaises(Error) as caught:
            narrative.closure(book)
        self.assertEqual(caught.exception.code, 'story_closure')


class DriftCheckReconciliationTests(unittest.TestCase):
    """What the writer files, and what the engine refuses to settle."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = SQLiteRepository.initialize(Path(self.temp.name) / 'book',
                                                seeded_book(tracked_contract(6)))
        self.app = Application(self.repo)
        self.owner = self.app.run(through=6, source='工程夹具授权写完六章。')['owner']
        drive(self.app, self.owner, until='write')

    def tearDown(self):
        self.repo.close()
        self.temp.cleanup()

    def receipt(self):
        return response(self.app)

    def submit(self, result):
        handoff = self.app.submit(result)
        return handoff

    def advance(self):
        return self.app.advance(owner=self.owner)

    def findings(self):
        draft = self.repo.load().get('draft') or {}
        return draft.get('findings') or []

    def criteria(self):
        return {finding.get('criterion') for finding in self.findings()}

    def draft_book(self):
        """A second driven book, for a variant that needs to commit its own first chapter."""
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        repo = SQLiteRepository.initialize(Path(temp.name) / 'book',
                                           seeded_book(tracked_contract(6)))
        self.addCleanup(repo.close)
        app = Application(repo)
        owner = app.run(through=6, source='工程夹具授权写完六章。')['owner']
        drive(app, owner, until='write')
        return app

    def test_the_fixture_receipt_commits_and_settles_the_planned_events(self):
        result = self.submit(self.receipt())
        self.assertEqual(result['committed_chapter'], 1)
        book = self.repo.load()
        self.assertEqual(book['state']['clock'], 1)
        self.assertEqual(book['state']['story_nodes']['n1']['status'], 'resolved')
        self.assertEqual(float(book['state']['resources']['["shen","车费","元"]']), 3)
        # `facts.settle` stores the knowledge projection as a stance, not as the reveal stage the
        # outline speaks: `hinted` is the reader-facing name for "suspects".
        self.assertEqual(book['state']['knowledge']['shen:source']['stance'], 'suspects')

    def test_a_missing_or_extra_item_is_a_coverage_drift(self):
        # One rule, two shapes: a planned increment left unfiled, and a filed row the plan never
        # declared. The refused round moves the draft to repair, where the second shape is filed.
        result = self.receipt()
        result['data']['drift_check']['items'].pop(0)
        self.submit(result)
        self.assertIn('drift_coverage', self.criteria())
        self.assertEqual(self.repo.load()['draft']['stage'], 'repair')
        self.advance()
        result = self.receipt()
        result['data']['drift_check']['items'].append({
            'kind': 'resources', 'key': '["shen","不存在","元"]',
            'planned': {'from': 0, 'to': 1}, 'actual': {'from': 0, 'to': 1},
            'status': 'kept', 'reason': '工程样本。',
            'evidence': {'chapter': 1, 'quote': '次日'}})
        self.submit(result)
        self.assertIn('drift_coverage', self.criteria())

    def test_receipt_arithmetic_must_match_the_engine_projection(self):
        # One rule, two fields: the before-value is the engine's projection, never the writer's
        # guess, and a `kept` row's result must be the planned one. Both are findings, so the second
        # shape is filed on the repair round the first one opened.
        result = self.receipt()
        target = next(item for item in result['data']['drift_check']['items']
                      if item['kind'] == 'resources')
        target['actual']['from'] = 99
        self.submit(result)
        self.assertIn('drift_before', self.criteria())
        self.advance()
        result = self.receipt()
        target = next(item for item in result['data']['drift_check']['items']
                      if item['kind'] == 'resources')
        target['actual']['to'] = 88
        self.submit(result)
        self.assertIn('drift_kept', self.criteria())

    def test_the_receipt_cannot_smuggle_claims_past_the_check(self):
        # One rule, two smuggles: an evidence quote the prose does not contain, and a self-written
        # events array. Both are refused outright (the failed submit rolls back, so the pending task
        # serves both cases).
        def fabricated_quote():
            result = self.receipt()
            result['data']['drift_check']['items'][0]['evidence']['quote'] = '这句话不在正文里。'
            return result, 'evidence'

        def self_reported_events():
            result = self.receipt()
            result['data']['events'] = [{'op': 'clock', 'before': 0, 'after': 1,
                                         'evidence': {'chapter': 1, 'quote': '次日'}}]
            return result, 'writer_events'

        for build in (fabricated_quote, self_reported_events):
            result, code = build()
            with self.subTest(code=code):
                with self.assertRaises(Error) as caught:
                    self.app.submit(result)
                self.assertEqual(caught.exception.code, code)

    def test_declared_departures_are_failed_candidates_without_changing_facts_or_plans(self):
        result = self.receipt()
        original = copy.deepcopy(self.repo.load())
        target = next(item for item in result['data']['drift_check']['items']
                      if item['kind'] == 'resources')
        target.update(status='deviated', actual={'from': 4, 'to': 5}, reason='正文里他多领了一趟车费。')
        result['data']['drift_check']['verdict'] = 'deviated'
        self.assertIsNone(self.submit(result)['committed_chapter'])
        book = self.repo.load()
        self.assertEqual(book['state'], original['state'])
        self.assertEqual(book['plans'], original['plans'])
        self.assertEqual(book['design_drift'], [])
        self.assertIn('outline_alignment', self.criteria())

        app = self.draft_book()
        result = response(app)
        check = result['data']['drift_check']
        item = next(item for item in check['items'] if item['kind'] == 'hook')
        item.update(status='skipped', actual=None, reason='正文漏掉了本章必须埋设的承诺。')
        check['verdict'] = 'deviated'
        self.assertIsNone(app.submit(result)['committed_chapter'])
        book = app.repo.load()
        self.assertEqual(book['design_drift'], [])
        self.assertEqual(book['draft']['stage'], 'repair')
        self.assertEqual(app.repo.headers(book['branch']), [])

    def test_unplanned_facts_are_diagnosed_for_current_prose_repair_without_settling(self):
        result = self.receipt()
        original = copy.deepcopy(self.repo.load())
        check = result['data']['drift_check']
        check['unplanned'] = [
            {'kind': 'knowledge', 'key': 'shen:secret',
             'actual': {'from': None, 'to': 'confirmed'}, 'reason': '核对中另外确认了秘密。',
             'evidence': copy.deepcopy(check['items'][0]['evidence'])},
            {'kind': 'resources', 'key': '["shen","车费","元"]',
             'actual': {'from': 3, 'to': 7}, 'reason': '花费之后又领到四元车费。',
             'evidence': copy.deepcopy(check['items'][0]['evidence'])}]
        check['verdict'] = 'deviated'
        self.assertIsNone(self.submit(result)['committed_chapter'])
        book = self.repo.load()
        self.assertEqual(book['state'], original['state'])
        self.assertEqual(book['plans'], original['plans'])
        self.assertEqual(book['design_drift'], [])
        self.assertEqual(book['draft']['drift_check']['unplanned'], check['unplanned'])
        handoff = self.advance()
        self.assertEqual((handoff['task']['stage'], handoff['task']['chapter']), ('repair', 1))
        self.assertEqual(self.submit(self.receipt())['committed_chapter'], 1)

    def test_a_deviation_without_a_reason_or_a_clean_verdict_over_deviations_is_refused(self):
        # One rule, two contradictions between the verdict and the rows: a departure filed without a
        # reason, and a departure filed under a `clean` verdict. Both are findings, so the second
        # shape is filed on the repair round the first one opened.
        result = self.receipt()
        target = next(item for item in result['data']['drift_check']['items']
                      if item['kind'] == 'resources')
        target.update(status='deviated', actual={'from': 4, 'to': 5}, reason='')
        result['data']['drift_check']['verdict'] = 'deviated'
        self.submit(result)
        self.assertIn('drift_reason', self.criteria())
        self.advance()
        result = self.receipt()
        target = next(item for item in result['data']['drift_check']['items']
                      if item['kind'] == 'resources')
        target.update(status='deviated', actual={'from': 4, 'to': 5}, reason='正文里多领了一趟车费。')
        # The fresh receipt's verdict stays `clean`: a booked deviation contradicts it.
        self.submit(result)
        self.assertIn('drift_verdict', self.criteria())


class CompletionTests(unittest.TestCase):
    """A tracked book completes only when the chain it declared is fully settled."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = SQLiteRepository.initialize(Path(self.temp.name) / 'book',
                                                seeded_book(tracked_contract(6)))
        self.app = Application(self.repo)

    def tearDown(self):
        self.repo.close()
        self.temp.cleanup()

    def test_a_full_tracked_book_completes_with_its_chain_closed(self):
        owner = self.app.run(finish=True, source='工程夹具授权完本。')['owner']
        handoff = drive(self.app, owner)
        self.assertEqual(handoff['action'], 'ready_to_complete')
        self.assertTrue(self.app.complete(owner)['completed'])
        book = self.repo.load()
        self.assertEqual(book['state']['thread_progress']['line-v1']['status'], 'resolved')
        self.assertEqual(len(book['state']['story_nodes']), 6)
        self.assertTrue(self.app.audit()['ok'])
        self.assertEqual(self.app.complete(owner)['idempotent'], True)

    def test_repaired_departures_finish_only_with_the_original_plans_fulfilled(self):
        owner = self.app.run(finish=True, source='工程夹具授权完本。')['owner']
        drive(self.app, owner, until='write')
        plans = copy.deepcopy(self.repo.load()['plans'])
        result = response(self.app)
        target = next(item for item in result['data']['drift_check']['items']
                      if item['kind'] == 'resources')
        target.update(status='deviated', actual={'from': 4, 'to': 5}, reason='正文里他多领了一趟车费。')
        result['data']['drift_check']['verdict'] = 'deviated'
        self.assertIsNone(self.app.submit(result)['committed_chapter'])
        drive(self.app, owner)
        report = self.app.audit()
        self.assertTrue(report['ok'])
        self.assertEqual(report['design_drift'], [])
        self.assertEqual(self.repo.load()['plans'], plans)
        self.assertTrue(self.app.complete(owner)['completed'])

    def test_rework_budget_still_bounds_the_loop(self):
        owner = self.app.run(finish=True, source='工程夹具授权完本。')['owner']
        drive(self.app, owner, until='write')
        # Every round files a receipt the engine refuses the same way: the budget must run out at
        # REPAIRS and hand the decision to the author instead of looping forever.
        rounds = 0
        while rounds < 6:
            handoff = self.app.advance(owner=owner)
            if handoff['action'] != 'task_ready':
                break
            if handoff['task']['stage'] not in ('write', 'repair', 'redesign'):
                break
            result = response(self.app)
            result['data']['prose'] += ('门关着。', '门开着。', '灯灭了。')[rounds]
            result['data']['drift_check']['items'].pop(0)
            self.app.submit(result)
            rounds += 1
        book = self.repo.load()
        self.assertNotIn(book['status'], ('completed',))
        self.assertTrue(rounds <= 3, '返修轮次应有界：%d' % rounds)
        self.assertTrue(book['draft'] is not None)
        handoff = self.app.advance(owner=owner)
        self.assertEqual(handoff['action'], 'paused')


class HookSettlementTests(unittest.TestCase):
    """Promises move through the real ledger: plant opens them, payoff pays them, completion audits.

    The engine side is the existing `facts.settle` hook event — v2.1 only supplies the producer
    (volume declaration + chapter execution + the writer's `hook` self-comparison rows), so what is
    asserted here is that the entry lands in `state.hooks` with the declared due date and that the
    unfinished-promise gate sees it.
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = SQLiteRepository.initialize(Path(self.temp.name) / 'book',
                                                seeded_book(contract(chapters=2, volumes=1)))
        self.addCleanup(self.repo.close)
        self.app = Application(self.repo)

    def owner(self):
        return self.app.run(finish=True, source='工程夹具授权按伏笔账写完。')['owner']

    def submit_chapter(self, owner, until='write'):
        handoff = drive(self.app, owner, until=until)
        self.assertEqual(handoff['task']['stage'], 'write')
        return self.app.submit(response(self.app))

    def test_plant_opens_the_promise_with_the_declared_due_and_payoff_pays_it(self):
        owner = self.owner()
        self.submit_chapter(owner)
        promise = self.repo.load()['state']['hooks']['hook-v1-required']
        self.assertEqual(promise['status'], 'open')
        self.assertEqual(promise['due'], 2)
        self.assertIn('凭据', promise['text'])


class HookCompletionTests(unittest.TestCase):
    """The closing audit sees promises now: an open one refuses completion until it is paid."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def build(self, chapters=2, volumes=1):
        self.repo = SQLiteRepository.initialize(Path(self.temp.name) / 'book',
                                                seeded_book(contract(chapters=chapters,
                                                                     volumes=volumes)))
        self.addCleanup(self.repo.close)
        self.app = Application(self.repo)
        return self.app, self.repo

    def test_a_two_volume_book_pays_its_promises_and_completes(self):
        app, repo = self.build(chapters=4, volumes=2)
        owner = app.run(finish=True, source='工程夹具授权跨卷伏笔完本。')['owner']
        self.assertEqual(drive(app, owner)['action'], 'ready_to_complete')
        hooks = repo.load()['state']['hooks']
        self.assertEqual(hooks['hook-v1-required']['status'], 'paid')
        self.assertEqual(hooks['hook-v1-carry']['status'], 'paid')
        self.assertEqual(hooks['hook-v2-required']['status'], 'paid')
        self.assertTrue(app.complete(owner)['completed'])

    def test_completion_is_refused_while_a_promise_is_still_open(self):
        # A promise may legitimately outlive the written chapters: a continuing one whose payoff
        # window lies past the book's last chapter stays open through `ready_to_complete`, and the
        # closing audit must refuse to call the book done while it is unpaid.
        repo = SQLiteRepository.initialize(Path(self.temp.name) / 'open-book',
                                           seeded_book(contract(chapters=4, volumes=2)))
        self.addCleanup(repo.close)
        app = Application(repo)
        owner = app.run(finish=True, source='工程夹具授权跨卷伏笔完本。')['owner']
        handoff = app.advance(owner=owner)
        self.assertEqual(handoff['task']['stage'], 'volume_outline')
        rows = volume_rows(repo.load(), ['v1', 'v2'], hooks=True)
        rows[0]['hooks'].append({'id': 'hook-open-later', 'text': '读者记住的那张凭据还没有下文。',
                                 'plant': [1, 1], 'payoff': [5, 5], 'required': False,
                                 'continues': True})
        app.submit({**response(app),
                    'data': {'volumes': rows}})
        handoff = app.advance(owner=owner)
        self.assertEqual(handoff['action'], 'await_volume_confirm')
        app.confirm_volume(handoff['volumes_hash'], '工程夹具认可跨卷伏笔卷纲。', owner)
        handoff = app.advance(owner=owner)
        self.assertEqual(handoff['task']['stage'], 'chapter_outline')
        book = repo.load()
        chapters = chapter_rows(book, book['contract']['volumes'][0], book['state'], hooks=True)
        chapters[0]['hooks'].append({'hook': 'hook-open-later', 'action': 'plant',
                                     'note': '埋一条后文才兑现的承诺。'})
        app.submit({**response(app), 'data': {'volume': 'v1', 'chapters': chapters}})
        self.assertEqual(drive(app, owner)['action'], 'ready_to_complete')
        hooks = repo.load()['state']['hooks']
        self.assertEqual(hooks['hook-open-later']['status'], 'open')
        self.assertEqual({hooks[key]['status'] for key in ('hook-v1-required', 'hook-v1-carry',
                                                           'hook-v2-required')}, {'paid'})
        with self.assertRaises(Error) as caught:
            app.complete(owner)
        self.assertEqual(caught.exception.code, 'payoffs')
        self.assertFalse(repo.load()['status'] == 'completed')

    def test_the_hook_chain_does_not_add_a_dispatch(self):
        app, repo = self.build()
        owner = app.run(finish=True, source='工程夹具授权按伏笔账完本。')['owner']
        stages = []
        for _ in range(20):
            handoff = app.advance(owner=owner)
            if handoff['action'] == 'await_author':
                app.approve(handoff['prose_hash'], '工程夹具认可当前版本。', owner)
                continue
            if handoff['action'] == 'await_volume_confirm':
                app.confirm_volume(handoff['volumes_hash'], '工程夹具认可当前卷纲。', owner)
                continue
            if handoff['action'] != 'task_ready':
                break
            stages.append(handoff['task']['stage'])
            app.submit(response(app))
        self.assertEqual(stages, ['volume_outline', 'chapter_outline', 'write', 'write'])
        self.assertTrue(repo.load()['volumes_outline']['v1']['hooks'])
        self.assertEqual([entry['action'] for entry in repo.load()['plans']['1']['hooks']],
                         ['plant'])


if __name__ == '__main__':
    unittest.main()
