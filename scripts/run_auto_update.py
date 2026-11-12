"""Safely refresh one static issue, retaining published data on failure."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import build_site_payload
import generate_amazon_weekly
import generate_weekly
import update_ai_news
import update_amazon_news
from generate_cards import request_cards
from generate_opinion import _write_json_atomic

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
BEIJING = ZoneInfo("Asia/Shanghai")


def today_bjt() -> date:
    return datetime.now(BEIJING).date()


def monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def amazon_bucket(article: dict) -> str | None:
    name = article.get("sourceName", "")
    title = article.get("title", "")
    if name.startswith("AWS ") or name.startswith("About Amazon"):
        return None
    if re.search(r"SAMPLE HOUSE|十年亚马逊生涯|红海类目", title, re.I):
        return None
    # A competitor's own results or discounts do not become Amazon news just
    # because a publisher adds its generic cross-border suffix to the title.
    if re.search(r"Shopee|TikTok Shop|Lazada|速卖通|Temu", title, re.I) and not re.search(
        r"亚马逊|Amazon|欧盟小包|IOSS", title, re.I
    ):
        return None
    if re.search(r"亚马逊.{0,12}(?:授权升级|规则变更|重大政策)|(?:SUP|SPP).{0,12}授权", title, re.I):
        return "news"
    if re.search(r"亚马逊.{0,16}(?:FBA|物流|配送)?.{0,8}费用调整", title, re.I):
        return "news"
    if re.search(r"黑五|网一|Deal.{0,8}(?:提报|截止)", title, re.I):
        return "watch"
    if re.search(r"政策|新政|费用|收费|物流|延误|合规|风险|监管|规则|授权|专利|policy|fees?|shipping|logistics|IOSS|关税|海关", title, re.I):
        return "watch"
    if re.search(r"工具|方法|指南|如何|做法|实践|案例|破局|复盘|经验|预计送达时间|订单.{0,8}回来|MCF|ASIN|QA|build|guide|workflow", title, re.I):
        return "learn"
    if re.search(r"发布|宣布|推出|上线|重大|改革|announc|launch|introduc", title, re.I) and re.search(r"亚马逊|Amazon|卖家|跨境", title, re.I):
        return "news"
    if "亚马逊" in title and article.get("sourceName", "").startswith("雨果"):
        return "learn"
    return None


def amazon_impact(article: dict, bucket: str) -> int:
    title = article.get("title", "")
    if bucket == "watch":
        if re.search(r"黑五|网一|Deal.{0,8}(?:提报|截止)", title, re.I):
            return 95
        if re.search(r"亚马逊.*(?:授权|政策|费用|收费|规则|合规)", title, re.I):
            return 100
        if re.search(r"物流|延误|发货", title, re.I):
            return 90
        if re.search(r"IOSS|关税|税费", title, re.I):
            return 80
        if re.search(r"亚马逊", title) and re.search(r"上架|专利|合规", title):
            return 70
        return 30
    if bucket == "news":
        if re.search(r"授权升级|规则变更|重大政策|SUP|SPP", title, re.I):
            return 110
        if re.search(r"费用调整|FBA.*上涨", title, re.I):
            return 105
        return 30 if re.search(r"亚马逊|Amazon", title, re.I) else 10
    return 10


def amazon_sources(articles: list[dict], day: date) -> list[dict]:
    start = monday(day).isoformat()
    current = [item for item in articles if start <= item.get("date", "") <= day.isoformat()]
    groups = {key: [] for key in ("news", "watch", "learn")}
    for article in current:
        bucket = amazon_bucket(article)
        if bucket:
            groups[bucket].append(article)
    ranked = []
    for bucket, rows in groups.items():
        rows.sort(key=lambda row: (amazon_impact(row, bucket), row.get("date", ""), row.get("title", "")), reverse=True)
        ranked.extend((bucket, row) for row in rows)
    # The daily refresh must cover the whole Monday-to-today window. First
    # preserve one relevant article per day, then fill by seller impact.
    picked = []
    seen = set()
    for publication_day in sorted({row["date"] for _, row in ranked}):
        choices = [(bucket, row) for bucket, row in ranked if row["date"] == publication_day]
        if choices:
            bucket, row = max(choices, key=lambda pair: amazon_impact(pair[1], pair[0]))
            picked.append((bucket, row))
            seen.add(row["sourceUrl"])
    for bucket, row in sorted(ranked, key=lambda pair: (amazon_impact(pair[1], pair[0]), pair[1]["date"]), reverse=True):
        if len(picked) >= 15:
            break
        if row["sourceUrl"] not in seen:
            picked.append((bucket, row))
            seen.add(row["sourceUrl"])
    picked.sort(key=lambda pair: ("news", "watch", "learn").index(pair[0]))
    missing_body = [row for _, row in picked if not row.get("bodyText")]
    with ThreadPoolExecutor(max_workers=8) as pool:
        fetched = list(pool.map(
            lambda row: update_amazon_news.fetch_article(row["sourceName"], row["sourceUrl"]),
            missing_body,
        ))
    refreshed_by_url = dict(zip((row["sourceUrl"] for row in missing_body), fetched))
    sources = []
    for bucket, article in picked:
        body = article.get("bodyText", "")
        if not body:
            refreshed = refreshed_by_url.get(article["sourceUrl"])
            body = refreshed.get("bodyText", "") if refreshed else ""
        scope = "body" if len(body.strip()) >= 80 else "title"
        excerpt = body[:7000] if scope == "body" else article["title"]
        sources.append({"id": f"A{len(sources) + 1}", "title": article["title"],
                        "sourceName": article["sourceName"], "publishedAt": article["date"],
                        "url": article["sourceUrl"], "summary": article.get("summary", ""),
                        "excerpt": excerpt, "evidenceScope": scope, "bucket": bucket,
                        "alsoBuckets": ["watch"] if bucket == "news" and re.search(r"授权|政策|规则", article["title"]) else []})
    return sources


def public_amazon_sources(sources: list[dict]) -> list[dict]:
    return [{key: value for key, value in source.items() if key != "excerpt"} for source in sources]


def refresh_amazon(day: date, card_client=request_cards,
                   article_client=generate_amazon_weekly.request_article) -> bool:
    before = json.loads((DATA / "amazon.json").read_text(encoding="utf-8"))
    collected = update_amazon_news.main()
    path = DATA / "amazon.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    live_articles = collected.get("articles", payload["articles"]) if isinstance(collected, dict) else payload["articles"]
    sources = amazon_sources(live_articles, day)
    public_sources = public_amazon_sources(sources)
    week = generate_weekly.week_key(monday(day))
    old_ai = before.get("ai", {})
    model = os.environ.get("AI_NEWS_MODEL", "deepseek-flash").strip()
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if (sources or old_ai.get("article")) and (not model or not key):
        raise RuntimeError("model credentials are not configured")
    if old_ai.get("week") and old_ai.get("week") != week and old_ai.get("article"):
        # Monday's collection completes the prior week before opening the new one.
        # Merge with yesterday's saved rows so a busy source's six-item cap does
        # not silently remove a Monday-to-Sunday original from the final issue.
        merged = {item["sourceUrl"]: item for item in before.get("articles", []) + live_articles}
        prior_day = day - timedelta(days=1)
        prior_sources = amazon_sources(list(merged.values()), prior_day)
        prior_cards = (old_ai.get("cards", {}) if old_ai.get("sources") == public_amazon_sources(prior_sources)
                       else card_client(prior_sources, model, key, amazon=True))
        prior_article = generate_amazon_weekly.generate(prior_sources, prior_day, model, key,
                                                       client=article_client)
        final_prior = {**old_ai, "date": prior_day.isoformat(), "sources": public_amazon_sources(prior_sources),
                       "cards": prior_cards, "article": prior_article, "model": model}
        generate_amazon_weekly.close_prior_issue(final_prior, week, DATA / "amazon-weekly")
    if old_ai.get("week") == week and old_ai.get("sources") == public_sources:
        cards = old_ai.get("cards", {})
    else:
        cards = card_client(sources, model, key, amazon=True)
    if (old_ai.get("week") == week and old_ai.get("date") == day.isoformat()
            and old_ai.get("sources") == public_sources and old_ai.get("article")):
        article = old_ai.get("article")
    else:
        article = generate_amazon_weekly.generate(sources, day, model, key, client=article_client)
    payload["ai"] = {"week": week, "date": day.isoformat(), "sources": public_sources, "cards": cards,
                     "article": article, "model": model}
    _write_json_atomic(path, payload)
    return True


def shown_week(mode: str) -> str:
    if mode == "weekly":
        index = json.loads((DATA / "weekly" / "index.json").read_text(encoding="utf-8"))
        return index["weeks"][0]["week"] if index["weeks"] else "—"
    amazon = json.loads((DATA / "amazon.json").read_text(encoding="utf-8"))
    if amazon.get("ai", {}).get("week"):
        return amazon["ai"]["week"]
    updated = date.fromisoformat(amazon["updatedAt"][:10])
    return generate_weekly.week_key(monday(updated))


def run(mode: str, day: date | None = None, *, amazon_refresh=refresh_amazon,
        ai_refresh=update_ai_news.main, weekly_publish=generate_weekly.publish_complete_week) -> bool:
    if mode not in ("weekly", "amazon"):
        raise ValueError("unknown update mode")
    day = day or today_bjt()
    target = generate_weekly.week_key(monday(day) - timedelta(days=7) if mode == "weekly" else monday(day))
    status_path = DATA / "update-status.json"
    status = json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() else {}
    with tempfile.TemporaryDirectory() as directory:
        backup = Path(directory) / "data"
        shutil.copytree(DATA, backup)
        try:
            if mode == "weekly":
                ai_refresh()
                news = json.loads((DATA / "news.json").read_text(encoding="utf-8"))
                if any(str(row.get("status", "")).startswith("failed")
                       for row in news.get("sourceCoverage", {}).values()):
                    raise RuntimeError("one or more sources failed")
                weekly_publish(monday(day) - timedelta(days=7))
            else:
                amazon_refresh(day)
            status[mode] = {"state": "ok", "attemptedWeek": target,
                            "checkedAt": datetime.now(timezone.utc).isoformat()}
            _write_json_atomic(status_path, status)
            build_site_payload.main()
            return True
        except Exception as exc:
            shutil.rmtree(DATA)
            shutil.copytree(backup, DATA)
            status[mode] = {"state": "failed", "attemptedWeek": target,
                            "shownWeek": shown_week(mode),
                            "checkedAt": datetime.now(timezone.utc).isoformat()}
            _write_json_atomic(status_path, status)
            build_site_payload.main()
            print(f"{mode} update failed: {type(exc).__name__}: {exc}")
            return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("weekly", "amazon"), required=True)
    args = parser.parse_args()
    return 0 if run(args.mode) else 1


if __name__ == "__main__":
    raise SystemExit(main())
