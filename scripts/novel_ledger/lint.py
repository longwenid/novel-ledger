"""Mechanical prose defects the engine judges itself, before any reviewer is paid.

Three defect classes were each found only by an independent review session on a real run, costing
a repair round plus a full re-review every time: a chapter that reused an earlier chapter's action
group verbatim, a chapter whose dialogue quotes used the other quote family from the rest of the
book, and a leftover foreign word in otherwise-Chinese prose. All three are arithmetic on text, so
they belong at submit time — and therefore at preflight time, which runs the same validation —
rather than in a reviewer's judgement. rework.md 的设计原则 1：能机械判定的，不交给独立会话。
"""
from __future__ import annotations

import re
from .contracts import require

# A window of this many consecutive identical characters shared with a committed chapter is a copy,
# not a coincidence: Chinese prose that is not quoting the earlier chapter verbatim does not repeat
# 25 characters in a row. The real case was a whole action group (~40 characters) reused as-is.
DUPLICATE_GRAM = 25
# How many nearest committed chapters are compared. Verbatim reuse in practice is local (adjacent
# chapters recycle action groups); older echoes stay covered by the cross-chapter scope reviews,
# so this bounds the cost of the check without pretending to be the whole book's memory.
DUPLICATE_WINDOW = 8
DUPLICATE_LIMIT = 3
# A long template with many changed numbers is stronger evidence than a shared
# sentence. Short numerical examples and ordinary dates do not trigger this path.
NUMERIC_TEMPLATE_SPAN = 120
NUMERIC_TEMPLATE_RUNS = 8
# Fewer dialogue quotes than this cannot establish a family; a stray mark is not a style breach.
STYLE_MIN_QUOTES = 3
# A run of this many Latin letters is foreign residue in an otherwise-Chinese voice. Single letters
# (variables, grades) are left to the author's judgement.
LATIN_MIN = 2

_CORNER = ('「', '『')
_WESTERN = ('"', '“', '”')
_LATIN_RUN = re.compile('[A-Za-z]{%d,}' % LATIN_MIN)
_NUMBER_RUN = re.compile(r'\d+')


def _numeric_view(prose):
    """Normalize digit runs while keeping offsets into the unmodified source."""
    parts, starts, ends, cursor = [], [], [], 0
    for match in _NUMBER_RUN.finditer(prose):
        parts.append(prose[cursor:match.start()])
        starts.extend(range(cursor, match.start()))
        ends.extend(range(cursor + 1, match.start() + 1))
        parts.append('#')
        starts.append(match.start())
        ends.append(match.end())
        cursor = match.end()
    parts.append(prose[cursor:])
    starts.extend(range(cursor, len(prose)))
    ends.extend(range(cursor + 1, len(prose) + 1))
    return ''.join(parts), starts, ends


def _runs(prose, size):
    return [prose[i:i + size] for i in range(max(0, len(prose) - size + 1))]


def _finding(criterion, chapter, reason, **extra):
    row = {'criterion': criterion, 'severity': 'quality', 'target_chapter': chapter,
           'repair_scope': 'local', 'reason': reason}
    row.update(extra)
    return row


def _shared_span(prose, prior_text, size):
    """The longest verbatim span the two texts share, found from one size-gram hit and extended.

    Greedy extension on string search stays cheap at chapter sizes (a few thousand characters) and
    returns a readable quote the repair can name, instead of an arbitrary fixed-length window.
    """
    seen = set(_runs(prior_text, size))
    hit = next((run for run in _runs(prose, size) if run in seen), None)
    if hit is None:
        return None
    start = prose.find(hit)
    left, right = start, start + len(hit)
    while left > 0 and prior_text.find(prose[left - 1:right]) >= 0:
        left -= 1
    while right < len(prose) and prior_text.find(prose[left:right + 1]) >= 0:
        right += 1
    return left, right


def cross_chapter_duplicates(prose, priors, chapter, size=DUPLICATE_GRAM, limit=DUPLICATE_LIMIT):
    """Verbatim spans this draft shares with already committed chapters.

    priors is a nearest-first iterable of (chapter, text). One finding per offending prior chapter,
    carrying the shared span as the quote, so the repair rewrites exactly that span.
    """
    findings = []
    numeric = None
    for prior_chapter, prior_text in priors:
        if not prior_text:
            continue
        span = _shared_span(prose, prior_text, size)
        if span is None:
            if numeric is None:
                numeric = _numeric_view(prose)
            normalized, starts, ends = numeric
            prior_normalized, _, _ = _numeric_view(prior_text)
            repeated = _shared_span(normalized, prior_normalized, NUMERIC_TEMPLATE_SPAN)
            if repeated is None or normalized[repeated[0]:repeated[1]].count('#') < NUMERIC_TEMPLATE_RUNS:
                continue
            left, right = starts[repeated[0]], ends[repeated[1] - 1]
            findings.append(_finding(
                'repetition', chapter,
                '与第 %d 章存在仅数字变化的长段落模板；需重写本章实际行动、阻力与后果，不能靠章号或数字扰动消除匹配。'
                % prior_chapter, duplicate_of=prior_chapter, quote=prose[left:right],
                length=right - left, normalization='numeric'))
            if len(findings) >= limit:
                break
            continue
        left, right = span
        findings.append(_finding(
            'repetition', chapter,
            '与已核验的第 %d 章逐字重复 %d 字（「%s」）：同一动作组或句段不能跨章复用，'
            '把这段换成只属于本章的写法；确需呼应前文时改写而不是照抄。'
            % (prior_chapter, right - left, prose[left:min(right, left + 60)]),
            duplicate_of=prior_chapter, quote=prose[left:right], length=right - left))
        if len(findings) >= limit:
            break
    return findings


def _quote_counts(prose):
    """Count only top-level, closed quotations; nested quotation is a valid use of two families."""
    counts = {'corner': 0, 'western': 0}
    pairs = {'「': '」', '『': '』', '“': '”', '"': '"', '‘': '’'}
    for block in prose.splitlines():
        start = 0
        while start < len(block):
            opening = block[start]
            closing = pairs.get(opening)
            if closing is None:
                start += 1
                continue
            stack, end = [closing], start + 1
            while end < len(block) and stack:
                char = block[end]
                if char == stack[-1]:
                    stack.pop()
                elif char in pairs:
                    stack.append(pairs[char])
                end += 1
            if stack:
                start += 1
                continue
            if opening in _CORNER:
                counts['corner'] += 1
            elif opening in _WESTERN:
                counts['western'] += 2
            start = end
    return counts


def style_findings(prose, priors, chapter, minimum=STYLE_MIN_QUOTES):
    """Dialogue-quote family consistency: within the chapter, and against the committed book.

    A chapter that mixes both families internally, or that switches to the family the book does not
    use, is a page-visible format drift the reader cannot unsee — measured on a real run where one
    chapter's quotes and title marks broke from the other chapters' convention.
    """
    own = _quote_counts(prose)
    if sum(own.values()) < minimum:
        return []
    findings = []
    if min(own.values()) >= minimum:
        findings.append(_finding(
            'language', chapter,
            '本章同时使用两套对白引号（直角 %d 处、西文 %d 处）；统一为其中一套，'
            '并与全书其余章节一致。' % (own['corner'], own['western']),
            quote_families=own))
    else:
        book = {'corner': 0, 'western': 0}
        for _, text in priors:
            counts = _quote_counts(text)
            book['corner'] += counts['corner']
            book['western'] += counts['western']
        own_family = max(own, key=own.get)
        book_family = max(book, key=book.get)
        if max(book.values()) >= minimum and own_family != book_family:
            findings.append(_finding(
                'language', chapter,
                '全书已核验章节使用%s引号，本章用的是另一套（直角 %d 处、西文 %d 处）；'
                '按全书既定体例统一。' % ('直角' if book_family == 'corner' else '西文',
                                          own['corner'], own['western']),
                quote_families=own, book_families=book))
    return findings


def latin_findings(prose, chapter, allowed=()):
    """Runs of Latin letters in an otherwise-Chinese voice; measured as a stray foreign word that
    survived into a committed chapter and had to be repaired through a full revision branch."""
    runs = [run for run in _LATIN_RUN.findall(prose) if run not in set(allowed)]
    if not runs:
        return []
    first = runs[0]
    at = prose.find(first)
    return [_finding(
        'language', chapter,
        '正文出现西文残留：%s；全书声线为中文，把这几处改为中文表达（专名按作者约定处理）。'
        % '、'.join(runs[:5]),
        matches=runs[:10], quote=prose[max(0, at - 10):at + len(first) + 10])]


def draft_findings(prose, priors, chapter, allowed_latin=()):
    """Every mechanical finding for a freshly drafted or repaired chapter, ready for route_repair.

    priors is nearest-first (chapter, text) of committed chapters, bounded by the caller; the
    findings use the reader check names (`repetition`, `language`) so they enter the same
    obligations and self-check rubric the reviewer and the producer brief already share.
    """
    require(isinstance(prose, str) and type(chapter) is int, 'lint', '机械校验需要正文文本与章号。')
    return (cross_chapter_duplicates(prose, priors, chapter)
            + style_findings(prose, priors, chapter)
            + latin_findings(prose, chapter, allowed_latin))
