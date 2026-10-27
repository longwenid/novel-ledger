# 第 45 章会话成本解剖与四项修复（2026-10-22）

会话 `session-b927e14e-39b6-4197-b389-9bb1b11eb396`（2026-10-22 21:12–21:35，模型 deepseek-v4.1-flash，宿主 opencode-go）续写《神明维修工》第 45 章并开启 46—50 章新组。全程约 23 分钟、116 次模型调用、合计 **10,752,677 tokens**（totalTokens = input + output + cacheRead 口径，与 [全本实测](dsh-run-cost-2026-10-22.md) 一致），实际入库只有一章正文。本文记录解剖结果与本轮（2.0.2）四项修复。

## 总量与分段

| 会话 | 内容 | 模型调用 | totalTokens |
|---|---|---|---|
| 主会话（总编） | 唤醒 1.81M、快速授权与派工 0.74M、租约事故 0.55M、新组派工 0.83M | 46 | 3.94M |
| Worker d9c4 | 第 45 章单章：引导+材料 0.95M、初稿+返修循环 2.61M、回执+事故+提交 2.50M | 56 | 6.07M |
| Worker c88b | 46—50 新组引导（会话导出时中断，未出稿） | 14 | 0.74M |

cacheRead 占 95.5%（10.27M），全部输出仅 131K：成本几乎全部是**每步全量重读增长的上下文**，Worker 上下文从 13K 涨到 162K。折算约 6.8M/章（Worker+主会话摊销），远高于快速组实测均值 2.09M/章。

## 四条根因与修复

1. **微返修循环**：Worker 对 draft45.md 做 26 次微小编辑（每次 18—280 字符）逐项凑文风指标，每轮试算-修改重读约 14 万 token 上下文，返修段 20 次调用花 2.61M。check 本已一次算出全部 findings，但响应只回 style_report，lint/drift/字数违规要下一轮派工才可见。
   **修复**：`submit`（含 preview）响应新增 `findings` 全量列表（`Outcome.findings`）；派工卡第 4 步与 [craft](../../references/craft.md#修订原则) 改为"一次合并修正全部 findings，以完整段落为单位重写，不逐条小改反复试算"。
2. **租约过期事故**：返修循环两次引擎调用间隔超过 300 秒租期，`worker_lease` 中断；主控重开租约、双方各多付一轮（合计约 0.9M）。Worker 侧此前没有任何续租路径，watch 只续主控租约。
   **修复**：活动自动续租——每次携带正确 token 的成功 check/submit 都把租约延长 `worker_lease_seconds`（DEFAULTS 新增，默认 300）；只有沉默（不再调用引擎）才让租约过期。空闲超期与主控恢复路径语义不变。长返修章可由主控 `prepare-worker --seconds` 直接放宽。
3. **单章组双冷启动**：上一会话写到 44 章结束，本会话沿 `target=45` 建组被钳成 {45,45}，随后 46—50 另开新组新 Worker——快速组摊薄冷启动的机制完全没有发生，反而付了两次引导。
   **修复**：`run` 在快速模式且剩余章数不足一组时返回 `fast_group_note` 提示（不改变授权语义）；[runtime](../../references/runtime.md#快速无人值守十章一组) 增加"建组前对齐 run --through"指引。
4. **组内重复读参考文档**：narrative.md（16K）与 craft.md（5.2K）每章都重读，既不在必读冻结表也不在组级读取缓存。
   **修复**：组内续章派工卡第 1 步注明 guides 与首章相同、已读可跳过、仅按需补读。

## 验证

- `test_worker_activity_renews_the_lease_while_silence_still_expires_it`（跨 TTL 的 check 心跳续租后同一回执过期点提交成功；既有空闲超期测试保持不变）。
- `test_preview_answers_every_defect_in_one_call`（重复 span + 西文残留两类违规一次 preview 全量返回，已入 fast 门）。
- `test_run_warns_when_the_target_would_clip_the_group`（through=7 告警、through=11 无告警）。
- fast 门与 full 门全部通过（版本 2.0.2）。

对后续同类会话的预期：返修段从 ~26 轮压到 2—3 轮（省约 2M/章）、租约事故归零（省约 0.9M）、不再出现单章组（省一次冷启动约 1.5—2M）、组内参考文档复用（省约 20K×4 章）。
