#!/usr/bin/env python3
"""check-length.py — 盐选七步法 字数与章门核验（阶段 4 写后即测）

用法:
  python3 check-length.py <正文.md> [--paywall "卡点锚句"] [--first-twist "首次反转锚句"] [--target 12000] [--intro "导语结束锚句"] [--fragment]

口径（唯一标准）: 字数 = 中文字符 + 标点（不含空白与 Markdown 标记）。
分章标记: 规范 = 纯数字独立成行（1/2/3，不带点/括号等任何符号，style-rules 章节标题条）；识别端兼容 "## N." / "【N】" / "N." 三种带符号写法与纯数字行。
导语边界: 缺省取第 1 个章节标记之前；--intro 显式指定导语结束锚句（优先）。
末章与尾声: 分章正则只在数字标记处切分，末个分块 = 末章正文(+尾声) 混合体——
  末块内行首「尾声」标签（容忍 # 前缀/【】/：。装饰，标签后可跟内容）命中 → 拆为「末章+尾声」两块分别过门
  （末章走章门 1800-3500 ❌ 级；尾声走 AT-07 投稿必填门 50-500 字，⚠️ 级不计退出码）；
  无标签 → 末块整体走章门，并 ⚠️ 提示「未识别到尾声块（AT-07 投稿必填）」。
首次反转定位: --first-twist "锚句" 给出黄金三章第 3 章首次反转的正文锚句；与 --paywall
  同时给定时核对相对位置——首次反转必须早于主付费墙（卡点前兑现），反转晚于卡点 = ❌。
口径声明（盐选单口径）: --platform salt|zhihu|yan 三入参映射**同一**付费墙口径（zhihu/yan 为别称）——
  盐选唯一口径 = 免费区 3000-4000 字（AT-04）/ 首锁占比 25-35%（AT-05；短篇付费卡点公认最佳区间）；
  平台口径（AT-26）：知乎/盐言/盐选同属一个平台，不存在第二套字数占比口径；
  --midpoint "锚句" 机检中卡点 45-55%（AT-10，⚠️ 级）。
卡后钩子密度: --paywall 给定且正文含【钩子+留白】/【悬念+反转】标注时，额外统计
  "卡点后 300 字内钩子数"（AT-18：≥3 优秀/2 良好/1 合格/0 不合格，参考项不计退出码）。
  建议在 05-标注稿上跑（标注即计数源，净稿无标注则提示改跑标注稿或人工核）。

退出码（❌ 必须改变退出码, 否则自动化门禁形同虚设；语义对齐 AT-56: 2=⚠️ 级待修, 3=❌ 级必修）:
  0 = 达标或仅 ⚠️ 提示; 1 = 用法错误; 3 = 有 ❌ 级问题
  ❌ 级 = 低于 12000 或高于 16000（AT-01 篇幅带） / 章门未过 / 付费墙锚句缺失或字位偏离 / 首次反转锚句缺失或晚于付费墙。
  （本脚本无"⚠️ 改变退出码"档——⚠️ 项仅提示不改码，故不产出 2；跨脚本以 check-all "任一非 0=修完再交"聚合为准。）
  --fragment: 片段模式（评估片段/单章测试/阶段4 写后即测的章级调用）——
  跳过全文硬线与章门 ❌ 判定（降为提示），只报分章字数与付费墙字位；整篇完稿核验禁用本开关。
"""
import re
import sys
from pathlib import Path

# 末块内行首「尾声」标签：容忍 markdown # 前缀/【】/：。装饰，
# 标签后可跟内容（如「尾声：雨停了」）；「尾声」后紧跟汉字（「尾声终究会来」式行首措辞）
# 不误判为标签——标签独占行或后接标点两种形态才认。
ENDING_LABEL = re.compile(r'^\s*(?:#{1,6}\s*)?【?\s*尾声\s*】?\s*(?:[:：。.，,、;；!！?？].*)?$', re.M)


def count(text: str) -> int:
    # 先剔除 markdown 结构行（标题/引用块/表格），再计"汉字+标点"——
    # 若只剔符号不剔整行，标题文字与引用说明会被计入导语/正文导致误报超限；
    # 口径与 check-metrics.clean() 对齐。
    t = re.sub(r'^\s*#+.*$', '', text, flags=re.M)
    t = re.sub(r'^\s*>.*$', '', t, flags=re.M)
    t = re.sub(r'^\s*\|.*\|\s*$', '', t, flags=re.M)
    # 体裁标签行剔除：「【古言爽文】」这类首行类型标签是产物元信息不是正文，
    # 全文与分块都不该计入字数（实测 6 字计入的偏差虽小，但标称字数必须等于报文口径）。
    # 只剔「整行就是单个短括号标签」的形态，不剔正文内的标注符号（那是标注稿，另属 check-metrics）。
    t = re.sub(r'^\s*【[^】\n]{1,10}】\s*$', '', t, flags=re.M)
    t = re.sub(r'\s', '', t)
    t = re.sub(r'[#|*`>-]', '', t)
    return len(t)


def take_n(text: str, n: int) -> str:
    """从 text 开头按 count 口径截取约 n 个有效字符（非空白、非 markdown 符号）——供
    卡后钩子窗口计数用（近似口径：不整行剔除结构行，参考项不追求精确）。"""
    acc, cnt = [], 0
    for ch in text:
        acc.append(ch)
        if ch not in '\t\n\r #|*`>-':
            cnt += 1
        if cnt >= n:
            break
    return ''.join(acc)


def chapter_flag(c: int, fragment: bool) -> tuple:
    """章门判定（1800-3500 ❌ 级）——末章/中间章共用，禁两处各写一遍
    原实现里「末块无尾声标签」与「中间章」两个分支的判定代码逐字重复，改一处忘另一处
    就会两口径漂移。返回 (flag, is_bad)。"""
    flag = '✅' if 1800 <= c <= 3500 else ('❌低于章门1800' if c < 1800 else '❌超上限3500')
    if 2800 < c <= 3500:
        flag += '（情绪拉扯档区间，非标准档 1800-2800，需在细纲注明）'
    if flag.startswith('❌'):
        if fragment:
            flag = flag.replace('❌', '提示(片段模式不计):')
            return flag, False
        return flag, True
    return flag, False


def main():
    # 显式帮助入口：-h/--help 打 docstring 退 0（无参仍退 1，保持 AT-56 用法错误口径）
    if any(a in ("-h", "--help") for a in sys.argv[1:]):
        print(__doc__ or "用法: 见脚本头部 docstring")
        sys.exit(0)
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    # 参数解析（校验式）：裸 args[index+1] 取值会在缺值时静默错位或 IndexError——
    # 尾随 flag 崩 IndexError、--target 非数字崩 ValueError、未知 flag 静默忽略致按错误
    # 模式跑（打错 --frament 会当整篇判）——三类违「边界输入不崩」铁律，现统一干净退 1
    flag_with_value = {'--paywall', '--first-twist', '--intro', '--target', '--platform', '--midpoint'}
    known_flags = flag_with_value | {'--fragment'}
    USAGE = ('用法: check-length.py <正文.md> [--fragment] [--paywall "锚句"] [--first-twist "锚句"] '
             '[--intro "锚句"] [--midpoint "锚句"] [--target N] [--platform salt|zhihu|yan]')
    positional, values, fragment = [], {}, False
    i = 0
    while i < len(args):
        a = args[i]
        if a.startswith('--'):
            if a not in known_flags:
                print(f'❌ 未知参数: {a}\n{USAGE}')
                sys.exit(1)
            if a == '--fragment':
                fragment = True
            else:
                if i + 1 >= len(args) or args[i + 1].startswith('--'):
                    print(f'❌ 参数 {a} 缺少取值（取值须紧跟 flag 之后）\n{USAGE}')
                    sys.exit(1)
                values[a] = args[i + 1]
                i += 1
        else:
            positional.append(a)
        i += 1
    if not positional:
        print('❌ 用法错误: 未指定正文文件（开关写在文件之后）\n')
        print(__doc__)
        sys.exit(1)
    if len(positional) > 1:
        print(f'❌ 用法错误: 只接受一个正文文件（收到 {len(positional)} 个）\n{USAGE}')
        sys.exit(1)
    path = Path(positional[0])
    paywall = values.get('--paywall')
    first_twist = values.get('--first-twist')
    intro_anchor = values.get('--intro')
    midpoint_anchor = values.get('--midpoint')
    platform = values.get('--platform', 'salt')
    if platform not in ('zhihu', 'yan', 'salt'):
        print(f'❌ 未知平台口径: {platform}（--platform 取 salt / zhihu / yan——zhihu/yan 为兼容入参, 三者映射同一盐选口径, AT-26）')
        sys.exit(1)
    platform = 'salt'  # 盐选单口径：zhihu/yan 为同一平台的别称，统一折算
    target = 12000
    if '--target' in values:
        try:
            target = int(values['--target'])
        except ValueError:
            print(f'❌ --target 须为整数（收到: {values["--target"]}）\n{USAGE}')
            sys.exit(1)

    if not path.is_file():
        print(f'❌ 文件不存在: {path}（用法: check-length.py <正文.md> [--fragment] [--paywall "锚句"] [--first-twist "锚句"]）')
        sys.exit(1)
    t = path.read_text(encoding='utf-8-sig')
    total = count(t)
    # 空稿前置拦截：clean 后 0 字时下方所有判定都失真——「低于 AT-01 篇幅带
    # 差 12000 字」会把输入错误报成质量问题，且 pct=pos/total 有除零风险。与
    # check-metrics/check-ai/check-mss 同口径：空稿 = 输入无效，退 1（AT-56）。
    if total == 0:
        print(f'❌ 正文为空（clean 后 0 字）: {path}——检查文件是否误传空稿或 Markdown 标记被全量剔除')
        sys.exit(1)
    print(f'全文: {total} 字（口径: 汉字+标点）')

    # 章节标记：规范=纯数字独立成行（1/2/3，不带点/括号等符号）；识别端兼容带符号写法
    # "## N." / "【N】" / "N." / 纯数字行四种（兼容纯数字行——旧稿与平台真爆款不误判）。
    secs = re.split(r'^(?:##\s*\d+\.?|【\d+】|\d+\.|\d+)$', t, flags=re.M)
    # 末块拆分：模板（templates/README.md）规定 03-正文 = 导语 + 纯数字章 1..N + 无标记尾声块
    # （AT-07 投稿必填 50-500 字），但分章正则只在数字标记处切分——末块 = 末章(+尾声) 混合体。
    # 若把末块无条件当尾声判 50-500，末章的章门 ❌ 会被 ⚠️ 掩盖、也查不出末章超上限，
    # 尾声门本身反而判不准。故：末块内行首「尾声」标签命中 → 拆为「末章+尾声」
    # 两块分别过门；无标签 → 末块整体走章门并提示补尾声（⚠️ 不计退出码）。
    nsec = len(secs)
    has_ending = False
    if nsec > 3:
        em = ENDING_LABEL.search(secs[-1])
        if em:
            secs = secs[:-1] + [secs[-1][:em.start()], secs[-1][em.start():]]
            has_ending = True
    names = ['导语/起始'] + [f'第{i}章' for i in range(1, len(secs))]
    if has_ending:
        names[-1] = '尾声'
    bad = []
    for n, s in zip(names, secs):
        c = count(s)
        if n == names[0]:
            if fragment and len(secs) == 1:
                print(f'  {n}: {c} 字 ℹ️ 片段模式免导语判定（无章节标记——单测导语用非片段模式或 --intro 锚句显式指定）')
                continue
            if len(secs) == 1 and c > 400:
                print(f'  {n}: {c} 字 ⚠️ 未识别到章节标记（规范=纯数字独立成行 1/2/3，不带符号；识别兼容 ## N. /【N】/ N. 三种带符号写法），导语判定跳过——可用 --intro 锚句指定导语结束位置')
                continue
            if intro_anchor:
                k = s.find(intro_anchor)
                if k >= 0:
                    c = count(s[:k + len(intro_anchor)])
                    flag = '✅' if 80 <= c <= 150 else '⚠️导语应 80-150（黄金 100-150，严口径）'
                    _intro_txt = s[:k + len(intro_anchor)]
                else:
                    # 锚句缺失禁静默按整块计数——那会输出误导性「导语 N 字 ⚠️」（内容问题假象），
                    # 与 --paywall/--first-twist 锚句缺失同口径：显式 ❌ 并入未过项
                    print(f'❌ 未找到导语锚句: {intro_anchor[:20]}…（锚句须与正文逐字一致；导语字位判定失效）')
                    bad.append('导语锚句缺失')
                    flag = '❌导语锚句缺失'
                    _intro_txt = ''
            else:
                flag = '✅' if 80 <= c <= 150 else '⚠️导语应 80-150（黄金 100-150，严口径）'
                _intro_txt = s
            # 导语首句钩子近似硬检——导语以身份/背景
            #    陈述句开头("我是…值班员")、冲突迟至第2句,纯字数门拦不住。
            #    口径:前 30 字命中疑问/转折/危机冲突/异常事件信号词任一 → 静默;无任何信号 →
            #    ⚠️ 后缀提示人工复核"首句是否身份/背景陈述句",不计退出码(语义近似,防误报打死)。
            _head30 = re.sub(r'\s', '', _intro_txt)[:30]
            _sig = ('？', '?', '怎么', '为什么', '难道', '竟然', '居然', '突然', '却发现', '却在', '不料',
                    '死', '离婚', '分手', '开除', '破产', '被抓', '报警', '抢救', '手术', '病危',
                    '消失', '失踪', '背叛', '辞退', '坠楼', '起诉', '查封', '第一', '刚刚', '竟被', '被甩', '被裁')
            if _head30 and not any(w in _head30 for w in _sig):
                flag += ' ⚠️首30字未见冲突/悬念信号词——人工复核首句是否身份/背景陈述句'
        elif n == '尾声':
            # 尾声块门（AT-07 投稿必填 50-500 字）——独立分支；⚠️ 级不计退出码
            flag = '✅' if 50 <= c <= 500 else '⚠️尾声应 50-500 字（AT-07 投稿必填；模板缺省 50-150）'
        elif n == names[-1] and nsec > 3:
            # 末章（未识别到尾声标签）：末块整体走章门，与中间章同门；
            # 另 ⚠️ 提示补尾声块（不计退出码）。
            flag, is_bad = chapter_flag(c, fragment)
            if is_bad:
                bad.append(n)
            flag += '；⚠️未识别到尾声块（AT-07 投稿必填：末章后另起一行以「尾声」标签起头写 50-500 字收束，模板缺省 50-150）'
        else:
            flag, is_bad = chapter_flag(c, fragment)
            if is_bad:
                bad.append(n)
        print(f'  {n}: {c} 字 {flag}')

    if total < 12000:
        if fragment:
            print(f'ℹ️ 低于 AT-01 篇幅带下限 12000 字（片段模式不计, 整篇完稿禁用 --fragment）')
        else:
            print(f'❌ 低于 AT-01 篇幅带 12000-16000，差 {12000 - total} 字')
            bad.append('全文<12000')
    elif total > 16000 and not fragment:
        print(f'❌ 高于 AT-01 篇幅带上限 16000，超 {total - 16000} 字')
        bad.append('全文>16000')
    elif total > 16000:
        print(f'ℹ️ 高于 AT-01 篇幅带上限 16000（片段模式不计）')
    elif total < target:
        print(f'⚠️ 低于目标 {target}（篇幅带已过）')
    else:
        print('✅ 字数达标')

    paywall_pos = None
    if paywall:
        idx = t.find(paywall)
        if idx < 0:
            print(f'❌ 未找到付费墙锚句: {paywall[:20]}…（锚句丢失=完稿字位复核失效）')
            bad.append('付费墙锚句缺失')
        else:
            pos = count(t[:idx])
            paywall_pos = pos
            pct = pos / total * 100
            ok = 3000 <= pos <= 4000 or 25 <= pct <= 35
            band = '盐选 3000-4000 字 / 25-35% 带'
            print(f'付费墙字位: 第 {pos} 字（{pct:.1f}%）{"✅ 在带内" if ok else "❌ 偏离 " + band}（口径 盐选单口径）')
            if not ok and not fragment:
                bad.append('付费墙字位偏离')
            # 卡后钩子密度（AT-18）——付费墙锚句后 300 字窗口内钩子标注计数
            # 计数兼容四类类型后缀【钩子·新问题/新信息/情绪转折/危险升级】与【钩子+留白】简化写法
            hook_pat = re.compile(r'【钩子[^】]*】|【悬念\+反转】')
            hook_marks = len(hook_pat.findall(t))
            if hook_marks:
                seg = take_n(t[idx + len(paywall):], 300)
                n_hooks = len(hook_pat.findall(seg))
                grade = '≥3 优秀' if n_hooks >= 3 else ('2 良好' if n_hooks == 2 else ('1 合格' if n_hooks == 1 else '0 不合格'))
                print(f'卡后钩子密度（AT-18）: 卡点后 300 字内钩子标注 {n_hooks} 个 → {grade}（口径=【钩子·X】四类/【钩子+留白】+【悬念+反转】；参考项不计退出码，在标注稿上跑更准）')
            else:
                print('卡后钩子密度（AT-18）: 正文无章末钩/悬念标注，无法机检——改在 05-标注稿上跑，或审稿人工核')
            # C11 卡点三连击核对窗口（AT-18 备注口径，人工核参考项不计退出码）——卡前 200 字情绪峰值 / 卡点认知颠覆 / 卡后 200 字反转，三连击缺一效果减半
            pre200 = take_n(t[:idx][::-1], 200)[::-1].replace('\n', ' ')
            post200 = take_n(t[idx + len(paywall):], 200).replace('\n', ' ')
            print('C11 卡点三连击核对（人工核）: 卡前 200 字情绪是否到顶 / 卡点句是否认知颠覆 / 卡后 200 字是否紧跟反转')
            print(f'  卡前 200 字: …{pre200}')
            print(f'  卡点锚句: {paywall}')
            print(f'  卡后 200 字: {post200}…')
    if first_twist:
        idx = t.find(first_twist)
        if idx < 0:
            print(f'❌ 未找到首次反转锚句: {first_twist[:20]}…（黄金三章第 3 章反转定位失效）')
            bad.append('首次反转锚句缺失')
        else:
            tp = count(t[:idx])
            print(f'首次反转字位: 第 {tp} 字')
            if paywall_pos is not None and tp > paywall_pos:
                print(f'❌ 首次反转（第 {tp} 字）晚于付费墙（第 {paywall_pos} 字）——黄金三章第 3 章反转必须落在卡点前兑现（细纲质量门: 反转章累计预估字数 < 付费墙字位）')
                bad.append('首次反转晚于付费墙')
            elif paywall_pos is not None:
                print(f'✅ 首次反转早于付费墙 {paywall_pos - tp} 字（卡点前兑现）')
    if midpoint_anchor:
        idx = t.find(midpoint_anchor)
        if idx < 0:
            print(f'⚠️ 未找到中卡点锚句: {midpoint_anchor[:20]}…（中卡点字位人工核对）')
        else:
            mp = count(t[:idx])
            m_pct = mp / max(total, 1) * 100
            m_ok = 45 <= m_pct <= 55
            print(f'中卡点字位: 第 {mp} 字（{m_pct:.1f}%）{"✅ 在 45-55% 带内" if m_ok else "⚠️ 偏离中卡点 45-55% 带（AT-10，⚠️ 级人工复核）"}')
    if fragment and (paywall or midpoint_anchor):
        print('ℹ️ 片段模式：付费墙/中卡点的绝对字位偏离仅提示、不计退出码（"首次反转早于付费墙"相对位置仍计）——整篇完稿核验禁用 --fragment')
    if bad:
        print(f'❌ 未过项: {bad} → 按章补"动作-反应回合+感官+对话"，禁注水')
        sys.exit(3)
    sys.exit(0)


if __name__ == '__main__':
    main()
