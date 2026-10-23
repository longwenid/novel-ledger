"""The error taxonomy guard: every code the engine raises is classified exactly once.

Content / controller / technical is a behavioural contract, not a comment: content codes answer
previews as data and never enter the failure accounting, controller codes route recovery to the
controller, everything else keeps counting. A new code added without a decision would silently
pick a side, so this test walks every raise site and refuses the unclassified.
"""
import ast
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from novel_ledger.contracts import CONTENT_ERRORS, CONTROLLER_ERRORS, TECHNICAL_ERRORS

ROOT = Path(__file__).resolve().parents[1]
# Callables that receive a raise code as a literal argument, next to require/Error themselves.
CODE_ARGS = {'require': 1, 'Error': 0, '_reject': 1}


def raised_codes():
    """Every error code literally raised under scripts/, with one site per occurrence."""
    codes = {}
    for path in (ROOT / 'scripts').rglob('*.py'):
        if '__pycache__' in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id in CODE_ARGS):
                continue
            index = CODE_ARGS[node.func.id]
            if len(node.args) <= index or not isinstance(node.args[index], ast.Constant) \
                    or not isinstance(node.args[index].value, str):
                continue
            codes.setdefault(node.args[index].value, []).append('%s:%d' % (path.name, node.lineno))
    return codes


class ErrorTaxonomyTests(unittest.TestCase):
    def test_the_three_sets_are_pairwise_disjoint(self):
        self.assertFalse(CONTROLLER_ERRORS & CONTENT_ERRORS)
        self.assertFalse(CONTROLLER_ERRORS & TECHNICAL_ERRORS)
        self.assertFalse(CONTENT_ERRORS & TECHNICAL_ERRORS)

    def test_every_raised_code_is_classified_exactly_once(self):
        classified = CONTENT_ERRORS | CONTROLLER_ERRORS | TECHNICAL_ERRORS
        unclassified = {code: sites for code, sites in raised_codes().items()
                        if code not in classified}
        self.assertEqual(
            unclassified, {},
            '每个新错误码都必须显式归入 CONTENT_ERRORS / CONTROLLER_ERRORS / TECHNICAL_ERRORS 之一，'
            '分类决定它走数据通道还是技术核算：' + str(unclassified))

    def test_content_codes_stay_out_of_the_controller_routes(self):
        # Recovery routing reads CONTROLLER_ERRORS; a content code there would hand every preview
        # defect to the controller instead of answering it as data.
        from novel_ledger.contracts import RECOVERY_ROUTES
        self.assertFalse(set(RECOVERY_ROUTES) & CONTENT_ERRORS)


if __name__ == '__main__':
    unittest.main()
