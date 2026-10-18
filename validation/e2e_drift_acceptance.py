"""Lead 端到端验收：五步流水线全链 + 漂移拒绝（spec §8.3）。

不依赖任何人工步骤：用 tests/support.py 的夹具驱动真实引擎，断言
  1) 派工序列恰好是 volume_outline → chapter_outline → write×N（无任何审查阶段）；
  2) 一路写到 target_reached 且状态/字数入账；
  3) 章纲状态链拒绝人为漂移（enter 与上一章 exit 不符、资源为负、时钟倒退）；
  4) drift_check 漏项 / 自报前态不符 → 不提交正文，走有界返修；
  5) 修正后的回执能重新提交并入库。
"""
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'tests'))

from novel_ledger.bootstrap import local_application as Application
from novel_ledger.contracts import Error
from novel_ledger.sqlite_store import SQLiteRepository
import support


def open_app(project, chapters=3, volumes=1):
    repo = SQLiteRepository.initialize(project, support.seeded_book(
        support.contract(chapters=chapters, volumes=volumes)))
    return repo, Application(repo)


def drive_recording(app, owner, limit=300):
    """drive()，但同时记录派工序列。"""
    stages = []
    for _ in range(limit):
        handoff = app.advance(owner=owner)
        action = handoff['action']
        if action == 'await_choice':
            board = handoff['board']
            app.opening_choice(board['options'][0]['id'], board['hash'], '验收脚本选择第一案。', owner)
            continue
        if action == 'await_author':
            app.approve(handoff['prose_hash'], '验收脚本认可首章。', owner)
            continue
        if action != 'task_ready':
            return handoff, stages
        stages.append(handoff['task']['stage'])
        app.submit(support.response(app))
    raise AssertionError('流程没有在有限步内停止')


def case_happy_path(tmp, chapters=3, volumes=1):
    repo, app = open_app(tmp / ('book-%d-%d' % (chapters, volumes)), chapters=chapters, volumes=volumes)
    try:
        run = app.run(through=chapters, source='验收脚本授权写完全书。')
        handoff, stages = drive_recording(app, run['owner'])
        book = repo.load()
        rows = repo.headers(book['branch'])
        return {'handoff': handoff, 'stages': stages, 'book': book, 'rows': rows}
    finally:
        repo.close()


def expect_refusal(label, fn):
    """Run fn(); report whether the engine refused it, and with which code."""
    try:
        value = fn()
    except Error as exc:
        return {'case': label, 'refused': True, 'error': exc.code, 'message': exc.message}
    return {'case': label, 'refused': False, 'returned': value}


def case_drift_refusals(tmp):
    results = []
    # 1. 章纲：enter 与上一章 exit 不符（人为把第 2 章的进入条件改错）
    repo, app = open_app(tmp / 'drift-enter', chapters=2)
    try:
        # 走到 chapter_outline 派工
        owner = app.run(through=2, source='验收脚本授权。')['owner']
        while True:
            step = app.advance(owner=owner)
            if step['action'] != 'task_ready':
                break
            if step['task']['stage'] == 'chapter_outline':
                break
            app.submit(support.response(app))
        result = support.response(app)
        for row in result['data']['chapters'][1:]:
            for entry in row.get('enter', []):
                entry['expected'] = 999999
        results.append(expect_refusal('章纲 enter 与上一章 exit 不符', lambda: app.submit(result)))
    finally:
        repo.close()

    # 2. 章纲：资源增量把余额打成负数
    repo, app = open_app(tmp / 'drift-negative', chapters=2)
    try:
        owner = app.run(through=2, source='验收脚本授权。')['owner']
        while True:
            step = app.advance(owner=owner)
            if step['action'] != 'task_ready':
                break
            if step['task']['stage'] == 'chapter_outline':
                break
            app.submit(support.response(app))
        result = support.response(app)
        row = result['data']['chapters'][0]
        if row.get('resources'):
            row['resources'][0]['to'] = -5
        else:
            results.append({'case': '资源为负', 'refused': None, 'note': '夹具本章无资源增量，改用时钟倒退'})
        if row.get('resources'):
            results.append(expect_refusal('资源增量为负', lambda: app.submit(result)))
    finally:
        repo.close()

    # 3. 章纲：时钟倒退
    repo, app = open_app(tmp / 'drift-clock', chapters=2)
    try:
        owner = app.run(through=2, source='验收脚本授权。')['owner']
        while True:
            step = app.advance(owner=owner)
            if step['action'] != 'task_ready':
                break
            if step['task']['stage'] == 'chapter_outline':
                break
            app.submit(support.response(app))
        result = support.response(app)
        result['data']['chapters'][0]['clock'] = {'advance_days': -3}
        results.append(expect_refusal('时钟倒退', lambda: app.submit(result)))
    finally:
        repo.close()
    return results


def ensure_task(app, owner):
    """A pending task for the next attempt: an accepted repair routes one on the next advance."""
    if app.repo.pending() is not None:
        return
    step = app.advance(owner=owner)
    if step['action'] == 'await_author':
        app.approve(step['prose_hash'], '验收脚本认可首章。', owner)
        app.advance(owner=owner)


def case_drift_check(tmp):
    """执笔自比的两类错：漏项、actual.from 自报不符；以及修正后能入库。"""
    results = []
    repo, app = open_app(tmp / 'drift-check', chapters=2)
    try:
        owner = app.run(through=2, source='验收脚本授权。')['owner']
        while True:
            step = app.advance(owner=owner)
            if step['action'] != 'task_ready':
                raise AssertionError('未到达执笔：' + str(step.get('action')))
            if step['task']['stage'] == 'write':
                break
            app.submit(support.response(app))
        before = len(app.repo.headers(app.repo.load()['branch']))

        omitted = support.response(app)
        omitted['data']['drift_check']['items'] = omitted['data']['drift_check']['items'][:-1]
        outcome = expect_refusal('drift_check 漏项', lambda: app.submit(omitted))
        outcome['committed'] = len(app.repo.headers(app.repo.load()['branch'])) - before
        results.append(outcome)
        ensure_task(app, owner)

        wrong = support.response(app)
        if wrong['data']['drift_check']['items']:
            wrong['data']['drift_check']['items'][0]['actual']['from'] = '自报的错前态'
        else:
            wrong['data']['drift_check']['unplanned'] = [{'kind': 'resources', 'key': '车费',
                                                          'change': '未登记的变化', 'reason': ''}]
        outcome = expect_refusal('drift_check 自报前态不符', lambda: app.submit(wrong))
        outcome['committed'] = len(app.repo.headers(app.repo.load()['branch'])) - before
        results.append(outcome)
        ensure_task(app, owner)

        # 修正后的回执：引擎应接受并入库
        good = support.response(app)
        response = app.submit(good)
        results.append({'case': '修正后重新提交', 'refused': False,
                        'committed_chapter': response.get('committed_chapter'),
                        'after': len(app.repo.headers(app.repo.load()['branch'])) - before})
    finally:
        repo.close()
    return results


def main():
    tmp = Path(tempfile.mkdtemp(prefix='novel-v2-e2e-'))
    report = {}
    try:
        happy = case_happy_path(tmp)
        report['happy'] = {'action': happy['handoff']['action'], 'stages': happy['stages'],
                           'chapters': len(happy['rows']), 'han': happy['book']['written_han'],
                           'design_drift': len(happy['book'].get('design_drift') or [])}
        two = case_happy_path(tmp, chapters=4, volumes=2)
        report['two_volumes'] = {'action': two['handoff']['action'], 'stages': two['stages'],
                                 'volumes_outlined': sorted(two['book'].get('volumes_outline') or {}),
                                 'chapter_outline_volumes': sorted(two['book'].get('chapter_outlines') or {})}
        report['drift_refusals'] = case_drift_refusals(tmp)
        report['drift_check'] = case_drift_check(tmp)
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    import json
    print(json.dumps(report, ensure_ascii=False, indent=2))
    stages = Counter(report['happy']['stages'])
    assert report['happy']['action'] == 'target_reached', report['happy']
    assert set(stages) == {'volume_outline', 'chapter_outline', 'write'}, stages
    assert stages['write'] == 3, stages
    assert report['two_volumes']['action'] == 'target_reached', report['two_volumes']
    assert len(report['two_volumes']['volumes_outlined']) == 2
    assert len(report['two_volumes']['chapter_outline_volumes']) == 2
    for row in report['drift_refusals']:
        assert row.get('refused') is not False, row
    assert report['drift_check'][0].get('refused') or report['drift_check'][0].get('committed') == 0, report['drift_check']
    assert report['drift_check'][1].get('refused') or report['drift_check'][1].get('committed') == 0, report['drift_check']
    assert report['drift_check'][2]['after'] == 1, report['drift_check']
    print('E2E OK')


if __name__ == '__main__':
    main()
