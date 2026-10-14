"""Pure editorial decisions: alignment holds, root remedies and scope closure."""
from __future__ import annotations

import copy
from .contracts import digest, require, text

CLOSURE_CHECKS = ('scope_question', 'dramatized_process', 'character_choice', 'cost', 'aftermath', 'handoff')


def enabled(book):
    return bool((book.get('contract') or {}).get('editorial_features'))


def effective_contract(book):
    value = copy.deepcopy(book['contract'])
    first = 1
    for volume in value['volumes']:
        volume['first'] = first
        volume['end'] = book.get('scope_ends', {}).get(volume['id'], volume['end'])
        first = volume['end'] + 1
    return value


def context_hash(book):
    return digest({k: book.get(k) for k in ('contract', 'designs', 'profiles', 'style_anchor', 'scope_ends')})


def sources(book, scope):
    rows = [{'id': 'contract:reader_promise', 'text': book['contract']['reader_promise'], 'required': True},
            {'id': 'contract:ending', 'text': book['contract']['ending'], 'required': True}]
    # The theme is a payoff like the promise and the ending, so 完本验收 checks it too. A contract
    # imported before opening/2 never declared one, and then there is simply no such source.
    if text(book['contract'].get('theme')):
        rows.append({'id': 'contract:theme', 'text': book['contract']['theme'], 'required': True})
    for field in ('world_rules', 'red_lines', 'style_traits', 'relationships', 'arcs'):
        rows.extend({'id': 'contract:' + field + ':' + str(i), 'text': value, 'required': True}
                    for i, value in enumerate(book['contract'].get(field, [])))
    rows.extend({'id': 'author_feedback:' + str(i), 'text': value, 'required': True} for i, value in enumerate(book['feedback']))
    for design in book['designs'].values():
        for node in design['nodes']:
            rows.append({'id': 'node:' + node['id'], 'text': node['outcome'], 'required': node['required']})
        for line in design.get('threads', []):
            rows.append({'id': 'thread:' + line['id'], 'text': line['ending_condition'], 'required': line['required']})
    rows.extend({'id': 'hook:' + k, 'text': h['text'], 'required': True} for k, h in book['state']['hooks'].items())
    rows.extend({'id': 'case:' + k, 'text': c['goal'], 'required': True} for k, c in book.get('repair_cases', {}).items())
    # IDs are stable requirements, never a count inferred from chapter length.
    return list({r['id']: r for r in rows}.values()) if scope == 'book' else []


def root_case(book, data, scope, evidence, chapter):
    value = data.get('repair_case')
    require(isinstance(value, dict) and all(text(value.get(k)) for k in ('root_ref', 'goal', 'verification_condition')),
            'repair_case', '修复需 repair_case={root_ref,goal,verification_condition,evidence}，root_ref 使用稳定问题来源。')
    ref = evidence(value.get('evidence'))
    cases = book.setdefault('repair_cases', {})
    # An unresolved scope has one stable root. A new label cannot reset the existing allowance.
    active = [(k, c) for k, c in cases.items() if c['scope'] == scope and c['status'] != 'resolved']
    key = digest({'scope': scope, 'root_ref': value['root_ref']})
    require(not active or any(k == key for k, c in active), 'repair_case', '本范围尚有未解决根问题，不能换来源文字重开额度。',
            {'active': [k for k, c in active], 'recover': '沿原 repair_case.root_ref 和目标提出下一轮实质方案。'})
    case = cases.setdefault(key, {'root_ref': value['root_ref'], 'scope': scope, 'goal': value['goal'],
                                 'verification_condition': value['verification_condition'], 'rounds': [], 'status': 'open'})
    require(case['goal'] == value['goal'] and case['verification_condition'] == value['verification_condition'],
            'repair_case', '未解决的原目标与验收条件不能被新措辞替换。')
    mechanism = data.get('remedy')
    require(isinstance(mechanism, dict) and all(text(mechanism.get(k)) for k in ('mechanism', 'substantive_change')),
            'remedy', 'remedy 需 mechanism/substantive_change，说明本轮如何修好。')
    require(len(case['rounds']) < 2, 'remedy_exhausted', '根问题两轮方案已耗尽，保留最后验收和原目标。', {'case_id': key, 'recover': '请求作者针对原问题作具体裁决，不 resume 重发。'})
    fingerprint = digest(mechanism)
    require(not case['rounds'] or case['rounds'][-1]['mechanism_hash'] != fingerprint, 'remedy', '原样方案不能作为新一轮修复。')
    round_id = digest({'case': key, 'round': len(case['rounds']) + 1, 'mechanism': mechanism})
    case['rounds'].append({'id': round_id, 'mechanism_hash': fingerprint, 'proposal': copy.deepcopy(mechanism),
                           'evidence': ref, 'chapter': chapter, 'status': 'pending'})
    case['status'] = 'open'
    return key


def remedy_review(book, data, scope, evidence):
    active = {k: c for k, c in book.get('repair_cases', {}).items() if c['status'] != 'resolved'
              and (c['scope'] == scope or scope == 'revision' and k in (book.get('revision_run') or {}).get('case_ids', []))}
    if not active:
        return
    rows = data.get('remedy_review')
    require(isinstance(rows, list) and len(rows) == len(active) and all(isinstance(r, dict) and text(r.get('case_id')) for r in rows)
            and {r.get('case_id') for r in rows} == set(active), 'remedy_review', '逐项验收当前范围所有根问题。')
    for row in rows:
        case = active[row['case_id']]
        require(row.get('round_id') == case['rounds'][-1]['id'] and row.get('result') in ('pass', 'fix') and text(row.get('reason')),
                'remedy_review', '绑定最后一轮 round_id 并给出实际验收依据。')
        row['evidence'] = evidence(row.get('evidence'))
        require(row['result'] == ('pass' if data['verdict'] == 'pass' else 'fix'), 'remedy_review', '根问题验收与本范围结论须一致。')
        case['rounds'][-1]['review'] = copy.deepcopy(row)
        case['rounds'][-1]['status'] = row['result']
        if row['result'] == 'pass':
            case['status'] = 'resolved'


def closure(book, task, data, evidence):
    scope = task['scope']
    value = data.get('closure')
    payload = task['payload']['closure']
    require(isinstance(value, dict) and value.get('context_hash') == payload['context_hash'], 'closure', '关闭回执须绑定冻结 context_hash。')
    decision = value.get('decision')
    require(decision in ('accept_close', 'continue_scope', 'revise_range', 'needs_author'), 'closure', '关闭 decision 不合法。')
    checks = value.get('checks')
    require(isinstance(checks, list) and len(checks) == len(CLOSURE_CHECKS) and all(isinstance(r, dict) and text(r.get('id')) for r in checks)
            and {r.get('id') for r in checks} == set(CLOSURE_CHECKS), 'closure', '关闭六项检查须完整覆盖。')
    for row in checks:
        require(row.get('result') in ('pass', 'missing', 'defect', 'author') and text(row.get('reason'))
                and isinstance(row.get('evidence'), list) and row['evidence'], 'closure', '关闭检查需结论、理由与正文证据。')
        row['evidence'] = [evidence(r) for r in row['evidence']]
    require((decision == 'accept_close') == (data['verdict'] == 'pass'), 'closure', '只有 accept_close 可与 pass 一起提交。')
    if decision == 'accept_close':
        require(all(r['result'] == 'pass' for r in checks), 'closure', '关闭前六项职责全部成立。')
        if scope == 'book':
            rows = value.get('completion_coverage')
            wanted = {r['id']: r for r in payload['sources']}
            require(isinstance(rows, list) and len(rows) == len(wanted) and all(isinstance(r, dict) and text(r.get('id')) for r in rows)
                    and {r.get('id') for r in rows} == set(wanted), 'completion_coverage', '终审逐项覆盖独立枚举的全部来源。')
            for row in rows:
                require(text(row.get('reason')) and row.get('result') in ('fulfilled', 'permitted_open')
                        and (row['result'] == 'fulfilled' or not wanted[row['id']]['required']), 'completion_coverage', '核心职责不得以开放结局排除。')
                require(isinstance(row.get('evidence'), list) and row['evidence'], 'completion_coverage', '每项来源须正文证据。')
                row['evidence'] = [evidence(r) for r in row['evidence']]
            require(value.get('prose_hashes') == payload['prose_hashes'] and value.get('source_coverage_checked') is True
                    and value.get('cross_chunk_checked') is True, 'completion_coverage', '终审需确认准确正文版本及跨块查漏。')
        book.setdefault('scope_closures', {})[scope] = {'review_key': task['payload']['review_key'], 'context_hash': payload['context_hash'],
                                                      'value': copy.deepcopy(value)}
        return
    require(any(r['result'] != 'pass' for r in checks), 'closure', '非关闭决定需明确未解决职责。')
    if decision == 'needs_author':
        require(text(value.get('question')) and isinstance(value.get('options'), list) and len(value['options']) >= 2
                and all(isinstance(o, dict) and text(o.get('label')) and text(o.get('impact')) for o in value['options']),
                'closure', '作者裁决需具体 question 及至少两个 label/impact 选项。')
        book['author_block'] = copy.deepcopy(value)
        book.update(status='paused', pause_reason=value['question'])
        return
    exhausted = [k for k, c in book.get('repair_cases', {}).items() if c['scope'] == scope and c['status'] != 'resolved'
                 and len(c['rounds']) >= 2 and c['rounds'][-1]['status'] == 'fix']
    if exhausted:
        book['remedy_exhausted'] = exhausted
        book.update(status='paused', pause_reason='根问题最后一轮仍未通过，已保存验收；需作者针对原目标裁决。')
        return
    case_id = root_case(book, value, scope, evidence, task['last'])
    if decision == 'revise_range':
        span = value.get('range')
        require(isinstance(span, list) and len(span) == 2 and all(type(n) is int for n in span)
                and task['first'] <= span[0] <= span[1] <= task['last'], 'closure', '修订 range=[起点,终点] 须在已核验范围内。')
        book['revision_directive'] = {'first': span[0], 'through': task['last'], 'reason': value['repair_case']['goal'], 'case_ids': [case_id]}
        book.update(status='paused', pause_reason='关闭核验要求修订已写缺陷。')
        return
    require(value.get('existing_content_valid') is True and not any(r['result'] in ('defect', 'author') for r in checks)
            and all(text(value.get(k)) for k in ('missing_function', 'completion_path', 'length_basis')), 'closure', '补写只处理未展开职责，不能掩盖已写缺陷。')
    contract = effective_contract(book)
    target = contract['volumes'][-1] if scope == 'book' else next((v for v in contract['volumes'] if 'volume:' + v['id'] == scope), None)
    require(target is not None and target['end'] == task['last'] and not book.get('revision_run'), 'closure', '只能在当前卷真实尾部补写；历史卷或修订中走 revise。')
    through = value.get('append_through')
    require(type(through) is int and target['end'] < through <= target['end'] + contract['scope_append_limit'], 'closure', '补写终点须有界，遵守 scope_append_limit。')
    require(book['finish'] or book['target'] >= through, 'target', '补写不能超出作者授权章节范围。')
    delta = through - target['end']
    require(book['written_han'] + (contract['volumes'][-1]['end'] - task['last'] + delta) * contract['chapter_min'] <= contract['word_range'][1],
            'word_budget', '补写后总篇幅无法成立，须作者改约。')
    book['scope_ends'] = {v['id']: v['end'] + (delta if v['end'] >= target['end'] else 0) for v in contract['volumes']}
    if book['finish']:
        book['target'] += delta
    # The original contract/hash stays immutable; only a bounded scope decision changes layout.
    book['plans'] = {n: p for n, p in book['plans'].items() if int(n) <= task['last']}
    book['alignment_hold'] = {'mode': 'future', 'chapter': task['last'] + 1, 'reason': value['completion_path'], 'case_ids': [case_id]}


def alignment(data, plan, events, evidence, state=None):
    value = copy.deepcopy(data.get('alignment'))
    require(isinstance(value, dict) and value.get('action') in ('follow_plan', 'adapt_future', 'align_design', 'repair_prose')
            and text(value.get('reason')), 'alignment', 'alignment 需 action/reason/realizations。')
    rows = value.get('realizations')
    require(isinstance(rows, list) and len(rows) == len(plan['node_ids']) and all(isinstance(r, dict) and text(r.get('node')) for r in rows)
            and {r.get('node') for r in rows} == set(plan['node_ids']), 'alignment', 'realizations 恰好核验本章每个节点，未实现也明示。')
    actual = {}
    for row in rows:
        require(row.get('after') in ('seeded', 'advanced', 'resolved', 'not_realized') and text(row.get('reason')), 'alignment', '实际实现 after/reason 不合法。')
        row['evidence'] = evidence(row.get('evidence'))
        definition = plan['node_contracts'][row['node']]
        criteria = {c['id']: c for c in definition.get('criteria', [])}
        if criteria:
            fulfilled = row.get('fulfilled_criteria')
            require(isinstance(fulfilled, list) and all(isinstance(c, dict) and text(c.get('id')) and c['id'] in criteria and text(c.get('actual_effect')) for c in fulfilled)
                    and len({c['id'] for c in fulfilled}) == len(fulfilled), 'alignment', '逐项声明 fulfilled_criteria={id,actual_effect,evidence}。')
            for criterion in fulfilled:
                criterion['evidence'] = evidence(criterion.get('evidence'))
            prior = row.get('prior_criteria', [])
            established = (state or {}).get('story_nodes', {}).get(row['node'], {}).get('criteria', {})
            require(isinstance(prior, list) and all(text(k) and k in criteria and k in established for k in prior)
                    and len(prior) == len(set(prior)), 'alignment', 'prior_criteria 只能引用正式前态已核验的本节点判据。')
            require(row['after'] != 'resolved' or {k for k, c in criteria.items() if c.get('required', True)} <= {c['id'] for c in fulfilled} | set(prior),
                    'alignment', '必要效果判据没有正文证据，不能声明节点兑现。')
        if row['after'] != 'not_realized':
            actual[row['node']] = row['after']
    require(isinstance(events, list) and all(isinstance(e, dict) and (e.get('op') != 'story_node' or text(e.get('node'))) for e in events),
            'alignment', '事实事件须为对象，节点 ID 须为非空字符串。')
    provided = {e.get('node'): e.get('after') for e in events if e.get('op') == 'story_node'}
    require(len(provided) == sum(e.get('op') == 'story_node' for e in events) and provided == actual,
            'alignment', '实际实现须与独立事实事件一致。')
    judgments = {r['node']: r for r in rows}
    require(all('criteria' not in e or e['criteria'] == judgments[e['node']].get('fulfilled_criteria', [])
                for e in events if e['op'] == 'story_node'), 'alignment', '节点事件判据须与独立实现回执一致。')
    if value['action'] == 'follow_plan':
        require(actual == {a['node']: a['after'] for a in plan['node_actions']}, 'alignment', '偏离原计划时用 adapt_future 或 align_design。')
    return copy.deepcopy(value)


def closure_template(payload):
    return {'context_hash': payload['context_hash'], 'decision': '',
            'checks': [{'id': k, 'result': '', 'reason': '', 'evidence': []} for k in CLOSURE_CHECKS],
            **({'completion_coverage': [{'id': r['id'], 'result': '', 'reason': '', 'evidence': []} for r in payload['sources']],
                'prose_hashes': payload['prose_hashes'], 'source_coverage_checked': False, 'cross_chunk_checked': False} if payload['sources'] else {})}
