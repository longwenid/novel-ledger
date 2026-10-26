"""The fifth increment and the optional volume terminals, end to end.

`relations` makes the relation event `facts` has always owned a designed, chapter-declared step:
the volume outline may name a terminal, the chapter outlines walk the literal ladder
(chapter N's `to` is chapter N+1's `from`), the writer's self-comparison files one row per
declared step, and the settled state feeds the chapters that follow. `reader_knowledge` is the
declared-then-checked volume terminal: a volume that declares none is checked for none.

The merged-dispatch test is here on purpose (GAP-1 of the survey): t0/t1 share one simulate path
across volumes, and a cross-volume relation hand-off must behave there, not only on the
single-volume path.
"""
import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from novel_ledger import drift, drift_reconcile, drift_simulation, drift_validation, facts
from novel_ledger.bootstrap import local_application as Application
from novel_ledger.contracts import RESULT, Error, SCALE_TIERS
from novel_ledger.result_templates import drift_items
from novel_ledger.sqlite_store import SQLiteRepository
from support import chapter_rows, contract, long_prose, relation_book, response, seeded_book, volume_outline_fixture, volume_rows

COORDINATE = 'shen>guan:alliance'
QUOTE = '次日，沈桐核对了记录，在后院说明自己的选择与代价。'


class RelationDesignChainTests(unittest.TestCase):
    """Chapter relations: the design chain accepts, chains and refuses the fifth increment."""

    def setUp(self):
        self.book = relation_book(4)
        self.contract, self.world, self.state = self.book['contract'], self.book['world'], self.book['state']
        self.volume = self.contract['volumes'][0]
        self.outline = self.validate_volume(volume_rows(self.book, ['v1'], relations=True))

    def validate_volume(self, rows):
        return drift_validation.validate_volume_outline({'volumes': rows}, self.contract, self.world,
                                                        {}, {}, ['v1'], self.state)['v1']

    def validate_chapters(self, rows=None, outline=None, state=None):
        return drift_validation.validate_chapter_outline(
            {'volume': 'v1', 'chapters': rows or self.rows()}, self.contract['chapter_outline'],
            self.volume, outline or self.outline, self.world,
            self.state if state is None else state)

    def rows(self):
        return chapter_rows(self.book, self.volume, self.state, relations=True)

    def test_the_ladder_walks_into_state_relations_and_closes_on_the_terminal(self):
        rows = self.rows()
        normalized = self.validate_chapters(rows)
        simulated, findings = drift_simulation.simulate(rows, self.state, self.world,
                                                        self.volume, self.outline)
        self.assertEqual(findings, [])
        self.assertEqual([row['relations'][0]['to'] if row['relations'] else None for row in rows],
                         ['戒备', '试探', '同盟', None])
        self.assertEqual(simulated['relations'][COORDINATE], '同盟')
        # The installed row and the plan row both carry the array the writer is reconciled against.
        self.assertIn('relations', normalized[0])
        planned = drift.plan_rows(normalized)[0]
        self.assertEqual(planned['relations'][0]['key'], 'alliance')

    def test_a_broken_literal_continuity_is_refused_as_drift_chain(self):
        rows = self.rows()
        rows[2]['relations'][0]['from'] = '密友'      # chapter 3 must quote chapter 2's `to`
        with self.assertRaises(Error) as caught:
            self.validate_chapters(rows)
        self.assertIn('drift_chain', {f['criterion'] for f in caught.exception.details['findings']})

    def test_malformed_rows_are_refused_as_drift_shape(self):
        mutations = (lambda row: row.update(target='shen'),               # source == target
                     lambda row: row.update(key='alliance:extra'),        # ':' inside the key
                     lambda row: row.update(to=''),                       # no stable word
                     lambda row: row.pop('reason'))                       # no cause
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                rows = self.rows()
                mutate(rows[0]['relations'][0])
                with self.assertRaises(Error) as caught:
                    self.validate_chapters(rows)
                self.assertIn('drift_shape', {f['criterion'] for f in caught.exception.details['findings']})

    def test_an_unregistered_end_is_refused_by_the_design_chain(self):
        rows = self.rows()
        rows[0]['relations'][0]['target'] = 'stranger'
        with self.assertRaises(Error) as caught:
            self.validate_chapters(rows)
        self.assertIn('drift_relation', {f['criterion'] for f in caught.exception.details['findings']})

    def test_absent_null_and_empty_all_mean_no_relation_change(self):
        """migrationPlan's promise: an installed older row is never re-judged, and a new receipt
        without the array declares "no relation change" exactly like an empty one. Dropping the
        coordinate from the enter/exit handshake too is what "not declared at all" looks like —
        leaving those rows while removing the deltas would be a self-contradictory receipt."""
        plain = self.validate_volume(volume_rows(self.book, ['v1']))
        self.assertEqual(plain['relations'], [])                # absent normalizes to empty
        absent, nulled = self.rows(), self.rows()
        for row in absent:
            row.pop('relations')
            row['enter'] = [item for item in row['enter'] if item.get('kind') != 'relations']
            row['exit'] = [item for item in row['exit'] if item.get('kind') != 'relations']
        for row in nulled:
            row['relations'] = None
            row['enter'] = [item for item in row['enter'] if item.get('kind') != 'relations']
            row['exit'] = [item for item in row['exit'] if item.get('kind') != 'relations']
        for label, rows in (('absent', absent), ('null', nulled)):
            with self.subTest(shape=label):
                self.validate_chapters(rows, outline=plain)     # must not raise

    def test_the_prefilled_form_covers_exactly_what_the_engine_reconciles(self):
        row = drift.plan_rows(self.validate_chapters())[1]      # chapter 2: from 戒备 to 试探
        self.assertEqual([item['kind'] for item in drift_items(row) if item['kind'] == 'relations'],
                         ['relations'])
        item = next(item for item in drift_items(row) if item['kind'] == 'relations')
        self.assertEqual(item['key'], COORDINATE)
        self.assertEqual(item['planned'], {'from': '戒备', 'to': '试探'})
        extra = {'kind': 'relations', 'key': 'guan>shen:alliance', 'planned': {'from': None, 'to': '戒备'},
                 'actual': {'from': None, 'to': '戒备'}, 'status': 'kept', 'reason': '反向关系。',
                 'evidence': {'chapter': 2, 'quote': QUOTE}}
        items = []
        for item in drift_items(row):
            items.append({'kind': item['kind'], 'key': item['key'],
                          'planned': copy.deepcopy(item['planned']),
                          'actual': copy.deepcopy(item['planned']), 'status': 'kept',
                          'reason': '正文落实。', 'evidence': {'chapter': 2, 'quote': QUOTE}})
        items.append(extra)
        settled = drift_reconcile.reconcile({'items': items, 'unplanned': [], 'verdict': 'clean'},
                                            row, self.state, self.world)
        self.assertIn('drift_coverage', {f['criterion'] for f in settled['findings']})


class VolumeTerminalTests(unittest.TestCase):
    """The volume's optional terminals: declared-then-checked, refused when they do not close."""

    def setUp(self):
        self.book = relation_book(4)
        self.contract, self.world, self.state = self.book['contract'], self.book['world'], self.book['state']
        self.volume = self.contract['volumes'][0]

    def validate_volume(self, rows):
        return drift_validation.validate_volume_outline({'volumes': rows}, self.contract, self.world,
                                                        {}, {}, ['v1'], self.state)['v1']

    def validate_chapters(self, outline, rows=None):
        return drift_validation.validate_chapter_outline(
            {'volume': 'v1', 'chapters': rows or chapter_rows(self.book, self.volume, self.state,
                                                             relations=True)},
            self.contract['chapter_outline'], self.volume, outline, self.world, self.state)

    def test_an_undeclared_relation_terminal_is_never_checked(self):
        plain = self.validate_volume(volume_rows(self.book, ['v1']))
        self.assertEqual(plain['relations'], [])                # empty on record: nothing to close
        self.validate_chapters(plain)                           # must not raise

    def test_a_declared_relation_terminal_must_match_the_simulated_close(self):
        outline = self.validate_volume(volume_rows(self.book, ['v1'], relations=True))
        self.assertEqual(outline['relations'][0]['to'], '同盟')
        self.validate_chapters(outline)
        broken = copy.deepcopy(outline)
        broken['relations'][0]['to'] = '密友'
        with self.assertRaises(Error) as caught:
            self.validate_chapters(broken)
        self.assertIn('drift_closure', {f['criterion'] for f in caught.exception.details['findings']})

    def test_a_volume_relation_row_is_refused_when_its_ends_are_not_registered(self):
        rows = volume_rows(self.book, ['v1'], relations=True)
        rows[0]['relations'][0]['target'] = 'stranger'
        with self.assertRaises(Error) as caught:
            self.validate_volume(rows)
        self.assertIn('volume_reference',
                      {f['criterion'] for f in caught.exception.details['findings']})


class ReaderKnowledgeTerminalTests(unittest.TestCase):
    """C2: the reader-facing terminal is compared against the volume's declared disclosure ladder.

    The design chain never settles a disclosure (settlement needs prose evidence), so the terminal
    is checked against the last stage this volume's chapter outlines declare — or the settled
    projection where this volume declares no further step for the topic.
    """

    def setUp(self):
        self.book = relation_book(4)
        self.contract, self.world, self.state = self.book['contract'], self.book['world'], self.book['state']
        self.volume = self.contract['volumes'][0]
        self.outline = drift_validation.validate_volume_outline(
            {'volumes': volume_rows(self.book, ['v1'])}, self.contract, self.world,
            {}, {}, ['v1'], self.state)['v1']

    def chapters_with_disclosure(self):
        rows = chapter_rows(self.book, self.volume, self.state)
        rows[1]['disclosures'] = [{'topic': 'source', 'after': 'hinted', 'claim': '封条有疑点。'}]
        return rows

    def validate(self, outline, rows=None):
        return drift_validation.validate_chapter_outline(
            {'volume': 'v1', 'chapters': rows or self.chapters_with_disclosure()},
            self.contract['chapter_outline'], self.volume, outline, self.world, self.state)

    def test_an_undeclared_terminal_is_never_checked(self):
        self.assertEqual(self.outline['reader_knowledge'], [])  # empty on record: nothing to close
        self.validate(self.outline)                             # disclosures without a terminal pass

    def test_a_declared_terminal_must_match_the_last_declared_stage(self):
        self.outline['reader_knowledge'] = [{'topic': 'source', 'to': 'hinted',
                                             'reason': '卷末读者看到第一处疑点。'}]
        self.validate(self.outline)
        broken = copy.deepcopy(self.outline)
        broken['reader_knowledge'][0]['to'] = 'confirmed'
        with self.assertRaises(Error) as caught:
            self.validate(broken)
        self.assertIn('drift_closure', {f['criterion'] for f in caught.exception.details['findings']})

    def test_a_declared_terminal_without_any_declared_step_is_refused(self):
        self.outline['reader_knowledge'] = [{'topic': 'never-mentioned', 'to': 'hinted',
                                             'reason': '卷末从未披露过的题。'}]
        with self.assertRaises(Error) as caught:
            self.validate(self.outline, rows=chapter_rows(self.book, self.volume, self.state))
        self.assertIn('drift_closure', {f['criterion'] for f in caught.exception.details['findings']})

    def test_a_declared_terminal_reads_the_settled_projection_when_the_volume_stays_silent(self):
        self.state['reader_knowledge']['source'] = {'status': 'suspected', 'claim': '前卷已确认疑点。',
                                                    'chapter': 0, 'evidence': None}
        self.outline['reader_knowledge'] = [{'topic': 'source', 'to': 'suspected',
                                             'reason': '本卷不再推进该披露。'}]
        self.validate(self.outline, rows=chapter_rows(self.book, self.volume, self.state))


class MergedCrossVolumeRelationTests(unittest.TestCase):
    """C4: the t0/t1 merged dispatch carries a relation across volumes on the shared simulate path.

    One receipt answers both volumes' outlines and chapter outlines; the engine validates them in
    book order and carries the chain forward, so volume two's opening chapter must continue the
    relation from volume one's designed close — the same path where a cross-volume promise once
    failed. A receipt that breaks the hand-off is refused whole.
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / 'book'

    def merged_book(self):
        row = next(entry for entry in SCALE_TIERS if entry['id'] == 't1')
        raw = contract(chapters=4, volumes=2)
        raw.update(narrative_tracking=True,
                   chapter_min=row['chapter_min'], chapter_max=row['chapter_max'],
                   chapter_aim=row['chapter_aim'])
        raw['entities'] = raw['entities'] + [{'id': 'guan', 'name': '管衡', 'kind': 'person'}]
        book = seeded_book(raw)
        book['world']['characters'].append({'id': 'guan', 'name': '管衡', 'role': '主管',
                                            'desire': '考核达标。', 'limit': '不替人担责。',
                                            'knowledge_boundary': '只看考核数字。', 'links': ['rules:r1']})
        return book

    def merged_receipt(self, app, break_handoff=False):
        task = app.repo.pending()
        work = task['input']
        data = volume_outline_fixture(app, work, relations=True)
        if break_handoff:
            data['chapters']['v2'][0]['relations'][0]['from'] = '密友'
        return {'schema': RESULT, 'task_id': task['id'], 'input_hash': task['input_hash'],
                'session': 'merged-' + Path(self.temp.name).name, 'data': data}

    def test_the_relation_crosses_the_volume_boundary_and_settles_in_prose(self):
        repo = SQLiteRepository.initialize(self.project, self.merged_book())
        app = Application(repo)
        try:
            owner = app.run(finish=True, source='工程夹具授权 t1 两卷完本。')['owner']
            handoff = app.advance(owner=owner)
            self.assertEqual(handoff['action'], 'task_ready')
            self.assertEqual(handoff['task']['stage'], 'volume_outline')
            # One merged receipt: volume one's terminal is 试探 (two rungs), volume two's is 同盟.
            submitted = self.merged_receipt(app)
            terminals = {row['id']: row['relations'][0]['to'] for row in submitted['data']['volumes']}
            self.assertEqual(terminals, {'v1': '试探', 'v2': '同盟'})
            # The literal hand-off: volume two's first chapter reads volume one's close verbatim.
            self.assertEqual(submitted['data']['chapters']['v2'][0]['relations'][0]['from'], '试探')
            self.assertEqual(app.submit(submitted)['outcome'], 'design_accepted')
            book = repo.load()
            self.assertEqual(sorted(book['chapter_outlines']), ['v1', 'v2'])
            for chapter in range(1, 5):
                handoff = app.advance(owner=owner)
                if handoff['action'] == 'await_author':
                    app.approve(handoff['prose_hash'], '工程夹具认可当前版本。', owner)
                    handoff = app.advance(owner=owner)
                self.assertEqual(handoff['action'], 'task_ready')
                work = app.repo.pending()['input']
                result = response(app)
                prose = long_prose(chapter)
                result['data']['prose'] = prose
                for item in result['data']['drift_check']['items']:
                    item['evidence'] = {'chapter': chapter, 'quote': prose[:20]}
                self.assertTrue(app.submit(result)['accepted'])
            self.assertEqual(repo.load()['state']['relations'][COORDINATE], '同盟')
        finally:
            repo.close()

    def test_a_broken_cross_volume_hand_off_refuses_the_whole_receipt(self):
        repo = SQLiteRepository.initialize(self.project, self.merged_book())
        app = Application(repo)
        try:
            owner = app.run(finish=True, source='工程夹具授权 t1 两卷完本。')['owner']
            app.advance(owner=owner)
            with self.assertRaises(Error) as caught:
                app.submit(self.merged_receipt(app, break_handoff=True))
            self.assertEqual(caught.exception.code, 'design_drift')
            criteria = {finding['criterion'] for finding in caught.exception.details['findings']}
            self.assertIn('drift_chain', criteria)
        finally:
            repo.close()


if __name__ == '__main__':
    unittest.main()
