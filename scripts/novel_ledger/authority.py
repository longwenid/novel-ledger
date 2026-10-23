"""Verifier for a protected host's per-request proofs.

The embedding host supplies key, proof and actual caller context outside model
control. No key is loaded from project files or environment variables. This is a
transport adapter, not an OS sandbox or a model-host implementation.
"""
from __future__ import annotations

import hashlib
import hmac
from .contracts import digest, dump, require, text


class SignedHostAuthority:
    def __init__(self, key, proof, *, context_id, audience, clock):
        require(isinstance(key, bytes) and len(key) >= 32, 'host_authority', '宿主密钥至少32字节。')
        require(text(context_id) and text(audience), 'host_authority', '宿主必须绑定实际调用上下文与项目受众。')
        self.key, self.proof, self.context_id, self.audience, self.clock = key, proof, context_id, audience, clock

    def verify(self, kind, subject, source=''):
        require(isinstance(self.proof, dict), 'host_authority', '缺少宿主签发证明。')
        claims = self.proof.get('claims')
        require(isinstance(claims, dict), 'host_authority', '宿主证明缺少claims。')
        signature = hmac.new(self.key, dump(claims).encode('utf-8'), hashlib.sha256).hexdigest()
        supplied = self.proof.get('signature')
        require(isinstance(supplied, str) and hmac.compare_digest(signature, supplied),
                'host_authority', '宿主证明签名不匹配。')
        now = self.clock()
        require(claims.get('kind') == kind and claims.get('subject') == digest(subject)
                and claims.get('source_hash') == digest(source) and claims.get('audience') == self.audience
                and claims.get('caller_context') == self.context_id,
                'host_authority', '证明不属于当前对象、来源、项目或调用上下文。')
        require(type(claims.get('issued_at')) in (int, float) and type(claims.get('expires_at')) in (int, float)
                and claims['issued_at'] <= now < claims['expires_at']
                and claims['expires_at'] - claims['issued_at'] <= 600 and text(claims.get('nonce')),
                'host_authority', '宿主证明过期、时间范围无效或缺少nonce。')
        if kind in ('worker', 'observer'):
            require(claims.get('isolated') is True and claims.get('context_id') == subject.get('session')
                    and claims['context_id'] != self.context_id, 'host_authority',
                    '宿主必须证明已创建不同于主控的独立模型上下文。')
        else:
            require(claims.get('human') is True and text(claims.get('interaction_id')),
                    'host_authority', '作者决定必须来自宿主真实人类交互。')
        return {'verified': True, **{key: claims.get(key) for key in ('nonce', 'context_id', 'interaction_id',
                                                                    'audience', 'caller_context')}}
