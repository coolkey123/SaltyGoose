#!/usr/bin/env python3
"""check-process.py — 工序留痕核验（阶段 6 终审前必跑）

用法:
  python3 check-process.py <项目目录>

为什么要这个脚本（实测教训）:
  05-终审报告.md 的「终审工序执行记录」「裁决表」是**手抄**进模板的——
  机检输出 → 人工转录 → 报告，中间没有脚本直连。女帝的第一天实战中,
  删除两条不适用的工序后, 裁决表被顺手写成「六项门槛全过」而表内只剩 5 行,
  结论句毫无察觉（人眼只读结论不数行）。这类"自洽性断裂"机器一秒能查, 人眼未必。

三项核验:
  P1 工序编号连续  工序表 # 列须 1..N 无缺号、无重号（删工序后须重排）
  P2 裁决自洽      结论句点名的项数 N 须等于裁决表数据行数；表内不得有占位符
                   （⚠️/待核/未测/—/TBD）——有意保留的"未执行"必须明写原因, 不许只留符号
  P3 机检数字溯源  结论句/裁决表里的 MSS 分值须在「机检数字报告」节中出现
                  （节序无关——非机检节引用的每个分值都须能在机检节找到，禁取全文
                   首匹配；防结论分与实际机检分脱节: 改稿后重跑机检, 报告分未更新）

退出码: 0 = 三项全过; 1 = 用法错误/文件不存在; 2 = ⚠️ 级（须人工确认）; 3 = ❌ 级（须改）
"""
import re
import sys
from pathlib import Path

PLACEHOLDER = ('⚠️', '待核', '未测', '未核', 'TBD', '____', '—', '-', 'N/A')


def find_report(d: Path):
    """双报告制：核验对象 = 05-终审报告.md（工序表/裁决表/结论句都在终审报告）；
    无终审报告才退 05-初审报告.md 或任一 05-*.md（旧单报告制品降级兼容）。"""
    for pat in ('05-终审报告.md', '05-初审报告.md', '05-*.md'):
        hits = sorted(d.glob(pat))
        if hits:
            return hits[0]
    return None


def table_after(lines, header_kw):
    """返回表头含 header_kw 的表格数据行（跳过表头与分隔行）。"""
    for i, ln in enumerate(lines):
        s = ln.strip()
        if s.startswith('|') and header_kw in s:
            rows = []
            for ln2 in lines[i + 1:]:
                s2 = ln2.strip()
                if not s2.startswith('|'):
                    break
                if re.match(r'^\|[\s:|-]+\|$', s2):
                    continue
                rows.append([c.strip() for c in s2.strip('|').split('|')])
            return rows
    return None


def main():
    if any(a in ('-h', '--help') for a in sys.argv[1:]):
        print(__doc__ or '用法: check-process.py <项目目录>')
        sys.exit(0)
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    d = Path(sys.argv[1])
    if not d.is_dir():
        print(f'❌ 目录不存在: {d}')
        sys.exit(1)
    f = find_report(d)
    if not f:
        print(f'❌ 未找到 05-终审报告.md / 05-初审报告.md（{d}）')
        sys.exit(1)
    text = f.read_text(encoding='utf-8-sig')
    lines = text.splitlines()
    bad, warn = [], []

    print(f'=== P 工序留痕核验（{f.name}）===')

    # P1 工序编号连续
    procs = table_after(lines, '工序')
    if procs is None:
        print('  ℹ️ P1 跳过：未识别到「工序」表')
    else:
        nums = []
        for r in procs:
            m = re.match(r'^\d+$', r[0]) if r else None
            nums.append(int(r[0]) if m else None)
        if any(n is None for n in nums):
            print(f'  ⚠️ P1 工序表存在非数字编号行：{nums}')
            warn.append('P1 工序表编号非纯数字')
        elif nums != list(range(1, len(nums) + 1)):
            print(f'  ❌ P1 工序编号不连续：{nums}（应为 1..{len(nums)}——删工序后须重排）')
            bad.append('P1 工序编号不连续')
        else:
            print(f'  ✅ P1 工序编号连续 1..{len(nums)}（共 {len(nums)} 道）')

    # P2 裁决自洽
    verdict = table_after(lines, '门槛')
    concl = [ln.strip() for ln in lines
             if ln.strip().startswith('**终审结论')]
    if verdict is None:
        print('  ℹ️ P2 跳过：未识别到「裁决」表')
    else:
        n_rows = len(verdict)
        ph = [r[0] for r in verdict
              if len(r) >= 4 and any(p == r[3] or r[3].startswith(p) for p in PLACEHOLDER)]
        if ph:
            print(f'  ⚠️ P2 裁决表含占位结论 {len(ph)} 行：{"、".join(ph[:5])}'
                  f'（保留"未执行"项须在行内写明未执行原因, 不能只留符号）')
            warn.append('P2 裁决表含占位结论')
        if not concl:
            print('  ⚠️ P2 未找到「终审结论」句，无法核对项数')
            warn.append('P2 缺终审结论句')
        else:
            m = re.search(r'([一二三四五六七八九十两\d]+)\s*项', concl[0])
            said = None
            if m:
                cn = {'一': 1, '二': 2, '两': 2, '三': 3, '四': 4, '五': 5,
                      '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}
                said = cn.get(m.group(1), None) or (
                    int(m.group(1)) if m.group(1).isdigit() else None)
            if said is None:
                print(f'  ✅ P2 结论句未点名项数（{concl[0][:40]}），不核项数；表内 {n_rows} 行')
            elif said != n_rows:
                print(f'  ❌ P2 结论句说「{said} 项」，裁决表实为 {n_rows} 行——自洽性断裂')
                bad.append('P2 结论项数与裁决表行数不符')
            else:
                print(f'  ✅ P2 结论项数 {said} = 裁决表 {n_rows} 行')

    # P3 机检数字溯源（节序无关）：非机检节引用的 MSS 分值须能在机检节找到
    #   ——禁取全文首匹配：机检节排在结论/裁决之前时，首匹配恒为机检节自身的值，
    #   结论里的陈旧分永远查不出来（in_detail 恒真，检查形同虚设）
    # 双报告制：机检节在**初审报告**里（MSS 数字报告的载体），终审报告
    # 的结论/裁决引用它的分值——溯源跨两份报告；无初审报告时退终审报告自身。
    f_first = d / '05-初审报告.md'
    src_text = f_first.read_text(encoding='utf-8-sig') if f_first.exists() else text
    segs = re.split(r'^## ', src_text, flags=re.M)
    head_seg, body_segs = segs[0], segs[1:]
    detail = '\n'.join(s for s in body_segs if '机检' in s.split('\n')[0])
    claims = []
    # claims 面 = 终审报告的非机检节（结论/裁决在终审报告）；初审报告自身节不参与 claims
    segs_t = re.split(r'^## ', text, flags=re.M)
    head_t, body_t = segs_t[0], segs_t[1:]
    for s in [head_t] + [x for x in body_t if '机检' not in x.split('\n')[0]]:
        claims.extend(re.findall(r'MSS[^\n]{0,20}?(\d{2,3}\.\d)', s))
    if not claims:
        print('  ℹ️ P3 跳过：未找到 MSS 分值')
    else:
        stale = [v for v in dict.fromkeys(claims) if v not in detail]
        if stale:
            src = list(dict.fromkeys(re.findall(r'MSS[^\n]{0,20}?(\d{2,3}\.\d)', detail)))
            hint = (f'（机检节分值为 {"、".join(src)}）' if src
                    else '（未识别到机检节或节内无 MSS 分值）')
            print(f'  ⚠️ P3 MSS {"、".join(stale)} 未在「机检数字报告」节内出现{hint}'
                  f'——结论分与机检分可能脱节（改稿后未重跑？）')
            warn.append('P3 MSS 分未在机检节溯源')
        else:
            print(f'  ✅ P3 MSS {"、".join(dict.fromkeys(claims))} 在机检数字报告节内有源')

    if bad:
        print(f'\n❌ {len(bad)} 项须改：{bad}')
        sys.exit(3)
    if warn:
        print(f'\n⚠️ {len(warn)} 项须人工确认：{warn}')
        sys.exit(2)
    print('\n✅ 工序留痕三项全过')
    sys.exit(0)


if __name__ == '__main__':
    main()
