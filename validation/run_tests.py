"""Standard-library fast boundary checks and complete regression entry points.

The fast gate is the set of v2 boundaries that must never regress: the architecture graph, the
domain/port/CLI boundaries, the five-step pipeline shape and its outline chain, the storage and
dependency bounds, and the runner itself. It is a strict subset of `full` (the guard in
`tests/test_validation_runner.py` checks that, plus non-empty boundaries for architecture, domain,
ports, CLI and revision bounds) and every entry must import on the current tree, so a module that is
mid-migration belongs in a named case here only once it is green again.
"""
import argparse
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# The v2 gate: opening gates and the outline chain are the new spine, so `test_outlines` and
# `test_pipeline_shapes` carry the end-to-end path that used to live in the review-flow tests.
FAST = (
    'test_architecture', 'test_domain_boundaries', 'test_application_ports',
    'test_cli_boundary', 'test_dependency_bounds', 'test_longform', 'test_outlines',
    'test_pipeline_shapes.PipelineShapeTests', 'test_review_material', 'test_storage_growth',
    'test_context_growth', 'test_plot_precision',
    'test_snapshot_integrity', 'test_snapshot_probe', 'test_verification', 'test_outline_lock', 'test_fast_writing',
    'test_prose_lint.LintUnitTests',
    'test_prose_lint.LintFlowTests.test_preview_answers_every_defect_in_one_call',
    'test_style_voice', 'test_style_guard_flow',
    'test_validation_runner', 'test_architecture_repairs', 'test_opening_architecture',
    # The v2.1 execution contract: the taxonomy guard, the content-preview data path, and the
    # mechanical receipt assembly that turns a steady-state chapter into ~6 model calls.
    'test_error_taxonomy',
    'test_execution_handoff.ContentPreviewHandoffTests',
    'test_execution_handoff.WriteReceiptHandoffTests',
    'test_execution_handoff.ExecutionHandoffTests.test_first_identity_fault_hands_back_without_reset_ceremony',
    # The fast gate pins automatic revision bounds with one end-to-end case; the full gate
    # additionally covers proposal authorization, changed sources and rollback.
    'test_revision_bounds.RevisionBoundsTests.test_a_revision_inside_the_window_opens_its_exact_range',
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
    parser.add_argument('suite', choices=('fast', 'full'), nargs='?', default='fast')
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
