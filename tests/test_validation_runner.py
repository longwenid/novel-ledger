"""The fast gate stays a strict, duplicate-free subset of complete discovery."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ValidationRunnerTests(unittest.TestCase):
    def test_groups_work_outside_the_checkout_and_keep_critical_boundaries(self):
        with tempfile.TemporaryDirectory() as directory:
            groups = {}
            for group in ('fast', 'full'):
                result = subprocess.run(
                    [sys.executable, str(ROOT / 'validation' / 'run_tests.py'), group, '--list'],
                    cwd=directory, capture_output=True, text=True, encoding='utf-8')
                self.assertEqual(result.returncode, 0, result.stderr)
                ids = result.stdout.splitlines()
                self.assertEqual(len(ids), len(set(ids)))
                groups[group] = set(ids)
        self.assertTrue(groups['fast'] < groups['full'])
        for boundary in ('test_architecture.', 'test_domain_boundaries.', 'test_application_ports.',
                         'test_cli_boundary.', 'test_revision_bounds.'):
            self.assertTrue(any(name.startswith(boundary) for name in groups['fast']), boundary)

    def test_invalid_group_fails_instead_of_silently_skipping_tests(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / 'validation' / 'run_tests.py'), 'unknown'],
            capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 2)


if __name__ == '__main__':
    unittest.main()
