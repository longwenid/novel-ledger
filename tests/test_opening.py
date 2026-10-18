"""The current opening protocol: eleven male-channel gates, one question each.

These exercise opening/4 — the gate set a new book opens with: genre, origin, voice, scale, edge,
protagonist, relationships, world, opposition, payoff, title. The protagonist's origin is asked right
after the genre (the setting decides what "came from elsewhere" can even mean), the structural length
gate is answered by the engine from a proved ladder, every other gate by a cold worker, and the final
contract must keep each decision verbatim. Older gate sets keep their own regression cover:
`test_opening_v2.py` (opening/2) and `test_opening_legacy.py` (opening/1).
"""
import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from novel_ledger import creation, planning, workflow
from novel_ledger.bootstrap import local_application as Application
from novel_ledger.contracts import Error, OPENING_VERSION, SCALE_TIERS
from novel_ledger.sqlite_store import SQLiteRepository
from support import contract


VALUES = {
    'genre': {'genre': '都市异能', 'reader_promise': '看他从仓库夜班一路把签字责任查到底。', 'tone': '冷硬利落，偶尔留一点暖。'},
    'origin': {'family': '魂穿', 'arrival': '车祸后醒在这座仓库的夜班宿舍，带着上一世的核对习惯。',
               'cost': '原身的旧账跟着他，同事只当他忽然变了一个人。'},
    'voice': {'pov': '第三人称限知，只跟沈桐的所见所知。', 'voice': '短句推进，对白带信息。', 'style_traits': ['少解释多动作。', '章末留钩。']},
    'edge': {'advantage': '他能读出签字上被压过的第二层笔迹。', 'origin': '仓库夜班十年练出来的手感。',
             'growth': '三层：认笔迹、认印章、认改过的日期。', 'cost': '每次细看都要熬掉一夜的精力。',
             'ceiling': '能读出工具痕迹，读不出签字人的真实身份。'},
    'protagonist': {'id': 'shen', 'name': '沈桐', 'identity': '夜班退件工，背着一笔自己的旧账。',
                    'desire': '查清退件来源并洗掉自己的违规记录。', 'limit': '不牵连无关同事。'},
    'relationships': {'relationships': ['同事互相依赖，却各自担心承担责任。', '主管是他的旧师父，也是最想压住这件事的人。']},
    'world': {'world_premise': '一座仓库的夜班退件纠纷。',
              'mechanism': {'mode': 'none', 'principle': '只有普通规章与人情。', 'cost': '行动承担现实责任。', 'limits': []},
              'red_lines': ['没有超自然能力。'], 'allow_special_mechanism': False},
    'opposition': {'opposition': '第一卷对手是压签的主管，之后每卷抬一级：货站、承运商、写字楼里的签字链。',
                   'story_engine': '核对退件来源，追查签字责任。'},
    'payoff': {'plan': {'ways': ['核对签字打脸推责的人', '拿到被压的第二层笔迹', '把责任按证据落回原位'],
                        'cadence': '三到五章一次小兑现，章末留一个待查的封条。', 'hooks': '每卷中段翻出上一层签字链，卷尾落一次责任。'},
               'ending': '退件来源公开，工人承担违规开箱的后果，压签链条被拆开。', 'theme': '责任怎样在人之间传递。'},
    'title': {'title': '夜班退件：我能读出第二层笔迹'},
}
# Which field each gate varies so its options are genuinely different, not relabelled.
VARY = {'genre': 'reader_promise', 'origin': 'arrival', 'voice': 'voice', 'edge': 'advantage',
        'protagonist': 'identity', 'relationships': 'relationships', 'world': 'world_premise',
        'opposition': 'opposition', 'payoff': 'ending', 'title': 'title'}


def rows_for(gate):
    """Two worker-shaped options for one gate, built from the fixture values."""
    rows = []
    for index, ident in enumerate(('A', 'B')):
        value = copy.deepcopy(VALUES[gate])
        field = VARY.get(gate)
        if index and field:
            if isinstance(value[field], list):
                value[field] = value[field] + ['第二条关系：旧师父既护他也压他。']
            else:
                value[field] += '（另一种落法）'
        rows.append({'id': ident, 'title': '方案' + ident, 'premise': '具体方案' + ident + '。',
                     'pitch': '看一眼就想翻开的那句话' + ident + '。',
                     'scene': ['夜班仓库里，他把退件箱推到灯下，翻出封条上的签名。',
                               '凌晨的登记台前，他逐页核对自己经手的那一栏。'],
                     'driver': '方案' + ident + '以不同的方式推进：核对封条' + ident + '。',
                     'tradeoff': '相比另外一案，选它要放弃' + ident + '那条更快的路。',
                     'fit_reason': '承接已选题材，把推进压在一件具体物件上。', 'value': value})
    return rows


def shown(state):
    """The state with a board on display: the engine already gave one, or a worker offers one."""
    if state['board'] is not None:
        return state
    gate = creation.current(state)['id']
    return creation.offer(state, {'gate': gate, 'options': rows_for(gate)})


def walk(state):
    """Answer every gate in order, taking the first option the board shows."""
    while state['phase'] == 'choosing':
        state = shown(state)
        state = creation.pick(state, state['board']['options'][0]['id'], state['board']['hash'], '作者选它。')
    return state


def contract_from(state, world_rules=('夜班退件必须登记负责人。',)):
    """The contract a draft would write from these decisions, built independently of the projection."""
    choices = creation.selected(state)
    scale = choices['scale']
    total = scale['chapter_window'][0]
    value = contract()
    value.update({key: copy.deepcopy(scale[key]) for key in ('word_range', 'chapter_min', 'chapter_max', 'chapter_aim')})
    value.update(genre=choices['genre']['genre'], reader_promise=choices['genre']['reader_promise'], tone=choices['genre']['tone'])
    value.update(protagonist_origin=copy.deepcopy(choices['origin']))
    value.update(pov=choices['voice']['pov'], voice=choices['voice']['voice'], style_traits=list(choices['voice']['style_traits']))
    value.update(core_edge=copy.deepcopy(choices['edge']))
    value.update(protagonist_setup=copy.deepcopy(choices['protagonist']))
    value.update(relationships=list(choices['relationships']['relationships']))
    value.update(world_premise=choices['world']['world_premise'], red_lines=list(choices['world']['red_lines']),
                 allow_special_mechanism=choices['world']['allow_special_mechanism'], world_rules=list(world_rules))
    value.update(opposition=choices['opposition']['opposition'], story_engine=choices['opposition']['story_engine'])
    value.update(payoff_plan=copy.deepcopy(choices['payoff']['plan']), ending=choices['payoff']['ending'], theme=choices['payoff']['theme'])
    value.update(title=choices['title']['title'], planning_window=6,
                 volumes=[{'id': 'v' + str(i + 1), 'purpose': '查明来源并面对后果。',
                           'end': total * (i + 1) // scale['volume_count']} for i in range(scale['volume_count'])])
    return value


class OpeningThreeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / 'book'
        self.repo = SQLiteRepository.initialize(self.project, workflow.preparing_book(guided=True))
        self.app = Application(self.repo)

    def tearDown(self):
        self.repo.close()
        self.temp.cleanup()

    def assertCode(self, code, fn, *args):
        with self.assertRaises(Error) as caught:
            fn(*args)
        self.assertEqual(caught.exception.code, code)

    def test_a_new_project_opens_on_the_redesigned_gates_with_the_male_channel_direction(self):
        book = self.repo.load()
        self.assertEqual(creation.opening_version(book['creation']), OPENING_VERSION)
        self.assertEqual(self.app.status()['opening']['total_gates'],
                         len(creation.gate_ids(OPENING_VERSION)))
        task = self.app.advance()['task']
        self.assertEqual(task['stage'], 'opening_options')
        pending = self.repo.pending()['input']
        self.assertEqual(pending['payload']['gate']['id'], 'genre')
        # The direction reaches the option writer, together with what this gate means for it.
        self.assertIn('起点/番茄男频长篇网文', pending['brief'])
        self.assertIn('男频题材要连承诺一起给', pending['brief'])

    def test_the_origin_gate_follows_the_genre_and_owns_its_contract_field(self):
        """opening/4 asks where the protagonist came from, right after the genre decided the world.

        The origin is a contract field of its own (`protagonist_origin`), projected from the gate's
        whole value, so the alignment check compares it like every other decision.
        """
        from novel_ledger.contracts import CONTRACT_FIELDS, alignment_for, opening_source
        gates = [ident for ident, _title in creation.GATE_SETS[4]]
        self.assertEqual(len(gates), 11)
        self.assertEqual(gates[0], 'genre')
        self.assertEqual(gates[1], 'origin')
        self.assertEqual(creation.SYSTEM_GATES[4], ('scale',))
        self.assertEqual(creation.value_fields('origin', 4), ('family', 'arrival', 'cost'))
        row = next(entry for entry in CONTRACT_FIELDS if entry['key'] == 'protagonist_origin')
        self.assertEqual(tuple(row['shape']), ('family', 'arrival', 'cost'))
        self.assertEqual(opening_source(row, 4), ('origin', None))
        self.assertIn('protagonist_origin', alignment_for(4))

    def test_a_project_opened_under_the_older_protocol_keeps_its_ten_gates(self):
        """A gate set is a property of the project's own protocol, so v3 does not gain an origin."""
        state = creation.begin('工程夹具：旧协议项目。', version=3)
        self.assertEqual(len(creation.gate_ids(3)), 10)
        self.assertNotIn('origin', creation.gate_ids(3))
        self.assertEqual(creation.opening_version(state), 3)
        self.assertEqual(creation.gates(state), creation.GATES_V3)

    def test_the_anti_cliche_naming_discipline_survives_the_new_gate_order(self):
        """The origin gate precedes the protagonist gate, so the naming rules still apply there."""
        note = creation.gate_note(4, 'protagonist')
        self.assertTrue(note.strip())
        self.assertIn('命名', note)

    def test_every_later_gate_receives_the_direction_already_chosen(self):
        """A promise without its channel and setting is how a later gate drifts into another era.

        The protagonist gate once produced three consistent-sounding people from the wrong century
        because the selection line read exactly one field of the genre choice and that field was the
        promise. The line now carries the deciding fields under a fixed budget.
        """
        from novel_ledger import context
        chosen = {'title': '夜半验尸人',
                  'value': {'genre': '都市悬疑 + 妖异民俗，起点/番茄男频悬疑探案频道',
                            'reader_promise': '看一个没有执法权的法医助理把案子钉死。',
                            'tone': '冷、紧、潮湿'}}
        line = context._selection_line(chosen)
        self.assertIn('都市悬疑', line)
        self.assertIn('reader_promise=', line)
        self.assertLessEqual(len(line), len('夜半验尸人') + 121)
        # A gate whose value is a row of relations still contributes its first relation, and a gate
        # that decided nothing contributes only its title.
        relations = {'title': '关系', 'value': {'relationships': ['同门互相依赖又各自怕担责。']}}
        self.assertIn('同门互相依赖', context._selection_line(relations))
        self.assertEqual(context._selection_line({'title': '空门', 'value': {}}), '空门')

    def test_every_gate_owns_its_fields_and_states_its_structured_keys(self):
        for version in (3, OPENING_VERSION):
            for gate in creation.gate_ids(version):
                if gate in creation.SYSTEM_GATES[version]:
                    continue
                with self.subTest(gate=gate, version=version):
                    self.assertEqual(set(creation.value_fields(gate, version)), set(VALUES[gate]))
                    self.assertCode('opening_option', creation.validate_value, gate,
                                    {**copy.deepcopy(VALUES[gate]), 'unrelated': '越权字段。'}, version, {})
        # A premise the engine cannot check is refused: every declared key must be stated.
        edge = copy.deepcopy(VALUES['edge'])
        del edge['ceiling']
        self.assertCode('opening_option', creation.validate_value, 'edge', edge, 3, {})
        payoff = copy.deepcopy(VALUES['payoff'])
        payoff['plan']['ways'] = []
        self.assertCode('opening_option', creation.validate_value, 'payoff', payoff, 3, {})

    def test_an_origin_family_outside_the_four_directions_is_refused(self):
        for family in ('转世', '', None):
            broken = copy.deepcopy(VALUES['origin'])
            broken['family'] = family
            with self.subTest(family=family):
                self.assertCode('opening_option', creation.validate_value, 'origin', broken, 4, {})
        for field in ('arrival', 'cost'):
            incomplete = copy.deepcopy(VALUES['origin'])
            del incomplete[field]
            with self.subTest(missing=field):
                self.assertCode('opening_option', creation.validate_value, 'origin', incomplete, 4, {})
        # All four accepted directions pass with the two required sentences present.
        for family in ('魂穿', '身穿', '本土', '其他'):
            value = copy.deepcopy(VALUES['origin'])
            value['family'] = family
            self.assertIsNone(creation.validate_value('origin', value, 4, {}))

    def test_walking_every_gate_forms_a_contract_that_keeps_each_decision(self):
        state = walk(creation.begin('工程夹具：走完全程。'))
        self.assertEqual(state['phase'], 'world')
        choices = creation.selected(state)
        self.assertEqual(set(choices), set(creation.gate_ids(OPENING_VERSION)))
        value = contract_from(state)
        planning.validate_contract(value)
        world = {'rules': [{'principle': '夜班退件必须登记负责人。'}]}
        creation.validate_contract(value, state, world)
        # The two decisions male-channel serials live on are first-class contract terms, and the
        # origin is one of them now that the gate exists.
        self.assertEqual(value['core_edge'], choices['edge'])
        self.assertEqual(value['payoff_plan'], choices['payoff']['plan'])
        self.assertEqual(value['ending'], choices['payoff']['ending'])
        self.assertEqual(value['pov'], choices['voice']['pov'])
        self.assertEqual(value['protagonist_origin'], choices['origin'])
        # A contract that quietly changes a decision the author made is refused.
        tampered = copy.deepcopy(value)
        tampered['core_edge']['growth'] = '改成一层就封顶。'
        self.assertCode('opening_alignment', creation.validate_contract, tampered, state, world)
        retold = copy.deepcopy(value)
        retold['protagonist_origin'] = {**retold['protagonist_origin'], 'family': '身穿'}
        self.assertCode('opening_alignment', creation.validate_contract, retold, state, world)

    def test_intake_needs_only_a_tier_for_the_structural_gate(self):
        values = {gate: copy.deepcopy(value) for gate, value in VALUES.items()}
        values['scale'] = {'tier': 't4'}
        state = creation.intake(creation.begin('作者一次给全。'), values, '作者一次给全。')
        self.assertEqual(state['phase'], 'world')
        chosen = creation.selected(state)['scale']
        tier = next(row for row in SCALE_TIERS if row['id'] == 't4')
        for key in ('chapter_min', 'chapter_max', 'chapter_aim', 'volume_count', 'chapters', 'chapter_window'):
            self.assertEqual(chosen[key], tier[key], key)
        # An unknown class is refused with the real ladder rather than a guess (assertion folded
        # in from the retired version-2 twin of this test: the normalization is shared code).
        self.assertCode('opening_option', creation.intake, creation.begin('x'), {'scale': {'tier': 't9'}}, 'x')


if __name__ == '__main__':
    unittest.main()
