#!/usr/bin/env python3
"""五行行业轮动分析 - 自动化测试"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from five_elements_analysis import (
    FIVE_ELEMENTS, GENERATION, OVERCOMING, INDUSTRY_MAPPING,
    get_year_stems_branches, get_month_stems_branches,
    analyze_prosperity, analyze_special_patterns,
    generate_report, generate_advice, format_report,
)

passed = 0
failed = 0


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}" + (f" — {detail}" if detail else ""))


# ── 1. 天干地支五行映射 ──
print("\n[天干地支五行映射]")
check("甲→木", FIVE_ELEMENTS["甲"] == "木")
check("丙→火", FIVE_ELEMENTS["丙"] == "火")
check("戊→土", FIVE_ELEMENTS["戊"] == "土")
check("庚→金", FIVE_ELEMENTS["庚"] == "金")
check("壬→水", FIVE_ELEMENTS["壬"] == "水")
check("午→火", FIVE_ELEMENTS["午"] == "火")
check("子→水", FIVE_ELEMENTS["子"] == "水")

# ── 2. 年干支计算 ──
print("\n[年干支计算]")
stem, branch = get_year_stems_branches(2026)
check("2026年干支=丙午", f"{stem}{branch}" == "丙午", f"got {stem}{branch}")

stem, branch = get_year_stems_branches(2024)
check("2024年干支=甲辰", f"{stem}{branch}" == "甲辰", f"got {stem}{branch}")

stem, branch = get_year_stems_branches(2000)
check("2000年干支=庚辰", f"{stem}{branch}" == "庚辰", f"got {stem}{branch}")

# ── 3. 月干计算 ──
print("\n[月干计算]")
# 丙年（2026）月干：丙辛之年庚寅首 → 庚寅起
month_stem = get_month_stems_branches("丙", "寅")
check("丙年寅月干=庚", month_stem == "庚", f"got {month_stem}")

month_stem = get_month_stems_branches("丙", "午")
check("丙年午月干=甲", month_stem == "甲", f"got {month_stem}")

# 甲年月干：甲己之年丙寅首
month_stem = get_month_stems_branches("甲", "寅")
check("甲年寅月干=丙", month_stem == "丙", f"got {month_stem}")

# ── 4. 五行旺衰 ──
print("\n[五行旺衰]")
check("火月·火→旺", analyze_prosperity("火", "火") == "旺")
check("火月·木→相(木生火)", analyze_prosperity("木", "火") == "相")
check("火月·金→死(火克金)", analyze_prosperity("金", "火") == "死")
check("火月·水→囚(水克火)", analyze_prosperity("水", "火") == "囚")
check("火月·土→休(火生土)", analyze_prosperity("土", "火") == "休")

check("水月·水→旺", analyze_prosperity("水", "水") == "旺")
check("金月·金→旺", analyze_prosperity("金", "金") == "旺")

# ── 5. 生克关系完整性 ──
print("\n[生克关系]")
for element in ["木", "火", "土", "金", "水"]:
    check(f"{element}→{GENERATION[element]}(生)", GENERATION[element] in ["木", "火", "土", "金", "水"])
    check(f"{element}克{OVERCOMING[element]}", OVERCOMING[element] in ["木", "火", "土", "金", "水"])

# ── 6. 行业映射完整性 ──
print("\n[行业映射]")
for element in ["木", "火", "土", "金", "水"]:
    check(f"{element}有行业映射", element in INDUSTRY_MAPPING)
    if element in INDUSTRY_MAPPING:
        for key in ["核心", "衍生", "传统", "概念"]:
            check(f"{element}.{key}存在且非空",
                  key in INDUSTRY_MAPPING[element] and len(INDUSTRY_MAPPING[element][key]) > 0)

# ── 7. 特殊格局检测 ──
print("\n[特殊格局]")
patterns = analyze_special_patterns("午", "午", "甲")
check("年支=月支→伏吟", "伏吟" in patterns, f"got {patterns}")

patterns = analyze_special_patterns("子", "未", "己")
check("未月→燥土", "燥土" in patterns, f"got {patterns}")

patterns = analyze_special_patterns("子", "辰", "戊")
check("辰月→湿土", "湿土" in patterns, f"got {patterns}")

patterns = analyze_special_patterns("子", "午", "丙")
check("丙(火)干午(火)支→同气", "天干地支同气" in patterns, f"got {patterns}")

patterns = analyze_special_patterns("子", "午", "甲")
check("甲(木)干午(火)支→天干生地支", "天干生地支" in patterns, f"got {patterns}")

patterns = analyze_special_patterns("子", "午", "壬")
check("壬(水)干午(火)支→天干克地支", "天干克地支" in patterns, f"got {patterns}")

# ── 8. 报告生成完整性 ──
print("\n[报告生成]")
report = generate_report(2026, 6)

check("基础信息完整", all(k in report["基础信息"] for k in ["年份", "月份", "年干支", "月干支", "月令五行", "节气"]))
check("2026年6月年干支=丙午", report["基础信息"]["年干支"] == "丙午")
check("五行旺衰含5行", len(report["五行旺衰"]) == 5 and all(e in report["五行旺衰"] for e in ["木", "火", "土", "金", "水"]))
check("行业预测含主线/支线/回避", all(k in report["行业预测"] for k in ["主线", "支线", "回避"]))
check("主线行业非空", len(report["行业预测"]["主线"]) > 0)
check("操作建议非空", len(report["操作建议"]) > 0)

# ── 9. 全年12月无报错 ──
print("\n[全年12月生成]")
for m in range(1, 13):
    try:
        r = generate_report(2026, m)
        check(f"{m}月生成成功", True)
    except Exception as e:
        check(f"{m}月生成成功", False, str(e))

# ── 10. 格式化输出 ──
print("\n[格式化输出]")
text = format_report(report)
check("格式化包含标题", "五行行业轮动分析" in text)
check("格式化包含旺衰", "【五行旺衰】" in text)
check("格式化包含行业预测", "【行业预测】" in text)
check("格式化包含风险提示", "【风险提示】" in text)

# ── 11. 操作建议按五行 ──
print("\n[操作建议按五行]")
for element in ["火", "木", "土", "金", "水"]:
    advice = generate_advice(element, [], {e: analyze_prosperity(e, element) for e in ["木", "火", "土", "金", "水"]})
    check(f"{element}月建议非空", len(advice) > 0)

# 燥土特殊建议
advice = generate_advice("土", ["燥土"], {e: analyze_prosperity(e, "土") for e in ["木", "火", "土", "金", "水"]})
check("燥土建议含资源类", any("资源" in a or "煤炭" in a for a in advice), f"got {advice}")

# ── 结果 ──
print(f"\n{'='*50}")
print(f"结果: {passed} passed, {failed} failed, {passed+failed} total")
sys.exit(1 if failed > 0 else 0)
