"""Character interpretation, scene execution and text patches. Pure values only."""
from __future__ import annotations

import copy
from .contracts import digest, require, text


def growth_basis(state, entity):
    return digest({'growth': state['developments'].get(entity, []),
                   'current': state.get('character_current', {}).get(entity)})


def profile(value, state, previous=None):
    require(value.get('tier') in ('major', 'supporting', 'walk_on'), 'profile', '人物 tier 为 major/supporting/walk_on。')
    bio, voice = value.get('biography'), value.get('speech')
    require(isinstance(bio, dict) and all(text(bio.get(k)) for k in ('public_role', 'contradiction', 'values')),
            'profile', 'biography 需要 public_role/contradiction/values。')
    require(isinstance(voice, dict) and all(text(voice.get(k)) for k in ('register', 'rhythm', 'stress_shift'))
            and isinstance(voice.get('tactics'), list) and voice['tactics'] and all(text(t) for t in voice['tactics']),
            'profile', 'speech 需要 register/rhythm/stress_shift 和非空 tactics 数组。')
    modes = voice.get('relationship_modes', [])
    require(isinstance(modes, list) and all(isinstance(m, dict) and text(m.get('entity')) and text(m.get('mode')) for m in modes),
            'profile', 'relationship_modes 为 {entity,mode} 数组。')
    require(not previous or text(value.get('change_reason')), 'profile', '成长后重核档案须给 change_reason。')
    result = copy.deepcopy(value)
    # The engine binds the interpretation to observed growth; this is not a fact event.
    result['growth_basis'] = growth_basis(state, value['entity'])
    return result


def scenes(plan, entities):
    rows = plan.get('scenes')
    require(isinstance(rows, list) and rows, 'scene', '章计划需非空 scenes。')
    for scene in rows:
        require(isinstance(scene, dict) and all(text(scene.get(k)) for k in ('label', 'intent', 'conflict', 'turn')),
                'scene', '每场需要 label/intent/conflict/turn。')
        present, speakers = scene.get('present'), scene.get('speakers')
        require(isinstance(present, list) and present and all(p in plan['participants'] for p in present)
                and isinstance(speakers, list) and all(text(s) for s in speakers) and len(speakers) == len(set(speakers)) and set(speakers) <= set(present),
                'scene', 'present 属于 participants；speakers 明示发言者，静默场景用空数组。')
        intents = scene.get('dialogue_intents')
        require(isinstance(intents, list) and len(intents) == len(speakers)
                and all(isinstance(i, dict) and text(i.get('entity')) for i in intents)
                and {i.get('entity') for i in intents} == set(speakers), 'dialogue', 'dialogue_intents 恰好覆盖发言者。')
        for intent in intents:
            require(all(text(intent.get(k)) for k in ('seeks', 'withholds', 'pressure', 'tactic'))
                    and isinstance(intent.get('knowledge_topics'), list) and all(text(t) for t in intent['knowledge_topics']),
                    'dialogue', '对白意图需 seeks/withholds/pressure/tactic/knowledge_topics。')
    units = plan.get('expansion_units')
    require(isinstance(units, list) and units and all(isinstance(u, dict) for u in units), 'development', 'expansion_units 须非空。')
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
