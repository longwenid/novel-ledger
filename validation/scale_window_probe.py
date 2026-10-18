"""Read-only: does the closing audit accept a size the author authorized outside the tier window?

    python validation/scale_window_probe.py /path/to/project

Reads the four book partitions straight out of the store, so it works on any project the engine
wrote (v2's `book_state.PART_FIELDS` layout, unchanged since v1).
"""
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from novel_ledger import creation
from novel_ledger.contracts import SCALE_TIERS, Error

project = Path(sys.argv[1])
db = sqlite3.connect('file:' + (project / 'novel.sqlite3').as_posix() + '?mode=ro', uri=True)
root = json.loads(db.execute('SELECT value FROM kv WHERE key=?', ('book',)).fetchone()[0])


def part(name):
    row = db.execute('SELECT value FROM documents WHERE hash=?', (root['parts'][name],)).fetchone()
    return json.loads(row[0])


book = {}
for name in ('settings', 'canon', 'intent', 'execution'):
    book.update(part(name))
contract = book['contract']
opening = book.get('creation') or {}
if not opening.get('selections'):
    raise SystemExit('该项目不是逐门开书（creation.selections 为空）：档位窗口审计只对开书项目成立。')
tier = next(row for row in SCALE_TIERS if row['id'] == opening['selections']['scale']['tier'])
print('档位 %s 的章窗 %s；本约定卷末章号 %s' % (tier['id'], tier['chapter_window'], contract['volumes'][-1]['end']))
try:
    creation.validate_contract(contract, opening, book['world'])
    print('审计通过')
except Error as exc:
    print('审计拒绝：%s（%s）' % (exc.code, exc.message))
