"""Historical revision mechanics within the caller's transaction.

Application owns authorization, transaction scope and final persistence. This service
uses repository capabilities and an explicit cancellation callback; it never calls
back into arbitrary application use cases or starts a separate transaction.
"""
from __future__ import annotations

import copy
from .contracts import Error, digest, require
from .ports import Repository
from . import editorial, facts, narrative, revision_impact, store_keys, story_memory, understanding, workflow


class RevisionService:
    def __init__(self, repo: Repository, *, cancel_pending):
        self.repo = repo
        self.cancel_pending = cancel_pending

    def replay(self, branch, contract, through=None):
        state, previous, number = facts.seed(contract), 'genesis', 0
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

    def carry_suffix(self, book, revision):
        """Append the chapters past a narrow revision's end, unchanged, onto the candidate branch.

        Carrying is sound only while the rewrite leaves their facts intact: each carried chapter's
        frozen events settle against the new state, and the first divergence refuses the whole carry
        so the revision must widen instead of silently deshaping the suffix.
        """
        state = book['state']
        headers = self.repo.headers(book['branch'])
        head = headers[-1]['n']
        original_state = self.replay(revision['parent'], book['contract'], head)
        if revision.get('impact', {}).get('mode') in ('expression', 'reading'):
            require(state == original_state, 'revision_carry', '表达或阅读修订改变了事实投影，须按语义变更重新分析范围。')
        previous = headers[-1]['chain']
        contract_hash = digest(book['contract'])
        accepted_plans = {str(r['n']): self.repo.read_document(r['plan']) for r in headers}
        impact = revision.get('impact')
        require(not impact or impact.get('schema') == revision_impact.SCHEMA,
                'revision_impact', '修订方案必须按当前流程重新分析。')
        actions = {r['chapter']: r['action'] for r in (impact or {}).get('chapter_actions', [])}
        require(all(a in ('keep', 'local', 'rewrite') for a in actions.values()),
                'revision_impact', '修订方案含已删除的处理动作，须重新分析。')
        remaining = [r for r in revision.get('carry', []) if r['n'] > head]
        for index, row in enumerate(remaining):
            prose = self.repo.read_document(row['prose'])
            plan = self.repo.read_document(row['plan'])
            planned = book['plans'].get(str(row['n']))
            if planned != plan or actions.get(row['n']) == 'rewrite':
                # The revision changed this chapter's outline, or dropped it entirely: the rest of
                # the volume's chapter outlines are re-derived from the state the revision is
                # actually in, which is what the old alignment stages used to arbitrate.
                revision['carry'] = remaining[index:]
                book['state'] = state
                if revision.get('impact'):
                    plan_actions = revision['impact'].setdefault('chapter_actions', [])
                    action = next((a for a in plan_actions if a['chapter'] == row['n']), None)
                    if action is None:
                        action = {'chapter': row['n']}
                        plan_actions.append(action)
                    action.update(action='rewrite', reason='前文修订改变了本章章纲，按新章纲完整写作。')
                revision['outline_task'] = row['n']
                return
            try:
                story_memory.require_current(plan)
                story_memory.bind(copy.deepcopy(plan), accepted_plans)
                if book['contract'].get('narrative_tracking'):
                    require(not narrative.unmet(state, plan), 'plan_preconditions', '被携带章节的实际前提已被修订改变。',
                            {'unmet': narrative.unmet(state, plan)})
                require(all(story_memory.lookup(state, kind, key) == story_memory.lookup(original_state, kind, key)
                            for kind, key in story_memory.reads(plan)),
                        'story_dependency', '原样携带章节的显式叙事输入发生变化。')
                next_state, normalized = facts.settle(state, self.repo.read_document(row['events']), prose, row['n'])
            except Error as exc:
                raise Error('revision_carry', '修订影响了第 %d 章的事实，不能原样携带其后缀。' % row['n'],
                            {'chapter': row['n'], 'cause': exc.as_dict(),
                             'recover': '先重新分析实际依赖；依赖传播产生的扩大修订仍受自动回改边界约束，超范围先交付修复方案。'})
            state = next_state
            original_state, _ = facts.settle(original_state, self.repo.read_document(row['events']), prose, row['n'])
            carried = dict(row)
            carried['events'] = self.repo.document(normalized)
            carried['state_hash'] = digest(state)
            carried['chain'] = facts.chain(previous, carried, contract_hash)
            self.repo.add_chapter(book['branch'], carried)
            book['plans'][str(row['n'])] = plan
            accepted_plans[str(row['n'])] = plan
            previous = carried['chain']
            book['written_han'] += carried['han']
        book['state'] = state
        revision['carry'] = []

    def refresh_understanding(self, book):
        if 'understanding' not in book:
            return
        hashes = {r['n']: r['prose'] for r in self.repo.headers(book['branch'])}
        memory = book['understanding']
        revision = book.get('revision_run')
        if revision:
            parent = self.repo.get(store_keys.branch_book(revision['parent'])).get('understanding', understanding.empty())
            original = {digest(v) for v in parent['versions']}
            memory = {'schema': understanding.SCHEMA, 'versions': parent['versions'] +
                      [v for v in memory['versions'] if digest(v) not in original]}
        book['understanding'] = understanding.rebase(memory, hashes)

    def analyze(self, book, first, changes=None, through=None):
        rows = [{**row, 'plan_hash': row['plan'], 'events_hash': row['events'],
                 'plan': self.repo.read_document(row['plan']), 'events': self.repo.read_document(row['events'])}
                for row in self.repo.headers(book['branch'])]
        return revision_impact.analyze(rows, first, changes, through)

    def context_hash(self, book):
        return digest({'editorial': editorial.context_hash(book), 'plans': book['plans'],
                       'revision': book['revision']})

    def start_revision(self, book, directive):
        changes = directive.get('changes', {'mode': 'semantic', 'changes': []})
        impact = self.analyze(book, directive['first'], changes, directive['through'])
        head = self.repo.headers(book['branch'])[-1]['n']
        policy = editorial.revision_policy(book, head)
        violations = editorial.revision_violations(policy, impact)
        requested = directive.get('through')
        if type(requested) is int and impact['last'] > requested:
            # An author who names an endpoint ("only up to chapter four") does not get a branch that
            # quietly rewrites past it: the dependency analysis reaching further is a violation, and
            # the whole plan is saved for authorization instead of being executed.
            violations = violations + ['impact_beyond_request']
        if violations:
            plan = {**copy.deepcopy(directive), 'changes': changes, 'impact': impact,
                    'policy': policy, 'violations': violations, 'branch': book['branch'],
                    'context_hash': self.context_hash(book), 'blocked': True}
            plan.pop('plan_hash', None)
            plan['plan_hash'] = digest(plan)
            book['revision_directive'] = plan
            book.update(status='paused', pause_reason='修复影响超出自动回改范围；已保存方案，未修改原稿。')
            self.repo.record('revision_blocked', {'plan_hash': plan['plan_hash'], 'violations': violations})
            return book
        return self.begin(book, directive['first'], directive['reason'], impact['last'],
                                    directive.get('case_ids', ()), changes, impact)

    def begin(self, book, first, reason, through=None, case_ids=(), changes=None, impact=None):
        require(book['revision_run'] is None, 'revision', '先完成或撤销当前修订。')
        rows = self.repo.headers(book['branch'])
        require(rows and first <= rows[-1]['n'], 'revision', '修订起点必须已有正式正文。')
        book_last = rows[-1]['n']
        impact = impact if impact is not None else self.analyze(book, first, changes) if changes is not None else None
        end = impact['last'] if impact and through is None else book_last if through is None else through
        require(type(end) is int and first <= end <= book_last, 'revision', '修订终点须在修订起点与最后一章之间。',
                {'revision_first': first, 'book_last': book_last,
                 'recover': '一词级小修用 --through 收窄到受影响章；终点之后的章节原样携带并复核接缝。'})
        require(not impact or end >= impact['last'], 'revision_impact', '指定终点小于依赖分析的影响范围。',
                {'required_through': impact['last']} if impact else None)
        if impact:
            analyzed_last = impact['last']
            if end > analyzed_last:
                impact = self.analyze(book, first, changes, end)
                require(end >= impact['last'], 'revision_impact', '扩大的修改区间产生后续依赖，指定终点仍不足。',
                        {'required_through': impact['last']})
            impact['analyzed_last'] = analyzed_last
        parent = book['branch']
        self.repo.put(store_keys.branch_book(parent), book)
        branch = self.repo.fork(parent, first)
        old = self.repo.chapter(parent, first)
        # The暂停 that led here is over: the branch and its first task now carry the work, and leaving
        # the old reason behind makes status read as paused to every consumer of pause_reason.
        book.pop('pause_reason', None)
        book.update(branch=branch, state=self.replay(parent, book['contract'], first - 1),
                    written_han=sum(r['han'] for r in rows if r['n'] < first), status='running',
                    target=book_last, finish=False, revision=book['revision'] + 1)
        if 'understanding' in book:
            book['understanding'] = understanding.rebase(book['understanding'], {r['n']: r['prose'] for r in rows if r['n'] < first})
        book['revision_run'] = {'parent': parent, 'first': first, 'last': end, 'reason': reason,
                                'target': self.repo.get(store_keys.branch_book(parent))['target'], 'finish': self.repo.get(store_keys.branch_book(parent))['finish'],
                                'carry': [r for r in rows if r['n'] > end]}
        if impact:
            book['revision_run']['impact'] = impact
        draft = {'chapter': first, 'title': old['title'], 'prose': self.repo.read_document(old['prose']), 'producer': 'historical', 'history': [], 'findings': []}
        workflow.route_repair(book, draft, [{'criterion': 'change', 'severity': 'quality', 'target_chapter': first,
                                           'repair_scope': 'local' if impact and impact['mode'] != 'semantic' else 'chapter', 'reason': reason}])
        self.cancel_pending(reason)
        self.repo.record('revision', {k: v for k, v in book['revision_run'].items() if k != 'carry'})
        book['revision_run']['case_ids'] = list(case_ids)
        book.pop('revision_directive', None)
        return book
