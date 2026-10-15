"""Revisable literary interpretations, separate from canon and future plans."""
from __future__ import annotations

import copy
from .contracts import digest, require, text

SCHEMA = 'novel-ledger.understanding/1'
KINDS = ('character', 'relationship', 'theme', 'voice')
STATUSES = ('tentative', 'supported', 'contested', 'retired')


def empty():
    return {'schema': SCHEMA, 'versions': []}


def update(memory, changes, sources, locate, actor):
    """An independent reader records an interpretation, not a new story fact."""
    require(isinstance(changes, list), 'understanding', 'understanding 须为数组，无新增理解时给空数组。')
    result = copy.deepcopy(memory or empty())
    seen = set()
    current = latest(result)
    for change in changes:
        fields = {'id', 'kind', 'claim', 'subjects', 'topics', 'status', 'reason',
                  'evidence', 'counterevidence', 'valid_from', 'valid_through'}
        require(isinstance(change, dict) and not set(change) - fields
                and text(change.get('id')) and change['id'] not in seen,
                'understanding', '理解记录须有唯一 id，字段按工作台协议填写。')
        seen.add(change['id'])
        require(change.get('kind') in KINDS and change.get('status') in STATUSES
                and text(change.get('claim')) and text(change.get('reason')),
                'understanding', '理解需要 kind/claim/status/reason；状态是编辑判断，不由证据数量计算。')
        for key in ('subjects', 'topics'):
            require(isinstance(change.get(key), list) and all(text(v) for v in change[key])
                    and len(change[key]) == len(set(change[key])), 'understanding', key + ' 须为不重复的 ID 数组。')
        prior = current.get(change['id'])
        require(not prior or prior['kind'] == change['kind'], 'understanding', '同一理解 id 不改变种类；不同解释使用不同 id。')
        start, end = change.get('valid_from', 1), change.get('valid_through')
        require(type(start) is int and start >= 1 and (end is None or type(end) is int and end >= start),
                'understanding', '适用范围使用正文章号 valid_from/valid_through，不表示故事发生时间。')
        row = copy.deepcopy(change)
        row.update(valid_from=start, valid_through=end, producer=actor,
                   version=1 + max((v['version'] for v in result['versions'] if v['id'] == change['id']), default=0))
        for key in ('evidence', 'counterevidence'):
            refs = change.get(key, [])
            require(isinstance(refs, list) and (refs or key == 'counterevidence'),
                    'understanding', '理解至少有一项原文 evidence；反证可为空。')
            row[key] = []
            for ref in refs:
                normalized = locate(ref, sources)
                require(normalized['chapter'] > 0, 'understanding', '理解证据须来自正文，不使用设计或自评。')
                row[key].append({**normalized, 'prose_hash': digest(sources[normalized['chapter']])})
        result['versions'].append(row)
    return result


def latest(memory, prose_hashes=None):
    """A revision may reuse only versions whose complete evidence still belongs to this text."""
    selected = {}
    for row in (memory or empty())['versions']:
        refs = row['evidence'] + row['counterevidence']
        if prose_hashes is None or all(prose_hashes.get(r['chapter']) == r['prose_hash'] for r in refs):
            selected[row['id']] = row
    return selected


def rebase(memory, prose_hashes):
    result = copy.deepcopy(memory or empty())
    # Invalidated versions remain in immutable parent documents/branch snapshots.
    result['versions'] = [v for v in result['versions']
                          if all(prose_hashes.get(r['chapter']) == r['prose_hash']
                                 for r in v['evidence'] + v['counterevidence'])]
    return result


def select(memory, participants, topics, chapter, refs=()):
    current = latest(memory)
    require(set(refs) <= set(current), 'understanding_reference', '引用的作品理解不在当前版本中。',
            {'missing': sorted(set(refs) - set(current))})
    people, topics = set(participants), set(topics)
    return {key: copy.deepcopy(row) for key, row in current.items()
            if key in refs or row['status'] != 'retired' and row['valid_from'] <= chapter
            and (row['valid_through'] is None or chapter <= row['valid_through'])
            and (people.intersection(row['subjects']) or topics.intersection(row['topics'])
                 or not row['subjects'] and not row['topics'])}
