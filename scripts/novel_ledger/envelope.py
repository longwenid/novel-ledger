"""Declared shape of the frozen task material shared by compiler and delivery.

Two envelopes exist and both are contracts between independent components: the
frozen input a worker reads (``input.json``) and the dispatch envelope the caller
renders (``task.json``). Neither may grow a field silently, so each is validated
at the moment it is produced.
"""
from __future__ import annotations

from .contracts import require

# Fields the freeze compiler always produces. A worker's access token, sealed
# first-read material and the dispatch brief are added by other owners, so they
# are declared optional rather than required.
WORK_FIELDS = ('schema', 'stage', 'chapter', 'scope', 'first', 'last', 'payload', 'branch',
               'revision', 'records', 'required', 'checks_version', 'narrative_tracking',
               'capabilities', 'policy', 'prose', 'blind', 'obligations')
WORK_OPTIONAL = ('brief', 'first_read', 'first_read_hash')

# Fields the local delivery adapter renders for one dispatch. Guides are attached
# per stage, so a stage without reference documents legitimately omits them.
TASK_FIELDS = ('schema', 'task_id', 'input_hash', 'stage', 'chapter', 'scope', 'delivery_phase',
               'prose_files', 'task_path', 'result_path', 'project_path', 'host_log_path',
               'process', 'requires_new_worker', 'review_session', 'version', 'claim', 'baseline',
               'commands', 'stages', 'note', 'redispatch_count', 'material_bytes')
# A locked dispatch hides the formal material: it carries the first-read brief and
# path instead, and only an unlocked dispatch adds the input/template/records set.
TASK_OPTIONAL = ('brief', 'first_read_path', 'guides', 'input_path', 'template_path',
                 'records', 'required')


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
    return _validate(value, WORK_FIELDS, WORK_OPTIONAL, 'envelope_input', '冻结输入')


def validate_task(value):
    """The envelope the caller hands to a worker process."""
    return _validate(value, TASK_FIELDS, TASK_OPTIONAL, 'envelope_task', '派工信封')
