#!/usr/bin/env python3
"""
五行行业轮动分析脚本（对齐版）

基于天干地支、月令五行、地支藏干、四库、刑冲、流年加权、生克制化
分析行业轮动规律。月令按节气换月（命理通用），与"豆包"等口径对齐。
"""

import sys
import json
from datetime import datetime, timedelta

# ─────────────────────────── 基础映射 ───────────────────────────

# 天干地支 → 五行
FIVE_ELEMENTS = {
    "甲": "木", "乙": "木",
    "丙": "火", "丁": "火",
    "戊": "土", "己": "土",
    "庚": "金", "辛": "金",
    "壬": "水", "癸": "水",
    "寅": "木", "卯": "木",
    "辰": "土", "巳": "火", "午": "火", "未": "土",
    "申": "金", "酉": "金",
    "戌": "土", "亥": "水", "子": "水", "丑": "土"
}

# 地支藏干（本气、中气、余气）
HIDDEN_STEMS = {
    "寅": ["甲", "丙", "戊"],
    "卯": ["乙"],
    "辰": ["戊", "乙", "癸"],
    "巳": ["丙", "戊", "庚"],
    "午": ["丁", "己"],
    "未": ["己", "丁", "乙"],
    "申": ["庚", "壬", "戊"],
    "酉": ["辛"],
    "戌": ["戊", "辛", "丁"],
    "亥": ["壬", "甲"],
    "子": ["癸"],
    "丑": ["己", "癸", "辛"]
}

# 五行生克：GENERATION[X]=X所生；OVERCOMING[X]=X所克
GENERATION = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
OVERCOMING = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}

# ─────────────────────────── 节气 / 命理月 ───────────────────────────

# 命理月支顺序（立春起寅月为正月）
MONTH_BRANCHES_ORDER = ["寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥", "子", "丑"]

# 命理月名（正月..十月、冬月、腊月）
LUNAR_MONTH_NAMES = ["正月", "二月", "三月", "四月", "五月", "六月",
                     "七月", "八月", "九月", "十月", "冬月", "腊月"]

# 节气名（每月以"节"换月令）
SOLAR_TERMS = {
    "寅": "立春-惊蛰", "卯": "惊蛰-清明", "辰": "清明-立夏",
    "巳": "立夏-芒种", "午": "芒种-小暑", "未": "小暑-立秋",
    "申": "立秋-白露", "酉": "白露-寒露", "戌": "寒露-立冬",
    "亥": "立冬-大雪", "子": "大雪-小寒", "丑": "小寒-立春"
}

# 2026（丙午年）精确节气日期段：命理月 → (起始月.日, 结束月.日)
# 与"豆包"口径一致：每月以节气交界换月令
TERM_PERIODS_2026 = {
    "寅": ("2.4", "3.5"),   "卯": ("3.5", "4.5"),   "辰": ("4.5", "5.5"),
    "巳": ("5.5", "6.5"),   "午": ("6.5", "7.7"),   "未": ("7.7", "8.7"),
    "申": ("8.7", "9.7"),   "酉": ("9.7", "10.8"),  "戌": ("10.8", "11.7"),
    "亥": ("11.7", "12.7"), "子": ("12.7", "次年1.5"), "丑": ("次年1.5", "次年2.4"),
}

# 公历月 → 命理月支近似（取该月中点所在命理月，用于单月调用）
SOLAR_TO_BRANCH = ["丑", "寅", "卯", "辰", "巳", "午",
                   "未", "申", "酉", "戌", "亥", "子"]

# ─────────────────────────── 四库 / 地支特性 ───────────────────────────

# 四库（辰戌丑未）的库性：藏干中带"库"的五行 + 土性燥湿
# 对齐豆包口径：看藏干实际力量，标注"X库/燥湿土"
BRANCH_QUALITY = {
    "辰": {"type": "湿土", "lib": "水", "note": "水库·蓄水制火"},   # 藏癸水
    "丑": {"type": "湿土", "lib": "金", "note": "金库·寒湿藏金水"}, # 藏辛金癸水
    "戌": {"type": "燥土", "lib": "火", "note": "火库·燥土藏火"},   # 藏丁火
    "未": {"type": "燥土", "lib": None, "note": "燥土·藏丁火余气"}, # 燥土带火气，但土本气主导
}

# 六冲
CLASHES = {
    "子": "午", "午": "子", "丑": "未", "未": "丑",
    "寅": "申", "申": "寅", "卯": "酉", "酉": "卯",
    "辰": "戌", "戌": "辰", "巳": "亥", "亥": "巳",
}

# ─────────────────────────── 行业五行映射 ───────────────────────────

INDUSTRY_MAPPING = {
    "火": {
        "核心": ["半导体", "光模块", "通信设备", "AI算力", "消费电子"],
        "衍生": ["新能源车", "光伏", "风电", "储能"],
        "传统": ["电力", "传媒", "教育"],
        "概念": ["CPO", "HBM", "AI手机", "机器人", "算力"]
    },
    "木": {
        "核心": ["中药", "生物医药", "医疗器械"],
        "衍生": ["环保", "园林", "造纸"],
        "传统": ["农业", "林业", "纺织"],
        "概念": ["创新药", "中药", "医疗美容", "健康中国"]
    },
    "水": {
        "核心": ["物流", "航运", "旅游", "酒店"],
        "衍生": ["传媒", "游戏", "影视"],
        "传统": ["水务", "渔业"],
        "概念": ["跨境电商", "免税", "露营经济", "文化旅游"]
    },
    "金": {
        "核心": ["银行", "保险", "证券", "机械"],
        "衍生": ["汽车", "家电", "军工"],
        "传统": ["钢铁", "有色金属"],
        "概念": ["券商", "工业母机", "国防军工", "高端制造"]
    },
    "土": {
        "核心": ["房地产", "建筑", "建材"],
        "衍生": ["煤炭", "石油", "化工"],
        "传统": ["农业", "畜牧"],
        "概念": ["基建", "一带一路", "资源股", "新型城镇化"]
    }
}


# ─────────────────────────── 干支计算 ───────────────────────────

def get_year_stems_branches(year):
    """计算年干支"""
    stems = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
    branches = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
    return stems[(year - 4) % 10], branches[(year - 4) % 12]


def get_month_stem_by_branch(year_stem, month_branch):
    """根据年干和月支推算月干（五虎遁）"""
    stems = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
    # 月干起始表（五虎遁）：甲己→丙寅，乙庚→戊寅，丙辛→庚寅，丁壬→壬寅，戊癸→甲寅
    start = {"甲": 2, "己": 2, "乙": 4, "庚": 4, "丙": 6, "辛": 6,
             "丁": 8, "壬": 8, "戊": 0, "癸": 0}
    branch_idx = MONTH_BRANCHES_ORDER.index(month_branch)
    return stems[(start[year_stem] + branch_idx) % 10]


# ─────────────────────────── 月令五行力量模型 ───────────────────────────

def month_power(month_branch, year_stem, year_branch, month_stem=None):
    """
    计算当月各五行的综合力量（对齐豆包口径）：
      1. 月支本气为主旺 + 藏干叠加
      2. 月干透出力量（如庚寅月庚金有力）
      3. 四库库性加持（辰水库/戌火库/丑金库）
      4. 流年天干地支五行背景加权
      5. 流年生助（流年五行所生的五行得生）
      6. 流年支与月支：同气叠加 / 相冲减损
    返回 {五行: 力量值}，值越大越旺。
    """
    power = {e: 0 for e in ["木", "火", "土", "金", "水"]}

    # (1) 月支本气 + 藏干
    hidden = HIDDEN_STEMS.get(month_branch, [])
    weights = [10, 4, 2]  # 本气/中气/余气权重
    for i, stem in enumerate(hidden):
        power[FIVE_ELEMENTS[stem]] += weights[i] if i < len(weights) else 1

    # (2) 月干透出
    if month_stem:
        power[FIVE_ELEMENTS[month_stem]] += 3

    # (3) 四库库性加持
    qual = BRANCH_QUALITY.get(month_branch)
    if qual and qual.get("lib"):
        power[qual["lib"]] += 6

    # (4) 流年背景加权
    year_branch_element = FIVE_ELEMENTS[year_branch]
    year_stem_element = FIVE_ELEMENTS[year_stem]
    power[year_branch_element] += 4
    power[year_stem_element] += 2

    # (5) 流年生助：流年五行所生的五行得生
    generated = GENERATION.get(year_branch_element)
    if generated:
        power[generated] += 2

    # (6) 年支 vs 月支：同气叠加 / 相冲减损
    if year_branch == month_branch:
        power[FIVE_ELEMENTS[month_branch]] += 6
    elif CLASHES.get(year_branch) == month_branch:
        power[FIVE_ELEMENTS[month_branch]] -= 4
        power[year_branch_element] -= 4

    return power


def group_by_strength(power, threshold_ratio=0.45):
    """
    将五行力量分组（对齐豆包"旺:木>金；偏弱:水、土"口径）。
    threshold_ratio：力量 >= 最大力量 × ratio 视为"旺组"，其余为"偏弱组"。
    返回 (旺组排序列表, 偏弱组列表)。
    """
    max_v = max(power.values()) if power else 0
    threshold = max_v * threshold_ratio
    strong = [(e, v) for e, v in power.items() if v >= threshold and v > 0]
    weak = [e for e, v in power.items() if v < threshold or v <= 0]
    strong.sort(key=lambda kv: -kv[1])  # 按力量降序
    return [e for e, _ in strong], weak


def analyze_clash(month_branch, year_branch):
    """判断月支与年支的冲（如子月冲午年=子午冲）"""
    if CLASHES.get(year_branch) == month_branch:
        return f"{month_branch}{year_branch}冲"
    return None


def analyze_special_patterns(year_branch, month_branch, month_stem, year_stem):
    """分析特殊格局（含库性、刑冲、叠加、调候）"""
    patterns = []
    qual = BRANCH_QUALITY.get(month_branch)
    if qual:
        patterns.append(qual["note"])

    # 伏吟：年支与月支同
    if year_branch == month_branch:
        me = FIVE_ELEMENTS[month_branch]
        patterns.append(f"{month_branch}火伏吟·双{me}叠" if me == "火" else f"{month_branch}伏吟·{me}气叠加")

    # 六冲
    clash = analyze_clash(month_branch, year_branch)
    if clash:
        patterns.append(f"{clash}·月年相冲")

    # 天干地支关系
    se = FIVE_ELEMENTS[month_stem]
    be = FIVE_ELEMENTS[month_branch]
    if se == be:
        patterns.append("天干地支同气")
    elif GENERATION.get(se) == be:
        patterns.append("天干生地支")
    elif OVERCOMING.get(se) == be:
        patterns.append("天干克地支")

    return patterns


# ─────────────────────────── 报告生成 ───────────────────────────

def _industry_predict(dominant_elements, special_patterns):
    """根据主导五行 + 格局预测行业（混合派：五行→概念板块）
    主线聚焦当令本气（主导第1位），支线取次旺五行，避免流年背景火稀释主线。
    """
    predictions = {"主线": [], "支线": [], "回避": []}
    # 主线：当令本气（最强五行）
    if dominant_elements:
        predictions["主线"] = INDUSTRY_MAPPING[dominant_elements[0]]["核心"][:3]
    # 支线：次旺五行
    if len(dominant_elements) >= 2:
        predictions["支线"] = INDUSTRY_MAPPING[dominant_elements[1]]["衍生"][:2]
    # 回避：被当旺五行所克的五行行业
    if dominant_elements:
        overcome = OVERCOMING.get(dominant_elements[0])
        predictions["回避"] = INDUSTRY_MAPPING[overcome]["核心"][:2]
    return predictions


def _build_report_core(year, year_stem, year_branch, month_branch, label_month, period):
    """构造单月报告的公共逻辑（公历月/命理月共用）"""
    month_stem = get_month_stem_by_branch(year_stem, month_branch)
    power = month_power(month_branch, year_stem, year_branch, month_stem)
    strong, weak = group_by_strength(power)
    dominant = strong[0] if strong else FIVE_ELEMENTS[month_branch]
    special = analyze_special_patterns(year_branch, month_branch, month_stem, year_stem)
    predictions = _industry_predict(strong, special)

    # 调候用神（火旺之年，水/湿土月为降火调候喜月）
    year_ele = FIVE_ELEMENTS[year_branch]
    notes = []
    if year_ele == "火" and (dominant in ("水",) or
                             (BRANCH_QUALITY.get(month_branch, {}).get("type") == "湿土")):
        notes.append("调候降火喜月（喜金水、忌火土之人全年利好月）")

    # 五行旺衰定性（保留旺相休囚死口径，供兼容）
    me = FIVE_ELEMENTS[month_branch]
    prosperity = {}
    for e in ["木", "火", "土", "金", "水"]:
        prosperity[e] = _classic_state(e, me)

    return {
        "基础信息": {
            "年份": year,
            "月份": label_month,
            "月支": month_branch,
            "年干支": f"{year_stem}{year_branch}",
            "月干支": f"{month_stem}{month_branch}",
            "月令五行": me,
            "节气": SOLAR_TERMS.get(month_branch, ""),
            "节气日期段": period,
        },
        "月令力量": power,            # 各五行力量值
        "主导五行": strong,            # 旺组（降序）
        "偏弱五行": weak,             # 偏弱组
        "主导描述": _strength_desc(strong, weak),
        "特殊格局": special,
        "调候提示": notes,
        "五行旺衰": prosperity,        # 兼容旧字段（旺相休囚死）
        "行业预测": predictions,
        "操作建议": generate_advice(me, dominant, strong, special, notes),
    }


def _classic_state(element, month_element):
    """经典旺相休囚死（以月令为我）"""
    if element == month_element:
        return "旺"
    if GENERATION.get(month_element) == element:   # 月令生我→相
        return "相"
    if GENERATION.get(element) == month_element:   # 我生月令→休
        return "休"
    if OVERCOMING.get(element) == month_element:   # 我克月令→囚
        return "囚"
    return "死"                                    # 月令克我→死


def _strength_desc(strong, weak):
    """生成"旺：木＞金；偏弱：水、土"式描述"""
    s = "＞".join(strong) if strong else "—"
    w = "、".join(weak) if weak else "无"
    return f"旺：{s}；偏弱：{w}"


def generate_report(year, month, day=None):
    """
    按公历月份生成报告（兼容旧接口，month=公历月1-12）。
    内部按节气近似映射到命理月支。
    """
    year_stem, year_branch = get_year_stems_branches(year)
    month_branch = SOLAR_TO_BRANCH[(month - 1) % 12]
    period = TERM_PERIODS_2026.get(month_branch, ("", ""))
    return _build_report_core(year, year_stem, year_branch, month_branch, month, period)


def generate_lunar_month_report(year, lunar_idx):
    """
    按命理月生成报告（对齐豆包口径）。
    lunar_idx: 1=正月(寅) ... 11=冬月(子), 12=腊月(丑)
    """
    year_stem, year_branch = get_year_stems_branches(year)
    month_branch = MONTH_BRANCHES_ORDER[(lunar_idx - 1) % 12]
    period = TERM_PERIODS_2026.get(month_branch, ("", ""))
    return _build_report_core(year, year_stem, year_branch, month_branch,
                              LUNAR_MONTH_NAMES[(lunar_idx - 1) % 12], period)


def generate_year_reports(year):
    """生成全年12个命理月的报告列表（正月→腊月）"""
    return [generate_lunar_month_report(year, i) for i in range(1, 13)]


def generate_advice(month_element, dominant, strong, patterns, notes):
    """生成操作建议（基于主导五行 + 格局 + 调候）"""
    advice = []
    if notes:
        advice.extend(notes)
    if strong:
        advice.append(f"当月{strong[0]}气最旺，关注{INDUSTRY_MAPPING[strong[0]]['核心'][:2]}等{strong[0]}属性行业")
    if len(strong) >= 2:
        advice.append(f"次旺{strong[1]}气，可关注{INDUSTRY_MAPPING[strong[1]]['核心'][:2]}")
    overcome = OVERCOMING.get(dominant)
    if overcome:
        advice.append(f"{dominant}克{overcome}，回避{INDUSTRY_MAPPING[overcome]['核心'][:2]}等{overcome}属性行业")
    for p in patterns:
        if "伏吟" in p:
            advice.append(f"{p}，主导五行力量倍增，主线行业确定性更强")
        if "冲" in p:
            advice.append(f"{p}，本月波动加剧，注意风险对冲")
    return advice


# ─────────────────────────── 格式化输出 ───────────────────────────

def format_report(report):
    """单月详细报告（兼容旧格式）"""
    lines = []
    b = report["基础信息"]
    lines.append(f"🔮 {b['年份']}年 {b['月干支']}月（{b['月令五行']}旺）五行行业分析")
    lines.append("=" * 50)
    lines.append("")
    lines.append("【基础信息】")
    lines.append(f"  年干支：{b['年干支']}　月干支：{b['月干支']}")
    lines.append(f"  月令五行：{b['月令五行']}旺　节气：{b['节气']}")
    if b.get("节气日期段") and b["节气日期段"][0]:
        lines.append(f"  时段：{b['节气日期段'][0]}～{b['节气日期段'][1]}")

    if report.get("主导描述"):
        lines.append("")
        lines.append("【五行力量】")
        lines.append(f"  {report['主导描述']}")

    if report.get("特殊格局"):
        lines.append("")
        lines.append("【特殊格局】")
        for p in report["特殊格局"]:
            lines.append(f"  • {p}")

    if report.get("调候提示"):
        lines.append("")
        lines.append("【调候用神】")
        for n in report["调候提示"]:
            lines.append(f"  • {n}")

    lines.append("")
    lines.append("【行业预测】")
    pred = report["行业预测"]
    if pred["主线"]:
        lines.append("  🔥 主线行业：" + "、".join(pred["主线"]))
    if pred["支线"]:
        lines.append("  🌿 支线行业：" + "、".join(pred["支线"]))
    if pred["回避"]:
        lines.append("  ⚠️ 回避行业：" + "、".join(pred["回避"]))

    lines.append("")
    lines.append("【操作建议】")
    for a in report["操作建议"]:
        lines.append(f"  • {a}")

    lines.append("")
    lines.append("【风险提示】")
    lines.append("  • 五行理论为传统文化分析方法，仅供参考")
    lines.append("  • 需结合基本面、技术面、资金面综合判断")
    return "\n".join(lines)


def main():
    if len(sys.argv) < 3:
        print("用法: python five_elements_analysis.py <年份> <月份>")
        print("示例: python five_elements_analysis.py 2026 7")
        sys.exit(1)
    try:
        year = int(sys.argv[1])
        month = int(sys.argv[2])
        if month < 1 or month > 12:
            print("月份必须在1-12之间")
            sys.exit(1)
        report = generate_report(year, month)
        print(format_report(report))
        print("\n" + "=" * 50)
        print("JSON数据:")
        print(json.dumps(report, ensure_ascii=False, indent=2))
    except ValueError:
        print("请输入有效的年份和月份")
        sys.exit(1)


if __name__ == "__main__":
    main()
