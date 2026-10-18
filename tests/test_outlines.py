"""Step three and four: the volume outline and the chapter outline are settlement contracts.

v2 moved the drift judgement into the design stage. A volume outline declares every volume's
nodes, threads and terminal state; a chapter outline declares what each chapter changes
(resources, places, knowledge, characters, clock) together with the state it enters on and leaves
behind. The engine simulates the whole chain before a word is written, so every rejection below
happens at submit time, with the offending chapter and coordinate named.
"""
import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from novel_ledger import drift, planning, workflow
from novel_ledger.bootstrap import local_application as Application
from novel_ledger.contracts import Error, han_count
from novel_ledger.sqlite_store import SQLiteRepository
from support import (chapter_rows, contract, drive, response, seeded_book, volume_rows,
                     world_fixture)


def outlines(*chapters):
    """A chapter_outline receipt around the given rows."""
    return {'chapters': list(chapters)}


class VolumeOutlineTests(unittest.TestCase):
    def setUp(self):
        self.raw = contract(chapters=4, volumes=2)
        self.book = seeded_book(self.raw)
        self.contract = self.book['contract']
        self.world = self.book['world']
        self.state = self.book['state']
        self.rows = volume_rows(self.book, ['v1', 'v2'])

    def submit(self, rows, wanted=('v1', 'v2')):
        return drift.validate_volume_outline({'volumes': rows}, self.contract, self.world,
                                             {}, {}, list(wanted), self.state)

    def assertRejected(self, criterion, rows, wanted=('v1', 'v2')):
        with self.assertRaises(Error) as caught:
            self.submit(rows, wanted)
        self.assertEqual(caught.exception.code, 'design_drift')
        criteria = {finding['criterion'] for finding in caught.exception.details['findings']}
        self.assertIn(criterion, criteria, str(caught.exception.details['findings'])[:400])
        return caught.exception

    def test_a_volume_outline_covers_the_dispatched_volumes_in_contract_order(self):
        report = self.submit(self.rows)
        self.assertEqual(sorted(report), ['v1', 'v2'])
        self.assertEqual(report['v1']['id'], 'v1')
        self.assertEqual(report['v1']['nodes'][0]['id'], 'n1')
        self.assertEqual(report['v2']['nodes'][-1]['window'], [4, 4])

    def test_each_volume_lands_in_the_policy_word_band(self):
        policy = self.contract['volume_outline']
        for row in self.rows:
            length = drift._deep_han({key: row.get(key) for key in drift.VOLUME_FIELDS})
            self.assertGreaterEqual(length, policy['words'] - policy['tolerance'])
            self.assertLessEqual(length, policy['words'] + policy['tolerance'])

    def test_a_short_volume_outline_is_rejected_by_length(self):
        short = copy.deepcopy(self.rows)
        short[0]['arc'] = '甲' * 100
        self.assertRejected('volume_length', short)

    def test_a_volume_outline_must_answer_exactly_the_dispatched_volumes(self):
        with self.assertRaises(Error) as caught:
            self.submit(self.rows[:1], wanted=('v1', 'v2'))
        self.assertEqual(caught.exception.code, 'volume_outline')

    def test_a_node_window_outside_its_volume_is_rejected(self):
        broken = copy.deepcopy(self.rows)
        broken[0]['nodes'][0]['window'] = [1, 4]
        self.assertRejected('volume_node', broken)

    def test_a_node_id_registered_by_another_volume_cannot_be_reused(self):
        broken = copy.deepcopy(self.rows)
        broken[1]['nodes'][0]['id'] = broken[0]['nodes'][0]['id']
        self.assertRejected('volume_node', broken)

    def test_a_cross_volume_thread_must_declare_continues(self):
        broken = copy.deepcopy(self.rows)
        broken[1]['threads'][0]['id'] = broken[0]['threads'][0]['id']
        self.assertRejected('volume_thread', broken)
        carried = copy.deepcopy(self.rows)
        carried[1]['threads'][0]['id'] = carried[0]['threads'][0]['id']
        carried[1]['threads'][0]['continues'] = True
        report = self.submit(carried)
        self.assertTrue(report['v2']['threads'][0]['continues'])

    def test_a_resource_the_world_and_state_do_not_know_is_rejected(self):
        broken = copy.deepcopy(self.rows)
        broken[0]['resources'] = [{'key': '不存在的资源', 'from': 0, 'to': 1, 'reason': '工程样本。'}]
        self.assertRejected('volume_reference', broken)

    def test_an_unknown_place_or_character_is_rejected(self):
        broken = copy.deepcopy(self.rows)
        broken[0]['places'] = [{'entity': 'nobody', 'from': None, 'to': 'office', 'reason': '工程样本。'}]
        self.assertRejected('volume_reference', broken)

    def test_scope_all_states_every_volume_in_one_dispatch(self):
        job = workflow.next_volume_outline(self.book, self.contract)
        self.assertEqual(job.stage, 'volume_outline')
        self.assertEqual(job.payload['volume_ids'], ['v1', 'v2'])
        self.assertEqual(job.scope, 'volumes')

    def test_scope_rolling_answers_one_volume_at_a_time(self):
        book = copy.deepcopy(self.book)
        book['contract']['volume_outline'] = {'scope': 'rolling', 'words': 1000, 'tolerance': 100}
        job = workflow.next_volume_outline(book, book['contract'])
        self.assertEqual(job.payload['volume_ids'], ['v1'])
        book['volumes_outline'] = {'v1': self.submit(self.rows[:1], wanted=('v1',))['v1']}
        job = workflow.next_volume_outline(book, book['contract'])
        self.assertEqual(job.payload['volume_ids'], ['v2'])


class ChapterOutlineTests(unittest.TestCase):
    """The enter/exit state chain: everything the design stage refuses before prose exists."""

    def setUp(self):
        self.raw = contract(chapters=4, volumes=2)
        self.book = seeded_book(self.raw)
        self.contract = self.book['contract']
        self.world = self.book['world']
        self.state = self.book['state']
        self.volume = self.contract['volumes'][0]
        self.volume_row = drift.validate_volume_outline(
            {'volumes': volume_rows(self.book, ['v1'])}, self.contract, self.world,
            {}, {}, ['v1'], self.state)['v1']
        self.rows = chapter_rows(self.book, self.volume, self.state)

    def submit(self, rows, state0=None):
        return drift.validate_chapter_outline(
            {'volume': self.volume['id'], 'chapters': rows},
            self.contract['chapter_outline'], self.volume, self.volume_row, self.world,
            self.state if state0 is None else state0)

    def assertRejected(self, criterion, rows):
        with self.assertRaises(Error) as caught:
            self.submit(rows)
        self.assertEqual(caught.exception.code, 'design_drift')
        criteria = {finding['criterion'] for finding in caught.exception.details['findings']}
        self.assertIn(criterion, criteria, str(caught.exception.details['findings'])[:400])
        return caught.exception

    def test_a_self_consistent_chain_is_accepted_and_normalized(self):
        rows = self.submit(self.rows)
        self.assertEqual([row['chapter'] for row in rows], [1, 2])
        self.assertEqual(rows[0]['clock'], {'advance_days': 1})
        self.assertTrue(rows[0]['enter'])
        self.assertEqual([item['kind'] for item in rows[0]['enter']],
                         [item['kind'] for item in rows[0]['exit']])

    def test_the_chain_leaves_the_state_the_deltas_declare(self):
        rows = self.submit(self.rows)
        state, findings = drift.simulate(rows, self.state, self.world, self.volume, self.volume_row)
        self.assertEqual(findings, [])
        self.assertEqual(state['clock'], 2)
        self.assertEqual(state['resources'], {'["shen","车费","元"]': '2'})

    def test_a_chapter_must_cover_the_volume_from_its_start_to_the_last_chapter(self):
        with self.assertRaises(Error) as caught:
            self.submit(self.rows[:-1])
        self.assertEqual(caught.exception.code, 'chapter_outline')

    def test_the_synopsis_must_land_in_the_policy_band(self):
        short = copy.deepcopy(self.rows)
        short[0]['synopsis'] = '甲' * 70       # band is 150±60, so 70 is a drift, not a style choice
        self.assertRejected('chapter_length', short)

    def test_an_enter_that_disagrees_with_the_previous_exit_is_rejected(self):
        broken = copy.deepcopy(self.rows)
        broken[1]['enter'][0]['expected'] = 99
        self.assertRejected('drift_chain', broken)

    def test_an_exit_that_is_not_enter_plus_the_deltas_is_rejected(self):
        broken = copy.deepcopy(self.rows)
        broken[0]['exit'][1]['expected'] = '办公室'
        self.assertRejected('drift_chain', broken)

    def test_a_resource_cannot_go_negative(self):
        broken = copy.deepcopy(self.rows)
        broken[0]['resources'][0]['to'] = -1
        self.assertRejected('drift_resource', broken)

    def test_a_backwards_clock_is_rejected(self):
        broken = copy.deepcopy(self.rows)
        broken[0]['clock'] = {'advance_days': -1}
        self.assertRejected('drift_shape', broken)

    def test_an_unregistered_place_is_rejected(self):
        broken = copy.deepcopy(self.rows)
        broken[0]['places'][0]['to'] = '不存在的后院'
        self.assertRejected('drift_place', broken)

    def test_a_resource_from_that_does_not_match_the_chain_is_rejected(self):
        broken = copy.deepcopy(self.rows)
        broken[1]['resources'][0]['from'] = 4
        self.assertRejected('drift_chain', broken)

    def test_a_node_cannot_be_advanced_twice(self):
        book = seeded_book(self.raw)
        book['contract']['narrative_tracking'] = True
        book = seeded_book(book['contract'])
        volume = book['contract']['volumes'][0]
        volume_row = drift.validate_volume_outline(
            {'volumes': volume_rows(book, ['v1'])}, book['contract'], book['world'],
            {}, {}, ['v1'], book['state'])['v1']
        rows = chapter_rows(book, volume, book['state'])
        rows[1]['plot']['nodes'] = copy.deepcopy(rows[0]['plot']['nodes'])
        with self.assertRaises(Error) as caught:
            drift.validate_chapter_outline({'volume': 'v1', 'chapters': rows},
                                           book['contract']['chapter_outline'], volume,
                                           volume_row, book['world'], book['state'])
        criteria = {finding['criterion'] for finding in caught.exception.details['findings']}
        self.assertIn('drift_node', criteria)

    def test_a_node_outside_the_volume_outline_is_rejected(self):
        broken = copy.deepcopy(self.rows)
        broken[0]['plot']['nodes'] = [{'node': 'n99', 'after': 'resolved', 'outcome': '工程样本。'}]
        self.assertRejected('chapter_node', broken)

    def test_a_world_ref_that_does_not_exist_is_rejected(self):
        broken = copy.deepcopy(self.rows)
        broken[0]['world_refs'] = ['geography:missing']
        self.assertRejected('chapter_world', broken)

    def test_a_delta_array_may_be_empty_and_an_absent_one_reads_as_empty(self):
        empty = chapter_rows(self.book, self.volume, self.state, resources=False)
        self.assertEqual(empty[0]['resources'], [])
        self.assertEqual([item['kind'] for item in empty[0]['enter'] if item['kind'] == 'resources'], [])
        self.submit(empty)                       # "nothing of this kind changes" is a legal claim
        absent = copy.deepcopy(empty)
        for row in absent:
            row.pop('resources')
        # The engine treats an absent array as the same declaration rather than inventing an
        # increment: the chain is still checked, it just has less to check.
        self.submit(absent)

    def test_the_volume_close_lands_on_the_declared_terminals(self):
        broken = copy.deepcopy(self.volume_row)
        broken['resources'] = [{'key': '["shen","车费","元"]', 'from': 4, 'to': 1,
                                'reason': '卷末资源结余。'}]
        with self.assertRaises(Error) as caught:
            drift.validate_chapter_outline({'volume': 'v1', 'chapters': self.rows},
                                           self.contract['chapter_outline'], self.volume,
                                           broken, self.world, self.state)
        criteria = {finding['criterion'] for finding in caught.exception.details['findings']}
        self.assertIn('drift_closure', criteria)

    def test_a_repair_batch_anchors_on_the_state_the_book_is_actually_in(self):
        # The book has already written chapter 1: the live state is chapter 1's exit state.
        live, _ = drift.simulate(self.rows[:1], self.state, self.world, self.volume, None)
        tail = self.submit(copy.deepcopy(self.rows), state0=live)
        # Chapter 1 is a stale prefix now; the validator returns the suffix it anchored on.
        self.assertEqual([row['chapter'] for row in tail], [2])
        _, findings = drift.simulate(tail, live, self.world, self.volume, self.volume_row)
        self.assertEqual(findings, [])

    def test_scope_all_builds_every_volume_up_front(self):
        book = copy.deepcopy(self.book)
        book['contract']['chapter_outline'] = {'scope': 'all', 'words': 150, 'tolerance': 60}
        book['contract'] = planning.validate_contract(book['contract'])
        job = workflow.next_chapter_outline(book, book['contract'], book['contract']['volumes'][0],
                                            ahead=True)
        self.assertEqual(job.stage, 'chapter_outline')
        self.assertEqual(job.payload['volume'], 'v1')
        book['chapter_outlines'] = {'v1': chapter_rows(book, book['contract']['volumes'][0],
                                                       book['state'])}
        job = workflow.next_chapter_outline(book, book['contract'], book['contract']['volumes'][0],
                                            ahead=True)
        self.assertEqual(job.payload['volume'], 'v2')


class ChapterOutlineDispatchTests(unittest.TestCase):
    """The dispatch path: what the engine installs and what it refuses to write prose without."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = SQLiteRepository.initialize(Path(self.temp.name) / 'book',
                                                seeded_book(contract(chapters=2, volumes=1)))
        self.app = Application(self.repo)

    def tearDown(self):
        self.repo.close()
        self.temp.cleanup()

    def test_a_chapter_outline_is_installed_as_the_settlement_rows(self):
        drive(self.app, until='chapter_outline')
        work = self.repo.pending()['input']
        self.assertEqual(self.repo.read_document(work['records']['world_model'])['premise'],
                         world_fixture()['premise'])
        self.app.submit(response(self.app))
        book = self.repo.load()
        self.assertEqual(sorted(book['chapter_outlines']), ['v1'])
        self.assertEqual([row['chapter'] for row in book['chapter_outlines']['v1']], [1, 2])
        self.assertEqual(sorted(book['plans'], key=int), ['1', '2'])
        self.assertEqual(book['plans']['1']['clock'], {'advance_days': 1})
        self.assertEqual(book['state']['clock'], 0)

    def test_a_rejected_chapter_outline_leaves_the_book_untouched(self):
        drive(self.app, until='chapter_outline')
        before = copy.deepcopy(self.repo.load())
        broken = response(self.app)
        broken['data']['chapters'][0]['clock'] = {'advance_days': -1}
        with self.assertRaises(Error) as caught:
            self.app.submit(broken)
        self.assertEqual(caught.exception.code, 'design_drift')
        self.assertEqual(self.repo.load(), before)

    def test_the_writer_receives_its_own_chapter_outline_and_the_volume_row(self):
        drive(self.app, until='write')
        work = self.repo.pending()['input']
        self.assertIn('chapter_outline', work['required'])
        self.assertIn('volume_outline', work['required'])
        chapter = self.repo.read_document(work['records']['chapter_outline'])
        volume = self.repo.read_document(work['records']['volume_outline'])
        self.assertEqual(chapter['chapter'], 1)
        self.assertEqual(volume['id'], 'v1')
        self.assertEqual(chapter['enter'], self.repo.load()['plans']['1']['enter'])

    def test_no_word_is_written_without_a_registered_chapter_outline(self):
        drive(self.app, until='chapter_outline')
        self.app.submit(response(self.app))
        book = self.repo.load()
        self.assertEqual(sorted(book['plans']), ['1', '2'])
        book['plans'] = {}
        self.repo.save(book)
        handoff = self.app.advance()
        self.assertEqual(handoff['task']['stage'], 'chapter_outline')

    def test_the_policy_band_is_read_from_the_contract(self):
        raw = contract(chapters=2, volumes=1, chapter_words=80, chapter_tolerance=10)
        repo = SQLiteRepository.initialize(Path(self.temp.name) / 'narrow', seeded_book(raw))
        app = Application(repo)
        try:
            drive(app, until='chapter_outline')
            valid = response(app)
            length = han_count(valid['data']['chapters'][0]['synopsis'])
            self.assertEqual(length, 80)
            too_short = copy.deepcopy(valid)
            too_short['data']['chapters'][0]['synopsis'] = '甲' * 60
            with self.assertRaises(Error) as caught:
                app.submit(too_short)
            self.assertEqual(caught.exception.code, 'design_drift')
        finally:
            repo.close()


class ProvenanceTests(unittest.TestCase):
    """The outline chain reads the world, never invents a coordinate the world does not have."""

    def test_the_seeded_world_grounds_the_chapter_refs(self):
        book = seeded_book(contract())
        refs = chapter_rows(book, book['contract']['volumes'][0], book['state'])[0]['world_refs']
        self.assertTrue(refs)
        for ref in refs:
            section, ident = ref.split(':', 1)
            self.assertIn(ident, {row['id'] for row in book['world'][section]})

    def test_an_unseeded_world_leaves_refs_empty_instead_of_inventing_them(self):
        book = workflow.new_book(contract())
        rows = chapter_rows(book, book['contract']['volumes'][0], book['state'])
        self.assertEqual(rows[0]['world_refs'], [])

    def test_state_carries_every_delta_kind_as_an_array(self):
        book = seeded_book(contract())
        row = chapter_rows(book, book['contract']['volumes'][0], book['state'])[0]
        for field in ('resources', 'places', 'knowledge', 'characters'):
            self.assertIsInstance(row[field], list)
        self.assertIsInstance(row['clock'], dict)
        self.assertIsInstance(row['enter'], list)
        self.assertIsInstance(row['exit'], list)


if __name__ == '__main__':
    unittest.main()
