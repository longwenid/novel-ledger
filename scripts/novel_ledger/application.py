"""Application use cases over explicit persistence, compilation and delivery ports."""
from __future__ import annotations

import copy
from .contracts import (CONTENT_ERRORS, SINGLE_DELIVERY_STAGES, policy_default, CONTROLLER_STAGES, POLICY_FIELDS, RESULT, SCALE_TIERS, VERSION, Error, EXECUTION, Job,
                        blueprint_valid, execution_recovery, resolve_blueprint,
                        digest, dump, require, text)
from . import book_state, creation, facts, planning, workflow, craft, editorial, store_keys, lint
from .ports import Presentation, Repository, TaskCompiler
from .revision_service import RevisionService
from .opening_service import OpeningService
from .contract_activation import ContractActivation
from .verification import VerificationService
from .writing_service import WritingService
from .governance import Governance
from .continuity_service import ContinuityService
from .execution import controller_handoff, presence, review_handoff, submission_handoff

# An amendment preview is a JSON-encoded value, not prose: if it is cut, it says so, because a
# silently truncated preview reads as a valid value and would let a reviewer (or a script) compare
# against something the author never wrote.
AMENDMENT_PREVIEW_LIMIT = 4000


def _amendment_side(value, limit=AMENDMENT_PREVIEW_LIMIT):
    rendered = dump(value)
    return rendered if len(rendered) <= limit else rendered[:limit] + '…truncated'


class Application:
    def __init__(self, repo: Repository, *, compile_task: TaskCompiler, presentation: Presentation, clock, new_id,
                 authority=None, build_info=None):
        self.repo = repo
        self.compile_task = compile_task
        self.presentation = presentation
        self.clock = clock
        self.new_id = new_id
        self._revisions = RevisionService(repo, cancel_pending=self._cancel_pending)
        self._contracts = ContractActivation(repo)
        self._opening = OpeningService(repo, cancel_pending=self._cancel_pending)
        self._verification = VerificationService(repo)
        self._writing = WritingService(repo, compile_task, clock, new_id)
        self.build_info = build_info
        self._governance = Governance(repo, authority, new_id)
        self._continuity = ContinuityService(repo, self._governance, new_id, self._check_build)

    def _load(self):
        book = self.repo.load()
        if book['status'] == 'completed':
            reference = book.get('completion_snapshot')
            snapshot = self._verification.snapshot(reference)
            book = copy.deepcopy(snapshot['book'])
            book['completion_snapshot'] = reference
        else:
            self._verification.head(book)
        self._governance.check(book)
        return book

    def _save(self, book):
        # Validate before the transaction can commit, not in a later status query.
        self._verification.head(book)
        self.repo.save(book)
        self._governance.seal(book)

    def configure_assurance(self, trust, continuity, source, owner=None):
        with self.repo.transaction():
            self.controller_guard(owner)
            book = self._load()
            require(self.repo.pending() is None, 'assurance_policy', '先保留并取消在途任务，再切换保障策略。')
            self._governance.configure(trust, continuity, source)
            self._governance.seal(book)
        return self._governance.describe()

    def task_list(self):
        """`status --tasks`: every dispatched task with its lifecycle state, read-only."""
        book = self._load()
        rows = self.repo.task_rows()
        counts = {}
        for row in rows:
            counts[row['status']] = counts.get(row['status'], 0) + 1
        return {'version': VERSION, 'book_status': book['status'], 'tasks': rows, 'counts': counts}

    def status(self):
        book = self._load()
        # A contradictory state is reported by the command that produced it, not discovered later.
        book_state.check_state(book)
        rows = self.repo.headers(book['branch'])
        official = self.repo.get(store_keys.OFFICIAL_BRANCH, 'main')
        formal = self.repo.headers(official)
        task = self.repo.pending()
        # A frozen task belongs to the revision it was built from. If the book moved on without
        # retiring it, the next worker would only discover that on its first read.
        require(task is None or task['input']['revision'] == book['revision'], 'book_state',
                '在途任务冻结自另一个项目版本：先作废再派工。',
                {'task_revision': None if task is None else task['input']['revision'],
                 'book_revision': book['revision']})
        sealed = False
        revision = book['revision_run']
        return {'version': VERSION, 'assurance': self._governance.describe(),
                'status': book['status'], 'branch': book['branch'], 'formal_branch': official,
                'accepted_chapters': rows[-1]['n'] if rows else 0, 'formal_chapters': formal[-1]['n'] if formal else 0,
                'candidate_chapter': book['draft']['chapter'] if book['draft'] else None,
                'target': book['target'], 'written_han': book['written_han'], 'finish': book['finish'],
                'writing_mode': book.get('writing_mode', 'standard'), 'worker_batch': self._writing.describe(),
                'writing_batch_chapters': book.get('writing_batch_chapters') or policy_default('fast_batch_chapters'),
                # The confirmation gate's own state: which round the staged design is on, how many
                # reasoned refusals fed it, and — when a design is staged — the exact hash the
                # author's confirmation must bind to.
                'volume_gate': {'round': (book.get('volume_gate') or {}).get('round', 0),
                                'rejections': len((book.get('volume_gate') or {}).get('rejections') or []),
                                'confirmed': sorted((book.get('volume_gate') or {}).get('confirmed') or {}),
                                'pending': book.get('pending_design') is not None,
                                'pending_volumes': list((book.get('pending_design') or {}).get('volume_ids') or []),
                                'pending_hash': (book.get('pending_design') or {}).get('volumes_hash')},
                'structure_blueprint': (book.get('structure_blueprint') or {}).get('name'),
                'design_blueprint': (book.get('design_blueprint') or {}).get('name'),
                'pending_task': task['id'] if task else None, 'stage': task['input']['stage'] if task else None,
                'worker_presence': self.worker_presence(task['id']) if task else None,
                'engine': {'current': self.build_info, 'frozen': task['input'].get('build') if task else None,
                           'matches': not task or not task['input'].get('build') or task['input']['build'] == self.build_info},
                'execution_failure': self.repo.get(store_keys.technical_failure(task['id'])) if task else None,
                'pause_reason': None if sealed else book.get('pause_reason'),
                'author_decision': None if sealed else copy.deepcopy(book.get('author_block')),
                # What the author accepted while a review still asked for changes, so a project never
                # looks clean just because someone chose to go on.
                'accepted_findings': [{'stage': row['stage'], 'scope': row.get('scope'),
                                       'count': len(row.get('findings') or [])}
                                      for row in book.get('accepted_findings') or []],
                'workbench': {'enabled': 'understanding' in book},
                'opening': {'phase': book['creation']['phase'], 'selected_gates': len(book['creation']['selections']),
                            'total_gates': len(creation.gates(book['creation'])),
                            'gate': creation.current(book['creation'])['id'] if book['creation']['phase'] == 'choosing' else None}
                           if book.get('creation') else None,
                'revision_run': ({'parent': revision['parent'], 'first': revision['first'], 'last': revision['last'],
                                  'expansion': (revision.get('impact') or {}).get('expansion')})
                                 if revision else None,
                'revision_proposal': self._revision_summary(book)}

    def _revision_summary(self, book):
        plan = book.get('revision_directive') or {}
        if not plan.get('blocked'):
            return None
        actions = plan['impact']['chapter_actions']
        return {'plan_hash': plan['plan_hash'], 'first': plan['first'], 'requested_through': plan['through'],
                'required_through': plan['impact']['last'], 'reason': plan['reason'],
                'violations': plan['violations'], 'policy': plan['policy'],
                'action_counts': {name: sum(a['action'] == name for a in actions) for name in ('keep', 'local', 'rewrite')},
                'plan_path': self.presentation.revision_path(plan['plan_hash'])}

    def diagnose(self):
        """Read operational metadata without re-dispatching or trusting a damaged projection.

        This is a handoff snapshot, not an integrity audit or a replacement for advance.
        In particular, do not load prose, render task artifacts, or renew any lease here.
        """
        state = self.repo.load_part('execution')
        task = self.repo.pending()
        batch = self._writing.describe()
        task_origin = 'pending' if task else None
        if task is None and batch and batch['active'] and batch.get('task_id'):
            task = self.repo.task(batch['task_id'])
            task_origin = 'active_batch'
        run = self.repo.get(store_keys.CONTROLLER) or {}
        moment = self.clock()
        work = task['input'] if task else {}
        frozen = work.get('build')
        matches = not frozen or not self.build_info or frozen == self.build_info
        lease = self.repo.get(store_keys.claim(task['id'])) if task else None
        failure = self.repo.get(store_keys.technical_failure(task['id'])) if task else None
        review = self._continuity.summary(task['id']) if task else None
        decision = state.get('author_block') or {}
        headers = self.repo.headers(state['branch'])
        controller = {'owner': run.get('owner'), 'lease_until': run.get('until'),
                      'lease_valid': bool(run and run['until'] > moment),
                      'remaining_seconds': max(0, run.get('until', moment) - moment)}
        recovery = execution_recovery('engine_changed') if not matches else (
            execution_recovery(failure['code'], failure['failures']) if failure else None)
        # Never treat an expired lease as proof that a model stopped, or a diagnostic
        # suggestion as authorization to reset a task or change the author's target.
        if state['status'] in ('paused', 'completed') or decision:
            next_action = 'handle_boundary'
        elif not matches:
            next_action = 'pin_engine'
        elif failure and failure.get('blocked'):
            next_action = 'resolve_execution_failure'
        elif review:
            next_action = review_handoff(task['id'], review)['action']
        elif lease:
            next_action = 'verify_existing_worker'
        else:
            next_action = 'advance'
        return {'schema': 'novel-ledger.diagnostics/1', 'as_of': moment,
                'validation': {'integrity_checked': False, 'dispatch_authorized': False},
                'project': {**{key: state.get(key) for key in
                              ('status', 'branch', 'revision', 'target', 'finish', 'writing_mode',
                               'run_authorized', 'last_task')},
                            'accepted_chapters': headers[-1]['n'] if headers else 0,
                            'author_decision_id': decision.get('id'),
                            'author_decision_pending': bool(decision)},
                'engine': {'current': self.build_info, 'frozen': frozen, 'matches': matches},
                'controller': controller,
                'task': ({'task_id': task['id'], 'input_hash': task['input_hash'],
                          'status': task['status'], 'origin': task_origin, **{key: work.get(key) for key in
                                                     ('stage', 'chapter', 'scope', 'first', 'last')}} if task else None),
                'worker': ({'session': (lease or {}).get('session'),
                            **self.worker_presence(task['id'])} if task else None),
                'worker_batch': batch,
                'continuity': ({key: review.get(key) for key in
                               ('request_id', 'task_id', 'candidate_hash', 'phase', 'observer')}
                               if review else None),
                'execution_failure': ({key: failure.get(key) for key in
                                       ('code', 'operation', 'failures', 'blocked')} if failure else None),
                'recovery': recovery, 'next_action': next_action}

    def task_status(self, task_id):
        task = self.repo.task(task_id)
        batch = self._writing.task_status(task)
        failure = self.repo.get(store_keys.technical_failure(batch.get('batch_task') or task_id)) or {}
        return {**{key: task[key] for key in ('id', 'status', 'reviewer')}, **batch,
                'worker_presence': self.worker_presence(batch.get('batch_task') or task_id),
                'continuity': self._continuity.summary(batch.get('batch_task') or task_id),
                'execution_blocked': bool(failure.get('blocked')),
                'recovery': execution_recovery(failure.get('code', ''), failure.get('failures', 0))}

    def worker_presence(self, task_id):
        lease = self.repo.get(store_keys.claim(task_id))
        delivered = self.repo.get(store_keys.execution_reads(lease['execution_id']), {}) if lease and lease.get('execution_id') else {}
        return presence(lease, delivered, self.clock())

    def host_check(self):
        return {'native_worker_creation': False, 'worker_creation': 'external_host_required',
                'identity_verification_available': self._governance.authority is not None,
                'assurance': self._governance.describe(),
                'supervision': 'watch', 'watch_creates_workers': False,
                'unattended_host_ready': None,
                'next_action': 'verify_real_worker_creation_in_host',
                'note': '先由实际宿主创建独立模型会话；session登记和租约不证明Worker已启动。'}

    def authorize_worker(self, task_id, session, claim=None):
        task = self.repo.task(task_id)
        self._live(task, verify=False)
        failure = self.repo.get(store_keys.technical_failure(task_id)) or {}
        require(not failure.get('blocked'), 'technical_blocked', '本任务技术错误已交回主控。')
        self._session(task, session, claim)
        self._worker_actor(task, session)

    def worker_ready(self, task_id, session, claim=None, terminal_replay=False):
        """Portable worker entry: identity and recovery state before any material I/O."""
        task = self.repo.task(task_id)
        self._worker_actor(task, session)
        if terminal_replay and task['status'] == 'done':
            saved = task['result']
            require(saved.get('session') == session and saved.get('execution_claim') == claim,
                    'worker_lease', '只有原提交身份与凭据可确认已完成回执。')
            return {'schema': EXECUTION, 'task_id': task_id, 'session': session, 'ready': True,
                    'terminal_replay': True}
        self._live(task, verify=False)
        failure = self.repo.get(store_keys.technical_failure(task_id)) or {}
        require(not failure.get('blocked'), 'technical_blocked', '本任务技术错误已交回主控。')
        lease = self.repo.get(store_keys.claim(task_id))
        require(lease is not None, 'worker_identity', '任务尚未由主控绑定真实 Worker。')
        self._session(task, session, claim)
        return {'schema': EXECUTION, 'task_id': task_id, 'session': session, 'ready': True}

    def prepare_worker(self, task_id, session, owner=None, seconds=None, reset_failures=False, fresh_context=False):
        """Controller binds the host-returned identity; no invented session or prose edits."""
        self.controller_guard(owner)
        task = self.repo.task(task_id)
        self._live(task)
        failure = self.repo.get(store_keys.technical_failure(task_id)) or {}
        require(not failure.get('blocked') or reset_failures, 'technical_blocked',
                '先修复交接原因，再由主控显式 --reset-failures 恢复技术执行。')
        lease = self.claim(task_id, session, seconds, fresh_context=fresh_context)
        if reset_failures:
            with self.repo.transaction():
                self.repo.put(store_keys.technical_failure(task_id), None)
                self.repo.record('worker_recovered', {'task': task_id, 'session': session})
        view = self.presentation.task(self.repo.task(task_id), compact=True, preserve_result=True)
        return {'schema': EXECUTION, 'ready': True, 'identity_registered': True,
                'worker_presence': self.worker_presence(task_id),
                'next_action': {'actor': 'host', 'action': 'start_or_handoff_real_worker'}, 'task': view,
                'worker_env': {'NOVEL_TASK_ID': task_id, 'NOVEL_SESSION': session,
                               'NOVEL_EXECUTION_CLAIM': lease['token'],
                               'NOVEL_TASK_PATH': view.get('task_path', ''),
                               'NOVEL_PROJECT': view.get('project_path', '')},
                'lease_until': lease['until'],
                'note': '仅交给该真实 Worker；凭据不写入任务文件。宿主仍负责模型上下文隔离。'}

    # Wrong-command errors are syntax mistakes, not technical failures: guessing an
    # unknown CLI verb or flag shouldn't burn the same budget as a real crash.
    SYNTAX_ERRORS = frozenset({'file', 'access', 'worker_boundary'})

    def worker_failure(self, task_id, session, operation, code):
        """Technical accounting is separate from story revisions and literary repair budgets."""
        with self.repo.transaction():
            task = self.repo.task(task_id)
            require(task['status'] == 'pending', 'stale_task', '已结束任务不记录执行重试。')
            old = self.repo.get(store_keys.technical_failure(task_id)) or {}
            if old.get('blocked'):
                return {**execution_recovery(old['code'], old['failures']), 'task_id': task_id}
            if code in CONTENT_ERRORS:
                return {'actor': 'worker', 'action': 'correct_content', 'retry_allowed': True,
                        'failures': old.get('failures', 0), 'limit': policy_default('technical_retries'),
                        'content_error': True}
            if code in self.SYNTAX_ERRORS:
                # Syntax mistakes don't consume the technical budget; the worker just
                # needs to read the task card's commands and retry with the right argv.
                return {'actor': 'worker', 'action': 'correct_syntax', 'retry_allowed': True,
                        'failures': old.get('failures', 0), 'limit': policy_default('technical_retries'),
                        'syntax_error': True, 'hint': '核对 task.json.commands 里的规范命令后重试。'}
            count = old.get('failures', 0) + 1
            recovery = execution_recovery(code, count)
            row = {'task': task_id, 'session': session, 'operation': operation,
                   'code': code, 'failures': count,
                   'blocked': old.get('blocked', False) or not recovery['retry_allowed']}
            self.repo.put(store_keys.technical_failure(task_id), row)
            self.repo.record('worker_failure', row)
            return {**recovery, 'task_id': task_id}

    def worker_heartbeat(self, task_id, session, claim):
        """Execution-channel activity, separate from read-only business previews.

        Only an authenticated, unexpired pending lease renews. Completed receipt
        confirmations do not create or extend a new execution.
        """
        with self.repo.transaction():
            task = self.repo.task(task_id)
            if task['status'] != 'pending':
                return False
            self._live(task, verify=False)
            self._worker_actor(task, session)
            self._session(task, session, claim)
            lease = self.repo.get(store_keys.claim(task_id))
            require(lease is not None, 'worker_identity', '续租必须来自已准备的执行通道。')
            lease['activity_at'] = self.clock()
            lease['until'] = self.clock() + lease.get('seconds', policy_default('worker_lease_seconds'))
            self.repo.put(store_keys.claim(task_id), lease)
        return True

    def worker_succeeded(self, task_id, operation=None):
        old = self.repo.get(store_keys.technical_failure(task_id))
        # A material read cannot repair a failed submit/file operation. Only the same
        # operation succeeding (or a terminal commit) establishes relevant progress.
        if old and not old.get('blocked') and (operation == old.get('operation') or
                                              self.repo.task(task_id)['status'] == 'done'):
            with self.repo.transaction():
                self.repo.put(store_keys.technical_failure(task_id), None)
                self.repo.record('worker_progress', {'task': task_id, 'operation': operation})

    def preview_feedback(self, task_id, findings, session, claim):
        """Execution telemetry for repeated content previews; never a literary allowance.

        The CLI host calls this after a business preview has rolled back. Pure API
        previews do not acquire writes merely to report an error or run diagnostics.
        """
        with self.repo.transaction():
            task = self.repo.task(task_id)
            self._live(task, verify=False)
            self._worker_actor(task, session)
            self._session(task, session, claim)
            key = store_keys.content_rounds(task_id)
            old = self.repo.get(key) or {}
            signature = digest(sorted(digest(item) for item in findings))
            rounds = (old.get('rounds', 0) + 1 if old.get('signature') == signature else 1) if findings else 0
            stalled = rounds >= policy_default('design_stall_rounds')
            self.repo.put(key, {'signature': signature, 'rounds': rounds, 'stalled': stalled})
            self.repo.record('content_preview', {'task': task_id, 'signature': signature, 'rounds': rounds})
        return {'content_rounds': rounds, 'stalled': stalled}

    def _cancel_pending(self, reason):
        self._writing.close(reason)
        ident = self.repo.cancel_pending(reason)
        if ident:
            self.repo.after_commit(lambda: self.presentation.retire(ident))
        return ident

    def controller_guard(self, owner=None):
        run = self.repo.get(store_keys.CONTROLLER)
        if run and run['until'] > self.clock():
            require(owner == run['owner'], 'controller_lease', '运行主控仍持有租约。',
                    {'recover': '使用当前主控 owner，或待租约到期后重新 run 认领。'})

    def content_guard(self):
        """v2 has no blind first read: every dispatch reads the material it needs immediately."""
        return None

    def _live(self, task, verify=True):
        # Frozen source reads remain available for diagnosis even when the live
        # projection is damaged. No new task or submission can use that damage.
        book = self._load() if verify else self.repo.load()
        self._check_build(task)
        require(task['status'] == 'pending' and task['input']['branch'] == book['branch']
                and task['input']['revision'] == book['revision'], 'stale_task', '任务已失效，恢复当前任务；不可改身份重投旧结果。')
        return book

    def _check_build(self, task):
        frozen = task['input'].get('build')
        require(not frozen or not self.build_info or frozen == self.build_info, 'engine_changed',
                '当前引擎或执行规则已不同于冻结任务；保留候选，由主控明确切换版本后重新冻结任务。',
                {'task_id': task['id'], 'input_hash': task['input_hash'], 'frozen_build': frozen,
                 'current_build': self.build_info, 'recovery_commands': ['pin-engine', 'recover-engine'],
                 'boundary': '不还原开发目录；固定准确发布副本，或经作者升级授权对这一任务重新冻结。'})

    def _worker_actor(self, task, session):
        self._governance.actor(session)
        if self._governance.policy()['trust'] == 'required':
            lease = self.repo.get(store_keys.claim(task['id'])) or {}
            require(lease.get('session') == session and (lease.get('provenance') or {}).get('verified') is True,
                    'host_actor', '受控写作通道必须先登记经宿主证明的独立Worker，不能绕过prepare直接提交。')

    def _session(self, task, session, claim=None, check_lease=True):
        require(text(session), 'session', '须提供真实宿主会话身份 session。')
        require(claim is None or isinstance(claim, str), 'execution_claim',
                'execution_claim 须为 claim 命令返回的 token 裸字符串，不能是对象。',
                {'expect': '回执顶层 "execution_claim": "<token>"；token 来自 claim --task <ID> --session <会话> 的返回。'})
        owner = self.repo.session_task(session)
        scope = self._writing.scope(task, session)
        require(owner is None or owner == scope, 'session_reuse', '新任务须由新 Worker 执行；仅同一连写组允许复用。')
        lease = self.repo.get(store_keys.claim(task['id']))
        if lease and check_lease:
            require(lease['session'] == session and lease['token'] == claim and lease['until'] > self.clock(),
                    'worker_lease', 'Worker 租约或执行认领已过期。',
                    {'task_id': task['id'], 'lease_session': lease['session'], 'expired': lease['until'] <= self.clock()})

    def _sources(self, work):
        """Frozen recent chapters; workflow adds the composed current draft as its own evidence."""
        sources = {}
        record = (work.get('records') or {}).get('previous_chapters')
        if record:
            for row in self.repo.read_document(record):
                if 'prose' in row:
                    prose = row['prose']  # Existing frozen tasks use inline full chapters.
                else:
                    reference = work['records'].get(row.get('record'))
                    require(reference is not None and reference == row.get('prose_hash'),
                            'source_integrity', '前章正文索引与冻结来源不一致。')
                    prose = self.repo.read_document(reference)
                sources.setdefault(row['chapter'], prose)
        return sources

    def _priors(self, book, chapter):
        """The nearest committed chapters, for the mechanical prose checks at submit time."""
        rows = [row for row in self.repo.headers(book['branch']) if row['n'] != chapter]
        rows.sort(key=lambda row: abs(row['n'] - chapter))
        return [(row['n'], self.repo.read_document(row['prose'])) for row in rows[:lint.DUPLICATE_WINDOW]]

    def _world_refusal(self, task):
        """The world refusal staged on this task, exactly when this submission repairs one."""
        if task['input'].get('stage') != 'world_model':
            return None
        staged = self.repo.get(store_keys.world_rejection(task['id']))
        return staged if isinstance(staged, dict) and isinstance(staged.get('proposal'), dict) else None

    def _stage_world_refusal(self, task_id, candidate, error):
        """Keep the refused world candidate with its findings on the task it belongs to.

        The next `read` hands it back as the `previous_proposal` record, and the next submission
        is compared against it record by record: a repair may only change what the refusal named.
        """
        staged = {'proposal': copy.deepcopy(candidate),
                  'findings': workflow.rejection_findings(error),
                  'refusal': {'code': error.code, 'message': error.message},
                  'note': '上一版被拒候选与逐条问题。返修只改被点名处，其余记录与上一版逐字一致；'
                          '重新 read 本任务即可取回这份记录。'}
        with self.repo.transaction():
            self.repo.put(store_keys.world_rejection(task_id), staged)
            self.repo.record('world_refusal', {'task': task_id, 'code': error.code})
        return staged

    def _baseline(self, book, task=None):
        """A read-only projection of what stands right now, so a dispatcher never hand-summarizes
        the ledger: resource balances, open hooks, the clock, and the live candidate."""
        state = (self.repo.read_document(task['input']['records']['state']) if task else book['state'])
        return {'clock': state['clock'], 'resources': dict(sorted(state['resources'].items())),
                # The relation coordinates stand now, keyed `source>target:key` exactly the way the
                # chapter outlines and the reconciliation key them: a writer filing a relation
                # self-comparison reads the current word here instead of guessing a before-value.
                'relations': dict(sorted((state.get('relations') or {}).items())),
                'open_hooks': [{'id': ident, 'due': hook['due'], 'text': hook.get('text', '')}
                               for ident, hook in sorted(state['hooks'].items()) if hook['status'] == 'open'],
                'candidate': {'chapter': book['draft']['chapter'], 'stage': book['draft']['stage']} if book['draft'] else None}

    def _refresh_book(self, response):
        # A derived view cannot undo a committed receipt. Keep its failure separate
        # so the controller can retry html without resubmitting or rewriting prose.
        try:
            response['book_view'] = self.presentation.book()
        except (OSError, Error) as exc:
            response['book_view_error'] = str(exc)

    def advance(self, after=None, owner=None, compact=False, wait_pending=False):
        response = self._advance(after, owner, compact, wait_pending)
        self._refresh_book(response)
        return controller_handoff(response)

    def _advance(self, after=None, owner=None, compact=False, wait_pending=False):
        boundary = None
        refresh_world = False
        with self.repo.transaction():
            self.controller_guard(owner)
            book = self._load()
            if after:
                prior = self.repo.task(after)
                if prior['status'] == 'pending':
                    review = self._continuity.summary(after)
                    if review:
                        return review_handoff(after, review)
                    return {'action': 'wait_for_submit', 'task_id': after}
                if prior['status'] != 'done' or book.get('last_task') != after:
                    return {'action': 'resync', 'status': self.status()}
            task = self.repo.pending()
            if task:
                self._check_build(task)
                failure = self.repo.get(store_keys.technical_failure(task['id'])) or {}
                if failure.get('blocked'):
                    return {'action': 'worker_blocked', 'task_id': task['id'],
                            'recovery': execution_recovery(failure['code'], failure['failures']),
                            'status': self.status()}
                review = self._continuity.summary(task['id'])
                if review and book['status'] == 'running':
                    return review_handoff(task['id'], review)
            if book['status'] != 'running' and not (book['status'] == 'preparing' and book.get('creation')):
                proposal = self._revision_summary(book)
                if proposal:
                    self.repo.after_commit(lambda: self.presentation.revision(book['revision_directive']))
                    return {'action': 'revision_blocked', 'proposal': proposal, 'status': self.status()}
                return {'action': book['status'], 'status': self.status()}
            if task and wait_pending:
                # Supervision is not a re-dispatch: leave the active worker's files untouched.
                work = task['input']
                return {'action': 'wait_for_submit',
                        'task': {'task_id': task['id'], **{key: work[key] for key in ('stage', 'chapter', 'scope')}}}
            if not task:
                group = self._writing.active()
                if group:
                    current = self.repo.task(group['task_id'])
                    return {'action': 'wait_for_batch', 'task': {'task_id': current['id'],
                            **{key: current['input'][key] for key in ('stage', 'chapter', 'scope')}},
                            'worker_batch': self._writing.describe()}
                choice = workflow.choose(book, self.repo.headers(book['branch']))
                if isinstance(choice, dict) and choice['action'] == 'contract_ready':
                    book = self._contracts.activate(book)
                    self._governance.seal(book)
                    refresh_world = bool(book.get('world'))
                    choice = workflow.choose(book, self.repo.headers(book['branch']))
                if isinstance(choice, dict):
                    if choice['action'] == 'repair_exhausted':
                        book.update(status='paused', pause_reason='原修复额度已经耗尽，改约不重新发初稿额度。')
                        self._save(book)
                    if choice['action'] not in ('world_ready', 'outline_ready'):
                        boundary = {**choice, 'status': self.status()}
                        if choice['action'] not in ('await_choice', 'await_volume_confirm'):
                            return boundary
                        # A board on display falls through: the author-facing card is
                        # materialized below, outside the transaction.
                    else:
                        boundary = {**choice, 'status': self.status()}
                else:
                    task = self._writing.dispatch(book, choice, owner)
        view = {}
        # The world view belongs to boundaries that hand a world over (or a refresh after
        # contract activation); a choice board must not drag an unverified world into the return.
        if refresh_world or boundary and boundary.get('action') in ('world_ready', 'outline_ready'):
            try:
                view['world_view'] = self.presentation.world()
            except OSError as exc:
                view['world_view_error'] = str(exc)
        if boundary and boundary.get('action') in ('await_choice', 'await_volume_confirm') \
                and boundary.get('board') is not None:
            volume_board = boundary['action'] == 'await_volume_confirm'
            # The controller hands work/board.md (or work/volume-board.md) to the author instead of
            # re-rendering the JSON return: GBK consoles garble long UTF-8 stdout, and a live run
            # hand-wrote this card for every gate before the engine owned it. The confirmation
            # board gets the same treatment — a ten-volume staged design is exactly the kind of
            # page a console echo would mangle.
            try:
                boundary['board_card'] = (self.presentation.volume_board(boundary['board'])
                                          if volume_board else self.presentation.board(boundary['board']))
            except OSError as exc:
                boundary['board_card_error'] = str(exc)
            try:
                boundary['question_card'] = (self.presentation.volume_question(boundary['board'])
                                             if volume_board else self.presentation.question(boundary['board']))
            except OSError as exc:
                boundary['question_card_error'] = str(exc)
            if volume_board and isinstance(boundary.get('board_card'), str):
                # The local card links to the separately materialized complete design. Do not echo
                # it into both the response and snapshot; on a delivery error retain it for recovery.
                boundary['board'] = {key: value for key, value in boundary['board'].items() if key != 'design'}
            try:
                boundary['advance_snapshot'] = self.presentation.snapshot(boundary)
            except OSError as exc:
                boundary['advance_snapshot_error'] = str(exc)
            if compact and boundary.get('board_card'):
                # The full board lives on disk (board card + last-advance.json), so the compact
                # return names the options instead of echoing them a second time: a live run paid
                # a file-redirect dance per gate to keep the echo out of its context. The volume
                # board's compact form names the round, the version hash and the staged volumes —
                # the three facts a confirm command needs — and leaves the page to the file.
                board = boundary['board']
                boundary['board'] = ({'round': board.get('round'), 'hash': board.get('hash'),
                                      'volume_ids': board.get('volume_ids')} if volume_board else
                                     {'gate': board.get('gate'), 'round': board.get('round'),
                                      'hash': board.get('hash'), 'system': board.get('system'),
                                      'option_ids': [row.get('id') for row in board.get('options') or []]})
        if boundary:
            return {**boundary, **view}
        return {'action': 'task_ready', 'task': self.presentation.task(task, self._baseline(book, task), compact=compact), 'status': self.status(), **view}

    def recover_engine(self, task_id, input_hash, source, owner=None, worker_stopped=False):
        """Explicit version transition for exactly one pending task; no replanning or budget reset."""
        require(text(source), 'author_source', '重新冻结须保存作者对版本升级的授权原话。')
        with self.repo.transaction():
            self.controller_guard(owner)
            book = self._load()
            task = self.repo.task(task_id)
            pending = self.repo.pending()
            # Tolerate a truncated hex prefix or an all-zero placeholder from the
            # error response's details; a completely different hash is still refused.
            if input_hash and input_hash != pending.get('input_hash'):
                actual = pending.get('input_hash', '')
                is_prefix = len(input_hash) >= 8 and input_hash != '0' * len(input_hash) and actual.startswith(input_hash)
                is_placeholder = set(input_hash) <= {'0'} and len(input_hash) >= 8
                if not (is_prefix or is_placeholder):
                    require(False, 'engine_recovery',
                            '任务或输入版本已变，先核对当前status，不重放旧恢复请求。')
                input_hash = actual
            work = task['input']
            require(work.get('build') and self.build_info and work['build'] != self.build_info,
                    'engine_recovery', '只有构建确实不同的任务需要重新冻结。')
            require(work['branch'] == book['branch'] and work['revision'] == book['revision']
                    and book['status'] in ('running', 'preparing'),
                    'engine_recovery', '项目范围或状态已变，不以版本恢复绕过暂停和作者边界。')
            require(not self.repo.get(store_keys.claim(task_id)) or worker_stopped is True,
                    'worker_busy', '先核实原Worker已停止，再用 --worker-stopped 明确记录；租约过期不证明进程结束。')
            require(self._continuity.summary(task_id) is None, 'continuity_pending',
                    '当前任务仍有关联核验；先处理准确候选，不以版本切换绕过核验。')
            subject = {'task': task_id, 'input_hash': input_hash,
                       'from_build': work['build'], 'to_build': self.build_info}
            self._governance.authorize('engine_upgrade', subject, source)
            payload = {key: copy.deepcopy(value) for key, value in work.get('payload', {}).items()
                       if key != 'worker_batch'}
            job = Job(work['stage'], work['chapter'], work['scope'], work.get('first', 0), work.get('last', 0), payload)
            # Retiring removes only reproducible forms; result.json and existing story drafts remain.
            self._cancel_pending('明确授权的引擎版本切换；保留旧候选和创作依据。')
            book['revision'] += 1
            self._save(book)
            replacement = self._writing.dispatch(book, job, owner)
            require(replacement['input'].get('build') == self.build_info, 'engine_recovery',
                    '编译器没有使用目标构建，恢复事务已撤销。')
            self.repo.record('engine_upgrade', {**subject, 'replacement': replacement['id'],
                                               'source': source, 'worker_stopped': worker_stopped})
        return controller_handoff({'action': 'task_ready', 'recovered': True, 'retired_task': task_id,
                                   'task': self.presentation.task(replacement, self._baseline(book, replacement), compact=True),
                                   'status': self.status()})

    def read(self, task_id, record=None, everything=False, receive=None):
        task = self.repo.task(task_id)
        self._live(task, verify=False)
        work = task['input']
        lease = self.repo.get(store_keys.claim(task_id)) or {}
        if work['stage'] not in CONTROLLER_STAGES:
            self._worker_actor(task, lease.get('session'))
        execution = lease.get('execution_id')
        delivered = self.repo.get(store_keys.execution_reads(execution), {}) if execution else None
        staged = self._world_refusal(task)
        served = {'previous_proposal': digest(staged)} if staged is not None else {}
        names_read = ([name for name, value in delivered.items()
                       if work['records'].get(name) == value or served.get(name) == value]
                      if delivered is not None else self.repo.read_names(task_id))
        already = [] if (record or everything) else [n for n in names_read
                                                     if n in work['records'] or n in served]
        if not record and not everything:
            already = sorted(set(already) | set(self._writing.already_read(task)))
        names = [record] if record else [n for n in work['required'] if n not in already]
        if staged is not None and not record and 'previous_proposal' not in already:
            # The frozen dispatch predates the refusal it produced; the staged previous proposal
            # is the one record `read` serves from outside the frozen input, and only while the
            # repair loop is live — no refusal, no record.
            names.append('previous_proposal')
        available = {**work['records'], **served}
        require(all(n in available for n in names), 'record', '资料不在当前冻结任务目录中。')
        records = {}
        for n in names:
            if n in served and n not in work['records']:
                records[n] = {'hash': served[n], 'value': copy.deepcopy(staged)}
            else:
                records[n] = {'hash': available[n], 'value': self.repo.read_document(available[n])}
        result = {'task_id': task_id, 'input_hash': task['input_hash'], 'complete_records': True,
                  'execution_id': execution,
                  'stage': work['stage'], 'chapter': work['chapter'],
                  'records': records,
                  # One digest over the records this task must read. A controller running
                  # consecutive gates in one session compares it with the previous gate's and
                  # skips the read entirely when the required material did not change, instead
                  # of re-pulling an identical record set per gate.
                  'records_hash': digest({name: work['records'].get(name) for name in work['required']}),
                  'on_demand': {n: h for n, h in available.items() if n not in names}}
        if not record:
            # A worker reads the envelope it already holds, so a second full read of the same task
            # used to re-deliver every required record: a real design run spent more characters
            # re-sending records than on every envelope and receipt together. The journal already
            # knows what this task was handed, so a plain read returns what is still new, and the
            # records that were skipped are named rather than silently dropped.
            if already:
                result['already_read'] = already
                result['already_read_note'] = ('这些记录此前已交给本执行上下文；需要原文时用 read --record 名称重取，'
                                               '或用 read --all 取回全部必读记录。')
        return self._observe_read(task_id, names, result, receive)

    def _observe_read(self, task_id, names, result, receive=None):
        """Count actual supplemental output, including recall; this is not billed usage."""
        with self.repo.transaction():
            task = self.repo.task(task_id)
            lease = self.repo.get(store_keys.claim(task_id)) or {}
            if lease.get('execution_id'):
                key = store_keys.execution_reads(lease['execution_id'])
                delivered = self.repo.get(key, {})
                delivered.update({name: task['input']['records'][name] for name in names
                                  if name in task['input']['records']})
                staged = self._world_refusal(task)
                if staged is not None and 'previous_proposal' in names:
                    # The staged record is served from outside the frozen input; its digest joins
                    # the delivery marks so a repeated read can skip it like any other record.
                    delivered['previous_proposal'] = digest(staged)
                self.repo.put(key, delivered)
            self._writing.record_read(task, names)
            self.repo.record('read', store_keys.read_record(
                task_id, names, len(dump(result)), execution_id=lease.get('execution_id'),
                record_hashes={name: task['input']['records'][name] for name in names
                               if name in task['input']['records']}))
            if receive is not None:
                # Cache only successfully delivered material. The adapter's file failure
                # rolls back this execution's delivery marks and read journal together.
                return receive(result)
        return result

    def check(self, payload, task_id=None, session=None):
        """Dry-run a candidate receipt without submitting it, and without needing its task identity.

        A worker can ask "would this be accepted, and if not which field is wrong" against the current
        pending task, so it never has to read the engine's source to learn the format. Nothing is
        committed: the task comes straight from the repository and the receipt is only previewed.

        The answer separates two questions a worker used to have to guess between: `valid` says the
        receipt passed every check, `committed` says the ledger changed. A preview is never committed,
        so `accepted` stays false here — it means "nothing was accepted into the book", not "rejected".
        """
        task = self.repo.task(task_id) if task_id else self.repo.pending()
        require(task is not None, 'task', '项目当前没有在途任务可供试算。',
                {'recover': '先由主控 advance 派工，再对返回的 task_id 运行 check。'})
        require(task['status'] == 'pending', 'stale_task', '该任务已结束，不能用它试算。')
        require(isinstance(payload, dict), 'schema', '待检回执须为 JSON 对象。')
        require(payload.get('schema') == RESULT, 'schema', '回执缺 schema=' + RESULT + '。')
        require(payload.get('input_hash') == task['input_hash'], 'input_version', 'input_hash 与当前任务不符。',
                {'expected': task['input_hash'], 'got': payload.get('input_hash')})
        require(payload.get('task_id'), 'result', '回执缺 task_id。')
        # A candidate is often missing the session line while being drafted. Use the explicit
        # caller supplied by the entry adapter, or preview under the task's own reader; the
        # lease and session rules stay enforced for anything that actually commits.
        caller = session
        session = payload.get('session') or caller or task['reviewer'] or 'check-preview'
        if caller:
            require(session == caller, 'session', '试算身份与会话不符。')
        self._session(task, session, check_lease=False)
        preview = self.submit({**payload, 'session': session}, preview=True)
        return {**preview, 'valid': True, 'session_used': session}

    def submit(self, result, preview=False):
        require(isinstance(result, dict) and result.get('schema') == RESULT, 'schema', '回执协议无效。')
        refusal = []
        try:
            return self._submit(result, preview, refusal)
        except Error:
            # A refused world candidate is staged only after the submit transaction has fully
            # rolled back: writing it inside would be undone together with everything else.
            if refusal:
                self._stage_world_refusal(*refusal[0])
            raise

    def _submit(self, result, preview, refusal=None):
        refusal = refusal if refusal is not None else []
        with self.repo.transaction(preview=preview):
            task = self.repo.task(result.get('task_id'))
            if task['input']['stage'] not in CONTROLLER_STAGES:
                self._worker_actor(task, result.get('session'))
            if task['status'] == 'done':
                require(task['result_hash'] == digest(result), 'replay_conflict', '同一任务不能提交不同内容。')
                group = self._writing.active()
                continuing = bool(group and group['task_id'] == task['id'])
                saved = self.repo.get(store_keys.task_outcome(task['id']), {})
                response = {**saved, 'valid': True, 'accepted': not preview, 'checked': preview, 'committed': not preview,
                        'idempotent': True, 'task_id': task['id'],
                        'worker_boundary': 'continue' if continuing else 'finished'}
                if not saved:
                    response.update(outcome='receipt_replayed', legacy_outcome_unknown=True,
                                    committed_chapter=None)
                self.repo.after_commit(lambda: self._refresh_book(response))
                return response
            book = self._live(task)
            failure = self.repo.get(store_keys.technical_failure(task['id'])) or {}
            require(not failure.get('blocked'), 'technical_blocked', '本任务技术错误已交回主控。')
            require(book['status'] == 'running' or (book['status'] == 'preparing' and task['input']['stage'] == 'opening_options'),
                    'paused', '项目暂停，保留回执并由主控恢复。')
            require(result.get('input_hash') == task['input_hash'], 'input_version', '输入版本不匹配。',
                    {'expected': task['input_hash'], 'got': result.get('input_hash'),
                     'recover': '信封字段不手写：从本任务目录的 result.template.json 复制起稿，只改 data。'})
            self._session(task, result.get('session'), result.get('execution_claim'))
            if task['input']['stage'] not in CONTROLLER_STAGES:
                self._worker_actor(task, result['session'])
            work = copy.deepcopy(task['input'])
            # Mechanical prose defects are judged here, inside the same reconciliation that decides
            # whether the chapter commits; the producer sees the finding without spending a review
            # round, and preflight runs the same code.
            priors = self._priors(book, work['chapter']) if work['stage'] in ('write', 'repair', 'redesign') else None
            try:
                outcome = workflow.apply(book, work, result.get('data'), result['session'],
                                         self._sources(work), priors,
                                         previous_world=self._world_refusal(task))
            except Error as error:
                # The refused candidate is the only honest base its repair can build on. Remember
                # it here for `submit` to stage after the rollback; a preview never stages.
                if work['stage'] == 'world_model' and not preview:
                    refusal.append((task['id'], result.get('data'), error))
                raise
            review = None
            if outcome.chapter and self._governance.policy()['continuity'] == 'required':
                review = self._continuity.evaluation(task['id'], result)
                if review is None or review.get('pending'):
                    request = None if preview else self._continuity.prepare(task, result, outcome.chapter)
                    return {'valid': True, 'accepted': False, 'checked': preview, 'committed': False,
                            'task_id': task['id'], 'committed_chapter': None, 'outcome': 'continuity_review_required',
                            'candidate_hash': self._continuity.candidate_hash(result),
                            'request_id': request['request_id'] if request else self._continuity.candidate_hash(result),
                            'transaction': {'persisted': not preview, 'preview': preview}, 'findings': [],
                            'next_action': {'actor': 'controller', 'action': 'prepare_independent_observer'},
                            'worker_boundary': 'await_review', 'rework': copy.deepcopy((book.get('rework') or {}).get(str(work['chapter'])))}
                if review['findings']:
                    outcome = workflow.apply(book, work, result.get('data'), result['session'],
                                             self._sources(work), priors, external_findings=review['findings'])
                if outcome.chapter:
                    outcome.chapter['review']['continuity'] = review
            updated = outcome.book
            updated['last_task'] = task['id']
            if outcome.chapter:
                row = copy.deepcopy(outcome.chapter)
                # prose/events/plan/review are stored as immutable documents; `review` now holds the
                # chapter's reconciliation record (drift_check + alignment diagnostics + self_check).
                for field in ('prose', 'events', 'plan', 'review'):
                    row[field] = self.repo.document(row[field])
                previous = self.repo.headers(book['branch'])
                require(row['n'] == (previous[-1]['n'] + 1 if previous else 1), 'chapter_order', '正式章节只能顺序提交。')
                row['chain'] = facts.chain(previous[-1]['chain'] if previous else 'genesis', row, digest(book['contract']))
                self.repo.add_chapter(book['branch'], row)
            if work['stage'] not in CONTROLLER_STAGES:
                # Session binding keeps one worker per task: a replay of the same receipt stays
                # idempotent, and a second submission from another session is refused.
                self._writing.bind(task, result['session'])
            self.repo.finish_task(task['id'], result)
            if work['stage'] == 'world_model':
                # The accepted world supersedes the staged refusal; a later world task (a redesign
                # after a re-contract) is a new task id and starts from a clean slate.
                self.repo.put(store_keys.world_rejection(task['id']), None)
            revision = updated.get('revision_run')
            if revision and outcome.chapter and revision['last'] <= outcome.chapter['n'] and revision.get('carry'):
                # A narrow revision carries its untouched suffix once its own end commits.
                self._revisions.carry_suffix(updated, revision)
            if outcome.chapter:
                self._revisions.refresh_understanding(updated)
            if updated.get('revision_directive'):
                directive = updated['revision_directive']
                updated = self._revisions.start_revision(updated, directive)
            worker_boundary = self._writing.after_submit(updated, task)
            self._save(updated)
            self.repo.record('submit', {'task': task['id'], 'stage': work['stage'], 'committed_chapter': outcome.chapter is not None})
            response = {'valid': True, 'accepted': not preview, 'checked': preview, 'committed': not preview,
                        'task_id': task['id'], 'worker_boundary': worker_boundary,
                        'committed_chapter': outcome.chapter['n'] if outcome.chapter else None,
                        'next_stage': updated['draft']['stage'] if updated['draft'] else None,
                        'rework': (updated.get('rework') or {}).get(str(work['chapter'])), 'status': updated['status']}
            finding_rows = copy.deepcopy(outcome.findings or [])
            # A staged volume outline is an author boundary exactly like an open question: the
            # design passed every mechanical check and now waits for the author's own words, so
            # nothing continues automatically — not a repair round, not the next dispatch.
            volume_pending = bool(updated.get('pending_design'))
            needs_author = bool(updated.get('author_block') or volume_pending or updated['status'] == 'paused')
            business = ('volume_confirmation_required' if volume_pending else
                        'author_decision_required' if needs_author else
                        'repair_required' if finding_rows else
                        ('candidate_ready' if preview else 'chapter_committed') if outcome.chapter else 'design_accepted')
            response.update(outcome=business, findings=finding_rows,
                            transaction={'persisted': not preview, 'preview': preview},
                            next_action={'actor': 'author' if needs_author else 'worker' if finding_rows else 'controller',
                                         'action': ('confirm_volume' if volume_pending else 'answer' if needs_author
                                                    else 'revise_candidate' if finding_rows else 'continue')},
                            effects_if_submitted={'chapter_commit': bool(outcome.chapter),
                                                  'repair_consumption': int(work['stage'] == 'repair')})
            if not preview:
                response['continuation'] = submission_handoff(worker_boundary, needs_author)
            if outcome.style_report is not None:
                response['style_report'] = outcome.style_report
            if review is not None:
                response['quality_report'] = review
            self.repo.put(store_keys.task_outcome(task['id']), response)
            # Includes fast-mode submissions: they need no controller advance
            # between chapters. Preview/rollback must leave the page untouched.
            self.repo.after_commit(lambda: self._refresh_book(response))
        return response

    def claim(self, task_id, session, seconds=None, fresh_context=False):
        require(text(session), 'claim', '认领需要真实会话。')
        with self.repo.transaction():
            task = self.repo.task(task_id)
            if seconds is None:
                seconds = policy_default('single_delivery_lease_seconds' if task['input']['stage'] in SINGLE_DELIVERY_STAGES else 'worker_lease_seconds')
            require(type(seconds) is int and seconds > 0, 'claim', '租期须为正整数。')
            self._live(task)
            self._session(task, session, check_lease=False)
            old = self.repo.get(store_keys.claim(task_id))
            require(not old or old['until'] <= self.clock() or old['session'] == session, 'worker_busy', '另一 Worker 仍持有任务租约。')
            provenance = self._governance.authorize('worker', {'task': task_id, 'session': session})
            reuse = bool(old and old['session'] == session and not fresh_context)
            lease = {'session': session, 'token': old['token'] if reuse else self.new_id(),
                     'execution_id': (old.get('execution_id') if reuse else None) or self.new_id(),
                     'provenance': provenance,
                     'until': self.clock() + seconds, 'seconds': seconds}
            self.repo.put(store_keys.claim(task_id), lease)
            self._writing.bind(task, session, seconds)
            if fresh_context:
                group = self._writing.active()
                if group:
                    group['read_hashes'] = {}
                    self.repo.put(store_keys.WRITING_BATCH, group)
            self.repo.record('worker_prepared', {'task': task_id, 'session': session,
                                               'execution_id': lease['execution_id'], 'fresh_context': fresh_context})
            return {**lease, 'usage': '回执顶层 execution_claim 填写返回的 token 字段（裸字符串，非对象）。'}

    def release_claim(self, task_id, token):
        with self.repo.transaction():
            claim = self.repo.get(store_keys.claim(task_id))
            require(claim is not None and claim['token'] == token, 'worker_lease', '不能释放其他执行的认领。')
            self.repo.put(store_keys.claim(task_id), None)
            self.repo.record('worker_release', {'task': task_id})

    def run(self, through=None, finish=False, owner=None, seconds=None, source='', mode=None, batch=None):
        seconds = policy_default('controller_lease_seconds') if seconds is None else seconds
        require(type(seconds) is int and seconds > 0, 'lease', '租期须为正整数。')
        require(mode in (None, 'standard', 'fast'), 'writing_mode', '写作模式须为 standard 或 fast。')
        with self.repo.transaction():
            self.controller_guard(owner)
            book = self._load()
            selected_mode = mode or book.get('writing_mode', 'standard')
            if batch is not None:
                selected_batch = batch
            else:
                selected_batch = book.get('writing_batch_chapters') or policy_default('fast_batch_chapters')
            require(type(selected_batch) is int and selected_batch > 0, 'writing_batch',
                    '连写组章数须为正整数（run --batch N）。')
            group = self._writing.active()
            require(not group or selected_mode == book.get('writing_mode') and owner == group['owner'],
                    'writing_batch', '连写组仍在执行，先等本组结束；停止执行后可 pause --cancel 保留进度再切换模式。')
            require(book['contract'] is not None, 'creation', '开书约定尚未激活，先完成世界与约定的机械校验。')
            end = editorial.effective_contract(book)['volumes'][-1]['end']
            target = end if finish else through
            require(type(target) is int and 1 <= target <= end, 'target', '运行目标须为约定范围内的章号。')
            self._governance.authorize('run', {'target': target, 'finish': finish, 'mode': selected_mode,
                                               'batch': selected_batch}, source)
            pending = self.repo.pending()
            require(not pending or pending['input']['chapter'] <= target, 'target', '目标不能低于已冻结任务，先 pause --cancel。')
            # A narrow revision carries its suffix automatically once its end chapter commits, so a
            # run target beyond the revision end no longer overshoots the propagation range.
            require(book['revision_run'] is None or target >= book['revision_run']['last'], 'revision_target', '运行目标不能低于修订范围，先完成或撤销修订。')
            owner = owner or self.new_id()
            self.repo.put(store_keys.CONTROLLER, {'owner': owner, 'until': self.clock() + seconds})
            require(not group or target == book['target'] and finish == book['finish'],
                    'writing_batch', '连写期间不能改变授权终点，先停止当前组。')
            book.update(target=target, finish=finish, run_authorized=True, writing_mode=selected_mode,
                        writing_batch_chapters=selected_batch)
            book['decisions'].append({'kind': 'run', 'target': target, 'finish': finish, 'source': source,
                                      'mode': selected_mode, 'batch': selected_batch})
            self._save(book)
            self.repo.record('run', {'target': target, 'finish': finish, 'mode': selected_mode,
                                     'batch': selected_batch, 'source': source})
            return {'owner': owner, 'target': target, 'finish': finish, 'lease_seconds': seconds,
                    'writing_mode': selected_mode, 'writing_batch_chapters': selected_batch}

    def continue_writing(self, task_id, session, claim=None):
        """A worker's bounded continuation capability, never a general advance or author command."""
        with self.repo.transaction():
            book = self._load()
            self._worker_actor(self.repo.task(task_id), session)
            task, lease = self._writing.continue_task(book, task_id, session, claim)
        if task is None:
            return {'action': 'batch_finished', 'worker_boundary': 'finished'}
        failure = self.repo.get(store_keys.technical_failure(task['id'])) or {}
        if failure.get('blocked'):
            return {'action': 'worker_blocked', 'task_id': task['id'], 'worker_boundary': 'finished',
                    'recovery': execution_recovery(failure['code'], failure['failures'])}
        return {'action': 'task_ready', 'worker_boundary': 'continue',
                'task': self.presentation.task(task, self._baseline(book, task), compact=True),
                'execution_claim': lease['token'] if lease else None}

    def renew(self, owner, seconds=None):
        seconds = policy_default('controller_lease_seconds') if seconds is None else seconds
        require(type(seconds) is int and seconds > 0, 'lease', '租期须为正整数。')
        with self.repo.transaction():
            run = self.repo.get(store_keys.CONTROLLER)
            require(run is not None and run['owner'] == owner and run['until'] > self.clock(), 'controller_lease', '主控租约已失效。')
            run['until'] = self.clock() + seconds
            self.repo.put(store_keys.CONTROLLER, run)
        return run

    def approve(self, prose_hash, source, owner=None):
        require(text(source), 'author_source', '保存作者认可原话。')
        with self.repo.transaction():
            self.controller_guard(owner)
            book = self._load()
            row = self.repo.chapter(book['branch'], 1)
            require(row['prose'] == prose_hash, 'pilot_version', '认可版本与当前首章不一致。')
            self._governance.authorize('approve', {'prose_hash': prose_hash}, source)
            book['pilot'] = {'prose': prose_hash, 'contract': digest(book['contract']), 'source': source}
            # The approved first chapter is the voice anchor, for every project: v2.1 carries
            # literary consistency with style, so the sample must not depend on the editorial flag
            # (that flag gates patch/scene capabilities, not the voice). The registration is the
            # voice/气质 sample plus the opening reference; each later chapter's numeric expect is
            # rolled forward by style.current_anchor over the nearest approved chapters.
            book['style_anchor'] = {'prose_hash': prose_hash, 'sample': self.repo.read_document(row['prose']),
                                    'voice': book['contract']['voice'], 'traits': book['contract']['style_traits'],
                                    'source': source}
            self._save(book)
            self.repo.record('approve', book['pilot'])
        return {'approved': True, 'prose_hash': prose_hash}

    def confirm_volume(self, volumes_hash, source, owner=None):
        """The author approves the staged volume outline, bound to its exact version.

        The same shape as the first-chapter approval: the author's words are recorded against the
        staged `volumes_hash`, a stale hash is refused instead of approving whatever happens to be
        staged now, and the installation of the volume outlines with their merged chapter half and
        settlement rows is one transaction — the lock is "not installed yet", so confirmation is
        the only event that installs anything.
        """
        require(text(source), 'author_source', '认可卷纲须保存作者原话。')
        with self.repo.transaction():
            self.controller_guard(owner)
            book = self._load()
            pending = book.get('pending_design')
            require(isinstance(pending, dict), 'volume_confirm', '当前没有待认可的卷纲。')
            require(workflow.verify_design_hash(pending), 'volume_confirm',
                    '待认可内容与保存的版本不一致，请保留现场并核对暂存设计。')
            require(pending['volumes_hash'] == volumes_hash, 'volume_confirm',
                    '认可版本与当前暂存卷纲不一致，不能串版认可。',
                    {'expected': pending['volumes_hash'], 'got': volumes_hash,
                     'recover': '以 status.volume_gate.pending_hash 或 await_volume_confirm 返回的 '
                                'volumes_hash 重新执行。'})
            subject = {'volumes_hash': volumes_hash, 'round': pending['round'],
                       'volumes': list(pending['volume_ids'])}
            self._governance.authorize('volume_confirm', subject, source)
            workflow.activate_design(book)
            book['decisions'].append({'kind': 'volume_confirm', 'round': subject['round'],
                                      'volumes_hash': volumes_hash, 'source': source})
            book['revision'] += 1
            self._save(book)
            self.repo.record('volume_confirm', {**subject, 'source': source})
        return {'confirmed': True, 'volumes_hash': volumes_hash,
                'volumes': subject['volumes'], 'round': subject['round']}

    def revise_volume(self, adjustments, volumes_hash, source, owner=None):
        """The author's light edits to the staged design's narrative fields, re-validated in place.

        The whitelist is the author-facing prose only (purpose/arc/turns/climax/exit_state and
        style.trend); structural fields are refused with the re-run command, because a nudge there
        would invalidate the merged chapter half and the checks that already passed. The whole
        staged batch is re-validated after the edit and the hash is rebound, so the next
        confirmation still binds to exactly one version.
        """
        require(text(source), 'author_source', '轻调卷纲须保存作者原话。')
        with self.repo.transaction():
            self.controller_guard(owner)
            book = self._load()
            pending = book.get('pending_design')
            require(isinstance(pending, dict), 'volume_confirm', '当前没有待认可的卷纲。')
            require(workflow.verify_design_hash(pending), 'volume_confirm',
                    '待认可内容与保存的版本不一致，请保留现场并核对暂存设计。')
            require(pending['volumes_hash'] == volumes_hash, 'volume_confirm',
                    '调整版本与当前暂存卷纲不一致，先核对当前哈希。',
                    {'expected': pending['volumes_hash'], 'got': volumes_hash})
            self._governance.authorize('volume_revise',
                                       {'volumes_hash': volumes_hash, 'round': pending['round']}, source)
            workflow.revise_design(book, adjustments)
            book['decisions'].append({'kind': 'volume_revise',
                                      'volumes_hash': book['pending_design']['volumes_hash'], 'source': source})
            book['revision'] += 1
            self._save(book)
            self.repo.record('volume_revise', {'volumes_hash': book['pending_design']['volumes_hash'],
                                               'source': source})
        return {'revised': True, 'volumes_hash': book['pending_design']['volumes_hash'],
                'round': book['pending_design']['round']}

    def regroup_volume(self, volumes_hash, reason, blueprint=None, owner=None):
        """Drop the staged design with the author's reason; the reason feeds the next design round.

        The opening regroup's semantics at the volume gate: the refusal is recorded on the gate's
        own ledger (round, reason, what was refused), the round advances, the staging is cleared,
        and the world and contract stay. The next volume-outline dispatch freezes the refusal as
        input, so the re-run answers it instead of re-offering the same shape. `blueprint` switches
        the book's blueprint in the same breath — either layer, resolved by name — so the re-run is
        the moment a new blueprint takes effect.
        """
        require(text(reason), 'author_source', '保存作者退回理由；可以是用户只说的"换一版"。')
        with self.repo.transaction():
            self.controller_guard(owner)
            book = self._load()
            pending = book.get('pending_design')
            require(isinstance(pending, dict), 'volume_confirm', '当前没有待认可的卷纲。')
            require(pending['volumes_hash'] == volumes_hash, 'volume_confirm',
                    '退回版本与当前暂存卷纲不一致，先核对当前哈希。',
                    {'expected': pending['volumes_hash'], 'got': volumes_hash})
            subject = {'volumes_hash': volumes_hash, 'round': pending['round'],
                       'volumes': list(pending['volume_ids'])}
            self._governance.authorize('volume_regroup', subject, reason)
            if blueprint is not None:
                layer, _entry = resolve_blueprint(blueprint)
                require(layer, 'blueprint', '未知蓝图档名。', {'valid': blueprint_valid()})
                self._governance.authorize('blueprint', {'name': blueprint, 'layer': layer}, reason)
                book['%s_blueprint' % layer] = {'name': blueprint, 'source': reason}
            workflow.regroup_design(book, reason)
            book['decisions'].append({'kind': 'volume_regroup', 'round': subject['round'],
                                      'blueprint': blueprint, 'source': reason})
            book['revision'] += 1
            self._save(book)
            self.repo.record('volume_regroup', {**subject, 'reason': reason,
                                                'blueprint': blueprint, 'source': reason})
        return {'regrouped': True, 'round': (book.get('volume_gate') or {}).get('round', 0),
                'blueprint': blueprint}

    def blueprint(self, name, source, regenerate=False, owner=None):
        """Bind (or re-bind) a blueprint on either layer; optionally retire unwritten designs.

        Blueprints are one system in two decoupled layers sharing one namespace: the name resolves
        to the structure layer (a skeleton the volume and chapter designs follow) or the design
        layer (an author-confirmed reference document the volume dispatch ships as a guide). Each
        layer binds at most one per book and replaces its own slot only. A binding is a book-level
        author setting, absent by default — the engine never chooses one for the author. With
        `regenerate`, the volumes that have no committed prose (and no live draft) lose their
        outlines and settlement rows and are re-dispatched under the new blueprint; volumes with
        prose keep their outlines as history, so a late switch mixes skeletons by the author's own
        decision. Switching inside the gate goes through regroup-volume --blueprint instead, so the
        staged design and the blueprint change together.
        """
        require(text(source), 'author_source', '选择蓝图须保存作者原话。')
        layer, _entry = resolve_blueprint(name)
        require(layer, 'blueprint', '未知蓝图档名。', {'valid': blueprint_valid()})
        slot = '%s_blueprint' % layer
        with self.repo.transaction():
            self.controller_guard(owner)
            book = self._load()
            self._governance.authorize('blueprint', {'name': name, 'layer': layer,
                                                     'regenerate': regenerate}, source)
            removed = []
            if regenerate:
                require(book.get('pending_design') is None, 'volume_confirm',
                        '门内换蓝图与重出一版一体执行，不在 blueprint --regenerate 里清暂存。',
                        {'recover': '用 regroup-volume --hash 当前哈希 --reason 原话 --blueprint 档名。'})
                headers = self.repo.headers(book['branch'])
                written = {row['n'] for row in headers}
                draft = book.get('draft') or {}
                volumes = editorial.effective_contract(book)['volumes']
                busy = {volume['id'] for volume in volumes
                        if any(volume['first'] <= n <= volume['end'] for n in written)
                        or (draft and volume['first'] <= draft.get('chapter', 0) <= volume['end'])}
                removed = [volume['id'] for volume in volumes if volume['id'] not in busy]
                require(removed, 'blueprint',
                        '全部卷都已有正文或草稿，蓝图重生成无纲可删；改结构走 revise 或 recontract。',
                        {'written_volumes': sorted(busy)})
                retired = {n for volume in volumes if volume['id'] in removed
                           for n in range(volume['first'], volume['end'] + 1)}
                outlines = book.get('volumes_outline') or {}
                chapter_outlines = book.get('chapter_outlines') or {}
                plans = book.get('plans') or {}
                for ident in removed:
                    outlines.pop(ident, None)
                    chapter_outlines.pop(ident, None)
                for n in retired:
                    plans.pop(str(n), None)
                book['volumes_outline'] = outlines
                book['chapter_outlines'] = chapter_outlines
                book['plans'] = plans
            book[slot] = {'name': name, 'source': source}
            book['decisions'].append({'kind': 'blueprint', 'name': name, 'layer': layer,
                                      'regenerate': regenerate, 'source': source})
            book['revision'] += 1
            self._cancel_pending('蓝图变更：在途设计任务按新蓝图重派。')
            self._save(book)
            self.repo.record('blueprint', {'name': name, 'layer': layer, 'regenerate': regenerate,
                                           'removed_volumes': removed, 'source': source})
        return {'blueprint': name, 'layer': layer, 'regenerated': bool(regenerate),
                'removed_volumes': removed}

    def opening_choice(self, option, board_hash, source, owner=None):
        with self.repo.transaction():
            self.controller_guard(owner)
            book = self._load()
            self._governance.authorize('opening_choice', {'option': option, 'board': board_hash}, source)
            result = self._opening.choice(book, option, board_hash, source)
            self._save(book)
        return result

    def intake(self, values, source, owner=None):
        with self.repo.transaction():
            self.controller_guard(owner)
            book = self._load()
            self._governance.authorize('intake', values, source)
            result = self._opening.intake(book, values, source)
            self._save(book)
        return result

    def usage(self):
        return self.repo.usage()

    def prepare_observer(self, request_id, session, owner=None):
        with self.repo.transaction():
            self.controller_guard(owner)
            self._load()
            return self._continuity.prepare_observer(request_id, session)

    def recover_observer(self, request_id, observer, stopped, source, owner=None):
        with self.repo.transaction():
            self.controller_guard(owner)
            self._load()
            return self._continuity.recover_observer(request_id, observer, stopped, source)

    def read_review(self, request_id, session, token, chapter=None, compare=False):
        with self.repo.transaction():
            self._load()
            return self._continuity.read(request_id, session, token, chapter, compare)

    def observe_review(self, payload, session, token):
        require(isinstance(payload, dict), 'continuity_observation', '观察回执须为对象。')
        with self.repo.transaction():
            self._load()
            return self._continuity.observe(payload, session, token)

    def report_review(self, payload, session, token):
        require(isinstance(payload, dict), 'continuity_report', '核验回执须为对象。')
        with self.repo.transaction():
            self._load()
            return self._continuity.report(payload, session, token)

    def resolve_review(self, request_id, disposition, source, owner=None):
        with self.repo.transaction():
            self.controller_guard(owner)
            self._load()
            return self._continuity.resolve(request_id, disposition, source)

    def opening_tier(self, tier, source, owner=None):
        """Choose a size class by ladder position, however the window happens to be placed.

        A size class is not a creative proposal: making the author regroup and guess how many
        times to slide is an accident of the board, not a decision. The choice stays bound to a
        shown board, so this slides the ladder until the named tier is visible and picks it.
        """
        for _ in range(len(SCALE_TIERS)):
            book = self._load()
            board = (book.get('creation') or {}).get('board') or {}
            require(board.get('gate', {}).get('id') == 'scale', 'opening_gate',
                    '只有结构门可以按档位直接指定。', {'gate': board.get('gate', {}).get('id')})
            option = next((row for row in board.get('options', []) if row['value'].get('tier') == tier), None)
            if option is not None:
                return self.opening_choice(option['id'], board['hash'], source, owner)
            self.opening_regroup(board['hash'], '按档位直接指定：窗口沿阶梯滑动。', owner)
        require(False, 'opening_option', '该档位不在体量阶梯中。',
                {'valid_tiers': [row['id'] for row in SCALE_TIERS]})

    def opening_regroup(self, board_hash, reason, owner=None):
        with self.repo.transaction():
            self.controller_guard(owner)
            book = self._load()
            result = self._opening.regroup(book, board_hash, reason)
            self._save(book)
        # A structural gate's regroup already holds the next board (the ladder slid), so the card
        # materializes here: work/board.md must never keep showing the retired board the regroup
        # just replaced — the controller forwards that file to the author, and its stale hash
        # would be refused by the next choose/regroup. Creative gates leave the board empty;
        # their next advance dispatches the options task and refreshes the card itself.
        creation_state = book.get('creation') or {}
        board = creation_state.get('board') if creation_state.get('phase') == 'choosing' else None
        if isinstance(board, dict) and board.get('hash'):
            boundary = {'action': 'await_choice', 'board': copy.deepcopy(board), 'status': self.status()}
            result['action'] = boundary['action']
            result['board'] = {'gate': board.get('gate'), 'round': board.get('round'),
                               'hash': board.get('hash'), 'system': board.get('system'),
                               'option_ids': [row.get('id') for row in board.get('options') or []]}
            try:
                result['board_card'] = self.presentation.board(board)
            except OSError as exc:
                result['board_card_error'] = str(exc)
            try:
                result['question_card'] = self.presentation.question(board)
            except OSError as exc:
                result['question_card_error'] = str(exc)
            try:
                result['advance_snapshot'] = self.presentation.snapshot(boundary)
            except OSError as exc:
                result['advance_snapshot_error'] = str(exc)
        return result

    def opening_back(self, gate, reason, owner=None):
        with self.repo.transaction():
            self.controller_guard(owner)
            book = self._load()
            result = self._opening.back(book, gate, reason)
            self._save(book)
        return result

    def pause(self, reason, cancel=False, owner=None):
        require(text(reason), 'pause', '暂停须有原因。')
        with self.repo.transaction():
            self.controller_guard(owner)
            book = self._load()
            book.update(status='paused', pause_reason=reason)
            self._save(book)
            if cancel:
                self._cancel_pending(reason)
            self.repo.record('pause', {'reason': reason, 'cancel': cancel})
        return self.status()

    def resume(self, owner=None, source=''):
        with self.repo.transaction():
            self.controller_guard(owner)
            book = self._load()
            require(book['status'] == 'paused', 'resume', '只有暂停项目可以恢复。')
            draft = book.get('draft')
            if draft and draft.get('stage') == 'exhausted':
                # A single chapter that used its repair rounds used to dead-end here: `resume`
                # refused with a budget code and the only exits were discarding the candidate or
                # changing the contract. The role of resume is to hand the decision up instead.
                workflow.hold_for_draft_exhaustion(book)
                self._save(book)
                return self.status()
            require(not self._revision_summary(book), 'revision_bounds', '先处理超出自动回改范围的修复方案，resume 不扩大授权。',
                    self._revision_summary(book))
            require(not book['draft'] or book['draft']['stage'] != 'exhausted', 'repair_budget',
                    '修复额度已耗尽，恢复不增加额度；作者需明确处置当前方案。')
            require(not book.get('author_block'), 'author_decision', '原作者裁决尚未回答，不能通过 resume 绕过。')
            require(not book.get('remedy_exhausted'), 'remedy_exhausted', '根问题最后一轮失败，不能 resume 重发。')
            self._governance.authorize('resume', {'branch': book['branch'], 'revision': book['revision']}, source)
            book['status'] = 'running'
            # The stop is over; leaving its reason on the book makes status read as paused to every
            # consumer that looks at pause_reason first.
            book.pop('pause_reason', None)
            self._save(book)
            self.repo.record('resume', {'branch': book['branch'], 'revision': book['revision'], 'source': source})
        return self.status()

    def answer(self, decision_id, option, source, owner=None):
        """Record the author's answer to a pending decision and release the halt it caused.

        The question was handed up because no rewrite could settle it, so only the author can close
        it: the chosen option and the author's own words go on the record under the same question,
        and the block is cleared. A third way the options do not cover is a new decision, not an
        answer to this one — it goes back through the stage that asks (recontract for a changed
        premise), which is also how the pending block is replaced.
        """
        require(text(decision_id) and text(option), 'author_decision', '答复须指明待决问题的 id 与所选选项。')
        require(text(source), 'author_source', '保存作者答复的原话。')
        with self.repo.transaction():
            self.controller_guard(owner)
            book = self._load()
            block = book.get('author_block')
            require(isinstance(block, dict), 'author_decision', '当前没有待作者裁决的问题。')
            require(block.get('id') == decision_id, 'author_decision', '答复的问题与待决问题不一致。',
                    {'expected': block.get('id'), 'got': decision_id})
            self._governance.authorize('answer', {'decision_id': decision_id, 'option': option,
                                                 'subject': block.get('subject')}, source)
            if decision_id.startswith(('repair-exhausted:', 'repair-stalled:')):
                parts = decision_id.split(':')
                require(len(parts) == 3 and isinstance(block.get('subject'), dict)
                        and parts[2] == digest(block['subject']), 'author_decision',
                        '裁决对象与问题身份不一致，不能追加额度。')
            labels = [row['label'] for row in block.get('options') or []]
            require(option in labels, 'author_decision', '答复须是已展示的选项之一；作者另有第三条路时走改约或重新提案。',
                    {'options': labels, 'got': option,
                     'recover': '把第三条路整理成完整候选后执行 recontract --file 并附作者原话，经机械校验激活后回答本问题；'
                                '注意已有正文的改约会在新分支自第 1 章重写全书并重新机械核算（父分支保留，可 discard 恢复），'
                                '先向作者说明该代价再动手。'})
            book.setdefault('author_decision_history', []).append(
                {'question': copy.deepcopy(block),
                 'resolution': {'result': 'answered', 'option': option, 'reason': source}, 'reviewer': owner})
            # The answer must reach the next draft, which is why it joins the author's own words:
            # every task reads author_feedback, so the premise is re-drafted against it, not guessed.
            book['feedback'].append('作者裁决：' + block['question'] + ' → ' + option + '（作者原话：' + source + '）')
            book.pop('author_block', None)
            # Recording an answer moves the project on, so a task dispatched before the answer can
            # never be submitted again (its frozen revision is now old). Retiring it here turns a
            # worker that would only discover staleness on read into an explicit, immediate signal.
            stale = self._cancel_pending('作者裁决已记录：此前派出的任务随之失效。')
            if book.get('pause_reason') == block.get('question'):
                book.pop('pause_reason', None)
                book['status'] = 'running'
            decision = str(block.get('id', ''))
            if decision.startswith(('repair-exhausted:', 'repair-stalled:')):
                # The question was "the repair budget is spent" or "the same findings keep coming
                # back"; either way the answer decides what happens to this chapter's loop:
                # one more round, accepting the candidate with the findings kept open, or stopping
                # here so the author can redo the chapter themselves.
                stage = decision.split(':')[1]
                require(stage == 'chapter_repair', 'author_decision', '未知的额度停止点。', {'stop': decision})
                workflow.resolve_draft_exhaustion(book, option, block.get('subject'))
            book['revision'] += 1
            self._save(book)
            self.repo.record('author_decision', book['author_decision_history'][-1])
        answer = self.status()
        if stale:
            answer['retired_task'] = stale
            answer['retired_task_note'] = '该派工在裁决之前冻结，已作废；按当前状态重新 advance 再派 Worker。'
        return answer

    def set_lexical(self, override, source, owner=None):
        """The author's lexical rules live on the book, not inside a contract; each change is a version."""
        require(isinstance(override, dict) and set(override) <= set(POLICY_FIELDS), 'lexical_policy',
                '字面规则只接受 forbidden_terms/forbidden_name_chars/allowed_latin。')
        require(text(source), 'author_source', '保存作者改字面规则的原话。')
        policy = planning.resolve_policy(override)
        with self.repo.transaction():
            self.controller_guard(owner)
            book = self._load()
            self._governance.authorize('lexical', override, source)
            versions = book.setdefault('lexical_policy', [])
            require(bool(versions), 'lexical_policy', '项目缺少字面规则记录。')
            require(planning.policy_of(book) != policy, 'lexical_policy', '字面规则与当前版本相同，未改动。')
            versions.append({'version': len(versions) + 1, 'policy': policy, 'source': source})
            book['revision'] += 1
            book['decisions'].append({'kind': 'lexical', 'version': len(versions), 'source': source})
            self._cancel_pending('lexical policy changed')
            self._save(book)
            self.repo.record('lexical_policy', {'version': len(versions), 'source': source, 'policy': policy})
        return {'version': len(versions), 'policy': policy, 'active': True}

    def feedback(self, message, owner=None):
        require(text(message), 'feedback', '反馈须为具体作者要求。')
        with self.repo.transaction():
            self.controller_guard(owner)
            book = self._load()
            self._governance.authorize('feedback', {'message': message}, message)
            require(book['draft'] is not None, 'feedback', '当前无候选稿，已验收正文请用 revise 指定章号。')
            book['feedback'].append(message)
            workflow.route_repair(book, book['draft'], [{'criterion': 'language', 'severity': 'quality',
                'target_chapter': book['draft']['chapter'], 'repair_scope': 'local', 'reason': message}])
            book['revision'] += 1
            self._cancel_pending(message)
            self._save(book)
            self.repo.record('feedback', {'message': message})
        return self.status()

    def replan(self, first, reason, owner=None):
        require(type(first) is int and first > 0 and text(reason), 'replan', '重规划须有章号和原因。')
        with self.repo.transaction():
            self.controller_guard(owner)
            book = self._load()
            self._governance.authorize('replan', {'first': first, 'revision': book['revision']}, reason)
            rows = self.repo.headers(book['branch'])
            require((not rows or first > rows[-1]['n']) and book['draft'] is None, 'plan_guard', '已有正文或草稿的计划不能直接删除；先走修订。')
            book['plans'] = {n: p for n, p in book['plans'].items() if int(n) < first}
            book['chapter_outlines'] = {volume: [r for r in rows_ if r['chapter'] < first]
                                        for volume, rows_ in (book.get('chapter_outlines') or {}).items()}
            book['revision'] += 1
            book['feedback'].append(reason)
            self._cancel_pending(reason)
            self._save(book)
        return self.status()

    def recall(self, task_id, chapter=None, full_state=False, kind=None, key=None, limit=5, before=None):
        task = self.repo.task(task_id)
        self._live(task, verify=False)
        if task['input']['stage'] not in CONTROLLER_STAGES:
            self._worker_actor(task, (self.repo.get(store_keys.claim(task_id)) or {}).get('session'))
        if full_state:
            return self.read(task_id, 'complete_state')
        require(before is None or type(before) is int and before > 0, 'recall', 'before 须为正整数章号。')
        work = task['input']
        require('history_source' in work['records'], 'recall', '任务缺少冻结历史目录，须按当前协议重新派工。')
        snapshot = self.repo.read_document(work['records']['history_source'])
        if kind:
            require(kind in ('entity', 'node', 'topic', 'thread') and text(key) and type(limit) is int and 1 <= limit <= 20,
                    'recall', '记忆检索需要有效类型、ID 和 1～20 条范围。')
            require(work.get('narrative_tracking'), 'recall', '该冻结任务未启用叙事记忆检索；按 chapter 补读。')
            matches, chapters, more = [], [], False
            for _, page in self.repo.history_pages(snapshot, before):
                found = [r for r in self.repo.memory_rows(page) if
                         (key in r['entities'] if kind == 'entity' else
                          r.get(kind) == key or kind == 'topic' and key in r.get('topics', []))]
                if not found:
                    continue
                if len(chapters) == limit:
                    more = True
                    break
                chapters.append(page['n'])
                matches.extend(found)
            return self._observe_read(task_id, ['recall:' + kind],
                    {'kind': kind, 'key': key, 'matches': matches,
                     'more_before': chapters[-1] if more else None,
                     'recover': '按 matches 的 chapter 使用 recall --chapter N 完整补读；more_before 可用于下一页 --before N。'})
        require(type(chapter) is int and 1 <= chapter <= snapshot['through'], 'recall', '历史章不在本任务冻结目录中。')
        page = next(p for _, p in self.repo.history_pages(snapshot) if p['n'] == chapter)
        return self._observe_read(task_id, ['recall:chapter'],
                {'chapter': chapter, 'hash': page['prose'], 'prose': self.repo.read_document(page['prose']), 'summary': page['summary']})

    def revision_impact(self, first, changes=None, through=None):
        self.content_guard()
        return self._revisions.analyze(self._load(), first, changes, through)

    def revise(self, first, reason, owner=None, through=None, changes=None, proposal_hash=None, source=''):
        require(type(first) is int and first >= 1 and text(reason), 'revision', '修订需要章号和明确原因。')
        require(through is None or type(through) is int and through >= first, 'revision', '修订终点须为不小于起章的整数。')
        with self.repo.transaction():
            self.controller_guard(owner)
            book = self._load()
            self._governance.authorize('revise', {'first': first, 'through': through, 'changes': changes,
                                                 'proposal_hash': proposal_hash, 'revision': book['revision']}, source or reason)
            proposal = book.get('revision_directive') or {}
            require(bool(proposal_hash) == bool(source), 'author_source', '采纳超范围方案须同时提供 proposal_hash 和作者原话 source。')
            if proposal_hash:
                require(proposal.get('blocked') and proposal.get('plan_hash') == proposal_hash and text(source),
                        'revision_proposal', '作者授权须绑定当前修复方案的准确 plan_hash。')
                require(first == proposal['first'] and (through is None or through == proposal['impact']['last'])
                        and (changes is None or changes == proposal['changes']), 'revision_proposal', '不能借方案授权改动其他范围或变更内容。')
                impact = self._revisions.analyze(book, first, proposal['changes'], proposal['through'])
                require(impact == proposal['impact'] and proposal['branch'] == book['branch']
                        and proposal['context_hash'] == self._revisions.context_hash(book),
                        'revision_proposal', '方案来源已变化，须重新分析后绑定新方案。')
                book = self._revisions.begin(book, first, proposal['reason'], impact['last'],
                                            proposal.get('case_ids', ()), proposal['changes'], impact)
                book['decisions'].append({'kind': 'revision_authorization', 'plan_hash': proposal_hash,
                                          'first': first, 'last': impact['last'], 'source': source})
                self.repo.record('revision_authorization', book['decisions'][-1])
            else:
                # Every revision goes through the impact policy first: an amendment whose blast
                # radius exceeds the automatic range is saved as a complete proposal and waits for
                # the author's own authorization (revise --proposal-hash), instead of silently
                # rewriting half the book.
                book = self._revisions.start_revision(book, {
                    'first': first, 'through': through, 'reason': reason,
                    'changes': changes if changes is not None else {'mode': 'semantic', 'changes': []},
                    'case_ids': []})
            self._save(book)
        return self.status()

    def promote(self, owner=None):
        with self.repo.transaction():
            self.controller_guard(owner)
            book = self._load()
            revision = book.get('revision_run')
            require(revision is not None, 'revision', '当前没有待采纳的修订。')
            rows = self.repo.headers(book['branch'])
            parent = self.repo.headers(revision['parent'])
            required_end = min(parent[-1]['n'] if parent else 0,
                               editorial.effective_contract(book)['volumes'][-1]['end'])
            require(self.repo.pending() is None and not book.get('revision_directive')
                    and not book.get('draft') and not book.get('author_block')
                    and not revision.get('carry') and not revision.get('outline_task')
                    and [row['n'] for row in rows] == list(range(1, (rows[-1]['n'] if rows else 0) + 1))
                    and bool(rows) and rows[-1]['n'] >= max(required_end, revision['last'])
                    and workflow.choose(book, rows) == {'action': 'revision_ready'},
                    'revision', '修订正文、后缀或作者决定尚未完成，不能采纳候选。')
            self._audit(book)
            self.repo.promote(book['branch'], revision['parent'])
            self.repo.put(store_keys.OFFICIAL_BRANCH, book['branch'])
            book.update(revision_run=None, target=revision['target'], finish=revision['finish'], revision=book['revision'] + 1)
            self._save(book)
            self.repo.record('promote', {'branch': book['branch']})
        return self.status()

    def discard(self, owner=None, source=''):
        with self.repo.transaction():
            self.controller_guard(owner)
            book = self._load()
            if book['revision_run'] is None and (book.get('revision_directive') or {}).get('blocked'):
                # An over-window proposal waits for the author's own decision; deferring it is one.
                # Dismissal never widens anything: the plan hash and the author's words go on record,
                # the directive is dropped, and a later fix must re-analyze under the current source.
                require(text(source), 'author_source', '弃置或缓修超界修复方案须提供作者原话（--source）。')
                directive = book['revision_directive']
                decision = {'kind': 'revision_deferral', 'plan_hash': directive.get('plan_hash'),
                            'first': directive.get('first'), 'last': (directive.get('impact') or {}).get('last'),
                            'source': source}
                book.setdefault('decisions', []).append(decision)
                self.repo.record('revision_deferral', {k: decision[k] for k in ('plan_hash', 'first', 'last')})
                book.pop('revision_directive', None)
                book.pop('pause_reason', None)
                book['status'] = 'running'
                self._save(book)
                self.repo.record('discard', {'kind': 'revision_deferral'})
                return self.status()
            require(book['revision_run'] is not None, 'revision', '当前没有候选修订。')
            parent = book['revision_run']['parent']
            restored = self.repo.get(store_keys.branch_book(parent))
            # Discard restores story state, never already spent editorial effort.
            for chapter, spent in (book.get('rework') or {}).items():
                prior = restored['rework'].setdefault(chapter, {'repairs': 0, 'redesigns': 0})
                for field in ('repairs', 'redesigns'):
                    prior[field] = max(prior.get(field, 0), spent.get(field, 0))
                prior['initial_used'] = prior.get('initial_used', False) or spent.get('initial_used', False)
            if book.get('repair_cases'):
                restored['repair_cases'] = copy.deepcopy(book['repair_cases'])
            # Lexical rules belong to the project, not the discarded prose candidate.
            restored['lexical_policy'] = copy.deepcopy(book['lexical_policy'])
            restored['revision'] = book['revision'] + 1
            self._cancel_pending('discard revision')
            self._save(restored)
            self.repo.record('discard', {'branch': book['branch'], 'restored': parent})
        return self.status()

    @staticmethod
    def _contract_base(book, opening=False):
        """The contract a re-contract or its patch builds on."""
        pending = (book.get('pending_contract') or {}).get('data')
        if isinstance(pending, dict):
            return pending
        return None if opening else book.get('contract')

    # Contract fields whose change is a parameter adjustment, not a structural direction
    # change: they alter how the engine enforces the contract but don't affect any story
    # decision. Amending only these fields applies in-place without a rewrite branch.
    PARAMETER_AMENDABLE = frozenset({
        'chapter_min', 'chapter_max', 'chapter_aim',
        'style_guard', 'style_profile', 'revision_limit', 'narrative_tracking',
        'editorial_features', 'scope_append_limit', 'word_range',
    })

    def recontract(self, contract, source, owner=None, opening=False, patch=False):
        require(text(source), 'author_source', '改约须保存作者要求原话。')
        if patch:
            # A re-contract usually amends one clause of a candidate that has already been
            # reviewed. Hand-copying 40 unchanged fields to change one sentence is how a stray
            # duplicate gets in: the patch names only the fields the author is changing.
            with self.repo.transaction():
                book = self._load()
                base = self._contract_base(book, opening)
                require(isinstance(base, dict), 'contract', '没有可打补丁的底稿；首次约定请交完整候选。')
                unknown = sorted(set(contract) - set(base))
                require(not unknown, 'contract', '补丁含底稿里没有的字段。', {'unknown_fields': unknown})
                contract = {**base, **contract}
        candidate = planning.validate_contract(contract)
        facts.seed(candidate)
        with self.repo.transaction():
            self.controller_guard(owner)
            book = self._load()
            require(book['contract'] is None or not opening, 'creation', '已有生效约定，请用 recontract 改约。')
            self._governance.authorize('recontract', {'contract_hash': digest(candidate), 'opening': opening}, source)
            require(not editorial.enabled(book) or candidate['editorial_features'], 'editorial_protocol', '已启用编辑能力的项目不能改约降级以绕过根问题或关闭验收。')
            require(book['revision_run'] is None, 'revision', '先处置当前修订再改约。')
            if opening:
                state = book.get('creation')
                pending = self.repo.pending()
                # A complete candidate may be imported only while the guided opening is pristine:
                # nothing answered, nothing on display, and no gate task handed to a writer yet.
                # Dispatching the first gate task is what puts options in front of the author, so a
                # pending gate task means choices are already on their way and are not ours to drop.
                pristine = state is None or state['phase'] == 'ready' or (
                    state['phase'] == 'choosing' and not state['selections'] and state['board'] is None
                    and state['cursor'] == 0 and pending is None)
                require(pristine, 'creation',
                        '开书选择已开始，不能再用 opening --file 覆盖；完整约定请用 recontract --file。',
                        {'recover': '逐门开书按 advance/choose 继续；已答过门或已有约定时用 recontract。'})
                if state is not None and state['phase'] == 'choosing':
                    # The imported contract replaces the guided flow; leaving `creation` behind would
                    # keep dispatching gate tasks for a book that already has its contract.
                    book['creation'] = None
            planning.check_contract_names(candidate, planning.policy_of(book))
            # A re-contract usually changes one or two fields of an already reviewed candidate.
            # Handing the reviewer the delta is what lets it check the amendment instead of
            # re-reading 40 unchanged fields (and it cannot quietly become a second amendment).
            base = self._contract_base(book, opening)
            amendment = {}
            if isinstance(base, dict):
                for key in sorted(set(base) | set(candidate)):
                    before, after = base.get(key), candidate.get(key)
                    if before != after:
                        amendment[key] = {'before': _amendment_side(before), 'after': _amendment_side(after)}
            # A parameter-only amendment (word bounds, guard mode, limits) takes effect
            # immediately on the current book: it changes enforcement, not any story
            # decision, so existing chapters and outlines stay valid. A structural change
            # (premise, protagonist, world, etc.) still goes through the staged
            # pending_contract path that rewrites from chapter 1.
            if (isinstance(base, dict) and amendment
                    and set(amendment) <= self.PARAMETER_AMENDABLE
                    and book.get('contract') is not None and not opening):
                book['contract'] = candidate
                book['contract_source'] = {'amendment': amendment, 'source': source}
                self._save(book)
                self.repo.record('recontract_parameter', {'hash': digest(candidate), 'source': source,
                                                          'fields': sorted(amendment)})
                return {'staged': True, 'applied_in_place': True, 'amended_fields': sorted(amendment),
                        'contract_hash': digest(candidate)}
            self.repo.put(store_keys.AMENDMENT_BASE, book)
            self._cancel_pending(source)
            # The author's new contract supersedes an out-of-range repair plan; case budgets stay.
            book.pop('revision_directive', None)
            producer = book.get('controller_owner') or owner or 'controller'
            book.pop('pause_reason', None)
            if book.get('world') and book.get('creation'):
                # The world is the reading the contract has to agree with; v2 checks that here
                # instead of paying a contract reviewer to do it after the fact.
                creation.validate_contract(candidate, book['creation'], book['world'])
            book.update(status='running', revision=book['revision'] + 1,
                        pending_contract={'scope': 'contract', 'chapter': 1, 'data': candidate,
                                          'producer': producer, 'source': source, 'amendment': amendment})
            if owner:
                book['controller_owner'] = owner
            self._save(book)
            self.repo.record('recontract_candidate', {'hash': digest(candidate), 'source': source, 'producer': producer})
        return {'staged': True, 'contract_hash': digest(candidate)}

    def replay(self, branch, contract, through=None):
        return self._verification.replay(branch, contract, through)

    def _audit(self, book):
        return {**self._verification.audit(book), 'assurance': self._governance.describe(),
                'continuity_review': self._continuity_coverage(book)}

    def _continuity_coverage(self, book, rows=None):
        rows = self.repo.headers(book['branch']) if rows is None else rows
        reports = [(row['n'], self.repo.read_document(row['review']).get('continuity')) for row in rows]
        reviewed = [n for n, report in reports if report]
        return {'reviewed_chapters': reviewed, 'unreviewed_chapters': [row['n'] for row in rows if row['n'] not in reviewed],
                'host_verified_chapters': [n for n, report in reports if report and report['provenance'].get('verified')],
                'accepted_uncertainty_chapters': [n for n, report in reports if report and report.get('resolution')],
                'scope': 'declared_independent_report', 'literary_quality': 'editorial_judgment_not_certified'}

    def audit(self):
        self.content_guard()
        book = self.repo.load()
        if book['status'] == 'completed':
            frozen = self._verification.snapshot(book.get('completion_snapshot'))
            self._governance.check({**frozen['book'], 'completion_snapshot': book['completion_snapshot']})
            return {**self._verification.completion(frozen['book'], frozen['chapters']),
                    'assurance': self._governance.describe(),
                    'continuity_review': self._continuity_coverage(frozen['book'], frozen['chapters'])}
        report = self._audit(book)
        self._governance.check(book)
        return report

    def prune(self, owner=None):
        """Reclaim immutable documents no live record can reach; the story is untouched."""
        self.controller_guard(owner)
        return self.repo.prune()

    def complete(self, owner=None):
        with self.repo.transaction():
            self.controller_guard(owner)
            book = self._load()
            if book['status'] == 'completed':
                return {'completed': True, 'idempotent': True, 'snapshot_hash': book['completion_snapshot'],
                        **self._verification.scope()}
            require(self.repo.pending() is None and workflow.choose(book, self.repo.headers(book['branch'])) == {'action': 'ready_to_complete'},
                    'completion', '目标章数、章纲覆盖或承诺交代尚未完成，不能完本。')
            report = self._verification.completion(book)
            report.update(assurance=self._governance.describe(), continuity_review=self._continuity_coverage(book))
            book['completed_at'] = self.clock()
            book['status'] = 'completed'
            snapshot = self.repo.document({'contract': book['contract'], 'book': book, 'branch': book['branch'],
                                          'chapters': self.repo.headers(book['branch']), 'audit': report})
            book['completion_snapshot'] = snapshot
            self._save(book)
            self.repo.record('complete', report)
        return {'completed': True, 'snapshot_hash': snapshot, **report}

    def record_delivery(self, manifest):
        """Record an adapter's completed export against the exact completed snapshot."""
        require(isinstance(manifest, dict), 'delivery', '交付清单须为对象。')
        with self.repo.transaction():
            book = self._load()
            reference = book.get('completion_snapshot')
            require(book['status'] == 'completed' and reference
                    and manifest.get('snapshot_hash') == reference, 'completion', '交付清单须绑定当前完本快照。')
            snapshot = self._verification.snapshot(reference)
            expected = [{'chapter': row['n'], 'prose_hash': row['prose']} for row in snapshot['chapters']]
            require(manifest.get('chapters') == expected, 'delivery', '交付章节与完本快照不一致。')
            files = manifest.get('files')
            require(isinstance(files, list) and files and all(isinstance(row, dict)
                    and text(row.get('path')) and text(row.get('content_hash')) for row in files),
                    'delivery', '交付清单须包含文件位置和内容哈希。')
            value = {key: manifest[key] for key in ('snapshot_hash', 'chapters', 'files')}
            self.repo.put(store_keys.COMPLETION_DELIVERY, value)
            self.repo.record('deliver', {'snapshot_hash': reference})
        return {'recorded': True, 'snapshot_hash': reference}

    def patch(self, task_id, old, new, start=None):
        task = self.repo.task(task_id)
        book = self._live(task)
        self._worker_actor(task, (self.repo.get(store_keys.claim(task_id)) or {}).get('session'))
        require(task['input']['stage'] in ('repair', 'redesign') and task['input'].get('capabilities', {}).get('editorial'),
                'patch', '仅本任务声明的返修或重设计可定位补丁。')
        return craft.patch_at(book['draft']['prose'], old, new, start)
