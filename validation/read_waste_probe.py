"""Read-only delivery accounting; repeated records do not establish avoidable model usage."""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from novel_ledger.sqlite_store import SQLiteRepository

BOUNDARY = ('仅按实际 read 日志观察交付；同执行同哈希重复仍可能是必要补读，不等于可省 token。'
            '缺 execution_id 或记录哈希的旧日志只能列出同名候选；混合响应不按记录个数估算重复字符。'
            '响应字符含包装，不含宿主文件读取和模型历史；换执行上下文不视为已读。')


def analyze(records):
    known = set()
    names_by_task = defaultdict(set)
    per_task = defaultdict(lambda: {'events': 0, 'chars': 0})
    counts = {name: {'events': 0, 'response_chars': 0} for name in (
        'same_execution_same_hash', 'mixed_known_and_new', 'first_or_changed',
        'unclassified', 'legacy_same_name_candidates')}
    total = events = 0
    for row in records:
        task = row.get('task')
        names = set(row.get('records') or ())
        chars = row['chars']
        events += 1
        total += chars
        per_task[task]['events'] += 1
        per_task[task]['chars'] += chars
        execution = row.get('execution_id')
        hashes = row.get('record_hashes')
        identified = (isinstance(execution, str) and bool(execution) and names
                      and isinstance(hashes, dict)
                      and all(isinstance(hashes.get(name), str) and hashes[name] for name in names))
        if identified:
            keys = {(execution, name, hashes[name]) for name in names}
            repeated = keys & known
            kind = ('same_execution_same_hash' if repeated == keys
                    else 'mixed_known_and_new' if repeated else 'first_or_changed')
            known.update(keys)
        else:
            kind = 'unclassified'
            if names & names_by_task[task]:
                counts['legacy_same_name_candidates']['events'] += 1
                counts['legacy_same_name_candidates']['response_chars'] += chars
        counts[kind]['events'] += 1
        counts[kind]['response_chars'] += chars
        names_by_task[task].update(names)
    return {'events': events, 'chars': total, **counts,
            'largest_tasks': [{'task': task, **amounts} for task, amounts in
                              sorted(per_task.items(), key=lambda item: -item[1]['chars'])[:6]],
            'boundary': BOUNDARY}


def summary(project):
    repo = SQLiteRepository(Path(project).expanduser(), readonly=True)
    try:
        rows = repo.db.execute("SELECT value FROM journal WHERE action='read' ORDER BY id").fetchall()
        return analyze(json.loads(row['value']) for row in rows)
    finally:
        repo.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project')
    parser.add_argument('--json', action='store_true', help='输出结构化交付统计。')
    args = parser.parse_args(argv)
    result = summary(args.project)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    print('read 事件 %d 次，返回 %d 字符' % (result['events'], result['chars']))
    for key, label in (
            ('same_execution_same_hash', '同一执行、全部记录哈希已交付的响应'),
            ('mixed_known_and_new', '同一执行、混合已交付和新记录的响应'),
            ('first_or_changed', '同一执行首次交付或记录哈希变化的响应'),
            ('unclassified', '缺执行/哈希依据或无记录，无法分类的响应'),
            ('legacy_same_name_candidates', '其中旧日志同名重复候选（属于无法分类项）')):
        row = result[key]
        print('%s：%d 次，整份响应 %d 字符' % (label, row['events'], row['response_chars']))
    print(BOUNDARY)
    print('读取最多的任务：', result['largest_tasks'])
    return 0


if __name__ == '__main__':
    sys.exit(main())
