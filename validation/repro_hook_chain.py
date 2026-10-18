"""v2.1 伏笔链自洽样例（spec §三.3）：2 卷，每卷 1 条 required + v1 一条跨卷 continuing。

    python validation/repro_hook_chain.py

断言（每条不一致都会让用例判 NOT AS EXPECTED，并打印实测值）：
1. 卷纲声明 2 条 required（每卷一条）+ v1 一条 `continues: true` 的跨卷承诺；
2. 章纲按窗口 plant/payoff；第一卷收卷时本卷 required 全 `paid`、跨卷条目仍 `open`；
3. 跨卷条目在下一卷兑现，且 `state.hooks[id]['due'] == 卷纲声明的 payoff[1]`；
4. 存在未兑现的 open 承诺时 `complete()` 被拒（`payoffs`）；全部兑现后 `complete()` 通过。

退出码：0 = 全部符合预期；1 = 有不一致；2 = 引擎未接线（blocked，不作判定）。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v21_harness import hooks_status, open_project, play, run_cases             # noqa: E402
from novel_ledger.contracts import Error                                        # noqa: E402

V1_REQUIRED = 'hook-v1-required'
V1_CARRY = 'hook-v1-carry'
V2_REQUIRED = 'hook-v2-required'
# `ready_to_complete` is the engine-side terminal when the run was authorized with `finish=True`;
# `complete()` is the controller's separate call, and that is what §三.3 asks this script to judge.
FINISHED = ('target_reached', 'ready_to_complete')


def _run(app, owner, through, finish=False):
    """Authorize a run window and drive it; returns (owner, status, error, stages)."""
    owner = app.run(through=through, finish=finish, owner=owner,
                    source='v2.1 验收脚本授权。')['owner']
    stages, status, error, _findings = play(app, owner)
    return owner, status, error, stages


def _complete(app, owner):
    try:
        return {'kind': 'accepted', 'result': app.complete(owner=owner)}
    except Error as exc:
        return {'kind': 'rejected', 'code': exc.code, 'message': exc.message}


def _hook_states(book):
    return {key: row.get('status') for key, row in (book['state'].get('hooks') or {}).items()}


def _missing(book, wanted=()):
    return sorted(set(wanted) - set((book['state'].get('hooks') or {})))


def case_chain_state():
    """§三.3 的链式断言：第一卷 required 兑现、跨卷仍 open、due 取 payoff[1]、下一卷兑现。"""
    repo, app, owner = open_project(chapters=4, volumes=2)
    book = app.repo.load()
    volumes = book['contract']['volumes']

    owner, mid_status, mid_error, mid_stages = _run(app, owner, volumes[0]['end'])
    mid = app.repo.load()
    middle = {'status': mid_status,
              'error': None if mid_error is None else '%s: %s' % (mid_error.code, mid_error.message),
              'hooks': _hook_states(mid),
              'missing': _missing(mid, (V1_REQUIRED, V1_CARRY)),
              'chapters': [row['n'] for row in repo.headers(mid['branch'])]}

    owner, end_status, end_error, end_stages = _run(app, owner, volumes[-1]['end'])
    final = app.repo.load()
    hooks = final['state'].get('hooks') or {}
    carry = hooks.get(V1_CARRY) or {}
    declared = {row['id']: row for row in
                (final.get('volumes_outline') or {}).get('v1', {}).get('hooks') or []}
    expected_due = (declared.get(V1_CARRY) or {}).get('payoff', [None, None])[1]

    problems = []
    if middle['missing']:
        problems.append('第一卷收卷时缺少声明的 hook：%s' % middle['missing'])
    if middle['hooks'].get(V1_REQUIRED) != 'paid':
        problems.append('第一卷 required 未在卷末兑现：%s' % middle['hooks'].get(V1_REQUIRED))
    if middle['hooks'].get(V1_CARRY) != 'open':
        problems.append('跨卷承诺在第一卷就被关闭（应保持 open）：%s' % middle['hooks'].get(V1_CARRY))
    if end_status not in FINISHED or end_error is not None:
        problems.append('全书未跑到终点（%s）：%s %s' % ('/'.join(FINISHED), end_status, end_error))
    for ident in (V1_REQUIRED, V1_CARRY, V2_REQUIRED):
        if hooks.get(ident, {}).get('status') != 'paid':
            problems.append('%s 最终未 paid：%s' % (ident, hooks.get(ident)))
    if carry.get('due') != expected_due:
        problems.append('due 不等于卷纲声明的 payoff[1]：got %s want %s' % (carry.get('due'), expected_due))
    if carry.get('due') != volumes[1]['first']:
        problems.append('跨卷 due 不等于下一卷首章：got %s want %s'
                        % (carry.get('due'), volumes[1]['first']))
    if [row['n'] for row in repo.headers(final['branch'])] != list(range(1, 5)):
        problems.append('章号不连续：%s' % [row['n'] for row in repo.headers(final['branch'])])

    value = {'kind': 'accepted' if not problems else 'contradicted',
             'middle': middle,
             'final': {'status': end_status,
                       'error': None if end_error is None else '%s: %s' % (end_error.code, end_error.message),
                       'hooks': {key: {'status': row.get('status'), 'due': row.get('due')}
                                 for key, row in hooks.items()},
                       'due_expected': expected_due,
                       'chapters': [row['n'] for row in repo.headers(final['branch'])]},
             'problems': problems,
             'stages': mid_stages + end_stages,
             'fragment': '卷纲 v1 hooks = %s' % sorted(declared)}
    return value


def case_complete_refuses_open_hook():
    """A promise planted and never paid must stop `complete()` with the unaccounted-promise check."""
    def add_open_hook(data, task):
        data['volumes'][0]['hooks'].append({'id': 'hook-never-paid',
                                            'text': '读者记住这张凭据，作者尚未安排兑现的那一章。',
                                            'plant': [1, 1], 'payoff': [5, 6],
                                            'required': False, 'continues': True})
        return 'volumes[0].hooks 追加 continues=true、payoff=[5,6]（超出全书末章）的 hook-never-paid'

    def plant_it(data, task):
        data['chapters'][0].setdefault('hooks', []).append(
            {'hook': 'hook-never-paid', 'action': 'plant', 'note': '埋下但永不兑现。'})
        return 'chapters[0].hooks 追加 plant hook-never-paid'

    repo, app, owner = open_project(chapters=4, volumes=2)
    book = app.repo.load()
    play(app, owner, tamper=add_open_hook, on='volume_outline')
    play(app, owner, tamper=plant_it, on='chapter_outline')
    owner, status, error, stages = _run(app, owner, book['contract']['volumes'][-1]['end'], finish=True)
    final = app.repo.load()
    value = _complete(app, owner)
    value['chain_status'] = status
    value['chain_error'] = None if error is None else '%s: %s' % (error.code, error.message)
    value['hooks'] = _hook_states(final)
    value['chapters'] = [row['n'] for row in repo.headers(final['branch'])]
    value['fragment'] = 'complete() 面对一个 open 的 hook-never-paid'
    if status not in FINISHED or error is not None:
        value['kind'] = 'contradicted'
        value['problems'] = ['跑到终点前停了（%s）：%s %s' % ('/'.join(FINISHED), status, value['chain_error'])]
    elif value.get('kind') == 'rejected' and value.get('code') != 'payoffs':
        value['kind'] = 'contradicted'
        value['problems'] = ['被拒但错误码不是 payoffs：%s' % value.get('code')]
    return value


def case_complete_passes_when_all_paid():
    """The clean chain: every declared promise paid by the last chapter, `complete()` goes through."""
    repo, app, owner = open_project(chapters=4, volumes=2)
    book = app.repo.load()
    owner, status, error, stages = _run(app, owner, book['contract']['volumes'][-1]['end'], finish=True)
    final = app.repo.load()
    value = _complete(app, owner)
    value['chain_status'] = status
    value['chain_error'] = None if error is None else '%s: %s' % (error.code, error.message)
    value['hooks'] = _hook_states(final)
    value['chapters'] = [row['n'] for row in repo.headers(final['branch'])]
    value['fragment'] = 'complete() 在全部 hook 已 paid 时'
    if status not in FINISHED or error is not None:
        value['kind'] = 'contradicted'
        value['problems'] = ['自洽链没有跑到终点（%s）：%s %s' % ('/'.join(FINISHED), status, value['chain_error'])]
    elif not (value.get('kind') == 'accepted' and (value.get('result') or {}).get('completed')):
        value['kind'] = 'contradicted'
        value['problems'] = ['complete() 没有返回 completed=true：%s' % value.get('result')]
    return value


CASES = (
    {'name': '链01 卷末 required 全 paid、跨卷仍 open 并在下卷兑现', 'expect': 'accepted',
     'fn': case_chain_state},
    {'name': '链02 complete() 在存在未兑现承诺时被拒', 'expect': 'rejected',
     'fn': case_complete_refuses_open_hook},
    {'name': '链03 complete() 在全部兑现后通过', 'expect': 'accepted',
     'fn': case_complete_passes_when_all_paid},
)


def main(argv=None):
    ready, why = hooks_status()
    reason = None if ready else (why + ' 自洽链要在 drift 的钩子状态机落地后才有意义。')
    return run_cases('v2.1 伏笔链自洽样例', CASES, blocked=reason, argv=argv)


if __name__ == '__main__':
    sys.exit(main())
