"""SQLite adapter and transaction boundary. No domain imports or hidden upgrades."""
from __future__ import annotations

import contextlib
import json
import os
import re
import sqlite3
import time
import uuid
from pathlib import Path
from .contracts import SCHEMA, digest, dump, require
from . import store_keys
from . import book_state

# The two documents this adapter writes for a branch's history index. They are declared once because
# the values are compared in three places here and mirrored by the in-memory adapter; a literal per
# site is how a schema rename turns into a silent integrity failure.
HISTORY_SCHEMA = 'novel-ledger.history/1'
HISTORY_PAGE_SCHEMA = 'novel-ledger.history-page/1'

DDL = '''
CREATE TABLE kv(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE documents(hash TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE tasks(id TEXT PRIMARY KEY, status TEXT NOT NULL, input TEXT NOT NULL, input_hash TEXT NOT NULL,
    result TEXT, result_hash TEXT, reviewer TEXT);
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
        self._after_commit_callbacks = None
        try:
            schema = self.db.execute("SELECT value FROM kv WHERE key='" + store_keys.SCHEMA_KEY + "'").fetchone()
            require(schema is not None and json.loads(schema['value']) == SCHEMA, 'schema', '不支持该数据库版本，禁止隐式转换。')
        except sqlite3.DatabaseError:
            self.db.close()
            require(False, 'schema', '此目录不是有效项目；保留原文件并选择新目录。')
        except BaseException:
            self.db.close()
            raise

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
            db.execute('INSERT INTO kv VALUES (?,?)', (store_keys.SCHEMA_KEY, dump(SCHEMA)))
            parts = book_state.split(book)
            references = {name: digest(value) for name, value in parts.items()}
            db.executemany('INSERT OR IGNORE INTO documents VALUES (?,?)',
                           [(references[name], dump(value)) for name, value in parts.items()])
            db.execute('INSERT INTO kv VALUES (?,?)', (store_keys.BOOK_ROOT, dump({'schema': book_state.BOOK_SCHEMA, 'parts': references})))
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

    @property
    def storage_paths(self):
        """Concrete storage files reserved by this adapter, including resolved aliases."""
        database = self.project / 'novel.sqlite3'
        return frozenset(Path(str(base) + suffix).resolve()
                         for base in (database, database.resolve())
                         for suffix in ('', '-wal', '-shm', '-journal'))

    @contextlib.contextmanager
    def transaction(self, preview=False):
        self.db.execute('BEGIN IMMEDIATE')
        callbacks = []
        self._after_commit_callbacks = callbacks
        try:
            yield self
            self.db.rollback() if preview else self.db.commit()
        except BaseException:
            self.db.rollback()
            raise
        finally:
            self._after_commit_callbacks = None
        # Delivery effects run outside the transaction: a failed callback must never
        # pretend the already committed database was rolled back.
        if not preview:
            for callback in callbacks:
                callback()

    def after_commit(self, callback):
        """Defer an external effect until commit; outside a transaction run it now."""
        if self._after_commit_callbacks is None:
            callback()
        else:
            self._after_commit_callbacks.append(callback)

    def get(self, key, default=None):
        row = self.db.execute('SELECT value FROM kv WHERE key=?', (key,)).fetchone()
        return json.loads(row['value']) if row else default

    def put(self, key, value):
        self.db.execute('INSERT OR REPLACE INTO kv VALUES (?,?)', (key, dump(value)))

    def load(self):
        root = self._book_root()
        return book_state.assemble({name: self.read_document(key) for name, key in root['parts'].items()})

    def load_part(self, name):
        require(name in book_state.PART_FIELDS, 'book_ownership', '未知项目分区。')
        root = self._book_root()
        value = self.read_document(root['parts'][name])
        require(isinstance(value, dict) and set(value) <= set(book_state.PART_FIELDS[name]),
                'book_integrity', '项目分区字段归属不符。', {'part': name})
        return value

    def _book_root(self):
        root = self.get(store_keys.BOOK_ROOT)
        require(isinstance(root, dict) and root.get('schema') == book_state.BOOK_SCHEMA
                and isinstance(root.get('parts'), dict) and set(root['parts']) == set(book_state.PART_FIELDS),
                'book_integrity', '项目分区入口无效，禁止隐式转换。')
        return root

    def save(self, book):
        parts = {name: self.document(value) for name, value in book_state.split(book).items()}
        self.put(store_keys.BOOK_ROOT, {'schema': book_state.BOOK_SCHEMA, 'parts': parts})

    def prune(self):
        """Delete immutable documents no live record can reach, then reclaim the space.

        Documents are content addressed and written again on every commit, so superseded
        partition snapshots stay behind as garbage. Reachability is computed from every
        live cell that can name a document and then followed transitively, so anything
        removed is unreachable by construction.
        """
        keep, pending = set(), []

        def scan(value):
            if value is None:
                return
            text = value if isinstance(value, str) else dump(value)
            for token in re.findall(r'[0-9a-f]{64}', text):
                if token not in keep:
                    keep.add(token)
                    pending.append(token)

        for (value,) in self.db.execute('SELECT value FROM kv').fetchall():
            scan(value)
        for table in ('tasks', 'chapters', 'journal'):
            for row in self.db.execute('SELECT * FROM ' + table).fetchall():
                for cell in tuple(row):
                    scan(cell)
        while pending:
            key = pending.pop()
            row = self.db.execute('SELECT value FROM documents WHERE hash=?', (key,)).fetchone()
            if row is not None:
                scan(row[0])
        removed, kept = 0, 0
        for (key,) in self.db.execute('SELECT hash FROM documents').fetchall():
            if key in keep:
                kept += 1
            else:
                self.db.execute('DELETE FROM documents WHERE hash=?', (key,))
                removed += 1
        self.db.execute('VACUUM')
        # Only some reachable digests are document hashes: task input hashes and chapter
        # state hashes share the shape, so both counts are reported separately.
        return {'reachable_hashes': len(keep), 'documents_kept': kept, 'documents_removed': removed}

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

    def task_rows(self):
        """One light row per task ever dispatched, in dispatch order.

        The sanctioned read-only view of task lifecycle: a live reviewer needing "which tasks
        exist and what happened to them" opened the SQLite file with a scratch script, because
        no command answered that question.
        """
        rows = []
        for row in self.db.execute('SELECT id, status, reviewer, input FROM tasks ORDER BY rowid'):
            work = json.loads(row['input'])
            rows.append({'id': row['id'], 'status': row['status'], 'stage': work.get('stage'),
                         'chapter': work.get('chapter'), 'scope': work.get('scope'),
                         'session': row['reviewer']})
        return rows

    def task(self, task_id):
        row = self.db.execute('SELECT * FROM tasks WHERE id=?', (task_id,)).fetchone()
        require(row is not None, 'task', '任务不存在。')
        result = dict(row)
        for key in ('input', 'result'):
            result[key] = json.loads(result[key]) if result[key] else None
        require(digest(result['input']) == result['input_hash'], 'task_integrity', '冻结任务被修改。')
        return result

    def add_task(self, work):
        ident = uuid.uuid4().hex
        self.db.execute('INSERT INTO tasks(id,status,input,input_hash) VALUES (?,\'pending\',?,?)', (ident, dump(work), digest(work)))
        return self.task(ident)

    def finish_task(self, task_id, result):
        self.db.execute("UPDATE tasks SET status='done',result=?,result_hash=? WHERE id=?", (dump(result), digest(result), task_id))

    def cancel_pending(self, reason):
        row = self.db.execute("SELECT id FROM tasks WHERE status='pending'").fetchone()
        self.db.execute("UPDATE tasks SET status='cancelled' WHERE status='pending'")
        task_id = row['id'] if row else None
        self.record('cancel', {'reason': reason, 'task': task_id})
        return task_id

    def headers(self, branch):
        return [dict(r) for r in self.db.execute('SELECT * FROM chapters WHERE branch=? ORDER BY n', (branch,))]

    def history_snapshot(self, branch):
        """Reuse content-addressed chapter pages; the mutable head is only a dispatch cache.

        No schema migration is needed: pages use documents and heads use kv. Existing
        branches build once, then only appended chapters are indexed. Tasks freeze the
        returned value and never consult this mutable cache when recalling sources.
        """
        cache_key = store_keys.history_head(branch)
        cached = self.get(cache_key)
        snapshot = cached or {'schema': HISTORY_SCHEMA, 'head': None,
                                         'through': 0, 'chain': 'genesis'}
        self._validate_history(snapshot)
        if snapshot['through']:
            row = self.chapter(branch, snapshot['through'])
            page = self.read_document(snapshot['head'])
            require(row['chain'] == snapshot['chain'] == page['chain'] and page['n'] == snapshot['through'],
                    'history_integrity', '历史目录缓存与章节链不一致；不能用缓存覆盖正式历史。')
        rows = self.db.execute('SELECT * FROM chapters WHERE branch=? AND n>? ORDER BY n',
                               (branch, snapshot['through'])).fetchall()
        for row in rows:
            require(row['n'] == snapshot['through'] + 1, 'history_integrity', '历史目录的章节不连续。')
            page = {'schema': HISTORY_PAGE_SCHEMA, 'previous': snapshot['head'],
                    **{k: row[k] for k in ('n', 'prose', 'events', 'summary', 'chain')}}
            snapshot = {'schema': HISTORY_SCHEMA, 'head': self.document(page),
                        'through': row['n'], 'chain': row['chain']}
        if snapshot != cached:
            self.put(cache_key, snapshot)
        return snapshot

    def history_pages(self, snapshot, before=None):
        """Walk frozen pages newest first, verifying every page that is actually visited."""
        self._validate_history(snapshot)
        ident, number = snapshot['head'], snapshot['through']
        while ident:
            page = self.read_document(ident)
            require(page.get('schema') == HISTORY_PAGE_SCHEMA and page['n'] == number
                    and (number != snapshot['through'] or page['chain'] == snapshot['chain'])
                    and bool(page['previous']) == (number > 1), 'history_integrity', '冻结历史目录链不一致。')
            if before is None or number < before:
                yield ident, page
            ident, number = page['previous'], number - 1
        require(number == 0, 'history_integrity', '冻结历史目录缺少章节。')

    @staticmethod
    def _validate_history(snapshot):
        require(isinstance(snapshot, dict) and snapshot.get('schema') == HISTORY_SCHEMA
                and type(snapshot.get('through')) is int and snapshot['through'] >= 0
                and isinstance(snapshot.get('chain'), str)
                and (snapshot.get('head') is None and snapshot['through'] == 0 and snapshot['chain'] == 'genesis'
                     or isinstance(snapshot.get('head'), str) and len(snapshot['head']) == 64 and snapshot['through'] > 0),
                'history_integrity', '冻结历史目录入口或版本无效。')

    def memory_rows(self, page):
        """Search metadata is derived on demand from this page's immutable event source."""
        rows = []
        for event in self.read_document(page['events']):
            entities = list(event.get('subjects', []))
            for key in ('entity', 'from', 'to', 'holder'):
                ident = event.get(key)
                if isinstance(ident, dict):
                    ident = ident.get('id')
                if isinstance(ident, str):
                    entities.append(ident)
            rows.append({'chapter': page['n'], 'entities': sorted(set(entities)), 'node': event.get('node'),
                         'topic': event.get('topic'), 'topics': event.get('topics', []) if event.get('hook_links_version') == 1 else [],
                         'thread': event.get('thread', event.get('line')), 'op': event['op'], 'evidence': event['evidence']})
        return rows

    def chapter(self, branch, chapter):
        row = self.db.execute('SELECT * FROM chapters WHERE branch=? AND n=?', (branch, chapter)).fetchone()
        require(row is not None, 'chapter', '正式章节不存在。')
        return dict(row)

    def add_chapter(self, branch, row):
        self.db.execute('INSERT INTO chapters VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                        (branch, row['n'], row['title'], row['prose'], row['events'], row['plan'], row['review'], row['state_hash'], row['chain'], row['summary'], row['han']))

    def fork(self, parent, first):
        snapshot = self.history_snapshot(parent)
        prefix = {'schema': HISTORY_SCHEMA, 'head': None, 'through': 0, 'chain': 'genesis'}
        if first > 1:
            for ident, page in self.history_pages(snapshot):
                if page['n'] == first - 1:
                    prefix.update(head=ident, through=page['n'], chain=page['chain'])
                    break
            require(prefix['through'] == first - 1, 'history_integrity', '修订分支缺少冻结前缀。')
        ident = 'revision-' + uuid.uuid4().hex[:12]
        self.db.execute('INSERT INTO branches VALUES (?,?,?,\'candidate\')', (ident, parent, first))
        self.db.execute('INSERT INTO chapters SELECT ?,n,title,prose,events,plan,review,state_hash,chain,summary,han FROM chapters WHERE branch=? AND n<?', (ident, parent, first))
        self.put(store_keys.history_head(ident), prefix)
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

    def read_names(self, task_id):
        """Record names this task has already been handed, newest first, without duplicates."""
        seen = []
        rows = self.db.execute("SELECT value FROM journal WHERE action='read' ORDER BY id").fetchall()
        for row in rows:
            record = json.loads(row['value'])
            if record.get('task') != task_id:
                continue
            for name in record.get('records') or ():
                if name not in seen:
                    seen.append(name)
        return seen

    def usage(self):
        rows = self.db.execute('SELECT input,result FROM tasks').fetchall()
        reads = self.db.execute("SELECT value FROM journal WHERE action='read'").fetchall()
        return {'tasks': len(rows), 'task_input_chars': sum(len(r['input']) for r in rows),
                'accepted_receipt_chars': sum(len(r['result'] or '') for r in rows),
                'supplemental_read_chars': sum(store_keys.read_chars(json.loads(r['value'])) for r in reads),
                'attempted_receipt_chars': None, 'billed_tokens': None,
                'basis': '仅冻结信封、已接受回执和 CLI 实际读取；不含宿主历史、工具包装与缓存计费。'}
