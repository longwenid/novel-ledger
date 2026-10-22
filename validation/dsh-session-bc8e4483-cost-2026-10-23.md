# 整卷连跑成本解剖与双材料包/机械报告修复（2026-10-23，v2.1.1）

会话 `session-bc8e4483-3023-4d48-b883-79da94ec8133`（《神明维修工》，2026-10-23 01:45–07:14，deepseek-v4.1-flash / DSH 宿主，v2.1.0 引擎）在已授权目标上无人值守连写 **51 章正文 + 2 张章纲 + 1 次返修**（全书推进到 111 章），5.5 小时合计 **118,002,717 tokens、1,876 次模型调用 ≈ 2.15M/章**。

## v2.1.0 的两条先验证为生效

- **事故面干净**：journal 全程零 design_drift 计数、无返修熔断循环；4 次 worker_lease 全部 f=1 不阻断、主控 re-claim 即恢复（免 reset 仪式）；一次 file+stdin_json 双错才 blocked 一次、一次恢复。上半的四层修复按设计工作。
- **六步协议被采纳**：写章 Worker 全部使用 `commands.receipt`（每章一次）、worker-next/preflight/submit 各就各位，`read --save` 已有使用。

## 但每章成本没降反微升（2.09M → 2.15M）：调用数才是残余变量

| 会话 | 调用 | tokens | 备注 |
|---|---|---|---|
| 主会话 | 143 | 7.99M | job_output 轮询 40 次、send_message 18 次、watch 19 次 |
| 写章 Worker ×11 | ~1,500 | ~87M | 每章 ~33 次调用（六步本身只占 ~7 次） |
| 章纲 Worker ×2 | 74 / 196 | 5.06M / 14.44M | 第二张章纲：compress ×4 → 重读材料 50 次 |

**残余根因（每条都有逐调用证据）**：

1. **材料以"每记录一个文件"的粒度进出上下文**：写章 Worker 每章直读 6–8 个 mat 文件（章纲/前章/状态/锚点/合同…），每次读都是一次全上下文模型往返；章纲 Worker 被 compress 抹掉上下文后重读 50 次。
2. **draft.md 微编辑循环**：单个 Worker 对 draft.md 做 31 次 edit（每章 ~5 次）——文风/字数 findings 逐段小改，每改一次全价。
3. **自由探索调用**：ls/dir 类探查 24 次、本地 python 逐字段查看 56 次、后台任务轮询 job_output 21 次（写章 Worker 自己也轮询）。
4. **主会话仍在逐章参与**：watch 之外轮询子代理 40 次、发消息 18 次（7.99M 的大半）。

## 耗时结构（与 token 同根：往返数 × 单次时延）

- **write 章周期中位 4.9 分钟**（均值 5.7，最长 28.4＝租约事故章）；Worker 冷启动（到首笔长生成）0.3～3.4 分钟；单 Worker 全程 20～47 分钟。
- 逐调用间隔：中位 3.5～6.9 秒；**长生成调用（≥800 输出，即正文起草/大改）21～42 秒，每章只有 2～3 次；短往返（<200 输出）2.7～11.1 秒，每章 ~30 次**——约 85% 的墙钟时间在往返上，不在生成上。
- 结论：耗时与 token 同一个杠杆（调用数）。降调用同时降时延：材料包把每章 6–8 次读并为 1 次、机械报告把"逐轮暴露问题"压成一轮、F5 再并掉一次 preflight 往返。

## 四条修复（v2.1.1，质量门依旧一条不动）

1. **双材料包**：`read --save` 现在落三件——`read_pack.json`（机器全文）、**`read_pack.md`**（写作包：本章章纲/前章结尾 2500 字/状态/文风锚/字数预算，逐字分节，不做摘要以免失真）、**`read_ref.md`**（合同/世界/卷纲等组级参考）。派工卡规定：每章与每次 compress 后**只读 read_pack.md 一个文件**，参考材料按需再读。材料进出上下文从 6–8 次调用降为 1 次。
2. **receipt 附机械报告**：组装时本地跑 submit 同款的字数区间、lint 与文风代理解析，响应带 `prose_report{han, band, substance_ok, lint_findings, style_findings, clean}`——写手按数字一轮修完 draft（整段替换）再重跑 receipt，preflight 通常一次过。文风/字数的发现不再靠 preflight 往返逐轮暴露。
3. **调用纪律入卡**：明确"每个工具调用都是一次全上下文模型往返"；禁止 ls/dir 探查、python 逐字段查看 result.json、开后台任务再轮询——不确定格式用一次 check，不猜不翻。
4. **主干纪律**：runtime.md 写明 watch 期间零轮询零逐章消息，只在组边界动作（本轮实测主会话轮询+消息占其 7.99M 的大半）。
5. **receipt 一次组装+试算**：`receipt` 写出 result.json 后在同一进程直接跑全量 dry-run，响应带 `preview`（valid/findings）——第④⑤步合并为一次调用，每章再省一次全上下文往返（钱与时延同省）。

## 验证与预期

- 测试：`test_receipt_report_flags_a_draft_that_misses_the_band`（短稿报告不 clean）、receipt 组装测试增 `prose_report.clean` 断言、`test_read_save_lands_the_pack…` 改为断言三件落盘与 read_pack.md 分节；`delivery` 为 novel 入口登记 `pack_markdowns`（架构表显式决定）。
- fast 261 / full 571 全绿（版本 2.1.1）。
- 预期：写章每章 ~33 次调用 → 5–7 次（≈0.3–0.5M/章、约 1.5–2 分钟/章，其中正文生成本身 1–2 分钟是模型下限）；章纲/设计任务 compress 重建从 ~10 次调用降为 1–2 次；主会话 ≤2M/整卷。51 章整卷总账预期 **118M → 30M 上下、5.5 小时 → ~2 小时**，待下一轮真实连跑复核（对回到本文与 dsh-fast-group-cost-2026-10-23.md）。
