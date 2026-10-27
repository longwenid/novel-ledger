"""Pure author constraints, outline policies and planning validation entry points."""
from __future__ import annotations

import copy
import math
from . import contracts, drift_validation
from .contracts import (CONTRACT_FIELDS, DEFAULT_NAME_CHARS, DEFAULT_TERMS,
                        POLICY_FIELDS, contract_errors, contract_skeleton, digest, require, text)
from . import craft, story_memory


def resolve_policy(policy):
    """The book-level lexical policy is the only authority; this is the one resolver."""
    value = policy if isinstance(policy, dict) else {}
    resolved = {'forbidden_terms': list(DEFAULT_TERMS), 'forbidden_name_chars': list(DEFAULT_NAME_CHARS),
                'allowed_latin': []}
    for key in POLICY_FIELDS:
        if key in value:
            resolved[key] = copy.deepcopy(value[key])
    require(all(isinstance(resolved[k], list) and all(text(s) for s in resolved[k]) for k in POLICY_FIELDS),
            'lexical_policy', '字面规则须为字符串数组。')
    require(all(len(term) >= 2 and term.isascii() and term.isalpha() for term in resolved['allowed_latin']),
            'lexical_policy', 'allowed_latin 须逐项填写至少两个英文字母组成的完整词，区分大小写。')
    return resolved


def active_policy(versions):
    """Resolve only the active version; unrelated book state is never an input."""
    versions = versions or []
    require(isinstance(versions, list) and versions, 'lexical_policy', '项目缺少字面规则记录。')
    latest = versions[-1]
    require(isinstance(latest, dict), 'lexical_policy', '字面规则版本须为对象。')
    return resolve_policy(latest.get('policy', {}))


def policy_of(book):
    """The active lexical policy of a transaction aggregate."""
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
    and the `policy` block handed to the worker, so declared and enforced scope cannot drift. A
    stage the table does not list is a stage with nothing to enforce, which is how the deleted
    review stages stay deleted without a branch here.
    """
    scope = contracts.ENFORCEMENT.get(stage)
    if not scope:
        return
    resolved = resolve_policy(policy)
    terms_scope = scope.get('terms', ())
    names_scope = scope.get('names', ())
    hits = {}
    for path, value in _walk(data):
        segments = path.split('.') if path else []
        field = segments[-1] if segments else ''
        # A declared field matches any segment of the path, not just the leaf: a chapter's inline
        # `new_entities` rows carry their names one level down, and an opening option carries its
        # chosen `value` deep inside the options array — a leaf-only comparison let a forbidden
        # term ride into the world model through `options[].value.resource.source` while the very
        # same word in `options[].premise` was refused.
        if field in terms_scope or any(part in terms_scope for part in segments):
            found = [w for w in resolved['forbidden_terms'] if w in value]
            if found:
                hits.setdefault('forbidden_terms', []).append({'field': path, 'found': found})
        if field in names_scope or any(part in names_scope for part in segments):
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
            'allowed_latin': resolved['allowed_latin'],
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


def resolve_outline_policy(contract, key):
    """Required pipeline policies: absence defaults, explicit invalid values never do."""
    scopes = ('all', 'rolling') if key == 'volume_outline' else ('volume', 'all')
    policy = contract[key] if key in contract else contracts.policy_default(key)
    require(isinstance(policy, dict) and set(policy) == {'scope', 'words', 'tolerance'}
            and policy.get('scope') in scopes and type(policy.get('words')) is int and policy['words'] > 0
            and type(policy.get('tolerance')) is int and 0 <= policy['tolerance'] < policy['words'],
            key, key + ' 是必选阶段，不能用空对象或 null 关闭；须为 {scope:' + '|'.join(scopes)
            + ',words:正整数,tolerance:非负整数且小于 words}。',
            {'recover': '通过明确改约填写完整策略；缺省字段可使用默认值。',
             'default': contracts.policy_default(key)})
    return copy.deepcopy(policy)


def outline_policies(contract):
    policies = {key: resolve_outline_policy(contract, key)
                for key in ('volume_outline', 'chapter_outline')}
    require(not (policies['volume_outline']['scope'] == 'rolling'
                 and policies['chapter_outline']['scope'] == 'all'
                 and len(contract.get('volumes') or []) > 1),
            'outline_policy', '多卷 rolling 卷纲须搭配 volume 章纲；全书章纲须先有 all 卷纲。',
            {'recover': '明确改约选择 all/volume、all/all 或 rolling/volume。'})
    return policies


def validate_contract(raw):
    contract = copy.deepcopy(raw) if isinstance(raw, dict) else raw
    if isinstance(contract, dict):
        # Defaults are structural, not content: they may never invent an author decision. An empty
        # container is a shape the validator has to see; an empty string is a decision nobody made,
        # so an optional text field stays absent rather than being written in as blank.
        for row in CONTRACT_FIELDS:
            if row['key'] in contract:
                continue
            default = row['default']
            if default in ('', None):
                continue
            if default == [] and row.get('blank') is False and row.get('count', 1) > 0:
                # A field that must carry at least `count` rows cannot be satisfied by injecting an
                # empty list: that writes in a decision nobody made and then rejects its own default
                # on the very next line. An optional field simply stays absent; a required one is
                # reported as a missing field, which is the truth about the receipt.
                continue
            contract[row['key']] = copy.deepcopy(default)
    complaints = contract_errors(contract)
    require(not complaints, 'contract', '约定结构不成立：' + '；'.join(complaints[:6]))
    contract.setdefault('chapter_aim', min(contract['chapter_max'], max(contract['chapter_min'], 3500)))
    require(all(type(contract[k]) is int and contract[k] > 0
                for k in ('chapter_min', 'chapter_max', 'chapter_aim', 'revision_limit')),
            'contract', '章幅与修订窗口须为正整数。')
    require(contract['chapter_min'] <= contract['chapter_aim'] <= contract['chapter_max'], 'contract', '章目标须在上下限之间。')
    require(contract['chapter_max'] <= contracts.policy_default('chapter_max_ceiling'), 'contract',
            '章字数上限不得高于策略上限 %d。' % contracts.policy_default('chapter_max_ceiling'))
    require(type(contract['narrative_tracking']) is bool, 'contract', 'narrative_tracking 须为布尔值。')
    require(type(contract['editorial_features']) is bool and (not contract['editorial_features'] or contract['narrative_tracking']),
            'contract', 'editorial_features 需要 narrative_tracking；基础模式可明确设 false。')
    contract.update(outline_policies(contract))
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
    # here replaces the arithmetic that checked a hand-entered band against the count.
    contract['word_range'] = [last * contract['chapter_min'], last * contract['chapter_max']]
    for key in ('world_rules', 'red_lines', 'arcs'):
        require(isinstance(contract[key], list) and all(text(v) for v in contract[key]), 'contract', key + ' 须为字符串数组。')
    return contract


def volume_for(contract, chapter):
    return next((v for v in contract['volumes'] if v['first'] <= chapter <= v['end']), None)


def outline_policy(contract, volume, model=None):
    """The volume-outline policy bound to one volume of the live contract."""
    policy = resolve_outline_policy(contract, 'volume_outline')
    return {**copy.deepcopy(policy), 'first': volume['first'], 'last': volume['end'],
            'world_hash': digest(model) if model else None}


def chapter_policy(contract, volume, model=None):
    """The chapter-outline policy bound to one volume, with the same window vocabulary."""
    policy = resolve_outline_policy(contract, 'chapter_outline')
    return {**copy.deepcopy(policy), 'volume': volume['id'], 'first': volume['first'],
            'last': volume['end'], 'world_hash': digest(model) if model else None}


def validate_volume_outline(data, contract, world, selected=None, existing=None, missing_ids=None,
                            state=None):
    """Delegate the volume outline's mechanical checks to `drift_validation` (single implementation)."""
    return drift_validation.validate_volume_outline(data, contract, world, selected, existing, missing_ids, state)


def validate_chapter_outline(data, policy, volume_row, volume_row_outline, world, state0, previous=None):
    """Delegate the chapter outline's chain checks, then freeze the scenes it declares.

    `drift_simulation` owns the state chain; this entry point adds the one piece that needs the scene protocol
    (identity and reading dependencies), which is why it lives beside the policy rather than in the
    pure drift core. Rows without scenes are bound too: the binding is what records that the row
    declared no dependency, which a revision later reads as "conservatively expand".
    """
    rows = drift_validation.validate_chapter_outline(data, policy, volume_row, volume_row_outline, world, state0)
    entities = copy.deepcopy((state0 or {}).get('entities') or {})
    replaced = {row['chapter'] for row in rows}
    previous = {key: value for key, value in (previous or {}).items()
                if value['chapter'] not in replaced}
    for row in rows:
        if row.get('scenes'):
            craft.scenes(row, entities)
        story_memory.bind(row, previous)
        previous[str(row['chapter'])] = row
    return rows
