# novel-ledger 工程质检 2026 10 19

> 历史归档：本文件保留当轮版本、设计或实验条件，不是当前执行规范。旧门序、兼容条款、独立审查阶段及命令均不用于当前流程；当前唯一执行依据见 [任务协议](../../references/protocol.md) 与 [运行流程](../../references/runtime.md)。

本轮工程验收暂不通过。十三门开书、世界绑定、五步流水线和存储底座已有可运行实现，但修订采纳和执行态事实结算存在两项 P1 问题；等待、返修收口、闭合与文风契约仍有缺口。当前进展适合表述为“主链已实现，关键边界待修复”，不能据既有绿灯报告宣布全部通过。

审计对象：`9a2a5bb40be72c0d2d02c2bacc2bcf4fe7c0acf8`，引擎 `2.0.0`，开书 `opening/5`，存储 `novel-ledger/3`。日期按 Asia/Shanghai。审计开始时工作树干净；本轮仅新增本报告及[原始结果](quality-run-2026-10-19.json)，未修改引擎、现有测试或历史报告。源码行号均对应该提交。

## 进展与验证结果

| 检查 | 本轮结果 | 可支持的结论 |
|---|---|---|
| 全量 pytest | **535 passed，2 failed，1312 subtests passed**，28.24 秒 | 本机回归未全绿，失败已逐项分流 |
| 11 个专项脚本 | 全部退出 0 | 已有开书、漂移、伏笔、文风、旧缺陷回归样例可运行 |
| 工程度量 | 6 节执行成功；40 模块、137 依赖边、无环，核心含 CLI 12,201 行 | 分层守护及合成规模度量可运行；`material.world_model` 内部仍为 `blocked`，不能说材料度量全部完成 |
| 技能基础校验 | `Skill is valid!` | frontmatter 等基础格式合法 |
| 源码语法 | scripts 44、tests 41、validation 23 个 Python 文件均可解析 | 当前源码没有语法错误 |
| 文档检查 | 15 份活跃文档，检查器报告 0 坏锚点；相对文件链接目标存在；三份架构图一致 | 文件与图源同步；锚点检查器自身有漏报，见后文 |
| 静态未使用项检查 | 本机未安装 pyflakes，本轮未执行 | 不沿用历史报告的 pyflakes 结果冒充本轮结果 |

全量命令为 `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider`。11 个专项脚本为 `e2e_guided`、`adversarial`、`e2e_drift_acceptance`、`repro_hook_matrix`、`repro_hook_chain`、`repro_v21_gaps`、`repro_style_window`、`repro_merged_tier`、`repro_drift_clock`、`repro_knowledge_readback`、`repro_understanding_channel`，均在 `validation/`。逐项用时、完整失败输出、源码哈希、度量和对抗观察保存在 JSON 中。

两项 pytest 失败均执行到了此前受宿主符号链接能力限制的路径：

- `test_materializing_work_symlink_replaces_the_link_and_preserves_external_target`：真实恢复缺陷，对应 Q08。
- `test_world_files_need_only_reader_and_workspace`：测试在 `tests/test_presentation_boundaries.py:134` 构造 `selections=[{'gate':'genre'}]`，缺少实际 intake/pick 始终保存的 `option`，在 `bookpage.py:317` 抛 KeyError。应修复夹具；现有证据不足以认定这是生产可达状态的页面缺陷。

## P1 正式稿与事实真源

### Q01 未完成修订也能采纳为正式版本

位置：`scripts/novel_ledger/application.py:778–783`。

复现：先写至第 5 章，发起第 5 章表达修订，在尚未派出修订任务时调用 `promote`。采纳成功，`formal_chapters` 从 **5 降至 4**，`candidate_chapter` 仍为 5，`revision_run` 已清空。父分支原稿仍保留，但正式分支已切到缺章候选。

当前门槛仅检查没有 pending 与 revision_directive，随后审计候选已有前缀；没有证明修订区间和保留后缀已完成。采纳前应核验修订存在、无未处理草稿、修订终点完成、后缀完整，再允许切换正式版本。

### Q02 计划外变化提交成功却没有写入事实

位置：`scripts/novel_ledger/drift.py:1904–1918`；公开契约见 `references/protocol.md:97–103`。

复现：在第 1 章 `drift_check.unplanned` 声明 `knowledge/shen:secret`，实际由 `null` 变为 `confirmed`，填写原因、正文引文及 `verdict=deviated`。章节成功入库，偏差账中有该变化，`state.knowledge` 中却没有 `shen:secret`。

该分支只记偏差，没有生成事件或更新投影。后续章纲即使重排，也读取不到此次声明的实际变化。带结构化实际值的计划外变化必须经过相同事实规则结算；仅有说明、无法结算的条目应明确限制，不能返回事实已处理的成功状态。

## P2 流程与一致性缺陷

### Q03 执行偏差允许已确认知情倒退

位置：`scripts/novel_ledger/drift.py:1644–1653`，下游 `facts.py:138–147`。

合法章纲声明第 4 章 `confirmed→confirmed`。前三章正常提交后，将该章自比改为 `deviated`、`confirmed→hinted` 并附原因和引文，完整提交成功，正式事实由 `knows` 改为 `suspects`。设计模拟会挡住同类倒退，执行结算没有应用该规则。应复用同一知情状态机，同时保留协议允许的 `retracted` 路径。

### Q04 skipped 判断使用了错误变量

位置：`scripts/novel_ledger/drift.py:1875`。

代码判断 `kind == 'skipped'`，而 skipped 是 status。首章伏笔 plant 如实填写 `status=skipped, actual=null`、原因和证据后，仍进入事件生成，报 `drift_hook` 并转正文返修。它没有走文档承诺的“登记偏差后重排”。应在生成事件前按 status 跳过实际未发生的变化。

### Q05 watch 会移走当前 Worker 待提交的回执

位置：`scripts/novel_ledger/unattended.py:41`、`delivery.py:393–400`。

复现：派出 write，Worker 写好含真实 session 的有效 `result.json`，尚未提交时主干启动 watch。watch 的首次 advance 重建视图，把该文件挪为 `result.stale.json`，原提交路径消失，等待最终返回 idle。补充验证中，**Worker 持有有效 claim 时同样发生**。

运行指南推荐“派 Worker 后运行 watch”，因此这是正常使用时序的竞态。等待当前任务应保留活动回执；隔离旧回执应由明确的重新派工或任务替换边界触发。

### Q06 接受耗尽候选后仍然无法推进

位置：`scripts/novel_ledger/workflow.py:484–491`。

首次正文依次耗尽 write、repair、repair、redesign 后，作者选择“接受当前候选，把问题记为未解决项继续”。answer 瞬间返回 running，但 draft 被清空，候选没有入库；随后 advance 连续返回 `repair_exhausted`，resume 后仍相同，正式章节为 0，也没有新的作者决定可处理。

应让“接受”完成明确的可继续状态转换，并保留候选。确属不能豁免的机械硬条件时，作者选项须给出真实可执行的处理方式。

### Q07 修订完成没有进入采纳动作

位置：`scripts/novel_ledger/workflow.py:278–279`；动作契约见 `references/runtime.md:65–69`。

正常完成第 5 章修订后返回 `target_reached`，正式分支仍为 main，候选分支和 revision_run 仍在。响应没有采纳提示。指南只在 `revision_ready` 时执行 promote，而 target_reached 是交付停止动作；当前实现没有产生 revision_ready 的分支。

应为已完成且等待采纳的修订返回明确边界；采纳后再恢复原授权目标。仅把动作名写进指南不能建立这条流程。

### Q08 损坏的派工视图无法从数据库重建

位置：`scripts/novel_ledger/delivery.py:430`。

前面 387–391 行已容错读取旧 task.json，430 行又无保护解析同一文件。普通损坏 JSON 或指向非 JSON 外部文本的 task.json 符号链接都会导致 materialize/advance 抛 JSONDecodeError。现有全量用例直接复现，外部文件未被改写。

派工视图是派生物。无效旧视图应按不存在处理，从数据库重建；重新派工计数不能阻断恢复。

### Q09 小体量世界简报与硬通货绑定互相冲突

位置：`scripts/novel_ledger/world.py:82–90`、`briefs.py:202–205`、`world.py:123–135`。

opening/5 的 world 门必含硬通货，但 declared_sections 仅补 powers/cosmology，没有补 economy。t0/t1/t2 的简报因此要求 economy 保持空数组，绑定校验却要求 economy 实写同名硬通货和分配者。按本档简报构造的三个完整候选均报 `world_alignment`。

应让已声明的 resource 自动要求 economy，保持“任务要求”和“提交判据”来自同一领域集合，并同步 `references/world.md:11–13`。

### Q10 两个开书门要求四案但只接收三案

位置：`scripts/novel_ledger/creation.py:312`、`:337`、`:850`，以及 `references/opening.md:96`。

当前来历门与脑洞门简报均写“四个方向各给一个方案”，统一接收器限制每门 2～3 案。两个门按简报提交四案均立即报 `opening_options`。应统一选项数量与呈现方式；四种来历作为可选方向，不应自动变成接收器无法容纳的四份回执。

### Q11 卷末闭合保证超过实际可计算契约

位置：`scripts/novel_ledger/drift.py:690–731`、`:884–888`；保证见 `references/narrative.md:114` 与 `runtime.md:127`。

卷纲声明“30 日后舍身救同伴”，章纲实际只推进 2 日，人物仍为“先核对再行动”，两个公共 validator 均接受，最终 `simulate findings=[]`。人物终值只检查当前状态存在；卷纲 clock 总量未闭合；自然语言 exit_state 只检查非空。

人物在卷纲与章纲中还使用不同表达形状，不能直接增加一次字符串相等比较。应先统一可计算的终态表达并核验人物与累计时钟；自然语言 exit_state 的语义保证应收窄，避免宣称引擎已经证明它成立。

### Q12 必填文风声明可以完全省略

位置：`scripts/novel_ledger/drift.py:1062`、`:1332`；必填要求见 `references/narrative.md:55`、`:102`。

删除卷纲 style 和所有章纲 style，两级校验均接受并归一为 `{}`。实现只复制字段，没有落实卷纲 trend、章纲 pov/rhythm 的必填约束。代理指标仍可能检查约定或重复度，但“卷方向—章声明—正文执行”的文风声明链没有建立。

应校验当前协议要求的类型与必填内容，并明确旧工件的兼容条件，避免把旧夹具缺字段当成新协议已验收。

### Q13 显式零对白目标失效

位置：`scripts/novel_ledger/style.py:215`。

章纲允许 `dialogue_ratio=0`，比较条件却采用 `0 < target <= 1`。完整提交中声明零对白，首章实际对白占比 83.1%、77 汉字、重复率 0，仍成功入库。纯函数对白占比 100% 的同类样例也没有 finding。

应明确零基数的比较方式，区分“目标未声明”和“明确声明为零”，补零边界回归。

## P3 文档与验收工具漂移

| 编号 | 位置与观察 | 处理建议 |
|---|---|---|
| D01 增量显式声明契约分裂 | `references/narrative.md:100` 要求四类增量可空但不得省略；`drift.py:360–364` 把缺字段/null 当空数组，`test_outlines.py:324` 还固定接受行为。删除四个字段后完整章纲仍通过。 | 明确采用显式声明或缺省为空，再统一实现、指南和测试；本轮不将既有宽松行为直接定为应当加严。 |
| D02 intake 示例过期 | `references/opening.md:161` 的 payoff 仅含 ending/theme；在当前新项目原样 intake 报 `opening_option`，缺 plan.ways，且未给 opening/5 的 anchor。 | 改为完整合法门值，或使用题材、书名等简单门举例，并通过当前入口验证。 |
| D03 锚点检查可以假绿 | `validation/anchor_check.py:27–31`：坏锚点即使被打印，退出码仍为 0；`anchor in title` 还把不存在的部分标题锚点判为有效。临时文档中 `#does-not-exist` 报 1 错但 exit 0，`#章纲` 对标题“章纲检查”报 0 错。 | 使用准确锚点规则，发现错误返回非零；补充同页引用和普通文件链接的覆盖范围说明。 |
| D04 当前度量入口指向旧快照 | `README.md:345` 称 `validation/metrics.json` 为当前工程度量，但该文件仍是旧结构：9,170 行、139 边；本轮为 12,201 行、137 边。 | 为快照保存日期、源码提交和度量版本；明确当前入口，历史结果保持原条件。指标变化不等同于质量变化。 |

## 合理性与验收范围

SQLite 真源、冻结材料、设计与事实分离、章纲状态链及有限返修是合理的职责划分，当前依赖图和存储合成测试为其提供了工程证据。主要问题集中在同一规则未贯穿整个生命周期：设计期会拒绝的知情倒退，执行期可以通过；世界要求和绑定分别生成；作者停点存在，却没有可继续的接受转换。这些应优先通过共享规则和状态转换修复，再考虑增加协议字段。

删除独立文学审查是已有作者决定，活跃指南也已说明代价，本轮不将其本身列为缺陷。机械核账只能验证结构化声明、证据定位与指标，不能证明正文语义、人物可信或阅读体验。十三门和固定卷纲成本是否适合微型项目，需要同条件真实试用判断，不能仅靠合成派工数下结论。promise_anchor 与上层不变结构当前仅作声明，也已明确公开，不计作本轮新增缺陷。

本轮覆盖技能工程及其内容漂移防线，使用临时数据库和合成正文；没有现成小说正文项目可供逐章抽读。真实模型长篇、宿主会话隔离和计费用量仍按 `references/validation.md` 独立验收，500 章、150 万合成汉字的存储测试不能替代这些验收。

## 修复顺序与复验条件

1. 先修 Q01/Q02，保护正式稿完整性与实际事实入账。
2. 再修 Q05/Q06/Q07/Q08，打通等待、作者接受、修订采纳与派生视图恢复。
3. 统一 Q03/Q04 的执行状态规则，以及 Q09/Q10 的任务生成契约。
4. 补足或收窄 Q11/Q12/Q13 的闭合与文风保证，同步文档、合法夹具和行为测试。
5. 修复无效测试夹具与 D01–D04，再跑全量和专项回归。新增行为回归应验证本报告的具体结果，包括未完成采纳被拒且正式稿不变、计划外事件进入状态、活跃回执仍能提交、作者接受后真正前进、修订就绪与正式采纳可区分。

本轮对抗样例及完整观测存于 [quality-run-2026-10-19.json](quality-run-2026-10-19.json)。既有专项脚本全部通过与本轮新发现并不冲突：这些边界大多不在既有样例中，部分测试还固定了与当前指南不同的行为。
