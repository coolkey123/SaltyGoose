#!/usr/bin/env python3
"""check-ai.py — 去AI味六合一速扫（阶段 5 工序 A 诊断用）

用法:
  python3 check-ai.py <正文.md>

覆盖 kill-ai.md 六合一速扫的可量化部分: 破壁词 / 黑名单 / 情绪抽象词 / 解释句追述 / 句式波动。
输出缺陷清单（位置可 grep 定位），供 Step 2 定级分流。阈值见 kill-ai 附录 B。

退出码（告警必须改变退出码, 否则自动化门禁形同虚设）:
  0 = 无必改项（可进 Step 3 改写）; 1 = 用法错误; 2 = 有必改候选
  必改候选 = 破壁词超阈 / 破壁词密度>0.5 / 黑名单命中 / 情绪词超阈 / 解释句超阈 / 弱化副词超阈（AT-37）。
  原"禁用标点"条款参考项化——……/—— 实测 97.8%/68.3% 盐选作品在用（非平台禁令），
        改为仅提示"叙述层避免扎堆"、不再计入必改候选（不阻断交付）。
  人味句豁免权在 Step 2 人工定级, 不在脚本层 —— 脚本只负责"抓出来并挡住"。
  三档输出口径（防"有⚠️却 exit 0"被误读为脚本漏判）:
    ❌+problems → 必改候选, exit 2 ‖ ⚠️+阈内清单 → 人工定级区, exit 0（末尾单列"阈内待人工定级 N 词"）
    ‖ ℹ️+灰名单 → 观察项, exit 0
两处判别力设计要点:
  - 短样本假阴性: 样本 <800 字自动进"短样本严格档"——情绪/解释词与**破壁词**命中即入
    必改候选（阈值按整篇口径设计, 短文本按次计数会漏掉"抽象情绪词直给"与高频破壁词
    这类典型 AI 味——例: "她心中充满了无尽的悲伤"与 2 处"忽然"必须被抓出）。
  - 子串误报: "十分"仅在非数字前缀语境计数（"四十分钟/考了一百分"是时间/分数,
    不是程度副词, 不应计入）。
"""
import collections
import re
import sys
from pathlib import Path

BIPO = {'忽然': 8, '突然': 8, '瞬间': 8, '因此': 10, '所以': 10, '因而': 10,
        '然而': 25, '可是': 8, '非常': 8, '十分': 8, '不禁': 5, '忍不住': 5,
        '原来': 8, '其实': 8, '终于': 6, '终究': 6, '毕竟': 6,
        '就像': 10, '仿佛': 10, '如同': 10}
# 黑名单分两级:
#   BLACKLIST_HARD = 高置信 AI 腔 —— 命中即入"必改候选"、计入退出码（problems → exit 2）
#   BLACKLIST_SOFT = 灰名单：真人亦常用、需语境定级 —— 仅提示、**不计退出码**，逐处人工定级
#   动机：把'空气凝固'等真人常用表达无条件判 exit 2 会误伤真爆款
#   （效果边界声明已强调机检是下限护栏、不是创作目标；误伤真作品 = 诱导无效修改）。
BLACKLIST_HARD = ['眼中闪过', '深吸一口气', '那一刻意识到', '心中涌起',
                  '沉声道', '淡淡地说', '嘴角微扬', '目光如炬', '心中暗道',
                  '不难看出', '由此可见', '综上所述',
                  '指尖泛白', '手心发凉']
BLACKLIST_SOFT = ['映入眼帘', '不由自主', '空气凝固', '心跳轰鸣',
                  '手忙脚乱', '一丝笑意', '一丝痛苦']
EMOTION = {'绝望': 2, '痛苦': 2, '悲伤': 2, '无奈': 2, '心如刀割': 0, '五雷轰顶': 0, '心如死灰': 0}  # 前组=直给级(≤2)，后组=陈词滥调级(0)——两级两线见 authority-table.md AT-36
EXPLAIN = {'这说明': 3, '也就是说': 3, '意思是': 3, '意味着': 3}
WEAK = {'微微': 3, '淡淡': 3, '缓缓': 3, '轻轻': 3}  # 近似口径：权威阈=每千字>3（authority-table.md AT-37）；本脚本以绝对次数>3 近似（单章/短样本），整篇核验按密度

_NUM_BEFORE = r'[0-9〇零一二两三四五六七八九十百千万亿]'


def count_word(body: str, w: str) -> int:
    """带语境边界的有效计数：消除子串误报。"""
    if w == '十分':
        # 数字+十分 = 时间/分数语境（"四十分钟"），非程度副词，不计
        return len(re.findall(rf'(?<!{_NUM_BEFORE})十分', body))
    return body.count(w)


def nospace_len(text: str) -> int:
    return len(re.sub(r'\s', '', text))


def main():
    # 显式帮助入口：-h/--help 打 docstring 退 0（无参仍退 1，保持 AT-56 用法错误口径）
    if any(a in ("-h", "--help") for a in sys.argv[1:]):
        print(__doc__ or "用法: 见脚本头部 docstring")
        sys.exit(0)
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    if len(sys.argv) > 2:
        print(f'❌ 用法错误: 只接受一个正文文件（收到 {len(sys.argv) - 1} 个）')
        sys.exit(1)
    p = Path(sys.argv[1])
    if not p.is_file():
        print(f'❌ 文件不存在: {sys.argv[1]}（用法: check-ai.py <正文.md>）')
        sys.exit(1)
    t = p.read_text(encoding='utf-8-sig')
    # 首行 H1 标题不计正文；全文仅一行标题（无换行）时 find 返回 -1，
    # 禁按 t[-1:] 切——尾字符会冒充正文绕过下方空稿拦截
    if t.startswith('#'):
        k = t.find('\n')
        body = t[k:] if k >= 0 else ''
    else:
        body = t
    # 空稿前置拦截：空正文下所有命中计数恒为 0 → 判「无 AI 味」exit 0，
    # 等于给空稿发通行证。空稿是输入错误，须退 1 与 check-metrics 同口径。
    if nospace_len(body) == 0:
        print(f'❌ 正文为空: {sys.argv[1]}——check-ai 无法评估空稿（先补齐正文再跑）')
        sys.exit(1)
    problems = []
    within_thresh = []  # 阈内命中（人工定级区）——不计退出码，但须显式汇总，防"有⚠️却 exit 0"被误读
    short_sample = nospace_len(body) < 800  # 短样本严格档（见 docstring）

    print('=== 破壁词（次数/阈值）===')
    for w, th in BIPO.items():
        n = count_word(body, w)
        if short_sample and n:
            # 补漏：短样本下密度失真不计、按次阈值又够不着，会形成判罚真空——命中即报
            problems.append(f'破壁词命中(短样本严格档): {w} {n} 处')
            print(f'  ⚠️ {w}: {n}（短样本严格档命中即报——整篇阈{th}，人味句 Step 2 可豁免）')
        elif n > th:
            problems.append(f'破壁词超阈: {w} {n}>{th}')
            print(f'  ⚠️ {w}: {n}（阈{th}）')
        elif n:
            print(f'  {w}: {n}（阈{th}）')
    dens = sum(count_word(body, w) for w in BIPO) / max(nospace_len(body), 1) * 100
    if short_sample:
        # 密度是整篇口径指标：16 字样本 1 个词即 6/100字，失真严重——短样本只看按次严格档
        print(f'  破壁词密度: {dens:.2f}/100字（短样本密度失真, 仅显示不计——判罚见情绪/解释词严格档）')
    elif dens > 0.5:
        problems.append(f'破壁词密度超阈: {dens:.2f}>0.5/100字')
        print(f'  破壁词密度: {dens:.2f}/100字（阈≤0.5）⚠️')
    else:
        print(f'  破壁词密度: {dens:.2f}/100字（阈≤0.5）✅')

    print('=== 黑名单（高置信 AI 腔——命中即必改候选）===')
    hits = 0
    for w in BLACKLIST_HARD:
        n = count_word(body, w)
        if n:
            hits += n
            problems.append(f'黑名单命中: {w} {n} 处')
            print(f'  ⚠️ {w}: {n} 处（必改候选——逐处人工定级: 真AI腔改, 人味句可豁免）')
    soft_hits = 0
    for w in BLACKLIST_SOFT:
        n = count_word(body, w)
        if n:
            soft_hits += n
            print(f'  ℹ️ {w}: {n} 处（灰名单观察项——真人亦常用, 逐处人工定级; 不计退出码, 防误伤真作品）')
    if short_sample:
        print('=== 情绪/解释词（短样本严格档: <800 字, 命中即报）===')
        for w, th in list(EMOTION.items()) + list(EXPLAIN.items()):
            n = count_word(body, w)
            if n:
                hits += n
                problems.append(f'情绪/解释词命中(短样本严格档): {w} {n} 处')
                print(f'  ⚠️ {w}: {n} 处（抽象情绪词直给/解释句——短文本中即 AI 味信号, 整篇口径阈{th}）')
    else:
        for w, th in list(EMOTION.items()) + list(EXPLAIN.items()):
            n = count_word(body, w)
            if n > th:
                hits += n
                problems.append(f'情绪/解释词超阈: {w} {n}>{th}')
                print(f'  ⚠️ {w}: {n}（阈{th}）')
            elif n:
                # 阈内命中也算「命中」——计入 hits（供下文"零命中"判定与汇总显示用），
                # 但**不进 problems**：AT-36 判罚链是"超阈才入必改候选"，阈内属人工定级区。
                # hits 与 problems 分工：hits=命中总量（含阈内），problems=必改候选（仅超阈）。
                hits += n
                within_thresh.append(f'{w}×{n}')
                print(f'  ⚠️ {w}: {n} 处（阈{th}内, 逐处人工判断：真AI腔改，人味句留）')
    if within_thresh:
        # 阈内条目单列汇总：防止执行者把"有 ⚠️ 输出但 exit 0"误读成脚本漏判
        print(f'  ℹ️ 阈内待人工定级 {len(within_thresh)} 词: {"、".join(within_thresh)}'
              f'（不计退出码——AT-36 判罚链只对超阈项生效）')
    if not hits and not soft_hits:
        print('  ✅ 零命中')

    print('=== 标点提示（…… / —— 可节制使用, 非禁用——仅提示不阻断）===')
    ell, dash = body.count('……'), body.count('——')
    if ell or dash:
        print(f'  ℹ️ …… {ell} 处 / —— {dash} 处（允许；叙述层避免扎堆，情绪峰值段/对话段可留'
              f'——原"禁用标点"条款参考项化, 不计必改）')
    else:
        print('  ✅ 零命中')

    print('=== 弱化副词扎堆（AT-37 必删级——命中入必改候选） ===')
    for w, th in WEAK.items():
        n = body.count(w)
        if n > th:
            problems.append(f'弱化副词 {w}×{n}')
            print(f'  ⚠️ {w}: {n}（阈{th}）——必删到 {th} 次内（AT-37）')

    print('=== 句式波动 ===')
    paras = [p.strip() for p in body.split('\n') if p.strip() and not p.startswith('#')]
    lens = [len(re.sub(r'\s', '', p)) for p in paras]
    if lens:
        print(f'  段落 {len(paras)} 个 | 长度 min{min(lens)} max{max(lens)} avg{sum(lens)//len(lens)}')
    else:
        print('  段落 0 个（空稿或纯结构行——句式波动指标跳过）')
    short = len([x for x in lens if x <= 5])
    if len(paras) < 15:
        print(f'  ≤5字独句段: {short}（样本<15段, 该指标仅整篇口径生效, 本样本不计）')
    else:
        print(f'  ≤5字独句段: {short}（需≥3）{"⚠️" if short < 3 else "✅"}')
    heads = collections.Counter(p[0] for p in paras if len(p) > 1)
    print(f'  段首字 TOP3: {heads.most_common(3)}（连续3段同开头需抽查）')
    if len(lens) < 3:
        print('  等长嫌疑: 样本段落<3, 跳过')
    else:
        even = all(abs(a - b) <= 3 for a, b in zip(lens, lens[1:10]))
        print(f'  前10段等长嫌疑: {"⚠️ 需长短交错" if even else "✅ 波动正常"}')

    print('=== 定级建议 ===')
    print(f'  必改候选 {len(problems)} 条: {problems if problems else "无"}')
    print('  人味保护提醒: "不是X。是Y。"式人物判断句、情绪直给句、章尾金句 → 保护不动')
    sys.exit(2 if problems else 0)


if __name__ == '__main__':
    main()
