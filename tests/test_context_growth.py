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

from novel_ledger import context, facts
from novel_ledger.bootstrap import local_application as Application
from novel_ledger.contracts import Job, dump
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


if __name__ == '__main__':
    unittest.main()
