"""Approved revision plans prepare character profiles before reusing a draft for writing."""
import copy
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from novel_ledger import craft, workflow
from novel_ledger.bootstrap import local_application as Application
from novel_ledger.sqlite_store import SQLiteRepository
from test_editorial import drive, enhanced_response
from test_narrative import tracked_contract


class AlignmentProfileTests(unittest.TestCase):
    def project(self, temp, helper=False):
        raw = tracked_contract(4)
        raw['editorial_features'] = True
        if helper:
            raw['entities'].append({'id': 'helper', 'name': '林勉', 'kind': 'person'})
        repo = SQLiteRepository.initialize(Path(temp) / 'book', workflow.new_book(raw))
        app = Application(repo)
        owner = app.run(through=4, source='工程回归：人物材料准备。')['owner']
        return repo, app, owner

    def check_profile_handoff(self, repo, app, owner, chapter, entities):
        book = repo.load()
        draft, budget = copy.deepcopy(book['draft']), copy.deepcopy(book['rework'])
        task = app.advance(owner=owner)['task']
        self.assertEqual((task['stage'], task['chapter']), ('profiles', chapter))
        self.assertEqual(repo.pending()['input']['payload']['entities'], entities)
        self.assertEqual(repo.load()['draft'], draft)
        self.assertEqual(repo.load()['rework'], budget)
        app.submit(enhanced_response(app))
        self.assertEqual(repo.load()['draft'], draft)
        self.assertEqual(repo.load()['rework'], budget)
        task = app.advance(owner=owner)['task']
        self.assertEqual((task['stage'], task['chapter']), ('repair', chapter))
        return repo.pending()['input']

    def test_preexisting_unprofiled_character_in_future_alignment_is_prepared_before_repair(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, app, owner = self.project(temp, helper=True)
            try:
                self.assertEqual(drive(app, owner)['action'], 'target_reached')
                self.assertNotIn('helper', repo.load()['profiles'])
                app.revise(2, '工程夹具：调整后续关系场景。', owner, through=2, changes={
                    'mode': 'reading', 'reading_changes': [{'kind': 'character', 'key': 'shen'}]})
                drive(app, owner, until='chapter_review')
                review = enhanced_response(app)
                review['data']['alignment']['action'] = 'adapt_future'
                app.submit(review)
                self.assertEqual(app.advance(owner=owner)['task']['stage'], 'alignment_plan')
                proposal = enhanced_response(app)
                plan = proposal['data']['plan']
                plan['participants'].append('helper')
                scene = plan['scenes'][0]
                scene['present'].append('helper')
                scene['speakers'].append('helper')
                scene['dialogue_intents'].append({
                    'entity': 'helper', 'seeks': '核对签字责任。', 'withholds': '没有需隐瞒的事。',
                    'pressure': '承担失误的后果。', 'tactic': '提供凭据。', 'knowledge_topics': []})
                app.submit(proposal)
                self.assertEqual(app.advance(owner=owner)['task']['stage'], 'alignment_review')
                app.submit(enhanced_response(app))
                work = self.check_profile_handoff(repo, app, owner, 3, ['helper'])
                self.assertEqual(set(repo.read_document(work['records']['profiles'])), {'shen', 'helper'})
                self.assertEqual(drive(app, owner)['action'], 'revision_ready')
                self.assertTrue(app.audit()['ok'])
                app.promote(owner)
                self.assertTrue(app.audit()['ok'])
            finally:
                repo.close()

    def test_historical_repair_rechecks_profile_against_restored_growth_without_spending_budget(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, app, owner = self.project(temp)
            try:
                for n in range(1, 4):
                    drive(app, owner, until='chapter_review')
                    self.assertEqual(repo.pending()['input']['chapter'], n)
                    review = enhanced_response(app)
                    if n == 3:
                        review['data']['facts']['events'].append({
                            'op': 'character_development', 'entity': 'shen',
                            'choice': '公开追问签字责任。', 'cost': '承担被怀疑的代价。',
                            'change': '愿意让同事核对自己的说法。',
                            'evidence': {'chapter': 3, 'quote': '要求先核对退件人的名字再开箱'}})
                    app.submit(review)
                self.assertEqual(drive(app, owner)['action'], 'target_reached')
                book = repo.load()
                self.assertEqual(book['profiles']['shen']['growth_basis'], craft.growth_basis(book['state'], 'shen'))
                app.revise(2, '工程夹具：回到成长前版本修正表达。', owner,
                           through=2, changes={'mode': 'expression'})
                book = repo.load()
                self.assertNotEqual(book['profiles']['shen']['growth_basis'], craft.growth_basis(book['state'], 'shen'))
                self.check_profile_handoff(repo, app, owner, 2, ['shen'])
                self.assertEqual(drive(app, owner)['action'], 'revision_ready')
                self.assertTrue(app.audit()['ok'])
                app.promote(owner)
                self.assertTrue(app.audit()['ok'])
            finally:
                repo.close()


if __name__ == '__main__':
    unittest.main()
