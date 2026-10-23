# novel-ledger 质检修复验收 2026 10 19

> 历史归档：本文件保留当轮版本、设计或实验条件，不是当前执行规范。旧门序、兼容条款、独立审查阶段及命令均不用于当前流程；当前唯一执行依据见 [任务协议](../../references/protocol.md) 与 [运行流程](../../references/runtime.md)。

[修复前质检](quality-run-2026-10-19.md)中的 Q01–Q13、D01–D04 已逐项处理，原始快照与结论保留。当前全量回归 **572 passed、1355 subtests passed、0 failed**；11 个专项脚本全部通过，pyflakes 无发现，技能基础校验和活跃文档链接检查通过。

修复基于 `9a2a5bb40be72c0d2d02c2bacc2bcf4fe7c0acf8` 的工作树，未提交或推送。当前源码以 [metrics.json](metrics.json) 的提交号与源码指纹共同定位；提交号表示基线，指纹包含本地修改。时间按 Asia/Shanghai 记录，度量生成时间使用明确标注的 UTC。

## 逐项处理

| 问题 | 修复后的可观察行为 | 回归依据 |
|---|---|---|
| Q01 未完成修订被采纳 | 未完成、有草稿、缺后缀或无修订时拒绝 promote，正式分支不变 | test_revision_bounds、test_revision_repairs |
| Q02 计划外事实漏记 | resources/places/knowledge/characters 的结构化实际变化生成事件、更新事实和后续重排前态；不可结算的说明明确拒绝 | test_drift_settlement、test_narrative |
| Q03 知情倒退 | 计划内偏差和计划外变化共用档位检查，拒绝 confirmed 降为 hinted，保留 retracted | test_drift_settlement |
| Q04 skipped 仍造事件 | 跳过只记偏差，不产生未发生的事件；跳过 plant 可提交并进入重排 | test_drift_settlement、test_narrative |
| Q05 watch 移走活动回执 | 等待已有任务不重建派工文件；有、无有效 claim 的回执都能继续提交 | test_unattended |
| Q06 接受候选后卡死 | 机械失败保留候选，只给明确再修或暂停调整约定的可执行选项；旧接受选项安全拒绝并回滚 | test_repair_convergence、test_runtime |
| Q07 修订完成路由错误 | 返回 revision_ready，采纳后恢复原授权目标；候选就绪与正式交付分开 | test_revision_bounds、test_revision_repairs |
| Q08 坏 task.json 阻断恢复 | 损坏 JSON、非对象和非法计数按旧视图不可用处理，从冻结输入重建 | test_presentation_boundaries |
| Q09 economy 要求冲突 | 已声明硬通货自动要求 economy，小体量简报与绑定一致，未声明的旧项目不追补 | test_world_grand |
| Q10 四案与三案上限冲突 | 脑洞、来历门统一从方向中提供 2～3 个具体方案 | test_opening |
| Q11 卷末终态不可计算 | 新卷用人物三字段终值与 clock.to 闭合，整卷另核对 advance_days；exit_state 明确仅作文字说明 | test_drift_settlement |
| Q12 文风必填漏验 | 新卷要求 style.trend，新章要求非空 pov/rhythm，非法对白目标拒绝 | test_drift_settlement |
| Q13 零对白目标失效 | 显式 0 真正参与比较，微量对白也不因展示舍入漏掉；可选目标不再由模板预填为 0 | test_style |
| D01 增量缺省契约分裂 | 保留缺字段/null 与空数组同义的已有行为，统一指南、简报、注释与错误文案 | test_outlines、活跃文档复核 |
| D02 intake 示例过期 | 示例改为完整合法的 title 与 scale，并通过当前 intake 入口 | test_opening |
| D03 锚点检查假绿 | 本地文件与精确标题锚点错误返回非零，覆盖同页、跨页和重复标题，忽略围栏示例 | test_validation_tools |
| D04 当前度量陈旧 | 刷新 metrics.json，生成时间、提交号和含本地修改的 Python 源码指纹随结果保存 | test_validation_tools、measure.py |

全量中原有的无效世界页面夹具也已改为真实 selection 形状，符号链接路径继续执行，没有用跳过测试掩盖失败。

## 协议与兼容

新冻结任务带 `outline_checks=outline-checks/1`。新卷必须填写 `clock={advance_days,to}`，其中 to 是卷末主线时钟绝对值；人物终态使用 `{desire,stance,relationship_focus}`。卷纲 trend 与章纲 pov/rhythm 按模板填写。缺少该能力的旧冻结任务按旧设计形状处理，已存旧卷纲不补造时钟终值或人物语义保证，历史章纲前缀不追溯新增文风要求。

`unplanned` 的可结算种类明确限定为资源、位置、知情和人物，必须给实际前后值、原因与精确正文引文，不能只提交 change 说明。情节、伏笔、披露和时钟仍受章纲契约约束。事实硬条件不能由“接受候选”豁免，候选、失败记录与已花额度都会保留。

## 验证与范围

- 全量：`python3 -m pytest -q -p no:cacheprovider`，572 passed、1355 subtests passed，27.28 秒。
- 专项：修复前使用的 11 个 validation 脚本全部退出 0。
- 静态与格式：pyflakes 覆盖 scripts/tests/validation，无发现；quick_validate、anchor_check 与保留 CRLF 的 diff 检查通过。pyflakes 仅装在临时检查目录，没有新增运行依赖。
- 度量：6 节执行成功、40 模块、137 依赖边且无环；`material.world_model` 仍明确标记为 blocked，不将该材料度量缺口说成完成。
- 独立使用验收：未读取本次审计或修复结论的验证者，在两个临时项目中完成授权小项目、历史候选准备与采纳、暂停恢复、预检回滚、人称违规拒绝及 complete/deliver，未发现阻断问题；使用导入约定夹具，十三门链路由已有专项脚本覆盖。

完整结果、检查返回值和准确源码指纹见 [修复验证数据](quality-fixes-2026-10-19.json)。

本轮验证使用临时项目和合成回执。真实长篇文学质量、模型历史隔离与计费用量仍属于独立验收范围；自然语言 exit_state、主题锚点和世界上层不变结构不被宣称已获得语义证明。
