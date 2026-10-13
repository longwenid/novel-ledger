---
name: novel-ledger
description: >-
  零输入逐门选择开书，自动创建丰富世界模型；支持长篇网络小说滚动规划、独立写审、修订、断点恢复和完本交付。
---

# novel-ledger

ROOT 为本技能目录，PROJECT 为独立小说目录。入口 `python3 ROOT/scripts/novel.py --project PROJECT 命令`；Windows 用 python。运行仅依赖 Python 3.9+ 标准库。

## 按任务取用

- 懒人开书：读 [逐门开书](references/opening.md)。无需一句话、题材或大纲，init 后系统先给当前门的 2～3 个方案；用户逐门选择。最后一门结束自动进入 [丰富世界模型](references/world.md) 创建和独立核验。
- 已有完整设定或反馈：读 [创作与写审](references/craft.md)。完整约定用 init --contract；已有要求直接采用，反馈与作者原话保存，不重复开选择题。
- 续写、无人值守或恢复：读 [运行](references/runtime.md)。advance 返回任务；委派真实 Worker，确认实际提交，再 advance --after 接续。沿用当前模型设置，不编造持续后台能力。
- 填写任务或处理拒绝：读 [协议](references/protocol.md)。使用当前模板和冻结任务身份，拒绝自带修正出口；不查旧 pass 猜字段。
- 改引擎或扩展能力：先读 [架构](references/architecture.md)，运行行为与依赖守护测试。文学评估读 [验证](references/validation.md)。

## 执行边界

1. SQLite 是唯一持久真源，正文与事实经 submit 原子提交；work 和 book.html 可重建。作者决定与运行目标走对应命令，不手改库或伪造回执。约定形状由 contracts.py 的字段表唯一决定，模板、校验和对齐都由它派生。
2. 主控只处理作者目标、任务身份和交接。每个执笔任务由新的空历史 Worker 写一章；每个章审由新的独立 Worker 完成事实与阅读两类核验。主控不读写正文，不自行签审；CLI 以角色分离执行：read/recall 需要 NOVEL_TASK_ID，无任务的调用按 role_boundary 拒绝。会话由宿主提供并无历史，程序只核对会话身份与不复用，空历史本身须另行验收。
3. 审稿先读取信封中的全部 prose_files，只读正文记录首读，执行 first-read 冻结；沿返回 task_path 读取解锁信封，再由原审稿者完成全部检查。首读不可改写，审稿者不读取执笔自评。
4. 正式任务使用 commands.read 一次读取完整必读记录；超出宿主显示能力时逐个 --record 完整读取。其余来源保留哈希和补读命令，未选入不代表不存在。不给正文或事实设字符截断；新 Worker 重新读必要资料。
5. 执笔只交正文、标题、具体 summary/self_check。事实审稿从正文独立重建事件；逐项理由和原文证据不可由模板自动填 pass。机械核验不证明语义判断正确。
6. 内容与篇幅共用两次返修、一次重设计，换 Worker、预检、恢复或修订不重置额度。字段拒绝与回滚不计次；耗尽保留稿件与失败史，不无限 resume。
7. 首章认可绑定准确 prose_hash 和作者原话；已有明确认可直接保存，不重复询问。运行目标持续到授权范围，阶段与卷末结束后继续。只有目标完成、作者暂停或无法自行解决的阻碍才停。

## 作者决定入口

`lexical --file 规则.json --source 原话` 改字面约定（默认禁词“账本、入账、回执”，默认禁字“砚”）：规则存在项目里并逐版留档，不放进约定，因此开书阶段同样生效。完整约定按状态选入口：项目未开始用 `init --contract 约定.json`；`init` 后还没 advance 可用 `opening --file 约定.json --source 原话` 导入并清除逐门选择；已派过门任务或已有约定用 `recontract --file`，先独立核验再重新规划。

## 最短交接

零输入开书：init → opening_options → await_choice → 用户选择 / 换组 / 返回 → 下一门；全部门结束 → world_model → world_review → opening_contract → contract_review → world_ready，自动交付 world.html 和 world.json 并给出绝对路径。用户不用编写设定，系统不代替用户选择；已有正文授权时按原话 run 接续，没有授权时停在交付处并向用户说明下一步。

advance → 按 task_path 派 Worker → Worker 阅读本任务，必要时冻结首读 → 填 result.template.json → submit → Worker 结束 → 主控 advance --after 最后任务 ID。

委派只给角色、task_path、一句背景和提交状态要求；技能明确授权在该创作流程中使用子 agent。不要复述整个信封。宿主会话身份填 session；实际使用执行认领时填 execution_claim。短状态、进程启动或口头“完成”不替代数据库内真实提交。

长范围核验由新审稿者逐块读完整章节，再派独立综合核验者阅读全部块报告、逐章证据和必要原文；不能复制块 pass 充当综合判断。到 ready_to_complete 后还须 complete 验收，再 export/html 交付绝对路径链接。

历史修订用 revise 指定修复起点，候选分支完整重写重审受影响后缀；原正式稿一直保留，范围复核通过后 promote。discard 恢复旧稿及原目标。改作者约定用 recontract，先独立核验，再重新规划与修订；纯更名目前也采用保守重审。

删除无信息作用的修饰和重复解释，用动作、对白、选择及后果区分人物声线。系统词汇“账本、入账、回执”不进入小说标题和正文，人物称呼默认不含“砚”；默认值在开书阶段即生效，早于任何约定存在，作者明确覆盖时用 lexical 命令写入项目级版本记录并保存原话。完整文学规则见 craft。

本技能是独立实现，不自动打开或转换未知来源数据库；数据库版本为 novel-ledger/2，旧版本库显式拒绝而不隐式升级。旧项目迁移和真实模型长跑需单独验收；不可把工程夹具宣称为文学成果。
