"""Read-only: the required set of representative stages, record by record."""
import json
import sqlite3
import sys
from pathlib import Path

project = Path(sys.argv[1])
wanted = set(sys.argv[2].split(','))
db = sqlite3.connect('file:' + (project / 'novel.sqlite3').as_posix() + '?mode=ro', uri=True)
db.row_factory = sqlite3.Row

for row in db.execute("SELECT id, input FROM tasks WHERE status='done'").fetchall():
    work = json.loads(row['input'])
    if work['stage'] not in wanted:
        continue
    sizes = []
    for name in work.get('required') or []:
        doc = db.execute('SELECT length(value) n FROM documents WHERE hash=?', (work['records'][name],)).fetchone()
        sizes.append((doc['n'], name))
    sizes.sort(reverse=True)
    print('task %s  stage=%-14s chapter=%s  required=%d 合计=%d' % (
        row['id'][:8], work['stage'], work.get('chapter'), len(sizes), sum(n for n, _ in sizes)))
    for size, name in sizes:
        print('    %7d  %s' % (size, name))
