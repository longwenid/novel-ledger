"""Query/assembly layer. Sources are immutable; selection never erases availability."""
from __future__ import annotations

import copy
import json
from .contracts import (DEFAULTS, SCALE_TIERS, TASK, WORLD_ARCHITECTURE, Job, require, tier_of)
from .contracts import (EDITORIAL_CAPABILITY, HOOK_LINKS_CAPABILITY,
                        SCENE_IDENTITY_CAPABILITY,
                        SCENE_MEMORY_CAPABILITY, UNDERSTANDING_CAPABILITY, VOLUME_OUTLINE_CAPABILITY)
from . import briefs, creation, narrative, style, world, editorial, story_memory, understanding
from .planning import policy_material, resolve_outline_policy, volume_for
from .ports import ContextStore
from .envelope import validate_work

# Capability names as they appear in a frozen task's capability map.
EDITORIAL = 'editorial'
UNDERSTANDING = 'understanding'
SCENE_IDENTITY = 'scene_identity'
READING_DEPENDENCIES = 'reading_dependencies'
VOLUME_OUTLINE = 'volume_outline'
SCENE_MEMORY = 'scene_memory'
HOOK_LINKS = 'hook_links'

# Stages whose decision needs the volume boundary table (which volume a chapter belongs to). A scene
# dispatch does not: the chapter is already named by the task, so requiring the table there would be
# the one piece of required material that grows with the book's structure for no decision of its own.
LAYOUT_STAGES = ('volume_outline', 'chapter_outline')
# Records that are a narrower view of another record, declared where the material is selected so the
# relationship is a decision rather than something a reader has to infer from two similar payloads.
# A projection is required only when the record it projects is not: a scene dispatch reads the rules
# through `world_core`, a design dispatch reads the `world_model` they come from, never both.
PROJECTIONS = (
    ('world_core', 'world_model'),
)


# What each stage must read to make its own decision, as opposed to what it may read if it needs to.
# Measured from what the engine actually hands out, and written down here so that giving a stage more
# material is a visible decision rather than one more `add(...)` line: the guard in tests/support.py
# compares every frozen dispatch against this table, so an undeclared record fails the suite that
# covers that stage. Records that several stages share (contract, state, world_model, ...) are still
# listed per stage — "why does this stage read this" is exactly what the table is for.
#
# v2 note: with the review stages removed there is no longer a "background stays on demand" half of a
# review decision, so every row here is the whole required set. `chapter_outline` is the hard
# prerequisite of a draft: it carries the enter/exit state chain the writer must satisfy, and the
# `drift_check` it submits is reconciled against exactly this row.
STAGE_MATERIAL = {
    'opening_options': ('opening_choices', 'opening_rejections'),
    'world_model': ('author_feedback', 'opening_basis', 'opening_choices', 'previous_proposal'),
    'opening_contract': ('author_feedback', 'opening_basis', 'opening_choices', 'world_model'),
    'volume_outline': ('author_feedback', 'contract', 'effective_layout', 'hooks', 'opening_basis',
                       'opening_choices', 'revision_impact', 'revision_instruction', 'state',
                       'style', 'world_model'),
    'chapter_outline': ('author_feedback', 'contract', 'design_drift', 'effective_layout', 'hooks',
                        'previous_chapters', 'previous_chapter:', 'revision_impact', 'revision_instruction', 'state',
                        'style', 'volume_outline', 'world_model'),
    'write': ('author_feedback', 'chapter_outline', 'contract', 'continuity_feedback', 'creative_memory', 'design_drift',
              'disclosure_boundary', 'hooks', 'previous_chapters', 'previous_chapter:', 'scene_context', 'scene_sources',
              'state', 'style', 'style_anchor', 'volume_outline', 'word_budget', 'world_core',
              'world_records'),
    'repair': ('author_feedback', 'base_draft', 'chapter_outline', 'contract', 'continuity_feedback', 'creative_memory',
               'design_drift', 'disclosure_boundary', 'hooks', 'previous_chapters', 'previous_chapter:', 'prior_candidate',
               'revision_impact', 'revision_instruction', 'scene_context', 'scene_sources', 'state',
               'style', 'style_anchor', 'volume_outline', 'word_budget', 'world_core', 'world_records'),
    'redesign': ('author_feedback', 'base_draft', 'chapter_outline', 'contract', 'continuity_feedback', 'creative_memory',
                 'design_drift', 'disclosure_boundary', 'hooks', 'previous_chapters', 'previous_chapter:', 'prior_candidate',
                 'revision_impact', 'revision_instruction', 'scene_context', 'scene_sources', 'state',
                 'style', 'style_anchor', 'volume_outline', 'word_budget', 'world_core', 'world_records'),
}


def undeclared_material(stage, required):
    """Required records this stage never declared, as a sorted list of names."""
    declared = set(STAGE_MATERIAL.get(stage) or ())
    prefixes = tuple(name for name in declared if name.endswith(':'))
    return sorted(name for name in required if name not in declared and not name.startswith(prefixes))


def projects_from(name):
    for narrow, wide in PROJECTIONS:
        if narrow.endswith(':'):
            if name.startswith(narrow):
                return wide + name[len(narrow):]
        elif name == narrow:
            return wide
    return None


def thin_required(records, required):
    """Drop required names that would charge the worker twice for one fact.

    Two cases, one pass: a record whose content is byte-identical to another required record, and a
    projection whose source is also required. Nothing is erased — a dropped name stays in `records`
    and in `on_demand`.
    """
    keep = []
    by_content = {}
    for name in required:
        source = projects_from(name)
        if source is not None and source in required:
            continue
        ident = records[name]
        if ident in by_content:
            continue
        by_content[ident] = name
        keep.append(name)
    return keep


def _planned_nodes(plan):
    """Nodes from chapter declarations and their materialized settlement projection."""
    ids = set(plan.get('node_ids') or ())
    for row in (plan.get('plot') or {}).get('nodes') or ():
        if isinstance(row, dict) and row.get('node'):
            ids.add(row['node'])
    return ids


def _complete_dependencies(plan):
    """A flag without actual per-scene declarations does not justify dropping background."""
    scenes = plan.get('scenes') or []
    return (plan.get('dependency_coverage') == 'complete' and bool(scenes)
            and all(isinstance(scene, dict) and isinstance(scene.get('reads'), list)
                    and isinstance(scene.get('depends_on'), list) for scene in scenes))


def _spatial_scope(state, participants, plan, inputs):
    """Keep declared locations plus the custody, route and parent chains that make them true.

    Called only for a complete dependency declaration. A partial declaration keeps the full
    spatial background: absence from an incomplete list is not evidence of irrelevance.
    """
    people = set(participants)
    people.update(key for kind, key in inputs
                  if kind in ('entities', 'placements', 'character_current', 'developments'))
    people.update(key.split(':', 1)[0] for kind, key in inputs if kind in ('facts', 'knowledge'))
    custody = state.get('custody', {})
    # A held object is located through its holder; a carrier's arrival bound includes everything
    # carried. Keep both directions, including nested containers, without following unrelated cast.
    related = {ident: set() for ident in state['entities']}
    for item, holder in custody.items():
        related.setdefault(item, set()).add(holder)
        related.setdefault(holder, set()).add(item)
    todo = list(people)
    while todo:
        for ident in related.get(todo.pop(), ()):
            if ident not in people:
                people.add(ident)
                todo.append(ident)
    places = state['places']
    locations = {place for entity, place in state['placements'].items() if entity in people}
    names = {}
    for ident, row in places.items():
        names.setdefault(row.get('name'), set()).add(ident)

    def location(value):
        if isinstance(value, str):
            if value in places:
                locations.add(value)
            locations.update(names.get(value, ()))

    link_ids = set()
    for movement in plan.get('places') or []:
        location(movement.get('from'))
        location(movement.get('to'))
        link_ids.update(movement.get('links') or [])
    for row in (plan.get('enter') or []) + (plan.get('exit') or []) + (plan.get('preconditions') or []):
        if row.get('kind') in ('places', 'place', 'placements'):
            location(row.get('expected'))
    for reference in plan.get('world_refs') or []:
        if isinstance(reference, str) and reference.startswith('geography:'):
            location(reference.split(':', 1)[1])
    links = state.get('links', {})
    for ident in link_ids:
        link = links.get(ident, {})
        location(link.get('a'))
        location(link.get('b'))
    # Preserve existing direct constraints between selected places, even if a writer is tempted
    # to omit a declared path or confuse a sound/sight link with a route.
    link_ids.update(ident for ident, link in links.items()
                    if link['a'] in locations and link['b'] in locations)
    todo = list(locations)
    while todo:
        parent = places.get(todo.pop(), {}).get('parent')
        if parent is not None and parent not in locations:
            locations.add(parent)
            todo.append(parent)
    return people, locations, link_ids


def scoped_state(state, participants, plan=None, chapter=0, horizon=3, *, allow_dependency_scope=True):
    plan = plan or {}
    inputs = story_memory.reads(plan) if plan else set()
    complete = allow_dependency_scope and _complete_dependencies(plan)
    selected = set(participants)
    if complete:
        selected, locations, links = _spatial_scope(state, selected, plan, inputs)
    view = copy.deepcopy(state)
    for field in ('entities', 'placements', 'developments'):
        view[field] = {k: v for k, v in state[field].items() if k in selected}
    view['facts'] = {k: v for k, v in state['facts'].items() if k.split(':', 1)[0] in selected}
    topics = set(plan.get('reader_refs', [])) | {d['topic'] for d in plan.get('disclosures', [])}
    topics.update(key for kind, key in story_memory.reading_refs(plan) if kind == 'disclosure')
    view['knowledge'] = {k: v for k, v in state['knowledge'].items()
                         if k.split(':', 1)[0] in selected and
                         (not complete or k.split(':', 1)[1] in topics or ('knowledge', k) in inputs)}
    if complete:
        view['places'] = {k: v for k, v in state['places'].items() if k in locations}
        for field in ('custody', 'arrivals'):
            if field in state:
                view[field] = {k: v for k, v in state[field].items() if k in selected}
        if 'anchors' in state:
            view['anchors'] = {k: v for k, v in state['anchors'].items()
                               if k.split(':', 1)[0] in selected | locations}
        if 'links' in state:
            view['links'] = {k: v for k, v in state['links'].items() if k in links}
            for link in view['links'].values():
                for key in link.get('requires', {}):
                    if key in state['facts']:
                        view['facts'][key] = state['facts'][key]
    view['resources'] = {k: v for k, v in state['resources'].items() if json.loads(k)[0] in selected}
    view['relations'] = {k: v for k, v in state['relations'].items() if k.split('>')[0] in selected or k.split('>')[1].split(':')[0] in selected}
    view['historical_assertions'] = {k: v for k, v in state['historical_assertions'].items() if selected.intersection(v['subjects'])}
    refs = set(plan.get('reader_refs', [])) | {d['topic'] for d in plan.get('disclosures', [])}
    view['hooks'] = {k: v for k, v in state['hooks'].items()
                     if v['status'] == 'open' and
                     (k in plan.get('hook_refs', []) or v['due'] <= chapter + horizon
                      or selected.intersection(v.get('subjects', [])) or refs.intersection(v.get('topics', [])))}
    view['developments'] = {k: v[-2:] for k, v in view['developments'].items()}
    if 'story_nodes' in state:
        nodes = _planned_nodes(plan)
        for definition in plan.get('node_contracts', {}).values():
            nodes.update(definition['depends_on'])
        view['story_nodes'] = {k: v for k, v in state['story_nodes'].items() if k in nodes}
        view['character_current'] = {k: v for k, v in state['character_current'].items() if k in selected}
        view['reader_knowledge'] = {k: v for k, v in state['reader_knowledge'].items() if k in refs or v['chapter'] >= chapter - 2}
        view['historical_assertions'] = {k: v for k, v in view['historical_assertions'].items() if k in plan.get('history_refs', [])}
        # Finished lines are history, while active and sleeping lines remain live obligations.
        # Explicit inputs below restore even a resolved line when this chapter reads it.
        view['thread_progress'] = {k: v for k, v in state['thread_progress'].items()
                                   if v.get('status') != 'resolved'}
        view['memory_sources'] = 'complete_state 保留全部状态和人物发展；历史原文经 history_source/recall 完整补读。未选择不代表不存在。'
    # Explicit causal inputs may refer to an off-stage character or a remote promise.
    # Participant heuristics must never erase those coordinates.
    for kind, key in inputs:
        present, value = story_memory.lookup(state, kind, key)
        field = 'story_nodes' if kind == 'node' else kind
        if present and kind != 'clock':
            view.setdefault(field, {})[key] = value
    conservative_reason = ('场景依赖声明不完整，保留参与人的全部知情与完整空间资料；未声明不视为无关。'
                           if allow_dependency_scope else
                           '设计任务可能决定后续章节，不能用起章旧依赖裁剪设计范围；保留参与人的全部知情与完整空间资料。')
    view['material_scope'] = {
        'mode': 'declared_dependencies' if complete else 'conservative',
        'source': 'complete_state',
        'note': ('知情与空间按完整场景依赖选择；站位、持有链、移动路径及父地点完整保留。'
                 if complete else conservative_reason)
                + '未选来源可按 complete_state 补读，缺失项不代表事实不存在。'}
    return view


def _brief(book, job):
    """The one page this dispatch needs, generated here instead of shipping whole guides."""
    previous = []
    version_of_book = creation.opening_version(book.get('creation') or {})
    for row in (book.get('creation') or {}).get('selections', []):
        gate = row['gate']
        previous.append((creation.gate_title(gate, version_of_book), _selection_line(row['option'])))
    payload = job.payload or {}
    if job.stage == 'opening_options':
        return briefs.opening_options(payload.get('gate', {}), payload.get('lens_brief', ''), previous,
                                      creation.opening_version(book['creation']))
    if job.stage == 'world_model':
        # The brief and the validator read the same declaration: the tier's base domains plus the
        # domains this opening's own gates declared (a tier ladder needs `powers`, a grand scale
        # needs `cosmology`), so the world the worker is asked for is the world the check accepts.
        tier = scale_tier(book)
        choices = creation.selected(book['creation']) if book.get('creation') else {}
        return briefs.world_model(previous=previous, repair=bool(payload.get('repair')),
                                  scale=_scale_line(book),
                                  sections=world.required_sections(tier['id'] if tier else None, choices))
    text = briefs.stage(job.stage, {**payload, 'editorial': editorial.enabled(book)})
    if job.stage == 'volume_outline' and previous:
        # The volume outline is the first dispatch that has to build on every closed gate at once;
        # naming the chosen directions in the brief costs one line each and saves a round trip.
        text += ('\n\n## 已选方向（不得推翻，卷纲必须承接）\n'
                 + '\n'.join('- %s：%s' % (name, line) for name, line in previous))
    return text


def scale_tier(book):
    """The tier row this project was sized to, or None when no tier is known yet.

    The contract is the tier's usual carrier, but the world dispatch runs before it exists —
    world and contract ride in one receipt — so the frozen scale choice is the only declaration
    available there. Reading it keeps the tier-scoped domain list the brief and the validator
    share.
    """
    tier = tier_of(book.get('contract') or {})
    if tier is not None:
        return tier
    chosen = creation.selected(book.get('creation') or {}) if book.get('creation') else {}
    tier_id = (chosen.get('scale') or {}).get('tier')
    return next((row for row in SCALE_TIERS if row['id'] == tier_id), None)


def _scale_line(book):
    """The chosen size class, spelled out for the world brief."""
    contract = book.get('contract') or {}
    volumes = contract.get('volumes') or []
    tier = scale_tier(book)
    if volumes:
        last = volumes[-1]['end']
        return '%s，%d 卷共 %d 章，每章 %s～%s 汉字' % (
            (tier['name'] + '档') if tier else '已定体量', len(volumes), last,
            contract.get('chapter_min'), contract.get('chapter_max'))
    if tier:
        # Pre-contract dispatch: the tier row already proves the volume count and chapter band,
        # so the size section is not silently dropped on the one dispatch that needs it most.
        return '%s，%d 卷共 %d 章，每章 %s～%s 汉字' % (
            tier['name'] + '档', tier['volume_count'], tier['chapters'],
            tier['chapter_min'], tier['chapter_max'])
    return ''


# The nested decision maps an opening gate hands back: each is read by a later gate, so the line
# expands the fields that decide direction rather than printing the object.
SELECTION_MAPS = (
    ('architecture', tuple(row[0] for row in WORLD_ARCHITECTURE)),
    ('scale', ('opening', 'terminal', 'unchanged')),        # 格局尺度：开局边界/终局等级/跨卷不变
    ('resource', ('name', 'allocator')),                    # 硬通货与分配者
    ('anchor', ('deliverable', 'deadline_chapter')),        # 主题锚点与最迟兑现章
)
# The flat decisions a later gate must keep, in the order the line reads them. The short ones come
# first because they decide everything downstream (which rule the world adds, how the protagonist
# stands toward it, what the terminal rung is); the prose fields follow and take whatever budget is
# left. The v1–v4 keys keep their relative order inside their group, so their lines render as before.
SELECTION_SHORT = ('genre', 'novelty', 'first_cause', 'stance', 'dark_side', 'terminal', 'opening',
                   'unchanged', 'advantage', 'identity', 'title', 'pov', 'tone')
SELECTION_PROSE = ('reader_promise', 'opposition', 'world_premise', 'story_engine', 'ending',
                   'voice', 'relationships', 'origin')


def _selection_parts(value):
    """The (label, text) pairs a later gate should see: decisions first, then maps, then prose.

    A gate's value is a mix: flat decisions (novelty, stance, world_premise) and structured ones
    (the ladder's scale map, the hard currency, the promise anchor). The short decisions read first
    because they carry the direction a later gate has to keep; the structured maps are expanded per
    field so a later gate sees "terminal=体系" instead of an object it would have to open; the long
    prose fields fill whatever budget is left, because a truncated sentence costs less than a lost
    decision.
    """
    seen = set()

    def emit(label, entry, cap=24):
        if label in seen or not isinstance(entry, str) or not entry.strip():
            return None
        seen.add(label)
        text = entry.strip()
        return label, text if len(text) <= cap else text[:cap] + '…'

    def scalar(key):
        entry = value.get(key)
        # A relation gate's gist is its first relation: an empty list is never a chosen direction.
        if isinstance(entry, list) and entry and isinstance(entry[0], str) and entry[0].strip():
            entry = entry[0]
        return emit(key, entry)

    for key in SELECTION_SHORT:
        pair = scalar(key)
        if pair:
            yield pair
    for key, fields in SELECTION_MAPS:
        entry = value.get(key)
        if not isinstance(entry, dict):
            continue
        for field in fields:
            pair = emit(field, entry.get(field))
            if pair:
                yield pair
    ladder = value.get('ladder')
    if isinstance(ladder, list):
        stages = [row['stage'].strip() for row in ladder
                  if isinstance(row, dict) and isinstance(row.get('stage'), str) and row['stage'].strip()]
        if stages:
            pair = emit('ladder', '→'.join(stages))
            if pair:
                yield pair
    for key in SELECTION_PROSE:
        pair = scalar(key)
        if pair:
            yield pair


def _selection_line(option, budget=240):
    """One compact line per closed choice: the direction, not a copy of the record.

    A later gate builds on everything already decided, so the line has to carry the fields that
    decide direction — the channel and setting, the promise, the edge, the view — not whichever
    single field happened to come first. Reading only one field is how a protagonist gate produced
    three consistent-sounding people in another era: the chosen genre text never reached it. The
    exact values still live in opening_choices and are re-checked when the contract is formed, so
    this line stays a summary under a fixed budget rather than a second copy of the record. The
    budget and the per-field cap grew with opening/5: a brainstorm gate, a ladder and a hard currency
    are three more decisions every later gate has to keep, and dropping a whole category costs a
    round trip while truncating one sentence costs nothing.
    """
    parts = []
    for key, entry in _selection_parts(option.get('value', {})):
        parts.append(key + '=' + entry)
        if sum(len(part) for part in parts) >= budget:
            break
    line = option.get('title', '')
    if parts:
        joined = '；'.join(parts)
        line += '：' + (joined[:budget] + '…' if len(joined) > budget else joined)
    return line


# The chapter a dispatch is about, as the settlement contract v2 uses it: the chapter outline row.
# `book['plans']` is that row materialized for settlement (the row the engine reconciles a
# drift_check against), so it wins; `book['chapter_outlines']` is the design record and is the
# fallback for a chapter whose settlement row does not exist yet.
def chapter_row(book, chapter):
    plan = (book.get('plans') or {}).get(str(chapter))
    if isinstance(plan, dict):
        return plan
    for rows in (book.get('chapter_outlines') or {}).values():
        for row in rows or ():
            if isinstance(row, dict) and row.get('chapter') == chapter:
                return row
    return None


def design_row(book, chapter):
    """The chapter's design row: the declaration the writer executes, independent of settlement.

    `chapter_row` prefers the materialized settlement row; the style declaration is read from here so
    a materialization that has not copied a field yet cannot silently drop the chapter's own style.
    """
    for rows in (book.get('chapter_outlines') or {}).values():
        for row in rows or ():
            if isinstance(row, dict) and row.get('chapter') == chapter:
                return row
    return None


def volume_row(book, volume):
    return (book.get('volumes_outline') or {}).get(volume['id']) if volume else None


def writing_volume_outline(outline, plan, chapter, source_hash):
    """Keep full prose direction and complete relevant records, with the full source available."""
    view = copy.deepcopy(outline)
    registry = {row['id']: row for row in outline.get('nodes', [])}
    selected = _planned_nodes(plan)
    selected.update(row['id'] for row in registry.values()
                    if isinstance(row.get('window'), list) and len(row['window']) == 2
                    and row['window'][0] <= chapter <= row['window'][1])
    for item in plan.get('enter', []) + plan.get('exit', []):
        if item.get('kind') == 'node':
            selected.add(item['key'])
    todo = list(selected)
    while todo:
        ident = todo.pop()
        for dependency in registry.get(ident, {}).get('depends_on', []):
            if dependency not in selected:
                selected.add(dependency)
                todo.append(dependency)
    view['nodes'] = [row for row in view.get('nodes', []) if row['id'] in selected]
    lines = {row.get('line') for row in view['nodes']}
    lines.update(row['thread'] for row in (plan.get('plot') or {}).get('threads', []))
    lines.update(item['key'] for item in plan.get('enter', []) + plan.get('exit', [])
                 if item.get('kind') == 'thread')
    view['threads'] = [row for row in view.get('threads', []) if row['id'] in lines]
    view['source'] = {'record': 'complete_volume_outline', 'hash': source_hash,
                      'chapter': chapter,
                      'note': '仅筛选本章节点、前置依赖与所在线路；方向、转折、伏笔、文风及卷末声明保留完整。'
                              '未选记录仍可按 complete_volume_outline 补读。'}
    return view


def hook_ledger(book, volume=None, refs=None):
    """The promise account a design decision reads: what is declared, and what is still open.

    `declared` is every hook any approved volume has registered (cross-volume promises keep their
    id and are marked `continues`), `open` is the subset the projection still holds as `open`, and
    `volume` is this volume's own declaration. A designer continuing a promise from an earlier
    volume needs the id, the text and the original window — re-inventing any of them is how a
    promise silently becomes two.

    `refs` selects complete entries for the task, together with this volume's declarations.
    None retains the complete ledger for supplemental reading; selection never edits the source.
    """
    selected = None if refs is None else set(refs)
    declared, current = [], []
    for ident, row in (book.get('volumes_outline') or {}).items():
        rows = [entry for entry in (row or {}).get('hooks') or [] if isinstance(entry, dict)]
        for entry in rows:
            if selected is not None and entry.get('id') not in selected and (volume is None or ident != volume['id']):
                continue
            declared.append({'id': entry.get('id'), 'text': entry.get('text'),
                             'plant': entry.get('plant'), 'payoff': entry.get('payoff'),
                             'required': entry.get('required'), 'continues': entry.get('continues'),
                             'volume': ident})
            if volume is not None and ident == volume['id']:
                current.append(entry)
    open_hooks = [{'id': ident, 'text': hook.get('text', ''), 'due': hook.get('due'),
                   'status': hook.get('status')}
                  for ident, hook in sorted((book['state'].get('hooks') or {}).items())
                  if hook.get('status') == 'open' and (selected is None or ident in selected)]
    return {'volume': current, 'declared': declared, 'open': open_hooks,
            'source': '伏笔账：卷纲声明（plant/payoff 窗口、required、continues），章纲只做 plant/payoff；'
                      '中途再提一次用 hook_refs 承接，不新增动作。open 是引擎投影里仍未兑现的条目。'
                      + ('完整历史声明见 complete_hooks，未选择不代表不存在。' if selected is not None else '')}


def style_material(book, volume, chapter_row=None):
    """The style specification one dispatch writes against: contract, anchor, volume, chapter.

    The contract's `voice`/`tone`/`pov`/`style_traits` are the author's decision, the anchor is the
    chapter the author approved (its measured metrics, not the prose — that record already exists),
    the volume row states how the style moves, and the chapter row states the execution points for
    this chapter. The effective tolerances are merged here so the writer compares against the same
    numbers the engine will use.
    """
    contract = book.get('contract') or {}
    volume_style = (volume or {}).get('style') if isinstance((volume or {}).get('style'), dict) else {}
    chapter_style = (chapter_row or {}).get('style') if isinstance((chapter_row or {}).get('style'), dict) else {}
    return {'voice': contract.get('voice', ''), 'tone': contract.get('tone', ''),
            'pov': contract.get('pov', ''), 'style_traits': list(contract.get('style_traits') or []),
            'guard': contract.get('style_guard', DEFAULTS['style_guard']),
            'anchor': style.baseline(book),
            'window': style.merged_window(contract, volume_style),
            'volume': dict(volume_style), 'chapter': dict(chapter_style),
            'source': '文风规格：契约 voice/tone/pov/style_traits 是底线，anchor 是作者认可首章的实测指标，'
                      'volume.trend 是本卷走向，chapter 是本章执行点；window 是合并后的容差。'
                      'guard=observe 默认只观察首章形状变化，strict 才执行锚点容差；'
                      '显式对白目标和高重复检查仍生效，实际视角须结合正文自比。'}


def _participants(plan, book):
    """Who is on stage this chapter, from the row itself rather than a profile table.

    v2 removed the profile stage: a chapter outlines its cast as `characters` deltas and inlines
    first appearances in `new_entities`, so the participant set is read from that row.
    """
    if plan:
        named = plan.get('participants')
        if isinstance(named, list) and named:
            return list(named)
        # Raw chapter rows carry the same cast through deltas and scene presence; materialized
        # rows normally already have participants. Keep both paths consistent before falling back
        # conservatively when the author supplied no cast declaration at all.
        entities = [row.get('entity') for row in plan.get('characters') or [] if isinstance(row, dict)]
        entities += [row.get('id') for row in plan.get('new_entities') or [] if isinstance(row, dict)]
        entities += [row.get('who') for row in plan.get('knowledge') or [] if isinstance(row, dict)]
        entities += [row.get('entity') for row in plan.get('places') or [] if isinstance(row, dict)]
        entities += [ident for scene in plan.get('scenes') or [] if isinstance(scene, dict)
                     for ident in scene.get('present') or []]
        entities = [ident for ident in entities if ident]
        if entities:
            return sorted(set(entities))
    return list(book['state']['entities'])


def _dispatch_volume(book, job):
    """The volume a dispatch belongs to: named by scope for outline work, by chapter otherwise."""
    contract = book.get('contract') or {}
    volumes = contract.get('volumes') or []
    if job.scope and job.scope.startswith('volume:'):
        ident = job.scope.split(':', 1)[1]
        return next((v for v in volumes if v['id'] == ident), None)
    if job.chapter:
        return volume_for(contract, job.chapter) if contract else None
    return None


def _batch_range(job, volume, payload):
    """The chapters a chapter_outline batch answers: the dispatch's own range, else the volume.

    A re-plan names its first chapter in `from_chapter`; that value wins over the job's range so a
    receipt never has to re-submit chapters the book has already written.
    """
    first = payload.get('from_chapter') or job.first or (volume['first'] if volume else 0)
    last = job.last or (volume['end'] if volume else 0)
    if first and last and last < first:
        last = first
    return first, last


def build(repo: ContextStore, book, job):
    records, required = {}, []

    def add(name, value, needed=True):
        records[name] = repo.document(value)
        if needed:
            required.append(name)

    stage, chapter = job.stage, job.chapter
    contract = book.get('contract') or {}
    # An outline batch is not about one chapter: it starts at the dispatch's first chapter, so the
    # chapters before that batch are what its new rows have to continue from.
    anchor = chapter or (job.first if stage == 'chapter_outline' else 0)
    # The chapter's settlement contract, as the outline chain froze it.
    plan = chapter_row(book, anchor) if anchor else None
    volume = _dispatch_volume(book, job)
    volume_outline_row = volume_row(book, volume)
    scene_task = bool(plan and plan.get('scenes') and stage in ('write', 'repair', 'redesign'))
    enhanced = editorial.enabled(book)
    # A worker needs the material its stage decides on, and nothing else: the opening reads the
    # closed choices, not a contract that does not exist yet or a state that is still empty.
    opening_stage = stage in ('opening_options', 'world_model', 'opening_contract')
    merged_outline = 'chapter_outline' in ((job.payload or {}).get('also') or ())
    add('contract', book['contract'], not opening_stage)
    participants = _participants(plan, book)
    tracking = bool(contract.get('narrative_tracking'))
    # `state` is required wherever a decision reads the true before-state. A plain volume outline is
    # the one design pass that runs before any prose — it sets the whole book's trends from the
    # contract and the world — so the (still nearly empty) state stays available on demand there.
    # A merged dispatch also answers chapter outlines, whose enter/exit chain is read off that same
    # state, so there it is required.
    # An existing start chapter is not the dependency boundary of a new design batch. Only prose
    # executes a fixed chapter contract; designers may need sources for any later chapter.
    state_view = scoped_state(book['state'], participants, plan, anchor,
                              allow_dependency_scope=stage in ('write', 'repair', 'redesign'))
    add('state', state_view,
        not opening_stage and (stage != 'volume_outline' or merged_outline))
    add('complete_state', book['state'], False)
    memory_stages = ('volume_outline', 'chapter_outline', 'write', 'repair', 'redesign')
    if 'understanding' in book and not opening_stage:
        add('complete_understanding', book['understanding'], False)
        if stage in memory_stages:
            topics = set((plan or {}).get('reader_refs', [])) | {d['topic'] for d in (plan or {}).get('disclosures', [])}
            memory_refs = set(plan.get('understanding_refs', [])) if plan else set()
            available_refs = set(understanding.latest(book['understanding']))
            unavailable_refs = sorted(memory_refs - available_refs)
            selected_memory = understanding.select(book['understanding'], participants, topics, chapter,
                                                    memory_refs & available_refs)
            if selected_memory or unavailable_refs:
                add('creative_memory', {'interpretations': selected_memory,
                    'unavailable_refs': unavailable_refs,
                    'boundary': '这是可修订的作品理解，含原文样本和反证，不是事实或写作命令；作者约定仍为方向来源。'})
    if enhanced:
        add('effective_layout', editorial.effective_contract(book)['volumes'], stage in LAYOUT_STAGES)
        if book.get('style_anchor'):
            add('style_anchor', book['style_anchor'])
    design_stages = ('volume_outline', 'chapter_outline')
    writing_stages = ('write', 'repair', 'redesign')
    if stage in design_stages or stage in writing_stages:
        # The promise account and the style specification every design decision and every draft has
        # to read: the volume declares the promises and the style trend, the chapter executes them.
        design_volume = volume_row(book, volume)
        design_chapter = design_row(book, anchor) if anchor else None
        add('complete_hooks', hook_ledger(book, design_volume), False)
        if stage in writing_stages:
            hook_refs = set(state_view.get('hooks', {}))
        else:
            # A design pass must see unresolved promises even when their people are offstage.
            hook_refs = {key for key, row in book['state'].get('hooks', {}).items()
                         if row.get('status') == 'open'}
            volume_ids = set((job.payload or {}).get('volume_ids') or ())
            hook_refs.update(row['id'] for ident, outline in (book.get('volumes_outline') or {}).items()
                             if ident in volume_ids for row in (outline or {}).get('hooks') or [])
        add('hooks', hook_ledger(book, design_volume, hook_refs))
        add('style', style_material(book, design_volume, design_chapter))
    if book.get('author_block'):
        add('author_block', book['author_block'])
    if book.get('creation'):
        # Brief summaries are bounded. New gates must read the full frozen choices so world
        # architecture and other long decisions survive without being reconstructed from snippets.
        chosen = stage in ('world_model', 'opening_contract', 'volume_outline')
        add('opening_basis', {'selection_hash': book['creation'].get('selection_hash'), 'source': book['creation']['source']}, chosen)
        choices_required = chosen or stage == 'opening_options'
        add('opening_choices', creation.selected(book['creation']), choices_required)
        if stage == 'opening_options':
            add('opening_rejections', [r for r in book['creation']['rejections'] if r['gate'] == job.payload['gate']['id']])
    if book.get('world'):
        model = book['world']
        # The volume and chapter design stages read the whole world: they decide what the story
        # walks through, so a projection of its rules is not enough. A scene dispatch reads the
        # core rules plus the records it touches, never the whole model.
        full_world = stage in ('volume_outline', 'chapter_outline', 'opening_contract')
        add('world_model', model, full_world)
        add('world_core', {'premise': model['premise'], 'rules': model['rules'], 'story_capacity': model['story_capacity']})
        if plan and stage in ('write', 'repair', 'redesign'):
            # A scene dispatch reads the records its chapter actually touches plus the disclosure
            # boundary; the design passes read the whole world model instead, so this slice would
            # only charge them twice for the same rules.
            records_by_id = world.index(model)
            selected_world = set(plan.get('world_refs', []))
            selected_world.update('characters:' + p for p in participants if 'characters:' + p in records_by_id)
            todo = list(selected_world)
            while todo:
                ident = todo.pop()
                for ref in records_by_id[ident]['links']:
                    if ref not in selected_world:
                        selected_world.add(ref)
                        if not tracking:
                            todo.append(ref)
            original = {key: records_by_id[key] for key in sorted(selected_world)}
            # The author's backstage truth is never required reading for a scene, with or without
            # narrative tracking. A writer who can read the answer writes the reveal away. The
            # tracking switch decides node bookkeeping, not who may see the ending.
            visible = {k: v for k, v in original.items() if not k.startswith('mysteries:')}
            add('world_records', visible)
            if tracking:
                add('world_author_records', original, False)
            add('disclosure_boundary', {'allowed_changes': plan.get('disclosures', []),
                 # A basic project keeps no reader-knowledge ledger, so the boundary states the
                 # secrets and the outline's allowed changes and leaves reader state empty rather
                 # than inventing one.
                 'reader_current': state_view.get('reader_knowledge', {}),
                 'author_secrets': [{'id': k, 'disclosure': v['disclosure'], 'causal_role': v['causal_role']} for k, v in original.items() if k.startswith('mysteries:')],
                 'source': '幕后真相见可选 world_author_records；作者真相不能自动成为人物知情或本章披露。'})
    if stage == 'chapter_outline' and volume_outline_row is not None:
        # The batch extends this volume's approved outline, so the volume row is the first thing it
        # has to read: node/thread ids and the exit_state it must land on are declared there.
        add('volume_outline', volume_outline_row)
        if (job.payload or {}).get('allow_retained_suffix'):
            add('prior_chapter_outlines', [r for r in (book.get('chapter_outlines') or {}).get(volume['id'], [])
                                           if r['chapter'] >= job.chapter], False)
    if plan:
        if stage in ('write', 'repair', 'redesign'):
            # The chapter outline is the hard prerequisite of a draft: it carries the enter/exit
            # state chain, and the drift_check the writer submits is reconciled against its deltas.
            add('chapter_outline', plan)
            if volume_outline_row is not None:
                add('complete_volume_outline', volume_outline_row, False)
                add('volume_outline', writing_volume_outline(
                    volume_outline_row, plan, chapter, records['complete_volume_outline']))
        if scene_task:
            add('scene_context', story_memory.packet(plan, book['state']))
            dependencies = []
            references = {ident for scene in plan.get('scenes', []) for ident in scene.get('depends_on', [])}
            local_ids = {s['id'] for s in plan['scenes']}
            external = references - local_ids
            locations = {s['id']: p['chapter'] for p in book['plans'].values() if p['chapter'] < chapter
                         for s in p.get('scenes', [])}
            require(external <= set(locations), 'story_dependency', '场景依赖缺少前章来源，须补读或重新规划。')
            for n in sorted({locations[ident] for ident in external}):
                row = repo.chapter(book['branch'], n)
                original = repo.read_document(row['plan'])
                scenes = [s for s in original.get('scenes', []) if s['id'] in references]
                require_ids = {s['id'] for s in scenes}
                require(require_ids == {ident for ident in external if locations[ident] == n},
                        'story_dependency', '场景依赖不在已提交章节版本中，须重新规划。')
                dependencies.append({'chapter': n, 'scenes': scenes, 'plan_hash': row['plan'],
                                     'prose_hash': row['prose'], 'events_hash': row['events'], 'chain': row['chain']})
            add('scene_sources', dependencies, bool(dependencies))
    if tracking and stage in ('write', 'repair', 'redesign'):
        add('word_budget', narrative.budget_for(book, chapter))
    if stage in ('write', 'repair', 'redesign', 'chapter_outline'):
        # Only chapters that exist: with `chapter_outline.scope='all'` a later volume's outlines are
        # designed before any prose is written, and asking the repository for chapters 0 and -1 used
        # to fail the whole dispatch.
        written = {row['n']: row for row in repo.headers(book['branch'])}
        previous = []
        for n in range(max(1, anchor - 2), anchor):
            row = written.get(n)
            if row is None:
                continue
            # Give each full chapter its own immutable record. Moving the two-chapter window
            # changes only the index and the newly introduced source, not the already-read prose.
            name = 'previous_chapter:' + str(n)
            records[name] = row['prose']
            required.append(name)
            previous.append({'chapter': n, 'prose_hash': row['prose'], 'record': name,
                             'summary': row['summary']})
        add('previous_chapters', previous)
        if stage in ('write', 'repair', 'redesign'):
            notes = []
            for item in previous:
                review = repo.read_document(written[item['chapter']]['review']).get('continuity') or {}
                if review.get('editorial_notes') or review.get('uncertain_findings'):
                    notes.append({'chapter': item['chapter'], 'prose_hash': written[item['chapter']]['prose'],
                                  'report_hash': review['report_hash'], 'editorial_notes': review.get('editorial_notes', []),
                                  'uncertain_findings': review.get('uncertain_findings', []),
                                  'resolution': review.get('resolution')})
            if notes:
                add('continuity_feedback', notes)
    payload = copy.deepcopy(job.payload or {})
    if 'understanding' in book and not opening_stage:
        payload['understanding'] = True
    if stage == 'volume_outline':
        # The batch policy: which volumes answer, where each one starts and ends, and the per-volume
        # word target. `volume_outline` is the policy map here; on a draft dispatch the same key
        # carries this volume's approved row instead. Defaults come from the contract policy.
        policy = resolve_outline_policy(contract, 'volume_outline')
        ids = payload.get('volume_ids') or [v['id'] for v in contract.get('volumes') or []]
        chosen = [v for v in contract.get('volumes') or [] if v['id'] in set(ids)]
        payload['volume_outline'] = {**policy,
                                     'volume_ids': [v['id'] for v in chosen],
                                     'volumes': [{'id': v['id'], 'purpose': v.get('purpose', ''),
                                                  'first': v['first'], 'end': v['end']} for v in chosen]}
        if merged_outline:
            # The merged half reads the same chapter-outline policy, per volume: the outer key names
            # the volumes this receipt must also outline chapter by chapter.
            chapter_policy_ = resolve_outline_policy(contract, 'chapter_outline')
            payload['chapter_outline'] = {
                **chapter_policy_,
                'volumes': [{'id': v['id'], 'first': v['first'], 'last': v['end']} for v in chosen]}
    if stage == 'chapter_outline':
        policy = resolve_outline_policy(contract, 'chapter_outline')
        first, last = _batch_range(job, volume, payload)
        payload['volume'] = volume['id'] if volume else payload.get('volume')
        payload['from_chapter'] = first
        payload['chapter_outline'] = {**policy, 'volume': payload['volume'], 'first': first, 'last': last}
    if stage in ('write', 'repair', 'redesign'):
        # The writer compares its own prose against both rows; the chapter row is what the engine
        # reconciles the drift_check against, and the volume row is where the arc has to land.
        payload['chapter_outline'] = plan
        payload['volume_outline'] = (writing_volume_outline(
            volume_outline_row, plan, chapter, records['complete_volume_outline'])
            if volume_outline_row is not None else None)
    if book.get('design_drift') and stage in ('chapter_outline', 'write', 'repair', 'redesign'):
        # Deviations the engine already booked. A re-plan has to absorb them, and a writer must know
        # which earlier promises no longer hold before continuing from them.
        add('design_drift', book['design_drift'])
    if enhanced and stage in ('write', 'repair', 'redesign'):
        payload['editorial'] = True
    if book['draft'] and stage in ('repair', 'redesign'):
        # Do not expose writer self-evaluation to anything downstream.
        add('base_draft', {'title': book['draft']['title'], 'prose': book['draft']['prose'],
                           'findings': book['draft'].get('findings', [])})
    if book['revision_run']:
        add('revision_instruction', book['revision_run']['reason'])
        if book['revision_run'].get('impact'):
            add('revision_impact', book['revision_run']['impact'])
    if book['feedback']:
        add('author_feedback', book['feedback'])
    if book.get('prior_candidate') and book['prior_candidate']['chapter'] == chapter:
        add('prior_candidate', book['prior_candidate'], stage in ('repair', 'redesign'))
    # A frozen head addresses shared immutable chapter pages. Re-dispatching another role
    # neither copies every summary nor re-reads every historical event.
    add('history_source', repo.history_snapshot(book['branch']), False)
    required = thin_required(records, required)
    brief = _brief(book, Job(stage, chapter, job.scope, job.first, job.last, payload))
    task = {'schema': TASK, 'stage': stage, 'chapter': chapter, 'scope': job.scope,
            'first': job.first, 'last': job.last, 'payload': payload, 'branch': book['branch'],
            'revision': book['revision'], 'records': records, 'required': required,
            'narrative_tracking': tracking,
            # Built from the declared capability table: the producers and the consumers of a frozen
            # protocol version string must be reading the same constant, or a rename degrades into
            # "this project is old" instead of failing.
            'capabilities': {**({EDITORIAL: EDITORIAL_CAPABILITY} if enhanced else {}),
                             **{UNDERSTANDING: UNDERSTANDING_CAPABILITY,
                                 SCENE_IDENTITY: SCENE_IDENTITY_CAPABILITY,
                                 READING_DEPENDENCIES: story_memory.READING_SCHEMA},
                             **({VOLUME_OUTLINE: VOLUME_OUTLINE_CAPABILITY} if contract.get('volume_outline') else {}),
                             **({SCENE_MEMORY: SCENE_MEMORY_CAPABILITY} if scene_task else {}),
                             **({HOOK_LINKS: HOOK_LINKS_CAPABILITY} if tracking else {})},
            # The active lexical policy travels with the task material, together with the fields
            # this dispatch actually inspects, so a worker never has to guess either one.
            'policy': policy_material(book.get('lexical_policy'), [stage, *tuple(payload.get('also', ()))])}
    if brief:
        task['brief'] = brief
    return validate_work(task)
