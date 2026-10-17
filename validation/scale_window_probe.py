"""Read-only: does the closing audit accept a size the author authorized outside the tier window?"""
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, r'C:\Users\longwen\.zcode\skills\novel-ledger\scripts')
from novel_ledger import creation, world
from novel_ledger.contracts import SCALE_TIERS, Error

project = Path(sys.argv[1])
db = sqlite3.connect('file:' + (project / 'novel.sqlite3').as_posix() + '?mode=ro', uri=True)
root = json.loads(db.execute('SELECT value FROM kv WHERE key=?', ('book',)).fetchone()[0])


def part(name):
    return json.loads(db.execute('SELECT value FROM documents WHERE hash=?', (root['parts'][name],)).fetchone()[0])


book = {}
for name in ('settings', 'canon', 'intent', 'execution'):
    book.update(part(name))
contract = book['contract']
tier = next(row for row in SCALE_TIERS if row['id'] == book['creation']['selections']['scale']['tier'])
print('档位 %s 的章窗 %s；本约定卷末章号 %s' % (tier['id'], tier['chapter_window'], contract['volumes'][-1]['end']))
try:
    creation.validate_contract(contract, book['creation'], book['world'])
    print('审计通过')
except Error as exc:
    print('审计拒绝：%s（%s）' % (exc.code, exc.message))
