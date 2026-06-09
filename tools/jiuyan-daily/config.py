BASE_URL = "https://www.jiuyangongshe.com"

BLOGGERS = {
    "panqianjiyao": {
        "name": "盘前纪要",
        "user_id": "4df747be1bf143a998171ef03559b517",
        "url": f"{BASE_URL}/u/4df747be1bf143a998171ef03559b517",
        "keywords": ["盘前纪要", "热点板块", "涨停事件"],
    },
    "caiwenSixiang": {
        "name": "财闻私享",
        "user_id": "53a66da6769e46db8ee8bd1a061238d4",
        "url": f"{BASE_URL}/u/53a66da6769e46db8ee8bd1a061238d4",
        "keywords": ["晚间资讯", "盘中发酵", "信息差"],
    },
}

ARTICLE_URL_TEMPLATE = f"{BASE_URL}/a/{{article_id}}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}
