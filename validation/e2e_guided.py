"""端到端迷你项目（spec-v2 §8.3）：opening_options→world_model→volume_outline→chapter_outline→write。

    python validation/e2e_guided.py

这是一条**脚本驱动**的全链，不是人工点选：各门的方案由本脚本按引擎自己声明的字段表
（`creation.value_fields`）机械生成，门的数量与顺序由 `creation.gate_ids(opening_version)` 派生
（opening/4 的 11 门同样适用，系统门 `scale` 不派工），世界模型按 `world.SECTIONS` 生成，
约定按 `contracts.CONTRACT_FIELDS.opening` 从作者已选项中投影出来。生成器只用引擎的公开表，
不抄任何实现者夹具的文本，因此它同时是对「门表/世界分区表/约定字段表」是否自洽的一次独立检查。

断言（§8.3 的四条 + opening/4 的门集）：
1. 全链无任何被删除的审查阶段派工，派工的门数 = 门集 − 系统门；
2. `origin` 门（opening/4）四方向都通过校验、第五种说法被拒、opening/3 不接受该门；
3. 章纲状态链拒绝一个人为漂移样例；
4. write 的 drift_check 漏项被拒；
5. 通过后状态正确入账，并一路写到 target_reached。
"""
import copy
import json
import sys
import tempfile
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'tests')]

from novel_ledger.bootstrap import local_application as Application          # noqa: E402
from novel_ledger.contracts import (CONTRACT_FIELDS, DERIVED_FIELDS, Error,  # noqa: E402
                                    OPENING_VERSION, SCALE_TIERS, opening_source)
from novel_ledger.sqlite_store import SQLiteRepository                       # noqa: E402
from novel_ledger import creation, stages as stage_names, world, workflow    # noqa: E402
from support import contract, drift_check_fixture, long_prose, response      # noqa: E402

DELETED_STAGES = frozenset({
    'world_review', 'contract_review', 'design_review', 'outline_review', 'chapter_review',
    'book_plan', 'volume_plan', 'plan', 'profiles',
    'scope_review', 'scope_synthesis', 'revision_review', 'alignment_plan', 'alignment_review',
})

_TEMPORARIES, _REPOS = [], []


def close_projects():
    while _REPOS:
        try:
            _REPOS.pop().close()
        except Exception:                               # noqa: BLE001 - already closed is fine
            pass


# ------------------------------------------------------------------ step one: the gates
class EngineNotReady(RuntimeError):
    """The engine this build loads does not declare what the current opening version needs."""


def vocabulary():
    """opening/5's enums and numeric floors, read from `contracts` (the single source of truth).

    Nothing here is copied into this script on purpose: if a value is missing the harness must say
    "not landed yet" instead of inventing a second declaration that can drift from the engine's.
    """
    from novel_ledger import contracts
    names = ('WORLD_SCOPES', 'WORLD_GROWTHS', 'WORLD_TERMINALS', 'STANCES', 'DARK_SIDES',
             'COSMOLOGY_SCOPES')
    missing = [name for name in names if not hasattr(contracts, name)]
    if missing:
        raise EngineNotReady('contracts 尚未导出 opening/5 词表：%s' % ','.join(missing))
    floors = (getattr(contracts, 'DEFAULTS', {}) or {}).get('world_ladder')
    if not isinstance(floors, dict) or set(floors) != {'tier_min', 'stage_min', 'anchor_max_chapter'}:
        raise EngineNotReady('contracts.DEFAULTS["world_ladder"] 形状不符：%r' % (floors,))
    values = {name: tuple(getattr(contracts, name)) for name in names}
    values['floors'] = floors
    return values


def opening_ready(default_version=None):
    """(ready, reason) for the default guided opening this build would run."""
    version = default_version if default_version is not None else OPENING_VERSION
    if version < 5:
        return True, 'opening/%d 不需要 v5 词表' % version
    try:
        vocabulary()
    except EngineNotReady as exc:
        return False, str(exc)
    return True, 'ok'


# Names the world model has to carry verbatim (spec §5.4): the ladder stages become records, and the
# tier rows become `powers` rows. Kept distinct per index so both uniqueness checks have something
# to bite on.
TIER_NAMES = ('学徒位', '执事位', '主事位', '执令位', '镇守位', '掌界位')
STAGE_NAMES = ('青石巷', '落霞谷', '云中城', '界门关')
SCOPES_FOR = {2: ('局部', '一界'), 3: ('局部', '一域', '一界'), 4: ('局部', '一城', '一域', '一界')}
GROWTHS_FOR = {2: ('地盘', '文明'), 3: ('地盘', '势力', '文明'), 4: ('地盘', '势力', '规则', '文明')}


def _tier_row(tier_id):
    return next(row for row in SCALE_TIERS if row['id'] == tier_id)


def premise_value(index, vocab):
    """§4.1: four non-empty keys, `novelty`/`first_cause` ≥12 chars, the two enums exact."""
    return {'novelty': '本世界多出一条可反复使用的规则：核对旧凭据能换来一次问话权。',
            'first_cause': '第一推动力来自一次错误的退件登记，它先改变了资源分配的顺序。',
            'stance': vocab['STANCES'][index % len(vocab['STANCES'])],
            'dark_side': vocab['DARK_SIDES'][index % len(vocab['DARK_SIDES'])]}


def world_gate_value(index, choices, vocab):
    """§4.2: the v4 world value plus the reader-visible tier ladder and the hard currency."""
    tier = (choices.get('scale') or {}).get('tier') or 't0'
    need = vocab['floors']['tier_min'][tier]
    value = {field: filler(field, index) for field in creation.value_fields('world', 5)
             if field not in ('tiers', 'resource')}
    value['tiers'] = [{'name': TIER_NAMES[i],
                       'condition': '第%d阶的条件：核满十份凭据并有人作保。' % (i + 1),
                       'gain': '第%d阶所得：可调用本阶的登记权限。' % (i + 1),
                       'cost': '第%d阶的代价：每调用一次要担一份责任。' % (i + 1),
                       'limit': '第%d阶的上限：只在本仓库的夜班生效。' % (i + 1)}
                      for i in range(need)]
    value['resource'] = {'name': '灵石', 'source': '夜班退件里回收的旧凭据可兑出灵石。',
                         'allocator': '由值班主管按登记顺序分配。'}
    return value


def ladder_value(index, choices, vocab):
    """§4.3: opening/terminal/unchanged plus a monotone stage table that the world must mirror."""
    tier = (choices.get('scale') or {}).get('tier') or 't0'
    need = vocab['floors']['stage_min'][tier]
    scopes = SCOPES_FOR.get(need) or tuple(vocab['WORLD_SCOPES'][i] for i in range(min(need, len(vocab['WORLD_SCOPES']))))
    growths = GROWTHS_FOR.get(need) or tuple(vocab['WORLD_GROWTHS'][i % len(vocab['WORLD_GROWTHS'])]
                                             for i in range(need))
    if any(scope not in vocab['WORLD_SCOPES'] for scope in scopes):
        raise EngineNotReady('本档位需要的 scope 不在 contracts.WORLD_SCOPES 里：%s' % (scopes,))
    if any(growth not in vocab['WORLD_GROWTHS'] for growth in growths):
        raise EngineNotReady('本档位需要的 growth 不在 contracts.WORLD_GROWTHS 里：%s' % (growths,))
    rows = [{'stage': STAGE_NAMES[i], 'scope': scopes[i], 'growth': growths[i],
             'new_rule': '第%d级的规则：跨过它就能看见上一层谁在分配。' % (i + 1),
             'cost': '第%d级的代价：升上去要交出旧身份的一部分。' % (i + 1)}
            for i in range(need)]
    terminal = '文明' if '文明' in growths else ('体系' if '规则' in growths
                                            else ('势力' if '势力' in growths else '局部'))
    if terminal != '文明' and need >= 3:
        raise EngineNotReady('terminal 与层级表的推导结果不符：%s' % terminal)
    return {'scale': {'opening': '第一章读者能看见的边界：一条夜班巷子与它背后的登记制度。',
                      'terminal': terminal,
                      'unchanged': '跨卷不变的上层结构：登记制度与它背后的分配者始终在场。'},
            'ladder': rows}


def payoff_value(index, choices, vocab):
    """§4.4: the v3 payoff value plus the theme anchor (deadline is a plain number)."""
    tier = (choices.get('scale') or {}).get('tier') or 't0'
    ceiling = min(vocab['floors']['anchor_max_chapter'], _tier_row(tier)['chapter_window'][1])
    value = {field: filler(field, index) for field in creation.value_fields('payoff', 5)
             if field != 'anchor'}
    value['anchor'] = {'deliverable': '第 %d 章前必须让读者看见：那次退件登记的代价由谁承担。' % min(12, ceiling),
                       'deadline_chapter': str(min(12, ceiling))}
    return value


def value_for(gate_id, version, index, choices, vocab=None):
    """The value for one gate: v5's four reshaped gates, otherwise the generic field filler."""
    if version >= 5:
        vocab = vocab or vocabulary()
        if gate_id == 'premise':
            return premise_value(index, vocab)
        if gate_id == 'world':
            return world_gate_value(index, choices, vocab)
        if gate_id == 'ladder':
            return ladder_value(index, choices, vocab)
        if gate_id == 'payoff':
            return payoff_value(index, choices, vocab)
    return {field: filler(field, index) for field in creation.value_fields(gate_id, version)}


def filler(field, index):
    """One gate value, from the field's own name. Only the engine's declared field list drives it."""
    if field == 'id':
        return 'shen'
    if field == 'name':
        return '沈桐'
    if field == 'genre':
        return '都市生活'
    if field == 'tier':
        return 't0'
    if field in ('word_range', 'chapter_min', 'chapter_max', 'chapter_aim', 'volume_count',
                 'chapters', 'chapter_window'):
        return copy.deepcopy(next(row for row in SCALE_TIERS if row['id'] == 't0')[field])
    if field == 'mechanism':
        return {'mode': 'none', 'principle': '只有现实规章与人情，没有超自然力量。',
                'cost': '行动要付出真实的职业代价。', 'limits': []}
    if field == 'allow_special_mechanism':
        return False
    if field == 'red_lines':
        return []
    if field == 'relationships':
        return ['同事互相依赖，却各自担心承担责任。']
    if field == 'style_traits':
        return ['少重复解释。', '因果承接完整。']
    if field == 'plan':
        return {'ways': ['脱困', '拿到关键线索', '公开责任'], 'cadence': '三到五章一个小兑现，章末留钩。',
                'hooks': '卷中转折放旧凭据暴露矛盾；卷尾高潮放来源公开并承担后果。'}
    if field == 'limits':
        return []
    if field == 'family':
        # opening/4's origin gate: `family` is a four-way enum, not free text. Rotation covers three
        # of them inside one gate; `origin_families_are_validated()` checks all four plus a refusal.
        return ORIGIN_FAMILIES[index % len(ORIGIN_FAMILIES)]
    return '工程第%d案：%s 的具体选择。' % (index + 1, field)


HEADS = ('以凭据开', '以人情开', '以规章开')
# opening/4 inserted `origin` right after `genre`; the gate set (and therefore the dispatch count) is
# derived from the engine's own tables, never hard-coded, so a later protocol version keeps working.
ORIGIN_FAMILIES = ('魂穿', '身穿', '本土', '其他')


def gate_receipt(app, task):
    """Three mechanically distinct options for whatever gate is pending."""
    opening = app.repo.load().get('creation') or {}
    version = creation.opening_version(opening)
    choices = creation.selected(opening)
    vocab = vocabulary() if version >= 5 else None
    gate_id = task['payload']['gate']['id']
    options = []
    for index in range(3):
        option = {'id': 'ABC'[index],
                  'title': '第%d案：%s' % (index + 1, gate_id),
                  'premise': '第%d案把选择压在一件具体的事上，写明谁在什么处境下做什么。' % (index + 1),
                  'pitch': '先干活，再算账。' if index == 0 else '把账算清，再决定干不干。' if index == 1 else '照章办事，代价自付。',
                  'scene': ['夜班的仓库里，他把退回的箱子推到灯下，翻出封条上的签名。',
                            '凌晨的登记台前，他逐页核对自己经手的那一栏，把责任栏空着。'],
                  'driver': HEADS[index] + '推进：' + '核凭据' * (index + 1) + '。',
                  'tradeoff': '选它就要放弃第%d条更快但更冒险的路。' % (index + 1),
                  'fit_reason': '承接此前已选的方向，把推进落在一件可核对的物件上。',
                  'value': value_for(gate_id, version, index, choices, vocab)}
        options.append(option)
    result = response(app)
    result['data'] = {'gate': gate_id, 'options': options}
    return result


# --------------------------------------------------- step two: the world and the contract
def world_receipt(app):
    """The world model, including opening/5's three verbatim bindings (spec §5.4).

    A v5 project declares its tier ladder, its hard currency and its 格局 stages in the gates, and the
    world model has to carry each of them as a record with the *same* name; a world that merely says
    something similar is rejected. The receipt builds exactly that, so the three failure paths stay in
    the engine's hands (the tests cover the negative side).
    """
    opening = app.repo.load()['creation']
    choices = creation.selected(opening)
    version = creation.opening_version(opening)
    value = {'selection_hash': opening['selection_hash'],
             'premise': choices['world']['world_premise'],
             'story_capacity': '退件责任、人情与制度足以承载一次来源核对和一场责任追查。'}
    for section, fields in world.SECTIONS.items():
        ident = 'shen' if section == 'characters' else {'rules': 'r1', 'geography': 'g1'}.get(section, section + '1')
        row = {field: '工程世界：%s 的%s。' % (section, field) for field in fields}
        row.update(id=ident, links=[])
        value[section] = [row]
    value['characters'][0].update(name=choices['protagonist']['name'],
                                  desire=choices['protagonist']['desire'],
                                  limit=choices['protagonist']['limit'])
    value['rules'][0]['principle'] = '夜班退件必须登记负责人。'
    if version >= 5:
        _apply_v5_bindings(value, choices)
    value['mechanisms'] = []
    return value


def _apply_v5_bindings(value, choices):
    """The declared tier rows / currency / stage names, repeated verbatim in the world model."""
    declared_tiers = (choices.get('world') or {}).get('tiers') or []
    if declared_tiers:
        value['powers'] = [{'id': 'power-%d' % (index + 1), **tier, 'links': []}
                           for index, tier in enumerate(declared_tiers)]
    resource = (choices.get('world') or {}).get('resource') or {}
    if resource:
        row = {field: '工程世界：economy 的%s。' % field for field in world.SECTIONS['economy']}
        row.update(id='economy1', links=[], resource=resource['name'],
                   distribution='由%s按登记顺序发放。' % resource['allocator'])
        value['economy'] = [row]
    stages = [row.get('stage') for row in ((choices.get('ladder') or {}).get('ladder') or [])
              if isinstance(row, dict) and row.get('stage')]
    if stages:
        # Each stage must exist as a record name in geography/cosmology/factions/powers; geography is
        # the one section every tier requires, so the stage places live there.
        rows = value.get('geography') or []
        for index, stage in enumerate(stages):
            row = {field: '工程世界：格局第%d级的%s。' % (index + 1, field)
                   for field in world.SECTIONS['geography']}
            row.update(id='stage-%d' % (index + 1), name=stage, links=[])
            rows.append(row)
        value['geography'] = rows
    scopes = {row.get('scope') for row in ((choices.get('ladder') or {}).get('ladder') or [])
              if isinstance(row, dict)}
    from novel_ledger import contracts
    cosmology_needed = bool(scopes & set(getattr(contracts, 'COSMOLOGY_SCOPES', ())))
    if cosmology_needed and 'cosmology' in world.SECTIONS:
        row = {field: '工程世界：空间与位面的%s。' % field for field in world.SECTIONS['cosmology']}
        row.update(id='cosmology1', links=[])
        value['cosmology'] = [row]


def opening_contract(app, model):
    """The contract the combined dispatch writes: selections projected through CONTRACT_FIELDS."""
    book = app.repo.load()
    opening = book['creation']
    version = creation.opening_version(opening)
    choices = creation.selected(opening)
    scale = choices['scale']
    total, volume_count = scale['chapters'], scale['volume_count']
    raw = contract(chapters=total, volumes=volume_count)
    for row in CONTRACT_FIELDS:
        if row.get('since', 1) > version or row['key'] in DERIVED_FIELDS:
            continue
        source = opening_source(row, version)
        if not source:
            continue
        gate, key = source
        if gate not in choices:
            continue
        raw[row['key']] = copy.deepcopy(choices[gate] if key is None else choices[gate].get(key))
    protagonist = choices['protagonist']
    geography = model['geography']
    raw.update(word_range=copy.deepcopy(scale['word_range']),
               chapter_min=scale['chapter_min'], chapter_max=scale['chapter_max'],
               chapter_aim=scale['chapter_aim'],
               world_premise=choices['world']['world_premise'],
               red_lines=copy.deepcopy(choices['world']['red_lines']),
               world_rules=[row['principle'] for row in model['rules']],
               entities=[{'id': protagonist['id'], 'name': protagonist['name'], 'kind': 'person'}],
               initial_resources=[{'holder': protagonist['id'], 'asset': '车费', 'unit': '元', 'quantity': '12'}],
               # `facts.seed` registers places from the contract itself, so the two ids the world
               # declares for geography are copied here under the same names (spec §4.3 grounds the
               # chapter outline's `places` in the world's geography).
               places=[{'id': row['id'], 'name': row['name']} for row in geography],
               placements={protagonist['id']: geography[0]['id']},
               # scope=all is the author asking for the whole chain on paper before the first word;
               # `scope=volume` would stop at `outline_ready` by design (workflow.choose's
               # `opening_only` branch), which is a boundary, not the end of the chain.
               chapter_outline={'scope': 'all', 'words': 150, 'tolerance': 60},
               volumes=[{'id': 'v' + str(i + 1), 'purpose': '查明来源并面对后果。',
                         'end': total * (i + 1) // volume_count} for i in range(volume_count)])
    return raw


# ------------------------------------------------------------------------- the driver
def prose_for(app, chapter, data):
    """Pad the engineering stub to the contract's chapter minimum.

    Every 25-character window has to be chapter-unique or the engine's cross-chapter duplication
    lint fires on the second chapter (and it is right to): `support.long_prose` is the shared
    fixture built for exactly that, so the padding is not what this script is testing.
    """
    from novel_ledger.contracts import han_count
    need = (app.repo.load().get('contract') or {}).get('chapter_min', 0)
    if han_count(data.get('prose') or '') < need:
        data['prose'] = long_prose(chapter)
    return data


def drive(app, tamper=None, on=None, tier='t1', through=None, limit=400):
    """Advance to a boundary, answering every dispatch with a mechanically built receipt."""
    stages, tampered, error, owner = [], False, None, None
    for _ in range(limit):
        handoff = app.advance(owner=owner)
        action = handoff['action']
        if action == 'await_choice':
            board = handoff['board']
            if board.get('system') or (board.get('gate') or {}).get('id') == 'scale':
                # A size class is named, not invented: the ladder slides to the tier the author says.
                app.opening_tier(tier, '端到端脚本：作者指定 %s 档。' % tier, owner)
            else:
                app.opening_choice(board['options'][0]['id'], board['hash'], '端到端脚本：作者选第一案。', owner)
            continue
        if action == 'await_author':
            app.approve(handoff['prose_hash'], '端到端脚本：作者认可首章。', owner)
            continue
        if action == 'outline_ready':
            # The guided opening hands the outlines over before prose is authorized (by design);
            # the author's own `run` is what authorizes the draft.
            end = (through if through is not None
                   else app.repo.load()['contract']['volumes'][-1]['end'])
            owner = app.run(through=end, source='端到端脚本：作者授权开写。')['owner']
            continue
        if action != 'task_ready':
            return stages, action, error
        task = app.repo.pending()['input']
        stages.append(task['stage'])
        if task['stage'] == 'opening_options':
            result = gate_receipt(app, task)
        elif task['stage'] == 'world_model' and 'opening_contract' in tuple((task.get('payload') or {}).get('also') or ()):
            model = world_receipt(app)
            result = response(app)
            result['data'] = {**model, 'contract': opening_contract(app, model)}
        else:
            result = response(app)
            if task['stage'] in ('write', 'repair', 'redesign'):
                # Pad first, then rebuild the self-comparison: every evidence quote has to be a
                # verbatim fragment of the prose actually being submitted, and the fixture quotes
                # whatever string it was handed.
                prose_for(app, task['chapter'], result['data'])
                result['data']['drift_check'] = drift_check_fixture(app, task, result['data']['prose'])
        wanted = (on,) if isinstance(on, str) else tuple(on or ())
        if tamper is not None and not tampered and task['stage'] in wanted:
            tamper(result['data'], task)
            tampered = True
        try:
            app.submit(result)
        except Error as exc:
            return stages, 'rejected', exc
        if tampered:
            return stages, 'tampered-submitted', None
    return stages, 'limit-reached', None


def fresh(guided=True, version=None):
    temporary = tempfile.TemporaryDirectory()
    _TEMPORARIES.append(temporary)
    book = workflow.preparing_book(source='端到端脚本：从逐门开书跑到完稿。', guided=guided,
                                   **({'opening_version': version} if version else {}))
    repo = SQLiteRepository.initialize(Path(temporary.name) / 'book', book)
    _REPOS.append(repo)
    return repo, Application(repo)


def _chapter_rows(data):
    """The chapter rows of whichever receipt shape carries them.

    A merged tier (t0/t1) returns the volumes and their chapters from the *volume* dispatch, with the
    rows grouped by volume id; a separate dispatch returns them as one flat list. A tamper that only
    knew the flat shape silently did nothing on a merged tier (the run then completed and the case
    read as "not rejected"), so both shapes are handled here.
    """
    chapters = data.get('chapters')
    if isinstance(chapters, dict):
        return next((rows for rows in chapters.values() if rows), [])
    return chapters or []


def tamper_enter(data, task):
    rows = _chapter_rows(data)
    rows[1]['enter'][0]['expected'] = 777
    return 'chapters[1].enter[0].expected -> 777（%s）' % (
        '合并回执按卷分组' if isinstance(data.get('chapters'), dict) else '独立章纲派工')


def tamper_missing_item(data, task):
    data['drift_check']['items'].pop()
    return 'drift_check.items.pop()'


def case_full_chain_clean():
    repo, app = fresh()
    stages, action, error = drive(app)
    book = repo.load()
    headers = [row['n'] for row in repo.headers('main')]
    chapters = (book['contract']['volumes'][-1]['end'])
    settled = book['state']['clock']
    declared = sum((book['plans'][str(row['n'])].get('clock') or {}).get('advance_days') or 0 for row in repo.headers('main'))
    # Gate expectations come from the engine's own tables: a protocol version that inserts a gate
    # (opening/4 added `origin`) changes the count, and this script must not need editing for it.
    creation_state = book.get('creation') or {}
    version = creation.opening_version(creation_state)
    gate_ids = creation.gate_ids(version)
    system = tuple(creation.SYSTEM_GATES.get(version, ()))
    return {'action': action,
            'error': None if error is None else '%s: %s' % (error.code, error.message),
            'opening_version': version,
            'gate_count': len(gate_ids),
            'gates': list(gate_ids),
            'system_gates': list(system),
            'expected_opening_options_dispatches': len(gate_ids) - len(system),
            'opening_options_dispatches': stages.count('opening_options'),
            'first_stages': stages[:6],
            'review_stages_dispatched': sorted(set(stages) & DELETED_STAGES),
            'unknown_stages': sorted(set(stages) - set(stage_names.STAGES)),
            'target_chapters': chapters, 'committed': headers,
            'clock_settled': settled, 'clock_declared': declared,
            'design_drift': len(book.get('design_drift') or []),
            'workbench_versions': len(book.get('understanding', {}).get('versions') or [])}


def case_chain_rejects_drift():
    repo, app = fresh()
    stages, action, error = drive(app, tamper=tamper_enter,
                                  on=('chapter_outline', 'volume_outline'))
    rows = ((error.details or {}).get('findings') if error is not None else None) or []
    return {'action': action,
            'error': None if error is None else '%s: %s' % (error.code, error.message),
            'criteria': sorted({row.get('criterion') for row in rows}),
            'findings': rows[:2]}


def case_drift_check_coverage():
    repo, app = fresh()
    stages, action, error = drive(app, tamper=tamper_missing_item, on='write')
    book = repo.load()
    findings = (book.get('draft') or {}).get('findings') or []
    return {'action': action,
            'error': None if error is None else '%s: %s' % (error.code, error.message),
            'criteria': sorted({row.get('criterion') for row in findings}),
            'findings': findings[:2],
            'repair_stage': (book.get('draft') or {}).get('stage')}


def case_origin_gate_forms():
    """opening/4: the `origin` gate's four directions are all valid, a fifth is refused, and the gate
    sits right after `genre` in the version's own gate list."""
    problems = []
    version = 4
    ids = creation.gate_ids(version)
    if 'origin' not in ids:
        problems.append('opening/4 的门集里没有 origin：%s' % list(ids))
    elif ids.index('origin') != 1 or ids[0] != 'genre':
        problems.append('origin 不在 genre 之后：%s' % list(ids))
    accepted = {}
    for family in ORIGIN_FAMILIES:
        value = {'family': family, 'arrival': '工程第 1 案：arrival 的具体选择。',
                 'cost': '工程第 1 案：cost 的具体选择。'}
        try:
            creation.validate_value('origin', value, version)
            accepted[family] = 'ok'
        except Error as exc:
            accepted[family] = '%s: %s' % (exc.code, exc.message)
    refused = None
    try:
        creation.validate_value('origin', {'family': '穿越', 'arrival': 'x', 'cost': 'y'}, version)
        refused = 'ACCEPTED'
    except Error as exc:
        refused = exc.code
    if any(row != 'ok' for row in accepted.values()):
        problems.append('有方向未被接受：%s' % accepted)
    if refused == 'ACCEPTED':
        problems.append('第五种说法（穿越）没有被拒')
    # A gate set that has no origin must not accept one either (v3 keeps its own shape).
    v3_refused = None
    try:
        creation.validate_value('origin', {'family': '魂穿', 'arrival': 'x', 'cost': 'y'}, 3)
        v3_refused = 'ACCEPTED'
    except Error as exc:
        v3_refused = exc.code
    if v3_refused == 'ACCEPTED':
        problems.append('opening/3 的门集不该接受 origin')
    return {'kind': 'accepted' if not problems else 'contradicted',
            'gate_ids_v4': list(ids), 'accepted': accepted, 'fifth_form': refused,
            'v3_origin': v3_refused, 'problems': problems,
            'fragment': 'creation.validate_value("origin", …, 4) 的四方向 + 第五种说法'}


def case_v3_project_unaffected():
    """An in-flight opening/3 project keeps its own ten-gate set: no `origin`, nine dispatches."""
    repo, app = fresh(version=3)
    stages, action, error = drive(app)
    book = repo.load()
    version = creation.opening_version(book.get('creation') or {})
    ids = creation.gate_ids(version)
    system = tuple(creation.SYSTEM_GATES.get(version, ()))
    problems = []
    if version != 3:
        problems.append('旧项目没有被当作 opening/3：version=%s' % version)
    if len(ids) != 10 or 'origin' in ids:
        problems.append('opening/3 的门集被改动：%s' % list(ids))
    if stages.count('opening_options') != len(ids) - len(system):
        problems.append('门派工数不符：%d（应 %d）' % (stages.count('opening_options'),
                                                      len(ids) - len(system)))
    if action != 'target_reached' or error is not None:
        problems.append('opening/3 项目没有跑完：%s %s' % (action, error))
    return {'kind': 'accepted' if not problems else 'contradicted',
            'opening_version': version, 'gate_count': len(ids), 'gates': list(ids),
            'opening_options_dispatches': stages.count('opening_options'),
            'action': action,
            'error': None if error is None else '%s: %s' % (error.code, error.message),
            'committed': [row['n'] for row in repo.headers('main')],
            'problems': problems,
            'fragment': 'workflow.preparing_book(guided=True, opening_version=3)'}


def case_v5_gate_values_shape():
    """opening/5 §4: the four reshaped gates' values pass the engine's own validator, and §5.3's
    declared sections follow from what the gates declare."""
    problems = []
    vocab = vocabulary()
    version = 5
    ids = creation.gate_ids(version)
    if OPENING_VERSION != 5:
        problems.append('默认开书版本不是 5：OPENING_VERSION=%s' % OPENING_VERSION)
    if len(ids) != 13 or 'premise' not in ids or 'ladder' not in ids:
        problems.append('v5 门集不是 13 门或缺少新门：%s' % list(ids))
    else:
        if ids.index('premise') != 1:
            problems.append('premise 不在 genre 之后：%s' % list(ids))
        if ids.index('world') > ids.index('ladder'):
            problems.append('world 门必须排在 ladder 之前：%s' % list(ids))
    choices = {'scale': {'tier': 't1'}}
    accepted, refused = {}, {}
    for gate in ('premise', 'world', 'ladder', 'payoff'):
        for index in range(3):
            value = value_for(gate, version, index, choices, vocab)
            try:
                creation.validate_value(gate, value, version, choices)
                accepted.setdefault(gate, []).append(index)
            except Error as exc:
                refused.setdefault(gate, []).append('%d:%s' % (index, exc.message))
    if refused:
        problems.append('我方生成的 v5 值未通过引擎校验：%s' % refused)
    # The scale gate is a system gate: the tier must exist before world/ladder read their floors.
    tier = _tier_row('t1')
    world_value = value_for('world', version, 0, choices, vocab)
    ladder = value_for('ladder', version, 0, choices, vocab)
    if len(world_value.get('tiers') or []) < vocab['floors']['tier_min']['t1']:
        problems.append('world.tiers 少于本档位下限')
    if len(ladder.get('ladder') or []) < vocab['floors']['stage_min']['t1']:
        problems.append('ladder 层数少于本档位下限')
    ceiling = min(vocab['floors']['anchor_max_chapter'], tier['chapter_window'][1])
    anchor = value_for('payoff', version, 0, choices, vocab)['anchor']
    if not anchor['deadline_chapter'].isdigit() or not 1 <= int(anchor['deadline_chapter']) <= ceiling:
        problems.append('anchor.deadline_chapter 不是纯数字或超出上限：%r（上限 %d）'
                        % (anchor['deadline_chapter'], ceiling))
    # §5.3: a ladder that reaches a cosmology scope must declare the cosmology section.
    declared = None
    if hasattr(world, 'declared_sections'):
        declared = list(world.declared_sections({'world': world_value, 'ladder': ladder}))
        if 'powers' not in declared:
            problems.append('声明了 tiers 却没声明 powers 领域：%s' % declared)
        if 'cosmology' not in declared:
            problems.append('阶梯触到宇宙尺度却没声明 cosmology 领域：%s（scopes=%s）'
                            % (declared, [row['scope'] for row in ladder['ladder']]))
        sections = list(world.required_sections('t1', {'world': world_value, 'ladder': ladder}))
        if not {'powers', 'cosmology'} <= set(sections):
            problems.append('required_sections 没有并入门里声明的领域：%s' % sections)
    else:
        problems.append('world.declared_sections 尚未落地（opening/5 §5.3）')
    return {'kind': 'accepted' if not problems else 'contradicted',
            'gate_ids_v5': list(ids), 'accepted_gates': accepted,
            'world_tiers': len(world_value.get('tiers') or []),
            'ladder_stages': [row['stage'] for row in ladder['ladder']],
            'ladder_scopes': [row['scope'] for row in ladder['ladder']],
            'terminal': ladder['scale']['terminal'],
            'anchor': anchor, 'declared_sections': declared, 'problems': problems,
            'fragment': 'value_for(premise|world|ladder|payoff, 5) + world.declared_sections'}


CASES = (
    # (name, fn, needs the default version's vocabulary)
    ('全链自洽（逐门开书→完稿）', case_full_chain_clean, True),
    ('opening/5 四门值形状与领域声明', case_v5_gate_values_shape, True),
    ('opening/4 origin 门四方向', case_origin_gate_forms, False),
    ('opening/3 旧项目不受影响', case_v3_project_unaffected, False),
    ('章纲状态链拒绝人为漂移', case_chain_rejects_drift, True),
    ('drift_check 漏项被拒', case_drift_check_coverage, True),
)


def main():
    report, failures, blocked = {}, 0, 0
    ready, why = opening_ready()
    for name, fn, needs_v5 in CASES:
        if needs_v5 and not ready:
            report[name] = {'kind': 'blocked', 'blocked': why}
            blocked += 1
        else:
            try:
                report[name] = fn()
            except BaseException as exc:                # noqa: BLE001 - reported, not swallowed
                report[name] = {'error': '%s: %s' % (type(exc).__name__, exc),
                                'traceback': traceback.format_exc().splitlines()[-6:]}
        print('### ' + name)
        print(json.dumps(report[name], ensure_ascii=False, indent=1)[:1400])
    close_projects()
    if blocked:
        print('\n引擎未就绪，%d 条用例记 blocked（未作判定）：%s' % (blocked, why))
        print('说明：opening/5 词表（contracts.WORLD_SCOPES 等）落地后重跑即可。')
        return 2
    clean = report['全链自洽（逐门开书→完稿）']
    shapes = report['opening/5 四门值形状与领域声明']
    origin = report['opening/4 origin 门四方向']
    legacy = report['opening/3 旧项目不受影响']
    chain = report['章纲状态链拒绝人为漂移']
    coverage = report['drift_check 漏项被拒']
    failures += 0 if (clean.get('action') == 'target_reached'
                      and clean.get('committed') == list(range(1, clean.get('target_chapters', 0) + 1))
                      and not clean.get('review_stages_dispatched')
                      and not clean.get('unknown_stages')
                      and clean.get('clock_settled') == clean.get('clock_declared')
                      and clean.get('opening_options_dispatches') == clean.get('expected_opening_options_dispatches')) else 1
    failures += 0 if shapes.get('kind') == 'accepted' else 1
    failures += 0 if origin.get('kind') == 'accepted' else 1
    failures += 0 if legacy.get('kind') == 'accepted' else 1
    failures += 0 if chain.get('action') == 'rejected' else 1
    failures += 0 if coverage.get('criteria') else 1
    print('\n%s' % ('全部符合预期' if not failures else '%d 项不符合预期' % failures))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
