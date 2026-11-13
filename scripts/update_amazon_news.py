"""Collect dated Amazon/cross-border articles from free public publisher pages.

These websites correspond to requested WeChat account names. This collector does
not read or claim to archive their WeChat posts.
"""

import json
import gzip
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "amazon.json"
BEIJING = ZoneInfo("Asia/Shanghai")
SITES = [
    ("雨果网／雨果跨境", "https://www.cifnews.com/amazon", r"https://www\.cifnews\.com/article/\d+"),
    ("AMZ123", "https://www.amz123.com/t", r"https://www\.amz123\.com/t/[A-Za-z0-9]+"),
    ("亚马逊全球开店", "https://globalselling.amazon.com/en/news-center", r"https://globalselling\.amazon\.com/news-center/news-center-\d+"),
    ("亚马逊广告", "https://advertising.amazon.com/zh-cn/library/newsroom", r"https://advertising\.amazon\.com/zh-cn/library/(?:news|resources/whats-new)/[A-Za-z0-9_-]+"),
]
RSS_SITES = [
    ("About Amazon · AI", "https://www.aboutamazon.com/news/tag/artificial-intelligence/feed"),
    ("About Amazon · Innovation", "https://www.aboutamazon.com/news/innovation-at-amazon/feed"),
]
DATE_RE = re.compile(r"\b(20\d\d-\d\d-\d\d)(?:T|\b)")


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.meta = {}

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "a" and values.get("href"):
            self.links.append(values["href"])
        if tag == "meta":
            key = values.get("property") or values.get("name")
            if key and values.get("content"):
                self.meta[key.lower()] = values["content"]


class ArticleBodyParser(HTMLParser):
    """Read paragraph text inside the publisher's article body, not sidebars."""

    CONTAINERS = {"article-content", "article-detail-content", "article-detail-main", "article-content-box",
                  "article-body", "post-content", "rich-text"}
    VOID = {"br", "img", "meta", "link", "input", "source", "hr", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.body_depth = None
        self.paragraph_depth = None
        self.parts = []
        self.paragraphs = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag not in self.VOID:
            self.depth += 1
        classes = set((values.get("class") or "").split())
        if self.body_depth is None and classes & self.CONTAINERS:
            self.body_depth = self.depth
        elif self.body_depth is not None and self.paragraph_depth is None and tag in {"p", "h2", "h3", "li"}:
            self.paragraph_depth = self.depth
            self.parts = []

    def handle_data(self, data):
        if self.paragraph_depth is not None:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if self.paragraph_depth == self.depth and tag in {"p", "h2", "h3", "li"}:
            value = cleaned("".join(self.parts))
            if len(value) >= 12:
                self.paragraphs.append(value)
            self.paragraph_depth = None
            self.parts = []
        if self.body_depth == self.depth and tag in {"div", "article", "main"}:
            self.body_depth = None
        if tag not in self.VOID:
            self.depth = max(0, self.depth - 1)


def article_body(html):
    parser = ArticleBodyParser()
    parser.feed(html)
    # Keep enough source context for methods that appear after the introduction.
    return "\n".join(parser.paragraphs)[:7000]


def get_page(url):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; AI-News/1.0)", "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7"},
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=16) as response:
                content = response.read(1_500_000)
                # Some publisher pages return gzip bytes even without an explicit
                # Accept-Encoding request. Decode before parsing metadata/body text.
                if content.startswith(b"\x1f\x8b"):
                    content = gzip.decompress(content)
                charset = response.headers.get_content_charset() or "utf-8"
                return content.decode(charset, "replace")
        except TimeoutError:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def cleaned(value):
    return re.sub(r"\s+", " ", unescape(value or "")).strip()


def article_date(site, html, meta):
    values = [
        meta.get("article:published_time", ""),
        meta.get("datepublished", ""),
        meta.get("pubdate", ""),
    ]
    if site == "雨果网／雨果跨境":
        match = re.search(r'<div class="date">\s*(20\d\d-\d\d-\d\d)', html)
        if match:
            values.append(match.group(1))
    elif site == "亚马逊全球开店":
        match = re.search(r"(20\d\d)年(\d{1,2})月(\d{1,2})日", html)
        if match:
            values.append(f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}")
    else:
        values += re.findall(r'"datePublished"\s*:\s*"([^"]+)', html)[:1]
    today = datetime.now(BEIJING).date()
    for value in values:
        match = DATE_RE.search(value)
        if not match:
            continue
        try:
            date = datetime.fromisoformat(match.group(1)).date()
        except ValueError:
            continue
        if date <= today:
            return date.isoformat()
    return None


def fetch_article(site, url):
    try:
        html = get_page(url)
        parser = PageParser()
        parser.feed(html)
        title = cleaned(parser.meta.get("og:title") or parser.meta.get("twitter:title"))
        if not title:
            match = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
            title = cleaned(re.sub(r"<[^>]+>", "", match.group(1))) if match else ""
        date = article_date(site, html, parser.meta)
        if not (title and date):
            return None
        summary = cleaned(parser.meta.get("og:description") or parser.meta.get("description"))
        body = article_body(html)
        return {"title": title, "date": date, "sourceName": site, "sourceUrl": url,
                "summary": summary[:240], "bodyText": body}
    except Exception:
        return None


def fetch_rss(site, feed_url):
    try:
        xml = get_page(feed_url)
        root = ET.fromstring(xml)
        articles = []
        for item in root.findall("./channel/item")[:10]:
            title = cleaned(item.findtext("title"))
            url = (item.findtext("link") or "").strip().split("?", 1)[0]
            raw_date = item.findtext("pubDate") or ""
            try:
                date = parsedate_to_datetime(raw_date).astimezone(timezone.utc).date()
            except (TypeError, ValueError, OverflowError):
                continue
            if not title or not url.startswith("https://") or date > datetime.now(BEIJING).date():
                continue
            summary = cleaned(re.sub(r"<[^>]+>", " ", item.findtext("description") or ""))
            articles.append({"title": title, "date": date.isoformat(), "sourceName": site,
                             "sourceUrl": url, "summary": summary[:240], "bodyText": ""})
            if len(articles) == 6:
                break
        return articles
    except Exception:
        return []


def merge_week_articles(previous, fresh, day):
    start = (day - timedelta(days=day.weekday())).isoformat()
    by_url = {item["sourceUrl"]: item for item in fresh}
    for item in previous:
        if start <= item.get("date", "") <= day.isoformat():
            current = by_url.get(item["sourceUrl"])
            if current is None or (not current.get("bodyText") and item.get("bodyText")):
                by_url[item["sourceUrl"]] = item
    return list(by_url.values())


def main():
    previous = json.loads(OUT.read_text(encoding="utf-8")).get("articles", []) if OUT.exists() else []
    candidates = []
    errors = []
    for site, listing, pattern in SITES:
        try:
            html = get_page(listing)
            parser = PageParser()
            parser.feed(html)
            seen = set()
            for href in parser.links:
                url = urllib.parse.urljoin(listing, href).split("?", 1)[0].split("#", 1)[0]
                if re.fullmatch(pattern, url) and url not in seen:
                    candidates.append((site, url))
                    seen.add(url)
                    if len(seen) == 30:
                        break
            if not seen:
                errors.append(f"{site}: no article links")
        except Exception as exc:
            errors.append(f"{site}: {type(exc).__name__}")
    articles = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(fetch_article, site, url) for site, url in candidates]
        rss_futures = {pool.submit(fetch_rss, site, url): site for site, url in RSS_SITES}
        for future in as_completed(futures):
            item = future.result()
            if item:
                articles.append(item)
        for future in as_completed(rss_futures):
            site = rss_futures[future]
            items = future.result()
            articles.extend(items)
            if not items:
                errors.append(f"{site}: no dated RSS article")
    by_site = {}
    for site, _, _ in SITES:
        site_items = sorted((item for item in articles if item["sourceName"] == site), key=lambda item: (item["date"], item["sourceUrl"]), reverse=True)
        by_site[site] = site_items[:30]
        if not by_site[site]:
            errors.append(f"{site}: no dated article")
    for site, _ in RSS_SITES:
        site_items = sorted((item for item in articles if item["sourceName"] == site), key=lambda item: (item["date"], item["sourceUrl"]), reverse=True)
        by_site[site] = site_items[:10]
    today = datetime.now(BEIJING).date()
    all_articles = merge_week_articles(previous, [item for values in by_site.values() for item in values], today)
    output = {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "sourceType": "public_publisher_websites_not_wechat_posts",
        "articles": sorted(all_articles, key=lambda item: (item["date"], item["sourceName"]), reverse=True),
        "errors": errors,
    }
    if errors or not output["articles"]:
        raise RuntimeError(f"Amazon source collection incomplete; retained previous dataset: {errors}")
    # Full page text is only used during this run. Do not republish it in the
    # repository or static site; the linked publisher remains the source.
    public_output = {**output, "articles": [
        {key: value for key, value in item.items() if key != "bodyText"}
        for item in output["articles"]]}
    OUT.write_text(json.dumps(public_output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"counts": {name: len(items) for name, items in by_site.items()}, "errors": errors, "output": str(OUT)}, ensure_ascii=True))
    return output


if __name__ == "__main__":
    main()
