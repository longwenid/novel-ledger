"""Synthetic protocol and transaction tests for the editorial surface v2 still owns.

v2 removed the reviewer roles, and with them the editorial decisions that existed only to arbitrate
a reviewer's receipt: alignment holds, root-remedy rounds and scope closure. What is left is the
part that is mechanical and still load-bearing — the effective contract (including a bounded append
that moved a volume's end), the context hash a revision plan is bound to, the bounded-revision
policy and its violations, plus the transaction guarantees around completion, delivery and the
lexical/fact settlement the editorial switch does not touch.
"""
import copy
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from novel_ledger import craft, creation, delivery, editorial, facts, workflow, bookpage
from novel_ledger.bootstrap import local_application as Application, local_workspace
from novel_ledger.contracts import Error, digest, dump
from novel_ledger.sqlite_store import SQLiteRepository
from support import contract, drive, response, seeded_book, tracked_contract
import quality_eval
import observe


class EditorialTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / 'book'
        raw = contract()
        raw.update(narrative_tracking=True, editorial_features=True)
        self.repo = SQLiteRepository.initialize(self.project, seeded_book(raw))
        self.app = Application(self.repo)

    def tearDown(self):
        self.repo.close()
        self.temp.cleanup()

    def assertCode(self, code, fn, *args, **kwargs):
        with self.assertRaises(Error) as caught:
            fn(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)

    def test_completion_delivery_is_frozen_and_survives_a_write_failure(self):
        """The completion snapshot is delivered under a frozen version: a later projection change
        does not alter it, and a failed write leaves the content complete for a same-snapshot retry."""
        owner = self.app.run(finish=True)['owner']
        self.assertEqual(drive(self.app, owner)['action'], 'ready_to_complete')
        complete = self.app.complete(owner)
        result = delivery.deliver_completion(self.repo, bookpage.render, workspace=local_workspace(self.repo))
        first = Path(result['files'][0]['path']).read_text(encoding='utf-8')
        b = self.repo.load()
        b['contract']['title'] = '当前投影标题变化不改变完本快照'
        self.repo.save(b)
        repeated = delivery.deliver_completion(self.repo, bookpage.render, workspace=local_workspace(self.repo))
        self.assertEqual(Path(repeated['files'][0]['path']).read_text(encoding='utf-8'), first)
        self.assertEqual(result['snapshot_hash'], complete['snapshot_hash'])
        self.assertEqual(result['chapters'], repeated['chapters'])
        self.assertEqual(result['files'], repeated['files'])

        self.tearDown()
        self.setUp()
        owner = self.app.run(finish=True)['owner']
        drive(self.app, owner)
        complete = self.app.complete(owner)
        with patch('novel_ledger.delivery.atomic_write', side_effect=OSError('工程写盘故障')):
            with self.assertRaises(OSError):
                delivery.deliver_completion(self.repo, bookpage.render, workspace=local_workspace(self.repo))
        self.assertEqual(self.repo.load()['status'], 'completed')
        result = delivery.deliver_completion(self.repo, bookpage.render, workspace=local_workspace(self.repo))
        self.assertEqual(result['snapshot_hash'], complete['snapshot_hash'])

    def test_active_feature_protocol_cannot_downgrade_to_skip_the_editorial_checks(self):
        raw = contract()
        self.assertCode('editorial_protocol', self.app.recontract, raw, '试图关闭编辑能力。')

    def test_a_declared_deviation_requires_prose_repair_under_the_same_fixed_outline(self):
        owner = self.app.run(through=2, source='工程夹具：两章。')['owner']
        drive(self.app, owner, until='write')
        original = copy.deepcopy(self.repo.load()['plans'])
        result = response(self.app)
        result['data']['drift_check']['items'][0].update(
            status='deviated', reason='正文只推进了一部分，剩下留到下一章。')
        result['data']['drift_check']['verdict'] = 'deviated'
        self.assertIsNone(self.app.submit(result)['committed_chapter'])
        book = self.repo.load()
        self.assertEqual(book['plans'], original)
        self.assertEqual(book['design_drift'], [])
        self.assertIn('outline_alignment', {f['criterion'] for f in book['draft']['findings']})
        self.assertEqual(self.app.advance(owner=owner)['task']['stage'], 'repair')
        self.assertEqual(self.app.submit(response(self.app))['committed_chapter'], 1)
        handoff = self.app.advance(owner=owner)
        self.assertEqual(handoff['action'], 'await_author')
        self.app.approve(handoff['prose_hash'], '工程夹具认可修复后的首章。', owner)
        self.assertEqual(self.app.advance(owner=owner)['task']['stage'], 'write')
        self.assertEqual(self.repo.load()['plans'], original)

    def test_effective_contract_resolves_bounds_and_a_bounded_append(self):
        book = workflow.new_book(contract(4))
        self.assertEqual([(v['first'], v['end']) for v in editorial.effective_contract(book)['volumes']],
                         [(1, 4)])
        book['scope_ends'] = {'v1': 6}
        self.assertEqual([(v['first'], v['end']) for v in editorial.effective_contract(book)['volumes']],
                         [(1, 6)])
        # The contract itself is never rewritten by a bounded scope decision.
        self.assertEqual(book['contract']['volumes'][0]['end'], 4)

    def test_revision_policy_bounds_the_window_and_names_every_violation(self):
        """A volume is closed once every chapter of it is on record; the window is the contract's."""
        book = workflow.new_book(contract(6, 2))
        policy = editorial.revision_policy(book, 5)
        self.assertEqual((policy['limit'], policy['earliest'], policy['head']), (3, 3, 5))
        self.assertEqual([(v['id'], v['first'], v['last']) for v in policy['closed_volumes']], [('v1', 1, 3)])
        self.assertEqual(editorial.revision_violations(policy, {'first': 4, 'last': 5}), [])
        self.assertIn('outside_recent_window', editorial.revision_violations(policy, {'first': 2, 'last': 2}))
        self.assertIn('rewrite_limit', editorial.revision_violations(policy, {'first': 1, 'last': 5}))
        self.assertIn('closed_volume', editorial.revision_violations(policy, {'first': 3, 'last': 3}))
        # Once a volume is written to its end it counts as closed, so further work in it is an
        # author decision rather than an automatic repair.
        self.assertIn('closed_volume', editorial.revision_violations(editorial.revision_policy(book, 6),
                                                                    {'first': 5, 'last': 6}))
        # A bounded append moves that end out, so the same head leaves the volume open again.
        book['scope_ends'] = {'v2': 8}
        self.assertEqual([(v['first'], v['end']) for v in editorial.effective_contract(book)['volumes']],
                         [(1, 3), (4, 8)])
        self.assertEqual([v['id'] for v in editorial.revision_policy(book, 6)['closed_volumes']], ['v1'])

    def test_context_hash_tracks_the_contract_and_the_style_anchor(self):
        book = workflow.new_book(contract(2))
        first = editorial.context_hash(book)
        self.assertEqual(editorial.context_hash(copy.deepcopy(book)), first)
        book['style_anchor'] = {'prose_hash': 'h', 'sample': '正文样本。'}
        changed = editorial.context_hash(book)
        self.assertNotEqual(changed, first)
        book['contract']['title'] = '改约后的书名'
        self.assertNotEqual(editorial.context_hash(book), changed)

    def test_patch_is_atomic_counts_budget_and_still_requires_a_new_receipt(self):
        drive(self.app, until='write')
        first = response(self.app)
        first['data']['prose'] = first['data']['prose'].replace('要求先核对', '要求先 check 再核对')
        self.app.submit(first)
        original = self.repo.load()['draft']['prose']
        self.app.feedback('把西文残留改回中文。')
        handoff = self.app.advance()
        self.assertEqual(handoff['task']['stage'], 'repair')
        result = response(self.app)
        result['data'].pop('prose')
        result['data'].update(craft.patch_at(original, 'check', '核对'), repair_note='只把残留词改回中文。')
        broken = copy.deepcopy(result)
        broken['data']['patches'][0]['start'] += 1
        self.assertCode('patch', self.app.submit, broken)
        self.assertEqual(self.repo.load()['draft']['prose'], original)
        before = copy.deepcopy(self.repo.load()['rework'])
        self.app.submit(result, preview=True)
        self.assertEqual(self.repo.load()['rework'], before)
        self.app.submit(result)
        self.assertEqual(self.repo.load()['rework']['1']['repairs'], 1)
        # A replay of the same receipt is idempotent; the chapter is on record now.
        self.assertTrue(self.app.submit(result)['idempotent'])
        self.assertEqual([row['n'] for row in self.repo.headers('main')], [1])

    def test_chapter_outline_scenes_are_validated_and_bound(self):
        """A chapter outline that declares scenes enters the scene protocol, not a free-text field.

        The row's `present` must be its own cast, `speakers` must state who talks, and one
        `dialogue_intent` per speaker is required — the check a live run used to pay a reviewer for.
        Accepting the row binds its scene identity and reading dependencies, which a later revision's
        carry reads back.
        """
        drive(self.app, until='chapter_outline')
        result = response(self.app)
        row = result['data']['chapters'][0]
        row['scenes'] = [{'id': 'scene:warehouse', 'label': '夜班仓库', 'present': ['shen'], 'speakers': ['shen'],
                          'intent': '追问签字责任。', 'conflict': '主管不愿核对。', 'turn': '要求公开来源。',
                          'reads': [], 'depends_on': [],
                          'dialogue_intents': [{'entity': 'shen', 'seeks': '核实经手人。',
                                                'withholds': '暂不说自己开过箱。', 'pressure': '可能失业。',
                                                'tactic': '先请对方解释封条。', 'knowledge_topics': []}]}]
        obsolete = copy.deepcopy(result)
        obsolete['data']['chapters'][0]['expansion_units'] = []
        self.assertCode('chapter_outline', self.app.submit, obsolete)
        self.assertEqual(self.repo.load()['chapter_outlines'], {})
        broken = copy.deepcopy(result)
        broken['data']['chapters'][0]['scenes'][0]['dialogue_intents'] = []
        self.assertCode('dialogue', self.app.submit, broken)
        self.assertEqual(self.repo.load()['chapter_outlines'], {})
        self.app.submit(result)
        accepted = self.repo.load()['chapter_outlines']['v1'][0]
        self.assertEqual(accepted['scenes'][0]['id'], 'scene:warehouse')
        self.assertEqual(accepted.get('scene_schema'), 'scene-identity/2')

    def test_partial_intake_skips_only_already_decided_gates(self):
        state = creation.begin()
        voice = {'pov': '第三人称限知，只跟沈桐的所见与所知。', 'voice': '具体动作与有立场的对白。',
                 'style_traits': ['少重复解释。']}
        state = creation.intake(state, {'voice': voice, 'title': {'title': '夜班退件'}}, '作者已给文风和书名。')
        self.assertEqual(creation.current(state)['id'], 'genre')
        self.assertEqual(creation.selected(state)['voice'], voice)
        self.assertEqual(creation.selected(state)['title'], {'title': '夜班退件'})
        self.assertCode('intake', creation.intake, state, {'title': {'title': '改名。'}}, '冲突')
        reopened = creation.back(state, 'voice', '重开文风。')
        self.assertNotIn('voice', creation.selected(reopened))
        self.assertNotIn('title', creation.selected(reopened))

    def test_usage_counts_actual_reads_without_inventing_billed_tokens(self):
        drive(self.app, until='write')
        task = self.repo.pending()
        self.app.read(task['id'])
        usage = self.app.usage()
        self.assertGreater(usage['supplemental_read_chars'], 0)
        self.assertIsNone(usage['billed_tokens'])

    def test_anchor_paths_and_custody_rules_are_distinct_and_enforced(self):
        """A fixed anchor refuses contradiction, a path demands its own arrival time, and custody
        (holder-bound location) is its own rule: a plain placement cannot teleport a held entity."""
        raw = tracked_contract()
        raw.update(editorial_features=True, places=[{'id': 'a', 'name': '仓库'}, {'id': 'b', 'name': '办公室'}],
                   placements={'shen': 'a'}, anchors=[{'entity': 'shen', 'key': 'hand', 'value': '右', 'policy': 'fixed'}],
                   links=[{'id': 'walk', 'a': 'a', 'b': 'b', 'kind': 'path', 'min_days': 2}])
        state = facts.seed(raw)
        self.assertCode('anchor_fixed', facts.settle, state, [{'op': 'anchor_assert', 'entity': 'shen', 'key': 'hand', 'value': '左', 'evidence': {'chapter': 1, 'quote': '次日'}}], '次日', 1)
        travel = {'op': 'travel', 'entity': 'shen', 'from': 'a', 'to': 'b', 'links': ['walk'], 'depart': 0, 'arrive': 1, 'evidence': {'chapter': 1, 'quote': '次日'}}
        self.assertCode('path_time', facts.settle, state, [travel], '次日', 1)
        travel['arrive'] = 2
        moved, _ = facts.settle(state, [travel], '次日', 1)
        self.assertEqual(moved['placements']['shen'], 'b')
        travel.update(**{'from': 'b', 'to': 'a', 'depart': 0, 'arrive': 2})
        travel['evidence']['chapter'] = 2
        self.assertCode('path_time', facts.settle, moved, [travel], '次日', 2)
        teleport = {'op': 'placement', 'entity': 'shen', 'before': {'place': 'a'}, 'after': {'place': 'b'}, 'evidence': {'chapter': 1, 'quote': '次日'}}
        self.assertCode('custody', facts.settle, state, [teleport], '次日', 1)

        # Custody preserves the arrival bound, and a path grants movement, not sight.
        raw = tracked_contract()
        raw.update(editorial_features=True, entities=[{'id': e, 'name': e, 'kind': 'person' if e != 'box' else 'object'} for e in ('shen', 'other', 'box')],
                   places=[{'id': 'a', 'name': '仓库'}, {'id': 'b', 'name': '办公室'}], placements={'shen': 'a', 'other': 'b', 'box': 'a'},
                   links=[{'id': 'walk', 'a': 'a', 'b': 'b', 'kind': 'path', 'min_days': 2}])
        state = facts.seed(raw)
        ref = {'chapter': 1, 'quote': '次日'}
        perceive = {'op': 'perceive', 'observer': 'shen', 'target': 'other', 'channel': 'sight', 'from': 'a', 'to': 'b', 'link': 'walk', 'evidence': ref}
        self.assertCode('path', facts.settle, state, [perceive], '次日', 1)
        pickup = {'op': 'placement', 'entity': 'box', 'before': {'place': 'a'}, 'after': {'holder': 'shen'}, 'evidence': ref}
        travel = {'op': 'travel', 'entity': 'shen', 'from': 'a', 'to': 'b', 'links': ['walk'], 'depart': 0, 'arrive': 2, 'evidence': ref}
        transfer = {'op': 'placement', 'entity': 'box', 'before': {'holder': 'shen'}, 'after': {'holder': 'other'}, 'evidence': ref}
        moved, _ = facts.settle(state, [pickup, travel, transfer], '次日', 1)
        self.assertEqual(moved['arrivals']['box'], 2)
        travel.update(entity='other', **{'from': 'b', 'to': 'a', 'depart': 1, 'arrive': 3})
        self.assertCode('path_time', facts.settle, moved, [travel], '次日', 1)


class EvaluationTests(unittest.TestCase):
    def test_first_read_refuses_to_write_inside_skill_tree(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp).resolve()
            with patch.object(quality_eval, 'ROOT', base):
                with self.assertRaises(Error) as caught:
                    quality_eval.seal(base / 'case' / 'input.json', base / 'receipt.json')
            self.assertEqual(caught.exception.code, 'project_isolation')
            self.assertFalse((base / 'case' / 'first-read.json').exists())

    def test_malformed_review_rows_are_rejected_as_domain_errors(self):
        work = {'case_id': 'case', 'chapters': [{'chapter': 1, 'prose': '正文'}]}
        evidence = [{'chapter': 1, 'start': 0, 'quote': '正文'}]
        review = {'case_id': 'case', 'input_hash': digest(work), 'first_read': {'reads': []},
                  'checks': [{'id': c, 'result': 'pass', 'reason': '工程判断。', 'evidence': evidence}
                             for c in quality_eval.CRITERIA], 'findings': []}
        for changes in ({'checks': [None]}, {'findings': [None]},
                        {'findings': [{'id': 'cost', 'severity': 'major', 'reason': '缺 criterion。', 'evidence': evidence}]},
                        {'findings': [{'criterion': 'cost', 'severity': 'major', 'reason': '坏证据。', 'evidence': [None]}]},
                        {'findings': [{'criterion': 'cost', 'severity': 'major', 'reason': '不能免证据。',
                                       'result': 'not_applicable', 'evidence': []}]}):
            with self.subTest(changes=changes), self.assertRaises(Error):
                quality_eval.validate_review(work, {**review, **changes})

    def test_observation_deduplication_unknown_usage_and_conflict(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'host.jsonl'
            row = {'provider': 'test', 'session_id': 's', 'request_id': 'r', 'input_tokens': 10, 'cache_read_tokens': 5, 'output_tokens': 2}
            path.write_text(dump(row) + '\n' + dump(row), encoding='utf-8')
            self.assertEqual(observe.summarize(path)['gross_tokens'], 17)
            path.write_text(dump(row) + '\n' + dump({**row, 'output_tokens': 3}), encoding='utf-8')
            with self.assertRaises(Error):
                observe.summarize(path)
            path.write_text(dump({**row, 'output_tokens': None}), encoding='utf-8')
            self.assertIsNone(observe.summarize(path)['gross_tokens'])

    def test_blind_cases_hide_expectations_and_freeze_first_read(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            (base / 'chapter.txt').write_text('次日，他选择承担责任。', encoding='utf-8')
            manifest = {'chapters': [{'chapter': 1, 'path': 'chapter.txt'}], 'cases': [{'label': '私有原稿', 'expectations': []}]}
            (base / 'manifest.json').write_text(dump(manifest), encoding='utf-8')
            result = quality_eval.prepare(base / 'manifest.json', base / 'run')
            case = result['cases'][0]
            work = json.loads(Path(case['input']).read_text(encoding='utf-8'))
            self.assertNotIn('私有原稿', dump(work))
            first = {'case_id': work['case_id'], 'input_hash': digest(work), 'data': {'reads': [
                {'chapter': 1, 'desire': '承担责任。', 'obstacle': '处境危险。', 'change': '选择行动。', 'read_on_reason': '后果如何。'}]}}
            receipt = base / 'first.json'
            receipt.write_text(dump(first), encoding='utf-8')
            quality_eval.seal(case['input'], receipt)
            first['data']['reads'][0]['change'] = '改写首读。'
            receipt.write_text(dump(first), encoding='utf-8')
            with self.assertRaises(Error):
                quality_eval.seal(case['input'], receipt)

    def test_literary_scoring_counts_localized_seed_and_keeps_unadjudicated_precision_unknown(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            prose = '次日，他交出三文钱。'
            (base / 'chapter.txt').write_text(prose, encoding='utf-8')
            manifest = {'chapters': [{'chapter': 1, 'path': 'chapter.txt'}], 'cases': [{'label': '私有变体', 'edits': [
                {'chapter': 1, 'start': prose.index('三'), 'old': '三', 'new': '九', 'criterion': 'cost'}]}]}
            (base / 'manifest.json').write_text(dump(manifest), encoding='utf-8')
            prepared = quality_eval.prepare(base / 'manifest.json', base / 'run')
            case = prepared['cases'][0]
            work = json.loads(Path(case['input']).read_text(encoding='utf-8'))
            first = {'case_id': work['case_id'], 'input_hash': digest(work), 'data': {'reads': [
                {'chapter': 1, 'desire': '交钱。', 'obstacle': '钱不够。', 'change': '交出钱。', 'read_on_reason': '看后果。'}]}}
            (base / 'first.json').write_text(dump(first), encoding='utf-8')
            quality_eval.seal(case['input'], base / 'first.json')
            quote = work['chapters'][0]['prose']
            evidence = [{'chapter': 1, 'start': 0, 'quote': quote}]
            review = {'case_id': work['case_id'], 'input_hash': digest(work), 'first_read': first['data'],
                      'checks': [{'id': c, 'result': 'fix' if c == 'cost' else 'pass', 'reason': '工程定位样本。', 'evidence': evidence}
                                 for c in quality_eval.CRITERIA],
                      'findings': [{'criterion': 'cost', 'severity': 'major', 'reason': '工程植入数字差异。', 'evidence': evidence}]}
            Path(case['output']).write_text(dump(review), encoding='utf-8')
            scored = quality_eval.score(base / 'run')
            self.assertEqual(scored['seeded']['true_positive'], 1)
            self.assertIsNone(scored['adjudicated']['precision'])


if __name__ == '__main__':
    unittest.main()
