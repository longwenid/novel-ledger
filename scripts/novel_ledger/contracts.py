"""Shared wire contracts and value utilities; no I/O or domain imports."""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

VERSION = '1.5.0'
SCHEMA = 'novel-ledger/3'
# The guided opening has its own protocol version, carried by the creation state itself. It is not the
# database schema: a new gate set only changes a JSON document inside the book record, so raising the
# storage version would lock every existing project out for no benefit. A project whose creation state
# is version 1 keeps the gate set it was opened with.
OPENING_VERSION = 3
TASK = 'novel-ledger.task/1'
RESULT = 'novel-ledger.result/1'
# The dispatch's own copy of who it is: data for cross-checking, never a permission.
IDENTITY = 'novel-ledger.identity/1'
FACT_CHECKS = ('coverage', 'continuity', 'resources', 'knowledge', 'time', 'world_rules', 'space')
READER_CHECKS = ('read_on', 'character', 'change', 'emotion_cost', 'language', 'repetition', 'substance')
LONG_CHECKS = ('causality', 'character_arcs', 'payoffs', 'pacing', 'world_rules', 'coverage')
DESIGN_CHECKS = ('author_constraints', 'causality', 'characters', 'disclosure', 'scale')
WORLD_CHECKS = ('choice_alignment', 'rule_consistency', 'spatial_connections', 'historical_causes',
                'faction_interests', 'economic_consequences', 'social_pressure', 'character_boundaries', 'disclosure', 'story_capacity')
# Check lists are part of the wire contract: a book already reviewed must keep being judged by the
# list it was reviewed against, or adding a check would retroactively fail every finished project.
# Receipts carry their own `checks_version` (absent means the original set); new submissions are
# always judged by CHECKS_VERSION, so raising it only affects work yet to be reviewed.
CHECKS_VERSION = 2
CHECK_SETS = {1: {'fact': FACT_CHECKS, 'reader': READER_CHECKS, 'design': DESIGN_CHECKS,
                  'world': WORLD_CHECKS, 'long': LONG_CHECKS}}
CHECK_SETS[2] = {'fact': FACT_CHECKS + ('narrative',),
                 'reader': READER_CHECKS + ('disclosure', 'pacing'),
                 'design': DESIGN_CHECKS + ('threads',),
                 'world': WORLD_CHECKS, 'long': LONG_CHECKS + ('bridges', 'disclosure')}
EDITORIAL_VERSION = 3
CHECK_SETS[3] = {**CHECK_SETS[2],
                 'fact': CHECK_SETS[2]['fact'] + ('character_consistency', 'stable_facts'),
                 'reader': CHECK_SETS[2]['reader'] + ('dialogue_identity', 'voice_match'),
                 'long': CHECK_SETS[2]['long'] + ('voice_evolution', 'revision_intent')}
# Version 4 exists because the opening now lets the author choose the narrative person and scope, and a
# chosen view has to be verified by an independent reader. It is only dispatched for contracts that
# actually declare `pov`: an imported contract without that field must not be judged against a view
# nobody chose.
POV_CHECKS_VERSION = 4
CHECK_SETS[4] = {**CHECK_SETS[3], 'reader': CHECK_SETS[3]['reader'] + ('pov_consistency',)}


def checks_for(version, kind):
    table = CHECK_SETS.get(version)
    require(table is not None, 'checks_version', '未知的检查清单版本。',
            {'known_versions': sorted(CHECK_SETS), 'recover': '回执按下发的模板版本填写，不要沿用旧版本号。'})
    entries = table.get(kind)
    require(entries is not None, 'checks_kind', '未知的检查类别。',
            {'kind': kind if isinstance(kind, str) else type(kind).__name__, 'known_kinds': sorted(table)})
    return entries


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
VOLUME_OUTLINE_CAPABILITY = 'volume-outline/1'
SCENE_MEMORY_CAPABILITY = 'scene-memory/1'
HOOK_LINKS_CAPABILITY = 'hook-links/1'
CAPABILITIES = {
    'editorial': (EDITORIAL_CAPABILITY,),
    'understanding': (UNDERSTANDING_CAPABILITY,),
    'scene_identity': (SCENE_IDENTITY_V1, SCENE_IDENTITY_CAPABILITY),
    'reading_dependencies': (READING_DEPENDENCIES_CAPABILITY,),
    'opening_bounds': (OPENING_BOUNDS_CAPABILITY,),
    'volume_outline': (VOLUME_OUTLINE_CAPABILITY,),
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
FIRST_READ = ('desire', 'obstacle', 'change', 'read_on_reason')
# Findings a reviewer may raise. The first three describe work a writer can repair; 'author' means
# no rewrite can settle it — the premise itself must be decided, so it is routed to the author
# instead of becoming a repair target (and it is the only severity that carries `decision`).
FINDING_SEVERITIES = ('blocker', 'quality', 'note', 'author')
AUTHOR_SEVERITY = 'author'
# Same shape as the author block this engine already pauses on, plus an id for provenance.
AUTHOR_DECISION_FIELDS = ('id', 'question', 'options')
DECISION_OPTION_FIELDS = ('label', 'impact')
# One pending decision at a time is the engine's existing invariant (a single author_block that
# `resume` refuses to bypass), so a receipt may hand up at most this many author-level findings.
AUTHOR_DECISIONS_PER_RECEIPT = 1
# Reviews taken while the book may still be paused for the author, before prose is committed to a
# chapter: only there can a design question be handed up and answered. Chapter-level reviews keep
# the strict default, so a finding there always describes work a writer can do right now.
AUTHOR_CHANNEL_STAGES = frozenset({'world_review', 'outline_review', 'design_review', 'contract_review',
                                   'alignment_review', 'scope_review', 'scope_synthesis'})
REPAIRS = 2
REDESIGNS = 1
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
FORM_ARTIFACTS = ('input.json', 'result.template.json')
# Brainstorm methods. A lens is a way to make the next option genuinely different, not a label:
# the axis spends one slot of the choice, the method says how to vary it. Kept beside the
# contract fields because option quality is part of the author-facing contract.
LENSES = (
    ('混搭', '让两种差异化设定深度参与因果，双方都必须改变故事走向；只贴皮不算混搭。',
     '提出两个各自成立的设定，再指出它们互相牵制的具体后果。'),
    ('倒置', '颠覆类型固有假定，并把反转在终局回溯闭环；为求新奇而无回收不算。',
     '先写清被倒置的那条公理，再给出终局如何回到它。'),
    ('代价', '让突破必须支付不可逆的实质代价，代价直接改变人物后续抉择；一次性的痛感不算。',
     '写清代价的具体形态，以及它如何限制下一次选择。'),
    ('限制', '用严苛限制驱动破局策略，让主角靠判断而非能力取胜；限制可随时取消不算。',
     '写清限制的边界与破局要用的具体手段。'),
    ('认知差', '用信息差制造不可逆选择，让知道本身带来风险；靠误会拖延不算。',
     '写清谁知道什么、这层差如何逼出选择。'),
    ('规则推演', '把一条底层规则推到社会结构与经济秩序的极限；只在中段使用不算。',
     '写清规则的边界，以及它挤压出的制度、代价与冲突。'),
    ('绑定', '让主角与核心对手在物理或命运上深度绑定，无法简单消灭；换个人当对手不算。',
     '写清绑定的机制，以及双方各自被限制的动作。'),
    ('闭环', '让终局与初始预期形成有据可依的反转，全程伏笔支撑；临时改口不算。',
     '写清初始预期、终局事实与中间需要埋设的线索。'),
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
    {'id': 't0', 'name': '微型', 'word_range': [34000, 59500], 'chapter_min': 2000, 'chapter_aim': 2600,
     'chapter_max': 3500, 'volume_count': 1, 'chapters': 17, 'chapter_window': [14, 19],
     'note': '单一事件的完整闭环：一条主线、两三个人物，没有卷内转折与支线并行的余地'},
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
# The default direction of the ten opening gates: male-channel long-form web fiction as it is
# serialised on 起点/番茄. It says how a cold option writer should shape a proposal, never what the
# author is allowed to choose — the author's own words, or an option already chosen, always win over
# this default, and a gate that conflicts with it is not a protocol error.
OPENING_DIRECTION = (
    '开篇三章内给出明确压力与第一个可见收益（脱困、打脸、拿到资源或关键线索），不开长篇设定铺垫。',
    '主角有一条稀缺优势或可升级的金手指，升级有明确条件与代价，不靠忽然变强。',
    '承诺读者看他怎么赢：每卷对手与舞台抬高一级（局部→势力→体系），冲突梯度能持续加码。',
    '爽点与悬念交替：短线三到五章一个小兑现，长线留一个更大的目标；章末留钩，静章也要有信息或关系变化。',
    '冲突落到具体利益与身份处境（资源、名额、地位、复仇、守护、真相），少写纯理念之争。',
    '题材走男频主流落点：玄幻修真、都市异能或职场逆袭、历史权谋、科幻末世、悬疑探案及其混搭。',
    '语感偏连载网文：短句推进、对白带信息、解释服从场景；不用纯文学式的氛围铺陈与心理长段。',
    '体量按长篇连载预期起步，默认窗口落在标准到超长之间，需要短篇或微型时换组向下取。',
)
# Per-gate emphasis. Every gate of the current gate set declares one, so the gate set cannot be
# redesigned without saying what the default direction means for each gate (a guard test derives
# that requirement from the gate table itself).
OPENING_DIRECTION_GATES = {
    'genre': '男频题材要连承诺一起给：爽点是什么、读者看谁赢谁、他在这个故事里想要什么。',
    'voice': '叙述先定人称与视角范围：贴住主角的限知视角便于持续给爽点与信息差；语感短句推进、对白带信息。',
    'scale': '长篇连载体量：这一门只选档位，别在这里讨论剧情；相邻档的差别要落到节奏与线索数量上。',
    'edge': '金手指或稀缺优势要能被反复使用并升级：说清它怎么来、分几层、每层的条件与代价、上限在哪。',
    'protagonist': '主角处境要自带压力与上升通道，欲望具体可量化，底线会在关键选择上真的挡住他。',
    'relationships': '关系要同时给出助力和背叛风险（兄弟、师徒、对手绑定、家族），感情线定分量与处理方式，不是围着主角转的配角团。',
    'world': '世界机制要为冲突持续供料：规则清楚、边界可验证，能不断产出对手、资源与身份差，不做纯氛围设定。',
    'opposition': '对抗要能逐卷抬高一级（局部→势力→体系）：第一卷对手挡着什么利益、每次胜利换来多强的对手、终局面对谁。',
    'payoff': '兑现方式写清楚（脱困、打脸、升级、资源、地位、基建、复仇、争霸），短线三五章一个小兑现，章末留钩，终局要兑现开篇承诺的那场胜利。',
    'title': '书名按男频搜索习惯给：关键词直接点出题材与金手指或身份优势，一眼能看懂看点，不用意象化短名。',
}
SCALE_WINDOW = 3          # how many consecutive tiers one board shows
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
    {'key': 'world_premise', 'kind': 'text', 'default': '', 'alignment': True},
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
    {'key': 'entities', 'kind': 'rows', 'default': [], 'alignment': True},
    {'key': 'initial_resources', 'kind': 'rows', 'default': [], 'alignment': False},
    {'key': 'volumes', 'kind': 'rows', 'default': [], 'alignment': True,
     'shape': ('id', 'purpose', 'end'), 'blank': False, 'count': 1},
    {'key': 'word_range', 'kind': 'band', 'default': [], 'alignment': False, 'opening': ('scale', 'word_range')},
    {'key': 'chapter_min', 'kind': 'int', 'default': None, 'alignment': True, 'opening': ('scale', 'chapter_min')},
    {'key': 'chapter_max', 'kind': 'int', 'default': None, 'alignment': True, 'opening': ('scale', 'chapter_max')},
    {'key': 'chapter_aim', 'kind': 'int', 'default': None, 'alignment': True, 'opening': ('scale', 'chapter_aim')},
    {'key': 'planning_window', 'kind': 'int', 'default': 3, 'alignment': False},
    {'key': 'review_interval', 'kind': 'int', 'default': 10, 'alignment': False},
    {'key': 'review_chunk', 'kind': 'int', 'default': 3, 'alignment': False},
    {'key': 'verification', 'kind': 'text', 'default': 'full', 'alignment': False},
    {'key': 'narrative_tracking', 'kind': 'bool', 'default': True, 'alignment': False},
    {'key': 'review_fanout', 'kind': 'int', 'default': 3, 'alignment': False},
    {'key': 'editorial_features', 'kind': 'bool', 'default': True, 'alignment': False},
    {'key': 'scope_append_limit', 'kind': 'int', 'default': 3, 'alignment': False},
    {'key': 'volume_outline', 'kind': 'map', 'default': {'scope': 'rolling', 'words': 500, 'tolerance': 50}, 'alignment': False, 'optional': True},
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

    A tuple means every version; a dict keys by version with `'*'` as the fallback, so a gate can be
    redesigned in a later protocol without re-reading an old project's choices through the new gates.
    Returns None when this version does not decide the field at all.
    """
    source = row.get('opening')
    if isinstance(source, dict):
        source = source.get(version, source.get('*'))
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
    'book_plan': {'terms': ('intent', 'ending_conditions', 'nodes')},
    'volume_plan': {'terms': ('intent', 'ending_conditions', 'nodes', 'brainstorm', 'chapters', 'selection_reason')},
    'volume_outline': {'terms': ('chapters',)},
    'plan': {'terms': ('plans',), 'names': ('new_entities',)},
    'profiles': {'terms': ('profiles',)},
    'alignment_plan': {'terms': ('plan', 'designs')},
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
                   'premise 具体内容、driver 这一版如何推进（只写故事动作）、'
                   'tradeoff 选它要放弃什么（与同组另外两案相比的代价）、'
                   'fit_reason 与已选方向的具体接口（承接哪条选择、因此改变了什么）、value 按本门字段。')


def _placeholder(row):
    if row['kind'] in ('rows', 'band'):
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
            elif row.get('blank') is False and len(value) < row.get('count', 1):
                complaints.append(key + ' 须提供至少 ' + str(row.get('count', 1)) + ' 条完整记录。')
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

