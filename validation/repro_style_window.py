"""v2.1 文风机械代理判据（spec §三.4）：越界产生 style finding 并进有界返修。

    python validation/repro_style_window.py

分两层：
* **单元层**（`style.metrics/compare` 直接调用，今天就该通过）：句长/对白比越界 → finding；
  容差内不报；无锚点只跑重复度与人称；章纲 `dialogue_ratio` 目标越界同样被核。
* **流程层**（`workflow.apply` 并入 findings）：同一章的人称与章纲声明不符 → style finding +
  `next_stage == 'repair'` 且 `committed_chapter is None`。

退出码：0 = 全部符合预期；1 = 有不一致；2 = 引擎未接线（style 模块或 workflow 接线缺失，blocked）。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v21_harness import open_project, play, run_cases, style_ready                # noqa: E402
from novel_ledger import style                                                    # noqa: E402

# 两个可复现的样本：长句为主（锚点）与短句/对白为主（越界）。汉字数都远高于 style.MIN_HAN。
LONG_SENTENCES = ('他把退回的箱子搬到灯下，先核对封条上的签字，再逐页翻开夜班登记册，'
                  '把每一笔经手的记录与责任栏对照，直到确认那处矛盾的出处为止。'
                  '主管站在门口看了很久，最后只说了一句“按流程办”，就转身回了值班室。'
                  '他没有争辩，只把那页复印了一份，夹进自己的工具袋里，准备明天再问。')
SHORT_SENTENCES = ('灯亮。箱子在。他翻封条。看签字。名字不对。他记下。'
                   '主管来了。他说：核对。主管说：按流程。他点头。收起凭据。走人。')
DIALOGUE_HEAVY = ('“先核对名字。”他说。\n“按流程办。”主管说。\n“流程也要求核对。”他说。\n'
                  '“那就核对。”主管说。\n“我今晚就核。”他说。\n“随你。”主管说。')
NO_DIALOGUE = ('他先核对封条上的签字，再把登记册翻到经手的那一页，逐项对照责任栏。'
               '确认矛盾之后，他把凭据收进工具袋，决定第二天再问一次。')
REPETITIVE = ('核对凭据责任栏。核对凭据责任栏。核对凭据责任栏。核对凭据责任栏。'
              '核对凭据责任栏。核对凭据责任栏。核对凭据责任栏。核对凭据责任栏。'
              '核对凭据责任栏。核对凭据责任栏。核对凭据责任栏。核对凭据责任栏。')


def _finding_metrics(rows):
    return sorted({row.get('metric') for row in rows})


def case_sentence_out_of_window():
    anchor = style.metrics(LONG_SENTENCES)
    measured = style.metrics(SHORT_SENTENCES)
    rows = style.compare(SHORT_SENTENCES, {}, anchor, style.DEFAULT_WINDOW, chapter=2)
    metrics = _finding_metrics(rows)
    shape = bool(rows) and all(row.get('severity') == 'quality' and row.get('repair_scope') == 'local'
                               and row.get('criterion', '').startswith('style_') for row in rows)
    # Shape metrics only run between samples of the same order of magnitude (style._same_order):
    # assert that precondition explicitly so shrinking a sample cannot silently disable this case.
    comparable = 1 / 3 <= (measured['han'] / anchor['han']) <= 3
    problems = []
    if not comparable:
        problems.append('样本不在同一数量级，句长比较不会执行：anchor han=%s, chapter han=%s'
                        % (anchor['han'], measured['han']))
    if not metrics:
        problems.append('句长越界没有产生 style finding')
    if not shape:
        problems.append('finding 形状不是 quality/local/style_*：%s' % rows[:2])
    return {'kind': 'accepted' if not problems else 'contradicted',
            'metrics': metrics, 'findings': rows[:3],
            'anchor_han': anchor['han'], 'chapter_han': measured['han'],
            'anchor': {k: anchor[k] for k in ('sentence_mean', 'sentence_short_share', 'dialogue_share')},
            'measured': {k: measured[k] for k in ('sentence_mean', 'sentence_short_share', 'dialogue_share')},
            'problems': problems,
            'fragment': '锚点=长句样本，本章=短句样本'}


def case_within_window_silent():
    anchor = style.metrics(LONG_SENTENCES)
    rows = style.compare(LONG_SENTENCES, {}, anchor, style.DEFAULT_WINDOW, chapter=2)
    return {'kind': 'accepted' if not rows else 'contradicted',
            'findings': rows[:3],
            'problems': [] if not rows else ['同一段文本与自身锚点比较仍报了 finding'],
            'fragment': '锚点=本章=同一段文本（容差内）'}


def case_without_anchor_only_two_checks():
    """无锚点：只跑本章重复度与人称；形状指标一项都不许出现，`unknown` 人称不算不符。"""
    rows = style.compare(SHORT_SENTENCES, {'pov': '第三人称限知'}, None, style.DEFAULT_WINDOW, chapter=2)
    metrics = _finding_metrics(rows)
    forbidden = {'sentence_mean', 'sentence_short_share', 'paragraph_mean', 'paragraph_max', 'dialogue_share'}
    leaked = sorted(set(metrics) & forbidden)
    problems = []
    if leaked:
        problems.append('无锚点却跑了需要锚点的指标：%s' % leaked)
    unknown_rows = style.compare('他说完就走。随后灯灭了。外面下起雨来。', {'pov': '第三人称限知'},
                                 None, style.DEFAULT_WINDOW, chapter=2)
    if any(row.get('metric') == 'person' for row in unknown_rows):
        problems.append('叙述人称无法判定（unknown）时报了 person 不符：%s' % unknown_rows)
    return {'kind': 'accepted' if not problems else 'contradicted',
            'metrics': metrics, 'findings': rows[:3],
            'unknown_person_findings': unknown_rows,
            'problems': problems,
            'fragment': 'anchor=None 的 compare()（含 unknown 人称）'}


def case_repetition_share():
    rows = style.compare(REPETITIVE, {}, None, style.DEFAULT_WINDOW, chapter=2)
    metrics = _finding_metrics(rows)
    return {'kind': 'accepted' if 'repetition' in metrics else 'contradicted',
            'metrics': metrics, 'findings': rows[:3],
            'problems': [] if 'repetition' in metrics else ['章内高重复没有触发 repetition 判据'],
            'fragment': '章内四字重复率超 window.repetition'}


def case_dialogue_ratio_target():
    declared = {'pov': '第三人称限知', 'rhythm': '短句推进', 'dialogue_ratio': 0.30}
    rows = style.compare(NO_DIALOGUE, declared, style.metrics(LONG_SENTENCES), style.DEFAULT_WINDOW, chapter=2)
    metrics = _finding_metrics(rows)
    return {'kind': 'accepted' if 'dialogue_ratio' in metrics else 'contradicted',
            'metrics': metrics, 'findings': rows[:3],
            'problems': [] if 'dialogue_ratio' in metrics else ['章纲 dialogue_ratio 目标未被核'],
            'fragment': 'chapter.style.dialogue_ratio=0.30，实际几乎没有对白'}


SHORT_ANCHOR = ('灯亮着。他把箱子放到桌上，先看封条，再看签字，名字不对。'
                '他记下这一页的编号，打算明天再问。他又看了一眼责任栏，什么也没写。')
LONG_CHAPTER = ''.join('第%d段：他把箱子搬到灯下，核对封条上的签字，又翻到登记册的那一页，'
                       '逐项对照责任栏，确认矛盾之后收好凭据。' % n for n in range(1, 40))


def case_short_anchor_long_chapter_silent():
    """锚点极短（约 60 汉字）而本章很长（2000+ 汉字）：形状类指标一项都不许报。

    这是样本量级造成的 artifact 防线（`style._same_order` 只比较同数量级的样本）；只有
    `dialogue_ratio`（章纲声明的绝对目标）与重复度/人称不受此限。
    """
    anchor = style.metrics(SHORT_ANCHOR)
    measured = style.metrics(LONG_CHAPTER)
    rows = style.compare(LONG_CHAPTER, {}, anchor, style.DEFAULT_WINDOW, chapter=2)
    metrics = _finding_metrics(rows)
    forbidden = {'sentence_mean', 'sentence_short_share', 'paragraph_mean', 'paragraph_max', 'dialogue_share'}
    leaked = sorted(set(metrics) & forbidden)
    problems = []
    if anchor['han'] < style.MIN_HAN:
        problems.append('锚点低于 MIN_HAN，baseline() 会直接返回 None：han=%s' % anchor['han'])
    if not (measured['han'] / anchor['han'] > 3):
        problems.append('样本没有超出同数量级（%.1f 倍），这个用例就没有意义'
                        % (measured['han'] / anchor['han']))
    if leaked:
        problems.append('不同数量级的样本仍被比较出形状 finding：%s' % leaked)
    return {'kind': 'accepted' if not problems else 'contradicted',
            'anchor_han': anchor['han'], 'chapter_han': measured['han'],
            'ratios': round(measured['han'] / anchor['han'], 1),
            'metrics': metrics, 'findings': rows[:3], 'problems': problems,
            'fragment': '锚点 han=%d，本章 han=%d（相差 %.1f 倍）'
                        % (anchor['han'], measured['han'], measured['han'] / anchor['han'])}


def case_merged_window_overrides():
    """卷纲 `style.window` 逐项覆盖契约 `style_window`（`style.merged_window`），且行为随容差翻转。

    判别式取确定值：锚点有对白、本章 `NO_DIALOGUE` 无对白，故 `dialogue_share` 的相对偏差恒为
    1.0；容差 0.5 → 报，容差 1.5 → 不报。与锚点具体数值无关，避免了「容差不够大所以仍报」的假通过。
    """
    anchor = style.metrics(LONG_SENTENCES)
    contract = {'style_window': {'dialogue': 0.5, 'sentence': 0.2}}
    volume_style = {'trend': '本卷对白变多。', 'window': {'dialogue': 1.5}}
    merged = style.merged_window(contract, volume_style)
    problems = []
    if anchor['dialogue_share'] <= 0:
        problems.append('锚点没有对白，dialogue_share 分支不会执行：%s' % anchor['dialogue_share'])
    if merged.get('dialogue') != 1.5:
        problems.append('卷纲覆盖未生效：dialogue=%s' % merged.get('dialogue'))
    if merged.get('sentence') != 0.2:
        problems.append('未覆盖项被改动：sentence=%s（应保持契约的 0.2）' % merged.get('sentence'))
    if merged.get('repetition') != style.DEFAULT_WINDOW['repetition']:
        problems.append('契约未声明的项未回落默认：repetition=%s' % merged.get('repetition'))
    contract_only = _finding_metrics(style.compare(NO_DIALOGUE, {}, anchor, style.merged_window(contract, None), chapter=2))
    with_volume = _finding_metrics(style.compare(NO_DIALOGUE, {}, anchor, merged, chapter=2))
    if 'dialogue_share' not in contract_only:
        problems.append('契约容差 0.5 下没有报 dialogue_share：%s' % contract_only)
    if 'dialogue_share' in with_volume:
        problems.append('卷纲把容差放宽到 1.5 后仍然报 dialogue_share：%s' % with_volume)
    return {'kind': 'accepted' if not problems else 'contradicted',
            'merged': merged, 'anchor_dialogue_share': anchor['dialogue_share'],
            'contract_only_metrics': contract_only, 'with_volume_metrics': with_volume,
            'problems': problems,
            'fragment': "契约 style_window={'dialogue':0.5} + 卷纲 window={'dialogue':1.5}"}


def case_metrics_finite_and_floors():
    """`metrics` 全值有限（含退化输入）；`compare` 在低于 `MIN_HAN` 时不判定。

    口径（Lead 22:22 收紧后）：`repetition_share` 恒为有限数，**门槛属于 `compare`**——
    只有 `repetition_grams >= MIN_NGRAMS` 才判重复度；而 `compare` 又先过 `MIN_HAN`，
    过线样本的四字窗数恒为 `han-3 >= 37 > 20`，所以门槛只会挡住极短样本，不会在正常章上静默失效。
    """
    problems = []
    samples = {'空串': '', '空白': '   \n  ', '只有引号': '“”「」', '单字': '灯',
               '标点': '。！？……——', '低于 MIN_HAN': '他看了看箱子。'}
    measured = {}
    for label, sample in samples.items():
        value = style.metrics(sample)
        measured[label] = {key: value[key] for key in
                           ('han', 'sentences', 'sentence_mean', 'paragraph_mean', 'paragraph_max',
                            'dialogue_share', 'repetition_grams', 'repetition_share', 'person')}
        for key, item in value.items():
            if isinstance(item, float) and (item != item or item in (float('inf'), float('-inf'))):
                problems.append('%s 的 %s 不是有限数：%r' % (label, key, item))
    short = style.metrics('他看了看箱子。')
    if short['han'] >= style.MIN_HAN:
        problems.append('这个样本没有低于 MIN_HAN，测不到下限：han=%s' % short['han'])
    if short['repetition_grams'] >= style.MIN_NGRAMS:
        problems.append('这个样本的四字窗数没有低于门槛，测不到门槛：grams=%s'
                        % short['repetition_grams'])
    if short['repetition_share'] is None or short['repetition_share'] != short['repetition_share']:
        problems.append('短样本的 repetition_share 不是有限数（口径：metrics 恒给有限值，门槛在 compare）')
    below = style.compare('他看了看箱子。', {}, None, style.DEFAULT_WINDOW, chapter=1)
    if below:
        problems.append('低于 MIN_HAN 的样本仍产生 finding：%s' % below)
    # 反向不变量：过了 MIN_HAN 的样本，四字窗数必然过 MIN_NGRAMS（40-3=37>20）。
    normal = style.metrics(SHORT_ANCHOR)
    if normal['han'] >= style.MIN_HAN and normal['repetition_grams'] < style.MIN_NGRAMS:
        problems.append('过 MIN_HAN 的样本反而被 repetition 门槛挡住：%s' % normal)
    return {'kind': 'accepted' if not problems else 'contradicted',
            'metrics': measured, 'below_floor_findings': below,
            'normal_sample': {'han': normal['han'], 'repetition_grams': normal['repetition_grams']},
            'problems': problems,
            'fragment': '退化输入（空串/空白/引号/单字/标点）与低于 MIN_HAN 的样本'}


def case_person_ignores_quoted_first_person():
    """人称只看引号外的叙述：对白里的「我」不算第一人称叙述。"""
    prose = ('他把箱子搬到灯下，核对封条上的签字。\n“我先看看。”他说。\n'
             '他翻开登记册，逐项对照责任栏。\n“我记下了。”他说。\n'
             '他合上本子，把凭据收进工具袋，决定明天再问一次。')
    measured = style.metrics(prose)
    rows = style.compare(prose, {'pov': '第三人称限知'}, None, style.DEFAULT_WINDOW, chapter=2)
    problems = []
    if measured['person'] != 'third':
        problems.append('引号内第一人称被算进了叙述人称：person=%s' % measured['person'])
    if any(row.get('metric') == 'person' for row in rows):
        problems.append('叙述是第三人称却报了 person 不符：%s' % rows)
    return {'kind': 'accepted' if not problems else 'contradicted',
            'person': measured['person'], 'findings': rows[:3], 'problems': problems,
            'fragment': '叙述第三人称 + 对白第一人称（引号内不计入人称）'}


def case_person_mismatch_flow():
    """流程层：章纲声明第三人称，正文写成第一人称 → style finding 且进有界返修、未入库。"""
    first_person = ('我先把退回的箱子搬到灯下。我核对封条上的签字。我翻开登记册。'
                    '我把责任栏空着，等主管过来。我记住那一页的编号，准备明天再问一次。')

    def declare_third(data, task):
        for row in data['chapters']:
            row['style'] = {'pov': '第三人称限知', 'rhythm': '短句推进，动作与物件密。'}
        return 'chapters[*].style.pov = 第三人称限知'

    def write_first(data, task):
        data['prose'] = first_person
        return 'write 的正文改用第一人称叙述'

    repo, app, owner = open_project(chapters=4, volumes=2)
    play(app, owner, tamper=declare_third, on='chapter_outline')
    stages, status, error, findings = play(app, owner, tamper=write_first, on='write')
    rows = findings or []
    criteria = sorted({row.get('criterion') for row in rows})
    value = {'kind': 'rejected' if 'style_person' in criteria else 'contradicted',
             'stages': stages,
             'criteria': criteria,
             'findings': rows[:3],
             'next_stage': (app.repo.load().get('draft') or {}).get('stage'),
             'committed': [row['n'] for row in repo.headers(app.repo.load()['branch'])],
             'problems': [] if 'style_person' in criteria else ['第一人称正文没有产生 style_person finding'],
             'fragment': '章纲声明第三人称；write 正文用第一人称'}
    return value


UNIT_CASES = (
    {'name': '文风01 句长越界 → style finding（quality/local）', 'expect': 'accepted',
     'fn': case_sentence_out_of_window},
    {'name': '文风02 容差内不误报', 'expect': 'accepted', 'fn': case_within_window_silent},
    {'name': '文风03 无锚点只跑重复度与人称', 'expect': 'accepted',
     'fn': case_without_anchor_only_two_checks},
    {'name': '文风04 章内高重复 → repetition', 'expect': 'accepted', 'fn': case_repetition_share},
    {'name': '文风05 dialogue_ratio 目标被核', 'expect': 'accepted', 'fn': case_dialogue_ratio_target},
    {'name': '文风06 极短锚点 vs 长章不报形状', 'expect': 'accepted',
     'fn': case_short_anchor_long_chapter_silent},
    {'name': '文风07 卷纲 style.window 逐项覆盖契约', 'expect': 'accepted',
     'fn': case_merged_window_overrides},
    {'name': '文风08 metrics 全值有限 + 门槛行为', 'expect': 'accepted',
     'fn': case_metrics_finite_and_floors},
    {'name': '文风09 人称只看引号外叙述', 'expect': 'accepted',
     'fn': case_person_ignores_quoted_first_person},
)

FLOW_CASES = (
    {'name': '文风06 人称不符 → style finding 并进返修', 'expect': 'rejected',
     'fn': case_person_mismatch_flow},
)


def main(argv=None):
    ready, why = style_ready()
    print('=== 单元层（style.metrics/compare；只依赖 style 模块）===')
    unit = run_cases('v2.1 文风单元判据', UNIT_CASES, blocked=None, argv=argv)
    print()
    print('=== 流程层（workflow.apply 并入 findings）===')
    flow = run_cases('v2.1 文风流程判据', FLOW_CASES, blocked=None if ready else why, argv=argv)
    if unit == 2 or flow == 2:
        return 2
    return max(unit, flow)


if __name__ == '__main__':
    sys.exit(main())
