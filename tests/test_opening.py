"""Current opening decisions, versioned gate ownership and contract alignment."""
import copy
import json
import subprocess
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

# The declared tier ladder of the fixture world: four rungs, so the value passes every tier's
# `tier_min` (the strictest is 4) and the ladder gate's `stage_min` (also 4) without the test having
# to know which tier the system gate will hand the author.
WORLD_TIERS = [
    {'name': '一阶登记员', 'condition': '连续夜班满一年',
     'gain': '可独立开箱核对第一批退件', 'cost': '每次核对耗掉一夜精力',
     'limit': '只对本仓库的第一批退件有效'},
    {'name': '二阶核对员', 'condition': '连续夜班满三年或主管担保',
     'gain': '可调阅两个班的登记册', 'cost': '担保出错要连坐',
     'limit': '只对本仓库两个班的退件有效'},
    {'name': '三阶复核员', 'condition': '经手退件零差错满两百件',
     'gain': '可复核他人签字并记责任', 'cost': '复核判断要署名',
     'limit': '只对本站点的退件有效'},
    {'name': '四阶归档员', 'condition': '主持过一次全站退件清查',
     'gain': '可封存整批档案并提请追责', 'cost': '封存须向承运方报备',
     'limit': '只对本站点的历史档案有效'},
]
# The scale ladder: one rung per declared scope, rising outward; the last rung reaches 一界, which is
# what makes `cosmology` a required world section for this opening.
LADDER_LEVELS = [
    {'stage': '值班室', 'scope': '局部', 'growth': '地盘',
     'new_rule': '退件必须登记负责人', 'cost': '得罪当班同事'},
    {'stage': '货站', 'scope': '一城', 'growth': '势力',
     'new_rule': '货权归站里分配', 'cost': '欠下站长的人情'},
    {'stage': '分拨中心', 'scope': '一域', 'growth': '规则',
     'new_rule': '过域要凭证与押金', 'cost': '押上自己的身份'},
    {'stage': '全国承运网', 'scope': '一界', 'growth': '认知',
     'new_rule': '跨界的签字互认', 'cost': '公开自己的底牌'},
]

VALUES = {
    'genre': {'genre': '都市异能', 'reader_promise': '看他从仓库夜班一路把签字责任查到底。', 'tone': '冷硬利落，偶尔留一点暖。'},
    'premise': {'novelty': '这个世界的退件签字会改写责任归属，谁签谁背。',
                'first_cause': '上一轮签字制度崩过一次，才有了现在的登记规矩。',
                'stance': '利用', 'dark_side': '制度'},
    'origin': {'family': '魂穿', 'arrival': '车祸后醒在这座仓库的夜班宿舍，带着上一世的核对习惯。',
               'cost': '原身的旧账跟着他，同事只当他忽然变了一个人。'},
    'voice': {'pov': '第三人称限知，只跟沈桐的所见所知。', 'voice': '短句推进，对白带信息。', 'style_traits': ['少解释多动作。', '章末留钩。']},
    'world': {'world_premise': '一座仓库的夜班退件纠纷。',
              'mechanism': {'mode': 'none', 'principle': '只有普通规章与人情。', 'cost': '行动承担现实责任。', 'limits': []},
              'red_lines': ['没有超自然能力。'], 'allow_special_mechanism': False,
              'tiers': copy.deepcopy(WORLD_TIERS),
              'resource': {'name': '车费', 'source': '夜班结余',
                           'allocator': '夜班主管按班次登记后发放'}},
    'ladder': {'scale': {'opening': '开局只看得见仓库这片夜班作业区，读者跟着一间屋子往外看。',
                         'terminal': '体系', 'unchanged': '上层机构与签字制度跨卷不变'},
               'ladder': copy.deepcopy(LADDER_LEVELS)},
    'edge': {'advantage': '他能读出签字上被压过的第二层笔迹。', 'origin': '仓库夜班十年练出来的手感。',
             'growth': '三层：认笔迹、认印章、认改过的日期。', 'cost': '每次细看都要熬掉一夜的精力。',
             'ceiling': '能读出工具痕迹，读不出签字人的真实身份。'},
    'protagonist': {'id': 'shen', 'name': '沈桐', 'identity': '夜班退件工，背着一笔自己的旧账。',
                    'desire': '查清退件来源并洗掉自己的违规记录。', 'limit': '不牵连无关同事。'},
    'relationships': {'relationships': ['同事互相依赖，却各自担心承担责任。', '主管是他的旧师父，也是最想压住这件事的人。']},
    'opposition': {'opposition': '第一卷对手是压签的主管，之后每卷抬一级：货站、承运商、写字楼里的签字链。',
                   'story_engine': '核对退件来源，追查签字责任。'},
    'payoff': {'plan': {'ways': ['核对签字打脸推责的人', '拿到被压的第二层笔迹', '把责任按证据落回原位'],
                        'cadence': '三到五章一次小兑现，章末留一个待查的封条。',
                        'hooks': '每卷中段翻出上一层签字链，卷尾落一次责任。'},
               'ending': '退件来源公开，工人承担违规开箱的后果，压签链条被拆开。',
               'theme': '责任怎样在人之间传递。',
               'anchor': {'deliverable': '公开退件来源并把责任按证据落回原位。',
                          'deadline_chapter': '12'}},
    'title': {'title': '夜班退件：我能读出第二层笔迹'},
}
VALUES['world']['architecture'] = {'space': '旧大陆与海上城邦靠季节航路相连，远洋断航使各地无法独自存续。', 'history': '上个时代的资源战争留下互保契约，失效的旧承诺正在引发新的饥荒。', 'civilizations': '内陆联邦依赖海上供给，城邦依赖内陆技术，双方为旧契约的解释权冲突。', 'conflict': '各方只能转移灾害而不能消除灾害，越成功自保就越破坏共同生存条件。', 'mystery': '共同灾害来自先民维持航路的选择，揭开真相后仍要决定谁承担修复代价。'}

# Which field each gate varies so its options are genuinely different, not relabelled. A dotted path
# reaches into a structured answer (the ladder's own `scale.opening`) without breaking its shape.
VARY = {'genre': 'reader_promise', 'premise': 'novelty', 'origin': 'arrival', 'voice': 'voice',
        'world': 'world_premise', 'ladder': 'scale.opening', 'edge': 'advantage',
        'protagonist': 'identity', 'relationships': 'relationships', 'opposition': 'opposition',
        'payoff': 'ending', 'title': 'title'}


def _vary(value, path):
    """Change one leaf of a gate value so the second option is a different direction."""
    target = value
    parts = path.split('.')
    for part in parts[:-1]:
        target = target[part]
    leaf = parts[-1]
    if isinstance(target[leaf], list):
        target[leaf] = target[leaf] + ['另一种落法：旧师父既护他也压他。']
    else:
        target[leaf] += '（另一种落法）'


def rows_for(gate, version=OPENING_VERSION):
    """Two worker-shaped options for one gate, built from the fixture values."""
    rows = []
    for index, ident in enumerate(('A', 'B')):
        owned = creation.value_fields(gate, version)
        value = {key: copy.deepcopy(value) for key, value in VALUES[gate].items() if key in owned}
        field = VARY.get(gate)
        if index and field:
            _vary(value, field)
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
    return creation.offer(state, {'gate': gate, 'options': rows_for(gate, creation.opening_version(state))})


def walk(state):
    """Answer every gate in order, taking the first option the board shows."""
    while state['phase'] == 'choosing':
        state = shown(state)
        state = creation.pick(state, state['board']['options'][0]['id'], state['board']['hash'], '作者选它。')
    return state


def walk_to(state, gate, limit=20):
    """Answer gates until `gate` is the current one, and leave it without a board.

    A test that needs a specific gate must not hard-code the gates in front of it: the gate set has
    been redesigned twice (v4 added the origin gate, v5 added premise and ladder), and every list of
    "the gates before it" silently becomes a different gate's board. Walking by the engine's own
    `current` is stable across that. The target gate is returned un-offered, so the caller can put
    its own options on the board.
    """
    for _step in range(limit):
        if state['phase'] != 'choosing':
            break
        if creation.current(state)['id'] == gate:
            return state
        state = shown(state)
        state = creation.pick(state, state['board']['options'][0]['id'], state['board']['hash'], '作者选它。')
    raise AssertionError('没有走到目标门：' + gate)


def contract_from(state, world_rules=('夜班退件必须登记负责人。',)):
    """The contract a draft would write from these decisions, built independently of the projection."""
    choices = creation.selected(state)
    scale = choices['scale']
    total = scale['chapter_window'][0]
    value = contract()
    value.update({key: copy.deepcopy(scale[key]) for key in ('word_range', 'chapter_min', 'chapter_max', 'chapter_aim')})
    value.update(genre=choices['genre']['genre'], reader_promise=choices['genre']['reader_promise'], tone=choices['genre']['tone'])
    value.update(core_premise=copy.deepcopy(choices['premise']))
    value.update(protagonist_origin=copy.deepcopy(choices['origin']))
    value.update(pov=choices['voice']['pov'], voice=choices['voice']['voice'], style_traits=list(choices['voice']['style_traits']))
    value.update(core_edge=copy.deepcopy(choices['edge']))
    value.update(protagonist_setup=copy.deepcopy(choices['protagonist']))
    value.update(relationships=list(choices['relationships']['relationships']))
    value.update(world_premise=choices['world']['world_premise'], red_lines=list(choices['world']['red_lines']),
                 allow_special_mechanism=choices['world']['allow_special_mechanism'], world_rules=list(world_rules),
                 world_tiers=copy.deepcopy(choices['world']['tiers']),
                 world_resource=copy.deepcopy(choices['world']['resource']))
    if 'architecture' in choices['world']:
        value['world_architecture'] = copy.deepcopy(choices['world']['architecture'])
    value.update(world_scale=copy.deepcopy(choices['ladder']['scale']),
                 world_ladder=copy.deepcopy(choices['ladder']['ladder']))
    value.update(opposition=choices['opposition']['opposition'], story_engine=choices['opposition']['story_engine'])
    value.update(payoff_plan=copy.deepcopy(choices['payoff']['plan']), ending=choices['payoff']['ending'],
                 theme=choices['payoff']['theme'], promise_anchor=copy.deepcopy(choices['payoff']['anchor']))
    value.update(title=choices['title']['title'], revision_limit=6,
                 volumes=[{'id': 'v' + str(i + 1), 'purpose': '查明来源并面对后果。',
                           'end': total * (i + 1) // scale['volume_count']} for i in range(scale['volume_count'])])
    return value


def values_for_version(version):
    """The fixture values narrowed to the current gate's owned fields."""
    narrowed = {}
    for gate in creation.gate_ids(version):
        if gate in creation.SYSTEM_GATES.get(version, ()) or gate not in VALUES:
            continue
        owned = set(creation.value_fields(gate, version))
        narrowed[gate] = {key: copy.deepcopy(value) for key, value in VALUES[gate].items()
                          if key in owned}
    return narrowed


class CurrentOpeningTests(unittest.TestCase):
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

    def test_a_new_project_opens_on_the_current_protocol_with_the_male_channel_direction(self):
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
        # The protagonist enters a world whose architecture is already decided.
        gates = creation.gate_ids(OPENING_VERSION)
        self.assertEqual(len(gates), 13)
        self.assertEqual(gates[:4], ('genre', 'premise', 'voice', 'scale'))
        self.assertEqual(creation.SYSTEM_GATES[OPENING_VERSION], ('scale',))
        self.assertEqual(gates.index('world') + 1, gates.index('ladder'))

    def test_premise_and_origin_briefs_request_the_counts_the_receiver_accepts(self):
        from novel_ledger import briefs
        for gate in ('premise', 'origin'):
            with self.subTest(gate=gate):
                state = walk_to(creation.begin(), gate)
                brief = briefs.opening_options(creation.current(state),
                                               creation.lens_brief(0), version=OPENING_VERSION)
                self.assertNotIn('四个方向各给一个方案', brief)
                options = rows_for(gate)
                third = copy.deepcopy(options[0])
                third.update(id='C', title='方案C', premise='第三种具体方案。',
                             driver='另从旧账切入，追查责任转手的证据。')
                options.append(third)
                for count in (2, 3):
                    board = creation.offer(state, {'gate': gate, 'options': options[:count]})['board']
                    self.assertEqual(len(board['options']), count)
                fourth = copy.deepcopy(third)
                fourth['id'] = 'D'
                self.assertCode('opening_options', creation.offer, state,
                                {'gate': gate, 'options': options + [fourth]})

    def test_the_premise_gate_asks_the_four_questions_and_projects_them_verbatim(self):
        """The core idea is four answers, projected as one contract field (`core_premise`)."""
        from novel_ledger.contracts import (CONTRACT_FIELDS, DARK_SIDES, STANCES, alignment_for,
                                            opening_source)
        self.assertEqual(creation.value_fields('premise', OPENING_VERSION),
                         ('novelty', 'first_cause', 'stance', 'dark_side'))
        row = next(entry for entry in CONTRACT_FIELDS if entry['key'] == 'core_premise')
        self.assertEqual(tuple(row['shape']), ('novelty', 'first_cause', 'stance', 'dark_side'))
        self.assertEqual(opening_source(row, OPENING_VERSION), ('premise', None))
        self.assertIn('core_premise', alignment_for(OPENING_VERSION))
        state = walk(creation.begin('工程夹具：走完全程。'))
        choices = creation.selected(state)
        checked = contract_from(state)
        self.assertEqual(checked['core_premise'], choices['premise'])
        # The two enumerated answers only accept their declared values, and the whole value is owned.
        for field, values in (('stance', STANCES), ('dark_side', DARK_SIDES)):
            broken = copy.deepcopy(VALUES['premise'])
            broken[field] = '图开心'
            self.assertCode('opening_option', creation.validate_value, 'premise', broken,
                            OPENING_VERSION, {})
            value = copy.deepcopy(VALUES['premise'])
            value[field] = values[-1]
            self.assertIsNone(creation.validate_value('premise', value, OPENING_VERSION, {}))
        extra = copy.deepcopy(VALUES['premise'])
        extra['unrelated'] = '越权字段。'
        self.assertCode('opening_option', creation.validate_value, 'premise', extra,
                        OPENING_VERSION, {})

    def test_the_origin_gate_owns_its_contract_field(self):
        """The origin is a contract field of its own (`protagonist_origin`), projected whole."""
        from novel_ledger.contracts import CONTRACT_FIELDS, alignment_for, opening_source
        self.assertEqual(creation.value_fields('origin', OPENING_VERSION),
                         ('family', 'arrival', 'cost'))
        row = next(entry for entry in CONTRACT_FIELDS if entry['key'] == 'protagonist_origin')
        self.assertEqual(tuple(row['shape']), ('family', 'arrival', 'cost'))
        self.assertEqual(opening_source(row, OPENING_VERSION), ('origin', None))
        self.assertIn('protagonist_origin', alignment_for(OPENING_VERSION))
        # The four accepted directions pass; anything else, or a missing required sentence, is refused.
        for family in ('魂穿', '身穿', '本土', '其他'):
            value = copy.deepcopy(VALUES['origin'])
            value['family'] = family
            self.assertIsNone(creation.validate_value('origin', value, OPENING_VERSION, {}))
        for family in ('转世', '', None):
            broken = copy.deepcopy(VALUES['origin'])
            broken['family'] = family
            with self.subTest(family=family):
                self.assertCode('opening_option', creation.validate_value, 'origin', broken,
                                OPENING_VERSION, {})
        for field in ('arrival', 'cost'):
            incomplete = copy.deepcopy(VALUES['origin'])
            del incomplete[field]
            with self.subTest(missing=field):
                self.assertCode('opening_option', creation.validate_value, 'origin', incomplete,
                                OPENING_VERSION, {})

    def test_the_world_gate_projects_the_tiers_and_the_hard_currency(self):
        """The world gate delivers a tier ladder and a hard currency with its allocator, verbatim."""
        from novel_ledger.contracts import CONTRACT_FIELDS, alignment_for, opening_source
        self.assertEqual(set(creation.value_fields('world', OPENING_VERSION)),
                         {'world_premise', 'mechanism', 'red_lines', 'allow_special_mechanism',
                          'tiers', 'resource', 'architecture'})
        for key, shape in (('world_tiers', ('name', 'condition', 'gain', 'cost', 'limit')),
                           ('world_resource', ('name', 'source', 'allocator'))):
            row = next(entry for entry in CONTRACT_FIELDS if entry['key'] == key)
            self.assertEqual(tuple(row['shape']), shape)
            self.assertIn(key, alignment_for(OPENING_VERSION))
        self.assertEqual(opening_source(next(entry for entry in CONTRACT_FIELDS
                                              if entry['key'] == 'world_tiers'), OPENING_VERSION),
                         ('world', 'tiers'))
        state = walk(creation.begin('工程夹具：走完全程。'))
        choices = creation.selected(state)
        checked = contract_from(state)
        self.assertEqual(checked['world_tiers'], choices['world']['tiers'])
        self.assertEqual(checked['world_resource'], choices['world']['resource'])
        # A rung needs every declared field, and the currency needs its allocator.
        missing = copy.deepcopy(VALUES['world'])
        del missing['tiers'][0]['cost']
        self.assertCode('opening_option', creation.validate_value, 'world', missing,
                        OPENING_VERSION, {})
        no_allocator = copy.deepcopy(VALUES['world'])
        del no_allocator['resource']['allocator']
        self.assertCode('opening_option', creation.validate_value, 'world', no_allocator,
                        OPENING_VERSION, {})
        # A one-character name would make the world-model binding a coincidence, not evidence.
        one_word = copy.deepcopy(VALUES['world'])
        one_word['tiers'][0]['name'] = '一'
        self.assertCode('opening_option', creation.validate_value, 'world', one_word,
                        OPENING_VERSION, {})
        short_allocator = copy.deepcopy(VALUES['world'])
        short_allocator['resource']['allocator'] = '人'
        self.assertCode('opening_option', creation.validate_value, 'world', short_allocator,
                        OPENING_VERSION, {})

    def test_the_ladder_gate_projects_the_scale_and_a_monotonic_ladder(self):
        """The scale ladder starts local, rises outward, and projects as `world_scale`/`world_ladder`."""
        from novel_ledger.contracts import CONTRACT_FIELDS, alignment_for, opening_source
        self.assertEqual(creation.value_fields('ladder', OPENING_VERSION), ('scale', 'ladder'))
        row = next(entry for entry in CONTRACT_FIELDS if entry['key'] == 'world_ladder')
        self.assertEqual(tuple(row['shape']), ('stage', 'scope', 'growth', 'new_rule', 'cost'))
        self.assertIn('world_scale', alignment_for(OPENING_VERSION))
        self.assertEqual(opening_source(row, OPENING_VERSION), ('ladder', 'ladder'))
        state = walk(creation.begin('工程夹具：走完全程。'))
        choices = creation.selected(state)
        checked = contract_from(state)
        self.assertEqual(checked['world_scale'], choices['ladder']['scale'])
        self.assertEqual(checked['world_ladder'], choices['ladder']['ladder'])
        # A ladder that shrinks back is not a ladder: the scope order must never go backwards.
        backwards = copy.deepcopy(VALUES['ladder'])
        backwards['ladder'][2]['scope'] = '局部'
        self.assertCode('opening_option', creation.validate_value, 'ladder', backwards,
                        OPENING_VERSION, {})
        # The terminal is the author's declared end state, from the declared enum only.
        bad_terminal = copy.deepcopy(VALUES['ladder'])
        bad_terminal['scale']['terminal'] = '看心情'
        self.assertCode('opening_option', creation.validate_value, 'ladder', bad_terminal,
                        OPENING_VERSION, {})
        # A one-character stage would bind a one-character world record by coincidence.
        one_word = copy.deepcopy(VALUES['ladder'])
        one_word['ladder'][0]['stage'] = '甲'
        self.assertCode('opening_option', creation.validate_value, 'ladder', one_word,
                        OPENING_VERSION, {})

    def test_the_payoff_gate_binds_a_theme_anchor_to_a_deadline_chapter(self):
        """The anchor is what has to be delivered and the chapter it is due by, projected as a map."""
        from novel_ledger.contracts import CONTRACT_FIELDS, alignment_for, opening_source
        self.assertIn('anchor', creation.value_fields('payoff', OPENING_VERSION))
        row = next(entry for entry in CONTRACT_FIELDS if entry['key'] == 'promise_anchor')
        self.assertEqual(tuple(row['shape']), ('deliverable', 'deadline_chapter'))
        self.assertIn('promise_anchor', alignment_for(OPENING_VERSION))
        self.assertEqual(opening_source(row, OPENING_VERSION), ('payoff', 'anchor'))
        state = walk(creation.begin('工程夹具：走完全程。'))
        choices = creation.selected(state)
        checked = contract_from(state)
        self.assertEqual(checked['promise_anchor'], choices['payoff']['anchor'])
        deadline = checked['promise_anchor']['deadline_chapter']
        self.assertIsInstance(deadline, str, '期限章存为数字字符串，不是整数')
        self.assertTrue(deadline.isdigit())
        # The anchor is due inside the opening: a later deadline is not an opening anchor any more.
        late = copy.deepcopy(VALUES['payoff'])
        late['anchor']['deadline_chapter'] = '31'
        self.assertCode('opening_option', creation.validate_value, 'payoff', late,
                        OPENING_VERSION, {})
        empty = copy.deepcopy(VALUES['payoff'])
        empty['anchor']['deliverable'] = ''
        self.assertCode('opening_option', creation.validate_value, 'payoff', empty,
                        OPENING_VERSION, {})

    def test_an_older_declared_protocol_is_refused_with_the_fix_named(self):
        """Old gate sets are not re-planned: a state that declares one is refused, and a fresh init
        starts on the current protocol."""
        for version in range(1, OPENING_VERSION):
            with self.subTest(version=version):
                state = {'schema': 'novel-ledger.creation/' + str(version), 'phase': 'choosing', 'cursor': 0}
                self.assertCode('creation', creation.opening_version, state)
                self.assertCode('creation', creation.begin, 'x', version)
                self.assertCode('creation', creation.validate_value, 'genre', VALUES['genre'], version)
        for schema in (None, 'unknown/6', 'novel-ledger.creation/nonsense'):
            with self.subTest(schema=schema):
                self.assertCode('creation', creation.opening_version, {'schema': schema})
        self.assertEqual(creation.opening_version(self.repo.load()['creation']), OPENING_VERSION)
        self.assertEqual(creation.gates(self.repo.load()['creation']), creation.GATES)

    def test_every_tier_is_writable_under_the_contract_rules(self):
        """No tier may be offered unless a contract inside it passes the same rules the engine enforces."""
        for tier in SCALE_TIERS:
            with self.subTest(tier=tier['id']):
                choices = {'scale': {k: copy.deepcopy(tier[k]) for k in
                                     ('word_range', 'chapter_min', 'chapter_max', 'chapter_aim', 'volume_count')}}
                choices['scale'].update(tier=tier['id'], chapters=tier['chapters'], chapter_window=list(tier['chapter_window']))
                creation.validate_value('scale', choices['scale'], OPENING_VERSION, choices)
                # Every chapter count the window declares must survive the contract rules, not just
                # the shortest one: the band, the per-chapter aim and the declared maximum have to
                # hold together at each end of the window, or the ladder offers a size nobody can
                # actually write at that length.
                for total in range(tier['chapter_window'][0], tier['chapter_window'][1] + 1):
                    with self.subTest(tier=tier['id'], chapters=total):
                        raw = contract()
                        raw.update({key: copy.deepcopy(tier[key]) for key in
                                    ('word_range', 'chapter_min', 'chapter_max', 'chapter_aim')})
                        raw['volumes'] = [{'id': 'v' + str(i + 1), 'purpose': '查明来源并面对后果。',
                                           'end': total * (i + 1) // tier['volume_count']}
                                          for i in range(tier['volume_count'])]
                        checked = planning.validate_contract(raw)
                        self.assertEqual(checked['volumes'][-1]['end'], total)
                        self.assertEqual(checked['word_range'],
                                         [total * tier['chapter_min'], total * tier['chapter_max']])

    def test_importing_a_contract_is_allowed_before_the_first_gate_and_refused_after(self):
        command = [sys.executable, str(ROOT / 'scripts' / 'novel.py'), '--project', str(self.project)]
        example = str(ROOT / 'assets' / 'contract.example.json')
        early = subprocess.run(command + ['opening', '--file', example, '--source', '作者开书前给完整约定。'],
                               capture_output=True, text=True, encoding='utf-8', errors='replace')
        self.assertEqual(early.returncode, 0, early.stdout)
        self.assertTrue(json.loads(early.stdout)['staged'])
        self.assertIsNone(self.repo.load()['creation'])
        # An imported contract is activated on the engine's alignment check instead of dispatching a
        # contract review; the first dispatch of the book is the volume outline.
        task = self.app.advance()['task']
        self.assertEqual(task['stage'], 'volume_outline')
        self.assertIsNotNone(self.repo.load()['contract'])

        # A project that has already shown a gate refuses the import; a fresh init stays importable.
        with tempfile.TemporaryDirectory() as temporary:
            late_project = Path(temporary) / 'started'
            cli = [sys.executable, str(ROOT / 'scripts' / 'novel.py'), '--project', str(late_project)]
            subprocess.run(cli + ['init'], capture_output=True, text=True, encoding='utf-8', errors='replace')
            subprocess.run(cli + ['advance'], capture_output=True, text=True, encoding='utf-8', errors='replace')
            late = subprocess.run(cli + ['opening', '--file', example, '--source', '作者中途给完整约定。'],
                                  capture_output=True, text=True, encoding='utf-8', errors='replace')
            self.assertEqual(late.returncode, 2)
            self.assertEqual(json.loads(late.stdout)['error'], 'creation')
            repo = SQLiteRepository(late_project)
            try:
                self.assertIsNotNone(repo.load()['creation'])
                self.assertIsNone(repo.load()['contract'])
                self.assertIsNotNone(repo.pending())
            finally:
                repo.close()
            other = Path(temporary) / 'other'
            subprocess.run([sys.executable, str(ROOT / 'scripts' / 'novel.py'), '--project', str(other), 'init'],
                           capture_output=True, text=True, encoding='utf-8', errors='replace')
            ready = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'novel.py'), '--project', str(other),
                                    'opening', '--file', example, '--source', '作者开书前给完整约定。'],
                                   capture_output=True, text=True, encoding='utf-8', errors='replace')
            self.assertEqual(ready.returncode, 0, ready.stdout)

    def test_the_anti_cliche_naming_discipline_survives_the_gate_order(self):
        """The naming rules live on the protagonist gate that asks it."""
        note = creation.gate_note(OPENING_VERSION, 'protagonist')
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
        values = values_for_version(OPENING_VERSION)
        for gate, value in values.items():
            with self.subTest(gate=gate):
                self.assertEqual(set(creation.value_fields(gate, OPENING_VERSION)), set(value))
                self.assertCode('opening_option', creation.validate_value, gate,
                                {**copy.deepcopy(value), 'unrelated': '越权字段。'}, OPENING_VERSION, {})
        # A value the engine cannot check is refused: every declared key must be stated.
        edge = copy.deepcopy(VALUES['edge'])
        del edge['ceiling']
        self.assertCode('opening_option', creation.validate_value, 'edge', edge, OPENING_VERSION, {})
        payoff = copy.deepcopy(VALUES['payoff'])
        payoff['plan']['ways'] = []
        self.assertCode('opening_option', creation.validate_value, 'payoff', payoff, OPENING_VERSION, {})

    def test_walking_every_gate_forms_a_contract_that_keeps_each_decision(self):
        state = walk(creation.begin('工程夹具：走完全程。'))
        self.assertEqual(state['phase'], 'world')
        choices = creation.selected(state)
        self.assertEqual(set(choices), set(creation.gate_ids(OPENING_VERSION)))
        value = contract_from(state)
        planning.validate_contract(value)
        world = {'rules': [{'principle': '夜班退件必须登记负责人。'}]}
        creation.validate_contract(value, state, world)
        # Every v5 decision is a first-class contract term, projected from its gate verbatim.
        self.assertEqual(value['core_premise'], choices['premise'])
        self.assertEqual(value['protagonist_origin'], choices['origin'])
        self.assertEqual(value['world_tiers'], choices['world']['tiers'])
        self.assertEqual(value['world_resource'], choices['world']['resource'])
        self.assertEqual(value['world_scale'], choices['ladder']['scale'])
        self.assertEqual(value['world_ladder'], choices['ladder']['ladder'])
        self.assertEqual(value['promise_anchor'], choices['payoff']['anchor'])
        self.assertEqual(value['core_edge'], choices['edge'])
        self.assertEqual(value['payoff_plan'], choices['payoff']['plan'])
        self.assertEqual(value['pov'], choices['voice']['pov'])
        # A contract that quietly changes a decision the author made is refused.
        tampered = copy.deepcopy(value)
        tampered['core_edge']['growth'] = '改成一层就封顶。'
        self.assertCode('opening_alignment', creation.validate_contract, tampered, state, world)
        retold = copy.deepcopy(value)
        retold['protagonist_origin'] = {**retold['protagonist_origin'], 'family': '身穿'}
        self.assertCode('opening_alignment', creation.validate_contract, retold, state, world)
        rewritten = copy.deepcopy(value)
        rewritten['world_tiers'][0]['name'] = '无名登记员'
        self.assertCode('opening_alignment', creation.validate_contract, rewritten, state, world)

    def test_intake_takes_whole_and_partial_decisions_without_inventing_anything(self):
        """A complete intake needs only a tier for the structural gate; a partial intake keeps the
        complete simple gates it was given and invents no other decision."""
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

        values = {'title': {'title': '作者已定书名'}, 'scale': {'tier': 't0'}}
        state = creation.intake(creation.begin(), values, '作者已经决定书名与体量。')
        selected = creation.selected(state)
        self.assertEqual(set(selected), {'title', 'scale'})
        self.assertEqual(selected['title'], values['title'])
        self.assertEqual(selected['scale']['tier'], 't0')
        self.assertEqual(creation.current(state)['id'], 'genre')


if __name__ == '__main__':
    unittest.main()
