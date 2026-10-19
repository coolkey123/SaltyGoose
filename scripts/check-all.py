#!/usr/bin/env python3
"""check-all.py — 一键全量门（禁直出执行面的宿主入口）

用法:
  python3 check-all.py                     # 技能本体门: 脚本可用性探针 + 一致性断言 + 回归测试
  python3 check-all.py <项目目录>           # 交付门: 探针 + 一致性 + 产物链对账 + 三件套(03/04 正文类) + 整篇核验
  python3 check-all.py <文件.md> [文件...]  # 预交付门: 探针 + 三件套(对每个文件, 章级 --fragment 口径)

对应 `scripts/README.md` 调用速查: 一键全量门 = 脚本可用性探针 + 一致性 + 字数 + 指标 + AI + 产物链对账。
退出码: 0 = 全过; 1 = 任一子步骤失败(含探针发现脚本损坏)。

纪律:
- 本脚本只做编排, 不含任何测量口径——口径分别在测量脚本与其 docstring 中;
- 三件套 = check-metrics(--fragment) + check-ai + check-length(--fragment); 任一 exit 2/3 = 修完再交
  (SKILL.md "禁直出"条款);
- 整篇完稿核验禁用 --fragment(脚本降级条款见 SKILL.md, 探针失败即降级人工执行同一口径)。
"""
import re
import subprocess
import sys
from pathlib import Path

# 跨平台执行：Windows 下直接以 .py 路径作可执行文件会报 WinError 193，
# 须统一加 sys.executable 前缀（与 tests/run-tests.py 的 run() 对齐）。
PY = [sys.executable]

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

# 整篇核验门槛 = AT-01 篇幅带下限。低于此数的样本按切片/章级处理，跳过整篇门。
FULL_MIN_CHARS = 12000
MEASURERS = ["check-length.py", "check-metrics.py", "check-ai.py",
             "check-consistency.py", "check-artifacts.py", "check-all.py",
             "check-fingerprint.py", "check-mss.py", "check-process.py"]


def run(label, cmd):
    print(f"\n=== {label} ===")
    r = subprocess.run([str(c) for c in (PY + list(cmd))], capture_output=True, text=True)
    if r.stdout:
        print(r.stdout.rstrip())
    if r.stderr:
        print(r.stderr.rstrip())
    ok = r.returncode == 0
    print(f"{'✅' if ok else '❌'} {label}: exit {r.returncode}")
    return ok


def probe():
    """脚本可用性探针: 逐脚本 py_compile(与 check-consistency 内置探针同口径)；
    cfile 投临时目录——默认写法会把 __pycache__/*.pyc 落进包体，污染交付目录"""
    print("=== 脚本可用性探针 ===")
    import py_compile, os, tempfile
    ok = True
    with tempfile.TemporaryDirectory() as td:
        for tool in MEASURERS:
            p = SCRIPTS / tool
            if not p.exists():
                print(f"❌ {tool} 不存在（工具链不全——降级协议见 SKILL.md 脚本降级条款）")
                ok = False
                continue
            try:
                py_compile.compile(str(p), cfile=os.path.join(td, "probe.pyc"), doraise=True)
                print(f"✅ {tool} 可编译")
            except py_compile.PyCompileError as e:
                print(f"❌ {tool} 不可编译: {e}")
                ok = False
    return ok


def trio(f: Path):
    """三件套自检(章级 --fragment 口径)——禁直出的预交付门"""
    ok = run(f"指标 {f.name}", [SCRIPTS / "check-metrics.py", f, "--fragment"])
    ok &= run(f"AI味 {f.name}", [SCRIPTS / "check-ai.py", f])
    ok &= run(f"字数 {f.name}", [SCRIPTS / "check-length.py", f, "--fragment"])
    return ok


def fullcheck(project: Path):
    """整篇核验（禁 --fragment）——补聚合门此前对 04/05 只走章级 --fragment 的落差。

    整篇过门禁用 --fragment；本步对净稿/正文取全文口径：
    样本 ≥ AT-01 篇幅下限（12000 字）→ 跑真整篇门（check-length / check-metrics 不带 --fragment），
    结果计入通过与否；样本不足下限（切片/章级 fixture）→ 打印跳过提示，不判失败
    （整篇完稿核验须另跑不带 --fragment，见 SKILL.md 禁直出 / 脚本降级条款）。"""
    cands = [p for p in (sorted(project.glob("04-*净稿*.md")) + sorted(project.glob("03-*正文*.md")))
             if p.is_file()]
    print('\n=== 整篇核验（禁 --fragment）===')
    if not cands:
        print("ℹ️ 未发现 03-正文.md / 04-正文净稿.md，整篇核验跳过")
        return True
    ok = True
    for f in cands:
        r = subprocess.run(PY + [str(SCRIPTS / "check-length.py"), str(f), "--fragment"],
                           capture_output=True, text=True)
        m = re.search(r'全文:\s*(\d+)\s*字', r.stdout)
        total = int(m.group(1)) if m else 0
        if total < FULL_MIN_CHARS:
            print(f"ℹ️ 整篇核验跳过 {f.name}（{total} 字 <{FULL_MIN_CHARS} 字（AT-01 下限）——"
                  f"切片/章级样本；整篇完稿须达 AT-01 篇幅带、禁用 --fragment）")
            continue
        ok &= run(f"整篇字数 {f.name}（禁 --fragment）", [SCRIPTS / "check-length.py", f])
        ok &= run(f"整篇指标 {f.name}（禁 --fragment）", [SCRIPTS / "check-metrics.py", f])
    return ok


def main():
    # 显式帮助入口：-h/--help 打 docstring 退 0。
    # 注意：**无参是本脚本的合法用法**——无参 = 跑「探针 + 一致性 + 金标准回归」全量自检，
    # 退出码由自检结果决定（全过 0 / 有失败非 0），不是用法错误退 1。
    # 这一点与其他脚本不同（其余脚本无参 = 用法错误退 1），因为 check-all 本身是聚合门。
    if any(a in ("-h", "--help") for a in sys.argv[1:]):
        print(__doc__ or "用法: 见脚本头部 docstring")
        sys.exit(0)
    args = sys.argv[1:]
    ok = probe()
    ok &= run("一致性断言(技能本体口径)", [SCRIPTS / "check-consistency.py"])

    if not args:
        ok &= run("回归测试(金标准样例对拍)", [ROOT / "tests" / "run-tests.py"])
    else:
        for a in args:
            p = Path(a)
            if p.is_dir():
                ok &= run(f"产物链对账 {p.name}", [SCRIPTS / "check-artifacts.py", p])
                if list(p.glob("05-终审报告.md")) or list(p.glob("05-*.md")):
                    ok &= run(f"工序留痕 {p.name}", [SCRIPTS / "check-process.py", p])
                bodies = sorted(p.glob("03*.md")) + sorted(p.glob("04*.md"))
                bodies = [b for b in bodies if b.is_file()]
                if not bodies:
                    print(f"ℹ️ {p.name} 内未发现 03/04 正文类文件, 三件套跳过（3 项）——非项目目录属正常；完整流程请确认期望检查项已跑，防'跳过=通过'漏检")
                for b in bodies:
                    ok &= trio(b)
                ok &= fullcheck(p)
                if list(p.glob("**/08-结构指纹.md")):
                    ok &= run(f"结构指纹 {p.name}", [SCRIPTS / "check-fingerprint.py", p])
            elif p.is_file():
                ok &= trio(p)
            else:
                print(f"❌ 路径不存在: {p}")
                ok = False

    print("\n" + ("=" * 46))
    print("✅ 一键全量门通过" if ok else "❌ 一键全量门未过——按上方 ❌ 项回修, 修完重跑")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
