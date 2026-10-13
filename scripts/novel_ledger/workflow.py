"""Pure lifecycle decisions and stage transitions. No repository or host imports."""
from __future__ import annotations

import copy
from .contracts import DESIGN_CHECKS, LONG_CHECKS, WORLD_CHECKS, REPAIRS, REDESIGNS, Job, Outcome, digest, han_count, require, text
from . import creation, facts, planning, quality, world


def new_book(contract, source=''):
    contract = planning.validate_contract(contract)
    book = {'contract': contract, 'contract_source': source, 'state': facts.seed(contract),
            'branch': 'main', 'revision': 0, 'status': 'running', 'target': 1, 'finish': False, 'written_han': 0,
            'lexical_policy': [{'version': 1, 'policy': planning.resolve_policy({}), 'source': '内置默认'}],
            'pilot': None, 'designs': {}, 'plans': {}, 'profiles': {}, 'draft': None,
            'proposal': None, 'reviews': {}, 'scope_parts': {}, 'rework': {}, 'revision_run': None, 'feedback': [], 'decisions': []}
    planning.check_contract_names(contract, planning.policy_of(book))
    return book


def preparing_book(source='', guided=False):
    return {'contract': None, 'contract_source': source, 'state': facts.seed({}),
            'branch': 'main', 'revision': 0, 'status': 'preparing', 'target': 1, 'finish': False, 'written_han': 0,
            'lexical_policy': [{'version': 1, 'policy': planning.resolve_policy({}), 'source': '内置默认'}],
            'pilot': None, 'designs': {}, 'plans': {}, 'profiles': {}, 'draft': None,
            'proposal': None, 'reviews': {}, 'scope_parts': {}, 'rework': {}, 'revision_run': None, 'feedback': [], 'decisions': [],
            'creation': creation.begin(source) if guided else None}


def review_key(scope, first, last, headers):
    return digest({'scope': scope, 'first': first, 'last': last,
                   'chapters': [r['chain'] for r in headers if first <= r['n'] <= last]})


def node_map(book):
    return {node['id']: node for design in book['designs'].values() for node in design['nodes']}


def repair_stage(budget):
    if budget.get('redesigns', 0) >= REDESIGNS:
        return 'exhausted'
    return 'repair' if budget.get('repairs', 0) < REPAIRS else 'redesign'


def choose(book, headers):
    opening = book.get('creation')
    if book['status'] in ('preparing', 'running') and opening and opening['phase'] == 'choosing':
        if opening['board']:
            return {'action': 'await_choice', **creation.view(opening)}
        gate = creation.current(opening)
        return Job('opening_options', 0, 'opening', payload={'gate': gate, 'round': opening['round'],
            'creative_lens': creation.LENSES[opening['round'] % len(creation.LENSES)]})
    if book['status'] != 'running':
        return {'action': book['status']}
    if book['proposal']:
        proposal = book['proposal']
        if proposal.get('needs_repair'):
            stage = 'world_model' if proposal['scope'] == 'world' else 'book_plan' if proposal['scope'] == 'book' else 'volume_plan'
            return Job(stage, proposal['chapter'], scope=proposal['scope'], payload={'repair': True})
        stage = 'world_review' if proposal['scope'] == 'world' else 'contract_review' if proposal['scope'] == 'contract' else 'design_review'
        return Job(stage, proposal['chapter'], scope=proposal['scope'])
    if book.get('pending_contract'):
        return {'action': 'contract_ready'}
    if opening and opening['phase'] == 'world':
        return Job('world_model', 1, 'world')
    if opening and opening['phase'] == 'contract':
        return Job('opening_contract', 1, 'contract')
    if opening and opening['phase'] == 'ready' and book.get('opening_world_only') and not book.get('run_authorized'):
        return {'action': 'world_ready', 'selection_hash': opening['selection_hash']}
    contract = book['contract']
    if 'book' not in book['designs']:
        return Job('book_plan', 1, scope='book')
    head = headers[-1]['n'] if headers else 0
    if head and (not book['pilot'] or book['pilot']['prose'] != headers[0]['prose']):
        return {'action': 'await_author', 'chapter': 1, 'prose_hash': headers[0]['prose']}
    if book['draft']:
        draft = book['draft']
        return Job(draft['stage'], draft['chapter'])
    if head:
        volume = planning.volume_for(contract, head)
        scopes = []
        if head % contract['review_interval'] == 0:
            scopes.append(('interval', max(1, head - contract['review_interval'] + 1), head))
        if head == volume['end']:
            scopes.append(('volume:' + volume['id'], volume['first'], head))
        revision = book['revision_run']
        if revision and head >= revision['last']:
            scopes.append(('revision', revision['first'], head))
        if book['finish'] and head == contract['volumes'][-1]['end']:
            scopes.append(('book', 1, head))
        for scope, first, last in scopes:
            key = review_key(scope, first, last, headers)
            if key not in book['reviews']:
                parts = book['scope_parts'].get(key, [])
                next_first = parts[-1]['last'] + 1 if parts else first
                if next_first <= last:
                    return Job('scope_review', last, scope, next_first, min(last, next_first + contract['review_chunk'] - 1), {'review_key': key, 'scope_first': first, 'scope_last': last})
                return Job('scope_synthesis', last, scope, first, last, {'review_key': key})
        if revision and head >= revision['last']:
            return {'action': 'revision_ready'}
    if head >= book['target']:
        return {'action': 'ready_to_complete' if book['finish'] else 'target_reached'}
    chapter = head + 1
    volume = planning.volume_for(contract, chapter)
    require(volume is not None, 'chapter_limit', '到达约定章节边界，需作者改约。')
    scope = 'volume:' + volume['id']
    if scope not in book['designs']:
        return Job('volume_plan', chapter, scope)
    if str(chapter) not in book['plans']:
        last = min(volume['end'], book['target'], chapter + contract['planning_window'] - 1)
        return Job('plan', chapter, 'window', chapter, last)
    plan = book['plans'][str(chapter)]
    missing = [ident for ident in plan['participants'] if ident not in book['profiles']]
    if missing:
        return Job('profiles', chapter, payload={'entities': missing})
    budget = book['rework'].get(str(chapter), {})
    if budget.get('initial_used'):
        stage = repair_stage(budget)
        if stage == 'exhausted':
            return {'action': 'repair_exhausted', 'chapter': chapter}
        return Job(stage, chapter)
    return Job('write', chapter)


def spend(book, chapter, stage):
    budget = book['rework'].setdefault(str(chapter), {'repairs': 0, 'redesigns': 0})
    if stage == 'write':
        require(not budget.get('initial_used'), 'repair_budget', '同一章不能通过重新开初稿重置修复轮次。')
        budget['initial_used'] = True
    elif stage == 'repair':
        require(budget['repairs'] < REPAIRS, 'repair_budget', '返修额度已用完。')
        budget['repairs'] += 1
    elif stage == 'redesign':
        require(budget['redesigns'] < REDESIGNS, 'repair_budget', '重设计额度已用完。')
        budget['redesigns'] += 1


def route_repair(book, draft, findings):
    budget = book['rework'].setdefault(str(draft['chapter']), {'repairs': 0, 'redesigns': 0})
    combined = draft.get('findings', []) + copy.deepcopy(findings)
    draft['findings'] = list({digest(f): f for f in combined}.values())
    next_stage = repair_stage(budget)
    if next_stage == 'exhausted':
        book['status'] = 'paused'
        book['pause_reason'] = '修复耗尽，保留候选正文与全部失败记录。'
        draft['stage'] = 'exhausted'
    else:
        draft['stage'] = next_stage
    book['draft'] = draft


def apply(book, task, data, actor, sources):
    require(isinstance(data, dict), 'result', 'data 须为对象。')
    book = copy.deepcopy(book)
    stage, chapter = task['stage'], task['chapter']
    row = None
    if stage == 'opening_options':
        book['creation'] = creation.offer(book['creation'], data)
        if book['creation']['board']['gate']['id'] == 'protagonist':
            policy = planning.policy_of(book)
            for option in book['creation']['board']['options']:
                planning.check_text(option['value']['name'], policy, names=True)
    elif stage == 'world_model':
        opening = book['creation']
        model = world.validate(data, creation.selected(opening), opening['selection_hash'])
        policy = planning.policy_of(book)
        for character in model['characters']:
            planning.check_text(character['name'], policy, names=True)
        old = book['proposal'] or {}
        book['proposal'] = {'scope': 'world', 'chapter': 1, 'data': model, 'producer': actor, 'attempts': old.get('attempts', 0)}
    elif stage == 'world_review':
        proposal = book['proposal']
        require(actor != proposal['producer'], 'review_independence', '世界模型须由独立核验者检查。')
        review = quality.checks(data, WORLD_CHECKS, sources)
        if review['verdict'] == 'pass':
            book['world'] = proposal['data']
            book['world_review'] = {'receipt': review, 'producer': proposal['producer'], 'reviewer': actor}
            book['proposal'] = None
            book['creation']['phase'] = 'contract'
        else:
            proposal['attempts'] += 1
            proposal['findings'] = review['findings']
            if proposal['attempts'] > REPAIRS:
                book.update(status='paused', pause_reason='世界模型核验修复耗尽，候选保留。')
            else:
                proposal['needs_repair'] = True
    elif stage == 'opening_contract':
        contract = planning.validate_contract(data)
        creation.validate_contract(contract, book['creation'], book['world'])
        planning.check_contract_names(contract, planning.policy_of(book))
        book['proposal'] = {'scope': 'contract', 'chapter': 1, 'data': contract, 'producer': actor,
                            'source': '用户逐门选择；完整选择版本 ' + book['creation']['selection_hash']}
    elif stage in ('book_plan', 'volume_plan'):
        known = node_map(book)
        design = planning.validate_design(data, known)
        old = book['proposal'] or {}
        book['proposal'] = {'scope': task['scope'], 'chapter': chapter, 'data': design, 'producer': actor, 'attempts': old.get('attempts', 0)}
    elif stage == 'design_review':
        proposal = book['proposal']
        require(proposal is not None and actor != proposal['producer'], 'review_independence', '设计核验须独立于提案者。')
        review = quality.checks(data, DESIGN_CHECKS, sources)
        if review['verdict'] == 'pass':
            book['designs'][proposal['scope']] = proposal['data']
            book['proposal'] = None
        else:
            proposal['attempts'] += 1
            proposal['findings'] = review['findings']
            if proposal['attempts'] > REPAIRS:
                book.update(status='paused', pause_reason='设计核验返修耗尽，候选保留。')
            else:
                proposal['needs_repair'] = True
    elif stage == 'contract_review':
        proposal = book['proposal']
        require(actor != proposal['producer'], 'review_independence', '改约核验须独立于作者要求整理者。')
        review = quality.checks(data, DESIGN_CHECKS, sources)
        if review['verdict'] == 'pass':
            book['pending_contract'] = proposal
            book['pending_contract_reviewer'] = actor
            book['proposal'] = None
        else:
            book.update(status='paused', pause_reason='改约未通过；旧约定和稿件完整保留。')
            proposal['findings'] = review['findings']
    elif stage == 'plan':
        plans = planning.validate_plans(data, task['first'], task['last'], node_map(book), book['state'], book['contract'], book.get('world'))
        for plan in plans:
            book['plans'][str(plan['chapter'])] = plan
    elif stage == 'profiles':
        profiles = planning.validate_profiles(data, task['payload']['entities'])
        for profile in profiles:
            book['profiles'][profile['entity']] = profile
    elif stage in ('write', 'repair', 'redesign'):
        require(all(text(data.get(k)) for k in ('title', 'prose', 'summary', 'self_check')), 'draft', '执笔需要 title/prose/summary/具体 self_check。')
        require('events' not in data and 'candidate_events' not in data, 'writer_events', '事实由独立审稿者从正文重建。')
        planning.check_text(data['title'] + '\n' + data['prose'], planning.policy_of(book))
        spend(book, chapter, stage)
        old = book['draft'] or {}
        draft = {'chapter': chapter, 'title': data['title'], 'prose': data['prose'], 'producer': actor,
                 'summary': data['summary'], 'self_check': data['self_check'], 'stage': 'chapter_review',
                 'history': old.get('history', []) + ([{'stage': old['stage'], 'prose': old['prose'], 'findings': old.get('findings', [])}] if old else []),
                 'findings': old.get('findings', []) if old else [f for f in book.get('carry_findings', []) if f.get('target_chapter') == chapter]}
        count = han_count(data['prose'])
        if not book['contract']['chapter_min'] <= count <= book['contract']['chapter_max']:
            route_repair(book, draft, [{'criterion': 'substance', 'severity': 'quality', 'target_chapter': chapter,
                                      'repair_scope': 'chapter', 'reason': '汉字篇幅不在约定区间。', 'actual_han': count}])
        else:
            book['draft'] = draft
    elif stage == 'chapter_review':
        draft = book['draft']
        require(draft is not None and actor != draft['producer'], 'review_independence', '正文审稿须独立于当前执笔者。')
        obligations = task['obligations']
        fact_review, reader = quality.chapter_review(data, sources, obligations)
        if fact_review['verdict'] != 'pass' or reader['verdict'] != 'pass':
            findings = [f for review in (fact_review, reader) for f in review['findings'] if f['severity'] != 'note']
            require(all(f['target_chapter'] == chapter for f in findings), 'repair_scope', '本章审稿只能安排当前章返修，历史缺陷走修订。')
            route_repair(book, draft, findings)
        else:
            state, events = facts.settle(book['state'], fact_review['events'], draft['prose'], chapter)
            require(state['clock'] - book['state']['clock'] == fact_review['elapsed_days'], 'elapsed_days', '正文时间声明与事件结算不一致。')
            plan = book['plans'][str(chapter)]
            require(all(book['state']['clock'] <= s['day'] <= state['clock'] for s in plan.get('schedule', [])),
                    'schedule', '当前章硬日程不在已核验的主线时间区间内。')
            require(all(p in state['entities'] for p in plan['participants']), 'entity_coverage', '计划参与人尚无已核验的正文身份。')
            for item in state['entities'].values():
                for name in [item['name']] + item.get('aliases', []):
                    planning.check_text(name, planning.policy_of(book), names=True)
            row = {'n': chapter, 'title': draft['title'], 'prose': draft['prose'], 'events': events,
                   'plan': plan, 'review': {'facts': fact_review, 'reader': reader, 'session': actor,
                   'writer': draft['producer'], 'first_read': task['first_read'], 'obligations': obligations},
                   'state_hash': digest(state), 'summary': fact_review['summary'], 'han': han_count(draft['prose'])}
            book['state'], book['draft'] = state, None
            book['written_han'] += row['han']
            book['carry_findings'] = [f for f in book.get('carry_findings', []) if f.get('target_chapter') != chapter]
    elif stage in ('scope_review', 'scope_synthesis'):
        review = quality.checks(data, LONG_CHECKS, sources)
        coverage = data.get('coverage')
        require(isinstance(coverage, list) and len(coverage) == len(sources) and all(isinstance(r, dict) and type(r.get('chapter')) is int for r in coverage)
                and {r['chapter'] for r in coverage} == set(sources), 'scope_coverage', '跨章核验须逐章给出覆盖证据。')
        for item in coverage:
            require(text(item.get('reason')) and item.get('evidence', {}).get('chapter') == item['chapter'], 'scope_coverage', '逐章覆盖需要本章理由与证据。')
            facts.evidence(item['evidence'], sources)
        if review['verdict'] == 'pass':
            accepted = {'scope': task['scope'], 'first': task['first'], 'last': task['last'], 'receipt': review, 'coverage': copy.deepcopy(coverage)}
            if stage == 'scope_review':
                book['scope_parts'].setdefault(task['payload']['review_key'], []).append(accepted)
            else:
                book['reviews'][task['payload']['review_key']] = accepted
        else:
            book.update(status='paused', pause_reason='跨章核验发现缺陷，按明确 target_chapter 开修订分支。')
            book['scope_findings'] = review['findings']
    else:
        require(False, 'stage', '未注册的任务阶段。')
    book['revision'] += 1
    return Outcome(book, row)
