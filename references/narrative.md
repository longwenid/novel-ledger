# 叙事推进与长篇上下文

何时读：写卷纲、写章纲、执笔自比、漂移或文风被拒绝和长篇上下文补读。只把实际正文与机械核算结果写入事实，不把未来设计改称既成事实。

## 适用范围与能力要求

本文维护卷纲、章纲、卷内状态链、伏笔账、文风规格、漂移核算与历史补读的接口规则，字段形状以当前任务模板和引擎校验为准。narrative_tracking 默认 true；显式关闭时章纲的 `plot.nodes`/`plot.threads` 可以为空，但**资源/位置/知情/时钟/人物增量仍然必需**。

| 当前任务 | 读取位置 |
|---|---|
| 卷纲、开书覆盖范围 | [卷纲](#卷纲) |
| 章纲、漂移字段、状态链被拒 | [章纲](#章纲)、[卷内状态链](#卷内状态链与校验) |
| 伏笔（承诺）的埋设与兑现 | [伏笔账](#伏笔账卷纲声明章纲执行) |
| 文风规格、代理指标、style finding | [文风](#文风) |
| 执笔自比、漂移核算 | [执笔自比与引擎核算](#执笔自比与引擎核算) |
| 篇幅、上下文材料、必读状态 | [篇幅与上下文](#篇幅与上下文) |
| 场景来源、阅读关联、依赖声明 | [场景依赖与任务材料](#场景依赖与任务材料) |
| 需要早期原文或事件 | [历史补读](#历史补读) |

## 卷纲

### 参数与范围

新建/明确改约默认 `volume_outline={scope:'all', words:2500, tolerance:500}`：即**每卷 2000–3000 汉字**（下限 2000 是作者定的下限，目标 2500）；`words` 是**每卷**汉字数，`tolerance` 是允许偏差，`scope` 为 all（一次交全部卷）或 rolling（进入该卷前交该卷）。空对象 `{}` 表示明确关闭卷纲。字数用工程统一的汉字计数，标点和拉丁字符不计。字数合格不证明因果、人物选择或阅读作用成立。

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
  "hooks": [{"id":"h1","text":"读者看到的承诺：箱子里那张旧凭据的来历",
             "plant":[1,4],"payoff":[18,25],"required":true,"continues":false}],
  "style": {"trend":"本卷文风走向：前紧后松，对白占比升到三成，叙述句转短",
            "window":{"dialogue":0.5}},
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
- `hooks` **必填数组，可为空**：本卷伏笔账，规则见 [伏笔账](#伏笔账卷纲声明章纲执行)。
- `style.trend` **必填**（具体文字，说明本卷文风怎么走、相对首章定调有何变化）；`style.window` 可选，逐项覆盖契约 `style_window`。见 [文风](#文风)。
- `resources`/`places`/`characters`/`knowledge` 是本卷大势，key/entity 必须存在于世界模型或既有状态；`window` 落在本卷章号区间。
- `exit_state` 必须非空：卷末闭合由它逐项验收，容差为 0。

### 校验与失败

提交时引擎机械校验：卷 id 与 `contract.volumes` 一一对应且顺序一致；每卷汉字数落在 `words±tolerance`；node/thread/hook id 全书唯一且不覆盖已批准 id；`resources/places/knowledge/characters` 引用的 key/entity 存在；`window` 落在本卷章号区间；`exit_state` 非空；`hooks` 的窗口与跨卷标记自洽（见 [伏笔账](#伏笔账卷纲声明章纲执行)）；`style.trend` 非空。任一项失败 → 提交被拒（`design_drift`），修复走既有 `repair` 预算，**不新增阶段**。

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
  "hooks": [{"hook":"h1","action":"plant","note":"本章埋下凭据，读者第一次看到它"}],
  "style": {"pov":"第三人称限知","rhythm":"短句推进，动作与物件密，少解释",
            "dialogue_ratio":0.30,"notes":"本章对峙段允许长句"},
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
- `hooks` **必填数组，可为空**：本卷伏笔的执行，`action` 只有 `plant` 与 `payoff` 两个值；中途“再提一次”用 `hook_refs`，不新增动作。见 [伏笔账](#伏笔账卷纲声明章纲执行)。
- `style`：`pov` 与 `rhythm` 必填，`dialogue_ratio`（0~1）与 `notes` 可选。见 [文风](#文风)。
- `scenes`/`pacing` 可选，保留工作台兼容；`hook_refs`/`reader_refs`/`history_refs` 指出本章要承接的旧承诺、旧认知与历史断言。
- `new_entities` 取代原人物档案派工：新人物/地点/物品首次出现时，在本章内联给出档案字段；落地后按 id 引用，不再单独派一次档案任务。
- 每章 synopsis 写清行动、阻力、选择、代价、结果与对下一章的推动；引用真实世界记录与卷纲已登记的节点/线路/伏笔。

### 卷内状态链与校验

1. 章号连续，恰好覆盖本卷 `[volume.first, volume.end]`（`scope=all` 时覆盖整卷）。
2. `synopsis` 汉字数落在 `words±tolerance`。
3. 每行增量形状合法：`from`/`to` 类型一致，`reason` 非空；resource 有 key 且存在于世界或既有状态；place 存在于世界 geography；node/thread/hook 属于本卷卷纲已登记集合（hook 另见跨卷带入规则）。
4. **enter/exit 冗余一致性**：`exit` 必须等于 `enter ⊕ 本章增量`（引擎自己算一遍比对）。任一侧缺项即漂移，拒绝。
5. **卷内状态链模拟**：从卷起始真实状态出发逐章应用增量，要求第 i 章 `enter` 恰好等于模拟到第 i 章开始的状态。模拟中拒绝：资源为负、`clock` 倒退、位置跳变到未登记地点、知情倒退（`retracted` 除外）、人物变化缺 `choice`/`cost`、同一 node 重复 `advanced` 或 resolved 后再推进、thread resolved 后重用，以及伏笔的重复埋设/重复兑现/越窗/未埋先承接（见 [伏笔账](#伏笔账卷纲声明章纲执行)）。
6. **卷末闭合**：最后一章模拟结果必须满足本卷 `exit_state` 与卷纲声明的 `resources/places/knowledge/characters` 终值（容差 0），且本卷 `required: true` 的伏笔全部 `paid`。

任一项失败 → `chapter_outline` 提交被拒（`design_drift`），修复走既有 `repair` 预算，不新增阶段。这条链解决的是“窗口内非节点状态不可前瞻”：后章的 `enter` 会撞上前章实际写出的状态，设计期就挡住资源/位置/知情漂移。

## 伏笔账（卷纲声明，章纲执行）

伏笔是**对读者的具体承诺**，不是支线（`threads`）的同义词：支线管剧情线是否推进，伏笔管“读者看到了什么、什么时候兑现”。

### 卷纲声明

```json
"hooks": [
  {"id": "h1", "text": "读者看到的承诺：箱子里那张旧凭据的来历",
   "plant": [1, 4], "payoff": [18, 25], "required": true, "continues": false}
]
```

- `id` 全书唯一（与 node/thread 同一命名空间纪律，不得覆盖既有 id）。
- `text` 是对读者的**具体**承诺，不接受“待补”“另有隐情”这类空话。
- `plant: [最早章, 最迟章]` 必须落在本卷章号区间内，且这两章之间必须出现一次 `plant`。
- `payoff: [最早章, 最迟章]`，要求 `payoff[0] >= plant[1]`。**允许越过本卷 `end`，但那时必须同时 `continues: true` 且 `required: false`**（跨卷伏笔）。
- `required: true` 表示本卷末必须兑现（由卷内状态链收尾校验）；`required` 且 `payoff[1] > volume.end` 非法。
- 校验：id 唯一 / 窗口合法 / `text` 非空 / 跨卷声明自洽。

### 章纲执行

```json
"hooks": [{"hook": "h1", "action": "plant", "note": "本章埋下凭据，读者第一次看到它"}]
```

- `action` **只有两个值**：`plant`（创建承诺）与 `payoff`（兑现）。中途“再提一次”用既有的 `hook_refs` 承接，**不新增动作**。
- `hook` 必须是「本卷 `hooks` 声明的 id」或「前卷 `continues: true` 且仍未兑现的 id」。**跨卷伏笔在下一卷不必重新登记**：下一卷章纲可以直接对它执行 `payoff`，下一卷卷纲也不要求重复声明；引擎按“前卷 continues 且未兑现”识别为合法。
- 同一 id：`plant` 恰好一次、`payoff` 恰好一次、`payoff` 必须晚于 `plant`（同章允许先 plant 后立刻 payoff，用于短线钩子）。
- `plant` 必须落在声明的 `plant` 窗口内，`payoff` 必须落在 `payoff` 窗口内。
- `hook_refs` 里出现的 id 必须已经 `plant`；未埋就承接 = 漂移。

### 卷末闭合与跨卷

卷内模拟结束时：本卷 `required: true` 的每个伏笔必须是 `paid`；`continues: true` 的允许仍为 `open`，带入下一卷，由下一卷的卷纲/章纲继续执行。卷末闭合与 `exit_state` 一样是硬判定，不靠人工检查。

### 结算

伏笔事件复用既有 hook 事件，不新造协议：`facts.settle` 已支持 `{'op':'hook', id, status, due, text, reason, evidence}`（`open`/`paid`/`closed`，延期最多两次，到期未兑现报 `hook_due`）。

- `plant` → `{'op':'hook','id':…,'status':'open','due': payoff[1],'text':…,'reason': note?,'evidence':…}`
- `payoff` → `{'op':'hook','id':…,'status':'paid','reason': note?,'evidence':…}`

这些事件由 `drift.reconcile` 从章纲行加 `drift_check` **产出，写手不手写事件**。`drift_check.items` 因此新增 `kind='hook'`：`planned={'action':'plant'|'payoff'}`、`actual={'action':…}`、`evidence` 为正文引文。

结果：`state.hooks` 对新书不再是空集，bookpage 的承诺区照常渲染，`complete()` 的“未交代承诺”检查对新书是真实检查（未兑现即拒绝）。

## 文风

文学质量不再有独立复核者，取而代之的是**文风规格（定性）+ 引擎机械代理指标（定量、零派工）**。作者已选定这一方案：它不是“只做自检”，也不是“越界即拒的硬门槛”。

### 规格：卷纲与章纲各自声明

- 卷纲 `style.trend`（必填）：本卷文风走向，相对首章定调怎么变（例：前紧后松、对白占比升到三成、叙述句转短）。可带 `style.window` 逐项覆盖契约容差。
- 章纲 `style`：`pov` 必填，须与契约 `pov` 一致，或落在卷纲 `style.trend` 声明的演进内（设计者自述，引擎只做字面一致性检查）；`rhythm` 必填（具体文字）；`dialogue_ratio` 可选目标（0~1）；`notes` 可选。

### 契约容差 `style_window`

```python
{'sentence': 0.35, 'paragraph': 0.35, 'dialogue': 0.40, 'repetition': 0.12, 'person': 1}
```

各项是**相对偏差**容忍（`|实测-基线|/基线 <= window`）；`repetition` 是本章内部高重复的绝对占比上限；`person` 为 1 表示视角标记必须与声明一致。作者可用改约调整。`repetition` 的 0.12 是实测校准值：正常中文散文的四字重复率约 0.04~0.09，而复读同一句的文本是 0.79~0.99，0.12 因此落在真实写作之上、病态之下。

**卷纲 `style.window` 是逐项合并**（`style.merged_window`）：先用契约 `style_window` 补齐默认，再用卷纲 `style.window` 的键逐个覆盖；只接受合法键与合法数值，非法项按契约默认处理。

### 五条代理判据（`style.py`）

1. `sentence_mean` / `sentence_short_share` 相对锚点越界；
2. `paragraph_mean` / `paragraph_max` 越界；
3. `dialogue_share` 相对锚点（或章纲 `dialogue_ratio`）越界；
4. `repetition_share` 超过 `window['repetition']`（与 `lint` 互补：lint 查跨章逐字重复，本项查本章内部高重复）；
5. `person` 与章纲 `pov`/契约 `pov` 不一致。

锚点是作者认可的首章样本（`book['style_anchor']['sample']`）。**没有锚点时降级**：只跑第 4、5 条，以及“与本章章纲声明目标”的对比——没有基线就不做相对越界判定，不拿默认值冒充定调。

**指标恒为有限数值，判不判由 `compare` 决定**：`metrics` 永远返回可序列化的有限值，除上述指标外还带 `han`（汉字数）、`sentences`（句数）与 `repetition_grams`（四字窗口数）供门槛判断（样本过短时 `repetition_share` 为 `0`），避免用噪声当偏差。`compare` 的实际门槛（与实现一致）：

- 正文汉字 `< 40` 时整章不判（样本太短，任何指标都是噪声）；锚点样本同样不足 40 汉字时视为**没有锚点**。
- 四字窗口数 `< 20` 时不判重复度。
- 句长/段长只在锚点与本章的**汉字量同数量级**（3 倍以内）且本章句数 `>= 3` 时才比较，避免拿极短样本的节奏去要求整章。
- `dialogue` 优先按章纲声明的 `dialogue_ratio`（0~1）判，没有声明时才用锚点比（同样要求同数量级）。

**`person` 的判定口径**：

- 只统计**引号外**的叙述文本（对白里“我”很多，会污染判断）。
- 标记按子串计数：第一人称 `我/咱/俺`，第三人称 `他/她/它`（`他们` 计 `他`）。
- 两类都出现 → `mixed`；都不出现 → `unknown`；只有一类 → `first`/`third`。
- **`unknown` 不判不符**（中文叙述常省略主语，把省略当错会大量误报）；`mixed` 与声明的单人称作对时算不符。
- 声明侧：只有章纲 `style.pov` 或契约 `pov` 里出现“第一人称”/“第三人称”时才判；两者都没写就不判。

### 处理路径与代价

`style.compare` 产出的 findings 形状与漂移 findings 一致（`{criterion,severity,target_chapter,repair_scope,reason,metric,expect,got}`，`severity='quality'`、`repair_scope='local'`），在 write/repair/redesign 提交时并入既有 findings 集合，走**同一个有界返修路径**：不新增阶段、不新增停止点、不消耗独立审。

**代价说清楚**：代理指标只保证“**文风一致、可核对**”——句长、段长、对白占比、本章重复度、视角标记与声明是否对得上。它**不证明“好看、人物可信”**，也不判断人物动机是否成立、节奏是否有张力、伏笔兑现是否有力。真正的文学判断仍然只能靠**人工抽读或离线盲测**（`scripts/quality_eval.py`），或另行发起一次修订。

## 执笔自比与引擎核算

执笔回执交 `title`/`prose`/`summary`，外加 `drift_check` 与 `self_check`：

```json
{
  "title": "…", "prose": "…", "summary": "…",
  "drift_check": {
    "items": [{
      "kind": "resources|places|knowledge|characters|clock|node|thread|hook",
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

`kind='hook'` 的行用动作而不是前后值：`planned={'action':'plant'|'payoff'}`、`actual={'action':…}`，`evidence` 仍是正文引文。

引擎核算（零派工）：

1. `items` 必须**恰好覆盖**本章纲的全部计划增量（kind+key 各一次，不多不少）；漏项/多项 → `drift_coverage` 拒绝。
2. 每条 `actual.from` 必须等于引擎投影的当前真实值（**不由写手自报前态**）；不等 → `drift_before` 拒绝。
3. `status=kept` 时 `actual.to` 必须等于 `planned.to`；`deviated`/`skipped` 必须给 `reason`，并写入 `book['design_drift']`。
4. `unplanned` 每项同样按第 2/3 条核算并登记；未登记的计划外变化会在下一次章纲校验（后章 `enter` 撞上）时暴露。
5. `evidence.quote` 必须是正文原文片段，走精确引文校验。
6. 通过后原子入账：复用事实、叙事与空间的既有机械判据（`facts.settle` / `narrative.prepare_events` / `spatial.settle`），事件来源是 `drift_check.items`；伏笔事件由 `drift.reconcile` 产出。
7. 存在 `deviated`/`skipped` 时：本章照常入库（偏差已在自比中说明理由），引擎把该偏差加入 `book['design_drift']`，并在下一章派工前对该卷剩余章纲派一次 `chapter_outline`（payload 带 `repair=True` 与偏差清单）重排——这是删除 alignment 阶段后的替代路径。
8. 其余既有闸门保留：字数区间（`word_budget`）、`lint.draft_findings`、字面约定（`literal_policy`）、禁用名，以及文风代理指标（见 [文风](#文风)）。

**代价说清楚**：`drift_check` 是执笔者自己写的，引擎只核对“计划增量是否齐全、前态是否等于投影、kept 是否等于计划值、偏差是否给了理由与引文”；文风代理指标只核对“与锚点和本章声明是否对得上”。两者都证明不了这一章好不好看、人物是否可信、节奏是否成立——**没有独立 agent 复核文学质量与阅读体验**。需要独立判断时只能人工抽读正文，或用离线盲测工具，或另行发起一次修订。

## 篇幅与上下文

跟踪项目允许长章短章共同满足总区间；chapter_max 可以高于全书平均上限。每章 word_budget 给出 minimum/maximum/aim，根据剩余章数和真实累计篇幅计算可完成范围；窄范围修订同时预留原样携带后缀的固定篇幅。字数不足或超范围的实际稿仍留档并消耗既有修复额度。无法达到目标时明确 `word_budget` 拒绝，修订前文或由作者改约，不降低目标。

执笔 story 读取本章章纲及直接前置，前置结果见投影状态，完整设计在 `design:*`。规划只选本卷未兑现的节点与伏笔；当前状态供参与人、当前动机、近期成长和相关承诺使用，承诺按到期、显式 `hook_refs`、相关人物/物品及话题选择，完整状态保留 `complete_state`。世界采用直接关联；world_records 为可见材料，幕后真相保留可选 world_author_records，disclosure_boundary 明确本章允许披露与读者前态。执笔的必读/载荷带契约文风（`voice`/`style_traits`/`tone`/`pov`）、`style_anchor` 样本、本卷 `style.trend` 与本章 `style`。

## 场景依赖与任务材料

新工作台任务采用 scene-identity/2：场景 ID 不绑定章号，跨章移动保留身份，独立的故事时间、作品理解与阅读关联见 [叙事工作台](workbench.md)。旧 `c章号:` 前缀是旧冻结身份协议；新任务未提供 ID 时引擎生成不透明 ID。

阅读关联由 reading-dependencies/1 能力及 `reading_schema` 标记冻结，旧任务中的同名字段不追补解释；没有标记时保守重读。相关字段、分级修订和创作记忆统一在工作台维护，不用事实 `dependency_coverage` 代替阅读关联覆盖。

章纲可声明 `dependency_coverage=partial|complete`，默认 partial。每场的 id、`reads=[{kind,key}]` 与 `depends_on=[场景ID]` 只能指向已登记前章或本章前场，禁止环及前向引用。complete 要求每场显式提供两份数组，无依赖给空数组；**v2 没有独立读者核对语义完整性**，引擎只核对声明形状与引用是否存在，遗漏只能靠后章 `enter` 撞上或作者抽读暴露。partial 在修订传播时保守扩大范围。

任务的 `scene_context` 携带本章章纲行与场景，inputs 给出显式输入和输入是否存在，plan_hash/state_hash 绑定准确来源。`scene_sources` 绑定前置已提交场景的章纲/正文/事件哈希与章节链；原文按本任务的 `recall --chapter` 补读。引用若只存在于未提交的重排章纲，派工拒绝并要求重新提交章纲。材料只是作者可用信息，人物实际知情仍以 `knowledge` 状态为准；未来设计不会变成事实。

## 历史补读

记忆检索可用 `recall --task ID --entity 人物ID`，或 `--node/--topic/--thread ID`：默认返回最近 5 个匹配章节的全部匹配证据；用 `--limit 1～20`、`--before 章号` 分页，再用 `--chapter N` 完整补读。新任务的可选 history_source 只冻结逐章不可变目录的入口及截至章号，查询由近到远读取所需页与事件，不每次重建全书摘要/事件索引。旧冻结任务仍读原 historical_index/memory_index；显式 `--record` 读取这两个旧名称时，新任务也能完整展开，但常规检索应使用 `recall`。后续新增章节和其他修订分支不会进入本任务的历史来源。

稀疏或无匹配查询仍可能遍历整个冻结历史，按章直接补读也可能遍历目录；页式复用减少重复构建与存储，不宣称所有查询都是常数时间。read/recall 返回的实际字符量均计入 usage，宿主包装、模型缓存与计费 token 由真实用量日志另算。

`complete` 除原有篇幅与来源验收外，必须验证所有 `required` 节点已 resolved、所有 `required` 线路已 resolved、所有 `required` 伏笔已 paid（跨卷 `continues` 的由后续卷收口）；未兑现承诺会直接拒绝，不再是对新书的空检查。机械门槛不证明情节好看；真实文学评价和实际 token 费用需真实宿主长跑另验收。

命令身份与修订影响分析见 [运行](runtime.md)，工程及真实长篇验收口径见 [验证](validation.md)。
