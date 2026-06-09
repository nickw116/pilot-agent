#!/usr/bin/env python3
"""
五行行业轮动分析 - 用户友好包装脚本

支持自然语言输入，自动解析年份和月份。
"""

import sys
import re
from five_elements_analysis import generate_report, format_report

def parse_input(text):
    """从自然语言文本中解析年份和月份"""
    # 匹配模式：2026年7月、2026年07月、2026-7、2026/7等
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
                return year, month
    
    # 如果没有找到，尝试从关键词推断
    current_year = 2026  # 默认当前年份
    
    # 月份关键词
    month_keywords = {
        '一月': 1, '二月': 2, '三月': 3, '四月': 4,
        '五月': 5, '六月': 6, '七月': 7, '八月': 8,
        '九月': 9, '十月': 10, '十一月': 11, '十二月': 12,
        '1月': 1, '2月': 2, '3月': 3, '4月': 4,
        '5月': 5, '6月': 6, '7月': 7, '8月': 8,
        '9月': 9, '10月': 10, '11月': 11, '12月': 12
    }
    
    for keyword, month in month_keywords.items():
        if keyword in text:
            return current_year, month
    
    return None, None

def analyze_text(text):
    """分析自然语言文本"""
    year, month = parse_input(text)
    
    if year and month:
        report = generate_report(year, month)
        return format_report(report)
    else:
        return """🔮 五行行业轮动分析

请指定要分析的年份和月份，例如：
• "分析2026年7月的五行行业"
• "2026年8月五行看什么行业？"
• "今年各月的五行分析"

支持格式：2026年7月、2026-7、2026/7等"""

def main():
    """主函数"""
    if len(sys.argv) > 1:
        # 如果有命令行参数，合并为一个字符串
        text = " ".join(sys.argv[1:])
    else:
        # 从标准输入读取
        text = sys.stdin.read().strip()
    
    if not text:
        print("请输入要分析的内容，例如：2026年7月五行行业分析")
        sys.exit(1)
    
    result = analyze_text(text)
    print(result)

if __name__ == "__main__":
    main()
