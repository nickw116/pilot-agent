#!/usr/bin/env python3
"""Web reader via Zhipu/ZAI MCP (webReader) - extract main text from a URL."""
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
MCP_ENDPOINT = f"https://{DOMAIN}/api/mcp/web_reader/mcp"
TOOL_NAME = "webReader"
# ================================================


def call_web_reader(url, return_format="markdown", no_cache=False, timeout=None,
                    with_images_summary=False, with_links_summary=False):
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
        "url": url,
        "return_format": return_format,
        "no_cache": no_cache,
    }
    if timeout:
        arguments["timeout"] = timeout
    if with_images_summary:
        arguments["with_images_summary"] = True
    if with_links_summary:
        arguments["with_links_summary"] = True

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
    """解析双重编码的 JSON，提取正文 content。"""
    try:
        s = raw.strip()
        if s.startswith('"'):
            inner = json.loads(s)
            if isinstance(inner, str) and inner.strip().startswith("{"):
                parsed = json.loads(inner)
                return parsed.get("content", parsed)
            if isinstance(inner, dict):
                return inner.get("content", inner)
            return inner
        if s.startswith("{"):
            return json.loads(s).get("content", s)
        return raw
    except Exception:
        return raw


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract main text content from a URL.")
    parser.add_argument("url", help="要读取的网页 URL")
    parser.add_argument("--format", default="markdown",
                        choices=["markdown", "text"],
                        help="返回格式（markdown / text），默认 markdown")
    parser.add_argument("--no-cache", action="store_true",
                        help="禁用缓存，强制重新抓取")
    parser.add_argument("--timeout", type=int, default=None,
                        help="请求超时（秒）")
    parser.add_argument("--images-summary", action="store_true",
                        help="附上图片清单摘要")
    parser.add_argument("--links-summary", action="store_true",
                        help="附上链接清单摘要")
    args = parser.parse_args()

    print(call_web_reader(
        args.url,
        return_format=args.format,
        no_cache=args.no_cache,
        timeout=args.timeout,
        with_images_summary=args.images_summary,
        with_links_summary=args.links_summary,
    ))
