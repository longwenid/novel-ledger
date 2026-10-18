"""Author constraints, rolling plans and profiles. All functions are pure."""
from __future__ import annotations

import copy
import math
from . import contracts
from .contracts import (CONTRACT_FIELDS, DEFAULT_NAME_CHARS, DEFAULT_TERMS,
                        POLICY_FIELDS, contract_errors, contract_skeleton, digest, han_count, require, text)
from .entities import register as register_entity
from . import narrative, craft


def resolve_policy(policy):
    """The book-level lexical policy is the only authority; this is the one resolver."""
    value = policy if isinstance(policy, dict) else {}
    resolved = {'forbidden_terms': list(DEFAULT_TERMS), 'forbidden_name_chars': list(DEFAULT_NAME_CHARS)}
    for key in POLICY_FIELDS:
        if key in value:
            resolved[key] = copy.deepcopy(value[key])
    require(all(isinstance(resolved[k], list) and all(text(s) for s in resolved[k]) for k in POLICY_FIELDS),
            'lexical_policy', '字面规则须为字符串数组。')
    return resolved


def active_policy(versions):
    """Resolve only the active version; unrelated book state is never an input."""
    versions = versions or []
    require(isinstance(versions, list) and versions, 'lexical_policy', '项目缺少字面规则记录。')
    latest = versions[-1]
    require(isinstance(latest, dict), 'lexical_policy', '字面规则版本须为对象。')
    return resolve_policy(latest.get('policy', {}))


def policy_of(book):
    """Compatibility query for callers holding a transaction aggregate."""
    return active_policy(book.get('lexical_policy'))


def check_text(value, policy, names=False):
    resolved = resolve_policy(policy)
    words = resolved['forbidden_name_chars'] if names else resolved['forbidden_terms']
    require(not any(w in value for w in words), 'literal_policy', '内容违反作者当前字面约定。',
            {'found': [w for w in words if w in value], 'recover': '修改当前候选；作者明确改规则时走 lexical 命令保存原话。'})


def _walk(node, path=''):
    """Yield (path, text) for every string in a nested result payload."""
    if isinstance(node, str):
        yield path, node
    elif isinstance(node, dict):
        for key, value in node.items():
            yield from _walk(value, path + '.' + str(key) if path else str(key))
    elif isinstance(node, list):
        for item in node:
            yield from _walk(item, path)


def enforce(policy, stage, data):
    """Enforce the rules declared for this stage, and nothing else.

    contracts.ENFORCEMENT is the single declaration of coverage: the same table drives this loop
    and the `policy` block handed to the worker, so declared and enforced scope cannot drift.
    """
    scope = contracts.ENFORCEMENT.get(stage)
    if not scope:
        return
    resolved = resolve_policy(policy)
    hits = {}
    for path, value in _walk(data):
        field = path.rsplit('.', 1)[-1] if path else ''
        if field in scope.get('terms', ()) or path.split('.')[0] in scope.get('terms', ()):
            found = [w for w in resolved['forbidden_terms'] if w in value]
            if found:
                hits.setdefault('forbidden_terms', []).append({'field': path, 'found': found})
        if field in scope.get('names', ()):
            found = [w for w in resolved['forbidden_name_chars'] if w in value]
            if found:
                hits.setdefault('forbidden_name_chars', []).append({'field': path, 'found': found})
    require(not hits, 'literal_policy', '内容违反作者当前字面约定（' + stage + '）。',
            {'violations': hits, 'stage': stage,
             'recover': '按 literal_policy 修正上述字段后重提；作者改规则用 lexical 命令保存原话。'})


def enforcement_scope(stage):
    """Human-readable coverage for the dispatch material: which fields are inspected here."""
    stages = (stage,) if isinstance(stage, str) else tuple(stage)
    terms, names, covered = [], [], []
    for name in stages:
        scope = contracts.ENFORCEMENT.get(name)
        if not scope:
            continue
        covered.append(name)
        terms.extend(field for field in scope.get('terms', ()) if field not in terms)
        names.extend(field for field in scope.get('names', ()) if field not in names)
    if not covered:
        return {'terms': [], 'names': [], 'stages': [], 'note': '本阶段不检查字面约定。'}
    return {'stages': covered, 'terms': terms, 'names': names, 'note': contracts.POLICY_NOTE}


def policy_material(versions, stage):
    """Task material built from policy versions and requested stages only."""
    stages = (stage,) if isinstance(stage, str) else tuple(stage)
    versions = versions or []
    latest = versions[-1] if versions else {'version': 1, 'policy': resolve_policy({}), 'source': '内置默认'}
    resolved = resolve_policy(latest.get('policy', {}))
    return {'version': latest.get('version', 1), 'source': latest.get('source', ''),
            'forbidden_terms': resolved['forbidden_terms'],
            'forbidden_name_chars': resolved['forbidden_name_chars'],
            'scope': enforcement_scope(stages),
            'editable': '作者改规则：novel.py lexical --file 规则.json --source 原话（逐版留档，开书阶段即生效）。'}


def skeleton():
    """Blank contract-shaped object: the delivery template for the opening contract stage."""
    return contract_skeleton()


def check_contract_names(contract, policy):
    """Name rules are enforced at every gate that can introduce an entity name."""
    for item in contract.get('entities', []):
        for name in [item.get('name', '')] + list(item.get('aliases', [])):
            check_text(name, policy, names=True)


def validate_plan_names(plan, policy):
    """New entities declared by a chapter plan are names too, so the project policy applies."""
    for item in plan.get('new_entities', []):
        for name in [item.get('name', '')] + list(item.get('aliases', [])):
            check_text(name, policy, names=True)


def validate_contract(raw):
    contract = copy.deepcopy(raw) if isinstance(raw, dict) else raw
    if isinstance(contract, dict):
        # Defaults are structural, not content: they may never invent an author decision. An empty
        # container is a shape the validator has to see; an empty string is a decision nobody made,
        # so an optional text field stays absent rather than being written in as blank.
        for row in CONTRACT_FIELDS:
            if row['key'] not in contract and row['default'] not in ('', None):
                contract[row['key']] = copy.deepcopy(row['default'])
    complaints = contract_errors(contract)
    require(not complaints, 'contract', '约定结构不成立：' + '；'.join(complaints[:6]))
    contract.setdefault('chapter_aim', min(contract['chapter_max'], max(contract['chapter_min'], 3500)))
    require(all(type(contract[k]) is int and contract[k] > 0
                for k in ('chapter_min', 'chapter_max', 'chapter_aim', 'planning_window', 'review_interval', 'review_chunk')),
            'contract', '篇幅、窗口和复审间隔须为正整数。')
    require(contract.get('verification') in ('full', 'fast'), 'contract',
            'verification 须为 full（默认全档：固定间隔块审+分块范围审）或 fast（快速档：跳过固定间隔块审，基础项目范围审合并为不超过 12 章的大块；章审与事实核验不降档）。')
    require(contract['chapter_min'] <= contract['chapter_aim'] <= contract['chapter_max'], 'contract', '章目标须在上下限之间。')
    require(type(contract['narrative_tracking']) is bool and type(contract['review_fanout']) is int and 2 <= contract['review_fanout'] <= 8,
            'contract', 'narrative_tracking 须为布尔值；review_fanout 须为 2～8，限制单次综合材料。')
    require(type(contract['editorial_features']) is bool and (not contract['editorial_features'] or contract['narrative_tracking']),
            'contract', 'editorial_features 需要 narrative_tracking；基础模式可明确设 false。')
    policy = contract['volume_outline']
    require(not policy or set(policy) == {'scope', 'words', 'tolerance'} and policy.get('scope') in ('rolling', 'current', 'all')
            and type(policy.get('words')) is int and policy['words'] > 0
            and type(policy.get('tolerance')) is int and 0 <= policy['tolerance'] < policy['words'],
            'volume_outline', 'volume_outline 为 {} 或 {scope:rolling|current|all,words:正整数,tolerance:非负整数且小于 words}。')
    volumes = contract['volumes']
    seen, last = set(), 0
    for volume in volumes:
        require(isinstance(volume, dict) and text(volume.get('id')) and text(volume.get('purpose'))
                and volume['id'] not in seen, 'volume', '卷需要唯一 id 和职责。')
        seen.add(volume['id'])
        if 'end' not in volume:
            require(type(volume.get('word_budget')) is int and volume['word_budget'] > 0, 'volume', '卷需要 end 或 word_budget。')
            volume['end'] = last + max(1, math.ceil(volume['word_budget'] / contract['chapter_aim']))
        require(type(volume['end']) is int and volume['end'] > last, 'volume', '卷末章号须严格递增。')
        volume['first'] = last + 1
        last = volume['end']
    # The total band is a projection of the two things the author actually decides: how many
    # chapters the book has, and the per-chapter range the size class proves writable. Deriving it
    # here replaces the arithmetic that checked a hand-entered band against the count — arithmetic
    # that could still be internally inconsistent, and did not survive a new size class.
    contract['word_range'] = [last * contract['chapter_min'], last * contract['chapter_max']]
    for key in ('world_rules', 'red_lines', 'arcs'):
        require(isinstance(contract[key], list) and all(text(v) for v in contract[key]), 'contract', key + ' 须为字符串数组。')
    return contract



def volume_for(contract, chapter):
    return next((v for v in contract['volumes'] if v['first'] <= chapter <= v['end']), None)


def outline_policy(contract, volume, model=None):
    policy = contract.get('volume_outline') or {}
    if not policy:
        return None
    return {**copy.deepcopy(policy), 'first': volume['first'], 'last': volume['end'],
            'world_hash': digest(model) if model else None}


def outline_refs(row, model):
    known_world = {section + ':' + item['id'] for section, rows in (model or {}).items()
                   if isinstance(rows, list) for item in rows if isinstance(item, dict) and 'id' in item}
    values = row.get('world_refs')
    require(isinstance(values, list) and (values or not model) and all(text(r) and r in known_world for r in values)
            and len(values) == len(set(values)), 'outline_world', '脑暴方案和每章卷纲须引用有效 world_refs；已有世界模型时不能为空。')


def validate_outline(data, policy, model, known_nodes):
    """Coverage and provenance are mechanical; a separate reviewer judges concise causality."""
    require(data.get('world_hash') == policy['world_hash'], 'outline_world', '卷纲须绑定本任务的准确世界模型版本。')
    options = data.get('brainstorm')
    require(isinstance(options, list) and 2 <= len(options) <= 3 and all(isinstance(o, dict)
            and all(text(o.get(k)) for k in ('id', 'premise', 'tradeoff')) for o in options),
            'outline_brainstorm', '卷纲先给 2～3 个不同推进方式的脑暴方案：id/premise/tradeoff/world_refs。')
    require(len({o['id'] for o in options}) == len(options) and len({o['premise'].strip() for o in options}) == len(options)
            and data.get('selected') in {o['id'] for o in options} and text(data.get('selection_reason')),
            'outline_brainstorm', '脑暴方案 ID 和推进说明不能重复；selected 引用选用方案并给 selection_reason。')
    for option in options:
        outline_refs(option, model)
    if policy.get('brainstorm_only'):
        require(not data.get('chapters'), 'outline_coverage', '先交卷内脑暴与节点；逐章说明由后续有界批次生成。')
    else:
        validate_chapter_outlines(data, policy, model, known_nodes)


def validate_chapter_outlines(data, policy, model, known_nodes):
    require(isinstance(data, dict) and data.get('world_hash') == policy['world_hash'], 'outline_world', '逐章卷纲须绑定本任务的准确世界模型版本。')
    chapters = data.get('chapters')
    require(isinstance(chapters, list) and all(isinstance(c, dict) and type(c.get('chapter')) is int for c in chapters)
            and [c['chapter'] for c in chapters] == list(range(policy['first'], policy['last'] + 1)),
            'outline_coverage', '逐章卷纲须按顺序完整覆盖当前冻结批次；后续范围由卷纲策略决定。',
            {'first': policy['first'], 'last': policy['last'], 'recover': '补齐本批次的每章情节推进说明。'})
    for chapter in chapters:
        prose = chapter.get('synopsis')
        require(text(prose), 'outline_length', '每章卷纲须提供 synopsis 情节推进说明。')
        length = han_count(prose)
        require(policy['words'] - policy['tolerance'] <= length <= policy['words'] + policy['tolerance'],
                'outline_length', '逐章卷纲篇幅不在目标范围内。',
                {'chapter': chapter['chapter'], 'actual': length, 'aim': policy['words'],
                 'minimum': policy['words'] - policy['tolerance'], 'maximum': policy['words'] + policy['tolerance'],
                 'recover': '用具体因果、选择、代价与变化补足或压缩，不重复设定、口号或正文描写凑字。'})
        outline_refs(chapter, model)
        ids = chapter.get('node_ids')
        require(isinstance(ids, list) and ids and all(text(n) and n in known_nodes for n in ids)
                and len(ids) == len(set(ids)), 'outline_nodes', '逐章卷纲须引用有效且不重复的设计 node_ids。')


def validate_design(data, known=(), tracking=False, known_threads=(), outline=None, model=None):
    require(isinstance(data, dict) and text(data.get('intent')) and text(data.get('ending_conditions')),
            'design', '设计需要 intent 和终局/卷末成立条件 ending_conditions。')
    nodes = data.get('nodes')
    require(isinstance(nodes, list) and nodes, 'design', '设计需要完整因果节点。')
    identifiers = []
    for node in nodes:
        require(isinstance(node, dict) and all(text(node.get(k)) for k in ('id', 'line', 'cause', 'choice', 'cost', 'outcome', 'disclosure')),
                'design', '节点需要 id/line/cause/choice/cost/outcome/disclosure。')
        require(isinstance(node.get('depends_on'), list) and all(text(n) for n in node['depends_on']), 'design', 'depends_on 须为节点 ID 数组。')
        identifiers.append(node['id'])
        effects, criteria = node.get('effects', []), node.get('criteria', [])
        require(isinstance(effects, list) and all(isinstance(e, dict) and text(e.get('id')) and text(e.get('text')) for e in effects)
                and len({e['id'] for e in effects}) == len(effects), 'design', 'effects 为唯一 id/text 数组。')
        require(isinstance(criteria, list) and all(isinstance(c, dict) and text(c.get('id')) and text(c.get('text'))
                and type(c.get('required', True)) is bool and isinstance(c.get('effects'), list)
                and c['effects'] and all(text(e) and e in {i['id'] for i in effects} for e in c['effects']) for c in criteria)
                and len({c['id'] for c in criteria}) == len(criteria), 'design', 'criteria 为 id/text/required/effects，引用真实作用 ID。')
    require(len(identifiers) == len(set(identifiers)) and not set(identifiers).intersection(known), 'design', '新节点 ID 不能重复或覆盖既有节点。')
    all_ids = set(identifiers) | set(known)
    graph = {n['id']: n['depends_on'] for n in nodes}
    visiting, done = set(), set()
    def visit(ident):
        require(ident not in visiting, 'design_cycle', '设计因果有环。')
        if ident in done or ident not in graph:
            return
        visiting.add(ident)
        for dependency in graph[ident]:
            require(dependency in all_ids, 'design_reference', '设计引用了不存在的节点。')
            visit(dependency)
        visiting.remove(ident)
        done.add(ident)
    for ident in identifiers:
        visit(ident)
    if tracking:
        narrative.validate_threads(data, nodes, known_threads)
    if outline:
        validate_outline(data, outline, model, all_ids)
    return copy.deepcopy(data)


def validate_plans(data, first, last, known_nodes, state, contract, world=None, policy=None, known_plans=None, identity_version=1, reading_version=None):
    plans = copy.deepcopy(data.get('plans')) if isinstance(data, dict) else None
    require(isinstance(plans, list) and all(isinstance(p, dict) and type(p.get('chapter')) is int for p in plans)
            and [p['chapter'] for p in plans] == list(range(first, last + 1)),
            'plan', '章计划须恰好覆盖本次窗口，按章号排列。')
    temporary = copy.deepcopy(state)
    previous = {n: p for n, p in (known_plans or {}).items() if not first <= p['chapter'] <= last}
    for plan in plans:
        require(all(text(plan.get(k)) for k in ('goal', 'obstacle', 'choice', 'cost', 'change', 'ending')), 'plan', '章计划需要目标、阻碍、选择、代价、变化和结尾。')
        require(isinstance(plan.get('node_ids'), list) and plan['node_ids'] and all(text(n) and n in known_nodes for n in plan['node_ids']), 'plan', '章计划须引用有效设计节点。')
        participants = plan.get('participants')
        require(isinstance(participants, list) and participants and all(text(p) for p in participants)
                and len(participants) == len(set(participants)), 'plan', 'participants 须为非空、不重复实体 ID。')
        require(isinstance(plan.get('new_entities', []), list), 'plan', 'new_entities 须为实体数组。')
        for item in plan.get('new_entities', []):
            register_entity(temporary['entities'], item)
        validate_plan_names(plan, policy if policy is not None else resolve_policy({}))
        require(all(p in temporary['entities'] for p in participants), 'plan', '参与人须为既有实体或本窗口声明的候选实体。')
        if world:
            refs = plan.get('world_refs')
            known = {section + ':' + row['id'] for section, rows in world.items() if isinstance(rows, list) for row in rows if isinstance(row, dict) and 'id' in row}
            require(isinstance(refs, list) and all(text(ref) and ref in known for ref in refs), 'world_reference', '有世界模型的章计划须声明 world_refs，可为空但不能引用不存在的记录。')
        require(isinstance(plan.get('obligations', []), list), 'plan', 'obligations 须为数组。')
        ids = []
        for obligation in plan.get('obligations', []):
            require(isinstance(obligation, dict) and text(obligation.get('id')) and text(obligation.get('text'))
                    and obligation.get('category') in ('facts', 'reader'), 'obligation', '义务需要 id/text/category。')
            ids.append(obligation['id'])
        require(len(ids) == len(set(ids)), 'obligation', '义务 ID 重复。')
        require(isinstance(plan.get('schedule', []), list), 'schedule', 'schedule 须为日程对象数组。')
        for schedule in plan.get('schedule', []):
            require(isinstance(schedule, dict) and schedule.get('basis') == 'main_clock'
                    and type(schedule.get('day')) is int and schedule['day'] >= state['clock']
                    and text(schedule.get('event')), 'schedule', '日程须声明主线坐标、有效天数和事件。')
        if contract.get('narrative_tracking'):
            narrative.validate_plan(plan, known_nodes, temporary)
        if contract.get('editorial_features'):
            craft.scenes(plan, temporary['entities'])
        from . import story_memory
        story_memory.bind(plan, previous, identity_version, reading_version)
        previous[str(plan['chapter'])] = plan
    return copy.deepcopy(plans)


def validate_profiles(data, required, state=None, previous=None, enhanced=False):
    profiles = data.get('profiles') if isinstance(data, dict) else None
    require(isinstance(profiles, list) and all(isinstance(p, dict) and text(p.get('entity')) for p in profiles)
            and {p['entity'] for p in profiles} == set(required)
            and len(profiles) == len(required), 'profile', '人物档案须恰好覆盖请求的实体。')
    for profile in profiles:
        require(all(text(profile.get(k)) for k in ('entity', 'desire', 'fear', 'limit', 'voice', 'knowledge_boundary')),
                'profile', '人物档案需要欲望、顾虑、底线、声线和知情边界。')
    if enhanced:
        profiles = [craft.profile(p, state, (previous or {}).get(p['entity'])) for p in profiles]
    return copy.deepcopy(profiles)

