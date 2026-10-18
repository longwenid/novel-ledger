"""Independent judgment validation. This checks evidence and protocol, not meaning."""
from __future__ import annotations

import copy
from .contracts import (AUTHOR_DECISION_FIELDS, AUTHOR_DECISIONS_PER_RECEIPT, AUTHOR_SEVERITY, CHECK_SETS,
                        CHECKS_VERSION, DECISION_OPTION_FIELDS, FINDING_SEVERITIES, FIRST_READ, checks_for, require, text)
from .evidence import evidence


def author_decision(findings):
    """The one author-level finding of a receipt, if any: no rewrite settles it, the author must decide."""
    rows = [f for f in findings or [] if isinstance(f, dict) and f.get('severity') == AUTHOR_SEVERITY]
    return rows[0]['decision'] if rows else None


def repairable(findings):
    """Findings a writer can act on: notes are advisory, author-level ones wait on the author."""
    return [f for f in findings or [] if f.get('severity') not in ('note', AUTHOR_SEVERITY)]


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


def checks(receipt, required, sources, obligations=(), challenge_ids=(), expected_version=None, author_channel=False):
    require(isinstance(receipt, dict) and receipt.get('verdict') in ('pass', 'fix'), 'review', '审稿需要 pass/fix 结论。',
            {'expect': {'verdict': 'pass|fix'},
             'rule': '没有 fail：任何一项有问题就整体记 fix 并逐条给 findings；全部成立才记 pass。',
             'got': receipt.get('verdict') if isinstance(receipt, dict) else None})
    version = receipt.get('checks_version', 1)
    require(expected_version is None or version == expected_version, 'checks_version', '回执版本与冻结任务不一致。',
            {'expected': expected_version, 'got': version, 'recover': '按当前任务模板填写 checks_version，不要降级检查清单。'})
    require(type(version) is int and version in CHECK_SETS, 'checks_version', '未知的检查清单版本。',
            {'known_versions': sorted(CHECK_SETS), 'recover': '回执按下发模板里的 checks_version 填写。'})
    rows = receipt.get('checks')
    require(isinstance(rows, list) and len(rows) == len(required) and all(isinstance(r, dict) and text(r.get('id')) for r in rows)
            and {r['id'] for r in rows} == set(required), 'review_coverage', '检查项须恰好覆盖任务清单，不得缺项或重复。',
            {'expect': list(required), 'checks_version': version})
    normalized = copy.deepcopy(receipt)
    normalized['checks_version'] = version
    for row in normalized['checks']:
        require(row.get('result') in ('pass', 'fix') and text(row.get('reason')), 'review', '每项检查须独立判断并给出理由。',
                {'expect': {'result': 'pass|fix', 'reason': 'str'},
                 'rule': '没有 fail：该项有问题记 fix 并在 findings 里逐条说明；两项都不可空。',
                 'got': {'result': row.get('result')}})
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
    decisions = []
    for finding in findings:
        require(isinstance(finding, dict) and finding.get('criterion') in required, 'finding', '发现须挂在本任务检查项上。',
                {'valid_criteria': list(required)})
        require(finding.get('severity') in FINDING_SEVERITIES and text(finding.get('reason')), 'finding',
                '发现须有严重度和具体原因。',
                {'expect': {'criterion': 'valid_criteria 之一', 'severity': '|'.join(FINDING_SEVERITIES), 'reason': 'str',
                            'evidence': '单个 {chapter,quote,start?} 对象', 'target_chapter': 'int（note 级可省）',
                            'repair_scope': 'local|chapter', 'decision': 'severity=author 时必填 {id,question,options}'}})
        finding['evidence'] = evidence(finding.get('evidence'), sources)
        if finding['severity'] == AUTHOR_SEVERITY:
            require(author_channel, 'author_decision', '本章节审稿没有作者裁决通道：能由改写解决的缺陷请用 blocker/quality 并给出修复章。',
                    {'recover': '需要作者拍板的设计问题，在世界模型、设计或跨章核验阶段上交。'})
            decision = finding.get('decision')
            require(isinstance(decision, dict) and all(k in decision for k in AUTHOR_DECISION_FIELDS)
                    and text(decision.get('id')) and text(decision.get('question'))
                    and isinstance(decision.get('options'), list) and len(decision['options']) >= 2
                    and all(isinstance(o, dict) and all(text(o.get(k)) for k in DECISION_OPTION_FIELDS) for o in decision['options']),
                    'author_decision', '需作者拍板的发现须带 id、具体 question 与至少两个 label/impact 选项。',
                    {'expect': {'id': 'str（同一裁决跨轮保持同一 id）', 'question': 'str',
                                'options': [{'label': 'str', 'impact': 'str'}, {'label': 'str', 'impact': 'str'}]},
                     'recover': '把设计问题连同取舍写成 question/选项交给作者，不要用 blocker 让写作端去改。'})
            decisions.append(finding)
            blocking.add(finding['criterion'])
            continue
        require('decision' not in finding, 'author_decision', '只有 severity=author 的发现可以携带裁决选项。',
                {'recover': '能由改写解决的缺陷删掉 decision 并给出 target_chapter/repair_scope。'})
        if finding['severity'] != 'note':
            blocking.add(finding['criterion'])
            require(type(finding.get('target_chapter')) is int and finding['target_chapter'] in sources,
                    'repair_scope', '缺陷须挂在冻结材料的章号上。',
                    {'valid_chapters': sorted(sources), 'got': finding.get('target_chapter'),
                     'rule': 'target_chapter 只能取本任务冻结材料包含的章号；全书设计/卷纲/约定核验的冻结材料是 '
                             'chapter 0——缺陷无论落在第几章都记 0，具体章写进 reason 的修订范围。'})
            require(finding.get('repair_scope') in ('local', 'chapter'), 'repair_scope',
                    '缺陷须明确 local/chapter 修复范围。',
                    {'valid_scopes': ['local', 'chapter'], 'got': finding.get('repair_scope')})
    require(len(decisions) <= AUTHOR_DECISIONS_PER_RECEIPT, 'author_decision', '一份回执一次只能上交一个作者裁决。',
            {'got': [f['decision']['id'] for f in decisions], 'limit': AUTHOR_DECISIONS_PER_RECEIPT,
             'recover': '把其余问题合并成同一问题的选项，或在下一轮核验中另交。'})
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
    facts = checks(data.get('facts'), checks_for(version, 'fact'), sources, [o for o in obligations if o['category'] == 'facts'], ('time',), version)
    reader = checks(data.get('reader'), checks_for(version, 'reader'), sources, [o for o in obligations if o['category'] == 'reader'], ('language',), version)
    if facts['verdict'] == 'pass':
        require(isinstance(facts.get('events'), list) and text(facts.get('summary')) and type(facts.get('elapsed_days')) is int
                and facts['elapsed_days'] >= 0, 'facts', '事实通过须提供 events、具体 summary 和非负 elapsed_days。')
    return facts, reader
