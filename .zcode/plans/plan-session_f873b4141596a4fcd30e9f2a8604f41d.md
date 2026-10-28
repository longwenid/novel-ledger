# 修复第 45 章会话高消耗的四条根因

> 状态：历史方案，2026-10-27 冻结归档；以下“现状”“新增”“测试”等是编写时的计划，不是当前待办或逐项完成证明。实现及操作以 [运行](../../references/runtime.md)、[文风](../../references/style.md) 为准，验收入口见 [验证](../../references/validation.md)，相关历史结果见 [token 修复报告](../../validation/archive/token-efficiency-fix-2026-10-24.md)。

基于会话解剖（10.75M tokens、95.5% 为上下文重放）与代码探索，四项修复彼此独立、全部向后兼容。预期合计把同类会话从 ~6.8M/章压回快速组正常水位（~2M/章量级）。

## 1. Worker 活动自动续租（引擎；对应租约过期事故，本次浪费 ~0.9M）

现状：租约 TTL 300 秒，Worker 任何成功命令都不续租；watch 只续主控租约。长返修循环超过 5 分钟必然 `worker_lease`，主控被迫重开租约、双方各付一轮。

- `contracts.py` DEFAULTS 增 `'worker_lease_seconds': 300`；`claim()` / `prepare_worker()` / `writing_service.continue_task` 的 seconds 默认值改读 `policy_default('worker_lease_seconds')`（CLI `--seconds` 已存在，不改接口）。
- `application.py` 新增 `_touch_lease(task_id, claim)`：claim token 与当前租约匹配时把 `until` 延长到 `clock() + worker_lease_seconds`；不匹配则不动、不拒绝。
- 调用点：`submit()` 在 `_session` 校验通过且非 preview 时（事务内，随提交原子落库）；`check()` 在 preview 成功返回后（事务外 kv 直写，不受回滚影响）。
- 空闲超期语义不变：最后一次活动后 300 秒无引擎调用仍过期。
- 测试（`test_application_ports.py`，仿 172–195 既有模式）：跨 TTL 的 check 活动续租后 submit 成功；无活动超期仍 `worker_lease`（既有测试保持绿）。

## 2. check/preflight 一次性返回全部 findings（引擎；对应 26 次微编辑返修循环，本次浪费 ~2M）

现状：check 只回 `style_report`；lint/drift/字数 findings 落在 `book['draft']['findings']`，Worker 要到下一轮派工才看到全文，诱发"改一点→试一次"循环，每轮全量重读 15 万 token 上下文。

- `workflow.py`：`Outcome` 增加 findings 字段（`route_repair` 前的合并列表，含 drift/substance/lint/style 全部）。
- `application.py submit()` 响应：存在 findings 时加 `findings` 键（preview 与正式提交都带）。
- 测试：一稿同时含文风 + 字数（或 lint）违规 → check 响应一次含全部 criterion。

## 3. 快速组授权截断预警（引擎；对应"45 单章组 + 46–50 新组"双冷启动，本次浪费 ~1.7M）

现状：`run --through 45` 时 `dispatch` 把组 `last` 钳到 target=45，单章成组，冷启动无法摊销；引擎不给任何提示。

- `application.py run()`：落授权后若 fast 模式且 `0 < target − head < fast_batch_chapters`，响应加 `fast_group_note`（内容：快速组将因授权终点只剩 N 章；作者"一次五章"类意图应先对齐 `run --through` 再派工，避免单章组摊不掉冷启动）。不改变授权语义，只提示。
- 测试：head=44、`--through 45` → note 出现；`--through 50` → 无。

## 4. 协议文档与派工卡降耗指引（文档；对应组内重读参考文档与微编辑行为）

- `delivery.py`：组内续章（`worker_batch` 任务）派工卡注明"guides 与本组首章相同，已读可跳过，仅按需补读"；check 步骤文案改为"一次合并修正全部 findings"。
- `references/craft.md` 返修段增补：check 的 findings 一次全量返回；一次返修合并处理全部问题，以完整段落/场景为单位重写；逐项微调每轮整段重读上下文，是最高成本动作。
- `references/runtime.md` 快速组段增补：建组前核对授权终点与剩余章数，"一次五章"类授权意图先对齐 `run --through` 再 advance 建组；长返修章可用 `prepare-worker --seconds` 放宽租约，配合活动续租。

## 5. 配套收尾

- `VERSION` 2.0.1 → 2.0.2，README 版本行同步。
- 新增 `validation/dsh-session-45-cost-fix-2026-10-22.md`：记录本会话成本解剖（三会话 10.75M 的分段核算）与四项修复，作为实测证据。
- 跑 `validation/run_tests.py` fast + full 双门（新增测试入 fast 门），git 单条提交（不推送，由用户决定）。
