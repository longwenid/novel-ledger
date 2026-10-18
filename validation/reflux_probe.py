"""Read-only: which drift findings keep coming back, and which of them the engine already judges.

v1 asked this of review receipts ("rework.md 机制 4：发现回流成判据"): every finding a reviewer filed
was kept in `tasks.result` and aggregated by 阶段 × 检查项. v2 has no reviewer, so the sources are
different — and the question is the same one:

* **引擎核算意见** — what the engine refused a draft for (`book['draft']['findings']`, written by
  `drift.reconcile` / `lint` / the word band), and the deviations it did book
  (`design_drift`, `carry_findings`, `accepted_findings`).
* **执笔自比** — the writer's own `drift_check` rows under `tasks.result` with
  `status ∈ deviated|skipped`, plus every `unplanned` row: a coordinate the chapter outline did not
  declare. A row that keeps being filed as deviated is the same signal a repeated review finding
  was: the criterion is not mechanical yet, or the outline is being written ahead of the prose.

Either way the money question is unchanged: a finding that appears twice, in the same shape, is a
candidate for the engine to compute once instead of a writer having to notice it every chapter.

Legacy databases still hold v1 review receipts; they are counted in their own section and labelled
`v1`, never mixed into the v2 numbers.

    用法：python validation/reflux_probe.py /path/to/project
"""
import hashlib
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

project = Path(sys.argv[1])
db = sqlite3.connect('file:' + (project / 'novel.sqlite3').as_posix() + '?mode=ro', uri=True)
db.row_factory = sqlite3.Row

# The v1 review stages, kept only so an old project still reports: nothing in v2 writes these.
LEGACY_REVIEW_STAGES = ('chapter_review', 'scope_review', 'scope_synthesis', 'revision_review',
                        'design_review', 'world_review', 'outline_review', 'contract_review',
                        'alignment_review')

# What the engine already settles mechanically, per drift coordinate. A repeated finding in one of
# these kinds means the *engine* let it through, not that the criterion is missing from the table.
MECHANICAL = {
    'resources': '引擎已机械判：facts.settle 前值与守恒（insufficient_resource）',
    'places': '引擎已机械判：spatial 锚点/拓扑/路径与最短耗时',
    'knowledge': '引擎已机械判：facts.settle knowledge.before + narrative 读者知情越权',
    'characters': '引擎已机械判：character_current.before 与 choice/cost/change 非空',
    'clock': '引擎已机械判：clock 单调 + 章纲 advance_days + elapsed_days',
    'node': '引擎已机械判：story_nodes 前态、依赖、重复推进与提前 resolved',
    'thread': '引擎已机械判：thread_progress 前态与线路依赖',
    'substance': '引擎已机械判：章幅区间（word_budget）',
    'repetition': '引擎已机械判：跨章逐字重复（lint.cross_chapter_duplicates）',
    'language': '引擎已机械判：西文残留与引号体例（lint.latin_findings/style_findings）',
    'drift': '引擎已机械判：drift.reconcile 覆盖/前态/kept 一致',
}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True)
                          .encode('utf-8')).hexdigest()


def book_document():
    """The whole book, assembled from the four declared parts without importing the engine."""
    root = db.execute("SELECT value FROM kv WHERE key='book'").fetchone()
    if root is None:
        return {}
    parts = json.loads(root['value']).get('parts') or {}
    book = {}
    for ident in parts.values():
        row = db.execute('SELECT value FROM documents WHERE hash=?', (ident,)).fetchone()
        if row is not None:
            value = json.loads(row['value'])
            if isinstance(value, dict):
                book.update(value)
    return book


def engine_findings(book):
    """Mechanical findings and booked deviations, as (source, criterion, kind, finding) rows."""
    rows = []
    for finding in (book.get('draft') or {}).get('findings') or []:
        if isinstance(finding, dict):
            rows.append(('draft.findings', str(finding.get('criterion') or '?'),
                         str(finding.get('kind') or '-'), finding))
    for finding in book.get('design_drift') or []:
        if isinstance(finding, dict):
            rows.append(('design_drift', str(finding.get('kind') or '?'),
                         str(finding.get('kind') or '-'), finding))
    for batch in book.get('accepted_findings') or []:
        for finding in (batch or {}).get('findings') or []:
            if isinstance(finding, dict):
                rows.append(('accepted_findings', str(finding.get('criterion') or '?'),
                             str(finding.get('kind') or '-'), finding))
    for finding in book.get('carry_findings') or []:
        if isinstance(finding, dict):
            rows.append(('carry_findings', str(finding.get('criterion') or '?'),
                         str(finding.get('kind') or '-'), finding))
    return rows


def drift_rows():
    """The writer's own comparisons: deviated/skipped rows and unplanned changes, per task."""
    rows = []
    for task in db.execute("SELECT id, input, result FROM tasks WHERE status='done' AND result IS NOT NULL").fetchall():
        work = json.loads(task['input'])
        stage = work.get('stage')
        if stage not in ('write', 'repair', 'redesign'):
            continue
        result = json.loads(task['result'])
        data = result.get('data') if isinstance(result, dict) else None
        check = (data or {}).get('drift_check') if isinstance(data, dict) else None
        if not isinstance(check, dict):
            continue
        for item in check.get('items') or []:
            if not isinstance(item, dict) or item.get('status') not in ('deviated', 'skipped'):
                continue
            rows.append((stage, str(item.get('kind') or '?'), item.get('status'),
                         {'chapter': work.get('chapter'), 'key': item.get('key'),
                          'planned': item.get('planned'), 'actual': item.get('actual'),
                          'reason': item.get('reason')}))
        for item in check.get('unplanned') or []:
            if isinstance(item, dict):
                rows.append((stage, str(item.get('kind') or '?'), 'unplanned',
                             {'chapter': work.get('chapter'), 'key': item.get('key'),
                              'change': item.get('change'), 'reason': item.get('reason')}))
    return rows


def legacy_rows():
    """v1 review receipts, so an old project still reports where its findings came from."""
    rows = []
    for task in db.execute("SELECT input, result FROM tasks WHERE status='done' AND result IS NOT NULL").fetchall():
        work = json.loads(task['input'])
        stage = work.get('stage')
        if stage not in LEGACY_REVIEW_STAGES:
            continue
        result = json.loads(task['result'])
        data = result.get('data') if isinstance(result, dict) else None
        groups = []
        if isinstance(data, dict):
            for key in ('facts', 'reader'):
                if isinstance(data.get(key), dict):
                    groups.append(data[key].get('findings'))
            groups.append(data.get('findings'))
        for findings in groups:
            for finding in findings or []:
                if isinstance(finding, dict) and finding.get('severity') not in (None, 'note'):
                    rows.append((stage, str(finding.get('criterion') or '?'), 'v1', finding))
    return rows


def aggregate(rows, key_of):
    table = defaultdict(lambda: {'count': 0, 'digests': set(), 'again': 0, 'sample': None})
    for row in rows:
        key = key_of(row)
        entry = table[key]
        entry['count'] += 1
        ident = digest(row[-1])
        if ident in entry['digests']:
            entry['again'] += 1
        entry['digests'].add(ident)
        if entry['sample'] is None:
            entry['sample'] = row[-1]
    return table


def report(title, rows, key_of, mechanical_by):
    print('=== %s：%d 条 ===' % (title, len(rows)))
    if not rows:
        print('（无）')
        return []
    table = aggregate(rows, key_of)
    print('%-38s %5s %5s  %s' % ('组合', '次数', '重复', '机械判定 / 样例'))
    for key, entry in sorted(table.items(), key=lambda kv: -kv[1]['count']):
        print('%-38s %5d %5d  %s %s' % ('×'.join(str(part) for part in key), entry['count'],
                                        entry['again'], mechanical_by(key),
                                        str(entry['sample'].get('reason') or entry['sample'].get('change') or '')[:70]))
    return sorted(((entry['again'], key, entry['count']) for key, entry in table.items() if entry['again']),
                  reverse=True)


book = book_document()
engine = engine_findings(book)
writer = drift_rows()
legacy = legacy_rows()
print('项目：%s' % project.resolve())
print('引擎核算意见 %d 条；执笔自比偏离 %d 条；v1 审稿 findings %d 条' % (len(engine), len(writer), len(legacy)))
print()

candidates = report('引擎核算与已入账偏差', engine,
                    lambda row: (row[0], row[1], row[2]), lambda key: MECHANICAL.get(key[2], ''))
candidates += report('执笔自比：deviated / skipped / unplanned', writer,
                     lambda row: (row[0], row[1], row[2]),
                     lambda key: MECHANICAL.get(key[1], '') if key[2] != 'unplanned' else '计划外变化：需在下一章章纲里补登记')
if legacy:
    print()
    candidates += report('v1 审稿 findings（仅历史项目，v2 不再产生）', legacy,
                         lambda row: (row[0], row[1]), lambda key: MECHANICAL.get(key[1], ''))

print()
if candidates:
    print('回流候选（同一条内容出现多于一次；次数 = 重复次数）：')
    for again, key, count in candidates:
        print('  %s：重复 %d 次 / 共 %d 次' % ('×'.join(str(part) for part in key), again, count))
    print('同一条判断重复出现，说明它还不是机械判据：先让引擎算一遍，再谈交给写手自比。')
else:
    print('没有重复出现的条目。')
