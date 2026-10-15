"""Scene identities and explicit narrative dependencies; no persistence or inferred facts."""
from __future__ import annotations

import copy
from .contracts import digest, require, text

KINDS = ('entities', 'facts', 'knowledge', 'resources', 'relations', 'placements', 'places',
         'character_current', 'reader_knowledge', 'hooks', 'node', 'clock', 'clock_threads',
         'thread_progress', 'historical_assertions', 'developments')
READING_KINDS = ('character', 'relationship', 'theme', 'voice', 'disclosure')
READING_SCHEMA = 'reading-dependencies/1'


def reading_enabled(plan):
    """Interpret only the reading protocol frozen into this exact plan version."""
    return plan.get('reading_schema') == READING_SCHEMA


def reading_coordinate(value):
    require(isinstance(value, dict) and set(value) == {'kind', 'key'}
            and value.get('kind') in READING_KINDS and text(value.get('key')),
            'reading_dependency', '阅读关联须为 {kind:character|relationship|theme|voice|disclosure,key:ID}。')
    return value['kind'], value['key']


def reading_refs(plan):
    refs = set()
    if reading_enabled(plan):
        refs.update(reading_coordinate(r) for r in plan.get('reading_refs', []))
        refs.update(reading_coordinate(r) for scene in plan.get('scenes', []) for r in scene.get('reading_refs', []))
    refs.update((kind, p) for p in plan.get('participants', []) for kind in ('character', 'voice'))
    refs.update(('disclosure', d['topic']) for d in plan.get('disclosures', []))
    return refs


def coordinate(value):
    require(isinstance(value, dict) and value.get('kind') in KINDS and text(value.get('key')),
            'story_dependency', '依赖坐标须为 {kind,key}，kind 使用事实投影种类。', {'valid_kinds': list(KINDS)})
    require(value['kind'] != 'clock' or value['key'] == 'main', 'story_dependency', '主时钟坐标使用 clock/main。')
    return value['kind'], value['key']


def bind(plan, previous, identity_version=1, reading_version=None):
    """Freeze new plans; callers rechecking history must pass its stored reading version."""
    if reading_version is None:
        reading_version = 1 if identity_version == 2 else 0
    require(type(reading_version) is int and reading_version in (0, 1),
            'reading_dependency', '未知的冻结阅读关联协议。')
    reading = reading_version == 1
    coverage = plan.get('dependency_coverage', 'partial')
    require(coverage in ('partial', 'complete'), 'story_dependency', 'dependency_coverage 为 partial 或 complete。')
    scenes = plan.get('scenes', [])
    require(isinstance(scenes, list) and all(isinstance(s, dict) for s in scenes),
            'story_dependency', 'scenes 须为场景对象数组。')
    require(coverage != 'complete' or scenes, 'story_dependency', '完整依赖声明须有实际场景。')
    if scenes:
        plan['dependency_coverage'] = coverage
    known = {s['id'] for p in previous.values() if p['chapter'] < plan['chapter']
             for s in p.get('scenes', []) if 'id' in s}
    occupied = {s['id'] for p in previous.values() if p['chapter'] != plan['chapter']
                for s in p.get('scenes', []) if 'id' in s}
    if identity_version == 2:
        plan['scene_schema'] = 'scene-identity/2'
    if reading:
        require('reading_schema' not in plan or reading_enabled(plan),
                'reading_dependency', '新计划使用 reading-dependencies/1 阅读关联协议。')
        plan['reading_schema'] = READING_SCHEMA
        require(plan.get('reading_coverage', 'partial') in ('partial', 'complete'),
                'reading_dependency', 'reading_coverage 为 partial 或 complete。')
        require(plan.get('reading_coverage') != 'complete' or scenes,
                'reading_dependency', '完整阅读关联声明须有实际场景。')
        for key in ('reading_refs', 'understanding_refs'):
            require(isinstance(plan.get(key, []), list), 'reading_dependency', key + ' 须为数组。')
        require(all(text(r) for r in plan.get('understanding_refs', [])),
                'understanding_reference', 'understanding_refs 须为理解 ID 数组。')
    for index, scene in enumerate(scenes, 1):
        default = ('scene:' + digest([plan['chapter'], index, scene.get('label')])[:20]
                   if identity_version == 2 else 'c%d:s%d' % (plan['chapter'], index))
        ident = scene.setdefault('id', default)
        prefix = 'c%d:' % plan['chapter']
        require(text(ident) and ident not in occupied
                and (identity_version == 2 or ident.startswith(prefix) and len(ident) > len(prefix)),
                'scene_identity', '场景 ID 须唯一；新协议保留移动前的 id，旧冻结协议仍用本章 c章号: 前缀。')
        occupied.add(ident)
        if reading:
            require('story_time' not in scene or text(scene['story_time']),
                    'scene_time', 'story_time 为故事发生时间说明，独立于正文阅读顺序，不直接推进事实时钟。')
            require(isinstance(scene.get('reading_refs', []), list), 'reading_dependency', '场景 reading_refs 须为数组。')
            require(plan.get('reading_coverage') != 'complete' or 'reading_refs' in scene,
                    'reading_dependency', '完整阅读关联声明须逐场列 reading_refs，无额外关联给空数组。')
        require(coverage != 'complete' or 'reads' in scene and 'depends_on' in scene,
                'story_dependency', '完整依赖声明须为每场列出 reads 和 depends_on，无依赖明确给空数组。')
        reads, links = scene.setdefault('reads', []), scene.setdefault('depends_on', [])
        require(isinstance(reads, list) and isinstance(links, list) and all(text(s) for s in links),
                'story_dependency', 'reads 为坐标数组，depends_on 为场景 ID 数组。')
        coords = [coordinate(r) for r in reads]
        intents = scene.get('dialogue_intents', [])
        require(isinstance(intents, list) and all(isinstance(i, dict) and text(i.get('entity'))
                and isinstance(i.get('knowledge_topics', []), list)
                and all(text(topic) for topic in i.get('knowledge_topics', [])) for i in intents),
                'story_dependency', '对白依赖须有 entity 和 knowledge_topics 字符串数组。')
        require(len(coords) == len(set(coords)) and len(links) == len(set(links)) and set(links) <= known,
                'story_dependency', '依赖不得重复，只能引用已登记的前章或本章前场；禁止前向引用和环。',
                {'scene': ident, 'unknown_scenes': sorted(set(links) - known)})
        known.add(ident)
    if reading:
        reading_refs(plan)
    return plan


def reads(plan):
    result = {coordinate(r) for scene in plan.get('scenes', []) for r in scene.get('reads', [])}
    result.update(coordinate(r) for r in plan.get('preconditions', []))
    result.update(('node', ident) for ident in plan.get('node_ids', []))
    for definition in plan.get('node_contracts', {}).values():
        result.update(('node', ident) for ident in definition.get('depends_on', []))
    result.update(('hooks', ident) for ident in plan.get('hook_refs', []))
    result.update(('reader_knowledge', ident) for ident in plan.get('reader_refs', []))
    result.update(('historical_assertions', ident) for ident in plan.get('history_refs', []))
    result.update(('entities', ident) for ident in plan.get('participants', []))
    result.update((kind, ident) for ident in plan.get('participants', [])
                  for kind in ('placements', 'character_current'))
    result.update(('knowledge', intent['entity'] + ':' + topic)
                  for scene in plan.get('scenes', []) for intent in scene.get('dialogue_intents', [])
                  for topic in intent.get('knowledge_topics', []))
    if plan.get('schedule'):
        result.add(('clock', 'main'))
    return result


def lookup(state, kind, key):
    if kind == 'clock':
        return True, state['clock']
    field = 'story_nodes' if kind == 'node' else kind
    values = state.get(field, {})
    return key in values, copy.deepcopy(values.get(key))


def packet(plan, state):
    """Role-independent scene inputs with exact state provenance, not generated summaries."""
    inputs = []
    for kind, key in sorted(reads(plan)):
        present, value = lookup(state, kind, key)
        inputs.append({'kind': kind, 'key': key, 'present': present, 'value': value})
    return {'schema': 'novel-ledger.scene-context/1', 'chapter': plan['chapter'],
            'plan_hash': digest(plan), 'state_hash': digest(state),
            'coverage': plan.get('dependency_coverage', 'partial'),
            'plan': copy.deepcopy(plan), 'inputs': inputs,
            'note': 'inputs 是作者可用前态；人物实际知情仍按 knowledge 与对白意图核对。缺失项不代表已成立。'}
