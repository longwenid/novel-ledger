# 卷纲与章纲全文（流程验证产出副本）

- **来源任务**：`2c198a12e64c4d9dbb88b1faf54ba06c`（stage=volume_outline，scope=volumes，t1 合并档 `merge_chapter_outline`：卷纲+章纲一次派工一份回执）
- **来源文件**：`C:/Users/longwen/.zcode/novel-ledger-process-validation/work/2c198a12e64c4d9dbb88b1faf54ba06c/result.json`（submit accepted=true / committed=true，confirm-volume 认可后在同一事务安装为生效章纲；第 1 章章纲已作为任务 5bbc81b8…（write/ch1）的冻结输入生效）
- **提取方式**：python 只读解析 `result.json` 的 `data.volumes`（2 卷）与 `data.chapters`（vol-1 第 1–25 章、vol-2 第 26–50 章），原样序列化（ensure_ascii=False，全部字段含空值原样保留）
- **纪律**：只读复制，未改动源项目与技能仓库任何既有文件

## 卷纲（data.volumes，共 2 卷）

### 卷 vol-1（巷口台区）

```json
{
  "id": "vol-1",
  "purpose": "挤走巷口黑市电贩，台区私供摊立起平价规矩，人命电免费写上黑板并被全巷认可",
  "stage": "巷口台区",
  "arc": "开局：江州江北老城电力巷，错峰名单上的永久末档，三天两停是日程不是事故。常亮是巷里的待业青年，白天打零工，夜里守瘫痪的父亲常守田，一台呼吸机连着老人的命。他的本事长在身上：掌心贴住金属接口，能把体力直接变成市电，一天约二十度，供多少亏多少力气，透支一次瘫半天。这三年度电怎么花，他心里有一本固定的排序：呼吸机排第一，谁也换不动；剩下的度电，先紧别人家的命，再谈自己的营生。停电夜他先把电续上呼吸机，又摸黑替巷口公用冰柜续了半格，被小卖部的秦姨隔着卷帘门看见那点光。摊子从窗台挪到巷口小黑板下，两块钱一度的平价电，白纸黑字，第一天就有人排队。挡在前面的是盘踞巷口的黑市电贩马六：柴油机加囤积的蓄电池，把老城的电抬到八块十块，人命机器的租金最狠；他的货源和通风报信来自片区电长周电长的默许分成，协查小赵被好处费喂着替他递消息。老城越垫底，黑市电越值钱，末档就是这门生意的护城河；常亮的平价私供一进场，砸的是这条链上三层的饭碗。双方行动：常亮靠平价和底细换信任。秦姨把巷里谁家有船、谁家有药、谁家孩子在江南上学一样样递过来，小卖部门口成了消息集散地；护士罗清上门骂醒他之后，把老城病人底册抄了一份拍在摊上，谁家什么机器、电池撑几个小时、紧急联系人是谁，一页一页清清楚楚，这本册子把他的二十度从凭感觉变成有账可依的排序。对面也没有闲着：马六先压价对拼，见他不动，就买通货栈断了常亮的零工，逼他白天没处挣钱夜里没电可卖；夜里泼柴油砸场子，把糊掉的黑板当街羞辱；再散出偷电的闲话，要把他的名声先泼脏。周电长两头拿捏：检修通道压着老线的报修单，登记簿压着错峰窗口的长短，谁不服就让谁家的窗口最短。常亮顶这些的手段只有两样：把电当众供出去让人看见，把规矩写成字让人认下来。转折：偷电闲话被一夜盯表当众拆穿，表没走一个字；罗清的病人底册一夜试跑，一户没漏，册子从一页纸变成巷子的先后序。全巷举手大会通过黑板三行规矩：人命电免费，平价电明码两块，供电顺序全楼举手定——定价权交出去，他只管供电，摊子从一个人的营生变成一条巷子的制度。马六明牌打光转暗手：囤电放空价牌守不住，被三句话当众点破倒卖；泼油的黑手被修车摊的旧监控和街坊记的脚程对了出来；小赵头一回开口，漏出囤电仓库不止一处、电长生意里有分成的话缝，周电长那句名单那年我就是这么把闸拉下来的醉话，把三年前的通宵拉到了眼前。老线在高温里打火，报修单压着不批，常亮看清光靠人情顶不住制度的手腕，报名考低压电工证，白天背题夜里供电，把零工彻底辞了；透支在杆下晕倒，被罗清拎进卫生站输液，父亲的命那一夜靠备用电池和邻居轮守撑过去——身体的本钱和全巷的靠他，两头都见了底。中段还有两处硬仗。一是登记簿：窗口排序把人命电器的户排到后头，常亮带底册当场对质，册上谁家什么机器清清楚楚，登记簿的号对不上人，排队的街坊一人一句把自家难处报出来，电长被顶得当场重排，底册从此压住了登记簿的笔。二是信息费：马六放话谁给常亮递消息就收谁的钱，秦姨顶住口风，递消息的人反而更多——老城的人情记账里，人命的事不谈钱，这条巷规比他的价牌老得多。常亮的电却始终只有二十度：白天背题、夜里供电、零工辞掉之后，铁盒和身体两头见底，他靠街坊轮流搭手才没垮下去。卷末高潮：老城预告停整一夜带两个白天，马六把最后的囤电抬到天价，专做人命机器的生意，钱到位就来电。常亮把底册摊开，把自家的电一格一格排进每户的钟点里，留给父亲的压到最后；按册送到第七户电见底，他把留给父亲的最后一格送了出去，人晕在楼道里。全巷没散，捏皮球的、抬电池的、守在呼吸机边的轮班守到天亮，死结解成互相欠着。天亮清算：小赵借巡查把仓库位置递上去，柴油机无备案、囤积电池整仓暂扣，马六被带走协查前撂话咬人，退回江北腹地；周电长连夜断掉常亮的检修通道自保，报修单原样压着；秦姨从他烧掉的旧物里抢出半本老登记簿，第一页的日期是三年前敲定第一版名单的那个通宵，签收人洇了半个姓。卷末局面：规矩立住、垄断破开、死结互解，现金攒下六千元，马六囤电清零；被断的检修通道和老登记簿两条线，一并带进下一卷。",
  "turns": [
    {
      "at": "开卷",
      "turn": "停电夜他把掌心的电第一次分给外人，暗手从此变成明摊，马六的价牌头一回没人看"
    },
    {
      "at": "第12章附近",
      "turn": "全巷举手立下黑板三行规矩，定价权交出去，他只管供电，摊子从人的营生变成巷子的制度"
    },
    {
      "at": "第17章附近",
      "turn": "泼柴油的黑手被旧监控和街坊脚程抓了现行，马六明面上的牌打光，转进阴处"
    },
    {
      "at": "第23章附近",
      "turn": "大停电夜他把留给父亲的最后一格电送出去，晕倒后全巷替他守呼吸机，死结解成互守"
    },
    {
      "at": "卷尾",
      "turn": "清算夜囤电整仓被暂扣，电长断通道自保，战场从巷口挪向制度，老登记簿带出下一卷的线索"
    }
  ],
  "climax": "大停电夜马六把最后囤电抬到天价，专做人命机器的生意，逼街坊在钱和命里选他；常亮按底册把电一户一户送到自己晕倒，全巷连夜捏皮球、抬电池替他守呼吸机；天亮后证据递上去，囤电仓库整仓被暂扣，价牌倒下，黑板三行规矩立成全巷认下的理，马六退回江北腹地。",
  "nodes": [
    {
      "id": "n1",
      "kind": "main",
      "purpose": "私供摊从窗台暗手到全巷举手立规",
      "ending_condition": "小黑板三行规矩经全巷举手通过",
      "required": true,
      "window": [
        1,
        12
      ]
    },
    {
      "id": "n2",
      "kind": "main",
      "purpose": "巷口黑市垄断被当面破开",
      "ending_condition": "囤电仓库被暂扣，柴油生意在巷口做不成",
      "required": true,
      "window": [
        5,
        25
      ]
    },
    {
      "id": "n3",
      "kind": "side",
      "purpose": "病人底册从一页纸变成巷子的先后序",
      "ending_condition": "窗口排队按底册压住登记簿乱序",
      "required": false,
      "window": [
        8,
        16
      ]
    },
    {
      "id": "n4",
      "kind": "hidden",
      "purpose": "名单第一版的当事人线索浮出",
      "ending_condition": "老登记簿第一页到手，问题带进下一卷",
      "required": false,
      "window": [
        2,
        25
      ]
    }
  ],
  "threads": [
    {
      "id": "t1",
      "kind": "main",
      "purpose": "供电摊立规矩线：从替人续电到全巷认下的平价规矩",
      "ending_condition": "规矩站稳，巷口垄断破局",
      "required": true
    },
    {
      "id": "t2",
      "kind": "hidden",
      "purpose": "名单末档之谜线：江北凭什么永远垫底",
      "ending_condition": "当事人线索到手，问题带进第二卷",
      "required": false,
      "continues": true
    }
  ],
  "hooks": [
    {
      "id": "h1",
      "text": "窗台接口旁那台呼吸机，和他一天二十度的死结：先保谁",
      "plant": [
        1,
        4
      ],
      "payoff": [
        20,
        25
      ],
      "required": true,
      "continues": false
    },
    {
      "id": "h2",
      "text": "周电长那句检修通道不让动就不让动——这只手什么时候真的攥下来",
      "plant": [
        5,
        8
      ],
      "payoff": [
        22,
        25
      ],
      "required": true,
      "continues": false
    },
    {
      "id": "h3",
      "text": "三年前那个通宵敲定的第一版名单：是谁、在哪、按什么把江北压成了末档",
      "plant": [
        2,
        4
      ],
      "payoff": [
        38,
        42
      ],
      "required": false,
      "continues": true
    },
    {
      "id": "h4",
      "text": "泼在黑板上的柴油是谁的手",
      "plant": [
        12,
        15
      ],
      "payoff": [
        16,
        19
      ],
      "required": true,
      "continues": false
    },
    {
      "id": "h5",
      "text": "罗清拍在摊上的病人底册：这本册子能管住一巷子人的先后吗",
      "plant": [
        8,
        11
      ],
      "payoff": [
        13,
        16
      ],
      "required": true,
      "continues": false
    },
    {
      "id": "h6",
      "text": "小赵那晚看见的掌心蓝光：他会说出去吗",
      "plant": [
        5,
        8
      ],
      "payoff": [
        16,
        20
      ],
      "required": true,
      "continues": false
    }
  ],
  "resources": [
    {
      "key": "现金",
      "from": 1200,
      "to": 6000,
      "reason": "平价电费与零工进项，扣去药钱器材与考证开销攒下"
    },
    {
      "key": "囤积电量",
      "from": 300,
      "to": 0,
      "reason": "放量对拼掏空一格，天价夜再放一格，仓库被查整仓清零"
    }
  ],
  "places": [],
  "characters": [
    {
      "entity": "chang-liang",
      "from": null,
      "to": {
        "desire": "守住黑板上的规矩和父亲的呼吸机，把摊子做成全巷离不了的正经营生",
        "stance": "规矩交给全巷举手，自己只管供电和底线，不再单打独斗",
        "relationship_focus": "从巷子欠他人情，变成全巷与他互相欠着、互相守着"
      },
      "reason": "底线经全巷举手写成规矩，死结解成互相欠着"
    }
  ],
  "relations": [],
  "reader_knowledge": [
    {
      "topic": "错峰名单第一版来历",
      "to": "hinted",
      "reason": "排队一场把为什么永远末档立成读者心里的问号"
    },
    {
      "topic": "周电长的分成网络",
      "to": "hinted",
      "reason": "小赵的话让读者先看见分成网络的影子"
    }
  ],
  "knowledge": [
    {
      "who": "chang-liang",
      "topic": "错峰名单第一版来历",
      "from": null,
      "to": "suspected",
      "reason": "登记簿第一页把疑点落成线索"
    },
    {
      "who": "chang-liang",
      "topic": "周电长与马六的分成",
      "from": null,
      "to": "suspected",
      "reason": "小赵的话让他把两个人拴在一起看"
    }
  ],
  "clock": {
    "advance_days": 40,
    "to": 40
  },
  "exit_state": "资源：常亮现金攒到六千元，马六囤积电量清零、再无库存可抬价；位置：马六退回江北老城腹地，常亮仍守电力巷；人物：常亮把人命电的底线守成全巷认下的规矩，马六明牌尽失退守阴处；知情：分成网络被常亮看破，名单来历在老登记簿上落成线索；线路：供电摊规矩线收口，名单之谜线开着口带进下一卷；主线时钟累计四十天。",
  "style": {
    "trend": "开卷贴着停电夜的巷口走，短句白话，对白只挑价码与人情；中段排队、盯表、对质这些场子对白升到三成五，句子越打越短；卷尾大会与停电夜放慢，长句落在人心上，热闹底下垫着疲惫。",
    "window": {}
  }
}
```

### 卷 vol-2（自治台区）

```json
{
  "id": "vol-2",
  "purpose": "街道共建的台区试点落地挂牌，样本进供电简报；错峰名单的来历揭开，老城自己排自己的序",
  "stage": "自治台区",
  "arc": "开局承接：巷口的规矩立住了，代价一起压过来。周电长断了检修通道，老线报修无门，巷子中段的线路在高温里出过火；协查正式立案查违规转供电，摊子的接线板被暂扣，黑板上的明码电成了案卷里的字；马六退回江北腹地扬言回来，街坊把自家的电池悄悄备了双份。常亮的黑板管得住人心，管不住制度的手：私供在纸面上仍是违规转供电，他给摊子护身的唯一办法，是给规矩找一个合法的名分。周电长那边连夜烧旧物，秦姨从火盆里抢出半本老登记簿，第一页的日期和洇了半个姓的签收人，把三年前那个通宵又拽回桌上。摊子这边的处境同样拧着：巷子里越认这套规矩，法理上悬空的分量就越重——认的人越多，一旦被拆，塌下来的也越多。转折一：街道办事处的高志远下巷走访，本子上的指标压了一路，却在小黑板和底册前站住——三行规矩、排队的秩序、一户不漏的册子，比他台账里任何一页都齐整。他连夜写方案，共建试点递到手里：街道出章、供电所出通道、经费与检修一并解决，换试点指标和挂牌日的展示。名分与套一起递来。小卖部夜议摊开算：秦姨算人心，罗清算病人，常亮算电，底线定成人命电第一这一条写进协议才谈。指标拉锯随之而来：街道要零停电的展示窗口、要照宣传稿排的时刻表、要好看的数据；常亮只给实数，宁可不要挂牌也不能造假，经费停了一半也不松口——他的账很清楚，数据造一次假，黑板三个字的信用就再也回不来。同一时间，小赵被抽给督查组摸底，两头烫脚：马六的好处费还没退干净，督查要的实情他最清楚；他在摊上蹲了半宿，问出一句要是把话说出去我算什么，常亮答算老城的人。转折二：高温里老线终于打火，检修通道还是没批。常亮揣着新考下的低压电工证，借施工队名义带人把中段线路整段换掉——这是他头一回用合法的手办成事，杆上下来手心全是汗，章比话硬。马六把柴油和短接线押在挂牌那一天，要让自治在全城眼前停电，试点一砸，规矩跟着陪葬；巷口的生面孔和柴油味被修车摊老人的眼色记下，轮值街坊把踩点的脚程一五一十记满一页。督查组进驻街道，摊牌三场一场比一场深：头一场问试点真伪与黑市根源，实数与台账当场对不齐；第二场摆到巷口，秦姨把老登记簿放上桌，第一页的日期与签收人对上三年前敲定名单的通宵——江北压末档换江南保产，洇掉的姓就在督查名单边上；第三场名单来历全盘揭开：权重三年没动一行，护着末档的不是哪一个人，是每个从末档里捞到好处的位置——电长的执行权、电贩的护城河、拿名单当政绩的章。问题从为什么是我们，变成秩序该由谁定，常亮心里落了地：名单动不了，能动的只有台区里这套自己排的序，而这正是他要接的下一仗。转折三：小赵退了好处费当众作证，协查眼线、囤电仓库、电长分成的走法一样一样摆上桌面，周电长被调离台区，分成网络连根拔，老线档案与检修通道划进试点协议附件，断了两个月的报修单批下来——通道这件事的收口，不再系在哪一个人的心情上，而是写进了章里。挂牌前夜全巷演练，展示线路真被人动了手脚，半条巷子骤黑：没人喊，底册启动，自筹电池上线，黑板顺序一格一格来，一个钟头把供电原样续回去，督查的人站在黑地里看完全程，在记录上写下非预案、成立；马六人赃并获，柴油短接线旧车一齐被扣，黑市在老城断根清街。协议谈判一寸一寸磨：常亮要人命电第一写进正文、窗口顺序由台区议定、检修通道入附件；街道要指标、要展示、要政绩署名；两边在挂牌日的倒逼下各让半步——街道拿实数据换样本，常亮拿展示换通道，谁也没拿到全部。卷末：试点协议定稿，错峰名单不动，台区内的窗口顺序、人命电第一、平价私供一条一条写进协议和小黑板，定价仍归全台区举手；罗清当众掀出常亮瞒下的晕倒旧事，全巷投票给他定下休息日——把定价权交出去时被排掉的第一个东西，他的休息，由全巷举手还给了他；自治台区试点挂牌，样本进了供电简报，别的街道打电话来抄做法；牌子立在巷口，督查临走留话样本要一直立着。他还是一天二十度的人，巷子已经离不开他，他也不再是那谁家小子。",
  "turns": [
    {
      "at": "开卷",
      "turn": "通道被断、协查立案、接线板被扣，规矩立在巷里，法却不在他这边"
    },
    {
      "at": "第30章附近",
      "turn": "街道抛出共建试点，合法的名分和指标的套一起递过来，接不接都要付代价"
    },
    {
      "at": "第36章附近",
      "turn": "老线打火通道无门，他持证换下整段线路，头一回用合法的手办成事"
    },
    {
      "at": "第40章附近",
      "turn": "老登记簿对上敲定之夜，名单来历与护着末档的利益在摊牌桌上全盘揭开"
    },
    {
      "at": "第44章附近",
      "turn": "挂牌前夜的破坏反被底册和自筹电池演成自治的实证，停电成了最硬的证明"
    },
    {
      "at": "卷尾",
      "turn": "试点挂牌样本外传，错峰名单不动，老城自己排自己的序，常亮定了休息日"
    }
  ],
  "climax": "督查摊牌会上老登记簿对上三年前敲定名单的通宵，江北压末档换江南保产、权重三年未动的全盘真相揭开，护着末档的利益一层层站到桌面上；挂牌前夜展示线路被动手脚，半条巷子骤黑，没人喊，底册启动自筹电池上线，一个钟头把供电原样续回，自治在全城眼前站住；随后马六人赃并获，黑市在老城断根清街。",
  "nodes": [
    {
      "id": "n5",
      "kind": "main",
      "purpose": "共建试点从街道提案走到挂牌",
      "ending_condition": "自治台区试点挂牌，样本进供电简报",
      "required": true,
      "window": [
        29,
        50
      ]
    },
    {
      "id": "n6",
      "kind": "main",
      "purpose": "错峰名单第一版的来历揭开",
      "ending_condition": "敲定之夜与护着末档的利益摆在桌面",
      "required": true,
      "window": [
        26,
        42
      ]
    },
    {
      "id": "n7",
      "kind": "side",
      "purpose": "小赵从眼线走进体系正规名录",
      "ending_condition": "作证退了好处费，进了网格协理名录",
      "required": false,
      "window": [
        29,
        45
      ]
    },
    {
      "id": "n8",
      "kind": "side",
      "purpose": "马六最后一搏落网清街",
      "ending_condition": "人赃并获，黑市电贩被清出本街",
      "required": false,
      "window": [
        36,
        46
      ]
    }
  ],
  "threads": [
    {
      "id": "t4",
      "kind": "main",
      "purpose": "试点落地线：从指标拉锯到挂牌样本",
      "ending_condition": "试点挂牌，样本进简报",
      "required": true
    },
    {
      "id": "t5",
      "kind": "side",
      "purpose": "名单真相线：登记簿对上敲定之夜",
      "ending_condition": "第一版名单的来历全貌揭开",
      "required": true
    },
    {
      "id": "t6",
      "kind": "side",
      "purpose": "体系裂缝线：小赵从眼线到证言",
      "ending_condition": "证言落地，裂缝变成常亮的缝",
      "required": true
    }
  ],
  "hooks": [
    {
      "id": "h7",
      "text": "老登记簿第一页洇掉半个姓的签收人：他到底是谁",
      "plant": [
        26,
        30
      ],
      "payoff": [
        38,
        42
      ],
      "required": true,
      "continues": false
    },
    {
      "id": "h8",
      "text": "挂牌日零停电的表态：真停电了这一局怎么收",
      "plant": [
        32,
        35
      ],
      "payoff": [
        42,
        46
      ],
      "required": true,
      "continues": false
    },
    {
      "id": "h9",
      "text": "常亮瞒下的晕倒旧事：什么时候被当众掀开",
      "plant": [
        40,
        43
      ],
      "payoff": [
        46,
        50
      ],
      "required": true,
      "continues": false
    },
    {
      "id": "h10",
      "text": "巷口回来的柴油味：马六赌的是哪一天动手",
      "plant": [
        36,
        39
      ],
      "payoff": [
        43,
        47
      ],
      "required": true,
      "continues": false
    }
  ],
  "resources": [
    {
      "key": "现金",
      "from": 6000,
      "to": 9300,
      "reason": "协议电费稳进，挂牌筹备与自筹电池的开销对冲"
    }
  ],
  "places": [],
  "characters": [
    {
      "entity": "chang-liang",
      "from": {
        "desire": "守住黑板上的规矩和父亲的呼吸机，把摊子做成全巷离不了的正经营生",
        "stance": "规矩交给全巷举手，自己只管供电和底线，不再单打独斗",
        "relationship_focus": "从巷子欠他人情，变成全巷与他互相欠着、互相守着"
      },
      "to": {
        "desire": "错峰名单不动，就把这片台区的序排好，让巷子离不开的是规矩不是他一身力气",
        "stance": "供电交给网和协议，自己只守人命电那条线和休息日",
        "relationship_focus": "从常师傅变成这片街区的基础，父亲与全巷同守一份规矩"
      },
      "reason": "从守摊人变成守规矩的人，把自己活成街区的基础"
    }
  ],
  "relations": [],
  "reader_knowledge": [
    {
      "topic": "错峰名单第一版来历",
      "to": "confirmed",
      "reason": "敲定之夜与护着末档的利益在摊牌会上全盘托出"
    },
    {
      "topic": "周电长的分成网络",
      "to": "confirmed",
      "reason": "证词把分成网络钉死在桌面"
    }
  ],
  "knowledge": [
    {
      "who": "chang-liang",
      "topic": "错峰名单第一版来历",
      "from": "suspected",
      "to": "confirmed",
      "reason": "摊牌会上听见全貌，疑点落定"
    },
    {
      "who": "chang-liang",
      "topic": "周电长与马六的分成",
      "from": "suspected",
      "to": "confirmed",
      "reason": "证词把当年那笔钱的走法坐实"
    }
  ],
  "clock": {
    "advance_days": 45,
    "to": 85
  },
  "exit_state": "资源：常亮现金攒到九千三百元，协议电费让摊子进项稳下来；位置：全巷各归各位，马六出局离街，周电长调离台区；人物：常亮从常师傅变成这片街区的基础，小赵站进体系，马六认栽出局；知情：名单来历对全巷揭开，分成网络连根拔；线路：试点线、真相线、体系线全部收口，样本立在供电简报里；主线时钟累计八十五天。",
  "style": {
    "trend": "市井白话承接前卷，公文与督查话术进场，冷热两路语气对撞出制度感；摊牌场短句交锋越收越紧，挂牌与休息日两场转舒缓放长；对白升到四成上下，叙述给结尾留出余温。",
    "window": {}
  }
}
```

## 章纲（data.chapters，共 50 章）

### vol-1（第 1–25 章）

#### 第 1 章

```json
{
  "chapter": 1,
  "synopsis": "错峰窗口临时跳票，电力巷整巷黑下来。父亲呼吸机的电池只够半小时，常亮把手贴上窗台的金属接口，掌心的电先续上呼吸机，又摸黑替巷口公用冰柜续了半格。马六的柴油机在巷口轰起来，八块钱一度的价牌挂上路灯。秦姨隔着小卖部卷帘门，看见了他窗台上那点光。电送出去，人乏得发虚，他没让第二个人看见。",
  "story_events": [],
  "reader_effect": null,
  "timeline": null,
  "beats": [],
  "role": null,
  "plot": {
    "beat": "停电夜常亮把掌心的电第一次分给外人，救下冰柜，被秦姨看破",
    "nodes": [
      {
        "node": "n1",
        "after": "seeded",
        "outcome": "窗台暗手替人续电，摊子的种子埋下"
      }
    ],
    "threads": [
      {
        "thread": "t1",
        "after": "active",
        "reason": "替人续电的暗线开场"
      }
    ]
  },
  "resources": [],
  "places": [],
  "knowledge": [
    {
      "who": "qin-yi",
      "topic": "常亮的供电本事",
      "from": null,
      "to": "suspected",
      "reason": "隔着卷帘门看见窗台接口那点光"
    }
  ],
  "characters": [],
  "relations": [],
  "clock": {
    "advance_days": 2
  },
  "enter": [
    {
      "kind": "knowledge",
      "key": "qin-yi:常亮的供电本事",
      "expected": null
    },
    {
      "kind": "node",
      "key": "n1",
      "expected": null
    },
    {
      "kind": "thread",
      "key": "t1",
      "expected": null
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 0
    }
  ],
  "exit": [
    {
      "kind": "knowledge",
      "key": "qin-yi:常亮的供电本事",
      "expected": "suspected"
    },
    {
      "kind": "node",
      "key": "n1",
      "expected": "seeded"
    },
    {
      "kind": "thread",
      "key": "t1",
      "expected": "active"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 2
    }
  ],
  "disclosures": [],
  "world_refs": [
    "everyday:evd-life-machines",
    "everyday:evd-alley-night",
    "geography:geo-dianlixiang"
  ],
  "new_entities": [],
  "hooks": [],
  "hook_refs": [],
  "reader_refs": [],
  "history_refs": [],
  "scenes": [],
  "pacing": {},
  "style": {
    "pov": "第三人称主角中心",
    "rhythm": "夜戏起手，短句压着人声，先见电光后见人",
    "notes": ""
  },
  "dependency_coverage": "partial",
  "reading_coverage": "partial",
  "reading_refs": [],
  "understanding_refs": []
}
```

#### 第 2 章

```json
{
  "chapter": 2,
  "synopsis": "白天配电房外排队登记，谁家几号全凭电长一支笔。常亮替三户人命电器续了电，队里有人开始打听他。马六翻高价牌，放话巷里的电只能从他手里出。常亮问秦姨，江北凭什么永远排在末档，她说三年前定名单那晚没人说得清细节，只记得那年夏天热得邪门。他把这个没答案的问题记下了。",
  "story_events": [],
  "reader_effect": null,
  "timeline": null,
  "beats": [],
  "role": null,
  "plot": {
    "beat": "排队场上他为人命电器续电，把名单之问记在心里",
    "nodes": [
      {
        "node": "n4",
        "after": "seeded",
        "outcome": "名单之问在队里立起来"
      }
    ],
    "threads": [
      {
        "thread": "t2",
        "after": "active",
        "reason": "末档之谜线开场"
      }
    ]
  },
  "resources": [],
  "places": [],
  "knowledge": [
    {
      "who": "chang-liang",
      "topic": "错峰名单第一版来历",
      "from": null,
      "to": "hinted",
      "reason": "排队一场让他起疑：末档凭什么定死"
    }
  ],
  "characters": [],
  "relations": [],
  "clock": {
    "advance_days": 1
  },
  "enter": [
    {
      "kind": "knowledge",
      "key": "chang-liang:错峰名单第一版来历",
      "expected": null
    },
    {
      "kind": "node",
      "key": "n4",
      "expected": null
    },
    {
      "kind": "thread",
      "key": "t2",
      "expected": null
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 2
    }
  ],
  "exit": [
    {
      "kind": "knowledge",
      "key": "chang-liang:错峰名单第一版来历",
      "expected": "hinted"
    },
    {
      "kind": "node",
      "key": "n4",
      "expected": "seeded"
    },
    {
      "kind": "thread",
      "key": "t2",
      "expected": "active"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 3
    }
  ],
  "disclosures": [
    {
      "topic": "错峰名单第一版来历",
      "after": "hinted",
      "note": "排队一场把为什么永远末档立成读者心里的问号"
    }
  ],
  "world_refs": [
    "everyday:evd-window-queue",
    "rules:rule-window",
    "characters:char-zhou-dianzhang"
  ],
  "new_entities": [],
  "hooks": [
    {
      "hook": "h1",
      "action": "plant",
      "note": "窗台接口旁的呼吸机和他一天二十度的量摆在一起"
    },
    {
      "hook": "h3",
      "action": "plant",
      "note": "队里没人答得上第一版名单怎么定的"
    }
  ],
  "hook_refs": [],
  "reader_refs": [],
  "history_refs": [],
  "scenes": [],
  "pacing": {},
  "style": {
    "pov": "第三人称主角中心",
    "rhythm": "白日群像，对白密集，队里七嘴八舌",
    "notes": ""
  },
  "dependency_coverage": "partial",
  "reading_coverage": "partial",
  "reading_refs": [],
  "understanding_refs": []
}
```

#### 第 3 章

```json
{
  "chapter": 3,
  "synopsis": "秦姨把巷里谁家有船、谁家有药一样样说给常亮，摊子从窗台挪到巷口小黑板底下。第一笔平价电钱收进铁盒，两块钱一度，白纸黑字。马六的手下来踹场，话没说完就被秦姨两句口风顶了回去，排队的街坊没散。摊子立住了，麻烦也跟着来了。",
  "story_events": [],
  "reader_effect": null,
  "timeline": null,
  "beats": [],
  "role": null,
  "plot": {
    "beat": "摊子从窗台挪到黑板下，第一笔平价电钱收进",
    "nodes": [],
    "threads": []
  },
  "resources": [
    {
      "key": "现金",
      "from": 1200,
      "to": 1500,
      "reason": "平价电费与开销的净进项"
    }
  ],
  "places": [],
  "knowledge": [
    {
      "who": "qin-yi",
      "topic": "常亮的供电本事",
      "from": "suspected",
      "to": "confirmed",
      "reason": "当面看他续电，口风从此守住"
    }
  ],
  "characters": [],
  "relations": [],
  "clock": {
    "advance_days": 1
  },
  "enter": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 1200
    },
    {
      "kind": "knowledge",
      "key": "qin-yi:常亮的供电本事",
      "expected": "suspected"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 3
    }
  ],
  "exit": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 1500
    },
    {
      "kind": "knowledge",
      "key": "qin-yi:常亮的供电本事",
      "expected": "confirmed"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 4
    }
  ],
  "disclosures": [],
  "world_refs": [
    "characters:char-qin-yi",
    "factions:fact-oldtown-mutual",
    "geography:geo-dianlixiang"
  ],
  "new_entities": [],
  "hooks": [],
  "hook_refs": [],
  "reader_refs": [],
  "history_refs": [],
  "scenes": [],
  "pacing": {},
  "style": {
    "pov": "第三人称主角中心",
    "rhythm": "短促利落，价码与人情对白来回",
    "notes": ""
  },
  "dependency_coverage": "partial",
  "reading_coverage": "partial",
  "reading_refs": [],
  "understanding_refs": []
}
```

#### 第 4 章

```json
{
  "chapter": 4,
  "synopsis": "邻巷的人循着消息找来，摊子头一回供不应求。马六不接价，转头买通货栈断了常亮的零工，逼他白天没处挣钱夜里没电可卖。常亮白天扛大包夜里守摊，两头的力气见底。他不涨价，把有限的电按急缓排开，自己晚饭减成一碗光面。",
  "story_events": [],
  "reader_effect": null,
  "timeline": null,
  "beats": [],
  "role": null,
  "plot": {
    "beat": "马六断他零工，常亮两头熬着不涨价",
    "nodes": [],
    "threads": []
  },
  "resources": [
    {
      "key": "现金",
      "from": 1500,
      "to": 1900,
      "reason": "平价电费与开销的净进项"
    }
  ],
  "places": [],
  "knowledge": [
    {
      "who": "ma-liu",
      "topic": "常亮的供电来路",
      "from": null,
      "to": "suspected",
      "reason": "便宜得邪门，派人盯了几晚没盯出来源"
    }
  ],
  "characters": [],
  "relations": [],
  "clock": {
    "advance_days": 2
  },
  "enter": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 1500
    },
    {
      "kind": "knowledge",
      "key": "ma-liu:常亮的供电来路",
      "expected": null
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 4
    }
  ],
  "exit": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 1900
    },
    {
      "kind": "knowledge",
      "key": "ma-liu:常亮的供电来路",
      "expected": "suspected"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 6
    }
  ],
  "disclosures": [],
  "world_refs": [
    "economy:econ-black-power",
    "mechanisms:mech-body-power",
    "characters:char-ma-liu"
  ],
  "new_entities": [],
  "hooks": [],
  "hook_refs": [],
  "reader_refs": [],
  "history_refs": [],
  "scenes": [],
  "pacing": {},
  "style": {
    "pov": "第三人称主角中心",
    "rhythm": "生活流叙述垫底，疲惫感渗进句子里",
    "notes": ""
  },
  "dependency_coverage": "partial",
  "reading_coverage": "partial",
  "reading_refs": [],
  "understanding_refs": []
}
```

#### 第 5 章

```json
{
  "chapter": 5,
  "synopsis": "巷子里起了闲话，说常亮的电是偷来的。排队的人看他眼神变了。常亮当众请人盯着电表看一晚：表没走一个字。电的来路说不清，但不是偷。马六的脸挂不住，暗地里把价又抬了一格，等停电拉长再收网。当晚他把电表的走字抄在小黑板角上，第二天谁来看都给看。",
  "story_events": [],
  "reader_effect": null,
  "timeline": null,
  "beats": [],
  "role": null,
  "plot": {
    "beat": "偷电闲话被一夜盯表当众拆穿",
    "nodes": [
      {
        "node": "n2",
        "after": "seeded",
        "outcome": "垄断与平价私供正面对上"
      }
    ],
    "threads": []
  },
  "resources": [
    {
      "key": "现金",
      "from": 1900,
      "to": 2200,
      "reason": "平价电费与开销的净进项"
    }
  ],
  "places": [],
  "knowledge": [],
  "characters": [],
  "relations": [],
  "clock": {
    "advance_days": 2
  },
  "enter": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 1900
    },
    {
      "kind": "node",
      "key": "n2",
      "expected": null
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 6
    }
  ],
  "exit": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 2200
    },
    {
      "kind": "node",
      "key": "n2",
      "expected": "seeded"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 8
    }
  ],
  "disclosures": [],
  "world_refs": [
    "rules:rule-private-supply",
    "characters:char-ma-liu",
    "society:soc-oldtown-order"
  ],
  "new_entities": [],
  "hooks": [],
  "hook_refs": [],
  "reader_refs": [],
  "history_refs": [],
  "scenes": [],
  "pacing": {},
  "style": {
    "pov": "第三人称主角中心",
    "rhythm": "对峙场短句交锋，静场只留电表声",
    "notes": ""
  },
  "dependency_coverage": "partial",
  "reading_coverage": "partial",
  "reading_refs": [],
  "understanding_refs": []
}
```

#### 第 6 章

```json
{
  "chapter": 6,
  "synopsis": "协查小赵奉命来查偷电，夜里巡到摊前，正看见常亮掌心贴着接口往外送电，电光是蓝的。他愣在当场，登记本上只写了查无实据。周电长把常亮叫到配电房，敲打他一句：巷子的老线归检修通道管，他说不让动就不让动。常亮听懂了，这是拿全巷的线捏他。",
  "story_events": [],
  "reader_effect": null,
  "timeline": null,
  "beats": [],
  "role": null,
  "plot": {
    "beat": "小赵夜巡撞见掌心蓝光，周电长拿检修通道敲打",
    "nodes": [],
    "threads": [
      {
        "thread": "t1",
        "after": "active",
        "reason": "通道敲打直接压在摊子头上"
      }
    ]
  },
  "resources": [],
  "places": [],
  "knowledge": [
    {
      "who": "xiao-zhao",
      "topic": "常亮的供电来路",
      "from": null,
      "to": "suspected",
      "reason": "亲眼看见蓝光，没敢往上报"
    },
    {
      "who": "zhou-dianzhang",
      "topic": "常亮的供电来路",
      "from": null,
      "to": "suspected",
      "reason": "表没走字电却便宜，猜到一半"
    }
  ],
  "characters": [],
  "relations": [],
  "clock": {
    "advance_days": 1
  },
  "enter": [
    {
      "kind": "knowledge",
      "key": "xiao-zhao:常亮的供电来路",
      "expected": null
    },
    {
      "kind": "knowledge",
      "key": "zhou-dianzhang:常亮的供电来路",
      "expected": null
    },
    {
      "kind": "thread",
      "key": "t1",
      "expected": "active"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 8
    }
  ],
  "exit": [
    {
      "kind": "knowledge",
      "key": "xiao-zhao:常亮的供电来路",
      "expected": "suspected"
    },
    {
      "kind": "knowledge",
      "key": "zhou-dianzhang:常亮的供电来路",
      "expected": "suspected"
    },
    {
      "kind": "thread",
      "key": "t1",
      "expected": "active"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 9
    }
  ],
  "disclosures": [],
  "world_refs": [
    "characters:char-xiao-zhao",
    "characters:char-zhou-dianzhang",
    "rules:rule-private-supply"
  ],
  "new_entities": [],
  "hooks": [
    {
      "hook": "h2",
      "action": "plant",
      "note": "不让动就不让动，那只手先悬着"
    },
    {
      "hook": "h6",
      "action": "plant",
      "note": "蓝光看进眼里，本子上只写查无实据"
    }
  ],
  "hook_refs": [],
  "reader_refs": [],
  "history_refs": [],
  "scenes": [],
  "pacing": {},
  "style": {
    "pov": "第三人称主角中心",
    "rhythm": "夜巡冷场，对白半截半截，留白多",
    "notes": ""
  },
  "dependency_coverage": "partial",
  "reading_coverage": "partial",
  "reading_refs": [],
  "understanding_refs": []
}
```

#### 第 7 章

```json
{
  "chapter": 7,
  "synopsis": "电长的登记簿把电力巷的窗口压到全台区最短，明摆着给黑市腾生意。公用冰柜眼见化冻，排队的街坊急得跳脚。常亮当众把冰柜续满，又按秦姨递的名单给两家药械续了电。人群里的议论变了风向：小常的电，比名单靠得住。",
  "story_events": [],
  "reader_effect": null,
  "timeline": null,
  "beats": [],
  "role": null,
  "plot": {
    "beat": "登记簿压短窗口，常亮当众续电把口碑压回来",
    "nodes": [
      {
        "node": "n1",
        "after": "advanced",
        "outcome": "暗手变明摊，口碑当众立住"
      }
    ],
    "threads": []
  },
  "resources": [
    {
      "key": "现金",
      "from": 2200,
      "to": 2400,
      "reason": "平价电费与开销的净进项"
    }
  ],
  "places": [],
  "knowledge": [],
  "characters": [],
  "relations": [],
  "clock": {
    "advance_days": 1
  },
  "enter": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 2200
    },
    {
      "kind": "node",
      "key": "n1",
      "expected": "seeded"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 9
    }
  ],
  "exit": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 2400
    },
    {
      "kind": "node",
      "key": "n1",
      "expected": "advanced"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 10
    }
  ],
  "disclosures": [],
  "world_refs": [
    "rules:rule-window",
    "everyday:evd-window-queue",
    "everyday:evd-alley-night"
  ],
  "new_entities": [],
  "hooks": [],
  "hook_refs": [],
  "reader_refs": [],
  "history_refs": [],
  "scenes": [],
  "pacing": {},
  "style": {
    "pov": "第三人称主角中心",
    "rhythm": "排队场升温，节奏加快，人声推着走",
    "notes": ""
  },
  "dependency_coverage": "partial",
  "reading_coverage": "partial",
  "reading_refs": [],
  "understanding_refs": []
}
```

#### 第 8 章

```json
{
  "chapter": 8,
  "synopsis": "夜里罗清找上门，进门就骂：她照护的制氧机病人当天差点出事，因为常亮把电先给了冰柜。她把老城的难处拍在桌上：人命电器一巷子都是，靠他一个人的身板，排得过来吗。常亮头一回被人把死结当面掀开，一夜没睡。秦姨在门口听了半截，没进来，第二天把一篮鸡蛋搁在他家窗台。",
  "story_events": [],
  "reader_effect": null,
  "timeline": null,
  "beats": [],
  "role": null,
  "plot": {
    "beat": "罗清上门掀开人命电排不过来的死结",
    "nodes": [],
    "threads": []
  },
  "resources": [
    {
      "key": "现金",
      "from": 2400,
      "to": 2700,
      "reason": "平价电费与开销的净进项"
    }
  ],
  "places": [],
  "knowledge": [],
  "characters": [],
  "relations": [],
  "clock": {
    "advance_days": 1
  },
  "enter": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 2400
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 10
    }
  ],
  "exit": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 2700
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 11
    }
  ],
  "disclosures": [],
  "world_refs": [
    "characters:char-luo-qing",
    "everyday:evd-life-machines"
  ],
  "new_entities": [],
  "hooks": [],
  "hook_refs": [],
  "reader_refs": [],
  "history_refs": [],
  "scenes": [],
  "pacing": {},
  "style": {
    "pov": "第三人称主角中心",
    "rhythm": "静场对骂，句子放长，情绪压着走",
    "notes": ""
  },
  "dependency_coverage": "partial",
  "reading_coverage": "partial",
  "reading_refs": [],
  "understanding_refs": []
}
```

#### 第 9 章

```json
{
  "chapter": 9,
  "synopsis": "常亮登门给制氧机病人补电赔礼，守到天亮。罗清把老城病人底册抄了一份拍在摊上：谁家什么机器、电池撑几个小时、联系人是谁，一页页清清楚楚。她说这东西比他的力气金贵。摊子上从此多了一本不能断电的册子。册页边角卷了，他拿夹子夹好，供完电先翻一遍才睡。",
  "story_events": [],
  "reader_effect": null,
  "timeline": null,
  "beats": [],
  "role": null,
  "plot": {
    "beat": "赔礼守到天亮，换来一册病人底册",
    "nodes": [
      {
        "node": "n3",
        "after": "seeded",
        "outcome": "底册从一页纸开始管事先"
      }
    ],
    "threads": []
  },
  "resources": [
    {
      "key": "现金",
      "from": 2700,
      "to": 2800,
      "reason": "平价电费与开销的净进项"
    }
  ],
  "places": [],
  "knowledge": [],
  "characters": [],
  "relations": [
    {
      "source": "chang-liang",
      "target": "luo-qing",
      "key": "照护",
      "from": null,
      "to": "搭手",
      "reason": "骂完还是把底册递了过来"
    }
  ],
  "clock": {
    "advance_days": 2
  },
  "enter": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 2700
    },
    {
      "kind": "relations",
      "key": "chang-liang>luo-qing:照护",
      "expected": null
    },
    {
      "kind": "node",
      "key": "n3",
      "expected": null
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 11
    }
  ],
  "exit": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 2800
    },
    {
      "kind": "relations",
      "key": "chang-liang>luo-qing:照护",
      "expected": "搭手"
    },
    {
      "kind": "node",
      "key": "n3",
      "expected": "seeded"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 13
    }
  ],
  "disclosures": [],
  "world_refs": [
    "characters:char-luo-qing",
    "everyday:evd-life-machines",
    "society:soc-oldtown-order"
  ],
  "new_entities": [],
  "hooks": [
    {
      "hook": "h5",
      "action": "plant",
      "note": "册子拍在摊上，一巷子的命换着看"
    }
  ],
  "hook_refs": [],
  "reader_refs": [],
  "history_refs": [],
  "scenes": [],
  "pacing": {},
  "style": {
    "pov": "第三人称主角中心",
    "rhythm": "夜到晨的过渡，叙述转缓，留体温",
    "notes": ""
  },
  "dependency_coverage": "partial",
  "reading_coverage": "partial",
  "reading_refs": [],
  "understanding_refs": []
}
```

#### 第 10 章

```json
{
  "chapter": 10,
  "synopsis": "底册头一回试跑，停电夜按册子排先后，一户没漏。小卖部门口的消息也聚过来：谁家有船、谁家有临街插座，秦姨一样样记。小赵再巡巷，对着底册一户一户看过去，头一回把老城的实情看进眼里。他没说话，本子却记满了。散场时他把底册包进塑料布，收进铁盒最里层。",
  "story_events": [],
  "reader_effect": null,
  "timeline": null,
  "beats": [],
  "role": null,
  "plot": {
    "beat": "底册试跑一夜没漏一户，消息网聚拢",
    "nodes": [],
    "threads": []
  },
  "resources": [
    {
      "key": "现金",
      "from": 2800,
      "to": 3200,
      "reason": "平价电费与开销的净进项"
    }
  ],
  "places": [],
  "knowledge": [
    {
      "who": "xiao-zhao",
      "topic": "常亮的供电来路",
      "from": "suspected",
      "to": "confirmed",
      "reason": "册子对上实情，蓝光的来路他认了"
    }
  ],
  "characters": [],
  "relations": [],
  "clock": {
    "advance_days": 2
  },
  "enter": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 2800
    },
    {
      "kind": "knowledge",
      "key": "xiao-zhao:常亮的供电来路",
      "expected": "suspected"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 13
    }
  ],
  "exit": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 3200
    },
    {
      "kind": "knowledge",
      "key": "xiao-zhao:常亮的供电来路",
      "expected": "confirmed"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 15
    }
  ],
  "disclosures": [],
  "world_refs": [
    "everyday:evd-window-queue",
    "characters:char-qin-yi",
    "characters:char-xiao-zhao"
  ],
  "new_entities": [],
  "hooks": [],
  "hook_refs": [],
  "reader_refs": [],
  "history_refs": [],
  "scenes": [],
  "pacing": {},
  "style": {
    "pov": "第三人称主角中心",
    "rhythm": "平稳铺陈，短段快切，像翻册子",
    "notes": ""
  },
  "dependency_coverage": "partial",
  "reading_coverage": "partial",
  "reading_refs": [],
  "understanding_refs": []
}
```

#### 第 11 章

```json
{
  "chapter": 11,
  "synopsis": "马六盯上底册，放话谁给常亮递消息就收谁的信息费。秦姨顶住没松口。常亮把新规矩写成三行：人命电免费，平价电明码两块，供电顺序全楼举手。他说价不该他一个人定，让全巷来。黑板抬到巷口，等一场大会。散会后秦姨留下擦黑板，把三行字又描了一遍才走。",
  "story_events": [],
  "reader_effect": null,
  "timeline": null,
  "beats": [],
  "role": null,
  "plot": {
    "beat": "马六收信息费施压，常亮把定价权交给全巷",
    "nodes": [],
    "threads": []
  },
  "resources": [
    {
      "key": "现金",
      "from": 3200,
      "to": 3500,
      "reason": "平价电费与开销的净进项"
    }
  ],
  "places": [],
  "knowledge": [],
  "characters": [],
  "relations": [],
  "clock": {
    "advance_days": 1
  },
  "enter": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 3200
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 15
    }
  ],
  "exit": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 3500
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 16
    }
  ],
  "disclosures": [],
  "world_refs": [
    "characters:char-ma-liu",
    "characters:char-qin-yi",
    "factions:fact-oldtown-mutual"
  ],
  "new_entities": [],
  "hooks": [],
  "hook_refs": [],
  "reader_refs": [],
  "history_refs": [],
  "scenes": [],
  "pacing": {},
  "style": {
    "pov": "第三人称主角中心",
    "rhythm": "压迫感渐起，对白带刺，句尾收紧",
    "notes": ""
  },
  "dependency_coverage": "partial",
  "reading_coverage": "partial",
  "reading_refs": [],
  "understanding_refs": []
}
```

#### 第 12 章

```json
{
  "chapter": 12,
  "synopsis": "全巷举手大会开了。三行规矩念一条过一条，人命电免费那条，举手最多最快。价由全楼定，常亮只管供电。马六的价牌头一回没人看，他站在人群外抽烟，眼神冷下去。黑板描了框，摊子从一个人的营生，变成一条巷子的规矩。散会后马六蹲在巷口抽完最后一支烟，把价牌翻过来扣下。",
  "story_events": [],
  "reader_effect": null,
  "timeline": null,
  "beats": [],
  "role": "规矩章：黑板三行经全巷举手通过",
  "plot": {
    "beat": "全巷举手通过黑板三行规矩",
    "nodes": [
      {
        "node": "n1",
        "after": "resolved",
        "outcome": "三行规矩举手通过，摊子成了制度"
      }
    ],
    "threads": [
      {
        "thread": "t1",
        "after": "active",
        "reason": "规矩立了，下一仗冲着规矩来"
      }
    ]
  },
  "resources": [
    {
      "key": "现金",
      "from": 3500,
      "to": 3900,
      "reason": "平价电费与开销的净进项"
    }
  ],
  "places": [],
  "knowledge": [],
  "characters": [
    {
      "entity": "chang-liang",
      "from": null,
      "to": {
        "desire": "把摊子立成全巷认的平价规矩，让父亲的呼吸机永远有电",
        "stance": "价和序交给全楼举手，人命电免费的底线自己攥着",
        "relationship_focus": "秦姨守口风，罗清递底册，街坊开始围着他转"
      },
      "choice": "价和序交给全楼举手，自己只管供电",
      "cost": "定价权交出去，休息时间头一个被排掉",
      "reason": "人物处境与立场的节点变化"
    }
  ],
  "relations": [
    {
      "source": "chang-liang",
      "target": "qin-yi",
      "key": "口风",
      "from": null,
      "to": "同盟",
      "reason": "大会是她一户一户喊来的"
    }
  ],
  "clock": {
    "advance_days": 2
  },
  "enter": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 3500
    },
    {
      "kind": "character",
      "key": "chang-liang",
      "expected": null
    },
    {
      "kind": "relations",
      "key": "chang-liang>qin-yi:口风",
      "expected": null
    },
    {
      "kind": "node",
      "key": "n1",
      "expected": "advanced"
    },
    {
      "kind": "thread",
      "key": "t1",
      "expected": "active"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 16
    }
  ],
  "exit": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 3900
    },
    {
      "kind": "character",
      "key": "chang-liang",
      "expected": {
        "desire": "把摊子立成全巷认的平价规矩，让父亲的呼吸机永远有电",
        "stance": "价和序交给全楼举手，人命电免费的底线自己攥着",
        "relationship_focus": "秦姨守口风，罗清递底册，街坊开始围着他转"
      }
    },
    {
      "kind": "relations",
      "key": "chang-liang>qin-yi:口风",
      "expected": "同盟"
    },
    {
      "kind": "node",
      "key": "n1",
      "expected": "resolved"
    },
    {
      "kind": "thread",
      "key": "t1",
      "expected": "active"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 18
    }
  ],
  "disclosures": [],
  "world_refs": [
    "factions:fact-oldtown-mutual",
    "society:soc-oldtown-order",
    "geography:geo-xiangkou-taiqu"
  ],
  "new_entities": [],
  "hooks": [],
  "hook_refs": [
    "h1"
  ],
  "reader_refs": [],
  "history_refs": [],
  "scenes": [],
  "pacing": {},
  "style": {
    "pov": "第三人称主角中心",
    "rhythm": "大会场群声，节奏明快，落锤定音",
    "notes": ""
  },
  "dependency_coverage": "partial",
  "reading_coverage": "partial",
  "reading_refs": [],
  "understanding_refs": []
}
```

#### 第 13 章

```json
{
  "chapter": 13,
  "synopsis": "当夜摊子被人泼了柴油，黑板糊了半边。街坊围着骂，马六一早拎着柴油机来送电装好人。常亮没接话，蹲下来擦黑板。他心里清楚，泼油的手是冲规矩来的，规矩要是靠他一个人守，就总有被泼的一天。第二天一早，排队的人照旧排到黑板底下，没少一个。",
  "story_events": [],
  "reader_effect": null,
  "timeline": null,
  "beats": [],
  "role": null,
  "plot": {
    "beat": "柴油泼上黑板，马六假意送电",
    "nodes": [],
    "threads": []
  },
  "resources": [
    {
      "key": "现金",
      "from": 3900,
      "to": 3700,
      "reason": "平价电费与开销的净进项"
    }
  ],
  "places": [],
  "knowledge": [],
  "characters": [],
  "relations": [],
  "clock": {
    "advance_days": 2
  },
  "enter": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 3900
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 18
    }
  ],
  "exit": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 3700
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 20
    }
  ],
  "disclosures": [],
  "world_refs": [
    "characters:char-ma-liu",
    "economy:econ-black-power",
    "geography:geo-dianlixiang"
  ],
  "new_entities": [],
  "hooks": [
    {
      "hook": "h4",
      "action": "plant",
      "note": "柴油泼在黑板下半边，手套都没留"
    }
  ],
  "hook_refs": [],
  "reader_refs": [],
  "history_refs": [],
  "scenes": [],
  "pacing": {},
  "style": {
    "pov": "第三人称主角中心",
    "rhythm": "夜色暗场，短句冷叙述，怒气压着",
    "notes": ""
  },
  "dependency_coverage": "partial",
  "reading_coverage": "partial",
  "reading_refs": [],
  "understanding_refs": []
}
```

#### 第 14 章

```json
{
  "chapter": 14,
  "synopsis": "常亮按底册把人命电一户一户送到，谁家几小时、谁家先谁家后，册子翻得起了毛边。糊掉的黑板第二天被街坊一人一笔描回来，笔画摞着笔画。递消息的人没断，马六的信息费收不上来，反把自己人得罪光了。马六在斜对面看了一早上，转身走得比来时快。",
  "story_events": [],
  "reader_effect": null,
  "timeline": null,
  "beats": [],
  "role": null,
  "plot": {
    "beat": "按册送电，街坊一人一笔描回黑板",
    "nodes": [
      {
        "node": "n3",
        "after": "advanced",
        "outcome": "册子从名单变成全巷的主心骨"
      }
    ],
    "threads": []
  },
  "resources": [
    {
      "key": "现金",
      "from": 3700,
      "to": 4000,
      "reason": "平价电费与开销的净进项"
    }
  ],
  "places": [],
  "knowledge": [],
  "characters": [],
  "relations": [],
  "clock": {
    "advance_days": 2
  },
  "enter": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 3700
    },
    {
      "kind": "node",
      "key": "n3",
      "expected": "seeded"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 20
    }
  ],
  "exit": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 4000
    },
    {
      "kind": "node",
      "key": "n3",
      "expected": "advanced"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 22
    }
  ],
  "disclosures": [],
  "world_refs": [
    "everyday:evd-life-machines",
    "factions:fact-oldtown-mutual"
  ],
  "new_entities": [],
  "hooks": [
    {
      "hook": "h5",
      "action": "payoff",
      "note": "停电夜按册排先后，真的一户没漏"
    }
  ],
  "hook_refs": [],
  "reader_refs": [],
  "history_refs": [],
  "scenes": [],
  "pacing": {},
  "style": {
    "pov": "第三人称主角中心",
    "rhythm": "温叙述，群像小段，笔触轻",
    "notes": ""
  },
  "dependency_coverage": "partial",
  "reading_coverage": "partial",
  "reading_refs": [],
  "understanding_refs": []
}
```

#### 第 15 章

```json
{
  "chapter": 15,
  "synopsis": "停电拉长，马六囤的电先见了底，价牌守不住。他放量压价想拖垮常亮，反倒把自己仓库掏空一格。常亮当着排队的人三句话点破囤电倒卖：他的电卖一度少一度，小常的电明天还有。队齐刷刷掉头。马六开始信常亮背后有货源。",
  "story_events": [],
  "reader_effect": null,
  "timeline": null,
  "beats": [],
  "role": null,
  "plot": {
    "beat": "囤电放空价牌守不住，三句话点破倒卖",
    "nodes": [],
    "threads": []
  },
  "resources": [
    {
      "key": "现金",
      "from": 4000,
      "to": 4300,
      "reason": "平价电费与开销的净进项"
    },
    {
      "key": "囤积电量",
      "from": 300,
      "to": 180,
      "reason": "黑市囤电的存数变化"
    }
  ],
  "places": [],
  "knowledge": [
    {
      "who": "ma-liu",
      "topic": "常亮的供电来路",
      "from": "suspected",
      "to": "misled",
      "reason": "认定背后有大货源，顺着假话查下去"
    }
  ],
  "characters": [],
  "relations": [],
  "clock": {
    "advance_days": 2
  },
  "enter": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 4000
    },
    {
      "kind": "resources",
      "key": "囤积电量",
      "expected": 300
    },
    {
      "kind": "knowledge",
      "key": "ma-liu:常亮的供电来路",
      "expected": "suspected"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 22
    }
  ],
  "exit": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 4300
    },
    {
      "kind": "resources",
      "key": "囤积电量",
      "expected": 180
    },
    {
      "kind": "knowledge",
      "key": "ma-liu:常亮的供电来路",
      "expected": "misled"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 24
    }
  ],
  "disclosures": [],
  "world_refs": [
    "economy:econ-black-power",
    "characters:char-ma-liu"
  ],
  "new_entities": [],
  "hooks": [],
  "hook_refs": [],
  "reader_refs": [],
  "history_refs": [],
  "scenes": [],
  "pacing": {},
  "style": {
    "pov": "第三人称主角中心",
    "rhythm": "打脸场语速快，对白占主，脆落",
    "notes": ""
  },
  "dependency_coverage": "partial",
  "reading_coverage": "partial",
  "reading_refs": [],
  "understanding_refs": []
}
```

#### 第 16 章

```json
{
  "chapter": 16,
  "synopsis": "窗口排序又出幺蛾子，登记簿把人命电器的户排到了后头。常亮带着底册当场对质：册上谁家什么机器一清二楚，登记簿的号却对不上人。排队的街坊一人一句把自家的难处报出来。电长被顶得下不来台，当场重排。底册成了巷子的主心骨。",
  "story_events": [],
  "reader_effect": null,
  "timeline": null,
  "beats": [],
  "role": null,
  "plot": {
    "beat": "登记簿乱序对不上底册，电长当场重排",
    "nodes": [
      {
        "node": "n3",
        "after": "resolved",
        "outcome": "窗口排队按底册压住登记簿乱序"
      },
      {
        "node": "n2",
        "after": "advanced",
        "outcome": "黑市的底数摸到一半"
      }
    ],
    "threads": []
  },
  "resources": [
    {
      "key": "现金",
      "from": 4300,
      "to": 4600,
      "reason": "平价电费与开销的净进项"
    }
  ],
  "places": [],
  "knowledge": [],
  "characters": [],
  "relations": [],
  "clock": {
    "advance_days": 1
  },
  "enter": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 4300
    },
    {
      "kind": "node",
      "key": "n3",
      "expected": "advanced"
    },
    {
      "kind": "node",
      "key": "n2",
      "expected": "seeded"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 24
    }
  ],
  "exit": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 4600
    },
    {
      "kind": "node",
      "key": "n3",
      "expected": "resolved"
    },
    {
      "kind": "node",
      "key": "n2",
      "expected": "advanced"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 25
    }
  ],
  "disclosures": [],
  "world_refs": [
    "rules:rule-window",
    "everyday:evd-window-queue",
    "characters:char-zhou-dianzhang"
  ],
  "new_entities": [],
  "hooks": [],
  "hook_refs": [],
  "reader_refs": [],
  "history_refs": [],
  "scenes": [],
  "pacing": {},
  "style": {
    "pov": "第三人称主角中心",
    "rhythm": "对质场硬碰硬，短句钉人，静一拍收",
    "notes": ""
  },
  "dependency_coverage": "partial",
  "reading_coverage": "partial",
  "reading_refs": [],
  "understanding_refs": []
}
```

#### 第 17 章

```json
{
  "chapter": 17,
  "synopsis": "泼柴油的事有了下文。修车摊的旧监控加上街坊记得的脚程，把当夜的人对了出来，是马六手下的两个熟脸。人赃对上，派出所来人带走了。马六明面上的牌打光了，巷口安静了两天，安静得反常。巷口安静了两天，安静得反常，常亮让街坊夜里留个心。",
  "story_events": [],
  "reader_effect": null,
  "timeline": null,
  "beats": [],
  "role": null,
  "plot": {
    "beat": "监控与脚程对出泼油的黑手",
    "nodes": [],
    "threads": []
  },
  "resources": [
    {
      "key": "现金",
      "from": 4600,
      "to": 4900,
      "reason": "平价电费与开销的净进项"
    }
  ],
  "places": [],
  "knowledge": [],
  "characters": [],
  "relations": [],
  "clock": {
    "advance_days": 2
  },
  "enter": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 4600
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 25
    }
  ],
  "exit": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 4900
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 27
    }
  ],
  "disclosures": [],
  "world_refs": [
    "society:soc-oldtown-order",
    "geography:geo-dianlixiang"
  ],
  "new_entities": [],
  "hooks": [
    {
      "hook": "h4",
      "action": "payoff",
      "note": "监控把那双手对了出来"
    }
  ],
  "hook_refs": [],
  "reader_refs": [],
  "history_refs": [],
  "scenes": [],
  "pacing": {},
  "style": {
    "pov": "第三人称主角中心",
    "rhythm": "查证段冷静克制，细节密，语气收",
    "notes": ""
  },
  "dependency_coverage": "partial",
  "reading_coverage": "partial",
  "reading_refs": [],
  "understanding_refs": []
}
```

#### 第 18 章

```json
{
  "chapter": 18,
  "synopsis": "小赵夜里来摊上，头一回主动开口：马六的囤电不止一处仓库，电长每笔生意里有没有分成，他见过一回钱的走法。说完他就走，怕人多看一眼。常亮把这话压在心里，分成两个字，把周电长和马六拴成了一根绳上的两个蚂蚱。",
  "story_events": [],
  "reader_effect": null,
  "timeline": null,
  "beats": [],
  "role": null,
  "plot": {
    "beat": "小赵开口漏出仓库与分成的缝",
    "nodes": [
      {
        "node": "n4",
        "after": "advanced",
        "outcome": "电长漏话，那晚的会他到过外围"
      }
    ],
    "threads": [
      {
        "thread": "t2",
        "after": "active",
        "reason": "电长漏话把谜线往里推了一层"
      }
    ]
  },
  "resources": [
    {
      "key": "现金",
      "from": 4900,
      "to": 5200,
      "reason": "平价电费与开销的净进项"
    }
  ],
  "places": [],
  "knowledge": [
    {
      "who": "chang-liang",
      "topic": "周电长与马六的分成",
      "from": null,
      "to": "suspected",
      "reason": "小赵的话让他把两个人拴在一起看"
    }
  ],
  "characters": [],
  "relations": [],
  "clock": {
    "advance_days": 2
  },
  "enter": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 4900
    },
    {
      "kind": "knowledge",
      "key": "chang-liang:周电长与马六的分成",
      "expected": null
    },
    {
      "kind": "node",
      "key": "n4",
      "expected": "seeded"
    },
    {
      "kind": "thread",
      "key": "t2",
      "expected": "active"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 27
    }
  ],
  "exit": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 5200
    },
    {
      "kind": "knowledge",
      "key": "chang-liang:周电长与马六的分成",
      "expected": "suspected"
    },
    {
      "kind": "node",
      "key": "n4",
      "expected": "advanced"
    },
    {
      "kind": "thread",
      "key": "t2",
      "expected": "active"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 29
    }
  ],
  "disclosures": [
    {
      "topic": "周电长的分成网络",
      "after": "hinted",
      "note": "读者先看见分成网络的影子"
    }
  ],
  "world_refs": [
    "characters:char-xiao-zhao",
    "factions:fact-black-market",
    "characters:char-zhou-dianzhang"
  ],
  "new_entities": [],
  "hooks": [
    {
      "hook": "h6",
      "action": "payoff",
      "note": "他没说出去，反把话递了过来"
    }
  ],
  "hook_refs": [],
  "reader_refs": [],
  "history_refs": [],
  "scenes": [],
  "pacing": {},
  "style": {
    "pov": "第三人称主角中心",
    "rhythm": "夜谈低声，句子半截，信任一寸寸给",
    "notes": ""
  },
  "dependency_coverage": "partial",
  "reading_coverage": "partial",
  "reading_refs": [],
  "understanding_refs": []
}
```

#### 第 19 章

```json
{
  "chapter": 19,
  "synopsis": "分成的话到底传进电长耳朵。检修通道收紧成明抢，老线的报修单压着不批，巷子中段的线路夜里打火。常亮没有证，杆都上不去，干着急。他盯着那截打火的线看了半宿，明白光靠人情顶不住制度的手腕。那晚打火的线头，他用绝缘胶布缠了三层，先顶一晚。",
  "story_events": [],
  "reader_effect": null,
  "timeline": null,
  "beats": [],
  "role": null,
  "plot": {
    "beat": "检修通道收紧成明抢，老线打火",
    "nodes": [],
    "threads": []
  },
  "resources": [
    {
      "key": "现金",
      "from": 5200,
      "to": 5600,
      "reason": "平价电费与开销的净进项"
    }
  ],
  "places": [],
  "knowledge": [],
  "characters": [],
  "relations": [],
  "clock": {
    "advance_days": 1
  },
  "enter": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 5200
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 29
    }
  ],
  "exit": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 5600
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 30
    }
  ],
  "disclosures": [],
  "world_refs": [
    "characters:char-zhou-dianzhang",
    "factions:fact-district-chiefs",
    "rules:rule-private-supply"
  ],
  "new_entities": [],
  "hooks": [],
  "hook_refs": [],
  "reader_refs": [],
  "history_refs": [],
  "scenes": [],
  "pacing": {},
  "style": {
    "pov": "第三人称主角中心",
    "rhythm": "受制段沉闷，长句压顶，火点在夜里",
    "notes": ""
  },
  "dependency_coverage": "partial",
  "reading_coverage": "partial",
  "reading_refs": [],
  "understanding_refs": []
}
```

#### 第 20 章

```json
{
  "chapter": 20,
  "synopsis": "常亮去报低压电工证的培训班，白天背题夜里供电，把零工彻底辞了。书上的规程一条一条背进脑子，他头一回把力气往合法的路子上使。培训费交出去，铁盒瘪下去一截，他不心疼：证下来，检修通道就多一道掰手腕的资格。",
  "story_events": [],
  "reader_effect": null,
  "timeline": null,
  "beats": [],
  "role": null,
  "plot": {
    "beat": "报名考电工证，力气往合法的路上使",
    "nodes": [],
    "threads": []
  },
  "resources": [
    {
      "key": "现金",
      "from": 5600,
      "to": 5500,
      "reason": "平价电费与开销的净进项"
    }
  ],
  "places": [],
  "knowledge": [],
  "characters": [],
  "relations": [],
  "clock": {
    "advance_days": 2
  },
  "enter": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 5600
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 30
    }
  ],
  "exit": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 5500
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 32
    }
  ],
  "disclosures": [],
  "world_refs": [
    "powers:pow-chizheng-diangong",
    "mechanisms:mech-body-power"
  ],
  "new_entities": [],
  "hooks": [],
  "hook_refs": [],
  "reader_refs": [],
  "history_refs": [],
  "scenes": [],
  "pacing": {},
  "style": {
    "pov": "第三人称主角中心",
    "rhythm": "生活流加自嘲，白天黑夜两头切",
    "notes": ""
  },
  "dependency_coverage": "partial",
  "reading_coverage": "partial",
  "reading_refs": [],
  "understanding_refs": []
}
```

#### 第 21 章

```json
{
  "chapter": 21,
  "synopsis": "连着透支，常亮在电线杆下晕倒，被收摊的秦姨看见，喊罗清来把他拎去卫生站输液。父亲那一夜靠备用电池和邻居轮守撑过去。罗清骂他：你的电是借身体的本，本钱亏光了，谁替全巷供电。他躺着，头一回没法还嘴。输液的时候他还惦记晚上的停电钟点，被罗清按回床上。",
  "story_events": [],
  "reader_effect": null,
  "timeline": null,
  "beats": [],
  "role": null,
  "plot": {
    "beat": "杆下晕倒被拎进卫生站，父亲靠邻里撑过夜",
    "nodes": [],
    "threads": []
  },
  "resources": [
    {
      "key": "现金",
      "from": 5500,
      "to": 5400,
      "reason": "平价电费与开销的净进项"
    }
  ],
  "places": [],
  "knowledge": [],
  "characters": [],
  "relations": [],
  "clock": {
    "advance_days": 2
  },
  "enter": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 5500
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 32
    }
  ],
  "exit": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 5400
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 34
    }
  ],
  "disclosures": [],
  "world_refs": [
    "characters:char-luo-qing",
    "mechanisms:mech-body-power",
    "characters:char-chang-shoutian"
  ],
  "new_entities": [],
  "hooks": [],
  "hook_refs": [],
  "reader_refs": [],
  "history_refs": [],
  "scenes": [],
  "pacing": {},
  "style": {
    "pov": "第三人称主角中心",
    "rhythm": "病中段虚弱，句子散，骂声带暖",
    "notes": ""
  },
  "dependency_coverage": "partial",
  "reading_coverage": "partial",
  "reading_refs": [],
  "understanding_refs": []
}
```

#### 第 22 章

```json
{
  "chapter": 22,
  "synopsis": "高温加缺口，调度预告老城要停整一夜带两个白天。马六把最后囤的电抬到天价，专做人命机器的生意：钱到位就来电。街坊把眼光投向小黑板。常亮把底册摊开，把自家的电一格一格排进每户的钟点里，留给父亲的，压到最后。",
  "story_events": [],
  "reader_effect": null,
  "timeline": null,
  "beats": [],
  "role": null,
  "plot": {
    "beat": "大停电预告，马六抬天价，常亮把电排到最后一格",
    "nodes": [],
    "threads": [
      {
        "thread": "t1",
        "after": "active",
        "reason": "价牌与黑板最后对上一次"
      }
    ]
  },
  "resources": [
    {
      "key": "现金",
      "from": 5400,
      "to": 5700,
      "reason": "平价电费与开销的净进项"
    },
    {
      "key": "囤积电量",
      "from": 180,
      "to": 120,
      "reason": "黑市囤电的存数变化"
    }
  ],
  "places": [],
  "knowledge": [],
  "characters": [],
  "relations": [],
  "clock": {
    "advance_days": 1
  },
  "enter": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 5400
    },
    {
      "kind": "resources",
      "key": "囤积电量",
      "expected": 180
    },
    {
      "kind": "thread",
      "key": "t1",
      "expected": "active"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 34
    }
  ],
  "exit": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 5700
    },
    {
      "kind": "resources",
      "key": "囤积电量",
      "expected": 120
    },
    {
      "kind": "thread",
      "key": "t1",
      "expected": "active"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 35
    }
  ],
  "disclosures": [],
  "world_refs": [
    "everyday:evd-life-machines",
    "economy:econ-black-power",
    "characters:char-ma-liu"
  ],
  "new_entities": [],
  "hooks": [],
  "hook_refs": [],
  "reader_refs": [],
  "history_refs": [],
  "scenes": [],
  "pacing": {},
  "style": {
    "pov": "第三人称主角中心",
    "rhythm": "大战前夜，节奏收紧，对白硬",
    "notes": ""
  },
  "dependency_coverage": "partial",
  "reading_coverage": "partial",
  "reading_refs": [],
  "understanding_refs": []
}
```

#### 第 23 章

```json
{
  "chapter": 23,
  "synopsis": "大停电夜按册送电，送到第七户常亮的电见底。他把留给父亲的最后一格送了出去，人在楼道里晕倒。全巷没散，手捏皮球的、抬电池的、守在呼吸机边的，一轮一轮替他守到天亮。醒来时父亲睡得平稳，床边坐着一巷子人。死结解开了，解成互相欠着。",
  "story_events": [],
  "reader_effect": null,
  "timeline": null,
  "beats": [],
  "role": "高潮章：死结解成全巷互守",
  "plot": {
    "beat": "把父亲的最后一格电送出去，全巷替他守夜",
    "nodes": [],
    "threads": []
  },
  "resources": [
    {
      "key": "现金",
      "from": 5700,
      "to": 5800,
      "reason": "平价电费与开销的净进项"
    }
  ],
  "places": [],
  "knowledge": [],
  "characters": [
    {
      "entity": "chang-liang",
      "from": {
        "desire": "把摊子立成全巷认的平价规矩，让父亲的呼吸机永远有电",
        "stance": "价和序交给全楼举手，人命电免费的底线自己攥着",
        "relationship_focus": "秦姨守口风，罗清递底册，街坊开始围着他转"
      },
      "to": {
        "desire": "守住黑板上的规矩和父亲的呼吸机，把摊子做成全巷离不了的正经营生",
        "stance": "规矩交给全巷举手，自己只管供电和底线，不再单打独斗",
        "relationship_focus": "从巷子欠他人情，变成全巷与他互相欠着、互相守着"
      },
      "choice": "把留给父亲的最后一格电先送了别人",
      "cost": "自己晕过去，父亲的命头一回交到街坊手里",
      "reason": "人物处境与立场的节点变化"
    }
  ],
  "relations": [],
  "clock": {
    "advance_days": 2
  },
  "enter": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 5700
    },
    {
      "kind": "character",
      "key": "chang-liang",
      "expected": {
        "desire": "把摊子立成全巷认的平价规矩，让父亲的呼吸机永远有电",
        "stance": "价和序交给全楼举手，人命电免费的底线自己攥着",
        "relationship_focus": "秦姨守口风，罗清递底册，街坊开始围着他转"
      }
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 35
    }
  ],
  "exit": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 5800
    },
    {
      "kind": "character",
      "key": "chang-liang",
      "expected": {
        "desire": "守住黑板上的规矩和父亲的呼吸机，把摊子做成全巷离不了的正经营生",
        "stance": "规矩交给全巷举手，自己只管供电和底线，不再单打独斗",
        "relationship_focus": "从巷子欠他人情，变成全巷与他互相欠着、互相守着"
      }
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 37
    }
  ],
  "disclosures": [],
  "world_refs": [
    "everyday:evd-life-machines",
    "factions:fact-oldtown-mutual",
    "characters:char-chang-shoutian"
  ],
  "new_entities": [],
  "hooks": [
    {
      "hook": "h1",
      "action": "payoff",
      "note": "死结在停电夜解成互相欠着"
    }
  ],
  "hook_refs": [],
  "reader_refs": [],
  "history_refs": [],
  "scenes": [],
  "pacing": {},
  "style": {
    "pov": "第三人称主角中心",
    "rhythm": "高潮夜群像，段落短促交替，静场有力",
    "notes": ""
  },
  "dependency_coverage": "partial",
  "reading_coverage": "partial",
  "reading_refs": [],
  "understanding_refs": []
}
```

#### 第 24 章

```json
{
  "chapter": 24,
  "synopsis": "天亮后清算。小赵借巡查把囤电仓库的位置递了上去，供电所突查，柴油机无备案、囤积电池整仓暂扣，马六被带走协查前撂话咬人。周电长连夜断了常亮的检修通道自保，动作快得像早有准备。价牌倒了，通道也断了，胜负一起压过来。",
  "story_events": [],
  "reader_effect": null,
  "timeline": null,
  "beats": [],
  "role": "清算章：囤电被端，价牌倒下",
  "plot": {
    "beat": "证据递上去囤电被端，电长断通道自保",
    "nodes": [
      {
        "node": "n2",
        "after": "resolved",
        "outcome": "囤电整仓被暂扣，巷口生意破局"
      }
    ],
    "threads": [
      {
        "thread": "t1",
        "after": "resolved",
        "reason": "规矩立稳，巷口这仗收口"
      }
    ]
  },
  "resources": [
    {
      "key": "现金",
      "from": 5800,
      "to": 5800,
      "reason": "平价电费与开销的净进项"
    },
    {
      "key": "囤积电量",
      "from": 120,
      "to": 0,
      "reason": "黑市囤电的存数变化"
    }
  ],
  "places": [
    {
      "entity": "ma-liu",
      "from": "geo-xiangkou-taiqu",
      "to": "geo-jiangbei",
      "reason": "所在地的变化"
    }
  ],
  "knowledge": [],
  "characters": [
    {
      "entity": "ma-liu",
      "from": null,
      "to": {
        "desire": "保住囤电的本钱，等常亮栽跟头再杀回来",
        "stance": "明面价牌倒了就把生意做进阴处",
        "relationship_focus": "与周电长从分成伙计变成互相攥着把柄的人"
      },
      "choice": "把最后的本钱押给人命电要挟",
      "cost": "巷口的地盘和人脸全丢了",
      "reason": "人物处境与立场的节点变化"
    }
  ],
  "relations": [
    {
      "source": "ma-liu",
      "target": "zhou-dianzhang",
      "key": "分成",
      "from": null,
      "to": "反目",
      "reason": "被带走前撂话咬人，把柄互相攥着"
    }
  ],
  "clock": {
    "advance_days": 2
  },
  "enter": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 5800
    },
    {
      "kind": "resources",
      "key": "囤积电量",
      "expected": 120
    },
    {
      "kind": "places",
      "key": "ma-liu",
      "expected": "geo-xiangkou-taiqu"
    },
    {
      "kind": "character",
      "key": "ma-liu",
      "expected": null
    },
    {
      "kind": "relations",
      "key": "ma-liu>zhou-dianzhang:分成",
      "expected": null
    },
    {
      "kind": "node",
      "key": "n2",
      "expected": "advanced"
    },
    {
      "kind": "thread",
      "key": "t1",
      "expected": "active"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 37
    }
  ],
  "exit": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 5800
    },
    {
      "kind": "resources",
      "key": "囤积电量",
      "expected": 0
    },
    {
      "kind": "places",
      "key": "ma-liu",
      "expected": "geo-jiangbei"
    },
    {
      "kind": "character",
      "key": "ma-liu",
      "expected": {
        "desire": "保住囤电的本钱，等常亮栽跟头再杀回来",
        "stance": "明面价牌倒了就把生意做进阴处",
        "relationship_focus": "与周电长从分成伙计变成互相攥着把柄的人"
      }
    },
    {
      "kind": "relations",
      "key": "ma-liu>zhou-dianzhang:分成",
      "expected": "反目"
    },
    {
      "kind": "node",
      "key": "n2",
      "expected": "resolved"
    },
    {
      "kind": "thread",
      "key": "t1",
      "expected": "resolved"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 39
    }
  ],
  "disclosures": [],
  "world_refs": [
    "factions:fact-black-market",
    "characters:char-xiao-zhao",
    "characters:char-zhou-dianzhang"
  ],
  "new_entities": [],
  "hooks": [
    {
      "hook": "h2",
      "action": "payoff",
      "note": "那只手真的攥下来：通道连夜断了"
    }
  ],
  "hook_refs": [],
  "reader_refs": [],
  "history_refs": [],
  "scenes": [],
  "pacing": {},
  "style": {
    "pov": "第三人称主角中心",
    "rhythm": "清算日快节奏，动作连动作，不解释",
    "notes": ""
  },
  "dependency_coverage": "partial",
  "reading_coverage": "partial",
  "reading_refs": [],
  "understanding_refs": []
}
```

#### 第 25 章

```json
{
  "chapter": 25,
  "synopsis": "黑板描了新漆，全巷认下这套规矩。电长的报复摆在明面：报修单原样压着，老线的问题悬在头顶。周电长烧旧物那晚，秦姨抢下半本老登记簿，第一页的日期是三年前那个通宵，签收人一栏洇了半个名字。常亮把簿子收进铁盒：名单的事，这才刚开始。",
  "story_events": [],
  "reader_effect": null,
  "timeline": null,
  "beats": [],
  "role": "卷尾章：线索带进下一卷",
  "plot": {
    "beat": "规矩描漆立住，老登记簿进了铁盒",
    "nodes": [
      {
        "node": "n4",
        "after": "resolved",
        "outcome": "当事人线索到手，问题带进下一卷"
      }
    ],
    "threads": [
      {
        "thread": "t2",
        "after": "active",
        "reason": "线索到手，谜线接着开"
      }
    ]
  },
  "resources": [
    {
      "key": "现金",
      "from": 5800,
      "to": 6000,
      "reason": "平价电费与开销的净进项"
    }
  ],
  "places": [],
  "knowledge": [
    {
      "who": "chang-liang",
      "topic": "错峰名单第一版来历",
      "from": "hinted",
      "to": "suspected",
      "reason": "登记簿第一页把疑点落成线索"
    }
  ],
  "characters": [],
  "relations": [],
  "clock": {
    "advance_days": 1
  },
  "enter": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 5800
    },
    {
      "kind": "knowledge",
      "key": "chang-liang:错峰名单第一版来历",
      "expected": "hinted"
    },
    {
      "kind": "node",
      "key": "n4",
      "expected": "advanced"
    },
    {
      "kind": "thread",
      "key": "t2",
      "expected": "active"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 39
    }
  ],
  "exit": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 6000
    },
    {
      "kind": "knowledge",
      "key": "chang-liang:错峰名单第一版来历",
      "expected": "suspected"
    },
    {
      "kind": "node",
      "key": "n4",
      "expected": "resolved"
    },
    {
      "kind": "thread",
      "key": "t2",
      "expected": "active"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 40
    }
  ],
  "disclosures": [],
  "world_refs": [
    "characters:char-zhou-dianzhang",
    "mysteries:mys-list-origin",
    "history:hist-stagger-orig"
  ],
  "new_entities": [],
  "hooks": [],
  "hook_refs": [
    "h3"
  ],
  "reader_refs": [],
  "history_refs": [],
  "scenes": [],
  "pacing": {},
  "style": {
    "pov": "第三人称主角中心",
    "rhythm": "卷尾收束，叙述放缓，余味压轴",
    "notes": ""
  },
  "dependency_coverage": "partial",
  "reading_coverage": "partial",
  "reading_refs": [],
  "understanding_refs": []
}
```

### vol-2（第 26–50 章）

#### 第 26 章

```json
{
  "chapter": 26,
  "synopsis": "检修通道被断的第二天，报修单原样退回。协查正式立案查违规转供电，摊子的接线板被暂扣，黑板上明码的电成了案卷里的字。街坊围着问怎么办，常亮把黑板照挂：规矩没错，错的是没给规矩一个名分。他要去找这个名分。",
  "story_events": [],
  "reader_effect": null,
  "timeline": null,
  "beats": [],
  "role": null,
  "plot": {
    "beat": "报修被退、接线板被扣，常亮要给规矩找名分",
    "nodes": [],
    "threads": []
  },
  "resources": [],
  "places": [],
  "knowledge": [],
  "characters": [],
  "relations": [],
  "clock": {
    "advance_days": 2
  },
  "enter": [
    {
      "kind": "clock",
      "key": "clock",
      "expected": 40
    }
  ],
  "exit": [
    {
      "kind": "clock",
      "key": "clock",
      "expected": 42
    }
  ],
  "disclosures": [],
  "world_refs": [
    "rules:rule-private-supply",
    "characters:char-zhou-dianzhang",
    "factions:fact-district-chiefs"
  ],
  "new_entities": [],
  "hooks": [],
  "hook_refs": [],
  "reader_refs": [],
  "history_refs": [],
  "scenes": [],
  "pacing": {},
  "style": {
    "pov": "第三人称主角中心",
    "rhythm": "冷开局，公文话与巷子话对撞",
    "notes": ""
  },
  "dependency_coverage": "partial",
  "reading_coverage": "partial",
  "reading_refs": [],
  "understanding_refs": []
}
```

#### 第 27 章

```json
{
  "chapter": 27,
  "synopsis": "周电长连夜烧旧物，火盆里全是旧单据。秦姨抢先捞了半本老登记簿出来。第一页的日期是三年前那个通宵，签收人一栏有个名字洇了水，只剩半个姓。常亮把簿子和父亲的老照片放在一层，两样都是三年前的夏天留下的东西。",
  "story_events": [],
  "reader_effect": null,
  "timeline": null,
  "beats": [],
  "role": null,
  "plot": {
    "beat": "周电长烧旧物，秦姨抢出半本老登记簿",
    "nodes": [
      {
        "node": "n6",
        "after": "seeded",
        "outcome": "登记簿第一页埋下当事人线索"
      }
    ],
    "threads": [
      {
        "thread": "t5",
        "after": "active",
        "reason": "真相线从半截姓氏开场"
      }
    ]
  },
  "resources": [],
  "places": [],
  "knowledge": [],
  "characters": [],
  "relations": [],
  "clock": {
    "advance_days": 2
  },
  "enter": [
    {
      "kind": "node",
      "key": "n6",
      "expected": null
    },
    {
      "kind": "thread",
      "key": "t5",
      "expected": null
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 42
    }
  ],
  "exit": [
    {
      "kind": "node",
      "key": "n6",
      "expected": "seeded"
    },
    {
      "kind": "thread",
      "key": "t5",
      "expected": "active"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 44
    }
  ],
  "disclosures": [],
  "world_refs": [
    "mysteries:mys-list-origin",
    "characters:char-qin-yi",
    "history:hist-stagger-orig"
  ],
  "new_entities": [],
  "hooks": [
    {
      "hook": "h7",
      "action": "plant",
      "note": "洇掉半个姓的签收人进了铁盒"
    }
  ],
  "hook_refs": [],
  "reader_refs": [],
  "history_refs": [],
  "scenes": [],
  "pacing": {},
  "style": {
    "pov": "第三人称主角中心",
    "rhythm": "夜火光里翻旧纸，句子压低",
    "notes": ""
  },
  "dependency_coverage": "partial",
  "reading_coverage": "partial",
  "reading_refs": [],
  "understanding_refs": []
}
```

#### 第 28 章

```json
{
  "chapter": 28,
  "synopsis": "马六要回来的话在巷子里传。有街坊把家里的电池悄悄备了双份，有人来问摊子还开不开。常亮照旧摆摊，按底册送电。他说了一句话钉在黑板旁：电在这里，规矩也在这里。人心浮动，摊子没散。傍晚摊前的人比往日多了一倍，都是来看他还在不在的。",
  "story_events": [],
  "reader_effect": null,
  "timeline": null,
  "beats": [],
  "role": null,
  "plot": {
    "beat": "回流的风声里摊子照开",
    "nodes": [],
    "threads": []
  },
  "resources": [
    {
      "key": "现金",
      "from": 6000,
      "to": 6200,
      "reason": "平价电费与开销的净进项"
    }
  ],
  "places": [],
  "knowledge": [],
  "characters": [],
  "relations": [],
  "clock": {
    "advance_days": 1
  },
  "enter": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 6000
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 44
    }
  ],
  "exit": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 6200
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 45
    }
  ],
  "disclosures": [],
  "world_refs": [
    "characters:char-ma-liu",
    "factions:fact-oldtown-mutual",
    "geography:geo-dianlixiang"
  ],
  "new_entities": [],
  "hooks": [],
  "hook_refs": [],
  "reader_refs": [],
  "history_refs": [],
  "scenes": [],
  "pacing": {},
  "style": {
    "pov": "第三人称主角中心",
    "rhythm": "短场快过，人心浮动写在对白里",
    "notes": ""
  },
  "dependency_coverage": "partial",
  "reading_coverage": "partial",
  "reading_refs": [],
  "understanding_refs": []
}
```

#### 第 29 章

```json
{
  "chapter": 29,
  "synopsis": "街道办事处的高志远下巷走访，本子上的指标压了一路，走到巷口却站住了：小黑板三行规矩、底册的册页、排队的秩序，比台账漂亮。他围着摊子转了两圈，回去连夜写了份东西。街道的门，头一回朝电力巷开了条缝。临走他在黑板前站了一会儿，把三行字拍照存进手机。",
  "story_events": [],
  "reader_effect": null,
  "timeline": null,
  "beats": [],
  "role": null,
  "plot": {
    "beat": "高志远下巷看见黑板与底册",
    "nodes": [],
    "threads": []
  },
  "resources": [
    {
      "key": "现金",
      "from": 6200,
      "to": 6400,
      "reason": "平价电费与开销的净进项"
    }
  ],
  "places": [],
  "knowledge": [],
  "characters": [],
  "relations": [],
  "clock": {
    "advance_days": 2
  },
  "enter": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 6200
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 45
    }
  ],
  "exit": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 6400
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 47
    }
  ],
  "disclosures": [],
  "world_refs": [
    "factions:fact-street-office",
    "geography:geo-jiedao-banshichu"
  ],
  "new_entities": [
    {
      "id": "gao-shi",
      "kind": "character",
      "name": "高志远",
      "role": "街道办事处派驻老城的网格干事",
      "desire": "在考核年里攒出一个拿得出手的亮点，顺利调回江南",
      "limit": "只能给政策的口子，不担违规的责任，政绩与风险之间先保自己",
      "knowledge_boundary": "看得见台账与考核指标，看不见黑市分成的暗与名单当年的内情"
    }
  ],
  "hooks": [],
  "hook_refs": [],
  "reader_refs": [],
  "history_refs": [],
  "scenes": [],
  "pacing": {},
  "style": {
    "pov": "第三人称主角中心",
    "rhythm": "新视角进场，观察性叙述，节奏轻快",
    "notes": ""
  },
  "dependency_coverage": "partial",
  "reading_coverage": "partial",
  "reading_refs": [],
  "understanding_refs": []
}
```

#### 第 30 章

```json
{
  "chapter": 30,
  "synopsis": "高志远带来共建方案：摊子挂进台区自治试点，街道出章、供电所出通道、经费与检修一并解决。条件也摆着：试点要出指标，挂牌日要好看。常亮没当场应，把方案带回来念给全巷听。名分和套，一起递到了手里。散会后全巷没人说话，都在等常亮先开口，他说再议一晚。",
  "story_events": [],
  "reader_effect": null,
  "timeline": null,
  "beats": [],
  "role": null,
  "plot": {
    "beat": "共建试点方案递到手里，名分与套一起",
    "nodes": [
      {
        "node": "n5",
        "after": "seeded",
        "outcome": "街道的章第一次朝摊子打开"
      }
    ],
    "threads": [
      {
        "thread": "t4",
        "after": "active",
        "reason": "试点线从提案起步"
      }
    ]
  },
  "resources": [
    {
      "key": "现金",
      "from": 6400,
      "to": 6700,
      "reason": "平价电费与开销的净进项"
    }
  ],
  "places": [],
  "knowledge": [],
  "characters": [],
  "relations": [],
  "clock": {
    "advance_days": 2
  },
  "enter": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 6400
    },
    {
      "kind": "node",
      "key": "n5",
      "expected": null
    },
    {
      "kind": "thread",
      "key": "t4",
      "expected": null
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 47
    }
  ],
  "exit": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 6700
    },
    {
      "kind": "node",
      "key": "n5",
      "expected": "seeded"
    },
    {
      "kind": "thread",
      "key": "t4",
      "expected": "active"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 49
    }
  ],
  "disclosures": [],
  "world_refs": [
    "factions:fact-street-office",
    "geography:geo-zizhi-taiqu",
    "rules:rule-private-supply"
  ],
  "new_entities": [],
  "hooks": [],
  "hook_refs": [],
  "reader_refs": [],
  "history_refs": [],
  "scenes": [],
  "pacing": {},
  "style": {
    "pov": "第三人称主角中心",
    "rhythm": "谈判场对白主导，条款一句句压",
    "notes": ""
  },
  "dependency_coverage": "partial",
  "reading_coverage": "partial",
  "reading_refs": [],
  "understanding_refs": []
}
```

#### 第 31 章

```json
{
  "chapter": 31,
  "synopsis": "小赵被抽去给督查组摸底，两头烫脚：马六的好处费还没退干净，督查要的实情他最清楚。他来摊上蹲了半宿，末了问常亮一句：要是把话说出去，我算什么。常亮说，算老城的人。他把烟掐了，走了。常亮望着他走远的背影，把摊上的灯又拨亮了一格。",
  "story_events": [],
  "reader_effect": null,
  "timeline": null,
  "beats": [],
  "role": null,
  "plot": {
    "beat": "小赵被抽给督查摸底，问出我算什么",
    "nodes": [
      {
        "node": "n7",
        "after": "seeded",
        "outcome": "两头人的裂缝开始选边"
      }
    ],
    "threads": [
      {
        "thread": "t6",
        "after": "active",
        "reason": "体系裂缝线开在一个人身上"
      }
    ]
  },
  "resources": [
    {
      "key": "现金",
      "from": 6700,
      "to": 6900,
      "reason": "平价电费与开销的净进项"
    }
  ],
  "places": [],
  "knowledge": [],
  "characters": [],
  "relations": [],
  "clock": {
    "advance_days": 2
  },
  "enter": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 6700
    },
    {
      "kind": "node",
      "key": "n7",
      "expected": null
    },
    {
      "kind": "thread",
      "key": "t6",
      "expected": null
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 49
    }
  ],
  "exit": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 6900
    },
    {
      "kind": "node",
      "key": "n7",
      "expected": "seeded"
    },
    {
      "kind": "thread",
      "key": "t6",
      "expected": "active"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 51
    }
  ],
  "disclosures": [],
  "world_refs": [
    "characters:char-xiao-zhao",
    "factions:fact-street-office"
  ],
  "new_entities": [],
  "hooks": [],
  "hook_refs": [],
  "reader_refs": [],
  "history_refs": [],
  "scenes": [],
  "pacing": {},
  "style": {
    "pov": "第三人称主角中心",
    "rhythm": "夜谈独场，沉默多，烟与话交替",
    "notes": ""
  },
  "dependency_coverage": "partial",
  "reading_coverage": "partial",
  "reading_refs": [],
  "understanding_refs": []
}
```

#### 第 32 章

```json
{
  "chapter": 32,
  "synopsis": "夜里小卖部把话摊开。秦姨算人心，罗清算病人，常亮算电。试点给名分，也要拿走些东西：指标压下来，停电时刻表就不归巷子说了算。常亮定下底线：人命电第一这一条，写进协议才谈，否则挂牌挂到别家去。散场时罗清把底册留在他手边，说了句先紧病人，别的不急。",
  "story_events": [],
  "reader_effect": null,
  "timeline": null,
  "beats": [],
  "role": null,
  "plot": {
    "beat": "小卖部夜议，底线定成人命电第一",
    "nodes": [],
    "threads": []
  },
  "resources": [
    {
      "key": "现金",
      "from": 6900,
      "to": 7000,
      "reason": "平价电费与开销的净进项"
    }
  ],
  "places": [],
  "knowledge": [],
  "characters": [],
  "relations": [],
  "clock": {
    "advance_days": 1
  },
  "enter": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 6900
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 51
    }
  ],
  "exit": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 7000
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 52
    }
  ],
  "disclosures": [],
  "world_refs": [
    "characters:char-qin-yi",
    "characters:char-luo-qing",
    "society:soc-oldtown-order"
  ],
  "new_entities": [],
  "hooks": [],
  "hook_refs": [],
  "reader_refs": [],
  "history_refs": [],
  "scenes": [],
  "pacing": {},
  "style": {
    "pov": "第三人称主角中心",
    "rhythm": "群议场，声部交替，落点清晰",
    "notes": ""
  },
  "dependency_coverage": "partial",
  "reading_coverage": "partial",
  "reading_refs": [],
  "understanding_refs": []
}
```

#### 第 33 章

```json
{
  "chapter": 33,
  "synopsis": "高志远把指标拍在桌上：挂牌日要零停电的展示窗口，时刻表照宣传稿排。常亮当场不接：巷子的电先紧人命，再紧参观。谈崩了一次，经费停了一半。高志远说你这是拿全巷的机会赌你的脾气，常亮说规矩就是规矩。当晚高志远在办公室坐到后半夜，两份稿子摆在一起。",
  "story_events": [],
  "reader_effect": null,
  "timeline": null,
  "beats": [],
  "role": null,
  "plot": {
    "beat": "零停电指标谈崩，经费停半",
    "nodes": [],
    "threads": []
  },
  "resources": [
    {
      "key": "现金",
      "from": 7000,
      "to": 7300,
      "reason": "平价电费与开销的净进项"
    }
  ],
  "places": [],
  "knowledge": [],
  "characters": [
    {
      "entity": "chang-liang",
      "from": {
        "desire": "守住黑板上的规矩和父亲的呼吸机，把摊子做成全巷离不了的正经营生",
        "stance": "规矩交给全巷举手，自己只管供电和底线，不再单打独斗",
        "relationship_focus": "从巷子欠他人情，变成全巷与他互相欠着、互相守着"
      },
      "to": {
        "desire": "让试点给摊子一个合法的名分，人命电仍排第一",
        "stance": "实数给街道，底线不谈判，宁可不要挂牌也不能造假",
        "relationship_focus": "与高志远在指标与人命之间拉锯，靠秦姨罗清守巷子的心"
      },
      "choice": "当场不接零停电的表态",
      "cost": "试点经费停了一半，街道的脸也僵了",
      "reason": "人物处境与立场的节点变化"
    }
  ],
  "relations": [],
  "clock": {
    "advance_days": 2
  },
  "enter": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 7000
    },
    {
      "kind": "character",
      "key": "chang-liang",
      "expected": {
        "desire": "守住黑板上的规矩和父亲的呼吸机，把摊子做成全巷离不了的正经营生",
        "stance": "规矩交给全巷举手，自己只管供电和底线，不再单打独斗",
        "relationship_focus": "从巷子欠他人情，变成全巷与他互相欠着、互相守着"
      }
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 52
    }
  ],
  "exit": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 7300
    },
    {
      "kind": "character",
      "key": "chang-liang",
      "expected": {
        "desire": "让试点给摊子一个合法的名分，人命电仍排第一",
        "stance": "实数给街道，底线不谈判，宁可不要挂牌也不能造假",
        "relationship_focus": "与高志远在指标与人命之间拉锯，靠秦姨罗清守巷子的心"
      }
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 54
    }
  ],
  "disclosures": [],
  "world_refs": [
    "factions:fact-street-office",
    "everyday:evd-life-machines"
  ],
  "new_entities": [],
  "hooks": [
    {
      "hook": "h8",
      "action": "plant",
      "note": "零停电三个字立起来，就等一场真停电"
    }
  ],
  "hook_refs": [],
  "reader_refs": [],
  "history_refs": [],
  "scenes": [],
  "pacing": {},
  "style": {
    "pov": "第三人称主角中心",
    "rhythm": "冲突场正面顶，短句硬碰，门摔上",
    "notes": ""
  },
  "dependency_coverage": "partial",
  "reading_coverage": "partial",
  "reading_refs": [],
  "understanding_refs": []
}
```

#### 第 34 章

```json
{
  "chapter": 34,
  "synopsis": "督查组过江的风声一天紧过一天。高志远两头周旋，把考核的话递过来又收回去。秦姨翻出登记簿，第一页那个洇掉的姓，和督查名单里一个姓对上了半个。常亮觉得这不是巧：三年前定名单的人，就要来看名单的结果。当晚他把登记簿又翻了一遍，把半个姓描在纸角上。",
  "story_events": [],
  "reader_effect": null,
  "timeline": null,
  "beats": [],
  "role": null,
  "plot": {
    "beat": "督查风声日紧，洇掉的姓对上半格",
    "nodes": [],
    "threads": [
      {
        "thread": "t5",
        "after": "active",
        "reason": "姓氏对上半格，谜线贴上督查"
      }
    ]
  },
  "resources": [
    {
      "key": "现金",
      "from": 7300,
      "to": 7500,
      "reason": "平价电费与开销的净进项"
    }
  ],
  "places": [],
  "knowledge": [],
  "characters": [],
  "relations": [],
  "clock": {
    "advance_days": 2
  },
  "enter": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 7300
    },
    {
      "kind": "thread",
      "key": "t5",
      "expected": "active"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 54
    }
  ],
  "exit": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 7500
    },
    {
      "kind": "thread",
      "key": "t5",
      "expected": "active"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 56
    }
  ],
  "disclosures": [],
  "world_refs": [
    "mysteries:mys-list-origin",
    "factions:fact-street-office",
    "history:hist-stagger-orig"
  ],
  "new_entities": [],
  "hooks": [],
  "hook_refs": [
    "h7"
  ],
  "reader_refs": [],
  "history_refs": [],
  "scenes": [],
  "pacing": {},
  "style": {
    "pov": "第三人称主角中心",
    "rhythm": "悬念段，细节埋针，语气收着",
    "notes": ""
  },
  "dependency_coverage": "partial",
  "reading_coverage": "partial",
  "reading_refs": [],
  "understanding_refs": []
}
```

#### 第 35 章

```json
{
  "chapter": 35,
  "synopsis": "马六在江北腹地重整旧部，柴油和短接线一批一批进。他把宝押在挂牌那天：让自治在全城眼前停电，试点一砸，常亮的规矩跟着陪葬。他不会再明着来，他要的是恰好的时机。他让手下去各巷口数配电房，把日子一天天对着挂牌倒推。",
  "story_events": [],
  "reader_effect": null,
  "timeline": null,
  "beats": [],
  "role": null,
  "plot": {
    "beat": "马六重整旧部押注挂牌日",
    "nodes": [],
    "threads": []
  },
  "resources": [
    {
      "key": "现金",
      "from": 7500,
      "to": 7600,
      "reason": "平价电费与开销的净进项"
    }
  ],
  "places": [],
  "knowledge": [],
  "characters": [],
  "relations": [],
  "clock": {
    "advance_days": 1
  },
  "enter": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 7500
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 56
    }
  ],
  "exit": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 7600
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 57
    }
  ],
  "disclosures": [],
  "world_refs": [
    "characters:char-ma-liu",
    "factions:fact-black-market",
    "economy:econ-black-power"
  ],
  "new_entities": [],
  "hooks": [],
  "hook_refs": [],
  "reader_refs": [],
  "history_refs": [],
  "scenes": [],
  "pacing": {},
  "style": {
    "pov": "第三人称主角中心",
    "rhythm": "反打线冷叙述，柴油味贯穿",
    "notes": ""
  },
  "dependency_coverage": "partial",
  "reading_coverage": "partial",
  "reading_refs": [],
  "understanding_refs": []
}
```

#### 第 36 章

```json
{
  "chapter": 36,
  "synopsis": "高温里老线终于打火，检修通道还是没批。常亮揣着新考下的低压电工证，借施工队名义带人把中段线路整段换掉。这是他头一回用合法的手办成事，杆上下来，手心全是汗。电长看着新线没说话，章比话硬。收工时全巷的灯一齐亮起来，比往日任何一晚都齐。",
  "story_events": [],
  "reader_effect": null,
  "timeline": null,
  "beats": [],
  "role": null,
  "plot": {
    "beat": "持证换线，头一回用合法的手办事",
    "nodes": [],
    "threads": []
  },
  "resources": [
    {
      "key": "现金",
      "from": 7600,
      "to": 7800,
      "reason": "平价电费与开销的净进项"
    }
  ],
  "places": [],
  "knowledge": [],
  "characters": [],
  "relations": [],
  "clock": {
    "advance_days": 2
  },
  "enter": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 7600
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 57
    }
  ],
  "exit": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 7800
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 59
    }
  ],
  "disclosures": [],
  "world_refs": [
    "powers:pow-chizheng-diangong",
    "rules:rule-private-supply",
    "characters:char-zhou-dianzhang"
  ],
  "new_entities": [],
  "hooks": [],
  "hook_refs": [],
  "reader_refs": [],
  "history_refs": [],
  "scenes": [],
  "pacing": {},
  "style": {
    "pov": "第三人称主角中心",
    "rhythm": "作业场实感，动作句子扎实，日光",
    "notes": ""
  },
  "dependency_coverage": "partial",
  "reading_coverage": "partial",
  "reading_refs": [],
  "understanding_refs": []
}
```

#### 第 37 章

```json
{
  "chapter": 37,
  "synopsis": "巷口出现生面孔，修车摊的老人朝常亮递了个眼色。夜里配电房外场有人踩点，柴油味压在风里。常亮没惊动，让街坊把进出的脚程都记下来。他知道有人要来，来的人等的是挂牌那天。夜里他绕着台区走了两圈，把每条线的位置又记一遍。",
  "story_events": [],
  "reader_effect": null,
  "timeline": null,
  "beats": [],
  "role": null,
  "plot": {
    "beat": "生面孔踩点，街坊记脚程",
    "nodes": [
      {
        "node": "n8",
        "after": "seeded",
        "outcome": "回来的柴油味被眼色记下"
      }
    ],
    "threads": []
  },
  "resources": [
    {
      "key": "现金",
      "from": 7800,
      "to": 8000,
      "reason": "平价电费与开销的净进项"
    }
  ],
  "places": [],
  "knowledge": [],
  "characters": [],
  "relations": [],
  "clock": {
    "advance_days": 2
  },
  "enter": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 7800
    },
    {
      "kind": "node",
      "key": "n8",
      "expected": null
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 59
    }
  ],
  "exit": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 8000
    },
    {
      "kind": "node",
      "key": "n8",
      "expected": "seeded"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 61
    }
  ],
  "disclosures": [],
  "world_refs": [
    "characters:char-ma-liu",
    "society:soc-oldtown-order",
    "geography:geo-xiangkou-taiqu"
  ],
  "new_entities": [],
  "hooks": [
    {
      "hook": "h10",
      "action": "plant",
      "note": "柴油味压在风里，日子对上了挂牌那天"
    }
  ],
  "hook_refs": [],
  "reader_refs": [],
  "history_refs": [],
  "scenes": [],
  "pacing": {},
  "style": {
    "pov": "第三人称主角中心",
    "rhythm": "戒备段静中带紧，夜风与眼色",
    "notes": ""
  },
  "dependency_coverage": "partial",
  "reading_coverage": "partial",
  "reading_refs": [],
  "understanding_refs": []
}
```

#### 第 38 章

```json
{
  "chapter": 38,
  "synopsis": "督查组进驻街道，头一场摊牌会就问得见骨：试点是不是造假，黑市为什么断不了，名单到底怎么排的。常亮答实数，高志远答台账，两本记录对不齐。散会后督查组留下一句：明天看巷子。登记簿在家等着上场。回家的路上，秦姨把登记簿用布包好，抱在怀里没撒手。",
  "story_events": [],
  "reader_effect": null,
  "timeline": null,
  "beats": [],
  "role": null,
  "plot": {
    "beat": "督查摊牌头场，实数与台账对不齐",
    "nodes": [
      {
        "node": "n5",
        "after": "advanced",
        "outcome": "试点被督查盯上，指标变成审视"
      }
    ],
    "threads": [
      {
        "thread": "t4",
        "after": "active",
        "reason": "试点线顶着督查的目光走"
      }
    ]
  },
  "resources": [
    {
      "key": "现金",
      "from": 8000,
      "to": 8200,
      "reason": "平价电费与开销的净进项"
    }
  ],
  "places": [],
  "knowledge": [],
  "characters": [],
  "relations": [],
  "clock": {
    "advance_days": 2
  },
  "enter": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 8000
    },
    {
      "kind": "node",
      "key": "n5",
      "expected": "seeded"
    },
    {
      "kind": "thread",
      "key": "t4",
      "expected": "active"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 61
    }
  ],
  "exit": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 8200
    },
    {
      "kind": "node",
      "key": "n5",
      "expected": "advanced"
    },
    {
      "kind": "thread",
      "key": "t4",
      "expected": "active"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 63
    }
  ],
  "disclosures": [
    {
      "topic": "错峰名单第一版来历",
      "after": "suspected",
      "note": "登记簿的日期把疑点引向当年那晚的会"
    }
  ],
  "world_refs": [
    "factions:fact-street-office",
    "factions:fact-list-system",
    "mysteries:mys-list-origin"
  ],
  "new_entities": [],
  "hooks": [],
  "hook_refs": [],
  "reader_refs": [],
  "history_refs": [],
  "scenes": [],
  "pacing": {},
  "style": {
    "pov": "第三人称主角中心",
    "rhythm": "会场高压，问答短促，静默重",
    "notes": ""
  },
  "dependency_coverage": "partial",
  "reading_coverage": "partial",
  "reading_refs": [],
  "understanding_refs": []
}
```

#### 第 39 章

```json
{
  "chapter": 39,
  "synopsis": "摊牌第二场摆到巷口。秦姨把老登记簿放上桌，第一页的日期和签收人，对上了三年前那晚的会议记录。通宵敲定的第一版名单，江北压末档换江南保产。督查组里有人变了脸色：那个洇掉的姓，就在他们中间。屋里静得能听见电表走字。",
  "story_events": [],
  "reader_effect": null,
  "timeline": null,
  "beats": [],
  "role": null,
  "plot": {
    "beat": "登记簿对上敲定之夜，姓就在督查边上",
    "nodes": [
      {
        "node": "n6",
        "after": "advanced",
        "outcome": "日期与签收人对上那晚的记录"
      }
    ],
    "threads": [
      {
        "thread": "t5",
        "after": "active",
        "reason": "真相线逼到摊牌桌前"
      }
    ]
  },
  "resources": [
    {
      "key": "现金",
      "from": 8200,
      "to": 8500,
      "reason": "平价电费与开销的净进项"
    }
  ],
  "places": [],
  "knowledge": [],
  "characters": [],
  "relations": [],
  "clock": {
    "advance_days": 2
  },
  "enter": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 8200
    },
    {
      "kind": "node",
      "key": "n6",
      "expected": "seeded"
    },
    {
      "kind": "thread",
      "key": "t5",
      "expected": "active"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 63
    }
  ],
  "exit": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 8500
    },
    {
      "kind": "node",
      "key": "n6",
      "expected": "advanced"
    },
    {
      "kind": "thread",
      "key": "t5",
      "expected": "active"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 65
    }
  ],
  "disclosures": [],
  "world_refs": [
    "mysteries:mys-list-origin",
    "history:hist-stagger-orig",
    "characters:char-qin-yi"
  ],
  "new_entities": [],
  "hooks": [
    {
      "hook": "h7",
      "action": "payoff",
      "note": "洇掉的姓对上了督查名单里的人"
    }
  ],
  "hook_refs": [],
  "reader_refs": [],
  "history_refs": [],
  "scenes": [],
  "pacing": {},
  "style": {
    "pov": "第三人称主角中心",
    "rhythm": "揭示前场，翻纸声与心跳，句子极短",
    "notes": ""
  },
  "dependency_coverage": "partial",
  "reading_coverage": "partial",
  "reading_refs": [],
  "understanding_refs": []
}
```

#### 第 40 章

```json
{
  "chapter": 40,
  "synopsis": "名单的来历全盘揭开：权重公式三年没动过一行，护着末档的不是哪一个人，是每一个从末档里捞到好处的位置：电长的执行权、电贩的护城河、拿名单当政绩的章。督查组把这一页复印带走。问题从为什么是我们，变成了秩序该由谁定。常亮的心里落了地。",
  "story_events": [],
  "reader_effect": null,
  "timeline": null,
  "beats": [],
  "role": "揭示章：敲定之夜与护着末档的利益上桌",
  "plot": {
    "beat": "名单来历全盘揭开",
    "nodes": [
      {
        "node": "n6",
        "after": "resolved",
        "outcome": "来历全貌揭开，谜题换位"
      }
    ],
    "threads": [
      {
        "thread": "t5",
        "after": "resolved",
        "reason": "真相线收口"
      }
    ]
  },
  "resources": [
    {
      "key": "现金",
      "from": 8500,
      "to": 8800,
      "reason": "平价电费与开销的净进项"
    }
  ],
  "places": [],
  "knowledge": [
    {
      "who": "chang-liang",
      "topic": "错峰名单第一版来历",
      "from": "suspected",
      "to": "confirmed",
      "reason": "摊牌会上听见全貌，疑点落定"
    }
  ],
  "characters": [],
  "relations": [],
  "clock": {
    "advance_days": 2
  },
  "enter": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 8500
    },
    {
      "kind": "knowledge",
      "key": "chang-liang:错峰名单第一版来历",
      "expected": "suspected"
    },
    {
      "kind": "node",
      "key": "n6",
      "expected": "advanced"
    },
    {
      "kind": "thread",
      "key": "t5",
      "expected": "active"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 65
    }
  ],
  "exit": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 8800
    },
    {
      "kind": "knowledge",
      "key": "chang-liang:错峰名单第一版来历",
      "expected": "confirmed"
    },
    {
      "kind": "node",
      "key": "n6",
      "expected": "resolved"
    },
    {
      "kind": "thread",
      "key": "t5",
      "expected": "resolved"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 67
    }
  ],
  "disclosures": [
    {
      "topic": "错峰名单第一版来历",
      "after": "confirmed",
      "note": "敲定之夜与权重真相在摊牌会上全盘托出"
    }
  ],
  "world_refs": [
    "mysteries:mys-list-origin",
    "rules:rule-cuufeng-list",
    "factions:fact-list-system"
  ],
  "new_entities": [],
  "hooks": [
    {
      "hook": "h3",
      "action": "payoff",
      "note": "三年前的那个通宵，终于有了全貌"
    }
  ],
  "hook_refs": [],
  "reader_refs": [],
  "history_refs": [],
  "scenes": [],
  "pacing": {},
  "style": {
    "pov": "第三人称主角中心",
    "rhythm": "大揭示段，叙述干净利落，回声收尾",
    "notes": ""
  },
  "dependency_coverage": "partial",
  "reading_coverage": "partial",
  "reading_refs": [],
  "understanding_refs": []
}
```

#### 第 41 章

```json
{
  "chapter": 41,
  "synopsis": "督查组把试点当样本盯死了：全市的眼睛都在，任何一次供电失败，都会被放大成否定自治的理由。常亮肩上的分量翻倍，白天巡查夜里盘点，头晕的毛病又来，他谁也没说。罗清看了他一眼，他躲开了。夜里盘点完，他在黑板前站了很久，没让人看出来。",
  "story_events": [],
  "reader_effect": null,
  "timeline": null,
  "beats": [],
  "role": null,
  "plot": {
    "beat": "样本被盯死，常亮瞒下头晕",
    "nodes": [],
    "threads": []
  },
  "resources": [
    {
      "key": "现金",
      "from": 8800,
      "to": 8600,
      "reason": "平价电费与开销的净进项"
    }
  ],
  "places": [],
  "knowledge": [],
  "characters": [],
  "relations": [],
  "clock": {
    "advance_days": 2
  },
  "enter": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 8800
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 67
    }
  ],
  "exit": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 8600
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 69
    }
  ],
  "disclosures": [],
  "world_refs": [
    "geography:geo-zizhi-taiqu",
    "mechanisms:mech-body-power",
    "characters:char-luo-qing"
  ],
  "new_entities": [],
  "hooks": [
    {
      "hook": "h9",
      "action": "plant",
      "note": "头晕瞒下了，眼神躲开了"
    }
  ],
  "hook_refs": [],
  "reader_refs": [],
  "history_refs": [],
  "scenes": [],
  "pacing": {},
  "style": {
    "pov": "第三人称主角中心",
    "rhythm": "重压段，白天巡查夜里盘点，语气干",
    "notes": ""
  },
  "dependency_coverage": "partial",
  "reading_coverage": "partial",
  "reading_refs": [],
  "understanding_refs": []
}
```

#### 第 42 章

```json
{
  "chapter": 42,
  "synopsis": "生面孔摸进配电房外场，被轮值的街坊一五一十记下：几点来、几点走、车的颜色。短接的路径浮出来，指向挂牌日的展示线路。常亮把记录交给高志远，两人头一回坐在同一边：这局要一起接。高志远把记录复印了一份，原件留给常亮贴在黑板旁。",
  "story_events": [],
  "reader_effect": null,
  "timeline": null,
  "beats": [],
  "role": null,
  "plot": {
    "beat": "踩点记录交高志远，两人同边",
    "nodes": [
      {
        "node": "n8",
        "after": "advanced",
        "outcome": "短接路径浮出，指向展示线路"
      }
    ],
    "threads": []
  },
  "resources": [
    {
      "key": "现金",
      "from": 8600,
      "to": 8800,
      "reason": "平价电费与开销的净进项"
    }
  ],
  "places": [],
  "knowledge": [],
  "characters": [],
  "relations": [],
  "clock": {
    "advance_days": 2
  },
  "enter": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 8600
    },
    {
      "kind": "node",
      "key": "n8",
      "expected": "seeded"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 69
    }
  ],
  "exit": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 8800
    },
    {
      "kind": "node",
      "key": "n8",
      "expected": "advanced"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 71
    }
  ],
  "disclosures": [],
  "world_refs": [
    "characters:char-ma-liu",
    "factions:fact-street-office",
    "society:soc-oldtown-order"
  ],
  "new_entities": [],
  "hooks": [],
  "hook_refs": [],
  "reader_refs": [],
  "history_refs": [],
  "scenes": [],
  "pacing": {},
  "style": {
    "pov": "第三人称主角中心",
    "rhythm": "对表段冷静，合作语气初成",
    "notes": ""
  },
  "dependency_coverage": "partial",
  "reading_coverage": "partial",
  "reading_refs": [],
  "understanding_refs": []
}
```

#### 第 43 章

```json
{
  "chapter": 43,
  "synopsis": "督查摊牌第三场，小赵把好处费退了，站出来作证：协查的眼线、囤电的仓库、电长分成的走法，一样一样摆上桌面。会场哗然。他的临时工牌子当场收了，人却站直了。证词落地，裂缝成了常亮伸进体系里的那道缝。散会后常亮在门口等他，两个人隔着马路点了点头。",
  "story_events": [],
  "reader_effect": null,
  "timeline": null,
  "beats": [],
  "role": "证言章：眼线站到实情一边",
  "plot": {
    "beat": "小赵退钱作证，证词落地",
    "nodes": [
      {
        "node": "n7",
        "after": "advanced",
        "outcome": "证言落地，裂缝变成入口"
      }
    ],
    "threads": [
      {
        "thread": "t6",
        "after": "active",
        "reason": "证言站住，线往收口走"
      }
    ]
  },
  "resources": [
    {
      "key": "现金",
      "from": 8800,
      "to": 9000,
      "reason": "平价电费与开销的净进项"
    }
  ],
  "places": [],
  "knowledge": [
    {
      "who": "chang-liang",
      "topic": "周电长与马六的分成",
      "from": "suspected",
      "to": "confirmed",
      "reason": "证词把当年那笔钱的走法坐实"
    }
  ],
  "characters": [
    {
      "entity": "xiao-zhao",
      "from": null,
      "to": {
        "desire": "凭老城实情换一个正经身份",
        "stance": "好处费退了，证言站到实情一边，不再两头传话",
        "relationship_focus": "从马六的眼线变成常亮伸进供电所的那道缝"
      },
      "choice": "退了好处费当众作证",
      "cost": "临时工的牌子当场收了",
      "reason": "人物处境与立场的节点变化"
    }
  ],
  "relations": [
    {
      "source": "chang-liang",
      "target": "xiao-zhao",
      "key": "传话",
      "from": null,
      "to": "同阵",
      "reason": "证言之后，缝变成了阵"
    }
  ],
  "clock": {
    "advance_days": 2
  },
  "enter": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 8800
    },
    {
      "kind": "knowledge",
      "key": "chang-liang:周电长与马六的分成",
      "expected": "suspected"
    },
    {
      "kind": "character",
      "key": "xiao-zhao",
      "expected": null
    },
    {
      "kind": "relations",
      "key": "chang-liang>xiao-zhao:传话",
      "expected": null
    },
    {
      "kind": "node",
      "key": "n7",
      "expected": "seeded"
    },
    {
      "kind": "thread",
      "key": "t6",
      "expected": "active"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 71
    }
  ],
  "exit": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 9000
    },
    {
      "kind": "knowledge",
      "key": "chang-liang:周电长与马六的分成",
      "expected": "confirmed"
    },
    {
      "kind": "character",
      "key": "xiao-zhao",
      "expected": {
        "desire": "凭老城实情换一个正经身份",
        "stance": "好处费退了，证言站到实情一边，不再两头传话",
        "relationship_focus": "从马六的眼线变成常亮伸进供电所的那道缝"
      }
    },
    {
      "kind": "relations",
      "key": "chang-liang>xiao-zhao:传话",
      "expected": "同阵"
    },
    {
      "kind": "node",
      "key": "n7",
      "expected": "advanced"
    },
    {
      "kind": "thread",
      "key": "t6",
      "expected": "active"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 73
    }
  ],
  "disclosures": [
    {
      "topic": "周电长的分成网络",
      "after": "confirmed",
      "note": "证词把分成网络钉死在桌面"
    }
  ],
  "world_refs": [
    "characters:char-xiao-zhao",
    "factions:fact-list-system",
    "characters:char-zhou-dianzhang"
  ],
  "new_entities": [],
  "hooks": [],
  "hook_refs": [],
  "reader_refs": [],
  "history_refs": [],
  "scenes": [],
  "pacing": {},
  "style": {
    "pov": "第三人称主角中心",
    "rhythm": "证言场庄重，句子站稳，哗然一拍",
    "notes": ""
  },
  "dependency_coverage": "partial",
  "reading_coverage": "partial",
  "reading_refs": [],
  "understanding_refs": []
}
```

#### 第 44 章

```json
{
  "chapter": 44,
  "synopsis": "挂牌前夜全巷演练，展示线路真被人动了手脚，半条巷子骤黑。没人喊：底册启动，自筹电池上线，黑板顺序一格一格来，一个钟头把供电原样续回去。督查组的人站在黑地里看完全程，在记录上写：非预案，成立。这一夜比挂牌日本身像挂牌。",
  "story_events": [],
  "reader_effect": null,
  "timeline": null,
  "beats": [],
  "role": "高潮章：停电夜反成自治的实证",
  "plot": {
    "beat": "挂牌前夜线路被动手脚，自治当场上演",
    "nodes": [],
    "threads": []
  },
  "resources": [
    {
      "key": "现金",
      "from": 9000,
      "to": 8700,
      "reason": "平价电费与开销的净进项"
    }
  ],
  "places": [],
  "knowledge": [],
  "characters": [],
  "relations": [],
  "clock": {
    "advance_days": 2
  },
  "enter": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 9000
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 73
    }
  ],
  "exit": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 8700
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 75
    }
  ],
  "disclosures": [],
  "world_refs": [
    "everyday:evd-window-queue",
    "factions:fact-oldtown-mutual",
    "geography:geo-zizhi-taiqu"
  ],
  "new_entities": [],
  "hooks": [
    {
      "hook": "h8",
      "action": "payoff",
      "note": "真停电了，一个钟头原样续回去"
    }
  ],
  "hook_refs": [],
  "reader_refs": [],
  "history_refs": [],
  "scenes": [],
  "pacing": {},
  "style": {
    "pov": "第三人称主角中心",
    "rhythm": "实战夜节奏极快，短句连打，黑地里见光",
    "notes": ""
  },
  "dependency_coverage": "partial",
  "reading_coverage": "partial",
  "reading_refs": [],
  "understanding_refs": []
}
```

#### 第 45 章

```json
{
  "chapter": 45,
  "synopsis": "人赃并获。柴油、短接线、守在巷口的旧车一齐被扣，马六的人连人带货堵在当场，治安与供电所联合清街。经营三年的黑市线在老城断了根，马六彻底出局。他被带走时看了常亮一眼，常亮没看他，在看黑板。当晚黑板前围满人，有人把三行规矩念出了声。",
  "story_events": [],
  "reader_effect": null,
  "timeline": null,
  "beats": [],
  "role": null,
  "plot": {
    "beat": "人赃并获，黑市断根清街",
    "nodes": [
      {
        "node": "n8",
        "after": "resolved",
        "outcome": "人赃并获，黑市清出本街"
      },
      {
        "node": "n7",
        "after": "resolved",
        "outcome": "作证的人进了网格协理名录"
      }
    ],
    "threads": [
      {
        "thread": "t6",
        "after": "resolved",
        "reason": "裂缝线收口成常亮的缝"
      }
    ]
  },
  "resources": [
    {
      "key": "现金",
      "from": 8700,
      "to": 8900,
      "reason": "平价电费与开销的净进项"
    }
  ],
  "places": [],
  "knowledge": [],
  "characters": [
    {
      "entity": "ma-liu",
      "from": {
        "desire": "保住囤电的本钱，等常亮栽跟头再杀回来",
        "stance": "明面价牌倒了就把生意做进阴处",
        "relationship_focus": "与周电长从分成伙计变成互相攥着把柄的人"
      },
      "to": {
        "desire": "另找门路，离开江北这条电上的食",
        "stance": "认栽出局，不再碰这片台区",
        "relationship_focus": "与周电长互相攥的把柄松了手，两败俱伤"
      },
      "choice": "把最后的本钱押给挂牌日一刀",
      "cost": "人货俱失，彻底出局",
      "reason": "人物处境与立场的节点变化"
    }
  ],
  "relations": [],
  "clock": {
    "advance_days": 2
  },
  "enter": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 8700
    },
    {
      "kind": "character",
      "key": "ma-liu",
      "expected": {
        "desire": "保住囤电的本钱，等常亮栽跟头再杀回来",
        "stance": "明面价牌倒了就把生意做进阴处",
        "relationship_focus": "与周电长从分成伙计变成互相攥着把柄的人"
      }
    },
    {
      "kind": "node",
      "key": "n8",
      "expected": "advanced"
    },
    {
      "kind": "node",
      "key": "n7",
      "expected": "advanced"
    },
    {
      "kind": "thread",
      "key": "t6",
      "expected": "active"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 75
    }
  ],
  "exit": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 8900
    },
    {
      "kind": "character",
      "key": "ma-liu",
      "expected": {
        "desire": "另找门路，离开江北这条电上的食",
        "stance": "认栽出局，不再碰这片台区",
        "relationship_focus": "与周电长互相攥的把柄松了手，两败俱伤"
      }
    },
    {
      "kind": "node",
      "key": "n8",
      "expected": "resolved"
    },
    {
      "kind": "node",
      "key": "n7",
      "expected": "resolved"
    },
    {
      "kind": "thread",
      "key": "t6",
      "expected": "resolved"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 77
    }
  ],
  "disclosures": [],
  "world_refs": [
    "characters:char-ma-liu",
    "factions:fact-black-market",
    "rules:rule-private-supply"
  ],
  "new_entities": [],
  "hooks": [
    {
      "hook": "h10",
      "action": "payoff",
      "note": "赌的日子到了，人也到了"
    }
  ],
  "hook_refs": [],
  "reader_refs": [],
  "history_refs": [],
  "scenes": [],
  "pacing": {},
  "style": {
    "pov": "第三人称主角中心",
    "rhythm": "收网场干净利落，不拖不解释",
    "notes": ""
  },
  "dependency_coverage": "partial",
  "reading_coverage": "partial",
  "reading_refs": [],
  "understanding_refs": []
}
```

#### 第 46 章

```json
{
  "chapter": 46,
  "synopsis": "证词和登记簿一起落地，周电长被调离台区，分成网络连根拔。移交清单里，老线的档案和检修通道一并划进试点协议附件。断了快两个月的报修单，批下来了。常亮把新批的单子贴在黑板旁边，两张纸并排。有街坊把两张纸的边角对齐，用透明胶一丝丝贴好。",
  "story_events": [],
  "reader_effect": null,
  "timeline": null,
  "beats": [],
  "role": null,
  "plot": {
    "beat": "电长调离，检修通道写进协议附件",
    "nodes": [],
    "threads": []
  },
  "resources": [
    {
      "key": "现金",
      "from": 8900,
      "to": 8700,
      "reason": "平价电费与开销的净进项"
    }
  ],
  "places": [],
  "knowledge": [],
  "characters": [],
  "relations": [],
  "clock": {
    "advance_days": 2
  },
  "enter": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 8900
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 77
    }
  ],
  "exit": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 8700
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 79
    }
  ],
  "disclosures": [],
  "world_refs": [
    "characters:char-zhou-dianzhang",
    "factions:fact-district-chiefs",
    "rules:rule-private-supply"
  ],
  "new_entities": [],
  "hooks": [],
  "hook_refs": [],
  "reader_refs": [],
  "history_refs": [],
  "scenes": [],
  "pacing": {},
  "style": {
    "pov": "第三人称主角中心",
    "rhythm": "善后段平铺，两张纸并排的画面感",
    "notes": ""
  },
  "dependency_coverage": "partial",
  "reading_coverage": "partial",
  "reading_refs": [],
  "understanding_refs": []
}
```

#### 第 47 章

```json
{
  "chapter": 47,
  "synopsis": "试点协议定稿：错峰名单不动，台区内的窗口顺序、人命电第一、平价私供，一条一条写进协议和小黑板，定价仍由全台区举手。高志远念完最后一款，全巷举手通过。常亮在签名栏写下名字，笔画很稳。签完名他把笔还给高志远，说这章比他一个人说话管用。",
  "story_events": [],
  "reader_effect": null,
  "timeline": null,
  "beats": [],
  "role": null,
  "plot": {
    "beat": "协议定稿全巷举手，签名落笔",
    "nodes": [],
    "threads": [
      {
        "thread": "t4",
        "after": "active",
        "reason": "协议落定，只等挂牌"
      }
    ]
  },
  "resources": [
    {
      "key": "现金",
      "from": 8700,
      "to": 9000,
      "reason": "平价电费与开销的净进项"
    }
  ],
  "places": [],
  "knowledge": [],
  "characters": [],
  "relations": [],
  "clock": {
    "advance_days": 2
  },
  "enter": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 8700
    },
    {
      "kind": "thread",
      "key": "t4",
      "expected": "active"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 79
    }
  ],
  "exit": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 9000
    },
    {
      "kind": "thread",
      "key": "t4",
      "expected": "active"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 81
    }
  ],
  "disclosures": [],
  "world_refs": [
    "factions:fact-street-office",
    "geography:geo-zizhi-taiqu",
    "rules:rule-window"
  ],
  "new_entities": [],
  "hooks": [],
  "hook_refs": [],
  "reader_refs": [],
  "history_refs": [],
  "scenes": [],
  "pacing": {},
  "style": {
    "pov": "第三人称主角中心",
    "rhythm": "定章节奏稳，念条款如点卯",
    "notes": ""
  },
  "dependency_coverage": "partial",
  "reading_coverage": "partial",
  "reading_refs": [],
  "understanding_refs": []
}
```

#### 第 48 章

```json
{
  "chapter": 48,
  "synopsis": "罗清当众把常亮瞒下的晕倒旧事掀了：筹备这一个多月，他晕过两回。全巷吵起来，最后举手表决定下休息日：那天摊子交底册轮值，谁也不许叫他。常亮想反对，举手的人比他那次大会还多。他说不过一巷子人。散会后罗清把木牌钉在窗台边，钉子敲得很响。",
  "story_events": [],
  "reader_effect": null,
  "timeline": null,
  "beats": [],
  "role": null,
  "plot": {
    "beat": "晕倒旧事被掀，休息日举手通过",
    "nodes": [],
    "threads": []
  },
  "resources": [
    {
      "key": "现金",
      "from": 9000,
      "to": 8800,
      "reason": "平价电费与开销的净进项"
    }
  ],
  "places": [],
  "knowledge": [],
  "characters": [],
  "relations": [
    {
      "source": "chang-liang",
      "target": "luo-qing",
      "key": "照护",
      "from": "搭手",
      "to": "管束",
      "reason": "骂成了规矩，休息日她盯着"
    }
  ],
  "clock": {
    "advance_days": 2
  },
  "enter": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 9000
    },
    {
      "kind": "relations",
      "key": "chang-liang>luo-qing:照护",
      "expected": "搭手"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 81
    }
  ],
  "exit": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 8800
    },
    {
      "kind": "relations",
      "key": "chang-liang>luo-qing:照护",
      "expected": "管束"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 83
    }
  ],
  "disclosures": [],
  "world_refs": [
    "characters:char-luo-qing",
    "society:soc-oldtown-order",
    "mechanisms:mech-body-power"
  ],
  "new_entities": [],
  "hooks": [
    {
      "hook": "h9",
      "action": "payoff",
      "note": "旧事当众掀开，换来一块休息日的木牌"
    }
  ],
  "hook_refs": [],
  "reader_refs": [],
  "history_refs": [],
  "scenes": [],
  "pacing": {},
  "style": {
    "pov": "第三人称主角中心",
    "rhythm": "暖场吵闹，群声起伏，笑声收",
    "notes": ""
  },
  "dependency_coverage": "partial",
  "reading_coverage": "partial",
  "reading_refs": [],
  "understanding_refs": []
}
```

#### 第 49 章

```json
{
  "chapter": 49,
  "synopsis": "挂牌日。自治台区试点的牌子挂在巷口，供电简报的样本页印着电力巷的小黑板，别的街道打电话来问细节。督查组临走留了话：样本要一直立着。常亮站在牌子底下，还是那个一天二十度的人，巷子已经离不开他。有街坊放了一挂小鞭炮，巷口的灯亮得像过年。",
  "story_events": [],
  "reader_effect": null,
  "timeline": null,
  "beats": [],
  "role": "终章：试点挂牌，样本外传",
  "plot": {
    "beat": "挂牌日，样本进简报",
    "nodes": [
      {
        "node": "n5",
        "after": "resolved",
        "outcome": "试点挂牌，样本进供电简报"
      }
    ],
    "threads": [
      {
        "thread": "t4",
        "after": "resolved",
        "reason": "试点线在牌子底下收口"
      }
    ]
  },
  "resources": [
    {
      "key": "现金",
      "from": 8800,
      "to": 9200,
      "reason": "平价电费与开销的净进项"
    }
  ],
  "places": [],
  "knowledge": [],
  "characters": [
    {
      "entity": "chang-liang",
      "from": {
        "desire": "让试点给摊子一个合法的名分，人命电仍排第一",
        "stance": "实数给街道，底线不谈判，宁可不要挂牌也不能造假",
        "relationship_focus": "与高志远在指标与人命之间拉锯，靠秦姨罗清守巷子的心"
      },
      "to": {
        "desire": "错峰名单不动，就把这片台区的序排好，让巷子离不开的是规矩不是他一身力气",
        "stance": "供电交给网和协议，自己只守人命电那条线和休息日",
        "relationship_focus": "从常师傅变成这片街区的基础，父亲与全巷同守一份规矩"
      },
      "choice": "把摊子交进协议，只守人命电那条线和休息日",
      "cost": "一辈子就是一天二十度的人，更大的场面只能靠网靠规矩靠别人",
      "reason": "人物处境与立场的节点变化"
    }
  ],
  "relations": [],
  "clock": {
    "advance_days": 1
  },
  "enter": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 8800
    },
    {
      "kind": "character",
      "key": "chang-liang",
      "expected": {
        "desire": "让试点给摊子一个合法的名分，人命电仍排第一",
        "stance": "实数给街道，底线不谈判，宁可不要挂牌也不能造假",
        "relationship_focus": "与高志远在指标与人命之间拉锯，靠秦姨罗清守巷子的心"
      }
    },
    {
      "kind": "node",
      "key": "n5",
      "expected": "advanced"
    },
    {
      "kind": "thread",
      "key": "t4",
      "expected": "active"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 83
    }
  ],
  "exit": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 9200
    },
    {
      "kind": "character",
      "key": "chang-liang",
      "expected": {
        "desire": "错峰名单不动，就把这片台区的序排好，让巷子离不开的是规矩不是他一身力气",
        "stance": "供电交给网和协议，自己只守人命电那条线和休息日",
        "relationship_focus": "从常师傅变成这片街区的基础，父亲与全巷同守一份规矩"
      }
    },
    {
      "kind": "node",
      "key": "n5",
      "expected": "resolved"
    },
    {
      "kind": "thread",
      "key": "t4",
      "expected": "resolved"
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 84
    }
  ],
  "disclosures": [],
  "world_refs": [
    "geography:geo-zizhi-taiqu",
    "factions:fact-street-office",
    "economy:econ-peak-power"
  ],
  "new_entities": [],
  "hooks": [],
  "hook_refs": [],
  "reader_refs": [],
  "history_refs": [],
  "scenes": [],
  "pacing": {},
  "style": {
    "pov": "第三人称主角中心",
    "rhythm": "终场明亮，叙述放开，余光长",
    "notes": ""
  },
  "dependency_coverage": "partial",
  "reading_coverage": "partial",
  "reading_refs": [],
  "understanding_refs": []
}
```

#### 第 50 章

```json
{
  "chapter": 50,
  "synopsis": "名单没动，江还是那条江，窗口照旧时有时无。区别是巷子里自己排自己的序：底册轮值、休息日的木牌挂在窗台边，父亲的呼吸机连着全巷的眼睛。有孩子问他是做什么的，街坊替他答：常师傅，这片停电的巷子归他供电。他坐在窗台边守着呼吸机，听着巷子里的动静，心里踏实。",
  "story_events": [],
  "reader_effect": null,
  "timeline": null,
  "beats": [],
  "role": "卷尾章：老城自己排自己的序",
  "plot": {
    "beat": "名单未动，巷子自己排序，常师傅",
    "nodes": [],
    "threads": []
  },
  "resources": [
    {
      "key": "现金",
      "from": 9200,
      "to": 9300,
      "reason": "平价电费与开销的净进项"
    }
  ],
  "places": [],
  "knowledge": [],
  "characters": [],
  "relations": [],
  "clock": {
    "advance_days": 1
  },
  "enter": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 9200
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 84
    }
  ],
  "exit": [
    {
      "kind": "resources",
      "key": "现金",
      "expected": 9300
    },
    {
      "kind": "clock",
      "key": "clock",
      "expected": 85
    }
  ],
  "disclosures": [],
  "world_refs": [
    "geography:geo-zizhi-taiqu",
    "mysteries:mys-list-origin",
    "characters:char-chang-shoutian"
  ],
  "new_entities": [],
  "hooks": [],
  "hook_refs": [],
  "reader_refs": [],
  "history_refs": [],
  "scenes": [],
  "pacing": {},
  "style": {
    "pov": "第三人称主角中心",
    "rhythm": "卷尾极缓，一句一景，收在书名上",
    "notes": ""
  },
  "dependency_coverage": "partial",
  "reading_coverage": "partial",
  "reading_refs": [],
  "understanding_refs": []
}
```
