#!/usr/bin/env python3
"""check-metrics.py — 可测指标与注水启发式（阶段 4 写后/阶段 6 审稿辅助）

用法:
  python3 check-metrics.py <正文.md> [--fragment]

  --fragment: 片段/章级模式（与 check-length --fragment 对齐）。
    单章/短样本调用时, 全文统计型比例指标（1 对话占比 / 2 独句段 / 9 注水比例）
    降为**参考显示、不计退出码**（比例在千字级样本上波动大, 整篇口径复核才算数）;
    结构性违规（3 超长段 / 5 虚词超限 / 6 填充词起段 / 7 同主语连段 / 8 段落均匀 / 10 相邻段均质）
    是段落级绝对规则, 片段模式照常判罚（但 8/10 另有"样本<15段参考档"短样本豁免, 见下）;
    4 金句按 ≥1/千字折算（仍为参考项）。
    不带 --fragment 时保持整篇口径（全文核验必须整篇跑, 不得用片段结论充数）。

测量项与阈值（全部来自 quality-gates / style-rules，可计算者才收）:
  1 对话占比      机检带 [18%,45%]（1514 篇实测校准；甜宠/口述感目标 40-50%）  → 阶段4 写作纪律 2
  2 独句段比例    ≥30% 达标线；25-30% ⚠️ 待修、<25% ⚠️ 重点修（⚠️ 级计 exit 2；片段模式参考不计——AT-12）  → 风格约束 2
  3 超长段        叙述段 >3 句或 >100 字 = ❌ 必修；51-100 字 = ⚠️ 警示（不计退出码）；≤50 字理想，目标 0 违规
  4 金句候选      15-25 字独立成段数，全文 ≥6 句        → 金句五大必埋位
  5 虚词密度      感到/觉得/很/非常/似乎/仿佛 ≤10 处（"很"按"很X"双字词计、剔除"很多/好多"——细化口径以实现为准）
                  长文（≥8000 字）降为参考项——绝对阈值=短篇口径，长文按密度人工复核（AT-38）
  6 填充词开头    以 然后/接着/之后 起段 ≤3 处          → 风格约束 4
  7 同主语连段    连续 ≥3 段以同一人称代词起段 = 违规    → AI 检测①近似
  7b 同施事连段   段首非代词但前12字内同一代词连续≥3段 = ⚠️人工复核(不计退出码，近似口径)
                  长文（≥8000 字）降为参考项——第一人称长文常连续 3 段"我"起句（AT-38）
  8 段落均匀度    相邻段字数极差 ≤10% 的连续段 ≥4 个（AT-13）
                  → 篇章层"同一字数切段是 AI 铁证"
  9 注水信号      抽象情绪词 8 词池（绝望/痛苦/悲伤/无奈/开心/难过/愤怒/尴尬）**合计** >10 处
                  ——粗信号，词池比 check-ai AT-36 的四词宽（多开心/难过/愤怒/尴尬），故**取合计口径**；
                  判罚权威仍在 check-ai 的逐词 ≤2（AT-36），本项只作注水嫌疑预警、不计入必改
                  + 千字虚词 >8 = ⚠️注水嫌疑，对照节拍表核对
  10 相邻段均质   相邻段字数差 ≤3 字占比 ≤40%              → 篇章层反节拍器（⚠️）
  11 一称感知占比 段含"我"≥85% / 字数口径 ≈92%（参考项——AT-15；三称稿不适用）
  12 尺子0速查    平均段落句数/连续等句数段/空转情绪段占比/重复10字片段（近似参考——kill-ai 尺子 0，权威=人工计数）
  13 单句超长     >25 字句计数/句数/最长句（参考项，写作端保证）
  14 标题字数     标题（H1/首行）字数 vs AT-24（≤20 字不剧透；15 字内更佳）（参考项，不计退出码）
  15 引号类型     「」 对话引号数 vs 双/英文引号数（参考项，不计退出码）
  16 对话推进率   对话轮数 + 含信息/动作/冲突词轮占比（粗信号）——AT-19 推进率 ≥70% 为语义口径，权威=审稿六维3人工核（参考项，不计退出码）
  17 具体化率     抽象情绪词粗信号——AT-20 具体:抽象 ≥2:1 为词性语义口径，权威=审稿 B4"具体替代泛泛"人工核（参考项，不计退出码）

标注稿口径（阶段 5 双版本）：
  【X】标注符号在 clean 阶段**先剔除再计量**——标注是机检计数源不是正文,
  不剔除会让「段落均匀」「超长段」在标注稿上产生结构性假阳性（同一段被撑长 5-20 字）。
  故 04-润色标注稿.md 与 04-正文净稿.md 的段落类读数应基本一致;
  若两者差异 >1 项, 先核是否有 ★ 号/破折号等非标注符号残留。

判定与退出码（分级退出, 让 good/bad 样例可区分, 告警必须改变退出码）:
  0 = 可测指标全过; 1 = 用法错误; 2 = 仅有 ⚠️ 级待修项; 3 = 含 ❌ 级必修项
  ❌ 级（超长段/虚词超限/同主语连段/段落均匀）→ exit 3; ⚠️ 级 → exit 2。
  金句密度按 quality-gates 归**参考项**（70%-130% 浮动带, 单项不足禁凑数）, 只提醒不计待修。
  主观门（人设立得住/勾出然后呢）仍以人工与四档判定为准。
"""
import re
import sys
from pathlib import Path

DIALOG = re.compile(r'「([^」]*)」|"([^"]*)"')  # 兼容「」与""两种引号（净稿被转引号时对话占比不归零）
PARA_SPLIT = re.compile(r'\n+')  # 段落切分兼容两种排版口径（style-rules 段落间隔条）：Markdown 稿段间 1 空行、站内编辑器稿顶格单换行
ABSTRACT = ['绝望', '痛苦', '悲伤', '无奈', '开心', '难过', '愤怒', '尴尬']
FILLER_FEEL = ['感到', '觉得', '很', '非常', '似乎', '仿佛']
FILLER_OPEN = ('然后', '接着', '之后')
PRON_OPEN = ('我', '他', '她', '它')


def dialog_chars(text: str) -> int:
    return sum(count(a or b) for a, b in DIALOG.findall(text))


def clean(markdown: str) -> str:
    t = re.sub(r'^#+.*$', '', markdown, flags=re.M)      # 标题
    # 表格行剔除: markdown 表格行（| 开头 | 结尾）是排版结构不是散文段落——
    # 不剔除会把整张打分表计为 1 个超长段, 让自带打分表的报告类产物
    # （00-选题评估/06-审稿报告, 模板本身要求打分表）被超长段门误杀
    t = re.sub(r'^\s*\|.*\|\s*$', '', t, flags=re.M)
    # 标注符号剔除（阶段 5 标注稿）：【爽点+打脸】/【伏笔·埋·V1·X】/【钩子·新问题】等
    # 是机检计数源、不是正文。不剔除会把同一段的字数撑长 5-20 字,
    # 让「段落均匀」「超长段」在标注稿上产生**结构性假阳性**——
    # 实测教训: 女帝的第一天 04-润色标注稿报「超长段 1 / 段落均匀 4 连段」,
    # 而同一正文净稿为 0 / 3（净稿才是交付物）, 曾被误读为"稿子有 AI 铁证"。
    t = re.sub(r'【[^】\n]*】', '', t)
    t = re.sub(r'[#|*`>\-]', '', t)
    return t


def count(text: str) -> int:
    return len(re.sub(r'\s', '', text))


def main():
    # 显式帮助入口：-h/--help 打 docstring 退 0（无参仍退 1，保持 AT-56 用法错误口径）
    if any(a in ("-h", "--help") for a in sys.argv[1:]):
        print(__doc__ or "用法: 见脚本头部 docstring")
        sys.exit(0)
    argv = sys.argv[1:]
    fragment = '--fragment' in argv
    argv = [a for a in argv if a != '--fragment']
    if not argv:
        print(__doc__)
        sys.exit(1)
    # 参数校验：打错 --frament 会静默按整篇跑、多文件只测第一个——校验式拒绝，干净退 1
    for a in argv:
        if a.startswith('--'):
            print(f'❌ 未知参数: {a}（用法: check-metrics.py <正文.md> [--fragment]）')
            sys.exit(1)
    if len(argv) > 1:
        print(f'❌ 用法错误: 只接受一个正文文件（收到 {len(argv)} 个）')
        sys.exit(1)
    if not Path(argv[0]).is_file():
        print(f'❌ 文件不存在: {argv[0]}（用法: check-metrics.py <正文.md> [--fragment]）')
        sys.exit(1)
    raw = Path(argv[0]).read_text(encoding='utf-8-sig')
    t = clean(raw)
    # 空稿前置拦截：clean 后无内容时，下方所有比例项分母都被 max(...,1) 兜成 1，
    # 会算出「对话占比 0% / 独句段 0%」并误判为「待修」——空稿是输入错误不是质量问题，直接退 1。
    if not t.strip():
        print(f'❌ 正文为空（clean 后 0 字）: {argv[0]}——检查文件是否误传空稿或 Markdown 标记被全量剔除')
        sys.exit(1)
    total = max(count(t), 1)
    long_text = total >= 8000  # 长文宽容: 绝对计数阈值(虚词/同主语)按短篇口径设计, 万字长文降为参考项
    issues = []   # ⚠️ 级待修（exit 2）
    must = []     # ❌ 级必修（exit 3）

    # 1 对话占比（fragment: 比例型——参考显示不计退出码）
    dialog = dialog_chars(t)
    pct = dialog / total * 100
    ok = 18 <= pct <= 45
    if fragment:
        print(f'1 对话占比: {pct:.1f}%（片段口径参考值——整篇机检带 [18%,45%] 复核, 不计退出码）')
    else:
        print(f'1 对话占比: {pct:.1f}%（机检带 [18%,45%]，1514 篇实测校准，均值 25.8%；甜宠/口述感目标 40-50%）{"✅" if ok else "⚠️ 显著超/低于机检带时自查对话戏是否缺失，禁强行凑比"}')
        if not ok:
            issues.append('对话占比')

    # 分段
    paras = [p.strip() for p in PARA_SPLIT.split(t) if p.strip()]

    # 2 独句段
    def is_one_sentence(p: str) -> bool:
        # 独句段 = 段内**叙述部分**为单句（剥除对话引文后判定）；纯对话行（剥后为空）不计入独句段统计
        body = re.sub(r'(「[^」]*」|"[^"]*")', '', p).strip()
        return len(body) > 0 and (body.endswith(('。', '！', '？', '…', '”')) and
                                  body.count('。') + body.count('！') + body.count('？') <= 1)
    singles = sum(1 for p in paras if is_one_sentence(p))
    spct = singles / max(len(paras), 1) * 100
    if fragment:
        print(f'2 独句段: {spct:.1f}%（{singles}/{len(paras)}）（片段参考——整篇≥30% 复核, 不计退出码）')
    else:
        if spct >= 30:
            print(f'2 独句段: {spct:.1f}%（{singles}/{len(paras)}）✅')
        else:
            level = '⚠️ <25% 重点修' if spct < 25 else '⚠️ 25-30% 待修'
            print(f'2 独句段: {spct:.1f}%（{singles}/{len(paras)}）{level}')
            issues.append('独句段')

    # 3 超长段（三处同口径：>100 必修 / 51-100 警示 / ≤50 理想）
    long_paras = 0
    mid_paras = 0
    for p in paras:
        if DIALOG.search(p):
            # 对话段豁免：带引导语的对话段（「他把伞放在门口：『走吧。』」式）若只认
            # 「段首即引号」就会被误判 ❌ 超长段——
            # 一句台词一段本身短，且本项针对叙述段；段内含对话引文即按对话段处理，
            # 对话段的长短由对话占比带（指标 1，机检带 [18%,45%]）与「」形式门（指标 15）把控。
            continue
        sents = len([s for s in re.split(r'[。！？]', p) if s.strip()])
        # 判据：>3 句或 >100 字 = 必修；≤50 字为理想线
        if sents > 3 or count(p) > 100:
            long_paras += 1
        elif count(p) > 50:
            mid_paras += 1   # 51-100 警示区（不拒稿，但要修到 ≤50 理想线）
    print(f'3 超长段(>3句或>100字): {long_paras} 个{"✅" if long_paras == 0 else "❌ 必修"}'
          f' | 51-100字警示段: {mid_paras} 个{"✅" if mid_paras == 0 else "⚠️ 建议优化至 ≤50 理想线（不拒稿不计退出码）"}')
    if long_paras:
        must.append('超长段')

    # 4 金句候选（15-25 字独立成段，含句号）—— 参考项: quality-gates 参考口径, 不计待修、不影响退出码
    #    "该字位独立成段数"不叫"金句候选", 防短段体长文虚高读数
    #    （实测知乎真爆款 1.05 万字报 148 句）——机检无法判定"是不是金句"（语义判断）,
    #    只报字位段数; 金句以人工对照五大必埋位为准, 禁为凑整读数补金句。
    gold = sum(1 for p in paras
               if 15 <= count(p) <= 25 and p.endswith(('。', '！', '？')) and not p.startswith(('「', '"')))
    if fragment:
        gmin = max(1, round(total / 1000))
        print(f'4 金句候选: {gold} 句（片段门槛 ≥{gmin}/千字折算）——机检仅报"15-25 字独立成段数"、非金句判定, 禁为凑数补金句, 五大必埋位自然产出优先')
    else:
        print(f'4 金句候选: {gold} 句{"✅" if gold >= 6 else "⚠️ ≥6（参考项）"}——机检仅报"15-25 字独立成段数"（短段体长文天然偏多, 非金句判定）; 金句以人工对照五大必埋位为准, 禁为凑数补金句')

    # 5 虚词（降误报）："很+单字形容词"是中文程度用法（很轻/攥得很紧/日头很毒）不计；
    #    只计"很+双字词"（很孤独/很紧张=情绪替代嫌疑）及 感到/觉得/非常/似乎/仿佛；数量词"很多/好多"不计
    t_wo_q = re.sub(r'很多|好多|之多', '', t)
    feel = sum(t_wo_q.count(w) for w in FILLER_FEEL if w != '很')
    feel += len(re.findall(r'很[\u4e00-\u9fff]{2}', t_wo_q))
    if feel <= 10:
        print(f'5 虚词(感到觉得很非常似乎仿佛): {feel} 处✅')
    elif long_text:  # 长文宽容：绝对阈值=短篇口径，万字长文自然行文必超，降为参考项（见 AT-38）
        print(f'5 虚词: {feel} 处（长文口径——按密度 {feel / total * 1000:.1f}/千字 人工复核，不计退出码；'
              f'绝对阈值≤10 为短篇尺度）')
        issues.append('虚词（长文参考）')
    else:
        print(f'5 虚词(感到觉得很非常似乎仿佛): {feel} 处❌ >10（近似口径）')
        must.append('虚词超限')

    # 6 填充词起段
    open_fill = sum(1 for p in paras if p.startswith(FILLER_OPEN))
    print(f'6 然后/接着/之后起段: {open_fill} 处{"✅" if open_fill <= 3 else "⚠️ ≤3"}')
    if open_fill > 3:
        issues.append('填充词起段')

    # 7 同主语连段
    best, cur, last = 0, 0, None
    for p in paras:
        head = next((w for w in PRON_OPEN if p.startswith(w)), None)
        if head and head == last:
            cur += 1
        else:
            cur = 1 if head else 0
        last = head
        best = max(best, cur)
    if best < 3:
        print(f'7 同主语连段最长: {best}✅')
    elif long_text:  # 长文宽容：第一人称长文连续 3 段以"我"起句属自然，降为参考项（见 AT-38）
        print(f'7 同主语连段最长: {best}（长文口径——第一人称长文常见，不计退出码）')
        issues.append('同主语连段（长文参考）')
    else:
        print(f'7 同主语连段最长: {best}❌ ≥3 违规（AI 检测①近似）')
        must.append('同主语连段')

    # 7b 同施事连段(近似) —— 起段口径(#7)漏检"第一笔…他…/第二笔…他…"式段内同施事连段
    #    (语义施事连续为"他"但段首为序数词,#7 报最长1)。
    #    口径:段首非代词、但前 12 字内出现同一人称代词且连续 ≥3 段 → ⚠️ 参考项提示人工复核(不计退出码,
    #    防语义近似误报打死正常稿);遇段首代词段断开,与 #7 起段口径互补不重复。
    best2, cur2, last2 = 0, 0, None
    for p in paras:
        if next((w for w in PRON_OPEN if p.startswith(w)), None):
            cur2, last2 = 0, None
            continue
        head2 = next((w for w in PRON_OPEN if w in p[:12]), None)
        if head2 and head2 == last2:
            cur2 += 1
        else:
            cur2 = 1 if head2 else 0
        last2 = head2
        best2 = max(best2, cur2)
    if best2 >= 3:
        print(f'7b 同施事连段(前12字同代词)最长: {best2}⚠️ 近似口径,人工复核排比/递进段是否单一施事(不计退出码)')
        issues.append('同施事连段(近似)')

    # 8 段落均匀度（相邻字数近似的连续段）
    #    短样本豁免: 样本 <15 段时相邻段天然近似, 判罚产生结构性假阳性
    #    ——阈值与本脚本独句段/尺子0 及 check-ai 的"样本<15段仅整篇口径生效"先例一致；
    #    实测教训: 金标准 mini-good 标注稿（7 段微型 fixture）曾被本项 ❌ 拦在一键门外,
    #    而回归只测 check-artifacts, 门禁与金标准自相矛盾数周无人发现。
    lens = [count(p) for p in paras]
    max_sim = cur_sim = 1
    for a, b in zip(lens, lens[1:]):
        if a and abs(a - b) / max(a, b) <= 0.10:
            cur_sim += 1
            max_sim = max(max_sim, cur_sim)
        else:
            cur_sim = 1
    if len(paras) < 15:
        print(f'8 段落均匀(相邻字数差≤10%)最长连段: {max_sim}（样本<15段——参考显示, 整篇口径复核, 不计退出码）')
    else:
        print(f'8 段落均匀(相邻字数差≤10%)最长连段: {max_sim}{"✅" if max_sim < 4 else "❌ ≥4 同字数切段=AI 铁证"}')
        if max_sim >= 4:
            must.append('段落均匀')

    # 9 注水信号
    abstract = sum(t.count(w) for w in ABSTRACT)
    per1k = feel / total * 1000
    warn = abstract > 10 or per1k > 8
    if fragment:
        print(f'9 注水信号: 抽象情绪词 {abstract} 处、虚词 {per1k:.1f}/千字（片段参考——整篇口径复核, 不计退出码）')
    else:
        print(f'9 注水信号: 抽象情绪词 {abstract} 处、虚词 {per1k:.1f}/千字'
              f'{"⚠️ 注水嫌疑，对照节拍表核对" if warn else "✅"}')
        if warn:
            issues.append('注水嫌疑')

    # 10 相邻段差≤3 占比（评估实战: 487 字切 31 段、相邻差≤3 达 14/30 = 机器等分节奏,
    #    违反 style-rules"长短交错"与 kill-ai"同一字数切段是 AI 铁证"——占比维度补指标 8 连段维度的盲区）
    if len(lens) >= 4:
        all_pairs = list(zip(lens, lens[1:]))
        # 排比/递进豁免: 双段均 ≤15 字的短段对不计均质（style-rules"高潮短段强化"常刻意等长, 防误伤文学手法）
        pairs = [(a, b) for a, b in all_pairs if max(a, b) > 15] or all_pairs
        near = sum(1 for a, b in pairs if a and abs(a - b) <= 3)
        npct = near / len(pairs) * 100
        ok10 = npct <= 40
        if len(lens) < 15:
            # 短样本豁免（与指标 8 同阈值同理: 微型样本段数少, 占比天然失真）
            print(f'10 相邻段差≤3字占比: {npct:.0f}%（{near}/{len(pairs)}）（样本<15段——参考显示, 整篇口径复核, 不计退出码）')
        else:
            print(f'10 相邻段差≤3字占比: {npct:.0f}%（{near}/{len(pairs)}）{"✅" if ok10 else "⚠️ ≤40%——长短交错, 忌机器等分"}（短段排比对已豁免）')
            if not ok10:
                issues.append('相邻段均质')

    # 11 一称感知占比（参考项——"第一人称占比 92%"的可计算口径;
    #    双口径并列: 段含"我"率 vs 字数占比——92% 是字数口径, 段含率天然偏低, 不可直接比,
    #    补齐字数口径后两列对照, 消除"段含率 <85% 却拿 92% 当基准"的口径错配; 只显示不计退出码, 三称稿不适用）
    my_paras = sum(1 for p in paras if '我' in p)
    mpct = my_paras / max(len(paras), 1) * 100
    my_chars = sum(count(p) for p in paras if '我' in p)
    cpct = my_chars / total * 100
    line = (f'11 一称感知占比: 段含"我" {mpct:.0f}%（{my_paras}/{len(paras)}段）| 字数口径 {cpct:.0f}%（含"我"段落字数/全文字数）'
            f'——一称稿参考带 段含率 ≥85%、字数口径 ≈92%；参考项不计退出码; 三称稿不适用')
    if cpct < 92:
        line += '；ℹ️ 一称感知低于 92% 参考带（仅供参考、非判罚——AT-15 参考项；对话密集/三称稿天然偏低）'
    print(line)

    # 12 尺子 0 速查（kill-ai 尺子 0 六项的机检近似面, 参考项不计退出码。
    #    权威口径 = kill-ai 尺子 0 定义（人工按定义计数优先）; 此处仅提供可计算近似, 供定级参考,
    #    "以量化为准"指人工计数与主观判断冲突时以计数为准, 不以本近似行替代人工计数）
    def _sents(p):
        return len([s for s in re.split(r'[。！？]', p) if s.strip()])
    avg_sents = sum(_sents(p) for p in paras) / max(len(paras), 1)
    run, runs3 = 1, 0
    for i in range(1, len(paras)):
        if _sents(paras[i]) == _sents(paras[i - 1]) and _sents(paras[i]) >= 2:
            run += 1
        else:
            if run >= 3:
                runs3 += run
            run = 1
    if run >= 3:
        runs3 += run
    emo_words = ('感到', '觉得', '绝望', '痛苦', '悲伤', '无奈', '愤怒', '委屈', '心如')
    empty_emo = sum(1 for p in paras if any(w in p for w in emo_words) and '「' not in p) / max(len(paras), 1) * 100
    body10 = re.sub(r'\s', '', t)
    grams = {}
    for i in range(len(body10) - 9):
        g = body10[i:i + 10]
        grams[g] = grams.get(g, 0) + 1
    rep_density = sum(1 for v in grams.values() if v >= 2) / max(total, 1) * 1000
    print(f'12 尺子 0 速查（近似口径参考项, 不计退出码; 权威计数见 kill-ai 尺子 0）: '
          f'平均段落句数 {avg_sents:.1f}（轻≤3/中3-5/重>5）| 连续等句数段≥3 连段 {runs3} 处（轻≤2/中3-4/重≥5）| '
          f'空转情绪段占比 {empty_emo:.0f}%（轻≤10/中10-25/重>25）| 重复10字片段 {rep_density:.1f}/千字（轻≤1/中2-3/重≥4）')

    # 13 单句超长（风格硬规"单句≤25 字"的机检参考面；
    #    参考项不计退出码: 该硬规由写作端保证, 审稿端按本行人工拆分——对话长句与专有名词句酌情豁免）
    body_noh = re.sub(r'^#+.*$', '', t, flags=re.M)
    body_noh = re.sub(r'【[^】]*】', '', body_noh)
    sents = [s.strip() for s in re.split(r'[。！？…」]', body_noh) if re.sub(r'\s', '', s)]
    long_s = [s for s in sents if len(re.sub(r'\s', '', s)) > 25]
    mx = max((len(re.sub(r'\s', '', s)) for s in sents), default=0)
    print(f'13 单句超长: >25 字 {len(long_s)} 句（参考项不计退出码——硬规 ≤25 字由写作端保证）| 句数 {len(sents)} | 最长 {mx} 字')

    # 14 标题字数（AT-24"标题≤20 字不剧透"的实测面；参考项不计退出码）
    raw_lines = [l.strip() for l in raw.splitlines() if l.strip()]
    title = next((l[2:].strip() for l in raw_lines if l.startswith('# ')), '')
    if not title and raw_lines:
        title = re.sub(r'^#*\s*', '', raw_lines[0]).strip()
    tlen = count(title)
    print(f'14 标题字数: {tlen} 字（{title[:24]}）'
          f'{"✅" if tlen and tlen <= 20 else "⚠️ AT-24 标题应 ≤20 字（15 字内更佳）、不剧透"}'
          f'——参考项不计退出码')

    # 15 引号类型（对话须「」；参考项不计退出码）
    n_corner = raw.count('「')
    n_double = len(re.findall(r'[“”"]', raw))
    print(f'15 引号类型: 「」{n_corner} 处 | 双/英文引号 {n_double} 处'
          f'{" ✅" if n_corner and not n_double else "——对话须用「」，参考项不计退出码"}')

    # 16 对话推进率（AT-19 量化子指标——推进率≥70% 是语义判断, 机检仅给
    #    对话轮数与"信息/动作/冲突"粗信号, 权威判定 = 审稿六维 3 人工核；参考项不计退出码）
    turns = len(re.findall(r'「[^」]*」', t))
    info_turns = len(re.findall(r'「[^」]*(说|问|答|叫|骂|喊|给|拿|走|要|不要|知道|不知道|查|证据|真相|钱|协议|离|分|凭什么|为什么)[^」]*」', t))
    print(f'16 对话推进率: 对话轮 {turns} 轮 | 含信息/动作/冲突词轮 {info_turns} 轮（{info_turns / max(turns, 1) * 100:.0f}%）'
          f'——AT-19 推进率 ≥70% 为语义口径, 机检仅粗信号, 权威判定 = 审稿六维 3 人工核（潜台词/信息差）')

    # 17 具体化率（AT-20 量化子指标——具体名词+动词:抽象名词+形容词 ≥2:1,
    #    需分词词性, 零依赖脚本仅给抽象情绪词粗信号; 权威判定 = B4 去AI味"具体替代泛泛"人工核）
    abstract17 = sum(t.count(w) for w in ABSTRACT)
    print(f'17 具体化率: 抽象情绪词 {abstract17} 处（全文 {total} 字）——AT-20 具体:抽象 ≥2:1 为词性语义口径, '
          f'机检仅报抽象词粗信号, 权威判定 = 审稿 B4"具体替代泛泛"人工核（参考项不计退出码）')

    print()
    if must:
        line = f'❌ 必修 {len(must)} 项: {must}'
        if issues:
            line += f' + ⚠️ 待修 {len(issues)} 项: {issues}'
        print(line + ' → 回阶段 4/5 按对应条目定向修（必修级, 不修不过门；禁注水式修改）')
        sys.exit(3)
    if issues:
        print(f'⚠️ 待修 {len(issues)} 项: {issues} → 回阶段 4/5 按对应条目定向修（禁注水式修改）')
        sys.exit(2)
    print('✅ 可测指标全过（主观门另见四档判定；金句密度为参考项另见第 4 行）')
    sys.exit(0)


if __name__ == '__main__':
    main()
