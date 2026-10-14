# 零输入逐门开书

何时读：没有想法也要开书、逐门选择、换方案或恢复开书。讨论技能不表示启动真实小说。

## 用户体验

用户只需表示要开书。不要要求先写一句话、提供题材、起名或填设定表。无 --contract 的 init 创建逐门项目，advance 即派 opening_options。

未指定项目路径时，主控在当前工作区选择独立小说目录，告知保存位置；不要覆盖已有项目，也不把选择目录变成必答门。技能目录只保存技能，不放正文项目。

每次只展示当前门名、进度和 2～3 个具体方案。方案说清主要内容、推进差异和代价，用户只选 A/B/C 即可；支持“换一组”和“返回某门”。不把字段、哈希和命令展示给用户。真实选择到来才推进，预选和超时不代表选择。方案 id 由方案 Worker 自定（不一定是 A/B/C），主控执行 choose 时用展示组里的真实 id；传错 id 的拒绝会带 `valid_options` 列表。

## 十门权威顺序

权威顺序在 `creation.GATES_V2`，一门只问一件事：

| # | 门 | 类型 | 作者要回答的一件事 | value |
|---|---|---|---|---|
| 1 | `genre` 题材、承诺与基调 | 创意门 | 写给谁、是什么故事、给读者什么感觉 | genre/reader_promise/tone |
| 2 | `pov` 叙述视角与人称 | 创意门 | 谁在讲、能看多远 | pov |
| 3 | `scale` 体量与分卷 | **结构门（引擎即时）** | 这本书多大、多少卷、每章多长 | tier/word_range/chapter_min/chapter_max/chapter_aim/volume_count/chapters/chapter_window |
| 4 | `world` 世界前提、机制与禁区 | 创意门 | 世界是什么样、有无特殊机制及其代价、绝不写什么 | world_premise、mechanism{mode,principle,cost,limits}、red_lines、allow_special_mechanism |
| 5 | `protagonist` 主角身份、欲望与底线 | 创意门 | 谁、要什么、底线在哪 | id/name/identity/desire/limit |
| 6 | `relationships` 核心关系与人物张力 | 创意门 | 身边与对面有谁、张力在哪 | relationships（至少一条） |
| 7 | `engine` 持续推进与主要对抗 | 创意门 | 靠什么持续、谁在挡 | story_engine/opposition |
| 8 | `ending` 终局与母题 | 创意门 | 落在哪里、这本书关于什么 | ending/theme |
| 9 | `voice` 文风与节奏 | 创意门 | 什么腔调、什么节奏 | voice/style_traits |
| 10 | `title` 书名 | 创意门 | 叫什么 | title |

顺序不是任意的：

- **视角排在第三门之前**。所有创意门都要给 2～3 个可落笔的画面样本，而画面必然带着人称。视角若排在最后，作者是在没定人称的情况下评估样本，选完再改人称，读到的质感就对不上。视角还先行于对抗与终局：限知决定哪些场面根本不能被叙述。
- **世界先于人物与推进**。机制与代价结构确定后，主角的欲望底线才在它的代价来源之内成立，主要对抗也取自世界的力量与关系。
- **关系先于推进**。对抗常直接来自关系网里的人；关系单独成门，也让“主角不动、只换关系网”这种改法不必推翻前面的选择（返回只归档关系之后的门）。
- **书名最后**。它是所有已选方向里最依赖上下文的一门，读完终局与文风再命名。
- 结构与内容交错：第 3 门由引擎即时给定（见下节），不打断等待。

派工预算：十门中九门是创意门（1、2、4、5、6、7、8、9、10），**9 次派工 + 10 次作者选择**；体量门当次给定、不派工、不等待。相比如下取舍是刻意的：门更细（原来一个门塞四件事），单门只决定一件事，作者对任一门不满意时返回的代价更小；代价是多几次等待。若确实要压缩，最省的一刀是把书名并回终局门（少一次派工），其次是把关系并回主角门。

每门方案的交付形状仍由 [创意工具箱](hatch.md) 与任务材料的 `brief` 给出；`pov` 与 `title` 这类单一决定门，`brief` 里另有一段“本门的交付要求”：视角门的每个 `scene` 必须用该方案的人称写出来（让作者读到人称的实际效果，而不是读解释），书名门必须给真正可用的候选名，不得交占位符。

`creation.GATES_V1` 保留原八门。项目自己的 creation 状态写明协议版本：`novel-ledger.creation/1` 的既有项目与在途开书继续走八门、旧 value 规则与旧对齐，`init` 新建项目为 `novel-ledger.creation/2`。不要替旧项目重排门序。

## 结构门（体量与分卷）

档位唯一权威是 `contracts.SCALE_TIERS`：五档阶梯，每档给出总字数区间、章幅上下限与目标、卷数、推荐总章数与该档可写完的章数区间。板子取阶梯上连续三档，默认窗口为“精简/标准/长篇”。

- 游标落到体量门时，主控直接把档位板写进展示状态并返回 await_choice：**没有任务、没有 Worker、没有等待**。
- 只向作者展示档位名、总字数区间、卷数、每章字数与章数，以及这一档比相邻档多买到什么、少买到什么。**不要求 pitch 与 scene**，也不要求 Worker 编造数字；方案回执的 pitch/scene/driver 硬要求只适用于创意门。
- 换一组沿阶梯滑动窗口（例如“标准/长篇/超长”），并照常保存否决。
- 档位数字与推荐章数由 `creation.validate_value` 校验；约定阶段的章数必须落在该档可写完区间内，否则报 `opening_alignment`。测试逐档证明每个档位都能写出一份通过 `planning.validate_contract` 的约定。

## 方案回执（创意门）

data={gate,options:[{id,title,pitch,scene,premise,driver,tradeoff,fit_reason,value}]}，每门 2～3 个，不预填作者决定。

- `pitch` 一句能记住的话（≤40字），`scene` 2～3 个可落笔的具体画面（谁在哪、手上是什么、正要做什么），两者都是硬要求：作者要看到能直接开写的场面，而不是概念。
- 透镜与方法**只用于构思，不得出现在给作者看的文本里**。`driver` 写这一版如何推进，`tradeoff` 写选它要放弃什么（与同组另外两案相比），`fit_reason` 写与已选方向的具体接口。写"某透镜落地/典型落法"会被 `opening_voice` 拒绝。
- 同组方案的推进方式不得同构（例如三案都以"以…为刻度推进"起句），会被 `opening_diversity` 拒绝。

必读材料只有拒绝记录：本门所需规则、本轮透镜与交付契约都写在任务材料的 `brief` 里；已选方向也在 brief 中，`opening_choices` 按需补读即可。上表即各门 `value` 字段的权威；结构门照抄不改数，单一决定门另有“本门的交付要求”一段。

## 系统执行

1. init 不需要 source 或 contract，自动生成 book.html，返回 book_view 的绝对路径；advance 后派新空历史方案 Worker，只给 task_path 和当前门角色。
2. Worker 完整读 opening_choices/opening_rejections/opening_basis 和 payload，生成当前门方案并 submit；结构门不接受方案回执（`opening_system`）。
3. advance 得 await_choice，展示原组并等待用户。用户选择后执行 choose 保存原话，再 advance 下一门。系统不能替用户选择。
4. 最后一门 choose 返回 next=world_model；立即 advance 派世界设计者，不重复询问是否开始创建世界。
5. 世界独立核验通过后，系统整理完整约定并独立核验，自动更新 book.html 并生成 world.json。新约定默认继续设计并独立核验全书骨架、各卷脑暴方案及所有卷的完整逐章卷纲，分批完成后以 outline_ready 交付；没有正文授权不派章计划或执笔。旧约定 volume_outline 未启用时仍返回 world_ready。world_view.html_path 指向 book.html；页面生成失败保留已核验内容，重复 advance 可重试。逐章说明与字段见 [叙事推进](narrative.md)。

已有明确正文授权时，世界交付后按原话调用 run；没有授权时在世界交付结束，不把选完设定等同于写完整本。

## 操作与恢复

已有部分完整门要求可在 init 后、未展示当前方案且无 pending 时用 `intake --file 要求.json --source 作者原话` 保存。文件如 `{"ending":{"ending":"作者指定结局。","theme":"母题。"},"title":{"title":"书名"}}`：键是**门 ID**，值是那一门的完整 value；用约定字段名当键（例如 `theme`）会被拒绝并返回 `valid_gates`。门 ID 必须属于当前协议（`novel-ledger.creation/2` 用上表的十门，旧项目用原八门）。只保存作者已定的值，不替缺字段补造决定。后续自动跳过这些门，保留原话和版本；返回会归档受影响的后续门。展示当前方案时不能 intake（含结构门板子），先选择或 back。

```bash
python3 "$ROOT/scripts/novel.py" --project "$PROJECT" init
python3 "$ROOT/scripts/novel.py" --project "$PROJECT" advance
python3 "$ROOT/scripts/novel.py" --project "$PROJECT" choose --option A --board 当前展示哈希 --source 'A'
python3 "$ROOT/scripts/novel.py" --project "$PROJECT" regroup --board 当前展示哈希 --reason '换一组'
python3 "$ROOT/scripts/novel.py" --project "$PROJECT" back --gate scale --reason '返回体量重选'
```

board 哈希由主控从展示响应恢复，用户不需知道。选择绑定准确展示版本，旧组编号不能套到新门。保存各组、选择、否决和原话；回退保留前门，后续依赖选择归档后重选。世界构建期间仍可回退，旧任务取消留档；约定激活后改方向用 recontract。

恢复用 advance：已展示组原样返回（结构门板子重新按同一 round 生成，哈希一致），未生成组恢复同一任务；不要求重选，不自动采纳历史否决。

已有完整约定时按项目状态选入口：项目还没开始时用 `init --contract 约定.json`；已经 `init` 但还没 advance（没有派过任何门任务）可以用 `opening --file 约定.json --source 原话`，导入后逐门选择状态被清除，流程直接进入约定核验；一旦派过门任务或作者已看过方案，`opening --file` 按 creation 错误拒绝，不静默忽略，也不替他丢掉已见选择，此时用 `recontract --file` 改约。已有生效约定时同样用 recontract，先独立核验再重新规划。

## 约定

opening_contract 读取闭合选择及核验世界，产出协议中的完整约定。逐门 value 的字段保留（主角门存为 protagonist_setup，关系门映射到 relationships，机制允许范围由世界门给出）。选定承诺、基调、视角、体量、世界前提、主角、关系、推进、终局、母题、书名和文风不得改变；卷职责、名称和初始化细节由系统推导并独立核验。十门决定的正是同样的十八个对齐字段，只是分布更细。

约定还须保留所选禁区（red_lines 是逐门所选禁区的超集），并在 entities 中保留所选主角，kind 为 person，id 与 name 与 protagonist_setup 一致，否则核验报 opening_alignment。result.template.json 由约定字段表派生，含全部对齐字段（含 title 与空 entities 骨架）；结构校验拒绝未知字段，因此模板不接受的字段不要提交。`tone`/`theme`/`pov` 自 opening/2 起由作者选定：模板里有这三个字段，逐门开书必须逐字保留；自备约定（`init --contract`）可以不带它们，此时项目按不带视角清单的版本核验，不会被追溯要求。书名自 opening/2 起也由作者在最后一门选定，约定工人不再代拟。
