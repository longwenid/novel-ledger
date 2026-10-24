"""Version-bound independent reading, frozen before plan/self-check comparison.

Requests and reports are audit documents, never direct writes to story facts.
Host authenticity is delegated to Governance; advisory mode stays visibly unverified.
"""
from __future__ import annotations

from .contracts import digest, dump, require, text
from .ports import Repository
from . import continuity, store_keys

SCHEMA = 'novel-ledger.continuity/1'


class ContinuityService:
    def __init__(self, repo: Repository, governance, new_id, validate_task):
        self.repo, self.governance, self.new_id = repo, governance, new_id
        self.validate_task = validate_task

    @staticmethod
    def candidate_hash(receipt):
        # Transport credentials may rotate during recovery; the frozen input and
        # every submitted content field must still match the independently read version.
        return digest({key: value for key, value in receipt.items() if key not in ('session', 'execution_claim')})

    def current(self, task_id):
        ident = self.repo.get(store_keys.pending_review(task_id))
        return self.repo.get(store_keys.continuity_review(ident)) if ident else None

    def summary(self, task_id):
        row = self.current(task_id)
        if not row:
            return None
        return {key: row.get(key) for key in ('request_id', 'task_id', 'candidate_hash', 'phase', 'observer')}

    def prepare(self, task, receipt, chapter):
        ident = self.candidate_hash(receipt)
        key = store_keys.continuity_review(ident)
        old = self.repo.get(key)
        current = self.current(task['id'])
        if current and current['request_id'] != ident:
            require(current['phase'] in ('await_observer', 'done'), 'continuity_pending',
                    '已有独立阅读或作者待决；保留原候选，完成核验或显式取消任务后再替换。')
            if current.get('report'):
                report = self.repo.read_document(current['report'])
                blocking = any(item['kind'] == 'contradiction' for item in report['findings'])
                blocking = blocking or (current.get('resolution') or {}).get('disposition') == 'repair'
                require(not blocking, 'continuity_settlement',
                        '原候选核验要求返修，须先重交原回执结算有限返修，再提交新稿。')
        index_key = store_keys.review_candidates(task['id'])
        index = self.repo.get(index_key, {})
        prose_key = digest(''.join(chapter['prose'].split()))
        require(index.get(prose_key) in (None, ident), 'no_progress',
                '正文未变，不能靠改自评或附带字段重复派读；重交准确原回执。',
                {'next_action': 'resubmit_original_receipt', 'request_id': index.get(prose_key)})
        self.repo.put(store_keys.pending_review(task['id']), ident)
        if old:
            return old
        history = [{'chapter': row['n'], 'prose_hash': row['prose'], 'review_hash': row['review']}
                   for row in self.repo.headers(task['input']['branch']) if row['n'] < chapter['n']]
        candidate = {'schema': SCHEMA, 'task_id': task['id'], 'input_hash': task['input_hash'],
                     'branch': task['input']['branch'], 'revision': task['input']['revision'],
                     'candidate_hash': ident, 'chapter': chapter['n'], 'title': chapter['title'],
                     'prose': chapter['prose'], 'prose_hash': digest(chapter['prose']),
                     'producer': receipt['session'], 'history': history,
                     'comparison': {'plan': chapter['plan'], 'self_check': receipt['data']['self_check'],
                                    'drift_check': receipt['data'].get('drift_check')}}
        row = {'schema': SCHEMA, 'request_id': ident, 'task_id': task['id'], 'candidate_hash': ident,
               'candidate': self.repo.document(candidate), 'phase': 'await_observer', 'observer': None}
        self.repo.put(key, row)
        self.repo.put(index_key, {**index, prose_key: ident})
        self.repo.put(store_keys.pending_review(task['id']), ident)
        self.repo.record('continuity_requested', {'request': ident, 'task': task['id']})
        return row

    def _active(self, ident):
        row = self.repo.get(store_keys.continuity_review(ident))
        require(row is not None, 'continuity_request', '不存在此核验请求。')
        task = self.repo.task(row['task_id'])
        self.validate_task(task)
        candidate = self.repo.read_document(row['candidate'])
        book = self.repo.load()
        require(task['status'] == 'pending' and self.repo.get(store_keys.pending_review(task['id'])) == ident
                and candidate['input_hash'] == task['input_hash'] and book['revision'] == candidate['revision']
                and book['branch'] == candidate['branch'], 'continuity_stale', '核验对象已失效或已被新候选替换。')
        return row, candidate

    def prepare_observer(self, ident, session):
        row, candidate = self._active(ident)
        require(text(session) and session != candidate['producer'], 'continuity_identity', '核验者必须不同于执笔者。')
        require(row.get('observer') in (None, session), 'continuity_identity', '此核验已有其他执行者。')
        scope = self.repo.session_task(session)
        require(scope in (None, ident), 'session_reuse', '核验须使用独立的空历史上下文。')
        if not row.get('observer'):
            row['provenance'] = self.governance.authorize('observer', {'request': ident, 'session': session})
            row.update(observer=session, token=self.new_id(), phase='first_read')
            self.repo.bind_session(session, ident)
            self.repo.put(store_keys.continuity_review(ident), row)
            self.repo.record('continuity_observer', {'request': ident, 'session': session,
                                                    'provenance': row['provenance']})
        return {'schema': SCHEMA, 'request_id': ident, 'session': session, 'token': row['token'], 'phase': row['phase']}

    def _observer(self, ident, session, token):
        row, candidate = self._active(ident)
        self.governance.actor(session)
        require(row.get('observer') == session and row.get('token') == token and text(token),
                'continuity_identity', '核验身份或凭据不匹配。')
        return row, candidate

    def _sources(self, candidate, names):
        sources = {'candidate': {'prose': candidate['prose'], 'prose_hash': candidate['prose_hash']}}
        sources.update({str(row['chapter']): {'prose': self.repo.read_document(row['prose_hash']),
                                             'prose_hash': row['prose_hash']} for row in candidate['history']
                        if str(row['chapter']) in names})
        return sources

    def read(self, ident, session, token, chapter=None, compare=False):
        row, candidate = self._observer(ident, session, token)
        if compare:
            require(row.get('observations'), 'continuity_phase', '先冻结纯正文观察，再读取章纲和执笔自评。')
            result = {'schema': SCHEMA, 'request_id': ident, 'candidate_hash': row['candidate_hash'],
                    'comparison': candidate['comparison'],
                    'observations': self.repo.read_document(row['observations']),
                    'report_template': {'schema': SCHEMA, 'request_id': ident, 'candidate_hash': row['candidate_hash'],
                                        'observations_hash': row['observations'], 'findings': [], 'assessment': ''}}
            self.repo.record('continuity_read', {**store_keys.read_record(row['task_id'], ['comparison'], len(dump(result))),
                                                'request': ident, 'phase': 'comparison'})
            return result
        all_sources = self._sources(candidate, {str(chapter)}) if chapter is not None else None
        if chapter is not None:
            require(str(chapter) in all_sources, 'continuity_source', '补读章节不属于冻结历史。')
            sources = {str(chapter): all_sources[str(chapter)]}
        else:
            window = 9 if candidate['chapter'] % 10 == 0 else 2
            selected = candidate['history'][-window:]
            sources = {'candidate': {'prose': candidate['prose'], 'prose_hash': candidate['prose_hash']}}
            sources.update({str(item['chapter']): {'prose': self.repo.read_document(item['prose_hash']),
                                                  'prose_hash': item['prose_hash']} for item in selected})
        seen = sorted(set(row.get('seen', [])) | set(sources))
        row['seen'] = seen
        self.repo.put(store_keys.continuity_review(ident), row)
        result = {'schema': SCHEMA, 'request_id': ident, 'candidate_hash': row['candidate_hash'],
                'chapter': candidate['chapter'], 'sources': sources,
                'history': {'count': len(candidate['history']),
                            'first_chapter': candidate['history'][0]['chapter'] if candidate['history'] else None,
                            'last_chapter': candidate['history'][-1]['chapter'] if candidate['history'] else None,
                            'read': 'commands.review-read --chapter N'},
                'observation_template': {'schema': SCHEMA, 'request_id': ident, 'candidate_hash': row['candidate_hash'],
                                         'read_sources': seen, 'observations': [], 'limitations': []},
                'instructions': '先通读正文，记录生死、行动、时间期限、地点/证物、知情与表达；未证实的旧账目只作线索。'}
        self.repo.record('continuity_read', {**store_keys.read_record(row['task_id'], sources, len(dump(result))),
                                            'request': ident, 'phase': 'blind'})
        return result

    def observe(self, payload, session, token):
        ident = payload.get('request_id')
        row, candidate = self._observer(ident, session, token)
        require(payload.get('schema') == SCHEMA and payload.get('candidate_hash') == row['candidate_hash'],
                'continuity_version', '观察不属于当前候选版本。')
        required = {'candidate'} | {str(item['chapter']) for item in candidate['history'][-(9 if candidate['chapter'] % 10 == 0 else 2):]}
        read_sources = payload.get('read_sources')
        limitations = payload.get('limitations', [])
        require(isinstance(read_sources, list) and all(text(name) for name in read_sources)
                and isinstance(limitations, list) and all(text(item) for item in limitations),
                'continuity_observation', 'read_sources与limitations须为字符串列表。')
        require(set(read_sources) <= set(row.get('seen', []))
                and required <= set(row.get('seen', [])) and required <= set(read_sources),
                'continuity_coverage', '独立首读尚未覆盖候选和完整相邻章。')
        values = continuity.observations(payload.get('observations'), self._sources(candidate, row.get('seen', [])))
        frozen = {'observations': values, 'read_sources': payload['read_sources'],
                  'candidate_hash': row['candidate_hash'], 'limitations': payload.get('limitations', [])}
        reference = digest(frozen)
        require(row.get('observations') in (None, reference), 'continuity_phase', '纯读观察已冻结，不能在看到自评后覆盖。')
        if row.get('observations'):
            return {'schema': SCHEMA, 'request_id': ident, 'phase': row['phase'],
                    'observations_hash': reference, 'idempotent': True}
        row.update(observations=self.repo.document(frozen), phase='comparison')
        self.repo.put(store_keys.continuity_review(ident), row)
        self.repo.record('continuity_observed', {'request': ident, 'observations': reference})
        return {'schema': SCHEMA, 'request_id': ident, 'phase': 'comparison', 'observations_hash': reference}

    def report(self, payload, session, token):
        ident = payload.get('request_id')
        row, candidate = self._observer(ident, session, token)
        require(row.get('observations') and payload.get('schema') == SCHEMA
                and payload.get('candidate_hash') == row['candidate_hash']
                and payload.get('observations_hash') == row['observations'],
                'continuity_phase', '必须引用已冻结观察并绑定准确候选版本。')
        items = continuity.findings(payload.get('findings'), self._sources(candidate, row.get('seen', [])))
        observed = self.repo.read_document(row['observations'])['observations']
        items.extend(continuity.observed_contradictions(observed))
        items = list({digest(item): item for item in items}.values())
        require(text(payload.get('assessment')), 'continuity_report', '给出基于原文的阅读结论。')
        result = {**payload, 'findings': items, 'observer': session, 'provenance': row['provenance']}
        reference = digest(result)
        require(row.get('report') in (None, reference), 'continuity_phase', '已提交核验报告不能静默覆盖。')
        if row.get('report'):
            return {**self.summary(row['task_id']), 'idempotent': True}
        row.update(report=self.repo.document(result), phase='review_required' if any(item['kind'] == 'uncertain' for item in items) else 'done')
        self.repo.put(store_keys.continuity_review(ident), row)
        self.repo.record('continuity_reported', {'request': ident, 'report': reference, 'phase': row['phase']})
        return self.summary(row['task_id'])

    def resolve(self, ident, disposition, source):
        row, candidate = self._active(ident)
        if row.get('resolution'):
            require(row['resolution']['disposition'] == disposition and row['resolution']['source'] == source,
                    'continuity_resolution', '作者裁决已保存，不能静默覆盖。')
            return {**self.summary(row['task_id']), 'idempotent': True}
        require(row['phase'] == 'review_required' and disposition in ('accept_uncertainty', 'repair'),
                'continuity_resolution', '仅未决歧义可交作者接受未决或要求返修。')
        require(text(source), 'author_source', '保存准确的作者裁决原话。')
        proof = self.governance.authorize('continuity_resolution', {'request': ident, 'report': row['report'],
                                                                   'disposition': disposition}, source)
        row.update(phase='done', resolution={'disposition': disposition, 'source': source, 'proof': proof})
        self.repo.put(store_keys.continuity_review(ident), row)
        self.repo.record('continuity_resolved', {'request': ident, 'resolution': row['resolution']})
        return self.summary(row['task_id'])

    def evaluation(self, task_id, receipt):
        row = self.current(task_id)
        if not row or row['candidate_hash'] != self.candidate_hash(receipt):
            return None
        if row['phase'] != 'done':
            return {'pending': True, **self.summary(task_id)}
        report = self.repo.read_document(row['report'])
        must_repair = (row.get('resolution') or {}).get('disposition') == 'repair'
        blocking = [item for item in report['findings'] if item['kind'] == 'contradiction'
                    or must_repair and item['kind'] == 'uncertain']
        return {'pending': False, 'request_id': row['request_id'], 'report_hash': row['report'],
                'provenance': row['provenance'], 'resolution': row.get('resolution'),
                'editorial_notes': [item for item in report['findings'] if item['kind'] == 'editorial'],
                'uncertain_findings': [item for item in report['findings'] if item['kind'] == 'uncertain'],
                'findings': [{'criterion': 'continuity', 'severity': 'quality', 'repair_scope': 'chapter',
                              'reason': item['reason'], 'evidence': item['evidence']} for item in blocking]}
