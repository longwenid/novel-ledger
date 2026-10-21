"""Engineering fixtures for literary memory, movable scenes and revision-scoped memory.

v2 keeps the workbench (作品理解) but removes the reader that used to file it: the writer's own
`understanding` candidate now travels with the chapter receipt and lands atomically with it, and a
revision invalidates the interpretations whose source prose it rewrote. What is gone with the
reviewer — a frozen first read, a separate reading pass, an independent re-read of a revision — has
no case here: those capabilities were deleted, not renamed.
"""
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
from support import contract, drive, long_prose, plan_extras, prose_stub, response, seeded_book


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
        story_memory.bind(scene, {})
        moved = copy.deepcopy(scene)
        moved['chapter'] = 5
        story_memory.bind(moved, {})
        self.assertEqual(scene['scenes'], moved['scenes'])
        self.assertEqual(moved['scene_schema'], 'scene-identity/2')
        with self.assertRaises(Error):
            story_memory.bind(moved, {'1': scene})

    def test_opaque_ids_are_unique_across_the_book(self):
        first = self.plan(1, 'scene:旧码头')
        story_memory.bind(first, {})
        second = self.plan(2, 'scene:新办公室')
        second['scenes'][0]['depends_on'] = ['scene:旧码头']
        story_memory.bind(second, {'1': first})
        clash = self.plan(3, 'scene:新办公室')
        with self.assertRaises(Error):
            story_memory.bind(clash, {'1': first, '2': second})

    def test_complete_reading_associations_cannot_omit_scene_declarations(self):
        plan = self.plan(1, 'scene:warehouse')
        plan['reading_coverage'] = 'complete'
        with self.assertRaises(Error):
            story_memory.bind(copy.deepcopy(plan), {})
        plan['scenes'][0]['reading_refs'] = [{'kind': 'relationship', 'key': 'shen>colleague'}]
        story_memory.bind(plan, {})
        self.assertIn(('relationship', 'shen>colleague'), story_memory.reading_refs(plan))


class WorkbenchTests(unittest.TestCase):
    # Cleanup goes through addCleanup, not tearDown: unittest runs tearDown before the cleanups a
    # test registers, so a secondary repository closed by addCleanup would still be open when a
    # tearDown-owned temp cleanup ran — deletable on POSIX, locked on Windows.
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / 'book'
        self.repo = SQLiteRepository.initialize(self.project, seeded_book(contract(6)))
        self.addCleanup(self.repo.close)
        self.app = Application(self.repo)
        self.owner = self.app.run(through=3, source='工程夹具：三章。')['owner']

    def scenes_receipt(self, dependencies=None):
        """A chapter-outline receipt whose rows declare the optional scene blocks."""
        result = response(self.app)
        dependencies = dependencies or {}
        for row in result['data']['chapters']:
            scene = plan_extras({'chapter': row['chapter']})['scenes'][0]
            scene['id'] = 'opaque-scene-%d' % row['chapter']
            scene['present'] = ['shen']
            scene['depends_on'] = list(dependencies.get(row['chapter'], []))
            row['scenes'] = [scene]
        return result

    def test_writer_memory_lands_atomically_with_the_chapter_without_changing_canon(self):
        drive(self.app, self.owner, until='write')
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
        # The next dispatch receives the actual original passage, and the selected memory is frozen.
        drive(self.app, self.owner, until='write')
        task = self.repo.pending()
        memory = self.repo.read_document(task['input']['records']['creative_memory'])
        self.assertEqual(memory['interpretations']['fear']['evidence'][0]['quote'], '要求先核对退件人的名字再开箱。')
        self.assertIn('作品理解', bookpage.render(self.repo))

    def test_a_malformed_memory_candidate_is_refused_and_rolls_the_submission_back(self):
        drive(self.app, self.owner, until='write')
        candidate = response(self.app)
        candidate['data']['understanding'] = [{'id': 'fear', 'kind': 'character'}]
        with self.assertRaises(Error) as caught:
            self.app.submit(candidate)
        self.assertEqual(caught.exception.code, 'understanding')
        self.assertEqual(self.repo.headers('main'), [])
        self.assertIsNone(self.repo.load()['draft'])
        # A founded candidate whose quote is forged is refused the same way, atomically.
        first = response(self.app)
        first['data']['understanding'] = [interpretation(quote='要求先核对退件人的名字再开箱。')]
        self.app.submit(first)
        drive(self.app, self.owner, until='write')
        self.app.revise(1, '改写第一章。', self.owner, changes={'mode': 'expression'})
        self.app.advance(owner=self.owner)
        candidate = response(self.app)
        candidate['data']['understanding'] = [interpretation(quote='伪造的原文。')]
        root = self.repo.get('book')
        rows = self.repo.headers(self.repo.load()['branch'])
        with self.assertRaises(Error):
            self.app.submit(candidate)
        self.assertEqual(self.repo.get('book'), root)
        self.assertEqual(self.repo.headers(self.repo.load()['branch']), rows)
        self.assertEqual(self.repo.pending()['id'], candidate['task_id'])

    def test_context_resolves_opaque_scene_ids_from_accepted_versions(self):
        handoff = drive(self.app, self.owner, until='chapter_outline')
        self.assertEqual(handoff['task']['chapter'], 1)
        self.app.submit(self.scenes_receipt({2: ['opaque-scene-1']}))
        drive(self.app, self.owner)
        book = self.repo.load()
        # The scene identity survives into the materialized settlement row, dependency and all.
        self.assertEqual(book['plans']['2']['scenes'][0]['depends_on'], ['opaque-scene-1'])
        work = context.build(self.repo, book, Job('repair', 2))
        sources = self.repo.read_document(work['records']['scene_sources'])
        self.assertEqual(sources[0]['scenes'][0]['id'], 'opaque-scene-1')
        self.assertEqual(sources[0]['prose_hash'], self.repo.chapter('main', 1)['prose'])
        book['plans']['1']['scenes'][0]['id'] = 'not-in-accepted-prose'
        book['plans']['2']['scenes'][0]['depends_on'] = ['not-in-accepted-prose']
        with self.assertRaises(Error):
            context.build(self.repo, book, Job('repair', 2))

    def test_revision_memory_is_invalidated_and_restored_only_from_unchanged_sources(self):
        """A revision discards the memory built on the rewritten range; a discard restores it, and a
        rewritten chapter's memory stays gone while the untouched chapter's memory survives."""
        drive(self.app, self.owner, until='write')
        candidate = response(self.app)
        candidate['data']['understanding'] = [interpretation(quote='要求先核对退件人的名字再开箱。')]
        self.app.submit(candidate)
        drive(self.app, self.owner, until='write')
        memory = self.repo.load()['understanding']
        self.app.revise(1, '改写第一章。', self.owner, changes={'mode': 'expression'})
        self.assertEqual(self.repo.load()['understanding']['versions'], [])
        self.app.discard(self.owner)
        self.assertEqual(self.repo.load()['understanding'], memory)

        drive(self.app, self.owner, until='write')
        first = response(self.app)
        first['data']['understanding'] = [interpretation(quote='要求先核对退件人的名字再开箱。')]
        self.app.submit(first)
        drive(self.app, self.owner, until='write')
        second = response(self.app)
        second['data']['understanding'] = [interpretation(ident='later', chapter=2, quote='指给主管看封条上的签字。')]
        self.app.submit(second)
        drive(self.app, self.owner)
        self.app.revise(1, '只调整表达。', self.owner, changes={'mode': 'expression'})
        self.app.advance(owner=self.owner)
        changed = response(self.app)
        changed['data']['prose'] = changed['data']['prose'].replace('要求先核对退件人的名字再开箱。',
                                                                    '请主管先确认退件人的名字，然后开箱。')
        self.app.submit(changed)
        drive(self.app, self.owner)
        current = understanding.latest(self.repo.load()['understanding'])
        self.assertNotIn('fear', current)
        self.assertIn('later', current)
        self.assertTrue(self.app.audit()['ok'])

    def test_contract_revision_rewrites_without_replaying_parent_under_the_new_contract(self):
        drive(self.app, self.owner)
        # A seeded book has no opening to carry a selection hash; the world export reads one. This
        # test pins the contract-revision path, not the export's tolerance for imported projects.
        book = self.repo.load()
        book['world']['selection_hash'] = 'engineering-selection'
        self.repo.save(book)
        changed = contract(6)
        changed['reader_promise'] = '查明责任，也重新理解同事的沉默。'
        self.app.recontract(changed, '修改作品方向。', self.owner)
        # The new contract re-derives the design instead of replaying the parent's: the branch has
        # no chapters, and step three is dispatched again under the amended promise.
        handoff = self.app.advance(owner=self.owner)
        self.assertEqual(handoff['task']['stage'], 'volume_outline')
        book = self.repo.load()
        self.assertEqual(book['volumes_outline'], {})
        self.assertEqual(self.repo.headers(book['branch']), [])
        self.assertEqual(book['revision_run']['first'], 1)
        self.assertTrue(self.app.audit()['ok'])

    def test_zero_progress_recontracts_preserve_budget_and_an_actionable_author_decision(self):
        book = self.repo.load()
        book.update(draft={'chapter': 1, 'title': '第一章 落账', 'prose': '正文一句。', 'findings': [{'code': 'scene_identity'}]},
                    rework={'1': {'repairs': 2, 'redesigns': 1, 'initial_used': True}},
                    status='paused', pause_reason='额度用尽。')
        workflow.hold_for_draft_exhaustion(book)
        spent = dict(book['rework']['1'])
        self.repo.save(book)
        changed = contract(6)
        changed['reader_promise'] = '重新激活规划链。'
        self.app.recontract(changed, '零进度重开。', self.owner)
        handoff = self.app.advance(owner=self.owner)
        self.assertEqual(handoff['action'], 'paused')
        new = self.repo.load()
        self.assertEqual(new['rework']['1'], spent)
        self.assertEqual(new['draft']['prose'], '正文一句。')
        self.assertEqual(new['prior_candidate']['prose'], '正文一句。')
        self.assertEqual(new['author_block'], book['author_block'])
        self.assertEqual(new['status'], 'paused')
        # The demoted candidate files its findings once, not once per code path.
        self.assertEqual(new['carry_findings'].count({'code': 'scene_identity'}), 1)
        # Another amendment cannot turn the pause into a fresh writing allowance.
        self.app.recontract(changed, '同一零进度项目再次改约。', self.owner)
        self.app.advance(owner=self.owner)
        self.assertEqual(self.repo.load()['rework']['1'], spent)
        block = self.repo.load()['author_block']
        self.app.answer(block['id'], block['options'][0]['label'], '作者明确追加一轮返修。', self.owner)
        self.assertEqual(self.repo.load()['rework']['1']['repairs'], spent['repairs'] - 1)
        self.assertEqual(self.app.advance(owner=self.owner)['task']['stage'], 'volume_outline')

    def test_missing_budget_is_rejected_without_creating_fresh_allowances(self):
        book = self.repo.load()
        del book['rework']
        self.repo.save(book)
        before = self.repo.get('book')
        with self.assertRaises(Error) as caught:
            self.app.advance(owner=self.owner)
        self.assertEqual(caught.exception.code, 'book_state')
        self.assertEqual(self.repo.get('book'), before)

    def test_scene_binding_includes_other_volumes_and_retains_the_replan_prefix(self):
        repo = SQLiteRepository.initialize(Path(self.temp.name) / 'multi-volume', seeded_book(contract(6, 2)))
        self.addCleanup(repo.close)
        app = Application(repo)
        owner = app.run(through=5, source='跨卷场景工程验证。')['owner']

        def scenes():
            result = response(app)
            for row in result['data']['chapters']:
                scene = plan_extras({'chapter': row['chapter']})['scenes'][0]
                scene.update(id='scene:' + str(row['chapter']), present=['shen'],
                             depends_on=['scene:1'] if row['chapter'] == 4 else [])
                row['scenes'] = [scene]
            return result

        drive(app, owner, until='chapter_outline')
        app.submit(scenes())
        drive(app, owner, until='chapter_outline')
        valid = scenes()
        duplicate = copy.deepcopy(valid)
        duplicate['data']['chapters'][0]['scenes'][0].update(id='scene:1', depends_on=[])
        root = repo.get('book')
        with self.assertRaises(Error) as caught:
            app.check(duplicate)
        self.assertEqual(caught.exception.code, 'scene_identity')
        self.assertEqual(repo.get('book'), root)
        app.submit(valid)
        self.assertEqual(drive(app, owner)['action'], 'target_reached')
        app.revise(4, '保留前缀场景来源，调整本卷表达。', owner, through=5,
                   changes={'mode': 'reading', 'reading_changes': [{'kind': 'character', 'key': 'shen'}]})
        self.assertEqual(app.advance(owner=owner)['task']['stage'], 'chapter_outline')
        revised = scenes()
        future_collision = copy.deepcopy(revised)
        future_collision['data']['chapters'][0]['scenes'][0].update(id='scene:6', depends_on=[])
        with self.assertRaises(Error) as caught:
            app.check(future_collision)
        self.assertEqual(caught.exception.code, 'scene_identity')
        app.submit(revised)
        self.assertEqual(repo.load()['plans']['4']['scenes'][0]['depends_on'], ['scene:1'])
        self.assertEqual(app.advance(owner=owner)['task']['stage'], 'repair')
        sources = repo.read_document(repo.pending()['input']['records']['scene_sources'])
        self.assertEqual(sources[0]['prose_hash'], repo.chapter('main', 1)['prose'])

    def test_patch_and_reuse_memory_quote_the_composed_chapter_and_rollback_preflight(self):
        drive(self.app, self.owner, until='write')
        self.app.submit(response(self.app))
        drive(self.app, self.owner, until='write')
        self.app.revise(1, '仅调整表达。', self.owner, through=1, changes={'mode': 'expression'})
        self.app.advance(owner=self.owner)
        result = response(self.app)
        base = self.repo.load()['draft']['prose']
        quote = base[:14]
        original = '要求先核对退件人的名字再开箱。'
        replacement = '请主管先确认退件人的名字然后开箱。'
        patch = {'base_hash': digest(base), 'patches': [{'start': base.index(original),
                  'old': original, 'new': replacement}], 'repair_note': '调整原句，保留本章事实。'}
        root = self.repo.get('book')
        for mode in ('prose', 'patches', 'reuse_original'):
            candidate = copy.deepcopy(result)
            candidate['data']['understanding'] = [interpretation(quote=quote)]
            if mode != 'prose':
                candidate['data'].pop('prose')
                candidate['data'].update(patch if mode == 'patches' else {
                    'base_hash': digest(base), 'reuse_original': True, 'repair_note': '核对原文仍成立。'})
            self.assertTrue(self.app.check(candidate)['valid'])
            self.assertEqual(self.repo.get('book'), root)
            if mode == 'patches':
                accepted = candidate
        forged = copy.deepcopy(accepted)
        forged['data']['understanding'][0]['evidence'][0]['quote'] = original
        with self.assertRaises(Error):
            self.app.check(forged)
        self.assertEqual(self.repo.get('book'), root)
        self.app.submit(accepted)
        changed = base.replace(original, replacement)
        memory = understanding.latest(self.repo.load()['understanding'])['fear']
        self.assertEqual(memory['evidence'][0]['prose_hash'], digest(changed))


class ReadingImpactTests(unittest.TestCase):
    def test_reading_influence_follows_explicit_associations_and_scene_bridges(self):
        rows = []
        for n in range(1, 5):
            plan = {'chapter': n, 'participants': ['shen'] if n == 2 else [],
                    'dependency_coverage': 'complete', 'reading_coverage': 'complete',
                    'reading_schema': story_memory.READING_SCHEMA,
                    'scenes': [{'id': 'scene:' + str(n), 'reads': [], 'reading_refs': [], 'depends_on': []}]}
            story_memory.bind(plan, {})
            rows.append(dict(n=n, chain=str(n), plan=plan, events=[], plan_hash=str(n), events_hash=str(n)))
        rows[2]['plan']['scenes'][0]['depends_on'] = ['scene:2']
        impact = revision_impact.analyze(rows, 1, {'mode': 'reading',
                                                'reading_changes': [{'kind': 'character', 'key': 'shen'}]})
        self.assertEqual([r['action'] for r in impact['chapter_actions']], ['local', 'rewrite', 'rewrite', 'keep'])
        self.assertEqual(impact['rewrite_chapters'], [1, 2, 3])
        rows[1]['plan']['participants'] = []
        rows[2]['plan']['participants'] = ['shen']
        rows[2]['plan']['scenes'][0]['depends_on'] = []
        rows[3]['plan']['scenes'][0]['depends_on'] = ['scene:2']
        gap_impact = revision_impact.analyze(rows, 1, {'mode': 'reading',
                           'reading_changes': [{'kind': 'character', 'key': 'shen'}]})
        self.assertEqual(gap_impact['last'], 4)
        self.assertEqual(gap_impact['rewrite_chapters'], [1, 2, 3, 4])
        rows[3]['plan']['scenes'][0]['depends_on'] = []
        rows[3]['plan'].pop('reading_coverage')
        self.assertEqual(revision_impact.analyze(rows, 1, {'mode': 'reading',
                         'reading_changes': [{'kind': 'character', 'key': 'shen'}]})['chapter_actions'][-1]['action'], 'rewrite')

    def test_accepted_plans_require_current_protocols_without_mutating_the_source(self):
        plan = {'chapter': 1, 'scenes': []}
        story_memory.bind(plan, {})
        row = dict(n=1, chain='one', plan=plan, events=[], plan_hash='plan', events_hash='events')
        self.assertEqual(revision_impact.analyze([row], 1, {'mode': 'expression'})['last'], 1)
        for field, obsolete in (('scene_schema', 'scene-identity/1'),
                                ('reading_schema', 'reading-dependencies/0')):
            for value in (None, obsolete):
                with self.subTest(field=field, value=value):
                    broken = copy.deepcopy(row)
                    if value is None:
                        broken['plan'].pop(field)
                    else:
                        broken['plan'][field] = value
                    before = copy.deepcopy(broken)
                    with self.assertRaises(Error) as caught:
                        revision_impact.analyze([broken], 1, {'mode': 'expression'})
                    self.assertEqual(caught.exception.code, 'story_protocol')
                    self.assertEqual(broken, before)
            invalid = copy.deepcopy(plan)
            invalid[field] = obsolete
            with self.assertRaises(Error) as caught:
                story_memory.bind(invalid, {})
            self.assertEqual(caught.exception.code, 'story_protocol')


class GuidedWorkbenchTests(unittest.TestCase):
    """A thirteen-gate opening still files its memory with the chapter that produced it.

    The workbench is on for every new book, so the guided path and the memory path are one flow: the
    writer's own interpretation travels in the same receipt as the prose and lands atomically with
    the chapter it cites.
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / 'book'
        self.repo = SQLiteRepository.initialize(self.project, workflow.preparing_book(guided=True))
        self.app = Application(self.repo)

    def tearDown(self):
        self.repo.close()
        self.temp.cleanup()

    def test_a_thirteen_gate_book_writes_a_chapter_and_files_its_memory(self):
        from novel_ledger import creation
        handoff = drive(self.app)
        self.assertEqual(handoff['action'], 'outline_ready')
        book = self.repo.load()
        self.assertEqual(creation.opening_version(book['creation']), creation.OPENING_VERSION)
        self.assertEqual(len(book['creation']['selections']), 13)
        self.assertIn('understanding', book)                 # the workbench is on for a new book
        run = self.app.run(through=1, source='作者授权试写一章。')
        drive(self.app, run['owner'], until='write')
        candidate = response(self.app)
        number = self.repo.pending()['input']['chapter']
        quote = prose_stub(number)[:14]                      # the stub's opening, cited as evidence
        candidate['data']['prose'] = quote + long_prose(number, count=110)
        candidate['data']['understanding'] = [interpretation(quote=quote)]
        outcome = self.app.submit(candidate)
        self.assertEqual(outcome['committed_chapter'], 1)
        self.assertEqual(understanding.latest(self.repo.load()['understanding'])['fear']['status'],
                         'tentative')
        self.assertIn('作品理解', bookpage.render(self.repo))
        self.assertTrue(self.app.audit()['ok'])


if __name__ == '__main__':
    unittest.main()
