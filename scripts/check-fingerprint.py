#!/usr/bin/env python3
"""check-fingerprint.py — 盐选七步法 结构指纹同质化机检（AT-47/AT-48，见 references/fingerprint.md）

用法:
  python3 scripts/check-fingerprint.py <目录 | 08-结构指纹.md ...>

作用:
  解析每篇的六维结构指纹（封闭枚举），两两比对；
  任一对 ≥2 维取同一枚举值 = 同型（⚠️）——命中 AT-46「连续 3 篇不得同一故事模式」红线预警。
  传目录时自动递归收集 **/08-结构指纹.md；传文件时直接比对给定篇目。

退出码: 0=无同型; 2=存在同型预警; 1=用法错误/解析失败。
"""
import re
import sys
from collections import Counter
from pathlib import Path

DIMS = ["叙事起点", "主角行动模式", "核心反转类型",
        "核心意象类别", "关系翻转方向", "付费卡点触发情境"]
MIN_OVERLAP = 2  # 两篇 ≥2 维取同一枚举值 = 同型（AT-48）


def parse_card(path):
    """从 08-结构指纹.md 抽取六维键值（容忍 -/*/加粗/编号前缀）。"""
    d = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        m = re.match(r'^\s*[-*]?\s*\**\s*([^:：*]+?)\s*\**\s*[:：]\s*(.+?)\s*$', line)
        if not m:
            continue
        key = re.sub(r'^\d+[\.、]\s*', '', m.group(1).strip())
        if key in DIMS:
            d[key] = m.group(2).strip()
    return d


def collect(args):
    files = []
    for a in args:
        p = Path(a)
        if p.is_dir():
            files += sorted(p.glob("**/08-结构指纹.md"))
        elif p.is_file():
            files.append(p)
        else:
            print(f"❌ 路径不存在: {a}")
            sys.exit(1)
    return files


def main():
    # 显式帮助入口：-h/--help 打 docstring 退 0（无参仍退 1，保持 AT-56 用法错误口径）
    if any(a in ("-h", "--help") for a in sys.argv[1:]):
        print(__doc__ or "用法: 见脚本头部 docstring")
        sys.exit(0)
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    files = collect(args)
    if not files:
        print("❌ 未发现任何 08-结构指纹.md（目录下需有该文件名，或显式传入指纹文件）")
        sys.exit(1)

    files = list(dict.fromkeys(files))  # 同一文件传两遍禁自我比对（自比重合 6 维=假同型）
    cards, disp = {}, {}
    # 禁按目录名做键：两个同名项目目录的第二篇会静默覆盖第一篇，同质化比对直接漏报——
    # 一律按文件路径为键；仅当目录名撞车时显示名升级为完整路径（保住可读性与不丢篇）
    name_cnt = Counter(f.parent.name or f.stem for f in files)
    for f in files:
        d = parse_card(f)
        missing = [k for k in DIMS if k not in d]
        if missing:
            print(f"❌ {f}: 缺维度 {missing}（指纹六维须填全，见 references/fingerprint.md）")
            sys.exit(1)
        key = str(f)
        base = f.parent.name or f.stem
        cards[key] = d
        disp[key] = key if name_cnt[base] > 1 else base

    names = list(cards)
    print(f"结构指纹比对：{len(names)} 篇")
    for n in names:
        print("  · " + disp[n] + ": " + " / ".join(cards[n][k] for k in DIMS))

    warn = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            overlap = [k for k in DIMS if cards[a][k] == cards[b][k]]
            tag = "⚠️ 同型" if len(overlap) >= MIN_OVERLAP else "ok"
            extra = f"（重合：{'、'.join(overlap)}）" if overlap else ""
            print(f"  [{tag}] {disp[a]} × {disp[b]}: 重合 {len(overlap)} 维{extra}")
            if len(overlap) >= MIN_OVERLAP:
                warn.append((disp[a], disp[b], overlap))

    if warn:
        print(f"\n⚠️ 命中同质化预警 {len(warn)} 对（≥{MIN_OVERLAP} 维重合 = 同型，AT-48）；"
              "若落在连续 3 篇窗口 = 触 AT-46 红线 → 回阶段 1 换模式重出（红线不在破格配额内）")
        sys.exit(2)
    print("\n✅ 无同型（任意两篇重合 ≤1 维）")
    sys.exit(0)


if __name__ == "__main__":
    main()
