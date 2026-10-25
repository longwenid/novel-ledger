"""Measure style without treating every change in chapter rhythm as a literary defect.

The default guard observes sentence, paragraph and unplanned dialogue-share differences from the
approved sample. An author may explicitly select strict checking of those numeric shape limits.
Chapter dialogue targets and high in-chapter repetition remain checkable in either mode.

Pronoun counts are observations in both modes: a first-person narrator can mention other people,
and third-person prose can render a character's interior words. These proxies cannot determine
narrative viewpoint or prove literary quality. The author, the declared style and the writer's
comparison with that style remain the sources for those judgements.
"""
from __future__ import annotations

import re

from .contracts import DEFAULTS, han_count, policy_default, profile_anchor, text

# Sentence terminators, and the quote families a Chinese manuscript actually uses. A quote family
# is a pair, so an unclosed quote simply yields no dialogue rather than half a chapter of it.
SENTENCE_END = '。！？…!?；;'
QUOTE_PAIRS = (('“', '”'), ('「', '」'), ('『', '』'), ('‘', '’'), ('"', '"'))
# Tolerances, metric floors and n-gram size all come from the one declaration in contracts.DEFAULTS:
# a duplicated default is how the same band ends up meaning two different things in two layers.
DEFAULT_WINDOW = policy_default('style_window')
MIN_HAN = DEFAULTS['style_floor_han']
MIN_SENTENCES = DEFAULTS['style_min_sentences']
MIN_NGRAMS = DEFAULTS['style_min_ngrams']
NGRAM = DEFAULTS['style_ngram']
SHORT_SENTENCE = DEFAULTS['style_short_sentence']
SAME_ORDER = DEFAULTS['style_same_order']
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
    pairs = dict(QUOTE_PAIRS)
    spans, narration = [], []
    for block in _iter_paragraphs(prose):
        rest, cursor, start = [], 0, 0
        while start < len(block):
            closing = pairs.get(block[start])
            if closing is None:
                start += 1
                continue
            # Scan in reading order, and count nested quotations only once as part of their
            # outer quotation. An unfinished quotation does not swallow the rest of a paragraph.
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
            spans.append(block[start + 1:end - 1])
            rest.append(block[cursor:start])
            cursor = start = end
        rest.append(block[cursor:])
        narration.append(''.join(rest))
    return ' '.join(spans), ' '.join(narration)


def metrics(prose):
    """The proxy metrics of one prose sample; every value is derived, never stored."""
    # Closing quotes and repeated terminators are punctuation, not zero-word sentences.
    sentences = [size for item in _iter_sentences(prose) for size in (han_count(item),) if size]
    paragraphs = [han_count(item) for item in _iter_paragraphs(prose)]
    dialogue, narration = _dialogue_spans(prose)
    total = han_count(prose)
    # Preserve the actual reading order: joining narration before dialogue invents n-grams at
    # boundaries that never existed in the prose, and loses the original ones around quotations.
    tokens = HAN.findall(str(prose or ''))
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
    """Inventory pronoun markers, without claiming they determine narrative viewpoint."""
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
    """The anchor sample's metrics, or the selected profile's declared anchor before any approval.

    A project never runs voiceless: without an approved pilot (or with one too short to
    measure) the shape comparison falls back to the anchor registered for the contract's
    style_profile (unknown or absent names mean the default profile), labeled `origin=default`
    so reports can tell a declared floor from an author-approved baseline. `approve` replaces
    it with the real measured sample."""
    anchor = (book or {}).get('style_anchor') or {}
    sample = anchor.get('sample')
    measured = metrics(sample) if text(sample) else None
    if measured and measured['han'] >= MIN_HAN:
        return measured
    return profile_anchor(((book or {}).get('contract') or {}).get('style_profile'))


def _finding(chapter, metric, expect, got, reason):
    return {'criterion': 'style_' + metric, 'severity': 'quality', 'target_chapter': chapter,
            'repair_scope': 'local', 'metric': metric, 'expect': expect, 'got': got, 'reason': reason}


def _observation(chapter, metric, expect, got, reason):
    return {'criterion': 'style_' + metric, 'target_chapter': chapter, 'metric': metric,
            'expect': expect, 'got': got, 'reason': reason}


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
        return 0.0 if not got else float('inf')
    return abs(got - base) / abs(base)


def _same_order(left, right):
    """Whether two samples are big enough to compare shape with each other (within Nx either way)."""
    left, right = left or 0, right or 0
    if not left or not right:
        return False
    ratio = left / right
    return 1 / SAME_ORDER <= ratio <= SAME_ORDER


def examine(prose, declared, anchor, window, chapter=0, contract=None):
    """Return measured metrics, nonbinding observations and actionable numeric findings.

    Only explicit strict guarding routes anchor-shape changes to findings. Viewpoint markers are
    always observations. Neither category substitutes for reading the author's actual style spec.
    """
    measured = metrics(prose)
    findings, observations = [], []
    report = {'metrics': measured, 'observations': observations, 'findings': findings}
    if measured['han'] < MIN_HAN:
        return report
    limits = window or DEFAULT_WINDOW
    declared = declared if isinstance(declared, dict) else {}
    strict = (contract or {}).get('style_guard', DEFAULTS['style_guard']) == 'strict'

    def shape_change(metric, expect, got, reason):
        if strict:
            findings.append(_finding(chapter, metric, expect, got, reason))
        else:
            observations.append(_observation(chapter, metric, expect, got, reason))

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
                shape_change(metric, base, measured[metric],
                             label + '相对首章样本的变化超过已设容差。')
    target = declared.get('dialogue_ratio')
    if type(target) in (int, float) and 0 <= float(target) <= 1:
        # A zero target must not lose a small amount of dialogue to the display metric's rounding.
        share = (han_count(_dialogue_spans(prose)[0]) / measured['han'] if target == 0
                 else measured['dialogue_share'])
        if _relative(share, float(target)) > limits.get('dialogue', DEFAULT_WINDOW['dialogue']):
            findings.append(_finding(chapter, 'dialogue_ratio', float(target), share,
                                     '对白占比偏离章纲已声明的目标，超过已设容差。'))
    elif anchor and anchor.get('dialogue_share') and _same_order(measured.get('han'), anchor.get('han')):
        base = anchor['dialogue_share']
        if _relative(measured['dialogue_share'], base) > limits.get('dialogue', DEFAULT_WINDOW['dialogue']):
            shape_change('dialogue_share', base, measured['dialogue_share'],
                         '对白占比相对首章样本的变化超过已设容差。')
    if measured.get('repetition_grams', 0) >= MIN_NGRAMS:
        repetition = measured['repetition_share']
        if repetition > limits.get('repetition', DEFAULT_WINDOW['repetition']):
            findings.append(_finding(chapter, 'repetition', limits.get('repetition', DEFAULT_WINDOW['repetition']),
                                     repetition, '本章内部四字重复率过高：同一串话在章内反复出现。'
                                                 '把重复的句子改写；若这是本卷有意的复沓，由作者调宽 style_window.repetition。'))
    expected_person = _declared_person(declared, contract)
    if expected_person and measured['person'] not in ('unknown', expected_person):
        observations.append(_observation(
            chapter, 'person', expected_person, measured['person'],
            '引号外出现的人称代词种类与视角声明标签不同；代词分布不能判定实际叙述视角。'))
    return report


def compare(prose, declared, anchor, window, chapter=0, contract=None):
    """Compatibility entry point returning only actionable findings from :func:`examine`."""
    return examine(prose, declared, anchor, window, chapter, contract)['findings']
