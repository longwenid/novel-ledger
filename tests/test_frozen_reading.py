"""Reading protocol freezes without reinterpreting metadata accepted before that protocol."""
import copy
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from novel_ledger import revision_impact, story_memory, workflow
from novel_ledger.bootstrap import local_application as Application
from novel_ledger.contracts import Error, digest
from novel_ledger.sqlite_store import SQLiteRepository
from support import contract, drive, response


def legacy_metadata(plan):
    """1.4 retained these additional fields without assigning them protocol semantics."""
    n = plan['chapter']
    plan.update(reading_refs=['theme:trust'], reading_coverage='complete',
                understanding_refs=None, scenes=[{
                    'id': 'c%d:s1' % n, 'label': '仓库', 'reads': [], 'depends_on': [],
                    'story_time': {'basis': 'flashback'}, 'reading_refs': 'free-form note'}],
                dependency_coverage='complete')
    return plan


class FrozenReadingTests(unittest.TestCase):
    def assertCode(self, code, fn, *args, **kwargs):
        with self.assertRaises(Error) as caught:
            fn(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)

    def current_plan(self, chapter, participants=()):
        return {'chapter': chapter, 'participants': list(participants),
                'reading_coverage': 'complete', 'dependency_coverage': 'complete',
                'scenes': [{'id': 'scene:%d' % chapter, 'label': '仓库', 'reads': [],
                            'depends_on': [], 'reading_refs': [], 'story_time': '三年前的冬夜'}]}

    def rows(self, plans):
        return [dict(n=p['chapter'], chain=str(p['chapter']), plan=p, events=[],
                     plan_hash=digest(p), events_hash=digest([])) for p in plans]

    def test_legacy_metadata_is_preserved_and_never_interpreted_as_reading_coordinates(self):
        plan = legacy_metadata({'chapter': 1, 'participants': ['shen'],
                                'disclosures': [{'topic': 'responsibility', 'after': 'hinted'}]})
        original = copy.deepcopy(plan)
        story_memory.bind(plan, {}, 1, 0)
        self.assertEqual(plan, original)
        self.assertFalse(story_memory.reading_enabled(plan))
        self.assertEqual(story_memory.reading_refs(plan), {
            ('character', 'shen'), ('voice', 'shen'), ('disclosure', 'responsibility')})
        # Ignoring new metadata does not relax the original scene or fact dependency guards.
        invalid = copy.deepcopy(plan)
        invalid['scenes'][0]['depends_on'] = ['c2:s1']
        self.assertCode('story_dependency', story_memory.bind, invalid, {}, 1, 0)
        invalid = copy.deepcopy(plan)
        invalid['scenes'][0]['reads'] = [{'kind': 'unknown', 'key': 'shen'}]
        self.assertCode('story_dependency', story_memory.bind, invalid, {}, 1, 0)

    def test_rechecking_an_unversioned_opaque_plan_does_not_hot_upgrade_it(self):
        plan = legacy_metadata({'chapter': 1})
        plan['scene_schema'] = 'scene-identity/2'
        plan['scenes'][0]['id'] = 'opaque-scene'
        original_hash = digest(plan)
        story_memory.bind(plan, {}, 2, 0)
        self.assertEqual(digest(plan), original_hash)
        self.assertNotIn('reading_schema', plan)

    def test_old_frozen_opaque_identity_task_does_not_acquire_reading_protocol(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = SQLiteRepository.initialize(Path(tmp) / 'book', workflow.new_book(contract(2)))
            try:
                app = Application(repo)
                drive(app, until='plan')
                task = repo.pending()
                work = copy.deepcopy(task['input'])
                self.assertEqual(work['capabilities']['scene_identity'], 'scene-identity/2')
                work['capabilities'].pop('reading_dependencies')
                candidate = response(app)
                for plan in candidate['data']['plans']:
                    legacy_metadata(plan)
                    plan['scenes'][0]['id'] = 'opaque:%d' % plan['chapter']
                outcome = workflow.apply(repo.load(), work, candidate['data'],
                                         candidate['session'], app._sources(work))
                for plan in outcome.book['plans'].values():
                    self.assertEqual(plan['scene_schema'], 'scene-identity/2')
                    self.assertNotIn('reading_schema', plan)
                    self.assertIsNone(plan['understanding_refs'])
            finally:
                repo.close()

    def test_new_plan_freezes_marker_and_validates_explicit_and_automatic_associations(self):
        plan = self.current_plan(1, ['shen'])
        plan['disclosures'] = [{'topic': 'responsibility', 'after': 'hinted'}]
        plan['reading_refs'] = [{'kind': 'theme', 'key': 'trust'}]
        plan['scenes'][0]['reading_refs'] = [{'kind': 'relationship', 'key': 'shen>colleague'}]
        story_memory.bind(plan, {}, 2)
        self.assertEqual(plan['reading_schema'], story_memory.READING_SCHEMA)
        self.assertEqual(story_memory.reading_refs(plan), {
            ('character', 'shen'), ('voice', 'shen'), ('disclosure', 'responsibility'),
            ('theme', 'trust'), ('relationship', 'shen>colleague')})
        frozen_hash = digest(plan)
        story_memory.bind(plan, {}, 2, 1)
        self.assertEqual(digest(plan), frozen_hash)

    def test_new_protocol_rejects_missing_or_malformed_reading_fields(self):
        cases = []
        plan = self.current_plan(1)
        plan['scenes'][0].pop('reading_refs')
        cases.append(('reading_dependency', plan))
        plan = self.current_plan(1)
        plan['reading_refs'] = ['theme:trust']
        cases.append(('reading_dependency', plan))
        plan = self.current_plan(1)
        plan['scenes'][0]['reading_refs'] = [{'kind': 'unknown', 'key': 'trust'}]
        cases.append(('reading_dependency', plan))
        plan = self.current_plan(1)
        plan['understanding_refs'] = [None]
        cases.append(('understanding_reference', plan))
        plan = self.current_plan(1)
        plan['scenes'][0]['story_time'] = {'basis': 'flashback'}
        cases.append(('scene_time', plan))
        plan = self.current_plan(1)
        plan['reading_schema'] = 'reading-dependencies/99'
        cases.append(('reading_dependency', plan))
        for code, plan in cases:
            with self.subTest(code=code, plan=plan):
                self.assertCode(code, story_memory.bind, plan, {}, 2, 1)

    def test_unversioned_claim_of_complete_coverage_still_requires_conservative_reading(self):
        plans = [legacy_metadata({'chapter': n, 'participants': []}) for n in range(1, 4)]
        before = copy.deepcopy(plans)
        impact = revision_impact.analyze(self.rows(plans), 1, {
            'mode': 'reading', 'reading_changes': [{'kind': 'theme', 'key': 'trust'}]})
        self.assertEqual([r['action'] for r in impact['chapter_actions']], ['local', 'review', 'review'])
        self.assertTrue(impact['reading_conservative'])
        self.assertEqual(plans, before)
        # Old expression/semantic requests do not opt into the new metadata by their names.
        expression = revision_impact.analyze(self.rows(plans), 1, {'mode': 'expression'})
        self.assertEqual([r['action'] for r in expression['chapter_actions']], ['local', 'keep', 'keep'])
        semantic = revision_impact.analyze(self.rows(plans), 1, {
            'mode': 'semantic', 'changes': [{'kind': 'knowledge', 'key': 'shen:source'}]})
        self.assertEqual([r['action'] for r in semantic['chapter_actions']], ['rewrite', 'keep', 'keep'])

    def test_versioned_reading_follows_automatic_associations_and_scene_bridges(self):
        plans = [self.current_plan(n, ['shen'] if n == 2 else []) for n in range(1, 5)]
        plans[2]['scenes'][0]['depends_on'] = ['scene:2']
        previous = {}
        for plan in plans:
            story_memory.bind(plan, previous, 2)
            previous[str(plan['chapter'])] = plan
        impact = revision_impact.analyze(self.rows(plans), 1, {
            'mode': 'reading', 'reading_changes': [{'kind': 'character', 'key': 'shen'}]})
        self.assertEqual([r['action'] for r in impact['chapter_actions']], ['local', 'review', 'review', 'keep'])
        self.assertFalse(impact['reading_conservative'])


class FrozenReadingProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        book = workflow.new_book(contract(4))
        book.pop('understanding')
        self.repo = SQLiteRepository.initialize(Path(self.temp.name) / 'book', book)
        self.app = Application(self.repo)
        self.owner = self.app.run(through=4, source='工程夹具：原版本四章授权。')['owner']
        drive(self.app, self.owner, until='plan')
        candidate = response(self.app)
        self.assertNotIn('reading_dependencies', self.repo.pending()['input']['capabilities'])
        for plan in candidate['data']['plans']:
            legacy_metadata(plan)
        self.app.submit(candidate)
        self.assertEqual(drive(self.app, self.owner)['action'], 'target_reached')

    def tearDown(self):
        self.repo.close()
        self.temp.cleanup()

    def test_legacy_chapters_audit_and_complete_without_reinterpreting_or_upgrading_metadata(self):
        hashes = [r['plan'] for r in self.repo.headers('main')]
        self.assertTrue(self.app.audit()['ok'])
        self.app.run(finish=True, owner=self.owner, source='工程夹具：核验旧记录完本。')
        self.assertEqual(drive(self.app, self.owner)['action'], 'ready_to_complete')
        self.assertTrue(self.app.complete(self.owner)['completed'])
        self.assertEqual([r['plan'] for r in self.repo.headers('main')], hashes)
        for row in self.repo.headers('main'):
            self.assertNotIn('reading_schema', self.repo.read_document(row['plan']))

    def test_legacy_carry_and_reading_review_survive_workbench_enable_without_hot_upgrade(self):
        original = self.repo.headers('main')
        self.app.enable_workbench('工程夹具：继续使用新工作台。', self.owner)
        self.app.revise(2, '工程夹具：仅修表达。', self.owner, changes={'mode': 'expression'})
        self.assertEqual(drive(self.app, self.owner)['action'], 'revision_ready')
        self.assertTrue(self.app.audit()['ok'])
        branch = self.repo.load()['branch']
        for old in original:
            self.assertEqual(self.repo.chapter(branch, old['n'])['plan'], old['plan'])
        self.app.promote(self.owner)
        changes = {'mode': 'reading', 'reading_changes': [{'kind': 'theme', 'key': 'trust'}]}
        before = [r['plan'] for r in self.repo.headers(branch)]
        impact = self.app.revision_impact(2, changes)
        self.assertEqual([r['action'] for r in impact['chapter_actions']], ['local', 'review', 'review'])
        self.app.revise(2, '工程夹具：独立核对旧稿阅读承接。', self.owner, changes=changes)
        reading = drive(self.app, self.owner, until='revision_review')
        self.assertEqual(reading['task']['chapter'], 3)
        self.assertEqual(drive(self.app, self.owner)['action'], 'revision_ready')
        self.assertTrue(self.app.audit()['ok'])
        self.assertEqual([r['plan'] for r in self.repo.headers(self.repo.load()['branch'])], before)
        self.app.promote(self.owner)


if __name__ == '__main__':
    unittest.main()
