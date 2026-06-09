import re
import logging

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["script", "style"]):
        tag.decompose()

    # Replace <br> with newlines before extracting text
    for br in soup.find_all("br"):
        br.replace_with("\n")

    # Replace <p> blocks with double newline
    for p in soup.find_all("p"):
        p.insert_after("\n\n")

    text = soup.get_text(separator="")
    # Collapse excessive whitespace
    lines = [line.strip() for line in text.splitlines()]
    text = "\n".join(line for line in lines if line)
    # Remove non-breaking spaces
    text = text.replace('\xa0', ' ')
    return text


def parse_hot_sectors(text: str) -> list[dict]:
    sectors = []
    hotspot_match = re.search(r'(?:一、)?昨日热点(.*?)(?=二[、．.]|$)', text, re.DOTALL)
    if not hotspot_match:
        return sectors

    block = hotspot_match.group(1)
    # Match patterns like "板块：个股1、个股2" or "MLCC：风华高科"
    pattern = re.compile(r'([^\n：:]+)[：:]\s*([^\n]+)')
    for m in pattern.finditer(block):
        sector_name = m.group(1).strip()
        stocks_str = m.group(2).strip()
        if not sector_name or len(sector_name) > 20:
            continue
        # Skip numbered items that aren't sector names
        if re.match(r'^[\d一二三四五六七八九十]+[、．.]', sector_name):
            continue
        stocks = [s.strip() for s in re.split(r'[、，,]+', stocks_str) if s.strip()]
        sectors.append({"sector": sector_name, "stocks": stocks})

    return sectors


def parse_events(text: str) -> list[dict]:
    events = []
    # Find section boundaries: 二、xxx, 三、xxx, etc.
    section_pattern = re.compile(
        r'([二三四五六七八九十]+[、．.])\s*([^\n]+)\n(.*?)(?=[三四五六七八九十]+[、．.]|No\.\d|$)',
        re.DOTALL,
    )

    hotspot_end = re.search(r'二[、．.]', text)
    if hotspot_end:
        body = text[hotspot_end.start():]
    else:
        body = text

    for m in section_pattern.finditer(body):
        number = m.group(1)
        title = m.group(2).strip()
        content = m.group(3).strip()
        # Clean up multi-line content
        content = re.sub(r'\n{2,}', '\n', content)
        if title:
            events.append({"number": number, "title": title, "content": content})

    return events


def parse_article(article: dict) -> dict:
    html = article.get("content_html", "")
    text = html_to_text(html) if "<" in html else html

    sectors = parse_hot_sectors(text)
    events = parse_events(text)

    title_match = re.search(r'No\.\d+\s*(.*)', text)
    section_title = title_match.group(1).strip() if title_match else ""

    return {
        "article_id": article["article_id"],
        "title": article.get("title", ""),
        "create_time": article.get("create_time", ""),
        "url": article.get("url", ""),
        "section_title": section_title,
        "sectors": sectors,
        "events": events,
        "stocks": article.get("stocks", []),
        "full_text": text,
    }
