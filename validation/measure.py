"""Engineering-only dependency and frozen-record measurements; no model calls.

The five-step pipeline (v2) has four dispatch classes before prose — `world_model`,
`volume_outline`, `chapter_outline`, `write` — and no review stage at all. This tool measures what
each class costs in transported characters, what the module graph looks like, and whether the
material a dispatch reads stays bounded as the book grows. It says nothing about literary quality,
provider tokens or billed money, and it never calls a model.

    python validation/measure.py
    python validation/measure.py --only graph,dispatch,material
    python validation/measure.py --out validation/metrics.json

A section that cannot run (an engine mid-migration, a fixture the tree has not caught up with yet)
is reported as `status: failed` with its traceback instead of aborting the other sections; the exit
code stays non-zero so a failure is never silent. The only outside dependency is `tests/support.py`
(the shared v2 fixtures); the history/tracking fixtures are kept local so a test module that is
itself mid-rewrite cannot stop the measurement.
"""
import argparse
import ast
import hashlib
import json
import subprocess
import sys
import tempfile
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'tests')]
from novel_ledger.bootstrap import local_application as Application
from novel_ledger.contracts import (OPENING_VERSION, PIPELINE_SHAPES, SCALE_TIERS, Job,
                                    digest, dump)
from novel_ledger.sqlite_store import SQLiteRepository
from novel_ledger.workflow import new_book, preparing_book
from novel_ledger import context, creation, facts
from support import (chapter_outline_fixture, contract, drive, response, seeded_book,
                     volume_outline_fixture)


def tracked_contract(chapters):
    """A contract with narrative tracking on; kept local so this tool never imports test modules."""
    raw = contract(chapters)
    raw.update(narrative_tracking=True, review_chunk=2, review_interval=3, planning_window=3)
    return raw


def append_history(repo, first, last, prose_han=0, entity='shen'):
    """Source records only, deliberately not reviewed chapters; the v1 fixture, kept local."""
    previous = repo.chapter('main', first - 1)['chain'] if first > 1 else 'genesis'
    for n in range(first, last + 1):
        prose = '工程第%d章：沈桐查出来源。' % n + '测' * prose_han
        events = [{'op': 'knowledge', 'entity': entity, 'topic': 'source',
                   'evidence': {'chapter': n, 'start': 0, 'quote': '工程第%d章' % n}}]
        row = {'n': n, 'title': '工程夹具', 'prose': repo.document(prose), 'events': repo.document(events),
               'plan': repo.document({}), 'review': repo.document({}), 'state_hash': digest({'fixture': n}),
               'summary': '工程夹具：核查来源。', 'han': len(prose)}
        row['chain'] = facts.chain(previous, row, digest(repo.load()['contract']))
        repo.add_chapter('main', row)
        previous = row['chain']


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


def dispatch_ledger():
    """How many dispatches the frozen stage graph spends for a book of each tier.

    This replaces the v1 review-tree measurement: `scopes.tree` is gone, and with it every dispatch
    whose only job was to have a second agent judge the first. What is left is arithmetic the
    contract itself declares — the opening gates (mainline, no dispatch per spec §1), one
    `world_model`, one `volume_outline` per batch, one `chapter_outline` per volume, one `write` per
    chapter — plus the one per-tier shape switch, `merge_chapter_outline`.
    """
    rows = []
    # The gate count is derived, not hard-coded: opening/4 inserted `origin` (11 gates, `scale` is a
    # system gate and spends no dispatch), so a literal "ten" here would silently misreport the cost.
    gate_ids = creation.gate_ids(OPENING_VERSION)
    system = tuple(creation.SYSTEM_GATES.get(OPENING_VERSION, ()))
    gates = {'opening_version': OPENING_VERSION, 'gates': list(gate_ids), 'system_gates': list(system),
             'dispatched_opening_options': len(gate_ids) - len(system),
             'note': '开书门由主干自执，不计子 agent 派工（spec §1/§7）；门数与系统门由 '
                     'creation.gate_ids / SYSTEM_GATES 派生。'}
    for tier in SCALE_TIERS:
        shape = PIPELINE_SHAPES.get(tier['id'], {})
        merged = bool(shape.get('merge_chapter_outline'))
        chapters, volumes = tier['chapters'], tier['volume_count']
        for scope in ('all', 'rolling'):
            volume_dispatches = 1 if scope == 'all' else volumes
            chapter_dispatches = 0 if merged else volumes
            rows.append({'tier': tier['id'], 'chapters': chapters, 'volumes': volumes,
                         'volume_scope': scope, 'merge_chapter_outline': merged,
                         'world_model': 1, 'volume_outline': volume_dispatches,
                         'chapter_outline': chapter_dispatches, 'write': chapters,
                         'before_prose': 2 + (0 if merged else 1),
                         'planning_total': 1 + volume_dispatches + chapter_dispatches,
                         'initial_volume_outlines': volumes if scope == 'all' else 1,
                         'total': 1 + volume_dispatches + chapter_dispatches + chapters})
    return {'gates': gates, 'by_tier': rows,
            'boundary': '依 PIPELINE_SHAPES 与 volume_outline.scope 的机械计数，chapter_outline.scope=volume；'
                        'before_prose 只计首章前派工，planning_total 计全程规划；不含返修/重设计和真实模型用量。'}


def _built_bytes(repo, book, job):
    """The same measurement for a dispatch assembled on demand (no task frozen yet)."""
    work = context.build(repo, book, job)
    required = {name: repo.read_document(work['records'][name]) for name in work['required']}
    return {'required_names': list(work['required']), 'required_records': len(work['required']),
            'declared_records': len(work['records']),
            'required_bytes': len(dump(required).encode('utf-8')),
            'envelope_bytes': len(dump(work).encode('utf-8'))}


def _install_outlines(app, book, raw):
    """Put step three/four receipts on the book without dispatching.

    These sections measure transport, not settlement: with the drift validator still landing, the
    only way to reach a `chapter_outline`/`write` envelope is to install the frozen v2 fixtures the
    way `workflow.apply` installs an accepted receipt. Shape comes from the shared fixtures, so the
    measurement cannot drift from what the engine hands out.
    """
    repo = app.repo
    volume_ids = [row['id'] for row in raw['volumes']]
    rows = volume_outline_fixture(app, {'stage': 'volume_outline', 'chapter': 1,
                                        'payload': {'volume_ids': volume_ids}})['volumes']
    book['volumes_outline'] = {row['id']: row for row in rows}
    repo.save(book)
    first = raw['volumes'][0]['id']
    chapters = chapter_outline_fixture(app, {'stage': 'chapter_outline', 'chapter': 1,
                                             'payload': {'volume': first}})['chapters']
    book['chapter_outlines'] = {first: chapters}
    book['plans'] = {str(row['chapter']): row for row in chapters}
    repo.save(book)
    return book


def material_metrics():
    """Per-class dispatch material, and whether future outlines inflate a live dispatch."""
    report = {'boundary': '字符量来自冻结信封与必读记录；不能换算成 token 或费用。'
                          '本表走 seeded 路径（无 creation），因此不含 opening_basis/opening_choices 三项；'
                          'world_model 另走当前版本逐门开书夹具测量。'}
    with tempfile.TemporaryDirectory() as temporary:
        repo = SQLiteRepository.initialize(Path(temporary) / 'seeded',
                                           seeded_book(contract(chapters=4, volumes=2)))
        try:
            app = Application(repo)
            book = repo.load()
            # Step four and five, measured through the same builder the engine uses.
            book = _install_outlines(app, book, book['contract'])
            report['volume_outline'] = _built_bytes(
                repo, book, Job('volume_outline', 1, 'volumes', payload={'volume_ids': ['v1', 'v2']}))
            report['chapter_outline'] = _built_bytes(
                repo, book, Job('chapter_outline', 1, 'volume:v1', 1, 2, payload={'volume': 'v1'}))
            before = _built_bytes(repo, book, Job('write', 1))
            # Every *other* volume's outline is now on the book, fully designed and unread by this
            # chapter. A dispatch that grew with them would be charging a writer for the whole book.
            other = volume_outline_fixture(app, {'stage': 'volume_outline', 'chapter': 1,
                                                 'payload': {'volume_ids': ['v2']}})['volumes']
            book['volumes_outline'].update({row['id']: row for row in other})
            repo.save(book)
            after = _built_bytes(repo, book, Job('write', 1))
            report['write'] = {'without_future_volume': before, 'with_future_volume': after,
                               'growth_bytes': after['required_bytes'] - before['required_bytes'],
                               'bounded_selection': before['required_names'] == after['required_names']}
        finally:
            repo.close()
    with tempfile.TemporaryDirectory() as temporary:
        repo = SQLiteRepository.initialize(Path(temporary) / 'guided',
                                           preparing_book('工程度量夹具。', guided=True))
        try:
            app = Application(repo)
            drive(app, until='world_model')
            work = repo.pending()['input']
            assert work['stage'] == 'world_model'
            report['world_model'] = {'status': 'ok', 'opening_version': creation.opening_version(repo.load()['creation']),
                'required_names': work['required'],
                'required_bytes': len(dump({name: repo.read_document(work['records'][name])
                                          for name in work['required']}).encode('utf-8'))}
        finally:
            repo.close()
    return report


def tracked_state_metrics(size):
    """Where a tracked write dispatch's material comes from as the volume's node list grows.

    Two different bounds are measured separately because they move independently: the settled-state
    slice and the required volume nodes follow this chapter and its dependencies. The complete
    volume source remains optional; the envelope must not sneak the full source back into payload.
    """
    with tempfile.TemporaryDirectory() as temporary:
        repo = SQLiteRepository.initialize(Path(temporary) / 'tracked',
                                           seeded_book(tracked_contract(chapters=size)))
        try:
            app = Application(repo)
            book = repo.load()
            book = _install_outlines(app, book, book['contract'])
            work = context.build(repo, book, Job('write', 1))
            state = repo.read_document(work['records']['state'])
            volume_row_bytes = len(dump(repo.read_document(work['records']['volume_outline'])).encode('utf-8'))
            assert 'story_nodes' in state, sorted(state)
            declared = {row['node'] for row in (book['plans']['1'].get('plot') or {}).get('nodes') or []}
            return {'volume_chapters': size,
                    'registered_nodes': sum(len(row.get('nodes') or [])
                                            for row in (book.get('volumes_outline') or {}).values()),
                    'nodes_declared_by_this_chapter': sorted(declared),
                    'settled_story_nodes_in_slice': len(state['story_nodes']),
                    'state_record_bytes': len(dump(state).encode('utf-8')),
                    'volume_outline_bytes': volume_row_bytes,
                    'complete_volume_outline_bytes': len(dump(repo.read_document(
                        work['records']['complete_volume_outline'])).encode('utf-8')),
                    'envelope_bytes': len(dump(work).encode('utf-8')),
                    'required_bytes': len(dump({name: repo.read_document(work['records'][name])
                                                for name in work['required']}).encode('utf-8'))}
        finally:
            repo.close()


def creative_memory_metrics(size):
    """Interpretation selection at a draft dispatch: 3 of N kept, every version preserved.

    Understanding is filed with a draft receipt (spec §5) and its evidence must quote *frozen*
    prose, so the first chapter — whose dispatch has nothing frozen behind it — cannot carry any:
    the interpretations are filed with chapter two's receipt, citing chapter one, and the draft
    that then carries `creative_memory` is chapter three's.
    """
    with tempfile.TemporaryDirectory() as temporary:
        repo = SQLiteRepository.initialize(Path(temporary) / 'book', seeded_book(contract(chapters=3)))
        try:
            app = Application(repo)
            owner = app.run(through=3, source='工程材料度量。')['owner']
            drive(app, owner, until='write')                    # chapter one: no frozen source yet
            app.submit(response(app))
            drive(app, owner, until='write')                    # chapter two: cite chapter one
            result = response(app)
            result['data']['understanding'] = [dict(
                id='interpretation-' + str(n), kind='character', claim='工程解释样本。', status='tentative',
                subjects=['shen'] if n < 3 else [], topics=[] if n < 3 else ['remote-' + str(n)],
                reason='仅验证材料筛选，不代表文学判断。', evidence=[{'chapter': 1, 'quote': '次日'}], counterevidence=[])
                for n in range(size)]
            outcome = app.submit(result)
            handoff = drive(app, owner, until='write')          # chapter three carries the material
            if len(repo.headers('main')) < 2:
                raise AssertionError('前两章未能入库，understanding 无处落盘：submit=%s，advance 停在 %s'
                                     % (json.dumps(outcome, ensure_ascii=False)[:200], handoff.get('action')))
            work = repo.pending()['input']
            assert 'creative_memory' in work['records'], sorted(work['records'])
            selected = repo.read_document(work['records']['creative_memory'])['interpretations']
            complete = repo.read_document(work['records']['complete_understanding'])
            assert len(selected) == 3 and len(complete['versions']) == size
            assert all(row['evidence'][0]['quote'] == '次日' for row in selected.values())
            values = {name: repo.read_document(work['records'][name]) for name in work['required']}
            return {'interpretations': size, 'selected_interpretations': len(selected),
                    'required_record_bytes': len(dump(values).encode('utf-8')),
                    'complete_optional_source_preserved': True}
        finally:
            repo.close()


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
                started = time.perf_counter()
                missing = app.recall(task['id'], kind='entity', key='absent', limit=5)
                missing_ms = round((time.perf_counter() - started) * 1000, 3)
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
                    'missing_match_ms': missing_ms,
                    'oldest_prose_complete': True, 'observed_read_chars': repo.usage()['supplemental_read_chars']}
        finally:
            repo.close()


SECTIONS = {
    'graph': lambda: graph_metrics(ROOT, 'novel_ledger'),
    'dispatch': dispatch_ledger,
    'material': material_metrics,
    'tracked': lambda: [tracked_state_metrics(n) for n in (20, 100, 500)],
    'memory': lambda: [creative_memory_metrics(n) for n in (20, 100, 500)],
    'history': lambda: [history_metrics(n) for n in (20, 100, 500)],
}


def snapshot_metadata(root=ROOT):
    """Bind a measurement to its source bytes, including local uncommitted fixes."""
    fingerprint = hashlib.sha256()
    files = sorted(path for directory in ('scripts', 'tests', 'validation')
                   for path in (root / directory).rglob('*.py'))
    for path in files:
        fingerprint.update(str(path.relative_to(root)).encode('utf-8') + b'\0')
        fingerprint.update(path.read_bytes() + b'\0')
    try:
        result = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=root, capture_output=True,
                                text=True, timeout=2)
        commit = result.stdout.strip() if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        commit = None
    return {'schema': 'novel-ledger.measurements/1',
            'generated_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'source_commit': commit, 'source_sha256': fingerprint.hexdigest(),
            'source_files': len(files)}


def main(argv=None):
    parser = argparse.ArgumentParser(description='工程材料与依赖度量（不调用模型）。')
    parser.add_argument('--out', type=Path)
    parser.add_argument('--only', help='逗号分隔的节名：' + ','.join(SECTIONS))
    args = parser.parse_args(argv)
    wanted = [name.strip() for name in args.only.split(',')] if args.only else list(SECTIONS)
    unknown = [name for name in wanted if name not in SECTIONS]
    if unknown:
        parser.error('未知的节：' + ','.join(unknown))
    report = {'metadata': snapshot_metadata(),
              'scope': 'engineering_only; not feature parity, literary quality, billed tokens or end-to-end savings',
              'pipeline': 'five steps: opening gates / world_model / volume_outline / chapter_outline / write'}
    failed = []
    for name in wanted:
        try:
            report[name] = {'status': 'ok', 'value': SECTIONS[name]()}
        except BaseException as exc:                    # noqa: BLE001 - a section report, not a handler
            failed.append(name)
            report[name] = {'status': 'failed', 'error': type(exc).__name__ + ': ' + str(exc),
                            'traceback': traceback.format_exc().splitlines()[-6:]}
            print('节 %s 失败：%s: %s' % (name, type(exc).__name__, exc), file=sys.stderr)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
