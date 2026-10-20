"""Read-only: total required material that is byte-identical to another required record."""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from novel_ledger.contracts import dump
from novel_ledger.sqlite_store import SQLiteRepository

project = Path(sys.argv[1])
repo = SQLiteRepository(project, readonly=True)
db = repo.db
dup_total = 0
pairs = Counter()
tasks = 0
for row in db.execute("SELECT input FROM tasks WHERE status='done'").fetchall():
    work = json.loads(row['input'])
    seen = {}
    for name in work.get('required') or []:
        ident = work['records'][name]
        size = len(dump(repo.read_document(ident)))
        if ident in seen:
            dup_total += size
            pairs[(seen[ident], name)] += size
            tasks += 1
        else:
            seen[ident] = name
print('必读里内容完全相同的重复：%d 字符，涉及 %d 个任务' % (dup_total, tasks))
for (left, right), size in pairs.most_common():
    print('   %s == %s : %d 字符' % (left, right, size))
repo.close()
