"""Rebuildable task views and book export. No lifecycle decisions."""
from __future__ import annotations

import html
import json
import sys
import time
from pathlib import Path
from .contracts import FIRST_READ, FORM_ARTIFACTS, IDENTITY, RESULT, VERSION, digest, require, text
from .result_templates import template
from .ports import PublicationReader
from .publication import publication
from .workspace import LocalWorkspace, atomic_write
from .envelope import validate_identity, validate_task
from . import store_keys


def json_write(path, value):
    atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


# The author-facing card for one choice board. The controller hands this file's content over
# verbatim instead of re-deriving a presentation from the JSON return: a live run had to redirect
# advance's stdout to a file (GBK consoles garble UTF-8) and then hand-write a markdown card for
# every gate, paying main-session tokens to re-render what the engine already knows.
def render_board_card(board):
    gate = board.get('gate') or {}
    letters = 'ABCDEF'
    lines = ['# 开书选择：第 %s/%s 门 · %s' % (gate.get('number', '?'), gate.get('total', '?'), gate.get('title', '')),
             '',
             'board `%s`（choose/regroup 时原样使用）' % board.get('hash', ''),
             '']
    for index, option in enumerate(board.get('options') or []):
        tag = letters[index] if index < len(letters) else str(index + 1)
        lines.append('## %s. %s' % (tag, option.get('title', '')))
        lines.append('- id：`%s`（choose --option 用它）' % option.get('id', ''))
        for field, label in (('pitch', '一句话'), ('premise', '这一版'), ('driver', '推进'),
                             ('tradeoff', '代价与风险'), ('fit_reason', '承接')):
            value = option.get(field)
            if text(value):
                lines.append('- **%s**：%s' % (label, value))
        scenes = option.get('scene') or []
        if scenes:
            lines.append('- **画面**：')
            lines.extend('  - %s' % row for row in scenes)
        lines.append('')
    warnings = board.get('name_warnings') or []
    if warnings:
        lines.append('## 命名提示')
        lines.extend('- %s' % row.get('message', '') for row in warnings)
        lines.append('')
    lines.append('---')
    lines.append('回复 **A / B / C** 选择；**换一组**（附原因更好）；**D** 自定义一句方向；**返回某门**改已选项。')
    return chr(10).join(lines) + chr(10)


def write_board_card(workspace: LocalWorkspace, board):
    """Materialize the current board as work/board.md; a derived view, rebuilt on every ask."""
    path = workspace.artifact_path(workspace.project / 'work' / 'board.md')
    atomic_write(path, render_board_card(board))
    return str(path)


def render_question(board):
    """The author-facing ask payload rendered once by the engine, mirroring the board card.

    The controller forwards it verbatim instead of re-authoring one-line summaries: a live run
    condensed every gate into hand-written option descriptions while the engine's card (pitch,
    premise, tradeoff) never reached the author.
    """
    gate = board.get('gate') or {}
    letters = 'ABCDEF'
    options = []
    for index, option in enumerate(board.get('options') or []):
        tag = letters[index] if index < len(letters) else str(index + 1)
        summary = option.get('pitch') if text(option.get('pitch')) else option.get('premise')
        options.append({'label': '%s %s' % (tag, option.get('title', '')), 'description': summary or ''})
    options.append({'label': '换一组（可附原因）',
                    'description': '这一组都不合适；说明理由（如“格局太小”“不够爽”），我按理由重出一组实质不同的方案。'})
    options.append({'label': 'D 自定义', 'description': '这一门我自己说：直接给方向或内容。'})
    number, total, title = gate.get('number', '?'), gate.get('total', '?'), gate.get('title', '')
    return {'questions': [{'header': '第 %s/%s 门%s' % (number, total, '（新一组）' if board.get('round') else ''),
                           'question': '第 %s 门（%s）：选哪个？' % (number, title),
                           'multiSelect': False, 'options': options}]}


def write_question_card(workspace: LocalWorkspace, board):
    """Materialize the ask payload as work/question.json beside the board card."""
    path = workspace.artifact_path(workspace.project / 'work' / 'question.json')
    json_write(path, render_question(board))
    return str(path)


def write_advance_snapshot(workspace: LocalWorkspace, boundary):
    """Persist the full boundary view as work/last-advance.json before any compact trimming.

    The board echo is the one advance output that exists nowhere on disk; with the snapshot the
    compact return may shrink to pointers without losing the full view.
    """
    path = workspace.artifact_path(workspace.project / 'work' / 'last-advance.json')
    json_write(path, boundary)
    return str(path)


def _quoted_argv(argv):
    return ' '.join("'%s'" % part for part in argv)


def render_dispatch_card(envelope, identity):
    """The worker bootstrap card, rendered by the engine from the frozen dispatch itself.

    Hand-written dispatch prompts drift from what the engine enforces (a live run taught a worker
    to run `claim` and the boundary guard rejected it), and every cold worker paid a role_boundary
    round to learn the env bootstrap. The card carries the exact preamble and steps once, from the
    same source the guards check against; the controller forwards the path instead of re-authoring
    the protocol.
    """
    stage = envelope['stage']
    claim = envelope.get('claim')
    if claim is None:
        claim_lines = ['- 本任务 claim=null：无需认领，直接读取与提交。认领（claim 命令）由主干进程执行；'
                       'Worker 进程（已设 NOVEL_TASK_ID）执行会被 worker_boundary 拒绝。']
    else:
        state = '已过期' if claim.get('expired') else '生效中（session=%s）' % claim.get('session')
        claim_lines = ['- 本任务已有租约（%s）：未过期沿用原会话；过期由主干重新认领，Worker 不执行 claim。' % state]
    suggested = identity['worker_env'].get('NOVEL_SESSION') or ('worker-%s-XXXX（自命名，XXXX 任选四位）' % stage)
    commands = envelope.get('commands') or {}
    locked = envelope.get('delivery_phase') == 'first_read'
    if locked:
        steps = ['1. 读 `task.json` 与 `brief.md`（首读指示）；完整读 prose_files 里的每一章正文。',
                 '2. 按 `first_read_path` 指向的 first-read.json 逐章填首读记录，执行 commands.first_read。',
                 '3. 首读冻结后按返回的新 task_path 继续：仍用本会话完成解锁后的核验，不换人不重读首读。',
                 '4. worker_boundary=finished 后结束：不自行 advance，不执行作者或主干命令。']
        command_names = ('read', 'first_read')
    else:
        steps = ['1. 读 `task.json` 与 `brief.md`；`guides` 列出本任务对应参考文档，按需再读。',
                 '2. 执行一次无参数 read（命令见下）把必读记录拿齐；确需某份再 read --record 名称。',
                 '3. 复制 `result.template.json` 为 `result.json` 起稿，只改 data；'
                 'schema/task_id/input_hash 不手写（input_version 报错会带 expected）。',
                 '4. `preflight` 试算，按报错 details.expect 修正；不为确认格式读引擎源码。',
                 '5. `submit` 提交；worker_boundary=finished 后结束：不自行 advance，不执行作者或主干命令，不改写 commands/guides。']
        command_names = ('read', 'preflight', 'submit')
    lines = ['# Worker 自举卡：%s' % stage,
             '',
             identity.get('task_line') or ('本任务：stage=%s。' % stage),
             '任务文件（唯一权威）：`%s`；简报全文：同目录 `brief.md`（不必解析 input.json）。' % envelope['task_path'],
             '',
             '## 1. 环境自举（PowerShell，照抄；会话名一次定下不再改）',
             '',
             '    $env:PYTHONIOENCODING=\'utf-8\'',
             '    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8',
             "    $env:NOVEL_TASK_ID='%s'" % envelope['task_id'],
             "    $env:NOVEL_SESSION='%s'" % suggested,
             '',
             '首条 read 报 role_boundary 说明环境变量未生效：回本块重设后再试。',
             '',
             '## 2. 步骤',
             '',
             *steps,
             '',
             '## 3. 认领',
             '',
             *claim_lines,
             '']
    for name in command_names:
        if commands.get(name):
            lines.append('- %s：%s' % (name, _quoted_argv(commands[name])))
    lines += ['',
              '## 4. 常见坑',
              '',
              '- commands 是 argv 数组：逐项传参，不拼 shell 字符串，不改路径。',
              '- 控制台 GBK 会乱码：中文内容走文件工件（brief.md、work/board.md、work/question.json），'
              '不在控制台打印长 JSON；自行重定向时 PowerShell 5 的 `Out-File -Encoding utf8` 带 BOM，读回用 utf-8-sig。',
              '- 完成后向主控只报状态：task_id、valid/accepted/committed、worker_boundary、'
              '错误或拒绝摘要（含 code）；不贴正文或完整回执。']
    return '\n'.join(lines) + '\n'



def output_path(workspace: LocalWorkspace, output, default):
    """Delegate output validation to the workspace that owns local paths."""
    return (workspace.output_path(output, default) if output
            else workspace.artifact_path(workspace.project / default))


def task_line(work):
    """One line that says what this dispatch actually is, read off the frozen task.

    The controller hands this line on instead of describing the work from the pipeline it assumes:
    a revision-scope review announced as the book's final review is a description error the worker
    can only discover after reading the frozen material.
    """
    parts = ['stage=' + str(work.get('stage'))]
    if work.get('scope'):
        parts.append('scope=' + str(work['scope']))
    if work.get('chapter'):
        chapter = ('chapter=%s' % work['chapter'] if work.get('first') in (None, work.get('chapter'))
                   else 'chapters=%s-%s' % (work['first'], work['last']))
        parts.append(chapter)
    parts.append('required=' + ','.join(work.get('required') or ()) or 'required=(无)')
    if work.get('blind'):
        parts.append('blind=先首读封印')
    return '本任务：' + '；'.join(parts) + '。派工说明以此为准，不要按流程位置想象。'


# Work directory ownership. `work/<task>/` mixes two kinds of file:
#   controller-authored, rebuildable: task.json, input.json, chapter-*.txt
#   worker-authored, never rewritten: result.template.json (the form) and result.json (the receipt)
# Cancellation is the only event that retires worker-authored artifacts, and it does so by
# deleting them rather than by leaving them for the next task to trip over.
def form_is_current(path, task):
    try:
        existing = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return False
    return isinstance(existing, dict) and existing.get('task_id') == task['id'] \
        and existing.get('input_hash') == task['input_hash']


def retire(base, *, workspace: LocalWorkspace):
    """Drop regenerable artifacts so a stale task view cannot be reused."""
    for name in FORM_ARTIFACTS:
        workspace.artifact_path(Path(base) / name).unlink(missing_ok=True)


def materialize(repo: PublicationReader, task, entry, baseline=None, compact=False, *, workspace: LocalWorkspace):
    work = task['input']
    base = workspace.artifact_path('work/' + task['id'])
    def artifact(name):
        return workspace.artifact_path(base / name)

    locked = work['blind'] and not task['first_read']
    prose_files = []
    for ref in work['prose']:
        path = artifact('chapter-' + str(ref['chapter']) + '.txt')
        atomic_write(path, repo.read_document(ref['hash']))
        prose_files.append({**ref, 'path': str(path)})
    command = [sys.executable, str(entry), '--project', str(workspace.project)]
    lease = repo.get(store_keys.claim(task['id']))
    # The envelope, its identity copy and the compact controller view all describe the same dispatch.
    # They are derived from one mapping so a shared field cannot be added to one of them and forgotten
    # in the others — which is how a controller ends up reading a stage the worker never got.
    shared = {'task_id': task['id'], 'input_hash': task['input_hash'], 'stage': work['stage'],
              'chapter': work['chapter'], 'scope': work['scope'],
              'delivery_phase': 'first_read' if locked else 'formal',
              'requires_new_worker': task['reviewer'] is None, 'review_session': task['reviewer']}
    envelope = {'schema': work['schema'], **shared, 'prose_files': prose_files,
                'task_path': str(artifact('task.json')), 'result_path': str(artifact('result.json')),
                'project_path': str(workspace.project), 'host_log_path': str(artifact('host.log')),
                'process': {'project_path': str(workspace.project), 'task_path': str(artifact('task.json')),
                            'log_path': str(artifact('host.log'))},
                'version': VERSION,
                # A live claim blocks re-dispatch. Expiry permits reclaiming only after checking
                # the existing worker and any frozen reviewer session.
                'claim': ({'session': lease['session'], 'expired': lease['until'] <= time.time()}
                          if lease else None),
                # The ledger baseline is a read-only projection: dispatchers forward it instead of
                # hand-summarizing balances, and workers use it to sanity-check precondition values.
                'baseline': None if locked else baseline,
                'commands': {'submit': command + ['submit', '--file', str(artifact('result.json'))],
                             'preflight': command + ['preflight', '--file', str(artifact('result.json'))],
                             'read': command + ['read', '--task', task['id']],
                             'recall': command + ['recall', '--task', task['id']]}}
    if work.get('capabilities', {}).get('editorial') and work['stage'] in ('repair', 'redesign'):
        envelope['commands']['patch'] = command + ['patch', '--task', task['id']]
    reference_dir = Path(entry).parent.parent / 'references'
    # Guides are optional reference material per stage; the dispatch's own brief carries what the
    # task needs, so whole documents are not shipped on every round.
    guides = {'opening_options': ('opening.md', 'hatch.md'), 'opening_contract': ('opening.md', 'world.md'),
              'world_model': ('world.md',), 'world_review': ('world.md',), 'volume_plan': ('hatch.md',)}
    if work.get('capabilities', {}).get('editorial'):
        guides[work['stage']] = (*guides.get(work['stage'], ()), 'editorial.md')
    if work.get('capabilities', {}).get('understanding'):
        guides[work['stage']] = (*guides.get(work['stage'], ()), 'workbench.md')
    also = tuple((work['payload'] or {}).get('also', ()))
    names = list(guides.get(work['stage'], ()))
    if work['stage'] not in ('opening_options', 'world_model', 'world_review', 'opening_contract'):
        names.extend(n for n in ('protocol.md', 'craft.md') if n not in names)
    for extra_stage in also:
        names.extend(name for name in guides.get(extra_stage, ()) if name not in names)
    if names:
        envelope['guides'] = [str(reference_dir / name) for name in names]
    envelope['stages'] = [work['stage'], *also]
    # Who this dispatch is belongs in the dispatch, not only in the host's environment: the worker
    # and the controller can then cross-check identity against the task instead of guessing. It
    # grants nothing — prose stays behind the host-injected credential.
    identity = {'schema': IDENTITY, **shared, 'stages': envelope['stages'],
                'project_path': str(workspace.project), 'task_path': envelope['task_path'],
                'entry': str(entry), 'version': VERSION,
                'worker_env': {'NOVEL_TASK_ID': task['id'], 'NOVEL_SESSION': task['reviewer']},
                # What this dispatch is, rendered from the frozen task itself. A controller that
                # describes the work from an assumed pipeline position instead of from here can hand a
                # worker a task it is not (a revision-scope review announced as the book's final
                # review); reading this line prevents that, and costs one sentence per dispatch.
                'task_line': task_line(work),
                'note': '本文件是派工身份的可核对副本，不授予权限：read/recall/patch/first-read 仍只对'
                        '宿主注入 NOVEL_TASK_ID 与 NOVEL_SESSION 的派工进程开放；NOVEL_SESSION 为空表示'
                        '本次由新会话自行命名。'}
    validate_identity(identity)
    identity_file = artifact('identity.json')
    json_write(identity_file, identity)
    envelope['identity_path'] = str(identity_file)
    # The brief rides inside input.json as one long JSON string, which console tools truncate or
    # garble; the markdown twin is what readers actually open. Both branches above settled the
    # text (the locked branch writes its own one-line brief into the envelope).
    brief_text = envelope.get('brief') or work.get('brief')
    if text(brief_text):
        brief_file = artifact('brief.md')
        atomic_write(brief_file, brief_text)
        envelope['brief_path'] = str(brief_file)
    dispatch_file = artifact('dispatch.md')
    atomic_write(dispatch_file, render_dispatch_card(envelope, identity))
    envelope['dispatch_path'] = str(dispatch_file)
    # The commands below are rendered from this process, so they work as long as this installation
    # does. Say so, and say what to do when it has moved: a stale path is refreshed by another
    # `advance`, never by rewriting the command by hand.
    envelope['note'] = ('commands 用当前安装的真实路径生成：' + command[0] + ' + ' + str(entry) +
                        '。若技能目录已移动导致路径不存在，回主控再执行一次 advance 刷新任务视图，'
                        '不要手改命令，也不要凭印象判定路径失效（宿主可用目录联接映射同一份安装）。')
    if locked:
        # Only first-read instructions are visible until sealing, never the planned outcomes.
        envelope['brief'] = '只读全部 prose_files，记录每章首读 desire/obstacle/change/read_on_reason 后执行 first_read。解锁后沿新 task_path 完成核验；不提前读设计、状态或自评。'
        first_path = artifact('first-read.json')
        if not first_path.exists():
            json_write(first_path, {'task_id': task['id'], 'input_hash': task['input_hash'], 'session': '',
                                   'data': {'reads': [dict(chapter=r['chapter'], **{k: '' for k in FIRST_READ}) for r in work['prose']]}})
        envelope['first_read_path'] = str(first_path)
        envelope['commands']['first_read'] = command + ['first-read', '--file', str(first_path)]
        # A blind task hands out no formal material; any earlier render is retired here.
        retire(base, workspace=workspace)
    else:
        # The view carries the task's own material; record hashes live in task.json alone, so the
        # same map is not delivered twice.
        view = {'task_id': task['id'], 'input_hash': task['input_hash'],
                **{key: value for key, value in work.items() if key != 'records'},
                'first_read': task['first_read'], 'first_read_hash': task['first_read_hash']}
        json_write(artifact('input.json'), view)
        template_path = artifact('result.template.json')
        # The form belongs to the Worker once minted: rebuilding a view must never blank a
        # half-filled form. A form minted for another task is stale and is replaced.
        if not form_is_current(template_path, task):
            result = {'schema': RESULT, 'task_id': task['id'], 'input_hash': task['input_hash'],
                      'session': task['reviewer'] or '',
                      'data': template(work['stage'], work['chapter'], {r['chapter']: '' for r in work['prose']},
                                       work['obligations'], also, work.get('checks_version', 1), work['payload'], work.get('narrative_tracking', False))}
            json_write(template_path, result)
        envelope.update(input_path=str(artifact('input.json')), template_path=str(template_path), records=work['records'], required=work['required'])
    # Two facts a controller cannot otherwise see: how many times this dispatch view has been
    # rendered (a second render for one task is a double dispatch, and used to be invisible), and
    # what it costs to read. Both are read off the artifacts themselves, so the read-only
    # delivery surface needs no new persistence capability.
    task_file = artifact('task.json')
    previous = json.loads(task_file.read_text(encoding='utf-8')) if task_file.exists() else None
    envelope['redispatch_count'] = (previous.get('redispatch_count', 0) + 1
                                    if previous and previous.get('input_hash') == envelope['input_hash'] else 1)
    envelope['material_bytes'] = sum(path.stat().st_size for path in
                                     (artifact('input.json'), artifact('result.template.json'))
                                     if path.exists())
    validate_task(envelope)
    json_write(task_file, envelope)
    if compact:
        # Keep the controller's context small; workers always receive the complete on-disk envelope.
        # The shared dispatch fields are listed from the same mapping the envelope was built from.
        keys = ('schema', 'version', *shared, 'task_path', 'identity_path', 'brief_path', 'dispatch_path', 'claim')
        return {key: envelope[key] for key in keys if key in envelope}
    return envelope


def export_book(repo: PublicationReader, output=None, format='html', *, workspace: LocalWorkspace):
    book, rows = publication(repo)
    require(book.get('contract') is not None, 'contract', '尚无生效约定，不能导出正文。',
            {'recover': '先完成开书：init --contract、opening --file 或逐门开书的约定核验。'})
    explicit = output is not None
    output = output_path(workspace, output, 'book.' + ('html' if format == 'html' else 'md'))
    reserved = workspace.project / 'book.html'
    if output == reserved or explicit and workspace.same_path(output, reserved):
        # 全书视图 owns this path; an implicit export would silently replace it with a plain render.
        require(False, 'output', 'book.html 是全书视图的输出位置；导出请用 --output 指定其他文件，或改用 html 命令。',
                {'recover': '例如 --output book-export.html（或 --format md 得到 book.md）。'})
    candidate = book['branch'] != repo.get(store_keys.OFFICIAL_BRANCH, 'main')
    if format == 'html':
        pieces = ['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>' + html.escape(book['contract']['title']) + '</title>',
                  '<style>body{max-width:48em;margin:3em auto;padding:0 1em;line-height:1.9}p{white-space:pre-wrap}section{margin:3em 0}</style>',
                  '<h1>' + html.escape(book['contract']['title']) + '</h1>']
        if candidate:
            pieces.append('<p>修订候选，尚未合并为正式版本。</p>')
        for row in rows:
            pieces.append('<section><h2>第' + str(row['n']) + '章 ' + html.escape(row['title']) + '</h2><p>' + html.escape(repo.read_document(row['prose'])) + '</p></section>')
        pieces.append('</html>')
        content = '\n'.join(pieces)
    else:
        content = '# ' + book['contract']['title'] + '\n\n' + ('修订候选，尚未合并为正式版本。\n\n' if candidate else '') + '\n\n'.join('## 第' + str(r['n']) + '章 ' + r['title'] + '\n\n' + repo.read_document(r['prose']) for r in rows)
    atomic_write(output, content)
    return {'path': str(output), 'chapters': len(rows), 'branch': book['branch'], 'candidate': candidate, 'inside_project': output.is_relative_to(workspace.project)}


def deliver_completion(repo: PublicationReader, render=None, *, workspace: LocalWorkspace):
    book = repo.load()
    require(book['status'] == 'completed' and book.get('completion_snapshot'), 'completion', '先完成内容验收再交付。')
    reference = book['completion_snapshot']
    snapshot = repo.read_document(reference)
    rows = snapshot['chapters']
    exported = export_book(repo, format='md', workspace=workspace)
    paths = [Path(exported['path'])]
    if render:
        page = workspace.artifact_path(workspace.project / 'book.html')
        atomic_write(page, render(repo))
        paths.append(page)
    manifest = {'snapshot_hash': reference, 'chapters': [{'chapter': r['n'], 'prose_hash': r['prose']} for r in rows],
                'files': [{'path': str(p), 'content_hash': digest(p.read_text(encoding='utf-8'))} for p in paths]}
    json_write(workspace.artifact_path(workspace.project / 'delivery.json'), manifest)
    return {'delivered': True, 'manifest_path': str(workspace.project / 'delivery.json'), **manifest}


def export_world(repo: PublicationReader, render, *, workspace: LocalWorkspace):
    book = repo.load()
    model = book.get('world')
    require(model is not None and book.get('world_review') is not None, 'world_view', '世界模型尚未通过独立核验。')
    json_path = workspace.artifact_path(workspace.project / 'world.json')
    html_path = workspace.artifact_path(workspace.project / 'book.html')
    json_write(json_path, {'selection_hash': model['selection_hash'], 'model_hash': digest(model),
                          'choices': book['creation']['selections'], 'world': model, 'review': book['world_review']})
    atomic_write(html_path, render(repo))
    return {'html_path': str(html_path), 'json_path': str(json_path), 'model_hash': digest(model)}
