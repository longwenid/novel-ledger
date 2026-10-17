# 任务与结果协议

何时读：约定、回执、事件和报错。协议与机械清单由 contracts.py 定义，模板动态生成，不预填判断。

## 适用范围与字段来源

本页说明字段与机械核验，文学判断见 [创作与写审](craft.md)。填写时以当前任务的 capabilities、checks_version、brief 和 result.template.json 为准，不自行增删检查项或预填 pass；格式不确定用 check，处理入口见 [运行](runtime.md)。

约定字段表以 contracts.py 的 CONTRACT_FIELDS 为唯一权威，模板、结构校验和对齐核验均由它派生。未知字段按 contract 拒绝，标为 optional 的数组/映射缺省时补空值；有 default 的字段采用表中默认值，其余按表检查必填。当前存储为 novel-ledger/3，已有 v3 可继续使用，v2 及更早数据库拒绝打开；任务协议和检查清单版本分别冻结，不用于转换数据库。

## 作者约定

核心字段包括 title/reader_promise/ending/genre、volumes、entities、protagonist_setup、story_engine、opposition、world_premise、voice、style_traits、relationships、chapter_min/chapter_max/chapter_aim、allow_special_mechanism，完整必填项按模板检查。`tone`/`theme`/`pov` 在 opening/2 中由作者选择并逐字保留；自备约定可缺省，不追溯要求补选。每卷 id/purpose 必填，end 为递增卷末章号，没有 end 时由 word_budget/chapter_aim 推导。总字数区间 word_range 是派生字段：由章数与每章区间算出，作者与派工材料都不填，也不参与开书对齐。

| 设置 | 默认与作用 |
|---|---|
| planning_window / review_interval / review_chunk | 3 / 10 / 3；近期计划窗口（同时限定自动历史回改的回溯窗口及初始修改章数）、间隔审与叶块大小 |
| narrative_tracking / review_fanout | true / 3；节点推进和有界综合见 [叙事推进](narrative.md) |
| editorial_features / scope_append_limit | true / 3；编辑能力要求叙事跟踪，关闭跟踪时也须关闭编辑能力；人物、改案和关闭字段见 [编辑能力](editorial.md) |
| volume_outline | rolling 近期卷纲；配置、批次与 current/all 范围统一见 [叙事推进](narrative.md) |
| verification | full；fast 省去固定间隔审，跟踪项目两档都保持有界范围分块；基础流程 fast 把叶块固定为 `contracts.FAST_REVIEW_BLOCK`（12）章（该组合不读 review_chunk），任何档位的范围任务都不会拿到整卷或全书；均保留章审、首读和事实核验 |

检查清单版本按用途各有自己的编号，`CHECK_SETS` 同时保留四套：1 为最初清单，2 起加入叙事、披露与节奏等项（`CHECKS_VERSION`），3 起为编辑能力清单（`EDITORIAL_VERSION`），4 起在作者选定了叙述视角的约定上再加 reader.pov_consistency（`POV_CHECKS_VERSION`）。启用编辑能力时为 3、约定另有 pov 时为 4、未启用编辑能力时为 2；回执按冻结版本复核，不追补后来新增的检查项，"v2 及更早数据库拒绝打开"说的是存储 schema，与检查清单编号不是一回事。

跟踪项目按每章 word_budget 动态约束剩余总预算，允许长短章共同收口；关闭叙事跟踪时的静态规则如下。作者只定两件事：**章数**（落在档位窗口内）与**每章字数区间**（来自档位表）。总字数区间由二者派生（`章数 × [chapter_min, chapter_max]`），因此不会再出现"表自己算不平"或"固定章数装不下总区间"的问题。完本核对的也是这两件事：章数写到位，且每一章都在区间内（后者在章节提交时逐章检查）。

entities=[{id,name,kind,aliases?}]、initial_facts=[{entity,key,value}]、initial_resources=[{holder,asset,unit,quantity}]、places=[{id,name,parent?}]、placements={entity:place} 只放已成立事实。quantity 为十进制字符串。world_rules/red_lines/arcs 是字符串数组，voice 保存文风。字面规则不属于约定：它是项目级 book.lexical_policy 的版本记录，用 `lexical --file 规则.json --source 原话` 修改，约定里出现 lexical_policy 会被结构校验拒绝。候选人物放计划 new_entities，经正文事实核验后成立。

protagonist_setup={id,name,identity,desire,limit} 保存主角身份、欲望和底线；relationships 为关系约定数组，style_traits 为文风特征数组。tone 保存给读者的基调，theme 保存母题，pov 保存叙述视角与人称（谁在讲、能看多远，换视角时如何交代）。完整约定可参考 [示例约定](../assets/contract.example.json)，按作者真实要求替换，不沿用示例题材和篇幅。

## 冻结任务与资料读取

task.json 给身份、路径和 commands。首读封印阶段不生成正式 input/template；解锁后 records 提供冻结哈希，required 给必读名称，prose 和 obligations 给正文及义务。brief 说明当前任务规则，guides 作为相关章节的参考，不重复通读全部文档。

主干使用 advance --compact 获取精简 task，再把 task_path 交给子 agent；磁盘 task.json 始终完整。review_session 非空表示当前任务已冻结首读，requires_new_worker=false，仍须沿该真实会话完成核验；新任务使用新会话。claim 只表示执行认领，须结合宿主中的子 agent 状态判断是否仍在执行，主干循环及动作分支见 [运行](runtime.md)。

工作台能力 `understanding/1`、稳定场景身份 `scene-identity/2`、阅读关联 `reading-dependencies/1`、作品理解字段和修订阅读任务见 [叙事工作台](workbench.md)。能力及规范化计划的 reading_schema 按版本解释，不追补旧回执或重解释旧计划的同名字段。新开书方案的篇幅上界另由 opening-bounds/1 冻结，见 [逐门开书](opening.md)。

新根审的 payload.closure.revision_policy 以 revision-bounds/1 冻结近期回改窗口、章数上限和已关闭卷的验收范围；revise_range 需在 closure.changes 声明表达、阅读或语义变更。该标记位于任务 payload，不是数据库版本或 capabilities 字段。没有该标记的旧根审保持原字段解释，执行层仍检查自动范围。revision_blocked 与 plan_hash 授权入口见 [运行](runtime.md)，修复回执字段见 [编辑能力](editorial.md)。

场景任务携带 capabilities.scene_memory=scene-memory/1；scene_context/scene_sources 为冻结的场景输入和已提交来源，字段及 dependency_coverage 见 [叙事推进](narrative.md)。revision-impact 的输入、采用范围与保守扩展规则见 [运行](runtime.md)。

每个任务材料的 `policy` 块是当前生效的项目字面约定：`version`/`source` 说明版本与来源（作者原话或内置默认），`forbidden_terms`/`forbidden_name_chars` 给出规则，`scope` 说明**本阶段实际检查哪些字段**。该块与执行检查共用 `contracts.ENFORCEMENT` 一张表，所以声明与校验不会脱节；越出 scope 的字段不检查，违反 scope 内字段以 `literal_policy` 拒绝并在 details 里列出命中字段与命中词。改规则用 `lexical` 命令。

`read --task ID` 返回全部必读完整记录；`--record 名称` 读单个完整记录。`recall --task ID --chapter N` 读冻结目录中的完整历史章，`--state` 读完整前态。新任务的可选 history_source 以哈希冻结逐章目录，旧任务仍使用自身索引；分页检索与承诺关联见 [叙事推进](narrative.md)。必读 state 按参与人和相关开放承诺选择，派工 baseline 也取该冻结视图，complete_state 永远可补读。结构选择不证明其他事实语义无关；跟踪项目 story 包含目标及直接前提，已兑现结果见 story_nodes，全部祖先和完整设计仍有补读入口。当前 state 是视图，不冒充全部资料。

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

submit 的 accepted=true 表示回执已接受，不等于正文通过：verdict=fix 也可正常入库并转入返修或暂停。根审可先成功保存修复回执，再由 advance 返回 revision_blocked。主干等待子 agent 结束后用 advance --compact --after 核实实际动作，不凭 accepted 单独判断章审通过或授权目标完成。

`check` 是给 Worker 的格式自检：把候选回执从标准输入管道进去（无需 `--file`，已通过身份环境定位当前任务时可省略命令行 `--task`）。回执本身仍须提供 task_id 和 input_hash，不允许猜测或改投身份；会话取自身份进程或任务自身。它按与 submit 相同的校验运行但**不提交、不消耗额度**，直接报告缺哪个字段或哪个枚举不对，让执行者不必读引擎源码确认格式。常见拒绝对应的期望形状：前值不匹配时 details 带 `current`（照抄为 before，新键为 null）；`evidence_scope`/首读覆盖带 `frozen_chapters`；`review_coverage`/`finding` 带 `expect`/`valid_criteria`；`event_op` 带 `valid_ops`；`opening_option`（choose）带 `valid_options`。报错里没有的形状不要去源码里找，用 check 试算。

历史修订的 revision_range 表示请求未覆盖已登记目标或回退到无关前文；revision_bounds 表示不能用 resume 跳过超界方案；revision_proposal 表示方案哈希、范围、变更或来源不匹配；author_source 表示缺少配套的方案哈希和作者原话。revision_blocked 是已保存方案的业务动作，不是回执格式拒绝；恢复步骤统一见 [运行](runtime.md)。

| 阶段 | data |
|---|---|
| opening_options | 当前门 gate 与 2～3 个 options，详见 [逐门开书](opening.md) |
| world_model / world_review | 完整世界记录与独立核验；默认 world_model 同时起草 data.contract，按 payload.also 和模板交付，详见 [世界模型](world.md) |
| opening_contract | 默认随世界起草，世界通过后再 contract_review；单独派发时读冻结的核验世界。约定不得更改用户选择，模板由 CONTRACT_FIELDS 派生 |
| book_plan / volume_plan | intent/ending_conditions/nodes。节点 id/line/cause/choice/cost/outcome/disclosure/depends_on；ID 唯一，引用存在，无因果环 |
| volume_outline / outline_review | 逐章卷纲有界批次与独立设计核验；world_hash/chapters、脑暴选案及篇幅规则见 [叙事推进](narrative.md) |
| design_review / contract_review | verdict/checks/findings/obligations；独立核验 proposal 来源，证据 chapter=0 |
| plan | plans 恰好覆盖冻结窗口；chapter/goal/obstacle/choice/cost/change/ending/node_ids/participants，可带 new_entities/obligations/schedule |
| profiles | 恰好覆盖 payload.entities；entity/desire/fear/limit/voice/knowledge_boundary |
| alignment_plan / alignment_review | 独立改案提案 reason/plan/designs 与设计核验；通过仍重新章审，见编辑能力 |
| write / repair / redesign | title/完整 prose/summary/具体 self_check；不交 events 或 candidate_events |
| revision_review | reader 阅读回执；先冻结首读，pass 保留待携带正文，fix 按 local/chapter 返修；不重抽事实 |
| chapter_review | facts 和 reader 两套完整回执；事实通过需 events/summary/elapsed_days，首读已持久冻结 |
| scope_review / scope_synthesis | 叶块 coverage 按 chapter；树形综合按 children 的 part_id，另交 handoff，见 [叙事推进](narrative.md) |

有世界模型的章计划还须声明 world_refs=[领域:id]，引用须存在，所选关联记录完整保留，并按跟踪能力选择关联范围。计划义务为 {id,category:facts或reader,text}；硬日程为 {basis:main_clock,day:整数,event:具体事件}，提交主线时间区间须覆盖该天数。

## 首读与审稿

首读为 `{task_id,input_hash,session,data:{reads:[{chapter,desire,obstacle,change,read_on_reason}]}}`，完整覆盖冻结正文，每项具体体验非空。相同内容幂等，改体验或换人拒绝。

checks 恰好覆盖模板，各项 {id,result:pass或fix,reason,evidence:[...]}。证据 {chapter,quote,start?}；缺 start 时引文必须唯一。time/language 附 challenge={risk,disposition:satisfied或violated,reason,evidence}，对应 pass/fix。

findings=[{criterion,severity:blocker或quality或note,reason,evidence,target_chapter,repair_scope:local或chapter}]。实质 finding 与 fix 检查一致，须给 target_chapter 与 repair_scope；note 可省修复范围。修复起点不从举证位置猜。reason 说明具体问题、影响和修订建议，evidence 保留精确原文，不另加字段。义务逐项回 {id,result,reason,evidence}，未履行者须关联带 obligation_id 的实质 finding。

severity=author 表示问题出在作者约定本身，任何改写都无法解决：它不写 target_chapter/repair_scope，改带 decision={id,question,options:[{label,impact}]}，question 须是作者能直接回答的问题，options 至少两个并说明取舍后果。程序把该发现挂到既有作者通道（暂停项目、pause_reason 取 question、resume 拒绝绕过），不安排写作端返修，也不消耗返修额度；作者选定选项后记录进 author_decision_history 并并入作者原话，候选按新前提重新起草，改约定本身的问题仍走改约核验。只有世界模型、设计、卷纲、改约、改案与跨章核验这些正文未定型的阶段有该通道，章内审稿仍只报能由改写解决的缺陷。一份回执最多上交一条 author 发现（一次只有一个待决问题），且只有 author 级发现可以携带 decision。

事实核对正文覆盖、连续性、资源、知情、时间、世界规则和空间；阅读核对追读、人物、变化、情绪代价、语言、重复和有效展开。跨章核对因果、人物弧线、兑现、节奏、世界规则和覆盖。程序检查协议及证据，独立审稿者负责判断语义。

## 事件

每条事件 evidence 引当前章完整正文，按数组顺序结算。事实由独立审稿生成，reader.pacing 的独立核验结果由引擎结算为 pace 事件。叙事事件及跟踪计划字段见 [叙事推进](narrative.md)。

| op | 字段与边界 |
|---|---|
| entity | entity={id,name,kind,aliases?}，身份和称呼唯一 |
| alias | entity/alias，称呼不得歧义 |
| state | entity/key/before/after；复活需 exception_reason，站位用 move |
| relation | from/to/key/before/after，已存在端点 |
| knowledge | entity/topic/before/claim/stance/source；stance=knows/believes/suspects/disproved，before 为旧 claim |
| resource | from/to 至少一方非 null，asset/unit/quantity/reason；对应 from_before/to_before，不透支 |
| clock | before/after 整数，引用时间表达；可带 thread，支线不推进主线 |
| hook | id/before/status=open或paid或closed；新承诺 text/due，延期取消需 reason，最多延期两次 |
| place | place={id,name,parent?}，父地点存在，定义不可覆盖 |
| move | entity/before/after/route/reason，before/after 为地点 ID |
| historical_assertion | id/subjects/claim/source/occurred_at={basis:main_clock,start,end}，不重结算当前事实 |
| character_development | entity/choice/cost/change |

editorial/1 可选空间事件 anchor/anchor_assert/anchor_change/link/link_change/placement/travel/perceive 的字段和边界见 [编辑能力](editorial.md)。这些能力只核验已登记拓扑、稳定属性与时间下限，不自动确定人物知情。

elapsed_days 等于主线时钟增量。引文真实、时间词存在及数值一致只证明机械条件；知情、代价与路径是否成立仍独立判断。

state.clock 是从初始状态起累计的内部天数，不是章号，也不要求正文逐章报日期。同日续接允许 elapsed_days=0 且不交 clock 事件；发生推进时，clock 引文可取正文任意位置的自然时间表达，不要求章首标签。天数增量由独立事实审稿结合前态和正文判断，不从章号推算。
