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


if __name__ == '__main__':
    unittest.main()
