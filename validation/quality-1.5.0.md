# 1.5.0 质检报告（长篇小说 / 架构解耦 / token 消耗）

> 历史归档：本文件保留当轮版本、设计或实验条件，不是当前执行规范。旧门序、兼容条款、独立审查阶段及命令均不用于当前流程；当前唯一执行依据见 [任务协议](../references/protocol.md) 与 [运行流程](../references/runtime.md)。

日期：2026-10-16。审计对象：`main` @ `5e2cb71`（离线 1.5.0 合并后）。范围：长篇创作能力、架构解耦、token 与上下文字符消耗。

本报告是**对照审计**，不是作者的验收记录；原始工程结果见 [验收记录](results.md)，度量原值见 [metrics.json](metrics.json)。结论与作者自述不一致处，以本报告点名的代码位置和复现方式为准。

复现入口（Windows 控制台需 UTF-8）：

```bash
PYTHONUTF8=1 python validation/run_tests.py fast
PYTHONUTF8=1 python validation/run_tests.py full
PYTHONUTF8=1 python validation/measure.py --out /tmp/metrics.json
```

---

## 一、总评

| 维度 | 评级 | 结论 |
|---|---|---|
| 架构解耦 | 强 | 逐模块依赖白名单、全作用域无环、核心 I/O 禁令都真实生效；痛点不在方法级耦合，而在**数据契约**（kv 键空间、冻结任务信封字段、阶段名）没有权威表 |
| token 消耗 | 设计好、证据薄 | 必读材料与书籍体量真正解耦（实测恒定）；但全部是字节证据，**没有真实计费或端到端数据**，且有两条非默认路径会退化 |
| 长篇小说 | 机制齐备、未验收 | 滚动规划、有界覆盖树、连续性结算、分级修订都在；**真实长篇长跑从未完成**、端到端实验最大 6 章；另有存储/写入二次膨胀与默认配置下的修订退化 |

一句话：**工程边界与材料选择是这套实现最扎实的部分，文学质量与真实费用是它自己划清、也确实没有验证的部分。**

---

## 二、架构解耦

### 证据

- [tests/test_architecture.py](../tests/test_architecture.py) 的 `ALLOWED` 逐模块声明允许的内部依赖（L13-59），并断言源码模块集合**恒等于**该表（L148-149）：新增模块或新增依赖必须显式写下架构决定。
- `CORE_EXTERNAL` 逐模块限制外部导入（L63-92），`FORBIDDEN_CORE_NAMES = {open, __import__, eval, exec, Path}`（L93）；扫描同时拦截 `ast.Name` 载入与 `ast.Attribute`（L126-132），覆盖函数内、绝对、相对与 `from` 导入（L96-123）。
- 扫描器**自带自测**（L176-204）：验证它能发现延迟导入、内建别名与 `Path` 访问；`test_every_module_has_an_explicit_dependency_boundary`、`test_complete_import_graph_is_acyclic` 均为真 AST 扫描。
- 实测依赖图：**34 模块 / 120 条内部边 / 0 环**，与 [metrics.json](metrics.json) 逐字段一致（本次重跑完全复现，仅耗时不同）。
- 组合根唯一且薄：[bootstrap.py](../scripts/novel_ledger/bootstrap.py) 74 行装配具体存储、冻结编译、交付、页面、宿主与工作区；`ALLOWED['novel'] = {contracts, bootstrap}`，CLI 不接触适配器。
- 端口替换有行为验证：[tests/test_application_ports.py](../tests/test_application_ports.py) 7 项全过（内存账本跑通生命周期、只读账本出交付、替代宿主与运行工厂执行公开入口），[tests/test_host_ports.py](../tests/test_host_ports.py) 除符号链接权限项外全过。
- 架构图真源、mmd 快照、README 块与 SVG 节点连线逐项核对（`test_architecture` 与 [tests/test_runtime.py](../tests/test_runtime.py) L971-973）。

### 风险

1. **数据契约没有权威表**。方法级注入干净（Application 用到的 Repository / Presentation 方法全部在 [ports.py](../scripts/novel_ledger/ports.py) 声明），但适配器直接读应用私有 kv 键：[delivery.py](../scripts/novel_ledger/delivery.py) L59 读 `claim:<task>`、L153 读 `official_branch`。键空间与值形状无处声明，接第二套存储要逆向应用私有约定。
2. **冻结任务信封字段无字段表**。信封由 [context.py](../scripts/novel_ledger/context.py) 组装、被 application / workflow / delivery / 模板共读；`book_state.PART_FIELDS` 那种"集中声明并拒绝未知键"的做法没有复制到任务信封。
3. **阶段名无注册表**。阶段字符串散布在 workflow / context / briefs / result_templates / delivery 五处以上；未知阶段是静默降级（`briefs` 返回 None、`result_templates` 兜底成设计形状），新增阶段漏改一处不报错。
4. **`contracts` 扇入 30/34**（本报告独立统计），作为字段唯一权威是正确设计，代价是任何字段表抖动波及全库。
5. **单一权威只做了一半**：`CONTRACT_ALIGNMENT`（[contracts.py](../scripts/novel_ledger/contracts.py) L184）被 [planning.py](../scripts/novel_ledger/planning.py) L7 import 后全库再无使用；`_v1_groups`（[creation.py](../scripts/novel_ledger/creation.py) L483-489）手写第二份 v1 门→字段映射，而 `_v2_groups`（L492-500）从字段表派生。
6. **守护测试的边界**：I/O 禁令是名字黑名单，`getattr(__builtins__, 'open')` 一类写法（以及 `patch('builtins.open')` 拦不住 `Path.read_text` / `os.open`）可以有效绕过；`CORE_EXTERNAL` 只覆盖部分模块，适配器不在其列，且没有"每个模块必须登记在核心或适配器之一"的断言防漏登记。[tests/test_domain_boundaries.py](../tests/test_domain_boundaries.py) L98-115 另立了一份更窄的边界表（5 个模块、只看相对导入）。
7. `application.py` 805 行、15 个内部依赖、45 个用例方法；[bookpage.py](../scripts/novel_ledger/bookpage.py) 701 行。是用例外观而非领域上帝对象，但继续增长会变难维护。

---

## 三、token 与上下文字符消耗

### 量化表（实测）

| 指标 | 数值 | 类型 |
|---|---|---|
| 必读记录 vs 未引用未来设计节点 10/100/1000 | 2730 / 2730 / 2730 B | 本报告复现 |
| 全量全书设计（不进必读，按哈希补读） | 2749 / 24619 / 244219 B | 本报告复现 |
| 连续因果节点 20/100/500 必读 | 3610 / 3610 / 3619 B | 本报告复现 |
| 编辑能力夹具 20/100/500 必读 | 5153 / 5153 / 5164 B | 本报告复现 |
| 500 条创作解释 | 只选 3 条，必读 4616 B 恒定 | 本报告复现 |
| `history_source` 冻结入口 | 197 / 198 / 198 B（20/100/500 章） | 本报告复现 |
| `recall` 实际读取字符 | 4237 / 4240 / 4253 | 本报告复现 |
| 旧全量目录+事件索引（对照对象） | 5846 / 29370 / 148570 B（约 290 B/章） | 本报告复现 |
| 无命中查询扫描页数 | 20 / 100 / 500（等于章数，最坏线性） | 本报告复现 |
| 单任务全部派工文件 | 5.2–9.0 KB（book_plan→chapter_review） | 本报告实测 |
| 其中 task.json | 4.5–5.1 KB（`commands` 1307 B、`records` 895 B） | 本报告实测 |
| `advance --compact` / 非 compact | 0.4–0.9 KB / 4.5–5.1 KB（约 6–12×） | 本报告实测 |
| 覆盖树约束 | 深度 2/4/5；每综合者 ≤3 子报告、≤6 边界章 | 本报告复现 |
| 综合 handoff 上限 | 6 项 × ≤800 字 + 1–8 条 × ≤240 字引文 | `scripts/novel_ledger/scopes.py`（历史模块，当前已删除） L52-56 |
| 默认窗口/分块 | `planning_window=3`、`review_chunk=3`、`review_fanout=3` | [contracts.py](../scripts/novel_ledger/contracts.py) L167-172 |
| 默认开关 | `verification=full`、`narrative_tracking=true`、`editorial_features=true` | [contracts.py](../scripts/novel_ledger/contracts.py) L170-173 |
| 运行期 guides 体积（路径挂载，非信封体积） | protocol+craft+editorial+workbench = 48,781 B | 本报告按磁盘字节核算 |
| `check` 免提交试算 | 从在途任务直接预览，不提交、不消耗额度 | [application.py](../scripts/novel_ledger/application.py) L211-238 |
| 真实 token 观测 | 只接受 provider 的 input/cache_read/output，缺失填 null，不发明费用 | [observe.py](../scripts/observe.py) L19-29 |
| 真实会话观测（作者估算，非计费） | 7 会话 217 步，输入 4318 万字符 / 输出 44.7 万字符 ≈ 96:1，主控占 44% | [results.md](results.md) L32 |

### 结论

- **每任务必读材料与书籍体量确实解耦**：设计节点 10→1000（体积 +8900%）、因果节点 20→500、解释 20→500 条，必读字节波动 <1%。`history_source` 是 198 B 的指针而非全文，`recall` 靠页化只读约 4.2 KB。
- 主控侧有 `--compact`，实测主控每步只拿 0.4–0.9 KB，完整 `task.json` 留在磁盘交 Worker；"主控不读写正文"由 [novel.py](../scripts/novel.py) L18 `WORKER_ONLY` + L112-130 身份校验机械约束（但只拦 CLI 命令，主控自身文件工具仍可读 `book.md`/`work/*/chapter-*.txt`）。
- 已知反模式基本被处理：读源码当材料→`check`；`guides` 只给路径；`brief` 现生成；baseline 取任务冻结 state；读写实际字符计入 usage。

### 风险

1. **没有真实计费数据**。作者在 [验证](../references/validation.md) L10 与 [results.md](results.md) 反复声明"字节不能换算 token 或费用"；`usage` 只记字符、`billed_tokens` 为 null。
2. **96:1 的输入膨胀不在引擎手里**，来自宿主每步重发历史。引擎只能减少步数与单步材料（compact / check / 按需投递），无机械步数上限。
3. **非追踪约定会退化**：[context.py](../scripts/novel_ledger/context.py) L212-222 在 `narrative_tracking=false` 时对 story 取依赖**传递闭包**（追踪只取一跳，L217-218）；L225-226 在非追踪时把**整份设计**列为必读（追踪只挂窗口切片 `frontier:`）。触发条件是旧约定/导入约定，默认开关为 true。现有夹具测不出：[measure.py](measure.py) L76 使用无依赖节点，所以恒为 2730 B。
4. **整本书进单个 Worker 的路径存在，但需两个非默认开关同时成立**：[workflow.py](../scripts/novel_ledger/workflow.py) L174 `block_last = last if fast`、L164-165 finish 时范围=全书、[context.py](../scripts/novel_ledger/context.py) L302-303 prose 取该范围全部章。**仅在 `verification=fast` 且 `narrative_tracking=false` 时**成立；默认 full + 追踪时经 `scopes.next_review` 走有界树（L169-170，L151 注释明写该保证）。
5. **同一章正文每章约 5–7 次进入上下文**：write / plan 各带前 2 章完整正文（L315-320），chapter_review 带草稿（L299），repair / redesign 带 `base_draft`（L324），scope_review 再读整块。以 3000 汉字/章计，一次 write 派工约 32.9 KB，其中前两章正文占约 55%，`brief` 只占约 5%。
6. **`briefs.py` 无任何长度上限**，全库唯一裁剪是 [context.py](../scripts/novel_ledger/context.py) L87 把已选方向摘要截到 60 字。
7. **guides 按能力而非按阶段挂载**（[delivery.py](../scripts/novel_ledger/delivery.py) L84-89）：`editorial_features` / `understanding` 启用后，运行期每次派工列出约 48.8 KB 的参考文档（信封里只有路径）。缓解是 [SKILL.md](../SKILL.md) 的"只读相关小节"，属模型自律，无机械上限。
8. **两条最坏路径线性于篇幅**：无命中 `recall` 与指定旧章补读（实测页数=章数）。作者已声明"不宣称最坏查询复杂度不随篇幅增长"。另有两条未在度量里体现的整书路径：`fork` 需回溯到起点建候选，`repo.load()` 每次反序列化**整个 intent + canon 分区**（[sqlite_store.py](../scripts/novel_ledger/sqlite_store.py) L121-123）。

---

## 四、长篇小说

### 机制（有代码/测试支撑）

- 默认 `rolling`：只完成近期已核验卷纲，按需补下一批（[架构](../references/architecture.md) 当前能力边界表）；批大小 = `min(6, planning_window)` = **3 章/批**（[workflow.py](../scripts/novel_ledger/workflow.py) L56）。`scope=current` 先出首卷全卷纲，`scope=all` 也仍分批派工 + 独立批审，不是一次交付。
- **有界覆盖树**：`scripts/novel_ledger/scopes.py`（历史模块，当前已删除） L9-28 固定 chunk/fanout 递归；500 章实测深度 5、每综合者 ≤3 子报告、≤6 章边界正文、handoff 六项各 ≤800 字。综合成本被硬性封顶。
- 连续性结算：资源前值与守恒、时钟、知情、关系、承诺、站位、历史断言由 `facts` / `narrative` 纯规则执行，设计与人物档案不直接产生事实。
- 修订不毁全书：`revision_impact` 输出 keep / review / local / rewrite 四级；默认只自动改最近 3 章并保护已关闭卷。
- 完本必须覆盖末章、实际总篇幅区间、作者首章决定和全部关闭条件，不自动降目标。
- 断点恢复、租约、首读冻结、`--after` 核实均有独立行为测试。

### 风险

1. **真实长篇文学验收尚未完成**。[验证](../references/validation.md) L83 明写"真实长篇文学对照尚未完成"，[results.md](results.md) 每轮均以"没有实际模型长篇试写"收尾。**"支持百万字"目前是设计与合成度量，不是已证事实。**
2. **测试量级与命名不符（本轮实测）**：[tests/test_revision_bounds.py](../tests/test_revision_bounds.py) L38 用 `tracked_contract(6)`，端到端最大 **6 章**；[tests/test_longform.py](../tests/test_longform.py) 自述是机制测试（`range(1, 5)`），其余为纯函数夹具。夹具正文是**同一句约 90 汉字的固定文本**（[tests/support.py](../tests/support.py) L77-78），契约章幅 `chapter_min=12 / chapter_max=90`（L19），而真实档位是 2500～4500 汉字/章；回执程序化填 pass、理由写"工程夹具"（L80-88）。500 章"历史"是**裸插 chapters 表、不经审稿**（[tests/test_history.py](../tests/test_history.py) L18-29 注释自认）。
3. **【高】存储与写入二次膨胀，且从不回收**。机制：每次 `save` 都把**整个 intent 分区**（plans + designs，随章数增长）按新哈希写入不可变 [sqlite_store.py](../scripts/novel_ledger/sqlite_store.py) L140-147（`documents` 表），旧快照永不删除；全库**没有任何 `DELETE FROM` 或 `VACUUM`**。本报告独立探针（200 章 × 3000 汉字，含逐章场景与节点）：DB **1.05 / 3.16 / 6.39 / 10.76 / 16.27 MB** @ 40/80/120/160/200 章，每 40 章增量 2.11→3.23→4.37→5.51 MB（**增量本身线性增长 ⇒ 累计二次**），每章写入 21.2→32.3 ms。另一路并行审计在更厚计划下测到 600 章 **433 MB**、每章 24.6→253 ms，趋势与本报告探针一致，常数随计划厚度变化（该外推未由本报告复算）。
4. **【高】默认 `dependency_coverage=partial` 会让"窄修订"退化为整段后缀重写**。[story_memory.py](../scripts/novel_ledger/story_memory.py) L50 缺省即 `partial`；[revision_impact.py](../scripts/novel_ledger/revision_impact.py) L80 `unknown = plan.get('dependency_coverage') != 'complete'`、L83 命中 `unknown` 即把后续每一章加入重写区间并沿 L92 继续级联。**语义修订**（`mode == semantic`，L70-77）因此默认重写到末章；表达/阅读修订不受影响。[briefs.py](../scripts/novel_ledger/briefs.py) L104 要求执笔显式声明 `complete`，属逐章自愿。
5. **【中高】作者/主控 `revise` 默认无界**。[revision_service.py](../scripts/novel_ledger/revision_service.py) L172-173：`changes` 为空时 `impact=None`，`through` 也为空时 `end = book_last` —— 一句 `revise --from-chapter N --reason "…"` 即从第 N 章重写到末章，无需显式扩大区间。审稿触发的路径反而受 `revision_bounds` 三重约束保护，两条路径不对称。
6. **【中】完本覆盖只覆盖"已登记项"**。[editorial.py](../scripts/novel_ledger/editorial.py) L51-70 的 sources 为 reader_promise / ending / theme（声明才有）/ world_rules / red_lines / style_traits / relationships / arcs / 作者反馈 / 节点 outcome / 线路 ending_condition / hooks / 修复案；**人物成长记录（[facts.py](../scripts/novel_ledger/facts.py) L223-226 只累加）、reader_knowledge 话题、世界谜题（[world.py](../scripts/novel_ledger/world.py) L16 有 truth/disclosure 但不在 sources）不进入完成覆盖**。且 `editorial_features=false` 时连 `completion_coverage` 都不要求。
7. **能力开关需要运维记忆**：1.5.0 新能力默认只对新项目/显式改约启用，旧在途任务按冻结协议解释；creation/1·2、editorial/1、库 schema、检查清单版本构成一张版本矩阵。
8. 语义质量仍依赖独立审稿者；引擎只保证"不能悄悄越界"。

---

## 五、交叉复核中被修正的结论

审计回执与独立复算不一致处，按下列结果为准：

| 原始说法 | 复核结果 |
|---|---|
| "依赖边实为 122，`metrics.json` 低估" | **不成立**。用同时收录 `ast.Import` 与绝对/相对 `ImportFrom` 的全扫描器复算 = **120**，与 [metrics.json](metrics.json) 一致；窄扫描器同为 120，两者差集为空 |
| "整本书进单个 Worker：高" | **降级为中**。需 `verification=fast` **且** `narrative_tracking=false` 同时成立；默认配置走有界树 |
| `--compact` 434 B vs 833–855 B 的差异 | 口径不同（是否含内联 `status`）。统一表述为 compact 0.4–0.9 KB vs 非 compact 4.5–5.1 KB |
| `validation/results.md` 历史字节与现行 `metrics.json` 不一致 | 属时间线日志，已被后文取代；本次不动历史记录，只以现行度量与复现为准 |

本轮（长篇维度）追加复核：

- **存储二次膨胀已独立复现**：曲线见第四节风险 3。趋势与并行审计一致，但**绝对常数不同**（本报告 200 章 16.27 MB，对方 200 章 50.18 MB），差异来自逐章计划的厚度与 designs 结构；两边都是合成夹具，都不能当作真实项目的绝对值。
- 对方未测到 `_audit` / `replay` 在 promote / complete 时的全书重放耗时，只用等价的批量文档读取做代理；**本报告同样未测，该耗时仍属未知**。
- 对方把"整本书进单 Worker"列为高危，本报告按代码复核**降为中**（需 `verification=fast` 且 `narrative_tracking=false`），此结论不变。
- 对"依赖边 122"的否定见上表。

---

## 六、建议

1. **先补真实计费验收**：用 [observe.py](../scripts/observe.py) 对一次 20–40 章连续试写入账，拿到 input / cache_read / output 与每章任务数。这是唯一能验证本报告第三节结论的动作。
2. **把 kv 键与冻结任务信封字段补成显式常量表**（照 `book_state.PART_FIELDS` 的做法集中声明并拒绝未知键），同时消掉"改存储要逆向私有约定"。
3. **给非追踪路径补回归或收窄**：`narrative_tracking=false` 时不应把整份设计列为必读；`verification=fast` + 非追踪应拒绝或强制分块。
4. **补一条真正的规模回归**（50–100 章合成滚动流程），让 `test_longform` 的名实相符；现有 500 章数据只覆盖传输层。
5. **减少每任务固定开销**：`task.json` 与 `input.json` 字段重叠，`commands` 每任务重发 1307 B。
6. **补一条守护断言**："每个模块必须登记在 `CORE_EXTERNAL` 或显式适配器集合之一"；删除 `CONTRACT_ALIGNMENT` 死导入，合并 `_v1_groups` 到字段派生。
7. 把"真实长篇验收"落成可复跑清单产物 —— 方法已在 [验证](../references/validation.md) 写好，缺的是执行记录。
8. **给存储加保留策略**：intent 快照按周期合并（如每卷或每 N 章一个检查点，其间增量），或提供显式的回收/压缩命令；至少把"documents 只增不删"从隐含行为变成文档化的容量模型，让作者知道 600 章会占用什么量级。
9. **把 `dependency_coverage` 的缺省反过来**：缺省声明不清时，修订应提示"将扩大为整段后缀重写"并给出受影响章数，而不是静默重写；或让新项目的执笔任务默认产出 `complete`。
10. **收窄 `revise` 的默认区间**：无 `--through` / `--changes-file` 时应先返回影响范围与影响章数，要求作者确认扩大，而不是直接 `end=book_last`；两条修订路径（作者发起 / 审稿发起）的边界应对称。
11. **明确完本覆盖的边界**：把人物成长、`reader_knowledge`、世界谜题是"不进完成覆盖"写成显式条目，或在 `sources` 中把它们列为可选要求，避免"机械验收通过"被误读成文学意义上的完结。

---

## 附录：本次验证环境

- `validation/run_tests.py fast`：**80 项通过**。
- `validation/run_tests.py full`：**372 项，0 失败，1 跳过，11 错误**；11 项错误全部为 `OSError WinError 1314`（`os.symlink` 需 Windows 开发者模式或管理员权限），来自 [test_host_ports.py](../tests/test_host_ports.py) L103、[test_presentation_boundaries.py](../tests/test_presentation_boundaries.py)、[test_storage_boundaries.py](../tests/test_storage_boundaries.py) 的符号链接逃逸用例，非代码缺陷。
- `validation/measure.py` 输出与 [metrics.json](metrics.json) 逐字段一致（除耗时）。
- **存储增长探针（本报告独立）**：200 章 × 3000 汉字、逐章累积场景与节点后逐章 `save`，DB 1.05 / 3.16 / 6.39 / 10.76 / 16.27 MB @ 40/80/120/160/200 章，每章写入 21.2 / 24.0 / 27.4 / 29.7 / 32.3 ms；`documents` 行数为 3n+5（线性，靠内容哈希去重），体积按 Σ 全 intent 快照呈二次。
- 本报告未修改引擎、测试或既有文档；所有夹具项目建在临时目录并已清理。
