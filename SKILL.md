---
name: novel-ledger
description: >-
  在用户要求从零开书、续写长篇网络小说、修订正文或恢复小说项目时使用。通过逐门选择、卷纲与章纲状态链、伏笔账、文风代理指标与执笔自比，按作者授权推进并交付。
---

# novel-ledger

沿用作者已有设定和决定，缺什么才补什么；只推进已授权目标。讨论小说、技能或引擎本身不表示启动创作。

ROOT 是本技能的绝对路径，PROJECT 是独立小说项目的绝对路径。入口为 `python3 ROOT/scripts/novel.py --project PROJECT 命令`（Windows 用 `python`），运行仅依赖 Python 3.9+ 标准库；项目数据和产物存入 PROJECT。宿主可能用目录联接（junction/symlink）把同一份安装映射到第二个路径：注入的基目录与任务 commands 里渲染的路径实为同一安装，不要当成两份技能核实。

流水线是**五步**：十门开书（主干自执）→ 世界模型与约定 → 每卷 2000–3000 汉字（目标 2500）的极简卷纲（含伏笔账与文风走向）→ 含资源/位置/情节漂移字段、伏笔执行（`plant`/`payoff`）与文风声明的极简章纲 → 按章纲执笔并自比，引擎机械核账（漂移 + 伏笔事件 + 文风代理指标）。**没有设计层审查，也没有章级独立审**（作者决定）。

## 先选当前任务

只读对应指南的相关小节。执行中的字段、身份、来源和能力以当前冻结的 `task.json`、`brief`、`required` 与模板为准。

| 当前任务 | 首先读取 | 何时补读 |
|---|---|---|
| 从零开书、导入已有设定 | [逐门开书](references/opening.md) | 当前是 `creation/3` 十门（起点/番茄男频长篇网文方向：金手指与成长线、对抗梯度、爽点兑现是一等决定，并落成约定字段）；换组或方案同质化读 [创意工具箱](references/hatch.md)；世界任务读 [世界模型](references/world.md)。已有项目保留自己的门序（creation/2、creation/1），不迁移。 |
| 续写、恢复、暂停、改变作者约定 | [运行与恢复](references/runtime.md) | 沿当前状态和原授权接续，不重新创建项目或重问已定事项。 |
| 写卷纲、写章纲、执笔或返修 | [创作与自比](references/craft.md) | 卷纲/章纲的形状、漂移字段、`enter`/`exit` 状态链与引擎核算读 [叙事推进](references/narrative.md)；伏笔账（卷纲声明、章纲 `plant`/`payoff`、卷末闭合）与文风（`style.trend`/`style`/`style_window`/代理指标）同页。 |
| 历史修订、影响分析、候选采纳或撤销 | [修订影响分析](references/runtime.md#修订影响分析) | 阅读关联与理解版本读 [叙事工作台](references/workbench.md)；补丁与人物/场景字段读 [编辑能力](references/editorial.md)。 |
| 延续作品理解、原文样本、移动场景 | [叙事工作台](references/workbench.md) | 按任务冻结的理解、场景身份和阅读依赖能力执行。 |
| 人物重核、场景展开、完本 | [编辑能力](references/editorial.md) | 任务含 `editorial/1` 时读对应阶段；交付与失败恢复按运行指南。 |
| 填回执、补材料、处理字段拒绝 | [任务与结果协议](references/protocol.md) | 先用当前模板和 `check` 试算；Worker 不查源码或旧回执猜格式。 |
| 修改引擎或核对能力边界 | [架构](references/architecture.md) | 工程检查、材料测量和人工文学抽读读 [验证](references/validation.md)；**要减少返工或投递成本时先读 [返工与成本](references/rework.md)**（判据前移、窄返修、结构化账目、机械正文判据等机制与设计原则）。 |

## 共同边界

| 边界 | 必须保持 |
|---|---|
| 作者决定 | 保存原话、范围和适用版本。已有准确选择或首章认可直接登记；只对真正缺失的决定等待，不扩大正文、修订或发布授权。 |
| 真源与事实 | SQLite 是唯一持久真源，正文和事实由 `submit` 原子提交，不手改库或伪造回执。设计、人物档案和作品理解不能直接变为事实。 |
| 章纲即结算契约 | 主干只管目标、派工和治理，不读写正文、不代签自比。进卷前交 `volume_outline`（每卷 2000–3000 汉字，目标 2500；含伏笔账 `hooks` 的窗口/`required`/`continues` 与文风走向 `style.trend`），进入该卷前交 `chapter_outline`（每章 synopsis 与资源/位置/知情/时钟/人物/情节增量，含 `enter`/`exit`，外加伏笔执行 `hooks` 与文风 `style`）；章纲提交时引擎按卷内状态链逐章模拟并比对 `enter`，伏笔的重复埋设/重复兑现/越窗/未埋先承接与卷末 `required` 未兑现一并拒绝。执笔一章后交 `drift_check` 逐项自比，引擎按投影给 `actual.from`，逐项核算覆盖与去向，并由 `drift.reconcile` 产出伏笔事件（写手不手写事件），不符走有界返修。 |
| 代价（必须向作者说明） | 不再有独立 agent 复核文学质量与阅读体验：设计层审查与章级独立审已全部删除。核对只剩引擎机械核账（漂移、伏笔、字数、lint）与执笔自比；文学质量由**文风机制**承担可核对的那一半（卷纲 `style.trend` + 章纲 `style` + `style.py` 五条代理指标按契约 `style_window` 比对首章锚点）。**代理指标只保证文风一致、可核对，不证明"好看、人物可信"**；真正的文学判断仍需人工抽读或离线盲测，或另行发起一次修订。 |
| 冻结材料 | 新 Worker 完整读取本任务必要资料；历史与设计按 `read`/`recall` 补读，缺资料按任务补读，不截断正文和证据。 |
| 修复与范围 | 预检、换 Worker、恢复、改约和修订不重置有限额度；超出自动范围的历史修订保存完整方案等作者授权，不能用 `resume` 绕过。 |
| 判断依据 | 逐项给原文、具体问题、影响和修订范围，不自动填 pass。漂移项必须给 `reason`，`deviated`/`skipped` 用正文引文说明实际写成了什么；机械通过不证明文学质量。 |

## 最短交接

本技能明确允许在小说创作流程中委派子 agent；沿用当前模型设置。下一任务由引擎选择，主干生命周期由宿主提供。开始或恢复前先按运行指南确认 PROJECT、授权目标与当前任务。

| 步骤 | 执行者 | 动作 |
|---|---|---|
| 取当前动作 | 主干 | `advance --compact`，已有 owner 时继续携带；按返回动作执行，不自行拼下一任务。 |
| 派工或恢复 | 主干 | 核对原执行者与 claim；仍在运行或认领有效时等待，其余新任务派空历史 Worker。未认领或租约过期不证明旧执行者已停止。 |
| 交给 Worker | 主干 | 开书门任务（opening_options）不派 Worker：主干自执（读 task.json 与同目录 brief.md → `read --task` → 从 result.template.json 起稿写 result.json → submit，session 填主干身份）。其余阶段（world_model、volume_outline、chapter_outline、write、repair、redesign）转发任务目录的 `dispatch.md`（引擎渲染的 Worker 自举卡：环境自举、步骤、认领状态、命令与常见坑）并附角色、`task_path`、一句背景；不手写环境自举或复述协议，不改写 `commands/guides`。 |
| 完成冻结任务 | Worker | 按 `dispatch.md` 自举环境后读 `task.json` 与 `brief.md`，按 `brief/required` 读取材料；从 `result.template.json` 起稿按模板写结果并执行 `commands.submit`。填真实 `session`，使用认领时附 token 裸字符串 `execution_claim`（认领由主干执行）。 |
| 核实提交 | 主干 | 无人值守连写用 `watch --owner ID`：等待与续租在引擎进程内完成，任务提交后直接带回下一 task_ready；需要显式核实时再 `advance --compact --after 该任务ID`。只收身份、提交状态或错误摘要，正文与完整回执留在项目。进程退出或口头完成不替代数据库提交。 |
| 接续或交付 | 主干 | 按 [运行动作表](references/runtime.md#动作分支) 处理选择、认可、修订、暂停和交付；章节、卷纲和卷末不是授权目标的停点。 |

Worker 提交后结束（`worker_boundary=finished`），不自行 advance。命令路径确实移动时由主干重新 advance 刷新，先核实文件，不凭路径字面判失效。

## 交付与停止

交付实际完成范围及文件绝对路径；开书范围以实际交付的卷纲为准——`scope=rolling` 时只交进入中的那一卷，不能称全书卷纲。`ready_to_complete` 仍须 `complete` 验收，再从准确快照 `deliver`；导出失败只恢复交付。

在授权目标完成、作者暂停或无法自行解决的阻碍处停止，保留任务、候选和失败原因。已有明确授权与准确版本决定时直接执行，不重复确认。未知来源数据库及旧版本不自动转换；已有项目的能力与版本边界见运行指南和 [已有项目](references/workbench.md#已有项目)。
