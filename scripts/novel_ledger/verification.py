"""Read-only verification of event history and completed publication sources.

Mutation services cannot define their own weaker replay. Stored status, state hashes
and previous audit reports are inputs to verify, never evidence of successful checks.
"""
from __future__ import annotations

from .contracts import digest, han_count, require, text
from .ports import VerificationReader, VerificationSources
from . import book_state, creation, drift_reconcile, editorial, facts, lint, narrative, planning, understanding, world


class VerificationService:
    def __init__(self, sources: VerificationReader):
        self.sources = VerificationSources(sources.read_document, sources.headers)

    @staticmethod
    def scope():
        return {'verification_scope': 'mechanical',
                'unverified': ['model_context_isolation', 'author_statement_authenticity', 'literary_quality']}

    def head(self, book):
        """Cheap continuation guard; full event replay remains a closing operation."""
        book_state.check_state(book)
        rows = self.sources.headers(book['branch'])
        expected = rows[-1]['state_hash'] if rows else digest(facts.seed(book.get('contract') or {}))
        require(digest(book['state']) == expected, 'projection',
                '当前事实投影不属于已提交章节链，禁止继续派工或提交。',
                {'chapter': rows[-1]['n'] if rows else 0,
                 'recover': '保留任务和候选，使用 audit 定位历史差异；不得直接改库或覆盖投影。'})
        require(book['written_han'] == sum(row['han'] for row in rows), 'projection', '汉字计数投影不一致。')
        if rows:
            require(rows[-1]['n'] == len(rows)
                    and facts.chain(rows[-2]['chain'] if len(rows) > 1 else 'genesis',
                                    rows[-1], digest(book['contract'])) == rows[-1]['chain'],
                    'chain', '当前约定或章节链头与已提交来源不一致。')
        return rows

    def replay(self, branch, contract, through=None, rows=None):
        state, previous, number = facts.seed(contract), 'genesis', 0
        rows = self.sources.headers(branch) if rows is None else rows
        for row in rows:
            if through is not None and row['n'] > through:
                break
            require(row['n'] == (1 if previous == 'genesis' else number + 1), 'chain', '章节链不连续。')
            number = row['n']
            prose = self.sources.read_document(row['prose'])
            state, normalized = facts.settle(state, self.sources.read_document(row['events']), prose, number)
            require(digest(normalized) == row['events'] and digest(state) == row['state_hash'], 'state_integrity', '事实重放与提交版本不一致。')
            require(facts.chain(previous, row, digest(contract)) == row['chain'], 'chain', '章节事件链被修改。')
            previous = row['chain']
        return state

    def audit(self, book, rows=None):
        book_state.check_state(book)
        require(book.get('contract') is not None, 'contract', '尚无生效约定，无法核对账本。',
                {'recover': '先完成开书约定与世界模型的机械核验。'})
        # A book imported from a hand-written contract has no opening record to compare its world
        # against: the world's shape was validated when `world_model` was dispatched (or by the
        # importer), and there is no selection hash to bind it to. Only a guided opening can be
        # checked for choice alignment, so that check runs exactly when the record exists.
        opening = book.get('creation')
        if book.get('world') and opening:
            choices = creation.selected(opening)
            world.validate(book['world'], choices, opening['selection_hash'],
                           sections=world.required_sections((creation.selected(opening).get('scale') or {}).get('tier'), choices))
            creation.validate_contract(book['contract'], opening, book['world'])
        rows = self.sources.headers(book['branch']) if rows is None else rows
        state = self.replay(book['branch'], book['contract'], rows=rows)
        require(digest(state) == digest(book['state']), 'projection', '当前状态投影与完整重放不一致。')
        require(sum(r['han'] for r in rows) == book['written_han'], 'projection', '汉字计数投影不一致。')
        chapter_state = facts.seed(book['contract'])
        for index, row in enumerate(rows):
            prose = self.sources.read_document(row['prose'])
            plan = self.sources.read_document(row['plan'])
            require(plan['chapter'] == row['n'], 'projection', '章节计划与章号不匹配。')
            review = self.sources.read_document(row['review'])
            require(isinstance(review, dict), 'outline_alignment', '章节缺少有效的章纲自比记录。',
                    {'chapter': row['n']})
            settlement = drift_reconcile.reconcile(review.get('drift_check'), plan, chapter_state, book.get('world'))
            require(not settlement['findings'], 'outline_alignment', '正式正文未通过固定章纲核验。',
                    {'chapter': row['n'], 'findings': settlement['findings']})
            chapter_state, events = facts.settle(chapter_state, facts.prepare_hook_links(settlement['events']),
                                                prose, row['n'])
            require(digest(events) == row['events'] and digest(chapter_state) == row['state_hash'],
                    'outline_alignment', '章节事实与固定章纲及自比记录不一致。', {'chapter': row['n']})
            require(book['contract']['chapter_min'] <= han_count(prose) <= book['contract']['chapter_max']
                    and han_count(prose) == row['han'], 'length', '正式篇幅不符合约定。')
            planning.check_text(prose, planning.policy_of(book))
            priors = reversed(rows[max(0, index - lint.DUPLICATE_WINDOW):index])
            findings = lint.draft_findings(prose, [(prior['n'], self.sources.read_document(prior['prose']))
                                                   for prior in priors], row['n'])
            require(not findings, 'prose_integrity', '正式正文未通过机械复验。',
                    {'chapter': row['n'], 'findings': findings})
        if 'understanding' in book:
            require(understanding.rebase(book['understanding'], {r['n']: r['prose'] for r in rows}) == book['understanding'],
                    'understanding_source', '作品理解包含不属于当前正文版本的依据。')
        # Anything the author accepted while a repair budget was still asking for changes stays on
        # the closing record: an accepted candidate must never read as a clean pass.
        accepted = [{'stage': row['stage'], 'scope': row.get('scope'), 'findings': row['findings']}
                    for row in book.get('accepted_findings') or []]
        deviations = list(book.get('design_drift') or [])
        return {'ok': True, 'chapters': len(rows), 'state_hash': digest(state), 'written_han': book['written_han'],
                **self.scope(),
                'accepted_findings': accepted,
                'accepted_findings_note': ('这些是作者在返修额度用尽后选择“接受并把意见记为未解决项”的条目；'
                                           '它们不是通过，完本后仍以未解决状态保留。' if accepted else ''),
                'design_drift': deviations,
                'design_drift_note': ('这些是历史版本遗留的偏差记录，不授予当前正文偏离章纲的权限；'
                                      '当前验收仍逐章核对固定章纲、自比与事实。'
                                      if deviations else '')}

    def completion(self, book, rows=None):
        """Current checks are run even for an already completed snapshot."""
        report = self.audit(book, rows)
        rows = self.sources.headers(book['branch']) if rows is None else rows
        end = editorial.effective_contract(book)['volumes'][-1]['end']
        require(rows and rows[-1]['n'] == end, 'chapter_target', '章节数未达到约定章数。')
        require(book.get('finish') and book.get('target') == end
                and not book.get('draft') and not book.get('pending_contract')
                and not book.get('revision_run') and not book.get('revision_directive'),
                'completion', '完本目标、候选或修订尚未闭合。')
        pilot = book.get('pilot') or {}
        require(pilot.get('prose') == rows[0]['prose'] and pilot.get('contract') == digest(book['contract'])
                and text(pilot.get('source')), 'pilot_version', '首章缺少对应准确正文与约定版本的作者认可。')
        require(not any(h['status'] == 'open' for h in book['state']['hooks'].values()),
                'payoffs', '仍有未交代承诺。')
        if book['contract'].get('narrative_tracking'):
            narrative.closure(book)
        if editorial.enabled(book):
            require(not book.get('author_block')
                    and all(c['status'] == 'resolved' for c in book.get('repair_cases', {}).values()),
                    'completion', '改案、根问题或作者裁决未解决。')
        return report

    def snapshot(self, reference):
        """Re-derive acceptance from immutable sources before publishing any files."""
        require(text(reference), 'completion', '缺少完本快照，不能依据状态标记交付。')
        snapshot = self.sources.read_document(reference)
        require(isinstance(snapshot, dict) and isinstance(snapshot.get('book'), dict)
                and isinstance(snapshot.get('chapters'), list), 'completion', '完本快照形状无效。')
        book, rows = snapshot['book'], snapshot['chapters']
        require(book.get('status') == 'completed' and snapshot.get('branch') == book.get('branch')
                and snapshot.get('contract') == book.get('contract'), 'completion', '完本快照来源不一致。')
        # Frozen chapter rows are authoritative for retrying delivery. A mutable
        # live view cannot replace them; their full event chain is checked below.
        self.completion(book, rows)
        return snapshot
