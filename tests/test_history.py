"""Synthetic storage and context fixtures, never literary or complete-book acceptance."""
import copy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'scripts')]
from novel_ledger import context, facts, workflow
from novel_ledger.bootstrap import local_application as Application
from novel_ledger.contracts import Error, Job, digest, dump
from novel_ledger.sqlite_store import SQLiteRepository
from support import append_history, tracked_contract


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = SQLiteRepository.initialize(Path(self.temp.name) / 'book', workflow.new_book(tracked_contract(600)))
        self.app = Application(self.repo)

    def tearDown(self):
        self.repo.close()
        self.temp.cleanup()

    def populate(self, count):
        with self.repo.transaction():
            append_history(self.repo, 1, count)

    def task(self):
        return self.repo.add_task(context.build(self.repo, self.repo.load(), Job('write', 1)))

    def assertCode(self, code, fn, *args, **kwargs):
        with self.assertRaises(Error) as caught:
            fn(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)

    def test_history_head_is_small_and_repeated_dispatch_does_not_scan_events(self):
        self.populate(500)
        first = self.repo.history_snapshot('main')
        documents = self.repo.db.execute('SELECT count(*) FROM documents').fetchone()[0]
        with patch.object(self.repo, 'read_document', wraps=self.repo.read_document) as reads:
            for _ in range(4):
                self.assertEqual(self.repo.history_snapshot('main'), first)
            self.assertEqual(reads.call_count, 4)
            self.assertTrue(all(c.args[0] == first['head'] for c in reads.call_args_list))
        self.assertEqual(self.repo.db.execute('SELECT count(*) FROM documents').fetchone()[0], documents)
        self.assertLess(len(dump(first)), 300)

    def test_append_adds_one_page_and_old_snapshot_keeps_its_boundary(self):
        self.populate(3)
        old = self.repo.history_snapshot('main')
        with self.repo.transaction():
            append_history(self.repo, 4, 4)
        with patch.object(self.repo, 'document', wraps=self.repo.document) as writes:
            new = self.repo.history_snapshot('main')
            self.assertEqual(writes.call_count, 1)
        self.assertEqual(self.repo.read_document(new['head'])['previous'], old['head'])
        self.assertEqual([p['n'] for _, p in self.repo.history_pages(old)], [3, 2, 1])
        self.assertEqual([p['n'] for _, p in self.repo.history_pages(new)], [4, 3, 2, 1])

    def test_fork_shares_only_unchanged_prefix_and_uses_its_own_suffix(self):
        self.populate(5)
        original = self.repo.history_snapshot('main')
        original_pages = dict((p['n'], ident) for ident, p in self.repo.history_pages(original))
        with self.repo.transaction():
            branch = self.repo.fork('main', 4)
        prefix = self.repo.history_snapshot(branch)
        self.assertEqual(prefix['head'], original_pages[3])
        row = self.repo.chapter('main', 4)
        row.update(prose=self.repo.document('工程修订正文。'), chain=digest('candidate-4'))
        self.repo.add_chapter(branch, row)
        revised = self.repo.history_snapshot(branch)
        pages = list(self.repo.history_pages(revised))
        self.assertEqual(pages[1][0], original_pages[3])
        self.assertEqual(self.repo.read_document(pages[0][1]['prose']), '工程修订正文。')
        self.assertEqual(self.repo.history_snapshot('main'), original)

    def test_missing_cache_rebuilds_the_same_immutable_head_without_schema_change(self):
        self.populate(4)
        old = self.repo.history_snapshot('main')
        schema = self.repo.db.execute('SELECT sql FROM sqlite_master ORDER BY name').fetchall()
        self.repo.db.execute("DELETE FROM kv WHERE key='history_head:main'")
        self.assertEqual(self.repo.history_snapshot('main'), old)
        self.assertEqual(self.repo.db.execute('SELECT sql FROM sqlite_master ORDER BY name').fetchall(), schema)

    def test_cache_and_page_corruption_are_rejected(self):
        self.populate(2)
        source = self.repo.history_snapshot('main')
        bad = {**source, 'chain': 'wrong'}
        self.repo.put('history_head:main', bad)
        self.assertCode('history_integrity', self.repo.history_snapshot, 'main')
        self.repo.put('history_head:main', source)
        self.repo.db.execute('UPDATE documents SET value=? WHERE hash=?', (dump({}), source['head']))
        self.assertCode('source_integrity', lambda: list(self.repo.history_pages(source)))

    def test_empty_history_and_nonexistent_chapter_do_not_leak_later_content(self):
        task = self.task()
        self.assertEqual(self.app.recall(task['id'], kind='entity', key='shen')['matches'], [])
        self.assertCode('recall', self.app.recall, task['id'], chapter=1)

    def test_recent_query_reads_only_the_requested_page_and_one_lookahead(self):
        self.populate(500)
        task = self.task()
        with patch.object(self.repo, 'memory_rows', wraps=self.repo.memory_rows) as reads:
            result = self.app.recall(task['id'], kind='entity', key='shen', limit=5)
            self.assertEqual(reads.call_count, 6)
        self.assertEqual([r['chapter'] for r in result['matches']], [500, 499, 498, 497, 496])
        self.assertEqual(result['more_before'], 496)
        second = self.app.recall(task['id'], kind='topic', key='source', limit=2, before=496)
        self.assertEqual([r['chapter'] for r in second['matches']], [495, 494])

    def test_sparse_pagination_keeps_all_matching_events_and_has_no_duplicate_chapters(self):
        self.populate(8)
        for n in range(1, 9):
            row = self.repo.chapter('main', n)
            event = self.repo.read_document(row['events'])[0]
            event['entity'] = 'shen' if n in (2, 5, 8) else 'other'
            events = [event, {**event, 'op': 'state'}] if n in (2, 5, 8) else [event]
            self.repo.db.execute('UPDATE chapters SET events=? WHERE branch=? AND n=?',
                                 (self.repo.document(events), 'main', n))
        task = self.task()
        result = self.app.recall(task['id'], kind='entity', key='shen', limit=2)
        self.assertEqual([r['chapter'] for r in result['matches']], [8, 8, 5, 5])
        self.assertEqual(result['more_before'], 5)
        last = self.app.recall(task['id'], kind='entity', key='shen', limit=2, before=5)
        self.assertEqual([r['chapter'] for r in last['matches']], [2, 2])
        self.assertIsNone(last['more_before'])

    def test_preview_rollback_does_not_publish_new_history_pages_or_cache_heads(self):
        self.populate(2)
        original = self.repo.history_snapshot('main')
        with self.repo.transaction(preview=True):
            append_history(self.repo, 3, 3)
            preview = self.repo.history_snapshot('main')
            self.assertEqual(preview['through'], 3)
        self.assertEqual(self.repo.history_snapshot('main'), original)
        self.assertCode('source', self.repo.read_document, preview['head'])

    def test_supplemental_sources_are_frozen_even_after_append_and_branch_row_change(self):
        self.populate(3)
        task = self.task()
        expected = self.app.recall(task['id'], chapter=2)
        self.repo.db.execute('UPDATE chapters SET prose=? WHERE branch=? AND n=2', (self.repo.document('替换正文'), 'main'))
        with self.repo.transaction():
            append_history(self.repo, 4, 4)
        self.assertEqual(self.app.recall(task['id'], chapter=2), expected)
        self.assertCode('recall', self.app.recall, task['id'], chapter=4)
        self.assertEqual(self.app.recall(task['id'], kind='node', key='missing')['matches'], [])

    def test_supplemental_reads_are_open_from_the_start_without_a_first_read_seal(self):
        """v2 has no blind first read, so recall and the index are readable on the first dispatch.

        The retired protocol sealed every supplemental read until a frozen first read was filed; the
        seal went with the reviewer stages, and what is left is that a frozen task may only read its
        own frozen sources.
        """
        self.populate(2)
        task = self.task()
        self.assertEqual(self.app.recall(task['id'], chapter=1)['chapter'], 1)
        self.assertIn('historical_index', self.app.read(task['id'], 'historical_index')['records'])
        self.assertEqual([r['chapter'] for r in self.app.recall(task['id'], kind='entity', key='shen')['matches']], [2, 1])

    def test_old_frozen_catalog_and_event_index_remain_readable(self):
        self.populate(3)
        task = self.task()
        snapshot = self.repo.read_document(task['input']['records']['history_source'])
        pages = [p for _, p in self.repo.history_pages(snapshot)]
        work = copy.deepcopy(task['input'])
        del work['records']['history_source']
        work['records']['historical_index'] = self.repo.document([{'chapter': p['n'], 'prose_hash': p['prose'], 'summary': p['summary']} for p in pages])
        work['records']['memory_index'] = self.repo.document([r for p in pages for r in self.repo.memory_rows(p)])
        self.repo.cancel_pending('模拟旧在途协议')
        legacy = self.repo.add_task(work)
        self.assertEqual(self.app.recall(legacy['id'], chapter=2)['chapter'], 2)
        self.assertEqual([r['chapter'] for r in self.app.recall(legacy['id'], kind='entity', key='shen', limit=2)['matches']], [3, 2])

    def test_explicit_full_index_read_remains_available_without_entering_default_input(self):
        self.populate(3)
        task = self.task()
        material = self.app.read(task['id'])
        self.assertNotIn('history_source', material['records'])
        self.assertIn('history_source', material['on_demand'])
        for name in ('historical_index', 'memory_index'):
            value = self.app.read(task['id'], name)['records'][name]
            self.assertEqual(value['hash'], digest(value['value']))
            self.assertEqual([r['chapter'] for r in value['value']], [1, 2, 3])

    def test_recall_output_is_observed_once_and_rejected_reads_are_not_counted(self):
        self.populate(2)
        task = self.task()
        before = self.repo.usage()['supplemental_read_chars']
        result = self.app.recall(task['id'], chapter=1)
        self.assertEqual(self.repo.usage()['supplemental_read_chars'] - before, len(dump(result)))
        before = self.repo.usage()['supplemental_read_chars']
        self.assertCode('recall', self.app.recall, task['id'], chapter=3)
        self.assertEqual(self.repo.usage()['supplemental_read_chars'], before)

    def test_hook_topic_metadata_is_searchable_without_forcing_reader_knowledge(self):
        self.populate(1)
        row = self.repo.chapter('main', 1)
        events = self.repo.read_document(row['events'])
        events.append({'op': 'hook', 'subjects': ['shen'], 'topics': ['hidden-source'], 'hook_links_version': 1,
                       'evidence': {'chapter': 1, 'quote': '沈桐查出来源'}})
        row.update(events=self.repo.document(events), chain=digest('fixture-with-hook'))
        self.repo.db.execute('UPDATE chapters SET events=?,chain=? WHERE branch=? AND n=1', (row['events'], row['chain'], 'main'))
        task = self.task()
        found = self.app.recall(task['id'], kind='topic', key='hidden-source')
        self.assertEqual(found['matches'][0]['op'], 'hook')
        self.assertNotIn('hidden-source', self.repo.load()['state']['reader_knowledge'])


class HookContextTests(unittest.TestCase):
    def setUp(self):
        self.state = workflow.new_book(tracked_contract(200))['state']
        self.state['entities']['token'] = {'id': 'token', 'name': '信物', 'kind': 'object'}
        self.state['hooks'] = {
            'person': {'status': 'open', 'due': 180, 'subjects': ['shen'], 'text': '人物承诺'},
            'object': {'status': 'open', 'due': 180, 'subjects': ['token'], 'text': '物品承诺'},
            'topic': {'status': 'open', 'due': 180, 'topics': ['source'], 'text': '话题承诺'},
            'unrelated': {'status': 'open', 'due': 180, 'subjects': ['token'], 'topics': ['other'], 'text': '远期承诺'},
            'legacy': {'status': 'open', 'due': 180, 'text': '旧承诺'},
            'soon': {'status': 'open', 'due': 23, 'text': '将到期承诺'},
            'closed': {'status': 'paid', 'due': 180, 'subjects': ['shen'], 'text': '已完成'},
        }

    def test_related_far_future_hooks_are_loaded_and_unrelated_hooks_remain_optional(self):
        view = context.scoped_state(self.state, ['shen'], {'reader_refs': ['source'], 'hook_refs': ['legacy']}, 21, 3)
        self.assertEqual(set(view['hooks']), {'person', 'topic', 'legacy', 'soon'})
        self.assertEqual(set(self.state['hooks']), {'person', 'object', 'topic', 'unrelated', 'legacy', 'soon', 'closed'})
        objects = context.scoped_state(self.state, ['token'], {}, 21, 3)
        self.assertEqual(set(objects['hooks']), {'object', 'unrelated', 'soon'})

    def test_hook_relations_are_evidence_backed_replayed_and_validated(self):
        state = workflow.new_book(tracked_contract(200))['state']
        prose = '沈桐答应核查来源。'
        event = {'op': 'hook', 'id': 'promise', 'status': 'open', 'before': None, 'due': 180,
                 'text': '核查来源', 'subjects': ['shen'], 'topics': ['source'],
                 'evidence': {'chapter': 1, 'quote': prose}}
        event = facts.prepare_hook_links([event], True)[0]
        after, normalized = facts.settle(state, [event], prose, 1)
        self.assertEqual(after['hooks']['promise']['subjects'], ['shen'])
        self.assertEqual(facts.settle(state, normalized, prose, 1)[0], after)
        for mutate in ({'subjects': ['unknown']}, {'subjects': ['shen', 'shen']}, {'topics': 'source'}):
            with self.assertRaises(Error) as caught:
                facts.settle(state, [{**event, **mutate}], prose, 1)
            self.assertEqual(caught.exception.code, 'hook_reference')
        with self.assertRaises(Error):
            facts.settle(after, [{**event, 'before': 'open', 'topics': [], 'evidence': {'chapter': 2, 'quote': prose}}], prose, 2)
        changed = {**event, 'before': 'open', 'topics': [], 'reason': '正文交代了核查话题的变化。', 'evidence': {'chapter': 2, 'quote': prose}}
        self.assertEqual(facts.settle(after, [changed], prose, 2)[0]['hooks']['promise']['topics'], [])

    def test_legacy_hooks_replay_without_new_fields_and_due_check_is_preserved(self):
        state = workflow.new_book(tracked_contract(200))['state']
        event = {'op': 'hook', 'id': 'old', 'status': 'open', 'before': None, 'due': 2,
                 'text': '旧承诺', 'evidence': {'chapter': 1, 'quote': '工程承诺'}}
        after, _ = facts.settle(state, [event], '工程承诺', 1)
        self.assertNotIn('subjects', after['hooks']['old'])
        with self.assertRaises(Error) as caught:
            facts.settle(after, [], '工程后文', 2)
        self.assertEqual(caught.exception.code, 'hook_due')

    def test_old_uninterpreted_hook_fields_do_not_change_historical_projection(self):
        state = workflow.new_book(tracked_contract(200))['state']
        event = {'op': 'hook', 'id': 'old', 'status': 'open', 'before': None, 'due': 180,
                 'text': '旧承诺', 'subjects': ['shen'], 'topics': '过去未解释的扩展值',
                 'evidence': {'chapter': 1, 'quote': '工程承诺'}}
        legacy = facts.prepare_hook_links([event], False)
        self.assertEqual(legacy, [event])
        after, _ = facts.settle(state, legacy, '工程承诺', 1)
        self.assertNotIn('subjects', after['hooks']['old'])
        self.assertNotIn('topics', after['hooks']['old'])

    def test_dispatch_baseline_uses_frozen_selected_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            book = workflow.new_book(tracked_contract(200))
            book['state'] = self.state
            book['plans']['21'] = {'participants': ['shen'], 'node_ids': [], 'node_contracts': {}, 'hook_refs': [], 'disclosures': []}
            repo = SQLiteRepository.initialize(Path(temporary) / 'book', book)
            try:
                # Baseline is queried directly to isolate transport from lifecycle scheduling.
                selected = context.scoped_state(self.state, ['shen'], book['plans']['21'], 21, 3)
                task = {'input': {'records': {'state': repo.document(selected)}}}
                baseline = Application(repo)._baseline(book, task)
                self.assertEqual({h['id'] for h in baseline['open_hooks']}, {'person', 'soon'})
            finally:
                repo.close()


if __name__ == '__main__':
    unittest.main()
