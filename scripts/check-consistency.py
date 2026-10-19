#!/usr/bin/env python3
"""盐选七步法 跨文件口径一致性自检（治"手工同步遗漏"的根故障）。
用法: python3 scripts/check-consistency.py   退出码 0=全过, 1=有失配
每次改 SKILL/references/templates/assets 后跑一遍，口径改回去会被本组断言抓住。
断言三层：ASSERTS=文件级串检查（机制串/命名/禁项）；CROSS_SAME=跨文件同文检查
      （设计性双份段落<入口速查/质量门镜像>改一处忘另一处即被抓，归一化只比文字）；
      AT_ROWS=AT 行级口径检查（同一字符串在别行也有出现时，只改某行值文件级看不见——行级补盲）。
另含在位枚举：9 工具/根文件与 docs/规则库新树（README + shared 8 + 七阶段 28）/templates 12/
      assets 规范文件 5/genre-cards 33 个 .md（README+32 卡）。
另含死链检查（）：全库 md 内反引号包裹的相对路径（.md/.py）须能解析到真实文件——
      `../`/`./` 开头按所在目录严格解析（作者已明确表达相对意图），其余按「技能根 /
      references 根 / 所在目录」多重基线宽容解析（兼容既有三种路径约定，防误报）；
      产物链命名（0X-中文名.md）与纯文件名简写不计。层级少写/多写一级即被抓——
      这类错只在运行时才暴露为"加载空气"，故固化为门禁。与 209 组口径断言并列、独立计段。
全部断言锚挂七类目录新结构：stageN-* 单文件断言改指 stageN-*/ 四文件之一
（枚举锚定串随枚举迁移，如 stage4 九条/七项 → stage4-draft/self-check.md，
18 维/76 项两表 → stage6-review/quality-gate.md）；md_library 扫描面 exemplars 禁入。
"""
import re, sys, pathlib, os
ROOT = pathlib.Path(__file__).resolve().parent.parent

# (说明, 文件|文件列表|None, 必须存在, 不得存在)；path=None 全库扫描（SKILL + references + templates + assets 规范文件 + genre-cards），
# path=列表表示多文件同锁（双份漂移：每个文件都必须含该串，任一份漏改即被抓）
ASSERTS = [
    # --- 主文件结构：七阶段一览与四确认门 ---
    # 阶段名已改为「初审与终审」，锁串随改（旧词「审稿」靠 SKILL 其他
    # 位置的"审稿隔离"等字样苟过=假绿，语义必须对齐现行阶段名）
    ("七阶段一览",            "SKILL.md", ["选题", "梗概", "细纲", "写作", "润色", "初审", "交付"], []),
    # 断言覆盖率系统审计：46 条规则中 39 条无直接断言守护（部分由内容串间接守护）。
    # 本组补的是「**高风险 + 零守护 + 措辞唯一**」的四条评审/结构诚信类规则——
    # 这类规则被删改时不会触发任何脚本症状（不像阈值类会立刻打架），最需要断言兜底。
    ("润色期禁动结构-stage5", "references/stage5-polish/rules.md",
                              ["禁在润色期新增/删除情节节点", "不在润色期动结构"], []),
    ("红队三档不混写-stage6", "references/stage6-review/rules.md",
                              ["设计取舍", "不得包装成", "三档不得混写"], []),
    ("终审禁新设标准-stage6", "references/stage6-review/rules.md",
                              ["终审层禁新设标准", "6a 一套尺、6b 一套尺"], []),
    ("禁平铺名词章题-stage7", "references/stage7-delivery/rules.md",
                              ["投稿章题必须带情绪动词", "平铺名词"], []),
    # 投稿包两件 + 投稿正文零标记的机检落点（脚本侧锚实现判罚串）
    ("投稿包两件正文零标记-脚本", "scripts/check-artifacts.py",
                              ["投稿包多出文件", "投稿正文含机检标记",
                               "样例 README 属说明文件已豁免"], []),
    ("投稿包两件零标记-stage7gate", "references/stage7-delivery/quality-gate.md",
                              ["只含两件", "零标注零标记"], []),
    # darwin dim4 优化：确认门标记纪律的约定串须常驻——2026-10-17 首批 🔴 标记
    # 在后续八轮迭代里被覆盖丢失且无守护，本条 + 下方计数断言是根因修复
    ("确认门标记纪律约定",     "SKILL.md",
                              ["🔴 CHECKPOINT 标记纪律", "缺 🔴 的确认门视为未设门",
                               "不得删任何 🔴"], []),
    ("四确认门计数=4",        "SKILL.md", ["确认门①", "确认门②", "确认门③", "确认门④", "四道确认门"],
                              ["确认门⑤", "三道确认门", "五道确认门"]),
    ("产物链编号完整",         "SKILL.md", ["00-选题评估.md", "01-梗概.md", "02-细纲.md", "03-正文.md",
                              "04-润色标注稿.md", "04-正文净稿.md", "05-初审报告.md", "05-终审报告.md",
                              "06-投稿包", "07-复盘.md", "08-结构指纹.md"], [r"09-结构指纹", r"05-审稿报告"]),
    # --- 全局硬条款 ---
    ("编造防线",              "SKILL.md", ["编造防线", "禁止代填"], []),
    ("禁直出三件套",          "SKILL.md", ["禁直出", "check-metrics.py --fragment"], []),
    ("口径唯一权威挂AT表",     "SKILL.md", ["口径唯一权威", "authority-table.md"], []),
    ("脚本降级条款",          "SKILL.md", ["脚本降级", "人工核验（脚本降级）"], []),
    ("效果边界声明",          "SKILL.md", ["效果边界", "机检全绿 ≠ 能过稿"], []),
    ("执行方式二选一",        "SKILL.md", ["执行方式", "方式①全自动", "逐阶段确认"], []),
    # --- 盐选单口径（禁盐言双口径残留） ---
    ("盐选单口径",            "SKILL.md", ["盐选唯一口径"], [r"两口径互斥", r"盐言 55-65%"]),
    ("盐选单口径AT26",        "references/shared/authority-table.md", ["AT-26", "盐选唯一口径"], [r"盐言 55-65%"]),
    # --- 关键数字口径（AT 表为唯一源，SKILL 只引） ---
    ("AT-04付费墙3000-4000",  "references/shared/authority-table.md", ["AT-04", "3000-4000"], []),
    ("AT-24标题三档",         "references/shared/authority-table.md", ["AT-24", "16-20 字合格"], [r"≤15 字不剧透"]),
    ("标题三档同步SKILL",      "SKILL.md", ["16-20 字合格"], [r"≤15 字不剧透"]),
    ("AT-31双打分≥25",        "references/shared/authority-table.md", ["AT-31", "≥25"], []),
    ("AT-32九维均分≥8",       "references/shared/authority-table.md", ["AT-32", "≥8"], []),
    ("双打分同步SKILL",       "SKILL.md", ["≥25", "均分 ≥8"], []),
    ("AT-22伏笔回收率≥80%",   "references/shared/authority-table.md", ["AT-22", "≥80%"], []),
    ("回收率同步SKILL",        "SKILL.md", ["≥80%"], []),
    ("AT-63段落合规率≥60%",   "references/shared/authority-table.md", ["AT-63", "≤50 字段落 ÷ 总段落 ≥60%"], []),
    # AT-14 单一硬线 ≥90%（取消「≥80% 下限 / 90% 目标」双线：80 与 85 在机检层同判，双线口径是假的）
    # 反向断言锁「双线措辞不得回流」——改回双线即报错。
    ("AT-14标注覆盖≥90%",      "references/shared/authority-table.md", ["AT-14", "≥90%"], [r"标注覆盖[率]?\s*(?:≥|<)?\s*80%"]),
    ("覆盖≥90同步stage5",      "references/stage5-polish/quality-gate.md", ["≥90%"], [r"标注覆盖[率]?[^\n]{0,10}80%"]),
    ("覆盖≥90同步SKILL",       "SKILL.md", ["≥90%（AT-14）"], [r"覆盖\s*(?:≥|<)?\s*80%"]),
    ("覆盖≥90同步模板",        "templates/04-annotated.md", ["≥90%（AT-14）"], [r"标注覆盖[率]?[^\n]{0,10}80%"]),
    ("覆盖≥90同步prompts",     "assets/prompts.md", ["≥90%（AT-14）"], [r"标注覆盖[率]?[^\n]{0,10}80%"]),
    ("覆盖≥90同步门总览",      "references/README.md", ["≥90%（AT-14）"], [r"标注覆盖[率]?[^\n]{0,10}80%"]),
    ("覆盖≥90同步self-check",  "references/stage5-polish/self-check.md", ["≥90%（AT-14）"], [r"标注覆盖[率]?[^\n]{0,10}80%"]),
    ("覆盖≥90同步stage6",      "references/stage6-review/quality-gate.md", ["标注覆盖率 ≥90%"], [r"标注覆盖率[^\n]{0,10}80%"]),
    # --- 篇幅口径锁定（防多带走私与错引回流） ---
    ("length占比带25-35",     "scripts/check-length.py", ["25-35% 带", "25 <= pct <= 35"],
                              ["20-35% 带", "20 <= pct <= 35", r"全文 20-35%"]),
    ("length中卡点引AT-10",   "scripts/check-length.py", ["中卡点 45-55%（AT-10"], ["中卡点 45-55%（AT-27"]),
    ("length卡后钩引AT-18",   "scripts/check-length.py", ["卡后钩子密度（AT-18）", "（AT-18：≥3"],
                              ["卡后钩子密度（AT-53）"]),
    ("stage1同质化引AT-46",   "references/stage1-topic/workflow.md", ["AT-46 红线"], ["AT-36 红线"]),
    ("ai弱化副词引AT-37",     "scripts/check-ai.py", ["AT-37"], ["AT-24 必删", "次内（AT-24）"]),
    ("篇幅口径SKILL",          "SKILL.md", ["12000-16000", "AT-01"], [r"12000-18000", r"8000-25000"]),
    ("篇幅口径AT表",           "references/shared/authority-table.md", ["12000-16000"], []),
    ("篇幅口径mss硬门",        "references/shared/mss-rules.md", ["12000-16000"], [r"8000-25000"]),
    ("篇幅口径stage6",         "references/stage6-review/workflow.md", ["F1 总字数 12000-16000"], [r"8000-25000"]),
    ("篇幅口径stage5",         "references/stage5-polish/quality-gate.md", ["12000-16000"], [r"12000-18000"]),
    ("篇幅口径脚本F1",         "scripts/check-mss.py", ["12000 <= n_chars <= 16000", "总字数不在 12000-16000"], [r"8000 <= n_chars"]),
    ("旧篇幅带禁回流",          "references/shared/authority-table.md", [], [r"缺省目标 12000-18000 字 \|"]),
    ("AT表唯一权威声明",       "references/shared/authority-table.md", ["唯一权威"], []),
    # --- 结构指纹挂接（08 命名，禁 09 残留） ---
    ("指纹挂SKILL",           "SKILL.md", ["08-结构指纹.md", "check-fingerprint.py"], [r"09-结构指纹"]),
    ("指纹glob改08",          "scripts/check-fingerprint.py", ["08-结构指纹"], [r"09-结构指纹"]),
    # --- 阶段细则关键机制串（一阶段四文件，缺串即断链） ---
    ("stage1热度四指标",       "references/stage1-topic/workflow.md", ["热度四指标", "候选卡", "双打分"], []),
    ("stage1红线与限流",       "references/stage1-topic/rules.md", ["红线", "限流词"], []),
    ("stage2梗概卡八字段",     "references/stage2-synopsis/quality-gate.md", ["一句话梗概", "悬念三要素", "情绪弧线", "双峰反转"], []),
    ("stage3细纲双视图",       "references/stage3-outline/workflow.md", ["双视图", "节末钩", "伏笔", "黄金三章"], []),
    ("stage4双锚句实测",       "references/stage4-draft/self-check.md", ["--paywall", "--first-twist", "全篇核验"], []),
    # 「全篇核验 7 项」被 5 处引用且含第 2/3 项有序交叉引用——枚举必须常驻 stage4 self-check，防删枚举留空引用
    ("stage4全篇核验七项枚举", "references/stage4-draft/self-check.md",
     ["全篇核验七项", "1. **三件套整篇复跑**", "2. **产物链机检**", "3. **双锚句",
      "4. **伏笔回收率", "5. **钩子密度与节末钩轮换**", "6. **信息投喂节奏**", "7. **标称即实测**",
      # 中卡点（AT-10）易漏：首锁双锚句只覆盖免费区。锁「--midpoint 出现在**全篇核验第3项**里」
      # —— 注意不能用裸 "--midpoint" 做串：workflow.md 第四节也有该串，同文件内删掉 self-check
      # 的第3项仍会命中（实测过：断言恒过=假绿）。故锚在第3项的专属上下文串上。
      "中卡点须单独给锚句"], []),
    # 「单章自查表 9 条」被 4 处引用——枚举必须常驻 stage4 self-check。
    # 每章自查九条：「段落/句长/标点」细项以指针形式指向 style-rules 三遍清单（唯一真源），
    # 此锁锁「指针存在 + 唯一真源指向」，防退回「两套清单各查一遍」的重复执行。
    ("stage4每章自查九条枚举", "references/stage4-draft/self-check.md",
     ["每章写作纪律与自查九条", "1. **章门字数**", "2. **开篇专项门**", "3. **场景**",
      "4. **对话**", "5. **段落/句长/标点**", "6. **环境必须参与叙事**",
      "7. **伏笔落地**", "8. **钩子与节末**", "9. **三件套与靶点**",
      "style-rules.md` 第十节", "禁与本条重复过两遍"], []),
    # 三遍清单是细项唯一真源，两端都要有「单向指向」声明，防退回两套并行
    ("style-rules三遍清单唯一真源", "references/shared/style-rules.md",
     ["本表是「段落结构/标点呼吸/字词语感」细项的唯一清单", "禁两套清单重复过"], []),
    ("stage5润色双版本",       "references/stage5-polish/quality-gate.md", ["靶点句", "check-ai.py", "双版本一致性"], []),
    ("stage6机检数字报告",     "references/stage6-review/workflow.md", ["check-mss.py", "机检数字报告", "根因路由"], []),
    # 全库 8 处引用「6b 终审」——stage6 workflow 须显式定义 6a/6b 分工并落地终审工序节，防「引用而无定义」
    # 改名：审稿与终审 → 初审与终审；6a=初审（产 05-初审报告）/ 6b=终审（产 05-终审报告）
    ("stage6初审终审分工",     "references/stage6-review/workflow.md",
                              ["初审（6a）/ 终审（6b）两半", "终审（6b）= 终审放行", "终审工序（6b，按序执行，任一不过即回退）",
                               "05-初审报告.md", "05-终审报告.md"], [r"审稿与终审"]),
    # genre-map 3 处引用「配角五规矩」——定义须常驻 stage3 workflow 人设卡工序，防悬空引用
    ("配角五规矩定义",         "references/stage3-outline/workflow.md", ["配角五规矩", "不喧宾夺主", "三查"], []),
    # genre-map 逻辑八查引用须按名（因果链），防回退到错位的「第 3 查」
    ("genre-map逻辑八查引用", "references/shared/genre-map.md", ["逻辑八查「因果链」"], [r"逻辑八查第 3 查"]),
    # 范围边界：本技能只到「创作 + 投稿打包」，投稿后运营数据不跟进——禁路径 B/赞藏比回流
    ("stage7范围边界纪律",     "references/stage7-delivery/rules.md", ["结构指纹", "复盘三问"], ["路径 B", "赞藏比", "引流试水篇"]),
    # --- principles 全局机制 ---
    ("principles四确认门",     "references/shared/principles.md", ["确认门①", "确认门④"], []),
    ("principles两层分离",     "references/shared/principles.md", ["规则库", "执行面"], []),
    ("principles降级条款",     "references/shared/principles.md", ["降级"], []),
    ("principles质量门制",     "references/shared/principles.md", ["质量门", "不过不前进"], []),
    # --- 产物链命名规范（templates/README） ---
    ("命名规范细纲单文件",    "templates/README.md", ["02-细纲.md", "单文件两篇"], []),
    ("命名规范禁拆回",       "templates/README.md", ["禁拆回"], []),
    # --- 投稿包件数口径（两件 + 机检提交包分立；禁三件/旧术语回流） ---
    # 禁项正则须容忍 Markdown 强调号（"投稿包**只含三件**"中 ** 插在词间——紧邻正则会漏）
    ("投稿包两件禁回流",      None, [], [r"投稿包\*{0,2}只含三件", r"投稿包\*{0,2}三件", r"机检适配件"]),
    # --- 脚本执行面口径 ---
    ("artifacts双视图适配",    "scripts/check-artifacts.py", ["f02 = f03 = find_file"], []),
    ("checkall整篇核验glob",   "scripts/check-all.py", ["03-*正文*.md", "04-*净稿*.md"], []),
    ("checkall探针含mss",      "scripts/check-all.py", ["check-mss.py"], []),
    ("checkall防跳过漏检",     "scripts/check-all.py", ["防'跳过=通过'漏检"], []),
    ("mss五模块权重",          "scripts/check-mss.py", ["形式", "标题导语梗概金句", "结构位置", "密度代理", "回收兑现"], []),
    ("mss封顶59",              "scripts/check-mss.py", ["59"], []),
    ("length双锚句开关",       "scripts/check-length.py", ["--paywall", "--first-twist"], []),
    ("metrics片段模式",        "scripts/check-metrics.py", ["--fragment"], []),
    ("ai五查在位",             "scripts/check-ai.py", ["禁用标点"], []),
    # --- 回归层 ---
    ("mss对拍进回归",          "tests/run-tests.py", ["mss-good", "mss-bad"], []),
    ("七步法命名进回归",       "tests/run-tests.py", ["mini-good/02-细纲.md", "mini-annot/04-润色标注稿.md"], []),
    ("五测量脚本进回归",       "tests/run-tests.py", ["check-length", "check-metrics", "check-ai",
                              "check-artifacts", "check-consistency"], []),
    # --- 横切 references（机制串，缺串即断链） ---
    ("质量门索引",             "references/README.md", ["不过不前进", "七阶段质量门", "确认门"], []),
    ("产物模板链",             "templates/README.md", ["00-选题评估.md", "02-细纲.md", "06-投稿包",
                              "08-结构指纹.md", "机检提交"], []),
    ("提示词七阶段",           "assets/prompts.md", ["[任务]", "确认门①", "快照自检", "重进五步"], []),
    ("执行卡两卡",             "scripts/README.md", ["卡一", "卡二", "脚本降级", "退出码"], []),
    ("MSS规则",                "references/shared/mss-rules.md", ["封顶 59", "机检结构匹配", "待人工复核"], []),
    # MSS 三档命名须统一为 AT-66「高匹配/低匹配/不匹配」——禁实现侧「高/中/低」回流
    ("MSS分层命名-mss-rules",  "references/shared/mss-rules.md", ["≥80 高匹配", "60-79 低匹配", "<60 不匹配"], [r"机检匹配中"]),
    ("MSS分层命名-脚本",       "scripts/check-mss.py", ["机检匹配高", "机检匹配低", "机检不匹配"], [r"机检匹配中"]),
    # 术语同义规范须常驻权威表（付费墙=付费卡点、免费区=免费试读区）
    ("付费墙术语同义注",       "references/shared/authority-table.md",
     ["术语同步", "主付费墙 = 主付费卡点", "免费区 = 免费试读区"], []),
    # 开篇两章加权（AT-79）与免费区钩子加密（AT-80）须四端一致：AT 表定义 + stage3 配额 + stage4 实测 + SKILL 速查
    # 加权带漂移即回到「全篇均分」——第 1 章取 1800 会把卡点挤到第 2 章末，直接损付费转化
    ("开篇两章加权-AT表",      "references/shared/authority-table.md",
     ["AT-79", "第 1 章 2200-2800 字；第 2 章 2000-2800 字", "两章均**禁取下限**"], []),
    ("开篇两章加权-stage3",    "references/stage3-outline/workflow.md",
     ["开篇两章加权（AT-79，配额门）", "第 1 章 **2200-2800**、第 2 章 **2000-2800**"], []),
    ("开篇两章加权-stage4",    "references/stage4-draft/self-check.md",
     ["第 1 章 2200-2800、第 2 章 2000-2800，两章禁取下限**（AT-79）"], []),
    ("免费区钩子加密",         "references/stage3-outline/workflow.md",
     ["免费区钩子加密（AT-80）", "每 500 字 ≥1 个信息型钩子"], []),
    # 卡点落位算法（AT-41）：禁回退为「免费试读区=第一章，章末即卡点」——与 AT-04 字位带数学冲突
    ("卡点落位算法-AT表",      "references/shared/authority-table.md",
     ["卡点定位算法（按序执行，取第一个满足者）", "主付费卡点必须落在第 1 章末之后的第一个可用断点"], []),
    ("卡点落位算法-stage3",    "references/stage3-outline/workflow.md",
     ["卡点跟字位走，不跟章号走"], []),
    # 九维阈值 ≥8（AT-32）——genre-map 命题决策链须对齐，防口径漂移
    ("genre-map九维阈值",      "references/shared/genre-map.md",
     ["命题九维评分均分 ≥8/10 动笔"],
     [r"九维[^。]{0,12}≥7"]),
    # 12 硬门划分须与 AT-66/stage6 一致：标题拆 2（字数/标点）、分节并 1——防 mss-rules 回退为「标题并 1/分节拆 2」
    # 注：must 走字面子串匹配（竖线不转义）；forbid 走正则（竖线须 \| 否则被当「或」元字符）
    ("MSS硬门划分对齐AT-66",   "references/shared/mss-rules.md",
     ["| 2 | 标题字数 | >20 字", "| 3 | 标题标点", "| 7 | 分节格式",
      "| 8 | 卡点标记 | 缺失，或首锁偏离全文 25%-35%"],
     [r"\| 2 \| 标题 \| >20 字", r"\| 7 \| 分节编号"]),
    ("会话拆分",               "references/shared/session-split.md", ["会话拆分", "确认门③", "重进五步", "每批 2-3 章"], []),
    # --- 领域 references（七步法口径锚） ---
    ("文风规则锚",             "references/shared/style-rules.md", ["「」", "破格配额", "裁决表"], []),
    # 自查清单标题项数须与实际 checkbox 数一致（三遍 20 项）；防「28 项」等错计回流
    ("style-rules自查项数",     "references/shared/style-rules.md", ["三遍 20 项"], [r"28 项"]),
    ("去AI规则锚",             "references/shared/kill-ai.md", ["信息守恒", "误报防护", "check-ai"], []),
    ("题材规则锚",             "references/shared/genre-map.md", ["防狗血", "空白度"], []),
    ("指纹规则锚",             "references/shared/fingerprint.md", ["六维", "MIN_OVERLAP", "08-结构指纹.md"], []),
    # 部署宿主参数已并入 docs/install.md（contextWindow/maxTokens/降级三档）
    ("部署规则锚",             "docs/install.md", ["contextWindow", "session-split.md"], []),
    # 五段表/断点信号曾整块复制进 deployment-guide 且与 session-split 漂移——权威单一化，禁回流
    ("部署禁复写五段表",       "docs/install.md", [], ["用户拍板梗概（确认门②）", "用户确认细纲（确认门③", "单会话段已覆盖 ≥2 个阶段"]),
    # --- 根目录文件与 docs ---
    ("AGENTS审稿隔离",         "AGENTS.md", ["材料包六件", "降半档", "pre_delivery", "净稿", "同上下文自审"], []),
    # 预交付门聚合口径「任一 2/3 = 修完再交」四份存续：scripts/README ↔ references/README 已由 CROSS_SAME 锁；
    # SKILL 禁直出条款与 AGENTS 宿主门各一份（prose 层）——补存在性锁，改聚合口径不许只改一处
    ("聚合口径SKILL禁直出",     "SKILL.md", ["exit 2/3 = 修完再交"], []),
    ("聚合口径AGENTS宿主门",    "AGENTS.md", ["exit 2/3 = 修完再交"], []),
    # AGENTS.md §三 是 SKILL 禁直出三件套的宿主层镜像（第三个副本）：脚本名与 --fragment 口径须同步在位
    ("禁直出三件套AGENTS固化",  "AGENTS.md", ["check-metrics.py", "check-ai.py", "check-length.py", "check-all.py", "--fragment"], []),
    # AT-56 备注指定 check-all 聚合为跨脚本权威（短语在备注列，AT_ROWS 只扫口径列，故走文件级）
    ("AT-56聚合口径备注锁",    "references/shared/authority-table.md", ["任一 2/3=修完再交"], []),
    ("CHANGELOG定版",          "docs/CHANGELOG.md", ["2.0.0", "authority-table.md", "check-consistency.py"], []),
    ("安装说明边界",           "docs/install.md", ["零依赖", "脚本降级", "过程产物不入包"], []),
    # --- 规则库完整性：SKILL.md 索引覆盖 references 新树（README + shared 8 + 七阶段目录） ---
    ("SKILL索引覆盖规则库",    "SKILL.md", ["references/README.md", "shared/principles.md", "shared/authority-table.md",
                              "shared/style-rules.md", "shared/kill-ai.md", "shared/mss-rules.md",
                              "shared/genre-map.md", "shared/fingerprint.md", "shared/session-split.md",
                              "stage1-topic/", "stage2-synopsis/", "stage3-outline/", "stage4-draft/",
                              "stage5-polish/", "stage6-review/", "stage7-delivery/"], []),
    # --- genre-cards 题材提示卡库（已迁 assets/，32 卡 + README；路由表在 genre-map 第十四节） ---
    ("genre-cards索引进SKILL", "SKILL.md", ["genre-cards", "禁全量 32 张同载"], []),
    ("genre-cards路由表在位",  "references/shared/genre-map.md",
                              ["genre-cards", "aliases", "主疼位初值"], []),
    ("genre-cards口径收口",    "assets/genre-cards/README.md",
                              ["authority-table.md", "AT-26"], [r"yanxuan-platform-spec"]),
    # --- 过稿/爆款优化口径在库（缺串即断链） ---
    # 预埋表五张→六张（新增名场面预埋表 AT-69）：SKILL/stage3/templates 同步，禁"五张预埋表"回流
    ("六张预埋表同步SKILL",    "SKILL.md", ["六张预埋表", "名场面预埋表"], ["五张预埋表"]),
    ("六张预埋表同步stage3",   "references/stage3-outline/workflow.md",
                              ["六张预埋表", "名场面预埋表"], ["五张预埋表"]),
    ("六张预埋表同步templates", "templates/02-outline.md",
                              ["六张预埋表", "名场面预埋表"], ["五张预埋表"]),
    ("卡点三型同步stage3",     "references/stage3-outline/workflow.md", ["卡点三型", "撕裂"], []),
    ("章题情绪动词同步stage3", "references/stage3-outline/workflow.md", ["章题", "情绪动词"], []),
    ("导语三要素同步stage4",   "references/stage4-draft/quality-gate.md",
                              ["反常识场景", "身份悬念", "未完成动作", "将破未破"], []),
    ("主疼位同步stage2",       "references/stage2-synopsis/workflow.md",
                              ["主疼位", "被辜负", "求而不得"], []),
    ("疼位公式矩阵同步genre-map", "references/shared/genre-map.md", ["疼位×公式矩阵"], []),
    # 红线 18 项正本归 assets/compliance-redlines.md 一处；SKILL.md 只留指针——锁「正本存全 + SKILL 必须指向它」，禁整段复制
    ("红线18项正本在compliance", "assets/compliance-redlines.md",
                              ["主角违法不惩", "军婚/官场/医疗事故", "禁入清单（18 项"], []),
    ("红线18项SKILL指针",      "SKILL.md",
                              ["18 项禁入清单与各项判据见 `assets/compliance-redlines.md`", "唯一正本，本文件不复述"], []),
    # 反向锁：SKILL 里一旦出现红线明细串（=有人把 18 项抄回来），立即报错
    ("红线18项禁回流SKILL",    "SKILL.md", [],
                              [r"自杀自残美化", r"校园霸凌美化", r"主角违法不惩",
                               r"军婚/官场/医疗事故", r"未成年恋判据"]),
    ("征文信号同步stage1",     "references/stage1-topic/workflow.md", ["征文活动信号", "AT-75"], []),
    # --- 阶段 1 产物结构断言（）---
    # 阶段 1 是唯一无产物机检面的阶段（00-选题评估.md 只在 check-metrics 注释里被提到）。
    # 不新增脚本（选题判断本质靠人，加脚本只会把"格式过了"误当"题行了"），
    # 只在既有文件级断言里锁**结构完整性**——六节齐、路线声明在、空白度字段在、红线判据指向正本。
    ("阶段1模板六节齐",         "templates/00-topic-evaluation.md",
                              ["1. 用户输入与意图锚点", "2. 扫榜热点总览表", "3. 候选卡 ×3",
                               "4. 双打分表", "5. 红线筛查矩阵", "6. 推荐结论"], []),
    ("阶段1模板空白度字段",     "templates/00-topic-evaluation.md", ["空白度搜索结果"], []),
    ("阶段1模板路线条件化",     "templates/00-topic-evaluation.md",
                              ["命题路线", "热点依据卡", "不得省略"], []),
    ("阶段1门含空白度5b",       "references/stage1-topic/quality-gate.md", ["5b", "空白度", "红海"], []),
    ("阶段1自查含空白度",       "references/stage1-topic/self-check.md", ["空白度自检"], []),
    ("阶段1红线判据指正本",     "references/stage1-topic/rules.md", ["compliance-redlines.md"], []),
    # 红线矩阵 54 格（18 项 × 3 候选）：防退化成"三候选均零命中"一句话
    ("阶段1模板红线54格",       "templates/00-topic-evaluation.md",
                              ["54 格", "逐格打勾", "限流词三类"], []),
    ("阶段1样例红线54格",       "examples/full-run/00-选题评估.md",
                              ["54 格", "⚠️ **待核**", "无付费触点", "主角违法不惩"],
                              [r"A/B/C 三行均\s*[“\"]?18 项零命中"]),
    # 新增空白度门必须同步到门总览（references/README.md 曾是唯一漏网文件）
    ("阶段1门总览含空白度",     "references/README.md", ["空白度四维已搜且非红海"], []),
    ("SKILL门表含空白度",       "SKILL.md", ["空白度四维已搜且非红海"], []),
    # 自检红线段必须锁 54 格 + 三态（禁退化成一句话零命中）
    ("阶段1自查红线54格",       "references/stage1-topic/self-check.md",
                              ["54 格", "待核", "替代方向"], []),
    # 禁裸文件名红线引用一律禁（死链检查只扫反引号路径，裸名扫不到）
    ("禁裸文件名红线引用",      "references/stage1-topic/quality-gate.md",
                              ["assets/compliance-redlines.md"],
                              [r"与\s*compliance-redlines\.md"]),
    # --- 阶段 2：九字段正本同序 + 口径锁死---
    # 字段行必须逐条匹配（含 Markdown 强调号），禁"脚注提到但字段行已删"蒙混过关——
    # 断言串须带 "| N | " 行首锚，否则删掉字段行仍会被脚注里的同名词满足
    ("阶段2模板九字段齐",        "templates/01-synopsis.md",
                              ["| 1 | 一句话梗概（双版本）", "| 2 | **目标读者与情绪承诺**",
                               "| 3 | 核心冲突", "| 4 | 核心悬念三要素",
                               "| 5 | 情绪弧线任务清单", "| 6 | 双峰反转 + 分级",
                               "| 7 | 核心意象闭环", "| 8 | 主角弧光一句话",
                               "| 9 | 结局走向与暂定标题"], []),
    ("阶段2样例九字段齐",        "examples/full-run/01-梗概.md",
                              ["目标读者与情绪承诺", "不可退让的理由", "结局走向", "九字段齐"], []),
    # 靶点口径：密度是判罚权威、总数按篇幅带折算；禁旧裸口径「总数 ≥15」回流
    ("阶段2靶点折算口径",       "templates/01-synopsis.md",
                              ["AT-33", "18-24", "22-29"], [r"靶点总数\s*[（(]≥15"]),
    ("阶段2样例靶点合规",       "examples/full-run/01-梗概.md",
                              ["AT-33", "按 1.35 万字折算"], [r"靶点总数\s*6\b"]),
    ("AT33折算口径在位",        "references/shared/authority-table.md",
                              ["AT-33", "18-24 个", "22-29 个", "已废止"], []),
    ("AT81压迫递进四层在位",    "references/shared/authority-table.md",
                              ["AT-81", "3000-4000 字", "递增"], []),
    # 压迫递进四层：四处都在查，须有 AT 编号可引
    ("压迫递进引AT81-模板",     "templates/01-synopsis.md", ["AT-81"], []),
    ("压迫递进引AT81-细纲",     "templates/02-outline.md", ["AT-33"], []),
    ("压迫递进引AT81-stage6",   "references/stage6-review/quality-gate.md", ["AT-81"], []),
    # 门 10 合并项 + 门 11 新增项
    ("阶段2门10合并标题",       "references/stage2-synopsis/quality-gate.md",
                              ["暂定标题合规 + 兑现预演", "AT-24", "AT-65"], []),
    ("阶段2门11情绪承诺落地",   "references/stage2-synopsis/quality-gate.md",
                              ["情绪承诺有落地字段", "不可退让"], []),
    # 阶段 3 承接须为九项逐项对照（历史漏 4 项致悬念三要素可整项丢失）
    ("阶段3承接九项对照",       "references/stage3-outline/quality-gate.md",
                              ["九字段", "悬念三要素", "核心冲突", "结局走向"], []),
    ("阶段2九字段禁退回八",     None, [], [r"梗概卡八字段", r"梗概八字段"]),
    # ── 阶段 3 加固（建议 1-8）─────────────────────────────────────
    # 建议1：机检曾把节拍表当独立靶点表，F 项按章数算分母 → 覆盖率 200%，AT-14 硬门恒过失效
    ("机检靶点表精确匹配",      "scripts/check-artifacts.py",
                              ["exact_col='靶点'", "exclude_lead='章'", "覆盖率 {cov:.0f}% > 100%"], []),
    # 建议2：节拍表列数曾三方不一致（门说8/workflow 定义 9/样例 7），统一为九列
    ("节拍表九列-门",           "references/stage3-outline/quality-gate.md",
                              ["**九列在位**", "靶点标注位"], [r"八列在位"]),
    ("节拍表九列-stage6",       "references/stage6-review/quality-gate.md",
                              ["**九列在位**", "靶点标注位"], [r"八列在位"]),
    ("节拍表九列-样例",         "examples/full-run/02-细纲.md",
                              ["| 章 | 章题 | 字数预算 | 场景 | 节拍功能 | 节末钩（带类型后缀） | 伏笔动作 | 信息投喂（AT-21） | 靶点标注位 |"], []),
    # 建议3：门10 伏笔地图双向一致曾无任何阶段回查、脚本也不对账
    ("门10双向一致有P1回查",    "references/stage6-review/quality-gate.md",
                              ["伏笔地图与上篇双向一致"], []),
    # P2 删两项（平台口径/相似度）18→16，合计 77→75
    ("AT54总数75项",            "references/shared/authority-table.md",
                              ["P1 **47**", "= **75** 项"], [r"P1 46 / P2 18 = 76 项", r"= \*\*77\*\* 项"]),
    ("样例伏笔地图双向一致",    "examples/full-run/02-细纲.md",
                              ["伏笔地图（人设视角：谁埋的/谁收的/指向哪层信息差）", "与上篇①伏笔规划表**逐条同序、编号互通**"], []),
    # 建议4：AT-43 记忆点显影位声明「细纲+正文双查」但门 9 口径缺
    ("门9含AT43记忆点",         "references/stage3-outline/quality-gate.md",
                              ["记忆点显影位", "AT-43"], []),
    ("P1人设卡含AT43",         "references/stage6-review/quality-gate.md",
                              ["记忆点显影位"], []),
    # 建议5：AT-72 声明归属「阶段 3 节拍表」但 stage3 零提及
    ("AT72入阶段3-workflow",    "references/stage3-outline/workflow.md",
                              ["AT-72", "闭环"], []),
    ("AT72入阶段3-门",          "references/stage3-outline/quality-gate.md", ["AT-72"], []),
    ("AT72入阶段3-自查",        "references/stage3-outline/self-check.md", ["AT-72"], []),
    # 建议6：check-length.py 输入为正文，阶段 3 调用必 exit 3——禁再列为阶段 3 机检
    ("阶段3禁用check-length",   "references/stage3-outline/self-check.md",
                              ["不适用于阶段 3", "exit 3"], [r"通过条件 \| exit 0"]),
    # 建议7：模板重复文字残留
    ("模板承接无重复句",        "templates/02-outline.md", [], [r"对不上先改细纲；对不上先改细纲"]),
    # 建议8：样例六张预埋表须齐（历史仅伏笔表 1 张，机检缺陷因此长期不可见）
    ("样例六表齐",              "examples/full-run/02-细纲.md",
                              ["① 伏笔规划表", "② 金句预埋清单", "③ 意象系统清单",
                               "④ 情绪靶点规划表", "⑤ 时间线台账", "⑥ 名场面预埋表"], []),
    ("样例靶点表头非节拍表",    "examples/full-run/02-细纲.md",
                              ["| 靶点编号 | 所在章 | 字位约 | 靶点类型 | 星级 | 主疼位归属（AT-73） |"], []),
    # 范围边界：投稿后跟进内容不在本技能范围——全库禁回流
    ("禁投稿后跟进内容-SKILL", "SKILL.md", ["不跟进"], ["路径 B", "复盘四问", "赞藏比"]),
    ("禁投稿后跟进内容-stage7", "references/stage7-delivery/rules.md", ["不跟进"], ["免费自荐位", "50 赞", "72 小时", "复盘四问"]),
    ("禁投稿后跟进内容-templates", "templates/README.md", [], ["复盘四问", "72h 数据归因", "路径 B"]),
    ("禁投稿后跟进内容-scriptsREADME", "scripts/README.md", [], ["复盘四问"]),
    ("禁投稿后跟进内容-referencesREADME", "references/README.md", [], ["复盘四问"]),
    ("禁投稿后跟进内容-prompts", "assets/prompts.md", [], ["路径 B", "50 赞", "复盘四问", "72h"]),
    ("复盘三问同步SKILL",      "SKILL.md", ["复盘三问"], ["复盘四问"]),
    ("复盘三问同步stage7",     "references/stage7-delivery/rules.md", ["复盘三问"], ["复盘四问"]),
    ("AI声明同步SKILL",        "SKILL.md", ["AI 辅助创作声明", "AT-74"], []),
    ("切片两件套同步AT-57/76", "SKILL.md", ["切片产出两件套", "AT-57", "AT-76"], []),
    ("男频边界同步SKILL",      "SKILL.md", ["男频向题材仅经平台征文通道启用"], []),
    # --- 设计性双份漂移锁定 ---
    # 两处双份逐条同文但排版形态不同（prompts 代码块版 vs session-split 加粗列表版），
    # CROSS_SAME 块级归一化不适配单行双份——改文件级逐条锁：path 传两文件，
    # 每个文件都必须含该条内容子串（子串取无 ** 纯文字，排版差异不入锁），任一份单改/漏改/删除即被抓。
    # 双份：新会话重进五步（assets/prompts.md 四·长稿断点提示词 ↔ references/shared/session-split.md 三）
    ("重进五步-断点定位双份", ["assets/prompts.md", "references/shared/session-split.md"],
                              ["产物链缺号即断点在缺号处"], []),
    ("重进五步-禁全量加载双份", ["assets/prompts.md", "references/shared/session-split.md"],
                              ["禁全量加载 references"], []),
    ("重进五步-不读历史产物双份", ["assets/prompts.md", "references/shared/session-split.md"],
                              ["（不读全部历史产物，不依赖对话记忆）"], []),
    ("重进五步-产物链完整双份", ["assets/prompts.md", "references/shared/session-split.md"],
                              ["00-08 无跳号、与六表台账一致"], []),
    ("重进五步-禁跳阶段硬续双份", ["assets/prompts.md", "references/shared/session-split.md"],
                              ["禁跳阶段硬续"], []),
    # --- 过稿/爆款优化落点锁定 ---
    # 付费墙分隔符：stage7 workflow 投稿包正文项 + templates/06 投稿包模板各锁一份（口径锚定 AT-04 首锁字位）
    ("付费墙分隔符-stage7",  "references/stage7-delivery/workflow.md", ["——以下为付费章节——", "[[首锁]]"], []),
    ("付费墙分隔符-templates", "templates/06-submission.md", ["以下为付费章节"], []),
    # docx 命名约定：stage7 workflow 投稿包正文项锁「标题_字数」形态
    ("投稿docx命名",         "references/stage7-delivery/workflow.md", ["重生后我撕了婚书_12800字"], []),
    # 节→章合并投稿口径：stage7 workflow 锁「节→章合并」+「章题带情绪动词」
    ("节章对齐投稿口径",     "references/stage7-delivery/workflow.md", ["章节一一对应", "章题带情绪动词"], [r"短章快节奏制"]),
    # 绿通观察点：投稿后跟进内容不属本技能范围，不设断言
    # 完读率代理三环：references/README 锁三环 + 500 字闭环口径；stage6 workflow 终审工序同步必查项
    ("完读率代理三环",       "references/README.md", ["完读率代理三环", "结尾前 500 字禁总结词收束"], []),
    ("完读率三环同步stage6", "references/stage6-review/workflow.md", ["完读率代理三环必查", "结尾前 500 字禁总结词收束"], []),
    # 前三行复检卡位（AT-78）：口径锚定 AT 表（原 exec-card 卡位正文随卡二分拆，执行层速查见 scripts/README.md）
    ("前三行复检卡位",       "references/shared/authority-table.md", ["开头第一行 = 具体动作", "禁身份陈述开场"], []),
    # --- 普查补充口径 ---
    # 「分节数<3」升级为硬门：脚本 hard.append 侧 + mss-rules 硬门表侧 + stage6 展开清单侧三处同锁
    ("分节数硬门-脚本",      "scripts/check-mss.py", ["分节数 {seq_len} <3（需 ≥3 章）", "seq_len = 0"], []),
    ("分节数硬门-规则表",    "references/shared/mss-rules.md", ["分节数 <3"], []),
    ("分节数硬门-stage6",    "references/stage6-review/quality-gate.md", ["编号异常或分节数<3"], []),
    # 失效行号锚改段落名锚：kill-ai 禁止再出现「check-metrics.py 第 N 行」式硬行号
    ("无硬行号锚-killai",    "references/shared/kill-ai.md", ["12 尺子 0 速查"], [r"check-metrics\.py\s*第\s*\d+\s*行"]),
    # 节数只认从 1 起连续递增序列：孤立数字行（年份/金额）不得计入节数，防绕过「<3 节」硬门
    ("节数只认连续序列",      "scripts/check-mss.py", ["seq_len = 0", "if n == expect"], []),
    # 终审「平台口径核验/相似度检测」两项条件项已删——原 5 条条件项口径断言
    # 换为通用待核纪律 + 删项禁回流（禁两项改头换面回终审工序）
    ("待核项禁假合格-stage6",  "references/stage6-review/rules.md",
                              ["待核项禁假合格", "⚠️ + 原因"], []),
    ("删项禁回流-终审工序",    "references/stage6-review/workflow.md",
                              ["工序沿革", "七道"],
                              [r"^\s*7\. \*\*平台口径核验", r"^\s*8\. \*\*相似度检测"]),
    # --- 18 维终审评分表与 76 项拒稿门勾选表（stage6-review/quality-gate.md 第二/三节为唯一载体；他处只引不复制） ---
    ("18维评分表-stage6",      "references/stage6-review/quality-gate.md",
                              ["18 维终审评分表", "六维审评分", "MSS 五模块折算", "完读率代理三环", "盲测外部对标"], []),
    ("18维门值同步stage6",      "references/stage6-review/quality-gate.md",
                              ["≥8.00", "无单项 <6", "未隔离"], []),
    ("75项勾选表-stage6",      "references/stage6-review/quality-gate.md",
                              ["75 项拒稿门勾选表", "P0 格式 12 项", "P1 内容 47 项", "P2 商业 16 项"],
                              [r"P1 内容 4[0-6] 项", r"P2 商业 18 项"]),
    ("随报告附两表-SKILL",      "SKILL.md",
                              ["18 维评分表与 75 项勾选表", "stage6-review/quality-gate.md` 第二/三节"], []),
    ("随报告附两表-初审模板",   "templates/05-first-review.md",
                              ["18 维评分表与 75 项勾选表", "stage6-review/quality-gate.md` 第二/三节"], []),
    ("75项指针-referencesREADME", "references/README.md",
                              ["stage6-review/quality-gate.md` 第三节"], [r"77 项拒稿门"]),
    # 修：曾把 P1 加到 47 项后，「12/46/18=76」这句**汇总文字**漏改（表格表头已是
    # 47），AT-54 也已是 77——三处口径打架。上面的断言只锁表头字符串，抓不到正文里的算式。
    # 故对两处汇总句各锁「含 47/77」且「禁残留 46/76」。
    ("拒稿门项数汇总-stage6", "references/stage6-review/quality-gate.md",
                              ["12/47/16=75"], [r"12/4[67]/18\s*=\s*7[67]", r"12/46/18\s*=\s*76"]),
    ("拒稿门项数汇总-referencesREADME", "references/README.md",
                              ["P1 内容 47 / P2 商业 16 = 75"], [r"P1 内容 46", r"18 = 77"]),
    # 18 维硬门稿算术漏洞封堵。联动纪律单独拦不住硬门稿——12 硬门全触发时
    # 第 7-11 维全压 5、其余 13 维满分，理论均分 155/18 = 8.61 > 8.00，硬门稿仍能合法过门。
    # 故「禁入 18 维评分」必须落字；防回归成"只有 ≤5 联动"的老口径（黑名单锁"仅…联动"表述）。
    ("18维硬门稿禁入-stage6", "references/stage6-review/quality-gate.md",
                              ["禁入 18 维评分", "8.61"], [r"仅.{0,6}联动"]),
    # 6a 与 18 维的换算关系言明：第 1-6 维直取 6a 分，6a 压线 7.0 时后 12 维须均分 8.5
    ("6a与18维换算-stage6",   "references/stage6-review/quality-gate.md",
                              ["6a 与 18 维的换算关系", "8.5"], []),
    # 盲测四维无对照源处置：不计分 + 均分按计分维折算 + 禁出可用档（条件项禁假合格同款）
    ("盲测无对照源处置-stage6", "references/stage6-review/quality-gate.md",
                              ["不计分", "需补信息（盲测对照源）"], []),
    # 送机检正文禁直引 03：stage6 workflow 2.1 调用口径改净稿派生
    ("送检正文禁直引03-stage6", "references/stage6-review/workflow.md",
                              ["禁直引", "03-正文.md"], []),
    # stage7 修复组：
    # ① 机检提交包指针——「附节」是全库孤词（06-submission.md 无此节），正本在
    #    machine-check-package.md；黑名单锁"附节"防回退
    ("机检提交包指针-stage7", "references/stage7-delivery/workflow.md",
                              ["templates/machine-check-package.md", "机检提交/"], ["附节"]),
    # ② R 编号断裂修复：R11/R12 在位、R13/R14 禁残留（断裂时编号不可按号引用）
    ("stage7规则编号连续",    "references/stage7-delivery/rules.md",
                              ["工序只许 A/B 两号", "投稿呈现层适配"], [r"\| R13 \|", r"\| R14 \|"]),
    # ③ 07 模板自降矛盾修复：复盘是门不是建议，禁回退"非质量门"表述
    ("07复盘是门-stage7",    "templates/07-review.md",
                              ["复盘门四道之一"], ["非质量门"]),
    # ④ check-fingerprint 阶段 7 落点：shared/fingerprint.md 与 08 模板都说"阶段 7/复盘"
    #    调用，执行层三文件须接住（此前零落点 = 实落回填后不跑比对，指纹登记不闭环）
    ("指纹机检-stage7workflow", "references/stage7-delivery/workflow.md",
                              ["check-fingerprint.py", "回填实落后跑"], []),
    ("指纹机检-stage7gate",  "references/stage7-delivery/quality-gate.md",
                              ["check-fingerprint.py", "实落回填后跑"], []),
    ("指纹机检-stage7selfcheck", "references/stage7-delivery/self-check.md",
                              ["check-fingerprint.py", "回填后跑"], []),
    # ⑤ M 项：送机检提交包四件此前零机检（stage7 门10 纯人工）
    ("机检四件M项-stage7",   "references/stage7-delivery/quality-gate.md",
                              ["送机检提交包四件齐", "check-artifacts"], []),
    # R 项（投稿七字段阈值）须在 stage7 质量门有落点，否则脚本查了文档不认
    ("R项七字段-stage7gate", "references/stage7-delivery/quality-gate.md",
                              ["check-artifacts.py` R 项", "R 项"], []),
    ("R项七字段-脚本",       "scripts/check-artifacts.py",
                              # 锚实现判罚串（R 项标题在 docstring/注释/print 三处同名）
                              ["R 跳过: 未找到 06-投稿包/后台投稿信息.md",
                               "作品标签", "不在 100-150 带内",
                               # 全量七字段 + 短标题的判罚串
                               "七字段缺项即交付不完", "AT-25 可选字段——缺项不判红",
                               "疑似整段误粘"], []),
    ("机检四件M项-脚本",     "scripts/check-artifacts.py",
                              # 锚实现判罚串而非标题——「M 送机检提交包四件」在 docstring
                              # 与注释里也各有一份，只删 print 处仍命中（J 项同款教训）
                              ["M 跳过: 未找到 机检提交/ 目录", "缺 `[[首锁]]` 标记"], []),
    # ⑥ 双锁标记与 --paywall 锚句互校：旧实现静默取标记，两口径漂移不报警
    ("双锁锚句互校-mss",     "scripts/check-mss.py",
                              ["卡点双口径互校", "容差 50"], []),
    # ⑦ 阶段 7 模板索引补三件（06-submission 之外的 machine-check/07/08）
    ("阶段7模板索引-SKILL",   "SKILL.md",
                              ["machine-check-package.md", "templates/07-review.md", "templates/08-fingerprint.md"], []),
    ("阶段7模板索引-refsREADME", "references/README.md",
                              ["machine-check-package.md", "templates/07-review.md", "templates/08-fingerprint.md"], []),
    # ⑧ 切片口径边界：rules 复盘绑定段末句与 SKILL.md 收尾复盘段末句双份同文
    #    （单改一处即漂移——明确"整篇级交付物不标适用范围：片段"的边界）
    # --- 跨文件裂缝修复锁定（改一门必同步他门，双份/指针任一处漂移即被抓） ---
    ("stage2质量门九条",        "references/stage2-synopsis/quality-gate.md",
                              ["单线推进声明", "反转分级", "情绪任务清单三项量化", "暂定标题合规 + 兑现预演"], []),
    ("尾声专项门-stage4",      "references/stage4-draft/quality-gate.md",
                              ["尾声专项门", "最后 300 字落具体意象", "禁总结词收束"], []),
    # check-artifacts J 项（导语/尾声结构核验）须在 stage4 侧有对应口径，
    # 否则脚本查了但文档不认，执行者会当它是噪音。三要素不可机检这点必须写清——
    # 防 J 项绿灯被误读成导语专项门已过。
    ("导语尾声机检-J项同步stage4", "references/stage4-draft/quality-gate.md",
                              ["J导语/尾声结构核验"], []),
    ("导语尾声机检-脚本口径", "scripts/check-artifacts.py",
                              #锚**实现代码**而非标题串：「J 导语/尾声结构核验」在 docstring 与
                              # 注释里也各有一份，只删 print 那处仍会命中（实测恒过=假绿）。
                              # 故锁判罚语句本身——删了判罚即等于 J 项静默失效。
                              ["J 跳过: 未找到 03-正文.md",
                               "不在 AT-06 的 80-150 带内", "不在 AT-07 的 50-500 带内",
                               "三要素仍走 stage4 人工复检"], []),
    ("批写桥接-stage4",        "references/stage4-draft/rules.md",
                              ["每批 2-3 章", "批写是会话层拆法，不替代逐章纪律"], []),
    ("卡点落位算法-SKILL",      "SKILL.md",
                              ["卡点跟字位走，不跟章号走"], []),
    ("靶点句送检口径-stage5",   "references/stage5-polish/rules.md",
                              ["所在章**整章过**", "无单句送检模式"], []),
    # K/L 项机检面须在 stage5 质量门有对应口径——脚本查了文档不认 = 执行者当噪音
    # （D 项数字守恒的旧口径只管数字集合，"逐字一致"实为纯人工，三轮评估连续点名）
    ("双版本对账K项-stage5",   "references/stage5-polish/quality-gate.md",
                              ["check-artifacts.py` K 项", "剥全部【…】标注后与净稿逐字相等"], []),
    ("净稿三扫L项-stage5",     "references/stage5-polish/quality-gate.md",
                              ["check-artifacts.py` L 项", "人工复扫补机检盲区"], []),
    # kill-ai 验收核心（Step 4 三把尺子）接入 stage5——此前只引前四层，洗没洗干净无尺子量
    ("kill-ai收口尺子-stage5", "references/stage5-polish/workflow.md",
                              ["Step 4", "五维评分 ≥35/50", "六合一合格线", "AI 检测 12 项"], []),
    # 润色删词必然缩水：<13000 预警 + 删除预算核对（kill-ai Step 4 尺子 0 等级对应上限）
    ("润色缩水预警-stage5",   "references/stage5-polish/quality-gate.md",
                              ["<13000 触发缩水预警", "删除预算"], []),
    # 阶段 3 六表机检补全（N/O/P/Q）——脚本查了文档不认 = 执行者当噪音
    # （J 项同款教训；且此前两轮把"四表无对账"列为遗留，本轮闭环）
    ("六表机检NQ-stage3gate", "references/stage3-outline/quality-gate.md",
                              ["N 金句逐字兑现", "O 意象闭环", "P 时间线", "Q 名场面"], []),
    ("六表机检NQ-stage3selfcheck", "references/stage3-outline/self-check.md",
                              ["N（金句逐字兑现）", "O（意象闭环结构）",
                               "P（时间线钉死与道具落点）", "Q（名场面落点与章序）"], []),
    ("六表机检NQ-脚本", "scripts/check-artifacts.py",
                              # 锚实现判罚串而非标题——N/O/P/Q 在 docstring 与注释里
                              # 也各有一份，只删 print 处仍命中（恒过=假绿）
                              ["N 跳过: 未识别到金句预埋清单", "O 跳过: 未识别到意象系统清单",
                               "P 跳过: 未识别到时间线台账", "Q 跳过: 未识别到名场面预埋表",
                               "关键道具未进正文", "正文零落点"], []),
    # 送机检正文派生净稿：禁直引 03-正文.md（stage5 R11 唯一正文来源）
    ("送机检正文派生净稿",     "templates/machine-check-package.md",
                              ["04-正文净稿.md", "禁直引", "03-正文.md"], []),
    ("复合式标注-SKILL",        "SKILL.md",
                              ["【爽点+打脸】", "【伏笔·埋·Vx·描述】"], []),
    ("复盘三问统一-复盘模板",   "templates/07-review.md",
                              ["最接近被拒的三个点", "规则库里哪条救了/漏了它", "要改技能文件的具体项"], []),
    ("工具表含check-process-SKILL", "SKILL.md",
                              ["check-process.py"], []),
    ("工具表含check-process-scriptsREADME", "scripts/README.md",
                              ["check-process.py"], []),
    ("run-tests清tmp夹具",      "tests/run-tests.py",
                              ["shutil.rmtree"], []),
    # --- 轻量规则项（竞品密度双口径/九维折算/加厚回排） ---
    ("竞品密度双口径-stage1",   "references/stage1-topic/workflow.md",
                              ["竞品密度双口径", "禁编造数值阈值"], []),
    ("九维折算表-stage1",       "references/stage1-topic/workflow.md",
                              ["S/A/B/C 折算表", "S | 10"], []),
    ("加厚回排纪律-stage3",     "references/stage3-outline/workflow.md",
                              ["加厚回排纪律", "保后段章 1800 底线优先"], []),
    # --- 全库禁项 ---
    ("无盐言双口径残留",        None, [], [r"盐言 55-65%"]),
    # --- 结构重整锁：终审并入阶段 6（stage7 只留投稿打包 + 复盘登记）；长文续写路径已删除 ---
    # stage7 工序只许 A/B 两号，终审内容（跨章扫描/跳读/红队）禁回流 stage7
    ("stage7工序AB编号",       "references/stage7-delivery/workflow.md",
                              ["工序 A · 投稿打包", "工序 B · 复盘登记"],
                              ["工序 C", "工序 A · 终审", "跨章扫描", "跳读测试", "红队终审"]),
    # 终审七工序唯一真源 = stage6 workflow 第五节；任一工序名漂移即断链（删两项后重排）
    ("终审七工序-stage6",      "references/stage6-review/workflow.md",
                              ["跨章扫描", "跳读测试", "付费测试", "盲测对比（强制）", "18 维终审评分",
                               "红队终审", "工序留痕核"], [r"平台口径核验（条件项）\*\*", r"相似度检测（条件项）\*\*"]),
    # 终审工序执行记录：终审七工序留痕载体（check-process 核验对象）——三端同锁缺一即断
    ("终审工序执行记录三端",    ["SKILL.md", "references/stage6-review/workflow.md", "templates/05-final-review.md"],
                              ["终审工序执行记录"], []),
    # check-process 三个解析锚点（工序表头/裁决表头含「门槛」/终审结论句/机检节名）的唯一
    # 文档背书 = templates/05-review-report.md 审稿报告模板——禁只活在脚本与回归夹具里（模板脱节=误报/跳过）
    # 双报告制：锚点①机检节名落在初审模板，锚点②③④（工序表/裁决表四列/
    # 结论句 N 项）落在终审模板——两模板合计覆盖 check-process 全部解析锚点
    ("checkprocess锚点-初审模板", "templates/05-first-review.md",
                              ["节名含「机检」"], []),
    ("checkprocess锚点-终审模板", "templates/05-final-review.md",
                              ["工序号", "终审裁决表", "N 项门槛全过"], []),
    # 条件项标准指针短语统一为「阶段 6 终审第 7/8 条」——旧指针「stage7 工序 A」禁回流
    # 旧指针「阶段 6 终审第 7/8 条」随删项禁回流（stage7 投稿面条件项改自有口径）
    # 补 genre-map.md——首轮列 11 个文件时漏了它，genre-map:329 的旧指针
    # （「按阶段 6 终审第 8 条」）静默活过一轮，本轮自查抓出。教训：**禁回流断言的文件
    # 清单要全库 rglob 推导，不能手数**——手数必漏。扫全库 md（CHANGELOG 按史实记录除外，
    # exemplars 是故意坏样例除外）；**不扫本脚本自身**——禁项正则的文本就在本文件里，
    # 扫自身=禁项词汇总自咬（与「长文续写禁回流」None 组同款自处理）。
    ("旧终审7-8指针禁回流",    [str(f.relative_to(ROOT)) for f in
                              sorted(ROOT.rglob("*.md")) if f.name != "CHANGELOG.md"
                              and ".bak" not in str(f) and "exemplars" not in str(f)],
                              [], [r"阶段 6 终审第 7", r"阶段 6 终审第 8", r"stage7 工序 A"]),
    # check-process 时序归位阶段 6 终审（打包前硬前置），禁留「阶段 7 交付前」
    ("checkprocess归位阶段6",   ["SKILL.md", "scripts/README.md"],
                              ["阶段 6 终审"], []),
    ("stage6标题含初审终审",    ["SKILL.md", "references/stage6-review/quality-gate.md",
                              "references/stage6-review/workflow.md", "references/stage6-review/rules.md",
                              "references/stage6-review/self-check.md", "AGENTS.md", "assets/prompts.md",
                              "docs/install.md", "assets/glossary.md", "references/shared/session-split.md"],
                              ["初审与终审"], [r"审稿与终审"]),
    # 长文续写路径已删除（本技能只写短篇）——01bis 前文拆解/逆向拆解/续写对账全链禁回流
    ("长文续写禁回流",          None, [], [r"01bis", r"前文拆解", r"逆向拆解", r"长文续写", r"续写对账"]),
    ("artifacts禁续写对账回流", "scripts/check-artifacts.py", [], [r"01bis", r"前文拆解", r"续写对账"]),
    ("run-tests禁续写对账回流", "tests/run-tests.py", [], [r"续写对账"]),
]

# 跨文件同文断言（第三层：治"同一段落在两文件各存一份、改一处忘另一处"的漂移——
# 设计性双份<入口层速查/质量门镜像>当前同文，锁死后任一份单改即被抓；
# 归一化只比文字（去 MD 强调/引用/空白/引号），不比排版）
# (说明, 文件A, 文件B, 锚点子串)：各取含锚点的正文块，归一化后必须同文
CROSS_SAME = [
    # 审稿隔离最高优先级纪律：SKILL 入口与 stage6 quality-gate 各存一份（入口层保留可见性）
    ("冷启动纪律双份同文", "SKILL.md", "references/stage6-review/quality-gate.md", "冷启动纪律（优先级最高）"),
    # 退出口径语义：scripts/README 速查与 references/README 门禁索引各存一份（执行面/规则面镜像）
    ("退出码语义双份同文", "scripts/README.md", "references/README.md", "退出码语义（AT-56）"),
    # 复盘绑定两条：SKILL.md 收尾复盘独立段 ↔ stage7-delivery/rules.md 复盘绑定段（块级同文，单改一处即漂移）
    ("复盘-持久记忆绑定双份同文", "SKILL.md", "references/stage7-delivery/rules.md", "复盘完成后把未闭环问题摘要与结构指纹写入持久记忆"),
    ("复盘-固化触发线双份同文", "SKILL.md", "references/stage7-delivery/rules.md", "同一类问题连续 3 篇出现 → 必须改技能文件，禁止每篇人肉兜底"),
    # 切片口径边界："整篇级交付物不标适用范围：片段"末句双份同文
    ("切片口径边界双份同文", "SKILL.md", "references/stage7-delivery/rules.md", "切片口径边界"),
]

# AT 行级断言（治"文件级串在、行级值被改"的漏网：同一字符串在别的行也有出现时，
# 只改 AT-04 行的值文件级断言看不见——口径改在行里也必须被抓）
# (说明, AT编号, 必须存在, 不得存在)；行文本 = authority-table.md 中 "| AT-xx |" 开头的那一行
AT_ROWS = [
    ("AT-04付费墙字位行",      "AT-04", ["3000-4000"], []),
    ("AT-24标题三档行",        "AT-24", ["16-20 字合格"], [r"≤15 字不剧透"]),
    ("AT-26盐选单口径行",      "AT-26", ["盐选唯一口径"], [r"盐言 55-65%"]),
    ("AT-31双打分≥25行",       "AT-31", ["≥25"], []),
    ("AT-32九维均分≥8行",      "AT-32", ["≥8"], []),
    ("AT-22伏笔回收率行",      "AT-22", ["≥80%"], []),
    ("AT-63段落合规率行",      "AT-63", ["≤50 字段落 ÷ 总段落 ≥60%"], []),
    ("AT-05卡点双口径行",      "AT-05", ["25-35%"], []),
    # 优化口径行级锁（防"串在别处、行值被改"式漏网）
    ("AT-69名场面预埋行",      "AT-69", ["≥1 个"], []),
    ("AT-70卡点三型行",        "AT-70", ["撕裂", "抉择"], []),
    ("AT-73主疼位指认行",      "AT-73", ["被辜负", "被误解", "求而不得", "身份落差", "丧失"], []),
    ("AT-75征文信号行",        "AT-75", ["8000-29999"], []),
    # 切片两件套格式门（AT-76）
    ("AT-76切片口径备注行",    "AT-76", ["口径备注", "退出码"], []),
    # 结构指纹同型判定行级锁：错位标签
    # 「AT48指纹维度」「AT49同型阈值」文件级松锁（子串各自在某处出现即过）——权威包无此条目，
    # 按正确编号补行级锁：AT-47=结构指纹维度数、AT-48=同型判定阈值（AT-49=选题候选，无需锁）
    ("AT-47指纹维度数行",      "AT-47", ["6 维"], []),
    ("AT-48同型阈值行",        "AT-48", ["≥2 维"], []),
    # 篇幅/章数与完读率口径行级锁
    # （AT_ROWS 只扫「值」列 cols[3]，子串须取值列内容；落备注列的口径另走文件级锁）
    ("AT-77完读率代理三环行",  "AT-77", ["结尾前 500 字禁总结词收束"], []),
    ("AT-78前三行复检行",      "AT-78", ["禁形容词起句", "禁身份陈述开场"], []),
    # 开篇两章加权与免费区钩子加密（AT-79/80）行级锁——值列漂移即回到"全篇均分"或"免费区平铺"
    ("AT-79开篇两章加权行",    "AT-79", ["第 1 章 2200-2800 字；第 2 章 2000-2800 字"], [r"1800-2800 字；第 2 章"]),
    ("AT-80免费区钩子加密行",  "AT-80", ["每 500 字 ≥1 个信息型钩子", "卡点前 1000 字 ≥3 个"], []),
    # 相似度双线（AT-23）：值列口径锁——判罚列已改「红线接线（条件项）」，值列双线禁删
    ("AT-23相似度双线行",      "AT-23", ["机器相似度 <15% 合格"], []),
]


def at_row_text(text, at_id):
    """取 authority-table.md 中指定 AT 编号的表格行（行级口径断言用）"""
    for ln in text.splitlines():
        if ln.strip().startswith(f"| {at_id} |"):
            return ln
    return ""

def block_with(text, anchor):
    """取含锚点的正文块（空行分段）；无则返回 None"""
    for blk in re.split(r"\n\s*\n", text):
        if anchor in blk:
            return blk.strip()
    return None

def md_library():
    """全库 md 扫描面（七类目录）：
    SKILL.md + references 递归（README + shared 8 + stageN 四文件树）
    + templates/*.md + assets 规范文件（glossary/source-whitelist/compliance-redlines/prompts/README）
    + assets/genre-cards/*.md。
    **assets/exemplars/ 禁入扫描**（bad/ 是故意的坏样例——禁项词在里面是设计而非回流）；
    examples/full-run/ 是演示产物，同禁入；
    tests/ 是回归夹具（bad 夹具故意含缺陷），同禁入。"""
    files = [ROOT / "SKILL.md"] + sorted((ROOT / "references").rglob("*.md"))
    files += sorted((ROOT / "templates").glob("*.md"))
    for name in ("glossary.md", "source-whitelist.md", "compliance-redlines.md", "prompts.md", "README.md"):
        files.append(ROOT / "assets" / name)
    files += sorted((ROOT / "assets" / "genre-cards").glob("*.md"))
    return files

def norm_block(s):
    """归一化正文块：去 Markdown 强调/引用/空白/引号——只比文字，不比排版"""
    s = re.sub(r"[*`>#\s]", "", s)
    return s.replace('"', "").replace("\u201c", "").replace("\u201d", "")


# 产物链命名（00-选题评估 / 03-正文 / 08-结构指纹 …）：落盘在「项目-{书名}/」而非技能文件夹，
# 故文档内引用它不算死链；模板命名（templates/06-submission.md）是英文后缀，不在此列。
PRODUCT_RE = re.compile(r"^0[0-8]-[\u4e00-\u9fff]")
# 机检提交包固定产物名（templates/machine-check-package.md 四件中的 md 三件）——
# 与产物链同理：是项目目录下的固定命名而非技能内文件，禁按死链扫。
# 实证教训：stage6 workflow 命令示例写「机检提交/正文纯文本.md」被误报死链，
# 该路径在项目目录语境成立（机器扫的是技能根/references 根语境）。
MC_PACKAGE_RE = re.compile(r"^(?:正文纯文本|标题导语梗概|金句列表)\.md$")


def link_library():
    """死链扫描面：全库 md——比 md_library()（口径扫描面）更广。
    死链可出现在任何文档里（历史存量就集中在 assets/genre-cards/README.md、
    assets/exemplars/README.md、examples/full-run/ 等口径面之外的文件），故全扫。
    仅排除 docs/CHANGELOG.md：它按史实记录旧路径，属实记录而非死链。"""
    return [f for f in sorted(ROOT.rglob("*.md")) if f.name != "CHANGELOG.md"]


def check_links():
    """死链检查：文档内反引号包裹的 .md/.py 相对路径必须能解析到真实文件。
    ——改路径最容易犯的错是「层级少写一级」（../ 写成 ../../ 或反之），
      跑起来才发现在加载空气，故固化为门禁。

    判定规则（兼容库内既有的三种路径约定，避免误报）：
      · `../` 或 `./` 开头 = 作者明确表达了「相对本文件」意图 → 只按所在目录解析，失败即报；
      · 其他写法 = 可能是「技能根相对」(`scripts/x.py`) 或「references 根相对」
        (`stage6-review/x.md`) 的既有约定 → 多重基线择一命中即通过。
    不计入 209 组口径断言（那三组锚定的是口径文字，本段锚定的是指向关系）。"""
    bad, checked = [], 0
    for f in link_library():
        text = f.read_text(encoding="utf-8-sig", errors="ignore")
        for m in re.finditer(r"`([A-Za-z0-9_\u4e00-\u9fff.][A-Za-z0-9_\u4e00-\u9fff./-]*\.(?:md|py))`", text):
            p = m.group(1)
            if p.startswith("http") or "/" not in p:      # 外链 / 纯文件名简写（非路径引用）
                continue
            if PRODUCT_RE.match(p.split("/")[-1]) or MC_PACKAGE_RE.match(p.split("/")[-1]):
                continue                     # 产物链命名 / 机检提交包固定产物名
            checked += 1
            bases = [f.parent] if p.startswith(("../", "./")) \
                else [ROOT, ROOT / "references", f.parent, f.parent.parent]
            if not any((b / p).resolve().exists() for b in bases):
                bad.append(f"❌ [死链] {f.relative_to(ROOT)} 引用 `{p}` —— 解析不到文件"
                           f"（层级写错？应指向 {p.split('/')[-1]}）")
    return list(dict.fromkeys(bad)), checked

def main():
    # 显式帮助入口：-h/--help 打 docstring 退 0（本脚本无参即全量自检，无"用法错误"态）
    if any(a in ("-h", "--help") for a in sys.argv[1:]):
        print(__doc__ or "用法: 见脚本头部 docstring")
        sys.exit(0)
    fails = []
    # 工具与回归样例存在性 + 脚本可用性探针（py_compile 探测脚本损坏，防"门塌了到用时才发现"；
    # cfile 投临时目录——默认写法会把 __pycache__/*.pyc 落进包体，污染交付目录（实测 95→103 文件）
    import py_compile, tempfile
    with tempfile.TemporaryDirectory() as _td:
        for tool in ("check-length.py", "check-metrics.py", "check-ai.py", "check-consistency.py",
                     "check-artifacts.py", "check-all.py", "check-fingerprint.py", "check-mss.py",
                     "check-process.py"):
            p = ROOT / "scripts" / tool
            if not p.exists():
                fails.append(f"❌ [工具在位] scripts/{tool} 不存在")
                continue
            try:
                py_compile.compile(str(p), cfile=os.path.join(_td, "probe.pyc"), doraise=True)
            except py_compile.PyCompileError as e:
                fails.append(f"❌ [脚本可用性探针] scripts/{tool} 不可编译: {e}")
    for case in ("tests/good-sample.md", "tests/bad-sample.md", "tests/run-tests.py",
                 "tests/golden/g10-第一人称开篇.md",
                 "tests/fixtures/mini-good/02-细纲.md", "tests/fixtures/mini-bad/02-细纲.md",
                 "tests/fixtures/mini-good/03-正文.md", "tests/fixtures/mini-annot/04-润色标注稿.md",
                 "tests/fixtures/mss-good/03-正文.md", "tests/fixtures/mss-bad/03-正文.md"):
        if not (ROOT / case).exists():
            fails.append(f"❌ [回归样例在位] {case} 不存在")
    # 确认门标记计数（darwin dim4 优化）：四道确认门须在**总览表与执行卡两处**各带
    # 🔴（≥8 处），且四道门各出现 ≥2 次——只靠措辞「用户确认才前进」不算数，LLM 解析时
    # 扫描视觉标记。实证教训：2026-10-17 加的 9 处标记在后续多轮迭代中被覆盖丢失，
    # 期间无任何断言报警——本条是那次的根因修复。
    skill_text = (ROOT / "SKILL.md").read_text(encoding="utf-8-sig") if (ROOT / "SKILL.md").exists() else ""
    n_gate = skill_text.count("🔴 确认门")
    if n_gate < 8:
        fails.append(f"❌ [确认门标记计数] SKILL.md 的「🔴 确认门」仅 {n_gate} 处（应 ≥8："
                     f"总览表 4 + 执行卡 4）——确认门失去视觉标记即退化为措辞，执行者无从判断该停")
    for g in "①②③④":
        n_g = skill_text.count(f"🔴 确认门{g}")
        if n_g < 2:
            fails.append(f"❌ [确认门{g}标记] 仅 {n_g} 处（应 ≥2：总览表 + 执行卡各一处）")
    # 范文库双轨同步：assets/exemplars 是资产视图复制、tests/golden+根 tests/
    # 是回归正本（D3 决策，见 assets/exemplars/README.md「双轨纪律」）。README 承诺
    # 「check-consistency.py 有同文断言盯着，单边漂移即报错」——此前**无实现**，
    # 7 个文件任一边单边修改会静默漂移（虚假承诺）。现补文件级归一化全同文断言。
    EXEMPLAR_PAIRS = [
        ("assets/exemplars/good/good-sample.md", "tests/good-sample.md"),
        ("assets/exemplars/bad/bad-sample.md", "tests/bad-sample.md"),
        ("assets/exemplars/good/g10-第一人称开篇.md", "tests/golden/g10-第一人称开篇.md"),
        ("assets/exemplars/good/g12-环境叙事.md", "tests/golden/g12-环境叙事.md"),
        ("assets/exemplars/good/g14-短段改造.md", "tests/golden/g14-短段改造.md"),
        ("assets/exemplars/good/g15-古言对峙.md", "tests/golden/g15-古言对峙.md"),
        ("assets/exemplars/good/g16-悬疑钩链.md", "tests/golden/g16-悬疑钩链.md"),
    ]
    for a, b in EXEMPLAR_PAIRS:
        pa, pb = ROOT / a, ROOT / b
        if not pa.exists() or not pb.exists():
            fails.append(f"❌ [范文库双轨缺边] {a} ↔ {b}（双轨两边的文件都须在位）")
        elif norm_block(pa.read_text(encoding="utf-8-sig")) != norm_block(pb.read_text(encoding="utf-8-sig")):
            fails.append(f"❌ [范文库双轨不同步] {a} ↔ {b}——单边修改即漂移（改内容必须两端同步，"
                         f"见 assets/exemplars/README.md 双轨纪律）")
    # 根目录入口文件 + docs 两文件存在性
    for extra in ("AGENTS.md", "SKILL.md", "docs/CHANGELOG.md", "docs/install.md"):
        if not (ROOT / extra).exists():
            fails.append(f"❌ [入口文件在位] {extra} 不存在")
    # references 新树在位：README + shared 8 文件 + 七阶段目录各四文件（workflow/quality-gate/self-check/rules）
    ref_files = ["README.md"] + [f"shared/{n}" for n in (
        "authority-table.md", "principles.md", "style-rules.md", "kill-ai.md",
        "mss-rules.md", "genre-map.md", "fingerprint.md", "session-split.md")]
    for d in ("stage1-topic", "stage2-synopsis", "stage3-outline", "stage4-draft",
              "stage5-polish", "stage6-review", "stage7-delivery"):
        ref_files += [f"{d}/{n}" for n in ("workflow.md", "quality-gate.md", "self-check.md", "rules.md")]
    for ref in ref_files:
        p = ROOT / "references" / ref
        if not p.exists():
            fails.append(f"❌ [规则库新树在位] references/{ref} 不存在")
    # templates 12 个在位
    tpl_files = ("00-topic-evaluation.md", "01-synopsis.md", "02-outline.md", "03-manuscript.md",
                 "04-annotated.md", "04-clean.md", "05-first-review.md", "05-final-review.md",
                 "06-submission.md", "07-review.md", "08-fingerprint.md", "gate-record.md",
                 "machine-check-package.md")
    for tpl in tpl_files:
        if not (ROOT / "templates" / tpl).exists():
            fails.append(f"❌ [templates 在位] templates/{tpl} 不存在")
    # assets 规范文件 5 个在位
    for ast in ("glossary.md", "source-whitelist.md", "compliance-redlines.md", "prompts.md", "README.md"):
        if not (ROOT / "assets" / ast).exists():
            fails.append(f"❌ [assets 规范文件在位] assets/{ast} 不存在")
    # genre-cards 子目录在位（README + 32 张题材卡；已迁 assets/）
    gc_dir = ROOT / "assets" / "genre-cards"
    if not gc_dir.is_dir():
        fails.append("❌ [genre-cards在位] assets/genre-cards/ 目录不存在")
    else:
        if not (gc_dir / "README.md").exists():
            fails.append("❌ [genre-cards在位] assets/genre-cards/README.md 不存在")
        gc_files = sorted(p.name for p in gc_dir.glob("*.md"))
        if len(gc_files) != 33:  # README + 32 张题材卡
            fails.append(f"❌ [genre-cards在位] 题材卡 .md 数量漂移：应为 33（README+32 卡），实有 {len(gc_files)}")
    # 脚本数量自述校验：文档声称的「N 个校验脚本」必须等于 scripts/*.py 实有数
    # （纯文案断言只能抓两处文案互相不一致，抓不到「文案一致但都与事实不符」——故直接数文件）
    py_files = sorted(p.name for p in (ROOT / "scripts").glob("*.py"))
    n_py = len(py_files)
    for doc, pat in (("docs/CHANGELOG.md", r"`scripts/` —— (\d+) 个零依赖脚本"),
                     ("docs/install.md", r"配 \*\*(\d+) 个零依赖 Python 校验脚本\*\*"),
                     ("docs/install.md", r"`scripts/` (\d+) 个校验脚本"),
                     ("SKILL.md", r"(\d+) 个零依赖机检脚本")):
        dp = ROOT / doc
        text = dp.read_text(encoding="utf-8-sig") if dp.exists() else ""
        for m in re.finditer(pat, text):
            if int(m.group(1)) != n_py:
                fails.append(f"❌ [脚本数量自述] {doc} 声称 {m.group(1)} 个脚本，"
                             f"实有 {n_py} 个（{', '.join(py_files)}）")
    for desc, path, must, forbid in ASSERTS:
        if path is None:  # 全库扫描
            files = md_library()
        elif isinstance(path, (list, tuple)):  # 多文件同锁（双份漂移：每个文件都必须含）
            files = [ROOT / p for p in path]
        else:
            files = [ROOT / path]
        for f in files:
            text = f.read_text(encoding="utf-8-sig") if f.exists() else ""
            for pat in must:
                if pat not in text:
                    fails.append(f"❌ [{desc}] {f.name} 缺失: {pat}")
            for pat in forbid:
                if re.search(pat, text):
                    fails.append(f"❌ [{desc}] {f.name} 命中禁项: {pat}")
    # 跨文件同文断言（设计性双份段落：两处必须同文，单改一处即漂移被抓）
    for desc, fa, fb, anchor in CROSS_SAME:
        ta = (ROOT / fa).read_text(encoding="utf-8-sig") if (ROOT / fa).exists() else ""
        tb = (ROOT / fb).read_text(encoding="utf-8-sig") if (ROOT / fb).exists() else ""
        ba, bb = block_with(ta, anchor), block_with(tb, anchor)
        if ba is None or bb is None:
            miss = fa if ba is None else fb
            fails.append(f"❌ [{desc}] {miss} 缺失含锚点「{anchor}」的正文块")
            continue
        if norm_block(ba) != norm_block(bb):
            fails.append(f"❌ [{desc}] 双份不同文：{fa} ↔ {fb}（锚点「{anchor}」段已漂移——两处同文或改单一事实源）")
    # 元断言：AGENTS.md 自述锚点行 ↔ 「AGENTS审稿隔离」断言组双向绑定
    # （若须检串只存在于自述行里，掏空隔离内容层也不会被主断言发现——自述成了内容的
    #  替身。故查两件事：①自述须列全须检串；②至少一个须检串的出现次数多于自述行内
    #  的次数（证明内容层有实体）。）
    agents_text = (ROOT / "AGENTS.md").read_text(encoding="utf-8-sig") if (ROOT / "AGENTS.md").exists() else ""
    anchor_line = next((l for l in agents_text.split("\n") if "断言锚点" in l), "")
    meta = [m for d, p, m, fb in ASSERTS if d == "AGENTS审稿隔离" and p == "AGENTS.md"]
    if not meta:
        fails.append("❌ [AGENTS锚点元断言] ASSERTS 中找不到「AGENTS审稿隔离」组——元断言目标丢失")
    else:
        for s in meta[0]:
            if s not in anchor_line:
                fails.append(f"❌ [AGENTS锚点自述缺串] {s} 未列入 AGENTS.md 锚点行描述（自述与断言漂移）")
        if not [s for s in meta[0] if agents_text.count(s) > anchor_line.count(s)]:
            fails.append("❌ [AGENTS锚点自述成替身] 须检串全部只存在于锚点行自述——隔离内容层已被掏空（自述不许充当内容）")
    # AT 行级口径断言（口径列的值被改 = 被抓，禁"串还在别处/别列"式漏网）
    at_text = (ROOT / "references" / "shared" / "authority-table.md").read_text(encoding="utf-8-sig") \
        if (ROOT / "references" / "shared" / "authority-table.md").exists() else ""
    for desc, at_id, must, forbid in AT_ROWS:
        row = at_row_text(at_text, at_id)
        if not row:
            fails.append(f"❌ [{desc}] authority-table.md 未找到 {at_id} 行")
            continue
        cols = row.split("|")
        val_col = cols[3].strip() if len(cols) > 3 else row  # 口径列（| AT-xx | 名称 | 值 | 判罚 | 备注 |）
        for pat in must:
            if pat not in val_col:
                fails.append(f"❌ [{desc}] {at_id} 口径列缺失: {pat}（行级口径被改）")
        for pat in forbid:
            if re.search(pat, row):
                fails.append(f"❌ [{desc}] {at_id} 行命中禁项: {pat}")
    # 旧产物名全库禁残留（扫描面 = md_library；命名以现行产物链为准，
    # 防止 02-投前方案/05-正文净稿/09-结构指纹 等旧名回流导致断链）
    for f in md_library():
        text = f.read_text(encoding="utf-8-sig") if f.exists() else ""
        for pat in (r"02-投前方案\.md", r"05-正文净稿\.md", r"09-结构指纹\.md"):
            if re.search(pat, text):
                fails.append(f"❌ [旧产物名残留] {f.name} 命中禁项: {pat}")
    # 死链检查（引用须能解析到真实文件；与 209 组口径断言并列，独立计段）
    link_fails, links_checked = check_links()
    fails.extend(link_fails)
    # 去重（全库扫描会重复报）
    fails = list(dict.fromkeys(fails))
    if fails:
        print("\n".join(fails)); print(f"\n{len(fails)} 处失配"); return 1
    print(f"✅ 一致性自检全过：{len(ASSERTS)} 组文件级断言 + {len(CROSS_SAME)} 组跨文件同文断言"
          f" + {len(AT_ROWS)} 组 AT 行级断言 + 死链检查 {links_checked} 条引用全通"); return 0

sys.exit(main())
