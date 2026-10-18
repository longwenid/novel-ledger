"""Query/assembly layer. Sources are immutable; selection never erases availability."""
from __future__ import annotations

import copy
import json
from .contracts import (SCALE_TIERS, TASK, Job, require, tier_of)
from .contracts import (EDITORIAL_CAPABILITY, HOOK_LINKS_CAPABILITY, OPENING_BOUNDS_CAPABILITY, SCENE_IDENTITY_CAPABILITY,
                        SCENE_MEMORY_CAPABILITY, UNDERSTANDING_CAPABILITY, VOLUME_OUTLINE_CAPABILITY)
from . import briefs, creation, narrative, world, editorial, story_memory, understanding
from .planning import policy_material, volume_for
from .ports import ContextStore
from .envelope import validate_work

# Capability names as they appear in a frozen task's capability map.
EDITORIAL = 'editorial'
UNDERSTANDING = 'understanding'
SCENE_IDENTITY = 'scene_identity'
READING_DEPENDENCIES = 'reading_dependencies'
OPENING_BOUNDS = 'opening_bounds'
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
    'opening_options': ('opening_rejections',),
    'world_model': ('author_feedback', 'opening_basis', 'opening_choices', 'previous_proposal'),
    'opening_contract': ('author_feedback', 'opening_basis', 'opening_choices', 'world_model'),
    'volume_outline': ('author_feedback', 'contract', 'effective_layout', 'opening_basis',
                       'opening_choices', 'revision_impact', 'revision_instruction', 'state',
                       'world_model'),
    'chapter_outline': ('author_feedback', 'contract', 'design_drift', 'effective_layout',
                        'previous_chapters', 'revision_impact', 'revision_instruction', 'state',
                        'volume_outline', 'world_model'),
    'write': ('author_feedback', 'chapter_outline', 'contract', 'creative_memory', 'design_drift',
              'disclosure_boundary', 'previous_chapters', 'scene_context', 'scene_sources', 'state',
              'style_anchor', 'volume_outline', 'word_budget', 'world_core', 'world_records'),
    'repair': ('author_feedback', 'base_draft', 'chapter_outline', 'contract', 'creative_memory',
               'design_drift', 'disclosure_boundary', 'previous_chapters', 'prior_candidate',
               'revision_impact', 'revision_instruction', 'scene_context', 'scene_sources', 'state',
               'style_anchor', 'volume_outline', 'word_budget', 'world_core', 'world_records'),
    'redesign': ('author_feedback', 'base_draft', 'chapter_outline', 'contract', 'creative_memory',
                 'design_drift', 'disclosure_boundary', 'previous_chapters', 'prior_candidate',
                 'revision_impact', 'revision_instruction', 'scene_context', 'scene_sources', 'state',
                 'style_anchor', 'volume_outline', 'word_budget', 'world_core', 'world_records'),
}


def undeclared_material(stage, required):
    """Required records this stage never declared, as a sorted list of names."""
    declared = set(STAGE_MATERIAL.get(stage) or ())
    return sorted(name for name in required if name not in declared)


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
    """The node ids a row advances, from either shape the engine has used.

    v2 chapter outlines declare nodes under `plot.nodes`; the older plan shape used `node_ids`. The
    projection reads both so a state slice is never narrowed to nothing by a rename.
    """
    ids = set(plan.get('node_ids') or ())
    for row in (plan.get('plot') or {}).get('nodes') or ():
        if isinstance(row, dict) and row.get('node'):
            ids.add(row['node'])
    return ids


def scoped_state(state, participants, plan=None, chapter=0, horizon=3):
    selected = set(participants)
    view = copy.deepcopy(state)
    for field in ('entities', 'placements', 'developments'):
        view[field] = {k: v for k, v in state[field].items() if k in selected}
    for field in ('facts', 'knowledge'):
        view[field] = {k: v for k, v in state[field].items() if k.split(':', 1)[0] in selected}
    view['resources'] = {k: v for k, v in state['resources'].items() if json.loads(k)[0] in selected}
    view['relations'] = {k: v for k, v in state['relations'].items() if k.split('>')[0] in selected or k.split('>')[1].split(':')[0] in selected}
    view['historical_assertions'] = {k: v for k, v in state['historical_assertions'].items() if selected.intersection(v['subjects'])}
    view['hooks'] = {k: v for k, v in state['hooks'].items() if v['status'] == 'open'}
    if 'story_nodes' in state:
        plan = plan or {}
        nodes = _planned_nodes(plan)
        for definition in plan.get('node_contracts', {}).values():
            nodes.update(definition['depends_on'])
        view['story_nodes'] = {k: v for k, v in state['story_nodes'].items() if k in nodes}
        view['character_current'] = {k: v for k, v in state['character_current'].items() if k in selected}
        refs = set(plan.get('reader_refs', [])) | {d['topic'] for d in plan.get('disclosures', [])}
        view['reader_knowledge'] = {k: v for k, v in state['reader_knowledge'].items() if k in refs or v['chapter'] >= chapter - 2}
        view['developments'] = {k: v[-2:] for k, v in view['developments'].items()}
        view['historical_assertions'] = {k: v for k, v in view['historical_assertions'].items() if k in plan.get('history_refs', [])}
        view['hooks'] = {k: v for k, v in view['hooks'].items()
                         if k in plan.get('hook_refs', []) or v['due'] <= chapter + horizon
                         or selected.intersection(v.get('subjects', [])) or refs.intersection(v.get('topics', []))}
        view['memory_sources'] = 'complete_state 保留全部状态和人物发展；历史原文经 history_source/recall 完整补读。未选择不代表不存在。'
    # Explicit causal inputs may refer to an off-stage character or a remote promise.
    # Participant heuristics must never erase those coordinates.
    if plan:
        for kind, key in story_memory.reads(plan):
            present, value = story_memory.lookup(state, kind, key)
            field = 'story_nodes' if kind == 'node' else kind
            if present and kind != 'clock':
                view.setdefault(field, {})[key] = value
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
        # The brief and the validator read the same tier declaration, so the world the worker is
        # asked for is the world the check accepts.
        tier = scale_tier(book)
        return briefs.world_model(previous=previous, repair=bool(payload.get('repair')),
                                  scale=_scale_line(book),
                                  sections=world.required_sections(tier['id'] if tier else None))
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


def _selection_line(option, budget=120):
    """One compact line per closed choice: the direction, not a copy of the record.

    A later gate builds on everything already decided, so the line has to carry the fields that
    decide direction — the channel and setting, the promise, the edge, the view — not whichever
    single field happened to come first. Reading only one field is how a protagonist gate produced
    three consistent-sounding people in another era: the chosen genre text never reached it. The
    exact values still live in opening_choices and are re-checked when the contract is formed, so
    this line stays a summary under a fixed budget rather than a second copy of the record.
    """
    value = option.get('value', {})
    parts = []
    for key in ('genre', 'reader_promise', 'advantage', 'identity', 'opposition', 'world_premise',
                'story_engine', 'ending', 'pov', 'voice', 'tone', 'title', 'relationships'):
        entry = value.get(key)
        # A relation gate's gist is its first relation: an empty list is never a chosen direction.
        if isinstance(entry, list) and entry and isinstance(entry[0], str) and entry[0].strip():
            entry = entry[0]
        if not isinstance(entry, str) or not entry.strip():
            continue
        parts.append(key + '=' + entry.strip())
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


def volume_row(book, volume):
    return (book.get('volumes_outline') or {}).get(volume['id']) if volume else None


def _participants(plan, book):
    """Who is on stage this chapter, from the row itself rather than a profile table.

    v2 removed the profile stage: a chapter outlines its cast as `characters` deltas and inlines
    first appearances in `new_entities`, so the participant set is read from that row.
    """
    if plan:
        named = plan.get('participants')
        if isinstance(named, list) and named:
            return list(named)
        entities = [row.get('entity') for row in plan.get('characters') or []
                    if isinstance(row, dict) and row.get('entity')]
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
    records, required, prose = {}, [], []

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
    add('state', scoped_state(book['state'], participants, plan, anchor, contract.get('planning_window', 3)),
        not opening_stage and (stage != 'volume_outline' or merged_outline))
    add('complete_state', book['state'], False)
    memory_stages = ('volume_outline', 'chapter_outline', 'write', 'repair', 'redesign')
    if 'understanding' in book and not opening_stage:
        add('complete_understanding', book['understanding'], False)
        if stage in memory_stages:
            topics = set((plan or {}).get('reader_refs', [])) | {d['topic'] for d in (plan or {}).get('disclosures', [])}
            memory_refs = (set(plan.get('understanding_refs', []))
                           if plan and story_memory.reading_enabled(plan) else set())
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
    if book.get('author_block'):
        add('author_block', book['author_block'])
    if book.get('creation'):
        # The brief already names every chosen direction in full, so the choices record is required
        # only where the dispatch has to build on all of them at once (world and volume design).
        # Rejections stay required for the opening, which must not re-propose a refused group.
        chosen = stage in ('world_model', 'opening_contract', 'volume_outline')
        add('opening_basis', {'selection_hash': book['creation'].get('selection_hash'), 'source': book['creation']['source']}, chosen)
        add('opening_choices', creation.selected(book['creation']), chosen)
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
                 'reader_current': scoped_state(book['state'], participants, plan, anchor).get('reader_knowledge', {}),
                 'author_secrets': [{'id': k, 'disclosure': v['disclosure'], 'causal_role': v['causal_role']} for k, v in original.items() if k.startswith('mysteries:')],
                 'source': '幕后真相见可选 world_author_records；作者真相不能自动成为人物知情或本章披露。'})
    if stage == 'chapter_outline' and volume_outline_row is not None:
        # The batch extends this volume's approved outline, so the volume row is the first thing it
        # has to read: node/thread ids and the exit_state it must land on are declared there.
        add('volume_outline', volume_outline_row)
    if plan:
        if stage in ('write', 'repair', 'redesign'):
            # The chapter outline is the hard prerequisite of a draft: it carries the enter/exit
            # state chain, and the drift_check the writer submits is reconciled against its deltas.
            add('chapter_outline', plan)
            if volume_outline_row is not None:
                add('volume_outline', volume_outline_row)
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
        previous = []
        for n in range(max(1, anchor - 2), anchor):
            row = repo.chapter(book['branch'], n)
            previous.append({'chapter': n, 'prose': repo.read_document(row['prose']), 'summary': row['summary']})
        add('previous_chapters', previous)
    payload = copy.deepcopy(job.payload or {})
    if 'understanding' in book and not opening_stage:
        payload['understanding'] = True
    if stage == 'volume_outline':
        # The batch policy: which volumes answer, where each one starts and ends, and the per-volume
        # word target. `volume_outline` is the policy map here; on a draft dispatch the same key
        # carries this volume's approved row instead. The defaults mirror the contract's own, so a
        # project loaded from before v2 still gets a stated target rather than an empty one.
        policy = contract.get('volume_outline') or {'scope': 'all', 'words': 1000, 'tolerance': 100}
        ids = payload.get('volume_ids') or [v['id'] for v in contract.get('volumes') or []]
        chosen = [v for v in contract.get('volumes') or [] if v['id'] in set(ids)]
        payload['volume_outline'] = {**policy,
                                     'volume_ids': [v['id'] for v in chosen],
                                     'volumes': [{'id': v['id'], 'purpose': v.get('purpose', ''),
                                                  'first': v['first'], 'end': v['end']} for v in chosen]}
        if merged_outline:
            # The merged half reads the same chapter-outline policy, per volume: the outer key names
            # the volumes this receipt must also outline chapter by chapter.
            chapter_policy_ = contract.get('chapter_outline') or {'scope': 'volume', 'words': 150, 'tolerance': 60}
            payload['chapter_outline'] = {
                **chapter_policy_,
                'volumes': [{'id': v['id'], 'first': v['first'], 'last': v['end']} for v in chosen]}
    if stage == 'chapter_outline':
        policy = contract.get('chapter_outline') or {'scope': 'volume', 'words': 150, 'tolerance': 60}
        first, last = _batch_range(job, volume, payload)
        payload['volume'] = volume['id'] if volume else payload.get('volume')
        payload['from_chapter'] = first
        payload['chapter_outline'] = {**policy, 'volume': payload['volume'], 'first': first, 'last': last}
    if stage in ('write', 'repair', 'redesign'):
        # The writer compares its own prose against both rows; the chapter row is what the engine
        # reconciles the drift_check against, and the volume row is where the arc has to land.
        payload['chapter_outline'] = plan
        payload['volume_outline'] = volume_outline_row
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
                             **({UNDERSTANDING: UNDERSTANDING_CAPABILITY,
                                 SCENE_IDENTITY: SCENE_IDENTITY_CAPABILITY,
                                 READING_DEPENDENCIES: story_memory.READING_SCHEMA} if 'understanding' in book else {}),
                             **({OPENING_BOUNDS: OPENING_BOUNDS_CAPABILITY} if stage == 'opening_options' else {}),
                             **({VOLUME_OUTLINE: VOLUME_OUTLINE_CAPABILITY} if contract.get('volume_outline') else {}),
                             **({SCENE_MEMORY: SCENE_MEMORY_CAPABILITY} if scene_task else {}),
                             **({HOOK_LINKS: HOOK_LINKS_CAPABILITY} if tracking else {})},
            # The active lexical policy travels with the task material, together with the fields
            # this dispatch actually inspects, so a worker never has to guess either one.
            'policy': policy_material(book.get('lexical_policy'), [stage, *tuple(payload.get('also', ()))]),
            # No v2 stage is a blind review: the prose field stays declared so the envelope keeps
            # rejecting unknown keys, and every dispatch now hands out formal material.
            'prose': prose}
    if brief:
        task['brief'] = brief
    return validate_work(task)
