"""Protected-host proof verification and fail-closed local behavior, not an OS sandbox test."""
import hashlib
import hmac
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'tests')]
from novel_ledger.authority import SignedHostAuthority
from novel_ledger.bootstrap import open_local_runtime, local_application
from novel_ledger.contracts import Error, RESULT, digest, dump
from novel_ledger.governance import Governance
from novel_ledger import store_keys
from support import contract


class HostAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.runtime = open_local_runtime(Path(self.temp.name) / 'book', initialize=True, contract=contract(2))
        self.addCleanup(self.runtime.close)
        self.repo = self.runtime.repo
        self.app = self.runtime.app
        self.app.configure_assurance('required', 'off', '明确使用受控宿主。')
        self.audience = self.app.status()['assurance']['project_id']
        self.key = b'host-owned-test-key-never-in-model' * 2
        self.serial = 0

    def authority(self, kind, subject, source='', caller='controller-context', **extra):
        self.serial += 1
        claims = {'kind': kind, 'subject': digest(subject), 'source_hash': digest(source), 'audience': self.audience,
                  'caller_context': caller, 'nonce': 'nonce-%d' % self.serial,
                  'issued_at': 100, 'expires_at': 200, 'human': True, 'interaction_id': 'real-message-%d' % self.serial,
                  **extra}
        proof = {'claims': claims, 'signature': hmac.new(self.key, dump(claims).encode(), hashlib.sha256).hexdigest()}
        return SignedHostAuthority(self.key, proof, context_id=caller, audience=self.audience, clock=lambda: 150)

    def test_required_mode_rejects_local_cli_style_identity_and_author_source(self):
        task = self.app.advance()['task']
        with self.assertRaises(Error) as caught:
            self.app.prepare_worker(task['task_id'], 'worker-ch76-80')
        self.assertEqual(caught.exception.code, 'host_authority')
        with self.assertRaises(Error):
            self.app.run(finish=True, source='模型自行宣称作者希望完本。')
        self.assertIsNone(self.repo.get(store_keys.claim(task['task_id'])))

    def test_registered_child_can_read_but_controller_cannot_impersonate_it(self):
        task = self.app.advance()['task']
        subject = {'task': task['task_id'], 'session': 'actual-child-context'}
        authority = self.authority('worker', subject, context_id='actual-child-context', isolated=True)
        controller = local_application(self.repo, authority=authority)
        prepared = controller.prepare_worker(task['task_id'], 'actual-child-context')
        with self.assertRaises(Error):
            controller.read(task['task_id'])
        child_authority = SignedHostAuthority(self.key, None, context_id='actual-child-context',
                                              audience=self.audience, clock=lambda: 150)
        child = local_application(self.repo, authority=child_authority)
        ready = child.worker_ready(task['task_id'], 'actual-child-context', prepared['worker_env']['NOVEL_EXECUTION_CLAIM'])
        self.assertTrue(ready['ready'])
        self.assertTrue(child.read(task['task_id'])['records'])

    def test_same_controller_context_cannot_be_registered_as_an_independent_child(self):
        subject = {'task': 'task-a', 'session': 'controller-context'}
        authority = self.authority('worker', subject, context_id='controller-context', isolated=True)
        with self.assertRaises(Error):
            authority.verify('worker', subject)

    def test_matching_caller_context_does_not_bypass_independent_worker_registration(self):
        task = self.app.advance()['task']
        authority = SignedHostAuthority(self.key, None, context_id='controller-context',
                                         audience=self.audience, clock=lambda: 150)
        controller = local_application(self.repo, authority=authority)
        with self.assertRaises(Error) as caught:
            controller.submit({'schema': RESULT, 'task_id': task['task_id'], 'session': 'controller-context', 'data': {}})
        self.assertEqual(caught.exception.code, 'host_actor')
        self.assertEqual(self.repo.task(task['task_id'])['status'], 'pending')

    def test_human_proof_is_bound_to_kind_subject_source_project_and_context(self):
        subject = {'decision_id': 'repair:exact-candidate', 'option': '再返修一轮', 'subject': {'chapter': 19}}
        authority = self.authority('answer', subject, '只对当前第19章追加一轮。')
        self.assertTrue(authority.verify('answer', subject, '只对当前第19章追加一轮。')['verified'])
        for kind, value, source in [('run', subject, '只对当前第19章追加一轮。'),
                                    ('answer', {**subject, 'decision_id': 'another'}, '只对当前第19章追加一轮。'),
                                    ('answer', subject, '模型自己编的新答复')]:
            with self.assertRaises(Error):
                authority.verify(kind, value, source)
        authority.audience = 'other-project'
        with self.assertRaises(Error):
            authority.verify('answer', subject, '只对当前第19章追加一轮。')

    def test_used_author_proof_cannot_be_replayed(self):
        authority = self.authority('answer', {'decision': 'exact'}, '只追加这一轮。')
        governance = Governance(self.repo, authority)
        with self.repo.transaction():
            governance.authorize('answer', {'decision': 'exact'}, '只追加这一轮。')
        with self.assertRaises(Error):
            with self.repo.transaction():
                governance.authorize('answer', {'decision': 'exact'}, '只追加这一轮。')

    def test_forged_or_expired_proof_and_nonhuman_decisions_are_rejected(self):
        subject = {'decision': 'exact'}
        for changes in ({'human': False}, {'expires_at': 140}):
            authority = self.authority('answer', subject, '原话', **changes)
            with self.assertRaises(Error):
                authority.verify('answer', subject, '原话')
        authority = self.authority('answer', subject, '原话')
        authority.proof['claims']['human'] = False
        with self.assertRaises(Error):
            authority.verify('answer', subject, '原话')


if __name__ == '__main__':
    unittest.main()
