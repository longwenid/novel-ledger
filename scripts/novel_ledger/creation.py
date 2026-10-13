"""Zero-input opening choices. Pure state; only the author selects a board option."""
from __future__ import annotations

import copy
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
LENSES = ('限制驱动', '利益冲突', '认知差', '不可逆代价', '规则推演', '关系绑定', '终局回扣', '类型公理倒置')


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
        validate_value(gate['id'], option.get('value'), selected(state))
    require(all(len({o[k] for o in options}) == len(options) for k in ('id', 'title', 'premise', 'driver')),
            'opening_diversity', '方案应有实质差异，不能只换标签或措辞。')
    state = copy.deepcopy(state)
    board = {'gate': gate, 'round': state['round'], 'basis': basis(state), 'options': copy.deepcopy(options)}
    board['hash'] = digest(board)
    state['board'] = board
    state['history'].append({'action': 'offer', 'board': board})
    return state


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
    state['rejections'].append({'gate': current(state)['id'], 'board': state['board'], 'reason': reason})
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
    require(state['phase'] in ('contract', 'ready') and len(choices) == len(GATES), 'opening_incomplete', '全部选择和世界核验完成后才能形成约定。')
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
