"""Opening option bounds apply to every dispatch; there is no lenient legacy shape any more."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from novel_ledger import creation
from novel_ledger.contracts import Error, SCALE_TIERS
from test_opening import VALUES


def options(pitch_length=40, scene_count=3):
    result = []
    for index, driver in enumerate(('从送货单追查联系人。', '让主角被调离旧岗位。')):
        value = copy.deepcopy(VALUES['genre'])
        if index:
            value['reader_promise'] += '侧重' + str(index) + '。'
        result.append({'id': str(index), 'title': '方案' + str(index),
                       'premise': '具体方向' + str(index), 'driver': driver,
                       'tradeoff': '调查意味着放弃稳定工作。', 'fit_reason': '承接读者承诺。',
                       'pitch': '追' * pitch_length,
                       'scene': ['主角站在办公室门外，手里拿着没有签字的退件单。'] * scene_count,
                       'value': value})
    return {'gate': 'genre', 'options': result}


class CreationBoundsTests(unittest.TestCase):
    def assertCode(self, code, function, *args, **kwargs):
        with self.assertRaises(Error) as caught:
            function(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)

    def test_exact_bounds_are_accepted_without_mutating_the_receipt(self):
        data = options()
        original = copy.deepcopy(data)
        state = creation.offer(creation.begin(), data)
        self.assertEqual(state['board']['options'], original['options'])
        self.assertEqual(data, original)

    def test_pitch_and_scene_upper_bounds_reject_oversized_options(self):
        self.assertCode('opening_option', creation.offer, creation.begin(), options(pitch_length=41))
        self.assertCode('opening_scene', creation.offer, creation.begin(), options(scene_count=4))

    def test_normal_story_words_and_shared_prefix_do_not_trigger_creative_guards(self):
        data = options()
        data['options'][0]['driver'] = '主角沿着石头阶梯寻找丢失的货物。'
        data['options'][1]['driver'] = '主角沿着石头阶梯逃避追兵的围堵。'
        data['options'][0]['premise'] = '合同将两家人绑定在一条商路上。'
        data['options'][1]['premise'] = '人物靠混搭零件修复旧机器和透镜。'
        state = creation.offer(creation.begin(), data)
        self.assertEqual(len(state['board']['options']), 2)
        data['options'][1]['driver'] = data['options'][0]['driver']
        self.assertCode('opening_diversity', creation.offer, creation.begin(), data)

    def test_explicit_method_metatext_is_still_rejected(self):
        data = options()
        data['options'][0]['pitch'] = '通过规则博弈透镜构思这个故事'
        self.assertCode('opening_voice', creation.offer, creation.begin(), data)

    def test_premise_placeholder_markers_do_not_reject_normal_words(self):
        value = copy.deepcopy(VALUES['premise'])
        value['novelty'] = '主角不再忽略低价订单，从中找到被同行忽视的机会。'
        value['first_cause'] = '双方暂定交易价格，持续竞争改变了附近商户的处境。'
        self.assertIsNone(creation.validate_value('premise', value))
        for marker in ('待补', '暂定', '同上', '略'):
            with self.subTest(marker=marker):
                incomplete = copy.deepcopy(value)
                incomplete['novelty'] = '主角寻找被同行忽视的机会，具体规则（%s）。' % marker
                self.assertCode('opening_option', creation.validate_value, 'premise', incomplete)

    def test_scale_card_explains_how_its_estimates_fit_together(self):
        for tier in SCALE_TIERS:
            with self.subTest(tier=tier['id']):
                option = creation._tier_option(tier, None)
                count = tier['chapters']
                low, high = tier['word_range']
                lower = max(tier['chapter_min'], (low + count - 1) // count)
                upper = min(tier['chapter_max'], high // count)
                target = tier['chapter_aim']
                first = max(tier['chapter_window'][0], (low + target - 1) // target)
                last = min(tier['chapter_window'][1], high // target)
                self.assertLessEqual(lower, upper)
                self.assertLessEqual(first, last)
                self.assertIn('平均每章约 %d～%d 字' % (lower, upper), option['premise'])
                self.assertIn('约需 %d～%d 章' % (first, last), option['premise'])
                self.assertEqual(option['value']['chapters'], count)


if __name__ == '__main__':
    unittest.main()
