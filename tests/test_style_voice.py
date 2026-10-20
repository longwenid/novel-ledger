"""Regression cases where a mechanical proxy mistook ordinary prose for a voice defect.

These cases check parsing and declared policy, rather than assigning literary quality scores.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from novel_ledger import lint, style
from test_style import paragraphs, sentences


class QuotationMetricsTests(unittest.TestCase):
    def test_dialogue_is_measured_in_reading_order_across_quote_families(self):
        corner_first = '「我先走。」他说。“你等会。”她喊。'
        western_first = '“你等会。”她喊。「我先走。」他说。'
        for prose in (corner_first, western_first):
            with self.subTest(prose=prose):
                measured = style.metrics(prose)
                self.assertEqual(measured['dialogue_share'], 0.6)
                self.assertEqual(measured['person'], 'third')

    def test_straight_quotes_count_as_dialogue_and_hide_character_person_marks(self):
        measured = style.metrics('"我先走。"他说。')
        self.assertEqual(measured['dialogue_share'], 0.6)
        self.assertEqual(measured['person'], 'third')

    def test_nested_quotations_are_not_counted_twice(self):
        measured = style.metrics('“我记得「天亮再走」这句话。”他说。')
        self.assertEqual(measured['dialogue_share'], round(10 / 12, 3))
        self.assertEqual(measured['person'], 'third')

    def test_unfinished_quote_does_not_turn_the_whole_paragraph_into_dialogue(self):
        measured = style.metrics('“我没写完。他把纸收起来。')
        self.assertEqual(measured['dialogue_share'], 0)

    def test_closing_quotes_and_ellipsis_do_not_create_zero_word_sentences(self):
        for prose in ('“你等会。”', '「你等会……」', '"你等会！！"'):
            with self.subTest(prose=prose):
                measured = style.metrics(prose)
                self.assertEqual(measured['sentences'], 1)
                self.assertEqual(measured['sentence_mean'], 3)

    def test_repetition_uses_the_manuscript_order_around_quotations(self):
        # The four characters 甲乙丙丁 recur in reading order across a quote boundary.
        # Sorting narration before dialogue had concealed this recurrence.
        measured = style.metrics('甲乙「丙丁」戊己。庚辛「甲乙」丙丁。')
        self.assertEqual(measured['repetition_grams'], 9)
        self.assertEqual(measured['repetition_share'], 0.1111)


class QuoteFamilyLintTests(unittest.TestCase):
    def test_an_inner_quotation_may_use_the_other_quote_family(self):
        prose = ('“他只说「天亮再走」，我没答应。”'
                 '“那句「天亮再走」也不作数。”'
                 '“你还记得「天亮再走」吗？”')
        self.assertEqual(lint.style_findings(prose, [], 2), [])

    def test_nested_prior_quotations_do_not_invent_a_different_book_convention(self):
        prior = '“他说「再见」，然后「转身」，最后「走了」。”'
        current = '“还等吗？”“不用。”“回去吧。”'
        self.assertEqual(lint.style_findings(current, [(1, prior)], 2), [])

    def test_distinct_top_level_quote_families_remain_a_format_finding(self):
        mixed = '「甲。」「乙。」「丙。」“丁。”“戊。”'
        findings = lint.style_findings(mixed, [], 2)
        self.assertEqual([row['criterion'] for row in findings], ['language'])


class StyleGuardTests(unittest.TestCase):
    def test_default_guard_observes_a_different_chapter_rhythm(self):
        anchor_prose = paragraphs(20, 6)
        chapter = sentences(6, 20, start=0x6000)
        report = style.examine(chapter, {'rhythm': '本章用短句写突发动作'},
                               style.metrics(anchor_prose), style.DEFAULT_WINDOW, chapter=2)
        self.assertEqual(report['metrics'], style.metrics(chapter))
        self.assertEqual(report['findings'], [])
        observed = {row['metric'] for row in report['observations']}
        self.assertIn('sentence_mean', observed)
        self.assertIn('paragraph_mean', observed)
        self.assertTrue(all(row['target_chapter'] == 2 for row in report['observations']))
        self.assertTrue(all('repair_scope' not in row for row in report['observations']))
        self.assertEqual(style.compare(chapter, {}, style.metrics(anchor_prose),
                                       style.DEFAULT_WINDOW), [])

    def test_unplanned_dialogue_share_changes_are_observations_by_default(self):
        anchor = style.metrics(sentences(12, 4) + sentences(12, 4, start=0x6000, quoted=True))
        chapter = sentences(12, 8, start=0x7000, quoted=True)
        observed = style.examine(chapter, {}, anchor, style.DEFAULT_WINDOW)
        self.assertEqual(observed['findings'], [])
        self.assertEqual([row['metric'] for row in observed['observations']], ['dialogue_share'])
        strict = style.examine(chapter, {}, anchor, style.DEFAULT_WINDOW,
                               contract={'style_guard': 'strict'})
        self.assertEqual([row['metric'] for row in strict['findings']], ['dialogue_share'])
        self.assertEqual(strict['observations'], [])

    def test_explicit_dialogue_targets_remain_findings_under_both_guards(self):
        chapter = sentences(12, 8, quoted=True)
        for guard in ('observe', 'strict'):
            with self.subTest(guard=guard):
                report = style.examine(chapter, {'dialogue_ratio': 0}, None,
                                       style.DEFAULT_WINDOW, contract={'style_guard': guard})
                self.assertEqual([(row['metric'], row['expect'], row['got'])
                                  for row in report['findings']], [('dialogue_ratio', 0, 1)])
                self.assertEqual(report['observations'], [])

    def test_high_repetition_remains_a_finding_under_both_guards(self):
        chapter = '他把责任栏推到主管面前，要求先核对名字。' * 8
        for guard in ('observe', 'strict'):
            with self.subTest(guard=guard):
                report = style.examine(chapter, {}, None, style.DEFAULT_WINDOW,
                                       contract={'style_guard': guard})
                self.assertEqual([row['metric'] for row in report['findings']], ['repetition'])

    def test_first_person_observation_and_third_person_interior_are_not_viewpoint_errors(self):
        samples = (
            ('第一人称', '我把书包挪到膝上，他还占着窗口。我等他开口，他却伸手关了灯。'
             '我没追问，他也没再看我。楼道里响了一阵脚步，门缝透进来一点亮光。'),
            ('第三人称限知', '她低头，想这回我总算没有白来。门外的人还在争执，她把信压回袖口，'
             '脸上没有半点变化。楼道里响了一阵脚步，门缝透进来一点亮光。'),
        )
        for guard in ('observe', 'strict'):
            for pov, chapter in samples:
                with self.subTest(guard=guard, pov=pov):
                    report = style.examine(chapter, {'pov': pov}, None, style.DEFAULT_WINDOW,
                                           contract={'style_guard': guard})
                    self.assertGreaterEqual(report['metrics']['han'], style.MIN_HAN)
                    self.assertEqual(report['metrics']['person'], 'mixed')
                    self.assertEqual(report['findings'], [])
                    self.assertEqual([row['metric'] for row in report['observations']], ['person'])

    def test_below_the_floor_metrics_are_available_without_verdicts(self):
        report = style.examine('他走了。', {'pov': '第一人称'}, None, style.DEFAULT_WINDOW)
        self.assertEqual(report['metrics']['han'], 3)
        self.assertEqual(report['findings'], [])
        self.assertEqual(report['observations'], [])


if __name__ == '__main__':
    unittest.main()
