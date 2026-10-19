"""Zero-input choices and rich world flow, using synthetic engineering receipts.

These exercise opening/2, the gate set in force before the male-channel redesign: 10 gates, one
question each, the structural length gate answered by the engine. The project is pinned to
opening_version=2 on purpose — a project opened under an older protocol keeps its own gate set — so
this module stays the regression cover for every project already in flight. opening/1 is covered by
`test_opening_legacy.py`, and the current default by `test_opening.py`.

What follows the gates is the v2 pipeline: one `world_model` receipt that also carries the contract
it implies, then `volume_outline` (merged with `chapter_outline` on the tiers that declare
`merge_chapter_outline`), then the author's writing authorization. Nothing waits for a reviewer, so
there is no review receipt shape to fake here beyond the two outline declarations themselves.
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
from novel_ledger.contracts import (CONTRACT_ALIGNMENT, RESULT, SCALE_TIERS, SCALE_WINDOW,
                                    alignment_for, dump, han_count)
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


# Padding has to look like prose to the style proxies or it measures the fixture instead of the
# handoff: a pool of words repeats its 4-grams no matter how it is rotated, so the filler is built
# from a deterministic hash over a wide character space. It reads as word salad, which is what a
# length stub is; the tests that care about content use their own sentences.
_MASK = (1 << 64) - 1


def _mix(value):
    value = (value * 0x9E3779B97F4A7C15) & _MASK
    value ^= value >> 29
    value = (value * 0xBF58476D1CE4E5B9) & _MASK
    value ^= value >> 32
    value = (value * 0x94D049BB133111EB) & _MASK
    return value ^ (value >> 31)


def _filler(index, chapter):
    """One deterministic sentence with no repeated skeleton to measure."""
    seed = index * 101 + chapter * 10007
    return ''.join(chr(0x4E00 + _mix(seed + position * 1009) % 1800) for position in range(11)) + '。'


def writable_response(app, task_id=None, session=None, claim=None):
    """The engineering draft is a stub. A tier's chapter_min is a real length, so pad it to fit the
    contract it is judged against — the point under test is the handoff, not the stub's length."""
    result = response(app, task_id, session, claim)
    data = result.get('data')
    if isinstance(data, dict) and isinstance(data.get('prose'), str):
        need = (app.repo.load().get('contract') or {}).get('chapter_min', 0)
        chapter = app.repo.pending()['input']['chapter']
        index = 1
        while han_count(data['prose']) < need:
            data['prose'] += _filler(index, chapter)
            index += 1
    return result


class OpeningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / 'book'
        self.repo = SQLiteRepository.initialize(self.project, workflow.preparing_book(guided=True, opening_version=2))
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
        """Close the gates, hand in the world plus its contract, and return the next boundary.

        v2 has no review stages: the receipt is checked mechanically, the contract it carries is
        activated inside the same `advance`, and the next dispatch is the volume outline.
        """
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
        return self.app.advance()

    def to_outline_ready(self, outline=None, scale_tier=None):
        """Drive to the boundary where the outlines are handed over and no prose exists yet."""
        handoff = self.world_ready(outline=outline, scale_tier=scale_tier)
        while handoff['action'] == 'task_ready' and handoff['task']['stage'] in ('volume_outline', 'chapter_outline'):
            support.check_dispatch(self.repo.pending()['input'])
            self.app.submit(response(self.app))
            handoff = self.app.advance()
        self.assertEqual(handoff['action'], 'outline_ready')
        return handoff

    def test_the_combined_receipt_is_checked_mechanically_and_the_contract_activates(self):
        """No reviewer stands between the world draft and the contract it implies.

        The old flow paid a world review, then a separate contract review on the longer tiers, and
        only then reached the outline. v2 validates the one receipt mechanically, activates the
        contract inside the same `advance`, and dispatches the volume outline next.
        """
        self.select_gates()
        task = self.app.advance()['task']
        self.assertEqual(task['stage'], 'world_model')
        # the combined dispatch publishes both guides and a template carrying both artifacts
        self.assertIn('world.md', json.dumps(task['guides']))
        blanks = json.loads(Path(task['template_path']).read_text(encoding='utf-8'))['data']
        self.assertIn('contract', blanks)
        blank = blanks['contract']
        self.assertEqual(len(blank), len(planning.skeleton()))
        full = contract_data(self.app, model(self.app))
        # Fields the alignment checks read are compared key by key, so the template must carry them.
        self.assertEqual(sorted(set(full) & set(CONTRACT_ALIGNMENT) - set(blank)), [])
        self.app.submit(receipt(self.app, combined(self.app)))
        handoff = self.app.advance()
        self.assertEqual(handoff['task']['stage'], 'volume_outline')
        book = self.repo.load()
        self.assertIsNotNone(book['contract'])
        self.assertEqual(book['creation']['phase'], 'ready')
        self.assertIsNone(book.get('proposal'), 'v2 books no world or contract candidate to review')
        # The template is filled the way the engine's own alignment check reads it: an object filled
        # from the published blank passes both validators with no author field invented.
        filled = {**blank, **copy.deepcopy(full)}
        filled.update(planning_window=6)   # structural, not an author decision
        planning.validate_contract(filled)
        creation.validate_contract(planning.validate_contract(filled), self.repo.load()['creation'],
                                   self.repo.load()['world'])

    def test_the_first_dispatch_carries_the_brief_the_lens_and_trimmed_reads(self):
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
        # The gate and its lens arrive with the task envelope; `read` turns record hashes into values.
        view = json.loads(Path(task['input_path']).read_text(encoding='utf-8'))
        self.assertEqual(view['payload']['gate']['id'], 'genre')
        self.assertEqual(view['payload']['creative_lens'], creation.LENSES[0])
        read_material = self.app.read(task['task_id'])
        self.assertNotIn('payload', read_material, 'the envelope is not repeated by read')
        self.assertNotIn('brief', read_material)
        self.assertIn(creation.LENSES[0], view['brief'])
        self.assertIn('opening_choices', read_material['on_demand'])
        single = self.app.read(task['task_id'], 'opening_choices')
        self.assertEqual(single['records']['opening_choices']['value'], {})
        # A single-record read is that record (plus the hash index), not a second copy of the whole
        # dispatch view: the worker already holds brief/payload/policy in input.json.
        self.assertNotIn('brief', single)
        self.assertNotIn('payload', single)
        self.assertIn('on_demand', single)
        self.assertIn('on_demand', read_material)
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

    def test_option_quality_is_refused_at_the_gate_that_owns_it(self):
        """Self-justification, thin scenes, drivers that do not diverge, duplicate drivers and a
        mechanism scope that contradicts the chosen mechanism each name their own rejection."""
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
        duplicate = options(self.app)
        duplicate['options'][1]['driver'] = duplicate['options'][0]['driver']
        self.assertCode('opening_diversity', self.app.submit, receipt(self.app, duplicate))
        self.app.submit(receipt(self.app, options(self.app)))          # 定位 accepted
        self.choose_board(self.board())                                # 定位
        self.choose_board(self.board())                                # 视角
        self.choose_board(self.board())                                # 体量（结构门，即时给定）
        task = self.app.advance()['task']
        self.assertEqual(task['stage'], 'opening_options')
        self.assertEqual(self.repo.pending()['input']['payload']['gate']['id'], 'world')
        scoped = options(self.app)
        scoped['options'][0]['value']['mechanism']['mode'] = 'bounded'
        self.assertCode('opening_option', self.app.submit, receipt(self.app, scoped))

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

    def test_complete_choices_create_the_world_and_stop_before_prose(self):
        final = self.world_ready()
        # The world arrives with the volume-outline dispatch: activation renders the view, and v2
        # dispatches the next step instead of parking on a `world_ready` boundary.
        self.assertEqual(final['task']['stage'], 'volume_outline')
        self.assertTrue(Path(final['world_view']['html_path']).is_file())
        book = self.repo.load()
        self.assertEqual(set(world.SECTIONS), set(book['world']) - {'selection_hash', 'premise', 'story_capacity'})
        self.assertEqual(book['creation']['phase'], 'ready')
        self.assertEqual(len(book['creation']['selections']), 10)
        self.assertEqual(self.repo.headers('main'), [])
        self.assertIsNone(book.get('world_review'))
        view = final['world_view']
        self.assertEqual(Path(view['html_path']), (self.project / 'book.html').resolve())
        self.assertFalse((self.project / 'world.html').exists())
        page = Path(view['html_path']).read_text(encoding='utf-8')
        for section, fields in world.SECTIONS.items():
            self.assertIn(world.LABELS[section], page)
            for row in book['world'][section]:
                for field in fields:
                    self.assertIn(row[field], page)
        self.assertIn('读正文', page)
        self.assertIn('世界关联图', page)
        self.assertIn('历史时间线', page)
        artifact = json.loads(Path(view['json_path']).read_text(encoding='utf-8'))
        self.assertEqual(artifact['world'], book['world'])
        self.assertEqual(len(artifact['choices']), 10)
        self.assertTrue(self.app.audit()['ok'])

    def test_world_and_outlines_deliver_without_prose_and_the_writer_compares_against_them(self):
        """The v2 handover: volume outline, chapter outline, then a draft judged against that row."""
        policy = {'scope': 'all', 'words': 500, 'tolerance': 50}
        handoff = self.world_ready(outline=policy, scale_tier='t0')
        self.assertEqual(handoff['task']['stage'], 'volume_outline')
        first_volume = self.repo.load()['contract']['volumes'][0]
        # The merged tier answers both outline artifacts in one receipt; the blank form is one row
        # per volume plus each volume's chapters, all empty.
        blank = json.loads(Path(handoff['task']['template_path']).read_text(encoding='utf-8'))['data']
        self.assertEqual([row['id'] for row in blank['volumes']], [first_volume['id']])
        self.assertEqual(sorted(blank['chapters']), [first_volume['id']])
        task = self.repo.pending()
        self.assertIn('world_model', task['input']['required'])
        self.assertEqual(task['input']['payload']['volume_outline']['volume_ids'], [first_volume['id']])
        before = copy.deepcopy(self.repo.load()['state'])
        self.app.submit(response(self.app))
        ready = self.app.advance()
        self.assertEqual(ready['action'], 'outline_ready')
        self.assertEqual(ready['volumes'], [first_volume['id']])
        self.assertEqual(ready['planning_mode'], 'all')
        self.assertEqual(ready['coverage'],
                         [{'volume': first_volume['id'], 'first': first_volume['first'], 'last': first_volume['end']}])
        book = self.repo.load()
        self.assertEqual([c['chapter'] for c in book['chapter_outlines'][first_volume['id']]],
                         list(range(first_volume['first'], first_volume['end'] + 1)))
        self.assertEqual(book['volumes_outline'][first_volume['id']]['exit_state'],
                         support.VOLUME_EXIT)
        self.assertEqual(self.repo.headers('main'), [])
        self.assertIsNone(self.repo.pending())
        self.assertEqual(book['state'], before, 'outlines declare deltas; they do not settle them')
        page = Path(ready['world_view']['html_path']).read_text(encoding='utf-8')
        self.assertIn('卷纲与章纲', page)
        self.assertIn(support.VOLUME_CLIMAX, page)
        # The one writing dispatch carries this chapter's row, and the outline is the contract.
        run = self.app.run(through=1, source='试写一章。')
        write = drive(self.app, run['owner'], until='write')
        self.assertEqual(write['task']['stage'], 'write')
        writer = self.repo.pending()['input']
        self.assertEqual(writer['payload']['chapter_outline'],
                         self.repo.load()['plans']['1'])
        self.assertIn('chapter_outline', writer['required'])
        self.assertIn('volume_outline', writer['required'])

    def test_volume_outline_rejections_are_atomic_and_preserve_the_frozen_task(self):
        # One short volume keeps the word target the fixture can actually hit; the volume count, not
        # the tier's chapter band, is what these rejections exercise.
        handoff = self.world_ready(outline={'scope': 'all', 'words': 500, 'tolerance': 50}, scale_tier='t0')
        self.assertEqual(handoff['task']['stage'], 'volume_outline')
        valid = response(self.app)
        before = dump(self.repo.load())
        task_id = self.repo.pending()['id']
        variants = []
        short = copy.deepcopy(valid)
        short['data']['volumes'][0]['arc'] = '甲'
        variants.append(('design_drift', short, 'the volume is far below its word target'))
        missing = copy.deepcopy(valid)
        missing['data']['volumes'] = []
        variants.append(('volume_outline', missing, 'a batch that answers no volume at all'))
        wrong_id = copy.deepcopy(valid)
        wrong_id['data']['volumes'][0]['id'] = 'v99'
        variants.append(('volume_outline', wrong_id, 'a volume outside the frozen batch'))
        for code, candidate, why in variants:
            with self.subTest(code=code, why=why):
                self.assertCode(code, self.app.submit, candidate)
                self.assertEqual(dump(self.repo.load()), before)
                self.assertEqual(self.repo.pending()['id'], task_id)
        # `preview` runs the same checks without committing, so a rejected draft leaves nothing behind.
        self.assertCode('design_drift', self.app.submit, copy.deepcopy(short), True)
        self.assertEqual(dump(self.repo.load()), before)
        self.app.submit(response(self.app))

    def test_the_delivery_policy_decides_how_much_outline_arrives_before_prose(self):
        """An explicit `all` and the engine default both stop at outline_ready with no prose; only the
        declared coverage differs, and neither writes a word."""
        for label, outline in (('explicit_all', {'scope': 'all', 'words': 500, 'tolerance': 50}),
                               ('engine_default', 'default')):
            with self.subTest(policy=label):
                ready = self.to_outline_ready(outline=outline, scale_tier='t0')
                self.assertEqual(ready['action'], 'outline_ready')
                self.assertEqual(ready['planning_mode'], 'all')
                book = self.repo.load()
                volume = book['contract']['volumes'][0]
                self.assertEqual(ready['volumes'], [row['id'] for row in book['contract']['volumes']])
                self.assertEqual(ready['coverage'],
                                 [{'volume': volume['id'], 'first': volume['first'], 'last': volume['end']}])
                self.assertEqual(len(book['chapter_outlines'][volume['id']]),
                                 volume['end'] - volume['first'] + 1)
                for row_id, row in book['volumes_outline'].items():
                    self.assertEqual(row['id'], row_id)
                    self.assertTrue(row['exit_state'])
                    self.assertTrue(row['nodes'] and row['threads'])
                self.assertEqual(self.repo.headers('main'), [])
                self.assertIsNone(self.repo.pending())
                self.assertTrue(self.app.audit()['ok'])
                self.tearDown()
                self.setUp()

    def test_world_and_outlines_do_not_generate_canonical_events(self):
        """Design declarations are validated and stored; they never settle into the fact ledger."""
        self.select_gates()
        self.app.advance()
        self.app.submit(receipt(self.app, combined(self.app)))
        handoff = self.app.advance()
        self.assertEqual(handoff['task']['stage'], 'volume_outline')
        before = copy.deepcopy(self.repo.load()['state'])      # the contract's seeded state
        self.app.submit(response(self.app))
        self.app.advance()
        self.assertEqual(self.repo.load()['state'], before)
        self.assertEqual(self.repo.headers('main'), [])

    def test_back_after_choices_cancels_stale_world_task(self):
        self.select_gates()
        self.app.advance()
        old = receipt(self.app, model(self.app))
        self.app.opening_back('world', '重新选择世界方向。')
        self.assertCode('stale_task', self.app.submit, old)
        self.assertEqual(self.board()['gate']['id'], 'world')

    def test_world_receipt_rejections_name_their_own_rule(self):
        """An invented mechanism, a dangling world link and a stale selection hash each name their code."""
        self.select_gates()
        self.app.advance()
        injected = combined(self.app)
        injected['mechanisms'] = [{'id': 'magic', **{k: '外挂。' for k in world.SECTIONS['mechanisms']}, 'links': []}]
        self.assertCode('world_alignment', self.app.submit, receipt(self.app, injected))
        dangling = model(self.app)
        dangling['geography'][0]['links'] = ['economy:missing']
        self.assertCode('world_reference', self.app.submit, receipt(self.app, dangling))
        stale = model(self.app)
        stale['selection_hash'] = 'old'
        self.assertCode('world', self.app.submit, receipt(self.app, stale))

    def test_final_contract_cannot_change_chosen_voice_or_scale(self):
        self.select_gates()
        self.app.advance()
        # Each attempt drafts the world plus a contract that breaks one closed choice: the combined
        # dispatch must refuse the contract half without accepting the world half either.
        for mutate, label in ((lambda value: value.update(voice='另一个文风。'), 'voice'),
                              (lambda value: value.update(chapter_aim=value['chapter_min'] if value['chapter_aim'] != value['chapter_min']
                                                   else value['chapter_max']), 'chapter_aim'),
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
        self.app.advance()                     # the contract is active; the outline is next
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
        """A book shorter than its tier's window is an alignment failure, not a silent keep; every
        chapter count inside the window — down to the smallest tier's shortest — survives the rules.

        The ladder used to start at 34,000 characters, so the shape an author may ask for (a few
        chapters, ten thousand characters) had no size class: the contract could be amended to it,
        but the closing audit would then refuse the book as incompatible with its tier.
        """
        self.select_gates()
        state = self.repo.load()['creation']
        window = creation.selected(state)['scale']['chapter_window']
        model_data = model(self.app)
        draft = contract_data(self.app, model_data)
        draft['volumes'][-1]['end'] = max(1, window[0] - 1)
        with self.assertRaises(Exception) as caught:
            creation.validate_contract(planning.validate_contract(draft), state, model_data)
        self.assertEqual(caught.exception.code, 'opening_alignment')
        self.assertIn('chapter_window', caught.exception.details)

        self.tearDown()
        self.setUp()
        self.select_gates(scale_tier='t0')
        state = self.repo.load()['creation']
        tier = creation.selected(state)['scale']
        self.assertEqual(tier['tier'], 't0')
        self.assertLessEqual(tier['chapter_window'][0], 3)
        self.assertLessEqual(tier['word_range'][0], 10000)
        model_data = model(self.app)
        for total in (tier['chapter_window'][0], 3, tier['chapters']):
            with self.subTest(chapters=total):
                draft = contract_data(self.app, model_data)
                draft['volumes'][-1]['end'] = total
                creation.validate_contract(planning.validate_contract(draft), state, model_data)

    def test_explicit_run_after_world_delivery_enters_existing_writing_flow(self):
        handoff = self.world_ready()
        self.assertEqual(handoff['task']['stage'], 'volume_outline')   # the outlines come first
        run = self.app.run(through=1, source='作者要求试写一章。')
        with patch.object(support, 'response', writable_response):
            self.assertEqual(drive(self.app, run['owner'])['action'], 'target_reached')
        self.assertEqual(self.app.status()['accepted_chapters'], 1)
        self.assertTrue(self.app.audit()['ok'])

    def test_world_view_failure_does_not_roll_back_activated_contract(self):
        # Block the export path before the world receipt lands, so the activation advance is the one
        # that fails to render the view.
        self.select_gates()
        self.app.advance()
        blocker = self.project / 'book.html'
        if blocker.exists():
            blocker.unlink()
        blocker.mkdir()
        self.app.submit(receipt(self.app, combined(self.app)))
        handled = self.app.advance()
        self.assertEqual(handled['task']['stage'], 'volume_outline')
        self.assertIn('world_view_error', handled)
        self.assertEqual(self.repo.load()['creation']['phase'], 'ready')
        self.assertIsNotNone(self.repo.load()['contract'])
        # The failure is transient: once the path is usable the outline handover renders the view
        # again, so a book is never stranded by an export that could not be written.
        blocker.rmdir()
        self.app.submit(response(self.app))
        ready = self.app.advance()
        self.assertEqual(ready['action'], 'outline_ready')
        self.assertTrue(Path(ready['world_view']['html_path']).is_file())
        self.assertNotIn('world_view_error', ready)

    def test_importing_a_contract_is_allowed_before_the_first_gate_and_refused_after(self):
        command = [sys.executable, str(ROOT / 'scripts' / 'novel.py'), '--project', str(self.project)]
        example = str(ROOT / 'assets' / 'contract.example.json')
        early = subprocess.run(command + ['opening', '--file', example, '--source', '作者开书前给完整约定。'],
                               capture_output=True, text=True, encoding='utf-8', errors='replace')
        self.assertEqual(early.returncode, 0, early.stdout)
        self.assertTrue(json.loads(early.stdout)['staged'])
        self.assertIsNone(self.repo.load()['creation'])
        # v2 activates an imported contract on the engine's alignment check instead of dispatching a
        # contract review; the first dispatch of the book is the volume outline.
        task = self.app.advance()['task']
        self.assertEqual(task['stage'], 'volume_outline')
        self.assertIsNotNone(self.repo.load()['contract'])

        # A project that has already shown a gate refuses the import; a fresh init stays importable.
        with tempfile.TemporaryDirectory() as temporary:
            late_project = Path(temporary) / 'started'
            cli = [sys.executable, str(ROOT / 'scripts' / 'novel.py'), '--project', str(late_project)]
            subprocess.run(cli + ['init'], capture_output=True, text=True, encoding='utf-8', errors='replace')
            subprocess.run(cli + ['advance'], capture_output=True, text=True, encoding='utf-8', errors='replace')
            late = subprocess.run(cli + ['opening', '--file', example, '--source', '作者中途给完整约定。'],
                                  capture_output=True, text=True, encoding='utf-8', errors='replace')
            self.assertEqual(late.returncode, 2)
            self.assertEqual(json.loads(late.stdout)['error'], 'creation')
            repo = SQLiteRepository(late_project)
            try:
                self.assertIsNotNone(repo.load()['creation'])
                self.assertIsNone(repo.load()['contract'])
                self.assertIsNotNone(repo.pending())
            finally:
                repo.close()
            other = Path(temporary) / 'other'
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
        self.repo = SQLiteRepository.initialize(self.project, workflow.preparing_book(guided=True, opening_version=2))
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

    def test_regroup_slides_the_window_and_the_full_ladder_stays_comparable(self):
        """换一组 slides the tier window instead of stalling, every window offers the whole ladder's
        tradeoffs, and the cycle visits exactly the windows the ladder can form."""
        board = self.app.advance()['board']
        self.app.opening_regroup(board['hash'], '换一组，想看看更长的档位。')
        moved = self.app.advance()['board']
        self.assertNotEqual(moved['hash'], board['hash'])
        self.assertNotEqual([o['value']['tier'] for o in moved['options']],
                            [o['value']['tier'] for o in board['options']])
        self.assertEqual(len(self.repo.load()['creation']['rejections']), 1)
        self.app.opening_choice(moved['options'][0]['id'], moved['hash'], '选它。')
        self.assertEqual(self.repo.load()['creation']['selections'][-1]['gate'], 'scale')

        # From a fresh walk (setUp re-closes the two creative gates): regrouping the structural gate
        # cycles through comparable windows.
        self.tearDown()
        self.setUp()
        seen = {}
        windows = []
        for _ in range(len(SCALE_TIERS) - 2):
            board = self.app.advance()['board']
            windows.append(tuple(option['value']['tier'] for option in board['options']))
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
        # Derived from the ladder so adding or removing a size class cannot silently leave this
        # list describing a ladder that no longer exists.
        ids = [row['id'] for row in SCALE_TIERS]
        expected = sorted({tuple(ids[start:start + SCALE_WINDOW]) for start in range(len(ids) - SCALE_WINDOW + 1)})
        self.assertTrue(set(windows) <= set(expected))

    def test_a_worker_may_not_answer_the_structural_gate(self):
        state = self.repo.load()['creation']
        self.assertCode('opening_system', creation.offer, state, {'gate': 'scale', 'options': []})

    def test_every_tier_is_writable_under_the_contract_rules(self):
        """No tier may be offered unless a contract inside it passes the same rules the engine enforces."""
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
                        self.assertEqual(checked['word_range'],
                                         [total * tier['chapter_min'], total * tier['chapter_max']])


class OpeningDecisionTests(unittest.TestCase):
    """Each author decision has exactly one home, and the ones added in opening/2 are author decisions."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = SQLiteRepository.initialize(Path(self.temp.name) / 'book', workflow.preparing_book(guided=True, opening_version=2))
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
        scale = creation.intake(creation.begin(version=2), {'scale': {'tier': 't3'}}, '作者选标准档。')
        values = {**copy.deepcopy(VALUES), 'scale': creation.selected(scale)['scale']}
        for gate, value in values.items():
            for key in ('unrecognized', 'pov' if gate != 'pov' else 'title'):
                with self.subTest(gate=gate, key=key):
                    invalid = {**value, key: '越权字段。'}
                    with self.assertRaises(Exception) as caught:
                        creation.validate_value(gate, invalid, 2, {})
                    self.assertEqual(caught.exception.code, 'opening_option')
                    self.assertEqual(caught.exception.details['unknown_fields'], [key])
                    before = creation.begin(version=2)
                    self.assertCode('opening_option', creation.intake, before, {gate: invalid}, '作者要求。')
                    self.assertEqual(before, creation.begin(version=2))

    def test_gate_value_rules_refuse_hollow_or_unearned_decisions(self):
        """Empty relationship arrays, blank view/theme/title values and a mechanism scope the chosen
        mechanism did not earn are all `opening_option` refusals; tone/theme/pov/title are the
        author-decision fields opening/2 added on top of opening/1."""
        empty = copy.deepcopy(VALUES['relationships'])
        empty['relationships'] = []
        self.assertCode('opening_option', creation.validate_value, 'relationships', empty, 2, {})
        ending = copy.deepcopy(VALUES['ending'])
        del ending['theme']
        self.assertCode('opening_option', creation.validate_value, 'ending', ending, 2, {})
        for gate, value in (('pov', {}), ('title', {'title': '  '})):
            self.assertCode('opening_option', creation.validate_value, gate, value, 2, {})
        for field in ('tone', 'theme', 'pov', 'title'):
            self.assertIn(field, alignment_for(2))
        for field in ('tone', 'theme', 'pov'):
            self.assertNotIn(field, alignment_for(1))
        scoped = copy.deepcopy(VALUES['world'])
        scoped['mechanism']['mode'] = 'bounded'
        scoped['mechanism']['principle'] = '有一条有限的超自然规则。'
        self.assertCode('opening_option', creation.validate_value, 'world', scoped, 2, {})
        scoped['allow_special_mechanism'] = True
        creation.validate_value('world', scoped, 2, {})

    def test_the_board_invariant_holds_across_the_walk_and_every_back_jump(self):
        """A structural gate must never wait for a worker, and no other gate may pre-empt one."""
        state = creation.begin('工程夹具：走完全程。', version=2)
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

    def test_intake_uses_gate_ids_and_refuses_field_names(self):
        state = creation.begin(version=2)
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


if __name__ == '__main__':
    unittest.main()
