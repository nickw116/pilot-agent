import re
import logging
from html import unescape

import requests

from config import ARTICLE_URL_TEMPLATE, HEADERS

logger = logging.getLogger(__name__)


def _extract_nuxt_data(html: str) -> str:
    match = re.search(r'window\.__NUXT__=(.*?)(?:</script>)', html, re.DOTALL)
    if not match:
        raise ValueError("window.__NUXT__ not found in HTML")
    return match.group(1)


_UNICODE_MAP = {
    '\\u002F': '/', '\\u003C': '<', '\\u003E': '>',
    '\\u0026': '&', '\\u0022': '"',
}


def _unescape_nuxt_string(s: str) -> str:
    for k, v in _UNICODE_MAP.items():
        s = s.replace(k, v)
    s = s.replace("\\'", "'").replace('\\"', '"')
    s = s.replace('\\n', '\n').replace('\\t', '\t')
    return unescape(s)


def _extract_articles_from_nuxt(nuxt_str: str) -> list[dict]:
    articles = []
    for m in re.finditer(
        r'title:"([^"]+)",content:"(.*?)(?<!\\)",sensitive_words:"([^"]*)"'
        r',article_id:"([^"]+)"'
        r'.*?create_time:"([^"]+)"'
        r'.*?like_count:(\d+)'
        r'.*?comment_count:(\d+)'
        r'.*?forward_count:(\d+)'
        r'.*?collect_count:(\d+)',
        nuxt_str,
        re.DOTALL,
    ):
        title, content, _, article_id, create_time = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
        articles.append({
            "article_id": article_id,
            "title": _unescape_nuxt_string(title),
            "content_preview": _unescape_nuxt_string(content),
            "create_time": create_time,
        })
    return articles


def get_article_list(limit: int = 5, blogger: dict = None) -> list[dict]:
    page_url = blogger["url"] if blogger else None
    if not page_url:
        raise ValueError("blogger config with 'url' is required")
    logger.info("Fetching article list from %s", page_url)
    resp = requests.get(page_url, headers=HEADERS, timeout=30)
    resp.raise_for_status()

    nuxt_str = _extract_nuxt_data(resp.text)
    articles = _extract_articles_from_nuxt(nuxt_str)

    logger.info("Found %d articles", len(articles))
    return articles[:limit]


def get_article_content(article_id: str) -> dict:
    url = ARTICLE_URL_TEMPLATE.format(article_id=article_id)
    logger.info("Fetching article %s from %s", article_id, url)
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()

    nuxt_str = _extract_nuxt_data(resp.text)

    title_match = re.search(r'title:"([^"]+)"', nuxt_str)
    time_match = re.search(r'create_time:"([^"]+)"', nuxt_str)

    content_start = nuxt_str.find('content:"')
    if content_start < 0:
        raise ValueError(f"Could not extract content for article {article_id}")
    content_start += len('content:"')

    end_marker = '",sensitive_words:"'
    content_end = nuxt_str.find(end_marker, content_start)
    if content_end < 0:
        end_marker = '",sensitive_words:'
        content_end = nuxt_str.find(end_marker, content_start)
    if content_end < 0:
        raise ValueError(f"Could not find content end marker for article {article_id}")

    raw_content_nuxt = nuxt_str[content_start:content_end]
    raw_content = _unescape_nuxt_string(raw_content_nuxt)
    title = _unescape_nuxt_string(title_match.group(1)) if title_match else ""
    create_time = time_match.group(1) if time_match else ""

    stocks = []
    for sm in re.finditer(r'stock_list:\[(.*?)\]', nuxt_str):
        for nm in re.finditer(r'name:"([^"]+)",code:"([^"]+)"', sm.group(1)):
            stocks.append({"name": nm.group(1), "code": nm.group(2)})

    return {
        "article_id": article_id,
        "title": title,
        "content_html": raw_content,
        "create_time": create_time,
        "stocks": stocks,
        "url": url,
    }
