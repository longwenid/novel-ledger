"""Zero-input choices and rich world flow, using synthetic engineering receipts."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from novel_ledger import creation, world, workflow
from novel_ledger.application import Application
from novel_ledger.contracts import CONTRACT_ALIGNMENT, RESULT
from novel_ledger.quality import template
from novel_ledger.sqlite_store import SQLiteRepository
from support import contract, drive


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


def receipt(app, data):
    task = app.repo.pending()
    return {'schema': RESULT, 'task_id': task['id'], 'input_hash': task['input_hash'], 'session': 'opening-test-' + uuid.uuid4().hex, 'data': data}


def options(app):
    gate = app.repo.pending()['input']['payload']['gate']['id']
    rows = []
    for i, ident in enumerate(('A', 'B', 'C')):
        value = copy.deepcopy(VALUES[gate])
        # Distinct concrete choices; only A is selected in full-flow fixtures.
        field = {'genre': 'reader_promise', 'protagonist': 'identity', 'engine': 'story_engine', 'world': 'world_premise', 'ending': 'ending', 'voice': 'voice'}.get(gate)
        if i and field:
            value[field] += '侧重' + str(i) + '。'
        elif i and gate == 'scale':
            value['word_range'] = [24 + i, 400 + i]
        elif i and gate == 'relationships':
            value['relationships'] = ['围绕第' + str(i) + '种利益分歧建立关系。']
        rows.append({'id': ident, 'title': '方案' + ident, 'premise': '具体方案' + ident + '。',
                     'driver': '选择' + ident + '驱动的后果。', 'tradeoff': '需要承担对应选择的代价。',
                     'fit_reason': '工程夹具，依据已选范围。', 'value': value})
    return {'gate': gate, 'options': rows}


def model(app):
    opening = app.repo.load()['creation']
    selected = creation.selected(opening)
    value = {'selection_hash': opening['selection_hash'], 'premise': selected['world']['world_premise'], 'story_capacity': '工程夹具：由退件责任、人情、资源与制度展开长期冲突。'}
    for section, fields in world.SECTIONS.items():
        ident = 'shen' if section == 'characters' else {'rules': 'r1', 'geography': 'g1'}.get(section, section + '1')
        row = {field: '工程世界中' + field + '的具体内容。' for field in fields}
        row.update(id=ident, links=[])
        value[section] = [row]
    value['characters'][0].update(name=selected['protagonist']['name'], desire=selected['protagonist']['desire'], limit=selected['protagonist']['limit'])
    value['rules'][0]['principle'] = '夜班退件必须登记负责人。'
    value['mechanisms'] = []
    return value


def contract_data(app):
    book = app.repo.load()
    choices = creation.selected(book['creation'])
    value = contract()
    for gate in ('scale', 'engine', 'world', 'ending', 'voice'):
        value.update(copy.deepcopy(choices[gate]))
    value.pop('mechanism', None)      # world gate input, not a contract field
    value.pop('volume_count', None)   # carried by len(volumes)
    value.update(genre=choices['genre']['genre'], reader_promise=choices['genre']['reader_promise'],
                 protagonist_setup=choices['protagonist'], allow_special_mechanism=choices['genre']['allow_special_mechanism'],
                 red_lines=choices['genre']['red_lines'], relationships=choices['relationships']['relationships'],
                 world_rules=[r['principle'] for r in book['world']['rules']])
    return value


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


class OpeningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / 'book'
        self.repo = SQLiteRepository.initialize(self.project, workflow.preparing_book(guided=True))
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
            self.app.opening_choice('A', board['hash'], 'A')

    def world_ready(self):
        self.select_gates()
        self.assertEqual(self.app.advance()['task']['stage'], 'world_model')
        self.app.submit(receipt(self.app, model(self.app)))
        self.assertEqual(self.app.advance()['task']['stage'], 'world_review')
        self.app.submit(receipt(self.app, review_data(self.app)))
        self.assertEqual(self.app.advance()['task']['stage'], 'opening_contract')
        self.app.submit(receipt(self.app, contract_data(self.app)))
        self.assertEqual(self.app.advance()['task']['stage'], 'contract_review')
        self.app.submit(receipt(self.app, review_data(self.app)))
        return self.app.advance()

    def test_opening_contract_template_carries_every_alignment_field(self):
        self.select_gates()
        self.assertEqual(self.app.advance()['task']['stage'], 'world_model')
        self.app.submit(receipt(self.app, model(self.app)))
        self.assertEqual(self.app.advance()['task']['stage'], 'world_review')
        self.app.submit(receipt(self.app, review_data(self.app)))
        task = self.app.advance()['task']
        self.assertEqual(task['stage'], 'opening_contract')
        self.assertIn('world.md', json.dumps(task['guides']))
        blank = template('opening_contract', 1, {})
        full = contract_data(self.app)
        # Fields the alignment checks read are compared key by key, so the template must carry them.
        self.assertEqual(sorted(set(full) & set(CONTRACT_ALIGNMENT) - set(blank)), [])
        filled = {**blank, **copy.deepcopy(full)}
        filled.update(planning_window=3, review_interval=10, review_chunk=3)   # structural, not author decisions
        # A Worker filling only the published template must pass the alignment checks.
        self.app.submit(receipt(self.app, filled))

    def test_zero_input_starts_first_gate_and_never_requests_a_premise(self):
        self.assertEqual(self.repo.load()['creation']['source'], '')
        board = self.offer()
        self.assertEqual(board['gate']['id'], 'genre')
        self.assertEqual(len(board['options']), 3)
        self.assertIsNone(self.repo.load()['contract'])

    def test_single_read_delivers_the_exact_gate_and_brainstorm_lens(self):
        task = self.app.advance()['task']
        material = self.app.read(task['task_id'])
        self.assertEqual(material['payload']['gate']['id'], 'genre')
        self.assertEqual(material['payload']['creative_lens'], creation.LENSES[0])
        self.assertEqual(material['records']['opening_choices']['value'], {})

    def test_each_choice_advances_one_gate_and_last_starts_world(self):
        self.select_gates(7)
        self.assertEqual(self.repo.load()['creation']['cursor'], 7)
        self.assertIsNone(self.repo.load().get('world'))
        board = self.offer()
        result = self.app.opening_choice('A', board['hash'], 'A')
        self.assertEqual(result['next'], 'world_model')
        self.assertEqual(self.app.advance()['task']['stage'], 'world_model')

    def test_options_wait_for_author_and_cannot_choose_themselves(self):
        board = self.offer()
        self.assertEqual(self.app.advance()['board']['hash'], board['hash'])
        self.assertEqual(self.repo.load()['creation']['selections'], [])
        self.assertIsNone(self.repo.pending())

    def test_regroup_preserves_choice_history_and_rejects_old_board(self):
        board = self.offer()
        self.app.opening_regroup(board['hash'], '换一组，减少对抗。')
        updated = self.offer()
        self.assertNotEqual(updated['hash'], board['hash'])
        self.assertEqual(len(self.repo.load()['creation']['rejections']), 1)
        self.assertCode('opening_version', self.app.opening_choice, 'A', board['hash'], 'A')

    def test_back_keeps_earlier_choices_and_archives_dependent_selections(self):
        self.select_gates(3)
        first = self.repo.load()['creation']['selections'][0]
        self.app.opening_back('scale', '返回体量门重选。')
        state = self.repo.load()['creation']
        self.assertEqual(state['selections'], [first])
        self.assertEqual(len(state['history'][-1]['invalidated']), 2)
        self.assertEqual(self.offer()['gate']['id'], 'scale')

    def test_restart_restores_exact_displayed_board(self):
        board = self.offer()
        self.repo.close()
        self.repo = SQLiteRepository(self.project)
        self.app = Application(self.repo)
        self.assertEqual(self.app.advance()['board'], board)

    def test_complete_choices_create_rich_reviewed_world_without_starting_prose(self):
        final = self.world_ready()
        self.assertEqual(final['action'], 'world_ready')
        book = self.repo.load()
        self.assertEqual(set(world.SECTIONS), set(book['world']) - {'selection_hash', 'premise', 'story_capacity'})
        self.assertEqual(book['creation']['phase'], 'ready')
        self.assertEqual(len(book['creation']['selections']), 8)
        self.assertEqual(self.repo.headers('main'), [])
        self.assertIsNone(self.repo.pending())
        self.assertEqual(self.app.advance()['action'], 'world_ready')
        view = final['world_view']
        self.assertTrue(Path(view['html_path']).is_file())
        artifact = json.loads(Path(view['json_path']).read_text(encoding='utf-8'))
        self.assertEqual(artifact['world'], book['world'])
        self.assertEqual(len(artifact['choices']), 8)
        self.assertTrue(self.app.audit()['ok'])

    def test_world_design_and_review_do_not_generate_canonical_events(self):
        self.select_gates()
        self.app.advance()
        before = self.repo.load()['state']
        self.app.submit(receipt(self.app, model(self.app)))
        self.app.advance()
        self.app.submit(receipt(self.app, review_data(self.app)))
        self.assertEqual(self.repo.load()['state'], before)
        self.assertEqual(self.repo.headers('main'), [])

    def test_back_after_choices_cancels_stale_world_task(self):
        self.select_gates()
        self.app.advance()
        old = receipt(self.app, model(self.app))
        self.app.opening_back('world', '重新选择世界方向。')
        self.assertCode('stale_task', self.app.submit, old)
        self.assertEqual(self.offer()['gate']['id'], 'world')

    def test_no_mechanism_choice_cannot_be_silently_overwritten(self):
        self.select_gates()
        self.app.advance()
        data = model(self.app)
        data['mechanisms'] = [{'id': 'magic', **{k: '外挂。' for k in world.SECTIONS['mechanisms']}, 'links': []}]
        self.assertCode('world_alignment', self.app.submit, receipt(self.app, data))

    def test_world_records_require_valid_cross_references_and_choice_version(self):
        self.select_gates()
        self.app.advance()
        data = model(self.app)
        data['geography'][0]['links'] = ['economy:missing']
        self.assertCode('world_reference', self.app.submit, receipt(self.app, data))
        data = model(self.app)
        data['selection_hash'] = 'old'
        self.assertCode('world', self.app.submit, receipt(self.app, data))

    def test_final_contract_cannot_change_chosen_voice_or_scale(self):
        self.select_gates()
        self.app.advance()
        self.app.submit(receipt(self.app, model(self.app)))
        self.app.advance()
        self.app.submit(receipt(self.app, review_data(self.app)))
        self.app.advance()
        data = contract_data(self.app)
        data['voice'] = '另一个文风。'
        self.assertCode('opening_alignment', self.app.submit, receipt(self.app, data))
        data = contract_data(self.app)
        data['word_range'] = [30, 400]
        self.assertCode('opening_alignment', self.app.submit, receipt(self.app, data))
        data = contract_data(self.app)
        data['story_engine'] = '换一个推进引擎。'
        self.assertCode('opening_alignment', self.app.submit, receipt(self.app, data))

    def test_explicit_run_after_world_delivery_enters_existing_writing_flow(self):
        self.world_ready()
        run = self.app.run(through=1, source='作者要求试写一章。')
        self.assertEqual(self.app.advance(owner=run['owner'])['task']['stage'], 'book_plan')
        self.assertEqual(drive(self.app, run['owner'])['action'], 'target_reached')
        self.assertEqual(self.app.status()['accepted_chapters'], 1)
        self.assertTrue(self.app.audit()['ok'])

    def test_world_delivery_error_does_not_roll_back_activated_contract(self):
        self.world_ready()
        blocker = self.project / 'world.html'
        blocker.unlink()
        blocker.mkdir()
        final = self.app.advance()
        self.assertEqual(final['action'], 'world_ready')
        self.assertIn('world_view_error', final)
        self.assertEqual(self.repo.load()['creation']['phase'], 'ready')
        self.assertIsNotNone(self.repo.load()['contract'])

    def test_duplicate_options_and_unsupported_mechanism_are_rejected(self):
        self.app.advance()
        data = options(self.app)
        data['options'][1]['driver'] = data['options'][0]['driver']
        self.assertCode('opening_diversity', self.app.submit, receipt(self.app, data))
        self.app.submit(receipt(self.app, options(self.app)))
        self.app.opening_choice('A', self.app.advance()['board']['hash'], 'A')
        self.select_gates(4)
        self.app.advance()
        data = options(self.app)
        data['options'][0]['value']['mechanism']['mode'] = 'bounded'
        self.assertCode('opening_constraint', self.app.submit, receipt(self.app, data))

    def test_importing_a_contract_into_a_guided_project_is_refused_not_ignored(self):
        command = [sys.executable, str(ROOT / 'scripts' / 'novel.py'), '--project', str(self.project)]
        early = subprocess.run(command + ['opening', '--file', str(ROOT / 'assets' / 'contract.example.json'),
                                          '--source', '作者开书前给完整候选。'],
                               capture_output=True, text=True, encoding='utf-8', errors='replace')
        self.assertEqual(early.returncode, 2)
        self.assertEqual(json.loads(early.stdout)['error'], 'creation')
        self.app.advance()
        late = subprocess.run(command + ['opening', '--file', str(ROOT / 'assets' / 'contract.example.json'),
                                         '--source', '作者中途给完整候选。'],
                              capture_output=True, text=True, encoding='utf-8', errors='replace')
        self.assertEqual(json.loads(late.stdout)['error'], 'creation')
        self.assertEqual(self.repo.load()['creation']['phase'], 'choosing')

    def test_cli_init_without_contract_immediately_supports_guided_opening(self):
        path = Path(self.temp.name) / 'zero'
        command = [sys.executable, str(ROOT / 'scripts' / 'novel.py'), '--project', str(path)]
        init = subprocess.run(command + ['init'], capture_output=True, text=True, encoding='utf-8', errors='replace')
        self.assertEqual(init.returncode, 0, init.stderr)
        result = subprocess.run(command + ['advance'], capture_output=True, text=True, encoding='utf-8', errors='replace')
        self.assertEqual(json.loads(result.stdout)['task']['stage'], 'opening_options')


if __name__ == '__main__':
    unittest.main()
