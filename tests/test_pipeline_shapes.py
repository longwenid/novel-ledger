"""The pipeline's own shape scales with the chosen size class.

A real three-chapter project paid the same pre-prose dispatch count as a serial because every
layer was a constant: 59 of 81 dispatches happened before the first word. The first declared
shape decision: on the smallest tier, a single volume's design is the book design, so the
volume_plan dispatch and its review never happen — the accepted book design is installed as the
volume design. Tiers that keep the separate layer still get it.
"""
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from novel_ledger import workflow
from novel_ledger.bootstrap import local_application as Application
from novel_ledger.contracts import PIPELINE_SHAPES, SCALE_TIERS
from novel_ledger.sqlite_store import SQLiteRepository
from support import check_dispatch, contract, response


def micro_contract(chapters=3, volumes=1):
    """A t0-band contract: the smallest tier's chapter band with a short chapter count."""
    base = contract(chapters=chapters, volumes=volumes)
    base.update(chapter_min=2000, chapter_max=3500, chapter_aim=2600,
                word_range=[2000 * chapters, 3500 * chapters])
    return base


def long_prose(n):
    """A chapter-length unique prose: numbers appear well inside every 25-character window."""
    parts = []
    for i in range(95):
        parts.append('第%d章%d段沈桐核对话%d，' % (n, i, n)
                     + '封条与责任栏对齐%d，' % (i + n)
                     + '先对名字再开箱%d。' % (i * 2 + n))
    parts[0] = '次日' + parts[0]          # the receipts' shared evidence anchor
    return ''.join(parts)


def record_stages(app, owner=None):
    """drive(), but remembering every dispatched stage on the way."""
    stages = []
    for _ in range(200):
        handoff = app.advance(owner=owner)
        if handoff['action'] == 'await_author':
            app.approve(handoff['prose_hash'], '工程夹具认可当前版本。', owner)
            continue
        if handoff['action'] != 'task_ready':
            return handoff, Counter(stages)
        stages.append(handoff['task']['stage'])
        check_dispatch(app.repo.pending()['input'])
        result = response(app)
        chapter = app.repo.pending()['input']['chapter']
        if result['data'].get('prose') is not None:
            result['data']['prose'] = long_prose(chapter)
        handoff = result['data'].get('handoff')
        if isinstance(handoff, dict):      # whole-prose quotes exceed the handoff's 240 limit
            handoff['evidence'] = [{'chapter': chapter, 'quote': long_prose(chapter)[:40]}]
        app.submit(result)
    raise AssertionError('工程流程没有在有限步骤内停止')


class PipelineShapeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / 'book'

    def tearDown(self):
        self.temp.cleanup()

    def drive_micro(self, chapters, volumes):
        repo = SQLiteRepository.initialize(self.project, workflow.new_book(
            micro_contract(chapters=chapters, volumes=volumes)))
        app = Application(repo)
        try:
            run = app.run(through=chapters, source='工程夹具授权写完全书。')
            handoff, stages = record_stages(app, run['owner'])
            book = repo.load()
            repo.close()
            return handoff, stages, book
        except BaseException:
            repo.close()
            raise

    def test_every_tier_declares_its_pipeline_shape(self):
        self.assertEqual(set(PIPELINE_SHAPES), {row['id'] for row in SCALE_TIERS})
        for shape in PIPELINE_SHAPES.values():
            self.assertEqual(set(shape), {'merge_volume_design', 'outline_batch'})

    def test_a_single_volume_micro_tier_reuses_the_book_design(self):
        handoff, stages, book = self.drive_micro(chapters=3, volumes=1)
        self.assertEqual(handoff['action'], 'target_reached')
        self.assertNotIn('volume_plan', stages)
        self.assertIn('book_plan', stages)
        # The alias is a copy, not a shared reference: the volume design carries the same nodes
        # while remaining a separate record the outline batches can grow on.
        self.assertEqual(book['designs']['volume:v1']['nodes'], book['designs']['book']['nodes'])
        self.assertIsNot(book['designs']['volume:v1'], book['designs']['book'])

    def test_a_multi_volume_project_still_designs_its_volume(self):
        handoff, stages, book = self.drive_micro(chapters=4, volumes=2)
        self.assertEqual(handoff['action'], 'target_reached')
        self.assertIn('volume_plan', stages)


if __name__ == '__main__':
    unittest.main()
