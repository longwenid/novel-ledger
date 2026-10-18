# opening/5 规格（冻结）：脑洞更大、世界更宏大

状态：**冻结**。实现与测试都以此文件为准；实现中若发现规格自相矛盾，回报 lead，不要各自改口径。
依据：`validation/research-brainstorm-trends.md`（起点/番茄脑洞与格局证据）、
`validation/research-worldbuilding-trends.md`（世界观骨架证据）。两条硬约束来自作者：
① 设计前期解决漂移（门选完的东西必须在世界模型里落地并可机械核对）；
② 不做任何独立审查环节（质量靠文风规格 + 机械代理指标，已在 v2.1 落地）。

## 0. 一句话目标

把开书门从「11 门问故事」重构成「13 门问设定」：新增 **核心脑洞门**（世界比同类多了什么规则、
第一推动力、主角与体系的关系、世界暗面来源）与 **格局升格门**（开局尺度、升格层级表、跨卷不变的上层结构），
世界门从「一句话前提 + 机制」升级为结构化交付（**位阶阶梯 + 硬通货 + 分配者**），
世界模型从 10 个平铺领域扩展到 **12 个领域**（新增 `powers` 力量/位阶阶梯、`cosmology` 空间与位面）
并为旧领域加可选深字段（纪元史承接、对立空间、跨卷仍在场、披露排期），
且门里选的位阶/硬通货/格局阶梯必须在世界模型里有**同名记录**（逐字绑定，机械核对）。

## 1. 版本与门集

`contracts.OPENING_VERSION = 5`；`creation.GATE_SETS[5] = GATES_V5`；`creation.SYSTEM_GATES[5] = ('scale',)`。
v1–v4 门集与各自 VALUE_RULES/GATE_NOTES 一律保留（在跑项目按自己的门集继续）。

```python
GATES_V5 = (
    ('genre',         '题材、频道与读者承诺'),
    ('premise',       '核心脑洞与第一推动力'),
    ('origin',        '主角来历：魂穿、身穿、本土或其他'),
    ('voice',         '叙述人称与语感'),
    ('scale',         '体量与分卷'),                     # SYSTEM 门，引擎按档位表给
    ('world',         '世界结构：位阶、硬通货、机制与禁区'),
    ('ladder',        '格局尺度与升格阶梯'),
    ('edge',          '核心优势与成长线'),
    ('protagonist',   '主角身份、处境与底线'),
    ('relationships', '核心关系与情感线'),
    ('opposition',    '主要对抗与冲突梯度'),
    ('payoff',        '爽点兑现、主题锚点与终局'),
    ('title',         '书名'),
)
```

顺序理由：脑洞决定后面所有门读什么（premise 紧跟 genre）；来历（origin）决定主角带什么；
世界结构（world）先于格局（ladder），格局阶梯要踩在世界已有的位阶/地域/势力上；
edge/protagonist/relationships/opposition/payoff/title 保持 v3/v4 的相对次序。
`OPENING_DIRECTION_GATES` 必须正好覆盖这 13 个门 id（守卫测试要求一一对应）。

## 2. 枚举与共享数字（单一来源：`contracts.py`）

```python
WORLD_SCOPES    = ('局部', '一城', '一域', '一界', '星海', '诸天')   # 格局阶梯每级的空间尺度
WORLD_GROWTHS   = ('地盘', '势力', '规则', '认知', '文明')            # 这一级变大的是什么
WORLD_TERMINALS = ('局部', '势力', '体系', '文明')                    # 终局面对的等级
STANCES         = ('顺从', '利用', '对抗')                            # 主角与规则体系的关系
DARK_SIDES      = ('外神', '天灾', '系统', '上层剥削', '制度', '人心')  # 世界暗面来源
COSMOLOGY_SCOPES = ('一界', '星海', '诸天')                           # 到这些尺度，cosmology 必填
SETTING_CLICHES = ('序列', '途径', '克苏鲁', '克系', '系统', '幕后黑手', '第四天灾',
                   '诸天', '无限流', '模拟器', '签到', '存档重开')     # 同质化提示词（仅提示，不拦）
```

`DEFAULTS['world_ladder']`（新增，唯一来源）：

```python
'world_ladder': {
    'tier_min':  {'t0': 2, 't1': 3, 't2': 3, 't3': 4, 't4': 4, 't5': 4},   # world 门位阶条数下限
    'stage_min': {'t0': 2, 't1': 2, 't2': 3, 't3': 4, 't4': 4, 't5': 4},   # ladder 门层级条数下限
    'anchor_max_chapter': 30,                                              # 主题锚点最迟兑现章（≈番茄十万字首秀）
},
```

## 3. 新增/变更的约定字段（`CONTRACT_FIELDS`，全部 `since: 5, optional: True`）

| key | kind | shape | opening 来源 | 说明 |
|---|---|---|---|---|
| `core_premise` | map | `('novelty','first_cause','stance','dark_side')` | `('premise', None)` | 核心脑洞四问 |
| `world_scale` | map | `('opening','terminal','unchanged')` | `('ladder','scale')` | 开局可见边界、终局等级、跨卷不变的上层结构 |
| `world_ladder` | rows（`blank: False, count: 1`） | 行 `('stage','scope','growth','new_rule','cost')` | `('ladder','ladder')` | 升格层级表 |
| `world_tiers` | rows（`blank: False, count: 1`） | 行 `('name','condition','gain','cost','limit')` | `('world','tiers')` | 读者看得见的位阶阶梯 |
| `world_resource` | map | `('name','source','allocator')` | `('world','resource')` | 硬通货：名称、来源、分配者 |
| `promise_anchor` | map | `('deliverable','deadline_chapter')` | `('payoff','anchor')` | 主题锚点：第 N 章前必须兑现什么 |

不改任何既有字段的 shape（改 shape 会让在跑项目的约定在校验时被拒）。
`world_premise`/`world_rules`/`red_lines`/`volumes`/`entities` 仍是派生字段，`DERIVATION_INPUTS['world']` 不变。
`alignment_for(5)` 因而包含 v1–v4 全部对齐字段 + 上表 6 个；`_v2_groups` 自动从门投影，无需手写。

## 4. 各门 value 形状与校验（`creation._validate_value_modern(..., version=5)`）

`_validate_value_modern` 现在按 `version in (3,4,5)` 走同一实现，v5 分支新增以下检查。

### 4.1 `premise`（value = core_premise 的四个键）

- 四键皆非空文本；`novelty` 与 `first_cause` 各 ≥ 12 字符。
- `stance ∈ STANCES`，`dark_side ∈ DARK_SIDES`（枚举，不接受同义词）。
- 四键都不得含 `待补 / 暂定 / 略 / 同上`。
- 板面告警（不拦）：`creation.premise_warnings(gate, options)`——`novelty`+`first_cause` 命中
  `contracts.SETTING_CLICHES` 时给 `{'code': 'premise_public_setting', ...}`，提示「这条组合已被头部占位，
  novelty 必须写清你新增的规则/资源」。与 `name_warnings` 同构，挂到 `board['premise_warnings']`。

### 4.2 `world`（world_premise / mechanism / red_lines / allow_special_mechanism / **tiers** / **resource**）

- 既有 world 校验全部保留（premise、mechanism 三件套、red_lines 数组、allow_special_mechanism 一致）。
- `tiers`：数组，每条恰好 `('name','condition','gain','cost','limit')` 五键且皆非空文本，`name` 不重复且 ≥2 字符；
  条数 ≥ `DEFAULTS['world_ladder']['tier_min'][tier]`（tier 取 `choices['scale']['tier']`）。
- `resource`：恰好 `('name','source','allocator')` 三键，皆非空文本且各 ≥2 字符（一字名会被记录文本偶然命中，
  绑定就不再是证据）。

### 4.3 `ladder`（value = `{'scale': {...}, 'ladder': [...]}`）

- `scale.opening` ≥ 8 字符（第一章读者能看见的边界）；`scale.unchanged` ≥ 8 字符（跨卷不变的上层结构）；
  `scale.terminal ∈ WORLD_TERMINALS`。
- `ladder` 每条恰好 `('stage','scope','growth','new_rule','cost')` 五键，皆非空文本；`stage` 不重复且 ≥2 字符；
  `stage` 写成**世界里能落成一条记录的名字**（地点/位面/势力/位阶名），不要写「第一卷」这类编号。
- 条数 ≥ `DEFAULTS['world_ladder']['stage_min'][tier]`。
- `scope ∈ WORLD_SCOPES`，且按 `WORLD_SCOPES` 序号**单调不减**。
- `growth ∈ WORLD_GROWTHS`；条数 ≥ 3 时至少一条 `growth ∈ ('规则','认知','文明')`（防「只换地图」）。
- `terminal` 与层级表一致：`文明`→存在 `growth=='文明'`；`体系`→存在 `'规则'`；`势力`→存在 `'势力'`；
  `局部`→仅允许 `tier in ('t0','t1')`。

### 4.4 `payoff`（plan / ending / theme / **anchor**）

- 既有 plan/ending/theme 校验保留。
- `anchor.deliverable` ≥ 12 字符；`anchor.deadline_chapter` 为纯数字字符串，
  `1 ≤ int ≤ min(DEFAULTS['world_ladder']['anchor_max_chapter'], tier['chapter_window'][1])`。

### 4.5 其余门

`genre/origin/voice/scale/edge/protagonist/relationships/opposition/title` 校验与 v4 相同；
`edge`、`world`、`opposition`、`payoff`、`premise`、`ladder` 的 `GATE_NOTES[5]` 与
`OPENING_DIRECTION_GATES` 文案按新语义重写（见 §7 必写要点）。

## 5. 世界模型（`world.py`）

### 5.1 领域（`SECTIONS` 末尾追加两个，保持既有 10 个的字段逐字不变）

```python
'powers':    ('name', 'condition', 'gain', 'cost', 'limit'),   # 力量/位阶阶梯，与 world 门 tiers 逐字对应
'cosmology': ('name', 'inhabitant', 'law', 'entry'),           # 空间与位面：层名、谁在、什么法则、怎么进
```

`LABELS` 追加 `'powers': '力量与位阶阶梯'`、`'cosmology': '空间与位面'`。
`LEGACY_SECTIONS = ('geography','history','rules','factions','economy','society','everyday',
'characters','mysteries','mechanisms')`；`GRAND_SECTIONS = ('powers','cosmology')`。
`TIER_SECTIONS` 的 t3/t4/t5 改为 `LEGACY_SECTIONS`（**不再用 ALL_SECTIONS**：在跑项目的世界没有新领域，
用 ALL_SECTIONS 会让它们的 `_audit` 直接失败）。

### 5.2 可选深字段（`OPTIONAL_FIELDS`，只校验「写了就必须非空文本」，不要求写）

```python
OPTIONAL_FIELDS = {
    'history':    ('epoch', 'carryover'),        # 纪元名/分期；上一纪元如何延续到当下
    'geography':  ('scale', 'counter_space'),    # 尺度（城/域/界…）；对立空间（入侵面/里世界）
    'factions':   ('survives_scale_up',),        # 跨卷仍在场的原因（防上一卷势力作废）
    'mysteries':  ('reveal_window', 'survival'), # 披露排期；真相揭开之后的生存问题
}
```

### 5.3 `required_sections(tier_id=None, choices=None)`

```python
def declared_sections(choices):        # 门里声明了什么，世界模型就必须多填什么
    extra = []
    if ((choices or {}).get('world') or {}).get('tiers'): extra.append('powers')
    scopes = {row.get('scope') for row in ((choices or {}).get('ladder') or {}).get('ladder') or []
              if isinstance(row, dict)}
    if scopes & set(COSMOLOGY_SCOPES): extra.append('cosmology')
    return tuple(extra)
```

`required_sections` = 档位基础域 ∪ `declared_sections(choices)`，按 `SECTIONS` 顺序去重。
旧开书（v1–v4）没有这些 choice → 结果与今天完全一致。

### 5.4 `validate(data, choices, selection_hash, sections=None)` 变更

1. **缺领域不再直接报错**：`data` 里缺的领域规范化为 `[]`（在返回的深拷贝里补上）；
   只有 **本档位/本次声明要求** 的领域才要求「至少一条实写记录」（`mechanisms` 的既有例外保留）。
   这样在跑项目的世界（没有 `powers`/`cosmology` 键）仍能通过 `_audit` 的一致性复检。
2. 新增三条**逐字绑定**（`choices` 声明了才检查，错误码沿用 `world_alignment`，details 里写清 rule/expect/got）：
   - `world_tiers`：每条声明的位阶，`powers` 里必须有一条记录 `name/condition/gain/cost/limit` 与它**逐字相同**；
     额外的高阶记录允许（世界可比门里声明的更长）。
   - `world_resource`：`economy` 里必须有一条 `resource` 与声明 `name` 逐字相同，且该条记录的 `distribution`
     字段文本里出现声明的 `allocator`（分配者必须写在分配方式里；在别的字段出现不算，避免偶然命中）。
   - `world_ladder`：每条 `stage` 必须在 `geography`/`cosmology`/`factions`/`powers` 里有一条 `name` **逐字相同**的记录。
3. 既有校验（premise 逐字、主角逐字、机制 mode、id/links 唯一性、`set(data) <= ...`）全部保留。

## 6. 卷纲：格局阶梯落到卷上（`drift.py` + `planning.py`）

- `drift.VOLUME_FIELDS` 增加 `'stage'`（放在 `'purpose'` 之后）；`result_templates.volume_row` 同步加 `'stage': ''`。
- `drift.validate_volume_outline(..., selected=...)`：当 `selected['ladder']['ladder']` 非空（v5 项目）时，
  本次派发的每一卷 `stage` 必须**逐字等于**某一级的 `stage`，且按合同卷序**只升不降**（层级序号单调不减）。
  一卷一级**不**强制：卷数通常多于阶梯级数（t3 是 6 卷一 4 级），同一级可以被连续几卷沿用。
  旧开书没有 ladder choice → `stage` 允许为空，行为与今天一致。
- `planning.validate_volume_outline` 已把 `selected` 透传，无需改动。
- `promise_anchor` 与 `world_scale.unchanged` 本轮**只做声明**（卷纲/章纲简报里点名必须承接），不加机械校验。

## 7. 简报与材料（`briefs.py` / `context.py` / `result_templates.py` / `bookpage.py`）

- `briefs.WORLD_PIECES` 按证据里的 7 层骨架重写，覆盖 12 个领域（含 `powers`/`cosmology`）与可选深字段，
  并写清三条绑定：「门里选的位阶表要逐字进 `powers`」「硬通货进 `economy` 且分配者写进分配方式」
  「格局阶梯每一级在本世界有一条同名记录」；尺度到「一界/星海/诸天」时 `cosmology` 必填。
- `briefs.world_model` 的 `sections` 参数改为按 `world.required_sections(tier, choices)` 传入（`context._brief` 同步）。
- `briefs.stage('volume_outline')` 增加 `stage` 的交付要求（取已选阶梯里的一级、逐卷只升不降）。
- `briefs.direction_block(...)` 调用的门 id 更新为 v5 存在的门（不要再引用 `engine`/`ending`）。
- `context._selection_line` 增加新键（`novelty/first_cause/stance/dark_side/opening/terminal/unchanged`，
  以及 `scale`/`resource`/`anchor` 这类嵌套 map 的按键展开），让后面的门看得到已选的脑洞与格局。
- `bookpage`：`FIELD_LABELS` 补 6 个新约定字段；`SUB_LABELS` 补新子键（novelty/first_cause/stance/dark_side/
  opening/terminal/unchanged/stage/scope/growth/new_rule/condition/gain/allocator/deliverable/deadline_chapter/
  epoch/carryover/counter_space/survives_scale_up/reveal_window/survival/layer/inhabitant/law/entry）；
  世界记录标题的回退链加入 `layer`（`cosmology` 记录没有 `name` 时也不该显示成领域名——本轮 `cosmology` 有 `name`，
  但保留回退更稳）。
- `result_templates`：世界模板随 `SECTIONS` 自动多两域；`volume_row` 加 `stage`。
- `envelope.py` 不新增 payload 键，应无改动。

## 8. 已验证的兼容性要求（必须成立）

- 在跑项目：v1–v4 门集照旧；旧世界（10 域、无 `powers`/`cosmology`）在 `_audit` 复检里通过。
- 旧约定：`CONTRACT_FIELDS` 既有行一个字都不改（shape/默认值/since）。
- `world.validate` 只在 `choices` 声明了新东西时才要求新领域与新绑定。
- 数值默认只在 `contracts.DEFAULTS` 声明一次（含新增 `world_ladder`）；其他模块只读不写死。
- 架构表不加新模块、不加新跨层边。

## 9. 验收标准

1. `python -m pytest -q` 全绿（含子测试），`python -m pyflakes scripts tests validation` 无输出。
2. 新增用例至少覆盖：13 门全走通的 guided opening；`premise` 枚举/长度/告警；
   `world.tiers` 条数下限与字段；`ladder` 单调性、防换地图、terminal 一致性、锚点上限；
   世界模型三条绑定各自的失败路径（缺同名位阶/缺硬通货/阶梯无同名记录）；
   旧世界（10 域）在 v4 choices 下仍通过；卷纲 `stage` 违反单调被拒。
3. `validation/e2e_guided.py` 等既有 harness 在 13 门下跑通；`validation/opening5-verification.md` 出结论。
4. `references/opening.md`、`references/world.md`、`SKILL.md`、`README.md` 与实现一致（13 门、12 领域、三条绑定）。
5. 派生件不提交（渲染出的 svg 等）；提交信息用中文说明本次重构。
