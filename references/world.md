# 丰富世界模型

何时读：逐门选择结束后的 world_model、世界补读和约定整理。

## 适用范围与来源

逐门选择结束后自动进入世界创建。设计者读取 opening_choices/opening_basis，绑定 selection_hash，不再要求作者填百科表。所选前提、主角、机制范围和禁区是约束；世界如何承载持续行动、冲突与后果由设计者展开。

## 创建内容

模型包含 premise/story_capacity/selection_hash 和完整记录数组。领域及记录字段以 `world.SECTIONS` 和当前任务模板为准；**必填集合由 `world.required_sections(tier, choices)` 合并档位基础域与门中声明后决定（微型档的基础域是规则、社会、日常、人物、隐秘与机制），最终列表之外的领域保留为空数组，不要为凑数写进来**——世界被之后每一次派工读取，它的规模是持续成本而不是一次性成本。

**v5 起还要叠加门里声明的要求**：`world.required_sections(tier, choices)` = 档位基础域 ∪ `world.declared_sections(choices)`——`world` 门声明了 `resource` 就把 `economy` 加进来（包括原本不要求该域的 t0/t1/t2），声明了 `tiers` 就把 `powers` 加进来，`ladder` 里有 `一界`/`星海`/`诸天` 级别的 `scope` 就把 `cosmology` 加进来。简报与提交校验共用这个集合，已声明的硬通货不会再被要求留空。**t3–t5 的档位基础域是 `LEGACY_SECTIONS`（原有 10 域），不含新增两域**：在跑项目的世界没有 `powers`/`cosmology` 键，拿全领域表去要求会让它们的一致性复检直接失败；新领域只在门里声明时才要求。v6 声明 `architecture` 时，还要求 geography/history/factions/rules/mysteries 承接五项架构；不强制增加宇宙位面。mechanisms 按所选机制方向为空或实写。

| 领域 | 说明 |
|---|---|
| geography | 地域聚落、环境资源、通行条件与情节压力 |
| history | 关键历史、后果与当下利益 |
| rules | 原理、适用范围、限制与违反后果 |
| factions | 组织诉求、力量来源、依赖和冲突 |
| economy | 资源生产、分配、稀缺与争夺 |
| society | 制度、习惯、执行方式和普通人处境 |
| everyday | 职业、日常行为与可用于场景的约束 |
| characters | 主角和关键人物、欲望底线、知情边界与关系 |
| mysteries | 隐秘利益或真相、披露安排和因果作用，不强迫超自然 |
| mechanisms | 原理、代价、限制与失效；已选无机制时为空 |
| powers | **力量与位阶阶梯**：记录字段 `name`/`condition`/`gain`/`cost`/`limit`，与 `world` 门声明的 `tiers` 逐字对应 |
| cosmology | **空间与位面**：记录字段 `name`/`inhabitant`/`law`/`entry`——层名、谁在、什么法则、怎么进 |

### 可选深字段

`world.OPTIONAL_FIELDS` 给旧领域加了可选深字段（**写了就必须非空文本，不要求写**）：

| 领域 | 可选深字段 |
|---|---|
| history | `epoch`（纪元名/分期）、`carryover`（上一纪元如何延续到当下） |
| geography | `scale`（城/域/界…的尺度）、`counter_space`（对立空间：入侵面/里世界） |
| factions | `survives_scale_up`（跨卷仍在场的原因，防上一卷势力作废） |
| mysteries | `reveal_window`（披露排期）、`survival`（真相揭开之后的生存问题） |

每条有稳定 id 与 links=[领域:id]，引用须存在。文字为完整具体说明，不用“待补”“同上”。保留所选主角欲望底线，不能把无机制改成外挂，也不得越过世界门所选禁区。丰富度来自因果、利益和场景承载，条目数量不证明丰富。

地域影响通行和资源，历史影响制度与势力，日常能进入人物行动；避免孤立百科和统一动机。体量决定展开尺度，世界可丰富，远期章纲继续滚动。

## 世界要产出哪些网文可用件

世界门按网文设定生成的口径出案（方法见 [创意工具箱](hatch.md#设定生成方法)），落到模型里就是下面这几件**能被后续卷纲/章纲花掉**的东西：

| 世界模型里的东西 | 至少产出 | 与门的对应 |
|---|---|---|
| `powers` | 读者看得见的**位阶阶梯**：级别名、升级条件、拿到什么、卡在哪、上限 | `world` 门的 `tiers` 每条在这里有同名记录（逐字） |
| `economy` | 一种**硬通货**：名称、来源、谁在分配（灵石/贡献点/积分/信用/丹药一类可记账资源） | `world` 门的 `resource` 在这里有同名记录，且 `distribution` 里出现声明的 `allocator` |
| `factions` | 有自身目标、资源依赖与冲突的组织，能形成不同的生存或治理方案 | 可承接 `ladder` 的 `stage`（跨卷仍在场用 `survives_scale_up` 说明） |
| `mechanisms` | 有特殊机制时：代价、上限与**供料链**（升级材料从哪来、谁在抢、世界怎么持续产出） | 与 `edge` 门声明的优势供料链一致 |
| `geography` / `cosmology` | 说明**空间边界与联系**：各方居所、通行条件、以及到 `一界`/`星海`/`诸天` 尺度时的位面（层名、谁在、什么法则、怎么进） | `ladder` 的每级 `stage` 在这里有同名记录（逐字） |

这几件是**给后续设计用的**，不是氛围描写：位阶的当前级别进 `characters`/`knowledge` 的状态（章纲的 `characters`/`knowledge` 增量按它写）；硬通货进资源增量账（章纲 `resources` 的 key 必须能在世界或既有状态里找到）；地图进 `places`——章纲的 `places` 增量会进位置漂移校验，跳到未登记地点直接拒绝。开篇用具体危机与行动展示必要规则，背景随卷纲的揭示安排展开。

## 三条逐字绑定

门里选完不是结束：`world`/`ladder` 门声明的东西必须在世界模型里有**同名记录**，提交时机械核对（错误码沿用 `world_alignment`，details 写清 rule/expect/got）。只在 `choices` 声明了才检查，旧开书（v1–v4）行为不变：

| 门里声明 | 世界模型里必须有 |
|---|---|
| `world_tiers` 的每条位阶 | `powers` 里有一条 `name`/`condition`/`gain`/`cost`/`limit` 与它**逐字相同**的记录；额外的高阶记录允许（世界可以比门里声明的更长） |
| `world_resource`（`name`/`source`/`allocator`） | `economy` 里有一条记录，其 `resource` 与声明的 `name` 逐字相同，且该条记录的 `distribution` 字段文本里出现声明的 `allocator`（分配者必须写在分配方式里；在别的字段出现不算） |
| `world_ladder` 的每级 `stage` | `geography`/`cosmology`/`factions`/`powers` 里有一条 `name` 与它**逐字相同**的记录 |

另外，`data` 里缺的领域会先规范化为 `[]`（在返回的深拷贝里补上），只有**本档位或本次声明要求**的领域才要求至少一条实写记录（`mechanisms` 的既有例外保留）——所以在跑项目（10 域、没有新键）仍能通过一致性复检。

## 世界架构绑定

`opening/6` 的 `world.architecture` 原样保存为约定 `world_architecture`。模型必须在下面每个指定字段里，用至少一条记录逐字保留对应声明；其他字段展开细节，links 表达关系。仅在别的字段提到、改写成摘要或重新发明背景，都不算承接。

| architecture 键 | 意义 | 世界记录字段 |
|---|---|---|
| space | 世界全貌、文明分布与通行边界 | `geography.environment` |
| history | 历史断层对当下的影响 | `history.present_effect` |
| civilizations | 多方生存方式、依存与冲突 | `factions.conflicts` |
| conflict | 持续恶化的贯穿矛盾 | `rules.consequences` |
| mystery | 终极真相与揭开后仍需解决的问题 | `mysteries.truth` |

声明与绑定目标共用 `contracts.WORLD_ARCHITECTURE`；旧项目未声明时不追溯补填。存进 `truth` 的作者设定不自动成为人物知识，披露须经卷纲窗口与章纲知情链安排。

## 机械校验与采纳

world_model 候选不更新正文事实。提交时由引擎机械校验字段形状、links 引用是否存在、领域是否落在本档位与本次声明的要求内、记录 id 是否唯一、世界与所选前提/机制范围/禁区是否一致，以及上面的位阶、资源、格局及世界架构绑定。通过即在同一事务采纳；失败保持原任务并返回具体错误，修正后重交，不消耗正文返修额度。

机械校验只证明字段、引用和声明一致。当前设计者须在世界、卷纲与章纲任务内推演因果、长期冲突和揭示顺序，卷纲的 `exit_state` 与章纲状态链检查可计算的资源和状态条件；不新增独立校验子 agent，也不把机械通过当作文学质量证明。

隐秘真相与未来意图不直接变为人物知情或已发生事件。

## 约定与交付

默认 world_model 在同一任务中起草世界和完整约定；检查 task.stages、payload.also 与模板，按要求把约定放入 data.contract。世界与候选约定由引擎按同一套机械校验在提交时判定（约定字段、与各门选择逐字一致、world_rules 与候选世界逐字一致、所有已声明的绑定成立），通过后原子激活。单独的 opening_contract 任务沿自己的冻结材料执行，开书交接见 [系统执行](opening.md#系统执行)。

| 交付对象 | 来源与时机 |
|---|---|
| book.html | 世界与约定机械校验通过后合并完整设定、已选方向，卷纲推进后继续更新。world_view.html_path 指向该统一页面。 |
| world.json | 导出已采纳的完整世界；与页面一并提供绝对路径，失败后由 advance 重建视图。 |
| 卷纲范围 | 按 outline_ready 的实际覆盖说明：默认 scope=all 一次交全部卷，rolling 进卷前交该卷；卷纲与章纲为必选阶段。见 [叙事推进](narrative.md#卷纲)。 |

世界关联图只使用显式 links，历史时间线按模型记录顺序展示，不从描述推断关系或时期。

## 卷纲与章纲从这里取什么

书级规划读完整世界；世界模型是后续所有漂移字段的引用底账，**引用不存在的 key/entity 会在章纲提交时被拒绝**。

| 下游字段 | 取自世界模型的哪里 |
|---|---|
| `volume_outline.stage` | 已选格局阶梯里的一级，逐字等于 `geography`/`cosmology`/`factions`/`powers` 里某条记录的 `name`；按卷序只升不降 |
| `volume_outline.resources[].key` | 世界的 economy/everyday 资源条目 id |
| `volume_outline.places[].from/to`、`chapter_outline.places[]` | geography 的地点 id（位置跳变到未登记地点即拒绝） |
| `volume_outline.characters[].entity`、`chapter_outline.characters[].entity` | characters 记录 id，以及既有状态里的人物 |
| `volume_outline.knowledge[].who/topic`、`chapter_outline.knowledge[]` | characters 的人物 id 与 mysteries/factions 等提供的话题 |
| `chapter_outline.world_refs` | `[领域:id]`，领域名取本页表头（含 `powers`/`cosmology`），id 必须在模型中存在 |
| `chapter_outline.new_entities` | 首次登场的新人物/地点/物品内联档案；落地后成为新的既有状态，后续按 id 引用 |

执笔阶段交付当前人物、引用记录及直接关联；隐秘真相保留在可选 world_author_records，并用 disclosure_boundary 明确本章披露许可。原 world_model 完整保留，沿关联补读，不递归展开整个世界。未选记录不代表语义无关，不截断记录或把秘密直接写成角色对白。

世界到卷纲、章纲的接口与状态链见 [叙事推进](narrative.md)；执笔与自比的判断依据见 [创作与自比](craft.md)；交付失败的恢复入口见 [运行](runtime.md)。
