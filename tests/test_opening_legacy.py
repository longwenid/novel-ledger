"""The gate set every already-opened project was opened with must keep working unchanged.

A project whose creation state is `novel-ledger.creation/1` — because it was opened before opening/2
shipped, or is still in flight — keeps its 8 gates, its own value rules, its cross-gate constraint and
its alignment expectations. This file exists to prove that protocol was not silently re-planned.
"""
import copy
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from novel_ledger import creation, planning, world, workflow
from novel_ledger.bootstrap import local_application as Application
from novel_ledger.contracts import RESULT, digest
from novel_ledger.result_templates import template
from novel_ledger.sqlite_store import SQLiteRepository
from support import contract


VALUES = {
    'genre': {'genre': '都市生活', 'reader_promise': '在夜班退件中查清责任。', 'red_lines': ['没有超自然能力。'], 'allow_special_mechanism': False},
    'scale': {'word_range': [24, 400], 'chapter_min': 12, 'chapter_max': 200, 'chapter_aim': 60, 'volume_count': 1},
    'protagonist': {'id': 'shen', 'name': '沈桐', 'identity': '夜班工人', 'desire': '查清责任。', 'limit': '不牵连无关同事。'},
    'engine': {'story_engine': '核对退件来源，追查签字责任。', 'opposition': '主管担心调查影响考核。'},
    'relationships': {'relationships': ['同事互相依赖，却各自担心承担责任。']},
    'world': {'world_premise': '一座仓库的夜班退件纠纷。', 'mechanism': {'mode': 'none', 'principle': '仅有普通规章与人情。', 'cost': '行动承担现实责任。', 'limits': []}},
    'ending': {'ending': '退件责任明确，工人承担违规开箱的后果。'},
    'voice': {'voice': '具体动作与有立场的对白。', 'style_traits': ['少重复解释。', '因果承接完整。']},
}
GATE_ORDER = ('genre', 'scale', 'protagonist', 'engine', 'relationships', 'world', 'ending', 'voice')


def receipt(app, data):
    task = app.repo.pending()
    return {'schema': RESULT, 'task_id': task['id'], 'input_hash': task['input_hash'],
            'session': 'legacy-opening-' + uuid.uuid4().hex, 'data': data}


def options(app):
    gate = app.repo.pending()['input']['payload']['gate']['id']
    rows = []
    for i, ident in enumerate(('A', 'B', 'C')):
        value = copy.deepcopy(VALUES[gate])
        field = {'genre': 'reader_promise', 'protagonist': 'identity', 'engine': 'story_engine',
                 'world': 'world_premise', 'ending': 'ending', 'voice': 'voice'}.get(gate)
        if i and field:
            value[field] += '侧重' + str(i) + '。'
        elif i and gate == 'scale':
            value['word_range'] = [24 + i, 400 + i]
        elif i and gate == 'relationships':
            value['relationships'] = ['围绕第' + str(i) + '种利益分歧建立关系。']
        rows.append({'id': ident, 'title': '方案' + ident, 'premise': '具体方案' + ident + '。',
                     'pitch': '看一眼就想翻开的那句话' + ident + '。',
                     'scene': ['夜班仓库里，他把退件箱推到灯下，翻出封条上的签名。',
                               '凌晨的登记台前，他逐页核对自己经手的那一栏。'],
                     'driver': '方案' + ident + '以不同的方式推进：' + '核对封条' + ident + '。',
                     'tradeoff': '相比另外两案，选它要放弃' + ident + '那条更快的路。',
                     'fit_reason': '承接已选题材，因此把推进压在一件具体物件上。', 'value': value})
    return {'gate': gate, 'options': rows}


def model(app):
    opening = app.repo.load()['creation']
    selected = creation.selected(opening)
    value = {'selection_hash': opening['selection_hash'], 'premise': selected['world']['world_premise'],
             'story_capacity': '工程夹具：由退件责任、人情、资源与制度展开长期冲突。'}
    for section, fields in world.SECTIONS.items():
        ident = 'shen' if section == 'characters' else {'rules': 'r1', 'geography': 'g1'}.get(section, section + '1')
        row = {field: '工程世界中' + field + '的具体内容。' for field in fields}
        row.update(id=ident, links=[])
        value[section] = [row]
    value['characters'][0].update(name=selected['protagonist']['name'], desire=selected['protagonist']['desire'],
                                  limit=selected['protagonist']['limit'])
    value['rules'][0]['principle'] = '夜班退件必须登记负责人。'
    value['mechanisms'] = []
    return value


def contract_data(app, world=None):
    book = app.repo.load()
    model_data = world if world is not None else book['world']
    choices = creation.selected(book['creation'])
    value = contract()
    for gate in ('scale', 'engine', 'world', 'ending', 'voice'):
        value.update(copy.deepcopy(choices[gate]))
    value.pop('mechanism', None)      # world gate input, not a contract field
    value.pop('volume_count', None)   # carried by len(volumes)
    value.pop('world_premise', None)  # derived from the verified world
    value.update(genre=choices['genre']['genre'], reader_promise=choices['genre']['reader_promise'],
                 protagonist_setup=choices['protagonist'], allow_special_mechanism=choices['genre']['allow_special_mechanism'],
                 red_lines=choices['genre']['red_lines'], relationships=choices['relationships']['relationships'],
                 world_premise=model_data['premise'], world_rules=[r['principle'] for r in model_data['rules']])
    return value


def combined(app, world=None):
    model_data = world if world is not None else model(app)
    return {**model_data, 'contract': contract_data(app, model_data)}


def review_data(app):
    task = app.repo.pending()
    work = task['input']
    sources = app._sources(work)
    data = template(work['stage'], work['chapter'], sources)
    ref = {'chapter': 0, 'quote': next(iter(sources.values()))}
    data['verdict'] = 'pass'
    for row in data['checks']:
        row.update(result='pass', reason='仅工程协议样本。', evidence=[ref])
    return data


class LegacyOpeningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / 'book'
        # The one difference from a new book: this project states which opening protocol it runs.
        self.repo = SQLiteRepository.initialize(self.project, workflow.preparing_book(guided=True, opening_version=1))
        self.app = Application(self.repo)

    def tearDown(self):
        self.repo.close()
        self.temp.cleanup()

    def assertCode(self, code, fn, *args):
        with self.assertRaises(Exception) as caught:
            fn(*args)
        self.assertEqual(caught.exception.code, code)

    def offer(self):
        task = self.app.advance()['task']
        self.assertEqual(task['stage'], 'opening_options')
        self.app.submit(receipt(self.app, options(self.app)))
        handoff = self.app.advance()
        self.assertEqual(handoff['action'], 'await_choice')
        return handoff['board']

    def select_gates(self, count=8):
        for _ in range(count):
            board = self.offer()
            self.app.opening_choice(board['options'][0]['id'], board['hash'], '选它。')

    def world_ready(self):
        self.select_gates()
        task = self.app.advance()['task']
        self.assertEqual(task['stage'], 'world_model')
        self.app.submit(receipt(self.app, combined(self.app)))
        self.assertEqual(self.app.advance()['task']['stage'], 'world_review')
        self.app.submit(receipt(self.app, review_data(self.app)))
        self.assertEqual(self.app.advance()['task']['stage'], 'contract_review')
        self.app.submit(receipt(self.app, review_data(self.app)))
        return self.app.advance()

    def test_the_legacy_gate_order_is_still_eight_gates_in_the_original_sequence(self):
        state = self.repo.load()['creation']
        self.assertEqual(creation.opening_version(state), 1)
        self.assertEqual(creation.gate_ids(1), GATE_ORDER)
        self.assertEqual(creation.current(state)['total'], 8)
        self.assertFalse(creation.SYSTEM_GATES[1])
        self.assertEqual(self.app.status()['opening']['total_gates'], 8)

    def test_every_gate_is_still_dispatched_and_the_last_starts_the_world(self):
        self.select_gates(7)
        self.assertEqual(self.repo.load()['creation']['cursor'], 7)
        board = self.offer()
        self.assertEqual(board['gate']['id'], 'voice')
        result = self.app.opening_choice(board['options'][0]['id'], board['hash'], '选它。')
        self.assertEqual(result['next'], 'world_model')
        self.assertEqual(self.app.advance()['task']['stage'], 'world_model')

    def test_world_ready_end_to_end_under_the_legacy_alignment(self):
        final = self.world_ready()
        self.assertEqual(final['action'], 'world_ready')
        book = self.repo.load()
        self.assertEqual(len(book['creation']['selections']), 8)
        self.assertEqual(book['creation']['phase'], 'ready')
        self.assertEqual(book['creation']['schema'], 'novel-ledger.creation/1')
        self.assertEqual(self.repo.headers('main'), [])
        self.assertTrue(self.app.audit()['ok'])
        # the contract came from the legacy gates: a title the worker authored, and no view/theme/tone
        self.assertEqual(book['contract']['genre'], VALUES['genre']['genre'])
        self.assertEqual(book['contract']['allow_special_mechanism'], VALUES['genre']['allow_special_mechanism'])
        self.assertNotIn('pov', book['contract'])
        self.assertNotIn('theme', book['contract'])

    def test_the_genre_gate_still_constrains_the_world_gate(self):
        self.app.advance()
        self.app.submit(receipt(self.app, options(self.app)))
        self.app.opening_choice('A', self.app.advance()['board']['hash'], 'A')
        self.select_gates(4)                       # scale, protagonist, engine, relationships
        self.assertEqual(self.app.advance()['task']['stage'], 'opening_options')
        data = options(self.app)
        data['options'][0]['value']['mechanism']['mode'] = 'bounded'
        self.assertCode('opening_constraint', self.app.submit, receipt(self.app, data))

    def test_legacy_intake_uses_the_legacy_gate_ids(self):
        state = creation.begin('', 1)
        accepted = creation.intake(state, {'relationships': VALUES['relationships']}, '作者已有关系。')
        self.assertEqual(creation.selected(accepted)['relationships'], VALUES['relationships'])
        with self.assertRaises(Exception) as caught:
            creation.intake(state, {'pov': {'pov': '第三人称限知。'}}, '新协议的门。')
        self.assertEqual(caught.exception.code, 'intake')
        self.assertNotIn('pov', caught.exception.details['valid_gates'])
        self.assertIn('relationships', caught.exception.details['valid_gates'])

    def test_legacy_alignment_partition_still_matches_its_own_field_table(self):
        from novel_ledger.contracts import alignment_for

        choices = {gate: copy.deepcopy(VALUES[gate]) for gate in GATE_ORDER}
        expected, derived, authored = creation._v1_groups(choices)
        expected = {key: value for key, value in expected.items() if key in alignment_for(1) and key not in derived}
        groups = (set(expected), derived, set(authored))
        self.assertEqual(set().union(*groups), set(alignment_for(1)))
        self.assertFalse(any(groups[i] & groups[j] for i in range(3) for j in range(i + 1, 3)))
        self.assertEqual(authored, {'title'})

    def test_legacy_contract_survives_recontract_validation(self):
        """A project opened before tone/theme/pov existed must still validate its own contract."""
        final = self.world_ready()
        self.assertEqual(final['action'], 'world_ready')
        state = self.repo.load()['creation']
        checked = planning.validate_contract(copy.deepcopy(self.repo.load()['contract']))
        creation.validate_contract(checked, state, self.repo.load()['world'])
        self.assertEqual(digest(checked), digest(self.repo.load()['contract']))

    def test_a_project_that_says_version_one_is_the_only_one_on_the_old_gate_set(self):
        """`init` starts on the new protocol; version 1 is an explicit, remembered choice."""
        path = Path(self.temp.name) / 'fresh'
        initialized = SQLiteRepository.initialize(path, workflow.preparing_book(guided=True))
        initialized.close()
        repo = SQLiteRepository(path)
        try:
            book = repo.load()
            self.assertEqual(creation.opening_version(book['creation']), 2)
            self.assertEqual(len(creation.gates(book['creation'])), 10)
        finally:
            repo.close()


if __name__ == '__main__':
    unittest.main()
