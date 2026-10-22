"""Pure lifecycle decisions, stage transitions and bounded draft repair."""
from __future__ import annotations

import copy
from .contracts import (DEFAULTS, OPENING_VERSION, PIPELINE_SHAPES, REDESIGNS,
                        REPAIRS, Job, Outcome,
                        capabilities_for, digest, han_count, require, text, tier_of)
from . import craft, creation, drift, drift_reconcile, drift_simulation, editorial, facts, ledger, lint, narrative, planning, style, understanding, world
from .evidence import evidence

# Where the engine stops moving on its own, and who decides what happens next. The value of this
# table is that no stop is a bare refusal with nowhere to go. v2 removed every stop that existed
# only because a reviewer stage could refuse: what is left is the author channel for a spent
# chapter budget, an out-of-scope revision, and a spent remedy budget.
STOP_POINTS = {
    'author_block': 'answer',                       # an open question is answered; nothing moves first.
    'repair-exhausted:chapter_repair': 'author_decision',
    'repair-stalled:chapter_repair': 'author_decision',
    'revision-blocked': 'plan_authorization',       # revise --proposal-hash with the author's own words
    'remedy-exhausted': 'recontract',               # the remedy budget is spent: change the premise
}
# What each channel means, for readers of the table and for the test that keeps it honest.
AUTHOR_CHANNELS = {
    'answer': '问题已在等作者回答，answer 记录选择后流程才继续。',
    'author_decision': '额度或未决导致停下：engine 提供再返修一轮或保留候选暂停，answer 落库；机械条件不可豁免。',
    'plan_authorization': '方案超出自动回改范围：作者用 revise --proposal-hash 绑定准确 plan_hash 授权。',
    'recontract': '改案额度已尽：改的是前提，走 recontract 并重新核验。',
}


def tier_id(opening):
    """The size class this opening was decided at, for requirements declared per tier."""
    scale = (creation.selected(opening) or {}).get('scale') or {}
    return scale.get('tier')


def merges_chapter_outline(book):
    """Whether this tier drafts a volume's outlines in the same dispatch as the volume outline.

    A short book's chapter outline is a few hundred characters of deltas; splitting it into a
    second cold session only buys latency, so the smallest tiers return both artifacts from one
    receipt and both contracts validate it. Declared per tier in PIPELINE_SHAPES.
    """
    tier = tier_of(editorial.effective_contract(book))
    return bool(tier is not None and PIPELINE_SHAPES.get(tier['id'], {}).get('merge_chapter_outline'))


def volume_policy(book):
    """The volume-outline policy of the live contract, defaults resolved by validation."""
    return planning.resolve_outline_policy(editorial.effective_contract(book), 'volume_outline')


def chapter_policy(book):
    """The chapter-outline policy of the live contract."""
    return planning.resolve_outline_policy(editorial.effective_contract(book), 'chapter_outline')


def new_book(contract, source=''):
    contract = planning.validate_contract(contract)
    book = {'contract': contract, 'contract_source': source, 'state': facts.seed(contract),
            'branch': 'main', 'revision': 0, 'status': 'running', 'target': 1, 'finish': False, 'written_han': 0,
            'lexical_policy': [{'version': 1, 'policy': planning.resolve_policy({}), 'source': '内置默认'}],
            'pilot': None, 'volumes_outline': {}, 'chapter_outlines': {}, 'plans': {}, 'design_drift': [],
            'understanding': understanding.empty(), 'draft': None, 'rework': {}, 'revision_run': None,
            'feedback': [], 'decisions': []}
    planning.check_contract_names(contract, planning.active_policy(book.get('lexical_policy')))
    return book


def preparing_book(source='', guided=False, opening_version=OPENING_VERSION):
    return {'contract': None, 'contract_source': source, 'state': facts.seed({}),
            'branch': 'main', 'revision': 0, 'status': 'preparing', 'target': 1, 'finish': False, 'written_han': 0,
            'lexical_policy': [{'version': 1, 'policy': planning.resolve_policy({}), 'source': '内置默认'}],
            'pilot': None, 'volumes_outline': {}, 'chapter_outlines': {}, 'plans': {}, 'design_drift': [],
            'understanding': understanding.empty(), 'draft': None, 'rework': {}, 'revision_run': None,
            'feedback': [], 'decisions': [],
            'creation': creation.begin(source, opening_version) if guided else None}


def draft_exhaustion_stage(budget):
    """The draft stage a spent repair budget leaves behind, or 'exhausted'."""
    if budget.get('redesigns', 0) >= REDESIGNS:
        return 'exhausted'
    return 'repair' if budget.get('repairs', 0) < REPAIRS else 'redesign'


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


def selections(book):
    """The opening's selected values, or an empty map for a book imported by contract."""
    state = book.get('creation')
    return creation.selected(state) if state else {}


def chapter_rows(book, volume_id):
    return (book.get('chapter_outlines') or {}).get(volume_id) or []


def outline_receipt(book, volumes):
    """The coverage line the author reads when the outlines are done and prose is not authorized."""
    return [{'volume': v['id'], 'first': v['first'],
             'last': max([r['chapter'] for r in chapter_rows(book, v['id'])] or [v['first']])} for v in volumes]


def next_volume_outline(book, contract, needed=None):
    """Which volume outline to draft next, honouring the policy's scope.

    `scope=all` drafts every missing volume in one dispatch, before the first word.
    `scope=rolling` drafts exactly the volume the book is about to enter — the one `needed` names —
    so "rolling" means one volume at a time on the way in, not every volume in order at the start.

    On the tiers that declare `merge_chapter_outline`, the dispatch also answers the chapter
    outlines of the volumes it just designed: one cold session for both artifacts, validated by
    both contracts, which is how a three-chapter book avoids a second design round-trip.
    """
    outlined = book.get('volumes_outline') or {}
    missing = [v for v in contract['volumes'] if v['id'] not in outlined]
    if not missing:
        return None
    merged = ('chapter_outline',) if merges_chapter_outline(book) else ()
    extra = {'also': merged} if merged else {}
    if volume_policy(book).get('scope') == 'rolling':
        volume = next((v for v in missing if needed is not None and v['id'] == needed['id']), None)
        if volume is None and needed is None:
            # No hint (a direct caller, or a book with no prose yet): the earliest missing volume.
            volume = missing[0]
        if volume is None:
            return None
        return Job('volume_outline', volume['first'], 'volume:' + volume['id'], volume['first'], volume['end'],
                   payload={'volume_ids': [volume['id']], **extra})
    return Job('volume_outline', 1, 'volumes', payload={'volume_ids': [v['id'] for v in missing], **extra})


def next_chapter_outline(book, contract, volume, ahead=False, next_chapter=1):
    """Which volume's chapter outlines to draft next.

    `scope=volume` drafts the volume about to be written; `scope=all` keeps drafting ahead until
    every volume's chain is on paper, which is what an author who wants the whole resource chain
    resolved before the first word should choose.

    A volume drafted *ahead* of the writing front states `anchor: design`: its first chapter's entry
    conditions continue from the previous volume's designed chain rather than from the prose state,
    because that prose does not exist yet. The volume about to be written anchors on reality.
    """
    def job_for(target):
        anchor = 'design' if target['first'] > next_chapter else 'state'
        return Job('chapter_outline', target['first'], 'volume:' + target['id'],
                   target['first'], target['end'],
                   payload={'volume': target['id'], 'anchor': anchor})

    if volume['id'] not in (book.get('chapter_outlines') or {}):
        return job_for(volume)
    if ahead and chapter_policy(book).get('scope') == 'all':
        for candidate in contract['volumes']:
            if candidate['id'] not in (book.get('chapter_outlines') or {}):
                return job_for(candidate)
    return None


def design_anchor(book, contract, volume, payload):
    """The state a chapter-outline chain continues from.

    A volume drafted ahead of the writing front (`anchor: design`) has no prose before it: its chain
    continues from the *designed* end of every earlier volume whose outlines are already installed,
    because that is the only state that exists. The volume about to be written anchors on the real
    projection instead — simulating designed outlines again there would double-count prose that has
    already settled.
    """
    if (payload or {}).get('anchor') != 'design':
        return book['state']
    state = book['state']
    for prior in contract['volumes']:
        if prior['end'] >= volume['first']:
            break
        rows = (book.get('chapter_outlines') or {}).get(prior['id'])
        if rows:
            state, _ = drift_simulation.simulate(rows, state, book.get('world'), prior,
                                      (book.get('volumes_outline') or {}).get(prior['id']))
    return state


def replan_volume_outline(book, contract, chapter, drift_rows, reason, through=None):
    """Build the bounded outline job for author-directed revision or an unplanned missing range.

    Failed prose is never a caller: it remains a repair of the current fixed chapter contract.
    """
    volume = planning.volume_for(contract, chapter)
    require(volume is not None, 'chapter_limit', '本章超出约定卷界，需作者改约。')
    # The re-plan answers the chapters from `chapter` to the end of its volume, so the dispatch's
    # own range starts there: handing the volume's first chapter to a batch that must re-derive the
    # chain from the state the book is actually in is how a re-plan used to be unanswerable.
    last = volume['end'] if through is None else min(through, volume['end'])
    return Job('chapter_outline', chapter, 'volume:' + volume['id'], chapter, last,
               payload={'volume': volume['id'], 'from_chapter': chapter, 'repair': True, 'allow_retained_suffix': True,
                        'drift': copy.deepcopy(drift_rows or []), 'reason': reason})


def choose(book, headers):
    opening = book.get('creation')
    if book['status'] in ('preparing', 'running') and opening and opening['phase'] == 'choosing':
        if opening['board']:
            return {'action': 'await_choice', **creation.view(opening)}
        gate = creation.current(opening)
        method = creation.lens_index(gate['id'], opening['round'], creation.opening_version(opening))
        return Job('opening_options', 0, 'opening', payload={'gate': gate, 'round': opening['round'],
            'creative_lens': creation.LENSES[method],
            'lens_brief': creation.lens_brief(method)})
    if book['status'] != 'running':
        return {'action': book['status']}
    if book.get('pending_contract'):
        return {'action': 'contract_ready'}
    if opening and opening['phase'] == 'world':
        # Step two: one dispatch drafts the world and the contract that reads it. Both are
        # validated mechanically here; nothing waits for a reviewer, so the cost of the opening
        # no longer depends on how many rounds a verifier needs.
        return Job('world_model', 1, 'world', payload={'also': ('opening_contract',)})
    if opening and opening['phase'] == 'contract':
        return Job('opening_contract', 1, 'contract')
    contract = editorial.effective_contract(book)
    planning.outline_policies(contract)
    volumes = contract['volumes']
    opening_only = bool(opening and opening['phase'] == 'ready' and book.get('opening_world_only')
                        and not book.get('run_authorized'))
    head = headers[-1]['n'] if headers else 0
    writing_volume = planning.volume_for(contract, head + 1 if head + 1 <= volumes[-1]['end'] else volumes[-1]['end'])
    # Step three: the volume outlines. Drafted for every volume at once, or one volume at a time,
    # by the contract's own policy — and in `rolling` mode the volume drafted is the one the book
    # is about to enter, not simply the next one in order.
    job = next_volume_outline(book, contract, writing_volume)
    if job:
        return job
    # Step four: the chapter outlines that carry the drift declarations.
    volume = writing_volume
    require(volume is not None, 'chapter_limit', '到达约定章节边界，需作者改约。')
    job = next_chapter_outline(book, contract, volume, ahead=not head, next_chapter=head + 1)
    if job and not (opening_only and chapter_policy(book).get('scope') != 'all'):
        return job
    if opening_only:
        # No prose authorization: the outlines are the deliverable, and the author decides next.
        return {'action': 'outline_ready', 'selection_hash': (opening or {}).get('selection_hash'),
                'volumes': [v['id'] for v in volumes],
                'planning_mode': volume_policy(book).get('scope'),
                'coverage': outline_receipt(book, volumes)}
    if head and (not book['pilot'] or book['pilot']['prose'] != headers[0]['prose']):
        return {'action': 'await_author', 'chapter': 1, 'prose_hash': headers[0]['prose']}
    revision = book.get('revision_run')
    chapter = head + 1
    reading_revision = revision and (revision.get('impact') or {}).get('reading_changes')
    if reading_revision and chapter <= revision['last'] and revision.get('outlined_through', 0) < chapter:
        return replan_volume_outline(book, contract, chapter, [],
                                     '阅读关联发生变化，先重排受影响章纲，再按新章纲修改正文。',
                                     through=revision['last'])
    if revision and revision.get('outline_task'):
        chapter = revision['outline_task']
        return replan_volume_outline(book, contract, chapter, revision.get('drift'),
                                     '修订改变了前文，本卷剩余章纲按真实状态重排。')
    if book['draft']:
        return Job(book['draft']['stage'], book['draft']['chapter'])
    if head >= book['target']:
        if revision and not revision.get('carry'):
            return {'action': 'revision_ready'}
        return {'action': 'ready_to_complete' if book['finish'] else 'target_reached'}
    chapter = head + 1
    volume = planning.volume_for(contract, chapter)
    require(volume is not None, 'chapter_limit', '到达约定章节边界，需作者改约。')
    row = (book.get('plans') or {}).get(str(chapter))
    if row is None:
        return replan_volume_outline(book, contract, chapter, [], '本卷章纲缺少这一章，按真实状态补齐。')
    # A fixed outline is not silently rewritten to fit a different committed history.
    mismatches = drift_reconcile.state_mismatch(book['state'], row)
    require(not mismatches, 'outline_state', '真实前态与固定章纲不符，保留现场并由作者决定修订范围，不能自动改纲。',
            {'chapter': chapter, 'findings': mismatches})
    # Historical departures require author-directed revision; they cannot justify automatic replanning.
    pending = [d for d in (book.get('design_drift') or [])
               if not d.get('absorbed_by') and d.get('chapter', 0) < chapter]
    require(not pending, 'outline_alignment', '历史正文仍有章纲偏差，须按作者授权修订，不能自动重排后续章纲。',
            {'chapter': chapter, 'findings': pending})
    budget = book['rework'].get(str(chapter), {})
    if budget.get('initial_used'):
        stage = draft_exhaustion_stage(budget)
        if stage == 'exhausted':
            return {'action': 'repair_exhausted', 'chapter': chapter}
        return Job(stage, chapter)
    return Job('write', chapter)


def route_repair(book, draft, findings, after_repair=False):
    budget = book['rework'].setdefault(str(draft['chapter']), {'repairs': 0, 'redesigns': 0})
    prior = {digest(f) for f in draft.get('findings', [])}
    combined = draft.get('findings', []) + copy.deepcopy(findings)
    draft['findings'] = list({digest(f): f for f in combined}.values())
    next_stage = draft_exhaustion_stage(budget)
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
    """The addressable parts of a world or outline candidate, keyed the way findings name them."""
    items = {}
    for section, rows in (data or {}).items():
        if section in ('chapters', 'volumes') and isinstance(rows, list):
            key = 'chapter' if section == 'chapters' else 'volume'
            for row in rows:
                if isinstance(row, dict) and key in row:
                    items['%s:%s' % (key, row[key])] = row
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
    again. An outline repair is re-derived from the state that moved, so the guard stays where it
    still protects something: a local finding must not rewrite unnamed records.
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
                        '请把本次重排声明为 chapter 范围。'})


def repair_summary(previous, candidate, findings):
    """What a narrow repair actually touched, as the summary the next dispatch reads."""
    before, after = identified_items(previous or {}), identified_items(candidate)
    named = named_items(previous or {}, findings or [])
    changed = sorted(key for key, value in before.items() if after.get(key, object()) != value)
    removed = sorted(key for key in before if key not in after)
    return {'named_by_findings': sorted(named),
            'changed': changed,
            'added': sorted(key for key in after if key not in before),
            'removed': removed,
            'unchanged': sorted(set(before) - set(changed) - set(removed)),
            'changed_but_not_named': sorted(key for key in changed if key not in named),
            'findings': findings or []}


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


EXHAUSTION_OPTIONS = (
    {'label': '再返修一轮（只按这几条改）',
     'impact': '给本章加一轮返修额度：只改被点名的记录，改完引擎重新核账。'
               '额度不是无限的，这一轮用尽后还会来问你。'},
    {'label': '保留候选并暂停，另行调整约定',
     'impact': '保留当前正文和失败记录，不豁免机械入库条件，也不增加额度。'
               '作者可以另行改约；已有正文时改约会在新分支自第 1 章重写全书。'},
)

# Keep the retired acceptance label recognizable for persisted author decisions; hard findings
# cannot be waived into the official chapter by an answer.
REPAIR_AGAIN = '再返修一轮（只按这几条改）'
ACCEPT_OPEN = '接受当前候选，把这几条记为未解决项继续'

# A finding that survives this many repair rounds is a stall, not slow convergence: the next
# identical round only spends budget. A real chapter went four rounds on the same two findings
# before anyone could see the loop was not converging at all.
STALL_AFTER_ROUNDS = DEFAULTS['stall_after_rounds']


def draft_decision_subject(book, draft):
    """Bind a budget answer to one candidate and one consumed allowance state."""
    return {'branch': book['branch'], 'chapter': draft['chapter'], 'revision': book['revision'],
            'contract_hash': digest(book['contract']), 'prose_hash': digest(draft.get('prose')),
            'findings_hash': digest(draft.get('findings') or []),
            'budget': copy.deepcopy(book['rework'].get(str(draft['chapter']), {}))}


def hold_for_draft_exhaustion(book):
    """Ask the author how to proceed when one chapter has spent its repair rounds."""
    draft = book['draft']
    findings = draft.get('findings') or []
    subject = draft_decision_subject(book, draft)
    book['author_block'] = {
        'id': 'repair-exhausted:chapter_repair:' + digest(subject), 'subject': subject,
        'question': '第 %d 章的返修额度已用尽，引擎核账仍给出 %d 条意见，接下来怎么处理？'
                    % (draft['chapter'], len(findings)),
        'options': copy.deepcopy(list(EXHAUSTION_OPTIONS))}
    book.update(status='paused', pause_reason=book['author_block']['question'])
    return book['author_block']


def hold_for_stalled_repeat(book, draft, stalled):
    """Hand a non-converging repair loop to the author while budget still remains.

    The spent-budget stop catches loops that ran out of rounds; this one catches loops that are
    burning them without moving: the same findings, verbatim, after a repair that claimed to fix
    them. The options match the spent-budget stop, and one more granted round resets the counter
    for the findings named here, so an author who sees actual movement can keep going.
    """
    draft['stage'] = 'stalled'
    subject = draft_decision_subject(book, draft)
    book['author_block'] = {
        'id': 'repair-stalled:chapter_repair:' + digest(subject), 'subject': subject,
        'question': '第 %d 章的同 %d 条意见已连续 %d 轮返修未解决，再按原样返修不会收敛，接下来怎么处理？'
                    % (draft['chapter'], len(stalled), STALL_AFTER_ROUNDS),
        'options': copy.deepcopy(list(EXHAUSTION_OPTIONS))}
    book.update(status='paused', pause_reason=book['author_block']['question'])
    return book['author_block']


def resolve_draft_exhaustion(book, option, subject=None):
    """Apply the author's answer for a spent chapter repair budget."""
    draft = book['draft']
    chapter = subject.get('chapter') if subject else (draft or {}).get('chapter')
    require(type(chapter) is int and str(chapter) in book['rework'], 'draft', '没有对应候选与额度记录。')
    budget = book['rework'][str(chapter)]
    if option == REPAIR_AGAIN:
        budget['repairs'] = max(0, budget.get('repairs', 0) - 1)
        if draft and draft['chapter'] == chapter:
            draft['stage'] = 'repair'
        # A granted round is a new lease on convergence: the counter that stalled the loop
        # starts over for the findings the author just voted to keep trying on.
        if draft and draft['chapter'] == chapter:
            draft.pop('recurrence', None)
        book['status'] = 'running'
        book.pop('pause_reason', None)
    elif option == ACCEPT_OPEN:
        require(False, 'author_decision', '当前候选仍未通过机械入库条件，不能直接接受；请再返修一轮或保留候选并暂停。',
                {'options': copy.deepcopy(list(EXHAUSTION_OPTIONS))})
    else:
        book.update(status='paused', pause_reason='作者选择保留候选并暂停，另行调整约定。')
    return book


def apply(book, task, data, actor, sources, priors=None):
    require(isinstance(data, dict), 'result', 'data 须为对象。')
    data = copy.deepcopy(data)
    book = copy.deepcopy(book)
    stage, chapter = task['stage'], task['chapter']
    tracking = bool((book.get('contract') or {}).get('narrative_tracking'))
    # Every capability is read through the declared table: a value this build does not know fails
    # here instead of quietly selecting the older protocol's interpretation of the same fields.
    caps = capabilities_for(task)
    enhanced = bool(caps.get('editorial'))
    # The opening gates run before any contract exists; every later stage has one.
    contract = editorial.effective_contract(book) if book.get('contract') else None
    row = None
    style_report = None
    findings = None
    if stage == 'opening_options':
        planning.enforce(planning.active_policy(book.get('lexical_policy')), stage, data)
        book['creation'] = creation.offer(book['creation'], data)
    elif stage == 'world_model':
        opening = book['creation']
        planning.enforce(planning.active_policy(book.get('lexical_policy')), stage, data)
        # A combined dispatch returns one object holding both artifacts; each is validated by its
        # own contract, so the world half is split off before world.validate sees it.
        also = (task.get('payload') or {}).get('also') or ()
        draft = {key: value for key, value in data.items() if key != 'contract'} if 'opening_contract' in also else data
        choices = creation.selected(opening)
        model = world.validate(draft, choices, opening['selection_hash'],
                               sections=world.required_sections(tier_id(opening), choices))
        book['world'] = model
        if 'opening_contract' in also:
            planning.enforce(planning.active_policy(book.get('lexical_policy')), 'opening_contract', data.get('contract'))
            contract = planning.validate_contract(data.get('contract'))
            facts.seed(contract)
            creation.validate_contract(contract, opening, model)
            planning.check_contract_names(contract, planning.active_policy(book.get('lexical_policy')))
            book['pending_contract'] = {'scope': 'contract', 'chapter': 1, 'data': contract, 'producer': actor,
                                        'source': '与已核验世界一并整理；完整选择版本 ' + opening['selection_hash']}
        elif book.get('creation'):
            book['creation']['phase'] = 'contract'
    elif stage == 'opening_contract':
        opening = book['creation']
        contract = planning.validate_contract(data)
        facts.seed(contract)
        creation.validate_contract(contract, opening, book['world'])
        planning.enforce(planning.active_policy(book.get('lexical_policy')), stage, contract)
        planning.check_contract_names(contract, planning.active_policy(book.get('lexical_policy')))
        book['pending_contract'] = {'scope': 'contract', 'chapter': 1, 'data': contract, 'producer': actor,
                                    'source': '用户逐门选择；完整选择版本 ' + opening['selection_hash']}
    elif stage == 'volume_outline':
        # Step three: one outline per volume, sized by the contract. Validated against the world and the
        # contract, then installed — there is no candidate waiting for a verdict.
        planning.enforce(planning.active_policy(book.get('lexical_policy')), stage, data)
        contract = editorial.effective_contract(book)
        wanted = list((task.get('payload') or {}).get('volume_ids') or [])
        require(wanted, 'volume_outline', '卷纲派工须声明本次要交的卷。')
        # `planning` owns the wrapper that adds the scene protocol on top of the same mechanical
        # checks (speaker/intent shape, scene identity, reading dependencies); calling `drift`
        # directly here would leave a chapter's scenes unbound and quietly retire the workbench.
        outlines = planning.validate_volume_outline(data, contract, book.get('world'), selections(book),
                                                    book.get('volumes_outline') or {}, wanted)
        old = book.get('volumes_outline') or {}
        if (task.get('payload') or {}).get('repair'):
            require_narrow_repair(old, outlines, (task.get('payload') or {}).get('drift') or [])
        for volume_id, outline in outlines.items():
            old[volume_id] = outline
        book['volumes_outline'] = old
        ledger.check(data.get('ledger'))
        if 'chapter_outline' in ((task.get('payload') or {}).get('also') or ()):
            # The merged half. Volumes are validated in book order and the chain is carried forward:
            # volume two's opening chapter may pay off a promise volume one declared in this very
            # receipt, so validating each volume against the book's frozen state would reject a
            # receipt that is internally consistent — and a two-volume small tier is the default
            # shape, not an edge case.
            half = data.get('chapters')
            require(isinstance(half, dict), 'volume_outline',
                    '合并派工须在 chapters 里按卷交出逐章章纲。',
                    {'expect': {'chapters': {'<volume_id>': ['章纲行']}}})
            simulated = book['state']
            for volume in contract['volumes']:
                if volume['id'] not in outlines:
                    continue
                volume_id = volume['id']
                require(isinstance(half.get(volume_id), list), 'volume_outline',
                        '合并派工缺少这一卷的章纲：' + volume_id)
                validated = planning.validate_chapter_outline(
                    {'volume': volume_id, 'chapters': half[volume_id]}, chapter_policy(book),
                    volume, outlines[volume_id], book.get('world'), simulated, book.get('plans'))
                book.setdefault('chapter_outlines', {})[volume_id] = validated
                for item in drift.plan_rows(validated):
                    book.setdefault('plans', {})[str(item['chapter'])] = item
                simulated, chain_findings = drift_simulation.simulate(validated, simulated, book.get('world'),
                                                           volume, outlines[volume_id])
                require(not chain_findings, 'design_drift', '合并回执的卷内状态链核账未通过。',
                        {'volume': volume_id, 'findings': chain_findings[:12]})
    elif stage == 'chapter_outline':
        # Step four: the volume's chapter outlines, each declaring what it changes and what state
        # it enters and leaves. The engine simulates the whole chain here, before a word is written.
        payload = task.get('payload') or {}
        volume_id = payload.get('volume')
        volume = next((v for v in editorial.effective_contract(book)['volumes'] if v['id'] == volume_id), None)
        require(volume is not None, 'chapter_outline', '章纲派工须声明本卷。')
        outline = (book.get('volumes_outline') or {}).get(volume_id)
        require(outline is not None, 'chapter_outline', '本卷尚无已登记的卷纲。')
        planning.enforce(planning.active_policy(book.get('lexical_policy')), stage, data)
        first = payload.get('from_chapter') or volume['first']
        require('from_chapter' not in data or type(data['from_chapter']) is int
                and data['from_chapter'] == first, 'chapter_outline',
                '章纲核算起点由冻结任务决定，不能通过回执跳过待修章节。')
        data['from_chapter'] = first
        last = (payload.get('chapter_outline') or {}).get('last', volume['end'])
        if payload.get('repair') and last < volume['end']:
            data.setdefault('through_chapter', last)
        retained = {}
        if 'through_chapter' in data:
            through = data['through_chapter']
            require(payload.get('repair') and payload.get('allow_retained_suffix')
                    and type(through) is int and first <= through <= last,
                    'chapter_outline', 'through_chapter 仅用于允许保留后缀的重排任务，且须在本批范围内。')
            submitted = data.get('chapters')
            require(isinstance(submitted, list) and all(isinstance(r, dict) for r in submitted)
                    and [r.get('chapter') for r in submitted] == list(range(first, through + 1)),
                    'chapter_outline', '局部重排须连续覆盖 from_chapter 到 through_chapter。')
            retained = {r['chapter']: r for r in chapter_rows(book, volume_id) if r['chapter'] > through}
            require(set(retained) == set(range(through + 1, volume['end'] + 1)),
                    'chapter_outline', '保留的后缀章纲缺失，须扩大重排范围。')
            data['chapters'] = submitted + [copy.deepcopy(retained[n]) for n in sorted(retained)]
        chapters = planning.validate_chapter_outline(data, chapter_policy(book), volume, outline,
                                                    book.get('world'),
                                                    design_anchor(book, contract, volume, payload), book.get('plans'))
        for item in chapters:
            if item['chapter'] in retained:
                require(digest(item) == digest(retained[item['chapter']]), 'chapter_outline',
                        '保留后缀的场景或阅读绑定发生变化，须扩大 through_chapter 后重新提交。')
        known = {r['chapter']: r for r in chapter_rows(book, volume_id) if r['chapter'] < first}
        replaced = {r['chapter']: r for r in chapters if r['chapter'] >= first}
        require(set(known) | set(replaced) == set(range(volume['first'], volume['end'] + 1)),
                'chapter_outline', '章纲须恰好覆盖本卷全部章号。',
                {'volume': volume_id, 'first': first})
        merged = [known.get(n) or replaced[n] for n in range(volume['first'], volume['end'] + 1)]
        book.setdefault('chapter_outlines', {})[volume_id] = merged
        for item in drift.plan_rows(merged):
            book.setdefault('plans', {})[str(item['chapter'])] = item
        if payload.get('repair'):
            # The re-plan absorbed every deviation booked before its first chapter. They stay on the
            # record — the audit reports them — but they no longer force another re-plan.
            for item in book.get('design_drift') or []:
                if item.get('chapter', 0) < first:
                    item['absorbed_by'] = {'volume': volume_id, 'from_chapter': first}
        revision = book.get('revision_run')
        if revision:
            if revision.get('outline_task') == first:
                revision.pop('outline_task')
            if (revision.get('impact') or {}).get('reading_changes'):
                revision['outlined_through'] = data.get('through_chapter', last)
        ledger.check(data.get('ledger'))
    elif stage in ('write', 'repair', 'redesign'):
        # Step five. The writer drafts from the chapter outline and submits its own item-by-item
        # comparison; the engine reconciles that comparison against the chapter outline and the
        # projected state. What used to be a reviewer's receipt is now this reconciliation, and
        # it costs no dispatch.
        require(all(text(data.get(k)) for k in ('title', 'summary', 'self_check')), 'draft',
                '执笔需要 title/summary/self_check。')
        require('events' not in data and 'candidate_events' not in data, 'writer_events',
                '正文事件由章纲与 drift_check 核算产生，不由执笔另写一份。')
        revision = book.get('revision_run')
        if revision and (revision.get('impact') or {}).get('reading_changes') and chapter <= revision['last']:
            require(revision.get('outlined_through', 0) >= chapter, 'revision_outline',
                    '阅读修订必须先提交当前章纲重排，再修改正文。',
                    {'recover': '未经过章纲重排的旧修订任务不能继续；撤销候选后按当前流程重新发起修订。'})
        base = book['draft']['prose'] if book['draft'] else (book.get('prior_candidate') or {}).get('prose')
        prose, patch = craft.compose(data, base if stage != 'write' else None)
        data = {**data, 'prose': prose}
        sources = {**sources, chapter: prose}
        planning.enforce(planning.active_policy(book.get('lexical_policy')), stage, data)
        spend(book, chapter, stage)
        old = book['draft'] or {}
        draft = {'chapter': chapter, 'title': data['title'], 'prose': data['prose'], 'producer': actor,
                 'summary': data['summary'], 'self_check': data['self_check'],
                 'drift_check': copy.deepcopy(data.get('drift_check')), 'stage': 'write',
                 'history': old.get('history', []) + ([{'stage': old['stage'], 'prose': old['prose'],
                                                        'findings': old.get('findings', [])}] if old else []),
                 'findings': old.get('findings', []) if old else [],
                 'recurrence': old.get('recurrence', {}) if old else {}}
        if patch:
            draft['patch'] = patch
        plan = (book.get('plans') or {}).get(str(chapter))
        require(plan is not None, 'chapter_outline', '本章尚无已登记的章纲，不能执笔。')
        presence = drift_reconcile.presence_notes(plan, book.get('world'), data['prose'])
        if presence:
            draft['presence'] = presence
        settlement = drift_reconcile.reconcile(data.get('drift_check'), plan, book['state'], book.get('world'))
        findings = list(settlement['findings'])
        count = han_count(prose)
        band = narrative.budget_for(book, chapter) if tracking else {'minimum': book['contract']['chapter_min'],
                                                                    'maximum': book['contract']['chapter_max']}
        if not band['minimum'] <= count <= band['maximum']:
            findings.append({'criterion': 'substance', 'severity': 'quality', 'target_chapter': chapter,
                             'repair_scope': 'chapter', 'reason': '汉字篇幅不在本章可完成全书的区间。',
                             'actual_han': count, 'allowed': [band['minimum'], band['maximum']]})
        # Mechanical prose defects are judged here, at submission, against the nearest committed
        # chapters: the same code preflight runs, so the producer sees the finding for free.
        findings.extend(lint.draft_findings(prose, priors or [], chapter))
        # And the style proxies: the checkable half of "did this chapter keep the voice the author
        # anchored". Consistency, not quality — a chapter can match every number and still be dull.
        # The volume's own `style.window` overrides the contract's tolerances for this stretch.
        write_volume = planning.volume_for(editorial.effective_contract(book), chapter)
        volume_style = ((book.get('volumes_outline') or {}).get(write_volume['id']) or {}).get('style') \
            if write_volume else None
        style_report = style.examine(prose, plan.get('style'), style.baseline(book),
                                     style.merged_window(book.get('contract'), volume_style), chapter,
                                     contract=book.get('contract'))
        findings.extend(style_report['findings'])
        if findings:
            route_repair(book, draft, findings, after_repair=stage != 'write')
        else:
            raw_events = facts.prepare_hook_links(settlement['events'])
            state, events = facts.settle(book['state'], raw_events, draft['prose'], chapter)
            if enhanced:
                require(not settlement['deviations'] or all(text(d.get('reason')) for d in settlement['deviations']),
                        'drift_reason', '与章纲不符的变化必须写明理由。')
            if tracking:
                _, threads = narrative.registry(book)
                require(all(text(e.get('thread')) and e['thread'] in threads
                            for e in events if e.get('op') == 'story_thread'), 'story_thread', '线路事件引用未登记线路。')
                nodes, _ = narrative.registry(book)
                for event in events:
                    if event['op'] == 'story_thread' and event['after'] == 'resolved':
                        require(all(narrative.progress(state, ident) == 'resolved'
                                    for ident, node in nodes.items()
                                    if node['line'] == event['thread'] and node['required']),
                                'story_closure', '线路仍有必要节点，不能提前关闭。')
            expected = (plan.get('clock') or {}).get('advance_days')
            if type(expected) is int:
                require(state['clock'] - book['state']['clock'] == expected, 'elapsed_days',
                        '正文推进的天数与章纲声明不一致。',
                        {'planned': expected, 'settled': state['clock'] - book['state']['clock']})
            require(all(book['state']['clock'] <= s['day'] <= state['clock']
                        for s in plan.get('schedule', [])), 'schedule', '本章硬日程不在已核验的主线时间区间内。')
            require(all(p in state['entities'] for p in plan.get('participants', [])), 'entity_coverage',
                    '章纲参与人尚无已核验的正文身份。')
            for item in state['entities'].values():
                for name in [item['name']] + item.get('aliases', []):
                    planning.check_text(name, planning.active_policy(book.get('lexical_policy')), names=True)
            row = {'n': chapter, 'title': draft['title'], 'prose': draft['prose'], 'events': events,
                   'plan': plan,
                   # The chapter's reconciliation record. The storage column keeps its old name
                   # (`review`) because renaming it would lock every existing project out of its own
                   # chapters; what it holds now is the writer's item-by-item drift_check and the
                   # deviations the engine booked against it — the replacement for a reviewer's
                   # receipt, recorded on the chapter itself.
                   'review': {'drift_check': copy.deepcopy(draft['drift_check']),
                              'design_drift': copy.deepcopy(settlement['deviations']),
                              'self_check': draft['self_check'],
                              'style_report': copy.deepcopy(style_report)},
                   'state_hash': digest(state), 'summary': draft['summary'], 'han': han_count(draft['prose'])}
            if draft.get('patch'):
                row['patch'] = draft['patch']
            book['state'], book['draft'] = state, None
            book['written_han'] += row['han']
    else:
        require(False, 'stage', '未注册的任务阶段。')
    if row is not None and data.get('understanding'):
        book['understanding'] = understanding.update(book.get('understanding'), data.get('understanding'),
                                                     sources, evidence, actor)
    book['revision'] += 1
    return Outcome(book, row, style_report, findings)
