"""Zero-input opening choices. Pure state; only the author selects a board option."""
from __future__ import annotations

import copy
from . import contracts
from .contracts import CONTRACT_ALIGNMENT, digest, require, text

GATES = (
    ('genre', '题材与读者体验'),
    ('scale', '篇幅与分卷体量'),
    ('protagonist', '主角身份、欲望与底线'),
    ('engine', '持续推进与主要对抗'),
    ('relationships', '核心关系与人物张力'),
    ('world', '世界前提与特殊机制'),
    ('ending', '工作终局与成立方向'),
    ('voice', '文风与阅读节奏'),
)
# Brainstorm lenses live in contracts.LENSES; this module only picks and carries them.
LENSES = tuple(label for label, _point, _structure in contracts.LENSES)


def lens_brief(index):
    """The method handed to the option writer: a bare label is not a method."""
    label, point, structure = contracts.LENSES[index % len(contracts.LENSES)]
    return '本轮创意透镜：' + label + '。' + point + ' 落地要求：' + structure


def begin(source=''):
    return {'schema': 'novel-ledger.creation/1', 'phase': 'choosing', 'cursor': 0,
            'round': 0, 'selections': [], 'board': None, 'history': [], 'rejections': [], 'source': source}


def selected(state):
    return {row['gate']: copy.deepcopy(row['option']['value']) for row in state['selections']}


def basis(state):
    return digest(state['selections'])


def current(state):
    ident, title = GATES[state['cursor']]
    return {'id': ident, 'title': title, 'number': state['cursor'] + 1, 'total': len(GATES)}


VALUE_RULES = {
    'genre': 'genre 题材、reader_promise 读者承诺、red_lines 禁区数组、allow_special_mechanism 布尔',
    'scale': 'word_range=[总汉字下限,上限]、chapter_min/chapter_max/chapter_aim、volume_count',
    'protagonist': 'id、name、identity 身份、desire 欲望、limit 底线',
    'engine': 'story_engine 持续推进的动力、opposition 主要对抗',
    'relationships': 'relationships 具体关系数组，独行方案可为空数组',
    'world': 'world_premise 世界前提、mechanism={mode:none或bounded, principle, cost, limits:数组}',
    'ending': 'ending 工作终局与成立方向',
    'voice': 'voice 文风、style_traits 表达要点数组',
}
# The delivery contract for one option: proposals, not arguments. The lens shapes how the option is
# found; it must not appear in what the author reads.
OPTION_CONTRACT = (
    '每个方案给：id、title 短标题、pitch 一句能记住的话（≤40字，不得出现透镜名或方法词）、'
    'scene 2～3 个可落笔的具体画面（谁、在哪、什么东西、正要做什么，每条≥12字）、'
    'premise 具体内容、driver 这一版如何推进（只写故事动作，不要写"某透镜落地"这类自评）、'
    'tradeoff 选它要放弃什么（与同组另外两案相比的代价，不要写品类通用缺点）、'
    'fit_reason 与已选方向的具体接口（承接哪条选择、因此改变了什么）、value 按本门字段。'
)
LENS_WORDS = ('透镜', '落地要求', '典型落法', '混搭', '倒置', '代价递进', '认知差', '规则推演', '闭环')


def _reject_lens_language(option):
    text = ' '.join(str(option.get(key, '')) for key in ('pitch', 'premise', 'driver', 'tradeoff', 'fit_reason'))
    self_reference = [word for word in LENS_WORDS if word in text]
    require(not self_reference, 'opening_voice', '方案文本不得自述创意方法；透镜只用于构思，不写给作者看。',
            {'found': self_reference, 'recover': '把"某透镜落地"改成这一版具体怎么推进。'})


def _check_scenes(option):
    scenes = option.get('scene')
    require(isinstance(scenes, list) and len(scenes) >= 2 and all(text(s) and len(s.strip()) >= 12 for s in scenes),
            'opening_scene', '每个方案至少给 2 个可落笔的具体画面（每条≥12字）：作者要看到能直接开写的场面。',
            {'recover': '写清谁在哪、手上是什么、正要做什么，不要给概念或口号。'})


def _check_driver_shape(options):
    """Three lengths of the same idea are not three options: the openings must not share a shape."""
    heads = []
    for option in options:
        driver = str(option.get('driver', '')).strip()
        head = driver[:6]
        heads.append(head)
    require(len(set(heads)) == len(heads), 'opening_diversity',
            '同组方案的推进方式开头雷同（例如都以"以…为刻度推进"起句），属于换个说法的同一个方案。',
            {'heads': heads, 'recover': '让三案的推进机制在结构上不同，而不是量级不同。'})


def validate_value(gate, value, choices):
    require(isinstance(value, dict), 'opening_option', '每个方案须有结构化 value。')
    if gate == 'genre':
        require(text(value.get('genre')) and text(value.get('reader_promise')) and isinstance(value.get('red_lines'), list)
                and all(text(s) for s in value['red_lines']) and type(value.get('allow_special_mechanism')) is bool,
                'opening_option', '题材方案需要题材、读者承诺、禁区和机制允许范围。')
    elif gate == 'scale':
        band = value.get('word_range')
        require(isinstance(band, list) and len(band) == 2 and all(type(n) is int and n > 0 for n in band)
                and band[0] <= band[1], 'opening_option', '篇幅方案需要有效 word_range。')
        require(all(type(value.get(k)) is int and value[k] > 0 for k in ('chapter_min', 'chapter_max', 'chapter_aim', 'volume_count'))
                and value['chapter_min'] <= value['chapter_aim'] <= value['chapter_max'], 'opening_option', '章幅与卷数须有效。')
        require(value['volume_count'] * value['chapter_min'] <= band[1], 'opening_option', '分卷最低承载不能超过总篇幅上限。')
    elif gate == 'protagonist':
        require(all(text(value.get(k)) for k in ('id', 'name', 'identity', 'desire', 'limit')), 'opening_option', '主角需要身份、欲望和底线。')
        require(not any(c in value['id'] for c in ':>'), 'opening_option', '主角 ID 不能含分隔符。')
    elif gate == 'engine':
        require(text(value.get('story_engine')) and text(value.get('opposition')), 'opening_option', '推进方案需要持续动力和对抗。')
    elif gate == 'relationships':
        require(isinstance(value.get('relationships'), list) and all(text(s) for s in value['relationships']), 'opening_option', '核心关系须为具体关系数组，独行方案可为空。')
    elif gate == 'world':
        mechanism = value.get('mechanism')
        require(text(value.get('world_premise')) and isinstance(mechanism, dict) and mechanism.get('mode') in ('none', 'bounded'), 'opening_option', '世界方案需要前提及明确机制类型。')
        require(text(mechanism.get('principle')) and text(mechanism.get('cost')) and isinstance(mechanism.get('limits'), list)
                and all(text(s) for s in mechanism['limits']), 'opening_option', '机制需要原理、代价和限制，无特殊机制也需解释。')
        require(choices.get('genre', {}).get('allow_special_mechanism', True) or mechanism['mode'] == 'none',
                'opening_constraint', '已选题材禁止特殊机制，不能用后续选项推翻。')
    elif gate == 'ending':
        require(text(value.get('ending')), 'opening_option', '终局方案需要具体成立方向。')
    elif gate == 'voice':
        require(text(value.get('voice')) and isinstance(value.get('style_traits'), list) and value['style_traits']
                and all(text(s) for s in value['style_traits']), 'opening_option', '文风方案需要表达特点和节奏。')


def offer(state, data):
    require(state['phase'] == 'choosing' and state['board'] is None, 'opening_state', '当前没有待生成的选择门。')
    gate = current(state)
    require(isinstance(data, dict) and data.get('gate') == gate['id'], 'opening_gate', '选项必须属于当前门。')
    options = data.get('options')
    require(isinstance(options, list) and 2 <= len(options) <= 3, 'opening_options', '每门提供 2～3 个可直接选择的具体方案。')
    for option in options:
        require(isinstance(option, dict) and all(text(option.get(k)) for k in ('id', 'title', 'premise', 'driver', 'tradeoff', 'fit_reason')),
                'opening_option', '方案需要标识、标题、具体内容、推进差异、代价和与已有选择的关联。')
        require(text(option.get('pitch')), 'opening_option', '方案需要 pitch：一句能记住的话（≤40字）。')
        _reject_lens_language(option)
        _check_scenes(option)
        validate_value(gate['id'], option.get('value'), selected(state))
    _check_driver_shape(options)
    require(all(len({o[k] for o in options}) == len(options) for k in ('id', 'title', 'premise', 'driver')),
            'opening_diversity', '方案应有实质差异，不能只换标签或措辞。')
    state = copy.deepcopy(state)
    board = {'gate': gate, 'round': state['round'], 'basis': basis(state), 'options': copy.deepcopy(options)}
    board['hash'] = digest(board)
    state['board'] = board
    state['history'].append({'action': 'offer', 'board': board})
    return state


def rejection_record(state, reason):
    """What a rejection has to carry forward: which directions the author already refused.

    The full board stays in `history` for audit; shipping it back on every later round would make the
    task material grow with every 换组, and a worker only needs to avoid repeating refused ideas.
    """
    board = state['board'] or {}
    return {'gate': current(state)['id'], 'round': state['round'], 'reason': reason,
            'titles': [o.get('title', '') for o in board.get('options', [])],
            'pitches': [o.get('pitch', '') for o in board.get('options', [])]}
def board_matches(state, board_hash):
    require(state['phase'] == 'choosing' and state['board'] is not None and state['board']['hash'] == board_hash
            and state['board']['basis'] == basis(state), 'opening_version', '请选择当前展示的一组方案；旧选项不能套到新一门。')


def pick(state, option_id, board_hash, source):
    require(text(source), 'author_source', '保存用户实际选择原话，用户只需选编号。')
    board_matches(state, board_hash)
    option = next((o for o in state['board']['options'] if o['id'] == option_id), None)
    require(option is not None, 'opening_option', '当前展示组中没有该选项。')
    state = copy.deepcopy(state)
    state['selections'].append({'gate': current(state)['id'], 'option': copy.deepcopy(option), 'board_hash': board_hash, 'source': source})
    state['history'].append({'action': 'choose', 'gate': current(state)['id'], 'option': option_id, 'board_hash': board_hash, 'source': source})
    state.update(board=None, round=0, cursor=state['cursor'] + 1)
    if state['cursor'] == len(GATES):
        state['phase'] = 'world'
        state['selection_hash'] = basis(state)
    return state


def regroup(state, board_hash, reason):
    require(text(reason), 'author_source', '保存换组要求；可以是用户只说的“换一组”。')
    board_matches(state, board_hash)
    state = copy.deepcopy(state)
    state['rejections'].append(rejection_record(state, reason))
    state['history'].append({'action': 'regroup', 'gate': current(state)['id'], 'reason': reason})
    state.update(board=None, round=state['round'] + 1)
    return state


def back(state, gate_id, reason):
    require(text(reason), 'author_source', '保存返回原因。')
    index = next((i for i, gate in enumerate(GATES) if gate[0] == gate_id), None)
    require(index is not None and index < state['cursor'], 'opening_back', '只能返回已经选过的一门。')
    state = copy.deepcopy(state)
    state['history'].append({'action': 'back', 'gate': gate_id, 'reason': reason, 'invalidated': copy.deepcopy(state['selections'][index:])})
    state.update(phase='choosing', cursor=index, round=0, board=None, selections=state['selections'][:index])
    state.pop('selection_hash', None)
    return state


def view(state):
    if state['phase'] != 'choosing':
        return {'phase': state['phase'], 'selected_gates': len(state['selections']), 'total_gates': len(GATES), 'selection_hash': state['selection_hash']}
    return {'phase': 'choosing', 'gate': current(state), 'board': copy.deepcopy(state['board']), 'selected': selected(state)}


def validate_contract(contract, state, world):
    """Every CONTRACT_ALIGNMENT field is decided by a closed choice, derived, or authored here."""
    choices = selected(state)
    # 'world' is the phase right after the last gate: every choice is closed, so a contract may be
    # formed then too — a combined dispatch drafts the world and that contract in one session.
    require(state['phase'] in ('world', 'contract', 'ready') and len(choices) == len(GATES),
            'opening_incomplete', '全部选择和世界核验完成后才能形成约定。')
    expected = {**choices['scale'], **choices['engine'], **choices['world'], **choices['ending'], **choices['voice'],
                'reader_promise': choices['genre']['reader_promise'], 'genre': choices['genre']['genre'],
                'protagonist_setup': choices['protagonist'], 'allow_special_mechanism': choices['genre']['allow_special_mechanism'],
                'relationships': choices['relationships']['relationships']}
    derived = {'entities', 'red_lines', 'volumes', 'world_rules', 'world_premise'}
    expected = {key: value for key, value in expected.items() if key in CONTRACT_ALIGNMENT and key not in derived}
    authored = {'title'}
    groups = (set(expected), derived, authored)
    require(set().union(*groups) == set(CONTRACT_ALIGNMENT)
            and not any(groups[i] & groups[j] for i in range(len(groups)) for j in range(i + 1, len(groups))),
            'alignment_schema', '对齐字段表与约定 schema 不一致，须同时更新。')
    for key, value in expected.items():
        if key == 'volume_count':
            require(len(contract['volumes']) == value, 'opening_alignment', '分卷数量与用户选择不一致。')
        else:
            require(contract.get(key) == value, 'opening_alignment', '最终约定改变了用户选择：' + key)
    require(all(line in contract['red_lines'] for line in choices['genre']['red_lines']), 'opening_alignment', '不能丢掉已选禁区。')
    protagonist = choices['protagonist']
    require(any(e['id'] == protagonist['id'] and e['name'] == protagonist['name'] and e['kind'] == 'person' for e in contract.get('entities', [])), 'opening_alignment', '最终约定必须保留所选主角身份。')
    require(contract['world_rules'] == [r['principle'] for r in world['rules']], 'opening_alignment', '约定世界规则须来自已独立核验的世界。')
    require(not contract.get('initial_knowledge'), 'opening_alignment', '世界隐秘设计不能直接登记为初始人物知情。')
    return contract
