"""Read-only: how much of a design dispatch's required material is a projection of another record.

Measures, for representative frozen tasks, each required record's size and how much of a narrow
record's text also appears in the full record it projects from — the evidence for dropping duplicate
required records.

v2 keeps exactly one declared projection (``context.PROJECTIONS``): ``world_core`` is the narrowed
view of ``world_model``, so a scene dispatch reads the rules through one of them and never both. The
v1 pairs that named deleted records (``frontier:book``/``design:book``, ``plan``/``scene_context``)
are gone with the stages that produced them; a legacy project still lists its own numbers in
``validation/results.md``.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from novel_ledger.contracts import dump
from novel_ledger.sqlite_store import SQLiteRepository

project = Path(sys.argv[1])
repo = SQLiteRepository(project, readonly=True)
db = repo.db

# (narrow, wide): the narrow record is a declared projection of the wide one. Mirrors
# `context.PROJECTIONS`; records are reconstructed through the current storage adapter.
PAIRS = (('world_core', 'world_model'),)


def document(ident):
    return len(dump(repo.read_document(ident)))


printed = 0
for row in db.execute("SELECT id, input FROM tasks WHERE status='done'").fetchall():
    work = json.loads(row['input'])
    required = work.get('required') or []
    records = work.get('records') or {}
    sizes = {name: document(records[name]) for name in required if name in records}
    hits = [(narrow, full) for narrow, full in PAIRS if narrow in sizes and full in sizes]
    if not hits:
        continue
    printed += 1
    total = sum(value or 0 for value in sizes.values())
    print('task %s stage=%-16s required=%d 材料=%d 字符' % (row['id'][:8], work['stage'], len(required), total))
    for narrow, full in hits:
        print('    %-16s %7d  ⊂  %-16s %7d   （窄记录是整份的投影，两份同时必读）'
              % (narrow, sizes[narrow] or 0, full, sizes[full] or 0))
    top = sorted(((value or 0), name) for name, value in sizes.items())[-4:]
    print('    最大的四份：' + '，'.join('%s %d' % (name, size) for size, name in reversed(top)))
if not printed:
    print('没有同时读到投影两侧的任务：%s 里的投影对为 %s。'
          % (project, '、'.join('%s ⊂ %s' % pair for pair in PAIRS)))
repo.close()
