"""Standard-library fast boundary checks and complete regression entry points."""
import argparse
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Keep import/role/transaction boundaries and an end-to-end author/repair/delivery
# path in the fast gate. Full discovery always includes newly added test modules.
FAST = (
    'test_architecture', 'test_domain_boundaries', 'test_application_ports',
    'test_cli_boundary', 'test_frozen_reading', 'test_revision_bounds',
    'test_revision_repairs', 'test_bookpage', 'test_validation_runner',
    'test_runtime.RuntimeTests.test_first_chapter_approval_binds_exact_version',
    'test_runtime.RuntimeTests.test_fact_fix_and_short_repair_share_one_budget',
    'test_runtime.RuntimeTests.test_compact_loop_preserves_author_boundary_and_reaches_revision_completion_and_delivery',
    'test_runtime.RuntimeTests.test_worker_process_cannot_take_controller_actions',
)


def build_suite(group):
    sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'tests')]
    loader = unittest.TestLoader()
    suite = (loader.discover(str(ROOT / 'tests')) if group == 'full'
             else loader.loadTestsFromNames(FAST))
    if loader.errors:
        raise ValueError('\n'.join(loader.errors))
    return suite


def test_ids(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from test_ids(item)
        else:
            yield item.id()


def main(argv=None):
    parser = argparse.ArgumentParser(description='运行快速边界检查或完整工程回归。')
    parser.add_argument('suite', choices=('fast', 'full'))
    parser.add_argument('--list', action='store_true', help='只列出测试，不执行。')
    parser.add_argument('-v', '--verbose', action='store_true')
    args = parser.parse_args(argv)
    sys.dont_write_bytecode = True
    try:
        suite = build_suite(args.suite)
    except ValueError as exc:
        parser.exit(2, str(exc) + '\n')
    count = suite.countTestCases()
    if not count:
        parser.exit(2, '没有找到测试。\n')
    if args.list:
        print('\n'.join(test_ids(suite)))
        return 0
    print('%s: %d tests' % (args.suite, count), file=sys.stderr)
    result = unittest.TextTestRunner(verbosity=2 if args.verbose else 1).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())
