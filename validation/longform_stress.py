"""Repeatable multi-million-character transport/storage probe; no model calls.

Source-only synthetic history is deliberately separate from the accepted lifecycle
probe. Neither is evidence of literary quality or actual provider context/token cost.
All databases are temporary; --out is the only persistent output.
"""
import argparse
import json
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'tests'), str(ROOT / 'validation')]

from novel_ledger import context
from novel_ledger.bootstrap import local_application
from novel_ledger.contracts import Job, digest, dump, han_count
from novel_ledger.sqlite_store import SQLiteRepository
from measure import append_history, snapshot_metadata
from support import (chapter_outline_fixture, contract, drive, seeded_book,
                     volume_outline_fixture)


def json_bytes(value):
    return len(dump(value).encode('utf-8'))


def source_probe(chapters, prose_han):
    """Freeze a late writer against archived volumes and complete source prose."""
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix='novel-scale-') as temporary:
        project = Path(temporary) / 'book'
        raw = contract(chapters=chapters + 1, volumes=max(1, (chapters + 1) // 25))
        raw['chapter_max'] = max(raw['chapter_max'], prose_han + 40)
        raw['word_range'] = [raw['chapter_min'] * (chapters + 1), raw['chapter_max'] * (chapters + 1)]
        raw['narrative_tracking'] = True
        raw['volume_outline']['scope'] = 'rolling'
        repo = SQLiteRepository.initialize(project, seeded_book(raw))
        try:
            app = local_application(repo)
            with repo.transaction():
                append_history(repo, 1, chapters, prose_han=prose_han)
                book = repo.load()
                book['written_han'] = sum(han_count(repo.read_document(row['prose']))
                                          for row in repo.headers('main'))
                outlines = volume_outline_fixture(app, {
                    'stage': 'volume_outline', 'chapter': 1, 'payload': {
                        'volume_ids': [v['id'] for v in book['contract']['volumes']]}})['volumes']
                book['volumes_outline'] = {v['id']: v for v in outlines}
                book['state']['clock'] = chapters
                # Archived promises are paid. Their original declarations and states
                # must remain available while the live writer reads relevant material.
                for outline in outlines[:-1]:
                    for hook in outline['hooks']:
                        book['state']['hooks'][hook['id']] = {
                            'status': 'paid', 'text': hook['text'], 'due': outline['clock']['to']}
                repo.save(book)
                volume = book['contract']['volumes'][-1]
                rows = chapter_outline_fixture(app, {
                    'stage': 'chapter_outline', 'chapter': volume['first'],
                    'payload': {'volume': volume['id']}})['chapters']
                book['chapter_outlines'] = {volume['id']: rows}
                book['plans'] = {str(row['chapter']): row for row in rows}
                repo.save(book)
                build_started = time.perf_counter()
                work = context.build(repo, book, Job('write', chapters + 1))
                task = repo.add_task(work)
                build_ms = (time.perf_counter() - build_started) * 1000
            required = {n: repo.read_document(work['records'][n]) for n in work['required']}
            compact = app.presentation.task(task, compact=True)
            source = repo.read_document(work['records']['history_source'])
            with patch.object(repo, 'read_document', wraps=repo.read_document) as reads:
                for _ in range(6):
                    assert repo.history_snapshot('main') == source
                snapshot_reads = reads.call_count
            assert snapshot_reads == 6, snapshot_reads
            with patch.object(repo, 'memory_rows', wraps=repo.memory_rows) as scans:
                found = app.recall(task['id'], kind='entity', key='shen', limit=5)
                recent_pages = scans.call_count
            assert len(found['matches']) == 5 and recent_pages == 6
            with patch.object(repo, 'memory_rows', wraps=repo.memory_rows) as scans:
                missing = app.recall(task['id'], kind='entity', key='absent', limit=5)
                missing_pages = scans.call_count
            assert not missing['matches'] and missing_pages == chapters
            first = app.recall(task['id'], chapter=1)
            oldest_hash = repo.chapter('main', 1)['prose']
            assert digest(first['prose']) == oldest_hash
            assert len(first['prose']) >= prose_han
            history_han = book['written_han']
            required_sizes = {n: json_bytes(v) for n, v in required.items()}
            repo.close()
            repo = SQLiteRepository(project)
            recovered = local_application(repo).recall(task['id'], chapter=1)
            assert recovered == first, 'Reopening must preserve the frozen source exactly.'
            return {
                'synthetic_source_chapters': chapters, 'synthetic_prose_han': history_han,
                'archived_volume_count': len(outlines) - 1,
                'late_writer_chapter': chapters + 1,
                'required_bytes': json_bytes(required), 'required_record_bytes': required_sizes,
                'compact_task_bytes': json_bytes(compact), 'frozen_work_bytes': json_bytes(work),
                'history_pointer_bytes': json_bytes(source), 'build_ms': round(build_ms, 3),
                'six_repeated_snapshot_document_reads': snapshot_reads,
                'recent_five_match_event_pages': recent_pages,
                'no_match_event_pages': missing_pages,
                'oldest_prose_complete_after_reopen': True,
                'sqlite_bytes': (project / 'novel.sqlite3').stat().st_size,
                'elapsed_seconds': round(time.perf_counter() - started, 3),
            }
        finally:
            repo.close()


def lifecycle_probe(chapters):
    """Use real submit/advance/complete across rolling volume boundaries."""
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix='novel-lifecycle-') as temporary:
        raw = contract(chapters=chapters, volumes=max(1, chapters // 10))
        raw['narrative_tracking'] = True
        raw['volume_outline']['scope'] = 'rolling'
        repo = SQLiteRepository.initialize(Path(temporary) / 'book', seeded_book(raw))
        try:
            app = local_application(repo)
            owner = app.run(finish=True, source='合成工程夹具授权跨卷完本验收。')['owner']
            handoff = drive(app, owner, limit=chapters * 4 + 20)
            assert handoff['action'] == 'ready_to_complete', handoff
            assert len(repo.headers('main')) == chapters
            result = app.complete(owner)
            book = repo.load()
            assert result['completed'] and result['ok'], result
            return {'accepted_chapters': chapters, 'volumes': len(raw['volumes']),
                    'accepted_han': book['written_han'], 'complete': True,
                    'elapsed_seconds': round(time.perf_counter() - started, 3),
                    'boundary': '真实工程提交链；短合成正文，不是数百万字文学写作。'}
        finally:
            repo.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sizes', default='100,500,1000,2000')
    parser.add_argument('--prose-han', type=int, default=3000)
    parser.add_argument('--lifecycle-chapters', type=int, default=100)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args(argv)
    try:
        sizes = sorted(set(int(n) for n in args.sizes.split(',')))
    except ValueError:
        parser.error('--sizes requires comma-separated integers')
    if not sizes or min(sizes) < 6 or args.prose_han < 1 or args.lifecycle_chapters < 1:
        parser.error('sizes >= 6, prose-han >= 1 and lifecycle-chapters >= 1 required')
    report = {'metadata': snapshot_metadata(),
              'scope': 'synthetic_engineering_only; not literary quality, tokens or billed cost',
              'sources': [source_probe(n, args.prose_han) for n in sizes],
              'lifecycle': lifecycle_probe(args.lifecycle_chapters)}
    first, last = report['sources'][0], report['sources'][-1]
    live_sizes = [r['required_bytes'] - r['required_record_bytes']['contract']
                  for r in report['sources']]
    report['growth'] = {
        'required_bytes': last['required_bytes'] - first['required_bytes'],
        'contract_bytes': last['required_record_bytes']['contract'] - first['required_record_bytes']['contract'],
        'required_except_contract_bytes': live_sizes[-1] - live_sizes[0],
        'boundary': '契约保留完整分卷表；已结历史不等于当前义务。显式依赖和未结义务增多时材料仍可增长。'}
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
