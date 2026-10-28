# 架构级修复：无人值守执行的四层修复（2.0.2 → 2.1.0）

> 状态：历史方案，2026-10-27 冻结归档；以下“现状”“新增”“测试”等是编写时的计划，不是当前待办或逐项完成证明。实现及操作以 [运行](../../references/runtime.md)、[文风](../../references/style.md) 为准，验收入口见 [验证](../../references/validation.md)，相关历史结果见 [token 修复报告](../../validation/archive/token-efficiency-fix-2026-10-24.md)。

依据：session_551f6e36（魔物旅馆）全程解剖——35 次 worker_failure / 23 次主控恢复，四类根因。修复原则：**错误只留给门槛与基础设施，返修迭代发生在数据通道上；租约跟随交付形态；角色恢复不搞仪式**。

## A. 失败核算分层（内容码不进技术计数）

现状：`novel.py:412-421` 漏斗把一切 Error（含 design_drift/world_alignment 等 ~70 个内容码）都计入 `technical_failure:<task>`，2 次即 blocked，主控被迫 `--reset-failures` 当人肉重试器（本次 18 次 design_drift 失败、14 次熔断全来自这里），违背 `application.py:165` 自己的 docstring。

1. `contracts.py` 新增显式错误分类三集合（沿用 CONTROLLER_ERRORS 的声明式模式）：
   - `CONTENT_ERRORS`：事实清单 A 类全量（design_drift、world_alignment、opening_alignment、literal_policy、volume_outline/chapter_outline 形状、drift_*/facts/narrative/spatial/craft/story_* 等，以三个探索代理的码表为准逐个登记）；
   - `PROTOCOL_ERRORS`：信封与形状类（schema、input_version、result、replay_conflict、envelope_*、chapter_order、drift_check 形状等）；
   - 既有 `CONTROLLER_ERRORS` 不动。
   - **分类守卫测试**：正则扫描 scripts/ 全部 `require(..., '码'` 与 `Error('码'` raise 点，断言每个码恰属一集——新增码漏登记时测试失败，防止分类表腐化。
2. `novel.py` 漏斗：`error.code ∈ CONTENT_ERRORS` 时**不调 worker_failure**（内容返修由 B 通道和既有 repairs/stall 预算管），协议码与技术码照计。
3. `execution_recovery`（contracts.py:613）改**统一两振熔断**：`blocked = failures >= technical_retries`，对 CONTROLLER_ERRORS 仍 f=1 即 actor=controller（角色路由不变），但不再 f=1 就 blocked——昨晚 session:null/worker_identity/worker_lease 各一次就熔断、恢复还要多加 `--reset-failures` 仪式；改后 f=1 时主控 re-claim 即恢复。`test_execution_handoff.py:199` 等按新语义更新。

## B. 试算即数据：check/preflight 把全量 findings 作为响应返回

现状：设计阶段核账失败走 raise（`drift.py:162 _reject`、`workflow.py:578`），details 截断 `[:12]`（`world.py:161` 另有 `[:8]`）——Worker 每轮只见 12 条，修一版冒一版；2.0.2 的"findings 一次全量返回"只覆盖了 write 阶段的 Outcome 路径。

1. `application.py` `submit(preview=True)` 路径：捕获 `code ∈ CONTENT_ERRORS` 的 Error（preview 事务本就回滚），返回数据响应 `{valid: false, accepted: false, committed: false, error, message, findings: [全量], content_rounds, stalled, recovery}`——与既有 prose 路径的 `response['findings']`（application.py:505）汇成同一个契约。非 preview 的 submit 仍 raise（提交是门槛，语义不变）。
2. 去截断：`drift.py:164` rows[:12]→全量（附 count）、`workflow.py:579`、`world.py:161` complaints[:8]→全量。已核实没有任何测试依赖截断条数。
3. **返修轮次信号**（防盲试无上限）：kv 新键 `content_rounds:<task>`（`store_keys.py` 注册前缀），preview 后小写入（照 `_touch_lease` 的回滚后单独写模式）：记录连续失败轮数与 findings digest 集；digest 集变化即视为有进展、计数归 1；连续 `design_stall_rounds`（DEFAULTS 新增，默认 3）轮无进展 → 响应带 `stalled: true`。纯数据信号不熔断，硬停仍由 watch 的 idle_limit 兜底；派工卡同步加一句"stalled=true 时停止盲试、把全量 findings 交回主控"。

## C. 租约模型：按交付形态定租期，活动续租补全

现状：租期一律 300 秒（`contracts.py:84`）；`_touch_lease` 续租硬编码 300——`--seconds 7200` 放宽后一次心跳即打回 300；preflight（=submit preview）在 459 行硬校验租约却因 `if not preview`（461 行）永不续租；read/recall/patch 校验租约但不续；CLI `--seconds` default=300 写死，策略表形同虚设。昨晚章纲 Worker 起草 10 分钟撞死、主控手动救场即此。

1. lease 行增记 `seconds`（授予时长）：`claim()` 写入；`_touch_lease` 按授予时长续期且取 max（永不缩短），并对缺 `seconds` 键的旧租约行宽容回退默认值（**兼容在途任务**）。
2. 续租点补全：read、recall、patch、worker-ready 成功后同样 `_touch_lease`（与 check/submit 同样的成功后小写模式）；submit 的 preview 分支也续（461 行条件去掉）。
3. **按阶段默认租期**：DEFAULTS 新增 `single_delivery_lease_seconds: 3600`，`SINGLE_DELIVERY_STAGES = {world_model, volume_outline, chapter_outline}`；`prepare_worker/claim` 的 seconds=None 时按任务阶段取默认（write 类仍 300+心跳）。CLI：`claim`/`prepare-worker` 的 `--seconds` default 改 None（novel.py:115，需把共享参数拆到子命令），`run`/`renew` 主控租约默认 300 不动。
4. 派工卡（delivery.py 步骤 4）补一句：长起草期间可用半成品回执跑 check 既保心跳又提前拿 findings（B 通道保证半成品试算只出数据不计失败）。

## D. 交接时序与文档

现状：Worker 先于凭据注入启动，journal 记 session:null×3、worker_identity×1（角色护栏正确拒绝，但每次都熔断+恢复）。

1. 派工卡自举段（delivery.py:210-213）把"停在自举边界"改成机械步骤 0：**NOVEL_* 环境变量未注入前，唯一允许的动作是本地读 task.json/brief.md；缺 NOVEL_SESSION 不重试任何引擎命令，直接带 worker_identity 交回**。
2. `briefs.py` 章纲简报（:355-359 附近）与 CHAPTER_CHECK_HINTS 补一句 enter/exit 与 characters from/to 的增量对语义（措辞按 drift_simulation 实际判据核对后落笔，修昨晚"把增量写成状态字符串/from 写 null"的反复）。
3. 文档：`references/runtime.md:48` 租约段重写（全操作续租+阶段租期+半成品心跳）；`references/protocol.md` 执行交接段同步 A/B 新语义；craft.md:72 的"一次全量"描述从此名副其实。

## 测试与入库（沿用 2.0.2 惯例）

- 新增测试（挂 fast 门）：错误分类覆盖守卫；设计阶段 preview 返数据不计失败（连续 3 轮不熔断）；findings 全量不截断（>12 条构造）；submit 内容失败不计数；preflight 续租；续租不缩短授予租期（7200 场景）；read/recall 续租；阶段默认租期（章纲 3600/执笔 300）；f=1 技术码不 blocked、f=2 blocked；stalled 信号（同 digest 两轮→stalled=true，digest 变化→归 1）。
- 更新受影响既有测试（test_execution_handoff 恢复语义、CLI --seconds 缺省）。
- 版本：`contracts.py VERSION='2.1.0'`、README 两处；release.json 留给同步工具（沿 2.0.2 先例不动）。
- `validation/session-551f6e36-unattended-anatomy-2026-10-23.md`：按 dsh-session-45 格式写本次解剖（35 失败/23 恢复时间线、四根因、修复、测试、预期收益：内容返修熔断归零、租约事故归零、每轮主控干预降为 stalled 或 idle 时一次）。
- 验证：`python tests/run_tests.py` fast 与 full 双门全绿后提交（信息格式沿"2.1.0 按 session_551f6e36 无人值守解剖修四层根因：…"）。

## 顺序与风险

实施顺序 A→B→C→D（A 是 B 的分类前提，B 是 C 心跳语义的前提）。动工前先查魔物旅馆在途任务状态：修改对在途任务向后兼容（旧租约行缺 seconds 有回退、preview 语义变化只会让在途 Worker 少熔断），但仍尽量等它提交后再落盘。全程不碰该项目数据库。