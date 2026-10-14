"""Query/assembly layer. Sources are immutable; selection never erases availability."""
from __future__ import annotations

import copy
import json
from .contracts import CHECKS_VERSION, EDITORIAL_VERSION, TASK, Job, checks_for, dump, digest
from . import briefs, creation, narrative, scopes, world, editorial
from .planning import outline_policy, policy_block, volume_for
from .workflow import node_map


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
    return view


def _brief(book, job):
    """The one page this dispatch needs, generated here instead of shipping whole guides."""
    previous = []
    for row in (book.get('creation') or {}).get('selections', []):
        gate = row['gate']
        title = next((name for ident, name in creation.GATES if ident == gate), gate)
        previous.append((title, _selection_line(row['option'])))
    payload = job.payload or {}
    if job.stage == 'opening_options':
        return briefs.opening_options(payload.get('gate', {}), payload.get('lens_brief', ''), previous)
    if job.stage == 'world_model':
        return briefs.world_model(previous=previous)
    return briefs.stage(job.stage, {**payload, 'editorial': editorial.enabled(book)})


def _selection_line(option):
    """One compact line per closed choice: the direction, not a copy of the record.

    The worker needs to know which way the book is already committed; the exact values live in
    opening_choices/opening_basis and are checked by `creation.validate_contract` at the contract
    stage, so repeating every field here would double the material for no added signal.
    """
    value = option.get('value', {})
    gist = ''
    for key in ('reader_promise', 'ending', 'story_engine', 'world_premise', 'identity'):
        if isinstance(value.get(key), str) and value[key].strip():
            gist = value[key].strip()
            break
    line = option.get('title', '')
    if gist:
        line += '：' + (gist[:60] + '…' if len(gist) > 60 else gist)
    return line


def build(repo, book, job):
    records, required, prose = {}, [], []
    def add(name, value, needed=True):
        records[name] = repo.document(value)
        if needed:
            required.append(name)
    stage, chapter = job.stage, job.chapter
    plan = book['plans'].get(str(chapter))
    enhanced = editorial.enabled(book)
    version = EDITORIAL_VERSION if enhanced else CHECKS_VERSION
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
    if enhanced:
        add('complete_profiles', book['profiles'], False)
        add('profile_history', book.get('profile_history', []), False)
        if stage in ('scope_review', 'scope_synthesis'):
            add('scope_profiles', {p: book['profiles'][p] for p in participants if p in book['profiles']})
        add('effective_layout', editorial.effective_contract(book)['volumes'])
        if book.get('style_anchor'):
            add('style_anchor', book['style_anchor'])
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
        add('world_model', model, stage in ('book_plan', 'volume_plan', 'volume_outline', 'outline_review', 'design_review', 'opening_contract', 'contract_review'))
        add('world_core', {'premise': model['premise'], 'rules': model['rules'], 'story_capacity': model['story_capacity']})
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
            if tracking:
                add('world_author_records', original, False)
                visible = {k: v for k, v in original.items() if not k.startswith('mysteries:')}
                add('world_records', visible)
                add('disclosure_boundary', {'allowed_changes': plan['disclosures'], 'reader_current': scoped_state(book['state'], participants, plan, chapter)['reader_knowledge'],
                     'author_secrets': [{'id': k, 'disclosure': v['disclosure'], 'causal_role': v['causal_role']} for k, v in original.items() if k.startswith('mysteries:')],
                     'source': '幕后真相见可选 world_author_records；作者真相不能自动成为人物知情或本章披露。'})
            else:
                add('world_records', original)
    if plan:
        add('plan', plan)
        add('profiles', {p: book['profiles'][p] for p in participants if p in book['profiles']})
        nodes = node_map(book)
        selected = set()
        def select(ident):
            if ident in selected:
                return
            selected.add(ident)
            for parent in nodes[ident]['depends_on']:
                if tracking:
                    selected.add(parent)
                else:
                    select(parent)
        for ident in plan['node_ids']:
            select(ident)
        add('story', [nodes[ident] for ident in sorted(selected)])
    for scope, design in book['designs'].items():
        needed = stage in ('volume_plan', 'plan', 'alignment_plan', 'alignment_review') and scope in ('book', 'volume:' + volume_for(editorial.effective_contract(book), chapter)['id'])
        add('design:' + scope, design, needed and not tracking)
        if needed and tracking:
            end = job.last or chapter + book['contract']['planning_window'] - 1
            add('frontier:' + scope, {**{k: v for k, v in design.items() if k not in ('nodes', 'chapters', 'outline_reviews')},
                'nodes': [n for n in design['nodes'] if narrative.progress(book['state'], n['id']) != 'resolved'
                          and n['window'][0] <= end and chapter <= n['window'][1]]})
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
        add('word_budget', narrative.budget_for(book, chapter))
    payload = copy.deepcopy(job.payload or {})
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
                                      'sources': editorial.sources(book, job.scope), 'prose_hashes': hashes}
    if stage in ('book_plan', 'volume_plan', 'volume_outline', 'world_model') and book['proposal']:
        add('previous_proposal', book['proposal'])
    if stage in ('design_review', 'outline_review', 'contract_review', 'world_review'):
        add('proposal', book['proposal'])
        prose = [{'chapter': 0, 'hash': repo.document(dump(book['proposal']['data']))}]
    elif stage == 'chapter_review':
        prose = [{'chapter': chapter, 'hash': repo.document(book['draft']['prose'])}]
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
    if stage in ('write', 'repair', 'redesign', 'plan'):
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
    if book['feedback']:
        add('author_feedback', book['feedback'])
    if book.get('prior_candidate') and book['prior_candidate']['chapter'] == chapter:
        add('prior_candidate', book['prior_candidate'], stage in ('repair', 'redesign', 'chapter_review'))
    # A frozen head addresses shared immutable chapter pages. Re-dispatching another role
    # neither copies every summary nor re-reads every historical event.
    add('history_source', repo.history_snapshot(book['branch']), False)
    brief = _brief(book, Job(stage, chapter, job.scope, job.first, job.last, payload))
    task = {'schema': TASK, 'stage': stage, 'chapter': chapter, 'scope': job.scope,
            'first': job.first, 'last': job.last, 'payload': payload, 'branch': book['branch'],
            'revision': book['revision'], 'records': records, 'required': required,
            'checks_version': version, 'narrative_tracking': tracking,
            'capabilities': {**({'editorial': 'editorial/1'} if enhanced else {}),
                             **({'volume_outline': 'volume-outline/1'} if (book.get('contract') or {}).get('volume_outline') else {}),
                             **({'hook_links': 'hook-links/1'} if tracking else {})},
            # The active lexical policy travels with the task material, together with the fields
            # this dispatch actually inspects, so a worker never has to guess either one.
            'policy': policy_block(book, [stage, *tuple(payload.get('also', ()))]),
            'prose': prose, 'blind': stage in ('chapter_review', 'scope_review'), 'obligations': obligations}
    if brief:
        task['brief'] = brief
    return task
