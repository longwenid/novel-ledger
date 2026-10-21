"""What each v2 dispatch must read, declared once and checked in both directions.

The old chapter review was the largest consumer of material (16.6x the text under review), so v2's
material table was the first thing that had to land: a writer reads its own chapter outline and the
volume row it has to land on, a chapter-outline dispatch reads the volume row and the whole world,
and a volume-outline dispatch reads the world and the closed choices. No stage reads a receipt
another agent wrote, because no other agent writes one.
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from novel_ledger import context
from novel_ledger.bootstrap import local_application as Application
from novel_ledger.sqlite_store import SQLiteRepository
from support import (chapter_rows, check_dispatch, contract, drive, response, seeded_book,
                     volume_rows)

DELETED_STAGES = frozenset({
    'world_review', 'contract_review', 'design_review', 'outline_review', 'chapter_review',
    'book_plan', 'volume_plan', 'plan', 'profiles', 'scope_review', 'scope_synthesis',
    'revision_review', 'alignment_plan', 'alignment_review',
})


class MaterialDeclarationTests(unittest.TestCase):
    def test_the_material_table_declares_only_registered_live_stages(self):
        from novel_ledger import stages
        self.assertFalse(set(context.STAGE_MATERIAL) & DELETED_STAGES,
                         '已删除阶段仍在材料表里：' + ','.join(sorted(set(context.STAGE_MATERIAL) & DELETED_STAGES)))
        self.assertEqual(set(context.STAGE_MATERIAL) - set(stages.STAGES), set())

    def test_the_writer_reads_the_two_outline_rows_it_settles_against(self):
        material = set(context.STAGE_MATERIAL['write'])
        self.assertIn('chapter_outline', material)
        self.assertIn('volume_outline', material)
        self.assertIn('state', material)
        self.assertIn('contract', material)
        self.assertIn('design_drift', material)

    def test_the_volume_outline_reads_the_world_and_the_closed_choices(self):
        material = set(context.STAGE_MATERIAL['volume_outline'])
        self.assertIn('world_model', material)
        self.assertIn('contract', material)
        self.assertIn('opening_choices', material)

    def test_the_chapter_outline_reads_the_volume_row_and_the_world(self):
        material = set(context.STAGE_MATERIAL['chapter_outline'])
        self.assertIn('volume_outline', material)
        self.assertIn('world_model', material)
        self.assertIn('design_drift', material)


class DispatchMaterialTests(unittest.TestCase):
    """The frozen dispatch must satisfy the declaration, not the other way around."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = SQLiteRepository.initialize(Path(self.temp.name) / 'book',
                                                seeded_book(contract(chapters=2, volumes=1)))
        self.app = Application(self.repo)

    def tearDown(self):
        self.repo.close()
        self.temp.cleanup()

    def pending(self):
        return self.repo.pending()['input']

    def test_every_dispatch_on_the_happy_path_declares_what_it_requires(self):
        seen = 0
        for _ in range(20):
            handoff = self.app.advance()
            if handoff['action'] == 'await_author':
                self.app.approve(handoff['prose_hash'], '工程夹具认可当前版本。')
                continue
            if handoff['action'] != 'task_ready':
                break
            work = self.pending()
            check_dispatch(work)                       # raises if required ⊄ declared
            seen += 1
            self.app.submit(response(self.app))
        self.assertGreaterEqual(seen, 3)               # volume_outline, chapter_outline, writes

    def test_a_volume_outline_dispatch_carries_the_world_and_the_choices_record(self):
        self.app.advance()
        work = self.pending()
        self.assertEqual(work['stage'], 'volume_outline')
        self.assertIn('world_model', work['required'])
        self.assertIn('contract', work['required'])
        self.assertTrue(work['payload']['volume_outline']['volume_ids'])

    def test_a_chapter_outline_dispatch_carries_the_volume_row(self):
        drive(self.app, until='chapter_outline')
        work = self.pending()
        self.assertIn('volume_outline', work['required'])
        self.assertIn('world_model', work['required'])
        volume = self.repo.read_document(work['records']['volume_outline'])
        self.assertEqual(volume['id'], 'v1')
        self.assertEqual(work['payload']['volume'], 'v1')
        self.assertEqual(work['payload']['chapter_outline']['volume'], 'v1')

    def test_a_write_dispatch_hands_over_the_settlement_row_with_its_enter_exit_chain(self):
        drive(self.app, until='write')
        work = self.pending()
        self.assertIn('chapter_outline', work['required'])
        self.assertIn('volume_outline', work['required'])
        chapter = self.repo.read_document(work['records']['chapter_outline'])
        self.assertEqual(chapter['chapter'], 1)
        self.assertTrue(chapter['enter'])
        self.assertTrue(chapter['exit'])
        self.assertEqual(chapter['enter'], self.repo.load()['plans']['1']['enter'])

    def test_repair_reads_the_fixed_outline_and_failed_candidate_instead_of_replanning(self):
        owner = self.app.run(through=2, source='工程夹具授权两章。')['owner']
        drive(self.app, owner, until='write')
        work = self.pending()
        plan_hash = work['records']['chapter_outline']
        result = response(self.app)
        target = next(item for item in result['data']['drift_check']['items']
                      if item['kind'] == 'resources')
        target.update(status='deviated', actual={'from': 4, 'to': 5}, reason='正文里他多领了一趟车费。')
        result['data']['drift_check']['verdict'] = 'deviated'
        self.assertIsNone(self.app.submit(result)['committed_chapter'])
        self.app.advance(owner=owner)
        work = self.pending()
        self.assertEqual((work['stage'], work['chapter']), ('repair', 1))
        self.assertEqual(work['records']['chapter_outline'], plan_hash)
        self.assertIn('base_draft', work['required'])
        candidate = self.repo.read_document(work['records']['base_draft'])
        self.assertEqual(candidate['prose'], result['data']['prose'])

    def test_a_late_dispatch_does_not_require_what_it_can_read_on_demand(self):
        drive(self.app, until='write')
        work = self.pending()
        on_demand = set(work['records']) - set(work['required'])
        self.assertTrue(on_demand)                     # nothing forces every record into required
        self.assertTrue(set(work['required']) <= set(context.STAGE_MATERIAL['write']))


class OutlineMaterialTests(unittest.TestCase):
    """The two outline dispatches read only what their own decision needs."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.book = seeded_book(contract(chapters=4, volumes=2))
        self.contract = self.book['contract']

    def tearDown(self):
        self.temp.cleanup()

    def test_outline_rows_carry_their_own_identities_and_point_back_at_their_volume(self):
        rows = volume_rows(self.book, ['v1'])
        normalized = dict(rows[0])
        self.assertEqual(normalized['id'], 'v1')
        self.assertEqual([node['id'] for node in normalized['nodes']], ['n1', 'n2'])
        self.assertEqual(normalized['exit_state'], rows[0]['exit_state'])
        self.assertTrue(normalized['exit_state'])
        volume = self.contract['volumes'][0]
        chapters = chapter_rows(self.book, volume, self.book['state'])
        self.assertEqual([row['chapter'] for row in chapters], [1, 2])
        self.assertTrue(all(row['synopsis'] for row in chapters))
        self.assertTrue(all(row['world_refs'] for row in chapters))


if __name__ == '__main__':
    unittest.main()
