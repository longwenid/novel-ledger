"""Authoritative names of the task stages the engine may dispatch."""
from __future__ import annotations

from .contracts import require

# Every stage a task can be frozen under. A stage missing here is not dispatched;
# briefs and deliverable templates refuse it instead of degrading to an empty shape.
#
# The five-step pipeline: thirteen opening gates decide, one dispatch writes the world and
# the contract, one writes each volume's outline at the contract length, one writes a volume's chapter
# outlines (resource/place/knowledge/plot deltas), and each chapter is drafted against its own
# outline with the engine reconciling the writer's self-comparison. There is no reviewer stage:
# the checks that used to be a second agent's receipt are now mechanical (drift.reconcile), so
# the count of dispatches before the first word is a constant instead of a function of reviews.
STAGES = frozenset({
    'chapter_outline', 'opening_contract', 'opening_options', 'redesign', 'repair',
    'volume_outline', 'world_model', 'write',
})
# Draft marker recorded when the repair budget is spent; never dispatched as a task.
DRAFT_EXHAUSTED = 'exhausted'


def require_stage(name):
    """Reject an unregistered stage instead of rendering an empty brief or template."""
    require(isinstance(name, str) and name in STAGES, 'stage', '未知或未登记的任务阶段。',
            {'stage': name if isinstance(name, str) else type(name).__name__,
             'known': sorted(STAGES)})
    return name


def require_rule(name, rule):
    require(rule is not None, 'stage_brief', '阶段已登记但缺少简报规则，属引擎缺陷。',
            {'stage': name, 'known': sorted(STAGES)})
    return rule


# Top-level delivery blocks a blank result must carry. Declared here so a template cannot
# silently change shape: a repair dispatch once handed out a world skeleton with no contract
# block, and the missing block then had nowhere official to live. A new stage must either
# declare its blocks or be listed as dynamic, or the guard test fails.
#
# `drift_check` is the fifth step made structural: the writer compares its own prose against the
# chapter outline item by item, and the engine reconciles that comparison against the projected
# state. It replaces the reviewer's receipt, so the write shape carries it at the top level.
DRIFT_BLOCKS = ('drift_check',)
BLOCKS = {
    'opening_options': ('gate', 'options'),
    'write': ('title', 'prose', 'summary') + DRIFT_BLOCKS + ('self_check',),
    'repair': ('title', 'prose', 'summary') + DRIFT_BLOCKS + ('self_check',),
    'redesign': ('title', 'prose', 'summary') + DRIFT_BLOCKS + ('self_check',),
    'volume_outline': ('volumes',),
    'chapter_outline': ('volume', 'chapters'),
}
# Blocks added only when the dispatch's payload asks for them; nothing else may appear.
CONDITIONAL_BLOCKS = {
    'world_model': ('contract',),
    # The smallest tiers answer a volume and its chapter outlines in one cold session: the chapter
    # half is a few hundred characters of deltas for volumes the same receipt just designed, and
    # splitting it buys latency rather than review (there is no review to split it from).
    'volume_outline': ('chapters',),
}
# Shapes assembled from dynamic declarations (world sections, contract fields, outline policy):
# they are checked by the modules that own those tables, not by block equality here.
DYNAMIC_BLOCKS = ('world_model', 'opening_contract')
