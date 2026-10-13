#!/usr/bin/env python3
"""CLI composition and default-deny access; domain behavior lives in novel_ledger."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from novel_ledger.contracts import Error, VERSION, require
from novel_ledger.application import Application
from novel_ledger.sqlite_store import SQLiteRepository
from novel_ledger.workflow import new_book, preparing_book
from novel_ledger import bookpage, delivery, host

PUBLIC = {'init', 'status', 'advance', 'submit', 'preflight', 'first-read', 'claim', 'run', 'renew', 'approve',
          'pause', 'resume', 'revise', 'promote', 'discard', 'opening', 'choose', 'regroup', 'back', 'recontract', 'replan', 'feedback', 'lexical', 'complete', 'host-step', 'host-loop'}
SEALED = {'read', 'recall', 'audit', 'export', 'html'}
WORKER = {'status', 'read', 'recall', 'submit', 'preflight', 'first-read'}
# Prose, frozen records and the first read belong to a dispatched task; the controller role never executes them.
WORKER_ONLY = {'read', 'recall', 'first-read'}


def load(path):
    try:
        return json.loads(Path(path).expanduser().read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise Error('file', '无法读取 JSON 文件。', {'path': str(path), 'recover': str(exc)})


def parser():
    root = argparse.ArgumentParser(description='长篇小说账本')
    root.add_argument('--version', action='version', version=VERSION)
    root.add_argument('--project')
    root.add_argument('--owner')
    subs = root.add_subparsers(dest='command', required=True)
    for command in sorted(PUBLIC | SEALED):
        sub = subs.add_parser(command)
        sub.add_argument('--project', default=argparse.SUPPRESS)
        sub.add_argument('--owner', default=argparse.SUPPRESS)
        if command == 'init':
            sub.add_argument('--contract')
            sub.add_argument('--source', default='')
        if command in ('submit', 'preflight', 'first-read', 'recontract', 'opening', 'lexical'):
            sub.add_argument('--file', required=True)
        if command in ('approve', 'recontract', 'opening', 'choose', 'lexical'):
            sub.add_argument('--source', required=True)
        if command == 'choose':
            sub.add_argument('--option', required=True)
        if command in ('choose', 'regroup'):
            sub.add_argument('--board', required=True)
        if command == 'regroup':
            sub.add_argument('--reason', default='换一组')
        if command == 'back':
            sub.add_argument('--gate', required=True)
            sub.add_argument('--reason', default='返回重选')
        if command == 'approve':
            sub.add_argument('--prose-hash', required=True)
        if command == 'advance':
            sub.add_argument('--after')
        if command in ('read', 'recall', 'claim'):
            sub.add_argument('--task', required=True)
        if command == 'read':
            sub.add_argument('--record')
        if command == 'recall':
            group = sub.add_mutually_exclusive_group(required=True)
            group.add_argument('--chapter', type=int)
            group.add_argument('--state', action='store_true')
        if command in ('claim', 'run', 'renew'):
            sub.add_argument('--seconds', type=int, default=300)
        if command == 'claim':
            sub.add_argument('--session', required=True)
        if command == 'run':
            group = sub.add_mutually_exclusive_group(required=True)
            group.add_argument('--through', type=int)
            group.add_argument('--complete', action='store_true')
            sub.add_argument('--source', default='')
        if command in ('pause', 'revise', 'replan'):
            sub.add_argument('--reason', required=True)
        if command == 'pause':
            sub.add_argument('--cancel', action='store_true')
        if command in ('revise', 'replan'):
            sub.add_argument('--from-chapter', type=int, required=True)
        if command == 'feedback':
            sub.add_argument('--text', required=True)
        if command in ('export', 'html'):
            sub.add_argument('--output')
            sub.add_argument('--format', choices=('html', 'md'), default='html')
        if command in ('host-step', 'host-loop'):
            sub.add_argument('--command-json', required=True)
            sub.add_argument('--timeout', type=int, default=300)
            if command == 'host-loop':
                sub.add_argument('--limit', type=int, default=100)
    return root


def role_guard(args):
    """A dispatched worker and the controller are different roles; prose is worker-only."""
    if args.command in WORKER_ONLY:
        require(os.environ.get('NOVEL_TASK_ID'), 'role_boundary',
                '正文与冻结资料只经派工任务读取；主控不直接读取正文。',
                {'recover': '由被派 Worker 携带 NOVEL_TASK_ID 读取本任务资料。'})


def worker_guard(app, args):
    ident = os.environ.get('NOVEL_TASK_ID')
    if not ident:
        return
    require(args.command in WORKER, 'worker_boundary', 'Worker 不能执行主控或作者命令。')
    require(getattr(args, 'task', ident) == ident, 'worker_boundary', 'Worker 只能访问自己的任务。')
    task = app.repo.task(ident)
    if args.command not in ('submit', 'preflight'):
        app._live(task)
        app._session(task, os.environ.get('NOVEL_SESSION'), os.environ.get('NOVEL_EXECUTION_CLAIM'))


def dispatch(args):
    require(args.project, 'project', '须指定 --project 小说项目绝对路径。')
    require(args.command in PUBLIC | SEALED, 'access', '未登记命令默认拒绝。')
    if args.command == 'init':
        require(not os.environ.get('NOVEL_TASK_ID'), 'worker_boundary', 'Worker 不能初始化项目。')
        book = new_book(load(args.contract), args.source) if args.contract else preparing_book(args.source, guided=True)
        repo = SQLiteRepository.initialize(args.project, book)
    else:
        repo = SQLiteRepository(args.project)
    try:
        app = Application(repo, Path(__file__).resolve())
        role_guard(args)
        worker_guard(app, args)
        if args.command in SEALED:
            app.content_guard()
        command, owner = args.command, args.owner
        if command in ('init', 'status'):
            return app.status()
        if command == 'advance':
            return app.advance(args.after, owner)
        if command in ('submit', 'preflight', 'first-read'):
            result = load(args.file)
            if os.environ.get('NOVEL_TASK_ID'):
                require(result.get('task_id') == os.environ['NOVEL_TASK_ID'] and result.get('session') == os.environ.get('NOVEL_SESSION'),
                        'worker_boundary', '回执不能改投其他任务或会话。')
            return app.seal(result) if command == 'first-read' else app.submit(result, command == 'preflight')
        if command == 'read':
            return app.read(args.task, args.record)
        if command == 'recall':
            return app.recall(args.task, args.chapter, args.state)
        if command == 'claim':
            return app.claim(args.task, args.session, args.seconds)
        if command == 'run':
            return app.run(args.through, args.complete, owner, args.seconds, args.source)
        if command == 'renew':
            return app.renew(owner, args.seconds)
        if command == 'approve':
            return app.approve(args.prose_hash, args.source, owner)
        if command == 'choose':
            return app.opening_choice(args.option, args.board, args.source, owner)
        if command == 'regroup':
            return app.opening_regroup(args.board, args.reason, owner)
        if command == 'back':
            return app.opening_back(args.gate, args.reason, owner)
        if command == 'pause':
            return app.pause(args.reason, args.cancel, owner)
        if command == 'resume':
            return app.resume(owner)
        if command == 'revise':
            return app.revise(args.from_chapter, args.reason, owner)
        if command == 'replan':
            return app.replan(args.from_chapter, args.reason, owner)
        if command == 'feedback':
            return app.feedback(args.text, owner)
        if command == 'lexical':
            return app.set_lexical(load(args.file), args.source, owner)
        if command == 'promote':
            return app.promote(owner)
        if command == 'discard':
            return app.discard(owner)
        if command in ('recontract', 'opening'):
            return app.recontract(load(args.file), args.source, owner, opening=command == 'opening')
        if command == 'audit':
            return app.audit()
        if command == 'complete':
            return app.complete(owner)
        if command == 'export':
            return delivery.export_book(repo, args.output, args.format)
        if command == 'html':
            require(args.format == 'html', 'format', 'html 命令只生成 HTML 全书视图；纯文本导出用 export --format md。')
            return bookpage.write(repo, args.output)
        if command == 'host-step':
            return host.step(app, load(args.command_json), owner, args.timeout)
        if command == 'host-loop':
            return host.loop(app, load(args.command_json), owner, args.limit, args.timeout)
        require(False, 'access', '未实现命令。')
    finally:
        repo.close()


def main(argv=None):
    try:
        value = dispatch(parser().parse_args(argv))
    except Error as exc:
        print(json.dumps(exc.as_dict(), ensure_ascii=False))
        return 2
    except (OSError, ValueError) as exc:
        print(json.dumps({'error': 'io', 'message': str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(value, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
