"""Authoritative names of the task stages the engine may dispatch."""
from __future__ import annotations

from .contracts import require

# Every stage a task can be frozen under. A stage missing here is not dispatched;
# briefs and deliverable templates refuse it instead of degrading to an empty shape.
STAGES = frozenset({
    'alignment_plan', 'alignment_review', 'book_plan', 'chapter_review', 'contract_review',
    'design_review', 'opening_contract', 'opening_options', 'outline_review', 'plan',
    'profiles', 'redesign', 'repair', 'revision_review', 'scope_review', 'scope_synthesis',
    'volume_outline', 'volume_plan', 'world_model', 'world_review', 'write',
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
REVIEW_BLOCKS = ('verdict', 'checks_version', 'checks', 'findings', 'obligations')
DESIGN_BLOCKS = ('intent', 'ending_conditions', 'nodes')
BLOCKS = {
    'opening_options': ('gate', 'options'),
    'chapter_review': ('facts', 'reader'),
    'contract_review': REVIEW_BLOCKS,
    'design_review': REVIEW_BLOCKS,
    'outline_review': REVIEW_BLOCKS,
    'alignment_review': REVIEW_BLOCKS,
    'world_review': REVIEW_BLOCKS,
    'scope_review': REVIEW_BLOCKS + ('coverage',),
    'scope_synthesis': REVIEW_BLOCKS + ('coverage',),
    'revision_review': ('reader',),
    'write': ('title', 'prose', 'summary', 'self_check'),
    'repair': ('title', 'prose', 'summary', 'self_check'),
    'redesign': ('title', 'prose', 'summary', 'self_check'),
    'profiles': ('profiles',),
    'alignment_plan': ('reason', 'plan', 'designs'),
    'plan': ('plans',),
    'book_plan': DESIGN_BLOCKS,
}
# Blocks added only when the dispatch's payload asks for them; nothing else may appear.
CONDITIONAL_BLOCKS = {
    'chapter_review': ('understanding', 'alignment'),
    'revision_review': ('understanding',),
    'scope_review': ('understanding', 'handoff', 'closure', 'remedy_review'),
    'scope_synthesis': ('understanding', 'handoff', 'closure', 'remedy_review'),
    'book_plan': ('threads',),
}
# Shapes assembled from dynamic declarations (world sections, contract fields, outline policy):
# they are checked by the modules that own those tables, not by block equality here.
DYNAMIC_BLOCKS = ('world_model', 'opening_contract', 'volume_outline', 'volume_plan')
