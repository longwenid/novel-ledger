"""Task-specific briefs generated from shared contracts and domain rules."""
from __future__ import annotations

from .creation import gate_title, value_rules
from .contracts import (BIOGRAPHY_FIELDS, OPENING_VERSION, OPTION_CONTRACT, WORLD_ARCHITECTURE)
from . import stages, world
BRIEFS = {
    'opening_options': '开书任务卡',
    'world_model': '世界与约定简报',
    'volume_outline': '卷纲简报',
    'chapter_outline': '章纲简报',
}


def _check_block(title, lead, rows):
    if not rows:
        return []
    return ['## ' + title, lead, *['- ' + row for row in rows], '']


def opening_options(gate, version=OPENING_VERSION, *, creative_lens=None):
    """A task locator and field contract; creative guidance lives in hatch.md."""
    lines = ['# ' + BRIEFS['opening_options'], '',
             '当前门：%s（%s）' % (gate_title(gate.get('id'), version), gate.get('id')),
             'value：' + value_rules(version, gate.get('id')), '',
             '提交字段：' + OPTION_CONTRACT, '',
             '来源：用 task.json.commands.read 读取完整 required；已选决定见 opening_choices，'
             '本门否决记录见 opening_rejections。',
             '按 result.template.json 填写；检查与提交使用 task.json.commands.check/submit。',
             '字面约定：方案文本与 value 的内容都受默认禁词（账本/入账/回执）约束，'
             '命中会以 literal_policy 拒绝并给出 found 词条（含 options[].value 深层文本）；改写避开，作者可用 lexical 调整规则。',
             '创意说明只在 task.json.guides 指向的 hatch.md，按当前门定位。']
    if creative_lens:
        lines.append('本轮方法标签（按需选用）：' + creative_lens)
    if gate.get('id') == 'genre':
        lines.append('题材目录见 task.json.catalog_path，不复制到任务卡。')
    return '\n'.join(lines)


# The mechanical checks the world dispatch is judged by. The independent world reviewer is gone, so
# these are the actual gates: everything here is enforced by the validator, and nothing that only a
# reader could judge is claimed.
WORLD_SELF_CHECK = (
    'selection_hash 与本任务冻结的选择逐字一致（不一致直接拒）。',
    '每个域的记录都有稳定 id 与 links=[领域:id]，引用的 id 都真实存在。',
    '裸 id 在全部领域间不重复，geography 的地点名不重复——下游按裸 id 和地名引用'
    '（资源 key、站位、位置移动），撞名即歧义，会被 world_id/world_identity 拒且点名撞名记录。',
    '本档位列出的领域每个至少一条实写记录；已选无特殊机制时 mechanisms 必须是空数组。',
    '三条逐字绑定：门里选的位阶表进 powers、硬通货进 economy（分配者写进分配方式）、'
    '格局阶梯每一级有一条同名记录；声明了却没落地会被 world_alignment 拒。',
    '可选深字段写了就必须非空（epoch/carryover/scale/counter_space/survives_scale_up/'
    'reveal_window/survival），不写不影响通过。',
    'premise 与 story_capacity 说清这个世界靠什么持续供料，不写「待补」。',
    '同一份回执里的 contract 逐字保留已选字段，不替作者改决定。',
)


# The seven layers the worldbuilding evidence finds in long-running serials — core idea, power
# ladder, space and planes, epoch history, factions and interests, resources and economy, truth and
# disclosure — plus the surface half (society and everyday life) the same evidence separates from the
# underlying design. Every item names the world section it is written into; no field is invented here.
WORLD_LAYERS = (
    ('核心理念（底层）', (
        ('rules', '世界的底层规则如何影响生产、生活与权力：适用范围、门槛与后果都要能落成场景；'
                  '规则之间不得互相否定。'),
        ('mechanisms', '有特殊机制时：原理/代价/限制/失效条件，外加升级材料从哪来、谁在抢（供料链）；'
                       '已选无特殊机制时保持空数组。'),
    )),
    ('力量阶梯（底层）', (
        ('powers', '位阶阶梯：每条 {name,condition,gain,cost,limit}。'
                   '**门里 world 门选的位阶表（world_tiers）必须逐字进这里**：name/condition/gain/cost/limit '
                   '与作者选定的一字不差，世界可以更长（允许更多高阶记录），但不能少、不能改写。'),
    )),
    ('空间与位面（底层）', (
        ('geography', '空间结构：尺度（可选深字段 scale：城/域/界…）、通行条件、'
                      '以及对立空间（可选深字段 counter_space：入侵面、里世界、异空间）。'
                      '**格局阶梯每一级的 stage 要在本域或 cosmology/factions/powers 里有一条同名记录。**'),
        ('cosmology', '层名 name、谁在 inhabitant、什么法则 law、怎么进 entry。'
                      '**格局尺度到「一界/星海/诸天」时本域必填**（只写到一城一域时可以留空）。'),
    )),
    ('纪元史（底层）', (
        ('history', '只展开影响当前冲突的历史：period 定位处境，event 写当时的问题与人的选择，'
                    'consequence 写谁获利、谁付代价，present_effect 写制度/日常遗留及今天的失效或冲突；'
                    'links 连到受影响的势力、制度与生活，因果可由关联记录共同承载。'
                    'present_effect 若承担逐字绑定，保留原文，细节放其他现有字段；epoch/carryover 按需。'),
    )),
    ('势力与利益（底层）', (
        ('factions', '不同组织或文明的生存方案、资源依赖与不能退让的利益；'
                     '跨卷仍在场的势力写清它靠什么延续（可选深字段 survives_scale_up），'
                     '避免上一卷势力到下一卷作废。'),
        ('characters', '人物基础档案须完整；主角、双主角与群像核心标 importance=core，并写 biography={'
                       + ','.join(BIOGRAPHY_FIELDS) + '} 四项非空文本：过往如何形成当下欲望、内在矛盾、'
                       '关系牵制、行为方式。配角可标 supporting，路人标 minor，不强写长传。'
                       '小传属于设计，不自动成为事实或角色知情；成长以正文证据和当前状态为准。'),
    )),
    ('资源与经济（底层）', (
        ('economy', '硬通货：**门里 world 门选的 resource（name/source/allocator）必须进这里**——'
                    'resource 与声明的 name 逐字相同，且这条记录的文本里要出现声明的 allocator'
                    '（分配者写进分配方式）。再补稀缺点与为它产生的冲突。'),
    )),
    ('真相与披露层（底层）', (
        ('mysteries', '世界的真相与读者认知的推进：披露排期（可选深字段 reveal_window）、'
                      '以及真相揭开之后人物还要面对什么（可选深字段 survival）。'
                      '这一层决定长篇的悬念续航，不要只写一句「幕后有人」。'),
    )),
    ('表层呈现（社会与日常）', (
        ('society', '制度、习惯与执行方式：普通人在这个世界的日常处境，以及它怎样持续产出压力。'),
        ('everyday', '生活细节与器物：能被写进场景的日常，用来给宏大设定落地，不做纯氛围铺陈。'),
    )),
)
WORLD_PIECE_NOTE = ('以下基础绑定与上列已声明的世界架构都由引擎核对，写错会被 world_alignment 拒绝：'
                    '① 门里选的位阶表（world_tiers）逐字进 powers；'
                    '② 门里选的硬通货（world_resource）进 economy，分配者写进分配方式；'
                    '③ 格局阶梯每一级（ladder 的 stage）在本世界有一条同名记录'
                    '（geography/cosmology/factions/powers 任一）。'
                    '另外这些设定是被后续卷纲/章纲消费的：位阶→人物与知情状态、硬通货→章纲资源增量（进漂移账）、'
                    '地图与位面→章纲 places（进位置校验），引用走的是记录的裸 id 与 geography 的地名，'
                    '两者都不与别的记录重复。'
                    '每条都要写成「能用」的具象设定'
                    '（谁、在哪、要什么、付什么代价），不是百科条目；本档位用不上的领域留空数组。')


def _world_piece_lines(sections):
    """The layer skeleton rendered for one dispatch, marking domains this tier does not require."""
    required = set(sections) if sections else None
    lines = []
    for layer, items in WORLD_LAYERS:
        rows = [(name, text) for name, text in items if required is None or name in required]
        if not rows:
            continue
        lines.append('- **%s**' % layer)
        for name, text in rows:
            lines.append('  - %s（%s）：%s' % (name, world.LABELS.get(name, name), text))
    lines.append('- 若 world 门声明 architecture，以下对应字段须逐字保留（直接导入约定按实际声明核验）：')
    lines.extend('  - architecture.%s → %s.%s：%s' % (key, section, field, note)
                 for key, note, section, field in WORLD_ARCHITECTURE)
    return lines


def world_model(previous=(), repair=False, scale=None, sections=None):
    """World plus contract in one dispatch: what the world owes, and what the contract must keep."""
    lines = ['# ' + BRIEFS['world_model'], '',
             '## 世界模型', '把已选方向扩展成能持续产生行动、冲突、代价与后果的环境。'
             '完整记录须有稳定 id（裸 id 全领域不重复）与 links=[领域:id]；同时给 premise、story_capacity 与准确的 selection_hash。'
             '不要写"待补"，写进去的域都要能落到具体场景。', '']
    lines.extend(['## 世界要产出哪些网文可用件（按七层骨架，就用现有字段，不新增字段）',
                  *_world_piece_lines(sections),
                  WORLD_PIECE_NOTE, ''])
    if sections:
        # Same declaration the validator uses: asking for the full twelve domains while the check
        # happens to accept a smaller world is how a micro project ends up writing records nobody
        # reads and repairing four times. The list is the tier's domains plus whatever this opening's
        # own gates declared (currency adds `economy`, ranks add `powers`, a grand scale adds
        # `cosmology`).
        labels = '、'.join('%s（%s）' % (name, world.LABELS.get(name, name)) for name in sections)
        empty = '、'.join(name for name in world.SECTIONS if name not in sections)
        lines.extend(['## 本档位要填的领域', '本项目按体量只需要：' + labels + '。'
                      + ('其余领域（' + empty + '）保留为空数组，不要为凑数写进来；' if empty else '')
                      + '除 mechanisms 外，列出的每个领域至少一条实写记录；'
                        '已选无特殊机制时 mechanisms 必须为空数组，有限机制时至少一条。', ''])
    if scale:
        # A world is read by every later dispatch, so its size is a recurring cost, not a one-off.
        # The twelve domains at "at least one record" is a floor, not a target — and this tier asks
        # for only some of them: a single-volume micro book only needs the institutions and people
        # its one line actually walks through.
        lines.extend(['## 规模要与已选体量相称', '本项目的体量与分卷是：' + scale + '。'
                      '世界架构先保留空间、历史、文明与终极问题的全貌；本书实际涉及的部分展开完整记录，远期背景保留能约束当前选择的骨架，不要求每条背景立即登场；'
                      '完整世界会被后续设计任务读取，扩展记录应确实支持故事。story_capacity 用一句话说清这个世界能撑住多少章、靠什么持续供料。', ''])
    if repair:
        # A repair re-emits the whole candidate, so an unrequested rewrite of untouched records is
        # pure cost: it reopens questions already settled, and the next check spends a round on new
        # material instead of the named defect. What counts as named is decided by the refusal's
        # own findings, which travel with the previous proposal.
        lines.extend(['## 这是返修，不是重写', '上一版候选与逐条拒绝理由都在 previous_proposal 记录里，重新 read 本任务即可取回。'
                      '只改被点名的问题，其余记录与上一版逐字一致；确实要牵动别处时，先只改点名处提交，'
                      '下一轮拒收会点名下一处。'
                      '逐条改完再自查一遍，避免改一处带出另一处不一致（规则互相否定、数字前后对不上、'
                      '某条程序被另一条堵死）。程序会逐条比对：没被点名的记录一旦被改动或删除，回执当场被拒'
                      '（repair_scope）。', ''])
    if previous:
        lines.append('## 已选方向（不得改动）')
        lines.extend('- %s：%s' % (name, text) for name, text in previous)
        lines.append('')
    lines.extend(['## 约定派生字段的准确形状（照此落笔，不要按占位猜类型）',
                  '- contract.world_rules：逐条逐字等于世界 rules 各条记录的 principle，顺序一致（数组）。',
                  '- 顶层 premise 与已选 world_premise 逐字相等（不是扩写或缩写）。',
                  '- 世界架构五项是字段全等绑定：门里声明的 space/history/civilizations/conflict/mystery '
                  '必须逐字写进对应世界记录的指定字段（environment/present_effect/conflicts/consequences/truth），'
                  '是整段相等，不是提及或包含。',
                  '- 世界 characters 里须有一条记录的 id/name/desire/limit 与所选主角逐字相同。',
                  '- contract.entities：每条 {id,name,kind}（kind 用 person/item/place 等）；'
                  '其中必须有一条 id/name/kind=person 与所选主角逐字相同，可另加 desire/limit。',
                  '- contract.volumes：每卷 {id, end}（卷末章号严格递增；卷数=所选档位的 volume_count），'
                  'first 与 word_range 由引擎推导，不手写。',
                  '- initial_resources 每条 {holder,asset,unit,quantity}：holder 必须是 entities 里已登记的实体，'
                  'quantity 是十进制字符串（写 "1200" 不写 1200）。'
                  '后续卷纲/章纲的资源增量只能作用于这里（或既有状态）登记过的坐标——'
                  '本书若要写资源变化（钱、材料、配额），现在就登记起点，不要留空。',
                  '- contract.placements（实体id→地点id）声明开局站位：要写位置移动的实体，'
                  '先在这里登记初始站位；实体须已在 contract.entities 登记，'
                  '地点 id 须先在 contract.places（{id,name}）登记并对应世界 geography 中的地点'
                  '——否则设计链不能建立位置坐标，章纲只能不写该实体的位置变化。',
                  '- 模板里的空字符串占位（如 payoff_plan.ways）代表「待填的数组/结构」：'
                  '按门内已选值原样落入，保持数组是数组，不改成一句话。',
                  ''])
    lines.extend(['## 同一份提交里还要给约定',
                  '按 task.stages 与 payload.also 指定的阶段填写 result.template.json；'
                  '约定逐字保留已选字段，填入 data.contract，不提交选案 options。', ''])
    lines.extend(_check_block('提交前自检（这些是机械校验会直接判的）',
                              '没有独立核验者了；下面每一条提交时都会机械判定，先自己过一遍：', WORLD_SELF_CHECK))
    return '\n'.join(lines)


# The delta groups a chapter outline declares, as the writer must answer them one by one. Five of
# the six state groups come from drift.DELTA_KINDS; `node`/`thread` are the plot group's two item
# kinds, which the same reconciliation checks. Both sets are read from drift.py at render time, so a
# self-check line can never describe a comparison the engine does not perform.
DELTA_HINTS = {
    'resources': '每笔资源从多少到多少与章纲一致，消耗有来源、得到有去处，数量守恒（不足会被拒）。'
                 'actual.from 由引擎投影，不要照抄章纲当既成事实。',
    'places': '人物从哪到哪与章纲一致，移动有过渡与耗时，不出现未登记地点，不瞬移。',
    'knowledge': '每个人只知道他该知道的：章纲写 hinted/suspected/confirmed 的，正文要有来源情节；'
                 '越界知情须从本章正文修掉，不能凭依据或 deviated 改变固定章纲；除 retracted 外不得无由倒退。',
    'characters': '人物变化有 choice（他选了什么）与 cost（付了什么）两个落点；'
                  '章纲声明的变化须在正文落实，漏写就返修；章纲未声明变化时保留原状态。',
    'relations': '章纲 relations 声明的关系变化逐条对上（key 形如 甲>乙:关系名）：to 用稳定短词，'
                 '上一章的 to 就是本章的 from，逐字承接；kept 申报的 to 必须与章纲逐字相同，'
                 '两端的实体须已登记。本章没有关系变化就不申报。',
    'clock': '本章推进天数与章纲一致，不倒退；章号不等于天数，同日续接不必为验收补造过夜。',
    'node': 'plot.nodes 写 seeded/advanced/resolved 的节点，正文里必须真发生：该埋的埋、该收的收；'
            '同一节点不得重复推进或已 resolved 后再推；改做或漏做须诊断并返修本章正文。',
    'thread': 'plot.threads 的线路状态（active/dormant/resolved）与正文一致；'
              '已 resolved 的线路不得重新启用，dormant 的线路要交代它为何搁置。',
    'hook': '本章声明的伏笔动作逐条对上：plant 的那一次要在正文里有读者能看见的具体载体'
            '（一件物、一句话、一个动作），payoff 的那一次是真兑现而不是再提一次；'
            '卷末 required 的必须在本卷内收（引擎在卷内状态链收尾校验），continuity 上的跨卷条目允许仍 open。',
    'disclosure': '本章声明的读者披露逐项给出实际档位和正文引文，不越过章纲，也不默认已经落实。',
}


def self_check_block():
    """Mechanical comparisons and a separate creative reflection in the same writing task.

    Read from the same delta-kind tables the engine reconciles against, so the brief cannot ask for a
    comparison the program does not perform. Reading effect stays explicitly outside that list:
    it uses the existing self_check, without a new score, settlement item or review task.
    """
    from .drift import DELTA_KINDS, ITEM_KINDS
    kinds = list(DELTA_KINDS) + [kind for kind in ('node', 'thread', 'hook', 'disclosure') if kind in ITEM_KINDS]
    rows = [(kind, DELTA_HINTS[kind]) for kind in kinds if kind in DELTA_HINTS]
    if not rows:
        return []
    return ['## 提交前自检（逐项与章纲比对）',
            '本章纲声明了哪些计划增量，drift_check.items 就必须一行不多、一行不少地覆盖它们；'
            '逐项核账写入 drift_check；self_check 补充本章文风落实与实际修订依据，无需重抄核账：',
            *['- %s：%s' % (kind, hint) for kind, hint in rows], '',
            '## 本章阅读效果（创作判断）',
            '在原有 self_check 中结合具体正文说明：读者本章得到了什么，哪种期待得到回应、加深或改变；'
            '可以是情节、情绪、关系、人物理解或生活体验，不要求每章高潮、反转或揭密。'
            '连读相邻章判断是否重复或空转，只有具体问题才局部修正；不另交报告、不设评分或新增核账项。', '']


VOLUME_CHECK_HINTS = (
    'volumes 的 id 与顺序和 payload.volume_ids / contract.volumes 一一对应，不多不少。',
    '每卷汉字数落在 words±tolerance；purpose、arc、climax、exit_state、style.trend 都不能空。',
    'stage 取已选格局阶梯里的一级并逐字一致，按卷序只升不降（直接导入约定未声明阶梯时允许留空）。',
    'node/thread/hook 的 id 全书唯一，不覆盖已批准的 id；node/thread window 落在本卷章号区间内。',
    'hooks 每条 plant 必须落在本卷章号区间；payoff[0] >= plant[1]；越过卷末的必须 continues=true 且 required=false。',
    'resources/places/knowledge/characters 引用的 key/entity 必须已存在于世界模型或既有状态。',
    'relations/reader_knowledge 可选：留空就是「本卷不声明这项终值」，声明了卷末才核对——'
    'relations 的 source/target 须已登记且 to 用稳定短词，reader_knowledge 的 to 取披露档位。',
    '不写逐章 synopsis（那是 chapter_outline 的产物），也不写 brainstorm/selection_reason。',
)
CHAPTER_CHECK_HINTS = (
    'chapters 章号连续，恰好覆盖本卷冻结范围 [first,last]，不多一章不少一章。',
    '每章 synopsis 汉字数落在 words±tolerance；plot.beat、world_refs、style.pov、style.rhythm 不得为空。',
    'resources/places/knowledge/characters/hooks 数组不得省略：没有变化就给空数组。',
    'relations 可选：缺省、null 与空数组同义（本章无关系变化）；声明了就按 {source,target,key,from,to,reason} '
    '逐字承接——上一章的 to 就是本章的 from，首次确立才允许 from=null，to 用稳定短词。',
    'enter 是本章开始时的状态，exit 必须等于 enter 施加本章全部增量后的结果，引擎会自己算一遍比对。',
    '五类增量的 from 承接前序同坐标状态，首次确立才允许 null；to 是变化后的完整值对象'
    '（relations 的 to 是稳定短词）。',
    'node/thread 只能引用本卷卷纲已登记的集合；threads 触碰不改状态可重申 active（reason 写交织方式）；'
    'knowledge 的 to 取 hinted|suspected|misled|confirmed|retracted。',
    'hooks 只有 plant/payoff 两个动作：同一 id 各一次、payoff 不早于 plant、各自落在卷纲窗口内；'
    'hook_refs 承接的 id 必须已经 plant 过。',
)

NATURAL_PROSE_GUIDE = (
    '读材料里 style_anchor 的样本（或生效文风档案——guides 里带档案文件，材料 style.profile 注明档名）'
    '和本卷 style.trend，按那个声线写，不要另外发明规则。'
    '写你知道的事：人物眼前的利益、他在意什么、他不愿明说的事，让细节从使用和忽略中自然出现。'
    '对白让人说话——直说、绕开、言不由衷或沉默都可以，动机不必说透。'
    '用动作和具体物件承载情绪，少用形容词解释感受。'
    '事实与知情边界按章纲固定，措辞和节奏自由展开。'
)


# Directional structure discipline for volume outlines: five requirements that name what a volume
# must *decide*, not numbers a validator counts. The expressiveness already exists in the schema
# (threads.continues, hooks windows, chapter dormant/active); what was missing was the ask, so this
# guide is appended to the volume rule instead of growing the receipt with fields nobody checks.
# No thresholds, no formulas, no platform arithmetic — the mechanically checked half stays in
# VOLUME_CHECK_HINTS, and mixing the two would misstate what the engine actually judges.
VOLUME_STRUCTURE_GUIDE = (
    '结构纪律（方向性要求，提交时无机械判据，落点由作者认可门核看）：'
    '①推进维度——每卷写明本卷落在哪些维度上推进：利益格局/关系/对规则的理解/代价累积，'
    '只换地图、只换对手不算推进；'
    '②每卷结构角色不同——与已交各卷比较本卷的结构职责，自审“最像哪一卷、差异是否机制级”；'
    '若仍是“新地图＋新对手＋旧账全清”的同构形状，换一种结构角色再交（警而不拦：作者点名的形状以作者为准）；'
    '③情节交错——本卷有线多卷时用 threads.continues 与章纲 dormant/active 表达并行与搁置，'
    '写清该线与主线如何相互影响；不强制每卷多线；'
    '④有波澜——turns 要改变后半卷的对抗走向：挫折、反转或代价在 arc/turns 可见，不以同义推进凑数；'
    '⑤卷间不清账——arc 开局承接前一卷的后果，跨卷承诺用 hooks.continues 带入带出，不把上一卷代价清零重来。'
    '卷级转折方法按 guides 的 hatch.md「卷级转折方法」选用。'
)


# A design method, not another receipt or validator. Detailed guidance lives in craft.md.
VOLUME_DESIGN_GUIDE = (
    '\n\n## 卷纲因果推演（先故事，后字段）\n'
    '先读冻结 contract、world_model、opening_choices/opening_basis（若有）、前卷设计与未结承诺；'
    '已生效约定是当前决定，原始选择保留来源，不从摘要重造设定。直接导入项目以约定和实际世界为准。\n'
    '①核心问题：主角本卷想得到什么，什么处境逼他现在行动；从阅读承诺、核心设想、来历与欲望底线取依据。\n'
    '②双方行动：主角怎么做，对手为何主动阻止；把世界规则、资源分配、历史遗留与关系依赖变成具体阻力，'
    '优势必须受已选代价和上限约束，无机制设定不补外挂。\n'
    '③选择与代价：哪里无法两全，主角选什么、失去什么，对手怎样回应；转折从这些行动产生，不按数量配额填。\n'
    '④不可逆后果：选择怎样改变处境、利益、关系或规则理解，后续为何无法原样继续；静卷也可积累关系与认知后果。\n'
    '⑤兑现与收束：回应阶段兑现、期限承诺与终局主题；非终卷留下后果可接，终卷／单卷检查结局，不强造新威胁。\n'
    '再把同一条因果链投影到 purpose/arc/turns/climax、nodes/threads/hooks 与状态终值，'
    '最后核算资源、位置、知情和累计时钟；视角、基调、书名承诺贯穿呈现。'
    '答案写入已有叙述字段，不交额外推演报告或新 JSON 字段；详细方法见 guides 的 craft.md。'
)


def stage(name, payload=None):
    """Cold workers receive the rules of their stage without inheriting controller history."""
    payload = payload or {}
    rules = {
        'opening_options': '按当前门与 result.template.json 交 options，字段约束见任务卡；创意说明见 hatch.md。',
        'world_model': '世界模型与约定同一次提交；本阶段下发的专用简报已含全部规则。',
        'opening_contract': '把已选方向与已核验世界整理为完整约定，严格保留对齐字段，按模板逐字段填写，不增加正文事实。',
        'volume_outline': '交付 volumes：恰好覆盖本批次的每一卷（payload.volume_ids），顺序与 contract.volumes 一致。'
                          '每卷是约 words 汉字的极简卷纲，把这一卷的因果骨架说完（words±tolerance 按性质是每卷总量，不是每段）。'
                          '约定声明 world_ladder 时 stage 从其中取一级，逐字写那一级的 stage 名（直接导入同样适用）；'
                          '按合同卷序只升不降（后一卷的层级序号不得低于前一卷），不写「第一卷」这类编号——'
                          '阶梯每一级在世界模型里都有同名记录，卷纲的 stage 必须对得上。'
                          '已声明 world_architecture 时，arc/turns 承接其长期矛盾、历史后果与文明立场；'
                          '远期真相先以 hooks/window 登记可见线索和揭示窗口，章纲逐步披露，不把作者全知当角色知情。'
                          'purpose 简洁说明这一卷的职责；arc 按因果充分展开开局处境→关键选择→卷末局面，计入整卷字数；'
                          'turns 按实际需要列改变走向的转折，不设次数配额；at 用「开卷」「卷中」「第N章附近」等位置文字；'
                          'climax 写卷末高潮与兑现物；'
                          'nodes 给 {id,kind:main|side|hidden,purpose,ending_condition,required,window:[本卷最早章,本卷最晚章]}；'
                          'threads 给 {id,kind,purpose,ending_condition,required}，跨卷延续的线路加 continues=true；'
                          'resources 给本卷资源大势 {key,from,to,reason}（key 必须已存在于世界模型或既有状态）；'
                          'places 给 {entity,from,to,reason} 的本卷起止；characters 给同样四键，'
                          'to 必须是 {desire,stance,relationship_focus} 的结构化卷末人物状态；'
                          'knowledge 给 {who,topic,from,to,reason}；'
                          'relations 可选（留空=本卷不声明关系终值）：每条 '
                          '{source,target,key,to,reason}，source/target 须已登记且不相等，key 不含 : 与 >，'
                          'to 用稳定短词（章纲增量的 to 与它逐字同源）；'
                          'reader_knowledge 可选（留空=本卷不声明读者认知终值）：每条 {topic,to,reason}，'
                          'to 取披露档位 hinted|suspected|misled|confirmed|retracted；'
                          'hooks 是必填数组（本卷没有伏笔就给空数组，缺字段会被拒）：每条 '
                          '{id,text,plant:[最早章,最迟章],payoff:[最早章,最迟章],required:true|false,continues:true|false}——'
                          'id 全书唯一（与 node/thread 同一命名空间）；'
                          'text 是对读者的具体承诺（哪件物、哪句话、哪桩没交代的事），不写「待补」；'
                          'plant 窗口必须落在本卷章号区间内，两章之间必须有一次 plant；payoff[0] >= plant[1]，'
                          '允许越过卷末，但越过时必须 continues=true 且 required=false；'
                          'required=true 的必须在卷末兑现，引擎在卷内状态链收尾处校验。'
                          '前卷未结伏笔保留首次声明，后卷在 arc 排承接、章纲用原 id 的 hook_refs/payoff，'
                          '不复制 hooks 声明、不重复 plant；清单见材料 hooks。终卷／单卷无需新增跨卷项或新威胁。'
                          'style.trend 必填：用具体文字说清本卷的叙述意图与人物说话方式如何随处境变化；'
                          '作者要求量化时再定对白或句段目标，'
                          '不写「同上」「保持」；可选 style.window 逐项覆盖契约 style_window'
                          '（sentence/paragraph/dialogue/repetition/person），只在对本卷有明确意图时才改。'
                          'clock.advance_days 是本卷总推进天数，clock.to 是卷末主线时钟的绝对累计天数（从初始状态累计，'
                          '不是相对增量）；章纲模拟最后一章时必须达到 clock.to。exit_state 必须非空，用自然语言说明卷末局面，'
                          '仅作创作提示；引擎闭合的是资源/位置/知情/人物与时钟的结构化终值，不验证 exit_state 的语义。'
                          'node/thread/hook id 全书唯一，不覆盖已批准 id。'
                          '不写逐章 synopsis，不写脑暴与选案理由，不写正文。',
        'chapter_outline': '交付 {volume, chapters}：章号连续、恰好覆盖本卷冻结范围 [first,last]。每章给：'
                           'synopsis（words±tolerance 汉字：本章故事内实际发生的事与人物处境）；'
                           'story_events可列实际事件，reader_effect单列读者效果，不能把后者写成角色台词或事实证据；'
                           'timeline可声明稳定scene_id、承接关系与已知分钟区间/期限；未知时省略，不按章号分配天数；'
                           '行动、阻力、选择与后果可以跨章承接，静章可停留于关系或余波；'
                           '写清实际承接，不要求每章六项齐备、即时结算或章末固定留钩。'
                           'plot.beat 一句话说清本章情节变化，plot.nodes=[{node,after:seeded|advanced|resolved,outcome}]、'
                           'plot.threads=[{thread,after:active|dormant|resolved,reason}] 只引用本卷卷纲已登记的 id；'
                           'threads 同时是本章交织申报——本章推进哪条线、以什么方式触碰哪条线'
                           '（轻触不改状态可重申 active，reason 写触碰方式与该线同本章主推进的相互影响）、'
                           '搁置哪条线（dormant+return_by）；不要求每章动所有线，写进本章的线要有申报；'
                           'beats 可选（短句数组）：按读者阅读顺序写叙述推进意图，可含倒叙、插叙或双线交替；'
                           '事件发生时间由 timeline 的显式声明与 clock 核算，场景依赖沿 scenes 的既有协议，不能由拍序改写；'
                           '形状自定——可只写一拍或停在余波，不定数量与事件、不设每拍字数、不套平台爽文公式；'
                           'role 可选（一句话）：写明本章在卷内的结构职责'
                           '（如「调查推进：逼近同一条证据链」）；相邻多章可共同承担调查、战斗、谈判或余波，'
                           '检查各章实际带来的压力、认识、情绪或后果，不要求逐章换职责名；'
                           '卷纲 turns 与 climax 可跨多章展开，role 可说明各章承担的部分，'
                           '不以均质推进凑章；蓝图（材料 blueprint 记录，若在）的骨架与推进维度是分派语言；'
                           'resources=[{key,from,to,reason}]、places=[{entity,from,to,reason}]、'
                           'knowledge=[{who,topic,from,to,reason}]、characters=[{entity,from,to,choice,cost}] 上述四类数组按模板逐项核对，缺省或 null 与空数组同义——'
                           '空数组就是「本章无此类变化」的声明；knowledge 的 to 取 hinted|suspected|misled|confirmed|retracted，'
                           'character 的 to 是 {desire,stance,relationship_focus} 且 choice/cost 缺一不可；'
                           'relations=[{source,target,key,from,to,reason}] 是第五类可选数组（缺省/null/空数组=本章无关系变化）：'
                           'source/target 用已登记实体且不相等，key 是关系名（不含 : 与 >），'
                           'to 用稳定短词，from 首次确立为 null、之后逐字承接上一章的 to；'
                           '关系压力写进场景意图与行动；形成实际关系状态变化时才申报 relations，不为临时情绪造稳定关系增量；'
                           '五类数组的 from/to 填准确前后值对象，不用状态描述字符串代替。'
                           'clock.advance_days 是本章经过的天数，不倒退；'
                           'enter/exit 是状态链的全部依据：enter 列本章开始时每个受动坐标的期望值（承接上一章 exit），'
                           'kind 取 resources|places|knowledge|character|node|thread|clock，key 用该坐标的键'
                           '（人物用实体 id，节点/线路用其 id，clock 用 clock）；'
                           'exit 必须等于 enter 施加本章全部增量后的结果——引擎自己算一遍比对，任一侧缺项即漂移、整份被拒，'
                           '先核实真实前态并列全实际变化，不能用少列坐标来避开核算；'
                           'disclosures 只登记本章实际呈现的线索、误导或确认，按 topic/after 进入认知核账；'
                           '可选 note 说明这次实际披露的节奏意图。仅暂不揭示、没有相关信息呈现时，不为写 note 补一条披露，'
                           '意图放在现有 pacing（如 pacing.note）或 scenes.intent；'
                           '外层谜底与内层真相分别使用稳定 topic，允许间隔多章、外层 confirmed 而内层尚未披露或仍 hinted；'
                           'world_refs 引用真实世界记录：写日常呼吸、关系场面或生活器物的章，'
                           '把要用的 everyday/society/characters 域记录点名；必读材料还含出场人物与直接关联，'
                           '其他设定按冻结世界补读；'
                           'new_entities 内联新人物/地点/物品档案 {id,kind,name,role,desire,limit,knowledge_boundary}，'
                           '人物（kind=person或character）第一次登记就给全；地点和物品不强填人物欲望。'
                           '同一世界人物须沿用正式姓名和身份；称谓放 aliases，不能换 ID 重建同名人物。'
                           '核心人物 importance=core，小传 biography 四字段见世界简报及 editorial.md；'
                           '已有冻结世界小传可直接沿该来源，不重复抄写，不另派档案阶段；'
                           'hooks 是必填数组（本章不埋也不兑就给空数组）：每条 {hook,action:plant|payoff,note}。'
                           '只有 plant 和 payoff 两个动作——plant 创建承诺（引擎按卷纲声明的 payoff[1] 设到期章），'
                           'payoff 兑现承诺；「中途再提一次」不算动作，用 hook_refs 承接已经埋下的承诺。'
                           'hook 必须是本卷卷纲 hooks 声明的 id，或前卷 continues=true 且仍未兑现的 id；'
                           '同一 id 恰好 plant 一次、payoff 一次，payoff 不早于 plant（同章允许 plant 后立刻 payoff，用于短线钩子）；'
                           'plant/payoff 各自必须落在卷纲声明的窗口内；卷末 required=true 的必须已 paid，'
                           'continues=true 的允许仍 open 带入下一卷；hook_refs 里的 id 必须已经 plant 过，未埋就承接会被拒。'
                           'style 必填：pov 与契约 pov 一致（或落在卷纲 style.trend 声明的演进内）、'
                           'rhythm 用具体文字写本章句法与节奏、dialogue_ratio 给 0~1 的目标（可选）、'
                           'notes 写本章例外（如对峙段允许长句）。'
                           'hook_refs/reader_refs/history_refs 声明要承接的旧资料；'
                           'scenes/pacing 为当前章纲的可选字段：分场是场景质感的容器，'
                           '对话场/动作场/日常场等类型写进 label/intent（方向自定），'
                           '需要写手按场展开时给 scenes，不强制每章分场；'
                           'pacing 只接受 end_push（章尾推力：本章结尾以什么把读者推向下一章）'
                           '与 note（其他节奏意图）两个非空文本键，开卷前五章与卷末章建议填 end_push。不写正文。',
        'write': '交 title/完整 prose/summary/具体 self_check 与逐条 drift_check。'
                 '本章纲（chapter_outline）与卷纲材料（volume_outline）都是必读；卷纲节点已按本章及前置依赖筛选，完整卷纲可从 complete_volume_outline 补读：按章纲的拍序、场景与增量落笔，'
                 '不添章纲没有的重大变化，也不漏掉章纲声明要发生的。'
                 '章纲的 beats/role/threads 交织申报/scenes/world_refs 点名是结构意图不是文字模板：'
                 'beats 表达读者阅读顺序，可含倒叙、插叙和双线交替，视角仍沿作者约定；事件时间与场景依赖分别核对，'
                 '不逐拍均匀着墨、不把拍当小标题，表达在事实与知情边界内自由展开。'
                 'drift_check.items 已按章纲的计划增量预填，逐条把 actual 填成正文实际发生的值'
                 '（actual.from 由引擎投影，不是你自报的前态）、status 取 kept|deviated|skipped，'
                 'deviated/skipped 必须写 reason，但只作为待返修诊断，不能入库；evidence.quote 必须是正文原文片段。'
                 'unplanned 用于报告须从正文修掉的计划外变化，不能据此新增事实；本章通过须所有项 kept、unplanned 为空、verdict=clean。'
                 'actual 按种类给形状：resources/places/knowledge/characters 一律 {"from": 可省, "to": 值}——'
                 'resources 的 to 是数值字符串（如 "2"），characters 的 to 是 {desire,stance,relationship_focus}（不得用 after 键），'
                 'knowledge 的 to 是档位，places 的 to 是地点 id；hook 用 {"action": "plant"|"payoff"}，'
                 '节点/线路/读者披露用 {"after": 状态}，clock 用 {"advance_days": n}。'
                 '遵守 word_budget 的本章范围（aim 是目标字数，min/max 是硬界——字数判断只看 word_budget；'
                 'style_anchor 样本的字数只用于文风可比性，不是本章字数目标）；字数不足靠增加事件补足——新的行动、阻力、转折或后果，'
                 '不以描写、重复或对话注水；作者真相、角色知情与读者已见严格区分，披露不越过 disclosure_boundary。'
                 'self_check 用具体表达说明实际视角、人物说话方式与节奏；'
                 'new_entities 必须在本章正文实际提及；名称或已登记 aliases 可自动定位，'
                 '也可交 drift_check.introductions=[{entity:实体ID,evidence:{chapter:本章,quote:原文,start:字符偏移}}]。'
                 '引文须含该实体名称或已登记别名；不能拿无关文字登记人物。'
                 'dialogue_ratio 未声明时不用补比例，已声明时如实核对，不按段落分配对白。'
                 '材料 style.profile 是生效文风档案档名（声线与口癖对照它的档案文件，guides 里带该文件）；'
                 'style.anchor 是当前形状基线（开卷参照或最近已认可章节中位，origin/basis 标明来源）、'
                 'style.window 是本卷生效的容差：'
                 '默认 style_guard=observe 时形状差异仅供观察；作者选 strict 才按容差核验句段与锚点对白比例。'
                 '章纲明确的对白目标与高重复检查仍生效；代词统计只是视角核对线索，不能代替阅读。'
                 '伏笔上 plant 的承诺与 payoff 的兑现都要在正文里落地，drift_check 的 hook 行照实填。'
                 '约定的叙述视角与人称是硬约束：不越出约定的视角范围，也不无标记地切换人称；'
                 '母题靠事件与选择体现，不写成口号；基调不靠形容词报幕。',
        'repair': '读完整基稿、返修问题与前态，交完整合成稿；local 保留成立部分，chapter 重排因果场景。'
                  '不重置修复额度。交付字段与 write 相同：完整 prose、summary、self_check，'
                  '以及逐条覆盖本章纲计划增量的 drift_check（返修后 actual 按最终稿填）。',
        'redesign': '保持已固定章纲的目标、变化与结局，重新组织当前章正文的因果呈现与场景展开；不修改章纲，不推翻已成立事实，不重复填充解释。'
                    '交付字段与 write 相同，修复额度共享；drift_check 仍须逐条覆盖本章纲的计划增量。',
    }
    stages.require_stage(name)
    rule = stages.require_rule(name, rules.get(name))
    merged_dispatch = name == 'volume_outline' and 'chapter_outline' in (payload.get('also') or ())
    if name == 'volume_outline':
        if merged_dispatch:
            # The engine rejects a merged receipt without per-chapter outlines; the brief used to
            # say the opposite ("don't deliver chapters"), which cost a live worker three rounds.
            rule += (' 本批次为合并派工（小体量档把 chapter_outline 并入本任务，不再单独派工）：'
                     'volumes 逐卷给全字段之外，必须在同一回执交付 chapters——'
                     '按 result.template.json 的 chapters 骨架逐章填齐本批次全部卷的章纲，'
                     '每章字段、enter/exit 状态链、hooks 与逐项自检规则与章纲阶段完全相同（见下方逐章自检清单）。')
        else:
            rule += (' 本批次要交的卷与各自章号区间见 payload.volume_outline：volumes 逐卷给全字段，'
                     '不交 chapters（逐章说明由后续 chapter_outline 完成）。')
        if payload.get('repair'):
            rule += (' 这是返修不是重写：只改被点名的问题与偏差行（payload.drift），'
                     '其余卷保持与上一版逐字一致；节点/线路 id 与已批准集合保持一致。')
        # Directional structure discipline rides with every volume dispatch; the author's blueprint
        # and the previous round's reasoned refusal are named only when they exist, so a plain
        # first round reads no phantom requirements.
        rule += ' ' + VOLUME_DESIGN_GUIDE + '\n\n' + VOLUME_STRUCTURE_GUIDE
        blueprint = payload.get('structure_blueprint')
        if isinstance(blueprint, dict) and blueprint.get('name'):
            rule += ('\n\n## 结构蓝图（作者选定：%s）\n'
                     '- 骨架：%s\n- 推进维度：%s\n- 卷间纠缠：%s\n'
                     '- 边界：蓝图只约束结构角色与推进方式，不定事件桥段、非情节模板、无平台公式。'
                     % (blueprint.get('name'), blueprint.get('skeleton'),
                        blueprint.get('drivers'), blueprint.get('echo')))
        design = payload.get('design_blueprint')
        if isinstance(design, dict) and design.get('name'):
            rule += ('\n\n## 设计蓝图（作者选定：%s）\n'
                     '- 文档：%s（%s，随本任务下发；按其映射表与档位按需取条目，先按卷纲因果设计推演再查条目）\n'
                     '- 边界：设计蓝图是设计参考与字段映射来源，不产生执行规则、不自动返工、不解析进校验。'
                     % (design.get('name'), design.get('file'), design.get('version')))
        rejections = payload.get('volume_rejections')
        if rejections:
            lines = ['- 第 %d 轮（涉及卷：%s）：%s'
                     % (row.get('round', 0),
                        '、'.join(v.get('id', '') for v in row.get('volumes') or []),
                        row.get('reason', ''))
                     for row in rejections if isinstance(row, dict)]
            rule += ('\n\n## 上一版卷纲被作者退回（带理由，本版必须回应，不得原样重出）\n'
                     + '\n'.join(lines))
    if name == 'chapter_outline':
        rule += (' 本批次范围见 payload.chapter_outline（volume/first/last/words/tolerance）。')
        if payload.get('repair'):
            if payload.get('from_chapter'):
                rule += ' 从第 %d 章开始重排剩余章纲。' % payload['from_chapter']
            if payload.get('allow_retained_suffix'):
                rule += (' 可先补读 prior_chapter_outlines 核对原后缀，再用 through_chapter 指定最后修改章，chapters 只交从起始章到该章的连续区间；'
                         '后续原章纲由引擎接回并完整核算，衔接或卷末闭合失败时扩大范围，不得省略受影响章节。')
            rule += (' 这是返修不是重写：payload.drift 列出已经发生的偏差，'
                     '只重排受影响的章与后续章，未受影响的章保持上一版逐字一致；'
                     '已经定稿在前章的 enter 值必须沿用引擎投影的真实状态，不要改写历史。')
    if name in ('volume_outline', 'chapter_outline'):
        rule += (' 可交可选 ledger 账目行（每行 {key,value,sum_of|product_of|equals|ratio_of:[整数]}）：'
                 '数字与数量关系一旦写成账目行，提交时机械验算，后续工件同键必须同值；'
                 '不声明就省略字段，不要把观感描述写成账目。')
    if name in ('write', 'repair', 'redesign'):
        rule += ' ' + NATURAL_PROSE_GUIDE
        rule += (' 本章纲是该章的固定契约：正文写完后逐条比对，有偏差就返修本章正文；不能自动改纲或重排后文来迁就偏差。'
                 '章纲确实无法成立时保留候选说明矛盾，交由作者决定是否改纲；漏项/多项都会被 drift_coverage 拒绝；'
                 'scene_context 的 plan_record 引用 chapter_outline，inputs 给准确前态；scene_sources 绑定历史原文版本；'
                 '依赖缺失先补读，不把人物误信当世界真相。')
    time_rule = ''
    if name in ('write', 'repair', 'redesign'):
        time_rule = (' 默认直接从人物行动、对白或场景切入，不在正文前加独立日期或“第一日、第二日”式报日标签，'
                     '也不把每章首句固定成时间播报。需要交代时间时自然融入场景转折；'
                     'state.clock 是内部累计天数，不是章号或必须写出的日期。'
                     '作者明确要求日记体、编年体或日期标记时按约定执行。')
    enhanced = ''
    if payload.get('editorial'):
        enhanced = {'repair': ' 可用 base_hash/patches/repair_note 或 reuse_original 替代 prose；程序合成后按章纲核算。基稿与前态仍必读。',
                    'redesign': ' 可提交版本补丁；仍消耗本章共享重设计额度。'}.get(name, '')
        if name in ('write', 'repair', 'redesign'):
            enhanced += ' 章纲的 beats/pacing 是叙述安排；scenes 的依赖与显式 timeline 分别遵守，不从阅读顺序推算事件先后。'
    memory = ''
    if payload.get('understanding'):
        memory = (' creative_memory 是可修订的理解及原文表达样本，结合反证和适用范围使用；'
                  '不把解释直接当世界事实，也不必模仿样本句式。unavailable_refs 是当前缺失或已失效的旧理解，'
                  '须核对原文或重规划，不照搬失效解释。')
    if name in ('chapter_outline', 'volume_outline') and payload.get('repair'):
        # A design repair re-emits affected rows; rewriting untouched ones is pure cost and reopens
        # questions the state chain already settled.
        rule += (' 返修只改被点名处：未被偏差波及的卷/章保持逐字一致，'
                 '逐条改完再自查一遍 enter/exit 链是否仍然自洽。')
    self_check = self_check_block() if name in ('write', 'repair', 'redesign') else []
    checks = ''
    if name == 'volume_outline':
        blocks = _check_block('提交前自检（这些是机械校验会直接判的）',
                              '没有独立核验者了；下面每一条提交时都会机械判定：', VOLUME_CHECK_HINTS)
        if merged_dispatch:
            blocks += _check_block('逐章自检（合并派工的 chapters 同样机械判定，状态链逐章重放 enter/exit）',
                                   'chapters 缺章、章号不连续或 enter/exit 对不上都会整份被拒：', CHAPTER_CHECK_HINTS)
        checks = '\n'.join(blocks)
    elif name == 'chapter_outline':
        checks = '\n'.join(_check_block('提交前自检（这些是机械校验会直接判的）',
                                        '没有独立核验者了；下面每一条提交时都会机械判定，'
                                        '状态链还会从卷起始真实状态逐章重放你的 enter/exit：', CHAPTER_CHECK_HINTS))
    body = [rule + time_rule + enhanced + memory] + self_check + ([checks] if checks else [])
    tail = ('字段形状按 result.template.json；格式不确定用 check 自检。完整协议和创作指导在 guides，'
            '来源不足时按冻结哈希补读，不读源码猜格式。'
            '字面约定随材料交付（task 材料的 policy 块，默认禁词为 账本/入账/回执）：'
            '本阶段 scope 覆盖的字段含这些词会被 literal_policy 拒绝，落笔前先避开或请作者用 lexical 改规则。')
    return '\n'.join(body) + ('' if body[-1] == '' else ' ') + tail
