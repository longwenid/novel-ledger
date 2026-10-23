# 当前2.0.1执行交接独立审查

范围：main `54c0047` 的prepare-worker、Python worker、worker_ready、技术失败、worker-next。用现有support夹具在临时独立工程复现，未修改仓库和真实小说项目。

结论：确认2项仍存在的用户可见缺陷：新入口破坏重复提交确认；更换Worker后阅读缓存导致空历史执行者没有必读材料。两项均为真实CLI生成命令复现，不依赖直接改库或篡改源码。

隔离工程：`/tmp/novel-handoff-review-a80mmwoz`。复现脚本：`/tmp/novel-ledger-quality-20261022/reproduce_current_handoff.py`。原始输出：`/tmp/novel-ledger-quality-20261022/current-handoff-repro.json`。

## CR-01 [P2] Python worker 的就绪预检挡住已提交回执的幂等重试

位置：`/Users/longwen/AndroidStudioProjects/skills/novel-ledger/scripts/novel.py:294`。

**触发**：真实Worker依生成commands.submit完成提交，第一次响应丢失或宿主重试原命令；项目和任务身份未更换，result.json未改。

**实际返回**：首条生成命令code0、committed_chapter=1；完全相同的生成命令第二次code2/stale_task，retry_allowed=false，要求主控prepare-worker --reset-failures。应用层用数据库已保存的同一canonical receipt重试却正常idempotent=true。

**预期**：相同回执返回已提交的幂等确认，保持章节数、稿件和轮次不变；冲突内容才报replay_conflict。

**原因**：portable入口对除worker-next外所有命令先执行worker_ready；worker_ready调用_live，要求task.pending。它在Application.submit的done/hash幂等分支之前拒绝已提交任务。prepare-worker也要求_live，因此错误建议的重置操作不能恢复这次已成功的提交。

**影响**：新默认执行入口破坏旧提交接口的幂等承诺；宿主重试把已经成功的写作误报失败，强制主控介入。无证据显示重复章节或数据损失，问题是可恢复性和准确提交确认。

**修复方向**：在读取回执并注入本次身份之后，由submit统一处理terminal replay：允许精确匹配的已提交回执进入幂等分支；对pending继续执行准备/租约/失败阻断检查。不要对read等材料入口全面放宽_live。返回稳定的提交确认及原committed_chapter，让宿主无须猜成功与否。

**必要回归**：

- 经真实生成的Python worker命令连续submit两次同文件：两次code0，第二次idempotent=true，章节/轮次只有一次。
- 快组当前章已提交、worker-next已经建立下一章、原组已结束三种状态均可确认旧回执，不能分叉或跳章。
- 同task改正文/身份/凭据后重放应replay_conflict或相应身份错误；过期未提交任务依旧拒绝。

## CR-02 [P1] 更换普通任务 Worker 后首读沿用前执行者缓存，空历史 Worker 得不到必读材料

位置：`/Users/longwen/AndroidStudioProjects/skills/novel-ledger/scripts/novel_ledger/application.py:355`。

**触发**：普通pending任务中，Worker A已经read，随后停止且租约过期；主控按恢复顺序status→advance --compact，再prepare-worker把同task绑定真实新Worker B。

**实际返回**：A首读7项。确认租约过期后主控status/advance、prepare B都成功，B首条生成read code0，但records={}、already_read列出7项、complete_records=true。B用read --all才重新得到7项。

**预期**：B作为空历史执行者，生成的首条read交付本任务全部required；同执行者重复read仍可复用已读缓存。保留同task/result和文学预算。

**原因**：Application.read按repo.read_names(task_id)跳过记录，历史read日志只绑定task，不绑定session/执行世代；prepare_worker换session时保留相同task却不改变此缓存。新入口的身份ready检查与阅读交付使用不同粒度。

**影响**：最短自举流程让新Worker在缺全部冻结设定/章纲/前态时收到“材料完整”成功响应。即使Worker根据already_read_note主动--all可绕过，也违反新Worker完整读取约束，且不能指望空历史Worker知道前执行者读过的材料自己没有。

**修复方向**：把材料交付缓存绑定受控execution_id/session及名称+hash；同task换执行者时启用新阅读世代，首读完整交付。仅同一真实Worker的受限快组允许跨task复用。短期可在prepare-worker检测session变化时显式给新派工首读--all，但需避免把任务级历史统计伪装为当前执行者已读。

**必要回归**：

- A读取全部后停止，租约过期，status/advance→prepare B：B首读records名称必须恰等于required。
- A只读取单个record后换B：B仍拿全部required；保留同task/input_hash/result不变。
- 同session恢复且模型历史保留时可复用；主控明确空历史重开时即使session标签复用也要新execution世代。
- 快组内同Worker复用未变hash仍有效；新组/换Worker不得继承旧read_hashes或task日志。

## 已核实的边界与次要观察

- 同稿重复提交失败未造成重复章节或数据丢失；直接应用接口仍正确幂等，因此是新portable前置检查的回归。
- 换Worker缺材料可通过`read --all`补救，但引擎正常首读返回空资料且complete_records=true，不应把恢复责任全部交给新执行者。
- 快组重复worker-next在当前任务blocked时仍顶层task_ready，嵌套execution.state=blocked。后续read仍拒绝，未绕过技术阻断；建议动作出口统一，暂不列高优先级缺陷。
- 复现覆盖了首次提交、重复submit、租约过期后标准恢复、更换真实会话身份、补读以及快组任务阻断后的接续重试。未把宽权限本机安全边界当新代码问题。
