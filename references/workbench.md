# 叙事工作台

何时读：任务含 understanding/1、scene-identity/2 或 reading-dependencies/1，需延续作品理解、重排场景或声明阅读关联。

## 方向、事实、理解与方案

作者约定决定作品方向，正文及事实事件保存已经发生的事；作品理解保存可修订的编辑解释，未来设计保存尚未实现的方案。理解属于 intent 分区中的 understanding，不进入 canon.state，不直接生成事件或核验义务。

人物说“我不在乎”是言语行为；“他可能害怕失去同伴”是理解；“下卷让他主动离开”是方案。解释可并存、受质疑或停用。字段完整与证据真实不证明解释正确；v2 没有独立阅读者来评判解释是否成立，理解只作为执笔时的可选材料，**不产生任何机械门槛**。成立正文的新发展由章纲重排登记，不为符合旧解释而改写人物。

## 创作记忆

**v2 由执笔提交理解增量**：write/repair/redesign 的回执可带顶层 `understanding` 字段，工作台模式下由引擎在入库时调用 `understanding.update` 更新记录；独立阅读与审查任务已删除，没有别的写入通道。记录按各自冻结版本读取（creative_memory），不追补、不重解释。

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
- status 为 tentative / supported / contested / retired，是写下解释者的具体判断，不按证据数量计算。supported 仍是有依据的解释。
- subjects/topics 是不重复 ID 数组，可为空；evidence 至少一条，counterevidence 可为空。证据必须在冻结正文来源内，不能用设计或执笔自评。
- valid_from 默认 1，valid_through 默认 null；两者表示适用的正文阅读范围，区别于故事发生时间。ID 稳定，同一 ID 更新保留旧版本；不同解释使用不同 ID，停用原解释可交 retired 并说明理由与依据。

程序补齐证据位置、正文哈希、记录版本与来源任务。complete_understanding 保存当前正文依据仍有效的全部理解版本，失效记录仍在不可变父文档或分支存档，不能将当前材料当作全部历史。相关理解、原文样本、反证及适用范围在 creative_memory，按参与人、话题与本版本章纲的 understanding_refs 选择；显式引用可补读场外或停用解释，但不代表当前仍适用。不截断选中记录或原文引句。显式引用不存在或因修订失效时，creative_memory.unavailable_refs 列出 ID，任务应补读原文或重新提交章纲，不继承失效解释，也不因此卡住返修派工。

修订开始时只继承仍属于候选正文前缀的理解。已改正文的旧解释不自动复活；未改后文实际携带后，恢复其有效原文依据。候选若新增解释（按原协议提交）优先于同 ID 的父稿解释。discard 恢复父稿，promote 和 complete 验收当前理解的来源版本；旧记录在不可变文档与父分支中保留。

## 场景身份与时间

scene-identity/2 的场景 ID 在整本中唯一，是不透明字符串，不从中解析章号。未提供时引擎为当前场景位置生成 ID；生成后移动场景、拆章或合章必须携带该 ID。移动须从原位置移除，不能让同一场景在两处同时登记。这是唯一规则，不再接受 `c章号:` 前缀的历史 ID。

本版本的 scene.story_time 可说明实际发生时间，例如“三年前冬夜”，不直接改变事实时钟。阅读顺序由章号和 scenes 数组顺序决定；披露顺序由章纲 `disclosures` 与 `knowledge` 增量记录，不再有独立阅读任务另记一份。depends_on 只引用已可用的前章或本章前场材料，不能用未来正文作为已取得的来源；倒叙的发生时间早，不表示必须先披露。自由重排仍要重新过章纲的卷内状态链，确认人物知情、因果与披露自洽。

scene_sources 按稳定 ID 找到已提交章纲，再核对正文、事件、章纲哈希与章节链；不能用未提交章纲冒充历史来源。展开单元 scene 仍表示本章数组位置，不是永久身份。

## 分级修订

revision-impact / revise 的 changes-file 支持 reading 模式及可选 reading_changes：

```json
{
  "mode": "reading",
  "reading_changes": [{"kind": "character", "key": "shen"}],
  "scenes": ["scene:warehouse-confrontation"]
}
```

mode=expression 或 reading 保持事实投影不变；reading 必须给非空 reading_changes。mode=semantic 继续沿事实和因果依赖保守扩大连续重写范围，也可同时给 reading_changes。reading_changes/reading_refs 的 kind 为 character / relationship / theme / voice / disclosure，key 是稳定关联 ID。人物及声线由 participants 自动关联，披露由 disclosures 关联；其他关联在章纲或每场 reading_refs 中明确声明。

任务冻结 capabilities.reading_dependencies=reading-dependencies/1，规范化章纲由引擎保存 reading_schema=reading-dependencies/1，Worker 不手填标记。所有章纲统一按该协议解释 reading_refs、reading_coverage、understanding_refs 和 story_time；没有标记的历史章纲不再有保守解释，重绑与修订核算直接按当前规则拒绝。

reading_coverage 默认 partial。声明 complete 须有实际场景，且每场都有 reading_refs（无额外关联给空数组）；**v2 没有独立读者核对遗漏与错误**，引擎只核对声明形状，语义是否完整只能靠作者抽读。阅读关联未核清时，对候选后文保守安排重写；已声明完整时沿匹配关联及受影响场景的依赖桥梁传播。

后续处理动作由影响分析给出：

| 动作 | 执行 |
|---|---|
| 原样携带 | 正文不动，仍核对显式前态、场景来源并重放事实 |
| 局部修改 | 修改指定局部，editorial/1 可用版本补丁，重新过机械核算与 lint |
| 按重排章纲重写 | 受影响的章纲由 `chapter_outline`（payload 带 `repair=True` 与偏差清单）重排后重写，再重新核算 |

分析命令的 last/rewrite_chapters 表示建议的初始修改区间，动作也列出区间之后仍需处理的章，不把携带等同于重写。revise 显式用 --through 扩大终点时，实际采用的区间、动作和传播一并更新；新增修改章不能继续沿用分析建议中的携带动作。最终以机械核算覆盖修订起章至候选末章，不只核对接缝。**v2 不再有独立重读任务**：阅读变化只能靠章纲重排 + 重写 + 作者抽读覆盖，不再有一次独立的阅读判断。

影响分析不等于自动执行授权。历史修订先受允许范围约束；revision_blocked 只保存方案，不建立候选分支，也不使原文依据及理解失效。超范围授权、准确方案与过期处理见 [运行](runtime.md)。

章纲重排不消耗正文返修次数，真实 repair/redesign 仍消耗原章共享额度。预检回滚核验、理解、候选章节和调度；中断恢复沿原 task 继续。新核验结果随候选章节存档，promote 后仍可 audit。

修订中若重排后的章纲改变了下一待携带章的计划，停止原样携带，保留新章纲并进入返修；旧章纲不能覆盖重排后的新意图。重排清理的后续计划重新规划，已指定重写的章即使新章纲与原章纲相同，也须重新写。返修前补齐新参与人物或重核成长后的档案（由章纲 `new_entities` 承载），保留候选正文及原修复额度；篇幅预算只预留当前修改章或重排窗口之后的固定后缀。后续仍按处理动作、事实重放和机械核算推进。

## 项目边界

所有项目自带工作台数据结构（init 即建立 understanding），没有事后启用的路径；`workbench` 命令已随旧项目支持一并移除。存储 schema 保持 novel-ledger/3，没有新增表或隐式迁移；v2 及更早数据库明确拒绝，不自动转换。旧开书协议（creation/1~/5）与旧任务能力形状同样读取即拒，见 [协议](protocol.md)。
