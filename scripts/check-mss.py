#!/usr/bin/env python3
"""check-mss.py — 盐选七步法 MSS 机检结构分

用法:
  python3 scripts/check-mss.py --text 04-正文净稿.md [--title 标题] [--intro 导语]
      [--logline 一句话梗概] [--quotes 金句1;金句2;...] [--foreshadow 伏笔回收.csv]
      [--paywall 锚句] [--person 1st|3rd|auto] [--json]
  # --text 首选 机检提交/正文纯文本.md（净稿+双锁标记）；用净稿时须配 --paywall 锚句。
  # 禁直引 03-正文.md——写作期稿未过净稿冻结流程（stage5 R11）。

五模块: F 形式合规 30 + B 标题导语梗概金句 20 + T 结构位置 25 + D 密度代理 15 + R 回收兑现 10
分档（AT-66）: MSS ≥80 机检匹配高 / 60-79 机检匹配低 / <60 机检不匹配
硬门: 12 项可机检硬门任一项触发 → MSS 封顶 59
弱代理: B1-B12 待人工复核清单只提示，不计分，不改变 MSS / 分档 / 硬门 / 红线结论

口径纪律:
  1. 结论只写"机检结构匹配"，不写"过稿评估""爆款预测"；禁"保证过稿/必爆"表述。
  2. 所有关键词匹配必须输出：命中词、位置、窗口、上下文片段。无上下文片段不计分。
  3. 红线词命中只输出"待核提示"，不输出合规结论。
  4. 所有评分项必须可复算，给出分子/分母或窗口位置。

退出码（对齐 AT-56: 2=⚠️ 级待修, 3=❌ 级必修）: 0=硬门全过且 MSS≥80; 2=硬门全过但 MSS<80（机检匹配低/不匹配，需处理）; 3=硬门触发（封顶 59，❌ 级）; 1=用法错误/输入缺失。
机检基线：现行（基线有效期管理见 references/mss-rules.md，到期重校词表与阈值）。
"""
import argparse
import csv
import json
import re
import statistics
import sys
from pathlib import Path

RULES_VERSION = "现行"
CAP_SCORE = 59          # 硬门触发时 MSS 封顶 59
TIER_HIGH, TIER_MID = 80, 60

# ============================ 词表（机检可复算，人工词表维护） ============================
# 冲突/对立词
CONFLICT_WORDS = ["背叛", "揭穿", "撞破", "质问", "指责", "反目", "决裂", "争夺", "翻脸",
                  "羞辱", "挑衅", "对峙", "摊牌", "举报", "谎言", "欺骗", "误会", "排挤",
                  "造谣", "污蔑", "算计", "陷害", "抢走", "夺走", "赶出", "抛弃", "离婚",
                  "分手", "顶罪", "顶包", "撕破脸", "划清界限",
                  # 物证型/异常型冲突词——盐选大量开头是"静物异常"（桌上多了份协议、
                  # 手机里多了条语音），而非人际当场对撞。缺这一类会把真爆款式开头误判为平铺。
                  "解约", "遗嘱", "遗书", "尸检", "诊断书", "病危", "死亡", "血", "骨灰",
                  "空棺", "灵堂", "报警", "警方", "立案", "通缉", "判决", "传票", "鉴定",
                  "复印件", "录音", "监控", "照片", "离婚协议", "亲子鉴定", "债务", "欠条",
                  "失踪", "坠楼", "自杀", "车祸", "抢救", "手术", "绝症", "晚期", "癌",
                  "改嫁", "再婚", "私生子", "冒名", "顶替", "冒领", "被删", "被换", "不见了"]
# 悬念/未知词
SUSPENSE_WORDS = ["突然", "忽然", "竟然", "原来", "真相", "秘密", "没想到", "不料",
                  "难道", "究竟", "居然", "线索", "迹象", "预感", "不对劲", "古怪",
                  "奇怪", "消失", "失踪", "昏迷", "失忆", "陌生", "神秘", "幕后", "隐瞒"]
# 钩子词（按类型分四类，用于卡点后 300 字 ≥3 且类型去重）
HOOK_WORDS = {
    "动作": ["却", "但", "然而", "可是", "直到", "话音未落", "门开了", "下一秒",
             "转眼", "回头", "转身", "站住", "慢着", "冲过来", "扑过来"],
    "疑问": ["为什么", "怎么", "怎么回事", "难道", "究竟", "是谁", "什么",
             "？", "?", "吗"],
    "信息": ["电话", "短信", "消息", "语音", "病历", "报告", "照片", "遗嘱",
             "名单", "账户", "记录", "监控", "聊天记录"],
    "情绪": ["心一沉", "心头一紧", "猛地", "顿时", "瞬间", "骤然", "愣住", "怔住"],
}
# 情绪词（拐点）
EMOTION_WORDS = ["恨", "爱", "怕", "恐惧", "愤怒", "委屈", "心酸", "痛", "哭",
                 "泪", "崩溃", "绝望", "无助", "羞", "怒", "妒", "嫉", "愧", "疚",
                 "慌", "乱", "沉", "闷", "涩", "酸", "苦", "甜", "暖", "寒", "冷",
                 "咬牙", "颤抖", "发抖", "松了口气", "心头一紧", "心如刀割"]
# 动作动词
ACTION_WORDS = ["推", "拉", "拽", "抱", "摔", "砸", "扔", "踢", "跑", "冲", "扑",
                "抓", "握", "拍", "关", "开", "抬", "低", "转", "退", "进", "出",
                "站", "坐", "跪", "躺", "指", "瞪", "盯", "瞥", "咬", "吞", "吐",
                "走", "来", "去", "站起", "坐下", "回头", "转身", "离开", "跟上"]
# 物件名词
OBJECT_WORDS = ["手机", "电话", "钥匙", "门", "窗", "桌", "杯", "碗", "伞", "包",
                "钱", "卡", "信", "照片", "病历", "药", "刀", "绳", "灯", "镜",
                "车", "票", "屏幕", "报告", "名单", "账户", "监控", "遗嘱"]
# 身体反应词
BODY_WORDS = ["手心", "后背", "汗", "发麻", "腿软", "心口", "喉咙", "眼睛",
              "脑袋", "血", "脸", "唇", "指尖", "呼吸", "心跳", "头皮"]
# 推进/反转词
REVERSAL_WORDS = ["却", "原来", "竟然", "其实", "真相", "反转", "不料", "没想到",
                  "居然", "偏偏", "反而", "这才", "就在这时", "刹那间", "骤然",
                  "陡然", "猛地", "这才明白", "万万没想到"]
# 打脸/爽点词
SLAP_WORDS = ["打脸", "跪下", "道歉", "认错", "后悔", "狼狈", "目瞪口呆",
              "惊呆", "全场", "众人", "哄笑", "嘲讽", "闭嘴", "哑然",
              "无地自容", "扬眉吐气", "翻身", "解气", "脸色煞白", "说不出话"]
# 困境词
DIFFICULT_WORDS = ["走投无路", "没有办法", "别无选择", "不得不", "万一",
                   "来不及", "赶不上", "凑不齐", "交不起", "活不下去", "撑不住",
                   "拖不下去", "只能"]
# 暗示词（反转铺垫）
HINT_WORDS = ["似乎", "仿佛", "好像", "隐约", "依稀", "些许", "微微", "一丝",
              "某种", "据说", "听说", "传闻", "像是"]
# 铺垫词
PAVE_WORDS = ["曾经", "先前", "之前", "那天", "当初", "那时", "往日", "旧事",
              "早先", "早些时候", "当初那个"]
# 代价词
COST_WORDS = ["代价", "付出", "赔偿", "失去", "牺牲", "后果", "承担", "负责",
              "赔", "倒贴", "净身出户", "一无所有"]
# 感官词
SENSE_WORDS = ["看见", "见", "望", "瞅", "听见", "听", "闻", "嗅", "摸", "触",
               "尝", "冰冷", "温热", "刺痛", "香气", "臭味", "亮", "暗", "吵",
               "静", "安静", "寂静", "嘈杂", "潮湿", "干燥", "风", "雨", "雪"]
# 解释词（B2 潜台词弱代理）
EXPLAIN_WORDS = ["因为", "所以", "其实", "说明", "表示", "意味着", "也就是说"]
# 连接词（B7 AI 结构味弱代理）
CONNECT_WORDS = ["然后", "接着", "随后", "同时", "此外", "而且", "并且",
                 "不过", "但是", "然而", "因此", "所以"]
# 总结词（B6 结局余味弱代理 + 章末钩子排除项）
SUMMARY_WORDS = ["总之", "综上所述", "总的来说", "归根结底", "由此可见", "就这样"]
# 留白/情绪落点/讨论点词（B6）
BLANK_WORDS = ["也许", "或许", "大概", "可能", "仿佛", "像是", "无人",
               "从此", "许多年", "据说", "据说后来"]
DISCUSS_WORDS = ["谁", "为什么", "怎么", "究竟", "难道", "值不值", "该不该"]
# 目标词/动机词（B5 反派动机弱代理）
TARGET_WORDS = ["想要", "必须", "一定要", "打算", "计划", "决定", "目标",
                "目的是", "为了", "非得", "非要把"]
MOTIVE_WORDS = ["因为", "由于", "既然", "凭什么", "不甘", "不愿", "怨恨",
                "记恨", "嫉妒", "眼红", "咽不下"]
# 身份/特征词（B4 人设记忆点弱代理）
IDENTITY_WORDS = ["医生", "老师", "编辑", "保姆", "助理", "秘书", "护士", "记者",
                  "律师", "主妇", "学生", "女儿", "母亲", "姐姐", "妹妹", "妻子",
                  "前妻", "婆婆", "老板", "总裁", "司机", "护工", "月嫂", "保姆",
                  "厨师", "裁缝", "程序员", "设计师", "房东", "租客", "实习生"]
# 修辞词（B8 语言风格弱代理）
RHETORIC_WORDS = ["像", "如同", "仿佛", "好似", "宛如", "似的", "一般", "犹如"]
# 标题停用字（核心词提取用）
TITLE_STOP = {"的", "了", "是", "我", "你", "他", "她", "在", "和", "与", "有", "就",
              "都", "而", "及", "着", "或", "一个", "这个", "那个", "我们", "你们",
              "他们", "以及", "之后", "时候", "那些", "这些", "那个", "把", "被",
              "让", "向", "从", "对", "为", "以", "之", "其", "于"}
# 红线词表（命中只输出待核提示，不影响 MSS）
RED_LINE_WORDS = {
    "政治": ["颠覆国家", "分裂国家", "恐怖袭击", "暴恐", "极端组织", "邪教", "法轮"],
    "色情": ["性交", "做爱", "裸体", "淫秽", "情色", "生殖器", "色情"],
    "暴力": ["血腥", "分尸", "割喉", "虐杀", "爆炸物制作", "毒品制作", "制毒"],
    "自残": ["自杀", "割腕", "上吊", "服毒", "轻生", "想死"],
    "霸凌": ["校园霸凌", "霸凌", "围殴", "凌辱", "殴打同学"],
    "性别对立": ["普信男", "田园女权", "男人没一个好东西", "女人就该", "婚lv"],
    "地域歧视": ["河南人偷", "东北人都是", "某地人都是", "外地人都是"],
    "医疗伪科学": ["包治百病", "治愈癌症", "根治糖尿病", "神药", "偏方治绝症"],
    "法律伪常识": ["杀人不犯法", "欠债不用还", "假离婚躲债", "未成年犯罪不判刑"],
}
# 赛道粗分类关键词（信息项不计分）
GENRE_WORDS = {
    "现实情感": ["婚姻", "离婚", "彩礼", "婆媳", "出轨", "挽回", "相亲", "夫妻"],
    "生活化悬疑": ["失踪", "命案", "尸体", "警察", "凶杀", "悬案", "真相"],
    "脑洞短篇": ["穿越", "重生", "系统", "魂穿", "替身", "循环", "无限"],
    "言情甜虐": ["暗恋", "心动", "追妻", "火葬场", "甜", "虐", "白月光", "初恋"],
}
MARKDOWN_STRUCT = re.compile(r'^\s*(#{1,6}\s|\||>|```|---\s*$|\*\*)')
PARA_SPLIT = re.compile(r'\n\s*\n|\n')


# ============================ 基础测量 ============================
def clean_lines(text):
    """剔 markdown 结构行（标题/表格/引用/代码块/分隔线），保留正文行。"""
    out = []
    in_code = False
    for ln in text.splitlines():
        if ln.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code or MARKDOWN_STRUCT.match(ln):
            continue
        out.append(ln)
    return out


def body_text(text):
    return "\n".join(clean_lines(text))


def paragraphs(text):
    """按换行切段（剔空段与 markdown 结构行）。"""
    paras = [p.strip() for p in PARA_SPLIT.split(body_text(text)) if p.strip()]
    return paras


def para_len_stats(text):
    paras = paragraphs(text)
    if not paras:
        return {"n": 0, "le50": 0.0, "le30": 0.0, "avg": 0.0}
    lens = [len(re.sub(r'\s', '', p)) for p in paras]
    n = len(lens)
    return {
        "n": n,
        "le50": sum(1 for x in lens if x <= 50) / n,
        "le30": sum(1 for x in lens if x <= 30) / n,
        "avg": sum(lens) / n,
        "max": max(lens),
    }


def sentence_lens(text):
    """按句末标点切分，返回句长列表。"""
    t = body_text(text)
    parts = re.split(r'(?<=[。！？!?…；;])', t)
    out = []
    for p in parts:
        s = re.sub(r'\s', '', p)
        if s:
            out.append(len(s))
    return out


def avg_sentence_len(text):
    ls = sentence_lens(text)
    return sum(ls) / len(ls) if ls else 0.0


def sentence_len_std(text):
    ls = sentence_lens(text)
    return statistics.pstdev(ls) if len(ls) > 1 else 0.0


def halfwidth_ratio(text):
    t = body_text(text)
    half = len(re.findall(r'[,.;:!?\'"]', t))
    total = len(re.findall(r'[，。；：！？,…;:!?\.,\'"]', t))
    return (half / total) if total else 0.0


def count_word(word, text):
    """子串计数（与 check-ai.py count_word 同口径，防机检面分裂）。"""
    return text.count(word)


def find_hits(words, text):
    """返回 [(词, 位置)]，位置为正文内字符索引；供输出上下文片段。"""
    hits = []
    for w in words:
        start = 0
        while True:
            i = text.find(w, start)
            if i < 0:
                break
            hits.append((w, i))
            start = i + len(w)
    return sorted(hits, key=lambda x: x[1])


def context_of(text, pos, w, pad=12):
    a = max(0, pos - pad)
    b = min(len(text), pos + len(w) + pad)
    return text[a:b].replace("\n", "⏎")


# ============================ F 形式合规（30） ============================
def score_F(text, person_mode):
    det, hard = [], []
    score = 0.0
    t = body_text(text)
    n_chars = len(re.sub(r'\s', '', t))

    # F1 总字数 12000-16000（硬门1，AT-01）—10 分
    if 12000 <= n_chars <= 16000:
        score += 10
        det.append(("F1 总字数", 10, 10, f"{n_chars} 字，在 12000-16000 带内"))
    else:
        det.append(("F1 总字数", 0, 10, f"{n_chars} 字，偏离 12000-16000"))
        hard.append("总字数不在 12000-16000")

    # F2 分节合规（纯数字标记/编号连续/≥3 节；硬门7）—8 分
    # 规范口径：纯数字独立成行（1/2/3，不带点/括号等任何符号）；N./【N】/## N. 为非规范写法
    lines = clean_lines(text)
    sec_idx = [i for i, ln in enumerate(lines) if re.match(r'^\s*\d+\s*$', ln)]
    nums = [int(re.match(r'^\s*(\d+)\s*$', lines[i]).group(1)) for i in sec_idx]
    # 节数只认「从 1 起连续递增的分节序列」——正文里孤立成行的数字（年份/金额/序号，
    # 如 1987、3000）不算节。否则 1 真节 + 2 孤立数字会被误算成 3 节而绕过「分节数 <3」硬门。
    seq_len = 0
    for expect, n in enumerate(nums, start=1):
        if n == expect:
            seq_len += 1
        else:
            break
    mixed = [ln.strip() for ln in lines
             if re.match(r'^\s*第[一二三四五六七八九十\d]+[章节]', ln)]
    f2 = 0.0
    f2_note = []
    if mixed:
        hard.append("混用「第x章/第x节」分节格式")
        f2_note.append(f"命中混用格式 {len(mixed)} 处（如「{mixed[0][:12]}」）")
    elif not sec_idx:
        hard.append("未使用纯数字分节（1/2/3 独立成行，不带任何符号）")
        f2_note.append("未检测到纯数字分节标记")
        old_dot = [ln.strip() for ln in lines if re.match(r'^\s*\d+\.', ln)]
        if old_dot:
            hard.append("检测到非规范分节标记「N.」（须纯数字独立成行）")
            f2_note.append(f"命中带符号的「N.」分节标记 {len(old_dot)} 处（如「{old_dot[0][:12]}」）——须改为纯数字独立成行")
    else:
        f2 += 3
        f2_note.append(f"纯数字分节 {len(sec_idx)} 处")
        seq_ok = nums == list(range(1, len(nums) + 1))
        if seq_ok:
            f2 += 3
            f2_note.append(f"编号 1-{nums[-1]} 连续递增")
        else:
            hard.append("分节编号不连续/重复/倒序")
            f2_note.append(f"编号序列异常：{nums[:12]}")
        if seq_len >= 3:
            f2 += 2
            f2_note.append(f"分节数 {seq_len} ≥3")
        else:
            hard.append(f"分节数 {seq_len} <3（需 ≥3 章）")
            f2_note.append(f"分节数 {seq_len} <3（硬门）")
    score += f2
    det.append(("F2 分节合规", f2, 8, "；".join(f2_note)))

    # F3 段落 ≤50 字占比 ≥60%（硬门5）—6 分
    # 删 50-60% 警示带分支——文档四处（AT-63/mss-rules 硬门5/口径表/quality-gate P0）
    # 一致称 60% 为硬门，旧代码 50% 才触发 hard 与文档打架（名实不符：hard 文案自写 <60%）。
    # 硬门语义 = 二元：不过线即 0 分 + 触发，不再 graduated 放行。
    ps = para_len_stats(text)
    paras = paragraphs(text)
    n_le50 = sum(1 for p in paras if len(re.sub(r'\s', '', p)) <= 50)
    if ps["le50"] >= 0.6:
        score += 6
        det.append(("F3 段落≤50字占比", 6, 6,
                    f"{ps['le50']*100:.0f}%（{ps['n']} 段中 ≤50 字 {n_le50} 段）≥60%"))
    else:
        det.append(("F3 段落≤50字占比", 0, 6, f"{ps['le50']*100:.0f}% <60%"))
        hard.append("段落 ≤50 字占比 <60%")

    # F4 平均句长 ≤25—3 分
    avg_s = avg_sentence_len(text)
    if avg_s <= 25:
        score += 3
        det.append(("F4 平均句长", 3, 3, f"{avg_s:.1f} 字 ≤25"))
    elif avg_s <= 35:
        score += 1.5
        det.append(("F4 平均句长", 1.5, 3, f"{avg_s:.1f} 字，25-35 警示带"))
    else:
        det.append(("F4 平均句长", 0, 3, f"{avg_s:.1f} 字 >35"))

    # F5 对话符号「」（硬门6）—3 分；全文无任何对话痕迹时豁免并标注
    quote_cnt = t.count("「") + t.count("」")
    dq = len(re.findall(r'["""\']', t))
    if quote_cnt >= 2:
        score += 3
        det.append(("F5 对话符号「」", 3, 3, f"「」共 {quote_cnt} 个，合规"))
    elif dq >= 2:
        det.append(("F5 对话符号「」", 0, 3, f"检测到 {dq} 个弯引号但未用「」"))
        hard.append("对话未使用「」")
    else:
        score += 3
        det.append(("F5 对话符号「」", 3, 3, "全文未检测到对话痕迹，本项豁免（建议人工确认确无对话）"))

    # F 扣分项（强提示"重扣分"落地）：前 500 字无"我" -2；半角标点 >10% -2
    # 一称"我"频率仅适用一称稿（AT-64：三称稿不判）——第三人称稿整项不扣分，
    # 禁"先扣再返还"：未扣分时返还 = 白送 2 分（显式 --person 3rd 的稿子凭空加分）
    first500 = re.sub(r'\s', '', t)[:500]
    wo = count_word("我", first500)
    if person_mode == "3rd":
        det.append(("F- 前500字「我」", 0, 0,
                    f"{wo} 次——第三人称稿（--person 3rd），一称口径不适用（AT-64），本项不扣分"))
    elif wo >= 5:
        det.append(("F- 前500字「我」", 0, 0, f"{wo} 次，第一人称达标"))
    elif wo >= 1:
        score -= 2
        det.append(("F- 前500字「我」", -2, 0, f"仅 {wo} 次，强提示扣 2 分"))
    else:
        score -= 2
        det.append(("F- 前500字「我」", -2, 0, "前 500 字无「我」，强提示扣 2 分"))
    hw = halfwidth_ratio(text)
    if hw > 0.10:
        score -= 2
        det.append(("F- 半角标点", -2, 0, f"占比 {hw*100:.1f}% >10%，强提示扣 2 分"))
    else:
        det.append(("F- 半角标点", 0, 0, f"占比 {hw*100:.1f}% ≤10%"))

    return max(0.0, score), det, hard, n_chars


# ============================ B 标题导语梗概金句（20） ============================
def core_words(s):
    """标题/导语核心词提取：先按连接性虚字切分，再取 2-6 字中文片段（可复算）。"""
    if not s:
        return []
    parts = re.split(r'[的了是在和与及着或其于把被让向从对为以之而或都也就]', s)
    out = []
    for p in parts:
        for w in re.findall(r'[\u4e00-\u9fff]{2,6}', p):
            if w not in TITLE_STOP and len(w) >= 2:
                out.append(w)
    return list(dict.fromkeys(out))


def score_B(title, intro, logline, quotes):
    det, hard = [], []
    score = 0.0
    # B1 标题长度 ≤15 最佳/16-20 合格/>20 字硬门（硬门2）—6
    tl = len(re.sub(r'\s', '', title or ""))
    if not title:
        det.append(("B1 标题长度", 0, 6, "标题缺失"))
    elif tl <= 15:
        score += 6
        det.append(("B1 标题长度", 6, 6, f"{tl} 字 ≤15，最佳档"))
    elif tl <= 20:
        score += 4
        det.append(("B1 标题长度", 4, 6, f"{tl} 字，16-20 合格档"))
    else:
        det.append(("B1 标题长度", 0, 6, f"{tl} 字 >20"))
        hard.append("标题 >20 字")
    # B2 标题无问号感叹号（硬门3）—4
    if title and re.search(r'[？?！!]', title):
        det.append(("B2 标题标点", 0, 4, "标题含问号/感叹号"))
        hard.append("标题含问号/感叹号")
    else:
        score += 4
        det.append(("B2 标题标点", 4, 4, "无问号/感叹号"))
    # B3 标题冲突词共现（规格：加分项，不计分、不硬门，仅报告）
    hits = find_hits(CONFLICT_WORDS + SUSPENSE_WORDS, title or "")
    if hits:
        det.append(("B3 标题冲突词", 0, 0, f"命中「{hits[0][0]}」（冲突/悬念词共现，加分项不计分）"))
    else:
        det.append(("B3 标题冲突词", 0, 0, "未命中冲突/悬念词（加分项，不计分不硬门）"))
    # B4 导语 80-150（硬门4）—4
    il = len(re.sub(r'\s', '', intro or ""))
    if not intro:
        det.append(("B4 导语字数", 0, 4, "导语缺失"))
        hard.append("导语缺失（需 80-150 字）")
    elif 80 <= il <= 150:
        score += 4
        det.append(("B4 导语字数", 4, 4, f"{il} 字，在 80-150 内"))
    else:
        det.append(("B4 导语字数", 0, 4, f"{il} 字，偏离 80-150"))
        hard.append("导语不在 80-150 字")
    # B5 导语首句冲突/悬念词 —2
    first_sent = re.split(r'[。！？!?…]', intro or "", maxsplit=1)[0]
    hits = find_hits(CONFLICT_WORDS + SUSPENSE_WORDS, first_sent)
    if hits:
        score += 2
        det.append(("B5 导语首句冲突", 2, 2, f"首句命中「{hits[0][0]}」"))
    else:
        det.append(("B5 导语首句冲突", 0, 2, "首句未命中冲突/悬念词"))
    # B6 一句话梗概 ≤50 含冲突/悬念（强提示）—2
    ll = len(re.sub(r'\s', '', logline or ""))
    if not logline:
        det.append(("B6 一句话梗概", 0, 2, "梗概缺失，强提示重扣"))
    elif ll > 50:
        det.append(("B6 一句话梗概", 0, 2, f"{ll} 字 >50，强提示重扣"))
    elif find_hits(CONFLICT_WORDS + SUSPENSE_WORDS, logline):
        score += 2
        det.append(("B6 一句话梗概", 2, 2, f"{ll} 字，含冲突/悬念词"))
    else:
        score += 1
        det.append(("B6 一句话梗概", 1, 2, f"{ll} 字，未含冲突/悬念词"))
    # B7 金句 3-5 句每句 ≤40（强提示）—2
    qs = [q.strip() for q in (quotes or "").split("；") if q.strip()] if quotes else []
    if not qs:
        det.append(("B7 金句", 0, 2, "金句缺失，强提示重扣"))
    elif len(qs) < 3 or len(qs) > 5:
        det.append(("B7 金句", 0, 2, f"{len(qs)} 句，越界 3-5，强提示重扣"))
    elif any(len(re.sub(r'\s', '', q)) > 40 for q in qs):
        over = max(qs, key=lambda q: len(re.sub(r'\s', '', q)))
        det.append(("B7 金句", 0, 2, f"存在 >40 字句（「{over[:14]}…」）"))
    else:
        score += 2
        det.append(("B7 金句", 2, 2, f"{len(qs)} 句，每句 ≤40 字"))
    return score, det, hard


# ============================ T 结构位置（25） ============================
def find_paywall_pos(t, paywall_anchor):
    """返回 (字位, 依据)。显式 [[首锁]] 标记优先；否则 --paywall 锚句等效。

    注：标记与锚句同时存在时的字位互校在 main 流程内做（提示进 tips，不计分）——
    本函数只负责取位，保持单一职责。
    """
    m = re.search(r'\[\[首锁\]\]', t)
    if m:
        return m.start(), "[[首锁]]标记"
    if paywall_anchor:
        i = t.find(paywall_anchor)
        if i >= 0:
            return i, f"锚句「{paywall_anchor[:10]}」"
    return None, None


def score_T(text, paywall_anchor, n_chars):
    det, hard = [], []
    score = 0.0
    t = body_text(text)
    # 分节行在正文（干净坐标）中的字符偏移（章末窗口定位用）
    sec_pos = []
    pos = 0
    for ln in t.splitlines():
        if re.match(r'^\s*\d+\s*$', ln):
            sec_pos.append(pos)
        pos += len(ln) + 1

    # T1 开篇 100 字冲突标记共现（硬门10）—5
    # 共现判定修正：代词类**不具备独立判别力**——"我出门/她上班"同时命中代词+动作词，
    # 句子却可能完全无冲突（身份陈述式平开头，编辑最常拒的一类）。故代词类只作**加成**，
    # 必须与冲突词或后果词任一同在才算第 2 类；单靠「代词+动作」不判过。
    head = t[:100]
    cats = {
        "冲突词": [w for w, _ in find_hits(CONFLICT_WORDS, head)],
        "动作词": [w for w, _ in find_hits(ACTION_WORDS, head)],
        "代词": ["我", "你", "他", "她"] if re.search(r'[我你他她]', head) else [],
        "后果词": [w for w, _ in find_hits(["结果", "从此", "那一刻", "顿时", "瞬间", "再也", "毁了", "完了"], head)],
    }
    hit_cats = {k: v for k, v in cats.items() if v}
    # 实质类 = 冲突/后果（可直接判别）；动作与代词为辅助类，至少须有 1 个实质类支撑
    has_substantive = bool(cats["冲突词"] or cats["后果词"])
    if len(hit_cats) >= 2 and has_substantive:
        score += 5
        det.append(("T1 开篇冲突标记", 5, 5,
                    "；".join(f"{k}:{v[0]}" for k, v in hit_cats.items()) + "（共现≥2 类）"))
    elif len(hit_cats) >= 2:
        # 只有辅助类（动作/代词）凑够两类 = 假阳性放过，判不过并说明原因
        det.append(("T1 开篇冲突标记", 0, 5,
                    "前 100 字命中 " + "+".join(hit_cats) +
                    " 但无冲突词/后果词——疑似身份陈述式平开头（辅助类不独立成立）"))
        hard.append("开头 100 字无冲突/动作/代词/后果词共现（≥2 类）")
    else:
        det.append(("T1 开篇冲突标记", 0, 5,
                    f"前 100 字仅命中 {len(hit_cats)} 类词表（需 ≥2 类共现）"))
        hard.append("开头 100 字无冲突/动作/代词/后果词共现（≥2 类）")

    # T2 前 300 字钩子词 + 困境词 —4
    h300 = t[:300]
    hook_hits = find_hits([w for ws in HOOK_WORDS.values() for w in ws], h300)
    diff_hits = find_hits(DIFFICULT_WORDS, h300)
    t2 = 0.0
    if hook_hits:
        t2 += 2
    if diff_hits:
        t2 += 2
    score += t2
    det.append(("T2 前300字钩子/困境", t2, 4,
                (f"钩子词 {len(hook_hits)} 处（首见「{hook_hits[0][0]}」@{hook_hits[0][1]} 字）；"
                 if hook_hits else f"钩子词 {len(hook_hits)} 处；")
                + f"困境词 {len(diff_hits)} 处"))

    # T3 首锁字位（硬门8）—5；字位 3000-4000 优先，占比 25-35% 旁证兼容
    pw, basis = find_paywall_pos(t, paywall_anchor)
    if pw is None:
        det.append(("T3 首锁字位", 0, 5, "无 [[首锁]] 标记且未提供 --paywall 锚句"))
        hard.append("卡点标记缺失")
    else:
        # 占比口径：首锁前「去空白字数」÷ 全文「去空白字数」，分子分母同一把尺，
        # 与 AT-05「占比 25-35%」的文档表述对齐。若分子取含空白的原始字符位、
        # 分母取去空白字数，空行多的稿占比会被系统性低估。
        pw_chars = len(re.sub(r'\s', '', t[:pw]))
        pct = pw_chars / n_chars * 100 if n_chars else 0
        if 3000 <= pw_chars <= 4000:
            score += 5
            det.append(("T3 首锁字位", 5, 5, f"字位 {pw_chars}（全文 {pct:.1f}%），依据：{basis}；字位 3000-4000 合规"))
        elif 25 <= pct <= 35:
            score += 5
            det.append(("T3 首锁字位", 5, 5, f"字位 {pw_chars}（全文 {pct:.1f}%），依据：{basis}；占比 25-35% 合规"))
        else:
            det.append(("T3 首锁字位", 0, 5,
                        f"字位 {pw_chars}（全文 {pct:.1f}%），依据：{basis}；字位不在 3000-4000 且占比偏离 25-35%"))
            hard.append("首锁偏离全文 25%-35%（字位 3000-4000）")

    # T4 卡点前 200 字情绪词 —3
    if pw is not None:
        pre = t[max(0, pw - 200):pw]
        emo = find_hits(EMOTION_WORDS, pre)
        if emo:
            score += 3
            det.append(("T4 卡点前200字情绪词", 3, 3,
                        f"{len(emo)} 处（首见「{emo[0][0]}」）"))
        else:
            det.append(("T4 卡点前200字情绪词", 0, 3, "卡点前 200 字无情绪词"))
    else:
        det.append(("T4 卡点前200字情绪词", 0, 3, "无卡点位置，跳过"))

    # T5 卡点后 300 字钩子 ≥3 且类型不同 —4
    if pw is not None:
        post = t[pw:pw + 300]
        typed = {}
        for k, ws in HOOK_WORDS.items():
            hh = find_hits(ws, post)
            if hh:
                typed[k] = hh
        total = sum(len(v) for v in typed.values())
        t5 = 4 if len(typed) >= 3 else (2 if len(typed) == 2 else 0)
        score += t5
        det.append(("T5 卡点后300字钩子", t5, 4,
                    f"{total} 处 / {len(typed)} 类（{'、'.join(typed.keys()) or '无'}），要求 ≥3 处且类型不同"))
    else:
        det.append(("T5 卡点后300字钩子", 0, 4, "无卡点位置，跳过"))

    # T6 章末动作钩（每章末 100 字）+ 章末新问题（每章末 200 字）—2+2
    if len(sec_pos) >= 1:
        ends = []
        for i, sp in enumerate(sec_pos):
            ep = sec_pos[i + 1] if i + 1 < len(sec_pos) else len(t)
            ends.append(t[sp:ep])
        no_action, no_new = [], []
        for i, sec in enumerate(ends, 1):
            tail100 = sec[-100:]
            tail200 = sec[-200:]
            act = find_hits(ACTION_WORDS + ["……", "…"], tail100)
            summ = find_hits(SUMMARY_WORDS, tail100)
            if not act or summ:
                no_action.append(i)
            # 去重口径：上节尾 200 字**文子串匹配**——悬念词已在上节尾出现过则不作为新问题，
            # 语义即「与上一章关键词去重」（mss-rules 4.3 口径）。若改用切片列表做精确相等比较，
            # 切片边界几乎永不与词边界对齐，去重会失效、T6b 系统性偏松。
            prev_tail = ends[i - 2][-200:] if i >= 2 else ""
            newq = find_hits(HOOK_WORDS["疑问"], tail200)
            unk = [w for w in find_hits(SUSPENSE_WORDS, tail200)
                   if w[0] not in prev_tail]
            if not (newq or unk):
                no_new.append(i)
        # 连续两章无动作钩 → 硬门11
        consec = any(no_action[i] + 1 == no_action[i + 1] for i in range(len(no_action) - 1))
        if consec:
            hard.append("连续两章章末无动作钩子标记")
            det.append(("T6 章末动作钩", 0, 2, f"第 {no_action} 章章末缺动作钩，且存在连续两章缺失"))
        elif no_action:
            det.append(("T6 章末动作钩", 1, 2, f"第 {no_action} 章章末缺动作钩（非连续，未触硬门）"))
        else:
            score += 2
            det.append(("T6 章末动作钩", 2, 2, f"{len(ends)} 章章末均有动作钩标记"))
        if no_new:
            det.append(("T6 章末新问题", 0, 2, f"第 {no_new} 章章末 200 字无新问题/未知词"))
        else:
            score += 2
            det.append(("T6 章末新问题", 2, 2, f"{len(ends)} 章章末均有新问题或去重后的未知词"))
    else:
        det.append(("T6 章末钩子/新问题", 0, 4, "无分节，跳过"))

    return score, det, hard, pw


# ============================ D 密度代理（15） ============================
def score_D(text):
    det, hard = [], []
    score = 0.0
    t = body_text(text)
    n = len(re.sub(r'\s', '', t))
    per_k = n / 1000 if n else 1

    # D1 情绪词密度 0.8-1.2/千字 —4
    emo = find_hits(EMOTION_WORDS, t)
    dens = len(emo) / per_k if per_k else 0
    if 0.8 <= dens <= 1.2:
        score += 4
        det.append(("D1 情绪词密度", 4, 4, f"{dens:.2f} 个/千字（{len(emo)} 处 ÷ {per_k:.1f} 千字），在 0.8-1.2"))
    elif 0.5 <= dens < 0.8 or 1.2 < dens <= 1.6:
        score += 2
        det.append(("D1 情绪词密度", 2, 4, f"{dens:.2f} 个/千字，贴边带"))
    else:
        det.append(("D1 情绪词密度", 0, 4, f"{dens:.2f} 个/千字，偏离 0.8-1.2"))

    # D2 推进/反转词每 300 字窗口平均 ≥1 —3
    rev = find_hits(REVERSAL_WORDS, t)
    win300 = max(1, n / 300)
    d2 = len(rev) / win300
    if d2 >= 1:
        score += 3
        det.append(("D2 推进/反转词", 3, 3, f"{len(rev)} 处 ÷ {win300:.1f} 个 300 字窗口 = {d2:.2f}/窗口 ≥1"))
    elif d2 >= 0.5:
        score += 1.5
        det.append(("D2 推进/反转词", 1.5, 3, f"{d2:.2f}/窗口，0.5-1 警示带"))
    else:
        det.append(("D2 推进/反转词", 0, 3, f"{d2:.2f}/窗口 <0.5"))

    # D3 打脸/爽点词每 600 字窗口平均 ≥0.5 —3
    slap = find_hits(SLAP_WORDS, t)
    win600 = max(1, n / 600)
    d3 = len(slap) / win600
    if d3 >= 0.5:
        score += 3
        det.append(("D3 打脸/爽点词", 3, 3, f"{len(slap)} 处 ÷ {win600:.1f} 个 600 字窗口 = {d3:.2f}/窗口 ≥0.5"))
    elif d3 >= 0.25:
        score += 1.5
        det.append(("D3 打脸/爽点词", 1.5, 3, f"{d3:.2f}/窗口，贴边带"))
    else:
        det.append(("D3 打脸/爽点词", 0, 3, f"{d3:.2f}/窗口 <0.25"))

    # D4 每 2000 字新名词性词 ≥2 —3（实体名词词表 + 窗口统计，可复算）
    win2000 = max(1, round(n / 2000))
    obj = find_hits(OBJECT_WORDS, t)
    per_win_new = {}
    for w, p in obj:
        k = p // 2000
        per_win_new.setdefault(k, set()).add(w)
    counts = [len(per_win_new.get(i, set())) for i in range(win2000)]
    ok_win = sum(1 for c in counts if c >= 2)
    if ok_win >= max(1, win2000 * 0.6):
        score += 3
        det.append(("D4 新名词性词", 3, 3, f"{ok_win}/{win2000} 个 2000 字窗口 ≥2 个新名词"))
    elif ok_win >= 1:
        score += 1.5
        det.append(("D4 新名词性词", 1.5, 3, f"{ok_win}/{win2000} 个 2000 字窗口 ≥2 个新名词"))
    else:
        det.append(("D4 新名词性词", 0, 3, f"0/{win2000} 个 2000 字窗口达 ≥2 个新名词"))

    # D5 钩子类型轮换率 ≥60% —2（章末钩子类型序列相邻不同占比）
    sec_pos = []
    pos = 0
    for ln in t.splitlines():
        if re.match(r'^\s*\d+\s*$', ln):
            sec_pos.append(pos)
        pos += len(ln) + 1
    seq = []
    for i, sp in enumerate(sec_pos):
        ep = sec_pos[i + 1] if i + 1 < len(sec_pos) else len(t)
        tail = t[sp:ep][-100:]
        types = [k for k, ws in HOOK_WORDS.items() if find_hits(ws, tail)]
        seq.append(types[0] if types else "无")
    if len(seq) >= 2:
        rot = sum(1 for i in range(1, len(seq)) if seq[i] != seq[i - 1]) / (len(seq) - 1)
        if rot >= 0.6:
            score += 2
            det.append(("D5 钩子类型轮换", 2, 2, f"轮换率 {rot*100:.0f}%（序列：{'→'.join(seq)}）≥60%"))
        else:
            det.append(("D5 钩子类型轮换", 0, 2, f"轮换率 {rot*100:.0f}%（序列：{'→'.join(seq)}）<60%"))
    else:
        det.append(("D5 钩子类型轮换", 0, 2, "分节不足，跳过"))
    return score, det, hard


# ============================ R 回收兑现（10） ============================
def score_R(text, title, intro, foreshadow_csv, n_chars):
    det, hard = [], []
    score = 0.0
    t = body_text(text)
    # R1 伏笔回收率 ≥80%（硬门9）—6
    rows = []
    if foreshadow_csv and Path(foreshadow_csv).exists():
        with open(foreshadow_csv, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            heads = reader.fieldnames or []
            if all(c in heads for c in ("回收位置", "回收原句")):
                for r in reader:
                    # 剔除 restkey（None 键：行字段多于表头时 DictReader 把多余值放 list 进 None 键，
                    # 直接 .strip() 会因 list 无 strip 而崩）后再判空行
                    vals = [v for k, v in r.items() if k is not None and isinstance(v, str)]
                    if any(v.strip() for v in vals):
                        rows.append(r)
            # 表头缺必需列 → rows 留空，走下方"字段缺失"分支诚实报缺，不静默按 0% 判
    if foreshadow_csv and not rows:
        det.append(("R1 伏笔回收率", 0, 6, "伏笔回收表为空或字段缺失（须含回收位置/回收原句列）"))
        hard.append("伏笔回收表缺失")
    elif not foreshadow_csv:
        det.append(("R1 伏笔回收率", 0, 6, "未提供伏笔回收表（--foreshadow）"))
        hard.append("伏笔回收表缺失")
    else:
        planted = len(rows)
        rec = sum(1 for r in rows
                  if (r.get("回收位置") or "").strip() and (r.get("回收原句") or "").strip())
        rate = rec / planted if planted else 0
        if rate >= 0.8:
            score += 6
            det.append(("R1 伏笔回收率", 6, 6, f"{rec}/{planted} = {rate*100:.0f}% ≥80%"))
        else:
            # 删 60-80% 警示带分支——AT-22 与 mss-rules 硬门9 一致称 <80% 触发，
            # 旧代码 60% 才触发 hard 与文档打架。硬门二元：不过线即 0 分 + 触发。
            det.append(("R1 伏笔回收率", 0, 6, f"{rec}/{planted} = {rate*100:.0f}% <80%"))
            hard.append("伏笔回收率 <80%")
    # R2 承诺兑现：标题/导语核心词前 3000 字出现（硬门12）—4
    cores = []
    for s in (title, intro):
        cores += core_words(s)
    cores = list(dict.fromkeys(cores))
    front = t[:3000]
    missing, late, ok = [], [], []
    for w in cores:
        i = front.find(w)
        if i < 0:
            missing.append(w)
        else:
            cnt = t.count(w)
            if cnt == 1 and i > 2000:
                late.append(w)
            else:
                ok.append(w)
    if not cores:
        det.append(("R2 承诺兑现", 0, 4, "标题/导语无可提取核心词"))
    elif missing:
        # 硬门前先给两条自救路径——这两条不是"放宽", 是把判据讲明白：
        # ①拆分式兑现：标题核心词无法字面连续出现时（《女帝的第一天》→"女帝"+"第一天"），
        #   各片段在前 3000 字分别出现即算兑现，不必强行在导语里堆字面；
        # ②导语明示差异：导语可对"字面必然出现"的核心词作承接（导语是标题的承诺兑现声明，
        #   不属剧透），但仍算 0 分硬门命中，只提示可选的补救方向。
        split_ok = [w for w in missing
                    if len(w) >= 3 and all(seg in front for seg in split_word(w))]
        hint = ''
        if split_ok:
            hint = (f'；其中「{"、".join(split_ok[:3])}」可按拆分式兑现判定'
                    f'（{"、".join(split_ok[0])} 各片段已在前 3000 字分别出现）——'
                    f'拆分式只作人工裁量参考, 不改硬门, 是否采信由审稿人写明理由')
        det.append(("R2 承诺兑现", 0, 4,
                    f"核心词前 3000 字未出现：{'、'.join(missing[:5])}{hint}"))
        hard.append("标题/导语核心词在正文前 3000 字未出现")
    elif late:
        score += 2
        det.append(("R2 承诺兑现", 2, 4, f"核心词「{'、'.join(late[:3])}」仅 1 次且位置靠后（弱代理 B12）"))
    else:
        score += 4
        det.append(("R2 承诺兑现", 4, 4, f"核心词 {len(ok)} 个均在前 3000 字兑现（如「{ok[0]}」）"))
    return score, det, hard, cores, missing, late


def split_word(w):
    """核心词拆分式兑现的保守切分：三字词按 2+1（女帝的第一天→女帝|第一天 由四字规则处理，
    三字词取前二+后一），四字及以上取对半。只给人工裁量参考，不进计分。"""
    n = len(w)
    if n <= 2:
        return [w]
    cut = n // 2 if n >= 4 else 2
    return [w[:cut], w[cut:]]


# ============================ B1-B12 待人工复核弱代理（不计分） ============================
def weak_proxies(text, pw, cores, missing, late, n_chars):
    t = body_text(text)
    tips = []
    first500 = re.sub(r'\s', '', t)[:500]

    # B1 情绪外化不足：情绪词后 15 字内无动作/物件/身体词
    support = ACTION_WORDS + OBJECT_WORDS + BODY_WORDS
    for w, p in find_hits(EMOTION_WORDS, t):
        window = t[p + len(w):p + len(w) + 15]
        if not find_hits(support, window):
            tips.append(f"B1 第 {p//1000+1} 千字段（字位 {p}）情绪词「{w}」后 15 字无动作/物件/身体支撑，可能情绪外化不足")
            break
    # B2 潜台词不足：「」对话后 50 字内 ≥2 个解释词
    for m in re.finditer(r'」', t):
        window = t[m.end():m.end() + 50]
        ex = [w for w in EXPLAIN_WORDS if w in window]
        if len(ex) >= 2:
            tips.append(f"B2 字位 {m.end()} 对话后 50 字内连续解释词（{'、'.join(ex)}），可能潜台词不足")
            break
    # B3 代入感弱代理：前 500 字「我」达标但感官词 <3
    wo = first500.count("我")
    se = find_hits(SENSE_WORDS, first500)
    if wo >= 5 and len(se) < 3:
        tips.append(f"B3 前 500 字「我」{wo} 次达标，但感官词仅 {len(se)} 处，可能代入感不足")
    # B4 人设记忆点弱代理：前 500 字身份/特征词 <2 次
    idn = find_hits(IDENTITY_WORDS, first500)
    if len(idn) < 2:
        tips.append(f"B4 前 500 字身份/特征词仅 {len(idn)} 处（{'、'.join(w for w,_ in idn) or '无'}），可能人设记忆点不足")
    # B5 反派动机弱代理：首个冲突词后 500 字内无目标/因果/动机词
    ch = find_hits(CONFLICT_WORDS, t)
    if ch:
        w0 = t[ch[0][1]:ch[0][1] + 500]
        mv = [w for w in TARGET_WORDS + MOTIVE_WORDS if w in w0]
        if not mv:
            tips.append(f"B5 字位 {ch[0][1]} 冲突对象出现后 500 字内无目标/动机词，可能为工具人")
    # B6 结局余味弱代理：最后 200 字无留白/情绪/讨论点且以总结词结尾
    tail = t[-200:]
    if tail and not (find_hits(BLANK_WORDS + DISCUSS_WORDS, tail) or find_hits(EMOTION_WORDS, tail)) \
            and find_hits(SUMMARY_WORDS, tail):
        tips.append("B6 结尾 200 字缺留白/讨论点且以总结词收束，可能结局余味不足")
    # B7 AI 结构味弱代理：句长方差低或连接词密度高
    std = sentence_len_std(text)
    conn = len(find_hits(CONNECT_WORDS, t))
    if std < 4:
        tips.append(f"B7 句长标准差 {std:.1f} 偏低，节奏可能过于均匀（AI 结构味）")
    if n_chars and conn / (n_chars / 50) > 1:
        tips.append(f"B7 连接词密度 {conn} 处/每50字>1，可能 AI 结构味")
    # B8 语言风格弱代理：类符/形符比低或修辞词密度低
    bigrams = [t[i:i+2] for i in range(len(t) - 1)]
    if bigrams:
        ttr = len(set(bigrams)) / len(bigrams)
        if ttr < 0.5:
            tips.append(f"B8 二元类符/形符比 {ttr:.2f} 偏低，词汇重复度可能偏高")
    rhet = len(find_hits(RHETORIC_WORDS, t))
    if n_chars and rhet / (n_chars / 1000) < 2:
        tips.append(f"B8 修辞词密度 {rhet/(n_chars/1000):.2f}/千字 偏低，语言可能偏平")
    # B9 反转质量弱代理：反转词前 300 字无暗示词
    for w, p in find_hits(REVERSAL_WORDS, t):
        pre = t[max(0, p - 300):p]
        if not find_hits(HINT_WORDS, pre):
            tips.append(f"B9 字位 {p} 反转词「{w}」前 300 字无暗示词，反转铺垫可能不足")
            break
    # B10 打脸质量弱代理：打脸词前 300 字无铺垫词或后 100 字无代价词
    for w, p in find_hits(SLAP_WORDS, t):
        pre = t[max(0, p - 300):p]
        post = t[p:p + 100]
        if not find_hits(PAVE_WORDS, pre) or not find_hits(COST_WORDS, post):
            tips.append(f"B10 字位 {p} 打脸词「{w}」铺垫或代价不足，可能为伪打脸")
            break
    # B11 钩子质量弱代理：章末钩子词前 500 字无铺垫词
    sec_pos = []
    pos = 0
    for ln in t.splitlines():
        if re.match(r'^\s*\d+\s*$', ln):
            sec_pos.append(pos)
        pos += len(ln) + 1
    for i, sp in enumerate(sec_pos):
        ep = sec_pos[i + 1] if i + 1 < len(sec_pos) else len(t)
        tail = t[sp:ep][-100:]
        hh = find_hits([w for ws in HOOK_WORDS.values() for w in ws], tail)
        if hh:
            hp = ep - 100 + hh[0][1]
            pre = t[max(0, hp - 500):hp]
            if not find_hits(PAVE_WORDS, pre):
                tips.append(f"B11 第 {i+1} 章章末钩子词「{hh[0][0]}」前 500 字无铺垫词，可能为伪钩子")
            break
    # B12 承诺兑现弱代理：核心词仅 1 次且位置靠后
    for w in late:
        tips.append(f"B12 核心词「{w}」仅出现 1 次且位置靠后，承诺兑现可能不足")
    # 百分比断言：XX% 无来源标注
    for m in re.finditer(r'\d+(?:\.\d+)?%', t):
        pre = t[max(0, m.start() - 20):m.start()]
        if not re.search(r'据|数据|报告|统计|调查|显示', pre):
            tips.append(f"字位 {m.start()}「{m.group(0)}」百分比无来源标注，需人工核实")
            break
    # 红线词待核提示（不影响 MSS）
    red_hits = []
    for cat, ws in RED_LINE_WORDS.items():
        for w in ws:
            i = t.find(w)
            if i >= 0:
                red_hits.append((cat, w, i, context_of(t, i, w)))
    genre = [g for g, ws in GENRE_WORDS.items() if find_hits(ws, t)]
    return tips, red_hits, genre


# ============================ 主流程 ============================
class _Parser(argparse.ArgumentParser):
    """用法错误按 AT-56 退 1——argparse 默认退 2，与"⚠️ 级待修"撞码会误导聚合门"""
    def error(self, message):
        self.print_usage(sys.stderr)
        print(f"❌ 用法错误: {message}", file=sys.stderr)
        sys.exit(1)


def main():
    ap = _Parser(description="MSS 机检结构分（盐选七步法阶段6）")
    ap.add_argument("--text", required=True, help="正文文件（03-正文.md）")
    ap.add_argument("--title", default="")
    ap.add_argument("--intro", default="", help="导语；缺省从正文首个分节前自动提取")
    ap.add_argument("--logline", default="")
    ap.add_argument("--quotes", default="", help="金句，分号分隔")
    ap.add_argument("--foreshadow", default="", help="伏笔回收 CSV（埋设位置/埋设原句/回收位置/回收原句/回收方式）")
    ap.add_argument("--paywall", default="", help="付费墙锚句（无 [[首锁]] 标记时等效卡点位）")
    ap.add_argument("--person", default="auto", choices=["auto", "1st", "3rd"])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    p = Path(args.text)
    if not p.is_file():
        # exists() 对目录亦为真，须用 is_file()；否则 read_text() 会裸抛 IsADirectoryError。
        # 与 check-metrics/check-ai 守卫对齐：目录/不存在一律干净报错退 1
        print(f"❌ 正文文件不存在或不是文件: {args.text}（用法: check-mss.py --text <正文.md>）")
        return 1
    text = p.read_text(encoding="utf-8-sig")
    # 空稿前置拦截：空正文下 F/B/T/D/R 各项命中恒为 0，但硬门「总字数」需到 F1 才触发；
    # 若只给 --text 不给其它元信息，会得到一份"看似正常"的报告。空稿是输入错误，退 1。
    if not re.sub(r"\s", "", text):
        print(f"❌ 正文为空: {args.text}——check-mss 无法评估空稿（先补齐正文再跑）")
        return 1
    intro = args.intro.strip()
    intro_auto = False
    if not intro:
        # 自动提取：首个纯数字分节行之前的内容（剔结构行）
        pre = []
        for ln in text.splitlines():
            if re.match(r'^\s*\d+\s*$', ln):
                break
            if not MARKDOWN_STRUCT.match(ln) and ln.strip():
                pre.append(ln.strip())
        cand = re.sub(r'\s', '', "".join(pre))
        if 40 <= len(cand) <= 200:
            intro, intro_auto = cand, True
    person = args.person
    if person == "auto":
        person = "1st" if body_text(text)[:500].count("我") >= 5 else "3rd"

    f_score, f_det, f_hard, n_chars = score_F(text, person)
    b_score, b_det, b_hard = score_B(args.title, intro, args.logline, args.quotes)
    t_score, t_det, t_hard, pw = score_T(text, args.paywall, n_chars)
    d_score, d_det, d_hard = score_D(text)
    r_score, r_det, r_hard, cores, missing, late = score_R(text, args.title, intro, args.foreshadow, n_chars)
    tips, red_hits, genre = weak_proxies(text, pw, cores, missing, late, n_chars)

    # 卡点双口径互校（阶段 7 建议 7）：[[首锁]] 标记与 --paywall 锚句同时存在时
    # 校验字位一致——stage7 workflow 宣称二者"唯一对应关系"（同锚 AT-04 首锁字位），
    # 但旧实现静默取标记，两口径漂移不报警。互校提示进 tips（不计分，不改变 MSS）。
    if pw is not None and args.paywall:
        i = text.find(args.paywall)
        mi = text.find("[[首锁]]")
        if i >= 0 and mi >= 0 and abs(i - mi) > 50:
            tips.append(f"卡点双口径互校：`[[首锁]]` 标记在字位 {mi}、--paywall 锚句在字位 {i}，"
                        f"相差 {abs(i - mi)} 字（容差 50）——二者应同锚 AT-04 首锁字位；"
                        f"本次判定以标记为准，请人工确认哪个是对的")

    mss = f_score + b_score + t_score + d_score + r_score
    hards = f_hard + b_hard + t_hard + r_hard + d_hard
    capped = bool(hards)
    if capped:
        mss = min(mss, CAP_SCORE)
    mss = round(mss, 1)
    if capped:
        tier = "机检匹配低（硬门封顶 59）"
    elif mss >= TIER_HIGH:
        tier = "机检匹配高"
    elif mss >= TIER_MID:
        tier = "机检匹配低"
    else:
        tier = "机检不匹配"

    if args.json:
        print(json.dumps({
            "mss": mss, "F": f_score, "B": b_score, "T": t_score, "D": d_score, "R": r_score,
            "tier": tier, "hard": hards, "capped": capped, "n": 1,
            "rules_version": RULES_VERSION, "genre": genre,
            "weak_tips": tips, "red_hits": [{"类目": c, "词": w, "字位": i, "上下文": ctx}
                                            for c, w, i, ctx in red_hits],
            "details": [{"项": k, "得分": s, "满分": m, "依据": b} for k, s, m, b in
                        f_det + b_det + t_det + d_det + r_det],
        }, ensure_ascii=False, indent=2))
        if capped:
            return 3
        return 2 if mss < TIER_HIGH else 0

    # ---- 输出模板 ----
    print(f"MSS={mss} [F={f_score:.0f}·B={b_score:.0f}·T={t_score:.0f}·D={d_score:.0f}·R={r_score:.0f}"
          f"·{tier}·机检基线：{RULES_VERSION}·n=1]")
    print(f"（赛道粗分类：{'、'.join(genre) or '未归类'}；一称口径：{'适用' if person=='1st' else '不适用（第三人称稿）'}）")
    if intro_auto:
        print(f"（导语为自动提取：{len(intro)} 字；建议 --intro 显式传入复核）")

    print("\n命中项：")
    for k, s, m, b in f_det + b_det + t_det + d_det + r_det:
        if s > 0:
            print(f"- {k}：{b}")
    print("\n未命中/缺失项：")
    miss = [(k, b) for k, s, m, b in f_det + b_det + t_det + d_det + r_det if s <= 0 and m > 0]
    if miss:
        for k, b in miss:
            print(f"- {k}：{b}")
    else:
        print("- 无")

    print("\n硬门：")
    if hards:
        for h in dict.fromkeys(hards):
            print(f"- 触发：{h} → MSS 封顶 59")
    else:
        print("- 未触发")

    print("\n红线提示（只提示待核，不影响评分）：")
    if red_hits:
        for cat, w, i, ctx in red_hits:
            print(f"- 命中 {cat} 类红线词「{w}」@字位 {i}，上下文：…{ctx}… → 待人工核")
    else:
        print("- 无")

    print("\n修改建议：")
    sugg = []
    for k, s, m, b in t_det:
        if s < m and "钩子" in k:
            sugg.append("卡点后/章末补足钩子（≥3 处且类型不同，章末 100 字动作钩 + 200 字新问题）")
    if any("伏笔回收率" in k for k, s, m, b in r_det if s < m):
        sugg.append("补齐伏笔回收表并提升回收率至 ≥80%（埋设位置/原句、回收位置/原句、回收方式五字段齐全）")
    if any("标题" in k and s < m for k, s, m, b in b_det):
        sugg.append("标题压到 15 字内、去问号/感叹号、补冲突或情绪反差词")
    if any("段落" in k and s < m for k, s, m, b in f_det):
        sugg.append("长段拆句，把 ≤50 字段落占比提到 60% 以上")
    if not sugg:
        sugg.append("当前无结构项待改；语言风格/AI 味/代入感等不评项见待人工复核清单")
    for s_ in dict.fromkeys(sugg):
        print(f"- {s_}")

    print("\n待人工复核清单（不计分，不改变 MSS）：")
    if tips:
        for i, tp in enumerate(tips, 1):
            print(f"{i}. {tp}")
    else:
        print("1. 无触发项")

    print("\n注：本报告为机检结构匹配，不预测真实过稿或爆款，不代表真实读者反应。"
          "语言风格、AI 味、代入感、人设记忆点等不评。")
    if capped:
        return 3
    return 2 if mss < TIER_HIGH else 0


if __name__ == "__main__":
    sys.exit(main())
