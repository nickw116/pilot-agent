#!/usr/bin/env python3
"""
五行行业轮动分析 - 增强版自然语言处理

支持更多自然语言表达方式。
"""

import sys
import re
from five_elements_analysis import generate_report, format_report

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
        # 全年分析
        results = []
        results.append("🔮 2026年丙午年 五行行业轮动全年分析")
        results.append("=" * 60)
        
        for m in range(1, 13):
            report = generate_report(year, m)
            results.append(f"\n📅 {m}月（{report['基础信息']['月干支']}月）")
            results.append(f"   五行：{report['基础信息']['月令五行']}旺")
            
            if report['特殊格局']:
                results.append(f"   格局：{', '.join(report['特殊格局'])}")
            
            results.append(f"   主线：{', '.join(report['行业预测']['主线'][:3])}")
        
        results.append("\n" + "=" * 60)
        results.append("💡 操作建议：根据月令五行变化，把握行业轮动节奏")
        results.append("⚠️ 风险提示：五行理论仅供参考，需结合基本面分析")
        
        return "\n".join(results)
    
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
