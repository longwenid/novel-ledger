"""Pure evidence and explicit scene-time constraints; no natural-language truth oracle."""
from __future__ import annotations

from .contracts import digest, require, text


def citation(row, sources):
    require(isinstance(row, dict) and text(row.get('source')) and row['source'] in sources,
            'continuity_evidence', '引文不属于冻结来源。')
    source = sources[row['source']]
    start, quote = row.get('start'), row.get('quote')
    require(type(start) is int and start >= 0 and text(quote)
            and source['prose'][start:start + len(quote)] == quote
            and row.get('prose_hash') == source['prose_hash'],
            'continuity_evidence', '引文偏移、原文或版本不匹配。')
    return dict(row)


def observations(rows, sources):
    require(isinstance(rows, list), 'continuity_observation', '独立观察必须是列表。')
    result = []
    for row in rows:
        require(isinstance(row, dict) and all(text(row.get(k)) for k in ('entity', 'predicate'))
                and 'value' in row and row.get('certainty') in ('explicit', 'apparent', 'reported', 'uncertain'),
                'continuity_observation', '观察须有实体、谓词、值和明确/表象/传闻/不确定层级。')
        require(row.get('time_frame', 'present') in ('present', 'flashback', 'parallel', 'uncertain'),
                'continuity_observation', 'time_frame须区分当前叙事、补叙、并行或时序未决。')
        require(row['predicate'] != 'life_state' or row['value'] in ('alive', 'dead', 'unknown'),
                'continuity_observation', 'life_state使用alive/dead/unknown；昏迷等情况另记谓词。')
        value = {**row, 'evidence': citation(row.get('evidence'), sources)}
        if row.get('transition') is not None:
            require(isinstance(row['transition'], dict) and row['transition'].get('kind') == 'revival',
                    'continuity_observation', '生命周期例外须明确复苏机制。')
            value['transition'] = {'kind': 'revival', 'evidence': citation(row['transition'].get('evidence'), sources)}
        result.append(value)
    return result


def observed_contradictions(rows):
    """Irreversible explicit states cannot be waived by a clean report.

Only observations backed by raw prose enter here, never the old writer's ledger.
Apparent death, hearsay and an independently cited revival remain distinct.
"""
    def order(row):
        ev = row['evidence']
        return (float('inf') if ev['source'] == 'candidate' else int(ev['source']), ev['start'])

    last, issues = {}, []
    for row in sorted(rows, key=order):
        if row['predicate'] != 'life_state' or row['certainty'] != 'explicit' \
                or row.get('time_frame', 'present') != 'present' or row['value'] not in ('alive', 'dead'):
            continue
        prior = last.get(row['entity'])
        transition = row.get('transition')
        revived = transition and prior and order(prior) <= order(transition) <= order(row)
        if prior and prior['value'] == 'dead' and row['value'] == 'alive' and not revived:
            issues.append({'kind': 'contradiction', 'reason': '独立原文观察记录同一实体明确死亡后再次存活，缺少复苏事件。',
                           'evidence': [prior['evidence'], row['evidence']]})
        last[row['entity']] = row
    return issues


def findings(rows, sources):
    require(isinstance(rows, list), 'continuity_report', 'findings必须是列表。')
    result = []
    for row in rows:
        require(isinstance(row, dict) and row.get('kind') in ('contradiction', 'uncertain', 'editorial')
                and text(row.get('reason')), 'continuity_report', '问题须区分矛盾、歧义、编辑判断并说明原因。')
        evidence = row.get('evidence')
        require(isinstance(evidence, list) and len(evidence) >= (2 if row['kind'] == 'contradiction' else 1),
                'continuity_evidence', '明确矛盾须给出成对原文证据，其他判断至少一条。')
        result.append({**row, 'evidence': [citation(item, sources) for item in evidence]})
    return result


def timeline_findings(row, previous=None):
    """Check only explicit intervals, allowing unknown time, parallel scenes and flashbacks."""
    model = row.get('timeline')
    prior = (previous or {}).get('timeline') or {}
    active = ('open', 'extended', 'delegated')
    if model is None:
        return ([{'criterion': 'timeline', 'severity': 'quality', 'repair_scope': 'outline',
                  'target_chapter': row.get('chapter'), 'reason': '前场仍有明确未结期限，本章不能省略其承接。'}]
                if any(item['status'] in active for item in prior.get('deadlines', [])) else [])
    require(isinstance(model, dict) and text(model.get('scene_id'))
            and model.get('relation') in ('continues', 'after', 'parallel', 'flashback'),
            'timeline', 'timeline须给稳定scene_id与continues/after/parallel/flashback关系。')

    def interval(value):
        require(isinstance(value, list) and len(value) == 2 and all(type(n) is int for n in value)
                and value[0] <= value[1], 'timeline', '已知时间须为有序整数分钟区间；未知时省略。')
        return value

    start = interval(model['start']) if 'start' in model else None
    end = interval(model['end']) if 'end' in model else None
    baseline = interval(prior['end']) if prior.get('end') else start
    issues = []

    def issue(reason):
        issues.append({'criterion': 'timeline', 'severity': 'quality', 'repair_scope': 'outline',
                       'target_chapter': row.get('chapter'), 'reason': reason})

    if start and end:
        if end[1] < start[0]:
            issue('场景结束早于开始。')
    if baseline and end:
        expected = (row.get('clock') or {}).get('advance_days')
        if type(expected) is int and model['relation'] not in ('parallel', 'flashback'):
            low, high = end[0] // 1440 - baseline[1] // 1440, end[1] // 1440 - baseline[0] // 1440
            if not low <= expected <= high:
                issue('累计天数增量不可能由本章明确时间区间产生。')
    if model['relation'] == 'continues' and prior:
        if model['scene_id'] != prior.get('scene_id'):
            issue('同场承接更换了场景身份。')
        if start and prior.get('end') and start[1] < interval(prior['end'])[0]:
            issue('同场承接退回已结束动作之前，且未声明补叙。')
    if model['relation'] == 'after' and start and prior.get('end') and start[1] < interval(prior['end'])[0]:
        issue('后续场景早于前场结束。')
    deadlines = model.get('deadlines', [])
    require(isinstance(deadlines, list), 'timeline', 'deadlines须为列表。')
    identifiers = set()
    for deadline in deadlines:
        require(isinstance(deadline, dict) and text(deadline.get('id')) and deadline.get('status') in
                ('open', 'fulfilled', 'failed', 'extended', 'abandoned', 'delegated'),
                'timeline', '期限须有稳定id及完成/失约/延期等状态。')
        require(deadline['id'] not in identifiers, 'timeline', '同一场景期限id不能重复。')
        identifiers.add(deadline['id'])
        due = interval(deadline.get('due'))
        if end and end[0] > due[1] and deadline['status'] in active:
            issue('场景已越过明确期限，仍把期限标为未到期。')
        if deadline['status'] != 'open':
            require(text(deadline.get('resolution_event')), 'timeline', '期限变更须给故事内事件，不靠新任务覆盖。')
    if model['relation'] not in ('parallel', 'flashback'):
        current = {item['id']: item for item in deadlines}
        for deadline in prior.get('deadlines', []):
            if deadline['status'] not in active:
                continue
            continued = current.get(deadline['id'])
            if continued is None:
                issue('前场明确未结期限从后续场景中消失，须保留或给解决事件。')
            elif continued['due'] != deadline['due'] and continued['status'] != 'extended':
                issue('明确期限改变却没有延期事件。')
    return issues
