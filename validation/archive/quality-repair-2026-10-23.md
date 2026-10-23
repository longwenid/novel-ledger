# Antigravity 审计后的架构修复验收

范围：novel-ledger 主干，CLI 2.1.0，数据库格式仍为 novel-ledger/5。依据是本仓库 83b1484 保存的历史审计；不修改原小说、原会话或历史报告。此文记录当前实现和工程验证，不是创作规范入口。

## 已实现的修复

| 问题 | 当前行为 | 主要回归证据 |
|---|---|---|
| 事务接受被误当章节通过，诊断只看文风 | submit/check/preflight 返回统一 outcome、总 findings、事务状态和下一动作；章节以 committed_chapter 判断 | test_execution_handoff；原 WF-04-current 探针 |
| 新执行者继承前人已读状态 | 材料缓存绑定 execution_id、材料名和内容哈希；新上下文重交全部必要材料；快组仅同一上下文复用 | test_execution_handoff；原 CR-02 探针 |
| 成功重提被活任务/快组门禁误拒 | 已完成任务准确回执确认保留原业务结果和章节；冲突回执仍拒绝 | test_execution_handoff、test_fast_writing；原 CR-01 探针 |
| 无关 read/ready 清空技术失败 | 仅对应失败操作成功或终结提交解除非阻断失败；到限统一 worker_blocked，恢复留事件 | test_execution_handoff、test_fast_writing；原 AR-03 探针 |
| 同一失败稿反复耗文学额度 | 实际正文和诊断签名检测相同稿、空白变化及已知失败稿回转；no_progress 回滚，不新增文学轮次 | test_execution_handoff；既有返修收敛测试 |
| 自造会话名、作者原话可伪装可信来源 | advisory 显示未验证；required 验证宿主实际上下文、项目受众、签名、准确对象、原话和一次性凭据；未登记 Worker 不能绕过 prepare 直接提交 | test_host_authority、test_fast_writing |
| 直接清预算/诊断后接写 | 正式状态写入建立治理投影和策略检查点；异常后保留现场并拒绝推进 | test_continuity_flow、test_verification |
| 写作过程中替换引擎或指南 | 冻结引擎及规则指纹；执笔和独立读者都检查构建一致性 | test_execution_handoff、test_continuity_flow |
| 独立阅读被执笔自评诱导 | 原文首读 → 冻结观察 → 再看章纲和自评 → 版本化报告；引文绑定准确原文及偏移 | test_continuity_flow 的 API 与真实 CLI 交接 |
| 核验复试回退状态、反复派读或绕过额度 | 观察/报告/裁决准确重试幂等；同正文改附带字段不能重派；正在阅读不能换稿；阻断报告须先结算返修 | test_continuity_flow |
| 正常恢复触发同稿重复阅读 | 候选哈希保留全部内容，排除传输身份 session/execution_claim；合法更新凭据可沿用未改内容的报告；身份仍独立验证 | test_continuity_flow |
| 明确死亡后无解释再次存活 | 独立原文观察中确定的 dead→alive 形成矛盾；表象、传闻、补叙、并行和有据复苏分别处理 | test_continuity_flow |
| 几分钟战斗按章加天、未结期限消失 | 可选 timeline 校验同批主线场景、跨夜间隔、并行/补叙及期限承接；延期必须更新 due 并给故事内事件 | test_continuity_flow |
| 独立核验的新增成本隐形 | usage 单列 continuity_read_calls / continuity_read_chars；保持 billed_tokens 未知，不从字符推费用 | test_continuity_flow |
| 完本后改坏可变行影响覆盖说明 | 完本 audit 的核验覆盖使用已复验冻结章节，与交付快照一致 | test_verification |

规划模板另分 story_events 和 reader_effect，读者效果不进入事实结算。相邻章中的编辑意见和作者保留的歧义作为有版本的材料传给后续执笔者。减少形容词堆叠的默认文风保留，优先动作、事实与具体细节；不增加形容词配额或把文学偏好当机械拒稿条件。

正式 submit 后的书页刷新仍由提交后回调执行，快组每章同样刷新 book.html；未采纳的核验候选不冒充正式章节。既有 bookpage、fast_writing 和 runtime 测试一并回归。

## 默认与旧项目

新 CLI 项目默认 continuity=required、trust=advisory，需要宿主实际创建独立读者。它会增加真实阅读调用，不保证总费用下降。运行指南不再把旧单次实跑的费用比例或返修率外推为新流程的成本、文学质量保证。API 初始化保持显式装配约定；旧项目按原模式恢复，不倒填报告、构建证明或可信身份。

策略切换须有来源且没有在途任务；冻结构建变化须保留稿件、恢复原构建或按明确升级决定重新冻结。新模式的交接、模板与受控宿主装配入口见 [质量与宿主](../../references/quality.md)。

## 验证

- 完整回归：`python3 -m unittest discover -s tests -q`，592 项通过。
- 技能格式：skill-creator quick_validate 通过。
- 活跃指南链接：17 份文档，0 个失效引用。
- 原审计四个协议探针：CR-01、CR-02、AR-03、WF-04-current 均 defect_observed=false。探针只在临时工程运行，结果摘要另存于同名 JSON。
- 差异检查：git diff --check 通过。

所有自动回归使用工程夹具和临时项目。真实 CLI 测试证明命令与事务交接可以运行；没有实际调用模型来假充一次独立创作验收。

## 仍需部署和真实创作验收的部分

SignedHostAuthority 是受控宿主的验证适配器，不是 Antigravity/Codex 平台插件。本机没有部署服务账户、Worker 沙箱或真实人类交互签发通道；同系统账户仍可同时改数据库和检查点。required 模式缺可信宿主时拒绝执行，advisory 不宣称具备权限隔离。

独立观察由实际读者从原文提取，程序能验证引用和已声明约束，不能证明引用支持任意自然语言断言，也不能保证没有遗漏动作、地点、证物、知情或人物关系。跨卷期限和远章冲突须补读原文。通用语义检测召回率、误报率、文学效果及输入/缓存/输出 token 改善尚未测得，不能以合成测试通过代替这些结论。

发布包包含可用技能源码、指南、模板、测试和这份验收记录；排除私有会话审计、用量摘录、小说数据库、运行目录及缓存。本次仅本地提交，不推送或合并远端分歧。
