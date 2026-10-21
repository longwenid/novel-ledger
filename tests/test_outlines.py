"""Step three and four: the volume outline and the chapter outline are settlement contracts.

v2 moved the drift judgement into the design stage. A volume outline declares every volume's
nodes, threads, promises and terminal state; a chapter outline declares what each chapter changes
(resources, places, knowledge, characters, clock) together with the promise actions it executes and
the state it enters on and leaves behind. The engine simulates the whole chain before a word is
written, so every rejection below happens at submit time, with the offending chapter/coordinate
named.
"""
import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from novel_ledger import creation, drift, planning, workflow
from novel_ledger.bootstrap import local_application as Application
from novel_ledger.contracts import DEFAULTS, Error
from novel_ledger.sqlite_store import SQLiteRepository
from support import (chapter_rows, contract, drive, response, seeded_book,
                     volume_rows, world_fixture)



def outlines(*chapters):
    """A chapter_outline receipt around the given rows."""
    return {'chapters': list(chapters)}


def ladder_value(scopes=('一城', '一界')):
    """An opening/5 格局 ladder value: the volume stages have to be these strings verbatim."""
    names = ('青云城', '青云界', '诸天之外')
    return {'scale': {'opening': '第一章只见一座仓库与一条夜班线。',
                      'terminal': '势力',
                      'unchanged': '跨卷不变的是登记制度本身。'},
            'ladder': [{'stage': names[index], 'scope': scope,
                        'growth': ('地盘', '规则', '文明')[index],
                        'new_rule': '第%d级起适用的新规则：登记与通行。' % (index + 1),
                        'cost': '升到第%d级要付出的代价：旧身份作废。' % (index + 1)}
                       for index, scope in enumerate(scopes)]}


def ladder_book(ladder=True):
    """A seeded book with an optional ladder declared by its current opening."""
    book = seeded_book(contract(chapters=4, volumes=2))
    if ladder:
        state = creation.begin('工程夹具：格局阶梯。')
        state['selections'] = [{'gate': 'ladder',
                                'option': {'id': 'A', 'title': '方案A', 'premise': '工程夹具。',
                                           'value': ladder_value()},
                                'source': '作者选它。'}]
        book['creation'] = state
    return book


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

    def test_node_windows_and_ids_are_volume_scoped(self):
        outside = copy.deepcopy(self.rows)
        outside[0]['nodes'][0]['window'] = [1, 4]
        self.assertRejected('volume_node', outside)
        reused = copy.deepcopy(self.rows)
        reused[1]['nodes'][0]['id'] = reused[0]['nodes'][0]['id']
        self.assertRejected('volume_node', reused)

    def test_a_cross_volume_thread_must_declare_continues(self):
        broken = copy.deepcopy(self.rows)
        broken[1]['threads'][0]['id'] = broken[0]['threads'][0]['id']
        self.assertRejected('volume_thread', broken)
        carried = copy.deepcopy(self.rows)
        carried[1]['threads'][0]['id'] = carried[0]['threads'][0]['id']
        carried[1]['threads'][0]['continues'] = True
        report = self.submit(carried)
        self.assertTrue(report['v2']['threads'][0]['continues'])

    def test_volume_references_must_exist_in_the_world_and_state(self):
        unknown_resource = copy.deepcopy(self.rows)
        unknown_resource[0]['resources'] = [{'key': '不存在的资源', 'from': 0, 'to': 1, 'reason': '工程样本。'}]
        self.assertRejected('volume_reference', unknown_resource)
        unknown_entity = copy.deepcopy(self.rows)
        unknown_entity[0]['places'] = [{'entity': 'nobody', 'from': None, 'to': 'office', 'reason': '工程样本。'}]
        self.assertRejected('volume_reference', unknown_entity)

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


class VolumeStageTests(unittest.TestCase):
    """opening/5 §6: the scale ladder lands on the volumes, verbatim and only climbing."""

    def test_the_stage_field_is_part_of_the_volume_row_shape(self):
        self.assertIn('stage', drift.VOLUME_FIELDS)
        self.assertEqual(drift.VOLUME_FIELDS[drift.VOLUME_FIELDS.index('purpose') + 1], 'stage')
        rows = volume_rows(seeded_book(contract(chapters=4, volumes=2)), ['v1', 'v2'])
        for row in rows:
            self.assertIn('stage', row)


    def test_a_declared_ladder_fills_the_stages_in_contract_order(self):
        book = ladder_book()
        choices = creation.selected(book['creation'])
        rungs = [row['stage'] for row in choices['ladder']['ladder']]
        rows = volume_rows(book, ['v1', 'v2'])
        self.assertEqual([row['stage'] for row in rows], rungs[:2])
        report = drift.validate_volume_outline({'volumes': rows}, book['contract'], book['world'],
                                               choices, {}, ['v1', 'v2'], book['state'])
        self.assertEqual([report['v1']['stage'], report['v2']['stage']], rungs[:2])

    def test_a_stage_that_is_not_the_next_ladder_rung_is_refused(self):
        """Stages come from the ladder verbatim and only climb: invented or descending pairs are out."""
        book = ladder_book()
        choices = creation.selected(book['creation'])
        rungs = [row['stage'] for row in choices['ladder']['ladder']]
        invented = volume_rows(book, ['v1', 'v2'])
        invented[1]['stage'] = '工程夹具自造的层级'
        descending = volume_rows(book, ['v1', 'v2'])
        descending[0]['stage'], descending[1]['stage'] = rungs[1], rungs[0]
        for label, rows in (('invented', invented), ('descending', descending)):
            with self.subTest(scenario=label):
                with self.assertRaises(Error) as caught:
                    drift.validate_volume_outline({'volumes': rows}, book['contract'], book['world'],
                                                  choices, {}, ['v1', 'v2'], book['state'])
                self.assertEqual(caught.exception.code, 'design_drift')
                criteria = {finding['criterion'] for finding in caught.exception.details['findings']}
                self.assertIn('volume_stage', criteria, str(caught.exception.details)[:300])

    def test_the_tier_floor_for_a_ladder_is_declared_once_in_defaults(self):
        """The floors live in `contracts.DEFAULTS` alone; this pins the frozen table."""
        floors = DEFAULTS['world_ladder']
        self.assertEqual(floors['tier_min'],
                         {'t0': 2, 't1': 3, 't2': 3, 't3': 4, 't4': 4, 't5': 4})
        self.assertEqual(floors['stage_min'],
                         {'t0': 2, 't1': 2, 't2': 3, 't3': 4, 't4': 4, 't5': 4})
        self.assertEqual(floors['anchor_max_chapter'], 30)


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

    def test_a_self_consistent_chain_is_accepted_normalized_and_simulated(self):
        rows = self.submit(self.rows)
        self.assertEqual([row['chapter'] for row in rows], [1, 2])
        self.assertEqual(rows[0]['clock'], {'advance_days': 1})
        self.assertTrue(rows[0]['enter'])
        self.assertEqual([item['kind'] for item in rows[0]['enter']],
                         [item['kind'] for item in rows[0]['exit']])
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

    def test_chain_disagreements_are_rejected(self):
        """Enter must equal the previous exit, exit must equal enter plus the deltas, and a delta's
        `from` must pick up the chain where it actually stands."""
        enter = copy.deepcopy(self.rows)
        enter[1]['enter'][0]['expected'] = 99
        exit_sum = copy.deepcopy(self.rows)
        exit_sum[0]['exit'][1]['expected'] = '办公室'
        resource_from = copy.deepcopy(self.rows)
        resource_from[1]['resources'][0]['from'] = 4
        for scenario, broken in (('enter_disagrees', enter), ('exit_not_enter_plus_deltas', exit_sum),
                                 ('resource_from_off_the_chain', resource_from)):
            with self.subTest(scenario=scenario):
                self.assertRejected('drift_chain', broken)

    def test_delta_rules_are_rejected_where_they_break(self):
        """Negative resources, a backwards clock and an unknown place each name their own criterion."""
        negative = copy.deepcopy(self.rows)
        negative[0]['resources'][0]['to'] = -1
        backwards = copy.deepcopy(self.rows)
        backwards[0]['clock'] = {'advance_days': -1}
        unknown_place = copy.deepcopy(self.rows)
        unknown_place[0]['places'][0]['to'] = '不存在的后院'
        for criterion, broken in (('drift_resource', negative), ('drift_shape', backwards),
                                  ('drift_place', unknown_place)):
            with self.subTest(criterion=criterion):
                self.assertRejected(criterion, broken)

    def test_a_disclosure_row_without_a_reveal_tier_is_rejected_at_outline_time(self):
        """Settlement has always applied this test when the prose arrives; skipping it at outline
        time deadlocks the write stage against a frozen outline it may not fix (live 2026-10-21)."""
        broken = copy.deepcopy(self.rows)
        broken[0]['disclosures'] = [{'topic': '货箱来源', 'after': '也许大概'}]
        self.assertRejected('drift_shape', broken)
        valid = copy.deepcopy(self.rows)
        valid[0]['disclosures'] = [{'topic': '货箱来源', 'after': 'hinted'}]
        self.submit(valid)

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
        live, _ = drift.simulate(self.rows[:1], self.state, self.world, self.volume,
                                 self.volume_row)
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


class ProvenanceTests(unittest.TestCase):
    """The outline chain reads the world, never invents a coordinate the world does not have."""

    def test_the_seeded_world_grounds_the_chapter_refs(self):
        book = seeded_book(contract())
        row = chapter_rows(book, book['contract']['volumes'][0], book['state'])[0]
        refs = row['world_refs']
        self.assertTrue(refs)
        for ref in refs:
            section, ident = ref.split(':', 1)
            self.assertIn(ident, {row['id'] for row in book['world'][section]})
        for field in ('resources', 'places', 'knowledge', 'characters'):
            self.assertIsInstance(row[field], list)
        self.assertIsInstance(row['clock'], dict)
        self.assertIsInstance(row['enter'], list)
        self.assertIsInstance(row['exit'], list)
        self.assertIsInstance(row['hooks'], list)

    def test_an_unseeded_world_leaves_refs_empty_instead_of_inventing_them(self):
        book = workflow.new_book(contract())
        rows = chapter_rows(book, book['contract']['volumes'][0], book['state'])
        self.assertEqual(rows[0]['world_refs'], [])


class VolumeHookTests(unittest.TestCase):
    """The volume outline declares the promises; the declaration itself is checked mechanically."""

    def setUp(self):
        self.book = seeded_book(contract(chapters=4, volumes=2))
        self.contract, self.world, self.state = (self.book['contract'], self.book['world'],
                                                 self.book['state'])
        self.rows = volume_rows(self.book, ['v1', 'v2'], hooks=True)

    def submit(self, rows):
        return drift.validate_volume_outline({'volumes': rows}, self.contract, self.world,
                                             {}, {}, ['v1', 'v2'], self.state)

    def assertRejected(self, criterion, rows):
        with self.assertRaises(Error) as caught:
            self.submit(rows)
        self.assertEqual(caught.exception.code, 'design_drift')
        criteria = {finding['criterion'] for finding in caught.exception.details['findings']}
        self.assertIn(criterion, criteria, str(caught.exception.details['findings'])[:400])
        return caught.exception

    def test_a_hook_id_shares_the_volume_namespace_with_nodes_and_threads(self):
        broken = copy.deepcopy(self.rows)
        broken[0]['hooks'][0]['id'] = broken[0]['nodes'][0]['id']
        self.assertRejected('volume_hook', broken)
        thread_taken = copy.deepcopy(self.rows)
        thread_taken[0]['hooks'][0]['id'] = thread_taken[0]['threads'][0]['id']
        self.assertRejected('volume_hook', thread_taken)

    def test_promise_declarations_that_cannot_settle_are_rejected(self):
        """The declaration matrix: id collisions, inverted windows, cross-volume handover shape and
        empty text are all `volume_hook` findings, each named at submit time."""
        collision = copy.deepcopy(self.rows)
        collision[0]['hooks'][0]['id'] = collision[0]['nodes'][0]['id']
        inverted = copy.deepcopy(self.rows)
        inverted[0]['hooks'][0].update(plant=[2, 2], payoff=[1, 1])
        handover = copy.deepcopy(self.rows)
        handover[0]['hooks'][1].update(continues=False)
        late_required = copy.deepcopy(self.rows)
        late_required[0]['hooks'][0].update(payoff=[3, 3])
        blank = copy.deepcopy(self.rows)
        blank[0]['hooks'][0]['text'] = ''
        for scenario, broken in (('id_collision', collision), ('payoff_before_plant_window', inverted),
                                 ('cross_volume_without_continues', handover),
                                 ('required_paid_after_the_volume', late_required),
                                 ('empty_promise_text', blank)):
            with self.subTest(scenario=scenario):
                self.assertRejected('volume_hook', broken)

    def test_the_default_volume_rows_declare_a_required_and_a_continuing_hook(self):
        report = self.submit(copy.deepcopy(self.rows))
        required = report['v1']['hooks'][0]
        self.assertTrue(required['required'])
        self.assertFalse(required['continues'])
        self.assertEqual(required['payoff'], [2, 2])
        continuing = report['v1']['hooks'][1]
        self.assertFalse(continuing['required'])
        self.assertTrue(continuing['continues'])
        self.assertEqual(continuing['payoff'], [3, 3])
        self.assertEqual(len(report['v2']['hooks']), 1)   # the last volume has nobody to hand to

    def test_the_promise_ledger_can_be_switched_off_for_an_unrelated_check(self):
        report = self.submit(volume_rows(self.book, ['v1', 'v2'], hooks=False))
        self.assertEqual([report['v1']['hooks'], report['v2']['hooks']], [[], []])


class ChapterHookTests(unittest.TestCase):
    """Chapter outlines execute the promises; the chain refuses any execution that cannot settle."""

    def setUp(self):
        self.book = seeded_book(contract(chapters=4, volumes=2))
        self.contract, self.world, self.state = (self.book['contract'], self.book['world'],
                                                 self.book['state'])
        self.volume = self.contract['volumes'][0]
        self.volume_row = drift.validate_volume_outline(
            {'volumes': volume_rows(self.book, ['v1'], hooks=True)}, self.contract, self.world,
            {}, {}, ['v1'], self.state)['v1']
        self.rows = chapter_rows(self.book, self.volume, self.state, hooks=True)

    def submit(self, rows):
        return drift.validate_chapter_outline(
            {'volume': 'v1', 'chapters': rows}, self.contract['chapter_outline'], self.volume,
            self.volume_row, self.world, self.state)

    def assertRejected(self, criterion, rows):
        with self.assertRaises(Error) as caught:
            self.submit(rows)
        self.assertEqual(caught.exception.code, 'design_drift')
        criteria = {finding['criterion'] for finding in caught.exception.details['findings']}
        self.assertIn(criterion, criteria, str(caught.exception.details['findings'])[:400])
        return caught.exception

    def test_the_default_chain_plants_in_the_first_chapter_and_pays_in_the_last(self):
        rows = self.submit(copy.deepcopy(self.rows))
        self.assertEqual([entry['action'] for entry in rows[0]['hooks']],
                         ['plant', 'plant'])
        self.assertEqual([entry['hook'] for entry in rows[0]['hooks']],
                         ['hook-v1-required', 'hook-v1-carry'])
        self.assertEqual(rows[1]['hooks'],
                         [{'hook': 'hook-v1-required', 'action': 'payoff',
                           'note': '本卷末兑现本卷承诺。'}])

    def test_the_promise_schedule_can_be_switched_off(self):
        # With no promise declared, a chapter chain of empty hook arrays is the consistent shape:
        # the two switches travel together (a promise the volume declared must be executed).
        outline = drift.validate_volume_outline(
            {'volumes': volume_rows(self.book, ['v1'], hooks=False)}, self.contract, self.world,
            {}, {}, ['v1'], self.state)['v1']
        rows = chapter_rows(self.book, self.volume, self.state, hooks=False)
        validated = drift.validate_chapter_outline(
            {'volume': 'v1', 'chapters': rows}, self.contract['chapter_outline'], self.volume,
            outline, self.world, self.state)
        self.assertEqual([row['hooks'] for row in validated], [[], []])

    def test_the_promise_execution_matrix_is_rejected_case_by_case(self):
        """Every way a chapter can execute a promise it was not allowed to, one subTest each:
        planting an undeclared promise, paying before planting, planting or paying twice,
        acting outside the declared window, and hook_refs continuing an unplanted promise."""
        undeclared = copy.deepcopy(self.rows)
        undeclared[0]['hooks'].append({'hook': 'hook-unknown', 'action': 'plant', 'note': '工程样本。'})
        payoff_first = copy.deepcopy(self.rows)
        payoff_first[0]['hooks'] = [{'hook': 'hook-v1-required', 'action': 'payoff', 'note': '工程样本。'}]
        payoff_first[1]['hooks'] = [{'hook': 'hook-v1-required', 'action': 'plant', 'note': '工程样本。'}]
        planted_twice = copy.deepcopy(self.rows)
        planted_twice[0]['hooks'].append({'hook': 'hook-v1-required', 'action': 'plant', 'note': '工程样本。'})
        paid_twice = copy.deepcopy(self.rows)
        paid_twice[1]['hooks'].append({'hook': 'hook-v1-required', 'action': 'payoff', 'note': '工程样本。'})
        plant_late = copy.deepcopy(self.rows)
        plant_late[0]['hooks'] = [entry for entry in plant_late[0]['hooks']
                                  if entry['hook'] != 'hook-v1-required']
        plant_late[1]['hooks'].append({'hook': 'hook-v1-required', 'action': 'plant', 'note': '工程样本。'})
        payoff_early = copy.deepcopy(self.rows)
        payoff_early[0]['hooks'].append({'hook': 'hook-v1-required', 'action': 'payoff', 'note': '工程样本。'})
        refs_unplanted = copy.deepcopy(self.rows)
        refs_unplanted[0]['hooks'] = [entry for entry in refs_unplanted[0]['hooks']
                                      if entry['hook'] != 'hook-v1-carry']
        refs_unplanted[0]['hook_refs'] = ['hook-v1-carry']
        for scenario, broken in (('plant_undeclared', undeclared), ('payoff_before_plant', payoff_first),
                                 ('planted_twice', planted_twice), ('paid_twice', paid_twice),
                                 ('plant_outside_window', plant_late),
                                 ('payoff_outside_window', payoff_early),
                                 ('hook_refs_continue_unplanted', refs_unplanted)):
            with self.subTest(scenario=scenario):
                self.assertRejected('chapter_hook', broken)


class HookClosureTests(unittest.TestCase):
    """The volume close is where promises either land or are handed to the next volume."""

    def setUp(self):
        self.book = seeded_book(contract(chapters=4, volumes=2))
        self.contract, self.world = self.book['contract'], self.book['world']
        self.volumes = self.contract['volumes']
        self.state = self.book['state']
        self.v1_row = drift.validate_volume_outline(
            {'volumes': volume_rows(self.book, ['v1'], hooks=True)}, self.contract, self.world,
            {}, {}, ['v1'], self.state)['v1']

    def v1_chapters(self, hooks=True):
        return chapter_rows(self.book, self.volumes[0], self.state, hooks=hooks)

    def test_an_unpaid_required_promise_is_rejected_at_the_volume_close(self):
        rows = self.v1_chapters()
        rows[-1]['hooks'] = []                    # the volume ends without paying its promise
        with self.assertRaises(Error) as caught:
            drift.validate_chapter_outline({'volume': 'v1', 'chapters': rows},
                                           self.contract['chapter_outline'], self.volumes[0],
                                           self.v1_row, self.world, self.state)
        self.assertEqual(caught.exception.code, 'design_drift')
        criteria = {finding['criterion'] for finding in caught.exception.details['findings']}
        self.assertIn('drift_closure', criteria, str(caught.exception.details['findings'])[:400])

    def test_a_continuing_promise_may_stay_open_and_is_paid_in_the_next_volume(self):
        rows = self.v1_chapters()
        drift.validate_chapter_outline({'volume': 'v1', 'chapters': rows},
                                       self.contract['chapter_outline'], self.volumes[0],
                                       self.v1_row, self.world, self.state)
        after_v1, findings = drift.simulate(rows, self.state, self.world, self.volumes[0],
                                            self.v1_row)
        self.assertEqual(findings, [])
        self.assertEqual(after_v1['hooks']['hook-v1-carry']['status'], 'open')
        self.assertEqual(after_v1['hooks']['hook-v1-required']['status'], 'paid')
        v2_row = drift.validate_volume_outline(
            {'volumes': volume_rows(self.book, ['v2'], hooks=True)}, self.contract, self.world,
            {}, {'v1': self.v1_row}, ['v2'], after_v1)['v2']
        v2_rows = chapter_rows(self.book, self.volumes[1], after_v1, hooks=True)
        drift.validate_chapter_outline({'volume': 'v2', 'chapters': v2_rows},
                                       self.contract['chapter_outline'], self.volumes[1],
                                       v2_row, self.world, after_v1)
        after_v2, findings = drift.simulate(v2_rows, after_v1, self.world, self.volumes[1], v2_row)
        self.assertEqual(findings, [])
        self.assertEqual(after_v2['hooks']['hook-v1-carry']['status'], 'paid')
        self.assertEqual(after_v2['hooks']['hook-v2-required']['status'], 'paid')
        self.assertEqual({row['status'] for row in after_v2['hooks'].values()}, {'paid'})


if __name__ == '__main__':
    unittest.main()
