"""v2.1 验证骨架：反例矩阵共用的驱动、就绪探测与记账（V 写域，`validation/**`）。

被 `repro_hook_matrix.py`、`repro_hook_chain.py`、`repro_style_window.py` 复用。三条纪律：

* **就绪探测（readiness）**：引擎的 v2.1 接线还没落地时，脚本报 `blocked`（退出码 2），
  不把「引擎还没实现」写成「反例没被拒」——那样会把实现进度误报成缺陷。
* **期望对照（expect）**：每条用例声明它期望 `rejected` 还是 `accepted`；不一致才记 NOT AS EXPECTED
  （退出码 1），并在报告里给出实际的错误码/错误消息/findings。
* **可复读（JSON）**：完整结果写 `<script>.json`（默认落在临时目录，可用 `--out` 指定），
  报告正文只印表格与关键片段，便于粘进 `validation/v2.1-verification.md`。
"""
import argparse
import copy
import json
import sys
import tempfile
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'tests')]

from novel_ledger.bootstrap import local_application as Application          # noqa: E402
from novel_ledger.contracts import Error                                     # noqa: E402
from novel_ledger.sqlite_store import SQLiteRepository                       # noqa: E402
import support                                                               # noqa: E402
from support import contract, response, seeded_book                          # noqa: E402

_TEMPORARIES = []
_REPOS = []


def close_projects():
    while _REPOS:
        try:
            _REPOS.pop().close()
        except Exception:                               # noqa: BLE001 - a closed handle is fine
            pass
    try:                                                # leave the fixtures as we found them
        support.set_hooks_default(None)
    except Exception:                                   # noqa: BLE001 - older fixture builds
        pass


def hooks_supported():
    """Whether the drift side declares the v2.1 hook fields (spec §1.1/§1.2)."""
    from novel_ledger import drift
    return ('hooks' in tuple(getattr(drift, 'VOLUME_FIELDS', ()))
            and 'hooks' in tuple(getattr(drift, 'CHAPTER_FIELDS', ()))
            and 'hook' in tuple(getattr(drift, 'ITEM_KINDS', ())))


def hooks_status():
    """(ready, reason) for the hook chain, from the fixture owner's behavioural probe.

    `support.hooks_ready()` runs a hook-bearing volume outline through the validator: a `NameError`
    means the drift side has not landed yet, any structured refusal means the path executed. That is
    exactly the question this harness has to answer before it may call an accepted case a defect —
    the field tables can land before the helper bodies do.
    """
    probe = getattr(support, 'hooks_ready', None)
    if probe is None:
        ready = hooks_supported()
        return ready, 'fixture 侧没有 hooks_ready 探针；退回字段表探测：drift 声明 hooks=%s' % ready
    if probe():
        return True, 'ok'
    return False, ('support.hooks_ready() 为假（字段表已声明=%s）：drift 的钩子链尚未完整落地，'
                   '此时「用例被接受」是实现进度而不是缺陷。' % hooks_supported())


def hooks_ready():
    return hooks_status()[0]


def style_ready():
    """Whether `style.py` exists with the frozen API, and whether `workflow.apply` consumes it."""
    try:
        from novel_ledger import style, workflow
    except ImportError as exc:
        return False, 'style 模块不可导入：%s' % exc
    missing = [name for name in ('metrics', 'baseline', 'compare', 'window_of') if not hasattr(style, name)]
    if missing:
        return False, 'style 缺少冻结接口：%s' % ','.join(missing)
    if not hasattr(workflow, 'style'):
        return False, 'workflow.apply 尚未并入 style.compare（workflow 未导入 style）'
    return True, 'ok'


def open_project(raw=None, chapters=4, volumes=2, guided=False, hooks=True):
    """A seeded project, ready to drive.

    No controller lease is taken here: `application.run(...)` is what authorizes a window, and a
    case that needs one calls it explicitly (`app.run(owner=<previous>)` keeps the same identity, so
    repeated authorizations do not fight over the lease). `advance(owner=None)` is legal while no
    lease is held, which is how the counterexample cases drive the pipeline.

    `hooks=True` forces the fixture's hook declarations on for the session. Without it a receipt can
    carry empty `hooks` arrays whenever the fixture default follows a probe, and a hook case then
    tampers with nothing — an earlier run of this matrix reported ten false negatives that way.
    `close_projects()` puts the fixture default back.
    """
    if hooks:
        support.set_hooks_default(True)
    temporary = tempfile.TemporaryDirectory()
    _TEMPORARIES.append(temporary)
    book = seeded_book(raw if raw is not None else contract(chapters=chapters, volumes=volumes))
    repo = SQLiteRepository.initialize(Path(temporary.name) / 'book', book)
    _REPOS.append(repo)
    app = Application(repo)
    return repo, app, None


def play(app, owner, tamper=None, on=None, until=None, limit=400):
    """Advance the book answering every dispatch, tampering with exactly one receipt.

    `tamper(data, task)` gets the receipt of the first dispatch whose stage is `on` (lowest chapter
    first). Returns `(stages, status, error, findings)` where status ∈
    `rejected`(Error) / `tampered`(submitted, continue inspecting) / `await_*` / a terminal action.
    """
    stages, tampered = [], False
    for _ in range(limit):
        handoff = app.advance(owner=owner)
        action = handoff['action']
        if action == 'await_author':
            app.approve(handoff['prose_hash'], 'v2.1 验收脚本：作者认可首章。', owner)
            continue
        if action == 'await_choice':
            board = handoff['board']
            app.opening_choice(board['options'][0]['id'], board['hash'], 'v2.1 验收脚本。', owner)
            continue
        if action == 'outline_ready':
            book = app.repo.load()
            owner = app.run(through=book['contract']['volumes'][-1]['end'], owner=owner,
                            source='v2.1 验收脚本：作者授权开写。')['owner']
            continue
        if action != 'task_ready':
            return stages, action, None, []
        task = app.repo.pending()['input']
        stages.append(task['stage'])
        result = response(app)
        if task['stage'] in ('write', 'repair', 'redesign'):
            _pad_prose(app, task, result)
        if tamper is not None and not tampered and task['stage'] == on:
            tamper(result['data'], task)
            tampered = True
            try:
                app.submit(result)
            except Error as exc:
                return stages, 'rejected', exc, []
            return stages, 'tampered', None, list((app.repo.load().get('draft') or {}).get('findings') or [])
        try:
            app.submit(result)
        except Error as exc:
            return stages, 'rejected', exc, []
        if until and task['stage'] == until:
            return stages, 'until', None, []
    return stages, 'limit-reached', None, []


def draft_findings(app):
    return list((app.repo.load().get('draft') or {}).get('findings') or [])


def _pad_prose(app, task, result):
    """Lift the engineering stub to the contract's chapter minimum, then rebuild its self-comparison.

    Without this a probe on a real tier's band (t1+: 1800+ 汉字) never lands in the word budget, the
    draft is routed to repair, and the run pauses after two rounds — an artefact of the stub, not of
    the mechanism under test. Every 25-character window of `long_prose` is chapter-unique, so the
    cross-chapter duplication lint stays quiet; the drift_check is rebuilt against the padded text
    because each evidence quote has to be a verbatim fragment of what is actually submitted.
    """
    from novel_ledger.contracts import han_count
    from support import drift_check_fixture, long_prose
    need = (app.repo.load().get('contract') or {}).get('chapter_min', 0)
    data = result.get('data') or {}
    if han_count(data.get('prose') or '') >= need:
        return result
    data['prose'] = long_prose(task['chapter'])
    data['drift_check'] = drift_check_fixture(app, task, data['prose'])
    return result


def outcome_of(status, error, findings):
    """A compact, comparable description of what the engine did."""
    if error is not None:
        rows = ((error.details or {}).get('findings') if isinstance(error.details, dict) else None) or []
        return {'kind': 'rejected', 'code': error.code, 'message': error.message,
                'criteria': sorted({row.get('criterion') for row in rows if isinstance(row, dict)}),
                'first_finding': rows[0] if rows else None}
    if status == 'tampered':
        return {'kind': 'accepted', 'criteria': sorted({row.get('criterion') for row in findings}),
                'findings': findings[:3]}
    return {'kind': status}


def run_cases(title, specs, *, blocked=None, out=None, argv=None):
    """Run one case per spec, compare with its `expect`, print a table, return the exit code.

    `expect` ∈ {'rejected', 'accepted'}. `blocked` is a reason string: when set, every case is
    reported `blocked` and the exit code is 2 (the engine is not wired yet — no claim is made).
    """
    parser = argparse.ArgumentParser(description=title)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--only', help='按子串筛选用例名')
    args = parser.parse_args(argv)
    selected = [spec for spec in specs if not args.only or args.only in spec['name']]
    report, bad = {}, 0
    try:
        if blocked:
            for spec in selected:
                report[spec['name']] = {'case': spec['name'], 'expect': spec['expect'],
                                        'verdict': 'blocked', 'blocked': blocked}
        else:
            for spec in selected:
                try:
                    value = spec['fn']()
                except BaseException as exc:            # noqa: BLE001 - reported, not swallowed
                    value = {'kind': 'error', 'error': '%s: %s' % (type(exc).__name__, exc),
                             'traceback': traceback.format_exc().splitlines()[-5:]}
                verdict = ('ok' if value.get('kind') == spec['expect'] else 'NOT AS EXPECTED')
                report[spec['name']] = {'case': spec['name'], 'expect': spec['expect'],
                                        'verdict': verdict, 'observed': value,
                                        'fragment': value.pop('fragment', None)}
                if verdict != 'ok':
                    bad += 1
    finally:
        close_projects()
    for name, row in report.items():
        mark = {'ok': 'OK', 'blocked': 'BLOCKED', 'NOT AS EXPECTED': '<<< NOT AS EXPECTED'}[row['verdict']]
        print('%-46s %-6s %s' % (name[:46], row['expect'], mark))
        if row['verdict'] == 'NOT AS EXPECTED':
            print('    ' + json.dumps(row['observed'], ensure_ascii=False)[:900])
        elif row['verdict'] == 'blocked':
            print('    blocked: ' + row['blocked'])
        elif row.get('fragment'):
            observed = row['observed']
            detail = observed.get('message') or json.dumps(observed.get('first_finding'),
                                                           ensure_ascii=False)[:160]
            print('    %s → %s %s' % (row['fragment'][:80],
                                      observed.get('code') or observed.get('kind'), detail or ''))
    destination = args.out or (Path(tempfile.gettempdir()) / (Path(sys.argv[0]).stem + '.json'))
    destination.write_text(json.dumps({'title': title, 'blocked': blocked, 'cases': report},
                                      ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if blocked:
        print('\n引擎未就绪，%d 条用例记 blocked（未作判定）：%s' % (len(selected), blocked))
        print('JSON: ' + str(destination))
        return 2
    print('\n%d/%d 条符合预期%s' % (len(selected) - bad, len(selected),
                                    '' if not bad else '（不一致见上）'))
    if not blocked and bad == len(selected):
        print('提示：全部用例都不符合「被拒」期望，通常意味着该机制尚未接线（实现落地中）；'
              '引擎侧宣布就绪后重跑本脚本即可。')
    print('JSON: ' + str(destination))
    return 1 if bad else 0


__all__ = ['ROOT', 'Application', 'Error', 'SQLiteRepository', 'close_projects', 'contract',
           'copy', 'draft_findings', 'hooks_ready', 'hooks_status', 'hooks_supported',
           'open_project', 'outcome_of', 'play', 'response', 'run_cases', 'seeded_book',
           'style_ready']
