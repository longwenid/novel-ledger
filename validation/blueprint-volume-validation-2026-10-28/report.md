# 蓝图卷纲验证报告（2026-10-28）

> **验证对象**：novel-ledger「蓝图卷纲」链路——13 门开书 → 世界与约定 → 蓝图接入 → 六卷卷纲设计。**核心问题：按蓝图产出的卷纲是否足以支撑起点/番茄丰富度。**
> **项目**：`C:/Users/longwen/.zcode/novel-ledger-blueprint-validation`（t3 标准档：6 卷/约 180 章/45–81 万字，书名《这条街不卖》）；引擎 2.1.2，运行一律经固定副本 `C:/Users/longwen/.zcode/novel-ledger-runtime-bpv`（pin 自 HEAD 10ed917）。
> **材料来源**：四阶段实跑记录与交接信息（含引擎命令原始输出）、逐卷评估六份、书级评审两份、分诊合并（42 条原始 finding → 22 条）与独立复核结论（V1–V11 全部 verified）。本报告撰写时另行只读提取了 `work/65d479c9…/result.json` 六卷全文（逐字副本见同目录 volumes.md，JSON 反解比对一致；每卷汉字数按引擎口径复算得 2236/2105/2088/2075/2094/2124，与交接实测逐字一致）。

## 执行摘要

**一、跑到哪。** 链路整体跑通到作者边界：零输入逐门开书十三门 13/13 落定（selection_hash `e2aaee5b…`）→ 世界模型＋开书约定一次提交激活（world_model 哈希 `5d60c2fe…`、contract 生效哈希 `39d2a8d5…`）→ 结构蓝图「阶段升格-同图深化」绑定 → 六卷卷纲一轮 preflight 修复后一次性 submit accepted/committed，引擎停在作者认可门 **await_volume_confirm**（volumes_hash `30b08f51…`，pending v1–v6；分诊经固定副本入口复核 status 与交接一致）。全书尚无章纲与正文（accepted_chapters=0）。

**二、蓝图怎么接入。** 两层蓝图一通一断：

- **结构层（引擎系统）完全接线**：`blueprint --name 阶段升格-同图深化` 绑定后，新任务 required 增列 blueprint、brief.md 自带「## 结构蓝图（作者选定）」节，Worker 冻结材料即可见，无需带话。
- **设计层（plot-distill《卷纲设计蓝图》v1.2，作者代理确认落盘项目根，sha256 `ee5c065c…`）全程未走引擎通道**（V1，本轮唯一 high）：内置设计层目录空置 → 无档可绑 → status `design_blueprint=null` → 派工不携带 record/guide；冻结任务材料（brief/dispatch/task.json/guides 清单）零指针，Worker 发现它完全靠主干派工带话；实际供给走 bridge v1.5 已正式作废的「项目根文件存在即生效」旁路（手工副本＋写手自行读取，build_result.py 自述证实）。章纲阶段（逐卷独立派工）将继承同一缺口。

**三、总体丰富度结论。** 按蓝图产出的六卷卷纲**足以支撑**起点/番茄主流长篇的内容生产（详见 §蓝图→卷纲支撑力结论）：六卷派生结论五卷「充分」、卷4「勉强」（发明集中在对手/班底选角，主线设计权未失）；起点分 5/5/4.5/4/4/5（均 4.6）、番茄分 4/4/4/3.5/4/3.5（均 3.8）。短板不在结构框架（转折位/伏笔账/卷界承接/反模式全过），而在**人物供给**（对手与班底具名人物缺失贯穿五卷）与**叙述面微形状收敛**。

**四、最严重三条问题。**

1. **V1（high·design）**：设计蓝图接入全程未走引擎设计层通道，供给靠已作废旁路＋派工带话，文档口径与项目内确认事实矛盾，章纲阶段将继承同一缺口。
2. **V6/V7（medium·material）**：世界模型仅六具名人物，五卷对手戏与班底戏的具名对手/盟友大量只有机构级或绰号级指认，章纲均须 new_entities 现造（两条合并吸收 13 条原始记录）。
3. **V2/V4（medium·engine/material，同根）**：技能仓并行未提交改动贯穿运行与评审全程——运行中途 engine_changed 中断开书（hatch.md +21/-2）、评审中蓝图 v1.2 全量（749 行）被并行替换为 36 行浓缩自查单 v2c，三副本并存无哈希绑定，漂移已现实化且分诊时仍在变。

## 实跑记录

### 阶段1｜零输入逐门开书（init + 13 门）

- **操作类别**：`init --source` 保存作者委托原话（opening_basis）；十三门逐门 submit（选项＋理由）/choose/advance；scale 门 `choose --tier t3` 直达标准档。
- **结果**：✅ 13/13 落定，opening.phase=ready，selection_hash `e2aaee5b…`。已选要点：都市商战经营·老字号守业向／premise「永远差一户」（产权拆碎 vs 连片收购，对抗/制度）／主角陆知非（评估行六年归乡、收购名单有他签名）／对手城建资本链（周慎行→评估行→城更集团→基金）／书名《这条街不卖》。中途 1 次 engine_changed 中断（见卡点），按引擎给出的 pin-engine 路径固定 HEAD 10ed917 发布副本续跑，未丢数据（12 个门任务与 world_model/volume_outline 均 done，result.json 候选完整保留）。
- **作者边界点**：①委托自决通道启用——作者全权委托在案，委托只覆盖十三门选择，不延伸到卷纲认可、正文授权与首章定调；②13 门各自边界点（题材/核心设想/体量/世界架构/格局路径/视角/来历/核心优势/主角处境/对抗网络/关系/兑现/书名）逐门以作者代理身份自决并登记来源；③engine_changed 恢复路线——选 pin-engine 固定副本（不走需作者升级授权的 recover-engine、不还原开发目录），尊重引擎冻结纪律。
- **卡点原文摘录**：title 门 submit 返回 `{"error":"engine_changed","frozen_build":{"engine_hash":"f7671635…","rules_hash":"f7c47821…"},"current_build":{"rules_hash":"420984a4…"}}`；触发源 `git status --short → M references/hatch.md`（+21/−2，外部未提交改动，非本会话所为；复核证实工作树当时即「10ed917＋hatch.md 未提交」，该改动事后被提交为 950ae49）。

### 阶段2｜世界与约定（world_model＋opening_contract，同一任务两阶段）

- **操作类别**：spawn Worker 子代理读冻结材料起草 → preflight → submit；提交被采纳后以主干身份执行一次 advance 激活约定。
- **结果**：✅ 首轮通过机械校验并同事务采纳（accepted/committed/persisted=true，findings=[]），世界模型 12 领域落库（world.json 73178B，model_hash `5d60c2fe…`），约定生效哈希 `39d2a8d5…`，引擎进入 volume_outline task_ready。
- **作者边界点**：①Worker 身份准备——派工侧未注入凭据，Worker 以兼任主干身份补做 prepare-worker（`--task 887af32c… --session world-builder-887af32c --seconds 21600`）；②约定激活与推进——advance 属委托范围内推进而非新授权；③门内仅有称谓的人物命名——师父=温守成、马主任=马长青（role 注明街坊口中的马主任）、评估行=恒准评估行，专名逐字沿用后续勿改写。
- **卡点原文摘录**：`bash echo "NOVEL_TASK_ID=[$NOVEL_TASK_ID]"` → `NOVEL_TASK_ID=[]`（空）；提交前 task.json `execution.state="await_worker_identity"`、`claim=null`——按 dispatch.md 无凭据调用 worker 命令计身份技术失败（limit=2）。

### 阶段3｜蓝图接线（设计蓝图确认＋结构蓝图绑定）

- **操作类别**：设计蓝图作者确认——`cp references/volume-blueprint.md → 项目根/卷纲设计蓝图.md`，sha256 双端一致（`ee5c065cc73d…`，92702B），走 craft.md:23「作者确认并选定」路径；结构层 `blueprint --name 阶段升格-同图深化 --source …`（--source 存作者原话）；重跑 advance 恢复卷纲任务。
- **结果**：⚠️ 一通一断。**结构层完全接线**：新任务 65d479c9… required 增列 blueprint、brief.md:14 自带「## 结构蓝图（作者选定：阶段升格-同图深化）」节（骨架/推进维度/卷间纠缠/边界），Worker 冻结材料即可见。**设计层无通道可走**：内置设计层目录空置 → 无档可绑 → status `design_blueprint=null`，冻结材料零指针，Worker 只能靠派工带话（build_result.py:2 自述「按《卷纲设计蓝图》v1.2＋桥接映射 19 行表起草」证实旁路供给）。另：blueprint 绑定静默撤销了未认领的 pending 卷纲任务（redispatch_count:1），须自知重跑 advance 才恢复就绪（V12）。
- **作者边界点**：①**设计蓝图确认**——plot-distill《卷纲设计蓝图》v1.2 是否作为本书设计蓝图生效：确认全文原样生效（理由：作者全权委托验证运行，验证目标就是蓝图接入链路，v1.2 是当前唯一候选版本）；②**结构蓝图绑定**——五档选一：绑「阶段升格-同图深化」（理由：与冻结开书选择逐点对位——单街不换图/四级阶梯逐级升格/旧冲突后果参与新对抗；复仇反推/双层揭秘/多线交错与「一人守街」限知单主角＋守业（非复仇）题材不符）。
- **卡点原文摘录**：runtime craft.md:23「当前是 v1.2 **待作者确认稿**……确认前不供写作项目使用」；volume-blueprint.md:6「**本版仍待作者确认，确认前不得供 novel-ledger 写作项目使用**」；bridge.md:53「以下机制均为后续建议，未实现前不能宣称已生效」——三处口径与项目内已确认事实（decisions doc 7ddfb9951e「同时确认…作为本书设计蓝图」）矛盾，且确认事件无任何登记位置。

### 阶段4｜卷纲（volume_outline·t3 六卷 all 一次性交付）

- **操作类别**：Worker（volume-designer-65d479c9）按设计蓝图 v1.2＋bridge §一 19 行字段映射起草六卷，构建脚本自测（禁词/id 唯一/窗口/时钟累计）三轮后 preflight/submit；主干 advance 物化 board。
- **结果**：✅ 第二轮 preflight valid 零 findings，一次 submit 即 accepted/committed（outcome=volume_confirmation_required），引擎停在作者认可门 await_volume_confirm（round=0，volumes_hash `30b08f51…`，pending v1–v6）。终值每卷汉字数 v1=2236/v2=2105/v3=2088/v4=2075/v5=2094/v6=2124（带 2000–3000，本报告已按引擎口径独立复算一致）。引擎发 5 条「卷间边界重叠」advisory（只警不拦；「卷间纠缠缺位/转折位置模板同构/卷中空腰/伏笔中段无活动」均未触发）。
- **作者边界点**：①作者认可门——机械校验通过只证明链路可用，认可判断交后续独立评估，本验证不代行 confirm-volume/revise-volume；②advisory 处置边界——5 条只警不拦，不据此代行修订，advisory 原文随 handoff 全文移交（其中共同名词多为 BP-5.1 式卷尾钩直兑的刻意承接，是否需后卷开场改承接后果属文学判断）。
- **卡点原文摘录**：首轮 preflight `{"outcome":"repair_required","error":"design_drift","findings":[… 6 条 criterion=volume_length（expect [2000,3000]，got v1=1767/v2=1611/v3=1605/v4=1553/v5=1471/v6=1575）]}`；read 首次调用 `{"error":"session","message":"须提供真实宿主会话身份 session。",…failures:1/limit 2}` → 二次 `technical_blocked`（按 runtime.md:200 替代通道 `--session/--execution-claim` 恢复后 read/submit 全程无再失败）。

## 逐卷评估

| 卷号 | 派生结论 | 承重发明数 | 起点分 | 番茄分 | 一句依据 |
|---|---|---|---|---|---|
| 卷1 | 充分 | 4 | 5 | 4 | 前 10 章逐章排 beats 零主线发明，4 件全是 new_entities 具名登记级（不承重），抬价报告/征询程序/时限/家规等机制均有供给 |
| 卷2 | 充分 | 4 | 5 | 4 | 四件发明全是「已定角色的铸形」（对手功能/手法/结局均被钉死，只补名字与场面），主线零让渡；开卷 31–38 摸底段对快更口径偏缓 |
| 卷3 | 充分 | 3 | 4.5 | 4 | 三件发明为补面孔/补班底/补程序桥不挤占主线；恒准侧全卷无具名人物，长线人物对抗记忆点独压苏晓线 |
| 卷4 | 勉强 | 6 | 4 | 3.5 | 发明集中在主线对手侧——操盘手占 94–118 对抗主干位、五家老字号群像占 required 主节点约一半戏份，连续性要靠章纲现补 |
| 卷5 | 充分 | 4 | 4 | 4 | 四条发明全是支干填充，断供战打法/三户落法/样板对冲/临终托付等主线设计权未失；122 后对抗全机构化，「人对人」张力材料薄 |
| 卷6 | 充分 | 4 | 5 | 3.5 | 四处承重发明均属选角层（给已写好的角色位起名立档），走向/筹码/条款级攻防仍在卷纲；开卷前 12 章对手第一手动作材料最早落在 163 |

均值：起点 4.6、番茄 3.8。（各卷评估均以章纲设计员身份做前 10 章逐章派生测试；「承重发明」指章纲必须 new_entities 现造、且落在主线对抗位上的材料。）

### 各卷承重发明清单

**卷1（4 件）**

1. 酱菜坛第一户的具名人物档案——第 8–10 章中型兑现的对手戏主体，材料只给绰号级指认（arc「最动摇的第一户（酱菜坛那家）」）；
2. 抬价报告的具名签署人（评估行经理）——第 16 章口径比对与第 22–26 章高潮「评估行经理念完抬价报告」的念稿者需具名与立场；
3. 周慎行项目组的一线执行者——逐户上门报价、挂牌拍照的具名业务员；
4. 街口原百货大楼（样板间）的地点登记——n1a 与第 9 章剪彩的攻防舞台，geography 六条中无此条目。

**卷2（4 件）**

1. 二房东具名人物——n2c「拆解囤租网络」的对手靶子、56–58 资金链崩断跑路与门禁卡丢赌桌的当事人，手法与结局已钉死但无名字无面目；
2. 白手套债主——h5 载体「欠条落款是收购网络的白手套」与 42–54「债主一回回上门」的出场对手，材料只有功能位；
3. 何伯之子——turn 45「何伯家中先裂」与 exit_state「儿子离家躲债」的当事人，债务软肋既埋但名字/欠债缘由/父子相处方式须自铸；
4. 批发市场第一层转包户焦点户（半承重）——38–40「守住第一层转包户」中型兑现的落点人脸，可群像可聚焦。

**卷3（3 件）**

1. 恒准评估行侧具名对手（报告签发人/评估负责人/竞业诉讼代理）——61 章报告扉页起正面交锋、67 退件、74 对峙、84–88 理事会摊牌都需要一张可出场的脸；
2. 行会改组线场景班底（理事长/现任理事/五家老字号掌柜的姓名立场）——n3d（83–90）与 h9 五家联署条款的章级执行全靠发明（v4 联署线同样依赖）；
3. 「理事会→评估行撤回重评」的程序桥——climax 与 n3d 给了结果未给链路：行会无对评估报告的处置权供给，凭谁受理/谁有权要求须章纲拼装。

**卷4（6 件）**

1. 基金操盘手的人物实体（姓名/来历/与基金汇报线）——承担 t12 程序攻防 94–118 章的对手主干位，世界只有机构档案 fac-jijin；
2. 五家老字号中四家的名号与东家群像（含「念旧情/开价码」的具体人设与价码内容）——修鞋/酱菜/理发为租摊商户口径，够不上 rul-shangshi「三代传承」认定；
3. 经办科室把关人具体人物与「技术性理由」实例清单——n4d（103–115，required hidden）只有机制描述无人物与理由样本；
4. 听证会「谁代表老街」一问的发问者身份（评审专家/基金律师/主持人）——113–118 听证章须指派；
5. 电视民生栏目与记者（t15 叙事权线载体）——arc 明示采访与剪辑失真，栏目名与对话方缺位；
6. 公开产业关联风波的攻击发起方（「有人拿这个做文章」的有人）——中段节拍三件套之一的对抗落点身份未指。

**卷5（4 件）**

1. 银行/信托侧可指认的谈判对手人物——「银行的谈判桌」为三桌主戏之一而对手全为机构（信托骑缝章/银行/中介），金融层只有机构条目 fac-jijin；
2. 理发转灯、酱菜坛两户的具名掌柜与家庭处境——三户落法是 n5a 主线（121–135），两户在世界模型仅街景罗列一句；
3. 「清河街模式」样板评审的程序机制——n5b 只给「入围初评/拿入围函换展期」两级锚点，主办方与申报—初评—答辩规则须沿 rul-gongshi 四道关类比自建；
4. 断供三户贷款数额、互助金池与过桥周转的明码账目——卷纲只给主角侧存款 120000→70000，三户的债与过冬的具体账须章纲发明。

**卷6（4 件）**

1. 基金方主谈人＋律师团主笔的实体档案（名/小传/欲望/边界）——n6b（163–176）14 章三方谈判主战场对手需 new_entities 白手起家；
2. 政府方主谈人——三方桌政府侧（市级旧改办/住建口径）无实体（只有街道办马长青），「三方各派两人」的政府两张脸零供给；
3. 何伯之子——he-bo 卷终值「看儿子接铺」与 n6d「各归其位」的承载者，无名无档案；
4. 删页真相的史实人物（师门祖师/基金前身老股东·删页经手人）——h12 兑现（168–175）的恩怨史实层只有「守街不守财」族谱批注一句。

## 书级评审

### 跨卷承接

**材料基础**：result.json 六卷全文逐字段核对＋独立复算（只读）——stage 序列逐字等于 world_ladder 取值且只升不降；node/thread/hook id 全书唯一；hook 窗口跨卷自洽（payoff≥plant、越卷均 continues 且非 required）；clock 累计 120→1080 连续；银行存款链 420000→60000 六卷逐卷衔接；每卷汉字数全落 2000–3000 带。

**结论**：六卷作为全书结构足以支撑起点式长线追读——阶梯沿 world_ladder 只升不降且每级 new_rule 有事件钉位（家规→联盟成军→执委当选→三方章程），两次同级卷各有真战场；五处卷界全部「受力点→开局直兑＋消化窗」落地（BP-5.1–5.4 逐条可核），引擎 5 条边界警示经逐条对勘均为承接后果而非重演当夜；中段 v3/v4 有新对手与新回报非重复升级；两条超长伏笔（h2 约 120 章、h8 约 95 章）靠公约族每卷保温，等待成本可控。**风险不在框架而在材料/节奏缝合**：v3 遗留竞业诉讼断档（V9）、v1↔v3 卷尾高潮机制同型（V11）、设计层指针空置（V1）；另有 t4 联盟制度线登记断档（V10）与 h2 payoff 窗跨卷界（V20）两处派工级缝隙。

### 蓝图符合度

**材料基础**：会话起始读取的 volume-blueprint.md v1.2 全量（749 行：49 条 BP/73 引文/卷10 映射表）与 bridge v1.5（19 行映射逐行）双向核对；产出层 v1/v4/v6 对 41 条正面 BP＋8 反模式逐条人工对照，字数/标签计数/turns/hook id/clock/stage/resources 以 python 脚本实测。

**结论**：「蓝图→卷纲」供给链**在文档层成立、在引擎层尚未真正走通**。19 行映射对回执 18 字段覆盖完整且与蓝图卷10 双向一致（41 条正面 BP 全部入供给列）；产出卷纲对适用 BP 条目采用率极高（约 35+/41 可见，弃用原因全部健康：题材不适用/空白不供给/样本数值不照抄），无误把样本当阈值的实例。但本次供给走的是 bridge v1.5 已作废的「项目根文件」旁路（V1），且评审期间技能仓蓝图被并行替换为 36 行浓缩自查单 v2c（V4）——三副本无绑定漂移已现实化。产出面真正的丰富度短板是微形状收敛（六卷同套方法标签脚手架 V5、恒 3 转折 V13）与资源轴单一（V14），蓝图与现有 advisory 均不观察这类收敛；style.trend 是唯一「引擎必填而蓝图零供给」的回执字段（V15），「默认档偏离须说明理由」机制零行使且无指定落点（V18）。

## 问题清单

> 42 条原始 finding 经分诊合并为 22 条；独立复核对 V1–V11 逐条给出 verdict（全部 **verified**，关键锚点独立复现成立），V12–V22 未入独立复核清单（沿用分诊/阶段证据，其中 V22 分诊期已实跑双入口复核）。severity：high 1 条、medium 10 条、low 11 条。

### design（3 条：V1/V3/V17）

**V1｜severity: high｜复核: verified（六线锚点全部独立复现：grep 计数、文档口径逐字命中、sqlite 决策原文、sha256 一致、HEAD 代码空置、旁路自述；两处小出入不推翻结论）**
- **where**：`novel-ledger-blueprint-validation/work/65d479c9…/{task.json,input.json,brief.md,dispatch.md,read_ref.md,build_result.py}`；`runtime-bpv/references/{craft.md:23,volume-blueprint.md:6,volume-blueprint-bridge.md:53-55}`；novel.sqlite3 decisions（doc 7ddfb9951e）vs status design_blueprint=null。
- **what**：设计蓝图（plot-distill《卷纲设计蓝图》v1.2，作者已确认落盘）的接入全程未走引擎设计层通道：内置设计层目录空置→无档可绑→status design_blueprint=null→派工不携带 record/guide；冻结任务材料（brief/dispatch/task.json/guides 清单）零指针，Worker 发现它完全靠主干派工带话（阶段3、阶段4、跨卷承接、蓝图符合度四面记录互证）；Worker 经 guides 可读的 craft.md/volume-blueprint.md 口径仍是「待确认稿/确认前不得使用」且确认事件无任何登记位置（文档自述与项目内已确认事实矛盾）；实际供给走 bridge v1.5 已正式作废的「项目根文件存在即生效」旁路（手工副本＋写手自行读取），设计层派工通道（record design_blueprint＋整本 guide）本次验证零行使，章纲阶段（逐卷独立派工）将继承同一缺口。
- **证据摘录**：`grep -c "卷纲设计蓝图" {task.json,input.json,brief.md,dispatch.md,read_pack.md}` → 0/0/0/0/0（read_ref.md 3 处命中均为绑定 source 原话、无路径指针）；task.json guides 仅 hatch/editorial/workbench/protocol/craft 五件；status → `"design_blueprint": null, "structure_blueprint": "阶段升格-同图深化"`；decisions 原文「同时确认…作为本书设计蓝图」；项目根 卷纲设计蓝图.md sha256=`ee5c065cc73d…` 与决策声明一致；git HEAD(3169123) contracts.py `DESIGN_BLUEPRINT_CATALOG={}` 空置，runtime-bpv 引擎快照（10-28 22:15）早于设计层代码提交（10-29 00:02）——运行期确无引擎通道；build_result.py:2 自述「按《卷纲设计蓝图》v1.2＋桥接映射 19 行表起草」。

**V3｜severity: medium｜复核: verified（四线独立复现：本人即同款 spawn 子代理复现空环境变量；journal 仅一次失败；引擎源码链逐项属实）**
- **where**：workflow 派工步骤（task 887af32c… 与 65d479c9… 的 dispatch；对照 work/…/dispatch.md 第1节与 runtime.md:193-198）；阶段4 commands.read 首次调用。
- **what**：派工只 spawn Worker 子代理、未按引擎协议先 prepare-worker 注入凭据（NOVEL_TASK_ID/NOVEL_SESSION 均空、identity_registered=false）——阶段2 靠 Worker 兼任主干补做 prepare-worker 才能读材料；阶段4 同一缺陷再次现实化：首次无凭据调用即失败并烧掉两次技术失败额度之一（failures=1/limit 2，随即 technical_blocked），需 `--reset-failures`＋显式 `--session/--execution-claim` 恢复。按文档属预期行为，但误用成本高；后续 workflow 脚本派 Worker 前应加 prepare-worker 并把 worker_env 传入子代理。
- **证据摘录**：`echo "NOVEL_TASK_ID=[$NOVEL_TASK_ID]"` → `[]`；journal：任务 887af32c 仅 worker_prepared（Worker 自取会话名），任务 65d479c9 为 prepare→id=81 `worker_failure{code:session,failures:1,blocked:true,operation:read,session:null}`→再 prepare→worker_recovered→read/submit 成功（全库仅此一次失败）；application.py:411/:311-313/:298-299、contracts.py:733/:89（technical_retries=2）逐项属实。

**V17｜severity: low｜未独立复核**
- **where**：read_ref.md ## blueprint skeleton vs result.json stage 序列。
- **what**：结构层骨架文本「每卷沿已选格局阶梯升一级」与实际 6 卷 4 级序列（守铺人→街面主事×2→行业执委×2→城市合伙人）矛盾：BP-1.4/1.6 明确允许平台期、引擎只强制只升不降，但被派工的骨架文本过度承诺，作者侧无任何提示 reconcile。
- **证据摘录**：input.json payload.structure_blueprint.skeleton 原文「每卷沿已选格局阶梯升一级」；实测 stage 序列 `['守铺人','街面主事','街面主事','行业执委','行业执委','城市合伙人']`；BP-1.6 断言「也不要求每卷升阶」。

### engine（3 条：V2/V12/V22）

**V2｜severity: medium｜复核: verified（哈希变迁链完整复现：内存重算 clean-tree rules_hash 10ed917→f7c47821…、950ae49→420984a4…，diff 恰为 hatch.md +21/-2，证明报错时工作树即「10ed917＋hatch.md 未提交」）**
- **where**：`C:/Users/longwen/.zcode/skills/novel-ledger/references/hatch.md`（运行中途外部未提交改动）；触发点：title 门 submit（task 42791f34259f4eefab451764ff69e345）。
- **what**：开书运行中途技能仓库被外部未提交改动（references/hatch.md +21/-2），rules_hash 从 f7c47821… 变 420984a4…，title 门 submit/advance 报 engine_changed 中断流程；引擎按设计冻结并给出 pin_engine 恢复路径（固定 HEAD 10ed917 发布副本续跑全程通过），未丢数据。与 V4（蓝图版本漂移）同根——并行未提交改动持续存在于技能仓，分诊复核时已扩至 10 文件（+80/−761，含 contracts.py、test_volume_gate.py）。
- **证据摘录**：submit → `{"error":"engine_changed","frozen_build":{"rules_hash":"f7c47821…"},"current_build":{"rules_hash":"420984a4…"}}`；`git status --short → M references/hatch.md`（diff --stat +21/-2）；`pin-engine --ref 10ed917 --output …novel-ledger-runtime-bpv` → build rules_hash 与冻结一致、source_matches_runtime=true，换 ROOT 后全通过。

**V12｜severity: low｜未独立复核**
- **where**：blueprint 命令行为（无 --regenerate 的普通绑定）。
- **what**：blueprint 绑定会静默撤销未认领的 pending 卷纲任务——--regenerate 的各卷重派语义扩散到普通绑定，命令输出不提示，主干须自知重跑 advance 才恢复 volume_outline 就绪态。
- **证据摘录**：`blueprint --name 阶段升格-同图深化 --source …` → `{"blueprint":"阶段升格-同图深化","regenerated":false,"removed_volumes":[]}`；紧接 status → `pending_task:null`、`stage:null`；`advance --compact` → task_ready 新 task 65d479c9…、redispatch_count:1；hatch.md:163 只对 --regenerate 提及重派。

**V22｜severity: low｜未独立复核（分诊期已实跑双入口复核）**
- **where**：novel.py status 的 engine 块（frozen/matches 字段）；引擎终态证据采集命令。
- **what**：status 的 engine 块对入口/版本错位无鉴别力（frozen 恒 null 不展示冻结基线、matches 恒 true），且本轮「引擎终态」证据即经开发树入口采集：其 current 哈希（0632bcd9…/1504b33d…）非运行时固定副本的冻结对（f7671635…/f7c47821…），从 status 输出无法察觉这一错位（与 V2/V4 环境漂移互证）。
- **证据摘录**：固定副本入口 status → current `f7671635…/f7c47821…`（与全部 handoff 冻结值一致）、frozen:null、matches:true；开发树入口 → current `08dbe75d…/5b185cd5…`（第三套哈希）、仍 frozen:null/matches:true。

### material（8 条：V4/V6/V7/V8/V9/V10/V15/V16）

**V4｜severity: medium｜复核: verified（且分诊后状态继续演进：bridge v1.6→v1.7、contracts.py 设计层目录已登记首档「五书基准」——「仍在变」的更强证据）**
- **where**：`novel-ledger/references/volume-blueprint.md` 与 `volume-blueprint-bridge.md`（会话中途出现的未提交改动，分诊时仍在）。
- **what**：蓝图版本漂移在评审进行中现实化：技能仓全量 v1.2（749 行）被并行未提交改动替换为 36 行浓缩自查单 v2c（plot-distill.blueprint.v2c，2026-10-29；bridge 同步 v1.6），与验证项目根的 v1.2 全量副本、plot-distill 技能根存档三处并存；设计层无引擎哈希绑定（目录空置，见 V1；分诊时目录条目仅 name/file/summary/version 字符串无内容哈希），多副本一致性只靠人工纪律。
- **证据摘录**：`wc -l` → volume-blueprint.md=36（头两行「# 卷纲设计蓝图·浓缩自查单／版本：plot-distill.blueprint.v2c（v2-condensed，2026-10-29）」）、bridge=126；`git show HEAD` 同文件=749 行 v1.2；项目根副本（v1.2/747 行）与 plot-distill 技能根（v1.2/749 行）并存；git 未提交改动已扩至 10 文件（含 contracts.py/test_volume_gate.py/run_tests.py）。

**V6｜severity: medium｜复核: verified**
- **where**：卷3/characters·nodes(n3a 61-70, n3b 66-82)；卷4/characters（基金操盘手）；卷5/characters+factions（银行/信托）；卷6/n6b（基金主谈/律师团＋政府主谈）；卷1/arc+n1b+climax（评估行经理、项目组执行者，不承重）。
- **what**：世界模型 characters 仅六实体（lu-zhifei/wen-shoucheng/he-bo/su-xiao/zhou-shenxing/ma-changqing），各卷对手戏的具名对手大量只有机构级/绰号级指认、章纲均须 new_entities 现造（五卷独立记录互证的同一供给缺口）：v3 主线对手恒准评估行全卷无具名人物（报告签发人/竞业代理/档案经办，前 10 章正面交锋即需发明）；v4 基金操盘手承担 94–118 对抗主干位仅 arc 侧写（「不喝酒、不看街、只看模型」）；v5 断供战主戏「银行的谈判桌」无具名对手（122 后周慎行下场、后半卷对抗全机构化）；v6 n6b 14 章三方谈判主战场的基金主谈/律师团与政府主谈无名无档案；v1 评估行经理/项目组执行者为绰号级但不承重。
- **证据摘录**：world.json 与已入库 world 任务 characters 均恰六人；factions 仅 5 条机构条目（fac-pinggu「资质、数据与口径」、fac-jijin「能换操盘手、能等政策」引文逐字核对一致）；result.json v3.characters 仅 [lu-zhifei,su-xiao]、v4 仅 [lu-zhifei,ma-changqing]；contracts.py:679 证实 chapter_outline 契约带 new_entities 字段。

**V7｜severity: medium｜复核: verified（七组证据引文与字段全部独立复现；v4 承重成立——required main 跨 91-102 且 h9/t10 跨卷依赖）**
- **where**：卷4/nodes.n4a＋characters（承重）；卷3/nodes(n3d)·hooks(h9)·threads(t10)；卷4/nodes.n4d 与 arc 选择与代价段；卷5/nodes n5a（121-135 三户落法）；卷6/h12 payoff（168-175）与 n6d；卷1/arc+n1b。
- **what**：盟友/班底/史实人物零登记（跨卷印证的同一缺口）：v4 五家老字号除聚顺堂外零个体材料（91–102 required main 节点约一半戏份——四家东家与价码内容——须章纲现造，修鞋/酱菜/理发为租摊商户口径够不上 rul-shangshi 三代传承认定）；v3 行会改组线班底（理事长/现任理事/五家掌柜）无姓名立场、v4 联署线同样依赖；v4 把关人经办人物与「技术性理由」实例清单、公开产业关联风波攻击发起方（「有人拿这个做文章」的有人）身份未指认；v5 断供三户中理发转灯/酱菜坛两户无具名掌柜与处境；v6 删页真相史实人物（师门祖师/基金前身老股东·删页经手人）与何伯之子（接铺终值承载者）无名无档案；v1 酱菜坛第一户与街口原百货大楼（样板间攻防舞台）未入 geography。
- **证据摘录**：world characters 六人无上述任一条目（全库「理事长」0 次；何伯档案散文 4 次「儿子」无条目）；rul-shangshi limits 逐字含「行会只管行业身份，不管产权」；v4 arc 逐字含「有人念旧情，有人开价码」、n4a={main,required:true,window:[91,102]}；v6「三方各派两人，钢笔是借的」逐字在 arc 而政府侧仅 fac-zhixu 聚合＋街道干事马长青；v1 geography 恰六条无百货大楼。

**V8｜severity: medium｜复核: verified（对 world.json 全部 55 条目与冻结参考做关键词全扫：撤回/重评/复核/申报/答辩/入围/初评/主办方全部 0 命中）**
- **where**：卷3/climax·nodes(n3d 83-90)（理事会→撤回重评程序桥）；卷5/nodes n5b（130-143 样板评审线）。
- **what**：卷纲高潮/对冲载体的程序机制在世界模型无供给、须章纲拼装桥接（同一缺口两处）：v3 卷尾高潮「评估行当场被理事会要求撤回重评」的权限与程序链无供给——行会只被授权认定行规与老字号、无对评估报告的处置权，凭谁受理/谁有权要求须章纲发明；v5「清河街模式」样板评审程序（主办方、申报—初评—答辩规则）无供料，n5b 只给「入围初评/拿入围函换展期」两级锚点、须沿 rul-gongshi 四道关类比自建。
- **证据摘录**：v3 climax 原文；soc-hanghui enforcement=「理事会表决，媒体背书；资本以赞助与改组游说渗透」、rul-shangshi limits、fac-pinggu dependencies=「依赖资本方的委托费生存」（仅半条因果）；rul-gongshi principle 仅覆盖旧改四道关；v5 arc 原文只给「第140章前后样板入围初评」「拿样板评审的入围函换来银行的展期」两级锚点。

**V9｜severity: medium｜复核: verified（按卷块复算 grep：竞业 v3=9 其余卷 0、诉讼 v3=4 其余 0、撤诉/和解全书 0；另补查官司/法庭/起诉/开庭/传票/判决等全书全 0——无换词结算）**
- **where**：v3 exit_state 线路句（result.json:677）；对照 v4 arc/threads/exit_state（result.json:687-910）、v5（920-1123）、v6（1133-1318）。
- **what**：v3 卷末遗留的竞业诉讼（对手对主角已立案的法律对抗）在 v4–v6 全部文本中零次承接或结算：v3 exit_state 明言「竞业诉讼悬而未决」且行会改组/苏晓/股凭三线后卷均有承接登记，唯竞业诉讼无——跨卷断档且非 hook 非 thread，章纲阶段无 id 可挂；v6 exit_state 宣称「全书旧账结清」与此相悖。
- **证据摘录**：v3 exit_state「线路：口径战争收束，行会改组线、苏晓线、股凭暗线跨卷；竞业诉讼悬而未决」；对照 t13 承行会改组、t18 承股凭、苏晓 v4–v6 exit_state 均在；volume-blueprint-bridge.md:31,91 明示跨卷承接靠 arc 排承接＋章纲用原 id，exit_state 散句确无章纲可挂之锚。

**V10｜severity: medium｜复核: verified（v3–v6 四组 threads 逐条读完 t8–t24 共 17 条，无一是联盟制度线承接条目）**
- **where**：v2 threads t4（result.json:311-318）vs v3 threads（529-561）/v4（749-780）/v5（982-1021）/v6（1195-1224）。
- **what**：t4 联盟制度线 v2 continues:true（ending_condition「联盟制度成形并在后续卷滚动扩容」）后 v3–v6 无任何承接 thread——联盟制度演化（互助金→过桥周转→民间联合体→联席会议）只由 arc/nodes 承载；各卷章纲任务的 thread 集合仅限本卷登记，该线无 id 可申报活跃/休眠，属本卷纲自身承接惯例（公约/叙事权/行会/周慎行线均有后卷条目）下的登记断档。
- **证据摘录**：t4 ending_condition 原文与 continues:true；对照 t7→t11（承公约暗线·账房段）、t10→t13（承行会改组线）、t14→t19（承失势线）、t15→t20→t24（叙事权两跳）显式承接；briefs.py:389 章纲规范明文 plot.threads 只引用本卷卷纲已登记 id。

**V15｜severity: low｜未独立复核**
- **where**：references/volume-blueprint.md 卷10 行18／volume-blueprint-bridge.md 行19（会话起始读取版）。
- **what**：style.trend 是唯一「引擎必填而蓝图零供给」的回执字段：19 行映射对 18 个回执字段覆盖完整、41 条正面 BP 全部入供给列，但 style.trend/window 无任何 BP 供给（卷9 S-1 显式空白），该字段供给完全落在作者约定与文风侧。
- **证据摘录**：卷10 行18 蓝图条目列「—（空白）」处理列指 S-1、bridge 行19 BP 来源「—」；产出六卷 style.trend 均非空且相位相关（如 v5「对白降到全书最低」）。

**V16｜severity: low｜未独立复核**
- **where**：卷5/exit_state 苏晓句；卷6/t24 叙事权·定调段。
- **what**：收束终值单句化、无场景/结构承载（同一模式两处，跨卷互证）：v5 exit_state「苏晓开始筹划自立门户」无 thread/node/arc 承载（v5 threads 仅 t16–t20），章纲无抓手需发明场景；v6 t24 ending_condition「清河街模式定调为市级样板」仅结论一句，定调场景与媒体材料须回 v5 样板答辩段复用。
- **证据摘录**：v5 threads 仅 t16-t20 且 characters/结构化终值无 su-xiao 条目；v6 t24 ending_condition 一句原文、arc 尾段仅「批发市场升级方案公示」一笔。

### richness（5 条：V5/V11/V13/V14/V21）

**V5｜severity: medium｜复核: verified（severity=advisory「只警不拦」定性正确；轻微保留：「中型兑现」系 BP-3.1 跨度三分类的作者派生措辞非逐字词汇，归因 7/8 逐字成立）**
- **where**：result.json data.volumes[*].arc（六卷）；work/volume-board.md ## 结构提示（advisory 节）。
- **what**：六卷 arc 共用同一套方法标签脚手架（核心问题/铺垫段/选择与代价/不可逆点/推进维度/中型兑现/结构角色/开局承接 各卷各恰 1 次）：「卷间边界重叠」5 条 advisory 的命中片段一半实为方法词汇跨卷复用而非事件重叙（advisory 的「共同名词」豁免判断成立），另一半是刻意的卷尾钩直兑共同名词；但叙述面因此同构——BP 与 craft 的词汇被逐字当成分段模板，可在章纲或后续修订中靠变化措辞消解（非引擎阻断）。
- **证据摘录**：python 实测六卷 arc 八标签每卷各恰 1 次；volume-board.md:117-122 五条同文案 advisory；15 个命中片段约 8 个为方法/惯用词汇、7 个为卷尾钩直兑名词；五个卷边界的后卷开场逐对核对均为承接后果或钩直兑而非重演当夜。

**V11｜severity: medium｜复核: verified（仅注：v1 卷内只称「评估行」未点名恒准，同一性属跨卷指认——同型结论不动摇）**
- **where**：v1 climax（result.json:27）vs v3 climax（result.json:482）。
- **what**：卷尾高潮机制同型：v1 征询会与 v3 理事会 climax 同为「把自己的底稿与对手报告并排摊开、假设/参数/底稿编号逐条比对掀翻当众」，且两次对手武器同为恒准评估行的报告——中段爽点有同型风险；v3 arc 自辩「与第二卷的组织战不同」但对 v1 未做机制级区分。
- **证据摘录**：两处 climax 原文（行 27/482）；grep 底稿编号 v1=1、v3=2；v3 全卷 0 次提及征询/第一卷/上一卷。

**V13｜severity: low｜未独立复核**
- **where**：result.json data.volumes[*].turns 与 arc。
- **what**：六卷微形状完全收敛且无观察点：每卷恰 3 条 turns、每卷同用「铺垫段→升级→卷尾连落」三段形态；蓝图 BP-2.1 允许合并重排、S-3 不设次数默认，但现有 advisory（恰两条且位置全卷中/卷尾才提示）不覆盖「卷卷同数同形」，蓝图与引擎均不观察这类收敛（与 V5 标签渗漏同源互证）。
- **证据摘录**：实测 turns per volume=[3,3,3,3,3,3]（本报告提取时再次复算一致）；六卷 arc 各含「铺垫段」段 1 次；交接 note 3「转折位置模板同构…未触发」。

**V14｜severity: low｜未独立复核**
- **where**：result.json data.volumes[*].resources。
- **what**：资源轴是六轴中最薄一轴：六卷仅跟踪「银行存款」单一 key 且全为单调消耗型（420000→60000），BP-6.4 三型菜单（积累/消耗重创/失而复得）只用消耗一型，建立卷（v2 联盟）与收官卷亦无积累/回补型资源行；事件绑定齐全（无 8.5 违规）但形态单一。
- **证据摘录**：实测 resources keys={('银行存款',)}、from/to 依次 420000→310000→230000→160000→120000→70000→60000（本报告提取 v1 resources 原文核对一致）；BP-6.4 三型断言原文。

**V21｜severity: low｜未独立复核**
- **where**：preflight（第一轮，result.json 初稿）。
- **what**：卷纲初稿每卷汉字数不足（v1=1767…v5=1471，低于 2000 下限），被 preflight 以 6 条 volume_length blocker 整体拒回；按蓝图因果链逐卷扩充 arc/climax/exit_state/trend（结构角色自审、三张桌、过冬细账等段）后终值 2075–2236 全部落带——机械校验闭环生效，同时记录了初稿自然厚度不足的修复成本。
- **证据摘录**：preflight outcome=repair_required、error=design_drift、findings 6 条 criterion=volume_length（expect [2000,3000]，got v1=1767/v2=1611/v3=1605/v4=1553/v5=1471/v6=1575）；修复后第二轮 valid=true 零 findings、一次 submit 即 accepted/committed。

### pacing（2 条：V19/V20）

**V19｜severity: low｜未独立复核**
- **where**：卷3/nodes n3b（66-82，空档 71-73）；卷4/arc 第 91-99 段＋nodes.n4a（91-102）；卷6/arc 开局与 n6a/n6d（151-162）。
- **what**：三卷存在局部节拍供料空档、快更口径需章纲自造断章小钩（同一模式三处互证）：v3 71–73 转折间空窗（turn1 已落 62、h7 plant 收于 70、turn2 与中型兑现均在 74 后，仅剩 n3b「竞业绞索收紧」笼统供料）；v4 前段九章仅三簇事件材料（叩联署/学程序/公示挂网）、五家姿态仅「念旧情/开价码」两分、h10 载体 100 章才进场、n4a 12 章窗偏长；v6 开卷前 12 章对手第一手「合规化拆解」动作材料最早落在 163，冲突仅有账房归属/收储谈判环境程序摩擦与归位三件。
- **证据摘录**：v3 turns 62/74、n3b=[66,82]、h7 plant 收于 70、中型兑现 70-78；v4 n4a=[91,102]、h10.plant=[100,104]、arc 双方行动段起于「基金方lobby经办科室」；v6 n6b=[163,176]、geo-matou-cang story_pressure「收储谈判已开始…上锁的旧账房」。

**V20｜severity: low｜未独立复核**
- **where**：卷5/hooks h11（承 v4）payoff 窗 vs arc 开局；v1 hooks h2 payoff=[148,152] 跨 v5/v6 卷界。
- **what**：伏笔账面窗口与卷纲叙事排布错位两处（同类问题两来源互证）：h11 基金请柬 payoff 窗 [128,140]（承 v4）与 v5 arc 开局直兑（121 年会、122「请柬直兑成断供」）错位约 7 章，章纲须把账面 payoff 事件另排进 128–140 而非开局直兑场；h2 公约半句 payoff 窗 [148,152] 跨 v5/v6 卷界（v5 止 150、v6 始 151）而叙事完成点钉在 v5 临终窗 146–150——v5/v6 章纲分属两次派工，若 v5 侧按「跨卷伏笔归后卷」漏付推到 v6 151–152，将与 v6 开局「出殡余温未散」冲突（重演病榻）。
- **证据摘录**：h11 plant[116,120]/payoff[128,140] vs v5 arc「开局承接请柬直兑…回来第三天，断供通知送到柜台」；h2 payoff=[148,152]、v5 climax 146-150、v6 arc 开局自 151 起——复算 148≤150 且 152≥151。

### docs（1 条：V18）

**V18｜severity: low｜未独立复核**
- **where**：volume-blueprint-bridge.md §2.2 vs result.json。
- **what**：「默认档偏离须说明理由」机制零行使且无指定落点：产出六卷对全部适用默认档条目顺从，回执全文「偏离/不适用」出现 0 次——偏离机制未经真实偏离案例验证，且「相关自然语言字段」未指定位置，一旦偏离无从核对是否落字段。
- **证据摘录**：result.json 全文计数 偏离=0、不适用=0（「理由」5 处均为叙述用法）；bridge v1.5 §2.2「默认档偏离理由写入相关自然语言字段」原文。

## 蓝图→卷纲支撑力结论

**直接回答：按蓝图产出的卷纲是否足以支撑内容？——足以支撑，且余量在结构层；不足以「开箱即写」，缺口集中在选角与程序供料层。**

分口径：

- **起点口径（长线追读）：充分**（六卷起点分 4/4.5/5/4/4/5，均 4.6）。主线起落完整、三转折均实换对抗条件（BP-2.5）、卷末兑现物全部转为下卷入场券、两条超长伏笔有保温、五处卷界承接经引擎 advisory 逐条对勘成立、卷中空腰/伏笔中段无活动均未触发。
- **番茄口径（快更爽点）：基本够用但依赖章纲补密度**（六卷番茄分 3.5–4，均 3.8）。中型兑现按 8–10 章一落是起点式 cadence（本书契约 reader_promise 本就以起点为主），番茄式 3–5 章高频小兑现无章位粒度；三卷有局部节拍空档（v3 71–73、v4 91–99、v6 151–162）须章纲自造断章小钩（V19）。
- **派生测试**：六卷前 10 章逐章排 beats 全部可从卷纲＋冻结世界模型直接推出，零新冲突线/新机制/新对手主干发明；全部承重发明集中在「已定角色位的铸形」——起名、立档、补程序桥（19 件发明中无一代决主线走向，卷4 因发明落在 required 主节点对抗位而判「勉强」）。

**差距在哪（按对内容生产的影响排序）：**

1. **人物供给（V6/V7，13 条原始记录合并）**：对手侧与班底/盟友具名人物贯穿五卷缺失——不影响「写什么」但影响「谁在演」，章纲 new_entities 工作量大且连续性只能靠章纲层补。
2. **程序机制（V8）**：两处高潮/对冲载体（理事会撤回重评、样板评审程序）无世界模型供给，须章纲拼装因果链。
3. **跨卷账面（V9/V10/V20）**：竞业诉讼断档无 id 可挂、联盟制度线登记断档、h2 payoff 窗跨卷界——章纲两次独立派工时有漏付/冲突风险。
4. **叙述面收敛（V5/V11/V13/V14）**：六卷同套方法标签脚手架、恒 3 转折、v1↔v3 高潮机制同型、资源轴仅单调消耗型——中段爽点有同型风险，蓝图与引擎均不观察这类收敛。
5. **供给链本身（V1/V4/V15/V18）**：设计层旁路供给、三副本漂移无哈希绑定、style.trend 零供给、偏离机制零行使——不影响本卷纲质量，但影响「按蓝图生产」的可复制性与下本书的复用。

**plot_blueprint 引擎接入建议**（对应 V1/V4/V3；注意分诊复核时设计层代码已合入技能仓、contracts.py 设计层目录已登记首档「五书基准」，但目录条目仅 name/file/summary/version 字符串、无内容哈希）：

1. **走已实现的设计层通道而非旁路**：设计蓝图经作者确认后入内置 DESIGN_BLUEPRINT_CATALOG，绑定后派工自动携带 record design_blueprint＋整本 guide——Worker 冻结材料即可见，章纲阶段不再依赖主干带话（本次验证该通道零行使即为此故）。
2. **给目录条目补内容哈希**：v1.2/v2c/项目根三副本并存的漂移只有引擎哈希能拦；当前「确认后入库才可绑定」的纪律若无哈希绑定，多副本一致性仍靠人工。
3. **同步清理文档口径**：craft.md:23/volume-blueprint.md:6 的「待确认稿、确认前不得使用」自述与项目内已确认事实矛盾、确认事件无登记位置；bridge §二「已实现机制」须与引擎实际行为一致（bridge v1.5 明文作废的「项目根文件存在即生效」恰是本次实际供给路径）。
4. **派工脚本侧（V3）**：spawn Worker 前先 prepare-worker 并把 worker_env 注入子代理，避免烧技术失败额度。
5. **蓝图自身可补的观察点（V5/V13/V14）**：卷卷同数同形的微形状收敛与资源轴形态单一，蓝图 advisory 与引擎均不覆盖，可在蓝图自查单或引擎 advisory 中加观察项。

## 未覆盖范围

1. **章纲与正文阶段未实跑**：支撑力判断用派生测试（前 10 章模拟），不是引擎章纲状态链的真实验证。
2. **单会话内以主干自执模拟派工**：真实多会话 Worker、租约与 watch 未覆盖。
3. **丰富度标准未扫平台实时榜单**：以蓝图语料规律（掌门路/川菜馆等五书样本）＋结构纪律＋追读体验操作化。
4. **t3 标准档代表起点/番茄主流长篇下沿**：t4/t5 超长档未验证。
5. **设计蓝图 v1.2 的确认由作者代理代行**：真实作者的确认与裁剪流程未验证。
6. **confirm-volume 之后的链路（章纲派工、卷纲修订往返）不在本轮范围**。
