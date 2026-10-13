"""Author constraints, rolling plans and profiles. All functions are pure."""
from __future__ import annotations

import copy
import math
from . import contracts
from .contracts import (CONTRACT_ALIGNMENT, CONTRACT_FIELDS, CONTRACT_KEYS, DEFAULT_NAME_CHARS, DEFAULT_TERMS,
                        POLICY_FIELDS, contract_errors, contract_skeleton, require, text)
from .facts import entity, seed


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


def policy_of(book):
    """Resolve the active policy from a book record (versions are history, not authority)."""
    versions = book.get('lexical_policy') or []
    require(isinstance(versions, list) and versions, 'lexical_policy', '项目缺少字面规则记录。')
    latest = versions[-1]
    require(isinstance(latest, dict), 'lexical_policy', '字面规则版本须为对象。')
    return resolve_policy(latest.get('policy', {}))


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
    scope = contracts.ENFORCEMENT.get(stage)
    if not scope:
        return {'terms': [], 'names': [], 'note': '本阶段不检查字面约定。'}
    return {'terms': list(scope.get('terms', ())), 'names': list(scope.get('names', ())),
            'note': contracts.POLICY_NOTE}


def policy_block(book, stage):
    """The active policy as task material: what applies, where it came from, and how it changes."""
    versions = book.get('lexical_policy') or []
    latest = versions[-1] if versions else {'version': 1, 'policy': resolve_policy({}), 'source': '内置默认'}
    resolved = resolve_policy(latest.get('policy', {}))
    return {'version': latest.get('version', 1), 'source': latest.get('source', ''),
            'forbidden_terms': resolved['forbidden_terms'],
            'forbidden_name_chars': resolved['forbidden_name_chars'],
            'scope': enforcement_scope(stage),
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
        # Defaults are structural, not content: they may never invent an author decision.
        for row in CONTRACT_FIELDS:
            if row['key'] not in contract and (row.get('optional') or row['default'] not in ('', [], None)):
                contract[row['key']] = copy.deepcopy(row['default'])
    complaints = contract_errors(contract)
    require(not complaints, 'contract', '约定结构不成立：' + '；'.join(complaints[:6]))
    contract.setdefault('chapter_aim', min(contract['chapter_max'], max(contract['chapter_min'], 3500)))
    require(all(type(contract[k]) is int and contract[k] > 0
                for k in ('chapter_min', 'chapter_max', 'chapter_aim', 'planning_window', 'review_interval', 'review_chunk')),
            'contract', '篇幅、窗口和复审间隔须为正整数。')
    require(contract['chapter_min'] <= contract['chapter_aim'] <= contract['chapter_max'], 'contract', '章目标须在上下限之间。')
    band = contract['word_range']
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
    require(last * contract['chapter_max'] >= band[0] and last * contract['chapter_min'] <= band[1],
            'scale', '章节范围与总篇幅不能同时成立，请调整卷预算或章篇幅。')
    for key in ('world_rules', 'red_lines', 'arcs'):
        require(isinstance(contract[key], list) and all(text(v) for v in contract[key]), 'contract', key + ' 须为字符串数组。')
    seed(contract)
    return contract



def volume_for(contract, chapter):
    return next((v for v in contract['volumes'] if v['first'] <= chapter <= v['end']), None)


def validate_design(data, known=()):
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
    return copy.deepcopy(data)


def validate_plans(data, first, last, known_nodes, state, contract, world=None, policy=None):
    plans = data.get('plans') if isinstance(data, dict) else None
    require(isinstance(plans, list) and [p.get('chapter') for p in plans if isinstance(p, dict)] == list(range(first, last + 1)),
            'plan', '章计划须恰好覆盖本次窗口，按章号排列。')
    temporary = copy.deepcopy(state)
    for plan in plans:
        require(all(text(plan.get(k)) for k in ('goal', 'obstacle', 'choice', 'cost', 'change', 'ending')), 'plan', '章计划需要目标、阻碍、选择、代价、变化和结尾。')
        require(isinstance(plan.get('node_ids'), list) and plan['node_ids'] and all(n in known_nodes for n in plan['node_ids']), 'plan', '章计划须引用有效设计节点。')
        participants = plan.get('participants')
        require(isinstance(participants, list) and participants and all(text(p) for p in participants)
                and len(participants) == len(set(participants)), 'plan', 'participants 须为非空、不重复实体 ID。')
        require(isinstance(plan.get('new_entities', []), list), 'plan', 'new_entities 须为实体数组。')
        validate_plan_names(plan, policy if policy is not None else resolve_policy({}))
        for item in plan.get('new_entities', []):
            entity(temporary, item)
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
        for schedule in plan.get('schedule', []):
            require(isinstance(schedule, dict) and schedule.get('basis') == 'main_clock'
                    and type(schedule.get('day')) is int and schedule['day'] >= state['clock']
                    and text(schedule.get('event')), 'schedule', '日程须声明主线坐标、有效天数和事件。')
    return copy.deepcopy(plans)


def validate_profiles(data, required):
    profiles = data.get('profiles') if isinstance(data, dict) else None
    require(isinstance(profiles, list) and all(isinstance(p, dict) and text(p.get('entity')) for p in profiles)
            and {p['entity'] for p in profiles} == set(required)
            and len(profiles) == len(required), 'profile', '人物档案须恰好覆盖请求的实体。')
    for profile in profiles:
        require(all(text(profile.get(k)) for k in ('entity', 'desire', 'fear', 'limit', 'voice', 'knowledge_boundary')),
                'profile', '人物档案需要欲望、顾虑、底线、声线和知情边界。')
    return copy.deepcopy(profiles)

