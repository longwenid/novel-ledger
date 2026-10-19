"""Behavioral regressions for factual drift settlement and computable volume terminals."""
import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from novel_ledger import drift, facts, spatial
from novel_ledger.contracts import Error
from novel_ledger.result_templates import drift_items
from support import chapter_rows, contract, seeded_book, volume_rows


CURRENT = {'desire': '查清退件来源。', 'stance': '先核对再行动。',
           'relationship_focus': '与主管的责任边界。'}
QUOTE = '次日，沈桐核对了记录，在后院说明自己的选择与代价。'


def empty_row():
    return {'chapter': 1, 'plot': {'nodes': [], 'threads': []}, 'hooks': [],
            'resources': [], 'places': [], 'knowledge': [], 'characters': [],
            'clock': {'advance_days': 0}}


def receipt(row, unplanned=(), skip=False):
    items = []
    for item in drift_items(row):
        kind = item['kind']
        items.append({**item, 'actual': None if skip and kind != 'clock' else {'advance_days': 0},
                      'status': 'skipped' if skip and kind != 'clock' else 'kept',
                      'reason': '本章没有发生这项变化。' if skip else '正文发生了额外变化。',
                      'evidence': {'chapter': 1, 'quote': QUOTE}})
    return {'items': items, 'unplanned': list(unplanned),
            'verdict': 'deviated' if skip or unplanned else 'clean'}


def extra(kind, key, before, after, **details):
    return {'kind': kind, 'key': key, 'actual': {'from': before, 'to': after},
            'reason': '正文核对后产生了这项额外变化。',
            'evidence': {'chapter': 1, 'quote': QUOTE}, **details}


class UnplannedSettlementTests(unittest.TestCase):
    def setUp(self):
        raw = contract(4)
        raw['narrative_tracking'] = True
        self.book = seeded_book(raw)
        self.state = self.book['state']

    def reconcile(self, entries):
        row = empty_row()
        return drift.reconcile(receipt(row, entries), row, self.state, self.book['world'])

    def test_all_supported_unplanned_values_reach_the_canonical_projection(self):
        resource = '["shen","车费","元"]'
        rows = [extra('resources', resource, 4, 7), extra('resources', resource, 7, 8),
                extra('knowledge', 'shen:secret', None, 'confirmed'),
                extra('places', 'shen', 'office', 'yard'),
                extra('characters', 'shen', None, CURRENT,
                      choice='先核对后签字。', cost='多等了一夜。')]
        settled = self.reconcile(rows)
        self.assertEqual(settled['findings'], [])
        self.assertEqual(len(settled['deviations']), len(rows))
        state, events = facts.settle(self.state, settled['events'], QUOTE, 1)
        self.assertEqual(len(events), len(rows))
        self.assertEqual(state['resources'][resource], '8')
        self.assertEqual(state['knowledge']['shen:secret']['stance'], 'knows')
        self.assertEqual(state['placements']['shen'], 'yard')
        self.assertEqual(state['character_current']['shen']['value'], CURRENT)

    def test_a_new_fully_qualified_resource_coordinate_can_be_settled(self):
        key = '["shen","奖励","元"]'
        settled = self.reconcile([extra('resources', key, 0, 2)])
        self.assertEqual(settled['findings'], [])
        state, _ = facts.settle(self.state, settled['events'], QUOTE, 1)
        self.assertEqual(state['resources'][key], '2')

    def test_unplanned_knowledge_carries_the_prior_claim_into_fact_settlement(self):
        """Both shapes of an unplanned knowledge step: an extra delta chain and a planned row whose
        reconciled `actual` supplies the claim — each keeps the prior claim as `before` when settling."""
        settled = self.reconcile([
            extra('knowledge', 'shen:secret', None, 'hinted', claim='先发现封条有异。'),
            extra('knowledge', 'shen:secret', 'suspected', 'confirmed', claim='核对后确认来源。')])
        self.assertEqual(settled['findings'], [])
        self.assertEqual(settled['events'][1]['before'], '先发现封条有异。')
        state, events = facts.settle(self.state, settled['events'], QUOTE, 1)
        self.assertEqual(len(events), 2)
        self.assertEqual(state['knowledge']['shen:secret']['claim'], '核对后确认来源。')
        self.assertEqual(state['knowledge']['shen:secret']['stance'], 'knows')

        row = empty_row()
        row['knowledge'] = [{'who': 'shen', 'topic': 'secret', 'from': None,
                             'to': 'hinted', 'reason': '先发现一处疑点。'}]
        check = receipt(row, [extra('knowledge', 'shen:secret', 'suspected', 'confirmed',
                                   claim='进一步核对后确认来源。')])
        item = next(item for item in check['items'] if item['kind'] == 'knowledge')
        item.update(actual={'from': None, 'to': 'hinted'}, claim='封条上的字迹可疑。')
        settled = drift.reconcile(check, row, self.state, self.book['world'])
        self.assertEqual(settled['findings'], [])
        self.assertEqual(settled['events'][1]['before'], '封条上的字迹可疑。')
        state, events = facts.settle(self.state, settled['events'], QUOTE, 1)
        self.assertEqual(len(events), 2)
        self.assertEqual(state['knowledge']['shen:secret']['claim'], '进一步核对后确认来源。')
        self.assertEqual(state['knowledge']['shen:secret']['stance'], 'knows')

    def test_continuous_carrier_travel_keeps_custody_locations_in_step(self):
        raw = contract(4)
        raw.update(narrative_tracking=True, editorial_features=True)
        self.book = seeded_book(raw)
        self.state = self.book['state']
        facts.entity(self.state, {'id': 'box', 'name': '退件箱', 'kind': 'item'})
        self.state['custody']['box'] = 'shen'
        self.state['links']['path'] = {'kind': 'path', 'a': 'office', 'b': 'yard'}
        row = empty_row()
        row['places'] = [{'entity': 'shen', 'from': 'office', 'to': 'yard',
                          'reason': '携箱前往后院。', 'links': ['path']}]
        check = receipt(row, [extra('places', 'shen', 'yard', 'office', links=['path']),
                              extra('places', 'shen', 'office', 'yard', links=['path'])])
        item = next(item for item in check['items'] if item['kind'] == 'places')
        item['actual'] = {'from': 'office', 'to': 'yard'}
        settled = drift.reconcile(check, row, self.state, self.book['world'])
        self.assertEqual(settled['findings'], [])
        self.assertEqual([event['from'] for event in settled['events']], ['office', 'yard', 'office'])
        state, events = facts.settle(self.state, settled['events'], QUOTE, 1)
        self.assertEqual(len(events), 3)
        self.assertEqual(spatial.location(state, 'shen'), 'yard')
        self.assertEqual(spatial.location(state, 'box'), 'yard')

    def test_malformed_unplanned_deltas_are_rejected_with_their_own_criterion(self):
        """Malformed notes, missing values, unsupported kinds, negative resources, unknown places and
        missing evidence are all refused — no delta settles and no state event is emitted."""
        cases = [{'kind': 'knowledge', 'key': 'shen:secret', 'change': '知晓秘密。', 'reason': '发生了变化。'},
                 extra('knowledge', 'shen:secret', None, None),
                 extra('knowledge', 'shen:secret', None, {'status': 'confirmed'}),
                 extra('knowledge', 'shen:secret', {'status': 'confirmed'}, 'hinted'),
                 extra('places', 'shen', 'office', {'place': 'yard'}),
                 extra('clock', 'main', 0, 1), extra('node', 'n-new', None, 'resolved'),
                 extra(['knowledge'], 'shen:secret', None, 'confirmed'),
                 extra('unknown', 'x', None, 'confirmed')]
        for entry in cases:
            with self.subTest(entry=entry):
                settled = self.reconcile([entry])
                self.assertIn('drift_unplanned', {f['criterion'] for f in settled['findings']})
                self.assertEqual(settled['events'], [])
        for entry, criterion in ((extra('resources', '["shen","车费","元"]', 4, -1), 'drift_resource'),
                                 (extra('places', 'shen', 'office', 'missing-place'), 'drift_place')):
            with self.subTest(criterion=criterion):
                self.assertIn(criterion, {f['criterion'] for f in self.reconcile([entry])['findings']})
        missing = extra('knowledge', 'shen:secret', None, 'confirmed')
        missing.pop('evidence')
        self.assertIn('drift_evidence', {f['criterion'] for f in self.reconcile([missing])['findings']})

    def test_the_second_unplanned_delta_must_read_the_first_delta_state(self):
        key = '["shen","车费","元"]'
        settled = self.reconcile([extra('resources', key, 4, 7), extra('resources', key, 4, 8)])
        self.assertIn('drift_before', {f['criterion'] for f in settled['findings']})

    def test_unplanned_evidence_is_checked_by_the_existing_fact_reducer(self):
        entry = extra('knowledge', 'shen:secret', None, 'confirmed')
        entry['evidence']['quote'] = '正文不存在的引文。'
        settled = self.reconcile([entry])
        with self.assertRaises(Error) as caught:
            facts.settle(self.state, settled['events'], QUOTE, 1)
        self.assertEqual(caught.exception.code, 'evidence')

    def test_known_information_cannot_regress_but_can_be_retracted(self):
        self.state['knowledge']['shen:secret'] = {'claim': '已经确认。', 'stance': 'knows', 'source': '前章'}
        rejected = self.reconcile([extra('knowledge', 'shen:secret', 'confirmed', 'hinted')])
        self.assertIn('drift_knowledge', {f['criterion'] for f in rejected['findings']})
        allowed = self.reconcile([extra('knowledge', 'shen:secret', 'confirmed', 'retracted')])
        self.assertEqual(allowed['findings'], [])
        state, _ = facts.settle(self.state, allowed['events'], QUOTE, 1)
        self.assertEqual(state['knowledge']['shen:secret']['stance'], 'disproved')

    def test_a_planned_knowledge_item_cannot_use_deviated_to_bypass_monotonicity(self):
        self.state['knowledge']['shen:secret'] = {'claim': '已经确认。', 'stance': 'knows', 'source': '前章'}
        row = empty_row()
        row['knowledge'] = [{'who': 'shen', 'topic': 'secret', 'from': 'confirmed',
                             'to': 'confirmed', 'reason': '继续确认。'}]
        check = receipt(row)
        item = next(item for item in check['items'] if item['kind'] == 'knowledge')
        item.update(status='deviated', actual={'from': 'confirmed', 'to': 'hinted'})
        check['verdict'] = 'deviated'
        rejected = drift.reconcile(check, row, self.state, self.book['world'])
        self.assertIn('drift_knowledge', {f['criterion'] for f in rejected['findings']})
        item['actual']['to'] = 'retracted'
        allowed = drift.reconcile(check, row, self.state, self.book['world'])
        self.assertEqual(allowed['findings'], [])
        state, _ = facts.settle(self.state, allowed['events'], QUOTE, 1)
        self.assertEqual(state['knowledge']['shen:secret']['stance'], 'disproved')

    def test_skipped_deltas_record_the_deviation_without_any_state_event(self):
        variants = [('resources', [{'key': '["shen","车费","元"]', 'from': 4, 'to': 3, 'reason': '车费。'}]),
                    ('places', [{'entity': 'shen', 'from': 'office', 'to': 'yard', 'reason': '核对。'}]),
                    ('knowledge', [{'who': 'shen', 'topic': 'secret', 'from': None, 'to': 'hinted', 'reason': '发现。'}]),
                    ('characters', [{'entity': 'shen', 'from': None, 'to': CURRENT, 'choice': '核对。', 'cost': '等待。'}]),
                    ('hooks', [{'hook': 'h1', 'action': 'plant'}]),
                    ('node', [{'node': 'n1', 'after': 'resolved', 'outcome': '结论。'}])]
        for field, rows in variants:
            with self.subTest(kind=field):
                row = empty_row()
                if field == 'node':
                    row['plot']['nodes'] = rows
                else:
                    row[field] = rows
                settled = drift.reconcile(receipt(row, skip=True), row, self.state, self.book['world'])
                self.assertEqual(settled['findings'], [])
                self.assertEqual(settled['events'], [])
                self.assertEqual(len(settled['deviations']), 1)
                state, _ = facts.settle(self.state, settled['events'], QUOTE, 1)
                self.assertEqual(state, self.state)


class ComputableTerminalTests(unittest.TestCase):
    def setUp(self):
        raw = contract(4)
        raw['narrative_tracking'] = True
        self.book = seeded_book(raw)
        self.contract, self.world, self.state = self.book['contract'], self.book['world'], self.book['state']
        self.volume = self.contract['volumes'][0]
        self.raw_outline = volume_rows(self.book, ['v1'])[0]
        self.raw_outline['characters'] = [{'entity': 'shen', 'to': copy.deepcopy(CURRENT), 'reason': '卷末选择已落实。'}]
        self.outline = self.validate_volume(self.raw_outline)
        self.chapters = chapter_rows(self.book, self.volume, self.state)

    def validate_volume(self, outline):
        return drift.validate_volume_outline({'volumes': [outline]}, self.contract, self.world,
                                             {}, {}, ['v1'], self.state)['v1']

    def validate_chapters(self, rows=None, outline=None, state=None):
        return drift.validate_chapter_outline({'volume': 'v1', 'chapters': rows or self.chapters},
                                               self.contract['chapter_outline'], self.volume,
                                               outline or self.outline, self.world,
                                               self.state if state is None else state)

    def test_structured_character_terminal_must_equal_the_simulated_current_state(self):
        self.validate_chapters()
        broken = copy.deepcopy(self.outline)
        broken['characters'][0]['to']['stance'] = '卷末放弃调查。'
        with self.assertRaises(Error) as caught:
            self.validate_chapters(outline=broken)
        self.assertIn('drift_closure', {f['criterion'] for f in caught.exception.details['findings']})

    def test_full_volume_checks_absolute_clock_and_declared_elapsed_days(self):
        for field, value in [('to', 99), ('advance_days', 99)]:
            with self.subTest(field=field):
                broken = copy.deepcopy(self.outline)
                broken['clock'][field] = value
                with self.assertRaises(Error) as caught:
                    self.validate_chapters(outline=broken)
                self.assertIn('drift_closure', {f['criterion'] for f in caught.exception.details['findings']})

    def test_a_tail_replan_checks_the_absolute_terminal_without_recounting_the_prefix(self):
        prefix_state, _ = drift.simulate(self.chapters[:2], self.state, self.world,
                                         self.volume, self.outline)
        tail = self.chapters[2:]
        self.validate_chapters(tail, state=prefix_state)
        broken = copy.deepcopy(self.outline)
        broken['clock']['to'] = 99
        with self.assertRaises(Error):
            self.validate_chapters(tail, outline=broken, state=prefix_state)

    def test_new_outlines_require_style_shapes_and_computable_terminals(self):
        for mutate in (lambda r: r.pop('style'), lambda r: r['style'].update(trend=''),
                       lambda r: r['clock'].pop('to'), lambda r: r['characters'][0].update(to='只有文字')):
            broken = copy.deepcopy(self.raw_outline)
            mutate(broken)
            with self.assertRaises(Error):
                self.validate_volume(broken)
        for style in (None, {}, {'pov': '第三人称'}, {'pov': '第三人称', 'rhythm': '短句', 'dialogue_ratio': 2}):
            with self.subTest(style=style):
                broken = copy.deepcopy(self.chapters)
                broken[0]['style'] = style
                with self.assertRaises(Error) as caught:
                    self.validate_chapters(broken)
                self.assertIn('chapter_style', {f['criterion'] for f in caught.exception.details['findings']})


if __name__ == '__main__':
    unittest.main()
