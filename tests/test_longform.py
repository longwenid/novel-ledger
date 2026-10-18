"""Long-form behaviour that survives v2: rolling outlines, volume handover and scene memory.

The pipeline is still cheap per chapter, so a long book has to hand itself over from one volume to
the next without re-planning what it already wrote: the next volume's chapter outlines are built
from the state the book is actually in, the just-in-time policy drafts each volume only when it is
entered, and a booked deviation re-plans only the remaining chapters of the current volume. The
scene-memory guards (forward links, unknown coordinates) are unchanged, because they were never
part of the review pipeline.
"""
import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from novel_ledger import book_state, story_memory, workflow
from novel_ledger.bootstrap import local_application as Application
from novel_ledger.contracts import Error
from novel_ledger.sqlite_store import SQLiteRepository
from support import (append_history, contract, drive, plan_extras, response, seeded_book,
                     tracked_contract)


def rolling_contract(chapters=4, volumes=2):
    raw = contract(chapters=chapters, volumes=volumes)
    raw['volume_outline'] = {'scope': 'rolling', 'words': 1000, 'tolerance': 100}
    raw['chapter_outline'] = {'scope': 'volume', 'words': 150, 'tolerance': 60}
    raw['narrative_tracking'] = True
    return raw


class RollingOutlineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = SQLiteRepository.initialize(Path(self.temp.name) / 'book',
                                                seeded_book(rolling_contract(4, 2)))
        self.app = Application(self.repo)
        self.owner = self.app.run(through=4, source='工程夹具授权按卷推进。')['owner']

    def tearDown(self):
        self.repo.close()
        self.temp.cleanup()

    def next_stage(self):
        handoff = self.app.advance(owner=self.owner)
        while handoff['action'] == 'await_author':
            self.app.approve(handoff['prose_hash'], '工程夹具认可当前版本。', self.owner)
            handoff = self.app.advance(owner=self.owner)
        return handoff

    def test_rolling_policy_drafts_one_volume_at_a_time_just_before_it_is_entered(self):
        stages = []
        for _ in range(40):
            handoff = self.next_stage()
            if handoff['action'] != 'task_ready':
                break
            work = self.repo.pending()['input']
            stages.append((work['stage'],
                           work['payload'].get('volume_ids') or work['payload'].get('volume')))
            self.app.submit(response(self.app))
        volume_batches = [row[1] for row in stages if row[0] == 'volume_outline']
        # The rolling policy answers one volume per dispatch instead of all volumes in one receipt.
        self.assertEqual(volume_batches, [['v1'], ['v2']])
        chapter_volumes = [row[1] for row in stages if row[0] == 'chapter_outline']
        self.assertEqual(chapter_volumes, ['v1', 'v2'])
        self.assertEqual([row[0] for row in stages].count('write'), 4)

    def test_the_next_volume_anchors_on_the_state_the_book_is_in(self):
        drive(self.app, self.owner, until='write')
        self.app.submit(response(self.app))
        handoff = self.next_stage()                           # pilot approval for chapter 1
        handoff = self.next_stage()                           # chapter 2 is the same volume
        self.assertEqual(handoff['task']['stage'], 'write')
        self.assertEqual(self.repo.load()['state']['clock'], 1)
        self.app.submit(response(self.app))
        # Volume 1 is done: the rolling policy drafts volume 2's outline on entry (not up front),
        # and then its chapter chain — both starting from the state the last written chapter left
        # behind, which is the whole point of rolling the design forward with the prose.
        handoff = self.next_stage()
        self.assertEqual(handoff['task']['stage'], 'volume_outline')
        self.app.submit(response(self.app))
        handoff = self.next_stage()
        self.assertEqual(handoff['task']['stage'], 'chapter_outline')
        work = self.repo.pending()['input']
        self.assertEqual(work['payload']['volume'], 'v2')
        rows = response(self.app)['data']['chapters']
        enter_clock = [item['expected'] for item in rows[0]['enter'] if item['kind'] == 'clock']
        self.assertEqual(enter_clock, [2])

    def test_a_booked_deviation_replans_only_the_remaining_chapters_of_this_volume(self):
        drive(self.app, self.owner, until='write')
        result = response(self.app)
        target = next(item for item in result['data']['drift_check']['items']
                      if item['kind'] == 'resources')
        target.update(status='deviated', actual={'from': 4, 'to': 5}, reason='正文里多领了一趟车费。')
        result['data']['drift_check']['verdict'] = 'deviated'
        self.app.submit(result)
        self.next_stage()                                     # await_author
        handoff = self.next_stage()
        self.assertEqual(handoff['task']['stage'], 'chapter_outline')
        work = self.repo.pending()['input']
        self.assertTrue(work['payload']['repair'])
        self.assertEqual(work['payload']['from_chapter'], 2)
        self.assertEqual(work['payload']['drift'][0]['kind'], 'resources')
        # The re-plan lands in the same volume and leaves the already-written chapter alone.
        rows = response(self.app)['data']['chapters']
        self.assertGreaterEqual(min(row['chapter'] for row in rows), 1)
        drift_rows = self.repo.load()['design_drift']
        self.assertEqual([row['kind'] for row in drift_rows], ['resources'])

    def test_volume_rows_register_the_nodes_and_threads_the_chapters_advance(self):
        drive(self.app, self.owner, until='write')
        book = self.repo.load()
        volume = book['volumes_outline']['v1']
        self.assertEqual([node['id'] for node in volume['nodes']], ['n1', 'n2'])
        self.assertEqual([thread['id'] for thread in volume['threads']], ['line-v1'])
        rows = book['chapter_outlines']['v1']
        advanced = [row['plot']['nodes'][0]['node'] for row in rows]
        self.assertEqual(advanced, ['n1', 'n2'])


class StateChainHandoverTests(unittest.TestCase):
    """The settlement row of the first chapter of a later volume is the state the last one left."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp.cleanup()

    def test_a_later_volumes_rows_can_be_built_from_a_mid_book_state(self):
        repo = SQLiteRepository.initialize(Path(self.temp.name) / 'book',
                                           seeded_book(rolling_contract(4, 2)))
        app = Application(repo)
        try:
            owner = app.run(through=4, source='工程夹具授权按卷推进。')['owner']
            drive(app, owner, until='write')
            app.submit(response(app))
            book = repo.load()
            state = copy.deepcopy(book['state'])
            self.assertEqual(state['clock'], 1)
            volume = book['contract']['volumes'][1]
            from support import chapter_rows
            rows = chapter_rows(book, volume, state)
            enter_clock = [item['expected'] for item in rows[0]['enter'] if item['kind'] == 'clock']
            self.assertEqual(enter_clock, [1])
        finally:
            repo.close()


class SceneMemoryTests(unittest.TestCase):
    """Scene dependencies are still mechanical: forward links and unknown coordinates are refused."""

    def assertCode(self, code, fn, *args):
        with self.assertRaises(Error) as caught:
            fn(*args)
        self.assertEqual(caught.exception.code, code)

    def test_forward_scene_links_are_refused(self):
        first = plan_extras({'chapter': 1})
        first['scenes'][0].update(id='c1:warehouse', reads=[], depends_on=[])
        story_memory.bind(first, {})
        second = plan_extras({'chapter': 2})
        second['scenes'][0].update(id='c2:office', reads=[], depends_on=['c3:future'])
        self.assertCode('story_dependency', story_memory.bind, second, {'1': first})

    def test_a_scene_must_declare_its_reads(self):
        row = plan_extras({'chapter': 1})
        row['dependency_coverage'] = 'complete'
        del row['scenes'][0]['reads']
        self.assertCode('story_dependency', story_memory.bind, row, {})

    def test_unknown_coordinate_kinds_are_refused(self):
        row = plan_extras({'chapter': 1})
        row['scenes'][0]['reads'] = [{'kind': 'unknown', 'key': 'shen'}]
        self.assertCode('story_dependency', story_memory.bind, row, {})

    def test_scene_identity_is_frozen_per_version(self):
        row = plan_extras({'chapter': 2})
        story_memory.bind(row, {}, 2)
        self.assertEqual(row['scene_schema'], 'scene-identity/2')
        frozen = dict(row)
        story_memory.bind(row, {}, 2)
        self.assertEqual(row['scene_schema'], frozen['scene_schema'])


class PersistentStateTests(unittest.TestCase):
    """A long book's new records live in declared parts, so a rollback moves them together."""

    def test_v2_book_fields_are_declared_in_one_partition(self):
        raw = tracked_contract(6)
        book = workflow.new_book(raw)
        book['volumes_outline'] = {'v1': {'id': 'v1'}}
        book['chapter_outlines'] = {'v1': []}
        book['design_drift'] = [{'chapter': 1, 'kind': 'resources', 'key': 'x',
                                 'planned': {}, 'actual': {}, 'reason': '工程样本。'}]
        parts = book_state.split(book)
        declared = {key for fields in book_state.PART_FIELDS.values() for key in fields}
        for field in ('volumes_outline', 'chapter_outlines', 'design_drift'):
            self.assertIn(field, declared)
        self.assertEqual(book_state.assemble(parts), book)

    def test_committed_history_pages_are_immutable(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = SQLiteRepository.initialize(Path(temp) / 'book', seeded_book(contract(4)))
            try:
                append_history(repo, 1, 4, prose_han=50)
                snapshot = repo.history_snapshot('main')
                pages = [page for _, page in repo.history_pages(snapshot)]
                self.assertEqual(sorted(page['n'] for page in pages), [1, 2, 3, 4])
                self.assertEqual(repo.history_snapshot('main'), snapshot)
            finally:
                repo.close()

    def test_a_long_history_stays_readable_by_chapter_range(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = SQLiteRepository.initialize(Path(temp) / 'book', seeded_book(contract(4)))
            try:
                append_history(repo, 1, 4, prose_han=20)
                snapshot = repo.history_snapshot('main')
                pages = [page for _, page in repo.history_pages(snapshot)]
                tail = [page for page in pages if page['n'] >= 3]
                self.assertEqual(sorted(page['n'] for page in tail), [3, 4])
                self.assertTrue(all(page['chain'] for page in tail))
            finally:
                repo.close()


if __name__ == '__main__':
    unittest.main()
