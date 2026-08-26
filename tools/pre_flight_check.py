#!/usr/bin/env python3
"""
回答前自检脚本 - 5 项硬规则检查

用法：
    python3 pre_flight_check.py --text "回答草稿"
    python3 pre_flight_check.py --file path/to/draft.md

立规时间：2026-08-25
"""
import argparse
import re
import sys
from pathlib import Path


CHECKS = [
    {
        "id": 1,
        "name": "首屏有结论",
        "description": "首屏（前 300 字）必须出现答案/公式/具体内容",
        "check": "first_screen_has_conclusion",
    },
    {
        "id": 2,
        "name": "信源不打断阅读",
        "description": "正文里不应反复出现'来源:xxx'格式（最多 2 次）",
        "check": "source_not_interrupt",
    },
    {
        "id": 3,
        "name": "不先猜再问",
        "description": "不要在开头列 3 种可能让用户挑，要默认猜最可能的",
        "check": "not_too_many_options",
    },
    {
        "id": 4,
        "name": "结尾有行动钩子",
        "description": "结尾必须留行动钩子（'告诉我 xx 我帮你...'）",
        "check": "has_action_hook",
    },
    {
        "id": 5,
        "name": "查证过程不外露",
        "description": "正文里不要出现'我搜了xx'、'我查证了xx'、'我之前错了'等元信息",
        "check": "no_meta_info",
    },
]


def first_screen_has_conclusion(text):
    """检查首屏（标题后 300 字）是否有结论/公式/具体内容"""
    # 找第一个一级标题
    first_h1 = re.search(r"^#\s+.+?\n", text, re.MULTILINE)
    if first_h1:
        # 取标题后的内容
        after_title = text[first_h1.end():]
    else:
        # 没有标题，取开头
        after_title = text

    first_screen = after_title[:300]

    # 检查是否包含具体内容
    indicators = [
        r"\d+\s*[\*×/+\-=]\s*\d+",       # 算式（数字 运算符 数字）
        r"[\u4e00-\u9fa5A-Za-z_]+\s*=\s*\S+",  # 赋值
        r"^\s*[-*]\s+\S+",                # 列表项
        r"\|.+\|",                        # 表格行
        r"[A-Z\u4e00-\u9fa5]{4,}",        # 4 字以上短语
    ]
    for pat in indicators:
        if re.search(pat, first_screen, re.MULTILINE):
            return True
    return False


def source_not_interrupt(text):
    """检查正文里信源标注不超过 2 次"""
    pattern = re.compile(r"[（(]?\s*来源\s*[：:]\s*\S+[)）]?")
    matches = pattern.findall(text)
    return len(matches) <= 2


def not_too_many_options(text):
    """检查是否一开头列了 3 种以上可能让用户挑"""
    suspicious_patterns = [
        r"可能指[^\n]{0,30}(以下|几|多|3|三)",
        r"有以下[几\d种]+",
        r"你玩的是哪个[？?]",
        r"你想要哪种[？?]",
        r"你想要哪个[？?]",
    ]
    first_part = text[:500]
    for pat in suspicious_patterns:
        if re.search(pat, first_part):
            return False
    return True


def has_action_hook(text):
    """检查结尾是否有行动钩子"""
    tail = text[-200:]
    hook_patterns = [
        r"告诉我[你的]?\s*\S+",
        r"如果.{0,15}需要.{0,10}告诉我",
        r"可以.{0,10}帮你",
        r"完成后告诉我",
        r"[\?？]\s*$",
    ]
    for pat in hook_patterns:
        if re.search(pat, tail):
            return True
    return False


def no_meta_info(text):
    """检查正文里是否包含元信息（'我搜了'、'我之前错了'等）"""
    meta_patterns = [
        r"我搜了\d*个",
        r"我查证了",
        r"我之前.{0,5}错",
        r"我之前.{0,5}用了",
        r"经过.{0,10}验证",
        r"独立信源",
        r"多源交叉",
    ]
    for pat in meta_patterns:
        if re.search(pat, text):
            return False
    return True


CHECK_FUNCS = {
    "first_screen_has_conclusion": first_screen_has_conclusion,
    "source_not_interrupt": source_not_interrupt,
    "not_too_many_options": not_too_many_options,
    "has_action_hook": has_action_hook,
    "no_meta_info": no_meta_info,
}


def run_checks(text):
    results = []
    for check in CHECKS:
        func = CHECK_FUNCS[check["check"]]
        try:
            passed = func(text)
        except Exception as e:
            passed = False
            error = str(e)
        else:
            error = None
        results.append({
            "id": check["id"],
            "name": check["name"],
            "description": check["description"],
            "passed": passed,
            "error": error,
        })
    return {
        "all_passed": all(r["passed"] for r in results),
        "results": results,
    }


def format_report(result):
    lines = ["=" * 60]
    if result["all_passed"]:
        lines.append("✅ 5 项自检全部通过")
    else:
        lines.append("❌ 自检未通过，需修改：")
    lines.append("=" * 60)

    for r in result["results"]:
        status = "✅" if r["passed"] else "❌"
        lines.append(f"\n{status} [{r['id']}] {r['name']}")
        lines.append(f"   {r['description']}")
        if not r["passed"]:
            lines.append(f"   → 需要修正")

    lines.append("\n" + "=" * 60)
    fail_count = sum(1 for r in result["results"] if not r["passed"])
    pass_count = sum(1 for r in result["results"] if r["passed"])
    lines.append(f"通过 {pass_count}/5，失败 {fail_count}/5")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="回答前自检 - 5 项硬规则")
    parser.add_argument("--text", help="回答草稿文本")
    parser.add_argument("--file", help="回答草稿文件路径")
    parser.add_argument("--quiet", action="store_true", help="只输出是否通过")
    args = parser.parse_args()

    if args.file:
        text = Path(args.file).read_text(encoding="utf-8")
    elif args.text:
        text = args.text
    else:
        print("用法：python3 pre_flight_check.py --text '草稿' 或 --file draft.md")
        sys.exit(1)

    result = run_checks(text)

    if args.quiet:
        sys.exit(0 if result["all_passed"] else 1)
    else:
        print(format_report(result))
        sys.exit(0 if result["all_passed"] else 1)


if __name__ == "__main__":
    main()
