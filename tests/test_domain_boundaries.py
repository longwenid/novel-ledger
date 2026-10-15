"""Domain boundary checks run against plain values, with no project or SQLite setup."""
import ast
import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from novel_ledger import design_queries, entities, facts, planning, quality, result_templates, workflow
from novel_ledger.contracts import CHECKS_VERSION, Error
from novel_ledger.evidence import evidence
from architecture_table import ADAPTERS, ALLOWED, CORE_EXTERNAL
from support import contract


class DomainBoundaryTests(unittest.TestCase):
    def assertCode(self, code, fn, *args):
        with self.assertRaises(Error) as caught:
            fn(*args)
        self.assertEqual(caught.exception.code, code)

    def test_design_query_needs_only_design_values(self):
        first = {'id': 'arrival', 'depends_on': []}
        second = {'id': 'choice', 'depends_on': ['arrival']}
        designs = {'book': {'nodes': [first]}, 'volume:1': {'nodes': [second]}}
        self.assertEqual(design_queries.node_map(designs), {'arrival': first, 'choice': second})
        # The lifecycle compatibility query delegates to the same owner.
        self.assertEqual(workflow.node_map({'designs': designs}), design_queries.node_map(designs))
        self.assertEqual(design_queries.node_map({}), {})

    def test_entity_identity_rules_need_only_an_entity_table(self):
        table = {}
        row = {'id': 'shen', 'name': '沈桐', 'kind': 'person', 'aliases': ['小沈']}
        entities.register(table, row)
        row['aliases'].append('后来修改')
        self.assertEqual(table['shen']['aliases'], ['小沈'])
        self.assertCode('alias_conflict', entities.register, table,
                        {'id': 'other', 'name': '小沈', 'kind': 'person'})
        self.assertCode('entity', entities.register, table,
                        {'id': 'shen', 'name': '另一称呼', 'kind': 'person'})

    def test_exact_evidence_is_shared_without_a_fact_projection(self):
        source = {3: '他推开门。他推开门。'}
        self.assertCode('evidence', evidence, {'chapter': 3, 'quote': '他推开门。'}, source)
        ref = {'chapter': 3, 'quote': '他推开门。', 'start': 5}
        self.assertEqual(evidence(ref, source), ref)
        self.assertIs(facts.evidence, evidence)
        self.assertCode('evidence_scope', evidence, {'chapter': 2, 'quote': '门'}, source)

    def test_review_validation_accepts_only_a_receipt_and_frozen_prose(self):
        source = {3: '门已经锁上。'}
        receipt = {'verdict': 'pass', 'checks_version': CHECKS_VERSION,
                   'checks': [{'id': 'continuity', 'result': 'pass', 'reason': '门的状态一致。',
                               'evidence': [{'chapter': 3, 'quote': source[3]}]}],
                   'findings': []}
        original = copy.deepcopy(receipt)
        normalized = quality.checks(receipt, ['continuity'], source)
        self.assertEqual(normalized['checks'][0]['evidence'][0]['start'], 0)
        self.assertEqual(receipt, original)
        self.assertFalse(hasattr(quality, 'template'))

    def test_lexical_queries_need_only_policy_versions(self):
        versions = [{'version': 1, 'source': '最初约定', 'policy': {'forbidden_terms': ['甲']}},
                    {'version': 2, 'source': '作者改口', 'policy': {'forbidden_terms': ['乙']}}]
        self.assertEqual(planning.active_policy(versions)['forbidden_terms'], ['乙'])
        material = planning.policy_material(versions, ['write', 'repair'])
        self.assertEqual((material['version'], material['source']), (2, '作者改口'))
        material['forbidden_terms'].append('丙')
        self.assertEqual(versions[-1]['policy']['forbidden_terms'], ['乙'])

    def test_plan_rules_can_run_without_the_fact_reducer_state_shape(self):
        data = {'plans': [{'chapter': 1, 'goal': '查明来源', 'obstacle': '门被锁住',
                           'choice': '留下等待', 'cost': '失去时间', 'change': '得到线索',
                           'ending': '看见签字', 'node_ids': ['arrival'], 'participants': ['shen'],
                           'new_entities': [{'id': 'other', 'name': '顾平', 'kind': 'person'}],
                           'schedule': [{'basis': 'main_clock', 'day': 2, 'event': '等门开启'}]}]}
        state = {'entities': {'shen': {'id': 'shen', 'name': '沈桐', 'kind': 'person'}}, 'clock': 1}
        original = copy.deepcopy(state)
        plans = planning.validate_plans(data, 1, 1, {'arrival'}, state, {})
        self.assertEqual(plans[0]['participants'], ['shen'])
        self.assertEqual(state, original)
        self.assertNotIn('other', state['entities'])

    def test_initial_fact_consistency_is_enforced_by_lifecycle_composition(self):
        raw = contract()
        raw['initial_resources'][0]['holder'] = 'missing'
        # Planning checks the author contract, and lifecycle composition checks factual seeding.
        self.assertEqual(planning.validate_contract(raw)['initial_resources'][0]['holder'], 'missing')
        self.assertCode('resource', workflow.new_book, raw)

    def test_task_result_shapes_are_built_outside_quality_judgments(self):
        blank = result_templates.template('chapter_review', 3, {3: '正文'}, version=CHECKS_VERSION)
        self.assertEqual(blank['facts']['checks_version'], CHECKS_VERSION)
        self.assertEqual(blank['facts']['verdict'], '')
        self.assertEqual(blank['reader']['findings'], [])
        self.assertIn('reader_promise', result_templates.template('opening_contract', 0, {}))

    def test_task_envelopes_reject_undeclared_fields(self):
        from novel_ledger import envelope
        work = {name: None for name in envelope.WORK_FIELDS}
        self.assertEqual(envelope.validate_work(dict(work, brief='x'))['brief'], 'x')
        with self.assertRaises(Error):
            envelope.validate_work(dict(work, surprise=1))
        with self.assertRaises(Error):
            envelope.validate_work({k: v for k, v in work.items() if k != 'stage'})
        task = {name: None for name in envelope.TASK_FIELDS}
        self.assertIs(envelope.validate_task(task), task)
        with self.assertRaises(Error):
            envelope.validate_task(dict(task, guides=['x'], unexpected=1))

    def test_unknown_task_stage_is_rejected_instead_of_degrading(self):
        from novel_ledger import stages
        with self.assertRaises(Error):
            stages.require_stage('not_a_stage')
        with self.assertRaises(Error):
            result_templates.template('not_a_stage', 1, {})
        self.assertEqual(stages.require_stage('write'), 'write')

    def test_domain_modules_cannot_reintroduce_adapter_or_cross_layer_imports(self):
        # The boundary table is maintained once in architecture_table; this derives
        # the property instead of keeping a second, narrower copy that can drift.
        self.assertTrue(CORE_EXTERNAL, 'Core modules must stay explicitly listed.')
        for name in CORE_EXTERNAL:
            with self.subTest(module=name):
                dependencies = ALLOWED[name]
                self.assertFalse(dependencies & ADAPTERS,
                                 f'{name} depends on an adapter: {sorted(dependencies & ADAPTERS)}')
        context = ast.parse((ROOT / 'scripts' / 'novel_ledger' / 'context.py').read_text(encoding='utf-8'))
        self.assertFalse(any(isinstance(n, ast.ImportFrom) and n.module == 'workflow'
                             for n in ast.walk(context)))


if __name__ == '__main__':
    unittest.main()
