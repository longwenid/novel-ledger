"""Query/assembly layer. Sources are immutable; selection never erases availability."""
from __future__ import annotations

import copy
import json
from .contracts import (CHECKS_VERSION, EDITORIAL_VERSION, POV_CHECKS_VERSION, TASK, Job, checks_for, dump, digest, require, tier_of)
from .contracts import (EDITORIAL_CAPABILITY, HOOK_LINKS_CAPABILITY, OPENING_BOUNDS_CAPABILITY, SCENE_IDENTITY_CAPABILITY,
                        SCENE_MEMORY_CAPABILITY, UNDERSTANDING_CAPABILITY, VOLUME_OUTLINE_CAPABILITY)
from . import briefs, creation, narrative, scopes, world, editorial, story_memory, understanding
from .planning import outline_policy, policy_material, volume_for
from .design_queries import BASIC_DEPTH, TRACKED_DEPTH, frontier, node_map
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
LAYOUT_STAGES = ('book_plan', 'volume_plan', 'volume_outline', 'outline_review', 'design_review',
                 'scope_review', 'scope_synthesis', 'plan', 'alignment_plan', 'alignment_review')
# Records that are a narrower view of another record, declared where the material is selected so the
# relationship is a decision rather than something a reader has to infer from two similar payloads.
# A projection is required only when the record it projects is not: a scene dispatch reads the rules
# through `world_core`, a design dispatch reads the `world_model` they come from, never both.
# Prefix entries end with ':' and substitute the same suffix on both sides.
PROJECTIONS = (
    ('world_core', 'world_model'),
    ('scope_profiles', 'profiles'),
    ('frontier:', 'design:'),
)


# What each stage must read to make its own decision, as opposed to what it may read if it needs to.
# Measured from what the engine actually hands out, and written down here so that giving a stage more
# material is a visible decision rather than one more `add(...)` line: the guard in tests/support.py
# compares every frozen dispatch against this table, so an undeclared record fails the suite that
# covers that stage. Records that several stages share (contract, state, story, profiles, ...) are
# still listed per stage — "why does this stage read this" is exactly what the table is for.
STAGE_MATERIAL = {
    'opening_options': ('opening_rejections',),
    'world_model': ('author_feedback', 'opening_basis', 'opening_choices', 'previous_proposal'),
    'world_review': ('opening_basis', 'opening_choices', 'proposal'),
    'opening_contract': ('author_feedback', 'opening_basis', 'opening_choices', 'world_model'),
    'contract_review': ('contract_amendment', 'opening_basis', 'opening_choices', 'plan', 'profiles',
                        'proposal', 'story', 'world_model'),
    'book_plan': ('author_feedback', 'contract', 'disclosure_boundary', 'effective_layout', 'plan',
                  'previous_proposal', 'profiles', 'revision_instruction', 'state', 'story',
                  'world_model', 'world_records'),
    'design_review': ('author_feedback', 'contract', 'effective_layout', 'proposal',
                      'revision_instruction', 'state', 'world_model'),
    'volume_plan': ('author_feedback', 'contract', 'design:book', 'effective_layout',
                    'progress_frontier', 'revision_instruction', 'state', 'world_model'),
    'volume_outline': ('author_feedback', 'contract', 'outline_bridge', 'state', 'volume_design',
                       'world_model'),
    'outline_review': ('author_feedback', 'contract', 'outline_bridge', 'proposal', 'state',
                       'volume_design', 'world_model'),
    'plan': ('author_feedback', 'contract', 'creative_memory', 'effective_layout', 'frontier:book',
             'frontier:volume:v1', 'frontier:volume:v2', 'plan', 'previous_chapters', 'profiles',
             'progress_frontier', 'revision_instruction', 'state', 'story', 'volume_outline_window',
             'word_budget', 'world_core'),
    'profiles': ('author_feedback', 'contract', 'disclosure_boundary', 'plan', 'profiles',
                 'revision_instruction', 'state', 'story', 'style_anchor', 'world_core',
                 'world_records'),
    'write': ('author_feedback', 'chapter_outline', 'contract', 'creative_memory',
              'disclosure_boundary', 'plan', 'previous_chapters', 'profiles', 'scene_context',
              'scene_sources', 'state', 'story', 'style_anchor', 'word_budget', 'world_core',
              'world_records'),
    'chapter_review': ('author_feedback', 'chapter_outline', 'contract', 'plan', 'profiles',
                       'revision_impact', 'revision_instruction', 'state'),
    'repair': ('author_feedback', 'base_draft', 'contract', 'creative_memory', 'plan',
               'previous_chapters', 'prior_candidate', 'profiles', 'revision_impact',
               'revision_instruction', 'scene_context', 'scene_sources', 'state', 'story',
               'style_anchor', 'word_budget'),
    'redesign': ('base_draft', 'contract', 'plan', 'previous_chapters', 'profiles', 'state', 'story'),
    'revision_review': ('contract', 'plan', 'previous_chapters', 'profiles', 'revision_impact',
                        'revision_instruction', 'state', 'story'),
    'scope_review': ('author_feedback', 'contract', 'creative_memory', 'effective_layout', 'plan',
                     'profiles', 'revision_impact', 'revision_instruction', 'state', 'story',
                     'style_anchor'),
    'scope_synthesis': ('author_feedback', 'contract', 'creative_memory', 'effective_layout', 'plan',
                        'profiles', 'revision_impact', 'revision_instruction', 'scope_parts', 'state',
                        'story', 'style_anchor'),
    'alignment_plan': ('alignment_hold', 'contract', 'effective_layout', 'frontier:book',
                       'frontier:volume:v1', 'profiles', 'scene_context', 'state', 'story',
                       'style_anchor'),
    'alignment_review': ('alignment_hold', 'alignment_proposal', 'contract', 'effective_layout',
                         'frontier:book', 'frontier:volume:v1', 'profiles', 'scene_context', 'state',
                         'story', 'style_anchor'),
}


# What a chapter review decides on, as opposed to the background a scene dispatch reads. The
# reviewer judges this chapter against its plan, the scoped state, the participants and the
# author's terms; the world, the scene packet, the style anchor and the creative memory stay
# available on demand (`read --record`). Measured before this split, one 3,375-character chapter
# was reviewed against 56,031 characters of required material — 16.6 times the text under review,
# most of it background the reviewer never cites. STAGE_MATERIAL is the required half of this
# same decision; this tuple is the demoted half, so the two cannot drift apart silently.
CHAPTER_REVIEW_ON_DEMAND = ('creative_memory', 'disclosure_boundary', 'prior_candidate',
                            'scene_context', 'scene_sources', 'story', 'style_anchor',
                            'world_core', 'world_records')


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
    projection whose source is also required. Measured on a real run before this existed: 90,456
    characters of identical duplicates plus an 11,199-byte world projection on nearly every design
    and review dispatch. Nothing is erased — a dropped name stays in `records` and in `on_demand`.
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
        nodes = set(plan.get('node_ids', []))
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


def _brief(book, job, version=CHECKS_VERSION):
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
    return briefs.stage(job.stage, {**payload, 'editorial': editorial.enabled(book), 'checks_version': version})


def scale_tier(book):
    """The tier row this project was sized to, or None when the contract came in without a tier."""
    return tier_of(book.get('contract') or {})


def _scale_line(book):
    """The chosen size class, spelled out for the world brief."""
    contract = book.get('contract') or {}
    volumes = contract.get('volumes') or []
    if not volumes:
        return ''
    tier = scale_tier(book)
    last = volumes[-1]['end']
    return '%s，%d 卷共 %d 章，每章 %s～%s 汉字' % (
        (tier['name'] + '档') if tier else '已定体量', len(volumes), last,
        contract.get('chapter_min'), contract.get('chapter_max'))


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


def build(repo: ContextStore, book, job):
    records, required, prose = {}, [], []

    def add(name, value, needed=True):
        records[name] = repo.document(value)
        if needed:
            required.append(name)

    # A chapter review reads its judgement basis; the background a scene dispatch needs stays on
    # demand, declared in CHAPTER_REVIEW_ON_DEMAND next to the required half of the same decision.
    def need(name):
        return not (job.stage == 'chapter_review' and name in CHAPTER_REVIEW_ON_DEMAND)

    stage, chapter = job.stage, job.chapter
    plan = book['plans'].get(str(chapter))
    if stage == 'revision_review':
        original_row = book['revision_run']['carry'][0]
        require(original_row['n'] == chapter, 'revision', '阅读核验须绑定下一章准确版本。')
        plan = repo.read_document(original_row['plan'])
    scene_task = bool(plan and plan.get('scenes') and stage in
                      ('write', 'repair', 'redesign', 'chapter_review', 'alignment_plan', 'alignment_review'))
    enhanced = editorial.enabled(book)
    # A contract that declares a narrative view is reviewed against the check list that carries
    # pov_consistency; a contract without one keeps the version its project already runs on, so an
    # imported contract is never judged against a view nobody chose.
    version = POV_CHECKS_VERSION if enhanced and (book.get('contract') or {}).get('pov') \
        else EDITORIAL_VERSION if enhanced else CHECKS_VERSION
    # A worker needs the material its stage decides on, and nothing else: the opening reads the
    # closed choices, not a contract that does not exist yet or a state that is still empty.
    opening_stage = stage in ('opening_options', 'world_model', 'world_review', 'opening_contract', 'contract_review')
    add('contract', book['contract'], not opening_stage)
    participants = plan['participants'] if plan else list(book['state']['entities'])
    if enhanced and stage in ('scope_review', 'scope_synthesis'):
        selected_chapters = set(range(job.first, job.last + 1))
        if (job.payload or {}).get('children'):
            reports = scopes.reports(book)
            selected_chapters = {n for ident in job.payload['children'] for n in (reports[ident]['first'], reports[ident]['last'])}
        participants = sorted({p for r in repo.headers(book['branch']) if r['n'] in selected_chapters
                               for p in repo.read_document(r['plan'])['participants']})
    tracking = bool((book.get('contract') or {}).get('narrative_tracking'))
    add('state', scoped_state(book['state'], participants, plan, chapter, (book.get('contract') or {}).get('planning_window', 3)), not opening_stage)
    add('complete_state', book['state'], False)
    memory_stages = ('plan', 'profiles', 'write', 'repair', 'redesign', 'chapter_review',
                     'revision_review', 'scope_review', 'scope_synthesis', 'alignment_plan', 'alignment_review',
                     'book_plan', 'volume_plan', 'volume_outline')
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
                    'boundary': '这是可修订的作品理解，含原文样本和反证，不是事实或写作命令；作者约定仍为方向来源。'},
                    need('creative_memory'))
    if enhanced:
        add('complete_profiles', book['profiles'], False)
        add('profile_history', book.get('profile_history', []), False)
        if stage in ('scope_review', 'scope_synthesis'):
            add('scope_profiles', {p: book['profiles'][p] for p in participants if p in book['profiles']})
        add('effective_layout', editorial.effective_contract(book)['volumes'], stage in LAYOUT_STAGES)
        if book.get('style_anchor'):
            add('style_anchor', book['style_anchor'], need('style_anchor'))
    if book.get('author_block'):
        add('author_block', book['author_block'])
    if book.get('creation'):
        # The brief already names every chosen direction in full, so the choices record is reference
        # material rather than required reading; rejections stay required because a worker must not
        # re-propose a group the author already refused.
        chosen = stage in ('world_model', 'world_review', 'opening_contract', 'contract_review')
        add('opening_basis', {'selection_hash': book['creation'].get('selection_hash'), 'source': book['creation']['source']}, chosen)
        add('opening_choices', creation.selected(book['creation']), chosen)
        if stage == 'opening_options':
            add('opening_rejections', [r for r in book['creation']['rejections'] if r['gate'] == job.payload['gate']['id']])
    if book.get('world'):
        model = book['world']
        # An amendment review judges a change against the author's choices and the world's rules, so
        # it reads the world's core and the diff; the full model stays on demand. The first contract
        # review still reads the whole world, because that is where the contract is born.
        amended = stage == 'contract_review' and bool((book.get('proposal') or {}).get('amendment'))
        full_world = stage in ('book_plan', 'volume_plan', 'volume_outline', 'outline_review',
                               'design_review', 'opening_contract') or (stage == 'contract_review' and not amended)
        add('world_model', model, full_world)
        add('world_core', {'premise': model['premise'], 'rules': model['rules'], 'story_capacity': model['story_capacity']},
            need('world_core'))
        if plan:
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
            # narrative tracking. A writer who can read the answer writes the reveal away, and a
            # reviewer who can read it stops judging whether the prose discloses it properly; the
            # tracking switch decides node bookkeeping, not who may see the ending.
            visible = {k: v for k, v in original.items() if not k.startswith('mysteries:')}
            add('world_records', visible, need('world_records'))
            if tracking:
                add('world_author_records', original, False)
            add('disclosure_boundary', {'allowed_changes': plan.get('disclosures', []),
                 # A basic project keeps no reader-knowledge ledger, so the boundary states the
                 # secrets and the plan's allowed changes and leaves reader state empty rather
                 # than inventing one.
                 'reader_current': scoped_state(book['state'], participants, plan, chapter).get('reader_knowledge', {}),
                 'author_secrets': [{'id': k, 'disclosure': v['disclosure'], 'causal_role': v['causal_role']} for k, v in original.items() if k.startswith('mysteries:')],
                 'source': '幕后真相见可选 world_author_records；作者真相不能自动成为人物知情或本章披露。'},
                need('disclosure_boundary'))
    if plan:
        add('plan', plan, not scene_task or stage == 'chapter_review')
        if scene_task:
            add('scene_context', story_memory.packet(plan, book['state']), need('scene_context'))
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
            add('scene_sources', dependencies, bool(dependencies) and need('scene_sources'))
        add('profiles', {p: book['profiles'][p] for p in participants if p in book['profiles']})
        nodes = node_map(book['designs'])
        # Tracked projects read their target plus direct prerequisites; a basic project has no
        # progress frontier to narrow by, so it walks a bounded neighbourhood instead of the
        # whole ancestry. Both are bounded and neither recurses.
        depth = TRACKED_DEPTH if tracking else BASIC_DEPTH
        selected = frontier(nodes, plan['node_ids'], depth)
        add('story', [nodes[ident] for ident in sorted(selected)], need('story'))
    for scope, design in book['designs'].items():
        needed = stage in ('volume_plan', 'plan', 'alignment_plan', 'alignment_review') and scope in ('book', 'volume:' + volume_for(editorial.effective_contract(book), chapter)['id'])
        if needed and tracking:
            end = job.last or chapter + book['contract']['planning_window'] - 1
            add('frontier:' + scope, {**{k: v for k, v in design.items() if k not in ('nodes', 'chapters', 'outline_reviews')},
                'nodes': [n for n in design['nodes'] if narrative.progress(book['state'], n['id']) != 'resolved'
                          and n['window'][0] <= end and chapter <= n['window'][1]]})
        # A design scope is reference material, not required reading: the bounded `story`/`frontier`
        # slice already carries the nodes this dispatch decides on, so requiring the whole design
        # would make every task's material grow with the outline. volume_plan is the one stage with
        # no chapter plan, hence no bounded slice, so it reads its two design scopes directly.
        add('design:' + scope, design, needed and stage == 'volume_plan')
    if tracking and stage in ('plan', 'volume_plan'):
        nodes, threads = narrative.registry(book)
        end = job.last or chapter + book['contract']['planning_window'] - 1
        selected_nodes = {n['id'] for n in nodes.values() if n['window'][0] <= end and chapter <= n['window'][1]}
        parents = {p for ident in selected_nodes for p in nodes[ident]['depends_on']}
        add('progress_frontier', {'nodes': {ident: book['state']['story_nodes'].get(ident) for ident in sorted(selected_nodes | parents)},
             'threads': book['state']['thread_progress'],
             'overdue_nodes': [ident for ident, n in nodes.items() if n['required'] and n['window'][1] < chapter and narrative.progress(book['state'], ident) != 'resolved'],
             'source': '只列当前窗口节点及直接前置的真实进度；远期和完整历史保留 design:*/complete_state。'})
    if tracking and stage in ('plan', 'write', 'repair', 'redesign'):
        add('word_budget', narrative.budget_for(book, chapter, job.last if stage == 'plan' else None))
    payload = copy.deepcopy(job.payload or {})
    if 'understanding' in book and not opening_stage:
        payload['understanding'] = True
    if stage == 'revision_review':
        original_review = repo.read_document(original_row['review'])
        payload.update(original_plan=plan, prior_sessions=[original_review['writer'], original_review['session']],
                       original_prose_hash=original_row['prose'])
    volume = volume_for(editorial.effective_contract(book), chapter) if book.get('contract') else None
    if volume and book['contract'].get('volume_outline'):
        if stage == 'volume_plan':
            payload['volume_outline'] = {**outline_policy(editorial.effective_contract(book), volume, book.get('world')), 'brainstorm_only': True}
        elif stage == 'design_review' and book['proposal']['scope'].startswith('volume:'):
            payload['volume_outline'] = {**outline_policy(editorial.effective_contract(book), volume, book.get('world')), 'brainstorm_only': True}
        elif stage in ('volume_outline', 'outline_review'):
            payload['volume_outline'] = {**outline_policy(editorial.effective_contract(book), volume, book.get('world')), 'first': job.first, 'last': job.last}
        design = book['designs'].get('volume:' + volume['id'], {})
        chapters = design.get('chapters', [])
        if stage in ('volume_outline', 'outline_review'):
            add('volume_design', {k: v for k, v in design.items() if k not in ('chapters', 'outline_reviews')})
            add('outline_bridge', chapters[-1:] if chapters else [])
        if chapters and stage == 'plan':
            add('volume_outline_window', [c for c in chapters if job.first <= c['chapter'] <= job.last])
        if chapters and stage in ('write', 'repair', 'redesign', 'chapter_review', 'alignment_plan'):
            add('chapter_outline', next((c for c in chapters if c['chapter'] == chapter), None))
    if enhanced:
        payload['editorial'] = True
        if stage == 'chapter_review':
            payload['node_ids'] = plan['node_ids']
            payload['node_criteria'] = {n: [{k: c[k] for k in ('id', 'text')} for c in plan['node_contracts'][n].get('criteria', [])] for n in plan['node_ids']}
        if stage == 'contract_review' and book.get('author_block'):
            payload['author_question_hash'] = digest(book['author_block'])
        if stage in ('alignment_plan', 'alignment_review'):
            add('alignment_hold', book['alignment_hold'])
            payload['proposed_chapter'] = chapter
            if book.get('draft'):
                prose = [{'chapter': chapter, 'hash': repo.document(book['draft']['prose'])}]
            if stage == 'alignment_review':
                add('alignment_proposal', book['alignment_proposal'])
                prose.append({'chapter': 0, 'hash': repo.document(dump(book['alignment_proposal']))})
        if stage == 'scope_synthesis' and payload.get('root'):
            active = {k: c for k, c in book.get('repair_cases', {}).items() if c['status'] != 'resolved'
                      and (c['scope'] == job.scope or job.scope == 'revision' and k in (book.get('revision_run') or {}).get('case_ids', []))}
            if active:
                payload['remedies'] = [{'case_id': k, 'round_id': c['rounds'][-1]['id'], 'goal': c['goal'],
                                        'verification_condition': c['verification_condition']} for k, c in active.items()]
            if job.scope == 'book' or job.scope.startswith('volume:'):
                hashes = [{'chapter': r['n'], 'hash': r['prose']} for r in repo.headers(book['branch']) if job.first <= r['n'] <= job.last]
                payload['closure'] = {'context_hash': digest({'context': editorial.context_hash(book), 'chapters': hashes, 'scope': job.scope}),
                                      'sources': editorial.sources(book, job.scope), 'prose_hashes': hashes,
                                      'revision_policy': editorial.revision_policy(book, repo.headers(book['branch'])[-1]['n'])}
    if stage in ('book_plan', 'volume_plan', 'volume_outline', 'world_model') and book['proposal']:
        add('previous_proposal', book['proposal'])
    if stage in ('design_review', 'outline_review', 'contract_review', 'world_review'):
        add('proposal', book['proposal'])
        prose = [{'chapter': 0, 'hash': repo.document(dump(book['proposal']['data']))}]
        if stage == 'contract_review' and book['proposal'].get('amendment'):
            # A re-contract changes a field or two of a candidate that was already reviewed. The
            # reviewer checks the delta, so a second, quieter amendment cannot ride along unseen.
            add('contract_amendment', book['proposal']['amendment'])
    elif stage == 'chapter_review':
        prose = [{'chapter': chapter, 'hash': repo.document(book['draft']['prose'])}]
    elif stage == 'revision_review':
        prose = [{'chapter': chapter, 'hash': original_row['prose']}]
    elif stage in ('scope_review', 'scope_synthesis'):
        prose = [{'chapter': row['n'], 'hash': row['prose']} for row in repo.headers(book['branch']) if job.first <= row['n'] <= job.last]
        if stage == 'scope_synthesis':
            if payload.get('review_tree'):
                add('scope_catalog', prose, False)
                children = [scopes.reports(book)[ident] for ident in payload['children']]
                add('scope_parts', [scopes.digest_report(p) for p in children])
                for p in children:
                    add('scope_report:' + p['part_id'], p, False)
                boundaries = {n for p in children for n in (p['first'], p['last'])}
                prose = [p for p in prose if p['chapter'] in boundaries]
            else:
                add('scope_parts', book['scope_parts'][payload['review_key']])
    if stage in ('write', 'repair', 'redesign', 'plan', 'revision_review'):
        previous = []
        for n in range(max(1, chapter - 2), chapter):
            row = repo.chapter(book['branch'], n)
            previous.append({'chapter': n, 'prose': repo.read_document(row['prose']), 'summary': row['summary']})
        add('previous_chapters', previous)
    obligations = copy.deepcopy(plan.get('obligations', [])) if plan else []
    if book['draft'] and stage in ('repair', 'redesign'):
        # Do not expose writer self-evaluation to the reviewer.
        add('base_draft', {'title': book['draft']['title'], 'prose': book['draft']['prose'], 'findings': book['draft'].get('findings', [])})
    if book['draft'] and stage in ('repair', 'redesign', 'chapter_review'):
        for i, finding in enumerate(book['draft'].get('findings', [])):
            obligations.append({'id': 'repair:' + str(i), 'category': 'facts' if finding['criterion'] in checks_for(CHECKS_VERSION, 'fact') else 'reader', 'text': finding['reason']})
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
    brief = _brief(book, Job(stage, chapter, job.scope, job.first, job.last, payload), version)
    task = {'schema': TASK, 'stage': stage, 'chapter': chapter, 'scope': job.scope,
            'first': job.first, 'last': job.last, 'payload': payload, 'branch': book['branch'],
            'revision': book['revision'], 'records': records, 'required': required,
            'checks_version': version, 'narrative_tracking': tracking,
            # Built from the declared capability table: the producers and the consumers of a frozen
            # protocol version string must be reading the same constant, or a rename degrades into
            # "this project is old" instead of failing.
            'capabilities': {**({EDITORIAL: EDITORIAL_CAPABILITY} if enhanced else {}),
                             **({UNDERSTANDING: UNDERSTANDING_CAPABILITY,
                                 SCENE_IDENTITY: SCENE_IDENTITY_CAPABILITY,
                                 READING_DEPENDENCIES: story_memory.READING_SCHEMA} if 'understanding' in book else {}),
                             **({OPENING_BOUNDS: OPENING_BOUNDS_CAPABILITY} if stage == 'opening_options' else {}),
                             **({VOLUME_OUTLINE: VOLUME_OUTLINE_CAPABILITY} if (book.get('contract') or {}).get('volume_outline') else {}),
                             **({SCENE_MEMORY: SCENE_MEMORY_CAPABILITY} if scene_task else {}),
                             **({HOOK_LINKS: HOOK_LINKS_CAPABILITY} if tracking else {})},
            # The active lexical policy travels with the task material, together with the fields
            # this dispatch actually inspects, so a worker never has to guess either one.
            'policy': policy_material(book.get('lexical_policy'), [stage, *tuple(payload.get('also', ()))]),
            'prose': prose, 'blind': stage in ('chapter_review', 'scope_review', 'revision_review'), 'obligations': obligations}
    if brief:
        task['brief'] = brief
    return validate_work(task)
