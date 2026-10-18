"""Synthetic engineering receipts. These are never literary judgments."""
import uuid
from novel_ledger import context, scopes
from novel_ledger.contracts import RESULT
from novel_ledger.result_templates import template


def link_or_skip(case, link, target, target_is_directory=False):
    """Create a symbolic link, or report the host's missing capability as a skip.

    Windows only creates symbolic links with SeCreateSymbolicLinkPrivilege (Developer Mode or an
    elevated token). The alias and escape regressions that need one cannot be executed without it,
    and failing them would blame the engine for a host setting it does not own. Hard links need no
    privilege, so they are never guarded this way. The created link is returned for chaining.
    """
    try:
        link.symlink_to(target, target_is_directory=target_is_directory)
    except (OSError, NotImplementedError) as exc:
        case.skipTest('此宿主不能创建符号链接：' + str(exc))
    return link


def contract(chapters=2, volumes=1):
    return {'narrative_tracking': False, 'editorial_features': False, 'volume_outline': {}, 'title': '夜班退件', 'genre': '都市生活',
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


def outline_fixture(app, policy, anchor):
    """A valid per-chapter outline for one batch: refs off the real world, length off the policy."""
    model = app.repo.load().get('world')
    refs = [next(section + ':' + r['id'] for section, rows in model.items() if isinstance(rows, list) for r in rows)] if model else []
    sentence = '沈桐为核对封条追问经手人，主管以签字制度阻拦，他选择对照旧凭据并承担保管责任，发现笔迹矛盾后决定追查下一批退件。'
    synopsis = (sentence * (policy['words'] // len(sentence) + 3))
    from novel_ledger.contracts import han_count
    while han_count(synopsis) > policy['words']:
        synopsis = synopsis[:-1]
    return {'world_hash': policy['world_hash'],
            'chapters': [dict(chapter=k, synopsis=synopsis, world_refs=refs, node_ids=[anchor])
                         for k in range(policy['first'], policy['last'] + 1)]}


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
    data = template(stage, n, sources, work['obligations'], version=work.get('checks_version', 1),
                    payload=work['payload'], tracking=work.get('narrative_tracking', False))
    if stage in ('book_plan', 'volume_plan'):
        anchor = 'book' if stage == 'book_plan' else work['scope']
        data = {'intent': '查明来源。', 'ending_conditions': '证据公开且后果落实。',
                'nodes': [node(anchor, () if stage == 'book_plan' else ('book',))]}
        policy = work['payload'].get('volume_outline')
        if policy and 'volume_outline' in (work['payload'].get('also') or ()):
            # The merged single-volume dispatch: the skeleton receipt also carries the volume's
            # chapter outlines, the way the world receipt carries its contract.
            data.update(outline_fixture(app, policy, anchor))
        elif policy:
            model = app.repo.load().get('world')
            refs = [next(section + ':' + r['id'] for section, rows in model.items() if isinstance(rows, list) for r in rows)] if model else []
            data.update(world_hash=policy['world_hash'],
                        brainstorm=[dict(id='A', premise='从封条追问经手人，责任逐层扩散。', tradeoff='先承担追查责任。', world_refs=refs),
                                    dict(id='B', premise='先追查货物流向，再回查签字矛盾。', tradeoff='延迟确认经手人。', world_refs=refs)],
                        selected='A', selection_reason='工程样本：卷末责任与现有规则相接。')
    elif stage == 'volume_outline':
        book = app.repo.load()
        # A tier that merges the volume design into the book design has no volume-scope node, so
        # the outline references the node that actually exists instead of the scope it would expect.
        known = {node['id'] for design in book['designs'].values() for node in design.get('nodes', [])}
        anchor = work['scope'] if work['scope'] in known else 'book'
        data = outline_fixture(app, work['payload']['volume_outline'], anchor)
    elif stage == 'plan':
        book = app.repo.load()
        volume_id = next(v['id'] for v in book['contract']['volumes'] if v['first'] <= n <= v['end'])
        # A tier that merges the volume design into the book design has no volume-scope node, so
        # the plan references the node that actually exists instead of the scope it would expect.
        known = {node['id'] for design in book['designs'].values() for node in design.get('nodes', [])}
        anchor = 'volume:' + volume_id if 'volume:' + volume_id in known else 'book'
        data = {'plans': [dict(chapter=k, goal='查清退件。', obstacle='开箱违规。', choice='核对封条。', cost='承担责任。', change='发现来源。', ending='追问签字人。', node_ids=[anchor], participants=['shen'], obligations=[]) for k in range(work['first'], work['last'] + 1)]}
        if book.get('world'):
            for plan in data['plans']:
                plan['world_refs'] = ['rules:r1', 'geography:g1']
    elif stage == 'profiles':
        data = {'profiles': [dict(entity=e, desire='查清责任。', fear='丢掉工作。', limit='不牵连同事。', voice='直接追问具体事。', knowledge_boundary='只知自己经手的货物。') for e in work['payload']['entities']]}
    elif stage in ('write', 'repair', 'redesign'):
        # The old sentence set is kept verbatim (many tests quote fragments of it as evidence);
        # a short chapter-numbered marker between sentences makes every 25-character window
        # chapter-unique, so the engine's cross-chapter duplication check stays quiet for the
        # default fixture. Tests that want it loud copy a prior chapter's span deliberately.
        mark = '（记%d）' % n
        prose = ('次日，沈桐把退回的箱子放在桌上，' + mark
                 + '指给主管看封条上的签字。' + mark
                 + '他翻开夜班登记册，找出自己经手的那一页，' + mark
                 + '又把空白的责任栏推到主管面前，' + mark
                 + '要求先核对退件人的名字再开箱。')
        data = {'title': '封条' + str(n), 'prose': prose,
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
        if stage == 'revision_review':
            fill(data['reader'])
        elif stage == 'chapter_review':
            fill(data['facts'])
            fill(data['reader'])
            before = app.repo.load()['state']['clock']
            data['facts'].update(summary='沈桐核对退件来源。', elapsed_days=1,
                events=[{'op': 'clock', 'before': before, 'after': before + 1, 'evidence': {'chapter': n, 'quote': '次日'}}])
        else:
            fill(data)
            if stage in ('scope_review', 'scope_synthesis'):
                payload = work['payload']
                if payload.get('children'):
                    # The engine reuses accepted leaves across scopes (same span and chain), so
                    # children may be filed under a different review key: look them up the same
                    # way context.build does, through the merged report index.
                    spans = scopes.reports(app.repo.load())
                    data['coverage'] = [{'part_id': ident, 'reason': '工程覆盖样本。',
                                         'evidence': {'chapter': spans[ident]['last'], 'quote': sources[spans[ident]['last']]}}
                                        for ident in payload['children']]
                else:
                    data['coverage'] = [{'chapter': k, 'reason': '工程覆盖样本。', 'evidence': {'chapter': k, 'quote': p}} for k, p in sources.items()]
                if payload.get('review_tree') and isinstance(data.get('handoff'), dict):
                    sample = min(sources)
                    for field in data['handoff']:
                        if field != 'evidence':
                            data['handoff'][field] = '工程交接样本：块间因果、人物与披露的接缝说明。'
                    data['handoff']['evidence'] = [{'chapter': sample, 'quote': sources[sample]}]
    result = {'schema': RESULT, 'task_id': task['id'], 'input_hash': task['input_hash'], 'session': session, 'data': data}
    if claim:
        result['execution_claim'] = claim
    return result


def required_material(work):
    """The required records whose content is not already carried by an earlier required name.

    Every dispatch must satisfy this: a worker should never be charged twice for one fact, and two
    names holding byte-identical material also hide which one is authoritative.
    """
    seen, kept = set(), []
    for name in work['required']:
        ident = work['records'][name]
        if ident not in seen:
            seen.add(ident)
            kept.append(name)
    return kept


def check_dispatch(work):
    """Two invariants every frozen dispatch must satisfy, checked wherever a flow is driven."""
    if len(required_material(work)) != len(work['required']):
        raise AssertionError('必读记录里有内容完全相同的两份：' + ','.join(work['required']))
    undeclared = context.undeclared_material(work['stage'], work['required'])
    if undeclared:
        raise AssertionError('阶段 %s 的必读未在 context.STAGE_MATERIAL 里声明：%s'
                             % (work['stage'], ','.join(undeclared)))


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
        check_dispatch(app.repo.pending()['input'])
        app.submit(response(app))
    raise AssertionError('工程流程没有在有限步骤内停止')
