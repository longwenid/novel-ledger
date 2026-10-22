"""Rebuildable task views and book export. No lifecycle decisions."""
from __future__ import annotations

import html
import json
import shlex
import sys
import time
from pathlib import Path
from .catalog import GENRE_CATALOG
from .contracts import FORM_ARTIFACTS, IDENTITY, RESULT, VERSION, EXECUTION, CONTROLLER_STAGES, execution_recovery, digest, require, text
from .result_templates import template
from .ports import PublicationReader
from .publication import publication
from .workspace import LocalWorkspace, atomic_write
from .envelope import validate_identity, validate_task
from . import catalog, store_keys


def json_write(path, value):
    atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


# What a prose writer re-reads every chapter (and after every context compression): the chapter's
# own outline, the tail of the previous chapter, the live state and the anchors. Everything else —
# contract, world, volume outline — is group-start material the worker has already internalized,
# so it lands in a separate reference file read on demand instead of being re-read per chapter.
PACK_RECORDS = ('chapter_outline', 'previous_chapters', 'state', 'style_anchor', 'word_budget',
                'hooks', 'author_feedback')
PACK_TAIL_CHARS = 2500


def pack_markdowns(result):
    """One writing pack and one reference pack, in reading order, from a read response.

    Measured on a real fast-group run: a worker re-read six to eight material files per chapter
    (each read a full-context model round-trip), and a compressed context forced it to re-read
    everything. Two files turn that into one read per chapter: `read_pack.md` for the chapter's
    own material, `read_ref.md` for the rest. Nothing is summarized — sections are verbatim; only
    the previous chapter is tailed, because continuity lives at its end.
    """
    records = (result or {}).get('records') or {}

    def section(name, value):
        body = json.dumps(value, ensure_ascii=False, allow_nan=False)
        if name == 'previous_chapters' and len(body) > PACK_TAIL_CHARS:
            body = body[:120] + '\n…（前文省略，连续性只需要结尾；全文见 read_pack.json）…\n' + body[-PACK_TAIL_CHARS:]
        return '## ' + name + '\n```\n' + body + '\n```\n'

    pack_names = [name for name in PACK_RECORDS if name in records]
    ref_names = [name for name in records if name not in pack_names]
    head = '# 材料包：%s\n' % result.get('task_id', '') + \
           '写作每章与上下文被压缩后，只读本文件；其余材料在 read_ref.md，按需再读。\n\n'
    pack = head + ''.join(section(name, records[name]['value']) for name in pack_names)
    reference = '# 参考材料：%s\n' % result.get('task_id', '') + \
                '组首通读一次即可；仅在需要核对设定细节时再读。\n\n' + \
                ''.join(section(name, records[name]['value']) for name in ref_names)
    return {'read_pack.md': pack, 'read_ref.md': reference}


# The author-facing card for one choice board. The controller hands this file's content over
# verbatim instead of re-deriving a presentation from the JSON return: a live run had to redirect
# advance's stdout to a file (GBK consoles garble UTF-8) and then hand-write a markdown card for
# every gate, paying main-session tokens to re-render what the engine already knows.
# Advisory groups the engine may attach to a board. Each keeps its own heading: a naming note and a
# "this setting is already taken" note are different conversations, and folding them under one title
# would read as one problem. Nothing here blocks a choice — the author decides — so the card renders
# them as advice, never as a rejection reason.
BOARD_WARNINGS = (
    ('name_warnings', '命名提示'),
    ('premise_warnings', '设定同质化提示'),
)


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
    for key, title in BOARD_WARNINGS:
        rows = [row for row in board.get(key) or [] if isinstance(row, dict)]
        if not rows:
            continue
        lines.append('## ' + title)
        lines.extend('- %s%s' % (('方案%s：' % row['option']) if row.get('option') else '',
                                 row.get('message') or row.get('code') or '')
                     for row in rows)
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

    Capped at four options because common ask components cap the list there: a live controller
    facing that cap silently dropped the fixed actions (and once offered only 4 of the 12
    categories as the whole first gate). Custom input is the host's Other/free-text field, so the
    folding loses nothing; the full board stays in board.md for the chat text.
    """
    gate = board.get('gate') or {}
    letters = 'ABCDEF'
    options = []
    for index, option in enumerate(board.get('options') or []):
        tag = letters[index] if index < len(letters) else str(index + 1)
        summary = option.get('pitch') if text(option.get('pitch')) else option.get('premise')
        options.append({'label': '%s %s' % (tag, option.get('title', '')), 'description': summary or ''})
    options.append({'label': '换一组 / 自定义',
                    'description': '这一组都不合适：说明理由（如“格局太小”“不够爽”）我按理由重出一组；'
                                   '想自己定就直接在自定义/Other 里写方向或内容。'})
    options = options[:4]
    number, total, title = gate.get('number', '?'), gate.get('total', '?'), gate.get('title', '')
    return {'questions': [{'header': '第 %s/%s 门%s' % (number, total, '（新一组）' if board.get('round') else ''),
                           'question': '第 %s 门（%s）：选哪个？' % (number, title),
                           'multiSelect': False, 'options': options}]}


def render_catalog_card(catalog):
    """The first gate's category spread, as chat text rather than ask options.

    The protocol always meant the twelve categories to reach the author as text before the ask;
    a live controller facing a four-option ask component instead offered four categories as if
    they were the whole catalog. The card makes the spread a mechanical paste.
    """
    lines = ['# 开书第一门：先收一个题材方向',
             '',
             '下面是全部类目；回复一个类目名（或混搭、自定义方向）即可，之后的方案在这一门内深化：',
             '']
    lines.extend('- %s：%s' % (name, hook) for name, hook in catalog)
    lines.append('')
    return '\n'.join(lines) + '\n'


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
    if sys.platform == 'win32':
        return '& ' + ' '.join("'%s'" % part.replace("'", "''") for part in argv)
    return shlex.join(argv)


def render_dispatch_card(envelope, identity):
    """The worker bootstrap card, rendered by the engine from the frozen dispatch itself.

    Hand-written dispatch prompts drift from what the engine enforces (a live run taught a worker
    to run `claim` and the boundary guard rejected it), and every cold worker paid a role_boundary
    round to learn the env bootstrap. The card carries the exact preamble and steps once, from the
    same source the guards check against; the controller forwards the path instead of re-authoring
    the protocol.
    """
    stage = envelope['stage']
    if stage in CONTROLLER_STAGES:
        lines = ['# 主控自执卡：' + stage, '',
                 identity.get('task_line', ''),
                 '任务：`' + envelope['task_path'] + '`；读同目录 brief.md，按模板只填 data 和主控真实 session。',
                 '开书门不创建 Worker，无需 claim/prepare-worker，也不使用 Worker 环境自举。',
                 '执行 read 后按当前模板起稿，check 通过再 submit；字段问题按错误与模板修正，不查内部接口猜格式。', '']
        for name in ('read', 'check', 'submit'):
            if (envelope.get('commands') or {}).get(name):
                lines.append('- %s：%s' % (name, _quoted_argv(envelope['commands'][name])))
        if envelope.get('stale_result_session'):
            lines.append('遗留草稿已隔离：上次会话 %s 的未提交 result.json 已移到 result.stale.json；从当前模板起稿。'
                         % envelope['stale_result_session'])
        return '\n'.join(lines) + '\n'
    claim = envelope.get('claim')
    if claim is None:
        claim_lines = ['- 本任务 claim=null：开书门由主控自执；其他阶段须先由主控 prepare-worker 绑定真实会话。'
                       'Worker 不执行 claim，不从旧任务寻找或复制 session。']
    else:
        state = '已过期' if claim.get('expired') else '生效中（session=%s）' % claim.get('session')
        claim_lines = ['- 本任务已有租约（%s）：未过期沿用原会话；过期由主干重新认领，Worker 不执行 claim。' % state]
    session = identity['worker_env'].get('NOVEL_SESSION')
    session_line = ("    $env:NOVEL_SESSION='%s'" % session.replace("'", "''") if session else
                    "    if (-not $env:NOVEL_SESSION) { throw '缺少宿主执行身份：由主干注入真实会话标识，不得自拟。' }")
    commands = envelope.get('commands') or {}
    steps = ['1. 读 `task.json` 与 `brief.md`；`guides` 列出本任务对应参考文档，按需再读。',
             '2. 执行一次无参数 read（命令见下）把必读记录拿齐；确需某份再 read --record 名称。',
             '3. 复制 `result.template.json` 为 `result.json` 起稿，只改 data；'
             'Python worker 入口在内存中注入真实 session/execution_claim，不写回草稿；schema/task_id/input_hash 不手写。',
             '4. 执行 commands.preflight 试算：不通过时返回 valid=false 与全量 findings——这是返修数据不是错误，'
             '不计失败，把全部问题合并成一版修改——以完整段落或场景为单位重写，不逐条小改反复试算'
             '（每轮试算都重读全部上下文，是最高成本动作）；'
             '按 findings 的 expect/got 与 recovery 修正；stalled=true 表示连续多轮未收敛，停止盲试并把全量 findings 交回主控；'
             '不为确认格式读引擎源码。长起草期间可先拿半成品回执跑 check：既保租约心跳，又能提前拿 findings。',
             '5. `submit` 提交；worker_boundary=finished 后结束：不自行 advance，不执行作者或主干命令，不改写 commands/guides。']
    command_names = ('ready', 'read', 'check', 'preflight', 'submit')
    if stage == 'write' and 'receipt' in (envelope.get('commands') or {}):
        # The same one-write-one-assembly flow outside a group: prose goes in the draft file,
        # the receipt assembles around it and answers the mechanical report in the same call.
        steps[2] = ('3. 把成稿一次写入任务目录 `draft.md`（一次 write 完整章节，不逐段追加），'
                    '执行 commands.receipt 本地组装回执：信封、drift_check.items 与 actual.from 投影由引擎填好，'
                    '响应含机械报告（字数区间/lint/文风代理）——不达标按报告一轮修完 draft 再重跑 receipt，'
                    'clean 后核对每行 status/reason/quote 如实；schema/task_id/input_hash 不手写。')
        command_names = (*command_names, 'receipt')
    if envelope.get('worker_batch'):
        group = envelope['worker_batch']
        steps[0] = ('1. 读 `task.json` 与 `brief.md`；本任务不是本组首章时，guides 与首章相同，'
                    '已读可跳过，仅按需补读。')
        steps[2] = ('3. 执笔章把成稿一次写入任务目录 `draft.md`（完整章节，不逐段追加），'
                    '执行 commands.receipt 本地组装回执：信封、drift_check.items 与 actual.from 投影由引擎填好，'
                    '核对每行 status/reason/quote 如实后按需小改；返修章仍从 result.template.json 起稿。')
        steps[-1] = ('5. 本组范围第 %s～%s 章，每章固定序列（模型调用预算 ≤8 次/章，每个工具调用都是一次全上下文模型往返，省一步即省一步的钱）：'
                     '① commands.worker_next 取新任务与凭据，只按返回更新 NOVEL_TASK_ID/NOVEL_TASK_PATH/NOVEL_EXECUTION_CLAIM，保留同一 NOVEL_SESSION；'
                     '② 一次 commands.read 取增量材料并 --save 落盘，之后每章与上下文被压缩后只读 read_pack.md（章纲/前章尾/状态/锚）；'
                     '参考材料在 read_ref.md，仅在核对设定细节时读；禁止逐条 --record 重读未变更记录；'
                     '③ 成稿一次写入 draft.md（一次 write 完整章节，不逐段追加）；'
                     '④ commands.receipt 组装：响应含全量机械报告（字数区间/lint/文风代理），不达标按报告一轮修完 draft（整段替换，不逐句小改）再重跑 receipt，clean 后核对 status/quote/reason；'
                     '⑤ commands.preflight（机械报告已绿时通常一次过）；⑥ commands.submit。'
                     'worker_boundary=continue 回到 ①；finished 或 batch_finished 后结束；不得自行 advance 或处理作者决定。'
                     '调用纪律：不用 ls/dir/探查命令翻目录，不用 python 逐字段查看 result.json，不开后台任务再轮询输出——'
                     '这些每一次都是全价模型调用；不确定格式用一次 check，不猜不翻。'
                     % (group['first'], group['last']))
        command_names = (*command_names, 'worker_next', 'receipt')
    lines = ['# Worker 自举卡：%s' % stage,
             '',
             identity.get('task_line') or ('本任务：stage=%s。' % stage),
             '任务文件（唯一权威）：`%s`；简报全文：同目录 `brief.md`（不必解析 input.json）。' % envelope['task_path'],
             '',
             '## 1. 执行准备（Python 入口，跨平台）',
             '',
             '步骤 0（凭据门槛）：NOVEL_SESSION/NOVEL_EXECUTION_CLAIM 注入之前，只允许本地读 task.json 与 brief.md；'
             '缺 NOVEL_SESSION 时不重试任何引擎命令，直接把 worker_identity 交回主控。',
             '先由主控启动真实 Worker 并取得宿主会话 ID，再 prepare-worker；宿主将返回的 worker_env 仅交给该 Worker。',
             'identity 中 session 为空不是让你找旧身份；缺失或不匹配立即带错误码交回主控，不读正文、不遍历历史任务。',
             '首条 commands.read 会自动验证 ready，失败不会交付材料；commands.ready 仅用于诊断，不必另起模型轮次探测。Python 入口无需某一种 shell 的初始化脚本。',
             '宿主不能注入环境时，可在 worker 的 -- 前显式传 --session 与 --execution-claim；只用主控当次返回的值，不写入任务文件。',
             '',
             '### POSIX 环境示例（macOS/Linux，宿主已注入时不重复设置）',
             '    export NOVEL_TASK_ID=' + shlex.quote(envelope['task_id']),
             '    export PYTHONIOENCODING=utf-8',
             '    # NOVEL_SESSION / NOVEL_EXECUTION_CLAIM 由宿主提供；缺失交回主控。',
             '',
             '### PowerShell 环境示例（Windows，宿主已注入时不重复设置）',
             '',
             '    $env:PYTHONIOENCODING=\'utf-8\'',
             '    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8',
             "    $env:NOVEL_TASK_ID='%s'" % envelope['task_id'],
             session_line,
             '',
             '身份、角色、租约错误立即交回主控；其他技术错误按 details.recovery.retry_allowed 执行。连续错误达到 limit 后停止，主控修复原因后显式重开。',
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
    if envelope.get('stale_result_session'):
        lines += ['',
                  '## 遗留草稿已隔离',
                  '',
                  '- 目录里发现上一次派工未提交的回执草稿（session=%s），已改名为 `result.stale.json`。'
                  '它不代表本任务任何进度，也不是你的判断依据（核验任务尤其别读它——独立性从空白起算）；'
                  '从 `result.template.json` 起稿，直接覆盖提交。' % envelope['stale_result_session']]
    lines += ['',
              '## 4. 常见坑',
              '',
              '- commands 是 argv 数组：逐项传参，不拼 shell 字符串，不改路径。',
              '- 控制台 GBK 会乱码：中文内容走文件工件（brief.md、work/board.md、work/question.json），'
              '不在控制台打印长 JSON；自行重定向时 PowerShell 5 的 `Out-File -Encoding utf8` 带 BOM，读回用 utf-8-sig。',
              '- 完成后向主控只报状态：task_id、valid/accepted/committed、worker_boundary、'
              'committed_chapter、错误或拒绝摘要（含 code）；accepted=true 不等于章节落库，不贴正文或完整回执。']
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
        chapter = ('chapter=%s' % work['chapter'] if not work.get('first') or work.get('first') == work.get('chapter')
                   else 'chapters=%s-%s' % (work['first'], work['last']))
        parts.append(chapter)
    parts.append('required=' + ','.join(work.get('required') or ()) or 'required=(无)')
    return '本任务：' + '；'.join(parts) + '。派工说明以此为准，不要按流程位置想象。'


# Work directory ownership. `work/<task>/` mixes two kinds of file:
#   controller-authored, rebuildable: task.json, input.json
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


def baseline_projection(repo: PublicationReader, task, given=None):
    """The true before-state of one dispatch, for a writer's self-comparison.

    A `drift_check` row's `actual.from` is checked against the engine's own projection, not against
    what the writer remembers, so the writer is handed the same numbers: the clock, resource
    balances, where everyone stands, who knows what, the promises still open, and the live
    candidate. Everything here is read from the scoped state this dispatch already froze — a caller
    may pass `given` for the parts that live on the book rather than in the task (the candidate),
    and the projection fills in the rest instead of trusting a hand-written summary.
    """
    state = repo.read_document(task['input']['records']['state'])
    view = {'clock': state.get('clock'),
            'resources': dict(sorted((state.get('resources') or {}).items())),
            'placements': dict(sorted((state.get('placements') or {}).items())),
            'knowledge': dict(sorted((state.get('knowledge') or {}).items())),
            'open_hooks': [{'id': ident, 'due': hook.get('due'), 'text': hook.get('text', '')}
                           for ident, hook in sorted((state.get('hooks') or {}).items())
                           if hook.get('status') == 'open'],
            'candidate': None,
            'source': '本表是引擎投影的真实前态，只读参考：drift_check 的 actual.from 以它为准，不要自报前态。'}
    if isinstance(given, dict):
        # Caller-supplied values win where they exist (the live candidate is not frozen material),
        # but they can never remove a projection field: a dispatcher that forgot one would otherwise
        # silently shrink the baseline back to the shape this exists to replace.
        view.update({key: value for key, value in given.items() if value is not None})
    return view


def materialize(repo: PublicationReader, task, entry, baseline=None, compact=False, *, workspace: LocalWorkspace, preserve_result=False):
    work = task['input']
    base = workspace.artifact_path('work/' + task['id'])
    def artifact(name):
        return workspace.artifact_path(base / name)

    command = [sys.executable, str(entry), '--project', str(workspace.project)]
    lease = repo.get(store_keys.claim(task['id']))
    batch = work.get('payload', {}).get('worker_batch')
    # The envelope, its identity copy and the compact controller view all describe the same dispatch.
    # They are derived from one mapping so a shared field cannot be added to one of them and forgotten
    # in the others — which is how a controller ends up reading a stage the worker never got.
    shared = {'task_id': task['id'], 'input_hash': task['input_hash'], 'stage': work['stage'],
              'chapter': work['chapter'], 'scope': work['scope'],
              'delivery_phase': 'formal',
              'requires_new_worker': task['reviewer'] is None and not lease,
              'review_session': task['reviewer'] or (lease or {}).get('session')}
    envelope = {'schema': work['schema'], **shared,
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
                # hand-summarizing balances, and workers compare their prose against it.
                'baseline': baseline_projection(repo, task, baseline),
                'commands': {'submit': command + ['submit', '--file', str(artifact('result.json'))],
                             'preflight': command + ['preflight', '--file', str(artifact('result.json'))],
                             'read': command + ['read', '--task', task['id']],
                             'recall': command + ['recall', '--task', task['id']]}}
    failure = repo.get(store_keys.technical_failure(task['id'])) or {}
    controller_stage = work['stage'] in CONTROLLER_STAGES
    prepared = bool(lease and lease['until'] > time.time())
    envelope['execution'] = {'schema': EXECUTION,
                             'state': ('controller' if controller_stage else 'blocked' if failure.get('blocked')
                                       else 'ready' if prepared else 'await_worker_identity'),
                             'session': shared['review_session'],
                             'recovery': execution_recovery(failure.get('code', ''), failure.get('failures', 0))}
    if not controller_stage:
        envelope['commands']['report_error'] = command + ['worker-error', '--task', task['id']]
        direct = envelope['commands']
        envelope['commands'] = {name: command + ['worker', '--task', task['id'], '--'] + argv[len(command):]
                                for name, argv in direct.items()}
        envelope['commands']['ready'] = command + ['worker', '--task', task['id'], '--', 'worker-ready', '--task', task['id']]
    envelope['commands']['check'] = (command if controller_stage else command + ['worker', '--task', task['id'], '--']) + ['check', '--task', task['id'], '--file', str(artifact('result.json'))]
    worker_command = command if controller_stage else command + ['worker', '--task', task['id'], '--']
    if work['stage'] == 'write':
        # Mechanical assembly is an engine command, not model work: the receipt writes itself
        # from the draft plus the projections, and the writer keeps the verdicts and quotes.
        envelope['commands']['receipt'] = worker_command + ['receipt', '--task', task['id'],
                                                            '--prose', str(artifact('draft.md'))]
    if batch:
        envelope['worker_batch'] = batch
        envelope['commands']['worker_next'] = worker_command + ['worker-next', '--task', task['id']]
    if work.get('capabilities', {}).get('editorial') and work['stage'] in ('repair', 'redesign'):
        envelope['commands']['patch'] = worker_command + ['patch', '--task', task['id']]
    reference_dir = Path(entry).parent.parent / 'references'
    # Guides are optional reference material per stage; the dispatch's own brief carries what the
    # task needs, so whole documents are not shipped on every round. Only stages that actually have
    # a brief appear here: a guide for a stage with no rules to explain is a document nobody reads.
    guides = {'opening_options': ('opening.md', 'hatch.md'), 'opening_contract': ('opening.md', 'world.md'),
              'world_model': ('world.md',), 'volume_outline': ('hatch.md',),
              'chapter_outline': ('hatch.md',)}
    if work.get('capabilities', {}).get('editorial'):
        guides[work['stage']] = (*guides.get(work['stage'], ()), 'editorial.md')
    if work.get('capabilities', {}).get('understanding'):
        guides[work['stage']] = (*guides.get(work['stage'], ()), 'workbench.md')
    also = tuple((work['payload'] or {}).get('also', ()))
    names = list(guides.get(work['stage'], ()))
    if work['stage'] not in ('opening_options', 'world_model', 'opening_contract'):
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
                'worker_env': {'NOVEL_TASK_ID': task['id'],
                               'NOVEL_SESSION': task['reviewer'] or (lease or {}).get('session')},
                # What this dispatch is, rendered from the frozen task itself. A controller that
                # describes the work from an assumed pipeline position instead of from here can hand a
                # worker a task it is not (a revision-scope review announced as the book's final
                # review); reading this line prevents that, and costs one sentence per dispatch.
                'task_line': task_line(work),
                'note': '本文件是派工身份的可核对副本，不授予权限：read/recall/patch 仍只对'
                        '宿主注入 NOVEL_TASK_ID 与 NOVEL_SESSION 的派工进程开放；NOVEL_SESSION 为空表示'
                        '须由宿主提供真实执行身份，不能自行编造；这些声明不证明模型上下文隔离。'}
    validate_identity(identity)
    identity_file = artifact('identity.json')
    json_write(identity_file, identity)
    envelope['identity_path'] = str(identity_file)
    # The brief rides inside input.json as one long JSON string, which console tools truncate or
    # garble; the markdown twin is what readers actually open.
    brief_text = envelope.get('brief') or work.get('brief')
    if text(brief_text):
        brief_file = artifact('brief.md')
        atomic_write(brief_file, brief_text)
        envelope['brief_path'] = str(brief_file)
    if work['stage'] == 'opening_options' and (work.get('payload') or {}).get('gate', {}).get('id') == 'genre' \
            and not (work.get('payload') or {}).get('round'):
        # The first gate's category spread, materialized so the controller pastes it instead of
        # improvising under the ask component's option cap.
        catalog_file = artifact('catalog.md')
        atomic_write(catalog_file, render_catalog_card(GENRE_CATALOG))
        envelope['catalog_path'] = str(catalog_file)
    # A re-render of an unsubmitted task may find the previous attempt's half-written receipt in
    # the directory — a live reviewer found one sitting beside the blank form, one dropped
    # session away from being read as their own judgment (or submitted under someone else's
    # session). Quarantine it out of the worker's way before the dispatch card mentions it; the
    # ledger, not the work directory, is the receipt of record. Safe because re-rendering while
    # a worker is actively writing is already outside the dispatch protocol (wait for the
    # worker, then `advance --after`).
    prior_view = artifact('task.json')
    prior = None
    if prior_view.exists():
        try:
            prior = json.loads(prior_view.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            prior = None
        stale = artifact('result.json')
        same_batch_worker = bool(batch and lease and isinstance(prior, dict)
                                 and prior.get('review_session') == lease.get('session'))
        if not preserve_result and isinstance(prior, dict) and prior.get('input_hash') == envelope['input_hash'] and stale.exists() and not same_batch_worker:
            try:
                stale_receipt = json.loads(stale.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                stale_receipt = None
            if isinstance(stale_receipt, dict) and stale_receipt.get('session'):
                stale.replace(artifact('result.stale.json'))
                envelope['stale_result_session'] = stale_receipt['session']
    dispatch_file = artifact('dispatch.md')
    atomic_write(dispatch_file, render_dispatch_card(envelope, identity))
    envelope['dispatch_path'] = str(dispatch_file)
    # The commands below are rendered from this process, so they work as long as this installation
    # does. Say so, and say what to do when it has moved: a stale path is refreshed by another
    # `advance`, never by rewriting the command by hand.
    envelope['note'] = ('commands 用当前安装的真实路径生成：' + command[0] + ' + ' + str(entry) +
                        '。若技能目录已移动导致路径不存在，回主控再执行一次 advance 刷新任务视图，'
                        '不要手改命令，也不要凭印象判定路径失效（宿主可用目录联接映射同一份安装）。')
    # The view carries the task's own material; record hashes live in task.json alone, so the
    # same map is not delivered twice.
    view = {'task_id': task['id'], 'input_hash': task['input_hash'],
            **{key: value for key, value in work.items() if key != 'records'}}
    json_write(artifact('input.json'), view)
    template_path = artifact('result.template.json')
    # The form belongs to the Worker once minted: rebuilding a view must never blank a
    # half-filled form. A form minted for another task is stale and is replaced.
    if not form_is_current(template_path, task):
        result = {'schema': RESULT, 'task_id': task['id'], 'input_hash': task['input_hash'],
                  'session': shared['review_session'] or '',
                  'data': template(work['stage'], work['chapter'], also, work['payload'],
                                   work.get('narrative_tracking', False))}
        json_write(template_path, result)
    envelope.update(input_path=str(artifact('input.json')), template_path=str(template_path), records=work['records'], required=work['required'])
    # Two facts a controller cannot otherwise see: how many times this dispatch view has been
    # rendered (a second render for one task is a double dispatch, and used to be invisible), and
    # what it costs to read. Both are read off the artifacts themselves, so the read-only
    # delivery surface needs no new persistence capability.
    task_file = artifact('task.json')
    # This view is disposable: malformed JSON (including a final symlink's target) must not
    # prevent rebuilding the task from its immutable database input.
    previous = prior
    prior_count = previous.get('redispatch_count') if isinstance(previous, dict) else None
    envelope['redispatch_count'] = (prior_count + 1
                                    if type(prior_count) is int and prior_count >= 0
                                    and previous.get('input_hash') == envelope['input_hash'] else 1)
    envelope['material_bytes'] = sum(path.stat().st_size for path in
                                     (artifact('input.json'), artifact('result.template.json'))
                                     if path.exists())
    validate_task(envelope)
    json_write(task_file, envelope)
    if compact:
        # Keep the controller's context small; workers always receive the complete on-disk envelope.
        # The shared dispatch fields are listed from the same mapping the envelope was built from.
        keys = ('schema', 'version', *shared, 'task_path', 'identity_path', 'brief_path', 'dispatch_path',
                'claim', 'redispatch_count', 'stale_result_session', 'catalog_path', 'worker_batch', 'execution')
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
    require(model is not None, 'world_view', '世界模型尚未生成，无法导出世界观。',
            {'recover': '先完成 world_model 派工并提交世界模型。'})
    json_path = workspace.artifact_path(workspace.project / 'world.json')
    html_path = workspace.artifact_path(workspace.project / 'book.html')
    # A book imported from a hand-written contract has no opening record, so its world carries no
    # selection hash; the export must still work for it (only the hash is absent, not the world).
    json_write(json_path, {'selection_hash': model.get('selection_hash'),
                           'model_hash': digest(model),
                           'choices': (book.get('creation') or {}).get('selections', []), 'world': model})
    atomic_write(html_path, render(repo))
    return {'html_path': str(html_path), 'json_path': str(json_path), 'model_hash': digest(model)}
