"""Synthetic engineering receipts. These are never literary judgments."""
import copy
import uuid
from novel_ledger.contracts import RESULT, digest
from novel_ledger.quality import template


def contract(chapters=2, volumes=1):
    return {'title': '夜班退件', 'genre': '都市生活',
            'reader_promise': '一个夜班工人查清退件来源并承担自己的选择。',
            'ending': '退件来源公开，工人承担违规开箱的后果。', 'world_premise': '一座仓库的夜班退件纠纷。',
            'story_engine': '核对退件来源，追查签字责任。', 'opposition': '主管担心调查影响考核。',
            'voice': '以动作、物件、对白和后果呈现夜班人情。', 'allow_special_mechanism': False,
            'style_traits': ['少重复解释。', '因果承接完整。'],
            'relationships': ['同事互相依赖，却各自担心承担责任。'],
            'protagonist_setup': {'id': 'shen', 'name': '沈桐', 'identity': '夜班工人',
                                  'desire': '查清责任。', 'limit': '不牵连无关同事。'},
            'world_rules': ['夜班退件必须登记负责人。'],
            'chapter_min': 12, 'chapter_max': 90, 'chapter_aim': 60, 'word_range': [12 * chapters, 200 * chapters],
            'volumes': [{'id': 'v' + str(i + 1), 'purpose': '查明来源并面对后果。', 'end': (i + 1) * chapters // volumes} for i in range(volumes)],
            'entities': [{'id': 'shen', 'name': '沈桐', 'kind': 'person'}],
            'initial_resources': [{'holder': 'shen', 'asset': '车费', 'unit': '元', 'quantity': '4'}]}


def node(ident, dependencies=()):
    return {'id': ident, 'line': 'main', 'cause': '有人退回了错误的箱子。', 'choice': '打开箱子核对。',
            'cost': '承担违规责任。', 'outcome': '找到退件来源。', 'disclosure': '先展示箱子，再披露来源。', 'depends_on': list(dependencies)}


def response(app, task_id=None, session=None, claim=None):
    task = app.repo.task(task_id) if task_id else app.repo.pending()
    work = task['input']
    stage, n = work['stage'], work['chapter']
    session = session or task['reviewer'] or 'test-' + uuid.uuid4().hex
    sources = app._sources(work)
    if work['blind'] and not task['first_read']:
        first = {'task_id': task['id'], 'input_hash': task['input_hash'], 'session': session,
                 'data': {'reads': [dict(chapter=k, desire='工人想查清来源。', obstacle='开箱违规。', change='发现新证据。', read_on_reason='他如何承担责任。') for k in sources]}}
        if claim:
            first['execution_claim'] = claim
        app.seal(first)
    data = template(stage, n, sources, work['obligations'])
    if stage in ('book_plan', 'volume_plan'):
        data = {'intent': '查明来源。', 'ending_conditions': '证据公开且后果落实。',
                'nodes': [node('book' if stage == 'book_plan' else work['scope'], () if stage == 'book_plan' else ('book',))]}
    elif stage == 'plan':
        book = app.repo.load()
        volume_id = next(v['id'] for v in book['contract']['volumes'] if v['first'] <= n <= v['end'])
        data = {'plans': [dict(chapter=k, goal='查清退件。', obstacle='开箱违规。', choice='核对封条。', cost='承担责任。', change='发现来源。', ending='追问签字人。', node_ids=['volume:' + volume_id], participants=['shen'], obligations=[]) for k in range(work['first'], work['last'] + 1)]}
        if book.get('world'):
            for plan in data['plans']:
                plan['world_refs'] = ['rules:r1', 'geography:g1']
    elif stage == 'profiles':
        data = {'profiles': [dict(entity=e, desire='查清责任。', fear='丢掉工作。', limit='不牵连同事。', voice='直接追问具体事。', knowledge_boundary='只知自己经手的货物。') for e in work['payload']['entities']]}
    elif stage in ('write', 'repair', 'redesign'):
        data = {'title': '封条' + str(n), 'prose': '次日，沈桐把退回的箱子放在桌上，指给主管看封条上的签字。他翻开夜班登记册，找出自己经手的那一页，又把空白的责任栏推到主管面前，要求先核对退件人的名字再开箱。',
                'summary': '沈桐要求核对退件来源。', 'self_check': '工程夹具：动作和证据均在场，事件由独立审稿重建。'}
    else:
        def fill(receipt):
            ref = {'chapter': next(iter(sources)), 'quote': next(iter(sources.values()))}
            receipt['verdict'] = 'pass'
            for row in receipt['checks']:
                row.update(result='pass', reason='工程夹具，仅验证字段和流转。', evidence=[ref])
                if 'challenge' in row:
                    row['challenge'] = dict(risk='工程反证样本。', disposition='satisfied', reason='仅用于协议测试。', evidence=ref)
            for row in receipt['obligations']:
                row.update(result='pass', reason='工程义务样本。', evidence=[ref])
        if stage == 'chapter_review':
            fill(data['facts'])
            fill(data['reader'])
            before = app.repo.load()['state']['clock']
            data['facts'].update(summary='沈桐核对退件来源。', elapsed_days=1,
                events=[{'op': 'clock', 'before': before, 'after': before + 1, 'evidence': {'chapter': n, 'quote': '次日'}}])
        else:
            fill(data)
            if stage in ('scope_review', 'scope_synthesis'):
                data['coverage'] = [{'chapter': k, 'reason': '工程覆盖样本。', 'evidence': {'chapter': k, 'quote': p}} for k, p in sources.items()]
    result = {'schema': RESULT, 'task_id': task['id'], 'input_hash': task['input_hash'], 'session': session, 'data': data}
    if claim:
        result['execution_claim'] = claim
    return result


def drive(app, owner=None, until=None):
    for _ in range(100):
        handoff = app.advance(owner=owner)
        if handoff['action'] == 'await_author':
            app.approve(handoff['prose_hash'], '工程夹具作者明确认可当前版本。', owner)
            continue
        if handoff['action'] != 'task_ready':
            return handoff
        if until and handoff['task']['stage'] == until:
            return handoff
        app.submit(response(app))
    raise AssertionError('工程流程没有在有限步骤内停止')
