# 运行与恢复

ROOT/PROJECT 替换为绝对路径，项目产物不放技能目录。

```bash
python3 "$ROOT/scripts/novel.py" --project "$PROJECT" init --contract 作者约定.json --source '作者原话与范围'
python3 "$ROOT/scripts/novel.py" --project "$PROJECT" advance
```

零输入开书不带 --contract 执行 init，advance 先派当前门的方案任务。await_choice 展示当前门，全部选择后自动创建及核验世界，world_ready 交付世界设定；详见 [逐门开书](opening.md)。开书前就有完整约定用 `init --contract 约定.json`；已进入逐门选择的项目不再接受导入，改方向用 recontract。

直接完整约定的默认目标为试章；零输入选择流程默认交付世界模型。作者已授权正文后，用 `run --through N --source 原话` 或 `run --complete --source 原话` 保存目标并取得 owner。后续主控治理命令带 `--owner 返回值`；`renew --owner 返回值` 续租。过期后重新 run 认领，沿用已经授权的实际目标，不扩大范围。

## 任务交接

advance 返回 task_ready 时读 task.task_path。commands 为 argv 数组，按数组执行，不拼 shell 字符串。派真实新 Worker，填真实 session。需要执行认领时宿主调用 `claim --task ID --session ID`（返回里的 token 以**裸字符串**填进回执顶层 execution_claim，不能是对象），首读与提交附 execution_claim。任务视图带 `claim` 字段：`null` 表示无人认领，`{session, expired:false}` 表示有 Worker 在途（不要重派），`expired:true` 表示租约已过期、可由新 Worker 重新 claim 接手——result.json 存在但 claim 过期时，先重新 claim 再原样重提，不要改写回执。跨会话接管项目：先 `status` 再 `advance`，按返回动作接续，不手改库。

### 路径与失效判定

commands/guides 由**当前安装**渲染（解释器取自身份进程，脚本取自身份文件），并用目录联接（junction/symlink）映射时两条路径实为同一份安装。派工前先确认命令里的解释器与脚本存在，再交给 Worker；**不要凭路径字面判断某条命令失效**——先文件系统核实。技能目录确实移动过时，回主控再执行一次 `advance` 刷新任务视图即可重建命令，不要手改命令、也不要在派工提示里让 Worker"忽略 task.json 的 commands/guides"（那会让 Worker 用错身份或漏读必读记录）。

初始审稿信封只有冻结正文和首读模板；完整读 prose_files，填写 first_read_path 并执行 first_read 命令，沿返回 task_path 读解锁模板，同一模型会话继续核验。submit 返回 worker_boundary=finished 后 Worker 结束。

主控核实实际提交后 `advance --after ID`。未提交返回 wait_for_submit，旧回调返回 resync；不能凭口头完成派下章。await_author 给准确 prose_hash；已获得该版本认可时 `approve --prose-hash HASH --source 原话`，沿原目标继续。

范围审稿每个 scope_review 完整读本块章节；全部 pass 后，scope_synthesis 阅读全部块报告、逐章证据与必要历史原文，独立判断长范围关系。综合者不伪造全书首读。综合材料随覆盖增长，系统不承诺任意长篇都有固定上下文上限。

## 暂停与修改

- `pause --reason 原因` 保留任务与候选；`--cancel` 取消但留档。原会话可恢复时沿原首读继续；另派审稿者时取消旧任务，生成新首读，不能冒用旧 session。
- `resume` 不增加额度；耗尽时保留材料并报告缺陷和作者处理方向，不能重开任务清零。
- 候选稿反馈用 `feedback --text 原话`；验收稿用 `revise --from-chapter N --reason 原话`。一词级小修可用 `--through M` 把修订终点收窄到受影响章：终点之后的章节在终点章入库时原样携带（冻结事件对新状态重新结算，事实受影响即整单拒绝并要求扩大范围），修订块审覆盖改动章与接缝章。修订重审完整后缀（或窄范围的改动章+接缝）通过后 promote；discard 恢复旧稿及目标。
- `replan --from-chapter N --reason 原因` 只改未写窗口；已有草稿或正式稿的计划不能直接删除。
- `lexical --file 规则.json --source 原话` 改作者字面约定，新版本追加在项目记录里，旧版本保留；改规则会取消在途任务并作废其视图，下次 advance 重新派任务。
- `recontract --file 完整候选.json --source 原话` 取消旧任务留档，经独立核验激活新约定，在父稿保留的分支重新规划写审。`opening --file` 是同一核验路径的开书入口：只在项目没有派发过门任务时接受（`init` 之后、第一次 advance 之前），导入后清除逐门选择状态；派过门任务后按 creation 错误拒绝并用 recontract 改约。
- target_reached 表示授权章节目标完成；ready_to_complete 还须 complete 验收。通过后 export 导出纯文本（`--format md`）或简化 HTML，`html` 生成全书视图（约定、世界、设计、计划、档案、账本、章审与正文两种模式），两者都返回绝对路径，章节边界可显式刷新。

## 可选宿主

command.json 是已安装模型宿主的 argv 数组。`host-step --command-json 文件 --owner ID` 执行一步；`host-loop ... --limit N` 在当前进程持续监督，遇作者边界、失败、暂停或目标终点停止。

通过 NOVEL_TASK_PATH/NOVEL_PROJECT/NOVEL_TASK_ID/NOVEL_SESSION/NOVEL_EXECUTION_CLAIM 提供身份；CLI 只消费其中的 TASK_ID/SESSION/EXECUTION_CLAIM，PROJECT 与 TASK_PATH 是给 Worker 进程定位项目和回执的便利变量，命令行仍须显式给 --project。宿主负责实际模型新会话；新子进程不证明空模型历史。超时终止并等待自己的进程；返回 0 且任务实际 done 才继续。

advance 的动作除 task_ready、await_choice、await_author、wait_for_submit、resync、target_reached、ready_to_complete、world_ready、revision_ready 外，还包括表示停机的 paused、completed 和表示额度耗尽的 repair_exhausted；宿主适配器另有 worker_finished、host_timeout、step_limit、host_launch_failed、resume_session_required、needs_attention。遇到非 task_ready 动作先按边界处理，不要当作未知错误重试。

冻结过首读的遗留任务返回 resume_session_required；通用适配器不证明模型会话恢复能力。应用关闭后持续运行、真实模型历史隔离和计费用量未默认验证。
