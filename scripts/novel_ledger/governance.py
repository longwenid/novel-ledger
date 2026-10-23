"""Execution provenance and governance checkpoints, separate from story facts.

Local checkpoints detect accidental/bypassed repository saves, not a malicious OS
account rewriting both the book and checkpoint. Required trust needs an authority
injected by a protected host, never a secret placed in the novel's directory.
"""
from __future__ import annotations

from .contracts import digest, require, text
from .ports import Repository
from . import store_keys


class Governance:
    def __init__(self, repo: Repository, authority=None, new_id=None):
        self.repo, self.authority, self.new_id = repo, authority, new_id

    def policy(self):
        return self.repo.get(store_keys.ASSURANCE_POLICY) or {
            'trust': 'advisory', 'continuity': 'off', 'legacy_unverified': True}

    def configure(self, trust, continuity, source):
        require(trust in ('advisory', 'required') and continuity in ('off', 'required'),
                'assurance_policy', 'trust须为advisory/required，continuity须为off/required。')
        require(text(source), 'author_source', '保存保障策略的作者来源。')
        self.authorize('policy', {'trust': trust, 'continuity': continuity}, source)
        old = self.policy()
        book = self.repo.load()
        project_id = old.get('project_id') or self.new_id()
        legacy = old.get('legacy_unverified', False) and (book['revision'] > 0 or bool(self.repo.headers(book['branch'])))
        self.repo.put(store_keys.ASSURANCE_POLICY, {'trust': trust, 'continuity': continuity,
                                                   'source': source, 'project_id': project_id, 'legacy_unverified': legacy})
        self.repo.record('assurance_policy', {'trust': trust, 'continuity': continuity, 'source': source})

    def authorize(self, kind, subject, source=''):
        if self.policy()['trust'] != 'required':
            return {'verified': False, 'mode': 'advisory'}
        require(self.authority is not None, 'host_authority',
                '此项目要求受控宿主证明；本地CLI不能代签身份或作者答复。')
        require(kind in ('worker', 'observer') or text(source), 'author_source', '受控作者决定须保存真实原话。')
        proof = self.authority.verify(kind, subject, source)
        require(isinstance(proof, dict) and proof.get('verified') is True and text(proof.get('nonce'))
                and proof.get('audience') == self.policy().get('project_id'),
                'host_authority', '宿主未返回可验证的一次性证明。')
        key = store_keys.authorization(proof['nonce'])
        old = self.repo.get(key)
        if old and kind in ('worker', 'observer') and old['kind'] == kind and old['subject'] == digest(subject):
            return old['proof']  # Reconfirming the same registration grants no new capability.
        require(old is None, 'authorization_replay', '此宿主授权已经使用。')
        self.repo.put(key, {'kind': kind, 'subject': digest(subject), 'proof': proof})
        self.repo.record('host_authorization', {'kind': kind, 'subject': digest(subject), 'proof': proof})
        return proof

    def actor(self, session):
        if self.policy()['trust'] == 'required':
            require(self.authority is not None and self.authority.context_id == session
                    and self.authority.audience == self.policy().get('project_id'),
                    'host_actor', '调用通道不是已绑定的真实模型上下文。')

    @staticmethod
    def projection(book):
        draft = book.get('draft') or {}
        return {**{key: book.get(key) for key in ('branch', 'revision', 'status', 'target', 'finish', 'writing_mode', 'rework', 'author_block',
                                                  'author_decision_history', 'pilot', 'run_authorized')},
                'draft_control': {key: draft.get(key) for key in ('chapter', 'stage', 'findings', 'recurrence',
                                                                 'attempt_signatures', 'current_findings')}}

    def check(self, book):
        checkpoint = self.repo.get(store_keys.GOVERNANCE_CHECKPOINT)
        if checkpoint:
            require(checkpoint['projection'] == digest(self.projection(book))
                    and checkpoint.get('policy') == digest(self.repo.get(store_keys.ASSURANCE_POLICY)), 'governance_integrity',
                    '治理字段与最近正式操作不一致；保留现场，不清空返修记录继续。')

    def seal(self, book):
        # The first legitimate write establishes a checkpoint even for a legacy project.
        # Read-only commands never install one or certify earlier history.
        prior = self.repo.get(store_keys.GOVERNANCE_CHECKPOINT) or {}
        row = {'projection': digest(self.projection(book)), 'previous': prior.get('hash'),
               'policy': digest(self.repo.get(store_keys.ASSURANCE_POLICY))}
        row['hash'] = digest(row)
        self.repo.put(store_keys.GOVERNANCE_CHECKPOINT, row)
        self.repo.record('governance_checkpoint', row)

    def describe(self):
        policy = self.policy()
        return {'trust_mode': policy['trust'], 'continuity_mode': policy['continuity'],
                'project_id': policy.get('project_id'),
                'legacy_unverified': policy.get('legacy_unverified', False),
                'host_authority_available': self.authority is not None,
                'process_provenance': 'host_required' if policy['trust'] == 'required' else 'unverified',
                'storage_isolation': 'deployment_required',
                'note': '检查点不等于OS隔离；同账户可写数据库时仍须受控宿主部署。'}
