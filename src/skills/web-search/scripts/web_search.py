#!/usr/bin/env python3
"""Web search via Zhipu/ZAI MCP (web_search_prime)."""
import os
import sys
import json
import uuid
import argparse
import requests

# ================= Configuration =================
API_KEY = os.getenv("ZAI_API_KEY", "")
AI_MODE = os.environ.get("Z_AI_MODE")
DOMAIN = "api.z.ai" if AI_MODE == "ZAI" else "open.bigmodel.cn"
MCP_ENDPOINT = f"https://{DOMAIN}/api/mcp/web_search_prime/mcp"
TOOL_NAME = "web_search_prime"
# ================================================


def call_web_search(query, content_size="medium", recency=None, location="cn", domain_filter=None):
    if not API_KEY:
        return "Error: ZAI_API_KEY 环境变量未设置。"

    session_id = str(uuid.uuid4())
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Mcp-Session-Id": session_id,
        "Session-Id": session_id,
    }

    arguments = {
        "search_query": query,
        "content_size": content_size,
        "location": location,
    }
    if recency:
        arguments["search_recency_filter"] = recency
    if domain_filter:
        arguments["search_domain_filter"] = domain_filter

    payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "id": session_id,
        "params": {"name": TOOL_NAME, "arguments": arguments},
    }

    try:
        response = requests.post(
            MCP_ENDPOINT, headers=headers, json=payload, stream=True, timeout=60
        )
        if response.status_code != 200:
            return f"HTTP Error {response.status_code}: {response.text}"

        full_content = []
        for line in response.iter_lines():
            if not line:
                continue
            decoded = line.decode("utf-8")
            if not decoded.startswith("data:"):
                continue
            json_str = decoded[5:].strip()
            if not json_str or json_str == "[DONE]":
                continue
            try:
                data = json.loads(json_str)
                if data.get("error"):
                    return f"API Error: {data['error']}"
                content = data.get("result", {}).get("content")
                if not content:
                    continue
                if isinstance(content, str):
                    full_content.append(content)
                elif isinstance(content, list):
                    full_content.extend(
                        item.get("text", "")
                        for item in content
                        if item.get("type") == "text"
                    )
            except json.JSONDecodeError:
                continue

        return _clean("".join(full_content))

    except Exception as e:
        return f"Request Failed: {e}"


def _clean(raw):
    """解析双重编码的 JSON 结果。"""
    try:
        s = raw.strip()
        if s.startswith('"'):
            inner = json.loads(s)
            if isinstance(inner, str) and inner.strip().startswith("["):
                return json.loads(inner)
            if isinstance(inner, str) and inner.strip().startswith("{"):
                return json.loads(inner).get("content", inner)
            if isinstance(inner, (list, dict)):
                return inner
        if s.startswith("["):
            return json.loads(s)
        if s.startswith("{"):
            return json.loads(s).get("content", json.loads(s))
        return raw
    except Exception:
        return raw


def _format(result):
    if isinstance(result, list):
        lines = []
        for i, item in enumerate(result, 1):
            if not isinstance(item, dict):
                continue
            title = item.get("title", "")
            link = item.get("link", "")
            content = item.get("content", "")
            date = item.get("publish_date", "")
            lines.append(f"[{i}] {title}")
            if link:
                lines.append(f"    {link}")
            if content:
                lines.append(f"    {content}")
            if date:
                lines.append(f"    ({date})")
            lines.append("")
        return "\n".join(lines) if lines else str(result)
    return str(result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Web search via Zhipu/ZAI MCP.")
    parser.add_argument("query", help="搜索关键词")
    parser.add_argument("--content-size", default="medium",
                        choices=["medium", "high"],
                        help="摘要详细度（medium≈400-600字 / high≈2500字），默认 medium")
    parser.add_argument("--recency", default=None,
                        choices=["oneDay", "oneWeek", "oneMonth", "oneYear", "noLimit"],
                        help="时间范围过滤，默认不限")
    parser.add_argument("--location", default="cn",
                        choices=["cn", "us"],
                        help="地区（cn 中文区 / us 非中文区），默认 cn")
    parser.add_argument("--domain", default=None,
                        help="限定域名（如 www.example.com）")
    args = parser.parse_args()

    result = call_web_search(
        args.query,
        content_size=args.content_size,
        recency=args.recency,
        location=args.location,
        domain_filter=args.domain,
    )
    print(_format(result))
