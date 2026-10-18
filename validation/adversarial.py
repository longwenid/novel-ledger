"""V 验证位的对抗性验收（spec-v2 §8.3）：只看行为，不看实现。

    python validation/adversarial.py                # 全部用例
    python validation/adversarial.py --only chain   # 只跑名字里含 chain 的用例

每个用例都在一个**全新项目**上跑：用仓库自带的 v2 夹具把书推到目标阶段，然后只篡改一个字段
（篡改片段会打印出来），断言引擎的返回。用例分两类：

* **拒绝类**：人为漂移必须被挡下，并给出可读错误（`design_drift` / `drift_coverage` /
  `drift_before` / `insufficient_resource` …）。错误码或 findings 的 criterion 之一命中即算通过。
* **自洽类**：全部自洽的样例必须一路写到 `target_reached`，章章入库、状态正确结算、没有任何
  被删除的审查阶段派工。
"""
import argparse
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
from novel_ledger import stages as stage_names                               # noqa: E402
from support import contract, response, seeded_book                          # noqa: E402

DELETED_STAGES = frozenset({
    'world_review', 'contract_review', 'design_review', 'outline_review', 'chapter_review',
    'book_plan', 'volume_plan', 'plan', 'profiles',
    'scope_review', 'scope_synthesis', 'revision_review', 'alignment_plan', 'alignment_review',
})

_TEMPORARIES = []          # keep every TemporaryDirectory alive for the whole run
_REPOS = []                # and close every connection before those directories are cleaned up


def fresh_project(raw=None, chapters=4, volumes=2):
    """A new seeded project, returned with its app and a lease-holding owner.

    Four chapters over two volumes (v1 = chapters 1–2, v2 = 3–4): spec §8.3 asks for at least two
    volumes and three chapters, and the enter/exit chain needs a volume with more than one chapter
    to be observable at all.
    """
    temporary = tempfile.TemporaryDirectory()
    _TEMPORARIES.append(temporary)
    repo = SQLiteRepository.initialize(Path(temporary.name) / 'book',
                                       seeded_book(raw if raw is not None else contract(chapters=chapters, volumes=volumes)))
    _REPOS.append(repo)
    app = Application(repo)
    owner = app.run(through=chapters, source='对抗性验收：作者授权跑满全书。')['owner']
    return repo, app, owner


def close_projects():
    """Close every project opened by this run; Windows keeps the file locked until then."""
    while _REPOS:
        try:
            _REPOS.pop().close()
        except Exception:                               # noqa: BLE001 - a closed handle is fine
            pass


def play(app, owner, tamper=None, on=None, limit=40):
    """Drive the book, tampering with exactly one receipt; return (stages, outcome, findings, error).

    `tamper(data, task)` is applied to the first receipt whose stage is `on` (and, when the task
    carries a chapter, to the lowest chapter of that stage).
    """
    stages, tampered = [], False
    for _ in range(limit):
        handoff = app.advance(owner=owner)
        action = handoff['action']
        if action == 'await_author':
            app.approve(handoff['prose_hash'], '对抗性验收：作者认可首章。', owner)
            continue
        if action == 'await_choice':
            board = handoff['board']
            app.opening_choice(board['options'][0]['id'], board['hash'], '对抗性验收。', owner)
            continue
        if action != 'task_ready':
            return stages, {'action': action}, [], None
        task = app.repo.pending()['input']
        stages.append(task['stage'])
        result = response(app)
        if tamper is not None and not tampered and task['stage'] == on:
            fragment = tamper(result['data'], task)
            tampered = True
            try:
                outcome = app.submit(result)
            except Error as exc:
                return stages, {'error': exc}, [], fragment
            findings = list((app.repo.load().get('draft') or {}).get('findings') or [])
            return stages, outcome, findings, fragment
        try:
            outcome = app.submit(result)
        except Error as exc:
            return stages, {'error': exc}, [], None
    return stages, {'action': 'limit-reached'}, [], None


# --------------------------------------------------------------------------- tampering helpers
def _delta_key(row, kind):
    """A key the row actually declares for `kind`, so a tamper never invents a coordinate."""
    if kind == 'resources':
        return row['resources'][0]['key']
    if kind == 'places':
        return row['places'][0]['entity']
    if kind == 'knowledge':
        return row['knowledge'][0]['who'] + ':' + row['knowledge'][0]['topic']
    raise KeyError(kind)


def tamper_enter_of_second_chapter(data, task):
    """Chapter 2's declared entry state is changed, so it no longer equals chapter 1's exit."""
    row = data['chapters'][1]
    if row['enter']:
        row['enter'][0]['expected'] = 999
        return 'chapters[1].enter[0].expected -> 999', {'chapter': row['chapter'], 'enter': row['enter'][0]}
    row['enter'] = [{'kind': 'clock', 'key': 'main', 'expected': 999}]
    return 'chapters[1].enter -> [{clock/main/999}]', row['enter']


def tamper_exit_inconsistent(data, task):
    """Chapter 1's declared exit no longer equals enter ⊕ its own deltas."""
    row = data['chapters'][0]
    row['exit'][0]['expected'] = 4242
    return 'chapters[0].exit[0].expected -> 4242', row['exit'][0]


def tamper_resource_negative(data, task):
    """A resource delta is made to spend more than the balance, driving the projection negative."""
    row = data['chapters'][0]
    if not row['resources']:
        return 'no resource delta in this fixture', None
    entry = row['resources'][0]
    from decimal import Decimal
    entry['to'] = str(Decimal(str(entry['from'])) - (abs(Decimal(str(entry['from']))) + 5))
    for item in row['exit']:
        if item['kind'] == 'resources' and item['key'] == entry['key']:
            item['expected'] = entry['to']
    return 'chapters[0].resources[0].to -> %s (negative)' % entry['to'], entry


def tamper_volume_exit_state(data, task):
    """Step three: a volume declares no exit_state, which spec §3 requires to be non-empty."""
    data['volumes'][0]['exit_state'] = ''
    return 'volumes[0].exit_state -> ""', data['volumes'][0]['id']


def tamper_volume_node_window(data, task):
    """Step three: a node's window is moved outside its own volume's chapter range (spec §3)."""
    row = data['volumes'][0]
    row['nodes'][0]['window'] = [900, 950]
    return 'volumes[0].nodes[0].window -> [900,950]（卷界之外）', row['nodes'][0]


def tamper_volume_duplicate_node_id(data, task):
    """Step three: a second volume re-uses a node id already approved (spec §3: 全书唯一)."""
    if len(data.get('volumes') or []) < 2:
        return 'only one volume in this fixture', None
    first = data['volumes'][0]['nodes'][0]['id']
    data['volumes'][1]['nodes'][0]['id'] = first
    return 'volumes[1].nodes[0].id -> %s（与 v1 重复）' % first, data['volumes'][1]['nodes'][0]


def tamper_drift_missing_item(data, task):
    """Step five: the writer's self-comparison drops one planned coordinate."""
    items = data['drift_check']['items']
    dropped = items.pop()
    return ('drift_check.items 去掉一项 %s/%s（%d -> %d）'
            % (dropped['kind'], dropped['key'], len(items) + 1, len(items))), dropped


def tamper_drift_wrong_from(data, task):
    """Step five: `actual.from` is written as a value the engine does not project."""
    item = next(row for row in data['drift_check']['items'] if 'from' in row['planned'])
    item['actual']['from'] = 987654
    return 'drift_check.items[...].actual.from -> 987654', item


def tamper_drift_kept_mismatch(data, task):
    """Step five: a row is kept while its actual result differs from the outline's declaration."""
    item = data['drift_check']['items'][0]
    planned = item['planned']
    if 'to' in planned:
        item['actual']['to'] = '与章纲不符的结果'
    elif 'advance_days' in planned:
        item['actual']['advance_days'] = planned['advance_days'] + 7
    else:
        item['actual']['after'] = 'resolved' if item['actual'].get('after') != 'resolved' else 'seeded'
    return 'drift_check.items[0] kept 但 actual 与 planned 不符', item


def tamper_drift_verdict(data, task):
    """Step five: rows are deviated while the verdict still claims clean."""
    item = data['drift_check']['items'][0]
    item['status'] = 'deviated'
    item['reason'] = '对抗性样本：正文没有兑现这条章纲。'
    return 'items[0].status -> deviated（verdict 仍为 clean）', item


# --------------------------------------------------------------------------------- the cases
def case_chain_rejects_enter_drift():
    repo, app, owner = fresh_project()
    stages, outcome, findings, fragment = play(app, owner, tamper_enter_of_second_chapter,
                                               on='chapter_outline')
    error = outcome.get('error')
    rows = (error.details.get('findings') if error is not None else findings) or []
    return {'verdict': 'rejected' if (error is not None or findings) else 'ACCEPTED',
            'error': None if error is None else '%s: %s' % (error.code, error.message),
            'criteria': sorted({row.get('criterion') for row in rows}),
            'detail': rows[:3], 'fragment': fragment, 'stages': stages}


def case_chain_rejects_exit_drift():
    repo, app, owner = fresh_project()
    stages, outcome, findings, fragment = play(app, owner, tamper_exit_inconsistent, on='chapter_outline')
    error = outcome.get('error')
    return {'verdict': 'rejected' if (error is not None or findings) else 'ACCEPTED',
            'error': None if error is None else '%s: %s' % (error.code, error.message),
            'criteria': sorted({finding.get('criterion') for finding in findings} or
                               {row.get('criterion') for row in (error.details.get('findings') if error else [])}),
            'detail': (error.details.get('findings') if error is not None else findings)[:3],
            'fragment': fragment, 'stages': stages}


def case_chain_rejects_negative_resource():
    repo, app, owner = fresh_project()
    stages, outcome, findings, fragment = play(app, owner, tamper_resource_negative, on='chapter_outline')
    error = outcome.get('error')
    return {'verdict': 'rejected' if (error is not None or findings) else 'ACCEPTED',
            'error': None if error is None else '%s: %s' % (error.code, error.message),
            'criteria': sorted({finding.get('criterion') for finding in findings} or
                               {row.get('criterion') for row in (error.details.get('findings') if error else [])}),
            'detail': (error.details.get('findings') if error is not None else findings)[:3],
            'fragment': fragment, 'stages': stages}


def case_volume_outline_rejects_empty_exit_state():
    repo, app, owner = fresh_project()
    stages, outcome, findings, fragment = play(app, owner, tamper_volume_exit_state, on='volume_outline')
    error = outcome.get('error')
    return {'verdict': 'rejected' if (error is not None or findings) else 'ACCEPTED',
            'error': None if error is None else '%s: %s' % (error.code, error.message),
            'criteria': sorted({finding.get('criterion') for finding in findings} or
                               {row.get('criterion') for row in (error.details.get('findings') if error else [])}),
            'detail': (error.details.get('findings') if error is not None else findings)[:3],
            'fragment': fragment, 'stages': stages}


def case_volume_outline_rejects_out_of_range_window():
    repo, app, owner = fresh_project()
    stages, outcome, findings, fragment = play(app, owner, tamper_volume_node_window, on='volume_outline')
    error = outcome.get('error')
    return {'verdict': 'rejected' if (error is not None or findings) else 'ACCEPTED',
            'error': None if error is None else '%s: %s' % (error.code, error.message),
            'criteria': sorted({finding.get('criterion') for finding in findings} or
                               {row.get('criterion') for row in (error.details.get('findings') if error else [])}),
            'detail': (error.details.get('findings') if error is not None else findings)[:3],
            'fragment': fragment, 'stages': stages}


def case_volume_outline_rejects_duplicate_node_id():
    repo, app, owner = fresh_project()
    stages, outcome, findings, fragment = play(app, owner, tamper_volume_duplicate_node_id, on='volume_outline')
    error = outcome.get('error')
    return {'verdict': 'rejected' if (error is not None or findings) else 'ACCEPTED',
            'error': None if error is None else '%s: %s' % (error.code, error.message),
            'criteria': sorted({finding.get('criterion') for finding in findings} or
                               {row.get('criterion') for row in (error.details.get('findings') if error else [])}),
            'detail': (error.details.get('findings') if error is not None else findings)[:3],
            'fragment': fragment, 'stages': stages}


def case_drift_check_missing_item():
    repo, app, owner = fresh_project()
    stages, outcome, findings, fragment = play(app, owner, tamper_drift_missing_item, on='write')
    criteria = sorted({finding.get('criterion') for finding in findings})
    error = outcome.get('error')
    return {'verdict': 'rejected' if (error is not None or criteria) else 'ACCEPTED',
            'error': None if error is None else '%s: %s' % (error.code, error.message),
            'criteria': criteria, 'detail': findings[:3], 'fragment': fragment,
            'submit': {key: outcome.get(key) for key in ('committed_chapter', 'next_stage')},
            'stages': stages}


def case_drift_check_wrong_from():
    repo, app, owner = fresh_project()
    stages, outcome, findings, fragment = play(app, owner, tamper_drift_wrong_from, on='write')
    criteria = sorted({finding.get('criterion') for finding in findings})
    error = outcome.get('error')
    return {'verdict': 'rejected' if (error is not None or criteria) else 'ACCEPTED',
            'error': None if error is None else '%s: %s' % (error.code, error.message),
            'criteria': criteria, 'detail': findings[:3], 'fragment': fragment,
            'submit': {key: outcome.get(key) for key in ('committed_chapter', 'next_stage')},
            'stages': stages}


def case_drift_check_kept_mismatch():
    repo, app, owner = fresh_project()
    stages, outcome, findings, fragment = play(app, owner, tamper_drift_kept_mismatch, on='write')
    criteria = sorted({finding.get('criterion') for finding in findings})
    error = outcome.get('error')
    return {'verdict': 'rejected' if (error is not None or criteria) else 'ACCEPTED',
            'error': None if error is None else '%s: %s' % (error.code, error.message),
            'criteria': criteria, 'detail': findings[:3], 'fragment': fragment,
            'submit': {key: outcome.get(key) for key in ('committed_chapter', 'next_stage')},
            'stages': stages}


def case_clean_book_reaches_target():
    """The self-consistent sample: everything must commit, settle, and stop at target_reached."""
    repo, app, owner = fresh_project()
    stages, outcome, findings, _fragment = play(app, owner)
    headers = [row['n'] for row in repo.headers('main')]
    book = repo.load()
    state = book['state']
    plan_clock = sum((book['plans'][str(n)].get('clock') or {}).get('advance_days') or 0 for n in headers)
    return {'verdict': 'accepted' if outcome.get('action') == 'target_reached' and not findings else 'NOT-REACHED',
            'action': outcome.get('action'), 'chapters': headers,
            'clock_settled': state['clock'], 'clock_declared': plan_clock,
            'design_drift': len(book.get('design_drift') or []),
            'review_stages_dispatched': sorted(set(stages) & DELETED_STAGES),
            'stages': sorted(set(stages)),
            'unknown_stages': sorted(set(stages) - set(stage_names.STAGES))}


CASES = (
    ('chain: 第二章 enter 与上一章 exit 不符', case_chain_rejects_enter_drift),
    ('chain: exit 与 enter⊕增量 不符', case_chain_rejects_exit_drift),
    ('chain: 资源增量导致负值', case_chain_rejects_negative_resource),
    ('volume_outline: exit_state 为空', case_volume_outline_rejects_empty_exit_state),
    ('volume_outline: 节点 window 越出卷界', case_volume_outline_rejects_out_of_range_window),
    ('volume_outline: 节点 id 与已批准卷重复', case_volume_outline_rejects_duplicate_node_id),
    ('drift_check: 漏一项', case_drift_check_missing_item),
    ('drift_check: actual.from 写错', case_drift_check_wrong_from),
    ('drift_check: kept 与 planned 不符', case_drift_check_kept_mismatch),
    ('clean: 自洽样例一路到 target_reached', case_clean_book_reaches_target),
)


def main(argv=None):
    parser = argparse.ArgumentParser(description='对抗性验收（spec-v2 §8.3）。')
    parser.add_argument('--only', help='按子串筛选用例名')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args(argv)
    selected = [(name, fn) for name, fn in CASES if not args.only or args.only in name]
    report, failures = {}, 0
    try:
        for name, fn in selected:
            try:
                value = fn()
            except BaseException as exc:                # noqa: BLE001 - reported, not swallowed
                value = {'verdict': 'ERROR', 'error': '%s: %s' % (type(exc).__name__, exc),
                         'traceback': traceback.format_exc().splitlines()[-5:]}
            report[name] = value
            expect_reject = not name.startswith('clean:')
            ok = (value['verdict'] in ('rejected',) if expect_reject
                  else value['verdict'] == 'accepted')
            failures += 0 if ok else 1
            print('%-38s %-9s %s' % (name, value['verdict'], 'OK' if ok else '<<< NOT AS EXPECTED'))
            if not ok:
                print(json.dumps(value, ensure_ascii=False, indent=1)[:1200])
    finally:
        close_projects()
    print('\n%d/%d 用例符合预期' % (len(selected) - failures, len(selected)))
    if args.out:
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
