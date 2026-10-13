"""Query/assembly layer. Sources are immutable; selection never erases availability."""
from __future__ import annotations

import copy
import json
from .contracts import FACT_CHECKS, TASK, dump
from . import briefs, creation, world
from .planning import policy_block, volume_for
from .workflow import node_map


def scoped_state(state, participants):
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
    return None


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
    # A worker needs the material its stage decides on, and nothing else: the opening reads the
    # closed choices, not a contract that does not exist yet or a state that is still empty.
    opening_stage = stage in ('opening_options', 'world_model', 'world_review', 'opening_contract', 'contract_review')
    add('contract', book['contract'], not opening_stage)
    participants = plan['participants'] if plan else list(book['state']['entities'])
    add('state', scoped_state(book['state'], participants), not opening_stage)
    add('complete_state', book['state'], False)
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
        add('world_model', model, stage in ('book_plan', 'opening_contract', 'contract_review'))
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
                        todo.append(ref)
            add('world_records', {key: records_by_id[key] for key in sorted(selected_world)})
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
                select(parent)
        for ident in plan['node_ids']:
            select(ident)
        add('story', [nodes[ident] for ident in sorted(selected)])
    for scope, design in book['designs'].items():
        add('design:' + scope, design, stage in ('volume_plan', 'plan') and scope in ('book', 'volume:' + volume_for(book['contract'], chapter)['id']))
    payload = copy.deepcopy(job.payload or {})
    if stage in ('book_plan', 'volume_plan', 'world_model') and book['proposal']:
        add('previous_proposal', book['proposal'])
    if stage in ('design_review', 'contract_review', 'world_review'):
        add('proposal', book['proposal'])
        prose = [{'chapter': 0, 'hash': repo.document(dump(book['proposal']['data']))}]
    elif stage == 'chapter_review':
        prose = [{'chapter': chapter, 'hash': repo.document(book['draft']['prose'])}]
    elif stage in ('scope_review', 'scope_synthesis'):
        prose = [{'chapter': row['n'], 'hash': row['prose']} for row in repo.headers(book['branch']) if job.first <= row['n'] <= job.last]
        if stage == 'scope_synthesis':
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
            obligations.append({'id': 'repair:' + str(i), 'category': 'facts' if finding['criterion'] in FACT_CHECKS else 'reader', 'text': finding['reason']})
    if book['revision_run']:
        add('revision_instruction', book['revision_run']['reason'])
    if book['feedback']:
        add('author_feedback', book['feedback'])
    if book.get('prior_candidate') and book['prior_candidate']['chapter'] == chapter:
        add('prior_candidate', book['prior_candidate'], stage in ('repair', 'redesign', 'chapter_review'))
    add('historical_index', [{'chapter': r['n'], 'prose_hash': r['prose'], 'summary': r['summary']} for r in repo.headers(book['branch'])], False)
    brief = _brief(book, job)
    task = {'schema': TASK, 'stage': stage, 'chapter': chapter, 'scope': job.scope,
            'first': job.first, 'last': job.last, 'payload': payload, 'branch': book['branch'],
            'revision': book['revision'], 'records': records, 'required': required,
            # The active lexical policy travels with the task material, together with the fields
            # this dispatch actually inspects, so a worker never has to guess either one.
            'policy': policy_block(book, [stage, *tuple(payload.get('also', ()))]),
            'prose': prose, 'blind': stage in ('chapter_review', 'scope_review'), 'obligations': obligations}
    if brief:
        task['brief'] = brief
    return task
