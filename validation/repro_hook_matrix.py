"""v2.1 伏笔链反例矩阵（spec §三.2）：每条都必须被拒，且报错可读。

    python validation/repro_hook_matrix.py                 # 全部用例
    python validation/repro_hook_matrix.py --only plant    # 按子串筛选

退出码：0 = 全部符合预期；1 = 有用例与期望不一致（引擎缺陷或夹具过期）；2 = 引擎未接线（blocked，不作判定）。

矩阵（10 条）：章纲 plant 未在卷纲声明 / payoff 早于 plant / 同一 hook plant 两次 / payoff 两次 /
plant 越窗 / payoff 越窗 / 卷末 required 未兑现 / `hook_refs` 承接未埋的 hook / 卷纲 required+越卷 /
卷纲窗口非法。

每条用例都在**全新项目**上跑：用仓库自带的 v2.1 夹具（`support.*`，hooks 默认随引擎探测）把书推到
目标派工，然后只改一处，再断言引擎的返回。篡改片段会原样打印，便于复核。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v21_harness import hooks_status, open_project, outcome_of, play, run_cases   # noqa: E402


def _chapter_of(data, number):
    return next(row for row in data['chapters'] if row['chapter'] == number)


def _row_hooks(data, number):
    row = _chapter_of(data, number)
    return row.setdefault('hooks', [])


# --------------------------------------------------------------------------- 章纲级反例
def tamper_plant_undeclared(data, task):
    """章纲 plant 了一个卷纲没声明的 id。"""
    row = data['chapters'][0]
    row['hooks'] = [{'hook': 'hook-ghost', 'action': 'plant', 'note': '未在卷纲声明的承诺。'}]
    return 'chapters[0].hooks -> plant hook-ghost（卷纲未声明）'


def tamper_payoff_before_plant(data, task):
    """第 1 章就 payoff，第 2 章才 plant：兑现早于埋设。"""
    _chapter_of(data, 1)['hooks'] = [{'hook': 'hook-v1-required', 'action': 'payoff',
                                      'note': '先兑现。'}]
    _chapter_of(data, 2)['hooks'] = [{'hook': 'hook-v1-required', 'action': 'plant',
                                      'note': '后埋设。'}]
    return 'ch1 payoff → ch2 plant（顺序颠倒）'


def tamper_plant_twice(data, task):
    """同一个 id 埋两次。"""
    _row_hooks(data, 1).append({'hook': 'hook-v1-required', 'action': 'plant', 'note': '重复埋设。'})
    return 'ch1 与 ch2 都 plant hook-v1-required（重复埋设）'


def tamper_payoff_twice(data, task):
    """同一个 id 兑现两次（第 1 章补一次 payoff，第 2 章是夹具原有的 payoff）。"""
    _row_hooks(data, 1).append({'hook': 'hook-v1-required', 'action': 'payoff', 'note': '提前兑现。'})
    return 'ch1 与 ch2 都 payoff hook-v1-required（重复兑现）'


def tamper_plant_out_of_window(data, task):
    """plant 落在卷纲声明的 plant 窗口之外（窗口是 [1,1]，却在第 2 章埋）。"""
    _chapter_of(data, 1)['hooks'] = [row for row in _chapter_of(data, 1).get('hooks') or []
                                     if row.get('hook') != 'hook-v1-required']
    _row_hooks(data, 2).append({'hook': 'hook-v1-required', 'action': 'plant', 'note': '越窗埋设。'})
    return 'hook-v1-required plant 窗口 [1,1]，实际在第 2 章埋'


def tamper_payoff_out_of_window(data, task):
    """payoff 落在窗口之外（窗口 [2,2]，却在第 1 章兑现）。"""
    _chapter_of(data, 2)['hooks'] = [row for row in _chapter_of(data, 2).get('hooks') or []
                                     if row.get('hook') != 'hook-v1-required']
    _row_hooks(data, 1).append({'hook': 'hook-v1-required', 'action': 'payoff', 'note': '越窗兑现。'})
    return 'hook-v1-required payoff 窗口 [2,2]，实际在第 1 章兑现'


def tamper_required_never_paid(data, task):
    """卷末 required 未兑现：把本卷 required hook 的 payoff 整条删掉。"""
    for number in (1, 2):
        _chapter_of(data, number)['hooks'] = [row for row in _chapter_of(data, number).get('hooks') or []
                                              if not (row.get('hook') == 'hook-v1-required'
                                                      and row.get('action') == 'payoff')]
    return 'ch1/ch2 都删掉 hook-v1-required 的 payoff（卷末 required 未兑现）'


def tamper_hook_refs_unplanted(data, task):
    """hook_refs 承接一个还没埋的 id（跨卷 carry 尚未 plant）。"""
    _chapter_of(data, 1)['hook_refs'] = ['hook-v2-required']
    return 'ch1.hook_refs -> hook-v2-required（尚未 plant）'


# --------------------------------------------------------------------------- 卷纲级反例
def tamper_volume_required_across_volumes(data, task):
    """required=true 却把 payoff 写到卷外（跨卷必须 continues=true 且 required=false）。"""
    volume = data['volumes'][0]
    volume['hooks'].append({'id': 'hook-cross-required',
                            'text': '读者等着看这张凭据落到谁手里，本卷必须给答案。',
                            'plant': [1, 1], 'payoff': [3, 4],
                            'required': True, 'continues': False})
    return 'volumes[0].hooks 追加 required=true 且 payoff=[3,4]（越出卷末 2）'


def tamper_volume_illegal_window(data, task):
    """卷纲窗口非法：plant 窗口整体落在本卷章号区间之外。"""
    volume = data['volumes'][0]
    volume['hooks'].append({'id': 'hook-bad-window',
                            'text': '读者看到承诺，但这张承诺的埋设窗口不在本卷。',
                            'plant': [90, 91], 'payoff': [92, 93],
                            'required': True, 'continues': False})
    return 'volumes[0].hooks 追加 plant=[90,91]（本卷是 1..2）'


CASES = (
    {'name': '矩阵01 章纲 plant 未在卷纲声明', 'expect': 'rejected',
     'fn': lambda: _case('chapter_outline', tamper_plant_undeclared)},
    {'name': '矩阵02 payoff 早于 plant', 'expect': 'rejected',
     'fn': lambda: _case('chapter_outline', tamper_payoff_before_plant)},
    {'name': '矩阵03 同一 hook plant 两次', 'expect': 'rejected',
     'fn': lambda: _case('chapter_outline', tamper_plant_twice)},
    {'name': '矩阵04 同一 hook payoff 两次', 'expect': 'rejected',
     'fn': lambda: _case('chapter_outline', tamper_payoff_twice)},
    {'name': '矩阵05 plant 越窗', 'expect': 'rejected',
     'fn': lambda: _case('chapter_outline', tamper_plant_out_of_window)},
    {'name': '矩阵06 payoff 越窗', 'expect': 'rejected',
     'fn': lambda: _case('chapter_outline', tamper_payoff_out_of_window)},
    {'name': '矩阵07 卷末 required 未兑现', 'expect': 'rejected',
     'fn': lambda: _case('chapter_outline', tamper_required_never_paid)},
    {'name': '矩阵08 hook_refs 承接未埋的 hook', 'expect': 'rejected',
     'fn': lambda: _case('chapter_outline', tamper_hook_refs_unplanted)},
    {'name': '矩阵09 卷纲 required 且 payoff 越卷', 'expect': 'rejected',
     'fn': lambda: _case('volume_outline', tamper_volume_required_across_volumes)},
    {'name': '矩阵10 卷纲窗口非法', 'expect': 'rejected',
     'fn': lambda: _case('volume_outline', tamper_volume_illegal_window)},
)


def _case(stage, tamper):
    """One counterexample: fresh 2-volume project, one tampered receipt of `stage`."""
    repo, app, owner = open_project(chapters=4, volumes=2)
    box = {}

    def wrapped(data, task):
        box['fragment'] = tamper(data, task)
        return box['fragment']

    stages, status, error, findings = play(app, owner, tamper=wrapped, on=stage)
    value = outcome_of(status, error, findings)
    value['tampered_receipt'] = stage
    value['stages'] = stages
    value['fragment'] = box.get('fragment')
    return value


def main(argv=None):
    ready, why = hooks_status()
    reason = None if ready else (
        why + ' 就绪探测：python -c "import sys;sys.path[:0]=[\'scripts\',\'tests\'];'
              'import support;print(support.hooks_ready())"')
    return run_cases('v2.1 伏笔链反例矩阵', CASES, blocked=reason, argv=argv)


if __name__ == '__main__':
    sys.exit(main())
