"""Per-dispatch briefs: the one page a worker actually needs, instead of every guide in full.

A guide is a reference document for a whole stage; a dispatch needs the part that applies to the
task in hand. Keeping the brief generated here — next to the methods it quotes — means the author
pays for the current gate's rules and lens, not for the entire toolbox on every round.
"""
from __future__ import annotations

from .creation import gate_note, gate_title, value_rules
from .contracts import (AUTHOR_CHANNEL_STAGES, CHECKS_VERSION, GENRE_CATALOG, OPENING_DIRECTION, OPENING_DIRECTION_GATES,
                        OPENING_VERSION, OPTION_CONTRACT, checks_for)
from . import stages, world
BRIEFS = {
    'opening_options': '开书方案简报',
    'world_model': '世界与约定简报',
}


def direction_block(gates=()):
    """The house default the ten gates aim at, rendered for the worker drafting this dispatch.

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


def opening_options(gate, lens_brief, previous=(), version=OPENING_VERSION):
    """The brief for one gate: what this gate decides, how to vary it, and what to hand back."""
    lines = ['# ' + BRIEFS['opening_options'], '',
             '## 本门：%s（%s）' % (gate_title(gate.get('id'), version), gate.get('id')), '',
             'value 字段：' + value_rules(version, gate.get('id')), '']
    note = gate_note(version, gate.get('id'))
    if note:
        lines.extend(['## 本门的交付要求', note, ''])
    if gate.get('id') == 'genre' and not previous:
        lines.extend(['## 全类目目录（作者未给方向时第一轮先铺开）',
                      '把下面十二个类目逐项列为方案基础（可按相近合并，但不许只挑三四个）：',
                      *['- %s：%s' % (name, hook) for name, hook in GENRE_CATALOG],
                      '每案给该类目下的一个具体落点（不是类目说明）：主角生态位、第一卷压力与开篇三章的第一个爽点。'
                      '作者点了大方向后，下一轮回到 2～3 个深化方案。', ''])
    if previous:
        lines.append('## 已选方向（不要推翻，只在此之上给方案）')
        lines.extend('- %s：%s' % (name, text) for name, text in previous)
        lines.append('')
    lines.extend(direction_block([gate.get('id')]))
    lines.extend(['## 本轮创意透镜（用来想，不要写进方案文本）', lens_brief, ''])
    lines.extend(['## 换组纪律（本轮若是因为换组重新生成）',
                  '- 新一组必须与被拒的旧组方向实质不同：不得换名、改写收益或微调细节冒充新组；',
                  '- 吸收作者随换组补充的偏好（原因里写了「格局太小」就把格局拉高一级：从个人恩怨到生态位，从一条街到一座城、一个秩序）；',
                  '- 已拒方向见 opening_rejections 记录，逐条避开其思路而不只是避开其措辞。', ''])
    lines.extend(['## 交付契约', OPTION_CONTRACT])
    lines.append('')
    lines.append('完整方法表与选项格式见 guides 里的文件；本简报已含本门所需规则，不必为格式再读全文。')
    lines.append('')
    lines.append('路径自检：task.json 的 commands/guides 由当前安装渲染。先确认其中的解释器与脚本存在再执行；'
                 '若不存在，回报主控重新 advance 刷新任务视图，不要自行改写命令，也不要假定某条路径失效。')
    lines.append('')
    lines.append('格式自检：写回执前用 `check` 试算（把候选 JSON 从标准输入管道进去，如 '
                 '`python CLI --project PROJECT check < 候选.json`）。它按提交同一套校验运行但不入库，'
                 '会直接告诉你缺哪个字段、哪个枚举不对。**不要为了确认格式去读引擎源码**——那会白花上下文，'
                 'check 的回答就是权威。')
    return '\n'.join(lines)


def world_model(lens_brief=None, previous=(), repair=False, scale=None, sections=None):
    """World plus contract in one dispatch: what the world owes, and what the contract must keep."""
    lines = ['# ' + BRIEFS['world_model'], '',
             '## 世界模型', '把已选方向扩展成能持续产生行动、冲突、代价与后果的环境。'
             '完整记录须有稳定 id 与 links=[领域:id]；同时给 premise、story_capacity 与准确的 selection_hash。'
             '不要写"待补"，写进去的域都要能落到具体场景。', '']
    if sections:
        # Same declaration the validator uses: asking for ten domains while the check happens to
        # accept a smaller world is how a micro project ends up writing records nobody reads and
        # repairing four times.
        labels = '、'.join('%s（%s）' % (name, world.LABELS[name]) for name in sections)
        empty = '、'.join(name for name in world.SECTIONS if name not in sections)
        lines.extend(['## 本档位要填的领域', '本项目按体量只需要：' + labels + '。'
                      + ('其余领域（' + empty + '）保留为空数组，不要为凑数写进来；' if empty else '')
                      + '除 mechanisms 外，列出的每个领域至少一条实写记录；'
                        '已选无特殊机制时 mechanisms 必须为空数组，有限机制时至少一条。', ''])
    if scale:
        # A world is read by every later dispatch, so its size is a recurring cost, not a one-off.
        # Ten domains at "at least one record" is a floor, not a target: a single-volume micro book
        # only needs the institutions and people its one line actually walks through.
        lines.extend(['## 规模要与已选体量相称', '本项目的体量与分卷是：' + scale + '。'
                      '世界只需支撑这条主线走完：写进每条记录前先问它会在哪一章被用到，用不上的城市史、势力谱系与日常细节不要为凑数写进来；'
                      '每多一条记录，之后每一次派工都要多读它。story_capacity 用一句话说清这个世界能撑住多少章、靠什么持续供料。', ''])
    if repair:
        # The draft and its repair used to share one brief, so a repair dispatch never said it was
        # a repair: the worker had to infer it from previous_proposal, and rewriting untouched
        # records reopened questions the last review had already settled.
        lines.extend(['## 这是返修，不是重写', '上一版世界与逐条 findings 都在 previous_proposal 里。只改 findings 点名的问题，'
                      '其余记录保持与上一版逐字一致；不要借返修顺手改写没被点名的部分。'
                      '逐条改完再自查一遍，避免改一处带出另一处不一致（规则互相否定、数字前后对不上、'
                      '某条程序被另一条堵死）。程序会逐条比对：没被点名的记录一旦被改动或删除，回执当场被拒'
                      '（repair_scope）；确实需要扩大范围时请核验者把 finding 写成 chapter 范围。', ''])
    if previous:
        lines.append('## 已选方向（不得改动）')
        lines.extend('- %s：%s' % (name, text) for name, text in previous)
        lines.append('')
    lines.extend(direction_block(('world', 'protagonist', 'engine', 'ending')))
    lines.extend(['## 同一份提交里还要给约定', OPTION_CONTRACT,
                  '约定必须逐字保留已选字段；模板里 contract 一节的字段骨架照填。', ''])
    lines.extend(self_check_block('world_model', CHECKS_VERSION))
    return '\n'.join(lines)


# What an independent reviewer will judge, turned into what the producer can check before submitting.
# Read from the same table the review uses (`CHECK_SETS`), so a brief cannot drift from the rubric it
# is judged by. The most expensive rework there is: an independent session plus the full material plus
# a repair round, spent discovering something the brief could have asked for — a real run's world went
# 14 -> 7 -> 4 -> 3 findings over four repair rounds, most of them criteria now listed here.
SELF_CHECK_HINTS = {
    'coverage': '该兑现的节点都真在正文里发生了，不是被提到。',
    'continuity': '与前文的器物、编号、称呼、立场接得上；同一个事实两处说法一致。',
    'resources': '用掉与得到的资源有来源、有去处，数量对得上。',
    'knowledge': '每个人只知道他该知道的；越界知情的来源要写出来。',
    'time': '顺序、历时与时限算得通，不出现同一段时间被用两次。',
    'world_rules': '世界规则用到时没被绕过，代价照付。',
    'space': '人物在场与移动对得上，没有瞬移与同场冲突。',
    'narrative': '这一章的推动清楚：谁因何行动、阻力、选择与代价、信息或关系变化。',
    'character_consistency': '人物这一章的言行与他的欲望、底线、声线一致，除非有据地变化。',
    'stable_facts': '已确立的事实没有被这一章无意改掉。',
    'read_on': '读到章末读者会想知道下一章发生什么。',
    'character': '人物是可记住的具体的人，不是功能。',
    'change': '这一章确实改变了什么：处境、关系、认知或代价。',
    'emotion_cost': '情绪有来处，代价落在人身上且可查。',
    'language': '句子干净、不啰嗦、不用形容词报幕；同一动作不重复描写。机械项：全书中文声线不留西文单词，对白引号用全书同一套体例（提交时直接判）。',
    'repetition': '句式、动作组与解释不与自己或前文重复；换写法而不是换词。机械项：与已核验章节逐字相同的连续文段（≥25 字）提交时直接判，跨章照抄会被拒。',
    'substance': '每一场都在推进或改变，没有为凑字数存在的段落。',
    'disclosure': '披露顺序正确：读者现在该知道的知道，不该知道的没提前漏。',
    'pacing': '张弛有分配，静章也承担余波、关系或暗线。',
    'dialogue_identity': '遮住名字也能听出是谁在说。',
    'voice_match': '声线与人物档案一致，压力下会变但不变人。',
    'pov_consistency': '约定的叙述人称与视角是硬约束：不越界、不无标记地切换。',
    'voice_evolution': '跨章的语言与视角是演进而非漂移。',
    'author_constraints': '每一处仍在作者约定内：承诺、体量、分卷、禁区、视角没有被顺手改掉。',
    'causality': '节点之间是先因后果，链上没有断口与悬空。',
    'characters': '用到的人物都已登记，行动与欲望、底线一致。',
    'scale': '规模与体量相称：不为凑数加设定，也不留下撑不起终局的空间。',
    'threads': '线路职责、窗口与终局可兑现；必要线路标了 required。',
    'choice_alignment': '世界仍遵守已选方向与前提，没有替换作者的取舍。',
    'rule_consistency': '规则自洽：范围、限制与违反后果彼此不冲突。',
    'spatial_connections': '地域之间的通行与阻隔说得通，压力来自地理本身。',
    'historical_causes': '历史事件与当下利益有因果，不是背景装饰。',
    'faction_interests': '各方诉求、力量来源与依赖能推出冲突。',
    'economic_consequences': '资源的生产、分配与稀缺能推出争夺。',
    'social_pressure': '制度、习惯与执行方式能推出普通人的处境。',
    'character_boundaries': '人物的知情边界与底线明确且未被越过。',
    'story_capacity': '一句话说清这个世界靠什么持续供料。',
}
# Which rubric a producer can self-check before submitting (reviewers keep their own list).
PRODUCER_CHECKS = {
    'world_model': ('world',),
    'book_plan': ('design',), 'volume_plan': ('design',), 'volume_outline': ('design',),
    'alignment_plan': ('design',),
    'write': ('fact', 'reader'), 'repair': ('fact', 'reader'), 'redesign': ('fact', 'reader'),
    'plan': ('fact',),
}


def self_check_block(stage_name, version):
    """The reviewer's criteria rendered as questions the producer can answer before submitting."""
    names = []
    for kind in PRODUCER_CHECKS.get(stage_name) or ():
        names.extend(checks_for(version, kind))
    rows = [(name, SELF_CHECK_HINTS[name]) for name in dict.fromkeys(names) if name in SELF_CHECK_HINTS]
    if not rows:
        return []
    return ['## 提交前自检（独立审查者会逐项看这些）',
            '这是核验者用的同一份清单；机械项（字数、必须节点、引用存在、禁区字面）提交时会直接判，'
            '判断项请你自己先按下面的问题过一遍，别把可以自查的问题留给独立核验：',
            *['- %s：%s' % (name, hint) for name, hint in rows], '']


def stage(name, payload=None):
    """Cold workers receive the rules of their stage without inheriting controller history."""
    payload = payload or {}
    rules = {
        'book_plan': '形成全书粗骨架和终局条件。跟踪项目声明 threads={id,kind:main|side|hidden,purpose,ending_condition,required}；至少一条必要主线。节点需 id/line/cause/choice/cost/outcome/disclosure/depends_on/required/window=[最早章,最晚章]。depends_on 是先发生的因果，不用它表达卷与全书的层级包含关系。',
        'volume_plan': '围绕本卷职责安排转折、代价、余波与关系变化；threads 可为空以沿用既有线路，新节点 ID 不覆盖。远期粗排，近期细化。节点必填字段同 book_plan；完整设计保留可选入口，frontier 为本次窗口视图。',
        'volume_outline': '完整读 world_model、volume_design 与 outline_bridge，承接已通过的卷内方案和前一批最后一章，只交本批次逐章情节推动说明，不重造卷内节点或世界规则。',
        'outline_review': '独立完整读本批次 proposal、已批准 volume_design、world_model 与 outline_bridge，核对每章推进和跨批次接缝。证据 chapter=0 来自本批次候选；按当前设计核验清单举证，提出具体修复，不替执笔签 pass。',
        'plan': 'plans 按章号恰好覆盖窗口。每章 goal/obstacle/choice/cost/change/ending/node_ids/participants；跟踪项目还交 node_actions=[{node,after:seeded|advanced|resolved}]、preconditions=[{kind,key,expected}]、disclosures=[{topic,after}] 和 pacing 五项。先依据真实前态，再模拟节点行动排后章；已兑现节点不能重复用。reader_refs/hook_refs/history_refs 可声明需要承接的旧资料；动到旧人物或物品前查相关承诺，资料不足用 recall 补读。按约定视角安排场景可叙述的范围，不安排越出该视角的叙述。',
        'profiles': 'profiles 恰好覆盖 payload.entities；每人 entity/desire/fear/limit/voice/knowledge_boundary。底层设定保持稳定，当前动机/关系以 state.character_current 的有据变化为准。人物声线来自关注点、底线和交涉策略。',
        'write': '交 title/完整 prose/summary/具体 self_check，不交事件或 pass。完整读必读材料，以动作、对白、选择、后果写场景，删除重复解释。遵守 word_budget 的本章范围；静章承担余波、恢复、关系或暗线作用。作者真相、角色知情与读者已见严格区分，披露不越过 disclosure_boundary。约定的叙述视角与人称是硬约束：不越出约定的视角范围，也不无标记地切换人称；母题靠事件与选择体现，不写成口号；基调不靠形容词报幕。',
        'repair': '读完整基稿、问题、义务和前态，交完整合成稿；local 保留成立部分，chapter 重排因果场景。不重置修复额度，旧 pass 不沿用。交付字段与 write 相同。',
        'redesign': '重新设计当前章的因果与场景，再交完整正文；不推翻已成立事实，不重复填充解释。交付字段与 write 相同，修复额度共享。',
        'chapter_review': '先只读本章正文，记录 desire/obstacle/change/read_on_reason 并冻结首读；解锁后同会话独立核验。facts 从正文重建 events/summary/elapsed_days，reader 判断阅读体验，两类都逐项举证。跟踪项目 facts 必须逐项提供 story_node 事件，读者变化交 reader_knowledge，人物动机变化交 character_current；reader.pacing 记录实际节奏及单个 evidence。hook 可按正文证据声明 subjects 人物/物品 ID 与 topics 话题 ID，供远期相关性加载；未标注的旧承诺需补读，不能猜关联。',
        'revision_review': '先只读待携带章正文并冻结首读，再核对 revision_impact、前文和创作记忆的阅读影响。只交 reader 检查，不重抽事实，不修改正文；成立则 pass 并保留原文。实质问题给 fix，findings 明确当前章及 local 或 chapter，程序转入返修后再完整独立章审。建议用 note，不把偏好或不同解释当硬矛盾。',
        'scope_review': '只读完整本块正文，冻结首读再核验。逐章 coverage，检查因果、人物桥梁、主支暗线兑现和情绪余波。树形任务还交 handoff 六项和精确短引文，保留未决问题；不能以重复 pass 替代综合判断。',
        'scope_synthesis': '独立阅读冻结子报告及边界正文，核验跨块/跨卷因果、人物变化、披露顺序、兑现和呼吸衔接。树形任务 coverage 按 children 的 part_id 一一回应，并交 handoff；疑点通过 recall 完整补读历史章。不伪造全书首读，不逐层复制全部正文和报告。',
        'design_review': '独立核验 proposal 与作者约定；逐项 reason/evidence，不自动填 pass。跟踪设计额外核对线路职责、窗口、前置因果和可兑现终局。证据 chapter=0。',
        'contract_review': '完整核验作者选择、约定来源、体量与限制的一致性；不改变已有作者决定。证据 chapter=0，按模板检查清单提交。',
        'opening_contract': '把已核验世界和真实用户选择整理为完整约定，严格保留对齐字段，按模板填写，不增加正文事实。',
        'world_review': '独立核验选择和世界候选，逐项查规则、空间、历史、势力、经济、社会、人物、披露和长篇承载；证据 chapter=0。',
        'alignment_plan': '读取 alignment_hold 与准确正文，为当前章或即将进入的章提出完整 plan 和必要 designs 改案。保留已实现节点、必要职责与原目标；设计改案不产生事实，不改正文或清零额度。',
        'alignment_review': '独立核验 alignment_proposal 是否保全成立正文、作者约定、未解决目标与因果依赖；按设计模板逐项举证。通过后仍由新审稿者重读当前稿，不继承旧首读或 pass。',
    }
    stages.require_stage(name)
    rule = stages.require_rule(name, rules.get(name))
    outline = payload.get('volume_outline')
    if name == 'volume_plan' and outline:
        rule += (' 先完整读已核验 world_model 与全书骨架，比较 2～3 个因果不同的卷内推进方案，交 brainstorm=[{id,premise,tradeoff,world_refs}]。'
                 '在既定作者约定内选出最合适的一案，交 selected/selection_reason，不再要求作者重复选择；脑暴不能改写世界规则。'
                 '绑定 world_hash，节点覆盖整卷职责；当前只交方案和节点，逐章说明由后续 volume_outline 有界批次完成，不在此任务交 chapters。')
    if name == 'design_review' and outline:
        rule += ' 独立核验脑暴各案的推进方式确有差异、选案理由成立，世界限制和本卷节点可落实。逐章说明在后续批次单独核验。'
    if name == 'volume_outline' and outline:
        rule += (' world_hash 准确绑定本任务世界版本；chapters=[{chapter,synopsis,world_refs,node_ids}] 恰好覆盖第 %d～%d 章。'
                 '每章 synopsis 目标 %d 汉字，允许 %d～%d 汉字；以最精练的因果说明写清谁因何行动、遇到的阻力、选择与代价、信息或关系变化，以及怎样推动下一章。'
                 '静章说明余波、关系或线索的具体变化；不写正文、氛围扩写、空泛目标、重复设定或方法自评。每章引用真实世界记录和已批准设计节点。'
                 % (outline['first'], outline['last'], outline['words'], outline['words']-outline['tolerance'], outline['words']+outline['tolerance']))
    if name == 'outline_review':
        rule += ' 字数合格不等于情节成立：核验世界依据、因果桥梁、角色选择与代价、章末推动和精练程度，有问题沿 author_constraints/causality/characters/disclosure/scale 等当前检查项给 fix。'
    if name == 'plan':
        rule += (' 若有 volume_outline_window，先读已核验窗口卷纲，再依据真实前态细化；rolling 只细化近期，其余卷保留职责和关键节点，不编造已完成全书卷纲。'
                 ' 每场可声明稳定 id、reads=[{kind,key}] 和 depends_on=[前章或本章前场ID]。新 scene-identity/2 的 id 是不透明身份，移动或拆合章时保留；旧冻结协议仍用 c章号: 前缀。story_time 可独立说明故事发生时间，不按阅读章序推进时钟。'
                 ' dependency_coverage=complete 表示每场已列全依赖（无依赖也给空数组）；未核清用 partial，修订时将保守扩大范围。')
        if payload.get('understanding'):
            rule += ' understanding_refs 可显式补读场外作品理解；reading_refs 按人物/关系/母题/声线/披露声明阅读关联。reading_coverage=complete 须每场列 reading_refs，无额外关联也给空数组；未核清用 partial。'
    if name in ('book_plan', 'volume_plan', 'volume_outline', 'plan'):
        rule += (' 可交可选 ledger 账目行（每行 {key,value,sum_of|product_of|equals|ratio_of:[整数]}）：'
                 '数字与数量关系一旦写成账目行，提交时机械验算，后续工件同键必须同值；'
                 '不声明就省略字段，不要把观感描述写成账目。')
    if name in ('write', 'repair', 'redesign'):
        rule += ' 若有 chapter_outline，承接该章情节推动说明，按当前计划展开场景；卷纲不是正文，避免复制概要腔。'
        rule += ' scene_context 按场交付目标、依赖与准确前态，scene_sources 绑定历史原文版本；依赖缺失先补读或重规划，不把人物误信当世界真相。'
    time_rule = ''
    if name == 'plan':
        time_rule = ' 章号不等于天数；按场景因果安排时间，允许多章发生在同一天，不默认每章推进一天。schedule 只声明情节需要的硬日程，不把内部时钟设计成逐章日期标题。'
    elif name in ('write', 'repair', 'redesign'):
        time_rule = ' 默认直接从人物行动、对白或场景切入，不在正文前加独立日期或“第一日、第二日”式报日标签，也不把每章首句固定成时间播报。需要交代时间时自然融入场景转折；state.clock 是内部累计天数，不是章号或必须写出的日期。同日续接无需为验收补造过夜；作者明确要求日记体、编年体或日期标记时按约定执行。'
    elif name == 'chapter_review':
        time_rule = ' facts.time 按正文相对前态核验实际时间，允许 elapsed_days=0 且没有 clock 事件；不能要求每章过一天或用章首日期凑证据，clock 引文可在正文任意位置。reader.language/repetition 检查无叙事作用的章首报日与固定时间播报，有问题按原清单给 fix；情节必要的时间提示及作者明确约定的日期体例按作用判断。reader.pov_consistency 按约定的叙述视角与人称核验：切换视角本身不判错，缺少交代或标记的跳跃、越出约定视角范围给 fix。'
        time_rule += ' facts.continuity 同时核对场景 reads/depends_on 与正文因果；complete 声明遗漏依赖给 fix。revision_impact 只是范围分析，不替代独立阅读。'
    elif name in ('scope_review', 'scope_synthesis'):
        time_rule = ' 在 pacing 检查跨章开场是否反复报日或沿用固定时间播报；根据叙事作用和作者体例判断，无作用的重复给修订意见，不因时间提示本身判错。reader.pov_consistency 一并核验约定的视角与人称在跨章之间是否稳定，以及每次视角切换是否作了交代。'
    extra = (' pacing={role:setup|pressure|turn|climax|aftermath|recovery|relationship|discovery,pressure_in,pressure_out,emotional_aftereffect,recovery_purpose}，用具体文字，不按固定轮替。'
             if name in ('plan', 'chapter_review') else '')
    handoff = (' handoff={causal_bridge,thread_changes,character_changes,disclosures,rhythm,open_questions,evidence}；文字每项≤800字，证据1～8条，每条引文≤240字，原文始终完整保留。'
               if name in ('scope_review', 'scope_synthesis') else '')
    enhanced = ''
    if payload.get('editorial'):
        enhanced = {'plan': ' 每章还需 scenes（label/intent/conflict/turn/present/speakers/dialogue_intents）与 expansion_units。',
                    'profiles': ' 还需 tier、biography={public_role,contradiction,values}、speech={register,tactics,rhythm,stress_shift,relationship_modes}；旧档更新给 change_reason。',
                    'repair': ' 可用 base_hash/patches/repair_note 或 reuse_original 替代 prose；程序合成后完整重审。基稿与前态仍必读。',
                    'redesign': ' 可提交版本补丁；仍消耗本章共享重设计额度。',
                    'chapter_review': ' 填 alignment 的实际节点实现及 follow_plan/adapt_future/align_design/repair_prose 裁决；不以完成数量替代实际效果。',
                    'scope_synthesis': ' root 若含 closure 按六项职责裁决；remedies 逐项验收原目标，末轮额度为零也先验。'}.get(name, '')
        if name == 'scope_synthesis' and payload.get('closure', {}).get('revision_policy'):
            enhanced += ' 优先保留已验收前文；确有历史缺陷才 revise_range，range 从最早 target_chapter 起，changes 区分 expression/reading/semantic 并声明真实变更坐标。程序先分析影响，超出近期窗口或触及已关闭的验收范围时只保存修复方案，不自动扩大重写。'
    authority = ''
    if name in AUTHOR_CHANNEL_STAGES:
        authority = (' 若某一项确实是作者约定本身的问题、任何改写都无法解决，把该发现标为 severity=author 并给'
                     ' decision={id,question,options}：id 是这条裁决的稳定身份，question 写成一个作者能直接回答的问题，'
                     'options 至少两个，每项 label/impact 说明取舍后果。程序会暂停项目、把问题交给作者，不安排写作端返修；'
                     '作者在选项内作答即记录并按新前提重拟候选，只有要改约定本身的答案才走改约——已有正文时改约会在'
                     '新分支自第 1 章重写重审，把该代价如实写进 options 的 impact 让作者知情。'
                     '一份回执最多上交一条；能由改写解决的缺陷仍用 blocker/quality 并给 target_chapter 与 repair_scope。')
    memory = ''
    if payload.get('understanding'):
        memory = ' creative_memory 是可修订的理解及原文表达样本，结合反证和适用范围使用；不把解释直接当世界事实，也不必模仿样本句式。unavailable_refs 是当前缺失或已失效的旧理解，须核对原文或重规划，不照搬失效解释。'
        if name in ('chapter_review', 'scope_review', 'scope_synthesis', 'revision_review'):
            memory += ' 有值得延续的新理解时交 understanding 数组（无新增用空数组），按 workbench 指南给 id/kind/claim/subjects/topics/status/reason/evidence/counterevidence；保留多种解释，不为完成表格强行提炼结论。'
    repair_rule = ''
    if payload.get('repair') and name in ('book_plan', 'volume_plan', 'volume_outline'):
        # A design repair re-emits the whole candidate, so an unrequested rewrite of untouched
        # records is pure cost: it reopens questions the last review already settled, and the next
        # review spends a round on new material instead of the named defect. A real world repair went
        # 14 -> 7 -> 4 findings while each round rewrote every record; narrowing the repair is what
        # makes the rounds converge.
        repair_rule = (' 这是返修不是重写：只改 findings 点名的问题，其余记录保持与上一版逐字一致，'
                       '不要借返修顺手改写没被点名的部分；上一版候选与逐条 findings 都在 previous_proposal 里，'
                       '逐条改完再自查一遍，避免改一处带出另一处不一致。')
    # The rubric the review uses, handed to the producer as questions it can answer itself. The same
    # criteria, read from the same table: a first draft that fails a criterion the brief could have
    # asked about costs an independent session, the full material and a repair round to discover.
    self_check = self_check_block(name, payload.get('checks_version', CHECKS_VERSION))
    return ('\n'.join([rule + time_rule + extra + handoff + enhanced + authority + memory + repair_rule]
                      + self_check)
            + ' 字段形状按 result.template.json；格式不确定用 check 自检。完整协议和创作指导在 guides，'
              '来源不足时按冻结哈希补读，不读源码猜格式。')
