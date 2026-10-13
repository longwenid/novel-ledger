"""Independent judgment validation. This checks evidence and protocol, not meaning."""
from __future__ import annotations

import copy
from .contracts import DESIGN_CHECKS, FACT_CHECKS, FIRST_READ, LONG_CHECKS, READER_CHECKS, WORLD_CHECKS, require, text
from .facts import evidence
from .world import SECTIONS
from . import planning


def first_read(data, sources):
    require(isinstance(data, dict) and isinstance(data.get('reads'), list), 'first_read', '首读需要 reads 数组。')
    reads = data['reads']
    require(len(reads) == len(sources) and all(isinstance(r, dict) and type(r.get('chapter')) is int for r in reads)
            and {r['chapter'] for r in reads} == set(sources), 'first_read', '首读须完整覆盖全部冻结正文。')
    for item in reads:
        require(isinstance(item, dict) and all(text(item.get(k)) for k in FIRST_READ), 'first_read', '每章首读四项均须为具体非空体验。')
    return copy.deepcopy(data)


def checks(receipt, required, sources, obligations=(), challenge_ids=()):
    require(isinstance(receipt, dict) and receipt.get('verdict') in ('pass', 'fix'), 'review', '审稿需要 pass/fix 结论。')
    rows = receipt.get('checks')
    require(isinstance(rows, list) and len(rows) == len(required) and all(isinstance(r, dict) and text(r.get('id')) for r in rows)
            and {r['id'] for r in rows} == set(required), 'review_coverage', '检查项须恰好覆盖任务清单，不得缺项或重复。')
    normalized = copy.deepcopy(receipt)
    for row in normalized['checks']:
        require(row.get('result') in ('pass', 'fix') and text(row.get('reason')), 'review', '每项检查须独立判断并给出理由。')
        refs = row.get('evidence')
        require(isinstance(refs, list) and refs, 'evidence', '每项检查须引用完整来源。')
        row['evidence'] = [evidence(ref, sources) for ref in refs]
        if row['id'] in challenge_ids:
            challenge = row.get('challenge')
            require(isinstance(challenge, dict) and text(challenge.get('risk')) and text(challenge.get('reason'))
                    and challenge.get('disposition') == ('satisfied' if row['result'] == 'pass' else 'violated'), 'challenge', '时间与文风须核对具体反证，结论一致。')
            challenge['evidence'] = evidence(challenge.get('evidence'), sources)
    findings = normalized.get('findings')
    require(isinstance(findings, list), 'finding', '审稿须提供 findings 数组，无问题用空数组。')
    failed = {r['id'] for r in normalized['checks'] if r['result'] == 'fix'}
    blocking = set()
    for finding in findings:
        require(isinstance(finding, dict) and finding.get('criterion') in required and finding.get('severity') in ('blocker', 'quality', 'note')
                and text(finding.get('reason')), 'finding', '发现须有检查项、严重度和具体原因。')
        finding['evidence'] = evidence(finding.get('evidence'), sources)
        if finding['severity'] != 'note':
            blocking.add(finding['criterion'])
            require(type(finding.get('target_chapter')) is int and finding['target_chapter'] in sources
                    and finding.get('repair_scope') in ('local', 'chapter'), 'repair_scope', '缺陷须明确修复章和 local/chapter 范围。')
    require(blocking == failed and receipt['verdict'] == ('fix' if failed else 'pass'), 'review_consistency', '结论、检查与实质缺陷必须一致。')
    rows = normalized.get('obligations', [])
    require(isinstance(rows, list) and len(rows) == len(obligations) and all(isinstance(r, dict) and text(r.get('id')) for r in rows)
            and {r['id'] for r in rows} == {o['id'] for o in obligations}, 'obligation', '必须逐项回应任务中的修改义务。')
    for row in rows:
        require(row.get('result') in ('pass', 'fix') and text(row.get('reason')) and isinstance(row.get('evidence'), list)
                and row['evidence'], 'obligation', '义务回应需要判断、理由和正文证据。')
        row['evidence'] = [evidence(ref, sources) for ref in row['evidence']]
        require(row['result'] != 'fix' or any(f.get('obligation_id') == row['id'] and f['severity'] != 'note' for f in findings),
                'obligation', '未履行义务必须关联实质缺陷。')
    return normalized


def chapter_review(data, sources, obligations):
    require(isinstance(data, dict), 'review', '综合审稿须为对象。')
    facts = checks(data.get('facts'), FACT_CHECKS, sources, [o for o in obligations if o['category'] == 'facts'], ('time',))
    reader = checks(data.get('reader'), READER_CHECKS, sources, [o for o in obligations if o['category'] == 'reader'], ('language',))
    if facts['verdict'] == 'pass':
        require(isinstance(facts.get('events'), list) and text(facts.get('summary')) and type(facts.get('elapsed_days')) is int
                and facts['elapsed_days'] >= 0, 'facts', '事实通过须提供 events、具体 summary 和非负 elapsed_days。')
    return facts, reader


def template(stage, chapter, sources, obligations=()):
    def review(ids, obs=(), challenges=()):
        return {'verdict': '', 'checks': [dict(id=ident, result='', reason='', evidence=[],
                **({'challenge': {'risk': '', 'disposition': '', 'reason': '', 'evidence': {}}} if ident in challenges else {})) for ident in ids],
                'findings': [], 'obligations': [{'id': o['id'], 'result': '', 'reason': '', 'evidence': []} for o in obs]}
    if stage == 'chapter_review':
        facts = review(FACT_CHECKS, [o for o in obligations if o['category'] == 'facts'], ('time',))
        facts.update(events=[], summary='', elapsed_days=None)
        return {'facts': facts, 'reader': review(READER_CHECKS, [o for o in obligations if o['category'] == 'reader'], ('language',))}
    if stage in ('design_review', 'contract_review'):
        return review(DESIGN_CHECKS)
    if stage == 'world_review':
        return review(WORLD_CHECKS)
    if stage == 'opening_options':
        return {'gate': '', 'options': []}
    if stage == 'world_model':
        return {'selection_hash': '', 'premise': '', 'story_capacity': '', **{k: [] for k in SECTIONS}}
    if stage == 'opening_contract':
        return planning.skeleton()
    if stage in ('scope_review', 'scope_synthesis'):
        result = review(LONG_CHECKS)
        result['coverage'] = [{'chapter': n, 'reason': '', 'evidence': {}} for n in sources]
        return result
    if stage in ('write', 'repair', 'redesign'):
        return {'title': '', 'prose': '', 'summary': '', 'self_check': ''}
    if stage == 'profiles':
        return {'profiles': []}
    if stage == 'plan':
        return {'plans': []}
    return {'intent': '', 'ending_conditions': '', 'nodes': []}
