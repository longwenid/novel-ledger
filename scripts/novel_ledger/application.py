"""Composition root: orchestrate domain decisions and commit them atomically."""
from __future__ import annotations

import copy
import json
import os
import sys
import time
import uuid
from pathlib import Path
from .contracts import CHECK_SETS, POLICY_FIELDS, RESULT, VERSION, Error, checks_for, digest, dump, han_count, require, text
from . import context, creation, delivery, facts, narrative, planning, quality, workflow, world, craft, editorial, bookpage


class Application:
    def __init__(self, repo, entry=None):
        self.repo = repo
        self.entry = entry or Path(__file__).resolve().parents[1] / 'novel.py'

    def status(self):
        book = self.repo.load()
        rows = self.repo.headers(book['branch'])
        official = self.repo.get('official_branch', 'main')
        formal = self.repo.headers(official)
        task = self.repo.pending()
        sealed = task and task['input']['blind'] and task['first_read'] is None
        revision = book['revision_run']
        return {'version': VERSION, 'status': book['status'], 'branch': book['branch'], 'formal_branch': official,
                'accepted_chapters': rows[-1]['n'] if rows else 0, 'formal_chapters': formal[-1]['n'] if formal else 0,
                'candidate_chapter': book['draft']['chapter'] if book['draft'] else None,
                'target': book['target'], 'written_han': book['written_han'], 'finish': book['finish'],
                'pending_task': task['id'] if task else None, 'stage': task['input']['stage'] if task else None,
                'pause_reason': None if sealed else book.get('pause_reason'),
                'opening': {'phase': book['creation']['phase'], 'selected_gates': len(book['creation']['selections']),
                            'total_gates': len(creation.gates(book['creation'])),
                            'gate': creation.current(book['creation'])['id'] if book['creation']['phase'] == 'choosing' else None}
                           if book.get('creation') else None,
                'revision_run': {k: revision[k] for k in ('parent', 'first', 'last')} if revision else None}

    def controller_guard(self, owner=None):
        run = self.repo.get('controller')
        if run and run['until'] > time.time():
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
        lease = self.repo.get('claim:' + task['id'])
        if lease and check_lease:
            require(lease['session'] == session and lease['token'] == claim and lease['until'] > time.time(),
                    'worker_lease', 'Worker 租约或执行认领已过期。',
                    {'lease_session': lease['session'], 'expired': lease['until'] <= time.time(),
                     'recover': '先执行 claim --task ' + task['id'] + ' --session <你的会话> 取得新 token，'
                                '再在回执顶层 execution_claim 填该 token（裸字符串）后重新提交；回执内容本身不用改。'})

    def _sources(self, work):
        refs = work['prose']
        if work.get('payload', {}).get('review_tree') and work['stage'] == 'scope_synthesis':
            refs = self.repo.read_document(work['records']['scope_catalog'])
        return {ref['chapter']: self.repo.read_document(ref['hash']) for ref in refs}

    def _baseline(self, book, task=None):
        """A read-only projection of what stands right now, so a dispatcher never hand-summarizes
        the ledger: resource balances, open hooks, the clock, and the live candidate."""
        state = (self.repo.read_document(task['input']['records']['state']) if task else book['state'])
        return {'clock': state['clock'], 'resources': dict(sorted(state['resources'].items())),
                'open_hooks': [{'id': ident, 'due': hook['due'], 'text': hook.get('text', '')}
                               for ident, hook in sorted(state['hooks'].items()) if hook['status'] == 'open'],
                'candidate': {'chapter': book['draft']['chapter'], 'stage': book['draft']['stage']} if book['draft'] else None}

    def advance(self, after=None, owner=None):
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
                return {'action': book['status'], 'status': self.status()}
            if not task:
                choice = workflow.choose(book, self.repo.headers(book['branch']))
                if isinstance(choice, dict) and choice['action'] == 'contract_ready':
                    book = self._activate_contract(book)
                    refresh_world = bool(book.get('world'))
                    choice = workflow.choose(book, self.repo.headers(book['branch']))
                if isinstance(choice, dict):
                    if choice['action'] == 'repair_exhausted':
                        book.update(status='paused', pause_reason='原修复额度已经耗尽，改约不重新发初稿额度。')
                        self.repo.save(book)
                    if choice['action'] not in ('world_ready', 'outline_ready'):
                        return {**choice, 'status': self.status()}
                    boundary = {**choice, 'status': self.status()}
                else:
                    task = self.repo.add_task(context.build(self.repo, book, choice))
                    self.repo.record('dispatch', {'task': task['id'], 'stage': choice.stage})
        view = {}
        if boundary or refresh_world:
            try:
                view['world_view'] = delivery.export_world(self.repo, bookpage.render)
            except OSError as exc:
                view['world_view_error'] = str(exc)
        if boundary:
            return {**boundary, **view}
        return {'action': 'task_ready', 'task': delivery.materialize(self.repo, task, self.entry, self._baseline(book, task)), 'status': self.status(), **view}

    def read(self, task_id, record=None):
        task = self.repo.task(task_id)
        self._live(task)
        work = task['input']
        require(not work['blind'] or task['first_read'] is not None, 'first_read_sealed', '先阅读冻结正文并提交首读，再读取正式资料。')
        names = [record] if record else work['required']
        virtual = record in ('historical_index', 'memory_index') and 'history_source' in work['records']
        require(virtual or all(n in work['records'] for n in names), 'record', '资料不在当前冻结任务目录中。')
        if virtual:
            require(record != 'memory_index' or work.get('narrative_tracking'), 'recall', '旧项目未启用叙事记忆检索。')
            snapshot = self.repo.read_document(work['records']['history_source'])
            pages = [p for _, p in self.repo.history_pages(snapshot)]
            value = ([{'chapter': p['n'], 'prose_hash': p['prose'], 'summary': p['summary']} for p in reversed(pages)]
                     if record == 'historical_index' else [r for p in reversed(pages) for r in self.repo.memory_rows(p)])
            records = {record: {'hash': digest(value), 'source_hash': work['records']['history_source'], 'value': value}}
        else:
            records = {n: {'hash': work['records'][n], 'value': self.repo.read_document(work['records'][n])} for n in names}
        result = {'task_id': task_id, 'input_hash': task['input_hash'], 'complete_records': True,
                **{key: work[key] for key in ('stage', 'chapter', 'scope', 'first', 'last', 'payload', 'branch', 'revision')},
                'records': records,
                'on_demand': {n: h for n, h in work['records'].items() if n not in names},
                'prose': work['prose'], 'first_read': task['first_read'], 'obligations': work['obligations'],
                'brief': work.get('brief'), 'policy': work['policy'], 'checks_version': work.get('checks_version', 1)}
        return self._observe_read(task_id, names, result)

    def _observe_read(self, task_id, names, result):
        """Count actual supplemental output, including recall; this is not billed usage."""
        with self.repo.transaction():
            self.repo.record('read', {'task': task_id, 'records': names, 'chars': len(dump(result))})
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
        return {'sealed': True, 'task': delivery.materialize(self.repo, task, self.entry)}

    def check(self, task_id=None, file=None):
        """Dry-run a candidate receipt without submitting it, and without needing its task identity.

        A worker can ask "would this be accepted, and if not which field is wrong" against the current
        pending task, so it never has to read the engine's source to learn the format. Nothing is
        committed: the task comes straight from the repository and the receipt is only previewed.
        """
        task = self.repo.task(task_id) if task_id else self.repo.pending()
        require(task is not None, 'task', '项目当前没有在途任务可供试算。',
                {'recover': '先由主控 advance 派工，再对返回的 task_id 运行 check。'})
        require(task['status'] == 'pending', 'stale_task', '该任务已结束，不能用它试算。')
        payload = json.loads(Path(file).read_text(encoding='utf-8')) if file else json.load(sys.stdin)
        require(isinstance(payload, dict), 'schema', '待检回执须为 JSON 对象。')
        require(payload.get('schema') == RESULT, 'schema', '回执缺 schema=' + RESULT + '。')
        require(payload.get('input_hash') == task['input_hash'], 'input_version', 'input_hash 与当前任务不符。',
                {'expected': task['input_hash'], 'got': payload.get('input_hash')})
        require(payload.get('task_id'), 'result', '回执缺 task_id。')
        # A candidate is often missing the session line while being drafted. Identify the caller from
        # the environment when it is there, and otherwise preview under the task's own reader; the
        # lease and session rules stay enforced for anything that actually commits.
        session = payload.get('session') or os.environ.get('NOVEL_SESSION') or task['reviewer'] or 'check-preview'
        if os.environ.get('NOVEL_SESSION'):
            require(session == os.environ['NOVEL_SESSION'], 'session', '试算身份与会话不符。')
        self._session(task, session, check_lease=False)
        preview = self.submit({**payload, 'session': session}, preview=True)
        return {'accepted': True, 'checked': True, 'session_used': session, **preview}

    def submit(self, result, preview=False):
        require(isinstance(result, dict) and result.get('schema') == RESULT, 'schema', '回执协议无效。')
        with self.repo.transaction(preview=preview):
            task = self.repo.task(result.get('task_id'))
            if task['status'] == 'done':
                require(task['result_hash'] == digest(result), 'replay_conflict', '同一任务不能提交不同内容。')
                return {'accepted': not preview, 'checked': preview, 'idempotent': True, 'task_id': task['id'],
                        'worker_boundary': 'finished'}
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
            updated['last_task'] = task['id']
            if outcome.chapter:
                row = copy.deepcopy(outcome.chapter)
                for field in ('prose', 'events', 'plan', 'review'):
                    row[field] = self.repo.document(row[field])
                previous = self.repo.headers(book['branch'])
                require(row['n'] == (previous[-1]['n'] + 1 if previous else 1), 'chapter_order', '正式章节只能顺序提交。')
                row['chain'] = facts.chain(previous[-1]['chain'] if previous else 'genesis', row, digest(book['contract']))
                self.repo.add_chapter(book['branch'], row)
            self.repo.bind_session(result['session'], task['id'])
            self.repo.finish_task(task['id'], result)
            revision = updated.get('revision_run')
            if outcome.chapter and revision and revision.get('carry') and revision['last'] == outcome.chapter['n']:
                self._carry_suffix(updated, revision)
            if updated.get('revision_directive'):
                directive = updated['revision_directive']
                updated = self._begin_revision(updated, directive['first'], directive['reason'], directive['through'], directive['case_ids'])
            self.repo.save(updated)
            self.repo.record('submit', {'task': task['id'], 'stage': work['stage'], 'committed_chapter': outcome.chapter is not None})
            response = {'accepted': not preview, 'checked': preview, 'task_id': task['id'], 'worker_boundary': 'finished',
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
            old = self.repo.get('claim:' + task_id)
            require(not old or old['until'] <= time.time() or old['session'] == session, 'worker_busy', '另一 Worker 仍持有任务租约。')
            lease = {'session': session, 'token': old['token'] if old and old['session'] == session else uuid.uuid4().hex, 'until': time.time() + seconds}
            self.repo.put('claim:' + task_id, lease)
            self.repo.bind_session(session, task_id)
            return {**lease, 'usage': '回执顶层 execution_claim 填写返回的 token 字段（裸字符串，非对象）。'}

    def release_claim(self, task_id, token):
        with self.repo.transaction():
            claim = self.repo.get('claim:' + task_id)
            require(claim is not None and claim['token'] == token, 'worker_lease', '不能释放其他执行的认领。')
            self.repo.put('claim:' + task_id, None)
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
            owner = owner or uuid.uuid4().hex
            self.repo.put('controller', {'owner': owner, 'until': time.time() + seconds})
            book.update(target=target, finish=finish, run_authorized=True)
            book['decisions'].append({'kind': 'run', 'target': target, 'finish': finish, 'source': source})
            self.repo.save(book)
            return {'owner': owner, 'target': target, 'finish': finish, 'lease_seconds': seconds}

    def renew(self, owner, seconds=300):
        require(type(seconds) is int and seconds > 0, 'lease', '租期须为正整数。')
        with self.repo.transaction():
            run = self.repo.get('controller')
            require(run is not None and run['owner'] == owner and run['until'] > time.time(), 'controller_lease', '主控租约已失效。')
            run['until'] = time.time() + seconds
            self.repo.put('controller', run)
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
            self.repo.cancel_pending(reason)
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
                self.repo.cancel_pending(reason)
            self.repo.record('pause', {'reason': reason, 'cancel': cancel})
        return self.status()

    def resume(self, owner=None):
        with self.repo.transaction():
            self.controller_guard(owner)
            book = self.repo.load()
            require(book['status'] == 'paused', 'resume', '只有暂停项目可以恢复。')
            require(not book['draft'] or book['draft']['stage'] != 'exhausted', 'repair_budget', '修复额度已耗尽，恢复不增加额度；作者需明确处置当前方案。')
            require(not book['proposal'] or book['proposal'].get('attempts', 0) <= 2, 'repair_budget', '设计返修额度已耗尽。')
            require(not book.get('scope_findings'), 'scope_fix', '先按跨章核验缺陷开启修订。')
            require(not book.get('author_block'), 'author_decision', '原作者裁决尚未回答，不能通过 resume 绕过。')
            require(not book.get('remedy_exhausted'), 'remedy_exhausted', '根问题最后一轮失败，不能 resume 重发。')
            require(not book.get('alignment_hold') or book['alignment_hold'].get('attempts', 0) < 2, 'remedy_exhausted', '同一改案额度已耗尽。')
            book['status'] = 'running'
            self.repo.save(book)
        return self.status()

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
            self.repo.cancel_pending('lexical policy changed')
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
            self.repo.cancel_pending(message)
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
            self.repo.cancel_pending(reason)
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

    def replay(self, branch, contract, through=None):
        state, previous = facts.seed(contract), 'genesis'
        rows = self.repo.headers(branch)
        for row in rows:
            if through is not None and row['n'] > through:
                break
            require(row['n'] == (1 if previous == 'genesis' else number + 1), 'chain', '章节链不连续。')
            number = row['n']
            prose = self.repo.read_document(row['prose'])
            state, normalized = facts.settle(state, self.repo.read_document(row['events']), prose, number)
            require(digest(normalized) == row['events'] and digest(state) == row['state_hash'], 'state_integrity', '事实重放与提交版本不一致。')
            require(facts.chain(previous, row, digest(contract)) == row['chain'], 'chain', '章节事件链被修改。')
            previous = row['chain']
        return state

    def _carry_suffix(self, book, revision):
        """Append the chapters past a narrow revision's end, unchanged, onto the candidate branch.

        Carrying is sound only while the rewrite leaves their facts intact: each carried chapter's
        frozen events settle against the new state, and the first divergence refuses the whole carry
        so the revision must widen instead of silently deshaping the suffix.
        """
        state = book['state']
        previous = self.repo.headers(book['branch'])[-1]['chain']
        contract_hash = digest(book['contract'])
        for row in revision['carry']:
            prose = self.repo.read_document(row['prose'])
            try:
                if book['contract'].get('narrative_tracking'):
                    plan = self.repo.read_document(row['plan'])
                    require(not narrative.unmet(state, plan), 'plan_preconditions', '被携带章节的实际前提已被修订改变。',
                            {'unmet': narrative.unmet(state, plan)})
                state, normalized = facts.settle(state, self.repo.read_document(row['events']), prose, row['n'])
            except Error as exc:
                raise Error('revision_carry', '修订影响了第 %d 章的事实，不能原样携带其后缀。' % row['n'],
                            {'chapter': row['n'], 'cause': exc.as_dict(),
                             'recover': '撤销本修订后用更远的终点（或全书）重开 revise，重做受影响章。'})
            carried = dict(row)
            carried['events'] = self.repo.document(normalized)
            carried['state_hash'] = digest(state)
            carried['chain'] = facts.chain(previous, carried, contract_hash)
            self.repo.add_chapter(book['branch'], carried)
            previous = carried['chain']
            book['written_han'] += carried['han']
        book['state'] = state
        revision['carry'] = []

    def _begin_revision(self, book, first, reason, through=None, case_ids=()):
        require(book['revision_run'] is None, 'revision', '先完成或撤销当前修订。')
        rows = self.repo.headers(book['branch'])
        require(rows and first <= rows[-1]['n'], 'revision', '修订起点必须已有正式正文。')
        book_last = rows[-1]['n']
        end = book_last if through is None else through
        require(type(end) is int and first <= end <= book_last, 'revision', '修订终点须在修订起点与最后一章之间。',
                {'revision_first': first, 'book_last': book_last,
                 'recover': '一词级小修用 --through 收窄到受影响章；终点之后的章节原样携带并复核接缝。'})
        parent = book['branch']
        self.repo.put('branch-book:' + parent, book)
        branch = self.repo.fork(parent, first)
        old = self.repo.chapter(parent, first)
        book.update(branch=branch, state=self.replay(parent, book['contract'], first - 1),
                    written_han=sum(r['han'] for r in rows if r['n'] < first), status='running',
                    target=book_last, finish=False, revision=book['revision'] + 1)
        book['revision_run'] = {'parent': parent, 'first': first, 'last': end, 'reason': reason,
                                'target': self.repo.get('branch-book:' + parent)['target'], 'finish': self.repo.get('branch-book:' + parent)['finish'],
                                'carry': [r for r in rows if r['n'] > end]}
        book.pop('scope_findings', None)
        draft = {'chapter': first, 'title': old['title'], 'prose': self.repo.read_document(old['prose']), 'producer': 'historical', 'history': [], 'findings': []}
        workflow.route_repair(book, draft, [{'criterion': 'change', 'severity': 'quality', 'target_chapter': first, 'repair_scope': 'chapter', 'reason': reason}])
        self.repo.cancel_pending(reason)
        self.repo.record('revision', {k: v for k, v in book['revision_run'].items() if k != 'carry'})
        book['revision_run']['case_ids'] = list(case_ids)
        book.pop('revision_directive', None)
        return book

    def revise(self, first, reason, owner=None, through=None):
        require(type(first) is int and first >= 1 and text(reason), 'revision', '修订需要章号和明确原因。')
        with self.repo.transaction():
            self.controller_guard(owner)
            book = self._begin_revision(self.repo.load(), first, reason, through)
            self.repo.save(book)
        return self.status()

    def promote(self, owner=None):
        with self.repo.transaction():
            self.controller_guard(owner)
            book = self.repo.load()
            require(self.repo.pending() is None and workflow.choose(book, self.repo.headers(book['branch'])) == {'action': 'revision_ready'}, 'revision', '修订范围及独立复核尚未完成。')
            self._audit(book)
            revision = book['revision_run']
            self.repo.promote(book['branch'], revision['parent'])
            self.repo.put('official_branch', book['branch'])
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
            restored = self.repo.get('branch-book:' + parent)
            # Discard restores story state, never already spent editorial effort.
            for chapter, spent in book['rework'].items():
                prior = restored['rework'].setdefault(chapter, {'repairs': 0, 'redesigns': 0})
                for field in ('repairs', 'redesigns'):
                    prior[field] = max(prior.get(field, 0), spent.get(field, 0))
                prior['initial_used'] = prior.get('initial_used', False) or spent.get('initial_used', False)
            if book.get('repair_cases'):
                restored['repair_cases'] = copy.deepcopy(book['repair_cases'])
            restored['revision'] = book['revision'] + 1
            self.repo.cancel_pending('discard revision')
            self.repo.save(restored)
            self.repo.record('discard', {'branch': book['branch'], 'restored': parent})
        return self.status()

    def recontract(self, contract, source, owner=None, opening=False):
        require(text(source), 'author_source', '改约须保存作者要求原话。')
        candidate = planning.validate_contract(contract)
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
            if not book['proposal'] or book['proposal']['scope'] != 'contract':
                self.repo.put('amendment_base', book)
            self.repo.cancel_pending(source)
            producer = book.get('controller_owner') or owner or 'controller'
            book.update(status='running', revision=book['revision'] + 1,
                        proposal={'scope': 'contract', 'chapter': 1, 'data': candidate, 'producer': producer, 'source': source})
            if owner:
                book['controller_owner'] = owner
            self.repo.save(book)
            self.repo.record('recontract_candidate', {'hash': digest(candidate), 'source': source, 'producer': producer})
        return {'staged': True, 'contract_hash': digest(candidate)}

    def _activate_contract(self, old):
        proposal = old['pending_contract']
        rows = self.repo.headers(old['branch'])
        self.repo.put('branch-book:' + old['branch'], self.repo.get('amendment_base', old))
        book = workflow.new_book(proposal['data'], proposal['source'])
        book['contract_review'] = {'producer': proposal['producer'],
                                   'reviewer': old.get('pending_contract_reviewer', proposal['producer'])}
        if old.get('creation') and old['creation']['phase'] == 'contract':
            book['creation'] = copy.deepcopy(old['creation'])
            book['creation']['phase'] = 'ready'
            book['world'] = copy.deepcopy(old['world'])
            book['world_review'] = copy.deepcopy(old['world_review'])
            book['opening_world_only'] = True
        book['feedback'] = old['feedback'] + [proposal['source']]
        if old.get('repair_cases'):
            book['repair_cases'] = copy.deepcopy(old['repair_cases'])
        if old.get('author_decision_history'):
            book['author_decision_history'] = copy.deepcopy(old['author_decision_history'])
        if old.get('remedy_exhausted'):
            book['remedy_exhausted'] = copy.deepcopy(old['remedy_exhausted'])
        book['carry_findings'] = copy.deepcopy(old.get('carry_findings', [])) + copy.deepcopy(old.get('scope_findings', []))
        if old['draft']:
            book['carry_findings'].extend(copy.deepcopy(old['draft'].get('findings', [])))
            book['prior_candidate'] = {k: old['draft'][k] for k in ('chapter', 'title', 'prose')}
        book.update(rework=old['rework'], revision=old['revision'] + 1,
                    target=min(old['target'], book['contract']['volumes'][-1]['end']), finish=old['finish'])
        if rows:
            book['branch'] = self.repo.fork(old['branch'], 1)
            last = min(rows[-1]['n'], book['contract']['volumes'][-1]['end'])
            book.update(target=last, finish=False,
                        revision_run={'parent': old['branch'], 'first': 1, 'last': last, 'reason': proposal['source'],
                                      'target': min(old['target'], book['contract']['volumes'][-1]['end']), 'finish': old['finish']})
        else:
            book['branch'] = old['branch']
        self.repo.save(book)
        self.repo.record('contract_activate', {'hash': digest(book['contract']), 'source': proposal['source']})
        return book

    def _audit(self, book):
        require(book.get('contract') is not None, 'contract', '尚无生效约定，无法核对账本。',
                {'recover': '先完成开书约定与其独立核验。'})
        if book.get('world'):
            opening = book['creation']
            world.validate(book['world'], creation.selected(opening), opening['selection_hash'])
            creation.validate_contract(book['contract'], opening, book['world'])
            approval = book['world_review']
            review = quality.checks(approval['receipt'], checks_for(approval['receipt'].get('checks_version', 1), 'world'), {0: dump(book['world'])})
            require(review['verdict'] == 'pass' and approval['reviewer'] != approval['producer'], 'world_review', '世界模型缺少独立通过核验。')
        amendment = book.get('contract_review')
        if amendment:
            require(amendment['reviewer'] != amendment['producer'], 'contract_review', '改约缺少独立核验。')
        rows = self.repo.headers(book['branch'])
        state = self.replay(book['branch'], book['contract'])
        require(digest(state) == digest(book['state']), 'projection', '当前状态投影与完整重放不一致。')
        require(sum(r['han'] for r in rows) == book['written_han'], 'projection', '汉字计数投影不一致。')
        review_before = facts.seed(book['contract'])
        for row in rows:
            prose = self.repo.read_document(row['prose'])
            review = self.repo.read_document(row['review'])
            plan = self.repo.read_document(row['plan'])
            require(plan['chapter'] == row['n'] and review['writer'] != review['session'], 'review_independence', '章节计划或独立审稿来源不匹配。')
            quality.first_read(review['first_read'], {row['n']: prose})
            f, r = quality.chapter_review(review, {row['n']: prose}, review['obligations'],
                                          version=review.get('facts', {}).get('checks_version', 1))
            require(f['verdict'] == r['verdict'] == 'pass', 'review', '正式章节缺少两类通过审稿。')
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
        return {'ok': True, 'chapters': len(rows), 'state_hash': digest(state), 'written_han': book['written_han']}

    def audit(self):
        self.content_guard()
        return self._audit(self.repo.load())

    def complete(self, owner=None):
        with self.repo.transaction():
            self.controller_guard(owner)
            book = self.repo.load()
            if book['status'] == 'completed':
                return {'completed': True, 'idempotent': True}
            require(self.repo.pending() is None and workflow.choose(book, self.repo.headers(book['branch'])) == {'action': 'ready_to_complete'}, 'completion', '目标、作者定调、卷审或全书复核尚未完成。')
            report = self._audit(book)
            require(book['contract']['word_range'][0] <= book['written_han'] <= book['contract']['word_range'][1], 'word_target', '实际总汉字数不在作者目标区间，不能降低目标冒充完本。')
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
            book['completed_at'] = time.time()
            snapshot = self.repo.document({'contract': book['contract'], 'book': book, 'branch': book['branch'],
                                          'chapters': self.repo.headers(book['branch']), 'audit': report})
            book['status'] = 'completed'
            book['completion_snapshot'] = snapshot
            self.repo.save(book)
            self.repo.record('complete', report)
        return {'completed': True, 'snapshot_hash': snapshot, **report}

    def patch(self, task_id, old, new, start=None):
        task = self.repo.task(task_id)
        book = self._live(task)
        require(task['input']['stage'] in ('repair', 'redesign') and task['input'].get('capabilities', {}).get('editorial'),
                'patch', '仅本任务声明的返修或重设计可定位补丁。')
        return craft.patch_at(book['draft']['prose'], old, new, start)
