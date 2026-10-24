# 零输入逐门开书

何时读：没有想法也要开书、逐门选择、换方案或恢复开书。讨论技能不表示启动真实小说。

## 适用范围与决定权

作者决定方向，系统负责给出具体选项、保存来源和核验一致性。已有要求先整理保存，只询问真实缺口。本页维护门序、字段与操作协议；开书创意与方法统一见 [创意工具箱](hatch.md)。

## 入口选择

下表命令均使用 `python3 ROOT/scripts/novel.py --project PROJECT` 入口。先确认项目是否存在、是否已经派过门任务，不覆盖项目或要求作者重填已有设定。

| 当前情况 | 命令 | 结果与边界 |
|---|---|---|
| 新项目，无完整约定 | `init` | 进入逐门选择，已有部分要求再用 intake 保存。 |
| 新项目，已有完整约定 | `init --contract 约定.json --source 原话` | 采用已有约定，默认推进试章目标。 |
| 已 init，尚未派过门任务 | `opening --file 约定.json --source 原话` | 导入完整约定，清除逐门选择；约定经机械校验激活后进入卷纲。 |
| 已派过门任务或已有约定 | `recontract --file 约定.json --source 原话` | 保留旧记录，新约定经机械校验后激活，见 [暂停与修改](runtime.md#暂停与修改)。 |
| 未展示当前方案且无 pending，已有部分完整门要求 | `intake --file 要求.json --source 原话` | 按门 ID 保存已定值，后续跳过这些门；不替缺口补造决定。 |
| 已有项目续写或恢复 | `status`，再 `advance --compact` | 接回当前任务；执行身份与授权见 [运行](runtime.md)。 |

## 用户体验

用户只需表示要开书。不要要求先写一句话、提供题材、起名或填设定表。无 --contract 的 init 创建逐门项目，advance 即派 opening_options。

未指定项目路径时，主控在当前工作区选择独立小说目录，告知保存位置；不要覆盖已有项目，也不把选择目录变成必答门。技能目录只保存技能，不放正文项目。

板面在 `await_choice` 时由引擎物化为 `work/board.md`（返回里的 `board_card` 路径）：门名、进度、每个方案的 id 与全部作者可读字段、命名提示和固定操作。同轮还会物化 `work/question.json`（返回里的 `question_card` 路径）：可直接投给宿主提问组件的选项结构，label 用短标题、description 用 pitch（结构门用 premise）原文，**总数封顶 4 个**（常见提问组件的选项上限）——板面方案 + “换一组 / 自定义”，自定义输入由宿主的 Other/自由填答承担，不单列选项。主控把卡片内容原样交给作者——先在回复正文里贴出 board.md 的内容（或给出其文件链接），再用 question.json 的选项原样发起提问，**不自拟一句话摘要替换引擎文案**；不在 GBK 控制台读长 JSON，也不手工重排版。宿主选项数低于 question.json 时截到“换一组”为止，不许删板面方案来腾位。`advance --compact` 的返回只带门名、哈希与 option_ids，完整板面以 board.md 与 `work/last-advance.json` 为准。

每次只展示当前门名、进度和 2～3 个具体方案。方案说清主要内容、推进差异和代价，用户只选 A/B/C 即可；支持“换一组”和“返回某门”。不把字段、哈希和命令展示给用户。真实选择到来才推进，预选和超时不代表选择。方案 id 由生成方自定（不一定是 A/B/C），主控执行 choose 时用展示组里的真实 id；传错 id 的拒绝会带 `valid_options` 列表。

### 门任务由主干自执（默认，不再每门派子 agent）

门任务（`opening_options`，声明在 `contracts.CONTROLLER_STAGES`）默认由主干在同一会话内执行，保留作者选择与换组记录：

1. `advance --compact` 取任务与 `task_path`；
2. 读任务目录的 `brief.md`（任务定位卡，含当前门、字段与来源入口；`input.json` 是同一内容的 JSON 原文，不必重复读）；需要必读记录时直接 `read --task 任务ID`（该阶段对主控放行 read/recall，正文与审读阶段不在此列）。同一会话连跑多门时可豁免：上一门的 `read` 返回 `records_hash` 与本门相同、且任务卡未新增必读记录，跳过本次 read；
3. 从 `result.template.json` 复制起稿 `result.json`，只填 data（信封三字段不手写，`input_version` 报错会带 expected）；`check` 试算后 `submit`（回执 `session` 填主干自己的会话身份即可，门任务不绑定会话）；
4. 展示板面等作者选择（板面与提问的转发纪律见上）；「换一组」就 `regroup` 后重复——同一会话连续换组即是复用，作者在环防止锚定。

全部开书选择完成、进入 `world_model` 后，按冻结任务派工：世界、卷纲、章纲和正文是实际工作量所在，主干只保留目标、任务身份与治理动作。宿主确实无法内联时才退回逐门派工，并如实说明。

### 第一门的全类目

作者没给题材方向时，第一轮不抽三个冷样本：`contracts.GENRE_CATALOG` 提供十二个男频类目（玄幻、仙侠修真、都市异能、都市职场、历史权谋、科幻末世、悬疑探案、游戏电竞、武侠、军事战争、体育竞技、二次元轻小说），引擎在第一门派工时把全目录物化为任务目录的 `catalog.md`（compact 返回的 `catalog_path`）。**铺目录是正文文本步骤，不是提问选项**：主控把 catalog.md 原文贴进对话（或给链接）让作者看到全部十二个类目，提问组件只用来收方向——选项可挑最可能的几个（≤宿主上限），其余类目与自定义靠宿主的 Other/自由填答。实测一次运行把四个类目塞进选项就当成全部目录，八个类目从作者视野里消失。收一句方向或自定义后，**回执仍按 offer 协议交 2～3 个方案**——在该类目内深化，不把全目录当成回执选项。作者已给方向时跳过铺目录直接出案（catalog.md 忽略即可）。

### 主角门的命名纪律

起名方法见 [名字与称呼](hatch.md#名字与称呼)。套路组合会在板面上以 `name_warnings` 提示（advisory，只警不拦，作者坚持则以作者为准）。**硬禁某个字**用字面规则：`lexical --file {"forbidden_name_chars": ["砚"]} --source 作者原话`，此后 opening_options/world_model/章计划的人名字段都会机械拦截该字。

### 换组纪律

作者要求换组时用 `regroup` 保存否决原话，读取 `opening_rejections` 后按 [换组方法](hatch.md#换组) 生成；返回此前决定用 `back`，不以换组替代回退。

## 门序与字段归属

项目使用 `creation.GATES`（`opening/6`），共 **13 门**。世界与格局先于主角来历确定，避免整套世界围着一个局部身份生长。字段以当前任务卡与模板为准，详细约束见 [协议](protocol.md)。

| # | 门 | 决定什么 |
|---|---|---|
| 1 | `genre` 题材与阅读承诺 | 类型、读者期待与基调；暂不锁死职业与局部事件 |
| 2 | `premise` 核心设想与世界命题 | 核心命题、历史推动力、主角立场与矛盾来源；暂不锁定姓名职业 |
| 3 | `voice` 叙述视角与阅读质地 | 人称、视角边界与语感；后续 scene 沿用所选人称 |
| 4 | `scale` 体量与分卷 | 引擎即时给档位；决定本书展开多少，不决定世界有多大 |
| 5 | `world` 世界架构 | 空间、历史、文明、贯穿矛盾、终极谜题，以及由此生长的机制、位阶与资源 |
| 6 | `ladder` 格局路径与终局视野 | 从终局问题倒推阶段；行动能力、认知和责任如何变化，哪些旧人旧事持续有效 |
| 7 | `origin` 主角来历与世界联系 | 魂穿、身穿、本土或其他；带来什么、谁会起疑、起初知道多少 |
| 8 | `edge` 核心优势与成长线 | 介入世界矛盾的优势、来源、成长条件、代价与上限 |
| 9 | `protagonist` 主角处境与底线 | 姓名、身份、私人欲望与会付出代价的底线 |
| 10 | `relationships` 人物关系与立场 | 各自目标与所属秩序，合作和分歧的来源 |
| 11 | `opposition` 多方对抗与持续冲突 | 眼前对手如何连到利益网络与根本矛盾，胜利如何改变局面 |
| 12 | `payoff` 阶段兑现与终局回应 | 早期兑现物与期限、阶段回报、终局行动及人的去向 |
| 13 | `title` 书名 | 独特意象或清晰卖点；短名、长名均可 |

世界门新增 `architecture`，五项完整保存在约定 `world_architecture` 中，并逐字绑定到世界模型的指定字段，见 [世界架构绑定](world.md#世界架构绑定)。构思方法见 [从处境或变化推演后果](hatch.md#从处境或变化推演后果)。

格局的 `stage` 使用能落成世界记录的名字；`new_rule` 说明揭开了什么、谁维持该规则，`cost` 说明新责任与代价。各级的尺度、成长类型与终局等级遵守协议。

后续每门必读完整的已选记录 `opening_choices`，从任务卡给出的来源入口读取。想改已选脑洞或世界须返回对应门，后续依赖重选。世界与约定阶段机械检查逐字承接，卷纲、章纲在原有任务内完成因果、揭示顺序及状态链核验，不新增独立校验子 agent。机械通过不代表脑洞原创或文学质量达标。

**旧开书协议不再支持**：声明 `creation/1`～`creation/5` 的项目在读取时被明确拒绝（错误说明以当前协议重开），不迁移、不按新门重读旧选择。自备约定（`init --contract`）不经门序核验，可省略当前约定中非必填的结构化开书决定。

无预填、换组或回退时，为 12 次创意方案生成、1 次引擎结构板与 13 次作者选择。已有要求跳过相应门；实际次数随操作变化。生成方法和换组原则见 [创意工具箱](hatch.md)。

开书项目保存 `novel-ledger.creation/6`（唯一支持的协议）；数据库布局为 `novel-ledger/5`，两者独立。

## 结构门（体量与分卷）

档位唯一权威是 `contracts.SCALE_TIERS`：六档阶梯（微型 / 短篇 / 精简 / 标准 / 长篇 / 超长），每档给出总字数区间、章幅上下限与目标、卷数、推荐总章数与该档可写完的章数区间。板子取阶梯上连续三档，默认窗口为“标准/长篇/超长”（男频连载常见体量，`SCALE_DEFAULT_WINDOW=3`）；短篇与微型换一组即可取到。**微型档的章窗从两三章的短篇一直到十七回的微型连载都算（`chapter_window [2, 19]`，推荐仍是 17 回）**：作者的"三章完本"这类要求必须有档位可以落地，否则契约层可以改到该体量，而完本审计仍会以"章数与档位不相容"拒绝这本已经写完的书。

- 游标落到体量门时，主控直接把档位板写进展示状态并返回 await_choice：**没有任务、没有 Worker、没有等待**。
- 只向作者展示档位名、总字数区间、卷数、每章字数与章数，以及这一档比相邻档多买到什么、少买到什么。**不要求 pitch 与 scene**，也不要求 Worker 编造数字；方案回执的 pitch/scene/driver 硬要求只适用于创意门。
- 换一组沿阶梯滑动窗口（例如“标准/长篇/超长”），并照常保存否决。作者直接给了目标体量或档位时用 `choose --tier t0～t5` 一次到位：窗口自动滑到该档再落选择，不必换组重问。
- 窗口只筛选展示范围；每档的比较说明始终依据完整阶梯，同一档位换到其他窗口仍保持相同说明。只有完整阶梯的最后一档才称为最大档。
- 档位数字与推荐章数由 `creation.validate_value` 校验；约定阶段的章数必须落在该档可写完区间内，否则报 `opening_alignment`。测试逐档证明每个档位都能写出一份通过 `planning.validate_contract` 的约定。

## 方案回执（创意门）

data={gate,options:[{id,title,pitch,scene,premise,driver,tradeoff,fit_reason,value}]}，每门 2～3 个，不预填作者决定。方案取舍与构思方法见 [创意工具箱](hatch.md#设定生成方法)。

- `pitch` 一句能记住的话（≤40字），`scene` 2～3 个可落笔的具体画面（谁在哪、手上是什么、正要做什么），两者都是硬要求：作者要看到能直接开写的场面，而不是概念。
- 透镜与方法**只用于构思，不得出现在给作者看的文本里**。`driver` 写这一版如何推进，`tradeoff` 写选它要放弃什么（与同组另外两案相比），`fit_reason` 写与已选方向的具体接口。写"某透镜落地/典型落法"会被 `opening_voice` 拒绝。
- 同组方案的推进方式不得同构（例如三案都以"以…为刻度推进"起句），会被 `opening_diversity` 拒绝。
- **当期参照**：候选的机制、节奏与审美锚定开书上下文带来的最新市场快照（当期在跑什么、什么已饱和），不引用执行者记忆里的旧热点；没有快照可用时如实按"无当期证据"构思并在取舍里注明，不伪装已核对当期。紧跟主流指的是当期周期的机制与审美，不是供给已饱和的旧热点换皮。
- **俗套命中自审**：premise / protagonist / opposition 门的每个候选，构思时先自审——最像的三本现有作品是什么、本书有什么它们没有的；差异是机制级的（怎么涨、怎么限、怎么兑现、读者在哪里动感情）才可入选，只是外衣（换朝代、换器物、换地名）就重出该候选。化石组合默认命中：遗孤血统＋残缺信物＋器物认主、无代价的圣人式主角底线、逐层升高的四层敌人梯。

程序对每份方案回执按去除首尾空白后的字符数执行 pitch≤40、scene 最多 3 条、每条 scene ≥12 字；这是唯一规则，没有旧任务的宽松解释。

**结构字段以当前门任务卡的 value 规则为准，不凭记忆猜格式**：stance/dark_side/family/ladder.terminal 等是枚举（合法值写在各门规则里），mechanism（mode/principle/cost/limits）、resource（name/source/allocator）、architecture（space/history/civilizations/conflict/mystery）、ladder.scale（opening/terminal/unchanged）、payoff.plan（ways/cadence/hooks）与 payoff.anchor（deliverable/deadline_chapter，纯数字章号）是结构体。生成方案前先读当前门 brief 的 value 规则一行，再落笔；`check` 的 findings 会逐字段指出违规与合法值，按它修正，不要连续盲试。

创意门执行者（默认主干，派工时为 Worker）先读 task.json、任务卡 `brief.md` 与 required 中的完整记录，含 opening_choices 与 opening_rejections。创意说明只读 [创意工具箱](hatch.md)；同一主干跨门已读且版本未变可复用。完整回执示例见 `assets/opening-options.example.json`；单一决定门按任务卡的字段边界交付。结构门由主干展示引擎档位板，不派 Worker 或提交方案回执。

`value` 只接受本门负责的字段，任务卡会列出允许字段。携带其他门的字段或未知字段按 `opening_option` 拒绝，详情给出 `allowed_fields`、`unknown_fields` 和修正出口；例如书名门不能附带 `pov` 改写已选视角。intake 使用相同边界，形成约定时还会再次校验闭合选择；改此前决定须 back 返回对应门。

## 系统执行

以下为默认路径；实际派工始终按 advance 与冻结任务执行，不按流程表手造下一任务。

| 阶段 | 执行者与动作 | 交接依据 |
|---|---|---|
| 初始化 | 主干 init，随后 advance --compact。 | 自动生成轻量 book.html 入口，返回 book_view 的绝对路径与预览启动命令；无设定时不要求 source 或 contract。 |
| 创意门 | **默认主干自执**（同一会话读 task.json、brief.md 与 required，生成方案并 submit，不派子 agent）；宿主无法内联时才派新空历史 Worker。 | 主干自执无交接等待；派工路径由主干等待结束再 --after 核实提交，委派只给任务路径和当前角色。 |
| 结构门 | 引擎即时返回档位板，主干展示。 | await_choice，无任务或 Worker；方案回执按 opening_system 拒绝。 |
| 作者选择 | 展示当前原组，选择后 choose 保存原话，再 advance。 | 系统不代选；换组和返回保留记录。 |
| 世界与约定起草 | 最后一门 choose 返回 next=world_model，立即 advance 派工。 | 默认任务同时包含 world_model 与 opening_contract（payload.also），回执为世界字段加 contract；以任务 stages、payload.also 和模板为准。 |
| 机械校验与激活 | 世界与约定**不再有独立核验阶段**：提交时由引擎校验字段、links 引用、选择一致性与约定对齐（含与所选世界的 world_rules 逐字一致），以及门里声明的位阶/硬通货/格局阶梯在世界模型里的**逐字绑定**（v6 加上世界架构）（见 [世界模型](world.md#三条逐字绑定)）；通过即在同一事务激活约定；失败保持当前任务，按具体错误修正后重交。 | 校验只证明字段、引用和声明一致，不证明世界承载或因果成立；判断留给卷纲与章纲的状态链，以及作者抽读。 |
| 卷纲 | 约定生效后按 `advance` 派 `volume_outline`：默认 `scope=all`，一次交全部卷、每卷 2000–3000 汉字（目标 2500）；`scope=rolling` 时进入该卷前交该卷。v5 及之后的项目每卷还要给 `stage`：**逐字取已选格局阶梯里的一级，且按卷序只升不降**（字段与校验见 [协议](protocol.md) 与 [世界模型](world.md#三条逐字绑定)）。t0/t1 由 `merge_chapter_outline` 把本卷卷纲与章纲合成一次派工。 | 形状、校验与覆盖见 [叙事推进](narrative.md#卷纲)。 |
| 章纲 | 每卷进入前派一次 `chapter_outline`：该卷每章极简章纲（资源/位置/知情/时钟/人物/情节增量与 enter/exit），提交时按卷内状态链逐章模拟。 | 漂移字段与核算见 [叙事推进](narrative.md#章纲)。 |
| 交付 | outline_ready 按实际卷纲覆盖交付；卷纲与章纲为必选阶段。 | world_view.html_path 指向统一 book.html，另交 world.json 的绝对路径；视图失败可 advance 重建。 |

已有明确正文授权时，开书交付后按原话调用 run；没有授权时在 outline_ready/world_ready 停止，不把选完设定等同于写完整本。

后续世界、约定和卷纲任务同样等待子 agent 结束，再用 --after 核实提交；会话恢复及完整动作分支见 [运行](runtime.md)。

## 操作与恢复

已有部分完整门要求可在 init 后、未展示当前方案且无 pending 时用 `intake --file 要求.json --source 作者原话` 保存。文件如 `{"title":{"title":"作者已定书名"},"scale":{"tier":"t0"}}`：键是**门 ID**，值是那一门的完整 value；用约定字段名当键（例如 `theme`）会被拒绝并返回 `valid_gates`。结构门只需给档位 ID（`t0`～`t5`，`t0` 为五万字级的微型档），引擎补齐已证明的数字——作者不必从引擎里抄算术，手改过的数字也不会被静默修正。门 ID 必须属于当前 creation 协议；新项目的 `novel-ledger.creation/6` 使用上表十三门（`premise` 承担核心设想，`origin` 承担主角来历，`world` 承担世界架构、位阶与硬通货，`ladder` 承担格局尺度与阶梯，`payoff` 承担终局、母题与主题锚点，`edge` 承担核心优势）。只保存作者已定的值，不替缺字段补造决定。后续自动跳过这些门，保留原话和版本；返回会归档受影响的后续门。展示当前方案时不能 intake（含结构门板子），先选择或 back。

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

默认 opening_contract 随 world_model 起草，读取闭合选择和同轮候选世界；候选世界与候选约定由引擎按同一套机械校验在提交时判定（字段、links 引用、与各门选择逐字一致），通过即原子激活，**没有独立核验阶段**。单独下发的 opening_contract 读取其冻结的已核验世界。逐门 value 的字段保留（主角门存为 protagonist_setup，关系门映射到 relationships，机制允许范围由世界门给出）。选定承诺、基调、核心设想、主角来历、视角、体量、世界架构、位阶与硬通货、格局尺度与升格阶梯、主角、关系、推进、终局、主题锚点、母题、书名和文风不得改变；卷职责、名称和初始化细节由系统推导，并在卷纲提交时与 `contract.volumes` 一一比对。对齐字段从同一字段声明派生，不通过合并整份 value 覆盖其他门。

约定还须保留所选禁区（red_lines 是逐门所选禁区的超集），并在 entities 中保留所选主角，kind 为 person，id 与 name 与 protagonist_setup 一致，否则核验报 opening_alignment。result.template.json 由约定字段表派生，含全部对齐字段（含 title 与空 entities 骨架）；结构校验拒绝未知字段，因此模板不接受的字段不要提交。`tone`/`theme`/`pov` 分属题材门（genre）、兑现门（payoff）与视角门（voice）选定：模板里有这三个字段，逐门开书必须逐字保留；自备约定（`init --contract`）可以不带它们，不追溯要求补选。书名由作者在最后一门选定，约定工人不再代拟。
