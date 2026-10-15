"""Engineering fixtures for literary memory, movable scenes and graded revisions."""
import copy
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from novel_ledger import context, facts, revision_impact, story_memory, understanding, workflow, bookpage
from novel_ledger.bootstrap import local_application as Application
from novel_ledger.contracts import Error, Job, digest
from novel_ledger.sqlite_store import SQLiteRepository
from support import contract, drive, response


def interpretation(ident='fear', chapter=1, quote='他没有回答。', **extra):
    return dict(id=ident, kind='character', claim='他可能害怕承担责任。', subjects=['shen'], topics=['responsibility'],
                status='tentative', reason='沉默也可能是保护同事，保留另一种解释。',
                evidence=[{'chapter': chapter, 'quote': quote}], counterevidence=[], **extra)


class MemoryTests(unittest.TestCase):
    def assertCode(self, code, fn, *args, **kwargs):
        with self.assertRaises(Error) as caught:
            fn(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)

    def test_interpretations_keep_sources_counterevidence_and_alternative_versions(self):
        sources = {1: '他没有回答。随后他站到了同事身前。', 2: '他承认自己怕丢工作。'}
        first = interpretation()
        first['counterevidence'] = [{'chapter': 1, 'quote': '他站到了同事身前。'}]
        memory = understanding.update(None, [first], sources, facts.evidence, 'reader-1')
        newer = interpretation(chapter=2, quote=sources[2])
        newer.update(status='supported', claim='他明确担心丢掉工作。', reason='新章提供了另一层依据。')
        revised = understanding.update(memory, [newer], sources, facts.evidence, 'reader-2')
        self.assertEqual(memory['versions'][0]['status'], 'tentative')
        self.assertEqual(understanding.latest(revised)['fear']['version'], 2)
        self.assertEqual(memory['versions'][0]['counterevidence'][0]['prose_hash'], digest(sources[1]))
        # Rewriting chapter 2 invalidates its interpretation, exposing the still-supported old version.
        rebased = understanding.rebase(revised, {1: digest(sources[1]), 2: digest('另一个版本。')})
        self.assertEqual(understanding.latest(rebased)['fear']['version'], 1)

    def test_memory_selection_preserves_full_voice_samples_and_explicit_offstage_refs(self):
        prose = '他没有回答。' * 3000
        change = interpretation(quote=prose)
        change.update(kind='voice', valid_from=2, valid_through=4)
        memory = understanding.update(None, [change], {1: prose}, facts.evidence, 'reader')
        self.assertEqual(understanding.select(memory, ['shen'], [], 1), {})
        self.assertEqual(understanding.select(memory, ['other'], [], 3), {})
        selected = understanding.select(memory, [], [], 3, ['fear'])
        self.assertEqual(selected['fear']['evidence'][0]['quote'], prose)
        self.assertIn('fear', understanding.select(memory, [], ['responsibility'], 3))
        self.assertCode('understanding_reference', understanding.select, memory, [], [], 3, ['missing'])

    def test_malformed_or_unfounded_understanding_is_refused(self):
        sources = {1: '他没有回答。'}
        for value in (None, {}, [None], [dict(interpretation(), status='certain')],
                      [dict(interpretation(), subjects='shen')], [dict(interpretation(), valid_from=True)],
                      [dict(interpretation(), counterevidence={})], [dict(interpretation(), evidence=[])],
                      [interpretation(), interpretation()]):
            with self.subTest(value=value):
                self.assertCode('understanding', understanding.update, None, value, sources, facts.evidence, 'reader')
        with self.assertRaises(Error):
            understanding.update(None, [interpretation(quote='正文没有这句话。')], sources, facts.evidence, 'reader')
        self.assertCode('understanding', understanding.update, None, [interpretation(chapter=0)],
                        {0: '他没有回答。'}, facts.evidence, 'reader')


class SceneTests(unittest.TestCase):
    def plan(self, chapter, ident):
        return {'chapter': chapter, 'dependency_coverage': 'complete', 'scenes': [
            {'id': ident, 'label': '仓库', 'reads': [], 'depends_on': [], 'story_time': '三年前的冬夜'}]}

    def test_scene_can_move_chapters_without_changing_identity_or_story_time(self):
        scene = self.plan(1, 'warehouse-flashback')
        story_memory.bind(scene, {}, 2)
        moved = copy.deepcopy(scene)
        moved['chapter'] = 5
        story_memory.bind(moved, {}, 2)
        self.assertEqual(scene['scenes'], moved['scenes'])
        self.assertEqual(moved['scene_schema'], 'scene-identity/2')
        with self.assertRaises(Error):
            story_memory.bind(moved, {'1': scene}, 2)

    def test_opaque_ids_use_available_sources_and_keep_legacy_identity_rules(self):
        first = self.plan(1, 'scene:旧码头')
        story_memory.bind(first, {}, 2)
        second = self.plan(2, 'scene:新办公室')
        second['scenes'][0]['depends_on'] = ['scene:旧码头']
        story_memory.bind(second, {'1': first}, 2)
        with self.assertRaises(Error):
            story_memory.bind(copy.deepcopy(second), {'1': first}, 1)
        with self.assertRaises(Error):
            story_memory.bind(dict(second, chapter=1), {}, 2)

    def test_complete_reading_associations_cannot_omit_scene_declarations(self):
        plan = self.plan(1, 'scene:warehouse')
        plan['reading_coverage'] = 'complete'
        with self.assertRaises(Error):
            story_memory.bind(copy.deepcopy(plan), {}, 2)
        plan['scenes'][0]['reading_refs'] = [{'kind': 'relationship', 'key': 'shen>colleague'}]
        story_memory.bind(plan, {}, 2)
        self.assertIn(('relationship', 'shen>colleague'), story_memory.reading_refs(plan))


class WorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / 'book'
        self.repo = SQLiteRepository.initialize(self.project, workflow.new_book(contract(4)))
        self.app = Application(self.repo)
        self.owner = self.app.run(through=4, source='工程夹具：四章。')['owner']

    def tearDown(self):
        self.repo.close()
        self.temp.cleanup()

    def prepare_reading_revision(self):
        self.assertEqual(drive(self.app, self.owner)['action'], 'target_reached')
        changes = {'mode': 'reading', 'reading_changes': [{'kind': 'character', 'key': 'shen'}]}
        impact = self.app.revision_impact(2, changes)
        self.assertEqual([a['action'] for a in impact['chapter_actions']], ['local', 'review', 'review'])
        self.app.revise(2, '调整动机的表现。', self.owner, changes=changes)
        self.assertEqual(drive(self.app, self.owner, until='revision_review')['task']['chapter'], 3)

    def test_independent_review_updates_memory_atomically_without_changing_canon(self):
        drive(self.app, self.owner, until='chapter_review')
        candidate = response(self.app)
        candidate['data']['understanding'] = [interpretation(quote='要求先核对退件人的名字再开箱。')]
        root = self.repo.get('book')
        canon = self.repo.load()['state']
        preview = self.app.submit(candidate, preview=True)
        self.assertTrue(preview['checked'])
        self.assertEqual(self.repo.get('book'), root)
        self.app.submit(candidate)
        book = self.repo.load()
        self.assertEqual(book['state']['facts'], canon['facts'])
        self.assertEqual(understanding.latest(book['understanding'])['fear']['status'], 'tentative')
        self.assertNotIn('fear', book['state']['facts'])
        # Next writer receives the actual original passage, and the selected memory is frozen.
        drive(self.app, self.owner, until='write')
        task = self.repo.pending()
        memory = self.repo.read_document(task['input']['records']['creative_memory'])
        self.assertEqual(memory['interpretations']['fear']['evidence'][0]['quote'], '要求先核对退件人的名字再开箱。')
        self.assertIn('作品理解', bookpage.render(self.repo))

    def test_writer_cannot_turn_self_interpretation_into_memory(self):
        drive(self.app, self.owner, until='write')
        candidate = response(self.app)
        candidate['data']['understanding'] = []
        with self.assertRaises(Error) as caught:
            self.app.submit(candidate)
        self.assertEqual(caught.exception.code, 'understanding')

    def test_context_resolves_opaque_scene_ids_from_accepted_versions(self):
        drive(self.app, self.owner, until='plan')
        candidate = response(self.app)
        for plan in candidate['data']['plans']:
            n = plan['chapter']
            plan.update(dependency_coverage='complete', scenes=[{
                'id': 'opaque-scene-' + str(n), 'label': '仓库', 'reads': [],
                'depends_on': ['opaque-scene-1'] if n == 2 else []}])
        self.app.submit(candidate)
        drive(self.app, self.owner)
        book = self.repo.load()
        work = context.build(self.repo, book, Job('repair', 2))
        sources = self.repo.read_document(work['records']['scene_sources'])
        self.assertEqual(sources[0]['scenes'][0]['id'], 'opaque-scene-1')
        self.assertEqual(sources[0]['prose_hash'], self.repo.chapter('main', 1)['prose'])
        book['plans']['1']['scenes'][0]['id'] = 'not-in-accepted-prose'
        book['plans']['2']['scenes'][0]['depends_on'] = ['not-in-accepted-prose']
        with self.assertRaises(Error):
            context.build(self.repo, book, Job('repair', 2))

    def test_unchanged_suffix_restores_memory_but_changed_source_does_not(self):
        drive(self.app, self.owner, until='chapter_review')
        first = response(self.app)
        first['data']['understanding'] = [interpretation(quote='要求先核对退件人的名字再开箱。')]
        self.app.submit(first)
        drive(self.app, self.owner, until='chapter_review')
        second = response(self.app)
        second['data']['understanding'] = [interpretation(ident='later', chapter=2, quote='指给主管看封条上的签字。')]
        self.app.submit(second)
        drive(self.app, self.owner)
        self.app.revise(1, '只调整表达。', self.owner, changes={'mode': 'expression'})
        self.app.advance(owner=self.owner)
        changed = response(self.app)
        changed['data']['prose'] = changed['data']['prose'].replace('要求先核对退件人的名字再开箱。', '请主管先确认退件人的名字，然后开箱。')
        self.app.submit(changed)
        drive(self.app, self.owner)
        current = understanding.latest(self.repo.load()['understanding'])
        self.assertNotIn('fear', current)
        self.assertIn('later', current)
        self.assertTrue(self.app.audit()['ok'])

    def test_old_frozen_task_does_not_acquire_new_memory_capability(self):
        drive(self.app, self.owner, until='chapter_review')
        task = self.repo.pending()
        # A persisted pre-upgrade envelope has neither capability nor the new optional form.
        work = copy.deepcopy(task['input'])
        work['capabilities'].pop('understanding')
        candidate = response(self.app)
        candidate['data'].pop('understanding')
        before = self.repo.load()['understanding']
        outcome = workflow.apply(self.repo.load(), {**work, 'first_read': self.repo.task(task['id'])['first_read']},
                                 candidate['data'], candidate['session'], self.app._sources(work))
        self.assertEqual(outcome.book['understanding'], before)

    def test_existing_v3_book_can_explicitly_enable_at_a_safe_boundary(self):
        book = self.repo.load()
        book.pop('understanding')
        self.repo.save(book)
        original = self.repo.get('book')
        self.app.advance(owner=self.owner)
        with self.assertRaises(Error) as caught:
            self.app.enable_workbench('启用创作记忆。', self.owner)
        self.assertEqual(caught.exception.code, 'workbench_boundary')
        self.repo.cancel_pending('工程夹具：回到章节边界。')
        enabled = self.app.enable_workbench('启用创作记忆。', self.owner)
        self.assertTrue(enabled['enabled'])
        root = self.repo.get('book')
        for name in ('canon', 'settings'):
            self.assertEqual(original['parts'][name], root['parts'][name])
        self.assertEqual(self.repo.load()['plans'], book['plans'])
        self.assertTrue(self.app.enable_workbench('同一要求。', self.owner)['already_enabled'])
        self.assertEqual(root, self.repo.get('book'))

    def test_reading_only_revisions_seal_first_read_and_retain_exact_prose(self):
        self.prepare_reading_revision()
        task = self.repo.pending()
        root = self.repo.get('book')
        with self.assertRaises(Error) as caught:
            self.app.read(task['id'])
        self.assertEqual(caught.exception.code, 'first_read_sealed')
        candidate = response(self.app)
        self.app.submit(candidate, preview=True)
        self.assertEqual(root, self.repo.get('book'))
        self.app.submit(candidate)
        candidate_branch = self.repo.load()['branch']
        self.assertEqual(self.repo.chapter(candidate_branch, 3)['prose'], self.repo.chapter('main', 3)['prose'])
        self.assertEqual(drive(self.app, self.owner)['action'], 'revision_ready')
        self.assertTrue(self.app.audit()['ok'])
        book = self.repo.load()
        self.assertEqual(book['rework']['3'].get('repairs', 0), 0)
        reviewed = self.repo.read_document(self.repo.chapter(candidate_branch, 3)['review'])
        self.assertEqual(len(reviewed['revision_readings']), 1)
        self.app.promote(self.owner)
        self.assertIsNone(self.repo.load()['revision_run'])

    def test_reading_problem_routes_to_local_repair_and_full_independent_chapter_review(self):
        self.prepare_reading_revision()
        candidate = response(self.app)
        receipt = candidate['data']['reader']
        criterion = receipt['checks'][0]['id']
        receipt['checks'][0]['result'] = 'fix'
        receipt['verdict'] = 'fix'
        receipt['findings'] = [{'criterion': criterion, 'severity': 'quality', 'reason': '承接动机的表达需要修正。',
                                'target_chapter': 3, 'repair_scope': 'local', 'evidence': {'chapter': 3, 'quote': '次日'}}]
        root = self.repo.get('book')
        self.app.submit(candidate, preview=True)
        self.assertEqual(self.repo.get('book'), root)
        self.app.submit(candidate)
        handoff = self.app.advance(owner=self.owner)
        self.assertEqual(handoff['task']['stage'], 'repair')
        self.assertEqual(self.repo.load()['draft']['findings'][0]['repair_scope'], 'local')
        self.app.submit(response(self.app))
        self.assertEqual(self.app.advance(owner=self.owner)['task']['stage'], 'chapter_review')
        self.app.submit(response(self.app))
        self.assertEqual(drive(self.app, self.owner)['action'], 'revision_ready')
        self.assertEqual(self.repo.load()['rework']['3']['repairs'], 1)
        self.assertTrue(self.app.audit()['ok'])

    def test_revision_memory_is_invalidated_and_discard_restores_it(self):
        drive(self.app, self.owner, until='chapter_review')
        candidate = response(self.app)
        candidate['data']['understanding'] = [interpretation(quote='要求先核对退件人的名字再开箱。')]
        self.app.submit(candidate)
        drive(self.app, self.owner)
        memory = self.repo.load()['understanding']
        self.app.revise(1, '改写第一章。', self.owner, changes={'mode': 'expression'})
        self.assertEqual(self.repo.load()['understanding']['versions'], [])
        self.app.discard(self.owner)
        self.assertEqual(self.repo.load()['understanding'], memory)

    def test_invalidated_explicit_memory_reference_is_reported_without_blocking_repair(self):
        drive(self.app, self.owner, until='write')
        book = self.repo.load()
        book['plans']['1']['understanding_refs'] = ['old-motive']
        work = context.build(self.repo, book, Job('repair', 1))
        packet = self.repo.read_document(work['records']['creative_memory'])
        self.assertEqual(packet['unavailable_refs'], ['old-motive'])
        self.assertEqual(packet['interpretations'], {})

    def test_paused_reading_task_resumes_the_same_frozen_first_read(self):
        self.prepare_reading_revision()
        result = response(self.app)
        task = self.repo.pending()
        self.app.pause('稍后继续核验。', owner=self.owner)
        self.app.resume(self.owner)
        resumed = self.app.advance(owner=self.owner)['task']
        self.assertEqual(resumed['task_id'], task['id'])
        self.assertEqual(resumed['delivery_phase'], 'formal')
        self.assertEqual(self.repo.pending()['first_read'], task['first_read'])
        self.app.submit(result)
        self.assertEqual(drive(self.app, self.owner)['action'], 'revision_ready')

    def test_rejected_memory_rolls_back_a_reading_pass_and_suffix_carry(self):
        self.prepare_reading_revision()
        candidate = response(self.app)
        candidate['data']['understanding'] = [interpretation(chapter=3, quote='伪造的原文。')]
        root = self.repo.get('book')
        rows = self.repo.headers(self.repo.load()['branch'])
        with self.assertRaises(Error):
            self.app.submit(candidate)
        self.assertEqual(self.repo.get('book'), root)
        self.assertEqual(self.repo.headers(self.repo.load()['branch']), rows)
        self.assertEqual(self.repo.pending()['id'], candidate['task_id'])

    def test_contract_revision_rewrites_without_replaying_parent_under_the_new_contract(self):
        drive(self.app, self.owner)
        changed = contract(4)
        changed['reader_promise'] = '查明责任，也重新理解同事的沉默。'
        self.app.recontract(changed, '修改作品方向。', self.owner)
        self.assertEqual(drive(self.app, self.owner)['action'], 'revision_ready')
        self.app.promote(self.owner)
        self.assertTrue(self.app.audit()['ok'])


class ReadingImpactTests(unittest.TestCase):
    def test_reading_influence_follows_explicit_associations_and_scene_bridges(self):
        rows = []
        for n in range(1, 5):
            plan = {'chapter': n, 'participants': ['shen'] if n == 2 else [],
                    'dependency_coverage': 'complete', 'reading_coverage': 'complete',
                    'reading_schema': story_memory.READING_SCHEMA,
                    'scenes': [{'id': 'scene:' + str(n), 'reads': [], 'reading_refs': [], 'depends_on': []}]}
            rows.append(dict(n=n, chain=str(n), plan=plan, events=[], plan_hash=str(n), events_hash=str(n)))
        rows[2]['plan']['scenes'][0]['depends_on'] = ['scene:2']
        impact = revision_impact.analyze(rows, 1, {'mode': 'reading',
                                                'reading_changes': [{'kind': 'character', 'key': 'shen'}]})
        self.assertEqual([r['action'] for r in impact['chapter_actions']], ['local', 'review', 'review', 'keep'])
        self.assertEqual(impact['rewrite_chapters'], [1])
        rows[3]['plan'].pop('reading_coverage')
        self.assertEqual(revision_impact.analyze(rows, 1, {'mode': 'reading',
                         'reading_changes': [{'kind': 'character', 'key': 'shen'}]})['chapter_actions'][-1]['action'], 'review')


if __name__ == '__main__':
    unittest.main()
