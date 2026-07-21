#!/usr/bin/env python3
"""
五行行业轮动分析 - 增强版自然语言处理

支持更多自然语言表达方式。
"""

import sys
import re
from five_elements_analysis import (
    generate_report,
    format_report,
    get_year_stems_branches,
    generate_year_reports,
)

ELEMENT_EMOJI = {"木": "🌿", "火": "🔥", "土": "🪨", "金": "💰", "水": "💧"}


def format_year_overview(year):
    """生成全年五行行业轮动一览（列表式·命理月·对齐豆包口径）"""
    year_stem, year_branch = get_year_stems_branches(year)
    lines = []
    lines.append(f"🔮 {year}年（{year_stem}{year_branch}年）五行行业轮动全年一览")
    lines.append("　立春起按节气换月令（非农历初一）；年柱丙火+午火，整体旺火")
    lines.append("━" * 46)
    lines.append("")

    for report in generate_year_reports(year):
        b = report["基础信息"]
        pred = report["行业预测"]
        me = b["月令五行"]
        period = b.get("节气日期段") or ("", "")
        period_str = f"{period[0]}～{period[1]}" if period[0] else b.get("节气", "")

        # 月份标题行：正月·庚寅月｜2.4~3.5
        lines.append(f"▌{b['月份']}·{b['月干支']}月｜{period_str}")

        # 月令 + 主导描述（旺:木>火；偏弱:土、金、水）
        emoji = ELEMENT_EMOJI.get(me, "")
        lines.append(f"   月令：{emoji} {me}当令　{report.get('主导描述','')}")

        # 特殊格局（库性/伏吟/刑冲）
        if report.get("特殊格局"):
            lines.append(f"   ✦格局：{'、'.join(report['特殊格局'])}")

        # 调候提示
        if report.get("调候提示"):
            for n in report["调候提示"]:
                lines.append(f"   💧调候：{n}")

        # 行业
        if pred["主线"]:
            lines.append(f"   🔥主线：{'、'.join(pred['主线'])}")
        if pred["支线"]:
            lines.append(f"   🌿支线：{'、'.join(pred['支线'])}")
        if pred["回避"]:
            lines.append(f"   ⚠回避：{'、'.join(pred['回避'])}")

        lines.append("")  # 月份间空行

    lines.append("─" * 46)
    lines.append("📊 全年规律：春(寅卯辰)木旺生火｜夏(巳午未)火极旺土燥｜秋(申酉戌)金旺火炼｜冬(亥子丑)金水制火")
    lines.append("💡 根据月令五行旺衰把握行业轮动节奏")
    lines.append("⚠️ 五行理论仅供参考，需结合基本面/技术面/资金面综合判断")

    return "\n".join(lines)

def parse_input_enhanced(text):
    """增强版自然语言解析"""
    text = text.lower().strip()
    
    # 匹配年份和月份
    patterns = [
        r'(\d{4})\s*年\s*(\d{1,2})\s*月',
        r'(\d{4})\s*[-/]\s*(\d{1,2})',
        r'(\d{4})\s*年\s*(\d{1,2})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            year = int(match.group(1))
            month = int(match.group(2))
            if 1 <= month <= 12:
                return year, month, "single"
    
    # 检查是否要求全年分析
    if any(keyword in text for keyword in ['各月', '全年', '每个月', '所有月份', '年度分析']):
        return 2026, None, "all"
    
    # 检查是否要求某个月份
    month_keywords = {
        '一月': 1, '二月': 2, '三月': 3, '四月': 4,
        '五月': 5, '六月': 6, '七月': 7, '八月': 8,
        '九月': 9, '十月': 10, '十一月': 11, '十二月': 12,
        '1月': 1, '2月': 2, '3月': 3, '4月': 4,
        '5月': 5, '6月': 6, '7月': 7, '8月': 8,
        '9月': 9, '10月': 10, '11月': 11, '12月': 12,
        '本月': None, '下月': None, '这个月': None, '下个月': None
    }
    
    for keyword, month in month_keywords.items():
        if keyword in text:
            # 对于"本月"、"下月"等，需要计算当前月份
            if month is None:
                from datetime import datetime
                current_month = datetime.now().month
                if '下' in keyword:
                    month = current_month + 1 if current_month < 12 else 1
                else:
                    month = current_month
            return 2026, month, "single"
    
    # 如果没有匹配到，返回提示
    return None, None, "help"

def analyze_text_enhanced(text):
    """增强版文本分析"""
    year, month, analysis_type = parse_input_enhanced(text)
    
    if analysis_type == "help":
        return """🔮 五行行业轮动分析

请指定要分析的内容，例如：
• "分析2026年7月的五行行业"
• "2026年8月五行看什么行业？"
• "今年各月的五行分析"
• "7月五行看什么行业？"

支持格式：2026年7月、2026-7、2026/7、7月等"""
    
    elif analysis_type == "all":
        # 全年分析（列表式一览，非表格）
        return format_year_overview(year)
    
    elif analysis_type == "single":
        # 单月分析
        report = generate_report(year, month)
        return format_report(report)
    
    return "分析出错，请重试"

def main():
    """主函数"""
    if len(sys.argv) > 1:
        text = " ".join(sys.argv[1:])
    else:
        text = sys.stdin.read().strip()
    
    if not text:
        print("请输入要分析的内容，例如：2026年7月五行行业分析")
        sys.exit(1)
    
    result = analyze_text_enhanced(text)
    print(result)

if __name__ == "__main__":
    main()
