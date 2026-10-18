"""Mechanical style proxies: the checkable half of "write in the contract's voice".

The author's decision for v2.1: literary quality is carried by style, not by a reviewer. Design
declares the spec — a volume's `style.trend` and a chapter's `style{pov,rhythm,dialogue_ratio}` —
and the engine computes these proxies for free when a chapter is submitted, so a chapter that
drifts away from the voice the author anchored is caught and repaired like any other drift.

What these numbers prove is *consistency*: sentence and paragraph shape, how much of the text is
dialogue, how repetitive a chapter is inside itself, and whether the narration keeps the person the
contract chose. They cannot prove a chapter is good — a page can match every number and still be
dull, and nothing here judges whether a character is believable. That residual is the author's to
read, or to measure offline with `scripts/quality_eval.py`.
"""
from __future__ import annotations

import re

from .contracts import han_count, text

# Sentence terminators, and the quote families a Chinese manuscript actually uses. A quote family
# is a pair, so an unclosed quote simply yields no dialogue rather than half a chapter of it.
SENTENCE_END = '。！？…!?；;'
QUOTE_PAIRS = (('“', '”'), ('「', '」'), ('『', '』'), ('‘', '’'))
# Default tolerances: relative deviation from the anchor for the shape metrics, an absolute share
# for in-chapter repetition, and 1 meaning "the narration person must match what was declared".
# The repetition share is calibrated, not guessed: ordinary Chinese prose in this repository measures
# 0.043~0.086 (README 0.057, references/narrative.md 0.083, results.md 0.086), while a template that
# repeats one clause measures 0.87. 0.12 sits above real writing and far below the pathological case.
DEFAULT_WINDOW = {'sentence': 0.35, 'paragraph': 0.35, 'dialogue': 0.40, 'repetition': 0.12, 'person': 1}
# Below these floors a sample is too short for a metric to mean anything, and comparing it would
# only produce noise findings on chapters that the word budget already governs. MIN_HAN is the one
# that binds in practice (a sample that passes it always has more than MIN_NGRAMS four-grams); the
# n-gram floor stays as the guard for the case where the prose floor is loosened.
MIN_HAN = 40
MIN_SENTENCES = 3
MIN_NGRAMS = 20
NGRAM = 4
SHORT_SENTENCE = 10
FIRST_PERSON = ('我', '咱', '俺')
THIRD_PERSON = ('他', '她', '它')
HAN = re.compile(r'[\u3400-\u4dbf\u4e00-\u9fff\U00020000-\U0003134f]+')


def _iter_paragraphs(prose):
    for block in str(prose or '').splitlines():
        block = block.strip()
        if block:
            yield block


def _iter_sentences(prose):
    for block in _iter_paragraphs(prose):
        start = 0
        for index, char in enumerate(block):
            if char in SENTENCE_END:
                candidate = block[start:index + 1].strip()
                if candidate:
                    yield candidate
                start = index + 1
        tail = block[start:].strip()
        if tail:
            yield tail


def _dialogue_spans(prose):
    """The text inside quotes, per paragraph: narration is what is left of it."""
    spans, narration = [], []
    for block in _iter_paragraphs(prose):
        rest, cursor = [], 0
        for opening, closing in QUOTE_PAIRS:
            while True:
                start = block.find(opening, cursor)
                if start < 0:
                    break
                end = block.find(closing, start + 1)
                if end < 0:
                    break
                spans.append(block[start + 1:end])
                rest.append(block[cursor:start])
                cursor = end + 1
        rest.append(block[cursor:])
        narration.append(''.join(rest))
    return ' '.join(spans), ' '.join(narration)


def metrics(prose):
    """The proxy metrics of one prose sample; every value is derived, never stored."""
    sentences = [han_count(item) for item in _iter_sentences(prose)]
    paragraphs = [han_count(item) for item in _iter_paragraphs(prose)]
    dialogue, narration = _dialogue_spans(prose)
    total = han_count(prose)
    tokens = HAN.findall(narration + dialogue)
    body = ''.join(tokens)
    grams = [body[i:i + NGRAM] for i in range(max(0, len(body) - NGRAM + 1))]
    repeated = 0 if not grams else (len(grams) - len(set(grams))) / len(grams)
    return {
        'han': total,
        'sentences': len(sentences),
        'sentence_mean': round(sum(sentences) / len(sentences), 3) if sentences else 0.0,
        'sentence_short_share': (round(sum(1 for n in sentences if n <= SHORT_SENTENCE) / len(sentences), 3)
                                 if sentences else 0.0),
        'paragraph_mean': round(sum(paragraphs) / len(paragraphs), 3) if paragraphs else 0.0,
        'paragraph_max': max(paragraphs) if paragraphs else 0,
        'dialogue_share': round(han_count(dialogue) / total, 3) if total else 0.0,
        # Always a finite number: whether a value is *judged* depends on the sample being long
        # enough, and that gate lives in `compare` (it needs `repetition_grams`).
        'repetition_share': round(repeated, 4),
        'repetition_grams': len(grams),
        'person': _person(narration),
    }


def _person(narration):
    """Which person the narration keeps, from its markers; 'unknown' when it shows neither."""
    first = sum(narration.count(marker) for marker in FIRST_PERSON)
    third = sum(narration.count(marker) for marker in THIRD_PERSON)
    if first and third:
        return 'mixed'
    if first:
        return 'first'
    if third:
        return 'third'
    return 'unknown'


def window_of(contract):
    """This contract's tolerances, defaults filled in for anything it does not state."""
    raw = (contract or {}).get('style_window')
    merged = dict(DEFAULT_WINDOW)
    if isinstance(raw, dict):
        for key, value in raw.items():
            if key in DEFAULT_WINDOW and isinstance(value, (int, float)) and value >= 0:
                merged[key] = float(value)
    return merged


def merged_window(contract, volume_style=None):
    """The contract's tolerances with a volume's own `style.window` applied on top.

    A volume may tighten or loosen one metric ("this volume leans on dialogue"), and that decision
    belongs to the volume outline rather than to a global contract edit.
    """
    merged = window_of(contract)
    raw = (volume_style or {}).get('window') if isinstance(volume_style, dict) else None
    if isinstance(raw, dict):
        for key, value in raw.items():
            if key in DEFAULT_WINDOW and isinstance(value, (int, float)) and value >= 0:
                merged[key] = float(value)
    return merged


def baseline(book):
    """The anchor sample's metrics: the chapter the author approved, or None before that."""
    anchor = (book or {}).get('style_anchor') or {}
    sample = anchor.get('sample')
    if not text(sample):
        return None
    measured = metrics(sample)
    return measured if measured['han'] >= MIN_HAN else None


def _finding(chapter, metric, expect, got, reason):
    return {'criterion': 'style_' + metric, 'severity': 'quality', 'target_chapter': chapter,
            'repair_scope': 'local', 'metric': metric, 'expect': expect, 'got': got, 'reason': reason}


def _declared_person(declared, contract):
    """The person a declaration asks for, or None when it does not name one."""
    sources = [str((declared or {}).get('pov') or ''), str((contract or {}).get('pov') or '')]
    for source in sources:
        if '第一人称' in source:
            return 'first'
        if '第三人称' in source:
            return 'third'
    return None


def _relative(got, base):
    if not base:
        return 0.0
    return abs(got - base) / abs(base)


def _same_order(left, right):
    """Whether two samples are big enough to compare shape with each other (within 3x either way)."""
    left, right = left or 0, right or 0
    if not left or not right:
        return False
    ratio = left / right
    return 1 / 3 <= ratio <= 3


def compare(prose, declared, anchor, window, chapter=0, contract=None):
    """Findings for one chapter against the anchor sample and its own declared style points.

    `anchor` is the baseline metrics (or None), `window` the tolerances, `declared` this chapter's
    `style` row. Rows without an anchor keep the two checks that need no baseline — in-chapter
    repetition and the narration person — instead of comparing against nothing.
    """
    measured = metrics(prose)
    if measured['han'] < MIN_HAN:
        return []
    limits = window or DEFAULT_WINDOW
    declared = declared if isinstance(declared, dict) else {}
    findings = []
    # Shape metrics are only comparable between samples of the same order of magnitude: a short
    # stub cannot say anything about a full chapter's rhythm, and measuring one against the other
    # produces findings that are artefacts of the sample rather than of the writing.
    comparable = bool(anchor) and _same_order(measured.get('han'), anchor.get('han'))
    if comparable and measured['sentences'] >= MIN_SENTENCES:
        pairs = (('sentence_mean', 'sentence', '句均长'), ('sentence_short_share', 'sentence', '短句占比'),
                 ('paragraph_mean', 'paragraph', '段均长'), ('paragraph_max', 'paragraph', '最长段'))
        for metric, family, label in pairs:
            base = anchor.get(metric) or 0
            if not base:
                continue
            if _relative(measured[metric], base) > limits.get(family, DEFAULT_WINDOW[family]):
                findings.append(_finding(chapter, metric, base, measured[metric],
                                         label + '相对首章定调偏离超过容差，正文的语感走了形。'))
    target = declared.get('dialogue_ratio')
    if isinstance(target, (int, float)) and 0 < float(target) <= 1:
        if _relative(measured['dialogue_share'], float(target)) > limits.get('dialogue', DEFAULT_WINDOW['dialogue']):
            findings.append(_finding(chapter, 'dialogue_ratio', float(target), measured['dialogue_share'],
                                     '对白占比与章纲声明不符，本章的推进方式变了。'))
    elif anchor and anchor.get('dialogue_share') and _same_order(measured.get('han'), anchor.get('han')):
        base = anchor['dialogue_share']
        if _relative(measured['dialogue_share'], base) > limits.get('dialogue', DEFAULT_WINDOW['dialogue']):
            findings.append(_finding(chapter, 'dialogue_share', base, measured['dialogue_share'],
                                     '对白占比相对首章定调偏离超过容差。'))
    if measured.get('repetition_grams', 0) >= MIN_NGRAMS:
        repetition = measured['repetition_share']
        if repetition > limits.get('repetition', DEFAULT_WINDOW['repetition']):
            findings.append(_finding(chapter, 'repetition', limits.get('repetition', DEFAULT_WINDOW['repetition']),
                                     repetition, '本章内部四字重复率过高：同一串话在章内反复出现。'
                                                 '把重复的句子改写；若这是本卷有意的复沓，由作者调宽 style_window.repetition。'))
    expected_person = _declared_person(declared, contract)
    if expected_person and measured['person'] not in ('unknown', expected_person):
        findings.append(_finding(chapter, 'person', expected_person, measured['person'],
                                 '叙述人称与章纲/约定的视角不一致。'))
    return findings
