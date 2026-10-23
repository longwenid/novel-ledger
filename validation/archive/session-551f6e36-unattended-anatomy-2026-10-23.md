# 魔物旅馆无人值守启动解剖与四层修复（2026-10-23，v2.1.0 上半）

会话 `session_551f6e36db7a24305cdbb75a3cdd34be`（《魔物旅馆》，2026-10-22 21:07–次日 00:30+，GLM-5.3-Flash / ZCode 宿主）从开书十三门推进到卷一 25 章章纲。十三门阶段（21:07–21:41）零失败；世界模型、卷纲、章纲三个 Worker 阶段共记录 **35 次 worker_failure、23 次主控恢复**，章纲任务在 23:37 派工后深陷"每失败两次就要主控亲手 reset-failures 一次"的循环。本文记录解剖结果与本轮（2.1.0 上半）四层修复。

## 失败时间线（journal 全量）

| 时段 | Worker | 失败码 | 次数 |
|---|---|---|---|
| 21:42–22:01 世界模型 | zcode-worker-mw1 | session（env 无凭据）×2、worker_lease ×2、world_alignment ×3、volume ×1、opening_alignment ×4 | 12 |
| 22:03–22:26 卷纲 | zcode-worker-vo1 | worker_identity ×1、session ×1、literal_policy ×1、design_drift ×3 | 6 |
| 23:37–00:30+ 章纲 | agent_c61ce915 | worker_lease ×1、design_drift ×15+（每 2 次熔断一次） | 17+ |

开书十三门全部一次通过（13 张卡 34 分钟），问题集中在派工执行链。

## 四条根因与修复

1. **内容性失败被计入技术失败计数，2 次即熔断**（18 次 design_drift、14 次熔断的主体）。`novel.py` 的 portable 错误漏斗把一切 Error——包括章纲/卷纲核账的内容码——都记进 `technical_failure:<task>`，违背 `worker_failure` 自己的 docstring（"Technical accounting is separate from story revisions"）。
   **修复**：contracts 新增显式错误三分类 `CONTENT_ERRORS / CONTROLLER_ERRORS / TECHNICAL_ERRORS`（AST 守卫测试扫描全部 raise 点强制全覆盖、三集互斥）；漏斗只对非内容码计数。
2. **设计阶段试算走 raise 且 findings 截断 12 条**：章纲链路 `require(..., 'design_drift', findings[:12])`，Worker 每轮只见 12 条、修一版冒一版（实测 25→12 的乒乓），主控被迫自己跑模拟转述全量。
   **修复**：`submit(preview=True)` 把内容错误转为**数据响应**（`valid=false` + 全量 findings + `content_rounds`/`stalled` 信号，连续同 digest 不收敛达 `design_stall_rounds`(3) 轮标记 stalled 交回主控）；去掉 drift/workflow/world 三处 `[:12]`/`[:8]` 截断。submit（提交门槛）仍 raise 但不计数。
3. **租约模型与交付形态脱节**：租期一律 300 秒、`_touch_lease` 续租硬编码 300（`--seconds 7200` 放宽后被一次心跳打回）、preflight（=preview）硬校验租约却因 `if not preview` 永不续租、CLI `--seconds` default=300 写死。章纲 Worker 静默起草 10 分钟后首次 preflight 撞死。
   **修复**：租约行记录授予 `seconds`，续租按授予时长且只增不减（旧租约行缺键有回退）；read/recall/patch/worker-ready/preflight 全部成为心跳点；`SINGLE_DELIVERY_STAGES`（world_model/opening_contract/volume_outline/chapter_outline）缺省租期 `single_delivery_lease_seconds`(3600)，claim/prepare-worker 的 CLI `--seconds` 缺省改 None 走策略。
4. **熔断语义过紧 + 凭据注入竞态**：CONTROLLER 码 1 次即 blocked，恢复还要叠加 `--reset-failures` 仪式；Worker 4 次先于凭据注入启动（session:null ×3、worker_identity ×1）。
   **修复**：`execution_recovery` 统一两振熔断（f=1 即交主控路由不变，但不 blocked——重新 prepare-worker 即恢复，第二次起才需 --reset-failures）；派工卡新增机械"步骤 0 凭据门槛"：NOVEL_* 注入前只准本地读 task.json/brief.md，缺 NOVEL_SESSION 直接交回不重试。

另：章纲简报与检查提示补一句四类增量 from/to 的前后值语义（from=前序投影逐字比对、首次确立才允许 null），修当晚"增量写成状态字符串/from 写 null"的反复。

## 验证

- 新增：`test_error_taxonomy`（三集守卫）、`ContentPreviewHandoffTests`（试算返数据不计失败、findings 全量、stalled 进度重置、submit 拒绝不计数）、`test_first_identity_fault_hands_back_without_reset_ceremony`、续租/租期三测（`test_worker_activity_renews…` 更新为按授予时长续期 1055.0）。
- fast 门 260 项、full 门全绿（版本 2.1.0）。

对后续同类会话的预期：内容返修熔断归零（主控不再当人肉重试器）、租约事故归零（单交付阶段默认 1 小时租期）、首次身份/租约事故恢复去掉 --reset-failures 仪式、每轮返修全量 findings 一版修完。
