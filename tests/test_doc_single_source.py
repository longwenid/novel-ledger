"""Doc values that restate a source declaration must be guarded, or they drift.

The architecture already guards its diagram this way (references/architecture.md is compared
verbatim against docs/architecture.mmd). The same treatment applies to two restatements that
cost real debugging time when they disagreed with the engine: the style_window tolerances
quoted in the craft docs, and the per-tier world-model floor domains. Each test parses the
doc's own spelling and compares against the single source (contracts.DEFAULTS / world.TIER_SECTIONS),
so editing the value in one place without the other fails here, naming both files.
"""
import ast
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from novel_ledger import contracts, world


def read(rel):
    return (ROOT / rel).read_text(encoding='utf-8')


class StyleWindowDocTests(unittest.TestCase):
    def test_narrative_tolerance_block_matches_contracts(self):
        """The python block in narrative.md's 契约容差 section restates DEFAULTS verbatim."""
        source = read('references/narrative.md')
        blocks = re.findall(r'```python\n(\{.*?\})\n```', source, re.S)
        quoted = None
        for block in blocks:
            value = ast.literal_eval(block)
            if isinstance(value, dict) and 'sentence' in value:
                quoted = value
        self.assertIsNotNone(quoted, 'narrative.md 不再引用 style_window 数值块；请更新本测试的解析位置')
        self.assertEqual(quoted, contracts.DEFAULTS['style_window'])

    def test_protocol_field_row_matches_contracts(self):
        """protocol.md's field table carries the tolerances in its compact `{k:v}` spelling."""
        source = read('references/protocol.md')
        row = next(line for line in source.splitlines() if '| style_window |' in line)
        found = {key: float(value) for key, value in re.findall(r'(\w+):([\d.]+)', row)}
        self.assertTrue(found, 'protocol.md 的 style_window 行不再内联数值；请更新本测试的解析方式')
        expected = {key: float(value) for key, value in contracts.DEFAULTS['style_window'].items()}
        self.assertEqual(found, expected)


class TierFloorDocTests(unittest.TestCase):
    def test_world_doc_names_every_tier_floor(self):
        """world.md must spell out each tier's base domains, and they must equal world.TIER_SECTIONS.

        t1/t2 floors used to live only in source, so a doc reader could not tell which domains a
        mid-tier world owed; the doc now carries them and this keeps the two equal.
        """
        source = read('references/world.md')
        t0 = re.search(r'`t0=\(([^)]+)\)`', source)
        t1 = re.search(r'`t1=t0∪(\w+)`', source)
        t2 = re.search(r'`t2=t1∪(\w+)`', source)
        self.assertIsNotNone(t0, 'world.md 缺 t0 基础域说明')
        self.assertIsNotNone(t1, 'world.md 缺 t1 基础域说明')
        self.assertIsNotNone(t2, 'world.md 缺 t2 基础域说明')
        floors = world.TIER_SECTIONS
        self.assertEqual(tuple(t0.group(1).split(',')), floors['t0'])
        self.assertEqual(floors['t1'], world._ordered(set(floors['t0']) | {t1.group(1)}))
        self.assertEqual(floors['t2'], world._ordered(set(floors['t1']) | {t2.group(1)}))
        self.assertEqual(floors['t3'], world.BASE_SECTIONS)


class StyleCatalogDocTests(unittest.TestCase):
    def test_style_hub_table_matches_the_registered_catalog(self):
        """style.md's 内置文风目录 table restates the registry's (name, file) pairs.

        A profile is one archive file plus one registry entry; the hub table is how a reader finds
        the same set the engine dispatches, so renaming or adding an archive in one place without
        the other fails here, naming both files.
        """
        source = read('references/style.md')
        section = re.search(r'## 内置文风目录\n(.*?)\n## ', source, re.S)
        self.assertIsNotNone(section, 'style.md 不再含「内置文风目录」表；请更新本测试的解析位置')
        rows = re.findall(r'\[([^\]]+)\]\((styles/[^)]+)\)', section.group(1))
        self.assertTrue(rows, '内置文风目录表没有档案链接')
        found = {name.replace('（默认）', ''): path for name, path in rows}
        self.assertEqual(found, {name: row['file'] for name, row in contracts.STYLE_CATALOG.items()},
                         'style.md 目录表与 contracts.STYLE_CATALOG 不一致')
        self.assertIn('（默认）', section.group(1), '目录表未标注默认档')


class BlueprintCatalogDocTests(unittest.TestCase):
    def test_hatch_blueprint_tables_match_both_registered_layers(self):
        """hatch.md's 蓝图目录 tables name exactly both layers' registries.

        A blueprint is one registry entry plus one table row; the doc tables are how an author (and
        the `blueprint --name` argument) finds the same set the engine carries, so a rename or an
        addition in one place without the other fails here, naming both files. The design layer
        being empty is a real state this version ships in: the section then carries the
        vacancy sentence and no table, which parses to zero rows.
        """
        source = read('references/hatch.md')
        section = re.search(r'## 蓝图目录\n(.*?)\n## ', source, re.S)
        self.assertIsNotNone(section, 'hatch.md 不再含「蓝图目录」节；请更新本测试的解析位置')
        layers = {}
        for layer in ('structure', 'design'):
            part = re.search(r'### %s层\n(.*?)(?=### |\Z)' % ('结构' if layer == 'structure' else '设计'),
                             section.group(1), re.S)
            self.assertIsNotNone(part, 'hatch.md 蓝图目录缺 %s 层小节' % layer)
            layers[layer] = re.findall(r'^\|\s*`([^`]+)`\s*\|', part.group(1), re.M)
        self.assertTrue(layers['structure'], '结构层表没有档名行')
        self.assertEqual(layers['structure'], list(contracts.BLUEPRINT_CATALOG),
                         'hatch.md 结构层表与 contracts.BLUEPRINT_CATALOG 不一致')
        self.assertEqual(layers['design'], list(contracts.DESIGN_BLUEPRINT_CATALOG),
                         'hatch.md 设计层表与 contracts.DESIGN_BLUEPRINT_CATALOG 不一致（空目录对应无表，见小节内空置说明）')

    def test_blueprint_names_stay_unique_across_the_two_layers(self):
        """One namespace: a name on both layers would shadow, because the command resolves by name."""
        self.assertEqual(len(set(contracts.BLUEPRINT_CATALOG) | set(contracts.DESIGN_BLUEPRINT_CATALOG)),
                         len(contracts.BLUEPRINT_CATALOG) + len(contracts.DESIGN_BLUEPRINT_CATALOG))
        self.assertEqual(contracts.resolve_blueprint('主线副线缠绕')[0], 'structure')
        self.assertEqual(contracts.resolve_blueprint('不存在档'), (None, None))

    def test_every_blueprint_declares_the_same_boundary_line(self):
        """The catalog cannot drift into a plot library one entry at a time."""
        self.assertTrue(contracts.BLUEPRINT_BOUNDARY)
        self.assertTrue(contracts.DESIGN_BLUEPRINT_BOUNDARY)
        for name, entry in contracts.BLUEPRINT_CATALOG.items():
            with self.subTest(blueprint=name):
                self.assertEqual(set(entry), {'name', 'layer', 'skeleton', 'drivers', 'echo'})
                self.assertEqual(entry['name'], name)
                self.assertEqual(entry['layer'], 'structure')
                for key in ('skeleton', 'drivers', 'echo'):
                    self.assertTrue(entry[key].strip(), '蓝图 %s 的 %s 为空' % (name, key))
        for name, entry in contracts.DESIGN_BLUEPRINT_CATALOG.items():
            with self.subTest(design_blueprint=name):
                self.assertEqual(set(entry), {'name', 'file', 'summary', 'version'})
                self.assertEqual(entry['name'], name)
                for key in ('file', 'summary', 'version'):
                    self.assertTrue(entry[key].strip(), '设计蓝图 %s 的 %s 为空' % (name, key))


if __name__ == '__main__':
    unittest.main()
