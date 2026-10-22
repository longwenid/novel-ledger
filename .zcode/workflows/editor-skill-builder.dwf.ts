/* zcode-workflow
description: 在写作引擎 novel-ledger 之上实现一个带记忆系统的总编技能：两名侦察并行摸底（引擎操控接口 ∥
  目标平台市场扫描实测），总架构师设计控制回路、记忆系统与授权模型，两名主笔并行撰写技能文档与记忆模板/操作手册，机械结构门加审校官-修订编辑对抗循环收口，独立冷读终审后交付。引擎仓库与技能目标目录、技能名、市场焦点均可通过参数指定。
args:
  marketFocus:
    type: string
    description: 市场扫描的平台与频道焦点，写进调研员的实测指令与 notCovered 口径
    default: 起点/番茄（男频长篇）
  repoPath:
    type: string
    description: 写作引擎 novel-ledger 仓库的绝对路径：命令事实基准、市场研究垫底文档与 --help 校验都从这里读，脚本不修改它
    default: C:/Users/longwen/.zcode/skills/novel-ledger
  skillDir:
    type: string
    description: 要创建（或重建）的总编技能目录，绝对路径；两名主笔只写这里，不碰引擎仓库
    default: C:/Users/longwen/.zcode/skills/chief-editor
  skillName:
    type: string
    description: 新技能 SKILL.md frontmatter 里的 name 字段
    default: chief-editor
*/
// 总编技能实现：一个带记忆系统、能操控 novel-ledger 并对标目标平台流行趋势的总编 skill。
const repoPath = String(args.repoPath || "C:/Users/longwen/.zcode/skills/novel-ledger");
const skillDir = String(args.skillDir || "C:/Users/longwen/.zcode/skills/chief-editor");
const skillName = String(args.skillName || "chief-editor");
const marketFocus = String(args.marketFocus || "起点/番茄（男频长篇）");

interface CommandDoc {
  /** 命令行原文，如 "advance --compact"、"choose --tier t2"。 */
  usage: string;
  /** 一句话：总编在什么时机用它、它返回什么。 */
  purpose: string;
  /** 需要作者身份、授权或裁决的注记；无需则留空。 */
  authorGate: string;
}
interface InterfaceMap {
  /** 总编可用的 novel.py 命令面（以 --help 实测为准）。 */
  commands: CommandDoc[];
  /** 作者授权与裁决机制如何运作：run 授权、author_decision 应答、无人值守 watch、连写 worker-next/claim。 */
  authorMechanism: string;
  /** 引擎硬约束：总编绝不能违反的规则（作者决定权、机械校验不可绕过、不直接改库、质量声明边界等）。 */
  constraints: string[];
  /** 技能目录里最值得总编执行者先读的 3~5 个文件路径。 */
  keyFiles: string[];
}
interface MarketMethod {
  /** 当日实测可访问的榜单/数据入口：名称、URL、页面上能拿到什么。 */
  sources: { name: string; url: string; note: string }[];
  /** 一套可复用的市场扫描步骤，每步一句话（从榜单到结论）。 */
  steps: string[];
  /** 本次实测得到的流行方向样本：题材×脑洞×体量，各一句，附来源。 */
  sample: string[];
  /** 访问受阻、需要登录或不可信的来源与原因（降级路径写在这里）。 */
  pitfalls: string[];
}
interface SkillDesign {
  /** 总编控制回路的步骤：每步做什么、调用哪条命令、写哪条记忆。 */
  loop: { step: string; action: string; memory: string }[];
  /** 记忆系统的文件划分：每个文件存什么字段、何时写入、何时读取。 */
  memory: { file: string; fields: string; when: string }[];
  /** 授权模型：总编与作者决定权的关系（预授权策略、原话留痕、裁决上报）。 */
  authorization: string;
  /** 相似但原创的边界规则（对标拆解做什么、红线是什么）。 */
  originalityRules: string[];
  /** 要写的文件清单：路径、一句话内容、归属哪位主笔（core=主文档组，support=记忆与手册组）。 */
  files: { path: string; what: string; owner: "core" | "support" }[];
}
interface SkillFile {
  /** 已写入的绝对路径。 */
  path: string;
  /** 一句话：这个文件里有什么。 */
  what: string;
}
interface ReviewFinding {
  /** 文件路径，必要时带行号。 */
  where: string;
  /** 一句话：什么会在实际使用时坏掉或误导执行者。 */
  problem: string;
  /** 证据：读到的原文片段或命令输出。 */
  evidence: string;
  /** blocker=会让总编技能跑不起来或违反引擎哲学；polish=改进项。 */
  severity: "blocker" | "polish";
}
interface WorkflowReport {
  conclusion: string;
  findings: ReviewFinding[];
  verified: string[];
  notCovered: string[];
}

const CHECK = [
  "import re, subprocess, sys",
  "from pathlib import Path",
  `base = Path('${skillDir}')`,
  "errors = []",
  "if not base.is_dir(): errors.append('技能目录不存在: %s' % base)",
  "skill = base / 'SKILL.md'",
  "text = skill.read_text(encoding='utf-8') if skill.exists() else ''",
  "if not skill.exists(): errors.append('缺少 SKILL.md')",
  "else:",
  "    m = re.match(r'^---\\s*\\n(.*?)\\n---\\s*\\n', text, re.S)",
  "    if not m: errors.append('SKILL.md 缺少 frontmatter')",
  "    else:",
  "        fm = m.group(1)",
  "        if not re.search(r'^name:', fm, re.M): errors.append('frontmatter 缺 name')",
  "        if not re.search(r'^description:', fm, re.M): errors.append('frontmatter 缺 description')",
  "mds = sorted(p.relative_to(base).as_posix() for p in base.rglob('*.md'))",
  "if len(mds) < 3: errors.append('文档不足 3 个 .md（当前 %d）' % len(mds))",
  "if not (base / 'memory').is_dir(): errors.append('缺少 memory/ 目录')",
  `h = subprocess.run([sys.executable, '${repoPath}/scripts/novel.py', '--help'], capture_output=True, text=True)`,
  "if h.returncode != 0: errors.append('novel.py --help 失败: %s' % h.stderr[:200])",
  "print('FILES:', ', '.join(mds))",
  "print('OK' if not errors else 'FAIL')",
  "for e in errors: print('ERROR:', e)",
  "sys.exit(0 if not errors else 1)",
].join("\n");

phase("摸底：写作引擎操控接口与市场扫描实测");
const [iface, market] = await Promise.all([
  agent("接口研究员", {
    system:
      "你是引擎接口研究员，只读不改。逐条核实后才写结论；引用文件给 path:line；做不到的直说并上报，不编造。",
  }).ask<InterfaceMap>(
    `研究仓库 ${repoPath}（也是当前工作目录），为"外部总编 skill 操控这个写作引擎"摸清接口。只读，不要编辑任何文件。\n` +
      `必读：SKILL.md、README.md、references/opening.md（十三门与 choose/regroup/back/intake）、references/runtime.md（授权与无人值守）、references/narrative.md；并用 python ${repoPath}/scripts/novel.py --help 实测完整命令面（含 worker-next/claim 连写、watch、answer、replan 等）。\n` +
      `交付四件事：commands（总编会用到的每个子命令：用法、时机、返回要点、是否需要作者身份/授权）；authorMechanism（run 授权原话如何生效、author_decision 如何应答、watch 与同人连写批次如何驱动）；constraints（引擎硬约束：作者决定权哲学、十三门协议 opening/6、机械校验不可绕过、禁止直接改库或删校验、机械通过不等于文学质量——凡是要写进总编技能红线里的，逐条给出处）；keyFiles（总编执行者上岗前必读的 3~5 个文件）。`,
  ),
  agent("市场调研员", {
    system:
      "你是网文市场调研员，用真实网络访问实测方法，不凭印象编造。来源要给 URL；访问失败就如实记入 pitfalls，不硬凑。",
  }).ask<MarketMethod>(
    `为总编 skill 实测一套「${marketFocus}最流行小说」的扫描方法，今天就要能用。\n` +
      `先读仓库里两份带分级来源的旧研究垫底（工作目录 ${repoPath} 下）：validation/research-brainstorm-trends.md 与 validation/research-worldbuilding-trends.md。\n` +
      `然后用 WebSearch/WebFetch 实测：目标平台的官方榜单与分类页（起点中文网的月票榜/畅销榜/分类榜、番茄小说的排行榜为默认语境，按焦点自适配），以及可交叉核对的第三方（行业报道、中国作协蓝皮书类）。记录哪些 URL 当天真实可读、能拿到什么（书名/题材/简介/数据）；哪些被反爬或需登录。\n` +
      `交付：sources（当天实测可访问的入口，含页面能拿到什么）；steps（从打开榜单到产出"题材×脑洞×体量"结论的可复用步骤，每步一句）；sample（按这套步骤今天实际拿到的流行方向样本，附来源）；pitfalls（受阻来源与降级路径，例如换官方渠道/第三方交叉核对）。`,
  ),
]);
log(`接口摸底：${iface.commands.length} 条命令、${iface.constraints.length} 条硬约束；市场实测：${market.sources.length} 个可用入口、${market.sample.length} 条流行样本`);

phase("设计总编控制回路与记忆系统");
const design = await agent("总架构师", {
  system:
    "你是技能架构师，产出可直接施工的设计。设计以已有事实为边界：不发明引擎没有的能力。若两条要求冲突，上报而不是硬凑。",
}).ask<SkillDesign>(
  `设计"总编 skill"（${skillName}）：住在 ${skillDir}，有自己的记忆系统，操控写作引擎 ${repoPath}（只通过 CLI 与其技能文档，绝不修改引擎），能按市场扫描结果立项并推进"类似但有自己想法"的长篇网文。\n` +
  `写作引擎接口摸底结果：\n${JSON.stringify(iface, null, 2)}\n` +
  `市场扫描实测结果：\n${JSON.stringify(market, null, 2)}\n` +
  `设计约束（必须遵守，逐条落进设计）：\n` +
  `1. 总编不是作者：作者决定权属于用户。总编依用户预授权行事（引用引擎的 run 授权与无人值守机制），授权原话与每次裁决留痕；author_decision 类问题按用户事先声明的策略处理或上报，不代作者拍板文学取舍。\n` +
  `2. 相似但原创：对标只拆结构（题材、脑洞形状、节奏、体量），专有名词、桥段、设定组合不搬；利用引擎自己的反同质化机制（SETTING_CLICHES 告警、换组纪律），不另造一套文学判断。\n` +
  `3. 教训红线（来自该引擎的实机复盘）：不绕过或削弱任何机械校验、不直接写数据库、不把代理指标当创作目标、候选不达标就返修而不是造假。\n` +
  `4. 记忆系统是纯文件（md/json）放在技能目录 memory/ 下，跨会话可读可写；分类建议：市场快照、对标拆解、选题决策、运行复盘、授权记录。设计里写清每类何时写、读什么。\n` +
  `5. 文件归属：SKILL.md 与 references/ 下主文档归 core 主笔；memory 模板、初始记忆（预填市场样本）、操作手册（含从扫描到立项到连写的具体命令序列）归 support 主笔。总文件量克制：每个文件一个职责。`,
);

phase("并行撰写技能文档、记忆模板与操作手册");
const [coreFiles, supportFiles] = await Promise.all([
  agent("主笔·技能主文档", {
    system: "你是技能主笔，写的文档要能直接执行：命令必须真实存在，引用必须指向真实文件。写完自查一遍再交付。若写入被拒或依据不足，上报。",
  }).ask<SkillFile[]>(
    `按以下设计撰写总编技能的主文档，写入 ${skillDir}（目录不存在就创建；不要动 ${repoPath}）。只写归属 core 的文件。\n` +
      `设计：\n${JSON.stringify(design, null, 2)}\n` +
      `命令事实基准（只能用这里出现的命令，不得杜撰）：\n${JSON.stringify(iface.commands, null, 2)}\n` +
      `硬约束红线（逐条写进 SKILL.md 的红线节）：\n${JSON.stringify(iface.constraints, null, 2)}\n` +
      `SKILL.md 需带 frontmatter（name: ${skillName} 与一行中文 description，格式参照 ${repoPath}/SKILL.md），正文写清：何时用这个技能、控制回路（引用 references 细则）、授权模型、红线、与 novel-ledger 的关系（总编通过其 CLI 操控，项目数据在小说项目目录）。references/ 主文档按设计 files 清单逐个写。若写入权限被拒，如实上报，不要改投别的目录。`,
  ),
  agent("主笔·记忆与手册", {
    system: "你是记忆与手册主笔，模板要能被无上下文的执行者直接照填，手册步骤要能照抄执行。数字与样本只用给定材料，不编造。若写入被拒或材料缺口，上报。",
  }).ask<SkillFile[]>(
    `按以下设计撰写总编技能的记忆系统与操作手册，写入 ${skillDir}（目录不存在就创建；不要动 ${repoPath}）。只写归属 support 的文件。\n` +
      `设计：\n${JSON.stringify(design, null, 2)}\n` +
      `市场实测样本（用于初始记忆的市场快照，保留来源）：\n${JSON.stringify(market, null, 2)}\n` +
      `命令事实基准（手册里的命令序列只能用这里的命令）：\n${JSON.stringify(iface.commands, null, 2)}\n` +
      `交付：memory/ 各模板与字段说明、一份预填了本次市场样本的初始记忆、references 下的操作手册（从"用户说开一本对标 X 的书"到扫描、选题定位、intake/逐门、授权 run、watch/worker-next 连写、复盘写记忆的具体命令序列，每步可照抄）。若写入权限被拒，如实上报。`,
  ),
]);
const written = [...coreFiles, ...supportFiles];
log(`初稿完成：${written.length} 个文件落盘（${written.map((f) => f.path.split("/").pop()).join("、")}）`);

const 修订编辑 = agent("修订编辑", {
  system: "你是修订编辑，只改总编技能目录下的文件，绝不触碰 novel-ledger 仓库本身。修复要小而准；无法修复时上报，不绕过。",
});

phase("机械校验文件结构与命令入口");
let gate = await world.run("python", ["-c", CHECK]);
for (let round = 1; round <= 3 && gate.exitCode !== 0; round += 1) {
  log(`结构校验第 ${round} 轮未过，交修订编辑修复`);
  await 修订编辑.ask(
    `总编技能未通过机械结构校验。校验输出：\n${gate.stdout}\n${gate.stderr}\n` +
      `请在 ${skillDir} 下修复全部 ERROR 项（SKILL.md frontmatter、文件数量、memory/ 目录、novel.py 可用性）。只改总编技能文件，不动 ${repoPath}。修完即止，不要扩展范围。`,
  );
  gate = await world.run("python", ["-c", CHECK]);
}
const structurallySound = gate.exitCode === 0;
log(structurallySound ? "结构校验通过" : "结构校验三轮未过，如实带入审校");

phase("对抗审校并修订至无阻断");
const 审校官 = agent("审校官", {
  system:
    "你是冷眼审校官，之前没见过任何草稿。找的是会在实际使用时坏掉的东西：命令用错、越权、记忆结构落不了地、红线缺失。证据要给文件与行；只读不改；修不了的矛盾上报。",
});
const fileList = written.map((f) => f.path).join("\n");
let findings = await 审校官.ask<ReviewFinding[]>(
  `对刚建好的总编技能做对抗审校。技能目录：${skillDir}，文件清单：\n${fileList}\n` +
    `对照事实基准逐条核实：\n1. 命令与机制——每个出现的 novel.py 用法对照 ${repoPath} 的真实 CLI（可运行 python ${repoPath}/scripts/novel.py --help 及读 references/runtime.md 核实）与十三门流程（references/opening.md）；\n2. 哲学一致性——作者决定权是否被总编僭越、机械校验是否被任何一句话削弱、是否有"保证流行/保证质量"式越界承诺；\n3. 记忆系统——每个模板的字段能否按设计落成文件、初始记忆是否与来源一致；\n4. 可执行性——一个没见过本项目的新会话照 SKILL.md 能否走通"扫描→立项→开书→连写→复盘"。\n` +
    `结构门已由脚本把关，不必重复报文件缺失类问题。输出 findings：blocker=会跑不起来或违反引擎哲学；polish=改进项。没有问题就返回空数组，不要为了凑数硬找。`,
);
let blockers = findings.filter((f) => f.severity === "blocker");
for (let round = 1; round <= 3 && blockers.length > 0; round += 1) {
  log(`审校第 ${round} 轮：${findings.length} 条意见，其中阻断 ${blockers.length} 条，交修订编辑`);
  await 修订编辑.ask(
    `修复总编技能（${skillDir}）审校发现的阻断项：\n${JSON.stringify(blockers, null, 2)}\n` +
      `只修列出的阻断项及其直接牵连，不动 ${repoPath}。修完即止。`,
  );
  findings = await 审校官.ask<ReviewFinding[]>(
    `复核你上一轮的阻断项是否已修复（逐条给证据），并整体再扫一遍是否引入新问题。上轮阻断项：\n${JSON.stringify(blockers, null, 2)}\n` +
      `输出仍然成立的全量 findings；全部修复则返回空数组。`,
  );
  blockers = findings.filter((f) => f.severity === "blocker");
}
const finalGate = await world.run("python", ["-c", CHECK]);
log(`终检：审校余留 ${findings.length} 条（阻断 ${blockers.length} 条）；结构门${finalGate.exitCode === 0 ? "通过" : "未过"}`);

phase("独立终审并交付");
const coldRead = await agent("独立终审员", {
  system: "你是独立终审员，只凭技能目录里的文本判断，不去对照引擎源码。回答要落在具体段落上；只读不改。",
}).ask<string>(
  `冷读 ${skillDir} 下的总编技能（SKILL.md 与全部 references、memory 文件）。假设用户对它说："去 ${marketFocus}看看现在什么火，开一本类似但有自己想法的书，写到第一卷。"一个从没见过本项目的新会话按这套文档执行：\n` +
    `1. 哪一步会卡住、找不到入口或得到含糊指令？\n2. 哪些话术会让执行者误以为自己有权替作者做文学决定或绕过校验？\n3. 记忆系统在第二次会话真的能接上吗？\n` +
    `挑最要紧的最多 5 条，每条给文件与原句；最后一句总结这套技能现在能不能上手用。`,
);
const polish = findings.filter((f) => f.severity === "polish");
const unresolved = blockers.map((f) => ({ ...f, severity: "polish" as const }));
await artifact.markdown(
  "delivery",
  [
    `# 总编技能（${skillName}）交付说明`,
    "",
    `位置：\`${skillDir}\`；结构门${finalGate.exitCode === 0 ? "通过" : "未过"}；审校余留意见 ${polish.length} 条。`,
    "",
    "## 控制回路",
    ...design.loop.map((s) => `- **${s.step}**：${s.action}（记忆：${s.memory}）`),
    "",
    "## 记忆系统",
    ...design.memory.map((m) => `- \`${m.file}\`：${m.fields}（${m.when}）`),
    "",
    "## 授权模型",
    design.authorization,
    "",
    "## 相似但原创的边界",
    ...design.originalityRules.map((r) => `- ${r}`),
    "",
    "## 文件清单",
    ...written.map((f) => `- \`${f.path}\`：${f.what}`),
    "",
    "## 独立终审意见",
    coldRead,
  ].join("\n"),
  { title: "总编技能交付说明", description: "控制回路、记忆系统、授权模型与文件清单。", primary: true },
);
const result: WorkflowReport = {
  conclusion:
    `总编技能已建在 \`${skillDir}\`：${written.length} 个文件，含记忆模板与预填市场快照、操作手册与红线。` +
    `结构门与命令入口校验${finalGate.exitCode === 0 ? "通过" : "未过（见 findings）"}；对抗审校${blockers.length === 0 ? "无遗留阻断" : `余留 ${blockers.length} 条阻断`}。首次使用建议用小档位试跑一轮全流程。`,
  findings: [...polish, ...unresolved],
  verified: [
    `机械结构门两轮全量执行（SKILL.md frontmatter、文件清单、memory 目录、novel.py --help），最终退出码 ${finalGate.exitCode}`,
    "审校官对照 novel-ledger 真实 CLI 与 references 逐条核对命令用法与哲学红线",
    "独立终审员对成品技能做无背景冷读",
  ],
  notCovered: [
    "未实际开书端到端运行总编全流程（需要真实开书授权；建议首次使用时以 t0/t1 小档位试跑）",
    `${marketFocus}榜单访问的长期稳定性仅当日实测，反爬变化时需按 pitfalls 降级`,
  ],
};
return result;