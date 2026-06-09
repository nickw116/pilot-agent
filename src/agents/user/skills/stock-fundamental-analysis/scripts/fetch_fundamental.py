#!/usr/bin/env python3
"""
个股基本面分析脚本

从本地 PostgreSQL 知识库（stocks_db）拉取基本面数据，
可选从韭研公社获取题材/异动数据作为辅助参考。

数据源优先级：
  1. PostgreSQL stocks_db（必须）
  2. 韭研公社（可选，需 Cookie，失败时优雅降级）

用法：
  python fetch_fundamental.py --code 002471              # 基本面分析
  python fetch_fundamental.py --code sz002471 --json     # JSON 输出
  python fetch_fundamental.py --code 603267 --verbose    # 详细输出
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime

import psycopg2
import psycopg2.extras

# ── 数据库配置 ──
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "stocks_db",
    "user": "pilot",
    "password": "pilot123",
}

# ── 缓存配置 ──
CACHE_DIR = os.path.join(os.path.dirname(__file__), ".cache")
CACHE_TTL = 3600  # 1 小时

# ── 韭研公社脚本路径（可选） ──
JIUYAN_SCRIPT = os.path.join(
    os.path.dirname(__file__),
    "/dev/null/jiuyan_disabled"  # 韭研公社已下线
)
JIUYAN_COOKIE_FILE = os.path.join(
    os.path.dirname(__file__),
    "/dev/null/jiuyan_disabled"  # 韭研公社已下线
)


def normalize_code(code: str) -> tuple[str, str]:
    """
    标准化股票代码，返回 (纯数字, DB格式)。
    支持输入: 002471 / sz002471 / 002471.SZ
    返回示例: ("002471", "002471.SZ")
    """
    code = code.strip().upper()
    # 去掉已知前缀
    for prefix in ("SZ", "SH", "BJ"):
        if code.startswith(prefix):
            code = code[len(prefix):]
            break
    # 去掉后缀
    code = code.replace(".SZ", "").replace(".SH", "").replace(".BJ", "")

    if not code.isdigit():
        return code, code

    # 判断市场
    if code.startswith("6"):
        return code, f"{code}.SH"
    elif code.startswith(("0", "3")):
        return code, f"{code}.SZ"
    elif code.startswith(("4", "8")):
        return code, f"{code}.BJ"
    return code, code


def get_db_connection():
    """获取 PostgreSQL 连接"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except psycopg2.OperationalError as e:
        print(json.dumps({
            "error": "数据库连接失败",
            "detail": str(e),
            "hint": "请检查 PostgreSQL 服务是否运行，以及 stocks_db 数据库是否存在",
        }, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(2)


def fetch_fundamental_from_db(conn, db_code: str) -> dict | None:
    """从 stocks_db 查询基本面数据"""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT stock_code, stock_name, pe_median, pe_percentile,
                   industry_level1, industry_level2, industry_level3,
                   is_leader, description,
                   fund_holding, fund_change,
                   northbound_holding, northbound_change,
                   created_at, updated_at
            FROM stocks WHERE stock_code = %s
        """, (db_code,))
        row = cur.fetchone()
        if row is None:
            return None
        return dict(row)


def fetch_peers(conn, stock: dict) -> list[dict]:
    """查询同行业（level3）股票的 PE 数据用于对比"""
    if not stock.get("industry_level3"):
        return []
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT stock_code, stock_name, pe_median, pe_percentile, is_leader
            FROM stocks
            WHERE industry_level3 = %s AND stock_code != %s
            ORDER BY pe_percentile ASC NULLS LAST
            LIMIT 10
        """, (stock["industry_level3"], stock["stock_code"]))
        return [dict(r) for r in cur.fetchall()]


def try_fetch_jiuyan(pure_code: str) -> dict:
    """
    尝试从韭研公社获取题材/异动数据。
    失败时返回空 dict + 警告信息，不影响主流程。
    """
    result = {"available": False, "warning": ""}

    # 检查 Cookie 文件是否存在
    cookie = ""
    if os.path.exists(JIUYAN_COOKIE_FILE):
        with open(JIUYAN_COOKIE_FILE) as f:
            cookie = f.read().strip()

    if not cookie:
        result["warning"] = "韭研公社数据未配置（需登录 Cookie），题材/异动数据不可用"
        return result

    # 尝试导入并调用韭研公社脚本
    if not os.path.exists(JIUYAN_SCRIPT):
        result["warning"] = "韭研公社脚本不可用（旧 skill 已下线）"
        return result

    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("fetch_anomaly", JIUYAN_SCRIPT)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        date_str = datetime.now().strftime("%Y-%m-%d")
        # 标准化为韭研公社格式 sz002471
        normalized = mod.normalize_code(pure_code)
        results = []
        for offset in range(5):
            from datetime import timedelta
            d = datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=offset)
            d_str = d.strftime("%Y-%m-%d")
            categories = mod.fetch_via_api(d_str, cookie)
            if not categories:
                continue
            results = mod.search_stocks(categories, code=pure_code)
            if results:
                break

        if results:
            result["available"] = True
            result["date"] = date_str
            result["items"] = []
            for r in results[:3]:  # 最多取 3 条
                result["items"].append({
                    "category": r.get("category", ""),
                    "category_reason": r.get("category_reason", ""),
                    "expound": r.get("expound", ""),
                    "time": r.get("time", ""),
                    "num": r.get("num", ""),
                })
        else:
            result["warning"] = f"韭研公社未找到 {pure_code} 近期题材数据"

    except Exception as e:
        result["warning"] = f"韭研公社调用失败: {e}"

    return result


# ── 缓存 ──

def _cache_path(db_code: str) -> str:
    return os.path.join(CACHE_DIR, f"{db_code}.json")


def load_cache(db_code: str) -> dict | None:
    """加载缓存，过期返回 None"""
    path = _cache_path(db_code)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            data = json.load(f)
        if time.time() - data.get("cached_at", 0) > CACHE_TTL:
            return None
        return data
    except (json.JSONDecodeError, OSError):
        return None


def save_cache(db_code: str, data: dict):
    """保存缓存"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    data["cached_at"] = time.time()
    with open(_cache_path(db_code), "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── 输出格式化 ──

def format_pe_comment(percentile) -> str:
    """PE 分位评价"""
    if percentile is None:
        return "无数据"
    if percentile > 70:
        return "偏高"
    elif percentile >= 30:
        return "合理"
    else:
        return "偏低"


def format_fund_change(change) -> str:
    """基金持仓变动描述"""
    if change is None:
        return "无数据"
    if change > 0:
        return f"增加 {change:.2f} 亿"
    elif change < 0:
        return f"减少 {abs(change):.2f} 亿"
    return "持平"


def format_northbound_change(change) -> str:
    """北向持仓变动描述"""
    if change is None:
        return "无数据"
    if change > 0:
        return f"加仓 {change:.2f} 亿"
    elif change < 0:
        return f"减仓 {abs(change):.2f} 亿"
    return "持平"


def format_report(stock: dict, peers: list[dict], jiuyan: dict, verbose: bool = False) -> str:
    """格式化人类可读报告"""
    code = stock["stock_code"]
    name = stock["stock_name"]
    lines = []

    lines.append(f"## {name}（{code}）基本面分析\n")

    # 一、核心结论（简要概述）
    pe_comment = format_pe_comment(stock.get("pe_percentile"))
    leader_tag = "行业龙头" if stock.get("is_leader") in ("1", 1, True, "是") else ""
    is_leader_yes = stock.get("is_leader") in ("1", 1, True, "是")
    industry = " → ".join(filter(None, [
        stock.get("industry_level1", ""),
        stock.get("industry_level2", ""),
        stock.get("industry_level3", ""),
    ]))
    desc = stock.get("description") or "暂无描述"

    conclusion_parts = [f"{name}（{code}）" ]
    if leader_tag:
        conclusion_parts.append(f"是{stock.get('industry_level3', '')}领域的{leader_tag}")
    else:
        conclusion_parts.append(f"属于{industry}行业")
    conclusion_parts.append(f"，当前 PE 分位{pe_comment}")

    if stock.get("fund_holding") is not None and stock["fund_holding"] > 5:
        conclusion_parts.append("，公募持仓较高")
    if stock.get("northbound_holding") is not None and stock["northbound_holding"] > 1:
        conclusion_parts.append("，北向资金有持仓")

    lines.append("### 一、核心结论")
    lines.append("".join(conclusion_parts) + "。\n")

    # 二、公司基本面
    lines.append("### 二、公司基本面")
    lines.append(f"- **主营业务**: {desc}")
    if is_leader_yes:
        lines.append(f"- **行业地位**: {leader_tag}")
    lines.append(f"- **行业分类**: {industry}\n")

    # 三、估值水平
    pe_median = stock.get("pe_median")
    pe_percentile = stock.get("pe_percentile")
    lines.append("### 三、估值水平")
    if pe_median is not None:
        lines.append(f"- **PE 中值**: {pe_median:.2f}")
    else:
        lines.append("- **PE 中值**: 无数据")
    if pe_percentile is not None:
        lines.append(f"- **PE 历史分位**: {pe_percentile:.1f}%（{pe_comment}）")
    else:
        lines.append("- **PE 历史分位**: 无数据")
    lines.append("")

    # 四、资金动向
    lines.append("### 四、资金动向")
    fund_h = stock.get("fund_holding")
    fund_c = stock.get("fund_change")
    if fund_h is not None:
        fund_c_desc = format_fund_change(fund_c)
        lines.append(f"- **公募持仓**: {fund_h:.2f} 亿元（{fund_c_desc}）")
    else:
        lines.append("- **公募持仓**: 无数据")

    nb_h = stock.get("northbound_holding")
    nb_c = stock.get("northbound_change")
    if nb_h is not None:
        nb_c_desc = format_northbound_change(nb_c)
        lines.append(f"- **北向持仓**: {nb_h:.2f} 亿元（{nb_c_desc}）")
    else:
        lines.append("- **北向持仓**: 无数据")
    lines.append("")

    # 五、同行业 PE 对比
    if peers:
        lines.append("### 五、行业地位")
        lines.append(f"在 {stock.get('industry_level3', '同行业')} 中的 PE 对比：")
        lines.append("")
        lines.append("| 股票 | PE 中值 | PE 分位 | 龙头 |")
        lines.append("|------|---------|---------|------|")
        # 当前股票
        pe_m = f"{pe_median:.1f}" if pe_median else "-"
        pe_p = f"{pe_percentile:.1f}%" if pe_percentile else "-"
        is_l = "是" if stock.get("is_leader") in ("1", 1, True, "是") else ""
        lines.append(f"| **{name}** | **{pe_m}** | **{pe_p}** | {is_l} |")
        for p in peers[:8]:
            p_pe = f"{p['pe_median']:.1f}" if p.get("pe_median") else "-"
            p_pct = f"{p['pe_percentile']:.1f}%" if p.get("pe_percentile") else "-"
            p_lead = "是" if p.get("is_leader") in ("1", 1, True, "是") else ""
            lines.append(f"| {p['stock_name']} | {p_pe} | {p_pct} | {p_lead} |")
        lines.append("")

    # 六、韭研公社题材参考
    lines.append("### 六、韭研公社题材参考")
    if jiuyan.get("available") and jiuyan.get("items"):
        for item in jiuyan["items"][:3]:
            if item.get("category"):
                lines.append(f"- **板块**: {item['category']}")
            if item.get("category_reason"):
                lines.append(f"  - **催化剂**: {item['category_reason']}")
            if item.get("expound"):
                expound = item["expound"]
                if verbose or len(expound) < 2000:
                    lines.append(f"  - **解析**: {expound}")
                else:
                    lines.append(f"  - **解析**: {expound[:2000]}...")
    else:
        lines.append(f"*{jiuyan.get('warning', '韭研公社数据不可用')}*")
    lines.append("")

    # 七、投资亮点与风险
    lines.append("### 七、投资亮点与风险")
    highlights = []
    risks = []

    # 基于数据自动生成
    if leader_tag:
        highlights.append(f"行业龙头，{stock.get('industry_level3', '')}领域领先企业")
    if pe_percentile is not None and pe_percentile < 30:
        highlights.append(f"估值处于历史低位（PE 分位 {pe_percentile:.1f}%）")
    elif pe_percentile is not None and pe_percentile < 50:
        highlights.append(f"估值处于合理偏低水平（PE 分位 {pe_percentile:.1f}%）")
    if fund_h is not None and fund_h > 5:
        highlights.append(f"公募基金重仓（{fund_h:.2f} 亿元）")
    if nb_h is not None and nb_h > 1:
        highlights.append(f"北向资金持仓（{nb_h:.2f} 亿元）")
    if nb_c is not None and nb_c > 0:
        highlights.append("北向资金近期加仓")

    if pe_percentile is not None and pe_percentile > 70:
        risks.append(f"估值偏高（PE 分位 {pe_percentile:.1f}%）")
    if fund_c is not None and fund_c < -5:
        risks.append(f"公募基金大幅减仓（{abs(fund_c):.2f} 亿元）")
    if nb_c is not None and nb_c < 0:
        risks.append(f"北向资金近期减仓（{abs(nb_c):.2f} 亿元）")
    if not desc or desc == "暂无描述":
        risks.append("缺少主营业务描述，信息不完整")

    # 补充到至少 1 条
    if not highlights:
        highlights.append("数据有限，暂无明显亮点")
    if not risks:
        risks.append("投资有风险，以上分析仅供参考")

    lines.append("- **亮点**:")
    for h in highlights[:3]:
        lines.append(f"  1. {h}")
    lines.append("- **风险**:")
    for r in risks[:3]:
        lines.append(f"  1. {r}")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="个股基本面分析（stocks_db + 韭研公社）")
    parser.add_argument("--code", "-c", required=True, help="股票代码，如 002471、sz002471、603678")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    parser.add_argument("--verbose", "-v", action="store_true", help="显示完整韭研公社解析文本")
    parser.add_argument("--no-cache", action="store_true", help="忽略缓存，强制刷新")
    parser.add_argument("--no-jiuyan", action="store_true", help="跳过韭研公社数据")
    args = parser.parse_args()

    pure_code, db_code = normalize_code(args.code)

    # 检查缓存
    if not args.no_cache and not args.no_jiuyan:
        cached = load_cache(db_code)
        if cached:
            if args.json:
                print(json.dumps(cached, ensure_ascii=False, indent=2))
            else:
                print(cached.get("_report", json.dumps(cached, ensure_ascii=False, indent=2)))
            return

    # 第一步：从数据库获取基本面数据
    conn = get_db_connection()
    try:
        stock = fetch_fundamental_from_db(conn, db_code)
        if stock is None:
            error = {
                "error": f"未找到股票 {db_code}",
                "hint": "请检查股票代码是否正确（如 002471、603678）",
            }
            print(json.dumps(error, ensure_ascii=False, indent=2), file=sys.stderr)
            sys.exit(1)

        peers = fetch_peers(conn, stock)
    finally:
        conn.close()

    # 第二步：可选 — 韭研公社数据
    jiuyan = {"available": False, "warning": ""}
    if not args.no_jiuyan:
        jiuyan = try_fetch_jiuyan(pure_code)

    # 第三步：组装输出
    report = format_report(stock, peers, jiuyan, verbose=args.verbose)

    # 构建完整数据
    output = {
        "stock": {
            "code": stock["stock_code"],
            "name": stock["stock_name"],
            "description": stock.get("description"),
            "pe_median": stock.get("pe_median"),
            "pe_percentile": stock.get("pe_percentile"),
            "industry": {
                "level1": stock.get("industry_level1"),
                "level2": stock.get("industry_level2"),
                "level3": stock.get("industry_level3"),
            },
            "is_leader": stock.get("is_leader"),
            "fund": {
                "holding": stock.get("fund_holding"),
                "change": stock.get("fund_change"),
            },
            "northbound": {
                "holding": stock.get("northbound_holding"),
                "change": stock.get("northbound_change"),
            },
        },
        "peers": [
            {
                "code": p["stock_code"],
                "name": p["stock_name"],
                "pe_median": p.get("pe_median"),
                "pe_percentile": p.get("pe_percentile"),
                "is_leader": p.get("is_leader"),
            }
            for p in peers
        ],
        "jiuyan": jiuyan,
        "_report": report,
    }

    # 保存缓存
    if not args.no_cache:
        save_cache(db_code, output)

    if args.json:
        # JSON 输出不含 _report
        json_output = {k: v for k, v in output.items() if k != "_report"}
        print(json.dumps(json_output, ensure_ascii=False, indent=2))
    else:
        print(report)


if __name__ == "__main__":
    main()
