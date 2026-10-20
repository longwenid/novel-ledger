# 叙事推进与长篇上下文

何时读：写卷纲、写章纲、执笔自比、漂移或文风被拒绝和长篇上下文补读。只把实际正文与机械核算结果写入事实，不把未来设计改称既成事实。

## 适用范围与能力要求

本文维护卷纲、章纲、卷内状态链、伏笔账、文风规格、漂移核算与历史补读的接口规则，字段形状以当前任务模板和引擎校验为准。narrative_tracking 默认 true；显式关闭时章纲的 `plot.nodes`/`plot.threads` 可以为空，但资源/位置/知情/时钟/人物变化仍按同一规则核算；四类增量数组缺省或为 null 时按空数组处理。

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

新建/明确改约默认 `volume_outline={scope:'all', words:2500, tolerance:500}`：即**每卷 2000–3000 汉字**（目标 2500，可由作者改约调整）；`words` 是**每卷**汉字数，`tolerance` 是允许偏差，`scope` 为 all（一次交全部卷）或 rolling（进入该卷前交该卷）。卷纲与章纲都是必选阶段；缺省使用默认策略，显式 `{}` 或 `null` 会被拒绝并提示填写完整策略。字数用工程统一的汉字计数，标点和拉丁字符不计。字数合格不证明因果、人物选择或阅读作用成立。

多卷策略组合为 all/volume、all/all 或 rolling/volume（依次为卷纲/章纲 scope）；rolling/all 会在约定校验时拒绝，避免提前派发尚无卷纲的全书章纲任务。

**t0/t1 有形状合并**：`PIPELINE_SHAPES` 只保留 `merge_chapter_outline`（t0/t1 为 true），让“本卷卷纲 + 该卷章纲”由**同一次派工、同一份回执**交付，两个契约各自校验同一份回执；其余档位分两次派工。

### 回执形状

```json
{"volumes": [{
  "id": "v1",
  "purpose": "卷职责，≤60 汉字",
  "stage": "逐字取已选格局阶梯中的一级",
  "arc": "展开开局处境、关键转折与卷末局面；整卷字段合计须满足 words±tolerance 汉字",
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
  "characters": [{"entity":"hero","from":null,"to":{"desire":"救出同伴","stance":"承担代价","relationship_focus":"与同伴互信"},"reason":"本卷成长终态"}],
  "knowledge": [{"who":"hero","topic":"…","from":null,"to":"suspected","reason":"…"}],
  "clock": {"advance_days": 30, "to": 30},
  "exit_state": "卷末必须达到的状态：资源/位置/人物/知情/线路各一句"
}]}
```

- `id` 与 `contract.volumes` 一一对应且顺序一致；`purpose` 是卷职责。
- 已声明 `world_ladder` 时，`stage` 必须逐字取其中一级，并按卷序只升不降；直接导入约定未声明阶梯时可留空。
- `nodes`/`threads` **按卷登记**，id 全书唯一、不覆盖已批准 id；跨卷线路用 `continues: true` 标记。
- `hooks` **必填数组，可为空**：本卷伏笔账，规则见 [伏笔账](#伏笔账卷纲声明章纲执行)。
- `style.trend` **必填**（具体文字，说明本卷文风怎么走、相对首章定调有何变化）；`style.window` 可选，逐项覆盖契约 `style_window`。见 [文风](#文风)。
- `resources`/`places`/`characters`/`knowledge` 是本卷大势，key/entity 必须存在于世界模型或既有状态；`window` 落在本卷章号区间。
- `clock.advance_days` 是本卷推进天数，`clock.to` 是卷末主线时钟绝对值；均为非负整数。人物 `to` 使用与章纲相同的三字段对象，卷末逐项核对。
- `exit_state` 必须非空，保存卷末局面的文字说明；它的自然语言含义不作机械验收。闭合判据来自资源、位置、知情、结构化人物终值和 `clock.to`。

### 校验与失败

提交时引擎机械校验：卷 id 与 `contract.volumes` 一一对应且顺序一致；每卷汉字数落在 `words±tolerance`；node/thread/hook id 全书唯一且不覆盖已批准 id；`resources/places/knowledge/characters` 引用的 key/entity 存在；`window` 落在本卷章号区间；`exit_state` 非空；`hooks` 的窗口与跨卷标记自洽（见 [伏笔账](#伏笔账卷纲声明章纲执行)）；`style.trend` 非空。任一项失败时提交被拒（`design_drift`），保持原任务并按具体错误重交，不消耗正文返修额度。

## 章纲

### 参数与范围

`chapter_outline={scope:'volume',words:150,tolerance:60}`：`words` 是**每章 synopsis** 的汉字数，`scope` 为 volume（进卷前交本卷）或 all（正文开始前覆盖全部卷）。引擎仍按卷派发章纲任务，按实际 scope 完成所需覆盖。

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
            "notes":"本章对峙段允许长句"},
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

- **必需**：`chapter` `synopsis` `plot.beat` `enter` `exit` `world_refs`。模板显式列出四个增量数组（`resources` `places` `knowledge` `characters`），便于逐类核对；空数组、缺字段和 null 均表示本章没有这类变化。写入的变化仍须通过完整形状与状态校验。
- `hooks` **必填数组，可为空**：本卷伏笔的执行，`action` 只有 `plant` 与 `payoff` 两个值；中途“再提一次”用 `hook_refs`，不新增动作。见 [伏笔账](#伏笔账卷纲声明章纲执行)。
- `style`：`pov` 与 `rhythm` 必填，`dialogue_ratio`（0~1）与 `notes` 可选。见 [文风](#文风)。
- `scenes`/`pacing` 是当前章纲的可选字段；`hook_refs`/`reader_refs`/`history_refs` 指出本章要承接的旧承诺、旧认知与历史断言。
- `new_entities` 取代原人物档案派工：新人物/地点/物品首次出现时，在本章内联给出档案字段；落地后按 id 引用，不再单独派一次档案任务。
- 每章 synopsis 交代实际发生的事、人物处境与本章阅读作用；行动与后果可跨章承接，不强求每章齐备一套节拍。引用真实世界记录与卷纲已登记的节点/线路/伏笔。

### 卷内状态链与校验

1. 章号连续，恰好覆盖本卷 `[volume.first, volume.end]`（`scope=all` 时覆盖整卷）。
2. `synopsis` 汉字数落在 `words±tolerance`。
3. 每行增量形状合法：`from`/`to` 类型一致，`reason` 非空；resource 有 key 且存在于世界或既有状态；place 存在于世界 geography；node/thread/hook 属于本卷卷纲已登记集合（hook 另见跨卷带入规则）。
4. **enter/exit 冗余一致性**：`exit` 必须等于 `enter ⊕ 本章增量`（引擎自己算一遍比对）。任一侧缺项即漂移，拒绝。
5. **卷内状态链模拟**：从卷起始真实状态出发逐章应用增量，要求第 i 章 `enter` 恰好等于模拟到第 i 章开始的状态。模拟中拒绝：资源为负、`clock` 倒退、位置跳变到未登记地点、知情倒退（`retracted` 除外）、人物变化缺 `choice`/`cost`、同一 node 重复 `advanced` 或 resolved 后再推进、thread resolved 后重用，以及伏笔的重复埋设/重复兑现/越窗/未埋先承接（见 [伏笔账](#伏笔账卷纲声明章纲执行)）。
6. **卷末闭合**：最后一章模拟结果必须等于卷纲声明的 `resources/places/knowledge/characters` 结构化终值与 `clock.to`（容差 0）；整卷模拟还核对 `clock.advance_days`。本卷 `required: true` 的伏笔须全部 `paid`。`exit_state` 只作文字说明。

任一项失败时保持原 `chapter_outline` 任务并返回 `design_drift`，不消耗正文返修额度；按错误修正后重新提交。

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

卷内模拟结束时：本卷 `required: true` 的每个伏笔必须是 `paid`；`continues: true` 的允许仍为 `open`，带入下一卷，由下一卷的卷纲/章纲继续执行。结构化卷末闭合是硬判定；`exit_state` 的叙事含义仍由作者判断。

### 结算

伏笔事件复用既有 hook 事件，不新造协议：`facts.settle` 已支持 `{'op':'hook', id, status, due, text, reason, evidence}`（`open`/`paid`/`closed`，延期最多两次，到期未兑现报 `hook_due`）。

- `plant` → `{'op':'hook','id':…,'status':'open','due': payoff[1],'text':…,'reason': note?,'evidence':…}`
- `payoff` → `{'op':'hook','id':…,'status':'paid','reason': note?,'evidence':…}`

这些事件由 `drift.reconcile` 从章纲行加 `drift_check` **产出，写手不手写事件**。`drift_check.items` 因此新增 `kind='hook'`：`planned={'action':'plant'|'payoff'}`、`actual={'action':…}`、`evidence` 为正文引文。

`state.hooks` 保存承诺状态，页面据此展示；`complete()` 拒绝仍开放的承诺。

## 文风

文风从作者约定、人物处境与本章阅读效果判断。默认 `style_guard=observe`：相对首章的句段与对白密度变化作为观察返回，不因形状不同强迫正文返修；作者明确选 `strict` 时才按容差约束首章形状。显式章纲对白目标与高重复检查在两档都生效。代词统计在两档都只观察，不自动裁决实际视角。

### 规格：卷纲与章纲各自声明

- 卷纲 `style.trend`（必填）写具体叙述意图，例如人物关系渐近时对白由试探变得直接；可带 `style.window` 逐项覆盖契约容差。作者要求量化时才选择数字目标，不为写趋势硬设配额。
- 章纲 `style` 的 `pov`、`rhythm` 必填；`dialogue_ratio`（0~1）与 `notes` 可选。视角沿用作者约定，节奏结合当章内容；未声明对白目标就不补比例，`notes` 不是绕过事实约束的豁免。
- 首章样本提供叙述气质和表达依据，静章、争吵、追逐与独处可以有不同的句段和对白密度。具体语言取舍见 [人物与表达的真实感](craft.md#人物与表达的真实感)。

### 契约容差 `style_window`

```python
{'sentence': 0.35, 'paragraph': 0.35, 'dialogue': 0.40, 'repetition': 0.12, 'person': 1}
```

句、段及对白容差按相对变化 `|实测-基线|/基线` 计算；在 observe 中用于提示，在 strict 中用于已选择的数值约束。`repetition` 是本章重复四字窗口的绝对占比上限，两个模式都检查；它不是“人味”或好坏评分，刻意复沓须结合原文和作者意图处理。`person` 字段随窗口保留，代词分布仅供观察，不能以数字证明叙事视角。

卷纲 `style.window` 逐项合并到契约窗口，只接受合法键和值。`style_guard` 只有 observe / strict 两个取值，默认取 contracts.DEFAULTS；选择 strict 通过正常作者约定或改约保存，不由返修者为当前稿件悄悄切换。数值约束仍不能证明文学成立。

### 五条代理判据（`style.py`）

1. `sentence_mean` / `sentence_short_share` 相对首章的变化；
2. `paragraph_mean` / `paragraph_max` 的变化；
3. 未声明对白目标时 `dialogue_share` 相对首章的变化；显式 `dialogue_ratio` 优先核验；
4. `repetition_share` 与本章绝对重复度上限比较，互补 lint 的跨章逐字重复检查；
5. `person` 记录引号外第一、第三人称代词分布，供核对原文。

`metrics` 保留原稿顺序计算重复率，识别中文、直角及英文直引号，嵌套对白不重复计数；闭引号和连续省略号不产生零汉字句。短文本门槛沿 contracts.DEFAULTS：正文不足 40 汉字整章不判，锚点不足 40 汉字不作为基线，四字窗口不足 20 不判重复度。句段只在锚点与本章字量同数量级（3 倍内）且本章至少三句时比较。

锚点缺失时不虚构基线，只记录可计算观察并检查显式对白目标和重复度。明确声明对白目标 0 时，非零对白仍产生偏差；未声明时，独处章没有对白可以是正常阅读需要。

**人称观察的边界**：第一人称叙述可写“我进门，他抬头”，第三人称限知也可贴近人物的内心话；中文还会省略主语。`first/third/mixed/unknown` 只是代词分布标签，不能证明越界、全知或人称切换。实际视角仍须按作者约定结合所知范围、心理归属与切换标记自比。

### 处理路径与代价

`style.examine` 返回 `metrics / observations / findings`。预检与提交把 `style_report` 返回给 Worker，正式章节的核账记录同时保存报告。observations 不占返修额度；findings 沿现有有界返修路径处理，不增加独立章审。`style.compare` 只返回 findings，供只需要执行判据的调用方使用。

观察不等于自动通过文学质量。写手应结合具体语境判断是否有问题；严格模式的形状偏差也只描述超过容差，不能直接断言人物可信度或语感好坏。机械检查没有发现异常时，仍可能存在模板化对白、空泛情绪和作者替人物讲道理。

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
    "unplanned": [{"kind":"knowledge","key":"hero:t2","actual":{"from":null,"to":"hinted"},"reason":"本章新增线索","evidence":{"chapter":1,"quote":"正文中的完整必要引文"}}],
    "verdict": "clean|deviated"
  },
  "self_check": "逐项说明本章与章纲的比对结论（不得为空）"
}
```

`kind='hook'` 的行用动作而不是前后值：`planned={'action':'plant'|'payoff'}`、`actual={'action':…}`，`evidence` 仍是正文引文。

引擎核算（零派工）：

1. `items` 必须**恰好覆盖**本章纲的全部计划增量（普通项按 kind+key，伏笔按 kind+key+action 区分）；漏项/多项 → `drift_coverage` 拒绝。
2. 前态取自引擎投影；填写的 `actual.from` 必须与该值相等；不等 → `drift_before` 拒绝。
3. `status=kept` 时 `actual.to` 必须等于 `planned.to`；`deviated`/`skipped` 必须给 `reason`，并写入 `book['design_drift']`。
4. `unplanned` 支持 `resources/places/knowledge/characters` 四类，必须给 `actual.from/to`、原因与本章精确引文；资源还需可还原的持有人/资产/单位，位置需路径，人物需 choice/cost。按同一事实规则生成事件、更新投影并记偏差，不能只填 change 说明。情节、伏笔、披露与时钟须通过章纲契约处理，未开放的种类明确拒绝。
5. `evidence.quote` 必须是正文原文片段，走精确引文校验。
6. 通过后原子入账：复用事实、叙事与空间的既有机械判据（`facts.settle` 及其调用的叙事、空间规则），事件来源是 `drift_check.items`；伏笔事件由 `drift.reconcile` 产出。
7. 存在 `deviated`/`skipped` 时：本章通过全部机械判据后入库，引擎把该偏差加入 `book['design_drift']`，并在下一章派工前对该卷剩余章纲派一次 `chapter_outline`（payload 带 `repair=True` 与偏差清单）重排。
8. 其余既有闸门保留：字数区间（`word_budget`）、`lint.draft_findings`、字面约定（`literal_policy`）、禁用名，以及文风代理指标（见 [文风](#文风)）。

## 篇幅与上下文

跟踪项目允许长章短章共同满足总区间；chapter_max 可以高于全书平均上限。每章 word_budget 给出 minimum/maximum/aim，根据剩余章数和真实累计篇幅计算可完成范围；窄范围修订同时预留原样携带后缀的固定篇幅。字数不足或超范围的实际稿仍留档并消耗既有修复额度。无法达到目标时明确 `word_budget` 拒绝，修订前文或由作者改约，不降低目标。

执笔读取冻结的 `chapter_outline` 和本章相关 `volume_outline`，完整卷纲可通过 `complete_volume_outline` 补读；前置结果见投影状态。当前状态供参与人、当前动机、近期成长和相关承诺使用，承诺按到期、显式 `hook_refs`、相关人物/物品及话题选择，完整状态保留 `complete_state`。世界采用直接关联；world_records 为可见材料，幕后真相保留可选 world_author_records，disclosure_boundary 明确本章允许披露与读者前态。执笔的必读/载荷带契约文风（`voice`/`style_traits`/`tone`/`pov`）、`style_anchor` 样本、本卷 `style.trend` 与本章 `style`。

## 场景依赖与任务材料

新工作台任务采用 scene-identity/2：场景 ID 不绑定章号，跨章移动保留身份，独立的故事时间、作品理解与阅读关联见 [叙事工作台](workbench.md)。未提供 ID 时引擎生成不透明 ID，后续重排须保留这个身份。

阅读关联统一由 reading-dependencies/1 能力及 `reading_schema` 标记冻结。相关字段、分级修订和创作记忆统一在工作台维护，不用事实 `dependency_coverage` 代替阅读关联覆盖。

章纲可声明 `dependency_coverage=partial|complete`，默认 partial。每场的 id、`reads=[{kind,key}]` 与 `depends_on=[场景ID]` 只能指向已登记前章或本章前场，禁止环及前向引用。complete 要求每场显式提供两份数组，无依赖给空数组；引擎只核对声明形状与引用是否存在，语义遗漏需结合后续状态冲突或人工抽读发现。partial 在修订传播时保守扩大范围。

任务的 `scene_context` 携带本章章纲行与场景，inputs 给出显式输入和输入是否存在，plan_hash/state_hash 绑定准确来源。`scene_sources` 绑定前置已提交场景的章纲/正文/事件哈希与章节链；原文按本任务的 `recall --chapter` 补读。引用若只存在于未提交的重排章纲，派工拒绝并要求重新提交章纲。材料只是作者可用信息，人物实际知情仍以 `knowledge` 状态为准；未来设计不会变成事实。

## 历史补读

记忆检索可用 `recall --task ID --entity 人物ID`，或 `--node/--topic/--thread ID`：默认返回最近 5 个匹配章节的全部匹配证据；用 `--limit 1～20`、`--before 章号` 分页，再用 `--chapter N` 完整补读。可选 history_source 只冻结逐章不可变目录的入口及截至章号，查询由近到远读取所需页与事件，不每次重建全书摘要/事件索引。历史原文与证据统一使用 `recall` 按冻结目录分页补读，不再提供旧全量索引别名。后续新增章节和其他修订分支不会进入本任务的历史来源。

稀疏或无匹配查询仍可能遍历整个冻结历史，按章直接补读也可能遍历目录；页式复用减少重复构建与存储，不宣称所有查询都是常数时间。read/recall 返回的实际字符量均计入 usage，宿主包装、模型缓存与计费 token 由真实用量日志另算。

`complete` 除原有篇幅与来源验收外，必须验证所有 `required` 节点已 resolved、所有 `required` 线路已 resolved、所有开放伏笔均已兑现或关闭（跨卷 `continues` 的由后续卷收口）。

命令身份与修订影响分析见 [运行](runtime.md)，工程及真实长篇验收口径见 [验证](validation.md)。

## 有界材料与局部重排

执笔的必读 volume_outline 为本章卷纲材料：节点保留本章动作、当前窗口、enter/exit 引用及递归前置依赖，线路随这些节点和章纲线路引用保留；方向、转折、伏笔、文风及卷末终值不截断。complete_volume_outline 是同一任务冻结的完整来源，需了解其他节点时按任务补读。章纲设计仍读完整卷纲。

必读 hooks 保留当前卷声明、本章动作与显式引用、相关人物/话题和近期到期承诺；完整历史声明保存在同一任务的可选 complete_hooks，按 `read --record complete_hooks` 补读。设计任务仍读取全部未结承诺。已兑现且未引用的历史伏笔、已收束且未引用的线路不随每章重复投递；显式状态输入保留完整值，完整状态仍在 complete_state。

材料量随本章实际义务变化：递归因果依赖、开放承诺和同时活跃线路多时仍会增长，不截断必要来源。章纲的出场者由人物、知情、位置变化及场景 present 等声明归纳；完全未声明参与人时会保守携带全部人物资料，因此长篇应在场景中如实声明 present。契约及其完整分卷表仍随任务提供，不承诺所有材料恒定字节数。

仅当冻结任务声明 payload.allow_retained_suffix 时，可先按需读取冻结的 prior_chapter_outlines 核对原后缀，章纲重排可增加 through_chapter（最后修改章），chapters 连续覆盖 from_chapter 至 through_chapter。引擎接回已保存的后续章纲并从真实前态验证整条剩余链、卷末闭合及场景/阅读绑定。任一不兼容即拒绝，须扩大范围重交；未给 through_chapter 时继续交到卷末。已写章节和未替换的后缀不因重排被改写。
