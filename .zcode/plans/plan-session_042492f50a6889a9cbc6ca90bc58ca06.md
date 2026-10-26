# 多文风架构：解耦、可配置、默认选择

## 目标与总设计

把"单一默认文风"改造成**注册式多文风目录 + 契约可配置选择 + 引擎逐档案感知**。用户已新增 `references/styles/账房掌门.md`、`神秘学双声部.md` 两份纯档案（各含 MUST/AVOID、语料事实表），后续还会新增。

**生效档案优先级链**（一处函数统一解析）：
1. `PROJECT/style-profile.md` — 作者经 style-distill 提取并确认的自定义档案（最高，引擎检测到文件即生效，注册锚缺失时机械锚回落引擎默认）
2. 契约 `style_profile` — 从内置目录选定的档案名
3. 引擎默认 — `DEFAULTS['style_profile_default'] = '市井修仙'`

内置库选定**不再需要复制文件到 PROJECT**（原机制是引擎无感知的补偿；PROJECT 文件今后只留给自定义提取档案）。

## A. 文档重构

1. **新建 `references/styles/市井修仙.md`**：整体迁移 style.md 的档案主体（一~七节：定位/语料事实/八大维度/口癖清单/风格演变/标题风格/仿写规范 MUST15+AVOID15），头部改为与另两份一致的 `# 文风档案 · 市井修仙（默认）` 格式，引言写明样本与直角引号体例。迁移字节级保真（LF，吸取 da601ca 的 CRLF 教训）。
2. **`references/style.md` 重写为纯机制枢纽**（约 120 行）：何时读；优先级链；内置目录表（三份：名/一句话定位/链接，与 STYLE_CATALOG 同步、测试守卫）；选择与切换（`init --contract` 自备 / 逐门开书作者口头选定→约定激活后 `recontract --patch {"style_profile":"账房掌门"} --source 原话` / 运行中换档同命令）；通用执行机制（原「执笔读什么」「自比比什么」「首章认可」「与首章锚点的关系」改为对"生效档案"通用）；新增档案流程（style-distill→作者确认→文件入 `references/styles/`→`STYLE_CATALOG` 注册一行→可选改默认）。用户已写的「可选文风库」小节并入目录表。
3. **SKILL.md**：L53「作者与文风」条目补内置库与 `style_profile` 字段；L64（用户已改）对齐新优先级链表述。
4. **narrative.md「文风」节**：锚点回落段改为"回落契约 style_profile 所选内置档案的注册锚点"。
5. **protocol.md**：契约字段表加 `style_profile` 行；**opening.md**：补一句内置库选择时机（约定激活后 patch / 自备约定直接带）。
6. 小修：`账房掌门.md:38` 悬空引用「材料与方法」；两档案 `stats.json` 路径表述改为"提取时语料统计"。

## B. 引擎（scripts/novel_ledger/）

1. **contracts.py**：
   - 新增模块级 `STYLE_CATALOG`（与 DEFAULTS 同层，同受单源纪律约束）：
     ```python
     STYLE_CATALOG = {
       '市井修仙': {'file': 'styles/市井修仙.md', 'anchor': {现有 style_default_anchor 七项数值}},
       '账房掌门': {'file': 'styles/账房掌门.md', 'anchor': {…}},
       '神秘学双声部': {'file': 'styles/神秘学双声部.md', 'anchor': {…}},
     }
     ```
     标定规则：`han` 一律 2000（可比性门槛非形状，沿用 4e9340e 结论）；`paragraph_mean/paragraph_max/dialogue_share` 取各档案"语料事实"数值（账房掌门 47.6/451/0.2643，神秘学 36.1/204/0.3652）；`sentence_mean/sentence_short_share` 档案有则取、无则沿用通用值并注释（实现时通读两档案语料事实节取数）。
   - `DEFAULTS['style_profile_default']='市井修仙'`；**删除** `DEFAULTS['style_default_anchor']`，新增 `profile_anchor(name)` 返回 `{**anchor, 'origin':'default', 'profile':name}`（非法/缺失名回落默认档），消灭双源。
   - `CONTRACT_FIELDS['style_profile']`：text、optional、choices=tuple(STYLE_CATALOG)、default=DEFAULTS['style_profile_default']、无 opening 映射（参数字段）。
2. **application.py**：`PARAMETER_AMENDABLE` += `'style_profile'`（换档走快速路径不触发全量重写，与 style_guard 同理）。
3. **style.py**：`baseline()` 回落改 `contracts.profile_anchor((book.get('contract') or {}).get('style_profile'))`；origin 仍 `'default'`（既有测试语义不变），新增 `profile` 名。
4. **context.py**：
   - 新增生效档案解析函数（唯一实现）：PROJECT/style-profile.md 存在→`{'name':'custom','file':该路径}`，否则 catalog[contract.style_profile]。
   - `style_material` 增 `'profile'`/`'profile_file'` 两键，`source` 文案同步；L655 无锚回落改 `profile_anchor(...)`。
5. **delivery.py**：write/repair/redesign 的 guides 追加 `style.md` 与生效档案文件路径（若 envelope 组装处拿不到 contract，则以 style_material 的 profile_file 为唯一通道，guides 保持静态——实现时确认）。材料块路径是必达通道（read_ref.md 全文随包下发）。
6. **briefs.py**：NATURAL_PROSE_GUIDE 与 write brief 文风段措辞微调（"（或默认档案）"→指向材料 style.profile_file），不改结构。

## C. 测试

1. 新增（并入 test_style.py 或新 test_style_catalog.py）：catalog 完整性（file 存在/anchor 全键正数/默认名∈catalog）；baseline 逐档回落（三档锚值+profile 名+非法名回落）；validate_contract 填默认、非法 choices 拒；recontract --patch 换档快速路径生效不建 pending_contract；style_material 注入 profile/profile_file、PROJECT 文件存在时 name='custom'；write 阶段 guides 含 style.md 与所选档案。
2. `test_doc_single_source.py`：新增 style.md 目录表 ↔ STYLE_CATALOG 的（名,文件）一致断言。
3. 更新受影响断言：test_style.py:198-209、:444 的 `policy_default('style_default_anchor')` 改走 `profile_anchor`。
4. 回归：fast（228）+ full（638）全绿。

## D. 不动项

13 门协议与 voice 门 value 结构、style_window 容差体系、style_anchor 认可机制、examine/compare 判据、连续性核验——全部不动。既有项目无 `style_profile` 字段→validate_contract 填默认→行为与今天逐字节一致。工作区未提交的 watch --task 等改动原样保留，本方案叠加其上。

## 实施顺序

1. contracts 注册表与字段 → style/context 回落 → application 快路径 → delivery/briefs
2. 文档重构（迁移默认档案、style.md 枢纽化、四处文档同步）
3. 测试新增修正 → fast 全绿 → full 全绿