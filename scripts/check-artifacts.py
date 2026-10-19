#!/usr/bin/env python3
"""check-artifacts.py — 产物链字段核验（阶段 4/6 对账用）

背景: 四个既有脚本只保护**技能本体**（check-consistency）与**单篇文本**（metrics/ai/length），
项目产物链（02-细纲/03-正文/04 双版本文件的字段完整性与对账）此前无机检面——三轮隔离评估
连续指出"章末钩无机检 / 人设动机无扫描 / 伏笔双标无对账 / 信息守恒无自动化"。

用法:
  python3 check-artifacts.py <项目目录>          # 自动发现七步法产物链（02-细纲/03-正文/04 双版本）
  python3 check-artifacts.py <文件1> [文件2 ...]  # 显式指定

检查项与判罚:
  A 章末钩字段   02-细纲.md 上篇节拍表"节末钩子"列每数据行非空且非模板占位 → 空缺 = ❌(exit 3)
  B 人设动机     02-细纲.md 下篇投前方案·人设卡含"动机"字段行非空（防工具人） → 空缺 = ❌(exit 3)
  C 伏笔双标对账 04 标注稿中【伏笔·埋】/【伏笔·收】计数 vs 02 伏笔规划表条目数 → 不等 = ⚠️(exit 2)
  D 数字守恒     03 正文 vs 04 净稿的阿拉伯数字集合差异（去AI味
                 不得丢数字——信息守恒的可计算子集）  → 差异 = ⚠️(exit 2)
  K 双版本对账   04 标注稿剥全部【…】标注+引用/标题行+空白 vs 04 净稿,
                 须完全相等（stage5 门4/R9"逐字一致"的唯一机检面）     → 不等 = ⚠️(exit 2)
  L 净稿三扫     04 净稿的编辑痕迹（修正:/批注/占位符/括号小标题）/
                 逐字重复句（≥10 字整句重复）/ 说明性尾注（stage5 门5/R10）→ 命中 = ⚠️(exit 2)
  E 防狗血关键词 正文命中欺骗引擎词（假装失忆/装病接近类）           → ⚠️ 人工复核(exit 2)
  F 标注覆盖     04 标注稿情绪标注数（六类情绪靶点）vs 02 细纲靶点表行数, 覆盖 <90%       → ⚠️(exit 2)
  N 金句兑现     02 细纲金句预埋清单每条原句须在 04 标注稿逐字出现（15-25 字带内自检）  → 未兑现 = ⚠️(exit 2)
  O 意象闭环     02 细纲意象清单核心信物恰 1 行 + 首现/末现非空 + 落点章号 ≤ 正文章数   → 不符 = ⚠️(exit 2)
  P 时间线台账   02 细纲时间线四行（纪年/年龄/季节/关键道具）钉死 + 关键道具正文有落点   → 缺 = ⚠️(exit 2)
  Q 名场面预埋   02 细纲名场面表 ≥1 行 + 五字段非空 + 章序不越界 + 一句话正文有落点      → 不符 = ⚠️(exit 2)
    （N-Q 四项 六张预埋表此前后两表有对账面、四表纯人工；缺表 = ℹ️ 跳过，
     有表而对不上才判——六表填满仍是阶段 3 人工门 2，机检做渐进补强）
  G 靶点密度与章末钩（钩子/靶点从人工数数升级为标注实测）
    G1 靶点密度  04 标注稿六类情绪靶点标注数/万字 <15（合格线; 虐文 ≥18） → ⚠️(exit 2)
    G2 章末钩    04 标注稿按章切分, 每章末 200 字内须有章末钩标注          → ⚠️(exit 2)
  J 导语/尾声结构核验
    03 正文的导语字数须落 AT-06 80-150、须有「尾声」标签行且落 AT-07 50-500 → ⚠️(exit 2)。
    ⚠️ 只核**结构与字数带**，三要素（AT-71）与禁总结词收束（AT-77）不可机检，仍走 stage4 人工复检。
  M 送机检提交包四件
    项目目录/机检提交/ 四件齐 + 正文纯文本带 [[首锁]] + 伏笔回收 CSV 五字段 → 缺 = ⚠️(exit 2)
    （stage7 门10 的机检面；目录不存在 = 跳过——未到送检时点不判失败）

退出码: 0 = 全过; 1 = 用法错误/无文件可查/输入文件不存在; 2 = 仅有 ⚠️ 级对账差异; 3 = 有 ❌ 级字段空缺。
文件缺失或表结构无法解析 = 跳过对应项并提示（不判失败, 但"文件在而表解析不到"
会报 ⚠️——多半是模板格式改了而本脚本没跟上, 须同步）；**全部链文件一个都没命中
= 退 1「无文件可查」**——给错路径/目录无产物链时禁报全过（假绿灯）。
纪律: 本脚本查字段与对账, 不判内容好坏（主观门仍走四档判定）; 解析降级时人工核验并
在审稿报告标注"⚠️ 产物机检降级"。
"""
import re
import sys
from pathlib import Path

# 防狗血: 骗负引擎类（genre-map 档案 9 负面清单的可计算子集——只抓明确句式, 宽松防误报）
DOG_BLOOD = ['假装失忆', '装失忆', '假失忆', '装病接近', '假装生病接近', '假装失忆了']
# 题材红线扫描（机检面——SKILL 阶段1 红线筛查/未成年恋判据 + genre-map 婚恋/校园
# 防狗血清单的可计算子集；只抓高风险**共现**句式, 命中仅提示人工复核, 防误伤正常剧情）
RED_LINE = [
    (re.compile(r'净身出户[^。！？\n]{0,20}(复合|原谅|跪|回头)'),
     '家暴/出轨洗白嫌疑（C2 红线·婚恋防狗血清单第 1 条「禁悔过洗白」）'),
    (re.compile(r'(绝症|临终|癌症晚期|病危)[^。！？\n]{0,30}(存折|遗书|遗言|遗产|存款)'),
     '亲情催泪嫌疑（C2 红线·禁存折式催泪）'),
    (re.compile(r'(存折|遗书|遗言)[^。！？\n]{0,30}(绝症|临终|癌症晚期|病危)'),
     '亲情催泪嫌疑（C2 红线·禁存折式催泪）'),
    (re.compile(r'(未成年|初中|高一|高二|高三)[^。！？\n]{0,20}(恋爱|初吻|同居|交往|在一起)'),
     '未成年恋嫌疑（C2 红线·恋爱线双方须 ≥18 岁）'),
    (re.compile(r'(自杀|自残|割腕|轻生|跳楼)[^。！？\n]{0,15}(解脱|勇敢|浪漫|值得|正确|最美|是种美|才是美)'),
     '自杀自残美化嫌疑（红线·禁把自伤写成解脱/勇敢/浪漫）'),
    (re.compile(r'(校园|同学|同桌|被)[^。！？\n]{0,12}(霸凌|欺凌|围殴|孤立)[^。！？\n]{0,10}(活该|咎由自取|大快人心|解气|报应)'),
     '校园霸凌美化嫌疑（红线·禁把霸凌写成爽/活该）'),
    (re.compile(r'(女人|男人|女的|男的)[^。！？\n]{0,12}(都是|就是|天生|没一个|都该)[^。！？\n]{0,8}(贱|蠢|坏|该死|不配)'),
     '性别对立嫌疑（红线·禁性别对立引战）'),
    (re.compile(r'(外地人|外省人|本地人|某地人)[^。！？\n]{0,10}(都|全是|没一个|就是)[^。！？\n]{0,8}(坏|骗|偷|穷|土)'),
     '地域歧视嫌疑（红线·禁地域歧视地图炮）'),
]
# 事实核验防线扫描（选题中的市场数据声称, 无来源标记即提示"待核"）
DATA_KW = ['数据', '热度', '增长', '排名', '阅读量', '播放量', '完读率', '付费率',
           '市场份额', '同比', '环比', '爆款指数']
SOURCE_MARK = ('待核', '来源', '口径', '估算', '样本库', '样本', '抽样', '平台公示', '未核', '据')
# 七类标注（节末钩=【钩子·X】四类类型后缀或【钩子+留白】简化写法；情绪靶点六类=排除钩子类）
MARKS = ['【爽点+打脸】', '【悬念+反转】', '【虐点+击穿】', '【甜点+升温】', '【笑点+反差】', '【泪点+来不及】', '【钩子+留白】']
# 单类标注（【爽点】/【悬念】…）= 阶段 5 §三 的"七类"字面写法。写成单类时
# G1/F 项按 0 计数, 靶点密度与覆盖率会静默归零——不是"稿子没靶点", 是"标注写错了"。
# 实测教训: 女帝的第一天曾全篇用单类标注, 靶点密度报 0/万字, 排查半小时才定位到格式。
SINGLE_MARKS = ['【爽点】', '【悬念】', '【虐点】', '【甜点】', '【笑点】', '【泪点】']
HOOK_PAT = re.compile(r'【钩子[^】]*】')  # 节末钩计数：兼容【钩子·新问题/新信息/情绪转折/危险升级】与【钩子+留白】简化写法
HOOK_TAIL = 200  # 章末钩尾窗（字）：章末钩只认章尾——stage3 口径「每章末 100 字内」，窗宽 200 字给标注格式留余量
PLACEHOLDER = ('____', '………', '悬念/情绪/行动钩', '待填', 'TBD')


def read(p: Path) -> str:
    return p.read_text(encoding='utf-8-sig')


def find_file(files, *patterns) -> Path:
    for pat in patterns:
        for f in files:
            if re.match(pat, f.name):
                return f
    return None


def table_rows(text: str, header_kw: str, exact_col: str = None, exclude_lead: str = None):
    """找表头含 header_kw 的 markdown 表, 返回 (表头列, 数据行列表) 或 None。

    ⚠️ 抢命中陷阱：原实现只判「表头行含关键字」，而节拍表本身就带
    「靶点标注位」「伏笔动作」两列（workflow 3.2 九列定义），于是 F/C 两项会把
    **节拍表**当成独立预埋表——实测 F 项拿节拍表 3 行（= 章数）当靶点分母，
    算出「覆盖率 200%」这种不可能值，AT-14硬门 恒过失效。
    对策：exact_col 优先只认列名**恰为**该值的表；exclude_lead 排除首列名含该
    子串的表（节拍表首列 =「章 N」，用它把节拍表从预埋表查询中剔除）。
    """
    lines = text.splitlines()
    cands = []  # (表头列, 数据行)
    for i, ln in enumerate(lines):
        if header_kw in ln and ln.strip().startswith('|'):
            cols = [c.strip() for c in ln.strip().strip('|').split('|')]
            rows = []
            for ln2 in lines[i + 1:]:
                s = ln2.strip()
                if not s.startswith('|'):
                    break
                if re.match(r'^\|[\s:|-]+\|$', s):
                    continue  # 分隔行
                cells = [c.strip() for c in s.strip('|').split('|')]
                rows.append(cells)
            cands.append((cols, rows))
    # 顺序不可颠倒：**先按 exclude_lead 剔除干扰表，再做 exact_col 精配**。
    # 反过来（先精配后剔除）无效——实测「靶点标注位」与「靶点编号」都不是列名恰等于
    # 「靶点」的值，只能落到前缀轮，而节拍表在文档里排在独立靶点表之前，先到先得。
    if exclude_lead:
        cands = [(c, r) for c, r in cands if not (c and exclude_lead in c[0])]
    if not cands:
        return None
    if exact_col:
        # 两轮匹配：① 列名**恰为** exact_col ② 列名以 exact_col 开头（后缀限长，
        # 容忍「靶点编号」这类带后缀的写法）
        for cols, rows in cands:
            if any(c == exact_col for c in cols):
                return cols, rows
        for cols, rows in cands:
            if any(c.startswith(exact_col) and len(c) <= len(exact_col) + 4 for c in cols):
                return cols, rows
    return cands[0][0], cands[0][1]


def cell_empty(v: str) -> bool:
    v = v.strip()
    return (not v) or any(ph in v for ph in PLACEHOLDER) or set(v) <= set('- ')


def table_after_heading(text: str, heading_kw: str):
    """找含 heading_kw 的标题行之后的第一个 markdown 表, 返回 (表头列, 数据行) 或 None。

    时间线台账的表头是「| 项 | 值 |」——本身不含「时间线」字样，table_rows 按
    表头关键字匹配不到它，故按标题锚取表（P 项用）。
    """
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if heading_kw in ln and ln.strip().startswith('#'):
            for ln2 in lines[i + 1:]:
                s = ln2.strip()
                if s.startswith('|'):
                    cols = [c.strip() for c in s.strip('|').split('|')]
                    rows = []
                    for ln3 in lines[lines.index(ln2) + 1:]:
                        s3 = ln3.strip()
                        if not s3.startswith('|'):
                            break
                        if re.match(r'^\|[\s:|-]+\|$', s3):
                            continue
                        rows.append([c.strip() for c in s3.strip('|').split('|')])
                    if rows:
                        return cols, rows
                    return None
                if s and not s.startswith('>'):
                    break  # 标题与表之间隔了正文——本标题下无表
    return None


def main():
    # 显式帮助入口：-h/--help 打 docstring 退 0（无参仍退 1，保持 AT-56 用法错误口径）
    if any(a in ("-h", "--help") for a in sys.argv[1:]):
        print(__doc__ or "用法: 见脚本头部 docstring")
        sys.exit(0)
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    arg = Path(sys.argv[1])
    extra = [Path(a) for a in sys.argv[2:]]
    if arg.is_dir():
        files = sorted(p for p in arg.glob('*.md') if p.is_file())
        files += extra
    else:
        if not arg.exists():
            print(f'❌ 文件不存在: {arg}（用法: check-artifacts.py <项目目录> 或 <文件1> [文件2 ...]）')
            sys.exit(1)
        files = [arg] + extra
    if not files:
        print('未找到任何产物文件')
        sys.exit(1)

    # 七步法产物链命名规范（templates/README.md）：02-细纲.md 单文件两篇——
    # f02（人设动机视图）与 f03（节末钩/伏笔表视图）同指该文件；f04=03-正文.md；
    # f05=04-润色标注稿.md、f05n=04-正文净稿.md（04 双版本）。变量名沿用历史编号，
    # 与现行文件名编号错位——禁按变量名"纠正"正则。禁拆回两个文件（deliverables 命名规范）。
    f02 = f03 = find_file(files, r'02[-_]', r'.*细纲.*')
    f04 = find_file(files, r'03[-_]', r'.*正文.*')
    f05 = find_file(files, r'04[-_].*标注.*', r'.*润色标注.*')
    f05n = find_file(files, r'04[-_].*净稿.*', r'.*净稿.*')

    # 假绿灯守卫：全部链文件一个都没命中 = 无文件可查（退 1，禁报全过）
    if not any((f02, f04, f05, f05n)):
        print('❌ 无文件可查：输入中未发现任何七步法产物链文件')
        print('   （02-细纲.md / 03-正文.md / 04-润色标注稿.md / 04-正文净稿.md 均未命中）')
        print('   排查：①路径是否为项目目录或产物文件本身 ②文件名是否符合 templates/README.md 命名规范')
        print('   阶段 4/6 之前本脚本无机检面——确无机检对象时请人工核验并标注"⚠️ 产物机检降级"')
        sys.exit(1)

    issues, must, notes = [], [], []

    def warn(msg):
        issues.append(msg)
        print(f'  ⚠️ {msg}')

    def bad(msg):
        must.append(msg)
        print(f'  ❌ {msg}')

    print(f'=== 产物文件发现（七步法链）===\n  细纲(双视图)={f02 and f02.name} '
          f'正文={f04 and f04.name} 标注稿={f05 and f05.name} 净稿={f05n and f05n.name}')

    # A 章末钩字段（细纲节拍表）
    print('=== A 章末钩字段（细纲表）===')
    if f03:
        t03 = read(f03)
        tb = table_rows(t03, '节末钩', exact_col='节末钩')
        if tb:
            cols, rows = tb
            idx = next((i for i, c in enumerate(cols) if '钩' in c), None)
            holes = [r[0] if r else '?' for r in rows
                     if idx is None or idx >= len(r) or cell_empty(r[idx])]
            if holes:
                bad(f'细纲章末钩空缺 {len(holes)} 处: 章 {", ".join(holes[:8])}（A 项——阶段4 门禁）')
            else:
                print(f'  ✅ {len(rows)} 章钩字段全在位')
        else:
            warn('细纲存在但未识别到"节末钩"列表（模板格式变化？同步本脚本或人工核验）')
    else:
        notes.append('A 跳过: 未找到 02-细纲.md')

    # B 人设动机（02）
    print('=== B 配角动机字段（方案）===')
    if f02:
        t02 = read(f02)
        mot_lines = [ln for ln in t02.splitlines() if '动机' in ln]
        # 标题行 ≠ 空缺行：`**三层欲望动机**：` / `#### 动机` / `| 独立动机句 |` 是块标题与表头,
        # 本身不含内容但下面紧随表格或正文。只认「行尾冒号且冒号后为空」的**续行缺失**形态，
        # 并排除纯标题（以 ** 或 # 包裹、或本身就是 markdown 表头单元格）。
        def _is_heading(ln):
            s = ln.strip()
            if re.match(r'^\s*#{1,6}\s', s):
                return True
            if re.fullmatch(r'\*\*[^*]*动机[^*]*\*\*[:：]?', s):
                return True   # **三层欲望动机**：
            if s.startswith('|'):
                return True   # 表格行/表头, 内容在末列, 缺列另由 cell_empty 判
            return False

        holes = [ln.strip()[:60] for ln in mot_lines
                 if not _is_heading(ln)
                 and (cell_empty(re.sub(r'^[\s|*-]*动机[^:：]*[:：]?', '', ln).strip())
                      or re.search(r'动机[^\n]{0,20}_{3,}', ln)
                      or re.search(r'动机[^:：\n]*[:：]\s*$', ln))]  # 行尾"动机："空值
        if not mot_lines:
            warn('方案存在但未找到任何"动机"字段（人设卡格式变化？同步本脚本或人工核验）')
        elif holes:
            bad(f'动机字段空缺 {len(holes)} 处（B 项——缺动机=工具人）: {holes[0]}')
        else:
            print(f'  ✅ {len(mot_lines)} 处动机字段均有内容')
    else:
        notes.append('B 跳过: 未找到 02-细纲.md')

    # C 伏笔双标对账（02 伏笔表 vs 04 标注稿）
    print('=== C 伏笔双标对账（【伏笔·埋】/【伏笔·收】）===')
    if f03 and f05:
        tb = table_rows(read(f03), '伏笔', exact_col='伏笔', exclude_lead='章')
        t05 = read(f05)
        # 兼容带编号/描述的写法：【伏笔·埋】/【伏笔·埋·V1】/【伏笔·埋·V1·珠帘=她能拆的东西】
        # 实测教训: 阶段 5 规范要求"埋描一体"（描述写进括号内），只认【伏笔·埋】会让
        # 全部合规标注计 0，报成"地图 11 / 埋 0 / 收 0"的假红灯，排查方向被带偏到"漏标"。
        n_buried = len(re.findall(r'【伏笔·埋[^】]*】', t05))
        n_taken = len(re.findall(r'【伏笔·收[^】]*】', t05))
        if tb:
            n_map = len(tb[1])
            status = '✅' if (n_buried == n_map and n_taken == n_map) else '⚠️'
            # 重复铺垫识别：埋标多于地图条目时，若多出的都是同一批 Vx 的重复埋设
            # （地图内已有该编号），那是"同一伏笔多处铺垫"的合规写法，不是错；
            # 只有出现地图里没有的 Vx 才是真错（多埋了没规划的伏笔）。
            ids_buried = re.findall(r'【伏笔·埋·([^·】]+)', t05)
            dup_note = ''
            if n_buried > n_map and ids_buried:
                uniq = list(dict.fromkeys(ids_buried))
                extra = n_buried - len(uniq)
                if extra > 0 and len(uniq) == n_taken:
                    status = '✅'
                    dup_note = (f'（埋 {n_buried} > 地图 {n_map}：其中 {extra} 处为同一 Vx 的重复铺垫, '
                                f'编号去重后 {len(uniq)} 个 = 收 {n_taken} 个, 判合规）')
            print(f'  {status} 地图条目 {n_map} | 埋 {n_buried} | 收 {n_taken}'
                  f'（对账公式: 埋数=收数=地图条目数）{dup_note}')
            if status == '⚠️':
                warn(f'伏笔双标对账不平: 地图{n_map}/埋{n_buried}/收{n_taken}（C 项——第 7 查重点；'
                     f'若为重复铺垫请确认编号一致, 若为漏收请补收标）')
        else:
            warn('细纲存在但未识别到"伏笔"表（C 项降级人工核验）')
    else:
        notes.append('C 跳过: 缺 02 细纲或 04 标注稿')

    # D 数字守恒（03 正文 vs 04 净稿——去AI味不丢数字）
    print('=== D 数字守恒（正文 vs 净稿——去AI味不丢数字）===')
    if f04 and f05n:
        def digits(p: Path) -> set:
            t = re.sub(r'^#+.*$', '', read(p), flags=re.M)  # 去标题行（防文件名编号"04/05"污染）
            return set(re.findall(r'\d+', t))
        n04, n05 = digits(f04), digits(f05n)
        lost, added = sorted(n04 - n05), sorted(n05 - n04)
        if lost or added:
            warn(f'数字集合差异: 丢失 {lost[:10] or "无"} / 新增 {added[:10] or "无"}（D 项——信息守恒）')
        else:
            print(f'  ✅ 数字集合一致（{len(n04)} 个）')
    else:
        notes.append('D 跳过: 需 03 正文与 04 净稿同时存在')

    # K 双版本逐字对账（stage5 门4/R9 的唯一机检面）
    # 背景：D 项只比**数字集合**（信息守恒的可计算子集），"净稿与标注稿除标注符号外
    # 逐字一致"这条投稿可信度底座门，此前的实现只有人眼——三轮隔离评估连续点名
    # （阶段 5 建议 1/5：门 4、R9、模板、stage6 P1 第 45 项都写"逐字一致"，无机检）。
    # 口径（stage5 建议 5 显式化的对账方法）：标注稿剥去全部【…】标注 + 引用/标题行
    # + 空白后，应与净稿**完全相等**；任何残差 = 净稿被手改过，或标注稿动了正文。
    print('=== K 双版本逐字对账（标注稿剥标注 vs 净稿，stage5 门4/R9）===')
    if f05 and f05n:
        def body_text(p: Path) -> str:
            t = read(p)
            # 剔引用块（> 开头，含样例声明）与标题行（# 开头——两稿标题文字本就不同：
            # 「04-正文净稿」vs「04-润色标注稿」，不剔必然假红）
            t = '\n'.join(ln for ln in t.splitlines()
                          if not re.match(r'^\s*(?:>|#{1,6}\s)', ln))
            t = re.sub(r'【[^】]*】', '', t)      # 剥全部方括号标注（七类复合式+伏笔双标+钩子后缀）
            t = re.sub(r'[#|*`>]', '', t)       # 剔行内 MD 标记
            return re.sub(r'\s', '', t)         # 剔全部空白（排版差异不算文本差异）
        b05, b05n = body_text(f05), body_text(f05n)
        if b05 == b05n:
            print(f'  ✅ 剥标注后逐字一致（{len(b05)} 字）')
        else:
            # 可复算：报首处差异字位与双侧上下文（对齐 R14 关键词输出纪律）
            i = next((k for k in range(min(len(b05), len(b05n))) if b05[k] != b05n[k]),
                     min(len(b05), len(b05n)))
            warn(f'双版本不一致（K 项——stage5 R9/门4）：剥标注后 {len(b05)} 字 vs 净稿 '
                 f'{len(b05n)} 字，首处差异字位 {i}：标注稿「{b05[max(0, i-10):i+10]}」'
                 f' vs 净稿「{b05n[max(0, i-10):i+10]}」。修法：以标注稿为基准重生成净稿，'
                 f'禁手改净稿"追"标注稿')
    else:
        notes.append('K 跳过: 需 04 标注稿与 04 净稿同时存在')

    # L 净稿清洁三扫（stage5 门5/R10 的唯一机检面）
    # 背景：编辑痕迹/逐字重复句/说明性尾注是投稿直接拒项（stage6 P1 第 44 项），
    # 此前只有 stage5 人工扫——机检面零覆盖（阶段 5 建议 2）。
    # 口径：三类各出可机检子集，命中 = ⚠️(exit 2) 提示 S1 清稿，禁假合格。
    # 逐字重复句只提示不判死——伏笔回看暗示按设计可重复（断链归 stage6 跨章扫描管，
    # 此处管"脏重复"），与 E 项同款"命中仅提示人工复核"。
    print('=== L 净稿清洁三扫（编辑痕迹/逐字重复句/说明性尾注，stage5 门5/R10）===')
    if f05n:
        lines = [ln for ln in read(f05n).splitlines()
                 if not re.match(r'^\s*(?:>|#{1,6}\s)', ln)]
        body = '\n'.join(lines)
        # ① 编辑痕迹：修正/批注残留 + 括号小标题行（（一）（二）式单独成行）
        EDIT_TRACE = re.compile(r'(修正\s*[:：]|批注\s*[:：]|\[改\]|\[需复核\]|TODO|TBD|待填)')
        paren_head = re.compile(r'^\s*[（(]\s*[一二三四五六七八九十\d]+\s*[）)]\s*$')
        tr_hits = [ln.strip()[:40] for ln in lines
                   if EDIT_TRACE.search(ln) or paren_head.match(ln)]
        # ② 逐字重复句：≥10 字整句完全重复出现 ≥2 次（去空白后按句号/问号/叹号切分）
        sents = [s for s in re.split(r'[。！？!?]', re.sub(r'\s', '', body)) if len(s) >= 10]
        dup = sorted({s for s in sents if sents.count(s) >= 2})
        # ③ 说明性尾注：文末作者注类（只看末 8 行——尾注按定义落在文末）
        TAIL_NOTE = re.compile(r'(作者注|作者的话|题外话|PS\s*[:：]|写在后面|码字不易|求收藏)')
        tail_hits = [ln.strip()[:40] for ln in lines[-8:] if TAIL_NOTE.search(ln)]
        if tr_hits:
            warn(f'净稿命中编辑痕迹 {len(tr_hits)} 处（L 项——S1 清稿，投稿直接拒项）: {tr_hits[:3]}')
        else:
            print('  ✅ 无编辑痕迹（修正:/批注/占位符/括号小标题零命中）')
        if dup:
            warn(f'净稿检出逐字重复句 {len(dup)} 组（L 项——≥10 字整句重复；伏笔回看设计内重复'
                 f'请人工确认，其余 = 脏重复）: {dup[:3]}')
        else:
            print('  ✅ 无逐字重复句（≥10 字整句零重复）')
        if tail_hits:
            warn(f'净稿文末命中说明性尾注（L 项——禁混入正文）: {tail_hits[:3]}')
        else:
            print('  ✅ 文末无说明性尾注')
    else:
        notes.append('L 跳过: 未找到 04-正文净稿.md')

    # E 防狗血关键词
    print('=== E 防狗血关键词（欺骗引擎类, 仅提示人工复核）===')
    hit = False
    for f in (f04, f05n or f05):
        if not f:
            continue
        t = read(f)
        for w in sorted(DOG_BLOOD, key=len, reverse=True):  # 长词优先, 命中后从文本剔除防子串重复报
            if w in t:
                hit = True
                warn(f'正文命中"{w}"（E 项——对照 genre-map 档案 9 防狗血清单第 1 条人工判定）')
                t = t.replace(w, '')
    if not hit:
        print('  ✅ 零命中')

    # F 标注覆盖（02 靶点表 vs 04 标注数）
    print('=== F 情绪标注覆盖 ===')
    if f03 and f05:
        tb = table_rows(read(f03), '靶点', exact_col='靶点', exclude_lead='章')
        t05 = read(f05)
        if tb and tb[1]:
            n_targets = len(tb[1])
            # F 项分子=六类情绪靶点标注（剔除【钩子+留白】防虚抬覆盖率——与 docstring 六类口径对齐）
            n_marks = sum(t05.count(m) for m in MARKS if m != '【钩子+留白】')
            # 单类标注拦截：写成【爽点】时六类复合计数为 0, 覆盖率会静默掉到 0%,
            # 人会先去猜"哪章漏写靶点", 实际是格式错。这里直接点名。
            n_single = sum(t05.count(m) for m in SINGLE_MARKS)
            if n_single and n_marks == 0:
                warn(f'标注格式错误：检出 {n_single} 处单类标注（【爽点】式），'
                     f'机检只认七类复合标注（【爽点+打脸】式）——覆盖率与靶点密度将按 0 计。'
                     f'改法：`【爽点】`→`【爽点+打脸】`、`【悬念】`→`【悬念+反转】`、'
                     f'`【虐点】`→`【虐点+击穿】`、`【甜点】`→`【甜点+升温】`、'
                     f'`【笑点】`→`【笑点+反差】`、`【泪点】`→`【泪点+来不及】`')
            cov = n_marks / max(n_targets, 1) * 100
            ok = cov >= 90
            print(f'  {"✅" if ok else "⚠️"} 靶点行 {n_targets} | 标注 {n_marks} | 覆盖率 {cov:.0f}%（AT-14 硬线 ≥90%）')
            if cov > 100:
                # >100% 只有一个成因：分母取到的不是靶点条目数。历史实测过
                # 「靶点行 3（实为章数）/ 标注 6 / 覆盖率 200%」这种不可能值——
                # 说明 table_rows 把节拍表当成了独立靶点表。此处直接点名。
                warn(f'覆盖率 {cov:.0f}% > 100% —— 分母取错表：命中的是节拍表而非独立'
                     f'「情绪靶点规划表」。检查该表是否存在且表头含「靶点」列（表头勿含「章」）')
            elif not ok:
                warn(f'标注覆盖率 {cov:.0f}% < 90%（AT-14 硬线——F 项，列出漏标靶点）')
        else:
            notes.append('F 跳过: 未识别到独立靶点表（表头须含「靶点」列且首列非「章」）')
    else:
        notes.append('F 跳过: 缺 02 细纲或 04 标注稿')

    # ==================== 阶段 3 六表之四表对账（两轮遗留项） ====================
    # 背景：六张预埋表此前只有伏笔（C 项）与靶点（F 项）有对账面，金句/意象/时间线/
    # 名场面四表纯人工——此前两轮遗留，样例 07-复盘列为下一轮首选候选。
    # 统一口径：**缺表 = ℹ️ 跳过**（对齐 F 项——六表填满是阶段 3 人工门 2，机检做
    # "有表即对账"的渐进补强）；**有表而对不上 = ⚠️(exit 2)**。
    # 正文章数共用口径：03 正文分章标记优先；无分章（迷你夹具/片段）时退细纲节拍表
    # 行数——否则 n_sec=0 会让 O/Q 的章号越界检查静默跳过（退化实测发现：
    # 无分章正文 + 章序 99 不报红，形同虚设）
    def _n_chapters() -> int:
        t04 = read(f04) if f04 else read(f05)
        n = len(list(re.finditer(r'^(?:##\s*\d+\.?|【\d+】|\d+\.|\d+)$', t04, flags=re.M)))
        if not n and f03:
            tb = table_rows(read(f03), '章', exact_col='章')  # 节拍表首列恰为「章」
            if tb:
                n = len(tb[1])
        return n

    # N 金句预埋清单（②表）：逐字兑现 + 表内自检
    print('=== N 金句预埋清单对账（细纲②表 vs 正文逐字兑现）===')
    if f03 and f05:
        tb = table_rows(read(f03), '金句', exact_col='金句')
        if tb and tb[1]:
            body05 = re.sub(r'\s', '', re.sub(r'【[^】]*】', '', read(f05)))
            n_ok, miss, n_bad_len = 0, [], 0
            for row in tb[1]:
                q = ''
                for h, c in zip(tb[0], row):
                    if '金句' in h and '预埋' not in h and '位' not in h:
                        q = re.sub(r'[*`\s]', '', c)
                        break
                if not q:
                    continue
                if not 15 <= len(q) <= 25:
                    n_bad_len += 1
                    warn(f'金句表条目「{q[:20]}…」{len(q)} 字，不在 15-25 字带内（N 项——AT-34 口径）')
                if q in body05:
                    n_ok += 1
                else:
                    miss.append(q[:18])
            if miss:
                warn(f'金句预埋未逐字兑现 {len(miss)}/{n_ok + len(miss)} 条（N 项——细纲承诺的金句在'
                     f'正文找不到：查润色期改写漂移，或漏写该金句位）: {miss[:3]}')
            elif n_ok:
                print(f'  ✅ {n_ok} 条金句全部逐字在位')
        else:
            notes.append('N 跳过: 未识别到金句预埋清单（表头须含「金句」列）')
    else:
        notes.append('N 跳过: 缺 02 细纲或 04 标注稿')

    # O 意象系统清单（③表）：核心信物唯一 + 闭环三列非空 + 落点章号不越界
    # 逐字兑现不做——意象关键词提取歧义大（「药瓶标签」正文从无连写），误报风险高于收益
    print('=== O 意象系统清单对账（细纲③表结构与闭环设计）===')
    if f03 and f05:
        tb = table_rows(read(f03), '意象', exact_col='意象')
        if tb and tb[1]:
            core = [r for r in tb[1] if any('核心' in c for c in r)]
            if len(core) != 1:
                warn(f'意象表核心信物行 {len(core)} 行（O 项——P1 门 16 要求 1 个信物首尾闭环，'
                     f'含「核心」字样的行须恰 1 行）')
            else:
                print('  ✅ 核心信物 1 行（闭环轴唯一）')
            n_bad_loop = 0
            for r in tb[1]:
                cells = dict(zip(tb[0], r))
                if not (cells.get('首现', '').strip() and cells.get('末现', '').strip()):
                    n_bad_loop += 1
            if n_bad_loop:
                warn(f'意象表 {n_bad_loop} 行首现/末现列空（O 项——闭环三列缺位即闭环设计不成立）')
            else:
                print(f'  ✅ {len(tb[1])} 行首现/末现均非空')
            # 落点章号 ≤ 正文章数（意象落在不存在的章 = 规划与成文脱节）
            n_sec = _n_chapters()
            over = []
            for r in tb[1]:
                cells = dict(zip(tb[0], r))
                for col in ('首现', '递进', '末现'):
                    for m in re.finditer(r'第?\s*(\d+)\s*章', cells.get(col, '')):
                        if n_sec and int(m.group(1)) > n_sec:
                            over.append(f'「{cells.get("意象", "?")[:12]}」{col}={m.group(1)}')
            if over:
                warn(f'意象落点章号越界（O 项——正文仅 {n_sec} 章）: {over[:3]}')
            elif n_sec:
                print(f'  ✅ 落点章号均 ≤ 正文 {n_sec} 章')
        else:
            notes.append('O 跳过: 未识别到意象系统清单（表头须含恰「意象」列）')
    else:
        notes.append('O 跳过: 缺 02 细纲或 04 标注稿')

    # P 时间线台账（⑤表）：四行钉死 + 关键道具宽松落点（2 字滑窗，抓完全没进正文的道具）
    # 时间词跨章自洽归 stage6 跨章扫描三查，本项不做（弱代理只提示，不判死）
    print('=== P 时间线台账对账（细纲⑤表钉死与道具落点）===')
    if f03 and f05:
        tb = table_after_heading(read(f03), '时间线')
        if tb and tb[1]:
            need = ('纪年', '年龄', '季节', '关键道具')
            got = {r[0].strip() for r in tb[1] if r}
            lack = [k for k in need if not any(k in g for g in got)]
            if lack:
                warn(f'时间线台账缺行 {lack}（P 项——纪年/年龄/季节/关键道具动笔前须钉死）')
            else:
                print('  ✅ 台账四行在位（纪年/年龄/季节/关键道具）')
            prop_row = next((r for r in tb[1] if r and '道具' in r[0]), None)
            if prop_row and len(prop_row) > 1:
                body05 = re.sub(r'\s', '', re.sub(r'【[^】]*】', '', read(f05)))
                lost = []
                for item in re.split(r'[／/、，,]', re.sub(r'（[^）]*）', '', prop_row[1])):
                    w = item.strip()
                    if not w:
                        continue
                    grams = {w[i:i + 2] for i in range(len(w) - 1)} if len(w) > 2 else {w}
                    if not any(g in body05 for g in grams):
                        lost.append(w)
                if lost:
                    warn(f'关键道具未进正文（P 项——钉死的道具在正文零落点，查漏写或改名）: {lost[:4]}')
                else:
                    print('  ✅ 关键道具均在正文有落点（2 字滑窗宽松匹配）')
        else:
            notes.append('P 跳过: 未识别到时间线台账（「时间线」标题后的表）')
    else:
        notes.append('P 跳过: 缺 02 细纲或 04 标注稿')

    # Q 名场面预埋表（⑥表）：≥1 行 + 五字段非空 + 章序不越界 + 一句话宽松落点
    print('=== Q 名场面预埋表对账（细纲⑥表，AT-69）===')
    if f03 and f05:
        tb = table_rows(read(f03), '名场面')
        if tb and tb[1]:
            if len(tb[1]) < 1:
                warn('名场面表零行（Q 项——AT-69 要求 ≥1 个）')
            n_empty = sum(1 for r in tb[1] if any(not c.strip() for c in r))
            if n_empty:
                warn(f'名场面表 {n_empty} 行字段空（Q 项——一句话/章序/峰值/兑现方式/传播点五字段须齐）')
            t04 = read(f04) if f04 else read(f05)
            n_sec = _n_chapters()
            over, body05 = [], re.sub(r'\s', '', re.sub(r'【[^】]*】', '', read(f05)))
            for r in tb[1]:
                cells = dict(zip(tb[0], r))
                for m in re.finditer(r'(\d+)', cells.get('预定章序', '')):
                    if n_sec and int(m.group(1)) > n_sec:
                        over.append(f'章序{m.group(1)}>{n_sec}')
                sent = re.sub(r'\s', '', cells.get('名场面一句话', ''))
                if sent:
                    grams = {sent[i:i + 2] for i in range(len(sent) - 1)} if len(sent) > 2 else {sent}
                    if not any(g in body05 for g in grams):
                        warn(f'名场面「{sent[:18]}…」正文零落点（Q 项——2 字滑窗宽松匹配仍不中，'
                             f'查漏铺垫或改写漂移）')
            if over:
                warn(f'名场面预定章序越界（Q 项——正文仅 {n_sec} 章）: {over[:3]}')
            if not n_empty and not over:
                print(f'  ✅ {len(tb[1])} 行五字段齐、章序在位')
        else:
            notes.append('Q 跳过: 未识别到名场面预埋表（表头须含「名场面」列）')
    else:
        notes.append('Q 跳过: 缺 02 细纲或 04 标注稿')

    # G 靶点密度与节末钩（钩子/靶点从人工数数升级为标注实测）
    print('=== G 靶点密度与章末钩（标注稿实测）===')
    if f05:
        t05 = read(f05)
        body = re.sub(r'【[^】]*】', '', t05)  # 剔除标注符号本身再数字数（字数口径同 check-length）
        n_chars = len(re.sub(r'\s', '', re.sub(r'[#|*`>-]', '', body)))
        n_targets = sum(t05.count(m) for m in MARKS if m != '【钩子+留白】')
        n_hooks = len(HOOK_PAT.findall(t05))  # 兼容【钩子·X】四类类型后缀与【钩子+留白】简化写法
        n_single_g = sum(t05.count(m) for m in SINGLE_MARKS)
        if n_single_g and n_targets == 0:
            warn(f'G1 靶点密度按 0 计，但检出 {n_single_g} 处单类标注（【爽点】式）——'
                 f'这是格式错误不是漏写靶点：机检只认七类复合标注（【爽点+打脸】式），改格式后密度会立刻回正')
        rate = n_targets / max(n_chars, 1) * 10000
        hook_rate = n_hooks / max(n_chars, 1) * 10000
        if rate >= 18:
            print(f'  ✅ 靶点密度 {rate:.1f}/万字（{n_targets} 个 / {n_chars} 字——虐文硬门带 ≥18）')
        elif rate >= 15:
            print(f'  ✅ 靶点密度 {rate:.1f}/万字（{n_targets} 个 / {n_chars} 字——合格带; 虐文须 ≥18）')
        elif rate >= 12:
            print(f'  ⚠️ 靶点密度 {rate:.1f}/万字（{n_targets} 个 / {n_chars} 字——12-14 边缘带）')
            warn(f'靶点密度 {rate:.1f}/万字 处边缘带（G1 项——须补至 ≥15/万字, 虐文 ≥18）')
        else:
            print(f'  ⚠️ 靶点密度 {rate:.1f}/万字（{n_targets} 个 / {n_chars} 字——低于合格线）')
            warn(f'靶点密度 {rate:.1f}/万字 < 15（G1 项——对照细纲靶点规划表查漏标或漏写靶点章）')
        print(f'  ℹ️ 章末钩 {n_hooks} 个 = {hook_rate:.1f}/万字（红线 ≥7/万字——参考口径不计退出码, 逐章在位率见 G2）')
        # 分节标记：规范=纯数字独立成行（1/2/3，不带符号）；兼容标注稿 ## N./## N 与带符号写法【N】/N.
        secs = re.split(r'^(?:##\s*\d+\.?|【\d+】|\d+\.|\d+)$', t05, flags=re.M)
        if len(secs) <= 1:
            notes.append('G2 跳过: 标注稿未识别到章节标记（片段/单章测试）——章末钩按细纲 A 项与人工核验')
        else:
            # 章末钩按「章末」判：只搜章尾 200 字窗——章中出现的【钩子】标注不构成章末钩
            # （stage3：每章末 100 字内须有动作钩标记；搜整章会让章中标注冒充章末在位）
            miss = [f'第{i}章' for i, s in enumerate(secs[1:], 1)
                    if not HOOK_PAT.search(s[-HOOK_TAIL:])]
            n_sec = len(secs) - 1  # 首个分块为导语, 不计入章
            if miss:
                warn(f'章末钩缺失 {len(miss)}/{n_sec} 章: {", ".join(miss[:8])}（G2 项——每章末 200 字内须有章末钩标注【钩子·X】四类任一或【钩子+留白】简化写法, 断在冲突最高点）')
            else:
                print(f'  ✅ {n_sec} 章章末钩全在位（每章均有章末钩标注）')
            # G3 节末钩类型同质：连续两章同类型=节奏同质化，四类须轮换或错峰
            g3_types = []
            for s in secs[1:]:
                m3 = re.search(r'【钩子·(新问题|新信息|情绪转折|危险升级)】', s[-HOOK_TAIL:])
                g3_types.append(m3.group(1) if m3 else None)
            same = [f'第{i}/{i + 1}章({g3_types[i - 1]})' for i in range(1, len(g3_types))
                    if g3_types[i - 1] and g3_types[i - 1] == g3_types[i]]
            typed = sum(1 for x in g3_types if x)
            if same:
                warn(f'章末钩类型同质: {", ".join(same[:6])}——连续两章同类型钩子=节奏同质化（G3），四类轮换（新问题/新信息/情绪转折/危险升级）或错峰')
            elif typed >= 2:
                print(f'  ✅ 章末钩类型无连续同质（{typed}/{n_sec} 章带类型后缀）')
            else:
                notes.append(f'G3 跳过: 类型后缀不足（{typed}/{n_sec} 章带【钩子·X】后缀）——补标类型后缀方可机检同质化')
    else:
        notes.append('G 跳过: 未找到 04 标注稿')

    # H 题材红线扫描（对抗用例——命中仅提示人工复核, 判罚级同 E 项）
    print('=== H 题材红线扫描（C2——净身出户洗白/亲情催泪/未成年恋/自杀自残美化/校园霸凌美化/性别对立/地域歧视, 仅提示人工复核）===')
    red_hit = False
    for f in (f04, f05n or f05):
        if not f:
            continue
        for ln in read(f).splitlines():
            for pat, msg in RED_LINE:
                if pat.search(ln):
                    red_hit = True
                    warn(f'正文命中题材红线嫌疑（{msg}）: {ln.strip()[:40]}')
    if not red_hit:
        print('  ✅ 零命中')

    # I 事实核验防线扫描（市场数据声称无来源即提示"待核"）
    print('=== I 事实核验防线（C4——无来源数据须标"待核"）===')
    fact_hit = False
    # 内部口径豁免：AT 编号、技能内部阈值（字数带/百分比带/章门）、伏笔与靶点计数、
    # 本轮自测实测值——这些是**规则值与本项目自算值**，不属"外部市场数据声称"，
    # 追来源标注属误报。实测教训: 女帝的第一天在细纲上一次性报了 8 处，
    # 全是「AT-10 45-55%」「回收率 100%」「23 个靶点」这类自洽口径，淹没真问题。
    INNER = ('AT-', '字位', '章门', '靶点', '回收率', '伏笔', '埋 / ', '埋/', '实测', '口径',
             '占比', '字数带', '字数', '预算', '门值', '带 ≥', '带≤', '∈',
             '弧线', '节点', '双峰', '峰', '场景', '节奏表', '配额',
             # 内部折算说明常写在续行（"靶点"落在上一行、"须配 18-24 个"落在本行），
             # 单行匹配不到关键词 → 误报 C4。实测漏这词会让样例的折算脚注稳定报假红灯。
             '须配', '按 AT-01', '万字', '正式写作', '迷你演示')
    for f in (f02,):
        if not f:
            continue
        for ln in read(f).splitlines():
            if any(k in ln for k in INNER):
                continue
            if (any(k in ln for k in DATA_KW) or re.search(r'\d+(\.\d+)?\s*%', ln)) \
                    and re.search(r'\d', ln) and not any(m in ln for m in SOURCE_MARK):
                fact_hit = True
                warn(f'数据声称无来源标记（C4——编造防线: 须标"待核"或引来源）: {ln.strip()[:50]}')
    if not fact_hit:
        print('  ✅ 未见无来源数据声称（内部口径值已豁免: AT 编号/字数带/靶点计数/伏笔回收率）')

    # J 导语/尾声结构核验（AT-06 导语 80-150 / AT-07 尾声 50-500）
    # 此前这两门只有 stage4 的人工专项门 + check-length 的拆分支判定，产物链侧无对账面：
    # 「导语压根没写」「尾声标签漏了」在阶段 4/6 都只表现为 ⚠️ 提示，人容易滑过去。
    # 口径：三要素（反常识场景/身份悬念/未完成动作）不可机检，只核**结构与字数带**——
    # 三要素仍走 stage4 人工复检，本项不冒充内容判定。
    print('=== J 导语/尾声结构核验（AT-06 导语 80-150 / AT-07 尾声 50-500）===')
    if f04:
        t04 = read(f04)
        # 与 check-length/G2 同款分章正则：规范=纯数字独立成行，兼容带符号写法
        m04 = list(re.finditer(r'^(?:##\s*\d+\.?|【\d+】|\d+\.|\d+)$', t04, flags=re.M))
        m_end = re.search(r'^[#【\s]*(?:尾声|尾聲)[】】】\s:：.。]?\s*$', t04, flags=re.M)
        if not m04:
            notes.append('J 跳过: 正文未识别到章节标记（迷你夹具/单章测试）——导语与尾声按 stage4 '
                         '专项门 + check-length.py 人工核验')
        else:
            intro_txt = t04[:m04[0].start()]
            # 只剔 MD 标记行（标题/引用/类型标签），**不能整行清空**——
            # 实测教训：早期版本用 re.sub(r'^.+?$','',txt,flags=re.M) 想剔标记，
            # 结果把导语正文一起删了，240 字导语被算成 0 字并误报"导语块为空"。
            intro_body = '\n'.join(ln for ln in intro_txt.splitlines()
                                   if not re.match(r'^\s*(?:>|【.*】|\[.*\]|#{1,6}\s|\*{3})', ln))
            n_intro = len(re.sub(r'\s', '', re.sub(r'[#|*`>\-]', '', intro_body)))
            if n_intro == 0:
                warn('导语块为空（AT-06 投稿必填 80-150 字）——首个章节标记之前须写导语')
            elif not 80 <= n_intro <= 150:
                warn(f'导语 {n_intro} 字，不在 AT-06 的 80-150 带内'
                     + ('（<80 信息量不足）' if n_intro < 80 else '（>150 拖慢首屏）'))
            else:
                print(f'  ✅ 导语 {n_intro} 字（AT-06 80-150 带内；三要素须人工复检）')
            if not m_end:
                warn('未识别到「尾声」标签行（AT-07 投稿必填 50-500 字）——check-length.py 会把'
                     '末块整体走章门并 ⚠️ 提示补尾声')
            else:
                n_end = len(re.sub(r'\s', '', re.sub(r'[#|*`>\-【】]', '', t04[m_end.end():])))
                if not 50 <= n_end <= 500:
                    warn(f'尾声 {n_end} 字，不在 AT-07 的 50-500 带内'
                         + ('（<50 信息量不足）' if n_end < 50 else '（>500 稀释结局冲击）'))
                else:
                    print(f'  ✅ 尾声 {n_end} 字（AT-07 50-500 带内）')
    else:
        notes.append('J 跳过: 未找到 03-正文.md')

    # M 送机检提交包四件（stage7 门10 的机检面）
    # 背景：送机检提交包四件此前只有 stage7 人工门（质量门第 10 项/自查第 9 项），
    # A-L 项与 check-all 都不查——缺件/字段错要到送检时才炸（阶段 7 建议 6）。
    # 口径：四件齐 + 正文纯文本带 [[首锁]] 标记 + CSV 五字段；缺 = ⚠️(exit 2)。
    print('=== M 送机检提交包四件（stage7 门10）===')
    mc_dir = (arg / '机检提交') if arg.is_dir() else None
    if mc_dir and mc_dir.is_dir():
        need = ['正文纯文本.md', '标题导语梗概.md', '金句列表.md', '伏笔回收.csv']
        missing = [n for n in need if not (mc_dir / n).exists()]
        if missing:
            warn(f'机检提交包缺件: {missing}（M 项——stage7 门10 四件齐；模板见 '
                 f'`templates/machine-check-package.md`）')
        else:
            print(f'  ✅ 四件齐')
        t_mc = mc_dir / '正文纯文本.md'
        if t_mc.exists():
            if '[[首锁]]' not in read(t_mc):
                warn('机检提交包正文纯文本缺 `[[首锁]]` 标记（M 项——check-mss T3 硬门的'
                     '显式卡点源；净稿无标记，送机检包须由净稿插回）')
            else:
                print('  ✅ 正文纯文本带 `[[首锁]]` 标记')
        f_csv = mc_dir / '伏笔回收.csv'
        if f_csv.exists():
            head = read(f_csv).splitlines()[0] if read(f_csv).splitlines() else ''
            lack = [c for c in ('埋设位置', '埋设原句', '回收位置', '回收原句', '回收方式')
                    if c not in head]
            if lack:
                warn(f'伏笔回收 CSV 缺字段 {lack}（M 项——五字段：埋设位置/埋设原句/'
                     f'回收位置/回收原句/回收方式，由 02-细纲 伏笔规划表导出）')
            else:
                print('  ✅ 伏笔回收 CSV 五字段在位')
    else:
        notes.append('M 跳过: 未找到 机检提交/ 目录（stage7 门10——送 check-mss 前必产四件，'
                     '模板见 templates/machine-check-package.md）')

    # R 后台投稿信息七字段阈值核验（darwin 普查 3.10 边界值项记的缺口：
    # 投稿面七字段此前纯人工——简介超带/标签数越界/金句超长要到编辑打回才知道）
    print('=== R 后台投稿信息七字段 + 短标题阈值（stage7 门3/5/6/8）===')
    sub_dir = (arg / '06-投稿包') if arg.is_dir() else None
    f_sub = (sub_dir / '后台投稿信息.md') if sub_dir and sub_dir.is_dir() else None
    if not f_sub or not f_sub.exists():
        notes.append('R 跳过: 未找到 06-投稿包/后台投稿信息.md（stage7 门5/6——投稿前必产七字段）')
    else:
        ts = read(f_sub)

        def _field(prefix):
            m = re.search(rf'\*\*{prefix}\*\*(?:[^：:]*)?[：:](.*)', ts)
            return m.group(1).strip() if m else ''

        # ① 作品名字：≤20 字（16-20 合格 / ≤15 最佳）+ 禁问号感叹号（AT-24）
        nm = re.search(r'《([^》]+)》', _field('作品名字'))
        if not nm:
            warn('后台投稿信息缺作品名字（stage7 门5——七字段缺项即交付不完）')
        else:
            n_nm = len(re.sub(r'\s', '', nm.group(1)))
            if n_nm > 20:
                warn(f'作品名字 {n_nm} 字 >20（AT-24 硬门——>20 字即硬门未过）')
            else:
                tier = '≤15 最佳档' if n_nm <= 15 else '16-20 合格档'
                print(f'  ✅ 作品名字《{nm.group(1)}》{n_nm} 字（{tier}）')
            if re.search(r'[？！?!]', nm.group(1)):
                warn(f'作品名字含问号/感叹号（AT-24 禁项）: {nm.group(1)}')
        # ② 作品标签 3-5 个
        tags = [x for x in re.split(r'[/／、,]',
                                    re.sub(r'（[^）]*）|\([^)]*\)', '', _field('作品标签')))
                if x.strip()]
        if not 3 <= len(tags) <= 5:
            warn(f'作品标签 {len(tags)} 个（stage7 门5——须 3-5 个）: {tags}')
        else:
            print(f'  ✅ 作品标签 {len(tags)} 个（3-5 带内）')
        # ③ 作品金句 1-2 句 × 每句 15-25 字（≠ 机检包金句列表 3-5 句，两口径分顶）
        quotes = re.findall(r'「([^」]+)」', _field('作品金句'))
        if not quotes:
            warn('后台投稿信息缺作品金句（stage7 门5）')
        elif len(quotes) > 2:
            warn(f'作品金句 {len(quotes)} 句 >2（stage7 门6——投稿金句 1-2 句，'
                 f'≠ 送机检包金句列表 3-5 句）')
        else:
            bad_q = [q for q in quotes if not 15 <= len(re.sub(r'\s', '', q)) <= 25]
            if bad_q:
                warn(f'作品金句超带（stage7 门6——每句 15-25 字）: {[q[:14] for q in bad_q]}')
            else:
                print(f'  ✅ 作品金句 {len(quotes)} 句 × 15-25 字（投稿面口径）')
        # ④ 内容简介 100-150 字
        intro = re.sub(r'（[^）]*）|\([^)]*\)', '', _field('内容简介'))
        n_intro = len(re.sub(r'\s', '', re.sub(r'[*`>]', '', intro)))
        if not 100 <= n_intro <= 150:
            warn(f'内容简介 {n_intro} 字，不在 100-150 带内（stage7 门6）')
        else:
            print(f'  ✅ 内容简介 {n_intro} 字（100-150 带内）')
        # ⑤ 类型/主角名/人设：AT 表无量化阈值，故只核「非空」（七字段缺项即交付不完，
        #    这是投稿包最常见的低级错误）。长度上限是**工程兜底非 AT 口径**——防整段误粘，
        #    阈值取得宽松（平台类型枚举一般 4-10 字/中文名 2-6 字/人设一句），误报可人工豁免。
        for fname, cap in (('作品类型', 20), ('主角名字', 15), ('主角人设', 60)):
            v = re.sub(r'（[^）]*）|\([^)]*\)', '', _field(fname)).strip()
            if not v:
                warn(f'后台投稿信息缺{fname}（stage7 门3——七字段缺项即交付不完）')
            elif len(re.sub(r'\s', '', v)) > cap:
                warn(f'{fname} {len(re.sub(chr(92) + "s", "", v))} 字超合理上限 {cap}'
                     f'（疑似整段误粘，stage7 门3；非 AT 口径，人工豁免）')
            else:
                print(f'  ✅ {fname}：{v[:14]}{"…" if len(v) > 14 else ""}')
        # ⑦ 投稿包只含两件（stage7 门1——过程产物 00-05 混入投稿包是常见错误）
        #    机检提交包在 `机检提交/` 另立目录，与本目录天然分离，不在此项管辖内。
        allow = {'正文.md', '后台投稿信息.md', 'README.md'}
        extra = sorted(f.name for f in sub_dir.iterdir()
                       if f.is_file() and f.name not in allow)
        if extra:
            warn(f'投稿包多出文件 {extra}（stage7 门1——只含正文+后台投稿信息两件；'
                 f'过程产物留项目目录备查，样例 README 属说明文件已豁免）')
        else:
            print('  ✅ 投稿包只含两件（正文 + 后台投稿信息；README 为样例说明已豁免）')
        # ⑧ 投稿正文禁出现任何机检标记（stage7 R4——标记混入投稿正文会被编辑直接发现）
        f_body = next((f for f in sub_dir.glob('正文.*') if f.is_file()), None)
        if not f_body:
            notes.append('  投稿正文未找到（06-投稿包/正文.*）——机检标记检查跳过')
        else:
            bt = read(f_body)
            leaked = []
            if '[[首锁]]' in bt or '[[二锁]]' in bt:
                leaked.append('[[首锁]]/[[二锁]] 双锁标记')
            n_mk = sum(bt.count(m) for m in MARKS if m != '【钩子+留白】')
            n_mk += len(HOOK_PAT.findall(bt))
            n_mk += sum(bt.count(m) for m in SINGLE_MARKS)
            if n_mk:
                leaked.append(f'{n_mk} 处情绪/钩子标注')
            if leaked:
                warn(f'投稿正文含机检标记 {leaked}（stage7 R4——标记只存在于送机检包，'
                     f'投稿正文零标注零标记；改用机检提交包/正文纯文本.md）')
            else:
                print('  ✅ 投稿正文零标注零标记（stage7 R4）')
        # ⑥ 短标题备选（AT-25 ≤10 字，**可选字段**——缺项只提示不判红）
        sline = next((ln for ln in ts.splitlines() if '短标题' in ln), '')
        snm = re.search(r'《([^》]+)》', sline)
        if not snm:
            print('  ℹ️ 短标题备选缺失（AT-25 可选字段——缺项不判红）')
        else:
            n_s = len(re.sub(r'\s', '', snm.group(1)))
            if n_s > 10:
                warn(f'短标题备选《{snm.group(1)}》{n_s} 字 >10（AT-25）')
            elif re.search(r'[？！?!]', snm.group(1)):
                warn(f'短标题备选含问号/感叹号（AT-24 禁项）: {snm.group(1)}')
            else:
                print(f'  ✅ 短标题备选《{snm.group(1)}》{n_s} 字（AT-25 ≤10）')

    print()
    for n in notes:
        print(f'  ℹ️ {n}')
    if must:
        print(f'❌ 字段空缺 {len(must)} 项: {must} → 回阶段 3 细纲补字段')
        sys.exit(3)
    if issues:
        print(f'⚠️ 对账差异 {len(issues)} 项 → 按提示人工复核, 结论落审稿报告')
        sys.exit(2)
    print('✅ 产物链字段与对账全过（内容主观门另见四档判定）')
    sys.exit(0)


if __name__ == '__main__':
    main()
