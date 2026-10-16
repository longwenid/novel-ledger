#!/usr/bin/env python3
"""CLI composition and default-deny access; domain behavior lives in novel_ledger."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from novel_ledger.contracts import Error, VERSION, require
from novel_ledger.bootstrap import open_local_runtime

PUBLIC = {'init', 'intake', 'status', 'usage', 'advance', 'submit', 'preflight', 'check', 'first-read', 'claim', 'run', 'renew', 'approve',
          'pause', 'resume', 'answer', 'revise', 'revision-impact', 'workbench', 'compact', 'promote', 'discard', 'opening', 'choose', 'regroup', 'back', 'recontract', 'replan', 'feedback', 'lexical', 'complete', 'host-step', 'host-loop'}
SEALED = {'read', 'recall', 'patch', 'audit', 'export', 'html', 'deliver'}
WORKER = {'status', 'read', 'recall', 'patch', 'submit', 'preflight', 'check', 'first-read'}
# Prose, frozen records and the first read belong to a dispatched task; the controller role never executes them.
WORKER_ONLY = {'read', 'recall', 'patch', 'first-read'}


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
        if command in ('submit', 'preflight', 'first-read', 'recontract', 'opening', 'lexical', 'intake'):
            sub.add_argument('--file', required=True)
        if command == 'check':
            sub.add_argument('--file')
            sub.add_argument('--task')
        if command in ('approve', 'recontract', 'opening', 'choose', 'lexical', 'intake', 'workbench'):
            sub.add_argument('--source', required=True)
        if command == 'choose':
            sub.add_argument('--option')
            sub.add_argument('--tier', help='结构门按档位直接指定；展示窗口会自动滑到该档。')
        if command in ('choose', 'regroup'):
            sub.add_argument('--board')
        if command == 'regroup':
            sub.add_argument('--reason', default='换一组')
        if command == 'back':
            sub.add_argument('--gate', required=True)
            sub.add_argument('--reason', default='返回重选')
        if command == 'approve':
            sub.add_argument('--prose-hash', required=True)
        if command == 'advance':
            sub.add_argument('--after')
            sub.add_argument('--compact', action='store_true', help='只返回主干派工信息，完整任务保留在 task_path。')
        if command in ('read', 'recall', 'claim', 'patch'):
            sub.add_argument('--task', required=True)
        if command == 'patch':
            sub.add_argument('--old', required=True)
            sub.add_argument('--new', required=True)
            sub.add_argument('--start', type=int)
        if command == 'read':
            sub.add_argument('--record')
        if command == 'recall':
            group = sub.add_mutually_exclusive_group(required=True)
            group.add_argument('--chapter', type=int)
            group.add_argument('--state', action='store_true')
            for kind in ('entity', 'node', 'topic', 'thread'):
                group.add_argument('--' + kind)
            sub.add_argument('--limit', type=int, default=5)
            sub.add_argument('--before', type=int)
        if command in ('claim', 'run', 'renew'):
            sub.add_argument('--seconds', type=int, default=300)
        if command == 'claim':
            sub.add_argument('--session', required=True)
        if command == 'run':
            group = sub.add_mutually_exclusive_group(required=True)
            group.add_argument('--through', type=int)
            group.add_argument('--complete', action='store_true')
            sub.add_argument('--source', default='')
        if command == 'answer':
            sub.add_argument('--decision-id', required=True, help='待作者裁决的问题 id，与 status 的 author_decision.id 一致。')
            sub.add_argument('--option', required=True, help='作者选定的选项 label，须是已展示选项之一。')
            sub.add_argument('--source', required=True, help='作者答复的原话。')
        if command in ('pause', 'revise', 'replan'):
            sub.add_argument('--reason', required=True)
        if command == 'pause':
            sub.add_argument('--cancel', action='store_true')
        if command in ('revise', 'replan', 'revision-impact'):
            sub.add_argument('--from-chapter', type=int, required=True)
        if command in ('revise', 'revision-impact'):
            sub.add_argument('--changes-file')
        if command == 'revise':
            sub.add_argument('--through', type=int)
            sub.add_argument('--proposal-hash')
            sub.add_argument('--to-end', action='store_true',
                             help='确认从修订起点重写到当前末章；未给 --through/--changes-file 时必须显式选择。')
            sub.add_argument('--source', default='')
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
        task = os.environ.get('NOVEL_TASK_ID')
        require(task, 'role_boundary',
                '正文与冻结资料只经派工任务读取；主控不直接读取正文。',
                {'recover': '把这条命令交给被派的任务执行（它带 NOVEL_TASK_ID 与 NOVEL_SESSION）；'
                            '主控要核对进度用 status，要补资料用 read --record 交由该任务完成。'})
        require(getattr(args, 'task', task) == task, 'worker_boundary', 'Worker 只能访问自己的任务。')


def worker_guard(app, args):
    ident = os.environ.get('NOVEL_TASK_ID')
    if not ident:
        return
    require(args.command in WORKER, 'worker_boundary', 'Worker 不能执行主控或作者命令。')
    if args.command not in ('submit', 'preflight'):
        app.authorize_worker(ident, os.environ.get('NOVEL_SESSION'), os.environ.get('NOVEL_EXECUTION_CLAIM'))


def dispatch(args, open_runtime=open_local_runtime):
    require(args.project, 'project', '须指定 --project 小说项目绝对路径。')
    require(args.command in PUBLIC | SEALED, 'access', '未登记命令默认拒绝。')
    if args.command == 'init':
        require(not os.environ.get('NOVEL_TASK_ID'), 'worker_boundary', 'Worker 不能初始化项目。')
    runtime = open_runtime(args.project, initialize=args.command == 'init',
                           contract=load(args.contract) if args.command == 'init' and args.contract else None,
                           source=args.source if args.command == 'init' else '', entry=Path(__file__).resolve())
    try:
        app = runtime.app
        role_guard(args)
        worker_guard(app, args)
        if args.command == 'workbench':
            return app.enable_workbench(args.source, args.owner)
        if args.command in SEALED:
            app.content_guard()
        command, owner = args.command, args.owner
        if command == 'init':
            result = app.status()
            try:
                result['book_view'] = runtime.book_view()
            except OSError as exc:
                result['book_view_error'] = str(exc)
            return result
        if command == 'status':
            return app.status()
        if command == 'advance':
            return app.advance(args.after, owner, compact=args.compact)
        if command == 'intake':
            return app.intake(load(args.file), args.source, owner)
        if command == 'usage':
            return app.usage()
        if command == 'patch':
            return app.patch(args.task, args.old, args.new, args.start)
        if command == 'deliver':
            return runtime.deliver()
        if command in ('submit', 'preflight', 'first-read'):
            result = load(args.file)
            require(isinstance(result, dict), 'schema', '回执须为 JSON 对象。')
            if os.environ.get('NOVEL_TASK_ID'):
                require(result.get('task_id') == os.environ['NOVEL_TASK_ID'] and result.get('session') == os.environ.get('NOVEL_SESSION'),
                        'worker_boundary', '回执不能改投其他任务或会话。')
            return app.seal(result) if command == 'first-read' else app.submit(result, command == 'preflight')
        if command == 'check':
            # Same validation as submit, but the receipt may omit task identity and may be piped in:
            # a worker learns which field is wrong without reading the engine's source.
            payload = load(args.file) if args.file else json.load(sys.stdin)
            return app.check(payload, getattr(args, 'task', None), session=os.environ.get('NOVEL_SESSION'))
        if command == 'read':
            return app.read(args.task, args.record)
        if command == 'recall':
            kind = next((k for k in ('entity', 'node', 'topic', 'thread') if getattr(args, k)), None)
            return app.recall(args.task, args.chapter, args.state, kind, getattr(args, kind) if kind else None, args.limit, args.before)
        if command == 'claim':
            return app.claim(args.task, args.session, args.seconds)
        if command == 'run':
            return app.run(args.through, args.complete, owner, args.seconds, args.source)
        if command == 'renew':
            return app.renew(owner, args.seconds)
        if command == 'approve':
            return app.approve(args.prose_hash, args.source, owner)
        if command == 'choose':
            if args.tier:
                return app.opening_tier(args.tier, args.source, owner)
            require(args.option and args.board, 'opening_option',
                    'choose 需要 --option 与 --board，或用 --tier 直接指定档位。')
            return app.opening_choice(args.option, args.board, args.source, owner)
        if command == 'regroup':
            require(args.board, 'opening_option', 'regroup 需要 --board。')
            return app.opening_regroup(args.board, args.reason, owner)
        if command == 'back':
            return app.opening_back(args.gate, args.reason, owner)
        if command == 'pause':
            return app.pause(args.reason, args.cancel, owner)
        if command == 'resume':
            return app.resume(owner)
        if command == 'answer':
            return app.answer(args.decision_id, args.option, args.source, owner)
        if command == 'revise':
            # An unscoped author revision silently rewrites from the start chapter to the last
            # one. Require an explicit scope so "change chapter 2" never means "rewrite the
            # rest of the book" by accident; revision_impact stays read-only and free.
            require(args.through or args.changes_file or args.proposal_hash or args.to_end,
                    'revision_scope',
                    '历史修订须声明作用范围：--through、--changes-file、--proposal-hash 或 --to-end 四选一。',
                    {'recover': '先跑 revision-impact --from-chapter N 查看影响终点，再用 --through 收窄；'
                                '确认要改到末章时显式加 --to-end。'})
            return app.revise(args.from_chapter, args.reason, owner, args.through,
                              load(args.changes_file) if args.changes_file else None, args.proposal_hash, args.source)
        if command == 'compact':
            return app.prune(owner)
        if command == 'revision-impact':
            return app.revision_impact(args.from_chapter, load(args.changes_file) if args.changes_file else None)
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
            return runtime.export(args.output, args.format)
        if command == 'html':
            require(args.format == 'html', 'format', 'html 命令只生成 HTML 全书视图；纯文本导出用 export --format md。')
            return runtime.html(args.output)
        if command == 'host-step':
            return runtime.host_step(load(args.command_json), owner, args.timeout)
        if command == 'host-loop':
            return runtime.host_loop(load(args.command_json), owner, args.limit, args.timeout)
        require(False, 'access', '未实现命令。')
    finally:
        runtime.close()


def main(argv=None):
    # Output is UTF-8 JSON regardless of the host locale: a controller reading our stdout must not
    # have to guess the console code page. Windows consoles render it correctly from 3.6 onward.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass
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
