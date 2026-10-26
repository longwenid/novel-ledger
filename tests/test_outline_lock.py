"""Fixed chapter contracts survive failed prose and cannot be bypassed at completion."""
import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'tests')]
from novel_ledger import drift, drift_reconcile, facts, workflow
from novel_ledger.bootstrap import open_local_runtime
from novel_ledger.contracts import Error, digest
from novel_ledger.result_templates import drift_items
from support import drive, response, tracked_contract


class FixedOutlineTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name) / 'book'
        self.runtime = open_local_runtime(self.project, initialize=True, contract=tracked_contract(2))
        self.addCleanup(self.runtime.close)
        self.app, self.repo = self.runtime.app, self.runtime.repo
        self.owner = self.app.run(finish=True, source='工程夹具授权按章纲完成两章。')['owner']
        drive(self.app, self.owner, until='write')

    def test_every_declared_item_stays_fixed_when_a_reason_is_supplied(self):
        baseline = response(self.app)
        before = tuple(self.repo.db.iterdump())
        for position, item in enumerate(baseline['data']['drift_check']['items']):
            for status in ('deviated', 'skipped'):
                with self.subTest(kind=item['kind'], status=status):
                    candidate = copy.deepcopy(baseline)
                    check = candidate['data']['drift_check']
                    check['items'][position].update(status=status, reason='写作时想改掉这项安排。')
                    if status == 'skipped':
                        check['items'][position]['actual'] = None
                    check['verdict'] = 'deviated'
                    result = self.app.check(candidate)
                    self.assertIsNone(result['committed_chapter'])
                    self.assertEqual(result['next_stage'], 'repair')
                    self.assertEqual(tuple(self.repo.db.iterdump()), before)

    def test_unplanned_changes_are_retained_only_in_the_failed_candidate(self):
        candidate = response(self.app)
        check = candidate['data']['drift_check']
        check['unplanned'] = [{'kind': 'knowledge', 'key': 'shen:extra',
                               'actual': {'from': None, 'to': 'confirmed'},
                               'reason': '正文额外揭示了秘密。',
                               'evidence': copy.deepcopy(check['items'][0]['evidence'])}]
        check['verdict'] = 'deviated'
        book = self.repo.load()
        self.assertIsNone(self.app.submit(candidate)['committed_chapter'])
        failed = self.repo.load()
        for field in ('plans', 'chapter_outlines', 'state', 'written_han', 'design_drift'):
            self.assertEqual(failed[field], book[field])
        self.assertEqual(failed['draft']['drift_check']['unplanned'], check['unplanned'])
        self.assertEqual(self.repo.headers('main'), [])

    def test_disclosures_require_explicit_matching_comparisons(self):
        row = {'chapter': 1, 'clock': {'advance_days': 0},
               'disclosures': [{'topic': 'secret', 'after': 'hinted', 'claim': '封条有疑点。'}]}
        quote = '沈桐发现封条上有一处疑点。'
        items = drift_items(row)
        for item in items:
            item.update(status='kept', reason='正文按章纲落实。',
                        actual=copy.deepcopy(item['planned']), evidence={'chapter': 1, 'quote': quote})
        check = {'items': items, 'unplanned': [], 'verdict': 'clean'}
        book = self.repo.load()
        valid = drift_reconcile.reconcile(check, row, book['state'], book.get('world'))
        self.assertEqual(valid['findings'], [])
        self.assertEqual(valid['events'][0]['op'], 'reader_knowledge')
        for variant, criterion in (('missing', 'drift_coverage'), ('changed', 'drift_kept'),
                                   ('skipped', 'outline_alignment')):
            with self.subTest(variant=variant):
                changed = copy.deepcopy(check)
                if variant == 'missing':
                    changed['items'].pop()
                elif variant == 'changed':
                    changed['items'][-1]['actual']['after'] = 'confirmed'
                else:
                    changed['items'][-1].update(status='skipped', actual=None)
                    changed['verdict'] = 'deviated'
                result = drift_reconcile.reconcile(changed, row, book['state'], book.get('world'))
                self.assertIn(criterion, {f['criterion'] for f in result['findings']})

    def test_a_declared_relation_row_is_as_fixed_as_every_other_item(self):
        """The fifth increment joined the frozen contract: a departure is diagnosed, never accepted."""
        row = {'chapter': 1, 'clock': {'advance_days': 0},
               'relations': [{'source': 'shen', 'target': 'guan', 'key': 'alliance',
                              'from': None, 'to': '戒备', 'reason': '第一次交锋。'}]}
        quote = '沈桐与管衡第一次交手，各自保留。'
        items = drift_items(row)
        for item in items:
            item.update(status='kept', reason='正文按章纲落实。',
                        actual=copy.deepcopy(item['planned']), evidence={'chapter': 1, 'quote': quote})
        check = {'items': items, 'unplanned': [], 'verdict': 'clean'}
        book = self.repo.load()
        facts.entity(book['state'], {'id': 'guan', 'name': '管衡', 'kind': 'person'})
        valid = drift_reconcile.reconcile(check, row, book['state'], book.get('world'))
        self.assertEqual(valid['findings'], [])
        self.assertEqual(valid['events'][0]['op'], 'relation')
        for status, criterion in (('deviated', 'outline_alignment'), ('skipped', 'outline_alignment')):
            with self.subTest(status=status):
                drifted = copy.deepcopy(check)
                drifted['items'][0].update(status=status, reason='写作时想改掉这项安排。',
                                           actual=None if status == 'skipped' else {'to': '同盟'})
                drifted['verdict'] = 'deviated'
                result = drift_reconcile.reconcile(drifted, row, book['state'], book.get('world'))
                self.assertIn(criterion, {f['criterion'] for f in result['findings']})

    def test_incompatible_entry_state_stops_without_replanning(self):
        self.app.submit(response(self.app))
        step = self.app.advance(owner=self.owner)
        self.app.approve(step['prose_hash'], '工程作者认可准确首章。', self.owner)
        book = self.repo.load()
        entry = next(e for e in book['plans']['2']['enter'] if e['kind'] == 'resources')
        entry['expected'] = 999
        before = copy.deepcopy(book)
        with self.assertRaises(Error) as caught:
            workflow.choose(book, self.repo.headers('main'))
        self.assertEqual(caught.exception.code, 'outline_state')
        self.assertEqual(book, before)

    def test_old_success_snapshot_with_a_declared_departure_cannot_be_delivered(self):
        drive(self.app, self.owner)
        self.app.complete(self.owner)
        book = self.repo.load()
        snapshot = self.repo.read_document(book['completion_snapshot'])
        first = snapshot['chapters'][0]
        review = self.repo.read_document(first['review'])
        review['drift_check']['items'][0].update(status='deviated', reason='旧版本允许带理由偏离章纲。')
        review['drift_check']['verdict'] = 'deviated'
        first['review'] = self.repo.document(review)
        previous = 'genesis'
        for row in snapshot['chapters']:
            row['chain'] = facts.chain(previous, row, digest(book['contract']))
            previous = row['chain']
        snapshot['audit'] = {'ok': True}
        book['completion_snapshot'] = self.repo.document(snapshot)
        self.repo.save(book)
        for operation in (self.app.audit, lambda: self.app.complete(self.owner), self.runtime.deliver):
            with self.subTest(operation=operation):
                with self.assertRaises(Error) as caught:
                    operation()
                self.assertEqual(caught.exception.code, 'outline_alignment')
        self.assertFalse((self.project / 'delivery.json').exists())


if __name__ == '__main__':
    unittest.main()
