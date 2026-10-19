"""Validation must reject broken local navigation instead of reporting a false green."""
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / 'validation' / 'anchor_check.py'
SPEC = importlib.util.spec_from_file_location('novel_anchor_check', CHECKER)
anchors = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(anchors)


class AnchorCheckTests(unittest.TestCase):
    def test_heading_anchors_are_exact_and_duplicates_have_distinct_ids(self):
        source = '# 章纲检查\n# 章纲检查\n# API Rules\n```markdown\n# 示例\n```\n'
        self.assertEqual(anchors.heading_ids(source), {'章纲检查', '章纲检查-1', 'api-rules'})

    def test_missing_and_partial_anchors_fail_the_command(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'guide.md').write_text('# 章纲检查\n', encoding='utf-8')
            for target in ('guide.md#does-not-exist', 'guide.md#章纲', '#missing', 'missing.md'):
                with self.subTest(target=target):
                    (root / 'README.md').write_text('# 正文\n[引用](' + target + ')\n', encoding='utf-8')
                    run = subprocess.run([sys.executable, str(CHECKER), '--root', directory],
                                         capture_output=True, text=True, encoding='utf-8')
                    self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
                    self.assertIn('bad references: 1', run.stdout)

    def test_valid_local_links_external_links_and_fenced_examples(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'guide.md').write_text('# 章纲检查\n# 章纲检查\n', encoding='utf-8')
            (root / 'README.md').write_text(
                '# 当前页\n[本页](#当前页) [别页](guide.md#章纲检查-1) [文件](guide.md)\n'
                '[外部](https://example.com/missing#heading)\n'
                '```markdown\n[只是示例](missing.md)\n```\n', encoding='utf-8')
            _, bad = anchors.check(root)
            self.assertEqual(bad, [])


class MeasurementSnapshotTests(unittest.TestCase):
    def test_snapshot_detects_uncommitted_source_changes(self):
        spec = importlib.util.spec_from_file_location('novel_measure', ROOT / 'validation' / 'measure.py')
        measure = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(measure)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'scripts').mkdir()
            source = root / 'scripts' / 'sample.py'
            source.write_text('value = 1\n', encoding='utf-8')
            before = measure.snapshot_metadata(root)
            source.write_text('value = 2\n', encoding='utf-8')
            after = measure.snapshot_metadata(root)
            self.assertNotEqual(before['source_sha256'], after['source_sha256'])
            self.assertEqual(after['source_files'], 1)
            self.assertTrue(after['generated_at'])


if __name__ == '__main__':
    unittest.main()
