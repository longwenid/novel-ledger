"""Conservative, evidence-addressed revision propagation over accepted chapter dependencies."""
from __future__ import annotations

from .contracts import digest, dump, require
from . import story_memory

SCHEMA = 'novel-ledger.revision-impact/3'


def writes(events):
    result = set()
    for event in events:
        op = event['op']
        if op == 'state':
            result.add(('facts', event['entity'] + ':' + event['key']))
        elif op == 'knowledge':
            result.add(('knowledge', event['entity'] + ':' + event['topic']))
        elif op == 'relation':
            result.add(('relations', event['from'] + '>' + event['to'] + ':' + event['key']))
        elif op == 'resource':
            result.update(('resources', dump([holder, event['asset'], event['unit']]))
                          for holder in (event['from'], event['to']) if holder is not None)
        elif op == 'clock':
            result.add(('clock_threads', event['thread']) if event.get('thread') else ('clock', 'main'))
        elif op in ('story_node', 'story_thread', 'reader_knowledge', 'hook', 'historical_assertion'):
            kind, key = {'story_node': ('node', 'node'), 'story_thread': ('thread_progress', 'thread'),
                         'reader_knowledge': ('reader_knowledge', 'topic'), 'hook': ('hooks', 'id'),
                         'historical_assertion': ('historical_assertions', 'id')}[op]
            result.add((kind, event[key]))
            if op == 'story_node':
                result.add(('thread_progress', event['line']))
        elif op in ('move', 'placement', 'travel'):
            # Custody chains and arrival times have derived writes not recoverable from the
            # event alone. Until those dependencies are modelled, retain the whole suffix.
            return None
        elif op in ('alias', 'character_current', 'character_development'):
            kind = {'alias': 'entities', 'character_current': 'character_current',
                    'character_development': 'developments'}[op]
            result.add((kind, event['entity']))
        elif op == 'entity':
            result.add(('entities', event['entity']['id']))
        elif op == 'place':
            result.add(('places', event['place']['id']))
        else:
            # An unmodelled event may affect arbitrary later inputs. Never infer independence.
            return None
    return result


def analyze(chapters, first, change=None, through=None):
    require(type(first) is int and first >= 1 and chapters and any(row['n'] == first for row in chapters),
            'revision', '修订起点必须已有正式章节。')
    forced_last = first if through is None else through
    require(type(forced_last) is int and first <= forced_last <= chapters[-1]['n'],
            'revision', '采用的修订终点须在起章与最后一章之间。')
    change = {'mode': 'semantic', 'changes': []} if change is None else change
    require(isinstance(change, dict) and set(change) <= {'mode', 'changes', 'scenes', 'reading_changes'}
            and change.get('mode') in ('expression', 'reading', 'semantic') and isinstance(change.get('changes', []), list)
            and isinstance(change.get('scenes', []), list) and isinstance(change.get('reading_changes', []), list), 'revision_impact',
            '变更说明为 {mode:expression|reading|semantic, changes:[{kind,key}], scenes:[场景ID], reading_changes:[{kind,key}]}。')
    touched = {story_memory.coordinate(c) for c in change.get('changes', [])}
    reading = {story_memory.reading_coordinate(c) for c in change.get('reading_changes', [])}
    require(change['mode'] == 'semantic' or not touched, 'revision_impact', '表达或阅读修订不得同时声明事实变更。')
    require(change['mode'] != 'reading' or reading, 'revision_impact', '阅读修订须声明 reading_changes。')
    for row in chapters:
        story_memory.require_current(row['plan'])
    origin = next(row for row in chapters if row['n'] == first)
    scene_ids = {s['id'] for s in origin['plan'].get('scenes', [])}
    require(all(isinstance(s, str) for s in change.get('scenes', []))
            and set(change.get('scenes', [])) <= scene_ids, 'revision_impact', '变更场景必须来自修订起章的准确计划。')
    affected = set(change.get('scenes') or scene_ids)
    decisions = [{'chapter': first, 'reason': '作者指定的修订起点。'}]
    fallback, initial_cause = False, None
    if change['mode'] == 'semantic':
        original_writes = writes(origin['events'])
        # Existing writes cannot describe newly introduced semantics without a change declaration.
        fallback = not touched or original_writes is None
        initial_cause = ('unexplained_events' if original_writes is None else
                         'undeclared_dependencies' if not touched else None)
        touched = touched or original_writes or set()
    pending, causes = [], []
    semantic = change['mode'] == 'semantic'
    reading_conservative = False
    for row in chapters:
        if row['n'] <= first:
            continue
        plan = row['plan']
        unknown = plan.get('dependency_coverage') != 'complete'
        links = {s for scene in plan.get('scenes', []) for s in scene.get('depends_on', [])}
        matched = bool(story_memory.reads(plan).intersection(touched) or links.intersection(affected))
        reading_unknown = plan.get('reading_coverage') != 'complete'
        reading_matched = bool(reading and (reading_unknown
                               or story_memory.reading_refs(plan).intersection(reading)
                               or links.intersection(affected)))
        if row['n'] <= forced_last or (semantic and (fallback or unknown or matched)) or reading_matched:
            if row['n'] <= forced_last:
                reason, cause = '作者明确扩大修改区间。', None
            elif semantic and writes(row['events']) is None:
                reason, cause = '事件无法解释，保守扩大至后续章节。', 'unexplained_events'
            elif semantic and unknown:
                reason, cause = '依赖声明不完整，保守扩大至后续章节。', 'undeclared_dependencies'
            elif semantic and fallback:
                cause = initial_cause or 'undeclared_dependencies'
                reason = ('事件无法解释，保守扩大至后续章节。' if cause == 'unexplained_events'
                          else '依赖声明不完整，保守扩大至后续章节。')
            elif reading_matched and reading_unknown:
                reason, cause = '阅读关联声明不完整，保守纳入连续重写区间。', 'undeclared_dependencies'
            else:
                reason, cause = '读取了受影响事实、阅读关联或依赖受影响场景。', 'declared_dependency'
            reading_conservative = reading_conservative or bool(reading and reading_unknown)
            if cause and cause != 'declared_dependency' and not causes:
                causes.append(cause)
            # Every intervening chapter is rewritten, so its outputs and scene links also
            # propagate before the next chapter is assessed. The final end bounds execution.
            for rewritten in pending + [row]:
                decisions.append({'chapter': rewritten['n'], 'reason': reason if rewritten is row else '处于连续修订区间。'})
                affected.update(s['id'] for s in rewritten['plan'].get('scenes', []))
                if semantic:
                    output = writes(rewritten['events'])
                    fallback = fallback or rewritten['plan'].get('dependency_coverage') != 'complete' or output is None
                    touched.update(output or set())
            pending = []
        else:
            pending.append(row)
    last = decisions[-1]['chapter']
    actions = []
    for row in chapters:
        if row['n'] < first:
            continue
        if row['n'] <= last:
            action = 'local' if not semantic and row['n'] == first else 'rewrite'
            reason = '修改指定正文；合成后重新执行完整机械核算。' if action == 'local' else '受影响章纲重排后重写并重新核算。'
        else:
            action, reason = 'keep', '未发现需重写的依赖；保留正文并核对显式前态、重放事实。'
        actions.append({'chapter': row['n'], 'action': action, 'reason': reason})
    return {'schema': SCHEMA, 'mode': change['mode'],
            'first': first, 'last': last, 'affected_chapters': decisions,
            'affected_scenes': sorted(affected), 'conservative': fallback or reading_conservative,
            'coverage': ('complete' if all(row['plan'].get('dependency_coverage') == 'complete'
                                           for row in chapters if row['n'] > first) else 'partial'),
            'expansion': ({'reason': causes[0], 'first': first, 'through': last,
                           'chapters': last - first + 1} if causes else None),
            'reading_conservative': reading_conservative,
            'rewrite_chapters': list(range(first, last + 1)),
            'chapter_actions': actions,
            'reading_changes': [{'kind': c['kind'], 'key': c['key']} for c in change.get('reading_changes', [])],
            'source_hash': digest([{k: r[k] for k in ('n', 'chain', 'plan_hash', 'events_hash')} for r in chapters]),
            'sources': [{'chapter': r['n'], 'chain': r['chain'], 'plan_hash': r['plan_hash'],
                         'events_hash': r['events_hash']} for r in chapters if r['n'] >= first],
            'note': '范围建议不免除章纲重排、正文机械核算及后缀事实重放；表达修订还须保持事实投影不变。'}
