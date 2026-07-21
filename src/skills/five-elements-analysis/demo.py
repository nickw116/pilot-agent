#!/usr/bin/env python3
"""
五行行业轮动分析 - 演示脚本

展示2026年各月的五行行业轮动分析。
"""

import sys
sys.path.insert(0, './scripts')

from five_elements_analysis import generate_report, format_report

def demo_2026():
    """演示2026年各月分析"""
    print("🔮 2026年丙午年 五行行业轮动全年分析")
    print("=" * 60)
    
    for month in range(1, 13):
        report = generate_report(2026, month)
        
        print(f"\n📅 {month}月（{report['基础信息']['月干支']}月）")
        print(f"   五行：{report['基础信息']['月令五行']}旺")
        
        if report['特殊格局']:
            print(f"   格局：{', '.join(report['特殊格局'])}")
        
        print(f"   主线：{', '.join(report['行业预测']['主线'][:3])}")
        
        if month == 6:
            print("   >>> 燥土余火，资源类接棒")
        elif month == 7:
            print("   >>> 燥土当令，资源股活跃")
        elif month == 8:
            print("   >>> 金气渐旺，金融股可能启动")

if __name__ == "__main__":
    demo_2026()
