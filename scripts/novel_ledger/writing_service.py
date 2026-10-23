"""Bounded same-worker writing over immutable, individually submitted chapter tasks.

The controller starts a group. Its worker can only request the next prose task in that frozen
range; author decisions, planning, revisions and new groups remain controller operations.
Every method that mutates state runs inside the caller's repository transaction.
"""
from __future__ import annotations

from .contracts import CONTINUOUS_WRITING_CAPABILITY, Job, digest, policy_default, require
from .ports import Repository, TaskCompiler
from . import editorial, planning, store_keys, workflow

PROSE_STAGES = ('write', 'repair', 'redesign')


class WritingService:
    def __init__(self, repo: Repository, compile_task: TaskCompiler, clock, new_id):
        self.repo, self.compile_task, self.clock, self.new_id = repo, compile_task, clock, new_id

    def active(self):
        group = self.repo.get(store_keys.WRITING_BATCH)
        return group if group and group.get('active') else None

    def close(self, reason):
        group = self.active()
        if group:
            group.update(active=False, stop_reason=reason)
            self.repo.put(store_keys.WRITING_BATCH, group)

    def describe(self):
        group = self.repo.get(store_keys.WRITING_BATCH)
        return ({key: group.get(key) for key in ('id', 'first', 'last', 'task_id', 'session', 'active', 'stop_reason')}
                if group else None)

    def task_status(self, task):
        descriptor = task['input'].get('payload', {}).get('worker_batch')
        if not descriptor:
            return {}
        group = self.active()
        matches = bool(group and group['id'] == descriptor['id'])
        return {'batch_active': matches, 'batch_task': group['task_id'] if matches else None}

    def scope(self, task, session):
        descriptor = task['input'].get('payload', {}).get('worker_batch')
        if not descriptor:
            return task['id']
        group = self.active()
        require(group and group['id'] == descriptor['id'] and group['task_id'] == task['id']
                and group['branch'] == task['input']['branch'] and group['revision'] == task['input']['revision'],
                'writing_batch', '连写任务已结束或不属于当前组。')
        require(group.get('session') in (None, session), 'session_reuse', '本组只能由已绑定的同一 Worker 执行。')
        return group['id']

    def bind(self, task, session, seconds=None):
        scope = self.scope(task, session)
        if scope != task['id']:
            require(self._unchanged(self.repo.load(), self.active()), 'writing_batch',
                    '本组冻结的章纲、约定或执行范围已改变，禁止认领和提交。')
        self.repo.bind_session(session, scope)
        if scope != task['id']:
            group = self.active()
            group['session'] = session
            if seconds is not None:
                group['lease_seconds'] = seconds
            self.repo.put(store_keys.WRITING_BATCH, group)

    def _unchanged(self, book, group):
        return (book.get('writing_mode') == 'fast' and book['status'] == 'running'
                and not book.get('revision_run') and not book.get('revision_directive')
                and book['branch'] == group['branch'] and book['revision'] == group['revision']
                and digest(book['contract']) == group['contract_hash'] and book['target'] >= group['last']
                and all(digest(book['plans'].get(str(n))) == value for n, value in group['plans'].items()))

    def _within(self, book, group, choice):
        return (self._unchanged(book, group) and isinstance(choice, Job) and choice.stage in PROSE_STAGES
                and group['first'] <= choice.chapter <= group['last'])

    def dispatch(self, book, choice, owner=None, group=None):
        if group is None and book.get('writing_mode') == 'fast' and choice.stage in PROSE_STAGES \
                and choice.chapter > 1 and book.get('pilot') and not book.get('revision_run'):
            run = self.repo.get(store_keys.CONTROLLER)
            require(run and run['owner'] == owner and run['until'] > self.clock(),
                    'controller_lease', '快速连写须由有效主控派工，先沿原授权 run 认领。')
            volume = planning.volume_for(editorial.effective_contract(book), choice.chapter)
            last = min(choice.chapter + policy_default('fast_batch_chapters') - 1, volume['end'], book['target'])
            # A group never invents or modifies a missing future outline.
            while last > choice.chapter and any(str(n) not in book['plans'] for n in range(choice.chapter, last + 1)):
                last -= 1
            group = {'id': self.new_id(), 'first': choice.chapter, 'last': last, 'owner': owner,
                     'branch': book['branch'], 'revision': book['revision'], 'contract_hash': digest(book['contract']),
                     'plans': {str(n): digest(book['plans'][str(n)]) for n in range(choice.chapter, last + 1)},
                     'active': True, 'session': None, 'read_hashes': {}, 'previous_task': None}
        if group:
            descriptor = {key: group[key] for key in ('id', 'first', 'last')}
            choice = Job(choice.stage, choice.chapter, choice.scope, choice.first, choice.last,
                         {**(choice.payload or {}), 'worker_batch': descriptor})
        work = self.compile_task(book, choice)
        if group:
            work['capabilities']['continuous_writing'] = CONTINUOUS_WRITING_CAPABILITY
        task = self.repo.add_task(work)
        if group:
            group['previous_task'], group['task_id'] = group.get('task_id'), task['id']
            self.repo.put(store_keys.WRITING_BATCH, group)
        self.repo.record('dispatch', {'task': task['id'], 'stage': choice.stage})
        return task

    def after_submit(self, book, task):
        if not task['input'].get('payload', {}).get('worker_batch'):
            return 'finished'
        group = self.active()
        if group and group['task_id'] == task['id'] and group['revision'] == task['input']['revision'] \
                and book['revision'] == group['revision'] + 1:
            # The one expected transition is this task's submission. Other version changes do not
            # inherit the continuation capability.
            group['revision'] = book['revision']
            self.repo.put(store_keys.WRITING_BATCH, group)
        if not group or not self._unchanged(book, group):
            self.close('项目暂停或创作依据改变。')
            return 'finished'
        choice = workflow.choose(book, self.repo.headers(book['branch']))
        if not self._within(book, group, choice):
            self.close('本组完成或到达规划、作者及授权边界。')
            return 'finished'
        return 'continue'

    def continue_task(self, book, task_id, session, claim=None):
        prior = self.repo.task(task_id)
        descriptor = prior['input'].get('payload', {}).get('worker_batch')
        require(descriptor and prior['status'] == 'done' and prior['result'].get('session') == session,
                'writing_batch', '只能从本 Worker 已提交的连写任务接续。')
        require(self.repo.session_task(session) == descriptor['id'], 'session_reuse', '会话不属于本连写组。')
        lease = self.repo.get(store_keys.claim(task_id))
        require(not lease or lease['session'] == session and lease['token'] == claim,
                'worker_lease', '接续凭据不属于上一任务。')
        group = self.active()
        if not group or group['id'] != descriptor['id']:
            return None, None
        require(group['session'] == session, 'session_reuse', '连写组执行者不匹配。')
        run = self.repo.get(store_keys.CONTROLLER)
        require(run and run['owner'] == group['owner'] and run['until'] > self.clock(),
                'controller_lease', '主控租约失效，保留连写进度并交主控恢复。')
        require(self._unchanged(book, group), 'writing_batch', '连写范围或创作依据已改变，交主控重新派工。')
        pending = self.repo.pending()
        if pending:
            require(group['previous_task'] == task_id and group['task_id'] == pending['id'],
                    'writing_batch', '该接续回调已过期，不能跳过当前任务。')
            return pending, self.repo.get(store_keys.claim(pending['id']))
        require(group['task_id'] == task_id and book.get('last_task') == task_id,
                'writing_batch', '只能接续本组最新提交，不能从旧任务分叉。')
        choice = workflow.choose(book, self.repo.headers(book['branch']))
        if not self._within(book, group, choice):
            self.close('已到连写范围边界。')
            return None, None
        task = self.dispatch(book, choice, group=group)
        lease = {'session': session, 'token': self.new_id(),
                 'execution_id': (lease.get('execution_id') if lease else None) or self.new_id(),
                 'provenance': (lease.get('provenance') if lease else None),
                 'until': self.clock() + group.get('lease_seconds', 300)}
        self.repo.put(store_keys.claim(task['id']), lease)
        return task, lease

    def already_read(self, task):
        group = self.active()
        descriptor = task['input'].get('payload', {}).get('worker_batch')
        if not group or not group.get('session') or not descriptor or group['id'] != descriptor['id']:
            return []
        return [name for name in task['input']['required']
                if group['read_hashes'].get(name) == task['input']['records'][name]]

    def record_read(self, task, names):
        group = self.active()
        if not group or not group.get('session') or group['task_id'] != task['id']:
            return
        group['read_hashes'].update({name: task['input']['records'][name] for name in names
                                     if name in task['input']['records']})
        self.repo.put(store_keys.WRITING_BATCH, group)
