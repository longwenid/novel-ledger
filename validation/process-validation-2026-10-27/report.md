# novel-ledger 流程验证报告（2026-10-27）

**验证对象**：novel-ledger 技能仓库（`C:/Users/longwen/.zcode/skills/novel-ledger`，引擎 2.1.2，engine_hash=501c0d58…，rules_hash=8ac920b5…，matches=true）
**验证项目**：`C:/Users/longwen/.zcode/novel-ledger-process-validation`（零输入 init、作者全权委托，最终成书设定：《这片停电的巷子归我供电》，都市异能·停电老城供电人，t1 短篇 2 卷 50 章）
**验证方式**：五阶段实跑（零输入逐门开书 → 世界模型与作者约定 → 卷纲+章纲合并派工 → 章纲生效核实 → 首章执笔）＋四份独立评审（文档审查/卷纲节奏/章纲节奏/首章试读）＋分诊合并（33 条原始记录 → 30 条独立问题）＋高危项只读复核。全部对源项目只读（副本材料见同目录 outlines.md / chapter1.md / decisions.md）。

---

## 执行摘要

**跑到哪**：流程全链跑通——零输入 init＋十三门 13/13 落定 → 世界模型/作者约定一次交付过审（任务 933092a7…，outcome=design_accepted）→ t1 合并档（merge_chapter_outline）两卷卷纲＋50 章章纲单次提交安装并作者 confirm（任务 2c198a12…，volumes_hash=edf237d6…）→ run --complete 授权至完本 → 首章《半格电》零返修 committed（repairs=0/redesigns=0，committed_chapter=1）＋作者认可（approve --prose-hash a40c1985…）。引擎终态（`python novel.py --project … status`，exit 0）：status=running、accepted_chapters=1、target=50、written_han=3418、volume_gate round 0 confirmed=["all"]、opening 13/13、continuity_mode=off、trust=advisory、writing_batch_chapters=5、无 pending_task/author_decision/pause、引擎 2.1.2 哈希匹配。各作者边界（十三门、卷纲认可、正文授权、首章定调）均按设计停走后由作者代理放行，22 条决定逐条登记于 decisions.md。

**卡在哪**：无阻塞性卡死——五阶段全部 completed、无 blocker 残留；三轮机械拒收（opening_voice、world_alignment、placement）与一次 worker 会话阻断均在 1–2 轮内按提示恢复。真正的「必卡点」在已安装的章纲内容里：唯一 high 级问题 V1（ch25/ch27 同夜事件跨卷重复消费）尚未爆发，但执笔推进到第 25/27 章时必有一章无法按纲落笔，须在到达前修订章纲或调整其中一章。

**最严重三条问题**：
1. **V1（high，pacing）**：同一夜事件（周电长烧旧物、秦姨抢半本老登记簿）在 ch25 与 ch27 各完整叙述一遍，h7 的 plant 账记在 ch27 而承诺载体在 ch25 已呈现给读者——执笔两章必有一章无法按纲落笔；正是卷间边界检查缺口（V13）放过的形状。
2. **V2（medium，engine）**：卷级 places/knowledge/characters/relations 实体引用校验只认世界模型 characters 的 id 集（配角 char- 前缀），约定 entities 与既有状态里的同名无前缀 id 一律判「未登记」，而章级增量用同一批 id 完全通过——两级判据不一致，造成一次 14 条 blocker 的拒收轮。
3. **V8（medium，pacing，方法层双评审互证）**：开篇期待感与爽点兑现节奏在方法层无抓手（伏笔 plant 窗口允许落在卷内任意章、无「开卷前几章应有可见承诺或首个兑现」提示项、卷级五条结构纪律无章级对应物）——本产出的合格开篇（第 3/5 章首兑现）属设计者手感而非方法保证，同族缺口还有中段维持无检查位（V9）与断章钩子无结构位（V12）。

**问题总量**：33 条原始记录合并为 30 条独立问题——pacing 14、docs 8、engine 3、design 2、other 2、author-gate 1；severity 分布 high 1 / medium 14 / low 15。文档审查总评：整体流程文档成熟度很高（恢复与失败路径真正闭环、数值口径单源、anchor_check 25 文件 0 坏链），薄弱点集中在一处默认值口径漏同步、协议页 outcome 枚举缺项、章纲活字段权威页缺位、十三门无委托自决通道与两套「蓝图」撞名。

---

## 实跑记录

| 阶段 | 操作类别 | 结果 | 涉及问题 |
|------|----------|------|----------|
| 零输入逐门开书 | init + advance/regroup/choose ×13 门 | ✅ completed，13/13 门落定，phase=ready | V16、V17 |
| world_model（含 opening_contract 同任务交付） | prepare-worker + worker read + submit（两轮 preflight 拒收后过审） | ✅ completed，outcome=design_accepted | V29、V6、V20、V21 |
| volume_outline（t1 合并档，含 chapter_outline） | worker read + submit（一轮 preflight 拒收后过审）+ confirm-volume | ✅ completed，volume_gate round 0 confirmed=["all"] | V2、V18、V21 |
| chapter_outline（章纲） | advance --compact 核实生效（无独立任务可领） | ✅ completed，action=outline_ready，50 章章纲已安装 | V18、V30 |
| 首章执笔（write 第 1 章） | run --complete + prepare-worker + submit + approve | ✅ completed，chapter_committed 零返修＋作者认可 | （无新增问题） |

### 阶段一：零输入逐门开书（init + 13 门）

- **操作类别**：引擎驱动（init / advance / regroup / choose），作者代理逐门选择（决定 1–14）。
- **结果**：十三门全部落定（题材→题材基因→前提→体量→世界→格局→视角→来历→能力边→主角→对手→关系→兑现→书名）；门 3 曾 regroup 滑窗口到微型/短篇/精简再直达 t1 短篇。
- **作者边界点**：13 门逐门停等，作者代理逐门选择（清单见 decisions.md 阶段一）；世界门首轮被 opening_voice 拒后改写作者可见文本重交（不改引擎判据）。
- **卡点原文摘录**（V16，regroup 后板面不刷新）：`regroup --board a5a300fa… --reason '验证运行需要小体量…'` 执行后 `cat work/board.md` 与 work/last-advance.json 仍为 t3/t4/t5 旧板（hash 仍 a5a300fa）；用旧 hash 二次 regroup 被拒：`error=opening_version, details.current_board=673a6b2f…`；再跑 `advance --compact` 得 await_choice round=1 hash=673a6b2f…，board.md 才更新为 t0/t1/t2。
- 另记（V17）：`status` 返回体 book_view.path 为 None（init/advance 均带该路径），磁盘上 book.html 存在（20941 字节）。

### 阶段二：world_model（含 opening_contract，同一任务交付）

- **操作类别**：Worker 执行（prepare-worker 登记会话 world-model-builder-1 → read → 起草 → submit，preflight 两轮拒收后过审）；作者代理代填约定补全字段（决定 15–17）。
- **结果**：任务 933092a7… submit accepted=true, committed=true, outcome=design_accepted, worker_boundary=finished；advance 激活约定并派出合并派工任务 2c198a12…（stage=volume_outline, stages=[volume_outline, chapter_outline]）。
- **作者边界点**：Worker 身份边界（主干代理身份登记）；十三门未固定填空项的代填（red_lines 最小超集、卷划分 2×25、initial_resources、placements＋contract.places）；约定激活即停、不代跑卷纲。
- **卡点原文摘录**：
  - 第 1 轮（V29）：`{"error": "world_alignment", "message": "世界模型须保留所选主角的身份、欲望和底线。", "details": {"rule": "characters 里须有一条记录的 id/name/desire/limit 与所选主角逐字相同", "expect": {"id": "chang-liang", …}}}`——主角记录裸 id 起草为 char-chang-liang 所致（brief.md:59 本已写明），改 id 并同步 8 处 characters 链接后通过。
  - 第 2 轮（V6）：`{"error": "placement", "message": "初始站位实体或地点不存在。"}`——简报未提地点 id 须先在 contract.places（{id,name}）登记；查 protocol.md:46 与 assets/contract.example.json 后补齐复检通过。
  - 会话阻断（V21）：宿主未注入 NOVEL_SESSION 等环境时首次 read 报 error=session（recovery failures=1），第二次仍 technical_blocked（failures=1/limit=2, retry_allowed=false, action=prepare_worker）；prepare-worker --reset-failures 后注入 NOVEL_* 再 read 成功。
  - 另记（V20）：read_pack.md 仅 3 行头部，opening_basis/opening_choices 全文在 read_ref.md，与 dispatch.md「两包都要读」措辞错位，不影响执行。

### 阶段三：volume_outline（t1 合并档，含 chapter_outline）

- **操作类别**：Worker 执行（read → 起草两卷卷纲＋50 章章纲＋完整状态链 → submit，preflight 一轮拒收后过审）；作者边界 confirm-volume（决定 18–19）。
- **结果**：任务 2c198a12… submit accepted/committed（outcome=volume_confirmation_required，worker_boundary=finished）→ confirm-volume confirmed=true → advance=outline_ready；volume_gate round 0 confirmed=["all"]（volumes_hash=edf237d6…），50 章章纲在同一事务安装（work/volume-design.md 273KB 含合并章纲全文）。
- **作者边界点**：await_volume_confirm 认可安装（source 原话绑定 volumes_hash）；未行使 revise-volume/regroup-volume（两条 advisory 均未触发，无额外轮次）。
- **卡点原文摘录**：
  - 第 1 轮（V2，14 条 blocker，criterion=volume_reference）：findings kind=places key=ma-liu『卷纲站位引用了世界模型与既有状态都没有的实体…先在约定 entities 登记』＋knowledge(qin-yi/ma-liu/xiao-zhao/zhou-dianzhang)/characters(ma-liu)/relations 共 14 条——而这些无前缀 id 在 read_pack.md:22-96 state.entities 与 read_ref.md:5-55 contract.entities 均存在，世界模型 characters 却用 char- 前缀；第 2 轮去掉卷级配角引用后 valid=true（配角终值声明改留章级增量后通过）。
  - 合并档交付面（V18）：brief.md:1『本批次为合并派工…必须在同一回执交付 chapters——按 result.template.json 的 chapters 骨架逐章填齐本批次全部卷的章纲』——一份 50 章回执同时过两个契约。
- 卷纲要点：vol-1 巷口台区（第 12 章按 promise_anchor 兑现平价规矩，h1–h6 卷内全收口）、vol-2 自治台区（h3 第 40 章 payoff，终局对齐 contract.ending）；clock 40/85，现金 1200→6000→9300，马六囤电 300→0。

### 阶段四：chapter_outline（章纲）

- **操作类别**：引擎核实（advance --compact / status --tasks / 库内只读核对），无任务可领——t1 合并档下章纲已随卷纲任务交付安装。
- **结果**：action=outline_ready（coverage vol-1 第 1–25 章、vol-2 第 26–50 章，planning_mode=all，selection_hash=670e550e…）；`status --tasks` 14 任务全部 done（无 chapter_outline 任务）；book.intent.chapter_outlines 已安装 50 行。
- **作者边界点**：outline_ready（正文 run 授权）——本阶段不代下一阶段预先 run，授权终点留给正文阶段（决定 20）。
- **卡点/备忘摘录**（V30，方法教训）：曾据 `ls work/ | head -20` 误判 volume-board.md/volume-question.json/volume-design.md 三个文件丢失（head 截断了字母序靠后的文件），逐文件 os.path.exists 核实均在；volume-design.md:483 起为『## 合并章纲』，解析得 vol-1 第 1–25 章、vol-2 第 26–50 章连续。后续阶段不要用截断式目录列举下结论。
- 另记：design_drift 拒绝循环在本项目零触发（合并档 submit 一次通过，findings=[]），「错误提示定位质量/修复轮次」验证点无真实事件可评；若需覆盖拒绝路径须另造场景，不宜在本项目追加。

### 阶段五：首章执笔（write 第 1 章）

- **操作类别**：作者授权（run --complete）→ Worker 执笔（任务 5bbc81b8…，prepare-worker 新会话）→ submit → 作者认可 approve（决定 21–22）。
- **结果**：submit 返回 outcome=chapter_committed、committed_chapter=1、transaction.persisted=true、findings=[]（零返修）；approve --prose-hash a40c1985… approved=true。status=running、accepted_chapters=1、written_han=3418、drift_check=clean。
- **作者边界点**：run --complete 授权至完本（target=50，source 原话绑定）；首章认可定调（对白占比 0.12 与段均 30.5 的偏离按开卷夜戏处境性偏离随认可说明，机械基线按认可首章登记）。
- **卡点摘录**：无。首章产物：work/5bbc81b8…/（task.json、prose.txt 12328 字节、result.json 等），正文《半格电》全文副本见 chapter1.md。

---

## 问题清单

30 条独立问题按 kind 分组。**复核状态**说明：V1 经只读复核 verified（复现链完整）；其余 29 条为各阶段/各评审一手记录经分诊合并（33→30），证据链完整但未经第二轮独立复核。

### pacing（14 条）

- **V1**｜severity: **high**｜复核: **已复核 verified**（只读复现成立，并核实章纲已作为 write/ch1 冻结输入生效）
  - **where**：`work/2c198a12e64c4d9dbb88b1faf54ba06c/result.json` 第 25/27 章（data.chapters.vol-1[24] 与 vol-2[1]）
  - **what**：同一夜事件（周电长烧旧物、秦姨抢半本老登记簿、洇了半个名字的签收人）在 ch25 与 ch27 各完整叙述一遍：h7 的 plant 账记在 ch27，但承诺载体在 ch25 已呈现给读者，ch27 还再推 2 天时钟——执笔两章必有一章无法按纲落笔；正是卷间边界检查缺口（V13）放过的形状。
  - **证据摘录**：ch25 synopsis『周电长烧旧物那晚，秦姨抢下半本老登记簿……签收人一栏洇了半个名字。常亮把簿子收进铁盒』＋knowledge 增量 hinted→suspected；ch27 synopsis『周电长连夜烧旧物，火盆里全是旧单据。秦姨抢先捞了半本老登记簿出来……只剩半个姓』且 knowledge 为空、clock advance_days=2；h7 声明 plant [26,30] 而 plant 行落在 ch27。复核：python -c 读取 result.json 逐字复现两章原文；引擎 status（exit 0）证实 volume_gate round 0 confirmed ["all"]，任务 5bbc81b8 input.json 的 chapter_outline 与 vol-1[0] 逐字节相同（章纲确为冻结输入）。
- **V8**｜severity: medium｜复核: 未独立复核（卷纲/章纲两评审互证合并）
  - **where**：references/narrative.md:169-174（伏笔窗口）、references/craft.md:15-37（开书与规划节无开篇密度位）、references/narrative.md:79（五条结构纪律仅卷级）
  - **what**：开篇期待感与爽点兑现节奏在方法层无抓手：plant 窗口允许落在卷内任意章、数量无默认、无「开卷前几章应有可见承诺或首个兑现」提示项；章纲层开书节不提「前 N 章须完成主角处境、第一兑现」，卷级五条结构纪律无章级对应物——本产出的合格开篇与首章正文的开篇白描压线（V27/V28）均属设计者手感或落空档，而非方法保证。
  - **证据摘录**：narrative.md:171『plant: [最早章, 最迟章] 必须落在本卷章号区间内』无更早/更密要求；volume-blueprint.md:277（BP-3.1）『这是跨度菜单，不是每卷配额』；产出层 ch1 危机+能力+代价、ch3 第一笔平价电钱、ch5 盯表自证为纲作者自发挥。
- **V9**｜severity: medium｜复核: 未独立复核
  - **where**：references/narrative.md:75（advisory 仅两条）；scripts/novel_ledger/workflow.py:272-288（实现）；volume-blueprint.md:680（S-15）
  - **what**：中段维持无检查位：卷纲层唯一涉及节奏形状的自动检查只有「threads/hooks 全无 continues」与「各卷转折恰两条且全在卷中/卷尾」两个窄触发 advisory（后者要求所有卷同时命中），转折堆卷首卷尾夹空腰、伏笔窗口两端聚集卷腰无兑现等塌腰形状不触发任何提示；产出层 vol-1 ch11–16 同型微循环（V11）即落在该缺口上。
  - **证据摘录**：workflow.py:280-284 `templated = all(len(volume.get('turns') or []) == 2 and all(... turn.get('at') in ('卷中', '卷尾') ...) for volume in volumes)`；volume-blueprint.md:680（S-15）『卷内中段节拍/支线密度的逐章精度……每卷中部仅 1 窗』自登空白。
- **V10**｜severity: medium｜复核: 未独立复核（凑字实例＋状态链核账反向核实合并）
  - **where**：`work/2c198a12…/result.json` 第 17 章 synopsis；方法层 references/narrative.md:147（words±tolerance 校验）
  - **what**：synopsis 硬字数下限诱发内容凑字：ch17 出现整句重复，删重后 86 字低于 90 字下限；反向核实确认状态增量核账本身不结构性伤害叙事弹性（空声明合法、静章合法、结构字段缺省合法），实际伤害来自硬字数下限。
  - **证据摘录**：ch17 synopsis 原文『……巷口安静了两天，安静得反常。巷口安静了两天，安静得反常，常亮让街坊夜里留个心。』统计『ch17: 100』汉字，手工核验删重后 86<90；全书 50 章 synopsis 分布 90–128，ch18/ch20/ch26 恰 90 压线。
- **V11**｜severity: medium｜复核: 未独立复核
  - **where**：`work/2c198a12…/result.json` 第 11–16 章 synopsis（vol-1）
  - **what**：vol-1 中段 ch11–16 连续六章四次同型『对手出招→当众化解→口碑+1』微循环（信息费、泼油、压价、登记簿乱序），且 ch16 与 ch7 同型——正缺章级『同型化解不连用』类纪律与中段检查位（方法缺口见 V8/V9）。
  - **证据摘录**：ch11『马六…收谁的信息费…全巷来』、ch13『柴油泼上黑板』→ch14『街坊一人一笔描回』、ch15『三句话点破囤电倒卖…队齐刷刷掉头』、ch16『登记簿把人命电器的户排到了后头…当场重排』；ch7 与 ch16 同为排序生事→当众对质化解。
- **V12**｜severity: medium｜复核: 未独立复核
  - **where**：references/narrative.md:92-94,120；references/craft.md:23
  - **what**：断章钩子（章尾推力）无任何结构化位置或评审位，只靠 synopsis 文字里的『对下一章的推动』与 beats 第三拍示例；框架允许静章收尾但从不提示连载章尾外推的留存作用——产出 ch1/2/5/13/23 均为内收收尾（首章因四线蓄力被试读评审留读，属执行层补救而非框架保证）。
  - **证据摘录**：产出末句 ch1『他没让第二个人看见』、ch2『他把这个没答案的问题记下了』、ch5『第二天谁来看都给看』、ch13『没少一个』、ch23『解成互相欠着』。
- **V13**｜severity: medium｜复核: 未独立复核
  - **where**：references/narrative.md:75（卷纲待认可 advisory）；work/volume-board.md（两卷弧线原文）
  - **what**：卷间边界只有两条只警不拦的 advisory（卷间纠缠缺位、转折位置模板同构），不覆盖『前卷卷尾已叙述/消费后卷开场事件』的重复——ch25/ch27 的高危重复（V1）正落在这个检查缺口上。
  - **证据摘录**：vol-1 arc 卷末『秦姨从他烧掉的旧物里抢出半本老登记簿』，vol-2 arc 开局又写『周电长那边连夜烧旧物，秦姨从火盆里抢出半本老登记簿』（volume-board.md 两卷弧线原文）。
- **V14**｜severity: medium｜复核: 未独立复核
  - **where**：references/narrative.md:115（`"pacing": {}` 示例）与 :124（pacing.note 一句带过）
  - **what**：pacing 字段有键无形状：回执示例只给空对象，全文档仅一句『意图写入现有 pacing（如 pacing.note）』，无可用键与语义说明，产出层 50/50 全空；beats/scenes 同样 0/50、role 9/50，框架的结构表达层在产出中形同虚设（与 V5 权威页缺位同类）。
  - **证据摘录**：统计输出『总章数: 50 / 字段使用数: {"disclosures": 5, "role": 9}』；h3 topic 三档推进（hinted ch2→suspected ch38→confirmed ch40）是 disclosures 成功用例，但 beats 0/50、pacing 0/50、scenes 0/50。
- **V15**｜severity: medium｜复核: 未独立复核
  - **where**：`work/5bbc81b845624140ada0aa36b1de02e9/prose.txt:105`
  - **what**：场景标题「〔秦姨〕」直接印在正文流里，网文正文无此惯例，读者第一反应是排版错误或草稿残留，出戏一次（self_check 已申报为有意设计）。
  - **证据摘录**：prose.txt:105 原文独立一行「〔秦姨〕」；self_check 申报『仅一场配角场景〔秦姨〕在切入前以场景标题标明跟随对象』。
- **V24**｜severity: low｜复核: 未独立复核
  - **where**：方法（volume-blueprint.md:6、747；craft.md:21；运行 status 见 structure_blueprint=null）
  - **what**：节奏对照标准自身未生效且不自证密度：蓝图 v1.2 待作者确认稿，引文未复验、选择与派工机制未接入，本项目未绑定（structure_blueprint=null），其节奏条目（BP-2.1 三段式、BP-7.2 高潮窗集中兑现等）对当前运行不构成约束，实际生效的节奏保障只来自执行协议（伏笔账/卷末闭合/五条纪律/两条 advisory）。
  - **证据摘录**：volume-blueprint.md:6『本版仍待作者确认，确认前不得供 novel-ledger 写作项目使用』；status 输出 `"structure_blueprint": null`。
- **V25**｜severity: low｜复核: 未独立复核
  - **where**：产出（卷 2/第 44–50 章）：`work/2c198a12…/result.json` chapters.vol-2 逐章 beat
  - **what**：终卷高峰后五章程缓收束：ch44/45 高潮峰值之后 46–50 五章为制度+情感收束段，尾部动能主要靠 h9（48 章兑现）与挂牌大典（49 章）维持，连载追读有尾部卸力风险；属刻意多拍收尾且终卷不要求新悬钩，形状成立。
  - **证据摘录**：ch44『挂牌前夜线路被动手脚，自治当场上演』（role=高潮章）、45『人赃并获，黑市断根清街』（h10:payoff）、49『挂牌日，样本进简报』（role=终章）、50『名单未动，巷子自己排序』（role=卷尾章）。
- **V26**｜severity: low｜复核: 未独立复核
  - **where**：`work/2c198a12…/result.json` 全书 hook_refs 统计；references/narrative.md:182-186
  - **what**：h3（三年前名单之谜）plant 第 2 章、payoff 第 40 章，跨 38 章间隔中仅 1 次 hook_refs 再提，长线承诺的读者期待维系密度偏低。
  - **证据摘录**：提取输出『--- hook_refs 非空位置 --- ch12: [h1] ch25: [h3] ch34: [h7]』。
- **V27**｜severity: low｜复核: 未独立复核
  - **where**：`work/5bbc81b845624140ada0aa36b1de02e9/prose.txt:1-17`（前 300 字）
  - **what**：开篇前约 280 字全是巷子与错峰制度的白描铺陈，人物本体压到 311 字才露名，刷屏读者有耐心考验；靠 283 字处的「黑了三年的窗台上亮起一点蓝」才把钩子抛进窗口内，属压线达标（方法层无开篇指引的空档，见 V8）。
  - **证据摘录**：python 统计去空白后 s.find('常亮')=311，s.find('一点蓝')=283；prose.txt:3-5『江北钉在末档，三天两停……电来了，是运气；电不来，是本分』。
- **V28**｜severity: low｜复核: 未独立复核
  - **where**：`work/5bbc81b845624140ada0aa36b1de02e9/prose.txt:59`
  - **what**：能力来源与保密动机在一段内集中说完（获得+代价+不能说三层一次灌），是全章最接近设定倾倒的一处，节奏陡平。
  - **证据摘录**：prose.txt:59 原文『三年前限电之夏，他守着爹的呼吸机，掌心贴住金属，体力头一回渡进了电器。本事长在身上，一天约莫二十度……说出去就是造谣外加精神有问题，所以他谁也没告诉』。

### docs（8 条）

- **V3**｜severity: medium｜复核: 未独立复核
  - **where**：references/architecture.md:267
  - **what**：独立连续性核验的默认值口径与其余六处文档相反：此处称新项目默认开启独立连读，而 quality.md/runtime.md 与 CLI 实际默认均为 off——commit 7287857 六处同步漏掉 architecture.md。
  - **证据摘录**：architecture.md:267「新CLI项目默认独立连读与候选比较」vs quality.md:7「新CLI项目默认 `continuity=off, trust=advisory`」；已核实 novel.py:80 default='off'。
- **V4**｜severity: medium｜复核: 未独立复核
  - **where**：references/protocol.md:5
  - **what**：自称回执/outcome 权威的协议页枚举 outcome 时漏掉 volume_confirmation_required。
  - **证据摘录**：protocol.md:5 枚举六种 outcome 无 volume_confirmation_required；runtime.md:168「volume_confirmation_required是卷纲已暂存待作者认可」；application.py:886 `business = ('volume_confirmation_required' if volume_pending else ...)`。本项目实跑即命中该 outcome（阶段三 submit 返回）。
- **V5**｜severity: medium｜复核: 未独立复核
  - **where**：references/narrative.md:89-130 vs references/quality.md:59-71
  - **what**：章纲模板实有的 story_events/reader_effect/timeline 三个字段不在章纲回执形状里，timeline/deadline 的声明义务（已登记未结期限须在后续主线章保留、跨过时须 fulfilled/failed/abandoned）只写在核验指南页——字段权威页缺位（与 V14 同类）。
  - **证据摘录**：narrative.md:89-116 回执 JSON 与 119-130 字段清单均无此三字段；引擎侧为活字段：result_templates.py:112 章行模板含 `'story_events': [], 'reader_effect': None, 'timeline': None`，drift.py:30 同列；briefs.py:384 会解释，缓解但不消除权威页缺位。
- **V6**｜severity: medium｜复核: 未独立复核
  - **where**：`work/933092a7b7534e8282fea4d10dc3bd32/brief.md:63`（contract.placements 条）与引擎 placement 校验
  - **what**：任务简报对 placements 只写『地点存在于世界 geography』，未提地点 id 须先在 contract.places（{id,name}）登记；该形状只在 protocol.md 与示例约定中可查，导致一次额外拒收轮。
  - **证据摘录**：preflight 第 2 轮 `{"error": "placement", "message": "初始站位实体或地点不存在。"}`；查 protocol.md:46『places=[{id,name,parent?}]、placements={entity:place}』后补 contract.places 复检通过。
- **V20**｜severity: low｜复核: 未独立复核
  - **where**：`work/933092a7…/read_pack.md`（本阶段写作材料包）
  - **what**：read_pack.md 为空壳（全部必读材料落在 read_ref.md），dispatch.md 要求『两包都要读』，措辞与实际分布略有错位；不影响执行。
  - **证据摘录**：worker read --save 输出 packs=[read_pack.md, read_ref.md]；read_pack.md 仅 3 行头部，opening_basis/opening_choices 全文在 read_ref.md。
- **V21**｜severity: low｜复核: 未独立复核
  - **where**：commands.read 首次调用（无 NOVEL_* 环境注入）
  - **what**：宿主未注入 NOVEL_SESSION 等环境时 worker 入口按身份错误计一次技术失败并立即阻断（failures=1/limit 2 即 technical_blocked），须主控 prepare-worker --reset-failures 才能继续；dispatch.md 虽写明可在 -- 前显式传 --session/--execution-claim，但没有先注入就试跑一次的代价是一次技术失败额度＋一轮复位。
  - **证据摘录**：首次 read 报 error=session（recovery failures=1），第二次仍 technical_blocked（retry_allowed=false, action=prepare_worker）；复位＋注入后 read 成功（saved read_pack.json, execution_id=115b93da…）。
- **V22**｜severity: low｜复核: 未独立复核
  - **where**：references/craft.md:71
  - **what**：『scene_context/2』记法与版本化能力命名（scene-memory/1、scene-identity/2）撞形，读者会去找不存在的『scene_context 第 2 版』能力。
  - **证据摘录**：craft.md:71「`scene_context/2` 通过 `plan_record` 引用它」；protocol.md:58 写法为「scene_context/scene_sources 为冻结的场景输入」且能力是 capabilities.scene_memory=scene-memory/1（workbench.md:44）；代码中无 scene_context/2（grep 仅 craft.md 一处）。
- **V23**｜severity: low｜复核: 未独立复核
  - **where**：README.md:215-231
  - **what**：仓库结构中的 references/ 清单漏列 volume-blueprint.md（747 行）与 volume-blueprint-bridge.md（120 行）两个实际存在的文件。
  - **证据摘录**：README.md:215-231 列出 references/ 下共 15 项不含这两文件；`grep -n volume-blueprint README.md SKILL.md` 无结果。

### engine（3 条）

- **V2**｜severity: medium｜复核: 未独立复核
  - **where**：`work/2c198a12…/result.json` 卷级字段 vs 引擎 preflight（criterion=volume_reference）
  - **what**：卷级 places/knowledge/characters/relations 实体引用校验只认世界模型 characters 的 id 集（配角为 char- 前缀），约定 entities、既有状态 baseline 与 state.entities 里的同名无前缀 id 一律判『未登记』；与 narrative.md『引用的 key/entity 必须已存在于世界模型或既有状态』的描述不符，且章级增量用同一批无前缀 id 完全通过——两级判据不一致（与 V29 同暴露 id 命名约定无统一口径）。
  - **证据摘录**：preflight 第 1 轮 14 条 blocker（places/knowledge/characters/relations，criterion=volume_reference）；read_pack.md:22-96 state.entities 与 read_ref.md:5-55 contract.entities 均含这些无前缀 id，world_model characters 却用 char- 前缀（read_ref.md:566-642）；第 2 轮去掉卷级配角引用后 valid=true。
- **V16**｜severity: low｜复核: 未独立复核
  - **where**：novel.py regroup（结构门换组）与 work/board.md 物化时序
  - **what**：结构门 regroup 换组被接受并生成新板 hash，但 work/board.md 与 work/last-advance.json 不随 regroup 刷新，需再跑一次 advance --compact 才拿到新板面；主控若 regroup 后直接读 board.md 转发作者，会展示旧档位与已失效 hash（另：regroup 返回 JSON 不含 advance 同名键，action/gate/board 均为 null）。
  - **证据摘录**：复现链四步见实跑记录阶段一（旧 hash 二次 regroup 被拒 error=opening_version，details.current_board=673a6b2f…）。
- **V17**｜severity: low｜复核: 未独立复核
  - **where**：novel.py status 返回体 book_view 字段
  - **what**：status 命令返回体不带 book_view 路径（init/advance 返回均带），主控在纯 status 恢复场景下拿不到预览入口，需另跑 advance 或自拼路径。
  - **证据摘录**：status 输出 book_view.path 为 None；advance --compact 与 init 返回均含 book_view.path="…\book.html"；磁盘该文件存在（20941 字节）。

### design（2 条）

- **V18**｜severity: low｜复核: 未独立复核
  - **where**：阶段设计：chapter_outline 阶段任务卡 vs 引擎 PIPELINE_SHAPES（references/narrative.md:30）；`work/2c198a12…/brief.md`（合并派工段）与阶段标签 volume_outline
  - **what**：t1 合并档下『章纲阶段』实际不存在独立派工：一次派工一份回执须同时交全部 2 卷卷纲＋两卷共 50 章章纲与完整状态链，章纲随卷纲认可在同一事务安装——阶段名 volume_outline 低估交付面、任务卡仍假设 chapter_outline 是独立阶段并预期 design_drift 循环，导致章纲阶段实际无任务可领、无回执可交，只能核实生效。
  - **证据摘录**：brief.md:1『本批次为合并派工…必须在同一回执交付 chapters——按 result.template.json 的 chapters 骨架逐章填齐』；`status --tasks` 14 任务全部 done（无 chapter_outline 任务）；narrative.md:30「PIPELINE_SHAPES 只保留 merge_chapter_outline（t0/t1 为 true）」。
- **V19**｜severity: low｜复核: 未独立复核
  - **where**：references/craft.md:21 与 SKILL.md:53
  - **what**：『结构蓝图』与『卷纲设计蓝图』两套系统共用『蓝图』一词，且 craft.md:21 同段先给用法再宣布『当前 v1.2 仍待作者确认…确认前不供写作项目使用』，是新读者最易迷路点之一（与 V24 同根）。
  - **证据摘录**：craft.md:21 先写「作者选定已确认的设计蓝图后，可按 [卷纲设计蓝图](volume-blueprint.md) 的适用条目展开设计」再收窄「尚未接入」；volume-blueprint-bridge.md:63 的二者辨析藏在未接入文档内部；SKILL.md:53、narrative.md:79 的『蓝图』均指结构蓝图。

### author-gate（1 条）

- **V7**｜severity: medium｜复核: 未独立复核
  - **where**：references/opening.md:9,85,139 与 SKILL.md:19
  - **what**：开书十三门没有任何『作者委托自决』通道：opening.md 明言『系统不代选』，作者明说「你帮我定」时主干只能继续逐门停等或违反边界；chief-editor 技能已支持按委托原话自决选题，novel-ledger 侧未承接该委托，显式委托场景未被文档覆盖。
  - **证据摘录**：opening.md:9「作者决定方向，系统负责给出具体选项」、:126「系统不代选」、:85「13 次作者选择」、:21/139 intake「只保存作者已定的值，不替缺字段补造决定」；grep 自决|委托 在 SKILL.md/opening.md 无结果。

### other（2 条）

- **V29**｜severity: low｜复核: 未独立复核
  - **where**：`work/933092a7…/result.json` 第 1 轮 preflight
  - **what**：世界 characters 主角记录裸 id 起草为 char-chang-liang，机械校验要求与所选主角 id 逐字相同（chang-liang）；属起草错误（brief.md:59 本已写明），与 V2 同暴露世界模型/约定/状态间 id 前缀约定无统一口径。
  - **证据摘录**：preflight 第 1 轮 world_alignment 拒收原文见实跑记录阶段二；将记录 id 改为 chang-liang 并同步 8 处 characters: 链接后通过。
- **V30**｜severity: low｜复核: 未独立复核
  - **where**：work/ 目录核对方法
  - **what**：核实方法提醒：曾据 `ls work/ | head -20` 误判 volume-board.md/volume-question.json/volume-design.md 三个文件丢失，后经逐文件 exists 检查证实均在（此前输出被 head 截断）；后续阶段不要用截断式目录列举下结论。
  - **证据摘录**：ls -la work/ 后接 head -20 时字母序排在 c9a0d729 之后的三个文件被切掉；逐个 os.path.exists 核实均存在，volume-design.md:483 起为『## 合并章纲』。

---

## 网文节奏评审结论

### 卷纲层

**结论：本项目两卷卷纲在全部节奏维度上成立，无 medium/high 级节奏缺陷；但方法层的节奏保证分布不均，成立主要靠执行协议硬保证＋设计者手感。**

- 方法层保证分布：卷末兑现与跨卷悬置由伏笔账＋卷末闭合＋结构纪律⑤机械硬保证；转折分布只有两条窄触发、只警不拦的看板 advisory；开篇期待密度、爽点兑现间隔与中段维持完全落在设计者判断区（V8/V9）。对照标准 volume-blueprint.md 是 v1.2 待作者确认稿（本项目 structure_blueprint=null），且自身登记无密度统计（S-2/S-3/S-13/S-15），只能对照形状不能对照密度（V24）。
- 产出层逐项核实：开篇钩子具体有载体且第 3/5 章即有首个兑现；转折 5/6 条近似均布（归一约 0%/17%/42%/58%/75%/96%）且每条可指认所换的对抗条件；中段在卷纲与章纲两层都有载体不塌（卷一 8–18 章、卷二 31–37 章逐章核实）；卷末高潮窗集中兑现并产出下卷受力点（老登记簿直成卷二 h7/n6）；跨卷悬置 h3/t2 在卷二开局直兑；伏笔兑现间隔约 3–5 章。
- 唯一保留：终卷高峰后五章缓收束的轻度尾部卸力风险（V25），属刻意多拍收尾、形状成立。

### 章纲层

**结论：50 章章纲是合格偏上的样本，框架骨架方向正确；主要缺陷是一处跨卷事件重复消费的高危矛盾、中段同型循环与一处凑字重复句。**

- 方法层：synopsis 六要素（行动-阻力-选择-代价-结果-推动）、伏笔 plant/payoff 窗口账、disclosures 分层揭秘与反公式纪律（静章合法、空增量合法、禁平台爽文公式）都能引导出网文式推进；但断章钩子无结构位（V12）、开篇与章级节奏无方向性纪律（V8）、pacing 字段有键无形状（V14）。
- 产出层：前 5 章构成合格开篇（ch1 危机+能力+代价立处境、ch2 名单末档立期待、ch3 摊子立住收第一笔钱完成第一兑现）；兑现密度分布合理（短线 4–5 章、中线 12–18 章、h1 在高潮章 23 兑现）。
- 三处主要缺陷：**ch25/ch27 同夜事件跨卷重复（V1，high，执笔必卡）**；vol-1 中段 ch11–16 四次同型微循环且 ch16 与 ch7 同型（V11）；ch17 synopsis 整句重复凑字（V10，硬字数下限诱发）。另 h3 长线 38 章间隔仅 1 次 hook_refs 再提，维系密度偏低（V26）。

### 首章试读

**结论：留读。会点开第二章；唯一真出戏是印在正文里的〔秦姨〕场景标题，修掉就是一篇干净有嚼头的市井开章。**

- 前 300 字内「全巷黑了、黑了三年的窗台亮起一点蓝」把钩子立住；主角是谁（常亮）、要什么（呼吸机不断电→把电当营生）、阻碍是什么（错峰制度、马六八块垄断、二十度体力上限、暴露即造谣）在三千四百字内全部落地，账目细节前后自洽。
- 对照章纲逐项兑现：synopsis 九要点、beat「第一次分电给外人救冰柜被秦姨看破」、ending「摊子的种子埋下」、required 伏笔 h1、knowledge qin-yi→suspected、clock+2，引擎 drift_check=clean；结尾「两块。他心道，我来。」四线蓄力（秦姨守口、冰柜闲话、马六翻牌、开摊宣言）。
- 三处保留：〔秦姨〕场景标题直接印在正文流出戏一次（V15，medium）；开篇约 280 字白描铺陈、主角 311 字才露名，压线达标（V27）；能力来源+代价+保密动机一段灌完，节奏陡平（V28）。

---

## 流程薄弱点与改进建议（按优先级）

1. **P0｜卷间边界检查位（对症 V1＋V13）**：在卷纲待认可看板增加（或升级为 blocker）「前卷卷尾已叙述/消费的事件不得在后卷开场重述」检查——比对相邻卷 arc 卷末/开局与末卷尾章/次卷首章 synopsis 的事件重叠。依据：本轮唯一 high 即落于此缺口，且后果是硬性的（执笔两章必有一章无法按纲落笔）；现有两条 advisory 明确不覆盖此形状，V1 已复现 verified。
2. **P1｜id 前缀口径统一（对症 V2＋V29）**：要么统一世界模型 characters 的 id 约定（去 char- 前缀或全链一致），要么让卷级 volume_reference 校验同时认 contract.entities 与 state.entities（与 narrative.md 的文字描述对齐）。依据：两级判据不一致在实跑中直接造成一次 14 条 blocker 的拒收轮，且主角 id 起草错误同类复发（V29），是引擎侧唯一的 medium。
3. **P1｜节奏方法层补三个空档（对症 V8/V9/V11/V12）**：①开书节增「开卷前 N 章须完成主角处境与第一个可见兑现」提示项（advisory 级即可）；②卷级五条结构纪律增章级对应物（至少「同型化解不连用」）；③断章钩子给结构化位置（如章纲 ending 的外推字段）或评审位；④中段检查位（伏笔窗口两端聚集无兑现、转折堆卷首卷尾夹空腰）。依据：14 条 pacing 中 10 条集中于此三个空档；本产出合格开篇与中段不塌均属设计者手感，方法不保证可复制性——下一本换人执笔即可能塌。
4. **P2｜文档口径修复（对症 V3/V4/V5/V6/V20/V21/V22/V23）**：architecture.md:267 的 continuity 默认值改为与六处文档一致；protocol.md:5 outcome 枚举补 volume_confirmation_required（本轮实跑已命中该 outcome）；narrative.md 章纲回执形状补 story_events/reader_effect/timeline 三字段及 timeline 声明义务；brief.md 的 contract.placements 条补「地点 id 须先在 contract.places 登记」；dispatch.md 的「两包都要读」措辞对齐实际分布；craft.md:71 改 scene_context/scene_sources 写法；README references/ 清单补两个 volume-blueprint 文件。依据：全部为低成本一处改动，其中 V3（口径相反）与 V4（权威页缺项）会直接误导主控决策。
5. **P2｜synopsis 硬字数下限重审（对症 V10）**：字数下限（90 字）诱发整句重复凑字——考虑改为「下限＋重复句/注水检测」或放宽容差并在 quality 指南写明「宁缺毋凑」。依据：ch17 实例已证伤害路径，且 ch18/ch20/ch26 恰 90 压线说明压线写作常态化。
6. **P3｜结构表达字段启用或裁撤（对症 V14）**：beats/pacing/scenes 在产出中 50/50 全空、role 9/50——要么给 pacing 定义可用键与语义（拍序/场景质感的结构表达），要么从模板裁撤减少回执噪音。依据：字段形同虚设会持续诱使 Worker 视其为可选项，结构表达层不落地。
7. **P3｜委托自决通道（对症 V7）**：opening.md 增「作者显式委托时按委托原话自决并逐门登记决定」的通道，承接 chief-editor 已支持的委托开书。依据：跨技能交接场景已实际存在（chief-editor→novel-ledger），当前文档让主干在该场景只有「逐门停等」或「违反边界」两条路。
8. **P3｜引擎小修（对症 V16/V17）**：regroup 成功后同步刷新 work/board.md 与 last-advance.json（或在返回 JSON 里带新板面）；status 返回体补 book_view.path。依据：均为低频但会直接误导主控的展示层问题（旧板面/失效 hash 转发作者、恢复场景拿不到预览入口）。
9. **P3｜命名与展示（对症 V19/V24）**：确认或裁撤 volume-blueprint（当前 v1.2 未接入即被 craft.md 以「可用语气」引用），或在 craft.md:21 把「先给用法再宣布不可用」的顺序倒转。依据：新读者迷路点，且『蓝图』撞名已在两处文档造成指代歧义。

---

## 未覆盖范围

本轮验证未覆盖以下范围（源自各阶段与评审的未覆盖申报，结论边界以此为准）：

1. **真实多会话 Worker 派工、租约交接与 watch 等待**：本次在单会话内以主干自执模拟（prepare-worker 登记主干代理身份，一个会话依次绑定各任务）；多 Worker 并行、租约真实到期交接（300s/3600s 两档的实际超时行为）、watch 阻塞等待与唤醒路径未走到。ownerToken 仅在首章阶段产生（908fba76…，租约 300s），其过期重认领路径未验证。
2. **无人值守快速分组连写（run --fast）与完本交付链**：writing_mode=standard、writing_batch_chapters=5 虽已配置，但正文只写到第 1 章；快速分组连写的组界冻结、组内无人值守推进、pin-engine 固定副本切换、完本交付（finish 状态到达、终稿导出）全链未执行。
3. **第二章起的连续状态链执行、伏笔兑现与跨卷闭合**：章纲层的 50 章状态链经卷内逐章模拟校验，但正文层逐章执行（enter/exit 增量、clock 推进、hook_due 到期提醒、跨卷闭合）无数据；V1 的 ch25/ch27 冲突将在该范围实际爆发，届时须先修订章纲。
4. **文学质量终判**：机械校验通过不等于文学质量（技能自身声明）；首章试读仅一名评审视角的留读结论，文风档案（references/styles/ 五个内置档案正文）、真实读者留存数据、完本质量均不在本轮范围。另：文档审查未逐条核对 volume-blueprint.md 卷 1–9 的 BP 条目表（仅抽样），未运行测试套件与 measure.py（评审限定只读）；章纲评审未逐块还原 documents 表 CAS 链式存储的章纲文档全文（以 tasks 表 result/input 与引擎 status 交叉确认代替）。

---

## 交付文件清单（本目录）

| 文件 | 内容 |
|------|------|
| report.md | 本报告 |
| outlines.md | 两卷卷纲＋50 章章纲全文副本（来源任务 2c198a12…，只读序列化） |
| chapter1.md | 首章《半格电》正文全文副本（来源任务 5bbc81b8…/prose.txt，逐字复制） |
| decisions.md | 作者代理决定清单（22 条，五阶段汇总） |
