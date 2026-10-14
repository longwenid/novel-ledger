"""Independent judgment validation. This checks evidence and protocol, not meaning."""
from __future__ import annotations

import copy
from .contracts import CHECK_SETS, CHECKS_VERSION, FIRST_READ, checks_for, require, text
from .facts import evidence
from .world import SECTIONS
from . import planning


def first_read(data, sources):
    require(isinstance(data, dict) and isinstance(data.get('reads'), list), 'first_read', '首读需要 reads 数组。',
            {'expect': 'reads 每项 {chapter, desire, obstacle, change, read_on_reason}，四项均为具体非空文本。'})
    reads = data['reads']
    require(len(reads) == len(sources) and all(isinstance(r, dict) and type(r.get('chapter')) is int for r in reads)
            and {r['chapter'] for r in reads} == set(sources), 'first_read', '首读须完整覆盖全部冻结正文。',
            {'frozen_chapters': sorted(sources)})
    for item in reads:
        require(isinstance(item, dict) and all(text(item.get(k)) for k in FIRST_READ), 'first_read', '每章首读四项均须为具体非空体验。')
    return copy.deepcopy(data)


def checks(receipt, required, sources, obligations=(), challenge_ids=()):
    require(isinstance(receipt, dict) and receipt.get('verdict') in ('pass', 'fix'), 'review', '审稿需要 pass/fix 结论。')
    version = receipt.get('checks_version', 1)
    require(version in CHECK_SETS, 'checks_version', '未知的检查清单版本。',
            {'known_versions': sorted(CHECK_SETS), 'recover': '回执按下发模板里的 checks_version 填写。'})
    rows = receipt.get('checks')
    require(isinstance(rows, list) and len(rows) == len(required) and all(isinstance(r, dict) and text(r.get('id')) for r in rows)
            and {r['id'] for r in rows} == set(required), 'review_coverage', '检查项须恰好覆盖任务清单，不得缺项或重复。',
            {'expect': list(required), 'checks_version': version})
    normalized = copy.deepcopy(receipt)
    normalized['checks_version'] = version
    for row in normalized['checks']:
        require(row.get('result') in ('pass', 'fix') and text(row.get('reason')), 'review', '每项检查须独立判断并给出理由。')
        refs = row.get('evidence')
        require(isinstance(refs, list) and refs, 'evidence', '每项检查须引用完整来源。')
        row['evidence'] = [evidence(ref, sources) for ref in refs]
        if row['id'] in challenge_ids:
            challenge = row.get('challenge')
            require(isinstance(challenge, dict) and text(challenge.get('risk')) and text(challenge.get('reason'))
                    and challenge.get('disposition') == ('satisfied' if row['result'] == 'pass' else 'violated'), 'challenge', '时间与文风须核对具体反证，结论一致。',
                    {'expect': {'risk': 'str', 'disposition': '检查 pass 时为 satisfied，fix 时为 violated',
                                'reason': 'str', 'evidence': '单个 {chapter,quote,start?} 对象'}})
            challenge['evidence'] = evidence(challenge.get('evidence'), sources)
    findings = normalized.get('findings')
    require(isinstance(findings, list), 'finding', '审稿须提供 findings 数组，无问题用空数组。')
    failed = {r['id'] for r in normalized['checks'] if r['result'] == 'fix'}
    blocking = set()
    for finding in findings:
        require(isinstance(finding, dict) and finding.get('criterion') in required, 'finding', '发现须挂在本任务检查项上。',
                {'valid_criteria': list(required)})
        require(finding.get('severity') in ('blocker', 'quality', 'note') and text(finding.get('reason')), 'finding',
                '发现须有严重度和具体原因。',
                {'expect': {'criterion': 'valid_criteria 之一', 'severity': 'blocker|quality|note', 'reason': 'str',
                            'evidence': '单个 {chapter,quote,start?} 对象', 'target_chapter': 'int（note 级可省）',
                            'repair_scope': 'local|chapter'}})
        finding['evidence'] = evidence(finding.get('evidence'), sources)
        if finding['severity'] != 'note':
            blocking.add(finding['criterion'])
            require(type(finding.get('target_chapter')) is int and finding['target_chapter'] in sources
                    and finding.get('repair_scope') in ('local', 'chapter'), 'repair_scope', '缺陷须明确修复章和 local/chapter 范围。')
    require(blocking == failed and receipt['verdict'] == ('fix' if failed else 'pass'), 'review_consistency', '结论、检查与实质缺陷必须一致。')
    rows = normalized.get('obligations', [])
    require(isinstance(rows, list) and len(rows) == len(obligations) and all(isinstance(r, dict) and text(r.get('id')) for r in rows)
            and {r['id'] for r in rows} == {o['id'] for o in obligations}, 'obligation',
            '义务回应须与任务义务清单一一对应。' if obligations else '本阶段任务未定义修改义务，obligations 须为空数组。',
            {'expect': [o['id'] for o in obligations] if obligations else []})
    for row in rows:
        require(row.get('result') in ('pass', 'fix') and text(row.get('reason')) and isinstance(row.get('evidence'), list)
                and row['evidence'], 'obligation', '义务回应需要判断、理由和正文证据。')
        row['evidence'] = [evidence(ref, sources) for ref in row['evidence']]
        require(row['result'] != 'fix' or any(f.get('obligation_id') == row['id'] and f['severity'] != 'note' for f in findings),
                'obligation', '未履行义务必须关联实质缺陷。')
    return normalized


def chapter_review(data, sources, obligations, version=CHECKS_VERSION):
    require(isinstance(data, dict), 'review', '综合审稿须为对象。')
    facts = checks(data.get('facts'), checks_for(version, 'fact'), sources, [o for o in obligations if o['category'] == 'facts'], ('time',))
    reader = checks(data.get('reader'), checks_for(version, 'reader'), sources, [o for o in obligations if o['category'] == 'reader'], ('language',))
    if facts['verdict'] == 'pass':
        require(isinstance(facts.get('events'), list) and text(facts.get('summary')) and type(facts.get('elapsed_days')) is int
                and facts['elapsed_days'] >= 0, 'facts', '事实通过须提供 events、具体 summary 和非负 elapsed_days。')
    return facts, reader


def template(stage, chapter, sources, obligations=(), extra=()):
    """The blank result for a stage. `extra` carries stages a combined dispatch also answers."""
    def review(ids, obs=(), challenges=()):
        return {'verdict': '', 'checks_version': CHECKS_VERSION,
                'checks': [dict(id=ident, result='', reason='', evidence=[],
                **({'challenge': {'risk': '', 'disposition': '', 'reason': '', 'evidence': {}}} if ident in challenges else {})) for ident in ids],
                'findings': [], 'obligations': [{'id': o['id'], 'result': '', 'reason': '', 'evidence': []} for o in obs]}
    if stage == 'chapter_review':
        facts = review(checks_for(CHECKS_VERSION, 'fact'), [o for o in obligations if o['category'] == 'facts'], ('time',))
        facts.update(events=[], summary='', elapsed_days=None)
        return {'facts': facts, 'reader': review(checks_for(CHECKS_VERSION, 'reader'), [o for o in obligations if o['category'] == 'reader'], ('language',))}
    if stage in ('design_review', 'contract_review'):
        return review(checks_for(CHECKS_VERSION, 'design'))
    if stage == 'world_review':
        return review(checks_for(CHECKS_VERSION, 'world'))
    if stage == 'opening_options':
        return {'gate': '', 'options': []}
    if stage == 'world_model':
        skeleton = {'selection_hash': '', 'premise': '', 'story_capacity': '', **{k: [] for k in SECTIONS}}
        if extra and 'opening_contract' in extra:
            # One dispatch drafts the world and the contract it implies: the contract is a reading
            # of selections plus that world, so it belongs in the same cold session.
            return {**skeleton, 'contract': planning.skeleton()}
        return skeleton
    if stage == 'opening_contract':
        return planning.skeleton()
    if stage in ('scope_review', 'scope_synthesis'):
        result = review(checks_for(CHECKS_VERSION, 'long'))
        result['coverage'] = [{'chapter': n, 'reason': '', 'evidence': {}} for n in sources]
        return result
    if stage in ('write', 'repair', 'redesign'):
        return {'title': '', 'prose': '', 'summary': '', 'self_check': ''}
    if stage == 'profiles':
        return {'profiles': []}
    if stage == 'plan':
        return {'plans': []}
    return {'intent': '', 'ending_conditions': '', 'nodes': []}
