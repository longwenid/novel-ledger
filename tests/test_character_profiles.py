"""Character identity, first-mention evidence and frozen comparison material."""
import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'tests')]
from novel_ledger import entities, facts, world
from novel_ledger.bootstrap import local_application
from novel_ledger.contracts import Error
from novel_ledger.sqlite_store import SQLiteRepository
from support import seeded_book, tracked_contract, drive, response


def character(**changes):
    return dict({'id': 'visitor', 'kind': 'person', 'name': '赵陌', 'role': '药商',
                 'desire': '收回药款。', 'limit': '不赊账。', 'knowledge_boundary': '只知草药价格。'}, **changes)


def biography():
    return {'past': '曾因赊药亏空，因此如今坚持现钱。',
            'contradiction': '想守住规矩，也不忍见熟人断药。',
            'relationships': '欠旧友救命之恩，对方却正急需赊药。',
            'behavior': '先问欠款与期限，难以拒绝时改为自己垫付。'}


class CharacterProfileTests(unittest.TestCase):
    def app(self, definition=None):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        book = seeded_book(tracked_contract(chapters=2))
        if definition:
            book['world']['characters'].append({**definition, 'links': []})
        repo = SQLiteRepository.initialize(Path(folder.name) / 'book', book)
        self.addCleanup(repo.close)
        return local_application(repo)

    def outline(self, app, item):
        drive(app, until='chapter_outline')
        receipt = response(app)
        receipt['data']['chapters'][0]['new_entities'] = [copy.deepcopy(item)]
        return receipt

    def writer(self, app, item):
        app.submit(self.outline(app, item))
        app.advance()
        return response(app)

    def test_missing_character_fields_are_rejected_without_losing_the_task(self):
        app = self.app()
        receipt = self.outline(app, {'id': 'visitor', 'kind': 'person', 'name': '赵陌'})
        before, task = app.repo.load(), app.repo.pending()['id']
        with self.assertRaises(Error) as caught:
            app.submit(receipt)
        self.assertEqual(caught.exception.code, 'design_drift')
        self.assertEqual(app.repo.load(), before)
        self.assertEqual(app.repo.pending()['id'], task)

    def test_world_identity_cannot_be_replaced_or_moved_to_another_id(self):
        definition = character(id='guan', name='管衡', role='主管')
        for item in (character(id='guan'), character(id='other', name='管衡'),
                     character(id='guan', name='管衡', role='药商')):
            with self.subTest(item=item):
                app = self.app(definition)
                with self.assertRaises(Error):
                    app.submit(self.outline(app, item))

    def test_a_matching_identity_may_have_a_new_motivation(self):
        definition = character()
        app = self.app(definition)
        result = app.submit(self.outline(app, character(desire='先给病人送药。')))
        self.assertEqual(result['outcome'], 'design_accepted')

    def test_core_biographies_have_structure_but_minor_people_need_no_long_bio(self):
        entities.validate_introduction(character(importance='minor'))
        entities.validate_introduction({'id': 'shed', 'kind': 'place', 'name': '药棚'})
        entities.validate_introduction({'id': 'bottle', 'kind': 'item', 'name': '药瓶'})
        for details in (None, '', [], {'past': '往事'}, {**biography(), 'behavior': ''}):
            with self.subTest(details=details):
                with self.assertRaises(Error):
                    entities.validate_introduction(character(importance='core', biography=details))
        entities.validate_introduction(character(importance='core', biography=biography()))
        definition = character(importance='core', biography=biography())
        entities.validate_introduction(character(importance='core'), [definition])
        with self.assertRaises(Error):
            entities.validate_introduction(character(importance='minor'), [definition])

    def test_world_profiles_use_the_same_biography_validation(self):
        from test_world_grand import base_model, world_choices
        selected = world_choices()
        model = base_model(selected)
        model['characters'][0].update(importance='core', biography=biography())
        world.validate(model, selected, 'sel', sections=('rules',))
        model['characters'][0]['biography']['past'] = []
        with self.assertRaises(Error):
            world.validate(model, selected, 'sel', sections=('rules',))

    def test_first_registration_can_reuse_a_frozen_core_biography(self):
        app = self.app(character(importance='core', biography=biography()))
        receipt = self.writer(app, character(importance='core'))
        receipt['data']['prose'] += '赵陌走进屋内。'
        self.assertEqual(app.submit(receipt)['committed_chapter'], 1)
        self.assertTrue(app.audit()['ok'])

    def test_world_aliases_cannot_overlap_another_persons_identity(self):
        from test_world_grand import base_model, world_choices
        selected = world_choices()
        model = base_model(selected)
        model['characters'].append({**character(), 'links': []})
        model['characters'][0]['aliases'] = ['赵陌']
        with self.assertRaises(Error) as caught:
            world.validate(model, selected, 'sel', sections=('rules',))
        self.assertEqual(caught.exception.code, 'world_identity')

    def test_unmentioned_people_cannot_be_registered_by_a_committed_chapter(self):
        app = self.app()
        receipt = self.writer(app, character())
        self.assertNotIn('赵陌', receipt['data']['prose'])
        before = app.repo.load()['state']
        preview = app.submit(receipt, preview=True)
        self.assertIsNone(preview['committed_chapter'])
        self.assertIn('drift_evidence', {item['criterion'] for item in preview['findings']})
        result = app.submit(receipt)
        self.assertIsNone(result['committed_chapter'])
        self.assertEqual(app.repo.load()['state'], before)
        self.assertNotIn('visitor', app.repo.load()['state']['entities'])
        self.assertEqual(app.repo.headers('main'), [])

    def test_alias_introduction_has_exact_evidence_and_preview_rolls_back(self):
        app = self.app()
        receipt = self.writer(app, character(aliases=['药商']))
        prose = receipt['data']['prose'] + '药商走进屋内。'
        receipt['data']['prose'] = prose
        receipt['data']['drift_check']['introductions'] = [
            {'entity': 'visitor', 'evidence': {'chapter': 1, 'quote': '药商走进屋内。',
                                             'start': prose.index('药商')}}]
        before = tuple(app.repo.db.iterdump())
        app.submit(receipt, preview=True)
        self.assertEqual(tuple(app.repo.db.iterdump()), before)
        result = app.submit(receipt)
        self.assertEqual(result['committed_chapter'], 1)
        row = app.repo.headers('main')[0]
        event = next(item for item in app.repo.read_document(row['events'])
                     if item['op'] == 'entity' and item['entity']['id'] == 'visitor')
        self.assertEqual(event['evidence']['quote'], '药商走进屋内。')
        self.assertTrue(app.audit()['ok'])

    def test_even_an_explicit_unrelated_registration_quote_is_rejected(self):
        app = self.app()
        receipt = self.writer(app, character())
        prose = receipt['data']['prose']
        receipt['data']['drift_check']['introductions'] = [
            {'entity': 'visitor', 'evidence': {'chapter': 1, 'quote': prose[:2], 'start': 0}}]
        result = app.submit(receipt)
        self.assertIsNone(result['committed_chapter'])
        self.assertNotIn('visitor', app.repo.load()['state']['entities'])

    def test_direct_settlement_cannot_use_a_first_character_for_registration(self):
        state = facts.seed(tracked_contract(chapters=2))
        for event in ({'op': 'entity', 'entity': character()},
                      {'op': 'entity', 'entity': character(),
                       'evidence': {'chapter': 1, 'quote': '次', 'start': 0}}):
            with self.subTest(event=event), self.assertRaises(Error):
                facts.settle(state, [event], '次日他独自回屋。', 1)
        self.assertNotIn('visitor', state['entities'])

    def test_character_profiles_are_frozen_and_hidden_until_after_blind_read(self):
        app = self.app(character(importance='core', biography=biography()))
        app.configure_assurance('advisory', 'required', '隔离工程核验。')
        receipt = self.writer(app, character())
        receipt['data']['prose'] += '赵陌走进屋内。'
        result = app.submit(receipt)
        self.assertEqual(result['outcome'], 'continuity_review_required')
        ident = result['request_id']
        prepared = app.prepare_observer(ident, 'independent-reader')
        actor = ('independent-reader', prepared['token'])
        blind = app.read_review(ident, *actor)
        self.assertNotIn('comparison', blind)
        with self.assertRaises(Error):
            app.read_review(ident, *actor, compare=True)
        payload = {**blind['observation_template'], 'read_sources': list(blind['sources'])}
        app.observe_review(payload, *actor)
        # Change the live design after the candidate was frozen; the reader must keep the old one.
        changed = app.repo.load()
        changed['world']['characters'][-1]['biography']['past'] = '这不是冻结的小传。'
        app.repo.save(changed)
        compared = app.read_review(ident, *actor, compare=True)['comparison']['characters']
        profile = compared['profiles']['visitor']
        self.assertEqual(profile['world']['biography'], biography())
        reference = compared['source_hashes']['world_records']
        self.assertEqual(app.repo.read_document(reference)['characters:visitor']['biography'], biography())
        self.assertEqual(profile['introduction']['name'], '赵陌')
        self.assertIsNone(profile['current'])


if __name__ == '__main__':
    unittest.main()
