"""Declared shape of the frozen task material shared by compiler and delivery.

Two envelopes exist and both are contracts between independent components: the
frozen input a worker reads (``input.json``) and the dispatch envelope the caller
renders (``task.json``). Neither may grow a field silently, so each is validated
at the moment it is produced.
"""
from __future__ import annotations

from .contracts import require

# Fields the freeze compiler always produces. The brief is optional.
WORK_FIELDS = ('schema', 'stage', 'chapter', 'scope', 'first', 'last', 'payload', 'branch',
               'revision', 'records', 'required', 'narrative_tracking',
               'capabilities', 'policy')
WORK_OPTIONAL = ('brief', 'build')
# `payload` is the one work field whose contents a stage decides on, so its keys are declared as
# well. Without this, "an undeclared field is rejected" held for the envelope but not for the
# container everything else travels in: the compiler wrote keys the consumers (briefs, result
# templates, workflow, editorial) read blind, and a rename would have failed at dispatch time.
WORK_PAYLOAD_FIELDS = (
    'gate', 'round', 'creative_lens',                          # one opening gate's board
    'also',                                                    # combined world + contract dispatch
    'mode', 'repair',                                          # redesign / bounded outline repair
    'understanding', 'editorial',                               # capability flags the brief reads
    'volume_ids',                                               # which volumes a volume_outline batch answers
    'volume', 'from_chapter', 'drift', 'reason',                # chapter_outline batch and its re-plan input
    'allow_retained_suffix',                                    # partial replan, validated with retained rows
    'anchor',                                                   # design-ahead chain vs the live state
    'structure_blueprint',                                      # the author's chosen structural blueprint (volume design)
    'volume_rejections',                                        # the author's reasoned refusals a re-run must answer
    'volume_outline', 'chapter_outline',                        # the volume row / the chapter row handed to a writer
    'design_drift',                                             # drift rows a re-plan must absorb
    # The promise ledger and the style specification normally travel as the `hooks` / `style`
    # records, declared where they are assembled (context.STAGE_MATERIAL). They are registered here
    # too so a dispatch that forwards either block inline — a re-plan naming the hooks to absorb, a
    # template that needs the effective window — is a declared shape instead of a rejected field.
    'hooks', 'style',
    'worker_batch',                                            # bounded same-worker prose continuation
)

# Fields the local delivery adapter renders for one dispatch. Guides are attached
# per stage, so a stage without reference documents legitimately omits them.
TASK_FIELDS = ('schema', 'task_id', 'input_hash', 'stage', 'chapter', 'scope', 'delivery_phase',
               'task_path', 'result_path', 'project_path', 'host_log_path',
               'process', 'requires_new_worker', 'review_session', 'version', 'claim', 'baseline',
               'commands', 'stages', 'note', 'redispatch_count', 'material_bytes', 'identity_path')
# A dispatch carries the formal material; the locked first-read form is gone with the review
# stages, so the envelope has one shape instead of two.
TASK_OPTIONAL = ('brief', 'guides', 'input_path', 'template_path',
                 'records', 'required', 'brief_path', 'dispatch_path', 'stale_result_session',
                 'catalog_path', 'worker_batch', 'execution')

# Dispatch identity (`identity.json` in the work directory): the task's own copy of who it is,
# written so a worker and the controller can cross-check the dispatched identity without guessing.
# It grants nothing: reading prose still requires the host-injected NOVEL_TASK_ID/NOVEL_SESSION.
IDENTITY_FIELDS = ('schema', 'task_id', 'input_hash', 'stage', 'stages', 'chapter', 'scope',
                   'delivery_phase', 'requires_new_worker', 'review_session', 'project_path',
                   'task_path', 'entry', 'version', 'worker_env', 'task_line', 'note')


def _validate(value, fields, optional, code, label):
    require(isinstance(value, dict), code, label + '必须是对象。')
    unknown = sorted(set(value) - set(fields) - set(optional))
    require(not unknown, code, label + '出现未声明字段，需先登记再使用。',
            {'unknown_fields': unknown})
    missing = sorted(set(fields) - set(value))
    require(not missing, code, label + '缺少必需字段。', {'missing_fields': missing})
    return value


def validate_work(value):
    """The frozen input a task is dispatched with."""
    _validate(value, WORK_FIELDS, WORK_OPTIONAL, 'envelope_input', '冻结输入')
    payload = value['payload']
    require(isinstance(payload, dict), 'envelope_input', '冻结输入的 payload 必须是对象。')
    unknown = sorted(set(payload) - set(WORK_PAYLOAD_FIELDS))
    require(not unknown, 'envelope_input', '冻结输入的 payload 出现未声明字段，需先登记再使用。',
            {'unknown_fields': unknown})
    return value


def validate_task(value):
    """The envelope the caller hands to a worker process."""
    return _validate(value, TASK_FIELDS, TASK_OPTIONAL, 'envelope_task', '派工信封')


def validate_identity(value):
    """The dispatch's own identity copy, written beside the task it belongs to."""
    return _validate(value, IDENTITY_FIELDS, (), 'envelope_identity', '派工身份')
