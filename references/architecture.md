# 架构与工程目标

当前执行仅以本技能入口、[任务协议](protocol.md)、[运行流程](runtime.md) 及其专项指南为准。`validation/` 中的历史规格、实验和报告只保存当轮证据，不作为执行规范或兼容承诺。

何时读：修改引擎、扩展命令或判断能力边界。

工程目标：百万字长篇的开书、世界模型、分卷卷纲、逐章章纲、逐章执笔自比、机械核账、历史修订、断点恢复与最终交付。协议和代码为独立实现，不与其他小说工程互通数据库或命令行为。

## 适用范围与维护依据

本页规定工程依赖、数据所有权和提交不变量。作者的创作决定保存在约定与原话中，创作判断见 [创作与自比](craft.md)；不把架构选择转换为正文写法要求。

字段与校验以源码声明和任务模板为准，接口摘要见 [协议](protocol.md)；命令及恢复步骤见 [运行](runtime.md)；测试、度量和真实长篇验收口径见 [验证](validation.md)。本文的 Mermaid 块是架构图真源，docs 为派生产物，生成及核对方法见 [图表维护](../docs/README.md)。

| 工程问题 | 读取位置 |
|---|---|
| 模块依赖、端口替换与装配 | [依赖方向](#依赖方向) |
| 主干、Worker、作者与事实的职责 | [主干循环与子 agent](#主干循环与子-agent)、[数据所有权与角色](#数据所有权与角色) |
| 修改提交、分区、缓存或恢复 | [不变量](#不变量)、[数据与失败](#数据与失败) |
| 判断已有能力与尚未支持的行为 | [当前能力边界](#当前能力边界)、[叙事与材料边界](#叙事与材料边界) |

## 判据前移与可靠底座

作者约定提供作品方向；卷纲与章纲在设计期声明资源、位置、知情、时钟、人物、情节与伏笔增量，以及本卷/本章的文风要求，引擎用卷内状态链逐章模拟；执笔后由 `drift_check` 逐项自比、`drift_reconcile.reconcile` 机械核算（并产出 hook 事件），再由事实、叙事与空间的既有判据入账，同时用 `style` 记录数值观察并核验已声明的文风约束。理解记录与创作记忆仍按版本保存，实际事件才写入 canon。context 将方向、当前事实、相关理解、文风规格与原文编译为冻结任务，workflow 负责交接，SQLite 事务、不可变文档和章节分支作为可靠底座。

understanding 是 intent 内独立的版本对象，不把解释与未来方案混成事实；原文证据失效时撤下对应版本，未改后文携带后恢复其有效记录。稳定场景身份与阅读位置分离，故事时间和披露另行记录。revision_impact 给出事实重写范围与阅读影响动作；受影响章的章纲由 `chapter_outline` 重排；启用连续性保障时另有准确候选的独立读者协议，不直接改作品理解。协议与项目边界见 [叙事工作台](workbench.md)。

## 主干循环与子 agent

宿主主干管理作者目标、任务身份、治理命令与简短进度；子 agent（Worker）读取完整冻结材料，完成当前世界、卷纲、章纲、执笔或返修并提交。开书门任务（opening_options）例外：无正文、无派工必要性，由主干在同一会话自执（`contracts.CONTROLLER_STAGES`），选择板由引擎物化为 work/board.md。workflow 决定下一任务，主干只接收身份及状态摘要，正文与完整回执保留在项目中；无人值守的等待由 `watch` 在引擎进程内承担。主干生命周期和模型会话隔离由宿主提供，host 是可选的外部进程适配器。execution为advance/watch提供controller.must_continue，submit的continuation区分组内与跨组角色；identity_registered、activity_observed和未知的worker_running分别表达登记、观察及存活边界。

compact 是派工返回视图，冻结任务、正文和材料保持完整。任务身份与执行认领分别承担提交校验和并发占用；派工、等待、同会话恢复及提交核实统一见 [主干循环](runtime.md#主干循环默认执行路径) 与 [任务交接](runtime.md#任务交接)；修订采纳、完本和交付统一按 [动作分支](runtime.md#动作分支) 执行。

## 依赖方向

```mermaid
flowchart TD
    CLI[命令入口 novel.py] --> BOOT[组合根 bootstrap]
    BOOT --> APP[应用编排 application]
    BOOT --> CTX[冻结编译 context]
    BOOT --> VIEW[交付适配器 presentation]
    BOOT --> SQL[存储适配器 sqlite_store]
    BOOT --> HOST[进程适配器 host]
    BOOT --> WATCH[无人值守等待 unattended]
    BOOT --> DEL
    BOOT --> PAGE
    BOOT --> WF
    BOOT --> WS[输出路径 workspace]
    APP --> PORT[应用端口 ports]
    APP --> VERIFY[只读验收 verification]
    VERIFY --> PORT
    VERIFY --> DOMAIN
    VERIFY --> DRIFTR[执笔核算 drift_reconcile]
    APP --> GOV[治理与授权 governance]
    GOV --> PORT
    APP --> CONT[独立核验 continuity_service]
    CONT --> PORT
    CONT --> CRULE[原文与时序 continuity]
    CRULE --> C
    APP --> WRITE[连写编排 writing_service]
    WRITE --> PORT
    WRITE --> WF
    WRITE --> DOMAIN
    APP --> WF[纯流程 workflow]
    APP --> DOMAIN[纯领域规则]
    CTX --> PORT
    CTX --> DOMAIN
    CTX --> BRIEF[任务说明 briefs]
    BRIEF --> DOMAIN
    WF --> DOMAIN
    WF --> DRIFT[漂移核算 drift]
    DRIFT --> DOMAIN
    WF --> DRIFTS[状态链模拟 drift_simulation]
    WF --> DRIFTR
    DRIFTS --> DOMAIN
    DRIFTR --> DOMAIN
    VIEW --> PORT
    VIEW --> DEL[任务与导出 delivery]
    VIEW --> PAGE[全书页面 bookpage]
    VIEW --> WS
    DEL --> PORT
    DEL --> PUB[只读查询 publication]
    DEL --> TPL[模板 result_templates]
    DEL --> WS
    PAGE --> PORT
    PAGE --> PUB
    PAGE --> DOMAIN
    PAGE --> WS
    TPL --> DOMAIN
    PUB --> PORT
    PUB --> VERIFY
    SQL --> BS[四区归属 book_state]
    SQL --> C[基础契约 contracts]
    HOST --> PORT
    WATCH --> PORT
    PORT --> C
    BS --> C
    DOMAIN --> C
```

箭头表示主要源码依赖，方向从调用方指向依赖。`novel.py` 只依赖基础契约与组合根，`bootstrap` 的 LocalRuntime 统一打开/初始化账本并提供视图、导出、交付与宿主执行入口。`bootstrap` 装配 SQLite、冻结编译器、文件交付、时钟与 ID 生成器；`Application` 只接收 `ports` 中声明的能力，通过注入的接口完成持久化、任务编译与交付。核心不发现项目目录、数据库文件、标准输入或宿主进程。`host` 只调用公开用例与任务状态查询。`TaskDelivery` 可选携带 `process: FileTaskTransport`，其中声明实际项目、任务和日志路径；子进程宿主在 claim 前验证该文件传输能力，非文件交付按 `host_transport` 拒绝且不会留下执行租约。

层级独立以可替换性为标准：存储、冻结编译、交付、时间和身份提供方可各自替换，核心规则与用例无需修改。`context` 依赖最小 `ContextStore`，交付与全书视图依赖只读 `PublicationReader`，完本交付也只生成文件与清单；组合根将清单交给应用的 `record_delivery` 核对当前完本快照并事务留档；查询辅助、实体注册和证据校验有独立纯模块，避免从较高层借用私有方法。模板生成由 `result_templates` 负责，机械判据由 `drift` 家族（`drift`/`drift_simulation`/`drift_validation`/`drift_reconcile`）与 `lint`/`ledger` 等纯模块执行。

图中应用编排包含 `application`、`revision_service`、`contract_activation` 与 `opening_service`；独立的 `verification` 服务只接收 `VerificationSources`（read_document 与 headers 两个能力），不持有可写 Repository。Application 保留公开用例、授权检查与事务入口；修订服务负责影响分析、分支建立、后缀处理与理解恢复，事实重放统一委托 verification；约定激活服务负责已采纳约定切换。两者在调用方事务内使用 Repository 端口；修订服务只额外接收明确的任务取消能力，不依赖 Application 或自行提交事务。

图中“纯领域规则”汇总规则模块，略去逐域边以保持可读；`drift` 家族单列，因为判据前移的主入口在族内（共享词汇在 `drift`，模拟、校验与核算是三个相位模块），workflow 与 verification 直接调用其中的模拟与核算。完整依赖白名单、所有作用域的导入、核心 I/O 禁令和无环约束由 `tests/test_architecture.py` 强制。替换验证须通过实际用例观察结果：内存账本跑通生命周期、只读账本生成交付、替代宿主与运行工厂执行公开入口，真实组合根另验收事务与文件效果衔接。具体回归入口按 [改动类型选择验证](validation.md#按改动类型选择验证)，完整边集由 `validation/measure.py` 测量。

架构图以 Mermaid 块形式存放在本文件（真源），快照存于 [docs/architecture.mmd](../docs/architecture.mmd) 与 README，三处逐字一致；**仓库不保存渲染件**，需要图片时从快照现场导出。图表与字段的说明各自引用对应真源，不在派生文件或其他文档中另立一套结构要求。

| 文件 | 权威职责 |
|---|---|
| governance / authority | 治理检查点、模式与一次性授权消费；签名验证适配器只接收受控宿主注入，不从项目读取密钥；不是OS隔离 |
| continuity / continuity_service | 明确区间及原文证据纯规则；候选保存、独立首读冻结、后比较、歧义裁决与准确版本采纳，报告不直接改事实 |
| runtime_install | 完整固定运行副本、Git归档选择、文件清单核验与只读文件模式；独立于小说库，不改变开发检出；用于隔离正常开发更新，不声称OS隔离 |
| execution | 纯值的主控接续指令与执行活动观察；不从租约推断进程存活 |
| build_info | 安装包代码与执行规则指纹；不包含历史validation产物，新冻结任务绑定此构建 |
| contracts | 协议标识、约定字段表与当前开书对齐字段、结构门档位表与档位管线形状表（PIPELINE_SHAPES）、共享数值默认（`DEFAULTS`，含 `world_ladder` 的位阶/阶梯条数下限与主题锚点上限）、修复上限、作者停点与通道表、错误形状；约定形状与阶段权限的唯一权威 |
| catalog | 开书内容目录：类型库、创意透镜、卷型转折、开书方向与门序、雷同戒律与档位板文案；纯数据无依赖，creation/briefs/delivery/bookpage 读取渲染选择板与简报 |
| ports | 持久化、只读查询、冻结编译、交付与宿主用例的能力契约；只依赖 contracts，不持有具体资源 |
| creation | 零输入方案、逐门选择、换组回退、闭合选择与来源；只有当前门序（creation/6，13 门先定世界与格局），更早协议读取即拒；结构门的档位板由引擎按档位表即时给出；对齐字段由字段表派生 |
| world | 世界记录（支持 12 个领域，按档位要求填写）、关联、选择一致性，以及已声明的位阶、资源、格局与世界架构逐字绑定；保持设计与事实分离 |
| planning | 作者约定、卷纲与章纲的落库校验、`new_entities` 与场景形状 |
| drift | 判据共享词汇：卷纲/章纲字段表、世界与投影助手、章纲增量提取、设计/执笔共用的状态归约 `_reduce` 与 `plan_rows`（把章纲冻结成执笔回执必须回答的条目）；briefs/result_templates 直接读它的字段表 |
| drift_simulation | 卷内状态链模拟（`simulate`，含伏笔 `plant`/`payoff` 状态机）、卷末闭合与设计/执笔两相位共用的事件构造；依赖 drift |
| drift_validation | 卷纲/章纲机械校验：字段形状、v5 卷 `stage` 逐字取阶梯一级且只升不降、篇幅策略、enter/exit 与规范化章形状；依赖 drift 与 drift_simulation |
| drift_reconcile | 执笔漂移核算（`reconcile`，产出 hook 事件）与 `state_mismatch` 章行比对；依赖 drift 与 drift_simulation |
| style | 文风代理指标的纯核心：`metrics`（句长/段长/对白占比/本章重复度/视角标记）、`baseline`（首章锚点）与 `examine`（按 `style_guard/style_window` 分开观察与 findings，`compare` 只取 findings）；零派工，只依赖 contracts |
| narrative | 线路、节点、知情、人物当前状态与动态篇幅的纯规则 |
| entities / evidence / design_queries | 实体注册、原文证据与设计节点查询的纯共享规则，领域模块直接复用 |
| craft | 场景与对白意图校验、出场人物选择、版本补丁定位与合成；只依赖 contracts |
| spatial | 稳定锚点、路径与视听连接、持有链和到达下限；只依赖 contracts |
| editorial | 编辑能力开关、有效约定、创作上下文哈希及自动回改策略与越界判定；只依赖 contracts |
| facts | 原文定位、事件前值、资源、时钟、站位与历史断言的纯结算 |
| workflow | 下一任务和状态转换，内容与篇幅共享修复额度；窄返修守卫、返修复发计数与 repair-stalled 停止点；按 PIPELINE_SHAPES 安装档位流程形状（当前只有 `merge_chapter_outline`：t0/t1 把本卷卷纲与章纲合成一次派工，两个契约各自校验同一份回执） |
| briefs / result_templates | 按阶段生成任务说明与交付模板；不承担回执核验 |
| context | 面向 ContextStore 编译冻结来源、必读选择和按需资料，不依赖 workflow |
| publication | 面向 PublicationReader 的只读交付快照查询；完本来源先经 verification 复验，再提供给页面和导出 |
| verification | 只读来源验收：推进前与保存前校验聚合状态及链头，完整事件重放、正文机械复验、必需线路与首章认可闭合；不信任 completed 或缓存 audit，不承担修改、派工和文学裁决 |
| application | 公开用例、作者与运行授权、准确方案授权和单一事务入口；组合领域及专项应用服务，不解析输入文件或生成交付文件 |
| writing_service | 五章组的执行范围、会话绑定、逐章接续、材料哈希复用与停止；只创建当前一章的冻结任务，不修改章纲，不代行作者和主控决定 |
| revision_service / contract_activation | 同事务内的历史修订、后缀重放、理解恢复及已采纳约定激活；依赖端口与纯规则，不反向调用应用用例 |
| opening_service | 逐门开书的门内决策机制（choice/intake/regroup/back 的状态变更、冻结与留痕）；在调用方事务内工作，主控租约与加载/保存留在应用层 |
| sqlite_store | 持久化、唯一 pending、幂等回执、不可变材料及分支；逐章历史来源与增量目录缓存；未达文档回收 |
| presentation | 实现交付端口，组合任务目录、修复方案、世界及全书视图 |
| workspace | 输出位置与受保护资源别名判定；保护路径由存储适配器经组合根注入 |
| delivery | 任务目录物化、表单保留与回收、正文和世界导出、选择板卡片（work/board.md）、提问载荷（work/question.json）、Worker 自举卡（dispatch.md）、简报全文（brief.md）与 advance 完整视图快照（work/last-advance.json）渲染 |
| bookpage | 固定大小的 book.html 入口、按栏目/章渲染的转义片段与显式离线全书导出；templates/ 保存 HTML/CSS/JS |
| preview | 本机 HTTP 只读适配器，仅监听 127.0.0.1；每个请求打开独立只读 SQLite 连接和一致读快照，按栏目或章节返回片段，目录分页，不公开数据库文件或写入接口 |
| host | 面向 HostApplication 的外部进程执行、超时终止和实际提交核实，不访问应用内部 Repository |
| unattended | 面向 WatchApplication 的无人值守等待循环：派工后由引擎进程等待外部提交并续租，仅在下一派工、作者决定、暂停、终点或 idle 时返回；本地组合根附写 work/watch.jsonl 派工日志 |
| lint | 正文机械判据（跨章逐字重复、对白引号体例、西文残留），在提交与 preflight 同套执行；只依赖 contracts |
| ledger | 可选结构化账目行的形状与四则关系验算、跨工件同键同值；只依赖 contracts |
| book_state | 项目分区的字段所有权与事务内组装；只依赖 contracts |
| story_memory | 不绑定章号的场景身份、事实/阅读关联及带来源的场景材料；只依赖 contracts |
| revision_impact | 根据已提交章纲、事件与版本指纹保守传播事实和阅读影响；只依赖 contracts/story_memory |
| understanding | 可修订解释、原文与反证、版本选择、适用范围及随正文版本失效/恢复；只依赖 contracts |
| bootstrap | 唯一的本地组合根，将具体存储、查询、交付、时钟和 ID 提供方接到应用端口 |
| novel.py | 参数、文件/标准输入解析、访问分级与 Worker 边界；只依赖 contracts 与 bootstrap，经可替换运行工厂调用公开能力 |

## 数据所有权与角色

### 作者决定与开书结构

- 约定形状只有一处定义：contracts.CONTRACT_FIELDS（字段、类型、占位、可选性、是否参与对齐）。交付模板（result_templates.template → contracts.contract_skeleton）、结构校验（planning.validate_contract → contracts.contract_errors）和对齐核验（creation.validate_contract）全部由它派生；新增约定字段只改这张表，对齐表与字段表不一致时报 alignment_schema。对齐字段由 contracts.CONTRACT_ALIGNMENT 派生，只使用当前门序与字段归属；自备约定可省略非必填的开书决定。
- 逐门开书中，直接选择字段的唯一来源也声明在 CONTRACT_FIELDS.opening：`(门 ID, value 字段)`，主角整份选择通过字段的 shape 声明；`None` 表示该门的 value 整份投影到约定字段（来历门即 `opening: ('origin', None)` → `protagonist_origin`，shape 为 `family/arrival/cost`）。creation 从同一声明派生各门允许的输入字段和约定对齐值；世界与体量的推导输入单列在 creation.DERIVATION_INPUTS。方案提交、intake 和闭合选择的约定核验均拒绝跨门及未知字段，错误带 allowed_fields/unknown_fields。对齐值逐字段读取，禁止整份 value 合并覆盖其他门的决定。
- 开书协议只有当前版本：creation 状态声明 `novel-ledger.creation/6`（`opening/6`，13 门先定世界与格局），更早的 creation/N 在读取时被明确拒绝（以当前协议重开），方案篇幅上界是无条件的唯一规则。存储 schema 为 novel-ledger/5，已删除任务首读列；v4 及更早库明确拒绝，不提供隐式迁移。
- 作者可见的方案板有两类来源：创意门的板子由主干自执（未内联时派新空历史 Worker）生成；结构门（体量与分卷）的档位板由引擎按 contracts.SCALE_TIERS 当次给出，不派工、不等待，Worker 回执按 opening_system 拒绝。引擎只给经证明写得完的档位，选择仍由作者做出，程序不替作者决定。
- 体量窗口只决定展示哪些档位；相邻档位与最大档由完整 SCALE_TIERS 决定。同一档位在不同窗口的说明与数值一致，窗口最后一项不因此成为最大档。

### 派工文件与角色

- `work/<task>/` 里两类文件分属不同作者：task.json、input.json、identity.json、dispatch.md（Worker 自举卡）、brief.md（简报全文） 由主控生成且可重建；result.template.json（表单）与 result.json（回执）由 Worker 写。主控只在表单缺失或属于其他任务时才生成它，重跑 advance 绝不覆盖 Worker 已填内容；取消任务是唯一回收表单的事件。重派未提交任务时，引擎把上次遗留的 result.json 草稿隔离为 `result.stale.json` 并在派工卡注明——账本才是回执的记录源。
- 角色由身份而非称呼区分：opening_options 属 `contracts.CONTROLLER_STAGES`，主干可读取该门的 read/recall 材料；其他阶段只对携带 NOVEL_TASK_ID 的派工身份开放，主控代读按 role_boundary 拒绝；audit/export/html 是验收与交付命令，主控可用。身份本身随派工一起留档（identity.json：task_id、input_hash、阶段、worker_env），供核对与解释失败，但权限只看宿主注入的凭据——可核对的数据不是许可证，也不由 Worker 写回。

### 执行交接与恢复所有权

`contracts.EXECUTION` 与统一恢复表声明执行协议及错误处理者；Application 的 prepare_worker/worker_ready/worker_failure 负责认领、就绪验证和技术失败状态，纯创作 workflow 不接管宿主身份。技术计数以 store_keys 声明的任务键保存，不修改作品分区、章节、返修额度或冻结输入。连续失败阻断后，任务仍 pending，status/advance/watch 给出可恢复的 worker_blocked，只有主控显式准备并重置可恢复。

CLI 的 Python worker 入口只执行 Worker 公开命令，先验证会话与认领，在内存中注入回执身份；不生成身份、不从任务文件取私有 token。交付层根据同一状态生成 execution、ready/commands 与跨平台卡片；prepare-worker 重建视图时保留 Worker 草稿。入口捕获到的技术错误可自动计数；宿主自己的任意工具失败须经 report_error 上报。旧直接接口兼容不构成安全沙箱，真实模型身份、工具限制与上下文隔离仍由宿主提供。

### 字面策略与材料选择

- 字面约定是项目级版本记录（book.lexical_policy），不属于约定快照；默认值在开书阶段即生效，作者改规则用 lexical 命令留档，改规则取消在途任务并作废其视图。约定里出现 lexical_policy 属于未知字段，直接拒绝。
- 字面约定的**执行范围**只声明一处：contracts.ENFORCEMENT 按阶段列出被检查的字段（terms 查禁词、names 查禁字），检查循环（planning.enforce）与交给任务的 `policy.scope` 都由它生成。因此派工说明不可能承诺程序不做的检查；新增阶段或字段只改这张表。
- 派工材料按"这一任务需要什么"投递，而不是按"这一阶段有什么"：`brief` 由 `briefs.py` 现生成（本门规则 + 本轮方法（简报里的"创意透镜"）+ 交付契约），整篇 guides 只作可选参考；必读记录只留本阶段真正要用的（开书方案必读完整已选记录与拒绝记录）；记录哈希只在 task.json 出现一次，不复制到视图。取舍标准是"作者为这次派工付出的上下文"，不是文档是否完整。因果邻域按同一口径收窄：追踪项目只读目标与其直接前置，基础项目在固定深度与节点上限内做有界遍历，因此派工材料不随因果链长度增长，也不在长链上耗尽解释器栈。
- 改约与导入的约定激活记录 producer（主控 owner）与来源原话；promote 与 complete 的验收会复查作者决定记录，防止绕过作者边界。

## 不变量

- 快速模式是可选执行策略：每组最多五章，同组共享会话，跨组继续隔离；逐章冻结、自比、核账和原子提交，额度按章不变。worker-next 仅能从本人已提交的当前任务推进组内下一步，不能执行规划、改纲、首章认可或超出授权目标。组进度与章节提交同事务，重试不重复入库。writing_mode 属 execution，writing_batch 为声明的执行元数据；常规新任务仍禁止会话复用。

- 所有 import（含函数内、相对与绝对包内 import）满足逐模块依赖白名单并构成无环图。纯规则不依赖应用端口、SQLite、文件、模型宿主、应用层或可变全局缓存；应用只依赖纯规则与端口。核心禁止 I/O 导入、内建 open、动态导入、eval/exec 和 Path 访问。
- **跨层共享的数值默认只有一处声明**：`contracts.DEFAULTS`（卷纲/章纲策略、`style_window` 与文风门槛、返修额度），经 `contracts.policy_default(key)` 取副本使用；契约字段默认值、`drift`/`style` 的校验、`context`/`workflow` 的兜底与测试夹具都读它，`tests/test_architecture.py::test_shared_numeric_defaults_are_declared_once` 防止重新硬编码。**分层边界仍由 `tests/architecture_table.py` 的依赖白名单管**，`DEFAULTS` 只管“同一个值只能有一个来源”，两者不是一回事。
- 应用进入状态变更前及保存前通过 verification 校验当前投影属于已提交链头（零章时属于约定初态）、累计字数和链头与约定绑定。冻结材料的只读补读仍可用于诊断损坏，不借此放行新派工或提交。
- 任务输入与来源按哈希冻结；预检运行同一提交逻辑并回滚。同一任务已提交的相同结果幂等，不同结果拒绝。
- 领域判断、章节证据、事件结算、任务完成和状态转换全部成功才 commit；一个阶段只由一个事务入口提交。取消只更新持久状态并返回任务 ID，文件回收通过 after_commit 在提交后执行；预检与异常回滚丢弃回调。回调失败会报告交付失败，已提交的数据仍然保留。
- 章节只能在章纲存在且固定、漂移核算通过（items 覆盖完整、`actual.from` 等于引擎投影）、字数区间、`lint`、字面规则与机械事件核验通过后入库；文风 findings 与 `lint` 命中按名进入有界返修，默认首章形状与代词 observations 不消耗返修额度。章纲本身必须先通过卷内状态链模拟（含 enter/exit 一致性、伏笔 `plant`/`payoff` 状态机与卷末闭合）。
- 作品理解不直接结算事件、替代作者约定或强制修稿；理解记录按其冻结版本读取，作品理解仍由执笔回执提交增量（`understanding.update`）；独立连续性报告不直接变成事实或理解。
- 除主干自执 opening_options 的 read/recall 外，材料读取只对携带派工身份的进程开放，主控不得代读正文；未派工的任务不生成正式材料。
- 程序核对宿主声明的会话身份，不证明宿主实际提供了空模型历史。身份卡只沿用宿主注入或认领中已有的执行标识，不生成“自命名”身份；子进程适配器明确返回 context_isolation=unverified。
- 每章内容与篇幅消耗同一个有限预算；预检、非法字段、暂停、换 Worker、修订或改约不能增加额度。
- 返修作者问题绑定候选正文、约定、章号、项目版本、问题与额度快照；准确 id 才可答复。改约不清空未回答的问题和额度，追加机会作用于该问题的章节，不能借当前 draft 的不同章号改变授权对象。
- 未来设计、人物小传和章纲不直接产生事实。过去断言不重结算当前资源与时间。
- 候选修订保留旧正式稿；事实与阅读依赖先共同确定完整连续修改区间，区间内按重排后的章纲重写并重新过全部机械判据，窄范围修订（--through）终点外的后缀按动作先重放或原样携带并对新状态重结算（事实受影响即拒绝）。显式扩大终点时更新实际动作及传播；discard 恢复父版本及原目标。
- 历史修订由作者明确请求发起，在创建分支前分析实际影响；超界方案原子保存到 execution.revision_directive，保持原稿与章节额度，主干只获得摘要和完整方案路径。扩大执行须绑定当前 plan_hash、作者原话、准确范围及未变化的章节与创作来源；恢复和换会话不放宽边界。
- 完本必须覆盖末章、每章篇幅区间、准确版本的作者首章决定和全部关闭条件（required 节点与线路），不自动降低目标。completed 重复调用仍复验冻结来源；publication 在任何正式导出写盘前重新验收完整快照，不用原有 audit.ok 代替判定。快照中的章节行是交付重试真源，可恢复被改坏的可变视图，但这些行的事件、正文、链、状态及闭合条件必须重新通过当前规则。

## 数据与失败

### 项目分区与事务快照

settings、canon、intent、execution 是同一作品事务聚合的四个持久化归属区。它们共享一个根快照、事务和版本一致性，不提供各自独立部署或独立提交的服务边界。层级解耦由能力端口和适配器替换实现；四区划分负责数据归属，两者各有职责。

documents 按完整逻辑值寻址；小文档直接保存 JSON，大容器通过专用编码引用 document_blocks 中的不可变共享块。列表按固定大小叶与分层清单保存，字典按键的哈希稳定分桶，嵌套累计集合也独立共享；追加版本不复制整份历史，也不依赖越来越长的增量链。`document` 仍返回完整逻辑值的哈希，`read_document` 重建完整普通值并核对块与逻辑值哈希；调用方不接触物理编码，不能把块清单大小当必读材料量。普通 JSON 值即使长得像清单也保留原意。存储协议为 novel-ledger/5，旧协议在打开时拒绝且原文件不变，不隐式迁移。

chapters 引用正文、事件、章纲与核算结果，chain 连接前章及约定版本。kv.book 是 novel-ledger.book/1 根目录，仅保存 settings/canon/intent/execution 四个逻辑内容哈希；字段所有权由 book_state.PART_FIELDS 声明，未知或跨区字段拒绝。settings 保存作者约定与字面策略，canon 保存已核验投影与累计字数，intent 保存世界、卷纲、章纲及独立 understanding 作品理解，execution 保存任务推进、候选、预算与核验，以及阻断的 revision_directive 修复方案；work/revision-HASH.json 仅为其可重建副本。正文版本由 chapters/documents 独立管理。未来计划内容只归属 intent，正式提交同时更新 execution 中的运行版本与最后任务；未变分区复用原逻辑哈希。分区文档、共享块、根引用和任务提交在同一事务中更新，预检一并回滚。

领域与流程接收事务内的普通值，跨区决策可以读取完整作品视图，领域不接收 Repository 或文件路径。load 从同一根快照组装，不能逐区读取不同版本拼成混合状态；load_part 可只读一个分区。分区拆分不意味着每次领域决策已是常数成本，也不改变显式分支/完本快照保存完整交付状态的行为。tasks 保存冻结输入与回执；journal 保存操作轨迹。普通读取不隐式升级 schema。

### 历史来源与派生缓存

历史来源采用不可变逐章页：页保存正文/事件哈希、章号、摘要、章节链与前页哈希；任务冻结 history_source 的入口、截至章号和链指纹。适配器在 kv 保存每个分支的可重建目录头，首次为既有章节建页，此后只追加新章；相同历史在不同角色派工间复用，修订分支共享未改前缀。缓存头只服务派工构建，补读沿任务冻结页读取，不用当前分支查询结果替换任务来源，也不将缓存当事实真源。页与头使用现有 documents/kv，不增加表或隐式升级数据库。

历史查询默认从近到远按所需页读取事件，收齐请求的匹配章节再查一章匹配以决定分页；页数有界的常见查询不解析整本事件。稀疏/无命中查询仍可遍历全部历史，任意指定章也可能遍历目录，不宣称最坏查询复杂度不随篇幅增长。实测无命中查询在 20/100/500 章为 13.9/46.3/209.6 ms（逐页扫描，返回字符不随篇幅变化），线性但尚不构成瓶颈，因此不设默认预算：事实查询以查全优先，省时不能换成漏查。历史补读只使用当前 history_source 逐章来源，不提供旧全量索引名称入口。目录优化不改变 complete_state、章节重放或携带核对的覆盖要求，也不证明整个派工流程为常数成本。

`compact`（适配器 `prune`）从根引用、章节行、任务与日志出发，遍历逻辑文档与共享块的引用，只删除不可达内容并回收空间，不改写活动状态。旧冻结来源及其全部间接块仍保留，先核对所有可达完整逻辑哈希与块哈希，再删除；损坏或缺失的共享来源必须先报告。扫描与删除共用写事务，防止其他连接在扫描后新增引用被误删，删除中途失败完整回滚，提交后再回收空间。独立 document/save/history_snapshot 调用也原子发布来源与入口，有外层事务时复用，不能提前提交预检。回收是显式主控操作，不是自动后台清理。

结构共享减少重复持久化；完整逻辑哈希、重建与领域视图仍需处理当前完整值，不能据磁盘收益宣称每次提交或读取都是常数成本。显式回收还要完整校验全部留存版本，其读取量按累计逻辑来源计，不能每章调用并期望常数开销。四分区的逻辑根格式不变，物理分块只归存储适配器。正常恢复仍沿当前任务继续，不为重开重放全书。

`compact` 的回收边界是**明示的**，不是"库不会长大"：它只管内容寻址的 documents 及其共享块。另有两处按任务累积、当前**不回收**：
每终结一个任务都会在 `tasks` 表留下冻结输入与完整回执（`finish_task` 只写不删，全库没有 `DELETE FROM tasks`），
`work/<task>/` 目录同样保留 task.json、input.json、result.json、identity.json 与可选日志。
量级按每章 4～6 个任务、单任务约 15 KB（表内）与约 25 KB（目录内）估算，即每章数十 KB 量级；
`usage` 报出的 `tasks` 计数就是表内累积的直接读数。之所以不自动删除：任务行是"谁在什么版本下核验了什么"的审计轨迹，
工作目录里的回执是 Worker 亲自写下的原文，回收它们会把可复盘性换成磁盘。
把它变成可回收项需要先定义保留窗口与"已提交回执可以从表内重建工作目录"的保证，
这属于独立变更（同上面的写入成本），不放在默认路径里。

### 失败与恢复边界

输入拒绝带 Error(code/message/details)，事务回滚；源哈希或重放不一致为完整性失败。视图写盘或提交后文件回收失败直接报告，数据库提交保持有效，派生文件可重建。宿主启动失败、超时、未提交和会话恢复均保留明确状态，具体处理见 [运行与恢复](runtime.md#动作分支)。

revision_blocked 表示超界方案已经原子保存，正式稿和章节额度保持。准确授权绑定数据库中的当前方案及来源，派生方案文件只作交付副本。摘要字段、文件重建和过期授权的处理见 [自动回改边界](runtime.md#自动回改边界)。

### 验收信任与部署边界

verification 是程序能力边界，不是操作系统安全沙箱。所有正式完本与导出路径共享只读判据，修订服务不再提供另一套事实重放实现；机械报告明确 verification_scope=mechanical，并列出未验证的模型上下文隔离、作者原话真实性和文学质量。数字归一后的长段模板复用由 lint 与逐字重复检查共同覆盖，预检、提交和最终复验使用同一判据。

本地 CLI、环境变量与 UUID 不能证明一个模型实际获得了空历史，也不能阻止同一系统账户直接修改源码和数据库。需要强制隔离的宿主须把可信引擎与数据库置于 Worker 写权限之外，通过受控接口提供任务读取与提交；作者答复也须由宿主的可信人类交互通道绑定准确对象。当前单机适配器不创建系统账户或安全沙箱，不能把会话声明或本地文件权限提示宣传为这些能力已验证。

## 当前能力边界

| 工程目标 | 实现选择 |
|---|---|
| 开书与试章 | 零输入逐门选择（主干自执，13 门：脑洞门问"多了什么规则"，世界门交位阶与硬通货，格局门交升格阶梯），完成后按档位要求创建世界模型并做机械校验与位阶、资源、格局及已声明的世界架构逐字绑定；完整约定也可导入，首章定调保持 |
| 分卷与逐章设计 | 世界与约定生效后派发各卷卷纲（每卷 2000–3000 汉字，目标 2500，默认一次交全部卷；v5 项目每卷 `stage` 逐字取格局阶梯一级且只升不降；含伏笔账 `hooks` 与文风走向 `style.trend`）；进入每卷前交该卷章纲（每章约 150 汉字 + 漂移字段 + enter/exit + 伏笔 `plant`/`payoff` + 文风 `style`） |
| 事实连续性 | 章纲状态链在设计期逐章模拟资源前值与守恒、时钟、知情、位置、人物变化与伏笔埋收，卷末核对结构化终值和 clock.to（容差 0）且 required 伏笔全 paid；自然语言 exit_state 只作说明 |
| 执笔核账 | `drift_check` 逐项自比（覆盖、前态、去向、偏差理由与引文），引擎仅在所有项符合固定章纲时按既有事实判据入账；偏差留作本章返修，不自动改纲；伏笔事件由 `drift_reconcile.reconcile` 产出 |
| 文学质量 | 新CLI项目默认独立连读与候选比较，旧项目按原模式恢复；报告覆盖、宿主证明与文学判断分开显示，协议见[质量与宿主](quality.md)。文风代理仍是：文风由作者约定、卷纲 `style.trend` 与章纲 `style` 提供依据；默认观察首章形状，作者选 strict 才执行锚点数值约束。显式对白目标与高重复继续检查；章纲声明出场的人物由 `drift_reconcile.presence_notes` 以世界模型名做机械落实观察（severity=note，记入 draft.presence，不耗返修额度、不拒稿）；代词标签不能判实际视角。**不证明"好看、人物可信"**——文学判断靠作者抽读或离线评测工具（`scripts/quality_eval.py`） |
| 修改恢复 | 冻结任务、候选稿、版本化改约、历史分支、合并撤销 |
| 局部修复 | 冻结能力支持完整稿、版本补丁和原文复用；合成后重新过机械核算与 lint，不自动免检入库 |
| 作品理解 | 按人物、话题与显式引用选取版本解释、原文表达样本与反证；候选稿隔离、依据失效和恢复 |
| 场景身份 | 新协议的 ID 不绑定章号，移动仍核对唯一性与已提交来源；阅读顺序、故事时间、披露分开 |
| 修订传播 | revision_impact 沿事实读取、阅读关联与场景桥梁给出处理动作；覆盖不足或未声明变更时保守扩大范围，语义完整性无人独立核验 |
| 长篇运行 | 宿主主干调度子 agent，引擎保留主控/Worker 租约、提交核实与可选进程适配器；真实模型历史隔离另验收 |
| 存储版本 | 当前为 novel-ledger/5，已删除旧审稿首读存储列；v4 及更早库明确拒绝，不提供隐式迁移 |

源码精简不证明文学质量或全程费用改善。分别衡量依赖、必读材料、派工、实际用量和返工，不以行数替代功能覆盖。

## 叙事与材料边界

新约定默认启用叙事跟踪，关闭跟踪时章纲的节点与线路可空，但资源/位置/知情/时钟/人物变化仍须核算，见 [叙事推进](narrative.md)。narrative 只依赖 contracts，facts 组合其有据结算；drift 通过 facts.apply_event 复用事实、叙事与空间状态转移，并调用世界规则做设计检查；账目验算与证据核验由流程层组合。实际进度、读者认知、当前动机均可重放，不由设计直接初始化；当前记录投影与完整可选来源分开，正文不删除、不截断。阅读关联按 reading-dependencies/1 统一解释，章纲由引擎统一冻结标记。

编辑能力冻结为 editorial/1，开关与字段见协议，专用字段见 [编辑能力](editorial.md)。craft/spatial/editorial 均是纯值规则，不传 Repository。章纲重排与正文重绑定由 workflow 返回，应用层单一事务保存；预检一并回滚。

完本快照保存完整交付状态与正文引用，delivery/bookpage 只读取冻结版本；组合根把 LocalPresentation 注入 Application，交付、页面与只读查询均不反向调用应用层。统一 book.html 和世界导出是可重建派生物；submit 通过 after_commit 调用交付端口维护固定大小的预览入口，advance 返回时也维护，内容未变不重写；preview 按需读库而不把书稿复制到入口，显式 html --standalone 才嵌入全书；入口错误独立回报，不回滚已生效内容；生成时机和实际交付范围见 [约定与交付](world.md#约定与交付)。读取观测在适配层留痕，离线评测与宿主观察不修改故事。

承诺关联冻结为可选 hook-links/1：领域层只验证有据事件的实体/话题关联及变更理由，查询层据关联选择材料；未标注旧承诺不自动猜关系，仍能完整补读。事件解释版本随规范化事件保存，旧在途能力不被追补，旧投影不因新增字段解释而改变。派工 baseline 取任务自己的冻结 state 视图，避免在信封再灌入全量资源与承诺。read 和 recall 输出都留实际字符观测，计费仍来自宿主日志。

## 状态转移与规划范围

设计模拟、执笔核算的影子投影与正式提交共用 `facts.apply_event`。该函数只作用于调用者持有的临时投影；`facts.settle` 负责正文引文与时间表达检查，整章到期规则由 facts.check_deadlines 供模拟和正式结算共享，正式事实仍只由提交事务写入。卷纲窗口、章纲 enter/exit 和卷末闭合继续由 drift 家族（drift_validation/drift_simulation）检查。设计没有正文证据，模拟通过不能代替正文提交。路径拓扑的开放、方向、通行条件、携带关系与显式出发/抵达时间在设计期也按正式规则检查。

卷纲与章纲为必选阶段，策略解析统一由 planning.resolve_outline_policy 负责。缺省使用默认值；显式空对象、null 和不完整策略不能悄悄恢复成默认值。卷纲 scope 只接受 all/rolling，章纲只接受 volume/all；其余值明确拒绝。

执笔材料筛选与局部重排保持完整冻结来源；保留的后缀仍通过状态链、卷末与阅读绑定核验，细节见 [有界材料与局部重排](narrative.md#有界材料与局部重排)。

策略组合与字段形状统一见 [卷纲参数](narrative.md#参数与范围)。

2.1.0的受控宿主与独立连续性流程、默认/旧项目模式及真实能力边界详见[质量与宿主](quality.md)。CLI本身不注入可信authority，required模式缺宿主就拒绝；检查点不能阻止同账户同时篡改数据与检查点。正式新状态写入建立治理检查点，读取不隐式认证旧历史。

## 运行安装与版本恢复

runtime_install将完整发布源码、规则、模板及素材发布到开发树外，生成文件清单和指纹；新副本核验完整后发布，原检出和小说库保持只读。固定入口后续在组合根打开库前验证清单。选择Git版本通过archive读取，不使用checkout/restore/stash；旧发布副本的运行规则仍以该发布为准。

Application.recover_engine是单一事务用例：核对准确pending task/input_hash、主控租约、实际构建差异、原执行者停止声明、作者升级授权及未处理的核验，再取消旧任务并按同阶段/范围编译新任务。章纲、正文、候选和预算不因版本切换重置；旧输入仍保留在数据库，旧result.json保留在原任务目录。没有引入架空的宿主模型创建API；真实宿主的跨组持续运行需另做实际验收。
