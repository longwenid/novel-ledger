"""Shared wire contracts and value utilities; no I/O or domain imports."""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

# The five-step pipeline is a protocol generation change: v2 removed every reviewer dispatch, so a
# task frozen by v1 (checks_version, obligations, blind first read, plan/book_plan stages) can no
# longer be executed by this build. Projects keep their storage schema; what changed is the
# pipeline, and the version says so.
VERSION = '2.0.0'
SCHEMA = 'novel-ledger/3'
# The guided opening has its own protocol version, carried by the creation state itself. It is not the
# database schema: a new gate set only changes a JSON document inside the book record, so raising the
# storage version would lock every existing project out for no benefit. A project whose creation state
# is version 1 keeps the gate set it was opened with.
OPENING_VERSION = 6
TASK = 'novel-ledger.task/1'
RESULT = 'novel-ledger.result/1'
# The dispatch's own copy of who it is: data for cross-checking, never a permission.
IDENTITY = 'novel-ledger.identity/1'
# v2 removed every reviewer stage: the check lists (FACT_CHECKS/READER_CHECKS/… and the
# CHECK_SETS versions they were raised under) are gone with the receipts that carried them.
# What a chapter owes is now declared by its own chapter outline, and what it actually did is
# computed by the engine from the writer's drift_check — see drift.py. Raises no longer travel
# as findings between a producer and a reviewer; a broken receipt is refused where it is filed.


# --------------------------------------------------------------------------------------------------
# Standard numeric settings, declared exactly once.
#
# Every layer that needs one of these reads it from here: the contract's own defaults below, the
# checks in drift/style/lint, the fallbacks in workflow/context, and the test fixtures. The rule is
# narrow but absolute — a *policy default* has one source. Scattering the same band across modules is
# not decoupling, it is four copies of one decision: changing the volume outline's floor from 1000 to
# 2000 once meant editing five literals, and any missed one would have left two layers disagreeing
# about what "the default" is. Layer boundaries (who may import whom) are the decoupling this repo
# enforces in tests/architecture_table.py; numbers shared across layers belong to this table.
#
# Each entry is data, not behaviour: changing a value here changes the engine's default for new
# projects, while an existing project keeps the policy stored in its own contract.
DEFAULTS = {
    # Step three: one volume outline per volume, complete in a single receipt. [floor, ceiling] =
    # [2000, 3000] 汉字 — 2000 is the author's floor, 2500 the target.
    'volume_outline': {'scope': 'all', 'words': 2500, 'tolerance': 500},
    # Step four: one synopsis per chapter, with that chapter's drift declarations.
    'chapter_outline': {'scope': 'volume', 'words': 150, 'tolerance': 60},
    # Style proxies: relative tolerances against the approved first chapter, an absolute in-chapter
    # repetition ceiling, and 1 meaning "the narration person must match what was declared". The
    # repetition ceiling is calibrated: ordinary Chinese prose measures 0.043~0.086 here, a chapter
    # that repeats one clause measures 0.79~0.99.
    'style_window': {'sentence': 0.35, 'paragraph': 0.35, 'dialogue': 0.40, 'repetition': 0.12, 'person': 1},
    # Where a style metric is worth measuring at all: below these floors the sample says nothing and
    # comparing it would only produce noise findings on chapters the word budget already governs.
    'style_floor_han': 40,
    'style_min_sentences': 3,
    'style_min_ngrams': 20,
    'style_ngram': 4,
    'style_short_sentence': 10,
    'style_same_order': 3,
    # Bounded repair: how many rounds one chapter may spend before the author is asked.
    'repairs': 2,
    'redesigns': 1,
    'stall_after_rounds': 2,
    # opening/5's two new gates are the ones a web serial lives on, so their floors are numbers, not
    # prose: how many rungs the reader-visible ladder must show at each size class, how many stages
    # the 格局 ladder must walk, and how late the theme anchor may land. `anchor_max_chapter` is the
    # reader-verifiable window the platforms actually reward (~100k characters at a 3.5k chapter
    # target); a small tier's own chapter window is tighter, so the check takes the smaller of the two.
    'world_ladder': {
        'tier_min': {'t0': 2, 't1': 3, 't2': 3, 't3': 4, 't4': 4, 't5': 4},
        'stage_min': {'t0': 2, 't1': 2, 't2': 3, 't3': 4, 't4': 4, 't5': 4},
        'anchor_max_chapter': 30,
    },
}


def policy_default(key):
    """A policy's default, copied: callers must not be able to mutate the one declaration."""
    value = DEFAULTS[key]
    return copy.deepcopy(value) if isinstance(value, (dict, list)) else value


# --------------------------------------------------------------------------------------------------
# opening/5's setting vocabulary, declared once for the gates, the world model and the checks.
#
# The 2024-2026 male-channel research (validation/opening5-spec.md §2) says the genre's live
# decisions are a world rule that keeps feeding the story, a ladder the reader can count, and an
# escalation that changes the rules instead of the map. Enumerating the answers is what makes them
# checkable at the gate instead of re-invented three dispatches later.
#
#   WORLD_SCOPES     the space a 格局 stage is fought over, in the order it may widen
#   WORLD_GROWTHS    what actually gets bigger at that stage — a map swap alone is the failure mode
#   WORLD_TERMINALS  the grade the ending must face; it has to match the ladder it was promised with
#   STANCES          the protagonist's relation to the rule system (顺从/利用/对抗 — the 博弈型 turn)
#   DARK_SIDES       where the world's malice comes from: an outside force, or people and institutions
# Opening decisions, their meaning, and their exact destination in world records.
WORLD_ARCHITECTURE = (
    ('space', '世界全貌与边界：文明分布、相互通行及尚不能抵达之处', 'geography', 'environment'),
    ('history', '历史断层：过去的选择如何形成今天的危机与利益结构', 'history', 'present_effect'),
    ('civilizations', '文明与秩序：不同群体的生存方式、相互依赖及不可兼得的目标', 'factions', 'conflicts'),
    ('conflict', '贯穿矛盾：即使主角不行动也会持续恶化的问题及其驱动力', 'rules', 'consequences'),
    ('mystery', '终极谜题：真相会改变什么既有认知，揭开后仍须解决什么', 'mysteries', 'truth'),
)

WORLD_SCOPES = ('局部', '一城', '一域', '一界', '星海', '诸天')
WORLD_GROWTHS = ('地盘', '势力', '规则', '认知', '文明')
WORLD_TERMINALS = ('局部', '势力', '体系', '文明')
STANCES = ('顺从', '利用', '对抗')
DARK_SIDES = ('外神', '天灾', '系统', '上层剥削', '制度', '人心')
# A ladder that reaches these scopes ranges beyond one map, so the world model has to carry a
# 空间与位面 domain for it. Told to the world dispatch and read by the same check.
COSMOLOGY_SCOPES = ('一界', '星海', '诸天')
# Combinations the current headliners already own: the public settings a new book can transplant
# for free, and therefore the ones a proposal has to prove it adds a rule to. Advisory only — the
# board shows the warning, the author keeps the choice (same severity as the name-cliche warning).
SETTING_CLICHES = ('序列', '途径', '克苏鲁', '克系', '系统', '幕后黑手', '第四天灾',
                   '诸天', '无限流', '模拟器', '签到', '存档重开')


# Frozen task capabilities: which version of a protocol a dispatch was planned under. A consumer reads
# them to keep interpreting a field the way that task was written. Each capability declares every
# version this build understands, so an undeclared value is an error instead of a silent downgrade to
# "old project" — a misspelled reading protocol would otherwise stop reading_refs being interpreted
# without anyone noticing.
EDITORIAL_CAPABILITY = 'editorial/1'
UNDERSTANDING_CAPABILITY = 'understanding/1'
SCENE_IDENTITY_V1 = 'scene-identity/1'
SCENE_IDENTITY_CAPABILITY = 'scene-identity/2'
READING_DEPENDENCIES_CAPABILITY = 'reading-dependencies/1'
OPENING_BOUNDS_CAPABILITY = 'opening-bounds/1'
# The volume outline protocol changed shape in v2: a volume is now one outline per volume, complete
# in a single receipt, carrying its own nodes/threads and state boundaries, and the per-chapter rows
# live in the chapter outline that follows it. A task frozen under volume-outline/1 describes a batch
# of chapters instead, so this build refuses it rather than reinterpreting its fields.
VOLUME_OUTLINE_CAPABILITY = 'volume-outline/2'
# New tasks require explicit style and computable volume terminals. Old frozen tasks keep their
# original interpretation; upgrading the engine does not add fields to an existing dispatch.
OUTLINE_CHECKS_CAPABILITY = 'outline-checks/1'
SCENE_MEMORY_CAPABILITY = 'scene-memory/1'
HOOK_LINKS_CAPABILITY = 'hook-links/1'
CAPABILITIES = {
    'editorial': (EDITORIAL_CAPABILITY,),
    'understanding': (UNDERSTANDING_CAPABILITY,),
    'scene_identity': (SCENE_IDENTITY_V1, SCENE_IDENTITY_CAPABILITY),
    'reading_dependencies': (READING_DEPENDENCIES_CAPABILITY,),
    'opening_bounds': (OPENING_BOUNDS_CAPABILITY,),
    'volume_outline': (VOLUME_OUTLINE_CAPABILITY,),
    'outline_checks': (OUTLINE_CHECKS_CAPABILITY,),
    'scene_memory': (SCENE_MEMORY_CAPABILITY,),
    'hook_links': (HOOK_LINKS_CAPABILITY,),
}


def capabilities_for(task):
    """A frozen task's capabilities, with every value checked against this build.

    Absent means the dispatch predates that capability; a present but undeclared value means the task
    was frozen by a version that knows a protocol this build does not, which is a dispatch error
    rather than an invitation to reuse the older interpretation.
    """
    frozen = (task or {}).get('capabilities') or {}
    require(isinstance(frozen, dict), 'capability', '任务 capabilities 须为对象。')
    unknown = sorted(str(key) + '=' + str(value) for key, value in frozen.items()
                     if value not in CAPABILITIES.get(key, ()))
    require(not unknown, 'capability', '任务冻结了本版本无法解释的能力值。',
            {'unknown': unknown, 'known': {key: list(values) for key, values in CAPABILITIES.items()},
             'recover': '该任务由不识别这些协议的版本冻结；用原版本继续执行，或取消后按当前协议重新派工。'})
    return frozen
# Findings the engine itself raises when a receipt cannot be reconciled (drift, lint, budget).
# 'author' means no rewrite can settle it — the premise itself must be decided, so it is routed to
# the author instead of becoming a repair target.
FINDING_SEVERITIES = ('blocker', 'quality', 'note', 'author')
AUTHOR_SEVERITY = 'author'
# Stages the controller session may execute itself. They carry no prose and no review-to-writer
# independence -- the opening gates are creative proposals the author judges live -- so the
# cold-session rule buys nothing here while costing a subagent per gate (measured: 0.4M~1M input
# tokens and 2~5 minutes each, for a 3.6K-character envelope). Everything else, starting with
# world_model, keeps the new-worker rule.
CONTROLLER_STAGES = frozenset({'opening_options'})
# The male-channel category ladder shown whole when the author starts with no direction: a genre
# decision should begin from the full menu, not from three cold samples (the first gate of a real
# run regrouped twice before the author ever saw a category list).
GENRE_CATALOG = (
    ('玄幻', '东方超凡体系：境界、宗门与天材地宝，爽点是层层升格与越阶碾压。'),
    ('仙侠修真', '求长生的修行世道：功法、因果与劫数，爽点是道途逆旅与斩断宿命。'),
    ('都市异能', '现代城市里的超凡觉醒：能力、组织与隐秘规则，爽点是能力变现与身份反转。'),
    ('都市职场', '现实赛道里的逆袭：行业、编制或商战，爽点是步步登高与打脸收权。'),
    ('历史权谋', '王朝与庙堂的博弈：出身、站位与大势，爽点是以小博大局局翻盘。'),
    ('科幻末世', '技术或灾变后的新秩序：舰队、废土或进化，爽点是文明级翻盘与重建。'),
    ('悬疑探案', '灵异或罪案的层层解谜：规则怪谈或刑侦流，爽点是真相反转与恶有恶报。'),
    ('游戏电竞', '游戏系统或电竞赛场：副本、排位或全服竞争，爽点是登顶与版本答案。'),
    ('武侠', '江湖门派与恩怨情仇：武功、侠义与门派倾轧，爽点是快意恩仇与称雄江湖。'),
    ('军事战争', '铁血战场与军旅生涯：命令、兄弟与家国，爽点是战役翻盘与建功授勋。'),
    ('体育竞技', '赛场内外的热血成长：天赋、苦练与团队，爽点是夺冠路与绝地逆转。'),
    ('二次元轻小说', '日常幻想或异世界轻改：人设、梗与羁绊，爽点是设定趣味与情绪价值。'),
)
# AI-generated names cluster on these: the cliche surname x mystical single char pair covers most
# model-produced two-character names, and readers spot the batch instantly (a real run kept
# producing a specific rare char in new names). The combination is flagged as an advisory on the
# board; a hard ban stays the author's lexical rule.
CLICHE_SURNAMES = '叶林萧楚顾沈陆苏秦'
CLICHE_GIVEN = '辰尘轩言夜寒渊冥烬煜珩枫炎离砚'
# Bounded repair budgets: one chapter may spend this many rounds before the author is asked. Declared
# in DEFAULTS with every other shared number, and aliased here because the workflow reads them by name.
REPAIRS = DEFAULTS['repairs']
REDESIGNS = DEFAULTS['redesigns']
# Fast verification merges block reviews by design: a basic project's fast mode sets the review block
# to exactly this size instead of reading the author's review_chunk, so one review task never covers
# more than this many chapters and a whole volume never lands in a single worker.
FAST_REVIEW_BLOCK = 12
TIME_MARKERS = tuple('日天夜晨早晚午时年月春夏秋冬晓暮昏宵旬翌昨今明') + ('星期', '分钟', '秒钟')
DEFAULT_TERMS = ['账本', '入账', '回执']
# No character is banned by default: naming is the author's decision, so the name rule starts empty
# and the author fills it through `lexical` when a project needs one.
DEFAULT_NAME_CHARS = []
# Work-directory artifacts the controller may regenerate; everything else in a task directory
# is authored by a Worker and is never rewritten behind its back.
FORM_ARTIFACTS = ('input.json', 'result.template.json', 'brief.md', 'dispatch.md', 'catalog.md')
# Setting-generation methods for the opening gates. A method is a way to make the next option
# genuinely different, not a label: the axis spends one slot of the choice, the method says how to
# vary it. Kept beside the contract fields because option quality is part of the author-facing
# contract.
#
# v3 rewrite: the earlier table was general literary brainstorming (mixing, inversion, binding,
# closure…) and a real run kept returning options the author rejected as 「格局太小」「不够网文」.
# The default direction is a male-channel long serial, and settings there are *built to spend*: an
# edge the world has to keep feeding, a ladder the reader can see, opponents that arrive with the
# next map, one hard currency somebody allocates, and enough headroom for a million characters.
# Each method therefore states what it must produce, and the third element is that check. The
# general craft discipline these replaced still applies — it lives in references/hatch.md.
LENSES = (
    ('金手指倒推', '先推演世界规则对所有人的后果，再找主角能介入的一处例外：它的升级材料、'
                   '克制它的对手、想抢它的组织，都要能从世界里持续产出；只给一个外挂不算。',
     '写清优势是什么、每次使用要什么、世界里有谁在供料、谁在抢它，以及它开篇三章第一次怎么用上。'),
    ('等级闭环', '把力量做成读者能预期的台阶（境界/段位/星级/职位），每级都有明确的升级条件与可量化'
                 '资源；条件写在世界里，读者随时能答"下一步要什么"。',
     '列出三级台阶：每级的名字、升级条件、拿到什么、卡在哪，以及谁在把守这个门槛。'),
    ('对手换图', '从个人困局追到利益网络、规则制定者与文明选择；旧对手的行动留下长期后果，新舞台'
                 '自带新资源与新规则；靠误会或临时加设定维持的梯度不算。',
     '写出前三级对手、每级挡住的具体利益，以及主角胜利后改变了什么规则、关系或可行动范围。'),
    ('硬通货', '从稀缺资源追问整个社会如何运转（能源/寿命/航路/知识/信用），谁分配它谁就有权，'
               '冲突围绕分配权与获取渠道展开；只当背景名词不算。',
     '写清资源名、来源、稀缺点、分配者，以及主角第一次为它出手的场合与代价。'),
    ('身份马甲', '主角在多个势力里有不同身份，制造扮猪吃虎、打脸与信息差；每个身份都要带暴露风险，'
                 '身份之间不能互相打架。',
     '写出至少两个身份、各自的用处、暴露会失去什么，以及第一次差点暴露的场合。'),
    ('套路反打', '在类型固有桥段上翻一层：读者熟悉的那一步照走，代价或结果反过来；为反而反、'
                 '让读者看不懂规则不算。',
     '先写清被反打的那条套路，再写反转后谁吃亏、爽点落在哪一句。'),
    ('代价上限', '主角的优势必须在开篇就带上可见的代价与明确的上限，代价改变后续抉择；'
                 '后期靠临时削弱或加强来维持平衡不算。',
     '写清代价的具体形态、上限在哪，以及它如何限制下一次选择。'),
    ('爽点倒推', '从读者要的兑现节奏倒推设定：短线兑现密度、章末钩与卷内高潮位置先定，设定为节奏'
                 '服务；设定好看而节奏空转不算。',
     '列出短线兑现的密度、两个卷内高潮的位置与开篇三章的第一个爽点。'),
    ('生态位垄断', '把故事放进一个被垄断的生态位：谁垄断什么、主角撬动哪一环、新平衡由谁付账；'
                   '只换皮不换生态位不算。',
     '写清垄断者、被撬动的环节，以及主角介入后的新秩序。'),
    ('数据面板', '把成长做成可核对的数字（属性、等级、任务、贡献、排行榜），让读者随时看见进步了'
                 '多少；数字要有人认账，随便写的等级不算。',
     '写清面板上会出现哪几项、每项怎么变，以及谁承认这张榜（排名对资源分配有什么实际后果）。'),
    ('记忆点标签', '给世界与主角造几个一眼能记住、能被读者复述的标签（称号、流派、道具、口号），'
                   '名字要能搜索、能出现在章末钩里。',
     '写出三个可传播的标签，说明它们第一次出现在哪一幕、由谁说出。'),
    ('长线续航', '设定必须撑住长篇：敌人、地图、资源与等级都留了继续加层的位置，不靠临时改设定'
                 '续命；三十章就把牌打光不算。',
     '写出第二卷与终局各新增什么层级，并说明它与你现在写的规则同源。'),
    # The opening/5 methods. The first twelve make a setting spendable; these five are what the
    # 2024-2026 evidence says a setting needs to still be there in volume six — a source for the
    # world's malice, an epoch above the current map, a rule the protagonist can play against, a
    # growth line that is not a number, and one visible carrier per backstage truth.
    ('世界暗面', '先定世界的恶意从哪来：外部不可名状（外神/天灾/系统），还是上层对人的剥削与制度失灵。'
                 '暗面必须持续供料——谁在收割、谁在承担、代价落到谁头上；换地图不换这条矛盾。',
     '写清恶意的来源、它今天正在拿走什么、主角第一次被它拿走的东西，以及至少两个也在承担它的人。'),
    ('纪元断层', '在世界上面压一层读者一时看不见的时间结构：上一个纪元留下了什么（遗迹、旧神、'
                 '遗留规则、还在运转的机构），主角每上一级就更靠近它；这一层不随地图更换而作废。',
     '写出上个纪元的名字与它留下的三样东西、现在谁在用它、以及主角在第几卷会碰到它。'),
    ('规则博弈', '把规则当对手而不是背景：主角对体系是顺从、利用还是对抗，至少一条读者看得见的规则'
                 '会被他利用或改写，改写的代价与反噬写清；规则不能被主角单方面宣布无效。',
     '写出被博弈的那条规则、主角的立场（顺从/利用/对抗）、第一次利用或改写的场合，以及反噬落在谁身上。'),
    ('非数值成长', '成长不只靠数值：认知迭代、心性、关系、真相掌握各给一条能兑现的线，让读者在'
                   '等级之外也能感到他变了；只更新面板不算成长。',
     '写出等级之外的两条成长线、各自第一次兑现的场合，以及它如何改变他下一步的选择。'),
    ('表层锚点', '选择与开局有关的底层设定，绑定一个读者能看见的载体（一件物、一个场景、一次冲突），'
                 '其余背景按揭示窗口展开；先展示异常或后果，再逐步说明原因。',
     '为开局关联的设定选一件物、一个场景或一次冲突，说明谁看见了什么、尚不知道什么。'),
)
# Volume-level turn methods: what makes a volume mid-point change direction instead of
# stacking everything on the finale. Used when planning the current volume.
VOLUME_TURNS = (
    ('卷中转折', '在卷半程安排关键翻盘，改变后半卷的对抗走向，不把高潮全堆在卷尾。'),
    ('代价递进', '卷内分段支付不可替代之物（名誉、靠山、同伴），换取核心真相。'),
    ('对手揭露', '前期明面阻力实为棋子，真正的对手在中期浮出水面。'),
    ('线索回收', '前期的闲笔或次要人物在卷尾成为决定胜负的关键手。'),
    ('双线演进', '核心对手在幕后推进自己的目标，与主角线交错施压。'),
)
# The structural (non-creative) gate: length and volume shape. These are arithmetic, not invention —
# every set below is proved writable by the same rules `planning.validate_contract` enforces, so the
# engine offers the tiers itself instead of asking a writer to invent numbers the validator may reject.
#   chapters       recommended total chapters for the tier
#   chapter_window the chapter counts at which the tier's band is actually reachable
SCALE_TIERS = (
    {'id': 't0', 'name': '微型', 'word_range': [6000, 59500], 'chapter_min': 2000, 'chapter_aim': 2600,
     'chapter_max': 3500, 'volume_count': 1, 'chapters': 17, 'chapter_window': [2, 19],
     'note': '单一事件的完整闭环：两三章的短篇到十七回的微型连载都算这一档；一条主线、两三个人物，'
             '没有卷内转折与支线并行的余地'},
    {'id': 't1', 'name': '短篇', 'word_range': [90000, 175000], 'chapter_min': 1800, 'chapter_aim': 2500,
     'chapter_max': 3500, 'volume_count': 2, 'chapters': 50, 'chapter_window': [40, 57],
     'note': '一次完整的因果闭环；没有中段铺陈与多线并行的余地'},
    {'id': 't2', 'name': '精简', 'word_range': [220000, 400000], 'chapter_min': 2200, 'chapter_aim': 3000,
     'chapter_max': 4000, 'volume_count': 4, 'chapters': 100, 'chapter_window': [84, 112],
     'note': '一条主线的完整起落与两三处关系变化；卷内很难安排中期翻盘'},
    {'id': 't3', 'name': '标准', 'word_range': [450000, 810000], 'chapter_min': 2500, 'chapter_aim': 3500,
     'chapter_max': 4500, 'volume_count': 6, 'chapters': 180, 'chapter_window': [143, 200],
     'note': '两三条线索交错、一次卷中转折与中期对手揭露；群像与代际铺陈仍要克制'},
    {'id': 't4', 'name': '长篇', 'word_range': [900000, 1500000], 'chapter_min': 3000, 'chapter_aim': 4000,
     'chapter_max': 5000, 'volume_count': 8, 'chapters': 300, 'chapter_window': [250, 360],
     'note': '多线并行、次要人物弧线与多次代价递进；再多的人物网需要更长篇幅'},
    {'id': 't5', 'name': '超长', 'word_range': [1800000, 3600000], 'chapter_min': 3000, 'chapter_aim': 4500,
     'chapter_max': 6000, 'volume_count': 10, 'chapters': 600, 'chapter_window': [489, 666],
     'note': '群像规模的多线交织、反复的势力更替与长期伏笔回收；对节奏控制要求最高'},
)
# The default direction of the opening gates: male-channel long-form web fiction as it is
# serialised on 起点/番茄. It says how a cold option writer should shape a proposal, never what the
# author is allowed to choose — the author's own words, or an option already chosen, always win over
# this default, and a gate that conflicts with it is not a protocol error.
OPENING_DIRECTION = (
    '默认面向起点/番茄长篇：先有足以改变社会运行的大脑洞，再找具体人物的切入口；作者已选题材与限制优先。',
    '脑洞推演规则→日常后果→利益重组→长期冲突；奇名、外挂标签和境界数量不能替代这条因果链。',
    '世界先看全貌：空间边界、历史断层、多方文明或制度、持续矛盾与终极谜题相互关联；世界不只为主角服务。',
    '格局同时扩大行动能力、认知与责任：个人求生可以牵动秩序存亡，升级不靠反复换地图、加更强敌人。',
    '开篇从可感知的危机或异常进入，早期兑现一次重要行动、发现或关系变化；宏大历史通过物件、制度和冲突逐步显影。',
    '主角有可反复运用的稀缺优势，来源、条件、代价与上限由世界规则解释；旧人物、承诺和付出在后续阶段仍有作用。',
    '情绪兑现服从题材：成长、智斗、探索、建设、守护均可，不强制每三五章打脸或每卷换敌；语感服从作者所选文风。',
    '参考代表作品的构造方法，不复制专有体系、人物关系和标志性桥段；短篇只展开宏大世界的一个切面，现实题材不强加诸天与神明。',
)
# Per-gate emphasis. Every gate of the current gate set declares one, so the gate set cannot be
# redesigned without saying what the default direction means for each gate (a guard test derives
# that requirement from the gate table itself).
OPENING_DIRECTION_GATES = {
    'genre': '男频题材要连承诺一起给：明确读者期待的情绪体验，别在第一门锁死主角职业与局部事件。',
    'premise': '核心规则改变整个社会：给出普通人、组织与文明三种后果，及一条能贯穿全书的问题。',
    'voice': '决定人称、视角与阅读质地；紧张、诙谐、厚重或诗性均可，场景展示所选声音。',
    'scale': '体量决定本书展开多少世界层次，不等于世界本身有多大；本门只选档位。',
    'world': '把空间、历史、文明、长期矛盾与谜题连接成世界架构，位阶和资源由其生长。',
    'ladder': '从终局问题倒推抵达路径；每一级写清认知、责任与规则的变化，旧世界仍参与新冲突。',
    'origin': '在已定世界中选择主角来历；说明他与历史、文明或异常规则的联系及最初可知边界。',
    'edge': '优势是进入世界矛盾的方式；条件、供料和代价来自已定规则，不能单方面豁免规则。',
    'protagonist': '私人欲望与世界问题相连，但开局保留真实局限、行动理由及会付出代价的底线。',
    'relationships': '关系双方各有目标和所属秩序，能够协作也可能在同一危机中作出相反选择。',
    'opposition': '个人对手、利益网络与根本矛盾相连；明确各方为何无法轻易退让，以及胜利如何改变局面。',
    'payoff': '安排早期承诺、阶段回报与终局回应；真相揭开仍有行动代价，文明问题回到具体人的命运。',
    'title': '提炼独特世界意象或清晰卖点，短名与搜索式长名均可，不按一种标题模板限制题材。',
}
SCALE_WINDOW = 3          # how many consecutive tiers one board shows
# How the pipeline itself scales with the chosen size class. Gates, world domains and design
# dispatches used to be constants, so a three-chapter book paid the same pre-prose dispatch count
# as a serial (measured on a real micro project: 59 of 81 dispatches happened before the first
# word). v2 keeps exactly one shape decision per tier: whether the volume outline dispatch also
# drafts the chapter outlines of the volumes it just designed. On the smallest tiers a volume's
# chapter outline is a few hundred characters of deltas, so splitting it into a second cold
# session only buys latency; the combined receipt is validated by both contracts (the volume
# outline and the chapter outline) before either half is installed. Tiers that keep the separate
# dispatch say so here, and a guard test derives the requirement from the tier table itself, so a
# new tier cannot arrive without declaring its shape.
PIPELINE_SHAPES = {
    't0': {'merge_chapter_outline': True},
    't1': {'merge_chapter_outline': True},
    't2': {'merge_chapter_outline': False},
    't3': {'merge_chapter_outline': False},
    't4': {'merge_chapter_outline': False},
    't5': {'merge_chapter_outline': False},
}


def tier_of(contract):
    """The tier row a contract's chapter band was sized to, or None for a custom band."""
    return next((row for row in SCALE_TIERS
                 if row['chapter_min'] == contract.get('chapter_min')
                 and row['chapter_max'] == contract.get('chapter_max')), None)
# Male-channel serials live in the long tiers, so the first board opens on 标准/长篇/超长; 精简 and
# 微型 stay one 换组 away for an author who wants something shorter.
SCALE_DEFAULT_WINDOW = 3
# What a structural option hands the author: a size ladder, never raw numbers to invent.
STRUCTURAL_CONTRACT = ('每个方案给 id、title 档位名（含卷数与字数区间）、premise 用一句话写清总字数、卷数、'
                       '每章字数与章数、tradeoff 说明这一档比相邻档多买到什么、少买到什么，value 照档位表逐字填。'
                       '不给 pitch/scene/driver，不写创意方法，不自行改动档位数字。')

# Single authority for the author contract: field, kind, default, whether the guided opening
# must preserve it, and whether an empty value is a valid skeleton entry. The delivery
# template, the validator and the alignment check are all derived from this table.
# `opening` declares an opening/2 choice's sole source: (gate, value key). A None key
# takes that gate's complete value, whose keys are declared by the field's shape.
CONTRACT_TYPES = {
    'text': (str,),
    'int': (int,),
    'bool': (bool,),
    'band': (list,),
    'rows': (list,),
    'map': (dict,),
}
CONTRACT_FIELDS = (
    {'key': 'title', 'kind': 'text', 'default': '', 'alignment': True, 'opening': ('title', 'title')},
    {'key': 'reader_promise', 'kind': 'text', 'default': '', 'alignment': True, 'opening': ('genre', 'reader_promise')},
    {'key': 'ending', 'kind': 'text', 'default': '', 'alignment': True,
     'opening': {'*': ('ending', 'ending'), 3: ('payoff', 'ending')}},
    {'key': 'genre', 'kind': 'text', 'default': '', 'alignment': True, 'opening': ('genre', 'genre')},
    {'key': 'story_engine', 'kind': 'text', 'default': '', 'alignment': True,
     'opening': {'*': ('engine', 'story_engine'), 3: ('opposition', 'story_engine')}},
    {'key': 'opposition', 'kind': 'text', 'default': '', 'alignment': True,
     'opening': {'*': ('engine', 'opposition'), 3: ('opposition', 'opposition')}},
    # opening/3 makes the two decisions male-channel serials live on first-class contract terms: what
    # the protagonist's edge is and how it grows, and how the reader's payoff is scheduled. Optional
    # like every later field, so contracts written before opening/3 stay loadable.
    {'key': 'core_edge', 'kind': 'map', 'default': '', 'alignment': True, 'optional': True, 'since': 3,
     'shape': ('advantage', 'origin', 'growth', 'cost', 'ceiling'), 'opening': ('edge', None)},
    {'key': 'payoff_plan', 'kind': 'map', 'default': '', 'alignment': True, 'optional': True, 'since': 3,
     'shape': ('ways', 'cadence', 'hooks'), 'opening': ('payoff', 'plan')},
    # opening/5's core-idea gate. Four keys rather than one paragraph because each is checked: the
    # novelty is what the world gained, the first cause is what keeps pushing it, the stance is how
    # the protagonist stands to the rule system, and the dark side names where the world's malice
    # comes from. A public setting can be reused for free; the novelty is the part that is owned.
    {'key': 'core_premise', 'kind': 'map', 'default': '', 'alignment': True, 'optional': True, 'since': 5,
     'shape': ('novelty', 'first_cause', 'stance', 'dark_side'), 'opening': ('premise', None)},
    # opening/5's payoff anchor: what must be delivered by which chapter, so a grand world still
    # proves itself inside the window the platforms actually measure.
    {'key': 'promise_anchor', 'kind': 'map', 'default': '', 'alignment': True, 'optional': True, 'since': 5,
     'shape': ('deliverable', 'deadline_chapter'), 'opening': ('payoff', 'anchor')},
    {'key': 'world_premise', 'kind': 'text', 'default': '', 'alignment': True},
    # opening/5's world gate: the reader-visible ladder and the hard currency, structured because
    # the world model has to keep them verbatim (`powers` / `economy` records of the same name).
    # Unstructured, they were prose in `world_premise` that the world dispatch re-invented.
    # opening/6 adds the five-part architecture; the same table names its world destinations.
    {'key': 'world_architecture', 'kind': 'map', 'default': '', 'alignment': True,
     'optional': True, 'since': 6, 'shape': tuple(row[0] for row in WORLD_ARCHITECTURE),
     'opening': ('world', 'architecture')},
    {'key': 'world_tiers', 'kind': 'rows', 'default': [], 'alignment': True, 'optional': True, 'since': 5,
     'shape': ('name', 'condition', 'gain', 'cost', 'limit'), 'exact': True, 'blank': False, 'count': 1,
     'opening': ('world', 'tiers')},
    {'key': 'world_resource', 'kind': 'map', 'default': '', 'alignment': True, 'optional': True, 'since': 5,
     'shape': ('name', 'source', 'allocator'), 'opening': ('world', 'resource')},
    # opening/5's 格局 gate: the opening's visible boundary, the grade the ending faces, the layer
    # that survives every escalation, and the ladder the volumes are required to walk in order.
    {'key': 'world_scale', 'kind': 'map', 'default': '', 'alignment': True, 'optional': True, 'since': 5,
     'shape': ('opening', 'terminal', 'unchanged'), 'opening': ('ladder', 'scale')},
    {'key': 'world_ladder', 'kind': 'rows', 'default': [], 'alignment': True, 'optional': True, 'since': 5,
     'shape': ('stage', 'scope', 'growth', 'new_rule', 'cost'), 'exact': True, 'blank': False, 'count': 1,
     'opening': ('ladder', 'ladder')},
    {'key': 'voice', 'kind': 'text', 'default': '', 'alignment': True, 'opening': ('voice', 'voice')},
    # Decided by the author at the opening gates since opening/2. Optional keeps a hand-written
    # `init --contract` file and every contract written before opening/2 loadable; a guided opening of
    # version 2 still has to carry them, because its gates chose them.
    {'key': 'tone', 'kind': 'text', 'default': '', 'alignment': True, 'optional': True, 'since': 2, 'opening': ('genre', 'tone')},
    {'key': 'theme', 'kind': 'text', 'default': '', 'alignment': True, 'optional': True, 'since': 2,
     'opening': {'*': ('ending', 'theme'), 3: ('payoff', 'theme')}},
    {'key': 'pov', 'kind': 'text', 'default': '', 'alignment': True, 'optional': True, 'since': 2,
     'opening': {'*': ('pov', 'pov'), 3: ('voice', 'pov')}},
    {'key': 'allow_special_mechanism', 'kind': 'bool', 'default': None, 'alignment': True, 'opening': ('world', 'allow_special_mechanism')},
    {'key': 'red_lines', 'kind': 'rows', 'default': [], 'alignment': True, 'optional': True},
    {'key': 'style_traits', 'kind': 'rows', 'default': [], 'alignment': True, 'opening': ('voice', 'style_traits')},
    {'key': 'relationships', 'kind': 'rows', 'default': [], 'alignment': True, 'opening': ('relationships', 'relationships')},
    {'key': 'world_rules', 'kind': 'rows', 'default': [], 'alignment': True},
    {'key': 'protagonist_setup', 'kind': 'map', 'default': '', 'alignment': True,
     'shape': ('id', 'name', 'identity', 'desire', 'limit'), 'opening': ('protagonist', None)},
    # opening/4's origin gate: what the protagonist brings into the story (魂穿/身穿/本土/其他) and what
    # it costs him. A field of its own rather than a key inside `protagonist_setup`, because adding a
    # key to that shape would reject every contract written before this version.
    {'key': 'protagonist_origin', 'kind': 'map', 'default': '', 'alignment': True, 'optional': True,
     'since': 4, 'shape': ('family', 'arrival', 'cost'), 'opening': ('origin', None)},
    {'key': 'entities', 'kind': 'rows', 'default': [], 'alignment': True},
    {'key': 'initial_resources', 'kind': 'rows', 'default': [], 'alignment': False},
    {'key': 'volumes', 'kind': 'rows', 'default': [], 'alignment': True,
     'shape': ('id', 'purpose', 'end'), 'blank': False, 'count': 1},
    {'key': 'word_range', 'kind': 'band', 'default': [], 'alignment': False, 'opening': ('scale', 'word_range')},
    {'key': 'chapter_min', 'kind': 'int', 'default': None, 'alignment': True, 'opening': ('scale', 'chapter_min')},
    {'key': 'chapter_max', 'kind': 'int', 'default': None, 'alignment': True, 'opening': ('scale', 'chapter_max')},
    {'key': 'chapter_aim', 'kind': 'int', 'default': None, 'alignment': True, 'opening': ('scale', 'chapter_aim')},
    # Legacy review-pipeline knobs. v2 has no reviewer dispatches, so nothing reads them any
    # more; they stay declared because a project written under the old pipeline still carries
    # them and must keep loading. See references/protocol.md for the retirement note.
    {'key': 'planning_window', 'kind': 'int', 'default': 3, 'alignment': False, 'legacy': True},
    {'key': 'review_interval', 'kind': 'int', 'default': 10, 'alignment': False, 'legacy': True},
    {'key': 'review_chunk', 'kind': 'int', 'default': 3, 'alignment': False, 'legacy': True},
    {'key': 'verification', 'kind': 'text', 'default': 'full', 'alignment': False, 'legacy': True},
    {'key': 'narrative_tracking', 'kind': 'bool', 'default': True, 'alignment': False},
    {'key': 'review_fanout', 'kind': 'int', 'default': 3, 'alignment': False, 'legacy': True},
    {'key': 'editorial_features', 'kind': 'bool', 'default': True, 'alignment': False},
    {'key': 'scope_append_limit', 'kind': 'int', 'default': 3, 'alignment': False},
    # Step three of the five-step pipeline: one outline per volume, written from the world model and
    # the opening choices, and delivered complete in a single receipt. The band is [2000, 3000]
    # 汉字: the author's floor is 2000, 2500 is the target, and the ceiling keeps a volume's outline
    # from growing into a cost that every later dispatch pays for. `scope=all` drafts every volume
    # before the first word; `rolling` drafts each volume just before it is entered.
    {'key': 'volume_outline', 'kind': 'map', 'default': policy_default('volume_outline'),
     'alignment': False, 'optional': True},
    # Step four: the per-chapter outline that carries the drift declarations. `words` bounds each
    # chapter's synopsis, not the delta rows — those are as long as the state they describe.
    # `scope=volume` builds a volume's chapter outlines just before writing it; `all` builds every
    # volume's up front, which is what an author who wants the whole resource chain resolved before
    # the first word should choose.
    {'key': 'chapter_outline', 'kind': 'map', 'default': policy_default('chapter_outline'),
     'alignment': False, 'optional': True},
    # v2.1: literary quality is carried by style, not by a reviewer. The author's spec is
    # qualitative (contract voice/tone, a volume's trend, a chapter's execution points); these are
    # the tolerances the engine applies to the proxies it can compute for free — see style.py.
    # `repetition` is an absolute in-chapter share, the others are relative deviations from the
    # approved first chapter, and `person` is 1 meaning "the narration person must match".
    {'key': 'style_window', 'kind': 'map', 'default': policy_default('style_window'),
     'alignment': False, 'optional': True},
    {'key': 'anchors', 'kind': 'rows', 'default': [], 'alignment': False, 'optional': True},
    {'key': 'links', 'kind': 'rows', 'default': [], 'alignment': False, 'optional': True},
    {'key': 'initial_facts', 'kind': 'rows', 'default': [], 'alignment': False, 'optional': True},
    {'key': 'places', 'kind': 'rows', 'default': [], 'alignment': False, 'optional': True},
    {'key': 'placements', 'kind': 'map', 'default': {}, 'alignment': False, 'optional': True},
    {'key': 'arcs', 'kind': 'rows', 'default': [], 'alignment': False, 'optional': True},
)
# Fields the engine projects instead of the author deciding them. They may still travel in an
# opening choice so the board can show them, but no alignment check compares them: comparing a
# projection against the decision it was projected from is how a derived field becomes a conflict.
DERIVED_FIELDS = ('word_range',)
CONTRACT_KEYS = tuple(row['key'] for row in CONTRACT_FIELDS)
# Every field declared as an alignment decision, regardless of opening version.
# The version-aware view is alignment_for(version); this one answers "which fields
# ever participate", which the opening tests assert the template covers.
CONTRACT_ALIGNMENT = tuple(row['key'] for row in CONTRACT_FIELDS if row['alignment'])


def opening_source(row, version):
    """Which gate and value key decide a contract field for one opening version.

    A tuple means every version. A dict keys by version, and **falls forward**: the newest numeric
    entry at or below this version wins, and `'*'` covers anything older than the first redesign.

    The falling-forward rule is what keeps a new gate set from becoming five hand-edited copies.
    opening/4 only inserted a gate in the middle of the order — every field it did not re-source must
    keep reading the gate that opening/3 gave it (pov ← voice, ending/theme ← payoff, story_engine and
    opposition ← opposition). Resolving `4` straight to `'*'` silently re-pointed those five fields at
    v1's gate ids, which no longer exist, and the mismatch only surfaced later as a KeyError while
    building a contract. Returns None when this version does not decide the field at all.
    """
    source = row.get('opening')
    if isinstance(source, dict):
        declared = [(key, value) for key, value in source.items() if type(key) is int and key <= version]
        source = max(declared, key=lambda pair: pair[0])[1] if declared else source.get('*')
    return source


def alignment_for(version):
    """The alignment fields an opening of this version actually decides.

    A contract written before opening/2 never chose a tone, theme or view, so those fields must not be
    read back as author decisions it failed to keep.
    """
    return tuple(row['key'] for row in CONTRACT_FIELDS
                 if row['alignment'] and row.get('since', 1) <= version)
CHARACTERS = ('name', 'role', 'desire', 'limit', 'knowledge_boundary')
POLICY_FIELDS = ('forbidden_terms', 'forbidden_name_chars')
# Where the author's lexical rules are enforced, declared per task stage. One table, used both to
# run the check and to tell a worker exactly which of its fields are inspected, so a dispatch
# instruction can never claim coverage the program does not perform.
#   terms: fields whose text must avoid the forbidden terms
#   names: fields whose text must avoid the forbidden name characters
ENFORCEMENT = {
    'opening_options': {'terms': ('title', 'premise', 'driver', 'tradeoff', 'fit_reason', 'value'),
                        'names': ('value.name',)},
    'world_model': {'names': ('characters.name',)},
    'volume_outline': {'terms': ('volumes',)},
    'chapter_outline': {'terms': ('chapters',), 'names': ('new_entities',)},
    'write': {'terms': ('title', 'prose')},
    'repair': {'terms': ('title', 'prose')},
    'redesign': {'terms': ('title', 'prose')},
    'opening_contract': {'terms': ('title',)},
}
POLICY_NOTE = ('本块是当前生效的项目字面约定：只覆盖上方 scope 列出的字段，越出范围的玩法不受检查；'
               '违反会以 literal_policy 拒绝并给出 found 列表。作者改规则用 lexical 命令保存原话，规则逐版留档。')
# The author-facing delivery contract for a proposed option: proposals, not arguments. The lens
# shapes how an option is found; it never appears in what the author reads.
OPTION_CONTRACT = ('每个方案给 id、title 短标题（真正可用的名字，不是「待定」这类占位符）、pitch 一句能记住的话（≤40字，不得出现透镜名或方法词）、'
                   'scene 2～3 个可落笔的具体画面（谁、在哪、什么东西、正要做什么，每条≥12字）、'
                   'premise 写清这一版的结果与收益（读者拿到什么、将触及什么规则、历史或文明问题）、driver 这一版如何推进（只写故事动作）、'
                   'tradeoff 写清两半：确定要付出的代价，与可能发生的风险（与同组另外两案相比）、'
                   'fit_reason 与已选方向的具体接口（承接哪条选择、因此改变了什么）、value 按本门字段。'
                   ' 同组方案在本门负责的规则、立场或体验上拉开差距；后门沿用已定世界，不靠推翻前门换方案。'
                   ' 方案里出现的数字必须前后自洽：次数、每次的量与总量要对得上（每次扣三岁、全书六次，总量就是十八年），'
                   ' 不要断言别的门才决定的数量，也不要让观感描述冒充算术。')


def _placeholder(row):
    if row['kind'] in ('rows', 'band'):
        if row.get('optional'):
            # An optional rows field blanks to its own default (an empty array), never to a row of
            # blanks: a template that invented a blank decision would then be refused by the very
            # shape check that reads it (and a pre-opening/5 project's template must stay loadable).
            return copy.deepcopy(row['default'])
        if row.get('shape'):
            entries = [{field: (0 if field == 'end' else '') for field in row['shape']}]
            return entries * row.get('count', 1)
        return copy.deepcopy(row['default'])
    if row['kind'] == 'map':
        if not row.get('shape') and isinstance(row['default'], dict):
            return copy.deepcopy(row['default'])
        return {field: '' for field in row.get('shape', ())}
    if row['kind'] == 'int':
        return row['default'] if type(row['default']) is int and row['default'] > 0 else 0
    return copy.deepcopy(row['default'])


def contract_skeleton():
    """A contract-shaped object carrying every key; never a valid contract on its own."""
    return {row['key']: _placeholder(row) for row in CONTRACT_FIELDS}


def contract_errors(raw):
    """Mechanical shape check against CONTRACT_FIELDS. Returns complaints, never raises."""
    complaints = []
    if not isinstance(raw, dict):
        return ['约定须为对象。']
    for unknown in sorted(set(raw) - set(CONTRACT_KEYS)):
        complaints.append('未知约定字段：' + unknown)
    for row in CONTRACT_FIELDS:
        key, kind = row['key'], row['kind']
        if key not in raw:
            if not row.get('optional'):
                complaints.append('缺少约定字段：' + key)
            continue
        value = raw[key]
        if kind == 'band':
            # An empty band means "not decided here": the total is a projection of the chapter
            # count and the per-chapter range, and validate_contract derives it from those.
            if value == []:
                continue
            if not isinstance(value, list) or len(value) != 2 or not all(type(n) is int and n > 0 for n in value) \
                    or value[0] > value[1]:
                complaints.append('word_range 须为有效总汉字区间。')
            continue
        if kind == 'rows':
            if not isinstance(value, list):
                complaints.append(key + ' 须为数组。')
            elif not value and row.get('optional'):
                # An empty array in an optional rows field means "not declared here" — the same thing
                # its absence means. A template that carries the field blank (a pre-open... a project
                # opened under an older protocol, or an imported contract) must not be refused for it;
                # a guided opening still requires it through the alignment check, not through shape.
                pass
            elif row.get('blank') is False and len(value) < row.get('count', 1):
                complaints.append(key + ' 须提供至少 ' + str(row.get('count', 1)) + ' 条完整记录。')
            elif row.get('exact') and row.get('shape'):
                # A row that declares `exact` states its whole key set and gives every key a value:
                # an undeclared or blank key inside a structured row is the same defect as an
                # undeclared contract field, only one level down. A hand-written or imported contract
                # bypasses the opening gate's per-value checks, so the shape check is its only guard
                # (adversarial review F2). `volumes` stays non-exact because the engine derives
                # `first` onto its rows.
                allowed = set(row['shape'])
                if any(not isinstance(entry, dict) or set(entry) != allowed
                       or not all(text(entry[field]) for field in allowed) for entry in value):
                    complaints.append(key + ' 的每条记录只能有这些字段，且每项都要写实：' + '/'.join(row['shape']))
            continue
        if kind == 'map':
            if not isinstance(value, dict) or any(field not in value for field in row.get('shape', ())):
                complaints.append(key + ' 须包含字段：' + '/'.join(row.get('shape', ())))
            continue
        if kind == 'text':
            if not text(value):
                complaints.append(key + ' 须为非空文本。')
            continue
        if kind == 'bool':
            if type(value) is not bool:
                complaints.append(key + ' 须为布尔值。')
        elif type(value) is not int or value <= 0:
            complaints.append(key + ' 须为正整数。')
    return complaints



class Error(Exception):
    def __init__(self, code, message, details=None):
        super().__init__(message)
        self.code, self.message = code, message
        self.details = details or {'recover': '按当前任务模板修正后重提；不要改库或替换任务身份。'}

    def as_dict(self):
        return {'error': self.code, 'message': self.message, 'details': self.details}


def require(ok, code, message, details=None):
    if not ok:
        raise Error(code, message, details)


def text(value):
    return isinstance(value, str) and bool(value.strip())


def dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(dump(value).encode('utf-8')).hexdigest()


def han_count(prose):
    return sum('\u3400' <= c <= '\u4dbf' or '\u4e00' <= c <= '\u9fff' or '\U00020000' <= c <= '\U0003134f' for c in prose)


@dataclass(frozen=True)
class Job:
    stage: str
    chapter: int
    scope: str = 'chapter'
    first: int = 0
    last: int = 0
    payload: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class Outcome:
    book: Dict[str, Any]
    chapter: Optional[Dict[str, Any]] = None

