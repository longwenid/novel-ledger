"""Minimal repro: a settled knowledge coordinate reads back as nothing, so the chain never matches.

    python validation/repro_knowledge_readback.py

`facts.settle` stores a knowledge entry's stance in its own vocabulary
(`facts.py:130`: `knows | believes | suspects | disproved`). A chapter outline declares the same
coordinate in the outline vocabulary (`drift.REVEALS`: `hinted | suspected | misled | confirmed |
retracted`), and `drift.STANCES` maps outline → settled:

    {'hinted': 'suspects', 'suspected': 'suspects', 'misled': 'believes',
     'confirmed': 'knows', 'retracted': 'disproved'}

`drift._project` reads a *settled* entry and runs that same forward map over it
(`drift.py:268`, `STANCES.get(entry.get('stance'))`), so **every settled knowledge coordinate
projects to None** — the inverse map is missing.

Consequences, both reproduced with the repository's own v2 fixtures:

1. `drift.state_mismatch(state, row)` reports a mismatch for every chapter outline that declares a
   knowledge delta, so `workflow.choose` re-plans the volume's outlines instead of drafting.
2. `drift.validate_chapter_outline` compares `enter`/delta `from` values against that same
   projection, so the re-plan receipt is rejected with `design_drift` — and it can never be
   answered, because the receipt describes the state the engine refuses to see.

Net effect: a book whose chapter outline declares one knowledge change commits chapter 1 and then
stops. Expected `hinted`/`suspected`; actual `None`.

End-to-end reproduction (needs the shared fixtures, `tests/support.py`):

    python - <<'PY'
    import sys, tempfile
    from pathlib import Path
    sys.path[:0] = ['scripts', 'tests']
    from novel_ledger.bootstrap import local_application as Application
    from novel_ledger.sqlite_store import SQLiteRepository
    from support import contract, seeded_book, response
    repo = SQLiteRepository.initialize(Path(tempfile.mkdtemp()) / 'b', seeded_book(contract(chapters=3)))
    app = Application(repo); owner = app.run(through=3, source='repro')['owner']
    for _ in range(8):
        handoff = app.advance(owner=owner)
        if handoff['action'] == 'await_author':
            app.approve(handoff['prose_hash'], 'repro', owner); continue
        if handoff['action'] != 'task_ready':
            print('stopped at', handoff['action']); break
        app.submit(response(app))
    print('committed chapters:', [row['n'] for row in repo.headers('main')])
    # observed: chapter 1 commits, then Error(design_drift, 章纲状态链核账未通过) on the next
    #           chapter_outline dispatch; the payload carries drift rows expect='hinted' got=None.
    PY
"""
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'scripts')]
from novel_ledger import drift                      # noqa: E402

SETTLED = ('knows', 'believes', 'suspects', 'disproved')


def main():
    print('1. drift.STANCES (outline -> settled):', drift.STANCES)
    print('2. facts.settle writes stance in     :', SETTLED, '(facts.py:130)')
    state = {'clock': 0, 'knowledge': {'shen:source': {'stance': 'suspects', 'claim': '来源与签字有关。'}}}
    print('3. drift.project(state, "knowledge", "shen:source") ->',
          repr(drift.project(state, 'knowledge', 'shen:source')), '(expected hinted/suspected)')
    broken = []
    for stance in SETTLED:
        probe = {'knowledge': {'k': {'stance': stance}}}
        value = drift.project(probe, 'knowledge', 'k')
        print('   settled %-9s -> %r' % (stance, value))
        if value is None:
            broken.append(stance)
    print('4. settled values that read back as None:', broken)
    return 0 if not broken else 1


if __name__ == '__main__':
    sys.exit(main())
