#!/usr/bin/env python3
"""五行行业轮动分析 - 自动化测试（含与豆包口径对齐断言）"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from five_elements_analysis import (
    FIVE_ELEMENTS, GENERATION, OVERCOMING, INDUSTRY_MAPPING,
    HIDDEN_STEMS, BRANCH_QUALITY, CLASHES,
    TERM_PERIODS_2026, MONTH_BRANCHES_ORDER, LUNAR_MONTH_NAMES,
    get_year_stems_branches, get_month_stem_by_branch,
    month_power, group_by_strength, analyze_clash,
    analyze_special_patterns, _classic_state,
    generate_report, generate_lunar_month_report, generate_year_reports,
    generate_advice, format_report,
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
for stem, ele in [("甲", "木"), ("丙", "火"), ("戊", "土"), ("庚", "金"), ("壬", "水")]:
    check(f"{stem}→{ele}", FIVE_ELEMENTS[stem] == ele)
check("午→火", FIVE_ELEMENTS["午"] == "火")
check("子→水", FIVE_ELEMENTS["子"] == "水")

# ── 2. 年干支计算 ──
print("\n[年干支计算]")
for y, expect in [(2026, "丙午"), (2024, "甲辰"), (2000, "庚辰")]:
    s, b = get_year_stems_branches(y)
    check(f"{y}年干支={expect}", f"{s}{b}" == expect, f"got {s}{b}")

# ── 3. 月干计算（五虎遁） ──
print("\n[月干计算]")
check("丙年寅月干=庚", get_month_stem_by_branch("丙", "寅") == "庚")
check("丙年午月干=甲", get_month_stem_by_branch("丙", "午") == "甲")
check("甲年寅月干=丙", get_month_stem_by_branch("甲", "寅") == "丙")

# ── 4. 五行力量模型 ──
print("\n[五行力量模型]")
ys, yb = "丙", "午"
pw = month_power("辰", ys, yb, get_month_stem_by_branch(ys, "辰"))
check("辰月水入库·水力量>0", pw["水"] > 0, f"got {pw}")
check("辰月土本气最旺", pw["土"] == max(pw.values()), f"got {pw}")

pw2 = month_power("午", ys, yb, get_month_stem_by_branch(ys, "午"))
check("午年午月火气最旺(双火叠)", pw2["火"] == max(pw2.values()), f"got {pw2}")

# ── 5. 旺衰强度分组 ──
print("\n[旺衰强度分组]")
strong, weak = group_by_strength(pw2)
check("午月旺组首位=火", strong[0] == "火", f"got {strong}")

# ── 6. 经典旺相休囚死（以月令为我，口诀方向校验） ──
print("\n[经典旺相休囚死]")
check("火月·火→旺", _classic_state("火", "火") == "旺")
check("火月·土→相(火生土=我生者相)", _classic_state("土", "火") == "相")
check("火月·木→休(木生火=生我者休)", _classic_state("木", "火") == "休")
check("火月·水→囚(水克火=克我者囚)", _classic_state("水", "火") == "囚")
check("火月·金→死(火克金=我克者死)", _classic_state("金", "火") == "死")

# ── 7. 生克关系完整性 ──
print("\n[生克关系]")
for e in ["木", "火", "土", "金", "水"]:
    check(f"{e}→{GENERATION[e]}(生)", GENERATION[e] in ["木", "火", "土", "金", "水"])
    check(f"{e}克{OVERCOMING[e]}", OVERCOMING[e] in ["木", "火", "土", "金", "水"])

# ── 8. 行业映射完整性 ──
print("\n[行业映射]")
for e in ["木", "火", "土", "金", "水"]:
    check(f"{e}有行业映射", e in INDUSTRY_MAPPING)
    for key in ["核心", "衍生", "传统", "概念"]:
        check(f"{e}.{key}非空", key in INDUSTRY_MAPPING[e] and len(INDUSTRY_MAPPING[e][key]) > 0)

# ── 9. 四库 / 六冲 ──
print("\n[四库库性]")
check("辰=水库", BRANCH_QUALITY["辰"]["lib"] == "水")
check("戌=火库", BRANCH_QUALITY["戌"]["lib"] == "火")
check("丑=金库", BRANCH_QUALITY["丑"]["lib"] == "金")

print("\n[六冲]")
check("子午冲", CLASHES["子"] == "午" and CLASHES["午"] == "子")
check("辰戌冲", CLASHES["辰"] == "戌")
check("子月冲午年→子午冲", analyze_clash("子", "午") == "子午冲")

# ── 10. 全年12命理月（与豆包口径对齐） ──
print("\n[全年12命理月·对齐豆包]")
reports = generate_year_reports(2026)
check("全年12个月", len(reports) == 12)
check("正月=寅月(立春起)", reports[0]["基础信息"]["月支"] == "寅", reports[0]["基础信息"]["月支"])
check("命理月名正月", reports[0]["基础信息"]["月份"] == "正月")
check("寅月节气起=2.4", reports[0]["基础信息"]["节气日期段"][0] == "2.4")
check("午月节气段=6.5~7.7", reports[4]["基础信息"]["节气日期段"] == ("6.5", "7.7"))
check("子月节气段=12.7~次年1.5", reports[10]["基础信息"]["节气日期段"] == ("12.7", "次年1.5"))

# 五月·午月：双火叠、火气全年极值
wu = reports[4]
check("午月主导五行首位=火", wu["主导五行"][0] == "火", str(wu["主导五行"]))
check("午月格局含伏吟/双火叠", any("伏吟" in p and "双火叠" in p for p in wu["特殊格局"]), str(wu["特殊格局"]))

# 三月·辰月：水库，水入库
chen = reports[2]
check("辰月格局含水库", any("水库" in p for p in chen["特殊格局"]), str(chen["特殊格局"]))
check("辰月水入旺组", "水" in chen["主导五行"], str(chen["主导五行"]))

# 六月·未 / 九月·戌：燥土主导
check("未月主导=土", reports[5]["主导五行"][0] == "土", str(reports[5]["主导五行"]))
check("戌月主导=土且格局含火库",
      reports[8]["主导五行"][0] == "土" and any("火库" in p for p in reports[8]["特殊格局"]),
      str(reports[8]["主导五行"]) + str(reports[8]["特殊格局"]))

# 七月·申 / 八月·酉：金主导
check("申月主导=金", reports[6]["主导五行"][0] == "金", str(reports[6]["主导五行"]))
check("酉月主导=金", reports[7]["主导五行"][0] == "金", str(reports[7]["主导五行"]))

# 冬月·子月：水旺 + 子午冲
zi = reports[10]
check("子月主导=水", zi["主导五行"][0] == "水", str(zi["主导五行"]))
check("子月格局含子午冲", any("子午冲" in p for p in zi["特殊格局"]), str(zi["特殊格局"]))

# ── 11. 报告生成完整性（兼容旧接口 generate_report） ──
print("\n[报告生成]")
report = generate_report(2026, 6)
check("基础信息完整", all(k in report["基础信息"] for k in ["年份", "月份", "年干支", "月干支", "月令五行", "节气"]))
check("2026年6月年干支=丙午", report["基础信息"]["年干支"] == "丙午")
check("新字段·主导五行/主导描述/月令力量存在",
      all(k in report for k in ["主导五行", "主导描述", "月令力量"]))
check("行业预测主线非空", len(report["行业预测"]["主线"]) > 0)
check("操作建议非空", len(report["操作建议"]) > 0)

# ── 12. 格式化输出 ──
print("\n[格式化输出]")
text = format_report(report)
check("格式化包含标题", "五行行业分析" in text)
check("格式化包含五行力量", "【五行力量】" in text)
check("格式化包含行业预测", "【行业预测】" in text)
check("格式化包含风险提示", "【风险提示】" in text)

# ── 结果 ──
print(f"\n{'='*50}")
print(f"结果: {passed} passed, {failed} failed, {passed+failed} total")
sys.exit(1 if failed > 0 else 0)
