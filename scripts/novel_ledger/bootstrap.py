"""Local composition root; concrete adapters meet only at this boundary.

Embedded users may instantiate Application with different ports directly. This
factory preserves the desktop/CLI setup without making the application discover
paths, concrete storage, clocks, or the caller's environment.
"""
from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path
from .application import Application
from . import bookpage, context, delivery, host, preview, runtime_install, unattended, workflow
from .contracts import require
from .presentation import LocalPresentation
from .sqlite_store import SQLiteRepository
from .workspace import LocalWorkspace
from .build_info import fingerprint


def local_workspace(repo: SQLiteRepository):
    return LocalWorkspace(repo.project, protected_paths=repo.storage_paths)


def local_application(repo: SQLiteRepository, entry=None, *, workspace=None, authority=None):
    workspace = workspace if workspace is not None else local_workspace(repo)
    entry = entry or Path(__file__).resolve().parents[1] / 'novel.py'
    root = Path(entry).resolve().parent.parent
    if (root / runtime_install.MANIFEST).exists():
        runtime_install.verify(root)
    build = fingerprint()

    def compile_task(book, job):
        return {**context.build(repo, book, job), 'build': build}

    return Application(repo, compile_task=compile_task,
                       presentation=LocalPresentation(repo, workspace, entry),
                       clock=time.time, new_id=lambda: uuid.uuid4().hex, authority=authority, build_info=build)


class LocalRuntime:
    """The local client's lifecycle and output operations, assembled in one place."""
    def __init__(self, repo: SQLiteRepository, entry=None):
        self.repo = repo
        self.entry = entry
        self.workspace = local_workspace(repo)
        self.app = local_application(repo, entry, workspace=self.workspace)

    def book_view(self):
        return bookpage.write(self.repo, workspace=self.workspace, entry=self.entry)

    def diagnose(self):
        result = self.app.diagnose()
        entry = Path(self.entry or Path(__file__).resolve().parents[1] / 'novel.py').resolve()
        base = [sys.executable, str(entry), '--project', str(self.repo.project)]
        owner = result['controller']['owner']
        controlled = base + (['--owner', owner] if owner else [])
        commands = {'diagnose': base + ['diagnose'], 'status': base + ['status']}
        if result['next_action'] == 'advance':
            commands['advance'] = controlled + ['advance', '--compact']
        if owner and result['controller']['lease_valid'] and result['next_action'] in (
                'verify_existing_worker', 'review_in_progress'):
            commands['watch'] = controlled + ['watch']
        task = result['task']
        if task:
            directory = self.repo.project / 'work' / task['task_id']
            task['paths'] = {name: str(directory / filename) for name, filename in
                             (('task', 'task.json'), ('dispatch', 'dispatch.md'), ('result', 'result.json'))}
        pinned = (entry.parent.parent / runtime_install.MANIFEST).is_file()
        result.update(runtime={'root': str(entry.parent.parent), 'entry': str(entry), 'pinned': pinned},
                      project_path=str(self.repo.project), commands=commands,
                      handoff={'resume': commands['diagnose'], 'recheck_before_action': True,
                               'resets_model_history': False,
                               'note': '宿主在安全交接点压缩或切换主控上下文；保留原授权与owner，先核实原执行者。'})
        if task and not result['engine']['matches']:
            result['engine_recovery'] = {
                'task_id': task['task_id'], 'input_hash': task['input_hash'],
                'preserved_result_path': task['paths']['result'],
                'restore_release': {'command': 'pin-engine',
                                    'required_inputs': ['matching_release_ref_or_runtime', 'new_runtime_directory']},
                'upgrade_release': {'prepare': '先不带--project将已选择的新版本固定到开发树外的新目录。',
                                    'from_pinned_entry_arguments': controlled[2:] + [
                                        'recover-engine', '--task', task['task_id'], '--input-hash', task['input_hash']],
                                    'required_inputs': ['pinned_entry', 'author_upgrade_source'] + (
                                        ['worker_stopped_confirmation'] if result['worker']['identity_registered'] else [])},
                'note': '准备固定副本不授权升级；实际恢复仍验证准确任务、作者授权及原执行者停止。'}
            if task['status'] != 'pending':
                result['engine_recovery'].pop('upgrade_release')
                result['engine_recovery']['note'] = '本组正在接续；先恢复匹配的固定入口并核实原执行者，不对已完成任务执行recover-engine。'
        if not pinned:
            result['runtime']['pin'] = {
                'arguments': base + ['pin-engine'], 'required_inputs': ['output'],
                'condition': '输出须在开发树外；成功后统一使用返回的entry，若冻结指纹不符按恢复路径处理。'}
        return result

    def deliver(self):
        result = delivery.deliver_completion(self.repo, lambda repo: bookpage.live_shell(self.workspace.project, self.entry),
                                             workspace=self.workspace)
        self.app.record_delivery(result)
        return result

    def export(self, output=None, format='html'):
        return delivery.export_book(self.repo, output, format, workspace=self.workspace)

    def html(self, output=None, *, standalone=False):
        return bookpage.write(self.repo, output, workspace=self.workspace, standalone=standalone, entry=self.entry)

    def save_materials(self, result, output):
        if output == 'read_pack.json':
            output = self.repo.project / 'work' / result['task_id'] / output
        target = self.workspace.artifact_path(output)
        bodies = {'response': target, **{name: self.workspace.artifact_path(target.with_name(name))
                                      for name in ('read_pack.md', 'read_ref.md')}}
        # Validate every destination before writing any artifact.
        paths = list(bodies.values())
        require(not any(self.workspace.same_path(left, right) for index, left in enumerate(paths)
                        for right in paths[index + 1:]), 'output', '材料响应与两份材料包必须使用不同文件。')
        self.workspace.write_json(bodies['response'], result)
        for name, content in delivery.pack_markdowns(result).items():
            self.workspace.write_text(bodies[name], content)
        return {'task_id': result['task_id'], 'saved': str(target),
                'packs': [str(bodies[name]) for name in ('read_pack.md', 'read_ref.md')],
                'records': sorted(result['records']), 'records_hash': result.get('records_hash'),
                'execution_id': result.get('execution_id'), 'already_read': result.get('already_read', []),
                'note': '完整材料已落盘；首次读取两包，不省略前章原文或必要来源。'}

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


def pin_local_runtime(project, output, ref=None, entry=None):
    expected, task = None, None
    if project is not None:
        repo = SQLiteRepository(project, readonly=True)
        try:
            pending = repo.pending()
            expected = pending['input'].get('build') if pending else None
            task = {'task_id': pending['id'], 'input_hash': pending['input_hash']} if pending else None
        finally:
            repo.close()
    root = Path(entry or __file__).resolve()
    root = root.parent.parent if entry else root.parents[2]
    return runtime_install.pin(root, output, ref=ref, expected=expected, project=project, task=task)


def preview_local(project, port=0, open_browser=False, entry=None):
    return preview.serve(project, port, open_browser, entry)


def open_local_runtime(project, *, initialize=False, contract=None, source='', entry=None, readonly=False):
    root = Path(entry).resolve().parent.parent if entry else Path(__file__).resolve().parents[2]
    if (root / runtime_install.MANIFEST).exists():
        runtime_install.verify(root)
    if initialize:
        require(not readonly, 'access', '只读入口不能初始化项目。')
        book = workflow.new_book(contract, source) if contract is not None else workflow.preparing_book(source, guided=True)
        repo = SQLiteRepository.initialize(project, book)
    else:
        require(contract is None, 'contract', '已有项目不接受初始化约定。')
        repo = SQLiteRepository(project, readonly=readonly)
    try:
        return LocalRuntime(repo, entry)
    except BaseException:
        repo.close()
        raise
