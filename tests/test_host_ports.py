"""A process host can run against public use cases without application internals."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from novel_ledger import host
from novel_ledger.contracts import Error
from support import link_or_skip


class PublicApplication:
    """Simulate a worker's external submission through the public status boundary."""
    def __init__(self, project, reviewer=None):
        self.project = project
        self.reviewer = reviewer
        self.status_reads = 0
        self.released = []
        self.claims = []

    def advance(self, after=None, owner=None, compact=False, wait_pending=False):
        return {'action': 'task_ready', 'task': {
            'task_id': 'task', 'task_path': str(self.project / 'task.json'),
            'process': {'project_path': str(self.project), 'task_path': str(self.project / 'task.json'),
                        'log_path': str(self.project / 'host.log')}}}

    def task_status(self, task_id):
        self.status_reads += 1
        return {'id': task_id, 'status': 'pending' if self.status_reads == 1 else 'done',
                'reviewer': self.reviewer}

    def claim(self, task_id, session, seconds=300):
        self.claims.append((task_id, session, seconds))
        return {'token': 'opaque-claim'}

    def release_claim(self, task_id, token):
        self.released.append((task_id, token))

    def renew(self, owner, seconds=300):
        return {'owner': owner}


class HostPortTests(unittest.TestCase):
    def test_process_uses_public_use_cases_and_delivered_locations(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            app = PublicApplication(project)
            self.assertFalse(hasattr(app, 'repo'))
            code = ('import json,os; print(json.dumps({k:os.environ[k] for k in '
                    '("NOVEL_PROJECT","NOVEL_TASK_PATH","NOVEL_TASK_ID","NOVEL_EXECUTION_CLAIM")}))')
            result = host.step(app, [sys.executable, '-c', code], timeout=10)
            self.assertEqual(result['action'], 'worker_finished')
            self.assertTrue(result['submitted'])
            self.assertEqual(app.released, [('task', 'opaque-claim')])
            environment = json.loads((project / 'host.log').read_text(encoding='utf-8'))
            self.assertEqual(environment, {'NOVEL_PROJECT': str(project), 'NOVEL_TASK_PATH': str(project / 'task.json'),
                                          'NOVEL_TASK_ID': 'task', 'NOVEL_EXECUTION_CLAIM': 'opaque-claim'})

    def test_frozen_session_is_reported_without_storage_or_process_access(self):
        with tempfile.TemporaryDirectory() as temporary:
            app = PublicApplication(Path(temporary), reviewer='reader-session')
            result = host.step(app, ['unused-command'])
            self.assertEqual(result['action'], 'resume_session_required')
            self.assertEqual(result['session'], 'reader-session')
            self.assertFalse(app.claims)
            self.assertFalse(app.released)

    def test_non_file_delivery_is_rejected_before_claiming_a_worker(self):
        with tempfile.TemporaryDirectory() as temporary:
            app = PublicApplication(Path(temporary))
            for process in (None, {}, {'log_path': 12}):
                with self.subTest(process=process), patch.object(app, 'advance', return_value={
                        'action': 'task_ready', 'task': {'task_id': 'task', 'process': process}}):
                    with self.assertRaises(Error) as caught:
                        host.step(app, ['unused-command'])
                    self.assertEqual(caught.exception.code, 'host_transport')
            self.assertFalse(app.claims)

    def test_failure_after_claim_always_releases_the_worker(self):
        with tempfile.TemporaryDirectory() as temporary:
            app = PublicApplication(Path(temporary))
            with patch.object(host.time, 'monotonic', side_effect=RuntimeError('clock failed')):
                with self.assertRaises(RuntimeError):
                    host.step(app, ['unused-command'])
            self.assertEqual(app.released, [('task', 'opaque-claim')])

    def test_host_log_replaces_aliases_without_changing_their_external_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            project = base / 'project'
            project.mkdir()
            external = base / 'outside.txt'
            external.write_text('original external file', encoding='utf-8')
            log = project / 'host.log'
            for kind in ('symbolic', 'hard'):
                with self.subTest(kind=kind):
                    log.unlink(missing_ok=True)
                    if kind == 'symbolic':
                        link_or_skip(self, log, external)
                    else:
                        os.link(external, log)
                    result = host.step(PublicApplication(project), [sys.executable, '-c', 'print("worker log")'])
                    self.assertEqual(result['action'], 'worker_finished')
                    self.assertEqual(external.read_text(encoding='utf-8'), 'original external file')
                    self.assertEqual(log.read_text(encoding='utf-8').strip(), 'worker log')
                    self.assertFalse(log.is_symlink())


if __name__ == '__main__':
    unittest.main()
