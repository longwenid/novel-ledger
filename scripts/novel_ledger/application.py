"""Application use cases over explicit persistence, compilation and delivery ports."""
from __future__ import annotations

import copy
from .contracts import (AUTHOR_CHANNEL_STAGES, CONTROLLER_STAGES, POLICY_FIELDS, REPAIRS, RESULT, SCALE_TIERS, VERSION,
                        checks_for, digest, dump, han_count, require, text)
from . import book_state, creation, facts, narrative, planning, quality, workflow, world, craft, editorial, store_keys, story_memory, understanding, lint
from .ports import Presentation, Repository, TaskCompiler
from .revision_service import RevisionService
from .contract_activation import ContractActivation

# An amendment preview is a JSON-encoded value, not prose: if it is cut, it says so, because a
# silently truncated preview reads as a valid value and would let a reviewer (or a script) compare
# against something the author never wrote.
AMENDMENT_PREVIEW_LIMIT = 4000


def _amendment_side(value, limit=AMENDMENT_PREVIEW_LIMIT):
    rendered = dump(value)
    return rendered if len(rendered) <= limit else rendered[:limit] + '…truncated'


class Application:
    def __init__(self, repo: Repository, *, compile_task: TaskCompiler, presentation: Presentation, clock, new_id):
        self.repo = repo
        self.compile_task = compile_task
        self.presentation = presentation
        self.clock = clock
        self.new_id = new_id
        self._revisions = RevisionService(repo, cancel_pending=self._cancel_pending)
        self._contracts = ContractActivation(repo)

    def status(self):
        book = self.repo.load()
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
        sealed = task and task['input']['blind'] and task['first_read'] is None
        revision = book['revision_run']
        return {'version': VERSION, 'status': book['status'], 'branch': book['branch'], 'formal_branch': official,
                'accepted_chapters': rows[-1]['n'] if rows else 0, 'formal_chapters': formal[-1]['n'] if formal else 0,
                'candidate_chapter': book['draft']['chapter'] if book['draft'] else None,
                'target': book['target'], 'written_han': book['written_han'], 'finish': book['finish'],
                'pending_task': task['id'] if task else None, 'stage': task['input']['stage'] if task else None,
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
                'action_counts': {name: sum(a['action'] == name for a in actions) for name in ('keep', 'review', 'local', 'rewrite')},
                'plan_path': self.presentation.revision_path(plan['plan_hash'])}

    def task_status(self, task_id):
        task = self.repo.task(task_id)
        return {key: task[key] for key in ('id', 'status', 'reviewer')}

    def authorize_worker(self, task_id, session, claim=None):
        task = self.repo.task(task_id)
        self._live(task)
        self._session(task, session, claim)

    def _cancel_pending(self, reason):
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
        task = self.repo.pending()
        require(not task or not task['input']['blind'] or task['first_read'] is not None,
                'first_read_sealed', '首读冻结前只能读取本任务正文。')

    def _live(self, task):
        book = self.repo.load()
        require(task['status'] == 'pending' and task['input']['branch'] == book['branch']
                and task['input']['revision'] == book['revision'], 'stale_task', '任务已失效，恢复当前任务；不可改身份重投旧结果。')
        return book

    def _session(self, task, session, claim=None, check_lease=True):
        require(text(session), 'session', '须提供真实宿主会话身份 session。')
        require(claim is None or isinstance(claim, str), 'execution_claim',
                'execution_claim 须为 claim 命令返回的 token 裸字符串，不能是对象。',
                {'expect': '回执顶层 "execution_claim": "<token>"；token 来自 claim --task <ID> --session <会话> 的返回。'})
        owner = self.repo.session_task(session)
        require(owner is None or owner == task['id'], 'session_reuse', '新任务须由新 Worker 执行，不得复用其他任务会话。')
        lease = self.repo.get(store_keys.claim(task['id']))
        if lease and check_lease:
            require(lease['session'] == session and lease['token'] == claim and lease['until'] > self.clock(),
                    'worker_lease', 'Worker 租约或执行认领已过期。',
                    {'lease_session': lease['session'], 'expired': lease['until'] <= self.clock(),
                     'recover': '先执行 claim --task ' + task['id'] + ' --session <你的会话> 取得新 token，'
                                '再在回执顶层 execution_claim 填该 token（裸字符串）后重新提交；回执内容本身不用改。'})

    def _sources(self, work):
        refs = work['prose']
        if work.get('payload', {}).get('review_tree') and work['stage'] == 'scope_synthesis':
            refs = self.repo.read_document(work['records']['scope_catalog'])
        return {ref['chapter']: self.repo.read_document(ref['hash']) for ref in refs}

    def _lint_draft(self, book, chapter):
        """Mechanical prose defects of a fresh candidate, against the nearest committed chapters."""
        rows = [row for row in self.repo.headers(book['branch']) if row['n'] != chapter]
        rows.sort(key=lambda row: abs(row['n'] - chapter))
        priors = [(row['n'], self.repo.read_document(row['prose']))
                  for row in rows[:lint.DUPLICATE_WINDOW]]
        findings = lint.draft_findings(book['draft']['prose'], priors, chapter)
        if findings:
            workflow.route_repair(book, book['draft'], findings)

    def _baseline(self, book, task=None):
        """A read-only projection of what stands right now, so a dispatcher never hand-summarizes
        the ledger: resource balances, open hooks, the clock, and the live candidate."""
        state = (self.repo.read_document(task['input']['records']['state']) if task else book['state'])
        return {'clock': state['clock'], 'resources': dict(sorted(state['resources'].items())),
                'open_hooks': [{'id': ident, 'due': hook['due'], 'text': hook.get('text', '')}
                               for ident, hook in sorted(state['hooks'].items()) if hook['status'] == 'open'],
                'candidate': {'chapter': book['draft']['chapter'], 'stage': book['draft']['stage']} if book['draft'] else None}

    def advance(self, after=None, owner=None, compact=False):
        boundary = None
        refresh_world = False
        with self.repo.transaction():
            self.controller_guard(owner)
            book = self.repo.load()
            if after:
                prior = self.repo.task(after)
                if prior['status'] == 'pending':
                    return {'action': 'wait_for_submit', 'task_id': after}
                if prior['status'] != 'done' or book.get('last_task') != after:
                    return {'action': 'resync', 'status': self.status()}
            task = self.repo.pending()
            if book['status'] != 'running' and not (book['status'] == 'preparing' and book.get('creation')):
                proposal = self._revision_summary(book)
                if proposal:
                    self.repo.after_commit(lambda: self.presentation.revision(book['revision_directive']))
                    return {'action': 'revision_blocked', 'proposal': proposal, 'status': self.status()}
                return {'action': book['status'], 'status': self.status()}
            if not task:
                choice = workflow.choose(book, self.repo.headers(book['branch']))
                if isinstance(choice, dict) and choice['action'] == 'contract_ready':
                    book = self._contracts.activate(book)
                    refresh_world = bool(book.get('world'))
                    choice = workflow.choose(book, self.repo.headers(book['branch']))
                if isinstance(choice, dict):
                    if choice['action'] == 'repair_exhausted':
                        book.update(status='paused', pause_reason='原修复额度已经耗尽，改约不重新发初稿额度。')
                        self.repo.save(book)
                    if choice['action'] not in ('world_ready', 'outline_ready'):
                        boundary = {**choice, 'status': self.status()}
                        if choice['action'] != 'await_choice':
                            return boundary
                        # A board on display falls through: the author-facing card is
                        # materialized below, outside the transaction.
                    else:
                        boundary = {**choice, 'status': self.status()}
                else:
                    task = self.repo.add_task(self.compile_task(book, choice))
                    self.repo.record('dispatch', {'task': task['id'], 'stage': choice.stage})
        view = {}
        # The world view belongs to boundaries that hand a world over (or a refresh after
        # contract activation); a choice board must not drag an unverified world into the return.
        if refresh_world or boundary and boundary.get('action') in ('world_ready', 'outline_ready'):
            try:
                view['world_view'] = self.presentation.world()
            except OSError as exc:
                view['world_view_error'] = str(exc)
        if boundary and boundary.get('action') == 'await_choice' and boundary.get('board') is not None:
            # The controller hands work/board.md to the author instead of re-rendering the JSON
            # return; GBK consoles garble long UTF-8 stdout, and a live run hand-wrote this card
            # for every gate before the engine owned it.
            try:
                boundary['board_card'] = self.presentation.board(boundary['board'])
            except OSError as exc:
                boundary['board_card_error'] = str(exc)
        if boundary:
            return {**boundary, **view}
        return {'action': 'task_ready', 'task': self.presentation.task(task, self._baseline(book, task), compact=compact), 'status': self.status(), **view}

    def read(self, task_id, record=None, everything=False):
        task = self.repo.task(task_id)
        self._live(task)
        work = task['input']
        require(not work['blind'] or task['first_read'] is not None, 'first_read_sealed', '先阅读冻结正文并提交首读，再读取正式资料。')
        already = [] if (record or everything) else [n for n in self.repo.read_names(task_id) if n in work['records']]
        names = [record] if record else [n for n in work['required'] if n not in already]
        virtual = record in ('historical_index', 'memory_index') and 'history_source' in work['records']
        require(virtual or all(n in work['records'] for n in names), 'record', '资料不在当前冻结任务目录中。')
        if virtual:
            require(record != 'memory_index' or work.get('narrative_tracking'), 'recall', '当前约定未启用叙事记忆检索。')
            snapshot = self.repo.read_document(work['records']['history_source'])
            pages = [p for _, p in self.repo.history_pages(snapshot)]
            value = ([{'chapter': p['n'], 'prose_hash': p['prose'], 'summary': p['summary']} for p in reversed(pages)]
                     if record == 'historical_index' else [r for p in reversed(pages) for r in self.repo.memory_rows(p)])
            records = {record: {'hash': digest(value), 'source_hash': work['records']['history_source'], 'value': value}}
        else:
            records = {n: {'hash': work['records'][n], 'value': self.repo.read_document(work['records'][n])} for n in names}
        result = {'task_id': task_id, 'input_hash': task['input_hash'], 'complete_records': True,
                  'stage': work['stage'], 'chapter': work['chapter'],
                  'records': records,
                  'on_demand': {n: h for n, h in work['records'].items() if n not in names}}
        if not record:
            # A worker reads the envelope it already holds, so a second full read of the same task
            # used to re-deliver every required record: a real design run spent more characters
            # re-sending records than on every envelope and receipt together. The journal already
            # knows what this task was handed, so a plain read returns what is still new, and the
            # records that were skipped are named rather than silently dropped.
            result.update({'first_read': task['first_read']})
            if already:
                result['already_read'] = already
                result['already_read_note'] = ('这些记录此前已交给本任务；需要原文时用 read --record 名称重取，'
                                               '或用 read --all 取回全部必读记录。')
        return self._observe_read(task_id, names, result)

    def _observe_read(self, task_id, names, result):
        """Count actual supplemental output, including recall; this is not billed usage."""
        with self.repo.transaction():
            self.repo.record('read', store_keys.read_record(task_id, names, len(dump(result))))
        return result

    def seal(self, result):
        require(isinstance(result, dict), 'first_read', '首读回执须为对象。')
        with self.repo.transaction():
            task = self.repo.task(result.get('task_id'))
            self._live(task)
            require(task['input']['blind'], 'first_read', '此任务没有首读阶段。')
            require(result.get('input_hash') == task['input_hash'], 'input_version', '首读输入版本不匹配。')
            self._session(task, result.get('session'), result.get('execution_claim'))
            first = quality.first_read(result.get('data'), self._sources(task['input']))
            if task['first_read'] is not None:
                require(task['first_read_hash'] == digest(first) and task['reviewer'] == result['session'], 'first_read_frozen', '首读已冻结，不可改写或换人。')
            else:
                self.repo.seal(task['id'], result['session'], first)
                self.repo.bind_session(result['session'], task['id'])
                self.repo.record('first_read', {'task': task['id'], 'hash': digest(first)})
            task = self.repo.task(task['id'])
        return {'sealed': True, 'task': self.presentation.task(task)}

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
        with self.repo.transaction(preview=preview):
            task = self.repo.task(result.get('task_id'))
            if task['status'] == 'done':
                require(task['result_hash'] == digest(result), 'replay_conflict', '同一任务不能提交不同内容。')
                return {'valid': True, 'accepted': not preview, 'checked': preview, 'committed': not preview,
                        'idempotent': True, 'task_id': task['id'], 'worker_boundary': 'finished'}
            book = self._live(task)
            require(book['status'] == 'running' or (book['status'] == 'preparing' and task['input']['stage'] == 'opening_options'),
                    'paused', '项目暂停，保留回执并由主控恢复。')
            require(result.get('input_hash') == task['input_hash'], 'input_version', '输入版本不匹配。')
            self._session(task, result.get('session'), result.get('execution_claim'))
            work = copy.deepcopy(task['input'])
            if work['blind']:
                require(task['first_read'] is not None and task['reviewer'] == result['session'], 'first_read', '先冻结首读，并由原审稿者继续完整核验。')
            work['first_read'] = task['first_read']
            outcome = workflow.apply(book, work, result.get('data'), result['session'], self._sources(work))
            updated = outcome.book
            if work['stage'] in ('write', 'repair', 'redesign') and updated.get('draft') \
                    and updated['draft'].get('stage') == 'chapter_review':
                # Mechanical prose defects are judged here, before the first reviewer is paid for
                # them; preflight runs the same code in preview, so the producer sees the finding
                # without spending a review round. Same routing as the length band.
                self._lint_draft(updated, work['chapter'])
            updated['last_task'] = task['id']
            if outcome.chapter:
                row = copy.deepcopy(outcome.chapter)
                for field in ('prose', 'events', 'plan', 'review'):
                    row[field] = self.repo.document(row[field])
                previous = self.repo.headers(book['branch'])
                require(row['n'] == (previous[-1]['n'] + 1 if previous else 1), 'chapter_order', '正式章节只能顺序提交。')
                row['chain'] = facts.chain(previous[-1]['chain'] if previous else 'genesis', row, digest(book['contract']))
                self.repo.add_chapter(book['branch'], row)
            if work['stage'] not in CONTROLLER_STAGES:
                # Session binding exists for independence: reviews must not be written by their
                # producers and first reads must stay with their reader. An opening gate has no
                # prose, no blind phase and no independence requirement, and the inline choice
                # chain (the controller executing its own gates) is the cheap, fast path a real
                # run needed — one subagent per gate bought nothing here.
                self.repo.bind_session(result['session'], task['id'])
            self.repo.finish_task(task['id'], result)
            revision = updated.get('revision_run')
            if revision and ((outcome.chapter and revision['last'] <= outcome.chapter['n']
                              and (revision.get('carry') or revision.get('impact')))
                             or work['stage'] == 'revision_review' and revision.get('reading_approved')
                             or work['stage'] == 'alignment_review' and not updated.get('alignment_hold')
                                and revision.get('reading_task')
                             or work['stage'] == 'plan' and revision.get('plan_task')):
                if work['stage'] == 'plan':
                    revision.pop('plan_task', None)
                self._revisions.carry_suffix(updated, revision)
            if outcome.chapter or work['stage'] == 'revision_review':
                self._revisions.refresh_understanding(updated)
            if updated.get('revision_directive'):
                directive = updated['revision_directive']
                updated = self._revisions.start_review(updated, directive)
            self.repo.save(updated)
            self.repo.record('submit', {'task': task['id'], 'stage': work['stage'], 'committed_chapter': outcome.chapter is not None})
            response = {'valid': True, 'accepted': not preview, 'checked': preview, 'committed': not preview,
                        'task_id': task['id'], 'worker_boundary': 'finished',
                        'committed_chapter': outcome.chapter['n'] if outcome.chapter else None,
                        'next_stage': updated['draft']['stage'] if updated['draft'] else None,
                        'rework': updated['rework'].get(str(work['chapter'])), 'status': updated['status']}
        return response

    def claim(self, task_id, session, seconds=300):
        require(text(session) and type(seconds) is int and seconds > 0, 'claim', '认领需要会话和正整数租期。')
        with self.repo.transaction():
            task = self.repo.task(task_id)
            self._live(task)
            require(not task['reviewer'] or task['reviewer'] == session, 'first_read', '冻结首读只能沿原审稿会话恢复；另派审稿者须取消旧任务。')
            self._session(task, session, check_lease=False)
            old = self.repo.get(store_keys.claim(task_id))
            require(not old or old['until'] <= self.clock() or old['session'] == session, 'worker_busy', '另一 Worker 仍持有任务租约。')
            lease = {'session': session, 'token': old['token'] if old and old['session'] == session else self.new_id(), 'until': self.clock() + seconds}
            self.repo.put(store_keys.claim(task_id), lease)
            self.repo.bind_session(session, task_id)
            return {**lease, 'usage': '回执顶层 execution_claim 填写返回的 token 字段（裸字符串，非对象）。'}

    def release_claim(self, task_id, token):
        with self.repo.transaction():
            claim = self.repo.get(store_keys.claim(task_id))
            require(claim is not None and claim['token'] == token, 'worker_lease', '不能释放其他执行的认领。')
            self.repo.put(store_keys.claim(task_id), None)
            self.repo.record('worker_release', {'task': task_id})

    def run(self, through=None, finish=False, owner=None, seconds=300, source=''):
        require(type(seconds) is int and seconds > 0, 'lease', '租期须为正整数。')
        with self.repo.transaction():
            self.controller_guard(owner)
            book = self.repo.load()
            require(book['contract'] is not None, 'creation', '开书约定尚未激活，先完成 opening 的独立核验。')
            end = editorial.effective_contract(book)['volumes'][-1]['end']
            target = end if finish else through
            require(type(target) is int and 1 <= target <= end, 'target', '运行目标须为约定范围内的章号。')
            pending = self.repo.pending()
            require(not pending or pending['input']['chapter'] <= target, 'target', '目标不能低于已冻结任务，先 pause --cancel。')
            # A narrow revision carries its suffix automatically once its end chapter commits, so a
            # run target beyond the revision end no longer overshoots the propagation range.
            require(book['revision_run'] is None or target >= book['revision_run']['last'], 'revision_target', '运行目标不能低于修订范围，先完成或撤销修订。')
            owner = owner or self.new_id()
            self.repo.put(store_keys.CONTROLLER, {'owner': owner, 'until': self.clock() + seconds})
            book.update(target=target, finish=finish, run_authorized=True)
            book['decisions'].append({'kind': 'run', 'target': target, 'finish': finish, 'source': source})
            self.repo.save(book)
            return {'owner': owner, 'target': target, 'finish': finish, 'lease_seconds': seconds}

    def renew(self, owner, seconds=300):
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
            book = self.repo.load()
            row = self.repo.chapter(book['branch'], 1)
            require(row['prose'] == prose_hash, 'pilot_version', '认可版本与当前首章不一致。')
            book['pilot'] = {'prose': prose_hash, 'contract': digest(book['contract']), 'source': source}
            if editorial.enabled(book):
                book['style_anchor'] = {'prose_hash': prose_hash, 'sample': self.repo.read_document(row['prose']),
                                        'voice': book['contract']['voice'], 'traits': book['contract']['style_traits'], 'source': source}
            self.repo.save(book)
            self.repo.record('approve', book['pilot'])
        return {'approved': True, 'prose_hash': prose_hash}

    def opening_choice(self, option, board_hash, source, owner=None):
        with self.repo.transaction():
            self.controller_guard(owner)
            book = self.repo.load()
            require(book['contract'] is None and book.get('creation') is not None, 'opening', '当前不是逐门开书阶段。')
            book['creation'] = creation.pick(book['creation'], option, board_hash, source)
            book['revision'] += 1
            if book['creation']['phase'] == 'world':
                book['status'] = 'running'
            self.repo.document(book['creation'])
            self.repo.save(book)
            self.repo.record('opening_choice', {'option': option, 'board_hash': board_hash, 'source': source})
        return {'selected': True, 'opening': creation.view(book['creation']), 'next': 'world_model' if book['creation']['phase'] == 'world' else 'opening_options'}

    def intake(self, values, source, owner=None):
        require(isinstance(values, dict), 'intake', '部分要求须为门 ID 到 value 的映射。')
        with self.repo.transaction():
            self.controller_guard(owner)
            book = self.repo.load()
            require(book['contract'] is None and book.get('creation'), 'intake', '仅准备项目接受部分要求。')
            require(self.repo.pending() is None, 'intake', '已有任务先按当前展示选择或 back，避免覆盖冻结任务。')
            for gate, value in values.items():
                planning.enforce(planning.policy_of(book), 'opening_options', {'value': value})
            book['creation'] = creation.intake(book['creation'], values, source)
            book['revision'] += 1
            if book['creation']['phase'] == 'world':
                book['status'] = 'running'
            self.repo.document(book['creation'])
            self.repo.save(book)
            self.repo.record('intake', {'source': source, 'gates': list(values)})
        return {'opening': creation.view(book['creation'])}

    def usage(self):
        return self.repo.usage()

    def opening_tier(self, tier, source, owner=None):
        """Choose a size class by ladder position, however the window happens to be placed.

        A size class is not a creative proposal: making the author regroup and guess how many
        times to slide is an accident of the board, not a decision. The choice stays bound to a
        shown board, so this slides the ladder until the named tier is visible and picks it.
        """
        for _ in range(len(SCALE_TIERS)):
            book = self.repo.load()
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
            book = self.repo.load()
            require(book['contract'] is None and book.get('creation') is not None, 'opening', '当前不是逐门开书阶段。')
            book['creation'] = creation.regroup(book['creation'], board_hash, reason)
            book['revision'] += 1
            self.repo.document(book['creation'])
            self.repo.save(book)
            self.repo.record('opening_regroup', {'reason': reason, 'board_hash': board_hash})
        return {'next': 'opening_options', 'opening': creation.view(book['creation'])}

    def opening_back(self, gate, reason, owner=None):
        with self.repo.transaction():
            self.controller_guard(owner)
            book = self.repo.load()
            require(book['contract'] is None and book.get('creation') is not None, 'opening', '有效约定已激活时使用 recontract，不覆盖旧选择。')
            book['creation'] = creation.back(book['creation'], gate, reason)
            book.update(status='preparing', proposal=None, world=None, revision=book['revision'] + 1)
            book.pop('pending_contract', None)
            book.pop('world_review', None)
            self._cancel_pending(reason)
            self.repo.document(book['creation'])
            self.repo.save(book)
            self.repo.record('opening_back', {'gate': gate, 'reason': reason})
        return {'next': 'opening_options', 'opening': creation.view(book['creation'])}

    def pause(self, reason, cancel=False, owner=None):
        require(text(reason), 'pause', '暂停须有原因。')
        with self.repo.transaction():
            self.controller_guard(owner)
            book = self.repo.load()
            book.update(status='paused', pause_reason=reason)
            self.repo.save(book)
            if cancel:
                self._cancel_pending(reason)
            self.repo.record('pause', {'reason': reason, 'cancel': cancel})
        return self.status()

    def resume(self, owner=None):
        with self.repo.transaction():
            self.controller_guard(owner)
            book = self.repo.load()
            require(book['status'] == 'paused', 'resume', '只有暂停项目可以恢复。')
            proposal = book.get('proposal')
            if proposal and proposal.get('attempts', 0) > REPAIRS:
                # The only stop left is a spent repair budget. Resume may not reset it, but a bare
                # refusal leaves the author nowhere to go: the role of resume here is to hand the
                # decision up, so the answer records what happens instead of silently continuing.
                workflow.hold_for_exhaustion(book, proposal, {'findings': proposal.get('findings') or []},
                                              workflow.stage_for_proposal(proposal))
                self.repo.save(book)
                return self.status()
            draft = book.get('draft')
            if draft and draft.get('stage') == 'exhausted':
                # Same dead end one level down: a single chapter that used its repair rounds.
                workflow.hold_for_draft_exhaustion(book)
                self.repo.save(book)
                return self.status()
            # Third shape: a revision whose own closure review flagged a chapter outside its range.
            # Starting a second run is impossible while the first is open and finishing the first is
            # impossible with the finding outstanding, so the author decides how it closes.
            if book.get('scope_findings') and book.get('revision_run'):
                workflow.hold_for_scope_findings(book, quality.repairable(book['scope_findings']) or book['scope_findings'])
                self.repo.save(book)
                return self.status()
            require(not self._revision_summary(book), 'revision_bounds', '先处理超出自动回改范围的修复方案，resume 不扩大授权。',
                    self._revision_summary(book))
            require(not book['draft'] or book['draft']['stage'] != 'exhausted', 'repair_budget', '修复额度已耗尽，恢复不增加额度；作者需明确处置当前方案。')
            require(not book['proposal'] or book['proposal'].get('attempts', 0) <= 2, 'repair_budget', '设计返修额度已耗尽。')
            require(not quality.repairable(book.get('scope_findings')), 'scope_fix', '先按跨章核验缺陷开启修订。')
            require(not book.get('author_block'), 'author_decision', '原作者裁决尚未回答，不能通过 resume 绕过。')
            require(not book.get('remedy_exhausted'), 'remedy_exhausted', '根问题最后一轮失败，不能 resume 重发。')
            require(not book.get('alignment_hold') or book['alignment_hold'].get('attempts', 0) < 2, 'remedy_exhausted', '同一改案额度已耗尽。')
            book['status'] = 'running'
            # The stop is over; leaving its reason on the book makes status read as paused to every
            # consumer that looks at pause_reason first.
            book.pop('pause_reason', None)
            self.repo.save(book)
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
            book = self.repo.load()
            block = book.get('author_block')
            require(isinstance(block, dict), 'author_decision', '当前没有待作者裁决的问题。')
            require(block.get('id') == decision_id, 'author_decision', '答复的问题与待决问题不一致。',
                    {'expected': block.get('id'), 'got': decision_id})
            labels = [row['label'] for row in block.get('options') or []]
            require(option in labels, 'author_decision', '答复须是已展示的选项之一；作者另有第三条路时走改约或重新提案。',
                    {'options': labels, 'got': option,
                     'recover': '把第三条路整理成完整候选后执行 recontract --file 并附作者原话，经独立核验回答本问题；'
                                '注意已有正文的改约会在新分支自第 1 章重写重审全书（父分支保留，可 discard 恢复），'
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
            if decision.startswith('scope-findings:'):
                # The run cannot grow and cannot be finished; the author closes it either way.
                if option == workflow.SCOPE_OPTIONS[0]['label']:
                    workflow.accept_scope_findings(book)
                else:
                    book.update(status='paused',
                                pause_reason='作者选择先撤销本次修订；执行 discard 后重新 advance 开一次范围更大的修订。')
            elif decision.startswith(('repair-exhausted:', 'repair-stalled:')):
                # The question was "the repair budget is spent" or "the same findings keep coming
                # back"; either way the answer decides what happens to this chapter's loop:
                # one more round, accepting the candidate with the findings kept open, or stopping
                # here so the author can redo the stage themselves.
                stage = decision.split(':', 1)[-1]
                if stage == 'chapter_repair':
                    workflow.resolve_draft_exhaustion(book, option)
                elif option == workflow.REPAIR_AGAIN:
                    workflow.allow_another_repair(book)
                elif option == workflow.ACCEPT_OPEN:
                    workflow.accept_with_findings(book, stage)
                else:
                    book.update(status='paused', pause_reason='作者选择重开本阶段或改约。')
            book['revision'] += 1
            self.repo.save(book)
            self.repo.record('author_decision', book['author_decision_history'][-1])
        answer = self.status()
        if stale:
            answer['retired_task'] = stale
            answer['retired_task_note'] = '该派工在裁决之前冻结，已作废；按当前状态重新 advance 再派 Worker。'
        return answer

    def set_lexical(self, override, source, owner=None):
        """The author's lexical rules live on the book, not inside a contract; each change is a version."""
        require(isinstance(override, dict) and set(override) <= set(POLICY_FIELDS), 'lexical_policy',
                '字面规则只接受 forbidden_terms/forbidden_name_chars。')
        require(text(source), 'author_source', '保存作者改字面规则的原话。')
        policy = planning.resolve_policy(override)
        with self.repo.transaction():
            self.controller_guard(owner)
            book = self.repo.load()
            versions = book.setdefault('lexical_policy', [])
            require(bool(versions), 'lexical_policy', '项目缺少字面规则记录。')
            require(planning.policy_of(book) != policy, 'lexical_policy', '字面规则与当前版本相同，未改动。')
            versions.append({'version': len(versions) + 1, 'policy': policy, 'source': source})
            book['revision'] += 1
            book['decisions'].append({'kind': 'lexical', 'version': len(versions), 'source': source})
            self._cancel_pending('lexical policy changed')
            self.repo.save(book)
            self.repo.record('lexical_policy', {'version': len(versions), 'source': source, 'policy': policy})
        return {'version': len(versions), 'policy': policy, 'active': True}

    def feedback(self, message, owner=None):
        require(text(message), 'feedback', '反馈须为具体作者要求。')
        with self.repo.transaction():
            self.controller_guard(owner)
            book = self.repo.load()
            require(book['draft'] is not None, 'feedback', '当前无候选稿，已验收正文请用 revise 指定章号。')
            book['feedback'].append(message)
            workflow.route_repair(book, book['draft'], [{'criterion': 'language', 'severity': 'quality',
                'target_chapter': book['draft']['chapter'], 'repair_scope': 'local', 'reason': message}])
            book['revision'] += 1
            self._cancel_pending(message)
            self.repo.save(book)
            self.repo.record('feedback', {'message': message})
        return self.status()

    def replan(self, first, reason, owner=None):
        require(type(first) is int and first > 0 and text(reason), 'replan', '重规划须有章号和原因。')
        with self.repo.transaction():
            self.controller_guard(owner)
            book = self.repo.load()
            rows = self.repo.headers(book['branch'])
            require((not rows or first > rows[-1]['n']) and book['draft'] is None, 'plan_guard', '已有正文或草稿的计划不能直接删除；先走修订。')
            book['plans'] = {n: p for n, p in book['plans'].items() if int(n) < first}
            book['revision'] += 1
            book['feedback'].append(reason)
            self._cancel_pending(reason)
            self.repo.save(book)
        return self.status()

    def recall(self, task_id, chapter=None, full_state=False, kind=None, key=None, limit=5, before=None):
        task = self.repo.task(task_id)
        self._live(task)
        require(not task['input']['blind'] or task['first_read'] is not None, 'first_read_sealed', '首读前不可补读历史资料。')
        if full_state:
            return self.read(task_id, 'complete_state')
        require(before is None or type(before) is int and before > 0, 'recall', 'before 须为正整数章号。')
        work = task['input']
        if kind:
            require(kind in ('entity', 'node', 'topic', 'thread') and text(key) and type(limit) is int and 1 <= limit <= 20,
                    'recall', '记忆检索需要有效类型、ID 和 1～20 条范围。')
            if 'history_source' in work['records']:
                require(work.get('narrative_tracking'), 'recall', '该冻结任务没有叙事记忆索引；旧项目按 chapter 补读。')
                snapshot = self.repo.read_document(work['records']['history_source'])
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
            require('memory_index' in work['records'], 'recall', '该冻结任务没有叙事记忆索引；旧项目按 chapter 补读。')
            index = self.repo.read_document(task['input']['records']['memory_index'])
            matches = [r for r in index if (before is None or r['chapter'] < before)
                       and (key in r['entities'] if kind == 'entity' else r.get(kind) == key)]
            chapters = sorted({r['chapter'] for r in matches}, reverse=True)[:limit]
            return self._observe_read(task_id, ['recall:' + kind],
                    {'kind': kind, 'key': key, 'matches': [r for r in matches if r['chapter'] in chapters],
                     'more_before': chapters[-1] if len({r['chapter'] for r in matches}) > limit else None,
                     'recover': '按 matches 的 chapter 使用 recall --chapter N 完整补读；more_before 可用于下一页 --before N。'})
        if 'history_source' in work['records']:
            snapshot = self.repo.read_document(work['records']['history_source'])
            require(type(chapter) is int and 1 <= chapter <= snapshot['through'], 'recall', '历史章不在本任务冻结目录中。')
            page = next(p for _, p in self.repo.history_pages(snapshot) if p['n'] == chapter)
            return self._observe_read(task_id, ['recall:chapter'],
                    {'chapter': chapter, 'hash': page['prose'], 'prose': self.repo.read_document(page['prose']), 'summary': page['summary']})
        catalog = self.repo.read_document(task['input']['records']['historical_index'])
        ref = next((r for r in catalog if r['chapter'] == chapter), None)
        require(ref is not None, 'recall', '历史章不在本任务冻结目录中。')
        return self._observe_read(task_id, ['recall:chapter'],
                {'chapter': chapter, 'hash': ref['prose_hash'], 'prose': self.repo.read_document(ref['prose_hash']), 'summary': ref['summary']})

    def revision_impact(self, first, changes=None, through=None):
        self.content_guard()
        return self._revisions.analyze(self.repo.load(), first, changes, through)

    def revise(self, first, reason, owner=None, through=None, changes=None, proposal_hash=None, source=''):
        require(type(first) is int and first >= 1 and text(reason), 'revision', '修订需要章号和明确原因。')
        require(through is None or type(through) is int and through >= first, 'revision', '修订终点须为不小于起章的整数。')
        with self.repo.transaction():
            self.controller_guard(owner)
            book = self.repo.load()
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
            elif book.get('scope_findings'):
                # Author-level findings were handed up through the author channel; only the rest
                # describe work a writer can actually do.
                targets = [f['target_chapter'] for f in quality.repairable(book['scope_findings'])]
                require(targets and first == min(targets) and (through is None or through >= max(targets)),
                        'revision_range', '审稿触发的修订须覆盖已记录缺陷，不得回退到无关前文。')
                directive = {'first': first, 'through': max(targets) if through is None else through,
                             'reason': proposal.get('reason', reason), 'case_ids': proposal.get('case_ids', []),
                             'changes': {'mode': 'semantic', 'changes': []} if changes is None else changes}
                book = self._revisions.start_review(book, directive)
            else:
                book = self._revisions.begin(book, first, reason, through, changes=changes)
            self.repo.save(book)
        return self.status()

    def enable_workbench(self, source, owner=None):
        require(text(source), 'author_source', '启用工作台须保存明确来源。')
        with self.repo.transaction():
            self.controller_guard(owner)
            book = self.repo.load()
            if 'understanding' in book:
                return {'enabled': True, 'already_enabled': True}
            require(self.repo.pending() is None and not book['draft'] and not book['revision_run'],
                    'workbench_boundary', '在无在途任务、草稿或修订的章节边界启用工作台，保留旧冻结任务。')
            book['understanding'] = understanding.empty()
            book['revision'] += 1
            self.repo.save(book)
            self.repo.record('workbench_enable', {'source': source})
        return {'enabled': True, 'already_enabled': False}

    def promote(self, owner=None):
        with self.repo.transaction():
            self.controller_guard(owner)
            book = self.repo.load()
            require(self.repo.pending() is None and workflow.choose(book, self.repo.headers(book['branch'])) == {'action': 'revision_ready'}, 'revision', '修订范围及独立复核尚未完成。')
            self._audit(book)
            revision = book['revision_run']
            self.repo.promote(book['branch'], revision['parent'])
            self.repo.put(store_keys.OFFICIAL_BRANCH, book['branch'])
            book.update(revision_run=None, target=revision['target'], finish=revision['finish'], revision=book['revision'] + 1)
            self.repo.save(book)
            self.repo.record('promote', {'branch': book['branch']})
        return self.status()

    def discard(self, owner=None):
        with self.repo.transaction():
            self.controller_guard(owner)
            book = self.repo.load()
            require(book['revision_run'] is not None, 'revision', '当前没有候选修订。')
            parent = book['revision_run']['parent']
            restored = self.repo.get(store_keys.branch_book(parent))
            # Discard restores story state, never already spent editorial effort.
            for chapter, spent in book['rework'].items():
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
            self.repo.save(restored)
            self.repo.record('discard', {'branch': book['branch'], 'restored': parent})
        return self.status()

    @staticmethod
    def _contract_base(book, opening=False):
        """The contract a re-contract or its patch builds on."""
        pending = (book.get('pending_contract') or {}).get('data')
        if isinstance(pending, dict):
            return pending
        proposal = book.get('proposal') or {}
        if proposal.get('scope') == 'contract' and isinstance(proposal.get('data'), dict):
            return proposal['data']
        return None if opening else book.get('contract')

    def recontract(self, contract, source, owner=None, opening=False, patch=False):
        require(text(source), 'author_source', '改约须保存作者要求原话。')
        if patch:
            # A re-contract usually amends one clause of a candidate that has already been
            # reviewed. Hand-copying 40 unchanged fields to change one sentence is how a stray
            # duplicate gets in: the patch names only the fields the author is changing.
            with self.repo.transaction():
                book = self.repo.load()
                base = self._contract_base(book, opening)
                require(isinstance(base, dict), 'contract', '没有可打补丁的底稿；首次约定请交完整候选。')
                unknown = sorted(set(contract) - set(base))
                require(not unknown, 'contract', '补丁含底稿里没有的字段。', {'unknown_fields': unknown})
                contract = {**base, **contract}
        candidate = planning.validate_contract(contract)
        facts.seed(candidate)
        with self.repo.transaction():
            self.controller_guard(owner)
            book = self.repo.load()
            require(book['contract'] is None or not opening, 'creation', '已有生效约定，请用 recontract 改约。')
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
            if not book['proposal'] or book['proposal']['scope'] != 'contract':
                self.repo.put(store_keys.AMENDMENT_BASE, book)
            self._cancel_pending(source)
            # The author's new contract supersedes these dispatches; the amendment base
            # retains them for discard, and scope findings/case budgets remain available.
            for key in ('revision_directive', 'alignment_hold', 'alignment_proposal'):
                book.pop(key, None)
            producer = book.get('controller_owner') or owner or 'controller'
            book.pop('pause_reason', None)
            book.update(status='running', revision=book['revision'] + 1,
                        proposal={'scope': 'contract', 'chapter': 1, 'data': candidate, 'producer': producer,
                                  'source': source, 'amendment': amendment})
            if owner:
                book['controller_owner'] = owner
            self.repo.save(book)
            self.repo.record('recontract_candidate', {'hash': digest(candidate), 'source': source, 'producer': producer})
        return {'staged': True, 'contract_hash': digest(candidate)}

    def replay(self, branch, contract, through=None):
        return self._revisions.replay(branch, contract, through)

    def _audit(self, book):
        require(book.get('contract') is not None, 'contract', '尚无生效约定，无法核对账本。',
                {'recover': '先完成开书约定与其独立核验。'})
        if book.get('world'):
            opening = book['creation']
            world.validate(book['world'], creation.selected(opening), opening['selection_hash'],
                           sections=world.required_sections(workflow.tier_id(opening)))
            creation.validate_contract(book['contract'], opening, book['world'])
            approval = book['world_review']
            review = quality.checks(approval['receipt'], checks_for(approval['receipt'].get('checks_version', 1), 'world'), {0: dump(book['world'])},
                                    author_channel='world_review' in AUTHOR_CHANNEL_STAGES)
            require(review['verdict'] == 'pass' and approval['reviewer'] != approval['producer'], 'world_review', '世界模型缺少独立通过核验。')
        amendment = book.get('contract_review')
        if amendment:
            require(amendment['reviewer'] != amendment['producer'], 'contract_review', '改约缺少独立核验。')
        rows = self.repo.headers(book['branch'])
        state = self.replay(book['branch'], book['contract'])
        require(digest(state) == digest(book['state']), 'projection', '当前状态投影与完整重放不一致。')
        require(sum(r['han'] for r in rows) == book['written_han'], 'projection', '汉字计数投影不一致。')
        review_before = facts.seed(book['contract'])
        accepted_plans = {}
        for row in rows:
            prose = self.repo.read_document(row['prose'])
            review = self.repo.read_document(row['review'])
            plan = self.repo.read_document(row['plan'])
            story_memory.bind(copy.deepcopy(plan), accepted_plans,
                              2 if plan.get('scene_schema') == 'scene-identity/2' else 1,
                              1 if story_memory.reading_enabled(plan) else 0)
            accepted_plans[str(row['n'])] = plan
            require(plan['chapter'] == row['n'] and review['writer'] != review['session'], 'review_independence', '章节计划或独立审稿来源不匹配。')
            quality.first_read(review['first_read'], {row['n']: prose})
            f, r = quality.chapter_review(review, {row['n']: prose}, review['obligations'],
                                          version=review.get('facts', {}).get('checks_version', 1))
            require(f['verdict'] == r['verdict'] == 'pass', 'review', '正式章节缺少两类通过审稿。')
            for reading in review.get('revision_readings', []):
                require(reading['prose_hash'] == row['prose'] and reading['chapter'] == row['n']
                        and reading['reviewer'] not in reading['prior_sessions'],
                        'review_independence', '修订阅读核验须绑定准确正文和独立会话。')
                quality.first_read(reading['first_read'], {row['n']: prose})
                receipt = reading['receipt']
                checked = quality.checks(receipt, checks_for(receipt['checks_version'], 'reader'),
                                         {row['n']: prose}, reading['obligations'], ('language',), receipt['checks_version'])
                require(checked['verdict'] == 'pass', 'review', '携带章节的修订阅读核验未通过。')
            require(book['contract']['chapter_min'] <= han_count(prose) <= book['contract']['chapter_max'] and han_count(prose) == row['han'], 'length', '正式篇幅不符合约定。')
            require(all(p in book['profiles'] for p in plan['participants']), 'profile', '正式章节人物档案缺失。')
            if book['contract'].get('narrative_tracking'):
                raw_events = self.repo.read_document(row['events'])
                realized = copy.deepcopy(plan)
                if review.get('alignment'):
                    editorial.alignment({'alignment': review['alignment']}, plan, raw_events, lambda ref: facts.evidence(ref, {row['n']: prose}), review_before)
                    if review['alignment']['action'] != 'follow_plan':
                        realized['node_actions'] = [{'node': r['node'], 'after': r['after']} for r in review['alignment']['realizations'] if r['after'] != 'not_realized']
                        realized['disclosures'] = [{'topic': e['topic'], 'after': e['after']} for e in raw_events if e['op'] == 'reader_knowledge']
                narrative.prepare_events(raw_events, realized)
            review_before, _ = facts.settle(review_before, self.repo.read_document(row['events']), prose, row['n'])
            planning.check_text(prose, planning.policy_of(book))
        if 'understanding' in book:
            require(understanding.rebase(book['understanding'], {r['n']: r['prose'] for r in rows}) == book['understanding'],
                    'understanding_source', '作品理解包含不属于当前正文版本的依据。')
        # Anything the author accepted while a reviewer was still asking for changes stays on the
        # closing record: an accepted candidate must never read as a clean pass.
        accepted = [{'stage': row['stage'], 'scope': row.get('scope'), 'findings': row['findings']}
                    for row in book.get('accepted_findings') or []]
        return {'ok': True, 'chapters': len(rows), 'state_hash': digest(state), 'written_han': book['written_han'],
                'accepted_findings': accepted,
                'accepted_findings_note': ('这些是作者在返修额度用尽后选择“接受并把意见记为未解决项”的条目；'
                                           '它们不是 pass，完本后仍以未解决状态保留。' if accepted else '')}

    def audit(self):
        self.content_guard()
        return self._audit(self.repo.load())

    def prune(self, owner=None):
        """Reclaim immutable documents no live record can reach; the story is untouched."""
        self.controller_guard(owner)
        return self.repo.prune()

    def complete(self, owner=None):
        with self.repo.transaction():
            self.controller_guard(owner)
            book = self.repo.load()
            if book['status'] == 'completed':
                return {'completed': True, 'idempotent': True}
            require(self.repo.pending() is None and workflow.choose(book, self.repo.headers(book['branch'])) == {'action': 'ready_to_complete'}, 'completion', '目标、作者定调、卷审或全书复核尚未完成。')
            report = self._audit(book)
            written = self.repo.headers(book['branch'])
            # 完本看两件事：章数写到位，且每一章都已在提交时落在章幅区间内（见章节验收）。
            # 总字数是这两者的派生结果，不再单独作为门槛。
            require(written and written[-1]['n'] == editorial.effective_contract(book)['volumes'][-1]['end'],
                    'chapter_target', '章节数未达到约定章数，不能降低目标冒充完本。')
            require(not any(h['status'] == 'open' for h in book['state']['hooks'].values()), 'payoffs', '仍有未交代承诺。')
            if book['contract'].get('narrative_tracking'):
                narrative.closure(book)
            if editorial.enabled(book):
                require(not book.get('alignment_hold') and not book.get('author_block')
                        and all(c['status'] == 'resolved' for c in book.get('repair_cases', {}).values()), 'completion', '改案、根问题或作者裁决未解决。')
                headers = self.repo.headers(book['branch'])
                for volume in editorial.effective_contract(book)['volumes']:
                    scope = 'volume:' + volume['id']
                    key = workflow.review_key(scope, volume['first'], volume['end'], headers, editorial.context_hash(book))
                    require(book.get('scope_closures', {}).get(scope, {}).get('review_key') == key, 'completion', '卷关闭记录不覆盖当前版本。')
                key = workflow.review_key('book', 1, headers[-1]['n'], headers, editorial.context_hash(book))
                require(book.get('scope_closures', {}).get('book', {}).get('review_key') == key, 'completion', '全书终审没有覆盖当前准确版本。')
            book['completed_at'] = self.clock()
            book['status'] = 'completed'
            snapshot = self.repo.document({'contract': book['contract'], 'book': book, 'branch': book['branch'],
                                          'chapters': self.repo.headers(book['branch']), 'audit': report})
            book['completion_snapshot'] = snapshot
            self.repo.save(book)
            self.repo.record('complete', report)
        return {'completed': True, 'snapshot_hash': snapshot, **report}

    def record_delivery(self, manifest):
        """Record an adapter's completed export against the exact completed snapshot."""
        require(isinstance(manifest, dict), 'delivery', '交付清单须为对象。')
        with self.repo.transaction():
            book = self.repo.load()
            reference = book.get('completion_snapshot')
            require(book['status'] == 'completed' and reference
                    and manifest.get('snapshot_hash') == reference, 'completion', '交付清单须绑定当前完本快照。')
            snapshot = self.repo.read_document(reference)
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
        require(task['input']['stage'] in ('repair', 'redesign') and task['input'].get('capabilities', {}).get('editorial'),
                'patch', '仅本任务声明的返修或重设计可定位补丁。')
        return craft.patch_at(book['draft']['prose'], old, new, start)
