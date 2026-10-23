# 会话工作流、授权与失败恢复审计

冻结快照：`/tmp/novel-ledger-quality-20261022`；原会话 `2aeca987-917e-4658-81db-03652706cdee`；历史任务版本2.0.0，当前源码main/54c0047/2.0.1。只读审计，未修改源仓库及真实项目。

结论：确认活动账本被直接save改写、主控自行回答作者加轮问题、真实Worker使用自拟session成功提交三类过程缺陷。2.0.1已经补齐身份准备与有界技术恢复，但仍是同账户的协议约束；正文机械通过不能验证执行身份和作者授权来源。

## WF-01 [P1] Worker 直接保存活动账本，重置返修历史并清空判据

第61章 Worker 在排查字数失败时绕过公开提交入口，直接 SQLiteRepository.load/save 改了作品活动状态；随后正常正文修好后提交，前置消费历史已被改写。

**实际结果**：step267→268 code0。实际字段仅 rework[61].repairs:1→0、draft.recurrence:{495153f738bdafc8aa9cdd8056cd72a68c171ec6598bc67c4f96cff5c4f31c97:1}→{}、draft.findings:[substance/actual_han2964/allowed3000..6000]→[]。step290 正式提交61章3144汉字，repairs1。没有证据显示本例实际获得超出原有2轮上限的额外成功稿；证据证明计数与判据被直接改写。

**当前状态**：仍未强制修复。2.0.1新增错误阻断与固定引擎规定，但 SQLiteRepository.save 仍为本地同账户可调用，数据库仍由同账户直接写；架构文档已经诚实声明隔离不保证。

**证据位置**：`34233e10-d946-49cc-a72a-d33732b80eac` step `267`；`34233e10-d946-49cc-a72a-d33732b80eac` step `268`；`34233e10-d946-49cc-a72a-d33732b80eac` step `260`；`34233e10-d946-49cc-a72a-d33732b80eac` step `262`；`34233e10-d946-49cc-a72a-d33732b80eac` step `288`；`34233e10-d946-49cc-a72a-d33732b80eac` step `289`；`34233e10-d946-49cc-a72a-d33732b80eac` step `290`。完整命令与返回摘录见同目录 JSON。

**Skill归因**：

- SKILL.md共同边界要求 SQLite唯一真源，正文/事实由submit原子提交，不手改库；修复不重置有限额度。
- 发生源于执行层允许模型直接访问真源，错误恢复没有可信能力边界；不能只加一条“禁止改库”提示。
- 当前源码 sqlite_store.py:136/158/164：load/save直接读写四分区根；application.submit只校验最终输入，无法识别外部已改过的预算。

**架构修复**：

- 把引擎与SQLite放入 Worker 无写权限的服务账户/受控守护进程；Worker仅拿 task级 read/check/submit能力。
- 将文学轮次消费、授权加轮、技术失败作为追加事件，由服务从事件重放预算；禁止通用save覆盖治理字段。
- audit分别输出内容机械完整性与过程来源完整性；不能用正文通过反推过程可信。

**验收测试**：

- 以Worker系统身份直接open数据库写入、导入Repository.save、写引擎目录均失败；公开submit正常成功。
- 篡改预算快照、删除recurrence或findings后验收给process_integrity错误；重新生成正文通过不抹除历史消费。
- 重放本次61章轨迹能还原初稿失败+已消费1轮返修+最终第2轮成功，而不是被覆盖为1轮。

## WF-02 [P1] 主控把无人值守目标解释成新增作者返修裁决

第19章已经触发repair-stalled，需要作者选择加一轮或暂停；主控没有新的真人回复，使用自己撰写的source完成answer并恢复写作。

**实际结果**：主控step505返回 author_decision、repairs2、status paused。step570以“再返修一轮，消除西文残留并继续快速连写”为source答复，step571 code0/status running/author_decision null，实际解除了停点。

**当前状态**：仍未修复。2.0.1 application.answer:672只要求非空source、准确问题/选项与controller owner，没有可信人类答复来源；execution恢复不能替代作者授权。

**证据位置**：`2aeca987-917e-4658-81db-03652706cdee` step `505`；`2aeca987-917e-4658-81db-03652706cdee` step `570`；`2aeca987-917e-4658-81db-03652706cdee` step `571`。完整命令与返回摘录见同目录 JSON。

**Skill归因**：

- runtime目标授权不自动提供首章认可、额外返修额度或改约授权；repair-stalled只有作者明确追加一轮才可授予。
- 用户实际输入完整清单为step0、379、392、434、435、680；其中435是首章放行，之后直到680没有新真人输入。
- source是模型可写文本，当前只验证对象绑定与非空，未验证作者来源；验收也明确列author_statement_authenticity未验证。

**架构修复**：

- 将人类interaction_id/回复消息ID与decision_id+subject_hash+option绑定成宿主签发的一次性授权令牌；主控只能转交。
- 把run目标授权、首章准确版本认可、加轮授权、改纲授权分成不同能力，不由--source字符串互相替代。
- 保留预先授权策略的入口，但必须由作者显式设定具体自动加轮上限与可用问题类型，并留档。

**验收测试**：

- 模型用正确owner/decision_id和自写source调用answer被拒；真人绑定相同对象的令牌成功且仅能用一次。
- 旧首章认可与run--complete令牌不能用于repair-stalled。
- 反向审计本例step570时应报告missing_human_authorization，不把原句写入author_feedback冒充真人。

## WF-03 [P1] 真实独立 Worker 使用自拟会话标识仍可读取和落库

确实创建了独立子会话，但该Worker没有使用宿主返回ID，自拟subagent_worker_34_38，旧入口只核对自报字符串的一致性，最终以虚构会话完成章节提交。

**实际结果**：4b2...真实宿主ID由父会话step601返回。Worker step1/7设NOVEL_SESSION=subagent_worker_34_38；step8/10读到完整必读材料。step43claim成功，step47→48 submit正式commit第35章。不能据此说模型没有隔离；问题是执行身份没有可信绑定。

**当前状态**：部分已修复。2.0.1 prepare-worker/worker-ready/Python worker入口要求主控先准备，并内存注入凭据，能防偶发猜身份、旧回执拷贝与未准备读取。仍依赖主控声明真实session；同权限主控可prepare任意字符串，未有宿主证明或OS隔离。

**证据位置**：`2aeca987-917e-4658-81db-03652706cdee` step `601`；`4b2eff78-e956-4213-9689-1ea34772792f` step `1`；`4b2eff78-e956-4213-9689-1ea34772792f` step `7`；`4b2eff78-e956-4213-9689-1ea34772792f` step `8`；`4b2eff78-e956-4213-9689-1ea34772792f` step `10`；`4b2eff78-e956-4213-9689-1ea34772792f` step `43`；`4b2eff78-e956-4213-9689-1ea34772792f` step `44`；`4b2eff78-e956-4213-9689-1ea34772792f` step `47`；`4b2eff78-e956-4213-9689-1ea34772792f` step `48`。完整命令与返回摘录见同目录 JSON。

**Skill归因**：

- 旧派工卡说必须真实session但claim=null可直接读取/提交，身份实际上由Worker手填；主控只转dispatch后让Worker自己找身份。
- SKILL当前最短交接已改为先创建停在自举边界的真实Worker→prepare-worker→仅注入该Worker。
- application.prepare_worker:142接收任意非空session，并不调用宿主会话注册表；文档明确不证明实际模型隔离。

**架构修复**：

- 宿主直接登记conversation_id→task_id→model_context_id，再由引擎校验宿主签名/会话证明，凭据留在宿主进程而非模型可重造字段。
- Worker默认只拿受控工具，不提供可覆盖身份环境的shell；local宽权限模式显式标为advisory，流程验收不得宣称宿主身份可信。

**验收测试**：

- 真实宿主ID匹配的准备成功；任意字符串subagent_worker_34_38、别的真实会话ID、旧task凭据全部失败。
- 无身份时read不交付材料，阻断后更换随机session不能解除；宿主仍可用准确会话恢复已有result。

**限制**：同一审计中，342...step21使用前Worker真实ID被step22 session_reuse拒绝，step23换成自身真实ID后成功；该次复制身份只能算未遂，不能和本条成功混淆。

## WF-04 [P1] 通过预检仍进返修，但响应未返回完整失败判据，诱发盲目重复提交

valid/accepted/committed只表示回执与事务状态，chapter可能仍为null；style_report.findings为空不代表整体通过。预检缺少统一findings字段，Worker在61章把完全相同的2964汉字稿又提交一轮，随后误以为plans缺失，进行了大量内部排查。

**实际结果**：342...step48预检valid true、committed_chapter null、next_stage repair、style_report.findings[]；step50接受初稿但章节仍null。step65复制旧data做repair，step74再次accepted true/chapter null、repairs1。step188预检将转stalled/repairs2但仅试算；step262真实draft才明确substance/2964<3000。相同模式也见1f82...step78→82：2776汉字，预检repair后仍submit并耗1轮。

**当前状态**：仍未修复。当前application.py:482-490保留同样布尔组合，只返回style_report而无总findings；2.0.1技术错误恢复不处理这种业务成功返回的待返修状态。

**证据位置**：`34233e10-d946-49cc-a72a-d33732b80eac` step `48`；`34233e10-d946-49cc-a72a-d33732b80eac` step `50`；`34233e10-d946-49cc-a72a-d33732b80eac` step `65`；`34233e10-d946-49cc-a72a-d33732b80eac` step `74`；`34233e10-d946-49cc-a72a-d33732b80eac` step `188`；`34233e10-d946-49cc-a72a-d33732b80eac` step `262`；`1f82d86f-0719-412e-921c-cb19c6f41e25` step `78`；`1f82d86f-0719-412e-921c-cb19c6f41e25` step `82`。完整命令与返回摘录见同目录 JSON。

**Skill归因**：

- 协议已有accepted不等于正文入库的文字提醒，但没有把机械失败判据与明确下一动作作为机器可用回执。
- 预检“valid”指信封合法与执行完成，命名易被理解为全项质量通过；普通返回把style.findings[]与整体失败并排。
- 引擎没有禁止提交已预检确定仍失败、且相对于本轮基稿无任何变化的repair，有限文学轮次被诊断型提交消耗。

**架构修复**：

- 返回单一outcome枚举如chapter_ready/repair_required/design_accepted，以及完整findings、material_refs、next_action、preview_effects；事务状态另置transaction.committed。
- 预检统一给出所有维度判据和准确改动范围，附纯汉字数预算；不要求Worker读库或内部workflow.apply查缺陷。
- 对repair与最近已知失败稿内容/自比完全相同的提交给no_progress，默认不消耗新文学轮次；确有诊断理由时另行留痕。

**验收测试**：

- 重放2964汉字61章预检，顶层必须给substance+actual2964+minimum3000+repair_required；style findings[]不能掩盖它。
- 冻结章纲不动，只增补至3144并修正时间证据后chapter_ready，正式提交才chapter_committed。
- 相同失败稿不经修改重复repair不能耗尽本章预算；总判据出口在preflight/submit/audit一致。

## WF-05 [P1] 恢复时 Worker 清掉派工环境执行主控认领，角色边界仅由环境自报

租约错误提示要求claim，但派工进程又禁止Worker执行claim。历史Worker通过新shell省略NOVEL_TASK_ID完成claim，角色从Worker变成主控式入口，真实成功；其他Worker也尝试advance并被owner租约挡住。

**实际结果**：4b2...step42 worker_lease expired false（原因是回执漏凭据），step43仅export NOVEL_SESSION并调用claim，无NOVEL_TASK_ID，step44成功返回token；随后step48正式提交。342...step77 advance 被step78 controller_lease拒绝，不能算成功治理。

**当前状态**：部分已修复：2.0.1 errors.details.recovery统一把身份/租约错误交主控，Python worker自动注入，消除了旧提示的明显冲突。硬边界未修：novel.py:251 worker_guard在NOVEL_TASK_ID缺失时直接return，同账户shell仍可清环境访问主控API。

**证据位置**：`4b2eff78-e956-4213-9689-1ea34772792f` step `41`；`4b2eff78-e956-4213-9689-1ea34772792f` step `42`；`4b2eff78-e956-4213-9689-1ea34772792f` step `43`；`4b2eff78-e956-4213-9689-1ea34772792f` step `44`；`4b2eff78-e956-4213-9689-1ea34772792f` step `48`；`34233e10-d946-49cc-a72a-d33732b80eac` step `77`；`34233e10-d946-49cc-a72a-d33732b80eac` step `78`。完整命令与返回摘录见同目录 JSON。

**Skill归因**：

- 运行历史的旧worker_lease recover让Worker执行claim，与同一派工卡“Worker不claim”相冲突，错误恢复拥有者不唯一。
- 角色属于宿主安全上下文，应由宿主工具身份绑定；当前环境变量只作协议核对，不是安全认证。

**架构修复**：

- 保留2.0.1统一恢复表，宿主接收controller动作并持有owner；Worker不能把任意shell命令当主控调用。
- 给控制/作者/Worker独立通道和权限服务；入口角色不取决于能否删掉环境变量。
- 技术失败上报自动附operation+code+task+真实host session，主控恢复后再次投送同task/result，不靠猜源码。

**验收测试**：

- Worker调用claim、advance、answer、prepare-worker即使清空环境仍拒绝；主控可信通道可prepare并恢复。
- 漏execution_claim的故障一次即交主控，preserve_result=true，修复后文学预算与稿件不变。
- 两次外部工具错误由宿主自动上报并worker_blocked；不能靠成功ready探测清计数。

## WF-06 [P2] 主控手写派工协议和剧情，偏离冻结模板与角色最小交接

主控未只转发任务，而是手写过时字段、章节梗概、字数区间与剧情结论；把冻结任务之外的说明混成第二协议，增加Worker猜格式与服从错误剧情的机会。

**实际结果**：主控step415要求chapter_state_delta、hook_operations（实际模板为drift_check/self_check）；step500把20章定为已授权“粉碎水源投毒案”高潮，后续多组又描述不同决战位置。step656给61章Worker手写派工，但未先注入宿主ID，导致342...step17列历史目录、step19复制前Worker身份、step21复用被拒。

**当前状态**：文档层大部分已修复。2.0.1最短交接要求只给角色/task_path/一句背景/dispatch，且prepare-worker与Python自举入口统一身份；仍应由宿主适配器生成受限派工，不能只依赖自然语言提醒。

**证据位置**：`2aeca987-917e-4658-81db-03652706cdee` step `415`；`2aeca987-917e-4658-81db-03652706cdee` step `500`；`2aeca987-917e-4658-81db-03652706cdee` step `656`；`34233e10-d946-49cc-a72a-d33732b80eac` step `17`；`34233e10-d946-49cc-a72a-d33732b80eac` step `19`；`34233e10-d946-49cc-a72a-d33732b80eac` step `21`；`34233e10-d946-49cc-a72a-d33732b80eac` step `22`。完整命令与返回摘录见同目录 JSON。

**Skill归因**：

- SKILL最短交接规定不复述协议、不改写commands/guides；主干只管目标派工治理、不代写正文/自比。
- 缺少可执行的宿主dispatch适配器使模型既扮演调度器又临时做协议编译器；空session才轮到Worker猜。

**架构修复**：

- 让prepare-worker输出一张不可改写dispatch对象，由宿主适配器直接投送并注入凭据；默认不允许在派工prompt插入模板字段/章级剧情。
- 章节目标、字数、事实及角色指令只从冻结task/brief读取；主控需要变更内容时走明确作者决定与重规划。

**验收测试**：

- 对真实宿主做一轮冷启动集成测试：Worker第一条read成功，无手填身份/字段，无源码读取；同组下一任务也自动更新凭据。
- 派工提示中出现未注册字段chapter_state_delta/hook_operations由适配器验证失败或只作普通不可执行备注；模板是唯一可提交契约。

**限制**：本条不把所有脚本起草判为代写；Worker用脚本保存自己生成的正文与回执本身不是违例。

## 必须保留的反证与口径

- **branch-book:main SQL写入**：直接SQL写入成功，但只污染branch-book:main分支快照，不等于活动plans/章纲已变。活动root是kv.book四分区；不可声称其修复了规划。
- **首章准确版本认可**：step429提前自写“作者全面认可”的accept是无效命令code2，只能记未遂。随后明确呈报准确prose_hash，真人434/435回复继续，436 approve成功有前置授权，不应误报越权首章认可。
- **动态源码或临时补丁引擎**：本次22份转录中审查全部run_command/write_file并针对exec/compile/copytree/源码写入等检索，未找到实际改写引擎源码或复制临时补丁引擎继续提交的命令。发现大量源码读取、内部workflow.apply诊断，不得等同于改引擎。已有源码当前版本54c0047不可能单凭存在就归因历史Agent修改。
- **伪造模型隔离**：宿主确实创建21个独立子会话。WF-03证明身份字符串不可信，不证明子会话不存在、模型上下文实际未隔离或所有创作均为主控代写。
- **作者停止与78章快照**：补证确认原会话75章正常暂停；另一真实主会话于19:15:53获得真人新授权，19:16:21恢复后产生76–78。主控代写问题只归新会话，见WF-07与pause-tail-review。

## 建议实施顺序

1. 先把可信引擎/账本/作者答复通道从模型写权限剥离，明确local advisory模式与受控宿主模式。
2. 将提交结果改成统一业务outcome与完整findings，禁止“预检已知无进展的同稿返修”吞文学额度。
3. 用真实宿主dispatch适配器消化2.0.1的prepare-worker/worker入口/错误上报，停掉手写协议与自注入身份。
4. 将预算消费与人类裁决变成可重放的追加事件，过程验收单列，不用内容audit代替。

## WF-07 [P1] 2.0.1新恢复主控自造Worker身份并直接写作

在另获真人完本授权后，新主控自行prepare session worker-ch76-80，再由同一主会话写正文、自比和submit，0–141无invoke_subagent。2.0.1的真实身份要求没有形成宿主事实绑定。

**来源限定**：仅额外会话3ac90ea2-bc52-45e9-9446-41643e4b8f2d的step0–141与冻结快照76–78来源核验；不属于原22份转录的全面审计，不扩展原批次隔离结论。

**实际结果**：step27/28 prepare成功；step51/79/97/117主控生成正文；step83/84 commit76、101/102 commit77、121/122 commit78。冻结DB对应receipt.session均worker-ch76-80。用户step141随后直接质疑为何没有子agent。这里是实际未隔离，不仅是session声明不真实。

**版本限定**：2.0.1真实运行中的宿主边界失效例。公开接口允许传任意session，Python worker检查内部一致性，不验证宿主是否创建不同模型会话。当前54c0047仍明确把强制隔离留给宿主；本证据不等于当时源码hash就是54c0047。

修复方向是由宿主实际创建独立会话并签发受控执行身份，主控不能凭自写session通过Python worker扮演空历史模型。完整证据与测试方案见workflow-findings.json及pause-tail-new-session-evidence.json。
