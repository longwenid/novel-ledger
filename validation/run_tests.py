"""Standard-library boundary checks, an e2e tier, and the complete regression entry.

Three tiers share one discovery space. `fast` is the daily gate: the v2 boundaries that must
never regress (the architecture graph, the domain/port/CLI boundaries, the five-step pipeline
shape and its outline chain, the storage and dependency bounds, and the runner itself) plus one
representative behavior per domain — budgeted wall clock, currently 120 seconds, so the gate
stays usable as feedback instead of accreting back into a slow suite. `e2e` carries the
heavyweight end-to-end files (multi-chapter writing flows, real CLI process handoffs, frozen
installs, continuity); `full` discovers everything and remains the strict superset (the guard
in `tests/test_validation_runner.py` checks subset and disjointness, plus non-empty boundaries
for architecture, domain, ports, CLI and revision bounds). Every entry must import on the
current tree, so a module that is mid-migration belongs in a named case here only once it is
green again.
"""
import argparse
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# The fast gate keeps the boundary scans and one representative behavior per domain. The heavy
# end-to-end files live in E2E below; the wall-clock budget keeps the daily gate honest.
FAST = (
    'test_architecture', 'test_domain_boundaries', 'test_application_ports',
    'test_cli_boundary', 'test_dependency_bounds', 'test_outlines',
    'test_pipeline_shapes.PipelineShapeTests', 'test_review_material', 'test_storage_growth',
    'test_context_growth', 'test_plot_precision',
    'test_snapshot_integrity', 'test_snapshot_probe', 'test_verification', 'test_outline_lock',
    'test_prose_lint.LintUnitTests',
    'test_prose_lint.LintFlowTests.test_preview_answers_every_defect_in_one_call',
    'test_style_voice', 'test_style_guard_flow',
    'test_validation_runner', 'test_opening_architecture',
    # Selected remote improvements and retained local provenance/evidence boundaries.
    'test_error_taxonomy', 'test_remote_integration',
    'test_host_authority',
    # The fast gate pins automatic revision bounds with one end-to-end case; the full gate
    # additionally covers proposal authorization, changed sources and rollback.
    'test_revision_bounds.RevisionBoundsTests.test_a_revision_inside_the_window_opens_its_exact_range',
)

# The heavyweight end-to-end tier: whole-book writing flows, real CLI process handoffs, frozen
# installs and long continuity runs. Each file here costs tens of seconds by nature.
E2E = (
    'test_fast_writing', 'test_execution_handoff', 'test_engine_runtime',
    'test_continuity_flow', 'test_runtime', 'test_longform', 'test_architecture_repairs',
)

# The daily gate must stay feedback-speed: a green run that blows the budget fails the gate,
# so adding weight to FAST requires paying for it here first.
FAST_BUDGET_SECONDS = 120


def build_suite(group):
    sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'tests')]
    loader = unittest.TestLoader()
    names = None if group == 'full' else (FAST if group == 'fast' else E2E)
    suite = (loader.discover(str(ROOT / 'tests')) if names is None
             else loader.loadTestsFromNames(names))
    if loader.errors:
        raise ValueError('\n'.join(loader.errors))
    return suite


def test_ids(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from test_ids(item)
        else:
            yield item.id()


def over_budget(group, elapsed):
    """True when a gate run must fail for wall clock even with green tests."""
    return group == 'fast' and elapsed > FAST_BUDGET_SECONDS


def main(argv=None):
    parser = argparse.ArgumentParser(description='运行快速边界检查或完整工程回归。')
    parser.add_argument('suite', choices=('fast', 'e2e', 'full'), nargs='?', default='fast')
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
    started = time.monotonic()
    result = unittest.TextTestRunner(verbosity=2 if args.verbose else 1).run(suite)
    elapsed = time.monotonic() - started
    print('%s wall clock: %.1fs' % (args.suite, elapsed), file=sys.stderr)
    if result.wasSuccessful() and over_budget(args.suite, elapsed):
        print('fast 门超出时间预算 %.0fs（实测 %.1fs）：门必须保持反馈速度，'
              '把重量移入 e2e 或先调预算再加重。' % (FAST_BUDGET_SECONDS, elapsed), file=sys.stderr)
        return 1
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())
