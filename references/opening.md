# 零输入逐门开书

何时读：没有想法也要开书、逐门选择、换方案或恢复开书。讨论技能不表示启动真实小说。

## 适用范围与决定权

作者决定方向，系统负责给出具体选项、保存来源和核验一致性。已有要求先整理保存，只询问真实缺口。门序与字段是协议要求，故事方案的优劣依据具体推进差异判断，写审原则见 [创作与写审](craft.md)。

## 入口选择

下表命令均使用 `python3 ROOT/scripts/novel.py --project PROJECT` 入口。先确认项目是否存在、是否已经派过门任务，不覆盖项目或要求作者重填已有设定。

| 当前情况 | 命令 | 结果与边界 |
|---|---|---|
| 新项目，无完整约定 | `init` | 进入逐门选择，已有部分要求再用 intake 保存。 |
| 新项目，已有完整约定 | `init --contract 约定.json --source 原话` | 采用已有约定，默认推进试章目标。 |
| 已 init，尚未派过门任务 | `opening --file 约定.json --source 原话` | 导入完整约定，清除逐门选择并进入核验。 |
| 已派过门任务或已有约定 | `recontract --file 约定.json --source 原话` | 保留旧记录，经独立核验后激活新约定，见 [暂停与修改](runtime.md#暂停与修改)。 |
| 未展示当前方案且无 pending，已有部分完整门要求 | `intake --file 要求.json --source 原话` | 按门 ID 保存已定值，后续跳过这些门；不替缺口补造决定。 |
| 已有项目续写或恢复 | `status`，再 `advance --compact` | 接回当前任务；执行身份与授权见 [运行](runtime.md)。 |

## 用户体验

用户只需表示要开书。不要要求先写一句话、提供题材、起名或填设定表。无 --contract 的 init 创建逐门项目，advance 即派 opening_options。

未指定项目路径时，主控在当前工作区选择独立小说目录，告知保存位置；不要覆盖已有项目，也不把选择目录变成必答门。技能目录只保存技能，不放正文项目。

板面在 `await_choice` 时由引擎物化为 `work/board.md`（返回里的 `board_card` 路径）：门名、进度、每个方案的 id 与全部作者可读字段、命名提示和固定操作。同轮还会物化 `work/question.json`（返回里的 `question_card` 路径）：可直接投给宿主提问组件的选项结构，label 用短标题、description 用 pitch（结构门用 premise）原文。主控把卡片内容原样交给作者——先在回复正文里贴出 board.md 的内容（或给出其文件链接），再用 question.json 的选项原样发起提问，**不自拟一句话摘要替换引擎文案**；不在 GBK 控制台读长 JSON，也不手工重排版。`advance --compact` 的返回只带门名、哈希与 option_ids，完整板面以 board.md 与 `work/last-advance.json` 为准。

每次只展示当前门名、进度和 2～3 个具体方案。方案说清主要内容、推进差异和代价，用户只选 A/B/C 即可；支持“换一组”和“返回某门”。不把字段、哈希和命令展示给用户。真实选择到来才推进，预选和超时不代表选择。方案 id 由生成方自定（不一定是 A/B/C），主控执行 choose 时用展示组里的真实 id；传错 id 的拒绝会带 `valid_options` 列表。

### 门任务由主干自执（默认，不再每门派子 agent）

开书门没有独立性要求：无正文、无首读封印、无审写分离，而实测每派一个冷子 agent 要 0.4M～1M input token、等 2～5 分钟，信封只有 3.6K 字符——代价买不到任何东西。因此门任务（`opening_options`，声明在 `contracts.CONTROLLER_STAGES`）默认由主干在同一会话内执行：

1. `advance --compact` 取任务与 `task_path`；
2. 读任务目录的 `brief.md`（简报全文，`input.json` 里那份是同一内容的 JSON 原文，不必解析）；需要必读记录时直接 `read --task 任务ID`（该阶段对主控放行 read/recall，正文与审读阶段不在此列）。同一会话连跑多门时可豁免：上一门的 `read` 返回 `records_hash` 与本门相同、且简报未新增必读记录，跳过本次 read；
3. 从 `result.template.json` 复制起稿 `result.json`，只填 data（信封三字段不手写，`input_version` 报错会带 expected）；`check` 试算后 `submit`（回执 `session` 填主干自己的会话身份即可，门任务不绑定会话）；
4. 展示板面等作者选择（板面与提问的转发纪律见上）；「换一组」就 `regroup` 后重复——同一会话连续换组即是复用，作者在环防止锚定。

世界门完成后（`world_model` 及之后的一切）恢复派独立 Worker：那些阶段有真实的独立性与首读要求。宿主确实无法内联时才退回逐门派工，并如实说明。

### 第一门的全类目

作者没给题材方向时，第一轮不抽三个冷样本：任务简报已内置 `contracts.GENRE_CATALOG` 十二个男频类目（玄幻、仙侠修真、都市异能、都市职场、历史权谋、科幻末世、悬疑探案、游戏电竞、武侠、军事战争、体育竞技、二次元轻小说），**主控在对话里把目录铺给作者**（内联执行时直接展示，派工时随派工说明转述），收一句方向或自定义；**回执仍按 offer 协议交 2～3 个方案**——在该类目内深化，不把全目录当成回执选项。作者已给方向时跳过铺目录直接出案。

### 主角门的命名纪律

AI 起名高度趋同（潇洒姓×玄乎单字是重灾区，同一个玄乎字会在多本书里反复出现）。主角门执行四条：姓氏贴世界与阶层、俗字与双字名优先、称呼链一次想好（全名→日常称呼→诨名/职衔）、口语测试三遍。套路组合会在板面上以 `name_warnings` 提示（advisory，只警不拦，作者坚持则以作者为准）。**硬禁某个字**用字面规则：`lexical --file {"forbidden_name_chars": ["砚"]} --source 作者原话`，此后 opening_options/world_model/章计划的人名字段都会机械拦截该字。

### 换组纪律

换组后的新一组必须与被拒旧组方向实质不同：不得换名、改写收益或微调细节冒充新组；吸收作者随换组补充的偏好（说「格局太小」就把格局拉高一级：从个人恩怨到生态位、从一条街到一座城一个秩序）；已拒方向在 `opening_rejections` 记录里，避开其思路而不只是措辞。换组按 round 顺延创意透镜。

## 门序与字段归属

新项目门序由 `creation.GATES_V3` 定义（男频长篇网文重设：`genre → voice → scale → edge → protagonist → relationships → world → opposition → payoff → title`）；直接选择字段由 `contracts.CONTRACT_FIELDS.opening` 按版本声明，推导输入由 `creation.DERIVATION_INPUTS` 声明。**已有项目保留自己的门序**：`creation/2`（`GATES_V2`）与 `creation/1`（`GATES_V1`）继续按各自协议运行，不迁移、不按新门重读旧选择。下表供理解当前版本，实际交付以本任务简报列出的允许字段为准：

| # | 门 | 类型 | 作者要回答的一件事 | value |
|---|---|---|---|---|
| 1 | `genre` 题材、频道与读者承诺 | 创意门 | 卖什么、谁看、爽点承诺是什么、什么基调 | genre/reader_promise/tone |
| 2 | `voice` 叙述人称与语感 | 创意门 | 谁在讲、能看多远、读起来是什么质地 | pov/voice/style_traits |
| 3 | `scale` 体量与分卷 | **结构门（引擎即时）** | 这本书多大、多少卷、每章多长 | tier/chapter_min/chapter_max/chapter_aim/volume_count/chapters/chapter_window（总字数区间 word_range 是派生结果：章数 × 每章区间，作者与 Worker 都不用填） |
| 4 | `edge` 核心优势与成长线 | 创意门 | 他靠什么赢、怎么变强、代价与上限 | advantage/origin/growth/cost/ceiling（约定字段 `core_edge`） |
| 5 | `protagonist` 主角身份、处境与底线 | 创意门 | 他从哪开始、要什么、底线在哪 | id/name/identity/desire/limit |
| 6 | `relationships` 核心关系与情感线 | 创意门 | 助力与背叛风险在哪、感情线多重 | relationships（至少一条） |
| 7 | `world` 世界前提、机制与禁区 | 创意门 | 世界怎么持续供料、有无特殊机制及其代价、绝不写什么 | world_premise、mechanism{mode,principle,cost,limits}、red_lines、allow_special_mechanism |
| 8 | `opposition` 主要对抗与冲突梯度 | 创意门 | 第一卷谁挡着、怎么逐卷抬高、终局面对谁 | opposition/story_engine |
| 9 | `payoff` 爽点兑现与终局 | 创意门 | 读者一路拿到什么、怎么兑现、最后兑现成什么 | plan{ways,cadence,hooks}（约定字段 `payoff_plan`）、ending、theme |
| 10 | `title` 书名 | 创意门 | 叫什么 | title |

人称与视角在人物、世界与对抗之前定下来，所以 `voice` 排在最前：后续各门的 scene 都用该方案的人称写。题材门的画面发生在人称选择前，只作体验预览，不替作者锁定人称。世界规则约束后续对抗的加码方式，关系门同时提供助力和背叛风险，书名承接已选题材与核心优势。

无预填、换组或回退时，十门为 9 次创意方案生成（默认主干自执，不派工）与 10 次作者选择；结构门当次给板。已有要求跳过相应门，实际次数随作者操作变化，不作为固定用量承诺。

方案字段以当前 brief 和模板为准，构思方法见 [创意工具箱](hatch.md)。`voice` 与 `title` 这类单一决定门另有专门交付要求：叙述门的每个 scene 用该方案的人称展示实际效果，书名门给真正可用的候选名，不交占位符。

## 默认方向（起点/番茄男频长篇网文）

十门的默认方向是**起点/番茄男频长篇网文**，声明在 `contracts.OPENING_DIRECTION`（共用做法）与 `contracts.OPENING_DIRECTION_GATES`（每门要点），由 `briefs.opening_options` 与 `briefs.world_model` 逐门渲染进简报，所以冷启动的方案生成者不必猜市场口味：

- 开篇三章内给压力与第一个可见收益；主角有可升级的稀缺优势或金手指，升级有条件与代价；每卷对手与舞台抬高一级；短线小兑现与长线悬念交替，章末留钩；冲突落到资源、名额、地位、复仇、守护、真相这类具体利益；题材走男频主流落点；语感短句推进、对白带信息；体量按长篇连载预期起步。
- 每门还有一条要点：题材连承诺一起给（爽点是什么、看谁赢谁），视角便于持续给爽点与信息差，世界机制持续供料，主角身份自带上升通道，关系同时给出助力与背叛风险，推进动力能反复加码，终局兑现开篇承诺的那场胜利，书名按男频搜索习惯点出看点。

这是**默认而非硬要求**：作者原话或已选方向与它冲突时一律以作者为准，方案与核验都不因为"不合男频"判错；作者要的是别的方向时，简报里这句话和这条约束同时存在。要改这个默认，改 `contracts` 里那两张表即可，其余文档与简报随之变化。

`init` 新建项目使用 `novel-ledger.creation/3` 十门协议（男频长篇方向），creation 状态保存所用门序版本；存储布局另使用 novel-ledger/3。协议版本与数据库版本各自负责自己的结构，不能通过修改版本号转换旧库。

## 结构门（体量与分卷）

档位唯一权威是 `contracts.SCALE_TIERS`：六档阶梯（微型 / 短篇 / 精简 / 标准 / 长篇 / 超长），每档给出总字数区间、章幅上下限与目标、卷数、推荐总章数与该档可写完的章数区间。板子取阶梯上连续三档，默认窗口为“标准/长篇/超长”（男频连载常见体量，`SCALE_DEFAULT_WINDOW=3`）；短篇与微型换一组即可取到。**微型档的章窗从两三章的短篇一直到十七回的微型连载都算（`chapter_window [2, 19]`，推荐仍是 17 回）**：作者的"三章完本"这类要求必须有档位可以落地，否则契约层可以改到该体量，而完本审计仍会以"章数与档位不相容"拒绝这本已经写完的书。

- 游标落到体量门时，主控直接把档位板写进展示状态并返回 await_choice：**没有任务、没有 Worker、没有等待**。
- 只向作者展示档位名、总字数区间、卷数、每章字数与章数，以及这一档比相邻档多买到什么、少买到什么。**不要求 pitch 与 scene**，也不要求 Worker 编造数字；方案回执的 pitch/scene/driver 硬要求只适用于创意门。
- 换一组沿阶梯滑动窗口（例如“标准/长篇/超长”），并照常保存否决。作者直接给了目标体量或档位时用 `choose --tier t0～t5` 一次到位：窗口自动滑到该档再落选择，不必换组重问。
- 窗口只筛选展示范围；每档的比较说明始终依据完整阶梯，同一档位换到其他窗口仍保持相同说明。只有完整阶梯的最后一档才称为最大档。
- 档位数字与推荐章数由 `creation.validate_value` 校验；约定阶段的章数必须落在该档可写完区间内，否则报 `opening_alignment`。测试逐档证明每个档位都能写出一份通过 `planning.validate_contract` 的约定。

## 方案回执（创意门）

data={gate,options:[{id,title,pitch,scene,premise,driver,tradeoff,fit_reason,value}]}，每门 2～3 个，不预填作者决定。

- `pitch` 一句能记住的话（≤40字），`scene` 2～3 个可落笔的具体画面（谁在哪、手上是什么、正要做什么），两者都是硬要求：作者要看到能直接开写的场面，而不是概念。
- 透镜与方法**只用于构思，不得出现在给作者看的文本里**。`driver` 写这一版如何推进，`tradeoff` 写选它要放弃什么（与同组另外两案相比），`fit_reason` 写与已选方向的具体接口。写"某透镜落地/典型落法"会被 `opening_voice` 拒绝。
- 同组方案的推进方式不得同构（例如三案都以"以…为刻度推进"起句），会被 `opening_diversity` 拒绝。

新派 opening_options 冻结 capabilities.opening_bounds=opening-bounds/1，程序按去除首尾空白后的字符数执行 pitch≤40、scene 最多3条。没有该能力的旧冻结任务保留原校验规则，已接受的旧方案板继续按原展示版本选择，不因升级重新拒绝；creation/1 和 creation/2 的门序及 value 规则仍由各自协议决定。

创意门执行者（默认主干，派工时为 Worker）先读 task.json、任务目录的 `brief.md` 和 required 中的完整记录。本门规则、当轮方法及已选方向已写入 brief；方案阶段当前必读记录为 opening_rejections，opening_choices 按需补读，不把可选资料升级为重复必读；完整回执的成品示例见 `assets/opening-options.example.json`。单一决定门按简报的专门交付要求执行；结构门由主干展示引擎档位板，不派 Worker 或提交方案回执。

`value` 只接受本门负责的字段，任务简报会列出允许字段。携带其他门的字段或未知字段按 `opening_option` 拒绝，详情给出 `allowed_fields`、`unknown_fields` 和修正出口；例如书名门不能附带 `pov` 改写已选视角。intake 使用相同边界，形成约定时还会再次校验闭合选择；改此前决定须 back 返回对应门。

## 系统执行

以下为默认路径；实际派工始终按 advance 与冻结任务执行，不按流程表手造下一任务。

| 阶段 | 执行者与动作 | 交接依据 |
|---|---|---|
| 初始化 | 主干 init，随后 advance --compact。 | 自动生成 book.html，返回 book_view 的绝对路径；无设定时不要求 source 或 contract。 |
| 创意门 | **默认主干自执**（同一会话读 task.json、brief.md 与 required，生成方案并 submit，不派子 agent）；宿主无法内联时才派新空历史 Worker。 | 主干自执无交接等待；派工路径由主干等待结束再 --after 核实提交，委派只给任务路径和当前角色。 |
| 结构门 | 引擎即时返回档位板，主干展示。 | await_choice，无任务或 Worker；方案回执按 opening_system 拒绝。 |
| 作者选择 | 展示当前原组，选择后 choose 保存原话，再 advance。 | 系统不代选；换组和返回保留记录。 |
| 世界与约定起草 | 最后一门 choose 返回 next=world_model，立即 advance 派工。 | 默认任务同时包含 world_model 与 opening_contract，回执为世界字段加 contract；以任务 stages、payload.also 和模板为准。 |
| 独立核验 | 依次派 world_review、contract_review。**t0/t1 契约随设计核验**：世界通过后引擎用同一套对齐校验（含与已核验世界的 world_rules 逐字一致）直接激活合并派工起草的约定，判断并入其后的 design_review（author_constraints 项对照生效约定）；返修动过世界导致对齐不过时自动回退独立契约核验。t2+ 与单独下发的 opening_contract 仍走独立 contract_review。 | 世界通过后才核验其约定；旧任务独立下发 opening_contract 时仍按原任务执行。 |
| 骨架与卷纲 | 按已核验约定设计并核验骨架、卷方向和逐章说明。**微型档（t0）默认合并派工**：骨架与整卷逐章卷纲同一个回执交付、同一次 design_review 核验，不再分批派 volume_outline；其余档位见 [叙事推进](narrative.md#滚动卷纲)。 | 策略、批次与实际覆盖见 [叙事推进](narrative.md#滚动卷纲)。 |
| 交付 | outline_ready 按 planning_mode/coverage 交付；关闭卷纲时为 world_ready。 | world_view.html_path 指向统一 book.html，另交 world.json 的绝对路径；视图失败可 advance 重建。 |

已有明确正文授权时，开书交付后按原话调用 run；没有授权时在 outline_ready/world_ready 停止，不把选完设定等同于写完整本。

后续世界、约定和卷纲任务同样等待子 agent 结束，再用 --after 核实提交；会话恢复及完整动作分支见 [运行](runtime.md)。

## 操作与恢复

已有部分完整门要求可在 init 后、未展示当前方案且无 pending 时用 `intake --file 要求.json --source 作者原话` 保存。文件如 `{"payoff":{"ending":"作者指定结局。","theme":"母题。"},"title":{"title":"书名"},"scale":{"tier":"t0"}}`：键是**门 ID**，值是那一门的完整 value；用约定字段名当键（例如 `theme`）会被拒绝并返回 `valid_gates`。结构门只需给档位 ID（`t0`～`t5`，`t0` 为五万字级的微型档），引擎补齐已证明的数字——作者不必从引擎里抄算术，手改过的数字也不会被静默修正。门 ID 必须属于当前 creation 协议；新项目的 `novel-ledger.creation/3` 使用上表十门（`payoff` 承担终局与母题，`edge` 承担核心优势）。只保存作者已定的值，不替缺字段补造决定。后续自动跳过这些门，保留原话和版本；返回会归档受影响的后续门。展示当前方案时不能 intake（含结构门板子），先选择或 back。

```bash
python3 "$ROOT/scripts/novel.py" --project "$PROJECT" init
python3 "$ROOT/scripts/novel.py" --project "$PROJECT" advance --compact
python3 "$ROOT/scripts/novel.py" --project "$PROJECT" choose --option A --board 当前展示哈希 --source 'A'
python3 "$ROOT/scripts/novel.py" --project "$PROJECT" choose --tier t1 --source '作者原话：写十万字'   # 结构门直达档位，窗口自动滑动
python3 "$ROOT/scripts/novel.py" --project "$PROJECT" regroup --board 当前展示哈希 --reason '换一组'
python3 "$ROOT/scripts/novel.py" --project "$PROJECT" back --gate scale --reason '返回体量重选'
```

board 哈希由主控从展示响应恢复，用户不需知道。选择绑定准确展示版本，旧组编号不能套到新门。保存各组、选择、否决和原话；回退保留前门，后续依赖选择归档后重选。世界构建期间仍可回退，旧任务取消留档；约定激活后改方向用 recontract。

恢复用 advance --compact：已展示组原样返回（结构门板子重新按同一 round 生成，哈希一致），未生成组恢复同一任务；先核实原执行者，仍在运行时等待，不重复派工。不要求重选，不自动采纳历史否决。

完整约定按 [入口选择](#入口选择) 操作。一旦派过门任务，opening --file 按 creation 拒绝，不静默丢弃已见选择；此时用 recontract。

## 约定

默认 opening_contract 随 world_model 起草，读取闭合选择和同轮候选世界；世界先通过 world_review，候选约定再进入独立 contract_review。单独下发的 opening_contract 读取其冻结的已核验世界。逐门 value 的字段保留（主角门存为 protagonist_setup，关系门映射到 relationships，机制允许范围由世界门给出）。选定承诺、基调、视角、体量、世界前提、主角、关系、推进、终局、母题、书名和文风不得改变；卷职责、名称和初始化细节由系统推导并独立核验。对齐字段从同一字段声明派生，不通过合并整份 value 覆盖其他门。

约定还须保留所选禁区（red_lines 是逐门所选禁区的超集），并在 entities 中保留所选主角，kind 为 person，id 与 name 与 protagonist_setup 一致，否则核验报 opening_alignment。result.template.json 由约定字段表派生，含全部对齐字段（含 title 与空 entities 骨架）；结构校验拒绝未知字段，因此模板不接受的字段不要提交。`tone`/`theme`/`pov` 自 opening/2 起由作者选定：模板里有这三个字段，逐门开书必须逐字保留；自备约定（`init --contract`）可以不带它们，此时项目按不带视角清单的版本核验，不会被追溯要求。书名自 opening/2 起也由作者在最后一门选定，约定工人不再代拟。
