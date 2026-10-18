"""The pipeline is five steps, and its shape is declared per size class.

v2 deleted the review chain: a real project used to pay a world review, a contract review, two
design reviews, volume-outline reviews, per-chapter reviews and a layered scope review before the
first word was accepted. What remains is a constant: one dispatch writes the world and the
contract, one writes every volume's outline, one writes a volume's chapter outlines, and each
chapter is drafted against its own outline. On the smallest tiers the chapter-outline dispatch is
merged into the volume-outline one, because a few hundred characters of deltas do not justify a
second cold session; every tier still declares which shape it uses, so a tier cannot arrive
without answering the question.
"""
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from novel_ledger import store_keys, workflow
from novel_ledger.bootstrap import local_application as Application
from novel_ledger.contracts import PIPELINE_SHAPES, SCALE_TIERS
from novel_ledger.sqlite_store import SQLiteRepository
from support import check_dispatch, contract, long_prose, response, seeded_book


# Every stage the old architecture dispatched and v2 removed. A pipeline that still dispatches one
# of them is running a review branch that has no owner any more.
DELETED_STAGES = frozenset({
    'world_review', 'contract_review', 'design_review', 'outline_review', 'chapter_review',
    'book_plan', 'volume_plan', 'plan', 'profiles', 'scope_review', 'scope_synthesis',
    'revision_review', 'alignment_plan', 'alignment_review',
})
# The five steps, as the dispatches that carry them (the opening gates are executed by the
# controller, so they are not frozen tasks).
PIPELINE_STEPS = ('volume_outline', 'chapter_outline', 'write')


def tier_contract(tier_id, chapters=2, volumes=None):
    """A contract whose chapter band names `tier_id`, sized to `chapters` chapters."""
    row = next(entry for entry in SCALE_TIERS if entry['id'] == tier_id)
    raw = contract(chapters=chapters, volumes=volumes or min(row['volume_count'], chapters))
    raw.update(chapter_min=row['chapter_min'], chapter_max=row['chapter_max'],
               chapter_aim=row['chapter_aim'])
    return raw


def record_stages(app, owner=None, until=None):
    """drive(), but remembering every dispatched stage and filing a long enough draft."""
    if owner is None:
        lease = app.repo.get(store_keys.CONTROLLER)
        owner = (lease or {}).get('owner')
    stages = []
    for _ in range(200):
        handoff = app.advance(owner=owner)
        if handoff['action'] == 'await_author':
            app.approve(handoff['prose_hash'], '工程夹具认可当前版本。', owner)
            continue
        if handoff['action'] != 'task_ready':
            return handoff, Counter(stages)
        work = app.repo.pending()['input']
        stages.append(work['stage'])
        if until and work['stage'] == until:
            return handoff, Counter(stages)
        check_dispatch(work)
        result = response(app)
        if isinstance(result['data'].get('prose'), str):
            prose = long_prose(work['chapter'])
            result['data']['prose'] = prose
            for item in result['data']['drift_check']['items']:
                item['evidence'] = {'chapter': work['chapter'], 'quote': prose[:20]}
        app.submit(result)
    raise AssertionError('工程流程没有在有限步骤内停止')


def drive_ordered(app, owner=None, limit=200):
    """Advance a whole book with chapter-length drafts, returning the dispatch order as dispatched.

    `record_stages` returns a Counter, which is what shape tests want; a merged receipt or an
    ahead-of-the-front outline dispatch is a *sequence* claim, so this keeps the order and files the
    padded prose every large-tier band needs.
    """
    if owner is None:
        lease = app.repo.get(store_keys.CONTROLLER)
        owner = (lease or {}).get('owner')
    stages = []
    for _ in range(limit):
        handoff = app.advance(owner=owner)
        if handoff['action'] == 'await_author':
            app.approve(handoff['prose_hash'], '工程夹具认可当前版本。', owner)
            continue
        if handoff['action'] != 'task_ready':
            return handoff, stages
        work = app.repo.pending()['input']
        stages.append(work['stage'])
        check_dispatch(work)
        result = response(app)
        if isinstance(result['data'].get('prose'), str):
            prose = long_prose(work['chapter'])
            result['data']['prose'] = prose
            for item in result['data']['drift_check']['items']:
                item['evidence'] = {'chapter': work['chapter'], 'quote': prose[:20]}
        app.submit(result)
    raise AssertionError('工程流程没有在有限步骤内停止')


class PipelineShapeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / 'book'

    def tearDown(self):
        self.temp.cleanup()

    def drive_tier(self, tier_id, chapters=2, volumes=None, until=None):
        repo = SQLiteRepository.initialize(
            self.project, seeded_book(tier_contract(tier_id, chapters=chapters, volumes=volumes)))
        app = Application(repo)
        try:
            run = app.run(through=chapters, source='工程夹具授权按档位形状跑完。')
            handoff, stages = record_stages(app, run['owner'], until=until)
            book = repo.load()
            repo.close()
            return handoff, stages, book
        except BaseException:
            repo.close()
            raise

    def test_every_tier_declares_only_the_chapter_outline_merge(self):
        self.assertEqual(set(PIPELINE_SHAPES), {row['id'] for row in SCALE_TIERS})
        for shape in PIPELINE_SHAPES.values():
            self.assertEqual(set(shape), {'merge_chapter_outline'})

    def test_the_merge_switch_is_read_through_one_table(self):
        for tier_id in ('t0', 't1'):
            self.assertTrue(workflow.merges_chapter_outline(seeded_book(tier_contract(tier_id))),
                            '%s 应合并章纲派工' % tier_id)
        for tier_id in ('t2', 't3', 't4', 't5'):
            self.assertFalse(workflow.merges_chapter_outline(seeded_book(tier_contract(tier_id))),
                             '%s 应分开派发卷纲与章纲' % tier_id)

    def test_a_large_tier_drafts_volume_then_chapter_outlines_then_prose(self):
        handoff, stages, _book = self.drive_tier('t2', chapters=4, volumes=4, until='write')
        self.assertEqual(handoff['action'], 'task_ready')
        self.assertEqual(handoff['task']['stage'], 'write')
        self.assertEqual(list(stages), ['volume_outline', 'chapter_outline', 'write'])
        self.assertFalse(set(stages) & DELETED_STAGES)

    def test_no_tier_dispatches_any_deleted_review_stage(self):
        handoff, stages, _book = self.drive_tier('t2', chapters=4, volumes=4)
        self.assertEqual(handoff['action'], 'target_reached')
        self.assertFalse(set(stages) & DELETED_STAGES,
                         '仍有被删除阶段的派工：' + ','.join(sorted(set(stages) & DELETED_STAGES)))
        self.assertEqual(set(stages), {'volume_outline', 'chapter_outline', 'write'})

    def test_a_merged_tier_answers_the_volume_and_its_chapters_in_one_dispatch(self):
        handoff, stages, book = self.drive_tier('t0', chapters=2, volumes=1, until='write')
        self.assertEqual(handoff['action'], 'task_ready')
        self.assertEqual(handoff['task']['stage'], 'write')
        # The merge is the tier's declared shape: both artifacts came back from the volume dispatch,
        # so no chapter_outline dispatch exists between the volume outline and the first draft.
        self.assertEqual(list(stages), ['volume_outline', 'write'])
        self.assertEqual([row['chapter'] for row in book['chapter_outlines']['v1']], [1, 2])
        self.assertEqual(sorted(book['volumes_outline']), ['v1'])

    def test_the_first_draft_waits_for_volume_and_chapter_outlines(self):
        repo = SQLiteRepository.initialize(self.project, seeded_book(tier_contract('t2', 4, 4)))
        app = Application(repo)
        try:
            owner = app.run(through=4, source='工程夹具授权四章。')['owner']
            stages = []
            for _ in range(20):
                handoff = app.advance(owner=owner)
                if handoff['action'] != 'task_ready':
                    break
                stages.append(handoff['task']['stage'])
                if handoff['task']['stage'] == 'write':
                    break
                app.submit(response(app))
            self.assertEqual(stages[0], 'volume_outline')
            self.assertIn('chapter_outline', stages)
            self.assertEqual(stages[-1], 'write')
            book = repo.load()
            self.assertEqual(sorted(book['volumes_outline']), ['v1', 'v2', 'v3', 'v4'])
            self.assertEqual(sorted(book['chapter_outlines']), ['v1'])
        finally:
            repo.close()

    def test_a_merged_two_volume_tier_hands_its_promise_to_the_next_volume(self):
        """t1's declared shape, end to end: one outline dispatch, then prose, and a paid promise.

        The merged receipt carries both volumes' chapter outlines, so the engine is the only thing
        that can carry volume one's continuing promise into volume two: the fixture designs the two
        chains as one and the engine validates them as one. Both the dispatch order and the settled
        ledger are asserted, because a merged receipt that lost its promise would still finish.
        """
        repo = SQLiteRepository.initialize(self.project, seeded_book(tier_contract('t1', 4, 2)))
        app = Application(repo)
        try:
            owner = app.run(finish=True, source='工程夹具授权 t1 两卷完本。')['owner']
            handoff, stages = drive_ordered(app, owner)
            self.assertEqual(handoff['action'], 'ready_to_complete')
            self.assertEqual(stages, ['volume_outline', 'write', 'write', 'write', 'write'])
            self.assertNotIn('chapter_outline', stages)
            book = repo.load()
            self.assertEqual(sorted(book['chapter_outlines']), ['v1', 'v2'])
            self.assertEqual([row['chapter'] for row in book['chapter_outlines']['v2']], [3, 4])
            declared = book['volumes_outline']['v1']['hooks'][1]
            self.assertTrue(declared['continues'])
            carry = book['state']['hooks']['hook-v1-carry']
            self.assertEqual(carry['status'], 'paid')
            self.assertEqual(carry['due'], declared['payoff'][1])          # 3 == volume two's first
            self.assertEqual(book['state']['hooks']['hook-v1-required']['status'], 'paid')
            self.assertEqual(book['state']['hooks']['hook-v2-required']['status'], 'paid')
            self.assertTrue(app.complete(owner)['completed'])
        finally:
            repo.close()

    def test_scope_all_lays_every_volumes_chapter_outlines_before_the_first_word(self):
        """The pre-laid chain: one chapter-outline dispatch per volume, all before prose starts.

        `scope=all` is the author asking for the whole chain on paper first, so the second volume is
        designed ahead of the writing front and its chain has to continue from volume one's *designed*
        close rather than from prose that does not exist yet.
        """
        raw = tier_contract('t2', 4, 2)
        raw['chapter_outline'] = {'scope': 'all', 'words': 150, 'tolerance': 60}
        repo = SQLiteRepository.initialize(self.project, seeded_book(raw))
        app = Application(repo)
        try:
            owner = app.run(finish=True, source='工程夹具授权预铺两卷章纲。')['owner']
            handoff, stages = drive_ordered(app, owner)
            self.assertEqual(handoff['action'], 'ready_to_complete')
            self.assertEqual(stages[:3], ['volume_outline', 'chapter_outline', 'chapter_outline'])
            self.assertEqual(stages.count('chapter_outline'), 2)
            self.assertEqual(stages.count('write'), 4)
            self.assertFalse(set(stages) & DELETED_STAGES)
            book = repo.load()
            self.assertEqual(sorted(book['chapter_outlines']), ['v1', 'v2'])
            # The ahead-of-front volume's opening chapter continues from the designed close.
            self.assertEqual(book['chapter_outlines']['v2'][0]['chapter'], 3)
            self.assertEqual(book['state']['hooks']['hook-v1-carry']['status'], 'paid')
            self.assertTrue(app.complete(owner)['completed'])
        finally:
            repo.close()

    def test_the_foreshadowing_chain_adds_no_dispatch(self):
        """Promises are declared and executed inside the two outline steps, never as new work.

        v2.1 adds the hook ledger, and the one property that must not move is the dispatch count: a
        promise is a row on the volume outline and an action on a chapter outline, so the sequence
        is still volume_outline → chapter_outline → write...
        """
        repo = SQLiteRepository.initialize(self.project, seeded_book(contract(chapters=2, volumes=1)))
        app = Application(repo)
        try:
            owner = app.run(finish=True, source='工程夹具授权按伏笔账写完。')['owner']
            stages = []
            for _ in range(20):
                handoff = app.advance(owner=owner)
                if handoff['action'] == 'await_author':
                    app.approve(handoff['prose_hash'], '工程夹具认可当前版本。', owner)
                    continue
                if handoff['action'] != 'task_ready':
                    break
                stages.append(handoff['task']['stage'])
                app.submit(response(app))
            self.assertEqual(stages, ['volume_outline', 'chapter_outline', 'write', 'write'])
            self.assertTrue(repo.load()['volumes_outline']['v1']['hooks'])
        finally:
            repo.close()


if __name__ == '__main__':
    unittest.main()
