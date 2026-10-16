"""Long-form ownership, rolling planning, explicit scene memory and safe revision behavior."""
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from novel_ledger import book_state, context, revision_impact, story_memory, workflow
from novel_ledger import bookpage, delivery
from novel_ledger.bootstrap import local_application as Application, local_workspace
from novel_ledger.contracts import Error, Job, digest
from novel_ledger.sqlite_store import SQLiteRepository
from support import contract, response
from test_narrative import tracked_contract, drive_tracked, tracked_response
from test_editorial import drive, enhanced_response, plan_extras


class LongformTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / 'book'
        self.repo = SQLiteRepository.initialize(self.project, workflow.new_book(contract(3)))
        self.app = Application(self.repo)

    def tearDown(self):
        self.repo.close()
        self.temp.cleanup()

    def assertCode(self, code, fn, *args, **kwargs):
        with self.assertRaises(Error) as caught:
            fn(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)

    def test_persistent_parts_reuse_unchanged_values_and_rollback_together(self):
        original = self.repo.get('book')
        self.assertEqual(original['schema'], book_state.BOOK_SCHEMA)
        self.assertNotIn('state', original)
        book = self.repo.load()
        book['plans']['1'] = {'chapter': 1, 'goal': '追问。'}
        self.repo.save(book)
        changed = self.repo.get('book')
        self.assertNotEqual(changed['parts']['intent'], original['parts']['intent'])
        for name in ('settings', 'canon', 'execution'):
            self.assertEqual(changed['parts'][name], original['parts'][name])
        count = self.repo.db.execute('SELECT count(*) FROM documents').fetchone()[0]
        with self.repo.transaction(preview=True):
            book['state']['clock'] = 4
            book['status'] = 'paused'
            self.repo.save(book)
        self.assertEqual(self.repo.get('book'), changed)
        self.assertEqual(self.repo.load()['state']['clock'], 0)
        self.assertEqual(self.repo.db.execute('SELECT count(*) FROM documents').fetchone()[0], count)

    def test_part_reads_are_narrow_and_assembled_load_uses_one_root(self):
        with patch.object(self.repo, 'read_document', wraps=self.repo.read_document) as reader:
            settings = self.repo.load_part('settings')
            self.assertEqual(reader.call_count, 1)
            self.assertEqual(settings['contract']['title'], '夜班退件')
        with patch.object(self.repo, 'get', wraps=self.repo.get) as getter:
            self.repo.load()
            self.assertEqual(getter.call_count, 1)

    def test_unknown_ownership_and_cross_partition_data_are_rejected(self):
        book = self.repo.load()
        book['unowned'] = '不可静默归入执行状态。'
        before = self.repo.get('book')
        self.assertCode('book_ownership', self.repo.save, book)
        self.assertEqual(before, self.repo.get('book'))
        root = copy.deepcopy(before)
        root['parts']['intent'] = self.repo.document({'state': {'clock': 9}})
        self.repo.put('book', root)
        self.assertCode('book_integrity', self.repo.load)

    def test_part_corruption_is_detected(self):
        key = self.repo.get('book')['parts']['canon']
        self.repo.db.execute('UPDATE documents SET value=? WHERE hash=?', ('{}', key))
        self.assertCode('source_integrity', self.repo.load)

    def test_version_two_project_is_refused_without_rewriting_it(self):
        self.repo.put('schema', 'novel-ledger/2')
        before = (self.project / 'novel.sqlite3').read_bytes()
        self.assertCode('schema', SQLiteRepository, self.project)
        self.assertEqual((self.project / 'novel.sqlite3').read_bytes(), before)

    def test_default_rolling_outline_stops_at_horizon_and_refills_on_demand(self):
        raw = tracked_contract(8)
        raw['volumes'] = contract(8, 2)['volumes']
        raw.pop('volume_outline')
        self.repo.save(workflow.new_book(raw))
        self.assertEqual(self.repo.load()['contract']['volume_outline']['scope'], 'rolling')
        owner = self.app.run(through=5, source='先写五章。')['owner']
        drive_tracked(self.app, owner, until='write')
        initial = self.repo.load()
        self.assertEqual([c['chapter'] for c in initial['designs']['volume:v1']['chapters']], [1, 2, 3])
        self.assertNotIn('volume:v2', initial['designs'])
        self.app.submit(tracked_response(self.app))
        self.assertEqual(drive_tracked(self.app, owner)['action'], 'target_reached')
        book = self.repo.load()
        self.assertEqual([c['chapter'] for c in book['designs']['volume:v1']['chapters']], [1, 2, 3, 4])
        self.assertEqual([c['chapter'] for c in book['designs']['volume:v2']['chapters']], [5, 6, 7])
        self.assertEqual(len(self.repo.headers('main')), 5)

    def test_rolling_project_can_complete_and_deliver_exact_snapshot(self):
        raw = tracked_contract(4)
        raw.pop('volume_outline')
        self.repo.save(workflow.new_book(raw))
        owner = self.app.run(finish=True, source='完成全书。')['owner']
        self.assertEqual(drive_tracked(self.app, owner)['action'], 'ready_to_complete')
        self.app.complete(owner)
        result = delivery.deliver_completion(self.repo, bookpage.render, workspace=local_workspace(self.repo))
        self.assertTrue((self.project / 'book.md').exists())
        self.assertTrue((self.project / 'book.html').exists())
        self.assertEqual(self.repo.load()['status'], 'completed')
        self.assertEqual(len(self.repo.headers('main')), 4)

    def test_basic_project_scope_reviews_stay_bounded_through_the_tree(self):
        # The flat scheme handed a whole volume to one synthesis worker, so a basic project's
        # dispatch grew with its length. Every project now reviews through the bounded tree.
        raw = contract(7, 1)
        raw['review_chunk'] = 2
        self.repo.save(workflow.new_book(raw))
        owner = self.app.run(finish=True, source='工程夹具授权写完。')['owner']
        scope_tasks = []
        for _ in range(200):
            handoff = self.app.advance(owner=owner)
            if handoff['action'] == 'await_author':
                self.app.approve(handoff['prose_hash'], '工程夹具作者明确认可当前版本。', owner)
                continue
            if handoff['action'] != 'task_ready':
                break
            work = self.repo.task(handoff['task']['task_id'])['input']
            if work['stage'] in ('scope_review', 'scope_synthesis'):
                scope_tasks.append(work)
            self.app.submit(response(self.app))
        self.assertEqual(handoff['action'], 'ready_to_complete')
        self.assertTrue(any(w['stage'] == 'scope_synthesis' and w['payload'].get('children')
                            for w in scope_tasks))
        fanout = self.repo.load()['contract']['review_fanout']
        for work in scope_tasks:
            # A leaf reads one chunk; a synthesis reads at most its children's boundary chapters,
            # so no dispatch ever carries the whole 7-chapter volume the way the flat scheme did.
            self.assertLessEqual(len(work['prose']), 2 * fanout)
            self.assertLess(len(work['prose']), 7)

    def test_frozen_flat_synthesis_receipt_keeps_its_legacy_protocol(self):
        # Tasks frozen before the tree still submit through the per-chapter coverage branch.
        book = workflow.new_book(contract(2, 1))
        sources = {1: '第一章正文。', 2: '第二章正文。'}
        task = {'stage': 'scope_synthesis', 'chapter': 2, 'scope': 'volume:v1', 'first': 1, 'last': 2,
                'payload': {'review_key': 'legacy-key'}, 'blind': False, 'obligations': [],
                'checks_version': 1, 'capabilities': {}, 'narrative_tracking': False}
        from novel_ledger.contracts import checks_for
        data = {'verdict': 'pass', 'checks_version': 1, 'findings': [], 'obligations': [],
                'checks': [{'id': ident, 'result': 'pass', 'reason': '工程夹具。',
                            'evidence': [{'chapter': 1, 'quote': sources[1]}]} for ident in checks_for(1, 'long')],
                'coverage': [{'chapter': k, 'reason': '工程覆盖。', 'evidence': {'chapter': k, 'quote': v}}
                             for k, v in sources.items()]}
        outcome = workflow.apply(book, task, data, 'legacy-reviewer', sources)
        self.assertIn('legacy-key', outcome.book['reviews'])

    def test_scene_dependencies_reject_forward_links_and_preserve_explicit_identity(self):
        first = plan_extras({'chapter': 1, 'goal': '追问。'})
        first['scenes'][0].update(id='c1:warehouse', reads=[], depends_on=[])
        first['dependency_coverage'] = 'complete'
        story_memory.bind(first, {})
        second = plan_extras({'chapter': 2, 'goal': '追问。'})
        second['scenes'][0].update(id='c2:office', reads=[], depends_on=['c1:warehouse'])
        second['dependency_coverage'] = 'complete'
        story_memory.bind(second, {'1': first})
        self.assertEqual(second['scenes'][0]['id'], 'c2:office')
        invalid = copy.deepcopy(second)
        invalid['scenes'][0]['depends_on'] = ['c3:future']
        self.assertCode('story_dependency', story_memory.bind, invalid, {'1': first})
        del invalid['scenes'][0]['reads']
        self.assertCode('story_dependency', story_memory.bind, invalid, {'1': first})
        self.assertCode('story_dependency', story_memory.bind, {'chapter': 1, 'scenes': '错误格式'}, {})

    def test_explicit_offstage_inputs_are_included_with_frozen_provenance(self):
        book = self.repo.load()
        book['state']['entities']['other'] = {'id': 'other', 'name': '主管', 'kind': 'person'}
        book['state']['facts']['other:secret'] = '封条已更换。'
        plan = plan_extras({'chapter': 1, 'goal': '追问。', 'participants': ['shen'], 'node_ids': []})
        plan['scenes'][0].update(reads=[{'kind': 'facts', 'key': 'other:secret'}], depends_on=[])
        story_memory.bind(plan, {})
        book['plans']['1'] = plan
        work = context.build(self.repo, book, Job('write', 1))
        state = self.repo.read_document(work['records']['state'])
        self.assertEqual(state['facts']['other:secret'], '封条已更换。')
        packet = self.repo.read_document(work['records']['scene_context'])
        self.assertEqual(packet['plan'], plan)
        self.assertNotIn('plan', work['required'])
        self.assertEqual(packet['state_hash'], digest(book['state']))
        self.assertEqual(packet['plan_hash'], digest(plan))
        book['state']['facts']['other:secret'] = '后来的版本。'
        self.assertEqual(self.repo.read_document(work['records']['scene_context']), packet)

    def prepare_enhanced(self):
        raw = tracked_contract(3)
        raw['editorial_features'] = True
        self.repo.save(workflow.new_book(raw))
        owner = self.app.run(through=3, source='先写三章。')['owner']
        self.assertEqual(drive(self.app, owner)['action'], 'target_reached')
        return owner

    def test_scene_sources_bind_accepted_chapters_and_reject_uncommitted_links(self):
        self.prepare_enhanced()
        book = self.repo.load()
        first_scene = book['plans']['1']['scenes'][0]['id']
        book['plans']['2']['scenes'][0]['depends_on'] = [first_scene]
        work = context.build(self.repo, book, Job('repair', 2))
        source = self.repo.read_document(work['records']['scene_sources'])[0]
        self.assertEqual(source['prose_hash'], self.repo.chapter('main', 1)['prose'])
        self.assertEqual(source['scenes'][0]['id'], first_scene)
        book['plans']['2']['scenes'][0]['depends_on'] = ['c1:uncommitted']
        self.assertCode('story_dependency', context.build, self.repo, book, Job('repair', 2))

    def test_expression_revision_carries_suffix_and_still_requires_independent_review(self):
        owner = self.prepare_enhanced()
        third = self.repo.chapter('main', 3)
        analysis = self.app.revision_impact(2, {'mode': 'expression'})
        self.assertEqual((analysis['first'], analysis['last']), (2, 2))
        self.app.revise(2, '调整一句表达。', owner, changes={'mode': 'expression'})
        self.app.advance(owner=owner)
        result = enhanced_response(self.app)
        result['data']['prose'] = result['data']['prose'].replace('主管面前', '主管身前')
        self.app.submit(result)
        self.assertEqual(self.app.advance(owner=owner)['task']['stage'], 'chapter_review')
        self.assertEqual(drive(self.app, owner)['action'], 'revision_ready')
        book = self.repo.load()
        self.assertEqual(self.repo.chapter(book['branch'], 3)['prose'], third['prose'])
        self.assertEqual(self.repo.chapter('main', 3), third)
        self.assertEqual(book['rework']['2']['repairs'], 1)
        self.app.promote(owner)
        self.assertIsNone(self.repo.load()['revision_run'])

    def test_expression_revision_cannot_sneak_in_a_fact_change(self):
        owner = self.prepare_enhanced()
        self.app.revise(2, '调整表达。', owner, changes={'mode': 'expression'})
        self.app.advance(owner=owner)
        self.app.submit(enhanced_response(self.app))
        self.app.advance(owner=owner)
        candidate = enhanced_response(self.app)
        candidate['data']['facts']['events'].append({'op': 'state', 'entity': 'shen', 'key': 'alive',
            'before': None, 'after': True, 'evidence': {'chapter': 2, 'quote': '次日'}})
        before = self.repo.get('book')
        self.assertCode('revision_carry', self.app.submit, candidate)
        self.assertEqual(before, self.repo.get('book'))
        self.assertEqual(self.repo.pending()['id'], candidate['task_id'])

    def test_revision_analysis_is_read_only_and_narrower_semantic_override_is_refused(self):
        owner = self.prepare_enhanced()
        before = self.repo.get('book')
        changes = {'mode': 'semantic', 'changes': [{'kind': 'knowledge', 'key': 'shen:source'}]}
        impact = self.app.revision_impact(1, changes)
        self.assertEqual(impact['last'], 3)
        self.assertTrue(impact['conservative'])
        self.assertEqual(self.repo.get('book'), before)
        self.assertCode('revision_impact', self.app.revise, 1, '改变知情。', owner, 1, changes)
        self.assertEqual(self.repo.get('book'), before)
        self.assertIsNone(self.repo.load()['revision_run'])

    def test_base_mode_carry_checks_explicit_dependencies_even_without_impact_analysis(self):
        owner = self.app.run(through=3, source='工程夹具：检查场景依赖。')['owner']
        for _ in range(100):
            handoff = self.app.advance(owner=owner)
            if handoff['action'] == 'await_author':
                self.app.approve(handoff['prose_hash'], '工程夹具认可。', owner)
            elif handoff['action'] == 'task_ready':
                candidate = response(self.app)
                if handoff['task']['stage'] == 'plan':
                    for plan in candidate['data']['plans']:
                        plan.update(dependency_coverage='complete', scenes=[{
                            'reads': [] if plan['chapter'] == 1 else [{'kind': 'facts', 'key': 'shen:alive'}],
                            'depends_on': []}])
                self.app.submit(candidate)
            else:
                self.assertEqual(handoff['action'], 'target_reached')
                break
        else:
            self.fail('基础流程未结束。')
        # An incomplete change declaration and a manual narrow revision both need a runtime guard.
        for changes in ({'mode': 'semantic', 'changes': [{'kind': 'facts', 'key': 'shen:other'}]}, None):
            with self.subTest(changes=changes):
                self.app.revise(1, '工程夹具：改变实际依赖。', owner, 1, changes)
                self.app.advance(owner=owner)
                self.app.submit(response(self.app))
                self.app.advance(owner=owner)
                candidate = response(self.app)
                candidate['data']['facts']['events'].append({'op': 'state', 'entity': 'shen', 'key': 'alive',
                    'before': None, 'after': True, 'evidence': {'chapter': 1, 'quote': '次日'}})
                before = self.repo.get('book')
                self.assertCode('revision_carry', self.app.submit, candidate)
                self.assertEqual(before, self.repo.get('book'))
                self.app.discard(owner)

    def test_invalid_revision_endpoint_is_a_domain_error_without_mutation(self):
        owner = self.prepare_enhanced()
        before = self.repo.get('book')
        for through in ('2', True, [], 0, 4):
            with self.subTest(through=through):
                self.assertCode('revision', self.app.revise, 1, '改表达。', owner, through, {'mode': 'expression'})
                self.assertEqual(before, self.repo.get('book'))

    def test_revision_impact_cli_works_without_leaking_content_and_workers_cannot_call_it(self):
        self.prepare_enhanced()
        spec = Path(self.temp.name) / 'change.json'
        spec.write_text(json.dumps({'mode': 'expression'}), encoding='utf-8')
        command = [sys.executable, str(Path(__file__).resolve().parents[1] / 'scripts' / 'novel.py'),
                   '--project', str(self.project), 'revision-impact', '--from-chapter', '2', '--changes-file', str(spec)]
        before = self.repo.get('book')
        result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(json.loads(result.stdout)['last'], 2)
        self.assertNotIn('沈桐', result.stdout)
        self.assertEqual(self.repo.get('book'), before)
        env = {**os.environ, 'NOVEL_TASK_ID': 'fake-worker'}
        denied = subprocess.run(command, env=env, capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(json.loads(denied.stdout)['error'], 'worker_boundary')


class ImpactTests(unittest.TestCase):
    def chapters(self):
        rows = []
        for n in range(1, 5):
            plan = {'chapter': n, 'participants': [], 'dependency_coverage': 'complete',
                    'scenes': [{'id': 'c%d:s1' % n, 'reads': [], 'depends_on': []}]}
            rows.append({'n': n, 'chain': str(n), 'plan': plan, 'events': [],
                         'plan_hash': 'plan-' + str(n), 'events_hash': 'events-' + str(n)})
        rows[1]['plan']['scenes'][0]['reads'] = [{'kind': 'facts', 'key': 'shen:secret'}]
        rows[1]['events'] = [{'op': 'knowledge', 'entity': 'other', 'topic': 'source'}]
        rows[2]['plan']['scenes'][0]['reads'] = [{'kind': 'knowledge', 'key': 'other:source'}]
        return rows

    def test_semantic_changes_propagate_transitively_and_bind_sources(self):
        rows = self.chapters()
        impact = revision_impact.analyze(rows, 1, {'mode': 'semantic', 'changes': [{'kind': 'facts', 'key': 'shen:secret'}]})
        self.assertEqual(impact['rewrite_chapters'], [1, 2, 3])
        self.assertFalse(impact['conservative'])
        self.assertIsNone(impact['expansion'])
        self.assertEqual(impact['coverage'], 'complete')
        self.assertEqual(impact['sources'][1]['plan_hash'], 'plan-2')
        rows[2]['plan']['scenes'][0]['reads'] = []
        rows[2]['plan']['scenes'][0]['depends_on'] = ['c2:s1']
        self.assertEqual(revision_impact.analyze(rows, 1, {'mode': 'semantic', 'changes': [{'kind': 'facts', 'key': 'shen:secret'}]})['last'], 3)

    def test_missing_dependencies_or_unspecified_changes_expand_conservatively(self):
        rows = self.chapters()
        rows[3]['plan']['dependency_coverage'] = 'partial'
        impact = revision_impact.analyze(rows, 1, {'mode': 'semantic', 'changes': [{'kind': 'facts', 'key': 'shen:secret'}]})
        self.assertTrue(impact['conservative'])
        self.assertEqual(impact['last'], 4)
        # The widening is reported with its cause and size, not left implicit.
        self.assertEqual(impact['expansion'], {'reason': 'undeclared_dependencies', 'first': 1,
                                               'through': 4, 'chapters': 4})
        self.assertEqual(impact['coverage'], 'partial')
        self.assertEqual(revision_impact.analyze(self.chapters(), 1)['last'], 4)
        unknown = self.chapters()
        unknown[0]['events'] = [{'op': 'unmodelled'}]
        unexplained = revision_impact.analyze(unknown, 1, {'mode': 'semantic',
            'changes': [{'kind': 'facts', 'key': 'shen:secret'}]})
        self.assertEqual(unexplained['last'], 4)
        self.assertEqual(unexplained['expansion']['reason'], 'unexplained_events')

    def test_continuous_rewrite_propagates_outputs_of_intermediate_chapters(self):
        rows = self.chapters()
        rows[1]['plan']['scenes'][0]['reads'] = []
        rows[2]['plan']['scenes'][0]['reads'] = [{'kind': 'facts', 'key': 'shen:secret'}]
        rows[3]['plan']['scenes'][0]['reads'] = [{'kind': 'knowledge', 'key': 'other:source'}]
        impact = revision_impact.analyze(rows, 1, {'mode': 'semantic',
            'changes': [{'kind': 'facts', 'key': 'shen:secret'}]})
        self.assertEqual(impact['last'], 4)
        self.assertIn('c2:s1', impact['affected_scenes'])

    def test_node_events_propagate_their_implicit_thread_write(self):
        rows = self.chapters()
        rows[1]['events'] = [{'op': 'story_node', 'node': 'n2', 'line': 'main'}]
        rows[2]['plan']['scenes'][0]['reads'] = [{'kind': 'thread_progress', 'key': 'main'}]
        impact = revision_impact.analyze(rows, 1, {'mode': 'semantic',
            'changes': [{'kind': 'facts', 'key': 'shen:secret'}]})
        self.assertEqual(impact['last'], 3)

    def test_spatial_writes_with_derived_state_force_conservative_propagation(self):
        for op in ('travel', 'placement', 'move'):
            with self.subTest(op=op):
                rows = self.chapters()
                rows[1]['events'] = [{'op': op, 'entity': 'shen'}]
                impact = revision_impact.analyze(rows, 1, {'mode': 'semantic',
                    'changes': [{'kind': 'facts', 'key': 'shen:secret'}]})
                self.assertEqual(impact['last'], 4)
                self.assertTrue(impact['conservative'])


if __name__ == '__main__':
    unittest.main()
