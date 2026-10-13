"""Engineering-only dependency and frozen-record measurements; no model calls."""
import argparse
import ast
import copy
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'tests')]
from novel_ledger.application import Application
from novel_ledger.contracts import dump
from novel_ledger.sqlite_store import SQLiteRepository
from novel_ledger.workflow import new_book
from support import contract, drive, node


def graph_metrics(root, package):
    folder = root / 'scripts' / package
    paths = [p for p in folder.glob('*.py') if p.stem != '__init__']
    graph = {}
    for path in paths:
        deps = set()
        for item in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            if isinstance(item, ast.ImportFrom) and item.level == 1:
                deps.update([item.module.split('.')[0]] if item.module else [a.name.split('.')[0] for a in item.names])
        graph[path.stem] = deps - {path.stem}
    index, stack, active, ids, low, groups = 0, [], set(), {}, {}, []
    def visit(v):
        nonlocal index
        ids[v] = low[v] = index
        index += 1
        stack.append(v)
        active.add(v)
        for w in graph[v]:
            if w not in graph:
                continue
            if w not in ids:
                visit(w)
                low[v] = min(low[v], low[w])
            elif w in active:
                low[v] = min(low[v], ids[w])
        if low[v] == ids[v]:
            group = []
            while True:
                w = stack.pop()
                active.remove(w)
                group.append(w)
                if w == v:
                    break
            if len(group) > 1:
                groups.append(sorted(group))
    for v in graph:
        if v not in ids:
            visit(v)
    entry = root / 'scripts' / 'novel.py'
    return {'modules': len(paths), 'runtime_lines_including_cli': sum(len(p.read_text(encoding='utf-8').splitlines()) for p in paths + [entry]),
            'cycles_including_deferred_imports': groups, 'dependency_edges': sum(len(v) for v in graph.values())}


def context_metrics(size):
    with tempfile.TemporaryDirectory() as temporary:
        repo = SQLiteRepository.initialize(Path(temporary) / 'book', new_book(contract()))
        try:
            app = Application(repo)
            drive(app, until='write')
            repo.cancel_pending('engineering context benchmark')
            book = repo.load()
            book['designs']['book']['nodes'].extend(node('future-' + str(i)) for i in range(size))
            repo.save(book)
            task = app.advance()['task']
            work = repo.task(task['task_id'])['input']
            required = {n: repo.read_document(work['records'][n]) for n in work['required']}
            full = repo.read_document(work['records']['design:book'])
            assert len(full['nodes']) == size + 1
            assert len(required['story']) == 2
            return {'unreferenced_future_nodes': size, 'required_record_bytes': len(dump(required).encode('utf-8')),
                    'full_book_design_bytes': len(dump(full).encode('utf-8')), 'complete_optional_source_preserved': True}
        finally:
            repo.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    report = {'scope': 'engineering_only; not feature parity, literary quality, billed tokens or end-to-end savings',
              'novel_ledger': graph_metrics(ROOT, 'novel_ledger'), 'context': [context_metrics(n) for n in (10, 100, 1000)]}
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
