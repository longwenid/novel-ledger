"""Task-specific briefs generated from shared contracts and domain rules."""
from __future__ import annotations

from .creation import gate_note, gate_title, value_rules
from .catalog import GENRE_CATALOG, OPENING_DIRECTION, OPENING_DIRECTION_GATES
from .contracts import (OPENING_VERSION, OPTION_CONTRACT, WORLD_ARCHITECTURE)
from . import catalog, stages, world
BRIEFS = {
    'opening_options': '开书方案简报',
    'world_model': '世界与约定简报',
    'volume_outline': '卷纲简报',
    'chapter_outline': '章纲简报',
}


def direction_block(gates=()):
    """The house default the current gate set aims at, rendered for the worker drafting this dispatch.

    The gate count belongs to the project's own opening version, so nothing here names a number: the
    per-gate emphasis is read off the declared table for whichever gates this dispatch asks about.
    It is a default, not a constraint: the brief says so next to the rules, because a worker that
    treats the market lean as a requirement would refuse an author who wants something else.
    """
    lines = ['## 默认方向（起点/番茄男频长篇网文）',
             '按这些做法给方案；作者原话或已选方向与它冲突时，一律以作者为准，本方向不是硬要求。', '']
    lines.extend('- ' + rule for rule in OPENING_DIRECTION)
    for gate in gates:
        emphasis = OPENING_DIRECTION_GATES.get(gate)
        if emphasis:
            lines.append('- ' + emphasis)
    lines.append('')
    return lines


def _check_block(title, lead, rows):
    if not rows:
        return []
    return ['## ' + title, lead, *['- ' + row for row in rows], '']


def opening_options(gate, lens_brief, previous=(), version=OPENING_VERSION):
    """The brief for one gate: what this gate decides, how to vary it, and what to hand back."""
    lines = ['# ' + BRIEFS['opening_options'], '',
             '## 本门：%s（%s）' % (gate_title(gate.get('id'), version), gate.get('id')), '',
             'value 字段：' + value_rules(version, gate.get('id')), '']
    note = gate_note(version, gate.get('id'))
    if note:
        lines.extend(['## 本门的交付要求', note, ''])
    if gate.get('id') == 'genre' and not previous:
        # The catalog is a chat step, not the receipt: offer() takes 2~3 options, so the
        # controller shows this table to the author first and the receipt deepens the named
        # direction. Inlining both sides of that instruction here keeps one authority.
        lines.extend(['## 全类目目录（作者未给方向时先用它收方向）',
                      '主控先在对话里把下面十二个类目铺给作者（原文照抄即可），收一句方向或自定义；',
                      '本任务回执不列全目录——按作者点名的类目给 2～3 个深化方案，每案写该类目下的具体落点：独特阅读体验、核心冲突的可能入口与早期回报；人物身份留给后门：',
                      *['- %s：%s' % (name, hook) for name, hook in GENRE_CATALOG],
                      '作者已给方向时跳过铺目录，直接在方向内出案。', ''])
    if previous:
        lines.append('## 已选方向（不要推翻，只在此之上给方案）')
        lines.extend('- %s：%s' % (name, text) for name, text in previous)
        lines.append('')
    lines.extend(direction_block([gate.get('id')]))
    lines.extend(['## 本轮创意透镜（用来想，不要写进方案文本）', lens_brief, ''])
    lines.extend(['## 换组纪律（本轮若是因为换组重新生成）',
                  '- 新一组必须与被拒的旧组方向实质不同：不得换名、改写收益或微调细节冒充新组；',
                  '- 吸收作者随换组补充的偏好（「格局太小」就把格局拉高一级：从个人困局追到历史成因、'
                  '规则冲突与文明选择，不只放大地名；「太怪、要正常」就回到类型主流的经典框架——'
                  '回到常规同样是实质不同的新组，不是偷懒）；',
                  '- 已拒方向见 opening_rejections 记录，逐条避开其思路而不只是避开其措辞。', ''])
    lines.extend(['## 交付契约', OPTION_CONTRACT])
    lines.append('')
    lines.append('完整方法表与选项格式见 guides 里的文件；本简报已含本门所需规则，不必为格式再读全文。')
    lines.append('')
    lines.append('读取纪律：先执行一次无参数 read 把必读一次拿齐（已交过的会被跳过并列名）；'
                 '确需某份材料再 read --record 名称，不逐条拉取、不重复拉取。'
                 '主干在同一会话连跑多门时另有豁免：上一门的 read 返回 records_hash 与本门相同、'
                 '且本门简报未新增必读记录，可跳过本次 read 直接写回执（read 返回里带 records_hash）。')
    lines.append('')
    lines.append('路径自检：task.json 的 commands/guides 由当前安装渲染。先确认其中的解释器与脚本存在再执行；'
                 '若不存在，回报主控重新 advance 刷新任务视图，不要自行改写命令，也不要假定某条路径失效。')
    lines.append('')
    lines.append('格式自检：写回执前用 `check` 试算（把候选 JSON 从标准输入管道进去，如 '
                 '`python CLI --project PROJECT check < 候选.json`）。它按提交同一套校验运行但不入库，'
                 '会直接告诉你缺哪个字段、哪个枚举不对。**不要为了确认格式去读引擎源码**——那会白花上下文，'
                 'check 的回答就是权威。')
    return '\n'.join(lines)


# The mechanical checks the world dispatch is judged by. The independent world reviewer is gone, so
# these are the actual gates: everything here is enforced by the validator, and nothing that only a
# reader could judge is claimed.
WORLD_SELF_CHECK = (
    'selection_hash 与本任务冻结的选择逐字一致（不一致直接拒）。',
    '每个域的记录都有稳定 id 与 links=[领域:id]，引用的 id 都真实存在。',
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
        ('characters', '主角及关键人物的欲望、底线、所属秩序与知识边界；成长改变行动范围，也改变关系与责任。'),
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
                    '地图与位面→章纲 places（进位置校验）。所以每条都要写成「能用」的具象设定'
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


def world_model(lens_brief=None, previous=(), repair=False, scale=None, sections=None):
    """World plus contract in one dispatch: what the world owes, and what the contract must keep."""
    lines = ['# ' + BRIEFS['world_model'], '',
             '## 世界模型', '把已选方向扩展成能持续产生行动、冲突、代价与后果的环境。'
             '完整记录须有稳定 id 与 links=[领域:id]；同时给 premise、story_capacity 与准确的 selection_hash。'
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
        # material instead of the named defect.
        lines.extend(['## 这是返修，不是重写', '上一版世界与逐条问题都在 previous_proposal 里。只改被点名的问题，'
                      '其余记录保持与上一版逐字一致；不要借返修顺手改写没被点名的部分。'
                      '逐条改完再自查一遍，避免改一处带出另一处不一致（规则互相否定、数字前后对不上、'
                      '某条程序被另一条堵死）。程序会逐条比对：没被点名的记录一旦被改动或删除，回执当场被拒'
                      '（repair_scope）。', ''])
    if previous:
        lines.append('## 已选方向（不得改动）')
        lines.extend('- %s：%s' % (name, text) for name, text in previous)
        lines.append('')
    lines.extend(direction_block(('world', 'ladder', 'premise', 'opposition', 'payoff', 'protagonist')))
    lines.extend(['## 同一份提交里还要给约定', OPTION_CONTRACT,
                  '约定必须逐字保留已选字段；模板里 contract 一节的字段骨架照填。', ''])
    lines.extend(_check_block('提交前自检（这些是机械校验会直接判的）',
                              '没有独立核验者了；下面每一条提交时都会机械判定，先自己过一遍：', WORLD_SELF_CHECK))
    return '\n'.join(lines)


# The delta groups a chapter outline declares, as the writer must answer them one by one. Four of
# the five state groups come from drift.DELTA_KINDS; `node`/`thread` are the plot group's two item
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
    """The chapter outline's declared deltas, turned into a line-by-line comparison the writer answers.

    Read from the same delta-kind tables the engine reconciles against, so the brief cannot ask for a
    comparison the program does not perform. The old rubric here quoted a reviewer's checks; with the
    review stages removed, the thing a producer is judged by is exactly this list.
    """
    from .drift import DELTA_KINDS, ITEM_KINDS
    kinds = list(DELTA_KINDS) + [kind for kind in ('node', 'thread', 'hook', 'disclosure') if kind in ITEM_KINDS]
    rows = [(kind, DELTA_HINTS[kind]) for kind in kinds if kind in DELTA_HINTS]
    if not rows:
        return []
    return ['## 提交前自检（逐项与章纲比对）',
            '本章纲声明了哪些计划增量，drift_check.items 就必须一行不多、一行不少地覆盖它们；'
            '逐项核账写入 drift_check；self_check 补充本章文风落实与实际修订依据，无需重抄核账：',
            *['- %s：%s' % (kind, hint) for kind, hint in rows], '']


VOLUME_CHECK_HINTS = (
    'volumes 的 id 与顺序和 payload.volume_ids / contract.volumes 一一对应，不多不少。',
    '每卷汉字数落在 words±tolerance；purpose、arc、climax、exit_state、style.trend 都不能空。',
    'stage 取已选格局阶梯里的一级并逐字一致，按卷序只升不降（直接导入约定未声明阶梯时允许留空）。',
    'node/thread/hook 的 id 全书唯一，不覆盖已批准的 id；node/thread window 落在本卷章号区间内。',
    'hooks 每条 plant 必须落在本卷章号区间；payoff[0] >= plant[1]；越过卷末的必须 continues=true 且 required=false。',
    'resources/places/knowledge/characters 引用的 key/entity 必须已存在于世界模型或既有状态。',
    '不写逐章 synopsis（那是 chapter_outline 的产物），也不写 brainstorm/selection_reason。',
)
CHAPTER_CHECK_HINTS = (
    'chapters 章号连续，恰好覆盖本卷冻结范围 [first,last]，不多一章不少一章。',
    '每章 synopsis 汉字数落在 words±tolerance；plot.beat、world_refs、style.pov、style.rhythm 不得为空。',
    'resources/places/knowledge/characters/hooks 数组不得省略：没有变化就给空数组。',
    'enter 是本章开始时的状态，exit 必须等于 enter 施加本章全部增量后的结果，引擎会自己算一遍比对。',
    '四类增量的 from 承接前序同坐标状态，首次确立才允许 null；to 是变化后的完整值对象。',
    'node/thread 只能引用本卷卷纲已登记的集合；knowledge 的 to 取 hinted|suspected|misled|confirmed|retracted。',
    'hooks 只有 plant/payoff 两个动作：同一 id 各一次、payoff 不早于 plant、各自落在卷纲窗口内；'
    'hook_refs 承接的 id 必须已经 plant 过。',
)

NATURAL_PROSE_GUIDE = (
    '首章按作者文风写出完整实稿定调；认可后以 style_anchor 原文样本承接声线，结合本卷、本章 style 随处境调整表达。'
    '先抓住人物眼前的利益、主观关注与不愿明说的事，细节从他的使用、在意或忽略中来。'
    '对白受关系和目的驱动，可以直说、绕开、言不由衷或沉默，允许动机与成长暂未说透。'
    '事实结果与知情边界固定，措辞、心理距离、停顿和句段可自由展开；保留有作用的心理、余波与静章。'
    '优先用动作与具体细节呈现感受，保留有辨识作用的修饰；重复解释与同感受的形容词堆叠就近删改。'
    '碎短句割裂动作、思绪或因果时合为完整句，需要节拍时保留短句。'
    '变化与必要数量须在正文中成立，核账解释留回执；本次写作或返修内连读当前段落，只修具体失真处。'
)


def stage(name, payload=None):
    """Cold workers receive the rules of their stage without inheriting controller history."""
    payload = payload or {}
    rules = {
        'opening_options': '按本门字段给 2～3 个用法各异的方案；本阶段下发的专用简报已含全部规则，'
                           '本行只用于保证每个已登记阶段都有规则。',
        'world_model': '世界模型与约定同一次提交；本阶段下发的专用简报已含全部规则。',
        'opening_contract': '把已选方向与已核验世界整理为完整约定，严格保留对齐字段，按模板逐字段填写，不增加正文事实。',
        'volume_outline': '交付 volumes：恰好覆盖本批次的每一卷（payload.volume_ids），顺序与 contract.volumes 一致。'
                          '每卷是约 words 汉字的极简卷纲，把这一卷的因果骨架说完（words±tolerance 按性质是每卷总量，不是每段）。'
                          'stage 必填（opening/5 及之后的逐门项目）：从已选格局阶梯里取一级，逐字写那一级的 stage 名；'
                          '按合同卷序只升不降（后一卷的层级序号不得低于前一卷），不写「第一卷」这类编号——'
                          '阶梯每一级在世界模型里都有同名记录，卷纲的 stage 必须对得上。'
                          '已声明 world_architecture 时，arc/turns 承接其长期矛盾、历史后果与文明立场；'
                          '远期真相先以 hooks/window 登记可见线索和揭示窗口，章纲逐步披露，不把作者全知当角色知情。'
                          'purpose ≤60 汉字说这一卷的职责；arc 约 250 汉字写开局处境→关键转折→卷末局面；'
                          'turns 至少两条转折（at 取「卷中」「卷尾」或「第N章附近」）；climax 写卷末高潮与兑现物；'
                          'nodes 给 {id,kind:main|side|hidden,purpose,ending_condition,required,window:[本卷最早章,本卷最晚章]}；'
                          'threads 给 {id,kind,purpose,ending_condition,required}，跨卷延续的线路加 continues=true；'
                          'resources 给本卷资源大势 {key,from,to,reason}（key 必须已存在于世界模型或既有状态）；'
                          'places 给 {entity,from,to,reason} 的本卷起止；characters 给同样四键，'
                          'to 必须是 {desire,stance,relationship_focus} 的结构化卷末人物状态；'
                          'knowledge 给 {who,topic,from,to,reason}；'
                          'hooks 是必填数组（本卷没有伏笔就给空数组，缺字段会被拒）：每条 '
                          '{id,text,plant:[最早章,最迟章],payoff:[最早章,最迟章],required:true|false,continues:true|false}——'
                          'id 全书唯一（与 node/thread 同一命名空间，跨卷续用必须 continues=true 且 required=false）；'
                          'text 是对读者的具体承诺（哪件物、哪句话、哪桩没交代的事），不写「待补」；'
                          'plant 窗口必须落在本卷章号区间内，两章之间必须有一次 plant；payoff[0] >= plant[1]，'
                          '允许越过卷末，但越过时必须 continues=true 且 required=false；'
                          'required=true 的必须在卷末兑现，引擎在卷内状态链收尾处校验。'
                          '续写前卷留下的伏笔时沿用同一 id 并标 continues=true，id 清单见材料 hooks.open。'
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
                           'resources=[{key,from,to,reason}]、places=[{entity,from,to,reason}]、'
                           'knowledge=[{who,topic,from,to,reason}]、characters=[{entity,from,to,choice,cost}] 四类数组按模板逐项核对，缺省或 null 与空数组同义——'
                           '空数组就是「本章无此类变化」的声明；knowledge 的 to 取 hinted|suspected|misled|confirmed|retracted，'
                           'character 的 to 是 {desire,stance,relationship_focus} 且 choice/cost 缺一不可；'
                           '四类数组的 from/to 填准确前后值对象，不用状态描述字符串代替。'
                           'clock.advance_days 是本章经过的天数，不倒退；'
                           'enter/exit 是状态链的全部依据：enter 列本章开始时每个受动坐标的期望值（承接上一章 exit），'
                           'kind 取 resources|places|knowledge|character|node|thread|clock，key 用该坐标的键'
                           '（人物用实体 id，节点/线路用其 id，clock 用 clock）；'
                           'exit 必须等于 enter 施加本章全部增量后的结果——引擎自己算一遍比对，任一侧缺项即漂移、整份被拒，'
                           '先核实真实前态并列全实际变化，不能用少列坐标来避开核算；'
                           'disclosures 写读者认知的推进，world_refs 引用真实世界记录；'
                           'new_entities 内联新人物/地点/物品档案 {id,kind,name,role,desire,limit,knowledge_boundary}，'
                           '第一次出现就给全，不用另派档案阶段；'
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
                           'scenes/pacing 为当前章纲的可选字段。不写正文。',
        'write': '交 title/完整 prose/summary/具体 self_check 与逐条 drift_check。'
                 '本章纲（chapter_outline）与卷纲材料（volume_outline）都是必读；卷纲节点已按本章及前置依赖筛选，完整卷纲可从 complete_volume_outline 补读：按章纲的场景与增量落笔，'
                 '不添章纲没有的重大变化，也不漏掉章纲声明要发生的。'
                 'drift_check.items 已按章纲的计划增量预填，逐条把 actual 填成正文实际发生的值'
                 '（actual.from 由引擎投影，不是你自报的前态）、status 取 kept|deviated|skipped，'
                 'deviated/skipped 必须写 reason，但只作为待返修诊断，不能入库；evidence.quote 必须是正文原文片段。'
                 'unplanned 用于报告须从正文修掉的计划外变化，不能据此新增事实；本章通过须所有项 kept、unplanned 为空、verdict=clean。'
                 'actual 按种类给形状：resources/places/knowledge/characters 一律 {"from": 可省, "to": 值}——'
                 'resources 的 to 是数值字符串（如 "2"），characters 的 to 是 {desire,stance,relationship_focus}（不得用 after 键），'
                 'knowledge 的 to 是档位，places 的 to 是地点 id；hook 用 {"action": "plant"|"payoff"}，'
                 '节点/线路/读者披露用 {"after": 状态}，clock 用 {"advance_days": n}。'
                 '遵守 word_budget 的本章范围；作者真相、角色知情与读者已见严格区分，披露不越过 disclosure_boundary。'
                 'self_check 用具体表达说明实际视角、人物说话方式与节奏；'
                 'dialogue_ratio 未声明时不用补比例，已声明时如实核对，不按段落分配对白。'
                 '材料 style.anchor 是首章的实测指标、style.window 是本卷生效的容差：'
                 '默认 style_guard=observe 时首章形状差异仅供观察；作者选 strict 才按容差核验句段与锚点对白比例。'
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
    if name == 'volume_outline':
        rule += (' 本批次要交的卷与各自章号区间见 payload.volume_outline：volumes 逐卷给全字段，'
                 '不交 chapters（逐章说明由后续 chapter_outline 完成）。')
        if payload.get('repair'):
            rule += (' 这是返修不是重写：只改被点名的问题与偏差行（payload.drift），'
                     '其余卷保持与上一版逐字一致；节点/线路 id 与已批准集合保持一致。')
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
            enhanced += ' 章纲的 scenes/pacing 若已给出，按场展开并保持场序与依赖。'
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
        checks = '\n'.join(_check_block('提交前自检（这些是机械校验会直接判的）',
                                        '没有独立核验者了；下面每一条提交时都会机械判定：', VOLUME_CHECK_HINTS))
    elif name == 'chapter_outline':
        checks = '\n'.join(_check_block('提交前自检（这些是机械校验会直接判的）',
                                        '没有独立核验者了；下面每一条提交时都会机械判定，'
                                        '状态链还会从卷起始真实状态逐章重放你的 enter/exit：', CHAPTER_CHECK_HINTS))
    body = [rule + time_rule + enhanced + memory] + self_check + ([checks] if checks else [])
    tail = ('字段形状按 result.template.json；格式不确定用 check 自检。完整协议和创作指导在 guides，'
            '来源不足时按冻结哈希补读，不读源码猜格式。')
    return '\n'.join(body) + ('' if body[-1] == '' else ' ') + tail
