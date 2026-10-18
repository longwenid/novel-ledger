# opening/5 验证报告（V 验证位 · task-24）

时间：2026-10-19 01:33–02:02（Asia/Shanghai）｜Lead 广播「核心已落地，树已绿」后的全量复跑：01:56–02:01
写域：`validation/**`（未改 scripts/、tests/、文档；既有历史报告的结论未动）
规格：`validation/opening5-spec.md`（冻结，§4 门校验 / §5 世界绑定 / §6 卷 stage / §9 验收）

证据时点版本：`VERSION 2.0.0`、`OPENING_VERSION 5`、`gate_ids(5)` 13 门、`world.SECTIONS` 12 领域。
SHA256 前 16 位：`creation.py 0A6114F62B5B4DB2`、`world.py CD1202C2BFEEA64D`、
`drift.py 04195A99F13B2BFE`、`contracts.py 88D0FAE0092A7634`、`tests/support.py 4C984B967FEF2308`。

---

## 一、§9 验收逐条判定

| # | 要求 | 判定 | 证据 |
|---|---|---|---|
| 1 | `python -m pytest -q` 全绿（含子测试）、`pyflakes scripts tests validation` 无输出 | **已满足** | pytest → **526 passed, 12 skipped, 1291 subtests passed, 0 failed**（191.32 s）；pyflakes → **rc=0、无输出** |
| 2 | 新增用例覆盖 13 门 guided opening、premise 枚举/长度/告警、world.tiers 下限与字段、ladder 单调性/防换地图/terminal/锚点上限、三条绑定失败路径、旧世界 10 域在 v4 choices 下通过、卷 stage 违反单调被拒 | **已满足（用例在 tests 侧，V 独立复跑全量）** | 上述用例随 526 passed 一起绿；V 另有独立形状与派生断言（§三/§四） |
| 3 | 既有 harness 在 13 门下跑通、`opening5-verification.md` 出结论 | **已满足** | `e2e_guided.py` **6/6**（13 门全链、12 次派工、v5 四门形状、origin 四方向、opening/3 旧项目、两条拒绝）；其余 10 个 harness 全 rc=0（§二） |
| 4 | `references/*`、`SKILL.md`、`README.md` 与实现一致（13 门、12 领域、三条绑定） | **不在本报告判据内** | 文档属 T3 写域；V 未改也未核（若需独立核文档请另派一格） |
| 5 | 派生件不提交；提交信息中文说明 | 不在 V 判据内 | 属 Lead 的提交纪律 |

---

## 二、原始计数（每条命令一行，01:56–02:01 实跑）

| # | 命令 | 原始结果 |
|---|---|---|
| 1 | `python -m pytest -q` | **526 passed, 12 skipped, 1291 subtests passed in 191.32s**（0 failed / 0 errors；12 个 skip 全为宿主符号链接能力） |
| 2 | `python -m pyflakes scripts tests validation` | **无输出，rc=0** |
| 3 | `python validation/e2e_guided.py` | **全部符合预期（6/6）**：全链自洽 / opening/5 四门值形状与领域声明 / opening/4 origin 四方向 / opening/3 旧项目 / 章纲链拒漂移 / drift_check 漏项 |
| 4 | `python validation/adversarial.py` | **10/10 用例符合预期** |
| 5 | `python validation/e2e_drift_acceptance.py` | **E2E OK** |
| 6 | `python validation/repro_hook_matrix.py` | **10/10 条符合预期** |
| 7 | `python validation/repro_hook_chain.py` | **3/3 条符合预期** |
| 8 | `python validation/repro_v21_gaps.py` | **5/5 条符合预期**（GAP-1/GAP-1b/GAP-2 回归门槛仍绿） |
| 9 | `python validation/repro_style_window.py` | **单元 9/9 + 流程 1/1** |
| 10 | `python validation/repro_merged_tier.py` | rc=0，`stages before the first draft = ['volume_outline','write']`（合并档位形状未回归） |
| 11 | `python validation/repro_drift_clock.py` | rc=0（`drift.reconcile` 产出 clock 事件、无 findings） |
| 12 | `python validation/repro_knowledge_readback.py` | rc=0（四个结算档位回读均非 None） |
| 13 | `python validation/repro_understanding_channel.py` | rc=0（`submit with understanding -> accepted`） |
| 14 | `python validation/measure.py` | rc=0（6/6 节；`dispatch` 节门表见 §四.2） |

**与 Lead 广播数字的交叉核对**：Lead 报 `525 passed / 12 skipped / 1291 subtests`，V 实测
`526 passed / 12 skipped / 1291 subtests`——**subtests 与 skip 完全一致、0 failed 一致，passed 多 1 项**。
两次运行之间树有微动（例如某个用例在此后落地）的可能性最大；此处只记原始观察，不据此推断结论。

---

## 三、重点复跑①：v5 四门值形状 + `declared_sections → powers/cosmology`

用例：`e2e_guided.py::opening/5 四门值形状与领域声明`（此前只在 01:38 的半落地树上跑出过一行，
本次为完整复跑）。**实测 `problems: []`**，逐项：

| 观测 | 原始值 |
|---|---|
| `creation.gate_ids(5)` | `genre → premise → origin → voice → scale → world → ladder → edge → protagonist → relationships → opposition → payoff → title`（13 门，顺序与 §1 一致） |
| 门序断言 | `premise` 在索引 1（紧随 `genre`）✓；`world` 在 `ladder` 之前 ✓ |
| 三案值全部通过 `creation.validate_value(gate, value, 5)` | `premise: [0,1,2]`、`world: [0,1,2]`、`ladder: [0,1,2]`、`payoff: [0,1,2]` 全部 accepted（无一被拒） |
| `world.tiers` 条数 | 3（t1 档 `tier_min['t1']=3`，正好取下界） |
| `ladder` 层级表 | `stages=['青石巷','落霞谷']`、`scopes=['局部','一界']`（按 `WORLD_SCOPES` 序号 0→3 单调不减）、条数 2（t1 档 `stage_min['t1']=2`） |
| `scale.terminal` | `'文明'`，与层级表自洽（存在 `growth='文明'` 一级） |
| `anchor` | `{'deliverable': '第 12 章前必须让读者看见：那次退件登记的代价由谁承担。', 'deadline_chapter': '12'}`；纯数字、12 ≤ min(30, t1 章窗上限 57)=30 ✓ |
| `world.declared_sections(...)` | **`['powers', 'cosmology']`** ✓（声明了 `tiers` → `powers`；阶梯触到 `一界` ∈ `COSMOLOGY_SCOPES` → `cosmology`） |
| `world.required_sections('t1', ...)` | 已并入 `powers`/`cosmology` ✓ |

**世界模型 12 领域**：`world.SECTIONS` 实测 12 项（既有 10 项逐字未变，末尾追加 `powers`、`cosmology`）。
`e2e_guided.world_receipt()` 按 §5.4 写三条逐字绑定——门里声明的 `tiers` 逐字进 `powers`、
`resource.name` 进 `economy.resource` 且分配者出现在记录文本、每个 `stage` 在 `geography` 有同名记录——
该回执在 13 门全链里被引擎接受（§四.1），即三条绑定在「应通过」方向成立；三条绑定的**失败路径**由
tests 侧用例覆盖（随全量 526 passed 一起绿）。

---

## 四、重点复跑②：13 门全链与「12 次派工」派生断言

### 4.1 `e2e_guided.py::全链自洽（逐门开书→完稿）`

| 观测 | 原始值 |
|---|---|
| `opening_version` | **5** |
| `gate_count` | **13** |
| `expected_opening_options_dispatches`（= 门集 − `SYSTEM_GATES[5]`） | **12** |
| `opening_options_dispatches`（实测） | **12**（断言相等 ✓） |
| 终点 | `target_reached`；`committed` 覆盖全部目标章号；`clock_settled == clock_declared` |
| 审查阶段派工 / 未知阶段 | 均 `[]` |
| 后续链路 | `world_model`（含约定）→ `volume_outline` → `chapter_outline` → `write`×50（t1 档 2 卷） |

### 4.2 `measure.py` 的派生门表（`--only dispatch`）

```json
{"opening_version": 5,
 "gates": ["genre","premise","origin","voice","scale","world","ladder","edge","protagonist",
           "relationships","opposition","payoff","title"],
 "system_gates": ["scale"], "dispatched_opening_options": 12}
```

即 harness 里已无「10/11 门」这类写死值：门数、系统门、派工数全部由
`creation.gate_ids` / `SYSTEM_GATES` / `OPENING_VERSION` 派生——opening/6 若再插门，这些脚本无需再改。

---

## 五、harness 适配记录（只改 harness，不改引擎）

| 文件 | 是否需改 | 依据 |
|---|---|---|
| `validation/e2e_guided.py` | **已改** | 唯一走开书门的脚本：新增 `vocabulary()`（从 `contracts` 读 §2 词表与 `DEFAULTS['world_ladder']`；缺项抛 `EngineNotReady` → 记 `blocked`，退出码 2，不把「未落地」写成失败）、`value_for()` 分派 v5 四门生成、`world_receipt()` 写三条逐字绑定与 `cosmology`、新增 v5 形状用例、门数断言全派生 |
| `validation/measure.py` | 无需改 | 门表自 opening/4 起已派生 |
| `v21_harness.py`、`repro_hook_*`、`repro_style_window`、`repro_v21_gaps`、`adversarial.py`、`e2e_drift_acceptance.py`、四个 BUG repro | 无需改 | 全部用 `support.seeded_book(...)`，不经过开书门；v5 新约定字段为 `optional`，缺省不影响 seeded 契约 |

**未改动**：`scripts/**`、`tests/**`、`references/**`、`SKILL.md`、`README.md`、`docs/**`，以及
`validation/` 既有历史报告（`v2-verification.md`、`v2.1-verification.md`、`opening4-verification.md` 与
`results.md` 的既有章节）的结论。

---

## 六、结论与边界

- **结论：§9 第 1、3 条由 V 独立复跑满足（pytest 526 passed/0 failed、pyflakes 0、13 门全链 6/6、
  其余 11 个 harness 全绿）；第 2 条的用例在 tests 侧并随全量一起绿，V 另有 §三/§四 的独立形状与派生断言；
  第 4、5 条不在 V 判据内（文档属 T3、提交属 Lead）。未发现引擎缺陷，无需回报的未满足项。**
- 诚实边界：V 的 526 与 Lead 的 525 差 1 项 passed（subtests/skip/failed 完全一致），已在 §二 记为观察，
  未据此推断任何结论。
- `e2e_guided.py` 的 v5 值由脚本按引擎公开表机械生成（不是抄实现者夹具），因此它是「§4 门校验能否被
  独立构造的合法值满足」的一次独立检查；生成器只覆盖**应通过**的方向，拒绝路径以 tests 为准。
- 全文未调用模型；12 个跳过项均为宿主符号链接能力。
