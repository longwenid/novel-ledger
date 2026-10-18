"""Read-only: which review findings keep coming back, and which of them the engine could judge.

rework.md 机制 4（发现回流成判据）的输入。每一份历史回执都留在 tasks.result 里；把其中全部
findings 按（阶段 × 检查项）聚合，标出跨任务重复出现的同一条（相同内容摘要出现多于一次），
并注明哪些类别已由引擎机械判定（repetition/language 的机械子项、substance 篇幅、ledger 账目）。
重复出现且未机械化的条目，就是下一批 check 项的候选——把审查经验变成引擎能力，靠的是这份账。

用法：python validation/reflux_probe.py /path/to/project
"""
import hashlib
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

project = Path(sys.argv[1])
db = sqlite3.connect('file:' + (project / 'novel.sqlite3').as_posix() + '?mode=ro', uri=True)
db.row_factory = sqlite3.Row

MECHANICAL = {
    'repetition': '已机械化：跨章逐字重复（lint.cross_chapter_duplicates）',
    'language': '已机械化：西文残留与引号体例（lint.latin_findings/style_findings）',
    'substance': '已机械化：章幅区间（band）',
}

REVIEW_STAGES = ('chapter_review', 'scope_review', 'scope_synthesis', 'revision_review',
                 'design_review', 'world_review', 'outline_review', 'contract_review',
                 'alignment_review')


def findings_of(stage, data):
    """Receipts keep findings in different shapes; read them all, never inventing any."""
    if not isinstance(data, dict):
        return
    groups = []
    for key in ('facts', 'reader'):
        if isinstance(data.get(key), dict):
            groups.append(data[key].get('findings'))
    groups.append(data.get('findings'))
    for findings in groups:
        for finding in findings or []:
            if isinstance(finding, dict) and finding.get('severity') not in (None, 'note'):
                yield finding


rows = defaultdict(lambda: {'count': 0, 'digests': set(), 'again': 0, 'reasons': []})
for task in db.execute('SELECT input, result FROM tasks WHERE status=\'done\'').fetchall():
    work = json.loads(task['input'])
    stage = work.get('stage')
    if stage not in REVIEW_STAGES or not task['result']:
        continue
    result = json.loads(task['result'])
    for finding in findings_of(stage, result.get('data')):
        key = (stage, finding.get('criterion'))
        row = rows[key]
        row['count'] += 1
        ident = hashlib.sha256(json.dumps(finding, ensure_ascii=False, sort_keys=True)
                               .encode('utf-8')).hexdigest()
        if ident in row['digests']:
            row['again'] += 1
        row['digests'].add(ident)
        if len(row['reasons']) < 2:
            row['reasons'].append(str(finding.get('reason'))[:90])

total = sum(row['count'] for row in rows.values())
print('审稿 findings 共 %d 条（%d 个 阶段×检查项 组合；重复 = 同一内容跨回执出现超过一次）'
      % (total, len(rows)))
print('%-34s %5s %5s  %s' % ('阶段×检查项', '次数', '重复', '机械判定 / 样例理由'))
for (stage, criterion), row in sorted(rows.items(), key=lambda kv: -kv[1]['count']):
    print('%-34s %5d %5d  %s %s' % ('%s×%s' % (stage, criterion), row['count'], row['again'],
                                    MECHANICAL.get(criterion, ''), row['reasons'][0] if row['reasons'] else ''))
candidates = sorted(((row['again'], stage, criterion, row['count'])
                     for (stage, criterion), row in rows.items()
                     if row['again'] and criterion not in MECHANICAL), reverse=True)
if candidates:
    print('\n机械化候选（重复出现且尚无机械判定，按重复次数排序）：')
    for again, stage, criterion, count in candidates:
        print('  %s×%s：重复 %d 次 / 共 %d 次' % (stage, criterion, again, count))
    print('这些是下一批 check 项的候选：同一条判断第二次出现时，先让引擎算一遍。')
else:
    print('\n没有重复出现且未机械化的发现。')
