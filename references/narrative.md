# 叙事推进与长篇上下文

何时读：写卷纲、写章纲、执笔自比、漂移被拒绝和长篇上下文补读。只把实际正文与机械核算结果写入事实，不把未来设计改称既成事实。

## 适用范围与能力要求

本文维护卷纲、章纲、卷内状态链、漂移核算与历史补读的接口规则，字段形状以当前任务模板和引擎校验为准。narrative_tracking 默认 true；显式关闭时章纲的 `plot.nodes`/`plot.threads` 可以为空，但**资源/位置/知情/时钟/人物增量仍然必需**。

| 当前任务 | 读取位置 |
|---|---|
| 卷纲、开书覆盖范围 | [卷纲](#卷纲) |
| 章纲、漂移字段、状态链被拒 | [章纲](#章纲)、[卷内状态链](#卷内状态链与校验) |
| 执笔自比、漂移核算 | [执笔自比与引擎核算](#执笔自比与引擎核算) |
| 篇幅、上下文材料、必读状态 | [篇幅与上下文](#篇幅与上下文) |
| 场景来源、阅读关联、依赖声明 | [场景依赖与任务材料](#场景依赖与任务材料) |
| 需要早期原文或事件 | [历史补读](#历史补读) |

## 卷纲

### 参数与范围

新建/明确改约默认 `volume_outline={scope:all,words:1000,tolerance:100}`：`words` 是**每卷**汉字数，`tolerance` 是允许偏差，`scope` 为 all（一次交全部卷）或 rolling（进入该卷前交该卷）。空对象 `{}` 表示明确关闭卷纲。字数用工程统一的汉字计数，标点和拉丁字符不计。字数合格不证明因果、人物选择或阅读作用成立。

**t0/t1 有形状合并**：`PIPELINE_SHAPES` 只保留 `merge_chapter_outline`（t0/t1 为 true），让“本卷卷纲 + 该卷章纲”由**同一次派工、同一份回执**交付，两个契约各自校验同一份回执；其余档位分两次派工。

### 回执形状

```json
{"volumes": [{
  "id": "v1",
  "purpose": "卷职责，≤60 汉字",
  "arc": "开局处境→关键转折→卷末局面，约 250 汉字",
  "turns": [{"at": "卷中|卷尾|第N章附近", "turn": "转折内容"}],
  "climax": "卷末高潮与兑现物",
  "nodes": [{"id":"n1","kind":"main|side|hidden","purpose":"…","ending_condition":"…","required":true,"window":[1,25]}],
  "threads": [{"id":"line1","kind":"main|side|hidden","purpose":"…","ending_condition":"…","required":true}],
  "resources": [{"key":"…","from":0,"to":12,"reason":"本卷资源大势"}],
  "places": [{"entity":"hero","from":"…","to":"…","reason":"…"}],
  "characters": [{"entity":"hero","from":"…","to":"…","reason":"…"}],
  "knowledge": [{"who":"hero","topic":"…","from":null,"to":"suspected","reason":"…"}],
  "clock": {"advance_days": 30},
  "exit_state": "卷末必须达到的状态：资源/位置/人物/知情/线路各一句"
}]}
```

- `id` 与 `contract.volumes` 一一对应且顺序一致；`purpose` 是卷职责。
- `nodes`/`threads` **按卷登记**，id 全书唯一、不覆盖已批准 id；跨卷线路用 `continues: true` 标记（不再有全书线路登记阶段）。
- `resources`/`places`/`characters`/`knowledge` 是本卷大势，key/entity 必须存在于世界模型或既有状态；`window` 落在本卷章号区间。
- `exit_state` 必须非空：卷末闭合由它逐项验收，容差为 0。

### 校验与失败

提交时引擎机械校验：卷 id 与 `contract.volumes` 一一对应且顺序一致；每卷汉字数落在 `words±tolerance`；node/thread id 全书唯一且不覆盖已批准 id；`resources/places/knowledge/characters` 引用的 key/entity 存在；`window` 落在本卷章号区间；`exit_state` 非空。任一项失败 → 提交被拒（`design_drift`），修复走既有 `repair` 预算，**不新增阶段**。

卷纲没有脑暴选案与 selection_reason，也没有独立的卷纲审查者：它提交时就机械判定，文学层面的推进设计没有人独立复核。

## 章纲

### 参数与范围

`chapter_outline={scope:'volume',words:150,tolerance:60}`：`words` 是**每章 synopsis** 的汉字数，`scope` 为 volume（本卷）或 all。每卷 1 次，在进入该卷前派。

### 回执形状

```json
{"volume": "v1", "chapters": [{
  "chapter": 1,
  "synopsis": "行动、阻力、选择、代价、结果、对下一章的推动（words±tolerance 汉字）",
  "plot": {
    "beat": "本章情节变化一句话",
    "nodes": [{"node":"n1","after":"seeded|advanced|resolved","outcome":"…"}],
    "threads": [{"thread":"line1","after":"active|dormant|resolved","reason":"…"}]
  },
  "resources": [{"key":"…","from":0,"to":3,"reason":"…"}],
  "places": [{"entity":"hero","from":"青云城","to":"落霞谷","reason":"…"}],
  "knowledge": [{"who":"hero","topic":"…","from":null,"to":"hinted|suspected|misled|confirmed|retracted","reason":"…"}],
  "characters": [{"entity":"hero","from":null,"to":{"desire":"…","stance":"…","relationship_focus":"…"},"choice":"…","cost":"…"}],
  "clock": {"advance_days": 1},
  "enter": [{"kind":"resources|places|knowledge|clock|character|node","key":"…","expected":0}],
  "exit":  [{"kind":"resources|places|knowledge|clock|character|node","key":"…","expected":3}],
  "disclosures": [{"topic":"…","after":"hinted"}],
  "world_refs": ["geography:luoxia"],
  "new_entities": [{"id":"…","kind":"character|place|item","name":"…","role":"…","desire":"…","limit":"…","knowledge_boundary":"…"}],
  "hook_refs": [], "reader_refs": [], "history_refs": [],
  "scenes": [], "pacing": {}
}]}
```

- **必需**：`chapter` `synopsis` `plot.beat` `enter` `exit` `world_refs`。四个增量数组（`resources` `places` `knowledge` `characters`）**可以空，但不得省略**——空数组等于声明“本章没有这类变化”，本身就是承诺。
- `scenes`/`pacing` 可选，保留工作台兼容；`hook_refs`/`reader_refs`/`history_refs` 指出本章要承接的旧承诺、旧认知与历史断言。
- **已知边界（v2）**：承诺（伏笔）只有承接没有登记——章纲能引用 `hook_refs`，但没有任何阶段产生新的 hook 事件，因此 `state.hooks` 在 v2 新书里是空集，完本的"未交代承诺"检查对这类项目是空检查。长线伏笔目前只能用 `plot.threads`（支线）表达：把承诺写进线路的 `purpose`/`ending_condition`，并在章纲的 `plot.threads` 里推进。要恢复逐条承诺账，需要下一版在章纲里增加 `hooks` 增量（登记/回收）并接到 `facts` 的 hook 事件。
- `new_entities` 取代原人物档案派工：新人物/地点/物品首次出现时，在本章内联给出档案字段；落地后按 id 引用，不再单独派一次档案任务。
- 每章 synopsis 写清行动、阻力、选择、代价、结果与对下一章的推动；引用真实世界记录与卷纲已登记的节点/线路。

### 卷内状态链与校验

1. 章号连续，恰好覆盖本卷 `[volume.first, volume.end]`（`scope=all` 时覆盖整卷）。
2. `synopsis` 汉字数落在 `words±tolerance`。
3. 每行增量形状合法：`from`/`to` 类型一致，`reason` 非空；resource 有 key 且存在于世界或既有状态；place 存在于世界 geography；node/thread 属于本卷卷纲已登记集合。
4. **enter/exit 冗余一致性**：`exit` 必须等于 `enter ⊕ 本章增量`（引擎自己算一遍比对）。任一侧缺项即漂移，拒绝。
5. **卷内状态链模拟**：从卷起始真实状态出发逐章应用增量，要求第 i 章 `enter` 恰好等于模拟到第 i 章开始的状态。模拟中拒绝：资源为负、`clock` 倒退、位置跳变到未登记地点、知情倒退（`retracted` 除外）、人物变化缺 `choice`/`cost`、同一 node 重复 `advanced` 或 resolved 后再推进、thread resolved 后重用。
6. **卷末闭合**：最后一章模拟结果必须满足本卷 `exit_state` 与卷纲声明的 `resources/places/knowledge/characters` 终值（容差 0）。

任一项失败 → `chapter_outline` 提交被拒（`design_drift`），修复走既有 `repair` 预算，不新增阶段。这条链解决的是“窗口内非节点状态不可前瞻”：后章的 `enter` 会撞上前章实际写出的状态，设计期就挡住资源/位置/知情漂移。

## 执笔自比与引擎核算

执笔回执交 `title`/`prose`/`summary`，外加 `drift_check` 与 `self_check`：

```json
{
  "title": "…", "prose": "…", "summary": "…",
  "drift_check": {
    "items": [{
      "kind": "resources|places|knowledge|characters|clock|node|thread",
      "key": "spirit-stone",
      "planned": {"from": 0, "to": 3},
      "actual":   {"from": 0, "to": 3},
      "status": "kept|deviated|skipped",
      "reason": "deviated/skipped 必填",
      "evidence": {"chapter": 1, "quote": "正文原文片段"}
    }],
    "unplanned": [{"kind": "knowledge", "key": "t2", "change": "…", "reason": "…"}],
    "verdict": "clean|deviated"
  },
  "self_check": "逐项说明本章与章纲的比对结论（不得为空）"
}
```

引擎核算（零派工）：

1. `items` 必须**恰好覆盖**本章纲的全部计划增量（kind+key 各一次，不多不少）；漏项/多项 → `drift_coverage` 拒绝。
2. 每条 `actual.from` 必须等于引擎投影的当前真实值（**不由写手自报前态**）；不等 → `drift_before` 拒绝。
3. `status=kept` 时 `actual.to` 必须等于 `planned.to`；`deviated`/`skipped` 必须给 `reason`，并写入 `book['design_drift']`。
4. `unplanned` 每项同样按第 2/3 条核算并登记；未登记的计划外变化会在下一次章纲校验（后章 `enter` 撞上）时暴露。
5. `evidence.quote` 必须是正文原文片段，走精确引文校验。
6. 通过后原子入账：复用事实、叙事与空间的既有机械判据（`facts.settle` / `narrative.prepare_events` / `spatial.settle`），事件来源是 `drift_check.items`。
7. 存在 `deviated`/`skipped` 时：本章照常入库（偏差已在自比中说明理由），引擎把该偏差加入 `book['design_drift']`，并在下一章派工前对该卷剩余章纲派一次 `chapter_outline`（payload 带 `repair=True` 与偏差清单）重排——这是删除 alignment 阶段后的替代路径。
8. 其余既有闸门保留：字数区间（`word_budget`）、`lint.draft_findings`、字面约定（`literal_policy`）、禁用名。

**代价说清楚**：`drift_check` 是执笔者自己写的，引擎只核对“计划增量是否齐全、前态是否等于投影、kept 是否等于计划值、偏差是否给了理由与引文”。它证明不了这一章好不好看、人物是否可信、节奏是否成立——**没有独立 agent 复核文学质量与阅读体验**。需要独立判断时只能人工抽读正文，或另行发起一次修订。

## 篇幅与上下文

跟踪项目允许长章短章共同满足总区间；chapter_max 可以高于全书平均上限。每章 word_budget 给出 minimum/maximum/aim，根据剩余章数和真实累计篇幅计算可完成范围；窄范围修订同时预留原样携带后缀的固定篇幅。字数不足或超范围的实际稿仍留档并消耗既有修复额度。无法达到目标时明确 `word_budget` 拒绝，修订前文或由作者改约，不降低目标。

执笔 story 读取本章章纲及直接前置，前置结果见投影状态，完整设计在 `design:*`。规划只选本卷未兑现的节点；当前状态供参与人、当前动机、近期成长和相关承诺使用，承诺按到期、显式 `hook_refs`、相关人物/物品及话题选择，完整状态保留 `complete_state`。世界采用直接关联；world_records 为可见材料，幕后真相保留可选 world_author_records，disclosure_boundary 明确本章允许披露与读者前态。

## 场景依赖与任务材料

新工作台任务采用 scene-identity/2：场景 ID 不绑定章号，跨章移动保留身份，独立的故事时间、作品理解与阅读关联见 [叙事工作台](workbench.md)。旧 `c章号:` 前缀是旧冻结身份协议；新任务未提供 ID 时引擎生成不透明 ID。

阅读关联由 reading-dependencies/1 能力及 `reading_schema` 标记冻结，旧任务中的同名字段不追补解释；没有标记时保守重读。相关字段、分级修订和创作记忆统一在工作台维护，不用事实 `dependency_coverage` 代替阅读关联覆盖。

章纲可声明 `dependency_coverage=partial|complete`，默认 partial。每场的 id、`reads=[{kind,key}]` 与 `depends_on=[场景ID]` 只能指向已登记前章或本章前场，禁止环及前向引用。complete 要求每场显式提供两份数组，无依赖给空数组；**v2 没有独立读者核对语义完整性**，引擎只核对声明形状与引用是否存在，遗漏只能靠后章 `enter` 撞上或作者抽读暴露。partial 在修订传播时保守扩大范围。

任务的 `scene_context` 携带本章章纲行与场景，inputs 给出显式输入和输入是否存在，plan_hash/state_hash 绑定准确来源。`scene_sources` 绑定前置已提交场景的章纲/正文/事件哈希与章节链；原文按本任务的 `recall --chapter` 补读。引用若只存在于未提交的重排章纲，派工拒绝并要求重新提交章纲。材料只是作者可用信息，人物实际知情仍以 `knowledge` 状态为准；未来设计不会变成事实。

## 历史补读

记忆检索可用 `recall --task ID --entity 人物ID`，或 `--node/--topic/--thread ID`：默认返回最近 5 个匹配章节的全部匹配证据；用 `--limit 1～20`、`--before 章号` 分页，再用 `--chapter N` 完整补读。新任务的可选 history_source 只冻结逐章不可变目录的入口及截至章号，查询由近到远读取所需页与事件，不每次重建全书摘要/事件索引。旧冻结任务仍读原 historical_index/memory_index；显式 `--record` 读取这两个旧名称时，新任务也能完整展开，但常规检索应使用 `recall`。后续新增章节和其他修订分支不会进入本任务的历史来源。

稀疏或无匹配查询仍可能遍历整个冻结历史，按章直接补读也可能遍历目录；页式复用减少重复构建与存储，不宣称所有查询都是常数时间。read/recall 返回的实际字符量均计入 usage，宿主包装、模型缓存与计费 token 由真实用量日志另算。

`complete` 除原有篇幅与来源验收外，必须验证所有 `required` 节点已 resolved、所有 `required` 线路已 resolved。机械门槛不证明情节好看；真实文学评价和实际 token 费用需真实宿主长跑另验收。

命令身份与修订影响分析见 [运行](runtime.md)，工程及真实长篇验收口径见 [验证](validation.md)。
