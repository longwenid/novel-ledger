"""Domain boundary checks run against plain values, with no project or SQLite setup."""
import ast
import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from novel_ledger import design_queries, entities, facts, planning, quality, result_templates, workflow
from novel_ledger.contracts import AUTHOR_CHANNEL_STAGES, CHECKS_VERSION, Error
from novel_ledger.evidence import evidence
from architecture_table import ADAPTERS, ALLOWED, CORE_EXTERNAL
from support import contract


class DomainBoundaryTests(unittest.TestCase):
    def assertCode(self, code, fn, *args, **kwargs):
        with self.assertRaises(Error) as caught:
            fn(*args, **kwargs)
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

    def test_declared_delivery_blocks_match_the_blank_templates(self):
        from novel_ledger import stages
        for stage, blocks in stages.BLOCKS.items():
            with self.subTest(stage=stage):
                self.assertEqual(tuple(sorted(result_templates.template(stage, 1, {}))),
                                 tuple(sorted(blocks)))
        for stage, extras in stages.CONDITIONAL_BLOCKS.items():
            with self.subTest(stage=stage, conditional=True):
                result = set(result_templates.template(stage, 1, {}))
                self.assertLessEqual(result, set(stages.BLOCKS.get(stage, ())) | set(extras))
        # A combined world dispatch adds exactly the contract block and nothing else; this is
        # the block a repair dispatch once omitted, leaving the fix with nowhere to live.
        skeleton = result_templates.template('world_model', 1, {})
        combined = result_templates.template('world_model', 1, {}, extra=('opening_contract',))
        self.assertEqual(set(combined) - set(skeleton), {'contract'})
        # Completeness is the point: a stage with no declaration would be a stage whose
        # deliverable shape nobody agreed on.
        declared = set(stages.BLOCKS) | set(stages.CONDITIONAL_BLOCKS) | set(stages.DYNAMIC_BLOCKS)
        self.assertEqual(set(stages.STAGES) - declared, set())

    def test_causal_frontier_is_iterative_and_bounded(self):
        from novel_ledger import design_queries as queries
        size = 5000
        nodes = {'n%d' % i: {'id': 'n%d' % i, 'depends_on': [] if i == 0 else ['n%d' % (i - 1)]}
                 for i in range(size)}
        tail = 'n%d' % (size - 1)
        selected = queries.frontier(nodes, [tail])
        self.assertEqual(selected,
                         [tail] + ['n%d' % (size - 1 - k) for k in range(1, queries.BASIC_DEPTH + 1)])
        self.assertEqual(queries.frontier(nodes, ['n3'], depth=1), ['n3', 'n2'])
        wide = {'seed': {'id': 'seed', 'depends_on': ['p%d' % i for i in range(40)]}}
        wide.update({'p%d' % i: {'id': 'p%d' % i, 'depends_on': []} for i in range(40)})
        self.assertEqual(len(queries.frontier(wide, ['seed'])), queries.NODE_LIMIT)

    def test_completion_sources_include_registered_payoffs(self):
        from novel_ledger import editorial
        state = {'hooks': {}, 'developments': {'shen': [{'change': '愿意担责。'}]},
                 'reader_knowledge': {'source': {'claim': '他知道了来源。'}}}
        book = {'contract': {'reader_promise': '看到责任被查明。', 'ending': '他担下了责任。'},
                'designs': {}, 'feedback': [], 'state': state,
                'world': {'mysteries': [{'id': 'source', 'disclosure': '卷末揭示来源。'}]}}
        rows = {row['id']: row for row in editorial.sources(book, 'book')}
        self.assertIn('development:shen:0', rows)
        self.assertIn('reader_knowledge:source', rows)
        self.assertEqual(rows['reader_knowledge:source']['required'], False)
        self.assertIn('mystery:source', rows)
        self.assertEqual(rows['mystery:source']['required'], True)
        self.assertEqual(editorial.sources(book, 'volume:v1'), [])

    def test_task_envelopes_reject_undeclared_fields(self):
        from novel_ledger import envelope
        work = {name: None for name in envelope.WORK_FIELDS}
        work['payload'] = {}
        self.assertEqual(envelope.validate_work(dict(work, brief='x'))['brief'], 'x')
        with self.assertRaises(Error):
            envelope.validate_work(dict(work, surprise=1))
        with self.assertRaises(Error):
            envelope.validate_work({k: v for k, v in work.items() if k != 'stage'})
        # The stage's own decision travels in `payload`, so an undeclared key there is rejected for
        # the same reason an undeclared envelope field is: the consumers read it blind.
        self.assertEqual(envelope.validate_work({**work, 'payload': {'gate': {}}})['payload'], {'gate': {}})
        with self.assertRaises(Error) as caught:
            envelope.validate_work({**work, 'payload': {'gate': {}, 'invented': 1}})
        self.assertEqual(caught.exception.details['unknown_fields'], ['invented'])
        task = {name: None for name in envelope.TASK_FIELDS}
        self.assertIs(envelope.validate_task(task), task)
        with self.assertRaises(Error):
            envelope.validate_task(dict(task, guides=['x'], unexpected=1))
        # Dispatch identity is declared the same way: data to check against, never a permission.
        identity = {name: None for name in envelope.IDENTITY_FIELDS}
        self.assertIs(envelope.validate_identity(identity), identity)
        with self.assertRaises(Error):
            envelope.validate_identity(dict(identity, credential='forge-me'))
        with self.assertRaises(Error):
            envelope.validate_identity({k: v for k, v in identity.items() if k != 'worker_env'})

    def test_unknown_task_stage_is_rejected_instead_of_degrading(self):
        from novel_ledger import stages
        with self.assertRaises(Error):
            stages.require_stage('not_a_stage')
        with self.assertRaises(Error):
            result_templates.template('not_a_stage', 1, {})
        self.assertEqual(stages.require_stage('write'), 'write')

    def test_opening_three_gates_own_every_alignment_field_they_claim(self):
        """The male-channel redesign is a gate set, so its ownership must close without a project."""
        from novel_ledger import creation
        from novel_ledger.contracts import (CONTRACT_FIELDS, DERIVED_FIELDS, OPENING_DIRECTION_GATES,
                                            alignment_for, opening_source)
        gates = [ident for ident, _title in creation.GATE_SETS[3]]
        self.assertEqual(len(gates), 10)
        self.assertEqual(set(OPENING_DIRECTION_GATES), set(gates),
                         'every gate of the redesign must say what the default direction means for it')
        self.assertEqual(creation.SYSTEM_GATES[3], ('scale',))
        for gate in gates:
            with self.subTest(gate=gate):
                self.assertIn(gate, creation.VALUE_RULES[3])
                self.assertTrue(creation.value_fields(gate, 3), 'a gate must own at least one field')
                self.assertTrue(creation.value_rules(3, gate).strip())
        owned = {row['key'] for row in CONTRACT_FIELDS
                 if opening_source(row, 3) and row['key'] not in DERIVED_FIELDS}
        derived = {'entities', 'red_lines', 'volumes', 'world_rules', 'world_premise'}
        self.assertEqual(owned | derived, set(alignment_for(3)))
        self.assertEqual(owned & derived, set())
        # A field a later protocol re-sources must still resolve for the versions before it, and a
        # field a version never decided (since > version) must not be sourced from it either.
        # opening/1 predates this ownership table (its contract is projected by hand), so it is not
        # read through it — only the versions that actually derive from the table are checked.
        for row in CONTRACT_FIELDS:
            for version in (2, 3):
                if row.get('since', 1) > version:
                    continue
                with self.subTest(field=row['key'], version=version):
                    source = opening_source(row, version)
                    if source:
                        self.assertIn(source[0], creation.gate_ids(version),
                                      'a version may only source fields from gates it actually has')

    def test_required_material_never_charges_twice_for_one_fact(self):
        """The thinning pass is a declared relationship, not an accident of two similar payloads.

        It covers both shapes a real run produced: a projection whose source is also required, and
        two names whose content is byte-identical. A dropped name stays reachable in `records`.
        """
        from novel_ledger import context
        self.assertEqual(context.projects_from('world_core'), 'world_model')
        self.assertEqual(context.projects_from('frontier:volume:v1'), 'design:volume:v1')
        self.assertEqual(context.projects_from('scope_profiles'), 'profiles')
        self.assertIsNone(context.projects_from('design:book'))
        records = {'contract': 'h0', 'world_model': 'h1', 'world_core': 'h2', 'design:book': 'h3',
                   'frontier:book': 'h3', 'profiles': 'h4', 'scope_profiles': 'h4'}
        both = ['contract', 'world_model', 'world_core', 'design:book', 'frontier:book',
                'profiles', 'scope_profiles']
        self.assertEqual(context.thin_required(records, both),
                         ['contract', 'world_model', 'design:book', 'profiles'])
        # Where no source is required the projection is exactly what the worker should read.
        self.assertEqual(context.thin_required(records, ['world_core', 'frontier:book', 'scope_profiles']),
                         ['world_core', 'frontier:book', 'scope_profiles'])
        self.assertEqual(context.thin_required({'world_model': 'h1', 'world_core': 'h2'},
                                               ['world_model', 'world_core']), ['world_model'])

    def test_book_state_invariants_are_checked_where_the_state_is_read(self):
        """Two fields that must move together are how a project ends up running while still paused.

        The check runs on every status read, so the command that produced the contradiction reports
        it instead of a later command discovering it.
        """
        from novel_ledger import book_state
        good = {'status': 'running', 'draft': None, 'accepted_findings': []}
        self.assertIs(book_state.check_state(good), good)
        with self.assertRaises(Error) as caught:
            book_state.check_state(dict(good, pause_reason='上一步的暂停原因'))
        self.assertEqual(caught.exception.code, 'book_state')
        with self.assertRaises(Error):
            book_state.check_state({'status': 'paused'})
        with self.assertRaises(Error):
            book_state.check_state(dict(good, status='whatever'))
        with self.assertRaises(Error):
            book_state.check_state(dict(good, accepted_findings=[{'stage': 'x'}]))
        book_state.check_state(dict(good, status='paused', pause_reason='等作者', draft={'chapter': 2}))

    def test_frozen_capability_values_are_checked_instead_of_degrading(self):
        """A task frozen with an unknown protocol version must fail, not read as an older project."""
        from novel_ledger import contracts
        task = {'capabilities': {'reading_dependencies': contracts.READING_DEPENDENCIES_CAPABILITY}}
        self.assertEqual(contracts.capabilities_for(task)['reading_dependencies'],
                         contracts.READING_DEPENDENCIES_CAPABILITY)
        # A dispatch that predates the capability map declared nothing, and that is not an error.
        self.assertEqual(contracts.capabilities_for({'capabilities': {}}), {})
        with self.assertRaises(Error) as caught:
            contracts.capabilities_for({'capabilities': {'scene_identity': 'scene-idenity/2'}})
        self.assertEqual(caught.exception.code, 'capability')
        self.assertEqual(caught.exception.details['unknown'], ['scene_identity=scene-idenity/2'])
        # Every version still in flight stays readable, so the guard cannot lock out frozen work.
        contracts.capabilities_for({'capabilities': {'scene_identity': contracts.SCENE_IDENTITY_V1}})
        contracts.capabilities_for({'capabilities': {'scene_identity': contracts.SCENE_IDENTITY_CAPABILITY}})
        # The producer builds the same strings the consumer compares against.
        source = (ROOT / 'scripts' / 'novel_ledger' / 'context.py').read_text(encoding='utf-8')
        for literal in ("'editorial/1'", "'understanding/1'", "'scene-identity/2'", "'reading-dependencies/1'",
                        "'opening-bounds/1'", "'volume-outline/1'", "'scene-memory/1'", "'hook-links/1'"):
            with self.subTest(literal=literal):
                self.assertNotIn(literal, source, 'capability strings belong to contracts, not to a second copy')

    def test_the_author_channel_is_declared_for_pre_prose_reviews_only(self):
        from novel_ledger import briefs, stages
        self.assertTrue(AUTHOR_CHANNEL_STAGES <= stages.STAGES,
                        'author channel names a stage the engine does not dispatch')
        for name in sorted(AUTHOR_CHANNEL_STAGES):
            with self.subTest(stage=name):
                stages.require_stage(name)
                self.assertIn('decision={id,question,options}', briefs.stage(name, {}),
                              'reviewers cannot use an option the brief never mentions')
        # A chapter is already committed prose: its review must describe work a writer can do now.
        self.assertFalse(AUTHOR_CHANNEL_STAGES & {'write', 'chapter_review', 'revision_review', 'repair', 'redesign'})

    def test_author_level_findings_are_structured_and_bounded(self):
        source = {3: '门已经锁上。'}
        decision = {'id': 'death-detail', 'question': '铁门里的内容能不能被录音带出去？',
                    'options': [{'label': '不能被带出', 'impact': '录音与转述都须改写。'},
                                {'label': '可以被带出', 'impact': '禁令改写为另一条。'}]}

        def receipt(severity, **extra):
            finding = {'criterion': 'continuity', 'severity': severity, 'reason': '作者约定本身互相冲突。',
                       'evidence': {'chapter': 3, 'quote': source[3]}, **extra}
            return {'verdict': 'fix', 'checks_version': CHECKS_VERSION,
                    'checks': [{'id': 'continuity', 'result': 'fix', 'reason': '冲突。',
                                'evidence': [{'chapter': 3, 'quote': source[3]}]}], 'findings': [finding]}

        # A chapter-level review has no author channel: that question is a writer's repair.
        self.assertCode('author_decision', quality.checks, receipt('author', decision=decision), ['continuity'], source)
        checked = quality.checks(receipt('author', decision=decision), ['continuity'], source, author_channel=True)
        self.assertEqual(quality.author_decision(checked['findings'])['id'], 'death-detail')
        self.assertEqual(quality.repairable(checked['findings']), [],
                         'an author decision must never become a worker repair target')
        # The question must be answerable, and only an author-level finding may carry it.
        self.assertCode('author_decision', quality.checks, receipt('author'), ['continuity'], source, author_channel=True)
        self.assertCode('author_decision', quality.checks, receipt('author', decision=dict(decision, options=decision['options'][:1])),
                        ['continuity'], source, author_channel=True)
        self.assertCode('author_decision', quality.checks,
                        receipt('blocker', decision=decision, target_chapter=3, repair_scope='local'),
                        ['continuity'], source, author_channel=True)
        # `resume` refuses to bypass one pending question, so a receipt may hand up only one.
        two = receipt('author', decision=decision)
        two['findings'].append(dict(copy.deepcopy(two['findings'][0]), decision=dict(decision, id='voice-range')))
        self.assertCode('author_decision', quality.checks, two, ['continuity'], source, author_channel=True)

    def test_an_author_decision_pauses_the_book_instead_of_a_repair_round(self):
        review = {'verdict': 'fix', 'findings': [{
            'criterion': 'world_rules', 'severity': 'author', 'reason': '两条规则冲突。',
            'evidence': {'chapter': 0, 'quote': '铁门内不留记录。'},
            'decision': {'id': 'death-detail', 'question': '录音能不能带出铁门内的内容？',
                         'options': [{'label': '不能', 'impact': '录音须改写。'}, {'label': '能', 'impact': '禁令改写。'}]}}]}
        book = {'status': 'running'}
        holder = {'attempts': 0}
        self.assertTrue(workflow.hold_for_author(book, review, holder))
        self.assertEqual(book['status'], 'paused')
        self.assertEqual(book['pause_reason'], book['author_block']['question'])
        self.assertEqual(book['author_block']['id'], 'death-detail')
        self.assertEqual(len(book['author_block']['options']), 2)
        self.assertEqual(holder['attempts'], 0, 'a premise no writer can change must not burn a repair attempt')
        # One pending question at a time: the registered decision keeps priority.
        self.assertFalse(workflow.hold_for_author(book, review, holder))
        self.assertEqual(book['author_block']['id'], 'death-detail')

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
