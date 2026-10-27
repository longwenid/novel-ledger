# 独立连续性核验与可信宿主

何时读：`continuity_review_required`、`review_required`、`review_in_progress`、`review_author_required`、`review_complete`，或配置保障模式、接入可信执行宿主。普通执笔仍按当前任务的commands与模板执行。

## 模式与边界

2.1.0的新CLI项目默认 `continuity=required, trust=advisory`。旧项目恢复保持原模式，不追填旧报告；每次正式状态写入建立治理检查点，之后直接清返修记录会报 `governance_integrity`。同系统账户仍能同时篡改数据和检查点，因此它是来源异常检测，不是OS安全隔离。

- `continuity=required`：通过机械判据的正文先成为候选，独立观察和比较完成后才正式提交。每章重新绑定准确候选；每十章一轮的默认首读包含此前九章，其余包含此前两章，均为全文。远距相关原文按冻结历史补读。首读返回附 observation_template 信封与 observation_example 行级示例：观察的 entity/predicate/value/certainty/time_frame 与 evidence 逐字引文按示例填写，不需要读引擎源码猜格式。
- `continuity=off`：保留机械路径，验收列出未经独立核验的章节；不据此宣称全文连续或人物可信。需要切换时使用 `assurance --trust advisory --continuity off|required --source 作者原话`，先确认原Worker已停止，保留候选并取消在途任务；不自动降低保障模式来恢复。
- `trust=advisory`：宿主仍须实际派出独立模型，但程序只能核对其声明和证据，报告显示未验证身份/人类来源。
- `trust=required`：必须由受控宿主注入真实调用上下文及签名证明；本地CLI没有该能力，prepare、作者决定与冒名提交会拒绝。这个模式不因为UUID形状正确就放行。

已有作品不因换版本而重写或补造独立报告。启用required也不能给旧历史补发“可信”标签。

## 主控与执笔交接

机械不通过时，submit/preflight顶层 `outcome=repair_required`，总 `findings` 给出字数、漂移、语言等全部当前判据，不能只看style.findings。`transaction.persisted`描述事务；`committed_chapter`才描述章节。业务预检不提交正文、候选、故事状态或文学额度；CLI 执行通道的续租和预览轮次记录见 [内容预检](runtime.md#内容预检与材料落盘)。

机械通过且需要独立阅读时：

1. `preflight`返回 `continuity_review_required`，不保存请求。Worker执行正式submit后，引擎保存准确候选和冻结历史，返回 `request_id`、`candidate_hash`、`worker_boundary=await_review`。章节与文学额度尚未改变。
2. 主控收到Worker摘要，或watch/advance返回 `review_required`，在核验尚未绑定读者时实际创建另一空历史读者上下文，取得真实会话ID。执行 `prepare-observer --request ID --session 真实ID`（带原owner），仅向该读者注入 `observer_env` 并交付返回的commands；清除执笔Worker的环境，不能由主控或执笔者换个名字代审。绑定后首读与比较阶段的advance返回 `review_in_progress`，主控执行 `watch --owner ID`，由引擎等待并续主控租约；不重复派读者，也不以模型轮询等待。
3. 读者执行 `commands.review-read`，完整读候选与相邻正文。只读阶段不提供章纲和执笔自评。响应的sources保留本次原文与准确hash，history只给冻结历史的章节范围、数量及补读入口；完整历史hash清单留在候选存储中，不反复投递。需要远章时加 `--chapter N`，只从本请求冻结历史取完整原文及hash，不缩减每章必读窗口。
4. 读者从read返回的 `observation_template` 起稿。观察给出实体、谓词、值、明确/表象/传闻/不确定，以及原文版本、quote/start。无法确认的事情保留限制，不自动填pass，也不要求每章凑若干事实。用 `commands.review-observe --file 观察.json` 冻结后，不能回头覆盖这份首读。
5. 读者执行 `commands.review-read --compare`，此时才拿到章纲、自比、相关人物材料和 `report_template`。`comparison.characters` 给出冻结任务中的世界档案、既有登记、本章新档案、章前当前状态与成长记录，并保留来源哈希。比较已读原文、计划、执笔自评；旧账目只作线索，涉及的旧事实须回到原文。用 `commands.review-report --file 报告.json` 提交。明确矛盾须成对引文；歧义和编辑判断分别记录。
6. `review_complete`后，由原执笔Worker用原候选和当前有效凭据重做submit。明确矛盾按统一findings进入本章有限返修，不能改纲迁就正文；通过才入库。纯编辑意见保留在报告，不用形容词数量或个人偏好自动拒稿。报告含歧义时advance/watch返回 `review_author_required`（报告存储phase仍为review_required），停止自动推进并交作者选择 `review-resolve --request ID --disposition accept_uncertainty|repair --source 原话`；接受未决会留痕，不能覆盖成clean。读者长时间未完成时watch返回idle，保留原候选和读者身份，先核实宿主执行状态。

同一候选已提交成功后原命令重试返回原章节确认和 `idempotent=true`；内容不同则拒绝。报告绑定task/input/candidate/observations各版本，候选哈希覆盖回执内容但排除session/execution_claim两项传输身份；主控合法重新派工时可更新这两项，不能因此重复收费阅读，也不能改data沿用旧核验。旧读者身份不能转成新执笔者，已开始的原读者仍独立完成核验。取消任务、换分支或新候选取代后，旧读者不得继续结算；引擎/规则构建变化时读者也停止。没有实际读者或宿主能力时保留候选报告缺口，不提交空核验来凑流程。

观察、报告和作者裁决的准确重试不写新事件，也不回退已完成状态。同一任务正文未变（含只改空白）时，改自评、摘要等字段不能重新派读；须重交原回执。读者已开始或歧义待决时不得换稿中断核验；报告要求返修时先重交原候选结算文学额度，再在新任务改稿，不能用换候选跳过额度。

`usage.continuity_read_calls/continuity_read_chars`单列独立首读、补读和比较材料的实际调用与字符；不并入旧机械路径的读取基线，也不换算成计费token。完整模型费用仍须宿主真实用量观测。

## 读者判断与证据

首读关注正在被故事依赖的生死、抓获/出发/到达/撤离、具体地点身份、证物来源/归属、时间与期限、谁知道什么、已兑现承诺和人物声线。核对前次胜利是否改变后续约束，是否反复把同一结论包装成新真相，以及管理语言是否进入对白。静章、停顿、心理和有意义的重复都可以成立。

观察的格式例如（哈希和偏移必须来自本次read，不能照抄示例）：

```json
{
  "entity": "person_example",
  "predicate": "life_state",
  "value": "dead",
  "certainty": "explicit",
  "evidence": {"source": "47", "prose_hash": "冻结文档hash", "quote": "原文精确引句", "start": 0}
}
```

`source=candidate`表示当前候选，数字字符串表示冻结历史章。life_state使用alive/dead/unknown；明确的dead→alive不能被空报告豁免，unknown不清除已知死亡。表象死亡用apparent，传闻用reported；补叙、并行或时序未决的观察须标 `time_frame=flashback|parallel|uncertain`，不按章节顺序强判生死矛盾，默认present表示当前叙事。确有复苏事件时可在alive观察加 `transition: {kind: "revival", evidence: {…准确引文…}}`，引文须位于死亡与重新存活之间。程序验证结构与证据，并核对这些明确观察之间的矛盾；不自行理解任意自然语言，也不能保证读者没有漏提事实。

报告的findings使用 `kind=contradiction|uncertain|editorial`、具体reason与evidence数组。先给读者造成的冲突及其原文，再解释可能机制；不先看执笔者的“严格符合”宣告。核账解释、伏笔标签与任务目标不是角色自然说话的默认材料。

人物小传用于核对行动动机、关系牵制、行为与声线是否有承接。已结算的当前状态和成长优先于初始设定；小传里的过往与计划不自动成为事实证据。仅与设计不同、表达不合个人偏好或转变依据不足时，分别给编辑意见或保留歧义，不能只凭档案判定正文事实矛盾；需要追溯时补读冻结原文。

## 规划中的时间与阅读作用

章纲synopsis只写故事内发生的事；`story_events`可列具体事件，`reader_effect`单列读者效果，后者不结算事实。`timeline`是可选明确约束：

```json
{
  "scene_id": "pump-room-fight",
  "relation": "continues",
  "start": [1265, 1265],
  "end": [1270, 1275],
  "deadlines": [{"id": "train", "due": [1385, 1385], "status": "open"}]
}
```

时间用同一故事基准的累计分钟区间；未知时省略，不能捏造分钟精度。relation接受continues/after/parallel/flashback。程序在同批章纲内校验明确区间、累计日增量与同场关系；有前场结束时间时把两场间隔计入日增量，并行和补叙不倒退当前主线。已登记未结期限须在后续主线章保留，不能靠省略字段消失；跨过时须fulfilled/failed/abandoned并给 `resolution_event`。延期须extended、更新due并给故事内事件；接管delegated仍是未结期限，不能豁免逾期。跨卷或更早原文中的期限、正文是否支持这些值，仍由独立读者补读核对。旧计划没有timeline时不自动推定每章一天。

## 受控宿主的部署契约

`ports.HostAuthority`与 `authority.SignedHostAuthority` 是实际的注入/验证入口，不是Antigravity或Codex插件。密钥不从项目文件或环境变量读取；当前本地适配器不自动创建服务账户和沙箱。

宿主必须把引擎、SQLite、治理事件与密钥放在Worker不可写/读的权限域，以受限工具或服务提供读/检/交稿；调用上下文由宿主在模型之外绑定。模型只拿任务能力，不能直接使用Repository、任意引擎shell或签发密钥。可以由宿主使用 `bootstrap.local_application(repo, authority=...)` 装配受控服务；既有本地CLI不注入authority，所以在required模式下会明确拒绝，不能靠CLI参数传一个自报proof放行。

每次调用的SignedHostAuthority接收宿主持有的key、proof、实际context_id、项目 `status.assurance.project_id` 作为audience，以及时钟。proof包含claims与HMAC-SHA256 signature；签名输入是 `contracts.dump(claims)` 的UTF-8字节。claims绑定kind、subject的 `contracts.digest`、原话source_hash、audience、caller_context、issued_at/expires_at（最多600秒）与一次性nonce。worker/observer还须由宿主证明独立context_id和isolated=true；作者类决定必须human=true并含真实interaction_id。

关键对象如下，不能跨类型复用：worker绑定task/session，observer绑定request/session，approve绑定prose_hash，answer绑定decision_id/option/准确subject，run绑定target/finish/mode，continuity_resolution绑定request/report/disposition。API在相应事务中消费nonce；失败事务回滚，不误耗授权。发出run目标不能代替首章认可、加轮或改纲。宿主只应对真实的人类交互签作者证明，绝不能对模型自写source签名。

签名证明和检查点的单元测试通过，不代表这台电脑或某平台已完成权限隔离。未接入真实宿主的项目继续显示unverified；需强保证时保留候选并报告宿主能力缺失。
