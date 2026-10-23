"""Real HTTP preview: bounded transport, fresh committed snapshots and no writes."""
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from novel_ledger import bookpage, preview
from novel_ledger.bootstrap import open_local_runtime
from novel_ledger.contracts import Error
from novel_ledger.sqlite_store import SQLiteRepository
from support import contract, drive, response


class PreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name).resolve() / 'book'
        self.runtime = open_local_runtime(self.project, initialize=True, contract=contract(2))
        self.server = preview.create_server(self.project)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': 0.01}, daemon=True)
        self.thread.start()
        self.path = urlsplit(self.server.url).path

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.runtime.close()
        self.temp.cleanup()

    def request(self, route='', method='GET', headers=None, absolute=False):
        connection = HTTPConnection(self.server.authority, timeout=5)
        connection.request(method, route if absolute else self.path + route, headers=headers or {})
        result = connection.getresponse()
        status, body = result.status, result.read().decode('utf-8')
        response_headers = dict(result.getheaders())
        connection.close()
        return status, response_headers, body

    def data(self, route):
        status, headers, body = self.request('api/' + route)
        self.assertEqual(status, 200, body)
        self.assertEqual(headers['Cache-Control'], 'no-store')
        return json.loads(body)

    def test_fresh_commits_are_visible_and_entry_is_neither_grown_nor_rewritten(self):
        drive(self.runtime.app, until='write')
        entry = self.project / 'book.html'
        original = entry.read_bytes(), entry.stat().st_mtime_ns
        database = tuple(self.runtime.repo.db.iterdump())
        self.assertEqual(self.data('index')['chapters'], 0)
        self.assertEqual(self.request()[0], 200)
        self.assertNotIn('夜班退件', self.request()[2])
        self.assertEqual(tuple(self.runtime.repo.db.iterdump()), database)
        receipt = response(self.runtime.app)
        self.runtime.app.submit(receipt)
        self.assertEqual(self.data('index')['chapters'], 1)
        self.assertIn(receipt['data']['prose'], self.data('chapter/1')['html'])
        self.assertEqual((entry.read_bytes(), entry.stat().st_mtime_ns), original)
        book = self.runtime.repo.load()
        book['contract']['title'] = '新的标题'
        self.runtime.repo.db.execute('BEGIN IMMEDIATE')
        self.runtime.repo.save(book)
        try:
            self.assertEqual(self.data('section/contract')['title'], '夜班退件')
        finally:
            self.runtime.repo.db.rollback()
        self.runtime.repo.save(book)
        self.assertEqual(self.data('section/contract')['title'], '新的标题')

    def test_pagination_and_only_requested_chapter_prose_is_read(self):
        repo = self.runtime.repo
        with repo.transaction():
            for n in range(1, 206):
                prose = repo.document('第%d章的正文：<script>不执行</script>。' % n)
                repo.add_chapter('main', dict(n=n, title='独有章节%d' % n, prose=prose,
                                            events='', plan='', review='', state_hash='', chain='', summary='摘要', han=100))
        prose_refs = {row['prose'] for row in repo.headers('main')}
        with patch.object(SQLiteRepository, 'read_document', autospec=True, side_effect=SQLiteRepository.read_document) as reads:
            self.assertEqual(self.data('index')['html'].count('class="item"'), 100)
            self.assertFalse(prose_refs & {call.args[1] for call in reads.call_args_list})
            reads.reset_mock()
            chapter = self.data('chapter/103')['html']
            self.assertIn('第103章的正文：&lt;script&gt;', chapter)
            self.assertNotIn('<script>不执行</script>', chapter)
            self.assertEqual([call.args[1] for call in reads.call_args_list if call.args[1] in prose_refs],
                             [repo.chapter('main', 103)['prose']])
        self.assertEqual(self.data('index?offset=200')['html'].count('class="item"'), 5)
        self.assertEqual(self.data('index?q=205')['html'].count('class="item"'), 1)
        bookpage.write(repo, workspace=self.runtime.workspace)
        original = (self.project / 'book.html').read_bytes()
        book = repo.load()
        book['plans'] = {'large': '很长的设定' * 100000}
        repo.save(book)
        bookpage.write(repo, workspace=self.runtime.workspace)
        self.assertEqual((self.project / 'book.html').read_bytes(), original)
        self.assertLess(len(original), 40000)

    def test_only_known_read_routes_on_the_local_origin_are_served(self):
        database = tuple(self.runtime.repo.db.iterdump())
        for route in ('novel.sqlite3', '../novel.sqlite3', 'api/chapter/999', 'api/section/missing'):
            self.assertEqual(self.request(route)[0], 404, route)
        self.assertEqual(self.request('/api/index', absolute=True)[0], 404)
        self.assertEqual(self.request('api/index', headers={'Host': 'attacker.example'})[0], 403)
        self.assertEqual(self.request('api/index', headers={'Origin': 'http://attacker.example'})[0], 403)
        self.assertEqual(self.request('api/index?offset=-1')[0], 422)
        self.assertEqual(self.request('api/index?offset=no')[0], 400)
        self.assertEqual(self.request('api/index', method='POST')[0], 501)
        self.assertEqual(self.request(method='HEAD')[2], '')
        self.assertEqual(tuple(self.runtime.repo.db.iterdump()), database)

    def test_explicit_standalone_export_preserves_preview_entry(self):
        drive(self.runtime.app, until='write')
        self.runtime.app.submit(response(self.runtime.app))
        entry = (self.project / 'book.html').read_bytes()
        for output in (None, self.project / 'book.html'):
            with self.assertRaises(Error):
                self.runtime.html(output, standalone=True)
        output = self.project / 'offline.html'
        self.runtime.html(output, standalone=True)
        self.assertIn('id="read-1"', output.read_text(encoding='utf-8'))
        self.assertNotIn('fetch(', output.read_text(encoding='utf-8'))
        self.assertEqual((self.project / 'book.html').read_bytes(), entry)

    def test_cli_preview_has_a_usable_url_and_stops_on_interrupt(self):
        environment = {k: v for k, v in os.environ.items() if not k.startswith('NOVEL_')}
        process = subprocess.Popen([sys.executable, str(ROOT / 'scripts/novel.py'), '--project', str(self.project), 'preview'],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', env=environment)
        try:
            info = json.loads(process.stdout.readline())
            url = urlsplit(info['preview_url'])
            connection = HTTPConnection(url.netloc, timeout=5)
            connection.request('GET', url.path + 'api/index')
            self.assertEqual(connection.getresponse().status, 200)
            connection.close()
            process.send_signal(signal.SIGINT)
            output, error = process.communicate(timeout=5)
            self.assertEqual(process.returncode, 0, error)
            self.assertTrue(json.loads(output)['preview_stopped'])
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)

    def test_completed_preview_uses_frozen_snapshot_and_delivery_stays_small(self):
        app = self.runtime.app
        owner = app.run(finish=True, source='测试作者授权。')['owner']
        self.assertEqual(drive(app, owner)['action'], 'ready_to_complete')
        app.complete(owner)
        self.runtime.deliver()
        entry = (self.project / 'book.html').read_bytes()
        book = self.runtime.repo.load()
        book['contract']['title'] = '完本后投影改名'
        self.runtime.repo.save(book)
        self.assertEqual(self.data('section/contract')['title'], '夜班退件')
        self.assertIn('id="read-1"', self.data('chapter/1')['html'])
        self.assertNotIn('夜班退件', entry.decode('utf-8'))
        self.assertLess(len(entry), 40000)
