"""The command adapter can dispatch through a different composition factory."""
import io
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import novel


class ApplicationEndpoint:
    def status(self):
        return {'status': 'running', 'backend': 'independent'}

    def check(self, payload, task_id=None, session=None):
        return {'payload': payload, 'task_id': task_id, 'session': session}


class AlternateRuntime:
    def __init__(self):
        self.app = ApplicationEndpoint()
        self.closed = False

    def close(self):
        self.closed = True


class CommandBoundaryTests(unittest.TestCase):
    def dispatch(self, command, runtime):
        calls = []

        def factory(project, **options):
            calls.append((project, options))
            return runtime

        arguments = novel.parser().parse_args(['--project', 'opaque-project', *command])
        with patch.dict(os.environ, {}, clear=True):
            result = novel.dispatch(arguments, open_runtime=factory)
        self.assertEqual(calls[0][0], 'opaque-project')
        self.assertTrue(runtime.closed)
        self.assertFalse(hasattr(runtime, 'repo'))
        return result, calls[0][1]

    def test_status_dispatch_has_no_concrete_persistence_requirement(self):
        result, options = self.dispatch(['status'], AlternateRuntime())
        self.assertEqual(result, {'status': 'running', 'backend': 'independent'})
        self.assertFalse(options['initialize'])
        self.assertIsNone(options['contract'])

    def test_stdin_is_parsed_at_the_command_boundary(self):
        payload = {'schema': 'receipt', 'session': 'explicit-reader', 'data': {'intent': '测试'}}
        with patch.object(sys, 'stdin', io.StringIO(json.dumps(payload))):
            result, _ = self.dispatch(['check', '--task', 'opaque-task'], AlternateRuntime())
        self.assertEqual(result, {'payload': payload, 'task_id': 'opaque-task', 'session': None})


if __name__ == '__main__':
    unittest.main()
