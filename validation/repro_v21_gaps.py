"""v2.1 独立验证发现的引擎缺口（最小复现）——GAP 脚本。

    python validation/repro_v21_gaps.py

两个 spec 合法、却跑不通的配置：

**GAP-1 合并档位 + 跨卷伏笔**：t0/t1 的卷纲派工把「本批各卷的卷纲 + 各卷章纲」放在同一份回执里
（`PIPELINE_SHAPES[tier].merge_chapter_outline`）。第 2 卷的首章要兑现第 1 卷声明的跨卷伏笔
（`continues: true`），而校验章纲那一半时用的伏笔登记表里没有同一份回执里刚声明的这些 hook →
引擎报 `design_drift 章纲形状/引用核账未通过`，finding 为
`{chapter: 3, kind: hook, key: hook-v1-carry, criterion: chapter_hook, expect: '本卷声明或前卷未兑现的 id', got: null}`。
即：**t0/t1 档、多卷的项目在第一次卷纲派工处就装不进去**。

**GAP-2 非合并档位 + `chapter_outline.scope='all'`**：spec §2 的 `scope=all` 指「先把全书章纲链
铺在纸上再落笔」，引擎也照此把第 2 卷的章纲排在第 1 章之前。但 `context.build` 为那一批读
`previous_chapters`（锚点前 2 章）时那些章还不存在，抛 `Error('正式章节不存在')`。

两个对照组说明差异来自「合并」与「scope=all」本身，而不是档位或卷数：
- 控制组 A：t1 档 2 卷 + 卷纲 `scope=rolling`（一次一卷，回执里没有跨卷 carry）→ 应通过；
- 控制组 B：t2 档 2 卷 + `scope=volume`（默认）→ 应通过。

期望：四个用例都应跑到终点；观察到 GAP-1/GAP-2 被判 NOT AS EXPECTED（退出码 1）。
修好后本脚本转绿，可作为回归门槛。退出码：0 = 全部符合预期；1 = 有缺口；2 = 环境未就绪。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v21_harness import open_project, play, run_cases                            # noqa: E402
from novel_ledger.contracts import Error, PIPELINE_SHAPES, SCALE_TIERS           # noqa: E402

FINISHED = ('target_reached', 'ready_to_complete')


def _contract(tier_id, chapters, volumes, chapter_scope, volume_scope='all'):
    from support import contract
    tier = next(row for row in SCALE_TIERS if row['id'] == tier_id)
    raw = contract(chapters=chapters, volumes=volumes)
    raw.update(chapter_min=tier['chapter_min'], chapter_max=tier['chapter_max'],
               chapter_aim=tier['chapter_aim'])
    raw['chapter_outline'] = {'scope': chapter_scope, 'words': 150, 'tolerance': 60}
    raw['volume_outline'] = {'scope': volume_scope, 'words': 1000, 'tolerance': 100}
    return raw


def _drive(raw):
    """Run the whole book; return a comparable outcome (status / error code+message / findings)."""
    repo, app, owner = open_project(raw=raw, hooks=True)
    volumes = app.repo.load()['contract']['volumes']
    owner = app.run(through=volumes[-1]['end'], owner=owner, source='v2.1 缺口复现。')['owner']
    try:
        stages, status, error, findings = play(app, owner)
    except Error as exc:                    # raised outside submit (e.g. context.build in advance)
        return {'kind': 'error', 'code': exc.code, 'message': exc.message,
                'chapters': [row['n'] for row in repo.headers('main')],
                'volumes_outline': sorted(app.repo.load().get('volumes_outline') or {})}
    book = app.repo.load()
    value = {'kind': 'accepted' if status in FINISHED and error is None else 'rejected',
             'stages': stages,
             'status': status if error is None else None,
             'error': None if error is None else '%s: %s' % (error.code, error.message),
             'findings': ((error.details or {}).get('findings')[:2] if error is not None else findings[:2]),
             'chapters': [row['n'] for row in repo.headers(book['branch'])],
             'volumes_outline': sorted(book.get('volumes_outline') or {})}
    return value


def case_merged_cross_volume():
    raw = _contract('t1', 4, 2, chapter_scope='all')
    value = _drive(raw)
    value['fragment'] = 't1 档（merge_chapter_outline=%s）2 卷 + chapter_outline.scope=all' % \
                        PIPELINE_SHAPES['t1']['merge_chapter_outline']
    value['problems'] = [] if value['kind'] == 'accepted' else [
        'GAP-1：合并回执里的跨卷伏笔在章纲那一半校验时不可见（%s）' % (value.get('error') or value.get('status'))]
    return value


def case_merged_rolling_control():
    """控制组 A：合并档位 + 卷纲 rolling + 章节 scope=volume。

    一次一卷的合并回执里没有「后一卷的章在执行同一回执里前一卷声明的跨卷伏笔」这种情况，
    因此它应当能跑通——这条对照把 GAP-1 与档位本身、与 GAP-2（scope=all）区分开。
    """
    raw = _contract('t1', 4, 2, chapter_scope='volume', volume_scope='rolling')
    value = _drive(raw)
    value['fragment'] = '控制组 A：t1 档 2 卷 + 卷纲 scope=rolling + 章节 scope=volume'
    value['problems'] = [] if value['kind'] == 'accepted' else [
        '控制组 A 也没有跑通：%s（说明差异不只是跨卷 carry）' % (value.get('error') or value.get('status'))]
    return value


def case_scope_all_unmerged():
    raw = _contract('t2', 4, 2, chapter_scope='all')
    value = _drive(raw)
    value['fragment'] = 't2 档（merge_chapter_outline=%s）2 卷 + chapter_outline.scope=all' % \
                        PIPELINE_SHAPES['t2']['merge_chapter_outline']
    value['problems'] = [] if value['kind'] == 'accepted' else [
        'GAP-2：scope=all 时后续卷的章纲早于前卷正文，previous_chapters 读不到（%s）'
        % (value.get('error') or value.get('status'))]
    return value


def case_scope_volume_control():
    raw = _contract('t2', 4, 2, chapter_scope='volume')
    value = _drive(raw)
    value['fragment'] = '控制组 B：t2 档 2 卷 + chapter_outline.scope=volume（默认）'
    value['problems'] = [] if value['kind'] == 'accepted' else [
        '控制组 B 也没有跑通：%s' % (value.get('error') or value.get('status'))]
    return value


def case_merged_default_shape():
    """GAP-1 的最严重形态：合并档位 + 2 卷 + **契约默认形状**（章节 scope=volume，卷纲 scope=all）。

    这正是 support.contract() 与 CONTRACT_FIELDS 默认值给出的形状，也是 t1 档（volume_count=2）
    最普通的开书方式——它连第一次卷纲派工都过不去。
    """
    raw = _contract('t1', 4, 2, chapter_scope='volume', volume_scope='all')
    value = _drive(raw)
    value['fragment'] = 't1 档 2 卷 + 默认形状（卷纲 scope=all、章节 scope=volume）'
    value['problems'] = [] if value['kind'] == 'accepted' else [
        'GAP-1b：默认形状的 t1 两卷项目也装不进卷纲（%s）' % (value.get('error') or value.get('status'))]
    return value


CASES = (
    {'name': 'GAP-1 合并档位 + 跨卷伏笔（t1，2 卷，章节 scope=all）', 'expect': 'accepted',
     'fn': case_merged_cross_volume},
    {'name': 'GAP-1b 合并档位 + 默认形状（t1，2 卷，章节 scope=volume）', 'expect': 'accepted',
     'fn': case_merged_default_shape},
    {'name': '对照A 合并档位 + 卷纲 rolling（无跨卷回执）', 'expect': 'accepted',
     'fn': case_merged_rolling_control},
    {'name': 'GAP-2 非合并档位 + 章纲 scope=all（t2，2 卷）', 'expect': 'accepted',
     'fn': case_scope_all_unmerged},
    {'name': '对照B 非合并档位 + 章纲 scope=volume', 'expect': 'accepted',
     'fn': case_scope_volume_control},
)


def main(argv=None):
    code = run_cases('v2.1 引擎缺口回归门槛（GAP-1/GAP-1b/GAP-2 + 两个对照）', CASES, argv=argv)
    print('\n说明：三个 GAP 用例在 2026-10-18 23:10 之前是 rejected（当时确实被挡住/崩掉），'
          '缺口修复后改为 accepted，本脚本自此是回归门槛：任何一条跑不到终点即为回归。')
    return code


if __name__ == '__main__':
    sys.exit(main())
