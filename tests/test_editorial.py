"""Synthetic protocol and transaction tests. No model or literary approval is implied."""
import copy
import json
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from test_narrative import tracked_contract, tracked_response, story_node, pace
from novel_ledger import craft, creation, delivery, editorial, facts, workflow, bookpage
from novel_ledger.bootstrap import local_application as Application, local_workspace
from novel_ledger.contracts import Error, digest, dump
from novel_ledger.sqlite_store import SQLiteRepository
import quality_eval
import observe


def plan_extras(plan):
    plan['scenes'] = [{'label': '夜班仓库', 'present': ['shen'], 'speakers': ['shen'], 'intent': '追问签字责任。',
                       'conflict': '主管不愿核对。', 'turn': '要求公开来源。', 'dialogue_intents': [
                           {'entity': 'shen', 'seeks': '核实经手人。', 'withholds': '暂不说自己开过箱。',
                            'pressure': '可能失业。', 'tactic': '先请对方解释封条。', 'knowledge_topics': []}]}]
    plan['expansion_units'] = [{'id': 'u1', 'scene': 1, 'focus': '核对封条。', 'development': '主管拒绝后换证据试探。',
                                'expected_change': '留下选择违规的原因及代价。'}]
    return plan


def enhanced_response(app):
    pending = app.repo.pending()
    if pending['input']['stage'] == 'alignment_plan':
        chapter = pending['input']['chapter']
        book = app.repo.load()
        plan = copy.deepcopy(book['plans'].get(str(chapter), book.get('alignment_hold', {}).get('original_plan')))
        if plan:
            plan['chapter'] = chapter
        return {'schema': 'novel-ledger.result/1', 'task_id': pending['id'], 'input_hash': pending['input_hash'],
                'session': 'engineering-' + uuid.uuid4().hex,
                'data': {'reason': '保全成立正文并对齐实际节点。', 'plan': plan, 'designs': []}}
    result = tracked_response(app)
    work = app.repo.pending()['input']
    data, stage = result['data'], work['stage']
    book = app.repo.load()
    if stage == 'plan':
        for plan in data['plans']:
            plan_extras(plan)
    elif stage == 'profiles':
        for profile in data['profiles']:
            profile.update(tier='major', biography={'public_role': '夜班工人', 'contradiction': '查明责任也怕牵连同事。', 'values': '先保住同事，再核对责任。'},
                           speech={'register': '具体直接。', 'tactics': ['先问经手细节。'], 'rhythm': '追问后留停顿。',
                                   'stress_shift': '被怀疑时反而少说。', 'relationship_modes': []}, change_reason='核对实际成长。')
    elif stage == 'chapter_review':
        data['alignment'] = {'action': 'follow_plan', 'reason': '工程样本按冻结计划实现。', 'realizations': [
            {'node': e['node'], 'after': e['after'], 'reason': '工程样本已演出行动。', 'evidence': e['evidence']}
            for e in data['facts']['events'] if e['op'] == 'story_node']}
    elif stage == 'scope_synthesis':
        if 'closure' in data:
            data['closure']['decision'] = 'accept_close'
            ref = {'chapter': work['first'], 'quote': '次日'}
            for row in data['closure']['checks']:
                row.update(result='pass', reason='工程样本核对职责。', evidence=[ref])
            for row in data['closure'].get('completion_coverage', []):
                row.update(result='fulfilled', reason='工程样本核对来源。', evidence=[ref])
            if 'prose_hashes' in data['closure']:
                data['closure'].update(source_coverage_checked=True, cross_chunk_checked=True)
        for row in data.get('remedy_review', []):
            row.update(result='pass', reason='工程样本原目标验收。', evidence={'chapter': work['first'], 'quote': '次日'})
    elif stage == 'alignment_plan':
        chapter = work['chapter']
        plan = copy.deepcopy(book['plans'].get(str(chapter), book.get('alignment_hold', {}).get('original_plan')))
        if plan:
            plan['chapter'] = chapter
        data = {'reason': '保全成立正文并对齐实际节点。', 'plan': plan, 'designs': []}
        result['data'] = data
    return result


def drive(app, owner=None, until=None):
    for _ in range(300):
        handoff = app.advance(owner=owner)
        if handoff['action'] == 'await_author':
            app.approve(handoff['prose_hash'], '工程作者认可准确首章。', owner)
        elif handoff['action'] != 'task_ready':
            return handoff
        elif until and app.repo.pending()['input']['stage'] == until:
            return handoff
        else:
            app.submit(enhanced_response(app))
    raise AssertionError('工程流没有在有界步骤结束')


class EditorialTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        raw = tracked_contract(3)
        raw['editorial_features'] = True
        self.repo = SQLiteRepository.initialize(Path(self.temp.name) / 'book', workflow.new_book(raw))
        self.app = Application(self.repo)

    def tearDown(self):
        self.repo.close()
        self.temp.cleanup()

    def assertCode(self, code, fn, *args, **kwargs):
        with self.assertRaises(Error) as caught:
            fn(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)

    def root(self):
        owner = self.app.run(finish=True)['owner']
        for _ in range(200):
            h = self.app.advance(owner=owner)
            if h['action'] == 'await_author':
                self.app.approve(h['prose_hash'], '工程准确批准。', owner)
                continue
            work = self.repo.pending()['input']
            if work['stage'] == 'scope_synthesis' and work['payload'].get('closure'):
                return owner
            self.app.submit(enhanced_response(self.app))
        self.fail('没有卷末 root')

    def fix_closure(self, decision):
        result = enhanced_response(self.app)
        data = result['data']
        ref = {'chapter': self.repo.pending()['input']['last'], 'quote': '次日'}
        data['verdict'] = 'fix'
        next(r for r in data['checks'] if r['id'] == 'payoffs')['result'] = 'fix'
        data['findings'] = [{'criterion': 'payoffs', 'severity': 'quality', 'reason': '余波尚未演出。', 'evidence': ref,
                             'target_chapter': ref['chapter'], 'repair_scope': 'chapter'}]
        closure = data['closure']
        closure.update(decision=decision, repair_case={'root_ref': 'volume:v1:aftermath', 'goal': '演出工人承担责任后的关系变化。',
                                                     'verification_condition': '关系变化有具体动作和后果。', 'evidence': ref},
                       remedy={'mechanism': '余波场景。', 'substantive_change': '补实主管对违规的处理。'})
        closure['checks'][4]['result'] = 'missing' if decision == 'continue_scope' else 'defect'
        if decision == 'revise_range' and 'revision_policy' in self.repo.pending()['input']['payload']['closure']:
            closure['changes'] = {'mode': 'expression'}
        return result

    def test_complete_snapshot_and_recover_delivery_use_frozen_version(self):
        owner = self.app.run(finish=True)['owner']
        self.assertEqual(drive(self.app, owner)['action'], 'ready_to_complete')
        complete = self.app.complete(owner)
        result = delivery.deliver_completion(self.repo, bookpage.render, workspace=local_workspace(self.repo))
        first = Path(result['files'][0]['path']).read_text()
        b = self.repo.load()
        b['contract']['title'] = '当前投影标题变化不改变完本快照'
        self.repo.save(b)
        repeated = delivery.deliver_completion(self.repo, bookpage.render, workspace=local_workspace(self.repo))
        self.assertEqual(Path(repeated['files'][0]['path']).read_text(), first)
        self.assertEqual(result['snapshot_hash'], complete['snapshot_hash'])
        self.assertEqual(result['chapters'], repeated['chapters'])
        self.assertEqual(result['files'], repeated['files'])

    def test_delivery_failure_keeps_content_complete_and_retry_uses_same_snapshot(self):
        owner = self.app.run(finish=True)['owner']
        drive(self.app, owner)
        complete = self.app.complete(owner)
        with patch('novel_ledger.delivery.atomic_write', side_effect=OSError('工程写盘故障')):
            with self.assertRaises(OSError):
                delivery.deliver_completion(self.repo, bookpage.render, workspace=local_workspace(self.repo))
        self.assertEqual(self.repo.load()['status'], 'completed')
        result = delivery.deliver_completion(self.repo, bookpage.render, workspace=local_workspace(self.repo))
        self.assertEqual(result['snapshot_hash'], complete['snapshot_hash'])

    def test_active_feature_protocol_cannot_downgrade_to_skip_closure(self):
        raw = tracked_contract(3)
        self.assertCode('editorial_protocol', self.app.recontract, raw, '试图关闭编辑能力。')

    def test_explicit_recontract_supersedes_the_current_alignment_dispatch(self):
        drive(self.app, until='chapter_review')
        result = enhanced_response(self.app)
        result['data']['alignment']['action'] = 'align_design'
        self.app.submit(result)
        self.assertIsNotNone(self.repo.load().get('alignment_hold'))
        changed = copy.deepcopy(self.repo.load()['contract'])
        changed['reader_promise'] = '工程作者明确改约以调整阅读承诺。'
        self.app.recontract(changed, '工程作者明确要求改约。')
        self.assertEqual(self.app.advance()['task']['stage'], 'contract_review')
        self.app.submit(enhanced_response(self.app))
        self.assertEqual(self.app.advance()['task']['stage'], 'book_plan')
        self.assertEqual(self.repo.load()['contract']['reader_promise'], changed['reader_promise'])

    def test_completion_source_coverage_cannot_omit_requirement(self):
        owner = self.root()
        self.app.submit(enhanced_response(self.app))
        drive(self.app, owner, 'scope_synthesis')
        result = enhanced_response(self.app)
        self.assertEqual(self.repo.pending()['input']['scope'], 'book')
        result['data']['closure']['completion_coverage'].pop()
        self.assertCode('completion_coverage', self.app.submit, result)
        self.assertNotIn('book', self.repo.load()['scope_closures'])

    def test_scene_dialogue_and_expansion_are_validated(self):
        drive(self.app, until='plan')
        result = enhanced_response(self.app)
        result['data']['plans'][0]['scenes'][0]['speakers'] = []
        self.assertCode('dialogue', self.app.submit, result)
        self.assertEqual(self.repo.load()['plans'], {})

    def test_blind_envelope_hides_baseline_and_new_editorial_material(self):
        drive(self.app, until='chapter_review')
        task = self.app.advance()['task']
        self.assertIsNone(task['baseline'])
        self.assertNotIn('records', task)
        self.assertNotIn('alignment', task['brief'])
        self.assertFalse(Path(task['task_path']).with_name('input.json').exists())

    def test_growth_rebuilds_interpretation_before_next_writer(self):
        owner = self.app.run(finish=True)['owner']
        drive(self.app, owner, 'chapter_review')
        result = enhanced_response(self.app)
        result['data']['facts']['events'].append({'op': 'character_development', 'entity': 'shen', 'choice': '要求主管核对。',
                                                 'cost': '承担违规。', 'change': '更愿意为同事担责。', 'evidence': {'chapter': 1, 'quote': '次日'}})
        self.app.submit(result)
        self.app.approve(self.repo.chapter('main', 1)['prose'], '工程认可。', owner)
        self.assertEqual(self.app.advance(owner=owner)['task']['stage'], 'profiles')
        profile = enhanced_response(self.app)
        profile['data']['profiles'][0].pop('change_reason')
        self.assertCode('profile', self.app.submit, profile)

    def test_patch_is_atomic_counts_budget_and_still_requires_new_review(self):
        drive(self.app, until='chapter_review')
        original = self.repo.load()['draft']['prose']
        self.app.feedback('将空白的责任栏改为责任栏。')
        self.app.advance()
        result = enhanced_response(self.app)
        result['data'].pop('prose')
        result['data'].update(craft.patch_at(original, '空白的责任栏', '责任栏'), repair_note='只删无作用修饰。')
        broken = copy.deepcopy(result)
        broken['data']['patches'][0]['start'] += 1
        self.assertCode('patch', self.app.submit, broken)
        self.assertEqual(self.repo.load()['draft']['prose'], original)
        before = copy.deepcopy(self.repo.load()['rework'])
        self.app.submit(result, preview=True)
        self.assertEqual(self.repo.load()['rework'], before)
        self.app.submit(result)
        self.assertEqual(self.repo.load()['rework']['1']['repairs'], 1)
        h = self.app.advance()
        self.assertEqual(h['task']['delivery_phase'], 'first_read')
        self.assertTrue(self.app.submit(result)['idempotent'])

    def test_alignment_hold_keeps_prose_and_requires_independent_replanning(self):
        drive(self.app, until='chapter_review')
        result = enhanced_response(self.app)
        result['data']['alignment'].update(action='align_design', reason='实际正文可成立，核验新的承接。')
        original = self.repo.load()['draft']['prose']
        budget = copy.deepcopy(self.repo.load()['rework'])
        self.app.submit(result)
        self.assertEqual(self.repo.headers('main'), [])
        self.assertEqual(self.app.advance()['task']['stage'], 'alignment_plan')
        self.app.submit(enhanced_response(self.app))
        self.assertEqual(self.app.advance()['task']['stage'], 'alignment_review')
        self.app.submit(enhanced_response(self.app))
        self.assertEqual(self.repo.load()['draft']['prose'], original)
        self.assertEqual(self.repo.load()['rework'], budget)
        self.assertEqual(self.app.advance()['task']['delivery_phase'], 'first_read')

    def test_adapt_future_commits_actual_progress_and_blocks_next_writer_until_reviewed(self):
        owner = self.app.run(finish=True)['owner']
        drive(self.app, owner, 'chapter_review')
        result = enhanced_response(self.app)
        result['data']['alignment']['action'] = 'adapt_future'
        self.app.submit(result)
        self.app.approve(self.repo.chapter('main', 1)['prose'], '工程批准。', owner)
        self.assertEqual(self.app.advance(owner=owner)['task']['stage'], 'alignment_plan')
        self.assertEqual(len(self.repo.headers('main')), 1)

    def test_partial_realization_extends_window_without_rewriting_or_forging_completion(self):
        owner = self.app.run(finish=True)['owner']
        drive(self.app, owner, 'chapter_review')
        result = enhanced_response(self.app)
        result['data']['alignment'].update(action='adapt_future', reason='第一章只是推进，第二章兑现。')
        result['data']['alignment']['realizations'][0]['after'] = 'advanced'
        result['data']['facts']['events'][1]['after'] = 'advanced'
        result['data']['facts']['events'] = [e for e in result['data']['facts']['events'] if e['op'] != 'story_thread']
        untouched = copy.deepcopy(result)
        self.app.submit(result)
        self.assertEqual(result, untouched)
        self.assertTrue(self.app.submit(untouched)['idempotent'])
        self.assertEqual(self.repo.load()['state']['story_nodes']['n1']['status'], 'advanced')
        self.assertEqual(self.app.advance(owner=owner)['action'], 'await_author')
        self.app.approve(self.repo.chapter('main', 1)['prose'], '工程批准该准确版本。', owner)
        self.app.advance(owner=owner)
        proposal = enhanced_response(self.app)
        design = copy.deepcopy(self.repo.load()['designs']['book'])
        design['nodes'][0]['window'] = [1, 2]
        plan = proposal['data']['plan']
        plan['node_ids'] = ['n1', 'n2']
        plan['node_actions'] = [{'node': 'n1', 'after': 'resolved'}, {'node': 'n2', 'after': 'resolved'}]
        proposal['data']['designs'] = [{'scope': 'book', 'data': design}]
        self.app.submit(proposal)
        self.app.advance(owner=owner)
        self.app.submit(enhanced_response(self.app))
        drive(self.app, owner, 'chapter_review')
        self.app.submit(enhanced_response(self.app))
        self.assertEqual(self.repo.load()['state']['story_nodes']['n1']['status'], 'resolved')
        self.assertTrue(self.app.audit()['ok'])

    def test_required_effect_criteria_cannot_be_replaced_by_node_status(self):
        drive(self.app, until='chapter_review')
        plan = copy.deepcopy(self.repo.load()['plans']['1'])
        plan['node_contracts']['n1']['effects'] = [{'id': 'cost', 'text': '处分生效。'}]
        plan['node_contracts']['n1']['criteria'] = [{'id': 'aftermath', 'text': '反应及关系变化。', 'effects': ['cost']}]
        result = enhanced_response(self.app)
        value = result['data']['alignment']
        value['realizations'][0]['fulfilled_criteria'] = []
        self.assertCode('alignment', editorial.alignment, {'alignment': value}, plan, result['data']['facts']['events'],
                        lambda r: facts.evidence(r, self.app._sources(self.repo.pending()['input'])))

    def test_realization_can_inherit_previously_evidenced_criterion_without_repeating_prose(self):
        definition = story_node('n1', 1)
        definition.update(effects=[{'id': 'cost', 'text': '承担责任。'}], criteria=[{'id': 'cost', 'text': '付出代价。', 'effects': ['cost']}])
        event = {'op': 'story_node', 'node': 'n1', 'line': 'main', 'depends_on': [], 'before': None, 'after': 'advanced', 'outcome': '已承担责任，尚待处理。',
                 'evidence': {'chapter': 1, 'quote': '次日'}, 'criteria': [{'id': 'cost', 'actual_effect': '责任已承担。', 'evidence': {'chapter': 1, 'quote': '次日'}}]}
        state, _ = facts.settle(self.repo.load()['state'], [event], '次日', 1)
        plan = {'node_ids': ['n1'], 'node_actions': [{'node': 'n1', 'after': 'resolved'}], 'node_contracts': {'n1': definition}}
        value = {'action': 'follow_plan', 'reason': '责任之前已承担，本章处理其后果。', 'realizations': [
            {'node': 'n1', 'after': 'resolved', 'reason': '完整处理。', 'evidence': {'chapter': 2, 'quote': '主管宣布处分。'},
             'fulfilled_criteria': [], 'prior_criteria': ['cost']}]}
        events = [{'op': 'story_node', 'node': 'n1', 'after': 'resolved'}]
        result = editorial.alignment({'alignment': value}, plan, events, lambda r: facts.evidence(r, {2: '主管宣布处分。'}), state)
        self.assertEqual(result['realizations'][0]['prior_criteria'], ['cost'])
        self.assertCode('alignment', editorial.alignment, {'alignment': value}, plan, events, lambda r: facts.evidence(r, {2: '主管宣布处分。'}), {})

    def test_last_failed_root_review_is_saved_before_exhaustion(self):
        owner = self.root()
        result = self.fix_closure('revise_range')
        result['data']['closure']['range'] = [3, 3]
        book = self.repo.load()
        work = self.repo.pending()['input']
        ref = lambda r: facts.evidence(r, self.app._sources(work))
        key = editorial.root_case(book, result['data']['closure'], work['scope'], ref, 3)
        case = book['repair_cases'][key]
        case['rounds'].append({**case['rounds'][0], 'id': 'last-round'})
        result['data']['remedy_review'] = [{'case_id': key, 'round_id': 'last-round', 'result': 'fix',
                                           'reason': '末轮仍缺余波。', 'evidence': {'chapter': 3, 'quote': '次日'}}]
        self.repo.save(book)
        self.app.submit(result)
        after = self.repo.load()
        self.assertEqual(after['repair_cases'][key]['rounds'][-1]['review']['result'], 'fix')
        self.assertEqual(after['status'], 'paused')
        self.assertEqual(after['branch'], 'main')
        self.assertEqual(after['remedy_exhausted'], [key])

    def test_author_question_cannot_be_cleared_by_resume(self):
        owner = self.root()
        result = self.fix_closure('needs_author')
        result['data']['closure'].update(question='保持开放结局还是补实后果？', options=[
            {'label': '补实', 'impact': '保留核心承诺。'}, {'label': '改约', 'impact': '改变终局授权。'}])
        self.app.submit(result)
        self.assertTrue(self.repo.load()['author_block'])
        self.assertCode('scope_fix', self.app.resume, owner)

    def test_scope_missing_duty_appends_within_budget_without_changing_contract(self):
        owner = self.root()
        old = copy.deepcopy(self.repo.load()['contract'])
        result = self.fix_closure('continue_scope')
        result['data']['closure'].update(existing_content_valid=True, missing_function='余波。', completion_path='增加处理后果的场景。',
                                         length_basis='总篇幅仍能承载。', append_through=4)
        self.app.submit(result)
        book = self.repo.load()
        self.assertEqual(book['contract'], old)
        self.assertEqual(editorial.effective_contract(book)['volumes'][0]['end'], 4)
        self.assertEqual(book['target'], 4)
        self.assertEqual(self.app.advance(owner=owner)['task']['stage'], 'alignment_plan')
        proposal = enhanced_response(self.app)
        new = copy.deepcopy(book['designs']['volume:v1'])
        new['threads'] = [{'id': 'aftermath', 'kind': 'side', 'purpose': '承担违规后果。', 'ending_condition': '主管实际处理。', 'required': True}]
        new['nodes'].append(story_node('aftermath4', 4, 'aftermath'))
        p = plan_extras({'chapter': 4, 'goal': '承担后果。', 'obstacle': '主管施压。', 'choice': '说明责任。', 'cost': '接受处分。',
                         'change': '关系变化。', 'ending': '主管决定处分。', 'participants': ['shen'], 'node_ids': ['aftermath4'],
                         'node_actions': [{'node': 'aftermath4', 'after': 'resolved'}], 'preconditions': [], 'disclosures': [], 'pacing': pace('aftermath')})
        proposal['data'] = {'reason': '补实原目标，不更改旧实现。', 'plan': p, 'designs': [{'scope': 'volume:v1', 'data': new}]}
        self.app.submit(proposal)
        self.app.advance(owner=owner)
        self.app.submit(enhanced_response(self.app))
        # The new plan's events are driven from its exact node contract rather than fixture n4.
        for _ in range(50):
            h = self.app.advance(owner=owner)
            if h['action'] != 'task_ready':
                self.assertEqual(h['action'], 'ready_to_complete')
                break
            self.app.submit(enhanced_response(self.app))
        self.assertTrue(self.app.complete(owner)['completed'])

    def test_scope_defect_builds_candidate_revision_in_same_transaction(self):
        owner = self.root()
        result = self.fix_closure('revise_range')
        result['data']['closure']['range'] = [3, 3]
        self.app.submit(result, preview=True)
        self.assertEqual(self.repo.load()['branch'], 'main')
        self.app.submit(result)
        book = self.repo.load()
        self.assertNotEqual(book['branch'], 'main')
        self.assertEqual(len(self.repo.headers('main')), 3)
        self.assertEqual(len(book['revision_run']['case_ids']), 1)
        self.assertEqual(self.app.advance(owner=owner)['task']['stage'], 'repair')

    def test_root_remedy_budget_survives_discard_and_last_round_is_reviewed(self):
        owner = self.root()
        result = self.fix_closure('revise_range')
        result['data']['closure']['range'] = [3, 3]
        self.app.submit(result)
        case = next(iter(self.repo.load()['repair_cases'].values()))
        self.app.discard(owner)
        self.assertEqual(len(next(iter(self.repo.load()['repair_cases'].values()))['rounds']), len(case['rounds']))
        b = self.repo.load()
        key, c = next(iter(b['repair_cases'].items()))
        c['rounds'].append({**c['rounds'][0], 'id': 'last-round'})
        data = {'verdict': 'pass', 'remedy_review': [{'case_id': key, 'round_id': 'last-round', 'result': 'pass',
                                                   'reason': '末轮确实成立。', 'evidence': {'chapter': 3, 'quote': '次日'}}]}
        editorial.remedy_review(b, data, c['scope'], lambda r: facts.evidence(r, {3: '次日'}))
        self.assertEqual(b['repair_cases'][key]['status'], 'resolved')

    def test_fixed_anchor_path_channels_and_custody_are_distinct(self):
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

    def test_custody_preserves_arrival_bound_and_path_does_not_grant_sight(self):
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

    def test_partial_intake_skips_only_already_decided_gates(self):
        state = creation.begin(version=2)
        value = {'ending': '退件来源公开，承担后果。', 'theme': '责任怎样在人之间传递。'}
        state = creation.intake(state, {'ending': value, 'title': {'title': '夜班退件'}}, '作者已给结局、母题和书名。')
        self.assertEqual(creation.current(state)['id'], 'genre')
        self.assertEqual(creation.selected(state)['ending'], value)
        self.assertEqual(creation.selected(state)['title'], {'title': '夜班退件'})
        self.assertCode('intake', creation.intake, state,
                        {'ending': {'ending': '改结局。', 'theme': '改母题。'}}, '冲突')
        reopened = creation.back(state, 'ending', '重开结局。')
        self.assertNotIn('ending', creation.selected(reopened))
        self.assertNotIn('title', creation.selected(reopened))

    def test_usage_counts_actual_reads_without_inventing_billed_tokens(self):
        drive(self.app, until='write')
        task = self.repo.pending()
        self.app.read(task['id'])
        usage = self.app.usage()
        self.assertGreater(usage['supplemental_read_chars'], 0)
        self.assertIsNone(usage['billed_tokens'])


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
            work = json.loads(Path(case['input']).read_text())
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
            work = json.loads(Path(case['input']).read_text())
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
