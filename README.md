# novel-ledger

长篇小说的**账本式**写作引擎：把作者决定、创作材料、事实状态与审查结论分开记账，用可恢复、可核验的流程支撑几十万到上百万字的连续创作。

仅依赖 Python 3.9+ 标准库，无第三方依赖、无需联网（调用模型的宿主由你自己提供）。

- **定位**：写作流程的**治理层**，不是提示词集合，也不是文本生成器。它不产生一个字，但决定谁能写、写完谁审、事实怎么入账、改稿怎么不毁原稿。
- **形态**：`scripts/novel.py` 一个 CLI + `scripts/novel_ledger/` 19 个模块（多数为纯规则，`sqlite_store`/`delivery`/`host`/`bookpage` 负责 IO）+ 一个 SQLite 项目库。
- **当前版本**：`1.3.0`，数据库 schema `novel-ledger/2`（旧版本库显式拒绝，不做隐式升级）。

1.2.0 将世界设定与正文统一到自动生成的 `book.html`，新增关系、时间线与进度图表；新书默认在世界核验后完成所有卷的逐章卷纲，每章目标 500 汉字（450～550），按有界批次独立核验。正文默认从场景切入，避免逐章报日。当前工作区的编辑能力、历史来源复用与远期承诺关联也随本版本交付；旧项目和在途任务仍保持自身协议，尚无保留全部内容并仅补卷纲的一键升级入口。

1.3.0 重做开书逐门选择：八门改为**十门，一门只问一件事**——题材承诺与基调 / 叙述视角与人称 / 体量与分卷（结构门）/ 世界前提机制与禁区 / 主角 / 核心关系 / 推进与对抗 / 终局与母题 / 文风与节奏 / 书名。视角排在所有展示画面样本的门之前（画面必带人称，最后才定人称等于让作者用错质感评估方案），世界先于人物与推进，关系先于对抗，书名最后。体量与分卷是**结构门**：档位由 `contracts.SCALE_TIERS` 给定并由引擎当次给出，不派工、不等待，每一档都已证明能写出一份通过约定校验的书。新书因此是 9 次派工 + 10 次作者选择，但每一门的决定更纯，返回重选的代价也更小。作者新增基调、母题、书名、叙述视角四项决定，其中视角由清单版本 4 的 `reader.pov_consistency` 独立核验。开书协议版本随项目状态冻结（`novel-ledger.creation/1` 的既有项目仍走原八门），数据库 schema 未变。

---

## 一、它解决什么问题

让模型写长篇，通常在几十章后崩掉：时间线对不上、资源凭空出现、人物知道了他不该知道的事、伏笔丢了、改一章要重写全书。常见做法是往提示词里塞更多规则，但提示词管不住状态——**没人能证明第 47 章的资源余额和第 12 章结算过的一致**。

novel-ledger 把这些问题当**账本问题**处理：让每一章的事实有出处、每一次判断有回执、每一份材料有哈希、每一个额度有上限。核心主张是：

> 文学判断交给独立审稿者，机械可验证的部分交给程序，两者都不许越界。

---

## 二、架构

```mermaid
flowchart TD
    CLI[命令入口] --> APP[应用编排]
    CLI --> SQL[SQLite 适配器]
    CLI --> HOST[宿主进程适配器]
    APP --> WF[纯流程决策]
    APP --> CTX[上下文查询]
    APP --> VIEW[任务与导出视图]
    WF --> OPEN[逐门选择]
    WF --> WORLD[世界规则]
    WF --> PLAN[规划规则]
    WF --> QA[质量规则]
    WF --> FACT[事实规则]
    WF --> NAR[叙事推进]
    WF --> SR[分层范围审]
    WF --> ED[编辑裁决]
    WF --> CF[人物与文本规则]
    PLAN --> CF
    QA --> ED
    FACT --> SP[空间拓扑]
    FACT --> NAR
    PLAN --> NAR
    QA --> SR
    CTX --> NAR
    CTX --> SR
    PLAN --> FACT
    QA --> FACT
    ED --> C
    CF --> C
    SP --> C
    PLAN --> C[共享数据契约]
    FACT --> C
    SQL --> C
    HOST --> C
```

上图为主要源码依赖；application 逐域 import 与各域到 contracts 的边在图上省略，完整边集由依赖守护测试与 `validation/measure.py` 计数给出（当前完整边集见 validation/metrics.json、无环）。渲染图见 [docs/architecture.svg](docs/architecture.svg)；源码真源是 [references/architecture.md](references/architecture.md) 中的 mermaid 块，本图与 `docs/architecture.mmd` 保持逐字一致，由测试守护。

### 分层与职责

| 层 | 模块 | 职责 |
|---|---|---|
| 入口 | `novel.py` | 参数解析、**访问分级**（公开/封印命令）、主控与 Worker 角色边界 |
| 编排 | `application` | 组合领域结果、**单一事务提交**、作者决定、运行认领与租约 |
| 决策（纯） | `workflow` | 下一个任务是什么、状态怎么迁移、修复额度怎么消耗 |
| 选择（纯） | `creation` | 逐门方案、换组回退、闭合选择与来源 |
| 世界（纯） | `world` | 丰富世界记录、跨记录关联、与所选方向的一致性 |
| 规划（纯） | `planning` | 作者约定、设计图、章计划、人物档案校验 |
| 事实（纯） | `facts` | 资源守恒、主支线时钟、知情、关系、地点站位、历史断言的纯结算 |
| 质量（纯） | `quality` | 首读与审稿回执的完整性、一致性、证据核验，模板生成 |
| 查询 | `context` | 冻结来源登记、必读选择、按人物/物品和话题带入远期承诺、按需补读入口 |
| 视图 | `delivery` | 任务目录物化、模板与表单、正文与世界导出 |
| 全书视图 | `bookpage` | `html` 命令的单文件页面：看设定与读正文两种模式 |
| 持久化 | `sqlite_store` | 事务边界、唯一 pending、幂等回执、不可变文档、分支、可复用逐章历史目录 |
| 宿主 | `host` | 外部进程执行、超时终止、核实真实提交 |

「纯」= 不 import SQLite、文件、子进程，也不持有全局状态；这条约束由测试里的依赖守护强制（含函数内 import），不是文档口头约定。

---

## 三、六个设计要点

### 1. 单一真源，派生物可弃

SQLite 是唯一持久真源；`work/` 目录、`book.html`、世界视图全部可重建，删掉不影响项目。提交走一个事务入口：领域判断、证据核验、事件结算、状态迁移全部成功才 commit。

新增一条材料或一次判断，只有两个落点——**不可变文档**（按内容哈希存放）或**kv 状态投影**，没有第三处可以偷改。

### 2. 约定形状只有一处定义

`contracts.CONTRACT_FIELDS` 是作者约定形状的唯一权威：交付模板、结构校验、对齐核验全部由它派生。

```python
CONTRACT_FIELDS = (
    {'key': 'title', 'kind': 'text', 'default': '', 'alignment': True},
    ...
    {'key': 'volumes', 'kind': 'rows', 'default': [], 'alignment': True,
     'shape': ('id', 'purpose', 'end'), 'blank': False, 'count': 1},
)
```

结果是三件事同时成立：模板不会漏字段（漏了就等于开书流程走不通）、未知字段直接拒绝（旧版本残留字段无法蒙混）、对齐表与字段表一旦脱节立刻报 `alignment_schema`。派生而非复制，是这套代码里反复出现的做法。

### 3. 事实由独立审稿者从正文重建

执笔任务**只交**正文、标题、摘要与自评；提交 `events` 会被拒绝——事件必须由另一个 Worker 在章审阶段从正文重新读出，逐条附引文与位置，再由程序机械核验前值、守恒、时间推进与引文真实性。执笔自评从不发给审稿者。

程序只证明机械条件（引文存在、数值一致、前值匹配）；**知情、代价与路径是否成立仍由独立审稿者判断**。两类核验（事实 / 阅读）必须都通过，章节才能入库。

### 4. 首读冻结与身份隔离

审稿者先只拿到冻结正文，读完提交「首读」：每章的欲望、阻碍、变化、追读理由。该记录一旦落库即不可改写、不可换人；之后才解锁完整资料做逐项核对。想要换审稿者，只能取消旧任务、生成新首读。

角色边界是**代码执行**的，不是称呼约定：`read`/`recall`/`first-read` 只在携带派工身份（`NOVEL_TASK_ID`）时可用，主控身份调用会被 `role_boundary` 拒绝——「主控不读写正文」由此成立。

### 5. 额度有限，消耗留痕

每章共享一个修复预算：**两次返修 + 一次重设计**。换 Worker、预检回滚、暂停恢复、历史修订、改约都不重置；字段拒绝不计次，但真实的短稿提交计一次并保留稿件。额度耗尽即暂停，保留候选正文与全部失败记录，不无限重试。

首章认可绑定准确的 `prose_hash` 与作者原话；约定变更（`recontract` / `opening`）记录 `producer`，核验者必须不同，且 `promote`、`complete` 的验收会复查这条记录。

### 6. 修订不毁原稿

历史修订从指定章起在**候选分支**完整重写并重审受影响后缀，原正式稿一直保留；范围复核通过才 `promote` 合并，也可以 `discard` 回到原稿与原目标——但已消耗的编辑额度不退还。跨章核验先分块审查全部章节，再由独立综合者阅读块报告、逐章证据与必要原文，独立判断，不能拿块 `pass` 当综合结论。

---

新增编辑能力在当前纯规则层接入：人物成长后重核表达，章计划声明场景意图与展开单元；返修可交版本补丁，但仍完整独立重审。成立正文的偏离可独立改案，卷末按职责关闭、补写或修订，根问题两轮额度跨任务与分支保留。完本从准确快照导出正文、阅读页与清单，失败只恢复交付。字段与边界见 [编辑能力](references/editorial.md)。

新约定默认 `editorial_features=true`，任务冻结 `editorial/1` 与检查清单 3（约定声明了 `pov` 时用清单 4，多一项 `reader.pov_consistency`）；旧项目和旧 pending 保持自身协议。部分作者要求用 `intake` 保存，只询问未定门；`usage` 与 `scripts/observe.py` 分别观察工程字符和宿主实际 token，`scripts/quality_eval.py` 提供独立盲测样本、首读冻结与定位计分。

## 四、项目库与生命周期

写小说产生的项目是**独立目录**，不在本仓库内：

```text
my-novel/
├── novel.sqlite3            唯一真源
├── work/<task_id>/          派工材料与回执（可重建）
├── book.html                全书视图：看设定（约定/世界/设计/计划/档案/账本/章审）+ 读正文
├── book.md                  纯文本导出（export）
└── world.json              世界模型与选择、核验记录；页面合并到 book.html
```

`book.html` 是**派生只读视图**：init 自动生成，开书完成后更新为包含世界设定的统一页面，不再生成单独的 world.html。单文件、无外部请求、无服务端，数据全部来自数据库，可随时用 `html` 命令重新生成；删除它不影响项目。设定模式提供世界关联图、历史与章节时间线、因果节点图、人物关系和地点站位图，以及字数、分卷、章幅与资源图表；图表保留完整文字明细，点击节点可定位详情。阅读模式支持字号、版心、纸色与字体切换，设置存在浏览器本地，`Ctrl+P` 可打印或导出 PDF。

`export` 输出纯文本或简化 HTML，**默认不会写 `book.html`**（那个位置归全书视图）；需要另一个文件时显式给 `--output`：`export --format md`、`export --output book-plain.html`。

SQLite 中的七张表各司其职：

| 表 | 作用 |
|---|---|
| `kv` | schema 版本、治理状态（`book`）、外部键值（分支存档、租约） |
| `documents` | 不可变完整值，**按内容哈希寻址**；冻结来源与正文都在这里 |
| `tasks` | 冻结输入、首读、回执；**唯一 pending 索引**保证同一时刻只有一个在途任务 |
| `sessions` | 会话到任务的绑定，用于**禁止跨任务复用会话** |
| `branches` / `chapters` | 分支与正式章节；每章带正文哈希、事件、计划、审稿、状态哈希与**前章链指纹** |
| `journal` | 操作轨迹：派工、提交、取消、改约、修订、完本 |

一次完整生命周期：

```
init ──► 逐门选择（10 门，一门一件事）──► 世界模型 ＋ 独立核验 ──► 完整约定 ＋ 独立核验
   └─ 或 --contract 直接导入完整约定
        │
        ▼
   全书骨架 ─► 卷内脑暴 ─► 逐章卷纲（分批独立核验） ─► 章计划 ─► 人物档案 ─► 执笔 ─► 首读冻结 ─► 章审（事实＋阅读）
        │                                            │
        │                                    入库：结算事实、更新投影、记录链指纹
        ▼
   间隔块审 ─► 卷末审 ─► 全书复核 ─► complete 验收（篇幅、承诺、快照）──► export / html
```

---

## 五、仓库结构

```text
novel-ledger/
├── README.md             本文件：架构与特点
├── SKILL.md              技能入口（DSH 等宿主的加载说明与执行边界）
├── scripts/
│   ├── novel.py          CLI：参数、访问分级、主控/Worker 边界
│   └── novel_ledger/     19 个模块（contracts 为约定字段唯一权威；bookpage 生成全书视图）
├── references/           分任务阅读的规程
│   ├── opening.md        逐门开书（含结构门与开书协议版本）
│   ├── world.md          丰富世界模型
│   ├── craft.md          创作与写审
│   ├── runtime.md        运行、恢复、宿主适配
│   ├── protocol.md       任务与结果协议、事件表
│   ├── architecture.md   模块职责、不变量、扩展指引
│   └── validation.md     验证方法与文学评估口径
├── assets/               可运行的完整约定样例
├── tools/                安装脚本（install-dsh.ps1：链接到 DSH 技能根）
├── docs/                 架构图产物（真源在 references/architecture.md）
├── tests/                200 项行为测试
└── validation/           工程度量脚本与验收记录
```

运行所需路径与常用命令：

```bash
python scripts/novel.py --version          # 1.3.0
python scripts/novel.py --help             # 全部子命令
```

进入真实写作流程需要的最小序列（`$P` 为你的小说目录）：

```bash
python scripts/novel.py --project "$P" init                # 零输入开书
python scripts/novel.py --project "$P" advance             # 取当前门方案或下一个任务
python scripts/novel.py --project "$P" init --contract assets/contract.example.json --source '作者原话'
python scripts/novel.py --project "$P" run --through 3 --source '作者授权先写三章'
```

`run` 返回 `owner` 租约令牌，之后每个主控命令都要带 `--owner <令牌>`，否则返回 `controller_lease`。派工与提交的完整流程见 [运行与恢复](references/runtime.md)。

---

## 五之二、安装到 DeepSeek Harness

DSH 通过 `@deepseek-ai/dsh-skill-filesystem` 发现本地技能（需该 provider 未被禁用）。它按优先级扫描若干根目录，任一根下的 `<name>/SKILL.md` 即为一个技能：

| 优先级 | 根目录 | 说明 |
|---:|---|---|
| 100 | `<projectRoot>/.dsh/skills` | 项目根是最靠近的含 `.git` 的祖先目录；仅对该项目生效 |
| 200 | `<projectRoot>/.agents/skills` | 同上，另一个共享约定 |
| 300 | `customSkillDirs` | 在 DSH 设置里自定义 |
| 400 | `$DSH_HOME/skills`（默认 `~/.dsh/skills`） | **推荐**：开启的每个工作区都能看到 |

安装就是把仓库链接到某个根目录，让 `git pull` 直接更新已安装的技能：

```powershell
# Windows（无需管理员权限，使用目录 junction）
powershell -ExecutionPolicy Bypass -File tools/install-dsh.ps1
powershell -ExecutionPolicy Bypass -File tools/install-dsh.ps1 -Remove
powershell -ExecutionPolicy Bypass -File tools/install-dsh.ps1 -Root D:\another-skills-root
```

```bash
# POSIX（符号链接）
pwsh tools/install-dsh.ps1            # $DSH_HOME/skills
pwsh tools/install-dsh.ps1 -Remove
```

脚本会在建立链接后自检：SKILL.md 能否透过链接读取、`scripts/novel.py --version` 是否可运行；若目标位置已有真实目录或指向别处的链接，会拒绝而不是覆盖。装好后技能在下次目录刷新时出现，无需重启。

技能正由同一份源码供多个宿主使用（例如 Codex 的 `~/.codex/skills` 也指向本仓库）；每个宿主需要各自建链，改动一次即可全部生效。

---

## 六、开发与验证

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v   # 200 项
python3 validation/measure.py --out validation/metrics.json          # 依赖图与必读材料度量
```

测试只用合成回执与临时项目：**验证协议、流转、额度与边界，不验证文学质量**。当前工程度量见 [metrics.json](validation/metrics.json)，包含所有函数内导入；纯规则依赖仍无环。改动引擎前请先读 [架构与工程目标](references/architecture.md)，并运行依赖守护测试。

Windows 提示：技能自身按 UTF-8 读写，默认 GBK 控制台下测试与 CLI 均可用；若运行外部校验脚本报编码错误，加 `PYTHONUTF8=1`。

---

## 七、边界与约束

- **字数**按汉字计数；`word_range` 与章幅区间由作者约定，系统不会为了让指标好看而降低目标。
- **默认字面规则**：正文与标题不出现系统词汇「账本、入账、回执」；**人名禁字默认为空**——起名是作者的决定，需要限制时用 `lexical` 命令按书设定。规则随任务材料的 `policy` 块交付，覆盖范围与版本可查，覆盖内容逐版留档、开书阶段即生效。
- **数据库版本**：`novel-ledger/2`，旧库显式拒绝。
- **不做的事**：不自动打开或转换未知来源数据库；不代作者做选择；不提供后台常驻能力。
- **未验证的部分**（不要把工程夹具当文学成果）：真实模型的历史隔离、应用退出后的持续运行、计费用量控制，以及真实文学质量评估——口径见 [验证](references/validation.md)。

## 许可

本仓库目前**未附许可证**，默认保留所有权利。如需在其它项目中使用或分发，请先联系作者添加合适许可证（如 MIT）。

## 叙事推进与长篇材料

新约定默认启用叙事跟踪：主线、支线与暗线登记职责和终局条件；节点推进、读者已见信息、人物当前动机和节奏均由独立审稿举证后结算。窗口前提变化触发重规划，每章根据真实累计篇幅计算剩余预算。完整协议见 [叙事推进](references/narrative.md)。

世界模型核验后，新约定默认继续全书骨架与所有卷逐章卷纲：基于世界比较卷内推进方案，再分批写每章目标 500 汉字（450～550）的精练情节说明，独立核验后保存并展示在 book.html。完整卷纲覆盖本卷全部章节，试写一章也不会截短；没有正文授权以 outline_ready 交付。volume_outline 默认 scope=all，在正文前完成所有卷；scope=current 可改为先交首卷、后续逐卷设计，tolerance=0 可要求严格 500 字；旧生效约定缺字段及旧 pending 保持原协议。

范围核验先完整读叶块，再按有限扇出逐层综合子报告与边界原文；正文、原报告与完整设计仍保留补读入口。执笔只取目标和直接因果前置，历史可按人物、节点、主题或线路检索。旧项目与旧在途任务沿自身协议，新能力需通过明确改约建立版本；已有审稿不因新增清单追溯失效。

历史来源不再为每轮派工重建全量摘要和事件索引：逐章不可变目录共享未改前缀，任务只冻结目录入口，补读按冻结范围分页返回完整证据及正文。远期承诺可由独立审稿按证据登记人物/物品和话题关联，相关对象再次登场即可带入任务材料；未标注旧承诺仍可补读。派工资源与承诺摘要也取任务冻结视图。原索引名称保持显式完整读取兼容，数据库没有新增表或隐式迁移。

规模与查询读量见 [工程验收](validation/results.md) 的历史来源测量；稀疏检索仍可能遍历全部冻结历史。真实长篇、跨卷文学盲评与实际费用的验收方法见 [验证](references/validation.md)，节奏和多线编排不采用未经验证的固定轮替门槛。

这些是可核验的治理和材料选择机制，不承诺仅靠机械校验证明文学质量或实际模型费用。
