# opening/5 独立对抗复核（task-25）

复核对象：HEAD `455379b`（"开书协议升到 opening/5"），`contracts.VERSION = 2.0.0`、`OPENING_VERSION = 5`。
依据：`validation/opening5-spec.md`（冻结规格）+ 源码 + tests；**未读** `validation/opening5-verification.md` 的结论。
方法：只读仓库；一次性探针脚本放在系统临时目录 `%TEMP%\o5adv\probe.py`（不提交、不在仓库内），
通过真实入口驱动：`bootstrap.local_application.Application` 的 `advance/opening_choice/opening_tier/submit/audit/run`
与 `workflow.choose`→`workflow.apply`→`world.validate`/`drift.validate_volume_outline` 的同一条调用链。
未改动仓库任何文件（本次唯一写入文件是本报告）。

复现：

```
python %TEMP%\o5adv\probe.py            # 46 条探针；输出 PASS/FAIL 与每条的证据串
python %TEMP%\o5adv\probe.py 2.1 3.3    # 只跑名字里含这些片段的探针
```

另有 3 条独立跑过的仓库用例（见 §五）：`tests/test_opening_legacy.py`（v1 端到端 8 passed）、
`tests/test_world_grand.py tests/test_creation_bounds.py`（29 passed / 34 subtests）、
`tests/test_architecture.py -k defaults`（1 passed / 384 subtests）。

**总判定：46/46 探针通过，四条复核重点全部"绕不过"；发现 2 条低严重度缺陷 + 4 条残余缺口/规格未定义 + 1 条无影响的死代码。**
下面每条给「结论 + 最小输入 + 证据」。

---

## 一、① 在跑项目兼容性 —— 绕不过

**结论：v1–v4 门集与旧世界（10 域）在真实入口下全绿；新字段既不注入也不被形状检查反咬；显式空数组被拒是有意语义，不是兼容性回归。**

| # | 结论 | 最小输入 / 复现 | 证据 |
|---|---|---|---|
| 1.1 | v1–v5 门集与系统门声明未被改动 | 探针 1.1 | `creation.py:16-94`：`GATES_V1..V5`、`GATE_SETS[5]`、`SYSTEM_GATES` 五版齐全 |
| 1.2 | v4（11 门）真实全链：板面→世界→约定→激活→卷纲派工，`audit()` ok，页面渲染 44,400 字符 | 探针 1.2 | 驱动 `advance/opening_choice/submit`；`application.py:890-902` |
| 1.2b | v3（10 门）同样全绿 | 探针 1.2b | 同上 |
| 1.2c | v1/v2 门序与系统门未动（v1 端到端由仓库 legacy 用例覆盖） | 探针 1.2c + `pytest tests/test_opening_legacy.py -q` | `creation.py:16-49,89,94` |
| 1.3 | **旧世界（10 域、无 `powers`/`cosmology` 键）在 v4 choices 下通过 `world.validate`、`application.audit()` 与 `bookpage.render`** | 探针 1.3：把 `support._opening_model` 的两个新键删掉后 `repo.save`，再 `app.audit()` | `world.py:58-65`（t3–t5 = `LEGACY_SECTIONS`）、`world.py:94-97`、`world.py:181-191`（缺域规范化为 `[]`，只有被要求的域要实写） |
| 1.3b | 反向：v5 开书 + 10 域世界在 audit 被 `world_section` 拒（兼容规则按版本生效，不是"永远宽松"） | 探针 1.3b | `world.py:84-91`（`declared_sections` 把 `powers` 加进 required） |
| 1.4 | 手写契约缺 `world_tiers`/`world_ladder`/`world_scale`/`world_resource`/`core_premise`/`promise_anchor`：`planning.validate_contract` 通过，键不会被注入 | 探针 1.4 | `planning.py:157-169`：`default == []` 且 `blank is False` 且 `count>0` 时**跳过注入**，避免"注入空数组→下一行被自己的形状检查拒"；六个新字段都是 `optional: True`（`contracts.py:443-464`） |
| 1.5 | 显式 `world_tiers: []` / `world_ladder: []` 被 `contract` 拒（"缺键=没决定，空数组=声称有表却没有"） | 探针 1.5/1.6c：`planning.validate_contract({'world_ladder': [], ...})` | `contracts.py:647-651`（`blank:False,count:1`）+ `planning.py:170-171` |
| 1.6 | `exact` 行只允许声明的键：多一个键即拒 | 探针 1.6 | `contracts.py:652-658` |
| 1.6b | 手写契约**可以**带合法的 `world_tiers`/`world_ladder` 行（不强制来自开门） | 探针 1.6b | `contracts.py:453-464` |
| 1.7 | `alignment_for(1..4)` 不含六个新字段，`alignment_for(5)` 全含；`_v2_groups` 按 `since` 过滤，旧约定不会被追着要新字段 | 探针 1.7 | `contracts.py:564-571`、`creation.py:941-956`、`creation.py:968-981` |
| 2.14/2.15 | 手改库里的开书记录（改名 / 砍掉一条位阶）会在 `audit()` 被二次校验抓住（`world_alignment` / `opening_option`）——绑定与下限不是"只在提交那一刻成立" | 探针 2.14/2.15 | `application.py:897-902`（有开书记录时每次 audit 重跑 `world.validate` + `creation.validate_contract`），`creation.py:969-970` |

**为什么绕不过**：新字段全部 `optional + since 5`，且 `alignment_for`/`_v2_groups` 都以版本为闸；
`required_sections` 的档位基础域在 t3–t5 明确回退到 `LEGACY_SECTIONS`，新域只由 `declared_sections` 追加；
缺域在 `world.validate` 内被规范化成 `[]`，因此旧世界不会因为"少两个键"而失败。

---

## 二、② 三条逐字绑定 —— 绕不过（两条"合法但空洞"的边界见缺陷 F1）

绑定实现在 `world.py:117-159`，错误码统一 `world_alignment`，`details.mismatches` 给出条数。
下面每条都是"改一处再提交真实 world_model 回执"，看引擎是否拒。

| # | 攻击 | 结果 | 证据 |
|---|---|---|---|
| 2.1 | `world_tiers→powers`：只改一个字段（`gain`） | **拒**（mismatches=1） | `world.py:129-135`：五个字段 `all(match.get(f) == row.get(f))` 全比 |
| 2.2 | 删掉一条位阶记录 | **拒** | 同上（`match is None`） |
| 2.3 | 同名多条、第一条是错的（`next()` 取第一条） | **拒** | `world.py:129` 的 `next(...)` 只认首个同名记录 |
| 2.4 | 同名多条、第一条正确 | **过**（规格允许"世界比门里声明的更长/更多"） | `world.py:121-123` 注释与 `world.py:130` 的 `all(...)` 只约束声明的那几条 |
| 2.5 | `world_resource→economy`：缺同名 `resource` | **拒** | `world.py:136-144` |
| 2.6 | `allocator` 只出现在**另一条** economy 记录里 | **拒** | `world.py:139` 只取 `resource` 同名的那一条，再对**该条**文本做包含判断 |
| 2.7 | `allocator` 挪到**同一条**记录的另一个字段（`conflict`） | **过**——这是规格明文语义（"该条记录文本里出现"），不是漏洞 | `world.py:104-114` `_record_text` 汇总该记录所有字符串字段 |
| 2.8 | `world_ladder→世界`：`stage` 只出现在 `mysteries` | **拒** | `world.py:149-153`：只查 `geography/cosmology/factions/powers` 四域 |
| 2.9 | 名字差一个字 | **拒** | 同上（`==` 逐字） |
| 2.10 | 名字多一个尾空格 | **拒**（严格等值，不做 strip/大小写折叠） | 同上 |
| 2.11 | 尺度到"一界"的 rung 落在 `cosmology` | **过**（正例） | `world.py:89-90` 把 `cosmology` 加进 required；`world.py:149` 认 `cosmology` |
| 2.12 | `powers` 记录某字段留空 | **拒**，但更早：`world_record`（域记录字段非空先于绑定） | `world.py:192-193` |
| 2.13 | 世界被接受后再手改库里的 `powers`，`audit()` | **拒** `world_alignment` | `application.py:900` |
| 2.17 | 被拒的世界回执是否留下半成品 | **无副作用**：`contracts.dump(book)` 前后逐字相同，任务仍 pending | `application.py:submit` 的事务回滚 + 本探针断言 |

**为什么绕不过**：三条绑定都在 `world.validate` 内、在域形状与 id 唯一性之后执行，且读取的是
`creation.selected(opening)`（`world.py:125,136,145`），与合同对齐用的同一份 choices（`creation.py:941-956`）；
`_audit` 每次重跑同一条链，所以"提交时对得上、事后改库"也会被抓。

---

## 三、③ 卷 `stage` 单调性 —— 绕不过（跳级/重复按规格本就允许）

实现在 `drift.py:889-894`（逐卷"必须是已选阶梯的一级"）与 `drift.py:1064-1083`（跨卷"只升不降"）。

| # | 攻击 | 结果 | 证据 |
|---|---|---|---|
| 3.1 | `stage` 不在阶梯里 | **拒** `design_drift`（criterion=`volume_stage`） | `drift.py:891-894` |
| 3.2 | `stage` 空串 | **拒**（阶梯非空时 `'' not in rungs`） | 同上；`drift.py:1049` 的规范化在拒绝之后 |
| 3.3 | 后一卷回退到更小层级 | **拒** | `drift.py:1075-1083`（`rank` 来自阶梯数组顺序，按合同卷序遍历） |
| 3.4 | 跳级（第 1 卷 rung0 → 第 2 卷 rung3） | **过**——规格只要求"单调不减"（`opening5-spec.md` §6），实现与规格一致 | 探针 3.4 保存后的 `volumes_outline` |
| 3.5 | 重复（六卷同一级） | **过**——规格明文"一卷一级不强制" | 探针 3.5 |
| 3.6 | **滚动派工**：第一批只交 v1（`payload.volume_ids == ['v1']`，真实派工），已入库 `v1.stage=rung2`，第二批 v2 用 `rung0` | **拒** | `drift.py:1069-1074`：遍历**合同全部卷**，先取本批 `volumes`、再取 `existing`，所以跨批也连续比较。第二批用与 `workflow.apply` 相同的调用形状复现（`workflow.py:555-556`） |
| 3.7 | 老项目（v4，无阶梯）`stage` 留空 | **过**（行为与今天一致） | `drift.py:875`（`ladder` 为空则整段跳过）、`drift.py:1049` |
| 3.8 | **t1 合并档位**（`also=('chapter_outline',)`）下违反阶梯 | **拒**（合并不豁免） | `workflow.py:145,254-256`；`drift.py:891` 在合并回执里同样先跑 |
| 3.9 | 档位下限在门与世界两处同源 | t3 恰好 4 级位阶 + 4 级阶梯 | `creation.py:581,680,715` 与 `world.py:152` 都读 `DEFAULTS['world_ladder']` |
| 3.10 | 半成品 choices（`None`/错形状）不得抛异常 | 全部返回空集合 | `world.py:74-91`、`drift.py:826-836` |
| 3.11 | 一字层级名 | **过**（见 F1：无最小信息量下限） | `creation.py:721-725` 只要求 `text()` |

**为什么绕不过**：逐卷校验与跨卷校验是两段独立判据，前者保证"来自阶梯"，后者保证"不回退"；
跨卷那段以**合同卷序**为坐标而不是以本批提交顺序，所以滚动派工无法靠"只交后一卷"重置基线。

---

## 四、④ 数值默认与派生件

- **单点声明成立**：`contracts.DEFAULTS['world_ladder']` = `tier_min{t0:2,t1:3,t2:3,t3:4,t4:4,t5:4}` /
  `stage_min{t0:2,t1:2,t2:3,t3:4,t4:4,t5:4}` / `anchor_max_chapter:30`，与规格 §2 逐值一致（`contracts.py:73-77`）；
  `policy_default` 返回深拷贝，改副本不影响声明（`contracts.py:81-84`，探针 4.1）。
- **没有第二处硬编码**：脚本全仓扫描 `tier_min|stage_min|anchor_max_chapter|world_ladder` 的非 contracts.py 命中只有读取点
  ——`bookpage.py:46`、`creation.py:581/680/715/773`、`world.py:152`；`anchor` 相关行里没有裸 `30`（探针 4.2）。
  守卫测试 `tests/test_architecture.py -k defaults` 通过（1 passed / 384 subtests）。
- **派生件不存在**：`git ls-files` 无 `.svg/.png/.jpg`，无 `__pycache__` 入库（探针 4.3）；规格 §9.5 满足。
- **`envelope.py` 未新增 payload 键**：`volume_ids` 早已声明（`envelope.py:29`），本次提交的 diff 里也没有 envelope.py。

---

## 五、⑤ 文档与实现

- `references/opening.md:57` 13 门顺序 = `creation.GATES_V5`（`creation.py:74-88`）；`:71-81` 每门字段与
  `value_fields(gate, 5)` 一致；`:88-94` 的下限表（tier_min t0=2/t1=t2=3/t3–t5=4；stage_min t0=t1=2/t2=3/t3–t5=4；
  锚点 ≤ min(30, 档位章窗上限)）与 `contracts.py:73-77`、`creation.py:755-776` 逐值一致（探针 5.1 抽了 tier_min 行）。
- `references/world.md:11-13`（档位基础域、t3–t5 = 旧 10 域、`declared_sections` 追加）、`:27-28`（两个新域的字段）、
  `:51-67`（三条绑定与 `world.py:126-153` 逐条对应）、`:97`（卷 stage 逐字 + 只升不降）均与实现一致。
- `SKILL.md:4,13,21`、`README.md:106,114,125,218,367`、`references/protocol.md:9,18-23,31-33` 都写 13 门 / 12 领域 / 三条绑定；
  未发现仍在把 `engine`/`ending` 当现行门 id 的表述（探针 5.2），也未发现"11 门/10 领域"被当作现行协议的说法
  （历史版本一律写成"旧项目保留自己的门序"）。
- 结论：**未发现文档与实现对不上的声称**（唯一"未写"的是新字段无最小长度这一边界，见 F1，规格本身也没要求）。

---

## 六、新发现的缺陷 / 残余缺口

### F1（低）绑定判据没有最小信息量下限，"合法但空洞"的值即可满足
`creation._validate_world_structures` 只要求 `text()`（`creation.py:692-696`），`_bindings` 对 `allocator` 用**子串包含**
（`world.py:140`）。因此 `allocator = "人"` 能过门，且一条文本里恰好含"人"的 economy 记录即可满足绑定。

最小复现（探针 2.16）：在 `world` 门的选项里把 `value['resource']['allocator']` 改成 `"人"` → 世界回执的
`economy[0].distribution` 写成 `'有人负责分配。'` → 提交通过。
同类：`ladder.stage` 用一字名（`'甲'`）同样通过并被绑定（探针 3.11）。
建议（若 lead 认为值得收紧）：给 `resource.name/allocator`、`ladder.stage` 加最小长度（如 ≥2），或把 allocator 的判定
从"记录文本包含"收紧为"必须出现在 `distribution` 字段"。

### F2（低-中）`contract_errors` 对 `rows` 只校验条数与键集合，不校验行内文本；导入路径没有第二道
`contracts.py:647-659`：`blank:False,count:1` 只保证"至少一行"，`exact` 只保证键集合。
`planning.validate_contract` 因此接受 `world_tiers: [{'name':'','condition':'','gain':'','cost':'','limit':''}]`
（探针 1.6d）。对引导开书无影响（`creation.validate_contract` 会逐字比对，`creation.py:977-981`），
但 `opening --file` 导入的契约（`novel.py:322-323` → `application.recontract(..., opening=True)`，
该方法在 `application.py:853-856` 把 `creation` 清空）不会跑开书对齐，`_audit` 也只在"有开书记录"时才跑
`world.validate`（`application.py:898`），所以导入路径可以长期带着全空的结构行。
建议：`contract_errors` 对 `rows` 的 `shape` 行加"写了就必须非空文本"（与 `world.OPTIONAL_FIELDS` 同一口径）。

### F3（信息性）三条绑定只覆盖引导开书
绑定读的是 `creation.selected(opening)`；导入契约没有 choices，因此它的 `world_tiers/world_resource/world_ladder`
不参与任何绑定。实际影响为零：导入项目不会派 `world_model`（`workflow.py:238` 需要 `opening`），
所以没有世界模型可绑。属"覆盖范围"而非可绕过。

### F4（信息性）economy 同名多条时只认第一条
`world.py:139` 的 `next(...)` 取首个 `resource` 同名记录：第一条不含 allocator、第二条含 → 判失败（保守，非漏洞）；
反之第一条含即通过。世界记录的 `id` 唯一但 `resource` 名不唯一（`world.py:194-196` 只查 id），
同名两条属"世界比门里更长"的允许范围。

### F5（信息性，规格未定义）阶梯"同级次序"没有语义
`_validate_ladder` 只保证 `scope` 序号单调不减（`creation.py:736-738`），`drift` 用**数组下标**排序（`drift.py:1067`）。
两条 `scope` 相同的层级谁先谁后由数组顺序决定，规格没有声明这是否有意义（也不影响"只升不降"判定）。

### F6（信息性，规格问题）"跳级"与"重复"未被约束
探针 3.4/3.5 证明二者都通过。这与规格 §6"只升不降、一卷一级不强制"一致，不是实现绕过；
若产品意图是"每卷至少推进一级"或"同一级不得连续超过 N 卷"，需要在规格里补一条，实现再加一条判据。

### F7（无功能影响）`drift.py:1165` 一行死代码
`findings.extend(_deltas(row, [])[1] if isinstance(_deltas(row, []), tuple) else [])`：`_deltas` 返回 `list`，
该分支永不成立；实际形状 findings 由 `drift.py:1166-1168` 收集，行为正确。
来源是 v2 换代提交 `04508ae`（非 opening/5 引入），可顺手删除。

---

## 八、Lead 处置（2026-10-19 02:40，本报告结论之后的追记，非复核者结论）

复核对象是 `455379b`。以下处置记在 hardening 提交里（`world.py`/`creation.py`/`contracts.py`/`drift.py` + 用例）：

| 发现 | 处置 | 落地 |
|---|---|---|
| F1 绑定无最小信息量 | **已修**：门侧 `world.tiers[].name`、`resource` 三键、`ladder[].stage` 各要求 ≥2 字符；世界侧 `allocator` 的判定从"记录任意文本包含"收紧为"必须出现在该记录的 `distribution` 字段"。回归用例：`test_opening`（一字位阶名/一字分配者/一字层级名被拒）、`test_world_grand`（分配者只写在 `conflict` 里仍被拒） | `creation.py::_validate_world_structures/_validate_ladder`、`world.py::_bindings` |
| F2 `contract_errors` 不校验行内文本 | **已修**：`exact` 行字段要求每条记录键集合恰好等于 shape，且每项都要写实（非空文本）。回归用例：`test_creation_bounds` 的空行被拒 | `contracts.py::contract_errors` |
| F7 `drift.py` 死代码 | **已删**（`_deltas` 返回 list，该分支永不成立；`shape` 行本就收集 findings） | `drift.py::validate_chapter_outline` |
| F2 的连带语义 | 为兼容在跑项目，可选 rows 字段的**空数组**明确为"未声明"（与缺席同义）：形状层放行，v5 的必填性由 `creation.validate_contract` 的对齐检查保证；模板对可选 rows 字段给空数组而不是空行 | `contracts.py::contract_errors/_placeholder` |
| F3/F4/F5/F6 | **接受现状，不改**：F3 覆盖范围（导入项目没有 world 派工，无可绑对象）；F4 economy 同名多条取首条属保守；F5 同级次序无产品含义；F6 跳级/重复是本轮规格明文的"只升不降、一卷一级不强制"，若将来要"每卷至少推进一级"需先改规格 | `validation/opening5-spec.md` §6 |

hardening 后的复跑：`python -m pytest -q` → **528 passed / 12 skipped / 1291 subtests / 0 failed**；
`python -m pyflakes scripts tests validation` → rc=0；`python validation/e2e_guided.py` → rc=0（13 门、12 次派工、`problems: []`）。

---

## 九、复核者的未覆盖与存疑（原第七节，保持原样）

- v1/v2 未做端到端驱动：`tests/support.py` 的开门夹具只覆盖 v3+ 的门名（v2 的 `engine`/`ending` 门没有夹具值，
  `support.opening_options` 会以 `opening_gate` 拒绝）。v1 由仓库 `tests/test_opening_legacy.py`（8 passed）覆盖，
  v2 只做了声明级核对（探针 1.2c）。**建议 lead 若要更强的兼容证据，补一个 v2 端到端用例。**
- 未跑全量 `pytest`/`pyflakes`（实现者已跑；我跑的是 3 个相关文件，均绿）。
- 未做并发/多控制器争用、未做存储层篡改（除 §一 的 2.14/2.15 两次开书记录手改），未测 `recontract` 路径下的
  `world_tiers` 改约（`application.py:874-877` 只在 `world and creation` 时校验）。
- 未评估判据的**文学/产品**合理性（例如 `anchor_max_chapter=30` 对 t5 的 489–666 章书是否过紧），
  本次只回答"实现是否按冻结规格机械成立"。
