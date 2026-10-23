# 运行与恢复

何时读：初始化、主干循环派工、续写、修订和任务恢复。字段格式见 [协议](protocol.md)，创作判断见 [创作与自比](craft.md)。

## 按场景定位

| 当前需要 | 读取小节 |
|---|---|
| 新建或导入设定 | [开书入口选择](opening.md#入口选择)；已有项目先看下面的运行前提。 |
| 授权正文、续租、循环派工 | [目标与主控认领](#目标与主控认领)、[主干循环](#主干循环默认执行路径)。 |
| 收到 action、不知道下一步 | [动作分支](#动作分支)。 |
| 认领、提交或恢复原会话 | [任务交接](#任务交接)。 |
| 暂停、反馈、改约或改字面规则 | [暂停与修改](#暂停与修改)、[字面规则](#字面规则)。 |
| 修改历史正文、分析范围、处理超界方案 | [修订影响分析](#修订影响分析)、[自动回改边界](#自动回改边界)。 |
| 章节目标、完本或文件交付 | [阶段结束与交付](#阶段结束与交付)。 |
| 使用外部模型进程 | [可选子进程适配器](#可选子进程适配器)；普通主干循环不需要读本节。 |

## 运行前提与初始化

2.1.0新CLI项目默认启用独立连续性核验，旧项目不自动切换。`status.assurance`分别显示连续性模式与宿主可信性，完整协议见[质量与宿主](quality.md)。required核验会增加真实读者调用，不能把下文旧机械路径的历史成本比例当作新模式费用保证。

ROOT/PROJECT 替换为绝对路径，项目产物不放技能目录。默认执行路径为主干循环调度子 agent；主干推进已授权目标，子 agent（Worker）只处理当前冻结任务。状态变化以真实命令返回和数据库提交为准。主干生命周期由宿主提供，本协议只约定业务推进与任务交接。

进入 world_model 及后续创作派工前，主干确认宿主能实际创建独立 Worker，并把宿主返回的执行身份与 task_id 对应保存。宿主不支持时保留在途任务并报告能力缺失，不能通过新造 session、同一主干批写或新子进程冒充空模型历史。会话身份由宿主注入；环境变量和 claim 只用于协议核对，不是模型隔离证明。

| 项目状态 | 开始方式 |
|---|---|
| 已有 PROJECT，续写或恢复 | 先 status，再 advance --compact；保留当前任务、候选和授权，不重新 init。 |
| 新 PROJECT | 按 [开书入口选择](opening.md#入口选择) 决定逐门开书、导入完整约定或 intake 部分要求。 |

已有项目的最短恢复命令：

```bash
python3 "$ROOT/scripts/novel.py" --project "$PROJECT" status
python3 "$ROOT/scripts/novel.py" --project "$PROJECT" advance --compact
```

开书交付按 outline_ready 的实际卷纲覆盖说明；卷纲与章纲为必选阶段；不将设计完成视为正文授权。

## 目标与主控认领

直接导入完整约定的默认目标为试章；逐门流程按当前卷纲策略交付开书设计，不自动获得正文授权。作者已授权正文后，用 `run --through N --source 原话` 或 `run --complete --source 原话` 保存目标并取得 owner。后续主控治理命令带 `--owner 返回值`；`renew --owner 返回值` 续租。过期后重新 run 认领，沿用已经授权的实际目标，不扩大范围。

## 快速无人值守：五章一组

快速无人值守按 `run --complete --fast --source 原话` 或 `run --through N --fast --source 原话` 在原授权目标上启用；模式保存为 `writing_mode=fast`，以后未指定模式的 run 沿用，`--standard` 恢复普通模式。模式选择不增加正文或作者裁决授权。首章取得准确版本认可后，同卷内的顺序执笔可优先采用快速组，减少新上下文启动和相同来源的重复投递。两组均须逐章冻结、完整成稿、自比、核账与原子提交；启用连续性保障时逐章独立核验。历史单次运行的费用比例和返修率不证明新流程会省多少token或保持相同文学质量。作者明确要求逐章新会话时用 `--standard`；模式属执行策略，总编在已授权目标内可直接采用，交付复盘注明实际模式。

首章仍单独写并取得准确版本认可；之后每组由一个真实 Worker 最多连写五章，不跨卷、不越过授权终点或缺失章纲。每章单独冻结、完整成稿、自比与提交，沿用固定章纲，事实只在该章通过后入库。不能一次交五章后跳过中间核验。返修仍使用本章有限额度，同一 Worker 只返修当前章，通过后才写下一章；暂停、停摆或需要作者决定时结束该组。

- 主干按原路径 advance 派出本组首任务，取得真实 Worker 会话 ID 后 prepare-worker 并注入返回的 worker_env；随后 `watch --owner ID` 等整组完成，不逐章另派 Worker。
- Worker 提交返回 `worker_boundary=continue` 时，执行当前 task.json 的 `commands.worker_next`。该命令只允许从本人已提交的最新任务接续当前组，不授予 advance、认领主控、改纲或作者权限。
- 返回下一任务后，按返回值更新 `NOVEL_TASK_ID`、`NOVEL_TASK_PATH`、`NOVEL_EXECUTION_CLAIM`，保留同一 `NOVEL_SESSION`；读取新 task.json、brief 和 read 返回的新增/变更必读材料。执行身份只在引擎授权的组内接续时更新。
- 同一组中已经实际读取、名称与哈希都相同的记录可复用；变更记录重新读取，`read --all` 始终可取完整材料。新组不继承此缓存，也不能复用旧组会话。
- 满五章、卷界、目标、规划阶段或作者边界时，submit 返回 `worker_boundary=finished`；`worker-next` 返回 `batch_finished` 同样结束。下一组由主干派新 Worker。重复接续返回同一个待办任务，旧回调不能跳过它。
- 主干收到 `wait_for_batch` 时继续等待本组，不另派工。进程退出但组仍 active 属于未完成；确认原执行者已停止后，可用 `pause --cancel` 结束该组，再 resume/advance 派新 Worker，已提交章节与返修额度保留。活跃组内不切换模式或改变目标。

本模式复用同一组的模型上下文；组间独立性仍由宿主提供。工程验证不等于模型写作速度或文学质量保证。

## 主干循环（默认执行路径）

主干执行治理命令，子 agent 负责读取材料、写卷纲与章纲、执笔和返修；workflow 决定下一任务，SQLite 保存实际状态。开书门任务（opening_options）例外：主干在同一会话内自执，换组时延续已选方向与否决记录；完成全部开书选择、进入 world_model 后恢复派工。主干只保留授权目标、owner、当前 task_id 与宿主子 agent 会话的对应关系，以及简短执行状态。

| 交接点 | 主干动作 | 核实依据 |
|---|---|---|
| 取当前状态 | advance --compact，已有 owner 时继续携带。 | 当前 action，不预猜阶段或自行拼任务。 |
| task_ready | **开书门任务（opening_options）由主干自执**：读 task_path 的 task.json 与同目录 brief.md，`read --task` 取必读（同会话连门且 records_hash 未变可豁免），从 result.template.json 起稿一次成稿后 check/submit（session 填主干身份，门任务不绑定会话）。其余阶段按任务交接规则派工；快速组内只由原 Worker 接续。 | 原执行者状态与 claim；普通新任务和快速新组用空历史会话，沿用当前模型设置。门任务对主控放行 read/recall（contracts.CONTROLLER_STAGES），正文阶段不在此列。 |
| Worker 结束 | 接收身份和状态摘要，正文与完整回执留在项目。**子 agent 空转结束**（无提交、无报告，或宿主显示其模型调用连续空响应重试）不是流程事件：用 `advance --compact` 重派同一 pending 任务（引擎重渲染视图，`redispatch_count` 递增，上次未提交的回执草稿被隔离为 `result.stale.json`；未提交不计任何返修额度），普通模式换一个新子 agent；快速模式先按上节确认原执行者停止，pause --cancel/resume 后重开组，不把已绑定组转给新会话。连续两次仍空转则保留现场报告作者，不要靠反复重派碰运气。 | task_id、真实 session、accepted/checked、worker_boundary 或错误码及原因。 |
| 核实提交 | 无人值守用 `watch --owner ID`（默认一步：等当前任务提交后直接取下一派工）；需要显式核实时 advance --compact --after 该任务ID。 | wait_for_submit 表示未提交，resync 表示重取状态；不能仅凭 accepted_chapters 判断卷纲或章纲是否已采纳。watch 的等待发生在引擎进程里，主干会话不为等待付费。 |
| 接续 | 按下面的动作表继续。 | 章节、卷纲、Worker 和卷末均非授权目标停点，修订采纳、完本与交付也在循环内。 |

### 动作分支

下表的命令均使用同一 PROJECT，已有 owner 时继续携带；作者已有明确授权直接执行，仅缺失的作者决定才询问。

Windows 控制台乱码时的通用规则：引擎输出是 UTF-8，GBK 终端显示会乱；需要人读的长内容一律走引擎物化的文件（brief.md、board.md、question.json、dispatch.md、task.json、html），机器可读的短 JSON 才看控制台，或先 `$env:PYTHONUTF8=1`。自行重定向 JSON 时注意 PowerShell 5 的 `Out-File -Encoding utf8` 带 BOM，Python 读回要用 utf-8-sig。

无人值守连写时，把"派 Worker → 等它提交 → 取下一派工"整段交给 `watch --owner ID --steps 1`：它派完当前任务后在引擎进程内等待提交（期间自动续租），任务完成即取下一 task_ready 并连同 task 一起返回；快速模式会等整组结束再返回；主干每次醒来只做一件事——按返回的 task 派 Worker，再运行一次 watch。遇到 await_author、await_choice、paused（含返修停摆与额度用尽）、revision_blocked、目标终点或 Worker 长时间未提交（idle）时 watch 停下并带回该动作，按上表处理。`--steps 0` 用于外部派工器长跑：每个被监督的派工会追加一行到 work/watch.jsonl。等待期间不产生任何主干推理，这是它替代"sleep + status 轮询"的全部意义。普通模式的无人值守同样适用；无人值守期间不要用 advance 代替 watch 等待，实际输入、缓存与输出费用从宿主观测核对。

| action | 主干下一步 |
|---|---|
| task_ready | 按任务路径派工；先核对仍在运行的子 agent 与 claim，具体见任务交接 |
| wait_for_batch | 原 Worker 正在接续本组，用 watch 等待整组；不要为下一章另派 Worker |
| worker_blocked | 核对 status.execution_failure 与恢复动作，修复身份、凭据或材料错误后，对同一任务 prepare-worker --reset-failures；保留稿件和文学额度，不直接重派绕过 |
| review_required | 保留候选与执笔Worker；按[独立核验](quality.md#主控与执笔交接)实际派出另一读者，用prepare-observer绑定，先冻结纯读再比较；歧义交作者准确裁决，主控不代审 |
| review_complete | 联系原执笔Worker，保留其上下文并续有效凭据，以准确候选重做submit；仍以outcome和committed_chapter核实结果 |
| wait_for_submit | 等待或联系当前子 agent 完成提交；它已结束时核实错误并沿允许会话恢复当前任务，不派下一个任务 |
| resync | 放下过期的 after 回调，重新调用不带 --after 的 advance --compact，以当前任务为准 |
| revision_ready | 修订属于当前授权目标时执行 promote，再回到 advance --compact；作者明确要求先看候选再决定时，交付候选并等待该决定 |
| revision_blocked | 交付 proposal.plan_path 中的完整修复方案，说明请求范围、实际影响、动作数量；保持原稿，等待作者对准确 plan_hash 的明确决定，不自动放宽范围 |
| ready_to_complete | 执行 complete；验收通过后执行 deliver，取得正文、阅读页和清单后才报告完本 |
| completed | 从完本快照执行 deliver 或恢复失败的交付；交付成功后结束 |
| target_reached | 刷新 html，按约定导出并交付实际完成的章节范围；不冒充全书完本 |
| world_ready / outline_ready | 交付返回的世界及实际卷纲覆盖；已有正文授权但尚未保存时，用 run 保存同一授权后继续，否则到本次开书目标结束 |
| await_choice | 返回携带 `board_card`（work/board.md，引擎渲染的作者卡片）与 `question_card`（work/question.json，可直接投给宿主提问组件的选项结构，封顶 4 项）。先在回复正文贴出 board.md 内容（或链接），再用 question.json 的选项原样发起提问，不自拟摘要替换引擎文案；宿主选项数更低时截到“换一组”为止，不删板面方案腾位，自定义走宿主 Other/自由填答。不在控制台直接读长 JSON（GBK 控制台会乱码）也不手工重排版。--compact 时返回只带门名/哈希/option_ids，完整板面在 board.md 与 work/last-advance.json。已有该板的明确选择则按卡内 id 与 hash 执行 choose 后继续，否则等待作者选择。第一门未定向时另有任务目录的 `catalog.md`（compact 的 catalog_path）：目录铺陈用正文贴出，不用提问选项装十二个类目 |
| await_author | 已有对应 prose_hash 的明确认可则 approve 后继续，否则提供该版本首章并等待认可 |
| paused / repair_exhausted | 保留候选和失败记录，报告具体阻碍；不自动 resume 或重派任务来重置预算。正文返修额度用尽（`REPAIRS=2`/`REDESIGNS=1`），或同一条漂移/机械项连续两轮未解决（`repair-stalled`）时，`resume` 不重置额度，而是保留候选并交由作者决定：再返修一轮（只改被点名的项）／保留候选并暂停，另行调整约定。用 `answer` 记录原话；只有明确追加一轮才授予该轮机会，不能接受机械失败稿直接入库。旧 `accepted_findings` 留档可见，旧卡的接受选项会拒绝且不丢候选 |
| preparing | 按初始化入口导入已有完整约定或完成开书准备；只对真实缺口等待作者，不空转调用 advance |

未登记的动作和命令错误按返回的 code/details 核实修正入口，不猜测成功或无条件重试。字段拒绝交回当前子 agent 修正；完整性失败、作者裁决和修复耗尽保留现场并报告。可恢复的执行失败先核实任务是否已提交、原执行者是否仍在运行，再决定等待或恢复；换执行者不增加返修额度。

outline_state 表示真实前态与固定章纲不符，保留现场交作者决定修订范围，不自动改纲。projection、chain、state_integrity、source_integrity 与 schema 是数据或版本问题：保留候选和失败信息，停止状态推进；已冻结的 read/recall 仍可用于定位来源。写作任务不调用底层存储保存投影，不改写 schema，不修改或复制临时引擎来取消判据。程序在派工/提交前和事务保存前检查聚合状态；未通过时该次状态变化回滚。

submit以outcome和总findings表达业务结果：repair_required是待返修，continuity_review_required是候选已保存并等待独立连读，chapter_committed才是正式章节。valid/accepted与transaction.persisted不代替committed_chapter。预检永不耗文学轮次；相同或仅空白变化的已知失败稿返回no_progress，不吞新轮次。无人值守目标不自动提供首章认可、追加返修或改约授权；required宿主模式还须真实人类通道证明，不能自写source冒充。

返修裁决的 id 绑定候选正文、约定、章节、项目版本、问题及已消耗额度；使用当前 status.author_decision.id 原样回答，不拼接固定停止点名称。改约保留候选、额度与未回答问题；作者追加额度时按问题绑定的章节处理，旧答复不能套用到另一个候选版本。

## 任务交接

advance --compact 的 task 只含任务身份、阶段、task_path、identity_path、brief_path、dispatch_path、claim 等派工信息；完整 task.json 仍按原协议写入 task_path，作者选择板与非派工动作保持完整（--compact 下板面回显压缩为哈希与 option_ids，全文在 board.md 与 work/last-advance.json）。主干把 task_path 交给子 agent，由它完整读取本任务。commands 为 argv 数组，按数组执行，不拼 shell 字符串。

每个任务目录另写 identity.json 与 dispatch.md：identity.json 是该任务自己的身份副本（task_id、input_hash、阶段、chapter/scope、delivery_phase、requires_new_worker、入口与版本，以及 worker_env 里应注入的变量名）；dispatch.md 是引擎从冻结任务渲染的 **Worker 自举卡**（环境自举命令、执行步骤、认领状态、argv 命令行、常见坑）。identity 供 Worker 与主控核对身份、供失败信息说明该注入什么，**不授予任何权限**：除 opening_options 对主干放行 read/recall 外，read/recall/patch 仍只对宿主注入 NOVEL_TASK_ID 与 NOVEL_SESSION 的派工进程开放，且命令里的 --task 必须等于 NOVEL_TASK_ID；worker_env.NOVEL_SESSION 为空表示宿主尚未注入执行身份，不能自行编造；已有 claim 时派工身份沿用其 session。身份凭据只存在于宿主环境，不进任务文件、也不由 Worker 写回。

除主干自执的 opening_options 外，新任务派真实新 Worker，填真实 session（普通模式一个会话只做一个任务；快速模式仅冻结的同组正文及其返修可接续，跨组仍按 session_reuse 拒绝）；**委派 = 转发 dispatch.md 路径 + 角色、task_path、一句背景和简短提交状态要求**，不手写环境自举与协议复述（手写派工提示曾教 Worker 执行 claim 而被 worker_boundary 拒绝）。子 agent 直接完成当前任务并 submit，worker_boundary=finished 后结束，不自行 advance 或代行作者与主干命令。**初始身份准备由主干执行**：用 `prepare-worker --task ID --session 宿主真实会话ID`，按下节交付 worker_env；Worker 不执行 claim。快速组内下一任务的凭据由 worker-next 生成。claim=null 表示尚未认领，不表示新 Worker 已可读取正文。

主干已派出的子 agent 仍在运行，或 claim.expired=false 时继续等待，不重派；claim=null 只表示没有执行认领，不证明没有运行中的子 agent。expired=true 表示提交前须重新认领，也不证明旧执行者已停止。已写好 result.json 但租约过期时，由主干沿允许会话重新 prepare-worker，Worker 使用新注入凭据后重提，保留已填回执。恢复任务先 status、再 advance --compact，以当前任务为准，不手改库；要看全部派工的生命周期用 `status --tasks`（id/状态/阶段/会话，取代直接查库）。

### 执行身份与技术恢复

材料交付按execution_id及名称/hash缓存；换Worker或同名空历史重开（prepare-worker --fresh-context）重新交付全部必读，保留任务、候选和文学预算。成功read/ready不清除其他操作的失败计数，只有对应操作确实成功或正式完成才清除未阻断记录。新任务冻结引擎与规则指纹；engine_changed按返回动作固定构建或保留稿件后显式重新冻结，不换临时引擎继续。

世界模型及后续派工使用 `novel-ledger.execution/1`，`task.execution.state` 为 `await_worker_identity`、`ready`、`blocked`；开书门是 `controller`。主控先创建真实独立 Worker，使它停在自举边界等待准备；用宿主返回的会话 ID 执行：

```bash
python3 "$ROOT/scripts/novel.py" --project "$PROJECT" --owner "$OWNER" prepare-worker --task "$TASK" --session "$SESSION"
```

宿主将响应的 `worker_env`（含当次凭据）仅交给该 Worker。`prepare-worker` 认领同一任务并刷新派工卡，保留 `result.json`，不把它当遗留草稿隔离。初次 `session` 为空时 Worker 等待主控准备，不遍历历史、不复制旧身份。不能提供真实身份的宿主应报告能力缺失。这个入口核对宿主声明的身份与租约，不证明实际模型隔离。

首条 `commands.read` 会自动完成 ready 验证，失败不交付材料；`commands.ready` 只用于宿主诊断，无需额外模型往返。生成的 Worker commands 经 Python `worker` 入口执行，兼容 macOS/Linux/Windows；不依赖 PowerShell 自举。宿主不能注入环境时，可在外层 `worker` 的 `--` 前传 `--session` 和 `--execution-claim`，值必须来自本次主控准备响应。凭据不写入 task/identity/dispatch 或模型起草的回执；入口在内存中补齐空 session 和缺失 claim，拒绝复用其他身份或凭据。schema/task_id/input_hash 仍从模板保留。底层旧命令保持兼容，新派工使用生成的 commands。

`details.recovery` 统一给出 `actor/action/retry_allowed/failures/limit`。身份、角色、会话复用和租约错误立即交主控；其他技术错误连续失败两次后返回主控。成功的实际操作清除未阻断的连续失败计数，ready 探测不清除计数。阻断保留 pending、草稿与文学返修预算，`advance/watch` 返回 `worker_blocked`，不空等到 idle。主控核实原因已修复后对同一任务 `prepare-worker --reset-failures`，不靠换 Worker、resume 或重派刷新计数。

通过 worker 执行的引擎命令错误由入口自动记录；CLI 看不到模型在引擎外执行的任意工具，宿主应按 `commands.report_error --code host_tool --operation 工具名` 上报失败，执行者同样遵循返回的恢复动作，不继续猜接口。仅靠本地 CLI 不能强制约束同权限进程访问源码和数据库。

### 远端集成后的便利入口

2.1.2保留以下便利功能，原有宿主、独立核验、执行世代和有限返修边界继续生效：

- 成功的Python worker命令在执行通道单独续租，按该租约原授予时长延长；不恢复已过期租约，不替换身份，也不因续租清除失败。世界模型、约定、卷纲、章纲默认授予3600秒以覆盖静默起草，正文默认300秒，主控显式seconds优先。直接嵌入API的宿主可调用worker_heartbeat，业务check/preflight本身仍可只读试算。
- CLI check/preflight遇到内容异常时返回outcome=repair_required、valid=false和完整findings，不消耗技术失败计数；原有结构化正文判据仍以outcome判断。执行通道另记内容预览连续轮次；相同诊断连续三轮返回stalled=true，停止盲试并交主控，不能借换会话清零；诊断改善或通过才更新这项观测。它不消耗文学额度，直接业务API试算仍不写库。协议、身份、完整性和宿主错误继续走原恢复规则；无关操作不能清空旧失败。直接API保留既有Error契约。
- `commands.read --save`将本次完整交付落到任务目录的read_pack.json、read_pack.md、read_ref.md；也可指定项目内输出路径。首次读取两份Markdown包，前章全文与证据不截断；同一上下文只复用已读且哈希不变的记录。压缩后遗失历史由主控用--fresh-context重新交付，不凭文件存在宣称已读。写盘失败回滚读取缓存；输出不能覆盖账本或互相别名。
- 程序不自动声明kept/clean，不给任意正文片段补造证据。自评与引文仍由实际执笔者逐项核对。减少碎短句仅在它割裂动作、思绪或因果时适用，以作者风格和本章节拍为准。

材料落盘量计入交付字符观测，不等于模型已读文件或计费token；实际费用仍以宿主观测为准。

### 路径与失效判定

commands/guides 由**当前安装**渲染（解释器取自身份进程，脚本取自身份文件），并用目录联接（junction/symlink）映射时两条路径实为同一份安装。派工前先确认命令里的解释器与脚本存在，再交给 Worker；**不要凭路径字面判断某条命令失效**——先文件系统核实。技能目录确实移动过时，回主控再执行一次 `advance` 刷新任务视图即可重建命令，不要手改命令、也不要在派工提示里让 Worker"忽略 task.json 的 commands/guides"（那会让 Worker 用错身份或漏读必读记录）。

### 正式任务与提交

| 阶段 | Worker 动作 | 结果 |
|---|---|---|
| 正式任务 | 完整读 required 及任务所需来源，按 result.template.json 填 result.json。格式不确定先 check，缺资料按 read/recall 补读。执笔阶段逐项写 drift_check 与 self_check。 | 当前输入版本的回执；不复制旧回执的结论，不凭记忆自报前态。 |
| 提交 | 执行 commands.submit；worker 入口在内存中注入当次身份与凭据。 | 漂移核算、字数、lint 与字面检查在提交时执行；worker_boundary=finished 后结束，主干再用 --after 核实；checked 只是试算，不代表已提交。 |

await_author 给准确 prose_hash；已获得该版本认可时由主干 `approve --prose-hash HASH --source 原话`，沿原目标继续。

## 暂停与修改

| 需要 | 命令入口 | 边界 |
|---|---|---|
| 暂停 | pause --reason 原因 | 保留任务与候选；--cancel 取消但留档。 |
| 恢复 | resume | 不增加额度；耗尽时保留材料并报告，不重开任务清零。内容与篇幅共享两次返修、一次重设计，字段拒绝与预检回滚不计次。正文候选返修额度用尽或停滞时，保留候选与已花额度，交由作者选择再返修一轮或保留候选并暂停调整约定；机械失败不提供“接受并继续”。旧卡接受选项会拒绝并保留原状态，选项之外的新决定仍走改约，代价照写进 impact |
| 候选稿反馈 | feedback --text 原话 | 对当前候选安排修复；已验收正文改用 revise。 |
| 历史正文修改 | revise --from-chapter N --reason 原话 | 必须声明作用范围四选一：`--through M` / `--changes-file` / `--proposal-hash` / `--to-end`；不给范围时命令直接拒绝，并提示先跑 revision-impact 查看影响终点。影响分析、后缀处理和完整范围验收见 [修订影响分析](#修订影响分析)。 |
| 作者明确要求的未写窗口重排 | replan --from-chapter N --reason 原因 | 已有草稿或正式稿的章纲不能直接删除；重排后的章纲重新过卷内状态链。 |
| 字面规则修改 | lexical --file 规则.json --source 原话 | 逐版记录，执行及恢复见 [字面规则](#字面规则)。 |
| 回收不可达文档 | compact | 只删除任何活动记录都到不了的内容寻址文档并回收空间；不改故事与账本状态，重复执行无副作用。 |
| 完整约定修改 | recontract --file 完整候选.json --source 原话 | 取消旧任务留档，新约定经机械校验激活后重新规划与执笔；已有正文时在继承父稿的新分支**自第 1 章重写全书**（父分支保留，可 discard 恢复），代价随已写章数线性增长——先向作者说明再执行；开书导入的状态条件见 [入口选择](opening.md#入口选择)。 |
| 答复作者裁决 | answer --decision-id ID --option 选项 --source 原话 | 只回答 status 的 author_decision 里已展示的选项，记录问题、选择与原话后清除 author_block；选项之外的新决定走 recontract（代价见上行）或重新提案。 |

作者明确改约时，暂时停用旧回改指令，先完成新约定的机械校验；原缺陷、已耗额度保留，撤销改约候选时恢复父稿原问题。不能借改约绕过修复额度或作者边界。改约是方向性决定而非答疑通道：已写 N 章的项目改约会在新分支重写 N 章，选项内可答的作者裁决用 answer 记录即可，不付这笔代价。

### 字面规则

项目默认禁词为“账本、入账、回执”，默认人名禁字为空；作者可按本书覆盖，不把个人命名偏好当引擎通用规范。以冻结任务 policy 的版本、来源、规则和实际执行 scope 为准，不在派工提示中另写一套规则。

lexical 将新版本追加到项目记录，旧版本保留；规则不属于作者约定，开书阶段也生效。修改会取消在途任务、作废旧视图，下次 advance 重新派工。约定激活、改约和 discard 均保留项目字面规则及其历史，撤销候选正文不撤销作者改规则的决定。字段及 literal_policy 拒绝见 [协议](protocol.md#冻结任务与资料读取)。

## 阶段结束与交付

`book.html` 是数据库的派生视图：正式 `submit` 在事务提交后自动刷新（快速组内逐章刷新），主干 `advance` 返回时也刷新，响应 `book_view` 提供路径与章节数。`check`/`preflight`、拒绝及事务回滚不改页面。刷新失败单独返回 `book_view_error`，不撤销已提交正文；主干用 `html` 重试或在下一次 `advance` 重建，不为页面错误重写正文。浏览器已打开页面时需重新加载才能看到新内容。

target_reached 表示授权章节目标完成；ready_to_complete 仍须 complete 验收。export 可导出纯文本（`--format md`）或简化 HTML，html 生成包含设计、事实和正文的全书视图，两者返回绝对路径；导出不代替完本验收。

**卷末不是审查阶段**：卷末闭合核对卷纲的结构化资源/位置/知情/人物终值、主线时钟 `clock.to` 与必要伏笔；自然语言 `exit_state` 只作说明，不宣称语义已被机械证明，不再有卷末范围审与根问题裁决。完本仍须 `complete` 验收：章数、每章篇幅区间、required 节点与线路解清、首章认可；之后执行 `deliver`，得到 book.md/book.html/delivery.json；交付失败重试该快照的 deliver，不重新写书。`usage` 查看实际记录字符，宿主 token 用独立 observe.py 导入观测，不从字符估算。

complete 的重复调用也复验准确快照；html/export/deliver 在写正式文件前通过同一只读服务重新核对冻结章节、完整事件链、正文机械项、首章版本和必需线路。旧 audit.ok 与 completed 状态均不能豁免。可变视图被改坏时，仍以已通过当前复验的完本快照恢复交付，不导出可变内容。报告 verification_scope=mechanical，unverified 明确列出模型隔离、作者原话真实性与文学质量。

工作台随项目初始化，协议与边界见 [叙事工作台](workbench.md)。阅读变化在新流程里不再派独立重读任务：受影响的章纲先由 `chapter_outline`（payload 带 `repair=True`，并提供修订影响与原因）按卷重排，冻结的 last 限制本批终点，区间外章纲由引擎保留并核对；纳入影响区间的正文重写，区间外后缀仅在显式前态与事实重放均通过时原样携带。

## 修订影响分析

`revision-impact --from-chapter N --changes-file 变更.json` 只读取已提交章纲、事件和哈希，不改项目、不返回正文。Worker 不能调用。变更说明由作者要求形成（例如抽读后发现的历史缺陷）：

```json
{"mode":"semantic","changes":[{"kind":"knowledge","key":"shen:source"}],"scenes":["scene:warehouse-confrontation"]}
```

| 变更类型 | changes-file 的声明 | 后文处理原则 |
|---|---|---|
| expression | 不带 changes，只改表达。 | 保持事实投影不变，仍核对后文前态。 |
| reading | 非空 reading_changes，声明人物、关系、母题、声线或披露关联。 | 受影响章及连续区间内的章纲重排后重写；无独立重读动作，区间外才可原样携带。 |
| semantic | changes 列实际变更坐标，可附 reading_changes。 | 沿事实与场景依赖分析，不完整时保守扩大。 |

kind 使用事实投影坐标（如 facts/knowledge/resources/relations/placements/hooks/reader_knowledge/node）；scenes 可省略，提供时必须是修订起章的实际场景。expression/reading 事实投影变化时按 revision_carry 拒绝，保留 pending 与旧稿。阅读坐标、版本标记和处理动作统一见 [叙事工作台](workbench.md#分级修订)。

语义分析沿显式 reads 与 depends_on 传播，受影响章节的已提交事件继续扩大影响；连续修订区间内的中间章节也会重写，其输出和场景依赖同样继续传播。story_node 同时更新节点与所属线路状态，两者均计入影响。缺少完整依赖、没有明确变更坐标或事件无法解释时保守扩展；move/placement/travel 涉及持有链、站位或到达时间的派生影响，目前也保守扩展。`last` 是事实与阅读依赖传播后的完整建议终点，rewrite_chapters 是连续修改区间；chapter_actions 只列 keep/local/rewrite，区间外为 keep。source_hash/sources 绑定分析的准确章节版本。**依赖声明的语义完整性不再有独立判断**：引擎只按显式 reads/depends_on 传播，空数组不证明故事没有联系，声明不完整时保守扩大；即使标为 complete，语义遗漏仍需作者抽读发现。分析结果另给出 `coverage` 与 `expansion`：后者写明保守扩大的原因（`undeclared_dependencies` 或 `unexplained_events`）、起点、终点与章数，并随 `status` 的 revision_run 暴露给主控与作者。

执行 `revise --from-chapter N --reason 原因 --changes-file 变更.json` 时会在创建候选分支的同一事务中重新分析，默认采用计算终点；显式 --through 不能小于该终点。扩大终点时，实际完整修改区间及 chapter_actions 同步扩大，新增修改章的事实输出与场景桥梁继续传播；分析命令的原建议不能冒充实际采用范围。不提供 changes-file 时保留手动修订入口，但必须显式选一边：`--through M` 收窄到受影响章，或 `--to-end` 确认改到当前末章——命令不会再把"改第 N 章"默认解释为"重写其后全部"。修改章仍须新执笔并按修正后的章纲重写；后缀章按动作重放或原样携带，机械核算通过后才能 promote。任务材料 revision_impact 携带实际采用的分析，表达及阅读修订不得改变事实。无论是否启用叙事跟踪、是否提供 changes-file，原样携带后文都核对显式输入与原版本前态，拒绝漏报变更造成的失配；已由重排章纲改变计划的待携带章转入返修。

### 自动回改边界

历史修订由作者明确请求发起。程序从最早 `target_chapter` 开始，先计算事实与阅读影响，按原样携带、局部修改或按重排章纲重写安排后续处理；请求区间不自动扩到范围末尾。表达或阅读修订保持事实投影，语义依赖未知时仍保守扩大，不能为缩小范围谎报 expression。

程序把本次请求与当前允许范围比较（边界来自 `editorial.revision_policy`）：自动回改限于**最近 limit 章**（`limit = contract.revision_limit`，缺省 `DEFAULTS['revision_limit']`；起章下限 `max(1, 末章-limit+1)`），单次重写章数超过 limit 记 `rewrite_limit`，修订区间与任一**已写满的整卷**（`end <= 末章`）相交记 `closed_volume`。超界时本次请求正常保存，原分支、正文和章节返修额度保持；完整修复方案保存在 execution.revision_directive，等待作者按准确 plan_hash 授权。

advance 返回 revision_blocked 时，顶层 proposal 为摘要，并将完整方案写到 proposal.plan_path；status 对应字段是 revision_proposal，无阻断方案时为 null。status 只提供路径，不保证文件已经生成；文件缺失时由 advance --compact 重建。两处摘要字段相同：

| 字段 | 含义 |
|---|---|
| plan_hash / plan_path | 当前完整方案的身份及派生文件路径；plan_hash 不等于 prose_hash 或任务 input_hash |
| first / requested_through / required_through | 起章、原请求终点及依赖分析后实际需要的修改终点 |
| action_counts | 各处理动作的章数；原样携带不计作重写 |
| violations / policy | 超界原因及此次检查的 limit 与已写满整卷；`outside_recent_window` 为起章过早，`rewrite_limit` 为单次重写章数超过 limit，`closed_volume` 为触及已写满整卷 |

主干据摘要说明范围与原因，交付完整方案路径；不把全量影响记录重复灌入对话。

主干调用 revise 也经过同一分析和边界，不能用未带 changes-file 的命令默认为全书重写。作者主动提出的历史修订仍按明确请求执行；主干不得用改约、重新 run 或 resume 绕过边界。

停点把处理方式交成作者决定时（见 [动作分支](#动作分支) 的 paused/repair_exhausted），项目暂停、status 的 author_decision 与 book.html 都显示待作者裁决的问题和选项，author_block 保存同一问题；此时不派任何写作任务，也不消耗返修额度。主干把问题和选项原样交给作者，作者选定后按原话记录：

```bash
python3 "$ROOT/scripts/novel.py" --project "$PROJECT" --owner "$OWNER" answer \
  --decision-id 待决问题ID --option '作者选定的选项label' --source '作者答复的原话'
```

答复须是已展示选项之一，否则以 author_decision 拒绝：作者另有第三条路时那是新决定，走改约或重新提案。记录写入 author_decision_history（同一问题、所选选项与作者原话），答复同时进入作者原话（author_feedback），清除 author_block；暂停原因就是该问题时项目恢复 running，否则保持暂停待处理其他停点。**顺序要求**：先 `answer` 记录裁决，再 `advance`/`recontract`。裁决会推进项目版本，派工在裁决之前冻结的任务随即失效（stale_task，只能取消重派），先派工后答复等于白派一个 Worker。下一步按新前提重新起草候选：世界交 world_model，卷纲交 volume_outline，章纲交 chapter_outline；改约定本身的问题仍走 recontract，其全书重写代价见[动作表](#动作分支)——主干转述问题时一并告知作者两条路径的代价差。没有作者答复时 resume 会以 author_decision 拒绝，不能用改约或重发绕过。

作者明确授权准确方案后，保存其原话并执行：

```bash
python3 "$ROOT/scripts/novel.py" --project "$PROJECT" --owner "$OWNER" revise \
  --from-chapter N --proposal-hash HASH --source '作者对该准确方案的明确授权原话' --reason '采纳修复方案'
```

HASH 取 advance 的 proposal.plan_hash 或 status 的 revision_proposal.plan_hash；起章、实际终点及变更内容必须匹配该方案。省略 --through 时采用方案实际终点，省略 --changes-file 时采用已保存变更；显式提供时须分别匹配 required_through 和完整方案中的 changes。程序重新核对章节来源、创作上下文及运行版本，字面规则变更等更新也会使旧方案失效；授权不增加章节修复额度。没有这项明确授权时只交付方案，不自动启动超范围修订。

若 revision_proposal 错误明确提示来源已变化，先核对当前状态、已保存的方案和原始请求，不继续重试旧 HASH。仍有同一批跨章缺陷时，用原 first、requested_through 和 changes 再调用 revise，不带 --proposal-hash 或 --source，让程序在原边界内重新评估；仍超界则保存新方案，再用 advance --compact 生成文件，重新交付准确哈希供作者决定。若已落入允许范围，则进入候选修订。revision-impact 只读分析，不替换已保存的阻断方案；不得把旧授权自动套到新哈希。

## 可选子进程适配器

仅在宿主通过外部模型进程执行任务时使用；默认的主干与子 agent 循环直接沿上文交接，不需要启动这层适配器。

command.json 是已安装模型宿主的 argv 数组。`host-step --command-json 文件 --owner ID` 执行一步；`host-loop ... --limit N` 在当前进程持续监督，遇作者边界、失败、暂停或目标终点停止。宿主用子 agent（而非子进程）执行 Worker 时，等价能力是 `watch`：等待与续租在引擎侧，派工由宿主完成。

通过 NOVEL_TASK_PATH/NOVEL_PROJECT/NOVEL_TASK_ID/NOVEL_SESSION/NOVEL_EXECUTION_CLAIM 提供身份；CLI 只消费其中的 TASK_ID/SESSION/EXECUTION_CLAIM，PROJECT 与 TASK_PATH 是给 Worker 进程定位项目和回执的便利变量，命令行仍须显式给 --project。宿主负责实际模型新会话；新子进程不证明空模型历史。超时终止并等待自己的进程；返回 0 且任务实际 done、连写组也已结束才继续。日志无法打开或进程无法启动时返回 host_launch_failed；认领后的各退出路径均释放任务占用，包括主控续租失败。

适配器另有 worker_finished、host_timeout、step_limit、host_launch_failed、needs_attention；step_limit 是适配器步数上限，不表示作者目标完成。advance 返回动作仍按上表处理。通用适配器不证明模型会话恢复能力，真实模型历史隔离和计费用量需另行验收。
