2.1.2选择性合并远端租约心跳、内容错误分类和完整材料包；保留2.1.0的独立核验、执行世代与构建约束。

# 任务与结果协议

2.1.0增加独立连续性辅助协议 `novel-ledger.continuity/1`，不改SQLite /5格式，不给旧任务追填报告。新CLI项目默认要求此核验；命令、双阶段模板与宿主证明契约见[质量与宿主](quality.md)。冻结input可含build（version/engine_hash/rules_hash），构建变化拒绝继续该任务。

提交统一返回outcome、当前总findings、transaction、next_action与effects_if_submitted；旧valid/accepted/committed保留兼容含义。outcome包括design_accepted、candidate_ready、chapter_committed、repair_required、author_decision_required、continuity_review_required；旧完成任务没有新结果快照时，重放返回receipt_replayed并标legacy_outcome_unknown，不猜是否当时入章。成功回执重试返回原确认，不重耗轮次。

何时读：约定、回执、漂移核算和报错。协议与机械清单由 contracts.py 定义，模板动态生成，不预填判断。

## 适用范围与字段来源

本页说明字段与机械核验，创作判断见 [创作与自比](craft.md)。填写时以当前任务的 capabilities、brief 和 result.template.json 为准，不自行增删字段或预填结论；格式不确定用 `check`，处理入口见 [运行](runtime.md)。

约定字段表以 contracts.py 的 CONTRACT_FIELDS 为唯一权威，模板与结构校验均由它派生。未知字段按 contract 拒绝，标为 optional 的数组/映射缺省时补空值；有 default 的字段采用表中默认值，其余按表检查必填。当前存储为 novel-ledger/5，通过不可变结构分块共享累计快照；文档哈希仍对应完整逻辑值，任务和回执不感知分块。仅支持当前库，v4 及更早数据库拒绝打开并保留原文件，不自动转换。CLI 版本为 `2.0.0`，只运行当前阶段与任务能力；旧门序、旧字段及独立审查阶段的任务直接拒绝，须以当前模板重新派工。开书协议版本为 `opening/6`（`novel-ledger.creation/6`，13 门，世界与格局先于主角来历），是唯一支持的协议：声明更早 creation 版本的项目在读取时被明确拒绝，以当前协议重开；自备约定不经门序核验，缺省的结构化开书字段不追溯补选。

## 作者约定

核心字段包括 title/reader_promise/ending/genre、volumes、entities、protagonist_setup、story_engine、opposition、world_premise、voice、style_traits、relationships、chapter_min/chapter_max/chapter_aim、allow_special_mechanism，完整必填项按模板检查；`protagonist_origin` 由来历门产生，`core_premise`/`world_scale`/`world_ladder`/`world_tiers`/`world_resource`/`promise_anchor` 由对应门产生，`world_architecture` 由世界门产生，见下表。`tone`/`theme`/`pov` 分属题材门（genre）、兑现门（payoff）与视角门（voice）选择并逐字保留；直接导入完整约定时，非必填的开书决定可缺省。每卷 id/purpose 必填，end 为递增卷末章号，没有 end 时由 word_budget/chapter_aim 推导。总字数区间 word_range 是派生字段：由章数与每章区间算出，作者与派工材料都不填，也不参与开书对齐。

| 设置 | 默认与作用 |
|---|---|
| protagonist_origin | `{family, arrival, cost}`（**optional、参与对齐**）：`family` 只能是"魂穿"/"身穿"/"本土"/"其他"之一，`arrival` 是"怎么来、带来了什么"，`cost` 是代价或麻烦；来历门的 value 整份投影到本字段（`opening: ('origin', None)`）。直接导入完整约定时可缺省 |
| core_premise | `{novelty, first_cause, stance, dark_side}`（**optional、参与对齐**）：核心脑洞四问。`novelty`/`first_cause` 各 ≥12 字符；`stance` ∈ 顺从/利用/对抗；`dark_side` ∈ 外神/天灾/系统/上层剥削/制度/人心。脑洞门的 value 整份投影（`opening: ('premise', None)`） |
| world_scale | `{opening, terminal, unchanged}`（**optional、参与对齐**）：`opening` 第一章读者能看见的边界（≥8 字符）、`terminal` ∈ 局部/势力/体系/文明、`unchanged` 跨卷不变的上层结构（≥8 字符）；格局门的 `scale` 投影（`opening: ('ladder', 'scale')`） |
| world_ladder | rows（`blank: False, count: 1`；**optional、参与对齐**）：行 `stage`/`scope`/`growth`/`new_rule`/`cost`。`scope` ∈ 局部/一城/一域/一界/星海/诸天 且按此序单调不减；`growth` ∈ 地盘/势力/规则/认知/文明，≥3 条时至少一条是规则/认知/文明；条数 ≥ `DEFAULTS['world_ladder']['stage_min'][tier]`（t0/t1 2、t2 3、t3–t5 4）。格局门的 `ladder` 投影（`opening: ('ladder', 'ladder')`） |
| world_architecture | `{space, history, civilizations, conflict, mystery}`（**optional、参与对齐**）：五项非空文本，逐门开书必填，自备约定可不带；世界门 `architecture` 原样投影，世界记录绑定见 [世界架构](world.md#世界架构绑定) |
| world_tiers | rows（`blank: False, count: 1`；**optional、参与对齐**）：行 `name`/`condition`/`gain`/`cost`/`limit`，`name` 不重复，条数 ≥ `DEFAULTS['world_ladder']['tier_min'][tier]`（t0 2、t1/t2 3、t3–t5 4）。世界门的 `tiers` 投影（`opening: ('world', 'tiers')`） |
| world_resource | `{name, source, allocator}`（**optional、参与对齐**）：硬通货的名称、来源、分配者；世界门的 `resource` 投影（`opening: ('world', 'resource')`） |
| promise_anchor | `{deliverable, deadline_chapter}`（**optional、参与对齐**）：主题锚点——`deliverable` ≥12 字符，`deadline_chapter` 为纯数字字符串且 `1 ≤ N ≤ min(DEFAULTS['world_ladder']['anchor_max_chapter'], 该档 chapter_window 上限)`（默认 30 章）。兑现门的 `anchor` 投影（`opening: ('payoff', 'anchor')`） |
| volume_outline | `volumes[]`，字段、长度与卷末终值见 [卷纲](narrative.md#卷纲)；选择绑定见 [世界规则](world.md#三条逐字绑定) |
| chapter_outline | `volume` + `chapters[]`，字段与状态链见 [章纲](narrative.md#章纲)；重排范围以冻结 payload 为准 |
| style_guard | `observe`（默认）/`strict`：前者只观察相对首章的句段和未声明对白比例变化，后者按窗口执行数值约束。显式对白目标、高重复在两档都核，代词只观察；作者选择经正常约定或改约留档 |
| style_window | `{sentence:0.35, paragraph:0.35, dialogue:0.40, repetition:0.12, person:1}`（optional、不参与对齐）：文风代理指标容差；句段与对白使用相对变化，repetition 是本章绝对重复度上限，person 保留为代词观察参数，不能据此断言叙事视角；卷纲 `style.window` 与契约**逐项合并**（先用契约补默认，再按合法键与合法数值逐个覆盖），作者可改约调整。见 [文风](narrative.md#文风) |
| narrative_tracking | true；关闭时章纲的 `plot.nodes`/`plot.threads` 可空，但事实增量仍按同一规则核算，四类数组缺省或 null 按空数组处理 |
| editorial_features | true；编辑能力要求叙事跟踪，关闭跟踪时也须关闭编辑能力；人物、场景与补丁字段见 [编辑能力](editorial.md) |
| revision_limit | 正整数，默认 `DEFAULTS['revision_limit']`（3）；自动回改最近多少章，越界仍须作者对准确方案授权 |

**开书枚举**（取值单点声明在 `contracts.py`，文档只列可用值）：`WORLD_SCOPES` 局部/一城/一域/一界/星海/诸天；`WORLD_GROWTHS` 地盘/势力/规则/认知/文明；`WORLD_TERMINALS` 局部/势力/体系/文明；`STANCES` 顺从/利用/对抗；`DARK_SIDES` 外神/天灾/系统/上层剥削/制度/人心；`COSMOLOGY_SCOPES` 一界/星海/诸天（格局到这些尺度时世界模型的 `cosmology` 必填）；`SETTING_CLICHES` 序列/途径/克苏鲁/克系/系统/幕后黑手/第四天灾/诸天/无限流/模拟器/签到/存档重开（脑洞门板面提示，**只提示不拦**）。这些枚举与 `DEFAULTS['world_ladder']`（`tier_min`/`stage_min`/`anchor_max_chapter`）一样，改一处即可。

**跨层共享的数值默认单点声明在 `contracts.DEFAULTS`**，由 `contracts.policy_default(key)` 取用（取回的是副本，调用方改不动那唯一一份声明）：卷纲/章纲策略、`style_window` 与文风门槛（`style_floor_han`/`style_min_sentences`/`style_min_ngrams`/`style_ngram`/`style_short_sentence`/`style_same_order`）、开书位阶/阶梯条数下限与主题锚点上限（`world_ladder` 的 `tier_min`/`stage_min`/`anchor_max_chapter`）、返修额度（`repairs`/`redesigns`/`stall_after_rounds`）都在那里。契约字段默认值、`drift`/`style`/`world` 的校验、`context`/`workflow` 的兜底以及测试夹具全部读它——改一个默认值只需改一处；`tests/test_architecture.py::test_shared_numeric_defaults_are_declared_once` 会挡住重新硬编码。**这不改变分层纪律**：层边界仍由 `tests/architecture_table.py` 管，`DEFAULTS` 只管“同一个值只能有一个来源”。

t0/t1 的 `PIPELINE_SHAPES` 只保留 `merge_chapter_outline=True`：本卷卷纲与章纲由一次派工、一份回执交付，两个契约各自校验同一份回执；其余档位分两次派工。

跟踪项目按每章 word_budget 动态约束剩余总预算，允许长短章共同收口；关闭叙事跟踪时的静态规则如下。作者只定两件事：**章数**（落在档位窗口内）与**每章字数区间**（来自档位表）。总字数区间由二者派生（`章数 × [chapter_min, chapter_max]`）。完本核对的也是这两件事：章数写到位，且每一章都在区间内（后者在章节提交时逐章检查）。

entities=[{id,name,kind,aliases?}]、initial_facts=[{entity,key,value}]、initial_resources=[{holder,asset,unit,quantity}]、places=[{id,name,parent?}]、placements={entity:place} 只放已成立事实。quantity 为十进制字符串。world_rules/red_lines/arcs 是字符串数组，voice 保存文风。字面规则不属于约定：它是项目级 book.lexical_policy 的版本记录，用 `lexical --file 规则.json --source 原话` 修改，约定里出现 lexical_policy 会被结构校验拒绝。新人物不再有独立的档案派工，改由章纲 `new_entities` 内联声明。

protagonist_setup={id,name,identity,desire,limit} 保存主角身份、欲望和底线；relationships 为关系约定数组，style_traits 为文风特征数组。tone 保存给读者的基调，theme 保存母题，pov 保存叙述视角与人称（谁在讲、能看多远，换视角时如何交代）。完整约定可参考 [示例约定](../assets/contract.example.json)，按作者真实要求替换，不沿用示例题材和篇幅。

## 冻结任务与资料读取

task.json 给身份、路径和 commands，其中 records 提供冻结哈希，required 给必读名称；input.json 保存任务材料视图，记录哈希不重复写入。前章正文由 `previous_chapters` 索引列出章号、摘要、prose_hash 与 record；每章全文分别冻结为 `previous_chapter:N` 必读记录。同一上下文按章复用未变来源，窗口移动不会再次传送已读全文；`--all` 或新上下文仍获得全部必要原文。返修基稿使用 base_draft，历史正文经 recall 补读；本章理解证据绑定全文、补丁或复用方式最终合成的完整正文。brief 说明当前任务规则，任务目录同时物化 `brief.md`（同一简报的 markdown 全文，直接读它，不解析 input.json）与 `dispatch.md`（Worker 自举卡：环境自举、步骤、认领状态、命令与常见坑）；重派未提交任务时，上次遗留的回执草稿由引擎隔离为 `result.stale.json`（派工卡会注明）——它不是进度也不是判断依据，从模板起稿。guides 作为相关章节的参考，不重复通读全部文档。

主干使用 advance --compact 获取精简 task；开书门任务（opening_options）由主干自执，其余阶段把 task_path 交给子 agent；磁盘 task.json 始终完整。除 `contracts.CONTROLLER_STAGES` 中由主干自执的 opening_options 外，新任务使用新 Worker 会话，`requires_new_worker` 要求一个会话只做一个任务（跨任务复用按 session_reuse 拒绝）；开书门不绑定主干会话，可连续执行。claim 只表示执行认领，须结合宿主中的子 agent 状态判断是否仍在执行，主干循环及动作分支见 [运行](runtime.md)。

工作台能力 `understanding/1`、稳定场景身份 `scene-identity/2`、阅读关联 `reading-dependencies/1`、作品理解字段见 [叙事工作台](workbench.md)。能力值与规范化计划的 reading_schema 由引擎统一冻结并按当前规则解释。开书方案的篇幅上界是无条件的唯一规则，见 [逐门开书](opening.md)。

场景任务携带 capabilities.scene_memory=scene-memory/1；scene_context/scene_sources 为冻结的场景输入和已提交来源，字段及 dependency_coverage 见 [叙事推进](narrative.md#场景依赖与任务材料)。revision-impact 的输入、采用范围与保守扩展规则见 [运行](runtime.md)。

每个任务材料的 `policy` 块是当前生效的项目字面约定：`version`/`source` 说明版本与来源（作者原话或内置默认），`forbidden_terms`/`forbidden_name_chars` 给出规则，`scope` 说明**本阶段实际检查哪些字段**。该块与执行检查共用 `contracts.ENFORCEMENT` 一张表，所以声明与校验不会脱节；越出 scope 的字段不检查，违反 scope 内字段以 `literal_policy` 拒绝并在 details 里列出命中字段与命中词。改规则用 `lexical` 命令。

`read --task ID` 只返回本任务**尚未拿到过**的必读记录（跳过的名字列在 already_read，需要原文用 `--record 名称` 或 `--all` 取回）；返回里的 `records_hash` 是本任务 required 对应名称及哈希的摘要；仅主干连续自执 opening_options 时，与前一次相同且必读名单未变可跳过本次 read；其他任务由各自 Worker 完整读取必读记录；`--record 名称` 读单个完整记录。`recall --task ID --chapter N` 读冻结目录中的完整历史章，`--state` 读完整前态。可选 history_source 以哈希冻结逐章目录；分页检索与承诺关联见 [叙事推进](narrative.md#历史补读)。必读 state 按参与人和相关开放承诺选择，派工 baseline 也取该冻结视图，complete_state 永远可补读。结构选择不证明其他事实语义无关；执笔材料包含本章章纲和相关卷纲，完整卷纲保留补读入口，见 [材料范围](narrative.md#有界材料与局部重排)。当前 state 是视图，不冒充全部资料。

hash 是规范 JSON 的 SHA256：UTF-8、ensure_ascii=False、sort_keys=True、紧凑分隔符、allow_nan=False。正文哈希也基于 JSON 字符串值，不是裸文件字节。来源完整性不证明阅读理解。

`scene_context` 通过 `plan_record=chapter_outline` 与 plan_hash 指向唯一完整章纲，另交付所依赖的准确前态，不重复内嵌章纲。普通材料读取日志可带 execution_id 与 record_hashes，用于区分同一上下文的重复交付和新上下文的必要恢复；旧日志缺少这些字段时不能据记录名推断可省 token。

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

新派工的 commands 通过跨平台 Python worker 入口执行；主控 prepare-worker 后，读取入口自动验证 ready，session 与 execution_claim 在内存中注入，不写回草稿。旧直接接口仍由宿主附执行认领。技术恢复遵循 details.recovery，连续失败阻断与文学返修分开；完整身份交接见 [执行身份与技术恢复](runtime.md#执行身份与技术恢复)。preflight 完整校验后回滚，checked 不等于入库；submit 才更新。相同已提交结果幂等，不同结果拒绝。拒绝不计修复额度，真实短稿提交计实际执笔轮次并保留稿件。

预检和正式执笔提交的 style_report 含 metrics/observations/findings，正式章节核账记录保存同一报告；observations 不触发返修，findings 沿现有额度处理。submit 的 accepted=true 表示回执已接受，不等于正文已入库。正文的字数、lint、文风和漂移 findings 会保留候选并进入有界返修；信封、结构或证据校验抛出的错误回滚提交。设计提交失败保持原任务，不自动消耗正文返修额度。

`check` 是给 Worker 的格式自检：把候选回执从标准输入管道进去（无需 `--file`，已通过身份环境定位当前任务时可省略命令行 `--task`）。回执本身仍须提供 task_id 和 input_hash（信封字段从 result.template.json 复制起稿，不手写；`input_version` 报错带 expected），不允许猜测或改投身份；会话取自身份进程或任务自身。它按与 submit 相同的校验运行但**不提交、不消耗额度**，直接报告缺哪个字段或哪个枚举不对，让执行者不必读引擎源码确认格式。常见拒绝对应的期望形状：前值不匹配时 details 带 `current`（照抄为 before，新键为 null）；章纲漂移带具体项、卷内位置与模拟到该章的状态；`opening_option`（choose）带 `valid_options`；`literal_policy` 带命中字段与命中词。报错里没有的形状不要去源码里找，用 check 试算。

历史修订的 revision_range 表示请求未覆盖已登记目标或回退到无关前文；revision_bounds 表示不能用 resume 跳过超界方案；revision_proposal 表示方案哈希、范围、变更或来源不匹配；author_source 表示缺少配套的方案哈希和作者原话。revision_blocked 是已保存方案的业务动作，不是回执格式拒绝；恢复步骤统一见 [运行](runtime.md)。

| 阶段 | data |
|---|---|
| opening_options | 当前门 gate 与 2～3 个 options，详见 [逐门开书](opening.md) |
| opening_contract | 默认随世界起草；单独派发时读冻结的已采纳世界，模板由 CONTRACT_FIELDS 派生 |
| world_model | 完整世界记录；默认同时起草 data.contract（payload.also），提交时由引擎机械校验引用、领域与选择一致性 |
| volume_outline | `volumes[]`，字段、长度与卷末终值见 [卷纲](narrative.md#卷纲)；选择绑定见 [世界规则](world.md#三条逐字绑定) |
| chapter_outline | `volume` + `chapters[]`，字段与状态链见 [章纲](narrative.md#章纲)；重排范围以冻结 payload 为准 |
| write / repair / redesign | title/summary/drift_check/具体 self_check；write 交完整 prose，repair/redesign 从 prose/patches/reuse_original 中三选一，补丁或复用另附准确 base_hash 与 repair_note（见 [版本补丁](editorial.md#版本补丁)）；工作台模式下可带顶层 `understanding` 增量（引擎在入库时更新作品理解）；提交时机械判定字数区间、跨章逐字重复（≥25 字）、对白引号体例、西文残留，核算漂移，并跑文风代理指标（见 [文风](narrative.md#文风)） |

有世界模型时，章纲须声明 world_refs=[领域:id]，引用须存在，所选关联记录完整保留。返修必须逐项解决引擎拒绝的具体项（漏项、前态不符、体例或字数命中）。若修正的是回执漏项且原文仍成立，可按版本补丁协议复用原文并说明依据；完整合成稿仍须重新通过全部机械判据，不能用复用忽略正文缺陷。

卷纲与章纲校验（文风必填、可计算卷末终值）对所有提交统一执行；重排使用当前任务模板，历史前缀不再按旧形状解释。

## 验收报告

`audit` 与 `complete` 的 `ok` 仅表示通过当前机械判据，报告包含 `verification_scope=mechanical`；`unverified` 列出 `model_context_isolation`、`author_statement_authenticity` 与 `literary_quality`，不把声明的 session、作者原话文本或自比结论当成这些能力已验证。完本重试与正式导出均重新验证冻结来源，不信任旧状态标记或 audit 报告。当前存储与任务字段版本不变，不转换旧库。

## 快速连写能力

`run --fast` 是执行模式，不属于创作约定，不改变章纲、篇幅或返修限额。普通任务的会话绑定任务 ID；快速正文任务声明 `continuous_writing=continuous-writing/1` 与 `payload.worker_batch={id,first,last}`，会话绑定组 ID，仅组内允许接续。每章仍有独立 task_id、input_hash、结果及事务；组内版本只随已验证的本任务提交推进。组冻结约定、分支及各章章纲哈希，其他修改使接续失效。

submit 的 `worker_boundary=continue` 表示当前任务结束但本组未结束，Worker 只执行 `commands.worker_next`。返回的新任务与 execution_claim 指定下一步身份；更新环境后读取新任务。finished/batch_finished 表示 Worker 结束。重复回调仅恢复当前待办，不创造多条任务分支。预检同时回滚章节、组进度、绑定和凭据。运行与恢复见[快速无人值守](runtime.md#快速无人值守五章一组)。

## 漂移核算

执笔按模板填写 `drift_check`，事件由引擎生成。计划增量覆盖、前态来源、伏笔动作、计划外变化与精确引文要求统一见 [执笔自比与引擎核算](narrative.md#执笔自比与引擎核算)。

## 结算与时钟

入库事件仅由已固定的计划增量与通过自比的正文核算生成；`unplanned` 只诊断待返修偏差，不能入库。`facts.settle` 检查引文并应用事实规则，成功后在提交事务中保存。状态链、卷末终值与伏笔规则见 [卷内状态链](narrative.md#卷内状态链与校验)。

`state.clock` 是从初始状态累计的天数，与章号无关。同日续接在章纲声明 `clock.advance_days=0`，自比仍覆盖该项；引擎不生成零天数推进事件。实际推进需正文时间表达支持，不要求逐章报日期。

## 局部章纲重排回执

只有声明 `payload.allow_retained_suffix=true` 的任务接受可选 `through_chapter`。提交连续区间，保留后缀仍须通过整条链核验；完整规则见 [有界材料与局部重排](narrative.md#有界材料与局部重排)，策略组合见 [卷纲参数](narrative.md#参数与范围)。
