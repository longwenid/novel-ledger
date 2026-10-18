"""Minimal repro: the creative-memory channel cannot be reached, because no dispatch freezes prose.

    python validation/repro_understanding_channel.py

Understanding is filed with a draft receipt and validated against *frozen* prose:

    application._sources(work)   -> {chapter: prose}  from work['prose']     (application.py:137)
    application.submit           -> workflow.apply(..., self._sources(work), ...)   (application.py:326)
    workflow.apply  (workbench)  -> understanding.update(..., sources, evidence, actor)
    understanding.update         -> evidence(ref, sources) -> require(chapter in sources)

`context.build` declares `prose = []` and never appends to it (context.py:307, :512 — `grep -n
"prose.append" scripts` finds nothing), so `_sources(work)` is `{}` for **every** dispatch of
**every** stage. `understanding.update` requires at least one evidence reference per interpretation,
so every interpretation is refused with `evidence_scope 引文不在冻结正文范围内` and
`book['understanding']` can never leave `{'versions': []}`.

Expected: the draft envelope carries the frozen chapters an interpretation may quote (at least the
previous chapter), so a filed interpretation is accepted.
Actual: `work['prose'] == []`; filing fails at the first interpretation.
"""
import sys
import tempfile
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'tests')]

from novel_ledger.bootstrap import local_application as Application          # noqa: E402
from novel_ledger.contracts import Error                                     # noqa: E402
from novel_ledger.sqlite_store import SQLiteRepository                       # noqa: E402
from support import contract, drive, response, seeded_book                   # noqa: E402


def main():
    with tempfile.TemporaryDirectory() as temporary:
        repo = SQLiteRepository.initialize(Path(temporary) / 'book', seeded_book(contract(chapters=3)))
        try:
            app = Application(repo)
            owner = app.run(through=3, source='创作记忆通道复现。')['owner']
            drive(app, owner, until='write')
            app.submit(response(app))                      # chapter 1 freezes
            drive(app, owner, until='write')               # chapter 2's dispatch
            work = repo.pending()['input']
            print('1. work["prose"]            =', work['prose'])
            print('2. app._sources(work)       =', sorted(app._sources(work)))
            print('3. frozen chapters          =', [row['n'] for row in repo.headers('main')])
            result = response(app)
            result['data']['understanding'] = [{
                'id': 'motive', 'kind': 'character', 'claim': '工程样本。', 'status': 'tentative',
                'subjects': ['shen'], 'topics': [], 'reason': '仅验证通道，不代表文学判断。',
                'evidence': [{'chapter': 1, 'quote': '次日'}], 'counterevidence': []}]
            try:
                app.submit(result)
            except Error as exc:
                print('4. submit with understanding -> Error(%s) %s' % (exc.code, exc.message))
                print('5. details                  ->', exc.details)
                return 1
            print('4. submit with understanding -> accepted')
            return 0
        except BaseException:
            traceback.print_exc()
            return 1
        finally:
            repo.close()


if __name__ == '__main__':
    sys.exit(main())
