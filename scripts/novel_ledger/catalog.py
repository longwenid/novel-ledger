"""Content menus the opening boards and briefs render: genre catalog, brainstorm lenses,
volume turns, opening directions and their gate order, cliche watch lists and the tier
board's structural copy. Pure data, no dependencies; the protocol stays in contracts."""

# Combinations the current headliners already own: the public settings a new book can transplant
# for free, and therefore the ones a proposal has to prove it adds a rule to. Advisory only — the
# board shows the warning, the author keeps the choice (same severity as the name-cliche warning).
SETTING_CLICHES = ('序列', '途径', '克苏鲁', '克系', '系统', '幕后黑手', '第四天灾',
                   '诸天', '无限流', '模拟器', '签到', '存档重开')

# The male-channel category ladder shown whole when the author starts with no direction: a genre
# decision should begin from the full menu, not from three cold samples (the first gate of a real
# run regrouped twice before the author ever saw a category list).
GENRE_CATALOG = (
    ('玄幻', '东方超凡体系：境界、宗门与天材地宝，爽点是层层升格与越阶碾压。'),
    ('仙侠修真', '求长生的修行世道：功法、因果与劫数，爽点是道途逆旅与斩断宿命。'),
    ('都市异能', '现代城市里的超凡觉醒：能力、组织与隐秘规则，爽点是能力变现与身份反转。'),
    ('都市职场', '现实赛道里的逆袭：行业、编制或商战，爽点是步步登高与打脸收权。'),
    ('历史权谋', '王朝与庙堂的博弈：出身、站位与大势，爽点是以小博大局局翻盘。'),
    ('科幻末世', '技术或灾变后的新秩序：舰队、废土或进化，爽点是文明级翻盘与重建。'),
    ('悬疑探案', '灵异或罪案的层层解谜：规则怪谈或刑侦流，爽点是真相反转与恶有恶报。'),
    ('游戏电竞', '游戏系统或电竞赛场：副本、排位或全服竞争，爽点是登顶与版本答案。'),
    ('武侠', '江湖门派与恩怨情仇：武功、侠义与门派倾轧，爽点是快意恩仇与称雄江湖。'),
    ('军事战争', '铁血战场与军旅生涯：命令、兄弟与家国，爽点是战役翻盘与建功授勋。'),
    ('体育竞技', '赛场内外的热血成长：天赋、苦练与团队，爽点是夺冠路与绝地逆转。'),
    ('二次元轻小说', '日常幻想或异世界轻改：人设、梗与羁绊，爽点是设定趣味与情绪价值。'),
)

# AI-generated names cluster on these: the cliche surname x mystical single char pair covers most
# model-produced two-character names, and readers spot the batch instantly (a real run kept
# producing a specific rare char in new names). The combination is flagged as an advisory on the
# board; a hard ban stays the author's lexical rule.
CLICHE_SURNAMES = '叶林萧楚顾沈陆苏秦'

CLICHE_GIVEN = '辰尘轩言夜寒渊冥烬煜珩枫炎离砚'

# Setting-generation methods for the opening gates. A method is a way to make the next option
# genuinely different, not a label: the axis spends one slot of the choice, the method says how to
# vary it. Kept beside the contract fields because option quality is part of the author-facing
# contract.
#
# v3 rewrite: the earlier table was general literary brainstorming (mixing, inversion, binding,
# closure…) and a real run kept returning options the author rejected as 「格局太小」「不够网文」.
# The default direction is a male-channel long serial, and settings there are *built to spend*: an
# edge the world has to keep feeding, a ladder the reader can see, opponents that arrive with the
# next map, one hard currency somebody allocates, and enough headroom for a million characters.
# Each method therefore states what it must produce, and the third element is that check. The
# general craft discipline these replaced still applies — it lives in references/hatch.md.
LENSES = (
    ('金手指倒推', '先推演世界规则对所有人的后果，再找主角能介入的一处例外：它的升级材料、'
                   '克制它的对手、想抢它的组织，都要能从世界里持续产出；只给一个外挂不算。',
     '写清优势是什么、每次使用要什么、世界里有谁在供料、谁在抢它，以及它开篇三章第一次怎么用上。'),
    ('等级闭环', '把力量做成读者能预期的台阶（境界/段位/星级/职位），每级都有明确的升级条件与可量化'
                 '资源；条件写在世界里，读者随时能答"下一步要什么"。',
     '列出三级台阶：每级的名字、升级条件、拿到什么、卡在哪，以及谁在把守这个门槛。'),
    ('对手换图', '从个人困局追到利益网络、规则制定者与文明选择；旧对手的行动留下长期后果，新舞台'
                 '自带新资源与新规则；靠误会或临时加设定维持的梯度不算。',
     '写出前三级对手、每级挡住的具体利益，以及主角胜利后改变了什么规则、关系或可行动范围。'),
    ('硬通货', '从稀缺资源追问整个社会如何运转（能源/寿命/航路/知识/信用），谁分配它谁就有权，'
               '冲突围绕分配权与获取渠道展开；只当背景名词不算。',
     '写清资源名、来源、稀缺点、分配者，以及主角第一次为它出手的场合与代价。'),
    ('身份马甲', '主角在多个势力里有不同身份，制造扮猪吃虎、打脸与信息差；每个身份都要带暴露风险，'
                 '身份之间不能互相打架。',
     '写出至少两个身份、各自的用处、暴露会失去什么，以及第一次差点暴露的场合。'),
    ('套路反打', '在类型固有桥段上翻一层：读者熟悉的那一步照走，代价或结果反过来；为反而反、'
                 '让读者看不懂规则不算。',
     '先写清被反打的那条套路，再写反转后谁吃亏、爽点落在哪一句。'),
    ('代价上限', '主角的优势必须在开篇就带上可见的代价与明确的上限，代价改变后续抉择；'
                 '后期靠临时削弱或加强来维持平衡不算。',
     '写清代价的具体形态、上限在哪，以及它如何限制下一次选择。'),
    ('爽点倒推', '从读者要的兑现节奏倒推设定：短线兑现密度、章末钩与卷内高潮位置先定，设定为节奏'
                 '服务；设定好看而节奏空转不算。',
     '列出短线兑现的密度、两个卷内高潮的位置与开篇三章的第一个爽点。'),
    ('生态位垄断', '把故事放进一个被垄断的生态位：谁垄断什么、主角撬动哪一环、新平衡由谁付账；'
                   '只换皮不换生态位不算。',
     '写清垄断者、被撬动的环节，以及主角介入后的新秩序。'),
    ('数据面板', '把成长做成可核对的数字（属性、等级、任务、贡献、排行榜），让读者随时看见进步了'
                 '多少；数字要有人认账，随便写的等级不算。',
     '写清面板上会出现哪几项、每项怎么变，以及谁承认这张榜（排名对资源分配有什么实际后果）。'),
    ('记忆点标签', '给世界与主角造几个一眼能记住、能被读者复述的标签（称号、流派、道具、口号），'
                   '名字要能搜索、能出现在章末钩里。',
     '写出三个可传播的标签，说明它们第一次出现在哪一幕、由谁说出。'),
    ('长线续航', '设定必须撑住长篇：敌人、地图、资源与等级都留了继续加层的位置，不靠临时改设定'
                 '续命；三十章就把牌打光不算。',
     '写出第二卷与终局各新增什么层级，并说明它与你现在写的规则同源。'),
    # The opening/5 methods. The first twelve make a setting spendable; these five are what the
    # 2024-2026 evidence says a setting needs to still be there in volume six — a source for the
    # world's malice, an epoch above the current map, a rule the protagonist can play against, a
    # growth line that is not a number, and one visible carrier per backstage truth.
    ('世界暗面', '先定世界的恶意从哪来：外部不可名状（外神/天灾/系统），还是上层对人的剥削与制度失灵。'
                 '暗面必须持续供料——谁在收割、谁在承担、代价落到谁头上；换地图不换这条矛盾。',
     '写清恶意的来源、它今天正在拿走什么、主角第一次被它拿走的东西，以及至少两个也在承担它的人。'),
    ('纪元断层', '在世界上面压一层读者一时看不见的时间结构：上一个纪元留下了什么（遗迹、旧神、'
                 '遗留规则、还在运转的机构），主角每上一级就更靠近它；这一层不随地图更换而作废。',
     '写出上个纪元的名字与它留下的三样东西、现在谁在用它、以及主角在第几卷会碰到它。'),
    ('规则博弈', '把规则当对手而不是背景：主角对体系是顺从、利用还是对抗，至少一条读者看得见的规则'
                 '会被他利用或改写，改写的代价与反噬写清；规则不能被主角单方面宣布无效。',
     '写出被博弈的那条规则、主角的立场（顺从/利用/对抗）、第一次利用或改写的场合，以及反噬落在谁身上。'),
    ('非数值成长', '成长不只靠数值：认知迭代、心性、关系、真相掌握各给一条能兑现的线，让读者在'
                   '等级之外也能感到他变了；只更新面板不算成长。',
     '写出等级之外的两条成长线、各自第一次兑现的场合，以及它如何改变他下一步的选择。'),
    ('表层锚点', '选择与开局有关的底层设定，绑定一个读者能看见的载体（一件物、一个场景、一次冲突），'
                 '其余背景按揭示窗口展开；先展示异常或后果，再逐步说明原因。',
     '为开局关联的设定选一件物、一个场景或一次冲突，说明谁看见了什么、尚不知道什么。'),
    # The mainstream counterweight (field feedback 2026-10-21: every method pool leaned toward
    # high concepts, so an author asking for a normal book never saw a normal option). A proven
    # classic frame executed well is a direction of its own, not a fallback.
    ('主流正统', '走类型里被验证过的经典框架：读者熟悉的推进照常发生，新意放在执行、节奏与完成度上，'
                 '不放在翻新设定上；为怪而怪、让读者看不懂规则不算。',
     '写清采用哪条经典框架、这一版靠什么执行优势站住（节奏、人物、信息差、兑现密度），'
     '以及与同类平均线的差异落在哪一环。'),
)

# Volume-level turn methods: what makes a volume mid-point change direction instead of
# stacking everything on the finale. Used when planning the current volume.
VOLUME_TURNS = (
    ('卷中转折', '在卷半程安排关键翻盘，改变后半卷的对抗走向，不把高潮全堆在卷尾。'),
    ('代价递进', '卷内分段支付不可替代之物（名誉、靠山、同伴），换取核心真相。'),
    ('对手揭露', '前期明面阻力实为棋子，真正的对手在中期浮出水面。'),
    ('线索回收', '前期的闲笔或次要人物在卷尾成为决定胜负的关键手。'),
    ('双线演进', '核心对手在幕后推进自己的目标，与主角线交错施压。'),
)

# The default direction of the opening gates: male-channel long-form web fiction as it is
# serialised on 起点/番茄. It says how a cold option writer should shape a proposal, never what the
# author is allowed to choose — the author's own words, or an option already chosen, always win over
# this default, and a gate that conflicts with it is not a protocol error.
OPENING_DIRECTION = (
    '默认面向起点/番茄长篇：先有足以改变社会运行的大脑洞，再找具体人物的切入口；作者已选题材与限制优先。',
    '脑洞推演规则→日常后果→利益重组→长期冲突；奇名、外挂标签和境界数量不能替代这条因果链。',
    '世界先看全貌：空间边界、历史断层、多方文明或制度、持续矛盾与终极谜题相互关联；世界不只为主角服务。',
    '格局同时扩大行动能力、认知与责任：个人求生可以牵动秩序存亡，升级不靠反复换地图、加更强敌人。',
    '开篇从可感知的危机或异常进入，早期兑现一次重要行动、发现或关系变化；宏大历史通过物件、制度和冲突逐步显影。',
    '主角有可反复运用的稀缺优势，来源、条件、代价与上限由世界规则解释；旧人物、承诺和付出在后续阶段仍有作用。',
    '情绪兑现服从题材：成长、智斗、探索、建设、守护均可，不强制每三五章打脸或每卷换敌；语感服从作者所选文风。',
    '参考代表作品的构造方法，不复制专有体系、人物关系和标志性桥段；短篇只展开宏大世界的一个切面，现实题材不强加诸天与神明。',
)

# Per-gate emphasis. Every gate of the current gate set declares one, so the gate set cannot be
# redesigned without saying what the default direction means for each gate (a guard test derives
# that requirement from the gate table itself).
OPENING_DIRECTION_GATES = {
    'genre': '男频题材要连承诺一起给：明确读者期待的情绪体验，别在第一门锁死主角职业与局部事件。',
    'premise': '核心规则改变整个社会：给出普通人、组织与文明三种后果，及一条能贯穿全书的问题。',
    'voice': '决定人称、视角与阅读质地；紧张、诙谐、厚重或诗性均可，场景展示所选声音。',
    'scale': '体量决定本书展开多少世界层次，不等于世界本身有多大；本门只选档位。',
    'world': '把空间、历史、文明、长期矛盾与谜题连接成世界架构，位阶和资源由其生长。',
    'ladder': '从终局问题倒推抵达路径；每一级写清认知、责任与规则的变化，旧世界仍参与新冲突。',
    'origin': '在已定世界中选择主角来历；说明他与历史、文明或异常规则的联系及最初可知边界。',
    'edge': '优势是进入世界矛盾的方式；条件、供料和代价来自已定规则，不能单方面豁免规则。',
    'protagonist': '私人欲望与世界问题相连，但开局保留真实局限、行动理由及会付出代价的底线。',
    'relationships': '关系双方各有目标和所属秩序，能够协作也可能在同一危机中作出相反选择。',
    'opposition': '个人对手、利益网络与根本矛盾相连；明确各方为何无法轻易退让，以及胜利如何改变局面。',
    'payoff': '安排早期承诺、阶段回报与终局回应；真相揭开仍有行动代价，文明问题回到具体人的命运。',
    'title': '提炼独特世界意象或清晰卖点，短名与搜索式长名均可，不按一种标题模板限制题材。',
}

# What a structural option hands the author: a size ladder, never raw numbers to invent.
STRUCTURAL_CONTRACT = ('每个方案给 id、title 档位名（含卷数与字数区间）、premise 用一句话写清总字数、卷数、'
                       '每章字数与章数、tradeoff 说明这一档比相邻档多买到什么、少买到什么，value 照档位表逐字填。'
                       '不给 pitch/scene/driver，不写创意方法，不自行改动档位数字。')
