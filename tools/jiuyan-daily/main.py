#!/usr/bin/env python3
import argparse
import json
import logging
import sys
from datetime import date

from config import BLOGGERS
from jiuyan_fetcher import get_article_list, get_article_content
from jiuyan_parser import parse_article

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def fetch_and_parse(blogger_key: str, date_filter: str = None, latest: int = 1):
    blogger = BLOGGERS[blogger_key]
    logger.info("Fetching articles for blogger: %s (%s)", blogger["name"], blogger_key)
    articles = get_article_list(limit=min(latest * 2, 10), blogger=blogger)

    if date_filter:
        articles = [a for a in articles if date_filter in a["create_time"]]
        if not articles:
            logger.warning("No articles found for date %s", date_filter)
            return []

    results = []
    for article in articles[:latest]:
        logger.info("Processing: %s (%s)", article["title"], article["create_time"])

        full = get_article_content(article["article_id"])
        parsed = parse_article(full)
        parsed["blogger"] = blogger_key
        parsed["blogger_name"] = blogger["name"]

        print("\n" + "=" * 60)
        print(json.dumps(parsed, ensure_ascii=False, indent=2))
        print("=" * 60 + "\n")

        results.append(parsed)

    return results


def main():
    parser = argparse.ArgumentParser(description="韭研公社多博主文章获取与总结")
    parser.add_argument(
        "--blogger", "-b",
        help="指定博主 (panqianjiyao, caiwenSixiang, all)",
        default="all",
    )
    parser.add_argument("--date", "-d", help="指定日期 (YYYY-MM-DD)", default=None)
    parser.add_argument("--latest", "-n", type=int, default=1, help="获取最近N篇 (默认1)")
    parser.add_argument("--debug", action="store_true", help="调试模式")
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.blogger == "all":
        targets = list(BLOGGERS.keys())
    elif args.blogger in BLOGGERS:
        targets = [args.blogger]
    else:
        print(f"未知博主: {args.blogger}")
        print(f"可选: {', '.join(BLOGGERS.keys())}, all")
        sys.exit(1)

    date_filter = args.date or date.today().isoformat()
    total = 0
    for blogger_key in targets:
        try:
            results = fetch_and_parse(
                blogger_key=blogger_key,
                date_filter=date_filter,
                latest=args.latest,
            )
            total += len(results)
        except Exception as e:
            logger.error("Failed for %s: %s", blogger_key, e, exc_info=True)

    if total == 0:
        print("未找到符合条件的文章")
        sys.exit(1)
    logger.info("Done! Processed %d articles total", total)


if __name__ == "__main__":
    main()
