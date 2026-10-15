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
