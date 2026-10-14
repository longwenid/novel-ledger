# 任务与结果协议

何时读：约定、回执、事件和报错。协议与机械清单由 contracts.py 定义，模板动态生成，不预填判断。

## 约定与材料

约定字段表以 contracts.py 的 CONTRACT_FIELDS 为唯一权威：交付模板、结构校验和对齐核验都由它派生，新增字段只改这一处。结构校验按表逐项执行，未知字段直接拒绝（旧版本残留字段会报 contract），标为 optional 的数组/映射缺省时补空值，其余必填。

必填 title/reader_promise/ending/genre/reader_promise 等全部文本字段、word_range=[总汉字下限,上限]、volumes、entities、protagonist_setup、story_engine、opposition、world_premise、voice、style_traits、relationships、chapter_min/chapter_max/chapter_aim、allow_special_mechanism。每卷 id/purpose 必填，end 为递增卷末章号，没有 end 时由 word_budget/chapter_aim 推导。planning_window/review_interval/review_chunk 可缺省（3/10/3）。verification 可缺省为 full：full 走固定间隔块审+分块范围审，fast 跳过固定间隔块审且范围审一次成块——两档的章审、首读与事实核验完全一致，档位只收窄调度密度，不放松任何不变量。审稿回执顶层带 checks_version：回执按提交时的检查清单版本存档，验收重放按回执自己的版本核对，因此引擎后续新增检查项不会追溯推翻已通过的核验。

篇幅必须**写得完**：固定章数 last 后，每章平均可用区间是 `[ceil(word_range[0]/last), floor(word_range[1]/last)]`；`chapter_aim` 与 `chapter_max` 都必须落在该区间内，否则报 `scale`（区间为空报"章数与总篇幅不能同时成立"）。错误详情里带 `per_chapter_range` 与可执行的修正建议（降低章幅或上调卷末章号），例如 47 章 × 上限 2600 配 11 万上限会被拒，因为每章平均最多只能 2340 字。

entities=[{id,name,kind,aliases?}]、initial_facts=[{entity,key,value}]、initial_resources=[{holder,asset,unit,quantity}]、places=[{id,name,parent?}]、placements={entity:place} 只放已成立事实。quantity 为十进制字符串。world_rules/red_lines/arcs 是字符串数组，voice 保存文风。字面规则不属于约定：它是项目级 book.lexical_policy 的版本记录，用 `lexical --file 规则.json --source 原话` 修改，约定里出现 lexical_policy 会被结构校验拒绝。候选人物放计划 new_entities，经正文事实核验后成立。

task.json 给身份、路径和 commands。first_read 时不生成正式 input/template；解锁后 records 提供冻结哈希，required 给必读名称，prose 和 obligations 给正文及义务。

每个任务材料的 `policy` 块是当前生效的项目字面约定：`version`/`source` 说明版本与来源（作者原话或内置默认），`forbidden_terms`/`forbidden_name_chars` 给出规则，`scope` 说明**本阶段实际检查哪些字段**。该块与执行检查共用 `contracts.ENFORCEMENT` 一张表，所以声明与校验不会脱节；越出 scope 的字段不检查，违反 scope 内字段以 `literal_policy` 拒绝并在 details 里列出命中字段与命中词。改规则用 `lexical` 命令。

`read --task ID` 返回全部必读完整记录；`--record 名称` 读单个完整记录。`recall --task ID --chapter N` 读冻结目录中的完整历史章，`--state` 读完整前态。必读 state 按参与人和开放承诺选择，complete_state 永远可补读。结构选择不证明其他事实语义无关；story 完整包含当前引用节点及显式前提，全设计仍有入口。

hash 是规范 JSON 的 SHA256：UTF-8、ensure_ascii=False、sort_keys=True、紧凑分隔符、allow_nan=False。正文哈希也基于 JSON 字符串值，不是裸文件字节。来源完整性不证明阅读理解。

## 结果

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

`check` 是给 Worker 的格式自检：把候选回执从标准输入管道进去（`check` 无需 `--file`，也可省略 task_id），它按与 submit 相同的校验运行但**不提交、不消耗额度**，并直接报告缺哪个字段或哪个枚举不对；会话取自身份进程或任务自身。它的存在是为了让执行者**不必读引擎源码确认格式**——源码不是任务材料，读它会显著推高上下文成本。常见拒绝对应的期望形状：前值不匹配时 details 带 `current`（照抄为 before，新键为 null）；`evidence_scope`/首读覆盖带 `frozen_chapters`；`review_coverage`/`finding` 带 `expect`/`valid_criteria`；`event_op` 带 `valid_ops`；`opening_option`（choose）带 `valid_options`。报错里没有的形状不要去源码里找，用 check 试算。

| 阶段 | data |
|---|---|
| opening_options | 当前门 gate 与 2～3 个 options，详见 [逐门开书](opening.md) |
| world_model / world_review | 完整世界记录与独立核验，详见 [世界模型](world.md) |
| opening_contract | 依据闭合选择和核验世界形成完整约定，不能更改用户选择；模板即 CONTRACT_FIELDS 骨架 |
| book_plan / volume_plan | intent/ending_conditions/nodes。节点 id/line/cause/choice/cost/outcome/disclosure/depends_on；ID 唯一，引用存在，无因果环 |
| design_review / contract_review | verdict/checks/findings/obligations；独立核验 proposal 来源，证据 chapter=0 |
| plan | plans 恰好覆盖冻结窗口；chapter/goal/obstacle/choice/cost/change/ending/node_ids/participants，可带 new_entities/obligations/schedule |
| profiles | 恰好覆盖 payload.entities；entity/desire/fear/limit/voice/knowledge_boundary |
| write / repair / redesign | title/完整 prose/summary/具体 self_check；不交 events 或 candidate_events |
| chapter_review | facts 和 reader 两套完整回执；事实通过需 events/summary/elapsed_days，首读已持久冻结 |
| scope_review / scope_synthesis | 范围核验和 coverage=[{chapter,reason,evidence}]，恰好覆盖冻结正文 |

有世界模型的章计划还须声明 world_refs=[领域:id]，引用须存在，完整关联记录随任务交付。计划义务为 {id,category:facts或reader,text}；硬日程为 {basis:main_clock,day:整数,event:具体事件}，提交主线时间区间须覆盖该天数。

## 首读与审稿

首读为 `{task_id,input_hash,session,data:{reads:[{chapter,desire,obstacle,change,read_on_reason}]}}`，完整覆盖冻结正文，每项具体体验非空。相同内容幂等，改体验或换人拒绝。

checks 恰好覆盖模板，各项 {id,result:pass或fix,reason,evidence:[...]}。证据 {chapter,quote,start?}；缺 start 时引文必须唯一。time/language 附 challenge={risk,disposition:satisfied或violated,reason,evidence}，对应 pass/fix。

findings=[{criterion,severity:blocker或quality或note,reason,evidence,target_chapter,repair_scope:local或chapter}]。实质 finding 与 fix 检查一致，修复起点由 target_chapter 明示，不从举证位置猜。义务逐项回 {id,result,reason,evidence}，未履行者须关联带 obligation_id 的实质 finding。

事实核对正文覆盖、连续性、资源、知情、时间、世界规则和空间；阅读核对追读、人物、变化、情绪代价、语言、重复和有效展开。跨章核对因果、人物弧线、兑现、节奏、世界规则和覆盖。程序检查协议及证据，独立审稿者负责判断语义。

## 事件

每条事件 evidence 引当前章完整正文，按数组顺序结算。只有 facts.events 可以成为正式事实。

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

elapsed_days 等于主线时钟增量。引文真实、时间词存在及数值一致只证明机械条件；知情、代价与路径是否成立仍独立判断。
