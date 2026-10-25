"""The built-in style library: registration, contract selection, and the writer's channel to it.

The catalog decouples profiles from the mechanism: an archive is a file under references/styles/
plus one registry entry, the contract names which one is in force (`style_profile`), and a writing
dispatch's guides carry the hub and the effective archive's file. These tests keep those three
sides from drifting apart — a renamed file, a dropped registry row, or a patch that quietly misses
the fast path all fail here.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'tests'))

from support import contract, drive, seeded_book

from novel_ledger import context, planning, style
from novel_ledger.bootstrap import local_application
from novel_ledger.contracts import STYLE_CATALOG, DEFAULTS, Error, profile_anchor
from novel_ledger.sqlite_store import SQLiteRepository


class StyleCatalogTests(unittest.TestCase):
    def test_every_registered_archive_exists_with_a_complete_anchor(self):
        self.assertTrue(STYLE_CATALOG)
        for name, row in STYLE_CATALOG.items():
            archive = ROOT / 'references' / row['file']
            self.assertTrue(archive.is_file(), '注册表声明了不存在的档案：%s' % name)
            anchor = row['anchor']
            self.assertEqual(set(anchor), {'han', 'sentences', 'sentence_mean', 'sentence_short_share',
                                           'paragraph_mean', 'paragraph_max', 'dialogue_share'}, name)
            for key, value in anchor.items():
                self.assertGreater(value, 0, (name, key))
            # han gates shape comparability and mirrors chapter_min; it is not the profile's length.
            self.assertEqual(anchor['han'], 2000, name)

    def test_the_default_name_is_registered_and_the_contract_choice_list_is_the_catalog(self):
        default = DEFAULTS['style_profile_default']
        self.assertIn(default, STYLE_CATALOG)
        row = next(r for r in planning.CONTRACT_FIELDS if r['key'] == 'style_profile')
        self.assertEqual(row['choices'], tuple(STYLE_CATALOG))
        self.assertEqual(row['default'], default)
        self.assertFalse(row['alignment'], 'style_profile 是参数字段，不参与门选择逐字对齐')

    def test_profile_anchor_names_its_archive_and_unknown_names_mean_the_default(self):
        default = profile_anchor()
        self.assertEqual(default['origin'], 'default')
        self.assertEqual(default['profile'], DEFAULTS['style_profile_default'])
        chosen = profile_anchor('账房掌门')
        self.assertEqual(chosen['profile'], '账房掌门')
        self.assertEqual(chosen['paragraph_mean'], STYLE_CATALOG['账房掌门']['anchor']['paragraph_mean'])
        self.assertNotEqual(chosen['paragraph_mean'], default['paragraph_mean'])
        # A pre-style_profile project or a custom PROJECT archive never registered a shape:
        # unknown and missing names still get the declared default floor, never silence.
        self.assertEqual(profile_anchor('不存在的档名'), default)
        self.assertEqual(profile_anchor(None), default)

    def test_baseline_falls_back_to_the_contract_profile(self):
        book = {'contract': {'style_profile': '神秘学双声部'}}
        self.assertEqual(style.baseline(book), profile_anchor('神秘学双声部'))
        self.assertEqual(style.baseline({'contract': {'style_profile': '自定义'}})['profile'],
                         DEFAULTS['style_profile_default'])


class StyleProfileContractTests(unittest.TestCase):
    def test_validate_contract_fills_the_default_and_rejects_unknown_names(self):
        self.assertEqual(planning.validate_contract(contract(2))['style_profile'],
                         DEFAULTS['style_profile_default'])
        raw = contract(2)
        raw['style_profile'] = '市集烟火'
        with self.assertRaises(Error):
            planning.validate_contract(raw)
        raw['style_profile'] = '账房掌门'
        self.assertEqual(planning.validate_contract(raw)['style_profile'], '账房掌门')

    def test_style_material_names_the_effective_profile(self):
        material = context.style_material({'contract': {'style_profile': '账房掌门', 'voice': 'v'}}, None)
        self.assertEqual(material['profile'], '账房掌门')
        self.assertEqual(material['anchor']['profile'], '账房掌门')
        self.assertEqual(context.style_material({}, None)['profile'],
                         DEFAULTS['style_profile_default'])


class StyleProfileDispatchTests(unittest.TestCase):
    """The writer's channel: guides carry the hub and the effective archive; patch switches it."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / 'book'
        raw = contract(2)
        raw.update(narrative_tracking=True, editorial_features=True, style_profile='账房掌门')
        self.repo = SQLiteRepository.initialize(self.project, seeded_book(raw))
        self.app = local_application(self.repo)
        self.owner = self.app.run(through=1, source='工程夹具：一章。')['owner']

    def tearDown(self):
        self.repo.close()
        self.temp.cleanup()

    def write_task_guides(self):
        handoff = drive(self.app, self.owner, until='write')
        self.assertEqual(handoff['task']['stage'], 'write')
        task = json.loads(Path(handoff['task']['task_path']).read_text(encoding='utf-8'))
        return [Path(path) for path in task['guides']]

    def test_write_guides_carry_the_hub_and_the_registered_archive(self):
        guides = self.write_task_guides()
        names = [guide.name for guide in guides]
        self.assertIn('style.md', names)
        archive = next(guide for guide in guides if guide.name == '账房掌门.md')
        self.assertEqual(archive.parent.name, 'styles')
        self.assertTrue(archive.is_file())

    def test_a_custom_project_archive_overrides_the_catalog_choice_in_guides(self):
        custom = self.project / 'style-profile.md'
        custom.write_text('# 文风档案\n\n作者确认的自定义档案。', encoding='utf-8')
        guides = self.write_task_guides()
        self.assertIn(custom.resolve(), [guide.resolve() for guide in guides])

    def test_recontract_patch_switches_the_profile_in_place(self):
        result = self.app.recontract({'style_profile': '神秘学双声部'}, '作者要求换档。',
                                     self.owner, patch=True)
        self.assertTrue(result['applied_in_place'])
        self.assertEqual(result['amended_fields'], ['style_profile'])
        book = self.repo.load()
        self.assertEqual(book['contract']['style_profile'], '神秘学双声部')
        self.assertIsNone(book.get('pending_contract'), '参数换档不得进入重写分支')
        self.assertEqual(style.baseline(book)['profile'], '神秘学双声部')


if __name__ == '__main__':
    unittest.main()
