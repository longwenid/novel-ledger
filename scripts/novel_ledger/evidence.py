"""Validate exact quotations against frozen chapter values. No state or adapter access."""
from __future__ import annotations

from .contracts import require, text


def evidence(ref, sources):
    require(isinstance(ref, dict) and type(ref.get('chapter')) is int and text(ref.get('quote')), 'evidence', '证据需要 chapter/quote。',
            {'expect': '单个对象 {chapter:int, quote:str, start?:int}；checks/obligations/coverage 的 evidence 是该对象的数组，findings/challenge/events 的 evidence 是单个对象。',
             'frozen_chapters': sorted(sources)})
    chapter = ref['chapter']
    require(chapter in sources, 'evidence_scope', '引文不在冻结正文范围内。', {'frozen_chapters': sorted(sources)})
    prose, quote = sources[chapter], ref['quote']
    start = ref.get('start')
    if start is None:
        start = prose.find(quote)
        require(start >= 0 and prose.find(quote, start + 1) < 0, 'evidence', '引文缺失或多次出现，请提供准确 start。')
    require(type(start) is int and start >= 0 and prose[start:start + len(quote)] == quote,
            'evidence', '引文与冻结正文不一致。')
    return {'chapter': chapter, 'start': start, 'quote': quote}
