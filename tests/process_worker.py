"""Real subprocess with synthetic receipts. Never use this as a model host."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from novel_ledger.sqlite_store import SQLiteRepository
from novel_ledger.bootstrap import local_application as Application
from support import response
from novel import dispatch, main, parser

if len(sys.argv) > 1 and sys.argv[1] == 'controller':
    raise SystemExit(main(['--project', os.environ['NOVEL_PROJECT'], 'advance']))

repo = SQLiteRepository(os.environ['NOVEL_PROJECT'])
try:
    app = Application(repo)
    if len(sys.argv) > 1 and sys.argv[1] == 'fast':
        chapters = []
        while True:
            task_id = os.environ['NOVEL_TASK_ID']
            result = response(app, task_id, os.environ['NOVEL_SESSION'], os.environ['NOVEL_EXECUTION_CLAIM'])
            path = Path(os.environ['NOVEL_TASK_PATH']).parent / 'result.json'
            path.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
            base = ['--project', os.environ['NOVEL_PROJECT']]
            submitted = dispatch(parser().parse_args(base + ['submit', '--file', str(path)]))
            chapters.append(submitted['committed_chapter'])
            if submitted['worker_boundary'] == 'finished':
                print(json.dumps({'synthetic': True, 'chapters': chapters, 'session': os.environ['NOVEL_SESSION']}))
                raise SystemExit(0)
            step = dispatch(parser().parse_args(base + ['worker-next', '--task', task_id]))
            os.environ['NOVEL_TASK_ID'] = step['task']['task_id']
            os.environ['NOVEL_TASK_PATH'] = step['task']['task_path']
            os.environ['NOVEL_EXECUTION_CLAIM'] = step['execution_claim']
    result = response(app, os.environ['NOVEL_TASK_ID'], os.environ['NOVEL_SESSION'], os.environ['NOVEL_EXECUTION_CLAIM'])
    path = Path(os.environ['NOVEL_TASK_PATH']).parent / 'result.json'
    path.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
finally:
    repo.close()
raise SystemExit(main(['--project', os.environ['NOVEL_PROJECT'], 'submit', '--file', str(path)]))
