# V 验证位 · 阶段一：validation/ 工具适配 v2 五步流程（终版）

> 历史归档：本文件保留当轮版本、设计或实验条件，不是当前执行规范。旧门序、兼容条款、独立审查阶段及命令均不用于当前流程；当前唯一执行依据见 [任务协议](../references/protocol.md) 与 [运行流程](../references/runtime.md)。

时间：2026-10-18 20:11–21:15（Asia/Shanghai）
写域：`validation/**`、`.team/verify-*.md`（未改 scripts/**、tests/**、references/**、SKILL.md、README.md）
说明：本文件与 `.team/verify-adversarial.md` 曾在 21:15 前后随整个 `.team/` 目录被删除，V 在 21:17 按最终树恢复并刷新为终版数字。

---

## 1. 工具适配结果（终验，21:11–21:15 冻结树）

| 工具 | 命令 | 结果 | 结论 |
|---|---|---|---|
| `measure.py` | `python validation/measure.py` | 6 节全 **ok**：graph / dispatch / material / tracked / memory / history | 已验证 |
| `reflux_probe.py` | `python validation/reflux_probe.py <project>` | 引擎核算意见 + 执笔自比偏离两源聚合；构造样本上检出「重复 1 次/共 2 次」回流候选 | 已验证 |
| `cost_report.py` | `python validation/cost_report.py --project <project>` | 按阶段输出任务数/输入/回执/磁盘（样本：3 章、6 任务、233 KB） | 已验证 |
| `run_analysis.py` | `python validation/run_analysis.py <project>` | 按阶段材料表 + journal + 磁盘账 | 已验证 |
| `required_probe.py` | `python validation/required_probe.py <project> write` | write 必读 8 份合计 6000 字符（chapter_outline 1859 / volume_outline 1663 / contract 1200 …） | 已验证 |
| `dup_required_probe.py` | `python validation/dup_required_probe.py <project>` | 必读字节重复 0 | 已验证 |
| `read_waste_probe.py` | `python validation/read_waste_probe.py <project>` | 逻辑可跑（样本无 recall，读事件 0） | 已验证 |
| `duplication_probe.py` | `python validation/duplication_probe.py <project>` | v2 仅剩 `world_core ⊂ world_model` | 已验证 |
| `anchor_check.py` | `python validation/anchor_check.py` | 15 文件、0 坏锚 | 已验证 |
| `scale_window_probe.py` | `python validation/scale_window_probe.py <project>` | 非逐门开书项目给明确出口（需逐门项目才出结论） | 无法验证（缺输入） |
| `run_tests.py` | `python validation/run_tests.py fast` / `fast --list` | 终验：FAST 全绿；`--list` rc 0、118 id、无重复、fast⊂full、5 边界前缀齐全；`unknown` rc 2 | 已验证 |

新增的独立验收入口（V 写域）：
`validation/adversarial.py`（10 个行为反例，10/10）、`validation/e2e_guided.py`（逐门开书全链，3/3）、
`validation/repro_drift_clock.py`、`repro_knowledge_readback.py`、`repro_merged_tier.py`、`repro_understanding_channel.py`（四个缺陷的回归守卫，现均 exit 0）。

**改动摘要**
- `measure.py`：删 `scopes` 导入与 `scopes.tree()` 的 `review_trees` 一节 → 改为 `dispatch` 节（按 `PIPELINE_SHAPES` × `volume_outline.scope` 机械计数五步派工）；删 `until='chapter_review'`，材料按 `world_model/volume_outline/chapter_outline/write` 四类量；`book['designs']` → `volumes_outline/chapter_outlines/plans`；不再 import `test_history`/`test_narrative`（自带 `tracked_contract`/`append_history`）；每节独立记账，失败打印 traceback 且退出码非 0。
- `reflux_probe.py`：`REVIEW_STAGES` 删除，改为「引擎核算意见（`draft.findings`/`design_drift`/`carry_findings`/`accepted_findings`）+ 执笔自比（`drift_check` 的 deviated/skipped/unplanned）」；v1 审稿回执单列并标注仅历史项目。
- `duplication_probe.py`：v1 投影对删除，改 v2 唯一投影 `world_core ⊂ world_model`。
- `scale_window_probe.py`：硬编码绝对路径改按 `__file__` 推导；非开书项目明确出口。
- `run_tests.py`：FAST 按 v2 重写（边界模块 + 五步流程形状 + 一个稳定的修订边界点名用例），`--list` 与 `unknown` 退出码口径与 tests-a 的不变量一致。
- `cost_report.py` / `run_analysis.py` / `anchor_check.py` / `required_probe.py` / `dup_required_probe.py` / `read_waste_probe.py`：无需改，逐个跑通。

---

## 2. 阶段一发现的引擎问题（全部已修复，回归脚本保留）

| 编号 | 现象 | 回归脚本 |
|---|---|---|
| BUG-0 | `drift._event_for` 读 `planned.get('advance_days')` 层级错（值在 `entry['planned']`）→ 任何时钟推进的章被 `drift_clock` 拒、返修耗尽后暂停 | `validation/repro_drift_clock.py` |
| BUG-1 | `_reveal_of` 用正向映射读结算值 → 已结算 knowledge 回读恒 None，章纲状态链死锁（第 1 章入库后 `chapter_outline` 必被拒） | `validation/repro_knowledge_readback.py` |
| BUG-2 | t0/t1 的 `merge_chapter_outline` 只被守卫测试读、引擎不消费 | `validation/repro_merged_tier.py` |
| BUG-3 | `work['prose']` 恒空 → `_sources()` 恒 `{}` → `understanding` 引文校验永远失败，创作记忆不可达 | `validation/repro_understanding_channel.py` |

四个脚本在终验树上均 exit 0（20:21/20:25/20:31/20:32 相继修复）。

---

## 3. 无法验证 / 依赖输入

1. **逐门开书路径的量测**：`support.drive()` 回答不了 `opening_options`（`response()` 交回 `gate="" options=[]`，`creation.offer` 拒绝）。V 因此在 `validation/e2e_guided.py` 里按引擎自己的 `creation.value_fields`/`world.SECTIONS`/`CONTRACT_FIELDS.opening` 机械生成方案，绕开该夹具缺口；`scale_window_probe.py` 仍需一个逐门开书项目才能给出档位窗口结论。
2. **全量 pytest / pyflakes / 悬空引用 / §8 五条验收**：见 `.team/verify-adversarial.md`（终验：pytest 全绿、pyflakes 0）。

## 4. 样本项目（非仓库文件）

`%TEMP%\nl-probe-project`（seeded 3 章，跑到 `target_reached`，3 章入库 6 任务）、`%TEMP%\nl-probe-deviated`（把 `places` 增量标 `deviated` 制造回流）。
