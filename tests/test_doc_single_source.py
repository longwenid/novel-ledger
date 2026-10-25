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


if __name__ == '__main__':
    unittest.main()
