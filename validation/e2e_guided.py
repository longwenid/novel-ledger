"""端到端迷你项目（spec-v2 §8.3）：opening_options→world_model→volume_outline→chapter_outline→write。

    python validation/e2e_guided.py

这是一条**脚本驱动**的全链，不是人工点选：十个门里除系统门（scale）外，其余各门的方案由本脚本按
引擎自己声明的字段表（`creation.value_fields`）机械生成，世界模型按 `world.SECTIONS` 生成，
约定按 `contracts.CONTRACT_FIELDS.opening` 从作者已选项中投影出来。生成器只用引擎的公开表，
不抄任何实现者夹具的文本，因此它同时是对「门表/世界分区表/约定字段表」是否自洽的一次独立检查。

断言（§8.3 的四条）：
1. 全链无任何被删除的审查阶段派工；
2. 章纲状态链拒绝一个人为漂移样例；
3. write 的 drift_check 漏项被拒；
4. 通过后状态正确入账，并一路写到 target_reached。
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
                                    SCALE_TIERS, opening_source)
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


# ------------------------------------------------------------------ step one: the ten gates
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
    return '工程第%d案：%s 的具体选择。' % (index + 1, field)


HEADS = ('以凭据开', '以人情开', '以规章开')


def gate_receipt(app, task):
    """Three mechanically distinct options for whatever gate is pending."""
    version = creation.opening_version(app.repo.load().get('creation') or {})
    gate_id = task['payload']['gate']['id']
    options = []
    for index in range(3):
        fields = creation.value_fields(gate_id, version)
        option = {'id': 'ABC'[index],
                  'title': '第%d案：%s' % (index + 1, gate_id),
                  'premise': '第%d案把选择压在一件具体的事上，写明谁在什么处境下做什么。' % (index + 1),
                  'pitch': '先干活，再算账。' if index == 0 else '把账算清，再决定干不干。' if index == 1 else '照章办事，代价自付。',
                  'scene': ['夜班的仓库里，他把退回的箱子推到灯下，翻出封条上的签名。',
                            '凌晨的登记台前，他逐页核对自己经手的那一栏，把责任栏空着。'],
                  'driver': HEADS[index] + '推进：' + '核凭据' * (index + 1) + '。',
                  'tradeoff': '选它就要放弃第%d条更快但更冒险的路。' % (index + 1),
                  'fit_reason': '承接此前已选的方向，把推进落在一件可核对的物件上。',
                  'value': {field: filler(field, index) for field in fields}}
        options.append(option)
    result = response(app)
    result['data'] = {'gate': gate_id, 'options': options}
    return result


# --------------------------------------------------- step two: the world and the contract
def world_receipt(app):
    opening = app.repo.load()['creation']
    choices = creation.selected(opening)
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
    value['mechanisms'] = []
    return value


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
        if tamper is not None and not tampered and task['stage'] == on:
            tamper(result['data'], task)
            tampered = True
        try:
            app.submit(result)
        except Error as exc:
            return stages, 'rejected', exc
        if tampered:
            return stages, 'tampered-submitted', None
    return stages, 'limit-reached', None


def fresh(guided=True):
    temporary = tempfile.TemporaryDirectory()
    _TEMPORARIES.append(temporary)
    book = workflow.preparing_book(source='端到端脚本：从逐门开书跑到完稿。', guided=guided)
    repo = SQLiteRepository.initialize(Path(temporary.name) / 'book', book)
    _REPOS.append(repo)
    return repo, Application(repo)


def tamper_enter(data, task):
    data['chapters'][1]['enter'][0]['expected'] = 777
    return 'chapters[1].enter[0].expected -> 777'


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
    return {'action': action,
            'error': None if error is None else '%s: %s' % (error.code, error.message),
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
    stages, action, error = drive(app, tamper=tamper_enter, on='chapter_outline')
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


def main():
    report, failures = {}, 0
    for name, fn in (('全链自洽（逐门开书→完稿）', case_full_chain_clean),
                     ('章纲状态链拒绝人为漂移', case_chain_rejects_drift),
                     ('drift_check 漏项被拒', case_drift_check_coverage)):
        try:
            value = fn()
        except BaseException as exc:                    # noqa: BLE001 - reported, not swallowed
            value = {'error': '%s: %s' % (type(exc).__name__, exc),
                     'traceback': traceback.format_exc().splitlines()[-6:]}
        report[name] = value
        print('### ' + name)
        print(json.dumps(value, ensure_ascii=False, indent=1)[:1400])
    close_projects()
    clean = report['全链自洽（逐门开书→完稿）']
    chain = report['章纲状态链拒绝人为漂移']
    coverage = report['drift_check 漏项被拒']
    failures += 0 if (clean.get('action') == 'target_reached'
                      and clean.get('committed') == list(range(1, clean.get('target_chapters', 0) + 1))
                      and not clean.get('review_stages_dispatched')
                      and not clean.get('unknown_stages')
                      and clean.get('clock_settled') == clean.get('clock_declared')) else 1
    failures += 0 if chain.get('action') == 'rejected' else 1
    failures += 0 if coverage.get('criteria') else 1
    print('\n%s' % ('全部符合预期' if not failures else '%d 项不符合预期' % failures))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
