# 叙事推进与长篇上下文

何时读：写卷纲、写章纲、执笔自比、漂移或文风被拒绝和长篇上下文补读。只把实际正文与机械核算结果写入事实，不把未来设计改称既成事实。

## 适用范围与能力要求

本文维护卷纲、章纲、卷内状态链、伏笔账、文风规格、漂移核算与历史补读的接口规则，字段形状以当前任务模板和引擎校验为准。narrative_tracking 默认 true；显式关闭时章纲的 `plot.nodes`/`plot.threads` 可以为空，但资源/位置/知情/时钟/人物变化仍按同一规则核算；五类增量数组（resources/places/knowledge/characters/relations）缺省或为 null 时按空数组处理——`relations` 留空就是「本章无关系变化」的合法声明。

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

设计顺序采用 [卷纲因果设计](craft.md#卷纲因果设计)：先用开书决定、当前约定、世界和前卷后果建立人物行动链，再映射回执字段。卷纲任务冻结完整上游材料；滚动后续卷额外必读 `previous_volume_outline`（相邻已批准卷纲），不只凭开书摘要重建前卷结局。这些来源不新增回执字段或文学阻断。

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
  "relations": [{"source":"hero","target":"foil","key":"alliance","from":null,"to":"同盟","reason":"本卷关系终值"}],
  "reader_knowledge": [{"topic":"…","to":"hinted","reason":"卷末读者认知终值"}],
  "clock": {"advance_days": 30, "to": 30},
  "exit_state": "卷末必须达到的状态：资源/位置/人物/知情/线路各一句"
}]}
```

- `id` 与 `contract.volumes` 一一对应且顺序一致；`purpose` 是卷职责。
- `turns[].at` 与 `turn` 使用非空文字；「卷中／卷尾／第N章附近」是位置示例，不是封闭枚举。「开卷」等清楚描述同样可用，设计蓝图的样本位置不新增词表或比例阈值校验。
- 已声明 `world_ladder` 时，`stage` 必须逐字取其中一级，并按卷序只升不降；直接导入约定未声明阶梯时可留空。
- `nodes`/`threads` **按卷登记**，id 全书唯一、不覆盖已批准 id；跨卷线路用 `continues: true` 标记。
- `hooks` **必填数组，可为空**：本卷伏笔账，规则见 [伏笔账](#伏笔账卷纲声明章纲执行)。
- 终卷与单卷作品不要求新增跨卷伏笔、新威胁或后续卷依赖；新埋设为空仍须按章纲承接并结清前卷真实待结义务。自然语言结局与余韵由作者判断，完本机械闭合沿现有规则执行。
- `style.trend` **必填**（具体文字，说明本卷文风怎么走、相对首章定调有何变化）；`style.window` 可选，逐项覆盖契约 `style_window`。见 [文风](#文风)。
- `resources`/`places`/`characters`/`knowledge`/`relations`/`reader_knowledge` 引用的 key/entity 必须存在于世界模型或既有状态；`window` 落在本卷章号区间。
- `relations`/`reader_knowledge` 是**可选终值，声明才核对**：留空数组就是不声明本卷这项终值，卷末闭合免检。`relations` 每条 `{source,target,key,to,reason}`，source/target 须已登记且不相等，key 不含 `:` 与 `>`，`to` 用稳定短词（章纲增量的 to 与它逐字同源）；`reader_knowledge` 每条 `{topic,to,reason}`，`to` 取披露档位，核对对象是本卷章纲 `disclosures` 声明的最后档位（本卷不再推进的 topic 取已结算投影）。
- `clock.advance_days` 是本卷推进天数，`clock.to` 是卷末主线时钟绝对值；均为非负整数。人物 `to` 使用与章纲相同的三字段对象，卷末逐项核对。
- `exit_state` 必须非空，保存卷末局面的文字说明；它的自然语言含义不作机械验收。闭合判据来自资源、位置、知情、结构化人物终值、关系与读者认知的声明终值和 `clock.to`。

### 校验与失败

提交时引擎机械校验：卷 id 与 `contract.volumes` 一一对应且顺序一致；每卷汉字数落在 `words±tolerance`；node/thread/hook id 全书唯一且不覆盖已批准 id；`resources/places/knowledge/characters/relations/reader_knowledge` 引用的 key/entity/两端实体存在（relations 的 source≠target，key 不含 `:` 与 `>`；reader_knowledge 的 `to` 取披露档位）；`window` 落在本卷章号区间；`exit_state` 非空；`hooks` 的窗口与跨卷标记自洽（见 [伏笔账](#伏笔账卷纲声明章纲执行)）；`style.trend` 非空。任一项失败时提交被拒（`design_drift`），保持原任务并按具体错误重交，不消耗正文返修额度。

通过全部机械校验的回执**落库前先进入待认可暂存**：卷纲（合并档连同其章纲与结算行）保存在 `pending_design`，引擎返回 `await_volume_confirm` 并物化 `work/volume-board.md` 与 `work/volume-question.json`；看板概览并链接 `work/volume-design.md`，详情按卷或章展示完整卷纲和本次合并章纲、结算行，作者用 `confirm-volume --hash volumes_hash --source 原话` 认可后，两半才在同一事务安装。新暂存的 hash 绑定上述三部分；旧版待认可项目保留卷纲专用 hash，卡片会提示其范围，作者应核对合并内容，章纲与执笔随之继续。轻调叙述面用 `revise-volume --file 调整.json --hash --source`（白名单 purpose/arc/turns/climax/exit_state/style.trend，结构化字段拒绝并指向重出）；带理由退回用 `regroup-volume --hash --reason 原话 [--blueprint 档名]`，理由进入下一次卷纲派工的冻结输入（`volume_rejections` 记录）。看板附一组只警不拦的 advisory，作者坚持以作者为准，它们没有也不可能有升级为阻断的开关：跨卷两条——至少两卷时比较本批次与相邻已认可前卷，threads/hooks 全无 continues 提示「卷间纠缠缺位」，各卷 turns 恰两条且位置全为卷中/卷尾提示「转折位置模板同构」（单卷样本不做跨卷判断）；卷形两条——某卷转折可定位且都落在卷首与卷尾、中段三分之一没有任何转折时提示「卷中空腰」，某卷伏笔窗口全部两端聚集（埋设都结束于中段前、兑现都开始于中段后）时提示「伏笔中段无活动」（两条仅对不少于 9 章的卷提示）；边界一条——相邻卷边界文本（前卷 arc/climax/末章 synopsis 对后卷 arc/首章 synopsis）出现 5 汉字以上相同片段时提示「卷间边界重叠」嫌疑：同一事件可能被前卷卷尾与后卷开场各叙述一遍，执笔到边界两章会有一章无法按纲落笔。相同片段也可能只是延续中的共同名词——同一事件重复叙述才需要处理：后卷开场承接后果而非重演当夜。

### 结构纪律

卷纲简报随每次派工携带五条**方向性**结构纪律（无机械判据，不设数值公式、不套平台公式）：①推进维度——每卷写明落在利益格局/关系/规则理解/代价累积哪些维度，只换地图换对手不算推进；②每卷结构角色不同——与已交各卷比结构职责并自审差异是否机制级，命中「新地图＋新对手＋旧账全清」化石形状须换结构角色再交（警而不拦）；③情节交错——有线多卷时用 `threads.continues` 与章纲 dormant/active 表达并行与搁置，写清与主线如何相互影响，不强制每卷多线；④有波澜——turns 要改变后半卷对抗走向，不以同义推进凑数；⑤卷间不清账——arc 开局承接前卷后果，跨卷承诺用 `hooks.continues` 带入带出。卷级转折方法见 [创意工具箱](hatch.md#卷级转折方法)；作者选定结构蓝图时（[结构蓝图目录](hatch.md#结构蓝图目录)），骨架与推进维度随派工携带，边界同上：不定事件桥段、非情节模板、无平台公式。

章级对应物（同样方向性、无机械判据，随章纲派工携带，供设计自审）：①开篇密度——开卷首章立主角处境、代价与可见钩子，开卷前几章（通常 3～5 章）内出现第一个可感知的兑现或明确承诺，让期待感尽早落地；②相邻章不同型压力——连续章不以同型「对手出招→当众化解→口碑+1」微循环推进，同型化解不连用；③兑现间隔——长短线伏笔的 plant 与 payoff 之间不长期无钩子活动，长线跨 10 章以上时中段以 `hook_refs` 再提维持期待；④章尾推力——章纲 synopsis 的「对下一章的推动」落到实处，或以 `pacing.end_push` 写明本章结尾把读者推向下一章的方式（静章内收时写明为什么内收同样有效）。

## 章纲

### 参数与范围

`chapter_outline={scope:'volume',words:150,tolerance:60}`：`words` 是**每章 synopsis** 的汉字数，`scope` 为 volume（进卷前交本卷）或 all（正文开始前覆盖全部卷）。引擎仍按卷派发章纲任务，按实际 scope 完成所需覆盖。

### 回执形状

```json
{"volume": "v1", "chapters": [{
  "chapter": 1,
  "synopsis": "行动、阻力、选择、代价、结果、对下一章的推动（words±tolerance 汉字）",
  "beats": ["开场处境一句话", "推进到什么处境", "停在余波上的一句"],
  "role": "转折章：落地卷纲第二条转折（at 第14章附近）",
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
  "relations": [{"source":"hero","target":"foil","key":"alliance","from":null,"to":"戒备","reason":"…"}],
  "clock": {"advance_days": 1},
  "enter": [{"kind":"resources|places|knowledge|relations|clock|character|node|thread","key":"…","expected":0}],
  "exit":  [{"kind":"resources|places|knowledge|relations|clock|character|node|thread","key":"…","expected":3}],
  "disclosures": [{"topic":"…","after":"hinted","note":"双层揭秘的外层先立，内层留到第N章窗"}],
  "world_refs": ["geography:luoxia"],
  "new_entities": [{"id":"…","kind":"character|place|item","name":"…","role":"…","desire":"…","limit":"…","knowledge_boundary":"…"}],
  "hook_refs": [], "reader_refs": [], "history_refs": [],
  "scenes": [], "pacing": {"end_push": "…", "note": "…"},
  "story_events": [], "reader_effect": null, "timeline": null
}]}
```

- **必需**：`chapter` `synopsis` `plot.beat` `enter` `exit` `world_refs`。模板显式列出五个增量数组（`resources` `places` `knowledge` `characters` `relations`），便于逐类核对；空数组、缺字段和 null 均表示本章没有这类变化——`relations` 与前四类同义，不写就是「本章无关系变化」。写入的变化仍须通过完整形状与状态校验。
- `beats`（可选，元素为非空文本的数组）按**读者阅读顺序**表达叙述推进意图，可只写一拍或停在余波上，也可包含倒叙、插叙与双线交替。它不定义事件发生顺序：显式故事时间由 `timeline` 表达，累计天数由 `clock` 核算，场景引用与依赖沿 `scenes` 的既有协议；不能用拍序改写已发生事实、前态或知情边界。不定拍数与每拍字数、不把拍当正文小标题、禁平台爽文公式。
- `role`（可选，一句话）说明本章对卷内故事的实际作用。相邻多章可共同承担一场调查、战斗、谈判或情绪余波，不要求每章换职责名；应看各章实际提供的压力、认识、情绪或后果。卷纲 `turns`／`climax` 可以跨多章展开，承担章可说明自身完成的部分。角色标签不机械证明转折已落地，连续阅读效果由创作者判断。
- 作者绑定结构蓝图时，章纲材料携带 `blueprint`，其骨架与推进维度用于分派，不定事件桥段、非情节模板。`beats`／`role` 缺省合法，给了只查形状，且**缺省不落键**，存量章纲行摘要和保留后缀重排的比对保持稳定。
- `plot.threads` 同时是本章交织申报：本章推进哪条线、以什么方式触碰哪条线（轻触不改状态可重申 `active`，`reason` 写触碰方式与该线同本章主推进的相互影响）、搁置哪条线（`dormant`+`return_by`）；不要求每章动所有线，写进本章的线要有申报。章内两线如何交替叙述属拍/场层，由 `beats`/`scenes` 表达。
- `disclosures` 登记本章实际向读者呈现的线索、误导或确认；每条 `topic/after` 都进入认知核账，需正文证据。其可选 `note` 只解释**这次实际披露**的节奏，如「确认了外层身份，暂不解释其动机」；note 自身不参与结算，不能覆盖 after 的披露边界。若本章仅暂不揭示、没有相关信息呈现，不为备注而新增披露条目；意图写入现有 `pacing`（如 `pacing.note`）或 `scenes.intent`，它们不新增认知核账项。
- 分层揭秘用独立稳定 `topic` 区分可分别判断的命题（例如外层身份与内层动机），分别安排披露；没有新呈现的内层可以不声明本章变化。允许一章连进、间隔多章或外层 confirmed 而内层仍 hinted，不用同一 topic 的文字备注冒充两个认知状态。不涉及披露时 `disclosures:[]` 合法，卷末仍按已声明的读者终值闭合。
- `hooks` **必填数组，可为空**：本卷伏笔的执行，`action` 只有 `plant` 与 `payoff` 两个值；中途“再提一次”用 `hook_refs`，不新增动作。见 [伏笔账](#伏笔账卷纲声明章纲执行)。
- `style`：`pov` 与 `rhythm` 必填，`dialogue_ratio`（0~1）与 `notes` 可选。见 [文风](#文风)。
- `scenes`/`pacing` 是当前章纲的可选字段：分场是场景质感的容器，对话场/动作场/日常场等类型写进 `label`/`intent`（方向自定），需要写手按场展开时给 `scenes`，不强制每章分场；`pacing` 有两个约定键——`end_push`（章尾推力：本章结尾以什么把读者推向下一章——外推悬念、未消化的余波或明示的下一步；静章内收时写明为什么内收也是有效填写）与 `note`（其他节奏意图说明，不参与核账），键缺省合法、给了只查非空文本。开卷前五章与卷末章建议填写 `end_push`，让断章钩子从纯文字习惯变成章纲里可对照的结构位（纪律背景见 [结构纪律](#结构纪律) 的章级对应物）；`hook_refs`/`reader_refs`/`history_refs` 指出本章要承接的旧承诺、旧认知与历史断言。写日常呼吸、关系场面或生活器物的章，把要用的 `everyday`/`society`/`characters` 域记录在 `world_refs` 点名——必读材料按显式引用、出场人物及直接关联筛选；其他世界记录仍可沿冻结来源补读。
- `story_events`/`reader_effect`/`timeline` 同为可选结构表达（章行模板已带空缺省）：`story_events` 可列本章实际发生的具体事件；`reader_effect` 单列读者效果，不结算事实、不能写成角色台词或事实证据；`timeline` 声明与锚点章的显式故事时间关系（parallel/flashback 等）与已知分钟区间，不按章号分配天数。已登记未结期限须在后续主线章保留，跨过期点时须给 fulfilled/failed/abandoned 结算——完整规则以 [质量与宿主](quality.md) 的时间线与期限一节为准。
- `new_entities` 在首次登记时内联给出档案，落地后按 id 引用。人物须有完整基础字段，显式核心人物须有小传来源；与冻结世界核对身份，地点和物品不套人物字段，统一见 [人物档案](editorial.md#人物档案)。
- 每章 synopsis 交代实际发生的事、人物处境与本章阅读作用；行动与后果可跨章承接，不强求每章齐备一套节拍。引用真实世界记录与卷纲已登记的节点/线路/伏笔。

**状态链坐标速查**（enter/exit 的 `key` 写法，增量行的字段与其一致）：

| kind | key 形态 | 说明 |
|---|---|---|
| `resources` | 资源名（asset，如 `灵砂`）或完整坐标 | 引擎按 `holder/asset/unit` 三段存储坐标；key 写资源名时可唯一解析即通过，同一资产多持有方时须写完整坐标。只能作用于约定 `initial_resources` 或既有状态已登记的坐标——设计链不能凭空确立新资源（要写资源变化，先在世界任务的约定里登记起点）。 |
| `places` | 实体 id；`expected`/`from`/`to` 用地点 id 或世界模型里的同名地名（引擎归一为 geography id） | 新地点先经本章 `new_entities`（kind=place）登记，之后的章才能引用；移动的实体须已有初始站位（约定 `placements`），没有初始站位的实体建立不了位置坐标。 |
| `knowledge` | `who:topic`（冒号连接实体 id 与话题） | 档位 hinted/suspected/misled/confirmed/retracted；`suspected` 与 `hinted` 同档参与倒退校验。世界模型里的人物不会自动进入 state.entities：写知情/人物增量前，该人物须已由约定 entities 或 `new_entities` 登记。 |
| `character` | 实体 id | `to` 为 `{desire,stance,relationship_focus}` 结构；增量行另需 `choice`/`cost`。 |
| `relations` | `source>target:key`（增量行的 source/target/key 拼成同一坐标） | 第五类增量数组 `relations=[{source,target,key,from,to,reason}]`：两端用已登记实体且不相等，key 是关系名（不含 `:` 与 `>`），`to` 用稳定短词；章 N 的 `to` 就是章 N+1 的 `from`，逐字承接，首次确立才允许 `from:null`。结算复用既有 relation 事件写入 `state.relations`，供后章材料与派工 baseline 读取。 |
| `node`/`thread` | 节点/线路 id | 本章增量涉及或进入条件用到的 node/thread，**enter 与 exit 都要列**；thread 的 exit 同样参与 `exit==enter⊕增量` 核对。 |
| `clock` | `clock` | `expected` 为累计天数绝对值，增量行用 `advance_days`。 |

### 卷内状态链与校验

1. 章号连续，恰好覆盖本卷 `[volume.first, volume.end]`（`scope=all` 时覆盖整卷）。
2. `synopsis` 汉字数落在 `words±tolerance`；同一 synopsis 内 6 汉字以上的分句逐字重复按 `chapter_filler` 拒绝——下限宁缺毋凑：删去重复后仍短于下限时，压缩事件或把事件并章后按区间重写，不以复沓凑字。
3. 每行增量形状合法：`from`/`to` 类型一致，`reason` 非空；resource 有 key 且存在于世界或既有状态；place 存在于世界 geography；relations 的两端实体已登记、source≠target、key 不含 `:` 与 `>`；node/thread/hook 属于本卷卷纲已登记集合（hook 另见跨卷带入规则）。
3a. 可选结构表达字段给了才查、缺省合法：`beats` 须为数组且各元素为非空文本（空数组合法），`role` 与 `disclosures[].note` 须为非空文本；`beats`/`role` 缺省不落键，存量章纲行的整行摘要保持稳定（保留后缀重排不受影响）。
4. **enter/exit 冗余一致性**：`exit` 必须等于 `enter ⊕ 本章增量`（引擎自己算一遍比对）。任一侧缺项即漂移，拒绝。
5. **卷内状态链模拟**：从卷起始真实状态出发逐章应用增量，要求第 i 章 `enter` 恰好等于模拟到第 i 章开始的状态。模拟中拒绝：资源为负、`clock` 倒退、位置跳变到未登记地点、知情倒退（`retracted` 除外）、人物变化缺 `choice`/`cost`、关系坐标引用未登记实体或章间 `from`/`to` 措辞不逐字承接、同一 node 重复 `advanced` 或 resolved 后再推进、thread resolved 后重用，以及伏笔的重复埋设/重复兑现/越窗/未埋先承接（见 [伏笔账](#伏笔账卷纲声明章纲执行)）。
6. **卷末闭合**：最后一章模拟结果必须等于卷纲声明的 `resources/places/knowledge/characters` 结构化终值、声明了的 `relations` 与 `reader_knowledge` 终值（未声明免检）与 `clock.to`（容差 0）；整卷模拟还核对 `clock.advance_days`。本卷 `required: true` 的伏笔须全部 `paid`。`exit_state` 只作文字说明。

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

这些事件由 `drift_reconcile.reconcile` 从章纲行加 `drift_check` **产出，写手不手写事件**。`drift_check.items` 因此新增 `kind='hook'`：`planned={'action':'plant'|'payoff'}`、`actual={'action':…}`、`evidence` 为正文引文。

`state.hooks` 保存承诺状态，页面据此展示；`complete()` 拒绝仍开放的承诺。

## 文风

文风从作者约定、人物处境与本章阅读效果判断。默认 `style_guard=observe`：相对首章的句段与对白密度变化作为观察返回，不因形状不同强迫正文返修；作者明确选 `strict` 时才按容差约束首章形状。显式章纲对白目标与高重复检查在两档都生效。代词统计在两档都只观察，不自动裁决实际视角。

### 规格：卷纲与章纲各自声明

- 卷纲 `style.trend`（必填）写具体叙述意图，例如人物关系渐近时对白由试探变得直接；可带 `style.window` 逐项覆盖契约容差。作者要求量化时才选择数字目标，不为写趋势硬设配额。
- 章纲 `style` 的 `pov`、`rhythm` 必填；`dialogue_ratio`（0~1）与 `notes` 可选。视角沿用作者约定，节奏结合当章内容；未声明对白目标就不补比例，`notes` 不是绕过事实约束的豁免。
- 首章样本提供叙述气质和表达依据，静章、争吵、追逐与独处可以有不同的句段和对白密度。具体语言取舍见 [文风机制与生效档案](style.md)，原文诊断见 [人物与表达的真实感](craft.md#人物与表达的真实感)。

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

锚点缺失时回落到契约 `style_profile` 所选内置档案的注册锚点（`contracts.profile_anchor`；未知或缺失档名按引擎默认档，项目根 style-profile.md 只替换文学档案，机械锚仍取契约内置选择，不因自定义文件改为引擎默认档）：形状指标照常比较——observe 档记为观察、strict 档产生 findings——报告标注基线为声明锚（含档名）而非作者认可，首章认可后由实锚替换。显式对白目标与重复度检查不变；明确声明对白目标 0 时，非零对白仍产生偏差；未声明时，独处章没有对白可以是正常阅读需要。

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
      "kind": "resources|places|knowledge|characters|relations|clock|node|thread|hook|disclosure",
      "key": "spirit-stone",
      "planned": {"from": 0, "to": 3},
      "actual":   {"from": 0, "to": 3},
      "status": "kept|deviated|skipped",
      "reason": "deviated/skipped 必填",
      "evidence": {"chapter": 1, "quote": "正文原文片段"}
    }],
    "introductions": [{"entity":"本章新实体ID","evidence":{"chapter":1,"quote":"包含名称或已登记别名的正文原文","start":123}}],
    "unplanned": [{"kind":"knowledge","key":"hero:t2","actual":{"from":null,"to":"hinted"},"reason":"本章新增线索","evidence":{"chapter":1,"quote":"正文中的完整必要引文"}}],
    "verdict": "clean|deviated"
  },
  "self_check": "逐项说明本章与章纲的比对结论（不得为空）"
}
```

`kind='hook'` 的行用动作而不是前后值：`planned={'action':'plant'|'payoff'}`、`actual={'action':…}`，`evidence` 仍是正文引文。

`kind='relations'` 的行 key 是 `source>target:key` 坐标：`planned/actual` 的 `to` 用稳定短词，`kept` 时必须与章纲逐字相同；`actual.from` 由引擎投影，派工 baseline 的 `relations` 表就是两章之间的真实关系现状。

`introductions` 可省略或为空；每行只指本章 `new_entities` 中一个不重复的 id，引文须属于本章且包含其名称或已登记别名。省略时程序从正文定位名称或别名；找不到则以 `drift_evidence` 进入本章返修，不登记实体。用称谓出场须先在档案 `aliases` 声明，不能拿无关引文代替。名称出现只证明有字面依据，实际身份、行动与人物可信度仍须结合上下文核对。

上例同时列出失败诊断字段。可入库稿须所有项为 `kept`、`unplanned=[]` 且 `verdict=clean`；发现偏差先按原章纲修正文，再按最终正文重新填写，不能只改回执结论。`disclosure` 用 `planned/actual={'after':披露档位}`。

引擎核算（零派工）：

1. `items` 必须**恰好覆盖**本章纲的全部计划增量（普通项按 kind+key，伏笔按 kind+key+action 区分）；漏项/多项 → `drift_coverage` 拒绝。
2. 前态取自引擎投影；填写的 `actual.from` 必须与该值相等；不等 → `drift_before` 拒绝。
3. 已生效章纲是固定契约。`status=kept` 时实际结果必须等于章纲的计划结果；`deviated`/`skipped` 即使给出理由也产生 `outline_alignment`，候选保留并返修当前正文，不能入库或自动改纲。
4. `unplanned` 只报告待修正文中的计划外变化，不授予新增事实的权限。资源/位置/知情/人物变化仍需具体前后值、原因和引文供诊断；通过时必须为空。读者披露与其他计划增量一样逐项自比，不由引擎默认为已落实。
5. `evidence.quote` 必须是正文原文片段，走精确引文校验。
6. 通过后原子入账：复用事实、叙事与空间的既有机械判据（`facts.settle` 及其调用的叙事、空间规则），事件来源是 `drift_check.items`；伏笔事件由 `drift_reconcile.reconcile` 产出。
7. 通过时所有计划项均须落实、无跳过或计划外变化，`verdict=clean`。失败只沿本章有界返修推进，章纲、后文计划和正式事实保持原样。章纲确有矛盾时保留现场交作者决定；作者明确发起的改纲或历史修订才进入对应重排流程。
8. 其余既有闸门保留：字数区间（`word_budget`）、`lint.draft_findings`、字面约定（`literal_policy`）、禁用名，以及文风代理指标（见 [文风](#文风)）。

## 篇幅与上下文

跟踪项目允许长章短章共同满足总区间；chapter_max 可以高于全书平均上限。每章 word_budget 给出 minimum/maximum/aim，根据剩余章数和真实累计篇幅计算可完成范围；窄范围修订同时预留原样携带后缀的固定篇幅。字数不足或超范围的实际稿仍留档并消耗既有修复额度。无法达到目标时明确 `word_budget` 拒绝，修订前文或由作者改约，不降低目标。

执笔读取冻结的 `chapter_outline` 和本章相关 `volume_outline`，完整卷纲可通过 `complete_volume_outline` 补读；前置结果见投影状态。当前状态供参与人、当前动机、近期成长和相关承诺使用，承诺按到期、显式 `hook_refs`、相关人物/物品及话题选择，完整状态保留 `complete_state`；关系现状随状态视图与派工 baseline 的 `relations` 表携带（键为 `source>target:key`）。世界采用直接关联；world_records 为可见材料，幕后真相保留可选 world_author_records，disclosure_boundary 明确本章允许披露与读者前态。执笔的必读/载荷带契约文风（`voice`/`style_traits`/`tone`/`pov`）、`style_anchor` 样本、本卷 `style.trend` 与本章 `style`。

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

句段取舍以 [文风](style.md) 为唯一源，判据用作者文风、首章锚点和本章 style，不以句长统一作品声线。
