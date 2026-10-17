"""Read-only: total required material that is byte-identical to another required record."""
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

project = Path(sys.argv[1])
db = sqlite3.connect('file:' + (project / 'novel.sqlite3').as_posix() + '?mode=ro', uri=True)
db.row_factory = sqlite3.Row
dup_total = 0
pairs = Counter()
tasks = 0
for row in db.execute("SELECT input FROM tasks WHERE status='done'").fetchall():
    work = json.loads(row['input'])
    seen = {}
    for name in work.get('required') or []:
        ident = work['records'][name]
        doc = db.execute('SELECT length(value) n FROM documents WHERE hash=?', (ident,)).fetchone()
        size = doc['n'] if doc else 0
        if ident in seen:
            dup_total += size
            pairs[(seen[ident], name)] += size
            tasks += 1
        else:
            seen[ident] = name
print('必读里内容完全相同的重复：%d 字符，涉及 %d 个任务' % (dup_total, tasks))
for (left, right), size in pairs.most_common():
    print('   %s == %s : %d 字符' % (left, right, size))
