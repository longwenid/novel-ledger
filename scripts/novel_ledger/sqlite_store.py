"""SQLite adapter and transaction boundary. No domain imports or hidden upgrades."""
from __future__ import annotations

import contextlib
import json
import os
import sqlite3
import time
import uuid
from pathlib import Path
from .contracts import FORM_ARTIFACTS, SCHEMA, digest, dump, require

DDL = '''
CREATE TABLE kv(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE documents(hash TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE tasks(id TEXT PRIMARY KEY, status TEXT NOT NULL, input TEXT NOT NULL, input_hash TEXT NOT NULL,
    result TEXT, result_hash TEXT, first_read TEXT, first_read_hash TEXT, reviewer TEXT);
CREATE UNIQUE INDEX one_pending ON tasks(status) WHERE status='pending';
CREATE TABLE sessions(id TEXT PRIMARY KEY, task TEXT NOT NULL);
CREATE TABLE branches(id TEXT PRIMARY KEY, parent TEXT, first INTEGER NOT NULL, status TEXT NOT NULL);
CREATE TABLE chapters(branch TEXT NOT NULL, n INTEGER NOT NULL, title TEXT NOT NULL, prose TEXT NOT NULL,
    events TEXT NOT NULL, plan TEXT NOT NULL, review TEXT NOT NULL, state_hash TEXT NOT NULL,
    chain TEXT NOT NULL, summary TEXT NOT NULL, han INTEGER NOT NULL, PRIMARY KEY(branch,n));
CREATE TABLE journal(id INTEGER PRIMARY KEY, at REAL NOT NULL, action TEXT NOT NULL, value TEXT NOT NULL);
'''


class SQLiteRepository:
    def __init__(self, project):
        self.project = Path(project).resolve()
        path = self.project / 'novel.sqlite3'
        require(path.is_file(), 'project', '项目未初始化。', {'recover': '使用 init --project 路径 --contract 作者约定.json 建立新项目。'})
        self.db = sqlite3.connect(str(path), timeout=10, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
        try:
            schema = self.db.execute("SELECT value FROM kv WHERE key='schema'").fetchone()
            require(schema is not None and json.loads(schema['value']) == SCHEMA, 'schema', '不支持该数据库版本，禁止隐式转换。')
        except sqlite3.DatabaseError:
            self.db.close()
            require(False, 'schema', '此目录不是有效项目；保留原文件并选择新目录。')

    @classmethod
    def initialize(cls, project, book):
        project = Path(project).resolve()
        project.mkdir(parents=True, exist_ok=True)
        target = project / 'novel.sqlite3'
        require(not target.exists(), 'exists', '项目已存在，不覆盖。')
        temporary = project / ('.novel-' + uuid.uuid4().hex + '.sqlite3')
        db = sqlite3.connect(str(temporary))
        try:
            db.executescript(DDL)
            db.execute('INSERT INTO kv VALUES (?,?)', ('schema', dump(SCHEMA)))
            db.execute('INSERT INTO kv VALUES (?,?)', ('book', dump(book)))
            db.execute("INSERT INTO branches VALUES ('main',NULL,1,'active')")
            db.commit()
            db.close()
            # Hard link publishes atomically and refuses an existing destination.
            try:
                os.link(str(temporary), str(target))
            except FileExistsError:
                require(False, 'exists', '另一个初始化已经完成，不覆盖。')
        finally:
            db.close()
            temporary.unlink(missing_ok=True)
        return cls(project)

    def close(self):
        self.db.close()

    @contextlib.contextmanager
    def transaction(self, preview=False):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield self
        except BaseException:
            self.db.rollback()
            raise
        else:
            self.db.rollback() if preview else self.db.commit()

    def get(self, key, default=None):
        row = self.db.execute('SELECT value FROM kv WHERE key=?', (key,)).fetchone()
        return json.loads(row['value']) if row else default

    def put(self, key, value):
        self.db.execute('INSERT OR REPLACE INTO kv VALUES (?,?)', (key, dump(value)))

    def load(self):
        return self.get('book')

    def save(self, book):
        self.put('book', book)

    def document(self, value):
        key = digest(value)
        self.db.execute('INSERT OR IGNORE INTO documents VALUES (?,?)', (key, dump(value)))
        return key

    def read_document(self, key):
        row = self.db.execute('SELECT value FROM documents WHERE hash=?', (key,)).fetchone()
        require(row is not None, 'source', '冻结来源不存在。')
        value = json.loads(row['value'])
        require(digest(value) == key, 'source_integrity', '冻结来源哈希不匹配。')
        return value

    def pending(self):
        row = self.db.execute("SELECT id FROM tasks WHERE status='pending'").fetchone()
        return self.task(row['id']) if row else None

    def task(self, task_id):
        row = self.db.execute('SELECT * FROM tasks WHERE id=?', (task_id,)).fetchone()
        require(row is not None, 'task', '任务不存在。')
        result = dict(row)
        for key in ('input', 'result', 'first_read'):
            result[key] = json.loads(result[key]) if result[key] else None
        require(digest(result['input']) == result['input_hash'], 'task_integrity', '冻结任务被修改。')
        require(result['first_read'] is None or digest(result['first_read']) == result['first_read_hash'], 'first_read_integrity', '冻结首读记录被修改。')
        return result

    def add_task(self, work):
        ident = uuid.uuid4().hex
        self.db.execute('INSERT INTO tasks(id,status,input,input_hash) VALUES (?,\'pending\',?,?)', (ident, dump(work), digest(work)))
        return self.task(ident)

    def seal(self, task_id, session, first_read):
        self.db.execute('UPDATE tasks SET first_read=?, first_read_hash=?, reviewer=? WHERE id=?',
                        (dump(first_read), digest(first_read), session, task_id))

    def finish_task(self, task_id, result):
        self.db.execute("UPDATE tasks SET status='done',result=?,result_hash=? WHERE id=?", (dump(result), digest(result), task_id))

    def cancel_pending(self, reason):
        row = self.db.execute("SELECT id FROM tasks WHERE status='pending'").fetchone()
        self.db.execute("UPDATE tasks SET status='cancelled' WHERE status='pending'")
        if row:
            # The dispatcher retires the derived view when it cancels; the store owns the row only.
            self.retire(str(self.project / 'work' / row['id']))
        self.record('cancel', {'reason': reason, 'task': row['id'] if row else None})

    def retire(self, base):
        for name in FORM_ARTIFACTS:
            (Path(base) / name).unlink(missing_ok=True)

    def headers(self, branch):
        return [dict(r) for r in self.db.execute('SELECT * FROM chapters WHERE branch=? ORDER BY n', (branch,))]

    def chapter(self, branch, chapter):
        row = self.db.execute('SELECT * FROM chapters WHERE branch=? AND n=?', (branch, chapter)).fetchone()
        require(row is not None, 'chapter', '正式章节不存在。')
        return dict(row)

    def add_chapter(self, branch, row):
        self.db.execute('INSERT INTO chapters VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                        (branch, row['n'], row['title'], row['prose'], row['events'], row['plan'], row['review'], row['state_hash'], row['chain'], row['summary'], row['han']))

    def fork(self, parent, first):
        ident = 'revision-' + uuid.uuid4().hex[:12]
        self.db.execute('INSERT INTO branches VALUES (?,?,?,\'candidate\')', (ident, parent, first))
        self.db.execute('INSERT INTO chapters SELECT ?,n,title,prose,events,plan,review,state_hash,chain,summary,han FROM chapters WHERE branch=? AND n<?', (ident, parent, first))
        return ident

    def promote(self, branch, parent):
        self.db.execute("UPDATE branches SET status='archived' WHERE id=?", (parent,))
        self.db.execute("UPDATE branches SET status='active' WHERE id=?", (branch,))

    def session_task(self, session):
        row = self.db.execute('SELECT task FROM sessions WHERE id=?', (session,)).fetchone()
        return row['task'] if row else None

    def bind_session(self, session, task_id):
        self.db.execute('INSERT OR IGNORE INTO sessions VALUES (?,?)', (session, task_id))

    def record(self, action, value):
        self.db.execute('INSERT INTO journal(at,action,value) VALUES (?,?,?)', (time.time(), action, dump(value)))
