"""Read-only: how much of a design task's required material is a projection of another record.

Measures, for representative frozen tasks, each required record's size and how much of a narrow
record's text also appears in the full record it projects from — the evidence for dropping duplicate
required records.
"""
import json
import sqlite3
import sys
from pathlib import Path

project = Path(sys.argv[1])
db = sqlite3.connect('file:' + (project / 'novel.sqlite3').as_posix() + '?mode=ro', uri=True)
db.row_factory = sqlite3.Row


def document(ident):
    row = db.execute('SELECT value FROM documents WHERE hash=?', (ident,)).fetchone()
    return None if row is None else len(row['value'])


pairs = [('world_core', 'world_model'), ('frontier:book', 'design:book'),
         ('state', 'complete_state'), ('plan', 'scene_context')]
for row in db.execute("SELECT id, input FROM tasks WHERE status='done'").fetchall():
    work = json.loads(row['input'])
    required = work.get('required') or []
    records = work.get('records') or {}
    if 'world_model' not in required:
        continue
    sizes = {name: document(records[name]) for name in required}
    hits = {narrow: sizes[narrow] for narrow, full in pairs
            if narrow in sizes and full in sizes}
    if not hits:
        continue
    total = sum(v or 0 for v in sizes.values())
    print('task %s stage=%-16s required=%d 材料=%d 字符' % (row['id'][:8], work['stage'], len(required), total))
    for narrow, full in pairs:
        if narrow in sizes and full in sizes:
            print('    %-16s %7d  ⊂  %-16s %7d   （窄记录是整份的投影，两份同时必读）'
                  % (narrow, sizes[narrow] or 0, full, sizes[full] or 0))
    top = sorted(((v or 0), k) for k, v in sizes.items())[-4:]
    print('    最大的四份：' + '，'.join('%s %d' % (k, v) for v, k in reversed(top)))
