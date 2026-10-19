#!/usr/bin/env python3
"""run-tests.py — 盐选七步法脚本回归测试（金标准样例对拍）

用法: python3 tests/run-tests.py   （退出码 0=全过, 1=回归失败）

七步法产物链（单文件两篇设计，02-细纲.md 为合并产物）:
  00-选题评估.md / 01-梗概.md / 02-细纲.md / 03-正文.md /
  04-润色标注稿.md + 04-正文净稿.md / 05-审稿报告.md / 06-投稿包/ / 07-复盘.md / 08-结构指纹.md

样例:
  tests/good-sample.md  规范样例：全部必修/待修指标必须清零（exit 0）—— 防止脚本误杀好稿
  tests/bad-sample.md   违规样例：必须触发 ≥5 项且 metrics exit 3、check-ai exit 2
                        —— 防止脚本失去判别力

覆盖范围（测量脚本全进回归；metrics --fragment 双模式；check-artifacts
产物机检；G 项靶点密度/章末钩正向回归 + check-length --first-twist 双锚句
正反例；MSS 机检结构分（F/B/T/D/R 五模块 + 12 硬门）正反对拍；七步法命名
锚点锁定防旧名回流；边界用例回归——空稿/纯空白/畸形 CSV/无参用法错误/
不存在文件/BOM 计数偏差，断言不崩且退出码语义正确（AT-56））:
  1 check-metrics.py   good exit 0 / bad exit 3（分级: ❌级=3, ⚠️级=2, 全过=0）
                       + --fragment 双模式: good=0 / bad=3（比例参考、结构照判）
                       + B2 对话段豁免: 带引导语长对话段豁免、纯叙述长段照判（段内含引文即豁免）
  2 check-ai.py        good exit 0 / bad exit 2（黑名单/密度/禁用标点必改；
                       <800 字短样本严格档: 情绪/解释词/破壁词命中即报）
  3 check-length.py    片段模式 good/bad exit 0；整篇 good exit 3（验证 ❌ 生效，AT-56）
                       + --first-twist 双锚句: 反转早于付费墙 exit 0 / 晚于 exit 2
                       + --intro 锚句双态: 存在照旧判 80-150 ✅ / 缺失显式 ❌ 退 3
                       （禁静默按整块计数输出误导性「导语 N 字 ⚠️」）
                       + 付费墙占比带锁定: 偏离时输出须点名 25-35% 带（AT-05）
                       + 末章/尾声三态: 带尾声合规 exit 0 / 末章<1800 exit 3 / 无尾声 exit 0+提示（B1）
                       + 篇幅带边界: 12001 字照过 / 16021 字 exit 3 且点名 AT-01 上限（AT-01 闭区间）
                       + --midpoint 中卡点: 锚句命中报字位+百分比 / 缺失显式提示；--platform 三别名 / 未知值退 1
  4 check-consistency.py  exit 0（全量断言锁定，组数以脚本输出为准）
  5 check-artifacts.py mini-good exit 0 / mini-bad exit 3 + mini-annot G 项正向
                       （靶点密度实测、章末钩全在位）
  6 check-all.py      mini-good exit 0 / mini-bad 非 0（一键全量门必须放行金标准、
                       拦住坏样例——回归只测分项不测聚合门, 金标准曾被一键门误杀）
  7 check-mss.py      mss-good exit 0 且 MSS≥80 / mss-bad exit 2 且 59 封顶 ≥5 硬门
                       + 分节格式硬门锁定：只认纯数字独立成行，「N.」带点式必触硬门且被点名
                       + --person 3rd 一称返还禁白送（未扣分时禁 +2，F=30 不超权重）
                       （MSS 机检结构分正反对拍，防五模块权重漂移）
  8 check-fingerprint.py 同型对 exit 2 / 差异对 exit 0 + 同名目录禁静默丢篇
                       （两篇同名目录同型指纹，第二篇被吞=同质化漏报）
                       + 同一文件传两遍禁自我比对（自比重合 6 维=假同型）
金句密度为 quality-gates 参考项（70%-130% 浮动带），不进 good 必过集合。
check-process.py 自洽回归：正例 exit 0 / 结论项数与裁决表脱节 exit 3 且点名「自洽性断裂」/
     陈旧 MSS 分反例 exit 2（机检节写 77.0、结论与裁决表引用 88.8——P3 禁取全文首匹配，
     机检节排前时首匹配恒为机检节自身的值，陈旧分将永远查不出）/
     坏路径 exit 1（夹具落 tests/.tmp/，跑完即清——防残留混进分发包体、防旧反例被复用）。
tests/golden/ 下支持多金标准（额外 good 样例，过三件套的复评产出固化）。
改任何测量脚本后必跑本测试。
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
METRICS = ROOT / "scripts" / "check-metrics.py"
CHECK_AI = ROOT / "scripts" / "check-ai.py"
CHECK_LEN = ROOT / "scripts" / "check-length.py"
PROCESS = ROOT / "scripts" / "check-process.py"

# 七步法命名锚点（check-consistency 断言锁定；历史旧名 03-细纲.md/05-正文.md 禁回流）
ANCHOR_XIGANG = "tests/fixtures/mini-good/02-细纲.md"        # 细纲单文件两篇合并产物
ANCHOR_RUNSE = "tests/fixtures/mini-annot/04-润色标注稿.md"  # 润色标注稿（阶段5产物）

# MSS 机检对拍元数据（与 fixtures/mss-*/03-正文.md 配套；标题/导语走显式传入）
MSS_GOOD_META = [
    "--title", "父亲的遗嘱第三页",
    "--intro", "父亲的遗嘱第三页，是一个谎言。签名的墨迹很新，纸的折痕却很旧。像有人把三年前的那一页撕掉，换上了自己的意思。母亲在电话里只说了四个字：他回来了。我知道她说的不是父亲。父亲躺在城东的墓园里，胸口那枚领带夹，是我亲手放进去的。",
    "--logline", "父亲入土三个月后，遗嘱第三页出现本该消失的签名，一个谎言被校对编辑女儿撕开，挖出埋了二十八年的命债。",
    "--quotes", "有人把东西让给你，不是欠你，是把你当人；有些账，记了半辈子。还的时候，一杯茶就是全部的仪式；遗嘱不是文物，是证据。证据要放在太阳底下。",
    "--foreshadow", str(ROOT / "tests" / "fixtures" / "mss-good" / "伏笔回收.csv"),
]
MSS_BAD_META = [
    "--title", "你后悔过吗？那些年我们错过的爱情与错过的人生真相大揭秘",
    "--intro", "这是一个关于错过与后悔的故事，写给每一个在深夜里独自失眠的人，如果你也曾对不起某个人，如果你也曾在人海里弄丢过一段感情，也许你能在这个故事里找到自己的影子，然后擦干眼泪，继续往前走，相信下一站，还会有风。",
]

# good 必须 ✅ 的核心项（前缀匹配输出行；金句=参考项不在此列）
CORE_OK = ["2 独句段", "3 超长段", "6 然后", "7 同主语", "8 段落均匀", "9 注水信号"]


def run(script, *args):
    r = subprocess.run([sys.executable, str(script), *[str(a) for a in args]],
                       capture_output=True, text=True)
    return r.returncode, r.stdout


def count_items(out):
    """汇总必修+待修项数（bad 样例判别力断言用）"""
    m1 = re.search(r'必修 (\d+) 项', out)
    m2 = re.search(r'待修 (\d+) 项', out)
    return (int(m1.group(1)) if m1 else 0) + (int(m2.group(1)) if m2 else 0)


def _proc_fixtures():
    """生成 check-process 的正/反例样例目录（写在 tests/.tmp/proc-*，跑完即清）。

    先整树清再建：残留旧夹具会让"反例"悄悄变成上轮遗留的正例，回归失去判别力；
    清理统一收口在 main() 第 13 组之后（含异常路径也走 finally 语义的末尾清）。
    """
    import tempfile
    base = ROOT / "tests" / ".tmp"
    shutil.rmtree(base, ignore_errors=True)
    ok_dir = base / "proc-ok"
    bad_dir = base / "proc-bad"
    stale_dir = base / "proc-stale"
    for d in (ok_dir, bad_dir, stale_dir):
        d.mkdir(parents=True, exist_ok=True)
    # 双报告制：初审报告载机检节（MSS 分值来源），终审报告载工序表/
    # 裁决表/结论句（check-process 核验对象）——P3 溯源跨两份报告
    doc_first = (
        "# 初审报告样例\n\n"
        "## 一、机检数字报告\n\n"
        "MSS 77.0（12 硬门零触发）。\n\n"
        "## 二、最致命 3 问题\n\n"
        "1. 车票回看暗示不足\n\n"
        "## 三、Findings 全单\n\n"
        "S2 一处\n\n"
        "## 四、最小改动修改方案\n\n"
        "回阶段 4 补一处暗示\n"
    )
    doc_final = (
        "# 终审报告样例\n\n"
        "## 一、终审工序执行记录\n\n"
        "| 工序号 | 工序 | 结论 | 证据位 |\n|---|---|---|---|\n"
        "| 1 | 跨章扫描 | 通过 | 全篇 |\n"
        "| 2 | 跳读测试 | 通过 | 章首尾 |\n"
        "| 3 | 付费测试 | 通过 | 免费区 |\n"
        "| 4 | 盲测对比 | 内部对照胜 | 三段 |\n"
        "| 5 | 18 维终审评分 | 8.3 | 评分表 |\n"
        "| 6 | 红队终审 | 3 条 | 拒点清单 |\n"
        "| 7 | 工序留痕核 | 通过 | 本表 |\n\n"
        "## 二、终审裁决表\n\n"
        "| 项 | 门槛 | 实测 | 判 |\n|---|---|---|---|\n"
        "| 初审六维均分 | ≥7 | 8.0 | ✅ |\n"
        "| MSS | 无硬门 | 77.0 | ✅ |\n"
        "| 完读率三环 | 全守 | 全守 | ✅ |\n\n"
        "## 三、终审结论\n\n"
        "**终审结论：可投。** 三项门槛全过，MSS 77.0。\n"
    )
    (ok_dir / "05-初审报告.md").write_text(doc_first, encoding="utf-8")
    (ok_dir / "05-终审报告.md").write_text(doc_final, encoding="utf-8")
    (bad_dir / "05-初审报告.md").write_text(doc_first, encoding="utf-8")
    (bad_dir / "05-终审报告.md").write_text(
        doc_final.replace("三项门槛全过", "四项门槛全过"), encoding="utf-8")
    # 陈旧分反例：初审机检节写 77.0，终审报告结论与裁决表却引用 88.8
    #   ——P3 若只查终审报告自身，跨报告溯源失效，陈旧分永远查不出
    (stale_dir / "05-初审报告.md").write_text(doc_first, encoding="utf-8")
    (stale_dir / "05-终审报告.md").write_text(
        doc_final.replace("| MSS | 无硬门 | 77.0 | ✅ |",
                          "| MSS | 无硬门 | 88.8 | ✅ |")
           .replace("**终审结论：可投。** 三项门槛全过，MSS 77.0。",
                    "**终审结论：可投。** 三项门槛全过，MSS 88.8。"),
        encoding="utf-8")


def main():
    fails = []
    good = ROOT / "tests" / "good-sample.md"
    bad = ROOT / "tests" / "bad-sample.md"
    # check-process 自洽样例（临时落盘，跑完即清）：正例=工序连续+项数相符；
    # 变体=把结论项数改大 1 → 必须报 ❌ 退 3（防"结论句与裁决表脱节"这类人眼漏检复发）
    _proc_fixtures()

    # --- 1. metrics: good 全过 exit 0 / bad 含❌级 exit 3 且 ≥5 项 ---
    code, out = run(METRICS, good)
    for prefix in CORE_OK:
        line = next((l for l in out.splitlines() if l.startswith(prefix)), None)
        if line is None:
            fails.append(f"metrics/good: 缺输出行 {prefix}")
        elif "✅" not in line:
            fails.append(f"metrics/good 应过却报警: {line}")
    if code != 0:
        fails.append(f"metrics/good: 退出码 {code}（应 0——含❌级或仍有待修项）")

    code, out = run(METRICS, bad)
    n = count_items(out)
    if n < 5:
        fails.append(f"metrics/bad: 只触发 {n} 项（应≥5，脚本失去判别力）")
    if code != 3:
        fails.append(f"metrics/bad: 退出码 {code}（应 3——含❌级必修项）")

    # --- 1b. metrics --fragment 片段模式: good 过 / bad 结构性违规照判 exit 3 ---
    code, _ = run(METRICS, good, "--fragment")
    if code != 0:
        fails.append(f"metrics/good --fragment: 退出码 {code}（应 0——比例型参考不计）")
    code, _ = run(METRICS, bad, "--fragment")
    if code != 3:
        fails.append(f"metrics/bad --fragment: 退出码 {code}（应 3——结构性违规片段照判）")

    # --- 1c. 多金标准（复评动态产出固化）: golden/ 下每个 good 过三件套 ---
    golden = ROOT / "tests" / "golden"
    if golden.exists():
        for g in sorted(golden.glob("*.md")):
            if g.name.lower() == "readme.md":
                continue  # 案例库索引文档，非样例
            code, _ = run(METRICS, g, "--fragment")
            if code != 0:
                fails.append(f"metrics/golden/{g.name} --fragment: 退出码 {code}（应 0——好稿误杀）")
            code, _ = run(CHECK_AI, g)
            if code != 0:
                fails.append(f"check-ai/golden/{g.name}: 退出码 {code}（应 0——好稿误杀）")
            code, _ = run(CHECK_LEN, g, "--fragment")
            if code != 0:
                fails.append(f"check-length/golden/{g.name} --fragment: 退出码 {code}（应 0——好稿误杀）")

    # --- 1d. 对话段豁免回归（带引导语的对话段不得误判超长段）---
    #     缺陷形态：超长段豁免若仅认「段首即引号」，带引导语的对话段（「她把伞放在门口：『你走吧。…』」式）
    #     不豁免，合规长对话段误吃 ❌ 必修；修复为段内含对话引文即按对话段豁免（对话段长短由
    #     对话占比带指标 1 与「」形式门指标 15 把控）。正反对拍：对话长段不计违规、纯叙述长段照判——
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tf:
        tf.write("她把伞放在门口，看见他还站在雨里：「你走吧。别回头。走了就别回来。家里还有我呢。"
                 "爸那边我再想办法。钱的事情不用你操心。一切都交给我。」雨越下越大。\n\n"
                 "她感到非常痛苦，觉得很悲伤。心中涌起一股说不出来的难过。眼泪就这样掉了下来。"
                 "她不知道该怎么办。也不知道该去找谁。只能一个人站在原地看着窗外。\n")
        dlg_p = tf.name
    try:
        code, out = run(METRICS, dlg_p, "--fragment")
        if code != 3:
            fails.append(f"metrics/B2: 退出码 {code}（应 3——纯叙述长段仍须 ❌ 必修，豁免不许放宽到叙述段）")
        m = re.search(r"3 超长段\(>3句或>100字\): (\d+) 个", out)
        if not m or m.group(1) != "1":
            fails.append(f"metrics/B2: 超长段计数 {m.group(1) if m else '缺失'}（应 1——仅纯叙述段计违规，"
                         f"带引导语的长对话段须豁免；B2 回归：豁免只认段首即引号则计数为 2）")
    finally:
        os.unlink(dlg_p)

    # --- 2. check-ai: good 无必改 exit 0 / bad 有必改 exit 2 ---
    code, _ = run(CHECK_AI, good)
    if code != 0:
        fails.append(f"check-ai/good: 退出码 {code}（应 0——无必改候选）")
    code, out = run(CHECK_AI, bad)
    if code != 2:
        fails.append(f"check-ai/bad: 退出码 {code}（应 2——黑名单/密度/禁用标点必改）")
    if "必改候选 0 条" in out:
        fails.append("check-ai/bad: 必改候选为 0（必改逻辑失效）")

    # --- 3. check-length: 片段模式两样例过 / 整篇 good 必须❌（验证退出码生效） ---
    for name, s in (("good", good), ("bad", bad)):
        code, _ = run(CHECK_LEN, s, "--fragment")
        if code != 0:
            fails.append(f"check-length/{name} --fragment: 退出码 {code}（应 0）")
    code, _ = run(CHECK_LEN, good)
    if code != 3:
        fails.append(f"check-length/good 整篇: 退出码 {code}（应 3——低于 AT-01 篇幅带下限，AT-56 ❌ 级必修）")

    # --- 3b. check-length 末章/尾声三态回归 ---
    #     缺陷形态：把末块（=末章+尾声混合体，分节正则只在数字标记处切分）无条件当尾声判 50-500：
    #     末章 800-3500 ❌ 门对末章永不生效（门洞）、模板合规稿恒报「⚠️尾声应 50-500」误报、
    #     尾声门自身从未正确执行过（mss-good 金标准末章 789 字被门洞藏住即此 bug 佐证）。
    #     三态锁定（内联构造，沿用 6c/11b 先例不增包体文件数；全文须 ≥12000 字（AT-01 下限），
    #     章数字数按硬线设计——否则状态②会因全文不达标先触 ❌，测不到末章门）：
    #     ① 带尾声合规稿（导语+4 章+「尾声」标签）→ exit 0，末章按章门 ✅、尾声 50-500 ✅、无误报；
    #     ② 带尾声但末章 <1800 → ❌低于章门1800 生效 exit 3（尾声块仍独立 ✅——拆块后两门分离）；
    #     ③ 无尾声标签 → 末块整体走章门 ✅ + ⚠️「未识别到尾声块」提示，exit 0（⚠️ 不计退出码）。
    def _b1_sec(n):
        pad = "她把药瓶摆成一排，标签朝外，雨声盖过了钟摆，父亲的照片在墙上看着这一切，遗嘱的第三页压在杯底，墨迹很新，纸的折痕却很旧。"
        return "\n\n".join([pad] * (n // len(pad) + 1))

    _b1_intro = ("父亲的遗嘱第三页，是一个谎言。有人突然把三年前的那一页撕掉，换上了自己的意思。"
                 "签名的墨迹很新，纸的折痕却很旧。母亲在电话里只说了四个字：他回来了。我知道她说的不是父亲。"
                 "父亲躺在城东的墓园里，胸口那枚领带夹，是我亲手放进去的。")
    _b1_ending = ("尾声。他走了，茶还温着。证据要放在太阳底下，这是她学到的唯一的一件事。"
                  "雨停了，伞还在门口，车票压在杯子底下，那张泛黄的纸条终于对上了号，二十八年的账，一杯茶就是全部的仪式。")

    def _b1_build(secs, labeled):
        parts = [_b1_intro]
        for i, s in enumerate(secs, 1):
            parts.append(str(i))
            parts.append(s)
        if labeled:
            parts.append("尾声")
            parts.append(_b1_ending)
        else:
            # 无标签态：结尾内容不以「尾声」起头（否则命中「标签+内容同行」容错形态即视为有标签）
            parts[-1] = parts[-1] + "\n\n" + _b1_ending.replace("尾声。", "", 1)
        return "\n\n".join(parts)

    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tf:
        tf.write(_b1_build([_b1_sec(2600)] * 4 + [_b1_sec(2000)], True))
        end_ok_p = tf.name
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tf:
        tf.write(_b1_build([_b1_sec(3000)] * 3 + [_b1_sec(700)], True))
        end_short_p = tf.name
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tf:
        tf.write(_b1_build([_b1_sec(2600)] * 4 + [_b1_sec(2000)], False))
        end_none_p = tf.name
    try:
        code, out = run(CHECK_LEN, end_ok_p)
        if code != 0:
            fails.append(f"check-length/ending-ok: 退出码 {code}（应 0——带尾声合规稿：末章走章门、尾声走 50-500 门，两门均过）")
        if "⚠️尾声应 50-500" in out:
            fails.append("check-length/ending-ok: 误报「尾声应 50-500」（B1 回归——末块被无条件当尾声判）")
        if not re.search(r"尾声: \d+ 字 ✅", out):
            fails.append("check-length/ending-ok: 尾声块未按 50-500 门判 ✅（B1 回归——尾声门失效）")
        if not re.search(r"第4章: \d+ 字 ✅", out):
            fails.append("check-length/ending-ok: 末章未按章门判 ✅（B1 回归——末章被当尾声判）")
        code, out = run(CHECK_LEN, end_short_p)
        if code != 3 or "低于章门1800" not in out:
            fails.append(f"check-length/ending-short: 退出码 {code} / 文案（应 3 且含「低于章门1800」——末章 ❌ 门对末章生效，B1 门洞回归）")
        if not re.search(r"尾声: \d+ 字 ✅", out):
            fails.append("check-length/ending-short: 末章不达标时尾声块仍应独立判 ✅（拆块后两门分离回归）")
        code, out = run(CHECK_LEN, end_none_p)
        if code != 0:
            fails.append(f"check-length/ending-none: 退出码 {code}（应 0——无尾声仅 ⚠️ 提示不计退出码）")
        if "未识别到尾声块" not in out:
            fails.append("check-length/ending-none: 未提示「未识别到尾声块」（AT-07 投稿必填提示缺失）")
    finally:
        for p in (end_ok_p, end_short_p, end_none_p):
            os.unlink(p)

    # --- 3b2. check-length 篇幅带边界锁定（AT-01 = 12000-16000，闭区间）---
    #     缺陷形态：整篇门仍写旧「1 万字硬线」——check-mss F1 判 12000-16000，
    #     check-length 却放行 10000-11999 字稿，同一篇稿在两道门里结论相反。
    #     本组锁两侧边界：带内照过、超上限显式 ❌ 并点名 AT-01（防止旧硬线回流）。
    def _b2_body(n):
        pad = "她把药瓶摆成一排，标签朝外，雨声盖过了钟摆，父亲的照片在墙上看着这一切，遗嘱的第三页压在杯底，墨迹很新，纸的折痕却很旧。"
        body = "1\n\n"
        while len(re.sub(r"\s", "", body)) < n:
            body += pad
        return body

    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tf:
        tf.write(_b2_body(12001))
        band_in_p = tf.name
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tf:
        tf.write(_b2_body(16021))
        band_over_p = tf.name
    try:
        code, out = run(CHECK_LEN, band_in_p)
        if "低于 AT-01 篇幅带" in out or "高于 AT-01 篇幅带" in out:
            fails.append("check-length/band-in: 12001 字落在 AT-01 带内却被判篇幅越界（边界正则/阈值回归）")
        code, out = run(CHECK_LEN, band_over_p)
        if code != 3:
            fails.append(f"check-length/band-over: 退出码 {code}（应 3——16021 字超 AT-01 上限 16000）")
        if "高于 AT-01 篇幅带" not in out:
            fails.append("check-length/band-over: 未报「高于 AT-01 篇幅带」（上限门缺失——旧 1 万字单边硬线回流）")
        if "全文>16000" not in out:
            fails.append("check-length/band-over: 未过项未点名「全文>16000」")
    finally:
        os.unlink(band_in_p)
        os.unlink(band_over_p)

    # --- 3b3. check-length --midpoint / --platform 入参面回归（此前零覆盖）---
    #     --midpoint 只有 ⚠️ 级提示路径（不改变退出码），但锚句能定位时必须报出百分比，
    #     锚句找不到时也必须显式提示——两者都被静默吞掉就等于中卡点机检面消失。
    #     --platform 只接受 salt/zhihu/yan 三别名，非法值须退 1（用法错误，AT-56）。
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tf:
        tf.write("他把诊断书塞进抽屉最底层，压在那沓没交的水电费单下面。妻子还在厨房喊他吃饭。\n\n"
                 "1\n\n他掏出那张泛黄的纸条。纸条上是二十年前的字迹，写着一个他从没告诉过任何人的地址。\n")
        mid_p = tf.name
    try:
        code, out = run(CHECK_LEN, mid_p, "--fragment", "--midpoint", "泛黄的纸条")
        if "中卡点字位" not in out:
            fails.append("check-length/midpoint-ok: 未报「中卡点字位」（--midpoint 机检面静默失效）")
        if not re.search(r"中卡点字位: 第 \d+ 字（[\d.]+%）", out):
            fails.append("check-length/midpoint-ok: 中卡点字位行缺百分比（AT-10 ⚠️ 级口径未输出）")
        code, out = run(CHECK_LEN, mid_p, "--fragment", "--midpoint", "这句在中卡点不存在")
        if "未找到中卡点锚句" not in out:
            fails.append("check-length/midpoint-missing: 锚句缺失未提示（禁静默跳过中卡点核对）")
        code, out = run(CHECK_LEN, mid_p, "--fragment", "--platform", "salt")
        if code != 0:
            fails.append(f"check-length/platform-ok: 退出码 {code}（应 0——salt 为合法别名）")
        code, out = run(CHECK_LEN, mid_p, "--fragment", "--platform", "fanqie")
        if code != 1:
            fails.append(f"check-length/platform-bad: 退出码 {code}（应 1——未知平台属用法错误，AT-56）")
        if "未知平台口径" not in out:
            fails.append("check-length/platform-bad: 未报「未知平台口径」（三别名映射校验缺失）")
    finally:
        os.unlink(mid_p)

    # --- 4. consistency 必须全过 ---
    code, out = run(ROOT / "scripts" / "check-consistency.py")
    if code != 0:
        fails.append("check-consistency 失败:\n" + out)

    # --- 4b. 空稿门禁回归：三件套对空正文必须退 1，禁「空稿判绿」---
    #     缺陷形态：metrics 用 max(count(t),1) 兜分母 → 空稿算出对话占比 0% 被列「待修」（误报）；
    #     ai / mss 命中计数恒 0 → 直接 exit 0（空稿拿到通行证，门禁形同虚设）。
    #     统一口径：空稿是输入错误不是质量问题，一律退 1 并点明「正文为空」。
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tf:
        empty_p = tf.name
    try:
        for _name, _args in (("check-metrics.py", [empty_p]),
                             ("check-ai.py", [empty_p]),
                             ("check-mss.py", ["--text", empty_p])):
            _code, _out = run(ROOT / "scripts" / _name, *_args)
            if _code != 1:
                fails.append(f"空稿门禁/{_name}: 退出码 {_code}（应 1——空稿不得判绿）")
            if "正文为空" not in _out:
                fails.append(f"空稿门禁/{_name}: 未点明「正文为空」（诊断信息缺失）")
    finally:
        os.unlink(empty_p)

    # --- 5. check-artifacts 产物机检: mini-good 过 / mini-bad 字段空缺必须被抓 ---
    art = ROOT / "scripts" / "check-artifacts.py"
    fg = ROOT / "tests" / "fixtures" / "mini-good"
    fb = ROOT / "tests" / "fixtures" / "mini-bad"
    if art.exists() and fg.exists() and fb.exists():
        code, _ = run(art, fg)
        if code != 0:
            fails.append(f"artifacts/good: 退出码 {code}（应 0——字段全在位）")
        code, out = run(art, fb)
        if code != 3:
            fails.append(f"artifacts/bad: 退出码 {code}（应 3——章末钩/动机空缺必被抓）")
        if "字段空缺" not in out:
            fails.append("artifacts/bad: 未报字段空缺（判别力失效）")
    else:
        fails.append("check-artifacts 或 fixtures 缺失（产物机检面丢失）")

    # --- 6. G 项靶点密度/节末钩机检 + --first-twist 双锚句回归 ---
    if art.exists():
        code, out = run(art, fg)
        if "靶点密度" not in out:
            fails.append("artifacts/good: G 项未执行（靶点密度缺失——G1 机检面丢失）")
        if "G1 项" in out or "G2 项" in out:
            fails.append("artifacts/good: G 项误报（好稿不应触发 G1/G2 警告）")
        fa = ROOT / "tests" / "fixtures" / "mini-annot"
        if fa.exists():
            code, out = run(art, fa)
            if code != 0:
                fails.append(f"artifacts/annot: 退出码 {code}（应 0——章末钩全在位、对账平）")
            if "章末钩全在位" not in out:
                fails.append("artifacts/annot: 未报章末钩全在位（G2 正向失效）")
            if "靶点密度" not in out:
                fails.append("artifacts/annot: 未报靶点密度（G1 正向失效）")
        else:
            fails.append("mini-annot fixture 缺失（G 项正向回归丢失）")
    else:
        fails.append("check-artifacts 缺失（G 项回归无法执行）")

    tg = ROOT / "tests" / "fixtures" / "twist-order-good.md"
    tb = ROOT / "tests" / "fixtures" / "twist-order-bad.md"
    if tg.exists() and tb.exists():
        code, out = run(CHECK_LEN, tg, "--fragment", "--paywall", "门被推开的那一刻",
                        "--first-twist", "他掏出那张泛黄的纸条")
        if code != 0:
            fails.append(f"check-length/twist-good: 退出码 {code}（应 0——反转早于付费墙）")
        if "首次反转早于付费墙" not in out:
            fails.append("check-length/twist-good: 未输出相对位置判定（双锚句核对失效）")
        code, out = run(CHECK_LEN, tb, "--fragment", "--paywall", "门被推开的那一刻",
                        "--first-twist", "他掏出那张泛黄的纸条")
        if code != 3:
            fails.append(f"check-length/twist-bad: 退出码 {code}（应 3——反转晚于付费墙必须被抓，❌ 级）")
        if "首次反转晚于付费墙" not in out:
            fails.append("check-length/twist-bad: 未报反转晚于付费墙（判别力失效）")
    else:
        fails.append("twist-order fixtures 缺失（双锚句回归丢失）")

    # --- 6a. --intro 导语锚句双态回归（存在照旧判 / 缺失显式 ❌）---
    #     缺陷形态：锚句找不到时静默按整块计数，输出误导性「导语 N 字 ⚠️」——
    #     把「锚句与正文不一致」包装成「导语字数超标」的内容问题假象，真问题
    #     （导语边界根本没定位到）反被掩盖。与 --paywall/--first-twist 锚句缺失
    #     同口径：显式 ❌ 并入未过项、退 3（AT-56）。fragment 模式章门降提示，
    #     保证只有导语锚句一项能改变退出码——正反例互不污染。
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tf:
        tf.write("他把诊断书塞进抽屉最底层，压在那沓没交的水电费单下面。妻子还在厨房喊他吃饭，"
                 "锅铲碰着锅底，声音很急，像在催一句他一直没敢应的话。窗外的天灰得发蓝，他站起来，又坐下去。\n\n"
                 "1\n\n他掏出那张泛黄的纸条。纸条上是二十年前的字迹，写着一个他从没告诉过任何人的地址。\n\n"
                 "2\n\n晚上他做了一桌子菜。妻子进门愣住了：「今天什么日子？」他说：「想做就做了，趁还能做的时候。」\n")
        intro_p = tf.name
    try:
        code, out = run(CHECK_LEN, intro_p, "--fragment", "--intro", "又坐下去。")
        if code != 0:
            fails.append(f"check-length/intro-ok: 退出码 {code}（应 0——锚句存在时导语判定照旧，fragment 章门降提示）")
        if "未找到导语锚句" in out:
            fails.append("check-length/intro-ok: 锚句存在却报缺失（find 逻辑回归）")
        m = re.search(r"导语/起始: (\d+) 字 (✅|⚠️|❌)", out)
        if not m or m.group(2) != "✅":
            fails.append(f"check-length/intro-ok: 导语未判 ✅（{m.group(0) if m else '行缺失'}）"
                         f"——锚句存在时须按 80-150 带判定，禁静默按整块计数")
        code, out = run(CHECK_LEN, intro_p, "--fragment", "--intro", "这句在正文里不存在")
        if code != 3:
            fails.append(f"check-length/intro-missing: 退出码 {code}（应 3——锚句缺失禁静默按整块计数，须显式 ❌）")
        if "未找到导语锚句" not in out:
            fails.append("check-length/intro-missing: 未报「未找到导语锚句」（误导性「导语 N 字 ⚠️」回流）")
    finally:
        os.unlink(intro_p)

    # --- 6b. G3 章末钩类型同质正反例 + C11 三连击窗口回归 ---
    hs = ROOT / "tests" / "fixtures" / "hooks-same"
    hd = ROOT / "tests" / "fixtures" / "hooks-diff"
    if hs.exists() and hd.exists() and art.exists():
        code, out = run(art, hs)
        if "章末钩类型同质" not in out:
            fails.append("artifacts/G3 正例: 连续两章同类型钩子未报警（同质判别力丢失）")
        code, out = run(art, hd)
        if "章末钩类型同质" in out:
            fails.append("artifacts/G3 负例: 类型各异仍报警（误报）")
    else:
        fails.append("hooks fixtures 缺失（G3 同质回归丢失）")

    # --- 6c. G2 章末钩尾窗反例：钩子标注只在章首（章中）出现，不构成章末钩 ---
    #     （曾搜整章：章中任何【钩子】标注都算「章末在位」，与 stage3「每章末 100 字内」
    #       口径打架；本反例锁「只认章尾 200 字窗」——每章 >200 字确保章首钩在窗外）
    if art.exists():
        g2_dir = ROOT / "tests" / ".tmp" / "g2-midhook"
        g2_dir.mkdir(parents=True, exist_ok=True)
        (g2_dir / "04-润色标注稿.md").write_text(
            "## 1\n【钩子+留白】\n"
            "他把钥匙插进锁孔，转了两圈，门没有开。第三圈的时候，锁芯里传来一声干涩的响，像骨头错位。"
            "他愣了一下，才想起这是母亲家的门，上周换过锁，新钥匙还在中介手里，旧的早就该作废。"
            "他站在楼道里，声控灯灭了又亮，亮了又灭，最后他蹲下去，从门缝底下往里看。"
            "拖鞋摆得整整齐齐，一双朝外，一双朝内，和母亲生前的习惯一模一样。"
            "他的鼻子忽然酸了一下，赶紧站起来，靠在墙上，抬头看着天花板上的水渍。"
            "那片水渍像一张地图，边缘发黄，中间还有一道裂痕。他看了很久，久到邻居开门出来倒垃圾，看了他一眼，又缩回去。"
            "他直起身，把钥匙从锁孔里拔出来，攥在手心里，金属的边缘陷进掌纹里。\n\n"
            "## 2\n【钩子+留白】\n"
            "雨是半夜开始下的。他躺在床上，听着雨点打在遮阳棚上，声音由稀到密，最后连成一片，"
            "像有人把整袋黄豆倒在了铁皮上。他睡不着，起身把窗户关小，留了一条缝，"
            "让风带着雨丝飘进来，落在窗台上的绿萝叶子上。那片叶子已经黄了一半，是母亲留下的，"
            "她叫它小帆，说看见叶子就想起他小时候折的纸船。他伸出手，指尖碰了碰叶尖，凉的，湿的，"
            "和他记忆里某个夏天的触感重叠在一起。他收回手，在黑暗里站了一会儿，才回到床上，把脸埋进枕头。"
            "枕头上有淡淡的樟脑味，是母亲衣柜里的味道，搬家的时候他执意把这只枕头带了过来。"
            "雨声渐渐小了，他闭上眼，听见自己的心跳，一下，一下，很慢，很重。\n\n"
            "## 3\n【钩子+留白】\n"
            "葬礼那天来了十七个人。他记不清他们是谁，只记得每个人都握了他的手，说了同一句话，然后松开，退到下一步去。"
            "他站在人群的最前面，看着棺材慢慢降下去，土一锹一锹地落在上面，声音闷得让人心慌。"
            "他没有哭，只是数着人数，数到第十七的时候，发现少了一个——那个每周三下午来陪母亲下棋的老头，今天没有来。"
            "他后来才知道，老头自己在三个月前也走了，就在隔壁街区，同一家医院，同一间病房。"
            "母亲从没提过这件事，就像她从不提自己每周三下午其实都在等一通不会响的电话。"
            "葬礼结束后，他一个人在墓园坐到天黑。守园人过来问他还好吗，他说还好。"
            "守园人点点头，指着远处一盏一盏亮起来的路灯说，这时候的灯，最像人间的星星。"
            "他抬起头，看见第一颗真正的星星，挂在墓园围墙外面的天上。\n",
            encoding="utf-8")
        code, out = run(art, g2_dir / "04-润色标注稿.md")
        if "章末钩缺失" not in out:
            fails.append("artifacts/G2 反例: 章中钩子标注被当章末在位（尾窗失效——搜整章回归）")
    code, out = run(CHECK_LEN, good, "--fragment", "--paywall", "而我，是被继承人")
    if "C11 卡点三连击" not in out:
        fails.append("check-length/C11: --paywall 未输出三连击核对窗口（G6 机检面丢失）")

    # --- 6c. 付费墙占比带锁定（25-35%，AT-05）---
    #     片段模式：字位偏离仅提示不计退出码；锚句置于全文开头（占比≈0%）必偏离，
    #     偏离输出须点名 25-35% 带——与 check-consistency 文件级断言双锁
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tf:
        tf.write("而他，是被继承人——这句话像一块冰滑进衣领。\n\n"
                 + "".join(f"第{i}段：她把药瓶摆成一排，标签朝外，雨声盖过了钟摆。\n\n" for i in range(1, 16)))
        band_p = tf.name
    try:
        code, out = run(CHECK_LEN, band_p, "--fragment", "--paywall", "而他，是被继承人")
        if code != 0:
            fails.append(f"check-length/band: 退出码 {code}（应 0——片段模式字位偏离仅提示）")
        if "25-35% 带" not in out:
            fails.append("check-length/band: 偏离输出未点名 25-35% 带（付费墙占比带口径漂移——AT-05：25-35%）")
    finally:
        os.unlink(band_p)

    # --- 6d. 边界用例回归（4 处边界 bug 锁定）---
    #     边界输入三铁律：不崩（禁裸 traceback）、退出码语义正确（AT-56）、诊断文案在位：
    #     - 空稿/纯空白: 不崩 + **必须退 1**（空稿是输入错误，不得判绿拿通行证）——
    #       早先只验「不崩」，用 exit 0 当代理，结果空稿能一路判绿过门（门禁漏洞）。
    #       现口径：不崩 = 无 traceback 且有诊断文案；判罚 = exit 1。
    #     - 畸形 CSV 双路径: ①表头缺必需列 → 诚实报「字段缺失」触硬门（禁静默按 0% 判）；
    #       ②表头正确但行字段溢出 → DictReader restkey（多余值进 None 键）直接 .strip()
    #       AttributeError → 剔 restkey 后正常判分
    #     - check-mss 无参数: argparse 默认退 2 与「⚠️ 级待修」撞码误导聚合门 → _Parser 退 1
    #     - 不存在文件/目录作参数: 裸 traceback → 干净「❌ 文件不存在/不是文件」退 1
    #       （check-mss 若用 exists() 判存在，目录亦为真致 read_text 抛 IsADirectoryError）
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tf:
        empty_p = tf.name  # 空文件
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tf:
        tf.write("\n\n   \n\t\n")  # 纯空白（无有效段落、无有效词）
        blank_p = tf.name
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tf:
        # H1-only 无换行稿：首行标题被剔后正文为空——find('\n') 返 -1 时禁按尾字符切片
        # （曾把最后一个字符当正文，空稿拦截失效、exit 0 放行）
        tf.write("# 只有一个标题没有换行")
        h1only_p = tf.name
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as tf:
        tf.write("不是,合法,CSV\n1,2\n,,,\n")  # 表头缺必需列 → 须诚实报「字段缺失」
        bad_csv = tf.name
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as tf:
        # 表头正确但行字段多于表头（restkey 陷阱：多余值进 None 键，直接 .strip() 会崩）。
        # 第三行前 5 字段全空——any() 短路求值必须走到 None 键才崩，首字段非空的溢出行漏检
        tf.write("埋设位置,埋设原句,回收位置,回收原句,回收方式\n"
                 "第三章,他把伞放在门口,第七章,伞还在门口,物件呼应\n"
                 "第一章,她留着那张旧照片,第九章,照片在火盆里烧掉了,信物呼应,溢出字段一,溢出字段二\n"
                 ",,,,,空行溢出A,空行溢出B\n")
        overflow_csv = tf.name
    try:
        for p in (empty_p, blank_p, h1only_p):
            code, out = run(CHECK_AI, p)
            # 不崩检查：裸 traceback 视为崩（与「退 1」区分开——退 1 是预期的判罚）
            if "Traceback" in out:
                fails.append(f"check-ai/{Path(p).name}: 空稿裸 traceback（守卫缺失）")
            if code != 1:
                fails.append(f"check-ai/{Path(p).name}: 退出码 {code}（应 1——空稿须判空，不得判绿）")
            if "正文为空" not in out and "段落 0 个" not in out:
                fails.append(f"check-ai/{Path(p).name}: 未点明空稿（诊断信息缺失）")
            code, out = run(METRICS, p, "--fragment")
            if "Traceback" in out:
                fails.append(f"metrics/{Path(p).name}: 空稿裸 traceback（守卫缺失）")
            if code != 1:
                fails.append(f"metrics/{Path(p).name} --fragment: 退出码 {code}（应 1——空稿须判空）")
            if "正文为空" not in out:
                fails.append(f"metrics/{Path(p).name} --fragment: 未点明「正文为空」")
        code, out = run(CHECK_AI, ROOT / "tests/definitely-not-exist.md")
        if code != 1 or "文件不存在" not in out:
            fails.append(f"check-ai/不存在文件: 退出码 {code} / 文案缺失（应 1 且 stdout 含「文件不存在」）")
        code, out = run(METRICS, ROOT / "tests/definitely-not-exist.md")
        if code != 1 or "文件不存在" not in out:
            fails.append(f"metrics/不存在文件: 退出码 {code} / 文案缺失（应 1 且 stdout 含「文件不存在」）")
        code, _ = run(ROOT / "scripts" / "check-mss.py")
        if code != 1:
            fails.append(f"mss/无参数: 退出码 {code}（应 1——用法错误禁 argparse 默认 2，与⚠️级撞码会误导聚合门）")
        code, out = run(ROOT / "scripts" / "check-mss.py", "--text", ROOT / "scripts")
        if code != 1 or "不是文件" not in out:
            fails.append(f"mss/目录作参数: 退出码 {code} / 文案缺失（应 1 且含「不是文件」——"
                         f"exists() 对目录为真致 read_text 裸 IsADirectoryError）")
        code, out = run(ROOT / "scripts" / "check-mss.py", "--text", ROOT / "tests" / "definitely-not-exist.md")
        if code != 1 or "不存在" not in out:
            fails.append(f"mss/不存在文件: 退出码 {code} / 文案缺失（应 1 且含「不存在」）")
        code, out = run(ROOT / "scripts" / "check-mss.py", "--text",
                        ROOT / "tests" / "fixtures" / "mss-good" / "03-正文.md", "--foreshadow", bad_csv)
        if code != 3:
            fails.append(f"mss/畸形CSV: 退出码 {code}（应 3——伏笔回收表缺失触硬门封顶 59）")
        if "字段缺失" not in out:
            fails.append("mss/畸形CSV: 未报字段缺失（表头校验回归——畸形 CSV 不许裸 traceback）")
        code, _ = run(ROOT / "scripts" / "check-mss.py", "--text",
                      ROOT / "tests" / "fixtures" / "mss-good" / "03-正文.md", "--foreshadow", overflow_csv)
        if code != 0:
            fails.append(f"mss/字段溢出CSV: 退出码 {code}（应 0——剔 restkey 后两行伏笔全回收；"
                         f"AttributeError 回归：对 None 键 list 直接 .strip() 会崩）")
    finally:
        for p in (empty_p, blank_p, h1only_p, bad_csv, overflow_csv):
            os.unlink(p)

    # --- 6e. BOM 计数偏差回归 ---
    #     Windows 编辑器（记事本/VS Code）常给 UTF-8 稿件加 BOM 头；read_text('utf-8')
    #     把 BOM 当正文计 1 字——3499 字稿读成 3500 越 AT-02 绝对上限，导语 80/150 字界
    #     （AT-06）同理可被掀翻。稿件面 6 个读取点（length/metrics/ai/mss/fingerprint/
    #     artifacts）已改 utf-8-sig；本用例锁「BOM 不影响计数与判罚」：
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tf:
        tf.write("1\n你好世界。这是测试内容。\n")
        nobom_p = tf.name
    with open(nobom_p, "rb") as bf:
        _body = bf.read()
    with tempfile.NamedTemporaryFile("wb", suffix=".md", delete=False) as tf:
        tf.write(b"\xef\xbb\xbf" + _body)  # 同内容 + BOM 头
        bom_p = tf.name
    try:
        _, out_nobom = run(CHECK_LEN, "--fragment", nobom_p)
        _, out_bom = run(CHECK_LEN, "--fragment", bom_p)
        m_nobom = re.search(r"全文:\s*(\d+)\s*字", out_nobom)
        m_bom = re.search(r"全文:\s*(\d+)\s*字", out_bom)
        if not m_nobom or not m_bom:
            fails.append("BOM回归: 字数行缺失（check-length 输出格式漂移？）")
        elif m_nobom.group(1) != m_bom.group(1):
            fails.append(f"BOM回归: 计数偏差 {m_nobom.group(1)} vs {m_bom.group(1)}"
                         f"（BOM 被计 1 字——读取点回退 utf-8）")
        code, _ = run(CHECK_AI, bom_p)
        if code != 0:
            fails.append(f"check-ai/BOM文件: 退出码 {code}（应 0——BOM 不许引发判罚）")
    finally:
        os.unlink(nobom_p)
        os.unlink(bom_p)

    # --- 6f. check-length 参数解析回归 ---
    #     手写 argv 裸 args[index+1] 取值：尾随 flag 崩 IndexError、--target 非数字崩
    #     ValueError、未知 flag 静默忽略致按错误模式跑（打错 --frament 会当整篇判）、多文件
    #     只跑第一个——现校验式解析一律干净退 1。鉴别法：干净文案在 stdout，裸 traceback 在
    #     stderr（run() 只捕 stdout）——文案缺席即崩过：
    for bad_args, desc, needle in (
        (["--paywall"], "尾随flag无值", "缺少取值"),
        (["--target", "abc"], "target非数字", "--target 须为整数"),
        (["--bogus-flag"], "未知flag", "未知参数"),
    ):
        code, out = run(CHECK_LEN, good, *bad_args)
        if code != 1 or needle not in out:
            fails.append(f"length/{desc}: 退出码 {code} / 文案「{needle}」缺席"
                         f"（应 1 且 stdout 含该文案——裸 traceback 回归则文案在 stderr）")
    code, out = run(CHECK_LEN, good, bad)
    if code != 1 or "只接受一个正文文件" not in out:
        fails.append(f"length/双文件: 退出码 {code} / 文案缺席（应 1 且含「只接受一个正文文件」）")
    # check-metrics/check-ai 同款静默忽略（打错 flag 按整篇跑 / 多文件只测第一个）：
    code, out = run(METRICS, good, "--frament")
    if code != 1 or "未知参数" not in out:
        fails.append(f"metrics/未知flag: 退出码 {code} / 文案缺席（应 1 且含「未知参数」——"
                     f"打错 --fragment 禁静默按整篇跑）")
    code, out = run(CHECK_AI, good, bad)
    if code != 1 or "只接受一个正文文件" not in out:
        fails.append(f"ai/双文件: 退出码 {code} / 文案缺席（应 1 且含「只接受一个正文文件」）")
    # 1e. metrics 两处 ❌ 级判据此前零覆盖：段落均匀（指标 8）与虚词超限（指标 5）——
    #     这两条是「AI 铁证/注水」的机检主判据，若阈值上调、或短样本豁免误把阈值放宽到 ≥15 段样本，
    #     回归原本不会响（good/bad 金标准的判罚全由超长段/同主语承担）。此处置 16 段同字数样本：
    #     相邻段差 ≤10% 必成 ≥4 连段 → 段落均匀 ❌；「觉得/感到」堆到 12 处 → 虚词超限 ❌。
    _uni = "她把药瓶摆成一排，标签朝外，雨声盖过了钟摆，父亲的照片在墙上看着这一切。\n\n"
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tf:
        tf.write("# 段落均匀与虚词超限判别力用例\n\n" + _uni * 16
                 + "\n她觉得很累。她感到很冷。她觉得很远。她感到很轻。她觉得很重。她感到很薄。"
                 "她觉得很长。她感到很短。她觉得很暗。她感到很亮。她觉得很旧。她感到很久。\n")
        uni_p = tf.name
    try:
        code, out = run(METRICS, uni_p)
        if code != 3:
            fails.append(f"metrics/段落均匀+虚词: 退出码 {code}（应 3——16 段同字数 + 虚词成堆，两条 ❌ 级判据须生效）")
        # 只看汇总必修行（"❌ 必修 N 项: [...]"）——尾部提示语含"必修级"，不能用 split("必修")[-1]
        must_line = next((l for l in out.splitlines() if l.startswith("❌ 必修")), "")
        if "段落均匀" not in must_line:
            fails.append("metrics/段落均匀: 16 段同字数未列入必修（≥4 连段=AI 铁证的机检主判据失效）")
        if "虚词超限" not in must_line:
            fails.append("metrics/虚词超限: 虚词成堆未列入必修（指标 5 判别力丢失）")
    finally:
        os.unlink(uni_p)

    # --- 7. check-all 一键全量门 × 金标准 fixture（回归不只测 check-artifacts,
    #   mini-good 曾被一键门自己的判罚拦下——门禁与金标准自相矛盾而无人发现, 由此封堵）---
    ca = ROOT / "scripts" / "check-all.py"
    if ca.exists() and fg.exists() and fb.exists():
        code, _ = run(ca, fg)
        if code != 0:
            fails.append(f"check-all/mini-good: 退出码 {code}（应 0——金标准必须过一键全量门）")
        code, out = run(ca, fb)
        if code == 0:
            fails.append("check-all/mini-bad: 退出码 0（应非 0——坏样例必须被一键门抓住）")
        if "脚本可用性探针" not in out:
            fails.append("check-all/mini-bad: 未执行脚本可用性探针（一键门聚合面失效）")
    else:
        fails.append("check-all 或 fixtures 缺失（一键门×金标准回归丢失）")

    # --- 8. 甜宠长稿用例（对话占比目标带 40-50% 可达性 + 好稿不误杀；
    #    七步法命名: 03-正文.md）---
    sw = ROOT / "tests" / "fixtures" / "genre-sweet" / "03-正文.md"
    if sw.exists():
        code, out = run(METRICS, sw, "--fragment")
        m = re.search(r'对话占比[:：]\s*([\d.]+)%', out)
        v = float(m.group(1)) if m else -1
        if not (40 <= v <= 50):
            fails.append(f"genre-sweet: 对话占比 {v}%（应落甜宠目标带 40-50%）")
        code, _ = run(CHECK_AI, sw)
        if code != 0:
            fails.append(f"check-ai/genre-sweet: 退出码 {code}（应 0——甜宠长稿好稿误杀）")
        code, _ = run(CHECK_LEN, sw, "--fragment")
        if code != 0:
            fails.append(f"check-length/genre-sweet --fragment: 退出码 {code}（应 0）")
    else:
        fails.append("genre-sweet fixture 缺失（甜宠长稿回归丢失）")

    # --- 9. 结构指纹同质化机检（同型对必须被抓 / 差异对必须放行）---
    fp = ROOT / "scripts" / "check-fingerprint.py"
    fps = ROOT / "tests" / "fixtures" / "fingerprint" / "same"
    fpd = ROOT / "tests" / "fixtures" / "fingerprint" / "diff"
    if fp.exists() and fps.exists() and fpd.exists():
        code, _ = run(fp, fps)
        if code != 2:
            fails.append(f"check-fingerprint/same: 退出码 {code}（应 2——同型必须被抓）")
        code, _ = run(fp, fpd)
        if code != 0:
            fails.append(f"check-fingerprint/diff: 退出码 {code}（应 0——差异稿误杀）")
    else:
        fails.append("check-fingerprint 或 fingerprint fixtures 缺失（指纹回归丢失）")

    # --- 9b. 同名目录禁静默丢篇 + 重复传同文件禁自我比对 ---
    #     两个同名项目目录（项目-甲/ 与 存档/项目-甲/）各存一篇同型指纹——按目录名做键时
    #     第二篇静默覆盖第一篇，两篇变一篇，同质化比对直接漏报（exit 0 假绿）；
    #     同一文件传两遍则禁自我比对（自比重合 6 维 = 假同型误报）
    fp_dup = ROOT / "tests" / ".tmp" / "fp-dup"
    card = ("- 叙事起点: 反常发现\n- 主角行动模式: 取证反击\n"
            "- 核心反转类型: 身份/关系反转\n- 核心意象类别: 器物信物\n"
            "- 关系翻转方向: 受害者→清算者\n- 付费卡点触发情境: 认知颠覆时刻\n")
    for sub in ("项目-甲", "存档/项目-甲"):
        d = fp_dup / sub
        d.mkdir(parents=True, exist_ok=True)
        (d / "08-结构指纹.md").write_text("# 指纹\n\n" + card, encoding="utf-8")
    code, out = run(fp, fp_dup)
    if code != 2:
        fails.append(f"check-fingerprint/同名目录: 退出码 {code}（应 2——同名目录第二篇被静默覆盖，同质化漏报）")
    if "2 篇" not in out:
        fails.append("check-fingerprint/同名目录: 未报 2 篇（篇数被吞——按目录名做键禁回流）")
    one = fpd / "甲" / "08-结构指纹.md"
    code, out = run(fp, one, one)
    if code != 0:
        fails.append(f"check-fingerprint/重复传同文件: 退出码 {code}（应 0——同一篇禁自我比对误报同型）")

    # --- 10. 整篇核验步 / 标题-引号测量 / 红线-事实核验回归 ---
    code, out = run(METRICS, good, "--fragment")
    if "14 标题字数" not in out or "15 引号类型" not in out:
        fails.append("metrics: 标题/引号测量项缺失（应含 14/15）")
    if art.exists():
        code, out = run(art, fg)
        if "题材红线扫描" not in out or "事实核验防线" not in out:
            fails.append("artifacts: 红线/事实扫描项缺失（应含 H/I）")
        if code != 0:
            fails.append(f"artifacts/mini-good: 退出码 {code}（应 0——新增扫描不得误伤金标准）")
    if ca.exists() and fg.exists():
        code, out = run(ca, fg)
        if "整篇核验" not in out:
            fails.append("check-all: 整篇核验步缺失")
        if code != 0:
            fails.append(f"check-all/mini-good: 退出码 {code}（应 0——整篇核验步不得误伤 <1 万字切片）")

    # --- 11. MSS 机检结构分正反对拍
    #     （F30+B20+T25+D15+R10 五模块 + 12 硬门；好稿满分放行 / 坏样 59 封顶）---
    mss = ROOT / "scripts" / "check-mss.py"
    mg = ROOT / "tests" / "fixtures" / "mss-good" / "03-正文.md"
    mb = ROOT / "tests" / "fixtures" / "mss-bad" / "03-正文.md"
    if mss.exists() and mg.exists() and mb.exists():
        code, out = run(mss, "--text", mg, *MSS_GOOD_META)
        if code != 0:
            fails.append(f"mss/good: 退出码 {code}（应 0——硬门全过且 MSS≥80）")
        m = re.search(r'MSS=([\d.]+)', out)
        if not m or float(m.group(1)) < 80:
            fails.append(f"mss/good: MSS={m.group(1) if m else '缺失'}（应 ≥80）")
        if "机检匹配高" not in out:
            fails.append("mss/good: 未报机检匹配高（五模块口径失效）")
        if "封顶 59" in out:
            fails.append("mss/good: 好稿竟触硬门封顶（误杀——检查词表/权重漂移）")
        code, out = run(mss, "--text", mb, *MSS_BAD_META)
        if code != 3:
            fails.append(f"mss/bad: 退出码 {code}（应 3——硬门触发封顶 59，❌ 级）")
        if "封顶 59" not in out:
            fails.append("mss/bad: 未报 59 封顶（硬门封顶失效）")
        n_gate = len(re.findall(r'触发：', out))
        if n_gate < 5:
            fails.append(f"mss/bad: 仅触发 {n_gate} 个硬门（应 ≥5，判别力失效）")
        # 11a 一称返还禁白送：--person 3rd 且前 500 字"我"≥5 时一称项不扣分也不返还——
        #     「先扣再返还」在未扣分时仍执行 +2，F 模块 32/30 超权重、MSS 虚高 2 分
        #     （AT-64：一称"我"频率仅适用一称稿，三称稿不判）
        code, out = run(mss, "--text", mg, *MSS_GOOD_META, "--person", "3rd")
        m2 = re.search(r'F=(\d+)', out)
        if not m2 or m2.group(1) != "30":
            fails.append(f"mss/person-3rd: F={m2.group(1) if m2 else '缺失'}（应 30——一称返还禁白送，F 模块权重 30 不许超）")
        # 11b F2 分节口径锁定：纯数字唯一合规——「N.」带点式必须触硬门且被点名
        #     （规范=1/2/3 独立成行不带符号，style-rules 章节标题条；防正则误改回认带点）
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tf:
            tf.write("1.\n\n他推开门，药瓶立在桌角，标签上的日期是1998年3月7日，墨迹很新。\n\n"
                     "2.\n\n雨下了四十分钟，伞骨断了两根。她把车票翻过来，背面写着1998。\n\n"
                     "3.\n\n尾声。他走了，茶还温着。证据要放在太阳底下，这是她学到的唯一一件事。\n")
            dotted_p = tf.name
        try:
            code, out = run(mss, "--text", dotted_p, "--title", "分节带点式锁定用例")
            if code == 0:
                fails.append("mss/dotted: 「N.」带点式分节竟过 F2 硬门（分节口径漂移——须只认纯数字独立成行）")
            if "「N.」" not in out:
                fails.append("mss/dotted: 未点名「N.」非规范分节标记（诊断提示失效）")
        finally:
            os.unlink(dotted_p)
        # 11b2 T1 开篇共现判别力锁定（假阳性回归）---
        #     缺陷形态：原判定只要凑够 2 类即过，而「代词+动作词」是最廉价的两类——
        #     "我叫林晚…出门坐地铁上班" 同时命中"我"与"出"，却完全是身份陈述式平开头，
        #     正是编辑最常拒的第一类。真爆款式静物异常（桌上多了份解约协议）反被漏判。
        #     口径：代词/动作仅为辅助类，须有冲突词或后果词支撑，否则不判过。
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tf:
            tf.write("1\n\n我叫林晚，今年二十八岁，在一家设计公司做项目经理。\n"
                     "那天早上，我像往常一样起床洗漱，然后出门坐地铁去上班。\n"
                     "天气很好，阳光透过办公室的玻璃窗照进来，落在我的工位上。\n")
            flat_p = tf.name
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tf:
            tf.write("1\n\n林晚推开门时，办公桌上摆着一份解约协议，落款日期是昨天。\n"
                     "她签的字，昨天没有签过。\n"
                     "指尖还沾着门把手的凉。她没敢碰那张纸，先掏出手机拍了一张。\n")
            hook_p = tf.name
        try:
            code, out = run(mss, "--text", flat_p, "--title", "平开头判别力用例")
            if "身份陈述式平开头" not in out:
                fails.append("mss/T1-flat: 身份陈述式平开头未被识破（代词+动作词凑 2 类即放过的假阳性回流）")
            if "硬门" in out and "开头 100 字无冲突" not in out:
                fails.append("mss/T1-flat: 平开头未触发开头共现硬门（判别力丢失）")
            code, out = run(mss, "--text", hook_p, "--title", "钩子开头判别力用例")
            if "身份陈述式平开头" in out:
                fails.append("mss/T1-hook: 静物异常型开头（解约协议）被误判为平开头（冲突词表缺物证型）")
        finally:
            os.unlink(flat_p)
            os.unlink(hook_p)
        # 11c F1 篇幅硬门边界锁定（AT-01 = 12000-16000，闭区间）---
        #     F1 是闭区间硬门，边界差 1 字即判罚，必须锁 11999/12000/16000/16001 四点，
        #     否则将来任何人把 `<=` 写回 `<`、或把区间改宽，回归都不会响。
        def _mk_len(n_target):
            body = "1\n\n"
            para = "他把手里的东西放下，转过身来，看着她。\n\n"
            i = 2
            while True:
                need = n_target - len(re.sub(r"\s", "", body))
                if need <= 0:
                    break
                if need < len(re.sub(r"\s", "", para)) + 5:
                    body += "甲" * need      # 精确补齐，确保落点可控
                    break
                body += para
                if len(re.sub(r"\s", "", body)) > (n_target / 3) * i - 30 and i <= 3:
                    body += f"{i}\n\n"
                    i += 1
            return body

        for n_target, want_in_band in ((11999, False), (12000, True),
                                       (16000, True), (16001, False)):
            p = None
            try:
                with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False,
                                                 encoding="utf-8") as tf:
                    tf.write(_mk_len(n_target))
                    p = tf.name
                code, out = run(mss, "--text", p, "--title", "篇幅边界锁定用例")
                in_band = "在 12000-16000 带内" in out
                if in_band != want_in_band:
                    fails.append(f"mss/F1边界 {n_target} 字: 判为「{'带内' if in_band else '偏离'}」，"
                                 f"应「{'带内' if want_in_band else '偏离'}」（AT-01 闭区间边界漂移）")
                if not want_in_band and "总字数不在 12000-16000" not in out:
                    fails.append(f"mss/F1边界 {n_target} 字: 越界却未报硬门文案「总字数不在 12000-16000」")
                if not want_in_band and code != 3:
                    fails.append(f"mss/F1边界 {n_target} 字: 退出码 {code}（应 3——越界须触硬门）")
            finally:
                if p:
                    os.unlink(p)
    else:
        fails.append("check-mss 或 mss fixtures 缺失（MSS 机检对拍回归丢失）")

    # --- 12. 七步法命名锚点存在性（防旧名回流: 03-细纲.md/05-正文.md 已禁）---
    for anchor in (ANCHOR_XIGANG, ANCHOR_RUNSE):
        if not (ROOT / anchor).exists():
            fails.append(f"七步法命名锚点缺失: {anchor}（旧名回流或夹具丢失）")

    # --- 13. check-process 自洽核验（正例过 / 结论项数被改大 1 必报 ❌ / 陈旧 MSS 分必报 ⚠️）---
    tmp = ROOT / "tests" / ".tmp"
    code, out = run(PROCESS, tmp / "proc-ok")
    if code != 0:
        fails.append(f"check-process/proc-ok: 退出码 {code}（应 0——合规报告误杀）\n{out}")
    code, out = run(PROCESS, tmp / "proc-bad")
    if code != 3:
        fails.append(f"check-process/proc-bad: 退出码 {code}（应 3——结论项数与裁决表脱节未被抓住）")
    if "自洽性断裂" not in out:
        fails.append("check-process/proc-bad: 报错文案未点名「自洽性断裂」（定位信息不足）")
    code, out = run(PROCESS, tmp / "proc-stale")
    if code != 2:
        fails.append(f"check-process/proc-stale: 退出码 {code}（应 2——结论引用陈旧 MSS 分未被抓住）")
    if "88.8" not in out or "77.0" not in out:
        fails.append("check-process/proc-stale: 报错文案未同时点名陈旧分 88.8 与机检节分值 77.0（定位信息不足）")
    code, _ = run(PROCESS, ROOT / "tests" / "nonexistent-dir")
    if code != 1:
        fails.append(f"check-process 路径不存在: 退出码 {code}（应 1——用法/输入错误，禁假绿灯）")
    # 夹具收口：正/反例目录跑完即清——残留 .tmp 会随打包混进分发件（包体平账多出条目），
    # 且旧反例被下轮 _proc_fixtures 复用前会静默改变回归输入
    shutil.rmtree(tmp, ignore_errors=True)

    if fails:
        print("❌ 回归失败:")
        print("\n".join(f"  - {f}" for f in fails))
        sys.exit(1)
    print("✅ 回归全过（9 脚本全覆盖 + check-all 一键门×金标准）: metrics good=0/bad=3≥5项(+fragment) + 段落均匀/虚词超限❌ + check-ai good=0/bad=2 | check-length 片段=0/整篇❌=3 + --first-twist 双锚句✅/❌ + --intro 锚句双态✅/❌ + 末章/尾声三态✅ + 篇幅带边界✅/❌ + midpoint/platform✅ | "
          "consistency=0 | artifacts good=0/bad=3 + G项(annot章末钩全在位) | "
          "check-all mini-good=0/mini-bad≠0（门禁与金标准不许打架） | "
          "整篇核验步/14-15 标题引号/H-I 红线事实 在位 | "
          "mss good=0/MSS≥80 机检匹配高、bad=3/59封顶≥5硬门、person-3rd F=30 禁返还白送、七步法命名锚点锁定 | "
          "fingerprint 同型=2/差异=0/同名目录=2/重复传同文件=0 | "
          "process 正例=0/自洽断裂=3/陈旧分=2/坏路径=1")
    sys.exit(0)


if __name__ == "__main__":
    main()
