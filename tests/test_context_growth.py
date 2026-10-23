"""Synthetic long-book selection: historical completion must not enlarge a new draft's input.

These source-only records exercise frozen material, not literary quality or model isolation.
Complete historical promises and explicit causal inputs must stay recoverable in full.
"""
import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts')]

from novel_ledger import context, facts, story_memory
from novel_ledger.bootstrap import local_application as Application
from novel_ledger.contracts import Error, Job, digest, dump
from novel_ledger.sqlite_store import SQLiteRepository
from support import drive, seeded_book, tracked_contract


def history_rows(book, count):
    """Append completed source records without pretending to have written a real novel."""
    for number in range(count):
        ident = 'past-' + str(number)
        hook = {'id': ident, 'text': '已兑现的历史承诺，原文与窗口须完整保留。',
                'plant': [number + 1, number + 1], 'payoff': [number + 1, number + 1],
                'required': True, 'continues': False}
        book['volumes_outline'][ident] = {'id': ident, 'hooks': [hook]}
        book['state']['hooks'][ident] = {'status': 'paid', 'due': number + 1, 'text': hook['text']}
        book['state']['thread_progress'][ident] = {
            'status': 'resolved', 'last_chapter': number + 1, 'reason': '这条支线已经收束。'}


def old_background(state, count):
    """Use the domain event API; these isolated places/topics are not inputs to the current scene."""
    for number in range(count):
        facts.apply_event(state, {'op': 'place', 'place': {
            'id': 'old-place-' + str(number), 'name': '本章无人所在的历史地点'}}, number + 1)
        facts.apply_event(state, {'op': 'knowledge', 'entity': 'shen',
            'topic': 'old-topic-' + str(number), 'before': None, 'claim': '过去已确认的无关知识',
            'source': '此前章节', 'stance': 'knows',
            'evidence': {'chapter': number + 1, 'quote': '此前已成立的原文证据。'}}, number + 1)


def complete_scene(**values):
    return {'id': 'current', 'reads': [], 'depends_on': [], **values}


class ContextGrowthTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.repo = SQLiteRepository.initialize(Path(self.temporary.name) / 'book',
                                                seeded_book(tracked_contract(chapters=6, volumes=2)))
        app = Application(self.repo)
        drive(app, until='write')
        self.book = self.repo.load()

    def tearDown(self):
        self.repo.close()
        self.temporary.cleanup()

    def material(self, book, job=None):
        work = context.build(self.repo, book, job or Job('write', 1))
        values = {name: self.repo.read_document(work['records'][name]) for name in work['required']}
        return work, values

    def test_two_thousand_completed_promises_and_lines_do_not_grow_required_draft_material(self):
        sizes = []
        for count in (20, 100, 500, 2000):
            with self.subTest(history=count):
                book = copy.deepcopy(self.book)
                history_rows(book, count)
                work, values = self.material(book)
                sizes.append(len(dump(values).encode('utf-8')))
                self.assertNotIn('complete_hooks', work['required'])
                complete = self.repo.read_document(work['records']['complete_hooks'])
                self.assertEqual(len([row for row in complete['declared']
                                      if row['id'].startswith('past-')]), count)
                self.assertFalse(any(row['id'].startswith('past-') for row in values['hooks']['declared']))
                self.assertFalse(any(key.startswith('past-') for key in values['state']['thread_progress']))
                self.assertIn('complete_hooks', values['hooks']['source'])
        self.assertEqual(len(set(sizes)), 1, sizes)

    def test_explicit_completed_dependencies_are_restored_and_live_obligations_are_kept(self):
        book = copy.deepcopy(self.book)
        history_rows(book, 500)
        book['state']['thread_progress']['live'] = {'status': 'active', 'last_chapter': 1}
        book['state']['thread_progress']['sleeping'] = {'status': 'dormant', 'return_by': 2000}
        plan = book['plans']['1']
        plan['scenes'] = [{'id': 'current', 'reads': [
            {'kind': 'thread_progress', 'key': 'past-0'}, {'kind': 'hooks', 'key': 'past-0'}],
            'depends_on': []}]
        before = copy.deepcopy(book)
        work, values = self.material(book)
        self.assertEqual(book, before)
        self.assertEqual(values['state']['thread_progress']['past-0'],
                         book['state']['thread_progress']['past-0'])
        self.assertEqual(set(values['state']['thread_progress']), {'past-0', 'live', 'sleeping'})
        declaration = next(row for row in values['hooks']['declared'] if row['id'] == 'past-0')
        self.assertEqual(declaration['text'], book['volumes_outline']['past-0']['hooks'][0]['text'])
        self.assertEqual(values['state']['hooks']['past-0']['status'], 'paid')
        self.assertEqual(next(row for row in values['scene_context']['inputs']
                              if row['kind'] == 'hooks' and row['key'] == 'past-0')['value']['status'], 'paid')
        # The complete ledger is immutable after dispatch, including the oldest full declaration.
        source = work['records']['complete_hooks']
        book['volumes_outline']['past-0']['hooks'][0]['text'] = '后来改了稿。'
        frozen = self.repo.read_document(source)
        self.assertEqual(next(row for row in frozen['declared'] if row['id'] == 'past-0'), declaration)

    def test_design_keeps_offstage_open_promises_and_requested_volume_declarations(self):
        book = copy.deepcopy(self.book)
        history_rows(book, 500)
        book['state']['hooks']['past-0'] = {
            'status': 'open', 'due': 2000, 'text': '跨卷承诺。', 'subjects': ['offstage']}
        job = Job('volume_outline', 1, 'volumes', payload={'volume_ids': ['past-1']})
        _, values = self.material(book, job)
        historical = {row['id'] for row in values['hooks']['declared'] if row['id'].startswith('past-')}
        self.assertEqual(historical, {'past-0', 'past-1'})
        self.assertEqual({row['id'] for row in values['hooks']['open']}, {'past-0'})

    def test_a_far_future_promise_action_is_required_even_without_a_related_cast_or_topic(self):
        book = copy.deepcopy(self.book)
        history_rows(book, 1)
        book['state']['hooks']['past-0'] = {
            'status': 'open', 'due': 2000, 'text': '跨卷承诺。', 'subjects': ['offstage']}
        book['plans']['1']['hooks'].append({'hook': 'past-0', 'action': 'payoff', 'note': '本章提前兑现。'})
        _, values = self.material(book)
        self.assertEqual(values['state']['hooks']['past-0']['status'], 'open')
        self.assertIn('past-0', {row['id'] for row in values['hooks']['declared']})
        self.assertIn('past-0', {row['id'] for row in values['hooks']['open']})

    def test_raw_rows_use_declared_unchanged_scene_cast_and_keep_unknown_cast_conservative(self):
        book = copy.deepcopy(self.book)
        for number in range(2000):
            ident = 'offstage-' + str(number)
            book['state']['entities'][ident] = {'id': ident, 'name': '远处人物'}
        plan = {'participants': [], 'characters': [], 'knowledge': [], 'places': [],
                'scenes': [{'present': ['shen']}]}
        self.assertEqual(context._participants(plan, book), ['shen'])
        plan['scenes'] = []
        self.assertEqual(set(context._participants(plan, book)), set(book['state']['entities']))

    def test_basic_projects_also_scope_unrelated_promises_and_long_development_history(self):
        state = facts.seed({'entities': [{'id': 'hero', 'name': '主角', 'kind': 'person'}]})
        state['developments']['hero'] = [{'chapter': number, 'change': '人物变化。'} for number in range(2000)]
        state['hooks'] = {
            'soon': {'status': 'open', 'due': 22, 'text': '即将兑现。'},
            'remote': {'status': 'open', 'due': 2000, 'subjects': ['other'], 'text': '远方承诺。'}}
        selected = context.scoped_state(state, ['hero'], {}, 21)
        self.assertEqual(set(selected['hooks']), {'soon'})
        self.assertEqual(selected['developments']['hero'], state['developments']['hero'][-2:])
        self.assertEqual(len(state['developments']['hero']), 2000)
        explicit = {'scenes': [{'reads': [{'kind': 'developments', 'key': 'hero'},
                                        {'kind': 'hooks', 'key': 'remote'}]}]}
        selected = context.scoped_state(state, ['hero'], explicit, 21)
        self.assertEqual(selected['developments']['hero'], state['developments']['hero'])
        self.assertEqual(set(selected['hooks']), {'soon', 'remote'})

    def test_complete_dependencies_bound_old_places_and_participant_knowledge(self):
        sizes = []
        for count in (20, 100, 500, 2000):
            with self.subTest(history=count):
                book = copy.deepcopy(self.book)
                plan = book['plans']['1']
                plan.update(dependency_coverage='complete', scenes=[complete_scene()])
                old_background(book['state'], count)
                before = copy.deepcopy(book)
                work, values = self.material(book)
                self.assertEqual(book, before)
                sizes.append(len(dump(values).encode('utf-8')))
                state = values['state']
                self.assertFalse(any(k.startswith('old-place-') for k in state['places']))
                self.assertFalse(any(k.startswith('shen:old-topic-') for k in state['knowledge']))
                self.assertEqual(state['material_scope']['mode'], 'declared_dependencies')
                complete = self.repo.read_document(work['records']['complete_state'])
                self.assertEqual(complete, book['state'])
                self.assertNotIn('complete_state', work['required'])
        self.assertEqual(len(set(sizes)), 1, sizes)

    def test_partial_or_missing_scene_dependencies_keep_unknown_background(self):
        book = copy.deepcopy(self.book)
        old_background(book['state'], 100)
        for declaration in ({}, {'dependency_coverage': 'partial', 'scenes': [complete_scene()]},
                            {'dependency_coverage': 'complete', 'scenes': []},
                            {'dependency_coverage': 'complete', 'scenes': [{'id': 'undeclared'}]}):
            with self.subTest(declaration=declaration):
                plan = {**book['plans']['1'], **declaration}
                selected = context.scoped_state(book['state'], ['shen'], plan, 1)
                self.assertEqual(selected['places'], book['state']['places'])
                self.assertEqual(selected['knowledge'], book['state']['knowledge'])
                self.assertEqual(selected['material_scope']['mode'], 'conservative')
                self.assertIn('不完整', selected['material_scope']['note'])
                self.assertEqual(selected['material_scope']['source'], 'complete_state')

    def test_design_batches_do_not_use_the_start_chapters_complete_dependency_boundary(self):
        book = copy.deepcopy(self.book)
        old_background(book['state'], 1)
        book['plans']['1'].update(dependency_coverage='complete', scenes=[complete_scene()])
        book['plans']['2'].update(dependency_coverage='complete', scenes=[complete_scene(
            id='later', reads=[{'kind': 'knowledge', 'key': 'shen:old-topic-0'}])])
        book['plans']['2']['places'] = [{'entity': 'shen', 'from': 'office', 'to': 'old-place-0'}]
        # These sources do not belong to the first fixed prose chapter, but a redesign covering
        # chapters 1-3 must keep them to decide the second chapter's knowledge and destination.
        _, first = self.material(book, Job('write', 1))
        self.assertNotIn('shen:old-topic-0', first['state']['knowledge'])
        self.assertNotIn('old-place-0', first['state']['places'])
        jobs = [Job('chapter_outline', 1, 'v1', 1, 3, {'repair': True}),
                Job('volume_outline', 1, 'volumes', payload={'volume_ids': ['v1']}),
                Job('volume_outline', 1, 'volumes', payload={'volume_ids': ['v1'], 'also': ['chapter_outline']})]
        for job in jobs:
            with self.subTest(stage=job.stage, payload=job.payload):
                work, _ = self.material(book, job)
                selected = self.repo.read_document(work['records']['state'])
                self.assertEqual(selected['knowledge']['shen:old-topic-0'],
                                 book['state']['knowledge']['shen:old-topic-0'])
                self.assertEqual(selected['places'], book['state']['places'])
                self.assertEqual(selected['material_scope']['mode'], 'conservative')
                self.assertIn('设计任务', selected['material_scope']['note'])

    def test_complete_knowledge_keeps_dialogue_changes_boundaries_and_offstage_reads(self):
        state = copy.deepcopy(self.book['state'])
        facts.apply_event(state, {'op': 'entity', 'entity': {
            'id': 'witness', 'name': '远处证人', 'kind': 'person'}}, 1)
        for who, topic in [('shen', 'dialogue'), ('shen', 'change'), ('shen', 'reveal'),
                           ('shen', 'reader'), ('shen', 'scene-reading'), ('shen', 'unused'),
                           ('witness', 'offstage')]:
            facts.apply_event(state, {'op': 'knowledge', 'entity': who, 'topic': topic,
                'before': None, 'claim': topic, 'source': '已核验原文', 'stance': 'knows',
                'evidence': {'chapter': 1, 'quote': '他记得当年的经过。'}}, 1)
        plan = {'chapter': 2, 'dependency_coverage': 'complete',
                'scenes': [complete_scene(
                    reads=[{'kind': 'knowledge', 'key': 'witness:offstage'}],
                    dialogue_intents=[{'entity': 'shen', 'knowledge_topics': ['dialogue']}],
                    reading_refs=[{'kind': 'disclosure', 'key': 'scene-reading'}])],
                'knowledge': [{'who': 'shen', 'topic': 'change', 'from': 'confirmed', 'to': 'retracted'}],
                'disclosures': [{'topic': 'reveal'}], 'reader_refs': ['reader']}
        selected = context.scoped_state(state, ['shen'], plan, 2)
        expected = {'shen:dialogue', 'shen:change', 'shen:reveal', 'shen:reader',
                    'shen:scene-reading', 'witness:offstage'}
        self.assertEqual(set(selected['knowledge']), expected)
        self.assertEqual(selected['knowledge'], {key: state['knowledge'][key] for key in expected})

    def test_complete_space_keeps_custody_route_parents_and_actual_travel_constraints(self):
        state = facts.seed({
            'editorial_features': True,
            'entities': [{'id': ident, 'name': ident, 'kind': 'object' if ident in ('box', 'token') else 'person'}
                         for ident in ('shen', 'guard', 'witness', 'box', 'token')],
            'places': [{'id': 'region', 'name': '城域'}, {'id': 'town', 'name': '城区', 'parent': 'region'},
                       {'id': 'office', 'name': '值班室', 'parent': 'town'},
                       {'id': 'gate', 'name': '中庭'}, {'id': 'yard', 'name': '后院'},
                       {'id': 'remote', 'name': '远处证人所在'}, {'id': 'unrelated', 'name': '废弃旧地'}],
            'placements': {'shen': 'office', 'guard': 'unrelated', 'witness': 'remote', 'box': 'office', 'token': 'office'},
            'initial_facts': [{'entity': 'guard', 'key': 'open', 'value': True}],
            'links': [{'id': 'first', 'a': 'office', 'b': 'gate', 'kind': 'path', 'min_days': 1,
                       'requires': {'guard:open': True}},
                      {'id': 'second', 'a': 'gate', 'b': 'yard', 'kind': 'path', 'min_days': 1},
                      {'id': 'sight', 'a': 'office', 'b': 'yard', 'kind': 'sight'},
                      {'id': 'remote-path', 'a': 'remote', 'b': 'unrelated', 'kind': 'path'}],
            'anchors': [{'entity': 'office', 'key': 'door', 'value': '东', 'policy': 'fixed'},
                        {'entity': 'unrelated', 'key': 'door', 'value': '西', 'policy': 'fixed'}]})
        facts.apply_event(state, {'op': 'placement', 'entity': 'token',
                                 'before': {'place': 'office'}, 'after': {'holder': 'box'}}, 1)
        facts.apply_event(state, {'op': 'placement', 'entity': 'box',
                                 'before': {'place': 'office'}, 'after': {'holder': 'shen'}}, 1)
        state['arrivals'].update(shen=2, box=4, token=4, witness=50)
        plan = {'chapter': 2, 'dependency_coverage': 'complete', 'scenes': [complete_scene(
                    reads=[{'kind': 'placements', 'key': 'witness'}])],
                'places': [{'entity': 'shen', 'from': 'office', 'to': 'yard', 'links': ['first', 'second']}]}
        selected = context.scoped_state(state, ['token'], plan, 2)
        self.assertEqual(set(selected['places']), {'region', 'town', 'office', 'gate', 'yard', 'remote'})
        self.assertEqual(set(selected['links']), {'first', 'second', 'sight'})
        self.assertEqual(selected['custody'], {'box': 'shen', 'token': 'box'})
        self.assertEqual(selected['facts']['guard:open'], True)
        self.assertEqual(selected['placements']['witness'], 'remote')
        self.assertEqual(selected['anchors'], {'office:door': state['anchors']['office:door']})
        travel = {'op': 'travel', 'entity': 'shen', 'from': 'office', 'to': 'yard',
                  'links': ['first', 'second'], 'depart': 4, 'arrive': 6}
        full_after, selected_after = copy.deepcopy(state), copy.deepcopy(selected)
        facts.apply_event(full_after, travel, 2)
        facts.apply_event(selected_after, travel, 2)
        for field in ('placements', 'custody', 'arrivals'):
            self.assertEqual(selected_after[field], {key: full_after[field][key] for key in selected_after[field]})
        for candidate in (state, selected):
            with self.assertRaises(Error) as caught:
                facts.apply_event(copy.deepcopy(candidate), {**travel, 'depart': 3}, 2)
            self.assertEqual(caught.exception.code, 'path_time')

    def test_scene_packet_references_the_only_chapter_outline_and_keeps_exact_inputs(self):
        book = copy.deepcopy(self.book)
        plan = book['plans']['1']
        plan.update(dependency_coverage='complete', scenes=[complete_scene(
            reads=[{'kind': 'entities', 'key': 'shen'}, {'kind': 'knowledge', 'key': 'shen:unknown'}])])
        work, values = self.material(book)
        packet = values['scene_context']
        self.assertNotIn('plan', packet)
        self.assertEqual(packet['plan_record'], 'chapter_outline')
        self.assertEqual(packet['plan_hash'], work['records']['chapter_outline'])
        self.assertEqual(packet['state_hash'], digest(book['state']))
        self.assertEqual({(item['kind'], item['key']) for item in packet['inputs']}, story_memory.reads(plan))
        for item in packet['inputs']:
            present, value = story_memory.lookup(book['state'], item['kind'], item['key'])
            self.assertEqual((item['present'], item['value']), (present, value))
        self.assertEqual(self.repo.read_document(work['records'][packet['plan_record']]), plan)


if __name__ == '__main__':
    unittest.main()
