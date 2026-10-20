# 实机验证复盘（2026-10-17）：一个三章小项目为什么花了 81 次派工与 650 万字符

> 历史归档：本文件保留当轮版本、设计或实验条件，不是当前执行规范。旧门序、兼容条款、独立审查阶段及命令均不用于当前流程；当前唯一执行依据见 [任务协议](../references/protocol.md) 与 [运行流程](../references/runtime.md)。

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

## 三、架构层面：为什么会发生，以及怎么从结构上避免

上面五条是现象。把它们按**同一类原因**归并之后，只剩四条根因；每条都给出"已经做了什么"和"还应当做什么"。

### 根因 A：投递关系不是声明，而是"逐阶段手写的布尔表达式 + 整份转储的读取语义"

材料的**生产**有单一权威（`CONTRACT_FIELDS`、世界模型、设计文档），但**投递**没有：`context.build` 里
每个阶段用一行行 `add(name, value, stage in (...))` 决定必读，而 `read` 的语义是"把这个任务的必读整份给我"。
于是两件事必然发生：加一个阶段就顺手多带一份（投影与源同场，实测 90,456 字符）；worker 读第二次就再付一次整份（实测 33%）。

- **已做**：`PROJECTIONS` 声明表把"谁是谁的投影"变成一处决定；`thin_required` 一趟同时收敛"内容相同"与
  "源在场"两种重复；`read` 只交未读，`--all`/`--record` 显式重读；夹具把"必读无内容重复"变成每次派工都要过的不变量。
- **还应当做**：把"这一阶段判断所必需的记录"也变成声明（`阶段 → 判据集`），与"背景材料"分开；
  守卫断言"必读 ⊆ 判据集 ∪ 明示的背景集"，且不含任何投影/源重复对。判据与背景分开之后，
  来源 3 的裁剪（审一章不再付 56K）就变成改表而不是改代码。
- **为什么这是解耦问题**：现在的耦合不在模块之间，而在**"谁能读什么"这条链上**——生产者改字段，
  投递端不会红；投递端多带一份，只有账单会说话。

### 根因 B：成本结构与体量脱钩（管线形状是常量）

门数、世界领域数、设计层数、审查层数、每阶段返修额度，全都不随体量变化；`scale` 门只决定章数与每章区间。
于是微型档成为**固定成本占比最高**的项目：59/81 次派工在第一个字之前，每千汉字 7.8 次派工、63 万读取字符。

- **还应当做**：把体量档位提升为**管线形状的输入**——与 `SCALE_TIERS` 同源的一张 `档位 → 阶段集与额度` 声明表；
  小档下合并产出比低的层（世界与约定已合并，下一层可合并骨架与卷设计），返修额度按"该阶段的产出规模"给。
  守卫：新增阶段必须声明它属于哪些档位，否则测试红。
- **一条判断**：审查的**独立性**不与审查的**层数**成正比。三章的书需要"设计一次独立审 + 每章一次独立审"，
  不需要五层设计审查；层数应当由体量×风险决定，而不是由协议一律给定。
- **风险与边界**：合并只能在"产出与判据同源"的层之间做（同一份设计的两次审查），
  不能把"作者约定对齐"与"事实核验"合并——那两类判据不同，合并会真的削弱独立性。

### 根因 C：停止条件没有配"作者通道"（同一类死路，实机撞到三次）

| 实例 | 触发条件 | 当时的两条出口 | 结果 |
|---|---|---|---|
| 世界候选 | 返修额度用尽而意见仍在收敛（14→7→4→3，0 blocker） | 改约（重做开书）／开书回退（重做 4 门） | 死路，作者无通道 |
| 第三章 | 章级返修 2 轮 + 重设计 1 轮用尽，只剩 2 条局部修订 | 放弃整章候选／改约 | 死路 |
| 修订运行中 | 本次修订的范围复核在**运行范围之外**发现问题 | `revise` 拒绝（有在途修订）／`promote` 拒绝（有未决缺陷） | 死路，只能 `discard` 丢掉已通过的章节 |

三处出口的形态**完全一样**：再给一轮／接受并把意见记为未解决项／重开或撤销。
这说明它不是三个特例，而是一条可以形式化的规则：

> 凡是因为**额度、范围或未决问题**而"引擎不再自动往下走"的位置，都必须生成一条结构化作者决定；
> 选项组合固定为这三类，且"接受"必须把意见写进可核对账本（`carry_findings` / `accepted_findings`），
> 在 `status` 与完本篇审计里可见——**接受不等于通过**。

- **已做**：三处都接了（`repair-exhausted:world_review|design_review|outline_review`、
  `repair-exhausted:chapter_repair`、`scope-findings:open-revision`），接受的条目在 `status.accepted_findings`
  与完本篇审计的 `accepted_findings` 里显式列出。
- **还应当做**：把这条规则做成**声明 + 守卫**——列出所有停止点（额度、范围、未决、悬置），
  测试断言"每个停止点在触发时都能生成 author_block"，这样下一个新加的停止点漏接通道会当场红。

### 根因 D：状态迁移的副作用没有原子表达

状态迁移会连带作废别的东西（裁决推进版本 → 在途任务失效；恢复 → 暂停原因失效；改约 → 旧候选失效），
但这些连带关系散落在各命令的实现里，于是出现：白派一个 Worker（`stale_task` 到读取时才发现）、
`status=running` 却留着 `pause_reason`、被截断的 `before/after` 看起来仍像完整值。

- **已做**：记录裁决时直接作废裁决前派出的任务并在返回值里回报 `retired_task`；恢复路径统一清暂停原因；
  改约预览保留完整值、截断显式标注。
- **已做（不变量）**：`book_state.check_state` 在每次读 `status` 时校验
  "运行中不得带暂停原因、暂停必须有原因、接受过的条目必须有阶段/范围/意见、候选稿必须指向章号"。
  **这条不变量落地当时就抓出第四处同类残留**：review 驱动的修订路径（`revision_service.begin`）
  同样把状态改成 running 却留着上一处暂停原因——说明"靠纪律记得成对修改"确实是不可靠的，必须由引擎保证。
- **还应当做**：把不变量扩到在途任务（`pending.revision == book.revision`），
  让"派工与状态版本必须一致"也由引擎而不是由顺序纪律保证。

### 根因 E：主控与引擎的分工没有可核对的接口

最后一个实例值得单独记：我把一个 `scope=revision / chapter=3` 的修订复核任务描述成"全书终审"，
Worker 按 `task.json` 与冻结材料纠正了我（该任务没有 closure、没有 sources，证据被冻结在第三章，
带前两章引文会被 `evidence_scope` 拒绝）。**引擎的守卫是对的，派工描述是错的。**

- **还应当做**：派工描述应当由**任务自身**渲染（`task.json` 已有 `stage/scope/chapter/first/last/required`），
  主控照念即可，而不是按"流程应该走到哪"去想象；把这段标准化说明放进派工模板，
  主控就不必也不该自己拼。这是"接口可核对"的问题，不是提示词技巧问题。

### 根因 F：最小体量档与"作者可能提出的作品形态"不匹配（本轮最后发现，也是最严重的一条）

作者中途把体量改成"三章完本、每章三千到三千五百汉字"（约一万字），改约经独立核验通过、正文写完并过了逐章审。
但**档位表里没有能表达这个形态的档**：最小的 t0 微型是从 34,000 字、14～19 章起步的。
契约层（`planning.validate_contract`）不检查章窗，所以改约能过；而完本审计（`creation.validate_contract`）
在 `version>=2` 时要求"全书章数落在该档章窗内"，否则报 `opening_alignment 全书章数与所选体量档位不相容`。
也就是说：**作者能改到那个体量，但引擎随后会拒绝这本已经写完的书**（`promote` / `complete` 都会撞上）。

本轮之所以没撞上，是另一个 bug 掩盖了它：第二次改约把已核验的世界丢了（本轮已修），
而那段档位校验在 `if book.get('world')` 分支里——世界不在，校验整体被跳过。
这正是"两个缺陷互相遮蔽"的典型：单个看都还能跑，合起来才是完整的失败链。

- **已做**：把微型档扩成能覆盖短篇形态（`word_range [6000, 59500]`、`chapter_window [2, 19]`，推荐仍是 17 回），
  这样"两三章的短篇"到"十七回的微型连载"都在同一档内合法；`references/opening.md` 写明这一条。
- **还应当做**：档位表与"作品形态"之间应当有一条更明确的关系——现在的档位同时承担"推荐体量"和"合法性边界"两个职责，
  所以要么补齐形态（本轮做法），要么把"作者书面指定的体量"作为一等授权记录在契约上，让审计按授权而不是按推荐区间判断。
  后者更灵活，但要连带处理"授权与推荐不一致时下游各阶段怎么读"。

这套引擎的**判据权威**（字段表、检查清单、阶段注册表、能力表）已经做得很扎实，
但**投递权威**和**停止权威**还留在实现细节里：谁读什么、什么时候必须停下、停下之后谁说了算。
本轮把后两者各推进了一步（声明化的投影关系、模式化的作者通道），并把它们写成可复跑的账。

更根本的一条（根因 F）：**引擎对"作品形态"的合法性边界写死在档位表里，而档位表只覆盖它预设的连载形态**。
凡是这样写死的边界，一旦作者提出边界外的形态，就会出现"能改到、能写完、但关不掉"的最坏组合——
改约与审计读的不是同一份判据，而且两个缺陷还会互相遮蔽。

---

## 四、本轮已落地的修复（可复跑）

| # | 修复 | 位置 | 证据 |
|---|---|---|---|
| 1 | `read` 只交未读记录，`--all` / `--record` 显式重读 | `application.read`、`ports.Repository.read_names`、两个适配器、CLI | 实测可省的整份重复 2,138,558 字符（33%）；`test_a_second_full_read_only_hands_over_what_is_still_new` |
| 2 | 投影关系声明化 + 必读一趟收敛（内容相同、源在场都不再重复） | `context.PROJECTIONS` / `context.thin_required` | 实测重复 90,456 字符 + 投影 11,199 字符/次；`test_required_material_never_charges_twice_for_one_fact`；夹具不变量 `required_material` |
| 3 | 改约只交差异，截断显式标注 | `application.recontract`（`contract_amendment`） | 42 次读取 935K 的改约审现在可只核差异 |
| 4 | 设计候选额度用尽的作者通道 | `workflow.hold_for_exhaustion` / `allow_another_repair` / `accept_with_findings` | 世界候选实机死路；`test_a_spent_repair_budget_hands_the_decision_to_the_author` |
| 5 | 章级额度用尽的作者通道 | `workflow.hold_for_draft_exhaustion` / `resolve_draft_exhaustion` | 第三章实机死路；`test_short_prose_preserved_and_rework_is_bounded` |
| 6 | 修订运行中范围缺陷的作者通道 | `workflow.hold_for_scope_findings` / `accept_scope_findings` | 第二章实机死锁（revise 与 promote 双向拒绝）；`test_a_revision_with_out_of_range_scope_findings_asks_the_author` |
| 7 | 接受过的条目在 `status` 与完本篇审计显式列出 | `application.status` / `_audit` | 接受不等于通过 |
| 8 | 记录裁决时作废裁决前派出的任务并回报 `retired_task` | `application.answer` | 一次白派 Worker（`stale_task`） |
| 9 | 恢复路径统一清暂停原因；裁决与派工顺序写进运行指南 | `application.resume` / `recontract`、`references/runtime.md` | `status=running` 却留 `pause_reason` |
| 10 | 状态不变量在每次读 `status` 时校验（运行中不得带暂停原因、暂停必须有原因、接受条目有阶段/范围/意见） | `book_state.check_state`、`application.status`；新增 `application → book_state` 依赖作为显式架构决定 | 落地当场抓出第四处同类残留（`revision_service.begin`），已修；`test_book_state_invariants_are_checked_where_the_state_is_read` |
| 11 | **投递材料声明表**：每个阶段必须声明它判断所必需的记录，与目录 shape 一样作为完整性要求 | `context.STAGE_MATERIAL` / `undeclared_material`；守卫在 `support.check_dispatch`（每次派工）与 `test_every_stage_declares_the_material_it_must_read`（阶段完整性） | 给一个阶段多带材料从此要改表；表由 19 个阶段的实测必读集固化 |
| 12 | **世界丰富度下限按档位**：域表由 `world.TIER_SECTIONS` 按体量决定，简报与校验读同一份声明 | `world.required_sections`、`briefs.world_model(sections=...)`、`context.scale_tier`、两处 `world.validate`、`references/world.md` | 微型档只要求 6 个域；`test_world_only_fills_the_sections_its_tier_requires` |
| 13 | **停止点登记表 + 守卫**：每个停止点必须声明作者通道，且通道本身要被解释 | `workflow.STOP_POINTS` / `AUTHOR_CHANNELS`、`test_every_stop_point_declares_where_the_author_decides` | 下一个新停止点漏配通道会当场红 |
| 14 | **派工说明由任务自身渲染**：`identity.task_line` 由冻结任务生成，主控照念而不是按流程位置想象 | `delivery.task_line`、`envelope.IDENTITY_FIELDS` | 一次把 `scope=revision` 说成"全书终审"的描述错误 |
| 15 | **改约审只核差异**：改约审读世界核心与 `contract_amendment`，整份世界模型转按需 | `context.build`（`amended` 分支） | 契约审的必读里最大一份（47,636 字符）不再默认投递 |
| 16 | **在途任务与项目版本一致性**：`status` 校验 `pending.input.revision == book.revision` | `application.status` | 与修复 8 同源；白派 Worker 在引擎侧不再可能 |
| 17 | **补齐最小的体量档**：微型档章窗 [2,19]、字数下限 6,000，使"两三章的短篇"可以落地 | `contracts.SCALE_TIERS`、`references/opening.md` | 见下节：档位表原本从 34,000 字 / 14 章起步，作者要的三章完本在协议里无处表达 |

## 五、还剩什么（按结构收益排序）

1. **管线形状随档位收缩（根因 B 的另一半）**：世界域表已经按档位（修复 12），剩下的层数问题——
   单卷小书要不要把骨架与卷设计合成一次派工——需要改协议并做一次实机验证才敢动。
   一条判断不变：合并只能在"产出与判据同源"的层之间做，别把"约定对齐"与"事实核验"并成一次审。
2. **停止点守卫再往前一步**：现在登记表保证"声明过的停止点有通道"；下一步是让新增停止点**必须**登记
   （例如把生成 `author_block` 的位置收成一个函数，未登记 id 直接拒绝）。
3. **审稿位的判据集继续收窄**：`chapter_review` 仍是 16.6 倍于被审文本；材料表现在让这件事可见且可改，但还没有改。
4. **体量与额度的关系**：返修轮数目前按阶段固定；小书真正贵的是返修轮数（实测世界 4 轮、第三章 3 轮），
   而额度收紧只会造成死路——正确方向是"让第一稿的规模与档位相称"（修复 12 是这条路的第一步）。
5. **派工模板化**：修复 14 给了 `task_line`，还可以把主控派工说明整段交由引擎渲染。

## 六、复现

```bash
python3 validation/run_analysis.py   /path/to/project   # 分阶段材料、读取、生命周期、磁盘
python3 validation/read_waste_probe.py /path/to/project # 重复读取的字符与占比
python3 validation/dup_required_probe.py /path/to/project # 必读里内容相同的重复
python3 validation/required_probe.py /path/to/project write,chapter_review # 指定阶段的必读构成
python3 validation/cost_report.py /path/to/project      # 单项目的按阶段与磁盘汇总
```
