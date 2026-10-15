"""Conservative, evidence-addressed revision propagation over accepted chapter dependencies."""
from __future__ import annotations

from .contracts import digest, dump, require
from . import story_memory


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
        elif op != 'pace':
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
    origin = next(row for row in chapters if row['n'] == first)
    scene_ids = {s['id'] for s in origin['plan'].get('scenes', [])}
    require(all(isinstance(s, str) for s in change.get('scenes', []))
            and set(change.get('scenes', [])) <= scene_ids, 'revision_impact', '变更场景必须来自修订起章的准确计划。')
    affected = set(change.get('scenes') or scene_ids)
    decisions = [{'chapter': first, 'reason': '作者指定的修订起点。'}]
    fallback = False
    if change['mode'] == 'semantic':
        original_writes = writes(origin['events'])
        # Existing writes cannot describe newly introduced semantics without a change declaration.
        fallback = not touched or original_writes is None
        touched = touched or original_writes or set()
    pending = []
    for row in chapters:
        if row['n'] <= first or change['mode'] != 'semantic':
            continue
        plan = row['plan']
        unknown = plan.get('dependency_coverage') != 'complete'
        links = {s for scene in plan.get('scenes', []) for s in scene.get('depends_on', [])}
        matched = bool(story_memory.reads(plan).intersection(touched) or links.intersection(affected))
        if row['n'] <= forced_last or fallback or unknown or matched:
            reason = ('作者明确扩大修改区间。' if row['n'] <= forced_last else
                      '依赖声明不完整，保守扩大至后续章节。' if fallback or unknown else '读取了受影响事实或依赖受影响场景。')
            # Revisions execute a continuous interval. A gap chapter is rewritten too, so its
            # outputs and scene links must propagate before assessing the remaining suffix.
            for rewritten in pending + [row]:
                decisions.append({'chapter': rewritten['n'], 'reason': reason if rewritten is row else '处于连续修订区间。'})
                affected.update(s['id'] for s in rewritten['plan'].get('scenes', []))
                output = writes(rewritten['events'])
                fallback = fallback or rewritten['plan'].get('dependency_coverage') != 'complete' or output is None
                touched.update(output or set())
            pending = []
        else:
            pending.append(row)
    if change['mode'] != 'semantic':
        for row in chapters:
            if first < row['n'] <= forced_last:
                decisions.append({'chapter': row['n'], 'reason': '作者明确扩大修改区间。'})
                affected.update(s['id'] for s in row['plan'].get('scenes', []))
    last = decisions[-1]['chapter']
    actions = []
    reading_scenes = set(affected)
    reading_conservative = False
    for row in chapters:
        if row['n'] < first:
            continue
        reading_complete = story_memory.reading_enabled(row['plan']) and row['plan'].get('reading_coverage') == 'complete'
        if row['n'] <= last:
            action = 'local' if change['mode'] != 'semantic' and row['n'] == first else 'rewrite'
            reason = '修改指定正文；合成后仍须完整独立章审。' if action == 'local' else '事实或因果影响进入连续重写区间。'
        elif reading and (not reading_complete
                          or story_memory.reading_refs(row['plan']).intersection(reading)
                          or any(reading_scenes.intersection(s.get('depends_on', []))
                                 for s in row['plan'].get('scenes', []))):
            action, reason = 'review', '阅读关联受影响或尚未完整声明，先独立首读；发现实质问题再修改。'
            reading_conservative = reading_conservative or not reading_complete
        else:
            action, reason = 'keep', '未发现需重写的依赖；保留正文并重放事实，最终仍核验修订接缝。'
        actions.append({'chapter': row['n'], 'action': action, 'reason': reason})
        if action != 'keep':
            reading_scenes.update(s['id'] for s in row['plan'].get('scenes', []))
    return {'schema': 'novel-ledger.revision-impact/2', 'mode': change['mode'],
            'first': first, 'last': last, 'affected_chapters': decisions,
            'affected_scenes': sorted(affected), 'conservative': fallback or reading_conservative,
            'reading_conservative': reading_conservative,
            'rewrite_chapters': list(range(first, last + 1)),
            'chapter_actions': actions,
            'reading_changes': [{'kind': c['kind'], 'key': c['key']} for c in change.get('reading_changes', [])],
            'source_hash': digest([{k: r[k] for k in ('n', 'chain', 'plan_hash', 'events_hash')} for r in chapters]),
            'sources': [{'chapter': r['n'], 'chain': r['chain'], 'plan_hash': r['plan_hash'],
                         'events_hash': r['events_hash']} for r in chapters if r['n'] >= first],
            'note': '范围建议不免除独立章审、后缀事实重放及修订范围复核；表达修订还须保持事实投影不变。'}
