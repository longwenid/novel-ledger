"""Pure lifecycle decisions and stage transitions. No repository or host imports."""
from __future__ import annotations

import copy
from .contracts import (AUTHOR_CHANNEL_STAGES, FAST_REVIEW_BLOCK, HOOK_LINKS_CAPABILITY,
                        OPENING_BOUNDS_CAPABILITY, OPENING_VERSION, READING_DEPENDENCIES_CAPABILITY, REPAIRS, REDESIGNS,
                        SCENE_IDENTITY_CAPABILITY, UNDERSTANDING_CAPABILITY, PIPELINE_SHAPES, tier_of,
                        Job, Outcome, capabilities_for, checks_for, digest, han_count, require, text)
from . import creation, facts, narrative, planning, quality, scopes, world, craft, editorial, understanding, design_queries, ledger
from .evidence import evidence

# Where the engine stops moving on its own, and who decides what happens next. The value of this
# table is that no stop is a bare refusal with nowhere to go: a real run hit the same dead end three
# times (a design candidate, one chapter, and a revision whose own scope review flagged a chapter
# outside its range), which is why the author channel is now a declared part of every stop rather
# than something each stopping point has to remember to add.
STOP_POINTS = {
    'author_block': 'answer',                       # an open question is answered; nothing moves first.
    'repair-exhausted:world_review': 'author_decision',
    'repair-exhausted:design_review': 'author_decision',
    'repair-exhausted:outline_review': 'author_decision',
    'repair-exhausted:chapter_repair': 'author_decision',
    'repair-stalled:chapter_repair': 'author_decision',
    'scope-findings:open-revision': 'author_decision',
    'revision-blocked': 'plan_authorization',       # revise --proposal-hash with the author's own words
    'scope-fix': 'review_driven_revision',          # revise --from-chapter N covers the findings
    'remedy-exhausted': 'recontract',               # the remedy budget is spent: change the premise
}
# What each channel means, for readers of the table and for the test that keeps it honest.
AUTHOR_CHANNELS = {
    'answer': '问题已在等作者回答，answer 记录选择后流程才继续。',
    'author_decision': '额度/范围/未决导致停下：engine 生成三选（再一轮／接受并记为未解决项／重开或撤销），answer 落库。',
    'plan_authorization': '方案超出自动回改范围：作者用 revise --proposal-hash 绑定准确 plan_hash 授权。',
    'review_driven_revision': '审稿发现的缺陷由 revise --from-chapter 开一次覆盖它们的修订。',
    'recontract': '改案额度已尽：改的是前提，走 recontract 并重新独立核验。',
}


def tier_id(opening):
    """The size class this opening was decided at, for requirements declared per tier."""
    scale = (creation.selected(opening) or {}).get('scale') or {}
    return scale.get('tier')


def merges_volume_design(book):
    """Whether this project's single volume reuses the book design instead of a second dispatch.

    The decision is declared per tier in PIPELINE_SHAPES and requires a one-volume contract:
    with one volume there is no boundary for a volume design to own that the book design has
    not already been reviewed against.
    """
    contract = book.get('contract') or {}
    tier = tier_of(contract)
    volumes = contract.get('volumes') or []
    return (tier is not None and len(volumes) == 1
            and bool(PIPELINE_SHAPES.get(tier['id'], {}).get('merge_volume_design')))


def install_merged_volume_design(book, scope, data):
    """On tiers that merge, the accepted book design is also the single volume's design.

    The copy is deliberate: outline batches accumulate `chapters` on the volume design, and the
    book design must not mutate along with them. Returns the alias key when one was installed.
    """
    if scope != 'book' or not merges_volume_design(book):
        return None
    volumes = editorial.effective_contract(book)['volumes']
    key = 'volume:' + volumes[0]['id']
    book['designs'][key] = copy.deepcopy(data)
    return key


def new_book(contract, source=''):
    contract = planning.validate_contract(contract)
    book = {'contract': contract, 'contract_source': source, 'state': facts.seed(contract),
            'branch': 'main', 'revision': 0, 'status': 'running', 'target': 1, 'finish': False, 'written_han': 0,
            'lexical_policy': [{'version': 1, 'policy': planning.resolve_policy({}), 'source': '内置默认'}],
            'pilot': None, 'designs': {}, 'plans': {}, 'profiles': {}, 'understanding': understanding.empty(), 'draft': None,
            'proposal': None, 'reviews': {}, 'scope_parts': {}, 'rework': {}, 'revision_run': None, 'feedback': [], 'decisions': []}
    planning.check_contract_names(contract, planning.active_policy(book.get('lexical_policy')))
    return book


def preparing_book(source='', guided=False, opening_version=OPENING_VERSION):
    return {'contract': None, 'contract_source': source, 'state': facts.seed({}),
            'branch': 'main', 'revision': 0, 'status': 'preparing', 'target': 1, 'finish': False, 'written_han': 0,
            'lexical_policy': [{'version': 1, 'policy': planning.resolve_policy({}), 'source': '内置默认'}],
            'pilot': None, 'designs': {}, 'plans': {}, 'profiles': {}, 'understanding': understanding.empty(), 'draft': None,
            'proposal': None, 'reviews': {}, 'scope_parts': {}, 'rework': {}, 'revision_run': None, 'feedback': [], 'decisions': [],
            'creation': creation.begin(source, opening_version) if guided else None}


def review_key(scope, first, last, headers, editorial_context=None):
    return digest({'scope': scope, 'first': first, 'last': last,
                   'chapters': [r['chain'] for r in headers if first <= r['n'] <= last],
                   **({'editorial_context': editorial_context} if editorial_context else {})})


def node_map(book):
    return design_queries.node_map(book['designs'])


def repair_stage(budget):
    if budget.get('redesigns', 0) >= REDESIGNS:
        return 'exhausted'
    return 'repair' if budget.get('repairs', 0) < REPAIRS else 'redesign'


def hold_for_author(book, review, holder=None):
    """Hand an author-level finding up through the existing author channel.

    No writer can repair a premise the author has not settled, so such a finding must not consume a
    repair round: it becomes the pending question `resume` refuses to bypass. The caller decides how
    its own candidate is disposed of, since only it knows what the next dispatch should re-draft.
    Returns True when held.
    """
    decision = quality.author_decision(review.get('findings'))
    if decision is None or book.get('author_block'):
        # One pending question at a time; an already-registered decision keeps priority.
        return False
    if holder is not None:
        holder['findings'] = review['findings']
    book['author_block'] = {'id': decision['id'], 'question': decision['question'],
                            'options': copy.deepcopy(decision['options'])}
    book.update(status='paused', pause_reason=decision['question'])
    return True


EXHAUSTION_OPTIONS = (
    {'label': '再返修一轮（只按这几条改）',
     'impact': '给本阶段加一轮返修额度：仍只改被点名的记录，改完再独立核验一次。'
               '额度不是无限的，这一轮用尽后还会来问你。'},
    {'label': '接受当前候选，把这几条记为未解决项继续',
     'impact': '候选进入下一阶段，这些发现不会被删掉，会记成未解决项，完本篇审计与全书视图都能看到。'
               '独立核验者给的是 fix，这一步等于你以作者身份承担这处风险。'},
    {'label': '重开本阶段或改约',
     'impact': '按现有路径重做本阶段或改约定：已有正文时改约会在新分支自第 1 章重写重审全书，'
               '代价随已写章数增长；没有正文时只是重新核验。'},
)

# The author's answer to an exhausted design review, by option position.
REPAIR_AGAIN = '再返修一轮（只按这几条改）'
ACCEPT_OPEN = '接受当前候选，把这几条记为未解决项继续'


def hold_for_exhaustion(book, proposal, review, stage):
    """Ask the author how to proceed when a design candidate has spent its repair rounds.

    Stopping with a bare pause left the author no channel at all: the two existing escapes
    (recontract, opening back) discard a nearly verified candidate for a few local fixes. The
    findings go up as a decision instead, and whichever way the author answers stays on record.
    """
    findings = review['findings']
    proposal['findings'] = findings
    blockers = sum(1 for finding in findings if finding['severity'] == 'blocker')
    book['author_block'] = {
        'id': 'repair-exhausted:' + stage,
        'question': '本阶段返修额度已用尽，独立核验仍给出 %d 条意见（其中 blocker %d 条），接下来怎么处理？'
                    % (len(findings), blockers),
        'options': copy.deepcopy(list(EXHAUSTION_OPTIONS))}
    book.update(status='paused', pause_reason=book['author_block']['question'])
    return book['author_block']


def allow_another_repair(book):
    """One more repair round for the current candidate, granted by the author."""
    proposal = book['proposal']
    require(proposal is not None, 'proposal', '没有可返修的候选。')
    proposal['attempts'] = REPAIRS
    proposal['needs_repair'] = True


def accept_with_findings(book, stage):
    """Accept a candidate whose last review asked for changes, and keep those changes open.

    The transition is the pass transition, so nothing downstream has to know; what differs is that
    the findings are recorded as unresolved instead of disappearing with the receipt.
    """
    proposal = book['proposal']
    require(proposal is not None, 'proposal', '没有可接受的候选。')
    findings = copy.deepcopy(proposal.get('findings') or [])
    book.setdefault('accepted_findings', []).append(
        {'stage': stage, 'scope': proposal.get('scope'), 'findings': findings})
    book['carry_findings'] = list(book.get('carry_findings') or []) + findings
    if stage == 'world_review':
        book['world'] = proposal['data']
        book['world_review'] = {'receipt': {'verdict': 'accepted_with_findings', 'findings': findings},
                                'producer': proposal['producer'], 'reviewer': None}
        book['proposal'] = book.get('contract_draft') or None
        book.pop('contract_draft', None)
        if book.get('creation'):
            book['creation']['phase'] = 'contract'
    elif stage == 'design_review':
        book['designs'][proposal['scope']] = proposal['data']
        install_merged_volume_design(book, proposal['scope'], proposal['data'])
        book['proposal'] = None
    elif stage == 'outline_review':
        design = book['designs'][proposal['scope']]
        design.setdefault('chapters', []).extend(copy.deepcopy(proposal['data']['chapters']))
        design.setdefault('outline_reviews', []).append(
            {'first': proposal['first'], 'last': proposal['last'], 'producer': proposal['producer'],
             'reviewer': None, 'data_hash': digest(proposal['data']), 'findings': findings,
             'verdict': 'accepted_with_findings'})
        book['proposal'] = None
    else:
        require(False, 'stage', '该阶段没有可接受的候选。')
    book['status'] = 'running'


def stage_for_proposal(proposal):
    """Which review stage a stuck proposal came from, without a second field to keep in sync."""
    require(isinstance(proposal, dict), 'proposal', '没有可处理的候选。')
    if proposal.get('kind') == 'volume_outline':
        return 'outline_review'
    if proposal.get('scope') == 'world':
        return 'world_review'
    return 'design_review'


def hold_for_draft_exhaustion(book):
    """Ask the author how to proceed when one chapter has spent its repair rounds.

    A chapter that is close enough that the reviewer is still only asking for local fixes used to
    dead-end here: `resume` refused with a budget code and the only exits were discarding the whole
    candidate or changing the contract. The author decides instead, and the decision is recorded.
    """
    draft = book['draft']
    findings = draft.get('findings') or []
    book['author_block'] = {
        'id': 'repair-exhausted:chapter_repair',
        'question': '第 %d 章的返修额度已用尽，独立章审仍给出 %d 条意见，接下来怎么处理？'
                    % (draft['chapter'], len(findings)),
        'options': copy.deepcopy(list(EXHAUSTION_OPTIONS))}
    book.update(status='paused', pause_reason=book['author_block']['question'])
    return book['author_block']


# A finding that survives this many repair rounds is a stall, not slow convergence: the next
# identical round only spends budget and an independent re-review. A real chapter went four
# rounds on the same two findings before anyone could see the loop was not converging at all.
STALL_AFTER_ROUNDS = 2


def hold_for_stalled_repeat(book, draft, stalled):
    """Hand a non-converging repair loop to the author while budget still remains.

    The spent-budget stop catches loops that ran out of rounds; this one catches loops that are
    burning them without moving: the same findings, verbatim, after a repair that claimed to fix
    them. The options are the spent-budget three, and one more granted round resets the counter
    for the findings named here, so an author who sees actual movement can keep going.
    """
    draft['stage'] = 'stalled'
    book['author_block'] = {
        'id': 'repair-stalled:chapter_repair',
        'question': '第 %d 章的同 %d 条意见已连续 %d 轮返修未解决，再按原样返修不会收敛，接下来怎么处理？'
                    % (draft['chapter'], len(stalled), STALL_AFTER_ROUNDS),
        'options': copy.deepcopy(list(EXHAUSTION_OPTIONS))}
    book.update(status='paused', pause_reason=book['author_block']['question'])
    return book['author_block']


def resolve_draft_exhaustion(book, option):
    """Apply the author's answer for a spent chapter repair budget."""
    draft = book['draft']
    require(draft is not None, 'draft', '没有可处理的候选稿。')
    chapter = draft['chapter']
    budget = book.setdefault('rework', {}).setdefault(str(chapter), {})
    if option == REPAIR_AGAIN:
        budget['repairs'] = max(0, budget.get('repairs', 0) - 1)
        draft['stage'] = 'repair'
        # A granted round is a new lease on convergence: the counter that stalled the loop
        # starts over for the findings the author just voted to keep trying on.
        draft.pop('recurrence', None)
        book['status'] = 'running'
    elif option == ACCEPT_OPEN:
        findings = copy.deepcopy(draft.get('findings') or [])
        book.setdefault('accepted_findings', []).append(
            {'stage': 'chapter_repair', 'scope': 'chapter:%d' % chapter, 'findings': findings})
        book['carry_findings'] = list(book.get('carry_findings') or []) + findings
        # The formal chapter stays as it is; only the candidate goes away.
        book['draft'] = None
        book['status'] = 'running'
    else:
        book.update(status='paused', pause_reason='作者选择重开本章或改约。')
    return book


SCOPE_OPTIONS = (
    {'label': '接受本次修订，把这几个缺陷记为未解决项并完成修订',
     'impact': '本次修订照常收尾，这些缺陷不会消失：它们记成未解决项，完本篇审计与状态都能看到。'
               '独立范围审给的是 fix，这一步等于你以作者身份承担这处风险。'},
    {'label': '先撤销本次修订，再把缺陷并入下一次修订',
     'impact': '撤销后回到原稿（本次已通过的章节改动一并放弃），再按当前状态重新 advance 开一次范围更大的修订。'
               '代价照旧：范围内各章要重新写审。'},
)


def hold_for_scope_findings(book, findings):
    """Ask the author how to close a revision whose own scope review flagged an out-of-range chapter.

    The third shape of the same dead end: a revision run can be told by the closure review of its own
    branch that a chapter just outside its range needs work. Starting a second run is impossible while
    the first is open, and finishing the first is impossible with the finding outstanding, so the
    author's only exit used to be discarding everything.
    """
    book['author_block'] = {
        'id': 'scope-findings:open-revision',
        'question': '本次修订的范围复核记下了 %d 条缺陷（涉及第 %s 章），但它们落在本次修订范围之外，接下来怎么处理？'
                    % (len(findings), '、'.join(str(f.get('target_chapter')) for f in findings)),
        'options': copy.deepcopy(list(SCOPE_OPTIONS))}
    book.update(status='paused', pause_reason=book['author_block']['question'])
    return book['author_block']


def accept_scope_findings(book):
    """Close the run with the scope review's findings recorded as unresolved rather than repaired."""
    findings = copy.deepcopy(book.get('scope_findings') or [])
    book.setdefault('accepted_findings', []).append(
        {'stage': 'scope_review', 'scope': 'open-revision', 'findings': findings})
    book['carry_findings'] = list(book.get('carry_findings') or []) + findings
    book.pop('scope_findings', None)
    book['status'] = 'running'
    return book


def next_outline(book, volume, chapter=None):
    if not book['contract'].get('volume_outline'):
        return None
    scope = 'volume:' + volume['id']
    chapters = book['designs'][scope].get('chapters', [])
    first = chapters[-1]['chapter'] + 1 if chapters else volume['first']
    rolling = book['contract']['volume_outline']['scope'] == 'rolling'
    if rolling and first > (chapter or volume['first']):
        return None
    if first <= volume['end']:
        last = min(volume['end'], first + min(6, book['contract']['planning_window']) - 1)
        return Job('volume_outline', first, scope, first, last)
    return None


def profile_job(book, chapter):
    plan = book['plans'][str(chapter)]
    missing = [ident for ident in plan['participants'] if ident not in book['profiles']
               or editorial.enabled(book) and book['profiles'][ident].get('growth_basis') != craft.growth_basis(book['state'], ident)]
    return Job('profiles', chapter, payload={'entities': missing}) if missing else None


def choose(book, headers):
    opening = book.get('creation')
    if book['status'] in ('preparing', 'running') and opening and opening['phase'] == 'choosing':
        if opening['board']:
            return {'action': 'await_choice', **creation.view(opening)}
        gate = creation.current(opening)
        return Job('opening_options', 0, 'opening', payload={'gate': gate, 'round': opening['round'],
            'creative_lens': creation.LENSES[opening['round'] % len(creation.LENSES)],
            'lens_brief': creation.lens_brief(opening['round'])})
    if book['status'] != 'running':
        return {'action': book['status']}
    if book.get('alignment_hold'):
        hold = book['alignment_hold']
        if hold['mode'] == 'future' and headers and (not book['pilot'] or book['pilot']['prose'] != headers[0]['prose']):
            return {'action': 'await_author', 'chapter': 1, 'prose_hash': headers[0]['prose']}
        return Job('alignment_review' if book.get('alignment_proposal') else 'alignment_plan', hold['chapter'], 'alignment',
                   payload={'mode': hold['mode']})
    if book['proposal']:
        proposal = book['proposal']
        if proposal.get('kind') == 'volume_outline':
            stage = 'volume_outline' if proposal.get('needs_repair') else 'outline_review'
            return Job(stage, proposal['chapter'], proposal['scope'], proposal['first'], proposal['last'], {'repair': bool(proposal.get('needs_repair'))})
        if proposal.get('needs_repair'):
            stage = 'world_model' if proposal['scope'] == 'world' else 'book_plan' if proposal['scope'] == 'book' else 'volume_plan'
            return Job(stage, proposal['chapter'], scope=proposal['scope'], payload={'repair': True})
        # A contract drafted together with the world waits for that world to be verified first:
        # the alignment check reads the verified world, so reviewing it earlier would be empty.
        if proposal['scope'] == 'contract' and proposal.get('after') == 'world' and not book.get('world'):
            return {'action': 'settling_world'}
        stage = 'world_review' if proposal['scope'] == 'world' else 'contract_review' if proposal['scope'] == 'contract' else 'design_review'
        return Job(stage, proposal['chapter'], scope=proposal['scope'])
    if book.get('pending_contract'):
        return {'action': 'contract_ready'}
    if opening and opening['phase'] == 'world':
        # One dispatch drafts both artifacts: the contract is a reading of the selections plus the
        # world it just wrote, so splitting them into two cold workers only buys latency. The two
        # verifications stay separate and in order.
        return Job('world_model', 1, 'world', payload={'also': ('opening_contract',)})
    if opening and opening['phase'] == 'contract':
        return Job('opening_contract', 1, 'contract')
    contract = editorial.effective_contract(book)
    outline = contract.get('volume_outline') or {}
    opening_only = opening and opening['phase'] == 'ready' and book.get('opening_world_only') and not book.get('run_authorized')
    if opening_only and not outline:
        return {'action': 'world_ready', 'selection_hash': opening['selection_hash']}
    if 'book' not in book['designs']:
        return Job('book_plan', 1, scope='book')
    head = headers[-1]['n'] if headers else 0
    if outline and (opening_only or outline['scope'] == 'all' and head == 0):
        volumes = contract['volumes'] if outline['scope'] == 'all' else contract['volumes'][:1]
        for volume in volumes:
            scope = 'volume:' + volume['id']
            if scope not in book['designs']:
                return Job('volume_plan', volume['first'], scope, volume['first'], volume['end'])
            job = next_outline(book, volume)
            if job:
                return job
        if opening_only:
            return {'action': 'outline_ready', 'selection_hash': opening['selection_hash'], 'volumes': [v['id'] for v in volumes],
                    'planning_mode': outline['scope'],
                    'coverage': [{'volume': v['id'], 'first': v['first'],
                                  'last': book['designs']['volume:' + v['id']]['chapters'][-1]['chapter']} for v in volumes]}
    if head and (not book['pilot'] or book['pilot']['prose'] != headers[0]['prose']):
        return {'action': 'await_author', 'chapter': 1, 'prose_hash': headers[0]['prose']}
    if book['draft']:
        draft = book['draft']
        if draft['stage'] in ('write', 'repair', 'redesign'):
            job = profile_job(book, draft['chapter'])
            if job:
                return job
        return Job(draft['stage'], draft['chapter'])
    revision = book.get('revision_run')
    if revision and revision.get('plan_task'):
        chapter = revision['plan_task']
        volume = planning.volume_for(contract, chapter)
        last = min(volume['end'], book['target'], chapter + contract['planning_window'] - 1)
        if outline.get('scope') == 'rolling':
            last = min(last, book['designs']['volume:' + volume['id']]['chapters'][-1]['chapter'])
        return Job('plan', chapter, 'window', chapter, last, {'replan': '独立改案清理了待携带章节计划，重新规划后再核验正文。'})
    if revision and revision.get('reading_task'):
        return Job('revision_review', revision['reading_task'], 'revision')
    if head:
        volume = planning.volume_for(contract, head)
        # Every project reviews through the bounded tree. The flat scheme used to hand a whole
        # volume (or a whole book) to one synthesis worker, so a basic project's dispatch grew
        # with its length; the tree caps each task at one block plus child digests regardless.
        # Fast verification keeps its merged blocks where it had them: bigger leaves, same bound.
        fast = contract.get('verification') == 'fast'
        review_scopes = []
        if head % contract['review_interval'] == 0 and not fast:
            review_scopes.append(('interval', max(1, head - contract['review_interval'] + 1), head))
        if head == volume['end']:
            review_scopes.append(('volume:' + volume['id'], volume['first'], head))
        if editorial.enabled(book):
            review_scopes = [(s, f, l) for s, f, l in review_scopes if not s.startswith('volume:')]
            review_scopes.extend(('volume:' + v['id'], v['first'], v['end']) for v in contract['volumes'] if v['end'] <= head)
        revision = book['revision_run']
        if revision and head >= revision['last']:
            review_scopes.append(('revision', revision['first'], head))
        if book['finish'] and head == contract['volumes'][-1]['end']:
            review_scopes.append(('book', 1, head))
        for scope, first, last in review_scopes:
            key = review_key(scope, first, last, headers, editorial.context_hash(book) if editorial.enabled(book) else None)
            if key not in book['reviews']:
                # Frozen tasks dispatched under the flat scheme keep their protocol in apply();
                # only new dispatches change. Parts stored without part_id are not reusable
                # leaves, so an in-flight scope re-reviews its blocks once.
                chunk = FAST_REVIEW_BLOCK if fast and not contract.get('narrative_tracking') else contract['review_chunk']
                return scopes.next_review(book, headers, scope, first, last, key, chunk)
        if revision and head >= revision['last']:
            return {'action': 'revision_ready'}
    if head >= book['target']:
        return {'action': 'ready_to_complete' if book['finish'] else 'target_reached'}
    chapter = head + 1
    volume = planning.volume_for(contract, chapter)
    require(volume is not None, 'chapter_limit', '到达约定章节边界，需作者改约。')
    if contract.get('narrative_tracking'):
        narrative.budget_for(book, chapter)
    scope = 'volume:' + volume['id']
    if scope not in book['designs']:
        return Job('volume_plan', chapter, scope, volume['first'], volume['end']) if outline else Job('volume_plan', chapter, scope)
    job = next_outline(book, volume, chapter)
    if job:
        return job
    if str(chapter) not in book['plans']:
        last = min(volume['end'], book['target'], chapter + contract['planning_window'] - 1)
        if outline.get('scope') == 'rolling':
            last = min(last, book['designs'][scope]['chapters'][-1]['chapter'])
        return Job('plan', chapter, 'window', chapter, last)
    plan = book['plans'][str(chapter)]
    if contract.get('narrative_tracking') and narrative.unmet(book['state'], plan):
        last = min(volume['end'], book['target'], chapter + contract['planning_window'] - 1)
        if outline.get('scope') == 'rolling':
            last = min(last, book['designs'][scope]['chapters'][-1]['chapter'])
        return Job('plan', chapter, 'window', chapter, last, {'replan': '实际结果改变了近期计划的前提。', 'unmet': narrative.unmet(book['state'], plan)})
    job = profile_job(book, chapter)
    if job:
        return job
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


def route_repair(book, draft, findings, after_repair=False):
    budget = book['rework'].setdefault(str(draft['chapter']), {'repairs': 0, 'redesigns': 0})
    prior = {digest(f) for f in draft.get('findings', [])}
    combined = draft.get('findings', []) + copy.deepcopy(findings)
    draft['findings'] = list({digest(f): f for f in combined}.values())
    next_stage = repair_stage(budget)
    recurrence = draft.setdefault('recurrence', {})
    stalled = []
    if after_repair:
        # Only findings raised again after a repair round that was told to fix them count as
        # recurring; first-round findings and author feedback start at zero.
        for finding in findings:
            key = digest(finding)
            if key in prior:
                recurrence[key] = recurrence.get(key, 0) + 1
                if recurrence[key] >= STALL_AFTER_ROUNDS:
                    stalled.append(finding)
    if stalled and next_stage != 'exhausted':
        hold_for_stalled_repeat(book, draft, stalled)
    elif next_stage == 'exhausted':
        book['status'] = 'paused'
        book['pause_reason'] = '修复耗尽，保留候选正文与全部失败记录。'
        draft['stage'] = 'exhausted'
    else:
        draft['stage'] = next_stage
    book['draft'] = draft


def identified_items(data):
    """The addressable parts of a world, design or outline candidate, keyed the way findings name them."""
    items = {}
    for section, rows in (data or {}).items():
        if section == 'chapters' and isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict) and 'chapter' in row:
                    items['chapter:%s' % row['chapter']] = row
        elif isinstance(rows, list) and rows and all(isinstance(r, dict) and 'id' in r for r in rows):
            for row in rows:
                items['%s:%s' % (section, row['id'])] = row
        elif not isinstance(rows, (list, dict)):
            items[section] = rows
    return items


def require_narrow_repair(previous, candidate, findings):
    """A local repair may only change the parts its findings name.

    Measured: a real run's world candidate was repaired four times, and the early repairs re-drafted
    everything — findings already settled came back, so the next review paid for the same ground
    again. The engine can tell a narrow repair from a rewrite mechanically: when every finding is
    local and its target is named, everything nobody named has to come back unchanged. Additions are
    allowed (a review sees them); changing or dropping an unnamed part is not.
    """
    if not previous or not findings:
        return
    if any(finding.get('repair_scope') != 'local' for finding in findings):
        return                       # a chapter/volume-scope repair may legitimately move more
    before, after = identified_items(previous), identified_items(candidate)
    if not before:
        return
    named = named_items(previous, findings)
    if not named:
        return                       # nothing identifiable in the findings: do not guess a scope
    drifted = sorted(key for key, value in before.items()
                     if key not in named and after.get(key, object()) != value)
    require(not drifted, 'repair_scope', '局部返修只能改被点名的部分，其余与上一版逐字一致。',
            {'changed_but_not_named': drifted[:8], 'named_by_findings': sorted(named)[:8],
             'recover': '把没被点名的记录/节点恢复为上一版内容；确实需要扩大改动范围时，'
                        '请核验者在 findings 里写成 chapter 范围。'})


def named_items(previous, findings):
    """The candidate's items a finding actually names, found in its criterion, reason and evidence."""
    text_of = ' '.join(' '.join(str(finding.get(field) or '') for field in ('criterion', 'reason'))
                       + ' ' + ' '.join(str(row.get('quote') or '') for row in finding.get('evidence') or []
                                        if isinstance(row, dict))
                       for finding in findings)
    named = set()
    for key, value in identified_items(previous).items():
        ident = key.split(':', 1)[-1]
        if key in text_of or ident in text_of:
            named.add(key)
        elif isinstance(value, dict) and any(str(part) in text_of for part in value.values()
                                             if isinstance(part, str) and part):
            named.add(key)
    return named


def apply(book, task, data, actor, sources):
    require(isinstance(data, dict), 'result', 'data 须为对象。')
    data = copy.deepcopy(data)
    book = copy.deepcopy(book)
    stage, chapter = task['stage'], task['chapter']
    version = task.get('checks_version', 1)
    tracking = bool((book.get('contract') or {}).get('narrative_tracking'))
    # Every capability is read through the declared table: a value this build does not know fails
    # here instead of quietly selecting the older protocol's interpretation of the same fields.
    caps = capabilities_for(task)
    enhanced = bool(caps.get('editorial'))
    workbench = caps.get('understanding') == UNDERSTANDING_CAPABILITY
    require('understanding' not in data or workbench and stage in ('chapter_review', 'scope_review', 'scope_synthesis', 'revision_review'),
            'understanding', '作品理解仅由带冻结能力的独立阅读任务更新。')
    identity_version = 2 if caps.get('scene_identity') == SCENE_IDENTITY_CAPABILITY else 1
    reading_version = 1 if caps.get('reading_dependencies') == READING_DEPENDENCIES_CAPABILITY else 0
    row = None
    if stage == 'opening_options':
        planning.enforce(planning.active_policy(book.get('lexical_policy')), stage, data)
        book['creation'] = creation.offer(book['creation'], data,
                                         strict_bounds=caps.get('opening_bounds') == OPENING_BOUNDS_CAPABILITY)
    elif stage == 'world_model':
        opening = book['creation']
        planning.enforce(planning.active_policy(book.get('lexical_policy')), stage, data)
        # A combined dispatch returns one object holding both artifacts; each is validated by its
        # own contract, so the world half is split off before world.validate sees it.
        draft = {key: value for key, value in data.items() if key != 'contract'} \
            if 'opening_contract' in (task.get('payload') or {}).get('also', ()) else data
        model = world.validate(draft, creation.selected(opening), opening['selection_hash'],
                               sections=world.required_sections(tier_id(opening)))
        old = book['proposal'] or {}
        if (task.get('payload') or {}).get('repair'):
            require_narrow_repair(old.get('data') or {}, model, old.get('findings') or [])
        book['proposal'] = {'scope': 'world', 'chapter': 1, 'data': model, 'producer': actor, 'attempts': old.get('attempts', 0)}
        if 'opening_contract' in (task.get('payload') or {}).get('also', ()):  # combined dispatch
            planning.enforce(planning.active_policy(book.get('lexical_policy')), 'opening_contract', data.get('contract'))
            contract = planning.validate_contract(data.get('contract'))
            facts.seed(contract)
            creation.validate_contract(contract, opening, model)
            planning.check_contract_names(contract, planning.active_policy(book.get('lexical_policy')))
            book['contract_draft'] = {'scope': 'contract', 'chapter': 1, 'data': contract, 'producer': actor,
                                      'after': 'world',
                                      'source': '与已核验世界一并整理；完整选择版本 ' + opening['selection_hash']}
    elif stage == 'world_review':
        proposal = book['proposal']
        require(actor != proposal['producer'], 'review_independence', '世界模型须由独立核验者检查。')
        review = quality.checks(data, checks_for(version, 'world'), sources, expected_version=version, author_channel=stage in AUTHOR_CHANNEL_STAGES)
        if hold_for_author(book, review, proposal):
            proposal['needs_repair'] = True
        elif review['verdict'] == 'pass':
            book['world'] = proposal['data']
            book['world_review'] = {'receipt': review, 'producer': proposal['producer'], 'reviewer': actor}
            book['proposal'] = book.get('contract_draft') or None
            book.pop('contract_draft', None)
            book['creation']['phase'] = 'contract'
        else:
            proposal['attempts'] += 1
            proposal['findings'] = review['findings']
            if proposal['attempts'] > REPAIRS:
                hold_for_exhaustion(book, proposal, review, stage)
            else:
                proposal['needs_repair'] = True
    elif stage == 'opening_contract':
        contract = planning.validate_contract(data)
        facts.seed(contract)
        creation.validate_contract(contract, book['creation'], book['world'])
        planning.enforce(planning.active_policy(book.get('lexical_policy')), stage, contract)
        planning.check_contract_names(contract, planning.active_policy(book.get('lexical_policy')))
        book['proposal'] = {'scope': 'contract', 'chapter': 1, 'data': contract, 'producer': actor,
                            'source': '用户逐门选择；完整选择版本 ' + book['creation']['selection_hash']}
    elif stage in ('book_plan', 'volume_plan'):
        known = node_map(book)
        planning.enforce(planning.active_policy(book.get('lexical_policy')), stage, data)
        design = planning.validate_design(data, known, tracking, narrative.registry(book)[1],
                                          task.get('payload', {}).get('volume_outline'), book.get('world'))
        ledger.check(data.get('ledger'))
        if tracking and task['scope'] == 'book':
            require(any(t['kind'] == 'main' and t['required'] for t in design['threads']), 'story_threads', '全书设计至少要有一条必须完成的主线。')
            require(any(n['required'] for n in design['nodes']), 'story_node', '全书设计须有必要终局节点。')
        old = book['proposal'] or {}
        if task.get('payload', {}).get('repair'):
            require_narrow_repair(old.get('data') or {}, design, old.get('findings') or [])
        book['proposal'] = {'scope': task['scope'], 'chapter': chapter, 'data': design, 'producer': actor, 'attempts': old.get('attempts', 0)}
    elif stage == 'volume_outline':
        policy = task['payload']['volume_outline']
        planning.enforce(planning.active_policy(book.get('lexical_policy')), stage, data)
        planning.validate_chapter_outlines(data, policy, book.get('world'), node_map(book))
        ledger.check(data.get('ledger'))
        old = book['proposal'] or {}
        if task.get('payload', {}).get('repair'):
            require_narrow_repair(old.get('data') or {}, data, old.get('findings') or [])
        book['proposal'] = {'kind': 'volume_outline', 'scope': task['scope'], 'chapter': chapter,
                            'first': task['first'], 'last': task['last'], 'data': data, 'producer': actor,
                            'attempts': old.get('attempts', 0)}
    elif stage == 'outline_review':
        proposal = book['proposal']
        require(actor != proposal['producer'], 'review_independence', '逐章卷纲批次须由独立核验者检查。')
        review = quality.checks(data, checks_for(version, 'design'), sources, expected_version=version, author_channel=stage in AUTHOR_CHANNEL_STAGES)
        if hold_for_author(book, review, proposal):
            proposal['needs_repair'] = True
        elif review['verdict'] == 'pass':
            design = book['designs'][proposal['scope']]
            existing = design.setdefault('chapters', [])
            volume = planning.volume_for(editorial.effective_contract(book), chapter)
            require(proposal['first'] == (existing[-1]['chapter'] + 1 if existing else volume['first'])
                    and proposal['data']['world_hash'] == design['world_hash'], 'outline_coverage', '批次必须接续已核验前缀，不能覆盖已有卷纲或更换世界版本。')
            existing.extend(copy.deepcopy(proposal['data']['chapters']))
            design.setdefault('outline_reviews', []).append({'first': proposal['first'], 'last': proposal['last'],
                'producer': proposal['producer'], 'reviewer': actor, 'receipt': review, 'data_hash': digest(proposal['data'])})
            book['proposal'] = None
        else:
            proposal['attempts'] += 1
            proposal['findings'] = review['findings']
            if proposal['attempts'] > REPAIRS:
                hold_for_exhaustion(book, proposal, review, stage)
            else:
                proposal['needs_repair'] = True
    elif stage == 'design_review':
        proposal = book['proposal']
        require(proposal is not None and actor != proposal['producer'], 'review_independence', '设计核验须独立于提案者。')
        review = quality.checks(data, checks_for(version, 'design'), sources, expected_version=version, author_channel=stage in AUTHOR_CHANNEL_STAGES)
        if hold_for_author(book, review, proposal):
            # The answer changes the premise, so re-draft it rather than re-review the same candidate.
            proposal['needs_repair'] = True
        elif review['verdict'] == 'pass':
            book['designs'][proposal['scope']] = proposal['data']
            install_merged_volume_design(book, proposal['scope'], proposal['data'])
            book['proposal'] = None
        else:
            proposal['attempts'] += 1
            proposal['findings'] = review['findings']
            if proposal['attempts'] > REPAIRS:
                hold_for_exhaustion(book, proposal, review, stage)
            else:
                proposal['needs_repair'] = True
    elif stage == 'contract_review':
        proposal = book['proposal']
        require(actor != proposal['producer'], 'review_independence', '改约核验须独立于作者要求整理者。')
        review = quality.checks(data, checks_for(version, 'design'), sources, expected_version=version, author_channel=stage in AUTHOR_CHANNEL_STAGES)
        if hold_for_author(book, review, proposal):
            # A contract has no draft stage of its own: the answer arrives through recontract.
            pass
        elif review['verdict'] == 'pass':
            if task['payload'].get('author_question_hash'):
                resolution = data.get('blocked_resolution')
                require(isinstance(resolution, dict) and resolution.get('question_hash') == task['payload']['author_question_hash']
                        and resolution.get('result') == 'answered' and text(resolution.get('reason')), 'author_decision', '独立核验须说明改约如何回答准确的原作者问题。')
                book.setdefault('author_decision_history', []).append({'question': book['author_block'], 'resolution': resolution, 'reviewer': actor})
                book.pop('author_block', None)
            book['pending_contract'] = proposal
            book['pending_contract_reviewer'] = actor
            book['proposal'] = None
        else:
            book.update(status='paused', pause_reason='改约未通过；旧约定和稿件完整保留。')
            proposal['findings'] = review['findings']
    elif stage == 'alignment_plan':
        require(enhanced and text(data.get('reason')) and isinstance(data.get('designs', []), list), 'alignment', '改案需 reason/plan/designs。')
        planning.enforce(planning.active_policy(book.get('lexical_policy')), stage, data)
        candidate = copy.deepcopy(book)
        replacements = data.get('designs', [])
        allowed = {'book', 'volume:' + planning.volume_for(editorial.effective_contract(book), chapter)['id']}
        require(len(replacements) <= 2 and all(isinstance(r, dict) and r.get('scope') in allowed for r in replacements)
                and len({r['scope'] for r in replacements}) == len(replacements), 'alignment', '只改全书和当前卷，不重复范围。')
        for replacement in replacements:
            candidate['designs'].pop(replacement['scope'], None)
        for replacement in replacements:
            scope = replacement['scope']
            volume = planning.volume_for(editorial.effective_contract(book), chapter)
            outline = planning.outline_policy(editorial.effective_contract(book), volume, book.get('world')) if scope.startswith('volume:') else None
            new = planning.validate_design(replacement.get('data'), node_map(candidate), True, narrative.registry(candidate)[1], outline, book.get('world'))
            old = book['designs'].get(scope, {})
            new_nodes = {n['id']: n for n in new['nodes']}
            for prior in old.get('nodes', []):
                require(not prior['required'] or prior['id'] in new_nodes and new_nodes[prior['id']]['required'],
                        'alignment', '不能通过改案删除或降级必要节点；改变作者终局走 recontract。')
                progress = narrative.progress(book['state'], prior['id'])
                updated_node = new_nodes.get(prior['id'], {})
                same_meaning = {k: v for k, v in prior.items() if k != 'window'} == {k: v for k, v in updated_node.items() if k != 'window'}
                extended_window = bool(updated_node) and updated_node['window'][0] <= prior['window'][0] and updated_node['window'][1] >= prior['window'][1]
                require(progress is None or progress == 'resolved' and updated_node == prior
                        or progress in ('seeded', 'advanced') and same_meaning and extended_window,
                        'alignment', '已实现语义保留；部分实现可有据扩展窗口，不能改写作用或判据。')
            for line in old.get('threads', []):
                require(line in new.get('threads', []), 'alignment', '既有线路职责保留，新增线路用新 ID。')
            candidate['designs'][scope] = new
        plan = planning.validate_plans({'plans': [data.get('plan')]}, chapter, chapter, node_map(candidate), book['state'],
                                       editorial.effective_contract(book), book.get('world'), planning.active_policy(book.get('lexical_policy')), book['plans'], identity_version, reading_version)[0]
        book['alignment_proposal'] = {'producer': actor, 'reason': data['reason'], 'plan': plan,
                                      'designs': candidate['designs'], 'basis': editorial.context_hash(book)}
    elif stage == 'alignment_review':
        proposal = book['alignment_proposal']
        require(actor != proposal['producer'], 'review_independence', '改案须由新独立核验者审查。')
        review = quality.checks(data, checks_for(version, 'design'), sources, expected_version=version, author_channel=stage in AUTHOR_CHANNEL_STAGES)
        if hold_for_author(book, review, proposal):
            # Drop this candidate so the next dispatch plans a new one against the author's answer.
            book.pop('alignment_proposal', None)
        elif review['verdict'] == 'pass':
            require(proposal['basis'] == editorial.context_hash(book), 'alignment', '改案来源已变化。')
            book['designs'] = proposal['designs']
            book['plans'] = {n: p for n, p in book['plans'].items() if int(n) < chapter}
            book['plans'][str(chapter)] = proposal['plan']
            book.setdefault('alignment_history', []).append({'proposal': proposal, 'review': review, 'reviewer': actor,
                                                            'hold': book['alignment_hold']})
            if book['draft']:
                book['draft']['stage'] = 'chapter_review'
            book.pop('alignment_hold', None)
            book.pop('alignment_proposal', None)
        else:
            hold = book['alignment_hold']
            hold['attempts'] = hold.get('attempts', 0) + 1
            hold['findings'] = review['findings']
            book.pop('alignment_proposal', None)
            if hold['attempts'] >= 2:
                book.update(status='paused', pause_reason='同一改案两轮未通过，保留原稿、原计划与次数。')
    elif stage == 'plan':
        planning.enforce(planning.active_policy(book.get('lexical_policy')), stage, data)
        plans = planning.validate_plans(data, task['first'], task['last'], node_map(book), book['state'], editorial.effective_contract(book),
                                        book.get('world'), planning.active_policy(book.get('lexical_policy')), book['plans'], identity_version, reading_version)
        volume = planning.volume_for(editorial.effective_contract(book), chapter)
        prior_ledger = list((book['designs'].get('book') or {}).get('ledger') or [])
        if volume:
            prior_ledger += (book['designs'].get('volume:' + volume['id']) or {}).get('ledger') or []
        for plan in plans:
            ledger.check(plan.get('ledger'))
            ledger.cross_check(plan.get('ledger'), prior_ledger)
            book['plans'][str(plan['chapter'])] = plan
    elif stage == 'profiles':
        planning.enforce(planning.active_policy(book.get('lexical_policy')), stage, data)
        profiles = planning.validate_profiles(data, task['payload']['entities'], book['state'], book['profiles'], enhanced)
        for profile in profiles:
            book['profiles'][profile['entity']] = profile
            if enhanced:
                book.setdefault('profile_history', []).append({'chapter': chapter, 'branch': book['branch'],
                                                               'producer': actor, 'profile': copy.deepcopy(profile)})
    elif stage in ('write', 'repair', 'redesign'):
        require(all(text(data.get(k)) for k in ('title', 'summary', 'self_check')), 'draft', '执笔需要 title/正文方式/summary/具体 self_check。')
        require('events' not in data and 'candidate_events' not in data, 'writer_events', '事实由独立审稿者从正文重建。')
        base = book['draft']['prose'] if book['draft'] else (book.get('prior_candidate') or {}).get('prose')
        require(enhanced or 'prose' in data, 'patch', '旧冻结任务仍提交完整 prose。')
        prose, patch = craft.compose(data, base if stage != 'write' else None)
        data = {**data, 'prose': prose}
        planning.enforce(planning.active_policy(book.get('lexical_policy')), stage, data)
        spend(book, chapter, stage)
        old = book['draft'] or {}
        draft = {'chapter': chapter, 'title': data['title'], 'prose': data['prose'], 'producer': actor,
                 'summary': data['summary'], 'self_check': data['self_check'], 'stage': 'chapter_review',
                 'history': old.get('history', []) + ([{'stage': old['stage'], 'prose': old['prose'], 'findings': old.get('findings', [])}] if old else []),
                 'findings': old.get('findings', []) if old else [f for f in book.get('carry_findings', []) if f.get('target_chapter') == chapter],
                 # The convergence counter survives a repair, the way the findings it counts do.
                 'recurrence': old.get('recurrence', {}) if old else {}}
        if patch:
            draft['patch'] = patch
        count = han_count(data['prose'])
        band = narrative.budget_for(book, chapter) if tracking else {'minimum': book['contract']['chapter_min'], 'maximum': book['contract']['chapter_max']}
        if not band['minimum'] <= count <= band['maximum']:
            route_repair(book, draft, [{'criterion': 'substance', 'severity': 'quality', 'target_chapter': chapter,
                                      'repair_scope': 'chapter', 'reason': '汉字篇幅不在本章可完成全书的区间。', 'actual_han': count, 'allowed': [band['minimum'], band['maximum']]}])
        else:
            book['draft'] = draft
    elif stage == 'chapter_review':
        draft = book['draft']
        require(draft is not None and actor != draft['producer'], 'review_independence', '正文审稿须独立于当前执笔者。')
        obligations = task['obligations']
        fact_review, reader = quality.chapter_review(data, sources, obligations, version)
        if fact_review['verdict'] != 'pass' or reader['verdict'] != 'pass':
            findings = [f for review in (fact_review, reader) for f in review['findings'] if f['severity'] != 'note']
            require(all(f['target_chapter'] == chapter for f in findings), 'repair_scope', '本章审稿只能安排当前章返修，历史缺陷走修订。')
            route_repair(book, draft, findings, after_repair=True)
        else:
            plan = book['plans'][str(chapter)]
            raw_events = fact_review['events']
            alignment = editorial.alignment(data, plan, raw_events, lambda r: evidence(r, sources), book['state']) if enhanced else None
            require(not alignment or alignment['action'] != 'repair_prose', 'alignment', 'repair_prose 须与实际 fix 检查和 findings 一起提交。')
            if alignment:
                realized_rows = {r['node']: r for r in alignment['realizations']}
                raw_events = copy.deepcopy(raw_events)
                for event in raw_events:
                    if event['op'] == 'story_node':
                        event['criteria'] = realized_rows[event['node']].get('fulfilled_criteria', [])
            if tracking:
                require(not narrative.unmet(book['state'], plan), 'plan_preconditions', '正文基线已改变，先重新规划。')
                require(not any(e.get('op') == 'pace' for e in raw_events), 'pacing', '事实事件不自行填写 pace；由独立 reader.pacing 生成。')
                actual_plan = copy.deepcopy(plan)
                if alignment and alignment['action'] != 'follow_plan':
                    actual_plan['node_actions'] = [{'node': r['node'], 'after': r['after']} for r in alignment['realizations'] if r['after'] != 'not_realized']
                    actual_plan['disclosures'] = [{'topic': e['topic'], 'after': e['after']} for e in raw_events if e.get('op') == 'reader_knowledge']
                raw_events = narrative.prepare_events(raw_events, actual_plan)
                _, threads = narrative.registry(book)
                require(all(text(e.get('thread')) and e['thread'] in threads for e in raw_events if e.get('op') == 'story_thread'), 'story_thread', '线路事件引用未登记线路。')
                pace = reader.get('pacing')
                require(isinstance(pace, dict) and all(text(pace.get(k)) for k in narrative.PACE_FIELDS) and pace.get('role') in narrative.PACE_ROLES, 'pacing', '阅读审稿须独立记录实际 pacing 五项及 evidence。')
                raw_events.append({'op': 'pace', **{k: pace[k] for k in narrative.PACE_FIELDS}, 'evidence': pace.get('evidence')})
            raw_events = facts.prepare_hook_links(raw_events, caps.get('hook_links') == HOOK_LINKS_CAPABILITY)
            state, events = facts.settle(book['state'], raw_events, draft['prose'], chapter)
            if tracking:
                nodes, _ = narrative.registry(book)
                for e in events:
                    if e['op'] == 'story_thread' and e['after'] == 'resolved':
                        require(all(narrative.progress(state, ident) == 'resolved' for ident, n in nodes.items() if n['line'] == e['thread'] and n['required']), 'story_closure', '线路仍有必要节点，不能提前关闭。')
            require(state['clock'] - book['state']['clock'] == fact_review['elapsed_days'], 'elapsed_days', '正文时间声明与事件结算不一致。')
            plan = book['plans'][str(chapter)]
            require(all(book['state']['clock'] <= s['day'] <= state['clock'] for s in plan.get('schedule', [])),
                    'schedule', '当前章硬日程不在已核验的主线时间区间内。')
            require(all(p in state['entities'] for p in plan['participants']), 'entity_coverage', '计划参与人尚无已核验的正文身份。')
            if alignment and alignment['action'] == 'align_design':
                book['alignment_hold'] = {'mode': 'current', 'chapter': chapter, 'reason': alignment['reason'],
                                          'original_plan': plan, 'prose_hash': digest(draft['prose']),
                                          'review': {'facts': fact_review, 'reader': reader, 'alignment': alignment}}
                book['revision'] += 1
                return Outcome(book)
            if alignment and alignment['action'] == 'adapt_future':
                require(chapter < editorial.effective_contract(book)['volumes'][-1]['end'] and chapter < book['target'],
                        'alignment', '末章或授权边界不能把缺口推给未授权后文，使用 align_design。')
                book['alignment_hold'] = {'mode': 'future', 'chapter': chapter + 1, 'reason': alignment['reason'],
                                          'original_plan': plan, 'prose_hash': digest(draft['prose'])}
            for item in state['entities'].values():
                for name in [item['name']] + item.get('aliases', []):
                    planning.check_text(name, planning.active_policy(book.get('lexical_policy')), names=True)
            row = {'n': chapter, 'title': draft['title'], 'prose': draft['prose'], 'events': events,
                   'plan': plan, 'review': {'facts': fact_review, 'reader': reader, 'session': actor,
                   'writer': draft['producer'], 'first_read': task['first_read'], 'obligations': obligations},
                   'state_hash': digest(state), 'summary': fact_review['summary'], 'han': han_count(draft['prose'])}
            if alignment:
                row['review']['alignment'] = alignment
            if draft.get('patch'):
                row['review']['patch'] = draft['patch']
            book['state'], book['draft'] = state, None
            book['written_han'] += row['han']
            book['carry_findings'] = [f for f in book.get('carry_findings', []) if f.get('target_chapter') != chapter]
    elif stage == 'revision_review':
        require(set(data) <= {'reader', 'understanding'}, 'revision_review', '修订重读只交 reader 和可选 understanding，不交事实事件或正文。')
        revision = book.get('revision_run')
        require(revision and revision.get('reading_task') == chapter and revision['carry']
                and revision['carry'][0]['n'] == chapter, 'revision', '阅读核验必须绑定当前待携带章节。')
        receipt = quality.checks(data.get('reader'), checks_for(version, 'reader'), sources,
                                 [o for o in task['obligations'] if o['category'] == 'reader'], ('language',), version)
        original = revision['carry'][0]
        require(actor not in task['payload']['prior_sessions'], 'review_independence', '修订阅读核验须使用独立新会话。')
        revision.setdefault('reading_reviews', []).append({'chapter': chapter, 'prose_hash': original['prose'],
                                                          'receipt': receipt, 'reviewer': actor, 'first_read': task['first_read'],
                                                          'prior_sessions': task['payload']['prior_sessions'],
                                                          'obligations': [o for o in task['obligations'] if o['category'] == 'reader']})
        revision.pop('reading_task', None)
        if receipt['verdict'] == 'pass':
            revision['reading_approved'] = chapter
            if workbench:
                book['understanding'] = understanding.update(book.get('understanding'), data.get('understanding', []), sources, evidence, actor)
        else:
            findings = [f for f in receipt['findings'] if f['severity'] != 'note']
            require(all(f['target_chapter'] == chapter for f in findings), 'repair_scope', '阅读核验只安排当前待携带章修改。')
            if revision.get('impact'):
                action = next((a for a in revision['impact'].get('chapter_actions', []) if a['chapter'] == chapter), None)
                if action is not None:
                    action.update(action='local' if all(f['repair_scope'] == 'local' for f in findings) else 'rewrite',
                                  reason='独立重读发现实质问题，按当前发现修改并完整写审。')
            revision['carry'].pop(0)
            original_plan = task['payload']['original_plan']
            book['plans'][str(chapter)] = original_plan
            draft = {'chapter': chapter, 'title': original['title'], 'prose': sources[chapter],
                     'producer': 'historical', 'history': [], 'findings': []}
            route_repair(book, draft, findings)
    elif stage in ('scope_review', 'scope_synthesis'):
        review = quality.checks(data, checks_for(version, 'long'), sources, expected_version=version, author_channel=stage in AUTHOR_CHANNEL_STAGES)
        coverage = data.get('coverage')
        tree_task = task['payload'].get('review_tree')
        children = task['payload'].get('children', [])
        if tree_task and children:
            require(isinstance(coverage, list) and len(coverage) == len(children) and all(isinstance(r, dict) and text(r.get('part_id')) for r in coverage)
                    and {r.get('part_id') for r in coverage} == set(children), 'scope_coverage', '综合核验须恰好覆盖冻结子报告。')
            prior = scopes.reports(book)
            for item in coverage:
                report = prior[item['part_id']]
                ref = item.get('evidence', {})
                require(text(item.get('reason')) and report['first'] <= ref.get('chapter', -1) <= report['last'], 'scope_coverage', '每项覆盖须说明该子范围的作用并引用其原文。')
                evidence(ref, sources)
        else:
            require(isinstance(coverage, list) and len(coverage) == len(sources) and all(isinstance(r, dict) and type(r.get('chapter')) is int for r in coverage)
                    and {r['chapter'] for r in coverage} == set(sources), 'scope_coverage', '跨章核验须逐章给出覆盖证据。')
            for item in coverage:
                require(text(item.get('reason')) and item.get('evidence', {}).get('chapter') == item['chapter'], 'scope_coverage', '逐章覆盖需要本章理由与证据。')
                evidence(item['evidence'], sources)
        root = stage == 'scope_synthesis' and (not tree_task or task['payload']['root'])
        if enhanced and root:
            editorial.remedy_review(book, data, task['scope'], lambda r: evidence(r, sources))
            if task['payload'].get('closure'):
                editorial.closure(book, task, data, lambda r: evidence(r, sources))
        if hold_for_author(book, review):
            book['scope_findings'] = review['findings']
        elif review['verdict'] == 'pass':
            accepted = {'scope': task['scope'], 'first': task['first'], 'last': task['last'], 'receipt': review, 'coverage': copy.deepcopy(coverage)}
            if tree_task:
                accepted.update({k: task['payload'][k] for k in ('part_id', 'level', 'children')})
                accepted['handoff'] = scopes.validate_handoff(data, sources, evidence)
            if stage == 'scope_review' or tree_task and not task['payload']['root']:
                book['scope_parts'].setdefault(task['payload']['review_key'], []).append(accepted)
            else:
                book['reviews'][task['payload']['review_key']] = accepted
        else:
            if not book.get('alignment_hold') and not book.get('author_block') and not book.get('revision_directive') and not book.get('remedy_exhausted'):
                book.update(status='paused', pause_reason='跨章核验发现缺陷，按明确 target_chapter 开修订分支。')
            book['scope_findings'] = review['findings']
    else:
        require(False, 'stage', '未注册的任务阶段。')
    if workbench and (row is not None or stage in ('scope_review', 'scope_synthesis') and review['verdict'] == 'pass'):
        book['understanding'] = understanding.update(book.get('understanding'), data.get('understanding', []), sources, evidence, actor)
    book['revision'] += 1
    return Outcome(book, row)
