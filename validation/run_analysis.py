"""Read-only analysis of a novel-ledger verification project.

Reports where the run's material and tokens actually went: per-stage dispatch material, receipts,
supplemental reads (the dominant term), task lifecycle, retries and disk growth.
"""
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from novel_ledger.contracts import SCHEMA

project = Path(sys.argv[1])
db = sqlite3.connect('file:' + (project / 'novel.sqlite3').as_posix() + '?mode=ro', uri=True)
db.row_factory = sqlite3.Row
version = db.execute("SELECT value FROM kv WHERE key='schema'").fetchone()
if version is None or json.loads(version['value']) != SCHEMA:
    raise SystemExit('只支持当前数据库协议：' + SCHEMA)

tasks = db.execute('SELECT id, status, input, result FROM tasks').fetchall()
by_stage = defaultdict(lambda: {'n': 0, 'input': 0, 'result': 0, 'required': 0, 'records': 0})
stage_of = {}
for row in tasks:
    work = json.loads(row['input'])
    stage = work.get('stage') or '<none>'
    stage_of[row['id']] = stage
    entry = by_stage[stage]
    entry['n'] += 1
    entry['input'] += len(row['input'])
    entry['result'] += len(row['result'] or '')
    entry['required'] += len(work.get('required') or ())
    entry['records'] += len(work.get('records') or {})

print('=== 1. 任务与材料（按阶段）===')
print('%-18s %5s %10s %10s %8s %8s' % ('stage', 'tasks', 'input ch', 'result ch', 'req/均', 'rec/均'))
total_in = total_out = 0
for stage, e in sorted(by_stage.items(), key=lambda kv: -kv[1]['input'] - kv[1]['result']):
    total_in += e['input']
    total_out += e['result']
    print('%-18s %5d %10d %10d %8.1f %8.1f' % (stage, e['n'], e['input'], e['result'],
                                               e['required'] / e['n'], e['records'] / e['n']))
print('%-18s %5d %10d %10d' % ('合计', len(tasks), total_in, total_out))

print()
print('=== 2. 补充读取（read 实际返回字符）===')
reads = db.execute("SELECT value FROM journal WHERE action='read'").fetchall()
by_stage_read = defaultdict(int)
count_by_stage_read = defaultdict(int)
top = []
for (value,) in reads:
    record = json.loads(value)
    stage = stage_of.get(record.get('task'), '<unknown>')
    by_stage_read[stage] += record['chars']
    count_by_stage_read[stage] += 1
    top.append((record['chars'], stage, record.get('task', '')[:8], record.get('records')))
total_read = sum(by_stage_read.values())
for stage, chars in sorted(by_stage_read.items(), key=lambda kv: -kv[1]):
    print('%-18s %4d 次 %10d 字符  均 %6d' % (stage, count_by_stage_read[stage], chars,
                                              chars // max(1, count_by_stage_read[stage])))
print('读取合计 %d 字符 / %d 次；任务信封 %d + 回执 %d = %d，读取是它的 %.2f 倍'
      % (total_read, len(reads), total_in, total_out, total_in + total_out,
         total_read / max(1, total_in + total_out)))
print('--- 单次最大的 8 次读取 ---')
for chars, stage, task, names in sorted(top, reverse=True)[:8]:
    print('%7d  %-16s task %s  records=%s' % (chars, stage, task, names))

print()
print('=== 3. 任务生命周期与返工 ===')
status_count = Counter(row['status'] for row in tasks)
print('任务状态:', dict(status_count))
actions = Counter(row[0] for row in db.execute('SELECT action FROM journal').fetchall())
print('journal 动作:', dict(actions))
submits = [json.loads(v) for (v,) in db.execute("SELECT value FROM journal WHERE action='submit'").fetchall()]
print('submit 次数:', len(submits))
print('未入库的 submit（被拒/预览）:', sum(1 for s in submits if not s.get('committed_chapter') and s.get('accepted') is False))
dispatches = [json.loads(v) for (v,) in db.execute("SELECT value FROM journal WHERE action='dispatch'").fetchall()]
print('dispatch 次数:', len(dispatches), ' 按阶段:',
      dict(Counter(stage_of.get(d['task'], '?') for d in dispatches)))
cancelled = Counter()
for row in tasks:
    if row['status'] == 'cancelled':
        cancelled[stage_of.get(row['id'], '?')] += 1
print('被取消的任务（按阶段）:', dict(cancelled))

print()
print('=== 4. 磁盘与账本 ===')
docs = db.execute('SELECT count(*) c FROM documents').fetchone()['c']
chapters = db.execute('SELECT count(*) c FROM chapters').fetchone()['c']
print('documents %d，chapters %d，database %.2f MB' % (docs, chapters, (project / 'novel.sqlite3').stat().st_size / 1e6))
work = project / 'work'
dirs = [p for p in work.iterdir() if p.is_dir()] if work.is_dir() else []
bytes_ = sum(f.stat().st_size for d in dirs for f in d.rglob('*') if f.is_file())
print('work 目录 %d 个，共 %.2f MB（均 %.0f KB）' % (len(dirs), bytes_ / 1e6, bytes_ / max(1, len(dirs)) / 1024))
res = sorted(((f.stat().st_size, f) for d in dirs for f in d.glob('result.json')), reverse=True)
print('最大的 result.json:', [(round(s / 1024), f.parent.name[:8]) for s, f in res[:5]])
