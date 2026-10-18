"""Minimal repro: the declared merged tier still dispatches a separate chapter outline.

    python validation/repro_merged_tier.py

The frozen spec (§2) rewrites `PIPELINE_SHAPES` so the smallest tiers answer a volume outline and
that volume's chapter outlines in one dispatch:

    't0': {'merge_chapter_outline': True}, 't1': {... True}, 't2'..'t5': False

`workflow.merges_chapter_outline(book)` reads that table, and the guard test
`tests/test_pipeline_shapes.py::test_a_merged_tier_answers_the_volume_and_its_chapters_in_one_dispatch`
asserts the observable consequence: driving a t0 book to its first draft must produce the stages
`['volume_outline', 'write']` with `book['chapter_outlines']['v1']` already filled.

Expected: `['volume_outline', 'write']`.
Actual (this tree): `['volume_outline', 'chapter_outline', 'write']` — nothing in `workflow.choose`
or `workflow.apply` reads the merge switch, `stages.BLOCKS['volume_outline']` has no `chapters`
block, and the flag is only ever read by its own guard test.
"""
import sys
import tempfile
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'tests')]

from novel_ledger.bootstrap import local_application as Application          # noqa: E402
from novel_ledger.contracts import PIPELINE_SHAPES                           # noqa: E402
from novel_ledger.sqlite_store import SQLiteRepository                       # noqa: E402
from novel_ledger import workflow                                            # noqa: E402
from support import contract, response, seeded_book                          # noqa: E402


def tier_contract(tier):
    """The t0 band, so `tier_of` resolves the shape the spec declares for the smallest tier."""
    raw = contract(chapters=2, volumes=1)
    raw.update(chapter_min=tier['chapter_min'], chapter_max=tier['chapter_max'],
               chapter_aim=tier['chapter_aim'])
    return raw


def main():
    from novel_ledger.contracts import SCALE_TIERS
    tier = next(row for row in SCALE_TIERS if row['id'] == 't0')
    print('1. PIPELINE_SHAPES[t0] =', PIPELINE_SHAPES.get('t0'))
    print('2. merges_chapter_outline(seeded t0 book) =',
          workflow.merges_chapter_outline(seeded_book(tier_contract(tier))))
    with tempfile.TemporaryDirectory() as temporary:
        repo = SQLiteRepository.initialize(Path(temporary) / 'book', seeded_book(tier_contract(tier)))
        try:
            app = Application(repo)
            owner = app.run(through=2, source='合并档位复现。')['owner']
            stages = []
            for _ in range(12):
                handoff = app.advance(owner=owner)
                if handoff['action'] != 'task_ready':
                    print('3. stopped at', handoff['action'])
                    break
                stages.append(handoff['task']['stage'])
                if handoff['task']['stage'] == 'write':
                    break
                app.submit(response(app))
            book = repo.load()
            print('4. stages before the first draft =', stages)
            print('5. chapter_outlines installed    =', sorted(book.get('chapter_outlines') or {}))
            expected = ['volume_outline', 'write']
            print('6. expected                      =', expected)
            return 0 if stages == expected else 1
        except BaseException:
            traceback.print_exc()
            return 1
        finally:
            repo.close()


if __name__ == '__main__':
    sys.exit(main())
