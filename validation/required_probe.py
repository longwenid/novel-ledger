"""Read-only: the required set of representative stages, record by record."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from novel_ledger.contracts import dump
from novel_ledger.sqlite_store import SQLiteRepository

project = Path(sys.argv[1])
wanted = set(sys.argv[2].split(','))
repo = SQLiteRepository(project, readonly=True)
db = repo.db

for row in db.execute("SELECT id, input FROM tasks WHERE status='done'").fetchall():
    work = json.loads(row['input'])
    if work['stage'] not in wanted:
        continue
    sizes = []
    for name in work.get('required') or []:
        sizes.append((len(dump(repo.read_document(work['records'][name]))), name))
    sizes.sort(reverse=True)
    print('task %s  stage=%-14s chapter=%s  required=%d 合计=%d' % (
        row['id'][:8], work['stage'], work.get('chapter'), len(sizes), sum(n for n, _ in sizes)))
    for size, name in sizes:
        print('    %7d  %s' % (size, name))
repo.close()
