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

    def test_status_attaches_the_book_view_when_the_runtime_offers_it(self):
        class ViewingRuntime(AlternateRuntime):
            def book_view(self):
                return {'path': str(Path('book') / 'book.html')}

        result, _ = self.dispatch(['status'], ViewingRuntime())
        self.assertEqual(result['book_view']['path'], str(Path('book') / 'book.html'))

    def test_stdin_is_parsed_at_the_command_boundary(self):
        payload = {'schema': 'receipt', 'session': 'explicit-reader', 'data': {'intent': '测试'}}
        with patch.object(sys, 'stdin', io.StringIO(json.dumps(payload))):
            result, _ = self.dispatch(['check', '--task', 'opaque-task'], AlternateRuntime())
        self.assertEqual(result, {'payload': payload, 'task_id': 'opaque-task', 'session': None})

    def test_piped_bytes_are_decoded_as_utf8_whatever_the_console_codepage_is(self):
        """A Windows console is not UTF-8: decoding the pipe through the locale mangles Chinese
        and then reports a field error for text the worker never wrote. The bytes are the contract."""
        payload = {'schema': 'receipt', 'session': 'reader', 'data': {'intent': '中文收据，标点：。？'}}
        for raw in (json.dumps(payload, ensure_ascii=False).encode('utf-8'),
                    json.dumps(payload, ensure_ascii=False).encode('utf-8-sig')):
            with self.subTest(bom=raw[:3] == b'\xef\xbb\xbf'):
                with patch.object(sys, 'stdin', io.BytesIO(raw)):
                    result, _ = self.dispatch(['check', '--task', 'opaque-task'], AlternateRuntime())
                self.assertEqual(result['payload'], payload)

    def test_a_pipe_that_is_not_utf8_names_the_fix_instead_of_guessing(self):
        payload = json.dumps({'schema': 'receipt', 'data': {'intent': '中文'}}, ensure_ascii=False)
        with patch.object(sys, 'stdin', io.BytesIO(payload.encode('gbk'))):
            with self.assertRaises(novel.Error) as caught:
                self.dispatch(['check', '--task', 'opaque-task'], AlternateRuntime())
        self.assertEqual(caught.exception.code, 'stdin_encoding')
        self.assertIn('--file', caught.exception.details['recover'])


if __name__ == '__main__':
    unittest.main()
