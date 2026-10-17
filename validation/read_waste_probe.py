"""Read-only: how many read characters were re-deliveries of records the task already had."""
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

project = Path(sys.argv[1])
db = sqlite3.connect('file:' + (project / 'novel.sqlite3').as_posix() + '?mode=ro', uri=True)
db.row_factory = sqlite3.Row

seen = defaultdict(set)
redundant = 0
total = 0
events = 0
fully_redundant = 0
for row in db.execute("SELECT value FROM journal WHERE action='read' ORDER BY id").fetchall():
    record = json.loads(row['value'])
    task = record.get('task')
    names = list(record.get('records') or ())
    chars = record['chars']
    total += chars
    events += 1
    fresh = [n for n in names if n not in seen[task]]
    if names and not fresh:
        fully_redundant += chars
    else:
        # Approximate the repeated portion by the share of already-seen names.
        redundant += chars * (len(names) - len(fresh)) / max(1, len(names))
    seen[task].update(names)

print('read 事件 %d 次，返回 %d 字符' % (events, total))
print('整份重复送达（本次要的记录此前全部给过）：%d 字符（%.0f%%）' % (fully_redundant, 100 * fully_redundant / max(1, total)))
print('含部分重复的重复部分：约 %d 字符' % redundant)
print('合计可省：约 %d 字符（%.0f%%）' % (fully_redundant + redundant,
                                     100 * (fully_redundant + redundant) / max(1, total)))
per_task = defaultdict(lambda: [0, 0])
for row in db.execute("SELECT value FROM journal WHERE action='read' ORDER BY id").fetchall():
    record = json.loads(row['value'])
    per_task[record.get('task')][0] += 1
    per_task[record.get('task')][1] += record['chars']
worst = sorted(per_task.items(), key=lambda kv: -kv[1][1])[:6]
print('读取最多的任务：', [(t[:8], n, c) for t, (n, c) in worst])
