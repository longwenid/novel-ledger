"""Scene execution and text patches. Pure values only.

v2 removed the profile stage: a first appearance is inlined in the chapter outline's `new_entities`,
so the character-interpretation helpers that used to live here (and their growth_basis binding) are
gone with the stage that dispatched them.
"""
from __future__ import annotations

import copy
from .contracts import digest, require, text


def participants_of(plan, entities=None):
    """Who is on stage in a row, from the row itself.

    A v2 chapter outline declares its cast through `characters`/`knowledge`/`places` deltas and
    `new_entities`, not through a plan-shaped `participants` list; a materialized plan row carries
    that list already. Reading both here keeps the scene check usable on either shape.
    """
    named = plan.get('participants')
    if isinstance(named, list) and named:
        return list(named)
    found = []
    for row in plan.get('characters') or []:
        if isinstance(row, dict) and text(row.get('entity')) and row['entity'] not in found:
            found.append(row['entity'])
    for row in plan.get('new_entities') or []:
        if isinstance(row, dict) and text(row.get('id')) and row['id'] not in found:
            found.append(row['id'])
    for row in (plan.get('knowledge') or []) + (plan.get('places') or []):
        if isinstance(row, dict):
            ident = row.get('who') or row.get('entity')
            if text(ident) and ident not in found:
                found.append(ident)
    if found:
        return found
    return list(entities or {})


def scenes(plan, entities):
    """Check the scenes a row declares, when it declares any.

    v2 chapter outlines may carry scenes for the workbench, but they are optional: an empty array is
    a row that did not break its chapter into scenes, not a row that forgot to. What is present is
    checked exactly as before, and the cast is read from the row rather than demanded in advance.
    """
    rows = plan.get('scenes')
    if not rows:
        return
    require(isinstance(rows, list) and all(isinstance(s, dict) for s in rows), 'scene', 'scenes 须为场景对象数组。')
    participants = participants_of(plan, entities)
    for scene in rows:
        require(isinstance(scene, dict) and all(text(scene.get(k)) for k in ('label', 'intent', 'conflict', 'turn')),
                'scene', '每场需要 label/intent/conflict/turn。')
        present, speakers = scene.get('present'), scene.get('speakers')
        require(isinstance(present, list) and present and all(p in participants for p in present)
                and isinstance(speakers, list) and all(text(s) for s in speakers) and len(speakers) == len(set(speakers)) and set(speakers) <= set(present),
                'scene', 'present 须为本章出场人物；speakers 明示发言者，静默场景用空数组。',
                {'participants': participants[:12], 'present': present})
        intents = scene.get('dialogue_intents')
        require(isinstance(intents, list) and len(intents) == len(speakers)
                and all(isinstance(i, dict) and text(i.get('entity')) for i in intents)
                and {i.get('entity') for i in intents} == set(speakers), 'dialogue', 'dialogue_intents 恰好覆盖发言者。')
        for intent in intents:
            require(all(text(intent.get(k)) for k in ('seeks', 'withholds', 'pressure', 'tactic'))
                    and isinstance(intent.get('knowledge_topics'), list) and all(text(t) for t in intent['knowledge_topics']),
                    'dialogue', '对白意图需 seeks/withholds/pressure/tactic/knowledge_topics。')
    units = plan.get('expansion_units')
    if not units:
        return
    require(isinstance(units, list) and all(isinstance(u, dict) for u in units), 'development', 'expansion_units 须为对象数组。')
    ids = []
    for unit in units:
        require(all(text(unit.get(k)) for k in ('id', 'focus', 'development', 'expected_change'))
                and type(unit.get('scene')) is int and 1 <= unit['scene'] <= len(rows),
                'development', '展开单元需 id/scene/focus/development/expected_change，scene 从 1 起。')
        ids.append(unit['id'])
    require(len(ids) == len(set(ids)), 'development', '展开单元 ID 不重复。')


def compose(data, base=None):
    modes = [k for k in ('prose', 'patches', 'reuse_original') if k in data]
    require(len(modes) == 1, 'patch', 'prose/patches/reuse_original 只能选一种正文方式。')
    if modes == ['prose']:
        require(text(data['prose']), 'draft', '正文须非空。')
        return data['prose'], None
    require(base is not None and data.get('base_hash') == digest(base), 'patch_base', '补丁须绑定本任务准确基稿哈希。')
    require(text(data.get('repair_note')), 'patch', '补丁或复用须给 repair_note。')
    if modes == ['reuse_original']:
        require(data['reuse_original'] is True, 'patch', 'reuse_original 只能为 true，仍需独立重审。')
        return base, {'base_hash': digest(base), 'reuse_original': True, 'repair_note': data['repair_note']}
    patches = data['patches']
    require(isinstance(patches, list) and patches and all(isinstance(p, dict) for p in patches), 'patch', 'patches 须非空。')
    end = -1
    for patch in sorted(patches, key=lambda p: p.get('start', -1) if type(p.get('start')) is int else -1):
        start, old, new = patch.get('start'), patch.get('old'), patch.get('new')
        require(set(patch) == {'start', 'old', 'new'} and type(start) is int and start >= 0 and text(old)
                and isinstance(new, str) and old != new and start >= end and base[start:start + len(old)] == old,
                'patch', '补丁字段为 start/old/new；基稿坐标须准确、不重叠、不原样替换。')
        end = start + len(old)
    prose = base
    for patch in sorted(patches, key=lambda p: p['start'], reverse=True):
        start = patch['start']
        prose = prose[:start] + patch['new'] + prose[start + len(patch['old']):]
    require(text(prose), 'patch', '不能清空整章。')
    return prose, {k: copy.deepcopy(data[k]) for k in ('base_hash', 'patches', 'repair_note')}


def patch_at(base, old, new, start=None):
    require(text(old) and isinstance(new, str), 'patch', '提供准确 old 和 new。')
    matches, cursor = [], 0
    while True:
        at = base.find(old, cursor)
        if at < 0:
            break
        matches.append(at)
        cursor = at + 1
    require(start is not None or len(matches) == 1, 'patch', '引文缺失或歧义，须指定 start。', {'matches': matches})
    patch = {'start': matches[0] if start is None else start, 'old': old, 'new': new}
    value = {'base_hash': digest(base), 'patches': [patch], 'repair_note': '定位预检。'}
    compose(value, base)
    return {'base_hash': digest(base), 'patches': [patch]}
