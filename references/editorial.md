# 人物、场景、改案与关闭

何时读：任务含 `capabilities.editorial=editorial/1`，尤其是人物重核、补丁、正文偏离、卷末与完本。新建及明确改约默认 `editorial_features=true`，要求 narrative_tracking；已启用项目不能降级以绕过验收；旧生效约定缺该字段保持原协议，旧 pending 不注入新字段。检查版本随任务冻结：编辑能力为 3，约定声明了叙述视角时为 4（reader 多一项 `pov_consistency`），旧版本 1/2/3 的回执仍按原清单验收。

按本任务定位相关小节：profiles/plan 读“人物与场景”，repair/redesign 读“版本补丁”，chapter_review/alignment_* 读“正文偏离”，范围 root 读“关闭与根问题”，完本读“终审与精确交付”。空间及评测工具只在相关任务取用，不因能力开启每次通读整页；任务 brief 和模板是当前执行入口。

## 人物与场景

人物档案沿用 entity/desire/fear/limit/voice/knowledge_boundary，新增：

- tier：major/supporting/walk_on。
- biography：public_role/contradiction/values，均为具体文字；values 说明价值优先顺序。
- speech：register/rhythm/stress_shift 与非空 tactics 数组；可带 relationship_modes=[{entity,mode}]。
- 更新旧档案给 change_reason；引擎绑定完整成长史及 character_current 的 growth_basis，成长后相关人物下次执笔前自动重核。

档案解释行动和表达，不能自行确立经历、资源或知情。当前动机与成长事实仍由正文事件结算。档案整份按参与人交付，不额外派昂贵索引任务。

每章 plans 还交 scenes 非空数组，每场 label/intent/conflict/turn/present/speakers/dialogue_intents。present 属于本章 participants；speakers 为实际拟发言者，纯动作场景显式空数组。对白意图恰好覆盖 speakers，每项 entity/seeks/withholds/pressure/tactic/knowledge_topics；没有相关话题用空数组，隐瞒或恢复不需要时说明原因。

expansion_units 非空，每项 id/scene/focus/development/expected_change；scene 从 1 起引用场景，development 说明试探、阻力、误判或演出方式，expected_change 说明删掉会损失什么。短稿补实这些作用，避免同义扩写。静章不强加危机，持续高潮不强插休息。

首章批准保存准确正文样本、声线、traits 与作者原话为 style_anchor。章审新增 character_consistency/stable_facts/dialogue_identity/voice_match，范围审新增 voice_evolution/revision_intent；约定声明了 `pov` 时另加 `pov_consistency`（清单 4），核验约定的人称与视角范围是否稳定、换视角是否作了交代，未声明视角的项目不排此项。没有对白或修订时仍说明本范围实际情况并举证，不强迫额外对白或虚构修订目标。

## 版本补丁

repair/redesign 可以交完整 prose，或者以下两种方式之一；仍交 title/summary/具体 self_check：

```json
{"base_hash":"本任务 base_draft.prose 的规范 JSON 哈希",
 "patches":[{"start":123,"old":"准确原文","new":"修改文字"}],
 "repair_note":"说明实际改动和保留部分"}
```

```json
{"base_hash":"准确基稿哈希","reuse_original":true,"repair_note":"核对原文仍成立的具体依据"}
```

prose/patches/reuse_original 三选一。start 是完整基稿的 Python 字符位置；补丁不重叠，不对空 old 插入，不原样替换，不清空整章。`commands.patch --old 原文 --new 新文 [--start N]` 返回准确基稿哈希及补丁；歧义时给目标 start。基稿、前态及修改义务仍必读，局部编辑不承诺无需读取全章。

程序合成全文后执行原篇幅、字面规则和额度检查；预检回滚不计次，实际 repair/redesign 计同一章的共享额度。补丁和复用都重新派独立审稿者完整首读及事实/阅读检查，保存补丁审计，不自动免审。新写首稿无基稿，不接受补丁。

## 正文偏离与独立改案

通过事实与阅读核验的章审增加 alignment={action,reason,realizations}。realizations 恰好覆盖本章 node_ids，每项 node/after/reason/evidence；after 为 seeded/advanced/resolved/not_realized，实际发生的节点须与 facts.events 的 story_node 一一对应。

设计节点可选 effects=[{id,text}] 和 criteria=[{id,text,required,effects:[作用ID]}]。required 缺省 true。有判据的实现填写 fulfilled_criteria=[{id,actual_effect,evidence}]；resolved 必须覆盖全部必要判据；可用 prior_criteria=[判据ID] 承接正式前态已核验的实现，保留原章证据，不强迫正文重演代价。未实现的模板判据从 fulfilled_criteria 删除，不填空白或假通过。引文真实性与覆盖由程序验证，实际作用是否充分由独立审稿者判断。

| action | 含义与下一步 |
|---|---|
| follow_plan | 实际节点状态按原计划实现，正常提交 |
| adapt_future | 当前内容及事实成立，原计划出现部分实现或披露调整；提交实际结果，再阻断下一章并独立改案。授权终点或末章不能将缺口推给未来 |
| align_design | 保留当前稿及其核验材料，不入库，进入当前章改案；额度不增加 |
| repair_prose | 事实或阅读确有 fix 和 findings，走原返修阶梯；不能两类 pass 却要求改文 |

首章认可仍先于未来改案，已有首章版本的认可不能代替改稿认可。

改案依次为新的 alignment_plan → 新独立 alignment_review。alignment_plan 返回 reason/完整 plan/designs；designs 可为空，或 [{scope,data}]，最多全书 book 和当前 volume:ID 两个范围，按全书后当前卷排序。既有线路职责、已开始实现节点语义、所有必要节点均保留；部分实现可扩展章号窗口但不能改变作用或判据，已兑现节点不改定义；新增后果用新 ID。不能改作者约定或借删除节点解除缺陷。

独立改案核验按设计模板逐项举证（候选材料 chapter=0，当前稿为实际章号），通过后原子采纳设计和计划，清理未写窗口。当前稿仍派新的章审，旧首读和 pass 不转移；未来改案核验完才写下章。同一 hold 两轮失败保留原稿、原目标和次数，不能通过 resume 清零。

## 关闭与根问题

卷末和全书 scope_synthesis 的 root 在普通范围核验之外增加 closure，绑定 payload.closure.context_hash。六项检查 scope_question/dramatized_process/character_choice/cost/aftermath/handoff；每项 id/result/reason/evidence，result=pass/missing/defect/author。

| decision | 条件与字段 |
|---|---|
| accept_close | 普通审稿 pass，六项全 pass；保存当前版本关闭记录 |
| continue_scope | 普通审稿 fix；existing_content_valid=true，无 defect/author；missing_function/completion_path/length_basis，append_through |
| revise_range | 普通审稿 fix，range=[起点,终点]；原子建立候选分支，传播实际覆盖到本范围末尾，原正式稿保留 |
| needs_author | 普通审稿 fix；具体 question 和至少两项 options=[{label,impact}]；保留现场，不允许 resume 绕过 |

后三项也须给普通审稿对应的实质 findings 和准确 target_chapter，不能用追加遮掩已写缺陷。

continue_scope 只在当前卷真实尾部进行，全书补写落在末卷；无后继正式章、无在途修订。单轮最多 scope_append_limit 章（默认 3），不能超出明确章节授权或总篇幅上限。保存独立 scope_ends，不覆盖作者原约定或历史章链；后续卷边界随增量顺延。补写先通过独立未来改案，最后重新做卷审、根问题验收及全书审，不直接标完本。

continue_scope/revise_range 还需 repair_case={root_ref,goal,verification_condition,evidence} 与 remedy={mechanism,substantive_change}。同一范围未解决案例沿原稳定 root_ref、目标与验收条件；不以任务 ID、换标签或改措辞重开额度。每个根问题最多两轮不同实质方案，撤销分支不退轮次，改约也保留案例与章节额度。

范围 root 若 payload.remedies 非空，填写 remedy_review，恰好覆盖 case_id/round_id，每项 result=pass|fix/reason/evidence。最后一轮仍须先验收；最后失败回执实际保存后暂停，不靠第三轮提案拒绝丢掉验收。当前版本不嵌套修订，先完成或撤销当前候选。

作者问题只由具体改约进入独立核验来回答。contract_review 模板中的 blocked_resolution 绑定原 question_hash，result=answered，并说明实际变化如何回答问题；没有回答不能解除阻断。根问题预算不会由此清零。

## 终审与精确交付

全书 closure 的 completion_coverage 恰好覆盖 payload.sources：作者读者承诺、终局、母题（约定声明时）、世界规则、禁区、风格、核心关系、弧线与反馈，以及设计节点、线路、已登记承诺及根问题。每项 id/result/reason/evidence；核心项必须 fulfilled，非必要节点/线路可有依据地 permitted_open。仍须 prose_hashes 完整对应准确章号及哈希，并声明 source_coverage_checked/cross_chunk_checked，从正文发现列表之外的漏项。

complete 核对当前全部卷关闭、全书来源覆盖、根问题、首章认可、实际篇幅和事件链，再保存不可变 completion_snapshot。`deliver` 从该快照导出 book.md/book.html/delivery.json，清单含快照引用、章节哈希及文件内容哈希（规范 JSON 字符串的 SHA256）。导出失败只重试 deliver，内容完成状态与快照不变。已完本的 export/html 同样使用冻结版本。

## 按题材使用空间能力

作者约定可选 anchors=[{entity,key,value,policy:fixed|eventful}]、links=[{id,a,b,kind,path属性…}]。锚点可指已存在实体或地点；地点的楼层/房号按 fixed anchor 保存，用途绑定用 eventful anchor；已成立地点父关系保持稳定。正文事件均须独立审稿给 evidence：

| op | 业务字段 |
|---|---|
| anchor / anchor_assert | entity/key/value，首次 policy 缺省 fixed；再次断言须相同 |
| anchor_change | entity/key/before/after/reason，仅 eventful 可改 |
| link | id/a/b/kind:path或sight或sound，可带 open/directed/min_days/requires:{事实键:值} |
| link_change | id/before/after/reason，前后为 open 布尔值 |
| placement | entity/before/after，位置为 {place:ID} 或 {holder:ID}；交接双方在同一已知地点，持有链不成环 |
| travel | entity/from/to/links:[逐段路径ID]；可同时给 depart/arrive，单位为主线天数 |
| perceive | observer/target/channel:sight或sound/from/to；跨地点须直接给 link，不自动更新 knowledge |

有 path 拓扑时使用 travel，不能以旧 move 的文字路线绕过条件；未建拓扑仍用旧 move。已知耗时为下限，未知段不捏造数字。已记录到达下限由携带物继承，转交或放下不清零；未给精确时间时不宣称移动耗时已验证。拓扑只核对登记连接、条件与时间；遮挡、指代、视距和生理能力仍由独立审稿判断。

## 用量与文学评测

`usage` 观察任务信封、已接受回执和 CLI read 实际交付字符；未记录的尝试或宿主计费为 null，字符不换算费用。`scripts/observe.py summary 宿主观测.jsonl` 对 provider/session_id/request_id 去重，同调用冲突拒绝累加；输入非缓存 token、缓存读取和输出分别记录，任一缺失则总量未知。观察工具不推进故事。

离线盲测工具用 `scripts/quality_eval.py prepare --manifest 清单.json --out 独立目录` 随机化完整样本，保留私有植入位置与预期；评审只获得自己的 input.json。先用 `first-read --input 样本/input.json --file 首读.json` 冻结首读，review.json 的 first_read 必须与冻结 data 一致，再 `score --directory 评测目录` 统计定位命中、漏检和已裁决误报。原稿不是金标准，没有独立裁决时误报率留未知；预期的文件/工具隔离由宿主落实，工具不证明模型真的盲读。所有评测数据存小说项目或独立临时目录，不写进 skill。
