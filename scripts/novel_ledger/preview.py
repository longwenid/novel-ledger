"""Loopback-only preview transport, backed by fresh read-only SQLite snapshots."""
from __future__ import annotations

import json
import secrets
import signal
import sqlite3
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from . import bookpage
from .contracts import Error, require
from .sqlite_store import SQLiteRepository


def create_server(project, port=0, entry=None):
    project = Path(project).expanduser().resolve()
    require(0 <= port <= 65535, 'preview', '预览端口须在 0 到 65535 之间。')
    repo = SQLiteRepository(project, readonly=True)
    repo.close()
    prefix = '/' + secrets.token_urlsafe(24) + '/'
    shell = bookpage.live_shell(project, entry).encode('utf-8')

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def respond(self, status, body, content_type='application/json; charset=utf-8'):
            if not isinstance(body, bytes):
                body = json.dumps(body, ensure_ascii=False, allow_nan=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(body)

        def do_HEAD(self):
            self.do_GET()

        def do_GET(self):
            origin = 'http://' + self.server.authority
            if (self.headers.get('Host') != self.server.authority or
                    self.headers.get('Origin', origin) != origin):
                return self.respond(403, {'message': '仅允许本机预览页面读取。'})
            url = urlsplit(self.path)
            if not url.path.startswith(prefix):
                return self.respond(404, {'message': '预览地址不存在，请使用启动命令返回的地址。'})
            path = url.path[len(prefix):]
            if path in ('', 'book.html'):
                return self.respond(200, shell, 'text/html; charset=utf-8')
            query = parse_qs(url.query)
            if path.startswith('api/section/') and path[12:] in dict(bookpage.SECTIONS):
                kind, value = 'section', path[12:]
            elif path == 'api/index':
                kind, value = 'index', None
            elif (path.startswith('api/chapter/') and len(path[12:]) <= 10
                  and path[12:].isascii() and path[12:].isdigit()):
                kind, value = 'chapter', int(path[12:])
            else:
                return self.respond(404, {'message': '预览内容不存在。'})
            try:
                offset = int(query.get('offset', ['0'])[0])
                text = query.get('q', [''])[0]
                require(offset >= 0 and len(text) <= 200, 'preview', '目录查询参数无效。')
                repo = SQLiteRepository(project, readonly=True)
                try:
                    # One response must not mix state from two writer commits.
                    repo.db.execute('BEGIN')
                    data = bookpage.preview_fragment(repo, kind, value, offset=offset, query=text)
                finally:
                    repo.close()
                return self.respond(200, data)
            except Error as exc:
                return self.respond(404 if exc.code == 'chapter' else 422, exc.as_dict())
            except ValueError:
                return self.respond(400, {'message': '目录查询参数无效。'})
            except (OSError, sqlite3.DatabaseError):
                return self.respond(503, {'message': '暂时无法读取作品账本，请稍后重试。'})

    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.authority = '127.0.0.1:%d' % server.server_address[1]
    server.url = 'http://' + server.authority + prefix
    return server


def serve(project, port=0, open_browser=False, entry=None):
    if sys.platform == 'win32':
        # A process launched in a fresh process group (how hosts start helpers) has
        # CTRL_C_EVENT disabled by Windows; CTRL_BREAK still arrives, so map it to the
        # same graceful stop instead of the default hard termination.
        def _raise_interrupt(_signum, _frame):
            raise KeyboardInterrupt()
        signal.signal(signal.SIGBREAK, _raise_interrupt)
    with create_server(project, port, entry) as server:
        info = {'preview_url': server.url, 'readonly': True, 'stop': 'Ctrl+C'}
        print(json.dumps(info, ensure_ascii=False), flush=True)
        if open_browser:
            webbrowser.open(server.url)
        try:
            server.serve_forever(poll_interval=0.2)
        except KeyboardInterrupt:
            pass
    return {'preview_stopped': True}
