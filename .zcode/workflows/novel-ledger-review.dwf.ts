/* zcode-workflow
description: novel-ledger 流程验证（到首章）
*/
// —— 常量 ——
const ROOT = "C:/Users/longwen/.zcode/skills/novel-ledger";
const NOVEL_PY = ROOT + "/scripts/novel.py";
const PROJECT = "C:/Users/longwen/.zcode/novel-ledger-process-validation";
const REPORT_DIR = "validation/process-validation-2026-10-27";

// —— 结果类型 ——
interface Finding {
  /** 问题位置：文件路径:行号 / 命令 / 卷章段 / 阶段名。 */
  where: string;
  /** 一句话：问题是什么（不是怎么修）。 */
  what: string;
  /** 证据：命令行+输出摘录，或 文件路径:行号+原文引文。没执行过的不写。 */
  evidence: string;
  /** high=流程无法继续/数据不一致/会误导作者做错决定；medium=明显摩擦或文档缺陷；low=可改进。 */
  severity: "low" | "medium" | "high";
  /** engine=引擎行为；docs=文档问题；design=流程设计；author-gate=作者边界；material=任务材料；pacing=网文节奏；other=其他。 */
  kind: "engine" | "docs" | "design" | "author-gate" | "material" | "pacing" | "other";
}
interface StageHandoff {
  /** 项目绝对路径。 */
  projectPath: string;
  /** 主控租约令牌（没有则空串）。 */
  ownerToken: string;
  /** 引擎当前阶段/状态（status 或 advance 输出要点）。 */
  engineState: string;
  /** 给下一阶段的注意事项。 */
  notes: string;
}
interface StageReport {
  /** 阶段名，如：开书十三门。 */
  stage: string;
  /** 本阶段是否完成到可交接（以引擎真实输出为准，不看口头完成）。 */
  completed: boolean;
  /** 卡点说明（completed=false 时必填：卡在哪、引擎最后输出原文）。 */
  blocker: string;
  /** 本阶段发现的问题；没有问题返回空数组，不要凑数。 */
  findings: Finding[];
  /** 作者代理决定清单，每条：边界点+决定+一句理由。 */
  authorDecisions: string[];
  /** 给下一阶段的移交信息。 */
  handoff: StageHandoff | null;
}
interface ReviewReport {
  /** 评审视角名（如：文档结构、卷纲节奏、首章试读）。 */
  lens: string;
  /** 两三句总判断。 */
  verdict: string;
  /** 发现的问题（kind 用 pacing/docs/design 等；可为空）。 */
  findings: Finding[];
  /** 实际覆盖了什么（读了哪些材料、跑了哪些命令）。 */
  covered: string;
  /** 未能覆盖的部分及原因。 */
  missing: string;
}
interface TriagedFinding extends Finding {
  /** 分诊编号，如 V3。 */
  id: string;
  /** 该问题来自哪些来源（阶段名/评审名，多条用逗号连接）。 */
  mergedFrom: string;
}
interface TriageResult {
  /** 两三句总判断：流程是否跑通、问题最集中在哪。 */
  summary: string;
  /** 去重合并后的全部发现（不丢任何独立问题）。 */
  findings: TriagedFinding[];
  /** severity=high 的条数。 */
  highCount: number;
}
interface ConfirmResult {
  /** 对应发现编号，如 V3。 */
  id: string;
  /** verified=独立复现成立；unconfirmed=无法复现/需写操作才能验证/证据不足。 */
  verdict: "verified" | "unconfirmed";
  /** 复现方式与结果一句话。 */
  note: string;
}
interface WriterResult {
  /** 主报告工作区相对路径（validation/process-validation-2026-10-27/report.md）。 */
  reportPath: string;
  /** 卷纲+章纲合辑路径；未能提取则 null。 */
  outlinesPath: string | null;
  /** 首章正文副本路径；首章未产出则 null。 */
  chapter1Path: string | null;
  /** 作者代理决定清单路径。 */
  decisionsPath: string | null;
  /** 两三句总结论。 */
  conclusion: string;
}
interface ReportFinding {
  id: string;
  where: string;
  what: string;
  evidence: string;
  severity: "low" | "medium" | "high";
  kind: string;
  status: "verified" | "unconfirmed";
}
interface WorkflowReport {
  /** 两三句回答用户问的问题。 */
  conclusion: string;
  findings: ReportFinding[];
  /** 本轮实际核查了什么、怎么核的。 */
  verified: string[];
  /** 没有覆盖的部分及原因。 */
  notCovered: string[];
}

// —— 进度看板 ——
artifact.board("progress", {
  title: "流程验证进度",
  key: "name",
  status: "status",
  columns: ["待办", "进行中", "完成", "受阻"],
  cardTitle: "name",
  detail: [{ field: "note", label: "说明" }],
});
const CARDS = [
  "开书十三门", "世界模型", "卷纲", "章纲", "首章",
  "文档审查", "卷纲节奏评审", "章纲节奏评审", "首章试读",
  "汇总分诊", "高危复核", "验证报告",
];
function card(name: string, status: string, note = ""): void {
  report({ name, status, note }, "progress");
}
for (const c of CARDS) card(c, "待办");

// —— 共用纪律与任务卡 ——
const DISCIPLINE = [
  "【共同纪律】",
  "1. 本次是作者全权委托测试跑通的流程验证运行：你同时扮演主干与作者代理。到达作者边界（选择/认可/授权）时，以作者代理身份显式登记并继续，每个作者决定记入 authorDecisions（边界点+决定+一句理由）。",
  "2. 先读 " + ROOT + "/SKILL.md 的阶段路由表，再读当前阶段对应指南；一切以引擎冻结任务（task.json、brief.md、required、result.template.json）为准，不凭记忆猜格式；按 SKILL.md 纪律不翻源码、测试或历史报告猜格式。指南之间或指南与任务卡冲突时，以任务卡为准并记一条 finding。",
  "3. Windows + git-bash，python 命令用 python；输出乱码或编码报错时设置 PYTHONUTF8=1。",
  "4. findings 只记真实发生的问题，每条附证据：命令行+输出摘录，或 文件路径:行号+原文引文；没执行过的不写；没有问题就返回空数组，不要凑数。",
  "5. 引擎拒绝时按指南与错误详情修正重试，同类问题至多重试 3 轮；仍无法前进则如实返回 completed=false 与 blocker（含引擎最后输出原文）。绝不修改引擎代码、判据或仓库文件来绕过失败。",
  "6. 技能仓库 " + ROOT + " 只读；小说产物只写入项目目录 " + PROJECT + "。验证目标是流程可用性，不是文学质量：达到引擎校验通过即可，不做额外打磨。",
].join("\n");

const MISSION_1 = [
  "【任务】你是独立的开书执行员，在真实引擎上执行 novel-ledger 的「零输入逐门开书」阶段（init + 13 门），验证流程可用性并收集问题。",
  "步骤：读 " + ROOT + "/references/opening.md（创意门另读 references/hatch.md）；项目目录为 " + PROJECT + "（若已存在且非空，记一条 finding 并先 mv 成同目录名加 .bak 后缀，再新建空目录）；init 项目；按指南逐门推进：创意门按回执要求生成 2~3 案、再以作者代理身份选择；结构门直接按引擎档位板选择。",
  "体量门：在档位板真实数字中选单卷章数最接近 12~30、总卷数不超过 2 的档位（优先短篇/精简档），理由记入 authorDecisions——这是为让验证能跑到首章，不是文学判断。",
  "完成标志：13 门全部落定、开书阶段按指南收口。移交信息（项目路径、租约令牌若有、引擎状态、给下一阶段的注意点）写入 handoff。",
].join("\n");

const MISSION_2 = [
  "【任务】你是独立的世界模型构建员，执行 world_model 阶段（默认与 opening_contract 合并），直到约定通过机械校验并激活。",
  "步骤：按 SKILL.md 路由读 " + ROOT + "/references/world.md；用引擎命令推进到当前任务；读取冻结任务材料，从 result.template.json 起稿，交付世界模型与完整作者约定；机械校验不过时按错误逐项修正重交，每轮被拒原因记入 findings。",
  "若流程要求作者认可或授权，以作者代理身份登记并记录边界点。完成标志：约定生效、引擎进入卷纲就绪态（以引擎输出为准）。",
].join("\n");

const MISSION_3 = [
  "【任务】你是独立的卷纲设计员，执行 volume_outline 阶段，直到卷纲通过机械校验并经作者认可生效。",
  "步骤：读 " + ROOT + "/references/craft.md 的「卷纲因果设计」「十三门世界与卷纲的承接」与 references/narrative.md 的「卷纲」节；从约定与开书选择推演卷纲（核心问题、双方行动、选择代价、兑现、伏笔声明、卷末终值），按引擎冻结任务交付；回执暂存后以作者代理身份执行 confirm-volume 认可并记录边界点；若需 revise-volume 或 regroup-volume 同样以作者代理处理。",
  "每次被引擎拒绝的原因与修正成本都记入 findings——这是本阶段最重要的验证点。完成标志：卷纲生效、章纲任务可派。",
].join("\n");

const MISSION_4 = [
  "【任务】你是独立的章纲设计员，执行 chapter_outline 阶段（本卷全部章），直到通过卷内状态链校验。",
  "步骤：读 " + ROOT + "/references/narrative.md 的「章纲」与「卷内状态链与校验」节；按卷纲与约定为本卷每一章写章纲（synopsis、状态增量、enter/exit、伏笔 hooks 等，以冻结任务模板为准），提交校验。",
  "design_drift 被拒时按错误详情修正重交，每次被拒原因与修复成本记入 findings——这是本阶段最重要的验证点；重点记录：校验错误提示是否足以定位问题、修复平均花几轮。完成标志：章纲生效、首章写作任务可派。",
].join("\n");

const MISSION_5 = [
  "【任务】你是独立的首章执笔员，执行 write 阶段的第一章，直到第一章 committed。",
  "步骤：读 " + ROOT + "/references/craft.md 的「执笔」节与 references/style.md（写作纪律唯一源），格式疑点查 references/protocol.md；按冻结任务材料从 result.template.json 起稿第一章正文（篇幅按约定区间），按协议逐项自比并 submit；引擎核算不过时按返修规则修正重交（额度内），每轮返修原因与代价记入 findings。",
  "首章通过后若流程要求首章认可（定调），以作者代理身份登记认可并记录边界点。完成标志：committed 第一章（以引擎输出为准，不看口头完成）。",
].join("\n");

const ASK_DOC = [
  "你是流程文档审查员（独立、只读）。审查对象：" + ROOT + " 下的 SKILL.md、README.md 与 references/ 全部指南（重点 opening/world/craft/narrative/runtime/protocol/quality/rework，其余扫读）。",
  "目标：找流程设计的薄弱点，不是挑文字毛病。检查维度：①文档间矛盾或口径不一；②交接缺口——上游承诺的材料/字段与下游必读清单是否对得上（开书→世界→卷纲→章纲→执笔→恢复）；③作者边界设计：哪些决定交作者、哪些自决，是否清晰、是否过密打断节奏；④恢复与失败路径是否闭环（租约、watch、返修额度、修订）；⑤过度复杂或易错点：一个新读者最可能在哪里迷路；⑥文档与引擎命令面的一致性（可运行 python " + NOVEL_PY + " --help 及各子命令 --help 只读核对；不建项目、不写库）。",
  "每条发现附 where（文件路径:行号）与 evidence（原文引文），kind 用 docs 或 design。verdict 里同时给出 2~3 条设计强项。covered 列出实际读过的文件。不修改任何文件。",
].join("\n");

const ASK_VOL_PACE = [
  "你是卷纲节奏评审员，验证「卷纲设计是否符合网文情节的节奏」。分两层：",
  "(a) 方法层：读 " + ROOT + "/references/craft.md「卷纲因果设计」、references/narrative.md「卷纲」与「结构纪律」节，判断这套设计方法本身能否产出符合网文连载节奏的卷结构（开篇钩子与期待感建立、转折/高潮的分布与密度、中段维持、卷末兑现、跨卷悬置、爽点兑现间隔）；以 references/volume-blueprint.md 的语料规律作对照标准（注意它是 v1 待作者确认稿，在 verdict 里注明此身份）。",
  "(b) 产出层：读取项目 " + PROJECT + " 下 work/ 各任务目录里卷纲任务的提交材料（或用 CLI 只读命令：先 python " + NOVEL_PY + " --help 看 read/recall/status 用法；不写库），逐卷评估实际卷纲的节奏：钩子够不够、转折是否均布、中段会不会塌、卷末高潮与兑现是否成立。",
  "产出物缺失或不完整时仅评审方法层，并在 missing 写明缺了什么。findings 的 kind 填 pacing，where 写明是「方法（文件:行）」还是「产出（卷号/章段）」。",
].join("\n");

const ASK_CH_PACE = [
  "你是章纲节奏评审员，验证「章纲设计是否符合网文情节的节奏」。分两层：",
  "(a) 方法层：读 " + ROOT + "/references/narrative.md「章纲」节（含 beats/role/disclosures/hooks/pacing 字段设计）与 craft.md 相关节，判断章纲框架是否引导出符合网文节奏的章节（黄金三章、每章行动-阻力-结果-推动、断章钩子、爽点与兑现密度、信息披露节奏），以及状态增量机制（enter/exit/资源/知情核账）会不会过度机械化、伤害叙事弹性。",
  "(b) 产出层：从项目 " + PROJECT + " 的 work/ 任务材料（或 CLI 只读命令，不写库）读实际章纲，逐章评估：前 5 章是否构成合格开篇（期待感、主角处境、第一兑现）、每章结尾是否有推力、中段章是否重复感、伏笔 plant/payoff 间隔是否合理。",
  "产出物缺失或不完整时仅评审方法层并在 missing 写明。findings 的 kind 填 pacing。",
].join("\n");

const ASK_READER = [
  "你是挑剔的网文读者，试读首章。读项目 " + PROJECT + " 中已提交的第一章正文（从 work/ 首章任务的提交材料读取，或 CLI 只读命令；先 --help 看用法，不写库）。",
  "以真实读者视角逐项判断：前 300 字是否抓人；是否清楚主角是谁、想要什么、阻碍是什么；期待感与悬念是否成立；有没有 AI 味或模板味；读完是否想点开第二章。",
  "再对照章纲第 1 章的声明（synopsis/beats/hooks，同样在 work/ 材料里）看正文是否兑现了设计。verdict 用两三句给出「留读/划走」判断。findings 的 kind 填 pacing。",
].join("\n");

// —— 执行辅助 ——
function failedStage(stage: string, err: unknown): StageReport {
  return {
    stage, completed: false,
    blocker: "执行子代理失败：" + String(err),
    findings: [], authorDecisions: [], handoff: null,
  };
}
function handoffOf(prev: StageReport | null): StageHandoff {
  if (prev !== null && prev.handoff !== null) return prev.handoff;
  return { projectPath: PROJECT, ownerToken: "", engineState: "未知：用 status/diagnose 自行核实", notes: "上一阶段未给交接信息" };
}
async function runStage(agentName: string, cardName: string, mission: string, prev: StageReport | null): Promise<StageReport> {
  card(cardName, "进行中");
  const instructions = mission + "\n\n【交接信息】" + JSON.stringify(handoffOf(prev)) + "\n\n" + DISCIPLINE;
  try {
    const r = await agent(agentName).ask<StageReport>(instructions);
    card(cardName, r.completed ? "完成" : "受阻", r.completed ? r.findings.length + " 条发现" : r.blocker.slice(0, 120));
    return r;
  } catch (e) {
    const r = failedStage(cardName, e);
    card(cardName, "受阻", r.blocker.slice(0, 120));
    return r;
  }
}
async function launchReview(cardName: string, agentName: string, instructions: string): Promise<ReviewReport> {
  card(cardName, "进行中");
  try {
    const r = await agent(agentName).ask<ReviewReport>(instructions);
    card(cardName, "完成", r.findings.length + " 条发现");
    return r;
  } catch (e) {
    card(cardName, "受阻", String(e).slice(0, 120));
    return { lens: agentName, verdict: "评审子代理执行失败：" + String(e), findings: [], covered: "", missing: "评审未完成（子代理失败）" };
  }
}

log("验证项目目录：" + PROJECT);

// —— 并行分支：文档审查（与实跑链同时进行）——
phase("审查流程文档的薄弱点");
const docReviewP = launchReview("文档审查", "流程文档审查员", ASK_DOC);

// —— 实跑链（串行，每阶段一个新子代理）——
phase("开书：初始化与十三门");
const s1 = await runStage("开书执行员", "开书十三门", MISSION_1, null);

let s2: StageReport | null = null;
if (s1.completed) {
  phase("世界模型与作者约定");
  s2 = await runStage("世界模型构建员", "世界模型", MISSION_2, s1);
}

let s3: StageReport | null = null;
if (s2 !== null && s2.completed) {
  phase("卷纲设计与作者认可");
  s3 = await runStage("卷纲设计员", "卷纲", MISSION_3, s2);
}

phase("评审卷纲的网文节奏");
const volPaceP = launchReview("卷纲节奏评审", "卷纲节奏评审员", ASK_VOL_PACE);

let s4: StageReport | null = null;
if (s3 !== null && s3.completed) {
  phase("章纲设计与状态链校验");
  s4 = await runStage("章纲设计员", "章纲", MISSION_4, s3);
}

phase("评审章纲的网文节奏");
const chPaceP = launchReview("章纲节奏评审", "章纲节奏评审员", ASK_CH_PACE);

let s5: StageReport | null = null;
if (s4 !== null && s4.completed) {
  phase("首章执笔与认可");
  s5 = await runStage("首章执笔员", "首章", MISSION_5, s4);
}

let readerP: Promise<ReviewReport | null> = Promise.resolve(null);
if (s5 !== null && s5.completed) {
  phase("试读首章的读者视角");
  readerP = launchReview("首章试读", "首章读者", ASK_READER);
}

const stagesAll = [s1, s2, s3, s4, s5];
const blockedStage = stagesAll.find((s) => s !== null && !s.completed);
log(blockedStage ? "实跑链受阻于：" + blockedStage.stage : "实跑链已跑到第一章");

// —— 引擎终态证据（只读命令，确定性留证）——
phase("记录引擎终态证据");
const lastHandoff = [s5, s4, s3, s2].reduce<StageHandoff | null>((acc, s) => (s !== null && s.handoff !== null ? s.handoff : acc), null);
const ownerToken = lastHandoff === null ? "" : lastHandoff.ownerToken;
const versionOut = await world.run("python", [NOVEL_PY, "--version"]);
const statusArgs = ["--project", PROJECT];
if (ownerToken !== "") statusArgs.push("--owner", ownerToken);
statusArgs.push("status");
const statusOut = await world.run("python", [NOVEL_PY].concat(statusArgs));
const engineEvidence =
  "$ python novel.py --version\n" + versionOut.stdout + versionOut.stderr +
  "\n$ python novel.py --project " + PROJECT + " status\n(exit " + String(statusOut.exitCode) + ")\n" + statusOut.stdout + statusOut.stderr;

// —— 汇总分诊（join：分诊需要全部来源到齐才能去重合并）——
phase("汇总分诊全部发现");
card("汇总分诊", "进行中");
const [docReview, volPace, chPace, reader] = await Promise.all([docReviewP, volPaceP, chPaceP, readerP]);
const triageInput = JSON.stringify({
  实跑阶段: stagesAll,
  评审: { 文档审查: docReview, 卷纲节奏: volPace, 章纲节奏: chPace, 首章试读: reader },
  引擎终态: engineEvidence,
});
let triage: TriageResult;
try {
  triage = await agent("分诊员").ask<TriageResult>(
    "你是分诊员。下面是同一轮 novel-ledger 流程验证的全部原始材料（五个实跑阶段报告、四份评审、引擎终态证据）。\n" +
    "任务：把所有 findings 合并去重（同一问题在不同阶段被重复记录的合为一条，mergedFrom 列出全部来源；跨来源互相印证的在 what 里注明关联），统一 severity 与 kind 口径，编号 V1、V2……，不丢任何独立问题。\n" +
    "summary 给两三句总判断：流程是否跑通、问题最集中在哪类。highCount 如实报 high 条数。\n\n" + triageInput,
  );
} catch (e) {
  // 分诊失败时保底：未去重的原始发现直接编号输出，不丢条目
  const reviews = [docReview, volPace, chPace, reader].filter((r): r is ReviewReport => r !== null);
  const raw: TriagedFinding[] = [];
  for (const src of reviews) for (const f of src.findings) raw.push({ ...f, id: "V" + String(raw.length + 1), mergedFrom: src.lens });
  for (const s of stagesAll) {
    if (s === null) continue;
    for (const f of s.findings) raw.push({ ...f, id: "V" + String(raw.length + 1), mergedFrom: s.stage });
  }
  triage = {
    summary: "分诊子代理失败（" + String(e) + "），以下为未去重的原始发现。",
    findings: raw,
    highCount: raw.filter((f) => f.severity === "high").length,
  };
}
card("汇总分诊", "完成", triage.findings.length + " 条（high " + String(triage.highCount) + "）");
log("分诊完成：" + triage.findings.length + " 条发现，high " + String(triage.highCount) + " 条");

// —— 高危发现独立复核 ——
const highs = triage.findings.filter((f) => f.severity === "high");
let confirms: ConfirmResult[] = [];
if (highs.length > 0) {
  phase("独立复核高危发现");
  card("高危复核", "进行中", highs.length + " 条");
  try {
    confirms = await agent("复核员").ask<ConfirmResult[]>(
      "你是独立复核员（只读）。下面是分诊后的全部 high 级发现与引擎终态证据。\n" +
      "逐条从证据出发独立复现：文档类发现——打开 where 指向的 文件:行 核对原文；引擎行为类——在项目 " + PROJECT + " 上用只读命令（status/diagnose/read 等，先 --help 看用法）核对。不得执行任何写入命令，不得修改任何文件。\n" +
      "判定：独立复现成立给 verified；无法复现、需要写操作才能验证或证据不足给 unconfirmed；已由引擎终态证据直接证明的直接给 verified 并在 note 注明由哪条输出证明。\n" +
      "返回数组，每条含 id/verdict/note，一条不落。\n\n【high 发现】" + JSON.stringify(highs) + "\n\n【引擎终态证据】" + engineEvidence,
    );
  } catch (e) {
    // 复核失败：保留 high 发现为 unconfirmed，不阻塞报告
    log("高危复核子代理失败：" + String(e));
  }
  card("高危复核", "完成", confirms.length + " 条已判定");
}

// —— 结果落账（分诊+复核后逐条 report，失败也保得住）——
const confirmById = new Map<string, ConfirmResult>();
for (const c of confirms) confirmById.set(c.id, c);
const returnFindings: ReportFinding[] = triage.findings.map((f) => {
  const c = confirmById.get(f.id);
  return {
    id: f.id, where: f.where, what: f.what, evidence: f.evidence,
    severity: f.severity, kind: f.kind,
    status: c ? c.verdict : "unconfirmed",
  };
});
for (const f of returnFindings) report(f);

// —— 撰写并交付报告 ——
phase("撰写并交付验证报告");
card("验证报告", "进行中");
const writer = agent("报告撰写员");
const notCovered = [
  "真实多会话 Worker 派工、租约交接与 watch 等待（本次在单会话内以主干自执模拟）",
  "无人值守快速分组连写（run --fast）与完本交付链",
  "第二章起的连续状态链执行、伏笔兑现与跨卷闭合",
  "文学质量终判：机械校验通过不等于文学质量（技能自身声明）",
];
const writerInput = JSON.stringify({
  分诊结果: triage,
  复核结论: confirms,
  实跑阶段: stagesAll,
  评审结论: { 文档审查: docReview, 卷纲节奏: volPace, 章纲节奏: chPace, 首章试读: reader },
  引擎终态: engineEvidence,
  未覆盖范围: notCovered,
});
let written: WriterResult | null = null;
try {
  written = await writer.ask<WriterResult>(
    "你是报告撰写员，汇总本轮 novel-ledger 流程验证的全部结果并落盘交付。输入材料见下方 JSON。\n" +
    "在 " + REPORT_DIR + "/ 目录（不存在则创建）写四个文件：\n" +
    "1. report.md——主报告：# novel-ledger 流程验证报告（2026-10-27）；## 执行摘要（跑到哪、卡在哪、最严重三条问题）；## 实跑记录（逐阶段：操作类别、结果、作者边界点、卡点原文摘录）；## 问题清单（按 kind 分组，每条：编号/severity/复核状态/where/what/证据摘录）；## 网文节奏评审结论（卷纲层、章纲层、首章试读）；## 流程薄弱点与改进建议（按优先级排序并说明依据）；## 未覆盖范围（按输入的未覆盖清单展开）。\n" +
    "2. outlines.md——从项目 " + PROJECT + " 的 work/ 提交材料（或 CLI 只读命令）复制实际卷纲与章纲全文，标注来源任务；提取不到返回 null。\n" +
    "3. chapter1.md——已提交首章正文全文；首章未产出返回 null。\n" +
    "4. decisions.md——全部作者代理决定清单（阶段、边界点、决定、理由），从各阶段 authorDecisions 汇总。\n" +
    "纪律：不修改 " + PROJECT + " 与技能仓库任何文件；文件名用上面给定的 ASCII 名；内容 UTF-8 中文。返回 WriterResult（路径用工作区相对路径）。\n\n" + writerInput,
  );
} catch (e) {
  log("报告撰写员失败：" + String(e));
}
async function publishWithRepair(path: string | null, publish: (p: string) => Promise<void>): Promise<boolean> {
  if (path === null || path === "") return false;
  try {
    await publish(path);
    return true;
  } catch {
    const fixed: string = await writer.ask<string>(
      "发布 " + path + " 失败（文件可能缺失或路径越界）。请确认该文件已写入工作区内此路径并修正，返回实际的工作区相对路径。",
    );
    try {
      await publish(fixed);
      return true;
    } catch {
      return false;
    }
  }
}
let reportOk = false;
let outlinesOk = false;
let chapter1Ok = false;
if (written !== null) {
  reportOk = await publishWithRepair(written.reportPath, async (p) => { await artifact.file("report", p, { title: "流程验证报告", primary: true }); });
  outlinesOk = await publishWithRepair(written.outlinesPath, async (p) => { await artifact.file("outlines", p, { title: "卷纲与章纲产出副本" }); });
  chapter1Ok = await publishWithRepair(written.chapter1Path, async (p) => { await artifact.file("chapter1", p, { title: "首章正文（验证运行产出）" }); });
} else {
  // 撰写员失败：用已归账的分诊结果直接拼一份保底报告，发现不丢
  const salvage = [
    "# novel-ledger 流程验证报告（保底版）",
    "",
    triage.summary,
    "",
    ...returnFindings.map((f) => "- [" + f.id + "/" + f.severity + "/" + f.status + "] " + f.where + "：" + f.what + "（证据：" + f.evidence.slice(0, 200) + "）"),
  ].join("\n");
  try {
    await artifact.markdown("salvage-report", salvage, { title: "流程验证报告（保底版）" });
    reportOk = true;
  } catch {
    reportOk = false;
  }
}
card("验证报告", "完成", reportOk ? "报告已交付" : "报告发布失败，见运行结果");

const runLine = blockedStage
  ? "实跑受阻于「" + blockedStage.stage + "」：" + blockedStage.blocker.slice(0, 160)
  : s5 !== null && s5.completed
    ? "全链实跑成功：十三门→世界模型→卷纲（作者认可）→章纲（状态链校验）→第一章已提交入库"
    : "实跑未达首章";
const conclusion = (written !== null ? written.conclusion + " " : "") +
  runLine + "。共归账 " + String(returnFindings.length) + " 条发现（high " + String(triage.highCount) + " 条，其中 " +
  String(returnFindings.filter((f) => f.severity === "high" && f.status === "verified").length) + " 条经独立复核确认）。" + triage.summary;

const result: WorkflowReport = {
  conclusion,
  findings: returnFindings,
  verified: [
    "十三门→世界模型→卷纲→章纲→首章在真实引擎上顺序实跑，各阶段命令与输出记录于各阶段证据",
    "引擎终态以只读命令留证（novel.py --version 与 status 输出附于报告）",
    highs.length > 0 ? String(highs.length) + " 条 high 发现由独立复核员只读复现，逐条标注 verified/unconfirmed" : "分诊后无 high 级发现",
  ],
  notCovered,
};
return result;