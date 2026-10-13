"""Per-dispatch briefs: the one page a worker actually needs, instead of every guide in full.

A guide is a reference document for a whole stage; a dispatch needs the part that applies to the
task in hand. Keeping the brief generated here — next to the methods it quotes — means the author
pays for the current gate's rules and lens, not for the entire toolbox on every round.
"""
from __future__ import annotations

from .creation import GATES, VALUE_RULES
from .contracts import OPTION_CONTRACT
BRIEFS = {
    'opening_options': '开书方案简报',
    'world_model': '世界与约定简报',
}


def gate_title(gate_id):
    return next((title for ident, title in GATES if ident == gate_id), gate_id)


def opening_options(gate, lens_brief, previous=()):
    """The brief for one gate: what this gate decides, how to vary it, and what to hand back."""
    lines = ['# ' + BRIEFS['opening_options'], '',
             '## 本门：%s（%s）' % (gate_title(gate.get('id')), gate.get('id')), '',
             'value 字段：' + VALUE_RULES.get(gate.get('id'), '按已选方向给出结构化方案。'), '']
    if previous:
        lines.append('## 已选方向（不要推翻，只在此之上给方案）')
        lines.extend('- %s：%s' % (name, text) for name, text in previous)
        lines.append('')
    lines.extend(['## 本轮创意透镜（用来想，不要写进方案文本）', lens_brief, ''])
    lines.extend(['## 交付契约', OPTION_CONTRACT])
    lines.append('')
    lines.append('完整方法表与选项格式见 guides 里的文件；本简报已含本门所需规则，不必为格式再读全文。')
    lines.append('')
    lines.append('路径自检：task.json 的 commands/guides 由当前安装渲染。先确认其中的解释器与脚本存在再执行；'
                 '若不存在，回报主控重新 advance 刷新任务视图，不要自行改写命令，也不要假定某条路径失效。')
    lines.append('')
    lines.append('格式自检：写回执前用 `check` 试算（把候选 JSON 从标准输入管道进去，如 '
                 '`python CLI --project PROJECT check < 候选.json`）。它按提交同一套校验运行但不入库，'
                 '会直接告诉你缺哪个字段、哪个枚举不对。**不要为了确认格式去读引擎源码**——那会白花上下文，'
                 'check 的回答就是权威。')
    return '\n'.join(lines)


def world_model(lens_brief=None, previous=()):
    """World plus contract in one dispatch: what the world owes, and what the contract must keep."""
    lines = ['# ' + BRIEFS['world_model'], '',
             '## 世界模型', '把已选方向扩展成能持续产生行动、冲突、代价与后果的环境。十个领域的字段权威见 world.SECTIONS，'
             '完整记录须有稳定 id 与 links=[领域:id]；同时给 premise、story_capacity 与准确的 selection_hash。',
             '每个领域至少一条实写记录：不要写"待补"，也不要只给经济与制度——地域、日常、人物、隐秘与机制都要能落到具体场景。', '']
    if previous:
        lines.append('## 已选方向（不得改动）')
        lines.extend('- %s：%s' % (name, text) for name, text in previous)
        lines.append('')
    lines.extend(['## 同一份提交里还要给约定', OPTION_CONTRACT,
                  '约定必须逐字保留已选字段；模板里 contract 一节的字段骨架照填。', ''])
    return '\n'.join(lines)
