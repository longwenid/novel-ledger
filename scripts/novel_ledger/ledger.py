"""Structured account blocks: arithmetic the engine can check, where prose cannot carry it.

Three defects on a real run were the same shape — numbers and relations living in prose only a
reviewer could re-derive ("six payments × three years each = eighteen years", "seventeen records
= six by age + eleven by procedure"), and each cost a repair round plus a full re-review. A
ledger block is optional: absent means no arithmetic was declared. Once a design, an outline or
a chapter plan carries one, every row is checked mechanically at submit (and therefore at
preflight), and a later artifact that reuses the same key must agree with the value already on
record. rework.md 机制 3。
"""
from __future__ import annotations

from .contracts import require, text

RELATIONS = ('sum_of', 'product_of', 'equals', 'ratio_of')


def check(block):
    """Validate one ledger block's shape and arithmetic; the failing row is named in the error."""
    require(block is None or isinstance(block, list), 'ledger',
            'ledger 须为行数组；不声明算术就省略该字段。')
    seen = set()
    for row in block or ():
        require(isinstance(row, dict) and text(row.get('key')) and type(row.get('value')) is int
                and row.get('value') >= 0, 'ledger', '每行需要 key 与非负整数 value。', {'row': row})
        key = row['key']
        require(key not in seen, 'ledger', '同一账目键不能出现两次。', {'key': key})
        seen.add(key)
        relations = [name for name in RELATIONS if name in row]
        require(len(relations) == 1, 'ledger', '每行恰好声明一种关系。',
                {'key': key, 'known': list(RELATIONS)})
        name = relations[0]
        operands = row[name]
        require(isinstance(operands, list) and len(operands) >= 2
                and all(type(n) is int for n in operands), 'ledger',
                '关系操作数须为至少两个整数。', {'key': key, 'relation': name})
        if name == 'sum_of':
            expected = sum(operands)
        elif name == 'product_of':
            expected = 1
            for operand in operands:
                expected *= operand
        elif name == 'equals':
            require(all(operand == row['value'] for operand in operands), 'ledger',
                    'equals 的各操作数应与 value 全部相等：' + key,
                    {'key': key, 'operands': operands})
            continue
        else:                                   # ratio_of: value * 后项 == 前项
            require(len(operands) == 2 and operands[1] != 0 and operands[0] % operands[1] == 0
                    and row['value'] * operands[1] == operands[0], 'ledger',
                    'ratio_of 须为可整除的两项且 value×后项==前项：' + key,
                    {'key': key, 'operands': operands})
            continue
        require(row['value'] == expected, 'ledger',
                '账目算不平：' + key, {'declared': row['value'], 'computed': expected,
                                      'relation': name, 'operands': operands,
                                      'recover': '按算得的结果改 value，或修正操作数；'
                                                 '观感描述不要写进账目行。'})


def cross_check(block, prior, prior_of='设计'):
    """A key that already has a value on record must keep it; a new key is new information."""
    values = {row['key']: row['value'] for row in prior or ()}
    for row in block or ():
        known = values.get(row['key'])
        require(known is None or known == row['value'], 'ledger',
                '账目键与%s已核验的值不一致。' % prior_of,
                {'key': row['key'], 'declared': row['value'], 'already_on_record': known,
                 'recover': '以已核验值为准改写本行；数字确需变化时先改上游工件并重新核验。'})
