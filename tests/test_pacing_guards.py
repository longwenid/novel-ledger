"""The pacing guards added after the 2026-10-27 process validation run.

Each guard answers a finding that run recorded with evidence: the ch25/ch27 boundary
duplication (V1 — one event narrated by both volumes' boundary texts), the hollow mid-volume
shapes (V9/V11 — turns clustered at both ends, hook windows pinned to the ends), the
verbatim-repeated synopsis clause written to clear the length floor (V10), the two-level
entity-reference disagreement (V2/V29 — volume rows refused ids the contract had registered),
and the structural regroup that retired a board without refreshing work/board.md (V16).
"""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'tests'))

from novel_ledger import drift_validation, workflow
from novel_ledger.bootstrap import local_application as Application
from novel_ledger.contracts import Error
from novel_ledger.sqlite_store import SQLiteRepository
from support import (SYNOPSIS_SENTENCE, _fit_text, chapter_rows, contract, drive,
                     response, seeded_book, volume_outline_fixture, volume_rows)
from test_opening_inline import gate_result


def codes(warnings):
    return {row['code'] for row in warnings}


class StructureWarningTests(unittest.TestCase):
    """The board advisories are pure functions of the staged design — no application needed."""

    def staged(self, volumes, chapters=None):
        return {'volume_ids': list(volumes), 'volumes': volumes, 'chapters': chapters or {}}

    def test_adjacent_boundary_texts_sharing_a_fragment_warn(self):
        shared = '秦姨从他烧掉的旧物里抢出半本老登记簿'
        pending = self.staged({
            'v1': {'id': 'v1', 'arc': shared + '，卷一收在铁盒上。', 'climax': '卷一高潮在公开盯表。',
                   'turns': [], 'hooks': []},
            'v2': {'id': 'v2', 'arc': '周电长连夜烧旧物，' + shared + '。', 'turns': [], 'hooks': []}})
        warnings = workflow.structure_warnings(pending, None, {'v1': [1, 30], 'v2': [31, 60]})
        self.assertIn('volume_boundary_overlap', codes(warnings))
        overlap = next(row for row in warnings if row['code'] == 'volume_boundary_overlap')
        self.assertEqual(overlap['volumes'], ['v1', 'v2'])
        self.assertIn('秦姨从他烧掉的旧物', overlap['message'])

    def test_distinct_boundary_texts_stay_quiet(self):
        pending = self.staged({
            'v1': {'id': 'v1', 'arc': '巷口台区从末档电表写到自治。', 'climax': '公开盯表。',
                   'turns': [], 'hooks': []},
            'v2': {'id': 'v2', 'arc': '自治台区挂牌后的新对手与新协议。', 'turns': [], 'hooks': []}})
        self.assertNotIn('volume_boundary_overlap',
                         codes(workflow.structure_warnings(pending, None, {'v1': [1, 30], 'v2': [31, 60]})))

    def test_the_previous_volume_edge_texts_join_the_comparison(self):
        previous = {'id': 'v1', 'arc': '常亮把簿子收进铁盒。', 'climax': '公开盯表。',
                    'turns': [], 'hooks': []}
        pending = self.staged({'v2': {'id': 'v2', 'arc': '秦姨抢先捞了半本老登记簿出来。', 'turns': [], 'hooks': []}})
        chapters = {'v2': [{'synopsis': '开场承接上一卷的后果。'}]}
        previous_chapters = [{'synopsis': '周电长烧旧物那晚，秦姨抢下半本老登记簿。'}]
        warnings = workflow.structure_warnings(pending, previous, {'v1': [1, 25], 'v2': [26, 50]},
                                               previous_chapters)
        self.assertIn('volume_boundary_overlap', codes(warnings))

    def test_shared_method_labels_do_not_read_as_an_event_retold(self):
        pending = self.staged({
            'v1': {'id': 'v1', 'arc': '本卷核心问题是旧档到期，铺垫段写街坊观望。',
                   'climax': '公开盯表。', 'turns': [], 'hooks': []},
            'v2': {'id': 'v2', 'arc': '开局承接挂牌后果，本卷核心问题是配额重分。', 'turns': [], 'hooks': []}})
        self.assertNotIn('volume_boundary_overlap',
                         codes(workflow.structure_warnings(pending, None, {'v1': [1, 30], 'v2': [31, 60]})))

    def test_uniform_turn_counts_across_volumes_warn(self):
        def volume(ident):
            return {'id': ident, 'arc': '卷%s的因果各不相同。' % ident, 'climax': '卷%s高潮。' % ident,
                    'turns': [{'at': '第%d章附近' % spot, 'turn': '换条件。'}
                              for spot in (3 + 30 * int(ident[1:]) - 30, 8 + 30 * int(ident[1:]) - 30,
                                           13 + 30 * int(ident[1:]) - 30)],
                    'hooks': [], 'threads': []}
        pending = self.staged({ident: volume(ident) for ident in ('v1', 'v2', 'v3')})
        spans = {'v1': [1, 30], 'v2': [31, 60], 'v3': [61, 90]}
        self.assertIn('volume_turn_uniform_count',
                      codes(workflow.structure_warnings(pending, None, spans)))

    def test_varying_turn_counts_stay_quiet(self):
        def volume(ident, count):
            return {'id': ident, 'arc': '卷%s的因果。' % ident, 'climax': '卷%s高潮。' % ident,
                    'turns': [{'at': '卷中', 'turn': '换条件。'}] * count, 'hooks': [], 'threads': []}
        pending = self.staged({'v1': volume('v1', 2), 'v2': volume('v2', 3), 'v3': volume('v3', 2)})
        self.assertNotIn('volume_turn_uniform_count',
                         codes(workflow.structure_warnings(pending, None,
                                                           {'v1': [1, 30], 'v2': [31, 60], 'v3': [61, 90]})))

    def test_a_continuing_thread_that_never_reappears_warns(self):
        def thread(ident, continues):
            return {'id': ident, 'kind': 'main', 'purpose': '线路%s的用途。' % ident,
                    'ending_condition': '收束条件。', 'required': True, 'continues': continues}
        pending = self.staged({
            'v1': {'id': 'v1', 'arc': '一', 'climax': '一', 'turns': [], 'hooks': [],
                   'threads': [thread('t4', True)]},
            'v2': {'id': 'v2', 'arc': '二', 'climax': '二', 'turns': [], 'hooks': [],
                   'threads': [thread('t9', False)]},
            'v3': {'id': 'v3', 'arc': '三', 'climax': '三', 'turns': [], 'hooks': [], 'threads': []}})
        warnings = workflow.structure_warnings(pending, None, {'v1': [1, 30], 'v2': [31, 60], 'v3': [61, 90]})
        dropped = [row for row in warnings if row['code'] == 'volume_thread_dropped']
        self.assertEqual([(row['volume'], row['line']) for row in dropped], [('v1', 't4')])

    def test_a_continuing_thread_re_registered_in_a_later_volume_stays_quiet(self):
        def thread(ident, continues):
            return {'id': ident, 'kind': 'main', 'purpose': '线路%s的用途。' % ident,
                    'ending_condition': '收束条件。', 'required': True, 'continues': continues}
        pending = self.staged({
            'v1': {'id': 'v1', 'arc': '一', 'climax': '一', 'turns': [], 'hooks': [],
                   'threads': [thread('t4', True)]},
            'v2': {'id': 'v2', 'arc': '二', 'climax': '二', 'turns': [], 'hooks': [],
                   'threads': [thread('t4', True)]}})
        self.assertNotIn('volume_thread_dropped',
                         codes(workflow.structure_warnings(pending, None, {'v1': [1, 30], 'v2': [31, 60]})))

    def test_a_payoff_window_straddling_a_volume_boundary_warns(self):
        pending = self.staged({
            'v1': {'id': 'v1', 'arc': '一', 'climax': '一', 'turns': [], 'threads': [],
                   'hooks': [{'id': 'h2', 'text': '公约半句。', 'plant': [10, 12], 'payoff': [148, 152],
                              'required': False}]}})
        spans = {'v1': [1, 30], 'v5': [121, 150], 'v6': [151, 180]}
        warnings = workflow.structure_warnings(pending, None, spans)
        straddle = next(row for row in warnings if row['code'] == 'volume_payoff_straddle')
        self.assertEqual(straddle['line'], 'h2')
        self.assertEqual((straddle['volume'], ), ('v1', ))

    def test_an_in_volume_payoff_window_stays_quiet(self):
        pending = self.staged({
            'v1': {'id': 'v1', 'arc': '一', 'climax': '一', 'turns': [], 'threads': [],
                   'hooks': [{'id': 'h1', 'text': '短线。', 'plant': [2, 4], 'payoff': [20, 25],
                              'required': False}]}})
        self.assertNotIn('volume_payoff_straddle',
                         codes(workflow.structure_warnings(pending, None, {'v1': [1, 30]})))

    def test_turns_clustered_at_both_ends_flag_the_hollow_middle(self):
        pending = self.staged({'v1': {'id': 'v1', 'arc': '卷一弧线。',
                                      'turns': [{'at': '开卷', 'turn': '立对手。'},
                                                {'at': '卷尾', 'turn': '换局面。'}],
                                      'hooks': []}})
        self.assertIn('volume_mid_hollow', codes(workflow.structure_warnings(pending, None, {'v1': [1, 30]})))

    def test_a_turn_in_the_middle_third_keeps_the_volume_quiet(self):
        pending = self.staged({'v1': {'id': 'v1', 'arc': '卷一弧线。',
                                      'turns': [{'at': '开卷', 'turn': '立对手。'},
                                                {'at': '第15章附近', 'turn': '换局面。'}],
                                      'hooks': []}})
        self.assertNotIn('volume_mid_hollow', codes(workflow.structure_warnings(pending, None, {'v1': [1, 30]})))

    def test_short_volumes_are_never_judged_on_middle_shape(self):
        pending = self.staged({'v1': {'id': 'v1', 'arc': '卷一弧线。',
                                      'turns': [{'at': '开卷', 'turn': '立对手。'},
                                                {'at': '卷尾', 'turn': '换局面。'}],
                                      'hooks': [{'id': 'h1', 'plant': [1, 1], 'payoff': [4, 4]},
                                                {'id': 'h2', 'plant': [1, 1], 'payoff': [4, 4]}]}})
        warnings = workflow.structure_warnings(pending, None, {'v1': [1, 4]})
        self.assertNotIn('volume_mid_hollow', codes(warnings))
        self.assertNotIn('volume_mid_no_hook', codes(warnings))

    def test_hook_windows_pinned_to_both_ends_flag_the_empty_middle(self):
        hooks = [{'id': 'h%d' % i, 'plant': [2, 4], 'payoff': [26, 30]} for i in (1, 2)]
        pending = self.staged({'v1': {'id': 'v1', 'arc': '卷一弧线。', 'turns': [], 'hooks': hooks}})
        self.assertIn('volume_mid_no_hook', codes(workflow.structure_warnings(pending, None, {'v1': [1, 30]})))

    def test_a_window_reaching_the_middle_keeps_the_volume_quiet(self):
        hooks = [{'id': 'h1', 'plant': [2, 4], 'payoff': [26, 30]},
                 {'id': 'h2', 'plant': [12, 14], 'payoff': [26, 30]}]
        pending = self.staged({'v1': {'id': 'v1', 'arc': '卷一弧线。', 'turns': [], 'hooks': hooks}})
        self.assertNotIn('volume_mid_no_hook', codes(workflow.structure_warnings(pending, None, {'v1': [1, 30]})))


class SynopsisFillerTests(unittest.TestCase):
    """A repeated clause is filler written to clear the length floor, not a style choice."""

    def setUp(self):
        self.raw = contract(chapters=4, volumes=2)
        self.book = seeded_book(self.raw)
        self.contract = self.book['contract']
        self.world = self.book['world']
        self.state = self.book['state']
        self.volume = self.contract['volumes'][0]
        self.volume_row = drift_validation.validate_volume_outline(
            {'volumes': volume_rows(self.book, ['v1'])}, self.contract, self.world,
            {}, {}, ['v1'], self.state)['v1']
        self.rows = chapter_rows(self.book, self.volume, self.state)

    def submit(self, rows):
        return drift_validation.validate_chapter_outline(
            {'volume': self.volume['id'], 'chapters': rows},
            self.contract['chapter_outline'], self.volume, self.volume_row, self.world, self.state)

    def test_a_verbatim_repeated_clause_is_refused_as_filler(self):
        rows = copy.deepcopy(self.rows)
        seed = '他数了一遍退件，又数了一遍登记单。他数了一遍退件，又数了一遍登记单。'
        rows[0]['synopsis'] = _fit_text(seed, 150)
        with self.assertRaises(Error) as caught:
            self.submit(rows)
        self.assertEqual(caught.exception.code, 'design_drift')
        criteria = {finding['criterion'] for finding in caught.exception.details['findings']}
        self.assertIn('chapter_filler', criteria)

    def test_distinct_clauses_at_the_same_length_stay_accepted(self):
        rows = copy.deepcopy(self.rows)
        rows[0]['synopsis'] = _fit_text(SYNOPSIS_SENTENCE, 150)
        self.submit(rows)

    def test_pacing_takes_its_two_named_keys_and_refuses_anything_else(self):
        rows = copy.deepcopy(self.rows)
        rows[0]['pacing'] = {'end_push': '章尾把读者推向对质。'}
        self.submit(rows)
        rows[0]['pacing'] = {'velocity': '快'}
        with self.assertRaises(Error) as caught:
            self.submit(rows)
        self.assertEqual(caught.exception.code, 'chapter_outline')


class VolumeEntityUnionTests(unittest.TestCase):
    """Volume references accept what the contract registered, not only world characters (V2)."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / 'book'
        self.repo = None

    def tearDown(self):
        if self.repo is not None:
            self.repo.close()
        self.temp.cleanup()

    def stage_with(self, extra_entities, placed_entity):
        raw = contract(chapters=4, volumes=2)
        raw['entities'].extend(extra_entities)
        self.repo = SQLiteRepository.initialize(self.project, seeded_book(raw))
        app = Application(self.repo)
        owner = app.run(finish=True, source='工程夹具授权跑到卷纲。')['owner']
        drive(app, until='volume_outline')
        result = response(app)
        result['data'] = volume_outline_fixture(app, self.repo.pending()['input'], hooks=False)
        result['data']['volumes'][0]['places'] = [
            {'entity': placed_entity, 'to': 'yard', 'reason': '卷末站位。'}]
        return app.submit(result)

    def test_a_contract_registered_entity_is_a_valid_volume_reference(self):
        outcome = self.stage_with([{'id': 'ma-liu', 'name': '马六', 'kind': 'person'}], 'ma-liu')
        self.assertEqual(outcome['outcome'], 'volume_confirmation_required')

    def test_an_entity_registered_nowhere_is_still_refused(self):
        with self.assertRaises(Error) as caught:
            self.stage_with([], 'ghost-person')
        criteria = {finding['criterion'] for finding in caught.exception.details['findings']}
        self.assertIn('volume_reference', criteria)


class RegroupBoardTests(unittest.TestCase):
    """A structural regroup materializes the next board instead of leaving the retired one (V16)."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / 'book'
        self.repo = SQLiteRepository.initialize(self.project, workflow.preparing_book(guided=True))
        self.app = Application(self.repo)

    def tearDown(self):
        self.repo.close()
        self.temp.cleanup()

    def walk_to_scale(self):
        for _ in range(13):
            handoff = self.app.advance()
            if handoff['action'] == 'await_choice':
                self.assertEqual(handoff['board']['gate']['id'], 'scale')
                return handoff
            self.assertEqual(handoff['action'], 'task_ready')
            result = gate_result(self.app, 'controller-main-session')
            self.app.submit(result)
            board = self.app.repo.load()['creation']['board']
            self.app.opening_choice(result['data']['options'][0]['id'], board['hash'], '作者选它。')
        raise AssertionError('没有走到结构门。')

    def test_a_structural_regroup_refreshes_the_board_card_and_snapshot(self):
        handoff = self.walk_to_scale()
        stale = Path(handoff['board_card']).read_text(encoding='utf-8')
        old_hash = handoff['board']['hash']
        result = self.app.opening_regroup(old_hash, '换一组：窗口沿阶梯滑动。')
        self.assertEqual(result['action'], 'await_choice')
        self.assertNotEqual(result['board']['hash'], old_hash)
        self.assertNotEqual(result['board']['option_ids'],
                            [row['id'] for row in handoff['board']['options']])
        card = Path(result['board_card'])
        self.assertEqual(card.name, 'board.md')
        self.assertTrue(card.is_file())
        self.assertNotEqual(card.read_text(encoding='utf-8'), stale)
        snapshot = json.loads(Path(result['advance_snapshot']).read_text(encoding='utf-8'))
        self.assertEqual(snapshot['board']['hash'], result['board']['hash'])
        # The engine's own state and the materialized card agree, so the next choose binds to
        # the new hash instead of being refused against the retired one.
        self.assertEqual(self.app.repo.load()['creation']['board']['hash'], result['board']['hash'])


if __name__ == '__main__':
    unittest.main()
