#!/usr/bin/env python3
"""
五行行业轮动分析脚本

基于天干地支、月令五行、生克制化分析行业轮动规律。
"""

import sys
import json
from datetime import datetime, timedelta

# 五行属性映射
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

# 地支藏干
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

# 五行生克关系
GENERATION = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
OVERCOMING = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}

# 行业五行映射
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

# 月支对应的节气（简化版，实际需要精确节气表）
SOLAR_TERMS = {
    "寅": "立春-惊蛰",
    "卯": "惊蛰-清明", 
    "辰": "清明-立夏",
    "巳": "立夏-芒种",
    "午": "芒种-小暑",
    "未": "小暑-立秋",
    "申": "立秋-白露",
    "酉": "白露-寒露",
    "戌": "寒露-立冬",
    "亥": "立冬-大雪",
    "子": "大雪-小寒",
    "丑": "小寒-立春"
}

def get_year_stems_branches(year):
    """计算年干支"""
    # 天干
    stems = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
    # 地支
    branches = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
    
    stem_idx = (year - 4) % 10
    branch_idx = (year - 4) % 12
    
    return stems[stem_idx], branches[branch_idx]

def get_month_stems_branches(year_stem, month_branch):
    """根据年干和月支计算月干"""
    # 月干计算规则：年干合化，甲己之年丙寅首，乙庚之年戊寅头...
    year_stem_idx = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"].index(year_stem)
    
    # 月干起始表
    month_stem_start = {
        "甲": 2, "己": 2,  # 丙寅
        "乙": 4, "庚": 4,  # 戊寅
        "丙": 6, "辛": 6,  # 庚寅
        "丁": 8, "壬": 8,  # 壬寅
        "戊": 0, "癸": 0   # 甲寅
    }
    
    month_branch_idx = ["寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥", "子", "丑"].index(month_branch)
    
    start_idx = month_stem_start[year_stem]
    month_stem_idx = (start_idx + month_branch_idx) % 10
    
    return ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"][month_stem_idx]

def analyze_prosperity(element, month_element):
    """分析五行旺衰"""
    if element == month_element:
        return "旺"
    elif GENERATION.get(element) == month_element:
        return "相"  # 我生之五行
    elif OVERCOMING.get(month_element) == element:
        return "死"  # 克我之五行
    elif OVERCOMING.get(element) == month_element:
        return "囚"  # 我克之五行
    else:
        return "休"

def analyze_special_patterns(year_branch, month_branch, month_stem):
    """分析特殊格局"""
    patterns = []
    
    # 伏吟：年支与月支相同
    if year_branch == month_branch:
        patterns.append("伏吟")
    
    # 燥土：未、戌为燥土
    if month_branch in ["未", "戌"]:
        patterns.append("燥土")
    
    # 湿土：辰、丑为湿土
    if month_branch in ["辰", "丑"]:
        patterns.append("湿土")
    
    # 天干地支关系
    stem_element = FIVE_ELEMENTS[month_stem]
    branch_element = FIVE_ELEMENTS[month_branch]
    
    if stem_element == branch_element:
        patterns.append("天干地支同气")
    elif GENERATION.get(stem_element) == branch_element:
        patterns.append("天干生地支")
    elif OVERCOMING.get(stem_element) == branch_element:
        patterns.append("天干克地支")
    
    return patterns

def generate_report(year, month, day=None):
    """生成分析报告"""
    # 计算年干支
    year_stem, year_branch = get_year_stems_branches(year)
    
    # 月支映射（简化：1月=丑，2月=寅...）
    month_branches = ["丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥", "子"]
    month_branch = month_branches[(month - 1) % 12]
    
    # 计算月干
    month_stem = get_month_stems_branches(year_stem, month_branch)
    
    # 五行分析
    month_element = FIVE_ELEMENTS[month_branch]
    year_element = FIVE_ELEMENTS[year_branch]
    
    # 特殊格局分析
    special_patterns = analyze_special_patterns(year_branch, month_branch, month_stem)
    
    # 五行旺衰分析
    prosperity = {}
    for element in ["木", "火", "土", "金", "水"]:
        prosperity[element] = analyze_prosperity(element, month_element)
    
    # 行业预测
    predictions = {
        "主线": [],
        "支线": [],
        "回避": []
    }
    
    # 根据月令五行确定主线行业
    if month_element == "火":
        predictions["主线"] = INDUSTRY_MAPPING["火"]["核心"][:3]
        if "伏吟" in special_patterns:
            predictions["主线"] = ["AI算力", "光模块", "半导体"]
        predictions["支线"] = INDUSTRY_MAPPING["火"]["衍生"][:2]
        predictions["回避"] = INDUSTRY_MAPPING["金"]["核心"][:2]
        
    elif month_element == "木":
        predictions["主线"] = INDUSTRY_MAPPING["木"]["核心"][:3]
        predictions["支线"] = INDUSTRY_MAPPING["木"]["衍生"][:2]
        predictions["回避"] = INDUSTRY_MAPPING["土"]["核心"][:2]
        
    elif month_element == "土":
        predictions["主线"] = INDUSTRY_MAPPING["土"]["核心"][:3]
        if "燥土" in special_patterns:
            predictions["主线"].extend(["煤炭", "有色金属"])
        predictions["支线"] = INDUSTRY_MAPPING["土"]["衍生"][:2]
        predictions["回避"] = INDUSTRY_MAPPING["水"]["核心"][:2]
        
    elif month_element == "金":
        predictions["主线"] = INDUSTRY_MAPPING["金"]["核心"][:3]
        predictions["支线"] = INDUSTRY_MAPPING["金"]["衍生"][:2]
        predictions["回避"] = INDUSTRY_MAPPING["火"]["核心"][:2]
        
    elif month_element == "水":
        predictions["主线"] = INDUSTRY_MAPPING["水"]["核心"][:3]
        predictions["支线"] = INDUSTRY_MAPPING["水"]["衍生"][:2]
        predictions["回避"] = INDUSTRY_MAPPING["火"]["核心"][:2]
    
    # 生成报告
    report = {
        "基础信息": {
            "年份": year,
            "月份": month,
            "年干支": f"{year_stem}{year_branch}",
            "月干支": f"{month_stem}{month_branch}",
            "月令五行": month_element,
            "节气": SOLAR_TERMS.get(month_branch, "")
        },
        "特殊格局": special_patterns,
        "五行旺衰": prosperity,
        "行业预测": predictions,
        "操作建议": generate_advice(month_element, special_patterns, prosperity)
    }
    
    return report

def generate_advice(month_element, patterns, prosperity):
    """生成操作建议"""
    advice = []
    
    if month_element == "火":
        if "伏吟" in patterns:
            advice.append("午火伏吟，火气极旺，重点配置AI、半导体等火属性行业")
        else:
            advice.append("火旺当令，关注科技成长股，适当配置新能源")
        advice.append("回避金融、机械等金属性行业（火克金）")
        
    elif month_element == "木":
        advice.append("木旺当令，关注医药、环保等木属性行业")
        advice.append("木生火，可提前布局火属性行业")
        
    elif month_element == "土":
        if "燥土" in patterns:
            advice.append("燥土当令，关注资源类股票（煤炭、有色金属）")
        else:
            advice.append("土旺当令，关注基建、房地产等土属性行业")
        advice.append("土生金，可关注金融、机械等金属性行业")
        
    elif month_element == "金":
        advice.append("金旺当令，关注金融、机械等金属性行业")
        advice.append("金生水，可关注物流、旅游等水属性行业")
        
    elif month_element == "水":
        advice.append("水旺当令，关注物流、旅游等水属性行业")
        advice.append("水生木，可关注医药、环保等木属性行业")
    
    return advice

def format_report(report):
    """格式化报告输出"""
    lines = []
    lines.append(f"🔮 {report['基础信息']['年份']}年{report['基础信息']['月份']}月 五行行业轮动分析")
    lines.append("=" * 50)
    lines.append("")
    lines.append("【基础信息】")
    lines.append(f"  年干支：{report['基础信息']['年干支']}")
    lines.append(f"  月干支：{report['基础信息']['月干支']}")
    lines.append(f"  月令五行：{report['基础信息']['月令五行']}旺")
    lines.append(f"  节气时段：{report['基础信息']['节气']}")
    
    if report['特殊格局']:
        lines.append(f"  特殊格局：{', '.join(report['特殊格局'])}")
    
    lines.append("")
    lines.append("【五行旺衰】")
    for element, state in report['五行旺衰'].items():
        lines.append(f"  {element}：{state}")
    
    lines.append("")
    lines.append("【行业预测】")
    lines.append("  🔥 主线行业：")
    for industry in report['行业预测']['主线']:
        lines.append(f"    • {industry}")
    
    lines.append("  🌿 支线行业：")
    for industry in report['行业预测']['支线']:
        lines.append(f"    • {industry}")
    
    lines.append("  ⚠️ 回避行业：")
    for industry in report['行业预测']['回避']:
        lines.append(f"    • {industry}")
    
    lines.append("")
    lines.append("【操作建议】")
    for advice in report['操作建议']:
        lines.append(f"  • {advice}")
    
    lines.append("")
    lines.append("【风险提示】")
    lines.append("  • 五行理论为传统文化分析方法，仅供参考")
    lines.append("  • 需结合基本面、技术面、资金面综合判断")
    lines.append("  • 特殊事件可能改变行业运行节奏")
    lines.append("  • 投资有风险，决策需谨慎")
    
    return "\n".join(lines)

def main():
    """主函数"""
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
        
        # 生成分析报告
        report = generate_report(year, month)
        
        # 输出格式化报告
        print(format_report(report))
        
        # 同时输出JSON格式（供程序调用）
        print("\n" + "=" * 50)
        print("JSON数据:")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        
    except ValueError:
        print("请输入有效的年份和月份")
        sys.exit(1)

if __name__ == "__main__":
    main()
