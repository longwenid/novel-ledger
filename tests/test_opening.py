"""Zero-input choices and rich world flow, using synthetic engineering receipts.

These exercise opening/2 — the gate set a new book opens with: 10 gates, one question each, the
structural length gate answered by the engine, and independent verification. The gate set every earlier
project was opened with is covered by `test_opening_legacy.py`: an in-flight opening keeps its own
protocol.
"""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from novel_ledger import creation, planning, world, workflow
from novel_ledger.bootstrap import local_application as Application
from novel_ledger.contracts import (CHECK_SETS, CHECKS_VERSION, CONTRACT_ALIGNMENT, EDITORIAL_VERSION,
                                    POV_CHECKS_VERSION, RESULT, SCALE_TIERS, SCALE_WINDOW, alignment_for, digest, dump, han_count)
from novel_ledger.result_templates import template
from novel_ledger.sqlite_store import SQLiteRepository
import support
from support import contract, drive, response


VALUES = {
    'genre': {'genre': '都市生活', 'reader_promise': '在夜班退件中查清责任。', 'tone': '冷硬的日常底色，偶尔留一点暖。'},
    'pov': {'pov': '第三人称限知，只跟沈桐的所见与所知；换场时先交代视角归属。'},
    'world': {'world_premise': '一座仓库的夜班退件纠纷。', 'mechanism': {'mode': 'none', 'principle': '仅有普通规章与人情。', 'cost': '行动承担现实责任。', 'limits': []},
              'red_lines': ['没有超自然能力。'], 'allow_special_mechanism': False},
    'protagonist': {'id': 'shen', 'name': '沈桐', 'identity': '夜班工人', 'desire': '查清责任。', 'limit': '不牵连无关同事。'},
    'relationships': {'relationships': ['同事互相依赖，却各自担心承担责任。']},
    'engine': {'story_engine': '核对退件来源，追查签字责任。', 'opposition': '主管担心调查影响考核。'},
    'ending': {'ending': '退件责任明确，工人承担违规开箱的后果。', 'theme': '责任怎样在人之间传递。'},
    'voice': {'voice': '具体动作与有立场的对白。', 'style_traits': ['少重复解释。', '因果承接完整。']},
    'title': {'title': '夜班退件'},
}
# Which field of each gate the fixture varies, so three options are genuinely distinct.
VARY = {'genre': 'reader_promise', 'pov': 'pov', 'world': 'world_premise', 'protagonist': 'identity',
        'relationships': 'relationships', 'engine': 'story_engine', 'ending': 'ending', 'voice': 'voice',
        'title': 'title'}


def receipt(app, data):
    task = app.repo.pending()
    return {'schema': RESULT, 'task_id': task['id'], 'input_hash': task['input_hash'], 'session': 'opening-test-' + uuid.uuid4().hex, 'data': data}


def rows_for(gate):
    """Three worker-shaped options for one gate, built from the fixture values."""
    rows = []
    for i, ident in enumerate(('A', 'B', 'C')):
        value = copy.deepcopy(VALUES[gate])
        field = VARY.get(gate)
        if i and field:
            if isinstance(value[field], list):
                value[field] = ['围绕第' + str(i) + '种利益分歧建立的关系。']
            else:
                value[field] += '侧重' + str(i) + '。'
        rows.append({'id': ident, 'title': '方案' + ident, 'premise': '具体方案' + ident + '。',
                     'pitch': '看一眼就想翻开的那句话' + ident + '。',
                     'scene': ['夜班仓库里，他把退件箱推到灯下，翻出封条上的签名。',
                               '凌晨的登记台前，他逐页核对自己经手的那一栏。'],
                     'driver': '方案' + ident + '以不同的方式推进：' + '核对封条' + ident + '。',
                     'tradeoff': '相比另外两案，选它要放弃' + ident + '那条更快的路。',
                     'fit_reason': '承接已选题材，因此把推进压在一件具体物件上。', 'value': value})
    return rows


def options(app):
    gate = app.repo.pending()['input']['payload']['gate']['id']
    return {'gate': gate, 'options': rows_for(gate)}


def shown(state):
    """The state with a board on display: the engine already gave one, or a worker offers one."""
    if state['board'] is not None:
        return state
    return creation.offer(state, {'gate': creation.current(state)['id'], 'options': rows_for(creation.current(state)['id'])})


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


def contract_data(app, world=None):
    """The contract as the combined dispatch writes it: read off the selections plus that draft world."""
    book = app.repo.load()
    model = world if world is not None else book['world']
    choices = creation.selected(book['creation'])
    scale = choices['scale']
    # The shortest chapter count the chosen tier can actually be written at, so the engineering flow
    # stays cheap: the contract only has to land inside the tier's writable window.
    total = scale['chapter_window'][0]
    value = contract()
    value.update({key: copy.deepcopy(scale[key]) for key in ('word_range', 'chapter_min', 'chapter_max', 'chapter_aim')})
    value.update(copy.deepcopy(choices['engine']))
    value.update(copy.deepcopy(choices['ending']))
    value.update(copy.deepcopy(choices['voice']))
    value.update(copy.deepcopy(choices['pov']))
    value.update(copy.deepcopy(choices['title']))
    value.update(genre=choices['genre']['genre'], reader_promise=choices['genre']['reader_promise'], tone=choices['genre']['tone'],
                 protagonist_setup=copy.deepcopy(choices['protagonist']),
                 relationships=copy.deepcopy(choices['relationships']['relationships']),
                 allow_special_mechanism=choices['world']['allow_special_mechanism'],
                 world_premise=choices['world']['world_premise'], red_lines=copy.deepcopy(choices['world']['red_lines']),
                 world_rules=[r['principle'] for r in model['rules']],
                 planning_window=6,
                 volumes=[{'id': 'v' + str(i + 1), 'purpose': '查明来源并面对后果。',
                           'end': total * (i + 1) // scale['volume_count']} for i in range(scale['volume_count'])])
    return value


def combined(app, world=None):
    """What the combined world+contract dispatch submits: the world plus the contract it implies."""
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


def writable_response(app, task_id=None, session=None, claim=None):
    """The engineering draft is a stub. A tier's chapter_min is a real length, so pad it to fit the
    contract it is judged against — the point under test is the handoff, not the stub's length."""
    result = response(app, task_id, session, claim)
    data = result.get('data')
    if isinstance(data, dict) and isinstance(data.get('prose'), str):
        need = (app.repo.load().get('contract') or {}).get('chapter_min', 0)
        filler = '登记台前的灯一直亮着，他把经手的凭据按顺序排开，逐个核对名字与责任栏。'
        while han_count(data['prose']) < need:
            data['prose'] += filler
    return result


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

    def board(self):
        """The current board: a creative gate needs a worker, a structural gate already has one."""
        handoff = self.app.advance()
        if handoff['action'] == 'await_choice':
            return handoff['board']
        task = handoff['task']
        self.assertEqual(task['stage'], 'opening_options')
        self.app.submit(receipt(self.app, options(self.app)))
        handoff = self.app.advance()
        self.assertEqual(handoff['action'], 'await_choice')
        return handoff['board']

    def choose_board(self, board, tier=None):
        option = board['options'][0]
        if tier is not None:
            # 换一组 slides the tier window along the ladder until the wanted size shows up.
            for _ in range(len(SCALE_TIERS)):
                tiers = [row['value']['tier'] for row in board['options']]
                if tier in tiers:
                    option = board['options'][tiers.index(tier)]
                    break
                self.app.opening_regroup(board['hash'], '换一组体量档位。')
                board = self.board()
            self.assertEqual(option['value']['tier'], tier)
        self.app.opening_choice(option['id'], board['hash'], '选它。')
        return option

    def test_naming_a_tier_slides_the_ladder_to_it(self):
        """A size class is named, not proposed: the window slides instead of the author regrouping."""
        self.select_gates(2)
        board = self.board()
        self.assertEqual(board['gate']['id'], 'scale')
        self.assertNotIn('t0', [row['value']['tier'] for row in board['options']])
        self.app.opening_tier('t0', '作者指定最小档。')
        self.assertEqual(creation.view(self.repo.load()['creation'])['selected']['scale']['tier'], 't0')

    def select_gates(self, count=10, scale_tier=None):
        for _ in range(count):
            board = self.board()
            self.choose_board(board, scale_tier if board['gate']['id'] == 'scale' else None)

    def world_ready(self, outline=None, scale_tier=None):
        self.select_gates(scale_tier=scale_tier)
        task = self.app.advance()['task']
        self.assertEqual(task['stage'], 'world_model')
        self.assertEqual(task['stages'], ['world_model', 'opening_contract'])   # one cold worker, two drafts
        # the combined dispatch answers both artifacts in one receipt
        data = combined(self.app)
        if outline == 'default':
            data['contract'].pop('volume_outline')
        elif outline is not None:
            data['contract']['volume_outline'] = outline
        self.app.submit(receipt(self.app, data))
        self.assertEqual(self.app.advance()['task']['stage'], 'world_review')
        self.app.submit(receipt(self.app, review_data(self.app)))
        self.assertEqual(self.app.advance()['task']['stage'], 'contract_review')
        self.app.submit(receipt(self.app, review_data(self.app)))
        return self.app.advance()

    def test_opening_contract_template_carries_every_alignment_field(self):
        self.select_gates()
        task = self.app.advance()['task']
        self.assertEqual(task['stage'], 'world_model')
        # the combined dispatch publishes both guides and a template carrying both artifacts
        self.assertIn('world.md', json.dumps(task['guides']))
        blanks = json.loads(Path(task['template_path']).read_text(encoding='utf-8'))['data']
        self.assertIn('contract', blanks)
        blank = blanks['contract']
        self.assertEqual(len(blank), len(planning.skeleton()))
        self.app.submit(receipt(self.app, combined(self.app)))
        self.assertEqual(self.app.advance()['task']['stage'], 'world_review')
        self.app.submit(receipt(self.app, review_data(self.app)))
        task = self.app.advance()['task']
        self.assertEqual(task['stage'], 'contract_review')
        full = contract_data(self.app)
        # Fields the alignment checks read are compared key by key, so the template must carry them.
        self.assertEqual(sorted(set(full) & set(CONTRACT_ALIGNMENT) - set(blank)), [])
        filled = {**blank, **copy.deepcopy(full)}
        filled.update(planning_window=6, review_interval=10, review_chunk=3, review_fanout=3)   # structural, not author decisions
        # The same alignment the contract branch runs, on an object filled from the published template.
        planning.validate_contract(filled)
        creation.validate_contract(planning.validate_contract(filled), self.repo.load()['creation'],
                                   self.repo.load()['world'])
        # The independent review of the drafted contract decides whether it activates.
        self.app.submit(receipt(self.app, review_data(self.app)))
        self.assertEqual(self.app.advance()['action'], 'world_ready')

    def test_brief_replaces_whole_guides_and_trims_unused_records(self):
        task = self.app.advance()['task']
        material = json.loads(Path(task['input_path']).read_text(encoding='utf-8'))
        brief = material['brief']
        # the brief carries this gate's own rules, the lens, and the author-facing contract
        self.assertIn('题材、承诺与基调', brief)
        self.assertIn('reader_promise', brief)
        self.assertIn(material['payload']['lens_brief'], brief)
        self.assertIn('pitch', brief)
        self.assertIn('scene', brief)
        # the brief carries the chosen directions, so only rejections stay required reading
        self.assertEqual(material['required'], ['opening_rejections'])
        envelope = json.loads(Path(task['task_path']).read_text(encoding='utf-8'))
        self.assertIn('opening_choices', envelope['records'])          # reachable on demand
        self.assertIn('state', envelope['records'])
        self.assertNotIn('state', material['required'])
        self.assertNotIn('contract', material['required'])
        # record hashes are delivered once, in task.json, not copied into the view
        self.assertNotIn('records', material)
        # the guide files remain available as reference, and world.md is not shipped to the opening
        self.assertIn('hatch.md', json.dumps(task['guides']))
        self.assertNotIn('world.md', json.dumps(task['guides']))
        # once directions are closed, the next creative brief carries them instead of the whole records
        self.choose_board(self.board())                       # 定位
        self.choose_board(self.board())                       # 视角
        self.choose_board(self.board())                       # 体量（结构门，即时给定）
        later = json.loads(Path(self.app.advance()['task']['input_path']).read_text(encoding='utf-8'))
        self.assertIn('已选方向', later['brief'])

    def test_guides_agree_with_the_enforced_option_contract(self):
        """The guide is prose; the contract is code. Keep the author-facing rules aligned."""
        from novel_ledger.contracts import OPTION_CONTRACT

        guide = (ROOT / 'references' / 'opening.md').read_text(encoding='utf-8')
        for token in ('pitch', 'scene', 'opening_voice', 'opening_diversity'):
            self.assertIn(token, guide, token)
        toolbox = (ROOT / 'references' / 'hatch.md').read_text(encoding='utf-8')
        self.assertIn('用来想', toolbox + guide)
        for key in OPTION_CONTRACT.split('、')[0:1]:
            self.assertIn('id', key)

    def test_options_must_propose_not_self_justify(self):
        self.app.advance()
        data = options(self.app)
        data['options'][0]['fit_reason'] = '混搭透镜的典型落法：两个设定互相改变走向。'
        self.assertCode('opening_voice', self.app.submit, receipt(self.app, data))
        data = options(self.app)
        data['options'][0]['scene'] = ['具体画面。']
        self.assertCode('opening_scene', self.app.submit, receipt(self.app, data))
        data = options(self.app)
        for option in data['options']:
            option['driver'] = '以刻度推进，' + option['id'] + '。'
        self.assertCode('opening_diversity', self.app.submit, receipt(self.app, data))

    def test_zero_input_starts_first_gate_and_never_requests_a_premise(self):
        self.assertEqual(self.repo.load()['creation']['source'], '')
        board = self.board()
        self.assertEqual(board['gate']['id'], 'genre')
        self.assertEqual(len(board['options']), 3)
        self.assertIsNone(self.repo.load()['contract'])

    def test_brainstorm_lenses_are_unique_methods_not_labels(self):
        from novel_ledger.contracts import LENSES, VOLUME_TURNS

        self.assertEqual(list(creation.LENSES), [label for label, _p, _s in LENSES])
        self.assertEqual(len(set(creation.LENSES)), len(LENSES))
        for index in range(len(LENSES)):
            brief = creation.lens_brief(index)
            self.assertIn(LENSES[index][0], brief)
            self.assertIn(LENSES[index][1], brief)
            self.assertIn(LENSES[index][2], brief)
        self.assertEqual(creation.lens_brief(len(LENSES)), creation.lens_brief(0))   # round wraps
        self.assertEqual(len(VOLUME_TURNS), 5)
        task = self.app.advance()['task']
        self.assertIn('hatch.md', json.dumps(task['guides']))
        material = json.loads(Path(task['input_path']).read_text(encoding='utf-8'))
        self.assertEqual(material['payload']['creative_lens'], LENSES[0][0])
        self.assertIn(LENSES[0][0], material['payload']['lens_brief'])
        self.assertIn(LENSES[0][1], material['payload']['lens_brief'])

    def test_single_read_delivers_the_exact_gate_and_brainstorm_lens(self):
        task = self.app.advance()['task']
        material = self.app.read(task['task_id'])
        self.assertEqual(material['payload']['gate']['id'], 'genre')
        self.assertEqual(material['payload']['creative_lens'], creation.LENSES[0])
        # the brief is delivered with the task; the choices record is reference, read on demand
        view = json.loads(Path(task['input_path']).read_text(encoding='utf-8'))
        self.assertIn(creation.LENSES[0], view['brief'])
        self.assertIn('opening_choices', material['on_demand'])
        single = self.app.read(task['task_id'], 'opening_choices')
        self.assertEqual(single['records']['opening_choices']['value'], {})

    def test_single_decision_gates_carry_their_own_delivery_requirement(self):
        self.choose_board(self.board())                                  # 定位
        view = json.loads(Path(self.app.advance()['task']['input_path']).read_text(encoding='utf-8'))
        self.assertIn('scene 用该方案的人称写出来', view['brief'])          # the person must show, not be argued
        self.choose_board(self.board())                                  # 视角
        self.choose_board(self.board())                                  # 体量
        self.select_gates(6)                                             # 世界…文风，留下最后一门
        title = json.loads(Path(self.app.advance()['task']['input_path']).read_text(encoding='utf-8'))
        self.assertIn('本门只决定书名', title['brief'])
        # the selected relations are carried as one readable line, not as an empty list
        self.assertIn('核心关系与人物张力', title['brief'])
        self.assertIn('同事互相依赖', title['brief'])

    def test_each_choice_advances_one_gate_and_last_starts_world(self):
        self.select_gates(9)
        self.assertEqual(self.repo.load()['creation']['cursor'], 9)
        self.assertIsNone(self.repo.load().get('world'))
        board = self.board()
        self.assertEqual(board['gate']['id'], 'title')
        result = self.app.opening_choice(board['options'][0]['id'], board['hash'], '选它。')
        self.assertEqual(result['next'], 'world_model')
        self.assertEqual(self.app.advance()['task']['stage'], 'world_model')

    def test_options_wait_for_author_and_cannot_choose_themselves(self):
        board = self.board()
        self.assertEqual(self.app.advance()['board']['hash'], board['hash'])
        self.assertEqual(self.repo.load()['creation']['selections'], [])
        self.assertIsNone(self.repo.pending())

    def test_regroup_preserves_choice_history_and_rejects_old_board(self):
        board = self.board()
        self.app.opening_regroup(board['hash'], '换一组，减少对抗。')
        updated = self.board()
        self.assertNotEqual(updated['hash'], board['hash'])
        self.assertEqual(len(self.repo.load()['creation']['rejections']), 1)
        self.assertCode('opening_version', self.app.opening_choice, 'A', board['hash'], 'A')

    def test_back_keeps_earlier_choices_and_archives_dependent_selections(self):
        self.select_gates(4)                                    # genre, pov, scale, world
        kept = self.repo.load()['creation']['selections'][:2]
        self.app.opening_back('scale', '返回体量门重选。')
        state = self.repo.load()['creation']
        self.assertEqual(state['selections'], kept)
        self.assertEqual(len(state['history'][-1]['invalidated']), 2)
        self.assertEqual(self.board()['gate']['id'], 'scale')

    def test_restart_restores_exact_displayed_board(self):
        board = self.board()
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
        self.assertEqual(len(book['creation']['selections']), 10)
        self.assertEqual(self.repo.headers('main'), [])
        self.assertIsNone(self.repo.pending())
        self.assertEqual(self.app.advance()['action'], 'world_ready')
        view = final['world_view']
        self.assertTrue(Path(view['html_path']).is_file())
        self.assertEqual(Path(view['html_path']), (self.project / 'book.html').resolve())
        self.assertFalse((self.project / 'world.html').exists())
        page = Path(view['html_path']).read_text(encoding='utf-8')
        for section, fields in world.SECTIONS.items():
            self.assertIn(world.LABELS[section], page)
            for row in book['world'][section]:
                for field in fields:
                    self.assertIn(row[field], page)
        self.assertIn('世界独立核验 · 通过', page)
        self.assertIn('读正文', page)
        self.assertIn('世界关联图', page)
        self.assertIn('历史时间线', page)
        artifact = json.loads(Path(view['json_path']).read_text(encoding='utf-8'))
        self.assertEqual(artifact['world'], book['world'])
        self.assertEqual(len(artifact['choices']), 10)
        self.assertTrue(self.app.audit()['ok'])

    def test_reviewed_world_automatically_leads_to_full_volume_outline_without_prose(self):
        policy = {'scope': 'current', 'words': 500, 'tolerance': 50}
        handoff = self.world_ready(outline=policy, scale_tier='t1')
        self.assertEqual(handoff['task']['stage'], 'book_plan')
        self.assertTrue(Path(handoff['world_view']['html_path']).is_file())
        first_volume = self.repo.load()['contract']['volumes'][0]
        head = drive(self.app, until='volume_plan')
        task = self.repo.pending()
        self.assertEqual(head['task']['chapter'], 1)
        material = self.app.read(task['id'])
        self.assertIn('world_model', task['input']['required'])
        self.assertEqual(material['payload']['volume_outline']['last'], first_volume['end'])
        template_path = Path(head['task']['template_path'])
        blank = json.loads(template_path.read_text(encoding='utf-8'))['data']
        self.assertNotIn('chapters', blank)
        self.assertEqual(len(blank['brainstorm']), 2)
        self.assertEqual(blank['world_hash'], digest(self.repo.load()['world']))
        batch = drive(self.app, until='volume_outline')['task']
        blank = json.loads(Path(batch['template_path']).read_text(encoding='utf-8'))['data']
        window = self.repo.load()['contract']['planning_window']
        self.assertEqual([c['chapter'] for c in blank['chapters']], list(range(1, min(6, window) + 1)))
        before = copy.deepcopy(self.repo.load()['state'])
        design = response(self.app)
        self.app.submit(design)
        review_task = self.app.advance()['task']
        self.assertEqual(review_task['stage'], 'outline_review')
        self.assertIn('world_model', self.repo.pending()['input']['required'])
        self.assertEqual(self.repo.load()['designs']['volume:v1'].get('chapters', []), [])
        review = response(self.app)
        review['session'] = design['session']
        self.assertCode('session_reuse', self.app.submit, review)
        self.app.submit(response(self.app))
        ready = drive(self.app)
        self.assertEqual(ready['action'], 'outline_ready')
        self.assertEqual(ready['volumes'], ['v1'])
        self.assertEqual(self.repo.headers('main'), [])
        self.assertIsNone(self.repo.pending())
        self.assertEqual(self.repo.load()['state'], before)
        chapters = self.repo.load()['designs']['volume:v1']['chapters']
        self.assertEqual([c['chapter'] for c in chapters], list(range(1, first_volume['end'] + 1)))
        self.assertTrue(all(han_count(c['synopsis']) == 500 for c in chapters))
        page = Path(ready['world_view']['html_path']).read_text(encoding='utf-8')
        self.assertIn('逐章卷纲', page)
        self.assertIn('卷纲脑暴与选案', page)
        self.assertIn(chapters[1]['synopsis'], page)
        run = self.app.run(through=1, source='试写一章。')
        drive(self.app, run['owner'], until='plan')
        planner = self.repo.pending()['input']
        selected = self.repo.read_document(planner['records']['volume_outline_window'])
        self.assertEqual([c['chapter'] for c in selected], [1])
        write = drive(self.app, run['owner'], until='write')
        self.assertEqual(write['task']['stage'], 'write')
        writer = self.repo.pending()['input']
        self.assertEqual(self.repo.read_document(writer['records']['chapter_outline']), chapters[0])

    def test_volume_outline_rejections_are_atomic_and_preserve_the_frozen_task(self):
        self.world_ready(outline={'scope': 'current', 'words': 500, 'tolerance': 50}, scale_tier='t1')
        drive(self.app, until='volume_plan')
        brainstorm = response(self.app)
        brainstorm['data']['brainstorm'][1]['premise'] = brainstorm['data']['brainstorm'][0]['premise']
        self.assertCode('outline_brainstorm', self.app.submit, brainstorm)
        drive(self.app, until='volume_outline')
        valid = response(self.app)
        before = dump(self.repo.load())
        task_id = self.repo.pending()['id']
        variants = []
        short = copy.deepcopy(valid); short['data']['chapters'][0]['synopsis'] = '甲' * 449
        variants.append(('outline_length', short))
        long = copy.deepcopy(valid); long['data']['chapters'][0]['synopsis'] = '甲' * 551
        variants.append(('outline_length', long))
        missing = copy.deepcopy(valid); missing['data']['chapters'].pop()
        variants.append(('outline_coverage', missing))
        wrong_world = copy.deepcopy(valid); wrong_world['data']['world_hash'] = 'other'
        variants.append(('outline_world', wrong_world))
        wrong_ref = copy.deepcopy(valid); wrong_ref['data']['chapters'][0]['world_refs'] = ['rules:missing']
        variants.append(('outline_world', wrong_ref))
        wrong_node = copy.deepcopy(valid); wrong_node['data']['chapters'][0]['node_ids'] = ['missing']
        variants.append(('outline_nodes', wrong_node))
        for code, candidate in variants:
            with self.subTest(code=code):
                self.assertCode(code, self.app.submit, candidate)
                self.assertEqual(dump(self.repo.load()), before)
                self.assertEqual(self.repo.pending()['id'], task_id)
        for length in (450, 550):
            edge = copy.deepcopy(valid)
            edge['data']['chapters'][0]['synopsis'] = '甲' * length
            self.app.submit(edge, preview=True)
            self.assertEqual(dump(self.repo.load()), before)
        self.app.submit(valid)

    def test_explicit_all_guided_opening_delivers_all_volume_outlines_before_prose(self):
        handoff = self.world_ready(outline={'scope': 'all', 'words': 500, 'tolerance': 50}, scale_tier='t1')
        self.assertEqual(handoff['task']['stage'], 'book_plan')
        ready = drive(self.app)
        self.assertEqual(ready['action'], 'outline_ready')
        book = self.repo.load()
        volumes = book['contract']['volumes']
        self.assertEqual(ready['volumes'], [volume['id'] for volume in volumes])
        self.assertEqual(book['contract']['volume_outline'], {'scope': 'all', 'words': 500, 'tolerance': 50})
        for volume in volumes:
            chapters = book['designs']['volume:' + volume['id']]['chapters']
            self.assertEqual([c['chapter'] for c in chapters], list(range(volume['first'], volume['end'] + 1)))
        self.assertEqual(self.repo.headers('main'), [])
        self.assertIsNone(self.repo.pending())
        self.assertTrue(self.app.audit()['ok'])

    def test_default_opening_delivers_only_near_term_outline_without_prose(self):
        self.world_ready(outline='default', scale_tier='t1')
        ready = drive(self.app)
        self.assertEqual(ready['action'], 'outline_ready')
        self.assertEqual(ready['planning_mode'], 'rolling')
        self.assertEqual(ready['coverage'], [{'volume': 'v1', 'first': 1, 'last': 6}])
        book = self.repo.load()
        self.assertNotIn('volume:v2', book['designs'])
        self.assertEqual(len(book['designs']['volume:v1']['chapters']), 6)
        self.assertEqual(self.repo.headers('main'), [])
        self.assertIsNone(self.repo.pending())

    def test_world_design_and_review_do_not_generate_canonical_events(self):
        self.select_gates()
        self.app.advance()
        before = self.repo.load()['state']
        self.app.submit(receipt(self.app, combined(self.app)))
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
        self.assertEqual(self.board()['gate']['id'], 'world')

    def test_no_mechanism_choice_cannot_be_silently_overwritten(self):
        self.select_gates()
        self.app.advance()
        data = combined(self.app)
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
        # Each attempt drafts the world plus a contract that breaks one closed choice: the combined
        # dispatch must refuse the contract half without accepting the world half either.
        for mutate, label in ((lambda value: value.update(voice='另一个文风。'), 'voice'),
                              (lambda value: value.update(word_range=[300000, 460000]), 'word_range'),
                              (lambda value: value.update(story_engine='换一个推进引擎。'), 'story_engine'),
                              (lambda value: value.update(title='换一个书名。'), 'title'),
                              (lambda value: value.update(tone='换一个基调。'), 'tone'),
                              (lambda value: value.update(pov='第三人称全知。'), 'pov')):
            model_data = model(self.app)
            draft = contract_data(self.app, model_data)
            mutate(draft)
            self.assertCode('opening_alignment', self.app.submit,
                            receipt(self.app, {**model_data, 'contract': draft}))
            self.assertIsNone(self.repo.load().get('proposal'))

    def test_title_option_cannot_override_view_and_rejection_is_atomic(self):
        self.select_gates(9)
        self.app.advance()
        before = dump(self.repo.load())
        task_id = self.repo.pending()['id']
        invalid = options(self.app)
        invalid['options'][0]['value']['pov'] = '第一人称，由主角讲述。'
        candidate = receipt(self.app, invalid)
        for preview in (True, False):
            with self.subTest(preview=preview):
                with self.assertRaises(Exception) as caught:
                    self.app.submit(candidate, preview=preview)
                self.assertEqual(caught.exception.code, 'opening_option')
                self.assertEqual(caught.exception.details['unknown_fields'], ['pov'])
                self.assertEqual(caught.exception.details['allowed_fields'], ['title'])
                self.assertEqual(dump(self.repo.load()), before)
                self.assertEqual(self.repo.pending()['id'], task_id)
        self.choose_board(self.board())
        self.app.advance()
        self.app.submit(receipt(self.app, combined(self.app)))
        for _ in range(2):
            self.app.advance()
            self.app.submit(receipt(self.app, review_data(self.app)))
        self.app.advance()
        self.assertEqual(self.repo.load()['contract']['pov'], VALUES['pov']['pov'])

    def test_contract_alignment_rejects_cross_gate_fields_in_closed_choices(self):
        self.select_gates()
        state = self.repo.load()['creation']
        model_data = model(self.app)
        draft = contract_data(self.app, model_data)
        title = next(row for row in state['selections'] if row['gate'] == 'title')
        title['option']['value']['pov'] = '第一人称，由主角讲述。'
        for view in (draft['pov'], title['option']['value']['pov']):
            with self.subTest(view=view):
                candidate = {**draft, 'pov': view}
                self.assertCode('opening_option', creation.validate_contract, candidate, state, model_data)

    def test_the_tier_window_bounds_the_chapter_count_the_contract_may_choose(self):
        """A book shorter than its tier's window is caught as an alignment failure, not silently kept."""
        self.select_gates()
        state = self.repo.load()['creation']
        window = creation.selected(state)['scale']['chapter_window']
        model_data = model(self.app)
        draft = contract_data(self.app, model_data)
        draft['volumes'][-1]['end'] = window[0] - 5
        with self.assertRaises(Exception) as caught:
            creation.validate_contract(planning.validate_contract(draft), state, model_data)
        self.assertEqual(caught.exception.code, 'opening_alignment')
        self.assertIn('chapter_window', caught.exception.details)

    def test_explicit_run_after_world_delivery_enters_existing_writing_flow(self):
        self.world_ready()
        run = self.app.run(through=1, source='作者要求试写一章。')
        self.assertEqual(self.app.advance(owner=run['owner'])['task']['stage'], 'book_plan')
        with patch.object(support, 'response', writable_response):
            self.assertEqual(drive(self.app, run['owner'])['action'], 'target_reached')
        self.assertEqual(self.app.status()['accepted_chapters'], 1)
        self.assertTrue(self.app.audit()['ok'])

    def test_world_delivery_error_does_not_roll_back_activated_contract(self):
        self.world_ready()
        blocker = self.project / 'book.html'
        blocker.unlink()
        blocker.mkdir()
        final = self.app.advance()
        self.assertEqual(final['action'], 'world_ready')
        self.assertIn('world_view_error', final)
        self.assertEqual(self.repo.load()['creation']['phase'], 'ready')
        self.assertIsNotNone(self.repo.load()['contract'])
        blocker.rmdir()
        recovered = self.app.advance()
        self.assertTrue(Path(recovered['world_view']['html_path']).is_file())
        self.assertNotIn('world_view_error', recovered)

    def test_duplicate_options_and_inconsistent_mechanism_scope_are_rejected(self):
        self.app.advance()
        data = options(self.app)
        data['options'][1]['driver'] = data['options'][0]['driver']
        self.assertCode('opening_diversity', self.app.submit, receipt(self.app, data))
        self.app.submit(receipt(self.app, options(self.app)))          # 定位 accepted
        self.choose_board(self.board())                                # 定位
        self.choose_board(self.board())                                # 视角
        self.choose_board(self.board())                                # 体量（结构门，即时给定）
        task = self.app.advance()['task']
        self.assertEqual(task['stage'], 'opening_options')
        self.assertEqual(self.repo.pending()['input']['payload']['gate']['id'], 'world')
        data = options(self.app)
        data['options'][0]['value']['mechanism']['mode'] = 'bounded'
        self.assertCode('opening_option', self.app.submit, receipt(self.app, data))

    def test_importing_a_contract_is_allowed_before_the_first_gate_and_refused_after(self):
        command = [sys.executable, str(ROOT / 'scripts' / 'novel.py'), '--project', str(self.project)]
        example = str(ROOT / 'assets' / 'contract.example.json')
        early = subprocess.run(command + ['opening', '--file', example, '--source', '作者开书前给完整约定。'],
                               capture_output=True, text=True, encoding='utf-8', errors='replace')
        self.assertEqual(early.returncode, 0, early.stdout)
        self.assertTrue(json.loads(early.stdout)['staged'])
        self.assertIsNone(self.repo.load()['creation'])
        self.assertEqual(self.app.advance()['task']['stage'], 'contract_review')
        self.app.submit(receipt(self.app, review_data(self.app)))
        self.assertEqual(self.app.advance()['task']['stage'], 'book_plan')

    def test_importing_a_contract_after_a_gate_is_shown_is_refused(self):
        command = [sys.executable, str(ROOT / 'scripts' / 'novel.py'), '--project', str(self.project)]
        example = str(ROOT / 'assets' / 'contract.example.json')
        self.app.advance()
        late = subprocess.run(command + ['opening', '--file', example, '--source', '作者中途给完整约定。'],
                              capture_output=True, text=True, encoding='utf-8', errors='replace')
        self.assertEqual(late.returncode, 2)
        self.assertEqual(json.loads(late.stdout)['error'], 'creation')
        self.assertIsNotNone(self.repo.load()['creation'])
        self.assertIsNone(self.repo.load()['contract'])
        self.assertIsNotNone(self.repo.pending())
        # A newly initialised project stays importable right up to the first advance.
        other = Path(self.temp.name) / 'other'
        subprocess.run([sys.executable, str(ROOT / 'scripts' / 'novel.py'), '--project', str(other), 'init'],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
        ready = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'novel.py'), '--project', str(other),
                                'opening', '--file', example, '--source', '作者开书前给完整约定。'],
                               capture_output=True, text=True, encoding='utf-8', errors='replace')
        self.assertEqual(ready.returncode, 0, ready.stdout)

    def test_cli_init_without_contract_immediately_supports_guided_opening(self):
        path = Path(self.temp.name) / 'zero'
        command = [sys.executable, str(ROOT / 'scripts' / 'novel.py'), '--project', str(path)]
        init = subprocess.run(command + ['init'], capture_output=True, text=True, encoding='utf-8', errors='replace')
        self.assertEqual(init.returncode, 0, init.stderr)
        result = subprocess.run(command + ['advance'], capture_output=True, text=True, encoding='utf-8', errors='replace')
        self.assertEqual(json.loads(result.stdout)['task']['stage'], 'opening_options')


class StructuralGateTests(unittest.TestCase):
    """The length gate is arithmetic, so the engine answers it instead of spending a worker on it."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / 'book'
        self.repo = SQLiteRepository.initialize(self.project, workflow.preparing_book(guided=True))
        self.app = Application(self.repo)
        # Close the two creative gates in front of the structural one: 定位 and 视角.
        for _ in range(2):
            self.app.advance()
            self.app.submit(receipt(self.app, options(self.app)))
            self.app.opening_choice('A', self.app.advance()['board']['hash'], 'A')

    def tearDown(self):
        self.repo.close()
        self.temp.cleanup()

    def assertCode(self, code, fn, *args):
        with self.assertRaises(Exception) as caught:
            fn(*args)
        self.assertEqual(caught.exception.code, code)

    def test_scale_board_arrives_without_a_dispatch_and_offers_proven_tiers(self):
        handoff = self.app.advance()
        self.assertEqual(handoff['action'], 'await_choice')            # no worker, no waiting
        self.assertIsNone(self.repo.pending())
        board = handoff['board']
        self.assertEqual(board['gate']['id'], 'scale')
        self.assertTrue(board.get('system'))
        self.assertEqual(len(board['options']), 3)
        for option in board['options']:
            # a size ladder, not an invitation to invent numbers or scenes
            self.assertNotIn('pitch', option)
            self.assertNotIn('scene', option)
            tier = next(row for row in SCALE_TIERS if row['id'] == option['value']['tier'])
            for key in ('word_range', 'chapter_min', 'chapter_max', 'chapter_aim', 'volume_count', 'chapters', 'chapter_window'):
                self.assertEqual(option['value'][key], tier[key], key)
            self.assertTrue(option['premise'] and option['tradeoff'])
        # the board is stable across a plain re-advance
        self.assertEqual(self.app.advance()['board'], board)
        # a worker may not re-propose this gate
        task = self.app.advance()
        self.assertEqual(task['action'], 'await_choice')

    def test_regroup_slides_the_tier_window_instead_of_stalling(self):
        board = self.app.advance()['board']
        self.app.opening_regroup(board['hash'], '换一组，想看看更长的档位。')
        moved = self.app.advance()['board']
        self.assertNotEqual(moved['hash'], board['hash'])
        self.assertNotEqual([o['value']['tier'] for o in moved['options']],
                            [o['value']['tier'] for o in board['options']])
        self.assertEqual(len(self.repo.load()['creation']['rejections']), 1)
        self.app.opening_choice(moved['options'][0]['id'], moved['hash'], '选它。')
        self.assertEqual(self.repo.load()['creation']['selections'][-1]['gate'], 'scale')

    def test_tier_comparison_uses_the_full_ladder_in_every_window(self):
        seen = {}
        for _ in range(len(SCALE_TIERS) - 2):
            board = self.app.advance()['board']
            for option in board['options']:
                ident = option['value']['tier']
                index = next(i for i, tier in enumerate(SCALE_TIERS) if tier['id'] == ident)
                if index + 1 < len(SCALE_TIERS):
                    following = SCALE_TIERS[index + 1]
                    self.assertIn(following['name'], option['tradeoff'])
                    self.assertNotIn('最大', option['tradeoff'])
                else:
                    self.assertIn('最大', option['tradeoff'])
                if ident in seen:
                    self.assertEqual(option, seen[ident])
                seen[ident] = option
            self.app.opening_regroup(board['hash'], '换一组。')
        self.assertEqual(set(seen), {tier['id'] for tier in SCALE_TIERS})

    def test_a_worker_may_not_answer_the_structural_gate(self):
        state = self.repo.load()['creation']
        self.assertCode('opening_system', creation.offer, state, {'gate': 'scale', 'options': []})

    def test_every_tier_is_writable_under_the_contract_rules(self):
        """No tier may be offered unless a contract inside it passes the same rules the engine enforces."""
        state = creation.begin('工程夹具：逐档验证可写完性。')
        for tier in SCALE_TIERS:
            with self.subTest(tier=tier['id']):
                choices = {'scale': {k: copy.deepcopy(tier[k]) for k in
                                     ('word_range', 'chapter_min', 'chapter_max', 'chapter_aim', 'volume_count')}}
                choices['scale'].update(tier=tier['id'], chapters=tier['chapters'], chapter_window=list(tier['chapter_window']))
                creation.validate_value('scale', choices['scale'], 2, choices)
                # Every chapter count the window declares must survive the contract rules, not just
                # the shortest one: the band, the per-chapter aim and the declared maximum have to
                # hold together at each end of the window, or the ladder offers a size nobody can
                # actually write at that length.
                for total in range(tier['chapter_window'][0], tier['chapter_window'][1] + 1):
                    with self.subTest(tier=tier['id'], chapters=total):
                        raw = contract()
                        raw.update({key: copy.deepcopy(tier[key]) for key in
                                    ('word_range', 'chapter_min', 'chapter_max', 'chapter_aim')})
                        raw['volumes'] = [{'id': 'v' + str(i + 1), 'purpose': '查明来源并面对后果。',
                                           'end': total * (i + 1) // tier['volume_count']}
                                          for i in range(tier['volume_count'])]
                        checked = planning.validate_contract(raw)
                        self.assertEqual(checked['volumes'][-1]['end'], total)


class OpeningDecisionTests(unittest.TestCase):
    """Each author decision has exactly one home, and the ones added in opening/2 are author decisions."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = SQLiteRepository.initialize(Path(self.temp.name) / 'book', workflow.preparing_book(guided=True))
        self.app = Application(self.repo)

    def tearDown(self):
        self.repo.close()
        self.temp.cleanup()

    def assertCode(self, code, fn, *args):
        with self.assertRaises(Exception) as caught:
            fn(*args)
        self.assertEqual(caught.exception.code, code)

    def test_gate_set_asks_one_question_per_gate(self):
        self.assertEqual(creation.gate_ids(2), ('genre', 'pov', 'scale', 'world', 'protagonist',
                                                'relationships', 'engine', 'ending', 'voice', 'title'))
        self.assertEqual(creation.gate_ids(1), ('genre', 'scale', 'protagonist', 'engine', 'relationships', 'world', 'ending', 'voice'))
        self.assertEqual(self.app.status()['opening'], {'phase': 'choosing', 'selected_gates': 0, 'total_gates': 10, 'gate': 'genre'})
        self.assertEqual(len(alignment_for(2)) - len(alignment_for(1)), 3)   # tone, theme, pov
        order = creation.gate_ids(2)
        # the view has to be settled before any gate that shows sample scenes, and before the ending
        self.assertLess(order.index('pov'), order.index('world'))
        self.assertLess(order.index('pov'), order.index('ending'))
        # the setting constrains the people in it; the opposition comes from the relation set
        self.assertLess(order.index('world'), order.index('protagonist'))
        self.assertLess(order.index('relationships'), order.index('engine'))
        # the name is the most context-dependent decision, so it closes the opening
        self.assertEqual(order[-1], 'title')

    def test_every_gate_rejects_foreign_and_unknown_value_fields(self):
        scale = creation.intake(creation.begin(), {'scale': {'tier': 't3'}}, '作者选标准档。')
        values = {**copy.deepcopy(VALUES), 'scale': creation.selected(scale)['scale']}
        for gate, value in values.items():
            for key in ('unrecognized', 'pov' if gate != 'pov' else 'title'):
                with self.subTest(gate=gate, key=key):
                    invalid = {**value, key: '越权字段。'}
                    with self.assertRaises(Exception) as caught:
                        creation.validate_value(gate, invalid)
                    self.assertEqual(caught.exception.code, 'opening_option')
                    self.assertEqual(caught.exception.details['unknown_fields'], [key])
                    before = creation.begin()
                    self.assertCode('opening_option', creation.intake, before, {gate: invalid}, '作者要求。')
                    self.assertEqual(before, creation.begin())

    def test_relationships_cannot_be_an_empty_array(self):
        value = copy.deepcopy(VALUES['relationships'])
        value['relationships'] = []
        self.assertCode('opening_option', creation.validate_value, 'relationships', value, 2, {})

    def test_the_view_the_theme_and_the_title_are_author_decisions(self):
        ending = copy.deepcopy(VALUES['ending'])
        del ending['theme']
        self.assertCode('opening_option', creation.validate_value, 'ending', ending, 2, {})
        for gate, value in (('pov', {}), ('title', {'title': '  '})):
            self.assertCode('opening_option', creation.validate_value, gate, value, 2, {})
        for field in ('tone', 'theme', 'pov', 'title'):
            self.assertIn(field, alignment_for(2))
        for field in ('tone', 'theme', 'pov'):
            self.assertNotIn(field, alignment_for(1))

    def test_mechanism_scope_must_match_the_chosen_mechanism(self):
        value = copy.deepcopy(VALUES['world'])
        value['mechanism']['mode'] = 'bounded'
        value['mechanism']['principle'] = '有一条有限的超自然规则。'
        self.assertCode('opening_option', creation.validate_value, 'world', value, 2, {})
        value['allow_special_mechanism'] = True
        creation.validate_value('world', value, 2, {})

    def test_the_board_invariant_holds_across_the_walk_and_every_back_jump(self):
        """A structural gate must never wait for a worker, and no other gate may pre-empt one."""
        state = creation.begin('工程夹具：走完全程。')
        for step in range(10):
            state = shown(state)
            state = creation.pick(state, state['board']['options'][0]['id'], state['board']['hash'], 'A')
            structural = state['phase'] == 'choosing' and creation.current(state)['id'] in creation.SYSTEM_GATES[2]
            self.assertEqual(state['board'] is not None, structural, step)
            if structural:
                self.assertTrue(state['board']['system'])
        self.assertEqual(state['phase'], 'world')
        self.assertEqual(len(state['selections']), 10)
        for gate in creation.gate_ids(2):
            jumped = creation.back(copy.deepcopy(state), gate, '工程夹具：返回重选。')
            structural = creation.current(jumped)['id'] in creation.SYSTEM_GATES[2]
            self.assertEqual(jumped['board'] is not None, structural, gate)

    def test_regroup_cycles_every_ladder_window(self):
        """换一组 on the structural gate slides the ladder instead of stalling on one window."""
        state = shown(creation.begin('工程夹具：换档。'))
        state = creation.pick(state, state['board']['options'][0]['id'], state['board']['hash'], 'A')
        state = shown(state)
        state = creation.pick(state, state['board']['options'][0]['id'], state['board']['hash'], 'A')
        windows = []
        for _ in range(9):
            board = state['board']
            windows.append(tuple(option['value']['tier'] for option in board['options']))
            state = creation.regroup(state, board['hash'], '换一组。')
            self.assertIsNotNone(state['board'])
            self.assertNotEqual(state['board']['hash'], board['hash'])
        # Derived from the ladder so adding or removing a size class cannot silently
        # leave this list describing a ladder that no longer exists.
        ids = [row['id'] for row in SCALE_TIERS]
        expected = sorted({tuple(ids[start:start + SCALE_WINDOW])
                           for start in range(len(ids) - SCALE_WINDOW + 1)})
        self.assertEqual(sorted(set(windows)), expected)

    def test_intake_of_the_structural_gate_needs_only_a_tier(self):
        """The author names a size class; the proved arithmetic stays the engine's business."""
        values = {gate: copy.deepcopy(VALUES[gate]) for gate in creation.gate_ids(2) if gate != 'scale'}
        values['scale'] = {'tier': 't3'}
        state = creation.intake(creation.begin('作者一次给全。'), values, '作者一次给全。')
        self.assertEqual(state['phase'], 'world')
        chosen = creation.selected(state)['scale']
        tier = next(row for row in SCALE_TIERS if row['id'] == 't3')
        for key in ('word_range', 'chapter_min', 'chapter_max', 'chapter_aim', 'volume_count', 'chapters', 'chapter_window'):
            self.assertEqual(chosen[key], tier[key], key)
        # an unknown class is refused with the real ladder, and a hand-edited number is not silently fixed
        with self.assertRaises(Exception) as caught:
            creation.intake(creation.begin('x'), {'scale': {'tier': 't9'}}, 'x')
        self.assertEqual(caught.exception.code, 'opening_option')
        self.assertEqual(caught.exception.details['valid_tiers'], [row['id'] for row in SCALE_TIERS])
        with self.assertRaises(Exception) as caught:
            creation.intake(creation.begin('x'), {'scale': {'tier': 't3', 'chapters': 7}}, 'x')
        self.assertEqual(caught.exception.code, 'opening_option')

    def test_intake_uses_gate_ids_and_refuses_field_names(self):
        state = creation.begin()
        with self.assertRaises(Exception) as caught:
            # `theme` is a contract field, not a gate: the author states a decision, not a field name.
            creation.intake(state, {'theme': {'theme': '责任怎样在人之间传递。'}}, '我定了母题。')
        self.assertEqual(caught.exception.code, 'intake')
        self.assertIn('ending', caught.exception.details['valid_gates'])
        self.assertIn('pov', caught.exception.details['valid_gates'])
        # a partial requirement in its own gate is accepted, and the same field may not be re-decided
        accepted = creation.intake(state, {'ending': copy.deepcopy(VALUES['ending']),
                                           'title': copy.deepcopy(VALUES['title'])}, '作者已有终局、母题和书名。')
        self.assertEqual(creation.current(accepted)['id'], 'genre')
        self.assertEqual(creation.selected(accepted)['ending'], VALUES['ending'])
        self.assertEqual(creation.selected(accepted)['title'], VALUES['title'])
        self.assertCode('intake', creation.intake, accepted,
                        {'title': {'title': '改书名。'}}, '冲突')

    def test_view_checklist_exists_and_is_not_retroactive(self):
        from novel_ledger import context
        from novel_ledger.contracts import Job

        self.assertIn('pov_consistency', CHECK_SETS[POV_CHECKS_VERSION]['reader'])
        for version in (CHECKS_VERSION, EDITORIAL_VERSION):
            self.assertNotIn('pov_consistency', CHECK_SETS[version]['reader'])
        self.assertEqual(template('chapter_review', 1, {1: '正文'}, version=POV_CHECKS_VERSION)['reader']['checks'][-1]['id'],
                         'pov_consistency')
        # which list a project is judged by follows the contract, not the engine version
        for declared, expected in ((True, POV_CHECKS_VERSION), (False, EDITORIAL_VERSION)):
            raw = contract()
            raw.update(editorial_features=True, narrative_tracking=True)
            if declared:
                raw['pov'] = '第三人称限知。'
            book = workflow.new_book(raw)
            task = context.build(self.repo, book, Job('book_plan', 1, scope='book'))
            self.assertEqual(task['checks_version'], expected, declared)
        bare = workflow.new_book(contract())          # no editorial capability, no view
        self.assertEqual(context.build(self.repo, bare, Job('book_plan', 1, scope='book'))['checks_version'], CHECKS_VERSION)


if __name__ == '__main__':
    unittest.main()
