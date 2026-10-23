# 快速组十三章连跑成本解剖与四条降耗修复（2026-10-23，v2.1.0 下半）

会话 `session-28e7ffc8-bdd3-4ce4-9c41-8a7cb1ee6c2c`（《神明维修工》，2026-10-22 23:53–次日 01:02，deepseek-v4.1-flash / DSH 宿主）在已授权目标上无人值守连写 **13 章（第 48～60 章）**：3 个快速组 Worker + 主会话，**27,212,875 tokens、440 次模型调用、69 分钟 ≈ 2.09M/章**——正好落在快速组基线上，且 journal 全程只有 2 次失败（1 次 worker_lease、1 次 time_evidence，各一次恢复）。结论：**事故已被 2.0.2 压住，剩下的 2.09M/章是协议基线的真实价格**；本文解剖基线构成并记录 2.1.0 下半的四条降耗修复。

## 成本结构

| 会话 | 调用 | tokens | 每章 |
|---|---|---|---|
| 主会话（总编） | 64 | 3.17M（12%） | 244K |
| Worker A（48-52） | 154 | 10.72M | 2.14M |
| Worker B（53-57） | 149 | 9.12M | 1.82M |
| Worker C（58-60） | 73 | 4.21M | 1.40M |

- **cacheRead 占 94%（25.6M），全部输出仅 349K**：成本公式是 `调用次数 × 每次重读的上下文`（Worker 上下文 19K→113K）。
- 组内曲线：冷启动章 1.58M～4.10M（74/50/31 次调用），稳态章 12–22 次调用、0.99M～2.07M。
- **稳态章解剖（18 次调用的样本章）**：真正创作 4 次（写稿、拼回执、check、submit），**其余 ~14 次全是材料搬运**——1 次引擎 read 落盘 read_all.json、~10 次 python 逐段抽取、compress 后重建。三个 Worker 自发演化：A 整文件读进上下文（2.14M/章）→ C 材料留盘只取切片（1.40M/章），同协议下 35% 差距说明**协议把材料进出上下文的机械问题丢给了模型现场发明**。恶性循环：上下文涨满 → compress（三组共 13 次）抹掉已读材料 → 逐条重读。
- 主会话 64 次调用里 watch ×8 之外仍逐章参与（3.17M）：唤醒后的交接动作可以更少。

## 四条修复（质量门一个不动：章纲冻结、逐章核账、文风代理、自比、原子提交全是本地 Python，零模型 token）

1. **R1 回执拼装从模型活变引擎命令**：新增 `receipt` 命令（`novel_ledger/receipts.py` + `application.draft_receipt`）——输入 `--prose draft.md`（可带 title/summary/self-check），引擎本地组装完整回执：信封、drift_check.items 按章纲预填、`actual.from` 全部用投影填好、status=kept 默认、evidence quote 逐条在正文中机械定位（时钟项锚定时间表达，未定位的行回报 `quotes_unlocated`），写出 result.json 并只回紧凑摘要（missing/未定位清单）。派工卡命令集为 write 阶段自动加入 `commands.receipt`。
2. **R2 材料进出上下文有协议**：`read --save [路径]` 把完整响应落盘（默认 read_pack.json），响应只回记录名/哈希/摘要——材料驻留磁盘，模型上下文只进增量。派工卡规定：compress 之后只允许一次全量重建（可用 --save），禁止逐条 `--record` 重读未变更记录。
3. **R3 每章固定动作序列**：批量组派工卡写死六步——①worker-next ②一次 read（--save）③成稿一次写入 draft.md ④receipt 组装核对 ⑤preflight 全量 findings 一版修 ⑥submit——并标注**模型调用预算 ≤8 次/章**（每步都重读全部上下文，省一步即省一步的钱）。
4. **R4 主会话组内零参与**：runtime.md 明确 `watch --owner ID` 本地轮询（零模型调用）一口气守完本组、`--steps 0` 到组边界，只在 worker_blocked/idle/作者边界返回时介入，不逐章查询、不逐章发消息。

## 验证

- 新增：`test_receipt_assembly_passes_preflight_without_model_plumbing`（引擎组装的回执原样过 preflight 并入库）、`WriteReceiptHandoffTests`（CLI：draft.md 进 → result.json 出 → preflight valid → submit 入库；read --save 落盘且响应紧凑）；receipts 模块入架构表。
- fast 门 260 项、full 门全绿（与上半同属 2.1.0，一次入库）。

对后续同类会话的预期：稳态章 12–22 次调用 → ~6 次（0.4M～0.6M/章），冷启动组 0.5M～0.8M，主会话 ≤1M/13 章；**13 章总账 27.2M → 9M～12M（约 2.5–3× 降幅）**，逐章质量口径完全不变。待下一轮真实宿主连跑复核。
