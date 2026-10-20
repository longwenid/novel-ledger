#!/usr/bin/env python3
"""Measure retained cumulative snapshots in an isolated synthetic SQLite project.

This is a storage probe, not a novel pipeline or literary acceptance test. Each
chapter settles one legal character-development event and adds one version of
the same interpretation. It saves the book and freezes complete state/memory
documents exactly as task source retention requires. Probe tasks are deliberately
minimal storage roots; no model, submit, outline validation, complete or deliver
is exercised. All project data is removed on exit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'tests')]
from novel_ledger import facts, understanding, workflow
from novel_ledger.contracts import digest, dump
from novel_ledger.evidence import evidence
from novel_ledger.sqlite_store import SQLiteRepository
from support import tracked_contract

FINGERPRINT_PATHS = [
    'scripts/novel_ledger/' + name + '.py' for name in
    ('sqlite_store', 'book_state', 'facts', 'understanding', 'workflow',
     'contracts', 'evidence', 'store_keys')
] + ['tests/support.py']


def fingerprints():
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in FINGERPRINT_PATHS}


def storage_bytes(repo):
    result = {
        'document_bytes': repo.db.execute(
            'SELECT coalesce(sum(length(CAST(value AS BLOB))),0) FROM documents').fetchone()[0],
        'document_count': repo.db.execute('SELECT count(*) FROM documents').fetchone()[0],
        'database_bytes': (repo.project / 'novel.sqlite3').stat().st_size,
    }
    has_blocks = repo.db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='document_blocks'").fetchone()
    result['document_block_bytes'] = (repo.db.execute(
        'SELECT coalesce(sum(length(CAST(value AS BLOB))),0) FROM document_blocks').fetchone()[0]
        if has_blocks else 0)
    result['document_block_count'] = (repo.db.execute('SELECT count(*) FROM document_blocks').fetchone()[0]
                                      if has_blocks else 0)
    result['physical_document_bytes'] = result['document_bytes'] + result['document_block_bytes']
    return result


def frozen_source_storage(repo, snapshots):
    """Count the unique physical closure owned by the frozen complete-source roots.

    This observes the documented storage format only for byte accounting. Correctness
    remains independently checked through the public read_document API.
    """
    roots = {key for snapshot in snapshots for key in snapshot['records'].values()}
    document_bytes, block_bytes, seen, pending = 0, 0, set(), []
    for key in roots:
        row = repo.db.execute('SELECT value FROM documents WHERE hash=?', (key,)).fetchone()
        if row is None:
            raise AssertionError('a frozen logical document root is missing')
        raw = row[0]
        document_bytes += len(raw.encode('utf-8'))
        if raw.startswith('NL5\n'):
            pending.append(json.loads(raw[4:]))
    while pending:
        key = pending.pop()
        if key in seen:
            continue
        seen.add(key)
        row = repo.db.execute('SELECT value FROM document_blocks WHERE hash=?', (key,)).fetchone()
        if row is None:
            raise AssertionError('a frozen physical block is missing')
        block_bytes += len(row[0].encode('utf-8'))
        kind, payload = json.loads(row[0])
        if kind in ('list-index', 'dict-index'):
            pending.extend(payload)
        elif kind in ('list', 'dict'):
            encoded_values = payload if kind == 'list' else [value for _, value in payload]
            pending.extend(value for encoding, value in encoded_values if encoding == 'ref')
        elif kind != 'value':
            raise AssertionError('unrecognized physical block kind in byte accounting')
    return {'logical_document_count': len(roots), 'unique_block_count': len(seen),
            'document_root_bytes': document_bytes, 'unique_block_bytes': block_bytes,
            'physical_bytes': document_bytes + block_bytes}


def verify_snapshot_sources(repo, snapshots):
    """Read every historical root; a readable head is insufficient evidence of retention."""
    started, cpu_started = time.perf_counter(), time.process_time()
    stream, logical_bytes = hashlib.sha256(), 0
    for snapshot in snapshots:
        number = snapshot['chapter']
        # Fetch the frozen task as well: local expected hashes must still be reachable
        # through immutable task roots after pruning and a fresh connection.
        task = repo.task(snapshot['task'])
        if task['status'] != 'done' or task['input']['records'] != snapshot['records']:
            raise AssertionError('frozen task lost its original complete-source roots')
        state = repo.read_document(snapshot['records']['complete_state'])
        memory = repo.read_document(snapshot['records']['complete_understanding'])
        for name, value in (('complete_state', state), ('complete_understanding', memory)):
            encoded = dump(value).encode('utf-8')
            actual = hashlib.sha256(encoded).hexdigest()
            if actual != snapshot['records'][name]:
                raise AssertionError('historical complete-source digest differs from its original value')
            logical_bytes += len(encoded)
            stream.update((str(number) + ':' + name + ':' + actual + '\n').encode('ascii'))
        developments = state['developments']['shen']
        versions = memory['versions']
        if (len(developments) != number or len(versions) != number
                or [row['evidence']['chapter'] for row in developments] != list(range(1, number + 1))
                or [row['version'] for row in versions] != list(range(1, number + 1))
                or [row['producer'] for row in versions] != ['fixture-' + str(n) for n in range(1, number + 1)]
                or [row['evidence'][0]['chapter'] for row in versions] != list(range(1, number + 1))
                or len(understanding.latest(memory)) != 1):
            raise AssertionError('historical complete source lost developments or interpretation versions')
    return {
        'frozen_tasks_verified': len(snapshots), 'complete_states_verified': len(snapshots),
        'complete_understandings_verified': len(snapshots),
        'full_logical_hashes_verified': 2 * len(snapshots),
        'all_expected_version_sequences_verified': True,
        'logical_frozen_source_bytes': logical_bytes,
        'frozen_source_hash_stream_sha256': stream.hexdigest(),
        'elapsed_s': round(time.perf_counter() - started, 3),
        'cpu_s': round(time.process_time() - cpu_started, 3),
    }


def latest_read_cost(repo, records, repeats=3):
    samples = []
    for _ in range(repeats):
        started, cpu_started = time.perf_counter(), time.process_time()
        values = [repo.read_document(records[name])
                  for name in ('complete_state', 'complete_understanding')]
        samples.append({'elapsed_ms': (time.perf_counter() - started) * 1000,
                        'cpu_ms': (time.process_time() - cpu_started) * 1000})
        for name, value in zip(('complete_state', 'complete_understanding'), values):
            if digest(value) != records[name]:
                raise AssertionError('latest complete-source read differs from the frozen value')
    return {
        'operation': 'read_complete_state_and_understanding', 'documents_per_sample': 2,
        'repeats': repeats, 'connection_reopened': False,
        'elapsed_ms_median': round(statistics.median(s['elapsed_ms'] for s in samples), 3),
        'cpu_ms_median': round(statistics.median(s['cpu_ms'] for s in samples), 3),
        'samples': [{key: round(value, 3) for key, value in row.items()} for row in samples],
        'boundary': 'Read plus production integrity verification; independent extra digest check is outside timing.',
    }


def reopen_and_verify(repo, snapshots, chapter_count, prose_han):
    project = repo.project
    repo.close()
    started, cpu_started = time.perf_counter(), time.process_time()
    repo = SQLiteRepository(project)
    restored = repo.load()
    reload = {
        'operation': 'reopen_and_load', 'connection_reopened': True,
        'elapsed_ms': round((time.perf_counter() - started) * 1000, 3),
        'cpu_ms': round((time.process_time() - cpu_started) * 1000, 3),
        'latest_interpretations': len(understanding.latest(restored['understanding'])),
        'interpretation_versions': len(restored['understanding']['versions']),
    }
    first = repo.chapter('main', 1)
    first_prose = repo.read_document(first['prose'])
    if (reload['interpretation_versions'] != chapter_count or reload['latest_interpretations'] != 1
            or digest(restored['state']) != snapshots[-1]['records']['complete_state']
            or digest(restored['understanding']) != snapshots[-1]['records']['complete_understanding']):
        raise AssertionError('reopened current book differs from its expected complete source')
    if (first_prose != '第1章：沈桐承担代价。' + '测' * prose_han
            or digest(first_prose) != first['prose']):
        raise AssertionError('reopened first chapter differs from its complete frozen source')
    reload.update(first_prose_hash=first['prose'], first_prose_hash_verified=True, first_prose_complete=True)
    return repo, reload, verify_snapshot_sources(repo, snapshots)


def measure(checkpoints=(100, 500), *, prose_han=3000, prune=True, progress=None):
    checkpoints = sorted(set(checkpoints))
    if not checkpoints or any(type(n) is not int or n < 1 for n in checkpoints):
        raise ValueError('chapter checkpoints must be positive integers')
    if type(prose_han) is not int or prose_han < 1:
        raise ValueError('prose_han must be a positive integer')
    report = {
        'schema': 'novel-ledger.storage-snapshot-probe/2',
        'synthetic': True,
        'conditions': {
            'chapter_checkpoints': checkpoints,
            'filler_han_per_chapter': prose_han,
            'contract_chapters': max(1667, checkpoints[-1]),
            'development_events_per_chapter': 1,
            'interpretation_ids': 1,
            'new_interpretation_versions_per_chapter': 1,
            'freeze_each_state_and_understanding': True,
            'nominal_word_count': 'Filler characters only; stored han is a synthetic lower bound.',
            'boundary': 'Storage-only synthetic tasks; no submit, model, full pipeline or literary acceptance.',
            'timing': 'Generation wall/CPU exclude checkpoint reads, storage accounting, full verification and prune.',
        },
        'metric_definitions': {
            'document_bytes': 'UTF-8 bytes in documents.value only; unchanged from the historical probe.',
            'document_block_bytes': 'UTF-8 bytes in document_blocks.value; zero when the table is absent.',
            'physical_document_bytes': 'document_bytes + document_block_bytes; excludes SQLite indexes and task cells.',
            'frozen_source_storage': 'Unique documents.value roots plus all reachable physical blocks for frozen complete sources; shared blocks count once.',
            'logical_frozen_source_bytes': 'Sum of every original complete_state and complete_understanding canonical JSON byte length.',
            'database_bytes': 'Entire SQLite file including metadata, indexes, task cells, unused pages and document storage.',
        },
        'source_sha256': fingerprints(),
        'probe_source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'checkpoints': [],
    }
    with tempfile.TemporaryDirectory(prefix='novel-snapshot-probe-') as temporary:
        repo = SQLiteRepository.initialize(
            Path(temporary) / 'book',
            workflow.new_book(tracked_contract(max(1667, checkpoints[-1]))))
        try:
            book, previous = repo.load(), 'genesis'
            snapshots, logical_frozen_bytes = [], 0
            generated_s, generated_cpu_s = 0, 0
            for number in range(1, checkpoints[-1] + 1):
                started, cpu_started = time.perf_counter(), time.process_time()
                prose = '第%d章：沈桐承担代价。' % number + '测' * prose_han
                ref = {'chapter': number, 'quote': '沈桐承担代价。'}
                event = {
                    'op': 'character_development', 'entity': 'shen',
                    'choice': '选择核实来源并继续调查。',
                    'cost': '承担调查后果并失去一次机会。',
                    'change': '改用证据判断人物的可信度。', 'evidence': ref,
                }
                with repo.transaction():
                    book['state'], normalized = facts.settle(book['state'], [event], prose, number)
                    book['understanding'] = understanding.update(
                        book['understanding'], [{
                            'id': 'hero', 'kind': 'character', 'claim': '沈桐对人的信任继续变化。',
                            'status': 'supported', 'subjects': ['shen'], 'topics': [],
                            'reason': '本章选择与代价。', 'evidence': [ref], 'counterevidence': [],
                        }], {number: prose}, evidence, 'fixture-' + str(number))
                    row = {
                        'n': number, 'title': '存储实验', 'prose': repo.document(prose),
                        'events': repo.document(normalized), 'plan': repo.document({}),
                        'review': repo.document({}), 'state_hash': digest(book['state']),
                        'summary': '存储实验', 'han': prose_han,
                    }
                    row['chain'] = facts.chain(previous, row, digest(book['contract']))
                    repo.add_chapter('main', row)
                    previous = row['chain']
                    book.update(written_han=number * prose_han, revision=number)
                    repo.save(book)
                    state = repo.document(book['state'])
                    memory = repo.document(book['understanding'])
                    if state != row['state_hash'] or memory != digest(book['understanding']):
                        raise AssertionError('document write returned a different logical hash')
                    logical_frozen_bytes += len(dump(book['state']).encode('utf-8'))
                    logical_frozen_bytes += len(dump(book['understanding']).encode('utf-8'))
                    task = repo.add_task({'records': {'complete_state': state,
                                                     'complete_understanding': memory},
                                          'stage': 'storage-probe'})
                    # A finished frozen task remains a root for immutable complete sources.
                    repo.db.execute("UPDATE tasks SET status='done' WHERE id=?", (task['id'],))
                    snapshots.append({'chapter': number, 'task': task['id'],
                                      'records': {'complete_state': state, 'complete_understanding': memory}})
                generated_s += time.perf_counter() - started
                generated_cpu_s += time.process_time() - cpu_started
                if number in checkpoints:
                    point = {
                        'chapters': number, 'synthetic_prose_han_at_least': number * prose_han,
                        **storage_bytes(repo),
                        'current_state_bytes': len(dump(book['state']).encode('utf-8')),
                        'current_understanding_bytes': len(dump(book['understanding']).encode('utf-8')),
                        'logical_frozen_source_bytes': logical_frozen_bytes,
                        'frozen_source_storage': frozen_source_storage(repo, snapshots),
                        'elapsed_s': round(generated_s, 3),
                        'cpu_s': round(generated_cpu_s, 3),
                        'latest_source_read': latest_read_cost(repo, snapshots[-1]['records']),
                    }
                    report['checkpoints'].append(point)
                    if progress:
                        progress(point)
            repo, report['reload'], report['frozen_sources_before_prune'] = reopen_and_verify(
                repo, snapshots, checkpoints[-1], prose_han)
            if report['frozen_sources_before_prune']['logical_frozen_source_bytes'] != logical_frozen_bytes:
                raise AssertionError('reopened frozen-source bytes differ from original values')
            if prune:
                before = storage_bytes(repo)
                started, cpu_started = time.perf_counter(), time.process_time()
                removed = repo.prune()
                report['prune'] = {
                    **removed, **storage_bytes(repo), 'before': before,
                    'elapsed_s': round(time.perf_counter() - started, 3),
                    'cpu_s': round(time.process_time() - cpu_started, 3),
                }
                report['prune']['frozen_source_storage'] = frozen_source_storage(repo, snapshots)
                repo, report['reload_after_prune'], report['frozen_sources_after_prune'] = reopen_and_verify(
                    repo, snapshots, checkpoints[-1], prose_han)
                for key in ('logical_frozen_source_bytes', 'frozen_source_hash_stream_sha256'):
                    if report['frozen_sources_after_prune'][key] != report['frozen_sources_before_prune'][key]:
                        raise AssertionError('prune changed or lost an original complete frozen source')
                started, cpu_started = time.perf_counter(), time.process_time()
                second_pass = repo.prune()
                report['prune']['second_pass'] = {
                    **second_pass, 'elapsed_s': round(time.perf_counter() - started, 3),
                    'cpu_s': round(time.process_time() - cpu_started, 3),
                }
                if second_pass['documents_removed'] or second_pass.get('blocks_removed', 0):
                    raise AssertionError('second prune still removes live-source documents')
        finally:
            repo.close()
    report['temporary_project_removed'] = True
    report['source_sha256_after'] = fingerprints()
    report['source_unchanged_during_probe'] = report['source_sha256_after'] == report['source_sha256']
    if not report['source_unchanged_during_probe']:
        raise AssertionError('measured source changed during the probe; repeat with stable source')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sizes = parser.add_mutually_exclusive_group()
    sizes.add_argument('--chapters', type=int, nargs='+', default=[100, 500],
                       help='Checkpoints; add 1667 explicitly for at least five million filler Han characters.')
    sizes.add_argument('--sizes', help='Comma-separated checkpoint alias, for example 100,500,1667.')
    parser.add_argument('--prose-han', type=int, default=3000)
    parser.add_argument('--no-prune', action='store_true')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    checkpoints = args.chapters
    if args.sizes is not None:
        try:
            checkpoints = [int(value) for value in args.sizes.split(',')]
        except ValueError:
            parser.error('--sizes must contain comma-separated positive integers')
    if any(n < 1 for n in checkpoints) or args.prose_han < 1:
        parser.error('chapter checkpoints and --prose-han must be positive integers')
    result = measure(checkpoints, prose_han=args.prose_han, prune=not args.no_prune,
                     progress=lambda point: print(json.dumps(point, ensure_ascii=False), file=sys.stderr, flush=True))
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding='utf-8')
    else:
        print(rendered, end='')


if __name__ == '__main__':
    main()
