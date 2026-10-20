"""Opening option bounds apply to every dispatch; there is no lenient legacy shape any more."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from novel_ledger import creation
from novel_ledger.contracts import Error
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


if __name__ == '__main__':
    unittest.main()
