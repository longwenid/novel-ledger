"""Rich world definitions; never mutate canonical facts or character knowledge."""
from __future__ import annotations

import copy
from .contracts import require, text

SECTIONS = {
    'geography': ('name', 'environment', 'resources', 'access', 'story_pressure'),
    'history': ('period', 'event', 'consequence', 'present_effect'),
    'rules': ('principle', 'scope', 'limits', 'consequences'),
    'factions': ('name', 'goal', 'power', 'dependencies', 'conflicts'),
    'economy': ('resource', 'production', 'distribution', 'scarcity', 'conflict'),
    'society': ('institution', 'norm', 'enforcement', 'pressure'),
    'everyday': ('practice', 'constraint', 'story_use'),
    'characters': ('name', 'role', 'desire', 'limit', 'knowledge_boundary'),
    'mysteries': ('truth', 'disclosure', 'causal_role'),
    'mechanisms': ('principle', 'cost', 'limits', 'failure_condition'),
}
LABELS = {'geography': '地理与通行', 'history': '历史与当下影响', 'rules': '世界规则', 'factions': '势力与利益',
          'economy': '资源与经济', 'society': '社会制度', 'everyday': '生活日常', 'characters': '人物与关系',
          'mysteries': '隐秘信息与披露', 'mechanisms': '特殊机制与代价'}
ALL_SECTIONS = tuple(SECTIONS)
# Which sections a world must fill, by scale tier. A world is read by every later dispatch, so its
# floor has to be the world this book's line actually walks through. Declared once and read by both
# the brief and this validator, because a brief that asks for a small world while the check demands
# ten domains is a requirement disagreeing with its own check — a real micro project paid for that in
# four repair rounds and 55 records. Sections outside the tier stay in the shape and may be empty.
TIER_SECTIONS = {
    't0': ('rules', 'society', 'everyday', 'characters', 'mysteries', 'mechanisms'),
    't1': ('geography', 'rules', 'society', 'everyday', 'characters', 'mysteries', 'mechanisms'),
    't2': ('geography', 'history', 'rules', 'society', 'everyday', 'characters', 'mysteries', 'mechanisms'),
    't3': ALL_SECTIONS,
    't4': ALL_SECTIONS,
    't5': ALL_SECTIONS,
}


def required_sections(tier_id=None):
    """The sections this tier's world must fill; every tier still delivers the full shape."""
    return tuple(TIER_SECTIONS.get(tier_id) or ALL_SECTIONS)


def index(model):
    return {section + ':' + row['id']: row for section in SECTIONS for row in model.get(section, [])}


def validate(data, choices, selection_hash, sections=None):
    required = required_sections(sections) if isinstance(sections, str) else tuple(sections or required_sections())
    require(isinstance(data, dict) and data.get('selection_hash') == selection_hash
            and text(data.get('premise')) and text(data.get('story_capacity')), 'world', '世界需要准确选择版本、核心前提和长篇承载说明。')
    require(data['premise'] == choices['world']['world_premise'], 'world_alignment', '世界前提须遵守所选方案。')
    all_ids = set()
    for section, fields in SECTIONS.items():
        rows = data.get(section)
        require(isinstance(rows, list), 'world_section', '世界缺少结构领域：' + section)
        require(bool(rows) or section in ('mechanisms',) or section not in required, 'world_section',
                '本档位要求填写的世界领域必须有实际内容：' + section,
                {'required_sections': list(required), 'recover': '按档位只填这条主线走得到的领域，其余留空数组。'})
        for row in rows:
            require(isinstance(row, dict) and text(row.get('id')) and all(text(row.get(k)) for k in fields), 'world_record', '世界记录缺少具体内容：' + section)
            key = section + ':' + row['id']
            require(key not in all_ids, 'world_id', '世界记录 ID 重复。')
            all_ids.add(key)
            require(isinstance(row.get('links'), list) and all(text(ref) for ref in row['links']), 'world_links', '世界记录须声明关联引用，独立记录可用空数组。')
    for section in SECTIONS:
        for row in data[section]:
            require(all(ref in all_ids for ref in row['links']), 'world_reference', '世界关联引用不存在。')
    names = [c['name'] for c in data['characters']]
    require(len(names) == len(set(names)), 'world_identity', '世界人物称呼不能歧义。')
    protagonist = choices['protagonist']
    require(any(c['id'] == protagonist['id'] and c['name'] == protagonist['name'] and c['desire'] == protagonist['desire']
                and c['limit'] == protagonist['limit'] for c in data['characters']), 'world_alignment', '世界模型须保留所选主角的身份、欲望和底线。')
    mode = choices['world']['mechanism']['mode']
    require((mode == 'none' and not data['mechanisms']) or (mode == 'bounded' and bool(data['mechanisms'])), 'world_alignment', '世界机制必须遵守已选的无机制或有限机制方向。')
    require(set(data) <= {'selection_hash', 'premise', 'story_capacity', *SECTIONS}, 'world_fields', '世界模型不得夹带正文事件或事实结算。')
    return copy.deepcopy(data)
