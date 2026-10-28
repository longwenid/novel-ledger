"""The engine renders the author-facing board card; the controller stops re-typesetting JSON.

A live opening run paid for this twice per gate: advance's UTF-8 stdout garbles on a GBK console,
so the controller redirected it to a file and then hand-wrote a markdown card (work/opp_board.md,
world_board.md, payoff_board.md — all hand-made) for the author to read. The card is the engine's
own derived view now: work/board.md is materialized on every await_choice, and the controller
hands its content over verbatim.
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'tests'))

from novel_ledger import bookpage, creation, delivery, workflow
from novel_ledger.bootstrap import local_application as Application
from novel_ledger.sqlite_store import SQLiteRepository
from test_opening import rows_for, shown, walk_to
from test_opening_inline import gate_result


class BoardCardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / 'book'
        self.repo = SQLiteRepository.initialize(self.project, workflow.preparing_book(guided=True))
        self.app = Application(self.repo)

    def tearDown(self):
        self.repo.close()
        self.temp.cleanup()

    def test_the_card_carries_author_choices_without_internal_command_metadata(self):
        state = self.app.repo.load()['creation']
        offered = shown(state)
        card = delivery.render_board_card(offered['board'])
        self.assertIn('第 %d/%d 门' % (creation.current(state)['number'],
                                      len(creation.gates(state))), card)
        self.assertNotIn(offered['board']['hash'], card)
        for option in offered['board']['options']:
            self.assertIn(option['title'], card)
            self.assertIn(option['pitch'], card)
        self.assertIn('换一组', card)

    def test_advance_materializes_the_card_exactly_when_a_board_is_on_display(self):
        self.app.advance()
        self.app.submit(gate_result(self.app, 'controller-main'))
        handoff = self.app.advance()
        self.assertEqual(handoff['action'], 'await_choice')
        self.assertTrue(handoff.get('board_card', '').endswith('board.md'))
        card = Path(handoff['board_card']).read_text(encoding='utf-8')
        self.assertNotIn(handoff['board']['hash'], card)
        self.assertNotIn('choose --option', card)
        # The file is a rebuilt view on the current board only: after the choice it is gone.
        chosen = handoff['board']['options'][0]
        self.app.opening_choice(chosen['id'], handoff['board']['hash'], '作者选它。')
        handoff = self.app.advance()
        self.assertEqual(handoff['action'], 'task_ready')
        self.assertTrue((self.project / 'work' / 'board.md').exists())   # latest board stands
        self.assertIsNone(handoff.get('board_card'))

    def test_name_warnings_surface_on_the_card(self):
        state = walk_to(self.app.repo.load()['creation'], 'protagonist')
        rows = rows_for('protagonist')
        rows[0]['value'] = {**rows[0]['value'], 'name': '沈砚'}
        offered = creation.offer(state, {'gate': 'protagonist', 'options': rows})
        card = delivery.render_board_card(offered['board'])
        self.assertIn('命名提示', card)
        self.assertIn('沈砚', card)

    def test_premise_card_displays_world_decisions_that_selection_will_bind(self):
        state = walk_to(self.app.repo.load()['creation'], 'premise')
        board = shown(state)['board']
        card = delivery.render_board_card(board)
        for option in board['options']:
            for field in ('novelty', 'first_cause', 'stance', 'dark_side'):
                self.assertIn(option['value'][field], card)

    def test_perspective_views_show_the_choice_without_a_second_style_picker(self):
        state = walk_to(self.app.repo.load()['creation'], 'voice')
        offered = shown(state)
        board = offered['board']
        card = delivery.render_board_card(board)
        question = delivery.render_question(board)['questions'][0]
        self.assertEqual(question['question'], '写作视角：这本书怎样安排人物视角？')
        self.assertIn('**试读**', card)
        self.assertIn('**取舍**', card)
        for option, shown_option in zip(board['options'], question['options']):
            self.assertIn(option['title'], shown_option['label'])
            for field in ('pitch', 'premise', 'driver', 'tradeoff', 'fit_reason'):
                self.assertIn(option[field], card)
            for scene in option['scene']:
                self.assertIn(scene, card)
        picked = creation.pick(offered, board['options'][0]['id'], board['hash'], '跟着主角看。')
        page = bookpage._world({'creation': picked})
        self.assertIn('<th>跟着谁看</th>', page)
        self.assertIn('<th>补充约定</th>', page)
        self.assertNotIn('<th>文风</th>', page)
        self.assertNotIn('<th>文风要点</th>', page)
        # Existing expression preferences stay intact even though the UI is simpler.
        self.assertEqual(creation.selected(picked)['voice'], board['options'][0]['value'])


if __name__ == '__main__':
    unittest.main()
