"""Opening-gate decision mechanics within the caller's transaction.

Application owns authorization, transaction scope and load/save. This service holds the
mechanics the opening decisions share — mutating the creation state through the creation
module, freezing it as a document, and naming the journal action — and never starts its
own transaction or re-checks the controller lease. The ladder slider (`opening_tier`)
stays in the application layer because each slide is its own transaction.
"""
from __future__ import annotations

from .contracts import require
from .ports import Repository
from . import creation, planning


class OpeningService:
    def __init__(self, repo: Repository, *, cancel_pending):
        self.repo = repo
        self.cancel_pending = cancel_pending

    def choice(self, book, option, board_hash, source):
        require(book['contract'] is None and book.get('creation') is not None,
                'opening', '当前不是逐门开书阶段。')
        book['creation'] = creation.pick(book['creation'], option, board_hash, source)
        book['revision'] += 1
        if book['creation']['phase'] == 'world':
            book['status'] = 'running'
        self.repo.document(book['creation'])
        self.repo.record('opening_choice', {'option': option, 'board_hash': board_hash, 'source': source})
        return {'selected': True, 'opening': creation.view(book['creation']),
                'next': 'world_model' if book['creation']['phase'] == 'world' else 'opening_options'}

    def intake(self, book, values, source):
        require(isinstance(values, dict), 'intake', '部分要求须为门 ID 到 value 的映射。')
        require(book['contract'] is None and book.get('creation'), 'intake', '仅准备项目接受部分要求。')
        require(self.repo.pending() is None, 'intake', '已有任务先按当前展示选择或 back，避免覆盖冻结任务。')
        for gate, value in values.items():
            planning.enforce(planning.policy_of(book), 'opening_options', {'value': value})
        book['creation'] = creation.intake(book['creation'], values, source)
        book['revision'] += 1
        if book['creation']['phase'] == 'world':
            book['status'] = 'running'
        self.repo.document(book['creation'])
        self.repo.record('intake', {'source': source, 'gates': list(values)})
        return {'opening': creation.view(book['creation'])}

    def regroup(self, book, board_hash, reason):
        require(book['contract'] is None and book.get('creation') is not None,
                'opening', '当前不是逐门开书阶段。')
        book['creation'] = creation.regroup(book['creation'], board_hash, reason)
        book['revision'] += 1
        self.repo.document(book['creation'])
        self.repo.record('opening_regroup', {'reason': reason, 'board_hash': board_hash})
        return {'next': 'opening_options', 'opening': creation.view(book['creation'])}

    def back(self, book, gate, reason):
        require(book['contract'] is None and book.get('creation') is not None,
                'opening', '有效约定已激活时使用 recontract，不覆盖旧选择。')
        book['creation'] = creation.back(book['creation'], gate, reason)
        book.update(status='preparing', world=None, revision=book['revision'] + 1)
        book.pop('pending_contract', None)
        self.cancel_pending(reason)
        self.repo.document(book['creation'])
        self.repo.record('opening_back', {'gate': gate, 'reason': reason})
        return {'next': 'opening_options', 'opening': creation.view(book['creation'])}
