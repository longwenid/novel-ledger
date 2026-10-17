"""Zero-input opening choices. Pure state; only the author selects a board option.

Two gate sets live side by side. Version 2 is what a new book opens with: one question per gate, the view
settled before any gate that shows sample scenes, the setting decided before the people who live in it,
and the length gate answered by the engine from a ladder of provably writable tiers instead of asking a
writer to invent numbers. Version 1 is the gate set every already-opened project was opened with; it
stays readable so an in-flight opening keeps its own protocol instead of being silently re-planned.
"""
from __future__ import annotations

import copy
from . import contracts
from .contracts import (OPENING_VERSION, SCALE_DEFAULT_WINDOW, SCALE_TIERS, SCALE_WINDOW, alignment_for,
                        digest, require, text)

GATES_V1 = (
    ('genre', '题材与读者体验'),
    ('scale', '篇幅与分卷体量'),
    ('protagonist', '主角身份、欲望与底线'),
    ('engine', '持续推进与主要对抗'),
    ('relationships', '核心关系与人物张力'),
    ('world', '世界前提与特殊机制'),
    ('ending', '工作终局与成立方向'),
    ('voice', '文风与阅读节奏'),
)
GATES_V2 = (
    ('genre', '题材、承诺与基调'),
    ('pov', '叙述视角与人称'),
    ('scale', '体量与分卷'),
    ('world', '世界前提、机制与禁区'),
    ('protagonist', '主角身份、欲望与底线'),
    ('relationships', '核心关系与人物张力'),
    ('engine', '持续推进与主要对抗'),
    ('ending', '终局与母题'),
    ('voice', '文风与节奏'),
    ('title', '书名'),
)
GATES_V3 = (
    ('genre', '题材、频道与读者承诺'),
    ('voice', '叙述人称与语感'),
    ('scale', '体量与分卷'),
    ('edge', '核心优势与成长线'),
    ('protagonist', '主角身份、处境与底线'),
    ('relationships', '核心关系与情感线'),
    ('world', '世界前提、机制与禁区'),
    ('opposition', '主要对抗与冲突梯度'),
    ('payoff', '爽点兑现与终局'),
    ('title', '书名'),
)
GATE_SETS = {1: GATES_V1, 2: GATES_V2, 3: GATES_V3}
# No bare `GATES` alias on purpose: which gate set applies is a property of the project's creation
# document, so every lookup goes through gates(state) instead of a module-level constant.
# Gates the engine answers itself from a table it has already proved satisfiable. A worker must not
# invent them, and no dispatch is spent on them.
SYSTEM_GATES = {1: (), 2: ('scale',), 3: ('scale',)}
# Inputs used by the world/scale derivation rules rather than copied into a contract.
# Direct choices and the protagonist value shape come from CONTRACT_FIELDS.opening.
DERIVATION_INPUTS = {'world': ('world_premise', 'mechanism', 'red_lines'),
                     'scale': ('tier', 'volume_count', 'chapters', 'chapter_window')}
# Brainstorm lenses live in contracts.LENSES; this module only picks and carries them.
LENSES = tuple(label for label, _point, _structure in contracts.LENSES)


def opening_version(state):
    """Which gate set a creation state belongs to. Anything unrecognised is treated as version 1."""
    raw = (state or {}).get('schema')
    try:
        version = int(str(raw).rsplit('/', 1)[-1])
    except (TypeError, ValueError):
        return 1
    return version if version in GATE_SETS else 1


def gates(state):
    return GATE_SETS[opening_version(state)]


def gate_ids(version):
    return tuple(ident for ident, _title in GATE_SETS[version])


def gate_title(gate_id, version=None):
    """Gate titles are version-scoped: the same id can ask a different question in a later protocol."""
    if version in GATE_SETS:
        found = next((title for ident, title in GATE_SETS[version] if ident == gate_id), None)
        if found:
            return found
    return next((title for ident, title in GATES_V2 + GATES_V1 if ident == gate_id), gate_id)


def lens_brief(index):
    """The method handed to the option writer: a bare label is not a method."""
    label, point, structure = contracts.LENSES[index % len(contracts.LENSES)]
    return '本轮创意透镜：' + label + '。' + point + ' 落地要求：' + structure


def begin(source='', version=OPENING_VERSION):
    return {'schema': 'novel-ledger.creation/' + str(version), 'phase': 'choosing', 'cursor': 0,
            'round': 0, 'selections': [], 'board': None, 'history': [], 'rejections': [], 'source': source}


def _normalize_intake(gate, value, version):
    """A structural gate is answered by naming a tier: the proved numbers are the engine's business.

    `intake` exists so an author with existing requirements never walks the gates. For every other gate
    the value is the decision itself; for the length gate the decision is the size class, so accepting
    only `{"tier": "t3"}` keeps the author from having to copy arithmetic out of the engine.
    """
    if gate not in SYSTEM_GATES.get(version, ()) or not isinstance(value, dict) or set(value) != {'tier'}:
        return value
    tier = next((row for row in SCALE_TIERS if row['id'] == value.get('tier')), None)
    require(tier is not None, 'opening_option', '体量要求须给出档位表里的档位 ID。',
            {'valid_tiers': [row['id'] for row in SCALE_TIERS],
             'recover': '用档位 ID 重写要求文件：' + '～'.join(row['id'] for row in SCALE_TIERS) + '（t0 最小）。'})
    return {'tier': tier['id'], 'word_range': list(tier['word_range']), 'chapter_min': tier['chapter_min'],
            'chapter_max': tier['chapter_max'], 'chapter_aim': tier['chapter_aim'],
            'volume_count': tier['volume_count'], 'chapters': tier['chapters'],
            'chapter_window': list(tier['chapter_window'])}


def intake(state, values, source):
    ids = gate_ids(opening_version(state))
    require(state['phase'] == 'choosing' and state['board'] is None and isinstance(values, dict) and values and text(source),
            'intake', '在未展示当前方案时保存部分要求，提供门 ID 到完整 value 的映射及作者原话。')
    known = selected(state)
    require(set(values) <= set(ids), 'intake', '要求使用已有门 ID；不把未定项伪造成作者决定。',
            {'valid_gates': list(ids), 'recover': '用本项目的门 ID 重写要求文件；已生效约定改方向用 recontract。'})
    version = opening_version(state)
    values = {gate: _normalize_intake(gate, value, version) for gate, value in values.items()}
    result = copy.deepcopy(state)
    all_values = {**known, **values}
    for gate in ids:
        if gate in all_values:
            validate_value(gate, all_values[gate], version, all_values)
    for gate, value in values.items():
        require(gate not in known or known[gate] == value, 'intake', '已定要求发生冲突，先 back 重开受影响门。')
        if gate not in known:
            result['selections'].append({'gate': gate, 'option': {'id': 'author:' + gate, 'title': '作者已有要求', 'value': copy.deepcopy(value)},
                                         'board_hash': None, 'source': source})
    result['history'].append({'action': 'intake', 'values': copy.deepcopy(values), 'source': source})
    return _advance_cursor(result)


def _advance_cursor(state):
    version = opening_version(state)
    ids = gate_ids(version)
    order = {ident: index for index, ident in enumerate(ids)}
    state['selections'].sort(key=lambda r: order[r['gate']])
    known = selected(state)
    state['cursor'] = next((index for index, ident in enumerate(ids) if ident not in known), len(ids))
    if state['cursor'] == len(ids):
        state['phase'] = 'world'
        state['selection_hash'] = basis(state)
        return state
    # A structural gate is answered the moment it is reached: the board comes from the tier table, so
    # the author never waits for a worker to invent numbers the contract stage would then reject.
    if ids[state['cursor']] in SYSTEM_GATES.get(version, ()):
        state['board'] = system_board(state)
    return state


def selected(state):
    return {row['gate']: copy.deepcopy(row['option']['value']) for row in state['selections']}


def basis(state):
    return digest(state['selections'])


def current(state):
    ids = gates(state)
    ident, title = ids[state['cursor']]
    return {'id': ident, 'title': title, 'number': state['cursor'] + 1, 'total': len(ids)}


VALUE_RULES = {
    1: {
        'genre': 'genre 题材、reader_promise 读者承诺、red_lines 禁区数组、allow_special_mechanism 布尔',
        'scale': 'chapter_min/chapter_max/chapter_aim、volume_count（总字数区间由章数与章幅派生）',
        'protagonist': 'id、name、identity 身份、desire 欲望、limit 底线',
        'engine': 'story_engine 持续推进的动力、opposition 主要对抗',
        'relationships': 'relationships 具体关系数组，独行方案可为空数组',
        'world': 'world_premise 世界前提、mechanism={mode:none或bounded, principle, cost, limits:数组}',
        'ending': 'ending 工作终局与成立方向',
        'voice': 'voice 文风、style_traits 表达要点数组',
    },
    2: {
        'genre': 'genre 题材、reader_promise 读者承诺、tone 基调（给读者的情绪与温度）',
        'pov': 'pov 叙述视角与人称：谁在讲、能看多远、换视角时怎样交代；scene 必须用该方案的人称写出来，让作者读到人称的实际效果',
        'scale': 'tier 档位 ID（intake 时只给 tier 即可，引擎补齐已证明的数字）、chapter_min/chapter_max/chapter_aim、volume_count、chapters、chapter_window（本门由系统按档位表即时给定，照抄不要改数；总字数区间是派生结果，不用填）',
        'world': 'world_premise 世界前提、mechanism={mode:none或bounded, principle, cost, limits:数组}、red_lines 禁区数组、allow_special_mechanism 布尔（必须等于 mode=="bounded"）',
        'protagonist': 'id、name、identity 身份、desire 欲望、limit 底线',
        'relationships': 'relationships 具体关系数组，至少一条：独行主角也要写清最关键的那段张力，不能交空数组',
        'engine': 'story_engine 持续推进的动力、opposition 主要对抗',
        'ending': 'ending 工作终局与成立方向、theme 母题（这本书关于什么）',
        'voice': 'voice 文风、style_traits 表达要点数组',
        'title': 'title 书名：与已选承诺、终局和文风相称的可用候选名，不是占位符',
    },
    3: {
        'genre': 'genre 题材与频道落点、reader_promise 读者承诺（爽点是什么、看谁赢谁）、tone 基调',
        'voice': 'pov 叙述人称与视角范围、voice 语感、style_traits 表达要点数组；scene 必须用该方案的人称写出来',
        'scale': 'tier 档位 ID（引擎按档位表补齐已证明的数字）、chapter_min/chapter_max/chapter_aim、volume_count、chapters、chapter_window（照抄不要改数；总字数区间是派生结果，不用填）',
        'edge': 'advantage 优势是什么、origin 怎么来、growth 分几层与升级条件、cost 每次使用的代价、ceiling 上限（约定字段 core_edge 直接存这五项）',
        'protagonist': 'id、name、identity 身份与处境、desire 欲望、limit 底线',
        'relationships': 'relationships 具体关系数组，至少一条：写清助力与背叛风险，以及感情线的分量与处理',
        'world': 'world_premise 世界前提、mechanism={mode:none或bounded, principle, cost, limits:数组}、red_lines 禁区数组、allow_special_mechanism 布尔（必须等于 mode=="bounded"）',
        'opposition': 'opposition 主要对抗与逐卷抬高方式（第一卷对手挡着什么利益、每次胜利换来多强的对手、终局面对谁）、story_engine 持续推进的动力',
        'payoff': 'plan={ways 兑现方式数组, cadence 短线兑现密度与章末钩, hooks 卷内高潮位置}（约定字段 payoff_plan 存这份 plan）、ending 终局兑现的那场胜利、theme 母题',
        'title': 'title 书名：男频搜索式可用名（点出题材与优势），不是占位符',
    },
}
# A gate whose delivery contract needs one more sentence than the value shape can carry.
GATE_NOTES = {
    2: {
        'pov': '本门只决定一件事：谁在讲。每个方案的 scene 用该方案的人称写出来，让作者读到的不是解释，而是这个人称讲出来的样子；pitch 也一样。不要在本门讨论情节走向。',
        'title': '本门只决定书名。每个方案给一个真正可用的候选名，并在 premise 里说清它承诺了什么、与终局如何相称；不要给"待定""暂名一"这类占位符，也不要重新讨论故事内容。',
    },
    3: {
        'voice': '本门只决定"怎么讲"：人称与视角范围是硬决定，语感是同一门的阅读质地。每个方案的 scene 与 pitch 都用该方案的人称写出来，让作者读到的不是解释，而是这个人称讲出来的样子；不要在本门讨论情节走向。',
        'edge': '本门只决定核心优势与成长线：advantage 优势是什么、origin 怎么得到、growth 分几层与每层升级条件、cost 每次使用的代价、ceiling 上限在哪。写清楚它在开篇三章内第一次怎么用上；不要写成世界观说明或力量体系百科，也不要替作者决定题材。',
        'opposition': '本门只决定对抗与梯度：第一卷谁挡着他、挡着什么具体利益、每次胜利换来多强的对手、终局面对谁。梯度必须是可执行的加码方式，不靠误会或临时改设定维持；不要在本门重述世界规则。',
        'payoff': '本门只决定读者一路拿到什么以及最后兑现成什么：plan 里的兑现方式、短线密度与章末钩、卷内高潮位置，以及终局兑现开篇承诺的那场胜利与母题。不要写成章节大纲，也不要在这里改对抗梯度。',
        'title': '本门只决定书名。按男频搜索习惯给真正可用的候选名：关键词直接点出题材与核心优势或身份优势，一眼能看懂看点；不要给"待定""暂名一"这类占位符，不要意象化短名，也不要重新讨论故事内容。',
    },
}


def gate_note(version, gate_id):
    return GATE_NOTES.get(version, {}).get(gate_id, '')


def value_rules(version, gate_id):
    rule = VALUE_RULES[version].get(gate_id, '按已选方向给出结构化方案。')
    if version >= 2:
        rule += ' value 只允许这些字段：' + '/'.join(value_fields(gate_id, version)) + '；不得携带其他门的决定或额外字段。'
    return rule


def value_fields(gate, version=OPENING_VERSION):
    """Opening input ownership for one version, derived from the same source used for alignment."""
    fields = []
    for row in contracts.CONTRACT_FIELDS:
        source = contracts.opening_source(row, version)
        if source and source[0] == gate and row.get('since', 1) <= version:
            fields.extend(row['shape'] if source[1] is None else (source[1],))
    return tuple(fields) + DERIVATION_INPUTS.get(gate, ())


# The delivery contract for one option: proposals, not arguments. The lens shapes how the option is
# found; it must not appear in what the author reads.
OPTION_CONTRACT = contracts.OPTION_CONTRACT
LENS_WORDS = ('透镜', '落地要求', '典型落法', '混搭', '倒置', '代价递进', '认知差', '规则推演', '闭环')


def _reject_lens_language(option):
    text = ' '.join(str(option.get(key, '')) for key in ('pitch', 'premise', 'driver', 'tradeoff', 'fit_reason'))
    self_reference = [word for word in LENS_WORDS if word in text]
    require(not self_reference, 'opening_voice', '方案文本不得自述创意方法；透镜只用于构思，不写给作者看。',
            {'found': self_reference, 'recover': '把"某透镜落地"改成这一版具体怎么推进。'})


def _check_scenes(option, strict_bounds=True):
    scenes = option.get('scene')
    require(isinstance(scenes, list) and len(scenes) >= 2
            and (not strict_bounds or len(scenes) <= 3)
            and all(text(s) and len(s.strip()) >= 12 for s in scenes),
            'opening_scene', ('每个方案给 2～3 个可落笔的具体画面（每条≥12字）。' if strict_bounds
                              else '每个方案至少给 2 个可落笔的具体画面（每条≥12字）。') + '作者要看到能直接开写的场面。',
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


def _tier_option(tier, following):
    low, high = tier['word_range']
    option = {'id': 'tier:' + tier['id'],
              'title': '%s档：%d 卷・约 %s～%s 万字' % (tier['name'], tier['volume_count'], _wan(low), _wan(high)),
              'premise': '全书约 %s～%s 万字，%d 卷约 %d 章；每章 %d～%d 字（目标 %d）。'
                         % (_wan(low), _wan(high), tier['volume_count'], tier['chapters'],
                            tier['chapter_min'], tier['chapter_max'], tier['chapter_aim']),
              'tradeoff': ('比%s档少买到：%s' % (following['name'], following['note'])) if following
                          else '已是阶梯里最大的一档：再长的篇幅只增加铺垫，不增加承载。',
              'value': {'tier': tier['id'], 'word_range': list(tier['word_range']),
                        'chapter_min': tier['chapter_min'], 'chapter_max': tier['chapter_max'],
                        'chapter_aim': tier['chapter_aim'], 'volume_count': tier['volume_count'],
                        'chapters': tier['chapters'], 'chapter_window': list(tier['chapter_window'])}}
    return option


def _wan(count):
    text = ('%.1f' % (count / 10000.0)).rstrip('0').rstrip('.')
    return text


def _tier_window(round_number):
    windows = max(1, len(SCALE_TIERS) - SCALE_WINDOW + 1)
    start = (SCALE_DEFAULT_WINDOW + round_number) % windows
    return list(SCALE_TIERS[start:start + SCALE_WINDOW])


def system_board(state):
    """The board a structural gate shows, built here and now: no task, no wait."""
    tiers = _tier_window(state['round'])
    following = {tier['id']: SCALE_TIERS[index + 1] if index + 1 < len(SCALE_TIERS) else None
                 for index, tier in enumerate(SCALE_TIERS)}
    options = [_tier_option(tier, following[tier['id']]) for tier in tiers]
    board = {'gate': current(state), 'round': state['round'], 'basis': basis(state),
             'options': options, 'system': True}
    board['hash'] = digest(board)
    return board


def validate_value(gate, value, version=OPENING_VERSION, choices=None):
    require(isinstance(value, dict), 'opening_option', '每个方案须有结构化 value。')
    if version == 3:
        return _validate_value_v3(gate, value)
    if version == 2:
        return _validate_value_v2(gate, value)
    return _validate_value_v1(gate, value, choices or {})


def _validate_value_v1(gate, value, choices):
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


def _validate_value_v2(gate, value):
    allowed = value_fields(gate, 2)
    unknown = sorted(set(value) - set(allowed))
    require(gate in gate_ids(2) and not unknown, 'opening_option', 'value 只能包含本门负责的字段。',
            {'gate': gate, 'unknown_fields': unknown, 'allowed_fields': list(allowed),
             'recover': '删除额外字段；修改此前决定须 back 返回对应门。'})
    if gate == 'genre':
        require(all(text(value.get(k)) for k in ('genre', 'reader_promise', 'tone')),
                'opening_option', '题材方案需要题材、读者承诺和基调。')
    elif gate == 'scale':
        tier = next((row for row in SCALE_TIERS if row['id'] == value.get('tier')), None)
        require(tier is not None, 'opening_option', '体量方案须来自档位表。',
                {'valid_tiers': [row['id'] for row in SCALE_TIERS],
                 'recover': '本门由主控从当前档位板照抄 value，不要自行改数。'})
        require(all(value.get(key) == tier[key] for key in ('word_range', 'chapter_min', 'chapter_max',
                                                           'chapter_aim', 'volume_count')),
                'opening_option', '体量方案的数字必须与档位表逐字一致。', {'tier': tier['id']})
        require(value.get('chapters') == tier['chapters'] and list(value.get('chapter_window') or []) == tier['chapter_window'],
                'opening_option', '体量方案的总章数与可写完区间必须与档位表一致。', {'tier': tier['id']})
        require(value['chapter_min'] <= value['chapter_aim'] <= value['chapter_max']
                and value['volume_count'] * value['chapter_min'] <= value['word_range'][1],
                'opening_option', '档位内的章幅与分卷须自洽。')
        require(tier['chapter_window'][0] <= value['chapters'] <= tier['chapter_window'][1],
                'opening_option', '档位推荐的章数必须落在该档可写完区间内。')
    elif gate == 'world':
        mechanism = value.get('mechanism')
        require(text(value.get('world_premise')) and isinstance(mechanism, dict) and mechanism.get('mode') in ('none', 'bounded'),
                'opening_option', '世界方案需要前提及明确机制类型。')
        require(text(mechanism.get('principle')) and text(mechanism.get('cost')) and isinstance(mechanism.get('limits'), list)
                and all(text(s) for s in mechanism['limits']), 'opening_option', '机制需要原理、代价和限制，无特殊机制也需解释。')
        require(isinstance(value.get('red_lines'), list) and all(text(s) for s in value['red_lines']),
                'opening_option', '世界方案需要禁区数组（可以为空，但必须是数组）。')
        require(type(value.get('allow_special_mechanism')) is bool and value['allow_special_mechanism'] == (mechanism['mode'] == 'bounded'),
                'opening_option', '机制允许范围必须与机制类型一致：有机制为真，无机制为假。')
    elif gate == 'pov':
        require(text(value.get('pov')), 'opening_option', '视角方案需要具体的人称与视角范围。')
    elif gate == 'protagonist':
        require(all(text(value.get(k)) for k in ('id', 'name', 'identity', 'desire', 'limit')), 'opening_option', '主角需要身份、欲望和底线。')
        require(not any(c in value['id'] for c in ':>'), 'opening_option', '主角 ID 不能含分隔符。')
    elif gate == 'relationships':
        require(isinstance(value.get('relationships'), list) and value['relationships'] and all(text(s) for s in value['relationships']),
                'opening_option', '核心关系至少一条：独行主角也要写清最关键的那段关系张力，不能交空数组。')
    elif gate == 'engine':
        require(text(value.get('story_engine')) and text(value.get('opposition')), 'opening_option', '推进方案需要持续动力和对抗。')
    elif gate == 'ending':
        require(all(text(value.get(k)) for k in ('ending', 'theme')), 'opening_option', '终局方案需要成立方向和母题。')
    elif gate == 'voice':
        require(text(value.get('voice')) and isinstance(value.get('style_traits'), list)
                and value['style_traits'] and all(text(s) for s in value['style_traits']),
                'opening_option', '文风方案需要文风和表达要点。')
    elif gate == 'title':
        require(text(value.get('title')), 'opening_option', '书名方案需要可用的书名。')


def _validate_value_v3(gate, value):
    """opening/3: the same ownership rule, with the male-channel decisions as first-class gates."""
    allowed = value_fields(gate, 3)
    unknown = sorted(set(value) - set(allowed))
    require(gate in gate_ids(3) and not unknown, 'opening_option', 'value 只能包含本门负责的字段。',
            {'gate': gate, 'unknown_fields': unknown, 'allowed_fields': list(allowed),
             'recover': '删除额外字段；修改此前决定须 back 返回对应门。'})
    if gate == 'genre':
        require(all(text(value.get(k)) for k in ('genre', 'reader_promise', 'tone')),
                'opening_option', '题材方案需要题材、读者承诺和基调。')
    elif gate == 'voice':
        require(text(value.get('pov')) and text(value.get('voice')) and isinstance(value.get('style_traits'), list)
                and value['style_traits'] and all(text(s) for s in value['style_traits']),
                'opening_option', '叙述方案需要人称与视角、语感和表达要点。')
    elif gate == 'scale':
        tier = next((row for row in SCALE_TIERS if row['id'] == value.get('tier')), None)
        require(tier is not None, 'opening_option', '体量方案须来自档位表。',
                {'valid_tiers': [row['id'] for row in SCALE_TIERS],
                 'recover': '本门由主控从当前档位板照抄 value，不要自行改数。'})
        require(all(value.get(key) == tier[key] for key in ('word_range', 'chapter_min', 'chapter_max',
                                                           'chapter_aim', 'volume_count')),
                'opening_option', '体量方案的数字必须与档位表逐字一致。', {'tier': tier['id']})
        require(value.get('chapters') == tier['chapters'] and list(value.get('chapter_window') or []) == tier['chapter_window'],
                'opening_option', '体量方案的总章数与可写完区间必须与档位表一致。', {'tier': tier['id']})
        require(value['chapter_min'] <= value['chapter_aim'] <= value['chapter_max']
                and value['volume_count'] * value['chapter_min'] <= value['word_range'][1],
                'opening_option', '档位内的章幅与分卷须自洽。')
        require(tier['chapter_window'][0] <= value['chapters'] <= tier['chapter_window'][1],
                'opening_option', '档位推荐的章数必须落在该档可写完区间内。')
    elif gate == 'edge':
        _require_keys(value, ('advantage', 'origin', 'growth', 'cost', 'ceiling'), '核心优势方案')
    elif gate == 'protagonist':
        require(all(text(value.get(k)) for k in ('id', 'name', 'identity', 'desire', 'limit')), 'opening_option', '主角需要身份、欲望和底线。')
        require(not any(c in value['id'] for c in ':>'), 'opening_option', '主角 ID 不能含分隔符。')
    elif gate == 'relationships':
        require(isinstance(value.get('relationships'), list) and value['relationships'] and all(text(s) for s in value['relationships']),
                'opening_option', '核心关系至少一条：写清助力与背叛风险，以及感情线的分量与处理。')
    elif gate == 'world':
        mechanism = value.get('mechanism')
        require(text(value.get('world_premise')) and isinstance(mechanism, dict) and mechanism.get('mode') in ('none', 'bounded'),
                'opening_option', '世界方案需要前提及明确机制类型。')
        require(text(mechanism.get('principle')) and text(mechanism.get('cost')) and isinstance(mechanism.get('limits'), list)
                and all(text(s) for s in mechanism['limits']), 'opening_option', '机制需要原理、代价和限制，无特殊机制也需解释。')
        require(isinstance(value.get('red_lines'), list) and all(text(s) for s in value['red_lines']),
                'opening_option', '世界方案需要禁区数组（可以为空，但必须是数组）。')
        require(type(value.get('allow_special_mechanism')) is bool and value['allow_special_mechanism'] == (mechanism['mode'] == 'bounded'),
                'opening_option', '机制允许范围必须与机制类型一致：有机制为真，无机制为假。')
    elif gate == 'opposition':
        require(text(value.get('opposition')) and text(value.get('story_engine')),
                'opening_option', '对抗方案需要对抗梯度与持续推进的动力。')
    elif gate == 'payoff':
        plan = value.get('plan')
        require(isinstance(plan, dict) and isinstance(plan.get('ways'), list) and plan['ways']
                and all(text(s) for s in plan['ways']),
                'opening_option', '爽点方案 plan.ways 至少列一条兑现方式（脱困、打脸、升级、资源、地位、基建、复仇、争霸等）。')
        _require_keys(plan, ('cadence', 'hooks'), '爽点方案 plan')
        _require_keys(value, ('ending', 'theme'), '爽点方案')
    elif gate == 'title':
        require(text(value.get('title')), 'opening_option', '书名方案需要可用的书名。')


def _require_keys(value, keys, label):
    """A structured decision states every declared key, not a paragraph the engine cannot check."""
    missing = [key for key in keys if not text(value.get(key))]
    require(not missing, 'opening_option', label + '需要逐项写清的结构化字段，不能留空或写成自由段落。',
            {'missing': missing, 'expect': list(keys)})


def offer(state, data, strict_bounds=True):
    require(state['phase'] == 'choosing', 'opening_state', '当前没有待生成的选择门。')
    version = opening_version(state)
    gate = current(state)
    require(gate['id'] not in SYSTEM_GATES.get(version, ()), 'opening_system',
            '本门由系统按档位表即时给定，不接受方案回执。',
            {'gate': gate['id'], 'recover': '结构门的 value 直接取当前展示档位，不要派 Worker 编造数字。'})
    require(state['board'] is None, 'opening_state', '当前没有待生成的选择门。')
    require(isinstance(data, dict) and data.get('gate') == gate['id'], 'opening_gate', '选项必须属于当前门。')
    options = data.get('options')
    require(isinstance(options, list) and 2 <= len(options) <= 3, 'opening_options', '每门提供 2～3 个可直接选择的具体方案。')
    for option in options:
        require(isinstance(option, dict) and all(text(option.get(k)) for k in ('id', 'title', 'premise', 'driver', 'tradeoff', 'fit_reason')),
                'opening_option', '方案需要标识、标题、具体内容、推进差异、代价和与已有选择的关联。')
        require(text(option.get('pitch')) and (not strict_bounds or len(option['pitch'].strip()) <= 40),
                'opening_option', '方案需要 pitch：一句能记住的话（≤40字）。' if strict_bounds else '方案需要非空 pitch。')
        _reject_lens_language(option)
        _check_scenes(option, strict_bounds)
        validate_value(gate['id'], option.get('value'), version, selected(state))
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
            and state['board']['basis'] == basis(state), 'opening_version', '请选择当前展示的一组方案；旧选项不能套到新一门。',
            {'gate': current(state)['id'], 'current_board': state['board']['hash'] if state.get('board') else None,
             'recover': '先 advance 取当前展示板的 hash，再用它执行 choose/regroup/back。'})


def pick(state, option_id, board_hash, source):
    require(text(source), 'author_source', '保存用户实际选择原话，用户只需选编号。')
    board_matches(state, board_hash)
    option = next((o for o in state['board']['options'] if o['id'] == option_id), None)
    require(option is not None, 'opening_option', '当前展示组中没有该选项。',
            {'valid_options': [o['id'] for o in state['board']['options']], 'board': state['board']['hash'],
             'recover': 'option id 由方案 Worker 自定（不一定是 A/B/C），从 valid_options 中选择。'})
    state = copy.deepcopy(state)
    state['selections'].append({'gate': current(state)['id'], 'option': copy.deepcopy(option), 'board_hash': board_hash, 'source': source})
    state['history'].append({'action': 'choose', 'gate': current(state)['id'], 'option': option_id, 'board_hash': board_hash, 'source': source})
    state.update(board=None, round=0)
    return _advance_cursor(state)


def regroup(state, board_hash, reason):
    require(text(reason), 'author_source', '保存换组要求；可以是用户只说的“换一组”。')
    board_matches(state, board_hash)
    state = copy.deepcopy(state)
    state['rejections'].append(rejection_record(state, reason))
    state['history'].append({'action': 'regroup', 'gate': current(state)['id'], 'reason': reason})
    state.update(board=None, round=state['round'] + 1)
    # A structural board has no worker to re-dispatch: 换一组 slides the tier window along the ladder.
    if current(state)['id'] in SYSTEM_GATES.get(opening_version(state), ()):
        state['board'] = system_board(state)
    return state


def back(state, gate_id, reason):
    require(text(reason), 'author_source', '保存返回原因。')
    ids = gate_ids(opening_version(state))
    index = next((i for i, ident in enumerate(ids) if ident == gate_id), None)
    require(index is not None and gate_id in selected(state), 'opening_back', '只能返回已经选过的一门。',
            {'valid_gates': list(ids)})
    state = copy.deepcopy(state)
    order = {ident: i for i, ident in enumerate(ids)}
    state['history'].append({'action': 'back', 'gate': gate_id, 'reason': reason, 'invalidated': copy.deepcopy([r for r in state['selections'] if order[r['gate']] >= index])})
    state.update(phase='choosing', cursor=index, round=0, board=None, selections=[r for r in state['selections'] if order[r['gate']] < index])
    _advance_cursor(state)
    state.pop('selection_hash', None)
    return state


def view(state):
    if state['phase'] != 'choosing':
        return {'phase': state['phase'], 'selected_gates': len(state['selections']), 'total_gates': len(gates(state)),
                'selection_hash': state['selection_hash']}
    return {'phase': 'choosing', 'gate': current(state), 'board': copy.deepcopy(state['board']), 'selected': selected(state)}


def _v1_groups(choices):
    expected = {**choices['scale'], **choices['engine'], **choices['world'], **choices['ending'], **choices['voice'],
                'reader_promise': choices['genre']['reader_promise'], 'genre': choices['genre']['genre'],
                'protagonist_setup': choices['protagonist'], 'allow_special_mechanism': choices['genre']['allow_special_mechanism'],
                'relationships': choices['relationships']['relationships']}
    derived = {'entities', 'red_lines', 'volumes', 'world_rules', 'world_premise'}
    return expected, derived, {'title'}


def _v2_groups(choices, version=OPENING_VERSION):
    """Project each decision from its declared owner, never merge entire option values.

    Ownership is per version: a field a later protocol re-sources is read from that version's gate,
    and a field the version never decided is simply absent instead of raising on a missing gate.
    """
    expected = {}
    for row in contracts.CONTRACT_FIELDS:
        if row.get('since', 1) > version or row['key'] in contracts.DERIVED_FIELDS:
            continue
        source = contracts.opening_source(row, version)
        if source:
            gate, key = source
            expected[row['key']] = copy.deepcopy(choices[gate] if key is None else choices[gate][key])
    derived = {'entities', 'red_lines', 'volumes', 'world_rules', 'world_premise'}
    return expected, derived, set()


def validate_contract(contract, state, world):
    """Every alignment field of this opening version is decided by a closed choice or derived here."""
    version = opening_version(state)
    choices = selected(state)
    ids = gate_ids(version)
    # 'world' is the phase right after the last gate: every choice is closed, so a contract may be
    # formed then too — a combined dispatch drafts the world and that contract in one session.
    require(state['phase'] in ('world', 'contract', 'ready') and len(choices) == len(ids),
            'opening_incomplete', '全部选择和世界核验完成后才能形成约定。')
    if version >= 2:
        for gate in ids:
            validate_value(gate, choices[gate], version)
    expected, derived, authored = _v1_groups(choices) if version == 1 else _v2_groups(choices, version)
    expected = {key: value for key, value in expected.items() if key in alignment_for(version) and key not in derived}
    groups = (set(expected), derived, set(authored))
    require(set().union(*groups) == set(alignment_for(version))
            and not any(groups[i] & groups[j] for i in range(len(groups)) for j in range(i + 1, len(groups))),
            'alignment_schema', '对齐字段表与约定 schema 不一致，须同时更新。')
    for key, value in expected.items():
        require(key in contract, 'opening_alignment', '约定缺少本门已选字段：' + key,
                {'key': key, 'recover': '按模板补齐该字段，并逐字保留作者选择。'})
        require(contract.get(key) == value, 'opening_alignment', '最终约定改变了用户选择：' + key)
    require(len(contract['volumes']) == choices['scale']['volume_count'], 'opening_alignment', '分卷数量与用户选择不一致。')
    if version >= 2:
        tier = next((row for row in SCALE_TIERS if row['id'] == choices['scale']['tier']), None)
        require(tier is not None, 'opening_alignment', '体量档位不在档位表中。', {'tier': choices['scale'].get('tier')})
        chapters = contract['volumes'][-1]['end']
        require(tier['chapter_window'][0] <= chapters <= tier['chapter_window'][1], 'opening_alignment',
                '全书章数与所选体量档位不相容。',
                {'tier': tier['id'], 'chapters': chapters, 'chapter_window': tier['chapter_window'],
                 'recover': '把卷末章号落在该档区间内，或 back 重选体量档位。'})
    forbidden = choices['genre'] if version == 1 else choices['world']
    require(all(line in contract['red_lines'] for line in forbidden['red_lines']), 'opening_alignment', '不能丢掉已选禁区。')
    protagonist = choices['protagonist']
    require(any(e['id'] == protagonist['id'] and e['name'] == protagonist['name'] and e['kind'] == 'person' for e in contract.get('entities', [])), 'opening_alignment', '最终约定必须保留所选主角身份。')
    require(contract['world_rules'] == [r['principle'] for r in world['rules']], 'opening_alignment', '约定世界规则须来自已独立核验的世界。')
    require(not contract.get('initial_knowledge'), 'opening_alignment', '世界隐秘设计不能直接登记为初始人物知情。')
    return contract
