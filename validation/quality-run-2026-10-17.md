# 实机验证复盘（2026-10-17）：一个三章小项目为什么花了 81 次派工与 650 万字符

对象：隔离项目 `C:\Users\longwen\.zcode\novels\verify-50k`（《我能看见死者缺的名额》，三章完本，正文 10,384 汉字）。
引擎：`main` @ 本轮修复后的工作区（开书协议 `creation/3`、存储 schema `novel-ledger/3`）。
方法：全部规划、执笔、审稿位由**真实独立会话**执行；主干只做派工、作者决定与治理命令。以下数字全部由
`validation/run_analysis.py`、`validation/read_waste_probe.py`、`validation/dup_required_probe.py`、
`validation/required_probe.py` 从该项目只读导出，可复跑。

> 字符量不是 token 或费用：中文大致一比一量级，但真实计费以宿主日志为准（`scripts/observe.py`）。
> 本文只谈**材料投递量**这一项引擎可负责的成本。

---

## 一、实测总量

| 指标 | 数值 |
|---|---|
| 派工任务 | **81**（另有 11 次取消、4 次作者裁决、7 次改约候选、2 次约定激活、1 次 discard） |
| 其中执笔 | **3**（一章一次）；开书 13、世界 10、约定 8、设计 23、章计划/人物 5、章审 9、返修 5、重设计 1、范围审 4 |
| 冻结输入合计 | 268,336 字符（均 3,313/任务） |
| 回执合计 | 799,064 字符（均 9,865/任务） |
| **补充读取（read 实际返回）** | **6,564,602 字符 / 307 次**（均 21,383/次） |
| 读取 ÷（输入+回执） | **6.07 倍** |
| 库体积 / work 目录 | 19.0 MB / 11.5 MB（81 个任务目录，均 138 KB） |
| 正文产出 | 10,384 汉字 → **每千汉字约 7.8 次派工、约 63 万读取字符** |

一句话：**这本书的费用不在写作上，而在“把同一批材料反复讲给每个角色听”上。**

---

## 二、异常消耗的五个来源（按实测贡献排序）

### 来源 1：`read` 会把已经给过的记录整份重发（占全部读取的 33%）

`read --task ID` 原本每次都返回该任务的**全部必读记录**。引擎其实已经在 journal 里记下“这个任务读过哪些记录”
（`store_keys.read_record`，`application._observe_read`），但下一次读取时全部重发。

- 实测：307 次读取里，**2,138,558 字符（33%）是“本次要的记录此前全部给过”的整份重复**。
- 单个任务最坏读到 26 万字符（`536d5ed6` 16 次、`29434c45` 3 次 256,410 字符）。
- 读者是谁也说明问题：`repair` 阶段均次读取 **74,456 字符**、`world_review` 47,654、`volume_plan` 41,762、
  `design_review` 35,727、`chapter_review` 32,518。

**修复（本轮已做）**：`read` 默认只交“本任务还没拿到过”的记录，并把被跳过的名字列在 `already_read` 里，
附一句“需要原文用 `--record 名称` 或 `read --all`”；新增 `read --all` 显式取回全部。实现落在
`application.read`（端口新增 `Repository.read_names`，SQLite 适配器与内存替身同步实现）。
删掉同一份材料的第二次投递是**纯收益**：语义不变，谁要重读谁显式要。

### 来源 2：同一内容在必读里出现两次（投影与源同时必读）

实测可直接量到两类：

| 重复对 | 实测重复字节 | 出现范围 |
|---|---|---|
| `scope_profiles` == `profiles` | 69,880 | 每个 `scope_review` / `scope_synthesis` |
| `frontier:book` == `design:book` | 20,576 | 每个 `volume_plan`（窗口覆盖全卷时两者逐字相同） |
| `world_core` ⊂ `world_model` | 11,199/次 | 几乎每个设计/审查任务（实测 47,636 + 11,199） |

`world_core` 也不是“另一种材料”，它就是从 `world_model` 里取 premise/rules/story_capacity 的投影
（`context.py` 中 `add('world_core', {...})` 与 `add('world_model', model)` 相邻）。一个设计任务因此
**为同一个世界付两次钱**，而且两份同时在场时，读者还得自己判断哪份是权威。

**修复（本轮已做）**：
- `context.build` 末尾按内容哈希收敛：**内容完全相同的必读只保留一份**（另一份仍在 `records` 里可按需读）。
- `world_core` 改为“源不在场时才必读”：设计/审查位读 `world_model`，场景位（write/repair/chapter_review）
  读 `world_core`，两者不再同时必读。
- 夹具新增不变量（`tests/support.py::required_material`）：每次派工都必须满足“必读里没有内容相同的两份”，
  这条不变量会跟着所有用 `drive()` 的测试跑，防止以后回退。

### 来源 3：审稿位的必读没有按“它要判断什么”裁剪

以本项目为例（`validation/required_probe.py` 实测）：

| 阶段 | 必读合计 | 最大三份 |
|---|---|---|
| `write` ch2 | 61,490 字符 | `scene_context` 21,014、`profiles` 13,175、`contract` 6,908 |
| `chapter_review` ch2 | 56,031 字符 | 同上（审的是 3,375 汉字的一章） |
| `repair` ch2 | 66,478 字符 | 再加 `base_draft` 与 `word_budget` |
| `volume_plan` | 93,630–95,976 字符 | `world_model` 47,636、`frontier:book`/`design:book` 12,312、`world_core` 11,199 |
| `contract_review` | 71,493–75,279 字符 | `world_model` 47,636、`world_core` 11,199、`proposal` 7–8.9K |

审一章 3,375 汉字的稿子要读 56,031 字符，比被审文本多 **16.6 倍**；其中 `scene_context`（21K）与
`profiles`（13K）对“这一章写得怎么样”只提供背景，不提供判据。

**建议（未做，属协议变更）**：给每个审稿阶段声明**判据集合**而不是“这一阶段相关的一切”——
`chapter_review` 需要 contract、scoped state、该章 plan、profiles（仅出场人）、该章正文；
`world_model` / `design:book` / `effective_layout` 转为按需。这条能一次砍掉审稿位的一半以上。

### 来源 4：规划管线与体量脱钩（固定成本压倒小体量）

81 次派工里只有 3 次执笔；**开书 13 + 世界 10 + 约定 8 + 设计 23 + 计划/人物 5 = 59 次（73%）发生在第一个字之前**。
三章一万字的书走的是与百万字长篇相同的门数、相同的世界十领域、相同的骨架→卷设计→逐章卷纲三层、
相同的五类独立审查，以及每阶段“返修 2 轮 + 重设计 1 轮”的额度。实测这些额度的实际用法：

- `world_model` 派了 **5** 次（1 稿 + 3 返修 + 1 作者批的追加返修），`world_review` **5** 次：世界候选从
  14 条意见收敛到 0，用了 4 轮验证 + 4 次整份返修；
- `contract_review` 派了 **8** 次（含 4 次改约 + 1 次被裁决作废的派工），42 次读取 935,263 字符——
  单阶段最大读取消费者；
- `chapter_review` 9 次（3 章 × 审/返修/再审），`design_review` 8 次。
- 外部成本：这 81 次里有 11 次任务被取消、4 次 `revision_blocked`、2 次约定激活、1 次 discard——
  控制面为了纠正“改约/裁决/范围”所付的重派。

**建议（未做，属端口与协议变更）**：让 `scale` 门已经成为一等决定的**体量档位**去决定管线形状，而不是只决定章数：
微型/短篇档下合并或跳过低产出的阶段（世界与约定已合并为一次派工，可以再合并骨架与卷设计；
单卷书的卷纲审查可并入设计审查），并按档位收缩返修额度（三章的书不需要每阶段 2 轮返修 + 1 轮重设计）。
判断依据是实测：小体量下这些阶段的产出（设计字数）远小于它们消耗的材料与派工。

### 来源 5：改约与裁决要重审整份约定

每次改约（本轮 7 次候选、2 次激活）都会走一遍 `contract_review`，而该阶段的必读是整份约定 +
整份世界 + opening_choices/basis（71–96K 字符）。作者只改了一句话（例如兑现节奏里的三个数字），
审查者却要重读全份材料。

**本轮已做的部分**：改约时把**改动字段**作为 `contract_amendment` 一并投递（`before/after` 全值，
截断时明确标注 `…truncated` 而不是把截断串伪装成完整值），审查者可以只核差异。
**建议（未做）**：把“核差异”变成默认——改约审的必读集合改为 `amendment + 旧约定 + 新约定`，
原候选整份转按需。

---

## 三、skill 设计问题（不是数字，是结构性判断）

1. **材料所有权只声明到“哪个模块”，没声明到“哪个阶段真正需要它”。** `world_model`/`world_core`/
   `design:book`/`frontier:*`/`scope_profiles`/`profiles` 各自都有明确的生产者，但“谁必须读”是逐阶段手写的布尔表达式，
   于是每加一个阶段就会顺手多带一份材料（本文来源 2、3 都是这样长出来的）。
   解耦的下一步是把投递关系也变成声明：一张 `阶段 → 判据记录集` 的表，由守卫断言“声明的记录必须存在、且不与别的必读重复”。

2. **同一事实的多条投递路径没有单一权威。** 投影与源同时在场时，读者无法从材料本身判断哪份是权威；
   本轮用“内容相同者只留一份 + 投影仅在源不在场时必读”消掉了已发现的几处，但同类关系还可再生（新投影 = 新重复）。

3. **额度是按阶段给的，不是按体量给的。** 三章的书与六百章的书共享同一套返修/重设计额度，而小体量下
   一个阶段的总产出可能还不如它一轮返修的材料多。额度应当与“这一阶段的产出规模”挂钩。

4. **设计阶段的死路仍然存在。** 本轮实机撞到两次“候选还在收敛、额度却已用完，而作者没有任何通道”：
   一次在世界候选（发现数 14→7→4→3、0 blocker），一次在第三章（只剩 2 条局部修订）。
   两次都已修（`resume` 把处理方式交成作者决定：再返修一轮／接受并把意见记为未解决项／重开本阶段），
   但**同一类死路在别的计数上还会复现**（例如范围审、改约审）：只要“额度”是唯一的停止条件，就要有对应的作者通道。

5. **作者裁决与派工的顺序没有约束。** 先派工后记录裁决会让刚派出的任务当场失效（`stale_task`，白派一次 Worker）。
   本轮已写进运行指南，但引擎侧仍可以更硬：裁决落库时若存在 pending 任务，直接在返回值里说明“该任务已作废，
   不要派工”，而不是让 Worker 在读取时才发现。

6. **体量与管线脱钩使“小书”成为最贵的一类。** 从每千汉字 7.8 次派工看，微型档不是“便宜的小项目”，
   而是**固定成本占比最高**的项目。若目标是让 skill 能开小书，管线必须随档位收缩。

---

## 四、本轮已落地的修复（可复跑）

| # | 修复 | 位置 | 证据 |
|---|---|---|---|
| 1 | `read` 只交未读记录，`--all` / `--record` 显式重读 | `application.read`、`ports.Repository.read_names`、两个适配器、CLI | 实测可省的整份重复 2,138,558 字符（33%）；`test_a_second_full_read_only_hands_over_what_is_still_new` |
| 2 | 必读里内容相同者只留一份 | `context.build` | 实测重复 90,456 字符；夹具不变量 `required_material` |
| 3 | `world_core` 仅在源不在场时必读 | `context.build` | 实测每次省 11,199 字符；`test_the_world_is_never_required_twice_on_one_dispatch` |
| 4 | 改约只交差异，截断显式标注 | `application.recontract`（`contract_amendment`） | 42 次读取 935K 的改约审现在可只核差异 |
| 5 | 设计/章级死路交作者决定 | `workflow.hold_for_exhaustion` / `hold_for_draft_exhaustion` / `resolve_draft_exhaustion`、`application.resume/answer` | 两次实机死路都可继续；两条回归 |
| 6 | 裁决与派工的顺序写进运行指南 | `references/runtime.md` | 一次被 `stale_task` 挡下的回执 |

## 五、建议但未做的修复（需协议/端口变更，按收益排序）

1. **阶段 → 判据记录集**：把“这一阶段必须读什么”从散落的布尔表达式收成一张声明表，配套守卫断言。
   预计砍掉审稿位一半以上材料（来源 3）。
2. **体量档位决定管线与额度**：小档合并/跳过产出比低的阶段与审查层（来源 4）。
3. **改约审默认核差异**：`contract_amendment` 升为唯一必读，原候选转按需（来源 5）。
4. **返修接受路径的完成度**：作者选“接受并把意见记为未解决项”后，完本审计与全书视图要把这些条目显式列出
   （`accepted_findings` 已入账本，尚需在 `book.html` 与完本篇审计里可见）。

## 六、复现

```bash
python3 validation/run_analysis.py   /path/to/project   # 分阶段材料、读取、生命周期、磁盘
python3 validation/read_waste_probe.py /path/to/project # 重复读取的字符与占比
python3 validation/dup_required_probe.py /path/to/project # 必读里内容相同的重复
python3 validation/required_probe.py /path/to/project write,chapter_review # 指定阶段的必读构成
python3 validation/cost_report.py /path/to/project      # 单项目的按阶段与磁盘汇总
```
