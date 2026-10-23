"""The fast and e2e gates stay strict, duplicate-free subsets of complete discovery."""
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def runner_module():
    spec = importlib.util.spec_from_file_location('run_tests', ROOT / 'validation' / 'run_tests.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ValidationRunnerTests(unittest.TestCase):
    def test_groups_work_outside_the_checkout_and_keep_critical_boundaries(self):
        with tempfile.TemporaryDirectory() as directory:
            groups = {}
            for group in ('fast', 'e2e', 'full'):
                result = subprocess.run(
                    [sys.executable, str(ROOT / 'validation' / 'run_tests.py'), group, '--list'],
                    cwd=directory, capture_output=True, text=True, encoding='utf-8')
                self.assertEqual(result.returncode, 0, result.stderr)
                ids = result.stdout.splitlines()
                self.assertEqual(len(ids), len(set(ids)))
                groups[group] = set(ids)
        self.assertTrue(groups['fast'] < groups['full'])
        self.assertTrue(groups['e2e'] < groups['full'])
        # The two selected gates must not double-run a case; weight belongs in exactly one tier.
        self.assertEqual(groups['fast'] & groups['e2e'], set())
        for boundary in ('test_architecture.', 'test_domain_boundaries.', 'test_application_ports.',
                         'test_cli_boundary.', 'test_revision_bounds.'):
            self.assertTrue(any(name.startswith(boundary) for name in groups['fast']), boundary)

    def test_invalid_group_fails_instead_of_silently_skipping_tests(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / 'validation' / 'run_tests.py'), 'unknown'],
            capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 2)

    def test_budget_gate_fails_only_fast_and_only_when_exceeded(self):
        module = runner_module()
        self.assertGreater(module.FAST_BUDGET_SECONDS, 0)
        self.assertTrue(module.over_budget('fast', module.FAST_BUDGET_SECONDS + 0.001))
        self.assertFalse(module.over_budget('fast', module.FAST_BUDGET_SECONDS))
        # A slow e2e or full run is expected; the budget polices the daily gate only.
        self.assertFalse(module.over_budget('e2e', module.FAST_BUDGET_SECONDS * 100))
        self.assertFalse(module.over_budget('full', module.FAST_BUDGET_SECONDS * 100))


if __name__ == '__main__':
    unittest.main()
