"""Shared wire contracts and value utilities; no I/O or domain imports."""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, Optional
# The five-step pipeline is a protocol generation change: v2 removed every reviewer dispatch, so a
# task frozen by v1 (checks_version, obligations, blind first read, plan/book_plan stages) can no
# longer be executed by this build. The pipeline and storage carry independent version identifiers.
VERSION = '2.1.2'


SCHEMA = 'novel-ledger/5'


# The guided opening has its own protocol version, carried by the creation state itself. It is not the
# database schema: a new gate set only changes a JSON document inside the book record, so raising the
# storage version is independent; only the current guided-opening protocol is accepted.
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
    # repetition ceiling, and a retained person observation parameter. The
    # repetition ceiling is calibrated: ordinary Chinese prose measures 0.043~0.086 here, a chapter
    # that repeats one clause measures 0.79~0.99.
    'style_window': {'sentence': 0.35, 'paragraph': 0.35, 'dialogue': 0.40, 'repetition': 0.12, 'person': 1},
    'style_guard': 'observe',
    # The voice floor every project gets before its first chapter is approved: with no
    # author-approved anchor, shape metrics compare against this declared default instead of
    # silently not judging. A mainstream chapter profile (~3.2k han, ~180 sentences, ~18-char
    # sentence mean, ~0.25 short-sentence share, ~0.30 dialogue). Observe guard records the drift
    # as observations; strict makes it actionable. approve replaces this with the real anchor.
    'style_default_anchor': {
        'han': 3200, 'sentences': 180, 'sentence_mean': 18.0, 'sentence_short_share': 0.25,
        'paragraph_mean': 2.4, 'paragraph_max': 6.0, 'dialogue_share': 0.30, 'origin': 'default',
    },
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
    'revision_limit': 3,
    'fast_batch_chapters': 10,
    'technical_retries': 2,
    'worker_lease_seconds': 300,
    'single_delivery_lease_seconds': 3600,
    'controller_lease_seconds': 300,
    # Unattended supervision cadence: how often watch polls task status, and how long a silent
    # worker may hold a task before the host is told (`idle`). Both stay facts for the caller;
    # neither fires a redispatch on its own.
    'watch_poll_seconds': 20.0,
    'watch_idle_limit_seconds': 1800.0,
    # Adjacent-prose context: how many previous chapters the writer's required pack and the
    # continuity reviewer's regular window both carry in full. The sliding window keeps each
    # chapter's marginal cost at one new chapter.
    'adjacent_window_chapters': 2,
    # The reviewer's periodic deep re-read: every `cadence` chapters it reads `wide_window`
    # preceding chapters in full instead of the adjacent two, auditing a whole fast group at once.
    'continuity_wide_cadence': 10,
    'continuity_wide_window': 9,
    'design_stall_rounds': 3,
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
# The 2024-2026 male-channel research (validation/archive/opening5-spec.md §2) says the genre's live
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


# Frozen task capabilities declare the current protocol used by each component.
# Unknown values fail rather than silently changing how a field is interpreted.
EDITORIAL_CAPABILITY = 'editorial/1'


UNDERSTANDING_CAPABILITY = 'understanding/1'


SCENE_IDENTITY_CAPABILITY = 'scene-identity/2'


READING_DEPENDENCIES_CAPABILITY = 'reading-dependencies/1'


# The volume outline protocol changed shape in v2: a volume is now one outline per volume, complete
# in a single receipt, carrying its own nodes/threads and state boundaries, and the per-chapter rows
# live in the chapter outline that follows it. A task frozen under volume-outline/1 describes a batch
# of chapters instead, so this build refuses it rather than reinterpreting its fields.
VOLUME_OUTLINE_CAPABILITY = 'volume-outline/2'


SCENE_MEMORY_CAPABILITY = 'scene-memory/1'


HOOK_LINKS_CAPABILITY = 'hook-links/1'


CONTINUOUS_WRITING_CAPABILITY = 'continuous-writing/1'


CAPABILITIES = {
    'editorial': (EDITORIAL_CAPABILITY,),
    'understanding': (UNDERSTANDING_CAPABILITY,),
    'scene_identity': (SCENE_IDENTITY_CAPABILITY,),
    'reading_dependencies': (READING_DEPENDENCIES_CAPABILITY,),
    'volume_outline': (VOLUME_OUTLINE_CAPABILITY,),
    'scene_memory': (SCENE_MEMORY_CAPABILITY,),
    'hook_links': (HOOK_LINKS_CAPABILITY,),
    'continuous_writing': (CONTINUOUS_WRITING_CAPABILITY,),
}


def capabilities_for(task):
    """A frozen task's capabilities, with every value checked against this build.

    An absent optional capability is disabled. Every declared value must match the current protocol.
    """
    frozen = (task or {}).get('capabilities')
    require(isinstance(frozen, dict), 'capability', '任务 capabilities 须为对象。')
    unknown = sorted(str(key) + '=' + str(value) for key, value in frozen.items()
                     if value not in CAPABILITIES.get(key, ()))
    require(not unknown, 'capability', '任务冻结了本版本无法解释的能力值。',
            {'unknown': unknown, 'known': {key: list(values) for key, values in CAPABILITIES.items()},
             'recover': '该任务由不识别这些协议的版本冻结；取消后按当前协议重新派工。'})
    required = ('understanding', 'scene_identity', 'reading_dependencies')
    missing = sorted(set(required) - set(frozen))
    require(not missing, 'capability', '任务缺少当前协议的必需能力，须重新派工。', {'missing': missing})
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


# Bounded repair budgets: one chapter may spend this many rounds before the author is asked. Declared
# in DEFAULTS with every other shared number, and aliased here because the workflow reads them by name.
REPAIRS = DEFAULTS['repairs']


REDESIGNS = DEFAULTS['redesigns']


TIME_MARKERS = tuple('日天夜晨早晚午时年月春夏秋冬晓暮昏宵旬翌昨今明') + ('星期', '分钟', '秒钟')


DEFAULT_TERMS = ['账本', '入账', '回执']


# No character is banned by default: naming is the author's decision, so the name rule starts empty
# and the author fills it through `lexical` when a project needs one.
DEFAULT_NAME_CHARS = []


# Work-directory artifacts the controller may regenerate; everything else in a task directory
# is authored by a Worker and is never rewritten behind its back.
FORM_ARTIFACTS = ('input.json', 'result.template.json', 'brief.md', 'dispatch.md', 'catalog.md')


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
     'opening': ('payoff', 'ending')},
    {'key': 'genre', 'kind': 'text', 'default': '', 'alignment': True, 'opening': ('genre', 'genre')},
    {'key': 'story_engine', 'kind': 'text', 'default': '', 'alignment': True,
     'opening': ('opposition', 'story_engine')},
    {'key': 'opposition', 'kind': 'text', 'default': '', 'alignment': True,
     'opening': ('opposition', 'opposition')},
    # opening/3 makes the two decisions male-channel serials live on first-class contract terms: what
    # the protagonist's edge is and how it grows, and how the reader's payoff is scheduled. Optional
    # for direct imports; guided openings must align them with their selected gates.
    {'key': 'core_edge', 'kind': 'map', 'default': '', 'alignment': True, 'optional': True,
     'shape': ('advantage', 'origin', 'growth', 'cost', 'ceiling'), 'opening': ('edge', None)},
    {'key': 'payoff_plan', 'kind': 'map', 'default': '', 'alignment': True, 'optional': True,
     'shape': ('ways', 'cadence', 'hooks'), 'opening': ('payoff', 'plan')},
    # opening/5's core-idea gate. Four keys rather than one paragraph because each is checked: the
    # novelty holds the chosen premise, conventional or speculative; first_cause keeps it moving.
    # stance and dark_side keep their registered enums without requiring an invented rule.
    {'key': 'core_premise', 'kind': 'map', 'default': '', 'alignment': True, 'optional': True,
     'shape': ('novelty', 'first_cause', 'stance', 'dark_side'), 'opening': ('premise', None)},
    # opening/5's payoff anchor: what must be delivered by which chapter, so a grand world still
    # proves itself inside the window the platforms actually measure.
    {'key': 'promise_anchor', 'kind': 'map', 'default': '', 'alignment': True, 'optional': True,
     'shape': ('deliverable', 'deadline_chapter'), 'opening': ('payoff', 'anchor')},
    {'key': 'world_premise', 'kind': 'text', 'default': '', 'alignment': True},
    # opening/5's world gate: the reader-visible ladder and the hard currency, structured because
    # the world model has to keep them verbatim (`powers` / `economy` records of the same name).
    # Unstructured, they were prose in `world_premise` that the world dispatch re-invented.
    # opening/6 adds the five-part architecture; the same table names its world destinations.
    {'key': 'world_architecture', 'kind': 'map', 'default': '', 'alignment': True,
     'optional': True, 'shape': tuple(row[0] for row in WORLD_ARCHITECTURE),
     'opening': ('world', 'architecture')},
    {'key': 'world_tiers', 'kind': 'rows', 'default': [], 'alignment': True, 'optional': True,
     'shape': ('name', 'condition', 'gain', 'cost', 'limit'), 'exact': True, 'blank': False, 'count': 1,
     'opening': ('world', 'tiers')},
    {'key': 'world_resource', 'kind': 'map', 'default': '', 'alignment': True, 'optional': True,
     'shape': ('name', 'source', 'allocator'), 'opening': ('world', 'resource')},
    # opening/5's 格局 gate: the opening's visible boundary, the grade the ending faces, the layer
    # that survives every escalation, and the ladder the volumes are required to walk in order.
    {'key': 'world_scale', 'kind': 'map', 'default': '', 'alignment': True, 'optional': True,
     'shape': ('opening', 'terminal', 'unchanged'), 'opening': ('ladder', 'scale')},
    {'key': 'world_ladder', 'kind': 'rows', 'default': [], 'alignment': True, 'optional': True,
     'shape': ('stage', 'scope', 'growth', 'new_rule', 'cost'), 'exact': True, 'blank': False, 'count': 1,
     'opening': ('ladder', 'ladder')},
    {'key': 'voice', 'kind': 'text', 'default': '', 'alignment': True, 'opening': ('voice', 'voice')},
    # Direct imports may omit these fields; guided openings must carry the decisions their gates made.
    {'key': 'tone', 'kind': 'text', 'default': '', 'alignment': True, 'optional': True, 'opening': ('genre', 'tone')},
    {'key': 'theme', 'kind': 'text', 'default': '', 'alignment': True, 'optional': True,
     'opening': ('payoff', 'theme')},
    {'key': 'pov', 'kind': 'text', 'default': '', 'alignment': True, 'optional': True,
     'opening': ('voice', 'pov')},
    {'key': 'allow_special_mechanism', 'kind': 'bool', 'default': None, 'alignment': True, 'opening': ('world', 'allow_special_mechanism')},
    {'key': 'red_lines', 'kind': 'rows', 'default': [], 'alignment': True, 'optional': True},
    {'key': 'style_traits', 'kind': 'rows', 'default': [], 'alignment': True, 'opening': ('voice', 'style_traits')},
    {'key': 'relationships', 'kind': 'rows', 'default': [], 'alignment': True, 'opening': ('relationships', 'relationships')},
    {'key': 'world_rules', 'kind': 'rows', 'default': [], 'alignment': True},
    {'key': 'protagonist_setup', 'kind': 'map', 'default': '', 'alignment': True,
     'shape': ('id', 'name', 'identity', 'desire', 'limit'), 'opening': ('protagonist', None)},
    # opening/4's origin gate: what the protagonist brings into the story (魂穿/身穿/本土/其他) and what
    # it costs him. A field of its own rather than a key inside `protagonist_setup`, because adding a
    # key to that shape would make a direct contract import invent a decision.
    {'key': 'protagonist_origin', 'kind': 'map', 'default': '', 'alignment': True, 'optional': True,
     'shape': ('family', 'arrival', 'cost'), 'opening': ('origin', None)},
    {'key': 'entities', 'kind': 'rows', 'default': [], 'alignment': True},
    {'key': 'initial_resources', 'kind': 'rows', 'default': [], 'alignment': False},
    {'key': 'volumes', 'kind': 'rows', 'default': [], 'alignment': True,
     'shape': ('id', 'purpose', 'end'), 'blank': False, 'count': 1},
    {'key': 'word_range', 'kind': 'band', 'default': [], 'alignment': False, 'opening': ('scale', 'word_range')},
    {'key': 'chapter_min', 'kind': 'int', 'default': None, 'alignment': True, 'opening': ('scale', 'chapter_min')},
    {'key': 'chapter_max', 'kind': 'int', 'default': None, 'alignment': True, 'opening': ('scale', 'chapter_max')},
    {'key': 'chapter_aim', 'kind': 'int', 'default': None, 'alignment': True, 'opening': ('scale', 'chapter_aim')},
    {'key': 'narrative_tracking', 'kind': 'bool', 'default': True, 'alignment': False},
    {'key': 'editorial_features', 'kind': 'bool', 'default': True, 'alignment': False},
    {'key': 'scope_append_limit', 'kind': 'int', 'default': 3, 'alignment': False},
    {'key': 'revision_limit', 'kind': 'int', 'default': DEFAULTS['revision_limit'], 'alignment': False},
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
    # approved first chapter. Pronoun observations cannot determine actual narrative viewpoint.
    {'key': 'style_window', 'kind': 'map', 'default': policy_default('style_window'),
     'alignment': False, 'optional': True},
    {'key': 'style_guard', 'kind': 'text', 'default': DEFAULTS['style_guard'],
     'choices': ('observe', 'strict'), 'alignment': False, 'optional': True},
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


# The fields compared with the current guided opening's closed choices.
CONTRACT_ALIGNMENT = tuple(row['key'] for row in CONTRACT_FIELDS if row['alignment'])


def opening_source(row, version=OPENING_VERSION):
    """The current gate and value key that decide this contract field."""
    require(version == OPENING_VERSION, 'creation', '仅支持当前开书协议。')
    return row.get('opening')


def alignment_for(version=OPENING_VERSION):
    """Fields decided by the current guided opening."""
    require(version == OPENING_VERSION, 'creation', '仅支持当前开书协议。')
    return CONTRACT_ALIGNMENT


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


# Mechanical receipt fields for one opening board. Creative guidance lives in hatch.md.
OPTION_CONTRACT = ('options 为2～3项数组；每项给非空 id、title、premise、driver、tradeoff、fit_reason，'
                   'pitch 为不超过40字的非空文本，scene 为2～3条至少12字的文本，value 按当前门字段。'
                   '同组 id/title/premise/driver 不重复；方案文本不得自述创意方法。')


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
                # its absence means. A direct import may carry the field blank;
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
            elif row.get('choices') and value not in row['choices']:
                complaints.append(key + ' 须取 ' + '/'.join(row['choices']) + '。')
            continue
        if kind == 'bool':
            if type(value) is not bool:
                complaints.append(key + ' 须为布尔值。')
        elif type(value) is not int or value <= 0:
            complaints.append(key + ' 须为正整数。')
    return complaints


EXECUTION = 'novel-ledger.execution/1'

# Recovery is a role contract, shared by errors, dispatch cards and the CLI.
# Never suggest a controller operation to a dispatched worker.
CONTROLLER_ERRORS = frozenset((
    'session', 'session_reuse', 'worker_identity', 'worker_lease', 'worker_busy',
    'controller_lease', 'role_boundary', 'worker_boundary', 'stale_task',
    'writing_batch', 'technical_blocked', 'source_integrity', 'state_integrity',
    'projection', 'chain', 'schema_version',
    'host_authority', 'host_actor', 'authorization_replay', 'governance_integrity',
    'engine_changed', 'engine_recovery', 'continuity_identity', 'continuity_stale',
    'continuity_pending', 'continuity_settlement',
))

SINGLE_DELIVERY_STAGES = frozenset({'world_model', 'opening_contract', 'volume_outline', 'chapter_outline'})

CONTENT_ERRORS = frozenset((
    'alias', 'alias_conflict', 'amount', 'anchor', 'anchor_fixed', 'chapter_outline',
    'character_current', 'clock', 'custody', 'design_drift', 'development', 'dialogue',
    'draft', 'drift_check', 'drift_reason', 'elapsed_days', 'entity', 'entity_coverage',
    'evidence', 'evidence_scope', 'event', 'event_op', 'events', 'historical', 'hook',
    'hook_due', 'hook_extension',
    'hook_reference', 'initial_fact', 'insufficient_resource', 'knowledge', 'ledger', 'link',
    'literal_policy', 'move', 'opening_alignment', 'opening_diversity', 'opening_gate',
    'opening_option', 'opening_options', 'opening_scene', 'opening_voice', 'outline_alignment',
    'outline_state', 'patch', 'patch_base', 'path', 'path_time', 'perceive', 'place',
    'place_cycle', 'placement', 'precondition', 'reader_knowledge', 'reading_dependency',
    'relation', 'repair_scope', 'resource', 'resurrection', 'revision_outline', 'scene',
    'scene_identity', 'scene_time', 'schedule', 'spatial_protocol', 'state', 'story_closure',
    'story_criteria', 'story_dependency', 'story_node', 'story_precondition', 'story_protocol',
    'story_thread', 'thread_due', 'time_conflict', 'time_evidence', 'understanding',
    'understanding_reference', 'volume_outline', 'word_budget', 'world', 'world_alignment',
    'world_fields', 'world_id', 'world_identity', 'world_links', 'world_optional',
    'world_record', 'world_reference', 'world_section', 'writer_events',
))

TECHNICAL_ERRORS = frozenset((
    'preview', 'section', 'runtime_install',
    'access', 'alignment_schema', 'author_decision', 'author_source', 'book_integrity',
    'book_ownership', 'book_state', 'capability', 'chapter', 'chapter_limit', 'chapter_order',
    'chapter_target', 'checks', 'claim', 'completion', 'contract', 'coverage', 'creation',
    'criterion', 'delivery', 'editorial_protocol', 'edits', 'envelope_identity', 'envelope_input',
    'envelope_task', 'execution_claim', 'exists', 'feedback', 'file', 'findings', 'first_read',
    'first_read_frozen', 'format', 'gold', 'history_integrity', 'host_command', 'host_loop',
    'host_timeout', 'host_transport', 'input_version', 'intake', 'lease', 'length',
    'lexical_policy', 'lint', 'manifest', 'observation', 'observation_conflict', 'opening',
    'opening_back', 'opening_incomplete', 'opening_state', 'opening_system', 'opening_version',
    'outline_policy', 'output', 'pause', 'paused', 'payoffs', 'pilot_version', 'plan_guard',
    'plan_preconditions', 'project', 'project_isolation', 'prose_integrity', 'recall', 'record',
    'remedy_exhausted', 'repair_budget', 'replan', 'replay_conflict', 'result', 'resume',
    'review', 'revision', 'revision_bounds', 'revision_carry', 'revision_impact',
    'revision_proposal', 'revision_scope', 'revision_target', 'schema', 'severity', 'source',
    'stage', 'stage_brief', 'stage_template', 'stale_case', 'stdin_encoding', 'stdin_json',
    'target', 'task', 'task_integrity', 'transaction', 'understanding_source', 'verdict',
    'volume', 'watch', 'worker_io', 'world_view', 'writing_mode',
))

CONTENT_ERRORS = CONTENT_ERRORS | frozenset(('no_progress', 'timeline', 'continuity_evidence',
                                               'continuity_observation', 'continuity_report'))
TECHNICAL_ERRORS = TECHNICAL_ERRORS | frozenset(('assurance_policy', 'continuity_request',
    'continuity_phase', 'continuity_resolution', 'continuity_version', 'continuity_source', 'continuity_coverage'))

RECOVERY_ROUTES = {
    'continuity_pending': ('await_existing_review', '保留原候选，完成正在进行的独立阅读或作者裁决；不重新派读换稿。'),
    'continuity_settlement': ('settle_reviewed_candidate', '把原候选的准确回执交还原Worker提交，先结算返修再写新稿。'),
    'engine_changed': ('pin_engine', '用pin-engine --ref准确提交 --output独立目录固定冻结构建；或沿作者升级授权用recover-engine对准确task/input_hash重新冻结。禁止还原开发目录或复用旧input_hash。'),
    'engine_recovery': ('inspect_engine_recovery', '核对status的当前任务、构建及原执行者，恢复只作用于准确待办，不重置创作额度。'),
    'governance_integrity': ('inspect_integrity', '核对治理事件与检查点，保留异常现场；不清预算或覆盖检查点继续。'),
    'host_authority': ('connect_trusted_host', '接入受控宿主证明；本地CLI不能自行生成可信作者授权或独立模型身份。'),
    'host_actor': ('restore_host_channel', '把调用交还已登记的实际上下文；不要改会话字符串冒充其他角色。'),
    'authorization_replay': ('request_current_authorization', '重新核对准确对象与真实人类回复，不能重放旧授权。'),
    'continuity_stale': ('resync_review', '核对当前候选与核验请求；旧报告不能覆盖新候选。'),
    'continuity_identity': ('restore_observer', '核对独立读者的实际宿主上下文和核验凭据；主控和执笔者不能代审。'),
    'controller_lease': ('renew_controller', '主控核对 owner；有效租约由原主控 renew，已失效则沿原授权 run 重新认领，再恢复 Worker。'),
    'stale_task': ('resync_task', '主控核对 status 与当前任务；不修改旧任务身份重投稿件。'),
    'writing_batch': ('resync_task', '主控核对当前组和原执行者；保留已提交章节，不把旧回调转成下一任务。'),
    'worker_busy': ('wait_for_worker', '主控先核对原 Worker 是否仍在运行；不抢占有效租约。'),
    'source_integrity': ('inspect_integrity', '主控保留现场并检查冻结来源；不重写数据库或放宽验收。'),
    'state_integrity': ('inspect_integrity', '主控保留现场并检查历史重放；不重写数据库或放宽验收。'),
    'projection': ('inspect_integrity', '主控保留现场并核对投影来源；不直接保存投影。'),
    'chain': ('inspect_integrity', '主控保留现场并核对事件链；不修改历史回执。'),
}


def execution_recovery(code, failures=0):
    escalated = code in CONTROLLER_ERRORS or failures >= policy_default('technical_retries')
    return {'actor': 'controller' if escalated else 'worker',
            'action': RECOVERY_ROUTES.get(code, ('prepare_worker', ''))[0] if escalated else 'correct_from_template',
            'retry_allowed': not escalated,
            'failures': failures, 'limit': policy_default('technical_retries')}


class Error(Exception):
    def __init__(self, code, message, details=None):
        super().__init__(message)
        self.code, self.message = code, message
        self.details = dict(details or {})
        recovery = execution_recovery(code)
        self.details.setdefault('recovery', recovery)
        if code in CONTROLLER_ERRORS:
            action_desc = ('由主控 prepare-worker 绑定 NOVEL_TASK_ID/NOVEL_SESSION 并注入凭据。' if recovery['action'] == 'prepare_worker'
                           else '主控按 recovery.action 恢复对应能力，不靠重置计数跳过原因。')
            self.details['recover'] = (RECOVERY_ROUTES.get(code, ('', ''))[1] +
                                       '保留任务与已填稿件，将 task_id、真实会话和错误码交回主控；' +
                                       action_desc +
                                       'Worker 不执行 claim/advance/run。')
        else:
            self.details.setdefault('recover', '按当前任务模板修正后重提；不要改库或替换任务身份。')

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
    style_report: Optional[Dict[str, Any]] = None
    findings: Optional[list] = None
