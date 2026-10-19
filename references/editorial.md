# 人物、场景、补丁与完本

何时读：任务含 `capabilities.editorial=editorial/1`，涉及人物重核、场景材料、版本补丁、正文偏离登记或完本；修订与理解协议读 [叙事工作台](workbench.md)。

## 适用范围与读取顺序

| 当前阶段 | 读取位置 | 执行重点 |
|---|---|---|
| chapter_outline | [人物与场景](#人物与场景) | `new_entities` 档案、对白意图、场景展开与声线来源。 |
| repair / redesign | [版本补丁](#版本补丁) | 准确基稿、三选一交稿方式及重新机械核算。 |
| write（自比） | [正文偏离](#正文偏离) | 偏差如实登记、理由与引文、下一章纲重排。 |
| 完本 | [完本与关闭](#完本与关闭) | 篇幅、required 节点与线路、快照交付。 |

空间及评测工具按题材和任务取用，不因能力开启每次通读整页。

本页维护编辑能力专用字段与状态转换；默认开关、依赖条件统一见 [协议](protocol.md)。执行以当前 brief、capabilities 和模板为准；已启用项目不能降级以绕过验收，已保存回执按冻结版本复核。创作判断沿 [创作与自比](craft.md) 执行，字段完整不证明内容成立。

## 人物与场景

### 人物档案

新人物不再有独立档案派工：首次登场时在章纲 `new_entities` 内联给出 `id`/`kind`/`name`/`role`/`desire`/`limit`/`knowledge_boundary`，落地后按 id 引用。已有角色的事实变化由章纲 `characters` 和正文自比提交；人物解释与样本按作品理解协议维护。

旧冻结任务里的档案字段（tier / biography / speech / relationship_modes 等）按各自协议解释，新任务模板以当前契约为准。档案解释行动和表达，不能自行确立经历、资源或知情；当前动机与成长事实仍由正文的漂移项与引擎结算确立。档案整份按参与人交付，不额外派昂贵索引任务。

### 场景计划

章纲每章可选 `scenes` 非空数组，每场 label/intent/conflict/turn/present/speakers/dialogue_intents。present 属于本章 participants；speakers 为实际拟发言者，静默场景显式空数组。对白意图恰好覆盖 speakers，每项 entity/seeks/withholds/pressure/tactic/knowledge_topics；没有相关话题用空数组，不需隐瞒或没有压力时在对应文字中说明实际情况。

场景还可携带稳定 id、reads 和 depends_on，章纲以 dependency_coverage 声明依赖是否完整；字段和保守扩大规则见 [叙事推进](narrative.md#场景依赖与任务材料)。执笔以 `scene_context` 读取本章章纲与场景，`scene_sources` 冻结前置场景版本。旧章纲行里的 `expansion_units` 等字段按原语义保留，新任务以当前模板为准。

短稿补实这些作用，避免同义扩写。静章不强加危机，持续高潮不强插休息。

### 声线锚点

首章批准保存准确正文样本、声线、traits 与作者原话为 style_anchor，作为后续执笔的声线依据，**也是文风代理指标的基线**（`book['style_anchor']['sample']`；没有锚点时仍核对重复度、视角及本章显式对白目标，详见 [文风](narrative.md#文风)）。约定声明 `pov` 时，执笔与自比按 pov 核对人称、视角范围和切换交代。具体问题由原文与影响支持；没有对白或没有修订时说明实际情况并举证，不强迫额外对白或虚构修订目标。

## 版本补丁

repair/redesign 可以交完整 prose，或者以下两种方式之一；仍交 title/summary/drift_check/具体 self_check：

```json
{"base_hash":"本任务 base_draft.prose 的规范 JSON 哈希",
 "patches":[{"start":123,"old":"准确原文","new":"修改文字"}],
 "repair_note":"说明实际改动和保留部分"}
```

```json
{"base_hash":"准确基稿哈希","reuse_original":true,"repair_note":"核对原文仍成立的具体依据"}
```

prose/patches/reuse_original 三选一。start 是完整基稿的 Python 字符位置；补丁不重叠，不对空 old 插入，不原样替换，不清空整章。`commands.patch --old 原文 --new 新文 [--start N]` 返回准确基稿哈希及补丁；歧义时给目标 start。基稿、前态及引擎拒绝的具体项仍必读，局部编辑不承诺无需读取全章。

程序合成全文后执行原篇幅、字面规则、lint 与漂移核算；预检回滚不计次，实际 repair/redesign 计同一章的共享额度。补丁和复用都保留补丁审计、重新执行同一套机械判据。

人物与关系解释、原文表达样本、跨章场景身份与先重排后改写见 [叙事工作台](workbench.md)。

历史稿先分析影响时使用 [运行](runtime.md) 中的 revision-impact / revise --changes-file。表达及阅读修订保持事实投影不变，阅读变化声明 reading_changes；语义修订沿依赖传播，缺少完整依赖时保守扩大。这与补丁交付方式分开：实际补丁或全文修改仍重新过机械核算与 lint，影响报告不代替判断。

## 正文偏离

偏差需在 `drift_check` 中给出原因与引文。通过全部机械判据后才入库，并触发后续章纲重排；覆盖、前态或事实规则不满足时不能凭偏差理由放行。字段和处理路径见 [漂移核算](narrative.md#执笔自比与引擎核算)。重排重新核验状态链与结构化卷末终值，`exit_state` 仅作文字说明。

## 完本与关闭

卷末闭合核对卷纲的结构化终值、绝对时钟 `clock.to` 与必要伏笔（容差 0）；自然语言 `exit_state` 只作文字说明。要追加计划外章节，只能由作者明确的新授权或改约完成，并在新章纲里重新登记增量。

`complete` 核对当前全部卷的闭合状态、required 节点与线路是否 resolved、首章认可、实际篇幅（章数与每章区间），再保存不可变 completion_snapshot；有来源覆盖枚举的项目按各自冻结版本复核。`deliver` 从该快照导出 book.md/book.html/delivery.json，清单含快照引用、章节哈希及文件内容哈希（规范 JSON 字符串的 SHA256）。导出失败只重试 deliver，内容完成状态与快照不变。已完本的 export/html 同样使用冻结版本。

## 按题材使用空间能力

作者约定可选 anchors=[{entity,key,value,policy:fixed|eventful}]、links=[{id,a,b,kind,path属性…}]。锚点可指已存在实体或地点；地点的楼层/房号按 fixed anchor 保存，用途绑定用 eventful anchor；已成立地点父关系保持稳定。空间结算仍由引擎按下面字段机械执行（`spatial.settle` 保留），触发来自章纲的 `places` 增量与执笔漂移项，证据是正文原文引文；具体提交形状以当前任务模板为准，旧任务按原协议解释：

| op | 业务字段 |
|---|---|
| anchor / anchor_assert | entity/key/value，首次 policy 缺省 fixed；再次断言须相同 |
| anchor_change | entity/key/before/after/reason，仅 eventful 可改 |
| link | id/a/b/kind:path或sight或sound，可带 open/directed/min_days/requires:{事实键:值} |
| link_change | id/before/after/reason，前后为 open 布尔值 |
| placement | entity/before/after，位置为 {place:ID} 或 {holder:ID}；交接双方在同一已知地点，持有链不成环 |
| travel | entity/from/to/links:[逐段路径ID]；可同时给 depart/arrive，单位为主线天数 |
| perceive | observer/target/channel:sight或sound/from/to；跨地点须直接给 link，不自动更新 knowledge |

有 path 拓扑时使用 travel，不能以基础 `places` 的文字路线绕过条件；未建拓扑且满足移动前提时可登记普通移动。已知耗时为下限，未知段不捏造数字。已记录到达下限由携带物继承，转交或放下不清零；未给精确时间时不宣称移动耗时已验证。拓扑只核对登记连接、条件与时间；遮挡、指代、视距和生理能力的语义合理性需人工核对。

## 用量与文学评测

本节仅供评测任务取用，实验条件与验收依据统一见 [验证](validation.md)。

`usage` 观察任务信封、已接受回执和 CLI read 实际交付字符；未记录的尝试或宿主计费为 null，字符不换算费用。`scripts/observe.py summary 宿主观测.jsonl` 对 provider/session_id/request_id 去重，同调用冲突拒绝累加；输入非缓存 token、缓存读取和输出分别记录，任一缺失则总量未知。观察工具不推进故事。

离线盲测工具用 `scripts/quality_eval.py prepare --manifest 清单.json --out 独立目录` 随机化完整样本，保留私有植入位置与预期；评审只获得自己的 input.json。先用 `first-read --input 样本/input.json --file 首读.json` 冻结首读，review.json 的 first_read 必须与冻结 data 一致，再 `score --directory 评测目录` 统计定位命中、漏检和已裁决误报。原稿不是金标准，没有独立裁决时误报率留未知；预期的文件/工具隔离由宿主落实，工具不证明模型真的盲读。所有评测数据存小说项目或独立临时目录，不写进 skill。
