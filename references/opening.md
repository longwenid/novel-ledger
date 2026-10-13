# 零输入逐门开书

何时读：没有想法也要开书、逐门选择、换方案或恢复开书。讨论技能不表示启动真实小说。

## 用户体验

用户只需表示要开书。不要要求先写一句话、提供题材、起名或填设定表。无 --contract 的 init 创建逐门项目，advance 即派 opening_options。

未指定项目路径时，主控在当前工作区选择独立小说目录，告知保存位置；不要覆盖已有项目，也不把选择目录变成必答门。技能目录只保存技能，不放正文项目。

每次只展示当前门名、进度和 2～3 个具体方案。方案说清主要内容、推进差异和代价，用户只选 A/B/C 即可；支持“换一组”和“返回某门”。不把字段、哈希和命令展示给用户。真实选择到来才推进，预选和超时不代表选择。

八门权威顺序在 creation.GATES：题材体验 → 篇幅分卷 → 主角身份欲望底线 → 推进与对抗 → 核心关系 → 世界前提与机制 → 工作终局 → 文风节奏。第一门由系统脑暴，后续依据已选方向生成。选择期间只展开足以决策的摘要，全部门结束后才创建丰富世界。

方案应在行动、利益、因果或阅读体验上有实质差异。换组保留否决理由并切换 creative_lens，可用限制、认知差、规则推演、代价、关系绑定、终局回扣；不为新奇推翻已选无外挂或生活流等约束。

## 系统执行

1. init 不需要 source 或 contract；advance 后派新空历史方案 Worker，只给 task_path 和当前门角色。
2. Worker 完整读 opening_choices/opening_rejections/opening_basis 和 payload，生成当前门方案并 submit。
3. advance 得 await_choice，展示原组并等待用户。用户选择后执行 choose 保存原话，再 advance 下一门。系统不能替用户选择。
4. 最后一门 choose 返回 next=world_model；立即 advance 派世界设计者，不重复询问是否开始创建世界。
5. 世界独立核验通过后，系统整理完整约定并独立核验，world_ready 自动生成 world.html/world.json 并交付绝对路径；不再要求作者填表或批准已选设定。

已有明确正文授权时，世界交付后按原话调用 run；没有授权时在世界交付结束，不把选完设定等同于写完整本。

## 操作与恢复

```bash
python3 "$ROOT/scripts/novel.py" --project "$PROJECT" init
python3 "$ROOT/scripts/novel.py" --project "$PROJECT" advance
python3 "$ROOT/scripts/novel.py" --project "$PROJECT" choose --option A --board 当前展示哈希 --source 'A'
python3 "$ROOT/scripts/novel.py" --project "$PROJECT" regroup --board 当前展示哈希 --reason '换一组'
python3 "$ROOT/scripts/novel.py" --project "$PROJECT" back --gate scale --reason '返回体量重选'
```

board 哈希由主控从展示响应恢复，用户不需知道。选择绑定准确展示版本，旧组编号不能套到新门。保存各组、选择、否决和原话；回退保留前门，后续依赖选择归档后重选。世界构建期间仍可回退，旧任务取消留档；约定激活后改方向用 recontract。

恢复用 advance：已展示组原样返回，未生成组恢复同一任务；不要求重选，不自动采纳历史否决。

已有完整约定时按项目状态选入口：项目还没开始时用 `init --contract 约定.json`；已经 `init` 但还没 advance（没有派过任何门任务）可以用 `opening --file 约定.json --source 原话`，导入后逐门选择状态被清除，流程直接进入约定核验；一旦派过门任务或作者已看过方案，`opening --file` 按 creation 错误拒绝，不静默忽略，也不替他丢掉已见选择，此时用 `recontract --file` 改约。已有生效约定时同样用 recontract，先独立核验再重新规划。

## 方案回执

data={gate,options:[{id,title,premise,driver,tradeoff,fit_reason,value}]}，每门 2～3 个，不预填作者决定。

| gate | value |
|---|---|
| genre | genre/reader_promise/red_lines 数组/allow_special_mechanism 布尔 |
| scale | word_range/chapter_min/chapter_max/chapter_aim/volume_count |
| protagonist | id/name/identity/desire/limit |
| engine | story_engine/opposition |
| relationships | relationships 具体关系数组，独行可为空 |
| world | world_premise、mechanism={mode:none或bounded,principle,cost,limits:数组} |
| ending | ending |
| voice | voice/style_traits 数组 |

opening_contract 读取闭合选择及核验世界，产出协议中的完整约定。逐门 value 的字段保留，主角完整选择另存 protagonist_setup，机制允许范围保留 allow_special_mechanism。选定承诺、体量、主角、推进、关系、前提、终局和文风不得改变；卷职责、名称和初始化细节由系统推导并独立核验。

约定还须保留所选禁区（red_lines 是逐门所选禁区的超集），并在 entities 中保留所选主角，kind 为 person，id 与 name 与 protagonist_setup 一致，否则核验报 opening_alignment。result.template.json 由约定字段表派生，含全部对齐字段（含 title 与空 entities 骨架）；结构校验拒绝未知字段，因此模板不接受的字段不要提交。
