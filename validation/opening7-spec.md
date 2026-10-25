# opening/7 规格：门序重排与逐门规格前移

当轮状态：**现行**。本文件记录 opening/7（`contracts.OPENING_VERSION = 7`）的门序理由、逐门 value 规格变化、
平台指引验收口径与字面版本号清理清单。字段归属（`CONTRACT_FIELDS.opening`）、`validate_value` 的接受集、
`DERIVATION_INPUTS` 与档位表数字全部不变——本轮只改门序与作者/写手读到的规格文本；归档后以
[任务协议](../references/protocol.md) 与 [逐门开书](../references/opening.md) 为准。

## 1. 版本与门序

`contracts.OPENING_VERSION = 7`；`creation.SYSTEM_GATES = {7: ('scale',)}`（键由 OPENING_VERSION 派生）。
门集不变（13 门、门名不变），仅顺序重排：

```
genre, premise, scale, world, ladder, voice, origin, edge, protagonist,
opposition, relationships, payoff, title
```

相对 opening/6 的三处移动及其理由（勘察依据：门序勘察 gateDependencies/orderProblems，逐条引代码行）：

- **voice 3→6（核心移位）**：voice 仅自校验、无跨门机械读（creation.py `_validate` 各门分支），却是落约后
  最硬的逐字约束（契约对齐逐字、章纲 pov 必须与契约一致）。旧序在仅知 genre+premise 时定死 pov，若
  world cosmology 或 ladder 星海/诸天尺度暗示跨位面叙述，唯一纠正路径是 back 作废 11 门。移到 world+ladder
  之后，pov 决策见到宇宙观与格局终局，错配场景消除，back(voice) 半径 11→8。写作纪律职责已由 style_profile
  参数承担（contracts.py 参数字段、recontract --patch 直改），voice 晚定不损失纪律层。
- **scale 4→3**：机械上必须先于 world/ladder/payoff（世界推导硬读 scale.tier）。voice 后移后，scale 落到
  world 前最后一个合法位，「体量承诺」决策点推到机制允许的最晚，且与 world 紧邻。如实声明：此移位是
  voice 后移的副产品，不解决「档位板不携带前门语境、tier 不可参数化修订」的机制面根因（硬约束禁改）。
- **opposition 11↔relationships 10（对调）**：旧序要求 relationships 先「写清助力与背叛风险」而后才有对手
  网络可依附，两门均无机械互检——勘察判定旧序「强迫前一门在信息不足处落笔，或后一门回头迁就已定关系」。
  对调后信息方向修正：opposition 先定，其利益网络素材主源在世界门的 factions 域与贯穿矛盾
  （contracts.WORLD_ARCHITECTURE 的 civilizations→factions、conflict→rules 绑定）；relationships 新增
  opposition 语境（opening_choices 按游标携带全部前门），背叛风险的落笔对象从「尚不存在的对手网络」
  变为已定网络。损失声明：opposition 的方案生成不再见到已选 relationships（若有先关系构想，走 intake
  预填归位）。

back 半径再分配（如实声明）：back(scale) 作废门数 10→11（voice 移到 scale 之后），tier 改档的返工半径
+1；换取 back(voice) 11→8 与 P2 错配消除。

## 2. 逐门 VALUE_RULES 变化（validate_value 不动，接受集零变化）

VALUE_RULES 是任务卡里写手逐字段读的规格行；本轮把埋在代码注释、recover 提示与文档里的约束前移进任务卡
（同 b0e1efe 的「结构化列表提高首轮命中」杠杆），要点：

- **genre**：reader_promise 行加平台指引——写清目标读者的阅读预期与主要落点平台（起点式长线订阅追读 /
  番茄式快节奏免费 / 双平台），说明承诺靠什么兑现；tone 行写明分属 genre/payoff(theme)/voice(pov) 三门
  三字段易串，逐门路径必填、直接导入可省（契约层 optional，既状明示）。
- **premise**：stance/dark_side 改为「枚举原词」表述并给反例（「人性」「天灾人祸」会被拒）；外部不可抗力
  取外神/天灾/系统、人心与制度取上层剥削/制度/人心（recover 语义前移）；占位词（待补/暂定/同上/略）任一键
  即拒；新增「与世界模型共享词表、选后只能承接不能推翻——世界级承诺」警示行（P5 缓解：脑洞先行是设计意图，
  不动位置，以规格提示分量）。
- **scale**：单行字符串改列表行——本门由引擎按档位表即时给定不接受方案回执；intake 只写 {"tier":"tN"}；
  档位数字以当前档位板为准不凭记忆写（六档 chapter_min=2000、chapter_max=10000 统一，chapter_aim
  t0=3500…t5=6000）；tier/volume_count/chapters/chapter_window 只喂推导不进合同，word_range/
  chapter_min/max/aim 进合同且可参数化修订。
- **world**：architecture 行保留五键集合合格式并补五键中英对照、键集恰五键多/少即拒；space 补格局 envelope
  申报（终局是否触及一界/星海/诸天——触及即 cosmology 域必填，P4 的义务前化到作者决策点）；tiers/resource
  行写明 ≥2 字动机（短名让同名记录被偶然命中、绑定不再是证据）；red_lines 行写明可空但必须数组、进约定后
  可增不可减；mechanism/allow_special_mechanism 恒等式示例（mode=bounded → true、none → false）。
- **ladder**：terminal/scope/growth 三枚举加「枚举」前缀并缩进为子行（不再与顶层字段行混排同缩进，防被
  误当 value 顶层键）；新增「势力在 terminal 与 growth、局部在 terminal 与 scope 同字不同表」互串警告；
  terminal=局部 只许 t0/t1；stage 必须是能落世界四域同名记录的名字（语义从文档前移进任务卡）；新增与
  world.space envelope 的衔接行。
- **voice**：style_traits 补形状示例（写成单字符串或逗号分隔一句会被拒）；新增新序语境行（cosmology 与
  格局终局已选，落约后逐字对齐不可漂移）与分工行（写作纪律由 style_profile 参数承担，本门只定结构性
  叙述事实）。
- **origin**：family 行改「枚举原词」并前移 recover 语义（四方向之外的变体归「其他」并在 arrival 说清
  机制）；arrival/cost 各写分工（怎么来带来了什么 / 代价或麻烦）。
- **edge**：五键各加语义注（advantage 承接世界门 architecture.conflict 等），并新增「五键逐项结构化，
  不可留空或并成一段散文」行。
- **protagonist**：id 行写明「:」是世界 links「领域:id」分隔符；name 行写明 name/desire/limit 逐字进世界
  characters 记录与约定 entities；新增俗套姓名 advisory 严重度说明（只警不拦；硬禁某字用字面规则）。
- **opposition**：两键各加分工（连到利益网络与根本矛盾；胜利如何改变局面、对抗如何持续供料）；利益网络
  素材以世界门 factions 域与贯穿矛盾为准；新增俗套自审引用与「关系门在其后依附于此」新序语境行。
- **relationships**：补形状示例（每条一句：人物+所属秩序+立场；写单条字符串或对象数组会被拒）；新增
  「依附于哪股已选势力/对手网络 + 感情线的分量与处理」新序语境行。
- **payoff**：anchor 行写全（纯数字章号例 28、写「第28章」会被拒、上限 min(30, 档位 chapter_window 上界)、
  键集恰两键）；plan.ways 数组语义与模板占位纠正提示前移；cadence 行锚定第1门 reader_promise 落的平台
  读法（起点式长线与番茄式快钩不同，引擎不设统一密度）；theme 行写明区别于 genre 门 tone。
- **title**：加默认禁词约束（含「账本/入账/回执」会被 literal_policy 拒）与「与已选 reader_promise/ending
  相称」。

## 3. 平台指引验收口径

genre.reader_promise 与 payoff.plan.cadence 的平台锚定文字是**方向性申报，不是频率公式**：验收时不得把
「起点式长线」「番茄式快钩」读成统一打脸频率、固定桥段间隔或任何数值密度（红线见 hatch.md「使用边界」：
不固定打脸频率或每卷换敌）。规格行已自带「不写统一频率或桥段公式」「引擎不设统一密度」限定；评审或抽读
发现把平台锚定执行成公式化节奏的，按违反红线处理，不按规格通过。

## 4. 字面版本号清理清单（升版必改，grep 已复核为穷尽）

- `tests/test_opening_architecture.py`：五处以字面 6 作版本实参的 `validate_value('world', …, 6)` 改
  `contracts.OPENING_VERSION`（creation 对 version≠OPENING_VERSION 抛 code='creation' 而非
  'opening_option'，升版后原断言必红）；`:111` 版本断言 6→7；docstring「Opening/6」→「Opening/7」。
- `tests/test_presentation_boundaries.py`：夹具字面 `'novel-ledger.creation/6'` 改
  `'novel-ledger.creation/%d' % contracts.OPENING_VERSION`（该文件自备 MemoryReader，不经 support.drive；
  bookpage.render 对含 selections 的 creation 调 creation.opening_version，非当前 schema 一律拒绝）。
- `tests/test_opening.py`：`for version in range(1, OPENING_VERSION)` 拒绝循环自动扩展至 creation/6，
  跑通确认而非改写；首四门断言改 `('genre', 'premise', 'scale', 'world')`。
- `tests/test_domain_boundaries.py`：`gates[:4]` 改新序并更新注释。
- `tests/test_bookpage.py`：手工走门顺序改 genre→premise→scale→world→ladder→voice。
- `tests/test_editorial.py`：intake voice/title 后 `current=='genre'` 断言在新序仍真（voice/title 均在
  genre 之后），不改。
- grep 面（tests/ 全目录：字面 'creation/6'、版本化 API 的字面实参）之外无其他命中；动态构造无法穷举，由
  `python -X utf8 validation/run_tests.py full` 全量兜底。

## 5. 兼容性与风险声明

- **无迁移**：升 opening/7 后一切存量 guided 书（含 phase=ready 已完本）在新引擎下读取即拒
  （status 与后续阶段 brief 都会触发），只能以当前协议重开；纯导入约定（init --contract，creation=None）
  不受影响。发布前需人工盘点在途项目。
- **P1 仅部分缓解**：档位板不携带前门语境、tier/卷数不可参数化修订属机制面（硬约束禁改），本轮只把
  scale 推到 world 前最后合法位并补文档纪律。
- **首轮命中率改善为预期性结论**：VALUE_RULES 纯文本变化不改变拒绝面，方向有 b0e1efe 实证支持，需下一
  个真实开书项目实测回归。
- **voice 后移的软代价**：premise/world/ladder 三门的方案画面在视角选定前生成、不能沿用已定人称
  （机械只查条数与 ≥12 字）；hatch.md 已按新位置写明「视角门前各门画面不锁人称」。
- **opposition 前移的语境损失**：其方案生成不再见到已选 relationships；利益网络素材以世界门 factions 域
  与贯穿矛盾为准（机械 grounding 在 contracts.WORLD_ARCHITECTURE 绑定表）；先有关系构想走 intake 预填。

## 6. 验证命令

```bash
python -X utf8 validation/run_tests.py fast   # fast 组不含 test_opening.py，绿不等于开书面绿
python -X utf8 validation/run_tests.py full   # fast+e2e 严格超集，full 兜底
```
