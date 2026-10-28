---
name: novel-ledger
description: >-
  在用户要求开书、续写网络小说、修订正文或恢复小说项目时使用。通过十三门设定、世界模型、卷纲与章纲，按作者授权写作并交付；支持单 Worker 分组快速无人值守（组大小可配，默认五章）。
---

# novel-ledger

主链：**十三门开书 → 世界模型与作者约定 → 卷纲（作者认可门）→ 当前卷章纲 → 首章认可 → 无人值守写作 → 完本交付**。卷纲回执过机械校验后暂存待作者 `confirm-volume` 认可（可 `revise-volume` 轻调叙述面、`regroup-volume` 带理由重出，看板物化在 work/volume-board.md）；小体量可合并卷纲与章纲派工，按冻结任务执行；已有设定直接沿用，只补真实缺口。讨论小说或技能本身不表示启动创作。

ROOT 是本技能绝对路径，PROJECT 是独立小说目录。入口为 `python3 ROOT/scripts/novel.py --project PROJECT 命令`（Windows 用 `python`），运行仅依赖 Python 3.9+ 标准库，正文项目不放技能目录。

## 当前任务只读当前材料

执行以本入口、当前冻结任务及对应指南为准。Worker 先读 `task.json`、`brief.md`，用生成的 commands 读取完整 required，从 `result.template.json` 起稿。任务卡提供本阶段交付信息；开书创意说明只在 [创意工具箱](references/hatch.md)，首次出案时读取，同一会话已读且版本未变可复用。其他 `guides` 按疑点补读相关小节，不遍历源码、测试或历史报告猜格式。

| 当前阶段 | 按需入口 | 关键交付 |
|---|---|---|
| 开书、导入设定 | [逐门开书](references/opening.md)；构思或换组时读 [创意工具箱](references/hatch.md) | 主干自执门任务，真实作者选择后推进；不重复询问已有决定。作者显式委托时按开书指南的委托自决通道逐门登记推进。 |
| 世界模型 | [世界模型](references/world.md) | 在同一任务推演历史选择如何留下当下制度、利益与生活约束；按要求同时交付作者约定。 |
| 卷纲、章纲 | [卷纲因果设计](references/craft.md#卷纲因果设计) 与 [十三门承接](references/craft.md#十三门世界与卷纲的承接)；字段与状态链查 [叙事推进](references/narrative.md) | 从当前约定、世界与前卷后果推演核心问题、双方行动、选择代价和兑现，再映射字段；章纲固定本章事实、变化与结果。 |
| 首章、后续执笔、当前章返修 | [创作与自比](references/craft.md#执笔)；写作纪律唯一源见 [文风](references/style.md)，格式疑点查 [协议](references/protocol.md) | 首章由作者认可准确版本以定调；后续沿人物处境写作、逐项自比，局部问题按影响范围修。 |
| 续写、无人值守、恢复、交付 | [运行与恢复](references/runtime.md#主干循环默认执行路径) | 按真实 action 接续授权目标，完成验收和交付后结束。 |

## 无人值守执行

连续写作先按 [固定运行版本](references/runtime.md#固定运行版本与受控切换) 建立开发树外的固定副本，以返回的 runtime_root 为 ROOT；写作期间不改引擎或判据绕过失败。

按 [主干循环](references/runtime.md#主干循环默认执行路径)、[任务交接](references/runtime.md#任务交接) 与 [动作分支](references/runtime.md#动作分支) 执行，具体命令、租约和恢复步骤只在运行指南维护：

- 主干管理授权目标与治理；开书门任务按开书指南自执，后续阶段委派真实独立 Worker，沿用当前模型设置。派工能力与历史隔离属于会话层，首次派工前按 [宿主能力检查](references/runtime.md#宿主能力与执行状态) 核实；能力缺失时保留任务并报告，不编造身份。
- Worker 只处理当前冻结任务；主干提供宿主真实身份与引擎返回的凭据，不手写另一套自举协议。正文阶段的长起草租约见 [执行身份与技术恢复](references/runtime.md#执行身份与技术恢复)。
- 等待由引擎侧有界 watch 承担。idle、未认领或租约过期均不证明原执行者已停止；先核实宿主状态，再决定等待、恢复原会话或重派。核验完成需重交时先唤醒原执笔者。
- 快速组只在 `worker_boundary=continue` 时沿 `commands.worker_next` 接续；`finished` 只结束当前 Worker。主干继续当前授权目标，直到实际交付、作者边界或无法恢复的阻碍；宿主中断如实交接。

## 后台保障

这些机制在后台随主链运行，遇到作者边界再交给作者：

- **事实与来源**：SQLite 是唯一持久真源；正文与事实由 submit 原子提交，不手改库。设计、人物档案、作品理解不自行成为事实；完整正文与证据保留，按冻结来源补读。
- **固定章纲与有限返修**：先核验章纲状态链，再执笔与核账。偏差附原因、正文引文与范围，不能自动改纲迁就正文；核账说明留在回执，正文呈现人物实际经历。预检、恢复或换 Worker 不重置额度，耗尽或超范围交作者决定。
- **独立连续性核验**：默认不执行；新 CLI 项目与旧项目均不自动开启，作者明确要求时以 `init/assurance --continuity required` 显式开启。开启后 `review_required` 实际派独立读者；`review_in_progress` 用 watch 等待；`review_author_required` 交作者裁决；`review_complete` 由原执笔者重交准确候选。主干与执笔者不代签，具体见 [核验交接](references/quality.md#主控与执笔交接)。
- **结果判定**：submit/preflight 看 outcome 与总 findings，正式章节看 committed_chapter，不用 accepted 或口头完成推断正文通过。不自动填 kept/clean/pass。身份与技术错误按 recovery 返回处理，完整性失败保留现场。
- **作者与文风**：只推进已有授权，已有准确选择和首章认可直接登记。写作纪律唯一源是 [文风](references/style.md)：档案来源、选择及切换按该页执行；数值形状默认只观察，不增加逐章“去 AI 味”评分或整章润色任务。机械通过不证明文学质量。

## 按需操作与开发

仅在任务涉及下列操作时加载；普通写作不逐项阅读：

| 触发情况 | 入口 |
|---|---|
| 作者要求改约、暂停或修改字面规则 | [暂停与修改](references/runtime.md#暂停与修改)；保留原话、范围和版本。 |
| 作者要认可卷纲、轻调叙述面或带理由重出；选定/更换蓝图 | [动作分支](references/runtime.md#动作分支) 的 await_volume_confirm 行与 [叙事推进](references/narrative.md#校验与失败)；蓝图一套两层（结构骨架／作者确认的设计参考），档名见 [创意工具箱](references/hatch.md#蓝图目录)，`blueprint --regenerate` 只删无正文各卷的设计。 |
| 作者要求改写历史正文、分析影响或采纳候选 | [修订影响分析](references/runtime.md#修订影响分析)；原稿保留，超范围方案等待准确授权。 |
| 作品理解、原文样本或场景身份需要维护 | [叙事工作台](references/workbench.md)；解释与已成立事实分开。 |
| 执笔文风：内置文风库选定（缺省默认档，唯一文风源） | [文风](references/style.md)；按生效档案读取声线、口癖与 MUST/AVOID，选档、换档与新增内置档案见该页。 |
| 当前任务涉及人物/空间字段、版本补丁 | [编辑能力](references/editorial.md) 对应小节。 |
| 接入可信执行宿主 | [质量与宿主](references/quality.md#受控宿主的部署契约)。 |
| 修改引擎、核对能力或排查消耗 | [架构](references/architecture.md)、[返工与成本](references/rework.md)、[验证](references/validation.md)；按变更范围运行检查。 |

工程测试和历史验证材料不进入日常写作上下文。历史规格与实验仅保存当轮证据，不作当前规范；查历史证据时从 [验证指南](references/validation.md) 定位。

## 交付

提供实际完成范围与文件绝对路径。book.html 是按需读取数据库的轻量预览入口；用 `preview --open` 查看，完整离线视图显式导出。开书交付按实际卷纲覆盖说明，rolling 不能称全书设计完成。

`ready_to_complete` 仍执行 complete，再从准确快照 deliver；导出失败只恢复交付。目标、候选与失败原因随停止状态保留，已有授权不重复确认。详细操作见 [阶段结束与交付](references/runtime.md#阶段结束与交付)。
