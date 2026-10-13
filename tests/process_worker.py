"""Real subprocess with synthetic receipts. Never use this as a model host."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from novel_ledger.sqlite_store import SQLiteRepository
from novel_ledger.application import Application
from support import response
from novel import main

if len(sys.argv) > 1 and sys.argv[1] == 'controller':
    raise SystemExit(main(['--project', os.environ['NOVEL_PROJECT'], 'advance']))

repo = SQLiteRepository(os.environ['NOVEL_PROJECT'])
try:
    app = Application(repo)
    result = response(app, os.environ['NOVEL_TASK_ID'], os.environ['NOVEL_SESSION'], os.environ['NOVEL_EXECUTION_CLAIM'])
    path = Path(os.environ['NOVEL_TASK_PATH']).parent / 'result.json'
    path.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
finally:
    repo.close()
raise SystemExit(main(['--project', os.environ['NOVEL_PROJECT'], 'submit', '--file', str(path)]))
