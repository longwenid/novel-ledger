"""Same-input all/rolling engineering acceptance. Synthetic prose; no model or billing calls."""
import argparse
import json
import sys
import tempfile
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'tests'), str(ROOT / 'validation')]
from novel_ledger.bootstrap import LocalRuntime, local_application as Application
from novel_ledger.contracts import dump, han_count
from novel_ledger.sqlite_store import SQLiteRepository
from support import contract, response, seeded_book
from measure import snapshot_metadata


def run_case(path, scope, chapters=36, volumes=3):
    raw = contract(chapters, volumes)
    raw['narrative_tracking'] = True
    raw['volume_outline']['scope'] = scope
    repo = SQLiteRepository.initialize(path, seeded_book(raw))
    app = Application(repo)
    owner = app.run(finish=True, source='工程验收夹具授权合成正文完本。')['owner']
    dispatches = []
    first_prose = None
    restarted = False
    started = perf_counter()
    try:
        for _ in range(chapters * 5):
            step = app.advance(owner=owner)
            if step['action'] == 'await_author':
                app.approve(step['prose_hash'], '工程夹具认可当前版本。', owner)
                continue
            if step['action'] != 'task_ready':
                if step['action'] != 'ready_to_complete':
                    raise AssertionError(step)
                break
            work = repo.pending()['input']
            if work['stage'] == 'write' and first_prose is None:
                first_prose = {'dispatches': len(dispatches),
                               'required_bytes': sum(d['required_bytes'] for d in dispatches),
                               'volume_outlines': len(repo.load()['volumes_outline']),
                               'generated_han': sum(d['result_han'] for d in dispatches)}
            dispatches.append({'stage': work['stage'], 'chapter': work['chapter'],
                               'required_bytes': len(dump({name: repo.read_document(work['records'][name])
                                                         for name in work['required']}).encode('utf-8'))})
            result = response(app)
            dispatches[-1]['result_han'] = han_count(dump(result['data']))
            if work['stage'] == 'volume_outline':
                dispatches[-1]['volume_outline_han'] = han_count(dump(result['data']))
            app.submit(result)
            if len(repo.headers('main')) == chapters // volumes and not restarted:
                app.pause('卷界暂停与重启验收。', owner=owner)
                repo.close()
                repo = SQLiteRepository(path)
                app = Application(repo)
                app.resume(owner=owner)
                restarted = True
        else:
            raise AssertionError('合成流程未在有界步数内完成')
        completed = app.complete(owner=owner)
        delivered = LocalRuntime(repo).deliver()
        assert delivered['delivered'] and delivered['snapshot_hash'] == completed['snapshot_hash']
        assert all(Path(row['path']).is_file() for row in delivered['files'])
        delivery_summary = {'delivered': True, 'snapshot_hash': delivered['snapshot_hash'],
                            'files_verified': len(delivered['files'])}
        assert completed['completed'] and len(repo.headers('main')) == chapters
        assert repo.load()['status'] == 'completed' and restarted
        return {'scope': scope, 'chapters': chapters, 'volumes': volumes,
                'completed': True, 'volume_boundary_restart': restarted,
                'delivery': delivery_summary, 'elapsed_seconds': round(perf_counter() - started, 3),
                'first_prose': first_prose,
                'dispatches': dispatches, 'total_dispatches': len(dispatches),
                'total_required_bytes': sum(d['required_bytes'] for d in dispatches),
                'written_han': repo.load()['written_han']}
    finally:
        repo.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='novel-architecture-') as temp:
        rows = [run_case(Path(temp) / scope, scope) for scope in ('all', 'rolling')]
    result = {'metadata': snapshot_metadata(ROOT), 'cases': rows,
              'boundary': '合成短正文的36章3卷工程验收；验证派工、卷界重启、完本交付和材料量。'
                          '未调用真实创作模型；耗时为本机引擎耗时，不代表创作延迟、文学效果或计费。'}
    if args.out:
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
