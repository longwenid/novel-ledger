"""Genre menus, stable method labels, advisory watch lists and structural board copy.

Creative methods live in references/hatch.md; protocol fields stay in contracts.
"""

# Familiar public-setting labels. Advisory only: their presence never requires a new rule
# or blocks an author choice, just as a name-cliche warning does not ban a name.
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

# Stable method labels used for rotation and display. Creative guidance lives only in
# references/hatch.md; these labels carry no creative requirements.
LENSES = (
    '金手指倒推',
    '等级闭环',
    '对手换图',
    '硬通货',
    '身份马甲',
    '套路反打',
    '代价上限',
    '爽点倒推',
    '生态位垄断',
    '数据面板',
    '记忆点标签',
    '长线续航',
    '世界暗面',
    '纪元断层',
    '规则博弈',
    '非数值成长',
    '表层锚点',
    '主流正统',
)

# Stable volume-turn labels; explanations live in references/hatch.md.
VOLUME_TURNS = (
    '卷中转折',
    '代价递进',
    '对手揭露',
    '线索回收',
    '双线演进',
)

# What a structural option hands the author: a size ladder, never raw numbers to invent.
STRUCTURAL_CONTRACT = ('每个方案给 id、title 档位名（含卷数与字数区间）、premise 用一句话写清总字数、卷数、'
                       '每章字数与章数、tradeoff 说明这一档比相邻档多买到什么、少买到什么，value 照档位表逐字填。'
                       '不给 pitch/scene/driver，不写创意方法，不自行改动档位数字。')
