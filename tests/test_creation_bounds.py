"""Opening bounds apply to new dispatches without rejecting frozen legacy options."""
import copy
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from novel_ledger import creation, planning, workflow
from novel_ledger.bootstrap import local_application as Application
from novel_ledger.contracts import Error
from novel_ledger.sqlite_store import SQLiteRepository
from support import contract


def options(version=2, pitch_length=40, scene_count=3):
    result = []
    for index, driver in enumerate(('从送货单追查联系人。', '让主角被调离旧岗位。')):
        value = {'genre': '职场悬疑', 'reader_promise': '查清退件责任。'}
        value.update({'tone': '克制而紧张。'} if version == 2 else
                     {'red_lines': [], 'allow_special_mechanism': False})
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

    def test_exact_new_bounds_are_accepted_without_mutating_the_receipt(self):
        data = options()
        original = copy.deepcopy(data)
        state = creation.offer(creation.begin(), data)
        self.assertEqual(state['board']['options'], original['options'])
        self.assertEqual(data, original)

    def test_new_pitch_and_scene_upper_bounds_reject_oversized_options(self):
        self.assertCode('opening_option', creation.offer, creation.begin(), options(pitch_length=41))
        self.assertCode('opening_scene', creation.offer, creation.begin(), options(scene_count=4))

    def test_old_frozen_tasks_keep_their_original_bounds_in_both_gate_protocols(self):
        for version in (1, 2):
            with self.subTest(version=version):
                book = workflow.preparing_book(guided=True, opening_version=version)
                work = {'stage': 'opening_options', 'chapter': 0, 'capabilities': {}}
                data = options(version, pitch_length=69, scene_count=4)
                accepted = workflow.apply(book, work, data, 'legacy-worker', {})
                self.assertEqual(accepted.book['creation']['board']['options'], data['options'])
                strict = {**work, 'capabilities': {'opening_bounds': 'opening-bounds/1'}}
                self.assertCode('opening_option', workflow.apply, book, strict, data, 'new-worker', {})

    def test_already_accepted_legacy_board_can_still_be_selected(self):
        for version in (1, 2):
            with self.subTest(version=version):
                state = creation.offer(creation.begin(version=version),
                                       options(version, pitch_length=69, scene_count=4), strict_bounds=False)
                advanced = creation.pick(state, '0', state['board']['hash'], '作者选择方案零。')
                selected = advanced['selections'][0]['option']
                self.assertEqual(len(selected['pitch']), 69)
                self.assertEqual(len(selected['scene']), 4)
                self.assertEqual(advanced['cursor'], 1)

    def test_new_dispatch_freezes_bounds_capability(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = SQLiteRepository.initialize(Path(temporary) / 'book', workflow.preparing_book(guided=True))
            try:
                app = Application(repo)
                self.assertEqual(app.advance()['task']['stage'], 'opening_options')
                self.assertEqual(repo.pending()['input']['capabilities']['opening_bounds'], 'opening-bounds/1')
            finally:
                repo.close()

    def test_a_contract_written_before_opening_five_still_loads_without_its_rows(self):
        """The v5 structural rows are optional: an old contract has neither and must not be refused."""
        legacy = contract(v5_rows=False)
        self.assertNotIn('world_tiers', legacy)
        self.assertNotIn('world_ladder', legacy)
        checked = planning.validate_contract(copy.deepcopy(legacy))
        self.assertNotIn('world_tiers', checked)
        book = workflow.new_book(legacy)
        self.assertIn('volumes', book['contract'])
        self.assertNotIn('world_tiers', book['contract'])
        self.assertNotIn('world_ladder', book['contract'])

    def test_the_v5_rows_accept_exactly_their_declared_fields(self):
        """A hand-written v5 contract states one rung and one ladder level, key set exact."""
        checked = planning.validate_contract(contract(v5_rows=True))
        self.assertEqual(len(checked['world_tiers']), 1)
        self.assertEqual(len(checked['world_ladder']), 1)
        extra = contract(v5_rows=True)
        extra['world_tiers'][0]['unexpected'] = '越界字段。'
        self.assertCode('contract', planning.validate_contract, extra)
        missing = contract(v5_rows=True)
        del missing['world_ladder'][0]['cost']
        self.assertCode('contract', planning.validate_contract, missing)
        empty = contract(v5_rows=True)
        empty['world_tiers'] = []
        self.assertCode('contract', planning.validate_contract, empty)


if __name__ == '__main__':
    unittest.main()
