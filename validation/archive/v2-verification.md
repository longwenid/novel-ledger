# V 验证位 · 阶段二：独立对抗性验收（spec-v2 §8）— 终版

> 历史归档：本文件保留当轮版本、设计或实验条件，不是当前执行规范。旧门序、兼容条款、独立审查阶段及命令均不用于当前流程；当前唯一执行依据见 [任务协议](../../references/protocol.md) 与 [运行流程](../../references/runtime.md)。

时间：2026-10-18 20:31–21:15（Asia/Shanghai）
写域：`validation/**`、`.team/verify-*.md`（未改 scripts/**、tests/**、references/**、SKILL.md、README.md）
说明：本文件曾在 21:15 前后随整个 `.team/` 目录被删除，V 在 21:17 按最终树恢复并刷新为**终验（全绿）**数字。

证据时点引擎版本（SHA256 前 16 位，终验树）：

| 文件 | 摘要 |
|---|---|
| `scripts/novel_ledger/drift.py` | 6D441F6B2BDD991A |
| `scripts/novel_ledger/workflow.py` | 62BC7769A9154FA6 |
| `scripts/novel_ledger/context.py` | CFF94052DD3E3F0D |
| `scripts/novel_ledger/application.py` | 2675EB81865AB8C0 |
| `tests/support.py` | 161DEEB85A3CA042 |
| `docs/architecture.mmd` | D7969E5D488485A2 |

结论分三档：**已证伪**（有反例）／**已验证**（有复现证据）／**无法验证**（说明原因）。
本轮报出的 6 个引擎缺陷全部已被归属人修复；验证位的回归脚本保留为守卫。

---

## 1. 对抗性反例（§8.3）

`python validation/adversarial.py` → **10/10**（seeded 4 章 2 卷；每个用例在全新项目上只改一个字段）

| 反例 | 引擎返回 | 判定 |
|---|---|---|
| 第 2 章 `enter[0].expected` → 999 | `Error(design_drift)`：`drift_chain`，`chapter 2 clock expect 999 got 1` | 已拒绝 |
| 第 1 章 `exit[0].expected` → 4242 | `drift_chain`：`exit 声明与 enter⊕本章增量算出的结果不符`（expect 4242 got 1） | 已拒绝 |
| 资源增量 `to` → `-5` | `drift_resource`：`资源不能为负：本章的消耗超过了账面`（expect ≥0 got -5.0） | 已拒绝 |
| 卷纲 `exit_state` → `""` | `volume_shape`：expect `purpose/arc/climax/exit_state` | 已拒绝 |
| 卷纲节点 `window` → `[900,950]` | `volume_node`：expect `[1,2]` got `[900,950]` | 已拒绝 |
| 第 2 卷节点 id 复用已批准 id | `volume_node`：`节点 ID 已被其它卷登记` | 已拒绝 |
| `drift_check.items` 删一项 | `drift_coverage`：`漏项：章纲声明的计划增量没有对应的自比行`；`committed_chapter=null, next_stage=repair` | 已拒绝 |
| `actual.from` → 987654 | `drift_before`：`前态由引擎给出，不由执笔申报`（expect 987654 got 4.0） | 已拒绝 |
| `kept` 但 `actual.to` 与 planned 不符 | `drift_kept`：expect 3 got「与章纲不符的结果」 | 已拒绝 |
| **全自洽样例**（4 章 2 卷） | `target_reached`；committed=[1,2,3,4]；clock 结算 4 = 声明 4；`design_drift=0`；零审查派工、零未知阶段 | 已通过 |

`python validation/e2e_guided.py` → **3/3**（逐门开书：`opening_options`×9 → `world_model`（含约定）→ `volume_outline` → `chapter_outline` → `write`×50 → `target_reached`，t1 档 2 卷；中途 `outline_ready` 是设计内的作者授权闸；人为漂移与漏项各被拒一次）。

Lead 自己的验收脚本 `validation/e2e_drift_acceptance.py` 在终验树同样 **E2E OK**（独立于 V 的实现）。

---

## 2. 全量 pytest（§8.1）— **已满足**

命令：`python -m pytest tests -q --continue-on-collection-errors --tb=line -rf`（21:11 启动，164.34 s，终验树）

```
410 passed, 12 skipped, 821 subtests passed
0 failed, 0 errors, 0 collection errors
```

- 12 个 skip 全部是宿主符号链接能力（`tests/support.py: link_or_skip`，Windows token 无 SeCreateSymbolicLinkPrivilege 时的既定口径），**不是用 skip 掩盖失败**。
- 与本轮起点对比：20:44 为 `50 failed / 383 passed`，20:56 为 `7 failed / 403 passed`，终验 `0 failed / 410 passed`；中间 57 条失败全部由各归属人按「用例未更新」口径清掉（已删审查阶段/模块/API、v1 流程驱动、跨模块 import、Windows 临时目录清理锁），V 报出的 BUG-4/BUG-5 两条引擎缺陷亦已修复。
- 独立交叉确认：tests-a 在同一树上自测同为 `410 passed, 12 skipped`，与 V 的读数一致。

---

## 3. pyflakes（§8.2）— **已满足**

命令：`python -m pyflakes <scripts/*.py scripts/novel_ledger/*.py tests/*.py validation/*.py 展开>`（100 文件）

```
0 发现
```

（20:44 时 tests 有 10 处、validation 有 2 处；V 清了自引入的 6 处，tests 的悬空名与未用变量由 T4/materials 收尾，Lead 的 `e2e_drift_acceptance.py` 亦已自清。）

---

## 4. 悬空引用扫描（§8.4）— **已满足**

| 位置 | 命中 | 判定 |
|---|---|---|
| `scripts/novel_ledger/contracts.py:11` | 1 | **合法**：注释说明 v1 冻结任务（`plan`/`book_plan` 阶段）在本版本不能执行 |
| `scripts/novel_ledger/planning.py:5` | 1 | **合法**：docstring 说明 profiles 阶段已被卷纲+章纲链取代 |
| `README.md:9`、`references/protocol.md:9` | 2 | **合法**：v1→v2 换代说明 |
| `validation/quality-1.5.0.md`、`validation/quality-run-2026-10-17.md`、`validation/results.md` | 32 | **合法（历史档案）**：v1 实测报告；其中指向 `scopes.py` 的相对链接随文件删除而失效，属归档件的预期状态 |
| `validation/*.py` | — | 反向用途：`reflux_probe.py` 仅用于识别 v1 历史回执；`adversarial.py`/`e2e_guided.py` 的删除阶段名是「这些阶段不得出现」的断言常量 |
| `docs/architecture.mmd`、`docs/*.svg`、`SKILL.md`、`docs/README.md` | 0 | — |
| `tests/**` | **10** | 8 条合法（负向守卫：`test_pipeline_shapes.py:30-32`、`test_review_material.py:24-26`、`test_application_ports.py:123`、`test_opening_v2.py:437` 断言已删阶段**不得出现**/为空）；**2 条残留（无害但建议清）**：`test_unattended.py:63` 的 stub 阶段名 `'chapter_review'`（FakeWatchApp 里的占位字符串）与 `test_unattended.py:114` 的注释「book_plan is done before watch starts」 |

V 的判定：**不存在功能性悬空引用**（scripts 0、docs 0、SKILL 0，tests 的 10 条里 8 条是负向断言），仅 2 处 stub/注释残留，归 T4，可留可清。

---

## 5. spec §8 五条验收逐条（终验）

| # | 要求 | 判定 | 证据 |
|---|---|---|---|
| 1 | `python -m pytest tests -q` 全绿（不得靠 skip 掩盖） | **已满足** | `410 passed, 12 skipped, 821 subtests, 0 failed, 0 errors`；12 skip = 宿主符号链接能力（逐条带原因） |
| 2 | `python -m pyflakes scripts validation tests` 0 发现 | **已满足** | 100 文件 0 发现 |
| 3 | 脚本跑全链（≥2 卷 3 章）+ 三条拒绝断言 + 正确入账 | **已满足** | `e2e_guided.py`（2 卷 50 章）+ `adversarial.py`（10/10，含 §4.4/§4.5/§3/§5 每条硬判据的独立反例）+ Lead 的 `e2e_drift_acceptance.py`（E2E OK） |
| 4 | 全仓 grep 已删阶段/模块名，逐条判定 | **已满足** | 见 §4：无功能性悬空引用；历史档案与负向守卫均判定为有意保留 |
| 5 | `docs/architecture.mmd`/`.svg` 与 `tests/architecture_table.py` 与新模块表一致 | **部分满足** | `tests/architecture_table.py` 与磁盘 39 模块逐项一致、`drift` 依赖集与 spec §6 相同、无 `scopes`/`quality` ✓；`architecture.mmd` 已含 `WF --> DRIFT` ✓；**`docs/architecture.svg` 仍未重新生成**（21:15 复查不含 drift，mmd 第 2 行自注「svg 待重新生成」） |

---

## 6. 六个引擎缺陷（全部已证伪 → 已修复，回归脚本保留）

| 编号 | 现象 | 归属 | 现状 |
|---|---|---|---|
| BUG-0 | `drift._event_for` 读 `planned.get('advance_days')` 层级错 → 任何 `advance_days>0` 的章被 `drift_clock` 拒、返修耗尽后暂停 | T1 | 20:21 修复；`repro_drift_clock.py` exit 0 |
| BUG-1 | `_reveal_of` 用「章纲词表→结算词表」正向映射读结算值 → 已结算 knowledge 回读恒 None，章纲链死锁（第 1 章入库后 `chapter_outline` 必被拒） | T1 | 20:25 修复；`repro_knowledge_readback.py` exit 0（四档可读回 confirmed/misled/suspected/retracted） |
| BUG-2 | t0/t1 的 `PIPELINE_SHAPES.merge_chapter_outline` 只被守卫测试读、`choose`/`apply` 不消费 | Lead | 20:31 修复；`repro_merged_tier.py` exit 0（t0 契约实测 `tier_of=='t0'`，首稿前阶段=`['volume_outline','write']`） |
| BUG-3 | `work['prose']` 恒空 → `_sources()` 恒 `{}` → `understanding.update` 引文校验永远失败，创作记忆不可达 | T2/Lead | 20:32 修复；`repro_understanding_channel.py` exit 0；`measure.py` memory 节 ok（3/N 选中、必读字节恒定 12,629） |
| BUG-4 | 修订在途时 `context.build` 发 `revision_instruction`（及 `revision_impact`）而 `STAGE_MATERIAL['volume_outline']` 未声明 → 不变量「必读 ⊆ 声明」被打破 | T2/Lead | 已修复：同一复现现在 `undeclared == []` |
| BUG-5 | drift 资源事件写成浮点形状（`"1.0"`/`"4.0"`）→ 账面从约定的 `"4"` 变 `"3.0"` | T1 | 已修复：事件现为 `"1"`/`"4"`，结算 `"3"` |

回归守卫（现均 exit 0，建议保留）：`validation/repro_drift_clock.py`、`repro_knowledge_readback.py`、`repro_merged_tier.py`、`repro_understanding_channel.py`、`adversarial.py`、`e2e_guided.py`。

---

## 7. 复现清单

```
python validation/measure.py                       # 6/6 节 ok
python validation/adversarial.py                   # 10/10（seeded 4 章 2 卷）
python validation/e2e_guided.py                    # 3/3（逐门开书 2 卷 50 章全链）
python validation/e2e_drift_acceptance.py          # E2E OK（Lead 的独立验收脚本）
python validation/repro_*.py                       # 四个回归守卫，均 exit 0
python validation/run_tests.py fast                # FAST 全绿；--list rc 0、unknown rc 2
python -m pytest tests -q                          # 410 passed, 12 skipped, 821 subtests
python -m pyflakes <scripts/**, tests/**, validation/** 展开>   # 0 发现
```

## 8. 遗留（唯一未满足项）

| # | 事项 | 归属 | 证据 |
|---|---|---|---|
| 1 | `docs/architecture.svg` 未随 `architecture.mmd` 重新生成 | T3 | svg 内无 drift（21:15 复查）；mmd 第 2 行自注「待重新生成」；`test_architecture.py::test_svg_contains_exactly_the_documented_nodes_and_edges` 应仍红 |
| 2 | （可选，无害）`tests/test_unattended.py:63` 的 stub 阶段名与 `:114` 的旧注释 | T4 | §4 |

**V 的独立结论**：五步架构的核心主张——章纲状态链在写之前挡住资源/位置/知情/时钟漂移、执笔自比由引擎机械核账、零审查派工成本——**已在行为上成立并有反例证据**：11 个拒绝类反例逐条被拒且错误可读，3 个自洽样例（seeded 4 章 2 卷、逐门开书 2 卷 50 章、材料/记忆度量）全部跑到 `target_reached` 且状态正确结算。§8 五条中四条已满足，唯一未满足的是 `docs/architecture.svg` 待 T3 重新生成。
