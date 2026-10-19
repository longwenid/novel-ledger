"""Domain boundary checks run against plain values, with no project or SQLite setup."""
import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from novel_ledger import design_queries, entities, facts, planning, result_templates, workflow
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

    def test_unknown_task_stage_is_rejected_instead_of_degrading(self):
        from novel_ledger import stages
        with self.assertRaises(Error):
            stages.require_stage('not_a_stage')
        with self.assertRaises(Error):
            result_templates.template('not_a_stage', 1, {})
        self.assertEqual(stages.require_stage('write'), 'write')

    def test_every_version_renders_a_rule_and_a_direction_for_each_of_its_gates(self):
        """Every gate set still in flight must hand its gates a deliverable rule and a direction.

        `OPENING_DIRECTION_GATES` is a flat table keyed by gate id, not partitioned by version: when
        a newer gate set adds a gate the table becomes a superset of the older sets that share its
        gate names (the direction text belongs to the redesign; opening/1 and /2 predate it and keep
        their own briefs). `VALUE_RULES` and `GATE_NOTES` are partitioned by version, and a version
        whose rule block was folded into a newer one must not KeyError when a project opened under it
        asks (opening/1 has no per-gate notes, which is normal: that protocol never carried them).
        """
        from novel_ledger import creation
        from novel_ledger.contracts import OPENING_DIRECTION_GATES, OPENING_VERSION
        for version in (1, 2, 3, 4, 5, OPENING_VERSION):
            with self.subTest(version=version):
                self.assertIn(version, creation.VALUE_RULES, '每版必须有规则块')
                gates = creation.gate_ids(version)
                for gate in gates:
                    self.assertTrue(creation.value_rules(version, gate).strip())
                notes = creation.GATE_NOTES.get(version) or {}
                self.assertLessEqual(set(notes), set(gates), '门内说明只能属于本版已有的门')
                for gate, note in notes.items():
                    self.assertTrue(note.strip())
        # The direction table was introduced with the male-channel redesign (v3) and grew with each
        # later gate set; the two earliest protocols keep their own briefs instead.
        for version in (3, 4, OPENING_VERSION):
            with self.subTest(direction_for=version):
                self.assertLessEqual(set(creation.gate_ids(version)), set(OPENING_DIRECTION_GATES),
                                     '重设计后的每一门必须有方向口径')
        self.assertEqual(set(creation.gate_ids(OPENING_VERSION)), set(OPENING_DIRECTION_GATES),
                         '当前版本的门与方向表必须一一对应')

    def test_the_current_gate_set_owns_every_alignment_field_it_claims(self):
        """The male-channel redesign is a gate set, so its ownership must close without a project.

        Each later protocol adds gates without renaming the older decisions; every version's
        alignment fields therefore have to be owned by exactly one of its gates, or a new gate that
        forgot its field only fails much later, at contract alignment.
        """
        from novel_ledger import creation
        from novel_ledger.contracts import (CONTRACT_FIELDS, DERIVED_FIELDS,
                                            OPENING_VERSION, alignment_for, opening_source)
        for version, size in ((3, 10), (4, 11), (OPENING_VERSION, 13)):
            gates = [ident for ident, _title in creation.GATE_SETS[version]]
            with self.subTest(version=version):
                self.assertEqual(len(gates), size)
                self.assertEqual(creation.SYSTEM_GATES[version], ('scale',))
                for gate in gates:
                    self.assertTrue(creation.value_fields(gate, version),
                                    'a gate must own at least one field')
                owned = {row['key'] for row in CONTRACT_FIELDS
                         if row.get('since', 1) <= version and opening_source(row, version)
                         and row['key'] not in DERIVED_FIELDS}
                derived = {'entities', 'red_lines', 'volumes', 'world_rules', 'world_premise'}
                self.assertEqual(owned | derived, set(alignment_for(version)))
                self.assertEqual(owned & derived, set())
        sources = {row['key'] for row in CONTRACT_FIELDS
                   if row.get('since', 1) <= OPENING_VERSION and opening_source(row, OPENING_VERSION)}
        for key in ('protagonist_origin', 'core_premise', 'world_tiers', 'world_resource',
                    'world_scale', 'world_ladder', 'promise_anchor'):
            self.assertIn(key, sources)
        # The v5 order: the core idea right after the genre, the origin behind it, and the world
        # structure before the scale ladder that steps on it.
        gates = [ident for ident, _title in creation.GATE_SETS[OPENING_VERSION]]
        self.assertEqual(gates[:4], ['genre', 'premise', 'voice', 'scale'])
        self.assertEqual(gates.index('world') + 1, gates.index('ladder'))
        self.assertEqual(creation.value_fields('premise', OPENING_VERSION),
                         ('novelty', 'first_cause', 'stance', 'dark_side'))

    def test_the_world_section_table_separates_the_floor_from_the_grand_sections(self):
        """opening/5 adds `powers`/`cosmology`; the per-tier floor does not become the whole table.

        A tier's floor is the world its line walks through. The two structural sections are required
        only when the opening declared something that lives there (`world.tiers`/`world.resource`/
        a grand scale on the ladder), which is what keeps a legacy ten-section world valid.
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
        # A legacy choice set declares neither, and its floor stays the ten original domains.
        self.assertEqual(tuple(world.declared_sections({})), ())
        self.assertEqual(set(world.required_sections('t3', {})),
                         set(world.required_sections('t3')))

    def test_every_protocol_derives_its_alignment_fields_from_gates_it_has(self):
        """A gate set that re-sources or renames a gate must still resolve every alignment field.

        `opening_source` inherits forward from the newest declared mapping at or below the asked
        version, so adding a gate set does not silently fall back to a gate that no longer exists.
        The value keys the alignment reads must also be owned by that gate, or `_v2_groups` would ask
        a gate for a key its own validator refuses. opening/1 predates this ownership table: its
        contract is projected by hand (`_v1_groups`, with `title` authored by the author), so its only
        permitted mismatch is that documented authored field.
        """
        from novel_ledger import creation
        from novel_ledger.contracts import (CONTRACT_FIELDS, DERIVED_FIELDS, alignment_for,
                                            opening_source)
        for version in (2, 3, 4, 5, 6):
            for row in CONTRACT_FIELDS:
                if row.get('since', 1) > version or row['key'] in DERIVED_FIELDS \
                        or row['key'] not in alignment_for(version):
                    continue
                source = opening_source(row, version)
                if not source:
                    continue
                gate, key = source
                with self.subTest(field=row['key'], version=version):
                    self.assertIn(gate, creation.gate_ids(version),
                                  'a version may only source fields from gates it actually has')
                    reads = set(row.get('shape') or ()) if key is None else {key}
                    self.assertTrue(reads <= set(creation.value_fields(gate, version)),
                                    'the gate must own the keys alignment reads: %s' % sorted(reads))
        # v1's hand projection: the only *sourced* field its table cannot resolve is the authored title.
        unresolvable = []
        for row in CONTRACT_FIELDS:
            if row.get('since', 1) > 1 or row['key'] not in alignment_for(1) \
                    or row['key'] in DERIVED_FIELDS:
                continue
            source = opening_source(row, 1)
            if source and source[0] not in creation.gate_ids(1):
                unresolvable.append(row['key'])
        self.assertEqual(unresolvable, ['title'])

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

    def test_the_hook_fields_are_declared_in_the_drift_tables(self):
        from novel_ledger import drift
        self.assertIn('hooks', drift.VOLUME_FIELDS)
        self.assertIn('hooks', drift.CHAPTER_FIELDS)
        self.assertIn('hook', drift.ITEM_KINDS)
        self.assertTrue(drift.HOOK_ACTIONS)

    def test_a_volume_outline_without_the_hook_array_is_a_shape_error(self):
        from novel_ledger import drift
        book = seeded_book(contract(chapters=2, volumes=1))
        rows = volume_rows(book, ['v1'])
        rows[0].pop('hooks')
        with self.assertRaises(Error) as caught:
            drift.validate_volume_outline({'volumes': rows}, book['contract'], book['world'],
                                          {}, {}, ['v1'], book['state'])
        self.assertEqual(caught.exception.code, 'design_drift')
        criteria = {finding['criterion'] for finding in caught.exception.details['findings']}
        self.assertIn('volume_hook', criteria, str(caught.exception.details['findings'])[:400])


class WebnovelSettingMethodTests(unittest.TestCase):
    """The opening's setting generators are web-serial methods with a required output.

    Rewriting the lenses from generic literary moves (混搭/倒置/闭环…) to web-serial setting
    generators is an author decision, so the wording is not pinned here. What the engine can check is
    the shape — a unique label, a method and an explicit "what must come out of it" — that the four
    generator families the decision names are covered, and that the world/edge gate notes carry the
    constraints the option writer has to satisfy (a visible ladder, an accountable scarce resource,
    a first conflict inside the opening three chapters, and room to add layers).
    """

    def lenses(self):
        from novel_ledger import contracts
        return contracts.LENSES

    def test_every_lens_is_a_nonempty_method_triple(self):
        from novel_ledger import creation
        lenses = self.lenses()
        self.assertGreaterEqual(len(lenses), 10)
        labels = [label for label, _point, _structure in lenses]
        self.assertEqual(len(set(labels)), len(labels), 'lens labels must be unique')
        self.assertEqual(list(creation.LENSES), labels,
                         'the dispatch names the same labels the table declares')
        for label, point, structure in lenses:
            with self.subTest(lens=label):
                self.assertEqual(label, label.strip())
                self.assertGreaterEqual(len(label), 3)
                self.assertGreaterEqual(len(point.strip()), 20,
                                        'a lens needs a method, not a label')
                self.assertGreaterEqual(len(structure.strip()), 15,
                                        'a lens must state what it has to produce')

    def test_the_lenses_cover_the_four_web_serial_generator_families(self):
        labels = [label for label, _point, _structure in self.lenses()]
        self.assertTrue(any('金手指' in label for label in labels),
                        'no advantage-supply generator in ' + repr(labels))
        self.assertTrue(any('等级' in label for label in labels),
                        'no level-ladder generator in ' + repr(labels))
        self.assertTrue(any('换图' in label or '对手' in label for label in labels),
                        'no opponent/stage-escalation generator in ' + repr(labels))
        self.assertTrue(any('通货' in label for label in labels),
                        'no hard-currency generator in ' + repr(labels))

    def test_the_world_and_edge_gate_notes_state_their_constraints(self):
        from novel_ledger import creation
        from novel_ledger.contracts import OPENING_DIRECTION_GATES
        note = creation.gate_note(3, 'world')
        self.assertTrue(note.strip())
        for word in ('等级', '资源', '三章'):
            self.assertIn(word, note)
        for word in ('历史', '文明', '矛盾', '资源'):
            self.assertIn(word, OPENING_DIRECTION_GATES['world'])
        self.assertIn('供料', OPENING_DIRECTION_GATES['edge'])
        # The world gate note belongs to opening/3; the earlier gate set never carried one.
        self.assertEqual(creation.gate_note(2, 'world'), '')

    def test_the_legacy_literary_labels_are_gone(self):
        labels = {label for label, _point, _structure in self.lenses()}
        self.assertEqual({'混搭', '倒置', '绑定', '闭环'} & labels, set(),
                         'legacy literary lenses are back in the label table')


if __name__ == '__main__':
    unittest.main()
