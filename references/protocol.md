# 任务与结果协议

何时读：约定、回执、漂移核算和报错。协议与机械清单由 contracts.py 定义，模板动态生成，不预填判断。

## 适用范围与字段来源

本页说明字段与机械核验，创作判断见 [创作与自比](craft.md)。填写时以当前任务的 capabilities、brief 和 result.template.json 为准，不自行增删字段或预填结论；格式不确定用 `check`，处理入口见 [运行](runtime.md)。

约定字段表以 contracts.py 的 CONTRACT_FIELDS 为唯一权威，模板与结构校验均由它派生。未知字段按 contract 拒绝，标为 optional 的数组/映射缺省时补空值；有 default 的字段采用表中默认值，其余按表检查必填。当前存储为 novel-ledger/3，已有 v3 可继续使用，v2 及更早数据库拒绝打开。协议版本为 `2.0.0`：v2 与 v1 是流水线换代，v1 的冻结任务（回执带 `checks_version`/`obligations`、要求首读，或阶段名为 `plan`/`book_plan` 等已删阶段的）在本版本不能执行，需按新协议重新派工。

## 作者约定

核心字段包括 title/reader_promise/ending/genre、volumes、entities、protagonist_setup、story_engine、opposition、world_premise、voice、style_traits、relationships、chapter_min/chapter_max/chapter_aim、allow_special_mechanism，完整必填项按模板检查。`tone`/`theme`/`pov` 在 opening/2 中由作者选择并逐字保留；自备约定可缺省，不追溯要求补选。每卷 id/purpose 必填，end 为递增卷末章号，没有 end 时由 word_budget/chapter_aim 推导。总字数区间 word_range 是派生字段：由章数与每章区间算出，作者与派工材料都不填，也不参与开书对齐。

| 设置 | 默认与作用 |
|---|---|
| volume_outline | `{scope:'all', words:1000, tolerance:100}`；`words` 是**每卷**汉字数，scope 为 all（一次交全部卷）或 rolling（进卷前交该卷）；空对象 `{}` 关闭卷纲 |
| chapter_outline | `{scope:'volume', words:150, tolerance:60}`；`words` 是**每章 synopsis** 汉字数，scope 为 volume 或 all |
| style_window | `{sentence:0.35, paragraph:0.35, dialogue:0.40, repetition:0.12, person:1}`（optional、不参与对齐）：文风代理指标的容差；前四项是相对偏差上限（`repetition` 为本章内部高重复的绝对占比上限，实测校准：正常散文 0.04~0.09、复读文本 0.79~0.99），`person=1` 表示视角标记必须与声明一致；卷纲 `style.window` 与契约**逐项合并**（先用契约补默认，再按合法键与合法数值逐个覆盖），作者可改约调整。见 [文风](narrative.md#文风) |
| narrative_tracking | true；关闭时章纲的 `plot.nodes`/`plot.threads` 可空，但资源/位置/知情/时钟/人物增量仍必需 |
| editorial_features | true；编辑能力要求叙事跟踪，关闭跟踪时也须关闭编辑能力；人物、场景与补丁字段见 [编辑能力](editorial.md) |
| planning_window / review_interval / review_chunk / review_fanout / verification | **保留字段，v2 基本不再读取**（legacy）：只用于加载旧项目与旧冻结任务的原字段解释，当前流程不按它们调度或分块。**例外**：`planning_window` 仍被修订边界读取（`editorial.revision_policy` 的 limit，缺省 `REVISION_LIMIT_DEFAULT`），决定自动回改的“最近 limit 章”窗口；其余四个字段没有读取点 |

t0/t1 的 `PIPELINE_SHAPES` 只保留 `merge_chapter_outline=True`：本卷卷纲与章纲由一次派工、一份回执交付，两个契约各自校验同一份回执；其余档位分两次派工。

跟踪项目按每章 word_budget 动态约束剩余总预算，允许长短章共同收口；关闭叙事跟踪时的静态规则如下。作者只定两件事：**章数**（落在档位窗口内）与**每章字数区间**（来自档位表）。总字数区间由二者派生（`章数 × [chapter_min, chapter_max]`）。完本核对的也是这两件事：章数写到位，且每一章都在区间内（后者在章节提交时逐章检查）。

entities=[{id,name,kind,aliases?}]、initial_facts=[{entity,key,value}]、initial_resources=[{holder,asset,unit,quantity}]、places=[{id,name,parent?}]、placements={entity:place} 只放已成立事实。quantity 为十进制字符串。world_rules/red_lines/arcs 是字符串数组，voice 保存文风。字面规则不属于约定：它是项目级 book.lexical_policy 的版本记录，用 `lexical --file 规则.json --source 原话` 修改，约定里出现 lexical_policy 会被结构校验拒绝。新人物不再有独立的档案派工，改由章纲 `new_entities` 内联声明。

protagonist_setup={id,name,identity,desire,limit} 保存主角身份、欲望和底线；relationships 为关系约定数组，style_traits 为文风特征数组。tone 保存给读者的基调，theme 保存母题，pov 保存叙述视角与人称（谁在讲、能看多远，换视角时如何交代）。完整约定可参考 [示例约定](../assets/contract.example.json)，按作者真实要求替换，不沿用示例题材和篇幅。

## 冻结任务与资料读取

task.json 给身份、路径和 commands。records 提供冻结哈希，required 给必读名称，prose 和 obligations 给正文及义务。brief 说明当前任务规则，任务目录同时物化 `brief.md`（同一简报的 markdown 全文，直接读它，不解析 input.json）与 `dispatch.md`（Worker 自举卡：环境自举、步骤、认领状态、命令与常见坑）；重派未提交任务时，上次遗留的回执草稿由引擎隔离为 `result.stale.json`（派工卡会注明）——它不是进度也不是判断依据，从模板起稿。guides 作为相关章节的参考，不重复通读全部文档。

主干使用 advance --compact 获取精简 task；开书门任务（opening_options）由主干自执，其余阶段把 task_path 交给子 agent；磁盘 task.json 始终完整。新任务使用新会话：`requires_new_worker` 保留，一个会话只做一个任务（跨任务复用按 session_reuse 拒绝）；首读与 `review_session` 已随审查阶段删除。claim 只表示执行认领，须结合宿主中的子 agent 状态判断是否仍在执行，主干循环及动作分支见 [运行](runtime.md)。

工作台能力 `understanding/1`、稳定场景身份 `scene-identity/2`、阅读关联 `reading-dependencies/1`、作品理解字段见 [叙事工作台](workbench.md)。能力及规范化计划的 reading_schema 按版本解释，不追补旧回执或重解释旧计划的同名字段。新开书方案的篇幅上界另由 opening-bounds/1 冻结，见 [逐门开书](opening.md)。

场景任务携带 capabilities.scene_memory=scene-memory/1；scene_context/scene_sources 为冻结的场景输入和已提交来源，字段及 dependency_coverage 见 [叙事推进](narrative.md#场景依赖与任务材料)。revision-impact 的输入、采用范围与保守扩展规则见 [运行](runtime.md)。

每个任务材料的 `policy` 块是当前生效的项目字面约定：`version`/`source` 说明版本与来源（作者原话或内置默认），`forbidden_terms`/`forbidden_name_chars` 给出规则，`scope` 说明**本阶段实际检查哪些字段**。该块与执行检查共用 `contracts.ENFORCEMENT` 一张表，所以声明与校验不会脱节；越出 scope 的字段不检查，违反 scope 内字段以 `literal_policy` 拒绝并在 details 里列出命中字段与命中词。改规则用 `lexical` 命令。

`read --task ID` 只返回本任务**尚未拿到过**的必读记录（跳过的名字列在 already_read，需要原文用 `--record 名称` 或 `--all` 取回）；返回里的 `records_hash` 是本任务全部可见记录哈希的一并摘要——主干同一会话连跑多个任务时，与前一次相同且必读名单未变即可跳过本次 read；`--record 名称` 读单个完整记录。`recall --task ID --chapter N` 读冻结目录中的完整历史章，`--state` 读完整前态。新任务的可选 history_source 以哈希冻结逐章目录，旧任务仍使用自身索引；分页检索与承诺关联见 [叙事推进](narrative.md#历史补读)。必读 state 按参与人和相关开放承诺选择，派工 baseline 也取该冻结视图，complete_state 永远可补读。结构选择不证明其他事实语义无关；跟踪项目 story 包含目标及直接前提，已兑现结果见投影状态，全部祖先和完整设计仍有补读入口。当前 state 是视图，不冒充全部资料。

hash 是规范 JSON 的 SHA256：UTF-8、ensure_ascii=False、sort_keys=True、紧凑分隔符、allow_nan=False。正文哈希也基于 JSON 字符串值，不是裸文件字节。来源完整性不证明阅读理解。

## 回执与格式自检

```json
{
  "schema": "novel-ledger.result/1",
  "task_id": "本任务ID",
  "input_hash": "本任务哈希",
  "session": "真实宿主会话ID",
  "data": {}
}
```

使用执行认领时附 execution_claim。preflight 完整校验后回滚，checked 不等于入库；submit 才更新。相同已提交结果幂等，不同结果拒绝。拒绝不计修复额度，真实短稿提交计实际执笔轮次并保留稿件。

submit 的 accepted=true 表示回执已接受，不等于正文通过：字数区间与 `lint` 命中按名返修，章纲漂移与漂移核算不符会被直接拒绝；设计类候选（世界、卷纲、章纲）返修额度用尽或停滞时由 `advance` 返回暂停停点。

`check` 是给 Worker 的格式自检：把候选回执从标准输入管道进去（无需 `--file`，已通过身份环境定位当前任务时可省略命令行 `--task`）。回执本身仍须提供 task_id 和 input_hash（信封字段从 result.template.json 复制起稿，不手写；`input_version` 报错带 expected），不允许猜测或改投身份；会话取自身份进程或任务自身。它按与 submit 相同的校验运行但**不提交、不消耗额度**，直接报告缺哪个字段或哪个枚举不对，让执行者不必读引擎源码确认格式。常见拒绝对应的期望形状：前值不匹配时 details 带 `current`（照抄为 before，新键为 null）；章纲漂移带具体项、卷内位置与模拟到该章的状态；`opening_option`（choose）带 `valid_options`；`literal_policy` 带命中字段与命中词。报错里没有的形状不要去源码里找，用 check 试算。

历史修订的 revision_range 表示请求未覆盖已登记目标或回退到无关前文；revision_bounds 表示不能用 resume 跳过超界方案；revision_proposal 表示方案哈希、范围、变更或来源不匹配；author_source 表示缺少配套的方案哈希和作者原话。revision_blocked 是已保存方案的业务动作，不是回执格式拒绝；恢复步骤统一见 [运行](runtime.md)。

| 阶段 | data |
|---|---|
| opening_options | 当前门 gate 与 2～3 个 options，详见 [逐门开书](opening.md) |
| opening_contract | 默认随世界起草；单独派发时读冻结的已采纳世界，模板由 CONTRACT_FIELDS 派生 |
| world_model | 完整世界记录；默认同时起草 data.contract（payload.also），提交时由引擎机械校验引用、领域与选择一致性 |
| volume_outline | `volumes[]`：id/purpose/arc/turns/climax/nodes/threads/**hooks**/style/resources/places/characters/knowledge/clock/exit_state；`hooks` 必填可为空（`{id,text,plant,payoff,required,continues}`），`style.trend` 必填；每卷约 1000 汉字，校验见 [叙事推进](narrative.md#卷纲) 与 [伏笔账](narrative.md#伏笔账卷纲声明章纲执行) |
| chapter_outline | `volume` + `chapters[]`：synopsis、plot.beat、四个增量数组、enter/exit、disclosures、world_refs、new_entities、**hooks**、**style**；`hooks` 必填可为空（`{hook,action:plant/payoff,note}`，只有这两个动作），`style` 的 `pov`/`rhythm` 必填；每章约 150 汉字，状态链见 [叙事推进](narrative.md#章纲) |
| write / repair / redesign | title/完整 prose/summary/drift_check/具体 self_check；工作台模式下可带顶层 `understanding` 增量（引擎在入库时更新作品理解）；提交时机械判定字数区间、跨章逐字重复（≥25 字）、对白引号体例、西文残留，核算漂移，并跑文风代理指标（见 [文风](narrative.md#文风)） |

有世界模型时，章纲须声明 world_refs=[领域:id]，引用须存在，所选关联记录完整保留。返修必须逐项回应引擎拒绝的具体项（漏项、前态不符、体例或字数命中），不重交原样候选。

## 漂移核算

`drift_check` 是执笔回执里唯一的自比结构，字段与拒绝码见 [叙事推进](narrative.md#执笔自比与引擎核算)。要点：

- `items` 恰好覆盖本章纲的全部计划增量（kind+key 各一次）；漏项/多项 → `drift_coverage`。
- `actual.from` 必须等于引擎投影的当前真实值，不由写手自报前态；不等 → `drift_before`。
- `status=kept` 时 `actual.to` 等于 `planned.to`；`deviated`/`skipped` 必须给 `reason` 并登记进 `book['design_drift']`。
- `unplanned` 每项按同一规则核算；未登记的计划外变化会在下一次章纲校验时暴露。
- `kind='hook'` 的行用动作而不是前后值：`planned={'action':'plant'|'payoff'}`、`actual={'action':…}`，`evidence` 仍是正文引文。伏笔事件由 `drift.reconcile` 从章纲行与 `drift_check` **产出，写手不手写事件**。
- `evidence.quote` 是正文原文片段，走精确引文校验。

## 结算与时钟

事件来源是 `drift_check.items`（含 `unplanned`），由引擎按既有机械判据结算：资源不透支、时钟不倒退、位置存在于世界、知情不倒退（`retracted` 除外）、人物变化必须有 `choice`/`cost`、node 不重复推进、thread 关闭后不重用、伏笔按 `plant`/`payoff` 转 `open`/`paid`（`{'op':'hook', id, status, due, text, reason, evidence}`，延期最多两次，到期未兑现报 `hook_due`）。**不再有独立审稿者提交事件回执**，读者侧的节奏核验也随章审一起删除。

伏笔事件由 `drift.reconcile` 产出，所以 `state.hooks` 对新书不再是空集，bookpage 的承诺区照常渲染，`complete()` 的“未交代承诺”检查对新书是真实检查；卷末 `required` 未兑现由章纲的卷内状态链收尾拒绝。见 [伏笔账](narrative.md#伏笔账卷纲声明章纲执行)。

elapsed_days 等于主线时钟增量。引文真实、时间词存在及数值一致只证明机械条件；知情、代价与路径是否成立，v2 没有独立判断，只能由作者抽读正文确认。

state.clock 是从初始状态起累计的内部天数，不是章号，也不要求正文逐章报日期。同日续接允许 elapsed_days=0 且不交 clock 增量；发生推进时，`clock` 的增量由执笔在章纲里声明、在自比里核对，不从章号推算。章纲的 `enter`/`exit` 与卷内模拟是这一幕的机械锚点，见 [叙事推进](narrative.md#卷内状态链与校验)。
