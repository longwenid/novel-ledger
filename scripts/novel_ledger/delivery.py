"""Rebuildable task views and book export. No lifecycle decisions."""
from __future__ import annotations

import html
import json
import os
import sys
import time
import uuid
from pathlib import Path
from .contracts import FIRST_READ, FORM_ARTIFACTS, RESULT, VERSION, digest, dump, require
from .world import LABELS, SECTIONS
from .quality import template


def atomic_write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name('.' + path.name + '-' + uuid.uuid4().hex)
    try:
        temporary.write_text(content, encoding='utf-8')
        os.replace(str(temporary), str(path))
    finally:
        temporary.unlink(missing_ok=True)


def json_write(path, value):
    atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


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


def retire(base):
    """Drop regenerable artifacts so a stale task view cannot be reused."""
    for name in FORM_ARTIFACTS:
        (Path(base) / name).unlink(missing_ok=True)


def materialize(repo, task, entry, baseline=None):
    work = task['input']
    base = repo.project / 'work' / task['id']
    locked = work['blind'] and not task['first_read']
    prose_files = []
    for ref in work['prose']:
        path = base / ('chapter-' + str(ref['chapter']) + '.txt')
        atomic_write(path, repo.read_document(ref['hash']))
        prose_files.append({**ref, 'path': str(path)})
    command = [sys.executable, str(entry), '--project', str(repo.project)]
    lease = repo.get('claim:' + task['id'])
    envelope = {'schema': work['schema'], 'task_id': task['id'], 'input_hash': task['input_hash'],
                'stage': work['stage'], 'chapter': work['chapter'], 'scope': work['scope'],
                'delivery_phase': 'first_read' if locked else 'formal', 'prose_files': prose_files,
                'task_path': str(base / 'task.json'), 'result_path': str(base / 'result.json'),
                'requires_new_worker': True, 'version': VERSION,
                # An in-flight claim tells the dispatcher whether another worker still owns this
                # task: an expired one is reclaimable, a live one is not a re-dispatch candidate.
                'claim': ({'session': lease['session'], 'expired': lease['until'] <= time.time()}
                          if lease else None),
                # The ledger baseline is a read-only projection: dispatchers forward it instead of
                # hand-summarizing balances, and workers use it to sanity-check precondition values.
                'baseline': baseline,
                'commands': {'submit': command + ['submit', '--file', str(base / 'result.json')],
                             'preflight': command + ['preflight', '--file', str(base / 'result.json')],
                             'read': command + ['read', '--task', task['id']]}}
    reference_dir = Path(entry).parent.parent / 'references'
    # Guides are optional reference material per stage; the dispatch's own brief carries what the
    # task needs, so whole documents are not shipped on every round.
    guides = {'opening_options': ('opening.md', 'hatch.md'), 'opening_contract': ('opening.md', 'world.md'),
              'world_model': ('world.md',), 'world_review': ('world.md',), 'volume_plan': ('hatch.md',)}
    also = tuple((work['payload'] or {}).get('also', ()))
    names = list(guides.get(work['stage'], ()))
    for extra_stage in also:
        names.extend(name for name in guides.get(extra_stage, ()) if name not in names)
    if names:
        envelope['guides'] = [str(reference_dir / name) for name in names]
    envelope['stages'] = [work['stage'], *also]
    # The commands below are rendered from this process, so they work as long as this installation
    # does. Say so, and say what to do when it has moved: a stale path is refreshed by another
    # `advance`, never by rewriting the command by hand.
    envelope['note'] = ('commands 用当前安装的真实路径生成：' + command[0] + ' + ' + str(entry) +
                        '。若技能目录已移动导致路径不存在，回主控再执行一次 advance 刷新任务视图，'
                        '不要手改命令，也不要凭印象判定路径失效（宿主可用目录联接映射同一份安装）。')
    if locked:
        first_path = base / 'first-read.json'
        if not first_path.exists():
            json_write(first_path, {'task_id': task['id'], 'input_hash': task['input_hash'], 'session': '',
                                   'data': {'reads': [dict(chapter=r['chapter'], **{k: '' for k in FIRST_READ}) for r in work['prose']]}})
        envelope['first_read_path'] = str(first_path)
        envelope['commands']['first_read'] = command + ['first-read', '--file', str(first_path)]
        # A blind task hands out no formal material; any earlier render is retired here.
        retire(base)
    else:
        # The view carries the task's own material; record hashes live in task.json alone, so the
        # same map is not delivered twice.
        view = {'task_id': task['id'], 'input_hash': task['input_hash'],
                **{key: value for key, value in work.items() if key != 'records'},
                'first_read': task['first_read'], 'first_read_hash': task['first_read_hash']}
        json_write(base / 'input.json', view)
        template_path = base / 'result.template.json'
        # The form belongs to the Worker once minted: rebuilding a view must never blank a
        # half-filled form. A form minted for another task is stale and is replaced.
        if not form_is_current(template_path, task):
            result = {'schema': RESULT, 'task_id': task['id'], 'input_hash': task['input_hash'],
                      'session': task['reviewer'] or '',
                      'data': template(work['stage'], work['chapter'], {r['chapter']: '' for r in work['prose']},
                                       work['obligations'], also)}
            json_write(template_path, result)
        envelope.update(input_path=str(base / 'input.json'), template_path=str(template_path), records=work['records'], required=work['required'])
    json_write(base / 'task.json', envelope)
    return envelope


def export_book(repo, output=None, format='html'):
    book = repo.load()
    require(book.get('contract') is not None, 'contract', '尚无生效约定，不能导出正文。',
            {'recover': '先完成开书：init --contract、opening --file 或逐门开书的约定核验。'})
    output = Path(output).expanduser().resolve() if output else repo.project / ('book.' + ('html' if format == 'html' else 'md'))
    if output.name == 'book.html' and output.parent == repo.project:
        # 全书视图 owns this path; an implicit export would silently replace it with a plain render.
        require(False, 'output', 'book.html 是全书视图的输出位置；导出请用 --output 指定其他文件，或改用 html 命令。',
                {'recover': '例如 --output book-export.html（或 --format md 得到 book.md）。'})
    require(not (output.parent == repo.project and output.name.startswith('novel.sqlite3')), 'output', '不能覆盖数据库及其事务文件。')
    rows = repo.headers(book['branch'])
    candidate = book['branch'] != repo.get('official_branch', 'main')
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
    return {'path': str(output), 'chapters': len(rows), 'branch': book['branch'], 'candidate': candidate, 'inside_project': output.is_relative_to(repo.project)}


def export_world(repo):
    book = repo.load()
    model = book.get('world')
    require(model is not None and book.get('world_review') is not None, 'world_view', '世界模型尚未通过独立核验。')
    json_path, html_path = repo.project / 'world.json', repo.project / 'world.html'
    json_write(json_path, {'selection_hash': model['selection_hash'], 'model_hash': digest(model),
                          'choices': book['creation']['selections'], 'world': model, 'review': book['world_review']})
    field_labels = {'name': '名称', 'environment': '环境', 'resources': '资源', 'access': '通行条件', 'story_pressure': '情节压力',
        'period': '时期', 'event': '历史事件', 'consequence': '后果', 'present_effect': '当下影响', 'principle': '规则原理',
        'scope': '适用范围', 'limits': '限制', 'consequences': '违反后果', 'goal': '诉求', 'power': '力量来源',
        'dependencies': '依赖', 'conflicts': '冲突', 'resource': '核心资源', 'production': '生产', 'distribution': '分配',
        'scarcity': '稀缺', 'conflict': '矛盾', 'institution': '制度', 'norm': '习惯', 'enforcement': '执行方式',
        'pressure': '社会压力', 'practice': '日常行为', 'constraint': '约束', 'story_use': '故事作用', 'role': '身份与作用',
        'desire': '欲望', 'limit': '底线', 'knowledge_boundary': '知情边界', 'truth': '隐秘内容', 'disclosure': '披露安排',
        'causal_role': '因果作用', 'cost': '代价', 'failure_condition': '失效条件'}
    pieces = ['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>世界设定</title>',
              '<style>body{max-width:60em;margin:3em auto;padding:0 1em;line-height:1.8}section{margin:3em 0}article{border-top:1px solid #ddd;padding:1em 0}dt{font-weight:bold}dd{margin:0 0 .7em;white-space:pre-wrap}</style>',
              '<h1>世界设定</h1><p>' + html.escape(model['premise']) + '</p><h2>已选方向</h2><ol>']
    for selection in book['creation']['selections']:
        pieces.append('<li>' + html.escape(selection['option']['title'] + '：' + selection['option']['premise']) + '</li>')
    pieces.append('</ol><h2>长篇承载</h2><p>' + html.escape(model['story_capacity']) + '</p>')
    for section, fields in SECTIONS.items():
        pieces.append('<section><h2>' + LABELS[section] + '</h2>')
        if not model[section]:
            pieces.append('<p>按已选方向，不设置特殊机制。</p>')
        for row in model[section]:
            pieces.append('<article><dl>')
            for field in fields:
                pieces.append('<dt>' + field_labels[field] + '</dt><dd>' + html.escape(row[field]) + '</dd>')
            pieces.append('</dl></article>')
        pieces.append('</section>')
    pieces.append('</html>')
    atomic_write(html_path, '\n'.join(pieces))
    return {'html_path': str(html_path), 'json_path': str(json_path), 'model_hash': digest(model)}
