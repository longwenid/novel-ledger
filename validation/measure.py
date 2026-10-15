"""Engineering-only dependency and frozen-record measurements; no model calls."""
import argparse
import ast
import copy
import json
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'tests')]
from novel_ledger.bootstrap import local_application as Application
from novel_ledger.contracts import dump
from novel_ledger.sqlite_store import SQLiteRepository
from novel_ledger.workflow import new_book
from novel_ledger import context, facts, scopes, story_memory
from novel_ledger.contracts import Job
from support import contract, drive, node
from test_history import append_history
from test_narrative import tracked_contract


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
              'novel_ledger': graph_metrics(ROOT, 'novel_ledger'), 'context': [context_metrics(n) for n in (10, 100, 1000)],
              'tracked_causal_context': [tracked_context_metrics(n) for n in (20, 100, 500)],
              'editorial_causal_context': [tracked_context_metrics(n, enhanced=True) for n in (20, 100, 500)],
              'creative_memory_context': [creative_memory_metrics(n) for n in (20, 100, 500)],
              'review_trees': [review_metrics(n) for n in (20, 100, 500)],
              'history_transport': [history_metrics(n) for n in (20, 100, 500)]}
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


def tracked_context_metrics(size, enhanced=False):
    with tempfile.TemporaryDirectory() as temporary:
        repo = SQLiteRepository.initialize(Path(temporary) / 'book', new_book(contract()))
        try:
            app = Application(repo)
            drive(app, until='write')
            repo.cancel_pending('engineering tracked context benchmark')
            book = repo.load()
            book['contract']['narrative_tracking'] = True
            if enhanced:
                from test_editorial import plan_extras
                book['contract']['editorial_features'] = True
                plan_extras(book['plans']['1'])
                # Freeze material directly: this benchmark measures transport, not profile refresh.
            book['state'] = facts.seed(book['contract'])
            nodes = [{**node('causal-' + str(i), () if i == 0 else ['causal-' + str(i-1)]),
                      'required': False, 'window': [1,2]} for i in range(size)]
            book['designs']['book']['nodes'] = nodes
            book['plans']['1'].update(node_ids=[nodes[-1]['id']], node_actions=[{'node': nodes[-1]['id'], 'after': 'seeded'}],
                                      node_contracts={nodes[-1]['id']: nodes[-1]}, disclosures=[], preconditions=[])
            if enhanced:
                story_memory.bind(book['plans']['1'], book['plans'], 2)
            repo.save(book)
            work = context.build(repo, book, Job('write', 1)) if enhanced else repo.task(app.advance()['task']['task_id'])['input']
            values = {n: repo.read_document(work['records'][n]) for n in work['required']}
            assert len(values['story']) == 2
            return {'causal_nodes': size, 'required_story_nodes': len(values['story']),
                    'required_record_bytes': len(dump(values).encode('utf-8')),
                    'complete_design_nodes': len(repo.read_document(work['records']['design:book'])['nodes'])}
        finally:
            repo.close()


def creative_memory_metrics(size):
    from support import response
    with tempfile.TemporaryDirectory() as temporary:
        repo = SQLiteRepository.initialize(Path(temporary) / 'book', new_book(contract()))
        try:
            app = Application(repo)
            owner = app.run(through=2, source='工程材料度量。')['owner']
            drive(app, owner, until='chapter_review')
            result = response(app)
            result['data']['understanding'] = [dict(
                id='interpretation-' + str(n), kind='character', claim='工程解释样本。', status='tentative',
                subjects=['shen'] if n < 3 else [], topics=[] if n < 3 else ['remote-' + str(n)],
                reason='仅验证材料筛选，不代表文学判断。', evidence=[{'chapter': 1, 'quote': '次日'}], counterevidence=[])
                for n in range(size)]
            app.submit(result)
            drive(app, owner, until='write')
            work = repo.pending()['input']
            selected = repo.read_document(work['records']['creative_memory'])['interpretations']
            complete = repo.read_document(work['records']['complete_understanding'])
            assert len(selected) == 3 and len(complete['versions']) == size
            assert all(r['evidence'][0]['quote'] == '次日' for r in selected.values())
            values = {n: repo.read_document(work['records'][n]) for n in work['required']}
            return {'interpretations': size, 'selected_interpretations': len(selected),
                    'required_record_bytes': len(dump(values).encode('utf-8')),
                    'complete_optional_source_preserved': True}
        finally:
            repo.close()


def review_metrics(chapters):
    parts = scopes.tree([{'n': n, 'chain': str(n)} for n in range(1, chapters+1)], 1, chapters, 3, 3)
    parents = [p for p in parts if p['level']]
    return {'chapters': chapters, 'tree_depth': parts[-1]['level'],
            'max_children_per_synthesis': max(len(p['children']) for p in parents),
            'max_boundary_chapters_per_synthesis': max(2 * len(p['children']) for p in parents),
            'root_span': [parts[-1]['first'], parts[-1]['last']]}


def history_metrics(chapters):
    """Measure transport and local source reads over synthetic million-character history.

    No model reviews or full novel lifecycle are simulated by these source-only records.
    Timings are observations; complexity assertions use counts and hashes instead.
    """
    with tempfile.TemporaryDirectory() as temporary:
        repo = SQLiteRepository.initialize(Path(temporary) / 'book', new_book(tracked_contract(chapters)))
        try:
            with repo.transaction():
                append_history(repo, 1, chapters, prose_han=3000)
                started = time.perf_counter()
                source = repo.history_snapshot('main')
                first_build_ms = round((time.perf_counter() - started) * 1000, 3)
            before = repo.db.execute('SELECT count(*) FROM documents').fetchone()[0]
            with patch.object(repo, 'read_document', wraps=repo.read_document) as reads:
                started = time.perf_counter()
                for _ in range(6):
                    assert repo.history_snapshot('main') == source
                repeat_ms = round((time.perf_counter() - started) * 1000, 3)
                repeat_reads = reads.call_count
            after = repo.db.execute('SELECT count(*) FROM documents').fetchone()[0]
            app = Application(repo)
            work = context.build(repo, repo.load(), Job('write', 1))
            task = repo.add_task(work)
            with patch.object(repo, 'memory_rows', wraps=repo.memory_rows) as scans:
                found = app.recall(task['id'], kind='entity', key='shen', limit=5)
                recent_pages = scans.call_count
            with patch.object(repo, 'memory_rows', wraps=repo.memory_rows) as scans:
                missing = app.recall(task['id'], kind='entity', key='absent', limit=5)
                missing_pages = scans.call_count
            assert len(found['matches']) == 5 and recent_pages == 6 and not missing['matches']
            assert repeat_reads == 6 and before == after and missing_pages == chapters
            oldest = app.recall(task['id'], chapter=1)
            assert oldest['prose'] == repo.read_document(repo.chapter('main', 1)['prose'])
            catalog, memory = [], []
            for _, page in repo.history_pages(source):
                catalog.append({'chapter': page['n'], 'prose_hash': page['prose'], 'summary': page['summary']})
                memory.extend({k: v for k, v in row.items() if k != 'topics'} for row in repo.memory_rows(page))
            return {'synthetic_chapters': chapters, 'synthetic_prose_han_at_least': chapters * 3000,
                    'history_source_bytes': len(dump(source).encode('utf-8')),
                    'previous_full_catalog_and_event_index_bytes': len(dump(catalog).encode('utf-8')) + len(dump(memory).encode('utf-8')),
                    'first_build_ms': first_build_ms, 'six_repeated_snapshot_ms': repeat_ms,
                    'six_repeated_snapshot_document_reads': repeat_reads, 'repeated_snapshot_new_documents': after - before,
                    'recent_five_match_event_pages_read': recent_pages, 'missing_match_event_pages_read': missing_pages,
                    'oldest_prose_complete': True, 'observed_read_chars': repo.usage()['supplemental_read_chars']}
        finally:
            repo.close()


if __name__ == '__main__':
    main()
