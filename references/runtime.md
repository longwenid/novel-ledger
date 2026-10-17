# 运行与恢复

何时读：初始化、主干循环派工、续写、修订和任务恢复。字段格式见 [协议](protocol.md)，内容判断见 [创作与写审](craft.md)。

## 按场景定位

| 当前需要 | 读取小节 |
|---|---|
| 新建或导入设定 | [开书入口选择](opening.md#入口选择)；已有项目先看下面的运行前提。 |
| 授权正文、续租、循环派工 | [目标与主控认领](#目标与主控认领)、[主干循环](#主干循环默认执行路径)。 |
| 收到 action、不知道下一步 | [动作分支](#动作分支)。 |
| 认领、首读、提交或恢复原会话 | [任务交接](#任务交接)。 |
| 暂停、反馈、改约或改字面规则 | [暂停与修改](#暂停与修改)、[字面规则](#字面规则)。 |
| 修改历史正文、分析范围、处理超界方案 | [修订影响分析](#修订影响分析)、[自动回改边界](#自动回改边界)。 |
| 章节目标、完本或文件交付 | [阶段结束与交付](#阶段结束与交付)。 |
| 使用外部模型进程 | [可选子进程适配器](#可选子进程适配器)；普通主干循环不需要读本节。 |

## 运行前提与初始化

ROOT/PROJECT 替换为绝对路径，项目产物不放技能目录。默认执行路径为主干循环调度子 agent；主干推进已授权目标，子 agent（Worker）只处理当前冻结任务。状态变化以真实命令返回和数据库提交为准。主干生命周期由宿主提供，本协议只约定业务推进与任务交接。

| 项目状态 | 开始方式 |
|---|---|
| 已有 PROJECT，续写或恢复 | 先 status，再 advance --compact；保留当前任务、候选和授权，不重新 init。 |
| 新 PROJECT | 按 [开书入口选择](opening.md#入口选择) 决定逐门开书、导入完整约定或 intake 部分要求。 |

已有项目的最短恢复命令：

```bash
python3 "$ROOT/scripts/novel.py" --project "$PROJECT" status
python3 "$ROOT/scripts/novel.py" --project "$PROJECT" advance --compact
```

开书交付按 outline_ready 的实际 coverage 说明，关闭卷纲时为 world_ready；不将设计完成视为正文授权。

## 目标与主控认领

直接导入完整约定的默认目标为试章；逐门流程按当前卷纲策略交付开书设计，不自动获得正文授权。作者已授权正文后，用 `run --through N --source 原话` 或 `run --complete --source 原话` 保存目标并取得 owner。后续主控治理命令带 `--owner 返回值`；`renew --owner 返回值` 续租。过期后重新 run 认领，沿用已经授权的实际目标，不扩大范围。

## 主干循环（默认执行路径）

主干执行治理命令，子 agent 负责读取材料、规划、执笔或审稿；workflow 决定下一任务，SQLite 保存实际状态。开书门任务（opening_options）例外：无独立性要求，主干在同一会话内自执（实测每门省一个冷子 agent 的 0.4M～1M input token 与 2～5 分钟等待，换组即同会话连续生成）；世界门及之后恢复派工。主干只保留授权目标、owner、当前 task_id 与宿主子 agent 会话的对应关系，以及简短执行状态。

| 交接点 | 主干动作 | 核实依据 |
|---|---|---|
| 取当前状态 | advance --compact，已有 owner 时继续携带。 | 当前 action，不预猜阶段或自行拼任务。 |
| task_ready | **开书门任务（opening_options）由主干自执**：读 task_path 的 task.json，`read --task` 取必读，一次成稿写 result.json 后 check/submit（session 填主干身份，门任务不绑定会话）。其余阶段按任务交接规则派新 Worker、恢复原会话或等待。 | 原执行者状态、claim、review_session；新任务用空历史会话，沿用当前模型设置。门任务对主控放行 read/recall（contracts.CONTROLLER_STAGES），正文与审读阶段不在此列。 |
| Worker 结束 | 接收身份和状态摘要，正文与完整回执留在项目。 | task_id、真实 session、accepted/checked、worker_boundary 或错误码及原因。 |
| 核实提交 | 无人值守用 `watch --owner ID`（默认一步：等当前任务提交后直接取下一派工）；需要显式核实时 advance --compact --after 该任务ID。 | wait_for_submit 表示未提交，resync 表示重取状态；不能仅凭 accepted_chapters 判断规划或核验任务是否完成。watch 的等待发生在引擎进程里，主干会话不为等待付费。 |
| 接续 | 按下面的动作表继续。 | 章节、窗口、Worker 和卷末均非授权目标停点，修订采纳、完本与交付也在循环内。 |

### 动作分支

下表的命令均使用同一 PROJECT，已有 owner 时继续携带；作者已有明确授权直接执行，仅缺失的作者决定才询问。

Windows 控制台乱码时的通用规则：引擎输出是 UTF-8，GBK 终端显示会乱；需要人读的长内容一律走引擎物化的文件（board.md、task.json、html），机器可读的短 JSON 才看控制台，或先 `$env:PYTHONUTF8=1`。

无人值守连写时，把"派 Worker → 等它提交 → 取下一派工"整段交给 `watch --owner ID --steps 1`：它派完当前任务后在引擎进程内等待提交（期间自动续租），任务完成即取下一 task_ready 并连同 task 一起返回；主干每次醒来只做一件事——按返回的 task 派 Worker，再运行一次 watch。遇到 await_author、await_choice、paused（含返修停摆与额度用尽）、revision_blocked、目标终点或 Worker 长时间未提交（idle）时 watch 停下并带回该动作，按上表处理。`--steps 0` 用于外部派工器长跑：每个被监督的派工会追加一行到 work/watch.jsonl。等待期间不产生任何主干推理，这是它替代"sleep + status 轮询"的全部意义。

| action | 主干下一步 |
|---|---|
| task_ready | 按任务路径派工；先核对仍在运行的子 agent、claim 与 review_session，具体见任务交接 |
| wait_for_submit | 等待或联系当前子 agent 完成提交；它已结束时核实错误并沿允许会话恢复当前任务，不派下一个任务 |
| resync | 放下过期的 after 回调，重新调用不带 --after 的 advance --compact，以当前任务为准 |
| revision_ready | 修订属于当前授权目标时执行 promote，再回到 advance --compact；作者明确要求先看候选再决定时，交付候选并等待该决定 |
| revision_blocked | 交付 proposal.plan_path 中的完整修复方案，说明请求范围、实际影响、动作数量和受保护的验收范围；保持原稿，等待作者对准确 plan_hash 的明确决定，不自动放宽范围 |
| ready_to_complete | 执行 complete；验收通过后执行 deliver，取得正文、阅读页和清单后才报告完本 |
| completed | 从完本快照执行 deliver 或恢复失败的交付；交付成功后结束 |
| target_reached | 刷新 html，按约定导出并交付实际完成的章节范围；不冒充全书完本 |
| world_ready / outline_ready | 交付返回的世界及实际卷纲 coverage；已有正文授权但尚未保存时，用 run 保存同一授权后继续，否则到本次开书目标结束 |
| await_choice | 返回携带 `board_card`（work/board.md，引擎渲染的作者卡片：门名/进度/各案 pitch·这一版·推进·代价风险·承接·画面/命名提示/固定操作）。把卡片内容原样交给作者，不在控制台直接读长 JSON（GBK 控制台会乱码）也不手工重排版；已有该板的明确选择则按卡内 id 与 hash 执行 choose 后继续，否则等待作者选择 |
| await_author | 已有对应 prose_hash 的明确认可则 approve 后继续，否则提供该版本首章并等待认可 |
| paused / repair_exhausted | 保留候选和失败记录，报告具体阻碍；不自动 resume 或重派任务来重置预算。**因额度、范围或未决问题停下时**（章级候选的同一条意见连续两轮返修未解决时也会以 repair-stalled 停下，额度未尽同样交作者），`resume` 不重置额度，而是把处理方式交成作者决定：设计候选与章级候选给"再返修一轮／接受候选并把意见记为未解决项／重开本阶段或改约"；修订运行中若范围复核在运行范围之外记下缺陷，给"接受本次修订并记为未解决项／先撤销本次修订再开一次范围更大的修订"。用 `answer` 记录选择后才继续；被接受的条目写进 `accepted_findings`，在 `status` 与完本篇审计里可见，**接受不等于通过** |
| preparing | 按初始化入口导入已有完整约定或完成开书准备；只对真实缺口等待作者，不空转调用 advance |

未登记的动作和命令错误按返回的 code/details 核实修正入口，不猜测成功或无条件重试。字段拒绝交回当前子 agent 修正；完整性失败、作者裁决和修复耗尽保留现场并报告。可恢复的执行失败先核实任务是否已提交、原执行者是否仍在运行，再决定等待或恢复；换执行者不增加文学返修额度。

## 任务交接

advance --compact 的 task 只含任务身份、阶段、task_path、identity_path、claim 和 review_session 等派工信息；完整 task.json 仍按原协议写入 task_path，作者选择板与非派工动作保持完整。主干把 task_path 交给子 agent，由它完整读取本任务。commands 为 argv 数组，按数组执行，不拼 shell 字符串。

每个任务目录另写 identity.json：该任务自己的身份副本（task_id、input_hash、阶段、chapter/scope、delivery_phase、requires_new_worker、review_session、入口与版本，以及 worker_env 里应注入的变量名）。它供 Worker 与主控核对身份、供失败信息说明该注入什么，**不授予任何权限**：read/recall/patch/first-read 仍只对宿主注入 NOVEL_TASK_ID 与 NOVEL_SESSION 的派工进程开放，且命令里的 --task 必须等于 NOVEL_TASK_ID；worker_env.NOVEL_SESSION 为空表示本次由新会话自行命名。身份凭据只存在于宿主环境，不进任务文件、也不由 Worker 写回。

新任务派真实新 Worker，填真实 session；委派只给角色、task_path、一句背景和简短提交状态要求。子 agent 直接完成当前任务并 submit，worker_boundary=finished 后结束，不自行 advance 或代行作者与主干命令。review_session 非空时 requires_new_worker=false，须沿原审稿会话继续；它不允许复用该会话处理另一个任务。需要执行认领时调用 `claim --task ID --session ID`，将返回 token 的裸字符串填入回执顶层 execution_claim，首读与提交均附带。

主干已派出的子 agent 仍在运行，或 claim.expired=false 时继续等待，不重派；claim=null 只表示没有执行认领，不证明没有运行中的子 agent。expired=true 表示提交前须重新认领，也不证明旧执行者已停止。已写好 result.json 但租约过期时，沿允许的会话重新 claim，只更新 execution_claim 后重提，保留审稿 data 和冻结首读。恢复任务先 status、再 advance --compact，以当前任务为准，不手改库。

### 路径与失效判定

commands/guides 由**当前安装**渲染（解释器取自身份进程，脚本取自身份文件），并用目录联接（junction/symlink）映射时两条路径实为同一份安装。派工前先确认命令里的解释器与脚本存在，再交给 Worker；**不要凭路径字面判断某条命令失效**——先文件系统核实。技能目录确实移动过时，回主控再执行一次 `advance` 刷新任务视图即可重建命令，不要手改命令、也不要在派工提示里让 Worker"忽略 task.json 的 commands/guides"（那会让 Worker 用错身份或漏读必读记录）。

### 首读与提交

| 阶段 | Worker 动作 | 结果 |
|---|---|---|
| 首读封印 | 完整读 prose_files，只记录正文体验；填写 first_read_path 并执行 commands.first_read。 | 首读冻结；按返回 task_path 读解锁信封，仍用原审稿会话。 |
| 正式任务 | 完整读 required 及任务所需来源，按 result.template.json 填 result.json。格式不确定先 check，缺资料按 read/recall 补读。 | 当前输入版本的回执，不复制旧 pass 或执笔自评。 |
| 提交 | 执行 commands.submit；认领过的任务附 token 裸字符串 execution_claim。 | worker_boundary=finished 后结束，主干再用 --after 核实；checked 只是试算，不代表已提交。 |

await_author 给准确 prose_hash；已获得该版本认可时由主干 `approve --prose-hash HASH --source 原话`，沿原目标继续。

范围审稿按 [叙事推进](narrative.md) 的分层覆盖执行：叶块完整读章，综合者读冻结子摘要、边界章并按疑点补读，不伪造全书首读或复制块 pass。

## 暂停与修改

| 需要 | 命令入口 | 边界 |
|---|---|---|
| 暂停 | pause --reason 原因 | 保留任务与候选；--cancel 取消但留档。恢复原首读用原会话，另派审稿者须取消并重新首读，不能冒用 session。 |
| 恢复 | resume | 不增加额度；耗尽时保留材料并报告，不重开任务清零。内容与篇幅共享两次返修、一次重设计，字段拒绝与预检回滚不计次。设计候选（世界、卷设计、逐章卷纲）返修额度用尽而核验仍有意见时，resume 会把处理方式交成一条作者决定：再返修一轮（只改被点名的记录）、接受候选并把这几条记为未解决项（写进 carry_findings，完本篇审计与全书视图可见，不是 pass）、或重开本阶段与改约；选项之外的新决定仍走改约，代价照写进 impact |
| 候选稿反馈 | feedback --text 原话 | 对当前候选安排修复；已验收正文改用 revise。 |
| 历史正文修改 | revise --from-chapter N --reason 原话 | 必须声明作用范围四选一：`--through M` / `--changes-file` / `--proposal-hash` / `--to-end`；不给范围时命令直接拒绝，并提示先跑 revision-impact 查看影响终点。影响分析、后缀处理和完整范围验收见 [修订影响分析](#修订影响分析)。 |
| 未写窗口重规划 | replan --from-chapter N --reason 原因 | 已有草稿或正式稿的计划不能直接删除。 |
| 字面规则修改 | lexical --file 规则.json --source 原话 | 逐版记录，执行及恢复见 [字面规则](#字面规则)。 |
| 回收不可达文档 | compact | 只删除任何活动记录都到不了的内容寻址文档并回收空间；不改故事与账本状态，重复执行无副作用。 |
| 完整约定修改 | recontract --file 完整候选.json --source 原话 | 取消旧任务留档，独立核验后重新规划写审；已有正文时在继承父稿的新分支**自第 1 章重写重审全书**（父分支保留，可 discard 恢复），代价随已写章数线性增长——先向作者说明再执行；开书导入的状态条件见 [入口选择](opening.md#入口选择)。 |
| 答复作者裁决 | answer --decision-id ID --option 选项 --source 原话 | 只回答 status 的 author_decision 里已展示的选项，记录问题、选择与原话后清除 author_block，按新前提重拟候选；选项之外的新决定走 recontract（代价见上行）或重新提案。 |

作者明确改约时，暂时停用旧回改指令及改案调度，先完成约定核验；原缺陷、根案例和已耗额度保留，撤销改约候选时恢复父稿原问题。不能借改约绕过修复额度或作者边界。改约是方向性决定而非答疑通道：已写 N 章的项目改约会在新分支重写重审 N 章，选项内可答的作者裁决用 answer 记录即可，不付这笔代价。

### 字面规则

项目默认禁词为“账本、入账、回执”，默认人名禁字为空；作者可按本书覆盖，不把个人命名偏好当引擎通用规范。以冻结任务 policy 的版本、来源、规则和实际执行 scope 为准，不在派工提示中另写一套规则。

lexical 将新版本追加到项目记录，旧版本保留；规则不属于作者约定，开书阶段也生效。修改会取消在途任务、作废旧视图，下次 advance 重新派工。约定激活、改约和 discard 均保留项目字面规则及其历史，撤销候选正文不撤销作者改规则的决定。字段及 literal_policy 拒绝见 [协议](protocol.md#冻结任务与资料读取)。

## 阶段结束与交付

target_reached 表示授权章节目标完成；ready_to_complete 仍须 complete 验收。export 可导出纯文本（`--format md`）或简化 HTML，html 生成包含设计、事实和正文的全书视图，两者返回绝对路径；导出不代替完本验收。

editorial/1 章审可能返回独立 alignment_plan/alignment_review，按同一主干循环交接派新 Worker，当前稿不重传、不复用旧通过。卷末 root 可在原授权内有界补写，或先分析历史修订，边界内原子开启候选，超界保存方案；最后一轮根问题失败与作者裁决均保持暂停。complete 之后执行 `deliver`，得到 book.md/book.html/delivery.json；交付失败重试该快照的 deliver，不重新写书。`usage` 查看实际记录字符，宿主 token 用独立 observe.py 导入观测，不从字符估算。

工作台新能力、旧 v3 项目的显式启用，以及 revision_review 重读转返修的流程见 [叙事工作台](workbench.md)。阅读变化不必立即重写后文；pass 后原文携带，fix 后局部修改或重写并完整独立章审。

## 修订影响分析

`revision-impact --from-chapter N --changes-file 变更.json` 只读取已提交计划、事件和哈希，不改项目、不返回正文。Worker 不能调用，首读封印期间也不开放。变更说明由作者要求或独立审稿结论形成：

```json
{"mode":"semantic","changes":[{"kind":"knowledge","key":"shen:source"}],"scenes":["c2:s1"]}
```

| 变更类型 | changes-file 的声明 | 后文处理原则 |
|---|---|---|
| expression | 不带 changes，只改表达。 | 保持事实投影不变，仍核对后文前态。 |
| reading | 非空 reading_changes，声明人物、关系、母题、声线或披露关联。 | 先独立重读；pass 保留原文，fix 后实际修改并完整章审。 |
| semantic | changes 列实际变更坐标，可附 reading_changes。 | 沿事实与场景依赖分析，不完整时保守扩大。 |

kind 使用事实投影坐标（如 facts/knowledge/resources/relations/placements/hooks/reader_knowledge/node）；scenes 可省略，提供时必须是修订起章的实际场景。expression/reading 事实投影变化时按 revision_carry 拒绝，保留 pending 与旧稿。阅读坐标、版本标记和 chapter_actions 四类动作统一见 [叙事工作台](workbench.md#分级修订)。

语义分析沿显式 reads 与 depends_on 传播，受影响章节的已核验事件继续扩大影响；连续修订区间内的中间章节也会重写，其输出和场景依赖同样继续传播。story_node 同时更新节点与所属线路状态，两者均计入影响。缺少完整依赖、没有明确变更坐标或事件无法解释时保守扩展；move/placement/travel 涉及持有链、站位或到达时间的派生影响，目前也保守扩展。`last` 为建议终点，rewrite_chapters 是连续初始修改区间（semantic 为重写，expression/reading 为局部修改）；区间后动作另看 chapter_actions。source_hash/sources 绑定分析的准确章节版本。语义上的依赖完整性仍由独立审稿判断，程序不从空数组证明故事没有联系。分析结果另给出 `coverage`
与 `expansion`：后者写明保守扩大的原因（`undeclared_dependencies` 或 `unexplained_events`）、起点、终点
与章数，并随 `status` 的 revision_run 暴露给主控与作者，因此扩大不再只体现在每章的 reason 里。

执行 `revise --from-chapter N --reason 原因 --changes-file 变更.json` 时会在创建候选分支的同一事务中重新分析，默认采用计算终点；显式 --through 不能小于该终点。扩大终点时，实际初始修改区间及 chapter_actions 同步扩大，新增修改章的事实输出与场景桥梁继续传播；分析命令的原建议不能冒充实际采用范围。不提供 changes-file 时保留手动修订入口，但必须显式选一边：`--through M` 收窄到受影响章，或 `--to-end` 确认改到当前末章——命令不会再把"改第 N 章"默认解释为"重写其后全部"。修改章仍须新执笔和完整独立章审，重读 pass 章保持原文；后缀重放及起章至候选末章的范围复核通过后才能 promote。任务材料 revision_impact 携带实际采用的分析，表达及阅读修订不得改变事实。无论是否启用叙事追踪、是否提供 changes-file，原样携带后文都核对显式输入与原版本前态，拒绝漏报变更造成的失配；已由独立改案改变计划的待携带章转入返修写审。

### 自动回改边界

普通章审只能修当前候选章。审稿指出历史缺陷时，新根审的 revise_range 声明 range 和 changes；程序从最早 target_chapter 开始，先计算事实与阅读影响，按 keep/review/local/rewrite 安排后续处理。请求区间不自动扩到审查范围末尾；表达或阅读修订保持事实投影，语义依赖未知时仍保守扩大，不能为缩小范围谎报 expression。

自动修订限于最近 planning_window 个已写章（默认 3 章），初始实际修改区间不得超过这一上限，也不得触及已关闭卷的验收范围。新关闭记录按当时的 first/last 保护，获准追加的新章不提前冻结；旧记录缺少范围时按该卷保守保护。超界时本次审稿正常保存，原分支、正文和章节返修额度保持；完整修复方案保存在 execution.revision_directive，根方案仍沿原案例及既有轮次留档。

advance 返回 revision_blocked 时，顶层 proposal 为摘要，并将完整方案写到 proposal.plan_path；status 对应字段是 revision_proposal，无阻断方案时为 null。status 只提供路径，不保证文件已经生成；文件缺失时由 advance --compact 重建。两处摘要字段相同：

| 字段 | 含义 |
|---|---|
| plan_hash / plan_path | 当前完整方案的身份及派生文件路径；plan_hash 不等于 prose_hash 或任务 input_hash |
| first / requested_through / required_through | 起章、原请求终点及依赖分析后实际需要的修改终点；重读后文另见动作 |
| action_counts | keep/review/local/rewrite 各动作的章数；review 不计作重写 |
| violations / policy | 超界原因及此次检查的窗口、上限和关闭范围；outside_recent_window 为起章过早，rewrite_limit 为修改区间过长，closed_volume 为触及关闭范围 |

主干据摘要说明范围与原因，交付完整方案路径；不把全量影响记录重复灌入对话。

已有 scope_findings 时，主干调用 revise 也经过同一分析和边界，不能用未带 changes-file 的命令默认为全书重写。作者主动提出的历史修订仍按明确请求执行；主干不得把审稿建议改称作者要求，也不得用改约、重新 run 或 resume 绕过边界。

审稿把问题标为 severity=author 时（见 [协议](protocol.md)），项目暂停、status 的 author_decision 与 book.html 都显示待作者裁决的问题和选项，author_block 保存同一问题；此时不派任何写作任务，也不消耗返修额度。主干把问题和选项原样交给作者，作者选定后按原话记录：

```bash
python3 "$ROOT/scripts/novel.py" --project "$PROJECT" --owner "$OWNER" answer \
  --decision-id 待决问题ID --option '作者选定的选项label' --source '作者答复的原话'
```

答复须是已展示选项之一，否则以 author_decision 拒绝：作者另有第三条路时那是新决定，走改约核验（blocked_resolution 回答准确问题）或重新提案。记录写入 author_decision_history（同一问题、所选选项与作者原话），答复同时进入作者原话（author_feedback），清除 author_block；暂停原因就是该问题时项目恢复 running，否则保持暂停待处理其他停点。**顺序要求**：先 `answer` 记录裁决，再 `advance`/`recontract`。裁决会推进项目版本，派工在裁决之前冻结的任务随即失效（stale_task，只能取消重派），先派工后答复等于白派一个 Worker。下一步按新前提重新起草候选：世界、全书或卷设计交 world_model/book_plan/volume_plan 返修，卷纲批次重交 volume_outline，改案丢弃旧候选重新 alignment_plan；改约定本身的问题仍走 recontract，其全书重写代价见[动作表](#动作分支)——主干转述问题时一并告知作者两条路径的代价差。没有作者答复时 resume 会以 author_decision 拒绝，不能用改约或重发绕过。

作者明确授权准确方案后，保存其原话并执行：

```bash
python3 "$ROOT/scripts/novel.py" --project "$PROJECT" --owner "$OWNER" revise \
  --from-chapter N --proposal-hash HASH --source '作者对该准确方案的明确授权原话' --reason '采纳修复方案'
```

HASH 取 advance 的 proposal.plan_hash 或 status 的 revision_proposal.plan_hash；起章、实际终点及变更内容必须匹配该方案。省略 --through 时采用方案实际终点，省略 --changes-file 时采用已保存变更；显式提供时须分别匹配 required_through 和完整方案中的 changes。程序重新核对章节来源、创作上下文及运行版本，字面规则变更等更新也会使旧方案失效；授权不增加章节或根问题的修复额度。没有这项明确授权时只交付方案，不自动启动超范围修订。

若 revision_proposal 错误明确提示来源已变化，先核对当前状态、已保存的审稿结论和原方案，不继续重试旧 HASH。仍有同一批跨章缺陷时，用原 first、requested_through 和 changes 再调用 revise，不带 --proposal-hash 或 --source，让程序在原边界内重新评估；仍超界则保存新方案，再用 advance --compact 生成文件，重新交付准确哈希供作者决定。若已落入允许范围，则进入候选修订。revision-impact 只读分析，不替换已保存的阻断方案；不得把旧授权自动套到新哈希。

## 可选子进程适配器

仅在宿主通过外部模型进程执行任务时使用；默认的主干与子 agent 循环直接沿上文交接，不需要启动这层适配器。

command.json 是已安装模型宿主的 argv 数组。`host-step --command-json 文件 --owner ID` 执行一步；`host-loop ... --limit N` 在当前进程持续监督，遇作者边界、失败、暂停或目标终点停止。宿主用子 agent（而非子进程）执行 Worker 时，等价能力是 `watch`：等待与续租在引擎侧，派工由宿主完成。

通过 NOVEL_TASK_PATH/NOVEL_PROJECT/NOVEL_TASK_ID/NOVEL_SESSION/NOVEL_EXECUTION_CLAIM 提供身份；CLI 只消费其中的 TASK_ID/SESSION/EXECUTION_CLAIM，PROJECT 与 TASK_PATH 是给 Worker 进程定位项目和回执的便利变量，命令行仍须显式给 --project。宿主负责实际模型新会话；新子进程不证明空模型历史。超时终止并等待自己的进程；返回 0 且任务实际 done 才继续。日志无法打开或进程无法启动时返回 host_launch_failed；认领后的各退出路径均释放任务占用，包括主控续租失败。

适配器另有 worker_finished、host_timeout、step_limit、host_launch_failed、resume_session_required、needs_attention；step_limit 是适配器步数上限，不表示作者目标完成。advance 返回动作仍按上表处理。

冻结过首读的遗留任务返回 resume_session_required；通用适配器不证明模型会话恢复能力。真实模型历史隔离和计费用量需另行验收。
