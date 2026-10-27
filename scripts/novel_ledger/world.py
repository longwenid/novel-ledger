"""Rich world definitions; never mutate canonical facts or character knowledge.

opening/5 widened the world from ten flat domains to twelve: `powers` (the reader-visible ladder of
ranks) and `cosmology` (spaces and planes) join the ten, and the older domains gained optional deep
fields (an epoch's carry-over, a counter-space, why a faction survives a scale-up, when a mystery is
revealed). The two new domains are required exactly when the opening declared something that has to
land in them, and what it declared must exist here word for word — that binding is what stops a gate
decision from being decoration.
"""
from __future__ import annotations

import copy
from .contracts import require, text
from . import contracts
from .entities import validate_character

SECTIONS = {
    'geography': ('name', 'environment', 'resources', 'access', 'story_pressure'),
    'history': ('period', 'event', 'consequence', 'present_effect'),
    'rules': ('principle', 'scope', 'limits', 'consequences'),
    'factions': ('name', 'goal', 'power', 'dependencies', 'conflicts'),
    'economy': ('resource', 'production', 'distribution', 'scarcity', 'conflict'),
    'society': ('institution', 'norm', 'enforcement', 'pressure'),
    'everyday': ('practice', 'constraint', 'story_use'),
    'characters': contracts.CHARACTERS,
    'mysteries': ('truth', 'disclosure', 'causal_role'),
    'mechanisms': ('principle', 'cost', 'limits', 'failure_condition'),
    # opening/5. `powers` mirrors the world gate's rank ladder field by field; `cosmology` is a space
    # or plane: its name, who lives there, what law holds, and how one enters.
    'powers': ('name', 'condition', 'gain', 'cost', 'limit'),
    'cosmology': ('name', 'inhabitant', 'law', 'entry'),
}
LABELS = {'geography': '地理与通行', 'history': '历史与当下影响', 'rules': '世界规则', 'factions': '势力与利益',
          'economy': '资源与经济', 'society': '社会制度', 'everyday': '生活日常', 'characters': '人物与关系',
          'mysteries': '隐秘信息与披露', 'mechanisms': '特殊机制与代价',
          'powers': '力量与位阶阶梯', 'cosmology': '空间与位面'}
ALL_SECTIONS = tuple(SECTIONS)
# Baseline domains; rank and plane records are required when the opening declares them.
BASE_SECTIONS = ('geography', 'history', 'rules', 'factions', 'economy', 'society', 'everyday',
                   'characters', 'mysteries', 'mechanisms')
GRAND_SECTIONS = ('powers', 'cosmology')
# Deep fields a record may carry. None of them is required; a field that is written must say
# something, because a placeholder in a deep field reads exactly like a decision that was never made.
OPTIONAL_FIELDS = {
    'history': ('epoch', 'carryover'),
    'geography': ('scale', 'counter_space'),
    'factions': ('survives_scale_up',),
    'mysteries': ('reveal_window', 'survival'),
}
# Which sections a world must fill, by scale tier. A world is read by every later dispatch, so its
# floor has to be the world this book's line actually walks through. Declared once and read by both
# the brief and this validator, because a brief that asks for a small world while the check demands
# ten domains is a requirement disagreeing with its own check — a real micro project paid for that in
# four repair rounds and 55 records. Sections outside the tier stay in the shape and may be empty.
# The grand domains are in no tier's floor: they become required through what the opening declared
# (see `declared_sections`), which is also what the §5 bindings check.
TIER_SECTIONS = {
    't0': ('rules', 'society', 'everyday', 'characters', 'mysteries', 'mechanisms'),
    't1': ('geography', 'rules', 'society', 'everyday', 'characters', 'mysteries', 'mechanisms'),
    't2': ('geography', 'history', 'rules', 'society', 'everyday', 'characters', 'mysteries', 'mechanisms'),
    't3': BASE_SECTIONS,
    't4': BASE_SECTIONS,
    't5': BASE_SECTIONS,
}


def _ordered(names):
    """A set of section names in the one canonical order this file declares."""
    wanted = set(names)
    return tuple(section for section in SECTIONS if section in wanted)


def declared_sections(choices):
    """What the opening declared the world must therefore carry.

    The world gate's currency lands in `economy` and its rank ladder in `powers`; a 格局 ladder that
    reaches a 界 or wider lands in `cosmology`. A direct import may declare none. A selection that is not the
    declared shape yields nothing rather than raising: the gate owns that shape, the world model
    only reads it.
    """
    extra = []
    world_choice = choices.get('world') if isinstance(choices, dict) else None
    if isinstance(world_choice, dict) and world_choice.get('resource'):
        extra.append('economy')
    if isinstance(world_choice, dict) and world_choice.get('tiers'):
        extra.append('powers')
    if isinstance(world_choice, dict) and world_choice.get('architecture'):
        extra.extend(section for _key, _note, section, _field in contracts.WORLD_ARCHITECTURE)
    ladder_choice = choices.get('ladder') if isinstance(choices, dict) else None
    rows = ladder_choice.get('ladder') if isinstance(ladder_choice, dict) else None
    scopes = {row.get('scope') for row in rows or [] if isinstance(row, dict)}
    if scopes & set(contracts.COSMOLOGY_SCOPES):
        extra.append('cosmology')
    return tuple(extra)


def required_sections(tier_id=None, choices=None):
    """The sections this tier's world must fill: the tier's floor plus what the opening declared."""
    base = TIER_SECTIONS.get(tier_id) or ALL_SECTIONS
    return _ordered(tuple(base) + declared_sections(choices))


def index(model):
    return {section + ':' + row['id']: row for section in SECTIONS for row in model.get(section, [])}


def _bindings(model, choices):
    """Declared opening decisions must exist in their world records, word for word.

    Each is checked only when the opening declared it, so an imported setting is not
    asked about decisions nobody made. Extra records are allowed — the world may be grander than the
    ladder the gates chose.
    """
    complaints = []
    world_choice = (choices or {}).get('world') or {}
    for row in world_choice.get('tiers') or []:
        if not isinstance(row, dict):
            continue
        match = next((item for item in model.get('powers') or [] if item.get('name') == row.get('name')), None)
        same = match is not None and all(match.get(field) == row.get(field) for field in SECTIONS['powers'])
        if not same:
            complaints.append({'rule': 'world_tiers→powers 逐字等值（name/condition/gain/cost/limit）',
                               'expect': {field: row.get(field) for field in SECTIONS['powers']},
                               'got': ({field: match.get(field) for field in SECTIONS['powers']}
                                       if match else None)})
    resource = world_choice.get('resource') or {}
    if resource:
        name, allocator = resource.get('name'), resource.get('allocator')
        match = next((item for item in model.get('economy') or [] if item.get('resource') == name), None)
        # The allocator has to be named where allocation is described. Searching the whole record let
        # a short allocator be satisfied by coincidence in another field (adversarial review F1);
        # `distribution` is the field the brief tells the world dispatch to write it into.
        distribution = (match or {}).get('distribution') or ''
        if match is None or not text(allocator) or allocator not in distribution:
            complaints.append({'rule': 'world_resource→economy 同名 resource，且 allocator 出现在该记录的 distribution 里',
                               'expect': {'resource': name, 'allocator': allocator},
                               'got': ({'resource': match.get('resource'),
                                        'distribution': match.get('distribution')} if match else None)})
    for row in ((choices or {}).get('ladder') or {}).get('ladder') or []:
        stage = row.get('stage') if isinstance(row, dict) else None
        if not text(stage):
            continue
        holders = [section for section in ('geography', 'cosmology', 'factions', 'powers')
                   if any(item.get('name') == stage for item in model.get(section) or [])]
        if not holders:
            complaints.append({'rule': 'world_ladder 每一级 stage 在 geography/cosmology/factions/powers 有同名 name 记录',
                               'expect': stage, 'got': []})
    frame = world_choice.get('architecture')
    if frame is not None:
        fields = {row[0] for row in contracts.WORLD_ARCHITECTURE}
        require(isinstance(frame, dict) and set(frame) == fields
                and all(text(frame.get(key)) for key in fields), 'world_alignment',
                '开书世界架构缺少完整声明。', {'expected_fields': sorted(fields)})
        for key, _note, section, field in contracts.WORLD_ARCHITECTURE:
            if not any(item.get(field) == frame[key] for item in model.get(section) or []):
                complaints.append({'rule': 'world.architecture.' + key + '→' + section + '.' + field,
                                   'expect': frame[key], 'got': '没有逐字承接的世界记录'})
    require(not complaints, 'world_alignment', '世界模型与门里声明的设定没有逐字对上。',
            {'rule': '位阶、硬通货、格局阶梯和已声明的世界架构必须按字段承接',
             'expect': 'powers 全字段等值；economy 同名 resource，且 allocator 出现在 distribution；'
                       '阶梯每级在 geography/cosmology/factions/powers 有同名 name',
             'got': complaints, 'mismatches': len(complaints),
             'recover': '把门里选定的那一行逐字写进对应领域的记录；世界可以比阶梯更长，但不能对不上。'})


def _required_from(sections, choices):
    """The required set from however this caller names it: a tier id, an explicit list, or nothing."""
    if isinstance(sections, str):
        return required_sections(sections, choices)
    if sections is not None:
        return _ordered(tuple(sections) + declared_sections(choices))
    tier = ((choices or {}).get('scale') or {}).get('tier')
    return required_sections(tier, choices)


def validate(data, choices, selection_hash, sections=None):
    required = _required_from(sections, choices)
    require(isinstance(data, dict) and data.get('selection_hash') == selection_hash
            and text(data.get('premise')) and text(data.get('story_capacity')), 'world', '世界需要准确选择版本、核心前提和长篇承载说明。',
            {'fields': ['selection_hash', 'premise', 'story_capacity'],
             'expect': 'selection_hash 与冻结选择一致；premise 与 story_capacity 为非空文本',
             'got': ({'selection_hash': data.get('selection_hash'), 'premise': data.get('premise'),
                      'story_capacity': data.get('story_capacity')} if isinstance(data, dict) else None)})
    require(data['premise'] == choices['world']['world_premise'], 'world_alignment', '世界前提须与所选方案逐字一致。',
            {'rule': '逐字相等；不是包含、缩写或改写', 'expect': choices['world']['world_premise'],
             'got': data.get('premise'), 'source': 'opening_choices.world.world_premise',
             'recover': '把 premise 改回所选原文（逐字）；要改前提先回开书门重选，不在世界任务里改写。'})
    model = copy.deepcopy(data)
    all_ids = set()
    owners = {}
    for section, fields in SECTIONS.items():
        rows = model.get(section)
        require(isinstance(rows, list), 'world_section', '世界缺少结构领域：' + section)
        require(bool(rows) or section in ('mechanisms',) or section not in required, 'world_section',
                '本档位/本次选择要求填写的世界领域必须有实际内容：' + section,
                {'required_sections': list(required), 'recover': '按档位与门里选定的设定只填这条主线走得到的领域，其余留空数组。'})
        for row in rows:
            require(isinstance(row, dict) and text(row.get('id')) and all(text(row.get(k)) for k in fields), 'world_record', '世界记录缺少具体内容：' + section,
                    {'section': section, 'id': row.get('id') if isinstance(row, dict) else None,
                     'expect': 'id 与该域全部字段写成非空文本；空字符串或占位词等于没写却占了位。'})
            if section == 'characters':
                validate_character(row)
            key = section + ':' + row['id']
            all_ids.add(key)
            owners.setdefault(row['id'], []).append(section)
            require(isinstance(row.get('links'), list) and all(text(ref) for ref in row['links']), 'world_links', '世界记录须声明关联引用，独立记录可用空数组。',
                    {'record': key, 'expect': 'links 是由 领域:id 组成的数组，独立记录用空数组',
                     'got': row.get('links')})
            for field in OPTIONAL_FIELDS.get(section, ()):
                if field in row:
                    require(text(row[field]), 'world_optional', '世界记录的可选深字段要么不写，写了就必须是非空文本。',
                            {'record': key, 'field': field, 'got': str(row[field])[:120],
                             'recover': '补成具体文字，或删掉这个键；空字符串等于没写却占了位。'})
    # The bare id is the handle later dispatches use without the section prefix (a resource key,
    # a place, an entity), so two domains sharing one id make that handle ambiguous even though
    # the section-qualified links still resolve. The refusal names the colliding records and every
    # record whose links point at them, so renaming one id and syncing those links stays inside
    # exactly the records a narrow repair is allowed to touch.
    for ident, sections in owners.items():
        if len(sections) < 2:
            continue
        keys = {section + ':' + ident for section in sections}
        referenced_by = sorted(section + ':' + row['id']
                               for section in SECTIONS for row in model[section]
                               for ref in row.get('links', []) if ref in keys)
        require(False, 'world_id', '世界记录的裸 id 在全部领域间必须唯一。',
                {'id': ident, 'sections': list(sections),
                 'expect': '一个裸 id 只属于一个领域', 'got': ident + ' 同时出现在 ' + '、'.join(sections),
                 'referenced_by': referenced_by,
                 'recover': '只改撞名记录：给其中一个换 id，并同步更新 referenced_by 里这些记录的 links；其余记录保持逐字不变。'})
    for section in SECTIONS:
        for row in model[section]:
            missing = [ref for ref in row['links'] if ref not in all_ids]
            require(not missing, 'world_reference', '世界关联引用不存在。',
                    {'record': section + ':' + row['id'], 'missing': missing,
                     'expect': 'links 只能引用本世界里已存在的 领域:id 记录；独立记录用空数组'})
    names = [name for c in model['characters'] for name in [c['name'], *c.get('aliases', [])]]
    duplicated = next((name for name in names if names.count(name) > 1), None)
    require(duplicated is None, 'world_identity', '世界人物称呼不能歧义。',
            ({'duplicate': duplicated,
              'records': ['characters:' + row['id'] for row in model['characters']
                          if duplicated in [row['name'], *row.get('aliases', [])]],
              'expect': 'characters 的 name 与 aliases 不跨人物重复',
              'recover': '只改撞名记录：给其中一条换个称呼并同步它处的引用；其余记录保持逐字不变。'}
             if duplicated is not None else
             {'expect': 'characters 的 name 与 aliases 不跨人物重复'}))
    # Geography is the other section later work addresses by name: chapter outlines declare moves
    # as place names before the engine normalizes them to ids, so two same-named places make the
    # target ambiguous. The refusal names both records, so a narrow repair renames exactly one.
    seen_places = {}
    for row in model['geography']:
        seen_places.setdefault(row['name'], []).append('geography:' + row['id'])
    for name, records in seen_places.items():
        require(len(records) == 1, 'world_identity', '世界地点名称不能歧义。',
                {'duplicate': name, 'records': records,
                 'expect': 'geography 的 name 互不相同', 'got': name + ' 有 ' + str(len(records)) + ' 条',
                 'recover': '只改撞名记录：给其中一条换个 name（或合并为一条并同步它的 links）；其余记录保持逐字不变。'})
    protagonist = choices['protagonist']
    require(any(c['id'] == protagonist['id'] and c['name'] == protagonist['name'] and c['desire'] == protagonist['desire']
                and c['limit'] == protagonist['limit'] for c in model['characters']), 'world_alignment', '世界模型须保留所选主角的身份、欲望和底线。',
            {'rule': 'characters 里须有一条记录的 id/name/desire/limit 与所选主角逐字相同',
             'expect': {k: protagonist[k] for k in ('id', 'name', 'desire', 'limit')},
             'source': 'opening_choices.protagonist'})
    mode = choices['world']['mechanism']['mode']
    require((mode == 'none' and not model['mechanisms']) or (mode == 'bounded' and bool(model['mechanisms'])), 'world_alignment', '世界机制必须遵守已选的无机制或有限机制方向。',
            {'selected_mode': mode,
             'rule': '所选 mode=none 时 mechanisms 必须为空数组；mode=bounded 时至少一条',
             'records': ['mechanisms:' + row['id'] for row in model['mechanisms']],
             'source': 'opening_choices.world.mechanism.mode'})
    _bindings(model, choices)
    require(set(data) <= {'selection_hash', 'premise', 'story_capacity', *SECTIONS}, 'world_fields', '世界模型不得夹带正文事件或事实结算。',
            {'got': sorted(set(data) - {'selection_hash', 'premise', 'story_capacity', *SECTIONS}),
             'expect': '顶层键只能是 selection_hash/premise/story_capacity 与十二个领域数组',
             'recover': '删掉夹带的键，把事件与事实留给章纲的增量声明。'})
    return model
