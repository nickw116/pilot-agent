#!/usr/bin/env python3
"""
verify_number.py
================
具体数字问题的多源收敛验证工具（2026-08-17 立规配套）。

设计目的：
    AGENTS.md 第 6 条要求"具体数字问题"必须多源验证、列候选值、并排证据。
    本脚本把这套方法论变成可调用工具，避免 Agent 凭一句话下结论。

使用流程：
    1) Agent 收到"具体数字"问题（堆叠数/攻击力/概率/日期 等）
    2) 调用 `generate_search_keywords(question, candidate_values)`
       → 拿到一组待搜的关键词
    3) Agent 调 web-search / web-reader 去搜这些关键词
       → 拿到一组 (keyword, snippet, url, source_type) 的证据
    4) 调用 `converge(question, candidate_values, evidences, min_sources=3)`
       → 输出每个候选值的支持/反对情况 + 最终建议
    5) Agent 据此写回答（必须按 AGENTS.md 第 6 条列出并排证据）

源码：
    /home/ubuntu/pilot-agent/tools/verify_number.py
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from typing import Iterable


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass
class Evidence:
    """一条证据（来自一次 web-search / web-reader 调用的结果）。"""
    keyword: str            # 用什么关键词搜到的
    snippet: str            # 摘要/正文片段
    url: str = ""           # 出处 URL
    source_type: str = ""   # 信源类型：攻略站 / 玩家社区 / 私服实测 / 官方wiki / 论坛 / 其他

    def to_dict(self):
        return asdict(self)


@dataclass
class CandidateResult:
    """一个候选值的验证结果。"""
    value: str
    support: list = field(default_factory=list)
    oppose: list = field(default_factory=list)
    neutral: list = field(default_factory=list)
    support_count: int = 0
    oppose_count: int = 0
    source_types_support: list = field(default_factory=list)

    def to_dict(self):
        return {
            "value": self.value,
            "support": self.support,
            "oppose": self.oppose,
            "neutral": self.neutral,
            "support_count": self.support_count,
            "oppose_count": self.oppose_count,
            "source_types_support": self.source_types_support,
        }


# ---------------------------------------------------------------------------
# Step 1: 生成搜索关键词
# ---------------------------------------------------------------------------

def _extract_clean_keywords(question: str) -> list:
    """从问题里抽出核心实体词。"""
    cleaned = question.strip()
    cleaned = re.sub(r"(多少个|多少|几个|几个一组|一组多少|一组几个|是几|是多少|准确数值|准确数字)", "", cleaned)
    cleaned = re.sub(r"[？?]+", "", cleaned).strip()
    return [cleaned] if cleaned else [question.strip()]


def generate_search_keywords(question: str, candidate_values: Iterable) -> list:
    """
    给定问题和候选值，生成一组待搜的关键词。

    Args:
        question: 用户原始问题，如 "079 黑刺一组多少个"
        candidate_values: 候选数字列表，如 [800, 1000, 1200]

    Returns:
        关键词列表（去重），覆盖：直问 + 每个候选值各搜一次 + 限定词
    """
    core_kws = _extract_clean_keywords(question)
    candidates = [str(v) for v in candidate_values]

    keywords = []
    seen = set()

    def add(kw):
        kw = kw.strip()
        if kw and kw not in seen:
            keywords.append(kw)
            seen.add(kw)

    # 1. 直问
    for core in core_kws:
        add(question)
        add(core)
        add(f"{core} 数量")
        add(f"{core} 一组")
        add(f"{core} 准确数值")
        add(f"{core} 官方")
        add(f"{core} wiki")
        add(f"{core} 数据库")

    # 2. 每个候选值都搜一次
    for core in core_kws:
        for v in candidates:
            add(f"{core} {v}")
            add(f"{core} {v} 个")

    # 3. 邻近对比
    if len(candidates) >= 2:
        joined = " ".join(candidates)
        for core in core_kws:
            add(f"{core} {joined}")
            add(f"{core} 对比 {joined}")

    return keywords


# ---------------------------------------------------------------------------
# Step 2: 信源类型识别
# ---------------------------------------------------------------------------

SOURCE_TYPE_RULES = [
    (r"(wiki|官网|gamewith|maplestory\.wiki|冒险岛wiki|nexon|官方)", "官方wiki"),
    (r"(bilibili|b站|nga|贴吧|tieba|baidu\.com/(?:tieba|forum))", "玩家社区"),
    (r"(mxd\.|mxdc|mxd079|17173|52pk|766|duowan|多玩)", "攻略站"),
    (r"(私服|怀旧服|cms|tms|kms|gms|服务器)", "私服实测"),
    (r"(攻略|指南|综合)", "攻略站"),
    (r"(论坛|贴|讨论|玩家|分享)", "玩家社区"),
    (r"(github\.com|gitee|码云)", "工具书"),
]


def classify_source(url: str, snippet: str = "") -> str:
    """根据 URL / 摘要 推断信源类型。"""
    text = f"{url} {snippet}"
    for pattern, stype in SOURCE_TYPE_RULES:
        if re.search(pattern, text, re.IGNORECASE):
            return stype
    return "其他"


# ---------------------------------------------------------------------------
# Step 3: 收敛判断（核心）
# ---------------------------------------------------------------------------

def _match_value(snippet: str, value: str) -> bool:
    """判断 snippet 里是否提到了 value。"""
    if re.search(rf"(?<!\d){re.escape(value)}(?!\d)", snippet):
        return True
    try:
        n = int(value)
        cn_simple = {
            800: "八百", 1000: "一千", 1200: "一千二百", 1500: "一千五百",
            2000: "两千", 500: "五百", 100: "一百", 10000: "一万",
        }
        cn_form = cn_simple.get(n)
        if cn_form and cn_form in snippet:
            return True
    except ValueError:
        pass
    return False


def _classify_stance(snippet: str, value: str, all_candidates: list) -> str:
    """把一条证据分类：support / oppose / neutral。"""
    has_value = _match_value(snippet, value)

    negation_pattern = rf"(不是|并非|错误|不对|应[^，。;]{{0,5}}为)\s*{re.escape(value)}"
    has_negation = bool(re.search(negation_pattern, snippet))

    if has_value and not has_negation:
        return "support"
    if has_value and has_negation:
        return "oppose"

    others = [c for c in all_candidates if c != value]
    for o in others:
        if _match_value(snippet, o):
            return "oppose"

    return "neutral"


def converge(
    question: str,
    candidate_values: Iterable,
    evidences: list,
    min_sources: int = 3,
) -> dict:
    """
    多源收敛判断。

    Returns:
        dict 包含 results / ranking / winner / confidence / verdict
    """
    candidates = [str(v) for v in candidate_values]
    results = {v: CandidateResult(value=v) for v in candidates}

    for ev in evidences:
        if not ev.snippet:
            continue
        stype = ev.source_type or classify_source(ev.url, ev.snippet)
        for v in candidates:
            stance = _classify_stance(ev.snippet, v, candidates)
            entry = {"keyword": ev.keyword, "url": ev.url, "snippet": ev.snippet[:200], "source_type": stype}
            if stance == "support":
                results[v].support.append(entry)
            elif stance == "oppose":
                results[v].oppose.append(entry)
            else:
                results[v].neutral.append(entry)

    for v in candidates:
        r = results[v]
        r.support_count = len(r.support)
        r.oppose_count = len(r.oppose)
        r.source_types_support = sorted(set(e["source_type"] for e in r.support))

    ranking = sorted(
        candidates,
        key=lambda v: (
            -results[v].support_count,
            -len(results[v].source_types_support),
            results[v].oppose_count,
        ),
    )

    winner = ranking[0]
    winner_r = results[winner]

    distinct_sources = len(winner_r.source_types_support)
    if winner_r.support_count >= 3 and distinct_sources >= 2:
        confidence = "high"
    elif winner_r.support_count >= 2 and distinct_sources >= 1:
        confidence = "medium"
    else:
        confidence = "low"

    conflict_warning = ""
    if len(ranking) >= 2:
        second = ranking[1]
        second_r = results[second]
        if winner_r.support_count > 0 and second_r.support_count > 0:
            if abs(winner_r.support_count - second_r.support_count) <= 1:
                conflict_warning = (
                    f"⚠️ 候选值 {winner} 和 {second} 支持数相近"
                    f"（{winner_r.support_count} vs {second_r.support_count}），"
                    "建议 Agent 把两者并排列出，让用户判断。"
                )

    if winner_r.support_count < min_sources:
        conflict_warning = (
            f"⚠️ 胜出值 {winner} 支持数（{winner_r.support_count}）"
            f"< {min_sources} 个，AGENTS.md 第 6 条要求至少 {min_sources} 个独立信源。"
            "请 Agent 继续搜更多信源，或在回答里明确告知用户'结论待证'。"
        ) + (conflict_warning or "")

    verdict_lines = [
        f"胜出值: {winner}（{confidence}）",
        f"支持数: {winner_r.support_count} / 信源类型: {winner_r.source_types_support}",
        f"反对数: {winner_r.oppose_count}",
    ]
    if conflict_warning:
        verdict_lines.append(conflict_warning)

    return {
        "question": question,
        "candidates": candidates,
        "results": {v: r.to_dict() for v, r in results.items()},
        "ranking": ranking,
        "winner": winner,
        "confidence": confidence,
        "verdict": "\n".join(verdict_lines),
    }


# ---------------------------------------------------------------------------
# 输出格式化
# ---------------------------------------------------------------------------

def format_report(converge_result: dict) -> str:
    """把 converge 结果格式化为 markdown。"""
    lines = []
    q = converge_result["question"]
    lines.append(f"## 多源验证报告：{q}\n")
    lines.append(f"**胜出**: `{converge_result['winner']}`（置信度: {converge_result['confidence']}）\n")
    lines.append(f"**排名**: {' > '.join(converge_result['ranking'])}\n")
    lines.append("\n### 各候选值详情\n")
    lines.append("| 候选值 | 支持数 | 反对数 | 支持信源类型 |")
    lines.append("|--------|--------|--------|--------------|")
    for v in converge_result["candidates"]:
        r = converge_result["results"][v]
        types_str = ", ".join(r["source_types_support"]) or "—"
        lines.append(f"| `{v}` | {r['support_count']} | {r['oppose_count']} | {types_str} |")

    lines.append("\n### 支持证据（按候选值）\n")
    for v in converge_result["candidates"]:
        r = converge_result["results"][v]
        if r["support"]:
            lines.append(f"**{v}** 的支持证据：")
            for e in r["support"][:5]:
                lines.append(f"- [{e['source_type']}] {e['snippet']} (来源: {e['url'] or e['keyword']})")
            lines.append("")

    lines.append("\n### 反对/冲突证据\n")
    for v in converge_result["candidates"]:
        r = converge_result["results"][v]
        if r["oppose"]:
            lines.append(f"**{v}** 的反对/冲突证据：")
            for e in r["oppose"][:3]:
                lines.append(f"- [{e['source_type']}] {e['snippet']} (来源: {e['url'] or e['keyword']})")
            lines.append("")

    lines.append("\n### Verdict\n")
    lines.append("```\n" + converge_result["verdict"] + "\n```\n")
    lines.append("\n> 按 AGENTS.md 第 6 条要求，回答中需**并排列出**胜出值与冲突值的证据，让用户判断。\n")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 命令行入口
# ---------------------------------------------------------------------------

def main():
    import sys
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 verify_number.py keywords <question> <cand1> <cand2> ...")
        print("  python3 verify_number.py converge <json_file>")
        print("")
        print("Or in Python:")
        print("  from verify_number import generate_search_keywords, converge, Evidence, format_report")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "keywords":
        if len(sys.argv) < 4:
            print("Usage: python3 verify_number.py keywords <question> <cand1> <cand2> ...")
            sys.exit(1)
        question = sys.argv[2]
        candidates = sys.argv[3:]
        kws = generate_search_keywords(question, candidates)
        print(json.dumps({"question": question, "candidates": candidates, "keywords": kws}, ensure_ascii=False, indent=2))
    elif cmd == "converge":
        json_path = sys.argv[2]
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        result = converge(
            question=data["question"],
            candidate_values=data["candidates"],
            evidences=[Evidence(**e) for e in data["evidences"]],
            min_sources=data.get("min_sources", 3),
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print("\n--- formatted report ---")
        print(format_report(result))
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
