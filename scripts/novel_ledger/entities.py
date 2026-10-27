"""Entity identity and naming rules over an entity table."""
from __future__ import annotations

import copy
from .contracts import BIOGRAPHY_FIELDS, CHARACTERS, CHARACTER_KINDS, require, text


def validate_character(item, *, core=False):
    require(isinstance(item, dict) and all(text(item.get(key)) for key in CHARACTERS),
            'entity', '人物档案需要 name/role/desire/limit/knowledge_boundary。')
    importance = item.get('importance')
    require(importance is None or importance in ('core', 'supporting', 'minor'),
            'entity', 'importance 只能为 core/supporting/minor。')
    aliases = item.get('aliases', [])
    require(isinstance(aliases, list) and all(text(alias) for alias in aliases)
            and len(set(aliases)) == len(aliases) and item['name'] not in aliases,
            'alias', '人物别名须为不重复的非空文本，不能重复正式姓名。')
    biography = item.get('biography')
    require(not (core or importance == 'core') or isinstance(biography, dict),
            'entity', '核心人物需要 biography={past,contradiction,relationships,behavior}。')
    if 'biography' in item:
        require(isinstance(biography, dict) and set(biography) == set(BIOGRAPHY_FIELDS)
                and all(text(biography.get(key)) for key in BIOGRAPHY_FIELDS),
                'entity', '小传须交代过往如何影响当下、内在矛盾、关系牵制与行为方式。')


def validate_introduction(item, definitions=()):
    """First registration owns identity; current motivation is settled separately."""
    require(isinstance(item, dict) and all(text(item.get(key)) for key in ('id', 'name', 'kind')),
            'entity', '新实体需要 id/name/kind。')
    aliases = item.get('aliases', [])
    require(isinstance(aliases, list) and all(text(alias) for alias in aliases),
            'alias', '别名须为非空字符串数组。')
    definition = next((row for row in definitions if row.get('id') == item['id']), None)
    names = {item['name'], *aliases}
    for row in definitions:
        other_names = {row['name'], *(row.get('aliases') or [])}
        require(row['id'] == item['id'] or not names.intersection(other_names),
                'alias_conflict', '此称呼已属于世界中的另一人物 ID。',
                {'entity': item['id'], 'world_entity': row['id']})
    if definition:
        require(item['kind'] in CHARACTER_KINDS and item['name'] == definition['name']
                and item.get('role') == definition['role'],
                'entity', '首次人物登记的 ID、正式姓名和身份须与冻结世界一致；称谓用 aliases。',
                {'entity': item['id'], 'expected_name': definition['name'],
                 'expected_role': definition['role']})
    if item['kind'] in CHARACTER_KINDS:
        effective = {**item}
        if definition and 'biography' not in item and 'biography' in definition:
            effective['biography'] = definition['biography']
        validate_character(effective)
        if definition and definition.get('importance') == 'core':
            require(item.get('importance') in (None, 'core'), 'entity', '不能降低已选核心人物层级。')
            # A frozen world biography need not be copied into a second full artifact.
            validate_character({**definition, **item,
                                'biography': item.get('biography', definition.get('biography'))}, core=True)


def register(entities, item):
    require(isinstance(item, dict) and all(text(item.get(k)) for k in ('id', 'name', 'kind')), 'entity', '实体需要 id/name/kind。')
    ident = item['id']
    require(not any(c in ident for c in ':>') and ident not in entities, 'entity', '实体 ID 重复或含分隔符。')
    aliases = item.get('aliases', [])
    require(isinstance(aliases, list) and all(text(a) for a in aliases), 'alias', '别名须为非空字符串数组。')
    names = [item['name']] + aliases
    used = {s for e in entities.values() for s in [e['name']] + e.get('aliases', [])}
    require(len(set(names)) == len(names) and not used.intersection(names), 'alias_conflict', '称呼重复或属于另一实体。')
    entities[ident] = copy.deepcopy(item)
