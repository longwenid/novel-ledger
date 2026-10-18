# 叙事推进与长篇上下文

何时读：全书/卷设计、章计划、执笔、章审、范围综合和叙事拒绝。只把实际正文及独立判断写入事实，不把未来设计改称既成事实。

## 适用范围与能力要求

本文维护滚动卷纲、叙事状态、场景依赖与分层核验的接口规则。narrative_tracking 默认 true；显式关闭时使用基础流程，不具备本文的节点推进门槛。能力开关和检查版本统一见 [协议](protocol.md)，当前任务与已保存回执按各自冻结版本核验。

状态、来源和依赖核验是流程要求；主支线安排与节奏作用按 [创作与写审](craft.md) 判断，不增加固定推进间隔或张力评分。editorial/1 可将成立正文的部分实现转入独立改案，见 [编辑能力](editorial.md)；以下严格节点对应规则适用于 follow_plan。

| 当前任务 | 读取位置 |
|---|---|
| 卷内方案、逐章卷纲、交付覆盖 | [滚动卷纲](#滚动卷纲) |
| 全书或卷设计、章计划 | [线路与章计划](#线路与章计划)；声明场景来源时补读 [场景依赖与任务材料](#场景依赖与任务材料)。 |
| 执笔、章审、叙事事件被拒绝 | [独立章审与事件](#独立章审与事件) 与 [篇幅与上下文](#篇幅与上下文) |
| 块审、卷审、全书综合 | [分层范围核验](#分层范围核验) |
| 需要早期原文或事件 | [历史补读](#历史补读) |

## 滚动卷纲

### 策略与篇幅

新建/明确改约默认 `volume_outline={scope:rolling,words:500,tolerance:50}`，scope 可改为 current 或 all，tolerance=0 为严格字数。空对象 `{}` 表示明确关闭逐章卷纲；省略字段则采用 rolling 默认值。字数用工程统一的汉字计数，标点和拉丁字符不计。每章情节说明保持精练，字数合格不证明因果、人物选择或阅读作用成立。

世界及约定核验后自动接续全书骨架，再做卷内脑暴与独立设计核验；volume_plan 在既定作者约定内给 2～3 个具体推进方案，交 `world_hash/brainstorm=[{id,premise,tradeoff,world_refs}]/selected/selection_reason`，当前阶段只交方案与节点。world_hash 绑定已核验世界，world_refs 必须存在；有世界时每案至少一项。选案由设计者判断并说明理由，独立审稿核验，不要求作者重复回答开书选择。

### 批次、核验与实际覆盖

方案通过后派 `volume_outline`，交 `world_hash/chapters=[{chapter,synopsis,world_refs,node_ids}]`，恰好覆盖本批次连续章号。**批次大小按档位声明（PIPELINE_SHAPES.outline_batch）**：单卷微型档（t0）整卷一批；其余档位沿用每批最多 min(6,planning_window) 章——planning_window 是写作期滚动重排的参数，不是开书期的切批刀（实测一本 17 章验证书按它切了 6 批，而骨架已整体核验过）。t0 还可整档省略该派工：`book_plan` 的合并派工（payload.also=volume_outline）让骨架与整卷逐章卷纲同一个回执交付、同一次 `design_review` 核验（causality/disclosure/threads 同时覆盖逐章 synopsis），返修也保持合并形状。每章 synopsis 写清行动、阻力、选择、代价、变化及对下一章的推动，默认 450～550 汉字；引用真实世界记录与已批准节点，不把未来设计登记成事实。`outline_review` 独立完整阅读当前批次、已定卷方案、世界及 `outline_bridge`（前一批最后一章），沿现有设计检查项举证；通过后原子追加，返修预算共享且有界，失败保留已通过前缀。返修预算用尽时按剩余问题分流：只剩 quality/note 级局部意见直接记为未解决项继续，blocker 或章范围级问题才交作者决定。完整旧卷纲始终保留可选来源，不在每批必读中重复全部前缀。

rolling 先完成首卷近期一个批次，进入未覆盖章节时才补下一批；章计划不得越过已核验卷纲边界。远期卷保留职责与关键节点，进入该卷时再细化。current 先完成首卷，后续每卷进入前完成；all 在正文前按卷顺序完成全部卷纲。后两种模式的完整覆盖不受试章授权影响。没有正文授权时以 `outline_ready` 交付并停止，返回 planning_mode/coverage 表示实际完成范围。逐章说明及脑暴选案在 book.html 的设计区展示；章计划必读 `volume_outline_window`，执笔只必读本章 `chapter_outline`，跟踪项目 frontier 不重复全部逐章说明。改案应保留已成立事实，再独立核验设计及正文。

## 线路与章计划

book_plan 的 threads 至少一条必要主线，每条 `{id,kind:main|side|hidden,purpose,ending_condition,required:bool}`。支线与暗线按故事需要登记，不按固定顺序轮流出现。volume_plan 的 threads 可为空以沿用既有线路，新线路不能覆盖已有 ID。

节点沿用 id/line/cause/choice/cost/outcome/disclosure/depends_on，并增加 `required:bool`、`window:[最早章,最晚章]`。line 引登记线路；depends_on 指实际因果前置，不能把全书终局当作本卷开场的前置来表示层级。远期使用粗窗口，当前卷才细化。新节点和线路 ID 不覆盖既有设计。

章计划沿用原字段，并声明：

- node_actions=[{node,after:seeded|advanced|resolved}]，与 node_ids 一一对应。seeded 可铺垫尚未完成前置的远期节点；advanced/resolved 之前，依赖须已由正文兑现，或在本章数组中先完成。不能反复推进已 resolved 的节点。
- preconditions=[{kind,key,expected}]，kind 为 facts/knowledge/resources/relations/placements/character_current/node/clock。character_current 的 expected 是人物当前 value 对象，node 为状态字符串，clock 的 key 可填 main。无额外前提用空数组。窗口内仅节点行动会模拟，后章资源、动机等尚未实际成立的前提不要伪造；下一章前重新检查真实状态，变化时自动重规划未写窗口。
- disclosures=[{topic,after:hinted|suspected|misled|confirmed|retracted}]，列本章允许的读者认知变化，无变化用空数组。reader_refs/hook_refs/history_refs 可指出要承接的旧认知、承诺和历史断言。当前任务未选择某条资料不意味着它不存在。
- pacing={role,pressure_in,pressure_out,emotional_aftereffect,recovery_purpose}。role 为 setup/pressure/turn/climax/aftermath/recovery/relationship/discovery，其余用具体文字；本章不需恢复时说明原因。使用节奏功能判断，不计算张力分数或固定轮替。

## 场景依赖与任务材料

新工作台任务采用 scene-identity/2：场景 ID 不绑定章号，跨章移动保留身份，独立的故事时间、作品理解与阅读关联见 [叙事工作台](workbench.md)。以下 c章号: 前缀是旧冻结身份协议；新任务未提供 ID 时引擎生成不透明 ID。

阅读关联另由 reading-dependencies/1 能力及计划 reading_schema 标记冻结，旧计划中的同名字段不追补解释；没有标记时保守重读。相关字段、分级修订和创作记忆统一在工作台维护，不用事实 dependency_coverage 代替阅读关联覆盖。

章计划可声明 `dependency_coverage=partial|complete`，默认 partial。旧身份协议中每场的 id 以 `c章号:` 开头，建议给有意义且跨重排保留的名称；省略时按当前顺序分配 c1:s1 形式的编号。`reads=[{kind,key}]` 声明使用的事实坐标，`depends_on=[场景ID]` 只能指向已登记前章或本章前场，禁止环及前向引用。complete 要求每场显式提供两份数组，无依赖给空数组；独立章审以 facts.continuity 核对声明是否与正文因果一致，遗漏则返修。partial 在修订传播时保守扩大范围。

保守扩大只说明影响，不能据此自动重写全书。新根审须声明真实 changes；审稿触发的历史修订在建立分支前检查近期窗口与已关闭验收范围，超界保存 revision_blocked 方案并等待准确授权，见 [运行](runtime.md)。

任务的 `scene_context.plan` 包含完整章计划及场景，inputs 给出显式输入和输入是否存在，plan_hash/state_hash 绑定准确来源；独立 plan 记录作为按需来源，避免重复必读；场外人物或远期承诺的显式坐标不会被参与人筛选丢掉。`scene_sources` 绑定前置已提交场景的 plan/prose/events 哈希与章节链；原文按本任务的 recall --chapter 补读。引用若只存在于未提交的重规划计划，派工拒绝并要求重新规划。材料只是作者可用信息，人物实际知情仍以 knowledge 和对白意图为准；未来设计不会变成事实。

## 独立章审与事件

facts.events 逐项重建本章 node_actions 的真实实现，节点事件不得遗漏。只在 facts/reader 均通过且所有结算成功后原子入库。事件 evidence 为当前章单个 `{chapter,quote,start?}` 对象。

| op | 审稿者填写 |
|---|---|
| story_node | node/before:旧状态或null/after/outcome/evidence；line/depends_on 由冻结设计补齐，审稿者不能替换前置因果；结算时自动将所属线路置为 active 并更新 last_chapter |
| story_thread | thread/before:旧状态或null/after:active或dormant或resolved/reason/evidence；dormant 还须 return_by:未来章号；已到返回章须有据恢复或调整，必要节点未兑现不能关闭 |
| reader_knowledge | topic/before:旧状态或null/after/claim/evidence；retracted 还需 reason，不把作者真相直接变成角色知情 |
| character_current | entity/before:旧value对象或null/after={desire,stance,relationship_focus}/choice/cost/change/evidence，保持人物底层档案，变化必须有选择和代价 |

reader.pacing 独立填写实际节奏五项和单个 evidence；引擎将这份核验结果作为 pace 事件保存。执笔者不生成节奏事实，不替审稿签 pass。pace_history 只保留最近六章供当前阅读，完整记录仍在章节事件和审稿中。

事件按数组顺序检查前态，包括同章前一事件的影响。例如先兑现 story_node，再关闭该线时，story_thread.before 应为 active，即便本章开始时该线未登记；check 会返回实际 current，不需要猜字段或修改历史。

首读先记录真实体验，再解锁设计。沿当前检查项用原文说明连续性、披露和节奏的实际作用，具体问题、影响及范围写入现有 reason/findings，不凭场景数量或强制动静轮替给 fix。判断依据见 [创作与写审](craft.md)。

## 篇幅与上下文

跟踪项目允许长章短章共同满足总区间；chapter_max 可以高于全书平均上限。每章 word_budget 给出 minimum/maximum/aim，根据剩余章数和真实累计篇幅计算可完成范围，窄范围修订同时预留原样携带后缀的固定篇幅；字数不足或超范围的实际稿仍留档并消耗既有修复额度。无法达到目标时明确 word_budget 拒绝，修订前文或由作者改约，不降低目标。

执笔 story 读取目标节点及直接依赖，前置结果见 state.story_nodes，完整设计在 design:*。规划 frontier:* 仅选本窗口未兑现节点。当前 state 供参与人、当前动机、近期成长和相关承诺使用；承诺按到期、显式 hook_refs、相关人物/物品及话题选择，完整状态与发展史保留 complete_state。世界采用直接关联；world_records 为可见材料，幕后真相保留可选 world_author_records，disclosure_boundary 明确本章允许披露与读者前态。

新任务声明 capabilities.hook_links=hook-links/1 时，独立事实审稿的 hook 事件可带 subjects=[人物或物品实体ID]、topics=[话题ID]。关联须来自正文证据，不从承诺文字猜实体，也不把设计意图当事实；改变已登记关联须给 reason。引擎为这些新事件保存 hook_links_version，重放时据该版本解释关联；旧任务不追补能力，旧事件中原先未解释的同名字段不改变旧投影。关联使未到期的伏笔在人物/物品参与或话题被 reader_refs/disclosures 引用时进入材料，不意味着这些对象不能受损。旧无标注承诺仍由到期与显式引用选择，规划和审稿需在 complete_state/recall 补查相关性。

## 分层范围核验

review_chunk 限制叶块章数；review_fanout 为 2～8，限制每个综合者的子报告数。fast 只省去固定间隔审；所有项目（含未开叙事跟踪的基础流程）的范围审都经有界覆盖树分块。基础项目的 fast 档把叶块大小直接设为 `FAST_REVIEW_BLOCK`（12）章，即这一组合不读作者配置的 review_chunk：配置更小时这是合并，配置更大时这是收窄，因此该值既是合并后的块大小也是单块上限。任何派工都不随卷长增长。树的叶覆盖完整正文，父覆盖连续子范围，节点指纹绑定章节链和检查版本；相同指纹的已审子树可复用，根仍独立接受当前范围。

叶块交逐章 coverage=[{chapter,reason,evidence}]；综合交 coverage=[{part_id,reason,evidence}]，与冻结 children 一一对应，证据须来自对应子范围。每层还交 handoff={causal_bridge,thread_changes,character_changes,disclosures,rhythm,open_questions,evidence}：六项具体文字，每项≤800字，evidence 1～8条、每条引文≤240字。记录无变化/无疑点也说明依据。完整报告和正文不截断，以上限制针对新写的交接摘要。

综合必读有限子摘要与各子范围首尾章；疑点沿 recall 完整补读，也可读 scope_report:ID 查看完整原报告。重点检查子块之间的动机桥梁、远距离因果、跨线合流与披露顺序，不能照抄 pass。所有检查理由和证据仍由新独立审稿者判断。

complete 除原验收外，必须验证所有 required 节点已 resolved、所有 required 线路已 resolved。机械门槛不证明情节好看；真实文学评价和实际 token 费用需真实宿主长跑另验收。

## 历史补读

记忆检索可用 `recall --task ID --entity 人物ID`，或 `--node/--topic/--thread ID`：默认返回最近5个匹配章节的全部匹配证据；用 `--limit 1～20`、`--before 章号` 分页，再用 `--chapter N` 完整补读。新任务的可选 history_source 只冻结逐章不可变目录的入口及截至章号，查询由近到远读取所需页与事件，不每次重建全书摘要/事件索引。旧冻结任务仍读原 historical_index/memory_index；显式 --record 读取这两个旧名称时，新任务也能完整展开，但常规检索应使用 recall。首读冻结前同样禁止检索，后续新增章节和其他修订分支不会进入本任务的历史来源。

稀疏或无匹配查询仍可能遍历整个冻结历史，按章直接补读也可能遍历目录；页式复用减少重复构建与存储，不宣称所有查询都是常数时间。read/recall 返回的实际字符量均计入 usage，宿主包装、模型缓存与计费 token 由真实用量日志另算。

命令身份、首读封印与修订影响分析见 [运行](runtime.md)，工程及真实长篇验收口径见 [验证](validation.md)。
