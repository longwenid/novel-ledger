"""Public behavior and shared-rule regressions for the architecture repairs."""
import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from novel_ledger import context, drift, facts, planning, spatial, workflow
from novel_ledger.bootstrap import local_application as Application
from novel_ledger.contracts import Error, digest, policy_default
from novel_ledger.sqlite_store import SQLiteRepository
from support import contract, drive, response, seeded_book


class PolicyTests(unittest.TestCase):
    def test_explicit_invalid_policies_are_not_silently_defaulted(self):
        for key in ('volume_outline', 'chapter_outline'):
            for invalid in ({}, None, [], False, '', {'scope': 'all'}):
                with self.subTest(key=key, invalid=invalid):
                    raw = contract()
                    raw[key] = invalid
                    with self.assertRaises(Error):
                        workflow.new_book(raw)
                    book = seeded_book(contract())
                    book['contract'][key] = invalid
                    with self.assertRaises(Error):
                        (workflow.volume_policy if key == 'volume_outline' else workflow.chapter_policy)(book)

    def test_missing_policies_default_and_rolling_selects_the_entering_volume(self):
        raw = contract(4, 2)
        for key in ('volume_outline', 'chapter_outline'):
            del raw[key]
        validated = planning.validate_contract(raw)
        for key in ('volume_outline', 'chapter_outline'):
            self.assertEqual(validated[key], policy_default(key))
        validated['volume_outline']['scope'] = 'rolling'
        book = seeded_book(validated)
        job = workflow.next_volume_outline(book, book['contract'])
        self.assertEqual(job.payload['volume_ids'], ['v1'])

    def test_incompatible_multi_volume_policies_are_rejected_before_dispatch(self):
        raw = contract(4, 2)
        raw['volume_outline']['scope'] = 'rolling'
        raw['chapter_outline']['scope'] = 'all'
        with self.assertRaises(Error) as caught:
            workflow.new_book(raw)
        self.assertEqual(caught.exception.code, 'outline_policy')
        book = seeded_book(contract(4, 2))
        book['contract'] = raw
        with self.assertRaises(Error):
            workflow.choose(book, [])



class SharedTransitionsTests(unittest.TestCase):
    def setUp(self):
        raw = contract(4)
        raw.update(narrative_tracking=True, editorial_features=True)
        self.book = seeded_book(raw)
        self.state = self.book['state']
        spatial.settle(self.state, {'op': 'link', 'id': 'gate', 'a': 'office', 'b': 'yard',
                                   'kind': 'path', 'directed': True, 'min_days': 2})
        self.row = {'chapter': 1, 'plot': {'nodes': [], 'threads': []}, 'hooks': [],
                    'resources': [], 'knowledge': [], 'characters': [],
                    'places': [{'entity': 'shen', 'from': 'office', 'to': 'yard',
                                'links': ['gate'], 'depart': 0, 'arrive': 2, 'reason': '赴后院核对。'}],
                    'clock': {'advance_days': 2},
                    'enter': [{'kind': 'places', 'key': 'shen', 'expected': 'office'},
                              {'kind': 'clock', 'key': 'main', 'expected': 0}],
                    'exit': [{'kind': 'places', 'key': 'shen', 'expected': 'yard'},
                             {'kind': 'clock', 'key': 'main', 'expected': 2}]}
        self.quote = '两天后，沈桐来到后院核对记录。'

    def reconcile(self, row):
        items = []
        for entry in drift._planned(row):
            kind = entry['kind']
            actual = {'advance_days': 2} if kind == 'clock' else {'from': 'office', 'to': 'yard'}
            items.append({'kind': kind, 'key': entry['key'], 'planned': entry['planned'],
                          'actual': actual, 'status': 'kept', 'reason': '赴后院核对。',
                          'evidence': {'chapter': 1, 'quote': self.quote}})
        return drift.reconcile({'items': items, 'unplanned': [], 'verdict': 'clean'},
                               row, self.state, self.book['world'])

    def test_design_and_prose_use_the_same_travel_clock_and_arrival_rules(self):
        before = copy.deepcopy(self.state)
        simulated, findings = drift.simulate([self.row], before, self.book['world'])
        self.assertEqual(findings, [])
        result = self.reconcile(self.row)
        self.assertEqual(result['findings'], [])
        settled, _ = facts.settle(before, result['events'], self.quote, 1)
        for field in ('placements', 'arrivals', 'clock', 'resources'):
            self.assertEqual(simulated[field], settled[field])
        self.assertEqual(self.state, before)
        self.assertEqual(settled['arrivals']['shen'], 2)

    def test_invalid_paths_are_rejected_in_design_and_reconciliation(self):
        for scenario in ('closed', 'requires', 'duration', 'half_time', 'wrong_direction', 'no_path', 'custody'):
            with self.subTest(scenario=scenario):
                state = copy.deepcopy(self.state)
                row = copy.deepcopy(self.row)
                if scenario == 'closed':
                    self.state['links']['gate']['open'] = False
                elif scenario == 'requires':
                    self.state['links']['gate']['requires'] = {'shen:permit': True}
                elif scenario == 'duration':
                    row['places'][0]['arrive'] = 1
                elif scenario == 'half_time':
                    del row['places'][0]['arrive']
                elif scenario == 'wrong_direction':
                    self.state['links']['gate'].update(a='yard', b='office')
                elif scenario == 'no_path':
                    row['places'][0].pop('links')
                else:
                    self.state['entities']['carrier'] = {'id': 'carrier', 'name': '携带者', 'kind': 'person'}
                    self.state['placements']['carrier'] = 'office'
                    self.state['custody']['shen'] = 'carrier'
                simulated, findings = drift.simulate([row], self.state, self.book['world'])
                self.assertTrue(any(f['criterion'] == 'drift_place' for f in findings), scenario)
                self.assertEqual(simulated['placements'], self.state['placements'])
                self.assertTrue(any(f['criterion'] == 'drift_place' for f in self.reconcile(row)['findings']))
                self.state = state

    def test_simulation_does_not_waive_prose_evidence(self):
        result = self.reconcile(self.row)
        with self.assertRaises(Error):
            facts.settle(self.state, result['events'], '正文没有这条引文。', 1)
        events = copy.deepcopy(result['events'])
        for event in events:
            event['evidence'] = {'chapter': 1, 'quote': '沈桐核对记录。'}
        with self.assertRaises(Error) as caught:
            facts.settle(self.state, events, '沈桐核对记录。', 1)
        self.assertEqual(caught.exception.code, 'time_evidence')

    def test_due_promises_are_checked_at_each_simulated_chapter_boundary(self):
        row = copy.deepcopy(self.row)
        row['hooks'] = [{'hook': 'promise', 'action': 'plant', 'note': '当章应兑现。'}]
        outline = {'hooks': [{'id': 'promise', 'text': '交代来源。', 'plant': [1, 1],
                              'payoff': [1, 1], 'required': False, 'continues': False}]}
        _, findings = drift.simulate([row], self.state, self.book['world'], volume_outline=outline)
        self.assertTrue(any(f['criterion'] == 'drift_deadline' for f in findings))
        event = {'op': 'hook', 'id': 'promise', 'status': 'open', 'before': None, 'due': 1,
                 'text': '交代来源。', 'evidence': {'chapter': 1, 'quote': self.quote}}
        with self.assertRaises(Error) as caught:
            facts.settle(self.state, [event], self.quote, 1)
        self.assertEqual(caught.exception.code, 'hook_due')



class NarrowReplanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = SQLiteRepository.initialize(Path(self.temp.name) / 'book', seeded_book(contract(4)))
        self.app = Application(self.repo)
        self.owner = self.app.run(through=4, source='工程夹具授权。')['owner']
        drive(self.app, self.owner, until='write')
        self.original = copy.deepcopy(self.repo.load()['chapter_outlines']['v1'])
        result = response(self.app)
        resource = next(r for r in result['data']['drift_check']['items'] if r['kind'] == 'resources')
        resource.update(status='deviated', actual={'from': 4, 'to': 5}, reason='核对后多领车费。')
        result['data']['drift_check']['verdict'] = 'deviated'
        self.app.submit(result)
        step = self.app.advance(owner=self.owner)
        if step['action'] == 'await_author':
            self.app.approve(step['prose_hash'], '夹具认可。', self.owner)
            step = self.app.advance(owner=self.owner)
        self.assertEqual(step['task']['stage'], 'chapter_outline')
        work = self.repo.pending()['input']
        self.assertEqual(self.repo.read_document(work['records']['prior_chapter_outlines']), self.original[1:])

    def tearDown(self):
        self.repo.close()
        self.temp.cleanup()

    def repair(self, reconnect=True):
        result = response(self.app)
        row = copy.deepcopy(self.original[1])
        row['resources'][0]['from'] = 5
        next(e for e in row['enter'] if e['kind'] == 'resources')['expected'] = 5
        if not reconnect:
            row['resources'][0]['to'] = 4
            next(e for e in row['exit'] if e['kind'] == 'resources')['expected'] = 4
        result['data'] = {'volume': 'v1', 'through_chapter': 2, 'chapters': [row]}
        return result

    def test_reconnects_one_chapter_and_preserves_the_suffix_exactly(self):
        before = digest(self.repo.load())
        self.app.check(self.repair())
        self.assertEqual(digest(self.repo.load()), before)
        self.app.submit(self.repair())
        rows = self.repo.load()['chapter_outlines']['v1']
        self.assertEqual(rows[0], self.original[0])
        self.assertEqual(rows[2:], self.original[2:])
        self.assertEqual(rows[1]['resources'][0]['from'], 5)
        drive(self.app, self.owner)
        self.assertEqual(len(self.repo.headers('main')), 4)

    def test_incompatible_retained_suffix_is_rejected_without_mutation(self):
        before = digest(self.repo.load())
        with self.assertRaises(Error) as caught:
            self.app.submit(self.repair(False))
        self.assertEqual(caught.exception.code, 'design_drift')
        self.assertEqual(digest(self.repo.load()), before)
        self.assertIsNotNone(self.repo.pending())

    def test_repair_receipts_cannot_move_the_frozen_range(self):
        """A repair answers the frozen anchor range exactly: skipping the anchor or naming a
        different end is refused, and the book is never mutated by the attempt."""
        skipped = self.repair()
        skipped['data']['from_chapter'] = 3
        for end in (None, True, 1, 5):
            with self.subTest(end=end):
                payload = copy.deepcopy(skipped)
                if end is not None:
                    payload['data']['through_chapter'] = end
                before = digest(self.repo.load())
                with self.assertRaises(Error):
                    self.app.submit(payload)
                self.assertEqual(digest(self.repo.load()), before)


class VolumeMaterialTests(unittest.TestCase):
    def test_dependency_closure_preserves_whole_records_and_source(self):
        outline = {'id': 'v', 'arc': '完整卷内走向', 'style': {'trend': '由紧转缓'},
                   'nodes': [{'id': 'old', 'line': 'a', 'window': [1, 1], 'depends_on': []},
                             {'id': 'now', 'line': 'b', 'window': [3, 3], 'depends_on': ['old']},
                             {'id': 'future', 'line': 'c', 'window': [9, 9], 'depends_on': []}],
                   'threads': [{'id': 'a'}, {'id': 'b'}, {'id': 'c'}],
                   'hooks': [{'id': 'promise', 'text': '原文承诺'}]}
        before = copy.deepcopy(outline)
        view = context.writing_volume_outline(outline, {'node_ids': ['now']}, 3, digest(outline))
        self.assertEqual([n['id'] for n in view['nodes']], ['old', 'now'])
        self.assertEqual(view['nodes'], outline['nodes'][:2])
        self.assertEqual([t['id'] for t in view['threads']], ['a', 'b'])
        self.assertEqual(view['hooks'], outline['hooks'])
        self.assertEqual(view['source']['hash'], digest(outline))
        self.assertEqual(outline, before)

    def test_writer_can_read_the_frozen_full_volume_on_demand(self):
        with tempfile.TemporaryDirectory() as directory:
            raw = contract(20)
            raw['narrative_tracking'] = True
            repo = SQLiteRepository.initialize(Path(directory) / 'book', seeded_book(raw))
            try:
                app = Application(repo)
                drive(app, until='write')
                work = repo.pending()['input']
                full_hash = work['records']['complete_volume_outline']
                full = repo.read_document(full_hash)
                scoped = repo.read_document(work['records']['volume_outline'])
                self.assertNotIn('complete_volume_outline', work['required'])
                self.assertIn('volume_outline', work['required'])
                self.assertEqual(full, repo.load()['volumes_outline']['v1'])
                self.assertEqual(scoped['source']['hash'], full_hash)
                self.assertEqual(work['payload']['volume_outline'], scoped)
                self.assertLess(len(scoped['nodes']), len(full['nodes']))
            finally:
                repo.close()


if __name__ == '__main__':
    unittest.main()
