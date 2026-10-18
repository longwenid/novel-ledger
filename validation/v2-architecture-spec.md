# novel-ledger 五步流水线（v2）架构规范 — 冻结版

作者决定（2026-10-18）：流程改为五步；**设计层审查与章级独立审全部取消**；删除 `book_plan` 与 `volume_plan`，世界模型直接产出各卷卷纲。
目标：在设计前期用**机械状态链**消除资源漂移，把判据从"写完之后靠独立审稿者"前移到"章纲声明 + 引擎核算"。

本文件是唯一接口契约。任何一格字段名、函数名、阶段名以本文件为准；实现者不得自行改名（要改先找 Lead）。

---

## 0. 一句话架构

> **章纲取代 plan 作为结算契约；执笔的 `drift_check` 取代审稿回执作为事件来源；引擎的机械校验强度不变（facts.settle / spatial / narrative / ledger / lint 全部保留）。**
> 删掉的是"独立审稿者这个 agent 与它的派工"，不是"核对"本身——核对变成零派工成本的引擎核算。

## 1. 阶段图（冻结）

| 步 | 阶段 | 派工形态 | 产物 |
|---|---|---|---|
| 1 | `opening_options` ×10 门 | 主干自执（不变） | `opening_choices` / `opening_basis` |
| 2 | `world_model`（payload.also=opening_contract） | 1 次 | world + contract（机械校验，无 review） |
| 3 | `volume_outline` | 1 次（scope=all 时含全部卷；rolling 时进卷前 1 次） | 每卷约 1000 汉字的极简卷纲 |
| 4 | `chapter_outline` | 每卷 1 次（进入该卷前） | 该卷每章极简章纲（资源/位置/情节/知情/人物/时钟增量 + enter/exit） |
| 5 | `write` | 每章 1 次 | 正文 + `drift_check` 自比对 + 引擎核算入账；不符→`repair`/`redesign` 有界返修 |

### 新 STAGES（唯一集合，共 8 个）

```python
STAGES = frozenset({
    'opening_options', 'opening_contract', 'world_model', 'volume_outline',
    'chapter_outline', 'write', 'repair', 'redesign',
})
```

### 从 STAGES 与派工中删除（共 13 个）

`world_review` `contract_review` `design_review` `outline_review` `chapter_review`
`book_plan` `volume_plan` `plan` `profiles`
`scope_review` `scope_synthesis` `revision_review` `alignment_plan` `alignment_review`

删除方式：阶段名从 `stages.STAGES` 移除；`workflow.choose`/`apply` 中对应分支删除；`briefs`/`result_templates`/`context.STAGE_MATERIAL`/`stages.BLOCKS`/`contracts.ENFORCEMENT`/`contracts.AUTHOR_CHANNEL_STAGES` 中对应行删除。**不要保留"冻结旧任务仍可跑"的兼容分支**——本次是架构换代，旧 in-flight 任务由作者重新 advance。

### 保留的旧能力（不改名、不新增阶段）

- `repair` / `redesign`：额度 `REPAIRS=2` / `REDESIGNS=1` 不变；触发源改为漂移核算失败 + lint + 字数。
- 修订（revision）：`revision_run.plan_task` 改派 `chapter_outline`（payload 带 `repair=True` 与偏差清单），`revision_run.reading_task` 删除；修订收尾用机械审计（章纲覆盖 + 状态不变式 + 未决漂移清单）。
- editorial 的 `enabled/effective_contract/context_hash/scenes` 等被广泛引用的辅助函数保留；`alignment`/`closure` 依赖章审回执的部分删除（具体边界由 T1/Lead 按引用点判定）。

## 2. 契约（contract）变更

| 字段 | 变化 |
|---|---|
| `volume_outline` | 默认改为 `{'scope': 'all', 'words': 1000, 'tolerance': 100}`；`scope ∈ all\|rolling`（all=一次交全部卷；rolling=进卷前交该卷）；words 为**每卷**汉字数 |
| `chapter_outline` | **新增**：`{'scope': 'volume', 'words': 150, 'tolerance': 60}`；words 为每章 synopsis 汉字数；scope ∈ volume\|all |
| `planning_window` | 保留字段，v2 不再读取（legacy） |
| `review_interval`/`review_chunk`/`review_fanout`/`verification` | 保留字段以加载旧项目，v2 不再读取（legacy） |
| `narrative_tracking` | 保留。false 时章纲的 `plot.nodes/threads` 可空，但资源/位置/知情/时钟/人物增量仍必需 |
| `PIPELINE_SHAPES` | 重写：`{'t0': {'merge_chapter_outline': True}, 't1': {...True}, 't2'..'t5': False}`；`merge_volume_design`/`outline_batch`/`merge_contract_review` 三个旧键删除并同步删除其守卫测试 |

## 3. `volume_outline` 回执形状（每卷约 1000 汉字）

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

校验（新 `drift.validate_volume_outline`）：卷 id 与 contract.volumes 一一对应且顺序一致；每卷汉字数落在 `words±tolerance`；node/thread id 全书唯一且不覆盖已批准 id；`resources/places/knowledge/characters` 引用的 key/entity 必须存在于世界模型或既有状态；`window` 落在本卷章号区间；`exit_state` 非空。
**不再有** volume_plan 的 brainstorm/selection_reason、不再有 book_plan 的全书 threads（线路改为按卷登记，跨卷线路用 `continues: true` 标记）。

## 4. `chapter_outline` 回执形状（极简章纲，漂移字段必需）

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

- 必需：`chapter` `synopsis` `plot.beat` `enter` `exit` `world_refs`。四个增量数组可空数组但**不得省略**（空数组=本章无该类变化，这本身就是声明）。
- `scenes`/`pacing` 可选，保留工作台兼容（原 plan 的 scenes/pacing 语义原样搬到章纲行）。
- `new_entities` 取代 `profiles` 阶段：新人物首次出现时在本章内联给出档案字段。

### 章纲的机械校验与卷内状态链模拟（`drift.validate_chapter_outline`）

1. 章号连续、恰好覆盖本卷 `[volume.first, volume.end]`（或 `scope=all` 时的整卷）。
2. `synopsis` 汉字数落在 `words±tolerance`。
3. 每行增量形状合法：`from`/`to` 类型一致；`reason` 非空；resource 有 key 且存在于世界/既有状态；place 存在于世界 geography；node/thread 属于本卷 `volume_outline` 已登记集合。
4. **enter/exit 冗余一致性**：`exit` 必须等于 `enter ⊕ 本章增量`（引擎自己算一遍比对）。任一侧缺项即漂移，拒绝。
5. **卷内状态链模拟**（核心，解决"窗口内非节点状态不可前瞻"）：
   `drift.simulate(chapters, state0, world, volume_row)` 从卷起始真实状态出发逐章应用增量，要求第 i 章 `enter` == 模拟到第 i 章开始的状态；模拟中拒绝：资源为负、`clock` 倒退、位置跳变到未登记地点、知情倒退（除 `retracted`）、人物变化缺 `choice`/`cost`、同一 node 重复 `advanced` 或 resolved 后再推进、thread resolved 后重用。
6. **卷末闭合**：最后一章模拟结果必须满足本卷 `exit_state` 与 `volume_row` 声明的 `resources/places/knowledge/characters` 终值（容差 0）。

任一项失败 → `chapter_outline` 提交被拒（`design_drift`），修复走既有 `repair` 预算，不新增阶段。

## 5. `write` 回执形状与漂移核算（第五步）

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

引擎核算（`drift.reconcile`，零派工）：
1. `items` 必须**恰好覆盖**本章纲的全部计划增量（kind+key 各一次，不多不少）；漏项/多项 → `drift_coverage` 拒绝。
2. 每条 `actual.from` 必须等于引擎投影的当前真实值（不由写手自报前态）；不等 → `drift_before` 拒绝。
3. `status=kept` 时 `actual.to` 必须等于 `planned.to`；`deviated`/`skipped` 必须有 `reason`，并写入 `book['design_drift']`。
4. `unplanned` 中每项同样按规则 2/3 核算并登记；未登记的计划外变化（后章 `enter` 撞上）会在下一次章纲校验时暴露。
5. `evidence.quote` 必须是正文原文片段（沿用 `evidence.py` 的精确引文校验）。
6. 通过后原子入账：复用 `facts.settle` / `narrative.prepare_events` / `spatial.settle` 的既有机械判据，事件来源由审稿回执换成 `drift_check.items`。
7. 存在 `deviated/skipped` 时：本章照常入库（作者已在自比中说明），但引擎把该偏差加入 `book['design_drift']`，并在下一章派工前对该卷剩余章纲派一次 `chapter_outline`（repair=True，payload 带偏差清单）重排——这是删除 alignment 阶段后的替代路径。
8. 其余既有闸门保留：字数区间（`word_budget`）、`lint.draft_findings`、字面约定（`literal_policy`）、禁用名。

## 6. 模块与文件所有权（互斥写域）

| 所有者 | 写域（唯一写者） |
|---|---|
| **Lead** | `scripts/novel_ledger/stages.py` `contracts.py` `workflow.py` `application.py` `revision_service.py` `entities.py` `evidence.py` |
| **T1 drift** | 新增 `scripts/novel_ledger/drift.py`；`planning.py` `narrative.py` `facts.py` `spatial.py` `ledger.py` `craft.py` `story_memory.py` `revision_impact.py` `understanding.py` `book_state.py` |
| **T2 materials** | `context.py` `briefs.py` `result_templates.py` `envelope.py` `creation.py` `world.py` `delivery.py` `bookpage.py` `presentation.py` `bootstrap.py` `ports.py` `publication.py` `workspace.py` `sqlite_store.py` `host.py` `unattended.py` `store_keys.py` `novel.py`（`scripts/novel.py`） |
| **T3 docs** | `SKILL.md` `README.md` `references/*.md` `docs/README.md` |
| **T4 tests** | `tests/**`（recon 期间除外） |
| **V 验证** | `validation/**` `.team/verify-*.md` |

删除文件：`scripts/novel_ledger/scopes.py`、`quality.py`（由 Lead 在脊梁落地后删除，并同步 `tests/architecture_table.py` 的 ALLOWED 表——该文件属 T4 写域，Lead 只发指令）。

新增依赖边（由 Lead 更新 `tests/architecture_table.py` 的 ALLOWED/CORE_EXTERNAL）：
```python
'drift': {'contracts', 'entities', 'narrative', 'spatial', 'ledger', 'world', 'evidence'},
'workflow': {..., 'drift'},
'planning': {'contracts', 'entities', 'narrative', 'craft', 'story_memory', 'drift'},
'application': {..., 'drift'},
```

## 7. 判据前移的账（给作者看的收益）

以 t2 档 25 章一卷为例：旧流程 ≈ 100+ 次派工（含 2 次 world/contract 审、2 次设计审、5 次卷纲+5 次卷纲审、约 9 次 plan、25 次章审、若干范围审）；新流程 ≈ 10 门（主干自执）+ 1 次 world + 1 次卷纲 + 1 次章纲 + 25 次执笔 ≈ **28 次子 agent 派工**，且资源/位置/知情漂移在设计期就被状态链挡住。
代价（必须写进文档，不粉饰）：**没有独立 agent 复核文学质量与阅读体验**；替代物是引擎机械核账 + 执笔自比。作者若需要独立判断，只能人工抽读或另行发起修订。

## 8. 验收（V 验证位独立执行）

1. `python -m pytest tests -q` 全绿（用例数可降，但不得靠 skip 掩盖）。
2. `python -m pyflakes scripts validation tests` 0 发现（或仓库既有口径）。
3. 端到端迷你项目：用脚本（非人工）跑 opening_options→world_model→volume_outline→chapter_outline→write 全链，至少 2 卷 3 章，断言：无审查阶段派工；章纲状态链拒绝一个人为漂移样例；write 的 drift_check 漏项被拒；通过后状态正确入账。
4. 悬空引用扫描：全仓库 grep 已删除阶段名/模块名，命中处必须是有意保留的 legacy 契约字段或历史文档记录，并在报告里逐条列出。
5. `docs/architecture.mmd`/`.svg` 与 `tests/architecture_table.py` 与新模块表一致。
