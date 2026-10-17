"""Mechanical prose defects the engine rejects itself, before any reviewer is paid.

Three defect classes each cost a real run a repair round plus a full independent re-review when
only the reviewer found them: a chapter that reused an earlier chapter's action group verbatim,
a chapter whose dialogue quotes used the other quote family, and a leftover foreign word. These
tests pin the mechanical judgements and their routing, including that preflight shows the same
finding without committing.
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from novel_ledger import lint, workflow
from novel_ledger.bootstrap import local_application as Application
from novel_ledger.sqlite_store import SQLiteRepository
from support import contract, drive, response


class LintUnitTests(unittest.TestCase):
    def test_verbatim_reuse_of_a_prior_chapter_is_found_with_the_shared_span(self):
        reused = '沈桐把退回的箱子放在桌上，指给主管看封条上的签字。'
        first = '第一章开头各不相同。' + reused + '第一章结尾各不相同。'
        second = '完全另起的第二章。' + reused + '又是不同的结尾。'
        findings = lint.cross_chapter_duplicates(second, [(1, first)], 2)
        self.assertEqual(len(findings), 1)
        self.assertEqual((findings[0]['criterion'], findings[0]['severity'],
                          findings[0]['repair_scope']), ('repetition', 'quality', 'local'))
        self.assertEqual(findings[0]['duplicate_of'], 1)
        self.assertIn(reused, findings[0]['quote'])

    def test_a_short_shared_window_is_not_copying(self):
        shared = '他把责任栏推到主管面前，要求先核对名字再开箱。'[:24]
        # The delimiters share no boundary character with each other, so the longest common
        # run stays exactly the 24-character window under the copy threshold.
        first = '甲甲' + shared + '末甲'
        second = '乙乙' + shared + '末乙'
        self.assertEqual(lint.cross_chapter_duplicates(second, [(1, first)], 2), [])

    def test_quote_family_switch_against_the_book_is_flagged(self):
        priors = [(1, '「昨夜的话算数。」他说完便走。「不留字据。」「不认口头。」')]
        switched = '他说"先核对。"又写"编号在此。"末了补一句"谁也不欠账。"'
        findings = lint.style_findings(switched, priors, 2)
        self.assertEqual([row['criterion'] for row in findings], ['language'])
        self.assertIn('统一', findings[0]['reason'])

    def test_mixing_both_quote_families_inside_one_chapter_is_flagged(self):
        mixed = '「昨夜的话算数。」他说完便走，回头又补了「不留字据。」和「不认口头。」随后另起一句"不欠账"，再说"两清了"。'
        self.assertEqual([row['criterion'] for row in lint.style_findings(mixed, [], 2)], ['language'])

    def test_few_quotes_never_establish_a_family(self):
        self.assertEqual(lint.style_findings('他只说了一句"好"。', [(1, '「昨夜的话算数。」他走了。')], 2), [])

    def test_foreign_residue_is_flagged_with_the_run(self):
        prose = '他把单子递过去，说签了字， bell 就归你敲了，别的事一概不问。'
        findings = lint.latin_findings(prose, 3)
        self.assertEqual([row['criterion'] for row in findings], ['language'])
        self.assertEqual(findings[0]['matches'], ['bell'])

    def test_the_author_may_allowlist_specific_latin_terms(self):
        prose = 'CT 报告放在最上层，他只核对了编号。'
        self.assertEqual(lint.latin_findings(prose, 3, allowed=('CT',)), [])


class LintFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / 'book'
        self.repo = SQLiteRepository.initialize(self.project, workflow.new_book(contract()))
        self.app = Application(self.repo)

    def tearDown(self):
        self.repo.close()
        self.temp.cleanup()

    def committed(self):
        return {row['n']: self.repo.read_document(row['prose']) for row in self.repo.headers('main')}

    def first_chapter_is_committed(self):
        drive(self.app, until='write')
        self.app.submit(response(self.app))
        drive(self.app, until='chapter_review')
        self.app.submit(response(self.app))
        handoff = self.app.advance()
        self.assertEqual(handoff['action'], 'await_author')
        self.app.approve(handoff['prose_hash'], '工程夹具认可第一章。')
        run = self.app.run(through=2, source='工程夹具授权写到第二章。')
        return run['owner']

    def test_a_chapter_reusing_a_committed_span_is_routed_to_repair(self):
        owner = self.first_chapter_is_committed()
        drive(self.app, owner=owner, until='write')
        first = self.committed()[1]
        result = response(self.app)
        result['data']['prose'] = '第二章重起炉灶，另立一案。' + first
        # Preflight runs the same judgement in preview: the producer sees it before committing.
        preview = self.app.submit({**result}, preview=True)
        self.assertFalse(preview['committed'])
        self.assertEqual(preview['next_stage'], 'repair')
        outcome = self.app.submit(result)
        self.assertTrue(outcome['committed'])
        self.assertEqual(outcome['next_stage'], 'repair')
        findings = self.repo.load()['draft']['findings']
        self.assertIn('repetition', [row['criterion'] for row in findings])
        # The repair dispatch carries the finding as an obligation, and a clean rewrite passes.
        task = self.app.advance(owner=owner)['task']
        self.assertEqual(task['stage'], 'repair')
        repaired = response(self.app)
        self.assertNotIn(first[:30], repaired['data']['prose'])
        outcome = self.app.submit(repaired)
        self.assertEqual(outcome['next_stage'], 'chapter_review')

    def test_foreign_residue_routes_the_writer_back_before_any_review(self):
        owner = self.first_chapter_is_committed()
        drive(self.app, owner=owner, until='write')
        result = response(self.app)
        result['data']['prose'] = result['data']['prose'].replace('要求先核对', '要求先 check 再核对')
        outcome = self.app.submit(result)
        self.assertEqual(outcome['next_stage'], 'repair')
        findings = self.repo.load()['draft']['findings']
        self.assertIn('language', [row['criterion'] for row in findings])
        self.assertTrue(any(row.get('matches') == ['check'] for row in findings))


if __name__ == '__main__':
    unittest.main()
