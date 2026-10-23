# opening/4 追补验证（V 验证位 · task-15 追补）

> 历史归档：本文件保留当轮版本、设计或实验条件，不是当前执行规范。旧门序、兼容条款、独立审查阶段及命令均不用于当前流程；当前唯一执行依据见 [任务协议](../../references/protocol.md) 与 [运行流程](../../references/runtime.md)。

时间：2026-10-19 01:05–01:15（Asia/Shanghai）
写域：`validation/**`（未改 scripts/**、tests/**、references/**、SKILL.md、README.md）
触发：开书协议升到 **opening/4**，在门 1（`genre`）之后插入「主角来历」门，共 **11 门**。
本文只记这一增量的独立复跑；v2.1 的完整验收见 `validation/v2.1-verification.md`。

证据时点版本：`VERSION = 2.0.0`、`OPENING_VERSION = 4`；SHA256 前 16 位：
`creation.py 5C90BF2485087205`、`contracts.py 1E5FE5A80AA3BBCF`、`workflow.py B8A734772EB55A97`。

---

## 一、门序与门数（已验证，派生自引擎自己的表）

```
python -c "import sys;sys.path[:0]=['scripts'];from novel_ledger import creation;print(creation.gate_ids(4))"
→ ('genre', 'origin', 'voice', 'scale', 'edge', 'protagonist', 'relationships', 'world', 'opposition', 'payoff', 'title')
```

- `origin` 在 **索引 1**（紧跟 `genre`），与 Lead 描述一致；`creation.GATE_SETS` 现有 1/2/3/4 四套，旧门集未被改动。
- `creation.SYSTEM_GATES[4] = ('scale',)` → **11 门中 10 门派工**、1 门由引擎自执。
- 实测（`validation/e2e_guided.py` 的全链用例）：`opening_version=4`、`gate_count=11`、
  `expected_opening_options_dispatches=10`、**实测 `opening_options` 派工 10 次**（断言相等）。
- 我脚本里的「门数」不再写死：断言的期望值来自 `creation.gate_ids(creation.opening_version(state))`
  与 `creation.SYSTEM_GATES`；`validation/measure.py` 的 `dispatch` 节同样改为派生输出
  （`{"opening_version": 4, "gates": [...11 项...], "system_gates": ["scale"], "dispatched_opening_options": 10}`）。
  **这两处是本次唯一需要改的夹具代码，不是引擎缺陷。**

## 二、`origin` 门的四方向校验（已验证）

```
python -c "…; creation.validate_value('origin', {'family':…, 'arrival':'…', 'cost':'…'}, 4)"
```

| 输入 | 结果 |
|---|---|
| `family='魂穿'` / `'身穿'` / `'本土'` / `'其他'`（`arrival`/`cost` 非空） | 四个方向**全部通过** |
| `family='穿越'`（四方向之外的说法） | 拒绝：`Error(opening_option)`，details 给 `valid_families` 与 `got` |
| 同一份 value 用 `version=3` 校验 | 拒绝（opening/3 的门集里没有 `origin`，不允许它携带 value） |

这条实证来自 `validation/e2e_guided.py` 的「opening/4 origin 门四方向」用例（`problems: []`）；
门序断言（`ids[0]=='genre'`、`ids.index('origin')==1`）与四方向断言在同一条用例里，避免只测一半。

流程层：全链用例的方案生成器对 `origin` 门特判——`family` 按 `ORIGIN_FAMILIES` 轮换
（一门三案取「魂穿/身穿/本土」，跨用例轮换覆盖「其他」），`arrival`/`cost` 用通用填充句；
11 门全部答完后链条照常走到 `world_model → volume_outline → chapter_outline → write×50`。

## 三、旧项目（opening/3）不受影响（已验证）

`workflow.preparing_book(guided=True, opening_version=3)` 起一个旧版本项目，跑同一条全链：

| 观测 | 结果 |
|---|---|
| `creation.opening_version(creation)` | `3` |
| 门集 | 10 门，**不含 `origin`**（`('genre','voice','scale','edge','protagonist','relationships','world','opposition','payoff','title')`） |
| `opening_options` 派工数 | **9**（= 10 门 − 系统门 `scale`），与派生期望相等 |
| 终点 | `target_reached`，章号连续入库 |

结论：门集由 creation 文档自己的 schema 决定，opening/4 的插入**没有**改动 v1/v2/v3 的门序或派工数。

## 四、追补复跑（逐项数字，01:05–01:15 树）

| 入口 | 结果 |
|---|---|
| `python -m pytest tests -q` | **487 passed, 12 skipped, 1074 subtests passed, 0 failed**（176.05 s；12 个 skip 全为宿主符号链接能力） |
| `python -m pyflakes`（scripts+tests+validation，107 文件） | **0 发现** |
| `validation/e2e_guided.py` | **5/5 全部符合预期**（全链自洽 / origin 四方向 / v3 旧项目 / 章纲链拒漂移 / drift_check 漏项） |
| `validation/adversarial.py` | 10/10（v2 对抗性矩阵未回归） |
| `validation/repro_hook_matrix.py` | 10/10 |
| `validation/repro_hook_chain.py` | 3/3 |
| `validation/repro_style_window.py` | 单元 9/9 + 流程 1/1 |
| `validation/repro_v21_gaps.py` | 5/5（GAP-1/GAP-1b/GAP-2 回归门槛仍绿） |
| `validation/measure.py` | exit 0（6/6 节；`dispatch` 节的开门表按 opening/4 派生） |
| `repro_drift_clock.py` / `repro_knowledge_readback.py` / `repro_merged_tier.py` / `repro_understanding_channel.py` | 均 exit 0（BUG-0…BUG-3 未回归） |

## 五、口径与边界

- 本文只验证 **opening/4 这一增量**：门序与门数、`origin` 四方向的接受与拒绝、旧版本门集不受影响，
  以及全仓回归未受影响。逐门方案文本的文学质量不在验收范围（生成器填的是工程样本句）。
- `origin` 的 value 形状（`family`/`arrival`/`cost`）与四值枚举以 `creation.validate_value` 的
  实际行为为准，本文的四方向清单是实测通过的集合，不是从文档抄的。
- 未调用模型，未改 `scripts/**`、`tests/**`；结论均可由上文命令复现。
