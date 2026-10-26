"""Domain boundary checks run against plain values, with no project or SQLite setup."""
import ast
import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from novel_ledger import catalog, design_queries, drift_validation, entities, facts, planning, result_templates, workflow
from novel_ledger.contracts import Error
from novel_ledger.evidence import evidence
from architecture_table import ADAPTERS, ALLOWED, CORE_EXTERNAL
from support import contract, seeded_book, volume_rows



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


    def test_lexical_queries_need_only_policy_versions(self):
        versions = [{'version': 1, 'source': '最初约定', 'policy': {'forbidden_terms': ['甲']}},
                    {'version': 2, 'source': '作者改口', 'policy': {'forbidden_terms': ['乙']}}]
        self.assertEqual(planning.active_policy(versions)['forbidden_terms'], ['乙'])
        material = planning.policy_material(versions, ['write', 'repair'])
        self.assertEqual((material['version'], material['source']), (2, '作者改口'))
        material['forbidden_terms'].append('丙')
        self.assertEqual(versions[-1]['policy']['forbidden_terms'], ['乙'])


    def test_initial_fact_consistency_is_enforced_by_lifecycle_composition(self):
        raw = contract()
        raw['initial_resources'][0]['holder'] = 'missing'
        # Planning checks the author contract, and lifecycle composition checks factual seeding.
        self.assertEqual(planning.validate_contract(raw)['initial_resources'][0]['holder'], 'missing')
        self.assertCode('resource', workflow.new_book, raw)

    def test_chapter_ceiling_is_a_policy_not_a_tier_artifact(self):
        """Tier tables open lower; a live contract may patch up to the declared ceiling."""
        from novel_ledger.contracts import policy_default
        ceiling = policy_default('chapter_max_ceiling')
        raw = contract()
        raw['chapter_max'] = ceiling
        raw['chapter_aim'] = ceiling
        raw['word_range'] = [raw['volumes'][-1]['end'] * raw['chapter_min'], raw['volumes'][-1]['end'] * ceiling]
        self.assertEqual(planning.validate_contract(raw)['chapter_max'], ceiling)
        raw['chapter_max'] = ceiling + 1
        with self.assertRaises(Error) as caught:
            planning.validate_contract(raw)
        self.assertEqual(caught.exception.code, 'contract')
        self.assertIn('策略上限', caught.exception.message)

    def test_task_result_shapes_are_built_outside_any_judgment(self):
        blank = result_templates.template('write', 3, payload={'chapter_outline': {}})
        self.assertEqual([item['kind'] for item in blank['drift_check']['items']], ['clock'])
        self.assertIn('self_check', blank)
        self.assertIn('reader_promise', result_templates.template('opening_contract', 0))
        volume = result_templates.template('volume_outline', 1, payload={'volume_ids': ['v1']})
        self.assertEqual([row['id'] for row in volume['volumes']], ['v1'])
        chapter = result_templates.template('chapter_outline', 1,
                                            payload={'volume': 'v1', 'chapter_outline': {'first': 2, 'last': 3}})
        self.assertEqual([row['chapter'] for row in chapter['chapters']], [2, 3])

    def test_declared_delivery_blocks_match_the_blank_templates(self):
        from novel_ledger import stages
        for stage, blocks in stages.BLOCKS.items():
            with self.subTest(stage=stage):
                self.assertEqual(tuple(sorted(result_templates.template(stage, 1))),
                                 tuple(sorted(blocks)))
        for stage, extras in stages.CONDITIONAL_BLOCKS.items():
            if stage in stages.DYNAMIC_BLOCKS:
                continue                     # a dynamic shape is checked by the module that owns it
            with self.subTest(stage=stage, conditional=True):
                result = set(result_templates.template(stage, 1))
                self.assertLessEqual(result, set(stages.BLOCKS.get(stage, ())) | set(extras))
        # A combined world dispatch adds exactly the contract block and nothing else; this is
        # the block a repair dispatch once omitted, leaving the fix with nowhere to live.
        skeleton = result_templates.template('world_model', 1)
        combined = result_templates.template('world_model', 1, extra=('opening_contract',))
        self.assertEqual(set(combined) - set(skeleton), {'contract'})
        # Completeness is the point: a stage with no declaration would be a stage whose
        # deliverable shape nobody agreed on.
        declared = set(stages.BLOCKS) | set(stages.CONDITIONAL_BLOCKS) | set(stages.DYNAMIC_BLOCKS)
        self.assertEqual(set(stages.STAGES) - declared, set())

    def test_world_only_fills_the_sections_its_tier_requires(self):
        """A micro book's world floor is the world its line walks through, not ten domains.

        The brief and the validator read the same tier declaration; before that, a micro project was
        asked to keep the world small while the check demanded every domain, and paid with four
        repair rounds and 55 records.
        """
        from novel_ledger import world
        choices = {'world': {'world_premise': '一座仓库的夜班退件纠纷。', 'mechanism': {'mode': 'none'}},
                   'protagonist': {'id': 'shen', 'name': '沈桐', 'desire': '查清责任。', 'limit': '不牵连无关同事。'}}
        character = {'id': 'shen', 'name': '沈桐', 'role': '夜班工人', 'desire': '查清责任。',
                     'limit': '不牵连无关同事。', 'knowledge_boundary': '只知道自己经手的单子。', 'links': []}
        model = {'selection_hash': 'h', 'premise': '一座仓库的夜班退件纠纷。', 'story_capacity': '一条主线走三章。',
                 'rules': [{'id': 'r1', 'principle': '退件必须登记负责人。', 'scope': '全库', 'limits': '夜班',
                            'consequences': '漏记就查夜班', 'links': []}],
                 'society': [{'id': 's1', 'institution': '交接班', 'norm': '当班签字', 'enforcement': '主管抽查',
                              'pressure': '谁签谁担', 'links': []}],
                 'everyday': [{'id': 'e1', 'practice': '夜班清点', 'constraint': '只有一个人', 'story_use': '制造时间压力',
                               'links': []}],
                 'characters': [character],
                 'mysteries': [{'id': 'm1', 'truth': '退件是主管放的', 'disclosure': '卷末', 'causal_role': '追查责任',
                                'links': []}],
                 'mechanisms': [], 'geography': [], 'history': [], 'factions': [], 'economy': [],
                 'powers': [], 'cosmology': []}
        self.assertEqual(world.validate(model, choices, 'h', sections='t0'), model)
        self.assertEqual(world.required_sections('t0'),
                         ('rules', 'society', 'everyday', 'characters', 'mysteries', 'mechanisms'))
        # opening/5 added two grand sections to the table, but they are not part of every tier's
        # floor: the floor is what the tier's own line walks through.
        self.assertNotEqual(world.required_sections('t3'), world.ALL_SECTIONS)
        self.assertEqual(len(world.required_sections('t3')), 10)
        for tier, names in world.TIER_SECTIONS.items():
            with self.subTest(tier=tier):
                self.assertTrue(set(names) <= set(world.SECTIONS), '档位域表只能用已登记的领域')
                self.assertEqual(len(names), len(set(names)))
                self.assertIn('mechanisms', names)
        with self.assertRaises(Error) as caught:
            world.validate(dict(model, rules=[]), choices, 'h', sections='t0')
        self.assertEqual(caught.exception.code, 'world_section')
        # A long tier still needs the sections a micro book may leave empty.
        with self.assertRaises(Error):
            world.validate(model, choices, 'h', sections='t3')

    def test_a_local_repair_may_only_change_what_its_findings_name(self):
        """Repairs that re-draft everything are how a run pays twice for the same ground.

        A real world candidate was repaired four times; the early repairs rewrote records nobody had
        questioned, findings already settled came back, and the next review paid for them again. The
        engine can tell a narrow repair from a rewrite mechanically, so it refuses the rewrite in the
        writer's own session instead of spending an independent review on it.
        """
        from novel_ledger import workflow
        previous = {'rules': [{'id': 'r1', 'principle': '第一条'},
                              {'id': 'r2', 'principle': '第二条'}],
                    'characters': [{'id': 'c1', 'name': '沈桐'}]}
        findings = [{'criterion': 'rule_consistency', 'severity': 'quality', 'repair_scope': 'local',
                     'reason': 'r1 的违反后果没写清。', 'evidence': [{'chapter': 0, 'quote': '第一条'}]}]
        # Only the named record changed: accepted.
        workflow.require_narrow_repair(previous, {'rules': [{'id': 'r1', 'principle': '第一条，违反者扣当班'},
                                                           {'id': 'r2', 'principle': '第二条'}],
                                                 'characters': previous['characters']}, findings)
        # An unnamed record changed or disappeared: refused, and the message names what drifted.
        changed = {'rules': [{'id': 'r1', 'principle': '第一条，违反者扣当班'},
                             {'id': 'r2', 'principle': '第二条改过了'}],
                   'characters': previous['characters']}
        with self.assertRaises(Error) as caught:
            workflow.require_narrow_repair(previous, changed, findings)
        self.assertEqual(caught.exception.code, 'repair_scope')
        self.assertEqual(caught.exception.details['changed_but_not_named'], ['rules:r2'])
        dropped = {'rules': [{'id': 'r1', 'principle': '第一条，违反者扣当班'}],
                   'characters': previous['characters']}
        with self.assertRaises(Error):
            workflow.require_narrow_repair(previous, dropped, findings)
        # A wider declared scope is exactly how a writer asks for permission to move more.
        workflow.require_narrow_repair(previous, changed, [dict(findings[0], repair_scope='chapter')])
        # Nothing identifiable in the findings: the guard does not guess a scope.
        workflow.require_narrow_repair(previous, changed, [dict(findings[0], reason='整体不够好。',
                                                               evidence=[])])
        # A rendered refusal is findings like any other: the complaint's own values and record
        # keys ride the reason text, because that text is what `named_items` matches records by —
        # a paraphrased refusal would fence the repair out of the very records it names.
        collision = Error('world_id', '世界记录的裸 id 在全部领域间必须唯一。',
                          {'id': 'shen', 'sections': ['characters', 'everyday'],
                           'referenced_by': ['rules:r1']})
        rendered = workflow.rejection_findings(collision)
        self.assertTrue(rendered)
        self.assertTrue(all(row['repair_scope'] == 'local' for row in rendered))
        world_previous = {'rules': [{'id': 'r1', 'principle': '第一条', 'links': ['everyday:shen']}],
                          'characters': [{'id': 'shen', 'name': '沈桐'}],
                          'everyday': [{'id': 'shen', 'practice': '夜班交接'}],
                          'history': [{'id': 'h1', 'event': '旧制度崩过一次。'}]}
        world_fixed = copy.deepcopy(world_previous)
        world_fixed['everyday'][0]['id'] = 'shen-shift'
        world_fixed['rules'][0]['links'] = ['everyday:shen-shift']
        workflow.require_narrow_repair(world_previous, world_fixed, rendered)
        world_tampered = copy.deepcopy(world_fixed)
        world_tampered['history'][0]['event'] = '顺手改写的历史。'
        with self.assertRaises(Error) as caught:
            workflow.require_narrow_repair(world_previous, world_tampered, rendered)
        self.assertEqual(caught.exception.code, 'repair_scope')
        # A refusal that names nothing degrades safely: the guard does not fence a scope nobody
        # established, so an unidentifiable complaint never blocks the next submission.
        workflow.require_narrow_repair(previous, changed, workflow.rejection_findings(
            Error('world_section', '本档位要求填写的世界领域必须有实际内容：society')))



    def test_every_stage_declares_the_material_it_must_read(self):
        """The same completeness rule as deliverable blocks, for the other half of a dispatch.

        A stage whose required material nobody agreed on is how a run's cost stops being a decision:
        a real one paid 90 KB of required records per design dispatch, including a world and its own
        projection. Adding material to a stage now means editing the table, and the fixture check in
        `support.check_dispatch` compares every frozen dispatch against it.
        """
        from novel_ledger import context, stages
        self.assertEqual(sorted(set(stages.STAGES) - set(context.STAGE_MATERIAL)), [],
                         '每个阶段都要声明必读材料')
        self.assertEqual(sorted(set(context.STAGE_MATERIAL) - set(stages.STAGES)), [],
                         '材料表里出现了未登记阶段')
        for stage, names in context.STAGE_MATERIAL.items():
            with self.subTest(stage=stage):
                self.assertEqual(len(names), len(set(names)), '同一份材料不要写两次')
                self.assertTrue(all(isinstance(name, str) and name for name in names))
        self.assertEqual(context.undeclared_material('write', ['contract', 'world_model']), ['world_model'])
        self.assertEqual(context.undeclared_material('write', ['contract', 'chapter_outline']), [])

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
        # An unknown stage is refused for the same reason: never degrade into a guessed shape.
        from novel_ledger import stages
        with self.assertRaises(Error):
            stages.require_stage('not_a_stage')
        with self.assertRaises(Error):
            result_templates.template('not_a_stage', 1, {})
        self.assertEqual(stages.require_stage('write'), 'write')

    def test_every_gate_has_fields_and_creative_tasks_locate_the_shared_guide(self):
        from novel_ledger import briefs, creation
        from novel_ledger.contracts import OPENING_VERSION
        for gate in creation.gate_ids(OPENING_VERSION):
            with self.subTest(gate=gate):
                self.assertTrue(creation.value_rules(OPENING_VERSION, gate).strip())
                if gate not in creation.SYSTEM_GATES[OPENING_VERSION]:
                    card = briefs.opening_options({'id': gate})
                    self.assertIn(gate, card)
                    self.assertIn('hatch.md', card)
                    self.assertIn('opening_choices', card)
                    self.assertIn('opening_rejections', card)

    def test_the_current_gate_set_owns_every_alignment_field_it_claims(self):
        """The male-channel redesign is a gate set, so its ownership must close without a project.

        Each later protocol adds gates without renaming the older decisions; every version's
        alignment fields therefore have to be owned by exactly one of its gates, or a new gate that
        forgot its field only fails much later, at contract alignment.
        """
        from novel_ledger import creation
        from novel_ledger.contracts import (CONTRACT_FIELDS, DERIVED_FIELDS,
                                            OPENING_VERSION, alignment_for, opening_source)
        version = OPENING_VERSION
        gates = [ident for ident, _title in creation.GATES]
        self.assertEqual(len(gates), 13)
        self.assertEqual(creation.SYSTEM_GATES[version], ('scale',))
        for gate in gates:
            self.assertTrue(creation.value_fields(gate, version),
                            'a gate must own at least one field')
        owned = {row['key'] for row in CONTRACT_FIELDS
                 if opening_source(row, version)
                 and row['key'] not in DERIVED_FIELDS}
        derived = {'entities', 'red_lines', 'volumes', 'world_rules', 'world_premise'}
        self.assertEqual(owned | derived, set(alignment_for(version)))
        self.assertEqual(owned & derived, set())
        sources = {row['key'] for row in CONTRACT_FIELDS
                   if opening_source(row, OPENING_VERSION)}
        for key in ('protagonist_origin', 'core_premise', 'world_tiers', 'world_resource',
                    'world_scale', 'world_ladder', 'promise_anchor'):
            self.assertIn(key, sources)
        # The opening/7 order: the core idea right after the genre, the size decision on the last
        # legal slot before the world, and the world structure before the scale ladder that steps
        # on it; voice waits behind world+ladder, and the opponent network precedes its relations.
        gates = [ident for ident, _title in creation.GATES]
        self.assertEqual(gates[:4], ['genre', 'premise', 'scale', 'world'])
        self.assertEqual(gates.index('world') + 1, gates.index('ladder'))
        self.assertEqual(creation.value_fields('premise', OPENING_VERSION),
                         ('novelty', 'first_cause', 'stance', 'dark_side'))

    def test_the_world_section_table_separates_the_floor_from_the_grand_sections(self):
        """opening/5 adds `powers`/`cosmology`; the per-tier floor does not become the whole table.

        A tier's floor is the world its line walks through. The two structural sections are required
        only when the opening declared something that lives there (`world.tiers`/`world.resource`/
        a grand scale on the ladder); imported settings only require what they declare.
        """
        from novel_ledger import world
        self.assertEqual(len(world.ALL_SECTIONS), 12)
        self.assertIn('powers', world.ALL_SECTIONS)
        self.assertIn('cosmology', world.ALL_SECTIONS)
        declared = {
            'world': {'tiers': [{'name': '一阶登记员'}], 'resource': {'name': '车费'}},
            'ladder': {'ladder': [{'stage': '全国承运网', 'scope': '一界'}]},
        }
        sections = world.required_sections('t3', declared)
        self.assertIn('powers', sections, 'declared tiers must be mirrored in the world')
        self.assertIn('cosmology', sections, 'a grand scale needs the cosmology section')
        self.assertLessEqual(set(world.required_sections('t3')), set(sections))
        # An import without extra declarations uses only its tier floor.
        self.assertEqual(tuple(world.declared_sections({})), ())
        self.assertEqual(set(world.required_sections('t3', {})),
                         set(world.required_sections('t3')))

    def test_the_gate_set_derives_every_alignment_field_from_gates_it_has(self):
        """A gate that re-sources a field must still resolve it, and own the keys alignment reads.

        `opening_source` picks the declared mapping, so a field may not silently fall back to a gate
        that no longer exists; and the value keys the alignment reads must be owned by that gate, or
        `_field_groups` would ask a gate for a key its own validator refuses.
        """
        from novel_ledger import creation
        from novel_ledger.contracts import (CONTRACT_FIELDS, DERIVED_FIELDS, alignment_for,
                                            opening_source)
        version = creation.OPENING_VERSION
        for row in CONTRACT_FIELDS:
            if row['key'] in DERIVED_FIELDS                     or row['key'] not in alignment_for(version):
                continue
            source = opening_source(row, version)
            if not source:
                continue
            gate, key = source
            with self.subTest(field=row['key']):
                self.assertIn(gate, creation.gate_ids(version),
                              'a gate set may only source fields from gates it actually has')
                reads = set(row.get('shape') or ()) if key is None else {key}
                self.assertTrue(reads <= set(creation.value_fields(gate, version)),
                                'the gate must own the keys alignment reads: %s' % sorted(reads))

    def test_required_material_never_charges_twice_for_one_fact(self):
        """The thinning pass is a declared relationship, not an accident of two similar payloads.

        It covers both shapes a real run produced: a projection whose source is also required, and
        two names whose content is byte-identical. A dropped name stays reachable in `records`.
        """
        from novel_ledger import context
        self.assertEqual(context.projects_from('world_core'), 'world_model')
        self.assertIsNone(context.projects_from('design:book'))
        records = {'contract': 'h0', 'world_model': 'h1', 'world_core': 'h2',
                   'state': 'h3', 'complete_state': 'h3'}
        both = ['contract', 'world_model', 'world_core', 'state', 'complete_state']
        self.assertEqual(context.thin_required(records, both),
                         ['contract', 'world_model', 'state'])
        # Where no source is required the projection is exactly what the worker should read.
        self.assertEqual(context.thin_required(records, ['world_core', 'complete_state']),
                         ['world_core', 'complete_state'])
        self.assertEqual(context.thin_required({'world_model': 'h1', 'world_core': 'h2'},
                                               ['world_model', 'world_core']), ['world_model'])

    def test_book_state_invariants_are_checked_where_the_state_is_read(self):
        """Two fields that must move together are how a project ends up running while still paused.

        The check runs on every status read, so the command that produced the contradiction reports
        it instead of a later command discovering it.
        """
        from novel_ledger import book_state
        good = {'status': 'running', 'draft': None, 'accepted_findings': [], 'rework': {}}
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
        current = {'understanding': contracts.UNDERSTANDING_CAPABILITY,
                   'scene_identity': contracts.SCENE_IDENTITY_CAPABILITY,
                   'reading_dependencies': contracts.READING_DEPENDENCIES_CAPABILITY}
        self.assertEqual(contracts.capabilities_for({'capabilities': current}), current)
        for invalid in (None, {}, [], {**current, 'scene_identity': 'scene-identity/1'},
                        {key: value for key, value in current.items() if key != 'understanding'}):
            with self.subTest(capabilities=invalid):
                self.assertCode('capability', contracts.capabilities_for, {'capabilities': invalid})
        with self.assertRaises(Error) as caught:
            contracts.capabilities_for({'capabilities': {**current, 'scene_identity': 'scene-idenity/2'}})
        self.assertEqual(caught.exception.code, 'capability')
        self.assertEqual(caught.exception.details['unknown'], ['scene_identity=scene-idenity/2'])
        # The producer builds the same strings the consumer compares against.
        source = (ROOT / 'scripts' / 'novel_ledger' / 'context.py').read_text(encoding='utf-8')
        for literal in ("'editorial/1'", "'understanding/1'", "'scene-identity/2'", "'reading-dependencies/1'",
                        "'opening-bounds/1'", "'volume-outline/1'", "'scene-memory/1'", "'hook-links/1'"):
            with self.subTest(literal=literal):
                self.assertNotIn(literal, source, 'capability strings belong to contracts, not to a second copy')




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


class HookDeclarationTests(unittest.TestCase):
    """The promise ledger's field tables are one declaration, read by templates and checks alike."""

    def test_the_hook_fields_are_declared_and_a_missing_array_is_a_shape_error(self):
        from novel_ledger import drift
        self.assertIn('hooks', drift.VOLUME_FIELDS)
        self.assertIn('hooks', drift.CHAPTER_FIELDS)
        self.assertIn('hook', drift.ITEM_KINDS)
        self.assertTrue(drift.HOOK_ACTIONS)
        book = seeded_book(contract(chapters=2, volumes=1))
        rows = volume_rows(book, ['v1'])
        rows[0].pop('hooks')
        with self.assertRaises(Error) as caught:
            drift_validation.validate_volume_outline({'volumes': rows}, book['contract'], book['world'],
                                          {}, {}, ['v1'], book['state'])
        self.assertEqual(caught.exception.code, 'design_drift')
        criteria = {finding['criterion'] for finding in caught.exception.details['findings']}
        self.assertIn('volume_hook', criteria, str(caught.exception.details['findings'])[:400])


class RelationDeltaDeclarationTests(unittest.TestCase):
    """The fifth increment and the optional volume terminals are one declaration, like the hooks.

    The relation coordinate, the blank forms and the writer's self-check lines all read the same
    tables in `drift`, so a comparison the brief asks for is a comparison the engine performs.
    """

    def test_the_relation_and_terminal_fields_are_declared_in_every_table(self):
        from novel_ledger import drift
        for table, field in ((drift.VOLUME_FIELDS, 'relations'),
                             (drift.VOLUME_FIELDS, 'reader_knowledge'),
                             (drift.CHAPTER_FIELDS, 'relations'),
                             (drift.DELTA_KINDS, 'relations'),
                             (drift.ITEM_KINDS, 'relations'),
                             (drift.ENTER_KINDS, 'relations')):
            with self.subTest(table=table, field=field):
                self.assertIn(field, table)
        self.assertEqual(drift.FIELDS['relations'], 'relations')
        self.assertEqual(drift.KIND_ALIASES['relation'], 'relations')
        self.assertEqual(drift.KIND_ALIASES['relations'], 'relations')

    def test_the_blank_forms_prefill_and_brief_read_the_same_tables(self):
        from novel_ledger import briefs, result_templates
        volume = result_templates.volume_row('v1')
        chapter = result_templates.chapter_row(1)
        # Optional by shape: the blank volume form carries both terminal arrays empty, the chapter
        # form carries the fifth increment array empty — leaving them empty is a legal declaration.
        self.assertEqual(volume['relations'], [])
        self.assertEqual(volume['reader_knowledge'], [])
        self.assertEqual(chapter['relations'], [])
        row = {'chapter': 1, 'clock': {'advance_days': 0},
               'relations': [{'source': 'shen', 'target': 'guan', 'key': 'alliance',
                              'from': None, 'to': '戒备', 'reason': '第一次交锋。'}]}
        prefiled = [item for item in result_templates.drift_items(row)
                    if item['kind'] == 'relations']
        self.assertEqual([item['key'] for item in prefiled], ['shen>guan:alliance'])
        self.assertEqual(prefiled[0]['planned'], {'from': None, 'to': '戒备'})
        self.assertIn('relations', briefs.stage('write'))
        self.assertIn('reader_knowledge', briefs.stage('volume_outline'))


class WebnovelSettingMethodTests(unittest.TestCase):
    """Dispatch labels must resolve to methods in the one creative guide."""

    def test_dispatch_labels_resolve_to_unique_documented_methods(self):
        from novel_ledger import creation
        guide = (ROOT / 'references' / 'hatch.md').read_text(encoding='utf-8')
        labels = catalog.LENSES + catalog.VOLUME_TURNS
        self.assertEqual(len(set(labels)), len(labels))
        self.assertEqual(creation.LENSES, catalog.LENSES)
        for label in labels:
            with self.subTest(lens=label):
                self.assertIsInstance(label, str)
                self.assertEqual(label, label.strip())
                self.assertEqual(guide.count('| ' + label + ' |'), 1)

    def test_the_lenses_cover_the_four_web_serial_generator_families(self):
        labels = catalog.LENSES
        self.assertTrue(any('金手指' in label for label in labels))
        self.assertTrue(any('等级' in label for label in labels))
        self.assertTrue(any('换图' in label or '对手' in label for label in labels))
        self.assertTrue(any('通货' in label for label in labels))

    def test_the_legacy_literary_labels_are_gone(self):
        self.assertFalse({'混搭', '倒置', '绑定', '闭环'} & set(catalog.LENSES))


if __name__ == '__main__':
    unittest.main()
