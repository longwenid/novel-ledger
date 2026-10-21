"""Current guided opening choices; only the author selects a board option."""
from __future__ import annotations

import copy
from . import contracts
from .contracts import (DEFAULTS, OPENING_VERSION, SCALE_DEFAULT_WINDOW, SCALE_TIERS, SCALE_WINDOW,
                        alignment_for, digest, require, text)

# The one gate set in force. Older protocols (opening/1../5) are refused rather than re-planned:
# a project that declares one is told to reopen under the current protocol, and nothing downstream
# has to keep a second gate order, field table or alignment promise alive.
GATES = (
    ('genre', '题材与阅读承诺'), ('premise', '核心脑洞与世界命题'),
    ('voice', '叙述视角与阅读质地'), ('scale', '体量与分卷'),
    ('world', '世界架构：空间、历史与文明'), ('ladder', '格局路径与终局视野'),
    ('origin', '主角来历与世界联系'), ('edge', '核心优势与成长线'),
    ('protagonist', '主角处境与底线'), ('relationships', '人物关系与立场'),
    ('opposition', '多方对抗与持续冲突'), ('payoff', '阶段兑现与终局回应'), ('title', '书名'),
)
# State-based lookups validate the current protocol before using this gate set.
# Gates the engine answers itself from a table it has already proved satisfiable. A worker must not
# invent them, and no dispatch is spent on them.
SYSTEM_GATES = {OPENING_VERSION: ('scale',)}
# Inputs used by the world/scale derivation rules rather than copied into a contract.
# Direct choices and the protagonist value shape come from CONTRACT_FIELDS.opening.
DERIVATION_INPUTS = {'world': ('world_premise', 'mechanism', 'red_lines'),
                     'scale': ('tier', 'volume_count', 'chapters', 'chapter_window')}
# Brainstorm lenses live in contracts.LENSES; this module only picks and carries them.
LENSES = tuple(label for label, _point, _structure in contracts.LENSES)


def opening_version(state):
    """Which gate set a creation state belongs to.

    A book without an opening state (a contract imported before any gate) reads as the current
    protocol; a state that declares an older protocol is refused with the fix named, not silently
    re-planned under a gate order its choices were never made for.
    """
    if state is None or state == {}:
        return OPENING_VERSION
    require(isinstance(state, dict) and state.get('schema') == 'novel-ledger.creation/' + str(OPENING_VERSION),
            'creation', '仅支持当前开书协议，请以当前协议重开。')
    return OPENING_VERSION


def gates(state):
    opening_version(state)
    return GATES


def gate_ids(version=OPENING_VERSION):
    require(version == OPENING_VERSION, 'creation', '仅支持当前开书协议。')
    return tuple(ident for ident, _title in GATES)


def gate_title(gate_id, version=None):
    return next((title for ident, title in GATES if ident == gate_id), gate_id)

GATE_LENSES = {
    'premise': ('规则博弈', '纪元断层', '世界暗面', '主流正统'),
    'world': ('纪元断层', '生态位垄断', '世界暗面', '长线续航', '主流正统'),
    'ladder': ('非数值成长', '长线续航', '规则博弈'),
    'origin': ('表层锚点', '身份马甲', '纪元断层'),
    'opposition': ('生态位垄断', '规则博弈', '世界暗面'),
}


def lens_index(gate, round_no, version=OPENING_VERSION):
    """Rotate methods suited to this gate."""
    pool = GATE_LENSES.get(gate)
    return LENSES.index(pool[round_no % len(pool)]) if pool else round_no % len(LENSES)


def lens_brief(index):
    """The method handed to the option writer: a bare label is not a method."""
    label, point, structure = contracts.LENSES[index % len(contracts.LENSES)]
    return '本轮创意透镜：' + label + '。' + point + ' 落地要求：' + structure


def begin(source='', version=OPENING_VERSION):
    require(version == OPENING_VERSION, 'creation',
            '开书协议 opening/%s 已不再支持：请以当前协议 opening/%d 开书。' % (version, OPENING_VERSION))
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


# What each gate's value must carry, in the words the option writer reads. One table for the one
# protocol in force; a field a gate never decided does not appear here.
VALUE_RULES = {
    'genre': 'genre 题材与频道落点、reader_promise 读者承诺（爽点是什么、看谁赢谁）、tone 基调',
    'premise': 'novelty 核心脑洞：这个世界比同类多出来的那一条规则/资源/分配方式（≥12字，写规则，不写外挂名字）；'
               'first_cause 第一推动力：过去发生了哪件事、今天还在推什么（≥12字）；'
               'stance 主角与这套规则体系的关系，只能填"顺从"/"利用"/"对抗"；'
               'dark_side 世界恶意的来源，只能填"外神"/"天灾"/"系统"/"上层剥削"/"制度"/"人心"',
    'voice': 'pov 叙述人称与视角范围、voice 语感、style_traits 表达要点数组；scene 必须用该方案的人称写出来',
    'scale': 'tier 档位 ID（引擎按档位表补齐已证明的数字）、chapter_min/chapter_max/chapter_aim、volume_count、chapters、chapter_window（照抄不要改数；总字数区间是派生结果，不用填）',
    'world': 'world_premise 世界前提、mechanism={mode:none或bounded, principle, cost, limits:数组}、'
             'tiers 位阶阶梯数组（每级 {name,condition,gain,cost,limit}，条数按已选档位下限）、'
             'resource 硬通货 {name,source,allocator}、red_lines 禁区数组、'
             'allow_special_mechanism 布尔（必须等于 mode=="bounded"）',
    'ladder': 'scale={opening 第一章可见边界（≥8字）, terminal 终局等级（局部/势力/体系/文明）, '
              'unchanged 跨卷不变的上层结构（≥8字，写清升格为什么不作废已写的卷）}；'
              'ladder 层级数组（每条 {stage,scope,growth,new_rule,cost}，条数按已选档位下限）：'
              'stage 是世界里能落成一条记录的名字（地点/位面/势力/位阶，不是"第一卷"）；'
              'scope 取 局部/一城/一域/一界/星海/诸天 且只升不降；growth 取 地盘/势力/规则/认知/文明，'
              '三级以上至少一级是规则/认知/文明；new_rule 这一级新增或改变的规则、cost 升上去要付的新代价',
    'edge': 'advantage 优势是什么、origin 怎么来、growth 分几层与升级条件、cost 每次使用的代价、ceiling 上限（约定字段 core_edge 直接存这五项）',
    'protagonist': 'id、name、identity 身份与处境、desire 欲望、limit 底线',
    'relationships': 'relationships 具体关系数组，至少一条：写清助力与背叛风险，以及感情线的分量与处理',
    'opposition': 'opposition 主要对抗与逐卷抬高方式（第一卷对手挡着什么利益、每次胜利换来多强的对手、终局面对谁）、story_engine 持续推进的动力',
    'payoff': 'plan={ways 兑现方式数组, cadence 短线兑现密度与章末钩, hooks 卷内高潮位置}（约定字段 payoff_plan 存这份 plan）、'
              'ending 终局兑现的那场胜利、theme 母题、'
              'anchor={deliverable 第 N 章前必须兑现什么（≥12字）, deadline_chapter 最迟章号（纯数字，不超过档位上限定）}',
}
VALUE_RULES['world'] += ('；architecture 世界架构={'
                         + '；'.join(key + ' ' + note for key, note, _section, _field in contracts.WORLD_ARCHITECTURE)
                         + '}，五项为非空文本，保存作者已选的全书设定，完整展开留给世界模型。')
VALUE_RULES['title'] = 'title 可用书名：承诺独特的世界意象或核心看点，可用凝练短名或清晰长名'
GATE_NOTES = {
    'genre': '作者没有给方向时，第一轮先把 GENRE_CATALOG 全类目铺开（十二个男频类目各配一句网文化读者承诺），让作者先挑类目或自定义；作者点了大方向后，再在类目内给 2～3 个具体方案。作者已给方向时直接在方向内出案。',
    'origin': '世界与格局已经确定。本门在魂穿/身穿/本土/其他中给出不同来历，'
              '说明带来的东西为何能介入既有世界矛盾，以及身份代价、谁会起疑与最初知识边界。'
              '不推翻已选历史与机制，不替后面的主角门起名或定职业。',
    'voice': '本门只决定"怎么讲"：人称与视角范围是硬决定，语感是同一门的阅读质地。每个方案的 scene 与 pitch 都用该方案的人称写出来，让作者读到的不是解释，而是这个人称讲出来的样子；不要在本门讨论情节走向。',
    'edge': '本门只决定核心优势与成长线：advantage 优势是什么、origin 怎么得到、growth 分几层与每层升级条件、cost 每次使用的代价、ceiling 上限在哪。写清楚它在开篇三章内第一次怎么用上；不要写成世界观说明或力量体系百科，也不要替作者决定题材。本门排在主角门之前，主角的姓名与身份还没决定：用「主角」指代，不要在本门给他起名、定职业或写编制——本门文本会被约定逐字保留，写进去的名字会与主角门后来选定的人冲突。',
    'protagonist': '本门决定主角身份、处境与底线，并执行反套路命名纪律：姓氏贴世界与阶层（市井用常见姓与俗字，世家才配行辈雅字，别扎堆潇洒姓）、俗字与双字名优先（单字玄乎名是重灾区）、称呼链一次想好（全名→日常称呼→诨名/职衔）、口语测试三遍（放进街坊对白念着像网文签名档就换）。套路组合（潇洒姓×玄乎单字）会以 name_warnings 出现在板面上。',
    'world': '先定全书 architecture，再从中长出位阶与资源。space 写清已知世界、多方居所及通行边界；'
             'history 写历史断层如何影响今天；civilizations 给出不同生存方案、依存与冲突；'
             'conflict 写主角不行动也会持续扩大的根本矛盾；mystery 写终极真相及揭开后的问题。'
             '这些可表现为大陆、星际与多层现实，也可表现为历史时代和现实制度网络，遵守题材与禁区。'
             '每组至少一案保持类型主流的经典形态，靠层次与依存关系做扎实；猎奇不是本门要求。'
             '开局只展示一个切面，世界规模不等于开篇信息量。与 premise 同源，不用更大地名掩盖局部设定。',
    'ladder': '先想终局需要回答什么，再倒推各阶段的可行动范围。scale.opening 是第一章可见切面；'
              'terminal 按实际问题选，宏大可以来自规则、文明或认知而不靠宇宙地图；unchanged 写旧人物与历史后果为何仍有效。'
              '每级 new_rule 同时说明揭开的认知、由谁维持该规则；cost 说明承担的新责任。'
              'stage 沿已有世界发展，允许同一空间内升格，不要求每卷换地图。完整字段和枚举按 value 规则。',
    'opposition': '给各方可理解的目标、依赖和不能退让的利益。opposition 串起眼前对手与长期冲突；'
                  'story_engine 写胜利如何改变资源、联盟或认知并引出下一次行动，避免只把敌人的战力调高。',
    'payoff': '用 plan 安排行动、探索、关系与成长的阶段回报，ending 回答核心脑洞的全书问题并交代人的去向。'
              'anchor 仍给准确早期兑现物与章号；不机械固定三五章打脸，也不以揭开真相代替解决矛盾。',
    'title': '本门只决定书名：提炼独特意象或核心卖点，凝练短名和直述长名都可，贴合已选语感。',
    'premise': '只改世界的一条根规则，并推演它对日常生活、组织利益与文明未来的连锁后果。'
               'novelty 写清新规则及至少两类后果；first_cause 写历史选择为何在此刻失衡；'
               'stance/dark_side 沿枚举填写，但不要强迫所有世界都由幕后黑手操纵。'
               '同组方案用不同的规则因果与终极问题拉开差距，不能只换职业、能力或敌人；'
               '每组至少一案走类型主流的常规路线：根规则可以普通熟悉，靠执行与兑现密度立住，怪异是选项不是默认。'
               '大世界用一场具体事件展示，主角身份留给后门。',
}


def gate_note(version, gate_id):
    return GATE_NOTES.get(gate_id, '')


def value_rules(version, gate_id):
    rule = VALUE_RULES.get(gate_id, '按已选方向给出结构化方案。')
    rule += ' value 只允许这些字段：' + '/'.join(value_fields(gate_id, version)) + '；不得携带其他门的决定或额外字段。'
    return rule


def value_fields(gate, version=OPENING_VERSION):
    """Opening input ownership for one version, derived from the same source used for alignment."""
    fields = []
    for row in contracts.CONTRACT_FIELDS:
        source = contracts.opening_source(row, version)
        if source and source[0] == gate:
            fields.extend(row['shape'] if source[1] is None else (source[1],))
    return tuple(fields) + DERIVATION_INPUTS.get(gate, ())


# The delivery contract for one option: proposals, not arguments. The lens shapes how the option is
# found; it must not appear in what the author reads. The interception list is derived from the live
# method table plus the legacy names: a method renamed in a later protocol must not become a word a
# worker can safely write into a pitch, and options written under the old table must keep being
# rejected for the same reason.
OPTION_CONTRACT = contracts.OPTION_CONTRACT
LEGACY_LENS_WORDS = ('混搭', '倒置', '代价递进', '认知差', '规则推演', '绑定', '闭环', '阶梯', '商业化倒推')
LENS_WORDS = tuple(dict.fromkeys(
    ('透镜', '落地要求', '典型落法') + tuple(row[0] for row in contracts.LENSES) + LEGACY_LENS_WORDS))


def _reject_lens_language(option):
    text = ' '.join(str(option.get(key, '')) for key in ('pitch', 'premise', 'driver', 'tradeoff', 'fit_reason'))
    self_reference = [word for word in LENS_WORDS if word in text]
    require(not self_reference, 'opening_voice', '方案文本不得自述创意方法；透镜只用于构思，不写给作者看。',
            {'found': self_reference, 'recover': '把"某透镜落地"改成这一版具体怎么推进。'})


def _check_scenes(option):
    scenes = option.get('scene')
    require(isinstance(scenes, list) and 2 <= len(scenes) <= 3
            and all(text(s) and len(s.strip()) >= 12 for s in scenes),
            'opening_scene', '每个方案给 2～3 个可落笔的具体画面（每条≥12字）。作者要看到能直接开写的场面。',
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
    """Validate the current opening's owned fields and structured decisions."""
    require(version == OPENING_VERSION, 'creation', '仅支持当前开书协议，请以当前协议重开。')
    require(isinstance(value, dict), 'opening_option', '每个方案须有结构化 value。')
    allowed = value_fields(gate, version)
    unknown = sorted(set(value) - set(allowed))
    require(gate in gate_ids(version) and not unknown, 'opening_option', 'value 只能包含本门负责的字段。',
            {'gate': gate, 'unknown_fields': unknown, 'allowed_fields': list(allowed),
             'recover': '删除额外字段；修改此前决定须 back 返回对应门。'})
    tier_id = ((choices or {}).get('scale') or {}).get('tier')
    tier = next((row for row in SCALE_TIERS if row['id'] == tier_id), None)
    floors = DEFAULTS['world_ladder']
    if gate == 'premise':
        keys = ('novelty', 'first_cause', 'stance', 'dark_side')
        require(all(text(value.get(key)) for key in keys), 'opening_option',
                '核心脑洞需要 novelty/first_cause/stance/dark_side 四项，逐项写清，不留空。',
                {'missing': [key for key in keys if not text(value.get(key))], 'expect': list(keys)})
        for key in ('novelty', 'first_cause'):
            require(len(value[key].strip()) >= 12, 'opening_option',
                    '脑洞的 %s 至少 12 字：一句话说不清新增了什么规则/资源，就还没有脑洞。' % key,
                    {'field': key, 'got': value[key], 'recover': '写清这条规则替世界新增了资源、分配方式还是代价。'})
        require(value['stance'] in contracts.STANCES, 'opening_option',
                'stance 只能是顺从/利用/对抗之一：主角与这套规则体系的关系要能一眼看懂。',
                {'valid': list(contracts.STANCES), 'got': value['stance']})
        require(value['dark_side'] in contracts.DARK_SIDES, 'opening_option',
                'dark_side 只能取已登记的世界恶意来源。',
                {'valid': list(contracts.DARK_SIDES), 'got': value['dark_side'],
                 'recover': '外部不可抗力取外神/天灾/系统，人心与制度取上层剥削/制度/人心。'})
        placeholders = [word for word in ('待补', '暂定', '同上', '略')
                        if any(word in value[key] for key in keys)]
        require(not placeholders, 'opening_option', '脑洞四问不接受占位词，必须写实际内容。',
                {'found': placeholders})
    elif gate == 'origin':
        forms = ('魂穿', '身穿', '本土', '其他')
        require(value.get('family') in forms, 'opening_option', '来历方向须是这四个之一。',
                {'valid_families': list(forms), 'got': value.get('family'),
                 'recover': 'family 填方向，具体写法写进 arrival；四个方向之外的说法归"其他"，并在 arrival 里说清机制。'})
        require(all(text(value.get(k)) for k in ('arrival', 'cost')), 'opening_option',
                '来历方案需要"怎么来、带来了什么"与"代价或麻烦"两句。')
    elif gate == 'genre':
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
        _validate_world_structures(value, tier_id, floors)
        fields = tuple(row[0] for row in contracts.WORLD_ARCHITECTURE)
        frame = value.get('architecture')
        require(isinstance(frame, dict) and set(frame) == set(fields)
                and all(text(frame.get(key)) for key in fields), 'opening_option',
                '世界架构须完整声明空间、历史、文明、持续矛盾与终极谜题。',
                {'expected_fields': list(fields), 'got': frame})
    elif gate == 'ladder':
        _validate_ladder(value, tier_id, floors)
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
        _validate_promise_anchor(value, tier, floors)
    elif gate == 'title':
        require(text(value.get('title')), 'opening_option', '书名方案需要可用的书名。')


def _validate_world_structures(value, tier_id, floors):
    """opening/5's world gate hands the world model two things it must keep verbatim.

    The ladder and the hard currency used to be prose inside `world_premise`, and the world dispatch
    re-invented them — the drift this redesign exists to remove. Structured here, the same rows are
    checked again against the world model's records (`world.validate`), so the gate's decision is the
    only version of it.
    """
    tiers = value.get('tiers')
    require(isinstance(tiers, list) and tiers, 'opening_option',
            '世界方案需要位阶阶梯 tiers：读者看得见的台阶，逐级给字段。')
    minimum = floors['tier_min'].get(tier_id, 3)
    require(len(tiers) >= minimum, 'opening_option',
            '本档位至少要 %d 级位阶：台阶太少，读者看不到可预期的成长。' % minimum,
            {'tier': tier_id, 'minimum': minimum, 'got': len(tiers)})
    names = []
    for row in tiers:
        _require_keys(row if isinstance(row, dict) else {}, ('name', 'condition', 'gain', 'cost', 'limit'), '位阶条目')
        require(isinstance(row, dict) and set(row) == {'name', 'condition', 'gain', 'cost', 'limit'},
                'opening_option', '位阶条目只能有 name/condition/gain/cost/limit 五个字段。',
                {'got': sorted(row) if isinstance(row, dict) else row})
        # A one-character rank name binds a one-character record: the binding would be satisfied by
        # coincidence, not by the author having named a rung (found by the adversarial review).
        require(len(row['name'].strip()) >= 2, 'opening_option',
                '位阶名称至少 2 个字：一个字的名字会让世界模型里的同名记录变成巧合。',
                {'got': row['name']})
        names.append(row['name'])
    require(len(names) == len(set(names)), 'opening_option', '位阶名称不能重复。', {'names': names})
    resource = value.get('resource')
    require(isinstance(resource, dict) and set(resource) == {'name', 'source', 'allocator'}
            and all(text(resource.get(key)) for key in ('name', 'source', 'allocator')),
            'opening_option', '硬通货需要 name 名称、source 来源、allocator 分配者三项，不能留空。',
            {'got': resource})
    short = [key for key in ('name', 'source', 'allocator') if len(resource[key].strip()) < 2]
    require(not short, 'opening_option',
            '硬通货的名称、来源与分配者各至少 2 个字：单字会被记录文本偶然命中，绑定就不再是证据。',
            {'short': short, 'got': resource})


def _validate_ladder(value, tier_id, floors):
    """opening/5's 格局 gate: a countable ladder that widens, changes something, and cannot void itself."""
    scale = value.get('scale')
    require(isinstance(scale, dict) and set(scale) == {'opening', 'terminal', 'unchanged'}
            and all(text(scale.get(key)) for key in ('opening', 'terminal', 'unchanged')),
            'opening_option', '格局门需要 scale={opening 可见边界, terminal 终局等级, unchanged 不变的上层结构}。',
            {'got': scale})
    require(scale['terminal'] in contracts.WORLD_TERMINALS, 'opening_option',
            'terminal 只能取终局等级表里的值。',
            {'valid': list(contracts.WORLD_TERMINALS), 'got': scale['terminal']})
    for key in ('opening', 'unchanged'):
        require(len(scale[key].strip()) >= 8, 'opening_option',
                'scale.%s 至少 8 字：边界与「升格为什么不让前面的卷作废」都要写实。' % key,
                {'field': key, 'got': scale[key]})
    rows = value.get('ladder')
    require(isinstance(rows, list) and rows, 'opening_option', '格局门需要 ladder 层级数组。')
    minimum = floors['stage_min'].get(tier_id, 3)
    require(len(rows) >= minimum, 'opening_option',
            '本档位至少要 %d 级格局阶梯。' % minimum,
            {'tier': tier_id, 'minimum': minimum, 'got': len(rows)})
    seen, ranks, growths = set(), [], []
    for row in rows:
        _require_keys(row if isinstance(row, dict) else {},
                      ('stage', 'scope', 'growth', 'new_rule', 'cost'), '格局层级')
        require(isinstance(row, dict) and set(row) == {'stage', 'scope', 'growth', 'new_rule', 'cost'},
                'opening_option', '层级条目只能有 stage/scope/growth/new_rule/cost 五个字段。',
                {'got': sorted(row) if isinstance(row, dict) else row})
        require(row['scope'] in contracts.WORLD_SCOPES, 'opening_option',
                'scope 只能取空间尺度表里的值，且写成世界里的名字。',
                {'valid': list(contracts.WORLD_SCOPES), 'got': row['scope'], 'row': row})
        require(row['growth'] in contracts.WORLD_GROWTHS, 'opening_option',
                'growth 只能取「这一级变大的是什么」表里的值。',
                {'valid': list(contracts.WORLD_GROWTHS), 'got': row['growth'], 'row': row})
        require(len(row['stage'].strip()) >= 2, 'opening_option',
                '层级名至少 2 个字：它在世界模型里要落成一条同名记录，一个字的名字只是巧合。',
                {'got': row['stage']})
        require(row['stage'] not in seen, 'opening_option', '格局层级名不能重复。', {'stage': row['stage']})
        seen.add(row['stage'])
        ranks.append(contracts.WORLD_SCOPES.index(row['scope']))
        growths.append(row['growth'])
    require(ranks == sorted(ranks), 'opening_option',
            '格局阶梯的空间尺度只能只升不降：格局不能越写越小。',
            {'scopes': [row['scope'] for row in rows], 'order': list(contracts.WORLD_SCOPES)})
    if len(rows) >= 3:
        require(any(growth in ('规则', '认知', '文明') for growth in growths), 'opening_option',
                '三级以上的阶梯至少要有一级变大的是规则、认知或文明，否则只是换地图。',
                {'growths': growths, 'recover': '把其中一级的 growth 改成规则/认知/文明，并写清这一级新增的规则与代价。'})
    terminal = scale['terminal']
    needs = {'文明': ('文明',), '体系': ('规则',), '势力': ('势力',)}.get(terminal)
    if needs:
        require(any(growth in needs for growth in growths), 'opening_option',
                '终局等级与阶梯对不上：%s 需要在阶梯里有一级 growth 是 %s。' % (terminal, '/'.join(needs)),
                {'terminal': terminal, 'needs': list(needs), 'growths': growths})
    else:
        require(tier_id in ('t0', 't1'), 'opening_option',
                '终局只到「局部」只适用于微型/短篇档位；长篇的终局要写在世界之上的等级。',
                {'tier': tier_id, 'terminal': terminal})


def _validate_promise_anchor(value, tier, floors):
    """The payoff anchor is the counterweight to a grand world: one promise with a chapter deadline.

    Evidence (validation/research-brainstorm-trends.md §4) puts the reader-verifiable window around
    the first 100k characters; the ladder's own floor is the tier's chapter window when that is
    tighter. `deadline_chapter` is digits so the check is arithmetic, not interpretation.
    """
    anchor = value.get('anchor')
    require(isinstance(anchor, dict) and set(anchor) == {'deliverable', 'deadline_chapter'}
            and all(text(anchor.get(key)) for key in ('deliverable', 'deadline_chapter')),
            'opening_option', '爽点门需要 anchor={deliverable 第 N 章前兑现什么, deadline_chapter 最迟章号}。',
            {'got': anchor})
    require(len(anchor['deliverable'].strip()) >= 12, 'opening_option',
            'anchor.deliverable 至少 12 字：写清世界再大也必须先兑现的那件事。', {'got': anchor['deliverable']})
    deadline = anchor['deadline_chapter'].strip()
    require(deadline.isdigit() and int(deadline) > 0, 'opening_option',
            'anchor.deadline_chapter 用纯数字写最迟章号（例：28），不写「第28章」这类文字。',
            {'got': anchor['deadline_chapter']})
    cap = floors['anchor_max_chapter'] if tier is None else min(floors['anchor_max_chapter'], tier['chapter_window'][1])
    require(int(deadline) <= cap, 'opening_option',
            '主题锚点最迟章不能超过 %d：宏大要靠前期可验证的兑现撑着。' % cap,
            {'cap': cap, 'got': deadline, 'tier': (tier or {}).get('id')})


def _require_keys(value, keys, label):
    """A structured decision states every declared key, not a paragraph the engine cannot check."""
    missing = [key for key in keys if not text(value.get(key))]
    require(not missing, 'opening_option', label + '需要逐项写清的结构化字段，不能留空或写成自由段落。',
            {'missing': missing, 'expect': list(keys)})


def name_warnings(gate, options):
    """Advisory flags for AI-cliché protagonist names; the author's lexical rule stays the hard ban.

    Model-produced names cluster on 潇洒姓×玄乎单字, and a real run kept reusing one rare char
    across new names. The board carries the warning so the author sees it with the option; the
    choice stays the author's (the v3 line proved warning-not-blocking is the right severity).
    """
    warnings = []
    if gate['id'] != 'protagonist':
        return warnings
    for option in options:
        name = str((option.get('value') or {}).get('name') or '')
        given = name[1:]
        if len(name) == 2 and name[0] in contracts.CLICHE_SURNAMES and given in contracts.CLICHE_GIVEN:
            warnings.append({'option': option.get('id'), 'code': 'protagonist_name_cliche',
                             'message': '「%s」是 AI 起名重灾组合（潇洒姓×玄乎单字），读者一眼批量脸；'
                                        '按主角门的命名纪律换贴世界与阶层的名字。' % name})
    return warnings


def premise_warnings(gate, options):
    """Advisory flags for a core idea built on a setting the current headliners already own.

    Systems, sequences, 克系+民俗, 无限流 and 幕后黑手 are public settings: free to use, and therefore
    worth nothing as a novelty claim (validation/research-brainstorm-trends.md §1.2). The warning
    names the collision and asks what this world gained; it never blocks a choice — same severity as
    the protagonist-name warning, for the same reason: the author decides.
    """
    warnings = []
    if gate.get('id') != 'premise':
        return warnings
    for option in options:
        value = option.get('value') if isinstance(option.get('value'), dict) else {}
        text_value = ' '.join(str(value.get(key, '')) for key in ('novelty', 'first_cause'))
        found = [word for word in contracts.SETTING_CLICHES if word in text_value]
        if found:
            warnings.append({'option': option.get('id'), 'code': 'premise_public_setting',
                             'message': '「%s」是被头部作品占位的公共设定组合，读者会当熟面孔：novelty 必须写清'
                                        '这个世界因此新增的规则/资源/分配方式，而不是这套设定本身。'
                                        '提示不拦选择：正统方向写清自己的增量即可，不必为避开它翻新设定。' % '、'.join(found)})
    return warnings


def offer(state, data):
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
        require(text(option.get('pitch')) and len(option['pitch'].strip()) <= 40,
                'opening_option', '方案需要 pitch：一句能记住的话（≤40字）。')
        _reject_lens_language(option)
        _check_scenes(option)
        validate_value(gate['id'], option.get('value'), version, selected(state))
    _check_driver_shape(options)
    require(all(len({o[k] for o in options}) == len(options) for k in ('id', 'title', 'premise', 'driver')),
            'opening_diversity', '方案应有实质差异，不能只换标签或措辞。')
    state = copy.deepcopy(state)
    board = {'gate': gate, 'round': state['round'], 'basis': basis(state), 'options': copy.deepcopy(options)}
    warnings = name_warnings(gate, options)
    if warnings:
        board['name_warnings'] = warnings
    setting = premise_warnings(gate, options)
    if setting:
        board['premise_warnings'] = setting
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


def _field_groups(choices, version=OPENING_VERSION):
    """Project each decision from its declared owner, never merge entire option values.

    Ownership comes directly from CONTRACT_FIELDS; a gate cannot overwrite another gate's decision.
    """
    expected = {}
    for row in contracts.CONTRACT_FIELDS:
        if row['key'] in contracts.DERIVED_FIELDS:
            continue
        source = contracts.opening_source(row, version)
        if source and source[0] in choices:
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
    for gate in ids:
        validate_value(gate, choices[gate], version, choices)
    expected, derived, authored = _field_groups(choices, version)
    expected = {key: value for key, value in expected.items() if key in alignment_for(version) and key not in derived}
    groups = (set(expected), derived, set(authored))
    require(set().union(*groups) == set(alignment_for(version))
            and not any(groups[i] & groups[j] for i in range(len(groups)) for j in range(i + 1, len(groups))),
            'alignment_schema', '对齐字段表与约定 schema 不一致，须同时更新。')
    for key, value in expected.items():
        require(key in contract, 'opening_alignment', '约定缺少本门已选字段：' + key,
                {'key': key, 'recover': '按模板补齐该字段，并逐字保留作者选择。'})
        require(contract.get(key) == value, 'opening_alignment', '最终约定改变了用户选择：' + key,
                {'key': key, 'rule': '逐字相等；不是包含、缩写或改写', 'expect': value, 'got': contract.get(key)})
    require(len(contract['volumes']) == choices['scale']['volume_count'], 'opening_alignment', '分卷数量与用户选择不一致。',
            {'rule': '卷数须等于所选体量档位的 volume_count', 'expect': choices['scale']['volume_count'],
             'got': len(contract['volumes']), 'source': 'opening_choices.scale'})
    tier = next((row for row in SCALE_TIERS if row['id'] == choices['scale']['tier']), None)
    require(tier is not None, 'opening_alignment', '体量档位不在档位表中。', {'tier': choices['scale'].get('tier')})
    chapters = contract['volumes'][-1]['end']
    require(tier['chapter_window'][0] <= chapters <= tier['chapter_window'][1], 'opening_alignment',
            '全书章数与所选体量档位不相容。',
            {'tier': tier['id'], 'chapters': chapters, 'chapter_window': tier['chapter_window'],
             'recover': '把卷末章号落在该档区间内，或 back 重选体量档位。'})
    forbidden = choices['world']
    require(all(line in contract['red_lines'] for line in forbidden['red_lines']), 'opening_alignment', '不能丢掉已选禁区。',
            {'missing': [line for line in forbidden['red_lines'] if line not in contract['red_lines']],
             'rule': '已选禁区逐条逐字保留在 red_lines 里，可增不可减'})
    protagonist = choices['protagonist']
    require(any(e['id'] == protagonist['id'] and e['name'] == protagonist['name'] and e['kind'] == 'person' for e in contract.get('entities', [])), 'opening_alignment', '最终约定必须保留所选主角身份。',
            {'rule': 'entities 里须有一条记录的 id/name/kind=person 与所选主角逐字相同',
             'expect': {'id': protagonist['id'], 'name': protagonist['name'], 'kind': 'person'},
             'source': 'opening_choices.protagonist'})
    require(contract['world_rules'] == [r['principle'] for r in world['rules']], 'opening_alignment', '约定世界规则须来自已独立核验的世界。',
            {'rule': 'world_rules 逐条逐字等于已核验世界 rules 各条的 principle，顺序一致',
             'expect': [r['principle'] for r in world['rules']], 'got': contract.get('world_rules')})
    require(not contract.get('initial_knowledge'), 'opening_alignment', '世界隐秘设计不能直接登记为初始人物知情。')
    return contract
