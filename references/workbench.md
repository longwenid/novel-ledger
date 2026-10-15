# 叙事工作台

何时读：任务含 understanding/1、scene-identity/2 或 reading-dependencies/1，需延续作品理解、重排场景、声明阅读关联，或执行 revision_review。

## 方向、事实、理解与方案

作者约定决定作品方向，正文及事实事件保存已经发生的事；作品理解保存可修订的编辑解释，未来设计保存尚未实现的方案。理解属于 intent 分区中的 understanding，不进入 canon.state，不直接生成事件或核验义务。

人物说“我不在乎”是言语行为；“他可能害怕失去同伴”是理解；“下卷让他主动离开”是方案。解释可并存、受质疑或停用。核验字段和证据真实性不证明解释正确；有不同理解或表达建议时用 note，只有具体阅读损失才安排返修。成立正文的新发展可沿现有 alignment 改案流程保留，不为符合旧解释而改写人物。

## 创作记忆

chapter_review、scope_review、scope_synthesis、revision_review 可在顶层 data 交 understanding 数组。只有相应核验通过并原子提交后更新，空数组表示本次没有新理解；执笔者不能提交。模板和指南由任务冻结能力决定，不给旧任务追补要求。

每条记录：

```json
{
  "id": "relationship:protect-colleague",
  "kind": "relationship",
  "claim": "他可能把保护同事放在证明自己清白之前。",
  "subjects": ["shen", "colleague"],
  "topics": ["responsibility"],
  "status": "tentative",
  "reason": "承担后果的动作支持这一解释，但还不能排除自保动机。",
  "evidence": [{"chapter": 12, "quote": "完整准确的原文引句"}],
  "counterevidence": [],
  "valid_from": 12,
  "valid_through": null
}
```

- kind 为 character / relationship / theme / voice；表达样本直接保留在 evidence 引文中，不用标签替代原文。
- status 为 tentative / supported / contested / retired，是审稿者的具体判断，不按证据数量计算。supported 仍是有依据的解释。
- subjects/topics 是不重复 ID 数组，可为空；evidence 至少一条，counterevidence 可为空。证据必须在本任务冻结正文来源内，不能用设计或执笔自评。综合者补读完整原文后才能使用相关证据。
- valid_from 默认 1，valid_through 默认 null；两者表示适用的正文阅读范围，区别于故事发生时间。ID 稳定，同一 ID 更新保留旧版本；不同解释使用不同 ID，停用原解释可交 retired 并说明理由与依据。

程序补齐证据位置、正文哈希、记录版本与审稿会话。complete_understanding 保存当前正文依据仍有效的全部理解版本，失效记录仍在不可变父文档或分支存档，不能将当前材料当作全部历史。相关理解、原文样本、反证及适用范围在 creative_memory，按参与人、话题与本版本章计划 understanding_refs 选择；显式引用可补读场外或停用解释，但不代表当前仍适用。不截断选中记录或原文引句。显式引用不存在或因修订失效时，creative_memory.unavailable_refs 列出 ID，任务应补读原文或重规划，不继承失效解释，也不因此卡住返修派工。

修订开始时只继承仍属于候选正文前缀的理解。已改正文的旧解释不自动复活；未改后文实际携带后，恢复其有效原文依据。候选新增解释优先于同 ID 的父稿解释。discard 恢复父稿，promote 和 complete 验收当前理解的来源版本；旧记录在不可变文档与父分支中保留。

## 场景身份与时间

scene-identity/2 的场景 ID 在整本当前版本中唯一，是不透明字符串，不从中解析章号。未提供时引擎为当前场景位置生成 ID；生成后移动场景、拆章或合章必须携带该 ID。移动须从原位置移除，不能让同一场景在两处同时登记。旧 c章号:名称 ID 可原样保留；没有新能力的旧冻结计划仍按原前缀规则校验。

本版本的 scene.story_time 可说明实际发生时间，例如“三年前冬夜”，不直接改变事实时钟。阅读顺序由章号和 scenes 数组顺序决定；披露顺序由章计划 disclosures 和独立 reader_knowledge 事件记录。depends_on 只引用已可用的前章或本章前场材料，不能用未来正文作为已取得的来源；倒叙的发生时间早，不表示必须先披露。自由重排仍须重新核验人物知情、因果与披露。

scene_sources 按稳定 ID 找到已提交计划，再核对正文、事件、计划哈希与章节链；不能用未提交计划冒充历史来源。展开单元 scene 仍表示本章数组位置，不是永久身份。

## 分级修订

revision-impact / revise 的 changes-file 新增 reading 模式及可选 reading_changes：

```json
{
  "mode": "reading",
  "reading_changes": [{"kind": "character", "key": "shen"}],
  "scenes": ["scene:warehouse-confrontation"]
}
```

mode=expression 或 reading 保持事实投影不变；reading 必须给非空 reading_changes。mode=semantic 继续沿事实和因果依赖保守扩大连续重写范围，也可同时给 reading_changes。reading_changes/reading_refs 的 kind 为 character / relationship / theme / voice / disclosure，key 是稳定关联 ID。人物及声线由 participants 自动关联，披露由 disclosures 关联；其他关联在计划或每场 reading_refs 中明确声明。

新任务冻结 capabilities.reading_dependencies=reading-dependencies/1，规范化计划由引擎保存 reading_schema=reading-dependencies/1，Worker 不手填标记。只有该标记的计划才解释 reading_refs、reading_coverage、understanding_refs 和 story_time；旧计划中同名字段原样保留，不因升级取得新语义。对没有标记的历史计划，阅读影响按覆盖未核清处理，保守重读，不能用旧同名 complete 声明缩小范围。

reading_coverage 默认 partial。声明 complete 须有实际场景，且每场都有 reading_refs（无额外关联给空数组）；独立读者核对遗漏与错误，不能仅凭字段完整推断语义完整。阅读关联未核清时，对候选后文保守安排重读；已声明完整时沿匹配关联及受影响场景的依赖桥梁传播。

chapter_actions 给出四类处理：

| action | 执行 |
|---|---|
| keep | 正文原样携带，仍核对显式前态、场景来源并重放事实 |
| review | 先派新独立 revision_review，只读正文冻结首读，再核验阅读效果 |
| local | 修改指定局部，editorial/1 可用版本补丁，仍完整独立章审 |
| rewrite | 在保守连续区间重写并完整独立章审 |

分析命令的 last/rewrite_chapters 表示建议的初始修改区间，chapter_actions 也列出区间之后需重读的章，不把重读等同于重写。revise 显式用 --through 扩大终点时，实际采用的区间、动作和传播一并更新；新增修改章不能继续沿用分析建议中的 keep/review 动作。未声明 reading_changes 的 expression/semantic 说明保持原有调度；最终修订范围审覆盖修订起章至候选末章，不只核验接缝。

影响分析不等于自动执行授权。审稿触发的历史修订先受近期窗口、修改章数和已关闭验收范围约束；revision_blocked 只保存方案，不建立候选分支，也不使原文依据及理解失效。超范围授权、准确方案与过期处理见 [运行](runtime.md)。

revision_review 的 data 为 reader 回执及可选 understanding。reader 使用本任务完整阅读检查清单、language 反证和阅读类义务，不重抽 events 或改写正文。pass 保留该章正文，保存原文哈希、首读、独立会话及核验记录后继续携带。fix 的实质 findings 须指当前章和 local/chapter；系统转入 repair，提交修改后重新派独立章审，事实和阅读均通过才继续。note 不触发返修。

重读不消耗正文返修次数，真实 repair/redesign 仍消耗原章共享额度。预检回滚核验、理解、候选章节和调度；中断恢复沿原 task/首读会话继续。新阅读核验随候选章节存档，promote 后仍可 audit，不沿用原作者或原审稿会话自审。

修订中若独立未来改案已改变下一待携带章的计划，停止原样携带，保留新计划并进入返修及完整独立章审；旧计划和旧 pass 不能覆盖已核验的新意图。改案清理的后续计划重新规划，已指定重写的章即使新计划与原计划相同，也须重新写审。返修前补齐新参与人物或重核成长后的档案，保留候选正文及原修复额度；篇幅预算只预留当前修改章或重规划窗口之后的固定后缀。后续仍按修订动作、事实重放和范围核验推进。

## 已有项目

1.5.0 新项目默认启用工作台。存储 schema 保持 novel-ledger/3，没有新增表或隐式迁移；已有 v3 项目无 understanding 时，直接续写沿原材料和身份协议运行。需要启用时，在无在途任务、草稿或修订的章节边界执行 `workbench --source 作者要求原话`，新增空作品理解并更新运行版本及启用来源，不改正文、事实、计划或旧回执。另一路径是 recontract 的新约定经独立核验后重新激活：它按新项目规则默认启用工作台并重新规划写审。两条路径均不追补旧冻结任务或重解释旧计划。v2 及更早数据库仍明确拒绝，不自动转换。
