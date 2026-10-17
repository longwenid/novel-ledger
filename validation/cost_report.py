#!/usr/bin/env python3
"""Per-project dispatch material and read accounting, without inventing tokens.

This is an offline reporting tool, not part of the engine: it opens a finished or in-flight
project read-only and reports what each stage actually cost in characters — the frozen envelope a
worker had to read, the receipt it wrote back, the extra records it pulled on demand, and the bytes
left on disk. It deliberately reports characters, not money: character counts cannot be converted
into provider tokens or cost, and a project with no provider log has an unknown bill.

    python3 validation/cost_report.py --project /path/to/book
    python3 validation/cost_report.py --project /path/to/book --out report.json
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

BOUNDARY = ('字符量来自冻结信封、已接受回执、读取日志与磁盘占用；不能换算成 token 或费用。'
            '真实计费需要宿主提供的 input/cache_read/output 日志（见 scripts/observe.py）。')


def connect(project):
    database = Path(project).expanduser() / 'novel.sqlite3'
    if not database.is_file():
        raise SystemExit('项目缺少 novel.sqlite3：' + str(database))
    return sqlite3.connect('file:' + database.as_posix() + '?mode=ro', uri=True)


def stage_rows(db):
    rows = db.execute('SELECT id, status, input, result FROM tasks').fetchall()
    stages = {}
    for task_id, status, raw_input, raw_result in rows:
        work = json.loads(raw_input)
        stage = work.get('stage') or '<unknown>'
        entry = stages.setdefault(stage, {'tasks': 0, 'input_chars': 0, 'result_chars': 0,
                                          'required': 0, 'records': 0})
        entry['tasks'] += 1
        entry['input_chars'] += len(raw_input)
        entry['result_chars'] += len(raw_result or '')
        entry['required'] += len(work.get('required') or ())
        entry['records'] += len(work.get('records') or ())
    for entry in stages.values():
        entry['mean_input_chars'] = round(entry['input_chars'] / entry['tasks'])
        entry['mean_result_chars'] = round(entry['result_chars'] / entry['tasks'])
    return stages


def read_rows(db):
    rows = db.execute("SELECT value FROM journal WHERE action='read'").fetchall()
    chars = 0
    for (value,) in rows:
        chars += json.loads(value)['chars']
    return {'events': len(rows), 'chars': chars}


def disk_rows(project):
    project = Path(project).expanduser()
    work = project / 'work'
    directories = [path for path in work.iterdir() if path.is_dir()] if work.is_dir() else []
    return {'task_directories': len(directories),
            'task_directory_bytes': sum(path.stat().st_size for directory in directories
                                         for path in directory.rglob('*') if path.is_file()),
            'database_bytes': (project / 'novel.sqlite3').stat().st_size}


def summary(project):
    db = connect(project)
    try:
        stages = stage_rows(db)
        counts = {name: db.execute('SELECT count(*) FROM ' + name).fetchone()[0]
                  for name in ('tasks', 'documents', 'chapters')}
        reads = read_rows(db)
    finally:
        db.close()
    disk = disk_rows(project)
    return {'project': str(Path(project).expanduser().resolve()),
            'tasks': {'total': counts['tasks'],
                      'input_chars': sum(s['input_chars'] for s in stages.values()),
                      'result_chars': sum(s['result_chars'] for s in stages.values()),
                      'by_stage': dict(sorted(stages.items()))},
            'supplemental_reads': reads,
            'ledger': {'documents': counts['documents'], 'chapters': counts['chapters']},
            'disk': disk, 'boundary': BOUNDARY}


def main(argv=None):
    parser = argparse.ArgumentParser(description='按阶段统计派工材料与读取字符量。')
    parser.add_argument('--project', required=True)
    parser.add_argument('--out')
    args = parser.parse_args(argv)
    report = summary(args.project)
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.out:
        Path(args.out).write_text(text + '\n', encoding='utf-8')
    print(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
