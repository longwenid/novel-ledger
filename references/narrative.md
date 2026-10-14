# 叙事推进与长篇上下文

何时读：全书/卷设计、章计划、执笔、章审、范围综合和叙事拒绝。只把实际正文及独立判断写入事实，不把未来设计改称既成事实。

## 新约定与旧项目

新建/明确改约时，narrative_tracking 默认 true、review_fanout 默认 3。旧已生效约定缺少 narrative_tracking 时沿用原事实形状和调度，不隐式改库；需要新能力时用 recontract 建立明确新版本。显式 false 是旧协议兼容模式，不具备本文的推进门槛。schema 仍为 novel-ledger/2；检查清单版本 2 随任务冻结，旧回执/旧在途任务仍按自身版本验收。

新约定另默认启用 editorial_features，任务检查版本为 3（约定声明了叙述视角时为 4，reader 多一项 pov_consistency）；显式旧兼容模式需 editorial_features=false。editorial/1 在独立章审中记录实际节点判据，可将成立正文的部分实现转入未来改案，或保留当前稿独立核验改案；不再要求所有偏离都重写正文。详见 [编辑能力](editorial.md)，以下严格节点对应规则仍适用于旧任务与 follow_plan。

## 线路和设计

新建/明确改约默认 `volume_outline={scope:all,words:500,tolerance:50}`，scope 可改为 current，tolerance=0 为严格字数。空对象 `{}` 是旧兼容模式；旧生效约定缺字段及旧在途任务不追补。字数用工程统一的汉字计数，标点和拉丁字符不计。每章情节说明保持精练，字数合格不证明因果、人物选择或阅读作用成立。

世界及约定核验后自动接续全书骨架，再做卷内脑暴与独立设计核验；volume_plan 在既定作者约定内给 2～3 个具体推进方案，交 `world_hash/brainstorm=[{id,premise,tradeoff,world_refs}]/selected/selection_reason`，当前阶段只交方案与节点。world_hash 绑定已核验世界，world_refs 必须存在；有世界时每案至少一项。选案由设计者判断并说明理由，独立审稿核验，不要求作者重复回答开书选择。

方案通过后派 `volume_outline`，每批最多 min(6,planning_window) 章，交 `world_hash/chapters=[{chapter,synopsis,world_refs,node_ids}]`，恰好覆盖本批次连续章号。每章 synopsis 写清行动、阻力、选择、代价、变化及对下一章的推动，默认 450～550 汉字；引用真实世界记录与已批准节点，不把未来设计登记成事实。`outline_review` 独立完整阅读当前批次、已定卷方案、世界及 `outline_bridge`（前一批最后一章），沿现有设计检查项举证；通过后原子追加，返修预算共享且有界，失败保留已通过前缀。完整旧卷纲始终保留可选来源，不在每批必读中重复全部前缀。

current 先完成首卷，后续每卷进入前完成；all 在正文前按卷顺序完成全部卷纲。完整覆盖不受试章授权影响，没有正文授权时以 `outline_ready` 交付并停止。逐章说明及脑暴选案在 book.html 的设计区展示；章计划必读 `volume_outline_window`，执笔只必读本章 `chapter_outline`，跟踪项目 frontier 不重复全部逐章说明。改案应保留已成立事实，再独立核验设计及正文。

book_plan 的 threads 至少一条必要主线，每条 `{id,kind:main|side|hidden,purpose,ending_condition,required:bool}`。支线与暗线按故事需要登记，不按固定顺序轮流出现。volume_plan 的 threads 可为空以沿用既有线路，新线路不能覆盖已有 ID。

节点沿用 id/line/cause/choice/cost/outcome/disclosure/depends_on，并增加 `required:bool`、`window:[最早章,最晚章]`。line 引登记线路；depends_on 指实际因果前置，不能把全书终局当作本卷开场的前置来表示层级。远期使用粗窗口，当前卷才细化。新节点和线路 ID 不覆盖既有设计。

章计划沿用原字段，并声明：

- node_actions=[{node,after:seeded|advanced|resolved}]，与 node_ids 一一对应。seeded 可铺垫尚未完成前置的远期节点；advanced/resolved 之前，依赖须已由正文兑现，或在本章数组中先完成。不能反复推进已 resolved 的节点。
- preconditions=[{kind,key,expected}]，kind 为 facts/knowledge/resources/relations/placements/character_current/node/clock。character_current 的 expected 是人物当前 value 对象，node 为状态字符串，clock 的 key 可填 main。无额外前提用空数组。窗口内仅节点行动会模拟，后章资源、动机等尚未实际成立的前提不要伪造；下一章前重新检查真实状态，变化时自动重规划未写窗口。
- disclosures=[{topic,after:hinted|suspected|misled|confirmed|retracted}]，列本章允许的读者认知变化，无变化用空数组。reader_refs/hook_refs/history_refs 可指出要承接的旧认知、承诺和历史断言。当前任务未选择某条资料不意味着它不存在。
- pacing={role,pressure_in,pressure_out,emotional_aftereffect,recovery_purpose}。role 为 setup/pressure/turn/climax/aftermath/recovery/relationship/discovery，其余用具体文字；本章不需恢复时说明原因。使用节奏功能判断，不计算张力分数或固定轮替。

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

首读先记录真实体验，再解锁设计。主动检查连续加压、高潮后立即重置、重复悬念、没有余波的代价、人物统一声线。静章可以承担关系变化、生活质感、恢复或暗线铺垫，不能把静章判成“必须增加对抗”。

## 篇幅与上下文

跟踪项目允许长章短章共同满足总区间；chapter_max 可以高于全书平均上限。每章 word_budget 给出 minimum/maximum/aim，根据剩余章数和真实累计篇幅计算可完成范围，窄范围修订同时预留原样携带后缀的固定篇幅；字数不足或超范围的实际稿仍留档并消耗既有修复额度。无法达到目标时明确 word_budget 拒绝，修订前文或由作者改约，不降低目标。

执笔 story 读取目标节点及直接依赖，前置结果见 state.story_nodes，完整设计在 design:*。规划 frontier:* 仅选本窗口未兑现节点。当前 state 供参与人、当前动机、近期成长和相关承诺使用；承诺按到期、显式 hook_refs、相关人物/物品及话题选择，完整状态与发展史保留 complete_state。世界采用直接关联；world_records 为可见材料，幕后真相保留可选 world_author_records，disclosure_boundary 明确本章允许披露与读者前态。

新任务声明 capabilities.hook_links=hook-links/1 时，独立事实审稿的 hook 事件可带 subjects=[人物或物品实体ID]、topics=[话题ID]。关联须来自正文证据，不从承诺文字猜实体，也不把设计意图当事实；改变已登记关联须给 reason。引擎为这些新事件保存 hook_links_version，重放时据该版本解释关联；旧任务不追补能力，旧事件中原先未解释的同名字段不改变旧投影。关联使未到期的伏笔在人物/物品参与或话题被 reader_refs/disclosures 引用时进入材料，不意味着这些对象不能受损。旧无标注承诺仍由到期与显式引用选择，规划和审稿需在 complete_state/recall 补查相关性。

## 分层范围核验

review_chunk 限制叶块章数；review_fanout 为 2～8，限制每个综合者的子报告数。fast 只省去固定间隔审，跟踪项目仍保持有界分块。树的叶覆盖完整正文，父覆盖连续子范围，节点指纹绑定章节链和检查版本；相同指纹的已审子树可复用，根仍独立接受当前范围。

叶块交逐章 coverage=[{chapter,reason,evidence}]；综合交 coverage=[{part_id,reason,evidence}]，与冻结 children 一一对应，证据须来自对应子范围。每层还交 handoff={causal_bridge,thread_changes,character_changes,disclosures,rhythm,open_questions,evidence}：六项具体文字，每项≤800字，evidence 1～8条、每条引文≤240字。记录无变化/无疑点也说明依据。完整报告和正文不截断，以上限制针对新写的交接摘要。

综合必读有限子摘要与各子范围首尾章；疑点沿 recall 完整补读，也可读 scope_report:ID 查看完整原报告。重点检查子块之间的动机桥梁、远距离因果、跨线合流与披露顺序，不能照抄 pass。所有检查理由和证据仍由新独立审稿者判断。

complete 除原验收外，必须验证所有 required 节点已 resolved、所有 required 线路已 resolved。机械门槛不证明情节好看；真实文学评价和实际 token 费用需真实宿主长跑另验收。

记忆检索可用 `recall --task ID --entity 人物ID`，或 `--node/--topic/--thread ID`：默认返回最近5个匹配章节的全部匹配证据；用 `--limit 1～20`、`--before 章号` 分页，再用 `--chapter N` 完整补读。新任务的可选 history_source 只冻结逐章不可变目录的入口及截至章号，查询由近到远读取所需页与事件，不每次重建全书摘要/事件索引。旧冻结任务仍读原 historical_index/memory_index；显式 --record 读取这两个旧名称时，新任务也能完整展开，但常规检索应使用 recall。首读冻结前同样禁止检索，后续新增章节和其他修订分支不会进入本任务的历史来源。

稀疏或无匹配查询仍可能遍历整个冻结历史，按章直接补读也可能遍历目录；页式复用减少重复构建与存储，不宣称所有查询都是常数时间。read/recall 返回的实际字符量均计入 usage，宿主包装、模型缓存与计费 token 由真实用量日志另算。
