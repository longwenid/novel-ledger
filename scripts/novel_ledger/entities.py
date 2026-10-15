"""Entity identity and naming rules over an entity table."""
from __future__ import annotations

import copy
from .contracts import require, text


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
