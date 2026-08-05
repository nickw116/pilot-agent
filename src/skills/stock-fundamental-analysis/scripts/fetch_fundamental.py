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




def format_report(stock: dict, peers: list[dict], jiuyan: dict, verbose: bool = False) -> str:
    """最小集行业报告（用户定制版，2026-07-23 重构）

    只输出:股票代码、行业分类、龙头标记、主营业务描述、参考龙头列表。
    不输出:估值水平(PE 已从本地 DB 清空)、资金动向(已清空)、价格行情。
    实时估值/行情请走 check_pe_quality.py / westockdata skill。
    """
    code = stock["stock_code"]
    name = stock["stock_name"]

    # 行业分类（一/二/三级）
    l1 = stock.get("industry_level1") or ""
    l2 = stock.get("industry_level2") or ""
    l3 = stock.get("industry_level3") or ""

    if l1 and l2 and l3:
        industry = f"{l1} → {l2} → {l3}"
    elif l1 and l2:
        industry = f"{l1} → {l2}"
    elif l1:
        industry = l1
    else:
        industry = "未分类"

    # 龙头标记
    is_leader = stock.get("is_leader") == "是"
    leader_label = "✅ 行业龙头" if is_leader else "一般标的"

    # 主营业务
    description = stock.get("description") or "暂无描述"

    # 同行业龙头列表
    leader_peers = [
        p for p in (peers or [])
        if p.get("is_leader") == "是" and p["stock_code"] != code
    ]

    lines = []
    lines.append(f"## {name}（{code}）")
    lines.append("")
    lines.append("### 公司基本面")
    lines.append(f"- **股票代码**: {code}")
    lines.append(f"- **所属行业**: {industry}")
    lines.append(f"- **行业地位**: {leader_label}")
    lines.append(f"- **主营业务**: {description}")

    if leader_peers:
        lines.append("")
        lines.append("### 同行业龙头（参考）")
        for p in leader_peers[:10]:
            entry = f"- {p['stock_name']}（{p['stock_code']}）"
            parts = [p.get(k) or "" for k in ("industry_level1", "industry_level2", "industry_level3")]
            parts = [x for x in parts if x]
            if parts:
                entry += f" — {' / '.join(parts)}"
            lines.append(entry)

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("### 📌 数据来源")
    lines.append("- 行业/龙头/描述:本地知识库 stocks_db（PostgreSQL）")
    lines.append("- 实时估值/行情:`check_pe_quality.py`(PE TTM)/ `westockdata` skill")

    return chr(10).join(lines)



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
