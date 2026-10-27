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
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from novel_ledger import context, creation, workflow
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
            if handoff['action'] == 'await_volume_confirm':
                self.app.confirm_volume(handoff['volumes_hash'], '工程夹具认可当前卷纲。')
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

    def test_a_chapter_outline_dispatch_carries_the_bound_blueprint_record(self):
        """The chapter stage reads the same structural skeleton the volume stage designs by:
        unbound it sees no record at all — the engine does not pick a structure for the author —
        while a bound one carries the catalog entry with the author's source line and boundary."""
        drive(self.app, until='chapter_outline')
        self.assertNotIn('blueprint', self.pending()['records'])
        self.app.blueprint('多线交错', '工程夹具在章纲前绑定结构蓝图。')
        handoff = self.app.advance()
        self.assertEqual(handoff['action'], 'task_ready')
        work = self.pending()
        self.assertEqual(work['stage'], 'chapter_outline')
        self.assertIn('blueprint', work['required'])
        record = self.repo.read_document(work['records']['blueprint'])
        self.assertEqual(record['name'], '多线交错')
        self.assertEqual(record['source'], '工程夹具在章纲前绑定结构蓝图。')
        self.assertTrue(record['boundary'])

    def test_hold_intent_reaches_the_writer_without_creating_a_disclosure(self):
        drive(self.app, until='chapter_outline')
        receipt = response(self.app)
        rows = receipt['data']['chapters']
        rows[0]['beats'] = ['先看到核对时的反应。', '回顾交接约定。', '回到当下继续核对。']
        for row in rows:
            row['role'] = '共同推进一次退件调查'
            row['disclosures'] = []
        rows[0]['pacing'] = {'note': '本章只写核对时的压力，暂不提供关于幕后动机的新信息。'}
        self.app.submit(receipt)
        drive(self.app, until='write')
        work = self.pending()
        plan = self.repo.read_document(work['records']['chapter_outline'])
        boundary = self.repo.read_document(work['records']['disclosure_boundary'])
        self.assertEqual(plan['beats'], rows[0]['beats'])
        self.assertEqual(plan['role'], rows[0]['role'])
        self.assertEqual(plan['pacing'], rows[0]['pacing'])
        self.assertEqual(boundary['allowed_changes'], [])
        checks = response(self.app)['data']['drift_check']['items']
        self.assertFalse(any(item['kind'] == 'disclosure' for item in checks))

    def test_a_named_everyday_record_reaches_the_writer_and_an_unnamed_one_does_not(self):
        """The life-material channel: `world_records` carries exactly the records the plan names
        (plus the cast's own files and their links), so naming an everyday record in the chapter
        outline delivers it to the writer and leaving it unnamed keeps the domain out of the
        scene material. The two chapters of one book cover both sides."""
        book = seeded_book(contract(chapters=2, volumes=1))
        book['world']['everyday'].append(
            {'id': 'nightshift', 'practice': '夜班交接时按册核对退件，签字后才放行。',
             'constraint': '人手不够时交接只能口头顶替，出事由签字人担。',
             'story_use': '登记册、旧凭据与夜班规矩给日常章质感。', 'links': []})
        repo = SQLiteRepository.initialize(Path(self.temp.name) / 'everyday-book', book)
        app = Application(repo)
        try:
            owner = app.run(through=2, source='工程夹具授权两章。')['owner']
            drive(app, owner, until='chapter_outline')
            receipt = response(app)
            # Explicit refs on both chapters, so the sides do not depend on the fixture's section
            # order: chapter 1 names the everyday record, chapter 2 does not.
            receipt['data']['chapters'][0]['world_refs'] = ['geography:office', 'everyday:nightshift']
            receipt['data']['chapters'][1]['world_refs'] = ['geography:office', 'rules:r1']
            app.submit(receipt)
            drive(app, owner, until='write')
            named = repo.read_document(repo.pending()['input']['records']['world_records'])
            self.assertIn('everyday:nightshift', named)
            app.submit(response(app))
            drive(app, owner, until='write')
            unnamed = repo.read_document(repo.pending()['input']['records']['world_records'])
            self.assertNotIn('everyday:nightshift', unnamed)
        finally:
            repo.close()


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


class PlanningLineageTests(unittest.TestCase):
    def test_all_thirteen_choices_and_accepted_world_reach_the_frozen_volume_task(self):
        from test_opening import walk
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder) / 'book'
            book = workflow.preparing_book(guided=True)
            book['creation'] = walk(book['creation'])
            book['status'] = 'running'  # the final author choice also advances the lifecycle
            expected_choices = creation.selected(book['creation'])
            self.assertEqual(set(expected_choices), set(creation.gate_ids()))
            with closing(SQLiteRepository.initialize(project, book)) as repo:
                app = Application(repo)
                drive(app, until='world_model')
                world_input = repo.pending()['input']
                basis = repo.read_document(world_input['records']['opening_basis'])
                self.assertEqual(repo.read_document(world_input['records']['opening_choices']), expected_choices)
                candidate = response(app)
                # The generic office and this opening's first stage otherwise share a fixture name.
                office = next(r for r in candidate['data']['geography'] if r['id'] == 'office')
                office['name'] = '夜班办公室'
                app.submit(candidate)
                drive(app, until='volume_outline')
                accepted = repo.load()
                task = repo.pending()['input']
                check_dispatch(task)
                for name in ('contract', 'world_model', 'opening_choices', 'opening_basis'):
                    self.assertIn(name, task['required'])
                self.assertEqual(repo.read_document(task['records']['opening_basis']), basis)
                self.assertEqual(repo.read_document(task['records']['opening_choices']), expected_choices)
                self.assertEqual(repo.read_document(task['records']['world_model']), accepted['world'])
                self.assertEqual(repo.read_document(task['records']['contract']), accepted['contract'])
                self.assertEqual(accepted['world']['selection_hash'], basis['selection_hash'])
                expected_hashes = dict(task['records'])
            with closing(SQLiteRepository(project)) as reopened:
                task = reopened.pending()['input']
                self.assertEqual(task['records'], expected_hashes)
                self.assertEqual(reopened.read_document(task['records']['opening_choices']), expected_choices)

    def test_rolling_volume_reads_the_adjacent_approved_outcome_without_all_history(self):
        with tempfile.TemporaryDirectory() as folder:
            book = seeded_book(contract(chapters=6, volumes=3))
            book['contract']['volume_outline']['scope'] = 'rolling'
            book['structure_blueprint'] = {'name': '多线交错', 'source': '作者选定交织结构。'}
            prior = volume_rows(book, ['v1', 'v2'])
            book['volumes_outline'] = {v['id']: v for v in prior}
            with closing(SQLiteRepository.initialize(Path(folder) / 'book', book)) as repo:
                task = context.build(repo, book, workflow.next_volume_outline(book, book['contract']))
                check_dispatch(task)
                self.assertIn('previous_volume_outline', task['required'])
                self.assertEqual(repo.read_document(task['records']['previous_volume_outline']), prior[-1])
                self.assertIn('blueprint', task['required'])
                self.assertEqual(repo.read_document(task['records']['blueprint'])['source'], '作者选定交织结构。')
                self.assertEqual(task['payload']['structure_blueprint']['name'], '多线交错')
                # A task's source remains immutable even if a caller mutates its in-memory book.
                book['volumes_outline']['v2']['exit_state'] = '后来改过的局面'
                self.assertNotEqual(repo.read_document(task['records']['previous_volume_outline'])['exit_state'],
                                    book['volumes_outline']['v2']['exit_state'])
                self.assertEqual(task['payload']['volume_ids'], ['v3'])


if __name__ == '__main__':
    unittest.main()
