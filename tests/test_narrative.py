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
from support import chapter_rows, contract, drive, response, seeded_book, volume_rows


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


if __name__ == '__main__':
    unittest.main()
