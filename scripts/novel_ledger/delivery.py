"""Rebuildable task views and book export. No lifecycle decisions."""
from __future__ import annotations

import html
import json
import sys
import time
from pathlib import Path
from .contracts import FIRST_READ, FORM_ARTIFACTS, IDENTITY, RESULT, VERSION, digest, require
from .result_templates import template
from .ports import PublicationReader
from .publication import publication
from .workspace import LocalWorkspace, atomic_write
from .envelope import validate_identity, validate_task
from . import store_keys


def json_write(path, value):
    atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def output_path(workspace: LocalWorkspace, output, default):
    """Delegate output validation to the workspace that owns local paths."""
    return (workspace.output_path(output, default) if output
            else workspace.artifact_path(workspace.project / default))


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
    envelope = {'schema': work['schema'], 'task_id': task['id'], 'input_hash': task['input_hash'],
                'stage': work['stage'], 'chapter': work['chapter'], 'scope': work['scope'],
                'delivery_phase': 'first_read' if locked else 'formal', 'prose_files': prose_files,
                'task_path': str(artifact('task.json')), 'result_path': str(artifact('result.json')),
                'project_path': str(workspace.project), 'host_log_path': str(artifact('host.log')),
                'process': {'project_path': str(workspace.project), 'task_path': str(artifact('task.json')),
                            'log_path': str(artifact('host.log'))},
                'requires_new_worker': task['reviewer'] is None, 'review_session': task['reviewer'], 'version': VERSION,
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
    identity = {'schema': IDENTITY, 'task_id': task['id'], 'input_hash': task['input_hash'],
                'stage': work['stage'], 'stages': envelope['stages'], 'chapter': work['chapter'],
                'scope': work['scope'], 'delivery_phase': envelope['delivery_phase'],
                'requires_new_worker': envelope['requires_new_worker'], 'review_session': task['reviewer'],
                'project_path': str(workspace.project), 'task_path': envelope['task_path'],
                'entry': str(entry), 'version': VERSION,
                'worker_env': {'NOVEL_TASK_ID': task['id'], 'NOVEL_SESSION': task['reviewer']},
                'note': '本文件是派工身份的可核对副本，不授予权限：read/recall/patch/first-read 仍只对'
                        '宿主注入 NOVEL_TASK_ID 与 NOVEL_SESSION 的派工进程开放；NOVEL_SESSION 为空表示'
                        '本次由新会话自行命名。'}
    validate_identity(identity)
    identity_file = artifact('identity.json')
    json_write(identity_file, identity)
    envelope['identity_path'] = str(identity_file)
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
        keys = ('schema', 'version', 'task_id', 'input_hash', 'stage', 'chapter', 'scope',
                'delivery_phase', 'task_path', 'identity_path', 'requires_new_worker', 'review_session', 'claim')
        return {key: envelope[key] for key in keys}
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
