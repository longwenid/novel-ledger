"""Local composition root; concrete adapters meet only at this boundary.

Embedded users may instantiate Application with different ports directly. This
factory preserves the desktop/CLI setup without making the application discover
paths, concrete storage, clocks, or the caller's environment.
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from .application import Application
from . import bookpage, context, delivery, host, unattended, workflow
from .contracts import require
from .presentation import LocalPresentation
from .sqlite_store import SQLiteRepository
from .workspace import LocalWorkspace


def local_workspace(repo: SQLiteRepository):
    return LocalWorkspace(repo.project, protected_paths=repo.storage_paths)


def local_application(repo: SQLiteRepository, entry=None, *, workspace=None):
    workspace = workspace if workspace is not None else local_workspace(repo)
    entry = entry or Path(__file__).resolve().parents[1] / 'novel.py'
    return Application(repo, compile_task=lambda book, job: context.build(repo, book, job),
                       presentation=LocalPresentation(repo, workspace, entry),
                       clock=time.time, new_id=lambda: uuid.uuid4().hex)


class LocalRuntime:
    """The local client's lifecycle and output operations, assembled in one place."""
    def __init__(self, repo: SQLiteRepository, entry=None):
        self.repo = repo
        self.workspace = local_workspace(repo)
        self.app = local_application(repo, entry, workspace=self.workspace)

    def book_view(self):
        return bookpage.write(self.repo, workspace=self.workspace)

    def deliver(self):
        result = delivery.deliver_completion(self.repo, bookpage.render, workspace=self.workspace)
        self.app.record_delivery(result)
        return result

    def export(self, output=None, format='html'):
        return delivery.export_book(self.repo, output, format, workspace=self.workspace)

    def html(self, output=None):
        return bookpage.write(self.repo, output, workspace=self.workspace)

    def host_step(self, command, owner=None, timeout=300):
        return host.step(self.app, command, owner, timeout)

    def host_loop(self, command, owner, limit=100, timeout=300):
        return host.loop(self.app, command, owner, limit, timeout)

    def watch(self, owner, steps=1, poll=20.0, idle_limit=1800.0):
        """Unattended progression with a local dispatch journal.

        The engine waits for externally executed workers itself; each dispatch it oversees is
        appended to work/watch.jsonl so a thin non-LLM dispatcher (or a later reader) can see
        what was handed out and when, without re-deriving it from the ledger.
        """
        log = self.workspace.artifact_path(self.workspace.project / 'work' / 'watch.jsonl')

        def on_dispatch(row):
            with open(log, 'a', encoding='utf-8') as stream:
                stream.write(json.dumps({'ts': time.time(), **row}, ensure_ascii=False) + '\n')

        return unattended.watch(self.app, owner, steps=steps, poll=poll, idle_limit=idle_limit,
                                on_dispatch=on_dispatch)

    def close(self):
        self.repo.close()


def open_local_runtime(project, *, initialize=False, contract=None, source='', entry=None):
    if initialize:
        book = workflow.new_book(contract, source) if contract is not None else workflow.preparing_book(source, guided=True)
        repo = SQLiteRepository.initialize(project, book)
    else:
        require(contract is None, 'contract', '已有项目不接受初始化约定。')
        repo = SQLiteRepository(project)
    try:
        return LocalRuntime(repo, entry)
    except BaseException:
        repo.close()
        raise
