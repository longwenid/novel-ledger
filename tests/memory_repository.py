"""A complete test repository using isolated Python values rather than a database."""
from contextlib import contextmanager
from copy import deepcopy
import re

from novel_ledger import book_state
from novel_ledger.contracts import digest, dump, require


class MemoryRepository:
    """The application port implemented without project paths, connections or files."""

    def __init__(self, book):
        self._values = {'book': deepcopy(book)}
        self._documents = {}
        self._tasks = {}
        self._sessions = {}
        self._branches = {'main': {'parent': None, 'status': 'active', 'chapters': {}}}
        self._journal = []
        self._sequence = 0
        self._callbacks = None

    def close(self):
        pass

    def snapshot(self):
        """Expose a detached transaction image for atomicity assertions."""
        return deepcopy((self._values, self._documents, self._tasks, self._sessions,
                         self._branches, self._journal, self._sequence))

    @contextmanager
    def transaction(self, preview=False):
        require(self._callbacks is None, 'transaction', 'Nested test transactions are unsupported.')
        before = self.snapshot()
        callbacks = []
        self._callbacks = callbacks
        try:
            yield self
        except BaseException:
            self._restore(before)
            raise
        else:
            if preview:
                self._restore(before)
        finally:
            self._callbacks = None
        if not preview:
            for callback in callbacks:
                callback()

    def _restore(self, before):
        (self._values, self._documents, self._tasks, self._sessions,
         self._branches, self._journal, self._sequence) = before

    def after_commit(self, callback):
        if self._callbacks is None:
            callback()
        else:
            self._callbacks.append(callback)

    def get(self, key, default=None):
        return deepcopy(self._values.get(key, default))

    def put(self, key, value):
        self._values[key] = deepcopy(value)

    def load(self):
        return self.get('book')

    def load_part(self, name):
        require(name in book_state.PART_FIELDS, 'book_ownership', 'Unknown book partition.')
        return book_state.split(self.load())[name]

    def save(self, book):
        book_state.split(book)  # Keep field ownership validation at this storage boundary.
        self.put('book', book)

    def document(self, value):
        key = digest(value)
        self._documents.setdefault(key, deepcopy(value))
        return key

    def read_document(self, key):
        require(key in self._documents, 'source', 'Frozen source does not exist.')
        value = deepcopy(self._documents[key])
        require(digest(value) == key, 'source_integrity', 'Frozen source hash differs.')
        return value

    def prune(self):
        """Keep the observable reclamation contract of the SQLite adapter."""
        keep, pending = set(), []

        def scan(value):
            for token in re.findall(r'[0-9a-f]{64}', value if isinstance(value, str) else str(value)):
                if token not in keep:
                    keep.add(token)
                    pending.append(token)

        for value in list(self._values.values()):
            scan(value)
        for group in (self._tasks, self._journal):
            for row in (list(group.values()) if isinstance(group, dict) else list(group)):
                scan(row)
        for branch in self._branches.values():
            for row in branch['chapters'].values():
                scan(row)
        while pending:
            key = pending.pop()
            if key in self._documents:
                scan(self._documents[key])
        removed = 0
        for key in list(self._documents):
            if key not in keep:
                del self._documents[key]
                removed += 1
        return {'reachable_hashes': len(keep), 'documents_kept': len(self._documents),
                'documents_removed': removed}

    def pending(self):
        return next((self.task(t['id']) for t in self._tasks.values() if t['status'] == 'pending'), None)

    def task(self, task_id):
        require(task_id in self._tasks, 'task', 'Task does not exist.')
        task = deepcopy(self._tasks[task_id])
        require(digest(task['input']) == task['input_hash'], 'task_integrity', 'Frozen task hash differs.')
        require(task['first_read'] is None or digest(task['first_read']) == task['first_read_hash'],
                'first_read_integrity', 'Frozen first read hash differs.')
        return task

    def _next_id(self, prefix):
        self._sequence += 1
        return prefix + str(self._sequence)

    def add_task(self, work):
        require(self.pending() is None, 'task', 'Only one pending task is allowed.')
        ident = self._next_id('task-')
        self._tasks[ident] = {'id': ident, 'status': 'pending', 'input': deepcopy(work),
                              'input_hash': digest(work), 'result': None, 'result_hash': None,
                              'first_read': None, 'first_read_hash': None, 'reviewer': None}
        return self.task(ident)

    def seal(self, task_id, session, first_read):
        self.task(task_id)
        self._tasks[task_id].update(first_read=deepcopy(first_read),
                                    first_read_hash=digest(first_read), reviewer=session)

    def finish_task(self, task_id, result):
        self.task(task_id)
        self._tasks[task_id].update(status='done', result=deepcopy(result), result_hash=digest(result))

    def cancel_pending(self, reason):
        task = self.pending()
        ident = task['id'] if task else None
        if task:
            self._tasks[ident]['status'] = 'cancelled'
        self.record('cancel', {'reason': reason, 'task': ident})
        return ident

    def headers(self, branch):
        return deepcopy([row for _, row in sorted(self._branches[branch]['chapters'].items())])

    def chapter(self, branch, chapter):
        row = self._branches[branch]['chapters'].get(chapter)
        require(row is not None, 'chapter', 'Accepted chapter does not exist.')
        return deepcopy(row)

    def add_chapter(self, branch, row):
        chapters = self._branches[branch]['chapters']
        require(row['n'] not in chapters, 'chapter', 'Accepted chapter already exists.')
        chapters[row['n']] = deepcopy(row)

    def history_snapshot(self, branch):
        previous = None
        rows = self.headers(branch)
        for row in rows:
            previous = self.document({'schema': 'novel-ledger.history-page/1', 'previous': previous,
                                      **{key: row[key] for key in ('n', 'prose', 'events', 'summary', 'chain')}})
        return {'schema': 'novel-ledger.history/1', 'head': previous,
                'through': rows[-1]['n'] if rows else 0,
                'chain': rows[-1]['chain'] if rows else 'genesis'}

    def history_pages(self, snapshot, before=None):
        require(snapshot.get('schema') == 'novel-ledger.history/1', 'history_integrity', 'Unknown history snapshot.')
        ident, number = snapshot['head'], snapshot['through']
        while ident:
            page = self.read_document(ident)
            require(page['schema'] == 'novel-ledger.history-page/1' and page['n'] == number
                    and (number != snapshot['through'] or page['chain'] == snapshot['chain'])
                    and bool(page['previous']) == (number > 1), 'history_integrity', 'Broken history page.')
            if before is None or number < before:
                yield ident, page
            ident, number = page['previous'], number - 1
        require(number == 0, 'history_integrity', 'Missing history page.')

    def memory_rows(self, page):
        rows = []
        for event in self.read_document(page['events']):
            entities = set(event.get('subjects', []))
            for key in ('entity', 'from', 'to', 'holder'):
                ident = event.get(key)
                if isinstance(ident, dict):
                    ident = ident.get('id')
                if isinstance(ident, str):
                    entities.add(ident)
            rows.append({'chapter': page['n'], 'entities': sorted(entities), 'node': event.get('node'),
                         'topic': event.get('topic'),
                         'topics': event.get('topics', []) if event.get('hook_links_version') == 1 else [],
                         'thread': event.get('thread', event.get('line')), 'op': event['op'],
                         'evidence': deepcopy(event['evidence'])})
        return rows

    def fork(self, parent, first):
        ident = self._next_id('revision-')
        self._branches[ident] = {'parent': parent, 'status': 'candidate',
                                 'chapters': {r['n']: r for r in self.headers(parent) if r['n'] < first}}
        return ident

    def promote(self, branch, parent):
        self._branches[parent]['status'] = 'archived'
        self._branches[branch]['status'] = 'active'

    def session_task(self, session):
        return self._sessions.get(session)

    def bind_session(self, session, task_id):
        self._sessions.setdefault(session, task_id)

    def record(self, action, value):
        self._journal.append({'action': action, 'value': deepcopy(value)})

    def usage(self):
        return {'tasks': len(self._tasks),
                'task_input_chars': sum(len(dump(t['input'])) for t in self._tasks.values()),
                'accepted_receipt_chars': sum(len(dump(t['result'])) for t in self._tasks.values() if t['result']),
                'supplemental_read_chars': sum(row['value']['chars'] for row in self._journal if row['action'] == 'read'),
                'attempted_receipt_chars': None, 'billed_tokens': None, 'basis': 'In-memory test observations.'}
