"""Check the static Amazon dataset before publication."""

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
data = json.loads((ROOT / "data" / "amazon.json").read_text(encoding="utf-8"))
assert data["sourceType"] == "public_publisher_websites_not_wechat_posts"
assert not data["errors"], data["errors"]
allowed = {
    "雨果网／雨果跨境": "www.cifnews.com",
    "AMZ123": "www.amz123.com",
    "亚马逊全球开店": "globalselling.amazon.com",
    "亚马逊广告": "advertising.amazon.com",
    "About Amazon · AI": "www.aboutamazon.com",
    "About Amazon · Innovation": "www.aboutamazon.com",
    "AWS 机器学习博客": "aws.amazon.com",
}
today = datetime.now(timezone.utc).date()
seen = set()
counts = Counter()
for article in data["articles"]:
    assert article["title"].strip()
    date = datetime.fromisoformat(article["date"]).date()
    assert date <= today
    assert urlparse(article["sourceUrl"]).scheme == "https"
    assert urlparse(article["sourceUrl"]).hostname == allowed[article["sourceName"]]
    assert article["sourceUrl"] not in seen
    seen.add(article["sourceUrl"])
    counts[article["sourceName"]] += 1
assert set(counts) == set(allowed)
assert all(count >= 2 for count in counts.values())
print(f"verified={len(seen)} sources={len(counts)} oldest={min(a['date'] for a in data['articles'])} newest={max(a['date'] for a in data['articles'])}")
