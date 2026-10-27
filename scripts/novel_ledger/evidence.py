"""Validate exact quotations against frozen chapter values. No state or adapter access."""
from __future__ import annotations

from .contracts import require, text


def registration(event, prose, chapter, *, aliases=()):
    """Bind a registration to its declared name/alias, never an arbitrary first character."""
    source = event.get('entity') if event.get('op') == 'entity' else event.get('place')
    names = ([source.get('name'), *(source.get('aliases') or [])] if isinstance(source, dict)
             else [event.get('alias')])
    names = [name for name in [*names, *aliases] if text(name)]
    ref = event.get('evidence')
    if ref is None:
        mentions = [(prose.find(name), name) for name in names if name in prose]
        require(bool(mentions), 'evidence', '首次登记须在正文出现名称或已登记别名，不能用无关文字作证。',
                {'names': names, 'recover': '正文落实该实体；若用称谓，先在章纲 aliases 声明，再交 introductions 引文。'})
        start, name = min(mentions)
        ref = {'chapter': chapter, 'quote': name, 'start': start}
    checked = evidence(ref, {chapter: prose})
    require(any(name in checked['quote'] for name in names), 'evidence',
            '登记引文必须包含该实体的名称或已登记别名，不能只引用同章无关句子。')
    return checked


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
