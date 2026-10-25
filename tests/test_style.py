"""Mechanical style proxies measure declared numeric limits without judging literary quality.

Anchor-shape bounds below use an explicit strict contract. The default observation guard and
ordinary prose that mixes pronouns are covered separately in test_style_voice.py.

Every case here is calibration, not appreciation. The samples are constructed to have exact,
predictable shapes — each sentence of a known 汉字 length, built from code points used nowhere else
in the sample — so `repetition_share` stays at its floor and the length arithmetic does not depend on
anything but the declared length. The tolerance boundary is tested as seriously as the violations: a
proxy that fires on normal variation would push a writer into flattening its voice.
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from novel_ledger import style
from novel_ledger.bootstrap import local_application as Application
from novel_ledger.sqlite_store import SQLiteRepository
from novel_ledger.result_templates import chapter_row
from support import contract, drive, response, seeded_book

# The engine's own default (spec §2.1), read from the module so a re-calibration is a visible change
# in the engine rather than something the tests keep asserting on their own. `repetition` is
# calibrated, not guessed: ordinary Chinese prose in this repository measures 0.04~0.09, a repeated
# template 0.79~0.99.
WINDOW = dict(style.DEFAULT_WINDOW)
STRICT = {'style_guard': 'strict'}
METRIC_KEYS = ('sentence_mean', 'sentence_short_share', 'paragraph_mean', 'paragraph_max',
               'dialogue_share', 'repetition_share', 'person')
THIRD_POV = '第三人称限知'


def sentences(length, count, start=0x4e00, quoted=False, marker='他'):
    """`count` sentences of exactly `length` 汉字, no character reused anywhere in the sample.

    Distinct code points keep `repetition_share` at its floor, so a case that means to test the
    length proxies cannot pass or fail because of the repetition one. `marker` is the narration
    person marker, so the same helper serves the person cases.
    """
    rows = []
    for index in range(count):
        body = marker + ''.join(chr(start + index * length + offset) for offset in range(length - 1))
        rows.append(('「%s」' % body) if quoted else body)
    return '。'.join(rows) + '。'


def paragraphs(length, count, start=0x4e00, per_paragraph=1, marker='他'):
    """`count` paragraphs (blank-line separated), each holding `per_paragraph` sentences."""
    blocks = [sentences(length, per_paragraph, start + index * length * per_paragraph, marker=marker)
              for index in range(count)]
    return '\n\n'.join(blocks)


def metrics_of(text):
    return style.metrics(text)


def repeated_sentences(copies, count=20, length=10):
    """`count` distinct sentences with the first one echoed `copies` more times.

    Ordinary prose echoes a beat now and then; this is the shape the repetition cap has to tolerate,
    built from the same generator as the clean samples so only the echo differs.
    """
    base = sentences(length, count)
    return base + (base.split('。')[0] + '。') * copies


def by_metric(findings, prefix):
    return [row for row in findings if str(row.get('metric') or '').startswith(prefix)]


class MetricsTests(unittest.TestCase):
    def test_sentence_length_and_short_share_are_measured_with_a_pinned_threshold(self):
        short, long = metrics_of(sentences(4, 10)), metrics_of(sentences(30, 10))
        self.assertLess(short['sentence_mean'], 8)
        self.assertGreater(long['sentence_mean'], 25)
        self.assertGreater(short['sentence_short_share'], 0.8)
        self.assertLess(long['sentence_short_share'], 0.2)
        # Ten 汉字 counts as short and eleven does not: the threshold is a decision, not a drift.
        self.assertEqual(metrics_of(sentences(10, 6))['sentence_short_share'], 1.0)
        self.assertEqual(metrics_of(sentences(11, 6))['sentence_short_share'], 0.0)
        mixed = metrics_of(sentences(4, 6) + sentences(40, 4, start=0x6000))
        self.assertEqual(mixed['sentences'], 10)
        self.assertAlmostEqual(mixed['sentence_short_share'], 0.6, places=2)
        self.assertAlmostEqual(mixed['sentence_mean'], 18.4, places=1)

    def test_sentence_splitting_follows_terminators_and_not_newlines(self):
        asked = metrics_of('他走了！他坐下？他抬头。')
        self.assertEqual(asked['sentences'], 3)
        self.assertEqual(asked['sentence_mean'], 3)
        # A newline starts a paragraph, never a sentence: the two lines are one paragraph each.
        lines = metrics_of('他走了\n他坐下')
        self.assertEqual(lines['sentences'], 2)
        self.assertEqual(lines['paragraph_mean'], 3)

    def test_paragraph_mean_and_max_follow_the_paragraphs(self):
        even = metrics_of(paragraphs(10, 5, per_paragraph=2))
        uneven = metrics_of(sentences(8, 1) + '\n\n' + sentences(8, 1, start=0x5000)
                            + '\n\n' + sentences(8, 12, start=0x5800))
        self.assertEqual(even['paragraph_mean'], 20)
        self.assertEqual(even['paragraph_max'], 20)
        self.assertEqual(uneven['paragraph_max'], 96)
        self.assertGreater(uneven['paragraph_mean'], 20)
        self.assertLess(uneven['paragraph_mean'], uneven['paragraph_max'])

    def test_dialogue_share_counts_quoted_text(self):
        spoken = metrics_of(sentences(5, 8, quoted=True))
        silent = metrics_of(sentences(5, 8))
        mixed = metrics_of(sentences(5, 4, quoted=True) + sentences(5, 4, start=0x6000))
        self.assertEqual(spoken['dialogue_share'], 1.0)
        self.assertEqual(silent['dialogue_share'], 0.0)
        self.assertAlmostEqual(mixed['dialogue_share'], 0.5, places=2)

    def test_repetition_share_rises_with_real_repetition_and_stays_quiet_below_the_ngram_floor(self):
        repeated = metrics_of('他把责任栏推到主管面前，要求先核对名字。' * 8)
        varied = metrics_of(sentences(12, 8))
        self.assertGreater(repeated['repetition_share'], 0.5)
        self.assertEqual(varied['repetition_share'], 0.0)
        # Too few four-grams to mean anything: the value stays finite and `compare` skips it.
        thin = metrics_of(sentences(4, 3))
        self.assertEqual(thin['repetition_share'], 0.0)
        self.assertLess(thin['repetition_grams'], style.MIN_NGRAMS)
        self.assertGreaterEqual(metrics_of(sentences(4, 8))['repetition_grams'], style.MIN_NGRAMS)

    def test_person_marks_first_third_mixed_and_unknown(self):
        self.assertEqual(metrics_of('我走进值班室。我翻开登记册。我核对了名字。')['person'], 'first')
        self.assertEqual(metrics_of('他走进值班室。他翻开登记册。他核对了名字。')['person'], 'third')
        self.assertEqual(metrics_of('我走进值班室，他抬头看我。我核对名字，他把封条推过来。')['person'], 'mixed')
        self.assertEqual(metrics_of('箱子放在桌上。登记册翻到那一页。')['person'], 'unknown')
        # A first-person line spoken by a character says nothing about the narration's person.
        self.assertEqual(metrics_of('「我走了。」他说完便走。「我不留字据。」')['person'], 'third')

    def test_every_declared_metric_is_present_finite_and_empty_prose_is_zero(self):
        empty = metrics_of('')
        for key in METRIC_KEYS[:-1]:
            self.assertEqual(empty[key], 0, key)
        self.assertEqual(empty['repetition_grams'], 0)
        self.assertEqual(empty['person'], 'unknown')
        for sample in (sentences(4, 6), '他走了。', '「一句话。」'):
            with self.subTest(sample=sample[:8]):
                value = metrics_of(sample)
                for key in METRIC_KEYS:
                    self.assertIn(key, value)
                for key in METRIC_KEYS[:-1]:
                    self.assertIsInstance(value[key], (int, float), key)
                    self.assertGreaterEqual(value[key], 0, key)
                self.assertIsInstance(value['repetition_grams'], int)


class WindowTests(unittest.TestCase):
    def test_window_reading_takes_known_non_negative_fields_and_fills_the_defaults(self):
        self.assertEqual(style.window_of({}), style.DEFAULT_WINDOW)
        window = style.window_of({'style_window': {'sentence': 0.5, 'repetition': -1, 'bogus': 2}})
        self.assertEqual(window['sentence'], 0.5)
        self.assertEqual(window['repetition'], style.DEFAULT_WINDOW['repetition'])
        self.assertNotIn('bogus', window)

    def test_a_volume_may_override_one_tolerance_on_top_of_the_contract(self):
        merged = style.merged_window({'style_window': {'dialogue': 0.4}},
                                     {'window': {'dialogue': 0.5, 'unknown': 0.1}})
        self.assertEqual(merged['dialogue'], 0.5)
        self.assertEqual(merged['sentence'], style.DEFAULT_WINDOW['sentence'])

    def test_compare_fills_a_default_for_a_window_that_omits_a_family(self):
        anchor = metrics_of(sentences(30, 8))
        dragged = sentences(6, 20, start=0x6000)
        narrow = {'repetition': 0.04, 'dialogue': 0.4, 'person': 1, 'paragraph': 5, 'sentence': 0.35}
        self.assertTrue(by_metric(style.compare(dragged, {}, anchor, narrow, chapter=1,
                                                contract=STRICT), 'sentence'))
        # A window that states nothing but repetition still applies the default sentence tolerance.
        self.assertTrue(by_metric(style.compare(dragged, {}, anchor, {'repetition': 0.04}, chapter=1,
                                                contract=STRICT),
                                  'sentence'))

    def test_shape_is_only_compared_between_samples_of_the_same_order(self):
        """A short anchor cannot dictate a full chapter's rhythm, and vice versa."""
        short_anchor = metrics_of(sentences(10, 6))                      # 60 汉字
        long_chapter = sentences(20, 100, start=0x6000)                  # 2000 汉字
        self.assertGreater(metrics_of(long_chapter)['han'], 3 * short_anchor['han'])
        self.assertEqual(style.compare(long_chapter, {}, short_anchor, WINDOW, chapter=1,
                                       contract=STRICT), [])
        # Within 3x the shapes are comparable again, and a real deviation is reported.
        comparable = sentences(20, 6, start=0x6000)                      # 120 汉字
        self.assertTrue(by_metric(style.compare(comparable, {}, short_anchor, WINDOW, chapter=1,
                                                contract=STRICT),
                                  'sentence'))


class BaselineTests(unittest.TestCase):
    def test_an_approved_pilot_is_the_anchor(self):
        sample = sentences(12, 6)                       # long enough to be a baseline
        book = {'style_anchor': {'prose_hash': 'h', 'sample': sample, 'source': '作者认可。'}}
        self.assertEqual(style.baseline(book), style.metrics(sample))

    def test_a_missing_or_short_anchor_falls_back_to_the_default_profile(self):
        """A project never runs voiceless: no anchor means the declared default floor."""
        from novel_ledger.contracts import profile_anchor
        default = profile_anchor()
        for book in ({'style_anchor': {'sample': '他走了。'}}, {}, {'style_anchor': None},
                     {'style_anchor': {'sample': ''}}):
            baseline = style.baseline(book)
            self.assertEqual(baseline, default)
            self.assertEqual(baseline['origin'], 'default')
            for key in ('han', 'sentences', 'sentence_mean', 'sentence_short_share',
                        'paragraph_mean', 'paragraph_max', 'dialogue_share'):
                self.assertGreater(baseline[key], 0, key)


class CompareTests(unittest.TestCase):
    """Strict shape bounds, explicit targets and nonbinding person observations stay separate."""

    def test_reporting_rows_carry_the_finding_shape(self):
        findings = style.compare('他把责任栏推到主管面前，要求先核对名字。' * 8, {}, None, WINDOW, chapter=2)
        self.assertEqual(len(findings), 1)
        row = findings[0]
        self.assertEqual(row['criterion'], 'style_repetition')
        self.assertEqual(row['metric'], 'repetition')
        self.assertEqual((row['severity'], row['repair_scope']), ('quality', 'local'))
        self.assertEqual(row['target_chapter'], 2)
        self.assertTrue(row['reason'])
        self.assertEqual(row['expect'], WINDOW['repetition'])
        self.assertGreater(row['got'], WINDOW['repetition'])

    def test_anchor_tolerances_report_their_own_metric_family(self):
        """Sentence, paragraph and dialogue drift each raise their own metric, not a neighbour's."""
        sentence = style.compare(sentences(6, 20, start=0x6000), {},
                                 metrics_of(sentences(30, 8)), WINDOW, chapter=3, contract=STRICT)
        self.assertTrue(by_metric(sentence, 'sentence'), sentence)
        for row in by_metric(sentence, 'sentence'):
            self.assertEqual(row['target_chapter'], 3)
            self.assertEqual(row['criterion'], 'style_' + row['metric'])
        paragraph_anchor = metrics_of(paragraphs(10, 6, per_paragraph=1))
        blocked = sentences(10, 6, start=0x5000)        # one long paragraph instead of six
        paragraph = style.compare(blocked, {}, paragraph_anchor, WINDOW, chapter=1, contract=STRICT)
        self.assertTrue(by_metric(paragraph, 'paragraph'), paragraph)
        self.assertFalse(by_metric(paragraph, 'dialogue'), paragraph)
        self.assertFalse(by_metric(paragraph, 'sentence'), paragraph)
        dialogue_anchor = metrics_of(sentences(12, 4) + sentences(12, 4, start=0x6000, quoted=True))
        talky = sentences(12, 8, start=0x7000, quoted=True)
        dialogue = style.compare(talky, {}, dialogue_anchor, WINDOW, chapter=1, contract=STRICT)
        self.assertTrue(by_metric(dialogue, 'dialogue'), dialogue)
        self.assertEqual(by_metric(dialogue, 'dialogue')[0]['criterion'], 'style_dialogue_share')

    def test_the_declared_dialogue_ratio_is_checked_without_an_anchor(self):
        silent = sentences(12, 8)
        findings = style.compare(silent, {'dialogue_ratio': 0.6}, None, WINDOW, chapter=5)
        self.assertTrue(by_metric(findings, 'dialogue'), findings)
        self.assertEqual(by_metric(findings, 'dialogue')[0]['criterion'], 'style_dialogue_ratio')
        self.assertEqual(findings[0]['target_chapter'], 5)
        # A chapter that hits its declared ratio is not reported, even with no anchor to compare to.
        spoken = sentences(12, 8, start=0x6000, quoted=True)
        self.assertEqual(style.compare(spoken, {'dialogue_ratio': 1.0}, None, WINDOW, chapter=5), [])

    def test_a_zero_dialogue_target_is_distinct_from_an_absent_target(self):
        silent = sentences(12, 8)
        spoken = sentences(12, 8, start=0x6000, quoted=True)
        self.assertEqual(style.compare(silent, {'dialogue_ratio': 0}, None, WINDOW), [])
        findings = style.compare(spoken, {'dialogue_ratio': 0}, None, WINDOW, chapter=5)
        self.assertEqual([(row['metric'], row['expect'], row['got']) for row in findings],
                         [('dialogue_ratio', 0.0, 1.0)])
        self.assertEqual(style.compare(spoken, {}, None, WINDOW), [])
        # An explicit zero takes precedence over a talkative anchor too.
        self.assertEqual(style.compare(silent, {'dialogue_ratio': 0},
                                       metrics_of(spoken), WINDOW), [])
        almost_silent = sentences(12, 500) + '「好」'
        self.assertEqual(metrics_of(almost_silent)['dialogue_share'], 0.0)
        self.assertTrue(by_metric(style.compare(almost_silent, {'dialogue_ratio': 0},
                                                None, WINDOW), 'dialogue'))

    def test_the_blank_chapter_form_does_not_choose_a_dialogue_target(self):
        declared = chapter_row(1)['style']
        declared.update(pov=THIRD_POV, rhythm='短句')
        spoken = sentences(12, 8, start=0x6000, quoted=True)
        self.assertEqual(style.compare(spoken, declared, None, WINDOW), [])

    def test_the_repetition_cap_is_calibrated_above_ordinary_prose(self):
        """0.12 sits above ordinary prose and below a repeated template; the author can tighten it.

        Echoing a beat is a legal device, so the finding names its exit instead of only demanding a
        rewrite: an author who meant the echo widens `style_window.repetition`.
        """
        mild = repeated_sentences(2)                      # two echoes of one sentence, ~0.07
        measured = metrics_of(mild)['repetition_share']
        self.assertGreater(measured, 0.04)
        self.assertLess(measured, style.DEFAULT_WINDOW['repetition'])
        self.assertEqual(style.compare(mild, {}, None, WINDOW, chapter=1), [])
        # An author who wants no echoing at all tightens the window, and then it does fire.
        tight = {**WINDOW, 'repetition': 0.04}
        self.assertTrue(by_metric(style.compare(mild, {}, None, tight, chapter=1), 'repetition'))
        # A chapter that keeps returning to the same sentence is still caught by the default,
        # and ordinary varied prose stays quiet without an anchor.
        heavy = repeated_sentences(8)
        self.assertGreater(metrics_of(heavy)['repetition_share'], style.DEFAULT_WINDOW['repetition'])
        findings = style.compare(heavy, {}, None, WINDOW, chapter=1)
        self.assertTrue(by_metric(findings, 'repetition'), findings)
        self.assertIn('style_window.repetition', findings[0]['reason'])
        self.assertEqual(style.compare(sentences(12, 8), {}, None, WINDOW), [])

    def test_person_markers_are_observations_even_under_strict_guarding(self):
        first = ('我走进值班室。我翻开登记册。我核对了名字。我一直站到天亮。'
                 '我又看了一遍凭据。我记得那天的雪。')
        third = ('他走进值班室。他翻开登记册。他核对了名字。他一直站到天亮。'
                 '他又看了一遍凭据。他记得那天的雪。')
        mixed = ('我走进值班室，他抬头看我。我核对名字，他把封条推过来。'
                 '我一直站到天亮，他先离开了。我写记录，他签字。')
        for guard in ('observe', 'strict'):
            for prose, pov, markers in ((first, THIRD_POV, 'first'),
                                        (third, '第一人称', 'third'),
                                        (mixed, THIRD_POV, 'mixed')):
                with self.subTest(guard=guard, pov=pov, markers=markers):
                    report = style.examine(prose, {'pov': pov}, None, WINDOW, chapter=4,
                                           contract={'style_guard': guard})
                    self.assertFalse(by_metric(report['findings'], 'person'))
                    observed = by_metric(report['observations'], 'person')
                    self.assertEqual([(row['target_chapter'], row['got']) for row in observed],
                                     [(4, markers)])
            report = style.examine(third, {'pov': THIRD_POV}, None, WINDOW,
                                   contract={'style_guard': guard})
            self.assertFalse(by_metric(report['observations'], 'person'))

    def test_the_contract_view_is_read_when_the_chapter_declares_none(self):
        first = ('我走进值班室。我翻开登记册。我核对了名字。我一直站到天亮。'
                 '我又看了一遍凭据。我记得那天的雪。')
        report = style.examine(first, {}, None, WINDOW, chapter=1, contract={'pov': THIRD_POV})
        self.assertFalse(by_metric(report['findings'], 'person'))
        self.assertTrue(by_metric(report['observations'], 'person'), report)
        matching = style.examine(first, {}, None, WINDOW, chapter=1, contract={'pov': '第一人称'})
        self.assertFalse(by_metric(matching['observations'], 'person'))
        overridden = style.examine(first, {'pov': '第一人称'}, None, WINDOW, chapter=1,
                                   contract={'pov': THIRD_POV})
        self.assertFalse(by_metric(overridden['observations'], 'person'))

    def test_an_unknown_person_is_not_treated_as_a_mismatch(self):
        """Narration with no marker at all is not evidence of the wrong view."""
        unmarked = sentences(12, 8, marker='')
        self.assertEqual(metrics_of(unmarked)['person'], 'unknown')
        report = style.examine(unmarked, {'pov': THIRD_POV}, None, WINDOW, chapter=1)
        self.assertFalse(by_metric(report['findings'], 'person'))
        self.assertFalse(by_metric(report['observations'], 'person'))

    def test_degradation_without_an_anchor_or_below_the_floor_is_not_judged(self):
        """No anchor means no baseline and no length verdicts; too short means no verdicts at all."""
        wild = sentences(4, 12, start=0x5000)
        findings = style.compare(wild, {'pov': THIRD_POV}, None, WINDOW, chapter=1)
        self.assertEqual(findings, [])
        short = sentences(4, 5)                          # 20 汉字: below the floor the proxies need
        self.assertLess(metrics_of(short)['han'], style.MIN_HAN)
        self.assertEqual(style.compare(short, {'pov': '第一人称'}, None, WINDOW, chapter=1), [])

    def test_normal_variation_inside_the_tolerance_is_not_reported(self):
        """This is the case that matters: a writer who drifts inside the window must not be stopped.

        The baseline is the anchor's own metrics; the prose moves sentence and paragraph length by
        about ten percent, well inside the declared window of 35%.
        """
        anchor = metrics_of(sentences(20, 10))
        drifted = sentences(22, 10, start=0x6000)
        self.assertAlmostEqual(drifted_sentence_gap(drifted, anchor), 0.1, places=2)
        findings = style.compare(drifted, {'pov': THIRD_POV}, anchor, WINDOW, chapter=1,
                                 contract=STRICT)
        self.assertEqual(findings, [])

    def test_a_wider_contract_window_tolerates_what_the_default_would_not(self):
        anchor = metrics_of(sentences(20, 10))
        shouted = sentences(9, 10, start=0x6000)         # 55% shorter sentences
        self.assertTrue(by_metric(style.compare(shouted, {}, anchor, WINDOW, chapter=1,
                                                contract=STRICT), 'sentence'))
        wide = {**WINDOW, 'sentence': 0.9}
        self.assertFalse(by_metric(style.compare(shouted, {}, anchor, wide, chapter=1,
                                                 contract=STRICT), 'sentence'))

    def test_a_comparison_against_its_own_metrics_is_silent(self):
        prose = sentences(14, 9)
        self.assertEqual(style.compare(prose, {'pov': THIRD_POV}, metrics_of(prose), WINDOW, chapter=1), [])


def drifted_sentence_gap(prose, anchor):
    """How far the sample's sentence mean sits from the anchor, as a relative deviation."""
    return abs(metrics_of(prose)['sentence_mean'] - anchor['sentence_mean']) / anchor['sentence_mean']


class StyleIntegrationTests(unittest.TestCase):
    """The proxies run at submission, in the same bounded repair path as the other findings."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / 'book'
        raw = contract(2)
        raw.update(narrative_tracking=True, editorial_features=True, style_guard='strict')
        self.repo = SQLiteRepository.initialize(self.project, seeded_book(raw))
        self.app = Application(self.repo)
        self.owner = self.app.run(through=2, source='工程夹具：两章。')['owner']

    def tearDown(self):
        self.repo.close()
        self.temp.cleanup()

    def pilot(self):
        """Commit chapter one and approve it: the approved prose becomes the style anchor."""
        drive(self.app, self.owner, until='write')
        self.assertEqual(self.app.submit(response(self.app))['committed_chapter'], 1)
        handoff = self.app.advance(owner=self.owner)
        self.assertEqual(handoff['action'], 'await_author')
        self.app.approve(handoff['prose_hash'], '工程作者认可首章文风。', self.owner)
        anchor = self.repo.load()['style_anchor']
        self.assertEqual(anchor['prose_hash'], handoff['prose_hash'])
        self.assertTrue(anchor['sample'])
        return anchor

    def test_a_style_deviation_goes_to_repair_and_a_matching_rewrite_commits(self):
        self.pilot()
        drive(self.app, self.owner, until='write')
        candidate = response(self.app)
        # Keep the drift evidence quote (the opening of the stub prose) verbatim; rewrite the rest
        # into a voice far from the anchor's: very short sentences, no dialogue at all.
        candidate['data']['prose'] = candidate['data']['prose'][:14] + sentences(4, 12, start=0x7000)
        direct = style.compare(candidate['data']['prose'], {}, style.baseline(self.repo.load()),
                               WINDOW, chapter=2, contract=STRICT)
        self.assertTrue(by_metric(direct, 'sentence'), direct)
        outcome = self.app.submit(candidate)
        self.assertIsNone(outcome['committed_chapter'])
        self.assertEqual(outcome['next_stage'], 'repair')
        findings = self.repo.load()['draft']['findings']
        self.assertTrue(by_metric(findings, 'sentence'), findings)
        # The rewrite that keeps the anchor's voice lands through the ordinary repair path.
        handoff = self.app.advance(owner=self.owner)
        self.assertEqual(handoff['task']['stage'], 'repair')
        repaired = response(self.app)
        self.assertFalse(by_metric(style.compare(repaired['data']['prose'], {},
                                                 style.baseline(self.repo.load()), WINDOW, chapter=2,
                                                 contract=STRICT),
                                   'sentence'))
        self.assertEqual(self.app.submit(repaired)['committed_chapter'], 2)
        self.assertEqual([row['n'] for row in self.repo.headers('main')], [1, 2])

    def test_a_project_without_an_anchor_judges_against_the_default_profile(self):
        """No approved pilot means the declared default floor: observed, never a silent pass.

        The default anchor is compared (origin=default) but the observe guard keeps shape drift
        non-blocking, so chapter one still commits — the floor records, it does not refuse."""
        from novel_ledger.contracts import profile_anchor
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / 'no-anchor'
            repo = SQLiteRepository.initialize(project, seeded_book(contract(2)))
            try:
                app = Application(repo)
                owner = app.run(through=2, source='工程夹具：无锚点。')['owner']
                self.assertEqual(style.baseline(repo.load()), profile_anchor())
                drive(app, owner, until='write')
                candidate = response(app)
                candidate['data']['prose'] = candidate['data']['prose'][:14] + sentences(4, 8, start=0x7000)
                outcome = app.submit(candidate)
                self.assertEqual(outcome['committed_chapter'], 1)
                self.assertEqual([row['n'] for row in repo.headers('main')], [1])
            finally:
                repo.close()

    def test_the_approved_pilot_becomes_the_baseline_the_next_chapter_is_measured_against(self):
        anchor = self.pilot()
        baseline = style.baseline(self.repo.load())
        self.assertEqual(baseline, style.metrics(anchor['sample']))
        drive(self.app, self.owner, until='write')
        task = self.repo.pending()['input']
        self.assertIn('style_anchor', task['required'])


if __name__ == '__main__':
    unittest.main()
