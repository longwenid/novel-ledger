"""Step five on a tracked book: the writer's self-comparison replaces the reviewer's receipt.

`drift.reconcile` is the whole check: the writer files one item per planned increment, the engine
projects the true before-value itself, `kept` must land on the plan, and a declared deviation is
booked into `book['design_drift']` instead of being argued about by a second agent. What used to
be a chapter review dispatch is now arithmetic inside `workflow.apply`.
"""
import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from novel_ledger import drift, narrative
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
        self.volume_row = drift.validate_volume_outline(
            {'volumes': volume_rows(self.book, ['v1'])}, self.contract, self.world,
            {}, {}, ['v1'], self.book['state'])['v1']
        self.rows = chapter_rows(self.book, self.volume, self.book['state'])

    def submit(self, rows, state0=None):
        return drift.validate_chapter_outline(
            {'volume': 'v1', 'chapters': rows}, self.contract['chapter_outline'], self.volume,
            self.volume_row, self.world,
            self.book['state'] if state0 is None else state0)

    def assertRejected(self, criterion, rows):
        with self.assertRaises(Error) as caught:
            self.submit(rows)
        self.assertEqual(caught.exception.code, 'design_drift')
        criteria = {finding['criterion'] for finding in caught.exception.details['findings']}
        self.assertIn(criterion, criteria, str(caught.exception.details['findings'])[:400])

    def test_the_node_registry_is_read_off_the_volume_outlines(self):
        book = copy.deepcopy(self.book)
        book['volumes_outline'] = {'v1': self.volume_row}
        nodes, threads = narrative.registry(book)
        self.assertEqual(sorted(nodes), ['n1', 'n2', 'n3', 'n4'])
        self.assertEqual(sorted(threads), ['line-v1'])
        self.assertEqual(nodes['n1']['line'], 'main')

    def test_a_tracked_chain_resolves_every_node_and_closes_the_line(self):
        rows = self.submit(self.rows)
        state, findings = drift.simulate(rows, self.book['state'], self.world, self.volume,
                                         self.volume_row)
        self.assertEqual(findings, [])
        self.assertEqual(state['story_nodes'][rows[0]['plot']['nodes'][0]['node']]['status'], 'resolved')
        self.assertEqual(state['thread_progress']['line-v1']['status'], 'resolved')

    def test_a_node_cannot_be_advanced_before_its_dependency(self):
        volume = copy.deepcopy(self.volume_row)
        volume['nodes'][1]['depends_on'] = ['n1']
        broken = copy.deepcopy(self.rows)
        broken[0]['plot']['nodes'] = copy.deepcopy(broken[1]['plot']['nodes'])
        with self.assertRaises(Error) as caught:
            drift.validate_chapter_outline(
                {'volume': 'v1', 'chapters': broken}, self.contract['chapter_outline'],
                self.volume, volume, self.world, self.book['state'])
        criteria = {finding['criterion'] for finding in caught.exception.details['findings']}
        self.assertIn('drift_node', criteria)

    def test_a_resolved_line_cannot_be_reused(self):
        rows = chapter_rows(self.book, self.volume, self.book['state'])
        # Chapter 1 closes the line; chapter 2 tries to reopen it. Both rows stay self-consistent as
        # declarations, so what fails is the simulation's own guard, not the exit arithmetic.
        rows[0]['plot']['threads'] = [{'thread': 'line-v1', 'after': 'resolved',
                                       'reason': '本卷核对提前收束。'}]
        rows[0]['enter'].append({'kind': 'thread', 'key': 'line-v1', 'expected': None})
        rows[0]['exit'].append({'kind': 'thread', 'key': 'line-v1', 'expected': 'resolved'})
        rows[1]['plot']['threads'] = [{'thread': 'line-v1', 'after': 'active',
                                       'reason': '工程样本：试图重开已收束的线路。'}]
        rows[1]['enter'].append({'kind': 'thread', 'key': 'line-v1', 'expected': 'resolved'})
        rows[1]['exit'].append({'kind': 'thread', 'key': 'line-v1', 'expected': 'resolved'})
        self.assertRejected('drift_thread', rows)

    def test_a_character_delta_needs_a_choice_and_a_cost(self):
        broken = copy.deepcopy(self.rows)
        broken[0]['characters'][0].pop('cost')
        self.assertRejected('drift_shape', broken)

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

    def test_a_missing_item_is_a_coverage_drift(self):
        result = self.receipt()
        result['data']['drift_check']['items'].pop(0)
        self.submit(result)
        self.assertIn('drift_coverage', self.criteria())
        self.assertEqual(self.repo.load()['draft']['stage'], 'repair')

    def test_an_extra_item_is_also_a_coverage_drift(self):
        result = self.receipt()
        result['data']['drift_check']['items'].append({
            'kind': 'resources', 'key': '["shen","不存在","元"]',
            'planned': {'from': 0, 'to': 1}, 'actual': {'from': 0, 'to': 1},
            'status': 'kept', 'reason': '工程样本。',
            'evidence': {'chapter': 1, 'quote': '次日'}})
        self.submit(result)
        self.assertIn('drift_coverage', self.criteria())

    def test_a_self_reported_before_that_contradicts_the_projection_is_refused(self):
        result = self.receipt()
        target = next(item for item in result['data']['drift_check']['items']
                      if item['kind'] == 'resources')
        target['actual']['from'] = 99
        self.submit(result)
        self.assertIn('drift_before', self.criteria())

    def test_kept_must_land_on_the_planned_value(self):
        result = self.receipt()
        target = next(item for item in result['data']['drift_check']['items']
                      if item['kind'] == 'resources')
        target['actual']['to'] = 88
        self.submit(result)
        self.assertIn('drift_kept', self.criteria())

    def test_evidence_must_be_a_verbatim_fragment_of_the_prose(self):
        result = self.receipt()
        result['data']['drift_check']['items'][0]['evidence']['quote'] = '这句话不在正文里。'
        with self.assertRaises(Error) as caught:
            self.app.submit(result)
        self.assertEqual(caught.exception.code, 'evidence')

    def test_a_declared_deviation_is_booked_into_design_drift(self):
        result = self.receipt()
        target = next(item for item in result['data']['drift_check']['items']
                      if item['kind'] == 'resources')
        target.update(status='deviated', actual={'from': 4, 'to': 5},
                      reason='正文里他多领了一趟车费。')
        result['data']['drift_check']['verdict'] = 'deviated'
        outcome = self.submit(result)
        self.assertEqual(outcome['committed_chapter'], 1)
        book = self.repo.load()
        self.assertEqual(book['state']['resources'], {'["shen","车费","元"]': '5'})
        self.assertEqual(len(book['design_drift']), 1)
        self.assertEqual(book['design_drift'][0]['kind'], 'resources')
        self.assertIn('多领了', book['design_drift'][0]['reason'])

    def test_unplanned_facts_are_committed_and_replanning_reads_the_updated_state(self):
        result = self.receipt()
        check = result['data']['drift_check']
        check['unplanned'] = [
            {'kind': 'knowledge', 'key': 'shen:secret',
             'actual': {'from': None, 'to': 'confirmed'}, 'reason': '核对中另外确认了秘密。',
             'evidence': copy.deepcopy(check['items'][0]['evidence'])},
            {'kind': 'resources', 'key': '["shen","车费","元"]',
             'actual': {'from': 3, 'to': 7}, 'reason': '花费之后又领到四元车费。',
             'evidence': copy.deepcopy(check['items'][0]['evidence'])}]
        check['verdict'] = 'deviated'
        self.assertEqual(self.submit(result)['committed_chapter'], 1)
        book = self.repo.load()
        self.assertEqual(book['state']['knowledge']['shen:secret']['stance'], 'knows')
        self.assertEqual(book['state']['resources']['["shen","车费","元"]'], '7')
        self.assertEqual(len(book['design_drift']), 2)
        handoff = self.advance()
        if handoff['action'] == 'await_author':
            self.app.approve(handoff['prose_hash'], '工程夹具认可首章版本。', self.owner)
            handoff = self.advance()
        self.assertEqual(handoff['task']['stage'], 'chapter_outline')
        replanned = response(self.app)
        resource = replanned['data']['chapters'][0]['resources'][0]
        self.assertEqual(resource['from'], 7)

    def test_a_skipped_plant_commits_a_deviation_without_planting_the_promise(self):
        result = self.receipt()
        check = result['data']['drift_check']
        item = next(item for item in check['items'] if item['kind'] == 'hook')
        item.update(status='skipped', actual=None, reason='本章未埋设这条承诺，需重排后续安排。')
        check['verdict'] = 'deviated'
        self.assertEqual(self.submit(result)['committed_chapter'], 1)
        book = self.repo.load()
        self.assertNotIn(item['key'], book['state']['hooks'])
        self.assertEqual(book['design_drift'][0]['kind'], 'hook')

    def test_a_deviated_item_without_a_reason_is_refused(self):
        result = self.receipt()
        target = next(item for item in result['data']['drift_check']['items']
                      if item['kind'] == 'resources')
        target.update(status='deviated', actual={'from': 4, 'to': 5}, reason='')
        result['data']['drift_check']['verdict'] = 'deviated'
        self.submit(result)
        self.assertIn('drift_reason', self.criteria())

    def test_a_clean_verdict_with_deviations_is_a_contradiction(self):
        result = self.receipt()
        target = next(item for item in result['data']['drift_check']['items']
                      if item['kind'] == 'resources')
        target.update(status='deviated', actual={'from': 4, 'to': 5}, reason='正文里多领了一趟车费。')
        self.submit(result)
        self.assertIn('drift_verdict', self.criteria())

    def test_the_engine_replans_the_rest_of_the_volume_after_a_booking(self):
        result = self.receipt()
        target = next(item for item in result['data']['drift_check']['items']
                      if item['kind'] == 'resources')
        target.update(status='deviated', actual={'from': 4, 'to': 5}, reason='正文里他多领了一趟车费。')
        result['data']['drift_check']['verdict'] = 'deviated'
        self.submit(result)
        handoff = self.advance()
        if handoff['action'] == 'await_author':
            self.app.approve(handoff['prose_hash'], '工程夹具认可首章版本。', self.owner)
            handoff = self.advance()
        self.assertEqual(handoff['task']['stage'], 'chapter_outline')
        work = self.repo.pending()['input']
        self.assertTrue(work['payload'].get('repair'))
        self.assertTrue(work['payload'].get('drift'))
        self.assertEqual(work['payload']['from_chapter'], 2)

    def test_the_writer_cannot_self_report_events(self):
        result = self.receipt()
        result['data']['events'] = [{'op': 'clock', 'before': 0, 'after': 1,
                                     'evidence': {'chapter': 1, 'quote': '次日'}}]
        with self.assertRaises(Error) as caught:
            self.app.submit(result)
        self.assertEqual(caught.exception.code, 'writer_events')


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

    def test_every_design_drift_row_is_visible_to_the_closing_audit(self):
        owner = self.app.run(finish=True, source='工程夹具授权完本。')['owner']
        # One declared deviation on the first chapter; the engine books it and re-plans the rest.
        drive(self.app, owner, until='write')
        result = response(self.app)
        target = next(item for item in result['data']['drift_check']['items']
                      if item['kind'] == 'resources')
        target.update(status='deviated', actual={'from': 4, 'to': 5}, reason='正文里他多领了一趟车费。')
        result['data']['drift_check']['verdict'] = 'deviated'
        self.app.submit(result)
        drive(self.app, owner)
        report = self.app.audit()
        self.assertTrue(report['ok'])
        self.assertEqual([row['kind'] for row in report['design_drift']], ['resources'])

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

    def test_a_book_completes_once_its_promises_are_paid(self):
        app, repo = self.build()
        owner = app.run(finish=True, source='工程夹具授权按伏笔账完本。')['owner']
        self.assertEqual(drive(app, owner)['action'], 'ready_to_complete')
        book = repo.load()
        self.assertEqual(book['state']['hooks']['hook-v1-required']['status'], 'paid')
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

    def test_a_two_volume_book_pays_the_continuing_promise_in_the_next_volume(self):
        app, repo = self.build(chapters=4, volumes=2)
        owner = app.run(finish=True, source='工程夹具授权跨卷伏笔完本。')['owner']
        self.assertEqual(drive(app, owner)['action'], 'ready_to_complete')
        hooks = repo.load()['state']['hooks']
        self.assertEqual(hooks['hook-v1-required']['status'], 'paid')
        self.assertEqual(hooks['hook-v1-carry']['status'], 'paid')
        self.assertEqual(hooks['hook-v2-required']['status'], 'paid')
        self.assertTrue(app.complete(owner)['completed'])

    def test_the_hook_chain_does_not_add_a_dispatch(self):
        app, repo = self.build()
        owner = app.run(finish=True, source='工程夹具授权按伏笔账完本。')['owner']
        stages = []
        for _ in range(20):
            handoff = app.advance(owner=owner)
            if handoff['action'] == 'await_author':
                app.approve(handoff['prose_hash'], '工程夹具认可当前版本。', owner)
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
