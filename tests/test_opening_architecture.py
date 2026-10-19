"""Opening/6 preserves world architecture across choices, dispatches and world records."""
import copy
import tempfile
import unittest
from pathlib import Path

from test_opening import VALUES, contract_from, walk, walk_to
from test_world_grand import base_model, check, choices_v5, record
from novel_ledger import contracts, creation, world, workflow
from novel_ledger.bootstrap import local_application as Application
from novel_ledger.contracts import Error
from novel_ledger.sqlite_store import SQLiteRepository

FRAME = VALUES['world']['architecture']
# Independent expected destinations, to catch a change in the authoritative mapping.
DESTINATIONS = {'space': ('geography', 'environment'),
                'history': ('history', 'present_effect'),
                'civilizations': ('factions', 'conflicts'),
                'conflict': ('rules', 'consequences'),
                'mystery': ('mysteries', 'truth')}


class WorldArchitectureTests(unittest.TestCase):
    def assertCode(self, code, function, *args):
        with self.assertRaises(Error) as caught:
            function(*args)
        self.assertEqual(caught.exception.code, code)

    def test_world_gate_requires_complete_frame_only_for_v6(self):
        value = copy.deepcopy(VALUES['world'])
        creation.validate_value('world', value, 6)
        for key in FRAME:
            for replacement in (None, '', [], {'unexpected': 'value'}):
                broken = copy.deepcopy(value)
                broken['architecture'][key] = replacement
                with self.subTest(key=key, replacement=replacement):
                    self.assertCode('opening_option', creation.validate_value, 'world', broken, 6)
            missing = copy.deepcopy(value)
            del missing['architecture'][key]
            self.assertCode('opening_option', creation.validate_value, 'world', missing, 6)
        value['architecture']['extra'] = '新增字段不能伪装成已选世界。'
        self.assertCode('opening_option', creation.validate_value, 'world', value, 6)
        del value['architecture']
        self.assertCode('opening_option', creation.validate_value, 'world', value, 6)
        creation.validate_value('world', value, 5)

    def test_contract_preserves_every_architecture_decision(self):
        state = walk(creation.begin(version=6))
        contract = contract_from(state)
        model = {'rules': [{'principle': '夜班退件必须登记负责人。'}]}
        creation.validate_contract(contract, state, model)
        self.assertEqual(contract['world_architecture'], FRAME)
        for key in FRAME:
            broken = copy.deepcopy(contract)
            broken['world_architecture'][key] += '后来另定一套。'
            with self.subTest(key=key):
                self.assertCode('opening_alignment', creation.validate_contract, broken, state, model)

    def test_world_requires_exact_text_in_the_designated_field(self):
        choices = choices_v5(tier='t0')
        choices['world']['architecture'] = copy.deepcopy(FRAME)
        model = base_model(choices)
        for key, (section, field) in DESTINATIONS.items():
            model[section].append(record(section, 'frame_' + key, **{field: FRAME[key]}))
        check(model, choices)
        self.assertTrue({'history', 'geography', 'factions', 'rules', 'mysteries'} <=
                        set(world.required_sections('t0', choices)))
        for key, (section, field) in DESTINATIONS.items():
            broken = copy.deepcopy(model)
            row = next(r for r in broken[section] if r['id'] == 'frame_' + key)
            # Keeping the original in another valid field must not satisfy the binding.
            other = next(f for f in world.SECTIONS[section] if f != field)
            row[other], row[field] = row[field], '被改写的世界背景。'
            with self.subTest(key=key):
                self.assertCode('world_alignment', check, broken, choices)
        legacy = choices_v5()
        check(base_model(legacy), legacy)

    def test_returning_to_world_invalidates_origin_only_in_new_order(self):
        for version, origin_retained in ((5, True), (6, False)):
            with self.subTest(version=version):
                complete = walk(creation.begin(version=version))
                restored = creation.back(complete, 'world', '世界重新构思。')
                self.assertEqual('origin' in creation.selected(restored), origin_retained)
                self.assertNotIn('ladder', creation.selected(restored))
                self.assertEqual(creation.current(restored)['id'], 'world')
                self.assertEqual(creation.opening_version(restored), version)

    def test_later_gate_reads_full_frozen_choices_across_reopening(self):
        for version in (5, 6):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as folder:
                book = workflow.preparing_book(guided=True, opening_version=version)
                book['creation'] = walk_to(book['creation'], 'edge')
                repo = SQLiteRepository.initialize(Path(folder) / 'book', book)
                try:
                    app = Application(repo)
                    app.advance()
                    pending = repo.pending()['input']
                    choices = repo.read_document(pending['records']['opening_choices'])
                    self.assertEqual(choices, creation.selected(book['creation']))
                    self.assertEqual('opening_choices' in pending['required'], version == 6)
                    if version == 6:
                        self.assertEqual(choices['world']['architecture'], FRAME)
                    # Reopening preserves both the frozen payload and the project's version.
                    frozen = copy.deepcopy(pending)
                    repo.close()
                    repo = SQLiteRepository(Path(folder) / 'book')
                    self.assertEqual(repo.pending()['input'], frozen)
                    self.assertEqual(creation.opening_version(repo.load()['creation']), version)
                finally:
                    repo.close()

    def test_regroup_rotates_gate_methods_and_legacy_keeps_global_rotation(self):
        for gate, expected in (('premise', '规则博弈'), ('world', '纪元断层'),
                               ('ladder', '非数值成长')):
            self.assertEqual(creation.LENSES[creation.lens_index(gate, 0, 6)], expected)
            self.assertNotEqual(creation.lens_index(gate, 0, 6), creation.lens_index(gate, 1, 6))
            self.assertEqual(creation.lens_index(gate, 0, 5), 0)
            self.assertEqual(creation.lens_index(gate, 1, 5), 1)
        self.assertEqual(contracts.OPENING_VERSION, 6)
